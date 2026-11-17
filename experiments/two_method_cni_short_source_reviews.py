"""Six whole-source CNI reviews,ordered by source length without outcomes.

The complete supplied contracts were read before these explicit recipes.
Quoted legal conditions are preserved;unselected form options,Boolean scope,
modal rights and unsupported boilerplate never become answer-bearing gold.
"""
from collections import Counter
from pathlib import Path
import json

from experiments.two_method_annotate import inputs
from experiments.two_method_graph_corpus import ROOT, BASE, read, sha
from experiments.two_method_maud_knowledge_reviews import ReviewedGraph
from experiments.two_method_airline_inventory_reviews import prepare as previous_reviews
from legal_skill_guard.paired_interfaces import graph_interface as gi
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


LOCK_PATH = ROOT / 'experiments/source_review_locks/cni_short6_20261117.json'


class ClauseGraph(ReviewedGraph):
    """Bookkeeping only;the source-specific recipes select every attachment."""
    def text(self, unit):
        return next(u['text'].strip() for u in self.units if u['id'] == unit)

    def n(self, identity, kind, concept, unit, *, name=None, quote=None):
        evidence = quote or self.text(unit)
        if not evidence or self.text(unit).count(evidence)!=1: raise ValueError('Keep a unique within-unit clause quote')
        if name is not None and name not in evidence: raise ValueError('Use literal node names')
        if identity in self.ids: raise ValueError('Duplicate reviewed node identity')
        self.ids.add(identity)
        self.nodes.append({'id':identity,'kind':kind,'concept':concept,'name':name or evidence[:120],
            'quote':evidence,'unit_id':unit})
        return identity

    def r(self, predicate, left, right, unit, *, quote=None, status='stated'):
        evidence = quote or self.text(unit)
        if not evidence or self.text(unit).count(evidence)!=1: raise ValueError('Relation quote left its reviewed unit')
        self.relations.append({'predicate': predicate, 'arguments': [left, right], 'value': None,
            'status': status, 'quote': evidence, 'unit_id': unit})

    def effect(self, identity, modality, unit, actor, action, name, *, material=None, recipients=()):
        self.n(identity, 'effect', modality, unit)
        self.n(identity+'_action', 'event', action, unit, name=name)
        if actor is not None: self.r('actor', identity, actor, unit)
        self.r('action', identity, identity+'_action', unit)
        if material: self.r('information', identity, material, unit)
        for recipient in recipients: self.r('recipient', identity, recipient, unit)
        return identity

    def qualify(self, identity, unit, effects, *, concept='unspecified', quote=None, name=None, kind='condition'):
        self.n(identity, kind, concept, unit, name=name, quote=quote)
        for effect in effects: self.r('condition', effect, identity, unit)
        return identity

    def statement(self, identity, unit, *, subject=None):
        self.n(identity, 'information', 'unspecified', unit)
        if subject: self.r('subject', identity, subject, unit)


def reviewed_graph(source, units):
    locks = {r['source']:r for r in read(LOCK_PATH)}
    if source not in locks or digest(units) != locks[source]['units_sha256']:
        raise ValueError('Only six exact whole-source views explicitly read here are reviewed')
    g = ClauseGraph(units); key = source.split(':')[1][:8]
    if key == 'a5b0361f':
        g.n('hydranautics','organization','disclosing_party',1,name='Hydranautics')
        g.n('visitor','group','receiving_party',1,name='Visitor')
        g.n('information','information','confidential_information',4)
        g.n('others','group','other_third_parties',6,name='others')
        g.qualify('tour_condition',3,[],name='touring Hydranautics’ facilities')
        g.statement('possible_access',2,subject='visitor');g.statement('exposure',5,subject='visitor')
        g.effect('hold_confidence','obligation',6,'visitor','unspecified','hold',material='information')
        g.qualify('same_care',6,['hold_confidence'],quote='will exercise at least the same care with respect thereto as it exercises with respect to its’ own confidential or proprietary information')
        g.effect('no_disclosure','prohibition',6,'visitor','disclosure','divulge',material='information',recipients=['others'])
        for identity,name in [('no_use','use'),('no_copy','copy'),('no_sell','sell'),('no_loan','loan')]:
            g.effect(identity,'prohibition',6,'visitor','unspecified',name,material='information')
        restricted=['no_disclosure','no_use','no_copy','no_sell','no_loan']
        # Clause3 says consent,not written consent. Clause4's written qualifier
        # belongs only to removing physical material from the premises.
        g.qualify('consent',6,restricted,quote='without Hydranautics’ consent')
        g.r('object','consent','hydranautics',6)
        g.effect('no_removal','prohibition',7,'visitor','unspecified','remove')
        g.n('physical_material','information','unspecified',7,name='any document, equipment or other materials')
        g.r('object','no_removal_action','physical_material',7)
        g.qualify('removal_written_consent',7,['no_removal'],concept='written_consent',quote='without Hydranautics’ written consent')
        g.r('object','removal_written_consent','hydranautics',7)
        g.effect('no_record','prohibition',8,'visitor','unspecified','photograph',material='information')
        g.qualify('record_scope',8,['no_record'],quote='photograph, videotape, or otherwise make any record of or preserve any Confidential Information')
        g.effect('safety','obligation',9,'visitor','unspecified','abide by all safety regulations')
        g.effect('designated_area','obligation',9,'visitor','unspecified','stay within designated areas')
        g.effect('no_unescorted_exit','prohibition',9,'visitor','unspecified','leave the touring party')
        g.qualify('escort',9,['no_unescorted_exit'],quote='without an escort by a Hydranautics authorized employee')
        for identity,unit in [('governing_law',10),('integration',11),('possible_liability',12)]:g.statement(identity,unit)
        unknown=['Visitor identity and legal person type,execution date and any actual performance are not supplied.',
            'Clause3 consent is not explicitly written;clause4 written consent does not waive the separate record-making prohibition.',
            'Facility access is possible,not a finding that a particular trade secret was actually observed;Nitto is not assigned an unstated corporate relationship.',
            'Liability is modal and governing/integration mechanics remain literal statements,not fully formalized legal effects.']
    elif key == 'bc93d2a7':
        g.n('company','group','disclosing_party',3,name='Company')
        g.n('recipient','group','receiving_party',3,name='Recipient')
        g.n('information','information','confidential_information',3)
        g.effect('confidentiality','obligation',4,'recipient','unspecified','maintain the confidence',material='information')
        g.effect('prevent_unauthorized_dissemination','obligation',4,'recipient','unspecified','prevent its unauthorized dissemination',material='information')
        for identity,unit in [('public_no_fault',5),('prior_knowledge',6),('independent_without_use',7),('lawful_third_party',8),('written_disclosure_agreement',9)]:
            g.n(identity,'exception','unspecified',unit)
            g.r('exception_for',identity,'information',unit)
        g.effect('purpose_limit','prohibition',10,'recipient','unspecified','use',material='information')
        g.qualify('business_evaluation_purpose',10,['purpose_limit'],quote='for purposes other than those necessary to consider the possibility of entering into a business relationship with the Company')
        g.r('owner','information','company',11)
        # A denied license grant is a negative proposition,not a prohibition
        # against every possible independently licensed act.
        g.statement('no_license_grant',11);g.statement('as_is_no_warranty',12)
        g.n('all_return_material','information','all_confidential_information_and_copies',13)
        g.effect('return','obligation',13,'recipient','return','return',material='all_return_material',recipients=['company'])
        g.n('written_request','condition','request',13,quote='upon the Company’s written request')
        g.r('trigger','return','written_request',13);g.r('actor','written_request','company',13)
        g.qualify('immediate',13,['return'],quote='immediately upon the Company’s written request')
        g.effect('export_compliance','obligation',14,'recipient','unspecified','comply with all United States export controls',material='information')
        g.statement('possible_irreparable_harm',15)
        g.effect('relief_right','permission',16,'company','unspecified','seek and obtain immediate injunctive relief')
        g.qualify('relief_breach_condition',16,['relief_right'],quote='from breaches of this Agreement')
        for identity,unit in [('governing_law',17),('exclusive_jurisdiction',18)]:g.statement(identity,unit)
        # The appended exam text does not establish Company=VMware or
        # Recipient=the particular candidate. Keep its conditional flow separate.
        g.n('exam_candidate','group','unspecified',19,name='YOUR')
        g.effect('exam_acceptance','obligation',19,'exam_candidate','unspecified','accept the terms and conditions')
        g.qualify('before_exam',19,['exam_acceptance'],quote='Prior to taking YOUR exam')
        g.statement('agreement_view',20)
        g.n('decline_after_begin','condition','unspecified',21)
        g.n('cancel_and_forfeit','effect','unspecified',21)
        g.r('condition','cancel_and_forfeit','decline_after_begin',21)
        g.r('actor','cancel_and_forfeit','exam_candidate',21)
        g.statement('yes_click_binding',22,subject='exam_candidate');g.statement('no_click_exit',23,subject='exam_candidate')
        unknown=['The Company and Recipient identities/legal forms are unprovided;VMware in appended exam text is not silently merged with Company.',
            'Definition exclusions remain alternatives;written permission to disclose is not a claim that all information was already released.',
            'No actual request,breach,injunction or exam choice is asserted;the exam-candidate referent is not established as the contractual Recipient.',
            'The detailed exam acceptance/cancellation/forfeiture mechanism and denied-license/warranty/venue propositions are only partly represented by this ontology.']
    elif key == '8fb38aee':
        g.n('first','group','unspecified',4,name='1st Party');g.n('second','group','unspecified',4,name='2nd Party')
        g.n('parties','group','either_party',4,name='Parties')
        g.n('information','information','confidential_information',17)
        g.statement('derived_material_definition',18)
        g.n('unilateral_option','condition','unspecified',9);g.n('mutual_option','condition','unspecified',10)
        g.n('selection','condition','unspecified',8)
        g.r('condition','selection','unilateral_option',9,status='unknown')
        g.r('condition','selection','mutual_option',10,status='unknown')
        # Do not choose a mode or tag either named party as the actual
        # receiving/disclosing party from an unchecked form alternative.
        g.effect('unilateral_nondisclosure','prohibition',9,'second','disclosure','disclosing',material='information')
        g.qualify('unilateral_selected',9,['unilateral_nondisclosure'],quote='Unilateral – This Agreement shall be Unilateral')
        g.effect('mutual_nondisclosure','prohibition',10,'parties','disclosure','disclosing',material='information')
        g.qualify('mutual_selected',10,['mutual_nondisclosure'],quote='Mutual – This Agreement shall be Mutual')
        for identity,unit in [('public',20),('programming',21),('prior_possession',22),('independent',23)]:
            g.n(identity,'exception','unspecified',unit);g.r('exception_for',identity,'information',unit)
        g.effect('hold_confidence','obligation',25,'parties','unspecified','hold and maintain',material='information')
        g.n('need_to_know_group','group','unspecified',25,quote='their agents, employees, representatives, affiliates, and any other individual or entity')
        g.qualify('need_to_know',25,['hold_confidence'],concept='need_to_know',quote='“need to know” basis')
        g.r('object','need_to_know','need_to_know_group',25)
        # The malformed "hold ... and to" wording is not silently rewritten
        # into a new unconditional disclosure permission.
        g.statement('responsible_party_liability',26)
        for identity,action,concept in [('no_publication','publish','disclosure'),('no_copy','copy','unspecified'),('no_sole_benefit_use','use','unspecified')]:
            g.effect(identity,'prohibition',27,'parties',concept,action,material='information')
        effects=['no_publication','no_copy','no_sole_benefit_use']
        g.qualify('opposite_party_written_approval',27,effects,concept='written_consent',quote='without the written approval of the other Party')
        g.qualify('sole_benefit_qualification',27,effects,quote='for their sole benefit')
        g.n('materials','information','unspecified',28,name='any and all materials')
        g.n('requesting_party','group','unspecified',28,name='Requesting Party')
        g.effect('return','obligation',28,'parties','return','return',material='materials',recipients=['requesting_party'])
        g.n('request','condition','request',28,quote='If requested')
        g.r('trigger','return','request',28)
        g.qualify('blank_return_deadline',28,['return'],quote='within ____ days')
        g.qualify('sectionV_unilateral_exception',29,['hold_confidence','no_publication','no_copy','no_sole_benefit_use','return'],quote='This Section shall not apply to the 1st Party if this Agreement is Unilateral as marked in Section II.')
        for identity,unit in [('confidentiality_duration',31),('integration',33),('written_amendment',34),('severability',36),('possible_relief',38),('available_remedies',39),('governing_law',41)]:g.statement(identity,unit)
        unknown=['Both Unilateral/Mutual boxes are unchecked;roles,mode and SectionV exclusion cannot be resolved to a selected case.',
            'Return deadline and signature dates/identities are blank;any-and-all materials is not strengthened to every defined information item and copy.',
            'The hold-and-to sentence has unresolved sharing grammar;need-to-know recipients are not an unconditional permission.',
            'The sole-benefit modifier and conditional SectionV party exclusion are not completely represented by flat effects.',
            'Duration ends on no-longer-trade-secret OR written release;continued confidentiality is not a right to retain materials.',
            'Amendment,severability,possible relief and notice/release mechanics remain literal propositions,not complete legal models.']
    elif key == '78adf3b3':
        g.n('college','organization','disclosing_party',4,name='Tompkins Cortland Community College')
        g.n('company','organization','receiving_party',4,name='Company')
        g.n('parties','group','either_party',7,name='Parties')
        g.n('recipient','group','receiving_party',8,name='Recipient')
        g.n('discloser','group','disclosing_party',9,name='Discloser')
        g.n('information','information','confidential_information',12)
        g.statement('additional_definition',13);g.statement('generated_or_oral_definition',14)
        g.effect('purpose_only_use','obligation',10,'parties','unspecified','use',material='information')
        g.qualify('agreed_service_purpose',10,['purpose_only_use'],quote='solely for the purpose of performing the service or services for which the Company and Tompkins Cortland Community College have made an agreement')
        g.qualify('necessary_extent',10,['purpose_only_use'],quote='only to the extent necessary for the stated Purpose')
        g.n('third_parties','group','other_third_parties',11,name='third parties or business partners')
        g.effect('no_external_disclosure','prohibition',11,'recipient','disclosure','provide',material='information',recipients=['third_parties'])
        g.qualify('college_written_agreement',11,['no_external_disclosure'],concept='written_consent',quote='without prior written agreement from Tompkins Cortland Community College')
        g.r('object','college_written_agreement','college',11)
        g.r('owner','information','college',15);g.statement('limited_use_no_other_license',16)
        g.effect('care','obligation',17,'company','unspecified','use the same degree of care',material='information')
        g.qualify('reasonable_minimum',17,['care'],quote='but in any event not less than reasonable care and means')
        g.n('employees','group','own_employees',18,name='employees')
        g.n('contractors','group','contractors',18,name='contractors')
        g.r('member_of','employees','recipient',18);g.r('member_of','contractors','recipient',18)
        g.effect('limited_sharing','permission',18,'recipient','disclosure','disclosed',material='information',recipients=['employees','contractors'])
        g.qualify('sharing_need_to_know',18,['limited_sharing'],concept='need_to_know',quote='with a “need to know”')
        g.qualify('sharing_written_confidentiality',18,['limited_sharing'],quote='who are subject to written confidentiality agreements sufficient to carry out the intent of this Agreement')
        g.n('request','condition','request',20,quote='Upon request of Tompkins Cortland Community College')
        g.r('actor','request','college',20)
        g.n('copy_material','information','unspecified',20,quote='all copies of the Confidential Information, in whatever form or media')
        g.n('destruction_material','information','confidential_information',20,quote='all such Confidential Information')
        g.effect('return','obligation',20,'company','return','return',material='copy_material',recipients=['college'])
        g.effect('certify_destruction','obligation',20,'company','unspecified','certify the destruction',material='destruction_material')
        for e in ['return','certify_destruction']:g.r('trigger',e,'request',20)
        g.qualify('disposition_choice',20,['return','certify_destruction'],quote='or certify the destruction of all such Confidential Information')
        g.qualify('prompt',20,['return','certify_destruction'],quote='shall promptly return')
        g.effect('written_notices','obligation',21,'parties','unspecified','notices shall be in writing')
        g.qualify('notice_delivery_receipt_rules',21,['written_notices'])
        g.effect('no_assignment','prohibition',26,'parties','unspecified','assign its rights or delegate its duties or obligations')
        g.qualify('opposite_party_assignment_consent',26,['no_assignment'],concept='written_consent',quote='without the other Party’s prior written consent')
        g.effect('statutory_compliance','obligation',30,'company','unspecified','comply with the provisions')
        for identity,unit in [('effective_full_execution',19),('severability',22),('limited_waiver',23),('conditional_equitable_relief',24),('governing_law',25),('integration',27),('law_list_part1',28),('law_list_part2',29),('conditional_breach_costs',31)]:g.statement(identity,unit)
        unknown=['The Company identity,dates and contents of the separate service agreement are unprovided;service beneficiaries are not employers.',
            'College consent and need-to-know/written-bound recipient clauses coexist;the graph does not decide an unstated override between them.',
            'Return-all-copies OR certification of destruction is a choice,not two unconditional simultaneous duties;certification is not collapsed into an extra destruction command.',
            'The five-day mailing rule belongs only to notices,not the prompt return deadline.',
            'The split law list and conditional negligence/breach/remedy,severability,waiver and execution mechanisms are preserved but not fully formalized.']
    elif key == '96361e4d':
        g.n('parties','group','either_party',4,name='parties')
        g.n('provider','group','disclosing_party',6,name='Provider')
        g.n('recipient','group','receiving_party',6,name='Recipient')
        g.n('information','information','confidential_information',6)
        for identity,unit in [('initial_public',8),('later_public_no_wrongful_disclosure',9),('prior_possession_with_awareness_limit',10),('lawful_good_faith_source',11)]:
            g.n(identity,'exception','unspecified',unit);g.r('exception_for',identity,'information',unit)
        g.n('third_parties','group','other_third_parties',13,name='third party')
        g.effect('no_disclosure','prohibition',13,'parties','disclosure','disclose',material='information',recipients=['third_parties'])
        g.effect('hold_confidence','obligation',13,'parties','unspecified','hold in strict confidence',material='information')
        g.qualify('continuing_confidence',13,['hold_confidence','no_disclosure'],quote='at all times and notwithstanding any termination or expiration of this Agreement')
        g.qualify('opposite_party_prior_consent',13,['no_disclosure'],concept='written_consent',quote='except as approved in advance in writing by the other party to this Agreement')
        g.effect('business_purpose','obligation',13,'parties','unspecified','use',material='information')
        g.qualify('business_purpose_limit',13,['business_purpose'],quote='for no purpose other than evaluating or pursuing a business relationship with the other party')
        for identity,concept,name in [('employees','own_employees','employees'),('advisors','unspecified','advisors'),('agents','agents','agents')]:
            g.n(identity,'group',concept,15,name=name);g.r('member_of',identity,'recipient',15)
        g.effect('limited_sharing','unspecified',15,'recipient','disclosure','share',material='information',recipients=['employees','advisors','agents'])
        g.qualify('purpose_necessity',15,['limited_sharing'],quote='when such disclosure is necessary for the purpose for which the Provider disclosed the information')
        g.n('staff','group','unspecified',16,name='employees, advisors, and agents')
        g.effect('staff_bound','obligation',16,'staff','unspecified','be bound by this Agreement')
        g.qualify('staff_access',16,['staff_bound'],quote='with access to Confidential Information')
        g.statement('recipient_responsibility',16,subject='recipient')
        g.n('valid_compulsion','exception','unspecified',18)
        g.r('exception_for','valid_compulsion','no_disclosure',18)
        g.qualify('valid_subpoena_or_order',18,['valid_compulsion'],quote='a valid subpoena or order by a court or other government body')
        g.effect('prior_notice','obligation',18,'recipient','unspecified','presents the Provider with as much prior written notice',recipients=['provider'])
        g.qualify('reasonable_notice',18,['valid_compulsion','prior_notice'],quote='as is reasonable in order to permit the Provider an opportunity to seek confidential treatment')
        g.effect('care','obligation',19,'recipient','unspecified','use at least as much care',material='information')
        g.qualify('reasonable_care_floor',19,['care'],quote='at least reasonable care')
        g.effect('notify_loss','obligation',21,'parties','unspecified','immediately notify')
        g.qualify('loss_or_unauthorized_disclosure',21,['notify_loss'],quote='upon discovery of any loss or unauthorized disclosure of the Confidential Information of the other party')
        g.effect('no_reproduction','prohibition',23,None,'unspecified','reproduced',material='information')
        g.qualify('reproduction_purpose_exception',23,['no_reproduction'],quote='except as required to accomplish the intent of this Agreement')
        g.statement('copy_ownership_and_legends',24,subject='provider')
        g.n('disposition_trigger','condition','unspecified',26,quote='Upon termination or expiration of the Agreement, or upon written request by either party')
        g.n('tangible_return_scope','information','unspecified',26,quote="all documents and other tangible materials representing the other's Confidential Information and all copies thereof")
        g.n('all_destroy_scope','information','all_confidential_information_and_copies',26,quote='all Confidential Information and copies thereof')
        g.effect('return','obligation',26,'parties','return','return',material='tangible_return_scope')
        g.effect('destroy','obligation',26,'parties','destruction','destroy',material='all_destroy_scope')
        g.effect('certify','obligation',26,'parties','unspecified','certify its destruction',material='all_destroy_scope',recipients=['provider'])
        for e in ['return','destroy','certify']:g.r('trigger',e,'disposition_trigger',26)
        g.qualify('return_or_destroy_choice',26,['return','destroy'],quote='or destroy all Confidential Information and copies thereof and certify its destruction to the Provider')
        g.qualify('certification_destroy_only',26,['certify'],quote='destroy all Confidential Information and copies thereof and certify its destruction to the Provider')
        g.qualify('prompt_disposition',26,['return','destroy'],quote='shall promptly return')
        g.effect('early_termination','permission',32,'parties','termination','terminate')
        g.qualify('ninety_day_prior_notice',32,['early_termination'],quote='at least 90 days prior written notice')
        for identity,unit in [('no_property_grant',28),('no_partnership_without_separate_agreement',29),('signature_effective_and_three_year_term',31),('two_year_confidentiality_survival',33),('governing_law',35),('conditional_equitable_relief',37),('interpretation',39),('severability',40),('fair_meaning',41),('integration',43),('supersession',44),('no_reliance_and_signed_amendment',45)]:g.statement(identity,unit)
        unknown=['Party names and execution dates are blank;Provider/Recipient roles stay relational and opposite-party consent is not self-consent.',
            'Advisors have no supplied legal/financial specialty;necessity of sharing is not silently recast as a different predicate.',
            'Will only share imposes a recipient/necessity restriction;it does not establish a standalone sufficient permission or a duty to actually disclose.',
            'Valid compulsory disclosure is conditionally nonviolating,not a command or a permission for every possible disclosure;notice is reasonable prior written notice.',
            'Disposition trigger is termination OR expiration OR written request;the current compact termination_or_request tag would omit expiration,so the literal three-way trigger is retained.',
            'Return tangible material OR destroy all information plus certification is a branch choice,not a conjunction of unconditional acts.',
            'The three-year term,90-day prior termination notice,two-year post-termination confidentiality and at-all-times language are kept without resolving their legal interaction.',
            'The reproduction clause is passive;its actor is not filled from the following copy-ownership clause.',
            'Property denial,copy legends,partnership,amendment,remedy and interpretation machinery is not fully formalized;survival is not material-retention permission.']
    elif key == 'ef7bf53e':
        g.n('crane','organization','receiving_party',11,name='Crane Co.')
        g.n('liberty','organization','disclosing_party',4,name='Liberty Technologies, Inc.')
        g.n('business','group','unspecified',11,name='divisions or subsidiaries of Liberty Technologies, Inc.')
        g.n('information','information','confidential_information',14)
        g.n('representatives','group','unspecified',14,name='representatives')
        for identity,concept,name in [('attorneys','legal_advisors','attorneys'),('accountants','unspecified','accountants'),('financial_advisors','financial_advisors','financial advisors')]:
            g.n(identity,'group',concept,14,name=name);g.r('member_of',identity,'representatives',14)
        g.n('agents','group','agents',14,name='agents');g.n('employees','group','own_employees',14,name='employees')
        g.effect('no_disclosure','prohibition',16,'crane','disclosure','disclosed',material='information')
        g.qualify('prior_written_consent',16,['no_disclosure'],concept='written_consent',quote='without your prior written consent')
        g.effect('transaction_only_use','obligation',16,'crane','unspecified','used',material='information')
        for effect in ['no_disclosure','transaction_only_use']:
            for actor in ['agents','representatives','employees']:g.r('actor',effect,actor,16)
        g.qualify('transaction_purpose',16,['transaction_only_use'],quote='other than in connection with the transaction described above')
        g.effect('limited_sharing','unspecified',17,'crane','disclosure','reveal',material='information',recipients=['agents','representatives','employees'])
        g.qualify('need_to_know_purpose',17,['limited_sharing'],concept='need_to_know',quote='who need to know the Information for the purpose of evaluating the transaction described above')
        g.qualify('informed_confidential_nature',17,['limited_sharing'],quote='who are informed by us of the confidential nature of the Information')
        g.qualify('written_agreement',17,['limited_sharing'],quote='who shall agree in writing to act in accordance with the terms and conditions of this Agreement')
        g.statement('representative_breach_responsibility',18,subject='crane')
        g.n('discussion_facts','information','unspecified',19,quote='the fact that the Information has been made available, that discussions or negotiations are taking place or have taken place')
        g.n('any_person','group','other_third_parties',19,name='any person or entity')
        g.effect('discussion_nondisclosure','prohibition',19,'crane','disclosure','disclose',material='discussion_facts',recipients=['any_person'])
        g.qualify('discussion_consent_or_law',19,['discussion_nondisclosure'],quote='Without your prior written consent, except as required by law')
        g.effect('written_information_record','obligation',20,'crane','unspecified','keep a record',material='information')
        g.n('returned_subset','information','unspecified',21)
        g.effect('return','obligation',21,'crane','return','returned',material='returned_subset',recipients=['liberty'])
        g.n('request','condition','request',21,quote='upon your request');g.r('trigger','return','request',21)
        g.qualify('prepared_document_exclusion',21,['return'],quote='except for that portion of the Information which consists of analyses, compilations, forecasts, studies or other documents prepared by us, our agents, representatives or employees')
        g.qualify('immediate_return',21,['return'],quote='immediately upon your request')
        g.n('prepared_subset','information','some_confidential_information',22,quote='That portion of the Information which consists of analyses, compilations, forecasts, studies or other documents prepared by us, our agents, representatives or employees')
        g.effect('prepared_hold','obligation',22,'crane','retention','held',material='prepared_subset')
        g.effect('prepared_destroy','obligation',22,'crane','destruction','destroyed',material='prepared_subset')
        g.n('prepared_request','condition','request',22,quote='upon your request');g.r('trigger','prepared_destroy','prepared_request',22)
        g.qualify('prepared_confidentiality',22,['prepared_hold'],quote='kept confidential and subject to the terms of this Agreement')
        g.qualify('prepared_disposition_choice',22,['prepared_hold','prepared_destroy'],quote='or destroyed upon your request')
        g.statement('oral_information_survival',22)
        g.n('document_preparers','group','unspecified',23,name='person or persons who prepared such documents')
        g.effect('written_destruction_confirmation','obligation',23,'crane','unspecified','confirmed in writing',material='prepared_subset',recipients=['liberty'])
        g.r('actor','written_destruction_confirmation','document_preparers',23)
        g.r('condition','written_destruction_confirmation','prepared_destroy',23)
        for identity,unit in [('public_without_own_disclosure',25),('lawful_nonconfidential_other_source',26),('independent_competitive_development',27)]:
            g.n(identity,'exception','unspecified',unit);g.r('exception_for',identity,'information',unit)
        g.effect('contact_restriction','prohibition',28,'crane','unspecified','communicate')
        g.qualify('contact_scope_consent',28,['contact_restriction'])
        g.effect('employee_solicitation_restriction','prohibition',29,'crane','unspecified','solicit for employment')
        g.qualify('solicitation_duration_consent_and_targets',29,['employee_solicitation_restriction'])
        for identity,unit in [('accuracy_no_warranty',30),('limited_final_agreement_reliance',31)]:g.statement(identity,unit)
        g.effect('compulsion_notice','obligation',32,'crane','unspecified','provide you with prompt written notice and oral notice',recipients=['liberty'])
        g.qualify('actual_compulsion_case',32,['compulsion_notice'],quote='we or anyone to whom we transmit the Information pursuant to this Agreement becomes legally compelled to disclose any of the Information')
        g.effect('limited_compelled_disclosure','obligation',33,'crane','disclosure','furnish',material='information')
        g.qualify('no_order_or_business_waiver',33,['limited_compelled_disclosure'],quote='such protective order or other remedy is not obtained, or that the Business waives compliance')
        g.qualify('advised_legally_required_portion',33,['limited_compelled_disclosure'],quote="only that portion of the Information which we are advised by the Business or the Business' attorney we are legally required to furnish")
        g.effect('directed_confidentiality_efforts','obligation',33,'crane','unspecified','exercise the efforts directed by the Business')
        g.qualify('efforts_conditional_case',33,['directed_confidentiality_efforts'])
        g.statement('directed_cost_reimbursement',34,subject='business')
        g.effect('standstill','prohibition',35,'crane','unspecified','purchase')
        g.qualify('standstill_scope_affiliates_term_and_board_approval',35,['standstill'])
        for identity,unit in [('fixed_expiry',36),('governing_law',37),('conditional_injunctive_relief',38),('signature_date',46)]:g.statement(identity,unit)
        unknown=['Business denotes specified divisions/subsidiaries,not automatically every Liberty entity;accountants are not silently renamed financial advisors.',
            'The general consent clause and limited employee/representative sharing need their exact conditions;flat clauses do not certify an unstated override.',
            'Agree to reveal only limits recipients;the restriction is not promoted to a sufficient standalone permission or a mandatory disclosure act.',
            'Required-by-law exception in the discussion-facts clause does not become a blanket exception to all information obligations.',
            'Return excludes the prepared subset;prepared-document holding versus request destruction is an alternative scope,not unqualified retention of all information.',
            'Continuing oral confidentiality and keeping a written-information location record do not create extra retention rights.',
            'The Business or its attorney supplies legal-necessity advice,not a newly permitted disclosure recipient;both written AND oral compulsion notice are retained.',
            'The standstill/contact/employment-target Boolean scope,conditional remedies and signature/effective-date relationship remain incompletely formalized;no actual legal compulsion,termination or fee is inferred.']
    else:raise ValueError('No explicit root-reviewed recipe for this source')
    return g.finish(complete=False,unknown=unknown)


def prepare():
    locks=read(LOCK_PATH)
    if len(locks)!=6 or Counter(r['role'] for r in locks)!=Counter(development=4,calibration=1,reference_only=1):
        raise ValueError('Keep the six original reviewed mothers and roles')
    _,previous=previous_reviews();checkpoint=read(BASE/'handoff/current_checkpoint.json')
    roles={r['source']:r for r in read(ROOT/checkpoint['formal_source_reference_registry']['artifact_root']/'roles.json')}
    public_path=ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json';public={s['key']:s for s in read(public_path)}
    builders=[Path(__file__),LOCK_PATH,ROOT/'experiments/two_method_annotate.py',
        ROOT/'experiments/two_method_maud_knowledge_reviews.py',ROOT/'experiments/two_method_airline_inventory_reviews.py',
        ROOT/'legal_skill_guard/paired_interfaces/graph_interface.py',ROOT/'legal_skill_guard/skill_evolution/objects.py']
    protocol={'experiment':'six_short_CNI_whole_source_root_reviews_v1',
        'source_sha256':{str(p.relative_to(ROOT)):sha(p) for p in builders},'original_TRAIN_public_sha256':sha(public_path),
        'locked_original_roles_and_sources':locks,'prior52_explicit_manifest_sha256':digest(previous),
        'review_order':'shortest remaining16 CNI complete-source texts;no outcome or native-question selection',
        'all16_original_CNI_mothers_still_required_no_scope_reduction':True,
        'native_target_questions_labels_weak_outputs_or_program_results_used':False,
        'explicit_root_review_not_automatic_semantic_certification':True,
        'interactive_root_annotation_cost_usd':None,'new_experimental_endpoint_requests':0}
    out=BASE/'CNI_short_source_reviews_v1'/digest(protocol);immutable_json(out/'protocol.json',protocol)
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
            'verification_scope':'Asserted local entities/effects/conditions against every supplied source unit;unrepresented Boolean/legal mechanics remain explicit unknown.',
            'source_span_checks':gi.validate(graph,units),'review':{'entire_supplied_view_read':True,'source_sha_locked':True,
                'no_unselected_form_option_blank_date_deadline_or_legal_specialty_filled':True,
                'no_survival_to_retention_or_request_to_termination_inference':True,
                'no_native_labels_reference_parameters_or_F_output_used_to_edit_graph':True},'new_model_requests':0}
        path=out/'cards'/digest([source,'v0'])/'source_review.json';immutable_json(path,card)
        rows.append({'source':source,'view':'v0','kind':'literal_semantic_graph','path':str(path.relative_to(ROOT)),'sha256':sha(path)})
    if len(rows)!=58 or len({(r['source'],r['view']) for r in rows})!=58:raise ValueError('Retain prior52 and new6 reviews exactly once')
    manifest={'reviews':rows,'new_root_reviewed_views':6,'previous_extra_reviews_retained':52,
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
