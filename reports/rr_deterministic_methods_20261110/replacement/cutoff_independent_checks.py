"""Independent exact state-space audit of capped_fold_direct; no solver calls."""
from collections import deque
from pathlib import Path
from random import Random
import hashlib
import json
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from capped_fold_direct import Piece, compare


def eval_raw(pieces, x):
    matching = [p for p in pieces if p.lo <= x and (p.hi is None or x <= p.hi)]
    assert len(matching) == 1
    return matching[0].a * x + matching[0].b


def contains(pieces, x):
    return any(p.lo <= x and (p.hi is None or x <= p.hi) for p in pieces)


def complete_generator_points(p, A, q, B):
    """Enumerate every finite point and the exact eventual saturated tail.

    For each growing final affine tail, ceil((cap-b)/a) is a point after
    which its clipped value is constant. Beyond the greatest such point,
    both clipped generators are constant; one final point represents the tail.
    This reduction is independent of the implementation's clipping routine.
    """
    if not p: return []
    lo = min(p[0].lo, q[0].lo)
    end = lo
    for pieces, cap in ((p, A), (q, B)):
        for piece in pieces:
            end = max(end, piece.hi if piece.hi is not None else piece.lo)
            if piece.hi is None and piece.a > 0:
                end = max(end, -((piece.b - cap) // piece.a))
    return [x for x in range(lo, end + 1) if contains(p, x)]


def bfs_minimum(p, A, q, B):
    points = complete_generator_points(p, A, q, B)
    steps = [(eval_raw(p, x), eval_raw(q, x)) for x in points]
    queue = deque([((0, 0), 0)])
    seen = {(0, 0)}
    while queue:
        (f, g), depth = queue.popleft()
        for fp, gq in steps:
            state = (min(A, f + fp), min(B, g + gq))
            if state[0] != state[1]: return depth + 1, len(seen)
            if state not in seen:
                seen.add(state)
                queue.append((state, depth + 1))
    return None, len(seen)


def random_piece(rng, lo, hi):
    a = rng.randrange(-3, 4) if hi is not None else rng.randrange(4)
    minimum_linear = a * lo if a >= 0 else a * hi
    return Piece(lo, hi, a, -minimum_linear + rng.randrange(8))


def check_pair(p, A, q, B):
    result = compare(p, A, q, B)
    minimum, states = bfs_minimum(p, A, q, B)
    assert result["minimum_count"] == minimum, (p, A, q, B, result, minimum)
    assert result["equivalent"] == (minimum is None)
    if minimum is not None:
        x = result["witness"]["record"]
        count = result["witness"]["repeat"]
        assert contains(p, x) and contains(q, x)
        assert count == minimum
        f, g = min(A, count * eval_raw(p, x)), min(B, count * eval_raw(q, x))
        assert f != g and f == result["F"] and g == result["G"]
    return states


def main():
    rng = Random(202611102)
    checked = states = 0
    families = {}
    for unbounded in (False, True):
        family_count = 0
        for _ in range(1500):
            intervals = [(-3, -1), (2, 5), (9, None if unbounded else 13)]
            p = tuple(random_piece(rng, lo, hi) for lo, hi in intervals)
            # Different segmentation over exactly the same gapped integer domain.
            q_intervals = [(-3, -2), (-1, -1), (2, 3), (4, 5), (9, 10),
                           (11, None if unbounded else 13)]
            q = tuple(random_piece(rng, lo, hi) for lo, hi in q_intervals)
            A, B = rng.randrange(31), rng.randrange(31)
            states += check_pair(p, A, q, B)
            checked += 1
            family_count += 1
        families["unbounded_tails" if unbounded else "finite_gapped_negative_slopes"] = family_count
    # Force common single-record semantics with unequal caps to exercise the
    # cardinality formula; arbitrary independent functions mostly differ at n=1.
    cutoff_cases = 0
    for H in range(1, 9):
        p = (Piece(0, 1, H, 0), Piece(4, None, 0, H))
        for small in range(H, 31):
            for large in (small + 1, small + 9):
                for A, B in ((small, large), (large, small)):
                    states += check_pair(p, A, p, B)
                    checked += 1
                    cutoff_cases += 1
    boundaries = []
    for A, B in ((0, 0), (0, 7), (7, 0), (7, 7)):
        zero = (Piece(2, None, 0, 0),)
        states += check_pair(zero, A, zero, B)
        checked += 1
        boundaries.append({"A": A, "B": B, "zero_generator": True})
    for A, B in ((0, 0), (0, 7), (7, 0), (7, 7)):
        states += check_pair((), A, (), B)
        checked += 1
    invalid = [
        ((Piece(0, None, -1, 5),), 5, (Piece(0, None, 0, 0),), 5),
        ((Piece(0, 3, 0, -1),), 5, (Piece(0, 3, 0, 0),), 5),
        ((Piece(0, 2, 0, 1),), 5, (Piece(0, 3, 0, 1),), 5),
        ((Piece(0, 3, 0, 1), Piece(3, 4, 0, 1)), 5,
         (Piece(0, 4, 0, 1),), 5),
    ]
    for args in invalid:
        try:
            compare(*args)
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid input was accepted")
    integer_contract_rejections = 0
    valid_piece = (Piece(0, 3, 1, 0),)
    invalid_types = [lambda: Piece(0.5, 3, 1, 0),
                     lambda: Piece(0, 3.0, 1, 0),
                     lambda: Piece(0, 3, True, 0),
                     lambda: compare(valid_piece, 1.5, valid_piece, 3),
                     lambda: compare(valid_piece, True, valid_piece, 3),
                     lambda: compare(valid_piece, None, valid_piece, 3)]
    for invoke in invalid_types:
        try:
            invoke()
        except TypeError:
            integer_contract_rejections += 1
        else:
            raise AssertionError("Noninteger contract was accepted")
    # Huge off-by-one boundary: do not materialize the returned multiset.
    H, A = 3, 10 ** 50
    huge = compare((Piece(0, None, 0, H),), A,
                   (Piece(0, None, 0, H),), A + 1)
    assert huge["minimum_count"] == A // H + 1
    assert (huge["minimum_count"] - 1) * H <= A < huge["minimum_count"] * H
    # Outside-premise counterexample, intentionally not fed to compare as legal.
    assert min(4, 2 * 2) == min(7, 2 * 2)
    assert min(4, 3 * 2) != min(7, 3 * 2)
    report = {
        "scope": "Independent exact BFS of reachable saturated output pairs; no floating point or MILP",
        "implementation_sha256": hashlib.sha256(Path(__file__).with_name("capped_fold_direct.py").read_bytes()).hexdigest(),
        "pairs_checked": checked, "families": families,
        "forced_unequal_cap_common_generator_cases": cutoff_cases,
        "reachable_states_processed": states, "mismatches": 0,
        "invalid_input_rejections": len(invalid),
        "noninteger_contract_rejections": integer_contract_rejections,
        "huge_integer_count_case": huge,
        "boundaries": boundaries,
        "free_replication_necessary": {"caps": [4, 7], "per_group": 2,
                                       "unrestricted_minimum": 3, "N_le_2_domain_equivalent": True}}
    Path(__file__).with_name("cutoff_independent_checks.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
