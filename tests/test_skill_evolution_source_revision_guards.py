from legal_skill_guard.skill_evolution.source_revision_guards import fit, mask_for


def test_guards_improve_native_outcomes_without_reintroducing_known_source_error():
    # Only disclosure changes; the other bits have no benefit. The word feature
    # also activates on a new source not named in training.
    texts = ['source with except staff', 'second except staff source', 'unrelated source']
    outcomes = []
    for i in range(3):
        outcomes.append({mask: {'source_valid': not (i == 2 and mask & 1),
                               'native_correct': int(bool(mask & 1) == (i < 2))}
                         for mask in range(8)})
    value = fit([None, 'except staff'], texts, outcomes, timeout_seconds=5)
    assert value['accepted'] and value['native_correct'] == 3 and value['optimization_complete']
    assert value['policy']['guards'] == {'disclosure': ['except staff'], 'disposal': [], 'retention': []}
    assert mask_for(value['policy'], 'new contract except staff') == ['disclosure']
    assert mask_for(value['policy'], 'no matching current clause') == []


def test_no_policy_is_accepted_when_all_actual_outputs_violate_source_checks():
    outcomes = [{mask: {'source_valid': False, 'native_correct': 4} for mask in range(8)}]
    value = fit([None], ['a source'], outcomes, timeout_seconds=5)
    assert not value['accepted'] and not value['satisfiable']
