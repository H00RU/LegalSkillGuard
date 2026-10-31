"""One fixed-content TRAIN delivery contrast; conditional empty-start formal build."""
import copy
import fcntl
import json
import os
import sys
import traceback
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace

from artifacts.launches.openexempt_skill_position_mechanism_20261027_run01 import cache_origin, follow_up
from experiments.openexempt_online import Online, acceptance, actor_payload, freeze, paired_effect, preserve
from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.learning.experiment import now, read, sha
from legal_skill_guard.learning.legal_namespace import allowable_namespaces
from legal_skill_guard.openexempt import ROOT, metrics
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha


def run_probe(config_path):
    cfg = read(config_path)
    assert cfg["study_kind"] == "fixed_content_source_bound_delivery_TRAIN_mechanism_not_formal_training"
    assert "teacher" not in cfg and cfg["new_teacher_calls_max"] == cfg["new_baseline_calls_max"] == 0
    assert cfg["skill_delivery_contract"] == "source_bound_system_procedures_v1"
    assert cfg["new_native_calls_max"] == 40 and cfg["adoption_minimum_balanced_native_f1_gain"] == .02
    out = ROOT / "runs" / cfg["run_id"]
    chain = ROOT / "artifacts/launches" / cfg["run_id"]
    assert not out.exists() and not config_path.with_suffix(".frozen.json").exists()
    study, status = None, "failed"
    try:
        source = ROOT / "runs" / cfg["source_main_run"]
        main_config = ROOT / cfg["source_main_config"]
        assert sha(main_config) == cfg["source_main_config_sha256"]
        assert sha(main_config.with_suffix(".frozen.json")) == cfg["source_main_manifest_sha256"]
        assert sha(source / "completion.json") == cfg["source_completion_sha256"]
        complete = read(source / "completion.json")
        assert complete["status"] == "completed_bounded_mechanism_study" and len(complete["batch_summary"]) == 8
        assert not (source / "failure.json").exists()
        for item in read(source / "terminal_preservation.json")["paths"]:
            assert sha(item["path"]) == item["sha256"]
        old_cfg = read(main_config)
        assert all(cfg[k] == old_cfg[k] for k in (
            "generation", "phase_dispatch", "input_packet", "grading_directory", "inference_environment"))
        candidate_path = ROOT / cfg["source_candidate_path"]
        assert sha(candidate_path) == cfg["source_candidate_sha256"]
        candidate = read(candidate_path)
        assert not candidate["accepted"]
        bank = candidate["proposed_bank"]
        assert csha(bank) == cfg["fixed_bank_sha256"] == read(ROOT / cfg["initial_library_publication"])["bank_sha256"]
        assert bank == read(ROOT / cfg["initial_library_publication"])["bank"]
        all_rows = read(ROOT / cfg["input_packet"])["rows"]
        groups = defaultdict(list)
        for row in all_rows:
            if row["family"] == "EC":
                groups["+".join(sorted(allowable_namespaces(row)))].append(row["case_id"])
        selected = {}
        for key, values in sorted(groups.items()):
            values = sorted(values)
            n = len(values)
            selected[key] = [values[i] for i in (0, (n - 1) // 3, 2 * (n - 1) // 3, n - 1)]
        assert selected == cfg["selected_public_source_groups"] and len(selected) == 5
        ids = {i for values in selected.values() for i in values}
        rows = [r for r in all_rows if r["case_id"] in ids]
        assert len(ids) == 20 and len(rows) == 40
        old_records = {(r["case_id"], r["family"]): r for r in candidate["actual_replay"]}
        assert len(old_records) == 256
        before, expected_scores, wire_plan = [], {}, []
        verified = SimpleNamespace(cfg=cfg, request_cache={})
        extra = {Path(__file__).resolve(), candidate_path, source / "completion.json",
                 source / "terminal_preservation.json", main_config, main_config.with_suffix(".frozen.json"),
                 ROOT / "artifacts/launches/openexempt_skill_position_mechanism_20261027_run01.py",
                 ROOT / cfg["on_success_formal_config"]}
        formal = read(ROOT / cfg["on_success_formal_config"])
        assert formal["mechanism_run_must_complete_before_freeze"] == cfg["run_id"]
        assert not formal.get("initial_library_publication") and formal["initial_library_prior_exposure_distinct_sources"] == 0
        assert formal["skill_delivery_contract"] == cfg["skill_delivery_contract"]
        extra.add(ROOT / formal["protocol"])
        for row in rows:
            key = row["case_id"], row["family"]
            record = copy.deepcopy(old_records[key])
            expected_scores[key] = record.pop("score")
            logical = source / "native/b8_candidate1_replay" / f"{row['case_id']}_{row['family']}_candidate.input.json"
            previous = read(logical)
            old_messages, schema, supplied = actor_payload(row, bank, direct_numeric=True, asset_references=True,
                skill_delivery_contract="passive_user_background_v1")
            messages, new_schema, new_supplied = actor_payload(row, bank, direct_numeric=True, asset_references=True,
                skill_delivery_contract=cfg["skill_delivery_contract"])
            assert previous["messages"] == old_messages and previous["schema"] == schema == new_schema
            assert previous["bank_sha256"] == record["bank_sha256"] == csha(bank)
            assert record["delivered_skill_ids"] == previous["delivered_skill_ids"] == [s["id"] for s in supplied]
            assert supplied == new_supplied and supplied and len(messages) == 2
            assert messages[1] == old_messages[2 if row["family"] == "EC" else 1]
            assert messages[0]["content"].startswith(old_messages[0]["content"])
            for skill in supplied:
                for field in ("when", "procedure", "avoid_when"):
                    assert skill["guidance"][field] in messages[0]["content"]
            assert actor_payload(row, [], direct_numeric=True, asset_references=True) == actor_payload(
                row, [], direct_numeric=True, asset_references=True, skill_delivery_contract=cfg["skill_delivery_contract"])
            raw_path = ROOT / record["raw_call_path"]
            cache_origin(verified, raw_path)
            raw_input = read(raw_path.with_suffix(".input.json"))
            assert raw_input["messages"] == old_messages and raw_input["schema"] == schema
            extra.update((logical, raw_path, raw_path.with_suffix(".input.json")))
            wire_plan.append({"case_id": row["case_id"], "family": row["family"],
                "old_wire_sha256": csha({"messages": old_messages, "schema": schema, "generation": cfg["generation"]}),
                "new_wire_sha256": csha({"messages": messages, "schema": schema, "generation": cfg["generation"]}),
                "original_raw_path": record["raw_call_path"], "unchanged_case_schema_legal_fields": True})
            before.append(record)
        assert len(verified.request_cache) == 40
        assert all(p["old_wire_sha256"] != p["new_wire_sha256"] for p in wire_plan)
        plan = RunStore.immutable_json(chain / "fixed_public_selection_and_wire_plan.json", {
            "at": now(), "selected_public_groups": selected, "bank_sha256": csha(bank),
            "logical_tasks_per_condition": 40, "new_native_requests": 40, "new_teacher_or_baseline_requests": 0,
            "wire_plan": wire_plan, "all_new_outcomes_unobserved": True})
        extra.add(plan)
        freeze(config_path, additional_sources=extra)
        study = Online(config_path)
        study.rows = rows
        assert study.bank == bank and not study.request_cache
        RunStore.immutable_json(out / "mechanism_started.json", {
            "at": now(), "actual_pid": os.getpid(), "fixed_bank_sha256": csha(bank),
            "tasks": 40, "new_native_max": 40, "not_formal_training_or_TEST": True})
        after = study._dispatch.native(lambda r: study.answer(
            r, bank, "source_bound_system_delivery", "same_content_system_procedures"), rows)
        assert len(study.native) == 40 and not study.teachers
        RunStore.immutable_json(out / "all_responses_before_any_new_grading.json", {"before": before, "after": after})
        study.grade(before + after)
        assert all(r["score"] == expected_scores[(r["case_id"], r["family"])] for r in before)
        RunStore.immutable_json(out / "paired_records.json", {"before": before, "after": after})
        bm, am = metrics(before), metrics(after)
        original_gate = acceptance(before, after, [], [])
        gain = sum(am[f]["f1"] - bm[f]["f1"] for f in ("EC", "EV")) / 2
        accepted = original_gate["accepted"] and gain + 1e-12 >= cfg["adoption_minimum_balanced_native_f1_gain"]
        strata = {key: {name: metrics([r for r in values if r["case_id"] in set(source_ids)])
                       for name, values in (("before", before), ("after", after))}
                  for key, source_ids in selected.items()}
        result = {"at": now(), "status": "completed_fixed_content_TRAIN_delivery_probe",
            "bank_sha256": csha(bank), "fixed_sources": 20, "tasks_per_condition": 40,
            "before_same_bank": bm, "after_same_bank": am, "balanced_native_f1_gain": gain,
            "predeclared_original_quality_gate": original_gate, "required_balanced_native_gain": .02,
            "formal_adoption_accepted": accepted, "per_public_stratum": strata,
            "paired_effect": paired_effect(before, after), "actual_native_calls": len(study.native),
            "actual_teacher_responses": 0, "new_baseline_generations": 0,
            "native_prompt_tokens": sum(r["response"]["prompt_tokens"] for r in study.native),
            "native_completion_tokens": sum(r["response"]["completion_tokens"] for r in study.native),
            "historical_scores_exactly_reproduced": True, "all_answers_saved_before_new_grading": True,
            "not_a_TEST_independent_repeat_or_learning_curve": True}
        RunStore.immutable_json(out / "completion.json", result)
        status = result["status"]
    except BaseException as exc:
        RunStore.immutable_json(out / "failure.json", {"at": now(), "error": repr(exc),
            "traceback": traceback.format_exc(), "actual_native_calls": len(study.native) if study else 0,
            "no_retry_or_quality_selection": True})
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
        print(json.dumps({"stage": "loading_probe_completed", "accepted": result["formal_adoption_accepted"],
                          "balanced_native_gain": result["balanced_native_f1_gain"]}), flush=True)
        follow_up(study, result)
