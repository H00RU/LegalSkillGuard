"""Compact teacher transport for one-predicate executable program proposals."""

import ast

import jsonschema

from legal_skill_guard.paired_interfaces.control_learning import program_from_proposal
from legal_skill_guard.paired_interfaces.scope_learning import strict_json
from legal_skill_guard.skill_evolution.native import record_schema


SCHEMA = record_schema({
    'predicate_prompt': {'type': 'string'},
    'schema_mode': {'type': 'string', 'enum': ['native', 'fixed']},
    'predicate_schema_json': {'type': 'string'},
    'compose_source': {'type': 'string'},
    'rationale': {'type': 'string'},
})

CONTRACT = (
    'Return only the requested JSON and do not use tools or run commands. Use one predicate named read and '
    'one pure compose function. In native mode set predicate_schema_json to "{}" and predict("read", input) '
    'will return a mapping of task ID to raw native answer after decoding the original evidence wire. In fixed '
    'mode return a strict JSON schema that reads the reusable local fields needed for deterministic composition. '
    'The function signature is compose(inputs, predict, extractors). Its output is the mapping from every native '
    'task ID to its typed answer, using the source public facts and rules. Inputs expose public, dataset, '
    'native_answer_schema, native_wire_schema, shared_assets and legal_tools. Pass the complete supplied public '
    'input to the predicate. Retain exact evidence ids whenever the native wire expects evidence. '
    'Do not invent missing facts, roles, labels or laws. The driver validates code and applies the same budget.'
)


def compile_proposal(value, sources):
    jsonschema.validate(value, SCHEMA)
    predicate_schema = strict_json(value['predicate_schema_json'])
    if not isinstance(predicate_schema, dict) or (value['schema_mode'] == 'native' and predicate_schema):
        raise ValueError('A compact proposal must preserve the native wire or declare one typed predicate schema')
    proposal = {'program': {'predicates': [{
        'id': 'read', 'prompt': value['predicate_prompt'], 'schema_mode': value['schema_mode'],
        'schema_json': value['predicate_schema_json'],
    }], 'extractors': [], 'composition': value['compose_source']},
        'policy_rationale': value['rationale'], 'changes_from_previous': []}
    return program_from_proposal(proposal, sources)


def compact_native_passthrough(program):
    """Use the common native reader input for a direct identity composer.

    The native wire schema already appears in the predicate system message.
    The full public task and answer schema are retained. The deterministic
    tool inventory and its host assets stay on the composition side.
    """
    predicate, = program['predicates']
    if predicate['schema_mode'] != 'native':
        return program
    composition = ast.parse(program['composition'])
    original = ast.parse('def compose(inputs, predict, extractors):\n    return predict("read", inputs)\n')
    if ast.dump(composition) != ast.dump(original):
        return program
    return {**program, 'composition': (
        'def compose(inputs, predict, extractors):\n'
        '    return predict("read", {"public": inputs["public"], '
        '"answer_schema": inputs["native_answer_schema"]})\n'
    )}
