"""Finite nominal string sorts at the actual relational-to-term boundary."""
from copy import deepcopy
import unittest

from legal_skill_guard.skill_evolution.scoped_grammar import constructors, term_sort


class ScalarSortTests(unittest.TestCase):
    def setUp(self):
        self.spec = {'constructors': [
            {'name': 'role', 'sort': 'Participant', 'arguments': ['recipient_role'], 'meaning': 'Declared role'},
            {'name': 'condition', 'sort': 'Condition', 'arguments': ['choice'], 'meaning': 'Declared condition'},
            {'name': 'norm', 'sort': 'Norm', 'arguments': ['Participant', 'Condition'], 'meaning': 'Fixture norm'}],
            'scalar_sorts': {'recipient_role': ['employees', 'contractors'],
                             'choice': ['need_to_know_required', 'written_confidentiality_required']}}

    def test_actual_failed_category_strings_keep_their_nominal_domains(self):
        schema = constructors(self.spec)
        self.assertEqual(term_sort(['norm', ['role', 'contractors'],
            ['condition', 'need_to_know_required']], schema), 'Norm')
        self.assertEqual(term_sort('contractors', schema), 'text')

    def test_wrong_domain_unbound_string_number_and_native_answer_still_fail(self):
        schema = constructors(self.spec)
        for value in ['need_to_know_required', 'unacquired_role', 4, 'Entailment']:
            with self.assertRaises(ValueError): term_sort(['role', value], schema)
        with self.assertRaises(ValueError): term_sort(['norm', 'contractors', ['condition', 'need_to_know_required']], schema)

    def test_undeclared_nominal_scalar_is_not_inferred_from_a_string(self):
        spec = deepcopy(self.spec); spec.pop('scalar_sorts')
        with self.assertRaises(ValueError): term_sort(['role', 'contractors'], constructors(spec))

    def test_scalar_declaration_cannot_erase_structural_types_or_allow_labels(self):
        for domains in [{'Participant': ['contractors']}, {'text': ['contractors']},
                        {'choice': ['Entailment']}, {'choice': ['x', 'x']}]:
            spec = deepcopy(self.spec); spec['scalar_sorts'] = domains
            with self.assertRaises(ValueError): constructors(spec)
