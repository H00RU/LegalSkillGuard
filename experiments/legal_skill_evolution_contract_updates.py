"""Two fixed original-TRAIN updates and frozen reuse from one real legal graph.

The shared seed isolates updating from independent acquisition. Its two actual
acquisition costs and the separate Free acquisition remain in the same ledger.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import fcntl
import hashlib
import json
from pathlib import Path

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor, FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import Library, digest
from legal_skill_guard.skill_evolution.proposal_batch import prefetch_teachers
from legal_skill_guard.skill_evolution.runtime import FrozenReads, SkillRuntime
from legal_skill_guard.skill_evolution.study import Study
from experiments.legal_skill_evolution_role_TRAIN import physical_snapshot, status


RUN = 'legal_skill_evolution_contract_updates_20261112'
ARMS = ('Full', 'FreeEvolution', 'AllPorts+CoRev', 'Lift+GenericJoint')


def read(path):return json.loads(path.read_text())


def prepare(root, original):
    acquisition = root / 'artifacts/legal_skill_evolution_contract_acquisition_20261112'
    acquired = read(acquisition / 'completed.json')
    source_protocol = read(acquisition / 'protocol.json')
    seed_path = acquisition / 'Full/B1.json'
    seed = Library.load(seed_path)
    if seed.hash != acquired['updates']['Full']['new_library_hash']:
        raise ValueError('Actual acquired graph changed')
    profile = read(original / 'configs/legal_skill_evolution_formal_v5_20261111.json')
    public_path = original / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'
    all_records = {r['key']: r for r in read(public_path)}
    keys = source_protocol['source_order_fixed_before_new_generation']
    if len(keys) != 4 or len({all_records[k]['parent_id'] for k in keys}) != 4:
        raise ValueError('Keep the four previously fixed distinct original TRAIN parents')
    contract = {
        'learning_object': 'Update the already-acquired source-grounded exception-applicability judgment and its legal consequence when the current contract differs.',
        'legal_modules': 'The existing graph separates an actual recipient-disclosure permission from the effect of the general nondisclosure obligation. Preserve this useful boundary where valid, but do not force two changes, fabricate defects, or split one record into extra skills.',
        'source_parameters': 'Explicitly compare the old source-specific recipient classes, safeguards, permission scope and prohibition/exception relationship to the supplied current contract. Preserve qualifications and reference scope. An old Paragraph 4 reference is not evidence for a different document.',
        'reads': 'READ may acquire supported source-rule parameters. The learned procedure must compute the exception and native consequence; do not delegate the complete native label or the full legal exception decision to READ. Missing rules are not defaults or invented conditions.',
        'scope': 'Focus disclosure tasks nda-5 and nda-7; declare public_tasks. Other native tasks retain ordinary fallback and remain in the parent score. current_question is a literal argument, not a model read.',
        'independence': 'All four conditions start with the exact same real Full seed and receive the same source/feedback. This comparison isolates update mechanisms, not independent end-to-end acquisition. FreeEvolution may use strong joint program and read edits; AllPorts may jointly read all relevant source premises without the three-premise restriction.',
        'admission': 'Keep strict trigger parent improvement and every historical parent nondecreasing. Single edits are sufficient when measured sufficient; do not manufacture joint necessity. A new graph is not CoRev.',
        'unknowns': 'Do not infer unstated consent, waive conditions, substitute an absent provision or hardcode a new parent answer. No teacher-produced field labels are independent gold.'}
    paths = list((root / 'legal_skill_guard/skill_evolution').glob('*.py'))
    paths += list((root / 'tests').glob('test_skill_evolution_*.py'))
    paths += [Path(__file__).resolve(), root / 'experiments/legal_skill_evolution_role_TRAIN.py']
    protocol = {'run_id': RUN, 'same_goal': True, 'goal_complete': False,
        'previously_fixed_source_order': keys, 'seed_parent': keys[0],
        'learning_batches': [[keys[0]], [keys[1]], [keys[2]]],
        'execute_update_batches': [2, 3], 'reuse_parents': [keys[3]], 'arms': list(ARMS),
        'start': 'Shared actual acquired Full legal graph; independent seed acquisitions separately preserved and costed.',
        'seed_library_hash': seed.hash,
        'seed_file_sha256': hashlib.sha256(seed_path.read_bytes()).hexdigest(),
        'seed_acquisition_protocol_hash': digest(source_protocol),
        'already_seen_original_TRAIN_not_blind': True,
        'source_selection': source_protocol['source_selection'],
        'teacher_workload': 'Four arms at each of two fixed update parents, no unchanged retry. Each keeps the existing three-block/three-revision/eight-parent allowance.',
        'reuse': 'After both updates freeze, execute one already-fixed other TRAIN parent once per arm, without teacher or further update; native annotations only grade it.',
        'mechanism_credit': {'Lift': 'Actual current-source premise reading and binding with unchanged procedure; singleton success alone does not prove a coupling advantage.',
            'CoRev': 'Two pre-existing legal responsibilities, actual USE, compatible-interface complete version table establishing necessary joint revision, and later real pattern use. Creation and interface breakage do not count.',
            'controls': 'Keep independent original acquisitions, shared-rule update comparison, AllPorts and generic multi-edit memory separate; report absorption and failure.'},
        'acquisition_contract': contract,
        'offline_evidence': 'Actual generated graph, source support and USE inspected; missing directly-used singleton candidates restored without changing P, old skills or correctness checks.',
        'automatic_retries': 0, 'no_new_sources_DEV_TEST_full_training_or_paper': True,
        'executor_profile': profile['executor'], 'teacher_profile': profile['teacher'],
        'public_TRAIN_sha256': hashlib.sha256(public_path.read_bytes()).hexdigest(),
        'code_sha256': {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}}
    folder = root / 'artifacts' / RUN
    immutable_json(folder / 'protocol.json', protocol)
    before_path = folder / 'ledger_before.json'
    if not before_path.exists():
        before = physical_snapshot(original / 'artifacts/rr_v2_preflight/research_ledger.sqlite3')
        if any(v.get('reserved', 0) for v in before.values()):raise ValueError('Reconcile pending requests first')
        immutable_json(before_path, before)
    return folder, profile, all_records, seed, protocol


def run(root, original):
    folder, profile, records, seed, protocol = prepare(root, original)
    with (folder / 'controller.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for rel, expected in protocol['code_sha256'].items():
            if hashlib.sha256((root / rel).read_bytes()).hexdigest() != expected:
                raise ValueError('Frozen update code changed: ' + rel)
        if (folder / 'completed.json').exists():return read(folder / 'completed.json')
        ledger_path = original / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'
        keys = protocol['previously_fixed_source_order']
        study = object.__new__(Study)
        study.root, study.folder, study.stage = root, folder, 'contract_update'
        study.profile = {**deepcopy(profile), 'prior_logical_replay_executions': {},
                         'acquisition_contract': protocol['acquisition_contract']}
        study.records = {k: records[k] for k in keys}
        grading = read(original / 'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')
        study.grading = {k: grading[k] for k in keys}
        study.source_ids = {'train': keys, 'dev': [], 'test': []}
        study.batches, study.arms = protocol['learning_batches'], ARMS
        study.order = sum(study.batches, [])
        study.ledger = EvolutionLedger(ledger_path, run_id=RUN, sources=study.source_ids,
            binding=digest(protocol), teacher_concurrency=2)
        study.executor = FrozenExecutor(study.ledger, folder, profile['executor'])
        study.executor.exact_replay_roots = [original / profile['artifacts']]
        for rel in profile.get('exact_replay_profiles', []):
            prior = read(original / rel)
            if digest(prior['executor']) != digest(profile['executor']):raise ValueError('Executor profile differs')
            study.executor.exact_replay_roots.append(original / prior['artifacts'])
        study.executor.exact_replay_roots.append(root / 'artifacts/legal_skill_evolution_contract_acquisition_20261112')
        study.reads = FrozenReads(study.executor);study.runtime = SkillRuntime(study.reads)
        study.teacher = FrozenTeacher(study.ledger, folder, profile['teacher'])
        for arm in ARMS:
            p = study.library_path(arm, 1)
            if p.exists():
                if Library.load(p).hash != seed.hash:raise ValueError('Shared seed differs')
            else:deepcopy(seed).save(p)
        try:
            for batch in protocol['execute_update_batches']:
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
                lib = Library.load(study.library_path(arm, 3))
                reuse[arm] = [study.parent(k, lib) for k in protocol['reuse_parents']]
            no_skill = [study.parent(k, Library()) for k in keys]
            result = {'completed_utc': datetime.now(timezone.utc).isoformat(),
                'goal_complete': False, 'protocol_hash': digest(protocol),
                'updates': {a: [read(folder / a / f'update_B{b}.json') for b in (2, 3)] for a in ARMS},
                'reuse_results': reuse, 'NoSkill_original_TRAIN_results': no_skill,
                'ledger_before': read(folder / 'ledger_before.json'),
                'ledger_after': physical_snapshot(ledger_path),
                'semantic_and_mechanism_review_pending': True,
                'no_new_DEV_TEST_full_training_or_paper': True}
            immutable_json(folder / 'completed.json', result)
            status(folder, phase='finite_updates_completed_review_pending', ledger=result['ledger_after'])
            return result
        except BaseException as e:
            status(folder, phase='preserved_after_error', error=type(e).__name__ + ': ' + str(e),
                   ledger=physical_snapshot(ledger_path))
            raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['prepare', 'run'])
    parser.add_argument('--original-root', type=Path, required=True)
    args = parser.parse_args();root = Path(__file__).resolve().parents[1]
    if args.action == 'prepare':
        folder, _, _, _, protocol = prepare(root, args.original_root)
        print(json.dumps({'protocol': str(folder / 'protocol.json'), 'protocol_hash': digest(protocol),
            'teacher_tasks': 8, 'original_TRAIN_parents': 4, 'new_model_calls': 0}))
    else:
        result = run(root, args.original_root)
        print(json.dumps({'completed': True, 'goal_complete': False, 'ledger': result['ledger_after']}))
