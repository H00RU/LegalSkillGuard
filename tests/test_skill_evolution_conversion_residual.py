"""Actual helper-based converter blocking paths, with no new case or model call."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from experiments import legal_skill_evolution_observation_library_train as study
from legal_skill_guard.skill_evolution.case_read_comparison import compare_reads
from legal_skill_guard.skill_evolution.conversion_residual import component_action, trace_conversion
from legal_skill_guard.skill_evolution.native import record_schema


class ConversionResidualTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.library = study.read(study.OUT / 'B1/ProgramGuided/library.json')
        cls.components = {c['id']: c for c in cls.library['components']}
        cls.public = {s['key']: s for s in study.read(study.parent.OUT / 'SARA_corrected_TRAIN_views.json')}
        cls.kernels = {r['source']: r['kernel'] for r in study.read(study.parent.OUT / 'SARA_native_kernel_bank.json')}

    def case(self, prefix):
        sid = next(s for s in self.public if prefix in s)
        row = study.read(study.OUT / 'B1/ProgramGuided/results' / (study.digest(sid) + '.json'))
        ids = row['actual_component_ids']
        contract = {'binding_program': self.library['binding_program'],
            'observation_prompt': '\n\n'.join(self.components[c]['prompt'] for c in ids),
            'observation_schema_json': json.dumps(record_schema({c: json.loads(self.components[c]['schema_json']) for c in ids})),
            'requires_neural_read': True}
        return row, contract, self.kernels[sid], self.public[sid]['views'][0]['public']

    def test_actual_helper_guard_identifies_unread_coupled_fields_not_optional_endpoint(self):
        row, contract, kernel, public = self.case('5c29a3')
        action = component_action(contract, kernel, public, row['observation'])
        self.assertEqual(action['component_ids'], ['marriage_returns_itemization'])
        self.assertEqual({p[-1] for p in action['blocking_observation_paths']}, {'returns', 'itemizations'})
        self.assertNotIn('end_date', [p[-1] for p in action['blocking_observation_paths']])
        self.assertEqual(action['residual_stage'], 'learned_conversion_program')
        self.assertTrue(action['not_a_Prolog_proof_trace_or_minimality_certificate'])

    def test_instrumentation_keeps_the_actual_converter_result(self):
        for prefix in ('5c29a3', '8175fcb9', '815f377b'):
            row, contract, kernel, public = self.case(prefix)
            traced = trace_conversion(contract, kernel, public, row['observation'])
            self.assertEqual(traced['result']['bindings'], row['grounded']['bindings'])
            self.assertEqual(traced['result']['unresolved'], row['grounded']['unresolved'])

    def test_pair_uses_one_initial_contract_and_keeps_unread_unchanged(self):
        row, contract, kernel, public = self.case('5c29a3')
        original = deepcopy(row['observation'])
        called = []
        def read(policy, action):
            called.append(policy)
            if policy == 'residual_guided':
                return {c: deepcopy(original[c]) for c in action['component_ids']}, {'offline_existing_observation': True}
            self.assertEqual(action['scope_reason'], 'existing_unresolved_message')
            self.assertEqual(action['component_ids'], ['marriage_returns_itemization'])
            return {c: deepcopy(original[c]) for c in action['component_ids']}, {'offline_existing_observation': True}
        result = compare_reads(contract, kernel, public, original, read)
        self.assertEqual(called, ['residual_guided', 'ordinary_reread'])
        self.assertTrue(result['contract_and_initial_observation_unchanged'])
        self.assertEqual(original, row['observation'])
        for policy in result['policies'].values():
            self.assertFalse(policy['execution']['handled'])
            self.assertEqual(policy['observation_after'], original)

    def test_an_executed_wrong_answer_is_not_label_triggered_rereading(self):
        row, contract, kernel, public = self.case('8175fcb9')
        self.assertTrue(row['execution']['handled'])
        def forbidden(*args):
            self.fail('Known native correctness cannot trigger an extra read')
        result = compare_reads(contract, kernel, public, row['observation'], forbidden)
        self.assertFalse(result['eligible'])

    def test_actual_later_unread_reason_through_helper_dict_list_and_merge(self):
        library = study.read(study.OUT / 'B2/FreeHistory/library.json')
        sid = next(s for s in self.public if 'd5e1138c' in s)
        row = study.read(study.OUT / 'B3/FreeHistory/initial_results' / (study.digest(sid) + '.json'))
        components = {c['id']: c for c in library['components']}
        ids = row['actual_component_ids']
        contract = {'binding_program': library['binding_program'], 'observation_prompt': '',
            'observation_schema_json': json.dumps(record_schema({c: json.loads(components[c]['schema_json']) for c in ids})),
            'requires_neural_read': True}
        public, kernel = self.public[sid]['views'][0]['public'], self.kernels[sid]
        action = component_action(contract, kernel, public, row['observation'])
        self.assertEqual(action['component_ids'], ['termination_benefit_events'])
        self.assertTrue(any(p[-1] == 'extraction_status' for p in action['blocking_observation_paths']))
        self.assertNotIn('payment_service_events', action['component_ids'])
        self.assertEqual(action['trace']['result']['unresolved'], row['grounded']['unresolved'])


if __name__ == '__main__':
    unittest.main()
