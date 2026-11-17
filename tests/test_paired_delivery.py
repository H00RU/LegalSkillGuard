"""Reporting adversarial cases;all score/ledger fixtures are constructed."""
import json
from pathlib import Path
import tempfile
import unittest

from legal_skill_guard.paired_delivery import (
    EvidenceReader, completeness, contrasts, cost_summary, csv_text, dataset_statistics,
    load_main, local_graph_diagnostics, paired_difference, read_ledger, resampling_interval,
    training_accounting)
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.skill_evolution.objects import digest
from tests import test_paired_formal_study as fixtures


class DeliveryTests(unittest.TestCase):
    def test_mothers_not_native_tasks_are_resampling_units_and_unresolved_stays_zero(self):
        rows = [{'source': 'one', 'view': 'v0', 'grade': 1., 'handled': True}] + [
            {'source': 'two', 'view': 'v' + str(i), 'grade': 0., 'handled': False} for i in range(3)]
        stat = dataset_statistics(rows, {(r['source'], r['view']) for r in rows}, draws=100)
        self.assertEqual(stat['mother_macro'], .5)
        self.assertEqual(stat['mothers'], 2)
        self.assertEqual(stat['unresolved_or_failed_native_tasks'], 3)
        self.assertEqual(stat['mother_resampling']['mean'], .5)
        self.assertFalse(stat['mother_resampling']['independent_training_runs_inferred_from_resampling'])
        with self.assertRaisesRegex(ValueError, 'denominator'):
            dataset_statistics(rows[:-1], {(r['source'], r['view']) for r in rows}, draws=100)
        with self.assertRaisesRegex(ValueError, 'zero'):
            dataset_statistics([{**rows[-1], 'grade': 1.}], {('two', 'v2')}, draws=100)

    def test_paired_contrast_matches_source_identity_and_does_not_treat_views_as_independent(self):
        left = {'per_mother': {'b': 0., 'a': 1.}}
        right = {'per_mother': {'a': .5, 'b': 0.}}
        delta = paired_difference(left, right, draws=100)
        self.assertEqual(delta['mean'], .25)
        self.assertEqual(delta['per_mother_differences'], {'a': .5, 'b': 0.})
        self.assertFalse(delta['automatic_mechanism_attribution'])
        with self.assertRaisesRegex(ValueError, 'exact same'):
            paired_difference(left, {'per_mother': {'c': 0., 'a': .5}}, draws=100)
        self.assertTrue(resampling_interval([1.], draws=100)['one_mother_has_no_sampling_information'])

    def test_actual_zero_price_unknown_fee_failed_usage_and_pending_are_distinct(self):
        def record(identity, role, status, value):
            return {'id': identity, 'role': role, 'purpose': 'fixture', 'source': 'fixture',
                'status': status, 'reserved_at': 0, 'result': json.dumps(value) if value is not None else None}
        rows = [record('a', 'executor', 'completed', {'usage': {'prompt_tokens': 7, 'completion_tokens': 3},
                    'incremental_api_cash_usd': 0., 'gpu_cost_usd': None}),
                record('b', 'executor', 'failed', {}), record('c', 'teacher', 'completed', {})]
        result = cost_summary(rows, executor_context=32)
        executor = next(g for g in result['groups'] if g['role'] == 'executor')
        teacher = next(g for g in result['groups'] if g['role'] == 'teacher')
        self.assertEqual(executor['settled_executor_token_interval'], [10, 42])
        self.assertIsNone(executor['actual_input_plus_output_tokens'])
        self.assertEqual(executor['incremental_api_cash_usd']['sum_known_measurements'], 0.)
        self.assertIsNone(executor['incremental_api_cash_usd']['total'])
        self.assertIsNone(teacher['settled_executor_token_interval'])
        self.assertIsNone(teacher['gpu_cost_usd']['sum_known_measurements'])
        pending = cost_summary([record('p', 'executor', 'reserved', None)], executor_context=32)
        self.assertIsNone(pending['groups'][0]['settled_executor_token_interval'])

    def test_ledger_connection_is_read_only_and_prefix_costs_do_not_mutate_it(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'ledger.sqlite3'
            with sqlite3.connect(path) as db:
                db.execute('create table calls (id,role,purpose,source,status,reserved_at,result)')
                db.execute('insert into calls values (?,?,?,?,?,?,?)', ('fixture', 'teacher', 'fixture', 'fixture', 'failed', 0, '{}'))
            before = path.read_bytes()
            rows = read_ledger(path)
            self.assertEqual(len(rows), 1)
            cost_summary(rows)
            self.assertEqual(before, path.read_bytes())

    def matrix(self):
        case = fixtures.FormalStudyTests()
        case.setUp(); self.addCleanup(case.doCleanups)
        case.study.run()
        return case

    def test_complete_matrix_export_rechecks_all35_cells_and_DEV_checkpoint_rule(self):
        fixture = self.matrix()
        report = load_main(EvidenceReader(fixture.root), fixture.evaluator.sources, draws=100)
        self.assertEqual(len(report['metrics']), 35 * 2)
        self.assertEqual(len(report['native_rows']), 35 * 2)
        self.assertEqual(report['freeze']['choices']['M1_M2']['MAUD']['checkpoint_batch'], 1)
        self.assertEqual(len(contrasts(report['metrics'], draws=100)), 5 * 5 * 2)
        self.assertIn('native_metrics', csv_text(report['native_rows']).splitlines()[0])

    def test_resealed_but_false_aggregate_is_rejected_against_complete_native_rows(self):
        fixture = self.matrix()
        path = fixture.root / 'evaluation/test/B8/M1_M2/scores.json'
        report = json.loads(path.read_text())
        report['datasets']['MAUD']['mother_macro'] = .125
        report.pop('cell_sha256')
        path.write_text(json.dumps(sealed(report, 'cell_sha256')))
        with self.assertRaisesRegex(ValueError, 'aggregate'):
            load_main(EvidenceReader(fixture.root), fixture.evaluator.sources, draws=100)

    def test_changed_native_prediction_is_rejected_before_any_result_export(self):
        fixture = self.matrix()
        path = next((fixture.root / 'evaluation/test/B8/M1_M2/predictions').glob('*.json'))
        prediction = json.loads(path.read_text())
        prediction['result']['native']['native']['answer'] = 'tampered'
        path.write_text(json.dumps(prediction))
        with self.assertRaisesRegex(ValueError, 'saved predictions'):
            load_main(EvidenceReader(fixture.root), fixture.evaluator.sources, draws=100)

    def test_empty_study_reports_missing_files_and_never_creates_scores(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = {'internal_structural_TRAIN_sources': ['fixture:train'],
                    'M1_ablation_fixed_TEST_sources': ['fixture:test']}
            cohort = {p: [{'key': 'fixture:' + p}] for p in ('dev', 'test')}
            result = completeness(tmp, cohort, plan)
            self.assertFalse(result['all_required_files_present'])
            self.assertFalse(result['complete_goal_claimed'])
            self.assertIn('training_B8_seal.json', result['missing_files'])
            self.assertEqual(list(Path(tmp).iterdir()), [])
            with self.assertRaisesRegex(ValueError, 'empty result'):
                csv_text([])

    def test_local_schema_disagreement_keeps_alignment_unknown_and_production_abstention_separate(self):
        graph = {'nodes': [], 'facts': [], 'schema': 'fixture', 'context': 'fixture'}
        changed = {**graph, 'facts': [{'predicate': 'fixture', 'arguments': [], 'status': 'unread'}]}
        def pair(view, observed, alignment):
            return {'source': 'fixture', 'dataset': 'fixture', 'view': view, 'plan': 'fixture',
                'physical_call_id': 'fixture', 'alignment': alignment,
                'pair': {'reference': graph, 'observed': observed, 'role': 'calibration', 'plan_version': 'fixture'}}
        rows = [pair('ambiguous', [graph, changed], {}),
                pair('unknown', [changed], {'analysis_alignment_unknown': True}),
                pair('refused', [changed], {'observed_outcome': {'production_abstention': True}}),
                pair('OE_refused', [changed], {'production_abstention': True})]
        report = local_graph_diagnostics(rows)
        self.assertEqual([r['local_schema_disagreement_interval'] for r in report], [[0, 1], [0, 1], [1, 1], [1, 1]])
        self.assertTrue(report[3]['production_abstention'])
        self.assertFalse(report[0]['native_failure_inferred_from_graph_mismatch'])
        self.assertFalse(report[0]['analysis_alignment_unknown'])
        self.assertTrue(report[1]['analysis_alignment_unknown'])
        with self.assertRaisesRegex(ValueError, 'duplicated'):
            local_graph_diagnostics(rows + [rows[0]])

    def test_logical_cached_budget_and_raw_TRAIN_prediction_seals_are_verified(self):
        from legal_skill_guard.rr.checkpoint import immutable_json
        from legal_skill_guard.paired_interfaces.control_accounting import usage_summary
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); binding = {'fixture': True}
            graph = {'nodes': [], 'facts': [], 'schema': 'fixture', 'context': 'fixture'}
            pair = {'source': 'fixture:mother', 'dataset': 'fixture', 'view': 'v0', 'plan': 'fixed',
                'physical_call_id': 'old:one', 'alignment': {},
                'pair': {'reference': graph, 'observed': [graph], 'role': 'calibration', 'plan_version': 'fixture'}}
            physical = {'id': 'old:one', 'role': 'executor', 'purpose': 'skill_actor', 'source': 'fixture:mother',
                'status': 'completed', 'result': json.dumps({'usage': {'prompt_tokens': 10, 'completion_tokens': 3}})}
            libraries, controls = {}, {}
            for batch in range(9):
                directory = root / f'interface_training/B{batch}'
                predictions = [{'source': 'fixture:mother', 'plan': 'fixed', 'native': {'v0': {'handled': True}}}] if batch else []
                immutable_json(directory / 'shared_verified_raw_evidence.json', {'study_binding': binding, 'pairs': [pair] if batch else []})
                immutable_json(directory / 'predictions_before_grading.json', predictions)
                immutable_json(directory / 'prediction_seal.json', sealed({'batch': batch, 'study_binding': binding,
                    'predictions_sha256': digest(predictions), 'source_only_reference_native_labels_opened': False}, 'training_prediction_seal_sha256'))
                immutable_json(directory / 'native_TRAIN_scores.json', [{'source': 'fixture:mother', 'plan': 'fixed', 'view': 'v0'}] if batch else [])
                if not batch: continue
                cap = {'input_plus_output_token_cap': 13}
                immutable_json(root / f'batch_seals/B{batch}.json', {'primary_comparison_cap': cap})
                for phase, arm in (('ordinary', 'ordinary_teacher_skills'), ('scope', 'budget_matched_SCOPE_adaptation')):
                    summary = {'batch': batch, 'token_cap': 13, 'unique_logical_observations': 1,
                        'charged_input_plus_output_tokens': 13, 'physical_call_ids': ['old:one']}
                    libraries[arm, batch] = {'comparison_budget': summary}
                    controls[arm] = {'comparison_budget': summary}
                    immutable_json(root / f'controls/{phase}/budget/limits/B{batch}.json',
                        sealed({'batch': batch, 'evidence': cap, 'token_cap': 13}, 'limit_sha256'))
                    immutable_json(root / f'controls/{phase}/budget/observations/one.json', sealed({
                        'observation_key': 'one', 'physical_call_id': 'old:one', 'source': 'fixture:mother',
                        'status': 'completed', 'physical_result_sha256': digest(json.loads(physical['result'])),
                        'usage': usage_summary([('old:one', 'completed', physical['result'])], context_tokens=32)}, 'observation_sha256'))
            immutable_json(root / 'postfreeze_choice_seal.json', {'paired_TRAIN_records_sha256': digest([pair])})
            main = {'training': {'study_binding': binding, 'actual_control_completion_evidence': controls}, 'libraries': libraries}
            report = training_accounting(EvidenceReader(root), main, [physical], context_tokens=32)
            self.assertEqual(report['physical_ids'], ['old:one'])
            self.assertEqual(len(report['comparison_budgets']), 16)
            self.assertEqual(len(report['graph_pairs']), 1)
            bad = root / 'interface_training/B8/predictions_before_grading.json'
            bad.write_text('[]')
            with self.assertRaisesRegex(ValueError, 'pre-grading'):
                training_accounting(EvidenceReader(root), main, [physical], context_tokens=32)


if __name__ == '__main__':
    unittest.main()
