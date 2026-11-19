from itertools import product

from experiments import convergence_revision5_oe_m2_cross_citation as cross


def test_separate_legal_citations_cannot_assign_two_principal_types():
    titles = {'EC': True, 'EV': None}
    pair = {'EC': {cross.APPAREL}, 'EV': {cross.SEWING}}
    assert list(cross.witnesses(pair, titles)) == []
    assert not cross.direct_support(pair, titles)
    for task in cross.TASKS:
        one = {**pair, task: set()}
        assert list(cross.witnesses(one, titles))


def test_direct_support_equals_joint_enumeration_for_all_observation_patterns():
    masks = (set(), {cross.APPAREL}, {cross.SEWING}, set(cross.CITATIONS))
    for ec, ev, title_ec, title_ev in product(masks, masks, (None, False, True), (None, False, True)):
        positives = {'EC': ec, 'EV': ev}
        titles = {'EC': title_ec, 'EV': title_ev}
        assert bool(list(cross.witnesses(positives, titles))) == cross.direct_support(positives, titles)


def test_nonpositive_ev_amount_is_not_a_positive_claim():
    output = {'asset': [{'citation': cross.APPAREL, 'claim_value': 0},
                        {'citation': cross.SEWING, 'claim_value': 100}]}
    assert cross.positive_citations('EV', output, 'asset') == {cross.SEWING}
    assert cross.positive_citations('EV', output, 'missing') == set()
