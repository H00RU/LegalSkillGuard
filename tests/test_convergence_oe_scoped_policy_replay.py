from decimal import Decimal

from experiments.convergence_revision5_oe_native_amount_bound import clip_claims
from experiments.convergence_revision5_oe_scoped_policy_replay import merge


def claim(citation, amount):
    return {'citation': citation, 'claim_value': amount}


def test_merge_keeps_established_and_unbound_assets_out_of_scope():
    original = {'unresolved': ['existing'], 'established': ['existing'], 'other': ['existing']}
    proposal = {'unresolved': ['new'], 'established': [], 'other': [], 'ungrounded': ['new']}
    inventory = {
        'a': {'description': 'unresolved', 'filing_interest_established': None},
        'b': {'description': 'established', 'filing_interest_established': True},
    }
    modes, counts = merge(original, proposal, inventory, {'existing', 'new'}, 'EC', {})
    assert modes['title_scope'] == {**original, 'unresolved': ['new']}
    assert modes['add_only'] == {**original, 'unresolved': ['existing', 'new']}
    assert modes['direct_amount_bound'] == original
    assert counts['excluded_established_title_rows'] == 1
    assert counts['excluded_unbound_proposal_rows'] == 2


def test_merge_skips_proposals_with_citations_outside_the_supplied_scope():
    original = {'unresolved': ['existing']}
    inventory = {'a': {'description': 'unresolved', 'filing_interest_established': None}}
    modes, counts = merge(original, {'unresolved': ['outside']}, inventory, {'existing'}, 'EC', {})
    assert modes['title_scope'] == modes['preserve_existing_amounts'] == modes['add_only'] == original
    assert counts['excluded_out_of_scope_rows'] == 1


def test_direct_amount_bound_preserves_citations_and_other_claims():
    original = {
        'quoted asset': [claim('above', 1800), claim('at', 375), claim('below', 200),
                         claim('outside', 400), claim('duplicate', 400), claim('duplicate', 450)],
        'unbound asset': [claim('above', 1800)],
    }
    guard = {'quoted asset': Decimal('375.00')}, {'above', 'at', 'below', 'duplicate'}
    projected, count = clip_claims(original, guard)
    assert count == 1
    assert projected == {**original, 'quoted asset': [claim('above', 375), *original['quoted asset'][1:]]}
    assert original['quoted asset'][0] == claim('above', 1800)
    assert clip_claims(original, None) == (original, 0)
