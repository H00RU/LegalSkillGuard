"""Program-guided factual reads must preserve unsupported and unknown outcomes."""
import json
from pathlib import Path
import unittest

from legal_skill_guard.skill_evolution.binding_refinement import compile_observation_plan, consume_factual_observation


class BindingRefinementTests(unittest.TestCase):
    def kernel(self):
        # Actual unchanged family program, not a synthetic legal training item.
        path = Path(__file__).resolve().parents[1] / 'reports/legal_skill_evolution_run_20261111/correct_skill_execution_20261114/verified_source_frame_error.json'
        record = json.loads(path.read_text())
        return {'program': record['same_legal_procedure'],
            'premises': {'excluded_employer_relationships': ['son', 'daughter', 'spouse']},
            'scope': 'exact_clause'}

    def bindings(self, relationships):
        return [{'inputs': {'service_performed_in_employ': True,
            'employer_relationship_to_employee': rel}} for rel in relationships]

    def observation(self, identity='relationship', cost=1):
        return {'id': identity, 'declared_cost': cost,
            'projection_program': "def apply(inputs, premises):\n    return {'observation': inputs['employer_relationship_to_employee']}\n"}

    def test_actual_child_abstraction_needs_no_gender_read(self):
        p = compile_observation_plan(self.kernel(), self.bindings(['son', 'daughter']), [self.observation()])
        self.assertEqual(p['tree']['kind'], 'answer')
        self.assertEqual(p['tree']['answer'], 'Entailment')
        self.assertEqual(p['tree']['worst_case_declared_cost'], 0)

    def test_disagreement_selects_a_factual_read_without_selecting_answer(self):
        p = compile_observation_plan(self.kernel(), self.bindings(['son', 'father']),
            [self.observation('expensive', 4), self.observation('cheap', 1)])
        self.assertEqual(p['tree']['observation_id'], 'cheap')
        self.assertEqual(p['tree']['worst_case_declared_cost'], 1)
        child = consume_factual_observation(p['tree'], 'cheap', 'father',
            [{'field': 'facts', 'quote': 'father'}], {'facts': 'The observed relation is father.'})
        self.assertEqual(child['answer'], 'Contradiction')

    def test_unmodeled_response_does_not_drop_an_inconvenient_binding(self):
        p = compile_observation_plan(self.kernel(), self.bindings(['son', 'father']), [self.observation()])
        r = consume_factual_observation(p['tree'], 'relationship', 'mother',
            [{'field': 'facts', 'quote': 'mother'}], {'facts': 'The observed relation is mother.'})
        self.assertEqual(r['kind'], 'unresolved')
        self.assertEqual(r['remaining_bindings'], [0, 1])
        self.assertTrue(r['requires_contract_update'])

    def test_uncovered_parent_branch_stays_unresolved(self):
        k = self.kernel(); k['scope'] = 'sufficient_positive_only'
        p = compile_observation_plan(k, self.bindings(['son', 'father']), [self.observation()])
        self.assertEqual(p['tree']['kind'], 'observe')
        negative = consume_factual_observation(p['tree'], 'relationship', 'father',
            [{'field': 'facts', 'quote': 'father'}], {'facts': 'father'})
        self.assertEqual(negative['kind'], 'unresolved')
        self.assertIsNone(negative['answer'])
        positive = consume_factual_observation(p['tree'], 'relationship', 'son',
            [{'field': 'facts', 'quote': 'son'}], {'facts': 'son'})
        self.assertEqual(positive['kind'], 'answer')
        self.assertEqual(positive['answer'], 'Entailment')

    def test_empty_coverage_has_no_default_answer(self):
        p = compile_observation_plan(self.kernel(), [], [])
        self.assertEqual(p['tree']['kind'], 'unresolved')
        self.assertIsNone(p['tree']['answer'])

    def test_native_answer_cannot_be_used_as_the_factual_projection(self):
        observation = self.observation()
        observation['projection_program'] = "def apply(inputs, premises):\n    return {'observation': 'Entailment'}\n"
        with self.assertRaises(ValueError):
            compile_observation_plan(self.kernel(), self.bindings(['son', 'father']), [observation])


if __name__ == '__main__':
    unittest.main()
