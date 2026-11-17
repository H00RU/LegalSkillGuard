"""Prefix isolation,complete failure denominators and true support extrapolation.

Synthetic operator fixtures exercise contracts;not a research efficacy result.
"""
from copy import deepcopy
import unittest

from legal_skill_guard.paired_interfaces.empirical_channel import graph_record
from legal_skill_guard.paired_interfaces.formal_learning import arm_snapshot, fit_prefix, pair_record, select
from legal_skill_guard.paired_interfaces.structural_channel import Fact, Graph, Pair
from legal_skill_guard.skill_evolution.objects import digest


class FormalLearningTests(unittest.TestCase):
    def inputs(self):
        graph = Graph((('x', 'event'),), frozenset({Fact('value_A', ('x',))}), 'fixture_schema', 'fixture_context')
        unseen = Graph(graph.nodes, graph.facts | {Fact('new_relationship', ('x',))}, graph.schema, graph.context)
        roles = [{'source': source, 'role': role, 'dataset': 'fixture', 'batch': 1}
                 for source, role in [('dev', 'development'), ('cal', 'calibration'),
                                      ('ref', 'reference_only'), ('eval', 'structure_evaluation')]]
        paired, scores = [], []
        for plan in ('columns', 'records'):
            for source, role in [('dev', 'development'), ('cal', 'calibration')]:
                pair = Pair(source, graph, graph, digest(['fixed_profile', plan]), role, 'fixture_provenance')
                paired.append({'source': source, 'dataset': 'fixture', 'view': 'v0', 'plan': plan, 'pair': pair_record(pair)})
                scores.append({'source': source, 'dataset': 'fixture', 'view': 'native', 'plan': plan,
                               'grade': 1., 'handled': True})
        references = [{'source': 'ref', 'view': 'v0', 'dataset': 'fixture', 'graph': graph_record(unseen)}]
        kwargs = {'candidate_orders': {'fixture': ['columns', 'records']},
                  'source_opaque_views': {row['source']: ['v0'] for row in roles}}
        return roles, paired, references, scores, {'dev': ['native'], 'cal': ['native']}, kwargs

    def snapshot(self, data=None):
        roles, pairs, refs, scores, native, kwargs = self.inputs() if data is None else data
        return fit_prefix(roles, 1, pairs, refs, scores, native, **kwargs)

    def test_missing_failed_pairs_and_reference_worlds_cannot_be_filtered(self):
        data = list(self.inputs()); data[1] = data[1][:-1]
        with self.assertRaisesRegex(ValueError, 'including decoder failures'):
            self.snapshot(data)
        data = list(self.inputs()); data[2] = []
        with self.assertRaisesRegex(ValueError, 'including native-undefined'):
            self.snapshot(data)

    def test_reference_only_native_feedback_cannot_select_primary_M1(self):
        data = list(self.inputs()); data[3] = data[3] + [
            {'source': 'ref', 'dataset': 'fixture', 'view': 'native', 'plan': 'records', 'grade': 0., 'handled': False}]
        with self.assertRaisesRegex(ValueError, 'reference-only'):
            self.snapshot(data)

    def test_mixed_versions_cannot_be_pooled_under_one_candidate(self):
        data = list(self.inputs()); data[1] = deepcopy(data[1])
        data[1][1]['pair']['plan_version'] = digest('another_profile')
        with self.assertRaisesRegex(ValueError, 'mixed'):
            self.snapshot(data)

    def test_M2_uses_unobserved_train_worlds_and_replay_receives_all_joint_pairs(self):
        snapshot = self.snapshot()
        def consume(graph):
            return {'handled': True, 'signature': 'A' if Fact('value_A', ('x',)) in graph.facts else 'B'}
        decision = select(arm_snapshot(snapshot, 'M1_M2'), dataset='fixture', schema='fixture_schema', context='fixture_context',
                          arm='M1_M2', consume=consume)
        risks = decision['risks']
        for report in risks.values():
            self.assertTrue(report['conditional_model_prediction'])
            self.assertEqual(report['calibration_sources'], 1)
            self.assertEqual(report['unrestricted_latent_risk_interval'], [0., 1.])
        replay_decision = select(arm_snapshot(snapshot, 'M1_full_trace_replay'), dataset='fixture',
                                 schema='fixture_schema', context='fixture_context',
                                 arm='M1_full_trace_replay', consume=consume)
        replay = replay_decision['risks']
        self.assertTrue(all(report['paired_mothers'] == 2 for report in replay.values()))
        self.assertFalse(decision['target_reference_graph_label_or_actual_weak_output_used'])
        self.assertEqual(snapshot['M1_choices']['fixture']['plan'], 'columns')

    def test_changed_learned_snapshot_is_rejected_before_selection(self):
        snapshot = self.snapshot(); snapshot['M1_choices']['fixture']['plan'] = 'records'
        with self.assertRaisesRegex(ValueError, 'changed'):
            select(snapshot, dataset='fixture', schema='fixture_schema', context='fixture_context',
                   arm='M1_only', consume=lambda graph: None)

    def test_native_grade_changes_cannot_change_M2_or_full_replay_learned_artifacts(self):
        first = self.snapshot()
        data = list(self.inputs()); data[3] = deepcopy(data[3])
        for row in data[3]:
            if row['plan'] == 'records':
                row['grade'] = 0.
        changed = self.snapshot(data)
        self.assertNotEqual(arm_snapshot(first, 'M1_only'), arm_snapshot(changed, 'M1_only'))
        for arm in ('M2_fixed_interfaces', 'M1_M2', 'M1_full_trace_replay'):
            self.assertEqual(arm_snapshot(first, arm), arm_snapshot(changed, arm))

    def test_replay_artifact_contains_no_channels_and_never_executes_M2(self):
        snapshot = arm_snapshot(self.snapshot(), 'M1_full_trace_replay')
        self.assertTrue(all('channels' not in row for row in snapshot['fitted_groups']))
        decision = select(snapshot, dataset='fixture', schema='fixture_schema', context='fixture_context',
                          arm='M1_full_trace_replay', consume=lambda graph: {'handled': True, 'signature': 'constant'})
        self.assertFalse(decision['channel_model_executed'])
        with self.assertRaisesRegex(ValueError, 'borrowed'):
            select(snapshot, dataset='fixture', schema='fixture_schema', context='fixture_context',
                   arm='M1_M2', consume=lambda graph: None)


if __name__ == '__main__':
    unittest.main()
