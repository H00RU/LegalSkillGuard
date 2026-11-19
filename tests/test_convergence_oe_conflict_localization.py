from experiments.convergence_revision5_oe_conflict_localization import evaluate, explain


def test_two_consistent_reads_localize_the_incompatible_variant():
    assert explain((30, 0, 30), (30, 31, 30)) == {
        'state': 'conflict', 'possible_single_outliers': [1]}
    assert explain((30, None, 30), (30, 31, 30))['state'] == 'missing_read'


def test_equal_evidence_for_more_than_one_removal_cannot_refute_the_base():
    assert explain((29, 30, 31), (29, 30, 32))['state'] == 'consistent'
    assert explain((30, 31, 32), (30, 40, 40))['possible_single_outliers'] == [1, 2]
    assert explain((25, 25, 27), (30, 31, 30))['possible_single_outliers'] == [2]
    assert explain((25, 26, 27), (30, 31, 30))['possible_single_outliers'] == []


def test_blanket_removal_drops_a_base_claim_supported_by_the_other_edit():
    inventory = {'asset_1': {'description': 'desk', 'amount_quote': '$30.00'}}
    claim = {'claim_value': 30, 'citation': 'C'}
    reads = [{'desk': [claim]}, {'desk': []}, {'desk': [claim]}]
    predictions, evidence = evaluate(reads, [inventory] * 3, {'C'})
    assert evidence[0]['possible_single_outliers'] == [1]
    assert predictions['drop_only_localized_base_conflicts'] == predictions['local_bounds']
    assert predictions['drop_every_conflict'] == {'desk': []}
