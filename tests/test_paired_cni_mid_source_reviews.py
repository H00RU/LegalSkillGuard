"""Source-bound recipient,trigger and material-scope regressions.

No native answer is computed;span/schema checks do not certify source meaning.
"""
from collections import Counter
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

from experiments import two_method_cni_mid_source_reviews as reviews
from experiments.two_method_annotate import inputs
from experiments.two_method_graph_corpus import ROOT, read
from legal_skill_guard.paired_interfaces import graph_interface as gi
from legal_skill_guard.skill_evolution.clients import FrozenExecutor,FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger


class CNIMidSourceReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.public={s['key']:s for s in read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
        cls.locks=read(reviews.LOCK_PATH)

    def example(self,prefix):
        source=next(r['source'] for r in self.locks if r['source'].split(':')[1].startswith(prefix))
        task,_=inputs(self.public[source]);self.assertEqual(len(task['views']),1)
        units=task['views'][0]['source_units'];return source,units,reviews.reviewed_graph(source,units)

    def nodes(self,graph):return {n['id']:n for n in graph['nodes']}

    def edges(self,graph):return {(e['predicate'],tuple(e['arguments'])) for e in graph['relations'] if e['status']=='stated'}

    def test_four_whole_sources_keep_original_non_development_roles_and_unknowns(self):
        self.assertEqual(Counter(r['role'] for r in self.locks),Counter(calibration=2,reference_only=2))
        for row in self.locks:
            _,units,graph=self.example(row['source'].split(':')[1][:8])
            checked=gi.validate(graph,units)
            self.assertTrue(checked['schema_and_source_spans_valid'])
            self.assertFalse(checked['source_semantic_truth_verified'])
            self.assertFalse(graph['scope_complete']);self.assertTrue(graph['unresolved'])
            self.assertGreater(len(graph['nodes']),50);self.assertGreater(len(graph['relations']),45)

    def test_source_drift_or_new_source_does_not_inherit_a_root_review(self):
        source,units,_=self.example('5cad3f37');altered=deepcopy(units);altered[31]['text']+=' '
        with self.assertRaisesRegex(ValueError,'four exact whole-source'):reviews.reviewed_graph(source,altered)
        with self.assertRaisesRegex(ValueError,'four exact whole-source'):reviews.reviewed_graph('ContractNLI:unreviewed',units)

    def test_sintec_business_end_is_not_nda_termination_and_only_staff_is_not_permission(self):
        _,_,graph=self.example('5cad3f37');nodes=self.nodes(graph);edges=self.edges(graph)
        self.assertEqual(nodes['business_end']['concept'],'unspecified')
        self.assertIn('business relation- ship',nodes['business_end']['quote'])
        self.assertIn(('trigger',('business_end_return','business_end')),edges)
        self.assertEqual(nodes['staff_disclosure_restriction']['concept'],'unspecified')
        self.assertIn(('condition',('request_destroy','destroy_no_copies')),edges)
        self.assertNotIn(('condition',('request_return','destroy_no_copies')),edges)
        self.assertEqual(nodes['possible_revocable_copy_consent']['kind'],'information')
        self.assertFalse(any(e['predicate']=='actor' and e['arguments'][0]=='no_reproduction' for e in graph['relations']))

    def test_sintec_public_exceptions_qualify_duties_not_definition(self):
        _,_,graph=self.example('5cad3f37');edges=self.edges(graph)
        self.assertIn(('exception_for',('duty_exceptions','hold_confidence')),edges)
        self.assertIn(('exception_for',('duty_exceptions','no_disclosure')),edges)
        self.assertNotIn(('exception_for',('duty_exceptions','information')),edges)

    def test_unhcr_recipient_branches_have_respective_need_and_shared_written_agreement(self):
        _,_,graph=self.example('de427b59');nodes=self.nodes(graph);edges=self.edges(graph)
        for effect in ('consented_other_party_sharing','own_personnel_sharing','related_personnel_sharing'):
            self.assertIn(('condition',(effect,'written_downstream_agreement')),edges)
        self.assertIn(('condition',('consented_other_party_sharing','other_party_consent')),edges)
        self.assertNotIn(('condition',('own_personnel_sharing','other_party_consent')),edges)
        self.assertIn(('condition',('own_personnel_sharing','own_strict_need')),edges)
        self.assertIn(('condition',('related_personnel_sharing','related_similar_need')),edges)
        self.assertNotIn(('condition',('consented_other_party_sharing','own_strict_need')),edges)
        self.assertEqual(nodes['own_officials']['concept'],'unspecified')
        self.assertEqual(nodes['affiliated_officials']['concept'],'unspecified')
        self.assertEqual(nodes['affiliated_employees']['concept'],'affiliate_employees')
        self.assertIn(('condition',('information','designated_at_disclosure')),edges)
        self.assertNotIn(('exception_for',('lawful_unrestricted_source','information')),edges)

    def test_unhcr_three_month_case_is_not_termination_or_universal_prompt_deadline(self):
        _,_,graph=self.example('de427b59');nodes=self.nodes(graph);edges=self.edges(graph)
        self.assertIn('three (3) months',nodes['no_business_in_three_months']['quote'])
        self.assertIn('both Parties have signed',nodes['no_business_in_three_months']['quote'])
        self.assertIn(('object',('disposition_cases','no_business_in_three_months')),edges)
        self.assertIn(('object',('disposition_cases','unhcr_request')),edges)
        self.assertIn(('condition',('unhcr_request','prompt_request_case')),edges)
        self.assertNotIn(('condition',('no_business_in_three_months','prompt_request_case')),edges)
        self.assertEqual(nodes['terminate_working_relationship_action']['concept'],'unspecified')
        self.assertFalse(any(n['concept']=='retention' for n in graph['nodes']))

    def test_biofiber_named_recipient_copy_consent_and_prior_notice_are_not_invented(self):
        _,_,graph=self.example('d50f9bcd');nodes=self.nodes(graph);edges=self.edges(graph)
        self.assertEqual(nodes['named_counterparty']['concept'],'unspecified')
        self.assertEqual(nodes['receiving_role']['concept'],'receiving_party')
        self.assertEqual(nodes['biofiber']['concept'],'unspecified')
        self.assertEqual(nodes['external_prior_written_consent']['concept'],'written_consent')
        self.assertEqual(nodes['no_copy_prior_consent']['concept'],'unspecified')
        self.assertEqual(nodes['no_database_storage_prior_consent']['concept'],'unspecified')
        self.assertEqual(nodes['directors']['concept'],'unspecified');self.assertEqual(nodes['officers']['concept'],'unspecified')
        self.assertIn(('condition',('required_disclosure_notice','protective_notice_purpose')),edges)
        self.assertNotIn('prior',nodes['required_disclosure_notice_action']['name'])
        self.assertFalse(any(e['predicate']=='recipient' and 'legal_advisor' in ' '.join(e['arguments']) for e in graph['relations']))

    def test_biofiber_derivative_destruction_and_certificate_are_not_return_choice(self):
        _,_,graph=self.example('d50f9bcd');nodes=self.nodes(graph);edges=self.edges(graph)
        self.assertIn(('condition',('return_embodiments','discloser_directs_choice')),edges)
        self.assertIn(('condition',('destroy_embodiments','discloser_directs_choice')),edges)
        self.assertNotIn(('condition',('destroy_derivatives','discloser_directs_choice')),edges)
        self.assertIn(('condition',('destroy_derivatives','immediate_derivative_destruction')),edges)
        self.assertIn(('condition',('destruction_certificate','certificate_if_destroyed_embodiments')),edges)
        self.assertNotIn(('condition',('return_embodiments','certificate_if_destroyed_embodiments')),edges)
        self.assertIn('officer',nodes['certificate_officer_signature']['quote'])
        for e in ('return_embodiments','destroy_embodiments','destroy_derivatives'):self.assertIn(('trigger',(e,'request')),edges)

    def test_switchdigital_search_staff_business_days_and_one_month_keep_scope(self):
        _,_,graph=self.example('d9360f2a');nodes=self.nodes(graph);edges=self.edges(graph)
        for identity in ('public_no_breach','prior_possession_limit','independent_by_or_for_recipient','other_source_no_breach','unrestricted_release','prior_written_approval'):
            self.assertIn(('condition',(identity,'combination_caveat')),edges)
        self.assertIn('exceptions in clause 1',nodes['search_including_exception_demonstration']['quote'])
        self.assertEqual(nodes['no_search']['concept'],'prohibition')
        self.assertIn('employees or directors',nodes['responsibility_staff']['quote'])
        self.assertNotIn('contractors',nodes['responsibility_staff']['quote'])
        self.assertIn('business days',nodes['two_business_days']['quote'])
        self.assertIn(('condition',('prior_consultation','before_disclosure')),edges)
        self.assertEqual(nodes['one_month_return']['quote'],'within one month')
        self.assertIn('completion of the Purpose or receipt',nodes['completion_or_written_request']['quote'])
        self.assertEqual(nodes['completion_or_written_request']['concept'],'unspecified')
        self.assertEqual(nodes['return_material']['concept'],'unspecified')
        self.assertFalse(any(n['concept'] in ('destruction','retention','affiliate_employees') for n in graph['nodes']))

    def test_cumulative_persistence_uses_no_native_labels_F_outputs_or_clients(self):
        original=Path.read_text
        def source_only(path,*args,**kwargs):
            if path.name=='grading.json':self.fail('native labels opened')
            return original(path,*args,**kwargs)
        with (patch.object(Path,'read_text',source_only),
              patch.object(FrozenExecutor,'__init__',side_effect=AssertionError('executor')),
              patch.object(FrozenTeacher,'__init__',side_effect=AssertionError('teacher')),
              patch.object(EvolutionLedger,'__init__',side_effect=AssertionError('ledger')),
              patch('legal_skill_guard.paired_interfaces.legal_consumers.contract',side_effect=AssertionError('F evaluated')),
              patch('legal_skill_guard.paired_interfaces.control_tools.execute_skill',side_effect=AssertionError('F evaluated'))):
            out,manifest=reviews.prepare()
        self.assertEqual(len(manifest['reviews']),62)
        self.assertEqual(manifest['previous_extra_reviews_retained'],58)
        self.assertIsNone(manifest['interactive_root_annotation_cost_usd'])
        self.assertFalse(manifest['independent_human_or_complete_legal_gold_claimed'])
        for row in manifest['reviews']:
            card=read(ROOT/row['path']);self.assertTrue(card['reference_ready'])
            self.assertFalse(card['complete_native_case_gold_claimed'])
            self.assertFalse(card['native_answers_used_to_create_or_repair_graph'])
            self.assertNotEqual(card['role'],'structure_evaluation')


if __name__=='__main__':unittest.main()
