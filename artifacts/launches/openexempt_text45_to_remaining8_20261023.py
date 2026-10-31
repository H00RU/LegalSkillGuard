"""Exact remaining TRAIN plan after text45; not an experiment framework.

Every declared stage runs once, with unchanged frozen learning inputs. Natural
completion and dual preservation release the next budget extension. No TEST,
outcome-based selection, failed-run retry, service replacement or bank import.
"""
from __future__ import annotations

import copy
import fcntl
import importlib.metadata
import json
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

ROOT = Path("/media/sangfor/vdb/legal-skill-evolve")
sys.path.insert(0, str(ROOT))
from experiments.openexempt_online import preserve
from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.learning.experiment import now, read, sha

OUT = ROOT / "artifacts/launches/openexempt_text45_to_remaining8_20261023"
FIRST = ROOT / "configs/openexempt_trace2skill_text_public_assets128_seed45_20261023_run02.json"
TEXT_PID, TEXT_START = 2156118, "474271148"
MODEL_PID, MODEL_START = 3613253, "446037091"
STAGES = [
  {
    "path": "configs/openexempt_whole_bank_public_assets128_20261023_run02.json",
    "run_id": "legal_openexempt_whole_bank_public_assets128_20261023_run02",
    "learner": "main",
    "seed": 45,
    "ceiling": 4023,
    "config_sha256": "b16f826de80e6fda8523d61133fa5bfe066f27d82da6d6390ae577a8277e2c0f",
    "frozen_sha256": "388834e0f3e7f806c1fb158d009a1630b20234baddca594d5c75a169b071e88a",
    "module": "experiments.openexempt_online",
    "attempts": 32
  },
  {
    "path": "configs/openexempt_first_commit_public_assets128_20261023_run02.json",
    "run_id": "legal_openexempt_first_commit_public_assets128_20261023_run02",
    "learner": "main",
    "seed": 45,
    "ceiling": 4055,
    "config_sha256": "8a015d1bc54a48b6f6d47dd1262eed3aff7a8ad3ecb5d9f7be45ee2cb4c0eba4",
    "frozen_sha256": "f8fc840b96c574f90383c231a2647c2affd5561ff6eed4ee8416789ffbd7cfd9",
    "module": "experiments.openexempt_online",
    "attempts": 32
  },
  {
    "path": "configs/openexempt_closed_feedback_public_assets128_seed145_20261023_run02.json",
    "run_id": "legal_openexempt_closed_feedback_public_assets128_seed145_20261023_run02",
    "learner": "main",
    "seed": 145,
    "ceiling": 4087,
    "config_sha256": "9ece11c0c90fabaeef0e6829aabad8c4071b955000e5884d7608c777449f312d",
    "frozen_sha256": "24296fbe01ae86456e1022f538ff021a4cad15ac88fdb2815a98aad841b49e98",
    "module": "experiments.openexempt_online",
    "attempts": 32
  },
  {
    "path": "configs/openexempt_ace_public_assets128_seed145_20261023_run02.json",
    "run_id": "legal_openexempt_ace_public_assets128_seed145_20261023_run02",
    "learner": "ace_native_online_v4",
    "seed": 145,
    "ceiling": 5639,
    "config_sha256": "034df0ec3e4b1077229a7275a8d4e335891da5538c37fc68da813905b1bba41f",
    "frozen_sha256": "077c669323ab0504e7af25cd600d856bda17d10bad11c623bed0986ccc4fa2d6",
    "module": "experiments.openexempt_ace_online",
    "attempts": 1552
  },
  {
    "path": "configs/openexempt_closed_feedback_public_assets128_seed245_20261023_run02.json",
    "run_id": "legal_openexempt_closed_feedback_public_assets128_seed245_20261023_run02",
    "learner": "main",
    "seed": 245,
    "ceiling": 5671,
    "config_sha256": "9d67a3ba981cf2acd236c3984cb44861f151f0ea1e8c74e46baf0f8fff116803",
    "frozen_sha256": "2d15c9619a41b84aec06c94475fb2182351790bbcfdcfb871477d5c9d637ce9d",
    "module": "experiments.openexempt_online",
    "attempts": 32
  },
  {
    "path": "configs/openexempt_ace_public_assets128_seed245_20261023_run02.json",
    "run_id": "legal_openexempt_ace_public_assets128_seed245_20261023_run02",
    "learner": "ace_native_online_v4",
    "seed": 245,
    "ceiling": 7223,
    "config_sha256": "1aa2ecc6dfe8e37cb62451705219436f40b82ccf3ac3d17356836e1b32e4e888",
    "frozen_sha256": "e9501f9efff3a338bfdf2e11f7c96f49082e28b1c708a311fd53d0fac134ed48",
    "module": "experiments.openexempt_ace_online",
    "attempts": 1552
  },
  {
    "path": "configs/openexempt_trace2skill_text_public_assets128_seed145_20261023_run02.json",
    "run_id": "legal_openexempt_trace2skill_text_public_assets128_seed145_20261023_run02",
    "learner": "trace2skill_text_offline_v1",
    "seed": 145,
    "ceiling": 7865,
    "config_sha256": "7272265d9fb94c908a6bc49f4f9c2aa1f6ce37296d07c9f6fbf11ed8b56b28a2",
    "frozen_sha256": "64e0e0980f3f14fb049af62b84f6ec847bacbc0110ffb6d8e9d657f297f84802",
    "module": "experiments.openexempt_trace2skill",
    "attempts": 642
  },
  {
    "path": "configs/openexempt_trace2skill_text_public_assets128_seed245_20261023_run02.json",
    "run_id": "legal_openexempt_trace2skill_text_public_assets128_seed245_20261023_run02",
    "learner": "trace2skill_text_offline_v1",
    "seed": 245,
    "ceiling": 8507,
    "config_sha256": "0d426ff778114799dba882b52d2b5cf6d2ad5df374f14568f4668fa3e53d2811",
    "frozen_sha256": "fad526e38dd4834277d8d027a8cbd3e7ccae320db40e0f37bcb0c1fa6cdea9e3",
    "module": "experiments.openexempt_trace2skill",
    "attempts": 642
  }
]
QUEUE_RUN = "legal_openexempt_remaining8_after_text45_20261023"

def ticks(pid):
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]
    except (FileNotFoundError, ProcessLookupError):
        return None

def terminal(config):
    cfg = read(config); out = ROOT / "runs" / cfg["run_id"]
    if (out / "failure.json").exists():
        raise RuntimeError("Failed predecessor cannot release the next stage: " + cfg["run_id"])
    complete = read(out / "completion.json")
    status = complete["status"]
    if status == "completed_trace2skill_text_offline_adaptation":
        if complete["source_cases"] != 128 or complete["actual_teacher_responses"] != 321:
            raise RuntimeError("Require complete256-analyst text construction")
        if not (out / "publications/final.json").is_file():
            raise RuntimeError("Missing unique final text publication")
    elif status in ("completed_bounded_mechanism_study", "completed_declared_ACE_adaptation_stream"):
        if len(complete["batch_summary"]) != 8 or len(list((out / "publications").glob("b*.json"))) != 8:
            raise RuntimeError("Require every original batch and final publication")
    elif status != "completed_frozen_static_TRAIN_control":
        raise RuntimeError("Not a naturally completed declared predecessor")
    receipt = read(out / "terminal_preservation.json")
    paths = receipt["paths"]
    if (len(paths) != 2 or len({Path(p["path"]).stat().st_dev for p in paths}) != 2
            or any(sha(Path(p["path"])) != p["sha256"] for p in paths)):
        raise RuntimeError("Require both intact predecessor terminal archives")
    return {"run_id": cfg["run_id"], "status": status,
        "completion_sha256": sha(out / "completion.json"),
        "terminal_receipt_sha256": sha(out / "terminal_preservation.json")}

def unchanged(stage, script_sha, packages):
    path = ROOT / stage["path"]; frozen = read(path.with_suffix(".frozen.json"))
    if (sha(path) != stage["config_sha256"]
            or sha(path.with_suffix(".frozen.json")) != stage["frozen_sha256"]
            or sha(Path(__file__)) != script_sha or frozen["packages"] != packages
            or ticks(MODEL_PID) != MODEL_START):
        raise RuntimeError("Declared profile, source controller or original single8B changed")
    if any(sha(ROOT / n) != digest for n, digest in frozen["files"].items()):
        raise RuntimeError("Frozen learning source/data/environment changed")
    cfg = read(path)
    if ((ROOT / "runs" / cfg["run_id"]).exists()
            or cfg["run_id"] != stage["run_id"]
            or cfg["teacher"]["total_invocation_budget"] != stage["ceiling"]):
        raise RuntimeError("No restart, overwrite, bank selection or undeclared budget")
    return cfg

def main():
    OUT.mkdir(exist_ok=False)
    if ticks(TEXT_PID) != TEXT_START or ticks(MODEL_PID) != MODEL_START:
        raise RuntimeError("Queue only against the exact live text waiter and original8B")
    script_sha = sha(Path(__file__))
    packages = {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()}
    first = read(FIRST); ledger = ROOT / first["teacher"]["ledger"]
    for stage in STAGES:
        unchanged(stage, script_sha, packages)
    initial = read(ledger)
    if initial["max_invocations"] != 3349:
        raise RuntimeError("Do not change the active ACE teacher ceiling")
    RunStore.immutable_json(OUT / "ledger_at_queue_unchanged.json", initial)
    RunStore.immutable_json(OUT / "queued.json", {
        "at": now(), "script_sha256": script_sha, "text_PID_start": [TEXT_PID, TEXT_START],
        "original_model_PID_start": [MODEL_PID, MODEL_START], "stages": STAGES,
        "current_ceiling_unchanged": 3349, "last_declared_ceiling": 8507,
        "only_waiting_no_model_teacher_or_TEST_calls": True})
    names = [str(p.relative_to(ROOT)) for p in OUT.glob("*.json")]
    names += [str(Path(__file__).relative_to(ROOT)), str(FIRST.relative_to(ROOT))]
    names += [str(FIRST.with_suffix(".frozen.json").relative_to(ROOT))]
    names += [v for s in STAGES for v in (s["path"], str(Path(s["path"]).with_suffix(".frozen.json")))]
    RunStore.immutable_json(OUT / "queued_preservation.json", preserve(QUEUE_RUN, "queued", names))
    print("Waiting for exact text45 completion; eight later TRAIN profiles remain unstarted", flush=True)
    while ticks(TEXT_PID) == TEXT_START:
        if ticks(MODEL_PID) != MODEL_START:
            raise RuntimeError("Original model disappeared; no replacement or automatic learner retry")
        time.sleep(45)
    terminal(ROOT / "configs/openexempt_fixed_static_train128_20261023_run03.json")
    prior, ceiling = FIRST, 3991
    for index, stage in enumerate(STAGES, 1):
        prior_evidence = terminal(prior)
        with (ROOT / "artifacts/openexempt_training.lock").open("a") as training_lock:
            fcntl.flock(training_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            cfg = unchanged(stage, script_sha, packages)
            with ledger.with_suffix(ledger.suffix + ".lock").open("a+") as budget_lock:
                fcntl.flock(budget_lock, fcntl.LOCK_EX)
                before = read(ledger)
                stable = lambda d: {k: v for k, v in d.items() if k not in ("max_invocations", "reservations")}
                reserved = before.get("historical_count_lower_bound", 0) + len(before["reservations"])
                if (before["max_invocations"] != ceiling or stable(before) != stable(initial)
                        or before["reservations"][:len(initial["reservations"])] != initial["reservations"]
                        or reserved + stage["attempts"] > stage["ceiling"]
                        or stage["ceiling"] != ceiling + stage["attempts"]):
                    raise RuntimeError("Keep all ledger history and the exact prospective serial ceilings")
                RunStore.immutable_json(OUT / f"stage{index}_before_extension.json", {
                    "at": now(), "predecessor": prior_evidence, "ledger": before, "next": stage})
                names = [str(p.relative_to(ROOT)) for p in OUT.glob("*.json")]
                RunStore.immutable_json(OUT / f"stage{index}_before_extension_preservation.json",
                    preserve(QUEUE_RUN, f"stage{index}_before_extension", names))
                after = copy.deepcopy(before); after["max_invocations"] = stage["ceiling"]
                RunStore.atomic_json(ledger, after)
        RunStore.atomic_json(OUT / "progress.json", {
            "at": now(), "state": "running_declared_TRAIN_stage", "index": index,
            "run_id": stage["run_id"], "teacher_ceiling": stage["ceiling"],
            "not_TEST_or_confirmed_performance": True})
        print("Starting declared stage", index, stage["run_id"], flush=True)
        subprocess.run([str(ROOT / ".venv/bin/python"), "-u", "-m", stage["module"],
                        "run", str(ROOT / stage["path"])], cwd=ROOT, check=True)
        complete = terminal(ROOT / stage["path"])
        RunStore.immutable_json(OUT / f"stage{index}_completed.json", {"at": now(), **complete})
        prior, ceiling = ROOT / stage["path"], stage["ceiling"]
    RunStore.immutable_json(OUT / "all8_TRAIN_stages_complete_NOT_TEST.json", {
        "at": now(), "runs": [s["run_id"] for s in STAGES],
        "final_TEST_still_requires_complete_matrix_and_freeze": True})

if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        if OUT.is_dir() and not (OUT / "handoff_failed.json").exists():
            RunStore.immutable_json(OUT / "handoff_failed.json", {
                "at": now(), "error": repr(error), "traceback": traceback.format_exc(),
                "no_retry_no_fallback_no_failed_predecessor_as_complete": True})
        raise
