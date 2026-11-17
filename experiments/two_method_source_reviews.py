"""Persist root-assistant source reviews of specific immutable graph proposals.

Each entry below was read against its entire supplied view. This is not an
independent human annotation or an automatic semantic certification heuristic.
Unreviewed views remain unreviewed, and partial scopes retain their unknowns.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from legal_skill_guard.paired_interfaces import graph_interface as gi
from legal_skill_guard.paired_interfaces.graph_pairs import consumer_signature, reference_graph
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest
from experiments.two_method_reference_audit import project

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/two_method_followthrough_20261116/annotation_v1'

REVIEWS = {
    'OpenExempt:d7a7ea93': {'views': {
        'v0': {
            'graph_sha256': '065c92b68c72e92def30d94af84ab18961d3ffe4afefcf76771dc2fac942d301',
            'units_sha256': '71bf20172c0518effb0a9db5a10f99f28807cdc80f55645cb77ea4eb2901b3e5',
            'review': 'Both complete supplied Facts units, all six nodes and ten relations were checked. The debtor group, petition date, three distinct assets, ownership and each amount agree with the source. The ceiling qualifier remains in the height value rather than being converted into an unqualified building dimension. The carriage house is explicitly a residence; the blender and bunk bed are household objects. Their unrepresented descriptive attributes remain unresolved. This Facts graph does not assert an exemption regime, personal-use assumption or exemption claim; public statutory/solved context is separate from this source-only annotation.',
            'evidence': [{'unit_id': 0, 'quote': 'Li and Nina Wang (hereinafter the Debtors) filed for bankruptcy on 07-13-2024.'},
                         {'unit_id': 1, 'quote': 'worth $142,200.00'},
                         {'unit_id': 1, 'quote': 'valued at $315.00'},
                         {'unit_id': 1, 'quote': 'with an appraisal value of $750.00'}],
            'corrections': []},
        'v1': {
            'graph_sha256': '7372f6acfe3f373d3c1fa58b7fe44dbe2a0efb35b85e730560212fa9147dc6ab',
            'units_sha256': 'da01a157f5a8b976a74fcf4f5f698ee1680b9fc3c55a1debde812a110e9d6528',
            'review': 'All three complete supplied Facts units, six nodes and ten relations were checked independently of the other native view. The two Wang debtors and filing date are explicit. The house and blender are jointly bound to Li and Nina in unit1; the bunk bed has its own ownership and valuation in unit2. All three amounts agree with their own asset anchors. Keep all descriptive-attribute omissions unresolved. No cross-view facts, exemption regime, statutory eligibility or target claim is added.',
            'evidence': [{'unit_id': 0, 'quote': 'Li and Nina Wang (hereinafter the Debtors) filed for bankruptcy on 7-13-2024.'},
                         {'unit_id': 1, 'quote': 'are both owned by Li and Nina'},
                         {'unit_id': 2, 'quote': 'The twin bunk bed with integrated drawers and ladder, owned by the Debtors, holds a monetary value of $750.00.'}],
            'corrections': []}}},
    'SARA_v2_Binary:3e22604a': {
        'graph_sha256': '51d97abb48e9e4e12de830388ea668474e9ec14fea1cb0598637b8100a31252b',
        'units_sha256': '2060abe7e6b5ce043fc2770184016ba2cfa3997b9d1bd2f906ba025fe454f194',
        'review': 'The entire supplied sentence, all eight nodes and eleven original relations were checked. Alice pays, Bob performs the work, the amount and service dates are explicit, and Bob is Alice father. The employer edge is not_stated, not an affirmative employment assertion. The payment date and the service recipient remain unestablished. The place node is source-supported but the event-location relation cannot be expressed. Preserve partial scope and every unresolved statement; explicitly mark the missing recipient rather than infer it from payer status.',
        'evidence': [{'unit_id': 0, 'quote': 'Alice has paid $3200 to her father Bob for work done from Feb 1st, 2017 to Sep 2nd, 2017, in Baltimore, Maryland, USA.'}],
        'corrections': [{'operation': 'recipient_remains_unknown', 'node': 'n_work',
                         'unit_id': 0, 'quote': 'paid $3200 to her father Bob for work done'}]},
    'SARA_v2_Binary:982d5316': {
        'graph_sha256': '8dfc59a593135bfdd489c145ca625ce86ca5b36f9a2a718df4d1532ab3093c19',
        'units_sha256': '6636387470d7330016482a7654a708807dcd29870a31bcf7d23de1869e9ccebe',
        'review': 'Both entire supplied units, all six nodes and ten original relations were checked. Alice is the payee and service performer; the first hospital is a service location/object, not an inferred employer or service recipient. The psychiatric commitment has its own participant, institution and dates. Do not identify the two hospitals, assign commitment dates to the service, or invent a payment day. All four unresolved statements are retained, with explicit unknown recipient state on the service.',
        'evidence': [{'unit_id': 0, 'quote': 'Alice was paid $200 in 2017 for services performed in a hospital.'},
                     {'unit_id': 1, 'quote': 'Alice was committed to a psychiatric hospital from January 24, 2015 to May 5th, 2019.'}],
        'corrections': [{'operation': 'recipient_remains_unknown', 'node': 'services',
                         'unit_id': 0, 'quote': 'services performed in a hospital'}]},
    'SARA_v2_Binary:30b162a5': {
        'graph_sha256': '1855ff4941b8cd5af9730cdf6388202b01a7b8bedac580c359393c0dedbb6343',
        'units_sha256': '690207a8d608f25518801f3201a20c280fb76ace2721e3e79a6ed86b108dc2ad',
        'review': 'Both entire units, all three nodes and three relations were checked. Payment amount, Alice payee and payment year are explicit. The section151(b) self-deduction is stated in the source but is outside this graph ontology, and remains explicitly unresolved. This is an audited partial representation with an acknowledged missing legal given, not a complete native tax-case reference. No target claim or answer was consulted.',
        'evidence': [{'unit_id': 0, 'quote': 'In 2017, Alice was paid $33200.'},
                     {'unit_id': 1, 'quote': 'She is allowed a deduction of $2000 for herself for the year 2017 under section 151(b).'}],
        'corrections': []},
    'SARA_v2_Binary:ff37f276': {
        'graph_sha256': '77146458898cae2a56ce14bd77d1d6bbc69cb0ad733b32562cb12f1fee57f0f1',
        'units_sha256': 'd643d0f14828d6d78372cc06b759101ade177d938a171757a474b25c94a234e5',
        'review': 'All three entire units, eight nodes and eleven original relations were checked. Payment to Alice, amount/year, Alice and Bob marriage with its start date, and both separate-return actors/year are explicit. A paid amount alone does not establish a separately owned income asset or its tax classification. Change that node to an unspecified monetary-information node and remove its unsupported ownership edge, while retaining the payment object/amount and payee edges. Preserve both original unresolved statements and add the unresolved tax nature of the payment.',
        'evidence': [{'unit_id': 0, 'quote': 'In 2019, Alice was paid $33200.'},
                     {'unit_id': 1, 'quote': 'Alice and Bob have been married since Feb 3rd, 2019.'},
                     {'unit_id': 2, 'quote': 'Alice and Bob file separate returns in 2019.'}],
        'corrections': [{'operation': 'monetary_information_not_income_asset', 'node': 'income_33200',
                         'owner': 'alice'}]},
    'MAUD:6867ee20': {
        'graph_sha256': 'e16733d892c44102b19839c43ebfca02f2ad803ad93175f5a3077c28d27fd145',
        'units_sha256': '96847307483c101252d9b15d803b7c03589deaf6d55dc13c7bfb53f660aa011e',
        'review': 'Both supplied units, all fifteen nodes and fifteen relations were checked. The general Company definition requires reasonable employee inquiry even though it uses actual-knowledge wording. The IP exception concerns specified clearance opinions/searches and conditional non-imputation; it does not excuse all employee inquiry. The constructive-imputation action is inside a prohibition, not an affirmative imputation rule. Keep all three unresolved statements and the scoped exception links. Display glosses are projected to their existing literal quotes only.',
        'evidence': [{'unit_id': 0, 'quote': 'in each case after reasonable inquiry of those employees who would reasonably be expected to have actual knowledge of the matter in question'},
                     {'unit_id': 1, 'quote': 'and if not conducted or obtained, no knowledge of any third Person Patents, Mark or other Intellectual Property that would have been revealed by such opinions or searches will be imputed'}],
        'project_display_names': True, 'corrections': []},
    'MAUD:2ae909b9': {
        'graph_sha256': 'ab03b872f3ac6c3a73ac643aa9ed074b533dd70c54323bf3adeba5aa794a6c2e',
        'units_sha256': '350396ba9554cbc3bddca0f4e282e772017d9b533f4326e89ccfe08b80e3c27e',
        'review': 'The entire supplied definition, all four nodes and four relations were checked. The definition concerns actual knowledge of the relevant party executive officers. It does not state an inquiry requirement. Executive-officer status alone does not establish employee status; remove that semantic tag while retaining the group and party membership relation. Keep the unresolved inquiry statement; no legal label is supplied by this audit.',
        'evidence': [{'unit_id': 0, 'quote': 'the actual knowledge of such party’s executive officers'}],
        'project_display_names': True,
        'corrections': [{'operation': 'source_concept_correction', 'node': 'v0_executive_officers', 'concept': 'unspecified'}]},
    'MAUD:d335026e': {
        'graph_sha256': 'b6d404b15c53b8b42254333fcb9550327a1e03dad19c897f579355031f664b33',
        'units_sha256': 'e89caf4f2cfcaf0779051b0d012181bdcb2bc7762e8b973634f5cf36e87626d3',
        'review': 'The supplied Company-side fragment, all four nodes and three relations were checked. Actual-knowledge wording and scheduled individuals are explicit. The omitted earlier branch remains unread; no inquiry or imputation state is invented. Preserve scope_complete=false and both unresolved statements.',
        'evidence': [{'unit_id': 0, 'quote': '“knowledge” means <omitted> (ii) with respect to the Company, the actual knowledge of the individuals listed on Section 8.16(a) of the Company Disclosure Schedule'}],
        'project_display_names': True, 'corrections': []},
    'MAUD:34dac12b': {
        'graph_sha256': '3b9ba14c52640c12f98264a64be566ab838373813c71938b1f0f3d6cb52988a3',
        'units_sha256': '97903a7772c1e6e82c17fa76524cb1f6880bd7de396bb62b0e2784603ed0d433',
        'review': 'The entire supplied Golden-side fragment, all six nodes and five relations were checked. The actual-knowledge standard, Golden subject and scheduled individuals are source-supported. The final and makes the rest of the definition unavailable; preserve scope_complete=false and both unresolved statements. Do not infer an inquiry obligation or its absence.',
        'evidence': [{'unit_id': 0, 'quote': 'in the case of Golden, the individuals listed in Schedule 1.1 of the Golden Disclosure Letter; and'}],
        'project_display_names': True, 'corrections': []},
    'MAUD:035f3960': {
        'graph_sha256': '22a7f4847add4dbc31ffccc7bbed10b36577233f4a7346c40f84b2a17487f768',
        'units_sha256': 'f9edbebe87d8febb7449eb8bc3d17e27b179926bd4b8f68784fac1871f7c23bf',
        'review': 'All four nodes and three edges are supported by the sole supplied fragment. Actual wording is explicit; inquiry absence is not asserted. The terminal and leaves the definition incomplete. Keep scope_complete=false and all unresolved statements.',
        'evidence': [{'unit_id': 0, 'quote': '“knowledge” means the actual knowledge of'},
                     {'unit_id': 0, 'quote': 'Company Disclosure Letter and'}],
        'corrections': []},
    'MAUD:7041a34a': {
        'graph_sha256': '7d2b3e2eb9bbeae72bef7823e2364baf795111cc8c7388ff745b8c9744354b9a',
        'units_sha256': 'b22913573042181e731e168670b3b500ffe800579ff4f1acf700b8ad9bb9a61c',
        'review': 'All seven nodes and six edges were checked. The actual-wording object and reasonable-inquiry condition both belong to this knowledge definition, with the Company/subsidiaries and scheduled individuals bound as stated. This verifies the supplied Company-side fragment, not every knowledge definition elsewhere in the contract. The public consumer contract resolves object/condition versus standard port spelling without changing a fact.',
        'evidence': [{'unit_id': 0, 'quote': 'actual knowledge, after reasonable inquiry of those individuals with responsibility for the matter in question'},
                     {'unit_id': 0, 'quote': 'with respect to the Company and the Company Subsidiaries'}],
        'corrections': []},
    'SARA_v2_Binary:250fc5e7': {
        'graph_sha256': '6e8c7f24661ae2243290af031b6c1b8a4eef4e10c990a283a619ad211a14436e',
        'units_sha256': 'dfa0a8d18a996bde0805cc794fad24d3ec54f284ad5e9181cecdf6bbf10bf4f9',
        'review': 'Both source units and all ten nodes/thirteen relations were checked. Alice is payee and the service performer; the University is the named service recipient, not an inferred statutory employer. Enrollment and class-attendance dates remain separate from the payment year and unknown service dates. A monetary amount does not identify the remuneration means, so remove the cash tag from the amount node. No exact payment day or service period is supplied.',
        'evidence': [{'unit_id': 0, 'quote': 'Alice was paid $3200 in 2017 for services performed for Johns Hopkins University.'},
                     {'unit_id': 1, 'quote': 'Alice was enrolled at Johns Hopkins University and attending classes from August 29, 2015 to May 30th, 2019.'}],
        'corrections': [{'operation': 'amount_is_not_a_remuneration_means', 'node': 'n5'}]},
    'SARA_v2_Binary:6939feda': {
        'graph_sha256': '1a47fc9b60f9acfdb7f3069613209ff6eaef90e2c1bf6cc8f259fd959ed16865',
        'units_sha256': 'f2acc2b7f6a58739fd63f0e5184492b501ac22ee5a24172830d8757c7eabbc04',
        'review': 'Both units, all ten nodes and eighteen original relations were checked. Payment directions, workers, amounts, explicit consideration links and the two service periods agree with the source. Neither payment date is supplied. Keep statutory employer unestablished. Add an explicit unknown service-recipient state rather than silently identify the payer as recipient; earlier historical assumptions are not reused as truth.',
        'evidence': [{'unit_id': 0, 'quote': 'Alice has paid $3200 to Bob for domestic service done from Feb 1st, 2017 to Sep 2nd, 2017.'},
                     {'unit_id': 1, 'quote': 'Bob has paid $4500 to Alice for work done from Apr 1st, 2017 to Sep 2nd, 2018.'}],
        'corrections': [{'operation': 'recipient_remains_unknown', 'node': 'domestic_service_2017',
                         'unit_id': 0, 'quote': 'paid $3200 to Bob for domestic service done'},
                        {'operation': 'recipient_remains_unknown', 'node': 'work_2017_2018',
                         'unit_id': 1, 'quote': 'paid $4500 to Alice for work done'}]},
}


ADDITIONAL_VIEW_REVIEWS = {
    'MAUD:d335026e': {
        'v1': {
            'graph_sha256': '9948c2f19fe4700000577584a27f771cb5170c8b382bcbadfc50905e3ba34ba4',
            'units_sha256': 'd4f2a3471a01e3421b0b5eb58d713e43e26b07af29fa83e68ba1e50967755a4f',
            'review': 'The entire supplied unit and every original assertion were checked. The Company promise, subsidiary causation, ordinary-course action and preservation action are separate from the notice/consultation and consent constraints. COVID relief requires good faith/reasonableness and the stated material-reliance notice condition. Deemed written consent requires five business days without a response. Add literal condition nodes for the commercial-efforts standard and the preservation duty consistency proviso; these are stated qualifiers, not assumptions. No dates or other-view terms are imported. The duty subtype occurs on its action node; a common consumer-port bridge, not a source-graph relabeling, handles that equivalent spelling.',
            'evidence': [{'unit_id': 0, 'quote': 'Parent shall be deemed to have consented in writing if it provides no response within five (5) business days'},
                         {'unit_id': 0, 'quote': 'to the extent consistent therewith'},
                         {'unit_id': 0, 'quote': 'use commercially reasonable efforts to preserve its assets and business organization intact in all material respects'}],
            'project_display_names': True,
            'corrections': [{'operation': 'source_qualifier_condition', 'node': 'v1_efforts_standard', 'effect': 'v1_covenant',
                             'unit_id': 0, 'quote': 'commercially reasonable efforts'},
                            {'operation': 'source_qualifier_condition', 'node': 'v1_preservation_consistency', 'effect': 'v1_preserve_action',
                             'unit_id': 0, 'quote': 'to the extent consistent therewith'}]},
        'v2': {
            'graph_sha256': '5ea2aa3825b55efb4791a36b37f80cab6009ac77b358763f6da9e54e49ad3eaf',
            'units_sha256': 'cb831bb73858b7b58f18630d3c1df9cd9c0500a692230b74809bc32063f5b7b2',
            'review': 'The entire supplied unit and every original assertion were checked. Preserve each omitted region, the unread action and the explicit inheritance list i/iii/iv/v without borrowing the omitted contents from the other native view. The restricted subsidiary group is expressly only subsidiaries not wholly owned; narrow its anchor to that full source noun phrase. Give the three separately referenced omitted clauses literal anchors and an explicit unread action on the prohibition. Parent consent and its five-business-day deeming rule are stated in this same view. Existing unresolved statements and scope_complete=false remain unchanged.',
            'evidence': [{'unit_id': 0, 'quote': 'clauses (i), (iii), (iv) and (v) of Section 5.1(a)'},
                         {'unit_id': 0, 'quote': 'any of its Subsidiaries that is not wholly owned'},
                         {'unit_id': 0, 'quote': 'no response within five(5) business days'}],
            'project_display_names': True,
            'corrections': [{'operation': 'source_evidence_correction', 'group': 'nodes', 'index': 2, 'unit_id': 0,
                             'quote': 'any of its Subsidiaries that is not wholly owned'},
                            {'operation': 'source_evidence_correction', 'group': 'nodes', 'index': 4, 'unit_id': 0, 'quote': 'clauses (i)'},
                            {'operation': 'source_evidence_correction', 'group': 'nodes', 'index': 6, 'unit_id': 0, 'quote': '(iv)'},
                            {'operation': 'source_evidence_correction', 'group': 'nodes', 'index': 7, 'unit_id': 0, 'quote': '(v)'},
                            {'operation': 'source_unread_relation', 'node': 'v2_negative_covenant', 'predicate': 'action',
                             'unit_id': 0, 'quote': 'shall not, and shall not permit'}]}},
    'MAUD:34dac12b': {
        'v1': {
            'graph_sha256': 'ff55c8b20ae29377942926cabccc123d25989f3dfc46245379cc816a51e72dc6',
            'units_sha256': 'fbaa31a28f27f0956f186c387b1af575a65b4b03d7571fd64e1e3eccde901487',
            'review': 'The entire supplied unit, including the omitted marker, and every original assertion were checked. Commodity-price and COVID relief are the two alternatives of clause iv. Its prior-notice/consultation and good-faith consideration conditions apply to both alternatives, not only COVID: make the trigger tag unspecified and attach those conditions to the commodity alternative as well. Keep the separate emergency relief and prompt-information duty, budget/consent exceptions and the distinct Ordinary Course definition with its COVID-deviation exception. The period ends at Effective Time or termination; no request occurs, so remove that unsupported duration tag. Correct the two-space any-Person anchor literally. Preserve scope_complete=false and both unresolved statements.',
            'evidence': [{'unit_id': 0, 'quote': 'any commercially reasonable actions (A)in response to change or developments resulting from material changes in commodity prices or (B)required to comply with COVID-19 Measures'},
                         {'unit_id': 0, 'quote': 'prior to taking any actions in reliance on this clause (iv)'},
                         {'unit_id': 0, 'quote': 'any  Person'},
                         {'unit_id': 0, 'quote': 'until the earlier of the Effective Time and the termination of this Agreement'}],
            'project_display_names': True,
            'corrections': [{'operation': 'source_concept_correction', 'node': 'v1_duration', 'concept': 'unspecified'},
                            {'operation': 'source_concept_correction', 'node': 'v1_covid_reliance_trigger', 'concept': 'unspecified'},
                            {'operation': 'source_evidence_correction', 'group': 'nodes', 'index': 31, 'unit_id': 0, 'quote': 'any  Person'},
                            {'operation': 'source_known_relation', 'predicate': 'condition',
                             'arguments': ['v1_commodity_exception', 'v1_notice_obligation'], 'unit_id': 0,
                             'quote': 'prior to taking any actions in reliance on this clause (iv)'},
                            {'operation': 'source_known_relation', 'predicate': 'condition',
                             'arguments': ['v1_commodity_exception', 'v1_consider_views_obligation'], 'unit_id': 0,
                             'quote': 'prior to taking any actions in reliance on this clause (iv)'}]},
        'v2': {
            'graph_sha256': 'ac24f1c5e2055df3801d155788ffb1bd7f94f8a345ae5cae06549ae1382e4ac5',
            'units_sha256': 'fefadf54102facdc2c9f0200f9eb6aacf0cd820e12468cee6de2e5ebf7095e0d',
            'review': 'The entire supplied preamble and every original assertion were checked. The Golden and subsidiary-permission prohibitions inherit the four stated exceptions. The earlier-of period contains Effective Time and termination only; remove the unsupported request semantic tag. Preserve the missing-action-list limitation, add explicit unread direct-action and permitted-object states, and keep scope_complete=false plus both unresolved statements. Do not import the different ordinary-course-view COVID relief into this view.',
            'evidence': [{'unit_id': 0, 'quote': 'until the earlier of the Effective Time and the termination of this Agreement'},
                         {'unit_id': 0, 'quote': 'Golden shall not, and shall not permit its Subsidiaries to:'}],
            'project_display_names': True,
            'corrections': [{'operation': 'source_concept_correction', 'node': 'v2_duration', 'concept': 'unspecified'},
                            {'operation': 'source_unread_relation', 'node': 'v2_golden_prohibition', 'predicate': 'action',
                             'unit_id': 0, 'quote': 'Golden shall not'},
                            {'operation': 'source_unread_relation', 'node': 'v2_permit_action', 'predicate': 'object',
                             'unit_id': 0, 'quote': 'shall not permit its Subsidiaries to'}]}},
    'MAUD:6867ee20': {
        'v1': {
            'graph_sha256': '2527673aba85b1db351e9582cd461b8bf5562dbd98f06fa3ab95ef90093ecb9c',
            'units_sha256': 'c0af7178a9763a3a47283c0d70346321b19ba3bb67810fe85523a3a49b2355cb',
            'review': 'All four supplied units and every node/relation were checked. The ordinary-course definition is separate from the operative duties. Company Parties must maintain existence and conduct business, and cause their subsidiaries to do so, subject to the stated effort standards. All five exceptions apply to those duties; the COVID response condition and good-faith standard remain attached to their own exception. Approval is by Parent I, not a different parent. The earlier-of endpoints and referenced restrictions remain explicit; keep all three unresolved limitations and do not infer missing calendar dates or disclosure-letter contents.',
            'evidence': [{'unit_id': 1, 'quote': 'ordinary course of business, consistent with past practices'},
                         {'unit_id': 3, 'quote': '(d) for any actions taken reasonably and in good faith to respond to COVID-19 or any COVID-19 Measures'},
                         {'unit_id': 3, 'quote': 'each of the Company Parties will, and will cause each of its Subsidiaries to'}],
            'project_display_names': True, 'corrections': []},
        'v2': {
            'graph_sha256': '55a4d3c8a47f6410fa013cd385a0cd63c22d399b299036ccbc4175a1e7a0330e',
            'units_sha256': '85d1e3925f52d23a3c6b123a251d465176dd8893c4b9748b55cb2820c833d251',
            'review': 'Both supplied units and every node/relation were checked. Direct and subsidiary-permission prohibitions are separate, with the same schedule/Parent I approval/agreement exceptions and earlier-of period. The terminal colon supplies no prohibited-action list: keep both unread action/object states, scope_complete=false and all four unresolved limitations. Do not transfer the COVID exception from this source other native view into this preamble.',
            'evidence': [{'unit_id': 1, 'quote': 'the Company Parties will not, and will not permit any of its Subsidiaries, to:'},
                         {'unit_id': 1, 'quote': '(ii) as approved by Parent I'}],
            'project_display_names': True, 'corrections': []}},
    'MAUD:2ae909b9': {
        'v1': {
            'graph_sha256': 'd1f640505d25da6e935e2175926c79a2fd14298fa368c348810a5bebcf673373',
            'units_sha256': '3ffc25aeef249716de91b37edb6bf39194cf01d8bac215ed4ab4db4160b33e75',
            'review': 'Both supplied units and every original node/relation were checked. East expressly includes East Subsidiaries for this section; the ordinary-course duty, Pre-Closing Period and five stated exceptions agree with the source. Central gives the prior written consent. Add source-literal condition nodes for taken-as-a-whole and in-all-material-respects so these stated qualifiers are not silently omitted. Scope remains the supplied local preamble only, not a claim that all referenced disclosure schedules or budget contents were read. No pandemic exception from another view is introduced.',
            'evidence': [{'unit_id': 1, 'quote': 'East (which for purposes of this Section 4.1 shall include the East Subsidiaries)'},
                         {'unit_id': 1, 'quote': 'taken as a whole, in all material respects in the ordinary course consistent with past practice'}],
            'project_display_names': True,
            'corrections': [{'operation': 'source_qualifier_condition', 'node': 'v1_joint_scope', 'effect': 'v1_covenant',
                             'unit_id': 1, 'quote': 'taken as a whole'},
                            {'operation': 'source_qualifier_condition', 'node': 'v1_materiality', 'effect': 'v1_covenant',
                             'unit_id': 1, 'quote': 'in all material respects'}]},
        'v2': {
            'graph_sha256': '38fa322484b192ddee289227c2fd63f77f0816890ac5cf980072288f64142a28',
            'units_sha256': '4e90ac32916f02472db196b30d057748263fbd74d41b9f38a5298b3e28fc9eb0',
            'review': 'The full supplied unit and every original node/relation were checked. The East/subsidiary prohibitions, inherited exceptions and Central consent are stated; the section-number mismatch is genuinely present and remains unresolved. Executive-officer status does not alone establish employee status, so remove that tag. The terminal colon leaves prohibited actions unread: add explicit unread direct-action and subsidiary-permitted-object relations, retain scope_complete=false and both existing unresolved statements, and infer no missing list contents.',
            'evidence': [{'unit_id': 0, 'quote': 'for purposes solely of this Section 4.2(b)'},
                         {'unit_id': 0, 'quote': 'an executive officer of Central'},
                         {'unit_id': 0, 'quote': 'East shall not and shall not permit any of the East Subsidiaries'}],
            'project_display_names': True,
            'corrections': [{'operation': 'source_concept_correction', 'node': 'v2_central_executive_officer', 'concept': 'unspecified'},
                            {'operation': 'source_unread_relation', 'node': 'v2_direct_prohibition', 'predicate': 'action',
                             'unit_id': 0, 'quote': 'East shall not'},
                            {'operation': 'source_unread_relation', 'node': 'v2_permit_action', 'predicate': 'object',
                             'unit_id': 0, 'quote': 'shall not permit any of the East Subsidiaries'}]}},
    'MAUD:7041a34a': {
        'v1': {
            'graph_sha256': 'bd9fd2231496c9102325e94a39deced72acec3f82d7473d278f8eadf2e54cadc',
            'units_sha256': 'fc3561208d7843334aa08bc9bcc8227626108665c4dcdaa519ffdd1cb0228106',
            'review': 'Both full supplied units, eighteen nodes and twenty-four relations were checked. The Company obligation and causative subsidiary obligation, earlier-of endpoints, schedule/agreement/law/consent exceptions, and COVID deeming provision are source-supported. The COVID measure is represented as a deeming effect and standard, not relabeled as a different exception to fit the consumer. The Parent anchor belongs to unit1. The agreement-permission exception crosses the unit boundary; use its literal unit0 introducer as the anchor and retain the unit1 continuation in this review evidence. Preserve the original causation limitation and every status; this is not a complete native-case gold assertion.',
            'evidence': [{'unit_id': 0, 'quote': '(x) expressly permitted by any other'},
                         {'unit_id': 1, 'quote': 'provision of this Agreement or as required by Law'},
                         {'unit_id': 1, 'quote': 'unless Parent shall otherwise consent in writing'},
                         {'unit_id': 1, 'quote': 'with any COVID-19 Measures being deemed to be in the ordinary course of business consistent with past practice'}],
            'project_display_names': True,
            'corrections': [
                {'operation': 'source_evidence_correction', 'group': 'nodes', 'index': 2, 'unit_id': 1, 'quote': 'Parent'},
                {'operation': 'source_evidence_correction', 'group': 'nodes', 'index': 12, 'unit_id': 0, 'quote': '(x) expressly permitted by any other'},
                {'operation': 'source_evidence_correction', 'group': 'relations', 'index': 14, 'unit_id': 0, 'quote': '(x) expressly permitted by any other'},
                {'operation': 'source_evidence_correction', 'group': 'relations', 'index': 15, 'unit_id': 0, 'quote': '(x) expressly permitted by any other'}]},
        'v2': {
            'graph_sha256': 'afdbe683f841f5510311544f6cdf5926b289b1ef8e91a024ea98fed14505049d',
            'units_sha256': '8cd8c8a5664b39d1b037af6113e39e2108a6404fcfe8dccf9532323c30216e01',
            'review': 'The entire supplied unit, fourteen nodes and twenty relations were checked. The Company and subsidiary prohibitions, inherited exceptions, consent scope and earlier-of timing are explicit. The action node is only the quoted placeholder any of the following, with category unread; no missing prohibited action is invented. Preserve scope_complete=false, the unread edge and both unresolved limitations. This supplied preamble does not establish an omitted pandemic exception or its absence.',
            'evidence': [{'unit_id': 0, 'quote': 'the Company shall not, and shall cause each Company Subsidiary not to'},
                         {'unit_id': 0, 'quote': 'do, or agree to do, any of the following without the prior written consent of Parent'}],
            'project_display_names': True, 'corrections': []}},
    'MAUD:035f3960': {
        'v1': {
            'graph_sha256': '26571d7316daf368043fa5f1b91fc4e7178e24dfdb240a8e71c73871f4389e51',
            'units_sha256': '0ffd51ad5725288d32ede1d89c05c1c1146bfc074be2ae16df3ff5437d8d325d',
            'review': 'The entire supplied unit including the explicit omitted marker, all thirty nodes and twenty-nine relations were checked. The Company/subsidiary ordinary-course duty, best-efforts qualifier, COVID response exception with notice/consultation conditions, separate consent exception and COVID deviations in the Ordinary Course definition are source-supported. Preserve the omission, unknown endpoint occurrence and ambiguous reasonably-practicable attachment. The agreement exception combines permissions and requirements, so do not assign the combined condition a permission-only semantic tag. Keep its literal disjunctive wording and record that remaining representational limitation.',
            'evidence': [{'unit_id': 0, 'quote': '(iv) for any actions required to comply with COVID-19 Measures or otherwise taken (or not taken)'},
                         {'unit_id': 0, 'quote': 'provide advance notice to and consult with Parent (if reasonably practicable)'},
                         {'unit_id': 0, 'quote': 'excluding any commercially reasonable deviations therefrom due to COVID-19 or COVID-19 Measures'}],
            'project_display_names': True,
            'corrections': [{'operation': 'source_concept_correction', 'node': 'v1_n11', 'concept': 'unspecified'},
                            {'operation': 'source_scope_limitation', 'text': 'The agreement exception combines permission and requirement alternatives; the graph does not separately represent their modalities.'}]},
        'v2': {
            'graph_sha256': '4fbd8ad2654ccf5191a18f67de12178f922d0409b034893ffd1ab245fd3419b8',
            'units_sha256': 'efe14bdb6a4f1bb4a52d9e61ec2b28098acc3d2dbd5e72b321c51184ae4fe8b3',
            'review': 'The entire supplied unit, twelve nodes and ten relations were checked. The negative-interim preamble, Company/subsidiary scope, exceptions, written consent and earlier-of endpoints are explicit. No prohibited-action list follows the colon in this supplied view; preserve scope_complete=false and both unresolved statements. The agreement exception includes either permission or requirement, so replace the permission-only tag with unspecified while retaining both words and the representational limitation.',
            'evidence': [{'unit_id': 0, 'quote': '(ii) as expressly permitted or required by this Agreement'},
                         {'unit_id': 0, 'quote': 'the Company shall not, and shall not permit its Subsidiaries to:'}],
            'project_display_names': True,
            'corrections': [{'operation': 'source_concept_correction', 'node': 'v2_n9', 'concept': 'unspecified'},
                            {'operation': 'source_scope_limitation', 'text': 'The agreement exception combines permission and requirement alternatives; the graph does not separately represent their modalities.'}]}}
}


def apply_review(graph, review):
    result = deepcopy(graph)
    for change in review['corrections']:
        if change['operation'] == 'amount_is_not_a_remuneration_means':
            node = next(n for n in result['nodes'] if n['id'] == change['node'])
            node.update(kind='information', concept='unspecified')
            result['unresolved'].append('The denomination states an amount, not the remuneration means.')
        elif change['operation'] == 'recipient_remains_unknown':
            result['relations'].append({'predicate': 'recipient', 'arguments': [change['node']],
                'value': None, 'status': 'unknown', 'unit_id': change['unit_id'], 'quote': change['quote']})
        elif change['operation'] == 'source_concept_correction':
            next(n for n in result['nodes'] if n['id'] == change['node'])['concept'] = change['concept']
        elif change['operation'] == 'monetary_information_not_income_asset':
            node = next(n for n in result['nodes'] if n['id'] == change['node'])
            node.update(kind='information', concept='unspecified')
            removed = [e for e in result['relations'] if e['predicate'] == 'owner'
                       and e['arguments'] == [change['node'], change['owner']]]
            if len(removed) != 1:
                raise ValueError('The specifically reviewed ownership edge changed')
            result['relations'].remove(removed[0])
            result['unresolved'].append('The source states payment but does not establish its tax classification as income.')
        elif change['operation'] == 'source_evidence_correction':
            result[change['group']][change['index']].update(unit_id=change['unit_id'], quote=change['quote'])
        elif change['operation'] == 'source_relation_status_correction':
            edge = result['relations'][change['index']]
            if (edge['predicate'] != change['predicate'] or edge['status'] != change['before']
                    or edge['value'] is not None):
                raise ValueError('The specifically reviewed assertion changed')
            edge['status'] = change['after']
        elif change['operation'] == 'source_node_kind_correction':
            node = next(n for n in result['nodes'] if n['id'] == change['node'])
            if node['kind'] != change['before']:
                raise ValueError('The specifically reviewed node kind changed')
            node.update(kind=change['after'], concept=change['concept'])
        elif change['operation'] == 'source_add_node':
            if any(node['id'] == change['node']['id'] for node in result['nodes']):
                raise ValueError('A specifically reviewed new node already exists')
            result['nodes'].append(deepcopy(change['node']))
        elif change['operation'] == 'source_node_text_correction':
            node = next(n for n in result['nodes'] if n['id'] == change['node'])
            if node['name'] != change['before_name']:
                raise ValueError('The specifically reviewed literal name changed')
            node.update(name=change['name'], quote=change['quote'], unit_id=change['unit_id'])
        elif change['operation'] in ('source_relation_correction', 'source_relation_remove'):
            edge = result['relations'][change['index']]
            if any(edge[key] != value for key, value in change['before'].items()):
                raise ValueError('The specifically reviewed relation changed')
            if change['operation'] == 'source_relation_remove':
                result['relations'].pop(change['index'])
            else:
                edge.update(change['after'])
        elif change['operation'] == 'source_scope_limitation':
            result['unresolved'].append(change['text'])
        elif change['operation'] == 'source_unresolved_text_correction':
            if result['unresolved'][change['index']] != change['before']:
                raise ValueError('The specifically reviewed uncertainty statement changed')
            result['unresolved'][change['index']] = change['after']
        elif change['operation'] == 'source_inventory_incomplete':
            result['scope_complete'] = False
            result['unresolved'].append(change['text'])
        elif change['operation'] == 'source_qualifier_condition':
            result['nodes'].append({'id': change['node'], 'kind': 'condition', 'concept': 'unspecified',
                'name': change['quote'], 'quote': change['quote'], 'unit_id': change['unit_id']})
            result['relations'].append({'predicate': 'condition', 'arguments': [change['effect'], change['node']],
                'value': None, 'status': 'stated', 'quote': change['quote'], 'unit_id': change['unit_id']})
        elif change['operation'] == 'source_unread_relation':
            result['relations'].append({'predicate': change['predicate'], 'arguments': [change['node']],
                'value': None, 'status': 'unread', 'quote': change['quote'], 'unit_id': change['unit_id']})
        elif change['operation'] == 'source_known_relation':
            result['relations'].append({'predicate': change['predicate'], 'arguments': change['arguments'],
                'value': None, 'status': 'stated', 'quote': change['quote'], 'unit_id': change['unit_id']})
        else:
            raise ValueError('Unreviewed source correction')
    return result


def persist_review(check_path, check, task, response, view_id, review):
    units = next(v['source_units'] for v in task['task']['views'] if v['view_id'] == view_id)
    graph = next(v['graph'] for v in response['value']['views'] if v['view_id'] == view_id)
    if digest(graph) != review['graph_sha256'] or digest(units) != review['units_sha256']:
        raise ValueError('A reviewed source/graph changed; do not transfer the review to a new proposal')
    by_unit = {u['id']: u for u in units}
    for item in review['evidence']:
        if item['quote'] not in by_unit[item['unit_id']]['text']:
            raise ValueError('Source review evidence not contiguous')
    approved = apply_review(graph, review)
    projection = None
    if review.get('project_display_names'):
        approved, projection = project(approved, units)
    span_checks = gi.validate(approved, units)
    dataset = check['source'].split(':')[0]
    native_views = [name for name, opaque in task['native_view_to_opaque_source_view'].items() if opaque == view_id]
    (world, metadata, transport), identities = reference_graph(approved, by_unit, dataset)
    domain = consumer_signature(world, dataset, native_views)
    artifact = {'source': check['source'], 'role': check['role'], 'view_id': view_id,
        'native_views': native_views, 'source_units_sha256': digest(units),
        'physical_annotation_call_id': check['physical_call_id'], 'original_graph_sha256': digest(graph),
        'review': review, 'graph': approved, 'source_span_checks': span_checks,
        'source_semantic_truth_verified': True, 'reference_ready': True,
        'verification_scope': 'asserted source-local graph and explicit unknowns in this supplied view only',
        'complete_native_case_gold_claimed': False, 'native_answers_used_to_create_or_repair_graph': False,
        'inside_current_pure_native_consumer_domain': bool(domain['handled']),
        'reviewer': 'root assistant source audit; not independent human annotation', 'new_model_calls': 0}
    if projection is not None:
        artifact['literal_anchor_projection'] = projection
    revision = review.get('audit_revision')
    folder = check_path.parent / 'audits' / view_id
    name = 'source_review.json'
    if revision is not None:
        if not isinstance(revision, str) or not revision or any(not (c.isalnum() or c in '_-') for c in revision):
            raise ValueError('An audit revision needs a safe explicit identity')
        previous = folder / name
        previous_hash = hashlib.sha256(previous.read_bytes()).hexdigest()
        if previous_hash != review['supersedes_audit_sha256']:
            raise ValueError('The superseded source audit no longer has its original bytes')
        name = 'source_review.' + revision + '.json'
        artifact.update(audit_revision=revision, supersedes_audit_sha256=previous_hash,
                        previous_source_audit_preserved=True)
    target = folder / name
    immutable_json(target, artifact)
    return {'source': check['source'], 'view': view_id,
            'reference_ready': True, 'consumer_domain': domain['handled'],
            'audit_path': str(target.relative_to(ROOT))}

def main():
    completed = []
    for check_path in sorted((BASE / 'proposed_references').glob('*/source_checks.json')):
        check = json.loads(check_path.read_text())
        selected = [v for prefix, v in REVIEWS.items() if check['source'].startswith(prefix)]
        if not selected:
            continue
        if len(selected) != 1:
            raise ValueError('A source matches more than one manual review identity')
        reviews = dict(selected[0].get('views', {'v0': selected[0]}))
        for prefix, additions in ADDITIONAL_VIEW_REVIEWS.items():
            if check['source'].startswith(prefix):
                if reviews.keys() & additions.keys():
                    raise ValueError('A manual source-view review would be overwritten')
                reviews.update(additions)
        task = json.loads(check_path.with_name('task.json').read_text())
        response = json.loads((BASE / 'calls' / digest(check['physical_call_id']) / 'result.json').read_text())
        for view_id, review in reviews.items():
            completed.append(persist_review(check_path, check, task, response, view_id, review))
    print(json.dumps(completed, ensure_ascii=False))


if __name__ == '__main__':
    main()
