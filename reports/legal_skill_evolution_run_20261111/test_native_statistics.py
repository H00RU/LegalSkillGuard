"""Validate the planned parent-unit metric and uncertainty calculation."""
import unittest

from .native_statistics import DATASETS, summarize, paired_source_bootstrap, nli_metrics, source_mean_intervals
from .formal_cost_footprints import used_physical_ids


def parent(dataset, grades, suffix='0', core=False):
    views = [{'view': str(i), 'controlled': False,
        'score': {'grade': value, 'correct': value == 1},
        'execution': {'core_executed': core, 'fallback': not core, 'answer': None}}
        for i, value in enumerate(grades)]
    return {'source': dataset + ':' + suffix, 'dataset': dataset, 'views': views,
            'native_grade': sum(grades) / len(grades) if all(v is not None for v in grades) else None}


class NativeStatisticsTests(unittest.TestCase):
    def test_shared_aligned_reads_and_failed_calls_are_each_counted_once(self):
        failed = 'legal_skill_evolution_formal_v1_20261111:' + 'a' * 64
        known = {'physical1', 'physical2', failed}
        events = [{'call_id': 'logical-only', 'physical_call_ids': ['physical1', 'physical2'],
            'subreads': [{'call_id': 'logical-1', 'physical_call_id': 'physical1'},
                         {'physical_call_id': 'physical2'}]},
            {'physical_call_id': 'physical1'}, {'error': 'Charged executor request failed: ' + failed}]
        self.assertEqual(used_physical_ids(events, known), known)

    def test_parent_then_dataset_means_are_not_view_pooled_or_controlled_scores(self):
        rows = [parent('OpenExempt', [0, 1]), parent('OpenExempt', [1, 1], '1'),
                parent('SARA_v2_Binary', [1]), parent('ContractNLI', [0] * 4),
                parent('RuleArena_Airline', [0]), parent('MAUD', [1] * 3)]
        rows[0]['views'].append({'view': 'controlled', 'controlled': True, 'score': {'grade': 1}})
        result = summarize(rows)
        self.assertAlmostEqual(result['datasets']['OpenExempt']['native_parent_mean'], .75)
        self.assertAlmostEqual(result['equal_five_dataset_macro'], .55)
        self.assertEqual(result['datasets']['OpenExempt']['path_counts']['native_views'], 4)
        self.assertEqual(result['datasets']['OpenExempt']['path_counts']['fully_correct_core_views'], 0)

    def test_paired_stratified_bootstrap_keeps_parent_views_and_all_five_datasets(self):
        left = [parent(d, [.75, .75], suffix=str(i)) for d in DATASETS for i in range(3)]
        right = [parent(d, [.25, .25], suffix=str(i)) for d in DATASETS for i in range(3)]
        result = paired_source_bootstrap(left, right, draws=256)
        self.assertAlmostEqual(result['equal_dataset_macro_difference'], .5)
        for interval in ('paired_source_bootstrap_95_percent_interval', 'four_contrast_Bonferroni_98_75_percent_interval'):
            for x in result[interval]:self.assertAlmostEqual(x, .5)
        self.assertEqual(result['independent_parents_per_dataset'], {d: 3 for d in DATASETS})
        with self.assertRaises(ValueError):paired_source_bootstrap(left, right[:-1], draws=8)
        right[0]['views'] = right[0]['views'][:1]
        with self.assertRaises(ValueError):paired_source_bootstrap(left, right, draws=8)

    def test_unknown_native_grade_is_neither_dropped_nor_made_zero(self):
        rows = [parent(d, [None if d == 'OpenExempt' else 1]) for d in DATASETS]
        self.assertIsNone(summarize(rows)['equal_five_dataset_macro'])
        with self.assertRaises(ValueError):paired_source_bootstrap(rows, rows, draws=8)
        with self.assertRaises(ValueError):summarize(rows + [rows[0]])
        with self.assertRaises(ValueError):source_mean_intervals(rows, draws=8)

    def test_source_mean_interval_does_not_invent_training_seed_variation(self):
        rows = [parent(d, [.5, .5], suffix=str(i)) for d in DATASETS for i in range(2)]
        interval = source_mean_intervals(rows, draws=64)
        for bounds in interval['intervals_95_percent'].values():
            for x in bounds:self.assertAlmostEqual(x, .5)
        self.assertFalse(interval['training_seed_variability'])

    def test_nli_invalid_answers_and_missing_evidence_remain_in_denominators(self):
        row = parent('ContractNLI', [1, 0, 1, 0])
        predictions = ['Entailment', 'invalid', 'NotMentioned', None]
        gold = ['Entailment', 'Contradiction', 'NotMentioned', 'Entailment']
        annotations = {row['source']: {str(i): {'answer': value, 'evidence': None if i == 2 else [i]}
            for i, value in enumerate(gold)}}
        for i, view in enumerate(row['views']):
            view['execution']['answer'] = predictions[i]
            if i in (0, 1):view['score']['evidence_f1'] = 1 if i == 0 else 0
        result = nli_metrics([row], annotations)
        self.assertAlmostEqual(result['three_label_macro_f1'], 5 / 9)
        self.assertAlmostEqual(result['evidence_f1_on_all_annotated_views'], 1 / 3)
        self.assertEqual(result['annotated_evidence_view_count'], 3)
        self.assertEqual(result['failed_execution_or_missing_evidence_views_scored_zero'], 1)


if __name__ == '__main__':unittest.main()
