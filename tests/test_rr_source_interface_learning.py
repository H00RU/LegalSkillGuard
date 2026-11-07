"""Invented TRAIN fixtures: whole-task filtering, exact rebind and common MB."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import sqlite3

import pytest

from legal_skill_guard.rr.coverage import Unsupported,digest
from legal_skill_guard.rr.interfaces import Refinement
from legal_skill_guard.rr.source_interface_learning import learn_source_interfaces,rebind_source_program
from legal_skill_guard.rr.source_interfaces import (check_source_examples,connector_cases,
    connector_identity,fit_source_examples,replace_connector)
from legal_skill_guard.rr.source_program import compile_source


def op(name,*args):return {'op':name,'args':list(args)}
def var(name):return {'var':name}


def equality_case():
    source={'key':'SARA_v2_Binary:invented_interface_fixture','dataset':'SARA_v2_Binary','public':{
        'rules':'If a licensed person is also insured, an eligible person exists.',
        'facts':'Alice is licensed.\nBob is insured.','query':'An eligible person exists.'}}
    graph={'op':'project_exists','params':{},'inputs':[{'op':'join_on','inputs':[{'slot':'licensed'},{'slot':'insured'}],
        'params':{'keys':['person']}}]}
    program={'bindings':[{'name':name,'type':'relation','value':{'columns':['person'],'rows':[[entity]],'closed':True},
        'sources':[unit]} for name,entity,unit in [('licensed','Alice','s1'),('insured','Bob','s2')]],
        'observations':[],'rule_residuals':[],'scopes':[],
        'nodes':[{'name':'joined','kind':'connector','body':{'graph':graph,'project':'identity'}}],
        'clauses':[{'name':'eligible','sources':['s0'],'value':var('joined'),'otherwise':False}],
        'query':op('if',var('eligible'),'Entailment','Contradiction')}
    view={'kind':'SARA_v2_Binary','edit':{'scope':'all_fact_occurrences','old':'Alice','new':'Bob'}}
    return source,program,{'answer':'Contradiction'},view


class RecordedOracle:
    def __init__(self,path,source,views=(),missing=()):
        self.ledger=SimpleNamespace(path=path);self.source=source;self.saved=list(views);self.calls=[]
        with sqlite3.connect(path) as db:
            db.execute('create table oracle_views (source,view_hash,reserved_at)')
            for key in [digest(v) for v in views]+list(missing):
                db.execute('insert into oracle_views values (?,?,0)',(source,key))
    def cached_views(self):return deepcopy(self.saved)
    def query(self,view):
        key=digest(view);self.calls.append(key)
        with sqlite3.connect(self.ledger.path) as db:
            if not db.execute('select 1 from oracle_views where source=? and view_hash=?',(self.source,key)).fetchone():
                db.execute('insert into oracle_views values (?,?,0)',(self.source,key))
        return 'Entailment'


def test_real_connector_interventions_compare_the_complete_native_task(tmp_path,monkeypatch):
    import legal_skill_guard.rr.source_interface_learning as learning
    source,program,grade,view=equality_case()
    monkeypatch.setattr(learning,'candidate_views',lambda *args:[view])
    oracle=RecordedOracle(tmp_path/'book.sqlite3',source['key'])
    result=learn_source_interfaces(source,grade,oracle,program=program)
    assert result['learned_pattern']['fields']==['entity_equality']
    assert result['connector_candidates_fully_checked']>0
    assert len(result['oracle_views'])==1 and result['refinement']['collisions']
    assert not result['finite_candidate_pool_is_Omega'] and not result['A_certificate_issued_by_B']
    assert all(not c['A_certificate_issued'] for h in result['candidate_checks'] for c in h['checks'])
    correct=next(c for c in result['candidate_checks'] if c['graph']==program['nodes'][0]['body']['graph'])
    assert [row['prediction'] for row in correct['checks']]==['Contradiction','Entailment']
    assert all(c['matches_reference'] and c['target_node_executed'] for c in correct['checks'])


def test_changed_entity_view_preserves_literal_provenance_without_modifying_the_original():
    from legal_skill_guard.rr.typed_learning import public_variant
    source,program,grade,view=equality_case();before=digest(program)
    variant=public_variant(source,grade,view)
    compiled,observed=rebind_source_program(source,variant,program,[])
    assert observed=={} and compiled['slots']['licensed'].rows==(('Bob',),)
    assert compiled['slots']['insured'].rows==(('Bob',),)
    assert digest(program)==before


def test_empty_executable_H_cannot_be_rescued_by_a_field_refinement(tmp_path,monkeypatch):
    import legal_skill_guard.rr.source_interface_learning as learning
    source,program,grade,view=equality_case();grade['answer']='Unknown'
    monkeypatch.setattr(learning,'candidate_views',lambda *args:[])
    monkeypatch.setattr(learning,'refine',lambda *args:Refinement('identified_on_observed_collisions',[('entity_equality',)],[]))
    result=learn_source_interfaces(source,grade,RecordedOracle(tmp_path/'book.sqlite3',source['key']),program=program)
    assert result['connector_candidates_retained']==0 and result['learned_pattern'] is None


def test_four_already_charged_missing_views_do_not_buy_a_new_budget(tmp_path,monkeypatch):
    import legal_skill_guard.rr.source_interface_learning as learning
    source,program,grade,view=equality_case()
    monkeypatch.setattr(learning,'candidate_views',lambda *args:[view])
    oracle=RecordedOracle(tmp_path/'book.sqlite3',source['key'],missing=['old'+str(i) for i in range(4)])
    result=learn_source_interfaces(source,grade,oracle,program=program)
    assert result['status']=='charged_view_record_missing' and oracle.calls==[]
    assert len(result['missing_charged_view_records'])==4 and result['learned_pattern'] is None


def test_unbound_cached_view_cannot_verify_a_graph_or_trigger_more_queries(tmp_path,monkeypatch):
    import legal_skill_guard.rr.source_interface_learning as learning
    source,program,grade,view=equality_case()
    oracle=RecordedOracle(tmp_path/'book.sqlite3',source['key'],views=[view])
    original=learning.rebind_source_program
    def base_only(s,variant,*args,**kwargs):
        if variant['public']!=s['public']:raise Unsupported('Actual edit cannot be rebound')
        return original(s,variant,*args,**kwargs)
    monkeypatch.setattr(learning,'rebind_source_program',base_only)
    monkeypatch.setattr(learning,'candidate_views',lambda *args:[])
    monkeypatch.setattr(learning,'refine',lambda *args:Refinement('identified_on_observed_collisions',[('entity_equality',)],[]))
    result=learn_source_interfaces(source,grade,oracle,program=program)
    assert result['connector_candidates_retained']>0 and result['connector_candidates_fully_checked']==0
    assert result['status']=='view_rebinding_unavailable' and result['learned_pattern'] is None


def numeric_case():
    source={'key':'RuleArena_Airline:invented_sum','dataset':'RuleArena_Airline','public':{
        'rules':'The fee is the sum of both item amounts plus 50.',
        'prompt':'Item a costs 10 and item b costs 20 for Alice in 2018. An alternative cap is 5.'}}
    amounts=[{'value':value,'unit':'USD','owner':'Alice','period':'2018','lineage':[lineage],'stage':'element'}
             for value,lineage in ((10,'a'),(20,'b'))]
    program={'bindings':[{'name':'amounts','type':'amounts','value':amounts,'sources':['s1']},
        {'name':'limit','type':'integer','value':5,'sources':['s1']}],
        'observations':[],'rule_residuals':[],'scopes':[],
        'nodes':[{'name':'total','kind':'connector','body':{'graph':{'op':'fold_reduce',
            'inputs':[{'slot':'amounts'}],'params':{'primitive':'sum_amounts'}},'project':'amount_value'}}],
        'clauses':[{'name':'fee','sources':['s0'],'value':op('add',var('total'),50),'otherwise':0}],
        'query':var('fee')}
    return source,program


def test_ordinary_MB_uses_same_full_task_candidate_checks_and_masks_values(tmp_path,monkeypatch):
    import legal_skill_guard.rr.source_interface_learning as learning
    source,program=numeric_case();grade={'answer':80,'reference_arguments':{'bag_list':[]}}
    monkeypatch.setattr(learning,'candidate_views',lambda *args:[])
    oracle=RecordedOracle(tmp_path/'book.sqlite3',source['key'])
    result=learn_source_interfaces(source,grade,oracle,program=program)
    assert result['candidate_checks'][0]['checks'][0]['prediction']==80
    assert result['learned_pattern'] is None
    frozen=fit_source_examples([{'learning':result}]);compiled=compile_source(source,program)
    assert check_source_examples(compiled,frozen)['accepted'] and oracle.calls==[]
    wrong={'op':'fold_reduce','inputs':[{'op':'map','inputs':[{'slot':'amounts'}],
        'params':{'primitive':'cap','scope':'element','limit_slot':'limit'}}],
        'params':{'primitive':'sum_amounts'}}
    replaced=replace_connector(program,{'node':'total','graph':wrong})
    rejected=check_source_examples(compile_source(source,replaced),frozen)
    assert not rejected['accepted'] and rejected['rejected_nodes']==['total']
    other_source=deepcopy(source);other_source['key']='RuleArena_Airline:different_public_source'
    other_source['public']['prompt']=other_source['public']['prompt'].replace('Alice','Carol').replace('10','11')
    other_program=deepcopy(program);other_program['bindings'][0]['value'][0]['value']=11
    for amount in other_program['bindings'][0]['value']:amount['owner']='Carol'
    a=connector_identity(compiled,'total',program['nodes'][0]['body']['graph'])
    b=connector_identity(compile_source(other_source,other_program),'total',other_program['nodes'][0]['body']['graph'])
    assert a==b
    encoded=json.dumps(frozen['content'])
    assert 'Alice' not in encoded and 'Carol' not in encoded and source['key'] not in encoded


def test_ambiguous_numeric_fact_edits_are_not_repaired_from_target_labels():
    source={'key':'RuleArena_Airline:ambiguous','dataset':'RuleArena_Airline','public':{
        'rules':'The fee is the supplied count.','prompt':'The supplied count is 100 and the comparison count is 100.'}}
    program={'bindings':[{'name':'count','type':'integer','value':100,'sources':['s1']}],
        'observations':[],'rule_residuals':[],'scopes':[],'nodes':[],
        'clauses':[{'name':'fee','sources':['s0'],'value':var('count'),'otherwise':0}],'query':var('fee')}
    variant=deepcopy(source);variant['public']['prompt']=variant['public']['prompt'].replace('is 100','is 50',1)
    with pytest.raises(Unsupported,match='unambiguous'):rebind_source_program(source,variant,program,[])


def test_unused_connectors_cannot_become_learned_executable_cases():
    source,program,_,_=equality_case()
    program['clauses'][0]['value']=op('eq',var('licensed'),var('licensed'))
    compiled=compile_source(source,program)
    assert connector_cases(compiled)==[]
