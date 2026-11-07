"""Existing pair/numeric-vector type checks also constrain generated syntax."""
import json
from pathlib import Path

from jsonschema import ValidationError
import pytest

from legal_skill_guard.rr.compiler_contract import compiler_response_schema
from legal_skill_guard.rr.ir_types import IRTypeError,check_expression
from legal_skill_guard.rr.wire_validation import validate_wire


ROOT=Path(__file__).resolve().parents[1]


def schema():
    case=json.loads((ROOT/'tests/fixtures/rr_scope_v5_binding_projection.json').read_text())
    return compiler_response_schema(case['source'])


def validate(expression,spec):
    validate_wire(expression,{'$defs':spec['$defs'],'$ref':'#/$defs/expr'})


def operation(op,*args):return {'op':op,'args':list(args)}


@pytest.mark.parametrize('expression',[
    operation('pair',operation('pair','key',1),2),
    operation('pair',17,2),
    operation('number_at',operation('array','s10'),0),
    operation('number_at',operation('array',operation('pair','key',1)),0),
    operation('number_at',operation('array'),0),
    operation('number_at',operation('if',True,operation('array',1),'s10'),0),
])
def test_schema_rejects_only_operand_types_already_rejected_by_the_engine(expression):
    with pytest.raises(IRTypeError):check_expression({'query':expression},{})
    with pytest.raises(ValidationError):validate(expression,schema())


@pytest.mark.parametrize('expression',[
    operation('pair',operation('if',{'var':'b'},'left','right'),{'var':'x'}),
    operation('pair',{'var':'key'},None),
    operation('number_at',{'var':'vec'},0),
    operation('number_at',operation('array',operation('scale',2,{'var':'x'}),operation('divide_constant',6,2)),0),
    operation('number_at',operation('if',{'var':'b'},operation('array',1),operation('array',2)),0),
    operation('number_at',operation('concat',operation('array',1),operation('array',2)),0),
])
def test_symbolic_and_nested_well_typed_operands_remain_supported(expression):
    types={'b':{'boolean'},'key':{'string'},'x':{'number'},'vec':{'numbers'}}
    check_expression({'query':expression},{},slot_types=types)
    validate(expression,schema())


def test_actual_paid_scope_loop_was_wire_valid_but_has_engine_invalid_operands():
    old_case=json.loads((ROOT/'tests/fixtures/rr_actual_ast_scope_v1.json').read_text())
    # The old paid scope AST is a complete JSON value inside the incomplete
    # response. It is tested alone, never completed into a candidate program.
    raw=old_case['raw_content'];pos=raw.index(':',raw.index('"scopes"'))+1
    scopes,_=json.JSONDecoder().raw_decode(raw,pos+len(raw[pos:])-len(raw[pos:].lstrip()))
    expression=scopes['s0']['condition']
    old=json.loads((ROOT/'artifacts/rr_method_runtime_20261107/executor_ast_scope_v1_20261107/seal.json').read_text())['schema']
    validate(expression,old)
    with pytest.raises(IRTypeError):check_expression({'query':expression},{})
    with pytest.raises(ValidationError):validate(expression,schema())


def test_actual_paid_input_first_node_loop_is_rejected_without_resolving_its_forward_variables():
    case=json.loads((ROOT/'tests/fixtures/rr_actual_ast_input_first_v1.json').read_text())
    raw=case['raw_content'];pos=raw.index('[',raw.index('"nodes"'))+1
    pos+=len(raw[pos:])-len(raw[pos:].lstrip())
    node,_=json.JSONDecoder().raw_decode(raw,pos)
    old=json.loads((ROOT/'artifacts/rr_method_runtime_20261107/executor_ast_input_first_v1_20261107/seal.json').read_text())['schema']
    validate(node['body'],old)
    with pytest.raises(ValidationError):validate(node['body'],schema())
    assert case['complete_JSON'] is False


def test_native_numeric_root_uses_the_same_numeric_vector_contract():
    sources=json.loads((ROOT/'data/packets/rr_v2/public_train.json').read_text())['sources']
    source=next(s for s in sources if s['dataset']=='RuleArena_Airline')
    spec=compiler_response_schema(source)
    root={'$defs':spec['$defs'],'$ref':'#/$defs/result_expr'}
    validate_wire(operation('number_at',operation('array',1,2),0),root)
    with pytest.raises(ValidationError):validate_wire(operation('number_at',operation('array','s0'),0),root)
