"""A paid starred numeric total uses exact vector addition, without syntax repair."""
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
import json

import pytest

from legal_skill_guard.rr.coverage import SourceLedger, FiniteTheory, Residual, Unsupported, complete, evaluate, digest
from legal_skill_guard.rr.ir_types import check_expression, IRTypeError
from legal_skill_guard.rr.pal_frontend import parse_pal, render_pal
from legal_skill_guard.rr.source_program import program_schema
from legal_skill_guard.rr.scoped_program import compile_query
from legal_skill_guard.rr.wire_validation import validate_wire
from legal_skill_guard.rr.rule_templates import matching_rule_template, instantiate_rule_template

ROOT = Path(__file__).resolve().parents[1]
def op(name, *args): return {'op': name, 'args': list(args)}
def var(name): return {'var': name}


@pytest.mark.parametrize('text', ['sum(fees)', 'add(*fees)', 'sum_numbers(fees)'])
def test_numeric_vector_sum_syntax_has_one_identical_typed_executable_meaning(text):
    program = parse_pal('fees = [20, 30, 40]\nquery = ' + text)
    assert program['query'] == op('sum_numbers', var('fees'))
    query = compile_query(program['nodes'], program['query'], {})
    assert query.execute({})['answer'] == 90
    assert parse_pal(render_pal(program)) == program
    source = json.loads((ROOT / 'artifacts/rr_method_runtime_20261107/reference_text_airline7_v17_20261108/seal.json').read_text())['source']
    validate_wire(program, program_schema(source))


def test_exact_numeric_sum_rejects_missing_boolean_string_and_mixed_values():
    query = op('sum_numbers', var('fees'))
    assert check_expression({'query': query}, {'fees': [1, Fraction(1, 2)]})['result_types'] == ['number']
    assert evaluate(query, {'fees': [1, Fraction(1, 2)]}) == Fraction(3, 2)
    for values in [None, True, '30', [20, True], [20, '30'], [20, None], {'a': 20}]:
        with pytest.raises(IRTypeError): check_expression({'query': query}, {'fees': values})
        with pytest.raises(Unsupported): evaluate(query, {'fees': values})
    with pytest.raises(Unsupported): evaluate(query, {})
    bad_branch = op('if', False, op('sum_numbers', op('array', 20, True)), 0)
    with pytest.raises(IRTypeError): check_expression({'query': bad_branch}, {})


def test_numeric_sum_cannot_hide_an_undefined_value_in_one_completion():
    ledger = SourceLedger.from_text('Fee schedule\nUnresolved applicability')
    ledger.clauses[0] = replace(ledger.clauses[0], state='compiled')
    vector = op('if', var('enabled'), op('array', 20, 30), op('array', op('number_at', op('array', 20), 5)))
    query = op('sum_numbers', vector)
    check_expression({'query': query}, {}, slot_types={'enabled': {'boolean'}})
    theory = FiniteTheory(ledger, {}, {'enabled': (False, True)}, query,
                          [Residual('s1', ('enabled',), 'public_structure', False)])
    result = complete(theory)
    assert result.status == 'unsupported_no_certificate' and 'in-range' in result.reason


def test_real_paid_starred_total_is_parsed_without_inventing_its_missing_current_observations():
    stage = ROOT / 'artifacts/rr_method_runtime_20261107/reference_text_airline7_v17_20261108'
    seal = json.loads((stage / 'seal.json').read_text())
    paid = json.loads((stage / 'calls' / digest(stage.name + ':parse:1') / 'result.json').read_text())
    assert 'add(*excess_fees)' in paid['content']
    match = matching_rule_template(seal['source'], seal['config']['library'])
    functions = [row['name'] for field in ('scopes', 'clauses') for row in match['program'][field]]
    program = parse_pal(paid['content'], external_functions=functions)
    assert program['query']['args'][-1] == op('sum_numbers', var('excess_fees'))
    from jsonschema import ValidationError
    with pytest.raises(ValidationError):
        instantiate_rule_template(seal['source'], match, {'program_lines':paid['content'].splitlines()}, library=seal['config']['library'])
