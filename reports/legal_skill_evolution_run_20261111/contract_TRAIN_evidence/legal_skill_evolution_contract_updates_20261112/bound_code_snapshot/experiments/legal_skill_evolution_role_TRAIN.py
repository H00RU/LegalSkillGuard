"""Finite authorized original-TRAIN acquisition/update diagnostic, not retraining."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sqlite3

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor, FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import Library, digest
from legal_skill_guard.skill_evolution.proposal_batch import prefetch_teachers
from legal_skill_guard.skill_evolution.runtime import FrozenReads, SkillRuntime
from legal_skill_guard.skill_evolution.study import Study


RUN = 'legal_skill_evolution_role_TRAIN_20261112'
ARMS = ('Full', 'FreeEvolution', 'AllPorts+CoRev', 'Lift+GenericJoint')
# Fixed from original TRAIN text and legal dependencies, before new generation.
PREFIXES = (('6939fedab07c', 'bb6b0bc1f7a0'),
            ('d9d6b23646a3', '3e22604a20ba'),
            ('ed3f34d32df6', 'd5e1138c0c20'))


def read(path):
    return json.loads(Path(path).read_text())


def physical_snapshot(path):
    with sqlite3.connect('file:' + str(path) + '?mode=ro', uri=True) as db:
        counts = {(r, s): n for r, s, n in db.execute('select role,status,count(*) from calls group by role,status')}
    return {role: {'total': sum(n for (r, _), n in counts.items() if r == role),
                   **{s: n for (r, s), n in counts.items() if r == role}}
            for role in ('executor', 'teacher')}


def prepare(root, original):
    profile = read(original / 'configs/legal_skill_evolution_formal_v5_20261111.json')
    public = original / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'
    records = {r['key']: r for r in read(public)}
    batches = []
    for prefixes in PREFIXES:
        batch = []
        for prefix in prefixes:
            found = [k for k in records if k.startswith('SARA_v2_Binary:' + prefix)]
            if len(found) != 1:
                raise ValueError('Original TRAIN source identity is not unique')
            batch.append(found[0])
        batches.append(batch)
    if len({records[k]['parent_id'] for b in batches for k in b}) != 6:
        raise ValueError('Diagnostic requires six distinct original parents')
    paths = list((root / 'legal_skill_guard/skill_evolution').glob('*.py'))
    paths += [root / 'experiments/legal_skill_evolution_role_TRAIN.py']
    paths += list((root / 'tests').glob('test_skill_evolution_*.py'))
    code = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}
    ledger = original / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'
    protocol = {'run_id': RUN, 'same_goal': True, 'goal_complete': False,
        'authorization': 'User resumed and authorized finite original-TRAIN learning-object/protocol adjustment; cumulative ledger and models retained.',
        'question': 'Can explicit role-bound acquisition learn reusable grounded employment/wage predicates and support subsequent legal-rule updates, rather than delegating a native answer to READ?',
        'legal_bottleneck': 'Separate payer/employer from employee and distinguish wages, statutory employment exclusions, and general versus agricultural employer tests under the supplied section 3306.',
        'arms': list(ARMS), 'start': 'Independent empty libraries; identical common role-binding foundation, source text and native TRAIN supervision. No imported skills.',
        'learning_batches': batches[:2], 'reuse_parents': batches[2],
        'all_six_are_original_TRAIN_not_blind': True, 'new_sources_or_seeds': False,
        'selection_basis': 'Original native text and actual statutory dependencies. No TEST failure or new scores used to select sources.',
        'eight_teacher_tasks': 'Four independent arms at two acquisition/update steps, existing three-block/three-revision/eight-parent limits unchanged. No unchanged retry.',
        'candidate_selection': 'Existing complete mixed-version tables: strict trigger improvement, every history parent nondecreasing; no relaxed acceptance.',
        'reuse_policy': 'After B2 freezes, two other original TRAIN parents execute once per arm with no teacher or update. Their annotations are used only for native grading.',
        'mechanism_credit': {'Lift': 'Actual measured premise rebinding with unchanged P; distinct parent application and comparison to AllPorts/ordinary acquisition required.',
            'CoRev': 'Revisions of already-installed distinct legal responsibilities, real USE, complete compatible-interface version table, joint necessity, and actual later pattern use. Creation, interface-break effects and rendering edges do not count.',
            'semantic_review': 'Inspect real argument/read/procedure/source trace. Format success, support-span selection, native coincidence and fallback alone are insufficient.'},
        'decision': 'Retain strong-control absorption and natural single-rule results. Diagnose a missing mechanism prerequisite from this finite pass; do not launch a full matrix or invent defects to trigger it.',
        'no_DEV_TEST_or_paper': True, 'automatic_retries': 0,
        'executor_profile': profile['executor'], 'teacher_profile': profile['teacher'],
        'code_sha256': code, 'public_TRAIN_sha256': hashlib.sha256(public.read_bytes()).hexdigest()}
    folder = root / 'artifacts' / RUN
    immutable_json(folder / 'protocol.json', protocol)
    baseline = folder / 'ledger_before.json'
    if not baseline.exists():
        snapshot = physical_snapshot(ledger)
        if any(v.get('reserved', 0) for v in snapshot.values()):
            raise ValueError('Reconcile in-flight physical requests before the diagnostic')
        immutable_json(baseline, snapshot)
    return folder, profile, records, protocol, ledger


def status(folder, **value):
    target = folder / 'status.json'
    temporary = folder / 'status.temporary.json'
    temporary.write_text(json.dumps({'utc': datetime.now(timezone.utc).isoformat(),
        'pid': os.getpid(), 'goal_complete': False, **value}, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(target)


def run(root, original):
    folder, profile, records, protocol, ledger_path = prepare(root, original)
    with (folder / 'controller.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for relative, expected in protocol['code_sha256'].items():
            if hashlib.sha256((root / relative).read_bytes()).hexdigest() != expected:
                raise ValueError('Frozen diagnostic code changed: ' + relative)
        if (folder / 'completed.json').exists():
            return read(folder / 'completed.json')
        keys = sum(protocol['learning_batches'], []) + protocol['reuse_parents']
        study = object.__new__(Study)
        study.root, study.folder, study.stage = root, folder, 'role_TRAIN_diagnostic'
        study.profile = {**deepcopy(profile), 'prior_logical_replay_executions': {}}
        study.records = {k: records[k] for k in keys}
        grading = read(original / 'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')
        study.grading = {k: grading[k] for k in keys}
        study.source_ids = {'train': keys, 'dev': [], 'test': []}
        study.ledger = EvolutionLedger(ledger_path, run_id=RUN, sources=study.source_ids,
            binding=digest(protocol), teacher_concurrency=2)
        study.executor = FrozenExecutor(study.ledger, folder, profile['executor'])
        roots = [original / profile['artifacts']]
        for relative in profile.get('exact_replay_profiles', []):
            prior = read(original / relative)
            if digest(prior['executor']) != digest(profile['executor']):
                raise ValueError('Prior executor profile changed')
            roots.append(original / prior['artifacts'])
        study.executor.exact_replay_roots = roots
        study.reads = FrozenReads(study.executor)
        study.runtime = SkillRuntime(study.reads)
        study.teacher = FrozenTeacher(study.ledger, folder, profile['teacher'])
        study.batches, study.arms = protocol['learning_batches'], ARMS
        study.order = sum(study.batches, [])
        study.initialize()
        try:
            for batch in (1, 2):
                for arm in ARMS:
                    status(folder, phase='initial', batch=batch, arm=arm)
                    study.initial_batch(arm, batch)
                status(folder, phase='teacher', batch=batch)
                prefetch_teachers(study, batch)
                for arm in ARMS:
                    status(folder, phase='candidate_validation', batch=batch, arm=arm)
                    study.update(arm, batch)
            reuse = {}
            for arm in ARMS:
                status(folder, phase='frozen_TRAIN_reuse', arm=arm)
                library = Library.load(study.library_path(arm, 2))
                reuse[arm] = [study.parent(k, library) for k in protocol['reuse_parents']]
            with study.ledger.transaction() as db:
                rows = db.execute('select id,role,status,result from calls where id like ? order by reserved_at', (RUN + ':%',)).fetchall()
            result = {'completed_utc': datetime.now(timezone.utc).isoformat(), 'goal_complete': False,
                'protocol_hash': digest(protocol), 'reuse_results': reuse,
                'updates': {arm: [read(folder / arm / f'update_B{b}.json') for b in (1, 2)] for arm in ARMS},
                'requests': [{'id': i, 'role': role, 'status': state, **{k: json.loads(raw or '{}').get(k)
                             for k in ('usage', 'elapsed_seconds', 'finish_reason')}} for i, role, state, raw in rows],
                'ledger_before': read(folder / 'ledger_before.json'),
                'ledger_after': physical_snapshot(ledger_path),
                'semantic_and_mechanism_review_pending': True, 'no_DEV_TEST_or_paper': True}
            immutable_json(folder / 'completed.json', result)
            status(folder, phase='finite_execution_completed_review_pending', ledger=result['ledger_after'])
            return result
        except BaseException as error:
            status(folder, phase='preserved_after_error', error=type(error).__name__ + ': ' + str(error),
                   ledger=physical_snapshot(ledger_path))
            raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['prepare', 'run'])
    parser.add_argument('--original-root', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.action == 'prepare':
        folder, _, _, protocol, _ = prepare(root, args.original_root)
        print(json.dumps({'protocol': str(folder / 'protocol.json'), 'protocol_hash': digest(protocol),
                          'TRAIN_parents': 6, 'teacher_tasks': 8, 'new_model_calls': 0}))
    else:
        result = run(root, args.original_root)
        print(json.dumps({'completed': True, 'goal_complete': False, 'ledger': result['ledger_after']}))
