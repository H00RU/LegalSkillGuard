"""Exact agreement with exhaustive selections; native errors never relax source checks."""
from copy import deepcopy
from itertools import combinations
import unittest
from unittest.mock import patch

from tests import test_skill_evolution_open_acquisition as fixture_module
from legal_skill_guard.skill_evolution.open_acquisition import execute
from legal_skill_guard.skill_evolution.lazy_native_selection import select
from legal_skill_guard.skill_evolution.relational_rules import canonical, context_identity, language_identity
from legal_skill_guard.skill_evolution.source_observations import fact


class LazyNativeSelectionTests(unittest.TestCase):
    def setUp(self):
        f = fixture_module.OpenAcquisitionTests()
        f.setUp()
        self.library = deepcopy(f.library)
        self.library['selected_rule_ids'] = ['broad']
        self.observations = [f.observation('one', 'Alpha.', 'first'), f.observation('two', 'Beta.', 'second')]

    def checker(self, sid):
        expected = sid == 'one'
        def check(output):
            correct = bool(output['statements']) == expected
            return {'accepted': correct, 'reason': 'software_fixture',
                'views': [{'core_executed': True, 'score': {'correct': correct}}]}
        return check

    def rows(self):
        rows = []
        for obs in self.observations:
            actual = execute(self.library, obs)
            rows.append({'source': obs['context']['id'], 'observation': obs,
                'actual': {'execution': actual, 'feedback': self.checker(obs['context']['id'])(actual['source_output'])}})
        return rows

    def exhaustive(self, rows):
        rules = self.library['language']['rules']
        candidates = []
        for n in range(len(rules)+1):
            for indices in combinations(range(len(rules)), n):
                library = deepcopy(self.library)
                ids = [rules[i]['id'] for i in indices]
                library['selected_rule_ids'] = ids
                loss, valid = 0, True
                for row in rows:
                    actual = execute(library, row['observation'])
                    theory = {canonical({k: v for k, v in a.items() if k != 'context_index'})
                        for a in actual['composition']['certain_outputs']}
                    context = row['observation']['context']
                    valid &= {canonical(a) for a in context['required']} <= theory
                    valid &= not bool({canonical(a) for a in context['forbidden']} & theory)
                    loss += not self.checker(row['source'])(actual['source_output'])['accepted']
                if valid:
                    candidates.append(((loss, len(set(ids)^{'broad'}), sum(rules[i]['cost'] for i in indices)), sorted(ids)))
        return min(candidates)

    def test_matches_all_subsets_and_complete_lexicographic_objective(self):
        rows = self.rows()
        result = select(self.library, rows, self.checker, ['broad'], timeout_seconds=10)
        expected, selected = self.exhaustive(rows)
        self.assertTrue(result['exact_optimum'])
        self.assertEqual((result['native_loss'], result['selection_edits'], result['complexity']), expected)
        self.assertEqual(result['selected_rule_ids'], selected)
        self.assertEqual(selected, ['join'])

    def test_source_constraint_preserved_with_unavoidable_native_error(self):
        self.observations[1]['context']['required'] = [fact('emit', 't1', 4)]
        rows = self.rows()
        result = select(self.library, rows, self.checker, ['broad'], timeout_seconds=10)
        expected, selected = self.exhaustive(rows)
        self.assertTrue(result['exact_optimum'])
        self.assertEqual((result['native_loss'], result['selection_edits'], result['complexity']), expected)
        self.assertEqual(result['selected_rule_ids'], selected)
        self.assertEqual(result['native_loss'], 1)

    def test_incomplete_prior_enumeration_is_samples_not_allowed_universe(self):
        rows = self.rows()
        obs = self.observations[0]
        profile = {'status': 'timeout', 'language_sha256': language_identity(self.library['language']),
            'context_sha256': context_identity(obs['context']), 'allowed_theories': None,
            'evaluations': [{'partial_source_constraints_satisfied': True, 'theory': [],
                'native_feedback': self.checker('one')({'statements': []})}]}
        result = select(self.library, rows, self.checker, ['broad'], samples=[{'source': 'one', 'profile': profile}], timeout_seconds=10)
        self.assertTrue(result['exact_optimum'])
        self.assertEqual(result['selected_rule_ids'], ['join'])

    def test_undeclared_possible_observation_is_not_filled(self):
        rows = self.rows()
        rows[0]['observation']['context']['unknown_groups'] = [[[], []]]
        with self.assertRaisesRegex(ValueError, 'complete observations'):
            select(self.library, rows, self.checker, ['broad'], timeout_seconds=10)

    def test_incomplete_solver_does_not_return_a_fitted_selection(self):
        with patch('legal_skill_guard.skill_evolution.lazy_native_selection._solve',
                return_value={'status': 'timeout', 'exhausted': False, 'cost': []}):
            result = select(self.library, self.rows(), self.checker, ['broad'], timeout_seconds=10)
        self.assertEqual(result['status'], 'timeout')
        self.assertIsNone(result['selected_rule_ids'])
        self.assertFalse(result['exact_optimum'])
        self.assertEqual(result['best_validated_selection']['native_loss'], 1)
        self.assertTrue(result['best_validated_selection']['all_supplied_partial_source_type_and_execution_checks_passed'])

    def test_invalid_incumbent_cannot_be_retained_after_timeout(self):
        self.observations[1]['context']['forbidden'] = [fact('emit', 't1', 4)]
        with patch('legal_skill_guard.skill_evolution.lazy_native_selection._solve',
                return_value={'status': 'timeout', 'exhausted': False, 'cost': []}):
            result = select(self.library, self.rows(), self.checker, ['broad'], timeout_seconds=10)
        self.assertIsNone(result['best_validated_selection'])


if __name__ == '__main__':
    unittest.main()
