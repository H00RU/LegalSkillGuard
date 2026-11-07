"""Frontend regressions; round trips are engineering checks, not learning evidence."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from legal_skill_guard.rr.coverage import Unsupported, digest
from legal_skill_guard.rr.ir_types import IRTypeError
from legal_skill_guard.rr.interfaces import InterfaceError
from legal_skill_guard.rr.scoped_program import compile_query
from legal_skill_guard.rr.source_bindings import decode_source_bindings
from legal_skill_guard.rr.source_code import (
    GRAPHS, SourceCodeError, compiler_response_schema, decode_compiler_response,
    parse_source_code, render_source_code, encode_compiler_program,
)
from legal_skill_guard.rr.source_execution import accept_followup, assess_source, prepare_followup
from legal_skill_guard.rr.source_program import compile_source, source_theory


def program(query=None):
    return {'bindings': [], 'observations': [], 'rule_residuals': [], 'nodes': [],
            'scopes': [], 'clauses': [], 'query': query}


def op(name, *args):
    return {'op': name, 'args': list(args)}


def actual():
    return json.loads((Path(__file__).parent / 'fixtures/rr_scope_v5_binding_projection.json').read_text())


def test_actual_paid_scope_program_roundtrip_preserves_full_theory_and_real_A_selection():
    record = actual()
    original = deepcopy(record['canonical_program'])
    code = render_source_code(original)
    restored = parse_source_code(code)
    assert restored == original == record['canonical_program']
    before = compile_source(record['source'], original)
    after = compile_source(record['source'], restored)
    assert digest(source_theory(before, record['observed'])) == digest(source_theory(after, record['observed']))
    assert source_theory(after, record['observed']).version == record['original_after_theory_hash']
    tokenize = lambda messages, **kwargs: {'count': len(json.dumps(messages))}
    request = prepare_followup(after, compilation='answer_separating', tokenize=tokenize,
        request_config={'context_tokens': 100000, 'max_tokens': 8192}, thinking=False)
    assert request['names'] == ['b_legally_separated'] and request['selected'] == ['s10']
    compiled, observed = accept_followup(after, request, {'observations': [{
        'name': 'b_legally_separated', 'value': True,
        'evidence': 'Alice and Bob were legally separated under a decree of divorce on September 16th, 2017.'}]})
    result = assess_source(compiled, observed)
    assert result['status'] == 'completion_stable'
    assert result['certificate']['completion_count'] == 4096
    assert len(code.encode()) < len(json.dumps(original, separators=(',', ':')).encode())


@pytest.mark.parametrize('expression', [
    op('if', True, 3, 7), op('not', False), op('xor', True, False),
    op('eq', 2, 3), op('ne', 2, 3), op('lt', 2, 3), op('le', 2, 3),
    op('sub', 7, 3), op('scale', 2, 3), op('divide_constant', 7, 3),
    op('ceil_divide_constant', 7, 3), op('number_at', op('array', 7, 3), 1),
    op('min', 7, 3), op('max', 7, 3), op('and', True, False),
    op('or', True, False), op('add', 2, 3), op('array', 2, 3),
    op('pair', 'field', 7), op('object', op('pair', 'field', 7)),
    op('concat', op('array', 2), op('array', 3)),
    op('and'), op('and', True), op('or'), op('or', False), op('add'),
])
def test_all_existing_expression_operators_roundtrip_and_execute_identically(expression):
    before = program(expression)
    after = parse_source_code(render_source_code(before))
    assert before == after
    assert compile_query([], before['query'], {}).evaluate({}) == compile_query([], after['query'], {}).evaluate({})


def test_familiar_syntax_lowers_without_python_coercion_or_native_defaults():
    ir = parse_source_code('''
x = integer(7, sources=['s0'])
b_ok = observation(entity='Alice', entity_source='s1', predicate='is licensed', predicate_source='s0')
less = x < 10
cost = 2 * (x - 3)
query = {'fee': cost, 'eligible': (b_ok and less)}
''')
    assert ir['observations'][0]['name'] == 'b_ok' and 'value' not in ir['observations'][0]
    assert ir['nodes'][1]['body'] == op('scale', 2, op('sub', {'var': 'x'}, 3))
    assert ir['query'] == op('object', op('pair', 'fee', {'var': 'cost'}),
                             op('pair', 'eligible', op('and', {'var': 'b_ok'}, {'var': 'less'})))


@pytest.mark.parametrize('name,params', [
    ('bind_rename', {'from': ['x'], 'to': ['y']}), ('join_on', {'keys': ['x']}),
    ('project_exists', {}), ('group_by', {'keys': ['x']}),
    ('map', {'primitive': 'exists'}), ('fold_reduce', {'primitive': 'all'}),
    ('thread_allowance', {'bank_slot': 'bank', 'key_slot': 'key'}),
])
def test_all_seven_graph_operators_preserve_exact_input_and_parameter_slots(name, params):
    graph = {'op': name, 'inputs': [{'slot': 'left'}] * GRAPHS[name], 'params': params}
    ir = program({'var': 'result'})
    ir['nodes'] = [{'name': 'result', 'kind': 'connector', 'body': {'graph': graph, 'project': 'identity'}}]
    assert parse_source_code(render_source_code(ir)) == ir


@pytest.mark.parametrize('projection', ['identity', 'amount_value', 'amount_values', 'entailment_label'])
def test_projections_and_stored_pattern_invocations_remain_explicit(projection):
    graph = {'pattern': 'a' * 64, 'variant': 0, 'slots': {'s0': 'input'}, 'columns': {'c0': 'person'}}
    ir = program({'var': 'result'})
    ir['nodes'] = [{'name': 'result', 'kind': 'connector', 'body': {'graph': graph, 'project': projection}}]
    restored = parse_source_code(render_source_code(ir))
    assert restored == ir
    with pytest.raises(InterfaceError, match='pattern'):
        compile_query(restored['nodes'], restored['query'], {'input': True})


def test_numeric_vector_projection_threads_the_one_bank_once():
    from legal_skill_guard.rr.interfaces import AllowanceBank, Amount
    key = ('rule', 'owner', 'period')
    bank = AllowanceBank()
    bank.create(key, 100, policy='input_order', order_observable=True)
    inputs = {'bank': bank, 'key': key,
              'items': [Amount(n, 'USD', 'owner', 'period', frozenset({str(i)}), 'element')
                        for i, n in enumerate((80, 70))]}
    ir = parse_source_code('''
remaining = amount_values(thread_allowance(items, params={'bank_slot':'bank', 'key_slot':'key'}))
query = [remaining[0], remaining[1]]
''')
    query = compile_query(ir['nodes'], ir['query'], inputs)
    result = query.execute(inputs)
    assert result['answer'] == [0, 50] and result['executed_nodes'] == ['remaining']
    assert bank.__rr_state__()['events'] == []


def test_actual_stored_B1_graph_keeps_explicit_execution_trace_after_roundtrip():
    from legal_skill_guard.rr.interfaces import Relation
    root = Path(__file__).resolve().parents[1]
    saved = json.loads((root / 'artifacts/rr_v2_formal_build_20261106/run_citation_fix/B1.frozen.json').read_text())
    library = saved['content']
    assert digest(library) == saved['sha256']
    item = library['patterns'][0]
    assert item['pattern']['fields'] == ['entity_equality']
    graph = {'op':'project_exists', 'params':{}, 'inputs':[{
        'pattern':item['pattern_hash'], 'variant':0,
        'slots':{'slot0':'left', 'slot1':'right'}, 'columns':{'column0':'person'}}]}
    ir = program({'var':'joined'})
    ir['nodes'] = [{'name':'joined', 'kind':'connector', 'body':{'graph':graph, 'project':'identity'}}]
    restored = parse_source_code(render_source_code(ir))
    assert restored == ir
    for right in [('Harry',), ('Dave',)]:
        # Witness strings already occur in the original public source; these
        # two offline graph inputs are not a new labelled legal source/view.
        inputs = {'left':Relation(('person',), (('Dave',),)),
                  'right':Relation(('person',), (right,))}
        before = compile_query(ir['nodes'], ir['query'], inputs, library=library).execute(inputs)
        after = compile_query(restored['nodes'], restored['query'], inputs, library=library).execute(inputs)
        assert before == after
        assert len(after['pattern_uses']) == 1
        assert after['pattern_uses'][0]['pattern_hash'] == item['pattern_hash']
        assert after['pattern_uses'][0]['status'] == 'executed_main_program'
    assert digest(library) == saved['sha256']


def test_inline_bindings_are_fresh_and_resource_clones_still_fail():
    code = """query = [allowance_bank([{'key':['rule','owner','period'],'balance':100,'policy':'input_order','order_observable':True}], sources=['s0']), allowance_bank([{'key':['rule','owner','period'],'balance':100,'policy':'input_order','order_observable':True}], sources=['s0'])]"""
    ir = parse_source_code(code)
    assert len(ir['bindings']) == 2 and ir['bindings'][0]['name'] != ir['bindings'][1]['name']
    with pytest.raises(ValueError, match='cloned'):
        decode_source_bindings(ir['bindings'], {'s0': 'rule owner period 100'})


def test_actual_bad_bindings_cannot_be_recovered_by_rendering():
    record = actual()
    bad = deepcopy(record['canonical_program'])
    bad['bindings'][0]['value'] = 900000000
    restored = parse_source_code(render_source_code(bad))
    assert restored == bad
    with pytest.raises((ValueError, Unsupported), match='grounding'):
        compile_source(record['source'], restored)


def test_real_v4_failure_is_not_made_valid_by_the_frontend():
    record = json.loads((Path(__file__).parent / 'fixtures/rr_actual_probe_v4_expressions.json').read_text())
    raw = record['raw_content']
    # Actual malformed if arities cannot be rendered as a well-formed ternary.
    # No operand, source witness or unknown rule is supplied by this frontend.
    with pytest.raises(SourceCodeError, match='malformed expression'):
        render_source_code(json.loads(raw))
    assert record['raw_content'] == raw


@pytest.mark.parametrize('code', [
    'import os\nquery = 1', 'x = __import__("os")\nquery = x',
    'query = object.__subclasses__()', 'query = (lambda: 1)()',
    'query = [x for x in [1]]', 'x = 1\nx = 2\nquery = x',
    'query = 1\nx = 2', 'query = 1\nquery = 2', 'x = 1',
    'query = 2.5', 'query = 2 ** 3', 'query = {"x": 1, "x": 2}',
    'query = integer(1, value=2, sources=["s0"])',
    'query = integer(1, sources=["s0"], unknown=True)',
    'query = integer(1, sources=["s0"], **{})',
    'query = integer(1, sources=None, sources=["s0"])',
    'query = project_exists(x, params={}, params={})',
    'query = [1, 2][-1]', 'query = [1, 2][True]', 'query = 1 / 0',
    'query = x * 2', 'query = True * 2', 'query = a < b < c',
    'query = {**{}}', 'query = add(*[1, 2])', 'query = a.b',
])
def test_unsupported_python_ambiguous_fields_and_missing_semantics_are_rejected(code):
    with pytest.raises(SourceCodeError):
        parse_source_code(code)


def test_unchosen_wrong_branch_still_fails_existing_all_branch_type_check():
    ir = parse_source_code('query = (1 if True else (not 4))')
    with pytest.raises(IRTypeError):
        compile_query(ir['nodes'], ir['query'], {})


def test_current_wire_constrains_declarations_and_rejects_legacy_envelopes_or_side_answers():
    from jsonschema import ValidationError
    from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues
    record = actual(); source = record['source']; ir = record['canonical_program']
    schema = compiler_response_schema(source)
    assert strict_output_schema_issues(schema) == []
    encoded = encode_compiler_program(ir)
    assert decode_compiler_response(encoded, source) == ir
    assert list(schema['properties'])[:2] == ['scopes', 'clauses']
    for response in [ir, {'code':render_source_code(ir)}, {**encoded, 'answer':7}, {}]:
        with pytest.raises(ValidationError):
            decode_compiler_response(response, source)


def test_actual_v1_code_failure_preserves_raw_bytes_and_precise_syntax_location():
    import hashlib
    record=json.loads((Path(__file__).parent/'fixtures/rr_actual_source_code_v1.json').read_text())
    raw=record['raw_content']
    assert hashlib.sha256(raw.encode()).hexdigest()==record['raw_content_sha256']
    assert record['finish_reason']=='stop' and record['usage']['completion_tokens']==74
    with pytest.raises(SourceCodeError) as caught:
        parse_source_code(json.loads(raw)['code'])
    diagnostic=caught.value.diagnostics[0]
    assert diagnostic['line']==1 and diagnostic['column']>0
    assert diagnostic['expected']=='syntactically valid declarative assignments'
    assert diagnostic['actual']=="unmatched ')'"


@pytest.mark.parametrize('expression',[
    "clause(sources=['s0'], value=True, otherwise=False)",
    "scope(source='s0', condition=True)", "contradiction()",
    "project_exists(join_on('s10'))", "project_exists('s10')",
])
def test_actual_v1_API_misuses_remain_rejected_without_inventing_missing_operands(expression):
    with pytest.raises(SourceCodeError) as caught:
        parse_source_code('query = '+expression)
    assert caught.value.diagnostics[0]['path']=='code'
