import pytest

from legal_skill_guard.skill_evolution.native import record_schema
from legal_skill_guard.skill_evolution.terminal_json import recover_json


def test_recover_closed_values_inside_whitespace_only_cutoff():
    schema = record_schema({'value': record_schema({'answer': {'type': 'string'},
                                                    'evidence': {'type': 'array'}})})
    output, closure = recover_json('{"value":{"answer":"an escaped \\" }", "evidence":[1, 2] \n ', schema,
                                   finish_reason='length')
    assert output == {'value': {'answer': 'an escaped " }', 'evidence': [1, 2]}}
    assert closure == {'finish_reason': 'length', 'trailing_whitespace_chars': 3,
                       'object_closures': 2, 'model_values_changed': False}


def test_forbid_partial_values_unrestricted_keys_and_duplicate_answers():
    schema = record_schema({'value': {'type': 'array'}})
    for raw in ('{"value":[1,2 \n', '{"value":"only a fragment ', '{"value":[1]',
                '{"value":[1],"value":[2]  '):
        with pytest.raises(ValueError):
            recover_json(raw, schema, finish_reason='length')
    with pytest.raises(ValueError, match='every permitted schema key'):
        recover_json('{"value":[1]  ', {**schema, 'additionalProperties': True}, finish_reason='length')
