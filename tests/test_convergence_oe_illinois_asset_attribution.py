from experiments.convergence_revision5_oe_illinois_asset_attribution import (
    CITATION,
    PERSONAL_USE,
    RULE,
    add_citation,
    attribution,
    normalize,
)


def task(facts, family='EC', clause=RULE):
    return {'id': family, 'public': {'original_input': (
        f'{PERSONAL_USE}\n\nStatutes:\n{CITATION}\n{clause}\n\nSolved Reasoning Steps:\n'
        'The Debtor may claim property exemptions under Illinois statutes.\n\nFacts:\n'
        'Ava Doe (hereinafter the Debtor) filed for bankruptcy on 3.6.2024. '
        f'{facts}\n\nOutput contract: the original claim plan'
    )}}


def test_asset_attribution_does_not_extend_to_neighboring_possession():
    view = task('The known assets of Ava include a lamp worth $85.00 and a brooch appraised at $245.00. '
                'Records show that Ava possesses a bracelet with a value of $200.00.')
    amounts, eligible, unresolved = attribution(view)
    assert eligible == {'brooch': 'assets_attributed_to_filer'}
    assert unresolved == {'bracelet': 'ownership_unresolved'}
    raw = {'lamp': [], 'brooch appraised at $245.00': [], 'bracelet': []}
    old = normalize(raw, amounts)
    assert add_citation(old, eligible) == {'lamp': [], 'brooch': [CITATION], 'bracelet': []}
    assert old['brooch'] == []


def test_source_scope_requires_ec_and_the_bound_statutory_sentence():
    facts = 'Ava owns a brooch worth $245.00.'
    assert attribution(task(facts))[1] == {'brooch': 'explicit_title'}
    assert attribution(task(facts, family='EV'))[1] == {}
    assert attribution(task(facts, clause='A different clause.'))[1] == {}
