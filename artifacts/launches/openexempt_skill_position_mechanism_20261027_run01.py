"""Task-conditioned TRAIN placement check, then a conditional empty-start build."""
import copy
import fcntl
import json
import sys
import traceback
from pathlib import Path

from experiments.openexempt_online import Online, acceptance, actor_payload, freeze, preserve
from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.learning.experiment import now, read, sha
from legal_skill_guard.openexempt import ROOT, metrics
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha


def cache_origin(study, path):
    raw = read(path)
    supplied = read(path.with_suffix(".input.json"))
    assert raw.get("transport_error") is None and len(raw["calls"]) == 1
    call = raw["calls"][0]
    wire, response = call["request"], call["response"]
    assert wire["messages"] == supplied["messages"]
    assert wire["response_format"]["json_schema"]["schema"] == supplied["schema"]
    assert all(wire[k] == study.cfg["generation"][k] for k in
               ("model", "temperature", "top_p", "top_k", "max_tokens", "seed"))
    assert wire.get("chat_template_kwargs", {}).get("enable_thinking", True) == (
        not study.cfg["generation"]["disable_thinking"])
    assert response["id"] == raw["response"]["raw_id"]
    assert response["usage"]["completion_tokens"] == raw["response"]["completion_tokens"]
    assert (response["choices"][0]["message"].get("content") or "").strip() == raw["response"]["content"]
    key = csha({"messages": supplied["messages"], "schema": supplied["schema"],
                "generation": study.cfg["generation"]})
    assert key not in study.request_cache
    study.request_cache[key] = {"response": copy.deepcopy(raw["response"]),
                                "raw_call_path": str(path.relative_to(ROOT))}


def run_probe(config_path):
    cfg = read(config_path)
    assert cfg["study_kind"] == "task_conditioned_skill_placement_TRAIN_mechanism"
    assert cfg["planned_teacher_responses_max"] == 0
    out = ROOT / "runs" / cfg["run_id"]
    if out.exists():
        raise FileExistsError("Never overwrite or resume a chosen probe outcome")
    study, status = None, "failed"
    try:
        # Validate the correct runs/ path before any generation, not at reporting.
        parent_path = ROOT / "runs" / cfg["mechanism_original_parent_run"] / "completion.json"
        parent = read(parent_path)
        assert parent["status"] == "completed_bounded_mechanism_study"
        original_cfg = read(ROOT / cfg["mechanism_before_case_source_config"])
        assert all(cfg[k] == original_cfg[k] for k in
                   ("generation", "input_packet", "grading_directory", "inference_environment"))
        formal_path = ROOT / cfg["on_success_formal_config"]
        formal_cfg = read(formal_path)
        assert formal_cfg["run_id"] != cfg["run_id"]
        assert not formal_cfg.get("initial_library_publication")
        assert formal_cfg["initial_library_prior_exposure_distinct_sources"] == 0
        assert not (ROOT / "runs" / formal_cfg["run_id"]).exists()
        study = Online(Path(config_path))
        assert csha(study.bank) == cfg["mechanism_bank_sha256"]
        source = ROOT / "runs" / cfg["mechanism_before_case_source_run"]
        ids = set(cfg["mechanism_source_case_ids"])
        recent = set(cfg["mechanism_current_source_case_ids"])
        historical = set(cfg["mechanism_historical_source_case_ids"])
        assert not recent & historical and recent | historical == ids
        rows = [r for r in study.rows if r["case_id"] in ids]
        assert len(rows) == len(ids) * 2
        before = []
        for row in rows:
            stem = f"{row['case_id']}_{row['family']}_candidate"
            original = read(source / "native/b8_candidate1_replay" / (stem + ".input.json"))
            record = read(source / "native/b8_candidate1_replay" / (stem + ".answer.json"))
            messages, schema, supplied = actor_payload(row, study.bank,
                grounded=True, direct_numeric=True, asset_references=True)
            expected = copy.deepcopy(original["messages"])
            if supplied and row["family"] == "EV":
                guide = expected.pop(1)
                guide["content"] = guide["content"].replace("The current legal case follows. ", "", 1)
                expected.append(guide)
            assert messages == expected and schema == original["schema"]
            assert original["bank_sha256"] == record["bank_sha256"] == csha(study.bank)
            cache_origin(study, ROOT / record["raw_call_path"])
            before.append(record)
        previous_position = ROOT / "runs" / cfg["mechanism_reuse_position_run"]
        original_new_calls = [p for p in sorted((previous_position / "native").rglob("*.json"))
                              if not p.name.endswith((".input.json", ".answer.json"))]
        assert len(original_new_calls) == 32
        assert len(read(previous_position / "paired_records.json")["after"]) == 32
        for path in original_new_calls:
            cache_origin(study, path)
        RunStore.immutable_json(out / "mechanism_started.json", {
            "at": now(), "fixed_current_source_ids": sorted(recent),
            "fixed_historical_source_ids": sorted(historical), "bank_sha256": csha(study.bank),
            "same_bank_before_after": True, "teacher_calls_planned": 0,
            "prior_origin_count_not_new_calls": len(study.request_cache),
            "original_parent_completion_path": str(parent_path.relative_to(ROOT)),
            "original_parent_completion_sha256": sha(parent_path),
            "not_formal_learning_or_TEST": True})
        after = study._dispatch.native(lambda r: study.answer(
            r, study.bank, "task_conditioned_position", "EC_before_EV_after"), rows)
        study.grade(before + after)
        by_key = {(r["case_id"], r["family"]): r for r in before}
        assert all(r["score"] == by_key[(r["case_id"], r["family"])]["score"]
                   for r in after if r["family"] == "EC")
        current_before = [r for r in before if r["case_id"] in recent]
        current_after = [r for r in after if r["case_id"] in recent]
        prior_before = [r for r in before if r["case_id"] in historical]
        prior_after = [r for r in after if r["case_id"] in historical]
        gate = acceptance(current_before, current_after, prior_before, prior_after)
        RunStore.immutable_json(out / "paired_records.json", {"before": before, "after": after})
        result = {"at": now(), "status": "completed_bounded_task_conditioned_TRAIN_probe",
            "bank_sha256": csha(study.bank), "fixed_sources": len(ids), "task_views": len(rows),
            "before_same_bank": metrics(before), "after_same_bank": metrics(after),
            "current_before": metrics(current_before), "current_after": metrics(current_after),
            "historical_before": metrics(prior_before), "historical_after": metrics(prior_after),
            "unchanged_original_admission_gate": gate,
            "EC_requests_and_scores_unchanged_not_regenerated": True,
            "actual_native_calls": len(study.native), "actual_teacher_responses": len(study.teachers),
            "exact_wire_reuses": len(study.reuse_events),
            "native_prompt_tokens": sum(r["response"]["prompt_tokens"] for r in study.native),
            "native_completion_tokens": sum(r["response"]["completion_tokens"] for r in study.native),
            "not_a_formal_main_result_TEST_or_independent_repeat": True}
        assert result["actual_native_calls"] <= cfg["planned_new_native_calls_max"]
        assert result["actual_teacher_responses"] == 0
        RunStore.immutable_json(out / "completion.json", result)
        status = result["status"]
    except BaseException as exc:
        RunStore.immutable_json(out / "failure.json", {"at": now(), "error": repr(exc),
            "traceback": traceback.format_exc(), "actual_native_calls": len(study.native) if study else 0})
        raise
    finally:
        if study is not None:
            study.progress("terminal", state=status)
        else:
            RunStore.atomic_json(out / "progress.json", {"at": now(), "state": "failed", "stage": "terminal"})
        names = [str(p.relative_to(ROOT)) for p in out.rglob("*") if p.is_file()]
        RunStore.immutable_json(out / "terminal_preservation.json", preserve(cfg["run_id"], "actual-terminal", names))
    return study, result


def follow_up(study, result):
    cfg = study.cfg
    formal_path = ROOT / cfg["on_success_formal_config"]
    formal = read(formal_path)
    chain = ROOT / "artifacts/launches" / cfg["run_id"]
    decision = RunStore.immutable_json(chain / "formal_decision.json", {
        "at": now(), "probe_run": cfg["run_id"], "formal_run": formal["run_id"],
        "formal_config_sha256": sha(formal_path),
        "will_start_if_boundary_checks_pass": result["unchanged_original_admission_gate"]["accepted"],
        "gate_uses_only_TRAIN_and_is_unchanged": True,
        "formal_initial_bank_and_request_cache_must_be_empty": True})
    if not result["unchanged_original_admission_gate"]["accepted"]:
        preserve(cfg["run_id"], "automatic-followup-not-started", [str(decision.relative_to(ROOT))])
        print(json.dumps({"stage": "formal_not_started", "reason": "TRAIN_mechanism_gate_rejected"}), flush=True)
        return
    try:
        study.check()
        assert not formal.get("initial_library_publication")
        assert formal["initial_library_prior_exposure_distinct_sources"] == 0
        assert all(formal[k] == cfg[k] for k in
                   ("generation", "input_packet", "grading_directory", "inference_environment", "phase_dispatch"))
        assert formal["mechanism_run_must_complete_before_freeze"] == cfg["run_id"]
        assert not formal_path.with_suffix(".frozen.json").exists()
        assert not (ROOT / "runs" / formal["run_id"]).exists()
        freeze(formal_path, additional_sources=[
            Path(__file__).resolve(), study.out / "completion.json",
            study.out / "paired_records.json", study.out / "terminal_preservation.json", decision])
        study.check()
        learner = Online(formal_path)
        assert not learner.bank and not learner.request_cache
        started = RunStore.immutable_json(chain / "formal_initialized.json", {
            "at": now(), "formal_run": formal["run_id"], "initial_records": 0,
            "initial_cached_responses": 0, "not_an_inherited_bank_or_independent_repeat": True})
        preserve(cfg["run_id"], "automatic-followup-started",
                 [str(decision.relative_to(ROOT)), str(started.relative_to(ROOT))])
        print(json.dumps({"stage": "formal_started_empty", "run_id": formal["run_id"]}), flush=True)
        learner.run()
    except BaseException as exc:
        failure = RunStore.immutable_json(chain / "formal_handoff_failure.json", {
            "at": now(), "error": repr(exc), "traceback": traceback.format_exc(),
            "probe_success_not_reclassified": True})
        preserve(cfg["run_id"], "automatic-followup-failure",
                 [str(decision.relative_to(ROOT)), str(failure.relative_to(ROOT))])
        target = ROOT / "runs" / formal["run_id"]
        if target.exists() and not (target / "terminal_preservation.json").exists():
            names = [str(p.relative_to(ROOT)) for p in target.rglob("*") if p.is_file()]
            RunStore.immutable_json(target / "handoff_failure_preservation.json",
                preserve(formal["run_id"], "handoff-failed-partial", names))
        raise


if __name__ == "__main__":
    with (ROOT / "artifacts/openexempt_training.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        study, result = run_probe(sys.argv[1])
        follow_up(study, result)
