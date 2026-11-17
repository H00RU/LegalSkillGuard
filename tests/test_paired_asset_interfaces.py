"""Frozen asset-port integration, missing bindings and absorbing uncertainty."""
from copy import deepcopy
import unittest

from legal_skill_guard.paired_interfaces import graph_interface as gi
from legal_skill_guard.paired_interfaces.asset_interfaces import compile_plans, consume, context_from_public, decode_inputs


class AssetInterfaceTests(unittest.TestCase):
    def plans(self, regime='Illinois'):
        return {plan['name']: plan for plan in compile_plans(gi.plans(), regime)}

    def record(self, plan, personal=True, status='stated'):
        cells = {'asset_descriptions': {'value': 'small desk', 'status': 'stated'},
                 'asset_values': {'value': 43, 'status': 'stated'},
                 'asset_is_personal_nonbusiness_property': {'value': personal, 'status': status}}
        return {'assets': [{'unit_id': 0, 'quote': 'one debtor owns a small desk worth $43 for personal use',
                            **{alias: cells[name] for name, alias in plan['field_aliases'].items()}}],
                'inventory_complete': True, 'unresolved': []}

    def units(self):
        return [{'id': 0, 'text': 'one debtor owns a small desk worth $43 for personal use'}]

    def test_residual_interface_omits_only_program_irrelevant_ports(self):
        plans = self.plans()
        local = plans['local_records']
        self.assertEqual(set(local['array_fields']), {'asset_descriptions', 'asset_values',
                                                      'asset_is_personal_nonbusiness_property'})
        self.assertNotIn('number_of_debtors', local['requested_fields'])
        self.assertIn('asset_is_personal_tangible_property', plans['records']['requested_fields'])
        self.assertIn('number_of_debtors', self.plans('Federal and Pennsylvania')['local_records']['requested_fields'])
        result = consume(local, self.record(local), self.units(), 'EV')
        self.assertTrue(result['handled'], result)
        self.assertTrue(result['paired_residual_consumer_executed'])
        self.assertFalse(result['fallback_executed'])

    def test_unknown_boolean_is_not_false_and_does_not_become_an_answer(self):
        plan = self.plans()['local_records']
        unknown = self.record(plan, None, 'unknown')
        projected = decode_inputs(plan, unknown, self.units())
        self.assertIsNone(projected['inputs']['asset_is_personal_nonbusiness_property'][0])
        self.assertEqual(projected['domains'], [{'path': ['asset_is_personal_nonbusiness_property', 0],
                                               'values': [False, True]}])
        self.assertFalse(consume(plan, unknown, self.units(), 'EV')['handled'])
        guessed = deepcopy(unknown)
        guessed['assets'][0][plan['field_aliases']['asset_is_personal_nonbusiness_property']]['value'] = False
        with self.assertRaisesRegex(ValueError, 'guessed'):
            decode_inputs(plan, guessed, self.units())

    def test_unaligned_or_duplicated_assets_and_non_source_anchors_reject(self):
        plan = self.plans()['local_records']
        value = self.record(plan)
        value['assets'].append(deepcopy(value['assets'][0]))
        with self.assertRaisesRegex(ValueError, 'indistinguishable'):
            decode_inputs(plan, value, self.units())
        value = self.record(plan)
        value['assets'][0]['quote'] = 'a different source'
        with self.assertRaisesRegex(ValueError, 'source anchor'):
            decode_inputs(plan, value, self.units())

    def test_public_out_of_domain_regime_is_preserved_and_cannot_compile_an_empty_answer(self):
        public = {'original_input': 'Solved Reasoning Steps:\nThe Debtor may claim property exemptions under Federal and Oregon statutes.\nFacts:\nExample facts.'}
        context = context_from_public(public)
        self.assertEqual(context['governing_regime'], 'Federal and Oregon')
        self.assertFalse(context['supported_by_frozen_legal_program'])
        with self.assertRaisesRegex(ValueError, 'outside'):
            compile_plans(gi.plans(), context['governing_regime'])

    def test_full_columns_keep_irrelevant_unknowns_and_agree_with_generated_D(self):
        plans = self.plans()
        columns = plans['columns']
        value = {'asset_unit_ids': [0], 'asset_quotes': [self.units()[0]['text']],
                 'inventory_complete': True, 'unresolved': [],
                 'number_of_debtors': {'value': None, 'status': 'unread', 'unit_id': 0,
                                       'quote': self.units()[0]['text']}}
        for field in columns['array_fields']:
            data = ('small desk' if field == 'asset_descriptions' else 43 if field == 'asset_values'
                    else True if field == 'asset_is_personal_nonbusiness_property' else None)
            value[field] = [{'value': data, 'status': 'stated' if data is not None else 'unknown'}]
        projected = decode_inputs(columns, value, self.units())
        self.assertIsNone(projected['inputs']['number_of_debtors'])
        self.assertIsNone(projected['inputs']['asset_is_personal_tangible_property'][0])
        baseline = consume(columns, value, self.units(), 'EV')
        local = plans['local_records']
        paired = consume(local, self.record(local), self.units(), 'EV')
        self.assertTrue(baseline['handled'], baseline)
        self.assertEqual(baseline['answer'], paired['answer'])
        value['asset_values'].append({'value': 44, 'status': 'stated'})
        with self.assertRaisesRegex(ValueError, 'misaligned'):
            decode_inputs(columns, value, self.units())


if __name__ == '__main__':
    unittest.main()
