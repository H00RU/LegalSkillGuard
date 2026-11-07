"""Source-required numeric primitives; offline execution is not learning evidence."""
from fractions import Fraction
import json
from pathlib import Path

import pytest

from legal_skill_guard.rr.coverage import FiniteTheory,Residual,SourceLedger,Unsupported,complete,evaluate
from legal_skill_guard.rr.grounding import binding_literal_audit,expression_literal_audit
from legal_skill_guard.rr.interfaces import AllowanceBank,Amount
from legal_skill_guard.rr.ir_types import IRTypeError
from legal_skill_guard.rr.scoped_program import compile_query


def op(name,*args):return {'op':name,'args':list(args)}
def var(name):return {'var':name}


@pytest.mark.parametrize('numerator,denominator,expected',[
    (0,2500,0),(2500,2500,1),(2501,2500,2),(-2501,2500,-1),
    (Fraction(5001,2),2500,2),(Fraction(-5001,2),2500,-1)])
def test_upward_division_is_exact_at_both_sides_of_an_increment(numerator,denominator,expected):
    query=compile_query([],op('ceil_divide_constant',var('amount'),denominator),{'amount':numerator})
    assert query.evaluate({'amount':numerator})==expected


@pytest.mark.parametrize('denominator',[0,-1,True,{'var':'denom'}])
def test_upward_division_rejects_invalid_or_dynamic_denominators(denominator):
    with pytest.raises(IRTypeError):
        compile_query([],op('ceil_divide_constant',var('n'),denominator),{'n':1,'denom':2})


def test_original_public_income_increment_can_be_expressed_without_loading_grading():
    public=json.loads((Path(__file__).resolve().parents[1]/'data/packets/rr_v2/public_train.json').read_text())
    source=next(s for s in public['sources'] if s['key']=='SARA_v2_Binary:097568705cac232354a1b0bc169fad14d5b105d2818fdebc5622f304975c747e')
    assert '$276932' in source['public']['facts'] and '$250000' in source['public']['facts']
    assert '$2,500 (or fraction thereof)' in source['public']['rules']
    expression=op('scale',2,op('ceil_divide_constant',op('sub',var('income'),var('threshold')),2500))
    query=compile_query([],expression,{'income':276932,'threshold':250000})
    assert query.evaluate({'income':276932,'threshold':250000})==22
    assert expression_literal_audit(expression,source['public']['rules'],'SARA_v2_Binary')['pass']


def bank_case():
    bank=AllowanceBank();key=('rule','owner','period')
    bank.create(key,100,policy='input_order',order_observable=True)
    amounts=[Amount(v,'USD','owner','period',frozenset({str(i)}),'element') for i,v in enumerate((80,70))]
    inputs={'bank':bank,'key':key,'amounts':amounts}
    node={'name':'remaining','kind':'connector','body':{'graph':{'op':'thread_allowance',
        'inputs':[{'slot':'amounts'}],'params':{'bank_slot':'bank','key_slot':'key'}},'project':'amount_values'}}
    return inputs,node


def test_individual_outputs_share_one_resource_consumption_and_remain_repeatable():
    inputs,node=bank_case()
    query=compile_query([node],op('array',op('number_at',var('remaining'),0),op('number_at',var('remaining'),1)),inputs)
    first=query.execute(inputs);second=query.execute(inputs)
    assert first['answer']==second['answer']==[0,50]
    assert first['executed_nodes']==['remaining']
    assert inputs['bank'].__rr_state__()['events']==[]


@pytest.mark.parametrize('expression',[
    op('number_at',op('array',1,'wrong'),0),
    op('number_at',op('array',1,True),0),
    op('number_at',op('array',1,2),-1),
    op('number_at',op('array',1,2),var('index')),
    op('if',False,op('number_at',op('array','wrong'),0),0)])
def test_inactive_or_dynamic_access_cannot_hide_an_invalid_numeric_vector(expression):
    with pytest.raises(IRTypeError):compile_query([],expression,{'index':0})


def test_out_of_range_access_cannot_produce_a_default_answer_or_certificate():
    inputs,node=bank_case();query=compile_query([node],op('number_at',var('remaining'),2),inputs)
    with pytest.raises(Unsupported,match='in-range'):query.evaluate(inputs)
    ledger=SourceLedger.from_text('accepted arithmetic fixture')
    theory=FiniteTheory(ledger,inputs,{},query,[Residual('s0',(),'accepted_translation',False)])
    assert complete(theory).status=='unsupported_no_certificate'


def test_public_unit_conversions_are_scoped_to_their_denominator_operand():
    text='The rate is 7 percent; the alternative is one-half of the amount.'
    assert expression_literal_audit(op('divide_constant',var('amount'),100),text,'RuleArena_Airline')['pass']
    assert expression_literal_audit(op('divide_constant',var('amount'),2),text,'RuleArena_Airline')['pass']
    assert not expression_literal_audit(op('add',var('amount'),100),text,'RuleArena_Airline')['pass']
    assert not expression_literal_audit(op('divide_constant',var('amount'),100),'Rate is 7.','RuleArena_Airline')['pass']
    assert binding_literal_audit('rational','1/2',text,set())['pass']
    assert not binding_literal_audit('integer',100,text,set())['pass']


def test_structural_indices_are_not_licensed_as_factual_numbers():
    text='Three asset values are supplied elsewhere.'
    audit=expression_literal_audit(op('number_at',var('values'),2),text,'OpenExempt')
    assert audit['pass'] and audit['structural_numeric_vector_indices'][0]['index']==2
    assert not expression_literal_audit(op('add',var('value'),2),text,'OpenExempt')['pass']


def test_numeric_vector_constructor_and_concatenation_preserve_safe_element_types():
    expr=op('number_at',op('concat',op('array',1,2),op('array',3)),2)
    query=compile_query([],expr,{})
    assert query.evaluate({})==3
    with pytest.raises(Unsupported):evaluate(op('number_at',var('values'),0),{'values':[True]})
