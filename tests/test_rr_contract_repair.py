from legal_skill_guard.rr.contract_repair import infer_postcomposition


def test_selects_only_a_source_literal_with_universal_reference_equivalence():
    r = infer_postcomposition('x', 'min(10,x)', {'x':'integer'}, 'x >= 0',
                             'The value may not exceed 10; a different threshold is 30.')
    assert r['status'] == 'verified_postcomposition_found'
    assert r['selected']['operator'] == 'min' and r['selected']['source_literal'] == 10
    assert not r['source_truth_or_cross_source_applicability_proved']


def test_does_not_invent_a_missing_constant_or_expand_search_until_success():
    r = infer_postcomposition('x', 'min(10,x)', {'x':'integer'}, 'x >= 0', 'The threshold is 30.')
    assert r['status'] == 'no_verified_patch_in_declared_grammar' and r['selected'] is None


def test_identity_wins_when_no_change_is_needed():
    r = infer_postcomposition('x+x', '2*x', {'x':'integer'}, 'x >= 0', 'At most 10.')
    assert r['selected']['operator'] == 'identity'
