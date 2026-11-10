"""Complete-denominator native DEV supplements from frozen predictions only.

Adds ContractNLI class-macro F1 and NormBench content recall/branch coverage,
plus source-paired comparisons. It neither changes predictions nor generates
new outputs. Missing predictions remain errors in the original denominators.
"""
from collections import Counter
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from legal_skill_guard.lsl.data import load_json, write_json, sha

LABELS = ('Entailment', 'Contradiction', 'NotMentioned')


def class_metrics(pairs):
    confusion = Counter(pairs)
    scores = {}
    for label in LABELS:
        tp = confusion[label, label]
        pred = sum(n for (g, p), n in confusion.items() if p == label)
        gold = sum(n for (g, p), n in confusion.items() if g == label)
        scores[label] = {'tp': tp, 'predicted': pred, 'gold': gold,
                        'F1': 2 * tp / (pred + gold) if pred + gold else 0.}
    return {'class_macro_F1': sum(v['F1'] for v in scores.values()) / 3,
        'per_class': scores, 'invalid_predictions': sum(n for (g, p), n in confusion.items() if p not in LABELS),
        'confusion': [{'gold': g, 'predicted': p, 'count': n} for (g, p), n in sorted(confusion.items())]}


def source_value(item):
    if item['dataset'] == 'NormBench':
        return item['score']['typed_content']['f1']
    if item['dataset'] == 'ContractNLI':
        return item['score']['native_accuracy']
    return float(item['score']['native_correct'])


def review(out, epoch):
    location = out / 'dev' / ('epoch%d' % epoch)
    if not (location / 'complete.json').exists():
        return None
    predictions = load_json(location / 'predictions.json')
    assert len(predictions) == 560
    rows = {r['key']: r for r in load_json(out / 'open_dataset.json')['records'] if r['split'] == 'dev'}
    assert len(rows) == 80
    fallback = load_json(location / 'fallback_results.json')
    systems = sorted({r['system'] for r in predictions})
    datasets = sorted({r['dataset'] for r in predictions})
    assert len(systems) == 7 and len(datasets) == 5
    by_system = {}
    indexed = {}
    for system in systems:
        indexed[system] = {r['source']: r for r in predictions if r['system'] == system}
        assert set(indexed[system]) == set(rows)
        by_system[system] = {}
        for dataset in datasets:
            selected = [r for r in indexed[system].values() if r['dataset'] == dataset]
            assert len(selected) == 16
            entry = {'sources': 16, 'main_valid': sum(r['main_path_valid'] for r in selected),
                'fallback_sources': sum(r['fallback_used'] for r in selected),
                'directed_head_used_without_fallback': sum(r['composition'].get('directed_head_used', False)
                    and not r['fallback_used'] for r in selected),
                'fallback_reasons': dict(Counter(str(r.get('fallback_reason') or r['composition'].get('error')
                    or r['composition'].get('reason')) for r in selected if r['fallback_used'])),
                'source_native_scores': {r['source']: source_value(r) for r in selected}}
            if dataset == 'ContractNLI':
                pairs = []
                for item in selected:
                    record = rows[item['source']]
                    labels = {}
                    if item['fallback_used'] and not item['main_path_valid']:
                        result = fallback.get(item['acquisition'] + ':' + item['source'], {})
                        labels = (result.get('parsed') or {}).get('answers', {})
                    elif item['main_path_valid']:
                        labels = {a['id']: a['label'] for a in item['prediction']['answers']}
                    gold = record['grade']['answers']
                    correct = sum(labels.get(key) == value for key, value in gold.items()) / 17
                    assert abs(correct - item['score']['native_accuracy']) < 1e-12
                    pairs.extend((value, labels.get(key, '__INVALID__')) for key, value in gold.items())
                entry.update(class_metrics(pairs), queries=272, statistical_source_units=16)
            elif dataset == 'NormBench':
                values = [r['score']['typed_content'] for r in selected]
                entry.update(typed_content_source_macro_recall=sum(v['tp'] / v['gold'] if v['gold'] else 1. for v in values) / 16,
                    typed_content_source_macro_precision=sum(v['tp'] / v['pred'] if v['pred'] else 0. for v in values) / 16,
                    membership_edge_F1=sum(r['score']['membership_edges']['f1'] for r in selected) / 16,
                    branch_behavior_proved_sources=sum(r['score']['branch_behavior_equivalent'] is True for r in selected),
                    branch_behavior_unknown_sources=sum(r['score']['branch_behavior_equivalent'] is None for r in selected))
            by_system[system][dataset] = entry
    comparisons = []
    for left, right in (('M1', 'Base'), ('M2', 'Base'), ('Joint', 'M1'), ('Joint', 'M2'),
                        ('M1', 'HardEM'), ('M1', 'ExecutionFilter'), ('M2', 'PairContrast')):
        for dataset in datasets:
            keys = [key for key, row in rows.items() if row['dataset'] == dataset]
            deltas = {key: source_value(indexed[left][key]) - source_value(indexed[right][key]) for key in keys}
            comparisons.append({'left': left, 'right': right, 'dataset': dataset, 'sources': 16,
                'metric': 'typed_content_F1' if dataset == 'NormBench' else 'source_native_accuracy',
                'mean_delta': sum(deltas.values()) / 16, 'wins': sum(v > 1e-12 for v in deltas.values()),
                'ties': sum(abs(v) <= 1e-12 for v in deltas.values()), 'losses': sum(v < -1e-12 for v in deltas.values()),
                'source_deltas': deltas})
    return {'epoch': epoch, 'physical_model_requests': 0, 'predictions_changed': False, 'TEST_loaded': False,
        'predictions_sha256': sha(location / 'predictions.json'), 'complete_sha256': sha(location / 'complete.json'),
        'by_system': by_system, 'source_paired_comparisons': comparisons,
        'different_libraries_not_averaged_into_an_undefined_score': True,
        'single_seed_DEV_not_confirmatory_TEST': True}


if __name__ == '__main__':
    out = ROOT / 'artifacts/lsl_mixed256_20261110'
    completed = []
    for epoch in (1, 2, 3):
        result = review(out, epoch)
        if result is not None:
            write_json(out / 'dev' / ('epoch%d' % epoch) / 'native_review.json', result)
            completed.append(epoch)
    print(json.dumps({'DEV_epochs_reviewed': completed, 'model_requests': 0}))
