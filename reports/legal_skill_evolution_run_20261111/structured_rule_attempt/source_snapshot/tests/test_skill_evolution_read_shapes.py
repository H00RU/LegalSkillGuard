"""Current-source record shapes preserve qualifiers without deriving rules."""
from copy import deepcopy
import unittest

import jsonschema

from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues
from legal_skill_guard.skill_evolution.read_shapes import value_schema
from legal_skill_guard.skill_evolution.runtime import FrozenReads
from legal_skill_guard.skill_evolution.teacher import PROPOSAL_SCHEMA, reader_from_wire


FIELD = {'type': 'array', 'question': 'Read literal permission clauses as separate records.',
         'item_fields': [{'name': 'recipient_classes', 'type': 'array', 'question': 'Explicitly named recipient classes.'},
                         {'name': 'conditions', 'type': 'array', 'question': 'Conditions attached to this clause.'},
                         {'name': 'context', 'type': 'string', 'question': 'The stated permission context.'}]}


class RecordReadShapes(unittest.TestCase):
    def test_records_are_closed_and_do_not_accept_the_old_flat_sentence_list(self):
        schema = value_schema(FIELD)
        self.assertEqual(strict_output_schema_issues(schema), [])
        jsonschema.validate([{'recipient_classes': ['employees'], 'conditions': ['need to know'],
                             'context': 'for the Purpose'}], schema)
        for bad in (["directors, officers and employees who have a need to know"],
                    [{'recipient_classes': ['employees'], 'context': 'for the Purpose'}],
                    [{'recipient_classes': [], 'conditions': [], 'context': '', 'answer': 'Entailment'}]):
            with self.assertRaises(jsonschema.ValidationError):jsonschema.validate(bad, schema)

    def test_teacher_and_reader_use_the_same_shape(self):
        self.assertEqual(strict_output_schema_issues(PROPOSAL_SCHEMA), [])
        reader = reader_from_wire({'id': 'r', 'question': 'Read the source.', 'source_locator': 'source_text',
            'fields': [{'name': 'permissions', **FIELD}], 'bindings': [{'premise': 'rules', 'field': 'permissions'}]})
        self.assertEqual(reader['schema']['properties']['permissions'], value_schema(FIELD))
        self.assertEqual(reader['fields']['permissions'], FIELD)

    def test_ambiguous_record_fields_and_unsupported_objects_are_rejected_before_request(self):
        for bad in ({**FIELD, 'type': 'string'}, {**FIELD, 'item_fields': []},
                    {**FIELD, 'item_fields': FIELD['item_fields'] * 2},
                    {**FIELD, 'item_fields': [{'name': 'x', 'type': 'object', 'question': 'X'}]}):
            with self.assertRaises(ValueError):value_schema(bad)

    def test_runtime_keeps_the_whole_record_and_rule_support_without_question(self):
        view = {'id': 'v', 'public': {'source_text': 'Disclosure to employees is allowed for the Purpose if they need to know.',
                                    'question': 'Is the final claim true?'}}
        expected = [{'recipient_classes': ['employees'], 'conditions': ['need to know'], 'context': 'for the Purpose'}]
        captured = []
        reads = FrozenReads(None)
        def generate(*args, **kwargs):
            captured.append(kwargs)
            response = {'permissions': {'status': 'known', 'value': deepcopy(expected), 'support_ids': [0]}}
            jsonschema.validate(response, kwargs['schema'])
            return response, {'call_id': 'fixture', 'physical_call_id': 'fixture'}
        reads.generate = generate
        actual, event = reads.read({'key': 'fixture', 'dataset': 'fixture'}, view,
            question=FIELD['question'], fields={'permissions': FIELD}, locator='source_text',
            purpose='fixture', require_rule_support=True)
        self.assertEqual(actual, {'permissions': expected})
        self.assertEqual(event['fields']['permissions']['support'][0]['text'], view['public']['source_text'])
        self.assertTrue(all(s['field'] != 'question' for s in captured[0]['content']['source_spans']))
        self.assertEqual(captured[0]['schema']['properties']['permissions']['properties']['value'], value_schema(FIELD, nullable=True))

    def test_unknown_does_not_become_an_empty_rule_set(self):
        reads = FrozenReads(None)
        reads.generate = lambda *a, **kw: ({'permissions': {'status': 'unknown', 'value': None,
            'support_ids': []}}, {'call_id': 'fixture'})
        values, event = reads.read({'key': 'fixture', 'dataset': 'fixture'},
            {'id': 'v', 'public': {'source_text': 'No usable material.'}},
            question=FIELD['question'], fields={'permissions': FIELD}, locator='source_text',
            purpose='fixture', require_rule_support=True, allow_unresolved=True)
        self.assertEqual(values, {})
        self.assertEqual(event['unresolved_fields'], ['permissions'])


if __name__ == '__main__':unittest.main()
