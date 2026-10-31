"""Test the actual feedback repair on a preserved chronological TRAIN prefix."""
import copy
import fcntl
import json
import os
import sys
import traceback
from pathlib import Path
from types import SimpleNamespace

from artifacts.launches.openexempt_skill_position_mechanism_20261027_run01 import cache_origin, follow_up
from experiments.openexempt_online import (
    Online, acceptance, accepted_commit_regressions, actor_payload,
    candidate_feedback, freeze, paired_effect, preserve,
)
from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.learning.experiment import now, read, sha
from legal_skill_guard.openexempt import ROOT, evaluate, metrics
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha


def run_probe(config_path):
    cfg = read(config_path)
    assert cfg["study_kind"] == "actual_revision_outcome_teacher_on_original_B7_prefix_not_formal_learning"
    assert cfg["skill_delivery_contract"] == "passive_user_background_v1"
    assert cfg["new_teacher_responses_max"] == cfg["max_candidate_attempts"] == 2
    out = ROOT / "runs" / cfg["run_id"]
    chain = ROOT / "artifacts/launches" / cfg["run_id"]
    assert not out.exists() and not config_path.with_suffix(".frozen.json").exists()
    study, status = None, "failed"
    try:
        source = ROOT / "runs" / cfg["source_main_run"]
        original_config = ROOT / cfg["source_main_config"]
        assert sha(original_config) == cfg["source_main_config_sha256"]
        assert sha(original_config.with_suffix(".frozen.json")) == cfg["source_main_manifest_sha256"]
        assert sha(source / "completion.json") == cfg["source_completion_sha256"]
        original_cfg = read(original_config)
        assert all(cfg[k] == original_cfg[k] for k in (
            "generation", "teacher", "phase_dispatch", "input_packet", "grading_directory", "inference_environment"))
        complete = read(source / "completion.json")
        assert complete["status"] == "completed_bounded_mechanism_study" and len(complete["batch_summary"]) == 8
        assert all(sha(p["path"]) == p["sha256"] for p in read(source / "terminal_preservation.json")["paths"])
        rows = read(ROOT / cfg["input_packet"])["rows"]
        by_key = {(r["case_id"], r["family"]): r for r in rows}
        history, empties, frozen_initial = {}, [], []
        extra = {Path(__file__).resolve(), original_config, original_config.with_suffix(".frozen.json"),
                 source / "completion.json", source / "terminal_preservation.json",
                 ROOT / "artifacts/launches/openexempt_skill_position_mechanism_20261027_run01.py"}
        for batch in range(1, 8):
            path = source / f"batches/b{batch}_prequential_records.json"
            forecasts = read(path)
            empties.extend(forecasts["empty"])
            frozen_initial.extend(forecasts["frozen_initial"])
            extra.add(path)
            if batch == 7:
                current_first = copy.deepcopy(forecasts["skills"])
                break
            history.update({(r["case_id"], r["family"]): r for r in forecasts["skills"]})
            path = source / f"publications/b{batch}.json"
            publication = read(path)
            extra.add(path)
            for decision in publication["training_decisions"]:
                if decision.get("accepted"):
                    if batch == 6:
                        decision["accepted_commit_regressions"] = accepted_commit_regressions(
                            list(history.values()), decision["actual_replay"])
                    history = {(r["case_id"], r["family"]): r for r in decision["actual_replay"]}
            if batch == 6:
                warm_publication = publication
        bank = warm_publication["bank"]
        assert csha(bank) == cfg["fixed_parent_bank_sha256"]
        assert read(ROOT / cfg["initial_library_publication"])["bank"] == bank
        assert len(history) == 192 and len(current_first) == 32
        before = {**history, **{(r["case_id"], r["family"]): r for r in current_first}}
        assert len(before) == 224 and max(k[0] for k in before) == cfg["seen_source_id_end"] == 292
        current_rows = [r for r in rows if 277 <= r["case_id"] <= 292]
        seen = [r for r in rows if r["case_id"] <= 292]
        retained = [d["accepted_commit_regressions"] for d in warm_publication["training_decisions"] if d.get("accepted")]
        assert len(retained) == 1 and retained[0]["regressed_tasks_total"] == 19
        feedback = [candidate_feedback(d, before, {"batch": 6}) for d in warm_publication["training_decisions"]]
        feedback = [d for d in feedback if d is not None]
        assert len(feedback) == 1 and len(feedback[0]["feedback_witness_replay"]) == 8
        imported = SimpleNamespace(cfg=cfg, request_cache={})
        for record in before.values():
            row = by_key[record["case_id"], record["family"]]
            assert record["bank_sha256"] == csha(bank)
            path = ROOT / record["raw_call_path"]
            cache_origin(imported, path)
            inp = read(path.with_suffix(".input.json"))
            messages, schema, supplied = actor_payload(row, bank, direct_numeric=True, asset_references=True)
            assert inp["messages"] == messages and inp["schema"] == schema
            assert record["delivered_skill_ids"] == [s["id"] for s in supplied]
            target = read(ROOT / cfg["grading_directory"] / f"{row['case_id']}.json")["targets"][row["family"]]
            answer = record["parsed"]["answer"] if record["parse_error"] is None else None
            assert evaluate(row, answer, target) == record["score"]
            extra.update((path, path.with_suffix(".input.json")))
        for retained_set in retained:
            for record in retained_set["before"] + retained_set["after"]:
                path = ROOT / record["raw_call_path"]
                extra.update((path, path.with_suffix(".input.json")))
        assert len(imported.request_cache) == 224
        # Bind the later forecast file without exposing it to the new teacher.
        extra.add(source / "batches/b8_prequential_records.json")
        formal_path = ROOT / cfg["on_success_formal_config"]
        formal = read(formal_path)
        assert formal["mechanism_run_must_complete_before_freeze"] == cfg["run_id"]
        assert formal["skill_delivery_contract"] == cfg["skill_delivery_contract"]
        assert not formal.get("initial_library_publication") and formal["initial_library_prior_exposure_distinct_sources"] == 0
        extra.update((formal_path, ROOT / formal["protocol"]))
        plan = RunStore.immutable_json(chain / "chronological_prefix_plan.json", {
            "at": now(), "parent96_source_bank_sha256": csha(bank), "prefix_tasks": 224,
            "current_source_ids": list(range(277, 293)), "teacher_max_source_id": 292,
            "actual_B6_regressions": 19, "bounded_actual_pre_post_witnesses": 8,
            "imported_native_origins": 224, "no_new_baseline_or_teacher_yet": True,
            "later16_not_teacher_evidence": True, "max_new_native": 480, "max_teacher_responses": 2})
        extra.add(plan)
        freeze(config_path, additional_sources=extra)
        study = Online(config_path)
        study.current_batch, study.latest = 7, copy.deepcopy(history)
        study.request_cache = imported.request_cache
        study.prequential_empty, study.prequential_frozen = empties, frozen_initial
        RunStore.immutable_json(out / "publications/b6.json", warm_publication)
        RunStore.immutable_json(out / "diagnostic_started.json", {
            "at": now(), "actual_pid": os.getpid(), "prior_cases": 96, "current_cases": 16,
            "native_initial_cache": 224, "no_future_teacher_input": True,
            "original_publication_and_scores_unchanged": True, "not_a_formal_build": True})
        publication = study.update(current_rows, seen, current_first)
        after = list(study.latest.values())
        assert len(after) == 224 and len(study.teachers) <= 2 and study.teacher_attempts <= 4
        prefix_gate = acceptance(current_first, [r for r in after if r["case_id"] >= 277],
                                 list(history.values()), [r for r in after if r["case_id"] < 277])
        changed = csha(study.bank) != csha(bank)
        prefix_gain = metrics(after)["mean_family_f1"] - metrics(list(before.values()))["mean_family_f1"]
        # Only now read/use later predictions; the teacher update is already fixed.
        future_before = copy.deepcopy(read(source / "batches/b8_prequential_records.json")["skills"])
        expected = {(r["case_id"], r["family"]): r.pop("score") for r in future_before}
        future_rows = [r for r in rows if r["case_id"] >= 293]
        assert len(future_before) == len(future_rows) == 32
        for record in future_before:
            assert record["bank_sha256"] == csha(bank)
            cache_origin(study, ROOT / record["raw_call_path"])
        future_after = study._dispatch.native(lambda r: study.answer(
            r, study.bank, "future_TRAIN16_after_fixed_update", "skills"), future_rows)
        RunStore.immutable_json(out / "all_future_responses_before_any_new_grading.json", {
            "before": future_before, "after": future_after, "bank_sha256": csha(study.bank)})
        study.grade(future_before + future_after)
        assert all(r["score"] == expected[r["case_id"], r["family"]] for r in future_before)
        future_gate = acceptance(future_before, future_after, [], [])
        future_gain = metrics(future_after)["mean_family_f1"] - metrics(future_before)["mean_family_f1"]
        accepted = changed and prefix_gate["accepted"] and prefix_gain > 1e-12 and future_gate["accepted"] and future_gain > 1e-12
        RunStore.immutable_json(out / "paired_records.json", {
            "prefix_before": list(before.values()), "prefix_after": after,
            "future_before": future_before, "future_after": future_after})
        result = {"at": now(), "status": "completed_actual_revision_outcome_teacher_prefix_probe",
            "initial_bank_sha256": csha(bank), "actual_final_bank_sha256": csha(study.bank),
            "actual_final_bank": study.bank, "bank_changed": changed,
            "prefix_before": metrics(list(before.values())), "prefix_after": metrics(after),
            "prefix_original_quality_gate": prefix_gate, "prefix_native_gain": prefix_gain,
            "future_before": metrics(future_before), "future_after": metrics(future_after),
            "future_original_quality_gate": future_gate, "future_native_gain": future_gain,
            "future_paired_effect": paired_effect(future_before, future_after),
            "formal_adoption_accepted": accepted, "actual_native_calls": len(study.native),
            "actual_teacher_responses": len(study.teachers), "actual_teacher_attempts": study.teacher_attempts,
            "native_prompt_tokens": sum(v["response"]["prompt_tokens"] for v in study.native),
            "native_completion_tokens": sum(v["response"]["completion_tokens"] for v in study.native),
            "original_prefix_native_cache": 224, "new_baseline_generations": 0,
            "not_an_independent_repeat_TEST_or_formal_learning_curve": True}
        assert result["actual_native_calls"] <= 480
        RunStore.immutable_json(out / "completion.json", result)
        status = result["status"]
    except BaseException as exc:
        RunStore.immutable_json(out / "failure.json", {"at": now(), "error": repr(exc),
            "traceback": traceback.format_exc(), "actual_native_calls": len(study.native) if study else 0,
            "actual_teacher_responses": len(study.teachers) if study else 0,
            "no_retry_answer_selection_or_original_overwrite": True})
        raise
    finally:
        if study is not None:
            study.progress("terminal", state=status)
        names = [str(p.relative_to(ROOT)) for p in out.rglob("*") if p.is_file()]
        RunStore.immutable_json(out / "terminal_preservation.json", preserve(cfg["run_id"], "actual-terminal", names))
    return study, result


if __name__ == "__main__":
    os.chdir(ROOT)
    with (ROOT / "artifacts/openexempt_training.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        study, result = run_probe(Path(sys.argv[1]).resolve())
        print(json.dumps({"stage": "actual_outcome_feedback_probe_completed",
                          "accepted": result["formal_adoption_accepted"],
                          "prefix_gain": result["prefix_native_gain"], "future_gain": result["future_native_gain"]}), flush=True)
        follow_up(study, result)
