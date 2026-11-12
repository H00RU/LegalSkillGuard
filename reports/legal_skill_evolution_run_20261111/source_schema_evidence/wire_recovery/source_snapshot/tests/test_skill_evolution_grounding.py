"""Exact source binding repairs formatting, never missing legal meaning."""
import unittest
from legal_skill_guard.skill_evolution.teacher_transport import unpack
import json

from legal_skill_guard.skill_evolution.grounding import bind_transcribed_quotes
from legal_skill_guard.skill_evolution.teacher import compile_block, propose
from legal_skill_guard.skill_evolution.objects import Library


class GroundingTests(unittest.TestCase):
    def test_production_compiler_keeps_program_and_legal_value_and_records_binding(self):
        origin = {'source_id': 'fixture', 'view_id': 'v', 'quote': 'paid— (A)'}
        skill = {'id': 'fixture', 'intent': 'fixture',
            'procedure': 'def apply(inputs, premises):\n    return {"answer": inputs["a"] and premises["p"]}\n',
            'inputs': [{'name': 'a', 'type': 'boolean', 'mode': 'read', 'question': 'A', 'field': 'a', 'skill_id': None}],
            'outputs': [{'name': 'answer', 'type': 'boolean', 'description': 'fixture'}],
            'premises': [{'name': 'p', 'type': 'boolean', 'mode': 'constant', 'value': True,
                'origin': origin, 'question': 'P', 'read_id': None, 'field': None}],
            'reads': [], 'semantic_records': [], 'source_obligations': [], 'source_provenance': [origin], 'version': 1}
        sources = {'fixture': {'views': [{'id': 'v', 'public': {'source_text': 'paid-\n (A)'}}]}}
        revision = compile_block({'revisions': [{'operation': 'create', 'skill': skill}]}, Library(), sources, 'Full')[0]
        self.assertEqual(revision['new']['procedure'], skill['procedure'])
        self.assertTrue(revision['new']['premises']['p']['value'])
        self.assertEqual(revision['new']['source_provenance'][0]['quote'], 'paid-\n (A)')
        self.assertTrue(revision['representation_adaptation']['source_quote_transcription_bindings'])

    def test_failed_raw_proposals_reach_teacher_without_duplicating_compiled_programs(self):
        raw = {'rationale': 'fixture failed hypothesis, not a verified rule', 'revisions': []}
        library = Library(provisional_edits=[{'error': 'fixture compile failure', 'raw_block': raw, 'revisions': None},
            {'error': None, 'raw_block': raw, 'revisions': [{'new': 'already supplied canonical proposal'}]}])
        class Capture:
            ledger = type('L', (), {'run_id': 'fixture'})()
            def propose(self, identity, **kwargs):return kwargs
        result = propose(Capture(), arm='Full', batch=2, library=library,
            source_records=[{'key': 'fixture', 'views': [{'id': 'v', 'answer_schema': {'type': 'boolean'}}]}],
            feedback=[], learned_patterns=[], trigger=['fixture'], history=[])
        retained = unpack(json.loads(result['user_prompt']))['retained_edits']
        self.assertEqual(retained[0]['raw_block'], raw)
        self.assertNotIn('raw_block', retained[1])

    def test_observed_separator_and_whitespace_bind_exact_literal_without_program_change(self):
        source = 'which is paid-\n  (A) after death, or\n (ii) retirement for disability'
        origin = {'source_id': 'fixture', 'view_id': 'v', 'quote':
            'which is paid— (A) after death, or (ii) retirement for disability'}
        skill = {'source_provenance': [origin], 'procedure': 'def apply(inputs, premises):\n    return {"answer": False}\n',
                 'premises': [{'value': 17}], 'inputs': []}
        sources = {'fixture': {'views': [{'id': 'v', 'public': {'source_text': source}}]}}
        actual, receipt = bind_transcribed_quotes(skill, sources)
        self.assertEqual(actual['source_provenance'][0]['quote'], source)
        self.assertEqual(actual['procedure'], skill['procedure'])
        self.assertEqual(actual['premises'], skill['premises'])
        self.assertEqual(len(receipt), 1)
        self.assertEqual(skill['source_provenance'][0]['quote'], origin['quote'])

    def test_words_missing_rules_numbers_and_numeric_dashes_are_not_adapted(self):
        source = 'paid-\n (A) after death and disability; the range is 100-200.'
        sources = {'fixture': {'views': [{'id': 'v', 'public': {'source_text': source}}]}}
        for quote in ('paid- (A) after death or disability', 'after death ... disability', 'the range is 100–200.',
                      'the range is 100-201.'):
            origin = {'source_id': 'fixture', 'view_id': 'v', 'quote': quote}
            value, receipt = bind_transcribed_quotes(origin, sources)
            self.assertEqual(value, origin)
            self.assertEqual(receipt, [])

    def test_ambiguous_source_spelling_is_not_chosen(self):
        origin = {'source_id': 'fixture', 'view_id': 'v', 'quote': 'paid— (A) after death'}
        sources = {'fixture': {'views': [{'id': 'v', 'public': {'one': 'paid-\n (A) after death',
                                                              'two': 'paid-  (A) after death'}}]}}
        self.assertEqual(bind_transcribed_quotes(origin, sources), (origin, []))


if __name__ == '__main__':unittest.main()
