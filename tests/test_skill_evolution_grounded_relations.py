"""Actual grounding failures: absent classes, wrong scope and ambiguity."""
from copy import deepcopy
import unittest

import jsonschema

from legal_skill_guard.skill_evolution.grounded_relations import (
    role_mentions, pointer_schema, bind_pointers)
from legal_skill_guard.skill_evolution.relational_compiler import compile_skill


def fixture():
    text = 'Actor permits its employees. Affiliate employees are separate.'
    boundary = text.index(' Affiliate')
    source = {'views': [{'public': {'source_text': text,
        'sentence_spans': [[0, boundary], [boundary + 1, len(text)]]}}]}
    spec = {'kind': 'relational_rule', 'rationale': 'Grounding regression, not performance evidence.',
        'frames': [{'name': 'authorization', 'meaning': 'A source-stated authorization.', 'fields': [
            {'name': 'roles', 'meaning': 'Roles belonging to this action.', 'type': 'array',
                'domain': ['employee', 'advisor']},
            {'name': 'owner', 'meaning': 'Explicitly stated organizational owner.', 'type': 'string',
                'domain': ['actor', 'affiliate']}]}], 'source_examples': [], 'policy_text': None,
        'procedure': 'def apply(inputs, premises):\n    return {"handled": False, "answer": "NotMentioned", "used_records": []}\n'}
    lexicons = [{'name': 'roles', 'entries': [
        {'symbol': 'employee', 'forms': ['employees']}, {'symbol': 'advisor', 'forms': ['advisors']}]}]
    compile_skill(spec, {})
    return source, spec, lexicons


def response(ids, support):
    return {'authorization': [{'support_ids': support, 'fields': {
        'roles': {'value': ids, 'support_ids': support},
        'owner': {'value': 'actor', 'support_ids': support}}}]}


class GroundedRelationChecks(unittest.TestCase):
    def test_absent_domain_member_cannot_be_generated_as_a_source_role(self):
        source, spec, lexicons = fixture()
        spans, mentions, rejected = role_mentions(source, spec, lexicons)
        self.assertEqual([m['concept'] for m in mentions], ['employee', 'employee'])
        self.assertEqual(rejected, [])
        records = bind_pointers(spec, spans, mentions, response([0], [0]))
        self.assertEqual(records[0]['values']['roles'], ['employee'])
        self.assertFalse(records[0]['relation_semantics_verified'])
        with self.assertRaises(jsonschema.ValidationError):
            bind_pointers(spec, spans, mentions, response(['employee', 'advisor'], [0]))

    def test_another_occurrence_cannot_borrow_the_first_clause_proof(self):
        source, spec, lexicons = fixture()
        spans, mentions, _ = role_mentions(source, spec, lexicons)
        with self.assertRaisesRegex(ValueError, 'outside field evidence'):
            bind_pointers(spec, spans, mentions, response([1], [0]))

    def test_unlearned_surface_is_unknown_and_not_an_invented_alias(self):
        source, spec, lexicons = fixture()
        source['views'][0]['public'] = {'source_text': 'Actor permits staff.', 'sentence_spans': [[0, 20]]}
        spans, mentions, _ = role_mentions(source, spec, lexicons)
        self.assertEqual(mentions, [])
        records = bind_pointers(spec, spans, mentions, response(None, [0]))
        self.assertNotIn('roles', records[0]['values'])
        self.assertEqual(records[0]['unresolved_fields'], ['roles'])
        with self.assertRaises(jsonschema.ValidationError):
            bind_pointers(spec, spans, mentions, response([0], [0]))

    def test_competing_learned_meanings_are_not_resolved_by_order(self):
        source, spec, lexicons = fixture()
        lexicons[0]['entries'][1]['forms'] = ['employees']
        _, mentions, rejected = role_mentions(source, spec, lexicons)
        self.assertEqual(mentions, [])
        self.assertEqual(len(rejected), 4)

    def test_duplicate_occurrences_preserve_the_role_set_without_mutating_raw_output(self):
        source, spec, lexicons = fixture()
        spans, mentions, _ = role_mentions(source, spec, lexicons)
        raw = response([0, 1], [0, 1]); original = deepcopy(raw)
        records = bind_pointers(spec, spans, mentions, raw)
        self.assertEqual(records[0]['values']['roles'], ['employee'])
        self.assertEqual(raw, original)


if __name__ == '__main__': unittest.main()
