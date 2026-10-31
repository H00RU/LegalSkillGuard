"""Completed-stage original-SPAN coverage, not a proposed or repaired answer.

All four before arms must have all six sources before any scores are read.
Candidate-only counts describe the search interface; they are not native model
performance, legal correctness, a selected bank or an achievable upper bound.
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from jsonschema import validate

from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.learning.audit import close, original_score
from legal_skill_guard.learning.experiment import now, read, sha
from legal_skill_guard.task import marked_text
from legal_skill_guard.utils.hashing import canonical_json_sha256

ARMS = ("strong_empty", "ordinary_memory", "unconditional_layout", "skill_memory")


def aggregate(records):
    n = len(records)
    nn = [q for q in records if q["Gold_choice"] != "NotMentioned"]
    tp, fp, fn = (sum(q[k] for q in nn) for k in ("tp", "fp", "fn"))
    return {
        "documents": len({q["document_id"] for q in records}), "hypotheses": n,
        "label_correct": sum(q["label_correct"] for q in records),
        "label_accuracy": sum(q["label_correct"] for q in records) / n,
        "evidence_tp": tp, "evidence_fp": fp, "evidence_fn": fn,
        "evidence_micro_f1_gold_non_neutral": 2 * tp / (2 * tp + fp + fn),
        "joint_exact_correct": sum(q["joint_exact"] for q in records),
        "joint_exact_accuracy": sum(q["joint_exact"] for q in records) / n,
        "nonneutral_label_and_all_evidence_correct": sum(q["joint_exact"] for q in nn),
        "correct_nm_with_empty_evidence": sum(q["joint_exact"] for q in records if q["Gold_choice"] == "NotMentioned"),
    }


def coverage(records):
    counts = Counter()
    for q in records:
        if q["Gold_choice"] == "NotMentioned":
            continue
        gold, pred, pool = (set(q[k]) for k in ("Gold_spans", "native_spans", "visible_candidates"))
        counts.update({
            "Gold_non_NM_queries": 1, "pool_tp": len(gold & pool),
            "pool_fp": len(pool - gold), "pool_fn": len(gold - pool),
            "pool_exact_queries": int(gold == pool), "empty_pool_queries": int(not pool),
            "native_missing_members": len(gold - pred),
            "native_missing_already_candidates": len((gold - pred) & pool),
            "native_missing_outside_candidates": len(gold - pred - pool),
            "native_true_members_from_pool": len(gold & pred & pool),
            "native_true_members_outside_pool": len((gold & pred) - pool),
            "native_set_equals_visible_pool": int(pred == pool),
            "pool_exact_but_native_not_exact": int(gold == pool and pred != gold),
            "missing_members_on_correct_labels": len(gold - pred) if q["label_correct"] else 0,
        })
    return {**counts, "pool_F1_descriptive_not_native_performance": 2 * counts["pool_tp"] / (2 * counts["pool_tp"] + counts["pool_fp"] + counts["pool_fn"])}


def analyse(batch, stage):
    cfg_path = ROOT / "configs/contractnli_literal_fixed_static.json"
    cfg, frozen = read(cfg_path), read(cfg_path.with_suffix(".frozen.json"))
    assert frozen["config_sha256"] == sha(cfg_path)
    assert all(sha(p) == digest for p, digest in frozen["files"].items())
    packet = read(ROOT / cfg["input_packet"])
    ids = [r["id"] for r in packet["training"] if r["batch"] == batch]
    arms = ARMS if stage == "before" else ("skill_memory",)
    paths = {arm: [OUT / f"batch{batch}_{stage}/{arm}/{d}.public.json" for d in ids] for arm in arms}
    assert len(ids) == 6 and all(p.exists() for values in paths.values() for p in values), "Never grade an incomplete stage or selected source subset"
    archive_path = ROOT / cfg["source_archive"]
    assert sha(archive_path) == cfg["source_archive_sha256"]
    with zipfile.ZipFile(archive_path) as archive:
        author = json.loads(archive.read("contract-nli/train.json"))
    rows = {r["id"]: r for r in author["documents"] if r["id"] in ids}
    labels = author["labels"]
    assert labels == packet["public_hypotheses"]
    version = batch - (stage == "before")
    bank_path = OUT / f"update_transactions/b{version}.json"
    bank = read(bank_path)["publication"]
    audited = {**frozen["files"], str(cfg_path): sha(cfg_path), str(bank_path): sha(bank_path), str(__file__): sha(__file__)}
    groups, raw_ids = {}, []
    for arm, values in paths.items():
        records = []
        for d, p in zip(ids, values, strict=True):
            row, unit = rows[d], read(p)
            assert unit["document_id"] == d and unit["stage"] == f"batch{batch}_{stage}" and unit["arm"] == arm
            assert unit["published_library"] == (bank if arm == "skill_memory" else [])
            assert unit["published_library_sha256"] == canonical_json_sha256(unit["published_library"])
            raw_path = Path(unit["raw_artifact"])
            raw = read(raw_path)
            assert len(raw["calls"]) == 1 and raw["response"] == unit["response"]
            request = raw["calls"][0]["request"]
            payload = json.loads(request["messages"][1]["content"])
            assert payload["full_contract_with_original_span_markers"] == marked_text(row)
            for name in ("model", "temperature", "top_p", "top_k", "max_tokens", "seed"):
                assert request[name] == cfg["generation"][name]
            score = original_score(unit["response"], row, row["annotation_sets"][0]["annotations"], list(labels))
            assert score["public_valid"] and unit["public_valid"]
            validate(score["parsed"], request["response_format"]["json_schema"]["schema"])
            close(score["queries"], unit["queries"])
            proposals = unit["actual_factual_trace"]["proposals"]
            for q in score["queries"]:
                h = q["hypothesis_id"]
                candidates = [] if proposals is None else proposals["by_hypothesis"][h]["candidates"]
                assert payload["hypotheses"][h]["fallible_evidence_candidates"] == (None if proposals is None else candidates)
                for c in candidates:
                    start, end = row["spans"][c["original_span_index"]]
                    assert c["literal_original_text"] == row["text"][start:end]
                records.append({
                    "document_id": d, "hypothesis_id": h, "Gold_choice": q["gold"]["choice"],
                    "Gold_spans": q["gold"]["spans"], "native_choice": q["prediction"]["choice"],
                    "native_spans": q["prediction"]["spans"], "native_reason": q["prediction"]["reason"],
                    "visible_candidates": [c["original_span_index"] for c in candidates],
                    "label_correct": q["label_correct"], "joint_exact": q["joint_exact"],
                    **{short: q["evidence_" + short] for short in ("tp", "fp", "fn")},
                })
            raw_ids.append(unit["response"]["raw_id"])
            audited.update({str(p): sha(p), str(raw_path): sha(raw_path)})
        groups[arm] = records
    assert len(raw_ids) == len(set(raw_ids)) == len(arms) * 6
    result = {
        "at": now(), "run_id": cfg["run_id"], "batch": batch, "stage": stage,
        "complete_source_ids": ids, "distinct_native_responses": len(raw_ids),
        "original_author_scores_actual_native_wires_and_literal_candidates_checked": True,
        "audited_file_sha256": audited,
        "metrics": {a: aggregate(qs) for a, qs in groups.items()},
        "candidate_coverage_NOT_native_answers_or_score_admission": {a: coverage(qs) for a, qs in groups.items()},
        "all_query_records": groups,
        "no_new_model_teacher_calls_inference_rewrite_or_endpoint_Gold": True,
        "factual_error_strata_not_internal_attention_or_single_skill_causal_proof": True,
    }
    destination = OUT / f"monitoring/complete_B{batch}_{stage}_original_candidate_coverage_audit.json"
    RunStore.immutable_json(destination, result)
    print(json.dumps({k: v for k, v in result.items() if k not in ("audited_file_sha256", "all_query_records")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=int, required=True, choices=(2, 3, 4))
    parser.add_argument("--stage", required=True, choices=("before", "after"))
    args = parser.parse_args()
    analyse(args.batch, args.stage)
