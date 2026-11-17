"""Source/role/attachment regressions for fourteen explicitly reviewed excerpts.

These prove transport and scope invariants;they do not replace root semantic
review with automatic truth certification or evaluate native answers.
"""
from collections import Counter
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

from experiments import two_method_maud_knowledge_reviews as reviews
from experiments.two_method_annotate import inputs
from experiments.two_method_graph_corpus import ROOT, read
from legal_skill_guard.paired_interfaces import graph_interface as gi
from legal_skill_guard.skill_evolution.clients import FrozenExecutor, FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger


class MAUDKnowledgeReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.public = {s['key']: s for s in read(ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
        cls.locks = read(reviews.LOCK_PATH)

    def example(self, prefix):
        source = next(r['source'] for r in self.locks if r['source'].split(':')[1].startswith(prefix))
        task, _ = inputs(self.public[source])
        units = next(v['source_units'] for v in task['views'] if v['view_id'] == 'v0')
        return source, units, reviews.reviewed_graph(source, units)

    def test_all_fourteen_have_source_spans_unknowns_and_original_role_counts(self):
        self.assertEqual(Counter(r['role'] for r in self.locks), Counter(development=6, calibration=4, reference_only=4))
        partial = []
        for row in self.locks:
            source, units, graph = self.example(row['source'].split(':')[1][:8])
            checks = gi.validate(graph, units)
            self.assertTrue(checks['schema_and_source_spans_valid'])
            self.assertFalse(checks['source_semantic_truth_verified'])
            self.assertTrue(graph['unresolved'])
            self.assertTrue(all(n['concept'] not in ('own_employees', 'affiliate_employees') for n in graph['nodes']))
            if not graph['scope_complete']: partial.append(source.split(':')[1][:8])
        self.assertEqual(set(partial), {'294850b3', 'a3142f07', '04bc1032', 'b3fc96b4', 'b8241f8f', 'ef95fbbc'})

    def test_source_drift_and_unreviewed_sources_cannot_gain_a_review_flag(self):
        source, units, _ = self.example('294850b3'); altered = deepcopy(units)
        altered[0]['text'] += ' '
        with self.assertRaisesRegex(ValueError, 'exact source view'):
            reviews.reviewed_graph(source, altered)
        with self.assertRaisesRegex(ValueError, 'exact source view'):
            reviews.reviewed_graph('MAUD:unreviewed', units)

    def test_direct_reports_are_targets_and_holders_stay_their_reporting_referents(self):
        _, _, graph = self.example('294850b3')
        relations = {(r['predicate'], tuple(r['arguments'])) for r in graph['relations']}
        self.assertIn(('recipient', ('inquiry', 'direct_report_employees')), relations)
        self.assertNotIn(('recipient', ('inquiry', 'company_holders')), relations)
        self.assertIn(('object', ('reporting_qualification', 'company_holders')), relations)
        _, _, graph = self.example('5a36bd3b')
        self.assertIn(['inquiry', 'direct_reports'], [r['arguments'] for r in graph['relations'] if r['predicate'] == 'recipient'])
        self.assertFalse(any(r['predicate'] == 'member_of' for r in graph['relations']))

    def test_party_branches_keep_respective_lists_and_shared_inquiry_scope(self):
        _, _, graph = self.example('9f3b4889')
        nodes = {n['id']: n for n in graph['nodes']}
        self.assertIn('Company’s Disclosure Letter', nodes['company_holders']['name'])
        self.assertIn('Parent’s Disclosure Letter', nodes['parent_holders']['name'])
        relations = {(r['predicate'], tuple(r['arguments'])) for r in graph['relations']}
        self.assertIn(('object', ('company', 'company_holders')), relations)
        self.assertNotIn(('object', ('company', 'parent_holders')), relations)
        self.assertTrue({('condition', ('company', 'inquiry')), ('condition', ('parent', 'inquiry'))} <= relations)
        _, _, shared = self.example('447ae333')
        objects = {tuple(r['arguments']) for r in shared['relations'] if r['predicate'] == 'object'}
        self.assertIn(('company', 'company_letter_group'), objects)
        self.assertIn(('holdings', 'company_letter_group'), objects)
        self.assertIn(('parent', 'parent_letter_group'), objects)

    def test_absent_inquiry_and_omitted_branches_are_not_negative_requirements(self):
        for prefix in ('a3142f07', 'e4081ab8', 'b1a2f5ad', '447ae333'):
            _, _, graph = self.example(prefix)
            self.assertFalse(any(n['concept'] in ('no_inquiry_required', 'due_inquiry_required', 'reasonable_inquiry_required') for n in graph['nodes']))
            self.assertTrue(any('inquiry' in s for s in graph['unresolved']))
        self.assertFalse(self.example('a3142f07')[2]['scope_complete'])
        self.assertFalse(self.example('04bc1032')[2]['scope_complete'])

    def test_future_eligibility_time_does_not_move_to_all_scheduled_holders(self):
        _, _, graph = self.example('195081ce')
        nodes = {n['id']: n for n in graph['nodes']}
        relations = {(r['predicate'], tuple(r['arguments'])) for r in graph['relations']}
        self.assertIn(('condition', ('future_holders', 'future_time')), relations)
        self.assertNotIn(('condition', ('scheduled', 'future_time')), relations)
        self.assertNotIn(('condition', ('definition', 'future_time')), relations)
        self.assertEqual(nodes['role_qualification']['kind'], 'condition')
        self.assertTrue(any('not an assertion that a replacement has occurred' in s for s in graph['unresolved']))

    def test_records_employee_inquiry_has_stated_actor_and_qualified_investigation_limit(self):
        _, _, graph = self.example('b3fc96b4')
        relations = {(r['predicate'], tuple(r['arguments'])) for r in graph['relations']}
        self.assertTrue({('recipient', ('inquiry', 'records')), ('recipient', ('inquiry', 'employees'))} <= relations)
        self.assertIn(('actor', ('inquiry', 'definition_holders')), relations)
        self.assertIn(('condition', ('inquiry', 'investigation_limit')), relations)
        self.assertFalse(any(n['concept'] == 'no_inquiry_required' for n in graph['nodes']))
        self.assertFalse(any(n['concept'] == 'explicit_actual_wording' for n in graph['nodes']))
        _, _, modal = self.example('ef95fbbc')
        nodes = {n['id']: n for n in modal['nodes']}
        self.assertEqual(nodes['expected_knowledge_qualification']['concept'], 'unspecified')
        self.assertEqual(nodes['potential_knowledge']['concept'], 'unspecified')
        self.assertIn(['direct_reports', 'expected_knowledge_qualification'], [r['arguments'] for r in modal['relations'] if r['predicate'] == 'condition'])

    def test_split_initial_never_merges_source_units_or_creates_an_extra_person(self):
        source, units, graph = self.example('b8241f8f')
        before = deepcopy(units)
        again = reviews.reviewed_graph(source, units)
        self.assertEqual(before, units); self.assertEqual(graph, again)
        people = [n for n in graph['nodes'] if n['kind'] == 'person']
        self.assertEqual(len(people), 9)
        self.assertFalse(any(n['name'] in ('A.', 'A. Brent King') for n in people))
        brent = next(n for n in people if n['name'] == 'Brent King')
        self.assertEqual(brent['unit_id'], 1)
        self.assertTrue(any('source-unit cut' in s for s in graph['unresolved']))

    def test_cumulative_persistence_keeps_original_two_and_never_calls_clients_or_reads_labels(self):
        original = Path.read_text
        def source_only(path, *args, **kwargs):
            if path.name == 'grading.json': self.fail('source review opened native labels')
            return original(path, *args, **kwargs)
        with patch.object(Path, 'read_text', source_only), \
             patch.object(FrozenExecutor, '__init__', side_effect=AssertionError('executor created')), \
             patch.object(FrozenTeacher, '__init__', side_effect=AssertionError('teacher created')), \
             patch.object(EvolutionLedger, '__init__', side_effect=AssertionError('ledger constructed')):
            out, manifest = reviews.prepare()
            repeated, same = reviews.prepare()
        self.assertEqual(out, repeated); self.assertEqual(manifest, same)
        self.assertEqual(len(manifest['reviews']), 16)
        self.assertIsNone(manifest['interactive_root_annotation_cost_usd'])
        self.assertTrue(manifest['unmetered_root_annotation_overhead_not_reported_as_free'])
        self.assertEqual(len({(r['source'], r['view']) for r in manifest['reviews']}), 16)
        for entry in manifest['reviews']:
            card = read(ROOT / entry['path'])
            self.assertTrue(card['reference_ready'])
            self.assertFalse(card['native_answers_used_to_create_or_repair_graph'])
            self.assertFalse(card['complete_native_case_gold_claimed'])
            self.assertNotEqual(card['role'], 'structure_evaluation')


if __name__ == '__main__':
    unittest.main()
