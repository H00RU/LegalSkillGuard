from copy import deepcopy
import json
import unittest

import jsonschema

from legal_skill_guard.skill_evolution.source_effect_records import decode


def ctor(name, args, sort):
    return {'name': name, 'arguments': args, 'sort': sort, 'meaning': name}


SPEC = {'constructors': [
    ctor('named_recipient', ['text'], 'Participant'),
    ctor('confidential_information', [], 'Information'),
    ctor('copies_of', ['Information'], 'Information'),
    ctor('information_bundle', ['Information', 'Information'], 'Information'),
    ctor('after_disposal', [], 'Trigger'),
    ctor('request_by', ['Participant'], 'Trigger'),
    ctor('retention_condition', ['text'], 'Condition'),
    ctor('no_condition', [], 'Condition'),
    ctor('return_to', ['Information', 'Participant'], 'Action'),
    ctor('no_exceptions', [], 'ExceptionSet'),
    ctor('exception_set', ['Exception'], 'ExceptionSet'),
    ctor('retention_exception', ['Participant', 'Information', 'Condition'], 'Exception'),
    ctor('disposal_obligation', ['Participant', 'Action', 'Trigger', 'ExceptionSet'], 'Norm'),
    ctor('retention_permission', ['Participant', 'Information', 'Trigger', 'Condition'], 'Norm'),
    ctor('retention_prohibition', ['Participant', 'Information', 'Trigger'], 'Norm')]}
UNITS = [{'id': 58, 'text': 'On Owner request Holder returns the information and copies to Owner; '
           'Counsel may keep a single copy for compliance.'}]
VALUE = {'return_or_destruction_duties': [{
    'actor_phrase': 'Holder', 'action': 'return',
    'information_scope': 'confidential_information_and_copies',
    'return_recipient_phrase': 'Owner',
    'alternative_triggers': [{'kind': 'request', 'requester_phrase': 'Owner'}],
    'retention_exception_indices': [0], 'other_exceptions': [], 'support_ids': [58]}],
    'post_disposal_retention': [{
        'mode': 'permission', 'actor_phrase': 'Counsel',
        'information_scope': 'copies_of_confidential_information',
        'restriction_phrase': 'a single copy for compliance',
        'restriction_status': 'source_scoped', 'applies_after_return_or_destruction': True,
        'support_ids': [58]}], 'unresolved': []}


class SourceEffectRecordTests(unittest.TestCase):
    def test_actual_named_fields_preserve_different_actors_condition_and_link(self):
        result, _ = decode(SPEC, UNITS, [58], json.dumps(VALUE))
        retained, duty = [r['term'] for r in result['statements']]
        self.assertEqual(duty[1], ['named_recipient', 'Holder'])
        self.assertEqual(retained[1], ['named_recipient', 'Counsel'])
        self.assertEqual(retained[4], ['retention_condition', 'a single copy for compliance'])
        self.assertEqual(duty[4][1][1:], [retained[1], retained[2], retained[4]])

    def test_no_exception_is_created_without_explicit_model_link(self):
        v = deepcopy(VALUE)
        v['return_or_destruction_duties'][0]['retention_exception_indices'] = []
        result, _ = decode(SPEC, UNITS, [58], json.dumps(v))
        self.assertEqual(result['statements'][1]['term'][4], ['no_exceptions'])

    def test_unknown_missing_fields_and_old_bad_slot_output_are_not_completed(self):
        for value in [{}, {'statements': [], 'unresolved': []}]:
            with self.assertRaises(jsonschema.ValidationError):
                decode(SPEC, UNITS, [58], json.dumps(value))
        value = deepcopy(VALUE)
        del value['return_or_destruction_duties'][0]['alternative_triggers']
        with self.assertRaises(jsonschema.ValidationError):
            decode(SPEC, UNITS, [58], json.dumps(value))

    def test_wrong_link_fabricated_literal_and_timing_are_rejected(self):
        for kind in ['link', 'literal', 'timing']:
            value = deepcopy(VALUE)
            if kind == 'link': value['return_or_destruction_duties'][0]['retention_exception_indices'] = [1]
            if kind == 'literal': value['post_disposal_retention'][0]['restriction_phrase'] = 'for archive'
            if kind == 'timing': value['post_disposal_retention'][0]['applies_after_return_or_destruction'] = False
            with self.assertRaises(ValueError):
                decode(SPEC, UNITS, [58], json.dumps(value))

    def test_prohibition_cannot_become_a_retention_exception(self):
        value = deepcopy(VALUE)
        value['post_disposal_retention'][0].update(mode='prohibition', restriction_phrase='', restriction_status='none')
        with self.assertRaises(ValueError):
            decode(SPEC, UNITS, [58], json.dumps(value))

    def test_unresolved_stays_unresolved_without_a_default_rule(self):
        result, _ = decode(SPEC, UNITS, [58], json.dumps({
            'return_or_destruction_duties': [], 'post_disposal_retention': [],
            'unresolved': ['The trigger is not representable.']}))
        self.assertFalse(result['complete'])
        self.assertEqual(result['statements'], [])
