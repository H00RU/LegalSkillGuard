"""Selection leakage and missing-denominator checks, not efficacy fixtures."""
import unittest

from legal_skill_guard.paired_interfaces.pilot_metrics import select_fixed_plans, summarize


class PilotMetricsTests(unittest.TestCase):
    def row(self, source, view, grade, *, plan='columns', role='development', handled=True):
        return {'source': source, 'view': view, 'dataset': 'fixture', 'plan': plan,
                'role': role, 'grade': grade, 'handled': handled}

    def test_mothers_are_balanced_and_failed_native_tasks_stay_in_denominator(self):
        rows = [self.row('many', str(i), 1.) for i in range(4)]
        rows.append(self.row('one', 'q', 0., handled=False))
        result = summarize(rows, {(row['source'], row['view']) for row in rows})
        self.assertEqual(result['mother_macro'], .5)
        self.assertEqual(result['unresolved_or_failed_native_tasks'], 1)
        with self.assertRaisesRegex(ValueError, 'denominator'):
            summarize(rows[:-1], {(row['source'], row['view']) for row in rows})
        with self.assertRaisesRegex(ValueError, 'twice'):
            summarize(rows + rows[:1], {(row['source'], row['view']) for row in rows})

    def test_calibration_and_structural_outcomes_cannot_change_a_D0_choice(self):
        lock = [{'key': 'dev', 'dataset': 'fixture', 'role': 'development'},
                {'key': 'cal', 'dataset': 'fixture', 'role': 'calibration'},
                {'key': 'eval', 'dataset': 'fixture', 'role': 'structure_evaluation'}]
        rows = [self.row('dev', 'q', 0., plan='columns'), self.row('dev', 'q', 1., plan='records')]
        options = ({'fixture': ['columns', 'records']}, {'dev': ['q'], 'cal': ['q'], 'eval': ['q']})
        before = select_fixed_plans(rows, lock, *options)
        rows.extend([self.row('cal', 'q', 1., plan='columns', role='calibration'),
                     self.row('eval', 'q', 1., plan='columns', role='structure_evaluation')])
        self.assertEqual(select_fixed_plans(rows, lock, *options), before)
        self.assertEqual(before['fixture']['plan'], 'records')

    def test_all_failure_ties_preserve_original_candidate_order(self):
        lock = [{'key': 'dev', 'dataset': 'fixture', 'role': 'development'}]
        rows = [self.row('dev', 'q', 0., plan=plan, handled=False) for plan in ('records', 'columns')]
        selected = select_fixed_plans(rows, lock, {'fixture': ['records', 'columns']}, {'dev': ['q']})
        self.assertEqual(selected['fixture']['plan'], 'records')
        with self.assertRaises(ValueError):
            summarize([self.row('dev', 'q', None)], {('dev', 'q')})


if __name__ == '__main__':
    unittest.main()
