"""Learn typed joint graph rewrites and retain channel non-identifiability.

The source-clustered polytope and unknown-error rules extend the pinned finite
prototype to empirical relational graph edits. Rewrite matches remain sets;
ambiguous operations and bindings are never collapsed to a guessed error.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from itertools import permutations, product
import math
from typing import Callable

import numpy as np
from scipy.optimize import linprog

from legal_skill_guard.skill_evolution.objects import digest

STATUSES = {'stated', 'negated', 'unknown', 'not_stated', 'unread'}


@dataclass(frozen=True, order=True)
class Fact:
    predicate: str
    arguments: tuple[str, ...]
    status: str = 'stated'

    def __post_init__(self):
        if self.status not in STATUSES:
            raise ValueError('Unknown, absent, negated and unread are distinct graph states')


@dataclass(frozen=True)
class Graph:
    nodes: tuple[tuple[str, str], ...]
    facts: frozenset[Fact]
    schema: str
    context: str

    def __post_init__(self):
        if len(dict(self.nodes)) != len(self.nodes):
            raise ValueError('Graph node identities must be unique')
        if not self.schema or not self.context:
            raise ValueError('Typed graph schema and structural context are required')


@dataclass(frozen=True)
class Pair:
    source_id: str
    reference: Graph
    observed: Graph | frozenset[Graph]
    plan_version: str
    role: str
    provenance: str

    def __post_init__(self):
        if self.role not in ('development', 'calibration') or not self.provenance:
            raise ValueError('A graph pair needs an explicit TRAIN role and provenance')
        for graph in observations(self):
            if (self.reference.schema, self.reference.context) != (graph.schema, graph.context):
                raise ValueError('Reference and observed graph domains differ')


def observations(pair):
    values = frozenset({pair.observed}) if isinstance(pair.observed, Graph) else pair.observed
    if not isinstance(values, frozenset) or not values or any(not isinstance(g, Graph) for g in values):
        raise ValueError('Keep every compatible complete graph alignment, without guessed probabilities')
    return values


@dataclass(frozen=True)
class JointEdit:
    variables: tuple[tuple[str, str], ...]
    before: tuple[Fact, ...]
    after: tuple[Fact, ...]
    all_matches: bool = False

    @property
    def identity(self):
        return digest({'variables': self.variables,
                       'before': [(f.predicate, f.arguments, f.status) for f in self.before],
                       'after': [(f.predicate, f.arguments, f.status) for f in self.after],
                       'all_matches': self.all_matches})

    def images(self, graph):
        if not self.variables and not self.before and not self.after:
            return frozenset({graph})
        by_kind = defaultdict(list)
        for node, kind in graph.nodes:
            by_kind[kind].append(node)
        variable_kinds = defaultdict(list)
        for variable, kind in self.variables:
            variable_kinds[kind].append(variable)
        choices = []
        for kind, variables in variable_kinds.items():
            if len(by_kind[kind]) < len(variables):
                return frozenset({graph})
            choices.append([dict(zip(variables, values))
                            for values in permutations(sorted(by_kind[kind]), len(variables))])
        outputs, changes = set(), []
        for parts in product(*choices):
            binding = {k: v for part in parts for k, v in part.items()}
            def instantiate(fact):
                return Fact(fact.predicate, tuple(binding.get(a, a) for a in fact.arguments), fact.status)
            before = {instantiate(f) for f in self.before}
            if before <= graph.facts:
                after = {instantiate(f) for f in self.after}
                changes.append((before, after))
                outputs.add(Graph(graph.nodes, frozenset((graph.facts - before) | after), graph.schema, graph.context))
        if self.all_matches and changes:
            # A learned systematic rewrite applies jointly to all compatible
            # anchors. Reject overlapping contradictory rewrites rather than
            # choose an advantageous binding or combine incompatible worlds.
            for i, (left, result) in enumerate(changes):
                for right, other in changes[i + 1:]:
                    if left & right and (result - left) != (other - right):
                        return frozenset(outputs)
            removed = set().union(*(before for before, after in changes))
            added = set().union(*(after for before, after in changes))
            return frozenset({Graph(graph.nodes, frozenset((graph.facts - removed) | added), graph.schema, graph.context)})
        # This is a conditional graph transformation. A missing pattern leaves
        # the graph unchanged; it does not prove that unmodeled errors vanish.
        return frozenset(outputs or {graph})


IDENTITY = JointEdit((), (), ())


def graph_key(graph):
    return digest({'nodes': sorted(graph.nodes), 'schema': graph.schema, 'context': graph.context,
                   'facts': [(f.predicate, f.arguments, f.status) for f in sorted(graph.facts)]})


def generalized_edit(reference, removed, added, *, all_matches=False):
    kinds, variables = dict(reference.nodes), {}
    for fact in [*sorted(removed), *sorted(added)]:
        for argument in fact.arguments:
            if argument in kinds and argument not in variables:
                variables[argument] = '?' + str(len(variables))
    def generalize(fact):
        return Fact(fact.predicate, tuple(variables.get(a, a) for a in fact.arguments), fact.status)
    return JointEdit(tuple((variable, kinds[node]) for node, variable in variables.items()),
                     tuple(generalize(f) for f in sorted(removed)),
                     tuple(generalize(f) for f in sorted(added)), all_matches)


def learn_dictionary(development_pairs):
    """Anti-unify observed joint differences without retaining person names.

    Node variables are typed, injective, and shared across the whole joint
    edit. An edit may therefore explain a swap and a reattachment together.
    New hallucinated node identities remain unknown errors, not repair rules.
    """
    edits = {IDENTITY.identity: IDENTITY}
    sources, unmatched = set(), []
    for pair in development_pairs:
        if pair.role != 'development':
            raise ValueError('Only disjoint dictionary-development sources may define edits')
        sources.add(pair.source_id)
        for observed in observations(pair):
            if pair.reference.nodes != observed.nodes:
                unmatched.append(pair.source_id)
                continue
            removed = sorted(pair.reference.facts - observed.facts)
            added = sorted(observed.facts - pair.reference.facts)
            edit = generalized_edit(pair.reference, removed, added)
            edits[edit.identity] = edit
            # Anti-unify repeated, anchor-local changes. The candidate is kept
            # only when its joint application reproduces the actual whole
            # development pair. This learns an operation beyond storing that
            # pair's exact number of events, without assuming independent edits.
            kinds = dict(pair.reference.nodes)
            anchor_kinds = {'event', 'service_event', 'effect', 'obligation', 'exception', 'bag', 'asset'}
            anchors = {f.arguments[0] for f in removed + added if f.arguments
                       and kinds.get(f.arguments[0]) in anchor_kinds}
            for anchor in sorted(anchors):
                before = [f for f in removed if f.arguments and f.arguments[0] == anchor]
                after = [f for f in added if f.arguments and f.arguments[0] == anchor]
                if before and after:
                    systematic = generalized_edit(pair.reference, before, after, all_matches=True)
                    if systematic.images(pair.reference) == frozenset({observed}):
                        edits[systematic.identity] = systematic
    return {'edits': tuple(edits.values()), 'development_sources': frozenset(sources),
            'unmatched_development_sources': unmatched}


@dataclass
class Channel:
    version: str
    schema: str
    context: str
    edits: tuple[JointEdit, ...]
    support: frozenset[Graph]
    sources: frozenset[str]
    A: np.ndarray
    b: np.ndarray
    alpha: float
    unknown_mode: str
    diagnostics: dict

    def bounds(self, lower_losses, upper_losses):
        low = np.r_[lower_losses, 0.]
        high = np.r_[upper_losses, 1.]
        args = {'A_ub': self.A, 'b_ub': self.b,
                'A_eq': np.ones((1, len(low))), 'b_eq': [1.],
                'bounds': (0., 1.), 'method': 'highs'}
        lo, hi = linprog(low, **args), linprog(-high, **args)
        if not lo.success or not hi.success:
            raise ValueError('Common conditional edit-mixture assumption is infeasible')
        return [max(0., float(lo.fun)), min(1., float(-hi.fun))]


def fit(pairs, dictionary, *, version, alpha=.05, unknown_mode='unrestricted'):
    if not pairs or not 0 < alpha < 1:
        raise ValueError('Nonempty empirical calibration and valid confidence level required')
    if unknown_mode not in ('unrestricted', 'detectable_residual'):
        raise ValueError('Unknown errors cannot be silently discarded')
    schemas = {(p.reference.schema, p.reference.context) for p in pairs}
    if len(schemas) != 1 or any(p.plan_version != version or p.role != 'calibration' for p in pairs):
        raise ValueError('Calibration schema, context, plan version or source role differs')
    sources = frozenset(p.source_id for p in pairs)
    if sources & dictionary['development_sources']:
        raise ValueError('Dictionary development and calibration mothers overlap')
    edits = dictionary['edits']
    strata = defaultdict(lambda: defaultdict(list))
    for pair in pairs:
        strata[pair.reference][pair.source_id].append(pair)
    images = {g: tuple(edit.images(g) for edit in edits) for g in strata}
    if any(not outcomes for values in images.values() for outcomes in values):
        raise ValueError('The edit dictionary has unsupported applicability in this context')
    categories = {g: set().union(*images[g]) for g in strata}
    # Fixed dictionary image-membership tests are source-conditional moments.
    # Their design coefficients are averaged over the same source clusters as
    # their observed indicators. This identifies a common edit mixture without
    # pretending every distinct reference graph has its own independent rate.
    cells = len(edits) + 1
    A, b, counts = [], [], {}
    ambiguous, unmatched = 0, 0
    for graph, groups in strata.items():
        counts[graph_key(graph)] = len(groups)
        for ps in groups.values():
            for pair in ps:
                compatible = sum(bool(observations(pair) & outcomes) for outcomes in images[graph])
                ambiguous += compatible > 1
                unmatched += compatible == 0
    by_source = defaultdict(list)
    for pair in pairs:
        by_source[pair.source_id].append(pair)
    radius = math.sqrt(math.log(2 * cells / alpha) / (2 * len(sources)))
    for classifier in range(cells):
        source_low, source_high, source_certain, source_possible = [], [], [], []
        for ps in by_source.values():
            lows, highs, certain, possible = [], [], [], []
            for pair in ps:
                graph = pair.reference
                target = images[graph][classifier] if classifier < len(edits) else None
                def event(value):
                    return value in target if target is not None else value not in categories[graph]
                matches = [event(g) for g in observations(pair)]
                lows.append(float(all(matches)))
                highs.append(float(any(matches)))
                certain.append([float(all(event(g) for g in outcomes)) for outcomes in images[graph]])
                possible.append([float(any(event(g) for g in outcomes)) for outcomes in images[graph]])
            source_low.append(float(np.mean(lows)))
            source_high.append(float(np.mean(highs)))
            source_certain.append(np.mean(certain, axis=0))
            source_possible.append(np.mean(possible, axis=0))
        lower = max(0., float(np.mean(source_low)) - radius)
        upper = min(1., float(np.mean(source_high)) + radius)
        if unknown_mode == 'detectable_residual':
            unknown_lo = unknown_hi = float(classifier == len(edits))
        else:
            unknown_lo, unknown_hi = 0., 1.
        A.extend([np.r_[np.mean(source_certain, axis=0), unknown_lo],
                  -np.r_[np.mean(source_possible, axis=0), unknown_hi]])
        b.extend([upper, -lower])
    schema, context = next(iter(schemas))
    channel = Channel(version, schema, context, edits, frozenset(strata), sources,
                      np.asarray(A), np.asarray(b), alpha, unknown_mode,
                      {'independent_mothers_by_reference': counts, 'pairs': len(pairs),
                       'ambiguous_pairs': ambiguous, 'unmatched_pairs': unmatched,
                       'ambiguous_observation_alignments': sum(len(observations(p)) > 1 for p in pairs),
                       'simultaneous_cells': cells,
                       'constraint_design': 'frozen_dictionary_source_clustered_moments',
                       'confidence_unit_count': len(sources),
                       'source_cluster_hoeffding_radius': radius,
                       'conditional_common_mixture_assumption': True,
                       'conditional_rewrites_are_identity_when_pattern_absent': True,
                       'detectable_unknown_assumption': unknown_mode == 'detectable_residual'})
    channel.bounds([0.] * len(edits), [0.] * len(edits))
    return channel


def risk(channel, consumer: Callable, train_world_weights, *, version, allow_stationary_transfer=False):
    if version != channel.version:
        return {'supported': False, 'reason': 'reader version differs'}
    if not train_world_weights or abs(sum(train_world_weights.values()) - 1.) > 1e-8 or any(v < 0 for v in train_world_weights.values()):
        raise ValueError('An explicit probability distribution over compatible TRAIN reference worlds is required')
    if any((g.schema, g.context) != (channel.schema, channel.context) for g in train_world_weights):
        return {'supported': False, 'reason': 'typed structural domain differs'}
    missing = set(train_world_weights) - channel.support
    if missing and not allow_stationary_transfer:
        return {'supported': False, 'reason': 'reference support gap'}
    lower, upper = [], []
    for edit in channel.edits:
        losses = []
        for graph, weight in train_world_weights.items():
            outcomes = edit.images(graph)
            if not outcomes:
                return {'supported': False, 'reason': 'edit applicability gap'}
            values = [float(consumer(other) != consumer(graph)) for other in outcomes]
            losses.append((weight * min(values), weight * max(values)))
        lower.append(sum(a for a, b in losses))
        upper.append(sum(b for a, b in losses))
    return {'supported': True, 'interval': channel.bounds(lower, upper),
            'unknown_mode': channel.unknown_mode, 'alpha': channel.alpha,
            'conditional_stationary_transfer': bool(missing), 'extrapolated_worlds': len(missing),
            'loss_lower_by_edit': lower, 'loss_upper_by_edit': upper}


def select(channels, consumer, train_world_weights, *, versions, costs, baseline,
           allow_stationary_transfer=False):
    predictions = {name: risk(channel, consumer, train_world_weights, version=versions[name],
                              allow_stationary_transfer=allow_stationary_transfer)
                   for name, channel in channels.items()}
    if any(not p['supported'] for p in predictions.values()):
        return {'plan': baseline, 'supported': False, 'risks': predictions}
    risk_only = min(predictions, key=lambda name: (predictions[name]['interval'][1], name))
    best = min(predictions, key=lambda name: (predictions[name]['interval'][1] + costs[name], name))
    separated = all(predictions[best]['interval'][1] + costs[best] < p['interval'][0] + costs[name]
                    for name, p in predictions.items() if name != best)
    return {'plan': best, 'supported': True, 'risks': predictions,
            'certified_separation': separated, 'risk_only_plan': risk_only,
            'risk_upper_bounds_differ': len({p['interval'][1] for p in predictions.values()}) > 1,
            'familywise_alpha_bound': sum(c.alpha for c in channels.values())}


def full_trace_replay(pairs, consumer, train_world_weights):
    strata = defaultdict(lambda: defaultdict(list))
    for pair in pairs:
        strata[pair.reference][pair.source_id].append(pair)
    if any(graph not in strata for graph in train_world_weights):
        return {'supported': False, 'reason': 'reference support gap'}
    lower = upper = 0.
    for graph, weight in train_world_weights.items():
        lo, hi = [], []
        for ps in strata[graph].values():
            losses = [[float(consumer(p.reference) != consumer(g)) for g in observations(p)] for p in ps]
            lo.append(float(np.mean([min(values) for values in losses])))
            hi.append(float(np.mean([max(values) for values in losses])))
        lower += weight * float(np.mean(lo))
        upper += weight * float(np.mean(hi))
    result = {'supported': True, 'empirical_risk_interval': [lower, upper], 'mother_weighted': True}
    if abs(upper - lower) < 1e-12:
        result['empirical_risk'] = lower
    return result
