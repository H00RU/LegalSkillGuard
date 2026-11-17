"""Native loss/selection invariants; constructed fixtures are not trial evidence."""
from dataclasses import replace
import unittest

from legal_skill_guard.paired_interfaces.empirical_channel import learn_dictionary
from legal_skill_guard.paired_interfaces.native_channel_selection import (
    NativeLoss, choose_risks, mother_world_weights, native_replay, native_risk)
from legal_skill_guard.paired_interfaces.structural_channel import Fact, Graph, Pair, fit


class NativeSelectionTests(unittest.TestCase):
    def setUp(self):
        self.good = Graph((('a', 'person'),), frozenset({Fact('eligible', ('a',))}), 'fixture', 'c')
        self.bad = replace(self.good, facts=frozenset())
        self.dictionary = learn_dictionary([Pair('dev', self.good, self.bad, 'v', 'development', 'fixture')])

    def pairs(self, version, observed):
        return [Pair(str(i), self.good, observed, version, 'calibration', 'fixture') for i in range(64)]

    def test_undefined_reference_outputs_cannot_be_zero_loss_or_filtered(self):
        pairs = self.pairs('v', self.good)
        channel = fit(pairs, self.dictionary, version='v')
        loss = NativeLoss(lambda graph: {'handled': False, 'reason': 'unresolved input'})
        for result in (native_risk(channel, loss, {self.good: 1.}, version='v'),
                       native_replay(pairs, loss, {self.good: 1.})):
            self.assertFalse(result['supported'])
            self.assertNotIn('interval', result)
            self.assertEqual(result['reference_domain']['undefined_reference_mass'], 1.)
        partial = NativeLoss(lambda graph: {'handled': True, 'signature': 'true'} if graph == self.good
                             else {'handled': False, 'reason': 'missing source scope'})
        domain = partial.reference_domain({self.good: .5, self.bad: .5})
        self.assertFalse(domain['supported'])
        self.assertEqual(domain['reference_worlds'], 2)
        self.assertEqual(domain['undefined_reference_mass'], .5)
        self.assertFalse(domain['reference_worlds_filtered_or_renormalized'])

    def test_defined_null_is_distinct_from_edited_abstention(self):
        loss = NativeLoss(lambda graph: {'handled': True, 'signature': 'null'} if graph == self.good
                         else {'handled': False, 'reason': 'failed read'})
        result = native_replay(self.pairs('v', self.bad), loss, {self.good: 1.})
        self.assertTrue(result['supported'])
        self.assertEqual(result['empirical_risk'], 1.)
        self.assertEqual(native_replay(self.pairs('v', self.good), loss, {self.good: 1.})['empirical_risk'], 0.)

    def test_real_channel_api_and_full_replay_produce_risk_dependent_choice(self):
        loss = NativeLoss(lambda graph: {'handled': True,
            'signature': 'true' if Fact('eligible', ('a',)) in graph.facts else 'false'})
        risks, replay = {}, {}
        for name, observed in [('columns', self.bad), ('records', self.good)]:
            pairs = self.pairs(name, observed)
            channel = fit(pairs, self.dictionary, version=name, unknown_mode='detectable_residual')
            risks[name] = native_risk(channel, loss, {self.good: 1.}, version=name)
            replay[name] = native_replay(pairs, loss, {self.good: 1.})
            self.assertFalse(native_risk(channel, loss, {self.good: 1.}, version='changed')['supported'])
        for values, is_replay in ((risks, False), (replay, True)):
            chosen = choose_risks(values, baseline='columns', costs={'columns': 0., 'records': 0.}, replay=is_replay)
            self.assertEqual(chosen['plan'], 'records')
            self.assertTrue(chosen['risk_informed_ranking'])
            self.assertTrue(chosen['changed_baseline'])

    def test_cost_choice_and_unsupported_families_do_not_count_as_mechanism(self):
        tied = {name: {'supported': True, 'interval': [0., 1.]} for name in ('columns', 'records')}
        result = choose_risks(tied, baseline='columns', costs={'columns': .1, 'records': 0.})
        self.assertEqual(result['plan'], 'records')
        self.assertFalse(result['risk_informed_ranking'])
        tied['columns'] = {'supported': False, 'reason': 'outside native domain'}
        result = choose_risks(tied, baseline='columns', costs={'columns': .1, 'records': 0.})
        self.assertFalse(result['supported'])
        self.assertEqual(result['plan'], 'columns')

    def test_weights_cluster_mothers_and_duplicate_worlds_do_not_create_samples(self):
        pairs = [Pair('one', self.good, self.good, 'v', 'calibration', 'a'),
                 Pair('one', self.bad, self.bad, 'v', 'calibration', 'b'),
                 Pair('two', self.good, self.good, 'v', 'calibration', 'c')]
        weights = mother_world_weights(pairs)
        self.assertEqual(weights, {self.good: .75, self.bad: .25})
        self.assertEqual(mother_world_weights(pairs + pairs[:1]), weights)
        with self.assertRaisesRegex(ValueError, 'calibration'):
            mother_world_weights([replace(pairs[0], role='development')])


if __name__ == '__main__':
    unittest.main()
