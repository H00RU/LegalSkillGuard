"""Four source-only CNI reviews after the six shortest complete contracts.

Every supplied source unit was read. Native questions,labels,reference
parameters,weak outputs and F results do not construct or repair these graphs.
"""
from collections import Counter
from pathlib import Path
import json

from experiments.two_method_annotate import inputs
from experiments.two_method_graph_corpus import ROOT, BASE, read, sha
from experiments.two_method_cni_short_source_reviews import ClauseGraph, prepare as previous_reviews
from legal_skill_guard.paired_interfaces import graph_interface as gi
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


LOCK_PATH=ROOT/'experiments/source_review_locks/cni_mid4_20261117.json'


def sintec(g):
    g.n('sintec','organization','disclosing_party',3,name='SINTEC UK LIMITED')
    g.n('recipient','group','receiving_party',2,name='Receiving Party')
    g.n('information','information','confidential_information',12)
    g.n('third_parties','group','other_third_parties',14,name='third parties')
    g.effect('hold_confidence','obligation',14,'recipient','unspecified','treat as strictly confidential',material='information')
    g.effect('no_disclosure','prohibition',14,'recipient','disclosure','disclose',material='information',recipients=['third_parties'])
    g.effect('no_other_use','prohibition',14,'recipient','unspecified','use',material='information')
    g.qualify('prior_written_consent',14,['no_disclosure','no_other_use'],concept='written_consent',quote='without the prior written consent of SINTEC')
    g.qualify('other_use_scope',14,['no_other_use'],quote='for its own business purposes or for other customers')
    g.effect('purpose_use','obligation',15,'recipient','unspecified','use',material='information')
    g.qualify('specified_authorized_purpose',15,['purpose_use'],quote="only for SINTEC's specified or authorized purposes in each case")
    g.n('selected_staff','group','own_employees',18,name='said employees')
    g.effect('staff_disclosure_restriction','unspecified',17,'recipient','disclosure','disclose',material='information',recipients=['selected_staff'])
    g.qualify('selected_staff_only',17,['staff_disclosure_restriction'],quote='only to selected members of its staff')
    g.qualify('absolutely_necessary_extent',17,['staff_disclosure_restriction'],quote="only to the extent absolutely necessary for SINTEC's specified or authorized purposes in each case")
    g.effect('ensure_employee_confidentiality','obligation',18,'recipient','unspecified','ensure')
    g.qualify('law_permits',18,['ensure_employee_confidentiality'],quote='To the extent permitted by law')
    g.qualify('employee_duty_duration_and_survival',18,['ensure_employee_confidentiality'])
    g.n('duty_exceptions','exception','unspecified',20)
    g.r('exception_for','duty_exceptions','hold_confidence',20)
    g.r('exception_for','duty_exceptions','no_disclosure',20)
    g.effect('exception_proof_burden','obligation',21,'recipient','unspecified','burden of proof')
    g.qualify('invoked_exceptions',21,['exception_proof_burden'],quote='to the extent it invokes them')
    g.r('owner','information','sintec',24)
    g.n('request','condition','request',25,quote='any time upon request')
    g.effect('request_return','obligation',25,'recipient','return','return',material='information',recipients=['sintec'])
    g.effect('request_destroy','obligation',25,'recipient','destruction','destroy',material='information')
    for e in ['request_return','request_destroy']:g.r('trigger',e,'request',25)
    g.qualify('sintec_option',25,['request_return','request_destroy'],quote="at SINTEC's option")
    g.qualify('request_return_mode',25,['request_return'],quote='promptly return it to SINTEC once and for all at no charge')
    g.qualify('destroy_no_copies',25,['request_destroy'],quote='destroy it without retaining any copies or records thereof')
    g.effect('no_reproduction','prohibition',27,None,'unspecified','reproductions',material='information')
    g.statement('possible_revocable_copy_consent',28,subject='sintec')
    g.n('reproductions','information','unspecified',29,name='any reproductions')
    g.effect('copy_return_or_destroy','obligation',29,'recipient','unspecified','return or destroy',material='reproductions')
    g.qualify('copy_request_and_51_modes',29,['copy_return_or_destroy'])
    g.n('final_return_scope','information','all_confidential_information_and_copies',31,quote='any and all information disclosed by SINTEC as well as any copies thereof')
    g.effect('business_end_return','obligation',31,'recipient','return','return',material='final_return_scope',recipients=['sintec'])
    g.n('business_end','condition','unspecified',31,quote='termination/expiration of the business relation- ship')
    g.r('trigger','business_end_return','business_end',31)
    g.statement('agreement_duration_and_renewal',34);g.statement('confidentiality_survival',35)
    g.statement('conditional_patent_reservation',37,subject='sintec')
    g.effect('patentable_findings_right','permission',39,'sintec','unspecified','apply for patent protection')
    g.qualify('new_patentable_findings',39,['patentable_findings_right'])
    g.statement('prior_use_waiver',40,subject='recipient')
    g.effect('sintec_nonassertion','prohibition',41,'sintec','unspecified','assert')
    g.qualify('outside_listed_fields',41,['sintec_nonassertion'],quote='provided the Receiving Party uses them outside the following fields of technology: paint and plant systems, automotive, automobile and aircraft production, energy and environmental systems, wood processing.')
    g.statement('patent_section_survival',42)
    g.effect('indemnity','obligation',44,'recipient','unspecified','indemnify',recipients=['sintec'])
    g.qualify('indemnity_breach_and_representative_scope',44,['indemnity'])
    for identity,unit in [('governing_law',47),('arbitration',49),('arbitration_place',50),('arbitrator_count',51),('arbitration_language',52),('severability',54),('written_changes',57),('separate_cooperation',59),('no_right_to_cooperation',60),('nda_independent_of_cooperation',61)]:g.statement(identity,unit)
    g.effect('replace_invalid_provision','permission',55,'sintec','unspecified','replace')
    g.qualify('invalidity_economic_replacement',55,['replace_invalid_provision'])
    return ['Receiving Party identity,signature dates and actual performances are unprovided;passive reproduction restriction has no invented actor.',
        'Only-selected-staff/necessary-extent wording is a restriction,not sufficient standalone disclosure permission;employment identities are not invented.',
        'The public-domain and lawfully-published exceptions apply to confidentiality duties,not an invented deletion of the Information definition;their alternatives and burden remain literal.',
        'Request return/destroy is at SINTEC option;no-copy/record qualifier stays with destruction,not every unrelated act.',
        'Termination/expiration of the business relationship is not asserted to be termination of this NDA;three-year term,two-year renewal,eighteen-month notice and three-year confidentiality survival remain distinct.',
        'Considering possible revocable reproduction consent is not an actual grant;patent waivers,field exclusions,indemnity and arbitration/replacement mechanics remain only partly formalized.']


def unhcr(g):
    g.n('unhcr','organization','disclosing_party',2,name='UNHCR')
    g.n('recipient','organization','receiving_party',6,name='Recipient')
    g.n('parties','group','either_party',7,name='Parties')
    g.n('information','information','confidential_information',14)
    g.qualify('designated_at_disclosure',14,['information'],quote='at the time of disclosure to the Recipient, is designated as confidential')
    g.effect('hold_confidence','obligation',15,'recipient','unspecified','held in trust and confidence',material='information')
    g.effect('same_care','obligation',17,'recipient','unspecified','use the same care and discretion',material='information')
    g.effect('purpose_only_use','obligation',19,'recipient','unspecified','use',material='information')
    g.qualify('disclosed_purpose',19,['purpose_only_use'],quote='solely for the purpose for which it was disclosed')
    g.n('other_party','group','other_third_parties',22,name='Any other party')
    g.effect('consented_other_party_sharing','permission',20,'recipient','disclosure','disclose',material='information',recipients=['other_party'])
    g.qualify('other_party_consent',22,['consented_other_party_sharing'],concept='written_consent',quote='the Discloser’s prior written consent')
    own='the Recipient’s employees, officials, representatives and agents'
    related='employees, officials, representatives and agents of any legal entity that it controls, controls it, or with which it is under common control'
    for identity,concept,name,quote in [
        ('own_employees','own_employees','employees',own),('own_officials','unspecified','officials',own),
        ('own_representatives','unspecified','representatives',own),('own_agents','agents','agents',own),
        ('affiliated_employees','affiliate_employees','employees',related),('affiliated_officials','unspecified','officials',related),
        ('affiliated_representatives','unspecified','representatives',related),('affiliated_agents','agents','agents',related)]:
        g.n(identity,'group',concept,23,quote=quote,name=name)
    own_ids=['own_employees','own_officials','own_representatives','own_agents']
    related_ids=['affiliated_employees','affiliated_officials','affiliated_representatives','affiliated_agents']
    g.n('related_entities','group','unspecified',23,quote='any legal entity that it controls, controls it, or with which it is under common control')
    for identity in own_ids:g.r('member_of',identity,'recipient',23)
    for identity in related_ids:g.r('member_of',identity,'related_entities',23)
    g.effect('own_personnel_sharing','permission',20,'recipient','disclosure','disclose',material='information',recipients=own_ids)
    g.effect('related_personnel_sharing','permission',20,'recipient','disclosure','disclose',material='information',recipients=related_ids)
    all_sharing=['consented_other_party_sharing','own_personnel_sharing','related_personnel_sharing']
    g.qualify('written_downstream_agreement',20,all_sharing,quote='Provided that the Recipient has a written agreement with the following persons or entities requiring them to treat the Confidential Information in accordance with this Agreement')
    g.qualify('own_strict_need',23,['own_personnel_sharing'],concept='need_to_know',quote='who have a strict need to know the contents of the Confidential Information')
    g.qualify('related_similar_need',23,['related_personnel_sharing'],concept='need_to_know',quote='who have a similar need to know the contents of the Confidential Information')
    for identity,unit in [('majority_control_option',24),('managerial_control_option',25),('UN_organ_option',26)]:
        g.n(identity,'condition','unspecified',unit);g.r('condition','related_entities',identity,unit)
    g.effect('required_law_disclosure','permission',28,'recipient','disclosure','disclose',material='information')
    g.qualify('law_required_extent',28,['required_law_disclosure'],quote='to the extent required by law')
    g.qualify('immunities_not_waived',28,['required_law_disclosure'],quote='subject to and without any waiver of the privileges and immunities of UNHCR')
    g.effect('law_prior_notice','obligation',28,'recipient','unspecified','give UNHCR sufficient prior notice',recipients=['unhcr'])
    g.qualify('protective_opportunity',28,['required_law_disclosure','law_prior_notice'],quote='in order to allow UNHCR to have a reasonable opportunity to take protective measures or such other action as may be appropriate before any such disclosure is made')
    g.effect('nonprecluded_disclosure','permission',30,'recipient','disclosure','disclosing',material='information')
    for identity,unit in [('lawful_unrestricted_source',31),('discloser_unrestricted_release',32),('previously_known',33),('completely_independent',34)]:
        g.n(identity,'condition','unspecified',unit);g.r('condition','nonprecluded_disclosure',identity,unit)
    g.effect('no_copy','prohibition',36,'recipient','unspecified','copy or reproduce',material='information')
    g.qualify('reasonable_purpose_copy_exception',36,['no_copy'],quote='except as reasonably required for the purposes contemplated in this Agreement')
    g.effect('copy_notices','obligation',36,'recipient','unspecified','ensure that any confidentiality or other proprietary rights notices',material='information')
    g.qualify('notices_on_all_copies',36,['copy_notices'],quote='are reproduced on all copies')
    g.statement('no_accuracy_warranty',37);g.statement('no_rights_grant',38)
    g.n('all_material','information','all_confidential_information_and_copies',39)
    g.effect('return','obligation',39,'recipient','return','returned',material='all_material',recipients=['unhcr'])
    g.effect('destroy','obligation',39,'recipient','destruction','destroyed',material='all_material')
    g.n('no_business_in_three_months','condition','unspecified',40)
    g.n('unhcr_request','condition','request',41)
    g.n('disposition_cases','condition','unspecified',39)
    for trigger in ['no_business_in_three_months','unhcr_request']:
        g.r('object','disposition_cases',trigger,40 if trigger=='no_business_in_three_months' else 41)
    for effect in ['return','destroy']:g.r('trigger',effect,'disposition_cases',39)
    g.qualify('return_or_destroy',39,['return','destroy'],quote='shall be returned to UNHCR or destroyed')
    g.qualify('prompt_request_case',41,['unhcr_request'],quote='promptly upon request by the UNHCR at any time')
    g.effect('indemnity','obligation',42,'recipient','unspecified','indemnify',recipients=['unhcr'])
    g.qualify('recipient_personnel_acts_omissions',42,['indemnity'])
    g.effect('terminate_working_relationship','permission',45,'parties','unspecified','terminate the working relationship')
    g.qualify('termination_written_notice',45,['terminate_working_relationship'],quote='by providing written notice to the other')
    g.n('relationship_fact','information','unspecified',51,quote='the fact that it has a confidential relationship with UNHCR')
    g.effect('relationship_publicity_ban','prohibition',51,'recipient','disclosure','make public',material='relationship_fact')
    g.effect('UN_name_use_ban','prohibition',51,'recipient','unspecified','use the name, emblem, or official seal')
    for identity,unit in [('no_business_obligation',43),('effective_signatures',44),('confidentiality_survival',45),('arbitration_after_20days',46),('no_punitive_awards',47),('limited_interest_authority',48),('award_binding',49),('UN_immunity',50),('severability',52),('integration',53),('signatory_authority',54)]:g.statement(identity,unit)
    return ['Bidder name,jurisdiction,addresses and execution dates are blank;no actual disclosure,notice,request,breach or arbitration is inferred.',
        'Definition requires designation as confidential at disclosure;2.5 permits specified disclosures rather than deleting the definition.',
        'Written downstream agreement governs all2.3 recipient branches;other-party consent and own/affiliated need-to-know conditions keep their respective scopes.',
        'Officials,representatives and agents are not automatically employees;majority ownership OR effective managerial control OR UN-organ definitions are not conjunctive tests.',
        'The nonprecluded-disclosure grounds and two disposition cases are alternatives not fully represented by flat edges.',
        'Failure to enter a business relationship within three months after both signatures is not Agreement termination;request-case promptness is not copied onto every case,arbitration20days or a fabricated90-day date.',
        'Confidentiality survival is not material-retention permission;return versus destruction chooser is not specified and is not invented.',
        'Immunities,indemnity,arbitration authority,publicity and conditional legal mechanics are preserved but not fully formalized.']


def biofiber(g):
    g.n('biofiber','organization','unspecified',2,name='JUST BIOFIBER STRUCTURAL SOLUTIONS CORP.')
    g.n('named_counterparty','group','unspecified',5,name='RECIPIENT')
    g.n('parties','group','either_party',6,name='Parties')
    g.n('receiving_role','group','receiving_party',6,name='Receiving Party')
    g.n('disclosing_role','group','disclosing_party',6,name='Disclosing Party')
    g.n('information','information','confidential_information',7)
    g.n('public_exception','exception','unspecified',8);g.n('prior_possession_exception','exception','unspecified',9)
    for e in ['public_exception','prior_possession_exception']:g.r('exception_for',e,'information',8 if e=='public_exception' else 9)
    g.qualify('written_record_proof',7,['public_exception','prior_possession_exception'],quote='the Receiving Party can establish through written records')
    g.qualify('nonpublic_compilation_caveat',8,['public_exception'],quote='where any part of such information is readily available to the trade or the public but a compilation of information which includes such part is not so available then such compilation shall be treated as Confidential Information hereunder')
    g.effect('purpose_use','obligation',10,'receiving_role','unspecified','use',material='information')
    g.qualify('purpose_limit',10,['purpose_use'],quote='solely for the Purpose')
    g.statement('no_mandatory_disclosure',11);g.statement('all_media_without_confidential_mark',12)
    g.effect('hold_confidence','obligation',13,'receiving_role','unspecified','keep the Confidential Information confidential',material='information')
    g.effect('protect_interest','obligation',13,'receiving_role','unspecified','protect',material='information')
    g.n('third_parties','group','other_third_parties',14,name='third party')
    g.effect('no_external_disclosure','prohibition',14,'receiving_role','disclosure','disclose',material='information',recipients=['third_parties'])
    g.qualify('external_prior_written_consent',14,['no_external_disclosure'],concept='written_consent',quote='without the Disclosing Party’s prior written consent')
    g.n('representatives','group','unspecified',14,name='Representatives')
    for identity,concept,name in [('directors','unspecified','directors'),('officers','unspecified','officers'),('employees','own_employees','employees')]:
        g.n(identity,'group',concept,14,name=name);g.r('member_of',identity,'representatives',14)
    g.effect('qualified_representative_sharing','permission',14,'receiving_role','disclosure','disclose',material='information',recipients=['representatives'])
    g.qualify('representative_need_to_know',14,['qualified_representative_sharing'],concept='need_to_know',quote='who have a need to know the Confidential Information for the Purpose')
    g.qualify('consistent_confidential_treatment',14,['qualified_representative_sharing'],quote='provided that the Receiving Party shall ensure that such Representatives treat the Confidential Information as confidential and at all times in a manner consistent with this Agreement')
    g.qualify('explicit_provided_however',14,['qualified_representative_sharing'],quote='provided however that the Receiving Party may disclose')
    g.effect('notify_unauthorized_use_possession','obligation',15,'receiving_role','unspecified','notify',recipients=['disclosing_role'])
    g.qualify('known_unauthorized_use_possession',15,['notify_unauthorized_use_possession'])
    g.effect('law_required_portion','obligation',16,'receiving_role','disclosure','disclose',material='information')
    g.qualify('law_or_court_order',16,['law_required_portion'],quote='required to disclose Confidential Information pursuant to any applicable law or an order from a court of competent jurisdiction')
    g.qualify('only_legally_required_portion',16,['law_required_portion'],quote='only disclose such portion of the Confidential Information that it is legally required to disclose')
    g.effect('reasonable_confidential_treatment_efforts','obligation',16,'receiving_role','unspecified','use all reasonable efforts',material='information')
    g.qualify('compelled_disclosure_case',16,['reasonable_confidential_treatment_efforts'])
    g.effect('required_disclosure_notice','obligation',17,'receiving_role','unspecified','promptly notify',recipients=['disclosing_role'])
    g.qualify('protective_notice_purpose',17,['required_disclosure_notice'],quote='so that the Disclosing Party may take appropriate steps to protect such Confidential Information from such disclosure')
    g.effect('no_copy','prohibition',18,'receiving_role','unspecified','copied or reproduced',material='information')
    g.effect('no_database_storage','prohibition',18,'receiving_role','unspecified','stored in a retrieval system or database',material='information')
    for e in ['no_copy','no_database_storage']:
        g.qualify(e+'_prior_consent',18,[e],quote='without the prior consent of the Disclosing Party')
        g.qualify(e+'_internal_purpose_exception',18,[e],quote='except for such copies and storage as may reasonably be required internally by the Receiving Party for the Purpose')
    g.effect('copy_proprietary_notices','obligation',19,'receiving_role','unspecified','contain the same proprietary notices',material='information')
    g.n('all_embodiments','information','all_confidential_information_and_copies',20,quote='the Confidential Information and all copies thereof in any form whatsoever')
    g.n('derivative_material','information','unspecified',20,quote='all compilations, analysis or derivative work relating to the Confidential Information')
    g.n('request','condition','request',20,quote='upon request')
    g.effect('return_embodiments','obligation',20,'receiving_role','return','return',material='all_embodiments',recipients=['disclosing_role'])
    g.effect('destroy_embodiments','obligation',20,'receiving_role','destruction','destroy',material='all_embodiments')
    g.effect('destroy_derivatives','obligation',20,'receiving_role','destruction','destroy',material='derivative_material')
    for e in ['return_embodiments','destroy_embodiments','destroy_derivatives']:g.r('trigger',e,'request',20)
    g.qualify('discloser_directs_choice',20,['return_embodiments','destroy_embodiments'],quote='or destroy, as directed by the Disclosing Party')
    g.qualify('embodiments_custody_scope',20,['return_embodiments','destroy_embodiments'],quote='under the power or control of the Receiving Party or its Representatives')
    g.qualify('immediate_derivative_destruction',20,['destroy_derivatives'],quote='and immediately destroy all compilations, analysis or derivative work')
    g.effect('destruction_certificate','obligation',21,'receiving_role','unspecified','deliver',recipients=['disclosing_role'])
    g.qualify('certificate_if_destroyed_embodiments',21,['destruction_certificate'],quote='Where the Receiving Party satisfies its obligation to return or destroy the embodiments of the Confidential Information by destroying such embodiments')
    g.qualify('certificate_officer_signature',21,['destruction_certificate'],quote='a certificate signed by an officer of the Receiving Party certifying such destruction of such embodiments')
    g.r('owner','information','disclosing_role',22)
    g.n('tangible_media','asset','other_asset',23,name='all tangible media')
    g.r('owner','tangible_media','disclosing_role',23)
    for identity,unit in [('no_implied_license',24),('as_is_warranty_limits',25),('errors_use_liability_limit',26),('no_updating_duty',27),('irreparable_harm_statement',28),('specific_reliance',29),('conditional_relief',30),('integration',31),('nonwaiver',32),('purpose_plus_two_year_term',33),('governing_law',34),('severability',36),('counterparts_permission',37),('counterparts_same_instrument',38),('execution_legal_advisor_context',39)]:g.statement(identity,unit)
    g.effect('no_assignment','prohibition',35,'parties','unspecified','assign')
    return ['The named counterparty RECIPIENT is not automatically the receiving role in every exchange;both parties can supply and receive information.',
        'Signature dates,named counterparty identity and actual Purpose completion or disclosure are unprovided;unmarked/all-media definition is retained.',
        'Written-record evidence qualifies both definition exclusions;public individual parts do not automatically exclude a nonpublic compilation.',
        'Directors and officers are not converted to employees;the explicit conditional representative permission keeps necessity,confidential-treatment and liability scope.',
        'Prior consent for copy/storage is not explicitly written;internal storage permission does not create a right to retain after request.',
        'Required-disclosure notice is prompt,but prior timing is not invented from its protective purpose.',
        'Request disposal means return OR directed destruction of embodiments,AND immediate destruction of derivatives;officer certificate is conditional on destroying embodiments.',
        'Purpose completion determines the two-year term extension,not an invented termination disposal trigger;execution discussion with legal advisors is not ongoing information-sharing permission.',
        'No-license,warranty,liability,counterparts and equitable-remedy mechanics and full Boolean scope remain incompletely formalized.']


def switchdigital(g):
    g.n('switchdigital','organization','unspecified',2,name='Switchdigital (London) Limited')
    g.n('applicant','group','unspecified',5,name='Applicant')
    g.n('parties','group','either_party',12,name='parties')
    g.n('recipient','group','receiving_party',22,name='receiving party')
    g.n('discloser','group','disclosing_party',24,name='disclosing party')
    g.n('information','information','confidential_information',18)
    for identity,unit in [('sample_analysis_scope',19),('prior_schedule_scope',20),('business_information_scope',21),('purpose_definition',17)]:g.statement(identity,unit)
    exceptions=[('public_no_breach',22),('prior_possession_limit',24),('independent_by_or_for_recipient',25),('other_source_no_breach',26),('unrestricted_release',27),('prior_written_approval',28)]
    for identity,unit in exceptions:
        g.n(identity,'exception','unspecified',unit);g.r('exception_for',identity,'information',unit)
    g.qualify('recipient_can_show',23,['prior_possession_limit','independent_by_or_for_recipient'])
    g.qualify('combination_caveat',29,[i for i,u in exceptions])
    g.effect('hold_confidence','obligation',32,'recipient','unspecified','maintain the same in confidence',material='information')
    g.effect('purpose_use','obligation',32,'recipient','unspecified','use',material='information')
    g.qualify('purpose_only',32,['purpose_use'],quote='only for the Purpose and for no other purpose')
    g.effect('no_commercial_use','prohibition',33,'recipient','unspecified','commercial use',material='information')
    g.effect('no_other_benefit_use','prohibition',34,'recipient','unspecified','use',material='information')
    g.qualify('further_agreement_exception',34,['no_other_benefit_use'])
    g.effect('no_search','prohibition',35,'recipient','unspecified','guiding or conducting a search',material='information')
    g.qualify('search_including_exception_demonstration',35,['no_search'])
    g.effect('no_copy','prohibition',36,'recipient','unspecified','copy reproduce or reduce to writing',material='information')
    g.qualify('reasonable_purpose_copy_exception',36,['no_copy'],quote='except as may be reasonably necessary for the Purpose')
    g.statement('copy_property',36,subject='discloser')
    g.n('employees','group','own_employees',37,name='employees')
    g.n('directors','group','unspecified',37,name='directors')
    g.n('contractors','group','contractors',37,name='contractors')
    g.n('third_parties','group','other_third_parties',37,name='third parties')
    g.effect('no_disclosure','prohibition',37,'recipient','disclosure','disclose',material='information',recipients=['employees','third_parties'])
    g.n('confidential_staff_exception','exception','unspecified',37)
    g.r('exception_for','confidential_staff_exception','no_disclosure',37)
    for identity in ['employees','directors','contractors']:g.r('recipient','confidential_staff_exception',identity,37)
    g.qualify('staff_confidence_purpose_need',37,['confidential_staff_exception'],concept='need_to_know',quote='except in confidence to such of its employees, directors or contractors who need to know the same for the Purpose')
    g.qualify('employment_or_service_contracts',38,['confidential_staff_exception'])
    g.effect('enforce_staff_obligations','obligation',39,'recipient','unspecified','enforce such obligations')
    g.qualify('own_expense_requested_breach_scope',39,['enforce_staff_obligations'])
    g.statement('responsibility_clause_header',40)
    g.n('responsibility_staff','group','unspecified',43,name='employees or directors')
    for identity,unit in [('responsibility_a',41),('responsibility_b',42),('responsibility_persons',43),('responsibility_crossref',44)]:g.statement(identity,unit)
    g.effect('security_care','obligation',45,'recipient','unspecified','apply',material='information')
    g.qualify('own_adequate_security_floor',45,['security_care'])
    g.effect('required_law_disclosure','permission',46,'recipient','disclosure','disclosure',material='information')
    g.qualify('required_by_law',46,['required_law_disclosure'],quote='any disclosure required by law')
    g.effect('law_notice','obligation',46,'recipient','unspecified','give',recipients=['discloser'])
    g.qualify('two_business_days',46,['required_law_disclosure','law_notice'],quote="not less than two business days' notice")
    g.effect('prior_consultation','obligation',46,'recipient','unspecified','consult',recipients=['discloser'])
    g.qualify('before_disclosure',46,['required_law_disclosure','prior_consultation'],quote='prior to such disclosure with a view to avoiding such disclosure if legally possible')
    g.n('return_material','information','unspecified',50,quote="all documents and materials (and all copies thereof) containing the other party's Confidential Information")
    g.effect('return','obligation',50,'parties','return','return',material='return_material')
    g.effect('return_certificate','obligation',50,'parties','unspecified','certify in writing')
    g.n('completion_or_written_request','condition','unspecified',50,quote='completion of the Purpose or receipt of a written request from the other party')
    for e in ['return','return_certificate']:g.r('trigger',e,'completion_or_written_request',50)
    g.qualify('one_month_return',50,['return','return_certificate'],quote='within one month')
    g.qualify('certificate_compliance',50,['return_certificate'],quote='that it has complied with the requirements of this sub-clause')
    g.n('agreement_publicity','information','unspecified',57,quote='the existence and nature of this Agreement')
    g.effect('publicity_confidentiality','obligation',57,'parties','unspecified','keep',material='agreement_publicity')
    g.effect('publicity_name_use_ban','prohibition',57,'parties','unspecified','use',material='agreement_publicity')
    g.qualify('publicity_opposite_party_written_consent',57,['publicity_name_use_ban'],concept='written_consent',quote='without the prior written consent of the other party')
    g.qualify('publicity_name_scope',57,['publicity_name_use_ban'])
    g.effect('written_notices','obligation',59,'parties','unspecified','notices under this Agreement shall be in writing')
    g.qualify('registered_recorded_delivery',59,['written_notices'])
    g.effect('no_assignment','prohibition',65,'parties','unspecified','assigned or otherwise transferred')
    g.qualify('assignment_opposite_consent',65,['no_assignment'],concept='written_consent',quote='without the prior written consent of the other party')
    g.effect('replacement_stipulation_endeavours','obligation',68,'parties','unspecified','use their reasonable endeavours')
    g.qualify('invalidity_replacement_scope',68,['replacement_stipulation_endeavours'])
    for identity,unit in [('handling_survival_after_return',51),('rights_reserved',53),('no_implied_license',54),('right_to_disclose_warranty',55),('notice_service_deeming',60),('one_year_term',62),('clauses123_survival',63),('severability',67),('unique_asset_statement',70),('conditional_injury',71),('conditional_equitable_relief',72),('other_relief',73),('counterparts_and_email',75),('no_partnership_or_trade_obligation',77),('nonwaiver',79),('integration',81),('written_amendments',82),('English_law_jurisdiction',83),('empty_schedule_heading',97)]:g.statement(identity,unit)
    return ['Applicant identity and execution day/month are blank;year2016 is not expanded into an exact date,and Schedule1 has no supplied prior-information inventory.',
        'The public/prior-possession/independent/third-source/unrestricted-release/written-approval exceptions retain the combination-of-features caveat;public pieces do not automatically exclude a secret combination.',
        'The separate search prohibition includes searching to demonstrate an exclusion;proof wording is not an invented permission to conduct that search.',
        'The confidential recipient exception keeps employees,directors and contractors distinct;the later responsibility clause names employees OR directors,not all contractors.',
        'Employment/services-contract constraints and requested enforcement at own expense keep their source scope;split(a)/(b)/(c) crossreferences are not fully formalized.',
        'Law-required disclosure needs at least two BUSINESS days notice AND prior consultation;general notice-service next-day deeming does not replace either condition.',
        'Return plus written certification is due within one MONTH after Purpose completion OR receipt of opposite-party written request;no destruction choice,30-day conversion or NDA-termination trigger is invented.',
        'The one-year NDA term and continuing clauses1/2/3 do not create a material-retention right;group-company names in publicity are not affiliate-employee recipients.',
        'Waivers,warranties,adequate-care guarantees,equitable relief and Boolean/reciprocal legal mechanics remain incompletely formalized.']


REVIEWERS={'5cad3f37':sintec,'de427b59':unhcr,'d50f9bcd':biofiber,'d9360f2a':switchdigital}


def reviewed_graph(source,units):
    locks={r['source']:r for r in read(LOCK_PATH)}
    if source not in locks or digest(units)!=locks[source]['units_sha256']:
        raise ValueError('Only four exact whole-source CNI views explicitly read here are reviewed')
    g=ClauseGraph(units);unknown=REVIEWERS[source.split(':')[1][:8]](g)
    return g.finish(complete=False,unknown=unknown)


def prepare():
    locks=read(LOCK_PATH)
    if len(locks)!=4 or len({r['source'] for r in locks})!=4 or Counter(r['role'] for r in locks)!=Counter(calibration=2,reference_only=2):
        raise ValueError('Keep the four original reviewed sources and roles')
    _,previous=previous_reviews();checkpoint=read(BASE/'handoff/current_checkpoint.json')
    roles={r['source']:r for r in read(ROOT/checkpoint['formal_source_reference_registry']['artifact_root']/'roles.json')}
    public_path=ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json';public={s['key']:s for s in read(public_path)}
    builders=[Path(__file__),LOCK_PATH,ROOT/'experiments/two_method_annotate.py',ROOT/'experiments/two_method_cni_short_source_reviews.py',
        ROOT/'legal_skill_guard/paired_interfaces/graph_interface.py',ROOT/'legal_skill_guard/skill_evolution/objects.py']
    protocol={'experiment':'four_midlength_CNI_whole_source_root_reviews_v1',
        'source_sha256':{str(p.relative_to(ROOT)):sha(p) for p in builders},'original_TRAIN_public_sha256':sha(public_path),
        'locked_original_roles_and_sources':locks,'prior58_explicit_manifest_sha256':digest(previous),
        'review_order':'next four by complete-source text length among original remaining10;no native outcomes',
        'remaining_six_CNI_and_all_original_other_sources_still_required':True,
        'native_target_questions_labels_weak_outputs_or_program_results_used':False,
        'explicit_root_review_not_automatic_semantic_certification':True,
        'interactive_root_annotation_cost_usd':None,'new_experimental_endpoint_requests':0}
    out=BASE/'CNI_mid_source_reviews_v1'/digest(protocol);immutable_json(out/'protocol.json',protocol)
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
            'verification_scope':'Every asserted local role/material/condition against all supplied units;unsupported Boolean and legal mechanics remain unknown.',
            'source_span_checks':gi.validate(graph,units),'review':{'entire_supplied_view_read':True,'source_sha_locked':True,
                'reciprocal_roles_recipient_branches_and_all_material_choices_preserved':True,
                'no_written_consent_prior_notice_date_business_day_or_termination_trigger_invented':True,
                'no_native_labels_reference_parameters_or_F_output_used_to_edit_graph':True},'new_model_requests':0}
        path=out/'cards'/digest([source,'v0'])/'source_review.json';immutable_json(path,card)
        rows.append({'source':source,'view':'v0','kind':'literal_semantic_graph','path':str(path.relative_to(ROOT)),'sha256':sha(path)})
    if len(rows)!=62 or len({(r['source'],r['view']) for r in rows})!=62:raise ValueError('Retain prior58 and new4 reviews exactly once')
    manifest={'reviews':rows,'new_root_reviewed_views':4,'previous_extra_reviews_retained':58,
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
    print(json.dumps({'artifact_root':str(out.relative_to(ROOT)),'new_reviewed_mothers':4,
        'cumulative_explicit_review_views':len(manifest['reviews']),'new_model_requests':0,'complete_goal_claimed':False},ensure_ascii=False))
