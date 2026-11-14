"""Lossless sharing of repeated JSON values in a complete teacher input."""
from collections import Counter
import ast
import json
import re

REFERENCE = '@v'
PROGRAM_SEGMENTS = '__lsg_program_segments__'
SOURCE_SEGMENTS = '@s'
INSTRUCTION = ('The input is losslessly reference-encoded JSON. Read task as the original input; '
    'each string "@N" consisting of @ followed only by decimal digits denotes shared_values["N"], '
    'recursively. Repeated source text, programs and execution records are shared, never omitted. '
    'References are storage identifiers, not legal rules, labels or source identities. '
    'All instructions and requested output schema remain unchanged.')
PROGRAM_INSTRUCTION = ('A program string may additionally be encoded as '
    '{"__lsg_program_segments__":[segment,...]}. After resolving ordinary '
    'shared-value references, concatenate those string segments in order, '
    'without adding separators, to recover the exact complete Python program. '
    'Segments preserve original whitespace, comments and function bodies. '
    'Source text may use {"@s":[segment,...]} under the same exact-concatenation rule; its segments use only verified original source-unit intervals. This shares unchanged helpers and original source clauses; it adds no rule.')


def serialized(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def pack(value):
    counts = Counter()
    smallest_reference = len(serialized('@0'))
    def count(node):
        if isinstance(node, str) and re.fullmatch(r'@[0-9]+', node):
            raise ValueError('Original input contains a reserved compact reference string')
        body = serialized(node)
        if len(body) > smallest_reference:counts[body] += 1
        if isinstance(node, dict):
            for child in node.values():count(child)
        elif isinstance(node, list):
            for child in node:count(child)
    count(value)
    # Actual dependency edges are often 86--95 characters: the old96-character
    # cutoff duplicated them throughout complete TRAIN histories. Share a value
    # when its repeated literal cost exceeds a conservative reference+pool cost.
    largest_identity = str(len(counts))
    reference_cost = len(serialized('@' + largest_identity))
    entry_cost = len(serialized(largest_identity)) + 2
    eligible = {body for body, n in counts.items() if n > 1
        and n * len(body) > len(body) + entry_cost + n * reference_cost}
    pool, identities = {}, {}
    def children(node):
        if isinstance(node, dict):return {key: encode(child) for key, child in node.items()}
        if isinstance(node, list):return [encode(child) for child in node]
        return node
    def encode(node):
        body = serialized(node)
        if body not in eligible:return children(node)
        if body not in identities:
            identity = str(len(identities));identities[body] = identity
            pool[identity] = children(node)
        return '@' + identities[body]
    task = encode(value)
    # Collapsing a repeated parent can leave a child referenced only once.
    # Inline those entries: they no longer save storage, and their contents
    # remain exact. The reference syntax and teacher instructions do not change.
    references = Counter()
    def references_in(node):
        if isinstance(node, str) and re.fullmatch(r'@[0-9]+', node):
            references[node[1:]] += 1
        elif isinstance(node, dict):
            for child in node.values():references_in(child)
        elif isinstance(node, list):
            for child in node:references_in(child)
    references_in(task)
    for node in pool.values():references_in(node)
    inline = {key for key, n in references.items() if n == 1}
    def compact(node):
        if isinstance(node, str) and re.fullmatch(r'@[0-9]+', node) and node[1:] in inline:
            return compact(pool[node[1:]])
        if isinstance(node, dict):
            return {key: compact(child) for key, child in node.items()}
        if isinstance(node, list):return [compact(child) for child in node]
        return node
    task = compact(task)
    pool = {key: compact(node) for key, node in pool.items() if key not in inline}
    return {'encoding': 'lossless_shared_JSON_values_v3', 'shared_values': pool, 'task': task}


def unpack(envelope):
    encoding = envelope['encoding']
    if encoding not in ('lossless_shared_JSON_values_v2', 'lossless_shared_JSON_values_v3'):
        raise ValueError('Unknown teacher transport')
    visiting = set()
    def reference(identity):
        if identity in visiting:raise ValueError('Cyclic teacher transport reference')
        visiting.add(identity);value = decode(envelope['shared_values'][identity]);visiting.remove(identity)
        return value
    def decode(node):
        if encoding == 'lossless_shared_JSON_values_v3' and isinstance(node, str) and re.fullmatch(r'@[0-9]+', node):
            return reference(node[1:])
        if isinstance(node, dict):
            if encoding == 'lossless_shared_JSON_values_v2' and set(node) == {REFERENCE}:
                return reference(node[REFERENCE])
            return {key: decode(child) for key, child in node.items()}
        if isinstance(node, list):return [decode(child) for child in node]
        return node
    return decode(envelope['task'])


def pack_programs(value, *, extra_program_fields=(), program_line_segments=False):
    """Share real unchanged helpers without normalizing any program bytes."""
    fields = {'source_program', 'planner_program', 'composition_program', 'decision_program', 'binding_program'}
    fields.update(extra_program_fields)
    def split(code):
        if program_line_segments:
            # Revision histories contain many nearly identical functions. Exact
            # lines expose their unchanged interiors to the existing dictionary;
            # this also preserves failed Python programs without parsing them.
            return {PROGRAM_SEGMENTS: code.splitlines(keepends=True)}
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return code  # A preserved failed program is data, not a transport failure.
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
    def source_segments(node):
        text, units = node.get('full_source_text'), node.get('source_units')
        if not isinstance(text, str) or not isinstance(units, list):
            return None
        intervals = [u for u in units if isinstance(u, dict) and type(u.get('start')) is int
            and type(u.get('end')) is int and isinstance(u.get('text'), str)]
        cursor, segments = 0, []
        for unit in sorted(intervals, key=lambda u: (u['start'], u['end'])):
            start, end = unit['start'], unit['end']
            if start < cursor or end <= start or end > len(text) or text[start:end] != unit['text']:
                continue
            segments.extend([text[cursor:start], unit['text']])
            cursor = end
        if not segments:
            return None
        segments.append(text[cursor:])
        assert ''.join(segments) == text
        return segments
    def factor(node):
        if isinstance(node, dict):
            if PROGRAM_SEGMENTS in node or SOURCE_SEGMENTS in node:
                raise ValueError('Original task contains the reserved program-segment key')
            parts = source_segments(node)
            return {k: {SOURCE_SEGMENTS:parts} if k=='full_source_text' and parts is not None else
                    split(v) if k in fields and isinstance(v, str) else factor(v)
                    for k, v in node.items()}
        if isinstance(node, list):
            return [factor(v) for v in node]
        return node
    result = pack(factor(value))
    result['program_encoding'] = 'exact_python_and_source_segments_v2'
    return result


def unpack_programs(envelope):
    if envelope.get('program_encoding') != 'exact_python_and_source_segments_v2':
        raise ValueError('Explicit exact-program encoding required')
    def restore(node):
        if isinstance(node, dict):
            if set(node) in ({PROGRAM_SEGMENTS}, {SOURCE_SEGMENTS}):
                parts = node[next(iter(node))]
                if not isinstance(parts, list) or any(not isinstance(p, str) for p in parts):
                    raise ValueError('Program segments must remain literal strings')
                return ''.join(parts)
            return {k: restore(v) for k, v in node.items()}
        if isinstance(node, list):
            return [restore(v) for v in node]
        return node
    return restore(unpack(envelope))
