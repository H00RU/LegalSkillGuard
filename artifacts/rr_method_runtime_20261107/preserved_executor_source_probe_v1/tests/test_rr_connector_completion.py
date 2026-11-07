"""Completion wiring regressions; invented units here are offline tests only."""
from copy import deepcopy
from fractions import Fraction
import json

import pytest

from legal_skill_guard.rr.compilation import source_theory
from legal_skill_guard.rr.connector_completion import ConnectorQuery
from legal_skill_guard.rr.coverage import Unsupported, complete, plan_batch
from legal_skill_guard.rr.engine import analyze
from legal_skill_guard.rr.interfaces import AllowanceBank, Amount


def source_and_proposal(*, bind_residual=False, unknown=False, candidates=1):
    source = {'dataset': 'RuleArena_Airline', 'public': {
        'rules': 'The fee is 7 per crate.\nBoolean b_waived = false.' +
                 ('\nAn untranslated exception may change the fee.' if unknown else ''),
        'prompt': 'Count: 2.'}}
    count_source = 's3' if unknown else 's2'
    bindings = [{'name': 'n_count', 'type': 'integer', 'value': 2, 'source': count_source}]
    compiled = ['s0', count_source]
    links = {'s0': ['query'], count_source: ['binding:n_count']}
    if bind_residual:
        bindings.append({'name': 'b_waived', 'type': 'scalar', 'value': False, 'source': 's1'})
        compiled.append('s1')
        links['s1'] = ['binding:b_waived']
    query = {'op': 'if', 'args': [{'var': 'b_waived'}, 0,
             {'op': 'scale', 'args': [7, {'var': 'n_result'}]}]}
    body = {'bindings': bindings, 'candidates': [{'slot': 'n_count'}]*candidates, 'selected': 0,
            'source_links': links, 'project': 'identity', 'query': query}
    proposal = {'answer': 14, 'program': {'kind': 'connector', 'body': body},
                'compiled_units': compiled, 'unsupported_units': [], 'interfaces': []}
    return source, proposal


def test_connector_result_enters_actual_source_completion_space():
    source, proposal = source_and_proposal()
    result = analyze(source, json.dumps(proposal))
    assert result['program_status'] == 'partially_compiled_connector'
    assert result['certificate_status'] == 'translation_unresolved'
    theory = source_theory(source, result)
    checked = complete(theory)
    assert sorted(w.answer for w in checked.worlds) == [0, 14]
    batch = plan_batch(theory, lambda units: len(units)*10, 100)
    assert batch.status == 'separation_complete'
    assert batch.selected == ('s1',)


def test_resolving_source_observation_rechecks_selected_connector():
    source, proposal = source_and_proposal(bind_residual=True)
    result = analyze(source, json.dumps(proposal))
    assert result['certificate_status'] == 'completion_stable'
    assert result['answer'] == 14
    assert result['certificate_basis'] == 'source_completion_selected_connector_not_H'
    assert result['certificate']['completion_count'] == 1
    assert result['certificate']['natural_language_faithfulness_proven'] is False
    assert len(result['execution_states']) == 1


def test_unknown_rule_scope_still_blocks_connector_certificate():
    source, proposal = source_and_proposal(bind_residual=True, unknown=True)
    result = analyze(source, json.dumps(proposal))
    assert result['candidate_answer'] == 14
    assert result['certificate_status'] == 'translation_unresolved'
    assert result['completion_assessment']['unknown_scope'] == ['s2']
    assert 'certificate' not in result


def test_agreeing_H_is_not_a_completion_proof():
    source, proposal = source_and_proposal(bind_residual=True, candidates=2)
    proposal['program']['body'].pop('selected')
    result = analyze(source, json.dumps(proposal))
    assert result['candidate_answer'] == 14
    assert result['program_status'] == 'candidate_pool_agreement_only'
    assert result['certificate_status'] == 'translation_unresolved'
    assert 'certificate' not in result
    assert source_theory(source, result) is None


@pytest.mark.parametrize('selected', [True, -1, 1, '0'])
def test_invalid_explicit_selection_is_rejected(selected):
    source, proposal = source_and_proposal(bind_residual=True)
    proposal['program']['body']['selected'] = selected
    result = analyze(source, json.dumps(proposal))
    assert result['program_status'] == 'invalid_IR'
    assert 'certificate' not in result


def test_connector_completion_keeps_exact_rationals():
    query = ConnectorQuery({'slot': 'n_input'}, {'project': 'identity',
        'query': {'op': 'divide_constant', 'args': [{'var': 'n_result'}, 3]}})
    assert query.evaluate({'n_input': 1}) == Fraction(1, 3)


def test_each_completion_world_has_an_independent_allowance_state():
    bank = AllowanceBank()
    key = ('rule', 'owner', 'period')
    bank.create(key, 100, policy='input_order', order_observable=True)
    inputs = [Amount(80, 'USD', 'owner', 'period', frozenset({str(i)}), 'element') for i in range(2)]
    env = {'bank': bank, 'key': key, 'amounts': inputs}
    before = deepcopy(bank.__rr_state__())
    query = ConnectorQuery({'op': 'thread_allowance', 'inputs': [{'slot': 'amounts'}],
        'params': {'bank_slot': 'bank', 'key_slot': 'key'}}, {'project': 'amount_values'})
    first, second = query.execute(env), query.execute(env)
    # thread_allowance returns the amounts remaining after entitlement use.
    assert first['answer'] == second['answer'] == [0, 60]
    assert [event['used'] for event in first['execution_state']['bank']['events']] == [80, 20]
    assert first['execution_state'] == second['execution_state']
    assert bank.__rr_state__() == before


def test_missing_connector_slots_are_not_repaired_by_completion():
    query = ConnectorQuery({'op': 'join_on', 'inputs': [{'slot': 'slot0'}, {'slot': 'slot1'}],
                           'params': {'keys': ['column0']}}, {'project': 'entailment_label'})
    with pytest.raises(Unsupported, match='slot0'):
        query.evaluate({'n_income': 6662, 'n_tax': 999})
