from legal_skill_guard.skill_evolution.partial_native_proof import execute
from test_skill_evolution_partial_native_proof import binding, kernel


def scopes(*properties):
    return {'family_scans':['service_'],
            'event_properties':[{'event':event,'predicate':predicate} for event,predicate in properties]}


def test_reading_service_roles_does_not_close_unread_dates(tmp_path):
    k=kernel(tmp_path,'s9001 :- service_(E),agent_(E,"worker"),patient_(E,"employer"),\\+ end_(E,_).','s9001')
    b=binding(('service_',['svc']),('agent_',['svc','worker']),('patient_',['svc','employer']))
    actual=execute(k,b,set(),{'facts':'Roles have been read; periods remain unread.'},
        scope_contract=scopes(('svc','agent_'),('svc','patient_')))
    assert not actual['handled'] and actual['answer'] is None
    assert any(x['predicate']=='end_' for x in actual['unread_factual_scopes'])
    complete=execute(k,b,set(),{'facts':'The service period was also scanned and has no end.'},
        scope_contract=scopes(('svc','agent_'),('svc','patient_'),('svc','end_')))
    assert complete['handled'] and complete['answer']=='Entailment'


def test_irrelevant_properties_need_not_be_read(tmp_path):
    k=kernel(tmp_path,'s9001 :- service_(E),agent_(E,"worker").','s9001')
    b=binding(('service_',['svc']),('agent_',['svc','worker']))
    result=execute(k,b,set(),{'facts':'Worker is known; dates and location unread.'},
        scope_contract=scopes(('svc','agent_')))
    assert result['handled'] and result['answer']=='Entailment'
    assert result['used_observation_families']==['service_']


def test_partial_event_closure_cannot_close_global_enumeration(tmp_path):
    k=kernel(tmp_path,'s9001 :- findall(E,end_(E,_),Ends),length(Ends,0).','s9001')
    result=execute(k,binding(('service_',['svc'])),set(),{'facts':'Only one event has been scanned.'},
        scope_contract=scopes(('svc','end_')))
    assert not result['handled']
    assert result['unread_factual_scopes'][0]['event'] is None


def test_property_closure_does_not_leak_between_events(tmp_path):
    k=kernel(tmp_path,'s9001 :- \\+ end_("svc",_).','s9001')
    b=binding(('service_',['svc']),('service_',['other']))
    result=execute(k,b,set(),{'facts':'The other event was scanned.'},scope_contract=scopes(('other','end_')))
    assert not result['handled']
    assert result['unread_factual_scopes'][0]['event']=='svc'


def test_unknown_referent_cannot_be_created_by_a_scope(tmp_path):
    import pytest
    k=kernel(tmp_path,'s9001 :- \\+ end_("invented",_).','s9001')
    with pytest.raises(ValueError,match='unobserved referent'):
        execute(k,binding(),set(),{'facts':'No observation.'},scope_contract=scopes(('invented','end_')))
