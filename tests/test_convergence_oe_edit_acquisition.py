import json

from experiments.convergence_revision5_oe_edit_acquisition import choose, edited_messages
from legal_skill_guard.paired_interfaces.convergence_ev_inventory import public_inventory


def test_same_pool_can_distinguish_source_placement_from_native_disagreement():
    inventory = {'asset_1': {'description': 'desk', 'amount_quote': '$14.00', 'source_quote': 'shared'},
                 'asset_2': {'description': 'lamp', 'amount_quote': '$140.00', 'source_quote': 'shared'}}
    entry = {'citation': 'A', 'claim_value': 14}
    roles = {'incumbent': {'desk': [entry], 'lamp': []},
             'candidate': {'desk': [entry], 'lamp': [entry]}}
    selected, counts = choose(inventory, roles, {'A'}, list(inventory))
    assert selected == {'source_context': 'asset_1', 'native_disagreement': 'asset_2'}
    assert counts['asset_1']['downstream_siblings'] == counts['asset_2']['native_disagreement'] == 1


def test_edit_preserves_wire_order_but_rebuilds_amount_and_shared_quote():
    source = ('Facts\nFacts:\nAda Martin (hereinafter the Debtor) filed for bankruptcy on 1/2/2024.\n'
              'Ada has a desk assessed at $14.00, in addition to a lamp valued at $140.00.\nOutput contract:\n')
    revision = source.replace('$14.00', '$15.00')
    public = {'original_input': source, 'asset_inventory': public_inventory(source)}
    load = {'public': {'native_views': [{'id': 'EV', 'public': public}]}, 'answer_schema': {}}
    payload = {'messages': [{'role': 'system', 'content': 'unchanged'},
                            {'role': 'user', 'content': json.dumps(load, sort_keys=True)}]}
    messages, _ = edited_messages(payload, source, source)
    assert messages == payload['messages']
    messages, changed = edited_messages(payload, source, revision)
    assert messages[0] == payload['messages'][0]
    assert changed['asset_inventory'] == public_inventory(revision)
    assert changed['asset_inventory']['asset_2']['amount_quote'] == '$140.00'
