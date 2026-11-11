"""First-attempt learning curves, paired with the same-source NoSkill arm.

All inputs are settled TRAIN checkpoints. Candidate feedback replays and DEV
are kept separate. This module never calls an executor or reads TEST files.
"""
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from experiments.legal_skill_evolution_formal import ARMS, PROFILE
from legal_skill_guard.skill_evolution.objects import Library, digest
from .native_statistics import DATASETS, summarize, average
from .skill_lineage import accepted_lineage, actual_use

ROOT = Path(__file__).resolve().parents[2]
REPORT = Path(__file__).resolve().parent


def load(path):return json.loads(Path(path).read_text())


def paired_initial(initial, baseline):
    left, right = summarize(initial), summarize(baseline)
    left_rows = {r['source']: r for r in left['source_rows']}
    right_rows = {r['source']: r for r in right['source_rows']}
    if set(left_rows) != set(right_rows):raise ValueError('First-attempt comparison must use identical parents')
    rows = []
    for key, row in left_rows.items():
        other = right_rows[key]
        if row['dataset'] != other['dataset'] or set(row['per_view_grade']) != set(other['per_view_grade']):
            raise ValueError('First-attempt comparison must preserve dataset and every native view')
        difference = (row['native_grade'] - other['native_grade']
            if row['native_grade'] is not None and other['native_grade'] is not None else None)
        rows.append({'source': key, 'dataset': row['dataset'], 'native_grade': row['native_grade'],
            'NoSkill_native_grade': other['native_grade'], 'paired_difference': difference})
    by_dataset = {dataset: average([r['paired_difference'] for r in rows if r['dataset'] == dataset])
                  for dataset in DATASETS}
    return left, {'equal_five_dataset_difference': average(list(by_dataset.values())),
                  'dataset_differences': by_dataset, 'source_rows': rows}


def main():
    folder = ROOT / load(PROFILE)['artifacts']
    manifest = load(ROOT / 'reports/legal_skill_evolution_plan_20261111/candidate_source_manifest.json')
    source_datasets = {r['key']: dataset for dataset, splits in manifest['datasets'].items() for r in splits['train']}
    footprints_path = REPORT / 'formal_cost_footprints.json'
    footprints = load(footprints_path) if footprints_path.exists() else {}
    costs = {(arm, p['batch']): p for arm, values in footprints.get('per_batch_observed_response_footprints', {}).items()
             for p in values}
    points, csv_rows = [], []
    for batch, source_batch in enumerate(manifest['source_sequence'], 1):
        expected = [r['source_key'] for r in source_batch['sources']]
        base_path = folder / 'NoSkill' / f'initial_B{batch}.json'
        if not base_path.exists():continue
        baseline = load(base_path)
        for arm in ARMS:
            path = folder / arm / f'initial_B{batch}.json'
            if not path.exists():continue
            initial = load(path)
            if initial['binding']['source_ids'] != expected or [r['source'] for r in initial['results']] != expected:
                raise ValueError('A first-attempt checkpoint changed the fixed source order')
            before = Library.load(folder / arm / f'B{batch - 1}.json')
            if any(parent['library_hash'] != before.hash for parent in initial['results']):
                raise ValueError('First attempts must all use the frozen batch-start library')
            summary, paired = paired_initial(initial['results'], baseline['results'])
            lineage = (accepted_lineage(folder, arm, batch - 1, source_datasets) if arm != 'NoSkill'
                       else {'library_hash': before.hash, 'skills': {}})
            uses = [row for parent in initial['results'] for row in actual_use(parent, before, lineage)]
            update_path = folder / arm / f'update_B{batch}.json'
            update = load(update_path) if update_path.exists() else None
            after = Library.load(folder / arm / f'B{batch}.json') if (folder / arm / f'B{batch}.json').exists() else None
            points.append({'arm': arm, 'batch': batch, 'TRAIN_parents_seen': batch * 16,
                'first_attempt_checkpoint': str(path.relative_to(ROOT)),
                'first_attempt_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                'batch_start_library_hash': before.hash, 'metrics': summary, 'paired_NoSkill': paired,
                'skills_before': len(before.skills), 'skills_after': len(after.skills) if after else None,
                'patterns_after': len(after.revision_patterns) if after else None,
                'update_complete': after is not None and (arm == 'NoSkill' or update is not None),
                'accepted_update_receipt': update,
                'actual_use': uses, 'response_footprint': costs.get((arm, batch))})
            for dataset in DATASETS:
                metrics = summary['datasets'][dataset]
                csv_rows.append({'arm': arm, 'batch': batch, 'TRAIN_parents_seen': batch * 16,
                    'dataset': dataset, 'native_parent_mean': metrics['native_parent_mean'],
                    'paired_NoSkill_difference': paired['dataset_differences'][dataset],
                    'parent_count': metrics['parent_count'],
                    'core_views': metrics['path_counts'].get('core_views', 0),
                    'fully_correct_core_views': metrics['path_counts'].get('fully_correct_core_views', 0),
                    'fallback_view_rate': metrics['fallback_view_rate'], 'skills_before': len(before.skills),
                    'skills_after': len(after.skills) if after else None,
                    'patterns_after': len(after.revision_patterns) if after else None})
    result = {'captured_utc': datetime.now(timezone.utc).isoformat(), 'new_model_calls': 0, 'TEST_opened': False,
        'points': points, 'source_manifest_sha256': hashlib.sha256((ROOT / 'reports/legal_skill_evolution_plan_20261111/candidate_source_manifest.json').read_bytes()).hexdigest(),
        'cost_snapshot_sha256': hashlib.sha256(footprints_path.read_bytes()).hexdigest() if footprints_path.exists() else None,
        'point_scope': 'All native views of all 16 parents, answered before this batch update; feedback replay never contributes to these scores.',
        'different_batches_have_different_cases': True,
        'paired_NoSkill_interpretation': 'Same-parent native grade difference, describing the existing prequential trajectory; not another trained arm or a held-out TEST estimate.',
        'cost_interpretation': footprints.get('interpretation'),
        'unmeasured_points_extrapolated': False, 'unresolved_or_unknown_grades_dropped': False}
    (REPORT / 'formal_TRAIN_trajectory.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    fields = ['arm', 'batch', 'TRAIN_parents_seen', 'dataset', 'native_parent_mean', 'paired_NoSkill_difference',
        'parent_count', 'core_views', 'fully_correct_core_views', 'fallback_view_rate', 'skills_before', 'skills_after', 'patterns_after']
    with (REPORT / 'formal_TRAIN_trajectory.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields);writer.writeheader();writer.writerows(csv_rows)
    print(json.dumps({'complete_first_attempt_points': len(points),
        'latest_by_arm': {a: max((p['batch'] for p in points if p['arm'] == a), default=None) for a in ARMS},
        'new_model_calls': 0, 'TEST_opened': False}))


if __name__ == '__main__':main()
