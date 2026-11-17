"""Complete fixed diagnostics routing with constructed actors/labels only."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from experiments.two_method_graph_corpus import BASE, read
from legal_skill_guard.paired_interfaces.formal_design import ARMS, source_roles
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.paired_interfaces.postfreeze_execution import PostfreezeExecution
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


class PostfreezeExecutionTests(unittest.TestCase):
    def test_full_fixed_probe_internal_fold_and_two_module_ablation_preserve_order_and_denominators(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); sources = read(BASE / 'prepared/source_lock.json')
            roles = source_roles(sources, read(BASE / 'pilot_lock.json'))
            datasets = {r['dataset'] for r in roles}
            public = {r['source']: {'key': r['source'], 'dataset': r['dataset'], 'views': [
                {'id': 'native', 'public': {'fixture': True}, 'answer_schema': {'type': 'boolean'}}]} for r in roles}
            tests = [{'key': source, 'dataset': source.split(':', 1)[0], 'views': [
                {'id': 'native', 'public': {'fixture': True}, 'answer_schema': {'type': 'boolean'}}]}
                for source in sources['sources']['test']]
            events = []
            class Actor:
                def views(self, source):
                    return [{'view': 'v0', 'pre_generation_domain_refusal': False,
                        'native_tasks': ['native'], 'native_public': {'native': {}},
                        'scope': {'schema': 'fixture', 'context': 'fixture'},
                        'plans': [{'name': p} for p in ('columns', 'records', 'local_records')]}]
                def channel_version(self, plan): return 'fixture'
                def measure(self, source, view, plan, purpose):
                    events.append(('probe_read', source['key'], plan['name']))
                    return {'physical_call_id': 'constructed:' + digest([source['key'], plan]),
                        'native': {'native': {'handled': True, 'answer': plan['name'] == 'records'}},
                        'usage': {'prompt_tokens': 1, 'completion_tokens': 1}}
                def __call__(self, source, library, purpose):
                    events.append(('cohort_read', source['key'], purpose))
                    return {'native': {'native': {'handled': True, 'answer': False}}}
                def verify_saved(self, source, library, purpose, result):
                    assert set(result['native']) == {'native'}
            interfaces_root = root / 'interface_training'
            immutable_json(interfaces_root / 'B8/shared_verified_raw_evidence.json', {'pairs': []})
            interfaces = type('InterfaceFixture', (), {'root': interfaces_root, 'actor': Actor()})()
            libraries = {}
            for arm in ARMS:
                value = {'arm': arm, 'batch': 8, 'fixture': True}
                if arm == 'M1_only':
                    value.update(M1_choices={d: {'plan': 'columns'} for d in datasets},
                                 raw_candidate_orders={d: ['columns', 'records', 'local_records'] for d in datasets})
                if arm == 'M1_M2': value['reference_world_groups'] = []
                libraries[arm, 8] = sealed(value, 'snapshot_sha256')
            training = sealed({'batch': 8, 'all_seven_libraries_frozen': True,
                'libraries': {arm: libraries[arm, 8]['snapshot_sha256'] for arm in ARMS}}, 'training_seal_sha256')
            freeze = sealed({'batch': 8, 'training_B8_seal': training}, 'freeze_sha256')
            manifest = {'endpoint_plan': {'refinement_only': 'local_records', 'compression_only': 'local_records'},
                        'same_endpoint_not_evidence_one_operator_is_better': True}
            def grade(partition, source, seal):
                events.append(('grade', seal['phase'], source))
                if seal['phase'] == 'transfer':
                    self.assertTrue((root / 'diagnostics/transfer/all_fixed_pool_predictions.json').exists())
                    self.assertEqual(sum(e[0] == 'probe_read' for e in events), 36)
                self.assertIn(source, seal['source_cohort'])
                return {'native': {'answer': True}}
            runner = PostfreezeExecution(root, roles=roles, source_lock=sources, public_train=public, public_test=tests,
                interface_trainer=interfaces, ablation_asset_manifest=manifest,
                ablation_asset_manifest_sha256=digest(manifest), actor_factory=lambda *a: Actor(),
                grade_provider=grade, source_binding_check=lambda: None)
            with patch('legal_skill_guard.paired_interfaces.postfreeze_protocol.select',
                       return_value={'plan': 'columns', 'supported': True}):
                plan = runner.prepare(libraries, training)
            self.assertFalse(any(e[0] == 'grade' for e in events))
            # These Boolean labels are artificial routing fixtures;the
            # original native legal graders are verified elsewhere.
            with patch('legal_skill_guard.paired_interfaces.postfreeze_execution.grade_view',
                       side_effect=lambda dataset, view, annotation, answer, evidence: {'grade': float(answer == annotation['answer'])}):
                terminal = runner.run(freeze)
            self.assertEqual(terminal['transfer_mothers'], 12)
            self.assertEqual(terminal['internal_structure_systems'], 7)
            self.assertEqual(terminal['M1_ablation_TEST_cells'], 6)
            self.assertFalse(terminal['two_independent_contributions_or_complete_goal_established'])
            report = read(root / 'diagnostics/transfer/report.json')
            self.assertTrue(all(r['mother_macro'] == 1 for r in report['system_native_metrics']['MOAR_style_measured_fixed_pool'].values()))
            self.assertTrue(all(r['mother_macro'] == 0 for r in report['system_native_metrics']['M1_M2'].values()))
            self.assertTrue(all(d['frozen_choices']['M1_M2']['plan'] == 'columns' for d in plan['transfer_decisions']))
            self.assertEqual(sum(e[0] == 'grade' and e[1] == 'M1_ablation' for e in events), 64 * 3)
            from legal_skill_guard.paired_delivery import EvidenceReader, load_diagnostics
            exported = load_diagnostics(EvidenceReader(root),
                {'train': list(public.values()), 'test': tests, 'dev': []}, plan['design'],
                {'training': training}, draws=100)
            measured = [r for r in exported['metrics'] if r['partition'] == 'transfer_TRAIN'
                        and r['arm'] == 'MOAR_style_measured_fixed_pool']
            self.assertEqual(len(measured), 3)
            self.assertTrue(all(r['mother_macro'] == 1 for r in measured))

    def test_diagnostics_cannot_run_without_original_pre_evaluation_seal(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = PostfreezeExecution(tmp, roles=[], source_lock={}, public_train={}, public_test=[],
                interface_trainer=None, ablation_asset_manifest={}, ablation_asset_manifest_sha256='fixture',
                actor_factory=lambda *a: self.fail('must not create actor'),
                grade_provider=lambda *a: self.fail('must not open grades'), source_binding_check=lambda: None)
            with self.assertRaisesRegex(ValueError, 'original pre-evaluation choice seal'):
                runner.run({})


if __name__ == '__main__':
    unittest.main()
