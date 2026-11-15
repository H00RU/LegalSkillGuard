import hashlib
import json

from legal_skill_guard.skill_evolution.native import record_schema
from legal_skill_guard.skill_evolution.native_observation_execution import evaluate
from legal_skill_guard.skill_evolution.observation_source_review import review
from legal_skill_guard.skill_evolution.relational_observation_contract import schema
from legal_skill_guard.skill_evolution.sara_statute_kernel import fact_vocabulary
from test_skill_evolution_relational_observation_contract import PUBLIC, WITNESSES, reading, refined


def kernel(tmp_path, period=False):
    events=':- discontiguous father_/1.\n:- discontiguous agent_/2.\n:- discontiguous patient_/2.\n:- discontiguous end_/2.\n'
    clause='s9001 :- father_(E),agent_(E,"Parent"),patient_(E,"Child")'
    clause+=',\\+ end_(E,_)' if period else ''
    files={'events.pl':events,'utils.pl':'','section9001.pl':clause+'.'}
    for name,body in files.items():(tmp_path/name).write_text(body)
    return {'statute_directory':str(tmp_path),
        'statute_sha256':{n:hashlib.sha256(b.encode()).hexdigest()for n,b in files.items()},
        'fact_arities':fact_vocabulary(events), 'native_query':[{'predicate':'s9001','arguments':[]}],
        'input_fields_json':json.dumps({'facts':{'type':'array'},'negative_givens':{'type':'array'},'extraction_status':{'type':'string'}})}


def library():
    c=refined()
    view=schema(c)
    view['required']=[]
    return {'shared_helpers':'','components':[{'id':'family','meaning':'Learned relation contract fixture',
        'prompt':'Read source relations.','schema_json':json.dumps(record_schema({'views':{'type':'array','minItems':1,'items':view}})),
        'relation_contract':c,'complete_native_families':[]}]}


def observation():
    return {'family':{'views':[{'kinship_cue':reading(cue='father'),
        'kinship_roles':reading(related='Parent',reference='Child')}]}}


def test_relations_reach_real_native_execution_without_closing_dates(tmp_path):
    result=evaluate(library(),kernel(tmp_path),PUBLIC,observation(),'unreviewed_logic_fixture')
    assert result['handled'] and result['answer']=='Entailment'
    assert result['binding_executions'][0]['complete_families']==[]
    assert not any(s['predicate']=='end_' for s in result['binding_executions'][0]['scope_contract']['event_properties'])
    assert result['used_observation_families']==['father_']


def test_the_same_partial_observation_blocks_a_date_dependent_verdict(tmp_path):
    result=evaluate(library(),kernel(tmp_path,period=True),PUBLIC,observation(),'unreviewed_logic_fixture')
    assert not result['handled'] and result['answer'] is None
    assert any(s['predicate']=='end_' for s in result['binding_executions'][0]['execution']['unread_factual_scopes'])


def test_partial_source_checks_keep_missing_period_pending_not_passed():
    facts=[{'predicate':'service_','arguments':['svc']},
        {'predicate':'agent_','arguments':['svc','Bob']},{'predicate':'patient_','arguments':['svc','Alice']}]
    grounded={'bindings':[{'inputs':{'facts':facts,'negative_givens':[]}}]}
    sid='SARA_v2_Binary:bb6b0bc1_actual_TRAIN_annotation'
    full=review(sid,grounded,complete_families=['service_'])
    assert full['failures']>=2
    partial=review(sid,grounded,complete_families=[],scope_contract={
        'family_scans':['service_'],'event_properties':[{'event':'svc','predicate':p}for p in ('agent_','patient_')]})
    assert partial['failures']==0
    assert any('Service period' in c['check']for c in partial['pending_checks'])
    assert any('Explicit home' in c['check']for c in partial['pending_checks'])
    assert not any('Service period' in c['check']for c in partial['checks'])
    wrong={**grounded,'bindings':[{'inputs':{'facts':facts+[{'predicate':'start_','arguments':['svc','2018-01-01']}],
                                             'negative_givens':[]}}]}
    assert review(sid,wrong,complete_families=[],scope_contract=partial_scope())['failures']>0


def partial_scope():
    return {'family_scans':['service_'],'event_properties':[{'event':'svc','predicate':p}for p in ('agent_','patient_')]}


def test_an_explicit_empty_scan_cannot_erase_a_known_TRAIN_service_or_father():
    empty={'bindings':[{'inputs':{'facts':[],'negative_givens':[]}}]}
    value=review('SARA_v2_Binary:3e22604a_actual_TRAIN_annotation',empty,complete_families=[],
        scope_contract={'family_scans':['service_','father_'],'event_properties':[]})
    assert value['failures']==2
