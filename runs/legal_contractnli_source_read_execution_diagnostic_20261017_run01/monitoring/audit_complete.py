"""Independent manual original-member audit; refuses partial-stage grading."""

# ruff: noqa: E402
from __future__ import annotations

import copy
import importlib.util
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jsonschema import validate

from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.learning.experiment import now, read, sha
from legal_skill_guard.task import marked_text


def summary(rows):
    n = len(rows)
    tp, fp, fn = (sum(r[k] for r in rows) for k in ("tp", "fp", "fn"))
    lc, je = (sum(r[k] for r in rows) for k in ("label_correct", "joint_exact"))
    return {"hypotheses": n, "label_correct": lc, "label_accuracy": lc / n,
        "evidence_tp": tp, "evidence_fp": fp, "evidence_fn": fn,
        "evidence_micro_f1_gold_non_neutral": 2 * tp / (2 * tp + fp + fn),
        "joint_exact_correct": je, "joint_exact_accuracy": je / n,
        "NN_joint": sum(r["joint_exact"] and r["Gold_choice"] != "NotMentioned" for r in rows),
        "NM_joint": sum(r["joint_exact"] and r["Gold_choice"] == "NotMentioned" for r in rows)}


def paired(rows):
    indexed = {(r["document_id"], r["hypothesis_id"], r["arm"]): r for r in rows}
    result = {k: 0 for k in ("label_fixes", "label_damage", "joint_fixes", "joint_damage", "true_members_gained", "true_members_lost")}
    for r in rows:
        if r["arm"] != "empty_read":
            continue
        s = indexed[(r["document_id"], r["hypothesis_id"], "skill_read")]
        for field, prefix in (("label_correct", "label"), ("joint_exact", "joint")):
            result[prefix + "_fixes"] += int(s[field] and not r[field])
            result[prefix + "_damage"] += int(r[field] and not s[field])
        if r["Gold_choice"] != "NotMentioned":
            gold, empty, skill = (set(x) for x in (r["Gold_spans"], r["spans"], s["spans"]))
            result["true_members_gained"] += len((gold & skill) - empty)
            result["true_members_lost"] += len((gold & empty) - skill)
    return result


def main():
    assert read(OUT / "progress.json")["state"] == "completed", "No partial-stage grading"
    complete, registry = read(OUT / "completion.json"), read(OUT / "registration.json")
    assert complete["actual_new_native_teacher_calls"] == [32, 0]
    bindings = dict(registry["files"])
    assert all(sha(p) == h for p, h in bindings.items())
    cfg = read(ROOT / "configs/contractnli_source_programs_completion.json")
    assert sha(ROOT / cfg["source_archive"]) == cfg["source_archive_sha256"]
    with zipfile.ZipFile(ROOT / cfg["source_archive"]) as archive:
        author = json.loads(archive.read("contract-nli/train.json"))
    author_rows = {r["id"]: r for r in author["documents"]}
    inference = {r["id"]: r for r in read(OUT / "source_inputs_without_Gold.json")["documents"]}
    module_spec = importlib.util.spec_from_file_location("frozen_source_read", OUT / "experiment.py")
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    rows, raw_ids, usage, flows, wire_checks = [], set(), {}, {}, []
    for entry in registry["ordered_requests"]:
        stage, arm, doc = (entry[k] for k in ("stage", "arm", "document_id"))
        first, final = (OUT / f"native/{stage}/{arm}/{doc}.{role}.native.json" for role in ("source_read", "final"))
        initial = read(entry["path"])
        actual_path = OUT / f"prospective_actual/{stage}/{arm}/{doc}.final.json"
        second = read(actual_path)
        rpath = OUT / f"source_reads/{stage}/{arm}/{doc}.json"
        receipt = read(rpath)
        source, original = inference[doc], author_rows[doc]
        assert set(source) == {"id", "text", "spans"}
        assert all(source[k] == original[k] for k in source)
        assert json.loads(initial["messages"][1]["content"])["full_contract_with_original_span_markers"] == marked_text(original)
        requests = read(first)
        action = json.loads(requests["response"]["content"])
        assert receipt["actual_lawyer_requested_reads_by_hypothesis"] == action
        literal = {}
        for value in action.values():
            for i in value["original_span_indices"]:
                assert type(i) is int and 0 <= i < len(source["spans"])
                literal[str(i)] = source["text"][slice(*source["spans"][i])]
        assert receipt["returned_full_original_span_text_once"] == literal
        expected = copy.deepcopy(initial["final_base"]["messages"])
        expected[0]["content"] += module.AFTER_READ
        expected += [{"role": "assistant", "content": requests["response"]["content"]},
            {"role": "user", "content": json.dumps({"actual_current_source_read_result": receipt}, ensure_ascii=False, separators=(",", ":"))}]
        assert second["messages"] == expected and second["schema"] == initial["final_base"]["schema"]
        for path, payload, role in ((first, initial, "source_read"), (final, second, "final")):
            raw = read(path)
            assert raw["transport_error"] is None and len(raw["calls"]) == 1
            wire, server = (raw["calls"][0][k] for k in ("request", "response"))
            response = raw["response"]
            assert wire["messages"] == payload["messages"]
            assert wire["response_format"]["json_schema"]["schema"] == payload["schema"]
            assert all(wire[k] == cfg["generation"][k] for k in ("model", "temperature", "top_p", "top_k", "max_tokens", "seed"))
            assert response["finish_reason"] == server["choices"][0]["finish_reason"] == "stop"
            assert response["content"] == server["choices"][0]["message"]["content"]
            assert response["raw_id"] == server["id"] and response["raw_id"] not in raw_ids
            assert server["choices"][0]["message"]["reasoning_content"]
            raw_ids.add(response["raw_id"])
            validate(json.loads(response["content"]), payload["schema"])
            cost = usage.setdefault(arm, {}).setdefault(role, {"prompt_tokens": 0, "completion_tokens": 0})
            for k in cost:
                assert response[k] == server["usage"][k]
                cost[k] += response[k]
            bindings[str(path)] = sha(path)
            wire_checks.append({"path": str(path), "raw_id": response["raw_id"], "native_schema_source_and_usage_checked": True})
        values = json.loads(read(final)["response"]["content"])
        body = json.loads(initial["messages"][1]["content"])
        flow = flows.setdefault(stage, {}).setdefault(arm, {k: 0 for k in (
            "Gold_reread_and_cited", "Gold_reread_but_omitted", "Gold_not_reread_but_cited", "Gold_not_reread_not_cited", "Gold_NN_final_NM_with_Gold_reread")})
        for h, g in original["annotation_sets"][0]["annotations"].items():
            v = values[h]
            gold, selected, reread = set(g["spans"]), set(v["spans"]), set(action[h]["original_span_indices"])
            nn = g["choice"] != "NotMentioned"
            row = {"stage": stage, "arm": arm, "document_id": doc, "hypothesis_id": h,
                "original_hypothesis": body["hypotheses"][h]["original_hypothesis"],
                "Gold_choice": g["choice"], "Gold_spans": g["spans"], **v,
                "reread_indices": action[h]["original_span_indices"], "reading_focus": action[h]["inspection_focus"],
                "ordinary_candidate_indices": [v["original_span_index"] for v in body["hypotheses"][h]["fallible_evidence_candidates"]],
                "label_correct": v["choice"] == g["choice"],
                "joint_exact": v["choice"] == g["choice"] and gold == selected,
                "tp": len(gold & selected) if nn else 0, "fp": len(selected - gold) if nn else 0,
                "fn": len(gold - selected) if nn else 0}
            rows.append(row)
            if nn:
                for k, count in (("Gold_reread_and_cited", len(gold & reread & selected)),
                    ("Gold_reread_but_omitted", len((gold & reread) - selected)),
                    ("Gold_not_reread_but_cited", len((gold - reread) & selected)),
                    ("Gold_not_reread_not_cited", len(gold - reread - selected)),
                    ("Gold_NN_final_NM_with_Gold_reread", int(v["choice"] == "NotMentioned" and bool(gold & reread)))):
                    flow[k] += count
        for path in (actual_path, rpath):
            bindings[str(path)] = sha(path)
    assert len(raw_ids) == len(wire_checks) == 32 and len(rows) == 272
    phase = {stage: {arm: summary([r for r in rows if r["stage"] == stage and r["arm"] == arm]) for arm in ("empty_read", "skill_read")} for stage in ("B6", "B7")}
    for stage, arms in phase.items():
        published = read(OUT / f"stage_results/{stage}.json")["metrics"]
        for arm, value in arms.items():
            assert all(abs(value[k] - published[arm][k]) < 1e-12 for k in value if k not in ("NN_joint", "NM_joint"))
    reference_path = OUT / "monitoring/fixed_prefix_historical_direct_strong_controls_before_new_stage_scoring.json"
    for path in (Path(__file__).resolve(), OUT / "completion.json", OUT / "registration.json", reference_path):
        bindings[str(path)] = sha(path)
    report = {"at": now(), "run_id": OUT.name, "all32_actual_calls16_finals_original_author_sets_source_actions_and_wires_checked": True,
        "phase_metrics": phase, "combined_metrics": {arm: summary([r for r in rows if r["arm"] == arm]) for arm in ("empty_read", "skill_read")},
        "paired_changes": {stage: paired([r for r in rows if r["stage"] == stage]) for stage in ("B6", "B7")},
        "combined_paired_changes": paired(rows), "reread_to_citation_flow": flows,
        "full_source_always_visible_not_reread_is_not_unseen_or_causal_attention": True,
        "nonGold_context_reads_not_scored_as_false_positive_reads": True,
        "all_query_records": rows, "actual_usage_by_arm_role": usage, "wire_checks": wire_checks,
        "historical_stronger_one_call_reference": read(reference_path), "bindings": bindings,
        "not_new_learning_or_independent_repeat_or_mature_method_win_or_TEST": True}
    dest = OUT / "monitoring/complete32_original_sets_actual_read_and_citation_class_diagnosis.json"
    RunStore.immutable_json(dest, report)
    print(json.dumps({k: report[k] for k in ("phase_metrics", "combined_metrics", "combined_paired_changes", "reread_to_citation_flow")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
