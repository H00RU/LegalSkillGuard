"""One induction-only, grammar-free control; no fitting/tuning on held grades.

Exact (h,context) empirical memory backs off to the original fitted independent
matrix. The original structured model's fixed unexplained mass is retained as
the cache mixture weight; no threshold, feature or hyperparameter is scanned.
"""
from datetime import datetime, timezone
import hashlib
import json
import math
import numpy as np

from experiments.rr_v2_semantic_learning import STAGE, REPORT, read, check_frozen
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.semantic_learning import H, Y


def empirical_backoff(training, h, context, independent, residual):
    matching = [r for r in training if r['h'] == list(h) and r['context'] == list(context)]
    if not matching:
        return list(independent), {'route': 'original_independent_matrix', 'matching_induction_cases': []}
    counts = np.zeros(len(Y))
    for row in matching:
        counts[Y.index(tuple(row['y']))] += row['weight']
    empirical = counts / counts.sum()
    p = (1. - residual) * empirical + residual * np.array(independent)
    assert np.isclose(p.sum(), 1.) and np.all(p > 0)
    return p.tolist(), {'route': 'exact_h_context_memory_with_independent_residual',
                        'matching_induction_cases': [r['case_id'] for r in matching]}


def main():
    f = check_frozen(); blind = read(STAGE / 'blind_predictions.json')
    residual = f['models']['structured']['residual_mass']
    assert residual == .05
    training = f['training_rows']
    assert {r['case_id'].split(':')[0] for r in training} == {'TRAIN71', 'TRAIN79'}
    # Compile every h-conditioned forecast first; grades are opened afterward.
    compiled = {}
    for cid, case in blind['cases'].items():
        rows = []
        for h, prior in zip(H, case['conditional_forecasts']):
            p, route = empirical_backoff(training, h, case['context'], prior['independent'], residual)
            assert len(p) == 81 and abs(sum(p) - 1.) < 1e-12
            rows.append({'h': list(h), 'joint_distribution': p, 'route': route})
        compiled[cid] = rows
    original = read(REPORT / 'M1M2_real_TRAIN_results.json')
    scored = []
    for row in original['rows']:
        all_h = compiled[row['case_id']]
        p = all_h[H.index(tuple(row['h']))]['joint_distribution']; yi = Y.index(tuple(row['y']))
        maxp = max(p)
        modes = [list(Y[i]) for i, v in enumerate(p) if abs(v - maxp) < 1e-12]
        structured = blind['cases'][row['case_id']]['conditional_forecasts'][H.index(tuple(row['h']))]['structured']
        structured_max = max(structured)
        structured_modes = [list(Y[i]) for i, v in enumerate(structured)
                            if abs(v - structured_max) < 1e-12]
        likelihood = [d['joint_distribution'][yi] for d in all_h]; best = max(likelihood)
        decoded = [list(H[i]) for i, v in enumerate(likelihood) if abs(v - best) < 1e-12]
        scored.append({'case_id': row['case_id'], 'mother': row['mother'], 'teacher_h_for_grading': row['h'],
            'observed_y': row['y'], 'weight': row['weight'],
            'negative_log_likelihood': -math.log(p[yi]), 'observed_probability': p[yi],
            'joint_mode_ties': modes, 'joint_mode_unique_correct': modes == [row['y']],
            'original_structured_joint_mode_ties': structured_modes,
            'original_structured_joint_mode_unique_correct': structured_modes == [row['y']],
            'original_structured_single_argmax_correct': max(range(len(Y)), key=lambda i: structured[i]) == yi,
            'inverse_MAP_ties': decoded, 'inverse_MAP_unique_correct': decoded == [row['h']],
            'route_at_grading_h': all_h[H.index(tuple(row['h']))]['route']})
    total_weight = sum(r['weight'] for r in scored)
    destination = REPORT / 'reader_backoff_control_results.json'
    captured = (read(destination)['captured_utc'] if destination.exists()
                else datetime.now(timezone.utc).isoformat())
    out = {'captured_utc': captured, 'analysis_kind':
        'Post-hoc stronger-control diagnosis on already observed TRAIN exclusions; not a new confirmatory experiment',
        'new_model_calls': 0, 'residual_mass_inherited_unchanged': residual,
        'new_features_or_hyperparameters_scanned': False,
        'operator_grammar_or_role_copy_used': False, 'teacher_h_is_only_for_scoring': True,
        'all_h_forecasts_compiled_before_reading_grading_rows_in_this_script': True,
        'original_frozen_learning_sha256': hashlib.sha256((STAGE / 'frozen_learning.json').read_bytes()).hexdigest(),
        'mean_joint_NLL': sum(r['weight'] * r['negative_log_likelihood'] for r in scored) / total_weight,
        'unique_joint_mode_correct': sum(r['joint_mode_unique_correct'] for r in scored),
        'unique_inverse_MAP_correct': sum(r['inverse_MAP_unique_correct'] for r in scored),
        'cases': len(scored), 'independent_excluded_mothers': 2, 'per_case': scored,
        'original_structured_joint_NLL': original['forecast_scores']['structured']['mean']['negative_log_likelihood'],
        'common_probability_tie_tolerance': 1e-12,
        'original_structured_unique_joint_mode_correct': sum(r['original_structured_joint_mode_unique_correct'] for r in scored),
        'original_structured_single_argmax_correct': sum(r['original_structured_single_argmax_correct'] for r in scored),
        'original_structured_inverse_MAP_correct': sum(
            r['joint_inference']['structured']['MAP_ties'] == [r['h']]
            for r in original['rows']),
        'source_frame_acceptance_is_separate': True, 'native_legal_answers_evaluated': False,
        'no_new_independent_contribution_claim': True, 'goal_complete': False}
    immutable_json(destination, out)
    print(json.dumps({k: v for k, v in out.items() if k != 'per_case'}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
