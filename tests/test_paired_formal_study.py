"""Full coordinator ordering fixtures;no research data,teacher or server calls."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from legal_skill_guard.paired_interfaces.formal_controls import ORDINARY, SCOPE
from legal_skill_guard.paired_interfaces.formal_design import ARMS
from legal_skill_guard.paired_interfaces.formal_evaluation import FormalEvaluation, sealed
from legal_skill_guard.paired_interfaces.formal_study import FormalStudy
from legal_skill_guard.paired_interfaces.formal_training import MissingSourceReviews
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.ledger import BudgetError
from legal_skill_guard.skill_evolution.objects import digest
from tests import test_paired_formal_budget as fixtures


class FormalStudyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.binding = {'constructed_fixture_only': True}
        self.events = []; self.ready = True
        ledger = fixtures.FixtureLedger('fixture_primary'); self.addCleanup(ledger.db.close)
        raw = fixtures.FixtureExecutor(ledger)
        for batch in range(1, 9):
            raw.generate('fixture_primary:' + str(batch), source='fixture:' + str(batch), purpose='skill_actor')
        tests = self
        class Interfaces:
            root = tests.root / 'primary'
            orders = {'SARA_v2_Binary': ['columns', 'records', 'local_records'],
                      'MAUD': ['columns', 'records', 'local_records']}
            registry = SimpleNamespace(readiness=lambda batch: {'ready': tests.ready, 'batch': batch})
            actor = SimpleNamespace(executor=raw)
            def batch(self, batch):
                tests.events.append(('primary', batch))
                immutable_json(self.root / ('B' + str(batch)) / 'shared_verified_raw_evidence.json', {
                    'study_binding': tests.binding, 'pairs': [{'physical_call_id': 'fixture_primary:' + str(i)}
                                                            for i in range(1, batch + 1)]})
                return {arm: tests.library(arm, batch) for arm in ('M1_only', 'M2_fixed_interfaces', 'M1_full_trace_replay', 'M1_M2')}
        self.interfaces = Interfaces()
        sources = {partition: [{'key': partition + ':' + dataset, 'dataset': dataset, 'views': [
            {'id': 'native', 'public': {'facts': 'fixture'}, 'answer_schema': {'type': 'boolean'}}]}
            for dataset in ('SARA_v2_Binary', 'MAUD')] for partition in ('dev', 'test')}
        def grades(partition, source, seal):
            self.assertTrue((self.root / 'training_B8_seal.json').exists())
            self.events.append(('grade', partition))
            return {'native': {'answer': True}}
        self.evaluator = FormalEvaluation(self.root / 'evaluation', sources, binding=self.binding, grade_provider=grades)
        def control_factory(arm, batch, cap):
            if batch:
                self.assertEqual(cap['input_plus_output_token_cap'], 13 * batch)
            class Control:
                def batch(self, value):
                    tests.events.append((arm, value)); return tests.library(arm, value)
                def completion_evidence(self):
                    return {'arm': arm, 'actual_fixed_optimizer_teacher_calls': [arm + ':' + str(i) for i in range(8)],
                        'candidates_per_dataset': 3,
                        'libraries_B0_through_B8': {str(i): tests.library(arm, i)['snapshot_sha256'] for i in range(9)}}
            return Control()
        def actors(arm, partition, freeze):
            def actor(source, library, purpose):
                self.assertEqual(purpose, 'skill_dev' if partition == 'dev' else 'skill_test')
                self.assertIsNone(freeze) if partition == 'dev' else self.assertIsNotNone(freeze)
                answer = library['batch'] == 1 if source['dataset'] == 'MAUD' else library['batch'] in (4, 8)
                return {'native': {'native': {'handled': True, 'answer': answer}}}
            return actor
        self.study = FormalStudy(self.root, binding=self.binding, interface_trainer=self.interfaces,
            control_factory=control_factory, evaluator=self.evaluator, evaluation_actor_factory=actors,
            source_binding_check=lambda: self.events.append(('source_binding_check',)))

    def library(self, arm, batch):
        return sealed({'arm': arm, 'batch': batch, 'fixture': True}, 'snapshot_sha256')

    def test_all_nine_prefixes_and_seven_systems_precede_the_fixed_28_plus7_matrix(self):
        terminal = self.study.run()
        self.assertEqual(len(terminal['DEV_cells']), 28); self.assertEqual(len(terminal['TEST_cells']), 7)
        self.assertFalse(terminal['independent_contributions_or_complete_goal_established'])
        self.assertEqual(len(list((self.root / 'libraries').glob('B*/*.json'))), 9 * 7)
        for batch in range(9):
            self.assertLess(self.events.index((SCOPE, batch)), self.events.index((ORDINARY, batch)))
        self.assertLess(self.events.index((ORDINARY, 8)), next(i for i, e in enumerate(self.events) if e[0] == 'grade'))
        freeze = json.loads((self.root / 'evaluation/selection_freeze.json').read_text())
        self.assertEqual(freeze['choices']['M1_M2']['MAUD']['checkpoint_batch'], 1)
        self.assertEqual(freeze['choices']['M1_M2']['SARA_v2_Binary']['checkpoint_batch'], 8)

    def test_full_missing_reference_gate_stops_before_any_component_execution(self):
        self.ready = False
        with self.assertRaises(MissingSourceReviews):
            self.study.train()
        self.assertFalse(any(e[0] in ('primary', ORDINARY, SCOPE, 'grade') for e in self.events))

    def test_incomplete_control_stage_evidence_prevents_B8_training_seal(self):
        original = self.study.control_factory
        def incomplete(arm, batch, cap):
            control = original(arm, batch, cap)
            method = control.completion_evidence
            control.completion_evidence = lambda: {**method(), 'actual_fixed_optimizer_teacher_calls': []}
            return control
        self.study.control_factory = incomplete
        with self.assertRaisesRegex(ValueError, 'must be evidenced'):
            self.study.train()
        self.assertFalse((self.root / 'training_B8_seal.json').exists())
        self.assertFalse(any(e[0] == 'grade' for e in self.events))

    def test_production_binding_requires_cached_actor_physical_audits(self):
        evaluation = FormalEvaluation(self.root / 'strict_eval', self.evaluator.sources,
            binding={'enforce_physical_actor_audit': True}, grade_provider=lambda *a: self.fail('must not open grading'))
        with self.assertRaisesRegex(ValueError, 'audit saved physical'):
            evaluation.evaluate('dev', 'M1_only', 1,
                {s['dataset']: self.library('M1_only', 1) for s in self.evaluator.sources['dev']}, lambda *a: None)

    def test_changed_protocol_cannot_register_a_second_main_matrix(self):
        from experiments.two_method_formal_study import bind_single_study
        registry = self.root / 'study_registry'
        initial = bind_single_study(registry, registry / 'one', digest('one'))
        self.assertEqual(initial, bind_single_study(registry, registry / 'one', digest('one')))
        with self.assertRaisesRegex(BudgetError, 'one formal matrix is already bound'):
            bind_single_study(registry, registry / 'two', digest('two'))
        self.assertTrue(initial['not_a_live_process_or_permission_receipt'])

    def test_diagnostic_choices_are_frozen_after_B8_but_before_any_DEV_or_TEST_grade(self):
        events = self.events
        class Diagnostics:
            def prepare(self, libraries, training):
                events.append(('diagnostic_choice_seal',))
            def run(self, freeze):
                events.append(('diagnostic_run',))
                return {'constructed_fixture': True}
        self.study.diagnostics = Diagnostics()
        result = self.study.run()
        seal_index = events.index(('diagnostic_choice_seal',))
        first_grade = next(i for i, e in enumerate(events) if e[0] == 'grade')
        self.assertLess(events.index((ORDINARY, 8)), seal_index)
        self.assertLess(seal_index, first_grade)
        self.assertGreater(events.index(('diagnostic_run',)), first_grade)
        self.assertFalse(result['complete_goal_claimed'])


if __name__ == '__main__':
    unittest.main()
