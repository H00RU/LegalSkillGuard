"""Independent full-wire/manual-set audit, only after a complete study is terminal.

Run-local reproducibility artifact, not learner code or an admission mechanism.
The same source can audit the prospective literal-view learner with explicit
--config/--run-dir; it never generates answers or edits frozen inputs.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import zipfile
from pathlib import Path

from analyse_completed_batches import ROOT, aggregate, contrast, original_markers

sys.path.insert(0, str(ROOT))

from jsonschema import validate

from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.learning.audit import close, original_score
from legal_skill_guard.learning.experiment import now, read, sha
from legal_skill_guard.learning.task_local import ARMS, PREFIX_ARMS, task_local_messages, task_skill_projection
from legal_skill_guard.utils.hashing import canonical_json_sha256 as canonical_sha


def metrics(records):
    result = aggregate(records)
    nn = [q for q in records if q["Gold_choice"] != "NotMentioned"]
    result["evidence_query_mean_f1_gold_non_neutral"] = sum(
        2 * q["tp"] / (2 * q["tp"] + q["fp"] + q["fn"]) for q in nn
    ) / len(nn)
    return result


def audit(config_path, out):
    cfg, done = read(config_path), read(out / "completion.json")
    assert read(out / "progress.json")["state"] == "completed"
    launch = read(out / "launch.json")
    proc = Path("/proc") / str(launch["pid"])
    assert not proc.exists(), "Do not change source or call a run terminal from a stale status alone"
    assert done["run_id"] == cfg["run_id"] == out.name
    assert (done["distinct_native_responses"], done["logical_observations"]) == (148, 166)
    frozen = read(config_path.with_suffix(".frozen.json"))
    assert frozen["config_sha256"] == sha(config_path)
    assert all(sha(p) == digest for p, digest in frozen["files"].items())
    assert read(out / "audits/complete166_before_later_grading.json")["logical_observations"] == 166
    endpoints = list(out.glob("later/*/*.public.json"))
    assert len(endpoints) == 40 and len(list(out.glob("later_scored/*/*.json"))) == 40

    # Gold is opened only after the complete40/148/166 and terminal guards above.
    assert sha(ROOT / cfg["source_archive"]) == cfg["source_archive_sha256"]
    with zipfile.ZipFile(ROOT / cfg["source_archive"]) as archive:
        author = json.loads(archive.read("contract-nli/train.json"))
    source = {r["id"]: r for r in author["documents"]}
    packet = read(ROOT / cfg["input_packet"])
    labels = packet["public_hypotheses"]
    assert author["labels"] == labels
    for row in packet["training"]:
        assert {k: v for k, v in row.items() if k != "batch"} == source[row["id"]]
    for row in packet["later_inputs_no_annotation_sets"]:
        assert row == {k: v for k, v in source[row["id"]].items() if k != "annotation_sets"}
    expected_slots = {
        (f"batch{r['batch']}_before", arm, r["id"]) for r in packet["training"] for arm in PREFIX_ARMS
    } | {
        (f"batch{r['batch']}_after", "skill_memory", r["id"]) for r in packet["training"]
    } | {
        ("retention_b4", "skill_memory", r["id"]) for r in packet["training"] if r["batch"] == 1
    } | {("later", arm, d) for arm in ARMS for d in cfg["expected_later_ids"]}
    paths = sum((list(out.glob(pattern)) for pattern in (
        "batch*_*/*/*.public.json", "batch*_*/*/*.reference.json",
        "retention_b4/*/*.public.json", "later/*/*.public.json",
    )), [])
    assert len(paths) == len(expected_slots) == 166
    paths.sort(key=lambda p: (p.parent.parent.name, int(p.name.split(".")[0]), p.parent.name != "strong_empty", p.parent.name))
    audited = {str(config_path): sha(config_path), str(config_path.with_suffix(".frozen.json")): sha(config_path.with_suffix(".frozen.json"))}
    groups, slots, physical, endpoint_queries = {}, set(), {}, {arm: [] for arm in ARMS}
    main_ids = set()
    for path in paths:
        unit = read(path)
        d, arm, stage = unit["document_id"], unit["arm"], unit["stage"]
        slot = (stage, arm, d)
        assert slot in expected_slots and slot not in slots
        slots.add(slot)
        row = source[d]
        version = 4 if stage in ("later", "retention_b4") else int(stage[5]) - stage.endswith("before")
        bank = read(out / f"update_transactions/b{version}.json")["publication"] if arm == "skill_memory" and version else read(out / "static_procedures.json")["library"] if arm == "static_procedures" else []
        state = None if arm == "strong_empty" or not version else read(ROOT / cfg["reference_training_run"] / f"evidence_models/ordinary_M{version}.manifest.json")["state_sha256"]
        assert unit["published_library"] == bank and unit["published_library_sha256"] == canonical_sha(bank)
        trace = unit["actual_factual_trace"]
        assert trace["ordinary_model_state"] == state
        raw_path = Path(unit["raw_artifact"])
        raw = read(raw_path)
        assert len(raw["calls"]) == 1 and raw["response"] == unit["response"]
        req = raw["calls"][0]["request"]
        for key in ("model", "temperature", "top_p", "top_k", "max_tokens", "seed"):
            assert req[key] == cfg["generation"][key]
        messages, schema, _ = task_local_messages(row, labels, cfg["bundled_solver_system"], bank, trace["proposals"], unconditional_layout=arm == "unconditional_layout")
        assert req["messages"] == messages
        assert req["response_format"] == {"type": "json_schema", "json_schema": {"name": "contractnli_callable_final", "strict": True, "schema": schema}}
        payload = json.loads(req["messages"][1]["content"])
        assert set(payload) == {"full_contract_with_original_span_markers", "hypotheses", "output_contract", "ordinary_source_evidence_tool"}
        assert payload["full_contract_with_original_span_markers"] == original_markers(row)
        assert list(payload["hypotheses"]) == list(labels)
        projection = task_skill_projection(bank, labels)
        independent = original_score(unit["response"], row, row["annotation_sets"][0]["annotations"], list(labels))
        if independent["public_valid"]:
            validate(independent["parsed"], req["response_format"]["json_schema"]["schema"])
        if stage != "later":
            close(independent, unit)
        else:
            scored_path = out / f"later_scored/{arm}/{d}.json"
            scored = read(scored_path)
            assert scored["response"] == unit["response"] and scored["raw_artifact"] == unit["raw_artifact"]
            close(independent, scored)
            audited[str(scored_path)] = sha(scored_path)
        records = []
        for h, label in labels.items():
            question = payload["hypotheses"][h]
            assert question["original_hypothesis"] == label["hypothesis"]
            assert question["original_public_short_description"] == label["short_description"]
            assert question["applicable_published_skills"] == projection[h]
            candidates = None if trace["proposals"] is None else trace["proposals"]["by_hypothesis"][h]["candidates"]
            assert question["fallible_evidence_candidates"] == candidates
            for c in candidates or []:
                i = c["original_span_index"]
                assert type(i) is int and 0 <= i < len(row["spans"])
                if cfg.get("candidate_source_view") == "literal_original_span_v1":
                    start, end = row["spans"][i]
                    assert c["literal_original_text"] == row["text"][start:end]
                else:
                    assert "literal_original_text" not in c
            q = next(x for x in independent["queries"] if x["hypothesis_id"] == h)
            g, prediction = q["gold"], q["prediction"]
            gs, ps = set(g["spans"]), set() if prediction is None else set(prediction["spans"])
            nn = g["choice"] != "NotMentioned"
            records.append({
                "d": d, "h": h, "Gold_choice": g["choice"], "Gold_spans": sorted(gs),
                "choice": None if prediction is None else prediction["choice"], "spans": sorted(ps),
                "reason": None if prediction is None else prediction["reason"],
                "label_correct": prediction is not None and prediction["choice"] == g["choice"],
                "joint_correct": prediction is not None and prediction["choice"] == g["choice"] and gs == ps,
                "tp": len(gs & ps) if nn else 0, "fp": len(ps - gs) if nn else 0, "fn": len(gs - ps) if nn else 0,
                "candidate_members": [c["original_span_index"] for c in candidates or []],
                "delivered_skill_ids": [s["id"] for s in projection[h]],
                "used_skill_ids": [] if prediction is None else prediction["used_skill_ids"],
            })
        groups.setdefault((stage, arm), []).extend(records)
        if stage == "later":
            endpoint_queries[arm].extend(records)
        rid = unit["response"]["raw_id"]
        if rid in physical:
            assert physical[rid][0] == raw_path and physical[rid][1] == raw
            assert stage == "batch1_before" and arm != "strong_empty"
        else:
            physical[rid] = (raw_path, raw)
        if arm == "skill_memory":
            main_ids.add(rid)
        audited.update({str(path): sha(path), str(raw_path): sha(raw_path)})
    assert slots == expected_slots and len(physical) == 148 and len(main_ids) == 62
    new = [r for p, r in physical.values() if p.is_relative_to(out)]
    inherited = [r for p, r in physical.values() if not p.is_relative_to(out)]
    assert (len(new), len(inherited)) == (cfg["planned_new_native_calls"], cfg.get("planned_inherited_native_calls", 0))
    for name, records in (("new_native_usage", new), ("inherited_native_usage_not_new_spend", inherited)):
        assert {k: sum(r["response"][k] for r in records) for k in ("prompt_tokens", "completion_tokens")} == done[name]
    endpoint_metrics = {arm: metrics(qs) for arm, qs in endpoint_queries.items()}
    for arm, values in endpoint_metrics.items():
        for key, value in values.items():
            if key in done["development"][arm]:
                assert math.isclose(value, done["development"][arm][key], abs_tol=1e-12)
    teacher_records = []
    training_batch = {r["id"]: r["batch"] for r in packet["training"]}
    for name in ("static_public_task_only", *(f"task_local_b{b}" for b in range(1, 5))):
        directory = out / "teacher" / name
        wire, response, event = (read(directory / f) for f in ("wire_request.json", "response.json", "event_log.json"))
        invocation = response["invocation"]
        assert response["model"] == cfg["teacher"]["model"] and not response["cache_hit"]
        assert canonical_sha(wire) == response["request_sha256"]
        assert canonical_sha(response["value"]) == response["response_sha256"]
        assert invocation["returncode"] == 0 and invocation["attempt"] == 1 and not invocation["tool_events_detected"]
        assert canonical_sha({"event_log": event["event_log"]}) == invocation["event_log_sha256"]
        validate(response["value"], wire["output_schema"])
        body = json.loads(wire["user_prompt"])
        if name == "static_public_task_only":
            assert set(body) == {"public_hypotheses", "full_master_and_actual_scoped_projection_token_cap"}
            assert body["public_hypotheses"] == labels
            assert response["value"]["library"] == read(out / "static_procedures.json")["library"]
        else:
            batch = int(name[-1])
            expected_ids = [d for d, b in training_batch.items() if b in (batch - 1, batch)]
            assert body["supplied_original_witness_ids"] == expected_ids
            cases = body["original_cases_and_actual_same_parent_observations"]
            assert [c["document_id"] for c in cases] == expected_ids
            for case in cases:
                d = case["document_id"]
                stage = f"batch{training_batch[d]}_{'before' if training_batch[d] == batch else 'after'}"
                alternatives = [p for suffix in ("public", "reference") if (p := out / stage / "skill_memory" / f"{d}.{suffix}.json").exists()]
                assert len(alternatives) == 1
                actual = read(alternatives[0])
                assert case["full_original_contract_with_spans"] == original_markers(source[d])
                assert case["original_annotations"] == source[d]["annotation_sets"][0]["annotations"]
                assert case["actual_public_response"] == {k: actual["response"][k] for k in ("raw_id", "finish_reason", "content")}
                for h, gold in case["original_annotations"].items():
                    index = next(q for q in body["hypothesis_indexed_original_feedback"][h] if q["document_id"] == d)
                    prediction = actual["parsed"][h] if actual["public_valid"] else None
                    gs, ps = set(gold["spans"]), set() if prediction is None else set(prediction["spans"])
                    assert index["original_Gold_choice"] == gold["choice"]
                    assert index["actual_choice"] == (None if prediction is None else prediction["choice"])
                    assert index["missing_original_members"] == sorted(gs - ps) and index["extra_original_members"] == sorted(ps - gs)
                    if cfg.get("teacher_feedback_view") == "literal_evidence_comparisons_v1":
                        assert index["literal_original_evidence_comparison"] == [
                            {"original_span_index": i, "literal_original_text": source[d]["text"][source[d]["spans"][i][0]:source[d]["spans"][i][1]],
                             "original_Gold_member": i in gs, "actual_public_answer_member": i in ps}
                            for i in sorted(gs | ps)
                        ]
            assert response["value"] == read(out / f"update_transactions/b{batch}.json")["actual_teacher_value"]
        inherited_teacher = (directory / "explicit_historical_reference.json").exists()
        teacher_records.append({"name": name, "inherited_not_new_spend": inherited_teacher, "actual_invocation": invocation})
        audited.update({str(directory / f): sha(directory / f) for f in ("wire_request.json", "response.json", "event_log.json")})
    for field, inherited_flag in (("new_teacher_usage", False), ("inherited_teacher_usage_not_new_spend", True)):
        selected = [t for t in teacher_records if t["inherited_not_new_spend"] == inherited_flag]
        assert len(selected) == (cfg.get("planned_inherited_teacher_calls", 0) if inherited_flag else cfg["planned_new_teacher_calls"])
        assert {k: sum(t["actual_invocation"]["usage"][k] for t in selected) for k in ("input_tokens", "output_tokens", "reasoning_output_tokens")} == done[field]
    result = {
        "at": now(), "run_id": cfg["run_id"], "analysis_source_sha256": sha(__file__),
        "base_manual_analysis_source_sha256": sha(Path(__file__).with_name("analyse_completed_batches.py")),
        "all_original_author_sources166_native_wires_and2822_logical_query_sets_match": True,
        "distinct_native_raw_ids": len(physical), "new_native": len(new), "inherited_native": len(inherited),
        "main_path_distinct_native_ids": len(main_ids), "endpoint_sources": 8, "endpoint_native": 40,
        "all_new_and_inherited_native_usage_independently_accounted": True,
        "all5_actual_teacher_roles_full_original_feedback_values_and_usage_checked": True,
        "actual_teacher_invocations": teacher_records,
        "endpoint_metrics": endpoint_metrics,
        "matched_main_minus_controls": {arm: contrast(endpoint_queries[arm], endpoint_queries["skill_memory"]) for arm in ARMS if arm != "skill_memory"},
        "all_endpoint_query_records": endpoint_queries,
        "audited_file_sha256": {**frozen["files"], **audited, str(out / "completion.json"): sha(out / "completion.json")},
        "zero_new_model_teacher_calls_and_no_source_or_answer_changes": True,
        "exposed_TRAIN_development_not_official_TEST_independent_repeat_or_causal_skill_credit": True,
    }
    destination = out / "monitoring/complete166_original_author_endpoint_manual_sets_and_actual_cost_audit.json"
    RunStore.immutable_json(destination, result)
    print(json.dumps({"receipt": str(destination), "endpoint_metrics": endpoint_metrics, "distinct_raw_ids": len(physical)}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    audit(args.config.resolve(), args.run_dir.resolve())
