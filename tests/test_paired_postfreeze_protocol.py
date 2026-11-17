"""Frozen diagnostic ordering and measured TRAIN-search isolation fixtures."""
from copy import deepcopy
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from experiments.two_method_graph_corpus import BASE, read
from legal_skill_guard.paired_interfaces.formal_design import ARMS, source_roles
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.paired_interfaces.formal_learning import pair_record
from legal_skill_guard.paired_interfaces.postfreeze_protocol import diagnostic_design, measured_MOAR_choices, seal
from legal_skill_guard.paired_interfaces.structural_channel import Fact, Graph, Pair
from legal_skill_guard.skill_evolution.objects import digest


class PostfreezeProtocolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source_lock = read(BASE / 'prepared/source_lock.json')
        self.roles = source_roles(self.source_lock, read(BASE / 'pilot_lock.json'))

    def inputs(self):
        datasets = sorted({r['dataset'] for r in self.roles})
        libraries = {}
        for arm in ARMS:
            value = {'arm': arm, 'batch': 8, 'fixture': True}
            if arm == 'M1_only':
                value.update(M1_choices={d: {'plan': 'columns'} for d in datasets},
                             raw_candidate_orders={d: ['columns', 'records', 'local_records'] for d in datasets})
            if arm == 'M1_M2': value['reference_world_groups'] = []
            libraries[arm] = sealed(value, 'snapshot_sha256')
        training = sealed({'batch': 8, 'libraries': {a: v['snapshot_sha256'] for a, v in libraries.items()},
                           'all_seven_libraries_frozen': True}, 'training_seal_sha256')
        public = {r['source']: {'key': r['source'], 'dataset': r['dataset'], 'views': []} for r in self.roles}
        class Actor:
            def views(self, source):
                return [{'view': 'v0', 'pre_generation_domain_refusal': False,
                    'scope': {'schema': 'fixture_schema', 'context': 'fixture_context'},
                    'native_tasks': ['native'], 'native_public': {'native': {}},
                    'plans': [{'name': p} for p in ('columns', 'records', 'local_records')]}]
            def channel_version(self, plan): return 'fixture_fixed_profile'
        graph = Graph((('x', 'event'),), frozenset({Fact('field:A', ('x',))}), 'fixture_schema', 'fixture_context')
        records = []
        for role in ('development', 'calibration'):
            row = next(r for r in self.roles if r['role'] == role and r['dataset'] == 'SARA_v2_Binary')
            for plan in ('columns', 'records', 'local_records'):
                p = Pair(row['source'], graph, graph, 'fixture_fixed_profile', role, 'constructed:' + plan + role)
                records.append({'source': row['source'], 'dataset': row['dataset'], 'plan': plan, 'pair': pair_record(p)})
        manifest = {'endpoint_plan': {'refinement_only': 'local_records', 'compression_only': 'local_records'},
                    'same_endpoint_not_evidence_one_operator_is_better': True}
        return {'roles': self.roles, 'source_lock': self.source_lock, 'libraries': libraries,
            'training_seal': training, 'public_train': public, 'interface_actor': Actor(),
            'paired_records': records, 'ablation_asset_manifest': manifest,
            'ablation_asset_manifest_sha256': digest(manifest)}

    def test_original_fixed_cohorts_and_ablation_TEST_subset_are_not_expanded(self):
        result = diagnostic_design(self.roles, self.source_lock)
        self.assertEqual(len(result['transfer_TRAIN_sources']), 12)
        self.assertEqual(len(result['internal_structural_TRAIN_sources']), 8)
        self.assertEqual(len(result['M1_ablation_fixed_TEST_sources']), 64)
        self.assertEqual(result['M1_ablation_TEST_cells'], 6)

    def test_choices_seal_without_target_labels_and_original_libraries_stay_unchanged(self):
        args = self.inputs(); before = deepcopy(args['libraries'])
        with patch('legal_skill_guard.paired_interfaces.postfreeze_protocol.select',
                   return_value={'plan': 'columns', 'supported': True}):
            result = seal(self.root, **args)
        self.assertEqual(args['libraries'], before)
        self.assertEqual(len(result['transfer_decisions']), 12)
        for variant in ('refinement_only', 'compression_only'):
            self.assertEqual(result['ablation_libraries'][variant]['M1_choices']['OpenExempt']['plan'], 'local_records')
        for row in result['transfer_decisions']:
            self.assertFalse(row['actual_target_weak_read_or_native_grade_used'])
        (self.root / 'label_access/dev').mkdir(parents=True)
        self.assertEqual(result, seal(self.root, **args))
        (self.root / 'postfreeze_choice_seal.json').unlink()  # Only this test's own temporary artifact.
        with self.assertRaisesRegex(ValueError, 'after target labels opened'):
            seal(self.root, **args)

    def test_reference_only_actual_read_cannot_enter_fitting_the_noise_model(self):
        args = self.inputs()
        source = next(r['source'] for r in self.roles if r['role'] == 'reference_only')
        args['paired_records'][0]['source'] = source
        with self.assertRaisesRegex(ValueError, 'reference-only'):
            seal(self.root, **args)

    def test_measured_MOAR_uses_all_actual_TRAIN_candidates_only_after_complete_prediction_seal(self):
        decisions = [{'source': 'constructed_TRAIN', 'view': 'v0', 'fixed_candidate_order': ['columns', 'records', 'local_records'],
                      'native_tasks': ['one', 'two'], 'frozen_choices': {'M1_M2': {'plan': 'columns'}}}]
        scores = [{'source': 'constructed_TRAIN', 'opaque_view': 'v0', 'plan': plan, 'view': task,
                   'handled': plan != 'columns', 'grade': float(plan == 'records')}
                  for plan in decisions[0]['fixed_candidate_order'] for task in ('one', 'two')]
        keys = sorted((r['source'], r['opaque_view'], r['plan'], r['view']) for r in scores)
        prediction_seal = sealed({'native_candidate_slots': 6, 'native_slot_keys_sha256': digest(keys),
            'diagnostic_decisions_sha256': digest(decisions)}, 'probe_prediction_seal_sha256')
        before = deepcopy(decisions)
        result = measured_MOAR_choices(scores, decisions, prediction_seal)
        self.assertEqual(result[0]['plan'], 'records')
        self.assertEqual(decisions, before)
        self.assertTrue(result[0]['actual_current_TRAIN_native_feedback_used'])
        with self.assertRaisesRegex(ValueError, 'Every fixed candidate'):
            measured_MOAR_choices(scores[:-1], decisions, prediction_seal)


if __name__ == '__main__':
    unittest.main()
