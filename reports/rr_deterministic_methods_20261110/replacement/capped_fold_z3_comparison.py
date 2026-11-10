"""Exact and compute-transparent baselines for capped_fold_direct.py.

These are local Z3 encodings, NOT executions of SQLSolver or VeriEQL.
All methods receive the same clipped PWA cells and their exact maxima.
"""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "work" / "legal-validation-deps"))
import z3
from time import perf_counter
from capped_fold_direct import Piece, clipped, maximum, compare, evaluate, endmin, valid_range, single_difference
from aggregate_witness import compress_interval_sum
import json


def joint_cells(p, q):
    out = []
    i = j = 0
    while i < len(p) and j < len(q):
        a, b = p[i], q[j]
        lo, hi = max(a.lo, b.lo), endmin(a.hi, b.hi)
        if valid_range(lo, hi):
            out.append((lo, hi, a.a, a.b, b.a, b.b))
        if a.hi == b.hi:
            i += 1
            j += 1
        elif a.hi is None or (b.hi is not None and b.hi < a.hi):
            j += 1
        else:
            i += 1
    return out


def capterm(x, c):
    return z3.If(x <= c, x, c)


def exact_optimized(o, objective, constraints):
    if isinstance(objective, int):
        objective = z3.IntVal(objective)
    o.set(timeout=3000)
    handle = o.minimize(objective)
    status = o.check()
    if status == z3.unsat:
        return {"status": "equivalent", "minimum_count": None}
    if status != z3.sat:
        return {"status": "unknown", "reason": o.reason_unknown()}
    model = o.model()
    count = model.eval(objective).as_long()
    # Independent optimality check; a feasible model alone is insufficient.
    proof = z3.Solver()
    proof.set(timeout=3000)
    proof.add(*constraints, objective < count)
    optimal = proof.check()
    if optimal != z3.unsat:
        return {"status": "unknown", "reason": "optimality not established", "feasible_count": count}
    return {"status": "different", "minimum_count": count,
            "_model": model, "lower": str(handle.lower()), "upper": str(handle.upper())}


def weighted_cell(p, A, q, B, Hp, Hq):
    cells = joint_cells(p, q)
    o = z3.Optimize()
    counts, sums_p, sums_q, metadata = [], [], [], []
    constraints = []
    variables = 0
    for j, (lo, hi, ap, bp, aq, bq) in enumerate(cells):
        # Zero-output cells can never help a shortest differing witness.
        if ap == aq == bp == bq == 0:
            continue
        n = z3.Int(f"n_{j}")
        counts.append(n)
        constraints.append(n >= 0)
        variables += 1
        if ap == aq == 0:
            sums_p.append(bp * n)
            sums_q.append(bq * n)
            metadata.append((n, None, lo, hi))
        else:
            if hi is None:
                raise ValueError("finite capped PWA cannot grow on an unbounded tail")
            s = z3.Int(f"S_{j}")
            variables += 1
            constraints.extend([n * lo <= s, s <= n * hi])
            sums_p.append(ap * s + bp * n)
            sums_q.append(aq * s + bq * n)
            metadata.append((n, s, lo, hi))
    N, U, V = z3.Sum(counts), z3.Sum(sums_p), z3.Sum(sums_q)
    # Publish and use the same exact per-record maxima supplied to direct method.
    constraints.extend([U <= Hp * N, V <= Hq * N, capterm(U, A) != capterm(V, B)])
    o.add(*constraints)
    result = exact_optimized(o, N, constraints)
    result.update({"variables": variables, "constraints": len(constraints), "cells": len(cells)})
    model = result.pop("_model", None)
    if model is not None:
        runs = []
        for n, s, lo, hi in metadata:
            count = model.eval(n).as_long()
            if s is None:
                if count:
                    runs.append((lo, count))
            else:
                total = model.eval(s).as_long()
                runs.extend(compress_interval_sum(count, total, lo, hi))
        F = min(A, sum(evaluate(p, x) * n for x, n in runs))
        G = min(B, sum(evaluate(q, x) * n for x, n in runs))
        assert F != G and sum(n for _, n in runs) == result["minimum_count"]
        result["witness_runs"] = runs
    return result


def normalized_1d(p, A, q, B, Hp, Hq):
    # This baseline deliberately uses the SAME saturation reduction, then asks
    # an exact optimizer for the integer minimum instead of computing division.
    witness, _ = single_difference(p, q)
    if witness is not None:
        return {"status": "different", "minimum_count": 1, "variables": 0}
    if A == B or Hp == 0:
        return {"status": "equivalent", "minimum_count": None, "variables": 0}
    N = z3.Int("normalized_N")
    cs = [N >= 0, N * Hp > min(A, B)]
    o = z3.Optimize()
    o.add(*cs)
    result = exact_optimized(o, N, cs)
    result.pop("_model", None)
    result["variables"] = 1
    return result


def at(pieces, x):
    expr = z3.IntVal(0)
    choices = []
    for p in reversed(pieces):
        cond = z3.And(x >= p.lo, z3.BoolVal(True) if p.hi is None else x <= p.hi)
        expr = z3.If(cond, p.a * x + p.b, expr)
        choices.append(cond)
    return expr, z3.Or(choices)


def bounded_unroll(p, A, q, B, Hp, Hq, limit=8):
    # Same clipped PWA and H; finite-bound result explicitly remains bounded.
    calls = 0
    for n in range(1, limit + 1):
        solver = z3.Solver()
        solver.set(timeout=3000)
        fs, gs = [], []
        for j in range(n):
            x = z3.Int(f"record_{j}")
            f, allowed = at(p, x)
            g, allowed_q = at(q, x)
            solver.add(allowed, allowed_q)
            fs.append(f)
            gs.append(g)
        fp, gq = z3.Sum(fs), z3.Sum(gs)
        solver.add(fp <= n * Hp, gq <= n * Hq, capterm(fp, A) != capterm(gq, B))
        status = solver.check()
        calls += 1
        if status == z3.sat:
            return {"status": "different", "minimum_count": n, "calls": calls, "bound": limit}
        if status == z3.unknown:
            return {"status": "unknown", "reason": solver.reason_unknown(), "calls": calls, "bound": limit}
    return {"status": "no difference within bound", "calls": calls, "bound": limit}


def cases():
    result = []
    for k in [1, 4, 16, 64]:
        # Nonzero constant-on-point cells, representative of categorical branches.
        p = tuple(Piece(i, i, 0, (i * 7) % 13 + 1) for i in range(k))
        for A in [100, 1_000_000]:
            result.append((f"shared_piecewise_k{k}_A{A}", p, A, p, A + 1))
    p = (Piece(0, 5, 1, 0), Piece(6, None, 0, 5))
    result += [
        ("same_cap_different_saturated_inners", (Piece(0, None, 1, 0),), 9,
         (Piece(0, 8, 1, 0), Piece(9, None, 0, 9)), 9),
        ("single_record_difference", p, 4, p, 8),
        ("zero_cap_common_zero", (Piece(0, None, 0, 7),), 0,
         (Piece(0, None, 0, 0),), 8),
        ("negative_slope_nonnegative_values", (Piece(0, 8, -1, 8),), 9,
         (Piece(0, 8, -1, 8),), 12),
    ]
    return result


def main():
    rows = []
    totals = {"direct": 0., "weighted_cell_z3": 0., "same_reduction_1d_z3": 0., "bounded_unroll_z3": 0.}
    for name, p, A, q, B in cases():
        # Shared clipped PWA/max preprocessing is performed only once.
        hp, hq = clipped(p, A), clipped(q, B)
        Hp, Hq = maximum(hp)[0], maximum(hq)[0]
        row = {"name": name, "A": A, "B": B, "H_P": Hp, "H_Q": Hq}
        for method, fn in [
            ("direct", lambda: compare(hp, A, hq, B)),
            ("weighted_cell_z3", lambda: weighted_cell(hp, A, hq, B, Hp, Hq)),
            ("same_reduction_1d_z3", lambda: normalized_1d(hp, A, hq, B, Hp, Hq)),
            ("bounded_unroll_z3", lambda: bounded_unroll(hp, A, hq, B, Hp, Hq)),
        ]:
            t = perf_counter()
            result = fn()
            result["seconds"] = perf_counter() - t
            totals[method] += result["seconds"]
            row[method] = result
        expected = row["direct"]["minimum_count"]
        for method in ["weighted_cell_z3", "same_reduction_1d_z3"]:
            assert row[method]["status"] != "unknown", (name, method, row[method])
            assert row[method]["minimum_count"] == expected, (name, method)
        bound = row["bounded_unroll_z3"]
        if expected is not None and expected <= bound["bound"] and bound["status"] != "unknown":
            assert bound["minimum_count"] == expected
        elif bound["status"] == "different":
            raise AssertionError((name, bound))
        rows.append(row)
    out = {"status": "deterministic local exact comparisons; no model calls",
           "z3_version": z3.get_version_string(), "pairs": len(rows), "all_exact_results_match": True,
           "shared_preprocessing": "same clipped PWA, input domain and exact per-record maxima H",
           "timing_scope": "one run of encoding plus solving; import/shared preprocessing excluded; not robust performance estimate",
           "total_seconds": totals, "results": rows,
           "important_boundary": "The normalized 1D baseline uses the same algebraic reduction as the direct method. It measures remaining optimizer overhead, not an independent competing idea. SQLSolver and VeriEQL were not executed."}
    Path(__file__).with_name("capped_fold_z3_results.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "results"}, indent=2))


if __name__ == "__main__":
    main()
