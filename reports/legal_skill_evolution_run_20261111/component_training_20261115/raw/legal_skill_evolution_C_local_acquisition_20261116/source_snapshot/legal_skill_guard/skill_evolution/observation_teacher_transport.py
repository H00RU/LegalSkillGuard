"""Losslessly share the actual observation schema ASTs in large teacher tasks.

The acquired schemas are canonical compact JSON strings. Exposing their parsed
objects to the existing shared-value transport lets common witness/record
schemas share storage instead of repeatedly escaping their whole strings.
Only byte-exact canonical strings use the tag; every other input stays literal.
The output protocol and all legal/source information remain unchanged.
"""
from copy import deepcopy
import json

from .teacher_transport import pack_programs, unpack_programs


SCHEMA_AST = '__lsg_canonical_schema_json__'
INSTRUCTION = ('In this INPUT only, schema_json may be encoded as '
    '{"__lsg_canonical_schema_json__": schema_object}. After resolving shared-value references, '
    'serialize schema_object with UTF-8 characters and compact JSON separators (comma and colon, no extra spaces) '
    'to recover the EXACT original schema_json string and its property order. This is storage sharing, '
    'not a changed schema or added legal information. Output component_edits.schema_json remains an ordinary '
    'JSON string as required by the output schema; do not emit input transport tags in your answer.')


def pack_task(task):
    def factor(node):
        if isinstance(node, dict):
            if SCHEMA_AST in node:
                raise ValueError('Original task uses the reserved schema transport tag')
            result = {}
            for key, value in node.items():
                if key == 'schema_json' and isinstance(value, str):
                    try:
                        parsed = json.loads(value)
                    except json.JSONDecodeError:
                        parsed = None  # Preserve failed schema text exactly.
                    if isinstance(parsed, dict) and json.dumps(parsed, ensure_ascii=False, separators=(',', ':')) == value:
                        result[key] = {SCHEMA_AST: factor(parsed)}
                        continue
                result[key] = factor(value)
            return result
        if isinstance(node, list):
            return [factor(value) for value in node]
        return deepcopy(node)

    result = pack_programs(factor(task), extra_program_fields=('conversion_program',),
        program_line_segments=True)
    result['observation_schema_encoding'] = 'canonical_JSON_schema_AST_v1'
    return result


def unpack_task(envelope):
    if envelope.get('observation_schema_encoding') != 'canonical_JSON_schema_AST_v1':
        raise ValueError('Explicit observation schema transport required')

    def restore(node):
        if isinstance(node, dict):
            if set(node) == {SCHEMA_AST}:
                return json.dumps(restore(node[SCHEMA_AST]), ensure_ascii=False, separators=(',', ':'))
            return {key: restore(value) for key, value in node.items()}
        if isinstance(node, list):
            return [restore(value) for value in node]
        return node

    return restore(unpack_programs(envelope))
