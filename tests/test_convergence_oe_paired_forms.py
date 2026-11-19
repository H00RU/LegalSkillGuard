from itertools import product

import pytest

from experiments import convergence_revision5_oe_paired_forms as paired
from experiments import convergence_revision5_oe_scoped_forms as original


def test_fixed_and_joint_form_mappings_cover_the_same_finite_port_domain():
    for values in product((None, False, True), repeat=2):
        raw = dict(zip(original.PORTS[1:], values, strict=True))
        forms = paired.read_forms(raw, original.FIXED)
        assert set(original.worlds(None, forms)) == set(original.worlds(None, fixed=(None, *values)))
        if forms:
            assert paired.read_forms(list(forms), original.RELATION) == forms


def test_pairing_preserves_ambiguity_when_reads_disagree():
    ordinary = frozenset({'movable_nonapparel'})
    apparel = frozenset({'wearing_apparel'})
    assert paired.merge_forms(ordinary, ordinary | apparel) == ordinary
    assert paired.merge_forms(ordinary, apparel) == ordinary | apparel
    assert paired.merge_forms(frozenset(), ordinary) == ordinary


def test_pairing_refuses_a_separate_fact_about_business_use(monkeypatch):
    quote = 'The Debtor owns a desk with a value of $290.00.'
    inventory = {'asset_1': {'description': 'desk', 'amount_quote': '$290.00', 'source_quote': quote,
                             'filing_interest_established': True}}
    monkeypatch.setattr(paired, 'title_inventory', lambda _: (1, inventory, {quote: {}}))

    def case(date, addition=''):
        text = (f'{paired.PERSONAL}\nStatutes:\nOne pinned clause.\nSolved Reasoning Steps:\n'
                f'Adjacent premise\nFacts:\nAlice Doe (hereinafter the Debtor) filed for bankruptcy on {date}. '
                f'{quote} {addition}\nOutput contract:')
        return {'debtor': 1, 'public': {'source_text': text, 'public_scope': original.REGIME, 'inventory': inventory},
                'native': {'public': {'original_input': text}}}

    assert paired.form_context(case('1.9.2024')) == paired.form_context(case('9 January 2024'))
    with pytest.raises(ValueError, match='separate fact'):
        paired.form_context(case('9 January 2024', 'The desk is used solely for business.'))
