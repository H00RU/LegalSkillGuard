"""One fixed ACE-terminal -> repaired128 handoff; no retry or model scheduler."""

from __future__ import annotations

import copy
import fcntl
import json
import os
import subprocess
import sys
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path("/media/sangfor/vdb/legal-skill-evolve")
sys.path.insert(0, str(ROOT))
from experiments.openexempt_online import preserve  # noqa: E402
from legal_skill_guard.experiment.storage import RunStore  # noqa: E402
from legal_skill_guard.utils.hashing import sha256_file  # noqa: E402

PYTHON = ROOT / ".venv/bin/python"
OLD = ROOT / "runs/legal_openexempt_ace_TRAIN_reflect_online_20261020_run01"
CONFIG = ROOT / "configs/openexempt_closed_feedback_public_assets128_20261021_run01.json"
CONFIG_SHA = "5181ce6f1d4a5efc96154a53991780ab4491681d7e69d295aecb3c19ecdd291c"
PACKET_SHA = "ef17d71b8b12f433f73d8c41afb04c506346614e69891cde66840d6daf6c7c45"
OUT = ROOT / "artifacts/launches/openexempt_ACE_to_repaired128_20261021"


def read(path):
    return json.loads(path.read_text())


def now():
    return datetime.now(UTC).isoformat()


def start_ticks(pid):
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]
    except FileNotFoundError:
        return None


def main():
    OUT.mkdir(exist_ok=False)
    cfg = read(CONFIG)
    if sha256_file(CONFIG) != CONFIG_SHA or cfg["teacher"]["total_invocation_budget"] != 1765:
        raise RuntimeError("The declared128 profile changed; do not launch a guessed replacement")
    RunStore.immutable_json(OUT / "queued.json", {
        "at": now(), "wait_for_PID": 769029, "wait_for_start_ticks": "451536081",
        "target_run": cfg["run_id"], "config_sha256": CONFIG_SHA,
        "packet_sha256": PACKET_SHA, "score_independent_successor": True,
        "initial_library": "empty, no ACE or historical bank imported",
        "no_live_ACE_source_or_ledger_change": True,
    })
    deadline = time.monotonic() + 24 * 3600
    while start_ticks(769029) == "451536081":
        if time.monotonic() > deadline:
            raise TimeoutError("Wait deadline only; did not stop or restart ACE")
        time.sleep(10)
    with (ROOT / "artifacts/openexempt_training.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        complete = read(OLD / "completion.json")
        if complete["status"] != "completed_declared_ACE_adaptation_stream" or len(complete["batch_summary"]) != 4:
            raise RuntimeError("ACE did not finish all4 declared batches; keep its failure, no bypass")
        terminal = read(OLD / "terminal_preservation.json")
        if len(terminal["paths"]) != 2 or any(
                sha256_file(Path(p["path"])) != p["sha256"] for p in terminal["paths"]):
            raise RuntimeError("Both intact ACE terminal backups are required")
        frozen = read(ROOT / "configs/openexempt_ace_TRAIN_reflect_online_20261020_run01.frozen.json")
        if any(sha256_file(ROOT / n) != h for n, h in frozen["files"].items()):
            raise RuntimeError("The completed ACE frozen source changed")
        if start_ticks(3613253) != "446037091":
            raise RuntimeError("The one frozen8B service changed or disappeared")
        if sha256_file(CONFIG) != CONFIG_SHA or sha256_file(ROOT / cfg["input_packet"]) != PACKET_SHA:
            raise RuntimeError("The fixed128 config or packet changed")
        if CONFIG.with_suffix(".frozen.json").exists() or (ROOT / "runs" / cfg["run_id"]).exists():
            raise FileExistsError("The successor run/freeze already exists; never overwrite")
        RunStore.immutable_json(OUT / "ACE_terminal_verified.json", {
            "at": now(), "ACE_completion_sha256": sha256_file(OLD / "completion.json"),
            "unchanged_ACE_bindings": len(frozen["files"]),
            "same_single_model_PID_and_start_ticks": True,
            "ACE_scores_not_used_to_pick_seed_cases_or_bank": True,
        })
        ledger = ROOT / cfg["teacher"]["ledger"]
        with ledger.with_suffix(ledger.suffix + ".lock").open("a+") as budget_lock:
            fcntl.flock(budget_lock, fcntl.LOCK_EX)
            before = read(ledger)
            if before["max_invocations"] != 1733 or before["model"] != cfg["teacher"]["model"]:
                raise RuntimeError("Teacher ledger changed; never reset historical counts")
            RunStore.immutable_json(OUT / "ledger_before_explicit_extension.json", before)
            names = [str(p.relative_to(ROOT)) for p in OUT.glob("*.json")]
            names += [str(Path(__file__).relative_to(ROOT)), str(CONFIG.relative_to(ROOT)), cfg["protocol"]]
            backed = preserve(cfg["run_id"], "before_explicit128_budget_extension", names)
            RunStore.immutable_json(OUT / "before_extension_preservation.json", backed)
            after = copy.deepcopy(before)
            after["max_invocations"] = 1765
            RunStore.atomic_json(ledger, after)
        freeze_code = (
            "from pathlib import Path; from experiments.openexempt_online import freeze; "
            f"c=Path({str(CONFIG)!r}); "
            f"print({{'new128_frozen_bindings':len(freeze(c,additional_sources=(Path({str(Path(__file__))!r}),))['files'])}})"
        )
        subprocess.run([str(PYTHON), "-c", freeze_code], cwd=ROOT, check=True)
        RunStore.immutable_json(OUT / "ready_to_exec128_once.json", {
            "at": now(), "target_run": cfg["run_id"], "config_sha256": CONFIG_SHA,
            "teacher_limit": 1765, "nominal_proposals_max": 16, "transport_attempts_max": 32,
            "all_prior_teacher_reservations_preserved": True,
            "no_extra_GPU_qualification_or_old_answer_import": True,
        })
    print("Starting the fixed repaired128 learning stream from empty memory", flush=True)
    os.chdir(ROOT)
    os.execv(str(PYTHON), [str(PYTHON), "-m", "experiments.openexempt_online", "run", str(CONFIG)])


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        if OUT.is_dir() and not (OUT / "handoff_failed.json").exists():
            RunStore.immutable_json(OUT / "handoff_failed.json", {
                "at": now(), "error": repr(error), "traceback": traceback.format_exc(),
                "no_restart_no_fallback_no_score_overwrite": True,
            })
        raise
