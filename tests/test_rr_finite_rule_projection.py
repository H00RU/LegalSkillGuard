"""Regress existing source-guard evaluation; no second projection implementation."""
from copy import deepcopy
import pytest
from legal_skill_guard.rr.legal_predicate_skills import evaluate_guard,run

RULE={'id':'source-condition','head':{'predicate':'applies','arguments':['?claimant','?subject','?year'],'positive':True},
 'body':[{'predicate':'allowed','arguments':['?claimant','?subject','?year'],'positive':True}],
 'different':[{'left':'?claimant','right':'?subject'}],'authority':'fixture','quote':'source condition','guard_quote':'source condition'}
QUERY={'predicate':'applies','arguments':[None,'Bob','2017'],'positive':True}


def programme(rule=RULE):
    return {'predicates':[{'name':p,'roles':['claimant','subject','year'],'functional':False,'meaning':'fixture'} for p in ['applies','allowed']],
        'rules':[rule],'priorities':[],'unresolved':[]}


def fact(person,value,year='2017'):
    return {'atom':{'predicate':'allowed','arguments':[person,'Bob',year],'positive':value},'quote':'explicit fixture'}


def check(facts,q=QUERY,domains=None,rule=RULE):
    return evaluate_guard(programme(rule),{'facts':facts,'query':q,'unresolved':[]},rule['id'],domains=domains)['condition_value']


def test_one_negative_does_not_close_an_open_world():
    assert check([fact('Alice',False)]) is None


def test_ground_missing_evidence_is_still_unknown():
    q=QUERY|{'arguments':['Alice','Bob','2017']}
    assert check([],q) is None
    assert check([fact('Alice',False)],q) is False


def test_closed_projection_uses_explicit_negatives_only():
    assert check([fact('Alice',False)],domains={0:['Alice','Bob']}) is False


def test_missing_or_inconsistent_candidate_is_unknown():
    assert check([fact('Alice',False)],domains={0:['Alice','Charlie']}) is None
    assert check([fact('Alice',False),fact('Alice',True)],domains={0:['Alice']}) is None


def test_explicit_positive_settles_an_open_projection():
    assert check([fact('Alice',True)]) is True
    assert check([fact('Alice',True)],domains={0:['Alice','Charlie']}) is True


def test_self_claim_and_other_year_do_not_supply_a_witness():
    assert check([fact('Bob',True),fact('Alice',True,'2016')],domains={0:['Alice','Bob']}) is None
    assert check([],domains={0:['Bob']}) is False


def test_unbound_or_incomplete_domain_rejected():
    with pytest.raises(ValueError,match='exactly'):check([],domains={})
    with pytest.raises(ValueError,match='set'):check([],domains={0:['Alice','Alice']})
    bad=deepcopy(RULE);bad['body'][0]['arguments'][0]='?other'
    with pytest.raises(ValueError,match='Unbound'):check([],rule=bad)


@pytest.mark.parametrize('positive',[True,False])
def test_contradictory_signed_fact_cannot_determine_either_query_polarity(positive):
    q={'predicate':'allowed','arguments':['Alice','Bob','2017'],'positive':positive}
    result=run(programme(),{'facts':[fact('Alice',True),fact('Alice',False)],'query':q,'unresolved':[]})
    assert result['answer'] is None and not result['query_supported'] and not result['query_refuted']


@pytest.mark.parametrize('positive',[True,False])
def test_contradictory_signed_amount_is_not_decisive_refuting_evidence(positive):
    p={'predicates':[{'name':'amount','roles':['subject','value'],'functional':True,'meaning':'fixture'}],
       'rules':[],'priorities':[],'unresolved':[]}
    atom={'predicate':'amount','arguments':['A','2000'],'positive':True}
    facts=[{'atom':atom,'quote':'positive'},{'atom':atom|{'positive':False},'quote':'negative'}]
    result=run(p,{'facts':facts,'query':atom|{'positive':positive},'unresolved':[]})
    assert result['answer'] is None and not result['query_supported'] and not result['query_refuted']
