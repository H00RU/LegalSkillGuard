"""Literal inventory,source-order and annotation-boundary regressions.

No fee result is evaluated or fed back into these source annotations.
"""
from collections import Counter
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

from experiments import two_method_airline_inventory_reviews as reviews
from experiments.two_method_annotate import inputs
from experiments.two_method_graph_corpus import ROOT, read
from legal_skill_guard.paired_interfaces import graph_interface as gi, rich_graph_pairs
from legal_skill_guard.paired_interfaces.graph_evidence import normalize_graph_evidence
from legal_skill_guard.paired_interfaces.native_graph_consumers import airline
from legal_skill_guard.skill_evolution.clients import FrozenExecutor, FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger


class AirlineSourceReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.public = {s['key']: s for s in read(ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
        cls.locks = read(reviews.LOCK_PATH)

    def example(self, prefix):
        source = next(r['source'] for r in self.locks if r['source'].split(':')[1].startswith(prefix))
        task, _ = inputs(self.public[source])
        self.assertEqual(len(task['views']), 1)
        units = task['views'][0]['source_units']
        return source, units, reviews.reviewed_graph(source, units)

    def projected(self, graph, units):
        graph, _ = normalize_graph_evidence(graph, units)
        (world, _, _), _ = rich_graph_pairs.reference_graph(graph, {u['id']: u for u in units}, 'review-transport-test')
        return rich_graph_pairs.rich_graph(world)

    def measurements(self, graph):
        return {(e['arguments'][0], e['predicate']): e['value'] for e in graph['relations']
                if e['predicate'] in ('length', 'width', 'height', 'weight')}

    def test_twenty_views_156_occurrences_and_original_roles_have_exact_source_spans(self):
        self.assertEqual(Counter(r['role'] for r in self.locks), Counter(development=8, calibration=8, reference_only=4))
        count = 0
        for row in self.locks:
            _, units, graph = self.example(row['source'].split(':')[1][:8])
            checks = gi.validate(graph, units)
            self.assertTrue(checks['schema_and_source_spans_valid'])
            self.assertFalse(checks['source_semantic_truth_verified'])
            self.assertTrue(graph['scope_complete'])
            bags = [n for n in graph['nodes'] if n['kind'] == 'bag']
            count += len(bags)
            self.assertEqual(len(bags), len(units)-2)
            self.assertEqual(len(self.measurements(graph)), 4*len(bags))
            self.assertEqual({n['unit_id'] for n in bags}, set(range(1,len(bags)+1)))
        self.assertEqual(count, 156)

    def test_unreviewed_or_changed_sources_never_inherit_semantic_review(self):
        source, units, _ = self.example('e88c2c8f')
        for change in ('one_byte', 'omitted_bag', 'reordered_bags'):
            altered = deepcopy(units)
            if change == 'one_byte': altered[1]['text'] += ' '
            elif change == 'omitted_bag': altered.pop(2)
            else: altered[1], altered[2] = altered[2], altered[1]
            with self.assertRaisesRegex(ValueError, 'twenty exact source views'):
                reviews.reviewed_graph(source, altered)
        with self.assertRaisesRegex(ValueError, 'twenty exact source views'):
            reviews.reviewed_graph('RuleArena_Airline:unreviewed', units)

    def test_equal_weights_do_not_merge_distinct_bags_or_sort_dimensions(self):
        _, _, graph = self.example('bc47b812'); values = self.measurements(graph)
        self.assertEqual([values['bag_'+str(i), 'weight'] for i in range(1,6)], [7,53,53,51,58])
        self.assertEqual([values['bag_2', p] for p in ('length','width','height')], [48,33,24])
        self.assertEqual([values['bag_3', p] for p in ('length','width','height')], [38,16,10])
        _, _, graph = self.example('3e9dfb75'); values = self.measurements(graph)
        self.assertEqual([values['bag_5', p] for p in ('length','width','height')], [39,13,15])
        _, _, graph = self.example('3b3bf13a')
        self.assertEqual(self.measurements(graph)['bag_4','weight'], 100)

    def test_item_names_do_not_create_fee_class_or_bag_legal_title(self):
        for row in self.locks:
            graph = self.example(row['source'].split(':')[1][:8])[2]
            bags = {n['id'] for n in graph['nodes'] if n['kind'] == 'bag'}
            self.assertTrue(all(n['concept']=='unspecified' for n in graph['nodes'] if n['kind']=='bag'))
            self.assertFalse(any(e['predicate']=='owner' and e['arguments'][0] in bags for e in graph['relations']))
            categories = [e['value'] for e in graph['relations'] if e['predicate']=='category']
            self.assertEqual(len(categories),len(bags))
            self.assertTrue(set(categories) <= {'backpack','luggage box'})
            self.assertFalse(any(e['predicate']=='amount' for e in graph['relations']))

    def test_ticket_price_cabins_and_literal_direction_do_not_become_fee_totals(self):
        for prefix, price, origin, destination, cabin in (
            ('92d91f15',53,'Austin','Los Angeles','Main Cabin'),
            ('7b4b9947',43,'Los Angeles','Washington D.C.','Premium Economy'),
            ('30fe9798',1209,'Hong Kong','Austin','First'),
            ('51ecb012',133,'Mexico City','Sacramento','Business')):
            _, _, graph = self.example(prefix)
            nodes = {n['id']:n for n in graph['nodes']}
            self.assertEqual(nodes['origin']['name'],origin)
            self.assertEqual(nodes['destination']['name'],destination)
            self.assertEqual(nodes['cabin']['concept'],cabin)
            prices = [e for e in graph['relations'] if e['predicate']=='ticket_price']
            self.assertEqual(len(prices),1); self.assertEqual(prices[0]['value'],price)
            self.assertEqual(prices[0]['arguments'],['ticket'])
            self.assertEqual([e['value'] for e in graph['relations'] if e['predicate']=='route'],[None])

    def test_source_anchor_order_survives_graph_order_permutations_without_executing_F(self):
        _, units, graph = self.example('bc47b812')
        graph['nodes'].reverse(); graph['relations'].reverse()
        transported = self.projected(graph,units)
        captured=[]
        def no_execution(skill, values):
            captured.append(values)
            return {'handled':False,'answer':None,'reason':'Projection inspected without executing law'}
        with patch('legal_skill_guard.paired_interfaces.control_tools.execute_skill',side_effect=no_execution):
            result = airline(transported)
        self.assertFalse(result['handled'])
        self.assertEqual(len(captured),1)
        values = captured[0]
        self.assertEqual(values['item_weights'],[7,53,53,51,58])
        self.assertEqual(values['item_lengths'],[18,48,38,51,36])
        self.assertEqual(values['item_widths'],[11,33,16,29,18])
        self.assertEqual(values['item_heights'],[9,24,10,23,10])
        self.assertEqual(values['ticket_price'],262)

    def test_unsupported_routes_keep_literal_cities_and_never_reach_F(self):
        with patch('legal_skill_guard.paired_interfaces.control_tools.execute_skill',side_effect=AssertionError('F called')):
            for prefix, destination in (('cf4251b3','Amsterdam'),('68dc5c0d','Jerusalem'),('51ecb012','Sacramento')):
                _, units, graph = self.example(prefix)
                self.assertEqual(next(n['name'] for n in graph['nodes'] if n['id']=='destination'),destination)
                result = airline(self.projected(graph,units))
                self.assertFalse(result['handled'])
                self.assertIn('Route is outside',result['reason'])

    def test_cumulative_persistence_never_opens_labels_or_constructs_clients(self):
        original=Path.read_text
        def source_only(path,*args,**kwargs):
            if path.name=='grading.json': self.fail('Source review opened grading')
            return original(path,*args,**kwargs)
        with (patch.object(Path,'read_text',source_only),
              patch.object(FrozenExecutor,'__init__',side_effect=AssertionError('executor')),
              patch.object(FrozenTeacher,'__init__',side_effect=AssertionError('teacher')),
              patch.object(EvolutionLedger,'__init__',side_effect=AssertionError('ledger'))):
            out,manifest=reviews.prepare()
        self.assertEqual(len(manifest['reviews']),52)
        self.assertEqual(manifest['previous_extra_reviews_retained'],32)
        self.assertIsNone(manifest['interactive_root_annotation_cost_usd'])
        self.assertFalse(manifest['independent_human_or_complete_legal_gold_claimed'])
        for row in manifest['reviews']:
            card=read(ROOT/row['path'])
            self.assertTrue(card['reference_ready'])
            self.assertFalse(card['complete_native_case_gold_claimed'])
            self.assertFalse(card['native_answers_used_to_create_or_repair_graph'])
            self.assertNotEqual(card['role'],'structure_evaluation')


if __name__=='__main__':
    unittest.main()
