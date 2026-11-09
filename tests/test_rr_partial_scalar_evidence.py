import pytest

from legal_skill_guard.rr.partial_scalar_evidence import certify
from legal_skill_guard.rr.semantic_contracts import ContractError

SIG={'relationship':'boolean','days':'integer','year_days':'integer','age':'integer','younger':'boolean','joint':'boolean'}
PROGRAM='relationship and 2 * days > year_days and age < 25 and younger and not joint'
DOMAIN='days >= 0 and year_days > 0 and days <= year_days and age >= 0'


def checked(days=34):
    return {'days':{'value':days,'evidence':'a source-verified original residence interval'},
            'year_days':{'value':365,'evidence':'calendar-year query'}}


def test_decisive_verified_evidence_does_not_require_unrelated_unknowns():
    result=certify(PROGRAM,SIG,DOMAIN,checked())
    assert result['answer']=='Contradiction'
    assert set(result['proof_support'])=={'days','year_days'}
    assert set(result['unknown_inputs'])=={'age','younger','joint','relationship'}
    assert all(v==[False,True] for v in result['withhold_each_support_value'].values())


def test_untrusted_claims_never_enter_constraints():
    a=certify(PROGRAM,SIG,DOMAIN,checked(),quarantined=[{'field':'age','claimed':3}])
    b=certify(PROGRAM,SIG,DOMAIN,checked(),quarantined=[{'field':'age','claimed':1000}])
    assert a['possible_values']==b['possible_values']==[False]
    assert 'age' not in a['checked_bindings']


def test_missing_decisive_evidence_preserves_uncertainty():
    result=certify(PROGRAM,SIG,DOMAIN,{'year_days':checked()['year_days']})
    assert result['answer'] is None and result['possible_values']==[False,True]


def test_wrong_evidence_type_is_rejected():
    values=checked();values['days']['value']=False
    with pytest.raises(ContractError,match='wrong scalar type'):certify(PROGRAM,SIG,DOMAIN,values)


def test_inconsistent_evidence_cannot_certify_arbitrary_false():
    with pytest.raises(ContractError,match='Inconsistent'):certify(PROGRAM,SIG,DOMAIN,checked(400))


def test_empty_or_unknown_evidence_names_rejected():
    with pytest.raises(ContractError,match='explicit source evidence'):
        certify(PROGRAM,SIG,DOMAIN,{'days':{'value':34,'evidence':''}})
    with pytest.raises(ContractError,match='names'):
        certify(PROGRAM,SIG,DOMAIN,{'target':{'value':False,'evidence':'an unsupported target'}})
