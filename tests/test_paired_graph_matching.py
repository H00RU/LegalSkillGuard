import unittest

from legal_skill_guard.paired_interfaces.graph_matching import GraphMatchLimit, typed_bindings
from legal_skill_guard.paired_interfaces.structural_channel import Fact, Graph


class GraphPatternTests(unittest.TestCase):
    def test_small_joint_error_matches_large_graph_without_permutation_product(self):
        nodes = tuple([(f'p{i}', 'person') for i in range(100)] + [('e', 'event')])
        graph = Graph(nodes, frozenset({Fact('worker', ('e', 'p67')), Fact('recipient', ('e', 'p89'))}), 's', 'c')
        variables = (('?event', 'event'), ('?worker', 'person'), ('?recipient', 'person'))
        before = (Fact('worker', ('?event', '?worker')), Fact('recipient', ('?event', '?recipient')))
        self.assertEqual(list(typed_bindings(graph, variables, before, max_work=20)),
                         [{'?event': 'e', '?recipient': 'p89', '?worker': 'p67'}])

    def test_injective_entity_binding_keeps_roles_distinct(self):
        graph = Graph((('e', 'event'), ('p', 'person')), frozenset({
            Fact('worker', ('e', 'p')), Fact('recipient', ('e', 'p'))}), 's', 'c')
        variables = (('?e', 'event'), ('?p', 'person'), ('?q', 'person'))
        before = (Fact('worker', ('?e', '?p')), Fact('recipient', ('?e', '?q')))
        self.assertEqual(list(typed_bindings(graph, variables, before)), [])

    def test_exhausted_support_raises_instead_of_returning_a_selected_subset(self):
        graph = Graph(tuple((str(i), 'person') for i in range(5)), frozenset(), 's', 'c')
        with self.assertRaises(GraphMatchLimit):
            list(typed_bindings(graph, (('?p', 'person'), ('?q', 'person')), (), max_bindings=2))


if __name__ == '__main__':
    unittest.main()
