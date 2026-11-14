"""Offline executable/schema/lineage checks of paid cumulative library proposals."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

import jsonschema

from experiments import legal_skill_evolution_observation_library_train as current
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.case_observation_contract import apply_adapter, execute_alternatives
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.literal_facts import literal_bindings
from legal_skill_guard.skill_evolution.native import record_schema
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.runtime import decoder_schema, render_messages
from legal_skill_guard.skill_evolution.span_compiler import execute_json, validate_procedure


def run(arm, batch):
    protocol, ledger, public, kernels = current.setup()
    library = current.read(current.OUT / f'B{batch}' / arm / 'teacher.json')['value']
    jsonschema.validate(library, current.SCHEMA)
    adaptations = []
    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate schema key; no unambiguous adaptation')
            result[key] = value
        return result
    for component in library['components']:
        text = component['schema_json']
        decoder = json.JSONDecoder(object_pairs_hook=unique_keys)
        value, end = decoder.raw_decode(text)
        suffix = text[end:]
        if suffix:
            # A complete unique-key JSON object followed by exactly one
            # unmatched closing brace: punctuation only, no semantic token.
            assert suffix == '}', 'No deterministic schema punctuation recovery'
            jsonschema.Draft202012Validator.check_schema(value)
            component['schema_json'] = text[:end]
            adaptations.append({'component': component['id'], 'removed_exact_suffix': suffix,
                'before_sha256': digest(text), 'after_sha256': digest(text[:end]),
                'complete_JSON_term_and_all_field_values_unchanged': True})
    components = {c['id']: c for c in library['components']}
    assert len(components) == len(library['components']) and components
    registry = current.read(current.history.OUT / 'observation_component_registry.json')
    task = current.read(current.OUT / f'B{batch}/teacher_task.json')
    prior_ids = set(task.get('parent_component_registry', registry))
    if batch > 1 and 'parent_component_registry' not in task:
        for a in current.ARMS:
            prior_ids.update(c['id'] for c in current.read(current.OUT / f'B{batch-1}' / a / 'library.json')['components'])
    feedback = task['error_feedback_by_id']
    for component in components.values():
        assert set(component['parent_component_ids']) <= prior_ids, component['id']
        assert set(component['error_feedback_ids']) <= set(feedback), component['id']
        jsonschema.Draft202012Validator.check_schema(json.loads(component['schema_json']))
    for key in ('planner_program', 'binding_program'):
        current.validate_adapter(library[key], excluded_source_ids=protocol['sources'])
    folder = current.OUT / f'B{batch}' / arm
    immutable_json(folder / 'schema_compilation_receipt.json', {'adaptations': adaptations,
        'raw_teacher_response_unchanged': True, 'new_model_calls': 0,
        'all_non_schema_fields_unchanged': True, 'no_missing_semantics_invented': True})
    immutable_json(folder / 'library.json', library)
    client = FrozenExecutor(ledger, current.OUT, protocol['executor_profile'])
    rows, grammars = [], {}
    shared_python = '/media/sangfor/vdb/legal-skill-runtime/inference-qwen3-8b-vllm0102/bin/python'
    grammar_code = 'import json,sys,xgrammar; xgrammar.Grammar.from_json_schema(json.dumps(json.load(sys.stdin)))'
    for sid in protocol['sources']:
        if sid not in public:
            continue
        pub, kernel = public[sid]['views'][0]['public'], kernels[sid]
        plan = execute_json(library['planner_program'], {'kernel': kernel, 'public_case': pub}, {}, allow_helpers=True)
        assert set(plan) == {'component_ids'}
        ids = plan['component_ids']
        assert isinstance(ids, list) and len(ids) == len(set(ids)) and set(ids) <= set(components)
        row = {'source': sid, 'actual_planned_components': ids, 'neural_input_tokens': None}
        before = apply_adapter({'binding_program': library['binding_program']}, kernel, pub, None,
            literal_context=literal_bindings({'public': pub}))
        row['before_neural'] = {'grounded': before, 'execution': execute_alternatives(kernel, before)}
        if ids:
            schema = record_schema({cid: json.loads(components[cid]['schema_json']) for cid in ids})
            jsonschema.Draft202012Validator.check_schema(schema)
            wire = decoder_schema(schema)[0]
            key = digest(wire)
            if key not in grammars:
                check = subprocess.run([shared_python, '-c', grammar_code], input=json.dumps(wire),
                    text=True, capture_output=True, timeout=45)
                assert check.returncode == 0, check.stderr[-1800:]
                grammars[key] = {'schema_sha256': key, 'actual_serving_grammar_compiles': True}
            prompt = '\n\n'.join(components[cid]['prompt'] for cid in ids)
            messages = render_messages(prompt, {'current_case': pub, 'unchanged_legal_program': kernel,
                'component_meanings': {cid: components[cid]['meaning'] for cid in ids}}, schema)
            count = client.tokenize(messages, thinking=False)['count']
            assert count + protocol['executor_profile']['max_tokens'] <= protocol['executor_profile']['context_tokens']
            row['neural_input_tokens'] = count
        rows.append(row)
    receipt = {'arm': arm, 'batch': batch, 'library_sha256': digest(library),
        'rows': rows, 'serving_grammars': list(grammars.values()), 'new_model_generation_requests': 0,
        'components': len(components), 'sources_with_no_planned_channel': sum(not r['actual_planned_components'] for r in rows),
        'checks_do_not_prove_source_truth_or_method_novelty': True}
    immutable_json(current.OUT / f'B{batch}' / arm / 'unbound_library_preflight.json', receipt)
    print(json.dumps({k: receipt[k] for k in ('arm', 'batch', 'components', 'sources_with_no_planned_channel', 'new_model_generation_requests')}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--arm', choices=current.ARMS, required=True)
    parser.add_argument('--batch', type=int, choices=range(1, 9), default=1)
    args = parser.parse_args()
    run(args.arm, args.batch)
