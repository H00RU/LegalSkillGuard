import copy
import json

import unittest
from contextlib import contextmanager

@contextmanager
def raises_value(match=None):
    with unittest.TestCase().assertRaisesRegex(ValueError, match or ".*"):
        yield

from legal_skill_guard.skill_evolution.semantic_operations import (
    batches, finish, ground_answers, messages, prepare_queries, read_semantics,
    validate_operations)


OPS = [{'name': 'operative', 'question': 'Is the action an operative duty?',
        'choices': [{'name': 'duty', 'meaning': 'The stated action is required.'},
                    {'name': 'mention', 'meaning': 'It is only mentioned.'}],
        'examples': [{'source': 'TRAIN:a', 'quote': 'shall return', 'choice': 'duty'}]}]
UNITS = [{'id': 7, 'text': 'The recipient shall return the material.'},
         {'id': 19, 'text': 'Return does not end confidentiality. Return is mentioned.'}]
QUERIES = [{'id': 'q', 'operation': 'operative', 'unit_ids': [7]}]
VALUE = {'answers': [{'id': 'q', 'choice': 'duty',
                     'evidence': [{'unit_id': 7, 'quote': 'shall return'}]}]}
PROGRAM = '''def apply(inputs, premises):
    if inputs['phase'] == 'plan':
        return {'queries': [{'id': 'q', 'operation': 'operative', 'unit_ids': [7]}]}
    a = inputs['semantic_answers'][0]
    return {'observed': a['choice'], 'unknown_is_false': False}
'''


def test_real_pure_planner_model_answer_finisher_boundary():
    validate_operations(OPS, {'TRAIN:a': 'The recipient shall return material.'})
    plan = prepare_queries(PROGRAM, OPS, '', UNITS)
    answer = ground_answers(OPS, plan, UNITS, VALUE)
    assert finish(PROGRAM, '', UNITS, answer) == {'observed': 'duty', 'unknown_is_false': False}
    assert answer[0]['evidence'][0]['unit_occurrences'] == [[14, 26]]
    assert answer[0]['source_semantics_verified'] is False


def test_acquisition_examples_are_grounded_and_not_extra_sources(change):
    ops = copy.deepcopy(OPS)
    if change == 'duplicate': ops.append(ops[0])
    else: ops[0]['examples'][0][change] = 'not present'
    with raises_value():
        validate_operations(ops, {'TRAIN:a': 'shall return'})


def test_responses_cannot_change_identity_scope_or_supply_missing_answers(change):
    value = copy.deepcopy(VALUE)
    a = value['answers'][0]
    if change == 'missing': value['answers'] = []
    elif change == 'extra': value['answers'].append({**a, 'id': 'other'})
    elif change == 'duplicate': value['answers'].append(a)
    elif change == 'outside': a['evidence'][0]['unit_id'] = 19
    elif change == 'false_quote': a['evidence'][0]['quote'] = 'may retain'
    elif change == 'choice': a['choice'] = 'not_acquired'
    elif change == 'no_proof': a['evidence'] = []
    with raises_value(): ground_answers(OPS, QUERIES, UNITS, value)


def test_unknown_is_preserved_and_duplicate_phrase_occurrences_are_not_guessed():
    unknown = {'answers': [{'id': 'q', 'choice': 'unknown', 'evidence': []}]}
    assert ground_answers(OPS, QUERIES, UNITS, unknown)[0]['choice'] == 'unknown'
    q = [{**QUERIES[0], 'unit_ids': [19]}]
    v = {'answers': [{'id': 'q', 'choice': 'mention',
                     'evidence': [{'unit_id': 19, 'quote': 'Return'}]}]}
    assert len(ground_answers(OPS, q, UNITS, v)[0]['evidence'][0]['unit_occurrences']) == 2


def test_examples_ablation_preserves_meanings_queries_and_current_windows():
    full = json.loads(messages(OPS, QUERIES, UNITS)[1]['content'])
    no_examples = json.loads(messages(OPS, QUERIES, UNITS, examples=False)[1]['content'])
    assert full['current_queries'] == no_examples['current_queries']
    no_examples['operations'][0]['examples'] = full['operations'][0]['examples']
    assert full == no_examples


def test_truncation_does_not_retry_or_implicitly_execute_later_batches():
    class Client:
        calls = 0
        def generate(self, *args, **kwargs):
            self.calls += 1
            assert kwargs['thinking'] is False
            return {'finish_reason': 'length', 'content': '{'}
    client = Client()
    queries = [{**QUERIES[0], 'id': str(i)} for i in range(13)]
    with raises_value(match='Incomplete'):
        read_semantics(client, 'run:source', 'TRAIN:a', OPS, queries, UNITS)
    assert client.calls == 1
    assert list(map(len, batches(queries))) == [12, 1]


class SemanticOperationTests(unittest.TestCase):
    def test_explicit_complete_source_absence_preserves_actual_reading(self):
        ops = copy.deepcopy(OPS)
        ops[0]['choices'].append({'name': 'absent', 'meaning':
            'After examining the complete source, the specified operative duty is absent.'})
        queries = [{**QUERIES[0], 'unit_ids': [7, 19]}]
        raw = {'answers': [{'id': 'q', 'choice': 'absent', 'evidence': []}]}
        answer = ground_answers(ops, queries, UNITS, raw, scope='window',
            complete_source_absence_choices={'operative': ['absent']})[0]
        self.assertEqual(answer['choice'], 'absent')
        self.assertEqual(answer['evidence'], [])
        self.assertEqual(answer['complete_source_evidence']['unit_ids'], [7, 19])
        self.assertFalse(answer['source_semantics_verified'])
        self.assertEqual(raw['answers'][0], {'id': 'q', 'choice': 'absent', 'evidence': []})

    def test_absence_policy_cannot_make_unknown_or_partial_reads_negative(self):
        ops = copy.deepcopy(OPS)
        ops[0]['choices'].append({'name': 'absent', 'meaning': 'Absent in the complete source.'})
        policy = {'operative': ['absent']}
        full = [{**QUERIES[0], 'unit_ids': [7, 19]}]
        raw = {'answers': [{'id': 'q', 'choice': 'absent', 'evidence': []}]}
        for queries, scope in [(QUERIES, 'window'), (full, 'focus_last'), (full, None)]:
            with self.subTest(scope=scope, queries=queries), self.assertRaisesRegex(ValueError, 'complete current source'):
                ground_answers(ops, queries, UNITS, raw, scope=scope,
                    complete_source_absence_choices=policy)
        unknown = {'answers': [{'id': 'q', 'choice': 'unknown', 'evidence': []}]}
        answer = ground_answers(ops, full, UNITS, unknown, scope='window',
            complete_source_absence_choices=policy)[0]
        self.assertEqual(answer['choice'], 'unknown')
        self.assertNotIn('complete_source_evidence', answer)
        for choice in ['duty', 'mention']:
            with self.subTest(choice=choice), self.assertRaisesRegex(ValueError, 'needs current evidence'):
                ground_answers(ops, full, UNITS,
                    {'answers': [{'id': 'q', 'choice': choice, 'evidence': []}]},
                    scope='window', complete_source_absence_choices=policy)

    def test_source_absence_policy_rejects_undeclared_choices_and_false_quotes(self):
        raw = {'answers': [{'id': 'q', 'choice': 'duty', 'evidence': []}]}
        with self.assertRaisesRegex(ValueError, 'actual acquired choices'):
            ground_answers(OPS, QUERIES, UNITS, raw, scope='window',
                complete_source_absence_choices={'operative': ['undeclared']})
        ops = copy.deepcopy(OPS)
        ops[0]['choices'].append({'name': 'absent', 'meaning': 'Absent in the complete source.'})
        with self.assertRaisesRegex(ValueError, 'Nonverbatim'):
            ground_answers(ops, [{**QUERIES[0], 'unit_ids': [7, 19]}], UNITS,
                {'answers': [{'id': 'q', 'choice': 'absent',
                    'evidence': [{'unit_id': 7, 'quote': 'shall not return'}]}]},
                scope='window', complete_source_absence_choices={'operative': ['absent']})

    def test_real_typographic_quote_failure_has_unique_verbatim_recovery(self):
        # Minimized from the saved e7b scout response. Its legal choice is
        # untouched; only the two quotation-mark glyphs differ from the source.
        text = '(a) The term “Confidential Information” shall include all information.'
        raw_quote = 'The term "Confidential Information" shall include all information.'
        units = [{'id': 24, 'text': text}]
        queries = [{**QUERIES[0], 'unit_ids': [24]}]
        value = {'answers': [{'id': 'q', 'choice': 'duty',
            'evidence': [{'unit_id': 24, 'quote': raw_quote}]}]}
        grounded = ground_answers(OPS, queries, units, value)[0]
        self.assertEqual(grounded['choice'], 'duty')
        self.assertFalse(grounded['source_semantics_verified'])
        witness = grounded['evidence'][0]
        self.assertEqual(witness['raw_quote'], raw_quote)
        self.assertEqual(witness['quote'], text[4:])
        self.assertEqual(witness['unit_occurrences'], [[4, len(text)]])
        self.assertEqual(value['answers'][0]['evidence'][0]['quote'], raw_quote)

    def test_typographic_recovery_rejects_ambiguous_spans_and_word_changes(self):
        text = 'The “recipient” shall return material.'
        for current, quote in [
            (text + ' ' + text, 'The "recipient" shall return material.'),
            (text, 'The "recipient" shall not return material.'),
            (text, 'The "Recipient" shall return material.'),
        ]:
            with self.subTest(quote=quote, current=current), self.assertRaisesRegex(ValueError, 'Nonverbatim'):
                ground_answers(OPS, QUERIES, [{'id': 7, 'text': current}],
                    {'answers': [{'id': 'q', 'choice': 'duty',
                        'evidence': [{'unit_id': 7, 'quote': quote}]}]})

    def test_pure_boundary(self): test_real_pure_planner_model_answer_finisher_boundary()
    def test_acquisition_grounding(self):
        for change in ['source', 'quote', 'choice', 'duplicate']:
            with self.subTest(change=change): test_acquisition_examples_are_grounded_and_not_extra_sources(change)
    def test_response_grounding(self):
        for change in ['missing', 'extra', 'duplicate', 'outside', 'false_quote', 'choice', 'no_proof']:
            with self.subTest(change=change): test_responses_cannot_change_identity_scope_or_supply_missing_answers(change)
    def test_unknown_and_occurrences(self): test_unknown_is_preserved_and_duplicate_phrase_occurrences_are_not_guessed()
    def test_fair_ablation(self): test_examples_ablation_preserves_meanings_queries_and_current_windows()
    def test_no_retry(self): test_truncation_does_not_retry_or_implicitly_execute_later_batches()
