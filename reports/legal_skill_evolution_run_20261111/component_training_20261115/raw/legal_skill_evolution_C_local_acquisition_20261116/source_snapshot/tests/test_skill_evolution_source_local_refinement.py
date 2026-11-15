from copy import deepcopy

import pytest

from legal_skill_guard.skill_evolution.source_local_refinement import concepts, statements
from legal_skill_guard.skill_evolution.source_composition import statement_fingerprint


def fixture():
    previous = {'queries': [{'id': 'old', 'operation': 'source_clause_kind', 'unit_ids': [1]},
                            {'id': 'unrelated', 'operation': 'source_clause_kind', 'unit_ids': [2]}],
        'answers': [{'id': 'old', 'choice': 'source_permission', 'evidence_unit_ids': [1]},
                    {'id': 'unrelated', 'choice': 'source_other', 'evidence_unit_ids': [2]}],
        'fragments': [{'term': ['disclose'], 'support_ids': [1], 'query_ids': ['old', 'neural']},
                      {'term': ['return_to'], 'support_ids': [2], 'query_ids': ['unrelated']}], 'unresolved': []}
    visible = {'queries': [{'id': 'neural', 'operation': 'recipient', 'unit_ids': [1]},
                           {'id': 'audit', 'operation': 'audit', 'unit_ids': [1, 2]}],
               'complete_source_absence_choices': {'audit': ['absent']}}
    delta = {'retire_group_query_ids': ['old'], 'retire_neural_query_ids': ['neural'],
        'queries': [{'id': 'new', 'operation': 'source_clause_kind', 'unit_ids': [1]}],
        'answers': [{'id': 'new', 'choice': 'source_prohibition', 'evidence_unit_ids': [1]}],
        'fragments': [{'term': ['disclose'], 'support_ids': [1], 'query_ids': ['new']}], 'unresolved': []}
    return previous, visible, delta


def test_only_explicit_current_scope_is_replaced_and_original_is_retained():
    old, visible, delta = fixture(); preserved = deepcopy(old)
    value, receipt = concepts(old, delta, visible)
    assert value['fragments'] == [old['fragments'][1], delta['fragments'][0]]
    assert receipt['unchanged_fragment_indices'] == [1]
    assert old == preserved and receipt['original_response_not_overwritten']


def test_shared_neural_evidence_prevents_accidental_change_to_untouched_frame():
    old, visible, delta = fixture(); old['fragments'][1]['query_ids'].append('neural')
    with pytest.raises(ValueError, match='untouched source frame'):
        concepts(old, delta, visible)


def test_deleting_only_or_changing_whole_source_audit_is_rejected():
    old, visible, delta = fixture(); delta['fragments'] = []
    with pytest.raises(ValueError, match='actual new source-concept'):
        concepts(old, delta, visible)
    old, visible, delta = fixture(); delta['retire_neural_query_ids'] = ['audit']
    with pytest.raises(ValueError, match='whole-source absence audit'):
        concepts(old, delta, visible)


def test_new_unread_reason_does_not_keep_ordinary_complete_true():
    old = {'statements': [{'term': ['permission'], 'support_ids': [1]}], 'complete': True, 'unresolved': []}
    delta = {'retire_statement_indices': [0],
             'statements': [{'term': ['prohibition'], 'support_ids': [1]}], 'unresolved': ['unread condition']}
    value, _ = statements(old, delta, {'units': [{'id': 1}]})
    assert value['complete'] is False and value['unresolved'] == ['unread condition']
