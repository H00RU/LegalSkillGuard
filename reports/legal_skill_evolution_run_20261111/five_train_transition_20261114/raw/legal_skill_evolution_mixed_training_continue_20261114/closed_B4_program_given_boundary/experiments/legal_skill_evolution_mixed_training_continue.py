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

from experiments import legal_skill_evolution_observation_library_train as learned
from experiments import legal_skill_evolution_observation_library_preflight as preflight
from experiments import legal_skill_evolution_mixed_case_actor as actor
from experiments import legal_skill_evolution_mixed_residual_reads as residual_reads
from experiments import legal_skill_evolution_source_batch_update as source_updates
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


ROOT = learned.ROOT
OUT = ROOT / 'artifacts/legal_skill_evolution_mixed_training_continue_20261114'
read = learned.read


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
    with learned.setup()[1].transaction() as db:
        assert not db.execute("select 1 from calls where status='reserved'").fetchone()
        assert not db.execute('select 1 from calls where id like ?',
            (learned.RUN + f':B{batch}:%:update',)).fetchone()
    task = learned.make_task(protocol, batch, public, kernels)
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
    task['continuous_program_alignment'] = True
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
    protocol, ledger, public, kernels = learned.setup()
    for batch in range(start, stop + 1):
        if batch >= 4:
            source_updates.run(batch, batch)
        # Existing paid rows are immutable; no regeneration on resume.
        for arm in ('GenericView', *learned.ARMS):
            actor.execute(actor_protocol, batch, arm, initial=arm != 'GenericView')
        actor.generic.score(read(actor.generic.OUT / 'protocol.json'), batch)
        learned.score(protocol, public, batch, initial=True)
        if batch >= 4:
            residual_reads.run(batch)
        prepare_task(protocol, public, kernels, batch)
        learned.acquire(protocol, ledger, public, kernels, batch)
        for arm in learned.ARMS:
            if not (learned.OUT / f'B{batch}' / arm / 'unbound_library_preflight.json').exists():
                preflight.run(arm, batch)
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
