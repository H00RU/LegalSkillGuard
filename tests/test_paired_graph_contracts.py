from copy import deepcopy
import json
from pathlib import Path
import unittest

import jsonschema

from legal_skill_guard.paired_interfaces.graph_contracts import compile_weight_contract
from legal_skill_guard.paired_interfaces.numeric_ports import normalize_numeric_ports


class EncodingContractTests(unittest.TestCase):
    def setUp(self):
        lock = json.loads(Path('artifacts/two_method_followthrough_20261116/pilot_lock.json').read_text())
        self.original = lock['plans']['RuleArena_Airline'][2]
        self.corrected = compile_weight_contract(self.original)
        self.edge = {'predicate': 'weight', 'arguments': ['b'], 'value': self.original['weight_codec']['groups'][0]['code'],
                     'status': 'stated', 'unit_id': 0, 'quote': '8 lbs'}

    def test_grammar_enforces_exact_frozen_codebook_without_new_groups(self):
        schema = self.corrected['schema']['properties']['relations']['items']
        jsonschema.validate(self.edge, schema)
        for invalid in (8, '8', 'made_up_weight_class'):
            with self.subTest(value=invalid), self.assertRaises(jsonschema.ValidationError):
                jsonschema.validate({**self.edge, 'value': invalid}, schema)
        self.assertEqual(self.corrected['weight_codec'], self.original['weight_codec'])

    def test_unknown_and_negated_weights_do_not_become_positive_codes(self):
        schema = self.corrected['schema']['properties']['relations']['items']
        for status in ('unknown', 'unread', 'not_stated'):
            jsonschema.validate({**self.edge, 'status': status, 'value': None}, schema)
        jsonschema.validate({**self.edge, 'status': 'negated', 'value': 52}, schema)
        jsonschema.validate({**self.edge, 'predicate': 'length', 'value': '30'}, schema)

    def test_ordinary_candidates_and_original_asset_are_unchanged(self):
        before = deepcopy(self.original)
        compile_weight_contract(self.original)
        self.assertEqual(self.original, before)
        plain = {k: v for k, v in self.original.items() if k != 'weight_codec'}
        self.assertEqual(compile_weight_contract(plain), plain)


class NumericPortTests(unittest.TestCase):
    def test_only_stated_numeric_serializations_are_normalized(self):
        graph = {'nodes': [], 'relations': [
            {'predicate': 'length', 'arguments': ['b'], 'value': '30', 'status': 'stated'},
            {'predicate': 'weight', 'arguments': ['b'], 'value': 'bag_weight_lbs_group_2', 'status': 'stated'},
            {'predicate': 'amount', 'arguments': ['b'], 'value': None, 'status': 'unknown'},
            {'predicate': 'category', 'arguments': ['b'], 'value': '51', 'status': 'stated'},
            {'predicate': 'ticket_price', 'arguments': ['b'], 'value': '$400', 'status': 'stated'}],
            'scope_complete': False, 'unresolved': ['route not read']}
        value, receipt = normalize_numeric_ports(graph)
        self.assertEqual(value['relations'][0]['value'], 30)
        self.assertEqual(value['relations'][1:], graph['relations'][1:])
        self.assertEqual(value['unresolved'], graph['unresolved'])
        self.assertFalse(value['scope_complete'])
        self.assertEqual(len(receipt['changes']), 1)
        self.assertEqual(graph['relations'][0]['value'], '30')


if __name__ == '__main__':
    unittest.main()
