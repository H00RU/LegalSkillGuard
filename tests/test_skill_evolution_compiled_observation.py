import json
from types import SimpleNamespace

import pytest

from legal_skill_guard.skill_evolution.compiled_observation import execute


SCHEMA = {'type': 'object', 'required': ['reading'], 'additionalProperties': False,
    'properties': {'reading': {'type': 'object', 'required': ['text', 'status'],
        'additionalProperties': False, 'properties': {
            'text': {'type': 'string'}, 'status': {'enum': ['complete', 'unread']}}}}}


def test_observer_reads_current_facts_without_question_or_native_context():
    program = '''def apply(inputs,premises):
    if set(inputs) != {'facts'} or premises:
        return {'text':'context_leaked','status':'unread'}
    return {'text':inputs['facts'],'status':'complete'}
'''
    component = {'id': 'reading', 'observation_program': program}
    value, receipt = execute(component, {'facts': 'current source', 'question': 'hidden claim'}, SCHEMA)
    assert value['reading'] == {'text': 'current source', 'status': 'complete'}
    assert receipt['new_physical_requests'] == 0
    assert receipt['question_or_native_labels_supplied'] is False
    assert receipt['source_semantics_certified'] is False
    other, other_receipt = execute(component, {'facts': 'different source'}, SCHEMA)
    assert other['reading']['text'] == 'different source'
    assert other_receipt['facts_sha256'] != receipt['facts_sha256']


def test_observer_unknown_and_strict_schema_are_preserved():
    component = {'id': 'reading', 'observation_program': '''def apply(inputs,premises):
    return {'text':'','status':'unread'}
'''}
    value, _ = execute(component, {'facts': 'ambiguous source'}, SCHEMA)
    assert value['reading']['status'] == 'unread'
    component['observation_program'] = "def apply(inputs,premises):\n    return {'text':'missing status'}"
    with pytest.raises(Exception, match='status'):
        execute(component, {'facts': 'source'}, SCHEMA)


def test_observer_cannot_encode_a_native_answer():
    component = {'id': 'reading', 'observation_program':
        "def apply(inputs,premises):\n    return {'text':'Entailment','status':'complete'}"}
    with pytest.raises(ValueError, match='native answer'):
        execute(component, {'facts': 'source'}, SCHEMA)


def test_actual_component_route_and_replay_dispatch_no_model(tmp_path):
    from experiments.legal_skill_evolution_observation_component_execute import read_component
    client = SimpleNamespace(artifacts=tmp_path, ledger=SimpleNamespace(run_id='offline'))
    component = {'id': 'reading', 'schema_json': json.dumps(SCHEMA['properties']['reading']),
        'observation_program': "def apply(inputs,premises):\n    return {'text':inputs['facts'],'status':'complete'}"}
    args = (client, {}, 'original_TRAIN', component, {'native_query': []}, {'facts': 'current source'})
    first = read_component(*args, purpose='skill_actor')
    again = read_component(*args, purpose='skill_actor')
    assert first == again and first[1]['new_physical_requests'] == 0
    assert len(list((tmp_path / 'program_observations').glob('*.json'))) == 1
    assert not (tmp_path / 'component_reads').exists()


def test_paired_version_identity_includes_the_acquired_observer():
    from legal_skill_guard.skill_evolution.paired_observation_recombination import _library_key
    component = {'id': 'reading', 'meaning': 'reading', 'prompt': 'read source',
        'schema_json': '{}', 'conversion_program': 'converter', 'complete_native_families': []}
    a = {'shared_helpers': '', 'components': [{**component, 'observation_program': 'observer one'}]}
    b = {'shared_helpers': '', 'components': [{**component, 'observation_program': 'observer two'}]}
    assert _library_key(a) != _library_key(b)


def test_actual_observer_standard_string_padding_has_python_semantics():
    component = {'id': 'reading', 'observation_program': '''def apply(inputs,premises):
    return {'text':inputs['facts'].zfill(3),'status':'complete'}
'''}
    value, _ = execute(component, {'facts': '-7'}, SCHEMA)
    assert value['reading']['text'] == '-07'
    component['observation_program'] = "def apply(inputs,premises):\n    return inputs['facts'].encode()"
    with pytest.raises(ValueError, match='Unsupported attribute'):
        execute(component, {'facts': 'unsupported conversion'}, SCHEMA)


def test_actual_observer_dict_fromkeys_preserves_first_occurrence_order():
    component={'id':'reading','observation_program':'''def apply(inputs,premises):
    return {'text':'|'.join(list(dict.fromkeys(inputs['facts'].split()))),'status':'complete'}
'''}
    value,_=execute(component,{'facts':'Bob Alice Bob Charlie Alice'},SCHEMA)
    assert value['reading']['text']=='Bob|Alice|Charlie'
