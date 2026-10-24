"""Finite approved order: whole45, task-local45, frozen8 TEST, teacher-draft handoff.

All additional learning repeats are deferred. Their frozen scientific recipes
grant no execution authority. No TEST score selects a method, seed or bank.
"""
from __future__ import annotations

import argparse
import copy
import fcntl
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import signal
import sys
import time
import traceback

ROOT = Path("/media/sangfor/vdb/legal-skill-evolve")
sys.path.insert(0, str(ROOT))
OWNER_FILE = ROOT / "artifacts/launches/openexempt_main_only_repeats_20261024_run03.py"
OWNER_SHA = "3e7e934b0d64c403bc813d2221e478dd26e4da55d17aa9141af7d11aa80de26a"
spec = importlib.util.spec_from_file_location("preserved_current45_owner", OWNER_FILE)
owner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(owner)
phase = owner.phase
STAGES = copy.deepcopy(owner.ORIGINAL_STAGES)
OLD_FIRST = copy.deepcopy(STAGES[1])
STAGES[1] = {**OLD_FIRST, "path": "configs/openexempt_task_local_public_assets128_20261024_run01.json",
    "run_id": "legal_openexempt_task_local_public_assets128_20261024_run01",
    "config_sha256": "54bf4dbcd1a3a361cadc1d2d7a408ad7c7319ab5045abade53bb135d1320357a",
    "frozen_sha256": "31384154c55d22b57cc813544d2c3ff76fb2daac732159ac7c7020e7150a211c"}
OUT = ROOT / "artifacts/launches/openexempt_table_then_teacher_draft_20261024_run05"
RUN = "legal_openexempt_table_then_teacher_draft_20261024_run05"
PROTOCOL = "docs/research/OPENEXEMPT_MAIN_TABLE_FIRST_STAGED_REPEATS_20261024.md"
OWNER_PID, OWNER_START = 350157, "483938732"
EVAL_COMMIT = "ceff4d6d5b97f03a74249e2418ced02faed3840e"
PREPARED = ROOT / ".venv/phase-dispatch-20261023.pvio7N"
EVAL_SOURCES = {"experiments/openexempt_frozen_eval.py":
    "67419ca5942a46a7f8e6d0de88e57d2fe5d7263f66217539b7b994abeb505173",
    "tests/test_openexempt_frozen_eval.py":
    "5ce64a106d4e2c2b78c99c49d68452923ac47915f82626df15223bf077ff0c0a"}
BASE_CONFIGS = {
    "main45": "configs/openexempt_closed_feedback_public_assets128_20261021_run03.json",
    "ACE45": "configs/openexempt_ace_public_assets128_20261023_run04.json",
    "text45": "configs/openexempt_trace2skill_text_public_assets128_seed45_20261023_run02.json",
    "static": "configs/openexempt_direct_law_only_static_20261021_run03.json"}
INITIAL_CONFIG = "configs/openexempt_initial8_frozen_TEST_20261024_run01.json"
FUTURE_PLAN = str((OUT / "six_future_learning_recipes_before_initial_TEST.json").relative_to(ROOT))

phase.OUT, phase.RUN, phase.PROTOCOL = OUT, RUN, PROTOCOL
phase.COMMITS = (*phase.COMMITS, "ebfc0328c867132802850d98832e3e5924778cdf",
                 "514e819ef602282ecbd76669eb236fa095852f89", EVAL_COMMIT)
phase.old.STAGES = STAGES
owner.OUT, owner.RUN, owner.PROTOCOL = OUT, RUN, PROTOCOL
_original_profile_factory = phase.new_profile


def prospective_recipe(source, stage, environment, run_map):
    # Operational predecessor rename only; the original factory checks every
    # scientific field. No deferred recipe is executed by this controller.
    run_map = {**run_map, OLD_FIRST["run_id"]: STAGES[1]["run_id"]}
    result = _original_profile_factory(source, stage, environment, run_map)
    result["additional_learning_execution_authorization"] = "deferred_until_user_review_after_teacher_draft"
    return result


phase.new_profile = prospective_recipe


def archive(label):
    names = {str(p.relative_to(ROOT)) for p in OUT.rglob("*")
             if p.is_file() and p.name != "progress.json"}
    names.update(str(p.relative_to(ROOT)) for p in (
        Path(__file__), OWNER_FILE, owner.PHASE_FILE, phase.OLD, ROOT / PROTOCOL,
        phase.NEW_UNIT, ROOT / "ops/legal-qwen3-8b.service", ROOT / phase.OLD_ENV))
    names.update(str((PREPARED / name).relative_to(ROOT)) for name in EVAL_SOURCES)
    for value in [s["path"] for s in STAGES] + [OLD_FIRST["path"]] + list(BASE_CONFIGS.values()) + [INITIAL_CONFIG]:
        original = ROOT / value
        future = ROOT / value.replace("20261023_run02", "20261023_run03")
        for path in {original, future}:
            names.update(str(p.relative_to(ROOT)) for p in (path, path.with_suffix(".frozen.json")) if p.is_file())
    versions = ROOT / "artifacts/research/openexempt_legal_scope_20261020/source_snapshots/runtime_versions_20261023"
    names.update(str(p.relative_to(ROOT)) for p in versions.glob("*.py"))
    receipt = phase.preserve(RUN, label, sorted(names))
    if len({Path(item["path"]).stat().st_dev for item in receipt["paths"]}) != 2:
        raise RuntimeError("Require two separate preservation devices")
    phase.save(label + "_preservation", receipt)


phase.archive = owner.archive = archive


def plan():
    if (phase.sha(OWNER_FILE) != OWNER_SHA or phase.sha(owner.PHASE_FILE) != owner.PHASE_SHA
            or phase.sha(phase.OLD) != phase.OLD_SHA):
        raise RuntimeError("Keep every original orchestration source immutable")
    if (owner.state(OWNER_PID)[1] != OWNER_START
            or owner.state(owner.OLD_PID) != ("T", owner.OLD_START)
            or owner.state(owner.CHILD_PID)[1] != owner.CHILD_START
            or phase.old.ticks(phase.old.MODEL_PID) != phase.old.MODEL_START):
        raise RuntimeError("Adopt only the verified current scheduler, held owner, learner and model")
    for reader, writer in ((3, 1), (5, 2)):
        if os.readlink(f"/proc/{owner.OLD_PID}/fd/{reader}") != os.readlink(f"/proc/{owner.CHILD_PID}/fd/{writer}"):
            raise RuntimeError("The original learner output pipe identity changed")
    packages = {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()}
    if packages != phase.read(ROOT / "artifacts/launches/openexempt_main_only_repeats_20261024_run03/queued.json")["packages"]:
        raise RuntimeError("The canonical package environment changed")
    for stage in [*STAGES, OLD_FIRST]:
        path = ROOT / stage["path"]
        if phase.sha(path) != stage["config_sha256"] or phase.sha(path.with_suffix(".frozen.json")) != stage["frozen_sha256"]:
            raise RuntimeError("Never overwrite an original prospective config or freeze")
    for stage in STAGES[1:]:
        if (ROOT / "runs" / stage["run_id"]).exists():
            raise RuntimeError("Only unstarted successors can be rescheduled")
    if (ROOT / "runs" / OLD_FIRST["run_id"]).exists():
        raise RuntimeError("The superseded first-commit must be genuinely unstarted")
    for stage in STAGES[2:]:
        path = ROOT / stage["path"].replace("20261023_run02", "20261023_run03")
        if path.exists() or path.with_suffix(".frozen.json").exists():
            raise RuntimeError("Future source-rebased profiles must be genuinely uncreated")
    for name, digest in EVAL_SOURCES.items():
        if phase.sha(PREPARED / name) != digest:
            raise RuntimeError("The prepared verified staged evaluator changed")
    if (ROOT / INITIAL_CONFIG).exists():
        raise RuntimeError("Never replace a TEST config or an already launched evaluation")
    ledger = ROOT / phase.read(phase.old.FIRST)["teacher"]["ledger"]
    if phase.read(ledger)["max_invocations"] != 4023:
        raise RuntimeError("Current45 retains its actual4023 ceiling")
    sources = [Path(__file__), OWNER_FILE, owner.PHASE_FILE, phase.OLD, ROOT / PROTOCOL, phase.NEW_UNIT]
    sources += [PREPARED / name for name in EVAL_SOURCES]
    return {"controller_sources": {str(p.relative_to(ROOT)): phase.sha(p) for p in sources},
        "packages": packages, "original_model": [phase.old.MODEL_PID, phase.old.MODEL_START],
        "superseded_scheduler": [OWNER_PID, OWNER_START], "adopted_learner": [owner.CHILD_PID, owner.CHILD_START],
        "stages": STAGES, "source_promotion": list(phase.COMMITS),
        "initial_actual_conditions": 8, "prospective_final16_not_authorized_or_completed": True,
        "six_recipes_frozen_before_initial_TEST": True,
        "no_additional_independent_learning_started_by_this_queue": True,
        "second_policy_currently_declared": "task_local; user-authorized granularity control",
        "active_ceiling_unchanged": 4023, "final_live_ceiling_after_two_controls": 4055}


def adopt_current(queued):
    if (owner.state(OWNER_PID)[1] != OWNER_START
            or owner.state(owner.OLD_PID) != ("T", owner.OLD_START)
            or (ROOT / "runs" / STAGES[1]["run_id"]).exists()):
        raise RuntimeError("The exact current scheduler changed before handoff")
    os.kill(OWNER_PID, signal.SIGSTOP)
    for _ in range(50):
        if owner.state(OWNER_PID)[0] in ("T", "t"):
            break
        time.sleep(0.1)
    if owner.state(OWNER_PID)[0] not in ("T", "t"):
        raise RuntimeError("Cannot safely hold the superseded scheduler")
    if (owner.state(owner.OLD_PID) != ("T", owner.OLD_START)
            or (ROOT / "runs" / STAGES[1]["run_id"]).exists()):
        os.kill(OWNER_PID, signal.SIGCONT)
        raise RuntimeError("The boundary already advanced; preserve its actual successor and re-scope handoff")
    phase.save("current_scheduler_held_learner_and_model_uninterrupted", {
        "held_scheduler": [OWNER_PID, OWNER_START], "learner": queued["adopted_learner"],
        "model": queued["original_model"], "no_learner_or_model_signal": True})
    owner.adopt_current(queued)  # Drains exact3019419 pipes until actual child natural exit.
    if owner.state(owner.CHILD_PID)[1] == owner.CHILD_START and owner.state(owner.CHILD_PID)[0] != "Z":
        raise RuntimeError("A live learner can never be retired with an owner")
    if owner.state(OWNER_PID)[1] == OWNER_START:
        os.kill(OWNER_PID, signal.SIGKILL)
    phase.save("superseded_scheduler_retired_after_natural_learner_exit", {
        "scheduler_pid": OWNER_PID, "no_learner_or_model_signal": True})


def arm(name, role, backend, config, *, future=False):
    path = ROOT / config
    source = phase.read(path)
    value = {"name": name, "role": role, "backend": backend,
             "source_config": config, "source_config_sha256": phase.sha(path), "bank_sha256": None}
    if future:
        return value
    out = ROOT / "runs" / source["run_id"]
    publication = (out / "publication.json" if role == "static_law_only" else
        out / "publications" / ("b1.json" if role == "B1_frozen" else
            "final.json" if source.get("learner") == "trace2skill_text_offline_v1" else "b8.json"))
    bank = phase.read(publication)["playbook" if backend == "ace" else "bank"]
    from legal_skill_guard.utils.hashing import canonical_json_sha256
    value["bank_sha256"] = canonical_json_sha256(bank)
    return value


def contrasts(seeds):
    after = ["main" + str(seed) for seed in seeds]
    return [{"name": name, "after": after, "before": before} for name, before in (
        ("vs_empty", ["empty"]), ("vs_static", ["static"]),
        ("vs_own_B1", ["own_B1_" + str(seed) for seed in seeds]),
        ("vs_ACE", ["ACE" + str(seed) for seed in seeds]),
        ("vs_text", ["text" + str(seed) for seed in seeds]))]


def prepare_initial(stages, *, learning_schedule=None, learning_protocol=None,
                    evaluation_run_id="legal_openexempt_initial8_frozen_TEST_20261024_run01",
                    additional_dependencies=()):
    from legal_skill_guard.learning import runtime_sources
    recipe = phase.read(ROOT / "configs/openexempt_IID128_sealed_TEST_20261021_recipe.json")
    source = phase.read(ROOT / BASE_CONFIGS["main45"])
    initial = [{"name": "empty", "role": "strong_empty", "backend": "direct"},
        arm("static", "static_law_only", "direct", BASE_CONFIGS["static"]),
        arm("main45", "evolved", "direct", BASE_CONFIGS["main45"]),
        arm("own_B1_45", "B1_frozen", "direct", BASE_CONFIGS["main45"]),
        arm("ACE45", "experience", "ace", BASE_CONFIGS["ACE45"]),
        arm("text45", "experience", "direct", BASE_CONFIGS["text45"]),
        arm("whole_bank", "ablation", "direct", STAGES[0]["path"]),
        arm("task_local", "ablation", "direct", STAGES[1]["path"])]
    templates, entries = copy.deepcopy(initial), []
    for stage in stages:
        seed, config = stage["seed"], stage["path"]
        kind = "main" if stage["learner"] == "main" else "ace" if stage["module"].endswith("ace_online") else "text"
        name = ("ACE" if kind == "ace" else kind) + str(seed)
        templates.append(arm(name, "evolved" if kind == "main" else "experience",
                             "ace" if kind == "ace" else "direct", config, future=True))
        if kind == "main":
            templates.append(arm("own_B1_" + str(seed), "B1_frozen", "direct", config, future=True))
        entries.append({"kind": kind, "seed": seed, "source_config": config,
            "source_config_sha256": stage["config_sha256"], "source_frozen_sha256": stage["frozen_sha256"]})
    secondary = [{"name": "vs_" + name, "after": ["main45"], "before": [name]}
                 for name in ("whole_bank", "task_local")]
    future_plan = {"policy": "six_recipes_frozen_before_initial_TEST_v1", "no_TEST_feedback_to_learning": True,
        "future_builds_not_selected_using_initial_scores": True, "future_recipes_not_completed_banks": True,
        "additional_learning_execution_authorization": "deferred_until_user_review_after_teacher_draft",
        "learning": entries, "initial_arm_names": [a["name"] for a in initial],
        "planned_final_arms": templates, "primary_contrasts": contrasts((45, 145, 245)),
        "secondary_contrasts": secondary}
    phase.RunStore.immutable_json(ROOT / FUTURE_PLAN, future_plan)
    cfg = {"run_id": evaluation_run_id,
        "evaluation_role": "sealed_frozen_comparison", "evaluation_stage": "initial_single_build_descriptive",
        "final_matrix_frozen": True, "no_validation_set": True, "reference_arm": "empty",
        "execution_contract": "direct_statutory_claims", "execution_contract_version": 14,
        "library_token_hard_cap": 4096, "generation": copy.deepcopy(source["generation"]),
        "input_packet": recipe["input_packet"], "grading_directory": recipe["grading_directory"],
        "source_cases": 128, "training_source_cases": 128, "training_batch_source_cases": 16,
        "training_packet_sha256": phase.sha(ROOT / source["input_packet"]),
        "upstream_archive": source["upstream_archive"], "inference_environment": phase.ENVIRONMENT,
        "protocol": PROTOCOL, "staged_comparison_protocol": PROTOCOL,
        "statistics_plan": "docs/research/OPENEXEMPT_FINAL_ANALYSIS_TEXT_COMPLEMENT_ADDENDUM_20261022.md",
        "future_learning_plan": FUTURE_PLAN, "future_learning_plan_sha256": phase.sha(ROOT / FUTURE_PLAN),
        "external_text_adaptation": "trace2skill_text_offline_v1",
        "ablation_design": "legal_scope_granularity_v1",
        "learning_execution_schedule": learning_schedule or runtime_sources.SCHEDULE,
        "learning_execution_schedule_protocol": learning_protocol or runtime_sources.PROTOCOL,
        "inference_request_workers": 4,
        "inference_dispatch_protocol": "docs/research/OPENEXEMPT_FROZEN_EVAL_SINGLE_INSTANCE_DISPATCH_20261023.md",
        "inference_dispatch_policy": "four_workers_one_instance_exact_wire_lock_no_retry",
        "inference_dependency_artifacts": [*source["inference_dependency_artifacts"],
            str(Path(__file__).relative_to(ROOT)), "docs/research/OPENEXEMPT_FINAL_ANALYSIS_PLAN_20261021.md",
            *additional_dependencies],
        "arms": initial, "primary_contrasts": contrasts((45,)), "secondary_contrasts": secondary}
    phase.RunStore.immutable_json(ROOT / INITIAL_CONFIG, cfg)
    return cfg


def evaluation_terminal(config):
    cfg = phase.read(ROOT / config)
    out = ROOT / "runs" / cfg["run_id"]
    complete = phase.read(out / "completion.json")
    receipt = phase.read(out / "terminal_preservation.json")
    if ((out / "failure.json").exists() or complete["status"] != "completed_frozen_comparison"
            or complete["evaluation_stage"] != cfg["evaluation_stage"] or complete["teacher_calls"] != 0
            or set(complete["metrics"]) != {a["name"] for a in cfg["arms"]}
            or any(complete["metrics"][a["name"]][f]["tasks"] != 128 for a in cfg["arms"] for f in ("EC", "EV"))
            or len(receipt["paths"]) != 2
            or len({Path(p["path"]).stat().st_dev for p in receipt["paths"]}) != 2
            or any(phase.sha(Path(p["path"])) != p["sha256"] for p in receipt["paths"])):
        raise RuntimeError("Require the complete original TEST matrix and both actual terminal archives")
    return {"run_id": cfg["run_id"], "complete_and_dual_preserved": True,
            "completion_sha256": phase.sha(out / "completion.json")}


def evaluate(config):
    for action in ("freeze", "run"):
        phase.command([str(ROOT / ".venv/bin/python"), "-u", "-m", "experiments.openexempt_frozen_eval",
                       action, str(ROOT / config)])
    result = evaluation_terminal(config)
    phase.save(phase.read(ROOT / config)["run_id"] + "_complete", result)
    archive(phase.read(ROOT / config)["run_id"] + "_complete")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("inspect", "run"))
    args = parser.parse_args()
    queued = plan()
    if args.action == "inspect":
        print(json.dumps({"plan_valid": True, "two_controls_then_frozen8_then_teacher_draft": True,
            "no_independent_repeats_launched": True,
            "no_TEST_or_model_read_or_write": True, "second_policy": queued["second_policy_currently_declared"]}))
        return
    OUT.mkdir(exist_ok=False)
    phase.save("queued", queued)
    ledger = ROOT / phase.read(phase.old.FIRST)["teacher"]["ledger"]
    baseline = phase.read(ledger)
    phase.save("ledger_at_queue_unchanged", baseline)
    archive("queued")
    adopt_current(queued)
    predecessor, ceiling = ROOT / STAGES[0]["path"], 4023
    second = STAGES[1]
    with (ROOT / "artifacts/openexempt_training.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        phase.old.unchanged(second, phase.OLD_SHA, queued["packages"])
        phase.extend(ledger, baseline, ceiling, second, predecessor, queued)
    phase.command([str(ROOT / ".venv/bin/python"), "-u", "-m", second["module"], "run", str(ROOT / second["path"])])
    phase.save("second_declared45_control_complete", phase.old.terminal(ROOT / second["path"]))
    predecessor, ceiling = ROOT / second["path"], second["ceiling"]
    with (ROOT / "artifacts/openexempt_training.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        stages = phase.transition(queued)
        prepare_initial(stages)
    archive("six_recipes_and_initial8_config_before_TEST")
    evaluate(INITIAL_CONFIG)
    phase.save("necessary_experiments_complete_teacher_draft_handoff", {
        "initial8_completed_and_dual_preserved": True,
        "task_local_replaced_genuinely_unstarted_first_commit": True,
        "all_independent_repeats_deferred_not_started": True,
        "prospective_recipes_are_not_execution_authority": True,
        "paper_draft_still_requires_actual_result_and_claim_integration": True,
        "teacher_ledger_ceiling_stays": 4055})
    archive("necessary_experiments_complete_teacher_draft_handoff")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        if OUT.is_dir() and not (OUT / "handoff_failed.json").exists():
            phase.save("handoff_failed", {"error": repr(error), "traceback": traceback.format_exc(),
                "no_failed_stage_success_or_answer_repair_or_TEST_retry": True})
            archive("failed_handoff_terminal")
        raise
