"""Versioned source-only postprocessing of already paid rich graph reads.

Never dispatch, retry, repair partial JSON, change a semantic value, or open
evaluation reference truth. The strict v3 predictions remain immutable. The
new deterministic decoder/alignment receives its own full calibration version.
"""
from copy import deepcopy
import json
from pathlib import Path
import sqlite3

import jsonschema

from experiments.two_method_annotate import inputs
from experiments.two_method_graph_corpus import (
    BASE, ROOT, capture, fit_complete_groups, read, serialize_pair, sha)
from legal_skill_guard.paired_interfaces import graph_interface as gi
from legal_skill_guard.paired_interfaces.public_graph_ports import consumer_graph
from legal_skill_guard.paired_interfaces.graph_evidence import normalize_graph_evidence
from legal_skill_guard.paired_interfaces.graph_pairs import consumer_signature, pair_from_audited_reference
from legal_skill_guard.paired_interfaces.legal_consumers import contract, maud
from legal_skill_guard.paired_interfaces.numeric_ports import normalize_numeric_ports
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

LEDGER = ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'


def strict_constant(name):
    raise ValueError('Non-JSON numeric literal: ' + name)


def physical_response(actual, source):
    identity = actual['physical_call_id']
    paths = [BASE / phase / 'calls' / digest(identity) / 'result.json'
             for phase in ('pilot_reads_v3', 'pilot_reads_v2', 'pilot_reads_v1')]
    paths = [p for p in paths if p.exists()]
    if len(paths) != 1:
        raise ValueError('Actual paid response does not have one original physical artifact')
    value = read(paths[0])
    with sqlite3.connect('file:' + str(LEDGER) + '?mode=ro', uri=True) as db:
        row = db.execute('SELECT role,purpose,source,status,result FROM calls WHERE id=?', (identity,)).fetchone()
    if not row or row[:4] != ('executor', 'skill_actor', source, 'completed'):
        raise ValueError('Actual response differs from the settled physical ledger identity')
    settled = json.loads(row[4])
    for field in ('request_hash', 'content', 'finish_reason', 'usage'):
        if settled[field] != value[field]:
            raise ValueError('Physical response differs from original ledger content: ' + field)
    return value, {'physical_call_id': identity, 'response_path': str(paths[0].relative_to(ROOT)),
                   'response_sha256': sha(paths[0]), 'actual_physical_ledger_identity_verified': True}


def decode_actual(actual, item, units, locked_plan):
    response, proof = physical_response(actual, item['source'])
    graph, receipt, decoder = None, None, None
    errors = []
    try:
        if response['finish_reason'] != 'stop':
            raise ValueError('Incomplete generation remains unknown; no partial JSON recovery')
        task_path = (ROOT / item['read_path']).with_name('task.json')
        request = read(task_path)
        if request['source'] != item['source'] or request['plan_version'] != item['version']:
            raise ValueError('Read schema does not bind the original fixed source/version')
        raw = json.loads(response['content'], parse_constant=strict_constant)
        jsonschema.validate(raw, request['output_schema'])
        graph, decoder = gi.decode_plan(locked_plan, raw)
        graph, receipt = normalize_graph_evidence(graph, units)
    except (ValueError, KeyError, TypeError, jsonschema.ValidationError) as error:
        errors.append(type(error).__name__ + ': ' + str(error))
        graph = None
    outputs, numeric, closure, consumer_input_sha256 = {}, None, None, None
    if graph is not None:
        normalized, numeric = normalize_numeric_ports(graph)
        consumed, closure = consumer_graph(normalized)
        consumer_input_sha256 = digest(consumed)
        function = contract if item['dataset'] == 'ContractNLI' else maud if item['dataset'] == 'MAUD' else None
        if function:
            outputs = {task: function(consumed, task) for task in item['native_tasks']}
        else:
            outputs = {task: {'handled': False, 'answer': None,
                        'reason': 'Native source-graph adapter still incomplete; no fabricated answer'}
                       for task in item['native_tasks']}
    return {'source': item['source'], 'role': item['role'], 'view': item['view'],
        'plan': item['plan'], 'raw_read_version': item['version'], **proof,
        'old_strict_read_path': item['read_path'], 'old_strict_errors': actual['errors'],
        'old_strict_predictions_preserved': True, 'graph': graph, 'errors': errors,
        'evidence_receipt': receipt, 'original_paired_decoder_receipt': decoder,
        'public_numeric_port_receipt': numeric, 'public_consumer_port_receipt': closure,
        'native_consumer_input_graph_sha256': consumer_input_sha256,
        'native_consumer_outputs_before_grading': outputs, 'native_grading_opened': False,
        'source_semantic_truth_not_certified_by_metadata_checks': True,
        'new_model_requests': 0, 'new_independent_trial_claimed': False}


def run():
    original = capture()
    lock, reader = read(BASE / 'pilot_lock.json'), read(BASE / 'pilot_reads_v3/protocol.json')
    paths = [Path(__file__).relative_to(ROOT), Path('experiments/two_method_graph_corpus.py'),
             *[Path('legal_skill_guard/paired_interfaces') / f for f in (
                 'graph_evidence.py', 'graph_pairs.py', 'empirical_channel.py', 'graph_matching.py',
                 'graph_interface.py', 'structural_channel.py', 'numeric_ports.py',
                 'consumer_graph_contract.py', 'public_graph_ports.py', 'legal_consumers.py')]]
    source_binding = {str(p): sha(ROOT / p) for p in paths}
    binding = {'source_sha256': source_binding, 'reader_protocol_sha256': sha(BASE / 'pilot_reads_v3/protocol.json'),
        'executor': reader['executor'], 'source_only_no_labels': True,
        'decoder': 'verbatim_pointer_and_nonconflicting_display_gloss_v1',
        'no_semantic_value_status_scope_or_inventory_repair': True,
        'structure_evaluation_references_not_opened': True, 'new_model_requests': 0}
    out = BASE / 'source_graph_postprocessing_v1' / digest(binding)
    immutable_json(out / 'protocol.json', binding)
    for path in paths:
        dest = out / 'source_snapshot' / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        body = (ROOT / path).read_bytes()
        if dest.exists() and dest.read_bytes() != body:
            raise ValueError('An immutable postprocessing source snapshot changed')
        if not dest.exists():
            dest.write_bytes(body)
    train = {s['key']: s for s in read(ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
    corpus = {k: deepcopy(v) for k, v in original.items() if k not in ('inventory', 'pairs')}
    corpus.update(protocol='audited-real-train-pairs-source-evidence-v1', inventory=[], pairs=[],
                  original_strict_corpus_preserved=True, postprocessing_protocol_sha256=sha(out / 'protocol.json'))
    originals = {(p['source'], p['view'], p['version']): p for p in original['pairs']}
    processed = []
    for item in original['inventory']:
        candidate = deepcopy(item)
        raw_version = item['version']
        candidate.update(raw_read_version=raw_version, version=digest({
            'raw_wire_version': raw_version, 'executor': reader['executor'],
            'postprocessing_binding': binding, 'decoder_applied': item['dataset'] != 'RuleArena_Airline'}))
        corpus['inventory'].append(candidate)
        if item['dataset'] == 'RuleArena_Airline':
            previous = originals.get((item['source'], item['view'], raw_version))
            if previous is not None:
                value = deepcopy(previous)
                value.update(candidate)
                value['pair']['plan_version'] = candidate['version']
                corpus['pairs'].append(value)
            continue  # Production port decoder has its own existing evidence binder.
        if not item['read_settled']:
            continue
        task, mapping = inputs(train[item['source']])
        units = next(v['source_units'] for v in task['views'] if v['view_id'] == item['view'])
        actual = read(ROOT / item['read_path'])
        plan = next(p for p in lock['plans'][item['dataset']] if p['name'] == item['plan'])
        result = decode_actual(actual, item, units, plan)
        immutable_json(out / 'reads' / (digest([item['source'], item['view'], raw_version]) + '.json'), result)
        processed.append(result)
        if not item['reference_reviewed']:
            continue
        audit = read(ROOT / item['audit_path'])
        reference, ref_receipt = normalize_graph_evidence(audit['graph'], units)
        pair, alignment = pair_from_audited_reference(reference, result['graph'], units,
            source=item['source'], role=item['role'], version=candidate['version'], context=item['context'],
            provenance=digest({'source_audit': item['audit_sha256'], 'physical_read': result['physical_call_id'],
                               'postprocessing_protocol': sha(out / 'protocol.json')}),
            semantic_reference_verified=True, observation_errors=result['errors'])
        corpus['pairs'].append({**candidate, 'pair': serialize_pair(pair), 'alignment': alignment,
            'reference_evidence_receipt': ref_receipt,
            'reference_native_consumer_domain': consumer_signature(pair.reference, item['dataset'], item['native_tasks']),
            'postprocessed_read_path': str((out / 'reads' / (digest([item['source'], item['view'], raw_version]) + '.json')).relative_to(ROOT))})
    target = out / 'corpus_snapshots' / digest(corpus)
    for name, expected in source_binding.items():
        if sha(ROOT / name) != expected:
            raise ValueError('Postprocessing source changed during this immutable capture: ' + name)
    immutable_json(target / 'corpus.json', corpus)
    fitted = fit_complete_groups(corpus)
    immutable_json(target / 'fitted_channels.json', fitted)
    summary = {'artifact_root': str(out.relative_to(ROOT)), 'corpus_snapshot': str(target.relative_to(ROOT)),
        'processed_actual_reads': len(processed), 'source_metadata_valid_reads': sum(r['graph'] is not None for r in processed),
        'audited_actual_pairs': len(corpus['pairs']),
        'unknown_observation_pairs': sum('unknown_observation' in r['alignment'] for r in corpus['pairs']),
        'native_views_executed_without_grading': sum(v['handled'] for r in processed for v in r['native_consumer_outputs_before_grading'].values()),
        'ready_groups': sum(g['all_locked_development_and_calibration_inputs_ready'] for g in fitted['groups']),
        'fitted_groups': sum(bool(g.get('fitted')) for g in fitted['groups']),
        'old_failures_preserved': True, 'structure_evaluation_truth_opened': False, 'new_model_requests': 0}
    immutable_json(target / 'summary.json', summary)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    run()
