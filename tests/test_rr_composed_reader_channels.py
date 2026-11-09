"""Recorded failure coverage, legacy numerical equivalence and frozen recovery."""
import json
from pathlib import Path
import unittest
import numpy as np

from legal_skill_guard.rr.composed_reader_channels import (
    POST, function_closure, primitive_functions, fit_channels, forecasts)
from legal_skill_guard.rr.semantic_learning import H, forecasts as legacy_forecasts

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / 'artifacts/rr_method_redesign_20261109/semantic_disambiguation_acquisition_v1_20261109'


class ComposedReaderRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frozen = json.loads((OLD / 'frozen_learning.json').read_text())
        cls.grammar = function_closure()
        cls.model = fit_channels(cls.frozen['training_rows'])

    def test_recorded_noncommuting_unknown_and_role_transfer(self):
        tables = [f['table'] for f in self.grammar]
        self.assertIn([0 if other == 2 else other for own, other in H], tables)
        before_negation = [1 - (0 if other == 2 else other) for own, other in H]
        after_negation = [0 if other == 2 else 1 - other for own, other in H]
        self.assertIn(before_negation, tables)
        self.assertIn(after_negation, tables)
        self.assertNotEqual(before_negation, after_negation)

    def test_semantic_closure_has_no_alias_prior_multiplicity(self):
        tables = [tuple(f['table']) for f in self.grammar]
        self.assertEqual(len(tables), len(set(tables)))
        for table in tables:
            for post in POST.values():
                self.assertIn(tuple(post[v] for v in table), tables)

    def test_actual83_fixed_slot_was_excluded_by_primitive_grammar(self):
        grades = json.loads((ROOT / 'reports/method_redesign_20261109/M1M2_real_TRAIN_results.json').read_text())
        rows = [r for r in grades['rows'] if r['case_id'].startswith('TRAIN83:')]
        def matches(f):
            return all(f['table'][H.index(tuple(r['h']))] == r['y'][0] for r in rows)
        self.assertFalse(any(matches(f) for f in primitive_functions()))
        self.assertTrue(any(matches(f) for f in self.grammar))

    def test_primitive_restriction_reproduces_original_frozen_joint(self):
        restricted = fit_channels(self.frozen['training_rows'], primitive_functions())
        for h in H:
            for context in [[0, 0], [1, 0], [0, 1]]:
                old = legacy_forecasts(self.frozen['models'], h, context)['structured']
                new = forecasts(restricted, h, context)['joint']
                np.testing.assert_allclose(new, old, atol=1e-12, rtol=0.)

    def test_closure_distribution_and_exact_json_recovery(self):
        recovered = json.loads(json.dumps(self.model))
        for h in H:
            before = forecasts(self.model, h, [1, 0])
            self.assertEqual(before, forecasts(recovered, h, [1, 0]))
            for p in before.values():
                self.assertTrue(all(v > 0 for v in p))
                self.assertAlmostEqual(sum(p), 1., places=11)
        self.assertEqual(len(self.model['training_mothers']), 2)

    def test_unasked_values_are_not_unknown_class(self):
        rows = json.loads(json.dumps(self.frozen['training_rows']))
        rows[0]['y'][0] = None
        with self.assertRaises(ValueError):
            fit_channels(rows)


if __name__ == '__main__':
    unittest.main()
