"""Native-loss guards for real channel selection and full paired replay.

An undefined reference output is a missing prerequisite, never a correct
prediction. An edited-side abstention is a pipeline failure when the reference
output is defined. No reference worlds are removed or reweighted for coverage.
"""
from collections import defaultdict
import math

from legal_skill_guard.paired_interfaces.graph_matching import GraphMatchLimit
from legal_skill_guard.paired_interfaces.observed_abstention import MARKER
from legal_skill_guard.paired_interfaces.structural_channel import (
    full_trace_replay, graph_key, risk)


def mother_world_weights(pairs):
    """Equal mothers, then equal distinct locked views within each mother."""
    by_source = defaultdict(dict)
    for pair in pairs:
        if pair.role != 'calibration':
            raise ValueError('Risk worlds must come from the locked calibration role')
        by_source[pair.source_id][graph_key(pair.reference)] = pair.reference
    if not by_source:
        raise ValueError('A nonempty calibration distribution is required')
    weights = defaultdict(float)
    for graphs in by_source.values():
        for graph in graphs.values():
            weights[graph] += 1. / (len(by_source) * len(graphs))
    return dict(weights)


class NativeLoss:
    def __init__(self, consume):
        self.consume = consume
        self.cache = {}

    def result(self, graph):
        if graph not in self.cache:
            # A production rejection never reached the native consumer in the
            # actual pipeline, even if a law-only F could answer without facts.
            if dict(graph.nodes).get(MARKER) == 'unresolved_read':
                result = {'handled': False, 'reason': 'Observed production decoder abstention'}
            else:
                result = self.consume(graph)
            if not isinstance(result, dict) or type(result.get('handled')) is not bool:
                raise ValueError('A native consumer must declare whether its output is defined')
            if result['handled'] and not isinstance(result.get('signature'), str):
                raise ValueError('A defined native output needs an unambiguous full signature')
            self.cache[graph] = result
        return self.cache[graph]

    def reference_domain(self, weights):
        if (not weights or any(not math.isfinite(w) or w <= 0 for w in weights.values())
                or abs(sum(weights.values()) - 1.) > 1e-8):
            raise ValueError('Declare positive normalized weights for every risk reference world')
        missing = []
        for graph, weight in weights.items():
            result = self.result(graph)
            if not result['handled']:
                missing.append({'reference_graph_key': graph_key(graph), 'weight': weight,
                                'native_consumer_result': result})
        return {'supported': not missing, 'reference_worlds': len(weights),
                'undefined_reference_worlds': len(missing),
                'undefined_reference_mass': sum(row['weight'] for row in missing),
                'undefined_reference_details': missing,
                'reference_worlds_filtered_or_renormalized': False}

    def __call__(self, graph):
        result = self.result(graph)
        # Different tuple tags keep a legally defined JSON null distinct from
        # an unavailable output. Only edited worlds may reach the second case;
        # every weighted reference was checked before risk or replay runs.
        return (('defined_native_signature', result['signature']) if result['handled']
                else ('edited_native_abstention',))


def native_risk(channel, loss, weights, *, version, allow_stationary_transfer=False):
    domain = loss.reference_domain(weights)
    if not domain['supported']:
        return {'supported': False, 'reason': 'Native reference loss is undefined',
                'reference_domain': domain}
    try:
        result = risk(channel, loss, weights, version=version,
                      allow_stationary_transfer=allow_stationary_transfer)
    except GraphMatchLimit as error:
        result = {'supported': False, 'reason': 'Complete rewrite computation exhausted its bound: ' + str(error)}
    return {**result, 'reference_domain': domain,
            'loss': 'full native signature changes or edited-side abstention',
            'native_accuracy_or_reference_gold_claimed': False}


def native_replay(pairs, loss, weights):
    domain = loss.reference_domain(weights)
    if not domain['supported']:
        return {'supported': False, 'reason': 'Native reference loss is undefined',
                'reference_domain': domain}
    return {**full_trace_replay(pairs, loss, weights), 'reference_domain': domain,
            'loss': 'full native signature changes or edited-side abstention',
            'native_accuracy_or_reference_gold_claimed': False}


def choose_risks(predictions, *, baseline, costs, replay=False):
    """Fixed upper-risk plus cost decision; unsupported families keep baseline."""
    if baseline not in predictions or set(predictions) != set(costs):
        raise ValueError('The baseline, candidates and cost bindings must agree')
    if any(not math.isfinite(value) or value < 0 for value in costs.values()):
        raise ValueError('Decision costs must be finite, nonnegative and declared')
    if any(not row['supported'] for row in predictions.values()):
        return {'supported': False, 'plan': baseline, 'risks': predictions,
                'reason': 'At least one fixed candidate has no supported native risk',
                'risk_informed_ranking': False, 'changed_baseline': False}
    key = 'empirical_risk_interval' if replay else 'interval'
    risk_only = min(predictions, key=lambda name: (predictions[name][key][1], name))
    selected = min(predictions, key=lambda name: (predictions[name][key][1] + costs[name], name))
    differs = len({row[key][1] for row in predictions.values()}) > 1
    return {'supported': True, 'plan': selected, 'risks': predictions,
            'risk_only_plan': risk_only, 'risk_informed_ranking': differs,
            'changed_baseline': selected != baseline,
            'certified_separation': all(predictions[selected][key][1] + costs[selected]
                < row[key][0] + costs[name] for name, row in predictions.items() if name != selected),
            'cost_only_or_tied_risk_choice_is_not_mechanism_evidence': not differs}
