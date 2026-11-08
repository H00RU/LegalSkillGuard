"""Real declaration failures and unchanged semantic gates for the compact wire."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from jsonschema import ValidationError
import pytest

from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.ir_types import IRTypeError
from legal_skill_guard.rr.source_code import (
    SourceCodeError, compiler_response_schema, decode_compiler_response,
    encode_compiler_program, parse_source_code,
)
from legal_skill_guard.rr.source_execution import assess_source, prepare_followup
from legal_skill_guard.rr.source_program import compile_source, source_theory
from legal_skill_guard.rr.wire_validation import validate_wire


ROOT = Path(__file__).resolve().parents[1]


def paid_case():
    return json.loads((ROOT/'tests/fixtures/rr_scope_v5_binding_projection.json').read_text())


def test_paid_translation_roundtrip_preserves_ir_full_theory_and_real_A_batch():
    case=paid_case(); source=case['source']; original=case['canonical_program']
    restored=decode_compiler_response(encode_compiler_program(original),source)
    assert restored==original
    before=compile_source(source,original); after=compile_source(source,restored)
    assert digest(source_theory(before,case['observed']))==digest(source_theory(after,case['observed']))
    assert assess_source(after,case['observed'])==assess_source(before,case['observed'])
    request=prepare_followup(after,compilation='answer_separating',
        tokenize=lambda *a,**k:{'count':100},request_config={'context_tokens':32768,'max_tokens':8192},thinking=False)
    assert request['selected']==['s10'] and request['names']==['b_legally_separated']


@pytest.mark.parametrize('index',range(5))
def test_recorded_wrong_fact_rule_provenance_is_rejected_by_generation_schema(index):
    case=json.loads((ROOT/'tests/fixtures/rr_actual_code_declaration_failures.json').read_text())['records'][index]
    assert hashlib.sha256(case['raw_content'].encode()).hexdigest()==case['raw_sha256']
    source=next(s for s in json.loads((ROOT/'data/packets/rr_v2/public_train.json').read_text())['sources']
                if s['key']==case['source'])
    raw=json.loads(case['raw_content']); original=parse_source_code(raw['code'])
    observation=deepcopy(original['observations'][0])
    # Isolate provenance from the independent naming failure. This does not
    # alter a prediction, execute a program, or restore missing semantics.
    observation['name']='b_header_diagnostic'
    with pytest.raises(ValidationError) as caught:
        validate_wire(observation,compiler_response_schema(source)['properties']['observations']['items'])
    assert list(caught.value.path)==case['field_path'][2:]
    with pytest.raises(ValidationError):
        decode_compiler_response(raw,source)


@pytest.mark.parametrize('expression',[
    'integer(3, sources=["s0"])', 'observation(entity="Alice", entity_source="s10", predicate="x", predicate_source="s0")',
    'residual(source="s0", quote="x")', 'scope(source="s0", condition=True)',
    'clause(sources=["s0"], value=True, otherwise=False)', '__import__("os")', 'x.__class__',
])
def test_expression_fragments_cannot_hide_declarations_or_arbitrary_python(expression):
    case=paid_case(); encoded=encode_compiler_program(case['canonical_program'])
    encoded['nodes'].append({'name':'bad_fragment','kind':'expression','code':expression})
    with pytest.raises(SourceCodeError) as caught:
        decode_compiler_response(encoded,case['source'])
    assert caught.value.diagnostics[0]['path']==f'nodes[{len(encoded["nodes"])-1}].code'


def test_unchosen_wrong_scope_branch_is_still_rejected_by_real_IR_type_checker():
    case=paid_case(); encoded=encode_compiler_program(case['canonical_program'])
    encoded['scopes'][0]['condition_code']='(True if True else 7)'
    restored=decode_compiler_response(encoded,case['source'])
    with pytest.raises((ValidationError, IRTypeError)):
        compile_source(case['source'],restored)


def test_fragment_syntax_error_retains_its_exact_field_location():
    case=paid_case(); encoded=encode_compiler_program(case['canonical_program'])
    encoded['clauses'][0]['value_code']='(True))'
    with pytest.raises(SourceCodeError) as caught:
        decode_compiler_response(encoded,case['source'])
    d=caught.value.diagnostics[0]
    assert d['path']=='clauses[0].value_code' and d['line']==1 and d['column']>0


def test_lifted_graph_temporary_cannot_capture_an_unbound_query_name():
    case=paid_case(); encoded=encode_compiler_program(case['canonical_program'])
    encoded['query']={'var':'_inline_0'}
    encoded['nodes'].append({'name':'probe','kind':'expression','code':'project_exists(unknown_input)'})
    restored=decode_compiler_response(encoded,case['source'])
    assert restored['query']=={'var':'_inline_0'}
    assert not any(n['name']=='_inline_0' for n in restored['nodes'])
    assert any(n['name']=='_inline_1' for n in restored['nodes'])


def test_boolean_native_query_and_whole_rule_residual_remain_invalid():
    case=paid_case(); encoded=encode_compiler_program(case['canonical_program'])
    encoded['query']=True
    with pytest.raises(ValidationError):decode_compiler_response(encoded,case['source'])
    # A wire round trip cannot turn an untranslated whole rule into a proper
    # residual. The exact same compile_source correctness check still runs.
    original=deepcopy(case['canonical_program'])
    from legal_skill_guard.rr.source_structure import inspect_source
    structure=inspect_source(case['source'])
    hole=original['rule_residuals'][0]
    clause=next(c for c in structure.ledger.clauses if c.id==hole['source'])
    hole['quote']=structure.ledger.text[clause.start:clause.end]
    restored=decode_compiler_response(encode_compiler_program(original),case['source'])
    from legal_skill_guard.rr.coverage import Unsupported
    with pytest.raises(Unsupported):compile_source(case['source'],restored)


def test_actual_first_compact_response_is_complete_but_not_executable_or_semantically_repaired():
    recorded=json.loads((ROOT/'tests/fixtures/rr_actual_compact_contract_v1.json').read_text())
    raw=recorded['raw_content']
    assert hashlib.sha256(raw.encode()).hexdigest()==recorded['raw_content_sha256']
    source=next(s for s in json.loads((ROOT/'data/packets/rr_v2/public_train.json').read_text())['sources']
                if s['key']==recorded['source'])
    response=json.loads(raw); validate_wire(response,compiler_response_schema(source))
    ir=decode_compiler_response(response,source)
    assert ir['clauses'][0]['value']['args'][0]['op']=='array'
    with pytest.raises(ValidationError):compile_source(source,ir)
    from legal_skill_guard.rr.source_validation import validation_feedback
    feedback=validation_feedback(source,ir)
    # Keep the paid historical feedback unchanged. The current diagnostic
    # adds precise operative-scope errors; it must retain every old error.
    assert {k:v for k,v in feedback.items() if k!='issues'}=={
        k:v for k,v in recorded['feedback'].items() if k!='issues'}
    assert all(issue in feedback['issues'] for issue in recorded['feedback']['issues'])
    added=[i for i in feedback['issues'] if i not in recorded['feedback']['issues']]
    assert added and all(
        i['expected'].startswith('executable source condition;') and i['actual']['source_text'] or
        i['path']=='query' and i['expected']=='root rule dependencies include the explicitly requested public section'
        and i['actual']['target']['reference']=='7703(a)(2)' for i in added)
    from legal_skill_guard.rr.source_program import compiler_prompt
    system,user=compiler_prompt(source,validation_feedback=recorded['feedback'])
    assert 'Use the actual JSON AST' in system
    assert json.loads(user)['validation_feedback']==recorded['feedback']
    assert 'Entailment' not in json.dumps(recorded['feedback'])
