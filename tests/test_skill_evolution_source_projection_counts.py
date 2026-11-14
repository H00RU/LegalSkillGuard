from copy import deepcopy
import json
from pathlib import Path

from experiments import legal_skill_evolution_source_count_bias_repair as repair
from legal_skill_guard.skill_evolution.source_projection_counts import add_counts
from legal_skill_guard.skill_evolution.source_projection_counts import validate_projections
import pytest


def test_zero_representation_count_cannot_establish_legal_absence():
    observation = {'visible_inputs': {'source_output': {'statements': []}},
        'context': {'facts': []}, 'contract_sha256': 'test_original_contract'}
    original = deepcopy(observation)
    value = add_counts(observation, [repair.PROJECTION])
    assert observation == original
    assert value['visible_inputs'] == observation['visible_inputs']
    assert value['structural_projection_receipt']['zero_count_is_not_legal_absence']
    assert len(value['context']['facts']) == 1
    assert value['contract_sha256'] != original['contract_sha256']
    assert 'complete_source_no_disclosure_permission' not in json.dumps(value['context'])


def test_actual_permission_counterevidence_blocks_false_absence_without_new_read():
    rows = [json.loads(p.read_text()) for p in (repair.OUT / 'results').glob('*.json')]
    permission = next(r for r in rows if r['source'].startswith('ContractNLI:e82'))
    no_permission = next(r for r in rows if r['source'].startswith('ContractNLI:bc93'))
    assert permission['actual_projection']['projections'][0]['count'] == 1
    assert ['complete_source_no_disclosure_permission'] not in [
        s['term'] for s in permission['source_output']['statements']]
    assert no_permission['actual_projection']['projections'][0]['count'] == 0
    assert ['complete_source_no_disclosure_permission'] in [
        s['term'] for s in no_permission['source_output']['statements']]
    result = json.loads((repair.OUT / 'result.json').read_text())
    assert result['new_model_calls'] == 0 and result['native_correct'] == 93
    assert len(rows) == 24 and all(r['source_review_passed'] for r in rows)


def test_invalid_projection_is_not_silently_a_zero_on_empty_input():
    observation = {'visible_inputs': {'source_output': {'statements': []}},
        'context': {'facts': []}, 'contract_sha256': 'original'}
    projection = deepcopy(repair.PROJECTION)
    projection['arguments_equal'][0]['position'] = -1
    with pytest.raises(ValueError):
        add_counts(observation, [projection])
    projection['arguments_equal'][0]['position'] = 2
    with pytest.raises(ValueError):
        validate_projections([projection], {'acq_disclosure_v3': {'arguments': ['text', 'text']}})


def test_guarded_library_runs_through_normal_observe_path_for_both_arms():
    path = repair.ROOT / 'artifacts/legal_skill_evolution_source_projection_runtime_20261115/result.json'
    value = json.loads(path.read_text())
    assert value['normal_observe_execute_used_both_arms']
    assert value['same_public_feature_available_to_Free']
    assert value['new_model_calls'] == 0
    assert value['results']['ConstraintAcquire']['native_correct'] == 93
    assert value['results']['FreeUpdate']['native_correct'] == 92
    assert all(r['all_existing_source_checks_pass'] and r['unresolved'] == 0 for r in value['results'].values())
