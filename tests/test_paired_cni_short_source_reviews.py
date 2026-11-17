"""Whole-source transport and contract-condition scope regressions.

These checks do not turn literal span agreement into semantic certification.
No native answer is evaluated or fed back into the source graph recipes.
"""
from collections import Counter
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

from experiments import two_method_cni_short_source_reviews as reviews
from experiments.two_method_annotate import inputs
from experiments.two_method_graph_corpus import ROOT, read
from legal_skill_guard.paired_interfaces import graph_interface as gi
from legal_skill_guard.skill_evolution.clients import FrozenExecutor, FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger


class CNIShortSourceReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.public={s['key']:s for s in read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
        cls.locks=read(reviews.LOCK_PATH)

    def example(self,prefix):
        source=next(r['source'] for r in self.locks if r['source'].split(':')[1].startswith(prefix))
        task,_=inputs(self.public[source]);self.assertEqual(len(task['views']),1)
        units=task['views'][0]['source_units']
        return source,units,reviews.reviewed_graph(source,units)

    def nodes(self,graph):return {n['id']:n for n in graph['nodes']}

    def edges(self,graph):return {(e['predicate'],tuple(e['arguments']),e['status']) for e in graph['relations']}

    def test_six_original_whole_sources_keep_roles_units_and_partial_scope(self):
        self.assertEqual(Counter(r['role'] for r in self.locks),Counter(development=4,calibration=1,reference_only=1))
        for row in self.locks:
            source,units,graph=self.example(row['source'].split(':')[1][:8])
            checks=gi.validate(graph,units)
            self.assertTrue(checks['schema_and_source_spans_valid'])
            self.assertFalse(checks['source_semantic_truth_verified'])
            self.assertFalse(graph['scope_complete']);self.assertTrue(graph['unresolved'])
            self.assertGreater(len(graph['nodes']),20)
            self.assertGreater(len(graph['relations']),20)
            self.assertTrue(all(e['unit_id'] in {u['id'] for u in units} for e in graph['relations']))

    def test_source_drift_and_unreviewed_sources_are_rejected(self):
        source,units,_=self.example('a5b0361f');changed=deepcopy(units);changed[6]['text']+=' '
        with self.assertRaisesRegex(ValueError,'six exact whole-source'):reviews.reviewed_graph(source,changed)
        with self.assertRaisesRegex(ValueError,'six exact whole-source'):reviews.reviewed_graph('ContractNLI:unreviewed',units)

    def test_repeated_name_uses_its_explicit_original_unit(self):
        _,units,graph=self.example('ef7bf53e');node=self.nodes(graph)['liberty']
        self.assertEqual(node['unit_id'],4);self.assertEqual(node['quote'],'Liberty Technologies, Inc.')
        self.assertGreater(sum(u['text'].count(node['quote']) for u in units),1)
        helper=reviews.ClauseGraph(units)
        with self.assertRaises(ValueError):helper.n('bad','organization','unspecified',0,quote='Liberty Technologies, Inc.')
        with self.assertRaises(ValueError):helper.n('invented','organization','unspecified',4,name='Different Company')

    def test_tour_consent_scopes_do_not_cross_to_recording(self):
        _,_,graph=self.example('a5b0361f');nodes=self.nodes(graph);edges=self.edges(graph)
        self.assertEqual(nodes['consent']['concept'],'unspecified')
        self.assertEqual(nodes['removal_written_consent']['concept'],'written_consent')
        self.assertIn(('condition',('no_disclosure','consent'),'stated'),edges)
        self.assertIn(('condition',('no_removal','removal_written_consent'),'stated'),edges)
        self.assertNotIn(('condition',('no_record','removal_written_consent'),'stated'),edges)
        self.assertNotIn(('condition',('no_record','consent'),'stated'),edges)
        self.assertFalse(any(n['concept'] in ('return','destruction','retention') for n in graph['nodes']))

    def test_company_request_and_exam_candidate_do_not_become_termination_or_identity(self):
        _,_,graph=self.example('bc93d2a7');nodes=self.nodes(graph);edges=self.edges(graph)
        self.assertEqual(nodes['all_return_material']['concept'],'all_confidential_information_and_copies')
        self.assertEqual(nodes['written_request']['concept'],'request')
        self.assertIn(('trigger',('return','written_request'),'stated'),edges)
        self.assertEqual(nodes['exam_candidate']['concept'],'unspecified')
        self.assertNotIn(('member_of',('exam_candidate','recipient'),'stated'),edges)
        self.assertFalse(any(n['concept'] in ('termination','termination_or_request') for n in graph['nodes']))
        self.assertEqual(nodes['written_disclosure_agreement']['kind'],'exception')
        self.assertNotEqual(nodes['written_disclosure_agreement']['concept'],'permission')

    def test_unchecked_form_blank_deadline_and_conditional_section_are_not_filled(self):
        _,_,graph=self.example('8fb38aee');nodes=self.nodes(graph);edges=self.edges(graph)
        for option in ('unilateral_option','mutual_option'):
            self.assertIn(('condition',('selection',option),'unknown'),edges)
        self.assertEqual(nodes['first']['concept'],'unspecified');self.assertEqual(nodes['second']['concept'],'unspecified')
        self.assertEqual(nodes['blank_return_deadline']['quote'],'within ____ days')
        self.assertEqual(nodes['materials']['concept'],'unspecified')
        for effect in ('hold_confidence','no_publication','no_copy','no_sole_benefit_use','return'):
            self.assertIn(('condition',(effect,'sectionV_unilateral_exception'),'stated'),edges)
        self.assertFalse(any(n['concept']=='retention' for n in graph['nodes']))
        self.assertFalse(any(n['concept']=='permission' for n in graph['nodes']))

    def test_college_disposition_choice_and_notice_deadline_keep_different_scopes(self):
        _,_,graph=self.example('78adf3b3');nodes=self.nodes(graph);edges=self.edges(graph)
        self.assertEqual(nodes['employees']['concept'],'own_employees')
        self.assertEqual(nodes['contractors']['concept'],'contractors')
        for condition in ('sharing_need_to_know','sharing_written_confidentiality'):
            self.assertIn(('condition',('limited_sharing',condition),'stated'),edges)
        self.assertIn(('trigger',('return','request'),'stated'),edges)
        self.assertIn(('condition',('certify_destruction','disposition_choice'),'stated'),edges)
        self.assertEqual(nodes['certify_destruction_action']['concept'],'unspecified')
        self.assertIn('five days',nodes['notice_delivery_receipt_rules']['quote'])
        self.assertNotIn(('condition',('return','notice_delivery_receipt_rules'),'stated'),edges)
        self.assertNotEqual(nodes['copy_material']['concept'],'all_confidential_information_and_copies')

    def test_mutual_three_way_trigger_passive_actor_and_advisor_limits(self):
        _,_,graph=self.example('96361e4d');nodes=self.nodes(graph);edges=self.edges(graph)
        self.assertEqual(nodes['advisors']['concept'],'unspecified')
        self.assertEqual(nodes['limited_sharing']['concept'],'unspecified')
        self.assertEqual(nodes['disposition_trigger']['concept'],'unspecified')
        self.assertIn('termination or expiration',nodes['disposition_trigger']['quote'])
        self.assertIn('or upon written request',nodes['disposition_trigger']['quote'])
        self.assertFalse(any(e['predicate']=='actor' and e['arguments'][0]=='no_reproduction' for e in graph['relations']))
        self.assertIn(('condition',('certify','certification_destroy_only'),'stated'),edges)
        self.assertNotIn(('condition',('return','certification_destroy_only'),'stated'),edges)
        self.assertEqual(nodes['hold_confidence']['concept'],'obligation')
        self.assertFalse(any(n['concept']=='retention' for n in graph['nodes']))

    def test_crane_prepared_subset_law_exception_and_notice_are_separate(self):
        _,_,graph=self.example('ef7bf53e');nodes=self.nodes(graph);edges=self.edges(graph)
        self.assertEqual(nodes['limited_sharing']['concept'],'unspecified')
        self.assertEqual(nodes['accountants']['concept'],'unspecified')
        self.assertEqual(nodes['financial_advisors']['concept'],'financial_advisors')
        self.assertEqual(nodes['prepared_subset']['concept'],'some_confidential_information')
        self.assertNotEqual(nodes['returned_subset']['concept'],'all_confidential_information_and_copies')
        self.assertIn(('condition',('return','prepared_document_exclusion'),'stated'),edges)
        self.assertIn(('condition',('discussion_nondisclosure','discussion_consent_or_law'),'stated'),edges)
        self.assertNotIn(('condition',('no_disclosure','discussion_consent_or_law'),'stated'),edges)
        for actor in ('crane','agents','representatives','employees'):
            self.assertIn(('actor',('no_disclosure',actor),'stated'),edges)
        notice=nodes['compulsion_notice_action']['name']
        self.assertIn('written notice and oral notice',notice)
        self.assertFalse(any(e['predicate']=='recipient' and e['arguments'][0]=='limited_compelled_disclosure' for e in graph['relations']))

    def test_cumulative_manifest_persistence_never_opens_labels_or_calls_F_clients(self):
        original=Path.read_text
        def source_only(path,*args,**kwargs):
            if path.name=='grading.json':self.fail('Source annotation opened labels')
            return original(path,*args,**kwargs)
        with (patch.object(Path,'read_text',source_only),
              patch.object(FrozenExecutor,'__init__',side_effect=AssertionError('executor')),
              patch.object(FrozenTeacher,'__init__',side_effect=AssertionError('teacher')),
              patch.object(EvolutionLedger,'__init__',side_effect=AssertionError('ledger')),
              patch('legal_skill_guard.paired_interfaces.legal_consumers.contract',side_effect=AssertionError('F evaluated')),
              patch('legal_skill_guard.paired_interfaces.control_tools.execute_skill',side_effect=AssertionError('F evaluated'))):
            out,manifest=reviews.prepare()
        self.assertEqual(len(manifest['reviews']),58)
        self.assertEqual(manifest['previous_extra_reviews_retained'],52)
        self.assertIsNone(manifest['interactive_root_annotation_cost_usd'])
        self.assertFalse(manifest['independent_human_or_complete_legal_gold_claimed'])
        for row in manifest['reviews']:
            card=read(ROOT/row['path'])
            self.assertTrue(card['reference_ready'])
            self.assertFalse(card['complete_native_case_gold_claimed'])
            self.assertFalse(card['native_answers_used_to_create_or_repair_graph'])
            self.assertNotEqual(card['role'],'structure_evaluation')


if __name__=='__main__':
    unittest.main()
