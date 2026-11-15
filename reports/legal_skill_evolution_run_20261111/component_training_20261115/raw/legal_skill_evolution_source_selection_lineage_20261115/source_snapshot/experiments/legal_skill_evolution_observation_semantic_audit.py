"""Regression for a real TRAIN misread, without modifying its observation.

The empty view is only a schema/converter capability probe, never a replacement
prediction, recovered IR, scored case, or additional source.
"""
from copy import deepcopy
import json

import jsonschema

from experiments import legal_skill_evolution_mixed_component_training as train
from experiments import legal_skill_evolution_source_selection_lineage as lineage
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.observation_component_library import component_value
from legal_skill_guard.skill_evolution.observation_source_review import review


ROOT = train.ROOT
OUT = ROOT / 'artifacts/legal_skill_evolution_observation_semantic_audit_20261115'


def run():
    before = lineage.ledger_snapshot()
    actual = train.read(OUT / 'actual_case.json')
    sid = actual['source']
    assert sid.startswith('SARA_v2_Binary:d9d6b2')
    bank = train.actor.acquisition.previous.parent.OUT
    source = next(s for s in train.read(bank / 'SARA_corrected_TRAIN_views.json') if s['key'] == sid)
    assert source['split'] == 'train'
    public = source['views'][0]['public']
    kernel = next(r['kernel'] for r in train.read(bank / 'SARA_native_kernel_bank.json') if r['source'] == sid)
    checkpoint = train.read(train.OUT / 'B8/checkpoint.json')
    arms = {}
    for arm in train.ARMS:
        library = train.read(ROOT / checkpoint['libraries'][arm]['path'])
        component = next(c for c in library['components'] if c['id'] == 'education_service_states')
        schema = json.loads(component['schema_json'])
        paid = deepcopy(actual['observation'][component['id']])
        jsonschema.validate(paid, schema)
        observed = [component_value(library, component, kernel, public, view) for view in paid['views']]
        probe = deepcopy(paid)
        for view in probe['views']:
            for name in ('institutions', 'enrollments', 'attendance'):
                view[name] = []
        jsonschema.validate(probe, schema)
        converted_probe = [component_value(library, component, kernel, public, view) for view in probe['views']]
        assert all(v['complete'] and not v['facts'] for v in converted_probe)
        arms[arm] = {'library_sha256': digest(library),
            'paid_observation_accepted_by_original_schema': True,
            'paid_conversion_complete': [v['complete'] for v in observed],
            'paid_conversion_native_predicates': sorted({f['predicate'] for v in observed for f in v['facts']}),
            'same_paid_view_through_this_arm_converter': True,
            'not_a_separate_model_response_for_the_control': arm != actual['candidate'],
            'complete_empty_arrays_accepted_by_same_schema_and_converter': True,
            'empty_probe_is_not_a_new_model_response_or_repaired_case': True,
            'actual_conversion': observed}
    original = deepcopy(actual['grounded'])
    after_review = review(sid, original)
    assert after_review['failures'] == 2
    assert original == actual['grounded']
    previous = train.read(OUT / 'before_review.json')
    assert previous['old_review']['failures'] == 0
    assert digest(original) == previous['grounded_sha256']
    after = lineage.ledger_snapshot()
    assert after == before
    immutable_json(OUT / 'result.json', {'source': sid,
        'source_facts': public['facts'], 'arms': arms,
        'old_partial_review': previous['old_review'], 'updated_partial_review': after_review,
        'original_whole_case_handled': actual['execution']['handled'],
        'raw_observation_or_converted_facts_changed': False,
        'interpretation': 'Semantic model error and missing partial source feedback; the schema does not force these positive records.',
        'not_a_recovered_native_case_or_method_gain': True,
        'new_model_calls': 0, 'ledger_before': before, 'ledger_after': after,
        'DEV_TEST_loaded': False, 'goal_complete': False})
    print(json.dumps({'old_source_failures': 0, 'updated_source_failures': 2,
        'empty_schema_capability': True, 'new_model_calls': 0}), flush=True)


if __name__ == '__main__':
    run()
