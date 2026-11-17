"""Source-local CNI audits; each complete supplied contract is read first.

Approvals bind original source/proposal hashes, not task answers. Unrepresented
Boolean scope, partial quotations and unsupported legal effects remain unknown.
"""
import json

from experiments.two_method_source_reviews import BASE, persist_review
from legal_skill_guard.skill_evolution.objects import digest


REVIEWS = {
    'ContractNLI:467e2e05': {
        'graph_sha256': 'aaa07b45c6538e3ddfdcc63d908662bca6f59aad9504e2975eac8dcd98a3e689',
        'units_sha256': '0e02c8b889437a558a63f85246e71ed419c1b1e067ef21f914b94fe1c3a906bf',
        'review': 'All seventy supplied units, seventy-seven nodes and one hundred original relations were checked. Parties and represented subclasses, definition exceptions, confidentiality/use/disclosure rules, four required representative-disclosure conditions, legal-process duties, alternative written-copy disposition branches, counsel-file retention and the securities/standstill clauses are source-supported subject to the retained limitations. Best of knowledge is not explicit actual wording. The non-transactional-use condition must retain other than. Written copies do not encompass all oral Information, and the initiator is not automatically a disclosing party. Counsel-file custody is a retention condition, not a permission to disclose to attorneys. Add missing source-prohibition qualifications to the information exclusions and preserve the either/or disposition and independent request/not-proceed trigger logic. A proposal recipient is COMSYS board, not all COMSYS; standstill assets are not an information recipient. Additional prompt decision-notice, written destruction confirmation, reimbursement and venue duties remain unrepresented, so inventory is incomplete. All original unresolved branch/date/retention/standstill statements remain. No native question or label was used.',
        'evidence': [
            {'unit_id': 7, 'quote': 'is not known to be prohibited from disclosing such information to the receiving Party by a legal, contractual or fiduciary obligation to either Party'},
            {'unit_id': 8, 'quote': 'was not known by the receiving Party, after due inquiry, to be subject to an obligation not to disclose such information'},
            {'unit_id': 13, 'quote': 'will not use any Information other than in connection with the Transaction'},
            {'unit_id': 21, 'quote': 'the other party will either'},
            {'unit_id': 22, 'quote': 'confirm such destruction to the initiating company in writing'},
            {'unit_id': 24, 'quote': 'Any oral Information will continue to be subject to the terms of this letter agreement'},
            {'unit_id': 25, 'quote': 'in the files of its legal counsel'},
            {'unit_id': 46, 'quote': 'make a proposal to the board of directors of COMSYS'},
            {'unit_id': 59, 'quote': 'Except as otherwise provided in paragraph 8 above'}],
        'project_display_names': True,
        'corrections': [
            {'operation': 'source_concept_correction', 'node': 'best_knowledge', 'concept': 'unspecified'},
            {'operation': 'source_concept_correction', 'node': 'not_proceed_event', 'concept': 'unspecified'},
            {'operation': 'source_concept_correction', 'node': 'all_written_copies', 'concept': 'unspecified'},
            {'operation': 'source_concept_correction', 'node': 'initiator', 'concept': 'unspecified'},
            {'operation': 'source_concept_correction', 'node': 'discussion_information', 'concept': 'unspecified'},
            {'operation': 'source_node_text_correction', 'node': 'transaction_use_condition',
                'before_name': 'in connection with the Transaction', 'name': 'other than in connection with the Transaction',
                'quote': 'other than in connection with the Transaction', 'unit_id': 13},
            {'operation': 'source_qualifier_condition', 'node': 'source_public_not_prohibited_disclosure', 'effect': 'public_exception',
                'unit_id': 6, 'quote': 'other than as a result of a disclosure by the receiving Party or its Representatives that is prohibited by this Agreement'},
            {'operation': 'source_qualifier_condition', 'node': 'source_no_known_disclosure_prohibition', 'effect': 'source_exception', 'unit_id': 7,
                'quote': 'is not known to be prohibited from disclosing such information to the receiving Party by a legal, contractual or fiduciary obligation to either Party'},
            {'operation': 'source_qualifier_condition', 'node': 'source_prior_source_no_known_duty', 'effect': 'prior_possession_exception', 'unit_id': 8,
                'quote': 'was not known by the receiving Party, after due inquiry, to be subject to an obligation not to disclose such information'},
            {'operation': 'source_qualifier_condition', 'node': 'source_destroy_alternative', 'effect': 'destroy_obligation',
                'unit_id': 21, 'quote': 'the other party will either'},
            {'operation': 'source_qualifier_condition', 'node': 'source_return_alternative', 'effect': 'return_obligation',
                'unit_id': 21, 'quote': 'the other party will either'},
            {'operation': 'source_qualifier_condition', 'node': 'source_counsel_file_custody', 'effect': 'retention_permission',
                'unit_id': 25, 'quote': 'in the files of its legal counsel'},
            {'operation': 'source_add_node', 'node': {'id': 'source_comsys_board', 'kind': 'group', 'concept': 'unspecified',
                'name': 'board of directors of COMSYS', 'quote': 'board of directors of COMSYS', 'unit_id': 46}},
            {'operation': 'source_relation_correction', 'index': 95,
                'before': {'predicate': 'recipient', 'arguments': ['company_proposal_permission', 'comsys']},
                'after': {'arguments': ['company_proposal_permission', 'source_comsys_board']}},
            {'operation': 'source_known_relation', 'predicate': 'member_of', 'arguments': ['source_comsys_board', 'comsys'],
                'unit_id': 46, 'quote': 'board of directors of COMSYS'},
            {'operation': 'source_scope_limitation', 'text': 'All written copies in a party or its representatives possession are covered by the disposition branches; oral Information has a separate continuing obligation. This is not an unqualified all-information-and-copies scope.'},
            {'operation': 'source_scope_limitation', 'text': 'Disposition actions are alternatives, with not-proceed and at-any-time request cases; the ontology does not fully encode this Boolean trigger/choice structure. A decision not to proceed with the Transaction is not agreement termination.'},
            {'operation': 'source_scope_limitation', 'text': 'Legal-record retention and determining continuing obligations are alternative grounds within counsel-file custody. Custody does not itself grant a disclosure permission to attorneys.'},
            {'operation': 'source_scope_limitation', 'text': 'Mutual notify-each-other pairing, omitted Representative subclasses and detailed standstill objects are not fully represented; no self-notification, complete membership inventory or information recipient is inferred.'},
            {'operation': 'source_inventory_incomplete', 'text': 'The proposal omits expressible prompt decision-notice, written destruction confirmation, non-destruction during pending proceedings, reimbursement and venue duties. Its operative-effect inventory is not complete.'},
            {'operation': 'source_relation_remove', 'index': 89, 'before': {'predicate': 'recipient', 'arguments': ['standstill_prohibition', 'comsys']}},
            {'operation': 'source_relation_remove', 'index': 65, 'before': {'predicate': 'recipient', 'arguments': ['retention_permission', 'attorneys']}}
        ]},
    'ContractNLI:c46f72f5': {
        'graph_sha256': 'eb7a4e758335dff7485fbbafa037241330f4754c9d1c2fa1b8c11c479391536f',
        'units_sha256': '7228f3f14df9bb34d5b5ecf62d42c7a6bd0eec0f24e28344baed63930d7fa029',
        'review': 'All seventy-six supplied units, fifty-seven nodes and ninety-one original relations were checked. The one-way NYNEX information definition, need-to-know/purpose exception, reasonable-care minimum, request-identified return within seven days, stored-data erasure, paragraph3 exceptions and survival/publicity provisions are supported. The two definition paths are alternatives, and the work-produced path also needs the competitive-advantage condition. Mixed copy/use/disclosure actions and internal/external people are not exclusively disclosure/other-third-party types. Reify the clear disclosure component and exception/record-proof conditions. Requested material plus its copies is not necessarily every globally held item; retain the explicit request scope and original all-copies wording without an unqualified all-information tag. A warranty of having bound personnel OR direct individual NDAs is not an unconditional future binding obligation. Survival is not material retention. A service beneficiary is not an employer. Keep execution-date ambiguity, OCR experts, unavailable compensation details and all original limitations; indemnity and acceptance mechanisms remain outside a complete inventory. No task question or native score was read.',
        'evidence': [
            {'unit_id': 9, 'quote': "which would either give NYNEX' competitors an advantage or diminish or eliminate NYNEX' advantage over its competitors"},
            {'unit_id': 12, 'quote': 'except on a "need-to-know" basis to the extent necessary for'},
            {'unit_id': 21, 'quote': 'a written request from NYNEX setting forth the Confidential Information to be returned'},
            {'unit_id': 22, 'quote': 'Upon receipt of such request'},
            {'unit_id': 24, 'quote': "as proven by CONSULTANT's written records; provided, however, that CONSULTANT immediately informs NYNEX, in writing, to establish its prior possession"},
            {'unit_id': 29, 'quote': 'CONSULTANT shall first advise NYNEX of same before making any disclosure to such body'},
            {'unit_id': 33, 'quote': 'or that each and every employee, agent or subcontractor has personally executed a Non-Disclosure Agreement'},
            {'unit_id': 36, 'quote': 'the rights and obligations with respect to the disclosure of Confidential Information set forth herein shall survive'},
            {'unit_id': 61, 'quote': 'Effective July 9th, 1996'}],
        'project_display_names': True,
        'corrections': [
            {'operation': 'source_concept_correction', 'node': 'restricted_actions', 'concept': 'unspecified'},
            {'operation': 'source_concept_correction', 'node': 'internal_or_external_persons', 'concept': 'unspecified'},
            {'operation': 'source_concept_correction', 'node': 'all_information_and_copies', 'concept': 'unspecified'},
            {'operation': 'source_concept_correction', 'node': 'representative_binding_obligation', 'concept': 'unspecified'},
            {'operation': 'source_concept_correction', 'node': 'survive_action', 'concept': 'unspecified'},
            {'operation': 'source_concept_correction', 'node': 'publicity_information', 'concept': 'unspecified'},
            {'operation': 'source_evidence_correction', 'group': 'nodes', 'index': 51, 'unit_id': 37,
                'quote': 'any details connected with such discussions or negotiations'},
            {'operation': 'source_evidence_correction', 'group': 'relations', 'index': 86, 'unit_id': 37,
                'quote': 'any details connected with such discussions or negotiations'},
            {'operation': 'source_evidence_correction', 'group': 'relations', 'index': 19, 'unit_id': 10,
                'quote': 'ALL NYNEX Confidential Information'},
            {'operation': 'source_node_kind_correction', 'node': 'need_to_know_condition', 'before': 'condition', 'after': 'exception', 'concept': 'need_to_know'},
            {'operation': 'source_node_kind_correction', 'node': 'prior_written_permission', 'before': 'condition', 'after': 'exception', 'concept': 'written_consent'},
            {'operation': 'source_node_kind_correction', 'node': 'publicity_consent', 'before': 'condition', 'after': 'exception', 'concept': 'written_consent'},
            {'operation': 'source_add_node', 'node': {'id': 'source_disclosure_component', 'kind': 'event', 'concept': 'disclosure',
                'name': 'disclosed, disseminated or communicated', 'quote': 'disclosed, disseminated or communicated', 'unit_id': 12}},
            {'operation': 'source_known_relation', 'predicate': 'action', 'arguments': ['paragraph2b_prohibition', 'source_disclosure_component'],
                'unit_id': 12, 'quote': 'shall not be copied, used, distributed, disclosed, disseminated or communicated'},
            {'operation': 'source_qualifier_condition', 'node': 'source_competitive_consequence', 'effect': 'produced_information_condition', 'unit_id': 9,
                'quote': "which would either give NYNEX' competitors an advantage or diminish or eliminate NYNEX' advantage over its competitors"},
            {'operation': 'source_add_node', 'node': {'id': 'source_prior_records_notice', 'kind': 'condition', 'concept': 'unspecified',
                'name': "as proven by CONSULTANT's written records", 'unit_id': 24,
                'quote': "as proven by CONSULTANT's written records; provided, however, that CONSULTANT immediately informs NYNEX, in writing, to establish its prior possession"}},
            {'operation': 'source_relation_correction', 'index': 36,
                'before': {'predicate': 'condition', 'arguments': ['prior_possession_exception', 'consultant']},
                'after': {'arguments': ['prior_possession_exception', 'source_prior_records_notice'], 'value': None}},
            {'operation': 'source_add_node', 'node': {'id': 'source_independent_records', 'kind': 'condition', 'concept': 'unspecified',
                'name': "as proven by CONSULTANT's written records", 'quote': "as proven by CONSULTANT's written records", 'unit_id': 27}},
            {'operation': 'source_relation_correction', 'index': 52,
                'before': {'predicate': 'condition', 'arguments': ['independent_development_exception', 'consultant']},
                'after': {'arguments': ['independent_development_exception', 'source_independent_records'], 'value': None}},
            {'operation': 'source_qualifier_condition', 'node': 'source_notice_prerequisite', 'effect': 'legal_requirement_exception', 'unit_id': 29,
                'quote': 'CONSULTANT shall first advise NYNEX of same before making any disclosure to such body'},
            {'operation': 'source_qualifier_condition', 'node': 'source_requested_material_scope', 'effect': 'paragraph2e_return_obligation', 'unit_id': 21,
                'quote': 'setting forth the Confidential Information to be returned'},
            {'operation': 'source_known_relation', 'predicate': 'condition', 'arguments': ['paragraph2e_destroy_obligation', 'source_requested_material_scope'],
                'unit_id': 22, 'quote': 'Upon receipt of such request'},
            {'operation': 'source_relation_correction', 'index': 89,
                'before': {'predicate': 'service_link', 'arguments': ['additional_service', 'additional_field_personnel']},
                'after': {'predicate': 'recipient'}},
            {'operation': 'source_scope_limitation', 'text': 'The marked/disclosed and competitively consequential work-produced definition paths are alternatives. The four allowed purposes are alternatives within the need-to-know exception, not four simultaneous requirements.'},
            {'operation': 'source_scope_limitation', 'text': 'The source warranty allows binding personnel to this agreement OR separate individual NDAs; no unqualified occurrence/future obligation of the first branch is asserted. Safeguarding against disclosure does not make the avoided third party a positive recipient.'},
            {'operation': 'source_scope_limitation', 'text': 'The abridged publicity quote is replaced by its contiguous details phrase and the paragraph2 header anchor is restored to unit10. Standalone publicity-protected material is not automatically the defined Confidential Information class.'},
            {'operation': 'source_inventory_incomplete', 'text': 'The indemnity/defend/hold-harmless covenant, direct-NDA alternative and acceptance/sign-return mechanisms are not fully represented as operative effects; the proposed inventory is not complete.'},
            {'operation': 'source_relation_remove', 'index': 18, 'before': {'predicate': 'recipient', 'arguments': ['paragraph2d_obligation', 'third_party']}}
        ]},
    'ContractNLI:62fda7e9': {
        'graph_sha256': '477d5a7183e454496299a0398709b1ae84a5eadd8cad6abf68c2d00f4cc52e1d',
        'units_sha256': '587b4ea95ed0f1a8eb83fb50d18d99c490f64d65dad1c104235cac8ad3485586',
        'review': 'All eighty-five complete supplied units, sixty nodes and seventy-five original relations were checked. The mutual party placeholders, information exceptions, representative subclasses, coordinated use/retention/disclosure restrictions with scoped exceptions, compelled-disclosure notice/assistance/limitation, reverse-engineering restriction and conditional work-product treatment are source-supported. Owns and/or controls does not establish definite ownership of the software platform: preserve it as unknown. Lenders are not thereby financial advisers, a composite Representative set is not wholly other third parties, survival is not an unconditional permission, and a bilateral executed agreement is not merely unilateral written consent. Keep-confidential is an action, not a prohibition type. Add the explicit law-required-material qualifier to the compelled-disclosure limitation. Later source sections contain expressible but unrepresented execution, non-solicitation, assignment, notice, fee and relief duties/permissions; mark inventory incomplete rather than certify the proposal as complete. All original missing dates, identity/recipient unknowns, lack of a return/destruction duty and limitations remain. No native question, label, or case construction data was used.',
        'evidence': [
            {'unit_id': 4, 'quote': 'Dealer Pay owns and/or controls certain proprietary and confidential intellectual property'},
            {'unit_id': 28, 'quote': 'directors, officers, employees, accountants, attorneys, lenders of funds and agents of a party or its affiliates'},
            {'unit_id': 32, 'quote': 'except as expressly authorized in writing by Originating Party'},
            {'unit_id': 36, 'quote': 'in the reasonable opinion of counsel, is required under applicable law'},
            {'unit_id': 37, 'quote': 'a mutually acceptable, written agreement executed by the parties'},
            {'unit_id': 39, 'quote': 'Receiving Party shall execute any instruments'},
            {'unit_id': 42, 'quote': 'for a period of 36 months after termination of the Business Relationship'},
            {'unit_id': 55, 'quote': 'Each party may assign or transfer this Agreement to a successor business entity'},
            {'unit_id': 65, 'quote': 'each party shall be entitled to seek immediate injunctive and other non-monetary equitable relief'}],
        'project_display_names': True,
        'corrections': [
            {'operation': 'source_relation_status_correction', 'index': 3, 'predicate': 'owner', 'before': 'stated', 'after': 'unknown'},
            {'operation': 'source_concept_correction', 'node': 'n_representatives', 'concept': 'unspecified'},
            {'operation': 'source_concept_correction', 'node': 'n_directors', 'concept': 'unspecified'},
            {'operation': 'source_concept_correction', 'node': 'n_officers', 'concept': 'unspecified'},
            {'operation': 'source_concept_correction', 'node': 'n_lenders', 'concept': 'unspecified'},
            {'operation': 'source_concept_correction', 'node': 'n_survival_condition', 'concept': 'unspecified'},
            {'operation': 'source_concept_correction', 'node': 'n_written_agreement_exception', 'concept': 'unspecified'},
            {'operation': 'source_concept_correction', 'node': 'n_keep_confidential_action', 'concept': 'unspecified'},
            {'operation': 'source_qualifier_condition', 'node': 'source_law_required_material', 'effect': 'n_limit_disclosure_obligation',
                'unit_id': 36, 'quote': 'is required under applicable law'},
            {'operation': 'source_inventory_incomplete', 'text': 'The proposal does not encode expressible duties/permissions in units39 and42–65, including execute-instruments, non-solicitation, fee recovery, assignment, notice mechanics and equitable relief; this is not a complete operative-effect inventory.'},
            {'operation': 'source_scope_limitation', 'text': 'The platform ownership/control disjunction remains unresolved. The representation vocabulary also does not fully encode the definition examples, the legally required subset of material or the structure of reasonable-counsel selection.'}
        ]},
    'ContractNLI:35462327': {
        'graph_sha256': 'a7dce9536345570fff0e822546f4974c74c47a2dd70dc5f13c40d7234ea6e1cc',
        'units_sha256': '509e8253ae2a5f9d79ea33b12aaeeea93f21308d219bfd159977193eab80825f',
        'review': 'All fifty-nine complete supplied units, eighty-five proposed nodes and one-hundred-fourteen original relations were checked. The broad information definition, written-consent restrictions, service-purpose exception, ten-business-day return of all documents/property/copies upon service termination, no retained copies/notes/abstracts and not-destroyed instruction agree with their own clauses. Preserve the explicit incomplete scope and every original limitation. A breach notice is not a return request. Copies/notes/abstracts are not retyped as all original information plus copies. Reify the President/VicePresident substitution as an exception with its own condition, not a person used as an exception. The annual-signing qualifier is retained. Unsupported recipients inferred from signing, speaking on behalf, supporting decisions and advocacy are removed; those action/object details remain literal or explicitly unresolved. The relationship-ending part of the survival clause anchors the service-end link, while distinct agreement-end events remain unrepresented. No native question or label was consulted.',
        'evidence': [
            {'unit_id': 4, 'quote': 'Annually the volunteers'},
            {'unit_id': 25, 'quote': 'without prior written consent from the Certification Council for Professional Dog Trainers'},
            {'unit_id': 29, 'quote': 'upon termination of service with CCPDT, Volunteer shall return within ten (10) business days'},
            {'unit_id': 30, 'quote': 'all information will be returned not destroyed'},
            {'unit_id': 34, 'quote': 'or the Vice President if the Volunteer is the President'},
            {'unit_id': 47, 'quote': 'and remain even after Volunteer’s relationship with the Certification Council for Professional Dog Trainers ends'},
            {'unit_id': 51, 'quote': 'upon notice from CCPDT declaring a breach of this Agreement'}],
        'project_display_names': True,
        'corrections': [
            {'operation': 'source_concept_correction', 'node': 'breach_notice', 'concept': 'unspecified'},
            {'operation': 'source_concept_correction', 'node': 'copies_notes_abstracts', 'concept': 'unspecified'},
            {'operation': 'source_add_node', 'node': {'id': 'source_vp_substitution', 'kind': 'exception', 'concept': 'unspecified',
                'name': 'or the Vice President if the Volunteer is the President', 'quote': 'or the Vice President if the Volunteer is the President', 'unit_id': 34}},
            {'operation': 'source_add_node', 'node': {'id': 'source_volunteer_is_president', 'kind': 'condition', 'concept': 'unspecified',
                'name': 'if the Volunteer is the President', 'quote': 'if the Volunteer is the President', 'unit_id': 34}},
            {'operation': 'source_relation_correction', 'index': 69,
                'before': {'predicate': 'exception_for', 'arguments': ['vice_president', 'discuss_conflict']},
                'after': {'arguments': ['source_vp_substitution', 'discuss_conflict']}},
            {'operation': 'source_known_relation', 'predicate': 'condition',
                'arguments': ['source_vp_substitution', 'source_volunteer_is_president'],
                'unit_id': 34, 'quote': 'or the Vice President if the Volunteer is the President'},
            {'operation': 'source_known_relation', 'predicate': 'recipient',
                'arguments': ['source_vp_substitution', 'vice_president'],
                'unit_id': 34, 'quote': 'or the Vice President if the Volunteer is the President'},
            {'operation': 'source_known_relation', 'predicate': 'member_of',
                'arguments': ['authorized_representatives', 'ccpdt'],
                'unit_id': 7, 'quote': 'or any of its authorized representatives'},
            {'operation': 'source_qualifier_condition', 'node': 'source_annual_signing', 'effect': 'signing_obligation',
                'unit_id': 4, 'quote': 'Annually'},
            {'operation': 'source_evidence_correction', 'group': 'relations', 'index': 99, 'unit_id': 47,
                'quote': 'and remain even after Volunteer’s relationship with the Certification Council for Professional Dog Trainers ends'},
            {'operation': 'source_scope_limitation', 'text': 'Speaking on behalf of CCPDT, supporting its decisions and advocating for its program do not identify CCPDT as an information recipient; the principal/decision/mission roles are not fully represented.'},
            {'operation': 'source_scope_limitation', 'text': 'Signing the agreement does not state a delivery recipient. Agreement expiration/termination/rescission are distinct from the encoded service-end trigger and remain incompletely represented.'},
            {'operation': 'source_scope_limitation', 'text': 'The confidentiality definition contains alternative disclosure/access and alternative discloser paths; separate actor edges do not assert a jointly performed factual disclosure.'},
            {'operation': 'source_relation_remove', 'index': 90, 'before': {'predicate': 'recipient', 'arguments': ['advocacy_obligation', 'ccpdt']}},
            {'operation': 'source_relation_remove', 'index': 85, 'before': {'predicate': 'recipient', 'arguments': ['support_decisions', 'ccpdt']}},
            {'operation': 'source_relation_remove', 'index': 80, 'before': {'predicate': 'recipient', 'arguments': ['no_speaking_for_ccpdt', 'ccpdt']}},
            {'operation': 'source_relation_remove', 'index': 8, 'before': {'predicate': 'recipient', 'arguments': ['signing_obligation', 'ccpdt']}}
        ]},
    'ContractNLI:e671a984': {
        'graph_sha256': '75f9d8e3788fabf64ddb4e9b1e1eb8ad0026a6e05790e61e24b27ab69d2a69e3',
        'units_sha256': '215d88d3c567d50c67e0957002b56e09361bb6adf264d4fbfc67cb200dc0bec4',
        'review': 'All twenty-five supplied units, seventy-five proposed nodes and eighty-six original relations were checked. The ROI channel, contact restriction with accompaniment exception, separate copying restriction with prior but not necessarily written consent, practical confidentiality measures, purpose-limited adviser access, compliance, conditional relief/damages and signing-relative duration are source-supported. Receiving-party is not a type of obtain-information event; remove that tag. Any information is not narrowed to some confidential information. A dollar-denominated damages entitlement is not cash paid. Independent legal advice is an information object sought, not a supplied group of advisers receiving confidential information: change that node kind and the associated relation accordingly. Staff learning information conditions the damages narrative, not the definition of what is confidential, so remove the misplaced information-definition condition. Preserve all original unresolved actors, signing dates, unknown purpose and no payer. Definition disjunctions and possible broad consent scope remain unresolved, not converted into conjunctive prerequisites or a wider disclosure permission. No native question, expected verdict or construction metadata was used.',
        'evidence': [
            {'unit_id': 5, 'quote': 'designated as Confidential Information by Disclosing Party, or from all the relevant circumstances'},
            {'unit_id': 8, 'quote': 'unless I am ACCOMPANIED BY AN ASSOCIATE OF ROI CORPORATION'},
            {'unit_id': 9, 'quote': 'without the prior consent of ROI Corporation'},
            {'unit_id': 10, 'quote': 'those agents and professional advisers to whom disclosure is necessary in pursuit of the Approved Purpose'},
            {'unit_id': 15, 'quote': 'which results in such information becoming known to STAFF and/or Patients will entitle Disclosing Party to liquidated damages'},
            {'unit_id': 16, 'quote': 'I will seek independent legal advice for review prior to issuing my signature'},
            {'unit_id': 17, 'quote': 'valid for 36 months and will expire 3 years from the date it was signed'}],
        'project_display_names': True,
        'corrections': [
            {'operation': 'source_concept_correction', 'node': 'obtain_information_action', 'concept': 'unspecified'},
            {'operation': 'source_concept_correction', 'node': 'any_information', 'concept': 'unspecified'},
            {'operation': 'source_concept_correction', 'node': 'liquidated_damages', 'concept': 'unspecified'},
            {'operation': 'source_node_kind_correction', 'node': 'independent_legal_adviser',
             'before': 'group', 'after': 'information', 'concept': 'unspecified'},
            {'operation': 'source_relation_correction', 'index': 77,
             'before': {'predicate': 'recipient', 'arguments': ['legal_advice_obligation', 'independent_legal_adviser']},
             'after': {'predicate': 'object', 'arguments': ['seek_legal_advice_action', 'independent_legal_adviser']}},
            {'operation': 'source_scope_limitation', 'text': 'The definition has alternative competitive/detrimental and designation/reasonable-assumption branches; the separate condition edges do not encode their full Boolean structure.'},
            {'operation': 'source_scope_limitation', 'text': 'The final prior-consent qualifier is attached to copying; whether it also qualifies writing/marking is not resolved, and no broader exception is inferred.'},
            {'operation': 'source_scope_limitation', 'text': 'Staff knowledge in unit14 belongs to a conditional damage consequence rather than the information definition; the ontology does not fully encode that causal statement.'},
            {'operation': 'source_scope_limitation', 'text': 'Exclusive representation by ROI is stated, but the generic relations do not fully encode the vendor-agent relationship or disclose the blank receiving-party identity.'},
            {'operation': 'source_relation_remove', 'index': 60,
             'before': {'predicate': 'condition', 'arguments': ['specific_confidential_information', 'staff_knowledge_condition']}}
        ]}
}


def main():
    completed = []
    for path in sorted((BASE / 'proposed_references').glob('*/source_checks.json')):
        check = json.loads(path.read_text())
        selected = [review for prefix, review in REVIEWS.items() if check['source'].startswith(prefix)]
        if not selected:
            continue
        if len(selected) != 1 or check['role'] not in ('development', 'calibration'):
            raise ValueError('The manual CNI review cohort changed')
        task = json.loads(path.with_name('task.json').read_text())
        response = json.loads((BASE / 'calls' / digest(check['physical_call_id']) / 'result.json').read_text())
        completed.append(persist_review(path, check, task, response, 'v0', selected[0]))
    if len(completed) != len(REVIEWS):
        raise ValueError('A declared manual CNI source audit was not persisted')
    print(json.dumps({'source_only_views': completed, 'new_model_requests': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()
