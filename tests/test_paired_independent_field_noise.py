"""Independent noise vs joint traces on explicit constructed correlation data."""
from copy import deepcopy
import unittest

from legal_skill_guard.paired_interfaces.independent_field_noise import fit, risk
from legal_skill_guard.paired_interfaces.native_channel_selection import NativeLoss
from legal_skill_guard.paired_interfaces.observed_abstention import abstention_graph
from legal_skill_guard.paired_interfaces.partial_native_loss import replay_bounds
from legal_skill_guard.paired_interfaces.structural_channel import Fact, Graph, Pair


class IndependentFieldNoiseTests(unittest.TestCase):
    def graph(self, left='A', right='A'):
        return Graph((('x', 'event'),), frozenset({Fact('left:' + left, ('x',)), Fact('right:' + right, ('x',))}),
                     'constructed_schema', 'constructed_context')

    def pairs(self):
        graph = self.graph()
        return [Pair('one', graph, graph, 'fixed_v1', 'development', 'fixture_one'),
                Pair('two', graph, self.graph('B', 'B'), 'fixed_v1', 'calibration', 'fixture_two')]

    def consume(self, graph):
        equal = any(Fact('left:' + value, ('x',)) in graph.facts and Fact('right:' + value, ('x',)) in graph.facts
                    for value in ('A', 'B'))
        return {'handled': True, 'signature': 'equal' if equal else 'different'}

    def test_independence_breaks_real_joint_correlation_in_the_constructed_fixture(self):
        pairs = self.pairs(); weights = {pairs[0].reference: 1.}
        independent = risk(fit(pairs), self.consume, weights, version='fixed_v1')
        joint = replay_bounds(pairs, NativeLoss(self.consume), weights)
        self.assertEqual(independent['interval'], [.5, .5])
        self.assertEqual(joint['empirical_risk_interval'], [0., 0.])
        self.assertFalse(independent['statistical_coverage_guarantee_claimed'])

    def test_production_abstention_mass_is_not_dropped_by_valid_read_conditioning(self):
        pairs = self.pairs(); p = pairs[1]
        pairs[1] = Pair(p.source_id, p.reference, abstention_graph(p.reference), p.plan_version, p.role, p.provenance)
        model = fit(pairs)
        result = risk(model, self.consume, {p.reference: 1.}, version='fixed_v1')
        self.assertEqual(result['production_abstention_probability'], .5)
        self.assertEqual(result['interval'], [.5, .5])
        self.assertEqual(result['source_mothers'], 2)

    def test_alignment_alternatives_have_bounds_and_no_uniform_guessed_probability(self):
        p = self.pairs()[0]
        ambiguous = Pair(p.source_id, p.reference, frozenset({p.reference, self.graph('B', 'B')}),
                         p.plan_version, p.role, p.provenance)
        result = risk(fit([ambiguous]), self.consume, {p.reference: 1.}, version='fixed_v1')
        self.assertEqual(result['interval'], [0., 1.])

    def test_new_field_keeps_its_mass_and_new_support_requires_explicit_assumption(self):
        model = fit(self.pairs()); base = self.graph()
        other = Graph(base.nodes, base.facts | {Fact('never_observed_field', ('x',))}, base.schema, base.context)
        self.assertFalse(risk(model, self.consume, {other: 1.}, version='fixed_v1')['supported'])
        result = risk(model, self.consume, {other: 1.}, version='fixed_v1', allow_stationary_transfer=True)
        self.assertEqual(result['interval'], [0., 1.]); self.assertEqual(result['unmodeled_target_field_mass'], 1.)

    def test_changed_versions_duplicate_pairs_and_partial_product_work_are_rejected(self):
        pairs = self.pairs()
        with self.assertRaisesRegex(ValueError, 'cannot count twice'):
            fit(pairs + [pairs[0]])
        model = fit(pairs)
        self.assertFalse(risk(model, self.consume, {self.graph(): 1.}, version='changed')['supported'])
        result = risk(model, self.consume, {self.graph(): 1.}, version='fixed_v1', max_terms=1)
        self.assertFalse(result['supported']); self.assertNotIn('interval', result)

    def test_undefined_reference_against_defined_prediction_is_not_zero_loss(self):
        base = self.graph(); other = self.graph('B', 'B')
        p = Pair('one', base, other, 'fixed_v1', 'development', 'fixture')
        consume = lambda g: {'handled': False} if g == base else {'handled': True, 'signature': 'defined'}
        result = risk(fit([p]), consume, {base: 1.}, version='fixed_v1')
        self.assertEqual(result['interval'], [0., 1.])


if __name__ == '__main__':
    unittest.main()
