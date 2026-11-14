"""Resume the current mixed TRAIN branches, preserving closed batch artifacts.

This is a continuation, not a replacement study or a cold-start experiment.
The established observation learner/actor retain their request identities. The
sidecar supplies the actual author programs at every subsequent update, keeps
raw failures in the task, and resumes only missing operations.
"""
import argparse
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from experiments import legal_skill_evolution_observation_library_train as learned
from experiments import legal_skill_evolution_observation_library_preflight as preflight
from experiments import legal_skill_evolution_mixed_case_actor as actor
from experiments import legal_skill_evolution_mixed_residual_reads as residual_reads
from experiments import legal_skill_evolution_source_batch_update as source_updates
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.sara_statute_kernel import current_case_interface, GIVENS
from legal_skill_guard.skill_evolution.native_case_encoding import FACTUAL_ENCODING


ROOT = learned.ROOT
RUN = 'legal_skill_evolution_mixed_training_checkpointed_20261114'
OUT = ROOT / 'artifacts' / RUN
read = learned.read


def setup():
    path = OUT / 'protocol.json'
    if path.exists():
        protocol = read(path)
    else:
        prior = read(learned.OUT / 'protocol.json')
        files = [Path(__file__), Path(preflight.__file__), Path(actor.__file__), Path(source_updates.__file__),
            Path(residual_reads.__file__), Path(learned.__file__),
            Path(source_updates.initial.__file__), Path(source_updates.checkpoints.__file__)]
        files += [ROOT / 'legal_skill_guard/skill_evolution' / name for name in (
            'sara_statute_kernel.py', 'generic_event_observation.py', 'native_case_encoding.py', 'case_observation_contract.py',
            'source_selection_certificate.py', 'source_disposal_review.py', 'clients.py', 'ledger.py',
            'teacher_transport.py', 'runtime.py', 'source_function_patch.py', 'acquisition_proposal.py',
            'open_acquisition.py', 'source_composition.py', 'native_theory_feedback.py',
            'span_compiler.py', 'span_compiler_worker.py')]
        protocol = {'run_id': RUN, 'same_goal': True, 'continued_from': prior['run_id'],
            'sources': prior['sources'], 'batches': prior['batches'],
            'executor_profile': prior['executor_profile'], 'teacher_profile': prior['teacher_profile'],
            'source_sha256': {str(p.resolve().relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
            'data_sha256': prior['data_sha256'], 'thinking': False, 'TEST_opened': False,
            'B1_through_B4_checkpoints_and_all_calls_preserved': True,
            'B5_forward_common_explicit_givens': GIVENS,
            'author_statute_sources_unchanged': True, 'shared_interface_repair_not_M2_learning_credit': True}
        protocol['same_run_teacher_concurrency'] = 2
        review_path = ROOT / 'artifacts/legal_skill_evolution_mixed_training_givens6_20261114/unbound_B5_semantic_review.json'
        protocol['data_sha256'] = {**protocol['data_sha256'], str(review_path.relative_to(ROOT)): hashlib.sha256(review_path.read_bytes()).hexdigest()}
        protocol['C5_teacher_results_reused_no_repeat'] = True
        protocol['source_compiler_accepts_only_ContractNLI_public_records'] = True
        for folder, arms in ((source_updates.train.OUT, source_updates.train.ARMS), (learned.OUT, learned.ARMS)):
            for arm in arms:
                inherited = folder / 'B5' / arm / 'teacher.json'
                protocol['data_sha256'][str(inherited.relative_to(ROOT))] = hashlib.sha256(inherited.read_bytes()).hexdigest()
        immutable_json(path, protocol)
        for p in files:
            target = OUT / 'source_snapshot' / p.resolve().relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(p.read_bytes())
    for name, expected in {**protocol['source_sha256'], **protocol['data_sha256']}.items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, name
    ledger = EvolutionLedger(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3', run_id=RUN,
        sources={'train': protocol['sources'], 'dev': [], 'test': []}, binding=digest(protocol), teacher_concurrency=2)
    public = {s['key']: s for s in read(learned.parent.OUT / 'SARA_corrected_TRAIN_views.json')}
    kernels = {r['source']: current_case_interface(r['kernel'])
        for r in read(learned.parent.OUT / 'SARA_native_kernel_bank.json')}
    return protocol, ledger, public, kernels


def verify_actor():
    protocol = actor.prepare()
    for name, expected in protocol['source_sha256'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, name
    return protocol


def prepare_task(protocol, public, kernels, batch):
    """The same complete task goes to the two independent teachers."""
    path = learned.OUT / f'B{batch}/teacher_task.json'
    if path.exists() and read(path).get('continuous_program_alignment'):
        return read(path)
    with setup()[1].transaction() as db:
        assert not db.execute("select 1 from calls where status='reserved'").fetchone()
        assert not db.execute('select 1 from calls where id like ?',
            (RUN + f':B{batch}:%:update',)).fetchone()
    task = learned.make_task(protocol, batch, public, kernels)
    task['native_event_encoding'] = FACTUAL_ENCODING
    immutable_json(OUT / f'B{batch}/predispatch_teacher_task.json', task)
    aligned = read(learned.OUT / 'B2/teacher_task.json')
    for key in ('shared_exact_immutable_author_programs', 'exact_author_program_interface_aligned',
                'alignment_is_public_infrastructure_not_method_gain'):
        task[key] = deepcopy(aligned[key])
    kernel = next(iter(kernels.values()))
    for name, body in task['shared_exact_immutable_author_programs'].items():
        assert hashlib.sha256(body.encode()).hexdigest() == kernel['statute_sha256'][name]
    from legal_skill_guard.skill_evolution.generic_event_observation import schema_for
    task['shared_fixed_generic_representation'] = {
        'schema': schema_for(kernel),
        'common_factual_serializer': (ROOT / 'legal_skill_guard/skill_evolution/generic_event_observation.py').read_text(),
        'actual_completed_batches': [read(actor.generic.OUT / f'B{b}/scored_results.json')
            for b in range(1, batch + 1) if (actor.generic.OUT / f'B{b}/scored_results.json').exists()],
        'shared_minimal_reader_context': ['facts', 'question', 'native_query', 'query_clause'],
        'old_truncated_responses_retained_not_retried': True}
    registry = deepcopy(aligned['parent_component_registry'])
    for b in range(1, batch):
        for arm in learned.ARMS:
            for component in read(learned.OUT / f'B{b}' / arm / 'library.json')['components']:
                registry[f'B{b}/{arm}/' + component['id']] = deepcopy(component)
    task['parent_component_registry'] = registry
    task['parent_reference_instruction'] = aligned['parent_reference_instruction']
    # These are actual generated observations and checked conversions, including
    # failures; score-only summaries would hide the mechanism that needs repair.
    task['actual_current_raw_observations_and_conversions'] = read(
        learned.OUT / f'B{batch}/initial_scored_results.json')
    for i, row in enumerate(task['actual_current_raw_observations_and_conversions']['rows']):
        if not row['execution']['handled'] or not row['native_score']['correct']:
            task['error_feedback_by_id'][f'B{batch}_actual_{row["arm"]}_{i}'] = {
                'source': row['source'], 'actual': row,
                'instruction': 'Diagnose planner, representation, factual observation, conversion and public native interface separately. Repair reusable components from current source facts; do not infer a case event from a target claim or default unread to absence.'}
    if batch == 3:
        task['error_feedback_by_id']['B3_actual_wage_scope_and_claim_leakage'] = {
            'finding': 'The real agricultural-hay wage case was routed through a termination/disability benefit component. PG invented disability and quoted the question as facts; Free correctly observed the payment but selected an irrelevant additional termination component and held it unread. Learn exact clause demand and reusable episode scope, not a case/name branch.'}
        task['error_feedback_by_id']['B3_actual_151_given_interface_boundary'] = {
            'finding': 'The actual facts explicitly say section151(d), not151(b)/(c). Both arms generated151(b); PG also invented income2000 from the question, while Free reversed an additional claim. The common native input permits only explicit151b/c auxiliary givens. The author151_d_2 body checks either b/c and Ea=0. Do not invent b/c, an income or a relationship to compensate for an unrepresented explicit given; preserve a genuine unsupported given as unresolved. This is distinct from a positive fact quote being a substring.'}
    else:
        task['error_feedback_by_id']['query_scope_and_unused_information'] = {
            'finding': 'Preserve genuinely needed unknowns, but do not require observing every fact in a case when the actual queried author program does not depend on it. In the closed B3 record, the151_d_2 query supplies Ea=2000 whereas every successful body ends Ea is0; this particular claim cannot succeed regardless of missing b/c givens. Source-given representability and the actual query dependency are separate. A law-only result is not learned factual observation success; never remove an unknown merely because a TRAIN label is known.'}
    pair_path = residual_reads.OUT / f'B{batch}/scored_results.json'
    if pair_path.exists():
        task['matched_same_contract_read_results'] = read(pair_path)
        task['actual_matched_read_observations'] = [read(p) for p in sorted(
            (residual_reads.OUT / f'B{batch}').glob('*.json')) if p.name != 'scored_results.json']
    if batch > 5:
        review_path = ROOT / 'artifacts/legal_skill_evolution_mixed_training_givens6_20261114/unbound_B5_semantic_review.json'
        review = read(review_path)
        seen = {sid for b in protocol['batches'][:batch-1] for sid in b}
        assert all(r['source'] in seen for r in review['source_audits'])
        task['past_actual_TRAIN_semantic_review'] = review
        for index, item in enumerate(review['source_audits']):
            task['error_feedback_by_id']['B5_source_semantics_' + str(index)] = item
        task['semantic_feedback_instruction'] = 'The same source-based review is supplied to both teachers. Correct-native outputs can still omit a stated venue category or invent a query-derived event day. Learn reusable observation distinctions and lowering from these actual errors. Do not alter old records, infer a cash quarter or payment day, turn unrelated source silence into false, or assume a correct label certifies extraction. Preserve source-supported execution and genuine unknowns.'
    task['continuous_program_alignment'] = True
    task['shared_case_interface_correction_after_closed_B4'] = {
        'current_explicit_legal_given_signatures': GIVENS,
        'finding': 'Actual B4 facts explicitly grant Alice deductions for herself under63(f)(1)(A) and spouse Bob under63(f)(1)(B). The former four-pilot input allowed only151b/c. The public case interface now permits those two exact existing author predicates. Preserve taxpayer/beneficiary direction, do not fabricate ages or blindness. Target predicates still cannot be supplied as facts; unknown151(d) is not automatically b/c.',
        'actual_current_kernel_interfaces_above_override_historical_prototype_cards': True,
        'source_only_original_TRAIN_audit': 'Other original TRAIN sources explicitly give a self151(b) amount and152(c)(1) qualifying-child status; those exact existing author predicates are exposed with their declared numeric/entity/year types as well.152_c_1 order is Dependent,Taxpayer,Year. This audit uses public TRAIN facts, no native labels or formal case fact files.',
        'author_statute_programs_and_closed_B4_results_unchanged': True,
        'both_arms_receive_same_repair_not_method_credit': True}
    task['future_case_facts_questions_labels_withheld_from_this_update'] = True
    path.unlink()
    immutable_json(path, task)
    immutable_json(OUT / f'B{batch}/task_alignment_receipt.json', {
        'task_sha256': digest(task), 'same_task_for_both_teachers': True,
        'author_programs': kernel['statute_sha256'], 'raw_old_tasks_preserved': True,
        'new_generation_calls_for_alignment': 0, 'TEST_opened': False})
    return task


def run(start, stop):
    actor_protocol = verify_actor()
    protocol, ledger, public, kernels = setup()
    for batch in range(start, stop + 1):
        if batch >= 4:
            source_updates.initial.run(batch)
        # Existing paid rows are immutable; no regeneration on resume.
        for arm in ('GenericView', *learned.ARMS):
            actor.execute(actor_protocol, batch, arm, initial=arm != 'GenericView')
        actor.generic.score(read(actor.generic.OUT / 'protocol.json'), batch)
        learned.score(protocol, public, batch, initial=True)
        if batch >= 4:
            residual_reads.run(batch)
        prepare_task(protocol, public, kernels, batch)
        source_protocol = source_updates.train.prepare()
        source_needed = not source_updates.checkpoints.exists(batch)
        if source_needed:
            source_updates.make_task(source_protocol, batch)
            # One controller, at most two authorized teacher requests, all in
            # the same bound physical ledger namespace. Each branch's two
            # independent proposals remain serial with its fixed common input.
            with ThreadPoolExecutor(max_workers=2) as pool:
                jobs = [pool.submit(source_updates.acquire, source_protocol, batch, ledger),
                    pool.submit(learned.acquire, protocol, ledger, public, kernels, batch)]
                failures = []
                for job in jobs:
                    try:
                        job.result()
                    except Exception as error:
                        failures.append(error)
                if failures:
                    raise failures[0]
            rows_by_arm = {arm: source_updates.compile_candidate(source_protocol, batch, arm) or []
                for arm in source_updates.train.ARMS}
            source_updates.finalize(batch, rows_by_arm)
        else:
            learned.acquire(protocol, ledger, public, kernels, batch)
        for arm in learned.ARMS:
            if not (learned.OUT / f'B{batch}' / arm / 'unbound_library_preflight.json').exists():
                preflight.run(arm, batch, context=(protocol, ledger, public, kernels))
            actor.execute(actor_protocol, batch, arm)
        learned.score(protocol, public, batch)
        immutable_json(OUT / f'B{batch}/observation_branch_complete.json', {
            'batch': batch, 'learning_update_executed': True,
            'not_all_five_training_complete': True, 'goal_complete': False})
        print(json.dumps({'observation_batch_completed': batch}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', type=int, choices=range(3, 9), default=3)
    parser.add_argument('--stop', type=int, choices=range(3, 9), default=8)
    args = parser.parse_args()
    with (ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        run(args.start, args.stop)
