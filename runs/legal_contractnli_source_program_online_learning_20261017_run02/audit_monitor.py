"""Complete-stage original-member audit and a no-model background stop monitor.

Never changes memory/answers, selects a checkpoint, scores a partial stage or
restarts training. Whole-trial stopping follows the already frozen protocol.
"""

# ruff: noqa: E402 -- Independent run-local entry point.
from __future__ import annotations

import json
import math
import os
import signal
import subprocess
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from jsonschema import validate

from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.learning.experiment import now, read, sha
from legal_skill_guard.learning.source_programs import execute_program, program_projection
from legal_skill_guard.task import marked_text

CONFIG = ROOT / "configs/contractnli_source_programs_v2.json"
ARMS = ("strong_empty", "ordinary_memory", "unconditional_layout", "skill_memory")
TARGETS = ("label_accuracy", "evidence_micro_f1_gold_non_neutral", "joint_exact_accuracy")


def identity(pid):
    proc = Path("/proc") / str(pid)
    try:
        fields = (proc / "stat").read_text().rsplit(")", 1)[1].split()
        if fields[0] == "Z":
            return None
        return {"pid": pid, "start_ticks": fields[19],
                "argv": [s.decode() for s in (proc / "cmdline").read_bytes().split(b"\0") if s]}
    except FileNotFoundError:
        return None


def aggregate(queries):
    nn = [q for q in queries if q["Gold_choice"] != "NotMentioned"]
    tp, fp, fn = (sum(q[k] for q in nn) for k in ("tp", "fp", "fn"))
    return {"hypotheses": len(queries), "label_correct": sum(q["label_correct"] for q in queries),
        "label_accuracy": sum(q["label_correct"] for q in queries) / len(queries),
        "evidence_tp": tp, "evidence_fp": fp, "evidence_fn": fn,
        "evidence_micro_f1_gold_non_neutral": 2 * tp / (2 * tp + fp + fn),
        "joint_exact_correct": sum(q["joint_exact"] for q in queries),
        "joint_exact_accuracy": sum(q["joint_exact"] for q in queries) / len(queries),
        "NN_joint": sum(q["joint_exact"] for q in nn),
        "NM_joint": sum(q["joint_exact"] for q in queries if q["Gold_choice"] == "NotMentioned"),
        "false_NM": sum(q["Gold_choice"] != "NotMentioned" and q["choice"] == "NotMentioned" for q in queries)}


def audit_stage(batch, stage, cfg, packet, frozen):
    destination = OUT / f"monitoring/independent_B{batch}_{stage}.json"
    if destination.exists():
        previous = read(destination)
        assert all(sha(p) == h for p, h in previous["audited_file_sha256"].items())
        return previous
    ids = [r["id"] for r in packet["training"] if r["batch"] == batch]
    arms = ARMS if stage == "before" else ("skill_memory",)
    paths = {}
    for arm in arms:
        paths[arm] = []
        for d in ids:
            found = [OUT / f"batch{batch}_{stage}/{arm}/{d}.{s}.json" for s in ("public", "reference")]
            found = [p for p in found if p.exists()]
            if not found:
                return None  # No partial-source grading.
            assert len(found) == 1
            paths[arm].append(found[0])
    assert len(ids) == 6 and all(sha(p) == h for p, h in frozen["files"].items())
    with zipfile.ZipFile(ROOT / cfg["source_archive"]) as archive:
        author = json.loads(archive.read("contract-nli/train.json"))
    rows = {r["id"]: r for r in author["documents"] if r["id"] in ids}
    labels = author["labels"]
    assert labels == packet["public_hypotheses"]
    version = batch - (stage == "before")
    bank_path = OUT / f"update_transactions/b{version}.json"
    bank = read(bank_path)["publication"] if version else []
    files = {**frozen["files"], str(CONFIG.with_suffix(".frozen.json")): sha(CONFIG.with_suffix(".frozen.json")), str(Path(__file__)): sha(__file__)}
    if version:
        files[str(bank_path)] = sha(bank_path)
    groups, raw_ids, candidate_sets = {}, [], {}
    for arm, members in paths.items():
        queries, candidate_sets[arm] = [], {}
        for d, path in zip(ids, members, strict=True):
            row, unit = rows[d], read(path)
            expected_bank = bank if arm == "skill_memory" else []
            assert unit["document_id"] == d and unit["stage"] == f"batch{batch}_{stage}" and unit["arm"] == arm
            assert unit["published_library"] == expected_bank
            raw_path = Path(unit["raw_artifact"])
            raw = read(raw_path)
            assert len(raw["calls"]) == 1 and raw["response"] == unit["response"]
            request = raw["calls"][0]["request"]
            assert all(request[k] == cfg["generation"][k] for k in ("model", "temperature", "top_p", "top_k", "max_tokens", "seed"))
            body = json.loads(request["messages"][1]["content"])
            delivery = unit["actual_factual_trace"]["task_local_delivery"]
            assert delivery["actual_task_local_projection"] == program_projection(expected_bank, labels)
            source = body["full_contract_with_original_span_markers"]
            for tag in delivery["source_lead_tags_by_original_span"].values():
                source = source.replace(tag, "", 1)
            assert source == marked_text(row)
            if expected_bank:
                assert body["published_source_programs"] == expected_bank
                executed = {s["id"]: execute_program(row, s) for s in expected_bank}
                assert executed == delivery["source_program_execution_by_skill"]
                assert body["source_program_query_receipts"] == {
                    sid: [{k: v for k, v in event.items() if k not in ("literal_original_clauses", "actual_query_arguments", "skill_id")}
                          for event in events] for sid, events in executed.items()}
            else:
                assert "published_source_programs" not in body and delivery["source_lead_tags_by_original_span"] == {}
            valid = unit["response"]["finish_reason"] == "stop"
            answer = json.loads(unit["response"]["content"]) if valid else None
            if valid:
                validate(answer, request["response_format"]["json_schema"]["schema"])
            assert valid == unit["public_valid"]
            candidate_sets[arm][d] = {}
            for h in labels:
                question = body["hypotheses"][h]
                scoped = [s for s in expected_bank if h in s["hypothesis_ids"]]
                assert question["original_hypothesis"] == labels[h]["hypothesis"]
                assert question["applicable_published_skills"] == [{"id": s["id"]} for s in scoped]
                candidates = question["fallible_evidence_candidates"] or []
                candidate_sets[arm][d][h] = candidates
                for c in candidates:
                    start, end = row["spans"][c["original_span_index"]]
                    assert c["literal_original_text"] == row["text"][start:end]
                gold, pred = row["annotation_sets"][0]["annotations"][h], answer[h] if valid else None
                gs, ps = set(gold["spans"]), set(pred["spans"]) if pred else set()
                correct = bool(valid and pred["choice"] == gold["choice"])
                q = {"document_id": d, "hypothesis_id": h, "Gold_choice": gold["choice"], "Gold_spans": sorted(gs),
                    "choice": pred["choice"] if pred else None, "spans": sorted(ps), "label_correct": correct,
                    "joint_exact": correct and gs == ps, "tp": len(gs & ps), "fp": len(ps - gs), "fn": len(gs - ps),
                    "ordinary_candidate_indices": [c["original_span_index"] for c in candidates]}
                stored = next(q for q in unit["queries"] if q["hypothesis_id"] == h)
                assert stored["gold"] == gold and stored["prediction"] == pred
                assert stored["label_correct"] == q["label_correct"] and stored["joint_exact"] == q["joint_exact"]
                queries.append(q)
            raw_ids.append(unit["response"]["raw_id"])
            files.update({str(path): sha(path), str(raw_path): sha(raw_path)})
        groups[arm] = queries
    if stage == "before":
        assert candidate_sets["ordinary_memory"] == candidate_sets["skill_memory"] == candidate_sets["unconditional_layout"]
    assert len(set(raw_ids)) == (6 if batch == 1 or stage == "after" else 24)
    metrics = {a: aggregate(q) for a, q in groups.items()}
    summary_path = OUT / f"batch{batch}_summary.json"
    if summary_path.exists():
        summary = read(summary_path)
        for arm in arms:
            for k in TARGETS:
                assert math.isclose(metrics[arm][k], summary[stage][arm][k], abs_tol=1e-12)
    result = {"at": now(), "run_id": OUT.name, "batch": batch, "stage": stage,
        "complete_source_ids": ids, "all_complete_actual_wires_original_source_and_manual_member_sets_checked": True,
        "distinct_native_responses": len(set(raw_ids)), "metrics": metrics, "all_query_records": groups,
        "audited_file_sha256": files, "no_generation_teacher_or_endpoint_scoring": True,
        "after_fit_also_changes_supervised_tool_not_pure_skill_effect": stage == "after"}
    RunStore.immutable_json(destination, result)
    return result


def worker():
    registration = read(OUT / "monitor_registration.json")
    expected = registration["parent_identity"]
    cfg, frozen = read(CONFIG), read(CONFIG.with_suffix(".frozen.json"))
    packet = read(ROOT / cfg["input_packet"])
    assert all(sha(p) == h for p, h in registration["files"].items())
    stopped = False
    while True:
        live = identity(expected["pid"])
        if live is not None:
            assert live == expected, "Exact parent identity changed; do not signal another worker"
        audited = {}
        try:
            for batch in range(1, 5):
                for stage in ("before", "after"):
                    value = audit_stage(batch, stage, cfg, packet, frozen)
                    if value:
                        audited[f"B{batch}_{stage}"] = value["metrics"]
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            if live is None:
                raise
            RunStore.atomic_json(OUT / "monitor_status.json", {"at": now(), "state": "retrying_read_only_observation", "error": repr(exc), "parent_confirmed_live": expected})
            time.sleep(10)
            continue
        if not stopped and live is not None and all(f"B{b}_before" in audited for b in (2, 3)):
            nonpositive = all(audited[f"B{b}_before"]["skill_memory"][k] <= audited[f"B{b}_before"]["ordinary_memory"][k] for b in (2, 3) for k in TARGETS)
            if nonpositive:
                assert identity(expected["pid"]) == expected
                RunStore.immutable_json(OUT / "monitor_whole_trial_stop_request.json", {"at": now(),
                    "parent_identity": expected, "reason": "Complete matched B2 and B3 all-three target effects nonpositive under frozen whole-trial stopping protocol",
                    "complete_metrics": {k: v for k, v in audited.items() if k in ("B2_before", "B3_before")},
                    "no_bank_choice_effect_admission_restart_or_goal_pause": True})
                os.kill(expected["pid"], signal.SIGTERM)
                stopped = True
        state = "parent_exited" if live is None else "monitoring_exact_live_parent"
        RunStore.atomic_json(OUT / "monitor_status.json", {"at": now(), "state": state,
            "parent_identity": expected, "complete_stage_metrics": audited, "whole_trial_stop_requested": stopped,
            "new_model_teacher_calls": [0, 0], "no_source_edits_bank_selection_or_automatic_restart": True})
        if live is None:
            return
        time.sleep(15)


if __name__ == "__main__":
    if sys.argv[1] == "launch":
        assert not (OUT / "monitor_launch.json").exists()
        parent = identity(read(OUT / "launch.json")["pid"])
        assert parent is not None
        files = read(CONFIG.with_suffix(".frozen.json"))["files"]
        RunStore.immutable_json(OUT / "monitor_registration.json", {"at": now(), "parent_identity": parent,
            "files": {**files, str(Path(__file__)): sha(__file__), str(CONFIG.with_suffix(".frozen.json")): sha(CONFIG.with_suffix(".frozen.json"))},
            "complete_B2_B3_whole_trial_stop_rule_predeclared_in_frozen_method_protocol": True})
        argv = [str(ROOT / ".venv/bin/python"), str(Path(__file__).resolve()), "worker"]
        with (OUT / "monitor.log").open("xb") as log:
            child = subprocess.Popen(argv, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                     start_new_session=True, env={**os.environ, "PYTHONUNBUFFERED": "1"})
        value = {"at": now(), "pid": child.pid, "actual_argv": argv, "parent_identity": parent,
                 "independent_of_chat_no_new_generation_or_teacher": True}
        RunStore.immutable_json(OUT / "monitor_launch.json", value)
        print(json.dumps(value))
    elif sys.argv[1] == "worker":
        try:
            worker()
        except BaseException as exc:
            RunStore.immutable_json(OUT / "monitor_failure.json", {"at": now(), "error": repr(exc),
                "observer_failure_not_automatically_parent_failure_or_restart": True})
            raise
    else:
        raise ValueError("Explicit launch or worker required")
