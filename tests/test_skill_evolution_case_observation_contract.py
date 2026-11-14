"""A correct kernel must not turn uncertain grounding into a selected answer."""
import unittest

from legal_skill_guard.skill_evolution.case_observation_contract import check_bindings, execute_alternatives


class CaseObservationContractTests(unittest.TestCase):
    def kernel(self):
        return {'program': "def apply(inputs, premises):\n    return {'handled': True, 'answer': 'Entailment' if inputs['relation'] in ('son', 'daughter', 'spouse') else 'Contradiction'}\n",
            'input_fields_json': '{"relation":{"type":"string"}}', 'scope': 'exact_clause'}

    def grounded(self, values):
        return {'bindings': [{'inputs': {'relation': x}, 'witnesses': [{'field': 'facts', 'quote': 'source relationship'}]} for x in values], 'unresolved': []}

    def test_unused_gender_can_remain_unresolved_when_correct_program_agrees(self):
        r = execute_alternatives(self.kernel(), self.grounded(['son', 'daughter']))
        self.assertTrue(r['handled']); self.assertEqual(r['answer'], 'Entailment')
        self.assertEqual(len(r['binding_executions']), 2)

    def test_disagreement_requires_grounding_refinement_not_answer_selection(self):
        r = execute_alternatives(self.kernel(), self.grounded(['son', 'father']))
        self.assertFalse(r['handled']); self.assertIsNone(r['answer'])
        self.assertEqual(r['answer_relevant_binding_differences'], ['relation'])

    def test_missing_or_failed_binding_does_not_become_false(self):
        for g in ({'bindings': [], 'unresolved': ['not read']},
                  {'bindings': [{'inputs': {}, 'witnesses': []}], 'unresolved': []}):
            r = execute_alternatives(self.kernel(), g)
            self.assertFalse(r['handled']); self.assertIsNone(r['answer'])

    def test_unrepresented_unresolved_observations_cannot_be_discarded(self):
        g = self.grounded(['son']); g['unresolved'] = ['another relevant relationship is unread']
        r = execute_alternatives(self.kernel(), g)
        self.assertFalse(r['handled']); self.assertIsNone(r['answer'])

    def test_statute_quote_cannot_support_case_grounding(self):
        with self.assertRaises(ValueError):
            check_bindings({'bindings': [{'inputs': {'relation': 'son'}, 'witnesses': [{'field': 'source_text', 'quote': 'son'}]}],
                'unresolved': []}, {'relation': {'type': 'string'}}, {'facts': 'actual case', 'question': 'query'})

    def test_false_local_subrule_cannot_refute_unimplemented_parent_branch(self):
        k = self.kernel(); k['scope'] = 'sufficient_positive_only'
        r = execute_alternatives(k, self.grounded(['father']))
        self.assertFalse(r['handled']); self.assertIsNone(r['answer'])
