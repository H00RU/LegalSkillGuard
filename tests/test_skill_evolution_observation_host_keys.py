from copy import deepcopy
import json

import jsonschema
import pytest

from experiments import legal_skill_evolution_payment_contract_refinement as acquired
from legal_skill_guard.skill_evolution.observation_copy_grammar import (
    assign_enumerator_keys,enumeration_schema,compile_wire)
from legal_skill_guard.skill_evolution.observation_relation_reader import read_relation
from legal_skill_guard.skill_evolution.relational_observation_contract import schema,forward


def actual():
    library=acquired.read(acquired.ROOT/'artifacts/legal_skill_evolution_field_projection_scopes_20261115/libraries/MethodProjected.json')
    component=next(c for c in library['components']if c['id']=='service_events')
    public,kernels=acquired.runtime.previous.data();sid=next(s for s in public if ':6939feda'in s)
    return component,sid,public[sid]['views'][0]['public'],kernels[sid]


def test_first_enumeration_names_rows_without_altering_any_source_attribute():
    c,sid,public,kernel=actual();contract=c['relation_contract'];name=contract['enumerator']
    original=schema(contract,[name]);requested,used=enumeration_schema(original,contract,name,{})
    assert used
    group=next(g for g in contract['relations']if g['name']==name)
    raw={name:{'status':'complete','records':[{'worker':'Bob'},{'worker':'Alice'}],
        'witnesses':[{'field':'facts','quote':public['facts']}]}}
    jsonschema.validate(raw,requested)
    value=assign_enumerator_keys(raw,group,c['id']);jsonschema.validate(value,original)
    assert raw[name]['records']==[{'worker':'Bob'},{'worker':'Alice'}]
    assert value[name]['records']==[{'source_key':'service_events_row_0','worker':'Bob'},
        {'source_key':'service_events_row_1','worker':'Alice'}]
    part=forward(contract,value,public,kernel)
    assert len([f for f in part['facts']if f['predicate']=='service_'])==2
    child=next(g for g in contract['relations']if g['name'].endswith('__employer'))
    wire,_=compile_wire(schema(contract,[child['name']]),contract,child['name'],public['facts'],value)
    items=wire['properties'][child['name']]['anyOf'][0]['properties']['records']['prefixItems']
    assert [r['properties']['source_key']['const']for r in items]==['service_events_row_0','service_events_row_1']


def test_unread_and_existing_identity_are_not_filled_or_renamed():
    c,_,_,_=actual();contract=c['relation_contract'];name=contract['enumerator']
    group=next(g for g in contract['relations']if g['name']==name)
    value={name:{'status':'unread','records':None,'witnesses':[]}}
    assert assign_enumerator_keys(value,group,c['id'])==value
    original=schema(contract,[name])
    assert enumeration_schema(original,contract,name,{name:value[name]})==(original,False)
    factual=deepcopy(contract);next(g for g in factual['relations']if g['name']==name)['fields'][0]['copy']=True
    with pytest.raises(ValueError,match='source-copied'):enumeration_schema(original,factual,name,{})


def test_actual_reader_keeps_raw_response_and_reconstructs_exact_host_keys_on_cache(tmp_path):
    c,sid,public,_=actual();name=c['relation_contract']['enumerator'];calls=[]
    response={name:{'status':'complete','records':[{'worker':'Bob'},{'worker':'Alice'}],
        'witnesses':[{'field':'facts','quote':public['facts']}]}}
    class Client:
        artifacts=tmp_path
        def tokenize(self,messages,thinking):return {'count':100}
        def generate(self,*args,**kwargs):
            calls.append(kwargs)
            jsonschema.validate(response,kwargs['schema'])
            assert '2018-01-01'not in json.dumps(kwargs['messages'])
            return {'content':json.dumps(response),'finish_reason':'stop','usage':{},'elapsed_seconds':0}
    protocol={'run_id':'offline_fixture','host_enumerator_keys':True,'compile_literal_copy_and_shared_keys':True,
        'executor_profile':{'max_tokens':8192,'context_tokens':32768}}
    first,_=read_relation(Client(),protocol,sid,c,name,public,{})
    second,receipt=read_relation(Client(),protocol,sid,c,name,public,{})
    assert len(calls)==1 and first==second and receipt['cache_hit']
    saved=json.loads(next((tmp_path/'relation_reads').glob('*.json')).read_text())
    assert json.loads(saved['raw_content'])==response and saved['value']==first
