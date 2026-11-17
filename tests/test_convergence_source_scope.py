import unittest
from experiments.convergence_source_audit import validate
from legal_skill_guard.paired_interfaces.source_context import enclosing_section,SourceContextUnavailable


class NewScopeTests(unittest.TestCase):
    def test_additional_native_headings_preserve_late_subclauses_and_old_parser(self):
        for heading in ('SECTION4.1.','Section 4.1.','4.1'):
            parent=heading+' Covenants.\nA shall act.\n4.1.1 Nested provision.\nLater exception.\n4.2 Next covenant.\n'
            with self.assertRaises(SourceContextUnavailable):enclosing_section(parent,'A shall act.')
            body,receipt=enclosing_section(parent,'A shall act.',structural_headers=True)
            self.assertIn('Later exception.',body);self.assertNotIn('4.2 Next',body)
            self.assertEqual(body,parent[slice(*receipt['parent_section_span'])])
            self.assertFalse(receipt['native_task_scope_complete'])

    def test_exact_quotes_do_not_approve_dangling_or_fabricated_exception_scope(self):
        text='A shall act. Except during a pandemic.'
        audit={'effects':[{'effect_id':'e','document_id':'d','operative_quote':'A shall act.','actor_quote':'A'}],
            'exceptions':[{'document_id':'d','condition_quote':'during a pandemic','attachment_quote':'Except during a pandemic.',
                'scope_options':[['missing_effect']],'scope_status':'explicit'}],
            'knowledge':{'document_id':'d','standard':'unresolved','evidence_quote':''}}
        got=validate(audit,{'d':text});self.assertFalse(got['grounding_checks_passed'])
        self.assertIn('dangling exception target',got['issues'])
        audit['exceptions'][0]['scope_options']=[['e']]
        got=validate(audit,{'d':text});self.assertTrue(got['grounding_checks_passed'])
        self.assertFalse(got['source_semantics_or_method_effect_certified_by_quote_contiguity'])


if __name__=='__main__':unittest.main()
