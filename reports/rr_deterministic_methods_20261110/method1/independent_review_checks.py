"""Independent exact-rational audit. Does not edit the recovery implementation."""
from fractions import Fraction as F
from itertools import product
from pathlib import Path
import hashlib
import json
import random
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from direct_recovery import PublicSpec, recover


def canonical_partition(features, columns):
    values = [tuple(row[c] for c in columns) for row in features]
    unique = []
    for value in values:
        if value not in unique: unique.append(value)
    return tuple(unique.index(value) for value in values)


def independent_semantics(partition, order, outer, spec, data):
    groups = {group: [] for group in partition}
    for group, (amount, deduction) in zip(partition, data):
        groups[group].append((amount, deduction))
    answer = F(0)
    for records in groups.values():
        amount = sum((r[0] for r in records), F(0))
        deduction = sum((r[1] for r in records), F(0))
        if order == "before":
            contribution = min(spec.cap, max(F(0), amount - deduction))
        else:
            contribution = max(F(0), min(spec.cap, amount) - deduction)
        answer += contribution
    return min(spec.outer_value, answer) if outer else answer


class ExactOracle:
    def __init__(self, partition, order, outer, spec):
        self.hidden = partition, order, outer
        self.spec = spec
        self.ledger = []

    def query(self, x, purpose, isolation):
        assert len(x) == len(self.spec.features)
        assert all(t >= 0 and 0 <= e <= t for t, e in x)
        assert self.spec.exclusion_allowed or not any(e for _, e in x)
        if self.spec.total_bound is not None:
            assert sum(t for t, _ in x) <= self.spec.total_bound, "probe_exceeds_total_bound"
        answer = independent_semantics(*self.hidden, self.spec, x)
        self.ledger.append((x, answer))
        return answer


def stress_data(spec, rng):
    data = []
    for _ in range(40):
        row = []
        for _ in spec.features:
            amount = F(rng.randrange(0, 1001), rng.choice((1, 3, 11, 101)))
            deduction = amount * F(rng.randrange(0, 11), 10) if spec.exclusion_allowed else F(0)
            row.append((amount, deduction))
        data.append(tuple(row))
    return data


def main():
    root = Path(__file__).resolve().parent
    feature_sets = [((0,), (0,), (1,), (1,)),
                    tuple(product((0, 1), repeat=2)) + ((0, 0),),
                    ((0, 0), (0, 0), (1, 1), (1, 1)),
                    ((0, 0, 0), (1, 1, 0), (0, 1, 1), (1, 0, 1)),
                    ((0,),)]
    checks = models_checked = physical_queries = 0
    problems = []
    rng = random.Random(202611101)
    for features, cap, ratio, allow_exclusion in product(feature_sets, (F(1, 3), F(7)),
                                                        (F(1, 2), F(1), F(3, 2), F(10)), (False, True)):
        spec = PublicSpec(features, cap=cap, outer_value=cap * ratio,
                          exclusion_allowed=allow_exclusion)
        all_partitions = {tuple(range(len(features)))}
        for keys in product((False, True), repeat=len(features[0])):
            all_partitions.add(canonical_partition(features, tuple(k for k, selected in enumerate(keys) if selected)))
        stress = stress_data(spec, rng)
        for partition, order, outer in product(sorted(all_partitions), ("before", "after"), (False, True)):
            oracle = ExactOracle(partition, order, outer, spec)
            recovered = recover(spec, oracle)
            models_checked += 1
            physical_queries += len(oracle.ledger)
            assert "status" not in recovered, recovered
            for x in stress:
                expected = independent_semantics(partition, order, outer, spec, x)
                actual = independent_semantics(recovered["partition"], recovered["order"], recovered["outer"], spec, x)
                if expected != actual:
                    problems.append({"spec": repr(spec), "truth": repr((partition, order, outer)),
                                     "recovered": recovered, "input": repr(x),
                                     "expected": str(expected), "actual": str(actual)})
                checks += 1
    # An intermediate bounded domain is present in PublicSpec but not handled by
    # the recovery formulas: C=7, B=12, sum(T)<=8, first probe uses T=10.5.
    bounded = PublicSpec(((0,), (0,), (1,), (1,)), total_bound=F(8))
    bounded_oracle = ExactOracle((0, 0, 1, 1), "before", False, bounded)
    bounded_result = recover(bounded, bounded_oracle)
    assert bounded_result.get("status") == "unsupported_domain"
    assert not bounded_oracle.ledger
    result = {"kind": "independent scalar Fraction semantics; finite stress, not a universal proof",
              "recovery_sha256": hashlib.sha256((root / "direct_recovery.py").read_bytes()).hexdigest(),
              "models_checked": models_checked, "stress_predictions_checked": checks,
              "learner_query_calls": physical_queries,
              "mismatches": problems,
              "intermediate_bounded_domain": {"cap": "7", "outer": "12", "sum_T_bound": "8",
                                                "first_probe_T": "21/2", "observed_result": bounded_result,
                                                "physical_queries_before_rejection": len(bounded_oracle.ledger)}}
    (root / "independent_review_checks.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "recovery_sha256"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
