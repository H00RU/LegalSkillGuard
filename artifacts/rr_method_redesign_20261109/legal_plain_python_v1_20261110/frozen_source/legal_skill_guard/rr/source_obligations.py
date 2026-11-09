"""Learned source-role interfaces with executable semantic obligations.

Source quotes establish membership/provenance, not NL truth. All proof results
are relative to the supplied domain and obligations; source review is separate.
"""
import ast
from dataclasses import dataclass
import z3
from .semantic_contracts import ContractError, expression, variables


@dataclass
class SourceModule:
    raw: dict
    signature: dict
    symbols: dict
    domain: object
    program: object
    obligations: list
    quote_positions: dict


def _positions(text, quote):
    if not isinstance(quote, str) or not quote:
        raise ContractError('A nonempty source quote is required')
    positions, start = [], 0
    while True:
        start = text.find(quote, start)
        if start < 0:
            break
        positions.append([start, start + len(quote)])
        start += 1
    if not positions:
        raise ContractError('Quote does not occur verbatim in the source: ' + quote[:100])
    return positions


def compile_module(value, source_text):
    required = {'inputs', 'output_type', 'domain', 'domain_quote', 'expression', 'rule_quote', 'obligations', 'unresolved'}
    if not isinstance(value, dict) or set(value) != required:
        raise ContractError('Source module fields do not match the sealed contract')
    if not value['inputs']:
        raise ContractError('A generic module must declare its real input roles')
    signature, positions = {}, {}
    for i, role in enumerate(value['inputs']):
        if set(role) != {'name', 'type', 'meaning', 'origin', 'quote'}:
            raise ContractError('Input role fields differ')
        name = role['name']
        if name == 'result' or name in signature or not name.isidentifier():
            raise ContractError('Duplicate/reserved/invalid input role')
        if role['type'] not in {'integer', 'boolean'} or role['origin'] not in {'case', 'external_rule'}:
            raise ContractError('Unknown role type or provenance category')
        if not isinstance(role['meaning'], str) or not role['meaning'].strip():
            raise ContractError('Every role requires an explicit semantic description')
        signature[name] = role['type']
        positions[f'input:{name}'] = _positions(source_text, role['quote'])
    if value['output_type'] not in {'integer', 'boolean'}:
        raise ContractError('Unsupported output type')
    symbols = variables(signature)
    domain = expression(value['domain'], symbols)
    if not z3.is_bool(domain):
        raise ContractError('Domain must be Boolean')
    solver = z3.Solver(); solver.set(timeout=3000); solver.add(domain)
    if solver.check() != z3.sat:
        raise ContractError('Empty or undecidable declared domain')
    positions['domain'] = _positions(source_text, value['domain_quote'])
    positions['program'] = _positions(source_text, value['rule_quote'])
    program = expression(value['expression'], symbols)
    if (value['output_type'] == 'integer') != z3.is_int(program):
        raise ContractError('Declared output type does not match the program')
    result = variables({'result': value['output_type']})['result']
    obligations = []
    names = set()
    for row in value['obligations']:
        if set(row) != {'name', 'condition', 'assertion', 'quote'} or row['name'] in names:
            raise ContractError('Obligation fields or names differ')
        names.add(row['name'])
        condition = expression(row['condition'], symbols)
        assertion = expression(row['assertion'], {**symbols, 'result': result})
        if not z3.is_bool(condition) or not z3.is_bool(assertion):
            raise ContractError('Obligation condition and assertion must be Boolean')
        if 'result' not in {n.id for n in ast.walk(ast.parse(row['assertion'], mode='eval')) if isinstance(n, ast.Name)}:
            raise ContractError('A postcondition must constrain result; input restrictions belong in domain')
        positions['obligation:' + row['name']] = _positions(source_text, row['quote'])
        obligations.append((row['name'], condition, assertion, result))
    if not obligations:
        raise ContractError('No semantic obligation was supplied')
    return SourceModule(value, signature, symbols, domain, program, obligations, positions)


def _plain(model, term):
    value = model.eval(term, model_completion=True)
    return z3.is_true(value) if z3.is_bool(value) else value.as_long()


def verify(module):
    rows = []
    for name, condition, assertion, result in module.obligations:
        solver = z3.Solver(); solver.set(timeout=3000)
        solver.add(module.domain, condition)
        reachable = solver.check()
        row = {'name': name, 'condition_reachable': str(reachable)}
        if reachable != z3.sat:
            row['status'] = 'vacuous_or_unknown_not_verified'
        else:
            solver.add(result == module.program, z3.Not(assertion))
            status = solver.check()
            row['status'] = 'verified' if status == z3.unsat else ('refuted' if status == z3.sat else 'unknown')
            if status == z3.sat:
                model = solver.model()
                row['witness'] = {k: _plain(model, v) for k, v in module.symbols.items()}
                row['result'] = _plain(model, module.program)
        rows.append(row)
    return {'obligations': rows, 'all_supplied_obligations_verified': all(r['status'] == 'verified' for r in rows),
            'unresolved': list(module.raw['unresolved']),
            'source_coverage_or_NL_faithfulness_proved': False,
            'signature_was_model_generated': True}


def bind_and_assess(module, bindings, query_value, *, comparison='eq'):
    """Keep absent fields symbolic. A known value requires exact input type."""
    if set(bindings) != set(module.signature):
        raise ContractError('Bindings must explicitly cover the learned interface; use null for unknown')
    solver = z3.Solver(); solver.set(timeout=3000); solver.add(module.domain)
    for name, kind in module.signature.items():
        value = bindings[name]
        if value is None:
            continue
        if type(value) is not (int if kind == 'integer' else bool):
            raise ContractError('Concrete role value has the wrong type: ' + name)
        solver.add(module.symbols[name] == value)
    if solver.check() != z3.sat:
        raise ContractError('Bindings contradict the source module domain')
    if comparison == 'eq':
        claim = module.program == query_value
    elif comparison == 'applies':
        if not z3.is_bool(module.program):
            raise ContractError('Applies requires a Boolean output')
        claim = module.program
    else:
        raise ContractError('Unsupported original query comparison')
    possibilities = []
    for truth in (True, False):
        solver.push(); solver.add(claim if truth else z3.Not(claim)); status = solver.check(); solver.pop()
        if status == z3.unknown:
            return {'status': 'solver_unknown', 'answer': None}
        if status == z3.sat:
            possibilities.append(truth)
    return {'status': 'claim_stable' if len(possibilities) == 1 else 'translation_or_observation_unresolved',
            'answer': ('Entailment' if possibilities == [True] else 'Contradiction' if possibilities == [False] else None),
            'possible_claim_values': possibilities, 'unknown_roles': [k for k,v in bindings.items() if v is None],
            'source_semantics_not_inferred_from_stability': True}
