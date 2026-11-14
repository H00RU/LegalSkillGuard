"""Resolve actual learned-converter blocking guards back to observation components.

The author legal program is untouched. This is an actual conversion-stage
residual, distinct from a native Prolog proof residual or a truth certificate.
"""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import jsonschema

from .case_observation_contract import apply_adapter, execute_alternatives, validate_adapter
from .literal_facts import literal_bindings
from .objects import digest
from .span_compiler import execute_json


def trace_conversion(contract, kernel, public, observation):
    program = contract['binding_program']
    validate_adapter(program)
    inputs = {'kernel': kernel, 'public_case': {'facts': public['facts'], 'question': public['question']},
        'literal_context': literal_bindings({'public': public}), 'observation': deepcopy(observation)}
    reference = execute_json(program, deepcopy(inputs), {}, allow_helpers=True)
    worker = Path(__file__).with_name('conversion_residual_worker.py')
    result = subprocess.run([sys.executable, '-I', '-S', str(worker)],
        input=json.dumps({'program': program, 'inputs': inputs}), capture_output=True,
        text=True, timeout=6, cwd='/tmp', env={'LANG': 'C.UTF-8'}, close_fds=True)
    if result.returncode:
        raise ValueError('Conversion tracing failed: ' + result.stderr[-1600:])
    traced = json.loads(result.stdout)
    if traced['result'] != reference:
        raise ValueError('Diagnostic changed actual converter output; no read action')
    return traced


def component_action(contract, kernel, public, observation):
    traced = trace_conversion(contract, kernel, public, observation)
    roots = json.loads(contract['observation_schema_json'])['properties']
    selected, paths = [], []
    for write in traced['blocking_writes']:
        for path in write['cause_paths']:
            if len(path) < 2 or path[0] != 'observation' or path[1] not in roots:
                continue
            value = {'observation': observation}
            try:
                for key in path:
                    value = value[key]
            except (KeyError, IndexError, TypeError):
                value = None
            if value is None or value == 'unread':
                if path not in paths:
                    paths.append(path)
                if path[1] not in selected:
                    selected.append(path[1])
    if not selected:
        raise ValueError('No executed unresolved write has a supported unread observation cause')
    schema = {'type': 'object', 'properties': {cid: deepcopy(roots[cid]) for cid in selected},
        'required': selected, 'additionalProperties': False}
    jsonschema.Draft202012Validator.check_schema(schema)
    return {'residual_stage': 'learned_conversion_program', 'component_ids': selected,
        'blocking_observation_paths': paths, 'schema': schema,
        'prompt': contract['observation_prompt'] + '\nThe actual conversion program is blocked on these observation paths: '
            + json.dumps(paths) + '\nRe-read ONLY the selected existing observation components. Return their unchanged schemas. Preserve genuinely unread values; an unmentioned fact is not automatically an unknown or a world-negative. Do not invent facts, clear guards, or answer the legal claim.',
        'trace': traced, 'binding_program_sha256': digest(contract['binding_program']),
        'no_native_label_or_factual_completion': True,
        'not_a_Prolog_proof_trace_or_minimality_certificate': True}


def repair_step(contract, kernel, public, observation, read):
    context = literal_bindings({'public': public})
    grounded = apply_adapter(contract, kernel, public, observation, literal_context=context)
    before = execute_alternatives(kernel, grounded)
    if before['handled']:
        return {'execution': before, 'read_requested': False, 'reason': 'Already handled'}
    action = component_action(contract, kernel, public, observation)
    value, receipt = read(action)
    jsonschema.validate(value, action['schema'])
    updated = deepcopy(observation)
    for component in action['component_ids']:
        updated[component] = deepcopy(value[component])
    jsonschema.validate(updated, json.loads(contract['observation_schema_json']))
    after = apply_adapter(contract, kernel, public, updated, literal_context=context)
    return {'execution': execute_alternatives(kernel, after), 'read_requested': True,
        'action': action, 'observation_after': updated, 'grounded_after': after, 'read_receipt': receipt,
        'residual_stage': 'learned_conversion_program', 'legal_program_and_contract_unchanged': True}
