"""Call teacher-acquired statutory sub-conclusions by their explicit source head.

The host recognizes literal query syntax, binds case values and compares a
computed property with a native claim. Every legal condition remains in the
teacher program. No rule, applicability fact or missing value is supplied here.
"""
import ast
import math
import re

import jsonschema

from .claim_scope import CITATION, clause_identifier, parts
from .objects import digest
from .source_python import execute, validate


def query_frame(question):
    matches = list(CITATION.finditer(question))
    if len(matches) != 1:
        return None
    path = parts(matches[0])
    clause = path[0] + ''.join('('+p+')' for p in path[1:])
    amounts = list(re.finditer(r'(?:equal\s+to|equals|is)\s*\$?\s*([0-9][0-9,]*(?:\.[0-9]+)?)(?:\s*%)?(?![\w,]|\.\d)', question, re.I))
    if len(amounts) == 1:
        value = float(amounts[0].group(1).replace(',', ''))
        return {'clause': clause, 'kind': 'quantity', 'claim': value,
                'negated': bool(re.search(r'\bnot\s+equal|\bunequal|\bdoes\s+not\s+equal', question, re.I))}
    if not amounts and re.search(r'\bappl(?:y|ies|icable)\b|\bfalls?\s+under\b|\bcan\s+claim\s+an?\s+exemption\b', question, re.I):
        return {'clause': clause, 'kind': 'predicate', 'claim': True,
                'negated': bool(re.search(r"\bdoes\s+not\s+apply\b|\bdoesn't\s+apply\b|\bis\s+not\s+applicable\b", question, re.I))}
    return None


def compile_library(value, law_material):
    validate(value['program'])
    functions = {f.name: f for f in ast.parse(value['program']).body}
    units, heads = {}, set()
    for unit in value['units']:
        unit = dict(unit)
        if not re.fullmatch(r'\d+(?:\([A-Za-z0-9]+\))*', unit['clause']):
            citations = list(CITATION.finditer(unit['clause']))
            if len(citations) != 1 or citations[0].start() != 0:
                raise ValueError('A source head needs one explicit leading statutory identifier')
            components = parts(citations[0])
            unit['clause'] = components[0] + ''.join('('+p+')' for p in components[1:])
        if not unit['id'] or unit['id'] in units:
            raise ValueError('Distinct acquired rule-unit identifiers required')
        clause_identifier(unit['clause'])
        head = (unit['clause'], unit['kind'])
        if unit['kind'] not in ('predicate', 'quantity') or head in heads:
            raise ValueError('One unambiguous callable property per source head/kind')
        if unit['function'] not in functions:
            raise ValueError('Acquired callable function is missing')
        arguments = functions[unit['function']].args
        if (len(arguments.posonlyargs + arguments.args) != 1 or arguments.vararg or
                arguments.kwarg or arguments.kwonlyargs or arguments.defaults):
            raise ValueError('A source property function takes only its case-fact map')
        if not unit['quote'] or unit['quote'] not in law_material[unit['source_field']]:
            raise ValueError('Acquired rule has no exact supplied-source witness')
        names = [f['name'] for f in unit['fields']]
        if len(names) != len(set(names)) or any(not n for n in names):
            raise ValueError('Distinct explicit factual input names required')
        if any(f['type'] not in ('boolean', 'integer', 'number', 'string') or not f['question'] for f in unit['fields']):
            raise ValueError('Explicit primitive factual interface required')
        units[unit['id']] = unit; heads.add(head)
    return {'law_digest': digest(law_material), 'program': value['program'], 'units': units}


def entry_program(library, unit_id):
    """Call the declared function; preserve every acquired legal function AST."""
    function = library['units'][unit_id]['function']
    tree = ast.parse(library['program'])
    entry = next(f for f in tree.body if f.name == 'apply')
    entry.body = [ast.Return(value=ast.Call(func=ast.Name(id=function, ctx=ast.Load()),
        args=[ast.Subscript(value=ast.Name(id='inputs', ctx=ast.Load()),
                            slice=ast.Constant(value='facts'), ctx=ast.Load())], keywords=[]))]
    return ast.unparse(ast.fix_missing_locations(tree))


def plan(library, question, law_material):
    if digest(law_material) != library['law_digest']:
        raise ValueError('Current law differs from the acquired source version')
    frame = query_frame(question)
    matches = [u for u in library['units'].values() if frame and
               (u['clause'], u['kind']) == (frame['clause'], frame['kind'])]
    if len(matches) != 1:
        return {'supported': False, 'frame': frame, 'unit': None, 'fields': {}}
    unit = matches[0]
    return {'supported': True, 'frame': frame, 'unit': unit['id'],
            'fields': {f['name']: {'type': f['type'], 'question': f['question']} for f in unit['fields']}}


def evaluate(library, planned, known_case_values):
    if not planned['supported']:
        return {'answer': 'unknown', 'value': None, 'used_units': [],
                'open_dependencies': ['No acquired callable source head for this query.']}
    unit = library['units'][planned['unit']]
    if not set(known_case_values) <= {f['name'] for f in unit['fields']}:
        raise ValueError('Case binding outside the acquired unit interface')
    declarations = {f['name']: f for f in unit['fields']}
    for name, value in known_case_values.items():
        jsonschema.validate(value, {'type': declarations[name]['type']})
    # Neither native question/claim nor labels/source IDs enter legal execution.
    result = execute(entry_program(library, unit['id']), {'facts': known_case_values})
    if set(result) != {'value', 'used_units', 'open_dependencies'}:
        raise ValueError('Callable rule must return its property and proof obligations')
    if not isinstance(result['used_units'], list) or not set(result['used_units']) <= set(library['units']):
        raise ValueError('Rule execution cites an unacquired unit')
    if not isinstance(result['open_dependencies'], list) or any(not isinstance(x, str) for x in result['open_dependencies']):
        raise ValueError('Explicit unresolved proof obligations required')
    value = result['value']
    if value is None:
        return {'answer': 'unknown', **result}
    if result['open_dependencies']:
        raise ValueError('A claimed definite property still has blocking proof obligations')
    if unit['kind'] == 'predicate':
        if type(value) is not bool:
            raise ValueError('Predicate result must be boolean or unresolved')
        truth = value
    else:
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError('Quantity result must be finite numeric or unresolved')
        truth = value == planned['frame']['claim']
    if planned['frame']['negated']:
        truth = not truth
    return {'answer': 'Entailment' if truth else 'Contradiction', **result}
