"""Real negative call regression plus formal-scope boundary controls."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from legal_skill_guard.rr.legal_predicate_skills import evaluate_guard,run
A=Path(__file__).resolve().parents[1]/'artifacts/rr_method_redesign_20261109'

def real():
 p=json.loads((A/'legal_grounded_replay_v1_20261109/frozen_library.json').read_text())['program']
 c=next(c for c in json.loads((A/'legal_grounded_replay_v1_20261109/shared_grounded_cases.json').read_text())['cases'] if c['ordinal']==87)
 return p,c


def test_actual_87_negative_callee_answers_its_ground_guard_without_new_source_rules():
 p,c=real();c['query']['arguments']=['Alice','Bob','2017']
 assert run(p,c)['answer'] is None
 result=evaluate_guard(p,c,'transferred63c5')
 assert result['condition_value'] is False
 body=result['branches'][0]['body_query']
 assert body=={'predicate':'deduction_under_section_151_allowable','arguments':['Alice','Bob','2017'],'positive':True}
 assert result['branches'][0]['proof']['answer']=='Contradiction'


def test_original_unbounded_question_is_not_replaced_by_a_named_person_domain():
 p,c=real();original=deepcopy(c)
 result=evaluate_guard(p,c,'transferred63c5')
 assert result['condition_value'] is None and result['domains'] is None
 assert result['scope']=='unbounded_projection';assert c==original


def test_explicit_finite_question_is_distinguished_from_native_unbounded_question():
 p,c=real();result=evaluate_guard(p,c,'transferred63c5',domains={0:['Alice']})
 assert result['condition_value'] is False
 assert result['scope']=='declared_finite_projection'
 assert evaluate_guard(p,c,'transferred63c5',domains={0:['Alice','UnknownTaxpayer']})['condition_value'] is None


def test_negative_role_and_year_are_not_reused_in_other_calls():
 p,c=real()
 for args in [['Bob','Alice','2017'],['Alice','Bob','2016']]:
  c['query']['arguments']=args
  assert evaluate_guard(p,c,'transferred63c5')['condition_value'] is None


def test_source_other_taxpayer_distinctness_is_evaluated_as_a_condition():
 p,c=real();c['query']['arguments']=['Bob','Bob','2017']
 result=evaluate_guard(p,c,'transferred63c5')
 assert result['condition_value'] is False
 assert result['branches'][0]['basis']=='source role/distinctness constraint'


def test_missing_callee_observation_remains_unknown():
 p,c=real();c['facts']=[f for f in c['facts'] if f['atom']['predicate']!='deduction_under_section_151_allowable']
 c['query']['arguments']=['Alice','Bob','2017']
 assert evaluate_guard(p,c,'transferred63c5')['condition_value'] is None


def test_negative_call_never_contraposes_an_unrelated_horn_rule():
 p,c=real()
 with pytest.raises(ValueError,match='does not name'):evaluate_guard(p,c,'r151_c_applicability')
 with pytest.raises(ValueError,match='exactly'):evaluate_guard(p,c,'transferred63c5',domains={1:['Alice']})
 with pytest.raises(ValueError,match='finite set'):evaluate_guard(p,c,'transferred63c5',domains={0:['Alice','Alice']})
