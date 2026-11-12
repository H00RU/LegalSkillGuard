"""Candidate source abstraction, partial-input proof and shared strong controls."""
from copy import deepcopy
import unittest

from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues
from legal_skill_guard.skill_evolution.source_schema import (SCHEMA, compile_schema, execute_schema,
    partial_conflicts, read_semantic_record, execute_text_policy)


def fixture():
    return {'kind': 'typed_rule', 'rationale': 'Synthetic source record for compiler verification only.',
        'scope_tasks': ['nda-5', 'nda-7'], 'read_question': 'Read the declared source facts.',
        'source_fields': [{'name': 'flag', 'type': 'boolean', 'question': 'Explicit flag?', 'domain': []},
                          {'name': 'other', 'type': 'boolean', 'question': 'Other flag?', 'domain': []}],
        'procedure': 'def apply(inputs, premises):\n    if premises["flag"]:\n        return {"answer": "Entailment"}\n    if premises["other"]:\n        return {"answer": "Contradiction"}\n    return {"answer": "NotMentioned"}\n', 'policy_text': None}


class SourceSchemaChecks(unittest.TestCase):
    def test_teacher_schema_is_strict_and_partial_execution_preserves_unknown(self):
        self.assertEqual(strict_output_schema_issues(SCHEMA), [])
        spec = compile_schema(fixture(), restricted=True)
        view = {'id': 'nda-5', 'public': {'question': 'Synthetic query'}}
        self.assertEqual(execute_schema(spec, {}, view, {'flag': True}), 'Entailment')
        with self.assertRaises(ValueError):execute_schema(spec, {}, view, {'flag': False})

    def test_raw_source_is_allowed_for_the_free_control_but_not_the_candidate(self):
        spec = fixture();spec['kind'] = 'raw_rule'
        spec['source_fields'] = [{'name': 'source', 'type': 'raw_spans', 'question': '', 'domain': []}]
        spec['procedure'] = 'def apply(inputs, premises):\n    return {"answer": "Entailment" if "synthetic" in premises["source"][0] else "NotMentioned"}\n'
        compile_schema(spec, restricted=False)
        with self.assertRaises(ValueError):compile_schema(spec, restricted=True)

    def test_source_vocabulary_is_checked_through_aliases_and_loops(self):
        spec = fixture()
        spec['source_fields'] = [{'name': 'roles', 'type': 'array', 'question': 'Source roles?', 'domain': ['role_a', 'role_b']}]
        spec['procedure'] = 'def apply(inputs, premises):\n    roles = premises["roles"]\n    found = False\n    for role in roles:\n        if role == "role_a":\n            found = True\n    return {"answer": "Entailment" if found else "NotMentioned"}\n'
        compile_schema(spec, restricted=True)
        spec['procedure'] = spec['procedure'].replace('role == "role_a"', 'role == "an exact old source phrase"')
        with self.assertRaisesRegex(ValueError, 'Undeclared source-dependent phrase'):compile_schema(spec, restricted=True)

    def test_compatible_unknown_is_not_a_distinguishing_value(self):
        a = {'source': 'a', 'query': 'q', 'target': 'Entailment', 'declared_fields': ['x', 'y'], 'known': {'x': True}}
        b = {'source': 'b', 'query': 'q', 'target': 'Contradiction', 'declared_fields': ['x', 'y'], 'known': {'x': True, 'y': False}}
        original = deepcopy([a, b]);w = partial_conflicts([a, b])
        self.assertEqual(len(w), 1)
        self.assertEqual([a, b], original)
        self.assertEqual(w[0]['left_unresolved'], ['y'])
        self.assertTrue(w[0]['completion_is_a_logical_witness_not_acquired_source_values'])
        b['known']['x'] = False
        self.assertEqual(partial_conflicts([a, b]), [])
        b['known']['x'] = True;b['query'] = 'different q'
        self.assertEqual(partial_conflicts([a, b]), [])

    def test_free_control_can_acquire_a_joint_text_policy(self):
        spec = fixture();spec.update(kind='text_policy', source_fields=[], procedure=None,
            read_question=None, policy_text='Synthetic learned policy, not a built-in legal rule.')
        compile_schema(spec, restricted=False)
        with self.assertRaises(ValueError):compile_schema(spec, restricted=True)

    def test_reader_omits_unknown_and_both_controls_show_one_source_ID_namespace(self):
        source = {'views': [{'id': t, 'public': {'source_text': 'Synthetic source.',
            'sentence_spans': [[0, 17]], 'question': 'A public query'}} for t in ('nda-5', 'nda-7')]}
        seen = []
        class Reader:
            def generate(self, *args, **kwargs):
                seen.append(kwargs)
                return {'flag': {'status': 'known', 'value': True, 'support_ids': [0]},
                        'other': {'status': 'unknown', 'value': None, 'support_ids': []}}, {'call_id': 'fixture'}
        values, event = read_semantic_record(Reader(), source, fixture())
        self.assertEqual(values, {'flag': True})
        self.assertEqual(event['unresolved_fields'], ['other'])
        self.assertNotIn('question', seen[0]['content'])
        self.assertNotIn('tasks', seen[0]['content'])
        self.assertFalse(any('public_sentence_id' in s for s in seen[0]['content']['source_spans']))
        policy = fixture();policy.update(kind='text_policy', source_fields=[], procedure=None, policy_text='Fixture policy')
        execute_text_policy(Reader(), source, policy)
        self.assertFalse(any('public_sentence_id' in s for s in seen[1]['content']['source_spans']))


if __name__ == '__main__':unittest.main()
