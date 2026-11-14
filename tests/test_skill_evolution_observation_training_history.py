from pathlib import Path

from legal_skill_guard.skill_evolution.observation_training_history import completed_history


def test_actual_rejected_birth_null_revision_reaches_next_teacher():
    root = Path('artifacts/legal_skill_evolution_mixed_component_training_source_review_20261115')
    arms = ('CoverageRecombine', 'FreeGlobalUpdate')
    history = completed_history(root, 2, arms)
    assert len(history) == 1 and history[0]['batch'] == 1
    assert set(history[0]['actual_teacher_proposals']) == set(arms)
    assert history[0]['actual_selected_checkpoint']['libraries']['CoverageRecombine']['candidate'].endswith('/retained')
    failures = [row for result in history[0]['actual_candidate_execution_and_source_reviews'].values()
        for row in result['rows'] if 'births' in row.get('error', '')]
    assert failures and any('None is not of type' in row['error'] for row in failures)
    # A failure in a rejected candidate is present even though its fields/code
    # are absent from the selected retained library.
    assert history[0]['failed_revisions_retained_even_when_old_library_selected']


def test_actual_B5_schema_and_coverage_rejections_reach_later_updates():
    root = Path('artifacts/legal_skill_evolution_mixed_component_training_line_transport_20261115')
    prior = Path('artifacts/legal_skill_evolution_mixed_component_training_source_review_20261115')
    history = completed_history(root, 6, ('CoverageRecombine', 'FreeGlobalUpdate'), prior_folders=[prior])
    failures = history[-1]['actual_proposal_validation_failures']
    assert any('Extra data' in row.get('error', '') for row in failures.values())
    assert any('Exactly one coverage contract' in row.get('proposal_error', '') for row in failures.values())
