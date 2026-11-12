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

    def test_actual_rule_read_cannot_treat_native_hypothesis_as_contract_evidence(self):
        root = Path(__file__).resolve().parents[1]
        recovery = root / 'reports/legal_skill_evolution_run_20261111/contract_TRAIN_evidence/legal_skill_evolution_contract_read_recovery_20261112'
        table = json.loads((recovery / 'FreeEvolution_B3/FreeEvolution/B3_candidates/0.json').read_text())['table']
        cell = next(c for c in table['mixed_version_table'] if c['mask'] == 3 and c['source'].startswith('ContractNLI:d50'))
        row = self.rows[cell['source']];view = next(v for v in row['views'] if v['id'] == 'nda-7')
        outcome = next(v for v in cell['trace']['views'] if v['view'] == 'nda-7')
        event = next(e for e in outcome['execution']['events'] if e.get('kind') == 'READ_LOCAL'
                     and 'general_third_party_nondisclosure_rule' in e['fields'])
        fields = deepcopy(event['fields'])
        self.assertEqual([s['field'] for s in fields['general_third_party_nondisclosure_rule']['support']], ['question'])
        for field in fields.values():field.pop('support')
        reads = FrozenReads(None)
        reads.generate = lambda *args, **kwargs: (deepcopy(fields), {})
        with self.assertRaisesRegex(LocalReadError, 'not supplied rule material'):
            reads.read(row, view, question=event['question'],
                fields={'general_third_party_nondisclosure_rule': {'type': 'boolean', 'question': 'Read the general prohibition.'}},
                locator=event['locator'], purpose='skill_replay', allow_unresolved=True, require_rule_support=True)


if __name__ == '__main__':unittest.main()
