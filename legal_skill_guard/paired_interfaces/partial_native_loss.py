"""Outer native-failure bounds with incomplete source-reference answers.

Abstention receives failure loss1, as in the existing native scorer. A defined
prediction against an undefined reference has loss[0,1]. Never compare two
undefined outputs as if they were correct. Every original reference world and
its weight remains. These are conditional error-model bounds, not gold answers.
"""
from collections import defaultdict

import numpy as np

from legal_skill_guard.paired_interfaces.graph_matching import GraphMatchLimit
from legal_skill_guard.paired_interfaces.structural_channel import observations


def loss_interval(loss, reference, edited):
    # Old pairing placeholders represent an unavailable alignment, not the
    # actual reader's native output. Their source-specific failure identity
    # must never be mistaken for the canonical production-abstention outcome.
    if any(node.startswith('failed-read:') and kind == 'unresolved_read'
           for node, kind in edited.nodes):
        return [0., 1.]
    observed = loss.result(edited)
    if not observed['handled']:
        return [1., 1.]
    expected = loss.result(reference)
    if not expected['handled']:
        return [0., 1.]
    value = float(observed['signature'] != expected['signature'])
    return [value, value]


def _semantics(domain):
    return {'reference_domain': domain,
        'loss_policy': 'native_failure_outer_bounds_with_partial_references_v1',
        'abstention_is_loss1_even_when_reference_answer_is_unknown': True,
        'defined_prediction_with_unknown_reference_is_loss_0_to_1': True,
        'partial_reference_answer_couplings_relaxed_for_outer_bounds': True,
        'analysis_alignment_placeholders_have_loss_0_to_1_not_assumed_abstention': True,
        'all_reference_weights_retained': True,
        'conditional_on_a_valid_native_task_answer_and_reference_F_when_defined': True,
        'native_accuracy_or_reference_gold_claimed': False}


def risk_bounds(channel, loss, weights, *, version, allow_stationary_transfer=False):
    domain = loss.reference_domain(weights)
    note = _semantics(domain)
    if version != channel.version:
        return {'supported': False, 'reason': 'reader version differs', **note}
    if any((graph.schema, graph.context) != (channel.schema, channel.context) for graph in weights):
        return {'supported': False, 'reason': 'typed structural domain differs', **note}
    missing = set(weights) - channel.support
    if missing and not allow_stationary_transfer:
        return {'supported': False, 'reason': 'reference support gap', **note}
    lower, upper = [], []
    try:
        for edit in channel.edits:
            lo = hi = 0.
            for graph, weight in weights.items():
                outcomes = edit.images(graph)
                if not outcomes:
                    return {'supported': False, 'reason': 'edit applicability gap', **note}
                intervals = [loss_interval(loss, graph, other) for other in outcomes]
                lo += weight * min(value[0] for value in intervals)
                hi += weight * max(value[1] for value in intervals)
            lower.append(lo)
            upper.append(hi)
    except GraphMatchLimit as error:
        return {'supported': False, 'reason': 'Complete rewrite computation exhausted its bound: ' + str(error), **note}
    return {'supported': True, 'interval': channel.bounds(lower, upper),
        'unknown_mode': channel.unknown_mode, 'alpha': channel.alpha,
        'loss_lower_by_edit': lower, 'loss_upper_by_edit': upper,
        'conditional_stationary_transfer': bool(missing), 'extrapolated_worlds': len(missing),
        'unmodeled_error_loss_interval': [0., 1.], **note}


def replay_bounds(pairs, loss, weights):
    domain = loss.reference_domain(weights)
    note = _semantics(domain)
    strata = defaultdict(lambda: defaultdict(list))
    for pair in pairs:
        strata[pair.reference][pair.source_id].append(pair)
    if any(graph not in strata for graph in weights):
        return {'supported': False, 'reason': 'reference support gap', **note}
    lower = upper = 0.
    for graph, weight in weights.items():
        lo, hi = [], []
        for source_pairs in strata[graph].values():
            intervals = [[loss_interval(loss, graph, observed) for observed in observations(pair)]
                         for pair in source_pairs]
            lo.append(float(np.mean([min(value[0] for value in values) for values in intervals])))
            hi.append(float(np.mean([max(value[1] for value in values) for values in intervals])))
        lower += weight * float(np.mean(lo))
        upper += weight * float(np.mean(hi))
    result = {'supported': True, 'empirical_risk_interval': [lower, upper],
              'mother_weighted': True, **note}
    if abs(upper - lower) < 1e-12:
        result['empirical_risk'] = lower
    return result
