from experiments.convergence_revision5_cni_disclosure_objects import compare_policies, score_witness


def test_nested_scope_requires_the_specific_existence_restriction():
    rule = {'family': 'specific_scoped_override', 'evidence': [55, 58, 60], 'secondary': [30, 49]}
    reading = {'answer': 'Entailment', 'evidence_sentence_ids': [49]}
    assert score_witness(reading, rule) == 'generic_scope_only'
    assert score_witness({'answer': 'Contradiction', 'evidence_sentence_ids': [96]}, rule) == 'label_conflict'
    assert compare_policies(reading, rule)['source_scope_check']['evidence_sentence_ids'] == [55, 58, 60]


def test_membership_requires_the_link_and_ambiguous_scope_is_left_alone():
    reading = {'answer': 'NotMentioned', 'evidence_sentence_ids': []}
    rule = {'family': 'linked_membership', 'evidence': [13, 16, 48]}
    modes = compare_policies(reading, rule)
    assert modes['explicit_object_check'] == reading
    assert modes['source_scope_check']['answer'] == 'Entailment'
    assert modes['source_scope_check']['evidence_sentence_ids'] == [13, 16, 48]
    modes = compare_policies(reading, {'family': 'nature_of_arrangement', 'evidence': []})
    assert all(value == reading for value in modes.values())
