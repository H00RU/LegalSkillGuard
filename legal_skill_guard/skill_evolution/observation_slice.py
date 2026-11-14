"""Compile a factual field read through an existing learned binding program.

The current implementation handles the actual single-view, one-array actions
in the TRAIN frontier. Unsupported lenses remain explicit; no source fact,
role inversion, confidence flag or native answer is synthesized here.
"""
import ast
from copy import deepcopy
import json

import jsonschema

from .case_observation_contract import checked_witnesses, validate_adapter
from .kernel_residual import trace_program, dependency_paths
from .native import record_schema
from .objects import digest


def resolve(root, path):
    node = root
    for part in path:
        while '$ref' in node:
            ref = node['$ref']
            if not ref.startswith('#/'):
                raise ValueError('Only local observation schema references are supported')
            node = root
            for key in ref[2:].split('/'):
                node = node[key.replace('~1', '/').replace('~0', '~')]
        node = node['items'] if isinstance(part, int) else node['properties'][part]
    return node


def compile_field_read(contract, kernel, public, observation, port):
    if port not in json.loads(kernel['input_fields_json']):
        raise ValueError('Residual asks an undeclared legal input')
    program = contract['binding_program']
    validate_adapter(program)
    tree = ast.parse(program)
    parent = {id(child): node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    bound_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if isinstance(key, ast.Constant) and key.value == 'inputs' and isinstance(value, ast.Name):
                    bound_names.add(value.id)
    candidates = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if (isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name)
                    and target.value.id in bound_names and isinstance(target.slice, ast.Constant)
                    and target.slice.value == port):
                ancestor = parent.get(id(node))
                while ancestor is not None and not isinstance(ancestor, ast.If):
                    ancestor = parent.get(id(ancestor))
                if ancestor is not None:
                    candidates.append((node, ancestor))
    if len(candidates) != 1:
        raise ValueError('No unique guarded observation-to-port lens in this adapter')
    assignment, guard = candidates[0]
    traced = trace_program(program, {'kernel': kernel,
        'public_case': {'facts': public['facts'], 'question': public['question']},
        'literal_context': {}, 'observation': observation})
    guard_events = [e for e in traced['events'] if e['kind'] == 'guard'
        and traced['source_nodes'][e['source_id']]['line'] == guard.test.lineno
        and traced['source_nodes'][e['source_id']]['expression'] == ast.unparse(guard.test)]
    if len(guard_events) != 1:
        raise ValueError('Lens requires one actual coherent observation view')
    _, paths = dependency_paths(traced, [guard_events[0]['id']], control_dependencies=False)
    paths = [p[1:] for p in paths if p and p[0] == 'observation']
    # Keep the concrete most-specific source observation path, not its enclosing
    # root/list aliases. Actual source evidence remains a separate required field.
    leaves = [p for p in paths if not any(len(q) > len(p) and q[:len(p)] == p for q in paths)]
    if len(leaves) != 1:
        raise ValueError('The residual lens is not a single factual field')
    path = leaves[0]
    schema_root = json.loads(contract['observation_schema_json'])
    value_schema = deepcopy(resolve(schema_root, path))
    kinds = value_schema.get('type', [])
    if isinstance(kinds, str):
        kinds = [kinds]
    if 'array' not in kinds:
        raise ValueError('Explicit finite absence is supported only for an array fact channel')
    value_schema['type'] = 'array'
    witnesses = {'type': 'array', 'items': record_schema({
        'field': {'type': 'string', 'enum': ['facts', 'question']}, 'quote': {'type': 'string'}})}
    schema = {'oneOf': [record_schema({'status': {'type': 'string', 'enum': [status]},
        'value': value_schema if status == 'records' else {'type': 'null'},
        'witnesses': {**witnesses, 'minItems': 0 if status == 'unread' else 1}})
        for status in ('records', 'none_stated', 'unread')]}
    for key in ('$defs', 'definitions'):
        if key in schema_root:
            schema[key] = deepcopy(schema_root[key])
    jsonschema.Draft202012Validator.check_schema(schema)
    prompt = contract['observation_prompt'] + '\nRead ONLY this source factual channel: ' + json.dumps(path) + '''.
Read the complete supplied finite case text. Return records with verbatim case
witnesses when such facts are stated. Return none_stated when this finite text
contains no matching statement, with a quote of the current text inspected;
that is textual absence, not a real-world negative. unread means extraction
unknown/failed. For none_stated/unread value is null. Never answer the legal
claim, invent a date/actor, or silently treat unread as an empty record set.
'''
    return {'port': port, 'observation_path': path, 'schema': schema, 'prompt': prompt,
        'binding_assignment': {'line': assignment.lineno, 'expression': ast.unparse(assignment)},
        'actual_guard': {'line': guard.test.lineno, 'expression': ast.unparse(guard.test), 'truth': guard_events[0]['truth']},
        'kernel_sha256': digest(kernel), 'binding_program_sha256': digest(program),
        'native_labels_or_factual_completion_used': False}


def merge_field_read(observation, action, read, public):
    jsonschema.validate(read, action['schema'])
    updated = deepcopy(observation)
    if read['status'] == 'unread':
        return updated
    checked_witnesses(read['witnesses'], public)
    path = action['observation_path']
    target = updated
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = [] if read['status'] == 'none_stated' else deepcopy(read['value'])
    # In the actual frontier schema, witnesses live beside this factual channel.
    if not isinstance(target, dict) or 'witnesses' not in target:
        raise ValueError('No declared sibling witness field for this observation lens')
    target['witnesses'].extend(deepcopy(read['witnesses']))
    return updated
