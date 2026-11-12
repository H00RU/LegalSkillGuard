"""Lossless sharing of repeated JSON values in a complete teacher input."""
from collections import Counter
import json

REFERENCE = '__lsg_shared_value__'
INSTRUCTION = ('The input is losslessly reference-encoded JSON. Read task as the original input; '
    'each singleton object {"__lsg_shared_value__":"vN"} denotes shared_values["vN"], '
    'recursively. Repeated source text, programs and execution records are shared, never omitted. '
    'References are storage identifiers, not legal rules, labels or source identities. '
    'All instructions and requested output schema remain unchanged.')


def serialized(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def pack(value):
    counts = Counter()
    def count(node):
        body = serialized(node)
        if len(body) >= 256:counts[body] += 1
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
