"""Shared, deterministic source-bound views of already generated expressions.

This is ordinary AST projection for a finite source pattern, not a learned legal
rule or a substitute for source fidelity. Raw modules remain immutable. A local
substitution value is kept distinct from the module's final taxpayer value.
"""
import ast
from datetime import date, datetime
import re

import z3

from .semantic_contracts import ContractError, evaluate


def substitution_view(module, clause, governing_text, authority):
    pairs = re.findall(r'substituting "\$([0-9,]+)" for "\$([0-9,]+)"', clause)
    if len(pairs) != 1:
        raise ContractError('One explicit source substitution is required')
    new, old = [int(x.replace(',', '')) for x in pairs[0]]
    candidates = []
    for node in ast.walk(ast.parse(module.raw['expression'], mode='eval')):
        if not (isinstance(node, ast.IfExp) and isinstance(node.test, ast.Name)
                and isinstance(node.body, ast.Constant) and isinstance(node.orelse, ast.Constant)):
            continue
        if (type(node.body.value), type(node.orelse.value)) != (int, int):
            continue
        if (node.body.value, node.orelse.value) != (new, old):
            continue
        role = next((r for r in module.raw['inputs'] if r['name'] == node.test.id), None)
        if role is None or role['type'] != 'boolean' or role['quote'] not in governing_text:
            continue
        candidates.append((node, role))
    unique = {ast.dump(node, include_attributes=False) for node, _ in candidates}
    if len(unique) != 1:
        raise ContractError('No unique existing AST function matches the source substitution')
    node, role = candidates[0]
    flag = role['name']
    outside = [value for name, value in module.symbols.items() if name != flag]
    projection = z3.Exists(outside, module.domain) if outside else module.domain
    solver = z3.Solver(); solver.set(timeout=3000); solver.add(z3.Not(projection))
    if solver.check() != z3.unsat:
        raise ContractError('Unprojected domain restrictions may constrain the selected input')
    return {'authority': authority, 'scope': 'local_substitution_operand_not_final_deduction',
            'expression': ast.get_source_segment(module.raw['expression'], node),
            'signature': {flag: 'boolean'}, 'condition_name': flag,
            'condition_quote': role['quote'], 'source_substitution_clause': clause,
            'new_amount': new, 'old_amount': old, 'existing_AST_occurrences': len(candidates),
            'domain_existential_projection_is_true': True,
            'natural_language_faithfulness_proved': False}


def calendar_year_condition(quote, year):
    """Original SARA calendar-year convention; no unknown date is invented."""
    if year is None:
        return None
    if type(year) is not int:
        raise ContractError('The query year must be an integer')
    match = re.fullmatch(r'(?:a )?taxable year beginning after (.+), and before (.+)', quote)
    if not match:
        raise ContractError('Unsupported temporal quote; do not infer its boundaries')
    try:
        lower, upper = [datetime.strptime(x, '%B %d, %Y').date() for x in match.groups()]
        beginning = date(year, 1, 1)
    except ValueError as exc:
        raise ContractError(str(exc)) from exc
    return lower < beginning < upper


def assess_view(view, binding, claimed_amount, *, query_authority):
    if query_authority != view['authority']:
        raise ContractError('The query cites a different legal output scope')
    if set(binding) != set(view['signature']) or type(claimed_amount) is not int:
        raise ContractError('Explicit typed view binding and integer claim required')
    flag = binding[view['condition_name']]
    if flag is not None and type(flag) is not bool:
        raise ContractError('A temporal condition must be Boolean or explicit unknown')
    if flag is None:
        return {'answer': None, 'applicable': None, 'value': None, 'basis': 'unknown_governing_condition'}
    if flag is False:
        return {'answer': 'Contradiction', 'applicable': False, 'value': None,
                'basis': 'source_clause_inapplicable_not_a_default_value'}
    value = evaluate(view['expression'], view['signature'], binding)
    return {'answer': 'Entailment' if value == claimed_amount else 'Contradiction',
            'applicable': True, 'value': value,
            'basis': 'existing_source_generated_AST_at_the_cited_local_scope'}
