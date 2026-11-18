import jsonschema
import pytest

from legal_skill_guard.openexempt import answer_schema
from legal_skill_guard.paired_interfaces.convergence_ev_inventory import (
    inventory_answer_schema, public_inventory, restore_inventory_answer, with_ev_inventory,
)
from legal_skill_guard.paired_interfaces.convergence_schema_control import ReversibleWire
from legal_skill_guard.skill_evolution.native import answer_wire_schema


def test_public_ev_inventory_round_trips_native_omission_and_empty_claims():
    text = ('11 U.S.C. § 522(d)\nFacts:\nThe debtor filed for bankruptcy. A table worth $500.00 and an antique '
            'lamp appraised at $70.00 are both owned by the debtor. A valuation of $12.00 has been assigned to '
            'the wooden stool owned by the debtor.\n\nOutput contract: Provide the asset claim plan.')
    inventory = public_inventory(text)
    assert [(row['description'], row['amount_quote']) for row in inventory.values()] == [
        ('table', '$500.00'), ('antique lamp', '$70.00'), ('wooden stool', '$12.00'),
    ]
    assert all(row['source_quote'] in text for row in inventory.values())
    view = {'id': 'EV', 'public': {'original_input': text}, 'answer_schema': answer_schema('EV')}
    enriched, = with_ev_inventory({'dataset': 'OpenExempt', 'views': [view]})['views']
    assert enriched['public']['asset_inventory'] == inventory and view['public'] == {'original_input': text}
    old = answer_wire_schema('OpenExempt', view)['properties']['answer']
    schema = inventory_answer_schema(old, inventory)
    claims = [{'citation': '11 U.S.C. § 522(d)', 'claim_value': 70}]
    encoded = {'asset_1': None, 'asset_2': claims, 'asset_3': []}
    jsonschema.validate(encoded, schema)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({'asset_2': claims}, schema)
    proposal = {'field_aliases': [{'original': 'claim_value', 'alias': 'amount'}], 'fields_first': ['claim_value']}
    codec = ReversibleWire(schema, proposal)
    restored = codec.restore(codec.encode(encoded))
    assert restore_inventory_answer(restored, inventory) == {'antique lamp': claims, 'wooden stool': []}


def test_public_ev_inventory_requires_every_dollar_quote_to_match_the_pinned_format():
    incomplete = ('Rules\nFacts:\nThe debtor might intend to spend $70.00. A table appraised at $500.00 is the '
                  'property of the debtor.\nOutput contract: Provide a claim plan.')
    assert public_inventory(incomplete) is None
