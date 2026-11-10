from copy import deepcopy
import pytest
from legal_skill_guard.rr.finite_rule_projection import project_definition

RULE={'id':'source-condition','head':{'predicate':'applies','arguments':['?claimant','?subject','?year'],'positive':True},
 'body':[{'predicate':'allowed','arguments':['?claimant','?subject','?year'],'positive':True}],
 'different':[{'left':'?claimant','right':'?subject'}]}
QUERY={'predicate':'applies','arguments':[None,'Bob','2017'],'positive':True}


def fact(person,value,year='2017'):
    return {'atom':{'predicate':'allowed','arguments':[person,'Bob',year],'positive':value},'quote':'explicit fixture'}


def test_one_negative_does_not_close_an_open_world():
    assert project_definition(RULE,[fact('Alice',False)],QUERY)['value'] is None


def test_a_ground_query_with_missing_evidence_is_still_unknown():
    q=QUERY|{'arguments':['Alice','Bob','2017']}
    assert project_definition(RULE,[],q)['value'] is None
    assert project_definition(RULE,[fact('Alice',False)],q)['value'] is False


def test_closed_projection_uses_explicit_negatives_only():
    r=project_definition(RULE,[fact('Alice',False)],QUERY,{'?claimant':['Alice','Bob']})
    assert r['value'] is False and len(r['witnesses'])==1
    assert not r['missing_condition_values_defaulted_false']


def test_missing_or_inconsistent_candidate_is_unknown():
    assert project_definition(RULE,[fact('Alice',False)],QUERY,{'?claimant':['Alice','Charlie']})['value'] is None
    assert project_definition(RULE,[fact('Alice',False),fact('Alice',True)],QUERY,{'?claimant':['Alice']})['value'] is None


def test_an_explicit_positive_settles_even_an_open_projection():
    assert project_definition(RULE,[fact('Alice',True)],QUERY)['value'] is True
    assert project_definition(RULE,[fact('Alice',True)],QUERY,{'?claimant':['Alice','Charlie']})['value'] is True


def test_self_claim_and_other_year_do_not_supply_a_witness():
    r=project_definition(RULE,[fact('Bob',True),fact('Alice',True,'2016')],QUERY,{'?claimant':['Alice','Bob']})
    assert r['value'] is None
    assert project_definition(RULE,[],QUERY,{'?claimant':['Bob']})['value'] is False


def test_unbound_or_incomplete_domain_is_rejected():
    with pytest.raises(ValueError,match='exactly'):project_definition(RULE,[],QUERY,{})
    with pytest.raises(ValueError,match='unique'):project_definition(RULE,[],QUERY,{'?claimant':['Alice','Alice']})
    bad=deepcopy(RULE);bad['body'][0]['arguments'][0]='?other'
    with pytest.raises(ValueError,match='Unbound'):project_definition(bad,[],QUERY)
