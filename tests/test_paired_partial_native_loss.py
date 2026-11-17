"""Conservative bounds retain unknown reference mass and penalize abstention."""
from dataclasses import replace
import unittest

from legal_skill_guard.paired_interfaces.empirical_channel import learn_dictionary
from legal_skill_guard.paired_interfaces.graph_pairs import failure_graph
from legal_skill_guard.paired_interfaces.native_channel_selection import NativeLoss, native_risk
from legal_skill_guard.paired_interfaces.observed_abstention import abstention_graph
from legal_skill_guard.paired_interfaces.partial_native_loss import loss_interval, replay_bounds, risk_bounds
from legal_skill_guard.paired_interfaces.structural_channel import Fact, Graph, Pair, fit


class PartialNativeLossTests(unittest.TestCase):
    def setUp(self):
        self.good = Graph((('a', 'person'),), frozenset({Fact('eligible', ('a',))}), 'fixture', 'c')
        self.other = replace(self.good, facts=frozenset())
        self.unknown = replace(self.good, facts=frozenset({Fact('unread', (), 'unread')}))
        self.loss = NativeLoss(lambda graph: {'handled': False, 'reason': 'unread source scope'}
            if graph == self.unknown else {'handled': True,
                'signature': 'null' if graph == self.good else 'false'})

    def test_all_reference_prediction_definedness_combinations_keep_distinct_losses(self):
        self.assertEqual(loss_interval(self.loss, self.unknown, self.unknown), [1., 1.])
        self.assertEqual(loss_interval(self.loss, self.unknown, self.good), [0., 1.])
        self.assertEqual(loss_interval(self.loss, self.good, self.unknown), [1., 1.])
        self.assertEqual(loss_interval(self.loss, self.good, self.good), [0., 0.])
        self.assertEqual(loss_interval(self.loss, self.good, self.other), [1., 1.])

    def test_full_replay_retains_unknown_mother_mass_and_all_alignment_outcomes(self):
        pairs = [Pair('known', self.good, self.good, 'v', 'calibration', 'fixture'),
                 Pair('missing', self.unknown, frozenset({self.unknown, self.good}),
                      'v', 'calibration', 'fixture')]
        result = replay_bounds(pairs, self.loss, {self.good: .5, self.unknown: .5})
        self.assertTrue(result['supported'])
        self.assertEqual(result['empirical_risk_interval'], [0., .5])
        self.assertEqual(result['reference_domain']['undefined_reference_mass'], .5)
        self.assertTrue(result['all_reference_weights_retained'])
        unknown_only = replay_bounds([pairs[1]], self.loss, {self.unknown: 1.})
        self.assertEqual(unknown_only['empirical_risk_interval'], [0., 1.])

    def test_an_unavailable_alignment_does_not_imply_the_actual_reader_abstained(self):
        placeholder = failure_graph(self.good, 'analysis alignment work exhausted')
        self.assertEqual(loss_interval(self.loss, self.good, placeholder), [0., 1.])
        pair = Pair('missing-alignment', self.good, placeholder, 'v', 'calibration', 'fixture')
        report = replay_bounds([pair], self.loss, {self.good: 1.})
        self.assertEqual(report['empirical_risk_interval'], [0., 1.])

    def test_absorbing_decoder_failure_cannot_be_revived_by_a_law_only_consumer(self):
        law_only = NativeLoss(lambda graph: {'handled': True, 'signature': 'constant'})
        failed = abstention_graph(self.good)
        self.assertFalse(law_only.result(failed)['handled'])
        self.assertEqual(loss_interval(law_only, self.good, failed), [1., 1.])

    def test_partial_native_risk_is_bounded_without_turning_unknown_identity_into_success(self):
        development = Pair('dev', self.unknown, self.unknown, 'v', 'development', 'fixture')
        dictionary = learn_dictionary([development])
        pairs = [Pair(str(i), self.unknown, self.unknown, 'v', 'calibration', 'fixture') for i in range(64)]
        channel = fit(pairs, dictionary, version='v', unknown_mode='detectable_residual')
        strict = native_risk(channel, self.loss, {self.unknown: 1.}, version='v')
        self.assertFalse(strict['supported'])
        bounded = risk_bounds(channel, self.loss, {self.unknown: 1.}, version='v')
        self.assertTrue(bounded['supported'])
        self.assertEqual(bounded['loss_lower_by_edit'], [1.])
        self.assertEqual(bounded['loss_upper_by_edit'], [1.])
        self.assertGreater(bounded['interval'][0], 0.)
        self.assertEqual(bounded['interval'][1], 1.)
        self.assertEqual(bounded['unmodeled_error_loss_interval'], [0., 1.])
        self.assertFalse(risk_bounds(channel, self.loss, {self.unknown: 1.}, version='changed')['supported'])

    def test_defined_domain_matches_strict_native_risk_and_replay_exactly(self):
        dictionary = learn_dictionary([Pair('dev', self.good, self.other, 'v', 'development', 'fixture')])
        pairs = [Pair(str(i), self.good, self.other if i % 4 == 0 else self.good,
                      'v', 'calibration', 'fixture') for i in range(64)]
        channel = fit(pairs, dictionary, version='v', unknown_mode='detectable_residual')
        actual = risk_bounds(channel, self.loss, {self.good: 1.}, version='v')
        expected = native_risk(channel, self.loss, {self.good: 1.}, version='v')
        self.assertEqual(actual['interval'], expected['interval'])
        self.assertEqual(replay_bounds(pairs, self.loss, {self.good: 1.})['empirical_risk'], .25)
        self.assertFalse(replay_bounds(pairs, self.loss, {self.other: 1.})['supported'])


if __name__ == '__main__':
    unittest.main()
