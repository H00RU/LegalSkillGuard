from experiments.convergence_m2_amount_judgment import _decode, first_visible_group, validate_update
from legal_skill_guard.paired_interfaces.diversity import public_source
from legal_skill_guard.skill_evolution.objects import digest

import json
import pytest


def test_separate_amount_and_judgment_gates():
    source = public_source({'index': 'joint', 'text': 'Amy is from Texas. Bob is from Maine. Carl is from Utah. '
                            'Amy and Bob both sue Carl for $12,000 and $99,000.'},
                           'diversity_5', project_split='train')
    group = first_visible_group([source])
    pairs = [{'source': source['key'], 'baseline_utility': 0.0, 'patch_utility': 1.0}]

    def evaluate(judgments):
        rows = [{'case': case.source_id, 'case_sha256': digest(case.public), 'physical_call_id': 'fixture-' + str(i),
                 'production_failure': None, 'value': {'stated_amount': amount, 'unstated_amount': None,
                                                       'exceeds_threshold': judgment}}
                for i, (case, amount, judgment) in enumerate(zip(group['cases'], group['ordered_stated_amounts'],
                                                                 judgments, strict=True))]
        return validate_update({'fixture': 'candidate'}, group, rows, pairs, [source['key']])

    assert evaluate([None, None, None])['status'] == 'rejected_missed_entailed_judgment'
    assert evaluate([None, None, True])['status'] == 'eligible_train_update'
    contradictory = evaluate([True, False, True])
    assert contradictory['judgment_gate'] == 'passed'
    assert contradictory['status'] == 'rejected_by_shared_explanation'
    assert contradictory['candidate_selected_by']['independent_completions']
    assert not contradictory['candidate_selected_by']['shared_explanation']


def test_match_the_exact_evidence_clause_and_require_a_visible_amount_read():
    clause = 'Amy and Bob both sue Carl for $80,000 and an unspecified dollar amount.'
    payload = {'stated_amount': 80000, 'unstated_amount': None, 'exceeds_threshold': True, 'quote': clause}

    def parse():
        return _decode({'finish_reason': 'stop', 'content': json.dumps(payload)}, clause)

    assert parse()['stated_amount'] == 80000
    payload['quote'] = 'Another clause.'
    with pytest.raises(ValueError, match='exact marked source clause'):
        parse()
    payload.update(quote=clause, stated_amount=None)
    with pytest.raises(ValueError, match='omitted the visible amount'):
        parse()
