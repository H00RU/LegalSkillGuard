import pytest
from legal_skill_guard.rr.semantic_contracts import ContractError
from legal_skill_guard.rr.source_obligations import compile_module, verify, bind_and_assess


def sample(expression='min(100,x)'):
    return dict(inputs=[dict(name='x', type='integer', meaning='input amount', origin='case', quote='amount')],
        output_type='integer', domain='x >= 0', domain_quote='amount', expression=expression,
        rule_quote='Output shall not exceed100.', obligations=[dict(name='cap', condition='True', assertion='result <= 100', quote='Output shall not exceed100.')], unresolved=[])


def test_source_obligation_finds_unseen_domain_failure_without_reference_program():
    module = compile_module(sample('x'), 'An amount. Output shall not exceed100.')
    result = verify(module)
    assert result['obligations'][0]['status'] == 'refuted'
    assert result['obligations'][0]['witness']['x'] > 100
    assert not result['source_coverage_or_NL_faithfulness_proved']


def test_unknown_fields_remain_symbolic_and_can_leave_claim_unresolved():
    module = compile_module(sample(), 'An amount. Output shall not exceed100.')
    assert verify(module)['all_supplied_obligations_verified']
    assert bind_and_assess(module, {'x':None}, 100)['answer'] is None
    assert bind_and_assess(module, {'x':101}, 100)['answer'] == 'Entailment'
    assert bind_and_assess(module, {'x':22}, 100)['answer'] == 'Contradiction'


def test_vacuous_obligation_not_counted_as_verified():
    raw = sample(); raw['obligations'][0]['condition'] = 'x < 0'
    result = verify(compile_module(raw, 'An amount. Output shall not exceed100.'))
    assert not result['all_supplied_obligations_verified']


def test_quote_mismatch_result_free_assertion_and_inconsistent_binding_rejected():
    raw = sample()
    with pytest.raises(ContractError):
        compile_module(raw, 'Some unrelated source.')
    raw['obligations'][0]['assertion'] = 'x >= 0'
    with pytest.raises(ContractError):
        compile_module(raw, 'An amount. Output shall not exceed100.')
    module = compile_module(sample(), 'An amount. Output shall not exceed100.')
    with pytest.raises(ContractError):
        bind_and_assess(module, {'x':-1}, 0)
