"""Necessary checks for partial observations; no semantic efficacy claims."""
import copy
import unittest
import numpy as np

from legal_skill_guard.rr.observed_reader_learning import (
    compatible_answers, fit_observed_channels, fit_observed_factors,
    fit_observed_mixture, observed_forecasts, operator_likelihood, validate_rows,
)
from legal_skill_guard.rr.semantic_learning import H, OPS, Y, fit_channels, forecasts, transform
from reports.method_redesign_20261109.audit_learning_attribution import factor_fit
from experiments.rr_v2_semantic_learning import STAGE, read


class ObservedReaderLearningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = read(STAGE / 'frozen_learning.json')['training_rows']

    def test_fully_observed_case_reproduces_original_models_and_controls(self):
        actual = fit_observed_channels(self.rows)
        old = fit_channels(self.rows)
        np.testing.assert_allclose(actual['structured']['global'], old['structured']['global'], atol=1e-14)
        np.testing.assert_allclose(actual['unstructured_softmax'], old['unstructured_softmax'], atol=1e-14)
        np.testing.assert_allclose(actual['factorized_same_grammar']['global'], factor_fit(self.rows), atol=1e-14)
        for h in H:
            for context in ([0, 0], [1, 0], [1, 1]):
                new = observed_forecasts(actual, h, context); prior = forecasts(old, h, context)
                for name in prior:
                    np.testing.assert_allclose(new[name], prior[name], atol=1e-14)

    def test_missing_R_is_not_a_reported_unknown_R(self):
        row = {'h': [0, 0], 'y': [0, 0, None, None], 'weight': 1.}
        like = operator_likelihood([row])[0]
        self.assertEqual(like[OPS.index(('self', 'self', 'self', 'self'))],
                         like[OPS.index(('self', 'self', 'erase', 'erase'))])
        asserted_unknown = {**row, 'y': [0, 0, 2, 2]}
        p = operator_likelihood([asserted_unknown])[0]
        self.assertNotEqual(p[OPS.index(('self', 'self', 'self', 'self'))],
                            p[OPS.index(('self', 'self', 'erase', 'erase'))])

    def test_partial_likelihood_is_exact_sum_of_full_likelihoods(self):
        row = {'h': [0, 1], 'y': [1, 1, None, None], 'weight': 1.}
        partial = operator_likelihood([row])[0]
        full = [{**row, 'y': list(y)} for y in Y if y[:2] == (1, 1)]
        np.testing.assert_allclose(partial, operator_likelihood(full).sum(axis=0), atol=1e-15)

    def test_unasked_factor_and_confusion_slots_get_no_new_counts(self):
        before = fit_observed_factors(self.rows)
        row = {**self.rows[0], 'case_id': 'partial', 'h': [0, 0], 'y': [0, 0, None, None], 'weight': .5}
        after = fit_observed_factors(self.rows + [row])
        np.testing.assert_array_equal(before[2:], after[2:])
        old = fit_observed_channels(self.rows); new = fit_observed_channels(self.rows + [row])
        np.testing.assert_array_equal(old['independent'][2:], new['independent'][2:])

    def test_partial_softmax_and_joint_control_preserve_unobserved_symmetry(self):
        row = {'case_id': 'one', 'mother': 'TRAIN', 'context': [1, 0], 'h': [0, 0],
               'y': [1, 1, None, None], 'weight': 1.}
        fitted = fit_observed_channels([row]); dist = observed_forecasts(fitted, [0, 0], [1, 0])
        for name in ('unstructured_softmax', 'joint_empirical'):
            compatible = [dist[name][i] for i, y in enumerate(Y) if y[:2] == (1, 1)]
            np.testing.assert_allclose(compatible, np.repeat(compatible[0], 9), atol=1e-14)
            self.assertGreater(sum(compatible), 1 / 9)
        for p in dist.values():
            self.assertAlmostEqual(sum(p), 1.)

    def test_no_observation_and_bad_class_values_are_rejected(self):
        row = copy.deepcopy(self.rows[0])
        for value in ([None] * 4, [0, 0, True, None], [0, 0, 3, None]):
            with self.assertRaises(ValueError):
                validate_rows([{**row, 'y': value}])


if __name__ == '__main__':
    unittest.main()
