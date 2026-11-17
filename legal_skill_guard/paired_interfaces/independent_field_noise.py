"""Empirical independent-field transfer comparator,without a joint channel.

Use every available paired TRAIN trace,with equal mother/view weights. Keep
whole-read production abstention mass explicitly;conditionally on a valid read,
draw each factual predicate family independently from its empirical marginal
rewrite distribution. Alignment alternatives remain sets,not guessed rates.
This is an empirical conditional independence/stationarity model,not a finite
sample coverage guarantee. Unknown edits retain native-loss bounds[0,1].
"""
from collections import defaultdict
from itertools import product
import math

from legal_skill_guard.paired_interfaces.empirical_channel import indexed
from legal_skill_guard.paired_interfaces.graph_matching import GraphMatchLimit
from legal_skill_guard.paired_interfaces.native_channel_selection import NativeLoss
from legal_skill_guard.paired_interfaces.observed_abstention import MARKER, edit_record, restore_edit
from legal_skill_guard.paired_interfaces.partial_native_loss import loss_interval
from legal_skill_guard.paired_interfaces.structural_channel import Graph, generalized_edit, graph_key, observations
from legal_skill_guard.skill_evolution.objects import digest


def family(fact):
    return fact.predicate.split(':', 1)[0]


def project(graph, field):
    return Graph(graph.nodes, frozenset(f for f in graph.facts if family(f) == field), graph.schema, graph.context)


def _unknown(graph):
    return any(node.startswith('failed-read:') and kind == 'unresolved_read' for node, kind in graph.nodes)


def fit(pairs):
    pairs = list(pairs)
    if not pairs or len({(p.plan_version, p.reference.schema, p.reference.context) for p in pairs}) != 1:
        raise ValueError('Independent-field fitting requires one complete reader/schema/context version')
    by_source = defaultdict(list); seen = set(); fields = set()
    for pair in pairs:
        identity = pair.source_id, pair.provenance
        if identity in seen:
            raise ValueError('The same actual TRAIN pair cannot count twice')
        seen.add(identity); by_source[pair.source_id].append(pair)
        fields.update(family(f) for f in pair.reference.facts)
        for observed in observations(pair):
            if MARKER not in dict(observed.nodes) and not _unknown(observed):
                fields.update(family(f) for f in observed.facts)
    weighted = [(p, 1. / (len(by_source) * len(values))) for values in by_source.values() for p in values]
    abstention = 0.; valid = []
    for pair, weight in weighted:
        flags = {MARKER in dict(graph.nodes) for graph in observations(pair)}
        if len(flags) != 1:
            raise ValueError('Do not assign probabilities to ambiguous production-abstention alignments')
        if flags == {True}:
            abstention += weight
        else:
            valid.append((pair, weight))
    marginals = {}
    for field in sorted(fields):
        aggregated = {}
        for pair, weight in valid:
            options = {}
            for observed in observations(pair):
                if _unknown(observed) or pair.reference.nodes != observed.nodes:
                    options['unknown'] = None
                    continue
                reference, actual = project(pair.reference, field), project(observed, field)
                edit = indexed(generalized_edit(reference, reference.facts - actual.facts, actual.facts - reference.facts))
                try:
                    supported = actual in edit.images(reference)
                except GraphMatchLimit:
                    supported = False
                options[edit.identity if supported else 'unknown'] = edit_record(edit) if supported else None
            values = [options[key] for key in sorted(options)]
            key = digest(values)
            if key not in aggregated:
                aggregated[key] = {'component_id': key, 'weight': 0., 'edit_options': values}
            aggregated[key]['weight'] += weight / (1. - abstention)
        marginals[field] = [aggregated[key] for key in sorted(aggregated)]
        if valid and abs(math.fsum(row['weight'] for row in marginals[field]) - 1.) > 1e-9:
            raise ValueError('The conditional empirical field marginal lost probability mass')
    first = pairs[0]
    model = {'model': 'empirical-independent-field-transfer-v1', 'version': first.plan_version,
        'schema': first.reference.schema, 'context': first.reference.context,
        'source_mothers': sorted(by_source), 'actual_pairs': len(pairs),
        'support_graph_keys': sorted({graph_key(p.reference) for p in pairs}),
        'observed_pair_provenance_sha256': digest([{'source': p.source_id, 'role': p.role,
            'reference': graph_key(p.reference), 'observed': sorted(graph_key(g) for g in observations(p)),
            'provenance': p.provenance} for p in sorted(pairs, key=lambda p: (p.source_id, p.provenance))]),
        'production_abstention_probability': abstention, 'conditional_field_marginals': marginals,
        'fit_sources': 'all available development and calibration pairs',
        'joint_field_dependence_retained': False, 'empirical_marginals_are_not_true_population_probabilities': True,
        'conditional_on_nonabstention_without_dropping_overall_abstention_mass': True,
        'alignment_alternatives_have_no_assigned_probability': True,
        'native_labels_or_current_target_actual_reads_used': False, 'statistical_coverage_guarantee_claimed': False}
    return {**model, 'model_sha256': digest(model)}


def risk(model, consume, weights, *, version, allow_stationary_transfer=False,
         max_terms=20000, max_images=20000):
    if model['model_sha256'] != digest({k: v for k, v in model.items() if k != 'model_sha256'}):
        raise ValueError('The independent-field model changed after freezing')
    note = {'empirical_independence_and_conditional_stationarity_assumptions': True,
        'statistical_coverage_guarantee_claimed': False, 'native_gold_or_accuracy_claimed': False,
        'source_mothers': len(model['source_mothers']), 'all_reference_mass_retained': True}
    if version != model['version']:
        return {'supported': False, 'reason': 'reader/decoder version differs', **note}
    if (not weights or any(not math.isfinite(w) or w <= 0 for w in weights.values())
            or abs(math.fsum(weights.values()) - 1.) > 1e-9):
        raise ValueError('Declare all positive normalized reference-world weights')
    if any((g.schema, g.context) != (model['schema'], model['context']) for g in weights):
        return {'supported': False, 'reason': 'typed structural context differs', **note}
    extrapolated = [g for g in weights if graph_key(g) not in model['support_graph_keys']]
    if extrapolated and not allow_stationary_transfer:
        return {'supported': False, 'reason': 'reference support gap requires an explicit stationarity assumption', **note}
    marginals = model['conditional_field_marginals']
    abstention = model['production_abstention_probability']
    if abstention >= 1. - 1e-12:
        return {'supported': True, 'interval': [1., 1.], 'production_abstention_probability': abstention,
                'conditional_stationary_transfer': bool(extrapolated), 'extrapolated_worlds': len(extrapolated), **note}
    terms = math.prod(len(values) for values in marginals.values())
    if terms * len(weights) > max_terms:
        return {'supported': False, 'reason': 'complete independent-field product exceeds its fixed work bound', **note}
    fields, loss = list(marginals), NativeLoss(consume)
    lower = upper = unknown_field_mass = 0.; work = 0
    try:
        for graph, world_weight in weights.items():
            if {family(f) for f in graph.facts} - set(fields):
                upper += world_weight; unknown_field_mass += world_weight
                continue
            lo = hi = 0.; cache = {}
            for components in product(*(marginals[field] for field in fields)):
                probability = math.prod(c['weight'] for c in components)
                if any(None in c['edit_options'] for c in components):
                    hi += probability; continue
                possibilities = []
                for field, component in zip(fields, components):
                    key = field, component['component_id']
                    if key not in cache:
                        images = set()
                        for saved in component['edit_options']:
                            images.update(restore_edit(saved).images(project(graph, field)))
                        if any(any(family(f) != field for f in image.facts) for image in images):
                            raise ValueError('A marginal field rewrite changed another field')
                        cache[key] = sorted({image.facts for image in images}, key=lambda facts:
                            digest([(f.predicate, f.arguments, f.status) for f in sorted(facts)]))
                    possibilities.append(cache[key])
                work += math.prod(len(values) for values in possibilities)
                if work > max_images:
                    return {'supported': False, 'reason': 'complete ambiguous field images exceed their fixed work bound', **note}
                intervals = [loss_interval(loss, graph, Graph(graph.nodes, frozenset().union(*parts), graph.schema, graph.context))
                             for parts in product(*possibilities)]
                if not intervals:
                    return {'supported': False, 'reason': 'an empirical marginal has no complete image', **note}
                lo += probability * min(value[0] for value in intervals)
                hi += probability * max(value[1] for value in intervals)
            lower += world_weight * lo; upper += world_weight * hi
    except GraphMatchLimit as error:
        return {'supported': False, 'reason': 'complete marginal matching exhausted its bound:' + str(error), **note}
    interval = [abstention + (1 - abstention) * lower, abstention + (1 - abstention) * upper]
    if not -1e-9 <= interval[0] <= interval[1] + 1e-9 <= 1. + 2e-9:
        raise ValueError('Independent-field probability/loss mass escaped its declared bounds')
    interval = [max(0., min(1., value)) for value in interval]
    return {'supported': True, 'interval': interval,
        'production_abstention_probability': abstention, 'unmodeled_target_field_mass': unknown_field_mass,
        'conditional_stationary_transfer': bool(extrapolated), 'extrapolated_worlds': len(extrapolated),
        'independent_product_terms_per_world': terms, 'complete_native_images_evaluated': work,
        'undefined_reference_loss_retains_0_to_1_bounds': True, **note}
