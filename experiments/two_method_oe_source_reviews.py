"""Source-only audit of the four fixed OpenExempt calibration views.

No questions, legal answers, construction labels or other-view facts are used.
The complete supplied units and original proposed graphs were read separately.
These are scoped assistant audits, not independent human gold annotations.
"""
import json

from experiments.two_method_source_reviews import BASE, persist_review
from legal_skill_guard.skill_evolution.objects import digest


REVIEWS = {
    'OpenExempt:fe5acb6c': {
        'v0': {
            'graph_sha256': 'a03ee11bd0d75408a54f54301e3141a68fc131b1d1964a6ceea6d4bcf469e609',
            'units_sha256': 'a923b0ae9ffe8596ddddb6c1aaa8bff19ea1753af7674133fc989beac6b26a98',
            'review': 'All three complete supplied units, seven nodes and twelve relations were checked. Both Demir people belong to the Debtors, who filed on the literal ambiguous 1.9.2024 date. The range is expressly their property and valued at 680; the rifle is possessed and valued at 600, with ownership correctly not_stated. Possession is not converted to ownership. Keep the unresolved date ordering, every status and the original inventory scope. Materials, appliance features and firearm subtype have no separate semantic attribute ports and remain an explicit representational limitation. No other native view, statutory exemption or expected answer supplies missing facts.',
            'evidence': [
                {'unit_id': 0, 'quote': 'filed for bankruptcy on 1.9.2024'},
                {'unit_id': 1, 'quote': 'appraised at $680.00 is the property of the Demirs'},
                {'unit_id': 2, 'quote': 'the Debtors possess a Henry Golden Boy .22 LR lever-action rifle with brass receiver with a value of $600.00'}],
            'corrections': [{'operation': 'source_scope_limitation',
                'text': 'The literal asset evidence retains range materials/features and rifle subtype, but these descriptive attributes have no separate semantic ports; the graph does not determine their legal treatment.'}]},
        'v1': {
            'graph_sha256': '7bdc2636b09f78b764ee50023377d482ec518e389fe5e988b3e8ce90662ef206',
            'units_sha256': 'ca9aa632d45a300d454e835562e006cbee522c28623506278bdb313d1eaa88ad',
            'review': 'Both complete supplied units, six nodes and ten relations were checked independently. The petition date is explicitly 9 January 2024. This view states ownership of both assets by the Debtors, unlike the possession wording in the other view; retain this own-view ownership rather than merging the two. The range amount 680 and rifle amount 600 attach to their own literal asset anchors. Broad household/personal-property tags do not establish any exemption class. Descriptive appliance and firearm attributes remain incompletely represented; no legal result is asserted.',
            'evidence': [
                {'unit_id': 0, 'quote': 'filed for bankruptcy on 9 January 2024'},
                {'unit_id': 1, 'quote': 'worth $680.00'},
                {'unit_id': 1, 'quote': 'appraised at $600.00 are both owned by the Debtors'}],
            'corrections': [{'operation': 'source_scope_limitation',
                'text': 'The literal asset evidence retains range materials/features and rifle subtype, but these descriptive attributes have no separate semantic ports; the graph does not determine their legal treatment.'}]}},
    'OpenExempt:de89e35f': {
        'v0': {
            'graph_sha256': '2447f957dd068159146725a8dc6d7d821d1fa3c38288a36b4fbcfa7cbeeca894',
            'units_sha256': 'b7311d5d5ba6682f792f2c31c1681ee67d4a7b29e8d3864e946b2a86f5ecf776',
            'review': 'All three complete units, seven nodes and nine relations were checked. Lina and Gabriel are the Debtors; the unambiguous numeric October14 petition date is source-supported. The prosthetic leg is priced at 12900, but ownership is only claimed: both original owner relations remain unknown. The mixer belongs to the Debtors and is appraised at 225. Do not replace claimed ownership with established ownership, infer a medical exemption, or borrow the other-view wording. Medical approval and detailed asset attributes are in literal evidence but lack distinct semantic ports, retained as an unresolved limitation.',
            'evidence': [
                {'unit_id': 0, 'quote': 'filed for bankruptcy on 10/14/2024'},
                {'unit_id': 1, 'quote': 'medically approved prosthetic leg with carbon fiber pylon and silicone socket liner, priced at $12,900.00, is claimed by Lina and Gabriel'},
                {'unit_id': 2, 'quote': 'belonging to the Debtors has an appraisal value of $225.00'}],
            'corrections': [{'operation': 'source_scope_limitation',
                'text': 'Medical approval, prosthetic function/materials and mixer features remain in literal evidence without separate semantic attributes; no medical-aid category or legal exemption is inferred.'}]},
        'v1': {
            'graph_sha256': '73773a7c6efbb7ddb74c9b19ad48985dcf1fbc3b99f6db05b3a1fcf3aa1f7f7e',
            'units_sha256': 'b8bfe48718c6ecd63b18b1d88fa3fb3c062c453c1fd9510fa6dec23bf71e05df',
            'review': 'All three complete units, eight nodes and ten relations were checked independently. Both debtors, the October14 filing date and the asset-disclosure event agree with their source anchors. Reporting the prosthetic leg in a disclosure does not expressly establish its owner; preserve the missing ownership relation and the original unresolved statement. Its value is 12900. The mixer explicitly belongs to Lina and Gabriel and is valued at 225. Detailed medical/material and mixer attributes remain unrepresented. Neither ownership claims from another view nor statutory eligibility is imported.',
            'evidence': [
                {'unit_id': 0, 'quote': 'filed for bankruptcy on October 14, 2024'},
                {'unit_id': 1, 'quote': 'A disclosure of assets by the Hassans reports a medically approved prosthetic leg'},
                {'unit_id': 1, 'quote': 'with a current value of $12,900.00'},
                {'unit_id': 2, 'quote': 'owned by Lina and Gabriel Hassan has been calculated to be $225.00'}],
            'corrections': [{'operation': 'source_scope_limitation',
                'text': 'Medical approval, prosthetic function/materials and mixer features remain in literal evidence without separate semantic attributes; no medical-aid category or legal exemption is inferred.'}]}}
}


def main():
    completed = []
    for path in sorted((BASE / 'proposed_references').glob('*/source_checks.json')):
        check = json.loads(path.read_text())
        selected = [reviews for prefix, reviews in REVIEWS.items() if check['source'].startswith(prefix)]
        if not selected:
            continue
        if len(selected) != 1 or check['role'] != 'calibration':
            raise ValueError('The source-only review cohort changed')
        task = json.loads(path.with_name('task.json').read_text())
        response = json.loads((BASE / 'calls' / digest(check['physical_call_id']) / 'result.json').read_text())
        for view, review in selected[0].items():
            completed.append(persist_review(path, check, task, response, view, review))
    if len(completed) != 4:
        raise ValueError('Fixed four OpenExempt calibration views were not all audited')
    print(json.dumps({'source_only_reviewed_views': completed, 'new_model_requests': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()
