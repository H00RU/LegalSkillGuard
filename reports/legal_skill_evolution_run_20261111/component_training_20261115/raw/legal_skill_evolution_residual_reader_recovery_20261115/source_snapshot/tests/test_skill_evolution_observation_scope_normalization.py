from copy import deepcopy

import pytest

from experiments import legal_skill_evolution_mixed_component_training as train
from legal_skill_guard.skill_evolution.case_observation_contract import apply_adapter
from legal_skill_guard.skill_evolution.component_binding_program import binding_program
from legal_skill_guard.skill_evolution.observation_component_library import component_value, convert, observation_schema
from legal_skill_guard.skill_evolution.observation_scope_normalization import normalize, WORLD_FIELDS
import json


@pytest.fixture(scope='module', params=['CoverageRecombine', 'FreeGlobalUpdate'])
def actual(request):
    root = train.ROOT / 'artifacts/legal_skill_evolution_family_guard_validation_union_fix_20261115'
    name = request.param + '/0'
    library = train.read(root / 'candidate_libraries' / (name + '.json'))
    row = next(train.read(p) for p in (root / 'family_results' / name).glob('*.json')
        if train.read(p)['source'].startswith('SARA_v2_Binary:5c29'))
    bank = train.actor.acquisition.previous.parent.OUT
    public = next(s['views'][0]['public'] for s in train.read(bank / 'SARA_corrected_TRAIN_views.json') if s['key'] == row['source'])
    kernel = train.actor.acquisition.current_case_interface(next(r['kernel'] for r in train.read(bank / 'SARA_native_kernel_bank.json') if r['source'] == row['source']))
    return library, row, public, kernel


def test_actual_co_residence_recovers_without_new_world_facts_or_modified_checks(actual):
    library, row, public, kernel = actual
    before = deepcopy(row['value'])
    result, receipts = normalize(library, kernel, public, before)
    assert before == row['value'] and receipts
    component = next(c for c in library['components'] if c['id'] == 'family_relationship_residence')
    part = component_value(library, component, kernel, public, result['family_relationship_residence']['views'][0])
    assert part['complete'] and not row['complete_alternatives']
    for receipt in receipts:
        fixed = {k: v for k, v in receipt['normalized_record'].items() if k in WORLD_FIELDS}
        for original in receipt['original_records']:
            assert {k: v for k, v in original.items() if k in WORLD_FIELDS} == fixed
    residences = [f['arguments'][0] for f in part['facts'] if f['predicate'] == 'residence_']
    assert len(residences) == 2  # Alice and Bob; duplicate linguistic framings are not extra events.
    assert not any(f['predicate'] == 'country_' for f in part['facts'])


def test_unread_or_distinct_residence_information_is_never_replaced_by_a_favorable_frame(actual):
    library, row, public, kernel = actual
    unread = deepcopy(row['value'])
    unread['family_relationship_residence']['views'][0]['extraction_status'] = 'unread'
    assert normalize(library, kernel, public, unread) == (unread, [])
    different = deepcopy(row['value'])
    records = different['family_relationship_residence']['views'][0]['residences']
    second = deepcopy(records[0]); second['location'] = 'a different place'; records.append(second)
    assert normalize(library, kernel, public, different) == (different, [])


def test_normalized_observation_uses_the_same_converter_in_execution_and_residual_trace(actual):
    library, row, public, kernel = actual
    observation, _ = normalize(library, kernel, public, row['value'])
    ids = ['family_relationship_residence']
    contract = {'binding_program': binding_program(library, ids),
        'observation_schema_json': json.dumps(observation_schema(library, ids))}
    traced = apply_adapter(contract, kernel, public, observation, literal_context={})
    assert traced == convert(library, ids, kernel, public, observation)
