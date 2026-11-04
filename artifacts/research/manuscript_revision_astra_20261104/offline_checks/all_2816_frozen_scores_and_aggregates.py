import os, sys
from pathlib import Path
root = Path(__file__).resolve().parents[4]
os.chdir(root)
sys.path.insert(0, str(root))
import json, math, socket, hashlib
from pathlib import Path
def blocked(*args, **kwargs):
    raise RuntimeError("Network prohibited in this read-only numerical review")
socket.socket.connect = blocked
socket.create_connection = blocked
from legal_skill_guard.openexempt import evaluate, metrics
def read(p):
    return json.loads(Path(p).read_text())
old = read("runs/legal_openexempt_v6_frozen_source_isolated_IID128_20261031_run01/scored_records.json")
scpath = "runs/legal_openexempt_skillcommit_paper_public_assets128_seed45_20261102_run05/TEST_scored_records.json"
old["skillcommit_paper45"] = read(scpath)
table = read("paper/tables/utility_frozen_results_with_skillcommit_20261104.json")
gold = {p.stem: read(p) for p in Path("data/packets/openexempt_IID128_confirmatory_TEST_20261030/grading_only").glob("*.json")}
def norm(x):
    if isinstance(x, float) and not math.isfinite(x):
        return None
    if isinstance(x, dict):
        return {k: norm(v) for k, v in x.items()}
    if isinstance(x, list):
        return [norm(v) for v in x]
    return x
def canonical_unordered(x):
    if isinstance(x, dict):
        return {k: canonical_unordered(v) for k, v in x.items()}
    if isinstance(x, list):
        return sorted([canonical_unordered(v) for v in x], key=lambda v: json.dumps(v, sort_keys=True))
    return x
score_mismatches, aggregate_mismatches, diagnostics = [], [], {}
for name, rows in old.items():
    counts = {f: {"n": 0, "strict_exact": 0, "order_insensitive_exact": 0,
                  "native_f1_one": 0, "complete_f1_one": 0,
                  "complete_one_but_not_strict": 0, "order_only_recoveries": 0,
                  "order_only_example_ids": [], "invalid": 0} for f in ("EC", "EV")}
    rescored = []
    for r in rows:
        target = gold[str(r["case_id"])]["targets"][r["family"]]
        assert gold[str(r["case_id"])]["source_key"] == r["source_key"]
        answer = (r["parsed"] or {}).get("answer")
        now = norm(evaluate(r, answer, target))
        if now != norm(r["score"]):
            score_mismatches.append({"arm": name, "case_id": r["case_id"],
                                    "family": r["family"], "original": r["score"], "recomputed": now})
        rescored.append({**r, "score": now})
        c = counts[r["family"]]
        c["n"] += 1
        c["strict_exact"] += int(now["exact_target"])
        unordered = canonical_unordered(answer) == canonical_unordered(target)
        c["order_insensitive_exact"] += int(unordered)
        c["native_f1_one"] += int(now["f1"] == 1)
        c["complete_f1_one"] += int(now["full_output_f1"] == 1)
        c["complete_one_but_not_strict"] += int(now["full_output_f1"] == 1 and not now["exact_target"])
        c["invalid"] += int(now["invalid_format"])
        if unordered and not now["exact_target"]:
            c["order_only_recoveries"] += 1
            if len(c["order_only_example_ids"]) < 5:
                c["order_only_example_ids"].append(r["case_id"])
    published = next(a["metrics"] for a in table["conditions"] if a["condition"] == name)
    now_metrics = metrics(rescored)
    if published != now_metrics:
        aggregate_mismatches.append({"arm": name, "original": published, "recomputed": now_metrics})
    diagnostics[name] = counts
print(json.dumps({"purpose": "fresh read-only reproduction of every retained 11-condition frozen score and aggregate",
                  "records": sum(map(len, old.values())), "score_mismatch_count": len(score_mismatches),
                  "score_mismatches_first5": score_mismatches[:5],
                  "aggregate_mismatch_count": len(aggregate_mismatches),
                  "aggregate_mismatches_first2": aggregate_mismatches[:2],
                  "nonfinite_values_normalized_to_JSON_null_before_comparison": True,
                  "metric_diagnostics_not_replacements": diagnostics,
                  "network_disabled": True, "model_or_teacher_calls": 0}, ensure_ascii=False))
