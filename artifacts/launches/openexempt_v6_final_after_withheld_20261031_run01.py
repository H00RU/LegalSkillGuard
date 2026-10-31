"""One bounded operational handoff: completed v6 control -> original frozen TEST CLI.

Never learns, edits a bank, chooses by score, retries an answer, or opens TEST
questions itself. The final configuration is generated only from actual terminal
sources. Existing source closure, matrix freeze, inference and scoring are reused.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
import traceback
from pathlib import Path

from experiments.openexempt_frozen_eval import (
    DISPATCH_PROTOCOL, UTILITY_SOURCE_DISJOINT_ARMS, UTILITY_SOURCE_DISJOINT_PACKET,
    UTILITY_SOURCE_DISJOINT_PACKET_SHA256, UTILITY_SOURCE_DISJOINT_PROTOCOL,
    UTILITY_SOURCE_DISJOINT_STAGE, ace_common_direct_bank, check_source_disjoint_plan,
)
from experiments.openexempt_online import ROOT, csha, now, preserve, read, sha
from legal_skill_guard.experiment.storage import RunStore

NAME = "openexempt_v6_final_after_withheld_20261031_run01"
OUT = ROOT / "artifacts/launches" / NAME
SCRIPT = Path(__file__).resolve()
CONTROL_PID, CONTROL_BIRTH = 1380034, "539695557"
MODEL_PID, MODEL_BIRTH = 958223, "486445918"
CONTROL_CONFIG = "configs/openexempt_v6_teacher_execution_withheld_public_assets128_20261030_run01.json"
MAIN_CONFIG = "configs/openexempt_complete_output_utility_public_assets128_20261030_run01.json"
TEST_RUN = "legal_openexempt_v6_frozen_source_isolated_IID128_20261031_run01"
MATRIX = OUT / "actual_final_matrix_config.json"
ACE_WRAPPER = ("artifacts/research/openexempt_legal_scope_20261020/"
               "ACE_actual_final_playbook_lossless_common_direct_wrapper_20261027.json")
SNAPSHOTS = ("artifacts/research/openexempt_legal_scope_20261020/"
             "source_snapshots/utility_eval_20261030")


def original_live(pid, birth):
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
    except FileNotFoundError:
        return False
    return fields[19] == birth and fields[0] not in ("Z", "X")


def completed_arm(name):
    role, backend, source_config = UTILITY_SOURCE_DISJOINT_ARMS[name]
    arm = {"name": name, "role": role, "backend": backend}
    if name == "empty":
        return arm
    config = ROOT / source_config
    source = read(config)
    frozen = config.with_suffix(".frozen.json")
    manifest = read(frozen)
    run = ROOT / "runs" / source["run_id"]
    if (run / "failure.json").exists():
        raise ValueError("Failed construction cannot enter final matrix: " + name)
    complete, terminal = run / "completion.json", run / "terminal_preservation.json"
    if not complete.is_file() or not terminal.is_file():
        raise ValueError("No actual terminal source for " + name)
    publication = run / ("publication.json" if name == "static" else
                         "publications/final.json" if name == "text45" else
                         "publications/b1.json" if role == "B1_frozen" else "publications/b8.json")
    pub = read(publication)
    bank = pub["playbook"] if name in {"ACE45", "ACE_common45"} else pub["bank"]
    arm.update(source_config=source_config, source_config_sha256=sha(config),
               source_frozen_sha256=sha(frozen), source_completion_sha256=sha(complete),
               source_publication_sha256=sha(publication),
               source_terminal_preservation_sha256=sha(terminal))
    if name == "ACE_common45":
        wrapped = read(ROOT / ACE_WRAPPER)
        if wrapped != ace_common_direct_bank(bank):
            raise ValueError("The common ACE representation must be lossless")
        bank = wrapped
        arm.update(representation_artifact=ACE_WRAPPER,
                   representation_sha256=sha(ROOT / ACE_WRAPPER))
    if name in {"utility45", "utility_own_B1_45", "strict45", "no_execution45", "projection45"}:
        digest = manifest["files"]["experiments/openexempt_online.py"]
        snapshot = f"{SNAPSHOTS}/openexempt_online__{digest}.py"
        if sha(ROOT / snapshot) != digest:
            raise ValueError("Missing the actual learner source snapshot: " + name)
        arm.update(source_snapshot=snapshot, source_snapshot_sha256=digest)
    arm["bank_sha256"] = csha(bank)
    return arm


def prepare():
    # No final config, TEST packet parsing, inference or future bank placeholder.
    known = {n: completed_arm(n) for n in UTILITY_SOURCE_DISJOINT_ARMS if n != "no_execution45"}
    files = {SCRIPT, ROOT / "experiments/openexempt_frozen_eval.py",
             ROOT / UTILITY_SOURCE_DISJOINT_PROTOCOL, ROOT / DISPATCH_PROTOCOL,
             ROOT / MAIN_CONFIG, ROOT / CONTROL_CONFIG,
             (ROOT / CONTROL_CONFIG).with_suffix(".frozen.json")}
    for arm in known.values():
        if arm["name"] == "empty":
            continue
        config = ROOT / arm["source_config"]
        run = ROOT / "runs" / read(config)["run_id"]
        files.update((config, config.with_suffix(".frozen.json"), run / "completion.json",
                      run / "terminal_preservation.json"))
        pub = "publication.json" if arm["name"] == "static" else "publications/final.json" if arm["name"] == "text45" else "publications/b1.json" if arm["role"] == "B1_frozen" else "publications/b8.json"
        files.add(run / pub)
        for key in ("representation_artifact", "source_snapshot"):
            if key in arm:
                files.add(ROOT / arm[key])
    value = {"at": now(), "classification": "operational_handoff_only_no_TEST_opened_or_final_matrix_yet",
             "bindings": {str(p.relative_to(ROOT)): sha(p) for p in sorted(files)},
             "known_completed_conditions": known,
             "pending_actual_control_config": CONTROL_CONFIG,
             "control_pid": CONTROL_PID, "control_birth": CONTROL_BIRTH,
             "original_model_pid": MODEL_PID, "original_model_birth": MODEL_BIRTH,
             "final_test_run_id": TEST_RUN,
             "all_ten_conditions_and_eighteen_endpoints_unchanged": True,
             "no_score_or_best_checkpoint_selection": True,
             "no_extra_independent_learning_repeats": True}
    RunStore.immutable_json(OUT / "intent.json", value)
    receipt = preserve(NAME, "intent", [*value["bindings"], str((OUT / "intent.json").relative_to(ROOT))])
    RunStore.immutable_json(OUT / "intent_preservation.json", receipt)
    print({"status": "prepared_wait_for_actual_control_completion", "known_conditions": len(known)}, flush=True)


def build_matrix(intent):
    arms = [completed_arm(n) for n in UTILITY_SOURCE_DISJOINT_ARMS]
    if {a["name"]: a for a in arms if a["name"] != "no_execution45"} != intent["known_completed_conditions"]:
        raise ValueError("An already-completed comparator or main source changed")
    main = read(ROOT / MAIN_CONFIG)
    cfg = {"run_id": TEST_RUN, "evaluation_stage": UTILITY_SOURCE_DISJOINT_STAGE,
           "protocol": UTILITY_SOURCE_DISJOINT_PROTOCOL, "statistics_plan": UTILITY_SOURCE_DISJOINT_PROTOCOL,
           "evaluation_role": "sealed_frozen_comparison", "final_matrix_frozen": True,
           "no_validation_set": True, "benchmark_development_status": "source_disjoint_IID_frozen_bank_confirmation",
           "independent_learning_repetitions": "user_deferred", "external_text_adaptation": "trace2skill_text_offline_v1",
           "reference_arm": "empty", "execution_contract": "direct_statutory_claims", "execution_contract_version": 14,
           "library_token_hard_cap": 4096, "input_packet": UTILITY_SOURCE_DISJOINT_PACKET + "/inputs.json",
           "grading_directory": UTILITY_SOURCE_DISJOINT_PACKET + "/grading_only",
           "input_packet_sha256": UTILITY_SOURCE_DISJOINT_PACKET_SHA256,
           "training_packet_sha256": sha(ROOT / main["input_packet"]),
           "source_cases": 128, "training_source_cases": 128, "training_batch_source_cases": 16,
           "generation": main["generation"], "inference_request_workers": 4,
           "inference_dispatch_protocol": DISPATCH_PROTOCOL,
           "inference_dispatch_policy": "four_workers_one_instance_exact_wire_lock_no_retry",
           "inference_environment": main["inference_environment"], "upstream_archive": main["upstream_archive"],
           "inference_dependency_artifacts": [*main["inference_dependency_artifacts"],
                str(SCRIPT.relative_to(ROOT)), str((OUT / "intent.json").relative_to(ROOT))],
           "arms": arms, "primary_contrasts": [{"name": "vs_" + n, "after": ["utility45"], "before": [n]}
                for n in UTILITY_SOURCE_DISJOINT_ARMS if n != "utility45"], "secondary_contrasts": []}
    check_source_disjoint_plan(cfg)  # Metadata only. Original freeze closes all real sources next.
    RunStore.immutable_json(MATRIX, cfg)
    return cfg


def run():
    intent = read(OUT / "intent.json")
    for name, digest in intent["bindings"].items():
        if sha(ROOT / name) != digest:
            raise ValueError("The predeclared operational handoff changed: " + name)
    source = read(ROOT / CONTROL_CONFIG)
    control = ROOT / "runs" / source["run_id"]
    RunStore.immutable_json(OUT / "started.json", {"at": now(), "stage": "wait_for_original_live_control", "TEST_opened": False})
    try:
        while True:
            if (control / "failure.json").exists():
                raise ValueError("Required control failed; preserve it, never start TEST or retry automatically")
            if not original_live(CONTROL_PID, CONTROL_BIRTH):
                if not (control / "completion.json").is_file() or not (control / "terminal_preservation.json").is_file():
                    raise ValueError("Original control stopped without a complete preserved terminal")
                break
            time.sleep(20)
        done = read(control / "completion.json")
        if (done["status"] != "completed_bounded_mechanism_study" or len(done["batch_summary"]) != 8
                or done.get("actual_teacher_responses") != 16):
            raise ValueError("Require actual complete eight-batch control, not a performance-selected prefix")
        receipt = read(control / "terminal_preservation.json")
        if len(receipt["paths"]) != 2:
            raise ValueError("Required control needs both real terminal archives")
        for item in receipt["paths"]:
            if sha(Path(item["path"])) != item["sha256"]:
                raise ValueError("A required control terminal archive changed")
        for name, digest in intent["bindings"].items():
            if sha(ROOT / name) != digest:
                raise ValueError("A bound source changed during the control")
        if not original_live(MODEL_PID, MODEL_BIRTH):
            raise ValueError("Original8B identity changed; no automatic reload or TEST restart")
        build_matrix(intent)
        for action in ("freeze", "run"):
            subprocess.run([sys.executable, "-u", "-m", "experiments.openexempt_frozen_eval", action,
                            str(MATRIX.relative_to(ROOT))], cwd=ROOT, check=True)
        test = ROOT / "runs" / TEST_RUN
        result = read(test / "completion.json")
        if result["status"] != "completed_frozen_comparison" or len(read(test / "terminal_preservation.json")["paths"]) != 2:
            raise ValueError("Final evaluation did not finish and preserve normally")
        RunStore.immutable_json(OUT / "completion.json", {"at": now(), "status": "completed_original_frozen_comparison",
            "actual_test_completion": str((test / "completion.json").relative_to(ROOT)),
            "actual_test_completion_sha256": sha(test / "completion.json"), "no_score_selected_branch": True})
    except BaseException as exc:
        RunStore.immutable_json(OUT / "failure.json", {"at": now(), "error": repr(exc),
            "traceback": traceback.format_exc(), "no_auto_retry_or_selected_TEST_answer": True})
        raise
    finally:
        files = [str(p.relative_to(ROOT)) for p in OUT.glob("*.json") if p.name != "terminal_preservation.json"]
        RunStore.immutable_json(OUT / "terminal_preservation.json", preserve(NAME, "actual-terminal", files))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "run"))
    {"prepare": prepare, "run": run}[parser.parse_args().action]()
