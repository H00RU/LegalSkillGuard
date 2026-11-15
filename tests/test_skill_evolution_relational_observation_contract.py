"""Logic fixtures only; these contracts are not claimed as acquired skills."""
from copy import deepcopy

import pytest

from legal_skill_guard.skill_evolution.relational_observation_contract import forward, pullback, split


def v(name):
    return {'var':name}


def contract():
    fields=[{'name':name,'type':'string','copy':name in ('cue','related','reference')}
            for name in ('key','cue','related','reference')]
    fields.append({'name':'end','type':'string','nullable':True,'copy':False})
    body={'predicate':'kinship','sign':'positive','arguments':[v('K'),'father',v('P'),v('C'),v('End')]}
    return {'key_domain':'kinship','enumerator':'kinship','constants':['father'],
        'relations':[{'name':'kinship','key':'key','fields':fields,'prompt':'Read all source kinships.'}],
        'covered_families':['father_'],'covered_properties':['agent_','patient_','end_'],
        'rules':[{'id':name,'cost':1,'head':{'predicate':name,'sign':'positive','arguments':args},
                  'body':[deepcopy(body)]} for name,args in
                 [('father_',[v('K')]),('agent_',[v('K'),v('P')]),
                  ('patient_',[v('K'),v('C')]),('end_',[v('K'),v('End')])]]}


KERNEL={'fact_arities':{'father_':1,'agent_':2,'patient_':2,'end_':2}}
PUBLIC={'facts':'Child pays their father Parent for work.'}
WITNESSES=[{'field':'facts','quote':PUBLIC['facts']}]


def reading(**row):
    return {'status':'complete','records':[{'key':'r0',**row}],'witnesses':WITNESSES}


def refined():
    return split(contract(),'kinship',[
        {'name':'kinship_cue','fields':['cue'],'prompt':'Copy the kinship cue.'},
        {'name':'kinship_roles','fields':['related','reference'],'prompt':'Read both people for each key.'},
        {'name':'kinship_period','fields':['end'],'prompt':'Read only a source-stated kinship end.'}])


def test_full_read_join_preserves_original_facts_and_closure():
    base={'kinship':reading(cue='father',related='Parent',reference='Child',end=None)}
    parts={'kinship_cue':reading(cue='father'),
           'kinship_roles':reading(related='Parent',reference='Child'),
           'kinship_period':reading(end=None)}
    before=forward(contract(),base,PUBLIC,KERNEL)
    after=forward(refined(),parts,PUBLIC,KERNEL)
    assert before['facts']==after['facts']
    assert before['scope_contract']==after['scope_contract']


def test_partial_relation_reading_keeps_dates_unknown():
    parts={'kinship_cue':reading(cue='father'),
           'kinship_roles':reading(related='Parent',reference='Child')}
    result=forward(refined(),parts,PUBLIC,KERNEL)
    assert result['facts']==[
        {'predicate':'father_','arguments':['kinship::r0']},
        {'predicate':'agent_','arguments':['kinship::r0','Parent']},
        {'predicate':'patient_','arguments':['kinship::r0','Child']}]
    assert result['unread_relations']==['kinship_period']
    assert result['scope_contract']['family_scans']==['father_']
    assert {r['predicate']for r in result['scope_contract']['event_properties']}=={'agent_','patient_'}


def test_unread_is_not_a_complete_empty_scan():
    result=forward(refined(),{'kinship_cue':{'status':'unread','records':None,'witnesses':WITNESSES}},PUBLIC,KERNEL)
    assert result['facts']==[]
    assert result['scope_contract']=={'family_scans':[],'event_properties':[]}


def test_invented_normalized_cue_is_rejected_instead_of_corrected():
    with pytest.raises(ValueError,match='copy field'):
        forward(refined(),{'kinship_cue':reading(cue='daughter')},PUBLIC,KERNEL)


def test_key_join_cannot_mix_different_source_records():
    roles=reading(related='Parent',reference='Child')
    roles['records'][0]['key']='different'
    with pytest.raises(ValueError,match='same source keys'):
        forward(refined(),{'kinship_cue':reading(cue='father'),'kinship_roles':roles},PUBLIC,KERNEL)


def test_pullback_does_not_prefill_goal_values_as_observations():
    c=refined()
    query={'predicate':'agent_','arguments':['kinship::r0','DesiredPerson']}
    unknown=pullback(c,query)
    assert all(d['observed_source_key'] is None for b in unknown['branches'] for d in b['joined_demands'])
    known=pullback(c,query,observed_keys=['kinship::r0'])
    assert all(d['observed_source_key']=='r0' for b in known['branches'] for d in b['joined_demands'])
    assert all('prefill' not in d or not d['prefill'] for b in known['branches'] for d in b['joined_demands'])
    assert {d['relation'] for b in known['branches'] for d in b['joined_demands']}=={'kinship_cue','kinship_roles'}


def test_split_preserves_repeated_variable_equality():
    c=contract()
    c['rules']=[c['rules'][0]]
    c['rules'][0]['body'][0]['arguments'][2:4]=[v('Same'),v('Same')]
    c['covered_properties']=[]
    r=split(c,'kinship',[
        {'name':'kind','fields':['cue'],'prompt':'Copy cue.'},
        {'name':'people','fields':['related','reference'],'prompt':'Read roles.'},
        {'name':'period','fields':['end'],'prompt':'Read dates.'}])
    result=forward(r,{'kind':reading(cue='father'),
        'people':reading(related='Parent',reference='Child')},PUBLIC,KERNEL)
    assert result['facts']==[]
