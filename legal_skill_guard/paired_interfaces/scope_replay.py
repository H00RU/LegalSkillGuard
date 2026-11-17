"""Offline SCOPE attribution using recorded weak labels and pure composition.

An alternative label is an intervention, never a new weak-model observation.
Previously unobserved predicate inputs are unsupported, including inputs on a
new branch. Frozen deterministic legal tools may be evaluated on new inputs.
"""
from copy import deepcopy
from itertools import combinations
import json
import select
import subprocess
import sys

import jsonschema

from legal_skill_guard.paired_interfaces.control_programs import validate_program
from legal_skill_guard.skill_evolution.objects import digest


def _replace(value, path, replacement):
    result = deepcopy(value)
    if not path:
        return deepcopy(replacement)
    parent = result
    for key in path[:-1]:
        parent = parent[key]
    parent[path[-1]] = deepcopy(replacement)
    return result


def label_mutations(schema, value, path=()):
    """Enumerate finite label-leaf changes; do not invent numbers or spans."""
    if 'enum' in schema or 'const' in schema or schema.get('type') == 'boolean':
        labels = schema.get('enum', [schema['const']] if 'const' in schema else [False, True])
        for label in labels:
            if digest(label) != digest(value):
                yield {'path': list(path), 'value': label}
        return
    for branch in schema.get('anyOf', schema.get('oneOf', [])):
        if jsonschema.Draft202012Validator(branch).is_valid(value):
            yield from label_mutations(branch, value, path)
    if isinstance(value, dict):
        for key, item in value.items():
            child = schema.get('properties', {}).get(key, schema.get('additionalProperties', {}))
            if isinstance(child, dict):
                yield from label_mutations(child, item, (*path, key))
    if isinstance(value, list):
        for index, item in enumerate(value):
            prefix = schema.get('prefixItems', [])
            child = prefix[index] if index < len(prefix) else schema.get('items', {})
            if isinstance(child, dict):
                yield from label_mutations(child, item, (*path, index))


def replay(message, execution, *, overrides=None, legal_tools=None):
    """Run the isolated pure worker without an executor or ledger capability."""
    program = message['program']
    validate_program(program)
    if digest(program) != execution['program_sha256']:
        raise ValueError('Replay program differs from the actual execution')
    tools, changes = legal_tools or {}, overrides or {}
    recorded = execution['traces']
    if any(type(i) is not int or not 0 <= i < len(recorded)
           or recorded[i].get('type', 'predicate') != 'predicate'
           or recorded[i].get('status') != 'validated' for i in changes):
        raise ValueError('An intervention must name an actually validated predicate')
    predicates = {p['id']: p for p in program['predicates']}
    for index, value in changes.items():
        predicate = predicates[recorded[index]['predicate']]
        schema = (message['inputs']['native_answer_schema'] if predicate['schema_mode'] == 'native'
                  else predicate['schema'])
        jsonschema.validate(value, schema)
    lookup = {}
    for index, trace in enumerate(recorded):
        if trace.get('type', 'predicate') == 'predicate' and trace.get('status') == 'validated':
            lookup.setdefault(digest([trace['predicate'], trace['input']]), []).append(index)
    used, events, answer, error = set(), [], None, None
    process = subprocess.Popen([sys.executable, '-B', '-m',
        'legal_skill_guard.paired_interfaces.control_worker'], stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
    try:
        process.stdin.write(json.dumps(message, ensure_ascii=False, allow_nan=False) + '\n')
        process.stdin.flush()
        while True:
            if not select.select([process.stdout], [], [], 30)[0]:
                raise TimeoutError('Replay did not reach a recorded callback or final answer')
            line = process.stdout.readline()
            if not line:
                raise RuntimeError('Replay worker exited without a verdict')
            event = json.loads(line)
            if event['type'] == 'result':
                answer = event['answer']
                jsonschema.validate(answer, message['inputs']['native_answer_schema'])
                break
            if event['sequence'] != len(events):
                raise ValueError('Replay callback order is malformed')
            if event['type'] == 'predicate':
                key = digest([event['predicate_id'], event['input']])
                index = next((i for i in lookup.get(key, []) if i not in used), None)
                if index is None:
                    raise ValueError('Unobserved predicate input on replay branch; no weak answer fabricated')
                used.add(index)
                value = changes.get(index, recorded[index]['value'])
                event.update(recorded_trace_index=index, intervened=index in changes,
                             physical_call_id=recorded[index].get('physical_call_id'))
            elif event['type'] == 'legal_tool':
                name = event['tool_id']
                binding = message['inputs']['legal_tools'].get(name)
                tool = tools.get(name)
                if not tool or not binding or tool['binding_sha256'] != binding['binding_sha256']:
                    raise ValueError('Replay legal tool lacks its original immutable binding')
                jsonschema.validate(event['input'], tool['input_schema'])
                value = tool['invoke'](event['input'])
                event.update(binding_sha256=tool['binding_sha256'], deterministic_recomputed=True)
            else:
                raise ValueError('Unknown replay callback')
            event['value'] = value
            events.append(event)
            process.stdin.write(json.dumps({'value': value}, ensure_ascii=False, allow_nan=False) + '\n')
            process.stdin.flush()
    except Exception as exc:
        error = type(exc).__name__ + ': ' + str(exc)
    finally:
        if process.poll() is None:
            if error is None:
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    process.kill()
            else:
                process.kill()
        process.wait(timeout=5)
        stderr = process.stderr.read()
        process.stdin.close(); process.stdout.close(); process.stderr.close()
    return {'supported': error is None, 'answer': answer, 'error': error,
            'events': events, 'worker_returncode': process.returncode, 'worker_stderr': stderr,
            'new_model_requests': 0, 'counterfactual_is_not_observed_weak_accuracy': True}


def attribute(message, execution, *, legal_tools=None, max_label_edits=2, max_replays=128):
    if max_label_edits not in (1, 2) or type(max_replays) is not int or max_replays < 1:
        raise ValueError('Declare a positive bounded one/two-label intervention design')
    if not execution.get('core_executed'):
        return {'baseline_reproduced': False, 'reason': 'Original execution did not complete',
                'original_error': execution.get('error'), 'interventions': [], 'new_model_requests': 0}
    baseline = replay(message, execution, legal_tools=legal_tools)
    original_events = execution['traces']
    def signature(event):
        return [event.get('type', 'predicate'), event.get('predicate', event.get('predicate_id', event.get('tool', event.get('tool_id')))),
                event['input'], event.get('value')]
    reproduced = (baseline['supported'] and digest(baseline['answer']) == digest(execution['answer'])
                  and [signature(e) for e in baseline['events']] == [signature(e) for e in original_events])
    if not reproduced:
        return {'baseline_reproduced': False, 'baseline': baseline, 'interventions': [],
                'reason': 'Exact recorded composition/trace was not reproduced', 'new_model_requests': 0}
    predicates = {p['id']: p for p in message['program']['predicates']}
    mutations, unbounded = [], []
    for index, trace in enumerate(execution['traces']):
        if trace.get('type', 'predicate') != 'predicate' or trace.get('status') != 'validated':
            continue
        p = predicates[trace['predicate']]
        schema = message['inputs']['native_answer_schema'] if p['schema_mode'] == 'native' else p['schema']
        options = list(label_mutations(schema, trace['value']))
        if not options:
            unbounded.append(index)
        for option in options:
            mutations.append({'trace_index': index, **option})
    results, seen, truncated = [], set(), False
    for width in range(1, max_label_edits + 1):
        for selected in combinations(mutations, width):
            identities = [(m['trace_index'], tuple(m['path'])) for m in selected]
            if len(set(identities)) != len(identities):
                continue
            overrides = {}
            for change in selected:
                index = change['trace_index']
                value = overrides.get(index, execution['traces'][index]['value'])
                overrides[index] = _replace(value, change['path'], change['value'])
            identity = digest(overrides)
            if identity in seen:
                continue
            seen.add(identity)
            if len(results) >= max_replays:
                truncated = True
                break
            result = replay(message, execution, overrides=overrides, legal_tools=legal_tools)
            results.append({'label_edits': list(selected), **result})
        if truncated:
            break
    return {'baseline_reproduced': True, 'baseline': baseline, 'interventions': results,
            'max_label_edits': max_label_edits, 'max_replays': max_replays,
            'enumeration_truncated': truncated, 'traces_without_finite_label_mutations': unbounded,
            'numeric_span_and_new_predicate_inputs_are_not_invented': True, 'new_model_requests': 0}
