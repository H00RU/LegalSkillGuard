from copy import deepcopy
import json

import jsonschema

from experiments import legal_skill_evolution_mixed_component_training as train
from legal_skill_guard.skill_evolution.literal_statutory_givens import constrain, _object_disjunction
from legal_skill_guard.skill_evolution.observation_source_review import review


def test_acquired_source_enum_constraint_removes_impossible_records_and_preserves_unread():
    schema = {'type': 'object', 'required': ['status', 'relationships'], 'properties': {
        'status': {'enum': ['complete', 'unread']},
        'relationships': {'type': ['array', 'null'], 'items': {'type': 'object',
            'required': ['source_term'], 'properties': {'source_term': {
                'type': 'string', 'enum': ['son', 'brother'], 'x-source-facts-token': True}}}}}}
    public = {'facts': 'The person is married.', 'question': 'Does a son qualify?'}
    result = constrain(schema, public, {'native_query': []})
    assert result['properties']['relationships']['maxItems'] == 0
    assert 'x-source-' not in json.dumps(result)
    assert jsonschema.Draft202012Validator(result).is_valid({'status': 'unread', 'relationships': None})
    assert not jsonschema.Draft202012Validator(result).is_valid({'status': 'complete', 'relationships': [{'source_term': 'son'}]})
    # A token is evidence only when it occurs in facts; 'person' is not 'son'.
    stated = constrain(schema, {'facts': 'Alice has a son, Bob.'}, {'native_query': []})
    jsonschema.validate({'status': 'complete', 'relationships': [{'source_term': 'son'}]}, stated)
    assert schema['properties']['relationships']['items']['properties']['source_term']['enum'] == ['son', 'brother']


def test_actual_unchanged_brother_hallucination_is_now_in_the_existing_kinship_review():
    path = train.ROOT / 'artifacts/legal_skill_evolution_literal_guard_probe_20261115/CoverageRecombine/after.json'
    row = train.read(path)
    assert any(f['predicate'] == 'brother_' for b in row['grounded']['bindings'] for f in b['inputs']['facts'])
    checked = review(row['source'], row['grounded'])
    assert checked['failures'] == 1
    assert checked['checks'][1]['passed']  # The separate literal-given repair remains valid.


def test_actual_free_teacher_discriminator_preserves_required_fields_and_exact_host_language():
    root = train.ROOT / 'artifacts/legal_skill_evolution_family_guard_validation_20261115'
    library = train.read(root / 'candidate_libraries/FreeGlobalUpdate/0.json')
    component = next(c for c in library['components'] if c['id'] == 'family_relationship_residence')
    original = json.loads(component['schema_json'])['properties']['views']['items']['properties']['relationships']['items']
    compiled = _object_disjunction(original)
    value = {'relation_type': 'son', 'source_basis': 'explicit_son', 'source_cue': 'son',
        'direction_form': 'reference_has_related', 'source_term': 'Alice has a son, Bob',
        'related_person': 'Bob', 'reference_person': 'Alice', 'start_date': None,
        'start_text': None, 'end_date': None, 'end_text': None,
        'witnesses': [{'field': 'facts', 'quote': 'Alice has a son, Bob'}]}
    before, after = jsonschema.Draft202012Validator(original), jsonschema.Draft202012Validator(compiled)
    assert before.is_valid(value) and after.is_valid(value)
    variants = []
    for key in original['required']:
        changed = deepcopy(value); changed.pop(key); variants.append(changed)
    for key, val in [('source_basis', 'explicit_brother'), ('source_cue', 'brother'), ('source_cue', 'absent'), ('extra', True)]:
        changed = deepcopy(value); changed[key] = val; variants.append(changed)
    assert all(before.is_valid(v) == after.is_valid(v) for v in variants)


def test_actual_failed_c_partial_record_cannot_satisfy_the_common_required_fields():
    root = train.ROOT / 'artifacts/legal_skill_evolution_family_guard_validation_20261115'
    library = train.read(root / 'candidate_libraries/CoverageRecombine/0.json')
    original = json.loads(next(c for c in library['components'] if c['id'] == 'family_relationship_residence')['schema_json'])
    bank = train.actor.acquisition.previous.parent.OUT
    public = next(s for s in train.read(bank / 'SARA_corrected_TRAIN_views.json') if s['key'].startswith('SARA_v2_Binary:a519'))
    kernel = next(r['kernel'] for r in train.read(bank / 'SARA_native_kernel_bank.json') if r['source'] == public['key'])
    schema = constrain(original, public['views'][0]['public'], kernel)
    partial = {'relation_type': 'son', 'source_basis': 'explicit_son', 'relation_cue': 'son'}
    projected = schema['properties']['views']['items']['properties']['relationships']['items']
    assert not jsonschema.Draft202012Validator(projected).is_valid(partial)
    for branch in projected['oneOf']:
        assert {'related_person', 'reference_person', 'source_term', 'witnesses'} <= set(branch['required'])
