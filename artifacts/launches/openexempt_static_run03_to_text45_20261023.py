"""One exact recovered-ACE/static-TRAIN -> text45 handoff, not a general experiment queue.

Wait only; do not touch the live ACE budget, run a qualification, retry a failed
learner, read TEST, select a bank, or import another method's answers.
"""

from __future__ import annotations

import copy
import fcntl
import importlib.metadata
import json
import os
import sys
import time
import traceback
from pathlib import Path

ROOT = Path("/media/sangfor/vdb/legal-skill-evolve")
sys.path.insert(0, str(ROOT))
from experiments.openexempt_fixed_train_control import require_completed_predecessors
from experiments.openexempt_online import preserve
from experiments.openexempt_trace2skill import validate_profile
from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.learning.experiment import now, read, sha

CONFIG = ROOT / "configs/openexempt_trace2skill_text_public_assets128_seed45_20261023_run02.json"
CONFIG_SHA = "a77cbbc0e736cbad75f695f442477601dc98c014160cc3c0761d1d9f6070d892"
FROZEN_SHA = "5cce8b779d5c71be3b98af3c3f816f3c16322eeff6ddc1923be27badb16fac02"
STATIC_CONFIG = ROOT / "configs/openexempt_fixed_static_train128_20261023_run03.json"
STATIC_SHA = "61b04780c11f15a1da8b8cae3b88acc2dee5de04f9abdcc0e44155e312fc59c0"
OUT = ROOT / "artifacts/launches/openexempt_static_run03_to_text45_20261023"
MODEL_PID, MODEL_START = 3613253, "446037091"
ACE_PID, ACE_START = 2150612, "474251167"
STATIC_PID, STATIC_START = 2155494, "474269030"


def ticks(pid):
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]
    except (FileNotFoundError, ProcessLookupError):
        return None


def unchanged(cfg, frozen, script_sha):
    if (sha(CONFIG) != CONFIG_SHA or sha(CONFIG.with_suffix(".frozen.json")) != FROZEN_SHA
            or sha(STATIC_CONFIG) != STATIC_SHA or sha(Path(__file__)) != script_sha):
        raise RuntimeError("Declared handoff/profile bytes changed")
    for name, digest in frozen["files"].items():
        if sha(ROOT / name) != digest:
            raise RuntimeError("Frozen text source/data/environment changed: " + name)
    packages = {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()}
    if packages != frozen["packages"] or ticks(MODEL_PID) != MODEL_START:
        raise RuntimeError("Original control environment or single model changed")
    if (ROOT / "runs" / cfg["run_id"]).exists():
        raise FileExistsError("Text run already exists; no retry, overwrite or resume")


def terminal_receipt(run_path):
    if (run_path / "failure.json").exists():
        raise RuntimeError("A failed predecessor cannot release this handoff")
    receipt = read(run_path / "terminal_preservation.json")
    paths = receipt["paths"]
    if (len(paths) != 2 or len({Path(p["path"]).resolve() for p in paths}) != 2
            or len({Path(p["path"]).stat().st_dev for p in paths}) != 2
            or any(sha(Path(p["path"])) != p["sha256"] for p in paths)):
        raise RuntimeError("Predecessor terminal backup is incomplete or changed")


def main():
    OUT.mkdir(exist_ok=False)
    if ticks(ACE_PID) != ACE_START or ticks(STATIC_PID) != STATIC_START:
        raise RuntimeError("Queue only against the exact active ACE and original static waiter")
    cfg, frozen, static = read(CONFIG), read(CONFIG.with_suffix(".frozen.json")), read(STATIC_CONFIG)
    validate_profile(cfg)
    script_sha = sha(Path(__file__))
    unchanged(cfg, frozen, script_sha)
    ledger = ROOT / cfg["teacher"]["ledger"]
    with ledger.with_suffix(ledger.suffix + ".lock").open("a+") as budget_lock:
        fcntl.flock(budget_lock, fcntl.LOCK_EX)
        initial = read(ledger)
        if initial["max_invocations"] != 3349 or initial["model"] != cfg["teacher"]["model"]:
            raise RuntimeError("Do not alter or reset the active ACE ledger")
        RunStore.immutable_json(OUT / "ledger_at_queue_not_modified.json", initial)
    RunStore.immutable_json(OUT / "queued.json", {
        "at": now(), "target_run": cfg["run_id"], "config_sha256": CONFIG_SHA,
        "frozen_sha256": FROZEN_SHA, "script_sha256": script_sha,
        "wait_PID_start": {str(ACE_PID): ACE_START, str(STATIC_PID): STATIC_START},
        "model_PID_start": {str(MODEL_PID): MODEL_START},
        "current_ledger_unchanged": 3349, "future_terminal_only_ceiling": 3991,
        "waiting_only_not_text_training": True, "no_model_or_teacher_or_TEST_calls": True,
    })
    names = [str(p.relative_to(ROOT)) for p in OUT.glob("*.json")]
    names += [str(p.relative_to(ROOT)) for p in (Path(__file__), CONFIG, CONFIG.with_suffix(".frozen.json"))]
    RunStore.immutable_json(OUT / "queued_preservation.json", preserve(
        cfg["run_id"], "queued_after_exact_static_run03_20261023", names))
    print("Waiting for exact static TRAIN completion; text45 not started; ledger3349 unchanged", flush=True)
    while ticks(STATIC_PID) == STATIC_START:
        if ticks(MODEL_PID) != MODEL_START:
            raise RuntimeError("Original single model disappeared; no automatic model replacement")
        time.sleep(45)
    with (ROOT / "artifacts/openexempt_training.lock").open("a") as training_lock:
        fcntl.flock(training_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        unchanged(cfg, frozen, script_sha)
        require_completed_predecessors(static)
        for predecessor in cfg["required_completed_predecessors"]:
            terminal_receipt(ROOT / "runs" / predecessor)
        static_path = ROOT / "runs" / static["run_id"]
        complete = read(static_path / "completion.json")
        if (complete["status"] != "completed_frozen_static_TRAIN_control"
                or len(complete["batch_summary"]) != 8
                or complete["phase_summary"]["B1_B8"]["source_cases"] != 128
                or complete["actual_new_teacher_responses"] != 0):
            raise RuntimeError("Require actual complete fixed256 predictions, not a partial static run")
        terminal_receipt(static_path)
        RunStore.immutable_json(OUT / "predecessors_terminal_verified.json", {
            "at": now(), "static_completion_sha256": sha(static_path / "completion.json"),
            "terminal_receipt_sha256": {
                name: sha(ROOT / "runs" / name / "terminal_preservation.json")
                for name in [*cfg["required_completed_predecessors"], static["run_id"]]},
            "whole128_no_performance_threshold": True,
        })
        with ledger.with_suffix(ledger.suffix + ".lock").open("a+") as budget_lock:
            fcntl.flock(budget_lock, fcntl.LOCK_EX)
            before = read(ledger)
            if ({k: v for k, v in before.items() if k != "reservations"}
                    != {k: v for k, v in initial.items() if k != "reservations"}
                    or before["reservations"][:len(initial["reservations"])] != initial["reservations"]):
                raise RuntimeError("Original ceiling or ledger history changed")
            reserved = before.get("historical_count_lower_bound", 0) + len(before["reservations"])
            if reserved + cfg["planned_teacher_transport_attempts_max"] > 3991:
                raise RuntimeError("Insufficient declared capacity for the complete text construction")
            RunStore.immutable_json(OUT / "ledger_before_explicit_extension.json", before)
            names = [str(p.relative_to(ROOT)) for p in OUT.glob("*.json")]
            RunStore.immutable_json(OUT / "before_extension_preservation.json", preserve(
                cfg["run_id"], "before_terminal_only_text45_budget_extension_20261023", names))
            after = copy.deepcopy(before)
            after["max_invocations"] = cfg["teacher"]["total_invocation_budget"]
            if after["max_invocations"] != 3991:
                raise RuntimeError("Unexpected prospective ceiling")
            RunStore.atomic_json(ledger, after)
        RunStore.immutable_json(OUT / "starting_text45_once.json", {
            "at": now(), "target_run": cfg["run_id"], "config_sha256": CONFIG_SHA,
            "source_files": len(frozen["files"]), "shared_teacher_ceiling": 3991,
            "no_bank_or_prediction_import_no_TEST_no_extra_GPU_qualification": True,
        })
    os.chdir(ROOT)
    python = str(ROOT / ".venv/bin/python")
    os.execv(python, [python, "-u", "-m", "experiments.openexempt_trace2skill", "run", str(CONFIG)])


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        if OUT.is_dir() and not (OUT / "handoff_failed.json").exists():
            RunStore.immutable_json(OUT / "handoff_failed.json", {
                "at": now(), "error": repr(error), "traceback": traceback.format_exc(),
                "no_predecessor_stop_or_restart_no_fallback_no_retry": True,
            })
        raise
