from copy import deepcopy
import json
from pathlib import Path

import pytest

from experiments import legal_skill_evolution_observation_component_execute as actor
from legal_skill_guard.skill_evolution.observation_component_library import validate
from legal_skill_guard.skill_evolution.observation_proposal_format import recover_format


def test_all_four_actual_B5_proposals_recover_only_redundant_syntax_and_unusable_metadata():
    root = Path('artifacts/legal_skill_evolution_mixed_component_training_line_transport_20261115/B5')
    task = actor.read(root / 'teacher_task.json')
    kernel = task['acquisition_cases'][0]['kernel']
    for arm in actor.acquisition.ARMS:
        base = task['current_libraries_both_available'][arm]
        for original in actor.read(root / arm / 'teacher.json')['value']['candidates']:
            before = deepcopy(original)
            recovered, receipts = recover_format(base, original)
            assert original == before
            assert receipts
            for old, new in zip(original['component_edits'], recovered['component_edits']):
                assert {k: v for k, v in old.items() if k != 'schema_json'} == {
                    k: v for k, v in new.items() if k != 'schema_json'}
                assert old['schema_json'] == new['schema_json'] + '}'
                value, _ = json.JSONDecoder().raw_decode(old['schema_json'])
                assert json.loads(new['schema_json']) == value
            library = actor.candidate_library(base, recovered)
            validate(library, kernel)
            assert {c['id'] for c in library['components']} == {
                c['id'] for c in base['components']} | {c['id'] for c in original['component_edits']}


@pytest.mark.parametrize('suffix', ['{}', ' trailing text', ']', '}}'])
def test_an_ambiguous_or_other_suffix_is_never_dropped(suffix):
    proposal = {'component_edits': [{'id': 'x', 'schema_json': '{"type":"object"}' + suffix}],
        'coverage_updates': []}
    with pytest.raises(ValueError):
        recover_format({'components': []}, proposal)


def test_missing_coverage_is_not_created_and_duplicate_coverage_is_not_chosen():
    base = {'components': [{'id': 'x'}]}
    proposal = {'component_edits': [], 'coverage_updates': []}
    recovered, _ = recover_format(base, proposal)
    with pytest.raises(ValueError, match='Exactly one coverage'):
        actor.candidate_library(base, recovered)
    proposal['coverage_updates'] = [{'id': 'x'}, {'id': 'x'}]
    recovered, _ = recover_format(base, proposal)
    with pytest.raises(ValueError, match='Exactly one coverage'):
        actor.candidate_library(base, recovered)
