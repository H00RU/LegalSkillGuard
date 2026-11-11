"""TRAIN-only replay of real acquisition records; performs no model requests."""
from collections import Counter, defaultdict
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from legal_skill_guard.skill_evolution.objects import Library, digest
from legal_skill_guard.skill_evolution.teacher import compile_block
from legal_skill_guard.skill_evolution.lift_proposals import schedule_lift
from legal_skill_guard.skill_evolution.native import public_strings


def audit(root):
    prepared = root / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'
    records = {r['key']: r for r in json.loads(prepared.read_text())}
    formal = root / 'artifacts/legal_skill_evolution_20261111/formal_v5'
    manifest = json.loads((root / 'reports/legal_skill_evolution_plan_20261111/candidate_source_manifest.json').read_text())
    batches = [[r['source_key'] for r in b['sources']] for b in manifest['source_sequence']]
    rows, replay, errors, prior_recoveries = [], [], [], []
    for arm in ('FreeEvolution', 'LiftOnly', 'CoRevOnly', 'Full', 'Lift+GenericJoint', 'AllPorts+CoRev'):
        for batch in range(1, 9):
            folder = formal / arm
            old = Library.load(folder / f'B{batch-1}.json')
            context = json.loads((folder / f'update_context_B{batch}.json').read_text())
            update = json.loads((folder / f'update_B{batch}.json').read_text())
            initial = json.loads((folder / f'initial_B{batch}.json').read_text())
            order = sum(batches[:batch], [])
            current = {r['source']: r for r in initial['results']}
            trigger = sorted(current, key=lambda k: (current[k]['selection_grade'] is None,
                current[k]['selection_grade'] if current[k]['selection_grade'] is not None else 0,
                order.index(k)))[:3]
            if context['old_library_hash'] != old.hash:raise ValueError('Old library/context differs')
            plan = schedule_lift(old, [context['current'][k] for k in trigger], arm)
            if plan:
                target = records[plan['trigger_source']]
                strings = public_strings([v['public'] for v in target['views']])
                plan['old_literal_quote_still_present'] = {n: any(
                    old.skills[plan['skill_id']].premises[n]['origin']['quote'] in s for s in strings)
                    for n in plan['premises']}
            rows.append({'arm': arm, 'batch': batch, 'old_library_hash': old.hash,
                         'scheduled_lift': plan})
            response = json.loads((folder / f'teacher_B{batch}.json').read_text())
            for index, block in enumerate(response['value']['blocks']):
                saved = json.loads((folder / f'B{batch}_candidates/{index}.json').read_text())
                if saved.get('raw_block') != block:
                    raise ValueError('Expected real raw-block candidate; check queue index')
                try:
                    revisions = compile_block(block, old, {k: records[k] for k in order}, arm)
                except Exception as error:
                    error_text = type(error).__name__ + ': ' + str(error)
                    expected = saved.get('error') == error_text
                    errors.append({'arm': arm, 'batch': batch, 'candidate': index,
                                   'error': error_text, 'matches_original_failure': expected})
                    if not expected:raise
                else:
                    if 'revisions' not in saved:
                        prior_recoveries.append({'arm': arm, 'batch': batch, 'candidate': index,
                            'original_error_preserved': saved['error'],
                            'current_compiler_result': [r['new_hash'] for r in revisions],
                            'admitted_or_reexecuted': False,
                            'note': 'The compile_block function was unchanged by this repair. Earlier grounded-quote fixes were already present in the repair base.'})
                        continue
                    same = digest(revisions) == digest(saved['revisions'])
                    replay.append({'arm': arm, 'batch': batch, 'candidate': index,
                                   'revision_hashes': [r['new_hash'] for r in revisions],
                                   'unchanged': same})
                    if not same:raise ValueError('An existing compiled proposal changed')
    law_blocks = defaultdict(Counter)
    for record in records.values():
        public = record['views'][0]['public']
        law = public.get('source_text')
        if 'original_input' in public:
            text = public['original_input']
            if 'Statutes:' not in text or 'Solved Reasoning Steps:' not in text:
                raise ValueError('Unexpected native OE source headings')
            law = text.split('Statutes:', 1)[1].split('Solved Reasoning Steps:', 1)[0]
        if law is not None:law_blocks[record['dataset']][hashlib.sha256(law.encode()).hexdigest()] += 1
    finals = {}
    for arm in ('FreeEvolution', 'LiftOnly', 'CoRevOnly', 'Full', 'Lift+GenericJoint', 'AllPorts+CoRev'):
        library = Library.load(formal / arm / 'B8.json')
        finals[arm] = {'skill_count': len(library.skills),
            'dependency_ports': [{'skill_id': s.id, 'port': n, 'producer': p['skill_id']}
                for s in library.skills.values() for n, p in s.inputs.items() if p['mode'] == 'skill'],
            'patterns': len(library.revision_patterns)}
    return {'schema': 'TRAIN-only-activation-repair-20261112', 'new_model_calls': 0,
        'test_outputs_or_labels_read': False, 'goal_complete': False,
        'real_teacher_contexts': rows, 'unchanged_compiled_candidates': replay,
        'preserved_original_failures': errors,
        'preexisting_offline_recoveries_not_reexecuted': prior_recoveries,
        'law_text_blocks': {d: {'sources': sum(c.values()), 'distinct_blocks': len(c),
            'block_hash_counts': dict(c)} for d, c in law_blocks.items()}, 'final_libraries': finals,
        'interpretation': {
            'lift_scheduler': 'This schedules evaluation, not admission or legal usefulness.',
            'same_law_text': 'Repeated law reduces value-rebinding opportunities; this alone does not prove identical scope or legal applicability.',
            'corevision': 'No actual producer/consumer dependency means no genuine CoRev training event; do not invent a split.',
            'native_OE_given_regime': 'Solved Reasoning Steps supplies the regime. Reading it is permitted literal extraction, not evidence of outsourced choice-of-law reasoning.'}}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser();parser.add_argument('--original-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True);args = parser.parse_args()
    result = audit(args.original_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'contexts': len(result['real_teacher_contexts']),
        'unchanged_compiled': len(result['unchanged_compiled_candidates']),
        'preserved_failures': len(result['preserved_original_failures']),
        'actual_train_lift_plans': [r for r in result['real_teacher_contexts'] if r['scheduled_lift']]}))
