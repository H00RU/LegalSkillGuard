"""Grade source bindings, retain empty numeric skills, inspect cached decisions."""
from datetime import datetime, timezone
import json
import numpy as np

from experiments.rr_v2_numeric_binding_pilot import ROOT, STAGE, read, sha
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.semantic_learning import H
from legal_skill_guard.rr.source_discrimination import execute_selector, learn_selector
from reports.method_redesign_20261109.audit_learning_attribution import factor_fit, factored_forecast
from reports.method_redesign_20261109.evaluate_source_bound_program import training_examples

REPORT = ROOT / 'reports/method_redesign_20261109'
OLD = ROOT / 'artifacts/rr_method_redesign_20261109/semantic_disambiguation_acquisition_v1_20261109'


def cached_decisions():
    frozen = read(OLD / 'frozen_learning.json'); blind = read(OLD / 'blind_predictions.json')
    grades = read(REPORT / 'M1M2_real_TRAIN_results.json')
    cases = {c['case_id']: c for c in read(OLD / 'seal.json')['cases']}
    ordinary = learn_selector(training_examples())
    result = []
    for grade in grades['rows']:
        cid = grade['case_id']; case = cases[cid]; context = blind['cases'][cid]['context']
        factors = factor_fit([r for r in frozen['training_rows'] if r['context'] == context] or frozen['training_rows'])
        # Original four models were forecast before these responses; factor
        # control remains the previously reported induction-only diagnostic.
        conditional = [{**d, 'factorized_same_grammar': factored_forecast(h, factors)}
            for h, d in zip(H, blind['cases'][cid]['conditional_forecasts'])]
        decisions = {}
        for model in conditional[0]:
            p = np.array([row[model] for row in conditional]).reshape(9, 9, 9)
            d = H.index(tuple(grade['y'][:2])); r = H.index(tuple(grade['y'][2:]))
            values = {'D_only': p.sum(axis=2)[:, d], 'R_only': p.sum(axis=1)[:, r], 'D_and_R': p[:, d, r]}
            decisions[model] = {mode: [list(H[i]) for i in np.flatnonzero(abs(v - v.max()) < 1e-12)]
                                for mode, v in values.items()}
        source = execute_selector(ordinary, case['facts'], case['focus'])
        # Grade after decisions; never use grade.h as an inference input.
        result.append({'case_id': cid, 'mother': grade['mother'], 'teacher_local_h_for_grading': grade['h'],
            'MAP_tie_sets': decisions, 'source_program_prediction': source['prediction'],
            'source_program_exact_frame_covered': any(all(candidate['values'][name] == grade['teacher_frame'][name]
                for name in ('payer', 'payee', 'work_activity', 'payment_medium')) for candidate in source['candidates']),
            'source_program_model_requests': 0, 'actual_D_span_accepted': grade['candidate_source_span_valid']})
    scores = {model: {mode: sum(row['MAP_tie_sets'][model][mode] == [row['teacher_local_h_for_grading']]
                              for row in result) for mode in ('D_only', 'R_only', 'D_and_R')}
              for model in result[0]['MAP_tie_sets']}
    assert all(r['source_program_prediction'] == r['teacher_local_h_for_grading'] and r['source_program_exact_frame_covered'] for r in result)
    out = {'captured_utc': datetime.now(timezone.utc).isoformat(), 'new_model_calls': 0,
        'kind': 'Post-hoc cached decision audit, not a fresh blind experiment', 'rows': result,
        'unique_MAP_local_pair_correct': scores, 'cases': len(result), 'independent_mothers': 2,
        'shared_source_program_correct': len(result), 'shared_source_program_inference_requests': 0,
        'decision': 'The shared source program already reaches this finite sample correctness upper bound and request-cost lower bound. Do not build or buy a query policy for these same four local tasks.',
        'MAP_is_not_a_source_semantic_certificate': True, 'native_task_success_claimed': False,
        'full_policy_optimizer_built': False, 'goal_complete': False}
    immutable_json(REPORT / 'cached_reader_decision_audit.json', out)
    return {k: v for k, v in out.items() if k != 'rows'}


def main():
    seal = read(STAGE / 'seal.json'); closure = read(STAGE / 'execution_closed_before_teacher.json')
    assert closure['seal_sha256'] == sha(STAGE / 'seal.json')
    for rel, h in closure['executor_files'].items():
        assert sha(STAGE / rel) == h
    teacher = read(STAGE / 'teacher.json')
    cases = teacher['physical_response']['value']['cases']
    assert len(cases) == 2 and {c['case_id'] for c in cases} == {'TRAIN1', 'TRAIN6'}
    assert len(teacher['validation']) == 2 and all(c['status'] == 'decoded' for c in teacher['validation'])
    reviews = []
    for case in seal['cases']:
        executor = read(STAGE / ('executor_' + case['case_id'] + '.json'))
        assert executor['validation']['status'] == 'decoded'
        proposed = executor['validation']['decoded']['bindings']
        t = next(c for c in cases if c['case_id'] == case['case_id'])
        assert len(proposed) == len(t['independent_bindings']['bindings']) == 2
        assert not t['unresolved']
        assert [r['values'] for r in proposed] == t['independent_bindings']['bindings']
        assert all(r['single_price_source_unit_control'] is True for r in proposed)
        reviews.append({'case_id': case['case_id'], 'source': case['source'],
            'gross_asset_value_bindings': [r['values'] for r in proposed],
            'independent_teacher_exactly_agrees_on_this_case': True,
            'ordinary_single_price_control_supports_these_proposed_assets': True,
            'asset_detection_is_from_actual_executor_not_free_oracle_input': True,
            'teacher_review': t['relation_and_completeness_review'], 'new_numeric_misread_errors': 0,
            'native_EC_EV_evaluated': False})
    assets = {'training_mothers': [c['source'] for c in seal['cases']], 'training_cases': ['TRAIN1', 'TRAIN6'],
        'actual_bindings_reviewed': 4, 'verified_numeric_binding_errors': [],
        'M1_numeric_discrimination_skills': [], 'M2_numeric_error_channels': [],
        'reason': 'No verified numeric binding error in these two induction mothers; do not create an identity/error skill or buy a repair/excluded-source experiment.',
        'previous_SARA_assets_unchanged': True, 'numeric_library_is_intentionally_empty': True,
        'unique_contribution_established': False, 'goal_complete': False}
    immutable_json(STAGE / 'numeric_method_assets.json', assets)
    immutable_json(REPORT / 'numeric_binding_results.json', {
        'captured_utc': datetime.now(timezone.utc).isoformat(), 'reviews': reviews, 'new_sources': 0,
        'induction_mothers': 2, 'bindings': 4, 'executor_calls': 2, 'teacher_calls': 1,
        'teacher_request_did_not_include_executor': teacher['teacher_did_not_receive_executor'],
        'numeric_method_assets': assets, 'excluded_sources_not_acquired': [11, 16],
        'new_full_build_started': False, 'TEST_started': False, 'paper_started': False, 'goal_complete': False})
    print(json.dumps({'numeric_reviews': reviews, 'numeric_assets': assets,
                      'cached_decision_audit': cached_decisions()}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
