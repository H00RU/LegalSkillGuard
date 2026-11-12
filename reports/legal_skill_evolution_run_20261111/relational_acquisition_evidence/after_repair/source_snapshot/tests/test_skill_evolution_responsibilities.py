"""Actual code/source observations plus explicitly synthetic routing fixtures."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from legal_skill_guard.skill_evolution.objects import Library, Skill
from legal_skill_guard.skill_evolution.patterns import relation_context
from legal_skill_guard.skill_evolution.responsibilities import context, invocations, read_cost, source_relation


class ResponsibilityContexts(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1]
        self.report = root / 'reports/legal_skill_evolution_run_20261111'
        folder = self.report / 'source_rule_evidence/legal_skill_evolution_source_rule_check_20261112'
        self.old = Library.load(folder / 'FreeEvolution/B2.json')
        self.table = json.loads((folder / 'FreeEvolution/B3_candidates/0.json').read_text())['table']
        self.new = {r['skill_id']: Skill.from_dict(r['new']) for r in
                    json.loads((folder / 'FreeEvolution/B3_candidates/0.json').read_text())['revisions']}
        self.sources = {r['key']: r for r in json.loads((self.report / 'contract_original_TRAIN_public.json').read_text())}
        self.producer = 'nda_representative_exception_applicability'
        self.consumer = 'nda_disclosure_permission_consequence'

    def test_actual_same_coarse_role_has_distinct_conditional_responsibility(self):
        p, c = self.old.skills[self.producer], self.old.skills[self.consumer]
        np, nc = self.new[p.id], self.new[c.id]
        self.assertEqual(relation_context(p, c, 'exception_applies'), relation_context(np, nc, 'exception_applies'))
        trace = next(x['trace'] for x in self.table['mixed_version_table'] if x['mask'] == 3
                     and x['source'].startswith('ContractNLI:354'))
        contexts = {u['view']: context(p, c, np, nc, 'exception_applies', u, self.sources[u['source']])
                    for u in invocations(trace, p.id, 'exception_applies', c.id)}
        employee, thirdparty = contexts['nda-5'], contexts['nda-7']
        self.assertEqual(employee['fields']['consumer_before_false_output'], {'answer': 'Contradiction'})
        self.assertEqual(employee['fields']['consumer_after_false_output'], {'answer': 'NotMentioned'})
        self.assertEqual(thirdparty['fields']['consumer_after_false_output'], {'answer': 'Contradiction'})
        self.assertNotEqual(employee['fields'], thirdparty['fields'])
        self.assertIn('source_relation', employee['unknown'])
        self.assertNotIn('source_relation_kind', employee['fields'])
        self.assertNotIn('declared_producer_role', employee['fields'])

    def test_actual_exception_reference_has_exact_scope_binding_without_dataset_ID_feature(self):
        seed = Library.load(self.report / 'contract_TRAIN_evidence/legal_skill_evolution_contract_acquisition_20261112/Full/B1.json')
        p, c = seed.skills[self.producer], seed.skills[self.consumer]
        source = next(s for k, s in self.sources.items() if k.startswith('ContractNLI:8af'))
        relation = source_relation(p, c, 'exception_applies', source)
        self.assertEqual(relation['status'], 'known')
        self.assertEqual((relation['consumer_scope'], relation['producer_scope']), ('3', '4'))
        text = source['views'][0]['public']['source_text']
        for key in ('producer_anchor', 'consumer_anchor'):
            item = relation[key];self.assertEqual(text[item['start']:item['end']], item['quote'])
        self.assertFalse(relation['legal_truth_or_universal_implication_inferred'])
        renamed = deepcopy(source);renamed['key'] = 'different_parent_identity';renamed['dataset'] = 'different_dataset'
        self.assertEqual(source_relation(p, c, 'exception_applies', renamed)['status'], 'known')
        other = next(s for k, s in self.sources.items() if k.startswith('ContractNLI:d50'))
        self.assertEqual(source_relation(p, c, 'exception_applies', other)['status'], 'unknown')
        bad = deepcopy(source);bad['views'][0]['public']['source_text'] += '\n4. Another possible scope.\n'
        self.assertEqual(source_relation(p, c, 'exception_applies', bad)['status'], 'unknown')
        mixed = deepcopy(source);mixed['views'][1]['public']['source_text'] = 'Different native view material.'
        self.assertEqual(source_relation(p, c, 'exception_applies', mixed)['status'], 'unknown')
        self.assertEqual(source_relation(p, c, 'exception_applies', mixed, view_id=mixed['views'][0]['id'])['status'], 'known')
        self.assertEqual(source_relation(p, c, 'exception_applies', mixed, view_id=mixed['views'][1]['id'])['status'], 'unknown')

    def test_missing_fields_remain_unknown_even_when_short_circuit_proves_one_code_effect(self):
        # This is the original design's Boolean mechanism fixture, not legal gold.
        origin = {'source_id': 'fixture', 'view_id': 'v', 'quote': 'Fixture only.'}
        p = Skill('p', 'fixture', 'def apply(inputs, premises):\n    return {"flag": inputs["a"] and not inputs["s"]}\n',
            {'a': {'type': 'boolean', 'mode': 'read', 'question': 'A'},
             's': {'type': 'boolean', 'mode': 'read', 'question': 'S'}}, {'flag': {'type': 'boolean'}},
            {}, (), (), (), (origin,)).validate()
        np = replace(p, version=2, procedure='def apply(inputs, premises):\n    return {"flag": inputs["a"]}\n').validate()
        c = Skill('c', 'fixture', 'def apply(inputs, premises):\n    return {"answer": inputs["flag"] or (inputs["s"] and inputs["c"])}\n',
            {'flag': {'type': 'boolean', 'mode': 'skill', 'skill_id': 'p', 'field': 'flag', 'arguments': {}},
             's': {'type': 'boolean', 'mode': 'read', 'question': 'S'},
             'c': {'type': 'boolean', 'mode': 'read', 'question': 'C'}},
            {'answer': {'type': 'boolean'}}, {}, (), (), (), (origin,)).validate()
        nc = replace(c, version=2, procedure='def apply(inputs, premises):\n    return {"answer": inputs["flag"] and (not inputs["s"] or inputs["c"])}\n').validate()
        unit = {'source': 'fixture', 'view': 'v', 'input_port': 'flag',
            'inputs': {'flag': True, 's': True}, 'premises': {}, 'USE': {'kind': 'USE'}}
        value = context(p, c, np, nc, 'flag', unit)
        self.assertNotIn('consumer_before_false_output', value['fields'])
        self.assertIn('consumer_before_false_output', value['unknown'])
        self.assertEqual(value['fields']['consumer_after_false_output'], {'answer': False})
        self.assertEqual(value['evidence']['reference_premises'], {})
        self.assertNotIn('c', unit['inputs'])
        self.assertEqual([x['port'] for x in value['fields']['producer_before_checks']], ['a', 's'])
        self.assertEqual([x['port'] for x in value['fields']['producer_after_checks']], ['a'])

    def test_read_cost_deduplicates_physical_origins_in_aligned_subreads(self):
        first = {'physical_call_id': 'actual-a', 'call_id': 'logical-a', 'usage': {'total_tokens': 10}}
        second = {'physical_call_id': 'actual-b', 'usage': {'total_tokens': 20}}
        trace = {'views': [{'execution': {'events': [
            {'kind': 'READ_LOCAL', **first},
            {'kind': 'READ_LOCAL', 'subreads': [first, second]}]}}]}
        table = SimpleNamespace(traces={(3, 'one'): trace, (3, 'two'): deepcopy(trace), (0, 'one'): trace})
        cost = read_cost(table, 3)
        self.assertEqual(cost['traced_tokens'], 30)
        self.assertEqual(cost['unique_read_origins'], 2)
        self.assertTrue(cost['complete'])

    def test_untraced_failure_is_unknown_cost_not_free(self):
        table = SimpleNamespace(traces={(0, 'one'): {'views': [{'execution': {
            'events': [], 'failed_candidates': [{'error': 'ReaderResponseError: invalid value'}]}}]}})
        self.assertFalse(read_cost(table, 0)['complete'])
        table.traces[0, 'one']['views'][0]['execution'] = {'events': [{'kind': 'READ_LOCAL', 'usage': {}}]}
        self.assertFalse(read_cost(table, 0)['complete'])


if __name__ == '__main__':unittest.main()
