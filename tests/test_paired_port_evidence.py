from copy import deepcopy
import unittest

from legal_skill_guard.paired_interfaces.port_evidence import bind_port_evidence


class PortEvidenceBinding(unittest.TestCase):
    def value(self):
        return {**{n: {'value': None, 'status': 'unknown', 'unit_id': 0, 'quote': 'intro'}
                   for n in ('ticket_price', 'cabin_class', 'origin_city', 'destination_city')},
                'bags': [{'unit_id': 0, 'quote': '8 lbs', 'item_weights': {
                    'status': 'stated', 'value': 'wrong_but_unchanged_code'}}],
                'inventory_complete': False, 'unresolved': ['route unknown']}

    def test_unique_quote_rebinds_only_its_pointer(self):
        value = self.value()
        fixed, receipt = bind_port_evidence({'name': 'records'}, value,
            [{'id': 0, 'text': 'intro'}, {'id': 1, 'text': 'a bag: 8 lbs'}])
        self.assertEqual(fixed['bags'][0]['unit_id'], 1)
        self.assertEqual(fixed['bags'][0]['item_weights'], value['bags'][0]['item_weights'])
        self.assertEqual(fixed['unresolved'], value['unresolved'])
        self.assertFalse(fixed['inventory_complete'])
        self.assertEqual(value['bags'][0]['unit_id'], 0)
        self.assertEqual(len(receipt['bindings']), 1)

    def test_ambiguous_or_invented_quote_cannot_pick_a_favorable_source(self):
        for units in ([{'id': 0, 'text': 'intro'}, {'id': 1, 'text': '8 lbs'}, {'id': 2, 'text': '8 lbs'}],
                      [{'id': 0, 'text': 'intro'}, {'id': 1, 'text': '9 pounds'}]):
            with self.subTest(units=units), self.assertRaises(ValueError):
                bind_port_evidence({'name': 'records'}, self.value(), units)


if __name__ == '__main__':
    unittest.main()
