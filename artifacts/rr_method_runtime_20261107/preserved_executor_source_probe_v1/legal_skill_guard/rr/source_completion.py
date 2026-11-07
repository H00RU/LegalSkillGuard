"""Source-derived finite observations; unrecognized clauses retain unknown scope.

The audited declaration grammar denotes constant, typed rule values. A value is
the entire observation of such a clause, not an abstract effect on the answer.
Only public declarations establish domains. Model claims never establish scope.
"""
from __future__ import annotations

import json
import re
from dataclasses import replace

from .coverage import FiniteTheory, Residual, digest


def declarations(ledger):
    result = {}
    for clause in ledger.clauses:
        text = ledger.text[clause.start:clause.end]
        boolean = re.fullmatch(r'Boolean (b_[A-Za-z0-9_]+) = (true|false)\.', text)
        finite = re.fullmatch(r'(Integer|Enum) ([ns]_[A-Za-z0-9_]+) in (\[[^\n]+\]) = (.+)\.', text)
        if boolean:
            name, raw = boolean.groups()
            domain, value = (False, True), raw == 'true'
        elif finite:
            kind, name, raw_domain, raw = finite.groups()
            if (kind == 'Integer') != name.startswith('n_'):
                continue
            try:
                domain, value = tuple(json.loads(raw_domain)), json.loads(raw)
            except (ValueError, TypeError):
                continue
            wanted = int if kind == 'Integer' else str
            if not domain or len(domain) > 64 or any(type(v) is not wanted for v in domain):
                continue
            if type(value) is not wanted or value not in domain or len(set(domain)) != len(domain):
                continue
        else:
            continue
        if name in result:
            raise ValueError('A finite rule has multiple public definitions')
        result[name] = {'source': clause.id, 'domain': domain, 'literal': value}
    return result


def expression_theory(ledger, slots, query, accepted, bindings):
    specs = declarations(ledger)
    by_name = {b['name']: b for b in bindings}
    domains, residuals = {}, []
    context = tuple(sorted(accepted))
    for name, spec in specs.items():
        if name in slots:
            binding = by_name[name]
            if binding['source'] != spec['source'] or digest(slots[name]) != digest(spec['literal']):
                raise ValueError('Finite rule binding disagrees with its complete public declaration')
    for i, clause in enumerate(ledger.clauses):
        if clause.id in accepted:
            ledger.clauses[i] = replace(clause, state='compiled')
            continue
        declared = [(name, spec) for name, spec in specs.items() if spec['source'] == clause.id]
        if declared:
            name, spec = declared[0]
            if name in slots:
                raise ValueError('A bound finite rule must retain its source coverage')
            domains[name] = spec['domain']
            residuals.append(Residual(clause.id, (name,), 'public_structure', False))
            ledger.clauses[i] = replace(clause, context=context)
        else:
            # No proposed source scope or missing semantic rule is filled in.
            residuals.append(Residual(clause.id, (), 'unverified_llm', True))
    return FiniteTheory(ledger, slots, domains, query, residuals,
        containment_assumptions=('complete constant finite-declaration grammar for verified residuals',
                                'accepted source-linked query/translation is faithful'))
