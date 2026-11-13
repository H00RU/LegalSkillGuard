"""Literal scope regression; these examples do not add empirical law tasks."""
import unittest
from legal_skill_guard.skill_evolution.query_scope import literal_query_arguments


class QueryScopeTests(unittest.TestCase):
    def test_actual_percentage_scope_does_not_read_asserted_value(self):
        r=literal_query_arguments('Under section 151(d)(3)(B), the applicable percentage for Alice for 2015 is equal to 22.')
        self.assertEqual(r['values'],{'year':2015,'subject':'Alice'})

    def test_actual_dependent_query_does_not_assert_dependency(self):
        r=literal_query_arguments('Alice can claim an exemption with Bob the dependent for 2015 under section 151(c).')
        self.assertEqual(r['values'],{'year':2015,'taxpayer':'Alice','individual':'Bob'})
        self.assertFalse(r['case_or_legal_propositions_inferred'])

    def test_actual_exemption_query_subject(self):
        r=literal_query_arguments("Under section 151(d)(2), Bob's exemption amount for the year 2015 is equal to $2000.")
        self.assertEqual(r['values'],{'year':2015,'subject':'Bob'})

    def test_qualifying_child_role_names_are_literal_only(self):
        r=literal_query_arguments('Under section 152(c)(1), Bob is a qualifying child of Alice for the year 2019.')
        self.assertEqual(r['values'],{'year':2019,'individual':'Bob','taxpayer':'Alice'})

    def test_ambiguous_year_is_not_selected(self):
        self.assertNotIn('year',literal_query_arguments('For 2015 or for 2016, is the claim true?')['values'])

    def test_existing_employment_binding_is_reused(self):
        r=literal_query_arguments('Section 3306(c)(5) applies to Alice employing Bob for the year 2017.')
        self.assertEqual(r['values'],{'year':2017,'employer':'Alice','employee':'Bob'})
