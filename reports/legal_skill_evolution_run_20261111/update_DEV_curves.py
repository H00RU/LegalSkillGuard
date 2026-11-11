"""Summarize only completed frozen-config DEV checkpoints, without feedback."""
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

from experiments.legal_skill_evolution_formal import ARMS, CURVE_ARMS, schedule, PROFILE as FORMAL_PROFILE
from .native_statistics import DATASETS, summarize, nli_metrics, source_mean_intervals

ROOT = Path(__file__).resolve().parents[2]
REPORT = Path(__file__).resolve().parent


def main():
    folder = ROOT / json.loads(FORMAL_PROFILE.read_text())['artifacts']
    expected = json.loads((ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/dev/public.json').read_text())
    expected = {r['key']: {v['id'] for v in r['views']} for r in expected}
    annotations = json.loads((ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/dev/grading.json').read_text())
    allowed = {(arm, batch) for action, arm, batch in schedule() if action == 'dev'}
    points, csv_rows = [], []
    for path in sorted((folder / 'dev').glob('*/B*.json')):
        saved = json.loads(path.read_text())
        arm, batch = saved['arm'], saved['batch']
        if (arm, batch) not in allowed:raise ValueError('An unregistered DEV checkpoint appeared')
        actual = {r['source']: {v['view'] for v in r['views'] if not v['controlled']} for r in saved['results']}
        if actual != expected or len(saved['results']) != len(expected):
            raise ValueError('DEV checkpoint must contain the exact complete source/view set')
        summary = summarize(saved['results'])
        a, b = summary['equal_five_dataset_macro'], saved['equal_dataset_macro']
        if a != b and not (a is not None and b is not None and math.isclose(a, b, rel_tol=0, abs_tol=1e-12)):
            raise ValueError('Recomputed DEV macro differs from production record')
        points.append({'arm': arm, 'batch': batch, 'library_hash': saved['library_hash'],
            'source_checkpoint': str(path.relative_to(ROOT)),
            'source_checkpoint_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'metrics': summary, 'source_uncertainty': source_mean_intervals(saved['results']),
            'ContractNLI_secondary': nli_metrics(saved['results'], annotations)})
        for dataset in DATASETS:
            d = summary['datasets'][dataset]
            csv_rows.append({'arm': arm, 'batch': batch, 'TRAIN_parents_seen': batch * 16,
                'dataset': dataset, 'DEV_parents': d['parent_count'], 'native_mean': d['native_parent_mean'],
                'native_views': d['path_counts']['native_views'], 'core_views': d['path_counts']['core_views'],
                'fallback_views': d['path_counts']['fallback_views'],
                'fully_correct_core_views': d['path_counts']['fully_correct_core_views']})
    snapshot = {'captured_utc': datetime.now(timezone.utc).isoformat(), 'stage': 'readonly_DEV',
        'new_model_calls': 0, 'teacher_feedback': False, 'TEST_opened': False,
        'formal_complete': (folder / 'training_DEV_completed.json').exists(),
        'expected_curve_arms': list(CURVE_ARMS), 'expected_curve_batches': list(range(9)),
        'points': points, 'completed_points': len(points), 'expected_points': len(allowed),
        'missing_points': [{'arm': a, 'batch': b} for a, b in sorted(allowed - {(p['arm'], p['batch']) for p in points})],
        'no_best_DEV_checkpoint_selection': True}
    (REPORT / 'formal_DEV_summary.json').write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + '\n')
    with (REPORT / 'formal_DEV_curve_data.csv').open('w', newline='') as stream:
        fields = ['arm', 'batch', 'TRAIN_parents_seen', 'dataset', 'DEV_parents', 'native_mean',
                  'native_views', 'core_views', 'fallback_views', 'fully_correct_core_views']
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader();writer.writerows(csv_rows)
    print(json.dumps({'completed_DEV_points': len(points), 'expected_points': len(allowed),
        'latest_batches': {arm: max((p['batch'] for p in points if p['arm'] == arm), default=None) for arm in ARMS},
        'new_model_calls': 0, 'TEST_opened': False}))


if __name__ == '__main__':main()
