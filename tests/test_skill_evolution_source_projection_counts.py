from copy import deepcopy
import json
from pathlib import Path

from experiments import legal_skill_evolution_source_count_bias_repair as repair
from legal_skill_guard.skill_evolution.source_projection_counts import add_counts


def test_zero_representation_count_cannot_establish_legal_absence():
    observation = {'visible_inputs': {'source_output': {'statements': []}},
        'context': {'facts': []}}
    original = deepcopy(observation)
    value = add_counts(observation, [repair.PROJECTION])
    assert observation == original
    assert value['visible_inputs'] == observation['visible_inputs']
    assert value['structural_projection_receipt']['zero_count_is_not_legal_absence']
    assert len(value['context']['facts']) == 1
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
