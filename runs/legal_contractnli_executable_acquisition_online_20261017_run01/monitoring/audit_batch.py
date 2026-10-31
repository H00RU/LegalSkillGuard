"""Read-only original-author/wire audit after a complete online batch phase."""

# ruff: noqa: E402 -- Run-local evidence analysis, not an inference component.
from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jsonschema import validate

from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.learning.acquisition import GUIDANCE_SCHEMA, TEACHER, execute_library
from legal_skill_guard.learning.experiment import now, read, sha
from legal_skill_guard.learning.publication import apply_differential_publication
from legal_skill_guard.task import marked_text
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha


def counts(rows):
    n = len(rows)
    tp, fp, fn = (sum(r[k] for r in rows) for k in ("tp", "fp", "fn"))
    label, joint = (sum(r[k] for r in rows) for k in ("label_correct", "joint_exact"))
    return {"hypotheses": n, "label_correct": label, "label_accuracy": label / n,
        "evidence_tp": tp, "evidence_fp": fp, "evidence_fn": fn,
        "evidence_micro_f1_gold_non_neutral": 2 * tp / (2 * tp + fp + fn),
        "joint_exact_correct": joint, "joint_exact_accuracy": joint / n,
        "NN_joint": sum(r["joint_exact"] and r["Gold_choice"] != "NotMentioned" for r in rows),
        "NM_joint": sum(r["joint_exact"] and r["Gold_choice"] == "NotMentioned" for r in rows),
        "Gold_cited_outside_both_ordinary_and_program": sum(len(set(r["Gold_spans"]) & set(r["spans"]) - set(r["ordinary"]) - set(r["program"])) for r in rows if r["Gold_choice"] != "NotMentioned"),
        "Gold_program_only_cited": sum(len(set(r["Gold_spans"]) & set(r["spans"]) & set(r["program"]) - set(r["ordinary"])) for r in rows if r["Gold_choice"] != "NotMentioned"),
        "Gold_program_available_but_omitted": sum(len(set(r["Gold_spans"]) & set(r["program"]) - set(r["spans"])) for r in rows if r["Gold_choice"] != "NotMentioned")}


def contrast(before, after):
    index = {(r["document_id"], r["hypothesis_id"]): r for r in before}
    assert set(index) == {(r["document_id"], r["hypothesis_id"]) for r in after}
    result = {k: 0 for k in ("label_fixes", "label_damage", "joint_fixes", "joint_damage", "true_members_gained", "true_members_lost")}
    for r in after:
        old = index[(r["document_id"], r["hypothesis_id"])]
        for field, prefix in (("label_correct", "label"), ("joint_exact", "joint")):
            result[prefix + "_fixes"] += int(r[field] and not old[field])
            result[prefix + "_damage"] += int(old[field] and not r[field])
        if r["Gold_choice"] != "NotMentioned":
            gold, previous, current = (set(v) for v in (r["Gold_spans"], old["spans"], r["spans"]))
            result["true_members_gained"] += len((gold & current) - previous)
            result["true_members_lost"] += len((gold & previous) - current)
    return result


def audit_units(units, author, cfg, bindings):
    sources = {r["id"]: r for r in author["documents"]}
    rows, ids, costs = [], set(), {"prompt_tokens": 0, "completion_tokens": 0}
    for u in units:
        p, raw = read(u["payload"]), read(u["raw_artifact"])
        assert raw["transport_error"] is None and len(raw["calls"]) == 1
        wire, server = (raw["calls"][0][k] for k in ("request", "response"))
        assert wire["messages"] == p["messages"]
        assert wire["response_format"]["json_schema"]["schema"] == p["schema"]
        assert all(wire[k] == cfg["generation"][k] for k in ("model", "temperature", "top_p", "top_k", "max_tokens", "seed"))
        assert u["response"] == raw["response"]
        assert raw["response"]["content"] == server["choices"][0]["message"]["content"]
        assert raw["response"]["finish_reason"] == server["choices"][0]["finish_reason"] == "stop"
        assert raw["response"]["raw_id"] == server["id"]
        assert server["model"] == cfg["generation"]["model"] and server["choices"][0]["message"]["reasoning_content"]
        validate(json.loads(raw["response"]["content"]), p["schema"])
        if server["id"] not in ids:
            for k in costs:
                assert raw["response"][k] == server["usage"][k]
                costs[k] += server["usage"][k]
            ids.add(server["id"])
        else:
            assert u["exact_same_run_cold_alias"] and u["condition"] == "skills"
        original = sources[u["document_id"]]
        source = {k: original[k] for k in ("id", "text", "spans")}
        body = json.loads(p["messages"][1]["content"])
        assert re.sub(r"<SOURCE_LEADS>.*?</SOURCE_LEADS>", "", body["full_contract_with_original_span_markers"]) == marked_text(source)
        assert set(body["hypotheses"]) == set(author["labels"])
        bank = p["bank"]
        assert p["bank_sha256"] == u["bank_sha256"] == csha(bank)
        assert body["executed_source_skill_index"] == [{"id": s["id"], "hypothesis_ids": s["hypothesis_ids"],
            "executed_query_count": len(s["guidance"]["source_queries"])} for s in bank]
        # Replay the declared frozen factual API; legal scores below are computed
        # independently by original-author member sets, not by this executor.
        executions = execute_library(source, bank)
        assert executions == p["actual_factual_trace"]["actual_source_executions"]
        tags = {}
        for sid, events in executions.items():
            for event in events:
                for role in ("matched", "neighbour", "preamble"):
                    for i in event[role]:
                        tags.setdefault(i, {}).setdefault(sid, []).append([event["query_index"], role])
        actual_tags = {int(m.group(2)): json.loads(m.group(1)) for m in re.finditer(
            r"<SOURCE_LEADS>(.*?)</SOURCE_LEADS><SPAN (\d+)>", body["full_contract_with_original_span_markers"])}
        assert actual_tags == tags
        assert p["fixed_ordinary_model_state"] == (None if u["condition"] == "strong_empty" else read(ROOT / cfg["ordinary_manifest"])["state_sha256"])
        values = json.loads(raw["response"]["content"])
        for h, g in original["annotation_sets"][0]["annotations"].items():
            question, value = body["hypotheses"][h], values[h]
            assert question["original_hypothesis"] == author["labels"][h]["hypothesis"]
            applicable = [s["id"] for s in bank if h in s["hypothesis_ids"]]
            assert question["applicable_executed_skill_ids"] == applicable
            assert {c for branch in p["schema"]["properties"][h]["anyOf"]
                for c in branch["properties"]["choice"]["enum"]} == {"Entailment", "Contradiction", "NotMentioned"}
            for branch in p["schema"]["properties"][h]["anyOf"]:
                assert branch["properties"]["spans"]["items"]["enum"] == list(range(len(source["spans"])))
            ordinary = [v["original_span_index"] for v in question["fallible_evidence_candidates"]]
            for i in ordinary:
                assert body["ordinary_candidate_original_text"][str(i)] == source["text"][slice(*source["spans"][i])]
            program = sorted({i for sid in applicable for event in executions[sid] for role in ("matched", "neighbour", "preamble") for i in event[role]})
            gold, prediction = set(g["spans"]), set(value["spans"])
            nn = g["choice"] != "NotMentioned"
            rows.append({"stage": u["stage"], "condition": u["condition"], "document_id": source["id"], "hypothesis_id": h,
                "Gold_choice": g["choice"], "Gold_spans": g["spans"], **value,
                "ordinary": ordinary, "program": program,
                "label_correct": g["choice"] == value["choice"],
                "joint_exact": g["choice"] == value["choice"] and gold == prediction,
                "tp": len(gold & prediction) if nn else 0, "fp": len(prediction - gold) if nn else 0,
                "fn": len(gold - prediction) if nn else 0})
        bindings.update({u["payload"]: sha(u["payload"]), u["raw_artifact"]: sha(u["raw_artifact"])})
    return rows, ids, costs


def audit_teacher(batch):
    cfg = read(ROOT / "configs/contractnli_executable_acquisition.json")
    frozen = read(ROOT / "configs/contractnli_executable_acquisition.frozen.json")
    assert all(sha(p) == h for p, h in frozen["files"].items())
    publication_path = OUT / f"publications/b{batch}.json"
    assert publication_path.exists(), "Wait for the whole actual teacher/publication"
    publication = read(publication_path)
    folder = OUT / f"teacher/update_b{batch}"
    wire, response = read(folder / "wire_request.json"), read(folder / "response.json")
    body_path = OUT / f"learning_inputs/update_b{batch}.json"
    body = read(body_path)
    assert wire["system_prompt"] == TEACHER
    assert json.loads(wire["user_prompt"]) == body
    assert wire["model"] == response["model"] == cfg["teacher"]["model"]
    assert wire["reasoning_effort"] == cfg["teacher"]["reasoning_effort"]
    assert csha(wire) == response["request_sha256"]
    assert not response["cache_hit"] and not response["invocation"]["tool_events_detected"]
    assert response["invocation"]["attempt"] == 1 and response["invocation"]["returncode"] == 0
    assert response["value"] == publication["delta"]
    expected = cfg["training_ids"][:8 * batch]
    assert [r["id"] for r in body["complete_cumulative_original_TRAIN_sources_and_Gold"]] == expected
    assert sha(ROOT / cfg["source_archive"]) == cfg["source_archive_sha256"]
    with zipfile.ZipFile(ROOT / cfg["source_archive"]) as archive:
        author = json.loads(archive.read("contract-nli/train.json"))
    author_rows = {r["id"]: r for r in author["documents"]}
    assert body["public_hypotheses"] == author["labels"]
    for case in body["complete_cumulative_original_TRAIN_sources_and_Gold"]:
        original = author_rows[case["id"]]
        assert all(case[k] == original[k] for k in ("id", "text", "spans"))
        assert case["original_annotations"] == original["annotation_sets"][0]["annotations"]
    own = []
    for b in range(1, batch + 1):
        own += [u for u in read(OUT / f"b{b}_before_complete.json")["units"] if u["condition"] == "skills"]
        if b < batch:
            own += read(OUT / f"b{b}_all_seen_retention.json")["units"]
    assert len(own) == len(body["actual_own_public_observations"]) == 4 * batch * (batch + 1)
    by_id = {u["response"]["raw_id"]: u for u in own}
    assert len(by_id) == len(own)
    assert body["current_parent_library"] == publication["parent"]
    parent_hash = csha(publication["parent"])
    actual_parent_native = set()
    for o in body["actual_own_public_observations"]:
        u = by_id[o["actual_native_raw_id"]]
        p = read(u["payload"])
        assert o["actual_public_answer"] == json.loads(u["response"]["content"])
        assert o["actual_bank_sha256"] == u["bank_sha256"] == csha(p["bank"])
        assert body["observed_libraries"][o["actual_bank_sha256"]] == p["bank"]
        assert o["actual_native_artifact_sha256"] == sha(u["raw_artifact"])
        assert body["actual_source_execution_catalogue"][o["actual_source_execution_ref"]] == p["actual_factual_trace"]["actual_source_executions"]
        if o["actual_bank_sha256"] == parent_hash:
            actual_parent_native.add(o["document_id"])
    assert actual_parent_native == set(expected), "Every seen source must have real same-parent native feedback"
    for d in expected:
        row = {k: author_rows[d][k] for k in ("id", "text", "spans")}
        current = execute_library(row, publication["parent"])
        ref = body["current_parent_source_replay_refs_not_new_native_responses"][str(d)]
        assert body["actual_source_execution_catalogue"][ref] == current
    replay = apply_differential_publication(publication["parent"], response["value"],
        author["labels"], expected, guidance_schema=GUIDANCE_SCHEMA)
    assert replay == publication["publication"]
    assert max(publication["capacity"].values()) <= cfg["library_token_hard_cap"]
    observed = {"CREATE": 0, "UPDATE": 0, "DELETE": 0, "MERGE": 0}
    for op in response["value"]["operations"]:
        observed[op["operation"]] += 1
    assert observed == publication["statistics"]["operation_counts"]
    bindings = frozen["files"].copy()
    for p in (publication_path, body_path, folder / "wire_request.json", folder / "response.json", folder / "event_log.json", Path(__file__).resolve()):
        bindings[str(p)] = sha(p)
    report = {"at": now(), "run_id": OUT.name, "batch": batch,
        "full_actual_teacher_wire_original_sources_Gold_own_and_exact_delta_replayed": True,
        "complete_seen_source_ids": expected, "actual_own_observations": len(own),
        "every_seen_source_has_actual_current_parent_native_feedback": sorted(actual_parent_native),
        "no_other_arm_or_future_source_answers_or_private_reasoning_passed": True,
        "actual_teacher_invocation": response["invocation"], "publication_statistics": publication["statistics"],
        "complete_published_programs": replay, "capacity": publication["capacity"], "bindings": bindings,
        "structural_replay_not_proof_of_general_legal_truth_transfer_or_teacher_rationale_causality": True}
    RunStore.immutable_json(OUT / f"monitoring/b{batch}_actual_teacher_full_cumulative_own_and_publication_audit.json", report)
    print(json.dumps({k: report[k] for k in ("batch", "complete_seen_source_ids", "actual_own_observations", "publication_statistics", "capacity")}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("batch", type=int, choices=range(1, 5))
    parser.add_argument("phase", choices=("before", "retention", "teacher"))
    args = parser.parse_args()
    b, phase = args.batch, args.phase
    if phase == "teacher":
        audit_teacher(b)
        return
    complete_path = OUT / (f"b{b}_before_complete.json" if phase == "before" else f"b{b}_all_seen_retention.json")
    assert complete_path.is_file(), "Whole phase must finish; no partial quality scoring"
    cfg = read(ROOT / "configs/contractnli_executable_acquisition.json")
    frozen = read(ROOT / "configs/contractnli_executable_acquisition.frozen.json")
    assert all(sha(p) == h for p, h in frozen["files"].items())
    assert sha(ROOT / cfg["source_archive"]) == cfg["source_archive_sha256"]
    with zipfile.ZipFile(ROOT / cfg["source_archive"]) as archive:
        author = json.loads(archive.read("contract-nli/train.json"))
    data, bindings = read(complete_path), frozen["files"].copy()
    units = data["units"]
    assert len(units) == (24 if phase == "before" else 8 * b)
    rows, ids, costs = audit_units(units, author, cfg, bindings)
    assert len(ids) == (16 if b == 1 else 24) if phase == "before" else len(ids) == 8 * b
    arms = sorted({r["condition"] for r in rows})
    metrics = {a: counts([r for r in rows if r["condition"] == a]) for a in arms}
    if phase == "before":
        for a, m in metrics.items():
            assert all(abs(m[k] - data["metrics"][a][k]) < 1e-12 for k in m if k not in (
                "NN_joint", "NM_joint", "Gold_cited_outside_both_ordinary_and_program", "Gold_program_only_cited", "Gold_program_available_but_omitted"))
        contrasts = {a: contrast([r for r in rows if r["condition"] == a], [r for r in rows if r["condition"] == "skills"]) for a in ("ordinary", "strong_empty")}
    else:
        reference_units = [u for u in read(OUT / f"b{b}_before_complete.json")["units"] if u["condition"] == "skills"]
        if b > 1:
            reference_units += read(OUT / f"b{b - 1}_all_seen_retention.json")["units"]
        parent_hash = csha(read(OUT / f"publications/b{b}.json")["parent"])
        assert all(u["bank_sha256"] == parent_hash for u in reference_units)
        previous, _, _ = audit_units(reference_units, author, cfg, bindings)
        contrasts = {"same_parent_actual_all_seen_before_update": contrast(previous, rows)}
    bindings.update({str(complete_path): sha(complete_path), str(Path(__file__).resolve()): sha(Path(__file__).resolve())})
    report = {"at": now(), "run_id": OUT.name, "batch": b, "phase": phase,
        "all_actual_wires_original_author_source_and_manual_member_sets_checked": True,
        "declared_factual_executor_replayed_not_a_second_legal_judge": True,
        "logical_answers": len(units), "actual_distinct_native_responses": len(ids),
        "metrics": metrics, "paired_contrasts": contrasts, "all_query_records": rows,
        "actual_unique_native_usage": costs, "bindings": bindings,
        "not_independent_repeats_or_official_TEST_or_proof_of_skill_causality_from_used_IDs": True}
    dest = OUT / f"monitoring/b{b}_{phase}_original_author_sets_actual_wires_and_acquisition_audit.json"
    RunStore.immutable_json(dest, report)
    print(json.dumps({k: report[k] for k in ("batch", "phase", "logical_answers", "actual_distinct_native_responses", "metrics", "paired_contrasts")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
