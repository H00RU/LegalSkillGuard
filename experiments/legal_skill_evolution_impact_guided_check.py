"""Execute the actual acquired edits and learned scope checks, without LLMs."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from experiments import legal_skill_evolution_impact_guided_edit as trial
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.open_acquisition import observe
from legal_skill_guard.skill_evolution.repair_impact_contracts import verify_effects


e = trial.e
OUT = trial.OUT / 'unbound_actual_check'


def source_checks(actual, source, review):
    roots = actual['execution']['source_output']['statements']
    forbidden = review['forbidden_unconditional_norm']
    qualified = review['supported_existing_qualified_norm']
    # Partial current-source checks, not a purported generic legal oracle.
    wrong = [r for r in roots if r['term'] == forbidden['term'] and 31 in r['support_ids']]
    right = [r for r in roots if r['term'] == qualified['term'] and 31 in r['support_ids']]
    return {'known_unconditional_assertion_absent': not wrong,
        'source_supported_qualified_restriction_present': True if right else None,
        'qualified_actor': qualified['term'][1] if right else None,
        'unreviewed_new_representations_require_review': not right,
        'full_source_semantics_certified': False}


def actual_impact_contract(scope):
    return {'repairs': [{'id': 'known_unconditional_assertion_absent',
            'evidence_ref': 'common_task.json#current_source_program_dependency_graph.partial_source_review'},
        {'id': 'source_supported_qualified_restriction_present',
            'evidence_ref': 'common_task.json#current_source_program_dependency_graph.partial_source_review'}],
        'conclusions': [{'id': row['node'], 'value': row['value'], 'validity': 'supported',
            'evidence_ref': row['validity_evidence_ref']} for row in scope['preserve_supported']]}


def validate_no_source_identity_hack(library, raw, source_ids):
    import ast
    from legal_skill_guard.skill_evolution.source_schema import LABELS
    changed = raw['source_functions'] + raw['decision_functions']
    disallowed = set(source_ids) | {s.split(':', 1)[1] for s in source_ids}
    for code in changed:
        for node in ast.walk(ast.parse(code)):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in disallowed:
                raise ValueError('Acquired edit branches on fixed source identity')
    for node in ast.walk(ast.parse(library['source_program'])):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in LABELS:
            raise ValueError('Source-stage native label bypass')


def run():
    p, _ = trial.setup()
    before = trial.rows()
    assert not any(r[6] == 'reserved' for r in before)
    assert all((trial.OUT / arm / 'teacher.json').exists() for arm in trial.ARMS)
    public = {s['key']: s for s in e.read(e.previous.prior.prior.PUBLIC)}
    grading = e.read(e.previous.prior.prior.GRADING)
    scope = e.read(trial.OUT / 'learned_generation_scope.json')
    task = e.read(trial.OUT / 'common_task.json')
    review = task['current_source_program_dependency_graph']['partial_source_review']
    contract = actual_impact_contract(scope)
    immutable_json(OUT / 'learned_scope_check_contract.json', contract)
    summaries = []
    for arm in trial.ARMS:
        raw = e.read(trial.OUT / arm / 'teacher.json')['value']
        try:
            library = trial.compile_edit(raw)
            validate_no_source_identity_hack(library, raw, p['acquisition_sources'])
        except Exception as exc:
            immutable_json(OUT / arm / 'compile_failure.json', {'error': type(exc).__name__ + ': ' + str(exc),
                'original_raw_preserved': True, 'not_success': True})
            summaries.append({'arm': arm, 'compile_passed': False, 'error': str(exc)})
            continue
        immutable_json(OUT / arm / 'candidate_library.json', library)
        results = []
        for source in p['acquisition_sources']:
            pub, units, _ = e.previous.prior.prior.source_material(e.previous.PARENT, public, source)
            observation = observe(trial.NoCalls(), trial.RUN + ':actual:' + arm + ':' + source,
                source, library, source_text=pub['source_text'], units=units,
                source_output=e.read(e.OUT / 'upstream' / e.name_for(source))['source_output'])
            actual = e.previous.prior.prior.evaluate_source(library, observation, public[source], grading[source])
            initial = e.read(e.OUT / 'unbound_pure_preview/ConstraintAcquire' / e.name_for(source))['actual']
            count = lambda x: sum(bool(v['score'] and v['score']['correct']) for v in x['feedback']['views'])
            row = {'source': source, 'native_correct_before': count(initial), 'native_correct_after': count(actual),
                'actual': actual, 'observation': observation, 'new_model_requests': 0}
            if source == p['target_source']:
                checks = source_checks(actual, source, review)
                effects = {'repairs': {k: checks[k] for k in ('known_unconditional_assertion_absent',
                    'source_supported_qualified_restriction_present')},
                    'conclusions': {r['id']: checks['qualified_actor'] for r in contract['conclusions']}}
                row.update({'actual_partial_source_checks': checks,
                    'learned_scope_effects': effects, 'learned_scope_selection': verify_effects(contract, effects)})
            immutable_json(OUT / arm / 'execution' / e.name_for(source), row)
            results.append(row)
        target, = [r for r in results if r['source'] == p['target_source']]
        summaries.append({'arm': arm, 'compile_passed': True,
            'native_correct_before': sum(r['native_correct_before'] for r in results),
            'native_correct_after': sum(r['native_correct_after'] for r in results), 'native_views': 32,
            'target_partial_source_checks': target['actual_partial_source_checks'],
            'learned_scope_selection': target['learned_scope_selection'],
            'actual_source_function_edits': len(raw['source_functions']),
            'actual_consumer_function_edits': len(raw['decision_functions']),
            'per_source': [{k: r[k] for k in ('source', 'native_correct_before', 'native_correct_after')} for r in results]})
    assert trial.rows() == before
    old = e.read(trial.OUT / 'ledger_before_row_hashes.json')
    assert all(digest(r) == old[r[0]] for r in before if r[0] in old)
    recent = [r for r in before if r[0].startswith(trial.RUN + ':')]
    assert len(recent) == 2 and all(r[6] == 'completed' for r in recent)
    result = {'rows': summaries, 'old_ledger_rows_unchanged': len(old),
        'cumulative_calls': len(before), 'new_executor_requests': 0, 'new_teacher_requests': len(recent),
        'new_requests_during_actual_check': 0,
        'same_common_task_history_and_edit_capacity': True,
        'actual_ImpactGuided_teacher_request_consumed_learned_generation_scope': True,
        'training_fit_is_not_prospective_edit_benefit': True,
        'independent_U_gain_established': False, 'goal_complete': False}
    immutable_json(OUT / 'summary.json', result)
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    run()
