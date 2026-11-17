from copy import deepcopy
import unittest

from legal_skill_guard.paired_interfaces.graph_pairs import (
    complete_loss_consumer, consumer_signature, pair_from_audited_reference, reference_graph)
from legal_skill_guard.paired_interfaces.structural_channel import observations


def node(identity, kind, concept, name, quote=None):
    return {'id': identity, 'kind': kind, 'concept': concept, 'name': name,
            'quote': quote or name, 'unit_id': 0}


def edge(predicate, arguments, quote='Alice performs service for Bob.'):
    return {'predicate': predicate, 'arguments': arguments, 'value': None,
            'status': 'stated', 'quote': quote, 'unit_id': 0}


class SourceGraphPairs(unittest.TestCase):
    def setUp(self):
        self.text = 'Alice performs service for Bob.'
        self.units = [{'id': 0, 'start': 0, 'end': len(self.text), 'text': self.text}]
        self.reference = {'nodes': [node('a', 'person', 'unspecified', 'Alice', self.text),
            node('b', 'person', 'unspecified', 'Bob', self.text),
            node('s', 'event', 'service', 'service')],
            'relations': [edge('worker', ['s', 'a']), edge('recipient', ['s', 'b'])],
            'scope_complete': True, 'unresolved': []}

    def pair(self, observed, **kwargs):
        return pair_from_audited_reference(self.reference, observed, self.units,
            source='constructed_source', role='development', version='fixed_read',
            provenance='synthetic invariant check, not experimental evidence', context='service',
            semantic_reference_verified=True, **kwargs)

    def test_source_entity_names_prevent_expected_role_alignment_from_repairing_a_swap(self):
        observed = deepcopy(self.reference)
        observed['relations'][0]['arguments'][1] = 'b'
        observed['relations'][1]['arguments'][1] = 'a'
        pair, receipt = self.pair(observed)
        self.assertEqual(receipt['alignment_count'], 1)
        self.assertEqual(receipt['compatible_source_identity_choices']['a'], ['a'])
        self.assertEqual(receipt['compatible_source_identity_choices']['b'], ['b'])
        self.assertNotEqual(next(iter(observations(pair))).facts, pair.reference.facts)

    def test_same_event_anchor_ambiguity_is_retained_without_a_probability(self):
        self.reference['nodes'].append(node('s2', 'event', 'service', 'service'))
        pair, receipt = self.pair(deepcopy({**self.reference, 'nodes': self.reference['nodes'][:-1]}))
        self.assertEqual(receipt['alignment_count'], 2)
        self.assertEqual(len(observations(pair)), 2)

    def test_alignment_limit_is_unknown_instead_of_the_first_successful_mapping(self):
        self.reference['nodes'].append(node('s2', 'event', 'service', 'service'))
        pair, receipt = self.pair({**self.reference, 'nodes': self.reference['nodes'][:-1]}, max_alignments=1)
        self.assertIn('unknown_observation', receipt)
        self.assertNotEqual(next(iter(observations(pair))).nodes, pair.reference.nodes)

    def test_teacher_output_or_span_checks_cannot_substitute_for_reference_audit(self):
        with self.assertRaisesRegex(ValueError, 'reference truth'):
            pair_from_audited_reference(self.reference, self.reference, self.units,
                source='s', role='calibration', version='v', provenance='teacher',
                context='service', semantic_reference_verified=False)

    def test_pure_consumer_roundtrip_and_undefined_reference_gate(self):
        graph = {'nodes': [node('e', 'effect', 'permission', 'may'),
            node('p', 'group', 'receiving_party', 'party'), node('r', 'group', 'own_employees', 'employees'),
            node('a', 'event', 'disclosure', 'disclose'), node('i', 'information', 'confidential_information', 'information')],
            'relations': [edge('actor', ['e', 'p']), edge('recipient', ['e', 'r']),
                edge('action', ['e', 'a']), edge('information', ['e', 'i'])],
            'scope_complete': True, 'unresolved': []}
        units = {0: {'id': 0, 'text': 'party may disclose information to employees'}}
        (world, metadata, receipt), identities = reference_graph(graph, units, 'contract')
        self.assertEqual(consumer_signature(world, 'ContractNLI', ['nda-5'])['signature'], ('Entailment',))
        consumer = complete_loss_consumer('ContractNLI', ['nda-5'], [world])
        self.assertEqual(consumer(world), ('defined', 'Entailment'))
        graph['scope_complete'] = False
        (bad, metadata, receipt), identities = reference_graph(graph, units, 'contract')
        self.assertEqual(consumer(bad), ('unresolved',))
        with self.assertRaisesRegex(ValueError, 'consumer domain'):
            complete_loss_consumer('ContractNLI', ['nda-5'], [bad])


if __name__ == '__main__':
    unittest.main()
