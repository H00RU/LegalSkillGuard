"""Replay final observation libraries on fixed TRAIN using paid reads only.

Missing or conflicting cached reads are missing evidence, never failed answers.
This entry point has no model client, ledger writer or DEV/TEST data access.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import jsonschema

from experiments import legal_skill_evolution_mixed_component_training as train
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native_case_encoding import FACTUAL_ENCODING
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.observation_component_library import component_value

ROOT = train.ROOT
OUT = ROOT / 'artifacts/legal_skill_evolution_observation_TRAIN_replay_20261115'
CACHE_NAMES = (
    'legal_skill_evolution_observation_component_execution_20261115',
    'legal_skill_evolution_observation_component_execution_conditional_20261115',
    'legal_skill_evolution_mixed_component_training_20261115',
    'legal_skill_evolution_mixed_component_training_source_review_20261115',
    'legal_skill_evolution_mixed_component_training_history_20261115',
    'legal_skill_evolution_mixed_component_training_status_schema_20261115',
    'legal_skill_evolution_mixed_component_training_line_transport_20261115',
    'legal_skill_evolution_mixed_component_training_validated_updates_20261115',
    'legal_skill_evolution_mixed_component_training_compact_refs_20261115',
)


class OfflineReadUnavailable(RuntimeError):
    pass


class PaidCacheOnly:
    artifacts = OUT
    ledger = SimpleNamespace(run_id=OUT.name)

    def tokenize(self, messages, *, thinking):
        raise OfflineReadUnavailable('No exact paid component response; no request dispatched')

    def generate(self, *args, **kwargs):
        raise AssertionError('Offline TRAIN replay must never generate')


def collect_cache(train_keys):
    cache, origins, conflicts = {}, {}, set()
    for name in CACHE_NAMES:
        assert 'DEV' not in name and 'TEST' not in name
        for path in sorted((ROOT / 'artifacts' / name / 'component_reads').glob('*.json')):
            value = train.read(path)
            if value['source'] not in train_keys:
                continue
            key = value['wire_input_sha256']
            assert path.stem == key
            body = {'source': value['source'], 'component_id': value['component_id'],
                    'value': value['value'], 'error': value['error']}
            if key in cache and digest(body) != digest(cache[key][0]):
                conflicts.add(key)
            else:
                cache.setdefault(key, (body, value))
            origins.setdefault(key, []).append(str(path.relative_to(ROOT)))
    for key, (_, value) in cache.items():
        if key not in conflicts:
            immutable_json(OUT / 'component_reads' / (key + '.json'), value)
    immutable_json(OUT / 'paid_read_origins.json', {'origins': origins,
        'conflicting_inputs_not_replayed': sorted(conflicts), 'new_model_calls': 0})
    return cache, conflicts


def run():
    protocol = train.read(train.OUT / 'protocol.json')
    bank = train.actor.acquisition.previous.parent.OUT
    public = {s['key']: s for s in train.read(bank / 'SARA_corrected_TRAIN_views.json')}
    kernels = {r['source']: train.actor.acquisition.current_case_interface(r['kernel'])
               for r in train.read(bank / 'SARA_native_kernel_bank.json')}
    assert len(public) == len(kernels) == 24
    assert set(public) == set(kernels) <= set(protocol['sources'])
    assert all(s['split'] == 'train' for s in public.values())
    grading = train.read(train.actor.acquisition.previous.parent.PREPARED / 'grading.json')
    checkpoint = train.read(train.OUT / 'B8/checkpoint.json')
    cache, conflicts = collect_cache(set(public))
    client = PaidCacheOnly()
    actor_protocol = {'shared_public_pure_calculation': True,
        'executor_profile': protocol['executor_profile'],
        'shared_native_event_encoding': FACTUAL_ENCODING}
    rows = []
    for arm in train.ARMS:
        library = train.read(ROOT / checkpoint['libraries'][arm]['path'])
        assert digest(library) == checkpoint['libraries'][arm]['sha256']
        by_id = {c['id']: c for c in library['components']}
        for sid in public:
            row = train.actor.execute_one(client, actor_protocol, arm, library, sid,
                kernels[sid], public[sid], 'final_B8_TRAIN_only', purpose='skill_actor')
            evaluated = 'OfflineReadUnavailable:' not in row.get('error', '')
            row = {**row, 'all_required_paid_reads_available': evaluated}
            if evaluated:
                row = train.scored(row, public, grading)
            components = []
            for cid, observation in row.get('observation', {}).items():
                jsonschema.validate(observation, json.loads(by_id[cid]['schema_json']))
                converted = [component_value(library, by_id[cid], kernels[sid],
                    public[sid]['views'][0]['public'], view) for view in observation['views']]
                components.append({'id': cid, 'views': len(converted),
                    'complete': [v['complete'] for v in converted],
                    'reasons': [v['reasons'] for v in converted],
                    'facts': [v['facts'] for v in converted]})
            row['individual_actual_component_conversions'] = components
            rows.append(row)
    result = {'new_model_calls': 0, 'teacher_calls': 0, 'ledger_created_or_written': False,
        'DEV_TEST_accessed': False, 'fixed_original_TRAIN_mothers': sorted(public),
        'final_B8_library_hashes': {a: checkpoint['libraries'][a]['sha256'] for a in train.ARMS},
        'unique_paid_read_keys': len(cache), 'conflicting_paid_read_keys': len(conflicts),
        'unavailable_read_is_missing_evidence_not_prediction_error': True,
        'native_correct_not_a_semantic_or_contribution_certificate': True,
        'rows': rows, 'summary': {}}
    for arm in train.ARMS:
        selected = [r for r in rows if r['candidate'] == arm]
        assessed = [r for r in selected if r['all_required_paid_reads_available']]
        result['summary'][arm] = {'mothers': len(selected), 'assessed': len(assessed),
            'missing_cached_read': len(selected) - len(assessed),
            'core_handled': sum(r['execution']['handled'] for r in assessed),
            'native_correct': sum(r['native_score']['correct'] for r in assessed),
            'known_partial_source_failures': sum(r['partial_source_review']['failures'] for r in assessed),
            'unresolved_reasons': dict(Counter(reason for r in assessed
                for reason in r.get('grounded', {}).get('unresolved', [])))}
    immutable_json(OUT / 'result.json', result)
    print(json.dumps({'summary': result['summary'], 'new_model_calls': 0}), flush=True)


if __name__ == '__main__':
    run()
