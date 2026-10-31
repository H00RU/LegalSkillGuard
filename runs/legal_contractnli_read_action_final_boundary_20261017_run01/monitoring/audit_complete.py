"""Manual original-set comparison after all eight counterfactual finals exist."""

# ruff: noqa: E402
from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1]
PARENT = ROOT / "runs/legal_contractnli_source_read_execution_diagnostic_20261017_run01"
sys.path.insert(0, str(ROOT))

from jsonschema import validate

from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.learning.experiment import now, read, sha


def summarize(rows):
    tp, fp, fn = (sum(r[k] for r in rows) for k in ("tp", "fp", "fn"))
    label, joint = (sum(r[k] for r in rows) for k in ("label_correct", "joint_exact"))
    return {"hypotheses": len(rows), "label_correct": label, "label_accuracy": label / len(rows),
        "evidence_tp": tp, "evidence_fp": fp, "evidence_fn": fn,
        "evidence_micro_f1_gold_non_neutral": 2 * tp / (2 * tp + fp + fn),
        "joint_exact_correct": joint, "joint_exact_accuracy": joint / len(rows),
        "NN_joint": sum(r["joint_exact"] and r["Gold_choice"] != "NotMentioned" for r in rows),
        "NM_joint": sum(r["joint_exact"] and r["Gold_choice"] == "NotMentioned" for r in rows),
        "Gold_reread_but_not_final_cited": sum(len(set(r["Gold_spans"]) & set(r["reread_indices"]) - set(r["spans"])) for r in rows if r["Gold_choice"] != "NotMentioned"),
        "final_all_members_not_reread": sum(len(set(r["spans"]) - set(r["reread_indices"])) for r in rows)}


def contrast(rows, old_arm):
    old = {(r["document_id"], r["hypothesis_id"]): r for r in rows if r["arm"] == old_arm}
    new = [r for r in rows if r["arm"] == "no_final_inspection"]
    result = {k: 0 for k in ("label_fixes", "label_damage", "joint_fixes", "joint_damage", "true_members_gained", "true_members_lost")}
    for r in new:
        before = old[(r["document_id"], r["hypothesis_id"])]
        for field, prefix in (("label_correct", "label"), ("joint_exact", "joint")):
            result[prefix + "_fixes"] += int(r[field] and not before[field])
            result[prefix + "_damage"] += int(before[field] and not r[field])
        if r["Gold_choice"] != "NotMentioned":
            gold, previous, current = (set(x) for x in (r["Gold_spans"], before["spans"], r["spans"]))
            result["true_members_gained"] += len((gold & current) - previous)
            result["true_members_lost"] += len((gold & previous) - current)
    return result


def main():
    complete, registry = read(OUT / "completion.json"), read(OUT / "registration.json")
    assert read(OUT / "progress.json")["state"] == "completed"
    assert complete["actual_new_native_teacher_calls"] == [8, 0]
    assert all(sha(path) == h for path, h in registry["files"].items())
    cfg = read(ROOT / "configs/contractnli_source_programs_completion.json")
    assert sha(ROOT / cfg["source_archive"]) == cfg["source_archive_sha256"]
    with zipfile.ZipFile(ROOT / cfg["source_archive"]) as archive:
        author = json.loads(archive.read("contract-nli/train.json"))
    original = {r["id"]: r for r in author["documents"]}
    parent_audit_path = PARENT / "monitoring/complete32_original_sets_actual_read_and_citation_class_diagnosis.json"
    parent_audit = read(parent_audit_path)
    rows = parent_audit["all_query_records"].copy()
    usage, raw_ids = {"prompt_tokens": 0, "completion_tokens": 0}, set()
    bindings = {**registry["files"], str(parent_audit_path): sha(parent_audit_path)}
    for e in complete["actual_new_answers"]:
        p, raw = read(e["path"]), read(e["raw_path"])
        old = read(p["parent_exact_final_payload"])
        assert len(raw["calls"]) == 1 and raw["transport_error"] is None
        wire, server = (raw["calls"][0][k] for k in ("request", "response"))
        assert wire["messages"] == p["messages"]
        assert wire["response_format"]["json_schema"]["schema"] == p["schema"] == old["schema"]
        assert all(wire[k] == cfg["generation"][k] for k in ("model", "temperature", "top_p", "top_k", "max_tokens", "seed"))
        assert p["messages"][0] == old["messages"][0] and p["messages"][2:] == old["messages"][2:]
        body, before = (json.loads(v["messages"][1]["content"]) for v in (p, old))
        for new_skill, old_skill in zip(body["published_contextual_skills"], before["published_contextual_skills"], strict=True):
            assert new_skill["guidance"]["inspection"] == ""
            new_skill["guidance"]["inspection"] = old_skill["guidance"]["inspection"]
        assert body == before
        response = raw["response"]
        assert response["content"] == server["choices"][0]["message"]["content"]
        assert response["finish_reason"] == server["choices"][0]["finish_reason"] == "stop"
        assert response["raw_id"] == server["id"] and response["raw_id"] not in raw_ids
        raw_ids.add(response["raw_id"])
        validate(json.loads(response["content"]), p["schema"])
        assert server["choices"][0]["message"]["reasoning_content"]
        for k in usage:
            assert response[k] == server["usage"][k]
            usage[k] += response[k]
        doc, stage = e["document_id"], e["stage"]
        source = original[doc]
        actions = json.loads(p["messages"][2]["content"])
        values = json.loads(response["content"])
        for h, gold in source["annotation_sets"][0]["annotations"].items():
            v, nn = values[h], gold["choice"] != "NotMentioned"
            gs, ps = set(gold["spans"]), set(v["spans"])
            rows.append({"stage": stage, "arm": "no_final_inspection", "document_id": doc,
                "hypothesis_id": h, "Gold_choice": gold["choice"], "Gold_spans": gold["spans"], **v,
                "original_hypothesis": body["hypotheses"][h]["original_hypothesis"],
                "reread_indices": actions[h]["original_span_indices"], "reading_focus": actions[h]["inspection_focus"],
                "label_correct": v["choice"] == gold["choice"],
                "joint_exact": v["choice"] == gold["choice"] and gs == ps,
                "tp": len(gs & ps) if nn else 0, "fp": len(ps - gs) if nn else 0, "fn": len(gs - ps) if nn else 0})
        bindings[e["raw_path"]] = sha(e["raw_path"])
    assert len(raw_ids) == 8 and len(rows) == 408
    arms = ("empty_read", "skill_read", "no_final_inspection")
    metrics = {stage: {arm: summarize([r for r in rows if r["stage"] == stage and r["arm"] == arm]) for arm in arms} for stage in ("B6", "B7")}
    for stage in metrics:
        for k, value in metrics[stage]["no_final_inspection"].items():
            if k not in ("NN_joint", "NM_joint", "Gold_reread_but_not_final_cited", "final_all_members_not_reread"):
                assert abs(value - complete["stage_metrics"][stage][k]) < 1e-12
    index = {(r["document_id"], r["hypothesis_id"], r["arm"]): r for r in rows}
    changes = []
    for r in rows:
        if r["arm"] != "no_final_inspection":
            continue
        old = index[(r["document_id"], r["hypothesis_id"], "skill_read")]
        if r["choice"] != old["choice"] or set(r["spans"]) != set(old["spans"]):
            source = original[r["document_id"]]
            ii = sorted(set(r["Gold_spans"]) | set(r["spans"]) | set(old["spans"]))
            changes.append({"before": old, "after": r, "full_original_Gold_or_changed_cited_fragments": [
                {"index": i, "text": source["text"][slice(*source["spans"][i])]} for i in ii]})
    for p in (Path(__file__).resolve(), OUT / "completion.json", OUT / "registration.json"):
        bindings[str(p)] = sha(p)
    report = {"at": now(), "run_id": OUT.name, "all8_new_finals_and_manual_original_author_sets_and_actual_wire_intervention_checked": True,
        "phase_metrics": metrics, "combined_metrics": {arm: summarize([r for r in rows if r["arm"] == arm]) for arm in arms},
        "phase_contrasts": {stage: {old: contrast([r for r in rows if r["stage"] == stage], old) for old in arms[:2]} for stage in metrics},
        "combined_contrasts": {old: contrast(rows, old) for old in arms[:2]},
        "all_query_records": rows, "all_changed_public_answers_and_original_fragments": changes,
        "actual_new_final_usage": usage, "shared_parent_source_reads_and_controls_not_free_or_independent": parent_audit["actual_usage_by_arm_role"],
        "historical_stronger_one_call_reference": parent_audit["historical_stronger_one_call_reference"],
        "bindings": bindings, "not_new_online_learning_or_independent_repeat_or_mature_method_win_or_TEST": True}
    dest = OUT / "monitoring/complete8_manual_original_sets_same_actions_final_guidance_and_strong_controls_audit.json"
    RunStore.immutable_json(dest, report)
    print(json.dumps({k: report[k] for k in ("phase_metrics", "combined_metrics", "combined_contrasts")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
