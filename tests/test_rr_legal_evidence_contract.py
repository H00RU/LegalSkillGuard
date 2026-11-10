from copy import deepcopy
import pytest
from experiments.rr_v2_legal_evidence_contract import validate_contract,CONTRACT,FRAMES
from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues

API=[{'name':'status','roles':['subject'],'functional':False,'meaning':'fixture'},
     {'name':'case_subject_year','roles':['person','year'],'functional':False,'meaning':'fixture'}]
POLICY=[{'rules':'An explicitly stated status is given.'}]
VALUE={'entries':[{'predicate':'status','direct_evidence':'The status is explicitly stated.',
    'insufficient_evidence':['A possible consequence is not explicit.'],'source_quotes':['An explicitly stated status is given.']},
    {'predicate':'case_subject_year','direct_evidence':'Named people and years.','insufficient_evidence':[],'source_quotes':[]}],
    'unresolved':[]}


def test_structure_is_not_a_fidelity_certificate():
    out=validate_contract(VALUE,API,POLICY)
    assert out['source_semantic_correctness_not_proved']


def test_unknown_or_duplicate_predicate_rejected():
    v=deepcopy(VALUE);v['entries'][1]['predicate']='status'
    with pytest.raises(ValueError,match='duplicate'):validate_contract(v,API,POLICY)


def test_missing_predicate_rejected():
    v=deepcopy(VALUE);v['entries'].pop()
    with pytest.raises(ValueError,match='Missing'):validate_contract(v,API,POLICY)


def test_unsupported_quote_rejected():
    v=deepcopy(VALUE);v['entries'][0]['source_quotes']=['Other words.']
    with pytest.raises(ValueError,match='absent'):validate_contract(v,API,POLICY)


def test_missing_substantive_quote_rejected():
    v=deepcopy(VALUE);v['entries'][0]['source_quotes']=[]
    with pytest.raises(ValueError,match='No governing'):validate_contract(v,API,POLICY)


def test_empty_guidance_rejected():
    v=deepcopy(VALUE);v['entries'][0]['direct_evidence']=' '
    with pytest.raises(ValueError,match='Empty'):validate_contract(v,API,POLICY)


def test_schemas_are_supported():
    assert not strict_output_schema_issues(CONTRACT)
    assert not strict_output_schema_issues(FRAMES)
