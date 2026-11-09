"""Regression on actual raw legal proposals; no grading labels consumed."""
import json
from pathlib import Path
from legal_skill_guard.rr.legal_case_grounding import ground_case,compile_question
from legal_skill_guard.rr.legal_predicate_skills import run
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/rr_method_redesign_20261109/legal_relations_exceptions_native_v3_20261109'

def data(i):
 s=json.loads((BASE/'seal.json').read_text());raw=json.loads((BASE/'facts.json').read_text())['value']['cases'];p=json.loads((BASE/'frozen_library.json').read_text())['program']
 return next(c for c in raw if c['ordinal']==i),next(c for c in s['cases'] if c['ordinal']==i),p


def test_real_query_swap_is_rejected_as_query_path_and_public_question_compiled():
 raw,s,p=data(86);g,audit=ground_case(raw,s,p)
 assert raw['query']['arguments']==['Bob','Alice','2015']
 assert g['query']['arguments']==[None,'Bob','2015']
 result=run(p,g)
 assert result['query_witnesses']==[['section_152_b_1_applies',['Alice','Bob','2015'],True]]
 assert ['dependent',['Bob','Charlie','2015'],True] not in result['known_atoms']
 assert ['dependent',['Bob','Charlie','2015'],False] in result['known_atoms']


def test_real_marriage_quote_cannot_supply_deduction_and_actual_dependency_still_used():
 raw,s,p=data(81);g,audit=ground_case(raw,s,p)
 assert len(audit['rejected_model_rows'])==1
 assert audit['rejected_model_rows'][0]['missing_participants']==['Bob']
 assert all(f['atom']['predicate']!='deduction_under_section_151_allowable' for f in g['facts'])
 assert run(p,g)['query_witnesses']==[['section_151_c_applies',['Alice','Bob','2015'],True]]


def test_real_zero_exception_suppresses_same_subject_base_not_other_subject():
 raw,s,p=data(72);g,_=ground_case(raw,s,p);yes=run(p,g);flat=run(p,g,use_priorities=False)
 assert yes['answer']=='Contradiction';assert flat['answer'] is None
 assert ['exemption_amount',['Bob','2015','0'],True] in yes['known_atoms']
 assert ['exemption_amount',['Bob','2015','2000'],True] not in yes['known_atoms']
 assert ['exemption_amount',['Alice','2015','2000'],True] in yes['known_atoms']


def test_real_negative_relation_does_not_become_a_negative_existential():
 raw,s,p=data(87);g,_=ground_case(raw,s,p)
 assert g['query']['arguments']==[None,'Bob','2017']
 assert run(p,g)['answer'] is None
 assert any(f['atom']['positive'] is False and f['atom']['arguments']==['Alice','Bob','2017'] for f in g['facts'])
