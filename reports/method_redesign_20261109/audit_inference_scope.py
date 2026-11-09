"""Separate frozen-channel inference, parameter identification and source support.

Read-only replay of existing TRAIN forecasts. Full likelihood support is not
observational equivalence; a MAP prediction is not a source semantic proof.
This audit changes no learned asset, prediction, raw response or scoring file.
"""
from datetime import datetime, timezone
import hashlib
import json
import numpy as np

from experiments.rr_v2_semantic_learning import STAGE, REPORT, read, check_frozen
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.semantic_learning import H, Y, OPS, transform

TOLERANCE = 1e-12


def geometry(distributions):
    p = np.asarray(distributions, dtype=float)
    assert p.shape == (9, 81) and np.all(p > 0)
    assert np.allclose(p.sum(axis=1), 1., rtol=0., atol=TOLERANCE)
    pairs = [{'left_h': list(H[i]), 'right_h': list(H[j]),
              'total_variation': float(np.abs(p[i] - p[j]).sum() / 2.)}
             for i in range(len(H)) for j in range(i)]
    equivalent = {str(list(h)): [list(H[j]) for j in range(len(H))
                  if float(np.abs(p[i] - p[j]).sum() / 2.) <= TOLERANCE]
                  for i, h in enumerate(H)}
    return {'all_nine_h_have_full_support': True,
            'minimum_pairwise_total_variation': min(r['total_variation'] for r in pairs),
            'distribution_equivalence_sets_at_fixed_parameters': equivalent,
            'all_nine_distributions_are_distinct_at_tolerance': all(len(v) == 1 for v in equivalent.values()),
            'pairwise_total_variations': pairs}


def main():
    check_frozen()
    blind_path = STAGE / 'blind_predictions.json'
    score_path = REPORT / 'M1M2_real_TRAIN_results.json'
    paths = [STAGE / 'frozen_learning.json', blind_path, score_path]
    original_hashes = {str(p.relative_to(STAGE.parents[2])): hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in paths}
    blind = read(blind_path)
    prior = np.exp(-.5 * np.array([sum(v != 'self' for v in op) for op in OPS]))
    prior /= prior.sum()
    untrained = []
    for h in H:
        p = np.full(81, .05 / 81)
        for op, weight in zip(OPS, prior):
            p[Y.index(tuple(transform(h, op)))] += .95 * weight
        untrained.append(p.tolist())
    prior_geometry = geometry(untrained)
    # Complete distribution comparisons are computed before opening grading rows.
    geometries = {cid: {model: geometry([f[model] for f in case['conditional_forecasts']])
                       for model in case['conditional_forecasts'][0]}
                  for cid, case in blind['cases'].items()}
    original = read(score_path)
    rows = []
    for row in original['rows']:
        cid = row['case_id']; yi = Y.index(tuple(row['y'])); models = {}
        for model in blind['cases'][cid]['conditional_forecasts'][0]:
            likelihood = np.array([f[model][yi] for f in blind['cases'][cid]['conditional_forecasts']])
            posterior = likelihood / likelihood.sum()  # original uniform h prior
            best = float(posterior.max())
            ties = [list(H[i]) for i, value in enumerate(posterior) if abs(value - best) <= TOLERANCE]
            models[model] = {'h_posterior': posterior.tolist(), 'uniform_h_prior': True,
                'MAP_ties': ties, 'MAP_unique_correct_for_local_labels': ties == [row['h']],
                'posterior_mass_at_MAP': best, 'positive_likelihood_h_count': int((likelihood > 0).sum()),
                'source_frame_accepted_and_correct_for_this_prediction':
                    ties == [row['h']] and row['all_roles_candidate_covered'],
                'geometry': geometries[cid][model]}
        rows.append({'case_id': cid, 'mother': row['mother'], 'context': blind['cases'][cid]['context'],
                     'observed_y': row['y'], 'teacher_h_for_scoring_only': row['h'],
                     'models': models})
    after = {str(p.relative_to(STAGE.parents[2])): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    assert original_hashes == after
    destination = REPORT / 'inference_scope_audit.json'
    out = {'captured_utc': read(destination)['captured_utc'] if destination.exists() else datetime.now(timezone.utc).isoformat(),
        'analysis_kind': 'Post-hoc existing TRAIN inference-contract audit; no new blind experiment',
        'new_model_calls': 0, 'new_sources_or_labels': 0, 'probability_tolerance': TOLERANCE,
        'frozen_files_unchanged': original_hashes,
        'full_support_does_not_imply_observational_equivalence': True,
        'identification_claim_is_conditional_on_frozen_channel_parameters': True,
        'joint_unknown_h_and_channel_parameters_identification_proved': False,
        'one_trajectory_is_not_certain_recovery': True,
        'posterior_values_are_not_empirically_calibrated': True,
        'untrained_same_grammar_geometry': prior_geometry,
        'distinct_conditional_distributions_are_not_learned_method_success': True,
        'all_original_models_fixed_parameter_distinct_h_distributions': {
            model: all(r['models'][model]['geometry']['all_nine_distributions_are_distinct_at_tolerance'] for r in rows)
            for model in rows[0]['models']},
        'local_MAP_unique_correct': {model: sum(r['models'][model]['MAP_unique_correct_for_local_labels'] for r in rows)
                                     for model in rows[0]['models']},
        'local_MAP_plus_complete_accepted_source_frame_correct': {
            model: sum(r['models'][model]['source_frame_accepted_and_correct_for_this_prediction'] for r in rows)
            for model in rows[0]['models']},
        'case_count': len(rows), 'independent_excluded_TRAIN_mothers': len({r['mother'] for r in rows}),
        'per_case': rows,
        'decision': 'Correct the interpretation of the old unresolved field: source proof was absent, not evidence of equal frozen likelihood distributions. Do not seek perfect anchors or add a zero-risk requirement. The same-information controls and source-candidate deficits still prevent independent contribution acceptance.',
        'native_legal_answers_evaluated': False, 'new_core_method_advantage_claimed': False,
        'goal_complete': False}
    immutable_json(destination, out)
    print(json.dumps({k: v for k, v in out.items() if k not in ('per_case', 'untrained_same_grammar_geometry', 'frozen_files_unchanged')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
