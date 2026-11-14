"""Matched policy routing on a real preserved TRAIN failure, without generation."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from legal_skill_guard.skill_evolution.case_read_comparison import compare_reads
from legal_skill_guard.skill_evolution.observation_slice import compile_field_read, merge_field_read
from experiments import legal_skill_evolution_temporal_contract_learning as study


class CaseReadComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rows = study.read(study.OUT / 'scored_results.json')['rows']
        cls.row = next(r for r in rows if r['arm'] == 'ProgramGuided' and '8175fcb9' in r['source'])
        cls.kernel = next(k for k in study.read(study.OUT / 'kernel_bank.json') if k['name'] == cls.row['kernel'])
        # The historical run used textual type descriptions. Its own runner
        # normalized them before checking bindings; normalize this fixture once
        # rather than adding an obsolete format branch to the current runtime.
        fields = json.loads(cls.kernel['input_fields_json'])
        for field in fields.values():
            field['type'] = study.direct.nominal_type(field['type'])
        cls.kernel['input_fields_json'] = json.dumps(fields)
        cls.contract = next(c for c in study.read(study.OUT / 'ProgramGuided/teacher.json')['value']['contracts'] if c['kernel_name'] == cls.kernel['name'])
        cls.public = next(c['source']['views'][0]['public'] for c in study.read(study.direct.OUT / 'fixed_development_cases.json') if c['source']['key'] == cls.row['source'])
        cls.paid = study.read(study.ROOT / 'artifacts/legal_skill_evolution_missing_event_read_20261114/observation.json')

    def test_both_paths_start_from_same_real_observation_and_use_same_contract(self):
        calls = []
        original = deepcopy(self.row['observation'])
        def read(policy, action):
            calls.append(policy)
            if policy == 'residual_guided':
                self.assertEqual(action['observation_path'], ['views', 0, 'decree_facts'])
                return self.paid, {'new_physical_calls': 0, 'offline_paid_replay': True}
            lens = compile_field_read(self.contract, self.kernel, self.public, original, 'legal_separation_decrees')
            return merge_field_read(original, lens, self.paid, self.public), {'new_physical_calls': 0, 'offline_paid_replay': True}
        result = compare_reads(self.contract, self.kernel, self.public, original, read)
        self.assertEqual(calls, ['residual_guided', 'ordinary_reread'])
        self.assertEqual(original, self.row['observation'])
        self.assertTrue(result['contract_and_initial_observation_unchanged'])
        for policy in result['policies'].values():
            self.assertEqual(len(policy['calls']), 1)
            self.assertTrue(policy['execution']['handled'])
        self.assertFalse(result['eligibility_uses_native_answers'])

    def test_already_handled_does_not_retry_using_score_or_target_label(self):
        lens = compile_field_read(self.contract, self.kernel, self.public, self.row['observation'], 'legal_separation_decrees')
        updated = merge_field_read(self.row['observation'], lens, self.paid, self.public)
        def forbidden(*args):
            self.fail('A handled input was re-read')
        result = compare_reads(self.contract, self.kernel, self.public, updated, forbidden)
        self.assertFalse(result['eligible'])
        self.assertEqual(result['policies'], {})

    def test_failed_witness_read_remains_a_failure_both_opportunities_preserved(self):
        calls = []
        def bad(policy, action):
            calls.append(policy)
            return {'status': 'none_stated', 'value': None, 'witnesses': []}, {'offline': True}
        result = compare_reads(self.contract, self.kernel, self.public, self.row['observation'], bad)
        self.assertEqual(calls, ['residual_guided', 'ordinary_reread'])
        for policy in result['policies'].values():
            self.assertFalse(policy['execution']['handled'])
            self.assertIn('error', policy)


if __name__ == '__main__':
    unittest.main()
