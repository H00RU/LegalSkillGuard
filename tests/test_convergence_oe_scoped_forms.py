import pytest

from experiments.convergence_revision5_oe_scoped_forms import proof, title_at_anchor, worlds


def test_ownership_requires_a_stated_relationship():
    assert title_at_anchor('Both objects are owned by the Debtors.') is True
    assert title_at_anchor('The Debtors assert ownership of a jacket.') is None
    assert title_at_anchor('The Debtors possess a jacket.') is None
    with pytest.raises(ValueError, match='verified title basis'):
        title_at_anchor('The jacket is listed in a report.')


def test_movable_and_apparel_remain_joint_while_title_is_unresolved():
    assert worlds(None, ('wearing_apparel',)) == ((False, True, True), (True, True, True))
    assert worlds(None, fixed=(None, None, True)) == worlds(None, ('wearing_apparel',))
    assert worlds(True, fixed=(False, None, True)) == ()
    assert worlds(None, ('out_of_scope',)) == ((False, False, False),)
    assert proof()['state_sets_verified'] == 21
