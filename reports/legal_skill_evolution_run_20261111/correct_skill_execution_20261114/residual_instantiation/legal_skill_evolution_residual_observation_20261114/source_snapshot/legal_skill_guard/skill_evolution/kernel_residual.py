"""Identify factual input dependencies of an actual unhandled kernel return.

This is a dynamic dependency slice, not symbolic completion, semantic coverage
certification or a claim to a globally minimal factual question. No missing
value is filled and no native label enters the analysis.
"""
import ast
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

from .objects import digest
from .span_compiler import validate_procedure


def trace_program(program, inputs, premises=None):
    # The current frontier kernels are single-entry modules. More elaborate
    # learned source/consumer modules retain their existing execution paths.
    validate_procedure(program, allow_helpers=False)
    request = {'program': program, 'inputs': deepcopy(inputs), 'premises': deepcopy(premises or {})}
    worker = Path(__file__).with_name('kernel_residual_worker.py')
    call = subprocess.run([sys.executable, '-I', '-S', str(worker)], input=json.dumps(request),
        text=True, capture_output=True, timeout=5, cwd='/tmp', env={'LANG': 'C.UTF-8'}, close_fds=True)
    if call.returncode:
        raise ValueError('Residual instrumentation failed: ' + call.stderr[-1600:])
    return json.loads(call.stdout)


def dependency_paths(traced, indices, *, control_dependencies=True):
    todo = list(indices); reached = set(); paths = []
    while todo:
        index = todo.pop()
        if index in reached:
            continue
        reached.add(index); event = traced['events'][index]
        todo.extend(event['parents'] if control_dependencies else event['data_parents'])
        for path in event['input_paths']:
            if path not in paths:
                paths.append(path)
    return reached, paths


def execution_residual(kernel, binding):
    traced = trace_program(kernel['program'], binding, kernel.get('premises', {}))
    events = traced['events']
    returns = [e for e in events if e['kind'] == 'return']
    if not returns:
        raise ValueError('No actual kernel return in residual trace')
    reached, paths = dependency_paths(traced, [returns[-1]['id']])
    causes = list(returns[-1]['controls'][-1:])
    # Kernels commonly record an unread channel in a boolean such as uncertain.
    # Follow the executed definition, not all possible assignments in the code.
    if causes:
        guard = events[causes[0]]
        expression = ast.parse(traced['source_nodes'][guard['source_id']]['expression'], mode='eval').body
        if isinstance(expression, (ast.Name, ast.UnaryOp)) and len(guard['data_parents']) == 1:
            definition = events[guard['data_parents'][0]]
            source = ast.parse(traced['source_nodes'][definition['source_id']]['expression']).body[0]
            if (isinstance(source, ast.Assign) and isinstance(source.value, ast.Constant)
                    and type(source.value.value) is bool and definition['controls']):
                controls = definition['controls']
                causes = [controls[-1]]
                # An elif/else chain may require both an absent bound and a
                # false continuation flag. Keep preceding false guards.
                if not events[controls[-1]]['truth']:
                    for identity in reversed(controls[:-1]):
                        if events[identity]['truth']:
                            break
                        causes.append(identity)
    _, cause_paths = dependency_paths(traced, causes, control_dependencies=False)
    unresolved_paths = []
    for path in paths:
        value = binding
        present = True
        try:
            for key in path:
                value = value[key]
        except (KeyError, IndexError, TypeError):
            value = None; present = False
        if not present or value is None:
            unresolved_paths.append({'path': path, 'present': present, 'value': value})
    guards = [{**e, **traced['source_nodes'][e['source_id']]} for e in events
        if e['id'] in reached and e['kind'] == 'guard']
    if traced['result'].get('handled') is True:
        causes, cause_paths, unresolved_paths = [], [], []
    return {'kernel_sha256': digest(kernel), 'binding_sha256': digest(binding),
        'actual_execution': traced['result'], 'dependent_input_paths': paths,
        'unresolved_input_paths': unresolved_paths, 'guards': guards,
        'return_cause_input_paths': cause_paths,
        'return_cause_guards': [{**events[i], **traced['source_nodes'][events[i]['source_id']]} for i in causes],
        'trace_events': len(events), 'factual_values_unchanged': True,
        'not_a_semantic_certificate_or_globally_minimal_read': True,
        'no_legal_rule_or_factual_completion_added': True}
