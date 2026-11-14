"""Reconcile saved DEV comparisons without generation or library modification."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/legal_skill_evolution_component_stage_review_20261115'
OLD = ROOT / 'artifacts/legal_skill_evolution_mixed_DEV_public_execution_20261115'
CURRENT = ROOT / 'artifacts/legal_skill_evolution_mixed_component_DEV_profile_fix_20261115'


def read(path):
    return json.loads(path.read_text())


def summarize(value):
    result = {}
    for name, recipe in value['recipes'].items():
        rows = recipe['rows']
        assert len(rows) == 40 and sum(len(r['views']) for r in rows) == 88
        score = sum(sum(v['score']['grade'] for v in r['views']) / len(r['views']) for r in rows) / len(rows)
        assert abs(score - recipe['native_parent_mean']) < 1e-12
        datasets = {}
        for dataset in sorted({r['dataset'] for r in rows}):
            selected = [r for r in rows if r['dataset'] == dataset]
            views = [v for r in selected for v in r['views']]
            datasets[dataset] = {
                'mothers': len(selected), 'views': len(views),
                'native_parent_mean': sum(sum(v['score']['grade'] for v in r['views']) / len(r['views']) for r in selected) / len(selected),
                'fallback_views': sum(v['fallback'] for v in views),
                'handled_core_views': sum(v['core_execution']['core_executed'] for v in views),
                'native_core_correct_views': sum(v['core_execution']['core_executed'] and v['core_score']['correct'] for v in views),
                'learned_path_native_correct_not_semantic_certification': sum(v['core_execution']['core_executed'] and v['core_score']['correct'] and v['current_learned_mechanism_executed'] for v in views),
            }
        result[name] = {'native_parent_mean': score, 'datasets': datasets}
    return result


def c_changes(value):
    by_arm = {arm: {(r['source'], v['view']): v for r in value['recipes'][arm]['rows'] for v in r['views']}
              for arm in ('C_PG_residual', 'NoC_PG_residual')}
    assert by_arm['C_PG_residual'].keys() == by_arm['NoC_PG_residual'].keys()
    return [{'source': sid, 'view': vid,
             'with_C': by_arm['C_PG_residual'][sid, vid]['score'],
             'without_C': by_arm['NoC_PG_residual'][sid, vid]['score']}
            for sid, vid in by_arm['C_PG_residual']
            if by_arm['C_PG_residual'][sid, vid]['score']['grade'] != by_arm['NoC_PG_residual'][sid, vid]['score']['grade']]


def run():
    original = read(OLD / 'scored_results.json')
    result = {'new_model_calls': 0, 'no_library_updates': True, 'TEST_opened': False,
              'goal_complete': False, 'original_valid_DEV': summarize(original),
              'original_C_changed_views': c_changes(original), 'historical_baselines': {}}
    paths = [OLD / 'scored_results.json']
    for name in ('NoSkill', 'FreeEvolution', 'Full'):
        path = ROOT / 'artifacts/legal_skill_evolution_20261111/formal_v5/dev' / name / 'B8.json'
        value = read(path)
        assert len(value['results']) == 40
        result['historical_baselines'][name] = {
            'native_parent_mean': sum(r['native_grade'] for r in value['results']) / 40,
            'dataset_scores': value['native_parent_means_by_dataset'],
            'matched_current_C_M2_control': name != 'Full',
            'old_Full_is_a_different_learning_trajectory': name == 'Full'}
        paths.append(path)
    result['current_profile_fix_completed'] = (CURRENT / 'scored_results.json').exists()
    if result['current_profile_fix_completed']:
        path = CURRENT / 'scored_results.json'
        current = read(path)
        result['current_valid_DEV'] = summarize(current)
        result['current_C_changed_views'] = c_changes(current)
        paths.append(path)
    initial = []
    for arm in ('CoverageRecombine', 'FreeGlobalUpdate'):
        for path in sorted((CURRENT / 'initial' / arm).glob('*.json')):
            row = read(path)
            initial.append({'source': row['source'], 'arm': arm,
                'handled': row['execution']['handled'], 'answer': row['execution']['answer'],
                'logical_component_reads': len(row['reads']),
                'error': row.get('error'),
                'unrepresented_native_families': row.get('plan', {}).get('unrepresented_native_families', []),
                'unresolved': row.get('grounded', {}).get('unresolved', []),
                'not_a_source_semantic_certificate': True})
            paths.append(path)
    result['current_initial_routes'] = initial
    result['current_followup_routes'] = []
    for arm in ('CoverageRecombine', 'FreeGlobalUpdate'):
        for path in sorted((CURRENT / 'followup' / arm).glob('*.json')):
            row = read(path)
            result['current_followup_routes'].append({'arm': arm,
                'source_record': str(path.relative_to(ROOT)),
                'eligible': row.get('eligible'), 'reason': row.get('reason'),
                'policies': {name: {'handled': p.get('execution', {}).get('handled'),
                    'answer': p.get('execution', {}).get('answer'),
                    'error': p.get('error'), 'action_reason': p.get('action', {}).get('reason')}
                    for name, p in row.get('policies', {}).items()}})
            paths.append(path)
    result['evidence_sha256'] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    OUT.mkdir(parents=True, exist_ok=True)
    filename = 'result_review_final.json' if result['current_profile_fix_completed'] else 'result_review_inflight.json'
    path = OUT / filename
    body = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if path.exists():
        # Inflight observations are snapshots; a completed review is immutable.
        if result['current_profile_fix_completed']:
            assert path.read_text() == body
        else:
            path = OUT / ('result_review_inflight_' + hashlib.sha256(body.encode()).hexdigest()[:12] + '.json')
    path.write_text(body)
    print(json.dumps({'review': str(path.relative_to(ROOT)),
        'current_completed': result['current_profile_fix_completed'],
        'current_scores': {k: v['native_parent_mean'] for k, v in result.get('current_valid_DEV', {}).items()}}))


if __name__ == '__main__':
    run()
