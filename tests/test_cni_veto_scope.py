import pytest

from legal_skill_guard.paired_interfaces import cni_veto_scope as scope


def test_negotiation_fact_veto_does_not_cover_general_relationships():
    origin = ['The parties shall not disclose the fact that negotiations have taken place.']
    bound = scope.bind_veto('nda-10', origin, [0])
    alias = ['The existence of any business negotiations shall be kept confidential.']
    unrelated = ['The recipient must not disclose the fact that a confidential relationship exists.']
    assert scope.chosen_role(bound, alias, selected='incumbent', native_fit='proposal') == 'incumbent'
    assert scope.chosen_role(bound, unrelated, selected='incumbent', native_fit='proposal') == 'proposal'
    with pytest.raises(ValueError, match='training witness'):
        scope.bind_veto('nda-10', origin, [1])


def test_recipient_scope_requires_a_representative_in_the_disclosure_clause():
    reps = ['We will reveal the Information only to agents and representatives who need to know.']
    employees = ['Confidential Information may be disclosed only to employees who need to know.']
    bound = scope.bind_veto('nda-7', reps, [0])
    assert scope.chosen_role(bound, reps, selected='incumbent', native_fit='proposal') == 'incumbent'
    assert scope.chosen_role(bound, employees, selected='incumbent', native_fit='proposal') == 'proposal'


def test_oral_veto_does_not_extend_to_notices():
    original = ['Oral Information will continue to be subject to the terms of this Agreement.']
    unrelated = ['The recipient must give an oral notice of a required disclosure.']
    bound = scope.bind_veto('nda-3', original, [0])
    assert scope.chosen_role(bound, original, selected='incumbent', native_fit='proposal') == 'incumbent'
    assert scope.chosen_role(bound, unrelated, selected='incumbent', native_fit='proposal') == 'proposal'
