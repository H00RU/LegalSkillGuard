"""Compile and actually execute the normal B2 source-library update.

No model is available to this offline path. The native check is lawful TRAIN
feedback. A reused selection certificate is allowed only for identical G,
consumer, renderers and the identical certified residual context.
"""
import argparse
from copy import deepcopy
import json

from experiments import legal_skill_evolution_source_library_train as train
from experiments.legal_skill_evolution_source_local_preview import NoModel
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.source_function_patch import apply_function_edits


def run(arm, *, supplied_type_repair=None):
    task = train.read(train.OUT / 'B2/teacher_task.json')
    old = task['current_libraries'][arm]
    raw = train.read(train.OUT / 'B2' / arm / 'teacher.json')['value']
    packet = deepcopy(raw)
    program, preservation = apply_function_edits(old['source_program'], packet.pop('source_function_edits'))
    packet['source_program'] = program
    assert packet['decision_functions'] == []
    public = {s['key']: s for s in train.read(train.parent.PREPARED / 'public.json') if s['dataset'] == 'ContractNLI'}
    grading = train.read(train.parent.PREPARED / 'grading.json')
    library, receipt, proposal = train.previous.old.compile_raw(old, packet, arm, public)
    library['spec']['decision_program'] = task['common_frozen_consumer']
    if arm == 'ConstraintAcquire':
        # Current B2 proposal reuses exactly the already selected G. Do not
        # silently substitute suggested IDs if a future proposal changes it.
        assert library['language'] == old['language']
        assert library['renderers'] == old['renderers']
        assert set(library['suggested_rule_ids']) == set(old['selected_rule_ids'])
        library['selected_rule_ids'] = old['selected_rule_ids']
    folder = train.OUT / 'B2' / arm
    install_folder = folder
    if supplied_type_repair is not None:
        provided = [c for lib in task['current_libraries'].values() for c in lib['spec']['constructors']
                    if c['name'] == supplied_type_repair]
        assert provided and all(c == provided[0] for c in provided)
        assert supplied_type_repair not in {c['name'] for c in library['spec']['constructors']}
        before_types = digest(library['spec']['constructors'])
        library['spec']['constructors'].append(deepcopy(provided[0]))
        folder = folder / 'provided_type_recovery'
        immutable_json(folder / 'type_recovery_receipt.json', {
            'constructor': provided[0], 'unique_existing_task_definition_sha256': digest(provided[0]),
            'before_types_sha256': before_types, 'after_types_sha256': digest(library['spec']['constructors']),
            'source_composition_and_consumer_code_unchanged': True, 'raw_response_unchanged': True,
            'native_labels_not_used_for_type_recovery': True, 'new_model_calls': 0})
    immutable_json(folder / 'compiled_candidate.json', library)
    immutable_json(folder / 'function_patch_preservation.json', preservation)
    immutable_json(folder / 'compilation_receipt.json', receipt)
    rows = []
    for source_task in task['tasks']:
        sid = source_task['source_id']
        path = folder / 'candidate_results' / train.previous.old.name_for(sid)
        if path.exists():
            row = train.read(path)
        else:
            prior_observation = train.read(train.parent.OUT / 'source_pass' / arm / train.previous.old.name_for(sid)).get('observation')
            observation = train.previous.old.observe(NoModel(), train.RUN + ':B2:offline:' + arm + ':' + sid,
                sid, library, source_text=source_task['full_source_text'], units=source_task['source_units'],
                source_output=source_task['incoming_source_output'],
                previous_observations=[prior_observation] if prior_observation is not None else [])
            assert observation['new_model_requests'] == 0
            primary = train.previous.old.previous.prior.prior.evaluate_source(library, observation, public[sid], None)
            immutable_json(path.with_name(path.stem + '_primary.json'), {'source': sid, 'observation': observation,
                'actual_unscored': primary, 'new_model_calls': 0})
            actual = train.previous.old.previous.prior.prior.evaluate_source(library, observation, public[sid], grading[sid])
            row = {'source': sid, 'current_batch': source_task['current_batch'], 'observation': observation,
                'actual': actual, 'correct': sum(bool(v['score'] and v['score']['correct']) for v in actual['feedback']['views']),
                'unresolved': len(public[sid]['views']) - sum(v['core_executed'] for v in actual['feedback']['views']),
                'new_model_calls': 0, 'fallback': False}
            immutable_json(path, row)
        rows.append(row)
        print(json.dumps({k: row[k] for k in ('source', 'current_batch', 'correct', 'unresolved')}), flush=True)
    certificate = None
    if arm == 'ConstraintAcquire':
        witness = next(r for r in rows if '8fb38aee' in r['source'])
        prior_path = train.previous.OUT / 'unbound_proposed_execution/ConstraintAcquire' / train.previous.old.name_for(witness['source'])
        before = train.read(prior_path)
        prior_certificate = train.read(train.previous.OUT / 'unbound_local_objective_certificate/certificate.json')
        assert prior_certificate['native_loss_lower_bound'] == 1
        assert witness['observation']['context'] == before['observation']['context']
        assert library['spec']['decision_program'] == old['spec']['decision_program']
        loss = sum(4 - r['correct'] for r in rows)
        assert loss == 1, 'The reused one-error bound does not certify this new candidate'
        certificate = {'scope_sources': [r['source'] for r in rows], 'native_loss': loss,
            'native_loss_lower_bound': 1, 'selection_edits': 0, 'selection_edit_lower_bound': 0,
            'same_G_renderers_consumer_and_certified_residual_context': True,
            'reused_residual_certificate_sha256': digest(prior_certificate),
            'only_phi_changed_in_this_batch': True, 'not_a_new_G_update_or_semantic_certificate': True,
            'exact_objective_minimum_given_current_phi': True, 'new_model_calls': 0}
        immutable_json(folder / 'selection_certificate.json', certificate)
    result = {'arm': arm, 'batch': 2, 'source_count': len(rows),
        'current_correct': sum(r['correct'] for r in rows if r['current_batch']), 'current_total': 12,
        'all_supplied_correct': sum(r['correct'] for r in rows), 'all_supplied_total': 4 * len(rows),
        'unresolved': sum(r['unresolved'] for r in rows), 'new_model_calls': 0,
        'row_summary': [{k: r[k] for k in ('source', 'current_batch', 'correct', 'unresolved')} for r in rows],
        'selected_G_certificate': certificate, 'goal_complete': False}
    immutable_json(folder / 'update_result.json', result)
    immutable_json(install_folder / 'library.json', library)
    if folder != install_folder:
        immutable_json(install_folder / 'update_result.json', {**result,
            'recovered_candidate_evidence': str(folder.relative_to(train.ROOT)),
            'original_type_failure_and_partial_executions_retained': True})
    print(json.dumps({k: v for k, v in result.items() if k not in ('row_summary', 'selected_G_certificate')}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--arm', choices=train.ARMS, required=True)
    parser.add_argument('--supplied-type-repair')
    args = parser.parse_args()
    run(args.arm, supplied_type_repair=args.supplied_type_repair)
