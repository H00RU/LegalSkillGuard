"""Execute learned case-observation adapters around an unchanged legal kernel.

The host supplies no relationship inversion, legal rule or factual default.
Quoted case witnesses and nominal argument types are necessary, not a proof of
semantic correctness. Alternative bindings remain alternatives; an unknown or
disagreeing execution is never replaced by a guessed answer.
"""
from copy import deepcopy
import ast
import json

import jsonschema

from .objects import digest
from .span_compiler import execute_json, validate_procedure


NATIVE = {'Entailment', 'Contradiction'}


def validate_adapter(program, *, excluded_source_ids=()):
    validate_procedure(program, allow_helpers=True)
    forbidden = NATIVE | set(excluded_source_ids)
    for node in ast.walk(ast.parse(program)):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in forbidden:
            raise ValueError('An observation adapter cannot encode a native answer or source identity')
    return program


def checked_witnesses(witnesses, public):
    if not witnesses:
        raise ValueError('An instantiated case view needs current factual/question witnesses')
    result = []
    for witness in witnesses:
        if set(witness) != {'field', 'quote'} or witness['field'] not in ('facts', 'question'):
            raise ValueError('Case observation witnesses cannot come only from the statute')
        text = public.get(witness['field'])
        quote = witness['quote']
        if not isinstance(text, str) or not isinstance(quote, str) or not quote or quote not in text:
            raise ValueError('Case witness is not verbatim in the current field')
        result.append(deepcopy(witness))
    return result


def check_bindings(value, fields, public):
    if set(value) != {'bindings', 'unresolved'} or not isinstance(value['bindings'], list) or not isinstance(value['unresolved'], list):
        raise ValueError('An observation adapter returns explicit binding alternatives and unresolved reasons')
    result = []
    for row in value['bindings']:
        if set(row) != {'inputs', 'witnesses'} or not isinstance(row['inputs'], dict):
            raise ValueError('One coherent case-input assignment per binding alternative')
        if not set(row['inputs']) <= set(fields):
            raise ValueError('Adapter invented an undeclared legal input')
        for name, actual in row['inputs'].items():
            if actual is None:
                raise ValueError('Unknown kernel inputs are omitted, not null factual values')
            jsonschema.validate(actual, {'type': fields[name]['type']})
        witnesses = checked_witnesses(row['witnesses'], public)
        result.append({'inputs': deepcopy(row['inputs']), 'witnesses': witnesses})
    return {'bindings': result, 'unresolved': deepcopy(value['unresolved']),
        'case_semantics_certified_by_types_and_quotes': False}


def apply_adapter(contract, kernel, public, raw_observation, *, literal_context):
    fields = json.loads(kernel['input_fields_json'])
    validate_adapter(contract['binding_program'])
    value = execute_json(contract['binding_program'], {'kernel': kernel,
        'public_case': {'facts': public['facts'], 'question': public['question']},
        'literal_context': literal_context, 'observation': raw_observation}, {}, allow_helpers=True)
    return check_bindings(value, fields, public)


def kernel_execution(kernel, binding):
    value = execute_json(kernel['program'], deepcopy(binding), deepcopy(kernel.get('premises', {})), allow_helpers=True)
    if 'answer' not in value:
        raise ValueError('Legal kernel did not return its declared answer')
    handled = value.get('handled', value['answer'] is not None)
    if type(handled) is not bool or handled and value['answer'] not in NATIVE:
        raise ValueError('A legal kernel returned an invalid native result')
    if kernel.get('scope') == 'sufficient_positive_only' and value['answer'] != 'Entailment':
        return {'handled': False, 'answer': None,
            'reason': 'A_negative_subrule_alone_does_not_refute_the_parent_clause'}
    return {**value, 'handled': handled}


def execute_alternatives(kernel, grounded):
    """Use the kernel's execution equivalence; never select a favorable row."""
    executed = []
    for row in grounded['bindings']:
        try:
            value = kernel_execution(kernel, row['inputs'])
            executed.append({'inputs': row['inputs'], 'witnesses': row['witnesses'], 'execution': value})
        except (ValueError, KeyError, TypeError) as exc:
            executed.append({'inputs': row['inputs'], 'witnesses': row['witnesses'],
                'execution': {'handled': False, 'answer': None, 'error': type(exc).__name__ + ': ' + str(exc)}})
    answers = {r['execution']['answer'] for r in executed if r['execution']['handled']}
    complete = bool(executed) and not grounded['unresolved'] and all(r['execution']['handled'] for r in executed)
    consistent = complete and len(answers) == 1
    differences = set()
    for a in executed:
        for b in executed:
            if a['execution']['answer'] == b['execution']['answer']:
                continue
            for name in set(a['inputs']) | set(b['inputs']):
                if a['inputs'].get(name) != b['inputs'].get(name):
                    differences.add(name)
    return {'handled': consistent, 'answer': next(iter(answers)) if consistent else None,
        'binding_executions': executed, 'answer_relevant_binding_differences': sorted(differences),
        'unresolved': grounded['unresolved'], 'kernel_sha256': digest(kernel),
        'not_a_binding_coverage_or_source_semantics_certificate': True,
        'no_favorable_binding_or_default_answer_selected': True}
