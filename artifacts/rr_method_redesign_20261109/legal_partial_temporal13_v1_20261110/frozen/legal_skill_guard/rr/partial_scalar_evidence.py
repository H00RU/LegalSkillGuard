"""Ordinary symbolic execution with only independently checked scalar evidence.

Unverified observations remain outside the solver. This is a shared correctness
component, not a learned mechanism or a natural-language fidelity certificate.
"""
import z3

from .semantic_contracts import ContractError, expression, variables


def certify(expression_text, signature, domain_text, checked_bindings, *, quarantined=()):
    if set(checked_bindings) - set(signature):
        raise ContractError('Evidence names do not belong to this source contract')
    known = {}
    for name, row in checked_bindings.items():
        if set(row) != {'value', 'evidence'} or not row['evidence']:
            raise ContractError('Checked scalar values require explicit source evidence')
        value = row['value']
        expected = {'integer': int, 'boolean': bool}.get(signature[name])
        if expected is None or type(value) is not expected:
            raise ContractError('Checked evidence has the wrong scalar type')
        known[name] = value
    syms = variables(signature); program = expression(expression_text, syms); domain = expression(domain_text, syms)
    if not z3.is_bool(program) or not z3.is_bool(domain):
        raise ContractError('This bounded proof path requires Boolean programme and domain')

    def possible(bindings):
        constraints = [syms[k] == v for k,v in bindings.items()]
        values = []
        for claim in [False, True]:
            solver = z3.Solver(); solver.set(timeout=3000)
            solver.add(domain, *constraints, program == claim)
            result = solver.check()
            if result == z3.unknown:
                raise ContractError('Symbolic proof unresolved: '+solver.reason_unknown())
            if result == z3.sat: values.append(claim)
        if not values: raise ContractError('Inconsistent checked evidence/domain; no explosion-based answer')
        return values

    values = possible(known)
    support = dict(known)
    if len(values) == 1:
        # Deterministic deletion yields an inclusion-minimal sufficient set,
        # not a minimum-cost policy and not a new learned selection algorithm.
        for name in sorted(known):
            trial = {k:v for k,v in support.items() if k != name}
            if possible(trial) == values: support = trial
        assert possible(support) == values
    else: support = {}
    dropped = {name: possible({k:v for k,v in support.items() if k != name}) for name in support}
    return {'possible_values': values,
        'answer': 'Entailment' if values == [True] else 'Contradiction' if values == [False] else None,
        'checked_bindings': checked_bindings, 'unknown_inputs': [k for k in signature if k not in known],
        'quarantined_observations': list(quarantined),
        'proof_support': {k: checked_bindings[k] for k in support},
        'support_verified_over_all_other_input_values': len(values) == 1,
        'withhold_each_support_value': dropped,
        'evidence_scope': 'Only independently checked source values enter the solver; quarantined claims never become assertions.',
        'natural_language_fidelity_or_record_completeness_proved_here': False,
        'selection': 'standard inclusion-minimal SMT evidence deletion, public to all controls',
        'new_learned_mechanism': False}
