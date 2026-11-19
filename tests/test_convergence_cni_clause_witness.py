from experiments.convergence_revision5_cni_clause_witness import complete, licenses, purposes


def test_completed_witness_preserves_native_indices_across_numbered_siblings():
    spans = [
        'In respect to the Confidential Information, the Recipient hereby undertakes;',
        '',
        '2.1.1 to hold it in confidence;',
        '',
        '2.1.2 to use it only for the Permitted Purpose.',
    ]
    assert purposes(spans) == {4: (0, 4)}
    revised, minimal = complete({'answer': 'Entailment', 'evidence': [1, 4]}, purposes(spans))
    assert revised == {'answer': 'Entailment', 'evidence': [0, 1, 4]}
    assert minimal == {'answer': 'Entailment', 'evidence': [0, 4]}
    spans[2] = '2.2.1 to hold it in confidence;'
    assert purposes(spans) == {}


def test_license_witness_recovers_negation_and_leaves_an_uncited_clause_unread():
    groups = licenses([
        'Nothing in this Confidentiality',
        'Agreement shall be construed as granting any right to the Confidential Information.',
    ])
    assert groups == {1: (0, 1)}
    abstention = {'answer': 'NotMentioned', 'evidence': []}
    assert complete(abstention, groups) == (abstention, abstention)
    unsupported = {'answer': 'Entailment', 'evidence': [0]}
    assert complete(unsupported, groups) == (unsupported, unsupported)
