"""Evaluation ordering and full-matrix freeze tests;constructed labels only."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from legal_skill_guard.paired_interfaces.formal_design import ARMS, CURVES
from legal_skill_guard.paired_interfaces.formal_evaluation import ConvergenceEvaluation, FormalEvaluation, sealed, verify
from legal_skill_guard.rr.ledger import BudgetError
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


class FormalEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.sources = {partition: [{'key': partition + ':' + dataset + ':' + str(i), 'dataset': dataset,
            'views': [{'id': 'native', 'public': {'facts': 'constructed fixture'},
                       'answer_schema': {'type': 'boolean'}}]} for dataset in ('SARA_v2_Binary', 'MAUD')
                       for i in range(2)] for partition in ('dev', 'test')}
        self.binding = {'fixture_code': 'one', 'not_a_scientific_run': True}
        self.grades_opened, self.actor_calls = [], []
        def grader(partition, source, seal):
            verify(seal, 'prediction_seal_sha256')
            self.assertEqual(len(seal['predictions_sha256']), 4)
            self.assertTrue(any(p.read_text() for p in self.root.glob(partition + '/B*/*/prediction_seal.json')))
            self.grades_opened.append((partition, source))
            return {'native': {'answer': True}}
        self.evaluation = FormalEvaluation(self.root, self.sources, binding=self.binding, grade_provider=grader)
        self.libraries = {(arm, batch): sealed({'arm': arm, 'batch': batch,
                           'fixture': 'constructed inference library'}, 'snapshot_sha256')
                          for arm in ARMS for batch in CURVES}

    def actor(self, source, library, purpose):
        self.actor_calls.append((source['key'], library['arm'], library['batch'], purpose))
        answer = library['batch'] in ((0, 1) if source['dataset'] == 'MAUD' else (0, 4, 8))
        return {'native': {'native': {'handled': True, 'answer': answer, 'fallback_executed': False}}}

    def curves(self):
        for arm in ARMS:
            for batch in CURVES:
                self.evaluation.evaluate('dev', arm, batch,
                    {source['dataset']: self.libraries[arm, batch] for source in self.sources['dev']}, self.actor)

    def training_seal(self):
        return sealed({'batch': 8, 'study_binding': self.binding, 'all_seven_libraries_frozen': True,
            'libraries': {arm: self.libraries[arm, 8]['snapshot_sha256'] for arm in ARMS}}, 'training_seal_sha256')

    def test_all28_cells_precede_per_dataset_choice_B0_excluded_and_later_ties(self):
        self.curves()
        freeze = self.evaluation.freeze(self.libraries, training_B8_seal=self.training_seal())
        for arm in ARMS:
            self.assertEqual(freeze['choices'][arm]['MAUD']['checkpoint_batch'], 0 if arm == 'empty' else 1)
            self.assertEqual(freeze['choices'][arm]['SARA_v2_Binary']['checkpoint_batch'], 0 if arm == 'empty' else 8)
            selected = {dataset: self.libraries[arm, value['checkpoint_batch']]
                        for dataset, value in freeze['choices'][arm].items()}
            report = self.evaluation.evaluate('test', arm, 8, selected, self.actor, freeze=freeze)
            self.assertEqual(sum(row['mothers'] for row in report['datasets'].values()), 4)
        self.assertEqual(len(self.grades_opened), (28 + 7) * 4)
        calls = len(self.actor_calls)
        # A completed cell resumes without neural work or opening labels again.
        self.evaluation.evaluate('test', 'empty', 8,
            {d: self.libraries['empty', 0] for d in freeze['choices']['empty']}, self.actor, freeze=freeze)
        self.assertEqual(len(self.actor_calls), calls)
        self.assertEqual(len(self.grades_opened), (28 + 7) * 4)

    def test_TEST_before_freeze_and_missing_DEV_cells_cannot_start(self):
        with self.assertRaisesRegex(ValueError, 'freeze'):
            self.evaluation.evaluate('test', 'M1_only', 8,
                {s['dataset']: self.libraries['M1_only', 8] for s in self.sources['test']}, self.actor)
        self.assertEqual(self.actor_calls, []); self.assertEqual(self.grades_opened, [])
        with self.assertRaises(FileNotFoundError):
            self.evaluation.freeze(self.libraries, training_B8_seal=self.training_seal())

    def test_unresolved_predictions_stay_in_full_native_denominator(self):
        report = self.evaluation.evaluate('dev', 'M1_only', 1,
            {s['dataset']: self.libraries['M1_only', 1] for s in self.sources['dev']},
            lambda *args: {'native': {'native': {'handled': False, 'answer': None}}})
        self.assertTrue(all(r['mother_macro'] == 0 and r['native_tasks'] == 2
                            and r['unresolved_or_failed_native_tasks'] == 2 for r in report['datasets'].values()))

    def test_transport_failure_is_not_a_scored_perception_abstention(self):
        def interrupted(*args):
            raise BudgetError('constructed unavailable service')
        with self.assertRaises(BudgetError):
            self.evaluation.evaluate('dev', 'M1_only', 1,
                {s['dataset']: self.libraries['M1_only', 1] for s in self.sources['dev']}, interrupted)
        self.assertEqual(self.grades_opened, [])

        self.assertFalse(list(self.root.glob('dev/B1/M1_only/scores.json')))

    def test_changed_saved_prediction_cannot_reuse_existing_scores(self):
        libraries = {s['dataset']: self.libraries['M1_only', 1] for s in self.sources['dev']}
        self.evaluation.evaluate('dev', 'M1_only', 1, libraries, self.actor)
        path = next(self.root.glob('dev/B1/M1_only/predictions/*.json'))
        record = json.loads(path.read_text()); record['result']['native']['native']['answer'] = 'changed'
        path.write_text(json.dumps(record))
        with self.assertRaises(FileExistsError):
            self.evaluation.evaluate('dev', 'M1_only', 1, libraries, self.actor)

    def test_changed_or_borrowed_library_and_incomplete_task_output_rejected(self):
        libraries = {s['dataset']: self.libraries['M1_only', 1] for s in self.sources['dev']}
        borrowed = deepcopy(libraries); borrowed['MAUD'] = self.libraries['M1_M2', 1]
        with self.assertRaisesRegex(ValueError, 'own exact arm'):
            self.evaluation.evaluate('dev', 'M1_only', 1, borrowed, self.actor)
        with self.assertRaisesRegex(ValueError, 'every native task'):
            self.evaluation.evaluate('dev', 'M1_only', 1, libraries, lambda *a: {'native': {}})
        self.assertEqual(self.grades_opened, [])


class ConvergenceEvaluationTests(unittest.TestCase):
    def test_b2_required_and_test_loader_receives_only_the_exact_b8_selection(self):
        def cohort(partition, count):
            return [{
                'key': f'{partition}/{dataset}/{index}', 'project_split': partition, 'dataset': dataset,
                'views': [{'id': 'native', 'public': {}, 'answer_schema': {'type': 'boolean'}}],
            } for dataset in sorted(ConvergenceEvaluation.datasets) for index in range(count)]

        dev, test = cohort('dev', 16), cohort('test', 32)
        identities = [{'source': row['key'], 'dataset': row['dataset'], 'project_split': 'test',
                       'native_views': ['native'], 'public_content_sha256': digest(row)} for row in test]
        binding = {'DEV_public_sha256': digest(dev), 'TEST_identities_sha256': digest(identities),
                   'enforce_physical_actor_audit': True}
        loads = []

        def loader():
            loads.append(True)
            return test

        def interrupted(*args):
            raise BudgetError('Stop after entering the synthetic TEST actor')
        interrupted.verify_saved = lambda *args: None

        with tempfile.TemporaryDirectory() as root:
            evaluation = ConvergenceEvaluation(root, dev, identities, binding=binding,
                grade_provider=lambda *args: self.fail('No labels should be opened'), load_test=loader)
            libraries = {(arm, batch): sealed({'arm': arm, 'batch': batch}, 'snapshot_sha256')
                         for arm in evaluation.arms for batch in evaluation.curves}
            training = sealed({'batch': 8, 'study_binding': binding, 'all_five_libraries_frozen': True,
                               'libraries': {arm: libraries[arm, 8]['snapshot_sha256'] for arm in evaluation.arms}},
                              'training_seal_sha256')
            arm = evaluation.arms[0]
            final = dict.fromkeys(evaluation.datasets, libraries[arm, 8])
            with self.assertRaisesRegex(ValueError, 'sealed fixed B8'):
                evaluation.evaluate('test', arm, 8, final, interrupted)
            self.assertEqual(loads, [])
            held_out_cell = None
            for (family, batch), library in libraries.items():
                report = sealed({'study_binding': binding, 'arm': family, 'batch': batch,
                    'partition': 'dev', 'public_cohort_sha256': digest(dev),
                    'datasets': dict.fromkeys(evaluation.datasets, {'mother_macro': float(batch == 1)}),
                    'libraries': dict.fromkeys(evaluation.datasets, library['snapshot_sha256'])}, 'cell_sha256')
                path = evaluation.cell_path('dev', family, batch) / 'scores.json'
                if family == arm and batch == 2:
                    held_out_cell = path, report
                else:
                    immutable_json(path, report)
            with self.assertRaises(FileNotFoundError):
                evaluation.freeze(libraries, training_B8_seal=training)
            immutable_json(*held_out_cell)
            freeze = evaluation.freeze(libraries, training_B8_seal=training)
            self.assertEqual(loads, [])
            self.assertTrue(all(row['checkpoint_batch'] == 8 for row in freeze['choices'][arm].values()))
            with self.assertRaisesRegex(ValueError, 'own exact arm'):
                evaluation.evaluate('test', arm, 8, dict.fromkeys(evaluation.datasets, libraries[arm, 1]),
                                    interrupted, freeze=freeze)
            self.assertEqual(loads, [])
            with self.assertRaises(BudgetError):
                evaluation.evaluate('test', arm, 8, final, interrupted, freeze=freeze)
            self.assertEqual(loads, [True])


if __name__ == '__main__':
    unittest.main()
