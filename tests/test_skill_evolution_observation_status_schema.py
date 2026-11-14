from copy import deepcopy
from itertools import product
import json
from pathlib import Path

import jsonschema

from legal_skill_guard.skill_evolution.observation_status_schema import compile_status_conditions


def test_required_status_disjunction_keeps_complete_and_unread_languages():
    schema = {'type': 'object', 'additionalProperties': False,
        'required': ['extraction_status', 'births', 'witnesses'], 'properties': {
            'extraction_status': {'enum': ['complete', 'unread']},
            'births': {'type': ['array', 'null'], 'items': {'type': 'string'}},
            'witnesses': {'type': 'array', 'items': {'type': 'string'}}},
        'allOf': [{'if': {'properties': {'extraction_status': {'const': 'complete'}}},
            'then': {'properties': {'births': {'type': 'array'}, 'witnesses': {'minItems': 1}}}}]}
    original = deepcopy(schema)
    compiled, receipt = compile_status_conditions(schema)
    assert schema == original and len(receipt) == 1
    old = jsonschema.Draft202012Validator(schema)
    new = jsonschema.Draft202012Validator(compiled)
    for status, births, witnesses in product(('complete', 'unread'), (None, [], ['stated birth']), ([], ['source quote'])):
        value = {'extraction_status': status, 'births': births, 'witnesses': witnesses}
        assert old.is_valid(value) == new.is_valid(value)
    assert new.is_valid({'extraction_status': 'unread', 'births': None, 'witnesses': []})
    assert not new.is_valid({'extraction_status': 'complete', 'births': None, 'witnesses': ['source quote']})


def test_actual_paid_component_outputs_keep_identical_host_acceptance():
    root = Path('artifacts/legal_skill_evolution_mixed_component_training_source_review_20261115')
    checked = compiled_count = 0
    for raw in (root / 'raw_responses').glob('*.json'):
        response = json.loads(raw.read_text())
        request = json.loads((Path(response['artifact_directory']) / 'request.json').read_text())
        schema = json.loads(request['payload']['messages'][-1]['content'])['output_schema']
        compiled, receipts = compile_status_conditions(schema)
        value = json.loads(response['content'])
        assert jsonschema.Draft202012Validator(schema).is_valid(value) == jsonschema.Draft202012Validator(compiled).is_valid(value)
        checked += 1
        compiled_count += bool(receipts)
    assert checked >= 20 and compiled_count >= 5


def test_optional_status_guard_is_not_reinterpreted_as_required():
    schema = {'type': 'object', 'properties': {'status': {'enum': ['complete', 'unread']}},
        'allOf': [{'if': {'properties': {'status': {'const': 'complete'}}}, 'then': {'properties': {}}}]}
    compiled, receipt = compile_status_conditions(schema)
    assert compiled == schema and receipt == []


def test_integer_number_intersection_preserves_amounts():
    schema = {'type': 'object', 'required': ['status', 'amount'], 'properties': {
        'status': {'enum': ['complete', 'unread']}, 'amount': {'type': ['integer', 'null']}},
        'allOf': [{'if': {'properties': {'status': {'const': 'complete'}}},
            'then': {'properties': {'amount': {'type': 'number'}}}}]}
    compiled, receipts = compile_status_conditions(schema)
    assert receipts
    for status, amount in product(('complete', 'unread'), (None, 2000, 2.5)):
        value = {'status': status, 'amount': amount}
        assert jsonschema.Draft202012Validator(schema).is_valid(value) == jsonschema.Draft202012Validator(compiled).is_valid(value)
