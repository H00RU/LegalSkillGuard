"""Freeze real M2 and complete-pair replay decisions before evaluation truth.

Only the locked development/calibration corpus and original public native
consumer inputs enter selection. This command never opens structural-evaluation
reference proposals, native grading, or evaluation predictions. Zero model calls.
"""
import argparse
from collections import defaultdict
import json
from pathlib import Path

import numpy as np

from experiments.two_method_annotate import inputs
from experiments.two_method_graph_corpus import BASE, ROOT, read, restore_pair, sha
from legal_skill_guard.paired_interfaces.native_channel_selection import (
    NativeLoss, choose_risks, mother_world_weights, native_replay, native_risk)
from legal_skill_guard.paired_interfaces.rich_graph_pairs import consumer_signature
from legal_skill_guard.paired_interfaces.observed_abstention import restore_edit
from legal_skill_guard.paired_interfaces.structural_channel import Channel, graph_key
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


def restore_channel(group, mode, calibration):
    record = group['channels'][mode]
    edits = []
    for item in group['edits']:
        edits.append(restore_edit(item))
    support = frozenset(pair.reference for pair in calibration)
    sources = frozenset(pair.source_id for pair in calibration)
    if (not support or sorted(graph_key(graph) for graph in support) != record['support_graph_keys']
            or sorted(sources) != record['calibration_sources']
            or sources & set(group['development_sources'])
            or any(pair.plan_version != group['version'] or pair.role != 'calibration' for pair in calibration)
            or {(graph.schema, graph.context) for graph in support} != {(next(iter(support)).schema, group['context'])}):
        raise ValueError('A channel no longer matches its disjoint original calibration pairs')
    A, b = np.asarray(record['A']), np.asarray(record['b'])
    if A.ndim != 2 or A.shape != (len(b), len(edits) + 1) or not np.isfinite(A).all() or not np.isfinite(b).all():
        raise ValueError('Malformed saved channel polytope')
    channel = Channel(group['version'], next(iter(support)).schema, group['context'], tuple(edits),
        support, sources, A, b, record['alpha'], mode, record['diagnostics'])
    channel.bounds([0.] * len(edits), [0.] * len(edits))
    return channel


def public_targets(lock, train):
    targets = []
    for row in lock['rows']:
        if row['role'] != 'structure_evaluation':
            continue
        source = train[row['key']]
        if digest(source) != row['public_sha256']:
            raise ValueError('A locked public target changed')
        task, mapping = inputs(source)
        for view in task['views']:
            native_tasks = sorted(name for name, opaque in mapping.items() if opaque == view['view_id'])
            native_public = {v['id']: v['public'] for v in source['views'] if v['id'] in native_tasks}
            if sorted(native_public) != native_tasks:
                raise ValueError('A public native task is missing')
            targets.append({'source': row['key'], 'dataset': row['dataset'], 'view': view['view_id'],
                'context': row['dataset'] + ':' + digest(native_tasks),
                'native_tasks': native_tasks, 'native_public': native_public})
    return targets


def run(snapshot, *, partial_reference_bounds=False):
    snapshot = snapshot.resolve()
    if not snapshot.is_relative_to(BASE.resolve()):
        raise ValueError('Use an immutable corpus snapshot in the current project')
    corpus = read(snapshot / 'corpus.json')
    if snapshot.name != digest(corpus):
        raise ValueError('Corpus snapshot content hash changed')
    corpus_protocol = snapshot.parent.parent / 'protocol.json'
    if sha(corpus_protocol) != corpus['postprocessing_protocol_sha256']:
        raise ValueError('Literal-consumer protocol binding changed')
    postprocessing = read(corpus_protocol)
    for name, expected in postprocessing['source_sha256'].items():
        if sha(ROOT / name) != expected:
            raise ValueError('A frozen literal consumer source changed: ' + name)
    lock_path = BASE / 'pilot_lock.json'
    public_path = ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'
    if sha(lock_path) != corpus['pilot_lock_sha256'] or sha(public_path) != postprocessing['TRAIN_public_sha256']:
        raise ValueError('The original pilot or TRAIN public binding changed')
    lock = read(lock_path)
    if (not corpus['inventory'] or len(corpus['pairs']) != len(corpus['inventory'])
            or any(row['role'] not in ('development', 'calibration') for row in corpus['pairs'])
            or any(not row['reference_reviewed'] or not row['read_settled'] for row in corpus['inventory'])
            or corpus.get('structure_evaluation_reference_graphs_opened') is not False
            or corpus.get('DEV_or_TEST_grading_opened') is not False):
        raise ValueError('Selection requires the complete fixed non-evaluation corpus')
    fitted = read(snapshot / 'fitted_channels.json')
    pairs = defaultdict(list)
    for record in corpus['pairs']:
        pair = restore_pair(record['pair'])
        if (pair.source_id, pair.role, pair.plan_version, pair.reference.context) != (
                record['source'], record['role'], record['version'], record['context']):
            raise ValueError('A pair lost its source/role/version/context binding')
        if pair.role == 'calibration':
            pairs[record['context'], record['version']].append(pair)
    groups = defaultdict(list)
    for group in fitted['groups']:
        groups[group['context']].append(group)
    train = {source['key']: source for source in read(public_path)}
    targets = public_targets(lock, train)
    paths = [str(Path(__file__).relative_to(ROOT)),
             'legal_skill_guard/paired_interfaces/native_channel_selection.py',
             'legal_skill_guard/paired_interfaces/observed_abstention.py',
             'legal_skill_guard/paired_interfaces/partial_native_loss.py']
    bindings = {name: sha(ROOT / name) for name in paths}
    protocol = {'experiment': 'real_native_M2_and_complete_pair_replay_selection_v1',
        'source_sha256': {**postprocessing['source_sha256'], **bindings},
        'corpus_snapshot': str(snapshot.relative_to(ROOT)), 'corpus_sha256': sha(snapshot / 'corpus.json'),
        'fitted_channels_sha256': sha(snapshot / 'fitted_channels.json'),
        'pilot_lock_sha256': sha(lock_path), 'TRAIN_public_sha256': sha(public_path),
        'public_target_consumers_sha256': digest(targets),
        'selection_worlds': 'all locked calibration mothers, then equal distinct views within mother',
        'undefined_reference_worlds': ('preserve all mass;prediction abstention loss1,defined prediction loss[0,1]'
            if partial_reference_bounds else 'unsupported; preserve full mass and baseline; no filtering'),
        'undefined_edited_worlds': ('native pipeline abstention loss1 regardless of reference definedness'
            if partial_reference_bounds else 'native pipeline abstention loss1 when reference output is defined'),
        'decision_costs': 'zero for every plan; token costs reported separately, no cost-only mechanism claim',
        'baseline': 'first originally locked plan for each dataset',
        'tie_rule': 'lexicographic plan name after upper risk',
        'conditional_assumptions': lock['M2_conditional_assumptions'],
        'target_worlds_are_not_used_in_selection': True,
        'transfer_to_evaluation_source_structures_not_validated_by_selection': True,
        'reference_outputs_are_not_asserted_native_gold': True,
        'native_loss_policy': ('abstention_aware_partial_reference_outer_bounds_v1'
            if partial_reference_bounds else 'strict_defined_reference_loss_v1'),
        'new_model_requests': 0, 'new_independent_trials': 0,
        'structure_evaluation_reference_graphs_opened': False,
        'native_grading_or_evaluation_predictions_opened': False}
    out = BASE / 'native_selection_v1' / digest(protocol)
    immutable_json(out / 'protocol.json', protocol)
    for name in bindings:
        target = out / 'source_snapshot' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        raw = (ROOT / name).read_bytes()
        if target.exists() and target.read_bytes() != raw:
            raise ValueError('Selection implementation snapshot changed')
        if not target.exists():
            target.write_bytes(raw)
    decisions = []
    if partial_reference_bounds:
        from legal_skill_guard.paired_interfaces.partial_native_loss import risk_bounds, replay_bounds
        predict_risk, replay_risk = risk_bounds, replay_bounds
    else:
        predict_risk, replay_risk = native_risk, native_replay
    for target in targets:
        family = groups.get(target['context'], [])
        baseline = lock['plans'][target['dataset']][0]['name']
        row = {key: value for key, value in target.items() if key != 'native_public'}
        row['public_consumer_sha256'] = digest(target['native_public'])
        row['baseline'] = baseline
        expected_plans = {plan['name'] for plan in lock['plans'][target['dataset']]}
        if {group['plan'] for group in family} != expected_plans or any(not g.get('fitted') for g in family):
            row.update(supported=False, reason='Incomplete fixed channel family', baseline_retained=baseline)
            decisions.append(row)
            continue
        family = sorted(family, key=lambda group: group['plan'])
        weights = mother_world_weights(pairs[family[0]['context'], family[0]['version']])
        for group in family[1:]:
            if mother_world_weights(pairs[group['context'], group['version']]) != weights:
                raise ValueError('Competing plans no longer share the full reference distribution')
        loss = NativeLoss(lambda world: consumer_signature(world, target['dataset'], target['native_public']))
        row['calibration_mothers'] = family[0]['channels']['unrestricted']['calibration_sources']
        row['train_world_weights'] = [{'graph_key': graph_key(graph), 'weight': weight}
                                      for graph, weight in sorted(weights.items(), key=lambda item: graph_key(item[0]))]
        costs = {group['plan']: 0. for group in family}
        row['M2'] = {}
        for mode in ('unrestricted', 'detectable_residual'):
            predictions = {}
            for group in family:
                calibration = pairs[group['context'], group['version']]
                channel = restore_channel(group, mode, calibration)
                predictions[group['plan']] = predict_risk(channel, loss, weights, version=group['version'])
            row['M2'][mode] = choose_risks(predictions, baseline=baseline, costs=costs)
        replay = {group['plan']: replay_risk(pairs[group['context'], group['version']], loss, weights)
                  for group in family}
        row['complete_paired_trace_replay'] = choose_risks(replay, baseline=baseline, costs=costs, replay=True)
        row['candidate_read_bindings'] = {group['plan']: {
            'literal_consumer_version': group['version'],
            'raw_read_version': next(item['raw_read_version'] for item in corpus['inventory']
                if item['context'] == group['context'] and item['version'] == group['version'])}
            for group in family}
        row['supported'] = all(result['supported'] for result in row['M2'].values())
        decisions.append(row)
    for name, expected in protocol['source_sha256'].items():
        if sha(ROOT / name) != expected:
            raise ValueError('A source changed during native selection: ' + name)
    immutable_json(out / 'selection.json', {'protocol_sha256': sha(out / 'protocol.json'), 'decisions': decisions,
        'structure_evaluation_reference_graphs_opened': False,
        'native_grading_or_evaluation_predictions_opened': False})
    summary = {'artifact_root': str(out.relative_to(ROOT)), 'public_target_views': len(decisions),
        'public_target_mothers': len({row['source'] for row in decisions}),
        'supported_M2_target_views': sum(row['supported'] for row in decisions),
        'risk_informed_M2_target_views': {mode: sum(row.get('M2', {}).get(mode, {}).get('risk_informed_ranking', False)
            for row in decisions) for mode in ('unrestricted', 'detectable_residual')},
        'supported_full_pair_replay_views': sum(row.get('complete_paired_trace_replay', {}).get('supported', False)
            for row in decisions), 'new_model_requests': 0, 'new_independent_trials': 0,
        'native_loss_policy': protocol['native_loss_policy'],
        'partial_reference_answers_not_reconstructed': True,
        'structure_evaluation_reference_graphs_opened': False,
        'native_grading_or_evaluation_predictions_opened': False,
        'M2_mechanism_completion_is_not_established_by_an_unsupported_or_tied_choice': True}
    immutable_json(out / 'summary.json', summary)
    print(json.dumps(summary, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus-snapshot', type=Path, required=True)
    parser.add_argument('--partial-reference-bounds', action='store_true',
        help='Keep unknown reference outputs as loss bounds;abstention remains loss1, never loss0')
    args = parser.parse_args()
    run(args.corpus_snapshot, partial_reference_bounds=args.partial_reference_bounds)


if __name__ == '__main__':
    main()
