"""Descriptive trace audit of completed TRAIN batches, never a learning gate.

No generation, teacher calls, later endpoint data or answer rewriting. Mechanical
match overlap is not causal attribution or independently judged legal relevance.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from legal_skill_guard.experiment.storage import RunStore

ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / "runs/legal_contractnli_grounded_feedback_learning_20261015_run01"


def read(path):
    return json.loads(path.read_text())


def metrics(value):
    tp, fp, fn = (value["evidence_" + k] for k in ("tp", "fp", "fn"))
    return {
        "label_correct": value["label_correct"],
        "hypotheses": value["hypotheses"],
        "accuracy": value["label_accuracy"],
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "f1": value["evidence_micro_f1_gold_non_neutral"],
        "tp_fp_fn": [tp, fp, fn],
        "joint_correct": value["joint_exact_correct"],
        "joint": value["joint_exact_accuracy"],
        "valid_documents": value["public_valid_documents"],
        "cutoffs": value["length_cutoffs"],
    }


def analyse():
    batches = []
    for path in sorted(RUN.glob("batch*_summary.json")):
        summary = read(path)
        batch = summary["batch"]
        entry = {
            "batch": batch,
            "source_ids": summary["source_ids"],
            "strong_empty": metrics(summary["strong_empty"]),
            "empty_receipts": metrics(summary["empty_receipts"]),
            "learners": {},
        }
        for arm in ("standard", "grounded"):
            counts = Counter()
            queries = []
            current = {}
            for doc in summary["source_ids"]:
                unit = read(RUN / f"batch{batch}_after" / arm / f"{doc}.public.json")
                for q in unit["queries"]:
                    key = q["hypothesis_id"]
                    current[f"{doc}/{key}"] = q
                    invocations = unit["actual_factual_trace"][key]["published_skill_invocations"]
                    if not invocations:
                        continue
                    receipts = [r for i in invocations for r in i["receipts"]]
                    matched = {n for r in receipts for n in r["matched_original_span_indices"]}
                    context = {
                        c["original_span_index"]
                        for r in receipts
                        for c in r["context_original_clauses"]
                    }
                    gold = set(q["gold"]["spans"])
                    chosen = set(q["prediction"]["spans"]) if q["prediction"] else set()
                    false = chosen - gold
                    exact_copy = bool(matched) and chosen == matched
                    counts["scoped_queries"] += 1
                    counts["exact_nonempty_match_set_copies"] += exact_copy
                    if q["gold_non_neutral"]:
                        counts["gold_memberships"] += len(gold)
                        counts["gold_in_matches"] += len(gold & matched)
                        counts["gold_in_matches_but_omitted"] += len((gold & matched) - chosen)
                        counts["gold_in_match_or_neighbour_context"] += len(gold & context)
                        counts["gold_in_context_but_omitted"] += len((gold & context) - chosen)
                        counts["false_selected"] += len(false)
                        counts["false_selected_in_matches"] += len(false & matched)
                        counts["false_selected_only_in_neighbour_context"] += len(
                            (false & context) - matched
                        )
                        counts["false_selected_outside_query_context"] += len(false - context)
                    queries.append(
                        {
                            "document_id": doc,
                            "hypothesis_id": key,
                            "gold_non_neutral": q["gold_non_neutral"],
                            "original_gold_spans": sorted(gold),
                            "actual_predicted_spans": sorted(chosen),
                            "mechanical_match_indices": sorted(matched),
                            "exact_copy_of_nonempty_match_union": exact_copy,
                            "label_correct": q["label_correct"],
                            "joint_exact": q["joint_exact"],
                            "false_selected_count": len(false),
                        }
                    )
            transaction = read(RUN / "update_transactions" / f"{arm}_b{batch}.json")
            reviews = transaction["actual_teacher_value"].get("coverage_review", {})
            current_reviews = {k: v for k, v in reviews.items() if k in current}
            entry["learners"][arm] = {
                "before_first_encounter": metrics(summary["before"][arm]),
                "after_seen_training_fit": metrics(summary["after"][arm]),
                "teacher_claimed_dispositions_all_seen": dict(
                    Counter(r["disposition"] for r in reviews.values())
                ),
                "current_batch_reviewed_issues": len(current_reviews),
                "current_reviewed_issues_now_joint_exact": sum(
                    current[k]["joint_exact"] for k in current_reviews
                ),
                "joint_fixed": len(summary["update_effects"][arm]["joint_exact_corrected"]),
                "joint_broken": len(summary["update_effects"][arm]["joint_exact_broken"]),
                "query_overlap_counts": dict(counts),
                "per_scoped_query": queries,
            }
        batches.append(entry)
    result = {
        "at": datetime.now(UTC).isoformat(),
        "run_id": RUN.name,
        "completed_batches_only": batches,
        "later_inputs_or_grading_never_opened": True,
        "descriptive_not_causal_isolation_or_publication_admission": True,
        "teacher_claims_are_not_proof_of_real_repairs": True,
    }
    RunStore.atomic_json(Path(__file__).parent / "mechanism_latest.json", result)
    print("Full descriptive audit: " + str(Path(__file__).parent / "mechanism_latest.json"))
    for batch in batches:
        for arm, data in batch["learners"].items():
            print(
                json.dumps(
                    {
                        "batch": batch["batch"],
                        "arm": arm,
                        "before": data["before_first_encounter"],
                        "after": data["after_seen_training_fit"],
                        "query_overlap": data["query_overlap_counts"],
                        "reviewed_current_issues": data["current_batch_reviewed_issues"],
                        "reviewed_now_joint_exact": data["current_reviewed_issues_now_joint_exact"],
                    },
                    ensure_ascii=False,
                )
            )


if __name__ == "__main__":
    analyse()
