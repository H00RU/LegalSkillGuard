"""Partial-supervision revision checks; fixtures are not legal study examples."""
from copy import deepcopy
import unittest

from legal_skill_guard.skill_evolution.relational_learning import fit_composition
from legal_skill_guard.skill_evolution.relational_rules import context_identity, language_identity
from tests.test_skill_evolution_relational_learning import atom, context, rule


class CompositionRevisionTests(unittest.TestCase):
    def setUp(self):
        x = {'var': 'X'}
        self.language = {'signatures': {
            'present': {'arguments': ['node'], 'kind': 'observed'},
            'other': {'arguments': ['node'], 'kind': 'observed'},
            'out': {'arguments': ['node'], 'kind': 'output'}}, 'constants': {},
            'rules': [rule('seen', atom('out', x), atom('present', x)),
                      rule('unseen', atom('out', x), atom('other', x))]}

    def test_unactivated_prior_branch_is_preserved_without_filling_any_fact(self):
        c = context('one', [atom('present', 'a')], required=[atom('out', 'a')])
        original = deepcopy(c)
        fresh = fit_composition(self.language, [c])
        revision = fit_composition(self.language, [c], prior_rule_ids=['seen', 'unseen'])
        self.assertEqual(fresh['selected_rule_ids'], ['seen'])
        self.assertEqual(revision['selected_rule_ids'], ['seen', 'unseen'])
        self.assertEqual(revision['selection_edits'], 0)
        self.assertEqual(c, original)

    def test_hard_counterevidence_removes_a_prior_rule(self):
        c = context('one', [atom('present', 'a'), atom('other', 'b')],
                    required=[atom('out', 'a')], forbidden=[atom('out', 'b')])
        got = fit_composition(self.language, [c], prior_rule_ids=['seen', 'unseen'])
        self.assertEqual(got['selected_rule_ids'], ['seen'])
        self.assertEqual(got['selection_edits'], 1)

    def test_native_loss_outranks_preservation_and_unknowns_remain_possible(self):
        c = context('one', [atom('present', 'a')],
                    unknown=[[[atom('other', 'b')], []]])
        vocabulary = [atom('out', 'a'), atom('out', 'b')]
        c['theory_constraints'] = {
            'status': 'complete', 'language_sha256': language_identity(self.language),
            'context_sha256': context_identity(c), 'vocabulary': vocabulary,
            'allowed_theories': [[atom('out', 'a')]], 'optimization': 'native_loss',
            'scored_theories': [{'theory': [], 'native_loss': 1},
                {'theory': [atom('out', 'a')], 'native_loss': 0},
                {'theory': [atom('out', 'b')], 'native_loss': 2},
                {'theory': vocabulary, 'native_loss': 1}]}
        got = fit_composition(self.language, [c], prior_rule_ids=['unseen'])
        self.assertEqual(got['selected_rule_ids'], ['seen'])
        self.assertEqual(got['native_loss'], 0)
        self.assertTrue(got['all_supplied_partial_constraints_hold_for_every_declared_possible_observation'])
        self.assertEqual(len(c['unknown_groups'][0]), 2)

    def test_prior_cannot_introduce_missing_rules_or_ambiguous_ids(self):
        c = context('one', [])
        for prior in (['invented'], ['seen', 'seen'], 'seen'):
            with self.assertRaises(ValueError):
                fit_composition(self.language, [c], prior_rule_ids=prior)


if __name__ == '__main__':
    unittest.main()
