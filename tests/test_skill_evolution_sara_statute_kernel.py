"""New data-only transport to the existing official statute runtime."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
import jsonschema

from experiments.legal_skill_evolution_native_execution_reuse import parse_query
from legal_skill_guard.skill_evolution.case_observation_contract import kernel_execution
from legal_skill_guard.skill_evolution.sara_statute_kernel import scalar, fact_term, input_schema, GIVENS


ROOT = Path(__file__).resolve().parents[1]


class SaraStatuteKernelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bank = json.loads((ROOT / 'artifacts/legal_skill_evolution_native_execution_reuse_20261114/kernel_bank.json').read_text())
        cls.kernel = deepcopy(next(k for k in cls.bank if k['name'] == 'surviving_spouse_death_window'))
        cls.kernel['native_query'] = [{'predicate': 's2_a_1_A',
            'arguments': ['TaxpayerFixture', {'variable': '_'}, {'variable': '_'}, {'variable': '_'}, 2015]}]

    def test_real_query_constants_and_conjunction_are_preserved_without_polarity(self):
        query = parse_query(':- \\+ s63_c_5("Person",_,_,2017,500).\n:- halt.')
        self.assertEqual(query[0]['arguments'], ['Person', {'variable': '_'}, {'variable': '_'}, 2017, 500])
        query = parse_query(':- s3306_c_10_A("services","School","Person","2017-01-01"), s3306_c_10_A_i("Person","School","2017-01-01").\n:- halt.')
        self.assertEqual(len(query), 2)
        self.assertEqual(query[1]['arguments'][-1], '2017-01-01')

    def test_unread_is_not_an_empty_complete_case(self):
        result = kernel_execution(self.kernel, {'facts': [], 'negative_givens': [], 'extraction_status': 'unread'})
        self.assertFalse(result['handled'])
        self.assertIsNone(result['answer'])

    def test_data_only_transport_executes_author_rules_with_no_original_case_facts(self):
        facts = [
            {'predicate': 'marriage_', 'arguments': ['marriage_fixture']},
            {'predicate': 'agent_', 'arguments': ['marriage_fixture', 'TaxpayerFixture']},
            {'predicate': 'agent_', 'arguments': ['marriage_fixture', 'SpouseFixture']},
            {'predicate': 'start_', 'arguments': ['marriage_fixture', '2012-04-05']},
            {'predicate': 'death_', 'arguments': ['death_fixture']},
            {'predicate': 'agent_', 'arguments': ['death_fixture', 'SpouseFixture']},
            {'predicate': 'start_', 'arguments': ['death_fixture', '2014-07-09']},
        ]
        result = kernel_execution(self.kernel, {'facts': facts, 'negative_givens': [], 'extraction_status': 'complete'})
        self.assertTrue(result['handled'], result)
        self.assertEqual(result['answer'], 'Entailment')
        self.assertTrue(result['source_program_unchanged'])

    def test_duplicate_assertions_and_source_changes_are_not_accepted(self):
        fact = {'predicate': 'death_', 'arguments': ['event_fixture']}
        with self.assertRaises(ValueError):
            kernel_execution(self.kernel, {'facts': [fact, fact], 'negative_givens': [], 'extraction_status': 'complete'})
        kernel = deepcopy(self.kernel)
        kernel['statute_sha256']['events.pl'] = '0' * 64
        with self.assertRaises(ValueError):
            kernel_execution(kernel, {'facts': [], 'negative_givens': [], 'extraction_status': 'complete'})

    def test_model_strings_are_data_and_not_prolog_source(self):
        payload = 'name"). halt. %'
        self.assertEqual(json.loads(scalar(payload)), payload)
        with self.assertRaises(ValueError):
            fact_term({'predicate': 'halt', 'arguments': []}, GIVENS)
        with self.assertRaises(ValueError):
            fact_term({'predicate': 's151_b_applies', 'arguments': ['A', 'B']}, GIVENS)

    def test_real_failed_factual_records_are_rejected_by_generation_types(self):
        folder = ROOT / 'artifacts/legal_skill_evolution_native_observation_read_20261114/results'
        for path in folder.glob('*.json'):
            row = json.loads(path.read_text())
            kernel = next(k for k in self.bank if k['name'] == ('general_employer' if '6939fedab0' in row['source'] else 'dependent_basic_deduction_limit'))
            with self.assertRaises(jsonschema.ValidationError):
                jsonschema.validate(row['observation']['inputs'], input_schema(kernel))


if __name__ == '__main__':
    unittest.main()
