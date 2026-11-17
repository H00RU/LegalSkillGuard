"""A strong control can invoke the same F residual without fabricated ports."""
import unittest

from legal_skill_guard.paired_interfaces.control_answers import source_bundle
from legal_skill_guard.paired_interfaces.formal_tools import legal_tools


class FormalToolsTests(unittest.TestCase):
    def source(self, regime):
        public = {'original_input': 'Solved Reasoning Steps:\nThe Debtor may claim property exemptions under '
                  + regime + ' statutes.\nFacts:\nOne debtor owns a desk.'}
        return {'key': 'fixture', 'dataset': 'OpenExempt',
                'views': [{'id': view, 'public': public, 'answer_schema': {'type': 'object'}}
                          for view in ('EC', 'EV')]}

    def test_control_tool_preserves_unknowns_and_does_not_demand_irrelevant_count(self):
        source = self.source('Illinois')
        tools, assets = legal_tools(source, source_bundle(source))
        tool = tools['public_context_residual_legal_module']
        payload = {'view_id': 'EV', 'inputs': {'asset_descriptions': ['desk'], 'asset_values': [43],
                                             'asset_is_personal_nonbusiness_property': [True]}}
        result = tool['invoke'](payload)
        self.assertTrue(result['handled'], result)
        self.assertTrue(result['common_public_context_residual_consumer'])
        self.assertNotIn('number_of_debtors', assets['common_public_context_residual_programs']['EV']['input_fields'])
        payload['inputs']['asset_is_personal_nonbusiness_property'] = [None]
        self.assertFalse(tool['invoke'](payload)['handled'])

    def test_unsupported_legal_domain_does_not_become_an_empty_native_answer(self):
        source = self.source('Federal and Oregon')
        tools, _ = legal_tools(source, source_bundle(source))
        result = tools['public_context_residual_legal_module']['invoke']({'view_id': 'EC', 'inputs': {}})
        self.assertFalse(result['handled'])
        self.assertIsNone(result['answer'])


if __name__ == '__main__':
    unittest.main()
