"""Exact current-selection certificate from independent native-loss bounds.

Only currently erroneous contexts require finite output enumeration: a hard-
valid zero-loss context already attains its nonnegative loss lower bound. If
the current selection attains the sum of these bounds and has zero edits, it
minimizes the existing lexicographic objective for this fixed representation.
No partial search or semantic-review failure can serve as a lower-bound proof.
"""
from .objects import digest
from .theory_supervision import native_loss
from .relational_rules import context_identity, language_identity


def certify_unchanged_selection(library, prior_selected, rows, checker_for, profile_for):
    if set(library['selected_rule_ids']) != set(prior_selected):
        return {'certified': False, 'reason': 'Selection differs; zero-edit bound cannot certify it'}
    witnesses = []
    for row in rows:
        sid = row['source']
        actual = row['actual']
        feedback = checker_for(sid)(actual['execution']['source_output'])
        observed = native_loss(feedback)
        if observed is None:
            return {'certified': False, 'reason': 'Current output violates a hard source/type/execution check', 'source': sid}
        if observed == 0:
            lower, profile_hash = 0, None
        else:
            profile = profile_for(sid, row['observation'])
            if profile['context_sha256'] != context_identity(row['observation']['context']) or profile['language_sha256'] != language_identity(library['language']):
                raise ValueError('Loss-bound profile differs from the current observation or G language')
            if profile['status'] != 'complete':
                return {'certified': False, 'reason': 'Incomplete enumeration is not a loss bound', 'source': sid}
            losses = [native_loss(r['native_feedback']) for r in profile['evaluations']
                if r['partial_source_constraints_satisfied'] and 'native_feedback' in r]
            losses = [loss for loss in losses if loss is not None]
            if not losses:
                return {'certified': False, 'reason': 'No hard-valid reachable output', 'source': sid}
            lower, profile_hash = min(losses), digest(profile)
        witnesses.append({'source': sid, 'current_native_loss': observed, 'native_loss_lower_bound': lower,
            'complete_profile_sha256': profile_hash, 'actual_output_sha256': digest(actual['execution']['source_output'])})
    observed = sum(r['current_native_loss'] for r in witnesses)
    lower = sum(r['native_loss_lower_bound'] for r in witnesses)
    return {'certified': observed == lower, 'scope_sources': [r['source'] for r in rows],
        'native_loss': observed, 'native_loss_lower_bound': lower,
        'selection_edits': 0, 'selection_edit_lower_bound': 0,
        'selection_complexity_fixed_by_the_unique_zero_edit_selection': True,
        'exact_objective_minimum_given_current_phi': observed == lower,
        'all_current_outputs_passed_existing_hard_checks': True, 'witnesses': witnesses,
        'source_truth_beyond_existing_checks_not_certified': True,
        'all_zero_loss_contexts_use_nonnegative_zero_lower_bound': True,
        'new_model_calls': 0}
