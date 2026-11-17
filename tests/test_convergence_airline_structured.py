import pytest

from experiments.convergence_airline_structured_update import MODES, compose


def test_same_bag_aggregation_detects_lost_coupling():
    reading = {'ticket': 500, 'items': [
        {'bag_id': 1, 'base_fee': 0, 'oversize': 0, 'overweight': 100},
        {'bag_id': 2, 'base_fee': 50, 'oversize': 150, 'overweight': 30},
    ]}
    original = compose(reading, 2)
    assert original == {'add_charges': 830, 'match_bag_max': 800, 'unpaired_marginals': 730}
    reading['items'][0]['overweight'], reading['items'][1]['overweight'] = 30, 100
    edited = compose(reading, 2)
    assert edited == {'add_charges': 830, 'match_bag_max': 730, 'unpaired_marginals': 730}


def test_composition_preserves_unknown_and_rejects_duplicate_items():
    reading = {'ticket': 500, 'items': [
        {'bag_id': 1, 'base_fee': 0, 'oversize': 0, 'overweight': None},
        {'bag_id': 2, 'base_fee': 50, 'oversize': 150, 'overweight': 30},
    ]}
    assert compose(reading, 2) == dict.fromkeys(MODES)
    reading['items'][0]['bag_id'] = 2
    with pytest.raises(ValueError, match='each|every'):
        compose(reading, 2)
