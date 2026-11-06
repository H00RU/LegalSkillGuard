"""Bounded Horn closure with explicit polarity and shared-variable unification."""
from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass(frozen=True, order=True)
class Atom:
    predicate: str
    arguments: tuple[str, ...]
    positive: bool = True

    def negate(self) -> Atom:
        return Atom(self.predicate, self.arguments, not self.positive)


@dataclass(frozen=True)
class Rule:
    body: tuple[Atom, ...]
    head: Atom
    source: str


def variables(atom: Atom) -> set[str]:
    return {a for a in atom.arguments if a.startswith("?")}


def closure(facts: set[Atom], rules: list[Rule], query: Atom, *, max_rounds: int = 32,
            max_atoms: int = 65536, seconds: float = 5) -> dict:
    if any(variables(a) for a in facts) or variables(query):
        raise ValueError("Facts and query must be ground")
    for r in rules:
        if not r.source or not variables(r.head) <= {v for a in r.body for v in variables(a)}:
            raise ValueError("Rule needs source provenance and range-restricted variables")
    end = time.monotonic() + min(seconds, 5)
    known, trace = set(facts), []
    for round_id in range(max_rounds):
        if time.monotonic() >= end or len(known) > max_atoms:
            return {"answer": None, "status": "budget_exhausted", "trace": trace}
        new = set()
        for rule in rules:
            bindings = [({}, [])]
            for pattern in rule.body:
                matches = []
                for bound, premises in bindings:
                    for fact in sorted(known):
                        if time.monotonic() >= end:
                            return {"answer": None, "status": "budget_exhausted", "trace": trace}
                        if (fact.predicate, fact.positive, len(fact.arguments)) != (
                                pattern.predicate, pattern.positive, len(pattern.arguments)):
                            continue
                        current = dict(bound)
                        for formal, actual in zip(pattern.arguments, fact.arguments):
                            if formal.startswith("?"):
                                if formal in current and current[formal] != actual:
                                    break
                                current[formal] = actual
                            elif formal != actual:
                                break
                        else:
                            matches.append((current, premises + [fact]))
                bindings = matches
            for bound, premises in bindings:
                head = Atom(rule.head.predicate,
                            tuple(bound.get(a, a) for a in rule.head.arguments), rule.head.positive)
                if head not in known and head not in new:
                    new.add(head)
                    trace.append({"atom": head, "source": rule.source,
                                  "premises": premises, "round": round_id + 1})
        if not new:
            if query in known and query.negate() in known:
                return {"answer": None, "status": "conflict", "trace": trace}
            answer = "True" if query in known else "False" if query.negate() in known else "Unknown"
            return {"answer": answer, "status": "closure_complete", "trace": trace}
        known.update(new)
    return {"answer": None, "status": "budget_exhausted", "trace": trace}
