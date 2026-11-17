import itertools
import unittest

from legal_skill_guard.paired_interfaces.empirical_channel import (
    IndexedJointEdit, graph_record, indexed, learn_dictionary, restore_graph)
from legal_skill_guard.paired_interfaces.graph_matching import GraphMatchLimit
from legal_skill_guard.paired_interfaces.structural_channel import (
    Fact, Graph, JointEdit, Pair, learn_dictionary as finite_dictionary)
from experiments.two_method_graph_corpus import fit_complete_groups, serialize_pair


class EmpiricalChannelMatching(unittest.TestCase):
    def test_indexed_images_equal_exhaustive_images_across_all_small_relation_worlds(self):
        nodes = (('e', 'event'), ('f', 'event'), ('a', 'person'), ('b', 'person'))
        atoms = [Fact('worker', (e, p)) for e in ('e', 'f') for p in ('a', 'b')]
        for flags in itertools.product((False, True), repeat=len(atoms)):
            graph = Graph(nodes, frozenset(f for f, yes in zip(atoms, flags) if yes), 's', 'c')
            for systematic in (False, True):
                edit = JointEdit((('?e', 'event'), ('?p', 'person')), (Fact('worker', ('?e', '?p')),),
                                 (Fact('recipient', ('?e', '?p')),), systematic)
                self.assertEqual(indexed(edit).images(graph), edit.images(graph))

    def test_a_small_role_swap_on_a_large_graph_uses_complete_fact_joins(self):
        graph = Graph(tuple([('e', 'event')] + [('p' + str(i), 'person') for i in range(100)]),
            frozenset({Fact('worker', ('e', 'p0')), Fact('recipient', ('e', 'p1'))}), 's', 'c')
        edit = IndexedJointEdit((('?e', 'event'), ('?a', 'person'), ('?b', 'person')),
            (Fact('worker', ('?e', '?a')), Fact('recipient', ('?e', '?b'))),
            (Fact('worker', ('?e', '?b')), Fact('recipient', ('?e', '?a'))))
        result = edit.images(graph, max_work=10)
        self.assertEqual(len(result), 1)
        self.assertIn(Fact('worker', ('e', 'p1')), next(iter(result)).facts)
        self.assertEqual(restore_graph(graph_record(graph)), graph)

    def test_work_exhaustion_does_not_return_a_partial_favorable_outcome(self):
        graph = Graph((('a', 'person'), ('b', 'person')), frozenset(), 's', 'c')
        edit = IndexedJointEdit((('?p', 'person'),), (), (Fact('seen', ('?p',)),))
        with self.assertRaises(GraphMatchLimit):
            edit.images(graph, max_bindings=1)

    def test_learned_dictionary_preserves_the_frozen_algorithm_and_role_gate(self):
        graph = Graph((('e', 'event'), ('a', 'person'), ('b', 'person')),
            frozenset({Fact('worker', ('e', 'a')), Fact('recipient', ('e', 'b'))}), 's', 'c')
        other = Graph(graph.nodes, frozenset({Fact('worker', ('e', 'b')), Fact('recipient', ('e', 'a'))}), 's', 'c')
        pair = Pair('fixture', graph, other, 'v', 'development', 'constructed invariant')
        expected, actual = finite_dictionary([pair]), learn_dictionary([pair])
        self.assertEqual({e.identity for e in expected['edits']}, {e.identity for e in actual['edits']})
        for edit in actual['edits']:
            original = next(e for e in expected['edits'] if e.identity == edit.identity)
            self.assertEqual(edit.images(graph), original.images(graph))
        with self.assertRaises(ValueError):
            learn_dictionary([Pair('c', graph, other, 'v', 'calibration', 'fixture')])

    def test_locked_incomplete_groups_are_not_fitted_and_real_failure_shapes_are_unknown(self):
        graph = Graph((('a', 'person'),), frozenset({Fact('present', ('a',))}), 's', 'c')
        failed = Graph((('a', 'person'), ('failure', 'unresolved_read')),
                       frozenset({Fact('read_failure', (), 'unread')}), 's', 'c')
        inventory, pairs = [], []
        for source, role, observed in [('dev', 'development', graph), ('cal', 'calibration', failed)]:
            item = {'source': source, 'role': role, 'context': 'c', 'version': 'v', 'dataset': 'fixture',
                    'native_tasks': ['q'], 'plan': 'records', 'reference_reviewed': True, 'read_settled': True}
            inventory.append(item)
            pairs.append({**item, 'pair': serialize_pair(Pair(source, graph, observed, 'v', role,
                'constructed integration fixture, no actual model call')),
                'reference_native_consumer_domain': {'handled': False}})
        corpus = {'inventory': inventory, 'pairs': pairs}
        result = fit_complete_groups(corpus)['groups'][0]
        self.assertTrue(result['fitted'])
        self.assertEqual(result['channels']['unrestricted']['diagnostics']['unmatched_pairs'], 1)
        self.assertEqual(result['reference_native_domain_views'], 0)
        inventory[1]['reference_reviewed'] = False
        pending = fit_complete_groups(corpus)['groups'][0]
        self.assertFalse(pending['fitted'])
        self.assertEqual(pending['missing_reference_reviews'], 1)

    def test_unrelated_consumer_does_not_change_a_fixed_selection_family_confidence_level(self):
        inventory, pairs = [], []
        for context in ('one', 'unrelated'):
            graph = Graph((('a', 'person'),), frozenset({Fact('present', ('a',))}), 's', context)
            for source, role in [('dev', 'development'), ('cal', 'calibration')]:
                item = {'source': source, 'role': role, 'context': context, 'version': 'v',
                        'dataset': 'fixture', 'native_tasks': [context], 'plan': 'records',
                        'reference_reviewed': True, 'read_settled': True}
                inventory.append(item)
                pairs.append({**item, 'pair': serialize_pair(Pair(source, graph, graph, 'v', role,
                    'constructed confidence-scope invariant')),
                    'reference_native_consumer_domain': {'handled': False}})
        single = fit_complete_groups({'inventory': inventory[:2], 'pairs': pairs[:2]})
        multiple = fit_complete_groups({'inventory': inventory, 'pairs': pairs})
        target = next(g for g in multiple['groups'] if g['context'] == 'one')
        self.assertEqual(single['groups'][0]['channels']['unrestricted']['alpha'],
                         target['channels']['unrestricted']['alpha'])
        self.assertEqual(target['alpha_per_plan_and_mode'], .025)
        self.assertEqual(multiple['all_consumer_union_error_bound'], .1)
        self.assertFalse(multiple['global_95_percent_coverage_claimed'])


if __name__ == '__main__':
    unittest.main()
