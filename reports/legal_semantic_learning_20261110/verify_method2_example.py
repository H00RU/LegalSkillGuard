"""Deterministic illustration of scope supervision; not a learned-model result."""
from itertools import product
import json
from pathlib import Path


def evaluate(name, b, e, r):
    if name == "gold_nested":
        return b and not (e and not r)
    if name == "restore_outside_base":
        return (b and not e) or r
    if name == "parallel_exclusions":
        return b and not e and not r
    raise ValueError(name)


def main():
    candidates = ("restore_outside_base", "parallel_exclusions")
    rows = []
    witnesses = {name: [] for name in candidates}
    for b, e, r in product((False, True), repeat=3):
        vals = {name: evaluate(name, b, e, r)
                for name in ("gold_nested", *candidates)}
        row = {"facts": {"b": b, "e": e, "r": r}, "outputs": vals}
        rows.append(row)
        for name in candidates:
            if vals[name] != vals["gold_nested"]:
                witnesses[name].append(row["facts"])
    assert evaluate("gold_nested", True, True, True)
    assert not evaluate("parallel_exclusions", True, True, True)
    assert not evaluate("gold_nested", False, True, True)
    assert evaluate("restore_outside_base", False, True, True)
    r_false_indistinguishable = all(
        len(set(row["outputs"].values())) == 1
        for row in rows if not row["facts"]["r"]
    )
    assert r_false_indistinguishable
    result = {
        "status": "deterministic_example_only",
        "fact_domain": "all 8 Boolean assignments; no additional legal constraints",
        "r_false_training_cases_cannot_distinguish_all_three": True,
        "wrong_composition_witnesses": witnesses,
        "truth_table": rows,
    }
    destination = Path(__file__).with_name("method2_example_result.json")
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"assignments": 8, "assertions_passed": True,
                      "witness_counts": {k: len(v) for k, v in witnesses.items()}}))


if __name__ == "__main__":
    main()
