"""One changed TRAIN update per method/control after the measured read failures."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
import argparse
import fcntl
import hashlib
import json
from pathlib import Path

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor, FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import Library, digest
from legal_skill_guard.skill_evolution.proposal_batch import prepare_context
from legal_skill_guard.skill_evolution.runtime import FrozenReads, SkillRuntime
from legal_skill_guard.skill_evolution.study import Study
from legal_skill_guard.skill_evolution.teacher import propose
from experiments.legal_skill_evolution_role_TRAIN import physical_snapshot, status

RUN = 'legal_skill_evolution_partial_contract_recovery_20261112'
ARMS = ('Full', 'Lift+GenericJoint')


def read(path):return json.loads(path.read_text())


def prepare(root, original):
    prior = root / 'artifacts/legal_skill_evolution_source_rule_check_20261112'
    structured = root / 'artifacts/legal_skill_evolution_structured_rule_check_20261112'
    if not (structured / 'completed.json').exists():raise ValueError('The two diagnostic READs must be terminal')
    keys = read(prior / 'protocol.json')['already_fixed_original_TRAIN_parents']
    seed_path = prior / 'FreeEvolution/B2.json'
    seed = Library.load(seed_path)
    profile = read(original / 'configs/legal_skill_evolution_formal_v5_20261111.json')
    public_path = original / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'
    records = {s['key']: s for s in read(public_path)}
    observed = read(prior / 'FreeEvolution/B3_candidates/0.json')
    flat_reads = {}
    for cell in observed['table']['mixed_version_table']:
        if cell['mask'] != 3:continue
        for view in cell['trace']['views']:
            for event in view['execution'].get('events', []):
                if event.get('kind') == 'READ_LOCAL':flat_reads[event['call_id']] = event
    contract = {
        'question': 'Repair the actual source-role/qualification mismatch in the existing legal dependency, using the simpler current primitive/flat-array interface. A nested-record READ attempt is not promoted: one response confuses notification duties with permissions and the other repeats to the output limit.',
        'objects': 'The two genuinely acquired existing helpers and their actual USE. Preserve useful rule boundaries; do not force two changes, add a gratuitous helper or manufacture an old defect. A necessary single edit is a valid result.',
        'source_parameters': 'Keep recipient classes, recipient ownership/roles, purpose/context and conditions distinct where the learned calculation uses them. Each list consumed as individual class names must contain class atoms, not a full qualified sentence or a protected-information category. Do not infer a permission from a prohibition or notification duty. Missing law stays unknown.',
        'computation': 'The helper computes the legal permission/applicability and native consequence. READ supplies literal source parameters, never the full native label or the final permission decision. A declaration or runtime support span is not independent semantic gold.',
        'scope': 'Disclosure tasks nda-5/nda-7 only where supported; the two other native views retain normal fallback and remain in the same parent score. No source-ID/native-answer lookup or hidden case-specific branch.',
        'comparison': 'Full and Generic receive the identical real Free B2 seed, same source texts, native TRAIN supervision, failure records, common runtime and one independently generated free proposal block each. Any scheduled Lift is evaluated equally. This isolates update mechanisms; it is not independent seed acquisition.',
        'admission': 'Strict trigger-parent improvement, every old parent nondecreasing, complete mixed-version table and compatible interfaces unchanged. Creation is not CoRev and read formatting is not Lift or CoRev.',
        'actual_flat_READ_failures_not_gold': flat_reads,
        'no_new_sources_DEV_TEST_full_training_or_paper': True}
    witness = read(root / 'tests/fixtures/skill_evolution_actual_unknown_guard_20261112.json')
    contract['actual_unresolved_execution_witness_not_gold'] = witness
    contract['specific_contract_repair'] = (
        'The prior two proposals used dictionary membership and False defaults on unresolved READs; '
        'the existing executor rejects this. The common prompt now states that runtime contract explicitly. '
        'Use literal accesses and valid short-circuiting, and request a separate source-supported structural fact '
        'when an explicit absence is needed. Do not treat reader uncertainty as absence, fabricate law, or copy '
        'the native answer into a read. Prior Full provenance also omitted an intervening parenthetical; '
        'all quotes must remain contiguous verbatim source substrings. This is a fixed contract repair, '
        'not a new source, schema sweep or relaxed admission.')
    paths = list((root / 'legal_skill_guard/skill_evolution').glob('*.py'))
    paths += list((root / 'tests').glob('test_skill_evolution_*.py')) + [Path(__file__).resolve(),
        root / 'tests/fixtures/skill_evolution_actual_unknown_guard_20261112.json']
    protocol = {'run_id': RUN, 'same_goal': True, 'goal_complete': False, 'arms': list(ARMS),
        'already_fixed_original_TRAIN_parents': keys, 'learning_batches': [[k] for k in keys[:3]],
        'execute_update_batch': 3, 'trigger': keys[2], 'history': keys[:2], 'frozen_reuse': keys[3],
        'shared_real_seed_hash': seed.hash, 'seed_path': str(seed_path.relative_to(root)),
        'acquisition_contract': contract,
        'changes_since_last_teacher': ['Complete READ/premise edit transplantation and actual code/source responsibility contexts implemented and offline checked.',
            'Source-rule reads exclude the native question and use one evidence-ID namespace.',
            'Retire the failed nested-record read; make atomic role/qualifier semantics explicit in the common acquisition contract and prompt.',
            'Explicitly synchronize the existing partial-unresolved execution and contiguous-quotation contracts with the teacher; real guard-failure regression added.'],
        'workload': 'Two independently generated teacher responses, one per arm, each at most one free block. Evaluate any pre-scheduled Lift and the free block with the original 1..3-edit complete table; then freeze and execute the fourth pre-fixed TRAIN parent once per arm. No repeat proposal, full matrix or TEST.',
        'interpretation': 'Report single-sufficient/absorption and failures. A local accepted package is not cross-parent pattern benefit. Reuse with the already-updated program is ordinary skill reuse unless a learned pattern actually changes candidate generation.',
        'offline_regressions_passed': 108, 'automatic_retries': 0,
        'public_TRAIN_sha256': hashlib.sha256(public_path.read_bytes()).hexdigest(),
        'executor_profile': profile['executor'], 'teacher_profile': profile['teacher'],
        'code_sha256': {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}}
    folder = root / 'artifacts' / RUN
    immutable_json(folder / 'protocol.json', protocol)
    return folder, protocol, profile, seed, {k: records[k] for k in keys}


def run(root, original):
    folder, protocol, profile, seed, records = prepare(root, original)
    with (folder / 'controller.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (folder / 'completed.json').exists():return read(folder / 'completed.json')
        for path, sha in protocol['code_sha256'].items():
            if hashlib.sha256((root / path).read_bytes()).hexdigest() != sha:raise ValueError('Bound code changed: ' + path)
        ledger_path = original / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'
        before_path = folder / 'ledger_before.json'
        if any(v.get('reserved', 0) for v in physical_snapshot(ledger_path).values()):raise ValueError('Reconcile pending requests first')
        if not before_path.exists():immutable_json(before_path, physical_snapshot(ledger_path))
        study = object.__new__(Study)
        study.root, study.folder, study.stage = root, folder, 'semantic_rule_update'
        study.profile = {**deepcopy(profile), 'prior_logical_replay_executions': {}, 'acquisition_contract': protocol['acquisition_contract']}
        study.records = records
        grading = read(original / 'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')
        study.grading = {k: grading[k] for k in records}
        study.source_ids = {'train': list(records), 'dev': [], 'test': []}
        study.batches, study.order, study.arms = protocol['learning_batches'], sum(protocol['learning_batches'], []), ARMS
        study.ledger = EvolutionLedger(ledger_path, run_id=RUN, sources=study.source_ids, binding=digest(protocol), teacher_concurrency=2)
        study.executor = FrozenExecutor(study.ledger, folder, profile['executor'])
        study.executor.exact_replay_roots = [original / profile['artifacts']]
        for rel in profile.get('exact_replay_profiles', []):
            previous = read(original / rel)
            if digest(previous['executor']) != digest(profile['executor']):raise ValueError('Fixed model configuration changed')
            study.executor.exact_replay_roots.append(original / previous['artifacts'])
        study.executor.exact_replay_roots += [root / 'artifacts' / name for name in (
            'legal_skill_evolution_contract_acquisition_20261112', 'legal_skill_evolution_contract_updates_20261112',
            'legal_skill_evolution_contract_read_recovery_20261112/AllPorts+CoRev_B2',
            'legal_skill_evolution_contract_read_recovery_20261112/FreeEvolution_B3',
            'legal_skill_evolution_source_rule_check_20261112', 'legal_skill_evolution_source_rule_id_check_20261112',
            'legal_skill_evolution_semantic_rule_update_20261112')]
        study.reads = FrozenReads(study.executor);study.runtime = SkillRuntime(study.reads)
        study.teacher = FrozenTeacher(study.ledger, folder, profile['teacher'])
        for arm in ARMS:
            path = study.library_path(arm, 2)
            if path.exists():
                if Library.load(path).hash != seed.hash:raise ValueError('Shared seed changed')
            else:deepcopy(seed).save(path)
        try:
            contexts = {}
            for arm in ARMS:
                status(folder, phase='prepare_existing_context', arm=arm)
                contexts[arm] = prepare_context(study, arm, 3)
            def one(arm):
                context = contexts[arm]
                if context['teacher_path'].exists():return read(context['teacher_path'])
                response = propose(FrozenTeacher(study.ledger, folder, profile['teacher']), arm=arm, batch=3,
                    library=context['old'], source_records=[records[k] for k in context['cohort']],
                    feedback=study.feedback(context['cohort'], context['current']), learned_patterns=context['old'].revision_patterns,
                    trigger=context['trigger'], history=context['history'], max_blocks=1,
                    planned_lift=context['planned_lift'], acquisition_contract=protocol['acquisition_contract'])
                immutable_json(context['teacher_path'], response);return response
            status(folder, phase='two_fixed_teacher_proposals')
            with ThreadPoolExecutor(max_workers=2) as pool:
                jobs = [pool.submit(one, arm) for arm in ARMS]
                # Drain both authorized tasks, including on one failure.
                errors = []
                for job in jobs:
                    try:job.result()
                    except Exception as error:errors.append(error)
                if errors:raise errors[0]
            for arm in ARMS:
                status(folder, phase='complete_candidate_table', arm=arm)
                study.update(arm, 3)
            reuse = {}
            for arm in ARMS:
                status(folder, phase='frozen_original_TRAIN_reuse', arm=arm)
                reuse[arm] = study.parent(protocol['frozen_reuse'], Library.load(study.library_path(arm, 3)))
            result = {'completed_utc': datetime.now(timezone.utc).isoformat(), 'goal_complete': False,
                'updates': {a: read(folder / a / 'update_B3.json') for a in ARMS}, 'reuse': reuse,
                'ledger_before': read(before_path), 'ledger_after': physical_snapshot(ledger_path),
                'semantic_review_pending': True, 'protocol_hash': digest(protocol)}
            immutable_json(folder / 'completed.json', result);status(folder, phase='terminal_review_pending', ledger=result['ledger_after'])
            return result
        except BaseException as error:
            status(folder, phase='preserved_after_error', error=type(error).__name__ + ': ' + str(error), ledger=physical_snapshot(ledger_path))
            raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser();parser.add_argument('action', choices=['prepare', 'run']);args = parser.parse_args()
    root = Path(__file__).resolve().parents[1];original = Path('/home/yndx/hhy/legal-skill-redesign-20261109')
    if args.action == 'prepare':
        folder, protocol, _, _, _ = prepare(root, original)
        print(json.dumps({'protocol': str(folder / 'protocol.json'), 'hash': digest(protocol), 'teacher_tasks': 2}))
    else:
        result = run(root, original);print(json.dumps({'completed': True, 'goal_complete': False, 'ledger': result['ledger_after']}))
