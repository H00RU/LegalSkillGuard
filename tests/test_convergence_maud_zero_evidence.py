import json
from copy import deepcopy

import jsonschema
import pytest

from experiments.convergence_revision5_maud_zero_evidence import (
    FIELD, SCHEMA_PROMPT, restore, transport, verify_exhaustive,
)


def sample():
    bool_answer = {'type': 'string', 'enum': ['Yes', 'No']}
    item = {'type': 'object', 'properties': {'answer': bool_answer,
            FIELD: {'type': 'array', 'maxItems': 0, 'items': {'type': 'integer'}}},
            'required': ['answer', FIELD], 'additionalProperties': False}
    root = {'type': 'object', 'properties': {'value': {'type': 'object', 'properties': {'q': item},
            'required': ['q'], 'additionalProperties': False}},
            'required': ['value'], 'additionalProperties': False}
    return {'messages': [{'role': 'system', 'content': 'Read the supplied text.\n' +
             SCHEMA_PROMPT + json.dumps(root)}, {'role': 'user', 'content': 'original input'}],
            'response_format': {'json_schema': {'schema': root}}}


def test_zero_evidence_field_remains_lossless():
    payload = sample()
    native = {'value': {'q': {'answer': 'Yes', FIELD: []}}}
    _, constant = transport(payload, 'literal_constant')
    messages, compact = transport(payload, 'omit_reconstruct')
    assert verify_exhaustive(payload) == 2
    assert messages[1] == payload['messages'][1]
    original = payload['response_format']['json_schema']['schema']
    assert restore(native, constant, original, 'literal_constant') == native
    assert restore({'value': {'q': {'answer': 'Yes'}}}, compact, original, 'omit_reconstruct') == native
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({'value': {'q': {'answer': 'Yes', FIELD: [0]}}}, constant)


def test_variable_evidence_is_never_erased():
    payload = sample()
    root = deepcopy(payload['response_format']['json_schema']['schema'])
    root['properties']['value']['properties']['q']['properties'][FIELD]['maxItems'] = 1
    payload['response_format']['json_schema']['schema'] = root
    payload['messages'][0]['content'] = SCHEMA_PROMPT + json.dumps(root)
    with pytest.raises(ValueError, match='variable evidence'):
        transport(payload, 'omit_reconstruct')
