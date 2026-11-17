"""Source boundaries and factual transport,without native answer evaluation."""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from experiments import two_method_sara_source_reviews as reviews
from experiments.two_method_annotate import inputs
from experiments.two_method_graph_corpus import ROOT, read
from legal_skill_guard.paired_interfaces import graph_interface as gi
from legal_skill_guard.paired_interfaces.native_graph_consumers import sara_binding
from legal_skill_guard.skill_evolution.clients import FrozenExecutor, FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger


class SARASourceReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.public = {s['key']: s for s in read(ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
        cls.locks = read(reviews.LOCK_PATH)

    def example(self, prefix):
        source = next(r['source'] for r in self.locks if r['source'].split(':')[1].startswith(prefix))
        task, _ = inputs(self.public[source])
        self.assertEqual(len(task['views']), 1)
        units = task['views'][0]['source_units']
        return source, units, reviews.reviewed_graph(source, units)

    def facts(self, graph):
        result = sara_binding(graph)
        self.assertEqual(result['scope_contract']['family_scans'], [])
        self.assertEqual(result['binding']['negative_givens'], [])
        return {(r['predicate'], tuple(r['arguments'])) for r in result['binding']['facts']}

    def test_sixteen_original_single_views_keep_roles_spans_and_unknowns(self):
        self.assertEqual(Counter(r['role'] for r in self.locks), Counter(development=6, calibration=6, reference_only=4))
        partial = []
        for row in self.locks:
            source, units, graph = self.example(row['source'].split(':')[1][:8])
            checks = gi.validate(graph, units)
            self.assertTrue(checks['schema_and_source_spans_valid'])
            self.assertFalse(checks['source_semantic_truth_verified'])
            self.assertTrue(graph['unresolved'])
            self.assertFalse(reviews.validate_factual_records(graph)['source_meaning_or_native_answer_certified'])
            self.facts(graph)
            if not graph['scope_complete']: partial.append(source)
        self.assertEqual(len(partial), 9)

    def test_source_drift_or_unreviewed_source_is_rejected(self):
        source, units, _ = self.example('815f377b')
        altered = deepcopy(units); altered[0]['text'] += ' '
        with self.assertRaisesRegex(ValueError, 'exact source views'):
            reviews.reviewed_graph(source, altered)
        with self.assertRaisesRegex(ValueError, 'exact source views'):
            reviews.reviewed_graph('SARA_v2_Binary:unreviewed', units)

    def test_diagnosis_is_observation_not_disability_onset_or_payment_date(self):
        _, _, graph = self.example('815f377b'); facts = self.facts(graph)
        self.assertIn(('disability_', ('disability',)), facts)
        self.assertIn(('retirement_', ('retirement',)), facts)
        self.assertIn(('start_', ('retirement', '2019-10-10')), facts)
        self.assertIn(('end_', ('employment', '2019-10-10')), facts)
        self.assertFalse(any(p == 'start_' and a[0] == 'disability' for p, a in facts))
        self.assertFalse(any(p in ('start_', 'end_') and a[0] == 'payment' for p, a in facts))
        dates = [(e['predicate'], e['arguments'][0]) for e in graph['relations'] if e['predicate'].startswith('date_')]
        self.assertIn(('date_at', 'disability'), dates)

    def test_service_period_wages_hay_and_year_do_not_invent_payment_facts(self):
        _, _, domestic = self.example('bb6b0bc1'); facts = self.facts(domestic)
        self.assertIn(('start_', ('service', '2017-02-01')), facts)
        self.assertIn(('end_', ('service', '2017-09-02')), facts)
        self.assertIn(('country_', ('home', 'usa')), facts)
        self.assertFalse(any(p in ('start_', 'end_') and a[0] == 'payment' for p, a in facts))
        self.assertNotIn(('patient_', ('service', 'alice')), facts)
        _, _, hay = self.example('d5e1138c'); facts = self.facts(hay)
        self.assertIn(('amount_', ('payment', 2325)), facts)
        self.assertIn(('means_', ('payment', 'hay')), facts)
        self.assertFalse(any(p in ('income_', 'start_', 'end_') for p, a in facts))
        self.assertFalse(any(p == 'means_' and a[-1] == 'cash' for p, a in facts))
        _, _, paid = self.example('8175fcb9'); facts = self.facts(paid)
        self.assertNotIn(('income_', ('payment',)), facts)
        self.assertFalse(any(p == 'agent_' and a[0] == 'payment' for p, a in facts))

    def test_allowances_keep_beneficiaries_without_election_or_borrowed_year(self):
        _, _, graph = self.example('6a38111a')
        edges = graph['relations']
        self.assertEqual({tuple(e['arguments']) for e in edges if e['predicate'] == 'recipient'},
                         {('self_allowance', 'alice'), ('spouse_allowance', 'bob')})
        self.assertEqual([e['value'] for e in edges if e['predicate'] == 'amount'], [33200, 600, 600])
        self.assertFalse(any(e['predicate'].startswith('date_') and 'allowance' in e['arguments'][0] for e in edges))
        for prefix in ('8175fcb9', '6a38111a', '02e9175d'):
            facts = self.facts(self.example(prefix)[2])
            self.assertFalse(any(p in ('itemize_deductions_', 'joint_return_') or p.startswith('s63') for p, a in facts))

    def test_exact_statutory_givens_keep_roles_and_do_not_transitively_expand(self):
        all_givens = []
        for row in self.locks:
            prefix = row['source'].split(':')[1][:8]
            facts = self.facts(self.example(prefix)[2])
            all_givens += [(prefix, p, a) for p, a in facts if p.startswith('s152') or p.startswith('s151')]
        self.assertCountEqual(all_givens, [
            ('cc82ab0f', 's152_c_1', ('bob', 'alice', 2015)),
            ('a51930fd', 's152_c_1', ('bob', 'alice', 2015)),
            ('a51930fd', 's152_c_1', ('charlie', 'bob', 2015))])
        self.assertFalse(any(p == 'son_' for p, a in self.facts(self.example('cc82ab0f')[2])))

    def test_explicit_blindness_death_and_decree_keep_subjects_and_dates(self):
        facts = self.facts(self.example('a3080e73')[2])
        self.assertIn(('blindness_', ('blindness',)), facts)
        self.assertIn(('agent_', ('blindness', 'alice')), facts)
        self.assertIn(('start_', ('blindness', '2016-03-20')), facts)
        facts = self.facts(self.example('cd2ab8fc')[2])
        self.assertIn(('agent_', ('death', 'alice')), facts)
        self.assertNotIn(('agent_', ('death', 'bob')), facts)
        self.assertNotIn(('end_', ('marriage', '2014-07-09')), facts)
        facts = self.facts(self.example('743ac2e5')[2])
        self.assertIn(('patient_', ('separation', 'marriage')), facts)
        self.assertIn(('agent_', ('separation', 'decree of divorce')), facts)
        self.assertIn(('start_', ('separation', '2017-09-16')), facts)
        self.assertNotIn(('end_', ('marriage', '2017-09-16')), facts)

    def test_reciprocal_payments_keep_four_amounts_payees_and_distinct_work(self):
        _, _, graph = self.example('d9d6b236'); facts = self.facts(graph)
        for event, payer, payee, amount, service in (
            ('pay_bob', 'alice', 'bob', 6771, 'agricultural_labor'),
            ('pay_charlie', 'alice', 'charlie', 6954, 'agricultural_labor'),
            ('pay_dan', 'alice', 'dan', 6872, 'agricultural_labor'),
            ('reverse_payment', 'bob', 'alice', 4520, 'other_work')):
            self.assertTrue({('agent_', (event, payer)), ('patient_', (event, payee)),
                ('amount_', (event, amount)), ('purpose_', (event, service))} <= facts)
            self.assertFalse(any(p in ('start_', 'end_') and a[0] == event for p, a in facts))
        self.assertIn(('end_', ('other_work', '2018-09-02')), facts)
        self.assertIn(('end_', ('agricultural_labor', '2017-09-02')), facts)
        self.assertTrue(any('grouping' in s for s in graph['unresolved']))

    def test_factual_node_indirection_survives_renaming_and_rejects_invalid_abi(self):
        _, _, graph = self.example('a51930fd'); original = self.facts(graph)
        renamed = deepcopy(graph); mapping = {n['id']: 'v' + str(i) for i, n in enumerate(graph['nodes'])}
        for node in renamed['nodes']: node['id'] = mapping[node['id']]
        for edge in renamed['relations']: edge['arguments'] = [mapping[a] for a in edge['arguments']]
        reviews.validate_factual_records(renamed)
        self.assertEqual(self.facts(renamed), {(p, tuple(mapping.get(a, a) for a in args)) for p, args in original})
        for changes in ({'predicate': 'undeclared_'}, {'arguments': []},
                        {'arguments': [{'node_argument': 0}, {'node_argument': 1}, '2015']},
                        {'arguments': [{'node_argument': 0}, {'node_argument': 1}, 2016]}):
            altered = deepcopy(graph)
            edge = next(e for e in altered['relations'] if e['predicate'] == 'native_factual_given'
                        and json.loads(e['value'])['predicate'] == 's152_c_1')
            record = json.loads(edge['value']); record.update(changes); edge['value'] = json.dumps(record)
            with self.assertRaises(ValueError): reviews.validate_factual_records(altered)
        altered = deepcopy(graph)
        edge = next(e for e in altered['relations'] if e['predicate'] == 'native_factual_given'
                    and json.loads(e['value'])['predicate'] == 's152_c_1')
        edge['quote'] = edge['quote'].replace('152(c)(1)', '152(c)(2)')
        with self.assertRaisesRegex(ValueError, 'exact source citation'): reviews.validate_factual_records(altered)

    def test_cumulative_manifest_retains_prior_cards_without_clients_or_labels(self):
        original = Path.read_text
        def source_only(path, *args, **kwargs):
            if path.name == 'grading.json': self.fail('source annotation opened labels')
            return original(path, *args, **kwargs)
        with (patch.object(Path, 'read_text', source_only),
             patch.object(FrozenExecutor, '__init__', side_effect=AssertionError('executor')),
             patch.object(FrozenTeacher, '__init__', side_effect=AssertionError('teacher')),
             patch.object(EvolutionLedger, '__init__', side_effect=AssertionError('ledger'))):
            out, manifest = reviews.prepare()
        self.assertEqual(len(manifest['reviews']), 32)
        self.assertEqual(manifest['previous_extra_reviews_retained'], 16)
        self.assertIsNone(manifest['interactive_root_annotation_cost_usd'])
        self.assertFalse(manifest['independent_human_or_complete_legal_gold_claimed'])
        for row in manifest['reviews']:
            card = read(ROOT / row['path'])
            self.assertTrue(card['reference_ready'])
            self.assertFalse(card['complete_native_case_gold_claimed'])
            self.assertFalse(card['native_answers_used_to_create_or_repair_graph'])
            self.assertNotEqual(card['role'], 'structure_evaluation')


if __name__ == '__main__':
    unittest.main()
