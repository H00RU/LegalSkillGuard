"""Frozen local reads, actual helper dataflow and the common direct fallback."""
from dataclasses import asdict
import json
from pathlib import Path
import re
import subprocess
import sys

import jsonschema

from .objects import Skill, digest
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


def execute_helper(skill, inputs, premises):
    skill.validate()
    if set(inputs) != set(skill.inputs) or set(premises) != set(skill.premises):
        raise ValueError('Complete current inputs and premise bindings required')
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

    def read(self, source, view, *, question, fields, locator, purpose):
        spans = source_spans(view['public'])
        properties = {}
        for name, specification in fields.items():
            kind = specification['type']
            if kind not in TYPES:
                raise ValueError('Unsupported local read type')
            value = {'type': [kind, 'null']}
            if kind == 'array':
                value['items'] = {'type': ['string', 'number', 'boolean', 'null']}
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
                     'read_question': question, 'source_locator': locator, 'fields': fields},
            schema=record_schema(properties), purpose=purpose)
        for item in value.values():
            item['support'] = [spans[i] for i in item['support_ids']]
        event = {**event, 'kind': 'READ_LOCAL', 'question': question, 'locator': locator,
                 'fields': value, 'source': source['key'], 'view': view['id']}
        for name, item in value.items():
            if item['status'] != 'known' or item['value'] is None:
                raise LocalReadError('Current-source read unresolved: ' + name, event)
            if not item['support_ids']:
                raise LocalReadError('Local field has no selected current-source support: ' + name, event)
            typed(item['value'], fields[name]['type'])
        return {n: x['value'] for n, x in value.items()}, event

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

        def apply(identity):
            if identity in completed:
                return completed[identity]
            if identity in visiting or identity not in library.skills:
                raise ValueError('Missing or cyclic skill dependency')
            visiting.add(identity)
            skill = library.skills[identity]
            inputs, fields = {}, {}
            for name, port in skill.inputs.items():
                if port['mode'] == 'skill':
                    producer = apply(port['skill_id'])
                    inputs[name] = producer[port['field']]
                    events.append({'kind': 'USE', 'producer': port['skill_id'], 'field': port['field'],
                        'consumer': identity, 'input': name, 'value': inputs[name]})
                elif port['mode'] == 'read':
                    fields[name] = {'type': port['type'], 'question': port['question']}
                else:
                    raise ValueError('Unknown input acquisition mode')
            if fields:
                values, event = self.reads.read(source, view, question='Read the current task input fields.',
                    fields=fields, locator='current supplied source, facts and question, according to each requested field', purpose=purpose)
                inputs.update(values); events.append(event)
            premises = {n: p['value'] for n, p in skill.premises.items() if p['mode'] == 'constant'}
            for reader in skill.reads:
                values, event = self.reads.read(source, view, question=reader['question'],
                    fields=reader['fields'], locator=reader['source_locator'], purpose=purpose)
                events.append(event)
                for name, port in skill.premises.items():
                    if port['mode'] == 'read' and port['read_id'] == reader['id']:
                        premises[name] = values[port['field']]
            value = execute_helper(skill, inputs, premises)
            events.append({'kind': 'APPLY', 'skill_id': identity, 'skill_hash': skill.hash,
                'version': skill.version, 'inputs': inputs, 'premises': premises, 'outputs': value,
                'source': source['key'], 'view': view['id']})
            completed[identity] = value; visiting.remove(identity)
            return value

        for identity in selected:
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
