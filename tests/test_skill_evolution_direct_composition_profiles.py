"""Exact reachable-profile tests, not additional research sources."""
from copy import deepcopy
import unittest

from legal_skill_guard.skill_evolution.direct_composition_profiles import admissible_direct_compositions
from legal_skill_guard.skill_evolution.relational_learning import fit_composition
from legal_skill_guard.skill_evolution.theory_supervision import admissible_theories, attach_scored_theories


def atom(name, *args):
    return {'predicate': name, 'arguments': list(args), 'sign': 'positive'}


def fixture(count):
    x, u = {'var': 'X'}, {'var': 'U'}
    language = {'signatures': {'bucket': {'arguments': ['group', 'text'], 'kind': 'observed'},
        'unit': {'arguments': ['unit'], 'kind': 'observed'},
        'emit': {'arguments': ['text', 'unit'], 'kind': 'output'}},
        'constants': {'group': ['many', 'few']}, 'rules': [
            {'id': name, 'cost': cost, 'head': atom('emit', x, u),
             'body': [atom('bucket', name, x), atom('unit', u)]}
            for name, cost in [('many', 2), ('few', 1)]]}
    library = {'language': language, 'renderers': [{'predicate': 'emit',
        'term': ['signal', {'scalar_argument': 0}], 'support_arguments': [1], 'support_from_terms': []}],
        'spec': {'constructors': [{'name': 'signal', 'sort': 'Norm', 'arguments': ['text'], 'meaning': 'Fixture'}]}}
    facts = [atom('unit', 7), atom('bucket', 'few', 'b'), *[atom('bucket', 'many', 'a' + str(i)) for i in range(count)]]
    observation = {'context': {'id': 'fixture', 'facts': facts, 'unknown_groups': [], 'required': [], 'forbidden': []},
        'visible_inputs': {'units': [{'id': 7, 'text': 'Fixture.'}], 'source_output': {'unresolved': []}},
        'term_nodes': {}, 'term_supports': {}, 'legacy_roots': {}}
    expected = {'a' + str(i) for i in range(count)}
    def check(output):
        accepted = {r['term'][1] for r in output['statements']} == expected
        return {'accepted': accepted, 'reason': 'fixture_match' if accepted else 'fixture_mismatch'}
    return library, observation, check


class DirectCompositionProfileTests(unittest.TestCase):
    def test_many_coemitted_heads_have_four_exact_program_outputs(self):
        library, observation, check = fixture(64)
        result = admissible_direct_compositions(library, observation, check)
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(len(result['vocabulary']), 65)
        self.assertEqual(result['finite_theory_count'], 4)
        self.assertEqual(result['relaxed_ground_output_subset_count'], 2 ** 65)
        self.assertTrue(result['not_a_complete_relaxed_representation_diagnostic'])
        self.assertEqual(result['accepted_theory_count'], 1)

    def test_fit_matches_full_relaxed_enumeration_without_changing_loss_or_cost(self):
        library, observation, check = fixture(2)
        full = admissible_theories(library, observation, check)
        reachable = admissible_direct_compositions(library, observation, check)
        self.assertEqual(full['finite_theory_count'], 8)
        self.assertEqual(reachable['finite_theory_count'], 4)
        fits = [fit_composition(library['language'], [attach_scored_theories(observation, result)['context']])
                for result in (full, reachable)]
        self.assertEqual(fits[0]['selected_rule_ids'], ['many'])
        self.assertEqual(fits[0]['selected_rule_ids'], fits[1]['selected_rule_ids'])
        self.assertEqual(fits[0]['native_loss'], fits[1]['native_loss'])
        self.assertEqual(fits[0]['cost'], fits[1]['cost'])

    def test_unknown_or_derived_dependencies_are_never_silently_removed(self):
        library, observation, check = fixture(2)
        unknown = deepcopy(observation)
        unknown['context']['unknown_groups'] = [[[atom('bucket', 'many', 'x')], []]]
        with self.assertRaisesRegex(ValueError, 'unknown is not filled'):
            admissible_direct_compositions(library, unknown, check)
        recursive = deepcopy(library)
        recursive['language']['rules'][0]['body'] = [atom('emit', {'var': 'X'}, {'var': 'U'})]
        with self.assertRaisesRegex(ValueError, 'recursive or derived'):
            admissible_direct_compositions(recursive, observation, check)
