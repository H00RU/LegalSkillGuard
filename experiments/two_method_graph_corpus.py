"""Capture audited real TRAIN pairs and fit only complete locked modules.

This command makes no model requests. It never opens structure-evaluation
reference graphs or any DEV/TEST grading file. Missing reference audits and
pending reads are reported separately from actual failed observations.
"""
from collections import defaultdict
import hashlib
import json
from pathlib import Path

from experiments.two_method_annotate import inputs
from legal_skill_guard.paired_interfaces.empirical_channel import (
    graph_record, learn_dictionary, restore_graph)
from legal_skill_guard.paired_interfaces.graph_matching import GraphMatchLimit
from legal_skill_guard.paired_interfaces.graph_pairs import (
    consumer_signature, pair_from_audited_reference)
from legal_skill_guard.paired_interfaces.structural_channel import (
    Pair, fit, graph_key, observations)
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/two_method_followthrough_20261116'


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def serialize_pair(pair):
    return {'source_id': pair.source_id, 'reference': graph_record(pair.reference),
            'observed': [graph_record(g) for g in sorted(observations(pair), key=graph_key)],
            'plan_version': pair.plan_version, 'role': pair.role, 'provenance': pair.provenance}


def restore_pair(record):
    return Pair(record['source_id'], restore_graph(record['reference']),
                frozenset(restore_graph(g) for g in record['observed']),
                record['plan_version'], record['role'], record['provenance'])


def capture():
    lock, protocol = read(BASE / 'pilot_lock.json'), read(BASE / 'pilot_reads_v3/protocol.json')
    if protocol['executor'] != lock['executor']:
        raise ValueError('The actual reader profile differs from the locked profile')
    if sha(BASE / 'pilot_lock.json') != protocol['pilot_lock_sha256']:
        raise ValueError('The pilot lock differs from the actual reader binding')
    for name, expected in protocol['source_sha256'].items():
        if sha(ROOT / name) != expected:
            raise ValueError('A live reader binding changed: ' + name)
    public = ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'
    if sha(public) != read(BASE / 'prepared/source_lock.json')['prepared_sha256']['train']['public']:
        raise ValueError('The locked original TRAIN public bytes changed')
    train = {s['key']: s for s in read(public)}
    plans = {d: dict(zip([p['name'] for p in ps], protocol['read_versions'][d]))
             for d, ps in lock['plans'].items()}
    inventory, paired = [], []
    annotation_root = BASE / 'annotation_v1/proposed_references'
    for row in lock['rows']:
        if row['role'] == 'structure_evaluation':
            continue  # No opening those references, including audit artifacts.
        source = train[row['key']]
        if digest(source) != row['public_sha256']:
            raise ValueError('A fixed source changed')
        task, mapping = inputs(source)
        for view in task['views']:
            native_tasks = sorted(name for name, opaque in mapping.items() if opaque == view['view_id'])
            # This partition uses public native task identities, never outcomes
            # or the teacher's graph structure. Repeated views remain clustered
            # by their original mother source in the channel confidence set.
            context = source['dataset'] + ':' + digest(native_tasks)
            audit_path = annotation_root / digest(row['key']) / 'audits' / view['view_id'] / 'source_review.json'
            audit = read(audit_path) if audit_path.exists() else None
            if audit is not None and (audit['source'] != row['key'] or audit['role'] != row['role']
                    or audit['view_id'] != view['view_id'] or sorted(audit['native_views']) != native_tasks
                    or audit['source_units_sha256'] != digest(view['source_units'])
                    or audit.get('reference_ready') is not True
                    or audit.get('source_semantic_truth_verified') is not True):
                raise ValueError('A source review does not bind this source/view/role')
            for name, version in plans[source['dataset']].items():
                identity = digest([row['key'], view['view_id'], version])
                path = BASE / 'pilot_reads_v3/reads' / identity / 'decoded.json'
                actual = read(path) if path.exists() else None
                item = {'source': row['key'], 'dataset': source['dataset'], 'role': row['role'],
                        'view': view['view_id'], 'native_tasks': native_tasks, 'context': context,
                        'plan': name, 'version': version, 'reference_reviewed': audit is not None,
                        'read_settled': actual is not None}
                if actual is not None and (actual['source'] != row['key']
                        or actual['role'] != row['role'] or actual['plan_version'] != version
                        or actual['opaque_source_view'] != view['view_id']):
                    raise ValueError('A read does not bind this source/view/version')
                if audit is not None:
                    item.update(audit_path=str(audit_path.relative_to(ROOT)), audit_sha256=sha(audit_path))
                if actual is not None:
                    item.update(read_path=str(path.relative_to(ROOT)), read_sha256=sha(path),
                                physical_call_id=actual['physical_call_id'],
                                actual_read_errors=actual['errors'])
                inventory.append(item)
                if audit is None or actual is None:
                    continue
                pair, alignment = pair_from_audited_reference(
                    audit['graph'], actual['decoded_graph'], view['source_units'],
                    source=row['key'], role=row['role'], version=version, context=context,
                    provenance=digest({'source_audit': item['audit_sha256'],
                                       'physical_read': actual['physical_call_id'],
                                       'read_artifact': item['read_sha256']}),
                    semantic_reference_verified=True, observation_errors=actual['errors'])
                domain = consumer_signature(pair.reference, source['dataset'], native_tasks)
                paired.append({**item, 'pair': serialize_pair(pair), 'alignment': alignment,
                               'reference_native_consumer_domain': domain})
    return {'protocol': 'audited-real-train-pairs-v1', 'inventory': inventory, 'pairs': paired,
            'reader_protocol_sha256': sha(BASE / 'pilot_reads_v3/protocol.json'),
            'pilot_lock_sha256': sha(BASE / 'pilot_lock.json'),
            'source_unit': 'original mother source; views are not independent samples',
            'structure_evaluation_reference_graphs_opened': False,
            'DEV_or_TEST_grading_opened': False, 'new_model_requests': 0,
            'unknown_observations_retained': True,
            'reference_review_scope': 'root assistant source-local audit; not independent human gold'}


def fit_complete_groups(corpus):
    groups, pair_groups = defaultdict(list), defaultdict(list)
    for item in corpus['inventory']:
        groups[item['context'], item['version']].append(item)
    for item in corpus['pairs']:
        pair_groups[item['context'], item['version']].append(item)
    # A selection family consists of the fixed competing plans for one public
    # consumer, including both explicitly different unknown-error models.
    # Unrelated consumers are separately reported and do not claim one global
    # 95% band. This is the family in the pinned prototype's README.
    versions_by_context = defaultdict(set)
    for context, version in groups:
        versions_by_context[context].add(version)
    results = []
    for key, items in sorted(groups.items()):
        context, version = key
        alpha = .05 / (2 * len(versions_by_context[context]))
        ready = all(i['reference_reviewed'] and i['read_settled'] for i in items)
        report = {'context': context, 'dataset': items[0]['dataset'],
                  'native_tasks': items[0]['native_tasks'], 'plan': items[0]['plan'],
                  'version': version, 'expected_views': len(items),
                  'missing_reference_reviews': sum(not i['reference_reviewed'] for i in items),
                  'pending_reads': sum(not i['read_settled'] for i in items),
                  'all_locked_development_and_calibration_inputs_ready': ready,
                  'confidence_selection_family': context, 'alpha_per_plan_and_mode': alpha}
        results.append(report)
        if not ready:
            report['fitted'] = False
            continue
        records = pair_groups[key]
        development = [restore_pair(r['pair']) for r in records if r['role'] == 'development']
        calibration = [restore_pair(r['pair']) for r in records if r['role'] == 'calibration']
        if not development or not calibration:
            report.update(fitted=False, unsupported='This fixed public module lacks both disjoint roles')
            continue
        try:
            dictionary = learn_dictionary(development)
            report.update(development_sources=sorted(dictionary['development_sources']),
                          unmodeled_development_sources=dictionary['unmatched_development_sources'],
                          reference_native_domain_views=sum(bool(r['reference_native_consumer_domain']['handled'])
                                                            for r in records),
                          edit_count=len(dictionary['edits']),
                          edits=[{'identity': e.identity, 'variables': e.variables,
                                  'before': [vars(f) for f in e.before],
                                  'after': [vars(f) for f in e.after], 'all_matches': e.all_matches}
                                 for e in dictionary['edits']], channels={})
            for mode in ('unrestricted', 'detectable_residual'):
                channel = fit(calibration, dictionary, version=version, alpha=alpha, unknown_mode=mode)
                report['channels'][mode] = {'A': channel.A.tolist(), 'b': channel.b.tolist(),
                    'alpha': channel.alpha, 'diagnostics': channel.diagnostics,
                    'support_graph_keys': sorted(graph_key(g) for g in channel.support),
                    'calibration_sources': sorted(channel.sources),
                    'conditional_detectable_unknown_assumption': mode == 'detectable_residual',
                    'unknown_mass_not_set_to_zero': True}
            report['fitted'] = True
        except (ValueError, GraphMatchLimit) as error:
            report.update(fitted=False, unsupported=type(error).__name__ + ': ' + str(error))
    return {'groups': results,
            'confidence_design': 'fixed_public_consumer_selection_family_v1',
            'familywise_alpha_per_consumer_and_both_modes': .05,
            'all_consumer_union_error_bound': min(1., .05 * len(versions_by_context)),
            'global_95_percent_coverage_claimed': False,
            'no_selection_or_transfer_claim_from_fit_alone': True}


def main():
    corpus = capture()
    paths = [Path(__file__).relative_to(ROOT),
             *[Path('legal_skill_guard/paired_interfaces') / f for f in (
                 'graph_pairs.py', 'empirical_channel.py', 'graph_matching.py', 'structural_channel.py',
                 'numeric_ports.py', 'consumer_graph_contract.py', 'public_graph_ports.py', 'legal_consumers.py')]]
    bindings = {str(p): sha(ROOT / p) for p in paths}
    key = digest({'corpus': corpus, 'source_sha256': bindings})
    target = BASE / 'real_graph_corpus_v1' / key
    for path in paths:
        dest = target / 'source_snapshot' / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        raw = (ROOT / path).read_bytes()
        if dest.exists() and dest.read_bytes() != raw:
            raise ValueError('An immutable corpus implementation snapshot changed')
        if not dest.exists():
            dest.write_bytes(raw)
    immutable_json(target / 'protocol.json', {'source_sha256': bindings,
        'reader_protocol_sha256': corpus['reader_protocol_sha256'],
        'pilot_lock_sha256': corpus['pilot_lock_sha256'], 'new_model_requests': 0})
    immutable_json(target / 'corpus.json', corpus)
    fitted = fit_complete_groups(corpus)
    immutable_json(target / 'fitted_channels.json', fitted)
    print(json.dumps({'artifact_root': str(target.relative_to(ROOT)),
        'expected_train_view_plan_pairs': len(corpus['inventory']), 'audited_actual_pairs': len(corpus['pairs']),
        'ready_groups': sum(g['all_locked_development_and_calibration_inputs_ready'] for g in fitted['groups']),
        'fitted_groups': sum(bool(g.get('fitted')) for g in fitted['groups']),
        'unknown_observation_pairs': sum('unknown_observation' in r['alignment'] for r in corpus['pairs']),
        'structure_evaluation_truth_opened': False, 'new_model_requests': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()
