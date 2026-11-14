"""Bind exact shared TRAIN history for the three unchanged boundary datasets.

The common FreeEvolution foundation is inherited by every new recipe. Its
original per-batch library, predictions, fallback flags, exposure and costs are
retained. Cached baseline outputs never count as a new C/M2 mechanism success.
No current or historical DEV/TEST file is loaded.
"""
import json
from pathlib import Path

from experiments import legal_skill_evolution_five_train as parent
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import Library, digest


ROOT = parent.ROOT
OUT = ROOT / 'artifacts/legal_skill_evolution_mixed_shared_routes_20261114'
COMMON = ROOT / 'artifacts/legal_skill_evolution_20261111/formal_v5/FreeEvolution'
DATASETS = {'OpenExempt', 'RuleArena_Airline', 'MAUD'}
read = parent.read


def run():
    protocol = parent.prepare()
    public = {s['key']: s for s in read(parent.PREPARED / 'public.json')}
    grading = read(parent.PREPARED / 'grading.json')
    old_manifest = read(COMMON.parent / 'execution_manifest.json')
    for name in ('public.json', 'grading.json'):
        path = parent.PREPARED / name
        assert old_manifest['data'][str(path.relative_to(ROOT))] == parent.file_hash(path)
    rows, checkpoints, call_ids = [], [], set()
    for batch, keys in enumerate(protocol['batches'], 1):
        before_path, after_path = COMMON / f'B{batch-1}.json', COMMON / f'B{batch}.json'
        before, after = Library.load(before_path), Library.load(after_path)
        checkpoint = {'batch': batch,
            'before_path': str(before_path.relative_to(ROOT)), 'before_library_hash': before.hash,
            'after_path': str(after_path.relative_to(ROOT)), 'after_library_hash': after.hash,
            'before_file_sha256': parent.file_hash(before_path), 'after_file_sha256': parent.file_hash(after_path),
            'same_common_checkpoint_for_all_new_recipes': True,
            'inherited_128_TRAIN_exposure_not_new_cold_start': True,
            'not_a_new_C_or_M2_update': True}
        checkpoints.append(checkpoint)
        immutable_json(OUT / f'B{batch}/checkpoint.json', checkpoint)
        for sid in keys:
            source = public[sid]
            if source['dataset'] not in DATASETS:
                continue
            path = COMMON / f'initial_B{batch}' / (digest(sid) + '.json')
            actual = read(path)
            assert actual['source'] == sid and actual['dataset'] == source['dataset']
            assert actual['library_hash'] == before.hash
            views = {v['id']: v for v in source['views']}
            checked = []
            for value in actual['views']:
                score = grade_view(source['dataset'], views[value['view']],
                    grading[sid][value['view']], value['execution']['answer'])
                assert score['correct'] == value['score']['correct'] and score['grade'] == value['score']['grade'], (sid, value['view'])
                # Historical runtime failures use failed_native_attempt, while
                # the scorer applied to their None answer uses format rejection.
                # Keep both records; neither becomes a valid/handled execution.
                checked.append({'view': value['view'], 'original_score': value['score'], 'rescored': score})
                for event in value['execution']['events']:
                    if event.get('physical_call_id'):
                        call_ids.add(event['physical_call_id'])
            row = {'source': sid, 'dataset': source['dataset'], 'batch': batch,
                'common_route': 'inherited_frozen_FreeEvolution', 'actual': actual,
                'original_path': str(path.relative_to(ROOT)), 'original_file_sha256': parent.file_hash(path),
                'source_public_sha256': digest(source), 'original_native_scores_rechecked': True,
                'regrade_records': checked,
                'new_model_calls': 0, 'not_new_C_or_M2_core_evidence': True,
                'pre_update_curve_only_no_post_update_prediction_invented': True}
            immutable_json(OUT / f'B{batch}/regraded_initial' / (digest(sid) + '.json'), row)
            rows.append(row)
    assert len(rows) == 80 and len({r['source'] for r in rows}) == 80
    summary = {'sources': len(rows), 'views': sum(len(r['actual']['views']) for r in rows),
        'correct_views': sum(v['score']['correct'] for r in rows for v in r['actual']['views']),
        'fallback_views': sum(v['execution']['fallback'] for r in rows for v in r['actual']['views']),
        'native_core_correct_views': sum(v['score']['correct'] and v['execution']['core_executed']
            for r in rows for v in r['actual']['views']),
        'physical_call_ids_of_reused_first_answers': sorted(call_ids),
        'all_inherited_foundation_learning_costs_common_to_all_recipes': True,
        'not_only_first_answer_costs': True, 'checkpoints': checkpoints,
        'new_model_calls': 0, 'TEST_opened': False,
        'not_full_five_training_completion': True, 'goal_complete': False}
    immutable_json(OUT / 'result.json', summary)
    print(json.dumps({k: v for k, v in summary.items() if k not in
        ('physical_call_ids_of_reused_first_answers', 'checkpoints')}), flush=True)


if __name__ == '__main__':
    run()
