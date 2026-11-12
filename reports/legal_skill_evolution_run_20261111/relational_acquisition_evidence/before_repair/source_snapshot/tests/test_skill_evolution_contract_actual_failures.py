"""Real-response regressions; original outputs and legal procedures stay intact."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import unittest

from legal_skill_guard.skill_evolution.claim_scope import declared_claim_mismatch
from legal_skill_guard.skill_evolution.objects import Library, Skill
from legal_skill_guard.skill_evolution.teacher import compile_block, validate_grounding
from legal_skill_guard.skill_evolution.runtime import FrozenReads, LocalReadError


class ActualContractFailures(unittest.TestCase):
    def setUp(self):
        r = Path(__file__).resolve().parents[1] / 'reports/legal_skill_evolution_run_20261111'
        self.rows = {v['key']: v for v in json.loads((r / 'contract_original_TRAIN_public.json').read_text())}
        self.evidence = r / 'contract_TRAIN_evidence/legal_skill_evolution_contract_updates_20261112'

    def proposal(self, arm, batch):
        return json.loads((self.evidence / arm / f'teacher_B{batch}.json').read_text())['value']['blocks'][0]

    def test_actual_AllPorts_empty_READ_lineage_does_not_invent_values_or_quotes(self):
        raw = self.proposal('AllPorts+CoRev', 2);before = deepcopy(raw)
        old = Library.load(self.evidence / 'AllPorts+CoRev/B1.json')
        result = compile_block(raw, old, self.rows, 'AllPorts+CoRev')
        self.assertEqual(raw, before)
        for proposed, compiled in zip(raw['revisions'], result):
            new = Skill.from_dict(compiled['new'])
            self.assertEqual(new.procedure, proposed['skill']['procedure'])
            self.assertTrue(all(p['mode'] == 'read' and 'value' not in p
                                and p['origin'] == {'source_id': '', 'view_id': '', 'quote': ''}
                                for p in new.premises.values()))
            bad = deepcopy(new.premises);name = next(iter(bad))
            bad[name] = {'mode': 'constant', 'type': bad[name]['type'], 'value': True,
                         'origin': {'source_id': '', 'view_id': '', 'quote': ''}}
            with self.assertRaises(ValueError):validate_grounding(replace(new, premises=bad), self.rows)
            bad = deepcopy(new.premises);bad[name]['origin']['quote'] = 'Invented quotation.'
            with self.assertRaises(ValueError):validate_grounding(replace(new, premises=bad), self.rows)

    def test_actual_Free_named_heading_preserves_scope_and_procedure(self):
        raw = self.proposal('FreeEvolution', 3)
        old = Library.load(self.evidence / 'FreeEvolution/B2.json')
        result = compile_block(raw, old, self.rows, 'FreeEvolution')
        new = Skill.from_dict(result[1]['new'])
        self.assertEqual(new.outputs['answer']['query_clauses'], ['heading:Non-Disclosure', '3(c)', '4(a)'])
        self.assertEqual(new.procedure, raw['revisions'][1]['skill']['procedure'])
        self.assertTrue(result[1]['representation_adaptation']['source_heading_bindings'])
        bad = deepcopy(new.outputs);bad['answer']['query_clauses'] = ['heading:Invented source heading']
        with self.assertRaises(ValueError):validate_grounding(replace(new, outputs=bad), self.rows)
        bad = deepcopy(raw);bad['revisions'][1]['skill']['outputs'][0]['query_clauses'] = ['paraphrase of a nondisclosure rule']
        with self.assertRaises(ValueError):compile_block(bad, old, self.rows, 'FreeEvolution')

    def test_named_heading_cannot_bypass_existing_numeric_scope_guard(self):
        old = Library.load(self.evidence / 'FreeEvolution/B2.json')
        terminal = next(s for s in old.skills.values() if 'answer' in s.outputs)
        outputs = deepcopy(terminal.outputs)
        outputs['answer']['query_clauses'] = ['heading:Non-Disclosure', '152(b)(1)']
        proof = declared_claim_mismatch(replace(terminal, outputs=outputs),
                                        {'public': {'question': 'Section 151(c) applies.'}})
        self.assertEqual(proof['queried_clause'], ['151', 'c'])

    def test_actual_hypothesis_evidence_is_absent_from_new_rule_read_payload(self):
        root = Path(__file__).resolve().parents[1]
        recovery = root / 'reports/legal_skill_evolution_run_20261111/contract_TRAIN_evidence/legal_skill_evolution_contract_read_recovery_20261112'
        table = json.loads((recovery / 'FreeEvolution_B3/FreeEvolution/B3_candidates/0.json').read_text())['table']
        cell = next(c for c in table['mixed_version_table'] if c['mask'] == 3 and c['source'].startswith('ContractNLI:d50'))
        row = self.rows[cell['source']];view = next(v for v in row['views'] if v['id'] == 'nda-7')
        outcome = next(v for v in cell['trace']['views'] if v['view'] == 'nda-7')
        event = next(e for e in outcome['execution']['events'] if e.get('kind') == 'READ_LOCAL'
                     and 'general_third_party_nondisclosure_rule' in e['fields'])
        self.assertEqual([s['field'] for s in event['fields']['general_third_party_nondisclosure_rule']['support']], ['question'])
        reads = FrozenReads(None)
        captured = []
        def generate(*args, **kwargs):
            captured.append(kwargs['content'])
            return {'general_third_party_nondisclosure_rule':
                {'status': 'unknown', 'value': None, 'support_ids': []}}, {}
        reads.generate = generate
        for v in [view, next(v for v in row['views'] if v['id'] == 'nda-5')]:
            values, trace = reads.read(row, v, question=event['question'],
                fields={'general_third_party_nondisclosure_rule': {'type': 'boolean', 'question': 'Read the general prohibition.'}},
                locator=event['locator'], purpose='skill_replay', allow_unresolved=True, require_rule_support=True,
                invocation_arguments={'current_question': v['public']['question'], 'year': 2017})
            self.assertEqual(values, {})
            self.assertEqual(trace['rule_context']['excluded_invocation_arguments'], ['current_question'])
            self.assertNotIn(v['public']['question'], json.dumps(captured[-1], ensure_ascii=False))
            self.assertEqual(captured[-1]['invocation_arguments'], {'year': 2017})
            self.assertNotIn('view_id', captured[-1])
            self.assertFalse(any(s['field'] == 'question' for s in captured[-1]['source_spans']))
            self.assertFalse(any('public_sentence_id' in s for s in captured[-1]['source_spans']))
            self.assertEqual([s['id'] for s in captured[-1]['source_spans']],
                             list(range(len(captured[-1]['source_spans']))))
        self.assertEqual(captured[0], captured[1])

    def test_public_sentence_positions_preserve_all_actual_TRAIN_source_text(self):
        from legal_skill_guard.skill_evolution.native import source_spans
        for row in self.rows.values():
            public = row['views'][0]['public'];text = public['source_text']
            spans = [s for s in source_spans(public) if s['field'] == 'source_text']
            self.assertGreater(len(spans), 1)
            self.assertEqual(''.join(''.join(s['text'] for s in spans).split()), ''.join(text.split()))
            for s in spans:self.assertEqual(s['text'], text[s['start']:s['end']])
            known = {s['public_sentence_id']: s for s in spans if 'public_sentence_id' in s}
            for index, (a, b) in enumerate(public['sentence_spans']):
                if text[a:b].strip():self.assertEqual(known[index]['text'], text[a:b])
        bad = deepcopy(public);bad['sentence_spans'] = [[0, 8], [7, 12]]
        with self.assertRaisesRegex(ValueError, 'overlap'):source_spans(bad)


if __name__ == '__main__':unittest.main()
