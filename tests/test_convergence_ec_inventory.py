from legal_skill_guard.paired_interfaces import convergence_ec_inventory as ec


def test_classification_binds_only_the_asset_with_its_own_literal_amount(monkeypatch):
    name = 'audiologist prescribed hearing aids'
    alias = f'{name} stands at $1,425.00'
    inventory = {'asset_1': {'description': name, 'source_quote': f'The {alias}.',
                             'amount_quote': '$1,425.00'}}
    monkeypatch.setattr(ec, 'public_inventory', lambda _: inventory)
    view = {'id': 'EC', 'public': {'original_input': 'public'}}
    wrong_amount = f'{name} stands at $1,424.00'
    answer = {alias: ['X', 'Y'], name: ['X', 'Z'], wrong_amount: ['unverified']}
    assert ec.bind_classification(view, answer) == {name: ['X', 'Y', 'Z'], wrong_amount: ['unverified']}
    assert ec.bind_classification({**view, 'id': 'EV'}, answer) is answer
    assert len(answer) == 3


def test_valuation_phrase_must_be_verbatim_and_unique():
    name = 'antique desk'
    row = {'description': name, 'source_quote': 'The antique desk is worth $75.00.',
           'amount_quote': '$75.00'}
    alias = f'{name} is worth $75.00'
    assert ec.asset_key(alias, {'asset_1': row}) == name
    alternate = f'{name} valued at $75.00'
    assert ec.asset_key(alternate, {'asset_1': row}) == alternate
    repeated = {**row, 'source_quote': f'{name} and a second {alias}.'}
    assert ec.asset_key(alias, {'asset_1': repeated}) == alias
