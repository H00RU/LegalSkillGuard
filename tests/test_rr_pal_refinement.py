"""Actual paid statutes, source-local controls; no fabricated model successes."""
from copy import deepcopy
import json
from pathlib import Path
import pytest

from legal_skill_guard.rr.coverage import Unsupported,digest
from legal_skill_guard.rr.rule_templates import matching_rule_template,instantiate_rule_template
from legal_skill_guard.rr.source_execution import prepare_followup,accept_followup,assess_source

ROOT=Path(__file__).resolve().parents[1]


def current():
    library=json.loads((ROOT/'artifacts/rr_method_runtime_20261107/reference_frontend_prior_sara3_template_v8_20261108/library.frozen.json').read_text())['content']
    source=next(s for s in json.loads((ROOT/'data/packets/rr_v2/public_train.json').read_text())['sources']
        if s['key']=='SARA_v2_Binary:bb6b0bc1f7a04930f30caf8ca1a05613334ce26d79c0b11a3c6e1d25ef197aba')
    _,compiled,_=instantiate_rule_template(source,matching_rule_template(source,library),{
        'entity_bindings':{'Alice':'Alice','Bob':'Bob'},'rule_outputs':['domestic_service_exclusion'],
        'combine':'any','negated':False})
    tokenizer=lambda messages,thinking:{'count':len(json.dumps(messages))}
    request=prepare_followup(compiled,compilation='answer_separating',tokenize=tokenizer,
        request_config={'context_tokens':1000000,'max_tokens':8192},thinking=False,library=library,pal_fragments=True)
    return compiled,request,library,tokenizer


def test_actual_legal_residual_is_refined_without_regenerating_rules_or_query():
    compiled,request,library,tokenizer=current();before=digest(compiled['program'])
    assert request['kind']=='joint_rule_translation_and_facts' and request['program_format']=='pal_fragment_v1'
    assert request['selection_basis']=='separation_complete' and 's37' in request['selected']
    assert request['input_tokens']==tokenizer(request['messages'],False)['count']==request['batch_plan']['cost']
    assert 's52' in request['context_closure']
    assert request['names']==['b_private_home_domestic_service']
    updated,observed=accept_followup(compiled,request,{
        'code':'current_cash = 3200 # s52\nb_domestic_remuneration_test = current_cash >= 1000',
        'factual_observations':[{'name':n,'value':True,'evidence':compiled['source']['public']['facts']} for n in request['names']]},library=library)
    for field in ('scopes','clauses','query','observations'):
        assert updated['program'][field]==compiled['program'][field]
    assert 'b_domestic_remuneration_test' not in updated['rule_residuals']
    assert digest(compiled['program'])==before and observed=={'b_private_home_domestic_service':True}
    result=assess_source(updated,observed)
    assert result['status']=='completion_stable' and result['answer']=='Contradiction'
    assert result['certificate']['natural_language_faithfulness_proven'] is False


@pytest.mark.parametrize('code',[
    'query = "Entailment"',
    'b_private_home_domestic_service = current_cash >= 1000',
    'current_cash = 99999 # s52\nb_domestic_remuneration_test = current_cash >= 1000',
    'current_cash = 3200 # s52\nb_domestic_remuneration_test = current_cash',
    '@rule("s4", otherwise=False)\ndef unrelated():\n    return True',
])
def test_local_refinement_rejects_changed_K_ungrounded_inputs_wrong_types_and_unselected_rules(code):
    compiled,request,library,_=current();before=deepcopy(compiled['program'])
    with pytest.raises((Unsupported,ValueError,TypeError,KeyError)):
        accept_followup(compiled,request,{'code':code,'factual_observations':[
            {'name':n,'value':True,'evidence':compiled['source']['public']['facts']} for n in request['names']]},library=library)
    assert compiled['program']==before


def test_actual_legal_component_preserves_A_dispatch_and_inactive_unknowns():
    stage=ROOT/'artifacts/rr_method_runtime_20261107/reference_instance_sara77_v11_20261108'
    result=json.loads((stage/'result.json').read_text())
    assert result['frontend']=='learned_identical_rule_template_v1' and result['fallback_used'] is False
    assert result['independent_executor_compilation'] is False
    from legal_skill_guard.rr.source_program import compile_source
    compiled=compile_source(json.loads((stage/'seal.json').read_text())['source'],result['program'])
    assert assess_source(compiled,result['observed'])==result['result']
    action=result['translation_actions'][0]
    assert action['selected']==['s52'] and action['names']==['b_enrolled_student','b_school_service']
    assert result['result']['certificate']['projection']['inactive_domain_multiplicity']==2**49
    active=[o for o in result['program']['observations'] if o['name'] in action['names']]
    assert {o['entity'] for o in active}=={'Alice'}
    assert result['attempts'][0]['template_instantiation']['current_executor_authored_full_statute'] is False


def test_actual_rejected_legal_fragment_recovers_only_existing_constant_and_exact_fact_quote():
    compiled,request,library,_=current()
    base=ROOT/'artifacts/rr_method_runtime_20261107/reference_instance_sara79_v12_20261108'
    raw=json.loads((base/'calls'/digest(base.name+':parse:1')/'result.json').read_text())
    response=json.loads(raw['content']);before=deepcopy(response)
    updated,observed=accept_followup(compiled,request,response,library=library)
    assert response==before
    assert updated['program']['bindings']==[{'name':'_fact_literal_0','type':'integer','value':3200,'sources':['s52']}]
    assert {p['kind'] for p in updated['deterministic_adaptations']}=={
        'existing_integer_literal_to_explicit_public_input','exact_self_source_marker_removed_from_fact_quote'}
    assert updated['accepted_observation_rows'][0]['evidence']==compiled['source']['public']['facts']
    assert assess_source(updated,observed)['answer']=='Contradiction'
    for field in ('query','scopes','clauses','observations'):
        assert compiled['program'][field]==updated['program'][field]


def test_incorrect_source_prefix_cannot_be_stripped_to_manufacture_fact_evidence():
    compiled,request,library,_=current()
    with pytest.raises(Unsupported,match='verbatim'):
        accept_followup(compiled,request,{'code':'b_domestic_remuneration_test = (3200 >= 1000)',
            'factual_observations':[{'name':n,'value':True,'evidence':'s0#'+compiled['source']['public']['facts']} for n in request['names']]},library=library)
