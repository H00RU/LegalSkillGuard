"""Regress the actual unbounded wire failure without generating model output."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from jsonschema import ValidationError
import pytest

from legal_skill_guard.rr.grounding import binding_literal_audit
from legal_skill_guard.rr.source_program import compiler_prompt,program_schema
from legal_skill_guard.rr.source_structure import inspect_source
from legal_skill_guard.rr.strict_contract import EXPRESSION_DEPTH
from legal_skill_guard.rr.wire_validation import validate_wire


def actual():
    root=Path(__file__).resolve().parents[1]
    fixture=json.loads((root/'tests/fixtures/rr_actual_method_c3_depth.json').read_text())
    source=next(s for s in json.loads((root/'data/packets/rr_v2/public_train.json').read_text())['sources']
                if s['key']==fixture['source'])
    return source,fixture


def test_actual_wire_retains_the_parser_failure_and_exact_raw_bytes():
    _,fixture=actual();raw=fixture['raw_content']
    assert hashlib.sha256(raw.encode()).hexdigest()==fixture['raw_content_sha256']
    assert fixture['result']['finish_reason']=='length'
    with pytest.raises(RecursionError):json.loads(raw)
    depth=maximum=0;quoted=escaped=False
    for char in raw:
        if quoted:
            if escaped:escaped=False
            elif char=='\\':escaped=True
            elif char=='"':quoted=False
        elif char=='"':quoted=True
        elif char in '{[':depth+=1;maximum=max(maximum,depth)
        elif char in '}]':depth-=1
    assert maximum==1301 and depth==1301


@pytest.mark.parametrize('kind',['expr','bool_expr','connector'])
@pytest.mark.parametrize('depth',[0,1,EXPRESSION_DEPTH,EXPRESSION_DEPTH+1])
def test_named_node_wire_has_a_finite_child_depth_but_accepts_legal_boundaries(kind,depth):
    source,_=actual();wire=program_schema(source)
    value={'slot':'witnesses'} if kind=='connector' else {'var':'guard'}
    for _ in range(depth):
        value={'op':'project_exists','inputs':[value],'params':{}} if kind=='connector' else \
            {'op':'not','args':[value]}
    schema={'$ref':'#/$defs/'+kind,'$defs':wire['$defs']}
    if depth>EXPRESSION_DEPTH:
        with pytest.raises(ValidationError):validate_wire(value,schema)
    else:validate_wire(value,schema)


def test_actual_fact_truth_cannot_become_a_boolean_or_numeric_public_binding():
    source,_=actual();wire=program_schema(source)
    text=inspect_source(source).ledger.text
    schema={'$ref':'#/$defs/binding','$defs':wire['$defs']}
    for kind,value in [('scalar',True),('scalar',False),('scalar',1),('integer',1),('rational','1'),
                       ('amount',{'value':1,'unit':'x','owner':'cat','period':'x','lineage':['x'],'stage':'element'})]:
        assert not binding_literal_audit(kind,value,text,set())['pass']
        with pytest.raises(ValidationError):
            validate_wire({'name':'input','type':kind,'value':value,'sources':['s1']},schema)
    validate_wire({'name':'fact_text','type':'scalar','value':'The cat is blue.','sources':['s1']},schema)
    _,user=compiler_prompt(source);contract=json.loads(user)['language_contract']
    assert contract['binding_value_schemas']=={arm['properties']['type']['enum'][0]:arm['properties']['value']
                                              for arm in wire['$defs']['binding']['anyOf']}


def test_only_explicit_public_boolean_values_are_enabled_without_inferring_truth():
    source,_=actual();source=deepcopy(source)
    source['public']['facts'].append('A literal flag is false.')
    wire=program_schema(source);schema={'$ref':'#/$defs/binding','$defs':wire['$defs']}
    text=inspect_source(source).ledger.text
    false={'name':'flag','type':'scalar','value':False,'sources':['s14']}
    assert binding_literal_audit('scalar',False,text,set())['pass']
    validate_wire(false,schema)
    with pytest.raises(ValidationError):validate_wire({**false,'value':True},schema)
