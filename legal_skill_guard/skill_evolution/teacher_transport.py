"""Lossless sharing of repeated JSON values in a complete teacher input."""
from collections import Counter
import ast
import json

REFERENCE = '__lsg_shared_value__'
PROGRAM_SEGMENTS = '__lsg_program_segments__'
INSTRUCTION = ('The input is losslessly reference-encoded JSON. Read task as the original input; '
    'each singleton object {"__lsg_shared_value__":"vN"} denotes shared_values["vN"], '
    'recursively. Repeated source text, programs and execution records are shared, never omitted. '
    'References are storage identifiers, not legal rules, labels or source identities. '
    'All instructions and requested output schema remain unchanged.')
PROGRAM_INSTRUCTION = ('A program string may additionally be encoded as '
    '{"__lsg_program_segments__":[segment,...]}. After resolving ordinary '
    'shared-value references, concatenate those string segments in order, '
    'without adding separators, to recover the exact complete Python program. '
    'Segments preserve original whitespace, comments and function bodies. '
    'This shares unchanged helpers across actual libraries; it adds no rule.')


def serialized(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def pack(value):
    counts = Counter()
    def count(node):
        body = serialized(node)
        if len(body) >= 96:counts[body] += 1
        if isinstance(node, dict):
            if REFERENCE in node:raise ValueError('Original input contains the reserved transport key')
            for child in node.values():count(child)
        elif isinstance(node, list):
            for child in node:count(child)
    count(value)
    pool, identities = {}, {}
    def children(node):
        if isinstance(node, dict):return {key: encode(child) for key, child in node.items()}
        if isinstance(node, list):return [encode(child) for child in node]
        return node
    def encode(node):
        body = serialized(node)
        if counts[body] < 2:return children(node)
        if body not in identities:
            identity = 'v' + str(len(identities));identities[body] = identity
            pool[identity] = children(node)
        return {REFERENCE: identities[body]}
    task = encode(value)
    return {'encoding': 'lossless_shared_JSON_values_v1', 'shared_values': pool, 'task': task}


def unpack(envelope):
    if envelope['encoding'] != 'lossless_shared_JSON_values_v1':raise ValueError('Unknown teacher transport')
    visiting = set()
    def decode(node):
        if isinstance(node, dict):
            if set(node) == {REFERENCE}:
                identity = node[REFERENCE]
                if identity in visiting:raise ValueError('Cyclic teacher transport reference')
                visiting.add(identity);value = decode(envelope['shared_values'][identity]);visiting.remove(identity)
                return value
            return {key: decode(child) for key, child in node.items()}
        if isinstance(node, list):return [decode(child) for child in node]
        return node
    return decode(envelope['task'])


def pack_programs(value):
    """Share real unchanged helpers without normalizing any program bytes."""
    fields = {'source_program', 'planner_program', 'composition_program', 'decision_program'}
    def split(code):
        tree = ast.parse(code)
        functions = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
        if len(functions) < 2:
            return code
        cursor = 0; segments = []
        for node in functions:
            fragment = ast.get_source_segment(code, node)
            start = code.index(fragment, cursor)
            segments.extend([code[cursor:start], fragment])
            cursor = start + len(fragment)
        segments.append(code[cursor:])
        assert ''.join(segments) == code
        return {PROGRAM_SEGMENTS: segments}
    def factor(node):
        if isinstance(node, dict):
            if PROGRAM_SEGMENTS in node:
                raise ValueError('Original task contains the reserved program-segment key')
            return {k: split(v) if k in fields and isinstance(v, str) else factor(v)
                    for k, v in node.items()}
        if isinstance(node, list):
            return [factor(v) for v in node]
        return node
    result = pack(factor(value))
    result['program_encoding'] = 'exact_python_segments_v1'
    return result


def unpack_programs(envelope):
    if envelope.get('program_encoding') != 'exact_python_segments_v1':
        raise ValueError('Explicit exact-program encoding required')
    def restore(node):
        if isinstance(node, dict):
            if set(node) == {PROGRAM_SEGMENTS}:
                parts = node[PROGRAM_SEGMENTS]
                if not isinstance(parts, list) or any(not isinstance(p, str) for p in parts):
                    raise ValueError('Program segments must remain literal strings')
                return ''.join(parts)
            return {k: restore(v) for k, v in node.items()}
        if isinstance(node, list):
            return [restore(v) for v in node]
        return node
    return restore(unpack(envelope))
