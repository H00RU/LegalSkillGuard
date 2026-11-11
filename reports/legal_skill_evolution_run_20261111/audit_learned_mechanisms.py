"""Inventory accepted learning and dedicated mechanisms without model calls."""
from datetime import datetime, timezone
from collections import Counter
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3

from experiments.legal_skill_evolution import PROFILE
from legal_skill_guard.skill_evolution.study import load_json, PILOT_ARMS
from legal_skill_guard.skill_evolution.objects import Library, coupled_blocks


def source_coverage(root, folder, arms):
    """Keep answering, selection exposure and declared learned support separate."""
    manifest = load_json(root / 'reports/legal_skill_evolution_plan_20261111/candidate_source_manifest.json')
    batches = {r['source_key']: n for n, batch in enumerate(manifest['source_sequence'], 1) for r in batch['sources']}
    datasets = {r['key']: dataset for dataset, partitions in manifest['datasets'].items() for r in partitions['train']}
    with sqlite3.connect('file:' + str(root / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') + '?mode=ro', uri=True) as db:
        settled = {}
        for identity, raw in db.execute("select id,result from calls where role='teacher' and status='completed'"):
            value = json.loads(raw)
            if value.get('request_sha256'):settled[value['request_sha256']] = (identity, value)
    result = {}
    for arm in ('NoSkill', *arms):
        initial, direct, support = {}, {}, {}
        for path in sorted((folder / arm).glob('initial_B*/*.json')):
            row = load_json(path)
            if row['source'] in initial:raise ValueError('A TRAIN parent has duplicate first-attempt checkpoints')
            initial[row['source']] = row
        teacher_calls = []
        for path in sorted((folder / arm).glob('teacher_B*.json')):
            response = load_json(path);identity, physical = settled[response['request_sha256']]
            if response['source_ids'] != physical['source_ids'] or response['value'] != physical['value']:
                raise ValueError('A teacher exposure record differs from its settled physical response')
            batch = int(path.stem.split('_B')[1])
            context = load_json(folder / arm / f'update_context_B{batch}.json')
            if response['source_ids'] != context['cohort']:raise ValueError('Actual teacher sources differ from saved context')
            teacher_calls.append({'batch': batch, 'physical_ledger_id': identity, 'direct_sources': response['source_ids']})
            for key in response['source_ids']:
                if key not in datasets or batches[key] > batch:raise ValueError('Teacher exposure is outside seen TRAIN')
                direct.setdefault(key, []).append({'batch': batch, 'role': 'trigger' if batches[key] == batch else 'history',
                                                   'physical_ledger_id': identity})
        paths = list((folder / arm).glob('B[0-8].json'))
        latest = max(paths, key=lambda p: int(p.stem[1:]))
        for skill in Library.load(latest).skills.values():
            for origin in skill.source_provenance:
                support.setdefault(origin['source_id'], set()).add(skill.id)
        rows = []
        for key in batches:
            row = initial.get(key)
            rows.append({'source': key, 'dataset': datasets[key], 'fixed_batch': batches[key],
                'first_attempt_completed': row is not None,
                'native_first_attempt_grade': row['native_grade'] if row else None,
                'native_core_correct_views': row['native_core_correct'] if row else None,
                'native_fallback_views': row['native_fallback_views'] if row else None,
                'direct_teacher_contexts': direct.get(key, []),
                'declared_current_skill_citations': sorted(support.get(key, set()))})
        result[arm] = {'first_attempt_parents': len(initial), 'fixed_TRAIN_parent_count': len(batches),
            'unique_direct_teacher_parents': len(direct),
            'direct_teacher_parents_by_dataset': dict(Counter(datasets[k] for k in direct)),
            'current_library_batch': int(latest.stem[1:]), 'actual_teacher_calls': teacher_calls, 'source_rows': rows}
    return {'arms': result,
        'interpretation': 'Every completed batch parent supplies a grade to the fixed trigger selection. Only the recorded cohort is directly supplied as full source/feedback to its teacher; these are distinct coverage measures. Current-skill citations are declarations, not proof of independent semantic learning or successful reuse.',
        'new_acceptance_threshold_added': False, 'source_or_cohort_policy_changed': False}


def main(formal=False):
    root = Path(__file__).resolve().parents[2]
    profile, arms = PROFILE, PILOT_ARMS
    if formal:
        from experiments.legal_skill_evolution_formal import PROFILE as FORMAL_PROFILE, ARMS
        profile, arms = FORMAL_PROFILE, tuple(a for a in ARMS if a != 'NoSkill')
    folder = root / load_json(profile)['artifacts']
    rows, accepted_widths = [], []
    proposal_counts, compiled_counts, accepted_counts = Counter(), Counter(), Counter()
    transfers, existing_joint_candidates = [], []
    for arm in arms:
        for path in sorted((folder / arm).glob('update_B*.json')):
            receipt = load_json(path)
            if receipt['selected_mask'] is not None:accepted_widths.append(receipt['selected_mask'].bit_count())
            library = Library.load(folder / arm / ('B' + str(receipt['batch']) + '.json'))
            skills = []
            for skill in library.skills.values():
                skills.append({'id': skill.id, 'version': skill.version, 'hash': skill.hash,
                    'origin_parents': sorted({o['source_id'] for o in skill.source_provenance}),
                    'declared_read_input_count': sum(p['mode'] == 'read' for p in skill.inputs.values()),
                    'current_source_premise_read_count': sum(p['mode'] == 'read' for p in skill.premises.values()),
                    'fixed_source_premise_count': sum(p['mode'] == 'constant' for p in skill.premises.values()),
                    'declared_coupled_blocks': coupled_blocks(skill),
                    'semantic_records': list(skill.semantic_records),
                    'note': 'Input-vs-premise declarations are teacher proposals, not independently verified semantic roles.'})
            lift_revisions = []
            teacher = load_json(folder / arm / ('teacher_B' + str(receipt['batch']) + '.json'))
            for block in teacher['value']['blocks']:
                proposal_counts.update(r['operation'] for r in block['revisions'])
            candidates = sorted((folder / arm / ('B' + str(receipt['batch']) + '_candidates')).glob('*.json'))
            for candidate_path in candidates:
                candidate = load_json(candidate_path)
                compiled_counts.update(r['operation'] for r in candidate.get('revisions', []))
                existing = [r for r in candidate.get('revisions', []) if r['old_hash'] is not None]
                if len(existing) >= 2:
                    existing_joint_candidates.append({'arm': arm, 'batch': receipt['batch'],
                        'candidate': int(candidate_path.stem), 'existing_skill_ids': [r['skill_id'] for r in existing],
                        'table_complete': candidate.get('table', {}).get('complete', False),
                        'classification': candidate.get('table', {}).get('classification'),
                        'selected_mask': candidate.get('selected_mask'),
                        'finally_accepted': receipt['selected_candidate'] == int(candidate_path.stem)})
                if candidate.get('pattern_id'):
                    transfers.append({'arm': arm, 'batch': receipt['batch'], 'pattern_id': candidate['pattern_id'],
                        'candidate': int(candidate_path.stem), 'verified_context': candidate['verified_context'],
                        'table_complete': candidate.get('table', {}).get('complete', False),
                        'classification': candidate.get('transplant_classification'),
                        'finally_accepted': receipt['selected_candidate'] == int(candidate_path.stem)})
            if receipt['selected_candidate'] is not None:
                if candidates:
                    candidate = load_json(next(p for p in candidates if int(p.stem) == receipt['selected_candidate']))
                    accepted = [r for i, r in enumerate(candidate['revisions']) if receipt['selected_mask'] & (1 << i)]
                    accepted_counts.update(r['operation'] for r in accepted)
                    lift_revisions = [r['skill_id'] for r in accepted if r.get('operation') == 'lift']
            rows.append({'arm': arm, 'batch': receipt['batch'], 'accepted_skill_count': len(library.skills),
                'skills': skills, 'accepted_dedicated_lift_revisions_this_update': lift_revisions,
                'learned_revision_pattern_count': len(library.revision_patterns),
                'learned_pattern_ids_this_update': receipt['learned_pattern_ids'],
                'initial_dependency_creation_is_not_joint_revision_learning': True})
    result = {'captured_utc': datetime.now(timezone.utc).isoformat(), 'new_model_calls': 0,
        'goal_complete': False, 'evidence_scope': ('settled fixed formal TRAIN updates; DEV not supplied to teachers; no TEST' if formal
                                                 else 'settled pilot updates only; not formal DEV/TEST'),
        'teacher_proposed_operations': dict(proposal_counts), 'compiled_candidate_operations': dict(compiled_counts),
        'accepted_operations': dict(accepted_counts), 'candidates_changing_multiple_existing_skills': existing_joint_candidates,
        'actual_pattern_transplant_candidates': transfers,
        'fixed_table_diagnostics': {
            'scope': 'Existing candidate tables and common production code only; no new generation, source execution or constructed mechanism experiment.',
            'common_joint_selector': 'legal_skill_guard.skill_evolution.revisions.VersionTable.choose',
            'common_selector_sha256': hashlib.sha256((root / 'legal_skill_guard/skill_evolution/revisions.py').read_bytes()).hexdigest(),
            'same_candidate_same_table_generic_joint_selection': 'identical_by_shared_implementation; not a method advantage',
            'accepted_update_widths': accepted_widths,
            'accepted_updates_requiring_multiple_revisions': sum(n > 1 for n in accepted_widths),
            'pattern_generated_candidates': len(transfers),
            'no_memory_fixed_queue': ('same_observed_queue_because_no_pattern_candidates_exist' if not transfers
                                      else 'requires_separate_fixed_queue_comparison'),
            'no_memory_is_not_an_independently_regenerated_counterfactual': True,
            'coupled_Lift_vs_single_port': ('no_actual_Lift_revision_available' if not accepted_counts.get('lift')
                                          else 'inspect_existing_Lift_tables_and_binding_traces'),
            'additional_learned_runtime_skill_mask': 'absent; all arms share lexical/type retrieval; frozen foreign-skill masks are a separate registered transfer contrast'},
        'library_inventory': rows,
        'dedicated_mechanisms_require_actual_events_and_other_parent_validation': True}
    if formal:result['source_level_learning_coverage'] = source_coverage(root, folder, arms)
    target = Path(__file__).with_name('formal_mechanism_inventory.json' if formal else 'learned_mechanism_inventory.json')
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'settled_updates': len(rows), 'latest_by_arm': {
        arm: {k: next(r for r in reversed(rows) if r['arm'] == arm)[k]
              for k in ('batch', 'accepted_skill_count', 'learned_revision_pattern_count')}
        for arm in arms if any(r['arm'] == arm for r in rows)}}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--formal', action='store_true')
    main(parser.parse_args().formal)
