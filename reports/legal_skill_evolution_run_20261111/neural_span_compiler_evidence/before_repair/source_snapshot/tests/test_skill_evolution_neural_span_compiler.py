"""Regressions for actual global-field contamination and source bindings."""
from copy import deepcopy
import unittest

from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues
from legal_skill_guard.skill_evolution.neural_span_compiler import (
    bind_records, binding_schema, frames_from_rules)
from legal_skill_guard.skill_evolution.span_compiler import compile_annotations
from tests.test_skill_evolution_span_compiler import fixture


class NeuralSpanCompilerChecks(unittest.TestCase):
    def setup_asset(self):
        spec = fixture();materials = {s['source']: s['quote'] for s in spec['seeds']}
        rules = compile_annotations(spec, materials)
        return spec, frames_from_rules(spec, rules)

    def test_new_wording_preserves_current_local_bindings(self):
        spec, frames = self.setup_asset()
        text = 'Data about partners is private. Sender is allowed to give a red item to workers today.'
        quote = 'Sender is allowed to give a red item to workers today.'
        response = {'records': [{'frame_id': frames[0]['id'], 'quote': quote,
            'slots': [{'name': 'entities', 'quote': 'workers'}]}]}
        records, rejected = bind_records(spec, frames, text, response)
        self.assertFalse(rejected);self.assertEqual(records[0]['values']['entities'], ['entity_x'])
        a, b = records[0]['span'];self.assertEqual(text[a:b], quote)
        self.assertIs(records[0]['relation_semantics_verified'], False)
        self.assertEqual(strict_output_schema_issues(binding_schema(frames)), [])

    def test_unrelated_role_cannot_enter_an_operating_clause(self):
        spec, frames = self.setup_asset();text = 'Partners appear in a definition. Sender may pass red item to workers now.'
        response = {'records': [{'frame_id': frames[0]['id'],
            'quote': 'Sender may pass red item to workers now.',
            'slots': [{'name': 'entities', 'quote': 'partners'}]}]}
        records, rejected = bind_records(spec, frames, text, response)
        self.assertFalse(records);self.assertEqual(len(rejected), 1)

    def test_missing_duplicate_or_invented_fields_remain_rejected(self):
        spec, frames = self.setup_asset();quote = spec['seeds'][0]['quote']
        for slots in [[], [{'name': 'unknown_field', 'quote': 'workers'}],
                      [{'name': 'entities', 'quote': 'workers'}] * 2]:
            records, rejected = bind_records(spec, frames, quote,
                {'records': [{'frame_id': frames[0]['id'], 'quote': quote, 'slots': slots}]})
            self.assertFalse(records);self.assertEqual(len(rejected), 1)

    def test_unknown_local_role_remains_unresolved(self):
        spec, frames = self.setup_asset();quote = 'Sender may pass red item to visitors now.'
        records, rejected = bind_records(spec, frames, quote, {'records': [{
            'frame_id': frames[0]['id'], 'quote': quote,
            'slots': [{'name': 'entities', 'quote': 'visitors'}]}]})
        self.assertFalse(rejected);self.assertIsNone(records[0]['values']['entities'])
        self.assertFalse(records[0]['lexical']['entities']['complete'])

    def test_raw_actor_object_binding_uses_joint_unique_nonoverlap(self):
        spec, frames = self.setup_asset();frame = deepcopy(frames[0])
        frame['slots'] = [{'name': 'object', 'lexicon': None}, {'name': 'condition', 'lexicon': None}]
        quote = 'A object B object C'
        response = {'records': [{'frame_id': frame['id'], 'quote': quote,
            'slots': [{'name': 'object', 'quote': 'object'}, {'name': 'condition', 'quote': 'B object C'}]}]}
        records, rejected = bind_records(spec, [frame], quote, response)
        self.assertFalse(rejected);self.assertEqual(records[0]['values']['object'], 'object')
        response['records'][0]['slots'][1]['quote'] = 'C'
        records, rejected = bind_records(spec, [frame], quote, response)
        self.assertFalse(records);self.assertEqual(len(rejected), 1)


if __name__ == '__main__':unittest.main()
