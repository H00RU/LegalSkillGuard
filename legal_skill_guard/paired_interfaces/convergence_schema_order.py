"""Normalize reversible field priorities supplied in original or alias notation."""

import re

import jsonschema

from legal_skill_guard.paired_interfaces.convergence_schema_control import schema_proposal


def normalize_proposal(proposal, public_fields):
    jsonschema.validate(proposal, schema_proposal())
    fields = set(public_fields)
    entries = proposal['field_aliases']
    aliases = {row['original']: row['alias'] for row in entries}
    if (len(aliases) != len(entries) or not aliases.keys() <= fields
            or any(not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', alias) for alias in aliases.values())
            or len(proposal['reader_guidance'].split()) > 90):
        raise ValueError('Use aliases of declared public fields and a reader guide of at most 90 words')
    names = {field: {field} for field in fields}
    for field, alias in aliases.items():
        names.setdefault(alias, set()).add(field)
    first = []
    for name in proposal['fields_first']:
        if len(names.get(name, ())) != 1:
            raise ValueError('A field preference has no unambiguous original public name')
        first.append(next(iter(names[name])))
    if len(first) != len(set(first)):
        raise ValueError('A field preference specifies the same original field multiple times')
    return {**proposal, 'fields_first': first}
