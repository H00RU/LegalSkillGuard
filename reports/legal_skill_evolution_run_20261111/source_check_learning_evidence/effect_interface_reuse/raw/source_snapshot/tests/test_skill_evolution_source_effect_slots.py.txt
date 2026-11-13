from copy import deepcopy
import json
import unittest

from legal_skill_guard.skill_evolution.source_effect_slots import decode


def ctor(name, args, sort):
    return {'name': name, 'arguments': args, 'sort': sort, 'meaning': name}


SPEC = {'constructors': [
    ctor('named_recipient', ['text'], 'Participant'),
    ctor('confidential_information', [], 'Information'),
    ctor('copies_of', ['Information'], 'Information'),
    ctor('after_disposal', [], 'Trigger'),
    ctor('retention_condition', ['text'], 'Condition'),
    ctor('disposal_obligation', ['Participant', 'Action', 'Trigger', 'ExceptionSet'], 'Norm'),
    ctor('retention_permission', ['Participant', 'Information', 'Trigger', 'Condition'], 'Norm'),
    ctor('retention_prohibition', ['Participant', 'Information', 'Trigger'], 'Norm')]}
UNITS = [{'id': 58, 'text': 'Its legal counsel may maintain a single copy for compliance.'}]
VALUE = {'statements': [{
    'constructor': 'retention_permission', 'actor_phrase': 'Its legal counsel',
    'argument_expressions': ['copies_of(confidential_information())', 'after_disposal()',
                             'retention_condition("a single copy for compliance")'],
    'support_ids': [58]}], 'unresolved': []}


class SourceEffectSlotTests(unittest.TestCase):
    def test_literal_condition_and_actor_survive_lowering(self):
        result, audit = decode(SPEC, UNITS, [58], json.dumps(VALUE))
        term = result['statements'][0]['term']
        self.assertEqual(term[1], ['named_recipient', 'Its legal counsel'])
        self.assertEqual(term[4], ['retention_condition', 'a single copy for compliance'])
        self.assertTrue(result['complete'])
        self.assertTrue(audit[-1]['text_audit'][0]['verbatim_in_cited_source'])

    def test_no_default_norm_is_created_for_unresolved_source(self):
        result, _ = decode(SPEC, UNITS, [58], json.dumps(
            {'statements': [], 'unresolved': ['Actor not resolved.']}))
        self.assertEqual(result['statements'], [])
        self.assertFalse(result['complete'])

    def test_wrong_sort_unknown_constructor_and_invented_text_rejected(self):
        for bad in ['after_disposal()', 'unacquired()', 'retention_condition("for archival use")']:
            value = deepcopy(VALUE)
            value['statements'][0]['argument_expressions'][2] = bad
            with self.assertRaises(ValueError):
                decode(SPEC, UNITS, [58], json.dumps(value))

    def test_actor_and_focus_cannot_be_borrowed(self):
        for change in ('actor', 'scope', 'duplicate'):
            value = deepcopy(VALUE)
            units = UNITS + [{'id': 57, 'text': 'Context heading.'}]
            if change == 'actor': value['statements'][0]['actor_phrase'] = 'another holder'
            if change == 'scope': value['statements'][0]['support_ids'] = [57]
            if change == 'duplicate': value['statements'][0]['support_ids'] = [58, 58]
            with self.assertRaises(ValueError):
                decode(SPEC, units, [58], json.dumps(value))
