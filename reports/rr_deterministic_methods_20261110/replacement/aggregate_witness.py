"""Deterministic prototype: exact witness reconstruction for interval aggregates.

This is arithmetic validation, not model evaluation or a novelty claim. The MILP
backend is numerical; every returned witness is reconstructed and checked with
Python integers before it is accepted. UNSAT is not advertised as a proof.
"""
from dataclasses import dataclass
from itertools import combinations_with_replacement, product
from pathlib import Path
import json
import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp


@dataclass(frozen=True)
class Segment:
    lo: int
    hi: int
    slope: int
    offset: int


@dataclass(frozen=True)
class Program:
    name: str
    pieces: tuple
    cap: int | None = None
    addition: int = 0

    def inner(self, x):
        s = next(p for p in self.pieces if p.lo <= x <= p.hi)
        return s.slope * x + s.offset

    def outer(self, v):
        return (v if self.cap is None else min(v, self.cap)) + self.addition


def common_cells(p, q):
    cells = []
    for a, b in product(p.pieces, q.pieces):
        lo, hi = max(a.lo, b.lo), min(a.hi, b.hi)
        if lo <= hi:
            cells.append((lo, hi, a.slope, a.offset, b.slope, b.offset))
    return cells


def outer_modes(p):
    if p.cap is None:
        return [(True, None)]
    return [(True, p.cap), (False, p.cap)]


def compress_interval_sum(n, total, lo, hi):
    """Construct n integers in [lo,hi] totaling total, in <=3 runs."""
    assert n >= 0 and n * lo <= total <= n * hi
    if n == 0:
        return []
    if hi == lo:
        return [(lo, n)]
    full, remainder = divmod(total - n * lo, hi - lo)
    runs = []
    if full:
        runs.append((hi, full))
    if remainder:
        runs.append((lo + remainder, 1))
    rest = n - full - int(remainder != 0)
    if rest:
        runs.append((lo, rest))
    assert sum(count for _, count in runs) == n
    assert sum(x * count for x, count in runs) == total
    return runs


def solve(p, q):
    cells = common_cells(p, q)
    k, d = len(cells), 2 * len(cells)
    # x[2j] = group count, x[2j+1] = sum of scalar input amounts.
    cp, cq, obj = np.zeros(d), np.zeros(d), np.zeros(d)
    base = []
    for j, (lo, hi, ap, bp, aq, bq) in enumerate(cells):
        obj[2*j] = 1
        cp[2*j:2*j+2] = [bp, ap]
        cq[2*j:2*j+2] = [bq, aq]
        lower, upper = np.zeros(d), np.zeros(d)
        lower[2*j:2*j+2] = [-lo, 1]
        upper[2*j:2*j+2] = [-hi, 1]
        base += [(lower, 0, np.inf), (upper, -np.inf, 0)]
    best = None
    attempts = 0
    for pm, qm, direction in product(outer_modes(p), outer_modes(q), [-1, 1]):
        cons = list(base)
        def output(program, coeff, mode):
            linear, cap = mode
            if cap is None:
                return coeff, program.addition
            cons.append((coeff, -np.inf if linear else cap,
                         cap if linear else np.inf))
            return (coeff, program.addition) if linear else (np.zeros(d), cap + program.addition)
        xp, bp = output(p, cp, pm)
        xq, bq = output(q, cq, qm)
        # Outputs are integers, so non-equality is one of two >=1 constraints.
        cons.append((direction * (xp - xq), 1 - direction * (bp - bq), np.inf))
        A = np.vstack([c[0] for c in cons])
        res = milp(obj, integrality=np.ones(d), bounds=Bounds(np.zeros(d), np.full(d, np.inf)),
                   constraints=LinearConstraint(A, [c[1] for c in cons], [c[2] for c in cons]),
                   options={"time_limit": 10})
        attempts += 1
        if res.x is None:
            continue
        values = [int(round(v)) for v in res.x]
        try:
            runs = []
            for j, cell in enumerate(cells):
                runs += compress_interval_sum(values[2*j], values[2*j+1], cell[0], cell[1])
            yp = p.outer(sum(p.inner(x) * n for x, n in runs))
            yq = q.outer(sum(q.inner(x) * n for x, n in runs))
            assert yp != yq
        except AssertionError:
            raise RuntimeError("Numerical solver returned a non-reconstructible witness")
        item = {"count": sum(n for _, n in runs), "runs": runs, "p": yp, "q": yq}
        if best is None or item["count"] < best["count"]:
            best = item
    return {"witness": best, "variables": d, "cells": k, "MILP_calls": attempts}


def brute(p, q, upper, max_n):
    for n in range(max_n + 1):
        for xs in combinations_with_replacement(range(upper + 1), n):
            a, b = p.outer(sum(map(p.inner, xs))), q.outer(sum(map(q.inner, xs)))
            if a != b:
                return n
    return None


def main():
    checked = 0
    reports = []
    for local_cap, global_cap in product([2, 3, 5, 7], [3, 6, 10, 13]):
        # x can originally be arbitrarily large: both programs use min(C,x),
        # so replacing x>C by C is semantics-preserving for this comparison.
        pieces = (Segment(0, local_cap, 1, 0),)
        p = Program("per-item cap then global cap", pieces, global_cap)
        q = Program("missing global cap", pieces)
        got = solve(p, q)
        exact = global_cap // local_cap + 1
        assert got["witness"]["count"] == exact
        if exact <= 4:
            assert brute(p, q, local_cap, 4) == exact
        else:
            assert brute(p, q, local_cap, 4) is None
        checked += 1
        reports.append({"C": local_cap, "G": global_cap, **got})

    # Genuine piecewise case: deduction before local cap vs after local cap.
    for cap, deduction, outer in product([3, 5, 7], [1, 2, 3], [None, 4, 8]):
        upper = cap + deduction
        p = Program("deduct then cap", (
            Segment(0, deduction, 0, 0),
            Segment(deduction + 1, upper, 1, -deduction),
        ), outer)
        q = Program("cap then deduct", (
            Segment(0, deduction, 0, 0),
            Segment(deduction + 1, cap, 1, -deduction),
            Segment(cap + 1, upper, 0, max(0, cap - deduction)),
        ), outer)
        # Remove empty intervals in the cap=deduction case.
        q = Program(q.name, tuple(s for s in q.pieces if s.lo <= s.hi), q.cap)
        got = solve(p, q)["witness"]
        expected = brute(p, q, upper, 3)
        assert (got["count"] if got is not None else None) == expected
        checked += 1

    giant_cap, local_cap = 1_000_000, 3
    p = Program("cap retained", (Segment(0, local_cap, 1, 0),), giant_cap)
    q = Program("cap omitted", p.pieces)
    giant = solve(p, q)
    assert giant["witness"]["count"] == giant_cap // local_cap + 1
    out = {
        "status": "arithmetic prototype only; no real model calls",
        "finite_pair_checks": checked,
        "finite_all_passed": True,
        "large_minimum_witness": giant,
        "examples": reports,
        "novelty_warning": "General LIA* already represents these unbounded sums; this validates a specialized reduction, not novelty.",
        "certificate_warning": "Integer witness checked exactly; numerical MILP UNSAT is not a formal certificate.",
    }
    path = Path(__file__).with_name("aggregate_witness_results.json")
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "examples"}, indent=2))


if __name__ == "__main__":
    main()
