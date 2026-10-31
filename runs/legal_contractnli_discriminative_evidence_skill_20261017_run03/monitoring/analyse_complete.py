"""Completed-only paired source/member mechanism analysis; no generation.

Read original TRAIN and real native wires, not intermediate scorer predictions.
This is eight already-taught development contracts, not algorithmic stability,
independent learning, new-case transfer or an official TEST result.
"""

# ruff: noqa: E402 -- This run-local analysis binds its own authoritative project.
from __future__ import annotations

import json
import sys
import zipfile
from collections import Counter
from pathlib import Path

import numpy as np
from jsonschema import ValidationError, validate

OUT = Path(__file__).resolve().parents[1]
ROOT = OUT.parents[1]
sys.path.insert(0, str(ROOT))

from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.learning.experiment import now, read, sha

ARMS = ["skills", "acquisition", "ordinary", "strong_empty"]
SEED, BOOTSTRAPS = 20261017, 5000


def counts(rows):
    nn = [r for r in rows if r["Gold_choice"] != "NotMentioned"]
    tp = sum(len(set(r["Gold_spans"]) & set(r["spans"])) for r in nn)
    fp = sum(len(set(r["spans"]) - set(r["Gold_spans"])) for r in nn)
    fn = sum(len(set(r["Gold_spans"]) - set(r["spans"])) for r in nn)
    n, correct = len(rows), sum(r["label_correct"] for r in rows)
    joint = sum(r["joint_exact"] for r in rows)
    return {"hypotheses": n, "original_NN": len(nn), "label_correct": correct,
        "label_accuracy": correct / n if n else None,
        "evidence_tp": tp, "evidence_fp": fp, "evidence_fn": fn,
        "evidence_micro_f1_gold_non_neutral": 2 * tp / (2 * tp + fp + fn) if nn else None,
        "joint_exact_correct": joint, "joint_exact_accuracy": joint / n if n else None}


def contrast(before, after):
    a, b = ({(r["document_id"], r["hypothesis_id"]): r for r in rows} for rows in (before, after))
    assert set(a) == set(b)
    out = Counter()
    changes = []
    for k, x in a.items():
        y = b[k]
        flags = {"label_fixes": not x["label_correct"] and y["label_correct"],
            "label_damage": x["label_correct"] and not y["label_correct"],
            "joint_fixes": not x["joint_exact"] and y["joint_exact"],
            "joint_damage": x["joint_exact"] and not y["joint_exact"]}
        out.update({key: int(value) for key, value in flags.items()})
        if x["Gold_choice"] != "NotMentioned":
            gold, old, new = (set(z) for z in (x["Gold_spans"], x["spans"], y["spans"]))
            out.update(true_members_gained=len(gold & new - old), true_members_lost=len(gold & old - new),
                false_citations_added=len(new - old - gold), false_citations_removed=len(old - new - gold))
        if any(flags.values()) or x["spans"] != y["spans"]:
            changes.append({"document_id": k[0], "hypothesis_id": k[1], "Gold_choice": x["Gold_choice"],
                "Gold_spans": x["Gold_spans"], "before_choice": x["choice"], "after_choice": y["choice"],
                "before_spans": x["spans"], "after_spans": y["spans"], **flags})
    left, right = counts(before), counts(after)
    return {"fix_damage_and_members": dict(out), "difference_after_minus_before": {
        k: right[k] - left[k] for k in ("label_accuracy", "evidence_micro_f1_gold_non_neutral", "joint_exact_accuracy")},
        "all_changed_questions": changes}


def intervals(before, after, ids):
    def matrix(rows):
        values = [counts([r for r in rows if r["document_id"] == d]) for d in ids]
        return np.array([[r[k] for k in ("hypotheses", "label_correct", "evidence_tp", "evidence_fp",
            "evidence_fn", "joint_exact_correct")] for r in values], dtype=float)
    a, b = matrix(before), matrix(after)
    draws = np.random.default_rng(SEED).integers(0, len(ids), size=(BOOTSTRAPS, len(ids)))
    def endpoints(m):
        v = m[draws].sum(axis=1)
        denominator = 2 * v[:, 2] + v[:, 3] + v[:, 4]
        assert np.all(denominator > 0)
        return np.column_stack((v[:, 1] / v[:, 0], 2 * v[:, 2] / denominator, v[:, 5] / v[:, 0]))
    delta = endpoints(b) - endpoints(a)
    return {"original_contract_clusters": len(ids), "replicates": BOOTSTRAPS, "seed": SEED,
        "fixed_learned_bank_seen_TRAIN_conditional_descriptive_not_algorithmic_stability_or_confirmatory_test": True,
        "percentile_95_intervals_after_minus_before": {key: np.quantile(delta[:, i], [.025, .975]).tolist()
            for i, key in enumerate(("label_accuracy", "evidence_micro_f1_gold_non_neutral", "joint_exact_accuracy"))}}


def failures(rows):
    counts, confusion = Counter(), Counter()
    for r in rows:
        confusion[f"{r['Gold_choice']}->{r['choice']}"] += 1
        if r["Gold_choice"] == "NotMentioned":
            counts["NM_questions"] += 1
            counts["NM_wrong_relation"] += not r["label_correct"]
            continue
        gold, cited, ordinary = map(set, (r["Gold_spans"], r["spans"], r["ordinary"]))
        direct = {x["original_span_index"] for x in r["additional"] if x["literal_match"]}
        context = {x["original_span_index"] for x in r["additional"] if not x["literal_match"]}
        roles = {"ordinary_C": ordinary, "extra_direct": direct, "extra_context_only": context}
        for name, positions in roles.items():
            counts[f"{name}_Gold"] += len(gold & positions)
            counts[f"{name}_Gold_cited"] += len(gold & positions & cited)
            counts[f"{name}_nonGold_cited"] += len(cited & positions - gold)
        outside = cited - ordinary - direct - context
        counts["outside_leads_Gold_cited"] += len(outside & gold)
        counts["outside_leads_nonGold_cited"] += len(outside - gold)
        bucket = "correct_label" if r["label_correct"] else "wrong_NM" if r["choice"] == "NotMentioned" else "wrong_E_or_C_or_invalid"
        counts[f"FN_with_{bucket}"] += len(gold - cited)
        counts[f"FP_with_{bucket}"] += len(cited - gold)
    return {"member_roles_NN_only_NM_has_no_member_labels": dict(counts), "original_to_predicted_relation": dict(confusion)}


def main():
    complete = read(OUT / "completion.json")
    audit = read(OUT / "monitoring/complete32_actual_wires_teacher_original_member_and_ablation_audit.json")
    assert [complete["completed_native_calls"], complete["completed_teacher_calls"]] == [32, 1]
    assert audit["all32_actual_wires_and_original_author_members_checked"]
    declaration = read(OUT / "declaration.json")
    cfg = declaration["config"]
    assert cfg["run_id"] == OUT.name and cfg["diagnostic_arms"] == ARMS
    assert sha(ROOT / cfg["source_archive"]) == cfg["source_archive_sha256"]
    with zipfile.ZipFile(ROOT / cfg["source_archive"]) as archive:
        author = json.loads(archive.read("contract-nli/train.json"))
    sources, labels = {r["id"]: r for r in author["documents"]}, author["labels"]
    units = read(OUT / "complete32_native_and_original_scores.json")["units"]
    before_outcomes = read(OUT / "monitoring/publication_source_delta_and_pre_outcome_subgroup_definition.json")
    scopes = set(before_outcomes["criterion_hypotheses_fixed_by_publication"])
    all_rows = {a: [] for a in ARMS}
    for u in units:
        p, raw = read(u["payload"]), read(u["raw_artifact"])
        assert raw["response"] == u["response"] and len(raw["calls"]) == 1
        wire = raw["calls"][0]
        assert wire["request"]["messages"] == p["messages"]
        served = json.loads(wire["request"]["messages"][1]["content"])
        value = None
        try:
            assert raw["response"]["finish_reason"] == "stop"
            value = json.loads(raw["response"]["content"])
            validate(value, p["schema"])
        except (ValueError, TypeError, ValidationError, AssertionError):
            value = None
        d, arm = u["document_id"], u["condition"]
        gold = sources[d]["annotation_sets"][0]["annotations"]
        for h in labels:
            g, v = gold[h], value[h] if value is not None else None
            choice, spans = (v["choice"], v["spans"]) if v is not None else (None, [])
            correct = choice == g["choice"]
            all_rows[arm].append({"document_id": d, "hypothesis_id": h, "Gold_choice": g["choice"],
                "Gold_spans": g["spans"], "choice": choice, "spans": sorted(set(spans)),
                "label_correct": correct, "joint_exact": correct and set(spans) == set(g["spans"]),
                "criterion_in_published_scope": h in scopes,
                "ordinary": [x["original_span_index"] for x in served["hypotheses"][h]["fallible_evidence_candidates"]],
                "additional": served["hypotheses"][h]["additional_source_read_indices"]})
    metrics = {a: counts(v) for a, v in all_rows.items()}
    for a, metrics_a in metrics.items():
        assert all(complete["results"][a][k] == v for k, v in metrics_a.items() if k != "original_NN")
    ids = cfg["diagnostic_source_ids"]
    report = {"at": now(), "run_id": OUT.name, "actual_contracts": 8,
        "actual_new_native_teacher_calls": [32, 1], "metrics": metrics,
        "paired_skills_vs_controls": {a: contrast(all_rows[a], all_rows["skills"]) for a in ARMS if a != "skills"},
        "conditional_source_intervals_skills_vs_controls": {a: intervals(all_rows[a], all_rows["skills"], ids) for a in ARMS if a != "skills"},
        "by_source": {str(d): {a: counts([r for r in rows if r["document_id"] == d]) for a, rows in all_rows.items()} for d in ids},
        "by_pre_outcome_criterion_scope": {str(present): {a: counts([r for r in rows if r["criterion_in_published_scope"] == present])
            for a, rows in all_rows.items()} for present in (True, False)},
        "by_original_hypothesis": {h: {a: counts([r for r in rows if r["hypothesis_id"] == h]) for a, rows in all_rows.items()} for h in labels},
        "failures_by_arm": {a: failures(rows) for a, rows in all_rows.items()},
        "actual_own_training_errors_before_update_not_new_native_effects": "See parent32 original-member failure decomposition, not the current eight-case endpoint.",
        "actual_new_native_usage": complete["actual_native_usage"],
        "actual_teacher_invocations": complete["actual_teacher_invocations"],
        "prior_stopped_contract_trial_actual_native_teacher_calls_not_free_or_erased": [2, 1],
        "not_independent_learning_new_case_transfer_mature_method_comparison_or_official_TEST": True,
        "no_new_generation_or_teacher_calls_for_analysis": True,
        "bindings": {str(p): sha(p) for p in (Path(__file__).resolve(), OUT / "completion.json",
            OUT / "complete32_native_and_original_scores.json", OUT / "publications/b5.json",
            OUT / "monitoring/complete32_actual_wires_teacher_original_member_and_ablation_audit.json",
            OUT / "monitoring/publication_source_delta_and_pre_outcome_subgroup_definition.json")}}
    path = OUT / "monitoring/complete32_paired_source_criterion_scope_and_native_member_analysis.json"
    RunStore.immutable_json(path, report)
    print(json.dumps({"report": str(path), "metrics": metrics}, ensure_ascii=False))


if __name__ == "__main__":
    main()
