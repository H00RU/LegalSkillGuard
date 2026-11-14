"""Actual TRAIN traces distinguish optional nulls from a blocking input."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
import jsonschema

from legal_skill_guard.skill_evolution.case_observation_contract import checked_witnesses, execute_alternatives, kernel_execution
from legal_skill_guard.skill_evolution.kernel_residual import execution_residual
from legal_skill_guard.skill_evolution.observation_slice import compile_field_read, merge_field_read
from experiments import legal_skill_evolution_temporal_contract_learning as study


class KernelResidualTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = study.read(study.OUT / 'scored_results.json')['rows']
        cls.row = next(r for r in cls.rows if r['arm'] == 'ProgramGuided' and '8175fcb9' in r['source'])
        cls.kernel = next(k for k in study.read(study.OUT / 'kernel_bank.json') if k['name'] == cls.row['kernel'])
        cls.contract = next(c for c in study.read(study.OUT / 'ProgramGuided/teacher.json')['value']['contracts'] if c['kernel_name'] == cls.kernel['name'])
        cls.public = next(c['source']['views'][0]['public'] for c in study.read(study.direct.OUT / 'fixed_development_cases.json') if c['source']['key'] == cls.row['source'])

    def test_actual_program_results_and_bindings_are_unchanged(self):
        before = deepcopy(self.row['grounded']['bindings'][0]['inputs'])
        after = execution_residual(self.kernel, before)
        self.assertEqual(after['actual_execution'], kernel_execution(self.kernel, before))
        self.assertEqual(before, self.row['grounded']['bindings'][0]['inputs'])
        self.assertNotIn('legal_separation_decrees', before)

    def test_actual_ongoing_marriage_does_not_demand_its_optional_end_date(self):
        result = execution_residual(self.kernel, self.row['grounded']['bindings'][0]['inputs'])
        self.assertEqual(result['return_cause_input_paths'], [['legal_separation_decrees']])

    def test_direct_input_stops_at_a_different_earlier_guard(self):
        row = next(r for r in self.rows if r['arm'] == 'DirectRead' and r['source'] == self.row['source'])
        inputs = {k: v for k, v in row['observation']['inputs'].items() if v is not None}
        result = execution_residual(self.kernel, inputs)
        self.assertIn(['marriage_intervals', 0, 'end_date'], result['return_cause_input_paths'])
        self.assertNotIn(['legal_separation_decrees'], result['return_cause_input_paths'])

    def test_lens_is_derived_from_the_actual_learned_assignment(self):
        action = compile_field_read(self.contract, self.kernel, self.public, self.row['observation'], 'legal_separation_decrees')
        self.assertEqual(action['observation_path'], ['views', 0, 'decree_facts'])
        self.assertIn('legal_separation_decrees', action['binding_assignment']['expression'])
        self.assertFalse(action['actual_guard']['truth'])

    def test_unread_is_not_empty_and_explicit_source_absence_uses_original_checks(self):
        original = self.row['observation']
        action = compile_field_read(self.contract, self.kernel, self.public, original, 'legal_separation_decrees')
        unread = merge_field_read(original, action, {'status': 'unread', 'value': None, 'witnesses': []}, self.public)
        self.assertEqual(unread, original)
        # Reuse the already paid factual result; this creates no new test case,
        # factual completion, model call, rule or target-native answer.
        paid = study.read(study.ROOT / 'artifacts/legal_skill_evolution_missing_event_read_20261114/observation.json')
        updated = merge_field_read(original, action, paid, self.public)
        grounded = study.apply(self.contract, self.kernel, self.public, updated)
        result = execute_alternatives(self.kernel, grounded)
        self.assertTrue(result['handled'])
        self.assertEqual(result['answer'], 'Entailment')
        self.assertIsNone(original['views'][0]['decree_facts'])

    def test_handled_execution_has_no_residual_read(self):
        original = self.row['observation']
        action = compile_field_read(self.contract, self.kernel, self.public, original, 'legal_separation_decrees')
        paid = study.read(study.ROOT / 'artifacts/legal_skill_evolution_missing_event_read_20261114/observation.json')
        updated = merge_field_read(original, action, paid, self.public)
        bound = study.apply(self.contract, self.kernel, self.public, updated)['bindings'][0]['inputs']
        result = execution_residual(self.kernel, bound)
        self.assertTrue(result['actual_execution']['handled'])
        self.assertEqual(result['return_cause_input_paths'], [])

    def test_real_missing_witness_response_is_rejected_by_wire_schema(self):
        action = compile_field_read(self.contract, self.kernel, self.public, self.row['observation'], 'legal_separation_decrees')
        result_path, = (study.ROOT / 'artifacts/legal_skill_evolution_joint_scoped_observations_20261114/calls').glob('*/result.json')
        actual = json.loads(study.read(result_path)['content'])['decree_facts']
        self.assertEqual(actual['status'], 'none_stated')
        self.assertEqual(actual['witnesses'], [])
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(actual, action['schema'])
        # Existing host semantics already required a witness: this repairs the
        # generation-schema mismatch and does not accept the rejected response.
        with self.assertRaises(ValueError):
            checked_witnesses(actual['witnesses'], self.public)


if __name__ == '__main__':
    unittest.main()
