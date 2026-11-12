"""Frozen local reads, actual helper dataflow and the common direct fallback."""
from dataclasses import asdict
import ast
import json
from pathlib import Path
import re
import subprocess
import sys

import jsonschema

from .objects import Skill, digest, dependency_arguments
from .answer_domain import incompatible_native_enum
from .claim_scope import declared_claim_mismatch
from legal_skill_guard.rr.checkpoint import immutable_json
from .native import (record_schema, answer_wire_schema, decode_answer,
                     public_task, public_strings, DIRECT_SYSTEM, restore_enum_transport, source_spans)

TYPES = {'boolean', 'integer', 'number', 'string', 'array', 'object'}


class LocalReadError(ValueError):
    def __init__(self, message, event):
        super().__init__(message)
        self.event = event


def render_messages(system, content, schema):
    # Guided decoding alone does not tell the model the requested field layout.
    return [{'role': 'system', 'content': system}, {'role': 'user', 'content': json.dumps(
        {'task': content, 'output_schema': schema}, ensure_ascii=False)}]


def typed(value, kind):
    if kind not in TYPES:
        raise ValueError('Undeclared port type')
    jsonschema.validate(value, {'type': kind})
    return value


def aligned_array_ports(skill):
    """Infer only literal parallel-array indexing contracts from the program.

    Dependent arrays must be observable solely at the anchor's loop index.
    Whole-array access or a different index prevents this inference.
    """
    tree = ast.parse(skill.procedure)
    parents = {id(c): n for n in ast.walk(tree) for c in ast.iter_child_nodes(n)}
    aliases = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)):
            continue
        value = node.value
        if (isinstance(value, ast.Subscript) and isinstance(value.value, ast.Name)
                and value.value.id in ('inputs', 'premises') and isinstance(value.slice, ast.Constant)
                and isinstance(value.slice.value, str)):
            aliases[node.targets[0].id] = (value.value.id, value.slice.value)
    stores = {name: sum(isinstance(n, ast.Name) and n.id == name and isinstance(n.ctx, ast.Store)
                       for n in ast.walk(tree)) for name in aliases}
    port_counts = {port: sum(p == port for p in aliases.values()) for port in aliases.values()}
    accesses = {}
    for port in aliases.values():
        accesses[port] = sum(isinstance(n, ast.Subscript) and isinstance(n.value, ast.Name)
            and n.value.id == port[0] and isinstance(n.slice, ast.Constant) and n.slice.value == port[1]
            for n in ast.walk(tree))
    aliases = {name: port for name, port in aliases.items()
               if stores[name] == 1 and port_counts[port] == 1 and accesses[port] == 1}
    groups = []
    for loop in ast.walk(tree):
        if not isinstance(loop, ast.For) or not isinstance(loop.target, ast.Name):continue
        if sum(isinstance(n, ast.Name) and n.id == loop.target.id and isinstance(n.ctx, ast.Store)
               for n in ast.walk(tree)) != 1:continue
        call = loop.iter
        if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                and call.func.id == 'range' and len(call.args) == 1):continue
        length = call.args[0]
        if not (isinstance(length, ast.Call) and isinstance(length.func, ast.Name)
                and length.func.id == 'len' and len(length.args) == 1
                and isinstance(length.args[0], ast.Name) and length.args[0].id in aliases):continue
        anchor_name = length.args[0].id
        anchor = aliases[anchor_name]
        dependents = []
        for name, port in aliases.items():
            if name == anchor_name:continue
            loads = [n for n in ast.walk(tree) if isinstance(n, ast.Name)
                     and isinstance(n.ctx, ast.Load) and n.id == name]
            if loads and all(isinstance(parents[id(n)], ast.Subscript)
                    and isinstance(parents[id(n)].ctx, ast.Load)
                    and parents[id(n)].value is n
                    and isinstance(parents[id(n)].slice, ast.Name)
                    and parents[id(n)].slice.id == loop.target.id
                    and parents[id(n)] in list(ast.walk(loop)) for n in loads):
                dependents.append(port)
        def is_array(port):
            return (skill.inputs if port[0] == 'inputs' else skill.premises).get(port[1], {}).get('type') == 'array'
        dependents = [p for p in dependents if is_array(p)]
        if dependents and is_array(anchor):groups.append((anchor, dependents))
    return groups


def execute_helper(skill, inputs, premises, *, unresolved_inputs=(), unresolved_premises=()):
    skill.validate()
    unknown = {'inputs': set(unresolved_inputs), 'premises': set(unresolved_premises)}
    for name, values, declared in (('inputs', inputs, skill.inputs), ('premises', premises, skill.premises)):
        if set(values) & unknown[name] or set(values) | unknown[name] != set(declared):
            raise ValueError('Every declared binding must be known or explicitly unresolved')
    if any(unknown.values()):
        # Omit unresolved values, never substitute None/False or a prior value.
        # Literal indexing raises if execution reaches a missing field. Reject
        # whole-map observation, aliases, dynamic indexing and mutation, which
        # could otherwise observe the omission or manufacture a replacement.
        tree = ast.parse(skill.procedure)
        parents = {id(c): n for n in ast.walk(tree) for c in ast.iter_child_nodes(n)}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Name) or node.id not in unknown or not unknown[node.id]:continue
            parent = parents.get(id(node))
            if (not isinstance(node.ctx, ast.Load) or not isinstance(parent, ast.Subscript)
                    or parent.value is not node or not isinstance(parent.ctx, ast.Load)
                    or not isinstance(parent.slice, ast.Constant) or not isinstance(parent.slice.value, str)):
                raise ValueError('Partially unresolved bindings require read-only literal field access')
    for name, value in inputs.items():
        typed(value, skill.inputs[name]['type'])
    for name, value in premises.items():
        typed(value, skill.premises[name]['type'])
    result = subprocess.run([sys.executable, '-I', '-S', str(Path(__file__).with_name('worker.py'))],
        input=json.dumps({'procedure': skill.procedure, 'inputs': inputs, 'premises': premises},
                         ensure_ascii=False, allow_nan=False), capture_output=True, text=True,
        timeout=4, cwd='/tmp', env={'LANG': 'C.UTF-8'}, close_fds=True)
    if result.returncode:
        raise ValueError('Learned helper failed: ' + result.stderr[-1600:])
    value = json.loads(result.stdout)
    if not isinstance(value, dict) or set(value) != set(skill.outputs):
        raise ValueError('Helper must return its complete declared output record')
    for name, item in value.items():
        typed(item, skill.outputs[name]['type'])
    return value


class FrozenReads:
    def __init__(self, executor):
        self.executor = executor

    def generate(self, source, view, *, system, content, schema, purpose):
        messages = render_messages(system, content, schema)
        payload = self.executor.payload(messages=messages, thinking=False, schema=schema)
        call_id = self.executor.ledger.run_id + ':' + digest({
            'source': source['key'], 'purpose': purpose, 'payload': payload})
        result = self.executor.generate(call_id, source=source['key'], purpose=purpose,
            messages=messages, thinking=False, schema=schema)
        if result['finish_reason'] != 'stop':
            raise ValueError('Incomplete model response retained: ' + str(result['finish_reason']))
        value = json.loads(result['content'])
        value, adaptations = restore_enum_transport(value, schema)
        jsonschema.validate(value, schema)
        return value, {'call_id': call_id, 'cache_hit': result.get('cache_hit', False),
                       'physical_call_id': result.get('reused_physical_call_id', call_id),
                       'transport_adaptations': adaptations,
                       'usage': result['usage'], 'elapsed_seconds': result['elapsed_seconds'],
                       'response_hash': digest(value)}

    def read(self, source, view, *, question, fields, locator, purpose,
             alignment=None, array_lengths=None, anchor_values=None, allow_unresolved=False,
             invocation_arguments=None):
        if alignment:
            anchor, dependents = alignment
            remaining = {n: spec for n, spec in fields.items() if n not in dependents}
            values, first = self.read(source, view, question=question, fields=remaining,
                locator=locator, purpose=purpose, allow_unresolved=allow_unresolved,
                invocation_arguments=invocation_arguments)
            if anchor not in values:
                raise LocalReadError('Array alignment anchor is unresolved: ' + anchor, first)
            count = len(values[anchor])
            try:
                extra, second = self.read(source, view, question=question,
                    fields={n: fields[n] for n in dependents}, locator=locator, purpose=purpose,
                    array_lengths={n: count for n in dependents}, anchor_values={anchor: values[anchor]},
                    allow_unresolved=allow_unresolved, invocation_arguments=invocation_arguments)
            except LocalReadError as error:
                event = {**error.event, 'fields': {**first['fields'], **error.event['fields']},
                    'subreads': [first, error.event],
                    'alignment': {'anchor': anchor, 'length': count, 'dependents': dependents}}
                raise LocalReadError(str(error), event) from error
            merged = {**values, **extra}
            events = [first, second]
            return merged, {'kind': 'READ_LOCAL', 'question': question, 'locator': locator,
                'source': source['key'], 'view': view['id'],
                'call_id': 'aligned:' + digest([e['call_id'] for e in events]),
                'physical_call_ids': [e['physical_call_id'] for e in events],
                'usage': {k: sum((e.get('usage') or {}).get(k, 0) or 0 for e in events)
                          for k in ('prompt_tokens', 'completion_tokens', 'total_tokens')},
                'fields': {**first['fields'], **second['fields']}, 'subreads': events,
                'invocation_arguments': invocation_arguments or {},
                'unresolved_fields': sorted(set(fields) - set(merged)),
                'alignment': {'anchor': anchor, 'length': count, 'dependents': dependents}}
        spans = source_spans(view['public'])
        properties = {}
        for name, specification in fields.items():
            kind = specification['type']
            if kind not in TYPES:
                raise ValueError('Unsupported local read type')
            value = {'type': [kind, 'null']}
            if kind == 'array':
                value['items'] = {'type': ['string', 'number', 'boolean', 'null']}
                if name in (array_lengths or {}):
                    value.update(minItems=array_lengths[name], maxItems=array_lengths[name])
            if kind == 'object':
                raise ValueError('Local reads use explicit primitive or array fields')
            properties[name] = record_schema({'status': {'type': 'string', 'enum': ['known', 'unknown']},
                'value': value, 'support_ids': {'type': 'array', 'maxItems': len(spans),
                    'items': {'type': 'integer', 'minimum': 0, 'maximum': len(spans) - 1}}})
        value, event = self.generate(source, view,
            system=('Read only the requested local fields from the current supplied text. '
                'For each known field select the supplied span IDs that support its value. '
                'The host binds these IDs to exact source text; do not rewrite or quote the source. '
                'Citation fields use full literal citation strings in the headings; a legacy label-ID output sentence is only an encoding instruction. '
                'Respect the question scope and roles. Never use old-source values. '
                'Use status unknown with value null if the current material is insufficient. '
                'Do not answer the entire task unless a requested field itself is that native label.'),
            content={'dataset': source['dataset'], 'view_id': view['id'], 'source_spans': spans,
                     'read_question': question, 'source_locator': locator, 'fields': fields,
                     **({'invocation_arguments': invocation_arguments,
                         'role_instruction': 'Read for these explicitly bound entities and period. The outer question does not override these arguments. Use the complete supplied source to interpret explicit given facts; do not infer a missing legal conclusion.'}
                        if invocation_arguments else {}),
                     **({'alignment_anchor_values': anchor_values,
                         'required_array_lengths': array_lengths,
                         'alignment_instruction': 'One value per supplied anchor entry, in that exact order; no additional entries.'}
                        if anchor_values is not None else {})},
            schema=record_schema(properties), purpose=purpose)
        for item in value.values():
            item['support'] = [spans[i] for i in item['support_ids']]
        event = {**event, 'kind': 'READ_LOCAL', 'question': question, 'locator': locator,
                 'fields': value, 'source': source['key'], 'view': view['id'],
                 'invocation_arguments': invocation_arguments or {}}
        known = {}
        for name, item in value.items():
            if item['status'] == 'unknown' and item['value'] is None:
                if allow_unresolved:continue
                raise LocalReadError('Current-source read unresolved: ' + name, event)
            if item['status'] != 'known' or item['value'] is None:
                raise LocalReadError('Inconsistent local field status/value: ' + name, event)
            if not item['support_ids']:
                raise LocalReadError('Local field has no selected current-source support: ' + name, event)
            typed(item['value'], fields[name]['type'])
            known[name] = item['value']
        event['unresolved_fields'] = sorted(set(fields) - set(known))
        return known, event

    def direct(self, source, view, purpose):
        self.executor.validate_scope(source['key'], purpose, False)
        identity = digest({'source': source['key'], 'task': public_task(source, view),
                           'frozen_executor': self.executor.config})
        cache = self.executor.artifacts / 'native_direct_baselines' / (identity + '.json')
        if cache.exists():
            saved = json.loads(cache.read_text())
            if saved['identity'] != identity or saved['execution']['core_executed']:
                raise ValueError('Frozen direct baseline identity changed')
            return json.loads(json.dumps(saved['execution']))
        value, event = self.generate(source, view, system=DIRECT_SYSTEM,
            content=public_task(source, view), schema=answer_wire_schema(source['dataset'], view), purpose=purpose)
        answer, evidence = decode_answer(source['dataset'], view, value)
        result = {'answer': answer, 'evidence_sentence_ids': evidence, 'events': [event],
                  'fallback': True, 'core_executed': False}
        immutable_json(cache, {'identity': identity, 'execution': result})
        return result


def retrieve(library, source, view, limit=5):
    """Common lexical retrieval; no labels, source IDs or dataset gate."""
    query = ' '.join(public_strings(view['public']))
    words = set(re.findall(r'[a-z]+', query.lower()))
    ranked = []
    for identity, skill in library.skills.items():
        terms = set(re.findall(r'[a-z]+', skill.intent.lower()))
        score = len(words & terms) / max(1, len(terms))
        if ('answer' in skill.outputs and skill.outputs['answer']['type'] == view['answer_schema']['type']):
            ranked.append((score, identity))
    return [identity for _, identity in sorted(ranked, reverse=True)[:limit]]


class SkillRuntime:
    def __init__(self, reads):
        self.reads = reads

    def run(self, source, view, library, *, purpose='skill_actor', retrieved=None, fallback=True):
        selected = retrieve(library, source, view) if retrieved is None else list(retrieved)
        events, completed, visiting, failures = [], {}, set(), []

        def apply(identity, arguments=None):
            arguments = {} if arguments is None else arguments
            invocation = (identity, digest(arguments))
            if invocation in completed:
                return completed[invocation]
            if identity in visiting or identity not in library.skills:
                raise ValueError('Missing or cyclic skill dependency')
            skill = library.skills[identity]
            skill.validate()
            required = {n: p for n, p in skill.inputs.items() if p['mode'] == 'argument'}
            if set(arguments) != set(required):
                raise ValueError('Invocation arguments must match all and only declared parameters')
            for name, value in arguments.items():
                typed(value, required[name]['type'])
            dependency_bindings = {n: dependency_arguments(skill, p, library.skills)
                for n, p in skill.inputs.items() if p['mode'] == 'skill'}
            visiting.add(identity)
            contracts = aligned_array_ports(skill)

            def alignment_for(mode, ports, current_fields):
                for anchor, dependents in contracts:
                    if anchor[0] != mode or anchor[1] not in ports:continue
                    names = list(dict.fromkeys(ports[p[1]] for p in dependents if p[0] == mode
                        and p[1] in ports and ports[p[1]] != ports[anchor[1]]))
                    if names and all(n in current_fields for n in [ports[anchor[1]]] + names):
                        return ports[anchor[1]], names
                return None

            inputs, fields = dict(arguments), {}
            for name, port in skill.inputs.items():
                if port['mode'] == 'read':
                    fields[name] = {'type': port['type'], 'question': port['question']}
            if fields:
                alignment = alignment_for('inputs', {n: n for n in fields}, fields)
                values, event = self.reads.read(source, view, question='Read the current task input fields.',
                    fields=fields, locator='current supplied source, facts and question, according to each requested field', purpose=purpose,
                    allow_unresolved=True,
                    **({'invocation_arguments': arguments} if arguments else {}),
                    **({'alignment': alignment} if alignment else {}))
                inputs.update(values); events.append(event)
            for name, bindings in dependency_bindings.items():
                port = skill.inputs[name]
                bound = {parameter: inputs[local] for parameter, local in bindings.items()}
                producer = apply(port['skill_id'], bound)
                inputs[name] = producer[port['field']]
                events.append({'kind': 'USE', 'producer': port['skill_id'], 'field': port['field'],
                    'consumer': identity, 'input': name, 'value': inputs[name],
                    'producer_arguments': bound, 'argument_bindings': bindings,
                    'consumer_arguments': arguments})
            premises = {n: p['value'] for n, p in skill.premises.items() if p['mode'] == 'constant'}
            for reader in skill.reads:
                ports = {n: p['field'] for n, p in skill.premises.items()
                         if p['mode'] == 'read' and p['read_id'] == reader['id']}
                if not ports:
                    continue
                alignment = alignment_for('premises', ports, reader['fields'])
                values, event = self.reads.read(source, view, question=reader['question'],
                    fields=reader['fields'], locator=reader['source_locator'], purpose=purpose,
                    allow_unresolved=True,
                    **({'invocation_arguments': arguments} if arguments else {}),
                    **({'alignment': alignment} if alignment else {}))
                events.append(event)
                for name, port in skill.premises.items():
                    if port['mode'] == 'read' and port['read_id'] == reader['id']:
                        if port['field'] in values:premises[name] = values[port['field']]
            missing_inputs, missing_premises = set(skill.inputs) - set(inputs), set(skill.premises) - set(premises)
            value = execute_helper(skill, inputs, premises,
                unresolved_inputs=missing_inputs, unresolved_premises=missing_premises)
            events.append({'kind': 'APPLY', 'skill_id': identity, 'skill_hash': skill.hash,
                'version': skill.version, 'inputs': inputs, 'premises': premises, 'outputs': value,
                'invocation_arguments': arguments,
                'unresolved_inputs': sorted(missing_inputs), 'unresolved_premises': sorted(missing_premises),
                'source': source['key'], 'view': view['id']})
            completed[invocation] = value; visiting.remove(identity)
            return value

        for identity in selected:
            if identity in library.skills:
                scope = declared_claim_mismatch(library.skills[identity], view)
                if scope:
                    failures.append({'skill_id': identity,
                        'error': 'StaticQueryScopeMismatch: the declared final proposition differs from the current explicit query',
                        'static_proof': scope})
                    continue
                proof = incompatible_native_enum(library.skills[identity].procedure, view['answer_schema'])
                if proof:
                    failures.append({'skill_id': identity,
                        'error': 'StaticNativeEnumMismatch: no possible helper answer satisfies the current native enum',
                        'static_proof': proof})
                    continue
            try:
                value = apply(identity)
                jsonschema.validate(value['answer'], view['answer_schema'])
                return {'answer': value['answer'], 'evidence_sentence_ids': [], 'fallback': False,
                    'core_executed': True, 'terminal_skill': identity, 'retrieved': selected,
                    'events': events, 'failed_candidates': failures}
            except (ValueError, KeyError, TypeError, jsonschema.ValidationError, subprocess.TimeoutExpired) as error:
                if isinstance(error, LocalReadError):events.append(error.event)
                failures.append({'skill_id': identity, 'error': type(error).__name__ + ': ' + str(error)})
                visiting.clear()
        if fallback:
            value = self.reads.direct(source, view, purpose)
            value.update(events=events + value['events'], retrieved=selected, failed_candidates=failures)
            return value
        return {'answer': None, 'evidence_sentence_ids': [], 'fallback': False,
                'core_executed': False, 'events': events, 'retrieved': selected,
                'failed_candidates': failures, 'unresolved': True}
