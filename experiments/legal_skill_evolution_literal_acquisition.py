"""Independent acquisition on one fixed TRAIN source after an actual read failure.

Tests the shared learning object, not independent Lift/CoRev effects. No full
training, new labels/sources, DEV/TEST or unchanged failed request is launched.
"""
from copy import deepcopy
from datetime import datetime, timezone
import fcntl
import hashlib
import json
from pathlib import Path
import sqlite3

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor, FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.literal_facts import literal_bindings
from legal_skill_guard.skill_evolution.objects import Library, digest
from legal_skill_guard.skill_evolution.proposal_batch import prefetch_teachers
from legal_skill_guard.skill_evolution.runtime import FrozenReads, SkillRuntime
from legal_skill_guard.skill_evolution.study import Study


def read(path):return json.loads(path.read_text())


def main():
    root = Path(__file__).resolve().parents[1]
    original = Path('/home/yndx/hhy/legal-skill-redesign-20261109')
    run_id = 'legal_skill_evolution_literal_acquisition_20261112'
    folder = root / 'artifacts' / run_id
    if (folder / 'completed.json').exists():return read(folder / 'completed.json')
    previous = read(root / 'artifacts/legal_skill_evolution_case_support_check_20261112/protocol.json')
    key = previous['parents'][0]
    profile = read(original / 'configs/legal_skill_evolution_formal_v5_20261111.json')
    prepared = original / 'artifacts/legal_skill_evolution_20261111/prepared/train'
    source = next(s for s in read(prepared / 'public.json') if s['key'] == key)
    code = list((root / 'legal_skill_guard/skill_evolution').glob('*.py')) + [Path(__file__).resolve()]
    protocol = {'run_id': run_id, 'original_TRAIN_parent': key,
        'purpose': 'Can independently acquired legal procedures consume source-oriented literal facts instead of asking the executor to invert a relative relationship?',
        'scope': 'Shared acquisition foundation only; not method benefit, transfer or two-contribution proof.',
        'arms': ['Full', 'FreeEvolution'], 'start': 'Independent empty libraries, same original source and native feedback.',
        'change_from_failed_requests': 'Literal positive has_relative(owner, word, relative) records plus caller-bound root arguments, with quoted evidence; legal eligibility remains learned by the teacher.',
        'literal_context': literal_bindings(source['views'][0]),
        'teacher_tasks': 2, 'automatic_retries': 0, 'offline_regressions_passed': 78,
        'candidate_protocol': 'Unchanged at most three blocks/three skills, complete mixed tables and strict trigger gain; no new admission gate.',
        'no_DEV_TEST_or_full_training': True,
        'executor_profile': profile['executor'], 'teacher_profile': profile['teacher'],
        'code_sha256': {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in code}}
    immutable_json(folder / 'protocol.json', protocol)
    with (folder / 'controller.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        ledger_path = original / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'
        with sqlite3.connect('file:' + str(ledger_path) + '?mode=ro', uri=True) as db:
            if db.execute("select 1 from calls where status='reserved'").fetchone():
                raise ValueError('Reconcile existing in-flight requests before acquisition')
        study = object.__new__(Study)
        study.root, study.folder, study.stage = root, folder, 'literal_acquisition'
        study.profile = {**deepcopy(profile), 'prior_logical_replay_executions': {}}
        study.records, study.grading = {key: source}, {key: read(prepared / 'grading.json')[key]}
        study.source_ids = {'train': [key], 'dev': [], 'test': []}
        study.arms, study.batches, study.order = tuple(protocol['arms']), [[key]], [key]
        study.ledger = EvolutionLedger(ledger_path, run_id=run_id, sources=study.source_ids,
                                      binding=digest(protocol), teacher_concurrency=2)
        study.executor = FrozenExecutor(study.ledger, folder, profile['executor'])
        study.executor.exact_replay_roots = [original / profile['artifacts']]
        for rel in profile.get('exact_replay_profiles', []):
            prior = read(original / rel)
            if digest(prior['executor']) != digest(profile['executor']):raise ValueError('Prior executor profile differs')
            study.executor.exact_replay_roots.append(original / prior['artifacts'])
        study.reads = FrozenReads(study.executor);study.runtime = SkillRuntime(study.reads)
        study.teacher = FrozenTeacher(study.ledger, folder, profile['teacher'])
        study.initialize()
        for arm in study.arms:study.initial_batch(arm, 1)
        prefetch_teachers(study, 1)
        updates = {arm: study.update(arm, 1) for arm in study.arms}
        with study.ledger.transaction() as db:
            rows = [dict(zip(('id', 'role', 'status', 'result'), row)) for row in db.execute(
                'select id,role,status,result from calls where id like ? order by reserved_at', (run_id + ':%',))]
        result = {'completed_utc': datetime.now(timezone.utc).isoformat(), 'goal_complete': False,
            'updates': updates, 'protocol_hash': digest(protocol), 'request_statuses': [
                {k: row[k] for k in ('id', 'role', 'status')} for row in rows],
            'count_by_role': {role: sum(row['role'] == role for row in rows) for role in ('executor', 'teacher')},
            'independent_method_effect_not_claimed': True}
        immutable_json(folder / 'completed.json', result)
        return result


if __name__ == '__main__':
    result = main()
    print(json.dumps(result))
