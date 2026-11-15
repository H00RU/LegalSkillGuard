from copy import deepcopy

import pytest

from legal_skill_guard.skill_evolution.source_frame_revision import merge


def output(*terms, complete=False, unresolved=()):
    return {'statements': [{'term': t, 'support_ids': [i]} for i, t in enumerate(terms)],
            'complete': complete, 'unresolved': list(unresolved)}


def test_unrelated_disposal_and_its_or_exception_are_kept_as_one_old_frame():
    disposal = ['disposal_obligation', ['receiving_party'],
                ['action_alternative', ['return_to', ['confidential_information'], ['disclosing_party']],
                 ['destroy', ['confidential_information']]],
                ['request_by', ['disclosing_party']], ['exception_set', ['authorization_exception', 'quote']]]
    old = output(['permission', 'old-scope'], disposal)
    new = output(['permission', 'new-scope'])
    before = deepcopy((old, new))
    result, receipt = merge(old, new, ['disclosure'])
    assert result['statements'] == [old['statements'][1], new['statements'][0]]
    assert result['statements'][0]['term'] == disposal
    assert (old, new) == before and receipt['whole_frames_preserved']


def test_selected_empty_retention_is_not_replaced_by_old_positive_and_unknown_stays_unknown():
    old = output(['retention_permission', 'old'], unresolved=['unread-date'])
    new = output(['permission', 'new'], complete=True)
    result, _ = merge(old, new, ['retention'])
    assert result['statements'] == []
    assert result['unresolved'] == ['unread-date']
    assert result['complete'] is False


def test_absence_audit_is_chosen_with_its_effect_family():
    old = output(['complete_source_no_disclosure_permission'], ['disposal_obligation', 'old'])
    new = output(['permission', 'new'])
    result, _ = merge(old, new, ['disclosure'])
    assert [r['term'][0] for r in result['statements']] == ['disposal_obligation', 'permission']
    assert merge(old, new, [])[0] == old
    assert merge(old, new, ['disclosure', 'disposal', 'retention'])[0] == new


def test_undeclared_new_effect_is_rejected_instead_of_silently_lost():
    with pytest.raises(ValueError, match='No declared revision family'):
        merge(output(['permission']), output(['invented_effect']), ['disclosure'])
