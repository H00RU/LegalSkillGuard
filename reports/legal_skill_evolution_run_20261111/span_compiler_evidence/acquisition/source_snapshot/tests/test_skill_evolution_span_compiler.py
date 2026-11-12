"""Source alignment, typed unknowns, guarded induction and a capable control."""
from copy import deepcopy
import unittest

from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues
from legal_skill_guard.skill_evolution.span_compiler import (SCHEMA, compile_annotations,
    parse_source, merge_rules, learn_grammar, locate, execute, validate_procedure)


def fixture():
    return {'kind': 'compiler', 'rationale': 'Synthetic transducer verification only.',
        'protected_tokens': ['not'], 'glue_words': ['and'],
        'lexicons': [{'name': 'entities', 'entries': [
            {'symbol': 'entity_x', 'forms': ['workers']},
            {'symbol': 'entity_y', 'forms': ['partners']}]}],
        'seeds': [{'source': 'a', 'quote': 'Sender may pass red item to workers now.',
            'kind': 'sample_relation', 'slots': [{'name': 'entities', 'quote': 'workers', 'lexicon': 'entities'}],
            'constants': [{'name': 'action', 'value': 'sample_transfer'}]},
            {'source': 'b', 'quote': 'Sender may pass blue item to partners now.',
            'kind': 'sample_relation', 'slots': [{'name': 'entities', 'quote': 'partners', 'lexicon': 'entities'}],
            'constants': [{'name': 'action', 'value': 'sample_transfer'}]}],
        'procedure': 'def apply(inputs, premises):\n    return {"handled": False, "answer": "NotMentioned", "used_records": []}\n',
        'policy_text': None}


class SpanCompilerChecks(unittest.TestCase):
    def test_strict_schema_and_only_unambiguous_verbatim_word_alignment(self):
        self.assertEqual(strict_output_schema_issues(SCHEMA), [])
        self.assertEqual(locate('A   blue\nunit.', 'A blue unit.'), (0, 14))
        with self.assertRaises(ValueError):locate('A unit. A unit.', 'A unit.')
        with self.assertRaises(ValueError):locate('A unit.', 'a unit.')
        with self.assertRaises(ValueError):locate('A unit.', 'A other unit.')

    def test_context_stays_attached_and_new_bindings_are_real_source_substrings(self):
        spec = fixture();materials = {'a': spec['seeds'][0]['quote'], 'b': spec['seeds'][1]['quote']}
        rules = compile_annotations(spec, materials)
        text = 'Sender may pass red item to workers and partners now.'
        rows = parse_source(spec, rules, text)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['values']['entities'], ['entity_x', 'entity_y'])
        self.assertTrue(rows[0]['lexical']['entities']['complete'])
        start, end = rows[0]['span'];self.assertEqual(text[start:end], text)
        self.assertEqual(parse_source(spec, rules, 'A red item contains data about workers and partners.'), [])

    def test_unrecognized_roles_remain_unresolved_instead_of_false_or_empty(self):
        spec = fixture();rules = compile_annotations(spec, {'a': spec['seeds'][0]['quote'], 'b': spec['seeds'][1]['quote']})
        rows = parse_source(spec, rules, 'Sender may pass red item to visitors now.')
        self.assertIsNone(rows[0]['values']['entities'])
        self.assertFalse(rows[0]['lexical']['entities']['complete'])
        self.assertEqual(rows[0]['lexical']['entities']['unresolved_surface'], ['visitors'])

    def test_native_feedback_blocks_a_bad_generalization_and_unguided_ablation_does_not(self):
        spec = fixture();rules = compile_annotations(spec, {'a': spec['seeds'][0]['quote'], 'b': spec['seeds'][1]['quote']})
        def score(grammar):return {'synthetic_negative': 0 if any(None in p for r in grammar for p in r['literals']) else 1}
        protected, log = learn_grammar(spec, rules, score, native_feedback=True)
        unguided, unguided_log = learn_grammar(spec, rules, score, native_feedback=False)
        self.assertEqual(len(protected), 2);self.assertFalse(log[0]['accepted'])
        self.assertEqual(len(unguided), 1);self.assertTrue(unguided_log[0]['accepted'])
        rows = parse_source(spec, unguided, 'Sender may pass green item to workers now.')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['values']['entities'], ['entity_x'])

    def test_polarity_and_literal_numeric_constants_cannot_be_erased_by_merge(self):
        spec = fixture();rules = compile_annotations(spec, {'a': spec['seeds'][0]['quote'], 'b': spec['seeds'][1]['quote']})
        bad = deepcopy(rules[1]);bad['literals'][0].insert(1, 'not')
        self.assertIsNone(merge_rules(rules[0], bad, {'not'}))
        a, b = deepcopy(rules[0]), deepcopy(rules[1]);a['literals'][0].append('12');b['literals'][0].append('24')
        self.assertIsNone(merge_rules(a, b, set()))

    def test_free_control_can_use_regex_and_text_operations_without_effectful_calls(self):
        code = 'def apply(inputs, premises):\n    text = premises["source_text"].lower()\n    found = re.search(r"red\\s+unit", text)\n    return {"handled": bool(found), "answer": "Entailment", "used_records": []}\n'
        self.assertTrue(execute(code, {}, {'source_text': 'RED unit'})['handled'])
        with self.assertRaises(ValueError):validate_procedure('def apply(inputs, premises):\n    return re.__dict__\n')
        with self.assertRaises(ValueError):validate_procedure('def apply(inputs, premises):\n    return open("file")\n')
        with self.assertRaises(ValueError):execute(fixture()['procedure'].replace('False', 'True'), {}, {'records': []})


if __name__ == '__main__':unittest.main()
