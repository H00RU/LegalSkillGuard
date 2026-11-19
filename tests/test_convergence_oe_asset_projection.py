from copy import deepcopy

from experiments.convergence_revision5_oe_asset_projection import evaluate
from legal_skill_guard.paired_interfaces.asset_port_decoder_v2 import decode
from tests import test_paired_asset_graph_pairs as fixtures


def case():
    card, raw, plan, units = fixtures.AssetGraphPairTests().fixture()
    record, _ = decode(plan, raw, units)
    inventory = {
        name: {'description': name, 'amount_quote': amount, 'source_quote': units[0]['text']}
        for name, amount in (('desk', '$20.00'), ('bike', '$40.00'))
    }
    return plan, record, deepcopy(card), inventory


def test_keeps_a_determined_sibling_when_an_observed_assertion_is_unsupported():
    plan, record, card, inventory = case()
    cell = card['port_record']['assets'][1]['fields']['asset_is_personal_nonbusiness_property']
    cell.update(value=None, status='unknown')
    result = evaluate(plan, record, card, inventory, 'EV')
    assert not result['audited_whole_handled']
    assert result['asset_keys_unresolved'] == ['bike']
    assert set(result['audited_projection']) == {'desk'}
    assert result['audited_projection']['desk'][0]['claim_value'] == 20


def test_an_unread_asset_is_unresolved_even_when_a_sibling_is_complete():
    plan, record, card, inventory = case()
    record['assets'].pop()
    record['inventory_complete'] = False
    record['unresolved'] = ['bike was unread']
    result = evaluate(plan, record, card, inventory, 'EC')
    assert result['original_unresolved'] == ['bike was unread']
    assert result['asset_keys_unresolved'] == ['bike']
    assert result['audited_whole'] == {}
    assert set(result['audited_projection']) == {'desk'}


def test_complete_deterministic_execution_matches_the_unchanged_program():
    plan, record, card, inventory = case()
    result = evaluate(plan, record, card, inventory, 'EV')
    assert result['audited_whole_handled']
    assert result['audited_whole'] == result['audited_projection']
    assert result['asset_keys_unresolved'] == []


def test_duplicate_asset_keys_leave_the_unambiguous_sibling():
    plan, record, card, inventory = case()
    record['assets'].append(deepcopy(record['assets'][0]))
    result = evaluate(plan, record, card, inventory, 'EC')
    assert result['asset_keys_unresolved'] == ['desk']
    assert set(result['audited_projection']) == {'bike'}
