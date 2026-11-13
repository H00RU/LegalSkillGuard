import unittest
import jsonschema
from legal_skill_guard.skill_evolution.source_term_interface import term_schema,validate_value

SPEC={'constructors':[
    {'name':'holder','arguments':[],'sort':'Participant','meaning':'A holder.'},
    {'name':'advisors','arguments':['Participant'],'sort':'Participant','meaning':'Their advisers.'},
    {'name':'copies','arguments':[],'sort':'Information','meaning':'Copies.'}]}


class SourceTermInterfaceTests(unittest.TestCase):
    def test_preserve_nested_typed_terms_and_argument_order(self):
        term=['advisors',['holder']]
        self.assertEqual(validate_value(SPEC,'Participant',term),term)

    def test_bad_arity_and_cross_sort_argument_rejected(self):
        for term in [['advisors'],['advisors',['copies']],['holder',['holder']]]:
            with self.assertRaises(jsonschema.ValidationError):validate_value(SPEC,'Participant',term)


if __name__=='__main__':unittest.main()
