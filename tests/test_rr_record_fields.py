"""Concrete fee-table access, scope aliases and preserved residual failures."""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
import json
from pathlib import Path
import pytest

from legal_skill_guard.rr.coverage import SourceLedger,FiniteTheory,Residual,Unsupported,complete,evaluate,digest
from legal_skill_guard.rr.ir_types import check_expression,IRTypeError
from legal_skill_guard.rr.pal_frontend import lower_pal
from legal_skill_guard.rr.source_program import compile_source
from legal_skill_guard.rr.source_execution import assess_source
from legal_skill_guard.rr.compiler_templates import validate_template
from test_rr_rule_templates import control

ROOT=Path(__file__).resolve().parents[1]
def op(name,*args):return {'op':name,'args':list(args)}
def var(name):return {'var':name}


def test_numeric_record_field_is_exact_and_has_no_missing_nonnumeric_or_boolean_default():
    expression=op('number_field',var('fees'),var('class'))
    assert check_expression({'query':expression},{'fees':{'Basic':60},'class':'Basic'})['result_types']==['number']
    assert evaluate(expression,{'fees':{'Basic':Fraction(1,2)},'class':'Basic'})==Fraction(1,2)
    for fees in [{},{'Basic':True},{'Basic':'60'},{'Basic':None}]:
        with pytest.raises(Unsupported):evaluate(expression,{'fees':fees,'class':'Basic'})
    for expression in [op('number_field',1,'Basic'),op('number_field',op('object'),0),
            op('if',False,op('number_field',op('array',1),'Basic'),0)]:
        with pytest.raises(IRTypeError):check_expression({'query':expression},{})


def test_a_missing_field_in_one_completion_prevents_a_certificate():
    ledger=SourceLedger.from_text('Fee schedule\nUnresolved applicability')
    ledger.clauses[0]=replace(ledger.clauses[0],state='compiled')
    record=op('if',var('enabled'),op('object',op('pair','Basic',60)),op('object'))
    query=op('number_field',record,'Basic')
    check_expression({'query':query},{},slot_types={'enabled':{'boolean'}})
    theory=FiniteTheory(ledger,{}, {'enabled':(False,True)},query,[Residual('s1',('enabled',),'public_structure',False)])
    result=complete(theory)
    assert result.status=='unsupported_no_certificate' and 'existing string field' in result.reason


def paid_numeric_program():
    stage=ROOT/'artifacts/rr_method_runtime_20261107/reference_pal_teacher_airline2_v13_20261108'
    source=json.loads((stage/'seal.json').read_text())['source']
    paid=json.loads((stage/'calls'/digest(stage.name+':compile')/'result.json').read_text())
    return source,lower_pal(source,paid['value']['code'])[0]


def test_actual_numeric_partial_program_keeps_all_operative_unknown_sources_and_no_answer():
    source,program=paid_numeric_program();compiled=compile_source(source,program)
    result=assess_source(compiled)
    assert result['status']=='translation_unresolved' and result['answer'] is None
    assert set(result['unknown_scope'])=={'s22','s23','s39','s40','s54','s55','s61','s62',
        's126','s127','s130','s131','s139','s140','s148'}
    assert 'oversize_panama_south_america_fees' in compiled['numeric_field_only_record_nodes']
    path=ROOT/'artifacts/rr_method_runtime_20261107/reference_frontend_prior_airline2_partial_v14_20261108/compiler_template.json'
    assert assess_source(validate_template(json.loads(path.read_text())))==result


def test_internal_field_addresses_cannot_hide_invented_values_or_escape_as_output_keys():
    source,program=paid_numeric_program()
    changed=deepcopy(program);changed['query']=var('oversize_panama_south_america_fees')
    with pytest.raises(Unsupported,match='Public literal grounding'):compile_source(source,changed)
    changed=deepcopy(program);row=next(c for c in changed['clauses'] if c['name']=='oversize_panama_south_america_fees')
    row['value']['args'][1]['args'][0]['args'][1]=999999
    with pytest.raises(Unsupported,match='Public literal grounding'):compile_source(source,changed)


def test_pure_alias_preserves_a_guarded_rule_but_cannot_hide_scope_bypass():
    source,_,_,program,compiled,_=control()
    alias={'name':'local_alias','kind':'expression','body':var('enrolled_student_condition')}
    wrapped=deepcopy(program);wrapped['nodes'].append(alias);wrapped['query']['args'][0]=var('local_alias')
    updated=compile_source(source,wrapped)
    for school in (False,True):
        for student in (False,True):
            observed={'b_school_service':school,'b_enrolled_student':student}
            actual=assess_source(updated,observed);original=assess_source(compiled,observed)
            assert (actual['status'],actual['answer'],actual['projection'])==(original['status'],original['answer'],original['projection'])
            assert actual['certificate']['completion_count']==original['certificate']['completion_count']
    wrapped['nodes'][-1]['body']=var('educational_service_scope')
    with pytest.raises(Unsupported,match='not bypass'):compile_source(source,wrapped)
    wrapped['nodes'][-1]['body']=var('b_enrolled_student')
    with pytest.raises(Unsupported,match='guarded clause'):compile_source(source,wrapped)
