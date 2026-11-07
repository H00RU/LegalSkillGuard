"""Actual rejected executor output: diagnosis never changes it or supplies truth."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
from jsonschema import ValidationError

from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.source_program import program_schema,proper_rule_subexpression
from legal_skill_guard.rr.source_validation import validation_feedback
from legal_skill_guard.rr.wire_validation import validate_wire


def actual_failure():
    root=Path(__file__).resolve().parents[1]
    raw=json.loads((root/'tests/fixtures/rr_actual_executor_source_v1.json').read_text())
    source=next(s for s in json.loads((root/'data/packets/rr_v2/public_train.json').read_text())['sources']
        if s['key']=='SARA_v2_Binary:743ac2e5258037a15b0e3549f47db2e50d051ec4449a3493120048fee188a814')
    return source,raw


def test_actual_failure_reports_field_types_provenance_and_missing_guard_without_mutation():
    source,raw=actual_failure();before=digest(raw)
    result=validation_feedback(source,raw)
    rows={row['path']:row for row in result['issues']}
    assert rows['scopes[0].condition']['expected']=='boolean'
    assert rows['scopes[0].condition']['actual']==['number']
    assert rows['query.args[0]']['actual']==['number']
    assert rows['bindings[0].value']['actual']['value']==2018
    assert rows['observations[0].predicate_source']['actual']['role']=='fact'
    assert rows['scopes']['actual']['source']=='s5'
    assert 'rule_residuals[0].quote' in rows and 'rule_residuals[0].name' in rows
    assert result['source_only'] and not result['grading_information_used'] and not result['candidate_modified']
    assert digest(raw)==before


def test_schema_closes_actual_fact_as_rule_and_numeric_literal_guard_before_execution():
    source,raw=actual_failure();schema=program_schema(source)
    with pytest.raises(ValidationError):validate_wire(raw,schema)
    properties=schema['properties']['observations']['items']['properties']
    validate_wire('s10',properties['entity_source'])
    with pytest.raises(ValidationError):validate_wire('s9',properties['entity_source'])
    with pytest.raises(ValidationError):validate_wire('s10',properties['predicate_source'])
    for condition in (2018,1,'quoted policy'):
        guard_schema={'$defs':schema['$defs'],'$ref':'#/$defs/bool_expr'}
        with pytest.raises(ValidationError):validate_wire(condition,guard_schema)
    validate_wire({'op':'lt','args':[2017,2018]},{'$defs':schema['$defs'],'$ref':'#/$defs/bool_expr'})


def test_removing_a_number_prefix_does_not_make_an_entire_rule_a_subexpression():
    assert not proper_rule_subexpression('An individual qualifies.','(2) An individual qualifies.')
    assert not proper_rule_subexpression('An individual qualifies.','(a) (2) An individual qualifies.')
    assert proper_rule_subexpression('individual','(2) An individual qualifies.')


def test_valid_paid_scope_program_remains_valid_under_stricter_contract():
    from legal_skill_guard.rr.source_program import compile_source
    root=Path(__file__).resolve().parents[1];source,_=actual_failure()
    raw=json.loads((root/'tests/fixtures/rr_scope_v5_binding_projection.json').read_text())['canonical_program']
    before=deepcopy(raw)
    compiled=compile_source(source,raw)
    assert raw==before and compiled['missing_scope_sources']==[]
