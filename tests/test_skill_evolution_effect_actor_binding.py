import unittest

from legal_skill_guard.skill_evolution.effect_actor_binding import bind, finish


SPEC = {'constructors': [{'name': 'named_recipient', 'arguments': ['text'],
                          'sort': 'Participant', 'meaning': 'The designated recipient.'}]}
UNITS = [{'id': 58, 'text': 'Holder returns it; its legal counsel may keep one copy.'}]
QUERIES = [{'id': 'sr_0_role', 'unit_ids': [58]}]
OBSERVATIONS = [
    {'query_id': 'sr_0_role', 'effect': 'disposal_obligation', 'unit_id': 58,
     'phrase': 'Holder'},
    {'query_id': 'sr_0_role', 'effect': 'retention_permission', 'unit_id': 58,
     'phrase': 'its legal counsel'},
]


class EffectActorBindingTests(unittest.TestCase):
    def test_distinct_effects_reach_the_actual_executable_input(self):
        program = '''def apply(inputs,premises):
    if inputs['phase']=='plan':
        return {'queries':[{'id':'sr_0_role','unit_ids':[58]}]}
    return inputs['effect_actor_bindings']['sr_0_']
'''
        result = finish({'spec': SPEC, 'program': program}, UNITS[0]['text'], UNITS,
                        [], OBSERVATIONS)
        self.assertEqual(result['disposal_obligation'], ['named_recipient', 'Holder'])
        self.assertEqual(result['retention_permission'],
                         ['named_recipient', 'its legal counsel'])

    def test_missing_actor_is_not_borrowed_from_another_effect(self):
        rows = [OBSERVATIONS[0], {**OBSERVATIONS[1], 'phrase': ''}]
        result = bind(SPEC, QUERIES, UNITS, rows)['sr_0_']
        self.assertIsNone(result['retention_permission'])

    def test_conflicts_foreign_evidence_and_invented_phrases_rejected(self):
        for rows in [OBSERVATIONS + [OBSERVATIONS[0]],
                     [{**OBSERVATIONS[0], 'unit_id': 59}],
                     [{**OBSERVATIONS[0], 'phrase': 'another actor'}],
                     [{**OBSERVATIONS[0], 'query_id': 'foreign_role'}]]:
            with self.assertRaises(ValueError):
                bind(SPEC, QUERIES, UNITS, rows)
