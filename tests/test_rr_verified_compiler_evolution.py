"""Admission integrity of real, independently checked earlier TRAIN programs."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.compiler_evolution import promote_verified_horn,select_compiler_templates
from legal_skill_guard.rr.compiler_templates import validate_template

ROOT=Path(__file__).resolve().parents[1]
STAGE=ROOT/'artifacts/rr_method_runtime_20261107/method_runtime_reference_v10_20261109'


def actual():
    seal=json.loads((STAGE/'seal.json').read_text());key=seal['sources']['train'][8]
    source=next(s for s in json.loads((ROOT/'data/packets/rr_v2/public_train.json').read_text())['sources'] if s['key']==key)
    record=json.loads((STAGE/'build/sources'/(digest(key)+'.json')).read_text())
    return seal,source,record


def promote(seal,source,record):
    return promote_verified_horn(source,record,train_sources=seal['sources']['train'],
        ledger_path=(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3').resolve())


def test_real_model_program_can_enter_after_independent_check_and_physical_provenance():
    seal,source,record=actual();t=promote(seal,source,record)
    assert t['origin']['role']=='executor' and not validate_template(t).export()['missing_units']
    assert t['code']==record['prediction']['model_horn_code']


def test_nontrain_and_changed_program_cannot_be_promoted():
    seal,source,record=actual()
    with pytest.raises(ValueError,match='TRAIN'):
        promote_verified_horn(source,record,train_sources=[],ledger_path=ROOT/'unused')
    corrupt=deepcopy(record);corrupt['prediction']['model_horn_code']+='\n'
    with pytest.raises(ValueError,match='actual model response'):promote(seal,source,corrupt)


def test_unsettled_or_unmatched_model_wire_cannot_enter():
    seal,source,record=actual();corrupt=deepcopy(record)
    for c in corrupt['prediction']['calls']:c['request_hash']='no-paid-origin'
    with pytest.raises(ValueError,match='settled physical origin'):promote(seal,source,corrupt)


def test_source_self_example_is_rejected_even_under_bounded_retrieval():
    seal,source,record=actual();t=promote(seal,source,record)
    with pytest.raises(ValueError,match='current program'):select_compiler_templates(source,[t],1)
