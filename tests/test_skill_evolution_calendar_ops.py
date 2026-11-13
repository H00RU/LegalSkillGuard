import unittest
from legal_skill_guard.skill_evolution.calendar_ops import (inclusive_year_overlap_days,year_days,
    elapsed_year_overlap_days,calendar_year)


class CalendarOperationTests(unittest.TestCase):
    def test_actual_interval_has_only34_days_in2019(self):
        self.assertEqual(inclusive_year_overlap_days('2015-09-01','2019-02-03',2019),34)
        self.assertEqual(year_days(2019),365)

    def test_full_leap_year_and_disjoint_interval(self):
        self.assertEqual(inclusive_year_overlap_days('2019-01-01','2021-12-31',2020),366)
        self.assertEqual(inclusive_year_overlap_days('2015-09-01','2019-02-03',2020),0)

    def test_observation_errors_are_not_silently_fixed(self):
        for a,b in [('2019-02-03','2015-09-01'),('2019-02-30','2019-03-01')]:
            with self.assertRaises(ValueError):inclusive_year_overlap_days(a,b,2019)
        with self.assertRaises(ValueError):year_days(None)

    def test_elapsed_and_inclusive_conventions_are_explicit(self):
        self.assertEqual(elapsed_year_overlap_days('2015-09-01','2019-02-03',2019),33)
        self.assertEqual(calendar_year('2019-02-03'),2019)

    def test_public_arithmetic_runs_inside_the_actual_restricted_worker(self):
        from legal_skill_guard.skill_evolution.source_python import execute
        program='''def apply(inputs,premises):
    return {'days': inclusive_year_overlap_days(inputs['start'],inputs['end'],inputs['year']),
        'elapsed': elapsed_year_overlap_days(inputs['start'],inputs['end'],inputs['year']),
        'year_days': year_days(inputs['year']), 'end_year': calendar_year(inputs['end'])}
'''
        self.assertEqual(execute(program,{'start':'2015-09-01','end':'2019-02-03','year':2019}),
                         {'days':34,'elapsed':33,'year_days':365,'end_year':2019})
