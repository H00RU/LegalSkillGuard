"""Exact finite completion semantics for method A.

This backend enumerates the *declared* semantic domain, never the connector
candidate pool H. It fails closed on size/time limits. Continuous arithmetic
requires a different backend: sampling a real interval is not a completion proof.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field, is_dataclass
from fractions import Fraction
from hashlib import sha256
from itertools import combinations, product
from typing import Any, Callable


def digest(value: Any) -> str:
    def encode(obj):
        if isinstance(obj, Fraction):
            return {"exact_rational": [obj.numerator, obj.denominator]}
        if is_dataclass(obj):
            return asdict(obj)
        if isinstance(obj, (set, frozenset)):
            return sorted(obj, key=digest)
        if hasattr(obj, "__rr_state__"):
            return obj.__rr_state__()
        raise TypeError(f"Unserializable semantic value: {type(obj).__name__}")
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                             separators=(",", ":"), allow_nan=False, default=encode).encode()).hexdigest()


@dataclass(frozen=True)
class Clause:
    id: str
    start: int
    end: int
    text_sha256: str
    state: str = "residual"
    context: tuple[str, ...] = ()


@dataclass
class SourceLedger:
    text: str
    clauses: list[Clause]

    @classmethod
    def from_text(cls, text: str) -> SourceLedger:
        # Every nonblank line, including headings and unrecognized fragments.
        units = [Clause(f"s{i}", m.start(), m.end(), sha256(m[0].encode()).hexdigest())
                 for i, m in enumerate(re.finditer(r"[^\n]+", text)) if m[0].strip()]
        result = cls(text, units)
        result.validate()
        return result

    def validate(self) -> None:
        ids = {c.id for c in self.clauses}
        if len(ids) != len(self.clauses):
            raise ValueError("Duplicate source unit")
        covered = set()
        for c in self.clauses:
            if not 0 <= c.start < c.end <= len(self.text):
                raise ValueError("Invalid source interval")
            if sha256(self.text[c.start:c.end].encode()).hexdigest() != c.text_sha256:
                raise ValueError("Source interval hash mismatch")
            if c.state not in {"compiled", "residual", "conflict"} or not set(c.context) <= ids:
                raise ValueError("Invalid state or dangling source reference")
            covered.update(range(c.start, c.end))
        if any(not ch.isspace() and i not in covered for i, ch in enumerate(self.text)):
            raise ValueError("Unregistered source text")

    def closure(self, selected: set[str]) -> set[str]:
        self.validate()
        by_id = {c.id: c for c in self.clauses}
        pending = list(selected)
        result = set()
        while pending:
            key = pending.pop()
            if key not in by_id:
                raise ValueError("Unknown source unit")
            if key not in result:
                result.add(key)
                pending.extend(by_id[key].context)
        return result

    @property
    def version(self) -> str:
        return digest({"text": self.text, "clauses": [asdict(c) for c in self.clauses]})


class Unsupported(ValueError):
    pass


def evaluate(node: Any, env: dict[str, Any]) -> Any:
    """Small data-only IR. Explicit variables; no eval, import or code generation."""
    from .public_horn import GroundHornQuery
    from .connector_completion import ConnectorQuery
    from .scoped_program import ScopedQuery
    if isinstance(node, GroundHornQuery):
        return node.evaluate(env)
    if isinstance(node, ConnectorQuery):
        return node.evaluate(env)
    if isinstance(node, ScopedQuery):
        return node.evaluate(env)
    if type(node) in (bool, int, str, Fraction) or node is None:
        return node
    if not isinstance(node, dict):
        raise Unsupported("IR literals must be bool, integer, enum string or null")
    if set(node) == {"var"}:
        if node["var"] not in env:
            raise Unsupported("Unbound IR variable")
        return env[node["var"]]
    if set(node) != {"op", "args"} or not isinstance(node["args"], list):
        raise Unsupported("Invalid expression")
    op, args = node["op"], node["args"]
    if op == "if" and len(args) == 3:
        cond = evaluate(args[0], env)
        if type(cond) is not bool:
            raise Unsupported("Nonboolean guard")
        return evaluate(args[1] if cond else args[2], env)
    values = [evaluate(a, env) for a in args]
    if op == 'number_at' and len(values) == 2:
        vector,index=values
        if (not isinstance(vector,list) or any(type(v) not in (int,Fraction) for v in vector)
                or type(args[1]) is not int or not 0 <= index < len(vector)):
            raise Unsupported('Number vector access needs exact values and an in-range literal index')
        return vector[index]
    if op == 'number_field' and len(values)==2:
        record,key=values
        if not isinstance(record,dict) or not isinstance(key,str) or key not in record:
            raise Unsupported('Numeric record access needs an existing string field; no default')
        if type(record[key]) not in (int,Fraction):
            raise Unsupported('Numeric record access cannot coerce a nonnumeric field')
        return record[key]
    if op == 'sum_numbers' and len(values)==1:
        vector=values[0]
        if not isinstance(vector,list) or any(type(v) not in (int,Fraction) for v in vector):
            raise Unsupported('Numeric sum requires exact integer/rational values; no coercion or default')
        return sum(vector)
    if op == "array":
        return values
    if op == "concat" and all(isinstance(v, list) for v in values):
        return [x for value in values for x in value]
    if op == "pair" and len(values) == 2 and isinstance(values[0], str):
        return values
    if op == "object":
        if any(not isinstance(v, list) or len(v) != 2 or not isinstance(v[0], str) for v in values):
            raise Unsupported("Object requires explicit string/value pairs")
        if len({v[0] for v in values}) != len(values):
            raise Unsupported("Duplicate output field")
        return {k: v for k, v in values}
    if op in {"and", "or", "xor", "not"}:
        if any(type(v) is not bool for v in values):
            raise Unsupported("Nonboolean operand")
        if op == "and":
            return all(values)
        if op == "or":
            return any(values)
        if op == "not" and len(values) == 1:
            return not values[0]
        if op == "xor" and len(values) == 2:
            return values[0] != values[1]
    if op in {"eq", "ne"} and len(values) == 2:
        numerical = all(type(v) in (int, Fraction) for v in values)
        same = (numerical or type(values[0]) is type(values[1])) and values[0] == values[1]
        return same if op == "eq" else not same
    if op in {"add", "sub", "min", "max", "lt", "le", "scale", "divide_constant", "ceil_divide_constant"}:
        if any(type(v) not in (int, Fraction) for v in values):
            raise Unsupported("Only exact integer/rational arithmetic in this backend")
        if op == "add":
            return sum(values)
        if op in {"min", "max"} and values:
            return (min if op == "min" else max)(values)
        if len(values) == 2:
            a, b = values
            if op == "sub":
                return a - b
            if op == "lt":
                return a < b
            if op == "le":
                return a <= b
            if op == "scale" and type(args[0]) in (int, Fraction):
                return a * b
            if op == "divide_constant" and type(args[1]) in (int, Fraction) and b != 0:
                return Fraction(a) / Fraction(b)
            if op == 'ceil_divide_constant' and type(args[1]) in (int,Fraction) and b > 0:
                quotient=Fraction(a)/Fraction(b)
                return -(-quotient.numerator//quotient.denominator)
    raise Unsupported(f"Unsupported operation or arity: {op}")


@dataclass(frozen=True)
class Residual:
    source: str
    slots: tuple[str, ...]
    evidence: str = "unverified_llm"
    # Verified footprint or TOP over the entire declared observation. If no
    # sound observation map exists, unknown_scope remains true: no certificate.
    unknown_scope: bool = True
    supported: bool = True


@dataclass
class FiniteTheory:
    ledger: SourceLedger
    facts: dict[str, Any]
    domains: dict[str, tuple[Any, ...]]
    query: Any
    residuals: list[Residual]
    constraints: list[Any] = field(default_factory=list)
    revision: int = 0
    events: list[dict] = field(default_factory=list)
    # Translation faithfulness is a declared assumption, never solver output.
    containment_assumptions: tuple[str, ...] = ()

    def validate(self) -> None:
        self.ledger.validate()
        if set(self.domains) & set(self.facts):
            raise ValueError("Completion choices cannot overwrite public facts")
        for domain in self.domains.values():
            if any(type(v) not in (bool, int, str) and v is not None for v in domain):
                raise Unsupported("Nonfinite or nonexact choice domain")
            if len({digest(v) for v in domain}) != len(domain):
                raise ValueError("Duplicate domain values")
        by_id = {c.id: c for c in self.ledger.clauses}
        registered = set()
        for r in self.residuals:
            if r.source not in by_id or by_id[r.source].state != "residual":
                raise ValueError("Residual has no residual source unit")
            if r.source in registered or not set(r.slots) <= self.domains.keys():
                raise ValueError("Duplicate residual or unbound semantic observation")
            registered.add(r.source)
        if registered != {c.id for c in self.ledger.clauses if c.state == "residual"}:
            raise ValueError("Unrepresented residual source obligation")
        if not set(self.domains) <= {s for r in self.residuals for s in r.slots}:
            raise ValueError("Completion variable has no source provenance")

    @property
    def version(self) -> str:
        return digest({"ledger": self.ledger.version, "facts": self.facts,
                       "domains": self.domains, "query": self.query,
                       "residuals": [asdict(r) for r in self.residuals],
                       "constraints": self.constraints, "revision": self.revision,
                       "assumptions": self.containment_assumptions})

    def narrow(self, slot: str, values: tuple, *, evidence: str) -> None:
        if evidence not in {"public_structure", "audited_template", "accepted_translation"}:
            raise ValueError("LLM scope guesses cannot narrow TOP")
        if not values or not {digest(x) for x in values} <= {digest(x) for x in self.domains[slot]}:
            raise ValueError("Not a nonempty narrowing; revoke explicitly instead")
        old = self.version
        self.domains[slot] = values
        self.revision += 1
        self.events.append({"event": "narrow", "slot": slot, "old": old,
                            "new": self.version, "evidence": evidence})

    def revoke(self, slot: str, values: tuple, *, reason: str) -> None:
        if not reason:
            raise ValueError("Revocation requires a reason")
        old = self.version
        self.domains[slot] = values
        self.revision += 1
        self.events.append({"event": "revoke_contract_and_dependent_certificates",
                            "slot": slot, "old": old, "new": self.version, "reason": reason})


@dataclass(frozen=True)
class World:
    choices: dict[str, Any]
    answer: Any


@dataclass
class CompletionResult:
    status: str
    worlds: list[World]
    theory_hash: str
    reason: str = ""
    answer: Any = None
    projection: dict = field(default_factory=dict)


def completion_projection(theory):
    """Sound syntactic noninterference for the compact, data-only query DAG.

    Unknown source scope is checked separately and is never removed here.
    Constraints participate in the read set. Other query implementations keep
    exhaustive enumeration of every declared domain.
    """
    from .scoped_program import ScopedQuery, expression_reads
    names=set(theory.domains)
    if not isinstance(theory.query,ScopedQuery) or any(
            not isinstance(c,dict) and type(c) not in (bool,int,str,Fraction,type(None))
            for c in theory.constraints):
        active=names
    else:
        active=theory.query.completion_dependencies()
        for constraint in theory.constraints:
            active |= expression_reads(constraint)
        active &= names
    inactive=names-active
    multiplicity=1
    for name in inactive:multiplicity*=len(theory.domains[name])
    return {'active_slots':sorted(active),'inactive_slots':sorted(inactive),
            'inactive_domain_multiplicity':multiplicity,
            'basis':'transitive_AST_read_noninterference' if inactive else 'all_domains_enumerated',
            'inactive_values_resolved':False}


def complete(theory: FiniteTheory, *, deadline: float | None = None,
             max_worlds: int = 65536, clock: Callable = time.monotonic) -> CompletionResult:
    """Exhaustive Ω. A partial prefix can NEVER yield a stable certificate."""
    version = theory.version
    try:
        theory.validate()
    except Unsupported as exc:
        return CompletionResult("unsupported_no_certificate", [], version, str(exc))
    if any(c.state == "conflict" for c in theory.ledger.clauses):
        return CompletionResult("conflict", [], version, "source conflict")
    if any(not r.supported for r in theory.residuals):
        return CompletionResult("unsupported_no_certificate", [], version, "domain outside IR")
    if any(r.unknown_scope for r in theory.residuals):
        return CompletionResult("translation_unresolved", [], version, "scope has no sound footprint")
    if any(r.evidence == "unverified_llm" for r in theory.residuals):
        return CompletionResult("translation_unresolved", [], version, "unverified TOP observation")
    if any(not values for values in theory.domains.values()):
        return CompletionResult("conflict", [], version, "empty_Omega")
    projection=completion_projection(theory)
    end = clock() + 5 if deadline is None else deadline
    worlds = []
    names = projection['active_slots']
    witness={name:theory.domains[name][0] for name in projection['inactive_slots']}
    try:
        for index, values in enumerate(product(*(theory.domains[n] for n in names))):
            if index >= max_worlds or clock() >= end:
                return CompletionResult("budget_exhausted", worlds, version, "enumeration/time limit")
            choices = {**witness, **dict(zip(names, values))}
            env = {**theory.facts, **choices}
            checks = [evaluate(c, env) for c in theory.constraints]
            if any(type(c) is not bool for c in checks):
                raise Unsupported("Constraint must be Boolean")
            if not all(checks):
                continue
            from .public_horn import GroundHornQuery
            answer = theory.query.evaluate(env, seconds=max(0, end - clock())) if isinstance(theory.query, GroundHornQuery) else evaluate(theory.query, env)
            if answer is None:
                raise Unsupported("Null is a system result, not a task answer")
            worlds.append(World(choices, answer))
    except TimeoutError as exc:
        return CompletionResult('budget_exhausted', worlds, version, str(exc))
    except Unsupported as exc:
        return CompletionResult("unsupported_no_certificate", worlds, version, str(exc))
    if not worlds:
        return CompletionResult("conflict", [], version, "empty_Omega")
    if any(w.answer == "__CONFLICT__" for w in worlds):
        return CompletionResult("conflict", worlds, version, "conflicting completion remains")
    if len({digest(w.answer) for w in worlds}) == 1:
        return CompletionResult("completion_stable", worlds, version, answer=worlds[0].answer,projection=projection)
    return CompletionResult("translation_unresolved", worlds, version, "different-answer completions",projection=projection)


def differing_pair(worlds: list[World], residuals: list[Residual], selected: set[str],
                   *, deadline: float, clock: Callable = time.monotonic) -> tuple | None:
    # Hashing observations implements the double-copy equality constraints;
    # compare answers within each equivalence class, without O(|Ω|²) pairs.
    seen = {}
    slots = sorted({s for r in residuals if r.source in selected for s in r.slots})
    for w in worlds:
        if clock() >= deadline:
            raise TimeoutError("separation query timed out")
        obs = digest({s: w.choices[s] for s in slots})
        if obs in seen and digest(seen[obs].answer) != digest(w.answer):
            return seen[obs], w
        seen[obs] = w
    return None


@dataclass
class BatchResult:
    status: str
    selected: tuple[str, ...] = ()
    context: tuple[str, ...] = ()
    cost: int = 0
    lower_bound: int = 0
    solver_calls: int = 0
    differences: list[tuple[str, ...]] = field(default_factory=list)
    theory_hash: str = ""


def plan_batch(theory: FiniteTheory, token_cost: Callable[[set[str]], int], budget: int,
               *, max_calls: int = 32, seconds: float = 5,
               clock: Callable = time.monotonic) -> BatchResult:
    """Implicit hitting set plus exact two-world separation, with shared closure cost."""
    deadline = clock() + min(seconds, 5)
    result = complete(theory, deadline=deadline, clock=clock)
    out = BatchResult(result.status, theory_hash=result.theory_hash)
    if result.status not in {"translation_unresolved", "conflict"} or not result.worlds:
        return out
    if len({digest(w.answer) for w in result.worlds}) < 2:
        return out
    active=set(result.projection.get('active_slots',theory.domains))
    units = sorted(r.source for r in theory.residuals if active.intersection(r.slots))
    if len(units) > 12:
        out.status = "budget_exhausted"  # never truncate residual groups
        return out
    try:
        while out.solver_calls < min(max_calls, 32):
            feasible = []
            for count in range(len(units) + 1):
                for subset in combinations(units, count):
                    if clock() >= deadline:
                        raise TimeoutError
                    if all(set(subset).intersection(d) for d in out.differences):
                        closure = theory.ledger.closure(set(subset))
                        cost = token_cost(closure) if subset else 0
                        if type(cost) is not int or cost < 0:
                            raise ValueError("Invalid context token cost")
                        feasible.append((cost, subset, tuple(sorted(closure))))
            if not feasible:
                out.status = "unobservable_with_available_actions"
                return out
            cost, subset, closure = min(feasible)
            out.lower_bound = cost
            if cost > budget:
                out.status = "batch_budget_insufficient"
                return out
            out.solver_calls += 1
            pair = differing_pair(result.worlds, theory.residuals, set(subset),
                                   deadline=deadline, clock=clock)
            if pair is None:
                out.status = "separation_complete"
                out.selected, out.context, out.cost = subset, closure, cost
                return out
            left, right = pair
            diff = tuple(r.source for r in theory.residuals
                         if any(digest(left.choices[s]) != digest(right.choices[s]) for s in r.slots))
            if not diff:
                out.status = "unobservable_with_available_actions"
                return out
            out.differences.append(diff)
    except TimeoutError:
        pass
    out.status = "budget_exhausted"
    return out


def certificate(theory: FiniteTheory, result: CompletionResult, *, deadline=None) -> dict:
    if result.status != "completion_stable" or result.theory_hash != theory.version:
        raise ValueError("No current stable certificate")
    # Recheck, rather than accepting a caller-constructed result as a proof.
    check = complete(theory, deadline=deadline)
    if check.status != "completion_stable" or digest(check.answer) != digest(result.answer):
        raise ValueError("Certificate verification failed")
    def proof_value(value):
        if isinstance(value, Fraction):
            return {"exact_rational": [value.numerator, value.denominator]}
        if isinstance(value, dict):
            return {k: proof_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [proof_value(v) for v in value]
        return value
    return {"status": result.status, "answer": proof_value(result.answer), "theory_hash": theory.version,
            "source_hash": theory.ledger.version,
            "completion_count": len(check.worlds)*check.projection.get('inactive_domain_multiplicity',1),
            "enumerated_query_worlds":len(check.worlds),
            "projection":check.projection,
            "backend": "exact_finite_enumeration_v1",
            "conditional_reference_containment": list(theory.containment_assumptions),
            "natural_language_faithfulness_proven": False}
