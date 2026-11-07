"""Actual source IR replay and request semantics; no new model/reference calls."""
from copy import deepcopy
from fractions import Fraction
import json
from pathlib import Path

import pytest

from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues
from legal_skill_guard.rr.coverage import Unsupported,digest
from legal_skill_guard.rr.source_execution import accept_followup,assess_source,exact_native,prepare_followup
from legal_skill_guard.rr.source_program import compile_source,observation_request
from legal_skill_guard.rr.wire_validation import validate_wire


def actual_case():
    root=Path(__file__).resolve().parents[1]
    record=json.loads((root/'tests/fixtures/rr_scope_v5_binding_projection.json').read_text())
    return compile_source(record['source'],record['canonical_program'])


def count(messages,*,thinking):
    assert thinking is False
    return {'count':len(json.dumps(messages,ensure_ascii=False))}


def prepare(compiled,*,policy='answer_separating',observed=None,tokenize=count,context=100000):
    return prepare_followup(compiled,observed,compilation=policy,tokenize=tokenize,
        request_config={'context_tokens':context,'max_tokens':8192},thinking=False)


def test_real_source_A_selects_only_the_separating_fact_and_dispatches_exact_payload():
    compiled=actual_case();before=digest(compiled['program']);request=prepare(compiled)
    assert request['kind']=='factual_observation' and request['joint_separation_complete']
    assert request['names']==['b_legally_separated'] and request['selected']==['s10']
    assert request['messages']==observation_request(compiled,request['names'])[0]
    assert request['input_tokens']==request['batch_plan']['cost']==count(request['messages'],thinking=False)['count']
    updated,observed=accept_followup(compiled,request,{'observations':[{'name':'b_legally_separated',
        'value':True,'evidence':'Alice and Bob were legally separated under a decree of divorce on September 16th, 2017.'}]})
    result=assess_source(updated,observed)
    assert result['status']=='completion_stable' and len(result['unresolved'])==12
    assert result['certificate']['completion_count']==4096
    assert not result['certificate']['natural_language_faithfulness_proven']
    assert digest(compiled['program'])==before


def test_full_policy_reads_all_residuals_and_keeps_legal_truth_outside_fact_observation():
    compiled=actual_case();request=prepare(compiled,policy='full')
    assert request['kind']=='joint_rule_translation_and_facts'
    assert {'s5','s6','s7','s8','s10'}<=set(request['selected'])
    assert not set(request['names'])&set(compiled['rule_residuals'])
    payload=json.loads(request['messages'][1]['content'])
    assert 'public_task' not in payload
    assert {u['id'] for u in payload['units']}==set(request['context_closure'])
    assert strict_output_schema_issues(request['schema'])==[]
    response={'program':compiled['program'],'factual_observations':[
        {'name':name,'value':None,'evidence':''} for name in request['names']]}
    validate_wire(response,request['schema'])
    updated,observed=accept_followup(compiled,request,response)
    result=assess_source(updated,observed,compilation='full')
    assert result['status']=='translation_unresolved' and result['answer'] is None


def test_full_policy_does_not_early_stop_on_a_query_stable_partial_translation():
    compiled=actual_case();observed={'b_legally_separated':True}
    assert assess_source(compiled,observed)['status']=='completion_stable'
    full=assess_source(compiled,observed,compilation='full')
    assert full['full_compilation_required'] and full['certificate'] is None and full['answer'] is None


def test_fixed_batch_is_distinct_and_does_not_send_s5_legal_truth_to_the_observer():
    compiled=actual_case();request=prepare(compiled,policy='generic_CEGAR_fixed_batch')
    assert request['selection_basis']=='generic_fixed_one_unit'
    assert request['selected']==['s5'] and request['kind']=='joint_rule_translation_and_facts'
    assert request['names']==[] and request['schema']['properties']['factual_observations']['maxItems']==0
    response={'program':compiled['program'],'factual_observations':[]}
    validate_wire(response,request['schema'])
    assert strict_output_schema_issues(request['schema'])==[]
    updated,observed=accept_followup(compiled,request,response)
    assert observed=={} and updated['rule_residuals']==compiled['rule_residuals']


def test_joint_retranslation_cannot_attach_cached_fact_truth_to_a_changed_entity():
    compiled=actual_case();observed={'b_legally_separated':True}
    request=prepare(compiled,policy='full',observed=observed)
    program=deepcopy(compiled['program'])
    next(o for o in program['observations'] if o['name']=='b_legally_separated')['entity']='Bob'
    response={'program':program,'factual_observations':[
        {'name':name,'value':None,'evidence':''} for name in request['names']]}
    with pytest.raises(Unsupported,match='Changed primitive meaning'):
        accept_followup(compiled,request,response,observed)


def test_request_measurement_mismatch_and_context_overflow_stop_before_dispatch():
    compiled=actual_case();calls=[]
    def unstable(messages,*,thinking):
        calls.append(messages);return {'count':len(calls)}
    with pytest.raises(ValueError,match='token counts differ'):prepare(compiled,policy='full',tokenize=unstable)
    with pytest.raises(Unsupported,match='no truncation'):prepare(compiled,policy='full',context=8193)


def test_exact_native_serialization_never_rounds_a_nonterminating_rational():
    assert exact_native({'v':[Fraction(20165,2),Fraction(7,100),Fraction(6,3)]})=={'v':[10082.5,.07,2]}
    with pytest.raises(Unsupported,match='rounding'):exact_native(Fraction(1,3))
