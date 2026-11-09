import pytest
from legal_skill_guard.rr.semantic_contracts import (
    ContractError, compare_modules, evaluate, minimum_separating_batch, validate_module,
)


def test_integer_division_matches_python_for_negative_numerators():
    for n in [-2501, -1, 0, 1, 2500, 2501]:
        assert evaluate('x // 2500', {'x': 'integer'}, {'x': n}) == n // 2500
        assert evaluate('ceildiv(x, 2500)', {'x': 'integer'}, {'x': n}) == -((-n) // 2500)


def test_typed_conditional_denominator_is_supported_without_model_repair():
    assert evaluate('ceildiv(x, 1250 if b else 2500)', {'x': 'integer', 'b': 'boolean'}, {'x': 2501, 'b': True}) == 3


def test_counterexample_is_executable_and_not_a_natural_language_proof():
    signature = dict(x='integer', y='integer', z='integer')
    r = compare_modules('x*y*z', 'x+y+z', signature, 'x > 0 and y > 0 and z > 0')
    assert r['status'] == 'sat' and r['left_value'] != r['right_value']
    assert evaluate('x*y*z', signature, r['witness']) == r['left_value']
    assert not r['natural_language_faithfulness_proved']


def test_equivalence_requires_nonempty_domain_and_all_assignments():
    r = compare_modules('x+x', '2*x', {'x': 'integer'}, 'x >= 0')
    assert r['equivalent_over_supplied_domain']
    with pytest.raises(ContractError):
        compare_modules('x', 'x+1', {'x': 'integer'}, 'x < 0 and x > 0')


@pytest.mark.parametrize('text', ['__import__("os")', 'x // 0', 'x // -2', 'ceildiv(x,x)', 'True+1', 'x[0]'])
def test_unsafe_or_ill_typed_terms_are_rejected(text):
    with pytest.raises(ContractError):
        evaluate(text, {'x': 'integer'}, {'x': 1})


def test_provenance_membership_does_not_claim_source_semantics():
    m = dict(expression='x+1', rule_quotes=['add one'], scope_notes='', unresolved_requirements=[])
    validate_module(m, {'x': 'integer'}, 'Please add one.')
    with pytest.raises(ContractError):
        validate_module(m, {'x': 'integer'}, 'Subtract two.')


def test_global_cost_and_feasible_joint_worlds_matter_to_separation():
    worlds = [dict(a=False,b=False), dict(a=True,b=True)]
    batches = [dict(id='a', fields=['a'], cost=1), dict(id='b', fields=['b'], cost=2), dict(id='all', fields=['a','b'], cost=10)]
    r = minimum_separating_batch(worlds, [0,1], batches)
    assert r['selected'] == ['a'] and r['cost'] == 1
    assert minimum_separating_batch(worlds, [0,0], batches)['selected'] == []
    assert minimum_separating_batch(worlds, [0,1], [])['status'] == 'unseparable'
    with pytest.raises(ContractError):
        minimum_separating_batch([], [], batches)
