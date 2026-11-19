import pytest

from experiments.convergence_revision5_airline_allowance import totals


def rule():
    return {'ticket':100,'base':[0,45,150,200],'complimentary_cutoff':70,
            'standard_weight':[[50,0],[53,30],[70,100],[100,200]],'size':[[62,0],[65,30],[115,200]]}


def test_amount_saved_is_after_combining_size_and_weight():
    fees=totals([(70,66),(63,58)],rule())
    assert fees['joint_assignment']==fees['exact_enumeration']==375
    assert fees['source_order']==fees['overweight_only_order']==445


def test_checked_bag_reordering_preserves_minimum_cost():
    first=totals([(70,66),(63,58)],rule())
    second=totals([(63,58),(70,66)],rule())
    assert first['joint_assignment']==second['joint_assignment']
    assert first['source_order']-second['source_order']==70


def test_public_nonaccepted_bucket_is_outside_the_fee_consumer():
    closed={**rule(),'standard_weight':[[50,0],[53,30],[70,100],[100,None]]}
    with pytest.raises(ValueError,match='not accepted'):
        totals([(62,81)],closed)
