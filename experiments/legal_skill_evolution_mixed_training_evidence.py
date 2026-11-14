"""Actual No-C execution and pre-update mixed TRAIN curves from saved results.

No generation is possible here. The ablation really bypasses learned source
extraction and G, using the common upstream source interpretation with the same
batch's typed native consumer. Missing first attempts stay unmeasured.
"""
from collections import defaultdict
import json

from experiments import legal_skill_evolution_source_library_train as source
from experiments import legal_skill_evolution_observation_library_train as obs
from experiments import legal_skill_evolution_mixed_shared_routes as shared
from experiments import legal_skill_evolution_generic_view_train as generic
from experiments import legal_skill_evolution_source_checkpoints as checkpoints
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native_theory_feedback import contract_checker, contract_execution
from legal_skill_guard.skill_evolution.objects import digest


ROOT = source.ROOT
OUT = ROOT / 'artifacts/legal_skill_evolution_mixed_training_evidence_20261114'
read = source.read


def feedback_of(row):
    value = row
    while 'feedback' not in value:
        if 'actual' not in value:
            raise ValueError('Actual source execution has no scored feedback')
        value = value['actual']
    return value['feedback']


def source_metrics(feedback):
    rows = feedback['views']
    return {'grade': sum((r.get('score') or {}).get('grade', 0) for r in rows) / 4,
        'correct_views': sum(bool((r.get('score') or {}).get('correct')) for r in rows),
        'expected_views': 4, 'handled_views': sum(r['core_executed'] for r in rows),
        'fallback_views': 0}


def run():
    protocol = source.prepare()
    public = {s['key']: s for s in read(source.parent.PREPARED / 'public.json')}
    grading = read(source.parent.PREPARED / 'grading.json')
    points = []
    for batch, keys in enumerate(protocol['mixed_batches'], 1):
        if not checkpoints.exists(batch-1):
            break
        library = checkpoints.load(batch-1, 'ConstraintAcquire')
        records = defaultdict(dict)
        for sid in keys:
            dataset = public[sid]['dataset']
            if dataset in shared.DATASETS:
                row = read(shared.OUT / f'B{batch}/regraded_initial' / (digest(sid) + '.json'))['actual']
                metrics = {'grade': row['native_grade'], 'correct_views': sum(v['score']['correct'] for v in row['views']),
                    'expected_views': len(row['views']), 'handled_views': sum(v['execution']['core_executed'] for v in row['views']),
                    'fallback_views': row['native_fallback_views'], 'inherited_common_result': True}
                for variant in ('C_PG', 'C_Free', 'C_Generic', 'NoC_PG', 'FreeSource_Free'):
                    records[variant][sid] = metrics
            elif dataset == 'ContractNLI':
                for arm, variants in [('ConstraintAcquire', ('C_PG', 'C_Free', 'C_Generic')),
                                      ('FreeUpdate', ('FreeSource_Free',))]:
                    path = source.OUT / f'B{batch}' / arm / 'initial' / source.previous.old.name_for(sid)
                    if not path.exists():
                        continue
                    metrics = source_metrics(feedback_of(read(path)))
                    for variant in variants:
                        records[variant][sid] = metrics
                upstream_path = source.parent.OUT / 'source_pass/upstream' / source.previous.old.name_for(sid)
                upstream = read(upstream_path)['source_output']
                target = OUT / f'B{batch}/NoC' / (digest(sid) + '.json')
                if target.exists():
                    no_c = read(target)
                    assert no_c['consumer_spec_sha256'] == digest(library['spec'])
                else:
                    primary = contract_execution(library['spec'], public[sid])(upstream)
                    immutable_json(target.with_name(target.stem + '_primary.json'), {
                        'source': sid, 'source_output': upstream, 'actual_unscored': primary,
                        'learned_phi_and_G_bypassed': True, 'consumer_spec_sha256': digest(library['spec'])})
                    feedback = contract_checker(library['spec'], public[sid], grading[sid])(upstream)
                    no_c = {'source': sid, 'source_output': upstream, 'feedback': feedback,
                        'consumer_spec_sha256': digest(library['spec']), 'learned_phi_and_G_bypassed': True,
                        'same_upstream_and_native_consumer': True, 'new_model_calls': 0}
                    immutable_json(target, no_c)
                records['NoC_PG'][sid] = source_metrics(no_c['feedback'])
            elif dataset == 'SARA_v2_Binary':
                path = obs.OUT / f'B{batch}/initial_scored_results.json'
                if path.exists():
                    for row in read(path)['rows']:
                        if row['source'] != sid:
                            continue
                        variants = ('C_PG', 'NoC_PG') if row['arm'] == 'ProgramGuided' else ('C_Free', 'FreeSource_Free')
                        metrics = {'grade': row['native_score']['grade'], 'correct_views': row['native_score']['correct'],
                            'expected_views': 1, 'handled_views': int(row['execution']['handled']), 'fallback_views': 0}
                        for variant in variants:
                            records[variant][sid] = metrics
                path = generic.OUT / f'B{batch}/scored_results.json'
                if path.exists():
                    row = next(r for r in read(path)['rows'] if r['source'] == sid)
                    records['C_Generic'][sid] = {'grade': row['native_score']['grade'],
                        'correct_views': row['native_score']['correct'], 'expected_views': 1,
                        'handled_views': int(row['execution']['handled']), 'fallback_views': 0}
        variants = {}
        for name, values in records.items():
            groups = defaultdict(list)
            for sid, value in values.items():
                groups[public[sid]['dataset']].append(value)
            variants[name] = {'measured_mothers': len(values), 'expected_mothers': 16,
                'complete_pre_update_point': len(values) == 16,
                'parent_macro_native_grade': sum(v['grade'] for v in values.values()) / len(values),
                'native_correct_views': sum(v['correct_views'] for v in values.values()),
                'measured_views': sum(v['expected_views'] for v in values.values()), 'expected_views': 35,
                'fallback_views': sum(v['fallback_views'] for v in values.values()),
                'per_dataset': {d: {'mothers': len(v), 'parent_macro_native_grade': sum(x['grade'] for x in v) / len(v)}
                    for d, v in groups.items()}, 'source_rows': values}
        points.append({'batch': batch, 'variants': variants})
    result = {'points': points, 'metric': 'Native view grade averaged within parent then across measured parents',
        'B1_global_observation_initial_unmeasured_not_zero': True,
        'common_80_routes_are_inherited_not_new_C_M2_success': True,
        'B4_original_initial_precedes_shared_disposal_consumer_correction': True,
        'not_post_update_or_frozen_final_scores': True,
        'native_grade_not_source_or_case_semantic_certificate': True, 'new_model_calls': 0, 'goal_complete': False}
    OUT.mkdir(parents=True, exist_ok=True)
    # Mutable observation of an active run, deliberately outside frozen inputs.
    (OUT / 'unbound_pre_update_learning_curve.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    for point in points:
        print(json.dumps({'batch': point['batch'], 'native_grades': {
            k: round(v['parent_macro_native_grade'], 4) for k, v in point['variants'].items()},
            'complete_points': {k: v['complete_pre_update_point'] for k, v in point['variants'].items()}}), flush=True)


if __name__ == '__main__':
    run()
