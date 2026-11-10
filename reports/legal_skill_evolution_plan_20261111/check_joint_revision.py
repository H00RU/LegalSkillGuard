"""Deterministic illustration only; no model, native labels, or server access."""
import itertools
import json
from pathlib import Path


def gold(a, s, c):
    # Constructed rule: basic eligibility AND (not student OR exception met).
    return a and (not s or c)


def run(a, s, c, producer_version, consumer_version):
    p = a if producer_version else a and not s
    return (p and (not s or c)) if consumer_version else (p or (s and c))


def main():
    rows = []
    for facts in itertools.product([False, True], repeat=3):
        outputs = {f"{p}{c}": int(run(*facts, p, c))
                   for p, c in itertools.product([0, 1], repeat=2)}
        rows.append({"A": int(facts[0]), "S": int(facts[1]), "C": int(facts[2]),
                     "gold": int(gold(*facts)), "outputs": outputs})
    assert all(row["outputs"]["11"] == row["gold"] for row in rows)
    uniform = {v: sum(row["outputs"][v] == row["gold"] for row in rows)
               for v in ["00", "10", "01", "11"]}
    assert uniform == {"00": 7, "10": 6, "01": 7, "11": 8}
    # Two distinct eligible student cases are allowed to share this Boolean projection.
    cohort = [(1, 0, 0), (1, 0, 1), (1, 1, 1), (1, 1, 1), (0, 1, 1), (1, 1, 0)]
    cohort_scores = {f"{p}{c}": sum(run(*facts, p, c) == gold(*facts) for facts in cohort)
                     for p, c in itertools.product([0, 1], repeat=2)}
    assert cohort_scores == {"00": 5, "01": 4, "10": 4, "11": 6}
    result = {
        "status": "constructed deterministic illustration, not native performance",
        "uniform_domain_n": 8, "uniform_correct": uniform,
        "uniform_rows": rows,
        "six_case_boolean_projections": cohort,
        "six_case_correct": cohort_scores,
        "interpretation": "Strict singleton-improvement cannot cross this repair valley; a full joint-search baseline can.",
    }
    path = Path(__file__).with_name("JOINT_REVISION_FINITE_CHECK.json")
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"path": str(path), "uniform": uniform, "six_case": cohort_scores}))


if __name__ == "__main__":
    main()
