from copy import deepcopy
from pathlib import Path
import json
import pytest
from experiments.rr_v2_legal_evidence_contract_v2 import source_units,schema,validate_guidance
from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues

API=[{'name':'status','roles':['subject'],'functional':False,'meaning':'fixture'}]
POLICIES=[{'section':1,'rules':'First paragraph.\n\n  A source condition.\n\nThird.'}]
UNITS=source_units(POLICIES)
VALUE={'contracts':{'status':{'direct_assertion':'The case explicitly asserts this status for this person.',
    'insufficient_without_inference':['One legal condition alone.'],'source_unit_ids':[1]}},'unresolved':[]}


def test_source_unit_offsets_recover_exact_original_bytes():
    for u in UNITS:
        assert POLICIES[0]['rules'][u['start_character']:u['end_character']]==u['text']
    assert UNITS[1]['text']=='  A source condition.'


def test_unit_expansion_never_retypes_source_quote():
    out=validate_guidance(VALUE,API,UNITS)
    assert out['entries'][0]['source_quotes']==[UNITS[1]] and not out['semantic_fidelity_proved']


def test_fixed_keys_reject_missing_entry():
    v=deepcopy(VALUE);v['contracts']={}
    with pytest.raises(ValueError,match='coverage'):validate_guidance(v,API,UNITS)


def test_no_substantive_quote_fabrication():
    v=deepcopy(VALUE);v['contracts']['status']['source_unit_ids']=[99]
    with pytest.raises(ValueError,match='Unknown'):validate_guidance(v,API,UNITS)


def test_substantive_unit_required():
    v=deepcopy(VALUE);v['contracts']['status']['source_unit_ids']=[]
    with pytest.raises(ValueError,match='Missing substantive'):validate_guidance(v,API,UNITS)


def test_duplicate_unit_rejected():
    v=deepcopy(VALUE);v['contracts']['status']['source_unit_ids']=[1,1]
    with pytest.raises(ValueError,match='Duplicate'):validate_guidance(v,API,UNITS)


def test_actual_first_response_contradiction_is_rejected():
    root=Path(__file__).resolve().parents[1]
    raw=json.loads((root/'artifacts/rr_method_redesign_20261109/legal_evidence_contract_source_v1_20261110/result.json').read_text())
    row=next(x for x in raw['value']['entries'] if x['predicate']=='section_151c_applies')
    v=deepcopy(VALUE);v['contracts']['status']={'direct_assertion':row['direct_evidence'],
        'insufficient_without_inference':row['insufficient_evidence'],'source_unit_ids':[1]}
    with pytest.raises(ValueError,match='Same long assertion'):validate_guidance(v,API,UNITS)


def test_empty_direct_criterion_rejected():
    v=deepcopy(VALUE);v['contracts']['status']['direct_assertion']=' '
    with pytest.raises(ValueError,match='Empty'):validate_guidance(v,API,UNITS)


def test_fixed_key_schema_is_supported():
    assert not strict_output_schema_issues(schema(API,UNITS))
