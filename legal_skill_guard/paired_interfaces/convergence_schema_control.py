"""Reversible schema optimization and native recovery for the PARSE control."""

from copy import deepcopy
import json

import jsonschema

from legal_skill_guard.paired_interfaces.control_answers import decode_native, source_bundle, wire_schema
from legal_skill_guard.paired_interfaces.formal_actors import verify_physical_response
from legal_skill_guard.paired_interfaces.scope_learning import strict_json
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import record_schema, restore_enum_transport
from legal_skill_guard.skill_evolution.objects import digest


def schema_proposal():
    return record_schema({
        'field_aliases': {'type': 'array', 'items': record_schema({
            'original': {'type': 'string'}, 'alias': {'type': 'string'}})},
        'fields_first': {'type': 'array', 'items': {'type': 'string'}},
        'reader_guidance': {'type': 'string'},
    })


def public_field_types(schema):
    """Describe observed public field names and types without answer values."""
    fields = {}

    def visit(node):
        for name, child in node.get('properties', {}).items():
            fields.setdefault(name, set()).add(json.dumps(child.get('type'), sort_keys=True))
            visit(child)
        if 'items' in node:
            visit(node['items'])

    visit(schema)
    return {name: [json.loads(value) for value in sorted(kinds)] for name, kinds in sorted(fields.items())}


class ReversibleWire:
    """Rename and order fields bijectively without removing any answer or evidence."""

    def __init__(self, schema, proposal):
        # Proposal validity across the known public family is checked at selection.
        # A future source can omit a field, but any new collision remains an error.
        self.original = deepcopy(schema)
        self.aliases = {row['original']: row['alias'] for row in proposal['field_aliases']}
        self.priority = {key: index for index, key in enumerate(proposal['fields_first'])}
        self.schema = self._rewrite(schema)
        jsonschema.Draft202012Validator.check_schema(self.schema)

    def _rewrite(self, node):
        changed = deepcopy(node)
        if {'allOf', 'anyOf', 'oneOf', 'if', '$ref', 'patternProperties', 'dependentSchemas',
                'dependentRequired', 'propertyNames', 'dependencies'} & node.keys():
            raise ValueError('The native schema has a constraint outside the field-alias compiler')
        if 'properties' in node:
            if node.get('additionalProperties') is not False:
                raise ValueError('Reversible native field renaming requires explicit object properties')
            properties = node['properties']
            ordered = sorted(properties, key=lambda name: self.priority.get(name, len(self.priority)))
            renamed = {self.aliases.get(name, name): self._rewrite(properties[name]) for name in ordered}
            if len(renamed) != len(properties):
                raise ValueError('A field alias collides with another visible native property')
            changed['properties'] = renamed
            required = node.get('required', [])
            if not set(required) <= properties.keys():
                raise ValueError('The original native schema requires undeclared properties')
            if 'required' in node:
                changed['required'] = [self.aliases.get(name, name) for name in ordered if name in required]
        if 'items' in node:
            changed['items'] = self._rewrite(node['items'])
        return changed

    def _translate(self, item, node, *, reverse):
        if isinstance(item, dict) and 'properties' in node:
            fields = node['properties']
            aliases = {name: self.aliases.get(name, name) for name in fields}
            keys = {alias: name for name, alias in aliases.items()} if reverse else aliases
            return {keys[key]: self._translate(value, fields[keys[key] if reverse else key], reverse=reverse)
                    for key, value in item.items()}
        if isinstance(item, list) and 'items' in node:
            return [self._translate(value, node['items'], reverse=reverse) for value in item]
        return item

    def restore(self, optimized):
        jsonschema.validate(optimized, self.schema)
        original = self._translate(optimized, self.original, reverse=True)
        jsonschema.validate(original, self.original)
        return original

    def encode(self, original):
        jsonschema.validate(original, self.original)
        optimized = self._translate(original, self.original, reverse=False)
        jsonschema.validate(optimized, self.schema)
        return optimized


def measure_schema(executor, root, source, proposal, purpose):
    """Make one shared-budget frozen read and recover the complete native wire."""
    bundle = source_bundle(source)
    codec = ReversibleWire(wire_schema(source['dataset'], bundle), proposal)
    schema = record_schema({'value': codec.schema})
    key_map = {key: value for key, value in codec.aliases.items() if key != value}
    messages = [
        {'role': 'system', 'content': 'Answer every native task from its complete public input. Retain every '
         'original answer, uncertainty and requested evidence. Output the exact supplied JSON schema. '
         'The following map gives original field name to requested output name: '
         + json.dumps(key_map, ensure_ascii=False, sort_keys=True) + '\n'
         + proposal['reader_guidance'] + '\nSchema: ' + json.dumps(schema, ensure_ascii=False, separators=(',', ':'))},
        {'role': 'user', 'content': json.dumps({'public': bundle['public'], 'answer_schema': bundle['answer_schema']},
                                              ensure_ascii=False, sort_keys=True)},
    ]
    call_id = executor.ledger.run_id + ':parse:' + digest([source['key'], purpose, messages])
    response = executor.generate(call_id, source=source['key'], purpose=purpose, messages=messages,
                                 schema=schema, thinking=False)
    physical_id = response.get('reused_physical_call_id', call_id)
    raw_digest = digest(response['content'])
    verify_physical_response(executor, identity=physical_id, source=source['key'], purpose=purpose,
                             content_sha256=raw_digest, usage=response['usage'], finish_reason=response['finish_reason'])
    error, restored, answers, evidence, changes = None, None, {}, {}, []
    try:
        if response['finish_reason'] != 'stop':
            raise ValueError('Schema reader response was incomplete')
        optimized, changes = restore_enum_transport(strict_json(response['content']), schema)
        jsonschema.validate(optimized, schema)
        restored = codec.restore(optimized['value'])
        answers, evidence = decode_native(source['dataset'], bundle, restored)
    except (ValueError, jsonschema.ValidationError) as exc:
        error = {'type': type(exc).__name__, 'reason': str(exc).split('\n')[0]}
    result = {'source_sha256': digest(source), 'proposal_sha256': digest(proposal),
              'physical_call_id': physical_id, 'response_sha256': raw_digest, 'usage': response['usage'],
              'finish_reason': response['finish_reason'], 'restored_native_wire': restored,
              'enum_transport_restorations': changes, 'production_error': error,
              'native': {view['id']: {'handled': view['id'] in answers,
                                      'answer': answers.get(view['id']),
                                      'evidence_sentence_ids': evidence.get(view['id'], [])}
                         for view in source['views']}}
    path = root / 'schema_control_reads' / digest(call_id)
    immutable_json(path / 'input.json', {'messages': messages, 'schema': schema, 'proposal': proposal})
    immutable_json(path / 'result.json', result)
    return result
