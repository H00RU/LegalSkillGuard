"""Exact direct comparison of two nonnegative, capped multiset sums.

No solver, floating point, cardinality bound, or sampled input domain is used by
`compare`. PWA coefficients, bounds and caps are integers. `hi=None` is infinity.
Scope: independent, freely replicable records; one final cap; common input domain.
"""
from dataclasses import dataclass, asdict
from itertools import combinations_with_replacement, product
from pathlib import Path
from time import perf_counter
import json


@dataclass(frozen=True)
class Piece:
    lo: int
    hi: int | None
    a: int
    b: int

    def __post_init__(self):
        for name in ("lo", "a", "b"):
            if type(getattr(self, name)) is not int:
                raise TypeError(f"{name} must be an exact integer (bool/float excluded)")
        if self.hi is not None and type(self.hi) is not int:
            raise TypeError("hi must be an exact integer or None")


def endmin(a, b):
    if a is None:
        return b
    if b is None:
        return a
    return min(a, b)


def valid_range(lo, hi):
    return hi is None or lo <= hi


def validate(pieces):
    previous = None
    for i, p in enumerate(pieces):
        if not valid_range(p.lo, p.hi):
            raise ValueError("empty PWA interval")
        if i and (previous is None or p.lo <= previous):
            raise ValueError("overlapping or unsorted PWA intervals")
        if p.hi is None and p.a < 0:
            raise ValueError("negative values on unbounded tail")
        vals = [p.a * p.lo + p.b]
        if p.hi is not None:
            vals.append(p.a * p.hi + p.b)
        if min(vals) < 0:
            raise ValueError("negative contribution outside theorem")
        previous = p.hi


def domain(pieces):
    out = []
    for p in pieces:
        if out and out[-1][1] is not None and p.lo == out[-1][1] + 1:
            out[-1] = (out[-1][0], p.hi)
        else:
            out.append((p.lo, p.hi))
    return out


def clipped(pieces, cap):
    if type(cap) is not int:
        raise TypeError("cap must be an exact finite integer (bool/float excluded)")
    if cap < 0:
        raise ValueError("cap must be nonnegative")
    out = []
    for p in pieces:
        if p.a == 0:
            out.append(Piece(p.lo, p.hi, 0, min(p.b, cap)))
        elif p.a > 0:
            last_unsaturated = (cap - 1 - p.b) // p.a
            hi = endmin(p.hi, last_unsaturated)
            if valid_range(p.lo, hi):
                out.append(Piece(p.lo, hi, p.a, p.b))
            lo = max(p.lo, last_unsaturated + 1)
            if valid_range(lo, p.hi):
                out.append(Piece(lo, p.hi, 0, cap))
        else:
            last_saturated = (p.b - cap) // (-p.a)
            hi = endmin(p.hi, last_saturated)
            if valid_range(p.lo, hi):
                out.append(Piece(p.lo, hi, 0, cap))
            lo = max(p.lo, last_saturated + 1)
            if valid_range(lo, p.hi):
                out.append(Piece(lo, p.hi, p.a, p.b))
    return tuple(out)


def evaluate(pieces, x):
    p = next(p for p in pieces if p.lo <= x and (p.hi is None or x <= p.hi))
    return p.a * x + p.b


def single_difference(p, q):
    i = j = checks = 0
    while i < len(p) and j < len(q):
        a, b = p[i], q[j]
        lo, hi = max(a.lo, b.lo), endmin(a.hi, b.hi)
        if valid_range(lo, hi):
            checks += 1
            if a.a * lo + a.b != b.a * lo + b.b:
                return lo, checks
            if a.a != b.a and (hi is None or lo < hi):
                return lo + 1, checks
        if a.hi == b.hi:
            i += 1
            j += 1
        elif a.hi is None or (b.hi is not None and b.hi < a.hi):
            j += 1
        else:
            i += 1
    return None, checks


def maximum(pieces):
    best = None
    for p in pieces:
        if p.a > 0:
            if p.hi is None:
                raise ValueError("clipped function cannot grow without bound")
            x = p.hi
        else:
            x = p.lo
        value = p.a * x + p.b
        if best is None or value > best[0]:
            best = (value, x)
    return best


def compare(p, A, q, B):
    validate(p)
    validate(q)
    if domain(p) != domain(q):
        raise ValueError("different record domains")
    hp, hq = clipped(p, A), clipped(q, B)
    x, scanned = single_difference(hp, hq)
    if x is not None:
        return {"equivalent": False, "minimum_count": 1,
                "witness": {"record": x, "repeat": 1},
                "F": min(A, evaluate(p, x)), "G": min(B, evaluate(q, x)),
                "reason": "one-record difference", "scan_cells": scanned}
    if A == B:
        return {"equivalent": True, "minimum_count": None,
                "reason": "same cap and equal clipped generators", "scan_cells": scanned}
    maximal = maximum(hp)
    if maximal is None or maximal[0] == 0:
        return {"equivalent": True, "minimum_count": None,
                "reason": "common clipped generator is identically zero", "scan_cells": scanned}
    H, x = maximal
    count = min(A, B) // H + 1
    F = min(A, count * evaluate(p, x))
    G = min(B, count * evaluate(q, x))
    assert F != G
    return {"equivalent": False, "minimum_count": count,
            "witness": {"record": x, "repeat": count}, "F": F, "G": G,
            "common_maximum": H, "reason": "unequal caps; repeat maximal common generator",
            "scan_cells": scanned}


def exhaustive_check():
    # All functions on three points with values in 0..3, all caps in 0..4.
    functions = list(product(range(4), repeat=3))
    bags = [xs for n in range(6) for xs in combinations_with_replacement(range(3), n)]
    objects, signatures = {}, {}
    for values in functions:
        p = tuple(Piece(i, i, 0, v) for i, v in enumerate(values))
        objects[values] = p
        for cap in range(5):
            signatures[(values, cap)] = [min(cap, sum(values[x] for x in xs)) for xs in bags]
    checked = 0
    for fv, gv, A, B in product(functions, functions, range(5), range(5)):
        result = compare(objects[fv], A, objects[gv], B)
        fs, gs = signatures[(fv, A)], signatures[(gv, B)]
        first = next((len(xs) for xs, f, g in zip(bags, fs, gs) if f != g), None)
        assert first == result["minimum_count"], (fv, gv, A, B, result, first)
        checked += 1
    return checked


def baseline_check():
    # Same finite integer domain, same per-record PWA, same final caps.
    from aggregate_witness import Program, Segment, solve
    checked, direct_seconds, milp_seconds = 0, 0.0, 0.0
    for upper, cap_p, cap_q in product([3, 7, 12], [4, 10, 30], [4, 17, 50]):
        p = (Piece(0, upper, 1, 0),)
        a = perf_counter()
        exact = compare(p, cap_p, p, cap_q)
        direct_seconds += perf_counter() - a
        prog = (Segment(0, upper, 1, 0),)
        a = perf_counter()
        generic = solve(Program("P", prog, cap_p), Program("Q", prog, cap_q))["witness"]
        milp_seconds += perf_counter() - a
        actual = None if generic is None else generic["count"]
        assert exact["minimum_count"] == actual
        checked += 1
    return {"matched_pairs": checked, "direct_seconds": direct_seconds,
            "numerical_MILP_seconds": milp_seconds,
            "qualification": "prototype overhead comparison, not a SQLSolver/LIA* benchmark"}


def boundary_failures():
    return {
        "negative_contributions": {
            "caps": [10, 10], "f": [20, -10], "g": [10, -10],
            "single_outputs_equal": True, "two_record_outputs": [10, 0],
            "excluded_by": "nonnegative contribution premise"},
        "shared_budget_no_replication": {
            "caps": [4, 7], "record_contribution": 2,
            "unrestricted_minimum": 3, "maximum_legal_records": 2,
            "legal_domain_equivalent": True,
            "excluded_by": "freely replicable independent records premise"},
        "global_deduction": {
            "F": "max(0, sum(x)-4)", "G": "max(0, sum(x)-5)",
            "record_domain": [0, 3], "single_outputs_equal": True,
            "x3_twice_outputs": [2, 1],
            "excluded_by": "one final cap without extra aggregate-side operations"}}


def main():
    start = perf_counter()
    finite = exhaustive_check()
    unbounded = [
        compare((Piece(0, None, 1, 0),), 9, (Piece(0, 8, 1, 0), Piece(9, None, 0, 9)), 9),
        compare((Piece(0, 2, 1, 0), Piece(3, None, 0, 3)), 1_000_000,
                (Piece(0, 2, 1, 0), Piece(3, None, 0, 3)), 1_000_001),
        compare((Piece(0, None, 0, 7),), 0, (Piece(0, None, 0, 0),), 8),
        compare((Piece(0, 8, -1, 8),), 5, (Piece(0, 8, -1, 8),), 9),
    ]
    assert unbounded[0]["equivalent"]
    assert unbounded[1]["minimum_count"] == 333334
    assert unbounded[2]["equivalent"]
    assert unbounded[3]["minimum_count"] == 1
    rejected = 0
    for thunk in [
        lambda: compare((Piece(0, None, 1, 0),), 1.5, (Piece(0, None, 1, 0),), 2),
        lambda: compare((Piece(0, None, 1, 0),), True, (Piece(0, None, 1, 0),), 2),
        lambda: compare((Piece(0, None, 1, 0),), None, (Piece(0, None, 1, 0),), 2),
        lambda: Piece(0., 2, 1, 0),
        lambda: Piece(0, False, 1, 0),
        lambda: Piece(0, 2, 0.5, 0),
    ]:
        try:
            thunk()
        except TypeError:
            rejected += 1
    assert rejected == 6
    baseline = baseline_check()
    out = {"status": "exact restricted algorithm; no model calls",
           "exhaustive_function_cap_pairs": finite,
           "finite_domain_size": 3, "finite_function_range": [0, 3],
           "enumerated_caps": [0, 4], "enumerated_bag_sizes": [0, 5],
           "unbounded_domain_cases": unbounded,
           "noninteger_or_infinite_cap_inputs_rejected": rejected,
           "baseline": baseline, "outside_scope_counterexamples": boundary_failures(),
           "elapsed_seconds": perf_counter() - start,
           "novelty": "Saturation monoid laws are established mathematics; direct restricted algorithm requires separate novelty assessment."}
    Path(__file__).with_name("capped_fold_direct_results.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "outside_scope_counterexamples"}, indent=2))


if __name__ == "__main__":
    main()
