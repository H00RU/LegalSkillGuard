"""Prepare/tokenize the complete TRAIN128 fixed reader inventory, without generation.

Three existing candidate families, original eight batches and frozen Qwen
profile. OE uses the versioned frozen-program ports; unchanged other-library
requests identify exact paid pilot reuse. No DEV/TEST content or grading is
opened. This preflight is not a claim that formal training has started.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

import jsonschema

from experiments.two_method_annotate import inputs
from experiments.two_method_graph_corpus import BASE, ROOT, read, sha
from legal_skill_guard.paired_interfaces import airline_interfaces, asset_interfaces
from legal_skill_guard.paired_interfaces.graph_contracts import compile_weight_contract
from legal_skill_guard.paired_interfaces.graph_prompt import schema_visible_plan
from legal_skill_guard.rr.client import ExecutorClient, request_payload
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


def prepare():
    lock_path, source_path = BASE / 'pilot_lock.json', BASE / 'prepared/source_lock.json'
    lock, source_lock = read(lock_path), read(source_path)
    public_path = ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'
    if sha(public_path) != source_lock['prepared_sha256']['train']['public']:
        raise ValueError('The locked original TRAIN public input changed')
    train = {source['key']: source for source in read(public_path)}
    batches = source_lock['training_batches']
    order = [key for batch in batches for key in batch]
    if len(batches) != 8 or len(order) != 128 or len(set(order)) != 128 or set(order) != set(train):
        raise ValueError('Use exactly the original128 mothers/eight batches')
    reader = read(BASE / 'pilot_reads_v3/protocol.json')
    if reader['executor'] != lock['executor'] or reader['executor']['enable_thinking'] is not False:
        raise ValueError('The original thinking-OFF execution profile changed')
    plans = {}
    for dataset, candidates in lock['plans'].items():
        if dataset == 'OpenExempt':
            continue
        compiled = (airline_interfaces.compile_plans(candidates) if dataset == 'RuleArena_Airline'
                    else [compile_weight_contract(plan) for plan in candidates])
        plans[dataset] = [schema_visible_plan(plan) for plan in compiled]
        if [plan['version'] for plan in plans[dataset]] != reader['read_versions'][dataset]:
            raise ValueError('An unchanged-library reader silently changed version')
    asset_plans = {regime: [schema_visible_plan(plan) for plan in asset_interfaces.compile_plans(
                   lock['plans']['OpenExempt'], regime)]
                   for regime in asset_interfaces.regimes(asset_interfaces.frozen_skill())}
    requests, schemas = [], {}
    for batch, keys in enumerate(batches, 1):
        for key in keys:
            source = train[key]
            task, mapping = inputs(source)
            native = {view['id']: view for view in source['views']}
            for view in task['views']:
                data = {'source_units': view['source_units']}
                if source['dataset'] == 'OpenExempt':
                    contexts = [asset_interfaces.context_from_public(native[name]['public'])
                                for name, opaque in mapping.items() if opaque == view['view_id']]
                    if len({digest(context) for context in contexts}) != 1:
                        raise ValueError('Equal facts have incompatible supplied public contexts')
                    data['public_context'] = contexts[0]
                    if not contexts[0]['supported_by_frozen_legal_program']:
                        # Keep every logical task in evaluation denominators,
                        # but never spend a read on a known law-domain refusal.
                        # This is not an observed decoder/model abstention.
                        for original in lock['plans']['OpenExempt']:
                            requests.append({'source': key, 'dataset': source['dataset'], 'batch': batch,
                                'opaque_view': view['view_id'], 'plan': original['name'],
                                'version': digest(['declared_legal_domain_refusal', original['version'], contexts[0]]),
                                'messages': [], 'schema': None, 'wire_payload_sha256': None,
                                'existing_paid_pilot_physical_call_id': None, 'thinking': False,
                                'dispatch_supported': False, 'pre_generation_unsupported': True,
                                'public_context': contexts[0],
                                'reason': 'Explicit public regime is outside the audited frozen legal program domain',
                                'not_a_model_abstention_or_physical_trial': True})
                        continue
                    candidates = asset_plans[contexts[0]['governing_regime']]
                else:
                    candidates = plans[source['dataset']]
                for plan in candidates:
                    jsonschema.Draft202012Validator.check_schema(plan['schema'])
                    schemas.setdefault(digest(plan['schema']), plan['schema'])
                    messages = [{'role': 'system', 'content': plan['system']},
                        {'role': 'user', 'content': json.dumps(data, ensure_ascii=False, sort_keys=True)}]
                    wire = request_payload(reader['executor'], messages=messages, thinking=False, schema=plan['schema'])
                    cached = BASE / 'pilot_reads_v3/reads' / digest([key, view['view_id'], plan['version']])
                    old_task = read(cached / 'task.json') if (cached / 'task.json').exists() else None
                    reuse = None
                    if old_task is not None:
                        old = read(cached / 'decoded.json')
                        if (old_task['messages'] != messages or old_task['output_schema'] != plan['schema']
                                or old['source'] != key or old['plan_version'] != plan['version']):
                            raise ValueError('A pilot reuse has different actual request inputs')
                        reuse = old['physical_call_id']
                    requests.append({'source': key, 'dataset': source['dataset'], 'batch': batch,
                        'opaque_view': view['view_id'], 'plan': plan['name'], 'version': plan['version'],
                        'messages': messages, 'schema': plan['schema'], 'wire_payload_sha256': digest(wire),
                        'existing_paid_pilot_physical_call_id': reuse, 'thinking': False,
                        'dispatch_supported': True, 'pre_generation_unsupported': False})
    if len(requests) != 624:
        raise ValueError('The complete TRAIN source-view/three-plan inventory changed')
    paths = [Path(__file__).relative_to(ROOT), 'experiments/two_method_annotate.py',
             'legal_skill_guard/paired_interfaces/asset_interfaces.py',
             'legal_skill_guard/paired_interfaces/program_residual.py',
             'legal_skill_guard/paired_interfaces/airline_interfaces.py',
             'legal_skill_guard/paired_interfaces/graph_interface.py',
             'legal_skill_guard/paired_interfaces/graph_contracts.py',
             'legal_skill_guard/paired_interfaces/graph_prompt.py', 'legal_skill_guard/rr/client.py']
    protocol = {'experiment': 'complete_TRAIN128_formal_fixed_reader_preflight_v1',
        'source_sha256': {str(path): sha(ROOT / path) for path in paths},
        'pilot_lock_sha256': sha(lock_path), 'source_lock_sha256': sha(source_path),
        'TRAIN_public_sha256': sha(public_path), 'executor': reader['executor'],
        'requests_sha256': digest(requests), 'schema_inventory_sha256': digest(schemas),
        'source_mothers': 128, 'batches': 8, 'candidate_families_per_dataset': 3,
        'new_OE_port_version_not_pooled_with_old_generic_read_channels': True,
        'no_evaluation_data_or_labels_opened': True, 'generation_requests': 0,
        'formal_training_or_goal_completion_claimed': False}
    out = BASE / 'formal_read_preflight_v1' / digest(protocol)
    immutable_json(out / 'protocol.json', protocol)
    immutable_json(out / 'requests.json', requests)
    immutable_json(out / 'schemas.json', schemas)
    immutable_json(out / 'plan_assets.json', {'unchanged_libraries': plans, 'OE_by_public_regime': asset_plans})
    return out, protocol, requests, schemas


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tokenize', action='store_true')
    args = parser.parse_args()
    out, protocol, requests, schemas = prepare()
    report = {'mothers': 128, 'batches': 8, 'logical_read_requests': len(requests),
        'unique_schemas': len(schemas), 'per_dataset': dict(Counter(row['dataset'] for row in requests)),
        'existing_paid_pilot_reads_identified': sum(bool(row['existing_paid_pilot_physical_call_id']) for row in requests),
        'OE_logical_read_slots': sum(row['dataset'] == 'OpenExempt' for row in requests),
        'supported_generation_slots': sum(row['dispatch_supported'] for row in requests),
        'pre_generation_domain_refusals': sum(row['pre_generation_unsupported'] for row in requests),
        'unhandled_tasks_not_removed_from_native_evaluation_denominators': True,
        'generation_requests': 0, 'training_started': False,
        'reference_reviews_M2_graph_adaptation_and_formal_arms_not_certified_by_this_preflight': True}
    if args.tokenize:
        client = ExecutorClient(None, out, protocol['executor'])
        report['readiness'] = client.readiness()
        counts = []
        for index, row in enumerate(requests):
            if not row['dispatch_supported']:
                continue
            value = client.tokenize(row['messages'], thinking=False)
            counts.append({'source': row['source'], 'view': row['opaque_view'], 'plan': row['plan'],
                'input_tokens': value['count'], 'input_plus_reserved_output': value['count'] + protocol['executor']['max_tokens'],
                'within_original_context': value['count'] + protocol['executor']['max_tokens'] <= protocol['executor']['context_tokens'],
                'serving_template_token_sha256': digest(value['tokens'])})
            if (index + 1) % 96 == 0:
                print(json.dumps({'event': 'read_only_tokenization_progress', 'completed': index + 1, 'total': len(requests)}), flush=True)
        report['all_within_original_context'] = all(row['within_original_context'] for row in counts)
        report['max_input_plus_reserved_output'] = max(row['input_plus_reserved_output'] for row in counts)
        immutable_json(out / 'tokenization.json', {'counts': counts, **report})
    immutable_json(out / ('tokenized_summary.json' if args.tokenize else 'prepared_summary.json'), report)
    print(json.dumps({'artifact_root': str(out.relative_to(ROOT)), **report}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
