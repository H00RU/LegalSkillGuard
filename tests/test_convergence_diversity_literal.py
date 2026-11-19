import pytest

from legal_skill_guard.paired_interfaces import diversity, diversity_claim_groups
from legal_skill_guard.paired_interfaces import diversity_literal as literal


def source(amount, key='public'):
    text = ('Amy is from Texas. Bob is from Maine. '
            f'Amy sues Bob for negligence for $39,000 and defamation for ${amount}.')
    return diversity.public_source({'index': '0', 'text': text}, key, project_split='train')


@pytest.mark.parametrize(('amount', 'answer'), [('36,000', 'No'), ('37,000', 'Yes')])
def test_literal_layouts_share_boundary_and_source_trace(amount, answer):
    mother = source(amount)
    view, = diversity_claim_groups.Provider().views(mother)
    measured = [literal.measure(mother, view, plan) for plan in view['plans']]
    assert all(row['outputs'] == {'native': answer} for row in measured)
    assert all(row['diagnostics']['parties_are_diverse'] for row in measured)
    assert len({row['source_coordinates_sha256'] for row in measured}) == 1
    assert min(r['coordinate_count'] for r in measured) < max(r['coordinate_count'] for r in measured)


def test_literal_refuses_amount_outside_certified_domain():
    with pytest.raises(ValueError, match='Fractional thousands'):
        literal.coordinates({'entity_context': {'claim_count': 1}},
                            ['Amy sues Bob for negligence for $75,001.'])


def test_selector_uses_complete_prefix_and_excludes_current_source():
    old, new = source('36,000', 'old'), source('37,000', 'new')
    provider = diversity_claim_groups.Provider()
    view, = provider.views(old)
    blank = literal.snapshot(0, None, [], [])
    fixed, _ = literal.choose(old, view, blank, learned=True)
    assert fixed['is_correct_fixed_raw_control']
    rows = [{'source': old['key'], 'template': literal.template(p), 'grounded_native': 1,
             'coordinate_count': literal.measure(old, view, p)['coordinate_count']} for p in view['plans']]
    prefix = literal.snapshot(1, blank, [old['key']], rows)
    plan, selection = literal.choose(old, view, prefix, learned=True)
    assert plan == fixed and selection['paired_TRAIN'] == 0
    new_view, = provider.views(new)
    plan, selection = literal.choose(new, new_view, prefix, learned=True)
    assert not plan['is_correct_fixed_raw_control']
    assert selection['paired_TRAIN'] == 1
    assert selection['chosen_coordinate_total'] < selection['fixed_coordinate_total']
    partial = literal.snapshot(1, blank, [old['key']], rows[:-1])
    plan, selection = literal.choose(new, new_view, partial, learned=True)
    assert plan['is_correct_fixed_raw_control'] and selection['paired_TRAIN'] == 0
