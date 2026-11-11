"""Finite TRAIN-only repair check; never resumes or replaces formal training.

One actual scheduled Lift and one independent acquisition per Full/FreeEvolution.
All requests use the existing ledger and fixed models. This is a diagnostic on
already-seen TRAIN, not independent generalization or a successful contribution.
"""
from datetime import datetime, timezone
from pathlib import Path
from copy import deepcopy
import argparse
import hashlib
import json
import sqlite3
from statistics import mean

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor, FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import Library, apply_revision_package, digest
from legal_skill_guard.skill_evolution.runtime import FrozenReads, SkillRuntime
from legal_skill_guard.skill_evolution.study import Study
from legal_skill_guard.skill_evolution.teacher import propose
from legal_skill_guard.skill_evolution.lift_proposals import compile_scheduled_lift
from legal_skill_guard.skill_evolution.revisions import VersionTable


RUN = 'legal_skill_evolution_activation_repair_20261112'
SARA_PAIRS = ['SARA_v2_Binary:cc82ab0fe40ca06245a9fdd00273c97ae8d8c2af9783b5618826de0125d41397',
              'SARA_v2_Binary:a51930fd174465a9bc8bd24887336e753d1f76990c346645a1ae5cd8c074536d']


def read(path):return json.loads(path.read_text())


def prepare(root, original):
    folder = root / 'artifacts/legal_skill_evolution_activation_repair_20261112'
    profile = read(original / 'configs/legal_skill_evolution_formal_v5_20261111.json')
    manifest = read(original / 'reports/legal_skill_evolution_plan_20261111/candidate_source_manifest.json')
    ids = {p: [r['key'] for rows in manifest['datasets'].values() for r in rows[p]] for p in ('train', 'dev', 'test')}
    records = {r['key']: r for r in read(original / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
    audit = read(root / 'reports/legal_skill_evolution_run_20261111/activation_repair_TRAIN_replay.json')
    plan = next(r['scheduled_lift'] for r in audit['real_teacher_contexts'] if r['arm'] == 'Full' and r['batch'] == 5)
    old = Library.load(original / 'artifacts/legal_skill_evolution_20261111/formal_v5/Full/B4.json')
    history = old.skills[plan['skill_id']].premises[plan['premises'][0]]['origin']['source_id']
    if history == plan['trigger_source']:raise ValueError('Lift requires a distinct actual history source')
    code = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((root / 'legal_skill_guard/skill_evolution').glob('*.py'))}
    for relative in ('experiments/legal_skill_evolution_activation_probe.py',
                     'reports/legal_skill_evolution_run_20261111/activation_repair_TRAIN_replay.json'):
        code[relative] = hashlib.sha256((root / relative).read_bytes()).hexdigest()
    protocol = {'run_id': RUN, 'goal_complete': False, 'new_full_training': False,
        'test_labels_or_results': False, 'already_seen_TRAIN_diagnostic': True,
        'lift': {'old_library_hash': old.hash, 'plan': plan,
                 'trigger': plan['trigger_source'], 'history': history,
                 'retrieval': [plan['skill_id']], 'teacher_blocks': 0},
        'independent_acquisition': {'arms': ['Full', 'FreeEvolution'], 'sources': SARA_PAIRS,
            'start': 'independent empty libraries; no imported learned helpers',
            'question': 'Does the common acquisition repair produce real source-grounded rule dependencies, or do strong ordinary programs suffice?',
            'candidate_blocks': 3, 'same_native_feedback_and_models': True,
            'not_evidence_of_old_skill_corevision': True},
        'teacher_jobs': 3, 'automatic_retries': 0, 'code': code,
        'executor_profile_hash': digest(profile['executor']), 'teacher_profile_hash': digest(profile['teacher']),
        'decisions': ['No repeated prompt tuning on failure.',
            'A rejected Lift is preserved; no false fallback or relaxed acceptance.',
            'No real dependency means CoRev remains unvalidated; do not manufacture it.',
            'An acquired dependency alone is not evidence of necessary joint revision or transfer.']}
    if not set(SARA_PAIRS + [history, plan['trigger_source']]) <= set(ids['train']):
        raise ValueError('All diagnostic sources must be original fixed TRAIN')
    immutable_json(folder / 'protocol.json', protocol)
    return folder, profile, ids, records, old, protocol


def execute(root, original):
    folder, profile, ids, records, old, protocol = prepare(root, original)
    for path, expected in protocol['code'].items():
        if hashlib.sha256((root / path).read_bytes()).hexdigest() != expected:
            raise ValueError('Bound diagnostic code changed')
    done = folder / 'completed.json'
    if done.exists():return read(done)
    ledger_path = original / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'
    with sqlite3.connect('file:' + str(ledger_path) + '?mode=ro', uri=True) as db:
        if db.execute("select 1 from calls where status='reserved'").fetchone():
            raise ValueError('Drain the existing physical request before this diagnostic')
    budget = EvolutionLedger(ledger_path, run_id=RUN, sources=ids, binding=digest(protocol))
    study = object.__new__(Study)
    study.root, study.folder, study.stage = root, folder, 'activation_diagnostic'
    study.profile = {**deepcopy(profile), 'prior_logical_replay_executions': {}}
    study.records = records
    study.grading = read(original / 'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')
    study.ledger = budget
    study.executor = FrozenExecutor(budget, folder, profile['executor'])
    study.executor.exact_replay_roots = [original / profile['artifacts']]
    study.reads = FrozenReads(study.executor);study.runtime = SkillRuntime(study.reads)
    study.teacher = FrozenTeacher(budget, folder, profile['teacher'])
    study.source_ids = ids
    lift_result_path = folder / 'lift_result.json'
    if not lift_result_path.exists():
        selected = protocol['lift'];cohort = [selected['trigger'], selected['history']]
        retrieval = {k: {v['id']: selected['retrieval'] for v in records[k]['views']} for k in cohort}
        baseline = {k: study.parent(k, old, retrieval_sets=retrieval[k], purpose='skill_replay') for k in cohort}
        path = folder / 'lift_teacher.json'
        response = read(path) if path.exists() else propose(study.teacher, arm='Full', batch=5,
            library=Library(skills={selected['plan']['skill_id']: old.skills[selected['plan']['skill_id']]}),
            source_records=[records[k] for k in cohort], feedback=study.feedback(cohort, baseline),
            learned_patterns=[], trigger=cohort[:1], history=cohort[1:], max_blocks=0,
            planned_lift=selected['plan'])
        immutable_json(path, response)
        revisions = compile_scheduled_lift(selected['plan'], response['value']['lift_reader'], old)
        new = apply_revision_package(old, revisions, old.hash)
        table = VersionTable(tuple(r['new_hash'] for r in revisions), tuple(cohort[:1]), tuple(cohort[1:]))
        tokens = {}
        for mask, library in ((0, old), (1, new)):
            tokens[mask] = 0
            for key in cohort:
                result = baseline[key] if mask == 0 else study.parent(key, library,
                    retrieval_sets=retrieval[key], purpose='skill_replay')
                table.observe(mask, key, result['selection_grade'], result)
                tokens[mask] += sum(e.get('usage', {}).get('total_tokens', 0)
                    for v in result['views'] for e in v['execution']['events'] if e.get('kind') == 'READ_LOCAL')
        immutable_json(lift_result_path, {'revisions': revisions, 'table': table.export(),
            'selected_mask': table.choose({m: tokens[m] - tokens[0] for m in tokens}),
            'read_tokens': tokens, 'acquired_reader_not_proof_of_contribution': True})
    study.arms = ('Full', 'FreeEvolution');study.batches = [SARA_PAIRS];study.order = SARA_PAIRS
    study.initialize()
    for arm in study.arms:study.initial_batch(arm, 1)
    for arm in study.arms:study.update(arm, 1)
    acquisitions = {}
    for arm in study.arms:
        library = Library.load(study.library_path(arm, 1))
        acquisitions[arm] = {'library_hash': library.hash, 'skills': len(library.skills),
            'dependency_ports': [{'consumer': s.id, 'input': n, 'producer': p['skill_id'], 'field': p['field']}
                for s in library.skills.values() for n, p in s.inputs.items() if p['mode'] == 'skill'],
            'pattern_count': len(library.revision_patterns), 'update': read(folder / arm / 'update_B1.json')}
    with budget.transaction() as db:
        calls = [dict(zip(('id', 'role', 'status', 'result'), r)) for r in db.execute(
            'select id,role,status,result from calls where id like ? order by reserved_at', (RUN + ':%',))]
    result = {'completed_utc': datetime.now(timezone.utc).isoformat(), 'goal_complete': False,
        'lift': read(lift_result_path), 'independent_acquisition': acquisitions,
        'physical_requests': [{'id': r['id'], 'role': r['role'], 'status': r['status'],
            'usage': json.loads(r['result']).get('usage'),
            'elapsed_seconds': json.loads(r['result']).get('elapsed_seconds')} for r in calls],
        'count_by_role': {role: sum(r['role'] == role for r in calls) for role in ('executor', 'teacher')},
        'test_used': False, 'formal_study_replaced': False}
    immutable_json(done, result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser();parser.add_argument('action', choices=['prepare', 'run'])
    parser.add_argument('--original-root', type=Path, required=True);args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.action == 'prepare':
        folder, _, _, _, _, protocol = prepare(root, args.original_root)
        print(json.dumps({'protocol': str(folder / 'protocol.json'), 'teacher_jobs': protocol['teacher_jobs'],
                          'test_used': False}))
    else:
        result = execute(root, args.original_root)
        print(json.dumps({'completed': True, 'counts': result['count_by_role'], 'goal_complete': False}))
