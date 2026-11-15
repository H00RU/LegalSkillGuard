"""Actual native-alias routing and unread/source-error separation."""
from pathlib import Path

from experiments import legal_skill_evolution_payment_contract_refinement as generation
from legal_skill_guard.skill_evolution.observation_source_review import review
from legal_skill_guard.skill_evolution.relational_observation_contract import pullback

OLD=generation.ROOT/'artifacts/legal_skill_evolution_payment_contract_runtime_20261115'


def test_actual_service_end_demand_does_not_read_foreign_kinship():
    row=next(generation.read(p)for p in (OLD/'cases/FreeTeacher/0').glob('*.json')
             if 'bb6b0bc1'in generation.read(p)['source'])
    library=generation.read(OLD/'candidate_libraries/FreeTeacher/0.json')
    aliases=[b for rows in row['execution']['component_conversions'].values()
             for item in rows if item['trusted_complete_observation']
             for b in item['converted'].get('source_event_binding',{}).get('bindings',[])]
    target={'predicate':'end_','arguments':['domestic service',{'var':'Date'}]}
    family=next(c for c in library['components']if c['id']=='family_relationship_residence')
    service=next(c for c in library['components']if c['id']=='service_events')
    assert pullback(family['relation_contract'],target)['branches']
    assert not pullback(family['relation_contract'],target,event_bindings=aliases)['branches']
    assert pullback(service['relation_contract'],target,event_bindings=aliases)['branches']


def test_actual_empty_pre_read_hay_case_is_pending_not_semantically_wrong():
    sid='SARA_v2_Binary:d5e1138c'
    grounded={'bindings':[{'inputs':{'facts':[],'negative_givens':[]}}]}
    result=review(sid,grounded,complete_families=[],scope_contract={'family_scans':[],'event_properties':[]})
    assert result['failures']==0 and result['pending_checks']
    closed=review(sid,grounded,complete_families=['payment_'])
    assert closed['failures']==1


def test_wrong_payment_purpose_is_not_rescued_by_executed_native_answer():
    row=next(generation.read(p)for p in (OLD/'cases/Method/1').glob('*.json')
             if 'bb6b0bc1'in generation.read(p)['source'])
    world=row['execution']['binding_executions'][0]
    result=review(row['source'],{'bindings':[{'inputs':world['inputs']}]},
        complete_families=world['complete_families'],scope_contract=world['scope_contract'])
    assert row['execution']['handled']
    assert not row['native_score']['correct']
    assert any('event connection'in c['check']and not c['passed']for c in result['checks'])
