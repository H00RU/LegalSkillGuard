"""Exact-view covenant/exception scope checks without native answer feedback."""
from collections import Counter
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

from experiments import two_method_maud_covenant_source_reviews as reviews
from experiments.two_method_annotate import inputs
from experiments.two_method_graph_corpus import ROOT,read
from legal_skill_guard.paired_interfaces import graph_interface as gi
from legal_skill_guard.skill_evolution.clients import FrozenExecutor,FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger


class MAUDCovenantReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.public={s['key']:s for s in read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
        cls.locks=read(reviews.LOCK_PATH)

    def example(self,prefix,view):
        source=next(r['source'] for r in self.locks if r['source'].split(':')[1].startswith(prefix))
        task,_=inputs(self.public[source]);units=next(v['source_units'] for v in task['views'] if v['view_id']==view)
        return source,units,reviews.reviewed_graph(source,view,units)

    def nodes(self,g):return {n['id']:n for n in g['nodes']}

    def edges(self,g):return {(e['predicate'],tuple(e['arguments'])) for e in g['relations'] if e['status']=='stated'}

    def test_32_views_are16_original_mothers_not32_independent_samples(self):
        self.assertEqual(len(self.locks),32)
        mothers={r['source']:r['role'] for r in self.locks};self.assertEqual(len(mothers),16)
        self.assertEqual(Counter(mothers.values()),Counter(development=6,calibration=6,reference_only=4))
        for row in self.locks:
            _,units,g=self.example(row['source'].split(':')[1][:8],row['view']);checked=gi.validate(g,units)
            self.assertTrue(checked['schema_and_source_spans_valid']);self.assertFalse(checked['source_semantic_truth_verified'])
            self.assertFalse(g['scope_complete']);self.assertTrue(g['unresolved'])
            self.assertEqual(self.nodes(g)['main']['concept'],'obligation' if row['view']=='v1' else 'prohibition')

    def test_source_view_swap_drift_and_unread_source_cannot_inherit_review(self):
        source,units,_=self.example('cef0e433','v1');changed=deepcopy(units);changed[1]['text']+=' '
        with self.assertRaisesRegex(ValueError,'32 exact separately read'):reviews.reviewed_graph(source,'v1',changed)
        with self.assertRaisesRegex(ValueError,'32 exact separately read'):reviews.reviewed_graph(source,'v2',units)
        with self.assertRaisesRegex(ValueError,'32 exact separately read'):reviews.reviewed_graph('MAUD:unreviewed','v1',units)

    def test_subsidiary_control_is_not_a_new_direct_subsidiary_promise(self):
        for prefix,view,mode in [('7e2add3c','v1','obligation'),('7e2add3c','v2','prohibition'),('aaf70b03','v2','obligation')]:
            _,_,g=self.example(prefix,view);n=self.nodes(g);e=self.edges(g)
            self.assertEqual(n['subsidiary_control']['concept'],mode)
            self.assertIn(('actor',('subsidiary_control','company')),e)
            self.assertIn(('object',('subsidiary_control_action','subsidiary_activity')),e)
            self.assertNotIn(('actor',('main','subsidiaries')),e)
        self.assertNotIn('subsidiary_control',self.nodes(self.example('5a36bd3b','v2')[2]))

    def test_effort_standard_applies_to_conduct_and_control_not_REIT_guarantee(self):
        for prefix in ('cef0e433','04bc1032','b8241f8f','447ae333'):
            _,_,g=self.example(prefix,'v1');e=self.edges(g)
            self.assertIn(('condition',('main','main_effort_standard')),e)
            self.assertIn(('condition',('subsidiary_control','main_effort_standard')),e)
        _,_,g=self.example('04bc1032','v1');self.assertNotIn(('condition',('REIT_qualification','main_effort_standard')),self.edges(g))

    def test_no_COVID_or_definitions_are_imported_from_positive_to_negative_view(self):
        for prefix in ('9f3b4889','447ae333'):
            positive=self.example(prefix,'v1')[2];negative=self.example(prefix,'v2')[2]
            self.assertTrue(any(n['concept']=='covid_19' for n in positive['nodes']))
            self.assertFalse(any(n['concept']=='covid_19' for n in negative['nodes']))
            self.assertTrue(any('not copied' in s for s in negative['unresolved']))
        for prefix in ('294850b3','bed0af63'):
            self.assertNotIn('temporal_window',self.nodes(self.example(prefix,'v2')[2]))

    def test_195081_negative_COVID_relief_is_only_for_named_clause_subset(self):
        _,_,g=self.example('195081ce','v2');n=self.nodes(g);e=self.edges(g)
        self.assertIn(('exception_for',('COVID_scoped_negative_relief','specified_negative_clauses')),e)
        self.assertNotIn(('exception_for',('COVID_scoped_negative_relief','main')),e)
        self.assertIn('(xii)',n['specified_negative_clauses']['quote']);self.assertIn('(xvii)',n['specified_negative_clauses']['quote'])
        self.assertIn('other than',n['specified_negative_clauses']['quote'])
        self.assertIn(('condition',('consent','consent_specific_iii_iv_sole_discretion')),e)

    def test_04bc_global_section51_response_is_in_both_supplied_views(self):
        for view in ('v1','v2'):
            _,_,g=self.example('04bc1032',view);n=self.nodes(g);e=self.edges(g)
            self.assertEqual(n['section51_COVID_response']['unit_id'],1)
            self.assertIn(('exception_for',('section51_COVID_response','main')),e)
            self.assertIn(('condition',('section51_COVID_response','section51_notwithstanding_scope')),e)
            self.assertIn('taking or failing to take',n['section51_notwithstanding_scope']['quote'])
        self.assertIn(('exception_for',('section51_COVID_response','REIT_qualification')),self.edges(self.example('04bc1032','v1')[2]))

    def test_required_measures_and_resumption_conditions_are_not_blanket_permission(self):
        _,_,g=self.example('cef0e433','v1');n=self.nodes(g)
        self.assertIn('as required by applicable Law',n['COVID_required_law_eligibility']['quote'])
        _,_,g=self.example('294850b3','v2');n=self.nodes(g);e=self.edges(g)
        self.assertIn(('condition',('resume_ordinary_conduct','compliance_no_longer_required')),e)
        self.assertEqual(n['resume_ordinary_conduct_action']['concept'],'unspecified')
        self.assertIn('no longer required',n['compliance_no_longer_required']['quote'])

    def test_consent_form_Buyer_Nicolet_and_absent_law_are_not_template_filled(self):
        ordinary=self.nodes(self.example('ef95fbbc','v1')[2]);negative=self.nodes(self.example('ef95fbbc','v2')[2])
        self.assertEqual(ordinary['consent']['concept'],'written_consent')
        self.assertIn('in writing in advance',ordinary['consent']['quote'])
        self.assertEqual(negative['consent']['concept'],'unspecified')
        self.assertEqual(negative['consent']['quote'],'as approved by Parent')
        for view in ('v1','v2'):
            _,_,g=self.example('b3fc96b4',view);n=self.nodes(g);e=self.edges(g)
            self.assertIn('consenting_Buyer',n);self.assertNotIn('consenting_Parent',n);self.assertNotIn('law',n)
            self.assertIn(('object',('consent','consenting_Buyer')),e)
        self.assertIn('consenting_Nicolet',self.nodes(self.example('aaf70b03','v1')[2]))

    def test_5a36_written_consent_crosses_units_without_joining_source_text(self):
        source,units,g=self.example('5a36bd3b','v2');before=deepcopy(units);n=self.nodes(g)
        self.assertEqual(n['consent']['unit_id'],1);self.assertEqual(n['consenting_Parent']['unit_id'],2)
        self.assertEqual(n['consent']['quote'],'with the written consent')
        self.assertEqual(n['company']['name'],'Acquired Companies')
        self.assertNotIn('subsidiaries',n)
        self.assertEqual(g,reviews.reviewed_graph(source,'v2',units));self.assertEqual(before,units)
        edge=next(e for e in g['relations'] if e['predicate']=='object' and e['arguments']==['consent','consenting_Parent'])
        self.assertEqual(edge['unit_id'],2)

    def test_BancShares_CIT_opposite_party_and_Pandemic_are_literal(self):
        for view in ('v1','v2'):
            _,_,g=self.example('b1a2f5ad',view);n=self.nodes(g);e=self.edges(g)
            self.assertIn(('member_of',('BancShares','company')),e)
            self.assertIn(('member_of',('CIT','company')),e)
            self.assertNotIn('consenting_Parent',n)
            self.assertEqual(n['Pandemic_required_law']['concept'],'pandemic')
            self.assertFalse(any(x['concept']=='covid_19' for x in g['nodes']))
            self.assertIn(('condition',('consent','opposite_party_consent')),e)
        self.assertNotIn('prior',self.nodes(self.example('b1a2f5ad','v1')[2])['consent']['quote'])
        self.assertIn('prior',self.nodes(self.example('b1a2f5ad','v2')[2])['consent']['quote'])

    def test_ordinary_definitions_keep_excluding_including_and_peer_practice(self):
        _,_,g=self.example('aaf70b03','v1');quote=self.nodes(g)['ordinary_definition_own_practice_and_industry']['quote']
        self.assertIn('past practices',quote);self.assertIn('similar in nature and magnitude',quote);self.assertIn('same line of business',quote)
        quote=self.nodes(self.example('447ae333','v1')[2])['ordinary_definition_excluding_deviations_literal']['quote']
        self.assertIn('excluding any commercially reasonable deviations',quote)
        quote=self.nodes(self.example('195081ce','v1')[2])['ordinary_definition_including_deviations']['quote']
        self.assertIn('including any commercially reasonable deviations',quote)
        quote=self.nodes(self.example('b8241f8f','v1')[2])['ordinary_definition_excludes_contract_law_tort']['quote']
        self.assertIn('breach of Contract',quote);self.assertIn('including negligence',quote)

    def test_Migration_and_cross_covenant_breach_provisos_are_not_COVID_aliases(self):
        _,_,g=self.example('e4081ab8','v2');n=self.nodes(g)
        self.assertIn('Migration',n);self.assertIn('section61b_not_automatic61a_breach',n)
        self.assertFalse(any(x['concept'] in ('covid_19','pandemic') for x in g['nodes']))
        self.assertIn('otherwise constitute a breach',n['section61b_not_automatic61a_breach']['quote'])
        _,_,g=self.example('04bc1032','v1')
        self.assertIn('breach of such other provision',self.nodes(g)['section51b_subject_matter_breach_qualification']['quote'])
        _,_,g=self.example('5a36bd3b','v1')
        self.assertIn('specific provisions shall govern',self.nodes(g)['section62b_specific_provisions_govern']['quote'])

    def test_conduct_only_COVID_does_not_remove_preservation_qualifications(self):
        _,_,g=self.example('9f3b4889','v1');e=self.edges(g)
        self.assertIn(('exception_for',('COVID_conduct_response','main')),e)
        for aux in ('preserve_organization','keep_services','preserve_relations'):
            self.assertNotIn(('exception_for',('COVID_conduct_response',aux)),e)
            self.assertIn(('condition',(aux,'aux_consistent_with_conduct')),e)
        _,_,g=self.example('b8241f8f','v1');n=self.nodes(g)
        self.assertIn('additional_efforts_object_omitted',n)
        self.assertNotIn('preserve_organization',n)
        self.assertTrue(any('additional effort object is omitted' in s for s in g['unresolved']))

    def test_cumulative100_cards_retain_original68_without_labels_F_or_clients(self):
        original=Path.read_text
        def source_only(path,*args,**kwargs):
            if path.name=='grading.json':self.fail('native labels decoded')
            return original(path,*args,**kwargs)
        with (patch.object(Path,'read_text',source_only),
              patch.object(FrozenExecutor,'__init__',side_effect=AssertionError('executor')),
              patch.object(FrozenTeacher,'__init__',side_effect=AssertionError('teacher')),
              patch.object(EvolutionLedger,'__init__',side_effect=AssertionError('ledger')),
              patch('legal_skill_guard.paired_interfaces.legal_consumers.maud',side_effect=AssertionError('F evaluated')),
              patch('legal_skill_guard.paired_interfaces.control_tools.execute_skill',side_effect=AssertionError('F evaluated'))):
            out,manifest=reviews.prepare()
        self.assertEqual(len(manifest['reviews']),100);self.assertEqual(manifest['previous_extra_reviews_retained'],68)
        self.assertEqual(manifest['new_reviewed_mothers'],16);self.assertEqual(manifest['new_root_reviewed_views'],32)
        self.assertIsNone(manifest['interactive_root_annotation_cost_usd'])
        self.assertFalse(manifest['independent_human_or_complete_legal_gold_claimed'])
        for row in manifest['reviews']:
            card=read(ROOT/row['path']);self.assertTrue(card['reference_ready'])
            self.assertFalse(card['complete_native_case_gold_claimed'])
            self.assertFalse(card['native_answers_used_to_create_or_repair_graph'])
            self.assertNotEqual(card['role'],'structure_evaluation')


if __name__=='__main__':unittest.main()
