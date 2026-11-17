"""Exact reviewed-source binding and prior unsupported-role regressions.

These checks validate source transport/unknown preservation;the semantic
review is the explicit root review,not an automated truth certificate.
"""
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

from experiments import two_method_cached_maud_reviews as cards
from experiments.two_method_annotate import inputs
from experiments.two_method_graph_corpus import ROOT, BASE, read, sha
from legal_skill_guard.paired_interfaces import graph_interface as gi
from legal_skill_guard.skill_evolution.clients import FrozenExecutor, FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger


class CachedMAUDReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.public = {s['key']: s for s in read(ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}

    def units(self, source):
        task, _ = inputs(self.public[source])
        return next(v['source_units'] for v in task['views'] if v['view_id'] == 'v0')

    def test_designated_holders_never_become_inquiry_targets_or_inferred_employees(self):
        for source in cards.LOCKS:
            graph = cards.reviewed_graph(source, self.units(source))
            self.assertFalse(graph['scope_complete'])
            self.assertTrue(any('target is not supplied' in s for s in graph['unresolved']))
            self.assertFalse(any(n['concept'] in ('own_employees', 'affiliate_employees') for n in graph['nodes']))
            self.assertFalse(any(r['predicate'] == 'member_of' for r in graph['relations']))
            self.assertFalse(any(r['predicate'] == 'recipient' and r['arguments'][0] == 'inquiry' for r in graph['relations']))
            checked = gi.validate(graph, self.units(source))
            self.assertTrue(checked['schema_and_source_spans_valid'])
            self.assertFalse(checked['source_semantic_truth_verified'])

    def test_patent_work_exception_and_non_imputation_keep_distinct_scopes(self):
        source = next(s for s in cards.LOCKS if s.startswith('MAUD:7e2add3c'))
        graph = cards.reviewed_graph(source, self.units(source))
        nodes = {n['id']: n for n in graph['nodes']}
        self.assertEqual(nodes['non_imputation']['concept'], 'prohibition')
        exceptions = [r['arguments'] for r in graph['relations'] if r['predicate'] == 'exception_for']
        self.assertEqual(exceptions, [['limited_inquiry_exception', 'inquiry']])
        actions = [r['arguments'] for r in graph['relations'] if r['predicate'] == 'action']
        self.assertIn(['non_imputation', 'imputation_action'], actions)
        self.assertIn(['limited_inquiry_exception', 'clearance_work'], actions)
        self.assertFalse(any(r['predicate'] == 'standard' and 'imputation_action' in r['arguments'] for r in graph['relations']))
        self.assertFalse(any(n['concept'] == 'explicit_actual_wording' for n in graph['nodes']))
        self.assertFalse(any('if not conducted' in n['quote'] for n in graph['nodes']))

    def test_inquiry_remains_a_condition_of_the_supplied_actual_wording_branch(self):
        source = next(s for s in cards.LOCKS if s.startswith('MAUD:cef0e433'))
        graph = cards.reviewed_graph(source, self.units(source))
        triples = {(r['predicate'], tuple(r['arguments']), r['status']) for r in graph['relations']}
        self.assertIn(('standard', ('definition', 'actual_wording'), 'stated'), triples)
        self.assertIn(('condition', ('definition', 'inquiry'), 'stated'), triples)
        self.assertTrue(any('other party branch' in s for s in graph['unresolved']))

    def test_changed_source_text_or_unreviewed_source_cannot_acquire_a_review_flag(self):
        source = next(iter(cards.LOCKS)); units = deepcopy(self.units(source))
        units[0]['text'] += ' '
        with self.assertRaisesRegex(ValueError, 'exact manually read'):
            cards.reviewed_graph(source, units)
        with self.assertRaisesRegex(ValueError, 'exact manually read'):
            cards.reviewed_graph('MAUD:unreviewed', self.units(source))

    def test_actual_persistence_never_creates_clients_reads_labels_or_changes_old_partial_reviews(self):
        original = Path.read_text; before = sha(cards.CACHE)
        def no_labels(path, *args, **kwargs):
            if path.name == 'grading.json': self.fail('source review opened native labels')
            return original(path, *args, **kwargs)
        with patch.object(Path, 'read_text', no_labels), \
             patch.object(FrozenExecutor, '__init__', side_effect=AssertionError('model client')), \
             patch.object(FrozenTeacher, '__init__', side_effect=AssertionError('teacher client')), \
             patch.object(EvolutionLedger, '__init__', side_effect=AssertionError('ledger client')):
            out, manifest = cards.prepare()
            again, repeated = cards.prepare()
        self.assertEqual(out, again); self.assertEqual(manifest, repeated)
        self.assertEqual(sha(cards.CACHE), before)
        self.assertEqual(len(manifest['reviews']), 2)
        for entry in manifest['reviews']:
            card = read(ROOT / entry['path'])
            self.assertEqual(card['role'], 'calibration')
            self.assertTrue(card['source_semantic_truth_verified'])
            self.assertFalse(card['native_answers_used_to_create_or_repair_graph'])
            self.assertFalse(card['complete_native_case_gold_claimed'])
            self.assertTrue(card['review']['entire_supplied_view_read'])


if __name__ == '__main__':
    unittest.main()
