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


def test_component_recombination_keeps_a_real_input_scope_change():
    from copy import deepcopy
    from legal_skill_guard.skill_evolution.paired_observation_recombination import coordinate_candidates
    a={'id':'a','meaning':'a','prompt':'p','schema_json':'{}','conversion_program':'old',
        'complete_native_families':[]}
    b={**a,'id':'b'}
    base={'shared_helpers':'','components':[a,b]}
    donor=deepcopy(base);donor['components'][0]['facts_only']=True
    donor['components'][1]['conversion_program']='new'
    candidates=coordinate_candidates({'retained':base,'joint':donor})
    assert any(lib['components'][0].get('facts_only')is True and
        lib['components'][1]['conversion_program']=='old'for lib in candidates.values())


def test_unchanged_reader_reuses_its_actual_paid_wire_record(tmp_path):
    from shutil import copyfile
    from experiments import legal_skill_evolution_service_observer_update as acquired
    from experiments import legal_skill_evolution_mixed_component_training as train
    root=acquired.ROOT
    key='1cf3d3874d04d6e7270048176124eee47050a45504bb1c4d7a564458915ae548'
    record=root/'artifacts/legal_skill_evolution_mixed_component_training_compact_refs_20261115/component_reads'/(key+'.json')
    raw=json.loads(record.read_text());assert raw['error']is None
    library=train.read(root/'artifacts/legal_skill_evolution_service_observer_dictionary_abi_20261115/selected_libraries/CoverageRecombine.json')
    component=next(c for c in library['components']if c['id']=='death_events')
    public,kernels=acquired.data();sid=raw['source']
    folder=tmp_path/'component_reads';folder.mkdir();copyfile(record,folder/record.name)
    client=SimpleNamespace(artifacts=tmp_path,ledger=SimpleNamespace(run_id='paid_replay_test'))
    protocol=train.read(root/'artifacts/legal_skill_evolution_service_observer_dictionary_abi_20261115/protocol.json')
    value,_=read_component(client,protocol,sid,component,kernels[sid],public[sid]['views'][0]['public'],purpose='skill_actor')
    assert value==raw['value']
