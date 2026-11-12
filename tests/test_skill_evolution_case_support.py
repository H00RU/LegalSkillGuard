"""Actual law-as-fact regression, preserving complete legal context."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from dataclasses import replace
from types import SimpleNamespace

from legal_skill_guard.skill_evolution.runtime import FrozenReads, LocalReadError
from legal_skill_guard.skill_evolution.native import source_spans
from legal_skill_guard.skill_evolution.objects import Library
from legal_skill_guard.skill_evolution.teacher import skill_from_wire
from legal_skill_guard.skill_evolution.runtime import SkillRuntime
from legal_skill_guard.skill_evolution.claim_scope import declared_claim_mismatch
from legal_skill_guard.skill_evolution.task_roles import explicit_task_roles


class CaseSupportTests(unittest.TestCase):
    def test_roles_are_literal_question_bindings_without_inferred_family_facts(self):
        view = {'public': {'question': 'Section 3306(c)(5) applies to Alice employing Bob for the year 2017.'}}
        bound = explicit_task_roles(view)
        self.assertEqual(bound['arguments'], {'employer': 'Alice', 'employee': 'Bob', 'year': 2017})
        a, b = bound['character_range']
        self.assertEqual(view['public']['question'][a:b], bound['literal_text'])
        self.assertFalse(bound['inferred_legal_or_family_facts'])
        self.assertIsNone(explicit_task_roles({'public': {'question': 'Who employs whom?'}}))

    def test_explicit_clause_contract_blocks_actual_unrelated_query_before_reading(self):
        fixture = json.loads((Path(__file__).parent / 'fixtures' /
            'skill_evolution_actual_law_as_fact_20261112.json').read_text())
        original = skill_from_wire(fixture['actual_terminal_wire'])
        outputs = deepcopy(original.outputs)
        outputs['answer']['query_clauses'] = fixture['offline_contract_transcription']['query_clauses']
        skill = replace(original, outputs=outputs).validate()
        self.assertEqual(skill.procedure, original.procedure)
        self.assertEqual(skill.inputs, original.inputs)
        proof = declared_claim_mismatch(skill, fixture['view'])
        self.assertEqual(proof['queried_clause'], ['3306', 'c', '1'])
        def forbidden(*args, **kw):
            raise AssertionError('An incompatible terminal must not call a model')
        result = SkillRuntime(SimpleNamespace(read=forbidden)).run(fixture['source'], fixture['view'],
            Library(skills={skill.id: skill}), retrieved=[skill.id], fallback=False)
        self.assertTrue(result['unresolved'])
        self.assertTrue(all(e['kind'] == 'BIND_TASK_ROLES' for e in result['events']))
        for question in ('Section 3306(c)(5) applies.', 'Section 3306(c)(5)(A) applies.'):
            self.assertIsNone(declared_claim_mismatch(skill, {'public': {'question': question}}))
        with self.assertRaises(ValueError):
            replace(skill, outputs={'answer': {**outputs['answer'], 'query_clauses': ['from the skill name']}}).validate()

    def test_actual_rule_only_spouse_read_is_rejected_without_changing_raw_output(self):
        fixture = json.loads((Path(__file__).parent / 'fixtures' /
            'skill_evolution_actual_law_as_fact_20261112.json').read_text())
        reads = FrozenReads(None)
        captured = []
        def generate(*args, **kwargs):
            captured.append(kwargs)
            return deepcopy(fixture['response']), deepcopy(fixture['event'])
        reads.generate = generate
        options = {'question': fixture['event']['question'], 'fields': fixture['field_specs'],
            'locator': fixture['event']['locator'], 'purpose': 'fixture', 'allow_unresolved': True}
        values, _ = reads.read(fixture['source'], fixture['view'], **options)
        self.assertEqual(values['employer_relationship_to_worker'], 'spouse')
        with self.assertRaisesRegex(LocalReadError, 'supported only by rule text') as raised:
            reads.read(fixture['source'], fixture['view'], **options, require_case_support=True)
        event = raised.exception.event
        self.assertEqual(event['physical_call_id'], fixture['physical_call_id'])
        self.assertEqual(event['fields']['employer_relationship_to_worker']['value'], 'spouse')
        self.assertEqual(captured[-1]['content']['required_case_support_fields'], ['facts', 'question'])
        self.assertTrue(any(s['field'] == 'source_text' for s in captured[-1]['content']['source_spans']))

    def test_explicit_given_legal_intermediate_may_use_law_and_case_together(self):
        view = {'id': 'v', 'public': {'source_text': 'The statute defines qualifying child.',
            'facts': 'GIVEN Bob satisfies section 152(c)(1) for Alice.',
            'question': 'Does the stated exclusion apply for 2015?'}}
        ids = [s['id'] for s in source_spans(view['public']) if s['field'] in ('facts', 'source_text')]
        reads = FrozenReads(None)
        reads.generate = lambda *args, **kw: ({'given': {'status': 'known', 'value': True,
            'support_ids': ids}}, {'call_id': 'fixture'})
        values, _ = reads.read({'key': 'fixture', 'dataset': 'fixture'}, view,
            question='Read the explicit GIVEN fact', fields={'given': {'type': 'boolean'}},
            locator='full supplied context', purpose='fixture', require_case_support=True)
        self.assertEqual(values, {'given': True})

    def test_contract_without_separate_case_facts_is_not_treated_as_rule_only(self):
        reads = FrozenReads(None)
        reads.generate = lambda *args, **kw: ({'term': {'status': 'known', 'value': 'employees',
            'support_ids': [0]}}, {'call_id': 'fixture'})
        values, event = reads.read({'key': 'fixture', 'dataset': 'ContractNLI'},
            {'id': 'v', 'public': {'source_text': 'Disclosure to employees is permitted.',
                                 'question': 'Who may receive disclosure?'}},
            question='Read the expressly listed recipients', fields={'term': {'type': 'string'}},
            locator='contract', purpose='fixture', require_case_support=True)
        self.assertEqual(values, {'term': 'employees'})
        self.assertNotIn('required_case_support_fields', event)


if __name__ == '__main__':
    unittest.main()
