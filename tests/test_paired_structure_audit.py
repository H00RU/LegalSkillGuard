"""Reject renamed-source novelty and preserve relational dependencies."""
from copy import deepcopy
import unittest

from legal_skill_guard.paired_interfaces.structure_audit import combinations_by_key, compare_target


class StructureAuditTests(unittest.TestCase):
    def graph(self):
        return {'nodes': [{'id': i, 'kind': kind, 'concept': concept, 'name': i}
                          for i, kind, concept in [('e', 'event', 'service'),
                              ('p', 'person', 'worker'), ('q', 'person', 'employer')]],
                'relations': [{'predicate': pred, 'arguments': args, 'status': 'stated',
                               'value': None, 'unit_id': 0, 'quote': pred}
                              for pred, args in [('worker', ['e', 'p']), ('employer', ['e', 'q'])]]}

    def test_ids_names_order_and_amount_literals_cannot_create_novelty(self):
        graph = self.graph()
        renamed = deepcopy(graph)
        mapping = {'e': 'z99', 'p': 'arbitrary_1', 'q': 'arbitrary_2'}
        for node in renamed['nodes']:
            node['id'] = mapping[node['id']]
            node['name'] = 'Different display name'
        for edge in renamed['relations']:
            edge['arguments'] = [mapping[value] for value in edge['arguments']]
            edge['value'] = 1831
            edge['quote'] = 'Different source wording'
        renamed['relations'].reverse()
        renamed['nodes'].reverse()
        for typed in (False, True):
            self.assertEqual(set(combinations_by_key(graph, typed=typed)),
                             set(combinations_by_key(renamed, typed=typed)))

    def test_same_event_binding_differs_from_a_role_or_endpoint_reconnection(self):
        graph = self.graph()
        reconnected = deepcopy(graph)
        reconnected['relations'][1]['arguments'] = ['e', 'p']
        for typed in (False, True):
            self.assertNotEqual(set(combinations_by_key(graph, typed=typed)),
                                set(combinations_by_key(reconnected, typed=typed)))
        result = compare_target(reconnected, [graph], typed=True)
        self.assertTrue(result['annotation_unseen_combinations'])
        self.assertFalse(result['novel_natural_structure_established'])
        self.assertFalse(result['training_source_absence_verified'])

    def test_unknown_and_negation_are_not_positive_fact_completion(self):
        graph = self.graph()
        original = set(combinations_by_key(graph, typed=False))
        graph['relations'][1]['status'] = 'unknown'
        self.assertFalse(combinations_by_key(graph, typed=False))
        graph['relations'][1]['status'] = 'negated'
        self.assertNotEqual(original, set(combinations_by_key(graph, typed=False)))


if __name__ == '__main__':
    unittest.main()
