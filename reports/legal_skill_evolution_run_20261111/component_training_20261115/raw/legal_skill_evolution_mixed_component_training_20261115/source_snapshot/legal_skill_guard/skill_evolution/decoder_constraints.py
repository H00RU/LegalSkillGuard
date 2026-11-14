"""Separate unsupported conditional decoding from unchanged host validation.

The installed xgrammar converter prioritizes allOf over sibling properties.
For an allOf containing only if/then/else clauses, it consequently accepts an
unconstrained item and loses the enclosing object's declared fields. Conditional
clauses remain mandatory in the ORIGINAL prompt and host schema; removing them
only from the wire grammar restores enforcement of the supported siblings.
"""
from .runtime import decoder_schema


def decoding_schema(schema):
    wire, host_checks = decoder_schema(schema)

    def visit(node, path):
        if not isinstance(node, dict):
            return
        clauses = node.get('allOf', [])
        deferred = [i for i, clause in enumerate(clauses)
            if isinstance(clause, dict) and 'if' in clause
            and set(clause) <= {'if', 'then', 'else'}]
        if deferred:
            host_checks.extend(path + '/allOf/' + str(i) for i in deferred)
            remaining = [clause for i, clause in enumerate(clauses) if i not in deferred]
            if remaining:
                node['allOf'] = remaining
            else:
                node.pop('allOf')
        for key in ('properties', '$defs', 'definitions'):
            for name, child in node.get(key, {}).items():
                visit(child, path + '/' + key + '/' + name)
        for key in ('items', 'additionalProperties', 'not', 'if', 'then', 'else'):
            visit(node.get(key), path + '/' + key)
        for key in ('allOf', 'anyOf', 'oneOf', 'prefixItems'):
            for i, child in enumerate(node.get(key, [])):
                visit(child, path + '/' + key + '/' + str(i))

    visit(wire, '')
    return wire, host_checks
