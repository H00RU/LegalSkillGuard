"""Prefix training/source-review isolation;all examples are constructed fixtures."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from legal_skill_guard.paired_interfaces.asset_graph_pairs import scope
from legal_skill_guard.paired_interfaces.asset_port_decoder_v2 import decode
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.paired_interfaces.formal_training import InterfaceBatchTrainer, MissingSourceReviews, ReferenceRegistry
from legal_skill_guard.skill_evolution.objects import digest
from tests import test_paired_asset_graph_pairs as fixtures


class FormalTrainingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        card, raw, plan, units = fixtures.AssetGraphPairTests().fixture()
        self.roles = [{'source': 'OpenExempt:fixture_' + name, 'dataset': 'OpenExempt', 'role': name,
                       'batch': 1 if name in ('development', 'calibration') else 2}
                      for name in ('development', 'calibration', 'reference_only', 'structure_evaluation')]
        self.public = {r['source']: {'key': r['source'], 'dataset': 'OpenExempt', 'views': [
            {'id': family, 'public': {'fixture': True}, 'answer_schema': {'type': 'object'}} for family in ('EC', 'EV')]}
                       for r in self.roles}
        self.reviews, self.grade_reads, self.model_reads = [], [], []
        for row in self.roles:
            if row['role'] == 'structure_evaluation':
                continue
            reviewed = {**deepcopy(card), 'source': row['source'], 'view_id': 'v0', 'role': row['role']}
            if row['role'] == 'reference_only':
                reviewed['port_record']['assets'][0]['fields']['asset_is_personal_nonbusiness_property'] = {
                    'value': None, 'status': 'unknown'}
            path = self.root / (row['role'] + '.json'); path.write_text(json.dumps(reviewed))
            self.reviews.append({'source': row['source'], 'view': 'v0', 'kind': 'asset_program_ports',
                                 'path': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        (self.root / 'fixture_pipeline.py').write_text('# constructed test pipeline\n')
        pipeline = {'fixture_pipeline.py': hashlib.sha256((self.root / 'fixture_pipeline.py').read_bytes()).hexdigest()}
        tests = self
        class FixtureActor:
            pipeline_binding = pipeline
            executor = SimpleNamespace(config={'fixture': True, 'enable_thinking': False})
            def views(self, source):
                refused = source.get('domain_refused', False)
                return [{'source': source['key'], 'dataset': 'OpenExempt', 'view': 'v0',
                    'native_tasks': ['EC', 'EV'], 'source_units': units,
                    'native_public': {v['id']: v['public'] for v in source['views']},
                    'scope': scope('Illinois') if not refused else None,
                    'read_input': {'source_units': units, 'public_context': {'governing_regime':
                        'Illinois' if not refused else 'Federal/Oregon', 'supported_by_frozen_legal_program': not refused}},
                    'pre_generation_domain_refusal': refused, 'plans': [] if refused else [plan]}]
            def measure(self, source, view, candidate, purpose):
                tests.model_reads.append(source['key'])
                ports, _ = decode(candidate, raw, units)
                return {'source': source['key'], 'graph': None, 'ports': ports,
                    'physical_call_id': 'constructed-fixture:' + source['key'],
                    'channel_version': digest('constructed-fixed-pipeline'), 'production_errors': [],
                    'native': {family: {'handled': False, 'answer': None} for family in ('EC', 'EV')}}
        self.actor = FixtureActor()

    def manifest(self, reviews=None):
        return sealed({'source_public_sha256': {k: digest(s) for k, s in self.public.items()},
            'formal_roles_sha256': digest(self.roles),
            'production_alignment_source_sha256': self.actor.pipeline_binding,
            'executor': self.actor.executor.config,
            'reviews': self.reviews if reviews is None else reviews}, 'registry_sha256')

    def trainer(self, manifest=None):
        registry = ReferenceRegistry(self.root, self.manifest() if manifest is None else manifest,
                                     self.roles, self.public, self.actor)
        def grade(source, seal):
            self.assertTrue((self.root / 'training' / ('B' + str(seal['batch'])) /
                             'predictions_before_grading.json').exists())
            self.grade_reads.append(source)
            self.assertIn(next(r['role'] for r in self.roles if r['source'] == source),
                          ('development', 'calibration'))
            return {'EC': {'answer': {}}, 'EV': {'answer': {}}}
        return InterfaceBatchTrainer(self.root / 'training', roles=self.roles, public=self.public,
            registry=registry, actor=self.actor, candidate_orders={'OpenExempt': ['local_records']},
            grade_provider=grade, study_binding={'fixture': 'no real model calls'})

    def test_prefix_measurements_exclude_future_reference_and_structural_sources(self):
        trainer = self.trainer(); libraries = trainer.batch(1)
        self.assertEqual(set(self.model_reads), {r['source'] for r in self.roles if r['batch'] == 1})
        self.assertEqual(len(self.grade_reads), 2)
        self.assertTrue(all(lib['batch'] == 1 for lib in libraries.values()))
        self.assertEqual(libraries['M1_M2']['reference_world_groups'], [])

    def test_pure_reference_unknown_world_is_kept_without_reads_or_native_grades(self):
        libraries = self.trainer().batch(2)
        self.assertEqual(set(self.model_reads), {r['source'] for r in self.roles if r['batch'] == 1})
        refs = libraries['M1_M2']['reference_world_groups']
        self.assertEqual(len(refs), 1)
        self.assertEqual(len(refs[0]['records']), 1)
        self.assertEqual(refs[0]['records'][0]['source'], 'OpenExempt:fixture_reference_only')
        self.assertEqual(len(self.grade_reads), 2)
        self.assertTrue(libraries['M1_full_trace_replay']['fitted_groups'])

    def test_missing_review_stops_before_any_source_read_or_native_grade(self):
        missing = [r for r in self.reviews if r['source'] != 'OpenExempt:fixture_calibration']
        with self.assertRaisesRegex(MissingSourceReviews, 'lacks 1'):
            self.trainer(self.manifest(missing)).batch(1)
        self.assertEqual(self.model_reads, []); self.assertEqual(self.grade_reads, [])

    def test_explicit_public_domain_refusal_is_retained_in_native_denominator(self):
        self.public['OpenExempt:fixture_calibration']['domain_refused'] = True
        libraries = self.trainer().batch(1)
        report = libraries['M1_only']['M1_choices']['OpenExempt']['candidate_metrics'][0]
        self.assertEqual(report['mothers'], 2); self.assertEqual(report['native_tasks'], 4)
        self.assertEqual(self.model_reads, ['OpenExempt:fixture_development'])
        self.assertEqual(len(self.grade_reads), 2)

    def test_changed_review_role_source_or_pipeline_binding_is_rejected(self):
        bad = deepcopy(self.reviews); bad[0]['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'exact bytes'):
            self.trainer(self.manifest(bad)).batch(1)
        changed = deepcopy(self.public); changed['OpenExempt:fixture_development']['views'][0]['public'] = {'changed': True}
        manifest = self.manifest()
        with self.assertRaisesRegex(ValueError, 'per-source public'):
            ReferenceRegistry(self.root, manifest, self.roles, changed, self.actor)
        (self.root / 'fixture_pipeline.py').write_text('# changed\n')
        with self.assertRaisesRegex(ValueError, 'production/alignment source changed'):
            self.trainer(manifest)

    def test_structural_review_cannot_be_added_to_primary_registry(self):
        extra = {**self.reviews[0], 'source': 'OpenExempt:fixture_structure_evaluation'}
        with self.assertRaisesRegex(ValueError, 'structural-evaluation truth'):
            self.trainer(self.manifest(self.reviews + [extra]))

    def test_B0_initializes_all_four_arms_without_model_or_grade_access(self):
        libraries = self.trainer().batch(0)
        self.assertEqual(len(libraries), 4)
        self.assertEqual(self.model_reads, []); self.assertEqual(self.grade_reads, [])
        self.assertFalse(libraries['M1_only']['M1_choices']['OpenExempt']['supported'])


if __name__ == '__main__':
    unittest.main()
