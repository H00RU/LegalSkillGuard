"""Literal orientation survives extraction without deciding any legal claim."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from legal_skill_guard.skill_evolution.literal_facts import literal_bindings
from legal_skill_guard.skill_evolution.objects import Library, Skill
from legal_skill_guard.skill_evolution.runtime import SkillRuntime


class LiteralFactsTests(unittest.TestCase):
    def test_actual_father_mention_preserves_literal_owner_and_relative(self):
        fixture = json.loads((Path(__file__).parent / 'fixtures' /
            'skill_evolution_actual_law_as_fact_20261112.json').read_text())
        view = deepcopy(fixture['view'])
        view['public']['facts'] = 'Alice has paid $3200 to her father Bob for work done in 2017.'
        view['public']['question'] = 'Section 3306(c)(5) applies to Alice employing Bob for the year 2017.'
        actual = literal_bindings(view)
        self.assertEqual(actual['values']['case_family_relations'], [['Alice', 'father', 'Bob']])
        self.assertEqual(actual['values']['employer'], 'Alice')
        self.assertEqual(actual['values']['employee'], 'Bob')
        self.assertNotIn('answer', actual['values'])
        for e in actual['evidence']:
            self.assertEqual(view['public'][e['field']][e['start']:e['end']], e['text'])

    def test_multiple_named_relations_and_no_negative_or_conditional_inference(self):
        facts = 'Eve has a son, Dan. Dan has a son, Ian.'
        values = literal_bindings({'public': {'facts': facts}})['values']
        self.assertEqual(values['case_family_relations'], [['Eve', 'son', 'Dan'], ['Dan', 'son', 'Ian']])
        for text in ('If Eve has a son, Dan, the rule applies.', 'Eve does not have a son, Dan.',
                     'Eve paid Dan for domestic work.', 'Eve and Fay have a son, Dan.'):
            self.assertNotIn('case_family_relations', literal_bindings({'public': {'facts': text}})['values'])

    def test_root_argument_is_source_bound_and_missing_never_defaults(self):
        # Fixture only: it tests binding, not a hand-written legal rule.
        skill = Skill('fixture', 'Echo a literal owner for binding regression',
            'def apply(inputs, premises):\n    return {"answer": inputs["case_family_relations"][0][0]}\n',
            {'case_family_relations': {'mode': 'argument', 'type': 'array'}},
            {'answer': {'type': 'string'}}, {}, (), (), (), ()).validate()
        def forbidden(*args, **kwargs):raise AssertionError('A literal-bound fixture needs no model')
        runtime = SkillRuntime(SimpleNamespace(read=forbidden))
        view = {'id': 'v', 'public': {'facts': 'Eve has a son, Dan.'}, 'answer_schema': {'type': 'string'}}
        result = runtime.run({'key': 'fixture'}, view, Library(skills={skill.id: skill}),
                             retrieved=[skill.id], fallback=False)
        self.assertEqual(result['answer'], 'Eve')
        self.assertTrue(result['core_executed'])
        view['public']['facts'] = 'No family information is supplied.'
        result = runtime.run({'key': 'fixture'}, view, Library(skills={skill.id: skill}),
                             retrieved=[skill.id], fallback=False)
        self.assertTrue(result['unresolved'])


if __name__ == '__main__':unittest.main()
