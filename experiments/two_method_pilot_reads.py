"""Run the locked TRAIN pilot readers with original physical request accounting.

The native question/answer is not an extraction input. All three read versions
were fixed before the first annotation call. Failed reads remain failed; this
driver neither changes candidates nor automatically retries them.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3

import jsonschema

from experiments.two_method_annotate import inputs
from legal_skill_guard.paired_interfaces import airline_interfaces
from legal_skill_guard.paired_interfaces import graph_interface as gi
from legal_skill_guard.paired_interfaces.consumer_graph_contract import consumer_graph
from legal_skill_guard.paired_interfaces.graph_contracts import compile_weight_contract
from legal_skill_guard.paired_interfaces.graph_prompt import schema_visible_plan
from legal_skill_guard.paired_interfaces.legal_consumers import contract, maud
from legal_skill_guard.paired_interfaces.native_adapters import run_airline
from legal_skill_guard.paired_interfaces.numeric_ports import normalize_numeric_ports
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/two_method_followthrough_20261116'
OUT = BASE / 'pilot_reads_v3'
LEDGER = ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare():
    lock = read(BASE / 'pilot_lock.json')
    # Preserve all three locked candidates and their precomputed codebooks.
    # The residual candidate's existing alphabet must also be its wire grammar.
    lock['plans'] = {d: [schema_visible_plan(p) for p in (
        airline_interfaces.compile_plans(plans) if d == 'RuleArena_Airline'
        else [compile_weight_contract(p) for p in plans])]
        for d, plans in lock['plans'].items()}
    sources = read(BASE / 'prepared/source_lock.json')
    train_path = ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'
    train = {r['key']: r for r in read(train_path)}
    if sha(train_path) != sources['prepared_sha256']['train']['public']:
        raise ValueError('Original TRAIN changed')
    paths = list(read(BASE / 'annotation_v1/protocol.json')['source_sha256'])
    paths += ['experiments/two_method_pilot_reads.py', 'legal_skill_guard/rr/client.py',
        'legal_skill_guard/paired_interfaces/graph_prompt.py',
        'legal_skill_guard/paired_interfaces/graph_contracts.py',
        'legal_skill_guard/paired_interfaces/airline_interfaces.py',
        'legal_skill_guard/paired_interfaces/numeric_ports.py',
        'legal_skill_guard/paired_interfaces/consumer_graph_contract.py',
        'legal_skill_guard/paired_interfaces/native_adapters.py',
        'history/rr_v2_20261106/data/cache/rr_v2/RuleArena/airline/gen_questions.py']
    bindings = {p: sha(ROOT / p) for p in paths}
    for path, expected in lock['initial_implementation_sha256'].items():
        if bindings[path] != expected:
            raise ValueError('A pilot implementation amendment is needed before using changed code')
    for path in paths:
        target = OUT / 'source_snapshot' / path
        target.parent.mkdir(parents=True, exist_ok=True)
        raw = (ROOT / path).read_bytes()
        if target.exists() and target.read_bytes() != raw:
            raise FileExistsError('Pilot reader snapshot changed: ' + path)
        if not target.exists():
            target.write_bytes(raw)
    protocol = {'run_id': 'two_method_pilot_reads_v3_20261117',
        'pilot_lock_sha256': sha(BASE / 'pilot_lock.json'),
        'source_lock_sha256': sha(BASE / 'prepared/source_lock.json'),
        'source_sha256': bindings, 'executor': lock['executor'],
        'read_versions': {d: [p['version'] for p in plans] for d, plans in lock['plans'].items()},
        'actor_input': 'one current opaque source view and exact fixed output schema; no question, labels, reference graph or other view',
        'full_prompt_semantics': 'locked system plus exact schema advertisement; JSON source_units only',
        'post_read_consumption': 'fixed graph consumers; unresolved never becomes an invented answer',
        'execution_order': 'all four locked Airline mothers first for the required M1 native integration, then other fixed sources by role and key; no cohort change',
        'no_hidden_retries': True, 'model_parameter_updates': False,
    }
    old_protocol = read(BASE / 'pilot_reads_v2/protocol.json')
    if protocol['executor'] != old_protocol['executor']:
        raise ValueError('Transport correction cannot change the executor profile')
    for dataset, versions in old_protocol['read_versions'].items():
        unchanged = () if dataset == 'RuleArena_Airline' else range(3)
        if any(protocol['read_versions'][dataset][i] != versions[i] for i in unchanged):
            raise ValueError('The port contract repair unexpectedly changed another reading candidate')
    amendment = {'reason': 'The generic Airline ontology did not recover the existing seven-port program baseline. Compile the same three operator families from the frozen signature, including its already generated weight alphabet; normalize public consumer port serializations.',
        'prior_protocol_sha256': sha(BASE / 'pilot_reads_v2/protocol.json'),
        'prior_driver_snapshot_sha256': sha(BASE / 'pilot_reads_v2/source_snapshot/experiments/two_method_pilot_reads.py'),
        'pilot_lock_sha256': protocol['pilot_lock_sha256'],
        'candidate_count_per_module_unchanged': True, 'source_cohort_and_roles_unchanged': True,
        'Airline_wire_schemas_replaced_to_implement_original_program_ports': True,
        'old_generic_Airline_runs_are_integration_evidence_not_complete_method_trials': True,
        'new_transform_families_added': False,
        'legal_programs_and_paired_weight_groups_unchanged': True, 'executor_profile_unchanged': True,
        'numeric_serialization_normalization_applied_equally': True,
        'definition_local_standards_and_explicit_recipient_membership_closure_shared_by_all_arms': True,
        'numeric_values_not_inferred_from_quotes_labels_or_defaults': True,
        'unchanged_wire_versions_reuse_original_v2_physical_requests': True,
        'new_read_versions': protocol['read_versions'],
        'old_physical_failures_and_costs_preserved': True,
        'changed_weight_schema_observations_not_pooled_with_v2_for_channel_calibration': True,
        'new_driver_source_sha256': sha(Path(__file__))}
    immutable_json(OUT / 'transport_amendment.json', amendment)
    immutable_json(OUT / 'protocol.json', protocol)
    return protocol, lock, sources, train


def consume(source, opaque, mapping, graph, units, modules):
    results = {}
    for view in source['views']:
        if mapping[view['id']] != opaque:
            continue
        if source['dataset'] == 'ContractNLI':
            result = contract(graph, view['id'])
        elif source['dataset'] == 'MAUD':
            result = maud(graph, view['id'])
        elif source['dataset'] == 'RuleArena_Airline':
            result = run_airline(graph, units, modules['RuleArena_Airline']['sha256'])
        else:
            result = {'handled': False, 'answer': None,
                      'reason': 'native graph-to-preserved-module adapter not yet run'}
        results[view['id']] = result
    return results


def run(stop_after=None, source_prefix=None):
    protocol, lock, source_lock, train = prepare()
    for path, expected in protocol['source_sha256'].items():
        if sha(ROOT / path) != expected:
            raise ValueError('Frozen pilot source changed before dispatch')
    with sqlite3.connect('file:' + str(LEDGER) + '?mode=ro', uri=True) as db:
        if db.execute("select count(*) from calls where status='reserved'").fetchone()[0]:
            raise RuntimeError('Existing request must settle before pilot reads')
    ledger = EvolutionLedger(LEDGER, run_id=protocol['run_id'], sources=source_lock['sources'],
        binding={'phase': 'fixed_pilot_reads', 'protocol_sha256': sha(OUT / 'protocol.json')})
    executor = FrozenExecutor(ledger, OUT, protocol['executor'])
    executor.exact_replay_roots = (BASE / 'pilot_reads_v2',)
    order = sorted(lock['rows'], key=lambda r: (
        0 if r['dataset'] == 'RuleArena_Airline' else 1,
        0 if r['dataset'] == 'ContractNLI' and r['role'] == 'development' else 1,
        {'development': 0, 'calibration': 1, 'structure_evaluation': 2}[r['role']], r['key']))
    attempted = 0
    for row in order:
        if source_prefix and not row['key'].startswith(source_prefix):
            continue
        source = train[row['key']]
        if digest(source) != row['public_sha256']:
            raise ValueError('Locked pilot source changed')
        task, mapping = inputs(source)
        for view in task['views']:
            for plan in lock['plans'][row['dataset']]:
                request_key = digest([row['key'], view['view_id'], plan['version']])
                output = OUT / 'reads' / request_key / 'decoded.json'
                if output.exists():
                    continue
                messages = [{'role': 'system', 'content': plan['system']},
                    {'role': 'user', 'content': json.dumps({'source_units': view['source_units']}, ensure_ascii=False, sort_keys=True)}]
                metadata = {'source': row['key'], 'role': row['role'], 'opaque_source_view': view['view_id'],
                    'native_view_to_opaque_source_view': mapping, 'plan': plan['name'],
                    'plan_version': plan['version'], 'messages': messages, 'output_schema': plan['schema']}
                immutable_json(output.with_name('task.json'), metadata)
                call_id = protocol['run_id'] + ':read:' + request_key
                print(json.dumps({'event': 'read_dispatch', 'source': row['key'],
                                  'plan': plan['name'], 'opaque_view': view['view_id']}), flush=True)
                response = executor.generate(call_id, source=row['key'], purpose='skill_actor',
                    messages=messages, thinking=False, schema=plan['schema'])
                graph, raw_value, receipt, checks = None, None, None, None
                errors = []
                if response['finish_reason'] != 'stop':
                    errors.append('Non-stop generation finish: ' + str(response['finish_reason']))
                try:
                    raw_value = json.loads(response['content'])
                    jsonschema.validate(raw_value, plan['schema'])
                    graph, receipt = (airline_interfaces.decode(plan, raw_value, view['source_units'])
                        if plan.get('production_decoder') == 'frozen_consumer_port_inventory_v1'
                        else gi.decode_plan(plan, raw_value))
                    checks = gi.validate(graph, view['source_units'])
                except (ValueError, KeyError, TypeError, jsonschema.ValidationError) as error:
                    errors.append(type(error).__name__ + ': ' + str(error))
                native_graph, numeric_receipt = normalize_numeric_ports(graph) if graph is not None else (None, None)
                native_graph, consumer_receipt = consumer_graph(native_graph) if native_graph is not None else (None, None)
                native = consume(source, view['view_id'], mapping, native_graph, view['source_units'], lock['modules']) if native_graph is not None and not errors else {}
                result = {'source': row['key'], 'role': row['role'], 'plan': plan['name'],
                    'plan_version': plan['version'], 'logical_call_id': call_id,
                    'physical_call_id': response.get('reused_physical_call_id', call_id),
                    'exact_physical_response_reused': bool(response.get('reused_physical_call_id')),
                    'opaque_source_view': view['view_id'], 'native_view_to_opaque_source_view': mapping,
                    'raw_graph_encoding': raw_value, 'decoded_graph': graph,
                    'paired_decoder_receipt': receipt, 'source_span_checks': checks,
                    'numeric_port_decoder_receipt': numeric_receipt,
                    'public_consumer_contract_receipt': consumer_receipt,
                    'native_consumer_input_graph_sha256': digest(native_graph),
                    'errors': errors, 'native_consumer_outputs': native,
                    'no_reference_truth_used_for_reading': True,
                    'source_semantic_correctness_not_certified_by_span_checks': True,
                    'token_usage': response['usage'], 'elapsed_seconds': response['elapsed_seconds']}
                immutable_json(output, result)
                print(json.dumps({'event': 'read_settled', 'source': row['key'], 'plan': plan['name'],
                    'valid_source_spans': not errors, 'errors': errors,
                    'native_views_handled': sum(bool(v.get('handled')) for v in native.values())}), flush=True)
                attempted += 1
                if stop_after is not None and attempted >= stop_after:
                    return


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--prepare', action='store_true')
    p.add_argument('--stop-after', type=int)
    p.add_argument('--source-prefix', help='Run an ordered subset of the already locked cohort')
    a = p.parse_args()
    if a.stop_after is not None and a.stop_after < 1:
        p.error('--stop-after must be positive')
    if a.prepare:
        protocol, lock, sources, train = prepare()
        print(json.dumps({'phase': protocol['run_id'], 'pilot_mothers': len(lock['rows']), 'model_calls': 0}))
    else:
        run(a.stop_after, a.source_prefix)


if __name__ == '__main__':
    main()
