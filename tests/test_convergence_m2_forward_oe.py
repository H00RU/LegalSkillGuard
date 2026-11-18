from experiments.convergence_m2_forward_oe import selection_decision


def _observation(*, shared, native_positive=False, complete=True):
    return {'shared_compatible': shared, 'independent_compatible': True, 'single_compatible': False,
            'all_queries_observed': complete, 'native_positive': native_positive}


def test_forward_title_gate_requires_an_actual_coherent_incumbent_and_literal_eligibility():
    candidate = _observation(shared=False, native_positive=True)
    incumbent = _observation(shared=True)
    accepted_literal = 'eligible_train_update'
    contrast = selection_decision(candidate, incumbent, accepted_literal)
    assert contrast['eligible_paired_contrast'] and contrast['isolated_shared_rejection_applied']
    assert contrast['candidate_selected_by']['independent_completions']
    assert not contrast['candidate_selected_by']['shared_explanation']

    both_incompatible = selection_decision(candidate, _observation(shared=False), accepted_literal)
    assert not both_incompatible['isolated_shared_rejection_applied']
    assert both_incompatible['candidate_selected_by']['literal_only']
    assert not both_incompatible['candidate_selected_by']['shared_explanation']

    rejected_literal = selection_decision(candidate, incumbent, 'reject_literal_assertions')
    assert not rejected_literal['isolated_shared_rejection_applied']
    assert not rejected_literal['candidate_selected_by']['independent_completions']


def test_forward_title_gate_treats_partial_projection_as_unmatched():
    candidate = _observation(shared=False, native_positive=True, complete=False)
    controls = selection_decision(candidate, _observation(shared=True), 'eligible_train_update')
    assert controls['candidate_selected_by']['shared_explanation'] is None
    assert not controls['eligible_paired_contrast'] and not controls['isolated_shared_rejection_applied']
