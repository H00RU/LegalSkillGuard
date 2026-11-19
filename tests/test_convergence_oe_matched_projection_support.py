from experiments.convergence_revision5_oe_matched_projection_support import review_pair


QUERIES = [{'requested_component': role, 'independently_verified_source_facts': {'stated_value_dollars': value}}
           for role, value in [('forwarded', 100), ('withheld', 110), ('withheld', 100), ('forwarded', 110)]]
SIGNATURES = [[100, 0, 0, 110], [0, 110, 100, 0]]


def test_compatibility_improves_when_conflicting_answers_are_removed():
    proof = review_pair(QUERIES, SIGNATURES, [0, 0, 0, 0], [None, 0, 0, None])
    support = proof['support']
    assert proof['removed_positions'] == [0, 3]
    assert support['incumbent_as_observed']['shared'] == 0
    assert support['remove_only']['shared'] == support['candidate_as_observed']['shared'] == 1
    assert support['incumbent_on_common'] == support['candidate_on_common']


def test_added_assertion_causes_shared_only_conflict_without_common_change():
    proof = review_pair(QUERIES, SIGNATURES, [None, 0, 0, None], [0, 0, 0, None])
    assert proof['added_positions'] == [0]
    assert proof['different_at_commonly_asserted_positions'] == []
    assert proof['support']['add_only'] == {'known': 3, 'shared': 0, 'independent': True}


def test_no_common_assertion_cannot_provide_a_matched_witness():
    proof = review_pair(QUERIES, SIGNATURES, [100, None, None, None], [None, 110, None, None])
    assert proof['common_positions'] == []
    assert proof['support']['candidate_on_common'] == {'known': 0, 'shared': 2, 'independent': True}
