"""Source-pointer transport checks; fixtures do not add research data."""
from copy import deepcopy
import json
import unittest

import jsonschema

from legal_skill_guard.skill_evolution.unit_evidence import (
    TRANSPORT, answer_schema, context_batches, decode_answers, reading_messages)
from legal_skill_guard.skill_evolution.source_observations import (
    decode_visible_inputs, encode_source_observations)


OPS = [{'name': 'meaning', 'question': 'Which asserted meaning?',
        'choices': [{'name': 'first', 'meaning': 'First meaning'},
                    {'name': 'absent', 'meaning': 'Absent in the complete current source'}],
        'examples': []}]
UNITS = [{'id': 4, 'text': 'A “relation- ship” is mentioned.'},
         {'id': 9, 'text': 'A different passage.'}]
QUERIES = [{'id': 'q', 'operation': 'meaning', 'unit_ids': [4, 9]}]


def content(choice='first', ids=(4,)):
    return json.dumps({'answers': {'q': {'choice': choice, 'evidence_unit_ids': list(ids)}}})


class UnitEvidenceTests(unittest.TestCase):
    def test_context_splitting_preserves_every_complete_query_and_output_reserve(self):
        class TokenizerOnly:
            config = {'max_tokens': 20, 'context_tokens': 100}
            def tokenize(self, messages, *, thinking):
                current = json.loads(messages[1]['content'])['current_queries']
                return {'count': 30 * len(current)}
        queries = [{**QUERIES[0], 'id': 'q' + str(i)} for i in range(7)]
        checks = [];batches = context_batches(TokenizerOnly(), OPS, queries, UNITS, scope='window', checks=checks)
        self.assertEqual([q for batch, _, _ in batches for q in batch], queries)
        self.assertTrue(any(not row['fits'] for row in checks))
        self.assertTrue(all(row['input_tokens'] + 20 <= 100 for _, _, row in batches))
        for batch, prompt, _ in batches:
            actual = json.loads(prompt[1]['content'])['current_queries']
            self.assertEqual([q['unit_ids'] for q in actual], [q['unit_ids'] for q in batch])
            self.assertTrue(all(q['current_units'] == UNITS for q in actual))

    def test_one_oversized_query_is_never_truncated_or_dispatched(self):
        class TokenizerOnly:
            config = {'max_tokens': 20, 'context_tokens': 100}
            def tokenize(self, messages, *, thinking):return {'count': 81}
        with self.assertRaisesRegex(ValueError, 'without truncation'):
            context_batches(TokenizerOnly(), OPS, QUERIES, UNITS, scope='window', checks=[])

    def test_actual_text_retrieved_without_word_or_quote_normalization(self):
        raw, answers = decode_answers(OPS, QUERIES, UNITS, content(), scope='focus_last')
        answer = answers[0]
        self.assertEqual(raw['answers']['q']['evidence_unit_ids'], [4])
        self.assertEqual(answer['evidence'][0]['quote'], UNITS[0]['text'])
        self.assertEqual(answer['evidence_transport'], TRANSPORT)
        self.assertEqual(answer['evidence'][0]['quote_origin'], 'host_retrieved_model_selected_current_unit')
        self.assertFalse(answer['source_semantics_verified'])
        # The host cannot revise even an unsupported/mistaken model choice.
        self.assertEqual(answer['choice'], 'first')

    def test_missing_answers_wrong_choices_and_noncurrent_or_duplicate_units_rejected(self):
        for value in [content(ids=(100,)), content(choice='Entailment'),
                      '{"answers":{}}',
                      '{"answers":{"q":{"choice":"first","evidence_unit_ids":[4],"quote":"made up"}}}']:
            with self.subTest(value=value), self.assertRaises(jsonschema.ValidationError):
                decode_answers(OPS, QUERIES, UNITS, value, scope='window')
        with self.assertRaisesRegex(ValueError, 'Duplicate JSON'):
            decode_answers(OPS, QUERIES, UNITS,
                '{"answers":{"q":{"choice":"first","choice":"absent","evidence_unit_ids":[4]}}}', scope='window')

    def test_identical_evidence_ID_repetition_is_idempotent_with_raw_error_preserved(self):
        raw, answers = decode_answers(OPS, QUERIES, UNITS, content(ids=(4, 4, 9, 4)), scope='window')
        self.assertEqual(raw['answers']['q']['evidence_unit_ids'], [4, 4, 9, 4])
        answer = answers[0]
        self.assertEqual(answer['selected_evidence_unit_ids'], [4, 9])
        self.assertEqual(answer['raw_selected_evidence_unit_ids'], [4, 4, 9, 4])
        self.assertFalse(answer['raw_wire_uniqueItems_valid'])
        self.assertEqual(answer['choice'], 'first');self.assertFalse(answer['source_semantics_verified'])
        encoded = encode_source_observations('fixture', source_text=' '.join(u['text'] for u in UNITS),
            units=UNITS, source_output={'statements': [], 'complete': False, 'unresolved': []},
            operations=OPS, queries=QUERIES, answers=answers, scope='window')
        self.assertEqual(encoded['visible_inputs']['answers'], answers)
        changed = deepcopy(answers);changed[0]['selected_evidence_unit_ids'] = [4]
        with self.assertRaisesRegex(ValueError, 'canonical evidence set disagree'):
            encode_source_observations('fixture', source_text=' '.join(u['text'] for u in UNITS),
                units=UNITS, source_output={'statements': [], 'complete': False, 'unresolved': []},
                operations=OPS, queries=QUERIES, answers=changed, scope='window')

    def test_no_automatic_quote_protocol_fallback_or_positive_without_evidence(self):
        old = json.dumps({'answers': {'q': {'choice': 'first',
            'evidence': [{'unit_id': 4, 'quote': UNITS[0]['text']}]}}})
        with self.assertRaises(jsonschema.ValidationError):
            decode_answers(OPS, QUERIES, UNITS, old, scope='window')
        with self.assertRaisesRegex(ValueError, 'needs current evidence'):
            decode_answers(OPS, QUERIES, UNITS, content(ids=()), scope='window')
        _, unknown = decode_answers(OPS, QUERIES, UNITS, content('unknown', ()), scope='window')
        self.assertEqual(unknown[0]['choice'], 'unknown')

    def test_absence_requires_actual_complete_scope_and_explicit_acquired_choice(self):
        absence = {'meaning': ['absent']}
        _, answers = decode_answers(OPS, QUERIES, UNITS, content('absent', ()),
            scope='window', complete_source_absence_choices=absence)
        self.assertEqual(answers[0]['complete_source_evidence']['unit_ids'], [4, 9])
        for queries, scope, policy in [(QUERIES, 'focus_last', absence),
                ([{**QUERIES[0], 'unit_ids': [4]}], 'window', absence),
                (QUERIES, 'window', None)]:
            with self.subTest(scope=scope, policy=policy), self.assertRaises(ValueError):
                decode_answers(OPS, queries, UNITS, content('absent', ()), scope=scope,
                               complete_source_absence_choices=policy)

    def test_selection_provenance_survives_lossless_encoder_and_is_revalidated(self):
        _, answers = decode_answers(OPS, QUERIES, UNITS, content(), scope='focus_last')
        inputs = {'source_text': ' '.join(u['text'] for u in UNITS), 'units': UNITS,
            'source_output': {'statements': [], 'complete': False, 'unresolved': []},
            'operations': OPS, 'queries': QUERIES, 'answers': answers, 'scope': 'focus_last'}
        encoded = encode_source_observations('fixture', **inputs)
        self.assertEqual(encoded['visible_inputs'], decode_visible_inputs(encoded))
        self.assertEqual(encoded['visible_inputs']['answers'][0], answers[0])
        modified = deepcopy(inputs)
        modified['answers'][0]['evidence'][0]['quote'] = 'relation- ship'
        with self.assertRaisesRegex(ValueError, 'whole current unit'):
            encode_source_observations('fixture', **modified)
        modified = deepcopy(inputs)
        modified['answers'][0]['selected_evidence_unit_ids'] = [9]
        with self.assertRaisesRegex(ValueError, 'whole current unit'):
            encode_source_observations('fixture', **modified)

    def test_scope_examples_and_schema_describe_same_current_unit_protocol(self):
        prompt = reading_messages(OPS, QUERIES, UNITS, scope='focus_last')
        current = json.loads(prompt[1]['content'])['current_queries'][0]
        self.assertEqual(current['focus_unit_id'], 9)
        self.assertEqual(current['current_units'], UNITS)
        self.assertIn('evidence_unit_ids', prompt[0]['content'])
        schema = answer_schema(OPS, QUERIES)
        self.assertEqual(schema['properties']['answers']['properties']['q']['properties']
            ['evidence_unit_ids']['items']['enum'], [4, 9])
