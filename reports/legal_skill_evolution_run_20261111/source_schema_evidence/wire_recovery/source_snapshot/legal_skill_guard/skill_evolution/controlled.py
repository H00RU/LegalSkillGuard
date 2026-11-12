"""The 32 already-authorized TRAIN views; public material and grades separated."""
from copy import deepcopy
import json
from pathlib import Path


def add_controlled(records, grading, evidence):
    records, grading = deepcopy(records), deepcopy(grading)
    by_parent = {r['parent_id']: r for r in records}
    by_key = {r['key']: r for r in records}

    def add(source, identity, public, schema, answer):
        if source['split'] != 'train':
            raise ValueError('Controlled diagnostic feedback belongs only to TRAIN')
        source['views'].append({'id': identity, 'public': public, 'answer_schema': schema,
                                'controlled_diagnostic': True})
        grading[source['key']][identity] = {'answer': answer,
            'annotation_kind': 'source_checked_TRAIN_diagnostic_not_official_gold'}

    for annotation in evidence['MAUD']['source_annotations']:
        source = by_parent[annotation['parent_contract']]
        for i, row in enumerate(annotation['truth_table']):
            public = {'source_text': annotation['fulltext_audit']['complete_definition_context'],
                'facts': {'matter': 'non-IP', 'source_specified_person_role_and_membership_satisfied': True,
                    'actual_known': row['actual_known'],
                    'required_inquiry_would_reveal': row['required_inquiry_would_reveal'],
                    'scope': annotation['controlled_scope']},
                'question': 'Under this contract definition, is this matter included in the specified party Knowledge? This is not a question about inquiry compliance or breach.'}
            add(source, 'controlled_knowledge_' + str(i), public, {'type': 'boolean'},
                row['reference_definition_satisfied'])
    source = by_key[evidence['RuleArena']['parent_key']]
    for i, row in enumerate(evidence['RuleArena']['four_views']):
        fee = row['controlled_moderate_oversize_fee']
        public = {'source_text': (
            'Controlled policy version, not a claim about the current airline policy. '
            'For this non-complimentary checked bag on Dallas to Sydney Main Cabin: '
            'dimension sum up to 62 inches has no oversize fee; above 62 and up to 65 inches '
            f'has an oversize fee of ${fee}. Weight up to 50 pounds has no overweight fee; '
            'above 50 and up to 70 pounds has an overweight fee of $100. '
            'When a bag is both oversize and overweight, charge the higher of the two fees.'),
            'facts': {'dimension_sum_inches': row['dimension_sum'], 'weight_pounds': row['weight']},
            'question': 'What is the integer violation surcharge only? Exclude ticket price, base bag fees and allocation among bags.'}
        add(source, 'controlled_surcharge_' + str(i), public, {'type': 'integer', 'minimum': 0},
            row['violation_surcharge'])
    source = next(r for r in records if r['dataset'] == 'SARA_v2_Binary'
                  and grading[r['key']]['native']['original_id'] == evidence['SARA']['parent_original_case'])
    for i, row in enumerate(evidence['SARA']['four_views']):
        add(source, 'controlled_year_' + str(i), {'source_text': source['views'][0]['public']['source_text'],
            'facts': {'tax_year': row['tax_year']}, 'question':
            'Does the special zero-exemption rule in section 151(d)(5) apply in this tax year? Do not ask whether the final exemption could be zero for another reason.'},
            {'type': 'boolean'}, row['s151_d5_zero_rule_applicable'])
    added = [(r['key'], v['id']) for r in records for v in r['views'] if v.get('controlled_diagnostic')]
    if len(added) != 32 or len({k for k, _ in added}) != 8:
        raise ValueError('The fixed controlled layer must contain 32 views of exactly eight TRAIN parents')
    return records, grading
