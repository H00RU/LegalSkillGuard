"""Joint evidence is retained without creating facts or merging alternative proofs."""
from copy import deepcopy
import unittest

from legal_skill_guard.skill_evolution.source_provenance_projection import preserve_joint_support
from legal_skill_guard.skill_evolution.source_composition import render_composition


def fixture():
    atom = lambda p, *args: {'predicate': p, 'arguments': list(args), 'sign': 'positive'}
    var = lambda v: {'var': v}
    language = {'signatures': {
        'root_support': {'arguments': ['term', 'unit'], 'kind': 'observed'},
        'emit': {'arguments': ['term', 'unit'], 'kind': 'output'}},
        'constants': {}, 'rules': [{'id': 'copy', 'head': atom('emit', var('A'), var('U')),
            'body': [atom('root_support', var('A'), var('U'))], 'cost': 1}]}
    renderers = [{'predicate': 'emit', 'term': ['wrapped', {'term_argument': 0}],
        'support_arguments': [1], 'support_from_terms': []}]
    spec = {'constructors': [
        {'name': 'leaf', 'meaning': 'An observed statement', 'sort': 'Norm', 'arguments': []},
        {'name': 'wrapped', 'meaning': 'An output containing its actual observed statement',
         'sort': 'Norm', 'arguments': ['Norm']}]}
    return language, renderers, spec


class JointSupportTests(unittest.TestCase):
    def test_cross_clause_witness_retained_and_alternative_occurrences_not_merged(self):
        language, renderers, spec = fixture()
        before = deepcopy((language, renderers))
        updated, output_renderers, changes = preserve_joint_support(language, renderers)
        self.assertEqual((language, renderers), before)
        self.assertEqual(updated['rules'][0]['body'], language['rules'][0]['body'])
        self.assertEqual(updated['rules'][0]['cost'], language['rules'][0]['cost'])
        self.assertEqual(output_renderers[0]['term'], renderers[0]['term'])
        self.assertEqual(len(changes), 1)
        encoded = {'visible_inputs': {'units': [{'id': i} for i in (15, 16, 18, 24)],
            'source_output': {'unresolved': ['missing timing remains unresolved']}},
            'term_nodes': {'a': ['leaf'], 'b': ['leaf']},
            'term_supports': {'a': [15, 16, 18], 'b': [24]}}
        result = {'status': 'sat', 'complete': True, 'possible_outputs': [],
            'unknown_observations_preserved': [], 'certain_outputs': [
            {'predicate': 'emit', 'arguments': ['a', 'a']},
            {'predicate': 'emit', 'arguments': ['b', 'b']}]}
        rows = render_composition(updated, output_renderers, encoded, result, spec)
        self.assertEqual([s['support_ids'] for s in rows['statements']], [[15, 16, 18], [24]])
        self.assertEqual(rows['unresolved'], ['missing timing remains unresolved'])

    def test_ambiguous_provenance_is_rejected_without_mutating_inputs(self):
        language, renderers, _ = fixture()
        extra = deepcopy(language['rules'][0]['body'][0]); extra['arguments'][0] = {'var': 'B'}
        language['rules'][0]['body'].append(extra)
        with self.assertRaisesRegex(ValueError, 'one explicit'):
            preserve_joint_support(language, renderers)

    def test_actual_legal_unit_coordinate_cannot_be_retyped_as_evidence(self):
        language, renderers, _ = fixture()
        renderers[0]['term'] = ['wrapped', {'scalar_argument': 1}, {'term_argument': 0}]
        with self.assertRaisesRegex(ValueError, 'evidence-only'):
            preserve_joint_support(language, renderers)
