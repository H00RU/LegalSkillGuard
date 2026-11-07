"""Canonical typed SourceIR wire, with one nullable scope slot per rule unit.

Scope slots contain executable ASTs or remain untranslated. Null never means a
false condition. All source, type, coverage and execution checks remain in the
existing compiler; no Python-expression strings are accepted on this path.
"""
from copy import deepcopy

from .source_program import program_schema
from .source_structure import inspect_source
from .strict_contract import obj, ref
from .wire_validation import validate_wire


COMPILER_FIELDS=('bindings','observations','rule_residuals','nodes','scopes','clauses','query')


def _rules(source):
    structure=inspect_source(source)
    return [c.id for c in structure.ledger.clauses if structure.roles[c.id]['role']=='rule']


def compiler_response_schema(source,library=None):
    schema=program_schema(source,library)
    entry=deepcopy(schema['properties']['scopes']['items'])
    del entry['properties']['source'];entry['required'].remove('source')
    schema['$defs']['scope_entry']=entry
    schema['properties']['scopes']=obj({sid:{'anyOf':[{'type':'null'},ref('scope_entry')]} for sid in _rules(source)})
    schema['properties']={key:schema['properties'][key] for key in COMPILER_FIELDS}
    schema['required']=list(COMPILER_FIELDS)
    return schema


def decode_compiler_response(response,source,library=None):
    validate_wire(response,compiler_response_schema(source,library))
    program=deepcopy(response)
    program['scopes']=[{'name':row['name'],'source':sid,'condition':row['condition']}
        for sid,row in response['scopes'].items() if row is not None]
    validate_wire(program,program_schema(source,library))
    return program


def encode_compiler_program(program,source):
    by_source={}
    for row in program['scopes']:
        if row['source'] in by_source:raise ValueError('One accepted scope per source unit')
        by_source[row['source']]={'name':row['name'],'condition':deepcopy(row['condition'])}
    rules=_rules(source)
    if not set(by_source)<=set(rules):raise ValueError('Scope provenance must be an actual rule unit')
    result=deepcopy(program)
    result['scopes']={sid:by_source.get(sid) for sid in rules}
    return {key:result[key] for key in COMPILER_FIELDS}
