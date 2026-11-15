"""Check the actual B8 update against previously seen original TRAIN cases.

Only exact paid component responses are replayed. Missing reads are missing
evidence, never model failures; the learner and the fixed DEV remain untouched.
"""
from collections import Counter
import fcntl
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from experiments import legal_skill_evolution_mixed_component_training as train
from experiments import legal_skill_evolution_observation_TRAIN_replay as replay
from experiments import legal_skill_evolution_source_selection_lineage as lineage
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native_case_encoding import FACTUAL_ENCODING
from legal_skill_guard.skill_evolution.objects import digest


ROOT = train.ROOT
OUT = ROOT / 'artifacts/legal_skill_evolution_observation_retention_regression_20261115'


class MissingPaidRead(RuntimeError):
    pass


class ExactPaidReads:
    artifacts = OUT
    ledger = SimpleNamespace(run_id=OUT.name)

    def tokenize(self, *args, **kwargs):
        raise MissingPaidRead('No exact paid component response, no physical request dispatched')

    def generate(self, *args, **kwargs):
        raise AssertionError('Offline retention regression cannot generate')


def collect_cache(train_sources):
    saved, conflicts, origins = {}, set(), {}
    for name in replay.CACHE_NAMES:
        assert 'DEV' not in name and 'TEST' not in name
        for path in sorted((ROOT / 'artifacts' / name / 'component_reads').glob('*.json')):
            row = train.read(path)
            if row['source'] not in train_sources:
                continue
            key = row['wire_input_sha256']
            assert path.stem == key
            payload = {k: row[k] for k in ('source', 'component_id', 'value', 'error')}
            if key in saved and saved[key][0] != payload:
                conflicts.add(key)
            saved.setdefault(key, (payload, row))
            origins.setdefault(key, []).append(str(path.relative_to(ROOT)))
    for key, (_, row) in saved.items():
        if key not in conflicts:
            immutable_json(OUT / 'component_reads' / (key + '.json'), row)
    immutable_json(OUT / 'exact_paid_read_provenance.json', {
        'origins': origins, 'conflicting_keys_not_used': sorted(conflicts), 'new_model_calls': 0})
    return len(saved), len(conflicts)


def run():
    before = lineage.ledger_snapshot()
    protocol = train.read(train.OUT / 'protocol.json')
    bank = train.actor.acquisition.previous.parent.OUT
    sources = {s['key']: s for s in train.read(bank / 'SARA_corrected_TRAIN_views.json')}
    kernels = {r['source']: train.actor.acquisition.current_case_interface(r['kernel'])
        for r in train.read(bank / 'SARA_native_kernel_bank.json')}
    grading = train.read(train.actor.acquisition.previous.parent.PREPARED / 'grading.json')
    assert set(sources) == set(kernels) and all(s['split'] == 'train' for s in sources.values())
    previous_keys = [sid for batch in protocol['batches'][:7] for sid in batch if sid in sources]
    current_keys = [sid for sid in protocol['batches'][7] if sid in sources]
    assert len(previous_keys) == len(set(previous_keys)) == 21 and len(current_keys) == 3
    assert not set(previous_keys) & set(current_keys)
    checkpoints = {n: train.read(train.OUT / f'B{n}/checkpoint.json') for n in (7, 8)}
    libraries = {(arm, n): train.read(ROOT / checkpoints[n]['libraries'][arm]['path'])
        for arm in train.ARMS for n in (7, 8)}
    immutable_json(OUT / 'protocol.json', {'same_goal': True,
        'question': 'Does the actual B8-selected observation update regress already seen TRAIN cases?',
        'previous_TRAIN_sources': previous_keys, 'current_batch_sources_excluded': current_keys,
        'libraries': {arm: {str(n): digest(libraries[arm, n]) for n in (7, 8)} for arm in train.ARMS},
        'missing_cached_reads_never_become_prediction_errors': True,
        'shared_current_public_repairs_both_sides': True,
        'DEV_TEST_loaded': False, 'new_model_calls': 0, 'ledger_before': before,
        'source_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (Path(__file__), ROOT / 'experiments/legal_skill_evolution_observation_component_execute.py',
                ROOT / 'legal_skill_guard/skill_evolution/observation_source_review.py')},
        'goal_complete': False})
    cache_count, conflicts = collect_cache(set(sources))
    actor_protocol = {'shared_public_pure_calculation': True,
        'executor_profile': protocol['executor_profile'], 'shared_native_event_encoding': FACTUAL_ENCODING}
    client = ExactPaidReads()
    rows, comparisons = [], []
    for arm in train.ARMS:
        for sid in previous_keys:
            pair = {}
            for n in (7, 8):
                row = train.actor.execute_one(client, actor_protocol, arm, libraries[arm, n], sid,
                    kernels[sid], sources[sid], 'B8_retention/at_B' + str(n), purpose='skill_actor')
                available = 'MissingPaidRead:' not in row.get('error', '')
                row = {**row, 'all_exact_paid_reads_available': available}
                if available:
                    row = train.scored(row, sources, grading)
                pair[n] = row
                rows.append(row)
            jointly_available = all(r['all_exact_paid_reads_available'] for r in pair.values())
            item = {'source': sid, 'arm': arm, 'jointly_assessable': jointly_available,
                'before_read_evidence_complete': pair[7]['all_exact_paid_reads_available'],
                'after_read_evidence_complete': pair[8]['all_exact_paid_reads_available']}
            if jointly_available:
                for n, label in ((7, 'before'), (8, 'after')):
                    r = pair[n]
                    item[label] = {'handled': r['execution']['handled'],
                        'native_correct': r['native_score']['correct'],
                        'partial_source_failures': r['partial_source_review']['failures'],
                        'unresolved': r.get('grounded', {}).get('unresolved', []),
                        'unresolved_proposal': r.get('unresolved_proposal'), 'error': r.get('error')}
            comparisons.append(item)
    after = lineage.ledger_snapshot()
    assert before == after
    summary = {}
    for arm in train.ARMS:
        subset = [r for r in comparisons if r['arm'] == arm]
        assessed = [r for r in subset if r['jointly_assessable']]
        summary[arm] = {'previous_sources': len(subset), 'jointly_assessable': len(assessed),
            'missing_read_evidence': len(subset)-len(assessed),
            'before_core_correct': sum(r['before']['handled'] and r['before']['native_correct'] for r in assessed),
            'after_core_correct': sum(r['after']['handled'] and r['after']['native_correct'] for r in assessed),
            'core_correct_to_unhandled': sum(r['before']['handled'] and r['before']['native_correct']
                and not r['after']['handled'] for r in assessed),
            'new_partial_source_failures': sum(r['after']['partial_source_failures']-r['before']['partial_source_failures']
                for r in assessed)}
    immutable_json(OUT / 'result.json', {'summary': summary, 'comparisons': comparisons, 'rows': rows,
        'unique_paid_read_keys': cache_count, 'conflicting_paid_read_keys': conflicts,
        'ledger_before': before, 'ledger_after': after, 'new_model_calls': 0,
        'DEV_TEST_loaded': False, 'not_a_new_model_run_or_contribution_certificate': True,
        'current_libraries_and_original_results_unchanged': True, 'goal_complete': False})
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    with (ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        run()
