from copy import deepcopy
import unittest

from legal_skill_guard.paired_interfaces.graph_evidence import normalize_graph_evidence
from legal_skill_guard.paired_interfaces.graph_pairs import pair_from_audited_reference


class GraphEvidenceDecoding(unittest.TestCase):
    def setUp(self):
        text = 'Alice paid her father Bob $3200.'
        self.units = [{'id': 0, 'start': 0, 'end': len(text), 'text': text}]
        self.graph = {'nodes': [
            {'id': 'a', 'kind': 'person', 'concept': 'unspecified', 'name': 'Alice', 'unit_id': 0, 'quote': 'Alice'},
            {'id': 'b', 'kind': 'person', 'concept': 'unspecified', 'name': 'her father Bob', 'unit_id': 0, 'quote': 'her father Bob'},
            {'id': 'p', 'kind': 'event', 'concept': 'payment', 'name': 'payment_event', 'unit_id': 8, 'quote': 'paid her father Bob $3200'}],
            'relations': [{'predicate': 'payer', 'arguments': ['p', 'a'], 'value': None,
                           'status': 'stated', 'unit_id': 0, 'quote': text}],
            'scope_complete': False, 'unresolved': ['payment date unknown']}

    def test_only_unique_pointers_and_nonliteral_display_glosses_change(self):
        graph, receipt = normalize_graph_evidence(self.graph, self.units)
        self.assertEqual(graph['nodes'][2]['unit_id'], 0)
        self.assertEqual(graph['nodes'][2]['name'], graph['nodes'][2]['quote'])
        self.assertEqual(graph['relations'], self.graph['relations'])
        self.assertEqual(graph['unresolved'], self.graph['unresolved'])
        self.assertEqual(receipt['semantic_payload_sha256_before'], receipt['semantic_payload_sha256_after'])
        self.assertFalse(receipt['source_semantic_truth_verified'])

    def test_conflicting_literal_identity_is_not_changed_to_the_quoted_person(self):
        for name in ('Alice', 'Employee Alice'):
            graph = deepcopy(self.graph)
            graph['nodes'][1].update(name=name, quote='Bob')
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'conflicts'):
                normalize_graph_evidence(graph, self.units)

    def test_ambiguous_pointer_duplicates_and_unknown_guessed_values_remain_errors(self):
        graph = deepcopy(self.graph)
        units = self.units + [{'id': 1, **{k: v for k, v in self.units[0].items() if k != 'id'}}]
        with self.assertRaisesRegex(ValueError, 'unique verbatim'):
            normalize_graph_evidence(graph, units)
        graph['nodes'][1]['id'] = 'a'
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            normalize_graph_evidence(graph, self.units)
        graph = deepcopy(self.graph)
        graph['relations'][0].update(status='unknown', value=3200)
        with self.assertRaisesRegex(ValueError, 'guessed factual'):
            normalize_graph_evidence(graph, self.units)

    def test_literal_submention_alignment_keeps_a_real_role_swap_visible(self):
        reference, _ = normalize_graph_evidence(self.graph, self.units)
        observed = deepcopy(reference)
        observed['nodes'][1].update(name='Bob', quote='Bob')
        observed['relations'][0]['arguments'][1] = 'b'
        pair, receipt = pair_from_audited_reference(reference, observed, self.units,
            source='fixture', role='development', version='fixed', provenance='constructed invariant',
            context='payment', semantic_reference_verified=True)
        self.assertEqual(receipt['alignment_count'], 1)
        self.assertNotEqual(next(iter(pair.observed)).facts, pair.reference.facts)


if __name__ == '__main__':
    unittest.main()
