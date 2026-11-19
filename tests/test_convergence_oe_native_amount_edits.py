from itertools import product
import json

from experiments.convergence_revision5_oe_native_amount_edits import change_wire, direct_cap, evaluate, shared_cap


def test_exact_cap_checks_allow_missing_rows_and_enforce_unchanged_amounts():
    for values in product((None, 0, 1, 2, 3, 4), repeat=3):
        assert shared_cap(values, (2, 3, 2)) == direct_cap(values, (2, 3, 2))
    assert shared_cap((2, 3, 2), (2, 3, 2))
    assert not shared_cap((2, 3, 1), (2, 3, 2))


def test_native_wire_edit_changes_only_literal_source_value():
    before = '45 U.S.C. § 9\nA chair worth $33.00.'
    after = before.replace('$33.00', '$34.00')
    user = json.dumps({'other': 'retained §', 'source': before}, ensure_ascii=False)
    wire = {'messages': [{'role': 'system', 'content': 'system'},
                         {'role': 'user', 'content': user}]}
    updated = change_wire(wire, before, after)
    assert updated[0] == wire['messages'][0]
    assert updated[1]['content'] == user.replace('$33.00', '$34.00')
    assert wire['messages'][1]['content'] == user


def test_missing_asset_is_unknown_and_an_explicit_empty_row_is_zero():
    inventory = {'a': {'description': 'desk', 'amount_quote': '$20.00'}}
    sequences = [{'desk': [{'citation': 'A', 'claim_value': 20}]}, {'desk': []}, {}]
    result = evaluate(sequences, [inventory] * 3, {'A'})
    assert result['unobserved_asset_rows'] == 1
    assert result['joint_conflicts'] == result['unchanged_asset_conflicts'] == 1
