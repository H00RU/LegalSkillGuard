"""Explicit whole-source reviews of the six final CNI TRAIN contracts.

Recipes are added only after the entire corresponding supplied source is
read. No native questions,labels,F results or weak responses repair a graph.
"""
from collections import Counter
from pathlib import Path
import json

from experiments.two_method_annotate import inputs
from experiments.two_method_graph_corpus import ROOT, BASE, read, sha
from experiments.two_method_cni_short_source_reviews import ClauseGraph
from experiments.two_method_cni_mid_source_reviews import prepare as previous_reviews
from legal_skill_guard.paired_interfaces import graph_interface as gi
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


LOCK_PATH=ROOT/'experiments/source_review_locks/cni_final6_20261117.json'


def samsung(g):
    g.n('samsung','organization','unspecified',4,name='Samsung Electronics Co., Ltd.')
    g.n('company','organization','unspecified',5,name='Company')
    g.n('parties','group','either_party',6,name='parties')
    g.n('discloser','group','disclosing_party',10,name='Discloser')
    g.n('recipient','group','receiving_party',10,name='Recipient')
    g.n('information','information','confidential_information',10)
    g.qualify('written_marking_branch',11,['information'])
    g.qualify('oral_visual_identification_and15days_confirmation',12,['information'])
    g.n('affiliates','group','unspecified',13,name='affiliates')
    for identity,concept,name in [('affiliate_officers','unspecified','officers'),('affiliate_directors','unspecified','directors'),('affiliate_employees','affiliate_employees','employees')]:
        g.n(identity,'group',concept,13,name=name);g.r('member_of',identity,'affiliates',13)
    g.effect('affiliate_sharing','permission',13,'recipient','disclosure','disclose',material='information',recipients=['affiliates'])
    g.qualify('affiliate_restricted_access',13,['affiliate_sharing'])
    g.qualify('affiliate_need_purpose',13,['affiliate_sharing'],concept='need_to_know',quote='who have a legitimate need-to-know to carry out the Purpose')
    g.qualify('affiliate_no_less_protective_terms',13,['affiliate_sharing'],quote='who are obligated to protect such Confidential Information pursuant to terms and conditions no less protective of Discloser than those contained in this Agreement')
    g.qualify('affiliate_control_definition',14,['affiliates'])
    g.effect('hold_confidence','obligation',16,'recipient','unspecified','receive and hold',material='information')
    g.qualify('same_care_reasonable_floor',16,['hold_confidence'])
    g.n('third_parties','group','other_third_parties',18,name='third party')
    g.effect('no_disclosure','prohibition',18,'recipient','disclosure','disclose',material='information',recipients=['third_parties'])
    g.effect('purpose_only_use','prohibition',19,'recipient','unspecified','use',material='information')
    g.qualify('furtherance_of_purpose',19,['purpose_only_use'])
    for identity,concept,name in [('own_officers','unspecified','officers'),('own_directors','unspecified','directors'),('own_employees','own_employees','employees')]:g.n(identity,'group',concept,20,name=name)
    g.effect('own_access_restriction','unspecified',20,'recipient','unspecified','restrict access',material='information',recipients=['own_officers','own_directors','own_employees'])
    g.qualify('own_need_purpose_bound_terms',20,['own_access_restriction'])
    g.effect('no_copy','prohibition',21,'recipient','unspecified','reproduce or copy',material='information')
    g.qualify('necessary_purpose_copy_exception',21,['no_copy'])
    g.n('negotiations','information','unspecified',22,name='the existence of any business negotiations, discussions or agreements in progress')
    g.effect('negotiation_nondisclosure','prohibition',22,'parties','disclosure','disclosed',material='negotiations')
    g.qualify('all_parties_written_approval',22,['negotiation_nondisclosure'],concept='written_consent',quote='without written approval of all the parties')
    g.n('other_units','group','unspecified',23,quote='any other division, department, group, or unit other than Samsung KNOX Business and Technology Division')
    g.effect('company_unit_restriction','prohibition',23,'company','disclosure','disclose',material='information',recipients=['other_units'])
    g.n('exclusions_header','condition','unspecified',25)
    section2=['hold_confidence','no_disclosure','purpose_only_use','own_access_restriction','no_copy','company_unit_restriction']
    for identity,unit in [('public_no_default',26),('prior_rightful_possession',27),('good_faith_free_source',28),('unrestricted_unaffiliated_release',29),('independent_without_use',30)]:
        g.n(identity,'exception','unspecified',unit);g.r('exception_for',identity,'information',unit)
        for effect in section2:g.r('exception_for',identity,effect,unit)
        g.r('condition',identity,'exclusions_header',25)
    g.n('law_valid_order_nonbreach','exception','unspecified',31);g.r('exception_for','law_valid_order_nonbreach','no_disclosure',31)
    g.effect('law_notice','obligation',31,'recipient','unspecified','provide prompt prior written notice',recipients=['discloser'])
    g.qualify('valid_order_or_required_law',31,['law_valid_order_nonbreach','law_notice'])
    g.qualify('no_other_confidentiality_waiver',31,['law_valid_order_nonbreach'],quote='or a waiver of confidentiality for other purposes')
    g.r('owner','information','discloser',33);g.statement('no_license',33)
    g.effect('proprietary_notice_reproduction','obligation',34,'recipient','unspecified','reproduce the symbols, legends or other proprietary notices',material='information')
    g.effect('no_notice_modification','prohibition',34,'recipient','unspecified','remove, add or modify',material='information')
    g.n('all_copies','information','unspecified',35,quote='all copies of such Discloser’s Confidential Information')
    g.n('disposal_trigger','condition','termination_or_request',35,quote='upon termination of this Agreement, or upon written request of Discloser, whichever is earlier')
    g.effect('return','obligation',35,'recipient','return','return',material='all_copies',recipients=['discloser'])
    g.effect('destroy','obligation',35,'recipient','destruction','destroy',material='all_copies')
    g.effect('compliance_certificate','obligation',35,'recipient','unspecified','certify in writing')
    for e in ['return','destroy','compliance_certificate']:g.r('trigger',e,'disposal_trigger',35)
    g.qualify('discloser_destruction_option',35,['return','destroy'],quote='or destroy at Discloser’s option')
    g.qualify('immediate_notice_based10day_limit',35,['return','destroy'],quote='immediately, but not later than 10 days after any notice thereof by Discloser')
    g.n('archival_copy','information','some_confidential_information',35,quote='a copy of such Confidential Information')
    g.effect('archival_retention','permission',35,'recipient','retention','retain',material='archival_copy')
    g.r('exception_for','archival_retention','return',35);g.r('exception_for','archival_retention','destroy',35)
    g.qualify('sole_archival_purpose',35,['archival_retention'],quote='solely for archival purpose')
    g.effect('no_reverse_engineering','prohibition',37,'recipient','unspecified','decompile',material='information')
    g.qualify('specific_advance_written_authorization',37,['no_reverse_engineering'],concept='written_consent')
    g.effect('own_expenses','obligation',44,'parties','unspecified','bear its own fees, costs and expenses')
    g.effect('terminate_on_notice','permission',49,'parties','termination','terminate')
    g.qualify('termination10day_written_notice',49,['terminate_on_notice'])
    g.effect('export_compliance','obligation',57,'parties','unspecified','comply with all applicable US and other export laws')
    g.qualify('required_export_licenses',57,['export_compliance'])
    for identity,unit in [('click_acceptance_condition',1),('registration_effective_date',3),('as_is',39),('no_transaction_commitment',40),('no_product_promise',41),('separate_signed_commitments',42),('warranty_priority',43),('independent_development_without_use',46),('24month_term',48),('confidence_survival',50),('purpose_use_ends_five_years_from_disclosure',51),('specified_sections_survive',52),('English_notice_delivery',54),('missing_registration_record',55),('conditional_harm',59),('right_apply_relief',60),('assignment_consent',62),('signed_waiver',64),('nonwaiver',65),('severability_condition',67),('economic_replacement',68),('remaining_validity',69),('Korean_law',71),('arbitration_IP_court_exception',72),('binding_award',73),('arbitration_confidence_exception',74),('integration_signed_amendment',76),('English_prevails',77),('purpose_contract_extension_not_shortening',78),('counterparts',80),('pdf_delivery',81),('electronic_signature_statement',82),('acceptance_authority',83)]:g.statement(identity,unit)
    return ['Registration date,Company identity,actual acceptance and disclosure dates are not provided;no actual signature,control state or consent is inferred.',
        'Written marking OR oral/visual identification plus15-day written confirmation are different definition paths.',
        'Affiliate definition is as written at Effective Date and while control exists;do not add a missing controlled-by relation or equate officers/directors with employees.',
        'Own access restrictions and affiliate permission retain their respective conditions;Company unit restriction is named-party-specific,not rewritten as a blanket Samsung organization chart.',
        'Return/destroy concerns all copies,with one archival-copy exception;ten-day maximum starts from Discloser notice,while separate early termination requires ten-day written notice.',
        'Purpose-use right ends at termination;five-year protection runs from each disclosure,not termination. Later Purpose-contract incorporation may extend but not shorten the term.',
        'Arbitration confidentiality/IP-court,export,warranty and full Boolean/temporal/reciprocal legal mechanics remain incompletely formalized;electronic-signature text is source data,not an action taken.']


def cert_audit(g):
    g.n('auditee','group','unspecified',9,name='Auditee')
    g.n('auditor','organization','receiving_party',17,name='Auditor')
    g.n('parties','group','either_party',22,name='parties')
    g.n('information','information','confidential_information',24)
    g.n('audit_results','information','confidential_information',25)
    g.n('product_details','information','unspecified',31)
    for identity,unit in [('alternative_government_auditee',7),('alternative_corporate_auditee',14),('empanelment',18),('unprovided_auditor_guidelines',19),('auditee_guideline_awareness',20),('guideline_commitment',21),('products_definition',26)]:g.statement(identity,unit)
    g.effect('audit_only_use','obligation',29,'auditor','unspecified','Use',material='information')
    g.qualify('audit_scope_purpose',29,['audit_only_use'])
    g.effect('hold_confidence','obligation',30,'auditor','unspecified','Maintain',material='information')
    g.qualify('reasonable_steps_and_own_client_care',30,['hold_confidence'])
    g.effect('no_product_copy','prohibition',31,'auditor','unspecified','make',material='product_details')
    g.effect('no_product_copy_retention','prohibition',31,'auditor','retention','retain',material='product_details')
    g.effect('no_result_copy','prohibition',32,'auditor','unspecified','make',material='audit_results')
    g.effect('no_result_copy_retention','prohibition',32,'auditor','retention','retain',material='audit_results')
    g.qualify('result_copy_written_consent',32,['no_result_copy','no_result_copy_retention'],concept='written_consent',quote='without the express written consent of Auditee')
    g.n('other_persons','group','other_third_parties',33,name='any other person or entity')
    g.effect('no_disclosure','prohibition',33,'auditor','disclosure','disclosure',material='information',recipients=['other_persons'])
    g.qualify('disclosure_written_consent',33,['no_disclosure'],concept='written_consent',quote='without the express written consent of theauditee')
    g.n('tangible_scope','information','unspecified',34)
    g.effect('return','obligation',34,'auditor','return','Return',material='tangible_scope',recipients=['auditee'])
    g.effect('destroy','obligation',34,'auditor','destruction','destroy',material='tangible_scope')
    g.qualify('auditee_discretion_choice',34,['return','destroy'],quote='at auditee’s discretion')
    g.n('agreement_end','condition','unspecified',35);g.n('auditee_request','condition','request',36)
    g.n('end_or_request','condition','unspecified',34,quote='immediately on')
    g.r('object','end_or_request','agreement_end',35);g.r('object','end_or_request','auditee_request',36)
    for e in ['return','destroy']:g.r('trigger',e,'end_or_request',34)
    g.effect('conditional_no_outside_India','prohibition',37,'auditor','unspecified','send',material='information')
    g.qualify('outside_storage_processing_scope',37,['conditional_no_outside_India'])
    g.qualify('outside_written_consent',37,['conditional_no_outside_India'],concept='written_consent',quote='without the express written consent of the Auditee')
    g.effect('secure_methodology','obligation',38,'auditor','unspecified','use only the best possible secure methodology',material='information')
    g.effect('no_nonresident_engagement','prohibition',39,'auditor','unspecified','engage or appoint')
    g.qualify('audit_personnel_scope',39,['no_nonresident_engagement'])
    g.effect('declared_manpower_only','obligation',40,'auditor','unspecified','deployed')
    g.qualify('government_critical_sector_case',40,['declared_manpower_only'])
    g.n('arrangement_services','information','unspecified',41)
    g.effect('no_public_discussion','prohibition',41,'auditor','disclosure','discuss',material='arrangement_services')
    g.effect('mandatory_employee_consultant_NDAs','obligation',42,'auditor','unspecified','Make sure')
    g.qualify('signed_NDA_for_engaged_auditors',42,['mandatory_employee_consultant_NDAs'])
    g.n('article2','group','unspecified',27)
    article2=['audit_only_use','hold_confidence','no_product_copy','no_product_copy_retention','no_result_copy','no_result_copy_retention','no_disclosure','return','destroy','conditional_no_outside_India','secure_methodology','no_nonresident_engagement','declared_manpower_only','no_public_discussion','mandatory_employee_consultant_NDAs']
    for e in article2:g.r('object','article2',e,27)
    g.effect('exception_proof_burden','obligation',44,'auditor','unspecified','burden of proving')
    g.n('mandated_agencies','group','unspecified',46,quote='CERT-In or similar Government entities mandated under the law')
    g.effect('agency_sharing','permission',46,'auditor','disclosure','share',material='audit_results',recipients=['mandated_agencies'])
    g.qualify('agency_calls_upon',46,['agency_sharing'],quote='as and when called upon to do so by such agencies')
    g.qualify('prior_written_information',46,['agency_sharing'],quote='with prior written information to the auditee')
    for identity,unit in [('independent_or_lawful_source',49),('public_without_breach',50),('known_documented_free',51),('auditee_written_release',52),('unbound_third_party',53)]:
        g.n(identity,'exception','unspecified',unit);g.r('exception_for',identity,'article2',48)
    g.n('own_employees','group','own_employees',62,name='employees')
    g.n('consultants','group','consultants',62,name='consultants')
    g.effect('own_need_to_know_restriction','unspecified',62,'auditor','disclosure','disclosure',material='information',recipients=['own_employees','consultants'])
    g.qualify('own_need_and_advice',62,['own_need_to_know_restriction'],concept='need_to_know')
    g.n('external_affiliate_entities','group','unspecified',62,quote='affiliates, subsidiaries, associates and/or third party')
    g.effect('no_affiliate_external_disclosure','prohibition',62,'auditor','disclosure','disclose',material='information',recipients=['external_affiliate_entities'])
    g.qualify('affiliate_prior_written_approval',62,['no_affiliate_external_disclosure'],concept='written_consent',quote='without prior written approval of the Auditee')
    g.effect('absolute_no_outside_country','prohibition',63,None,'unspecified','hosted or taken',material='information')
    g.qualify('absolute_country_text',63,['absolute_no_outside_country'],quote='outside the country in any circumstances')
    g.effect('compensation','obligation',57,'auditor','unspecified','compensate',recipients=['auditee'])
    g.qualify('breach_loss_case',57,['compensation'])
    g.effect('no_employee_solicitation','prohibition',85,'auditor','unspecified','solicit')
    g.qualify('employee_consultant_knowledge_term_and2years',85,['no_employee_solicitation'])
    g.qualify('solicitation_prior_written_consent',85,['no_employee_solicitation'],concept='written_consent',quote='without the prior written consent of Auditee')
    for identity,unit in [('possible_harm',55),('specific_performance',56),('liquidated_cap_contract_value',58),('litigation_costs',59),('cumulative_remedies',60),('no_IP_license',65),('no_conflict_representation',67),('authority_representation',69),('Indian_law_blank_court_city',71),('integration',73),('signed_amendments',75),('binding_successors',77),('severability',79),('nonwaiver',81),('perpetual_confidence_survival',83),('Indian_law',86),('senior_negotiation',87),('45day_arbitration',88),('blank_arbitration_venue',89),('written_English_award',90),('180day_arbitration_completion',91),('blank_term_year',93)]:g.statement(identity,unit)
    return ['The auditee form offers government/state/corporate alternatives;no organization option,party name,date,venue or term-year blank is filled.',
        'Definition is mutual but Article2 obligations specifically address Auditor;mutual survival does not invent all those duties for Auditee.',
        'Product-detail copy/retention ban has no supplied written-consent exception;the separate audit-result ban does. They are not merged.',
        'Immediate tangible disposition has expiration OR termination OR Auditee request and Auditee choice;no oral-information destruction or certificate requirement is invented.',
        'Article2 outside-India rule admits written consent,while Article7 forbids taking/hosting information abroad in any circumstances;both norms and their unresolved priority remain.',
        'Agency sharing requires a lawful mandated agency call and prior written information,not invented written permission;own need-to-know staff restriction does not erase the general consent clause.',
        'Article5 exceptions target Article2,not automatically the later Article7 restrictions;foregoing-exception proof wording has unresolved crossreference scope.',
        'Unprovided CERT-In guidelines,foreign-personnel restrictions,liquidated cap,solicitation qualifiers,arbitration/court priority and full Boolean mechanics remain incompletely formalized.']


def csbs(g):
    g.n('company','organization','unspecified',1,name='Conference of State Bank Supervisors, Inc.')
    g.n('vendor','group','unspecified',1,name='<Vendor Name Here>')
    g.n('parties','group','either_party',4,name='parties')
    g.n('recipient','group','receiving_party',9,name='receiving party')
    g.n('discloser','group','disclosing_party',15,name='disclosing party')
    g.n('information','information','confidential_information',7)
    g.n('derived_information','information','confidential_information',8)
    g.effect('hold_confidence','obligation',9,'recipient','unspecified','treat',material='information')
    g.qualify('own_care_reasonable_floor',9,['hold_confidence'])
    g.n('third_parties','group','other_third_parties',10,name='any person or entity')
    g.effect('no_disclosure','prohibition',10,'recipient','disclosure','disclose',material='information',recipients=['third_parties'])
    g.effect('purpose_only_use','prohibition',10,'recipient','unspecified','use',material='information')
    g.qualify('fulfilling_project',10,['purpose_only_use'],quote='for any purpose other than fulfilling its obligations under the Project')
    g.n('representatives','group','unspecified',10,name='Representatives')
    for identity,concept,name in [('employees','own_employees','employees'),('officers','unspecified','officers'),('directors','unspecified','directors'),('consultants','consultants','independent consultants'),('affiliate_entities','unspecified','affiliates'),('subsidiary_entities','unspecified','subsidiaries'),('agents','agents','other agents')]:
        g.n(identity,'group',concept,10,name=name);g.r('member_of',identity,'representatives',10)
    g.n('representative_exception','exception','unspecified',10)
    g.r('exception_for','representative_exception','no_disclosure',10);g.r('recipient','representative_exception','representatives',10)
    g.qualify('project_involvement',10,['representative_exception'],quote='involved in the performance of the Project')
    g.qualify('written_no_less_stringent_terms',12,['representative_exception'])
    g.effect('no_copy','prohibition',13,'parties','unspecified','make copies',material='information')
    g.qualify('undefined_authorized_persons_exception',13,['no_copy'])
    g.effect('copy_confidential_marking','obligation',14,'recipient','unspecified','marked Confidential',material='information')
    g.qualify('copy_original_proprietary_notices',14,['copy_confidential_marking'])
    g.n('all_material','information','all_confidential_information_and_copies',15)
    g.effect('project_request_return','obligation',15,'recipient','return','returned',material='all_material',recipients=['discloser'])
    g.effect('project_end_destroy','obligation',15,'recipient','destruction','destroyed',material='all_material')
    g.n('project_request','condition','request',15,quote='upon request')
    g.n('project_end','condition','unspecified',15,quote='the expiration or other termination of the Project')
    g.r('trigger','project_request_return','project_request',15);g.r('trigger','project_end_destroy','project_end',15)
    g.qualify('project_disposal_or',15,['project_request_return','project_end_destroy'])
    g.qualify('project_end10business_days',15,['project_end_destroy'],quote='within ten (10) business days of the expiration or other termination of the Project')
    g.n('nda_trigger','condition','termination_or_request',20)
    g.effect('cease_use','obligation',21,'recipient','unspecified','cease using',material='information')
    g.effect('nda_return','obligation',22,'recipient','return','return',material='all_material',recipients=['discloser'])
    g.effect('nda_compliance_certificate','obligation',23,'recipient','unspecified','certify in writing')
    for e in ['cease_use','nda_return','nda_compliance_certificate']:g.r('trigger',e,'nda_trigger',20)
    g.qualify('demand_receipt10business_days',22,['nda_return'],quote='within ten (10) business days of receipt of demand')
    g.qualify('certificate_separate_request',23,['nda_compliance_certificate'],quote='upon request of the disclosing party')
    g.n('backup_material','information','some_confidential_information',17,quote='electronic Confidential Information stored in back-up/archival storage')
    g.n('legal_copy','information','some_confidential_information',18,quote='a single copy of all Confidential Information')
    g.n('legal_department','group','unspecified',18,name='Receiving Party’s legal department')
    for suffix,backup_unit,legal_unit,targets in [('4',17,18,['project_request_return','project_end_destroy']),('5',25,26,['nda_return'])]:
        no_delete='backup_no_deletion_'+suffix
        g.n(no_delete,'exception','unspecified',backup_unit)
        g.r('information',no_delete,'backup_material',backup_unit)
        g.qualify('backup_policy_and_confidence_'+suffix,backup_unit,[no_delete])
        retain='legal_copy_retention_'+suffix
        g.effect(retain,'permission',legal_unit,'recipient','retention','retained',material='legal_copy')
        g.r('condition',retain,'legal_department',legal_unit)
        g.qualify('dispute_resolution_only_'+suffix,legal_unit,[retain],quote='for dispute resolution purposes only')
        g.qualify('retained_terms_continue_'+suffix,legal_unit,[retain])
        for target in targets:
            g.r('exception_for',no_delete,target,backup_unit)
            g.r('exception_for',retain,target,legal_unit)
    g.effect('actual_knowledge_breach_notice','obligation',19,'recipient','unspecified','promptly give notice')
    g.qualify('actual_knowledge_case',19,['actual_knowledge_breach_notice'])
    for identity,unit in [('prior_without_duty',30),('public',31),('third_party_unless_bound',32),('independent_contemporaneous_records',33),('prior_written_release',34)]:
        g.n(identity,'exception','unspecified',unit);g.r('exception_for',identity,'no_disclosure',29)
    g.n('vendor_GC','group','unspecified',35,name='General Counsel of <Vendor Name Here>')
    g.n('company_GC','group','unspecified',35,name='General Counsel of Company')
    for identity,recipient,case in [('vendor_case_notice','vendor_GC','in the case of <Vendor Name Here>, the General Counsel of <Vendor Name Here>'),('company_case_notice','company_GC','in the case of Company, to the General Counsel of Company')]:
        g.effect(identity,'obligation',35,'recipient','unspecified','provide prompt actual notice',recipients=[recipient])
        g.qualify(identity+'_case',35,[identity],quote=case)
        g.qualify(identity+'_valid_process_opportunity',35,[identity])
    g.effect('compelled_portion','obligation',36,'recipient','disclosure','furnish',material='information')
    g.qualify('no_order_or_waiver',36,['compelled_portion'])
    g.effect('compelled_assurance_efforts','obligation',36,'recipient','unspecified','exercise its reasonable efforts',material='information')
    g.qualify('compelled_efforts_case',36,['compelled_assurance_efforts'])
    g.effect('regulator_sharing','permission',38,'parties','disclosure','disclose',material='information')
    g.effect('vendor_regulatory_sharing','permission',38,'parties','disclosure','disclose',material='information')
    g.qualify('Company_oversight_agency',39,['regulator_sharing'])
    g.qualify('Vendor_regulatory_responsibilities',40,['vendor_regulatory_sharing'])
    g.qualify('both_cases_required_portion_and_assurance',41,['regulator_sharing','vendor_regulatory_sharing'])
    g.effect('export_compliance','obligation',54,'parties','unspecified','comply')
    g.qualify('required_authorizations',54,['export_compliance'])
    g.effect('no_assignment','prohibition',55,'parties','unspecified','assign')
    g.qualify('assignment_prior_written_consent',55,['no_assignment'],concept='written_consent')
    g.n('affiliate_successor_assignment','exception','unspecified',56);g.r('exception_for','affiliate_successor_assignment','no_assignment',56)
    g.qualify('assignee_written_binding_and_other_notice',56,['affiliate_successor_assignment'])
    g.effect('corporate_affiliate_performance','obligation',62,'parties','unspecified','responsible')
    g.effect('affiliate_exit_disposition','obligation',63,'parties','unspecified','cause')
    g.qualify('requested_before_exit_section5',63,['affiliate_exit_disposition'])
    for identity,unit in [('IP_remains_discloser',27),('no_IP_license',28),('possible_legal_breach',11),('conditional_equitable_relief',42),('reasonable_enforcement_costs',43),('signature_effective',44),('30day_notice_term_option',45),('3year_term_option',46),('longer_3years_or_trade_secret_survival',47),('UTSA_relation',48),('integration',50),('severability',51),('New_York_law',52),('possible_export_control',53),('void_assignment',57),('signatory_authority',58),('warranty_right_to_disclose',59),('as_is_discussion_only',60),('corporate_affiliate_definition',61),('independent_without_use',65),('similar_current_future_development',66)]:g.statement(identity,unit)
    return ['Vendor name,address and signature dates are blank;Company/affiliate scope stays as written without invented individual employee identities.',
        'Representatives include affiliate/subsidiary entities,not automatically those entities employees;Authorized Persons in the copy exception is unprovided and not equated to Representatives.',
        'Project-end destruction and request return in paragraph4 are not silently merged with paragraph5 NDA termination/written demand;ten-business-day start language differs and any missing termination-only anchor remains unknown.',
        'Repeated backup and legal-copy exceptions remain at their separate original units;no-duty-to-delete backups is not a general affirmative retention license.',
        'Single legal-department copy is dispute-resolution-only and subject to terms;legal custody is not permission to disclose to external legal advisors or to keep using all information.',
        'Nondisclosure exclusions do not delete the definition or waive all use/copy obligations;the public exception is not given an unstated no-fault qualifier.',
        'General-Counsel notice cases are preserved as written without correcting them to opposite-party notice;prompt actual notice is not rewritten as expressly written notice.',
        'Subpoena/order paths and independent regulatory-disclosure paths keep separate conditions;Vendor regulatory responsibilities are not relabelled Company responsibilities.',
        'Retained confidence,trade-secret survival,affiliate-exit/assignment crossreferences and the full Boolean/reciprocal/legal-priority mechanics remain incompletely formalized.']


def cyber_mutual(g):
    g.n('parties','group','either_party',7,name='Participating Entities')
    g.n('recipient','group','receiving_party',48,name='Participating Entity')
    g.n('discloser','group','disclosing_party',48,name='Participating Entity that disclosed the information')
    g.n('information','information','confidential_information',11)
    for identity,unit in [('agreement_date_and_participation',2),('program_context',4),('voluntary_help',5),('purpose',9),('generated_information',12),('aggregated_information',13),('observations_oral_information',14)]:g.statement(identity,unit)
    g.effect('hold_confidence','obligation',18,'parties','unspecified','maintain',material='information')
    g.n('third_parties','group','other_third_parties',19,name='third parties')
    g.effect('no_disclosure','prohibition',19,'recipient','disclosure','disclose',material='information',recipients=['third_parties'])
    g.qualify('express_permission_not_written',19,['no_disclosure'])
    g.effect('purpose_only_use','obligation',20,'parties','unspecified','use',material='information')
    g.qualify('program_purpose',20,['purpose_only_use'])
    g.effect('emergency_internal_sharing','permission',23,'recipient','disclosure','internally share',material='information')
    g.effect('emergency_use','permission',23,'recipient','unspecified','use',material='information')
    g.qualify('actual_threatened_system_risk',23,['emergency_internal_sharing','emergency_use'])
    g.effect('other_use_restriction','prohibition',24,'recipient','unspecified','use',material='information')
    g.qualify('other_use_prior_written_consent',24,['other_use_restriction'],concept='written_consent')
    g.n('third_party_nonbreach','exception','unspecified',26);g.r('exception_for','third_party_nonbreach','no_disclosure',26)
    for identity,unit in [('public_consistent_availability',27),('outside_program_received_or_developed',28),('unrestricted_lawful_third_source',29),('statutory_legal_process',30),('unanimous_owner_agreement',31),('later_nonconfidential_source_not_known_bound',32)]:
        g.n(identity,'condition','unspecified',unit);g.r('object','third_party_nonbreach',identity,unit)
    g.effect('legal_process_written_notice','obligation',34,'recipient','unspecified','notify in writing',recipients=['parties'])
    g.qualify('legal_process_five_business_days_from_receipt',34,['legal_process_written_notice'])
    g.n('legal_process_nonviolation','exception','unspecified',35);g.r('exception_for','legal_process_nonviolation','no_disclosure',35)
    g.qualify('seven_business_days_after_notification',35,['legal_process_nonviolation'])
    g.effect('FOIA_nondisclosure','prohibition',36,'recipient','disclosure','disclose',material='information')
    g.qualify('written_counsel_required_law_opinion',36,['FOIA_nondisclosure'])
    g.effect('FOIA_immediate_owner_notice','obligation',38,'recipient','unspecified','notify',recipients=['discloser'])
    g.qualify('upon_public_records_request',37,['FOIA_immediate_owner_notice'])
    g.effect('FOIA_exempt_treatment','obligation',39,'recipient','unspecified','treat',material='information')
    g.qualify('counsel_opinion_no_legal_requirement',39,['FOIA_exempt_treatment'])
    g.effect('cooperate_challenge','obligation',40,'recipient','unspecified','cooperate',recipients=['discloser'])
    g.effect('failed_challenge_required_portion','obligation',41,'recipient','disclosure','disclosed',material='information')
    g.qualify('failed_challenge_remedy_opinion',41,['failed_challenge_required_portion'])
    g.effect('breach_notice_and_recovery','obligation',43,'recipient','unspecified','immediately notify',recipients=['discloser'])
    g.qualify('actual_or_likely_unauthorized_disclosure',43,['breach_notice_and_recovery'])
    g.effect('withdrawal','permission',45,'parties','termination','withdraw')
    g.qualify('ten_day_prior_written_notice',45,['withdrawal'])
    g.n('all_material','information','all_confidential_information_and_copies',48)
    g.effect('return','obligation',48,'recipient','return','returned',material='all_material',recipients=['discloser'])
    g.n('termination','condition','termination',48,quote='Upon termination of this Agreement')
    g.r('trigger','return','termination',48)
    g.qualify('received_possession_control_scope',48,['return'])
    g.qualify('different_written_instructions',48,['return'],quote='unless otherwise instructed in writing by the Participating Entity that disclosed the information')
    g.n('backup_material','information','some_confidential_information',49,quote='Confidential Information is retained in the computer backup system')
    g.effect('backup_process_destruction','obligation',49,'recipient','destruction','destroyed',material='backup_material')
    g.qualify('regular_records_retention_process',49,['backup_process_destruction'])
    g.effect('destruction_certificate_alternative','permission',50,'recipient','unspecified','certify',material='all_material',recipients=['parties'])
    g.qualify('in_lieu_return_already_destroyed',50,['destruction_certificate_alternative'])
    g.n('record_copy','information','some_confidential_information',51,quote='a record copy of any Confidential Information')
    g.effect('legal_record_retention','permission',51,'recipient','retention','retain',material='record_copy')
    g.qualify('required_by_applicable_law',51,['legal_record_retention'],quote='if required to do so by applicable law')
    g.effect('retained_identification_and_commitment','obligation',52,'recipient','unspecified','identify in writing',material='record_copy',recipients=['discloser'])
    g.qualify('legal_retention_case_and_expiry_commitment',52,['retained_identification_and_commitment'])
    g.effect('retained_confidentiality','obligation',53,'recipient','unspecified','maintain the confidentiality',material='record_copy')
    g.qualify('while_possessed',53,['retained_confidentiality'])
    g.effect('notices','obligation',55,'parties','unspecified','notices, requests, demands, and other communications')
    g.qualify('writing_unless_agreed_delivery_modes',55,['notices'])
    g.effect('no_assignment','prohibition',71,'parties','unspecified','assign')
    g.qualify('assignment_prior_written_consent',71,['no_assignment'],concept='written_consent')
    for identity,unit in [('ten_year_survival',46),('notice_address_changes',56),('integration',58),('all_entities_written_changes',59),('no_other_rights',60),('no_warranty',62),('no_accuracy_reliance',63),('conditional_injunctive_relief',66),('New_York_law',68),('successors',70),('fair_construction',73),('signature_authority',75),('counterparts',77)]:g.statement(identity,unit)
    return ['Agreement text states15June2016,but executed Participating Entities and individual signature dates are not filled;no actual emergency or request is inferred.',
        'Representative lists in the definition describe information origins,not a new general permission to disclose to every listed employee/adviser.',
        'Actual/threatened-system-risk internal sharing is conditional and leaves internal recipient identities unspecified;express disclosure permission is not silently made written.',
        'Nonbreach disclosures are not definition exclusions;five-business-day receipt notice and seven-business-day post-notification process compliance keep different clocks.',
        'FOIA/public-records opinion/challenge paths stay separate from ordinary legal process;written legal opinion is not a broad disclosure-to-lawyers license.',
        'Return is termination-triggered,not request-triggered by the generic notices clause;backup regular-process destruction,certificate alternative and required-law record copy retain their own scope.',
        'Ten-year survival and retained-information confidentiality while possessed are not collapsed into one invented cutoff;legal/crossreference/Boolean priority remains incomplete.']


def shire(g):
    g.n('shire','organization','unspecified',3,name='Shire Pharmaceuticals, Inc.')
    g.n('lek','organization','unspecified',4,name='L.E.K.')
    g.n('new_river','organization','unspecified',4,name='New River Pharmaceuticals Inc.')
    g.n('parties','group','either_party',10,name='Parties')
    g.n('discloser','group','disclosing_party',17,name='Disclosing Party')
    g.n('recipient','group','receiving_party',18,name='Receiving Party')
    g.n('information','information','confidential_information',13)
    g.statement('definition_after_page_header',15)
    g.qualify('unique_synthesis_not_public_parts',16,['information'])
    g.n('agreement_discussions','information','some_confidential_information',19)
    g.n('derived_material','information','confidential_information',21)
    g.statement('LEK_engagement_not_employment',7)
    g.effect('hold_confidence','obligation',25,'parties','unspecified','hold',material='information')
    g.effect('care','obligation',26,'parties','unspecified','exercise',material='information')
    g.qualify('own_care_reasonable_floor',26,['care'])
    g.n('third_parties','group','other_third_parties',27,quote='third parties (including, without limitation, any clients, affiliates, independent contractors and consultants)')
    g.effect('no_disclosure','prohibition',27,'recipient','disclosure','disclose',material='information',recipients=['third_parties'])
    g.qualify('prior_written_disclosure_consent',27,['no_disclosure'],concept='written_consent',quote='without the prior, written consent of the Disclosing Party')
    g.qualify('paragraph4_exception',27,['no_disclosure'],quote='except as expressly permitted under Paragraph 4')
    g.effect('purpose_only_use','prohibition',28,'recipient','unspecified','use',material='information')
    g.qualify('use_purpose_and_written_consent',28,['purpose_only_use'])
    g.n('representatives','group','unspecified',30,name='Representatives')
    for identity,concept,name in [('directors','unspecified','directors'),('officers','unspecified','officers'),('employees','own_employees','employees'),('legal_advisors','legal_advisors','legal advisors'),('financial_advisors','financial_advisors','financial advisors'),('accountants','unspecified','accountants')]:
        g.n(identity,'group',concept,30,name=name);g.r('member_of',identity,'representatives',30)
    g.effect('representative_sharing','permission',30,'recipient','disclosure','disclose',material='information',recipients=['representatives'])
    g.qualify('bound_consistent_confidentiality',30,['representative_sharing'],quote='each bound by obligations of confidentiality consistent with this Agreement')
    g.qualify('bona_fide_need',30,['representative_sharing'],concept='need_to_know',quote='who have a bona fide need to know')
    g.qualify('necessary_business_extent',30,['representative_sharing'],quote='only to the extent necessary to carry out the Business Purpose')
    g.qualify('section4_subject_restrictions',30,['representative_sharing'],quote='Subject to the restrictions set forth below in this Section 4')
    g.effect('instruct_representatives','obligation',31,'parties','unspecified','instruct')
    g.qualify('other_rep_identities',32,['instruct_representatives'])
    g.qualify('no_further_unlisted_sharing',33,['instruct_representatives'])
    g.statement('representative_compliance_responsibility',34)
    g.n('exhibit_A','group','unspecified',35,quote='its Representatives identified on Exhibit A hereto')
    g.n('exhibit_B','group','unspecified',36,quote='Representatives identified on Exhibit B hereto')
    g.n('exhibit_C','group','unspecified',36,quote='NEW RIVER Representatives identified on Exhibit C hereto')
    for identity,actor,unit in [('shire_existence_restriction','shire',35),('lek_existence_restriction','lek',37),('new_river_existence_restriction','new_river',38)]:
        g.effect(identity,'prohibition',unit,actor,'disclosure','disclose',material='agreement_discussions')
        g.qualify(identity+'_listed_only',unit,[identity])
        evidence_units={'shire':[35,36,36],'lek':[37,37,37],'new_river':[38,39,38]}[actor]
        for listed,evidence_unit in zip(['exhibit_A','exhibit_B','exhibit_C'],evidence_units):g.r('condition',identity,listed,evidence_unit)
    g.statement('shire_clause_continuation',36);g.statement('new_river_clause_continuation',39)
    g.n('unlisted_new_river_contacts','group','unspecified',41)
    g.statement('possible_LEK_communications',41)
    g.effect('LEK_no_client_identification','prohibition',43,'lek','disclosure','disclose')
    g.qualify('unlisted_contact_client_identity_scope',43,['LEK_no_client_identification'])
    g.r('condition','LEK_no_client_identification','unlisted_new_river_contacts',41)
    g.n('competent_proof_header','condition','unspecified',45)
    for identity,unit in [('public_no_own_fault',46),('prior_written_records',47),('rightful_unrestricted_third_source',48),('documented_independent_development',49),('required_competent_authority',50),('specifically_authorized_written_disclosure',53)]:
        g.n(identity,'exception','unspecified',unit)
        for effect in ['hold_confidence','care','no_disclosure','purpose_only_use']:g.r('exception_for',identity,effect,45)
        g.r('condition',identity,'competent_proof_header',45)
    g.effect('authority_notice_efforts','obligation',51,'recipient','unspecified','used reasonable efforts',recipients=['discloser'])
    g.qualify('authority_required_case',50,['authority_notice_efforts'])
    g.qualify('prompt_notice_not_guaranteed_prior_written',51,['authority_notice_efforts'])
    g.effect('authority_confidentiality_efforts','obligation',52,'recipient','unspecified','informed the requesting authority',material='information')
    g.qualify('authority_confidential_treatment',52,['authority_confidentiality_efforts'])
    g.effect('no_material_removal','prohibition',55,'parties','unspecified','remove')
    g.qualify('removal_consent_not_written',55,['no_material_removal'])
    g.effect('approved_removal_terms','obligation',56,'parties','unspecified','comply')
    g.qualify('imposed_date_and_no_unconsented_copies',56,['approved_removal_terms'])
    g.n('return_material','information','unspecified',58,quote='all materials or tangible items containing the Disclosing Party’s Confidential Information and all copies thereof')
    g.effect('return','obligation',58,'recipient','return','return',material='return_material',recipients=['discloser'])
    g.n('request','condition','request',58,quote='Upon the Disclosing Party’s request')
    g.r('trigger','return','request',58)
    g.qualify('prompt_return',58,['return'],quote='promptly return')
    g.n('single_compliance_copy','information','some_confidential_information',58,quote='a single copy of Disclosing Party’s Confidential Information')
    g.effect('single_compliance_retention','permission',58,'recipient','retention','maintain',material='single_compliance_copy')
    g.r('exception_for','single_compliance_retention','return',58)
    g.qualify('legal_department_or_outside_counsel',58,['single_compliance_retention'],quote='Receiving Party’s legal department or outside legal counsel')
    g.qualify('regulatory_and_agreement_compliance',58,['single_compliance_retention'],quote='for purposes of regulatory compliance and compliance with the terms and conditions of this Agreement')
    g.effect('breach_notice_and_recovery','obligation',60,'recipient','unspecified','notify',recipients=['discloser'])
    g.qualify('immediate_discovery_case_assistance',60,['breach_notice_and_recovery'])
    g.effect('notices','obligation',72,'parties','unspecified','notices')
    g.qualify('fax_same_day_hardcopy',72,['notices'])
    g.qualify('delivery_service',73,['notices']);g.qualify('registered_mail',74,['notices'])
    g.effect('securities_compliance','obligation',123,'parties','unspecified','comply')
    g.effect('no_assignment','prohibition',126,'parties','unspecified','assign')
    g.qualify('assignment_prior_written_consent',126,['no_assignment'],concept='written_consent')
    g.effect('press_release_restriction','prohibition',129,'parties','disclosure','public statement',material='agreement_discussions')
    g.effect('trademark_publicity_restriction','prohibition',130,'parties','unspecified','use')
    g.qualify('publicity_prior_written_consent',130,['press_release_restriction','trademark_publicity_restriction'],concept='written_consent')
    for identity,unit in [('no_broader_use_license',62),('no_transaction_or_IP_commitment',64),('ownership_and_or_licensors_harm',66),('right_seek_injunction',67),('other_remedies',68),('five_year_term_written_extension',70),('notice_address_changes',97),('integration_written_changes',99),('existing_agreements_survive',100),('prior_named_agreement_survival',101),('invalidity',103),('remaining_validity',104),('written_replacement',105),('New_York_law',107),('no_continuing_waiver',109),('no_other_breach_waiver',110),('signed_waiver',111),('authority',114),('right_permit_evaluation',115),('no_conflict',116),('facsimile_counterparts',118),('potential_inside_information',121),('insider_securities_statement',122),('successors',125),('signed_changes',132)]:g.statement(identity,unit)
    return ['Effective Date is stated28November2006,but referenced ExhibitsA/B/C are not supplied;notice addressees and signatories are not invented as listed Representatives.',
        'Confidential definition crosses a page-header break;original units remain separate and no fabricated cross-unit quote or extra party name is inserted.',
        'Party-specific existence/discussion restrictions are not generalized to all Confidential Information;explicit legal/financial adviser classes and unspecified accountants remain distinct.',
        'LEK engagement is not legal employment;possible contact with unlisted NewRiver staff does not authorize revealing SHIRE identity.',
        'Competent-proof exclusions and unique-public-element caveat keep scope;authority notice requires reasonable efforts and is not upgraded to guaranteed prior written notice.',
        'Removal consent is not explicitly written;any imposed return date is unprovided. General material return is request-triggered,not automatically five-year-expiry-triggered.',
        'Single retained copy is for regulatory AND Agreement compliance,with legal-department/outside-counsel custody;it is not CSBS dispute-resolution retention or an independent unlimited disclosure grant.',
        'Existing separate agreements surviving execution do not establish unlimited survival for every present obligation;licensor rights and full Boolean/temporal/legal mechanisms remain incomplete.']


def jlt(g):
    g.n('recipient','organization','receiving_party',0,name='Marsh & McLennan Companies, Inc')
    g.n('company','organization','unspecified',12,name='Jardine Lloyd Thompson Group plc')
    g.n('parties','group','either_party',39,name='parties')
    g.n('information','information','confidential_information',13)
    g.n('agreement_component','information','some_confidential_information',14)
    g.n('transaction_component','information','some_confidential_information',15)
    g.n('discussion_component','information','some_confidential_information',16)
    g.n('group_shareholder_information','information','some_confidential_information',17)
    g.n('derivatives','information','confidential_information',23)
    g.n('target_information','information','some_confidential_information',32)
    g.qualify('target_a_to_c_start',33,['target_information']);g.qualify('target_a_to_c_end',34,['target_information'])
    for material,unit in [('agreement_component',14),('transaction_component',15),('discussion_component',16)]:g.r('object','target_information',material,unit)
    for identity,unit in [('public_or_available_with_inquiry_limit',20),('prior_lawful_unrestricted_possession',21),('independent_not_derivative',22)]:
        g.n(identity,'exception','unspecified',unit);g.r('exception_for',identity,'information',unit)
    g.statement('copies_and_derivatives_in_definition',18)
    g.n('group','group','unspecified',24,quote="such party's respective ultimate parent undertaking and such parent undertaking's subsidiary undertakings from time to time")
    g.n('representatives','group','unspecified',30,name='Representatives')
    for identity,concept,name in [('directors','unspecified','directors'),('officers','unspecified','officers'),('employees','own_employees','employees'),('agents','agents','agents'),('professional_advisers','unspecified','professional advisers')]:
        g.n(identity,'group',concept,30,name=name);g.r('member_of',identity,'representatives',30)
    g.n('group_staff','group','unspecified',30,quote="of a party or any member of such party's Group from time to time")
    g.n('finance_providers','group','unspecified',26,name='Permitted Finance Provider')
    g.n('goldman','organization','unspecified',27,name='Goldman Sachs International')
    g.qualify('other_provider_prior_written_consent_direct_NDA_limit',28,['finance_providers'])
    g.r('member_of','finance_providers','representatives',30)
    g.n('third_parties','group','other_third_parties',48,name='any other person')
    g.effect('full_information_nondisclosure','prohibition',48,'recipient','disclosure','disclose',material='information',recipients=['third_parties'])
    g.qualify('company_prior_written_consent',48,['full_information_nondisclosure'],concept='written_consent')
    g.effect('own_security','obligation',49,'recipient','unspecified','protected',material='information')
    g.effect('transaction_only_use','obligation',51,'recipient','unspecified','use',material='information')
    g.qualify('consider_implement_transaction',51,['transaction_only_use'])
    g.effect('target_information_nondisclosure','prohibition',52,'company','disclosure','disclose',material='target_information')
    g.qualify('target_prior_written_consent_and43',52,['target_information_nondisclosure'],concept='written_consent')
    g.n('JM_group_advisers','group','unspecified',54)
    g.n('panel_FCA','group','unspecified',55)
    g.n('target_special_recipients','exception','unspecified',52)
    g.r('exception_for','target_special_recipients','target_information_nondisclosure',52)
    g.r('recipient','target_special_recipients','JM_group_advisers',54);g.r('recipient','target_special_recipients','panel_FCA',55)
    for identity,effect,material in [('full_representative_exception','full_information_nondisclosure','information'),('target_representative_exception','target_information_nondisclosure','target_information')]:
        g.n(identity,'exception','unspecified',59);g.r('exception_for',identity,effect,58)
        g.r('recipient',identity,'representatives',59);g.r('information',identity,material,58)
        g.qualify(identity+'_concerned_and_necessary',59,[identity],concept='need_to_know')
    g.n('legal_regulatory_disclosure','exception','unspecified',60)
    for e in ['full_information_nondisclosure','target_information_nondisclosure']:g.r('exception_for','legal_regulatory_disclosure',e,58)
    g.qualify('lawfully_entitled_body_subject_to4',60,['legal_regulatory_disclosure'])
    g.effect('ensure_representative_compliance','obligation',62,'parties','unspecified','ensure')
    g.qualify('professional_finance_632_only_exception',62,['ensure_representative_compliance'])
    g.effect('no_announcement','prohibition',65,'parties','disclosure','announcement',material='transaction_component')
    g.qualify('announcement_written_consent_42_43',65,['no_announcement'],concept='written_consent')
    g.effect('pre_disclosure_consult','obligation',67,'parties','unspecified','consultation')
    g.qualify('legally_permissible_required_disclosure_consultation',67,['pre_disclosure_consult'])
    g.effect('post_disclosure_information','obligation',68,'parties','unspecified','inform')
    g.qualify('if_prior_consult_impossible_as_soon_practicable',68,['post_disclosure_information'])
    g.n('company_Code_announcement','exception','unspecified',70);g.r('exception_for','company_Code_announcement','no_announcement',70)
    g.effect('other_finance_approach_consent','obligation',72,'recipient','unspecified','inform the Company',recipients=['company'])
    g.qualify('non_Goldman_debt_approach_and_consent',72,['other_finance_approach_consent'])
    g.qualify('Code_consultation_constraint',73,['other_finance_approach_consent']);g.qualify('Code_announcement_constraint',74,['other_finance_approach_consent'])
    g.n('request','condition','request',77)
    g.n('deliverable_material','information','unspecified',78,quote='all hard copy documents and other materials which are in a form reasonably capable of delivery containing or reflecting the Confidential Information and all copies thereof')
    g.effect('return','obligation',78,'recipient','return','return',material='deliverable_material',recipients=['company'])
    g.effect('destroy_deliverable','obligation',78,'recipient','destruction','destroy',material='deliverable_material')
    g.effect('destroy_derivatives','obligation',78,'recipient','destruction','destruction',material='derivatives')
    g.effect('written_compliance_confirmation','obligation',78,'recipient','unspecified','confirm',recipients=['company'])
    for e in ['return','destroy_deliverable','destroy_derivatives','written_compliance_confirmation']:g.r('trigger',e,'request',77)
    g.qualify('recipient_choice',78,['return','destroy_deliverable'],quote='at your option')
    g.qualify('derivatives_and_confirmation_conjunction',78,['destroy_derivatives','written_compliance_confirmation'])
    g.effect('computer_erasure_steps','obligation',79,'recipient','unspecified','erase',material='information')
    g.qualify('where_not_already_returned_destroyed_reasonable_steps',79,['computer_erasure_steps'])
    g.effect('no_recover_erased','prohibition',79,'recipient','unspecified','access or recover',material='information')
    g.qualify('following_erasure',79,['no_recover_erased'])
    g.n('retained_copies','information','some_confidential_information',80)
    for identity,unit in [('law_reg_retention',81),('internal_compliance_retention',82),('impracticable_routine_backups_retention',83)]:
        g.effect(identity,'permission',80,'recipient','retention','retain',material='retained_copies')
        g.qualify(identity+'_ground',unit,[identity])
    g.effect('retained_no_further_use','prohibition',85,'recipient','unspecified','use',material='retained_copies')
    g.effect('retained_no_further_disclosure','prohibition',85,'recipient','disclosure','disclose',material='retained_copies')
    g.qualify('retained_terms_continue',85,['retained_no_further_use','retained_no_further_disclosure'])
    g.effect('contact_channel_restriction','obligation',88,'recipient','unspecified','direct all communications and questions')
    g.qualify('named_contact_list_and_prior_consent',88,['contact_channel_restriction'])
    g.n('company_consent_givers','group','unspecified',90,quote='Geoffrey Howe or Derek Walsh of the Company')
    g.statement('written_authorization_email',91)
    g.effect('discussion_contact_restriction','prohibition',93,'parties','unspecified','initiate or knowingly engage')
    g.effect('restricted_person_nonsolicitation','prohibition',94,'parties','unspecified','solicit, engage or employ')
    for e in ['discussion_contact_restriction','restricted_person_nonsolicitation']:g.qualify(e+'_12months_consent_procurement',92,[e])
    g.qualify('recruitment_ad_or_previous_termination_exceptions',95,['restricted_person_nonsolicitation'])
    g.qualify('shareholder_discussion_conditional_64',97,['discussion_contact_restriction'])
    g.effect('no_insider_dealing','prohibition',102,'recipient','unspecified','deal',material='information')
    g.effect('no_market_abuse','prohibition',103,'recipient','unspecified','use or disclose',material='information')
    standstill=[]
    for identity,unit,name in [('no_securities_acquisition',116,'acquire'),('no_acquisition_causing_acts',117,'act'),('no_offer_until_recommended',118,'offer'),('no_vote_solicitation',119,'solicitation'),('no_control_influence',121,'control'),('no_connected_arrangements',122,'agreement')]:
        g.effect(identity,'prohibition',unit,'recipient','unspecified',name);standstill.append(identity)
        g.qualify(identity+'_12month_consent_concert_scope',115,[identity])
    g.qualify('recommended_offer_vote_continuation',120,['no_vote_solicitation'])
    for identity,unit in [('recommended_lapse_Rule351',127),('third_party_firm_offer',128),('15percent_after_recommended_offer',129),('exempt_principal_trader_Rule38',132),('ordinary_course_not_on_behalf_no_CI',133)]:
        g.n(identity,'condition','unspecified',unit)
        for e in standstill:g.r('condition',e,identity,unit)
    g.effect('ensure_group_standstill','obligation',124,'recipient','unspecified','ensure')
    g.qualify('paragraph101_scope',124,['ensure_group_standstill'])
    g.effect('no_assignment','prohibition',176,'parties','unspecified','assign')
    g.qualify('assignment_consent_not_written',176,['no_assignment'])
    for identity,unit in [('restricted_person_definition',31),('Group_companies_legal_definition',37),('person_definition',38),('nonrestrictive_construction',41),('illustrative_words',43),('Group_beneficiary_enforcement',45),('acting_principal_own_cost',99),('possible_inside_information',101),('Code_governance',105),('taking_professional_advice_not_disclosure_grant',106),('Code_understanding',107),('secrecy',108),('minimize_leaks',109),('Rule_of6',110),('Rule212_company_limit',112),('concert_definition',136),('concert_party_definition',137),('offer_definition',138),('securities_interests_definition',139),('no_accuracy_responsibility',143),('no_information_liability',144),('no_update_duty',145),('no_reliance',147),('own_decision',149),('no_transaction_offer',151),('fraud_carveout_wrong_paragraph_reference',153),('18month_duration',155),('third_party_enforcement',157),('rescission_variation_limits',158),('no_other_statutory_enforcement',159),('seek_equitable_relief',161),('nonwaiver',163),('partial_exercise',164),('signed_variations',166),('privilege_not_waived',168),('cumulative_remedies',170),('no_extra_license',172),('severability',174),('English_law',179),('England_exclusive_jurisdiction',181),('forum_objection_waiver',182),('third_party_forum_enforcement',184),('counterparts',186),('effective_only_both_counterparts',187),('OCR_signature_date_unresolved',194)]:g.statement(identity,unit)
    return ['Marsh is the letter recipient and Company is JLT;the damaged signature-date string is not repaired into a date and actual counterpart execution is not inferred.',
        'Target Confidential Information covers definition(a)-(c),not the full Group/shareholder material in(d). Company special JM/Panel/FCA recipients apply only to Target information.',
        'Professional advisers have no supplied legal/financial specialty;Goldman and other debt providers are finance providers,not automatically financial advisers.',
        'Group representatives,consented other finance providers and direct-undertaking exclusion retain their definitions;professional advisers/finance-provider compliance exception is only6.3.2,not all confidentiality duties.',
        'Legal/regulatory disclosure consultation is qualified by legal permissibility and possibility;where prior consultation is impossible,later information is expressly allowed.',
        'Request-only return/destroy is at recipient option for deliverable material,with mandatory derivative destruction and confirmation;computer erasure is conditional and reasonable-steps based.',
        'Legal/regulatory,internal-compliance and impracticable routine-backup retention are alternative grounds,not one conjunctive test or a single-copy cap;backup no-access/recovery and all-retained no-further-use/disclosure scopes remain distinct.',
        'Named contact channels are not all authorized consent givers;Company consent givers are onlyHowe orWalsh and written consent may be by email. Assignment consent is not expressly written.',
        'Twelve-month standstill and contact limits differ from eighteen-month NDA duration;recommended-offer/15percent/third-offer exceptions and recruitment qualifiers are not simplified into unconditional rights.',
        'Missing external Code definitions,full Boolean/crossreference/Group scope,privilege and legal remedies remain incomplete;the paragraph10 fraud crossreference is retained rather than corrected.']


REVIEWERS={'4d4e550a':samsung,'e7b78d42':cert_audit,'6fce8464':csbs,
    '442c36c1':cyber_mutual,'8af247c6':shire,'bbb39011':jlt}


def reviewed_graph(source,units):
    locks={r['source']:r for r in read(LOCK_PATH)}
    if source not in locks or digest(units)!=locks[source]['units_sha256']:
        raise ValueError('Only six exact remaining CNI whole-source views explicitly read here are reviewed')
    g=ClauseGraph(units);unknown=REVIEWERS[source.split(':')[1][:8]](g)
    return g.finish(complete=False,unknown=unknown)


def prepare():
    locks=read(LOCK_PATH)
    if len(locks)!=6 or len({r['source'] for r in locks})!=6 or Counter(r['role'] for r in locks)!=Counter(development=2,calibration=3,reference_only=1):
        raise ValueError('Keep the final six original CNI sources,roles and batches')
    _,previous=previous_reviews();checkpoint=read(BASE/'handoff/current_checkpoint.json')
    roles={r['source']:r for r in read(ROOT/checkpoint['formal_source_reference_registry']['artifact_root']/'roles.json')}
    public_path=ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json';public={s['key']:s for s in read(public_path)}
    builders=[Path(__file__),LOCK_PATH,ROOT/'experiments/two_method_annotate.py',ROOT/'experiments/two_method_cni_short_source_reviews.py',
        ROOT/'experiments/two_method_cni_mid_source_reviews.py',ROOT/'legal_skill_guard/paired_interfaces/graph_interface.py',
        ROOT/'legal_skill_guard/skill_evolution/objects.py']
    protocol={'experiment':'final_six_CNI_whole_source_root_reviews_v1',
        'source_sha256':{str(p.relative_to(ROOT)):sha(p) for p in builders},'original_TRAIN_public_sha256':sha(public_path),
        'locked_original_roles_and_sources':locks,'prior62_explicit_manifest_sha256':digest(previous),
        'all_six_remaining_CNI_contracts_entire_supplied_text_read':True,
        'no_source_replacement_or_reassignment_or_outcome_selection':True,
        'native_target_questions_labels_weak_outputs_or_program_results_used':False,
        'explicit_root_review_not_automatic_semantic_certification':True,
        'interactive_root_annotation_cost_usd':None,'new_experimental_endpoint_requests':0}
    out=BASE/'CNI_long_source_reviews_v1'/digest(protocol);immutable_json(out/'protocol.json',protocol)
    rows=list(previous['reviews'])
    for lock in locks:
        source=lock['source'];role=roles[source]
        if (role['role'],role['batch'])!=(lock['role'],lock['batch']) or lock['view']!='v0':raise ValueError('Original source role/batch/view changed')
        task,mapping=inputs(public[source])
        if len(task['views'])!=1:raise ValueError('Do not collapse distinct source views')
        units=task['views'][0]['source_units'];graph=reviewed_graph(source,units)
        card={'source':source,'view_id':'v0','role':role['role'],'source_units_sha256':lock['units_sha256'],
            'native_views':sorted(mapping),'graph':graph,'reference_ready':True,'source_semantic_truth_verified':True,
            'native_answers_used_to_create_or_repair_graph':False,'complete_native_case_gold_claimed':False,
            'reviewer':'root assistant explicit whole-source review;not independent human annotation',
            'verification_scope':'All asserted local roles/material/conditions against every supplied source unit;unsupported legal,Boolean and missing-attachment scope stays unknown.',
            'source_span_checks':gi.validate(graph,units),'review':{'entire_supplied_view_read':True,'source_sha_locked':True,
                'retention_backup_legal_custody_and_material_branch_scopes_preserved':True,
                'missing_exhibits_dates_approval_types_and_legal_priorities_not_invented':True,
                'no_native_labels_reference_parameters_or_F_output_used_to_edit_graph':True},'new_model_requests':0}
        path=out/'cards'/digest([source,'v0'])/'source_review.json';immutable_json(path,card)
        rows.append({'source':source,'view':'v0','kind':'literal_semantic_graph','path':str(path.relative_to(ROOT)),'sha256':sha(path)})
    if len(rows)!=68 or len({(r['source'],r['view']) for r in rows})!=68:raise ValueError('Retain all previous62 and new6 reviews exactly once')
    manifest={'reviews':rows,'new_root_reviewed_views':6,'previous_extra_reviews_retained':62,
        'interactive_root_annotation_cost_usd':None,'unmetered_interactive_annotation_not_counted_as_free':True,
        'independent_human_or_complete_legal_gold_claimed':False,'new_model_requests':0}
    immutable_json(out/'manifest.json',manifest)
    for builder in builders:
        target=out/'source_snapshot'/builder.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists() and target.read_bytes()!=builder.read_bytes():raise ValueError('A frozen source builder changed')
        if not target.exists():target.write_bytes(builder.read_bytes())
    return out,manifest


if __name__=='__main__':
    out,manifest=prepare()
    print(json.dumps({'artifact_root':str(out.relative_to(ROOT)),'new_reviewed_mothers':6,
        'cumulative_explicit_review_views':len(manifest['reviews']),'new_model_requests':0,'complete_goal_claimed':False},ensure_ascii=False))
