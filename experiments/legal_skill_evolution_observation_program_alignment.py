"""Align the next normal TRAIN update with the exact common author program.

The B1 task exposed statute text/interfaces but omitted the actual Prolog bodies.
Preserve it and its outputs. At the safe B2 boundary, give both teachers identical
verified program bodies and the actual conversion/observation failures; do not
rerun B1 or hand-edit an answer-producing converter.
"""
from copy import deepcopy
import hashlib
import json

from experiments import legal_skill_evolution_observation_library_train as current
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


def run():
    protocol, ledger, public, kernels = current.setup()
    with ledger.transaction() as db:
        assert not db.execute("select 1 from calls where status='reserved'").fetchone()
        assert not db.execute('select 1 from calls where id like ?', (current.RUN + ':B2:%:update',)).fetchone()
    assert (current.OUT / 'B2/initial_scored_results.json').exists()
    target = current.OUT / 'B2/teacher_task.json'
    if target.exists() and current.read(target).get('exact_author_program_interface_aligned'):
        return
    task = current.make_task(protocol, 2, public, kernels)
    immutable_json(current.OUT / 'B2/predispatch_program_alignment/teacher_task.json', task)
    kernel = next(iter(kernels.values()))
    source = current.ROOT / kernel['statute_directory']
    bodies = {}
    for name, expected in kernel['statute_sha256'].items():
        body = (source / name).read_bytes()
        assert hashlib.sha256(body).hexdigest() == expected
        bodies[name] = body.decode()
    task['shared_exact_immutable_author_programs'] = bodies
    task['exact_author_program_interface_aligned'] = True
    task['alignment_is_public_infrastructure_not_method_gain'] = True
    task['do_not_rerun_closed_B1_outputs'] = True
    task['shared_fixed_generic_representation'] = {
        'schema': current.read(current.ROOT / 'artifacts/legal_skill_evolution_generic_view_train_20261114/generation_schema.json'),
        'common_factual_serializer': (current.ROOT / 'legal_skill_guard/skill_evolution/generic_event_observation.py').read_text(),
        'actual_B1_results': current.read(current.ROOT / 'artifacts/legal_skill_evolution_generic_view_train_20261114/B1/scored_results.json')}
    task['error_feedback_by_id']['B1_same_correct_observation_wrong_native_lowering'] = {
        'source': next(s for s in public if '8175fcb9' in s),
        'finding': 'Both real views correctly contain Bob itemized deduction4324 and ongoing Alice/Bob marriage. Both lower the deduction to itemize_deductions_, while the immutable s63_c_6_A body asks deduction_(Itemded). This is an actual observation-to-program conversion error, not missing marriage extraction. Learn from the exact shared program, do not change it or invent a date/end/fact. Keep the failed B1 results; do not issue another B1 read.'}
    task['error_feedback_by_id']['B1_coupled_observation_channel_unread'] = {
        'source': next(s for s in public if '5c29a3' in s),
        'finding': 'PG family observations are complete, but the bundled marriage/returns/itemization view has itemizations:null and returns:null; the converter correctly retains unresolved rather than guessing absence. The chosen representation couples channels. Inspect the actual program demand and error to decide what must be observed, factored or converted. Do not clear unresolved or convert unknown to empty to manufacture a pass.'}
    registry = current.read(current.history.OUT / 'observation_component_registry.json')
    for arm in current.ARMS:
        library = current.read(current.OUT / 'B1' / arm / 'library.json')
        for component in library['components']:
            registry['B1/' + arm + '/' + component['id']] = deepcopy(component)
    task['parent_component_registry'] = registry
    task['parent_reference_instruction'] = 'Use exact keys in parent_component_registry; scope B1 references by arm because component names can collide. A parent reference is still not proof of actual reuse.'
    # Preserve the zero-dispatch predecessor before replacing the next not-yet-
    # dispatched task. No request, original row or completed run is changed.
    target.unlink()
    immutable_json(target, task)
    immutable_json(current.OUT / 'B2/program_alignment_receipt.json', {
        'exact_source_sha256': kernel['statute_sha256'], 'both_teachers_receive_same_task_sha256': digest(task),
        'old_task_and_all_B1_outputs_preserved': True, 'new_model_calls': 0,
        'no_original_formal_case_facts_or_TEST': True, 'law_not_hand_edited_into_the_converter': True})
    print(json.dumps({'next_batch': 2, 'exact_author_programs_shared': len(bodies),
        'task_sha256': digest(task), 'new_model_calls': 0}), flush=True)


if __name__ == '__main__':
    run()
