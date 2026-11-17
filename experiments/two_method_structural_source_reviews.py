"""Source-only audits of sealed-pilot structural-evaluation proposals.

The reviewer read each full supplied view and every proposed node/relation.
No native answer or prediction enters these corrections. All choice artifacts
must already exist. These audits never enter dictionary development/calibration.
"""
import json
import hashlib
from pathlib import Path

from experiments.two_method_source_reviews import persist_review
from experiments.two_method_structural_cni_reviews import REVIEWS as CNI_REVIEWS
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/two_method_followthrough_20261116'
MAIN_SEAL = BASE / 'pilot_evaluation_v1/3a847ef33221884de63f234bc6e2ce78f1e19f2265cefc58fa4463e079f8a650/selection_freeze.json'

REVIEWS = {
    'SARA_v2_Binary:1ff7d9ea': {'v0': {
        'graph_sha256': '14dc7045b7509853e2e1a1aa74e16ebee8797372e084d6c84b27a70ca76b9259',
        'units_sha256': '2c7a8efb4a7a9f04108f75c7db56a1a1fd57a8ad4d7df0013cea69ba7eacbb0b',
        'review': 'All five supplied units, eight nodes and sixteen original relations were checked. Alice payment and Bob earnings are distinct assertions; payment is not automatically taxable income or cash. Reify the explicitly stated earnings as an income event with Bob as actor, not an ownership claim about an asset. Marriage start, year, separate-return actors and the express denial of deduction entitlement agree with the text. A denial of entitlement is not itself a prohibition on performing a deduction action: keep the generic fact and explicit quotation, without the prohibition tag. Preserve the missing payer and ontology limitations; no statutory consequence or native answer is supplied.',
        'evidence': [{'unit_id': 0, 'quote': 'In 2017, Alice was paid $33200.'},
                     {'unit_id': 1, 'quote': 'Alice and Bob have been married since Feb 3rd, 2017.'},
                     {'unit_id': 2, 'quote': 'Bob earned $10 in 2017.'},
                     {'unit_id': 3, 'quote': 'Alice and Bob file separate returns.'},
                     {'unit_id': 4, 'quote': 'Alice is not entitled to a deduction for Bob under section 151.'}],
        'corrections': [
            {'operation': 'source_node_kind_correction', 'node': 'n_bob_income',
             'before': 'asset', 'after': 'event', 'concept': 'income'},
            {'operation': 'source_relation_correction', 'index': 8,
             'before': {'predicate': 'owner', 'arguments': ['n_bob_income', 'n_bob']},
             'after': {'predicate': 'actor'}},
            {'operation': 'source_concept_correction', 'node': 'n_no_deduction_entitlement', 'concept': 'unspecified'},
            {'operation': 'source_scope_limitation', 'text': 'The source expressly denies deduction entitlement; this generic graph does not encode a prohibition on an act or resolve the statutory eligibility predicate.'}]}},
    'SARA_v2_Binary:ed3f34d3': {'v0': {
        'graph_sha256': '20c4baa9ee20dddd2b415b5ce8448aa026e20f3829db0cb2765f281fcc4a6941',
        'units_sha256': 'a21a02f5287e24490612a88464e7a7760188111d36099d014a061149382fcd03',
        'review': 'Both entire supplied units, seven nodes and nine original relations were checked. Alice pays Bob for domestic service; service dates and payment amount are explicit, while payment date remains not_stated. A person is not an employment event. The separate American-employer description is preserved as literal role information; it neither establishes nationality nor by itself binds Alice to this specific service as employer/recipient. Keep that event-specific employer unknown and recipient unknown rather than infer them from payment. Preserve the unrepresented location and role-definition limitations. No hidden case predicates or legal answer are added.',
        'evidence': [{'unit_id': 0, 'quote': 'Alice has paid $3200 to Bob for domestic service done from Feb 1st, 2017 to Sep 2nd, 2017, in Caracas, Venezuela.'},
                     {'unit_id': 1, 'quote': 'Alice is an American employer.'}],
        'corrections': [
            {'operation': 'source_concept_correction', 'node': 'alice', 'concept': 'unspecified'},
            {'operation': 'source_relation_status_correction', 'index': 5,
             'predicate': 'employer', 'before': 'stated', 'after': 'unknown'},
            {'operation': 'recipient_remains_unknown', 'node': 'service_1', 'unit_id': 0,
             'quote': 'domestic service done'},
            {'operation': 'source_add_node', 'node': {'id': 'source_american_employer_description',
             'kind': 'information', 'concept': 'unspecified', 'name': 'an American employer',
             'quote': 'an American employer', 'unit_id': 1}},
            {'operation': 'source_known_relation', 'predicate': 'category',
             'arguments': ['alice', 'source_american_employer_description'],
             'unit_id': 1, 'quote': 'Alice is an American employer.'},
            {'operation': 'source_unresolved_text_correction', 'index': 1,
             'before': "Alice's American nationality is stated, but nationality is not representable in the declared local ontology.",
             'after': 'American employer is an explicit role description; the source does not separately establish nationality/citizenship or encode the statutory definition of that role.'}]}},
    'OpenExempt:30e5ee8a': {
        'v0': {
            'graph_sha256': '0291c99dc3725252fdb6810103a63c9017b0d47999f2d56029670732d9ddb8f6',
            'units_sha256': 'e523cb9699465a8aafaca790b50bfa2bff3bdf092dc1205d3611897e15299932',
            'review': 'All three Facts units, five nodes and nine relations were checked. Suresh Menon is the expressly named debtor, with the written July3 filing date. The heater and earrings are distinct owned objects with their own amounts and literal descriptions. Other_asset is retained as the coarse available object type, not as a finding about statutory eligibility, personal use, clothing or jewelry exemptions. No debtor group/membership is invented merely to satisfy a native port. This checks supplied facts, not full native legal categories.',
            'evidence': [{'unit_id': 0, 'quote': 'Suresh Menon (hereinafter the Debtor) filed for bankruptcy on 3rd of July 2024.'},
                         {'unit_id': 1, 'quote': 'owned by Suresh Menon, holds a monetary value of $66.00'},
                         {'unit_id': 2, 'quote': "the Debtor's pair of small diamond stud earrings in 14-karat white gold stands at $1,500.00"}],
            'corrections': []},
        'v1': {
            'graph_sha256': '2a0a880ac3cf104bb865859c52225f08c67a19eb95b9aeb9957f3fcf9c9975f7',
            'units_sha256': '92d759576600b4fc9cbdfa40009788982c579ef17be345ccb63cdd838f1090c0',
            'review': 'All three independently supplied Facts units, five nodes and nine relations were checked. The date includes the written weekday, and ownership is expressly confirmed for the heater and earrings. The local Suresh reference identifies the sole named debtor, without importing another view. Asset values and full literal descriptions are correctly bound. Keep coarse other_asset typing and make no new statutory category, group, purpose or exemption claim.',
            'evidence': [{'unit_id': 0, 'quote': 'Wednesday, July 3rd, 2024'},
                         {'unit_id': 1, 'quote': 'Legal documents confirm that Suresh Menon owns a portable space heater'},
                         {'unit_id': 2, 'quote': 'Suresh is the rightful owner of a pair of small diamond stud earrings'}],
            'corrections': []}},
    'MAUD:708dc842': {
        'v0': {
            'graph_sha256': '44681775f25e94db6ae327e1d66019d3b72a17c5ba9290c2ea4b1354c745d7a0',
            'units_sha256': '9f2ddb4dbf0a9c9ceabd214edae3e96c64bea315161005da45a564df3f324f56',
            'review': 'The full unit, all seven nodes and five relations were checked. The definition explicitly requires reasonable inquiry to the direct report and identifies scheduled Persons as knowledge holders. The primary-responsibility qualifier is retained without choosing an unprovided identity. Both original uncertainty statements remain; actual-only wording and no-inquiry are not invented. Display glosses are projected to their existing literal quotes, with no new semantic fact.',
            'evidence': [{'unit_id': 0, 'quote': 'after reasonable inquiry to the direct report of such individual with primary responsibility for the relevant matter'},
                         {'unit_id': 0, 'quote': 'any of the Persons listed in Section 9.1(b) of the Company Disclosure Letter'}],
            'project_display_names': True, 'corrections': []},
        'v1': {
            'graph_sha256': '6dbc1ddb12c15845a0a9ca5d7de20bd24c75e31c6119fb6a607a6951a729bd8e',
            'units_sha256': '20a635d254c0c331eb6c5e8c3c20cbdf68fba912e8dca31e197f9bf0e33ae969',
            'review': 'The entire supplied section, all27 nodes and41 relations were checked. The ordinary-course/preservation efforts covenant, separate REIT duty, four general exceptions, two safe harbors and COVID response carveout are explicit. The REIT text applies only to applicable Subsidiaries, so correct the all-Subsidiary actor to a separately quoted applicable subgroup. The COVID exception reaches this Section4.1(a), with prior consultation only to the extent reasonably practicable. Preserve all original cross-reference, endpoint and date uncertainties, plus the unencoded cause/effort/alternative qualifications. No global negative-covenant COVID exception is inferred from this view.',
            'evidence': [{'unit_id': 0, 'quote': 'use commercially reasonable efforts to conduct its business in the ordinary course in all material respects'},
                         {'unit_id': 0, 'quote': 'shall maintain the status of the Company (and any of its applicable Subsidiaries) as a REIT'},
                         {'unit_id': 0, 'quote': 'this Section 4.1(a) shall not prohibit'},
                         {'unit_id': 0, 'quote': 'consultation with Parent in advance of taking such actions to the extent reasonably practicable'}],
            'project_display_names': True,
            'corrections': [
                {'operation': 'source_add_node', 'node': {'id': 'source_applicable_subsidiaries',
                 'kind': 'group', 'concept': 'unspecified', 'name': 'any of its applicable Subsidiaries',
                 'quote': 'any of its applicable Subsidiaries', 'unit_id': 0}},
                {'operation': 'source_relation_correction', 'index': 5,
                 'before': {'predicate': 'actor', 'arguments': ['v1_n7', 'v1_n2']},
                 'after': {'arguments': ['v1_n7', 'source_applicable_subsidiaries'], 'unit_id': 0,
                  'quote': 'shall maintain the status of the Company (and any of its applicable Subsidiaries) as a REIT'}},
                {'operation': 'source_known_relation', 'predicate': 'member_of',
                 'arguments': ['source_applicable_subsidiaries', 'v1_n1'], 'unit_id': 0,
                 'quote': 'the Company (and any of its applicable Subsidiaries)'},
                {'operation': 'source_scope_limitation', 'text': 'The Company causing Subsidiary conduct is not fully separated from direct duties; commercially reasonable efforts qualify ordinary-course/preservation conduct and do not promise outcomes.'},
                {'operation': 'source_scope_limitation', 'text': 'COVID effects or COVID Measures are alternatives, not a conjunction; advance consultation is qualified by reasonable practicability.'}]},
        'v2': {
            'graph_sha256': 'a16c73f800935d0653dbd6bed65bae8f1c6025e0231ca1dd56dbe7d0cdb455e6',
            'units_sha256': 'c7310ed68a18a884308b142ea2b8ce7766b0c54561b0e4222c1aee52969aa7b6',
            'review': 'The whole supplied header, all13 nodes and13 relations were checked. The colon omits the prohibited acts; retain its unread action, scope_complete=false and every original uncertainty. Date endpoints are alternatives and the four exceptions belong to this negative header. Parent consent and the prohibition on unreasonable withholding are distinct stated provisions. Do not import the COVID text from another view.',
            'evidence': [{'unit_id': 0, 'quote': 'the Company shall not, and shall cause its Subsidiaries not to:'},
                         {'unit_id': 0, 'quote': 'with Parent’s prior written consent (which consent is not to be unreasonably withheld, conditioned or delayed)'}],
            'project_display_names': True,
            'corrections': [{'operation': 'source_scope_limitation', 'text': 'The Company duty to cause Subsidiary nonperformance is not represented as a separate causal obligation.'}]}},
    'MAUD:c38dbc6d': {
        'v0': {
            'graph_sha256': '074ad6720549e6b62e7036ce4b748751151bde99a6fc48952ae29c48ced022f8',
            'units_sha256': 'dd9523e119c20a884d55b58b58af99d2d72cdf013b70a97c08e037e8ac490ed6',
            'audit_revision': 'receipt_scope_r1',
            'supersedes_audit_sha256': 'e83d1769ff13cf07706f94a07e350b306dd5f68b7d12c3ba1bbf3036f9b62ca6',
            'review': 'The full unit, all nine original nodes and eight relations were checked. Known-by wording does not contain the explicit word actual, so remove that unsupported tag. The definition expressly includes specified written-notice contents. Reify Bridge and DCB branches separately to preserve their own scheduled knowledge holders, rather than a cross-product. Attach the receipt qualifier to the expressly modified other-material-notice branch; do not extend it across the regulator-notice alternative. Keep unknown scheduled identities, alternatives and the such-Person referent. This corrects the overly broad first-review attachment, whose bytes remain preserved. No native knowledge-class label is read or asserted.',
            'evidence': [{'unit_id': 0, 'quote': 'shall mean those facts that are known by'},
                         {'unit_id': 0, 'quote': '(i) as to Bridge Bancorp, those Persons set forth in Bridge Bancorp Disclosure Schedule 1.1'},
                         {'unit_id': 0, 'quote': '(ii) as to DCB, those Persons set forth in DCB Disclosure Schedule 1.1'},
                         {'unit_id': 0, 'quote': 'any other material written notice received by such Person'}],
            'project_display_names': True,
            'corrections': [
                {'operation': 'source_concept_correction', 'node': 'v0_n1', 'concept': 'unspecified'},
                {'operation': 'source_add_node', 'node': {'id': 'source_bridge_branch', 'kind': 'condition',
                 'concept': 'unspecified', 'name': '(i) as to Bridge Bancorp, those Persons set forth in Bridge Bancorp Disclosure Schedule 1.1',
                 'quote': '(i) as to Bridge Bancorp, those Persons set forth in Bridge Bancorp Disclosure Schedule 1.1', 'unit_id': 0}},
                {'operation': 'source_add_node', 'node': {'id': 'source_DCB_branch', 'kind': 'condition',
                 'concept': 'unspecified', 'name': '(ii) as to DCB, those Persons set forth in DCB Disclosure Schedule 1.1',
                 'quote': '(ii) as to DCB, those Persons set forth in DCB Disclosure Schedule 1.1', 'unit_id': 0}},
                *[{'operation': 'source_relation_correction', 'index': index,
                   'before': {'arguments': ['v0_n1', target]},
                   'after': {'arguments': [branch, target]}}
                  for index, branch, target in [(1, 'source_bridge_branch', 'v0_n2'),
                      (2, 'source_bridge_branch', 'v0_n3'), (3, 'source_DCB_branch', 'v0_n4'),
                      (4, 'source_DCB_branch', 'v0_n5')]],
                *[{'operation': 'source_known_relation', 'predicate': 'condition',
                   'arguments': ['v0_n1', branch], 'unit_id': 0, 'quote': quote}
                  for branch, quote in [('source_bridge_branch', '(i) as to Bridge Bancorp, those Persons set forth in Bridge Bancorp Disclosure Schedule 1.1'),
                      ('source_DCB_branch', '(ii) as to DCB, those Persons set forth in DCB Disclosure Schedule 1.1')]],
                {'operation': 'source_qualifier_condition', 'effect': 'v0_n8', 'node': 'source_received_notice',
                 'unit_id': 0, 'quote': 'received by such Person'},
                {'operation': 'source_scope_limitation', 'text': 'Regulator notices and other material notices are alternative branches; the receipt qualifier and such-Person referent are not resolved to an unprovided named recipient.'}]},
        'v1': {
            'graph_sha256': 'c3c10819ad906e1c1bf090408cee79dd4c1877017fe107a3c5a651ce2ae289d2',
            'units_sha256': '61c5c37104dd7abdb67fb17fb3d72e642c0e721c5514d9ca88d954976228a554',
            'review': 'All three supplied units, fifteen nodes and sixteen relations were checked. Both parties and their respective Subsidiaries, time window, ordinary-course conduct and three exception alternatives are source-supported. The other party is relational, not interchangeable with the actor itself. The excerpt ends after clause(a) with a comma; mark incomplete inventory instead of assuming the remainder. Preserve Disclosure-Schedule uncertainty and the limited causal/endpoint representation. No exception is imported from another view.',
            'evidence': [{'unit_id': 2, 'quote': 'each of Bridge Bancorp and DCB shall, and shall cause each of its respective Subsidiaries to'},
                         {'unit_id': 2, 'quote': 'as consented to in writing by the other party'},
                         {'unit_id': 2, 'quote': '(a) conduct its business in the ordinary course in all material respects,'}],
            'project_display_names': True,
            'corrections': [
                {'operation': 'source_concept_correction', 'node': 'v1_n13', 'concept': 'unspecified'},
                {'operation': 'source_inventory_incomplete', 'text': 'The supplied section ends with clause(a) and a comma; later conduct obligations and qualifications are not supplied.'},
                {'operation': 'source_scope_limitation', 'text': 'Respective Subsidiary causation, the opposite-party consent pairing and alternative earlier endpoints are not fully represented by the flat aggregate roles.'}]},
        'v2': {
            'graph_sha256': '1f0fa026534c41709e975318ba75b795bc83e0557d557b6cf77cab6ac8bb06cf',
            'units_sha256': '8cf8f6d8721a4056bd6d41077fd275cf0e493947aa2c18c0b40375ba9522de59',
            'review': 'All three supplied units, fifteen nodes and fourteen relations were checked. The header forbids each party acting or permitting respective Subsidiary acts without the stated consent/exception conditions, but the act list is absent. Its permitting target is an object, not an information recipient; mark the underlying action unread and retain scope_complete=false and all original uncertainty. Other-party consent remains a relative opposite-party role. No COVID branch or specific prohibited action is invented.',
            'evidence': [{'unit_id': 2, 'quote': 'neither Bridge Bancorp nor DCB shall, and neither Bridge Bancorp nor DCB shall permit any of their respective Subsidiaries to'},
                         {'unit_id': 2, 'quote': 'without the prior written consent of the other party to this Agreement'}],
            'project_display_names': True,
            'corrections': [
                {'operation': 'source_relation_correction', 'index': 3,
                 'before': {'predicate': 'recipient', 'arguments': ['v2_n1', 'v2_n4']},
                 'after': {'predicate': 'object'}},
                {'operation': 'source_concept_correction', 'node': 'v2_n13', 'concept': 'unspecified'},
                {'operation': 'source_unread_relation', 'node': 'v2_n0', 'predicate': 'action',
                 'unit_id': 2, 'quote': 'shall permit any of their respective Subsidiaries to'},
                {'operation': 'source_scope_limitation', 'text': 'Opposite-party consent, causal non-permission and alternative earlier endpoints are not fully represented by the flat aggregate roles.'}]}},
}
REVIEWS.update(CNI_REVIEWS)


def main():
    seal = json.loads(MAIN_SEAL.read_text())
    if seal['calibration_or_structure_evaluation_grades_used_for_main_selection'] is not False:
        raise ValueError('Main choices must be frozen before opening evaluation reference proposals')
    lock = json.loads((BASE / 'pilot_lock.json').read_text())
    allowed = {row['key'] for row in lock['rows'] if row['role'] == 'structure_evaluation'}
    completed = []
    annotations = BASE / 'annotation_v1'
    for path in sorted((annotations / 'proposed_references').glob('*/source_checks.json')):
        check = json.loads(path.read_text())
        matches = [value for prefix, value in REVIEWS.items() if check['source'].startswith(prefix)]
        if not matches:
            continue
        if len(matches) != 1 or check['source'] not in allowed or check['role'] != 'structure_evaluation':
            raise ValueError('Evaluation audit is not bound to the original held-out TRAIN role')
        task = json.loads(path.with_name('task.json').read_text())
        if task['no_native_answers_or_questions'] is not True:
            raise ValueError('Review only source-only tasks')
        response = json.loads((annotations / 'calls' / digest(check['physical_call_id']) / 'result.json').read_text())
        for view_id, review in matches[0].items():
            completed.append(persist_review(path, check, task, response, view_id, review))
    manifest = {'reviews': completed, 'main_selection_freeze_sha256': hashlib.sha256(MAIN_SEAL.read_bytes()).hexdigest(),
        'source_sha256': {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (Path(__file__), ROOT / 'experiments/two_method_source_reviews.py',
                         ROOT / 'experiments/two_method_structural_cni_reviews.py')},
        'evaluation_reviews_do_not_enter_dictionary_or_calibration': True, 'new_model_requests': 0}
    target = BASE / 'structural_source_audits_v1' / digest(manifest) / 'manifest.json'
    immutable_json(target, manifest)
    print(json.dumps({'audit_manifest': str(target.relative_to(ROOT)),
        'audited_evaluation_views': len(completed),
        'audited_evaluation_mothers': len({row['source'] for row in completed}),
        'dictionary_or_calibration_updates': 0, 'new_model_requests': 0,
        'complete_native_case_gold_or_independent_human_annotation_claimed': False}, ensure_ascii=False))


if __name__ == '__main__':
    main()
