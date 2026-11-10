import pytest
import z3
from experiments.rr_v2_norm_query_prototype import classify_permission,offline_probes


def test_independent_software_ablation_distinctions():
    p=offline_probes()
    assert p['ordinary_consistency_selection_on_software_label']==['possible']
    assert not p['two_contributions_established']


def test_missing_permission_does_not_become_negative():
    assert classify_permission([],{},'external_adviser',action='disclose')['answer'] is None


def test_explicit_prohibition_without_permission_can_refute():
    rows=[{'effect':'prohibition','action':'disclose','recipient':'external_adviser','guard':z3.BoolVal(True)}]
    assert classify_permission(rows,{},'external_adviser',action='disclose')['answer']=='Contradiction'


def test_unordered_conflict_does_not_manufacture_authorization():
    rows=[{'effect':e,'action':'disclose','recipient':'external_adviser','guard':z3.BoolVal(True)} for e in ['permission','prohibition']]
    assert classify_permission(rows,{},'external_adviser',action='disclose')['answer'] is None


def test_observed_context_changes_operative_not_possible_semantics():
    rows=[{'effect':'permission','action':'disclose','recipient':'employee','guard':z3.Bool('need')}]
    assert classify_permission(rows,{},'employee',action='disclose',mode='operative',facts={'need':True})['answer']=='Entailment'
    assert classify_permission(rows,{},'employee',action='disclose',mode='operative',facts={'need':False})['answer'] is None


def test_mode_must_be_declared():
    with pytest.raises(ValueError,match='Unknown'):classify_permission([],{},'employee',action='disclose',mode='guess')


def test_unknown_effect_is_not_a_prohibition():
    rows=[{'effect':'unparsed','action':'disclose','recipient':'employee','guard':z3.BoolVal(True)}]
    with pytest.raises(ValueError,match='Unknown'):classify_permission(rows,{},'employee',action='disclose')


@pytest.mark.parametrize('effect',['permission','prohibition'])
def test_recorded_cross_action_counterexample(effect):
    rows=[{'effect':effect,'action':'reverse_engineer','recipient':'employee','guard':z3.BoolVal(True)}]
    assert classify_permission(rows,{},'employee',action='retain_information')['answer'] is None
    assert classify_permission(rows,{},'employee',action='reverse_engineer')['answer']==(
        'Entailment' if effect=='permission' else 'Contradiction')
