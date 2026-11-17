"""Production failures remain loss1; analysis gaps cannot become observations."""
from dataclasses import replace
import unittest

from legal_skill_guard.paired_interfaces.graph_pairs import failure_graph
from legal_skill_guard.paired_interfaces.native_channel_selection import NativeLoss, native_replay
from legal_skill_guard.paired_interfaces.observed_abstention import (
    ObservedAbstention, abstention_graph, canonical_pair, edit_record, learn_dictionary, restore_edit)
from legal_skill_guard.paired_interfaces.structural_channel import Fact, Graph, Pair, fit


class ObservedAbstentionTests(unittest.TestCase):
    def setUp(self):
        self.world = Graph((('a', 'person'),), frozenset({Fact('eligible', ('a',))}), 's', 'c')

    def pair(self, source, graph=None, role='calibration', reason='invalid JSON'):
        world = graph or self.world
        return Pair(source, world, failure_graph(world, reason), 'v', role, 'constructed fixture')

    def test_error_text_does_not_define_an_outcome_and_no_source_fact_is_restored(self):
        a, receipt = canonical_pair(self.pair('a', reason='invalid JSON at char17'),
                                   {'graph': None, 'errors': ['invalid JSON at char17']})
        b, _ = canonical_pair(self.pair('b', reason='invalid JSON at char903'),
                              {'graph': None, 'errors': ['invalid JSON at char903']})
        self.assertEqual(a.observed, b.observed)
        self.assertEqual(a.observed.facts, frozenset({Fact('read_failure', (), 'unread')}))
        self.assertFalse(receipt['source_fields_or_native_answers_reconstructed'])
        edit = ObservedAbstention((), (), ())
        self.assertEqual(restore_edit(edit_record(edit)).images(self.world), edit.images(self.world))
        other = Graph((('b', 'person'),), frozenset({Fact('eligible', ('b',))}), 's', 'c')
        self.assertEqual(edit.images(other), frozenset({abstention_graph(other)}))

    def test_analysis_alignment_failure_is_unchanged_when_production_graph_exists(self):
        pair = self.pair('a', reason='alignment work exhausted')
        actual, receipt = canonical_pair(pair, {'graph': {'nodes': []}, 'errors': []})
        self.assertEqual(actual, pair)
        self.assertFalse(receipt['production_abstention'])
        self.assertNotEqual(actual.observed, abstention_graph(pair.reference))
        with self.assertRaises(ValueError):
            canonical_pair(pair, {'graph': None, 'errors': []})

    def test_production_abstention_is_known_but_never_becomes_zero_native_loss(self):
        development, _ = canonical_pair(self.pair('dev', role='development'), {'graph': None, 'errors': ['cutoff']})
        dictionary = learn_dictionary([development])
        pairs = [canonical_pair(self.pair(str(i)), {'graph': None, 'errors': ['cutoff']})[0] for i in range(32)]
        channel = fit(pairs, dictionary, version='v', unknown_mode='detectable_residual')
        self.assertEqual(channel.diagnostics['unmatched_pairs'], 0)
        self.assertEqual(channel.diagnostics['confidence_unit_count'], 32)
        # Every known and unknown error is still allowed its full loss; this
        # outcome is not a semantic-correctness or graph-completion claim.
        self.assertTrue(dictionary['unmodeled_semantic_error_component_retained'])
        loss = NativeLoss(lambda graph: {'handled': True, 'signature': 'true'} if graph == self.world
                         else {'handled': False, 'reason': 'production rejected read'})
        self.assertEqual(native_replay(pairs, loss, {self.world: 1.})['empirical_risk'], 1.)

    def test_schema_context_version_and_role_are_not_erased_by_canonicalization(self):
        pair, _ = canonical_pair(self.pair('cal'), {'graph': None, 'errors': ['cutoff']})
        self.assertEqual(pair.plan_version, 'v')
        self.assertEqual((pair.observed.schema, pair.observed.context), ('s', 'c'))
        with self.assertRaisesRegex(ValueError, 'development'):
            learn_dictionary([pair])
        bad = replace(pair, plan_version='other')
        dictionary = learn_dictionary([replace(pair, source_id='dev', role='development')])
        with self.assertRaisesRegex(ValueError, 'version'):
            fit([bad], dictionary, version='v')
        item = edit_record(ObservedAbstention((), (), ()))
        item['operator'] = 'invented'
        with self.assertRaisesRegex(ValueError, 'Unknown'):
            restore_edit(item)


if __name__ == '__main__':
    unittest.main()
