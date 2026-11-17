"""Capture the same paid pilot in a separate consumer-complete graph version.

No new model request or native grading. Keep every old strict/v1 graph artifact.
Only development/calibration references are opened; source audits remain scoped.
"""
from copy import deepcopy
import json
from pathlib import Path

import jsonschema

from experiments.two_method_annotate import inputs
from experiments.two_method_graph_corpus import (
    BASE, ROOT, capture, fit_complete_groups, read, serialize_pair, sha)
from experiments.two_method_normalize_graph_reads import physical_response
from legal_skill_guard.paired_interfaces import airline_interfaces, graph_interface as gi
from legal_skill_guard.paired_interfaces.control_tools import module_assets
from legal_skill_guard.paired_interfaces.graph_evidence import normalize_graph_evidence
from legal_skill_guard.paired_interfaces.graph_prompt import schema_visible_plan
from legal_skill_guard.paired_interfaces.port_evidence import bind_port_evidence
from legal_skill_guard.paired_interfaces.rich_graph_pairs import (
    SCHEMA, consumer_signature, pair_from_audited_reference, reference_graph)
from legal_skill_guard.paired_interfaces.scope_learning import strict_json
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


def decode(actual, item, units, plan):
    response, physical = physical_response(actual, item['source'])
    graph, evidence, port_receipt, error = None, None, None, None
    try:
        if response['finish_reason'] != 'stop':
            raise ValueError('Truncated output remains an unknown observation')
        request = read((ROOT / item['read_path']).with_name('task.json'))
        if (request['source'], request['opaque_source_view'], request['plan_version']) != (
                item['source'], item['view'], item['version']):
            raise ValueError('The actual schema/source/view/version binding changed')
        raw = strict_json(response['content'])
        jsonschema.validate(raw, request['output_schema'])
        if item['dataset'] == 'RuleArena_Airline':
            raw, port_receipt = bind_port_evidence(plan, raw, units)
            graph, decoder = airline_interfaces.decode(plan, raw, units)
        else:
            graph, decoder = gi.decode_plan(plan, raw)
        graph, evidence = normalize_graph_evidence(graph, units)
    except (ValueError, KeyError, TypeError, jsonschema.ValidationError) as exc:
        error = type(exc).__name__ + ': ' + str(exc)
        graph = None
    return {'source': item['source'], 'view': item['view'], 'plan': item['plan'], **physical,
            'graph': graph, 'errors': [error] if error else [],
            'common_graph_evidence_receipt': evidence, 'common_port_evidence_receipt': port_receipt,
            'original_strict_errors': actual['errors'], 'original_reads_not_overwritten': True,
            'new_model_requests': 0, 'new_independent_trial': False}


def run():
    initial = capture()  # Explicitly excludes every structure-evaluation reference.
    lock = read(BASE / 'pilot_lock.json')
    public_path = ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'
    train = {source['key']: source for source in read(public_path)}
    names = ('graph_interface', 'graph_evidence', 'graph_pairs', 'rich_graph_pairs', 'scope_learning',
        'numeric_ports', 'airline_interfaces', 'port_evidence', 'graph_prompt', 'public_graph_ports',
        'consumer_graph_contract', 'legal_consumers', 'native_graph_consumers', 'partial_consumer_worker',
        'control_tools', 'consumer_worker', 'native_adapters', 'empirical_channel', 'graph_matching',
        'structural_channel')
    paths = [str(Path(__file__).relative_to(ROOT)), 'experiments/two_method_annotate.py',
        'experiments/two_method_graph_corpus.py', 'experiments/two_method_normalize_graph_reads.py',
        *['legal_skill_guard/paired_interfaces/' + name + '.py' for name in names],
        *['legal_skill_guard/skill_evolution/' + name + '.py' for name in (
            'sara_statute_kernel', 'partial_native_proof', 'literal_statutory_givens',
            'statute_input_dependencies', 'span_compiler')],
        'history/rr_v2_20261106/data/cache/rr_v2/RuleArena/airline/gen_questions.py']
    bindings = {name: sha(ROOT / name) for name in paths}
    protocol = {'schema': SCHEMA, 'source_sha256': bindings,
        'reader_protocol_sha256': sha(BASE / 'pilot_reads_v3/protocol.json'),
        'pilot_lock_sha256': sha(BASE / 'pilot_lock.json'), 'TRAIN_public_sha256': sha(public_path),
        'shared_native_assets_sha256': {d: digest(module_assets(d)) for d in lock['modules']},
        'new_model_requests': 0, 'new_independent_trials': 0,
        'no_native_grading_or_structure_evaluation_reference_access': True,
        'old_semantic_graphs_and_fits_not_replaced_or_pooled': True,
        'read_values_statuses_and_unknowns_preserved': True}
    out = BASE / 'literal_graph_corpus_v2' / digest(protocol)
    immutable_json(out / 'protocol.json', protocol)
    for name in paths:
        target = out / 'source_snapshot' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        raw = (ROOT / name).read_bytes()
        if target.exists() and target.read_bytes() != raw:
            raise ValueError('A literal graph snapshot changed')
        if not target.exists():
            target.write_bytes(raw)
    corpus = {key: deepcopy(value) for key, value in initial.items() if key not in ('inventory', 'pairs')}
    corpus.update(protocol='audited-real-literal-graph-pairs-v2', graph_schema=SCHEMA,
        postprocessing_protocol_sha256=sha(out / 'protocol.json'), inventory=[], pairs=[])
    plan_by_name = {(dataset, plan['name']): plan for dataset, plans in lock['plans'].items() for plan in plans}
    airline = {plan['version']: plan for plan in map(schema_visible_plan,
        airline_interfaces.compile_plans(lock['plans']['RuleArena_Airline']))}
    cache, processed = {}, []
    def consume(world, dataset, context):
        from legal_skill_guard.paired_interfaces.empirical_channel import graph_record
        key = digest([graph_record(world), dataset, context])
        if key not in cache:
            cache[key] = consumer_signature(world, dataset, context)
        return cache[key]
    for original in initial['inventory']:
        item = deepcopy(original)
        raw_version = item['version']
        item['version'] = digest({'original_read_version': raw_version,
                                  'literal_consumer_protocol': sha(out / 'protocol.json')})
        item['raw_read_version'] = raw_version
        corpus['inventory'].append(item)
        if not item['read_settled']:
            continue
        source = train[item['source']]
        units = next(view['source_units'] for view in inputs(source)[0]['views'] if view['view_id'] == item['view'])
        native_public = {view['id']: view['public'] for view in source['views'] if view['id'] in item['native_tasks']}
        plan = airline[raw_version] if item['dataset'] == 'RuleArena_Airline' else plan_by_name[item['dataset'], item['plan']]
        result = decode(read(ROOT / item['read_path']), {**original, 'version': raw_version}, units, plan)
        result['native_consumer_outputs_before_grading'] = {}
        if result['graph'] is not None:
            (world, _, _), _ = reference_graph(result['graph'], {u['id']: u for u in units}, item['context'])
            result['native_consumer_outputs_before_grading'] = consume(world, item['dataset'], native_public).get('native', {})
        path = out / 'reads' / (digest([item['source'], item['view'], raw_version]) + '.json')
        immutable_json(path, result)
        processed.append(result)
        if not item['reference_reviewed']:
            continue
        audit = read(ROOT / item['audit_path'])
        reference, reference_evidence = normalize_graph_evidence(audit['graph'], units)
        pair, alignment = pair_from_audited_reference(reference, result['graph'], units,
            source=item['source'], role=item['role'], version=item['version'], context=item['context'],
            provenance=digest({'source_audit': item['audit_sha256'], 'actual_read': result['physical_call_id'],
                               'postprocessing_protocol': sha(out / 'protocol.json')}),
            semantic_reference_verified=True, observation_errors=result['errors'])
        corpus['pairs'].append({**item, 'pair': serialize_pair(pair), 'alignment': alignment,
            'reference_literal_evidence': reference_evidence,
            'reference_native_consumer_domain': consume(pair.reference, item['dataset'], native_public),
            'postprocessed_read_path': str(path.relative_to(ROOT))})
    for name, expected in bindings.items():
        if sha(ROOT / name) != expected:
            raise ValueError('A literal graph source changed during capture: ' + name)
    target = out / 'snapshots' / digest(corpus)
    immutable_json(target / 'corpus.json', corpus)
    fitted = fit_complete_groups(corpus)
    immutable_json(target / 'fitted_channels.json', fitted)
    summary = {'artifact_root': str(out.relative_to(ROOT)), 'corpus_snapshot': str(target.relative_to(ROOT)),
        'processed_actual_reads': len(processed), 'valid_literal_metadata_reads': sum(r['graph'] is not None for r in processed),
        'audited_actual_pairs': len(corpus['pairs']),
        'unknown_observation_pairs': sum('unknown_observation' in row['alignment'] for row in corpus['pairs']),
        'actual_native_views_executed_before_grading': sum(result['handled'] for row in processed
            for result in row['native_consumer_outputs_before_grading'].values()),
        'ready_groups': sum(group['all_locked_development_and_calibration_inputs_ready'] for group in fitted['groups']),
        'fitted_groups': sum(bool(group.get('fitted')) for group in fitted['groups']),
        'new_model_requests': 0, 'new_independent_trials': 0,
        'structure_evaluation_reference_or_native_grading_opened': False}
    immutable_json(target / 'summary.json', summary)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    run()
