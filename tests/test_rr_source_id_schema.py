"""Actual source-ID membership is preserved across the finite grammar repair."""
import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator,ValidationError
import pytest

from legal_skill_guard.rr.source_program import compile_source,program_schema,source_unit_schema
from legal_skill_guard.rr.source_structure import inspect_source
from legal_skill_guard.rr.wire_validation import validate_wire


def test_all128_actual_source_role_sets_keep_exact_membership_including_gaps():
    root=Path(__file__).resolve().parents[1]
    sources=json.loads((root/'data/packets/rr_v2/public_train.json').read_text())['sources']
    for source in sources:
        structure=inspect_source(source);units={c.id for c in structure.ledger.clauses}
        groups=[units]+[{k for k,v in structure.roles.items() if v['role']==role} for role in ('rule','fact')]
        probes=units|{f's{i}' for i in range(len(units),len(units)+11)}|{'foreign','s01','s-1','s0.0','s0\n','s0\r','\ns0','s1\n',0,None}
        for members in groups:
            if not members:continue
            validator=Draft202012Validator(source_unit_schema(members))
            assert all(validator.is_valid(value)==(value in members) for value in probes)


def test_actual_enum_leak_stays_rejected_and_wire_valid_whole_rule_stays_semantically_rejected():
    from copy import deepcopy
    root=Path(__file__).resolve().parents[1]
    sources={s['key']:s for s in json.loads((root/'data/packets/rr_v2/public_train.json').read_text())['sources']}
    records=json.loads((root/'tests/fixtures/rr_actual_method_c2_enum.json').read_text())['records']
    airline,oe=records
    with pytest.raises(ValidationError):validate_wire(json.loads(airline['raw_content']),program_schema(sources[airline['source']]))
    source=sources[oe['source']];program=json.loads(oe['raw_content'])
    with pytest.raises(ValidationError) as failure:validate_wire(program,program_schema(source))
    assert list(failure.value.path)==['query']
    # Isolate the existing residual check behind a valid variable-shaped root.
    # This negative test variant is never a repaired prediction or scored IR.
    component=deepcopy(program)
    component['query']={'var':program['clauses'][0]['name']}
    validate_wire(component,program_schema(source))
    with pytest.raises(Exception,match='proper subexpression'):compile_source(source,component)
    assert program==json.loads(oe['raw_content'])


def test_actual_repeated_identifier_cannot_exhaust_the_output_but_source_quotes_remain_unbounded():
    root=Path(__file__).resolve().parents[1]
    value=json.loads((root/'tests/fixtures/rr_actual_method_c2_repetition.json').read_text())
    assert value['finish_reason']=='length' and value['completion_tokens']==8192
    with pytest.raises(json.JSONDecodeError):json.loads(value['raw_content'])
    names=re.findall(r'"name"\s*:\s*"([^"\\]*)"',value['raw_content']);longest=max(names,key=len)
    assert len(longest)>64 and longest.count('60_days_fuel_and_provisions')>1
    source=next(s for s in json.loads((root/'data/packets/rr_v2/public_train.json').read_text())['sources'] if s['key']==value['source'])
    schema=program_schema(source);identifier=schema['$defs']['binding']['anyOf'][0]['properties']['name']
    validate_wire(longest,{'type':'string','pattern':'^[A-Za-z_][A-Za-z0-9_]*$'})
    with pytest.raises(ValidationError):validate_wire(longest,identifier)
    validate_wire('n0',identifier)
    # This is an internal representation bound, never truncation of quotations.
    validate_wire(longest,schema['properties']['rule_residuals']['items']['properties']['quote'])
