"""Prefix-frozen M1,M2 and full-trace learners for the formal study.

No file/network/grading access. Callers supply verified TRAIN evidence only.
Reference-only worlds have no paired weak observation in the primary learner;
M2 explicitly extrapolates there. Full replay keeps every available paired
development/calibration trace as a strong empirical transfer proxy.
"""
from collections import defaultdict
from copy import deepcopy

import numpy as np

from legal_skill_guard.paired_interfaces.empirical_channel import graph_record, restore_graph
from legal_skill_guard.paired_interfaces.formal_design import assert_pair_access, prefix
from legal_skill_guard.paired_interfaces.graph_matching import GraphMatchLimit
from legal_skill_guard.paired_interfaces.native_channel_selection import NativeLoss, choose_risks
from legal_skill_guard.paired_interfaces.observed_abstention import edit_record, learn_dictionary, restore_edit
from legal_skill_guard.paired_interfaces.partial_native_loss import replay_bounds, risk_bounds
from legal_skill_guard.paired_interfaces.pilot_metrics import summarize
from legal_skill_guard.paired_interfaces.structural_channel import Channel, Pair, fit, graph_key, observations
from legal_skill_guard.skill_evolution.objects import digest


def pair_record(pair):
    return {'source_id': pair.source_id, 'reference': graph_record(pair.reference),
            'observed': [graph_record(graph) for graph in sorted(observations(pair), key=graph_key)],
            'plan_version': pair.plan_version, 'role': pair.role, 'provenance': pair.provenance}


def restore_pair(record):
    return Pair(record['source_id'], restore_graph(record['reference']),
                frozenset(restore_graph(graph) for graph in record['observed']),
                record['plan_version'], record['role'], record['provenance'])


def world_weights(records):
    by_source = defaultdict(dict)
    for row in records:
        graph = restore_graph(row['graph'])
        by_source[row['source']][graph_key(graph)] = graph
    if not by_source:
        raise ValueError('A nonempty prespecified reference distribution is required')
    weights = defaultdict(float)
    for graphs in by_source.values():
        for graph in graphs.values():
            weights[graph] += 1. / (len(by_source) * len(graphs))
    return dict(weights)


def fit_prefix(roles, batch, paired_records, reference_records, native_score_rows, source_native_views,
               *, candidate_orders, source_opaque_views, declared_pair_domain_refusals=None,
               declared_reference_domain_refusals=None):
    """Freeze a complete prefix,including explicit pre-generation domain refusals.

    A failed decoder is still a paired observation.Neither reference-native
    undefinedness nor bad native scores can justify a missing graph pair.
    """
    visible = {row['source']: row for row in prefix(roles, batch)}
    domain_refusals = declared_pair_domain_refusals or {}
    reference_refusals = declared_reference_domain_refusals or {}
    expected_pairs = {(source, view, plan) for source, row in visible.items()
                      if row['role'] in ('development', 'calibration')
                      for view in source_opaque_views[source] for plan in candidate_orders[row['dataset']]}
    expected_refs = {(source, view) for source, row in visible.items() if row['role'] == 'reference_only'
                     for view in source_opaque_views[source]}
    if (not set(domain_refusals) <= expected_pairs or not set(reference_refusals) <= expected_refs
            or any(not isinstance(value, str) or not value for value in [*domain_refusals.values(), *reference_refusals.values()])):
        raise ValueError('Domain refusals need prespecified in-cohort declaration receipts')
    assert_pair_access(roles, [row['source'] for row in paired_records], batch)
    groups = defaultdict(list)
    pair_public = {}
    versions = defaultdict(set)
    identities = set()
    for row in paired_records:
        pair = restore_pair(row['pair'])
        if 'native_public' in row:
            pair_public[digest(pair_record(pair))] = deepcopy(row['native_public'])
        expected = visible[row['source']]
        identity = row['source'], row['view'], row['plan']
        if identity in identities:
            raise ValueError('A paired source/view/candidate was counted twice')
        identities.add(identity)
        if (pair.source_id != row['source'] or pair.role != expected['role']
                or row['dataset'] != expected['dataset'] or row['plan'] not in candidate_orders[row['dataset']]):
            raise ValueError('A pair lost its source/role/candidate binding')
        key = row['dataset'], pair.reference.schema, pair.reference.context, row['plan']
        groups[key].append(pair)
        versions[key].add(pair.plan_version)
    if identities != expected_pairs - set(domain_refusals):
        raise ValueError('Every primary source/view/candidate,including decoder failures,must remain paired')
    if any(len(values) != 1 for values in versions.values()):
        raise ValueError('An unchanged candidate/context contains mixed model/decoder versions')
    reference_groups = defaultdict(list)
    ref_ids = set()
    for row in reference_records:
        identity = row['source'], row['view']
        if identity in ref_ids:
            raise ValueError('A reference-only source/view was counted twice')
        ref_ids.add(identity)
        if row['source'] not in visible or visible[row['source']]['role'] != 'reference_only':
            raise ValueError('Only the current prefix pure-reference pool defines M2 risk worlds')
        graph = restore_graph(row['graph'])
        if row['dataset'] != visible[row['source']]['dataset']:
            raise ValueError('A source-only reference lost its dataset binding')
        reference_groups[row['dataset'], graph.schema, graph.context].append(row)
    if ref_ids != expected_refs - set(reference_refusals):
        raise ValueError('Every prespecified reference-only world must be retained,including native-undefined worlds')
    m1 = {}
    measured_sources = {source for source, row in visible.items()
                        if row['role'] in ('development', 'calibration')}
    if any(row['source'] not in measured_sources for row in native_score_rows):
        raise ValueError('A reference-only/evaluation native grade reached primary M1 selection')
    if any(row['dataset'] != visible[row['source']]['dataset']
           or row['plan'] not in candidate_orders[row['dataset']] for row in native_score_rows):
        raise ValueError('A native TRAIN score lost its dataset/candidate binding')
    for dataset, orders in candidate_orders.items():
        sources = {source for source in measured_sources if visible[source]['dataset'] == dataset}
        if not sources:
            m1[dataset] = {'plan': orders[0], 'supported': False, 'reason': 'no current formal measurements'}
            continue
        expected = {(source, view) for source in sources for view in source_native_views[source]}
        candidates = []
        for index, plan in enumerate(orders):
            selected = [row for row in native_score_rows if row['source'] in sources and row['plan'] == plan]
            candidates.append({'plan': plan, 'candidate_index': index, **summarize(selected, expected)})
        winner = max(candidates, key=lambda row: (row['mother_macro'], -row['candidate_index']))
        m1[dataset] = {'plan': winner['plan'], 'supported': True, 'candidate_metrics': candidates,
                       'reference_or_evaluation_native_grades_used': False}
    fitted = []
    for (dataset, schema, context, plan), pairs in sorted(groups.items()):
        version = next(iter(versions[dataset, schema, context, plan]))
        development = [pair for pair in pairs if pair.role == 'development']
        calibration = [pair for pair in pairs if pair.role == 'calibration']
        record = {'dataset': dataset, 'schema': schema, 'context': context, 'plan': plan, 'version': version,
                  'pairs': [pair_record(pair) | ({'native_public': pair_public[digest(pair_record(pair))]}
                            if digest(pair_record(pair)) in pair_public else {}) for pair in pairs], 'fitted': False,
                  'development_mothers': len({pair.source_id for pair in development}),
                  'calibration_mothers': len({pair.source_id for pair in calibration})}
        fitted.append(record)
        if not development or not calibration:
            record['unsupported'] = 'both source-disjoint development and calibration roles are required'
            continue
        alpha = .05 / (2 * len(candidate_orders[dataset]))
        try:
            from legal_skill_guard.paired_interfaces.observable_transfer import fit_observable, model_record
            record['observable_model'] = model_record(fit_observable(development, calibration))
            dictionary = learn_dictionary(development)
            record.update(edits=[edit_record(edit) for edit in dictionary['edits']],
                          development_sources=sorted(dictionary['development_sources']), channels={})
            for mode in ('unrestricted', 'detectable_residual'):
                channel = fit(calibration, dictionary, version=version, alpha=alpha, unknown_mode=mode)
                record['channels'][mode] = {'A': channel.A.tolist(), 'b': channel.b.tolist(),
                    'alpha': channel.alpha, 'unknown_mode': mode, 'diagnostics': channel.diagnostics,
                    'support_graph_keys': sorted(graph_key(graph) for graph in channel.support),
                    'calibration_sources': sorted(channel.sources)}
            record['fitted'] = True
        except (ValueError, GraphMatchLimit) as error:
            record['unsupported'] = type(error).__name__ + ': ' + str(error)
    snapshot = {'batch': batch, 'M1_choices': m1, 'fitted_groups': fitted,
        'raw_reader_channel_versions': [{key: row[key] for key in ('dataset', 'schema', 'context', 'plan', 'version')}
                                        for row in fitted],
        'reference_world_groups': [{'dataset': dataset, 'schema': schema, 'context': context, 'records': rows}
                                   for (dataset, schema, context), rows in sorted(reference_groups.items())],
        'primary_measured_sources': sorted(measured_sources),
        'current_prefix_reference_only_sources': sorted(source for source, row in visible.items() if row['role'] == 'reference_only'),
        'current_prefix_structural_sources_not_fitted': sorted(source for source, row in visible.items() if row['role'] == 'structure_evaluation'),
        'raw_candidate_orders': candidate_orders,
        'expected_primary_pair_slots': len(expected_pairs),
        'actual_paired_slots': len(identities), 'expected_reference_views': len(expected_refs),
        'declared_pre_generation_pair_domain_refusals': [{'source': source, 'view': view, 'plan': plan, 'declaration_receipt': receipt}
            for (source, view, plan), receipt in sorted(domain_refusals.items())],
        'declared_reference_domain_refusals': [{'source': source, 'view': view, 'declaration_receipt': receipt}
            for (source, view), receipt in sorted(reference_refusals.items())],
        'confidence_family': 'one fixed public consumer,all its plans and both unknown modes;alpha .05',
        'reference_only_observations_or_native_labels_used': False,
        'future_source_evidence_used': False, 'global95_coverage_claimed': False}
    return {**snapshot, 'snapshot_sha256': digest(snapshot)}


def _channel(record, mode):
    saved = record['channels'][mode]
    calibration = [restore_pair(pair) for pair in record['pairs'] if pair['role'] == 'calibration']
    support = frozenset(pair.reference for pair in calibration)
    sources = frozenset(pair.source_id for pair in calibration)
    if (sorted(graph_key(graph) for graph in support) != saved['support_graph_keys']
            or sorted(sources) != saved['calibration_sources'] or sources & set(record['development_sources'])):
        raise ValueError('A frozen channel no longer binds its own source-disjoint calibration')
    return Channel(record['version'], record['schema'], record['context'],
                   tuple(restore_edit(edit) for edit in record['edits']), support, sources,
                   np.asarray(saved['A']), np.asarray(saved['b']), saved['alpha'], mode, saved['diagnostics'])


def arm_snapshot(snapshot, arm):
    """Materialize isolated learned artifacts;shared raw evidence is reusable.

    Native-score changes cannot alter the M2/replay artifacts.The replay cache
    does not carry or execute a learned error-channel model.
    """
    if digest({key: value for key, value in snapshot.items() if key != 'snapshot_sha256'}) != snapshot['snapshot_sha256']:
        raise ValueError('A learned snapshot changed before arm isolation')
    if arm not in ('M1_only', 'M2_fixed_interfaces', 'M1_full_trace_replay', 'M1_M2'):
        raise ValueError('This snapshot belongs to an interface-based arm')
    result = {key: deepcopy(snapshot[key]) for key in (
        'batch', 'raw_candidate_orders', 'raw_reader_channel_versions', 'primary_measured_sources',
        'current_prefix_reference_only_sources', 'current_prefix_structural_sources_not_fitted',
        'confidence_family', 'reference_only_observations_or_native_labels_used',
        'future_source_evidence_used', 'global95_coverage_claimed')}
    result.update(arm=arm, M1_choices={}, fitted_groups=[], reference_world_groups=[])
    if arm == 'M1_only':
        result['M1_choices'] = deepcopy(snapshot['M1_choices'])
    elif arm == 'M1_full_trace_replay':
        result['fitted_groups'] = [{key: deepcopy(row[key]) for key in
            ('dataset', 'schema', 'context', 'plan', 'version', 'pairs')} for row in snapshot['fitted_groups']]
    else:
        result['fitted_groups'] = [deepcopy(row) for row in snapshot['fitted_groups']
            if arm != 'M2_fixed_interfaces' or row['plan'] in ('columns', 'records')]
        for row in result['fitted_groups']:
            row['pairs'] = [pair for pair in row['pairs'] if pair['role'] == 'calibration']
        result['reference_world_groups'] = deepcopy(snapshot['reference_world_groups'])
    return {**result, 'snapshot_sha256': digest(result)}


def select(snapshot, *, dataset, schema, context, arm, consume):
    if digest({key: value for key, value in snapshot.items() if key != 'snapshot_sha256'}) != snapshot['snapshot_sha256']:
        raise ValueError('A frozen learned snapshot changed')
    if snapshot.get('arm', arm) != arm:
        raise ValueError('A different arm learned artifact cannot be borrowed for selection')
    if arm == 'M1_only':
        return snapshot['M1_choices'][dataset]
    if arm not in ('M2_fixed_interfaces', 'M1_M2', 'M1_full_trace_replay'):
        raise ValueError('This selector handles the four fixed interface-based arms')
    if arm in ('M2_fixed_interfaces', 'M1_M2'):
        from legal_skill_guard.paired_interfaces.formal_observable import select_observable
        return select_observable(snapshot, dataset=dataset, schema=schema, context=context, arm=arm, consume=consume)
    plans = snapshot['raw_candidate_orders'][dataset]
    if arm == 'M2_fixed_interfaces':
        plans = [plan for plan in plans if plan in ('columns', 'records')]
    baseline, loss = plans[0], NativeLoss(consume)
    available = [row for row in snapshot['fitted_groups']
                 if (row['dataset'], row['schema'], row['context']) == (dataset, schema, context)]
    by_plan = {row['plan']: row for row in available}
    if len(by_plan) != len(available):
        raise ValueError('Multiple source versions compete under the same candidate name')
    replay = {}
    for plan in plans:
        record = by_plan.get(plan)
        if record is None:
            replay[plan] = {'supported': False, 'reason': 'no current complete paired candidate data'}
            continue
        from legal_skill_guard.paired_interfaces.formal_observable import complete_replay
        replay[plan] = complete_replay(record['pairs'], dataset, consume)
    replay_choice = choose_risks(replay, baseline=baseline, costs={plan: 0. for plan in plans}, replay=True)
    return {**replay_choice, 'channel_model_executed': False,
            'target_reference_graph_label_or_actual_weak_output_used': False,
            'natural_structure_novelty_or_native_accuracy_not_established_by_selection': True}
