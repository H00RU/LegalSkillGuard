"""Reference semantics and real-negative boundary checks, not learned results."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from legal_skill_guard.rr.legal_support_ranges import (BLOCKS,INPUTS,PROFILE_SCHEMA,apply_support_bound,evaluate_profile,evaluate_pal,validate_profile)
A=Path(__file__).resolve().parents[1]/'artifacts/rr_method_redesign_20261109'


def reference():
 rows={
 '151a':('forwards','deduction151','exemptions151'),
 '151b':('supports','exemptions151','union(singleton(focus),spouses)'),
 '151c':('supports','exemptions151','dependent152'),
 '151d':('amount_only','none','empty()'),
 '152a':('forwards','dependent152','union(children152,relatives152)'),
 '152b':('removes_only','none','empty()'),
 '152c':('supports','children152','union(family,relationship_c2)'),
 '152d':('supports','relatives152','union(family,household,relationship_d2)')}
 return {'sections':{k:{'effect':e,'output':o,'support_expression':x,'quotes':['source '+k],'reason':'reference software control, not learned'} for k,(e,o,x) in rows.items()}}


def frame():return {k:[] for k in INPUTS}|{'spouses':['Alice'],'family':['Alice'],'all_actors':None}


def test_actual_negative_can_compose_with_a_source_support_guarantee_not_population_domain():
 p=json.loads((A/'legal_grounded_replay_v1_20261109/frozen_library.json').read_text())['program']
 c=next(c for c in json.loads((A/'legal_grounded_replay_v1_20261109/shared_grounded_cases.json').read_text())['cases'] if c['ordinal']==87)
 support=evaluate_profile(reference(),frame(),'Bob');assert support['range']==['Alice','Bob']
 before=deepcopy(c);result=apply_support_bound(p,c,'transferred63c5',support,source_review_accepted=True,anchor_review_accepted=True)
 assert result['condition_value'] is False
 assert result['no_population_domain_closure_assumed'] is True
 assert c==before and c['query']['arguments'][0] is None
 for s,a in [(False,True),(True,False)]:
  assert apply_support_bound(p,c,'transferred63c5',support,source_review_accepted=s,anchor_review_accepted=a)['condition_value'] is None


def test_unknown_or_unread_family_support_is_not_empty():
 f=frame();f['spouses']=None
 assert evaluate_profile(reference(),f,'Bob')['range'] is None
 f=frame();f['relationship_d2']=None
 assert evaluate_profile(reference(),f,'Bob')['range'] is None


def test_unrelated_anonymous_actor_does_not_expand_required_legal_role_support():
 f=frame();assert f['all_actors'] is None
 assert evaluate_profile(reference(),f,'Bob')['range']==['Alice','Bob']
 f['family']=['Alice','UnknownSpouse'];assert 'UnknownSpouse' in evaluate_profile(reference(),f,'Bob')['range']


def test_effect_distinctions_are_required_for_a_closed_positive_support_bound():
 p=reference();assert evaluate_profile(p,frame(),'Bob',erase_effect_distinctions=True)['range'] is None
 p['sections']['151d']['effect']='unknown';p['sections']['151d']['output']='unknown'
 assert evaluate_profile(p,frame(),'Bob')['range'] is None


def test_incomplete_source_coverage_and_unfounded_cycle_are_rejected():
 blocks={k:'source '+k for k in BLOCKS};p=reference();validate_profile(p,blocks)
 del p['sections']['152d']
 with pytest.raises(ValueError,match='All source'):validate_profile(p,blocks)
 p=reference();p['sections']['151a']['support_expression']='deduction151'
 with pytest.raises(ValueError,match='cyclic'):validate_profile(p,blocks)


def test_compact_source_conditioned_expression_can_be_a_fully_strong_control():
 expr='union(known_deduction151,known_exemptions151,known_dependent152,known_children152,known_relatives152,singleton(focus),spouses,family,household,relationship_c2,relationship_d2)'
 p={'expression':expr,'quotes':['source'],'unresolved':[]}
 assert evaluate_pal(p,frame(),'Bob')['range']==evaluate_profile(reference(),frame(),'Bob')['range']
 for k in INPUTS[:-1]:
  f=frame();f[k]=None
  assert evaluate_pal(p,f,'Bob')['range'] is None


def test_independent_extensional_comparison_detects_a_missing_legal_status_input():
 from legal_skill_guard.rr.legal_support_ranges import compare_support_functions
 expr='union(known_deduction151,known_exemptions151,known_dependent152,known_children152,known_relatives152,singleton(focus),spouses,family,household,relationship_c2,relationship_d2)'
 p={'expression':expr,'quotes':['source'],'unresolved':[]}
 assert compare_support_functions(reference(),p)['equivalent_for_all_abstract_input_sets']
 p['expression']=expr.replace('known_exemptions151,','')
 result=compare_support_functions(reference(),p)
 assert result['status']=='sat'
 assert result['counterexample_membership']['known_exemptions151'] is True
 assert result['counterexample_membership']['profile_contains'] is True
 assert result['counterexample_membership']['pal_contains'] is False


def test_actual_rejected_flat_output_cannot_hide_undeclared_names_behind_unresolved():
    path=A/'legal_support_acquisition_v1_20261110/pal.json'
    value=json.loads(path.read_text())['value']
    assert value['unresolved']
    with pytest.raises(ValueError,match='Undeclared support name knowndeduction151'):
        evaluate_pal(value,frame(),'Bob')
    assert evaluate_pal({'expression':'top()','quotes':['source'],'unresolved':['source open']},frame(),'Bob')['range'] is None


def test_source_acquisition_schemas_satisfy_teacher_strict_preflight():
    from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues
    from legal_skill_guard.rr.legal_support_ranges import PAL_SCHEMA
    assert strict_output_schema_issues(PROFILE_SCHEMA)==[]
    assert strict_output_schema_issues(PAL_SCHEMA)==[]


def test_actual_review_preflight_failure_is_present_in_old_schema_and_fixed_before_dispatch():
    from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues
    old=json.loads((A/'legal_support_acquisition_v1_20261110/seal.json').read_text())['review_schema']
    current=json.loads((A/'legal_support_teacher_v1_20261110/seal.json').read_text())['schemas']['review']
    assert '$.properties.comparison:untyped_schema' in strict_output_schema_issues(old)
    assert strict_output_schema_issues(current)==[]
