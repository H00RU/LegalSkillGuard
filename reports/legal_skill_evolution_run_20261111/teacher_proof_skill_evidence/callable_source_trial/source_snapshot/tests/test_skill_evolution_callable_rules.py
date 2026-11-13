"""Host-interface regressions, not empirical legal method evidence."""
from copy import deepcopy
import unittest

from legal_skill_guard.skill_evolution.callable_rules import (
    compile_library, evaluate, plan, query_frame)


class CallableRuleTests(unittest.TestCase):
    def setUp(self):
        self.material = {'source_text': 'Interface fixture: return the observed property.'}
        self.value = {'program': '''def property_value(facts):
    return {'value': facts.get('observed'),
            'used_units': ['observed_property'], 'open_dependencies': []}

def apply(inputs, premises):
    return property_value(inputs['facts'])
''', 'units': [{'id': 'observed_property', 'clause': '63(c)(6)(A)',
            'kind': 'predicate', 'function': 'property_value', 'source_field': 'source_text',
            'quote': self.material['source_text'],
            'fields': [{'name': 'observed', 'type': 'boolean', 'question': 'What observed property is given?'}]}]}
        self.library = compile_library(self.value, self.material)
        self.question = 'Section 63(c)(6)(A) applies to Alice for 2017.'

    def test_actual_applies_word_reaches_source_head(self):
        p = plan(self.library, self.question, self.material)
        self.assertTrue(p['supported'])
        self.assertEqual(evaluate(self.library, p, {'observed': True})['answer'], 'Entailment')

    def test_unavailable_case_value_stays_unknown(self):
        p = plan(self.library, self.question, self.material)
        self.assertEqual(evaluate(self.library, p, {})['answer'], 'unknown')

    def test_unknown_head_never_reuses_an_ancestor_or_different_clause(self):
        p = plan(self.library, 'Section 63(c)(6) applies to Alice.', self.material)
        self.assertFalse(p['supported'])
        self.assertEqual(evaluate(self.library, p, {})['answer'], 'unknown')

    def test_source_change_is_rejected(self):
        with self.assertRaises(ValueError):
            plan(self.library, self.question, {'source_text': 'Different source.'})

    def test_duplicate_source_head_is_not_silently_selected(self):
        v = deepcopy(self.value); u = deepcopy(v['units'][0]); u['id'] = 'another'; v['units'].append(u)
        with self.assertRaises(ValueError): compile_library(v, self.material)

    def test_quantity_comparison_occurs_outside_learned_legal_program(self):
        v = deepcopy(self.value); v['units'][0].update(clause='63(c)(3)', kind='quantity')
        v['units'][0]['fields'][0]['type'] = 'number'
        lib = compile_library(v, self.material)
        p = plan(lib, "Under section 63(c)(3), Alice's additional standard deduction is equal to $1200.", self.material)
        self.assertEqual(evaluate(lib, p, {'observed': 600+600})['answer'], 'Entailment')
        self.assertEqual(evaluate(lib, p, {'observed': 600})['answer'], 'Contradiction')
        self.assertEqual(query_frame('Under section 151(d)(3)(B), the applicable percentage is 2%.')['claim'], 2)

    def test_native_question_and_claim_are_unavailable_to_rule_code(self):
        v = deepcopy(self.value)
        v['program'] = "def property_value(facts):\n    return {'value':facts.get('question'),'used_units':['observed_property'],'open_dependencies':[]}\n\ndef apply(inputs,premises):\n    return property_value(inputs['facts'])\n"
        lib = compile_library(v, self.material)
        self.assertEqual(evaluate(lib, plan(lib,self.question,self.material), {})['answer'], 'unknown')

    def test_declared_function_does_not_need_duplicate_teacher_dispatch(self):
        v = deepcopy(self.value)
        v['program'] = v['program'].replace("return property_value(inputs['facts'])", "return None")
        lib = compile_library(v, self.material)
        self.assertEqual(evaluate(lib, plan(lib,self.question,self.material), {'observed': True})['answer'], 'Entailment')

    def test_unadorned_native_percentage_quantity(self):
        p = query_frame('Under section 151(d)(3)(B), the applicable percentage for Alice for 2015 is equal to 22.')
        self.assertEqual(p['kind'], 'quantity')
        self.assertEqual(p['claim'], 22)

    def test_native_claim_exemption_is_predicate(self):
        self.assertEqual(query_frame('Alice can claim an exemption with Bob the dependent for 2015 under section 151(c).')['kind'], 'predicate')

    def test_quantity_is_not_converted_to_applicability(self):
        v = deepcopy(self.value);v['units'][0]['kind'] = 'quantity'
        lib = compile_library(v,self.material)
        self.assertFalse(plan(lib,self.question,self.material)['supported'])

    def test_multiple_citations_are_unresolved(self):
        self.assertIsNone(query_frame('Section 63(c)(6)(A) and section 151(b) apply to Alice.'))


if __name__ == '__main__': unittest.main()
