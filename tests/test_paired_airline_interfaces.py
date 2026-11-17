from copy import deepcopy
import json
from pathlib import Path
import unittest

import jsonschema

from legal_skill_guard.paired_interfaces.airline_interfaces import compile_plans, decode
from legal_skill_guard.paired_interfaces.graph_interface import validate
from legal_skill_guard.paired_interfaces.native_adapters import run_airline


class ProgramPortInterfaces(unittest.TestCase):
    def setUp(self):
        locked = json.loads(Path('artifacts/two_method_followthrough_20261116/pilot_lock.json').read_text())
        self.plans = compile_plans(locked['plans']['RuleArena_Airline'])
        texts = ['M is a Main Cabin passenger flying from Philadelphia to New York.',
                 '1. A bag: 30 x 20 x 10 inches, 53 lbs.',
                 '2. A bag: 31 x 20 x 10 inches, 54 lbs.', "M's ticket is $100."]
        self.units, cursor = [], 0
        for i, text in enumerate(texts):
            self.units.append({'id': i, 'start': cursor, 'end': cursor + len(text), 'text': text})
            cursor += len(text) + 1
        def scalar(value, unit):
            return {'value': value, 'status': 'stated', 'unit_id': unit, 'quote': texts[unit]}
        self.base = {'ticket_price': scalar(100, 3), 'cabin_class': scalar('Main Cabin', 0),
            'origin_city': scalar('Philadelphia', 0), 'destination_city': scalar('New York', 0),
            'inventory_complete': True, 'unresolved': []}
        self.bags = [{'unit_id': i + 1, 'quote': texts[i + 1],
                     **{name: {'value': value, 'status': 'stated'} for name, value in zip(
                         ('item_lengths', 'item_widths', 'item_heights', 'item_weights'), values)}}
                    for i, values in enumerate([(30, 20, 10, 53), (31, 20, 10, 54)])]

    def value(self, plan):
        value = deepcopy(self.base)
        bags = deepcopy(self.bags)
        if plan.get('weight_codec'):
            for bag in bags:
                weight = bag['item_weights']['value']
                bag['item_weights']['value'] = next(g['code'] for g in plan['weight_codec']['groups'] if weight in g['members'])
        if plan['name'] == 'columns':
            value.update(bag_unit_ids=[b['unit_id'] for b in bags], bag_quotes=[b['quote'] for b in bags])
            value.update({name: [b[name] for b in bags] for name in plan['port_binding']})
        else:
            value['bags'] = bags
        return value

    def test_three_generated_encodings_feed_the_same_real_frozen_program(self):
        answers = []
        for plan in self.plans:
            value = self.value(plan)
            jsonschema.validate(value, plan['schema'])
            graph, receipt = decode(plan, value, self.units)
            validate(graph, self.units)
            result = run_airline(graph, self.units, plan['fixed_library_sha256'])
            self.assertTrue(result['learned_native_main_path_executed'])
            answers.append(result['answer'])
        self.assertEqual(len(set(answers)), 1)
        self.assertEqual(len(self.plans), 3)

    def test_unknown_measurement_remains_unknown_at_the_native_boundary(self):
        plan = self.plans[2]
        value = self.value(plan)
        value['bags'][0]['item_weights'] = {'value': None, 'status': 'unknown'}
        jsonschema.validate(value, plan['schema'])
        graph, receipt = decode(plan, value, self.units)
        self.assertFalse(run_airline(graph, self.units, plan['fixed_library_sha256'])['handled'])

    def test_array_decoder_rejects_missing_item_without_truncation(self):
        value = self.value(self.plans[0])
        value['item_widths'].pop()
        with self.assertRaisesRegex(ValueError, 'unaligned'):
            decode(self.plans[0], value, self.units)

    def test_residual_record_wire_schema_rejects_an_unencoded_literal_weight(self):
        plan = self.plans[2]
        value = self.value(plan)
        value['bags'][0]['item_weights']['value'] = 53
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(value, plan['schema'])


if __name__ == '__main__':
    unittest.main()
