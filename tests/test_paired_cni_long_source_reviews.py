"""Source-only scope regressions for the final six CNI contracts.

No native score or F output certifies an annotation. Every graph stays partial.
"""
from collections import Counter
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

from experiments import two_method_cni_long_source_reviews as reviews
from experiments.two_method_annotate import inputs
from experiments.two_method_graph_corpus import ROOT,read
from legal_skill_guard.paired_interfaces import graph_interface as gi
from legal_skill_guard.skill_evolution.clients import FrozenExecutor,FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger


class CNILongSourceReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.public={s['key']:s for s in read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
        cls.locks=read(reviews.LOCK_PATH)

    def example(self,prefix):
        source=next(r['source'] for r in self.locks if r['source'].split(':')[1].startswith(prefix))
        task,_=inputs(self.public[source]);self.assertEqual(len(task['views']),1)
        units=task['views'][0]['source_units'];return source,units,reviews.reviewed_graph(source,units)

    def nodes(self,g):return {n['id']:n for n in g['nodes']}

    def edges(self,g):return {(e['predicate'],tuple(e['arguments'])) for e in g['relations'] if e['status']=='stated'}

    def test_all_six_whole_sources_keep_roles_partial_scope_and_exact_spans(self):
        self.assertEqual(Counter(r['role'] for r in self.locks),Counter(development=2,calibration=3,reference_only=1))
        for r in self.locks:
            _,units,g=self.example(r['source'].split(':')[1][:8]);checked=gi.validate(g,units)
            self.assertTrue(checked['schema_and_source_spans_valid']);self.assertFalse(checked['source_semantic_truth_verified'])
            self.assertFalse(g['scope_complete']);self.assertTrue(g['unresolved'])
            self.assertGreater(len(g['nodes']),70);self.assertGreater(len(g['relations']),60)

    def test_changed_or_unreviewed_source_cannot_inherit_semantic_review(self):
        source,units,_=self.example('4d4e550a');changed=deepcopy(units);changed[35]['text']+=' '
        with self.assertRaisesRegex(ValueError,'six exact remaining CNI'):reviews.reviewed_graph(source,changed)
        with self.assertRaisesRegex(ValueError,'six exact remaining CNI'):reviews.reviewed_graph('ContractNLI:unreviewed',units)

    def test_samsung_affiliate_and_own_access_scopes_remain_different(self):
        _,_,g=self.example('4d4e550a');n=self.nodes(g);e=self.edges(g)
        self.assertEqual(n['affiliate_employees']['concept'],'affiliate_employees')
        self.assertEqual(n['affiliate_officers']['concept'],'unspecified')
        self.assertEqual(n['affiliate_sharing']['concept'],'permission')
        self.assertEqual(n['own_access_restriction']['concept'],'unspecified')
        self.assertIn('as of Effective Date',n['affiliate_control_definition']['quote'])
        self.assertIn('controls or is under common control',n['affiliate_control_definition']['quote'])
        self.assertIn(('actor',('company_unit_restriction','company')),e)
        self.assertNotIn(('actor',('company_unit_restriction','samsung')),e)

    def test_samsung_archival_copy_and_two_ten_day_clocks_do_not_merge(self):
        _,_,g=self.example('4d4e550a');n=self.nodes(g);e=self.edges(g)
        self.assertIn(('exception_for',('archival_retention','return')),e)
        self.assertEqual(n['archival_copy']['concept'],'some_confidential_information')
        self.assertEqual(n['sole_archival_purpose']['quote'],'solely for archival purpose')
        self.assertIn('after any notice thereof by Discloser',n['immediate_notice_based10day_limit']['quote'])
        self.assertIn('10 days written notice',n['termination10day_written_notice']['quote'])
        self.assertIn('5 years from the date on which',n['purpose_use_ends_five_years_from_disclosure']['quote'])
        self.assertIn('right terminates when this Agreement terminates',n['purpose_use_ends_five_years_from_disclosure']['quote'])

    def test_CERT_product_and_result_copy_bans_keep_different_consent(self):
        _,_,g=self.example('e7b78d42');n=self.nodes(g);e=self.edges(g)
        self.assertIn(('condition',('no_result_copy','result_copy_written_consent')),e)
        self.assertNotIn(('condition',('no_product_copy','result_copy_written_consent')),e)
        self.assertNotIn(('condition',('no_product_copy_retention','result_copy_written_consent')),e)
        self.assertIn(('exception_for',('public_without_breach','article2')),e)
        self.assertNotIn(('exception_for',('public_without_breach','no_affiliate_external_disclosure')),e)
        self.assertEqual(n['prior_written_information']['concept'],'unspecified')
        self.assertIn('information to the auditee',n['prior_written_information']['quote'])

    def test_CERT_country_rules_conflict_is_preserved_not_resolved(self):
        _,_,g=self.example('e7b78d42');n=self.nodes(g);e=self.edges(g)
        self.assertIn(('condition',('conditional_no_outside_India','outside_written_consent')),e)
        self.assertNotIn(('condition',('absolute_no_outside_country','outside_written_consent')),e)
        self.assertEqual(n['absolute_country_text']['quote'],'outside the country in any circumstances')
        self.assertTrue(any('unresolved priority' in s for s in g['unresolved']))
        self.assertEqual(n['auditee']['concept'],'unspecified')
        self.assertIn('expiration or termination',n['agreement_end']['quote'])

    def test_CSBS_duplicate_backup_legal_copy_units_and_targets_are_kept(self):
        _,_,g=self.example('6fce8464');n=self.nodes(g);e=self.edges(g)
        self.assertEqual(n['backup_no_deletion_4']['unit_id'],17);self.assertEqual(n['backup_no_deletion_5']['unit_id'],25)
        self.assertEqual(n['legal_copy_retention_4']['unit_id'],18);self.assertEqual(n['legal_copy_retention_5']['unit_id'],26)
        self.assertEqual(n['backup_no_deletion_4']['kind'],'exception')
        self.assertEqual(n['legal_copy_retention_4']['concept'],'permission')
        self.assertEqual(n['dispute_resolution_only_4']['quote'],'for dispute resolution purposes only')
        self.assertIn(('exception_for',('legal_copy_retention_4','project_end_destroy')),e)
        self.assertIn(('exception_for',('legal_copy_retention_5','nda_return')),e)
        self.assertNotIn(('exception_for',('legal_copy_retention_5','cease_use')),e)
        self.assertFalse(any(x['concept'] in ('legal_advisors','affiliate_employees') for x in g['nodes']))

    def test_CSBS_project_nda_demand_and_actual_GC_notice_cases_keep_scope(self):
        _,_,g=self.example('6fce8464');n=self.nodes(g);e=self.edges(g)
        self.assertIn('termination of the Project',n['project_end']['quote'])
        self.assertIn('receipt of demand',n['demand_receipt10business_days']['quote'])
        self.assertNotIn(('condition',('project_request_return','project_end10business_days')),e)
        self.assertIn('General Counsel of <Vendor Name Here>',n['vendor_case_notice_case']['quote'])
        self.assertIn(('recipient',('vendor_case_notice','vendor_GC')),e)
        self.assertIn(('recipient',('company_case_notice','company_GC')),e)
        self.assertNotIn('written',n['vendor_case_notice_action']['name'])
        self.assertIn('Vendor Name Here',n['Vendor_regulatory_responsibilities']['quote'])

    def test_cyber_five_day_receipt_and_seven_day_post_notice_are_separate(self):
        _,_,g=self.example('442c36c1');n=self.nodes(g);e=self.edges(g)
        self.assertIn('five (5) business days of receipt',n['legal_process_five_business_days_from_receipt']['quote'])
        self.assertIn('seven (7) business days following',n['seven_business_days_after_notification']['quote'])
        self.assertIn(('condition',('emergency_internal_sharing','actual_threatened_system_risk')),e)
        self.assertIn(('condition',('emergency_use','actual_threatened_system_risk')),e)
        self.assertEqual(n['express_permission_not_written']['concept'],'unspecified')
        self.assertFalse(any(x['concept'] in ('own_employees','legal_advisors','financial_advisors') for x in g['nodes']))

    def test_cyber_return_termination_backup_process_and_legal_record_have_scopes(self):
        _,_,g=self.example('442c36c1');n=self.nodes(g);e=self.edges(g)
        self.assertIn(('trigger',('return','termination')),e)
        self.assertEqual(n['backup_process_destruction']['concept'],'obligation')
        self.assertEqual(n['legal_record_retention']['concept'],'permission')
        self.assertEqual(n['required_by_applicable_law']['quote'],'if required to do so by applicable law')
        self.assertFalse(any(x['concept'] in ('request','termination_or_request') for x in g['nodes']))

    def test_shire_missing_exhibits_party_scopes_and_adviser_classes_are_not_filled(self):
        _,_,g=self.example('8af247c6');n=self.nodes(g);e=self.edges(g)
        for actor in ('shire','lek','new_river'):
            effect=actor+'_existence_restriction'
            self.assertIn(('actor',(effect,actor)),e)
            self.assertIn(('information',(effect,'agreement_discussions')),e)
            for exhibit in ('exhibit_A','exhibit_B','exhibit_C'):
                self.assertIn(('condition',(effect,exhibit)),e)
                self.assertEqual(n[exhibit]['concept'],'unspecified')
        self.assertFalse(any(x['predicate']=='member_of' and x['arguments'][-1] in ('exhibit_A','exhibit_B','exhibit_C') for x in g['relations']))
        self.assertEqual(n['legal_advisors']['concept'],'legal_advisors')
        self.assertEqual(n['financial_advisors']['concept'],'financial_advisors')
        self.assertEqual(n['accountants']['concept'],'unspecified')

    def test_shire_compliance_copy_is_request_scoped_not_CSBS_dispute_copy(self):
        _,_,g=self.example('8af247c6');n=self.nodes(g);e=self.edges(g)
        self.assertIn(('trigger',('return','request')),e)
        self.assertIn(('exception_for',('single_compliance_retention','return')),e)
        self.assertIn('regulatory compliance and compliance',n['regulatory_and_agreement_compliance']['quote'])
        self.assertIn('outside legal counsel',n['legal_department_or_outside_counsel']['quote'])
        self.assertEqual(n['removal_consent_not_written']['concept'],'unspecified')
        self.assertNotIn('prior written',n['authority_notice_efforts_action']['name'])

    def test_JLT_target_material_and_finance_roles_do_not_expand(self):
        _,_,g=self.example('bbb39011');n=self.nodes(g);e=self.edges(g)
        self.assertEqual(n['target_information']['concept'],'some_confidential_information')
        self.assertIn(('object',('target_information','agreement_component')),e)
        self.assertNotIn(('object',('target_information','group_shareholder_information')),e)
        self.assertIn(('exception_for',('target_special_recipients','target_information_nondisclosure')),e)
        self.assertNotIn(('exception_for',('target_special_recipients','full_information_nondisclosure')),e)
        self.assertEqual(n['professional_advisers']['concept'],'unspecified')
        self.assertEqual(n['finance_providers']['concept'],'unspecified')
        self.assertEqual(n['goldman']['concept'],'unspecified')
        self.assertIn('paragraph 6.3.2',n['professional_finance_632_only_exception']['quote'])

    def test_JLT_retention_alternatives_consultation_and_OCR_date_are_preserved(self):
        _,_,g=self.example('bbb39011');n=self.nodes(g);e=self.edges(g)
        for effect in ('law_reg_retention','internal_compliance_retention','impracticable_routine_backups_retention'):
            self.assertEqual(n[effect]['concept'],'permission')
            self.assertIn(('condition',(effect,effect+'_ground')),e)
        self.assertIn(('condition',('return','recipient_choice')),e)
        self.assertNotIn(('condition',('destroy_derivatives','recipient_choice')),e)
        self.assertIn('not possible before',n['if_prior_consult_impossible_as_soon_practicable']['quote'])
        self.assertIn('Geoffrey Howe or Derek Walsh',n['company_consent_givers']['quote'])
        self.assertEqual(n['assignment_consent_not_written']['concept'],'unspecified')
        self.assertIn('201$',n['OCR_signature_date_unresolved']['quote'])
        self.assertIn('following your Recommended Offer',n['15percent_after_recommended_offer']['quote'])

    def test_cumulative68_persistence_uses_no_labels_F_or_model_clients(self):
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
        self.assertEqual(len(manifest['reviews']),68);self.assertEqual(manifest['previous_extra_reviews_retained'],62)
        self.assertIsNone(manifest['interactive_root_annotation_cost_usd'])
        self.assertFalse(manifest['independent_human_or_complete_legal_gold_claimed'])
        for row in manifest['reviews']:
            card=read(ROOT/row['path']);self.assertTrue(card['reference_ready'])
            self.assertFalse(card['complete_native_case_gold_claimed'])
            self.assertFalse(card['native_answers_used_to_create_or_repair_graph'])
            self.assertNotEqual(card['role'],'structure_evaluation')


if __name__=='__main__':unittest.main()
