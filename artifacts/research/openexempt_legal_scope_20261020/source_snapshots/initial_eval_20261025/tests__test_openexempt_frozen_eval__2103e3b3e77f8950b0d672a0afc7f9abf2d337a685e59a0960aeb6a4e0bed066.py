"""Synthetic protocol checks only; no held-out packet or model service is used."""

import copy
import json
import os
import shutil
import sys
import threading
import time
from pathlib import Path

import numpy as np
import pytest
from jsonschema import validate

import experiments.openexempt_ace_online as ace
import experiments.openexempt_frozen_eval as frozen
import experiments.openexempt_online as common
import legal_skill_guard.learning.experiment as learning
from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.learning.experiment import INITIAL_PLAYBOOK, read, sha
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha


@pytest.fixture
def plan(tmp_path, monkeypatch):
    project = frozen.ROOT
    actor_files = frozen.SHARED_ACTOR_FILES + frozen.ACE_ACTOR_FILES
    for name in actor_files:
        dest = tmp_path / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.symlink_to(project / name)
    for module in (frozen, common, ace, learning):
        monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("legal_skill_guard.learning.legal_namespace.asset_description_lexicon",
                        lambda: ("watch",))
    monkeypatch.setattr(frozen.signal, "signal", lambda *args: None)
    monkeypatch.setattr(frozen, "preserve", lambda run, stage, names: {
        "files": len(names), "CPU_fixture_only_not_real_preservation": True})
    def put(name, data):
        return RunStore.immutable_json(tmp_path / name, data)

    generation = {"base_url": "http://127.0.0.1:8000/v1",
                  "model": "Qwen/Qwen3-8B", "model_root": "/fixture/frozen8b",
                  **frozen.FINAL_DECODING}
    put("stats.json", {"fixture_only": True, "paired_unit": "source_case"})
    put("data/train/inputs.json", {"rows": [{"source_key": "TRAIN0"}, {"source_key": "TRAIN1"}]})
    train_sha = sha(tmp_path / "data/train/inputs.json")
    put("data/train/preselection.json", {"source_cases": 2, "source_keys": ["TRAIN0", "TRAIN1"],
                                         "input_packet_sha256": train_sha})
    arms = [{"name": "empty", "role": "strong_empty", "backend": "direct"}]
    for backend in ("direct", "ace"):
        config = {"run_id": "learn_" + backend, "generation": generation,
                  "execution_contract": "direct_statutory_claims", "execution_contract_version": 14,
                  "skill_commit_policy": "legal_scope", "candidate_feedback_policy": "carry_partial_and_refine",
                  "library_token_hard_cap": 4096, "max_candidate_attempts": 2,
                  "source_cases": 2, "batch_source_cases": 1, "planned_batches": 2,
                  "input_packet": "data/train/inputs.json"}
        config_name = f"configs/{backend}.json"
        if backend == "ace":
            config.update(learner="ace_native_online_v4",
                initial_library_kind="native_empty_section_headers_without_legal_prior",
                ace_failed_output_feedback_policy="verbatim_public_output_no_answer_recovery")
        config_path = put(config_name, config)
        bindings = {name: sha(tmp_path / name) for name in actor_files}
        bindings.update({"data/train/inputs.json": train_sha,
                         "data/train/preselection.json": sha(tmp_path / "data/train/preselection.json")})
        put(f"configs/{backend}.frozen.json", {"config_sha256": sha(config_path), "files": bindings})
        bank = [] if backend == "direct" else INITIAL_PLAYBOOK
        field = "bank" if backend == "direct" else "playbook"
        put(f"runs/learn_{backend}/initialization.json", {field: bank, "initial_case_exposure": 0})
        put(f"runs/learn_{backend}/terminal_preservation.json", {"synthetic_only": True})
        for batch in (1, 2):
            put(f"runs/learn_{backend}/publications/b{batch}.json", {field: bank})
        status = ("completed_bounded_mechanism_study" if backend == "direct" else
                  "completed_declared_ACE_adaptation_stream")
        put(f"runs/learn_{backend}/completion.json", {"status": status,
            "batch_summary": [{"batch": 1}, {"batch": 2}],
            "prequential_skills": {"EC": {"tasks": 2}, "EV": {"tasks": 2}},
            "prequential": {"ace": {"EC": {"tasks": 2}, "EV": {"tasks": 2}}},
            "bank" if backend == "direct" else "final_playbook": bank})
        for role, name in (("evolved", "ours"), ("B1_frozen", "B1")) if backend == "direct" else (
                ("experience", "ACE"),):
            arms.append({"name": name, "role": role, "backend": backend,
                         "source_config": config_name, "source_config_sha256": sha(config_path),
                         "bank_sha256": csha(bank)})
    for seed in (145, 245):
        for backend in ("direct", "ace"):
            config = copy.deepcopy(read(tmp_path / f"configs/{backend}.json"))
            config["run_id"] += str(seed)
            config["generation"]["seed"] = seed
            config_name = f"configs/{backend}{seed}.json"
            config_path = put(config_name, config)
            bindings = copy.deepcopy(read(tmp_path / f"configs/{backend}.frozen.json"))
            bindings["config_sha256"] = sha(config_path)
            put(f"configs/{backend}{seed}.frozen.json", bindings)
            for batch in (1, 2):
                put(f"runs/{config['run_id']}/publications/b{batch}.json", read(
                    tmp_path / f"runs/learn_{backend}/publications/b{batch}.json"))
            put(f"runs/{config['run_id']}/completion.json", read(
                tmp_path / f"runs/learn_{backend}/completion.json"))
            put(f"runs/{config['run_id']}/initialization.json", read(
                tmp_path / f"runs/learn_{backend}/initialization.json"))
            put(f"runs/{config['run_id']}/terminal_preservation.json", {"synthetic_only": True})
            bank = [] if backend == "direct" else INITIAL_PLAYBOOK
            for role, name in (("evolved", "ours"), ("B1_frozen", "B1")) if backend == "direct" else (
                    ("experience", "ACE"),):
                arms.append({"name": name + str(seed), "role": role, "backend": backend,
                    "source_config": config_name, "source_config_sha256": sha(config_path),
                    "bank_sha256": csha(bank)})
    parent_path = tmp_path / "configs/direct.json"
    for variant, policy, feedback in (
            ("whole_bank", "whole_bank", "carry_partial_and_refine"),
            ("first_commit", "legal_scope", "batch_only_first_commit")):
        config = copy.deepcopy(read(parent_path))
        config.update(run_id="learn_" + variant, ablation_variant=variant,
                      skill_commit_policy=policy, candidate_feedback_policy=feedback,
                      comparison_reference_run="learn_direct",
                      comparison_reference_config_sha256=sha(parent_path))
        config_name = f"configs/{variant}.json"
        path = put(config_name, config)
        bindings = copy.deepcopy(read(parent_path.with_suffix(".frozen.json")))
        bindings["config_sha256"] = sha(path)
        put(f"configs/{variant}.frozen.json", bindings)
        for batch in (1, 2):
            put(f"runs/{config['run_id']}/publications/b{batch}.json", {"bank": []})
        for filename in ("completion.json", "initialization.json", "terminal_preservation.json"):
            put(f"runs/{config['run_id']}/{filename}", read(tmp_path / "runs/learn_direct" / filename))
        arms.append({"name": variant, "role": "ablation", "backend": "direct",
                     "source_config": config_name, "source_config_sha256": sha(path),
                     "bank_sha256": csha([])})
    public = {key: {} for key in frozen.PUBLIC_LAW_FIELDS}
    public["complete_public_statutes"] = {"Arizona": "Ariz. Rev. Stat. § 33-1123"}
    public["no_cases_targets_trajectories_scores_or_prior_bank"] = True
    public_path = put("data/public/law_only.json", public)
    static = {"run_id": "compile_static", "generation": generation, "teacher": {"model": "fixture_teacher"},
              "execution_contract": "direct_statutory_claims", "execution_contract_version": 14,
              "source_cases": 0, "planned_batches": 0, "library_token_hard_cap": 4096,
              "purpose": "one_blind_public_law_compilation_no_performance_evaluation",
              "input_is_public_law_contract_bundle_not_case_packet": True,
              "no_8B_generation_or_evaluation_in_compilation": True,
              "no_current_or_future_facts_labels_trajectories_scores_or_prior_bank_to_author": True,
              "input_packet": "data/public/law_only.json"}
    static_path = put("configs/static.json", static)
    bindings = {name: sha(tmp_path / name) for name in actor_files}
    bindings[static["input_packet"]] = sha(public_path)
    put("configs/static.frozen.json", {"config_sha256": sha(static_path), "files": bindings})
    put("runs/compile_static/publication.json", {"bank": [], "bank_sha256": csha([]),
        "Qwen_tokens": 2, "training_sources_seen": 0, "actual_native_generations": 0,
        "compiled_not_evaluated": True})
    put("runs/compile_static/completion.json", {"status": "compiled_law_only_static_bank_not_evaluated"})
    teacher = "runs/compile_static/teacher/law_only_compilation/"
    request = {"model": "fixture_teacher", "user_prompt": json.dumps(public)}
    put(teacher + "wire_request.json", request)
    event = put(teacher + "event_log.json", {"event_log": "synthetic no-tool teacher event"})
    put(teacher + "response.json", {"value": {"bank": []}, "cache_hit": False,
        "model": "fixture_teacher", "request_sha256": csha(request), "actual_event_log_path": str(event),
        "invocation": {"returncode": 0, "tool_events_detected": False,
            "event_log_sha256": csha({"event_log": "synthetic no-tool teacher event"})}})
    arms.append({"name": "static", "role": "static_law_only", "backend": "direct",
                 "source_config": "configs/static.json", "source_config_sha256": sha(static_path),
                 "bank_sha256": csha([])})
    source = {"case_id": 1000001, "source_key": "TEST", "prompt": "synthetic public prompt",
              "components": {"instruction": "Find all applicable exemptions.",
                "meta_instruction": "Only public law.",
                "statutes": "Ariz. Rev. Stat. § 33-1123\nHousehold property up to $15,000.",
                "solved_steps": "The Debtor may claim property exemptions under Arizona statutes.",
                "facts": "A (hereinafter the Debtor) owns a watch worth $40."}}
    put("data/test/inputs.json", {"rows": [{**source, "family": f} for f in ("EC", "EV")]})
    citation = "Ariz. Rev. Stat. § 33-1123"
    put("data/test/grading_only/1000001.json", {"targets": {
        "EC": {"watch": [citation]}, "EV": {"watch": [{"citation": citation, "claim_value": 40}]}}})
    proc = Path(f"/proc/{os.getpid()}")
    put("env.json", {"pid": os.getpid(),
        "actual_argv": [v.decode() for v in (proc / "cmdline").read_bytes().split(b"\0") if v],
        "process_start_ticks": (proc / "stat").read_text().rsplit(")", 1)[1].split()[19]})
    cfg = {"run_id": "synthetic_frozen", "evaluation_role": "sealed_frozen_comparison",
           "final_matrix_frozen": True, "no_validation_set": True, "generation": generation,
           "execution_contract": "direct_statutory_claims", "execution_contract_version": 14,
           "library_token_hard_cap": 4096,
           "statistics_plan": "stats.json", "training_source_cases": 2, "training_batch_source_cases": 1,
           "training_packet_sha256": train_sha, "source_cases": 1, "reference_arm": "empty",
           "input_packet": "data/test/inputs.json", "grading_directory": "data/test/grading_only",
           "inference_environment": "env.json", "arms": arms}
    cfg["primary_contrasts"] = [{"name": name, "after": ["ours", "ours145", "ours245"],
                                 "before": before} for name, before in (
        ("vs_empty", ["empty"]), ("vs_B1", ["B1", "B1145", "B1245"]),
        ("vs_ACE", ["ACE", "ACE145", "ACE245"]), ("vs_static", ["static"]))]
    cfg["secondary_contrasts"] = [{"name": "vs_" + name, "after": ["ours"], "before": [name]}
                                  for name in ("whole_bank", "first_commit")]
    config_path = tmp_path / "configs/evaluation.json"

    def seal():
        RunStore.atomic_json(config_path, cfg)
        names = ["env.json", "data/test/inputs.json", "data/test/grading_only/1000001.json"]
        RunStore.atomic_json(config_path.with_suffix(".frozen.json"), {
            "config_sha256": sha(config_path), "files": {name: sha(tmp_path / name) for name in names}})
        return config_path

    return cfg, seal, tmp_path


@pytest.fixture
def continued_ace_origin(tmp_path, monkeypatch):
    """A three-source synthetic TRAIN lineage, never a real test packet."""
    monkeypatch.setattr(frozen, "ROOT", tmp_path)
    def put(name, value):
        return RunStore.immutable_json(tmp_path / name, value)
    rows = [{"case_id": b, "family": f, "batch": b}
            for b in (1, 2, 3) for f in ("EC", "EV")]
    packet = put("train/inputs.json", {"rows": rows})
    old = {"run_id": "original_ace", "learner": "ace_native_online_v3",
           "generation": {"seed": 45}, "teacher": {"model": "fixture", "total_invocation_budget": 100},
           "input_packet": "train/inputs.json", "grading_directory": "TRAIN_only",
           "source_cases": 3, "batch_source_cases": 1, "planned_batches": 3,
           "execution_contract": "direct_statutory_claims", "execution_contract_version": 14,
           "library_token_hard_cap": 8192, "ace_max_TRAIN_reflection_rounds": 3,
           "ace_bullet_provenance_policy": "preserve_raw_ids_distinct_reflection_tags"}
    old_cfg = put("old.json", old)
    old_frozen = put("old.frozen.json", {"files": {"train/inputs.json": sha(packet)}})
    before, after = Path("runs/original_ace"), Path("runs/continued_ace")
    put(before / "initialization.json", {"playbook": INITIAL_PLAYBOOK})
    origins, responses, answer_paths = [], [], []
    parent, book = csha(INITIAL_PLAYBOOK), INITIAL_PLAYBOOK
    for batch in (1, 2, 3):
        records = {role: [] for role in ("ace", "empty", "empty_direct_numeric")}
        for family in ("EC", "EV"):
            name = before / "native" / f"b{batch}_prequential" / f"{batch}_{family}.json"
            put(name, {"stage": f"b{batch}_prequential", "calls": [{"fixture": True}]})
            origins.append(str(name))
            prediction = {"case_id": batch, "family": family, "raw_call_path": str(name),
                          "parsed": {"answer": {}}, "parse_error": None, "score": {"f1": 1.0}}
            if batch <= 2:
                ap = name.with_suffix(".answer.json")
                put(ap, prediction); answer_paths.append(str(ap))
            for role in records:
                records[role].append(copy.deepcopy(prediction))
        put(before / "batches" / f"b{batch}_records.json", records)
        put(after / "batches" / f"b{batch}_records.json", records)
        if batch <= 2:
            book += f"\n[misc-{batch:05d}] helpful=0 harmful=0 :: synthetic TRAIN rule {batch}"
            pub = {"playbook": book, "parent_playbook_sha256": parent, "playbook_sha256": csha(book)}
            put(before / "publications" / f"b{batch}.json", pub)
            put(after / "publications" / f"b{batch}.json", pub)
            parent = pub["playbook_sha256"]
            role = before / "teacher" / f"b{batch}_curator" / "response.json"
            put(role, {"cache_hit": False}); responses.append(str(role))
    summary = [{"batch": 1}, {"batch": 2}]
    put(before / "batch_summary.json", summary)
    put(before / "terminal_preservation.json", {"synthetic": True})
    put(before / "failure.json", {"error": "InterruptedError('Operator stop at artifact-safe boundary')",
        "actual_native_calls": len(origins) + 1, "actual_teacher_responses": len(responses) + 1})
    retired_native = before / "native/b3_TRAIN_round1/3_EV.json"
    retired_teacher = before / "teacher/b3_3_EV_r1_reflector/response.json"
    put(retired_native, {"stage": "b3_TRAIN_round1"})
    put(retired_teacher, {"cache_hit": False})
    files = [old_cfg, old_frozen, packet, *(tmp_path / before).rglob("*.json")]
    receipt = {"role": "exact_last_complete_ACE_prefix_not_best_checkpoint",
        "through_batch": 2, "saved_first_forecast_batch": 3,
        "source_config": "old.json", "source_config_sha256": sha(old_cfg),
        "source_frozen": "old.frozen.json", "source_frozen_sha256": sha(old_frozen),
        "source_run_id": old["run_id"], "parent_playbook_sha256": parent,
        "no_parse_failure_in_completed_prefix": True, "zero_B3_TRAIN_or_teacher_import": True,
        "native_origins": origins, "teacher_responses": responses,
        "retired_B3_TRAIN_native": 1, "retired_B3_teacher_responses": 1,
        "files": {str(p.relative_to(tmp_path)): sha(p) for p in files}}
    rp = put("receipt.json", receipt)
    initial = {"playbook": book, "not_a_new_independent_repeat_when_continued": True,
        "continued_same_learner_prefix": {"receipt": "receipt.json", "source_run": old["run_id"],
            "through_batch": 2, "parent_playbook_sha256": parent}}
    continuation = {"receipt_sha256": sha(rp), "source_run": old["run_id"],
        "not_a_new_independent_learning_repeat": True,
        "restored_native_origins": len(origins), "restored_teacher_responses": len(responses),
        "retired_B3_TRAIN_native_not_imported": 1, "retired_B3_teachers_not_imported": 1}
    put(after / "continuation.json", continuation)
    complete = {"continuation_source_run": old["run_id"], "batch_summary": summary + [{"batch": 3}],
        "restored_native_origins": len(origins), "restored_teacher_responses": len(responses),
        "actual_native_calls": len(origins) + 2, "fresh_native_calls_after_continuation": 2,
        "actual_teacher_responses": len(responses) + 3, "fresh_teacher_responses_after_continuation": 3}
    source = {**old, "run_id": "continued_ace", "learner": "ace_native_online_v4",
        "ace_failed_output_feedback_policy": "verbatim_public_output_no_answer_recovery",
        "initial_library_kind": "same_empty_origin_exact_last_completed_prefix_disclosed",
        "continuation_receipt": "receipt.json"}
    bound = {"files": {"receipt.json": sha(rp), "train/inputs.json": sha(packet)}}
    def resign():
        RunStore.atomic_json(rp, receipt)
        bound["files"]["receipt.json"] = sha(rp)
        cp = tmp_path / after / "continuation.json"
        RunStore.atomic_json(cp, {**read(cp), "receipt_sha256": sha(rp)})
    return source, bound, tmp_path / after, initial, complete, receipt, resign, answer_paths


def test_exact_ACE_prefix_origin_is_valid_without_a_TEST_or_model_read(continued_ace_origin, monkeypatch):
    source, bound, out, initial, complete, receipt, _, _ = continued_ace_origin
    seen = []
    def guarded(path):
        seen.append(str(path))
        assert "sealed_TEST" not in str(path)
        return read(path)
    monkeypatch.setattr(frozen, "read", guarded)
    result = frozen.check_ace_learning_origin(source, bound, out, initial, complete)
    assert out / "continuation.json" in result
    assert out.parent.parent / "receipt.json" in result
    assert all("sealed_TEST" not in p for p in seen)
    assert len(result) == len(receipt["files"]) + 7


@pytest.mark.parametrize("stage", [frozen.INITIAL_STAGE, frozen.FINAL_STAGE])
@pytest.mark.parametrize("mutation", [None, "missing_text", "small_matrix", "small_TEST", "small_TRAIN",
                                      "old12_matrix", "old_single_baseline_design", "missing_stage",
                                      "missing_plan", "missing_plan_hash", "missing_protocol", "old_ablations",
                                      "wrong_batch", "missing_primary", "missing_ablation"])
def test_formal_CLI_requires_the_complete_paper_design_before_bank_or_TEST_access(
        tmp_path, monkeypatch, stage, mutation):
    cfg = {"external_text_adaptation": "trace2skill_text_offline_v1",
           "arms": [{}] * (8 if stage == frozen.INITIAL_STAGE else 16),
           "evaluation_stage": stage, "staged_comparison_protocol": frozen.STAGED_PROTOCOL,
           "ablation_design": "legal_scope_granularity_v1",
           "future_learning_plan": "six_recipes.json", "future_learning_plan_sha256": "a" * 64,
           "source_cases": 128, "training_source_cases": 128, "training_batch_source_cases": 16,
           "primary_contrasts": [{}] * 5, "secondary_contrasts": [{}] * 2}
    if mutation == "missing_text":
        del cfg["external_text_adaptation"]
    elif mutation == "small_matrix":
        cfg["arms"] = cfg["arms"][:-1]
    elif mutation == "old12_matrix":
        cfg["arms"] = [{}] * 12
    elif mutation == "old_single_baseline_design":
        cfg["experience_replication_design"] = frozen.SINGLE_BASELINE_DESIGN
    elif mutation == "missing_stage":
        del cfg["evaluation_stage"]
    elif mutation == "missing_plan":
        del cfg["future_learning_plan"]
    elif mutation == "missing_plan_hash":
        del cfg["future_learning_plan_sha256"]
    elif mutation == "missing_protocol":
        del cfg["staged_comparison_protocol"]
    elif mutation == "old_ablations":
        cfg["ablation_design"] = "scope_and_feedback_legacy"
    elif mutation == "small_TEST":
        cfg["source_cases"] = 24
    elif mutation == "small_TRAIN":
        cfg["training_source_cases"] = 32
    elif mutation == "wrong_batch":
        cfg["training_batch_source_cases"] = 8
    elif mutation == "missing_primary":
        cfg["primary_contrasts"] = cfg["primary_contrasts"][:4]
    elif mutation == "missing_ablation":
        cfg["secondary_contrasts"] = []
    path = tmp_path / "evaluation.json"
    RunStore.immutable_json(path, cfg)
    monkeypatch.setattr(frozen, "ROOT", tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["formal_entry", "freeze", str(path)])
    class ActualBankGateReached(Exception):
        pass
    def not_a_real_bank_read(value):
        assert mutation is None
        raise ActualBankGateReached("Only the complete design may reach the actual bank checks")
    monkeypatch.setattr(frozen, "fixed_banks", not_a_real_bank_read)
    with pytest.raises(ActualBankGateReached if mutation is None else ValueError):
        frozen.main()


@pytest.mark.parametrize("mutation", ["unbound", "changed_artifact", "failed_prefix", "unfinished_native",
    "unfinished_teacher", "chosen_early_prefix", "rescored_B3", "missing_B3_view", "new_seed",
    "wrong_policy", "wrong_condition", "hidden_retired_cost", "wrong_fresh_cost"])
def test_invalid_ACE_continuation_cannot_enter_final_banks(continued_ace_origin, mutation):
    source, bound, out, initial, complete, receipt, resign, answer_paths = continued_ace_origin
    root = out.parent.parent
    if mutation == "unbound":
        bound["files"]["receipt.json"] = "0" * 64
    elif mutation in ("changed_artifact", "failed_prefix"):
        path = root / answer_paths[0]
        RunStore.atomic_json(path, {**read(path), "parse_error": "actual failed prefix"})
        if mutation == "failed_prefix":
            receipt["files"][answer_paths[0]] = sha(path); resign()
    elif mutation.startswith("unfinished_"):
        key = "native_origins" if mutation == "unfinished_native" else "teacher_responses"
        name = ("runs/original_ace/native/b3_TRAIN_round1/3_EV.json" if key == "native_origins" else
                "runs/original_ace/teacher/b3_3_EV_r1_reflector/response.json")
        receipt[key].append(name); resign()
    elif mutation == "chosen_early_prefix":
        RunStore.immutable_json(root / "runs/original_ace/publications/b3.json", {"not_last_B2": True})
    elif mutation == "rescored_B3":
        path = out / "batches/b3_records.json"; data = read(path)
        data["ace"][0]["score"]["f1"] = 0.5; RunStore.atomic_json(path, data)
    elif mutation == "missing_B3_view":
        for path in (out / "batches/b3_records.json", root / "runs/original_ace/batches/b3_records.json"):
            data = read(path)
            for role in data:
                data[role] = data[role][:1]
            RunStore.atomic_json(path, data)
        name = "runs/original_ace/batches/b3_records.json"
        receipt["files"][name] = sha(root / name); resign()
    elif mutation == "new_seed":
        source["generation"] = {"seed": 145}
    elif mutation == "wrong_policy":
        source["ace_failed_output_feedback_policy"] = "drop_failed_text"
    elif mutation == "wrong_condition":
        source["ace_max_TRAIN_reflection_rounds"] = 1
    elif mutation == "hidden_retired_cost":
        receipt["retired_B3_TRAIN_native"] = 0; resign()
    else:
        complete["fresh_native_calls_after_continuation"] += 1
    with pytest.raises(ValueError):
        frozen.check_ace_learning_origin(source, bound, out, initial, complete)


def test_ACE_restart_metadata_is_not_a_change_in_the_verified_empty_origin_protocol(plan):
    cfg, _, root = plan
    sources = {a["name"]: read(root / a["source_config"]) for a in cfg["arms"] if a.get("source_config")}
    sources["ACE"]["initial_library_kind"] = "same_empty_origin_exact_last_completed_prefix_disclosed"
    sources["ACE"]["continuation_receipt"] = "separately_verified_in_origin_tests.json"
    frozen.check_primary_contrasts(cfg, sources)
    sources["ACE145"]["ace_failed_output_feedback_policy"] = "different_failure_policy"
    with pytest.raises(ValueError, match="shared protocol"):
        frozen.check_primary_contrasts(cfg, sources)


@pytest.mark.parametrize("workers", [1, 4])
@pytest.mark.parametrize("source_duplicates", [1, 2])
@pytest.mark.parametrize("negative_asset", ["absent", "empty", "false_claim"])
def test_frozen_matrix_answers_every_arm_before_any_gold_read_and_reports_real_reuse(
        plan, monkeypatch, negative_asset, source_duplicates, workers):
    cfg, seal, root = plan
    # CPU dispatch fixture only. Real frozen-mode/environment guards are checked
    # separately below; no existing server is reconfigured or called.
    cfg["inference_request_workers"] = workers
    monkeypatch.setattr(frozen, "evaluation_request_workers", lambda _: workers)
    _, _, provenance = frozen.fixed_banks(cfg)
    assert all(root / "runs" / name / "terminal_preservation.json" in provenance
               for name in ("learn_direct", "learn_ace", "learn_direct145", "learn_ace145",
                            "learn_direct245", "learn_ace245", "learn_whole_bank", "learn_first_commit"))
    grade_reads, calls = [], []
    if negative_asset != "absent":
        packet = root / cfg["input_packet"]
        value = read(packet)
        for row in value["rows"]:
            row["components"]["facts"] += " The Debtor also owns a lamp worth $25."
        RunStore.atomic_json(packet, value)
        target_path = root / cfg["grading_directory"] / "1000001.json"
        target = read(target_path)
        for family in ("EC", "EV"):
            target["targets"][family]["lamp"] = []
        RunStore.atomic_json(target_path, target)
        monkeypatch.setattr("legal_skill_guard.learning.legal_namespace.asset_description_lexicon",
                            lambda: ("watch", "lamp"))
    if source_duplicates == 2:
        packet = root / cfg["input_packet"]
        rows = read(packet)["rows"]
        copies = [{**copy.deepcopy(row), "case_id": 1000002, "source_key": "TEST2"} for row in rows]
        RunStore.atomic_json(packet, {"rows": rows + copies})
        RunStore.immutable_json(root / cfg["grading_directory"] / "1000002.json", read(
            root / cfg["grading_directory"] / "1000001.json"))
        cfg["source_cases"] = 2

    concurrency_lock, concurrent_pair = threading.Lock(), threading.Event()
    activity = {"active": 0, "max": 0, "started": 0}

    def grading_read(path):
        if path.parent.name == "grading_only":
            assert len(list((root / "runs/synthetic_frozen/native").rglob("*.answer.json"))) == 26 * source_duplicates
            assert (root / "runs/synthetic_frozen/predictions_before_any_grading.json").is_file()
            grade_reads.append(str(path))
        return read(path)

    def call(self, dest, messages, schema, max_tokens, metadata):
        assert not grade_reads
        with concurrency_lock:
            activity["active"] += 1
            activity["started"] += 1
            activity["max"] = max(activity["max"], activity["active"])
            if activity["started"] >= 2:
                concurrent_pair.set()
        if workers == 4:
            assert concurrent_pair.wait(2), "Distinct synthetic requests should overlap"
        time.sleep(0.003)
        calls.append(metadata)
        ref = "Ariz. Rev. Stat. section 33-1123"
        value = {"A001": [ref] if metadata["family"] == "EC" else
                 [{"citation_ref": ref, "claim_value": 40}]}
        if negative_asset != "absent":
            value["A002"] = ([] if negative_asset == "empty" else
                             [ref] if metadata["family"] == "EC" else
                             [{"citation_ref": ref, "claim_value": 25}])
        if metadata["arm"] == "ace":
            value = {"reasoning": "synthetic public finding", "bullet_ids": [], "final_answer": value}
        validate(value, schema)
        response = {"content": json.dumps(value), "finish_reason": "stop",
                    "prompt_tokens": 13, "completion_tokens": 17}
        raw = {"response": response, **metadata}
        RunStore.immutable_json(dest, raw)
        self.native.append(raw)
        with concurrency_lock:
            activity["active"] -= 1
        return response

    monkeypatch.setattr(common, "read", grading_read)
    monkeypatch.setattr(frozen.FrozenEvaluation, "call", call)
    study = frozen.FrozenEvaluation(seal())
    study.run()
    result = read(study.out / "completion.json")
    assert len(calls) == 4 and len(grade_reads) == 26 * source_duplicates
    assert len(result["exact_wire_reuses_not_independent_draws"]) == 26 * source_duplicates - 4
    assert 1 <= activity["max"] <= workers
    assert activity["active"] == 0
    if workers == 4:
        assert activity["max"] >= 2
    assert result["inference_request_workers"] == workers
    saved = read(study.out / "predictions_before_any_grading.json")
    for values in saved.values():
        assert [(r["case_id"], r["family"]) for r in values] == [
            (row["case_id"], row["family"]) for row in read(root / cfg["input_packet"])["rows"]]
    assert result["teacher_calls"] == 0
    assert result["native_prompt_tokens"] == 52 and result["native_completion_tokens"] == 68
    # The original scorer gives the empty target asset zero either way. Final
    # reporting must preserve that native score while exposing the false claim.
    native_f1 = 1 if negative_asset == "absent" else 0.5
    complete_f1 = 2 / 3 if negative_asset == "false_claim" else 1
    for values in result["metrics"].values():
        for family in ("EC", "EV"):
            assert values[family]["f1"] == native_f1
            assert values[family]["full_output_f1"] == pytest.approx(complete_f1)
            assert values[family]["negative_or_unscored_asset_claims"] == (
                source_duplicates if negative_asset == "false_claim" else 0)
    assert result["paired_vs_own_B1_frozen"]["ours"]["mean_f1_difference"] == 0
    statistics = result["paired_source_statistics"]
    assert statistics["sources"] == source_duplicates and statistics["primary_family_comparisons"] == 8
    assert statistics["secondary_family_comparisons"] == 4
    assert set(statistics["secondary_contrasts"]) == {"vs_whole_bank", "vs_first_commit"}
    assert not statistics["all_primary_adjusted_lower_bounds_positive"]


@pytest.mark.parametrize("mutation", [
    "teacher", "not_frozen", "missing_B1", "missing_static", "missing_repeat", "missing_contrasts",
    "failed_learning", "zero_cases", "decoding", "warm_start", "wrong_repeat_seed", "mispaired_control",
    "repeat_policy", "repeat_teacher", "repeat_memory", "repeat_ACE_rounds", "missing_terminal", "unexpected_failure"])
def test_reject_invalid_final_matrix_before_test_packet_read(plan, monkeypatch, mutation):
    cfg, _, root = plan
    if mutation == "teacher":
        cfg["teacher"] = {"model": "not_allowed"}
    elif mutation == "not_frozen":
        cfg["final_matrix_frozen"] = False
    elif mutation == "missing_B1":
        cfg["arms"] = [a for a in cfg["arms"] if a["role"] != "B1_frozen"]
    elif mutation == "missing_static":
        cfg["arms"] = [a for a in cfg["arms"] if a["role"] != "static_law_only"]
    elif mutation == "missing_repeat":
        cfg["arms"] = [a for a in cfg["arms"] if a["name"] != "ours145"]
    elif mutation == "missing_contrasts":
        cfg["primary_contrasts"] = []
    elif mutation == "zero_cases":
        cfg["source_cases"] = 0
    elif mutation == "decoding":
        cfg["generation"]["seed"] = 46
    elif mutation == "warm_start":
        path = root / "runs/learn_direct/initialization.json"
        RunStore.atomic_json(path, {**read(path), "initial_case_exposure": 16})
    elif mutation == "missing_terminal":
        (root / "runs/learn_ace/terminal_preservation.json").unlink()
    elif mutation == "unexpected_failure":
        RunStore.immutable_json(root / "runs/learn_ace/failure.json", {"actual_failure": True})
    elif mutation == "wrong_repeat_seed" or mutation.startswith("repeat_"):
        config_name = "configs/ace145.json" if mutation == "repeat_ACE_rounds" else "configs/direct145.json"
        path = root / config_name
        value = read(path)
        if mutation == "wrong_repeat_seed":
            value["generation"]["seed"] = 45
        elif mutation == "repeat_policy":
            value["skill_commit_policy"] = "whole_bank"
        elif mutation == "repeat_teacher":
            value["teacher"] = {"model": "different_author"}
        elif mutation == "repeat_memory":
            value["library_token_hard_cap"] = 2048
        else:
            value["ace_max_TRAIN_reflection_rounds"] = 1
        RunStore.atomic_json(path, value)
        source_frozen = path.with_suffix(".frozen.json")
        RunStore.atomic_json(source_frozen, {**read(source_frozen), "config_sha256": sha(path)})
        for arm in cfg["arms"]:
            if arm.get("source_config") == config_name:
                arm["source_config_sha256"] = sha(path)
    elif mutation == "mispaired_control":
        next(c for c in cfg["primary_contrasts"] if c["name"] == "vs_B1")["before"].reverse()
    else:
        path = root / "runs/learn_direct/completion.json"
        RunStore.atomic_json(path, {**read(path), "status": "failed"})

    def guarded(path):
        assert str(path) != str(root / cfg["input_packet"])
        return read(path)

    monkeypatch.setattr(frozen, "read", guarded)
    with pytest.raises(ValueError):
        frozen.fixed_banks(cfg)


def test_test_overlap_is_retained_as_failure_without_inference_or_resampling(plan, monkeypatch):
    cfg, seal, root = plan
    packet = root / cfg["input_packet"]
    rows = copy.deepcopy(read(packet)["rows"])
    for row in rows:
        row["source_key"] = "TRAIN0"
    RunStore.atomic_json(packet, {"rows": rows})
    monkeypatch.setattr(frozen.FrozenEvaluation, "call", lambda *args: pytest.fail("No model call allowed"))
    study = frozen.FrozenEvaluation(seal())
    with pytest.raises(ValueError, match="overlaps"):
        study.run()
    assert (study.out / "failure.json").is_file()
    assert not (study.out / "completion.json").exists()
    assert read(packet)["rows"] == rows


@pytest.mark.parametrize("workers", [1, 4])
def test_native_failure_is_preserved_without_retry_or_partial_scoring(plan, monkeypatch, workers):
    cfg, seal, _ = plan
    cfg["inference_request_workers"] = workers
    monkeypatch.setattr(frozen, "evaluation_request_workers", lambda _: workers)
    calls = []

    def failed_call(self, dest, messages, schema, max_tokens, metadata):
        calls.append(1)
        raw = {"synthetic_transport_failure": True, **metadata}
        RunStore.immutable_json(dest, raw)
        self.native.append(raw)
        raise RuntimeError("synthetic transport failure")

    monkeypatch.setattr(frozen.FrozenEvaluation, "call", failed_call)
    monkeypatch.setattr(frozen.FrozenEvaluation, "grade", lambda *args: pytest.fail("No partial scoring"))
    study = frozen.FrozenEvaluation(seal())
    with pytest.raises(RuntimeError, match="synthetic transport failure"):
        study.run()
    assert 1 <= len(calls) <= workers
    assert len(list((study.out / "native").rglob("*.json"))) == 2 * len(calls)
    assert (study.out / "failure.json").is_file()
    assert not (study.out / "completion.json").exists()
    assert not (study.out / "predictions_before_any_grading.json").exists()
    if workers == 4:
        assert study.stop


@pytest.mark.parametrize("workers", [True, False, 0, 2, 5, "4", None])
def test_dispatch_rejects_undeclared_worker_counts_before_any_packet_read(workers, monkeypatch):
    monkeypatch.setattr(frozen, "read", lambda _: pytest.fail("No environment or TEST read required"))
    with pytest.raises(ValueError, match="one or four"):
        frozen.evaluation_request_workers({"inference_request_workers": workers})


@pytest.mark.parametrize("argv", [
    ["vllm", "--max-num-seqs", "4"], ["vllm"], ["vllm", "--max-num-seqs"],
    ["vllm", "--max-num-seqs", "1"],
    ["vllm", "--max-num-seqs", "4", "--max-num-seqs", "4"],
])
def test_parallel_dispatch_requires_declared_captured_four_sequence_environment(tmp_path, monkeypatch, argv):
    monkeypatch.setattr(frozen, "ROOT", tmp_path)
    RunStore.immutable_json(tmp_path / frozen.DISPATCH_PROTOCOL, {"synthetic_protocol_only": True})
    RunStore.immutable_json(tmp_path / "env.json", {"actual_argv": argv})
    cfg = {"inference_request_workers": 4, "inference_environment": "env.json",
           "inference_dispatch_protocol": frozen.DISPATCH_PROTOCOL,
           "inference_dispatch_policy": "four_workers_one_instance_exact_wire_lock_no_retry"}
    if argv == ["vllm", "--max-num-seqs", "4"]:
        assert frozen.evaluation_request_workers(cfg) == 4
    else:
        with pytest.raises(ValueError, match="captured four-sequence"):
            frozen.evaluation_request_workers(cfg)
    cfg.pop("inference_dispatch_policy")
    with pytest.raises(ValueError, match="explicit single-instance"):
        frozen.evaluation_request_workers(cfg)


def test_final_actor_endpoint_cannot_differ_from_learning_endpoint(plan, monkeypatch):
    cfg, _, _ = plan
    cfg["generation"]["base_url"] = "http://127.0.0.1:8001/v1"
    original = frozen.read

    def guarded(path):
        assert "data/test" not in str(path)
        return original(path)

    monkeypatch.setattr(frozen, "read", guarded)
    with pytest.raises(ValueError, match="differs: base_url"):
        frozen.fixed_banks(cfg)


@pytest.mark.parametrize("dependency", [
    "legal_skill_guard/learning/openexempt_ace.py", "third_party/ace/prompts/generator.py",
    "legal_skill_guard/inference/openai_client.py"])
def test_changed_ACE_inference_adapter_cannot_be_used_with_a_differently_trained_bank(plan, dependency):
    cfg, _, root = plan
    path = root / "configs/ace.frozen.json"
    changed = read(path)
    changed["files"][dependency] = "not-the-trained-adapter"
    RunStore.atomic_json(path, changed)
    with pytest.raises(ValueError, match="Shared task actor/scorer changed"):
        frozen.fixed_banks(cfg)


def test_completed_flag_cannot_hide_missing_training_sources(plan):
    cfg, _, root = plan
    path = root / "runs/learn_direct/completion.json"
    changed = read(path)
    changed["prequential_skills"]["EV"]["tasks"] = 1
    RunStore.atomic_json(path, changed)
    with pytest.raises(ValueError, match="every declared source"):
        frozen.fixed_banks(cfg)


def test_same_learned_bank_cannot_be_renamed_as_two_learning_repeats(plan):
    cfg, _, _ = plan
    ours = next(a for a in cfg["arms"] if a["role"] == "evolved")
    cfg["arms"].append({**ours, "name": "not_an_independent_repeat"})
    with pytest.raises(ValueError, match="not independent repeats"):
        frozen.fixed_banks(cfg)


@pytest.mark.parametrize("mutation", [
    "observed_cases", "public_changed", "private_field", "compile_failed", "over_cap", "duplicates",
    "cached_teacher", "different_request", "changed_event"])
def test_static_control_is_real_blind_compilation_not_fake_training_or_selected_bank(plan, mutation):
    cfg, _, root = plan
    static = next(a for a in cfg["arms"] if a["role"] == "static_law_only")
    source_path = root / static["source_config"]
    source = read(source_path)
    frozen_path = source_path.with_suffix(".frozen.json")
    bindings = read(frozen_path)
    if mutation == "observed_cases":
        source["source_cases"] = 1
        RunStore.atomic_json(source_path, source)
        static["source_config_sha256"] = bindings["config_sha256"] = sha(source_path)
    elif mutation in {"public_changed", "private_field"}:
        public_path = root / source["input_packet"]
        public = read(public_path)
        public["facts"] = "A private case must never be in this author's public bundle."
        RunStore.atomic_json(public_path, public)
        if mutation == "private_field":
            bindings["files"][source["input_packet"]] = sha(public_path)
    elif mutation == "compile_failed":
        path = root / "runs/compile_static/completion.json"
        RunStore.atomic_json(path, {"status": "failed"})
    elif mutation == "over_cap":
        path = root / "runs/compile_static/publication.json"
        RunStore.atomic_json(path, {**read(path), "Qwen_tokens": 4097})
    elif mutation == "duplicates":
        cfg["arms"].append({**static, "name": "not_an_independent_static_repeat"})
    elif mutation == "cached_teacher":
        path = root / "runs/compile_static/teacher/law_only_compilation/response.json"
        RunStore.atomic_json(path, {**read(path), "cache_hit": True})
    elif mutation == "different_request":
        path = root / "runs/compile_static/teacher/law_only_compilation/wire_request.json"
        RunStore.atomic_json(path, {**read(path), "user_prompt": json.dumps({"facts": "private"})})
    else:
        path = root / "runs/compile_static/teacher/law_only_compilation/event_log.json"
        RunStore.atomic_json(path, {"event_log": "changed synthetic event"})
    RunStore.atomic_json(frozen_path, bindings)
    with pytest.raises(ValueError):
        frozen.fixed_banks(cfg)


def test_source_bootstrap_keeps_EC_EV_and_learning_repeat_pairing_without_pseudoreplication(plan):
    cfg, _, _ = plan
    cfg["source_cases"] = 3
    records = {}
    for arm in cfg["arms"]:
        records[arm["name"]] = []
        for i, key in enumerate(("c", "a", "b")):
            for family in ("EC", "EV"):
                value = 0.5
                if arm["role"] == "evolved":
                    repeat = ["ours", "ours145", "ours245"].index(arm["name"])
                    value += (0.1 * (repeat + 1) + 0.05 * i) * (1 if family == "EC" else -1)
                records[arm["name"]].append({"source_key": key, "case_id": i + 1,
                                            "family": family, "score": {"f1": value}})
    result = frozen.paired_source_statistics(cfg, records)
    assert result["sources"] == 3 and result["primary_family_comparisons"] == 8
    assert result["source_keys_sorted"] == ["a", "b", "c"]
    ec = result["contrasts"]["vs_empty"]["endpoints"]["EC"]
    ev = result["contrasts"]["vs_empty"]["endpoints"]["EV"]
    assert ec["difference_pp"] == pytest.approx(25)
    assert ev["difference_pp"] == pytest.approx(-25)
    assert ec["adjusted_lower_positive"] and not ev["adjusted_lower_positive"]
    assert not result["all_primary_adjusted_lower_bounds_positive"]
    assert ec["source_win_tie_loss"] == [3, 0, 0]
    assert ev["sources_difference_at_most_minus_10pp"] == 3
    assert result["contrasts"]["vs_empty"]["per_learning_repeat"]["difference_pp"] == pytest.approx(
        np.asarray([[15, -15], [25, -25], [35, -35]]))
    reordered = {name: list(reversed(rows)) for name, rows in reversed(list(records.items()))}
    assert result == frozen.paired_source_statistics(cfg, reordered)
    ordinary = ec["conditional_95pct_interval_pp"]
    adjusted = ec["conditional_Bonferroni_interval_pp"]
    assert adjusted[0] <= ordinary[0] <= ordinary[1] <= adjusted[1]
    rng = np.random.Generator(np.random.PCG64(2026102192))
    source_draws = np.asarray([25, 30, 20])[rng.integers(3, size=(20000, 3))].mean(axis=1)
    assert ordinary == pytest.approx(np.quantile(source_draws, [0.025, 0.975], method="linear"))
    assert adjusted == pytest.approx(np.quantile(
        source_draws, [0.025 / 8, 1 - 0.025 / 8], method="linear"))
    secondary = result["secondary_contrasts"]["vs_first_commit"]
    endpoint = secondary["endpoints"]["EC"]
    assert endpoint["difference_pp"] == pytest.approx(15)
    assert endpoint["conditional_95pct_interval_pp"] == pytest.approx(np.quantile(
        source_draws - 10, [0.025, 0.975], method="linear"))
    assert endpoint["conditional_Bonferroni_interval_pp"] == pytest.approx(np.quantile(
        source_draws - 10, [0.025 / 4, 1 - 0.025 / 4], method="linear"))
    assert len(secondary["per_learning_repeat"]["difference_pp"]) == 1
    assert result["secondary_single_learning_seed45_not_three_repeats_or_matched_actual_compute"]


def _synthetic_expanded_primary(plan):
    cfg, _, root = plan
    sources = {a["name"]: read(root / a["source_config"])
               for a in cfg["arms"] if a.get("source_config")}
    names = []
    for seed, suffix in ((45, ""), (145, "145"), (245, "245")):
        name = "Text" + suffix
        names.append(name)
        source = copy.deepcopy(sources["ACE" + suffix])
        source.update(learner="trace2skill_text_offline_v1", merge_batch_size=5,
                      analysis_mode="synthetic_text_fixture_not_a_real_learning_run")
        source["run_id"] = "synthetic_text" + suffix
        source["generation"]["seed"] = seed
        sources[name] = source
        cfg["arms"].append({"name": name, "role": "experience", "backend": "direct",
                            "source_config": "synthetic_not_loaded.json"})
    cfg["external_text_adaptation"] = "trace2skill_text_offline_v1"
    cfg["primary_contrasts"].append({"name": "vs_text_adaptation", "before": names,
                                    "after": ["ours", "ours145", "ours245"]})
    return cfg, sources


def test_expanded_primary_family_is_ten_not_eight_and_still_source_paired(plan):
    cfg, sources = _synthetic_expanded_primary(plan)
    frozen.check_primary_contrasts(cfg, sources)
    cfg["source_cases"] = 3
    records = {a["name"]: [
        {"source_key": str(case), "case_id": case, "family": family,
         "score": {"f1": 0.6 if a["role"] == "evolved" else 0.5}}
        for case in (1, 2, 3) for family in ("EC", "EV")]
        for a in cfg["arms"]}
    result = frozen.paired_source_statistics(cfg, records)
    assert result["sources"] == 3
    assert result["primary_family_comparisons"] == 10
    assert result["secondary_family_comparisons"] == 4
    assert len(result["contrasts"]["vs_text_adaptation"]["per_learning_repeat"]["difference_pp"]) == 3


def _single_actual_experience_banks(plan):
    cfg, sources = _synthetic_expanded_primary(plan)
    deferred = {"ACE145", "ACE245", "Text145", "Text245"}
    cfg["arms"] = [a for a in cfg["arms"] if a["name"] not in deferred]
    for contrast in cfg["primary_contrasts"]:
        contrast["before"] = [n for n in contrast["before"] if n not in deferred]
    cfg["experience_replication_design"] = frozen.SINGLE_BASELINE_DESIGN
    cfg["baseline_build_amendment"] = frozen.SINGLE_BASELINE_PROTOCOL
    return cfg, sources


def _staged_six_recipe_fixture(plan):
    cfg, sources = _synthetic_expanded_primary(plan)
    root = plan[2]
    for name in frozen.runtime_sources.CURRENT:
        target = root / name
        original = Path(frozen.__file__).resolve().parents[1] / name
        if target.is_symlink():
            target.unlink()  # This fixture's own temporary symlink, not project source.
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original, target)
    entries = []
    for arm in cfg["arms"]:
        if arm["role"] == "strong_empty":
            continue
        source = sources[arm["name"]]
        seed = source["generation"]["seed"]
        kind = ("ace" if arm["backend"] == "ace" else
                "text" if arm["name"].startswith("Text") else "main")
        if arm["name"].startswith("Text"):
            arm["source_config"] = "configs/" + arm["name"] + ".json"
            arm["bank_sha256"] = csha([])
        path = root / arm["source_config"]
        if seed != 45 and arm["role"] != "B1_frozen":
            source["run_id"] = "future_" + source["run_id"]
            source["phase_dispatch"] = frozen.runtime_sources.DECLARATION
            source["inference_environment"] = cfg["inference_environment"]
        if arm["role"] == "B1_frozen" and seed != 45:
            source = sources["ours" + str(seed)]
            sources[arm["name"]] = source
        RunStore.atomic_json(path, source)
        arm["source_config_sha256"] = sha(path)
        if seed != 45 and arm["role"] != "B1_frozen":
            bindings = {name: sha(root / name) for name in frozen.runtime_sources.CURRENT}
            bindings[source["input_packet"]] = cfg["training_packet_sha256"]
            RunStore.atomic_json(path.with_suffix(".frozen.json"), {
                "config_sha256": sha(path), "files": bindings})
            entries.append({"kind": kind, "seed": seed, "source_config": arm["source_config"],
                "source_config_sha256": sha(path),
                "source_frozen_sha256": sha(path.with_suffix(".frozen.json"))})
    # Each B1 arm shares the exact actual source config with its evolved run.
    for arm in cfg["arms"]:
        if arm["role"] == "B1_frozen":
            arm["source_config_sha256"] = sha(root / arm["source_config"])
    initial_names = [a["name"] for a in cfg["arms"] if a["role"] == "strong_empty"
                     or sources[a["name"]]["generation"]["seed"] == 45]
    templates = copy.deepcopy(cfg["arms"])
    for arm in templates:
        if arm["name"] not in initial_names:
            arm["bank_sha256"] = None
    future = {"policy": "six_recipes_frozen_before_initial_TEST_v1",
              "no_TEST_feedback_to_learning": True, "future_builds_not_selected_using_initial_scores": True,
              "additional_learning_execution_authorization": "deferred_until_user_review_after_teacher_draft",
              "future_recipes_not_completed_banks": True, "learning": entries,
              "planned_final_arms": templates, "initial_arm_names": initial_names,
              "primary_contrasts": copy.deepcopy(cfg["primary_contrasts"]),
              "secondary_contrasts": copy.deepcopy(cfg["secondary_contrasts"])}
    path = root / "six_recipes.json"
    RunStore.atomic_json(path, future)
    RunStore.immutable_json(root / frozen.STAGED_PROTOCOL, {"synthetic_protocol_only": True})
    cfg.update(evaluation_stage=frozen.INITIAL_STAGE, staged_comparison_protocol=frozen.STAGED_PROTOCOL,
               future_learning_plan="six_recipes.json", future_learning_plan_sha256=sha(path))
    cfg["arms"] = [a for a in cfg["arms"] if a["name"] in initial_names]
    cfg["primary_contrasts"] = [{**c, "after": [n for n in c["after"] if n in initial_names],
                                 "before": [n for n in c["before"] if n in initial_names]}
                                for c in cfg["primary_contrasts"]]
    return cfg, sources, future, root


@pytest.mark.parametrize("stage", [frozen.INITIAL_STAGE, frozen.FINAL_STAGE])
@pytest.mark.parametrize("mutation", [None, "missing_recipe", "duplicate_seed", "config_hash",
    "frozen_hash", "runtime_unbound", "warm_origin", "changed_policy", "selected_repeats",
    "invented_bank", "initial_bank", "dropped_contrast", "started_before_initial", "unauthorized_repeats"])
def test_staged_six_actual_recipes_are_fixed_before_any_TEST_read(plan, monkeypatch, stage, mutation):
    cfg, sources, future, root = _staged_six_recipe_fixture(plan)
    if stage == frozen.FINAL_STAGE:
        cfg["evaluation_stage"] = stage
        cfg["arms"] = copy.deepcopy(future["planned_final_arms"])
        for arm in cfg["arms"]:
            if "bank_sha256" in arm and arm["bank_sha256"] is None:
                arm["bank_sha256"] = csha([])
        cfg["primary_contrasts"] = copy.deepcopy(future["primary_contrasts"])
    entry = future["learning"][0]
    if mutation == "missing_recipe":
        future["learning"].pop()
    elif mutation == "duplicate_seed":
        future["learning"][-1]["seed"] = 145
    elif mutation in ("config_hash", "frozen_hash"):
        entry["source_config_sha256" if mutation == "config_hash" else "source_frozen_sha256"] = "0" * 64
    elif mutation in ("runtime_unbound", "warm_origin", "changed_policy"):
        path = root / entry["source_config"]
        source = read(path)
        bound_path = path.with_suffix(".frozen.json")
        bound = read(bound_path)
        if mutation == "runtime_unbound":
            del bound["files"]["legal_skill_guard/learning/phase_dispatch.py"]
        else:
            source["initial_library_publication" if mutation == "warm_origin" else "skill_commit_policy"] = "changed"
            RunStore.atomic_json(path, source)
            bound["config_sha256"] = sha(path)
            entry["source_config_sha256"] = sha(path)
            for arm in future["planned_final_arms"] + cfg["arms"]:
                if arm.get("source_config") == entry["source_config"]:
                    arm["source_config_sha256"] = sha(path)
        RunStore.atomic_json(bound_path, bound)
        entry["source_frozen_sha256"] = sha(bound_path)
    elif mutation == "selected_repeats":
        future["future_builds_not_selected_using_initial_scores"] = False
    elif mutation == "invented_bank":
        next(a for a in future["planned_final_arms"] if a["name"] == "ours145")["bank_sha256"] = csha([])
    elif mutation == "initial_bank":
        next(a for a in cfg["arms"] if a["name"] == "ours")["bank_sha256"] = "0" * 64
    elif mutation == "dropped_contrast":
        cfg["primary_contrasts"].pop()
    elif mutation == "started_before_initial":
        (root / "runs" / read(root / entry["source_config"])["run_id"]).mkdir()
    elif mutation == "unauthorized_repeats":
        future["additional_learning_execution_authorization"] = "execute_now"
    RunStore.atomic_json(root / cfg["future_learning_plan"], future)
    cfg["future_learning_plan_sha256"] = sha(root / cfg["future_learning_plan"])
    def guarded(path):
        assert Path(path) != root / cfg["input_packet"]
        assert "grading_only" not in Path(path).parts
        return read(path)
    monkeypatch.setattr(frozen, "read", guarded)
    valid = mutation is None or (mutation == "started_before_initial" and stage == frozen.FINAL_STAGE)
    if valid:
        result = frozen.check_future_learning_plan(cfg, sources)
        assert root / "six_recipes.json" in result
        assert len([p for p in result if p.name.endswith(".frozen.json")]) == 6
    else:
        with pytest.raises(ValueError):
            frozen.check_future_learning_plan(cfg, sources)


def test_initial_single_build_intervals_are_descriptive_not_a_stopping_gate(plan):
    cfg, sources, _, _ = _staged_six_recipe_fixture(plan)
    frozen.check_primary_contrasts(cfg, sources)
    cfg["source_cases"] = 3
    records = {arm["name"]: [{"source_key": str(case), "case_id": case, "family": family,
                "score": {"f1": 0.6 if arm["role"] == "evolved" else 0.5}}
                for case in (1, 2, 3) for family in ("EC", "EV")] for arm in cfg["arms"]}
    result = frozen.paired_source_statistics(cfg, records)
    assert result["sources"] == 3
    assert result["primary_family_comparisons"] == 10
    assert result["secondary_family_comparisons"] == 4
    assert result["confirmatory_analysis"] is False
    assert result["all_primary_adjusted_lower_bounds_positive"] is None
    assert result["initial_table_not_a_repeat_selection_or_stopping_gate"] is True
    assert all(len(c["per_learning_repeat"]["difference_pp"]) == 1
               for c in result["contrasts"].values())


@pytest.mark.parametrize("mutation", [None, "changed_config", "changed_prediction", "changed_origin_index",
                                      "different_seed", "missing_original_bank", "failed_initial"])
def test_final_stage_requires_the_original_initial_matrix_provenance(plan, monkeypatch, mutation):
    initial, _, future, root = _staged_six_recipe_fixture(plan)
    initial_path = RunStore.immutable_json(root / "configs/initial_eval.json", initial)
    bound_path = initial_path.with_suffix(".frozen.json")
    RunStore.immutable_json(bound_path, {"config_sha256": sha(initial_path), "files": {}})
    out = root / "runs" / initial["run_id"]
    artifacts = {
        "completion.json": {"status": "completed_frozen_comparison", "evaluation_stage": frozen.INITIAL_STAGE,
            "teacher_calls": 0, "bank_sha256": {a["name"]: a.get("bank_sha256", csha([])) for a in initial["arms"]}},
        "predictions_before_any_grading.json": {"fixture": "not real TEST"},
        "native_origins_before_any_grading.json": {"fixture": "index validated separately"},
        "terminal_preservation.json": {"fixture": "not actual preservation"}}
    for name, value in artifacts.items():
        RunStore.immutable_json(out / name, value)
    cfg = copy.deepcopy(initial)
    cfg.update(evaluation_stage=frozen.FINAL_STAGE, arms=copy.deepcopy(future["planned_final_arms"]))
    cfg["initial_evaluation"] = {"source_config": str(initial_path.relative_to(root)),
        "source_config_sha256": sha(initial_path), "source_frozen_sha256": sha(bound_path),
        **{key: sha(out / name) for name, key in (
            ("completion.json", "completion_sha256"),
            ("predictions_before_any_grading.json", "predictions_sha256"),
            ("native_origins_before_any_grading.json", "native_origins_sha256"),
            ("terminal_preservation.json", "terminal_preservation_sha256"))}}
    if mutation == "changed_config":
        RunStore.atomic_json(initial_path, {**initial, "changed": True})
    elif mutation == "changed_prediction":
        RunStore.atomic_json(out / "predictions_before_any_grading.json", {})
    elif mutation == "changed_origin_index":
        RunStore.atomic_json(out / "native_origins_before_any_grading.json", {})
    elif mutation == "different_seed":
        cfg["generation"]["seed"] = 145
    elif mutation == "missing_original_bank":
        cfg["arms"] = [a for a in cfg["arms"] if a["name"] != "ours"]
    elif mutation == "failed_initial":
        RunStore.immutable_json(out / "failure.json", {"error": "synthetic"})
    def guarded(path):
        assert Path(path) != root / cfg["input_packet"]
        assert "grading_only" not in Path(path).parts
        return read(path)
    monkeypatch.setattr(frozen, "read", guarded)
    if mutation is None:
        assert len(frozen.check_initial_evaluation(cfg)) == 6
    else:
        with pytest.raises(ValueError):
            frozen.check_initial_evaluation(cfg)


@pytest.mark.parametrize("length_ended", [False, True])
@pytest.mark.parametrize("mutation", [None, "changed_response", "changed_wire_input", "duplicate_origin",
                                      "changed_generation", "scored_answers", "missing_task"])
def test_prior_stage_reuses_full_native_wire_not_scores_or_repaired_answers(plan, length_ended, mutation):
    cfg, _, root = plan
    rows = read(root / cfg["input_packet"])["rows"]
    initial = {"run_id": "initial_raw_fixture", "source_cases": 1, "arms": [{"name": "ours"}]}
    initial_path = RunStore.immutable_json(root / "configs/initial_raw.json", initial)
    out = root / "runs" / initial["run_id"]
    index = {"generation_sha256": csha(cfg["generation"]), "origins": []}
    predictions = {"ours": []}
    for row in rows:
        messages, schema, _ = common.actor_payload(row, [], grounded=True, direct_numeric=True, asset_references=True)
        content = json.dumps({"A001": ["Ariz. Rev. Stat. section 33-1123"] if row["family"] == "EC" else
                              [{"citation_ref": "Ariz. Rev. Stat. section 33-1123", "claim_value": 40}]})
        response = {"raw_id": "old_" + row["family"], "content": content,
                    "finish_reason": "length" if length_ended else "stop", "prompt_tokens": 11, "completion_tokens": 13}
        wire = {"messages": messages, **{k: cfg["generation"][k] for k in
                ("model", "temperature", "top_p", "top_k", "max_tokens", "seed")},
                "response_format": {"json_schema": {"schema": schema}}}
        observed = {"id": response["raw_id"], "usage": {"prompt_tokens": 11, "completion_tokens": 13},
                    "choices": [{"finish_reason": response["finish_reason"], "message": {"content": content}}]}
        raw_path = out / "native" / (row["family"] + ".json")
        RunStore.immutable_json(raw_path, {"response": response, "transport_error": None,
                                         "calls": [{"request": wire, "response": observed}]})
        RunStore.immutable_json(raw_path.with_suffix(".input.json"), {"messages": messages, "schema": schema})
        index["origins"].append({"fingerprint": csha({"messages": messages, "schema": schema,
                "generation": cfg["generation"]}), "raw_call_path": str(raw_path.relative_to(root)),
                "raw_sha256": sha(raw_path), "input_sha256": sha(raw_path.with_suffix(".input.json"))})
        predictions["ours"].append({"source_key": row["source_key"], "case_id": row["case_id"],
            "family": row["family"], "raw_call_path": str(raw_path.relative_to(root))})
    entry = index["origins"][0]
    raw_path = root / entry["raw_call_path"]
    if mutation == "changed_response":
        value = read(raw_path)
        value["response"]["content"] = "a fabricated answer"
        RunStore.atomic_json(raw_path, value)
        entry["raw_sha256"] = sha(raw_path)
    elif mutation == "changed_wire_input":
        value = read(raw_path.with_suffix(".input.json"))
        value["messages"] = [{"role": "user", "content": "a different request"}]
        RunStore.atomic_json(raw_path.with_suffix(".input.json"), value)
        entry["input_sha256"] = sha(raw_path.with_suffix(".input.json"))
        entry["fingerprint"] = csha({**value, "generation": cfg["generation"]})
    elif mutation == "duplicate_origin":
        index["origins"].append(copy.deepcopy(entry))
    elif mutation == "changed_generation":
        index["generation_sha256"] = "0" * 64
    elif mutation == "scored_answers":
        predictions["ours"][0]["score"] = {"f1": 1.0}
    elif mutation == "missing_task":
        predictions["ours"].pop()
    RunStore.immutable_json(out / "native_origins_before_any_grading.json", index)
    RunStore.immutable_json(out / "predictions_before_any_grading.json", predictions)
    RunStore.immutable_json(out / "completion.json", {"actual_native_calls": 2})
    study = object.__new__(frozen.FrozenEvaluation)
    study.cfg = {**cfg, "initial_evaluation": {"source_config": str(initial_path.relative_to(root))}}
    study.native, study.request_cache, study.reuse_events = [], {}, []
    study.initial_arm_names, study.prior_native_origins = set(), []
    if mutation is not None:
        with pytest.raises(ValueError):
            study.load_initial_raw_origins()
        return
    study.load_initial_raw_origins()
    assert len(study.prior_native_origins) == 2 and not study.native
    study.out, study.banks = root / "runs/final_raw_fixture", {"ours": []}
    study._wire_lock_guard, study._wire_locks = threading.Lock(), {}
    study.check, study.progress = lambda: None, lambda *args, **kwargs: None
    def forbidden_call(*args, **kwargs):
        raise AssertionError("An original initial-stage request must never be regenerated")
    study.call = forbidden_call
    answer = study.answer(rows[0], {"name": "ours", "backend": "direct"})
    assert bool(answer["parse_error"]) == length_ended
    assert answer["physical_alias_of_identical_wire"]["raw_call_path"] == index["origins"][0]["raw_call_path"]
    assert not study.native and len(study.reuse_events) == 1


def test_single_experience_banks_are_shared_controls_not_three_learning_draws(plan):
    cfg, sources = _single_actual_experience_banks(plan)
    assert len(cfg["arms"]) == 12
    frozen.check_primary_contrasts(cfg, sources)
    cfg["source_cases"] = 3
    records = {a["name"]: [
        {"source_key": str(case), "case_id": case, "family": family,
         "score": {"f1": 0.6 if a["role"] == "evolved" else 0.5}}
        for case in (1, 2, 3) for family in ("EC", "EV")]
        for a in cfg["arms"]}
    result = frozen.paired_source_statistics(cfg, records)
    assert result["sources"] == 3
    assert result["primary_family_comparisons"] == 10
    assert result["secondary_family_comparisons"] == 4
    assert result["shared_experience_predictions_not_independent_learning_repeats"]
    for contrast in ("vs_ACE", "vs_text_adaptation"):
        repeat = result["contrasts"][contrast]["per_learning_repeat"]
        assert len(repeat["before_F1_percent"]) == 1
        assert len(repeat["after_F1_percent"]) == len(repeat["difference_pp"]) == 3
        assert result["contrasts"][contrast]["endpoints"]["EV"]["difference_pp"] == pytest.approx(10)


@pytest.mark.parametrize("mutation", ["missing_amendment", "wrong_seed", "duplicated_control"])
def test_single_experience_design_rejects_missing_amendment_seed_selection_and_fake_repeats(plan, mutation):
    cfg, sources = _single_actual_experience_banks(plan)
    if mutation == "missing_amendment":
        del cfg["baseline_build_amendment"]
    elif mutation == "wrong_seed":
        sources["Text"]["generation"]["seed"] = 145
    else:
        cfg["arms"].append({"name": "ACE145", "role": "experience", "backend": "ace"})
    with pytest.raises(ValueError):
        frozen.check_primary_contrasts(cfg, sources)


@pytest.mark.parametrize("mutation", ["missing_flag", "missing_repeat", "missing_contrast",
                                     "mixed_method_group", "changed_text_policy"])
def test_expanded_primary_cannot_hide_or_mix_the_new_method(plan, mutation):
    cfg, sources = _synthetic_expanded_primary(plan)
    if mutation == "missing_flag":
        del cfg["external_text_adaptation"]
    elif mutation == "missing_repeat":
        cfg["arms"] = [a for a in cfg["arms"] if a["name"] != "Text145"]
    elif mutation == "missing_contrast":
        cfg["primary_contrasts"].pop()
    elif mutation == "mixed_method_group":
        next(c for c in cfg["primary_contrasts"] if c["name"] == "vs_ACE")["before"][0] = "Text"
    else:
        sources["Text145"]["merge_batch_size"] = 2
    with pytest.raises(ValueError):
        frozen.check_primary_contrasts(cfg, sources)


@pytest.mark.parametrize("mutation", [None, "missing_record", "changed_files", "changed_source", "failed"])
def test_text_bank_provenance_is_checked_without_opening_even_synthetic_TEST(plan, monkeypatch, mutation):
    cfg, _, root = plan
    project = Path(frozen.__file__).resolve().parents[1]
    dependencies = ("experiments/openexempt_trace2skill.py", "legal_skill_guard/learning/trace2skill_text.py")
    for name in dependencies:
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(project / name)
    RunStore.immutable_json(root / "text_protocol.md", {"synthetic": True})
    train_rows = [{"case_id": case, "source_key": f"TRAIN{case - 1}", "family": family}
                  for case in (1, 2) for family in ("EC", "EV")]
    train = root / "data/train/inputs.json"
    RunStore.atomic_json(train, {"rows": train_rows})
    train_sha = sha(train)
    selection = root / "data/train/preselection.json"
    RunStore.atomic_json(selection, {**read(selection), "input_packet_sha256": train_sha})
    cfg["training_packet_sha256"] = train_sha
    for config_path in (root / "configs").glob("*.frozen.json"):
        value = read(config_path)
        if "data/train/inputs.json" in value["files"]:
            value["files"].update({"data/train/inputs.json": train_sha,
                                    "data/train/preselection.json": sha(selection)})
            RunStore.atomic_json(config_path, value)
    text_names = []
    for seed in (45, 145, 245):
        name = "Text" + str(seed)
        text_names.append(name)
        source = copy.deepcopy(read(root / "configs/direct.json"))
        source.update(run_id="synthetic_text" + str(seed), learner="trace2skill_text_offline_v1",
                      protocol="text_protocol.md", library_token_hard_cap=8192)
        source["generation"]["seed"] = seed
        source_path = root / f"configs/text{seed}.json"
        RunStore.immutable_json(source_path, source)
        bindings = copy.deepcopy(read(root / "configs/direct.frozen.json"))
        bindings["config_sha256"] = sha(source_path)
        bindings["files"].update({dep: sha(root / dep) for dep in (*dependencies, "text_protocol.md")})
        RunStore.immutable_json(source_path.with_suffix(".frozen.json"), bindings)
        out = root / "runs" / source["run_id"]
        files = copy.deepcopy(frozen.TRACE2SKILL_INITIAL_FILES)
        RunStore.immutable_json(out / "initialization.json", {"bank": [], "patch_initial_files": files})
        RunStore.immutable_json(out / "publications/final.json", {
            "bank": [], "files": files, "files_sha256": csha(files), "library_tokens": 0})
        RunStore.immutable_json(out / "completion.json", {
            "status": "completed_trace2skill_text_offline_adaptation", "source_cases": 2,
            "final_bank": [], "final_files_sha256": csha(files),
            "actual_teacher_responses": 321, "actual_teacher_attempts": 321,
            "source_first_forecasts": {f: {"tasks": 2} for f in ("EC", "EV")},
            "final_TRAIN_replay": {f: {"tasks": 2} for f in ("EC", "EV")}})
        RunStore.immutable_json(out / "terminal_preservation.json", {"synthetic_fixture_only": True})
        for filename, stage in (("source_records.json", "source_first_forecasts"),
                                ("final_TRAIN_records.json", "final_TRAIN_replay")):
            RunStore.immutable_json(out / filename, [
                {**row, "stage": stage, "bank_sha256": csha([])} for row in train_rows])
        cfg["arms"].append({"name": name, "role": "experience", "backend": "direct",
                            "source_config": str(source_path.relative_to(root)),
                            "source_config_sha256": sha(source_path), "bank_sha256": csha([])})
    cfg["external_text_adaptation"] = "trace2skill_text_offline_v1"
    cfg["primary_contrasts"].append({"name": "vs_text", "before": text_names,
                                    "after": ["ours", "ours145", "ours245"]})
    # Only reduce the fixture to two synthetic TRAIN sources. Real 128-source
    # configs are separately checked by the actual validate_profile/freeze path.
    monkeypatch.setattr(frozen, "validate_trace2skill_profile",
                        lambda source: source["source_cases"] == 2)
    out = root / "runs/synthetic_text45"
    if mutation == "missing_record":
        path = out / "final_TRAIN_records.json"
        RunStore.atomic_json(path, read(path)[:-1])
    elif mutation == "changed_files":
        path = out / "publications/final.json"
        value = read(path)
        value["files"]["SKILL.md"] += "\nChanged fixture text.\n"
        RunStore.atomic_json(path, value)
    elif mutation == "changed_source":
        path = root / "configs/text45.frozen.json"
        value = read(path)
        value["files"][dependencies[1]] = "not-the-constructed-code"
        RunStore.atomic_json(path, value)
    elif mutation == "failed":
        path = out / "completion.json"
        RunStore.atomic_json(path, {**read(path), "status": "failed"})

    def guarded(path):
        assert Path(path) != root / cfg["input_packet"]
        return read(path)

    monkeypatch.setattr(frozen, "read", guarded)
    if mutation is None:
        banks, train_keys, _ = frozen.fixed_banks(cfg)
        assert all(name in banks for name in text_names)
        assert train_keys == {"TRAIN0", "TRAIN1"}
    else:
        with pytest.raises(ValueError):
            frozen.fixed_banks(cfg)


@pytest.mark.parametrize("mutation", ["missing", "mispaired", "policy", "budget", "teacher", "renamed"])
def test_policy_ablations_are_actual_single_seed_variants_before_TEST_load(plan, monkeypatch, mutation):
    cfg, _, root = plan
    if mutation == "missing":
        cfg["secondary_contrasts"].pop()
    elif mutation == "mispaired":
        cfg["secondary_contrasts"][0]["after"] = ["ours", "ours145", "ours245"]
    else:
        arm = next(a for a in cfg["arms"] if a["name"] == "whole_bank")
        path = root / arm["source_config"]
        source = read(path)
        if mutation == "policy":
            source["skill_commit_policy"] = "legal_scope"
        elif mutation == "budget":
            source["max_candidate_attempts"] = 1
        elif mutation == "teacher":
            source["teacher"] = {"model": "different_teacher"}
        else:
            source["run_id"] = "learn_direct"
        RunStore.atomic_json(path, source)
        frozen_path = path.with_suffix(".frozen.json")
        RunStore.atomic_json(frozen_path, {**read(frozen_path), "config_sha256": sha(path)})
        arm["source_config_sha256"] = sha(path)

    def guarded(path):
        assert path != root / cfg["input_packet"]
        return read(path)

    monkeypatch.setattr(frozen, "read", guarded)
    with pytest.raises(ValueError):
        frozen.fixed_banks(cfg)


@pytest.mark.parametrize("mutation", [None, "feedback_changed", "scope_changed", "old_first_commit",
                                      "new_attempt_cap", "unknown_design", "uniform_ok",
                                      "uniform_workers", "uniform_environment", "uniform_budget",
                                      "uniform_unmarked", "uniform_undeclared"])
def test_approved_task_local_ablation_changes_only_the_declared_granularity(plan, mutation):
    cfg, _, root = plan
    sources = {a["name"]: read(root / a["source_config"])
               for a in cfg["arms"] if a.get("source_config")}
    cfg["ablation_design"] = "legal_scope_granularity_v1"
    target = next(a for a in cfg["arms"] if a["name"] == "first_commit")
    target["name"] = "task_local"
    variant = sources.pop("first_commit")
    variant.update(ablation_variant="task_local", skill_commit_policy="task_local",
                   candidate_feedback_policy="carry_partial_and_refine")
    sources["task_local"] = variant
    for contrast in cfg["secondary_contrasts"]:
        if contrast["before"] == ["first_commit"]:
            contrast.update(name="vs_task_local", before=["task_local"])
    if mutation and mutation.startswith("uniform_"):
        cfg["learning_execution_schedule"] = frozen.runtime_sources.CONTROL_SCHEDULE
        for name in ("whole_bank", "task_local"):
            sources[name].update(
                phase_dispatch=copy.deepcopy(frozen.runtime_sources.DECLARATION),
                inference_environment="amended4.json",
                ablation_execution_schedule=frozen.runtime_sources.CONTROL_SCHEDULE,
                execution_order_addendum=frozen.runtime_sources.CONTROL_PROTOCOL)
        if mutation == "uniform_workers":
            variant["phase_dispatch"]["native_workers"] = 1
        elif mutation == "uniform_environment":
            variant["inference_environment"] = "different4.json"
        elif mutation == "uniform_budget":
            variant["generation"]["max_tokens"] = 4096
        elif mutation == "uniform_unmarked":
            del variant["ablation_execution_schedule"]
        elif mutation == "uniform_undeclared":
            del cfg["learning_execution_schedule"]
    if mutation == "feedback_changed":
        variant["candidate_feedback_policy"] = "batch_only_first_commit"
    elif mutation == "scope_changed":
        variant["skill_commit_policy"] = "legal_scope"
    elif mutation == "old_first_commit":
        variant["ablation_variant"] = "first_commit"
    elif mutation == "new_attempt_cap":
        variant["max_candidate_attempts"] = 1
    elif mutation == "unknown_design":
        cfg["ablation_design"] = "not_declared"
    if mutation in (None, "uniform_ok"):
        frozen.check_secondary_contrasts(cfg, sources)
    else:
        with pytest.raises(ValueError):
            frozen.check_secondary_contrasts(cfg, sources)


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "identity", "nonfinite", "extra_arm"])
def test_source_statistics_rejects_incomplete_or_mispaired_matrix_instead_of_dropping_cases(plan, mutation):
    cfg, _, _ = plan
    records = {arm["name"]: [{"case_id": 1, "source_key": "synthetic", "family": family,
                              "score": {"f1": 0.5}} for family in ("EC", "EV")]
               for arm in cfg["arms"]}
    if mutation == "missing":
        records["ours"].pop()
    elif mutation == "duplicate":
        records["ours"].append(copy.deepcopy(records["ours"][0]))
    elif mutation == "identity":
        records["ours"][0]["case_id"] = 2
    elif mutation == "nonfinite":
        records["ours"][0]["score"]["f1"] = float("nan")
    else:
        records["not_in_frozen_matrix"] = []
    with pytest.raises(ValueError):
        frozen.paired_source_statistics(cfg, records)


@pytest.fixture
def prospective_runtime(tmp_path, monkeypatch):
    """Only source bytes and synthetic receipts; no real case or TEST is read."""
    s = frozen.runtime_sources
    project = Path(frozen.__file__).resolve().parents[1]
    for name in (*s.CURRENT, 'legal_skill_guard/learning/runtime_sources.py', s.PROTOCOL):
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(project / name, target)
    for name, versions in s.HISTORICAL.items():
        for digest, stem in versions.items():
            path = f'{s.SNAPSHOTS}/{stem}__{digest}.py'
            target = tmp_path / path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(project / path, target)
    monkeypatch.setattr(frozen, 'ROOT', tmp_path)
    original = frozen.read
    def guarded(path):
        assert 'test' not in str(path.relative_to(tmp_path)).lower()
        return original(path)
    monkeypatch.setattr(frozen, 'read', guarded)
    return tmp_path


@pytest.mark.parametrize('name,digest', [
    (name, digest) for name, versions in frozen.runtime_sources.HISTORICAL.items()
    for digest in versions])
def test_exact_preserved_serial_sources_keep_protected_semantics(prospective_runtime, name, digest):
    s = frozen.runtime_sources
    files = s.verify_revision(prospective_runtime, name, digest)
    assert len(files) == 7 and any(digest in path.name for path in files)


@pytest.mark.parametrize('mutation', ['bundle', 'snapshot', 'unknown_hash', 'scorer', 'outside'])
def test_runtime_registry_does_not_waive_unknown_changes(prospective_runtime, mutation):
    s, root = frozen.runtime_sources, prospective_runtime
    name = 'experiments/openexempt_online.py'
    digest = next(iter(s.HISTORICAL[name]))
    if mutation == 'bundle':
        with (root / name).open('a') as stream:
            stream.write('\n# unapproved runtime change\n')
    elif mutation == 'snapshot':
        path = root / s.SNAPSHOTS / f'openexempt_online__{digest}.py'
        path.write_text('not the preserved source\n')
    elif mutation == 'unknown_hash':
        digest = '0' * 64
    elif mutation == 'scorer':
        name = 'legal_skill_guard/openexempt.py'
    else:
        name = '../experiments/openexempt_online.py'
    with pytest.raises(ValueError):
        s.verify_revision(root, name, digest)


def _synthetic_runtime_schedule(root):
    s = frozen.runtime_sources
    cfg = {'learning_execution_schedule': s.SCHEDULE,
           'learning_execution_schedule_protocol': s.PROTOCOL, 'arms': []}
    sources = {}
    for limit in (1, 4):
        RunStore.immutable_json(root / f'env{limit}.json', {
            'actual_argv': ['vllm', 'serve', 'same-frozen8b', '--max-num-seqs', str(limit)]})
    for seed in frozen.LEARNING_SEEDS:
        for method in ('main', 'ace', 'text'):
            name = f'{method}{seed}'
            source = {'run_id': name, 'source_cases': 128, 'generation': {'seed': seed},
                      'inference_environment': f'env{1 if seed == 45 else 4}.json'}
            bindings = dict(s.CURRENT)
            if seed == 45:
                bindings.update({name: next(iter(versions)) for name, versions in s.HISTORICAL.items()})
            else:
                source['phase_dispatch'] = copy.deepcopy(s.DECLARATION)
            source['learner'] = {'main': 'synthetic-main', 'ace': 'ace_native_online_v4',
                                 'text': 'trace2skill_text_offline_v1'}[method]
            bindings[source['inference_environment']] = sha(root / source['inference_environment'])
            path = root / f'configs/{name}.json'
            RunStore.immutable_json(path, source)
            RunStore.immutable_json(path.with_suffix('.frozen.json'), {'files': bindings})
            for filename in ('initialization.json', 'completion.json'):
                RunStore.immutable_json(root / f'runs/{name}/{filename}', {
                    'execution_dispatch': s.SERIAL_RECEIPT if seed == 45 else s.DECLARATION})
            cfg['arms'].append({'name': name, 'source_config': str(path.relative_to(root))})
            sources[name] = source
    return cfg, sources


def test_prospective_schedule_matches_all_methods_within_real_seed_boundary(prospective_runtime):
    cfg, sources = _synthetic_runtime_schedule(prospective_runtime)
    extras = frozen.check_learning_execution_versions(cfg, sources)
    assert prospective_runtime / frozen.runtime_sources.PROTOCOL in extras
    assert {p.name for p in extras} >= {'env1.json', 'env4.json'}


@pytest.mark.parametrize('mutation', [
    'legacy_undeclared', 'unknown_schedule', 'wrong_protocol', 'seed45_parallel',
    'repeat_serial', 'receipt', 'helper', 'environment_hash', 'within_seed_environment',
    'sequence_limit', 'model_arg'])
def test_changed_schedule_fails_before_any_case_or_TEST_access(prospective_runtime, mutation):
    root, s = prospective_runtime, frozen.runtime_sources
    cfg, sources = _synthetic_runtime_schedule(root)
    if mutation == 'legacy_undeclared':
        del cfg['learning_execution_schedule']
    elif mutation == 'unknown_schedule':
        cfg['learning_execution_schedule'] = 'not-an-approved-schedule'
    elif mutation == 'wrong_protocol':
        cfg['learning_execution_schedule_protocol'] = 'unapproved.md'
    elif mutation == 'seed45_parallel':
        sources['main45']['phase_dispatch'] = s.DECLARATION
    elif mutation == 'repeat_serial':
        del sources['ace145']['phase_dispatch']
    elif mutation == 'receipt':
        RunStore.atomic_json(root / 'runs/ace145/completion.json', {'execution_dispatch': s.SERIAL_RECEIPT})
    elif mutation == 'helper':
        path = root / 'configs/ace145.frozen.json'
        value = read(path)
        value['files']['legal_skill_guard/learning/phase_dispatch.py'] = 'unknown-version'
        RunStore.atomic_json(path, value)
    elif mutation == 'environment_hash':
        RunStore.atomic_json(root / 'env4.json', {'actual_argv': ['changed-after-learning']})
    elif mutation == 'within_seed_environment':
        shutil.copyfile(root / 'env4.json', root / 'otherenv.json')
        sources['text145']['inference_environment'] = 'otherenv.json'
        path = root / 'configs/text145.frozen.json'
        value = read(path)
        value['files']['otherenv.json'] = sha(root / 'otherenv.json')
        RunStore.atomic_json(path, value)
    else:
        path = root / 'env4.json'
        value = read(path)
        value['actual_argv'][4 if mutation == 'sequence_limit' else 2] = '2' if mutation == 'sequence_limit' else 'other-model'
        RunStore.atomic_json(path, value)
        for config in (root / 'configs').glob('*.frozen.json'):
            value = read(config)
            if 'env4.json' in value['files']:
                value['files']['env4.json'] = sha(path)
                RunStore.atomic_json(config, value)
    with pytest.raises(ValueError):
        frozen.check_learning_execution_versions(cfg, sources)


@pytest.mark.parametrize('mutation', [None, 'unmarked', 'workers', 'receipt',
                                     'old_source', 'control_environment', 'main_parallel',
                                     'evaluation_environment'])
def test_uniform_control_execution_keeps_original_banks_and_checks_both_controls(
        prospective_runtime, mutation):
    root, s = prospective_runtime, frozen.runtime_sources
    cfg, sources = _synthetic_runtime_schedule(root)
    cfg.update(learning_execution_schedule=s.CONTROL_SCHEDULE,
               learning_execution_schedule_protocol=s.CONTROL_PROTOCOL,
               evaluation_stage=frozen.INITIAL_STAGE, inference_environment='env4.json')
    cfg['arms'] = [a for a in cfg['arms'] if a['name'].endswith('45')
                   and not a['name'].endswith(('145', '245'))]
    sources = {a['name']: sources[a['name']] for a in cfg['arms']}
    for arm in cfg['arms']:
        arm['role'] = 'evolved' if arm['name'] == 'main45' else 'experience'
    protocol = root / s.CONTROL_PROTOCOL
    protocol.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(Path(frozen.__file__).resolve().parents[1] / s.CONTROL_PROTOCOL, protocol)
    for variant in ('whole_bank', 'task_local'):
        source = copy.deepcopy(sources['main45'])
        source.update(run_id=variant, ablation_variant=variant, skill_commit_policy=variant,
                      candidate_feedback_policy='carry_partial_and_refine',
                      phase_dispatch=copy.deepcopy(s.DECLARATION),
                      ablation_execution_schedule=s.CONTROL_SCHEDULE,
                      execution_order_addendum=s.CONTROL_PROTOCOL,
                      inference_environment='env4.json')
        path = root / f'configs/{variant}.json'
        RunStore.immutable_json(path, source)
        RunStore.immutable_json(path.with_suffix('.frozen.json'), {
            'files': {**s.CURRENT, 'env4.json': sha(root / 'env4.json')}})
        for filename in ('initialization.json', 'completion.json'):
            RunStore.immutable_json(root / f'runs/{variant}/{filename}', {
                'execution_dispatch': s.DECLARATION})
        sources[variant] = source
        cfg['arms'].append({'name': variant, 'role': 'ablation',
                            'source_config': str(path.relative_to(root))})
    if mutation == 'unmarked':
        del sources['task_local']['ablation_execution_schedule']
    elif mutation == 'workers':
        sources['task_local']['phase_dispatch']['native_workers'] = 1
    elif mutation == 'receipt':
        RunStore.atomic_json(root / 'runs/task_local/completion.json', {
            'execution_dispatch': s.SERIAL_RECEIPT})
    elif mutation == 'old_source':
        path = root / 'configs/task_local.frozen.json'
        value = read(path)
        value['files']['experiments/openexempt_online.py'] = next(iter(
            s.HISTORICAL['experiments/openexempt_online.py']))
        RunStore.atomic_json(path, value)
    elif mutation == 'control_environment':
        shutil.copyfile(root / 'env4.json', root / 'other4.json')
        sources['task_local']['inference_environment'] = 'other4.json'
        path = root / 'configs/task_local.frozen.json'
        value = read(path)
        value['files']['other4.json'] = sha(root / 'other4.json')
        RunStore.atomic_json(path, value)
    elif mutation == 'main_parallel':
        sources['main45']['phase_dispatch'] = s.DECLARATION
    elif mutation == 'evaluation_environment':
        cfg['inference_environment'] = 'env1.json'
    if mutation is None:
        extras = frozen.check_learning_execution_versions(cfg, sources)
        assert root / s.CONTROL_PROTOCOL in extras
    else:
        with pytest.raises(ValueError):
            frozen.check_learning_execution_versions(cfg, sources)
