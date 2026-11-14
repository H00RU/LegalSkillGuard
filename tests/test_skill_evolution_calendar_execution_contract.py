"""The public validator must agree with the worker's calendar capabilities."""
import unittest

from legal_skill_guard.skill_evolution.span_compiler import execute_json


class CalendarExecutionContractTests(unittest.TestCase):
    def test_generated_kernel_type_checks_keep_booleans_distinct_from_integer_years(self):
        program = "def apply(inputs, premises):\n    return {'integer_year': type(inputs['year']) is int}\n"
        self.assertEqual(execute_json(program, {'year': 2019}, {}), {'integer_year': True})
        self.assertEqual(execute_json(program, {'year': True}, {}), {'integer_year': False})

    def test_actual_cross_year_residence_interval_clips_to_query_year(self):
        program = """def apply(inputs, premises):
    return {'days': inclusive_year_overlap_days(inputs['start'], inputs['end'], inputs['year']),
            'year_days': year_days(inputs['year']),
            'end_year': calendar_year(inputs['end'])}
"""
        value = execute_json(program, {'start': '2015-09-01', 'end': '2019-02-03', 'year': 2019}, {})
        self.assertEqual(value, {'days': 34, 'year_days': 365, 'end_year': 2019})

    def test_invalid_observed_date_propagates_failure(self):
        code = "def apply(inputs, premises):\n    return {'days': elapsed_year_overlap_days(inputs['start'], inputs['end'], inputs['year'])}\n"
        with self.assertRaises(ValueError):
            execute_json(code, {'start': '2019-02-30', 'end': '2019-03-01', 'year': 2019}, {})
