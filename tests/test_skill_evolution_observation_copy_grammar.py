from copy import deepcopy

import jsonschema
import pytest

from experiments import legal_skill_evolution_payment_contract_refinement as generation
from legal_skill_guard.skill_evolution.observation_copy_grammar import compile_wire
from legal_skill_guard.skill_evolution.relational_observation_contract import schema
from legal_skill_guard.skill_evolution.observation_component_library import component_value


def test_real_invented_payment_kind_is_excluded_but_source_work_is_available():
    root=generation.ROOT/'artifacts/legal_skill_evolution_payment_contract_runtime_20261115'
    row=next(generation.read(p)for p in (root/'cases/Method/1').glob('*.json')
             if '3e22604a'in generation.read(p)['source'])
    lib=generation.read(root/'candidate_libraries/Method/1.json')
    contract=next(c for c in lib['components']if c['id']=='service_events')['relation_contract']
    public,kernels=generation.runtime.previous.data()
    facts=public[row['source']]['views'][0]['public']['facts']
    original=schema(contract,['service_core']);before=deepcopy(original)
    wire,receipt=compile_wire(original,contract,'service_core',facts,{})
    value=deepcopy(row['observation']['service_events']['views'][0])
    assert value['service_core']['records'][0]['kind']=='payment'
    with pytest.raises(jsonschema.ValidationError):jsonschema.validate(value,wire)
    value['service_core']['records'][0]['kind']='work'
    jsonschema.validate(value,wire)
    assert original==before and receipt['semantic_facts_added']is False
    value['service_core']['records'][0]['kind']='Alice Bob'
    jsonschema.validate(value,wire)  # Vocabulary mask is only a necessary condition.
    component=next(c for c in lib['components']if c['id']=='service_events')
    with pytest.raises(ValueError,match='copy field'):
        component_value(lib,component,kernels[row['source']],public[row['source']]['views'][0]['public'],value)


def test_child_key_transport_keeps_all_observed_events_and_does_not_fill_fields():
    contract={'enumerator':'roles','relations':[
        {'name':'roles','key':'key','fields':[{'name':'key','type':'string'}]},
        {'name':'dates','key':'key','fields':[{'name':'key','type':'string'},
            {'name':'date','type':'string','copy':True,'nullable':True}]}]}
    base=schema(contract,['dates'])
    prior={'roles':{'status':'complete','records':[{'key':'first'},{'key':'second'}]}}
    wire,receipt=compile_wire(base,contract,'dates','Feb 1st, 2017',prior)
    records=wire['properties']['dates']['anyOf'][0]['properties']['records']
    assert records['minItems']==records['maxItems']==2
    assert [r['properties']['key']['const']for r in records['prefixItems']]==['first','second']
    jsonschema.validate('Feb 1st, 2017',records['prefixItems'][0]['properties']['date'])
    jsonschema.validate(None,records['prefixItems'][0]['properties']['date'])
    assert 'const'not in records['prefixItems'][0]['properties']['date']
    assert receipt['shared_key_transport']['same_observed_enumerator_not_a_new_scan']
