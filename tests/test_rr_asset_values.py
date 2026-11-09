"""Exact fields and ordinary source-unit controls, not model accuracy tests."""
import unittest
from legal_skill_guard.rr.asset_values import decode_asset_values


class AssetValueTests(unittest.TestCase):
    def test_prices_are_read_exactly(self):
        text = 'A table costs $1,025.00. A chair costs $470.00.'
        d = decode_asset_values({'bindings': [{'asset_span': 'table', 'amount_span': '$1,025.00',
                                               'evidence_span': 'A table costs $1,025.00.'}]}, text)
        self.assertEqual(d['bindings'][0]['amount_decimal'], '1025.00')
        self.assertTrue(d['bindings'][0]['single_price_source_unit_control'])

    def test_other_asset_price_in_same_paragraph_is_not_a_correct_local_binding(self):
        text = 'A table costs $90. A chair costs $10.'
        d = decode_asset_values({'bindings': [{'asset_span': 'table', 'amount_span': '$10',
                                               'evidence_span': text}]}, text)
        self.assertFalse(d['bindings'][0]['single_price_source_unit_control'])
        self.assertFalse(d['relation_truth_proved_by_membership'])

    def test_absent_spans_and_duplicate_items_are_rejected(self):
        text = 'A table costs $90.'
        row = {'asset_span': 'table', 'amount_span': '$90', 'evidence_span': text}
        with self.assertRaises(ValueError):
            decode_asset_values({'bindings': [row, row]}, text)
        with self.assertRaises(ValueError):
            decode_asset_values({'bindings': [{**row, 'amount_span': '$99'}]}, text)

    def test_multiple_or_ambiguous_price_units_do_not_choose_a_favorable_occurrence(self):
        text = 'A chair costs $90. Another chair costs $10.'
        d = decode_asset_values({'bindings': [{'asset_span': 'chair', 'amount_span': '$10',
                                               'evidence_span': text}]}, text)
        self.assertIsNone(d['bindings'][0]['single_price_source_unit_control'])
        text = 'A table costs $90 and a chair costs $10.'
        d = decode_asset_values({'bindings': [{'asset_span': 'table', 'amount_span': '$90',
                                               'evidence_span': text}]}, text)
        self.assertIsNone(d['bindings'][0]['single_price_source_unit_control'])


if __name__ == '__main__':
    unittest.main()
