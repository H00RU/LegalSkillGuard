import json
from types import SimpleNamespace

from experiments.legal_skill_evolution_observation_component_execute import read_component
from legal_skill_guard.skill_evolution.native import record_schema


def test_fact_only_neural_read_is_invariant_to_question_and_query(tmp_path):
    class Client:
        artifacts=tmp_path
        ledger=SimpleNamespace(run_id='offline_test')
        messages=[]

        def tokenize(self,messages,*,thinking):
            assert thinking is False
            return {'count':1}

        def generate(self,*args,**kwargs):
            self.messages.append(kwargs['messages'])
            return {'finish_reason':'stop','content':json.dumps({'service':{'records':[]}})}

    component={'id':'service','meaning':'Only source-stated service records',
        'prompt':'Read only original facts. Query alignment is separate.',
        'facts_only':True,'schema_json':json.dumps(record_schema({'records':{'type':'array','items':{'type':'string'}}}))}
    protocol={'executor_profile':{'max_tokens':8192,'context_tokens':32768}}
    pub={'facts':'A source sentence.','question':'SECRET_QUERY_WORKDAY_2017_01_01'}
    kernel={'native_query':[{'predicate':'SECRET_QUERY_PREDICATE','arguments':[]}],'query_clause':'SECRET_QUERY_CLAUSE'}
    client=Client()
    first=read_component(client,protocol,'fixture',component,kernel,pub,purpose='skill_actor')[0]
    second=read_component(client,protocol,'fixture',component,{**kernel,'query_clause':'different'},
        {**pub,'question':'Another question'},purpose='skill_actor')[0]
    assert first==second and len(client.messages)==1
    wire=json.dumps(client.messages)
    assert 'SECRET_QUERY' not in wire
    assert 'current_legal_query' not in wire and '"question"' not in wire
    read_component(client,protocol,'fixture',component,kernel,{**pub,'facts':'A different source.'},purpose='skill_actor')
    assert len(client.messages)==2
