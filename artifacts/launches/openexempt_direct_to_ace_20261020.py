"""One declared run handoff, not a training algorithm or a retry scheduler.

Wait for the exact direct-v13 process, preserve its terminal evidence, integrate
already-checked commits, then execute the predeclared v13 ACE comparison once.
Any failed gate leaves a receipt and stops. No model restart or score selection.
"""

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
from legal_skill_guard.experiment.storage import RunStore  # noqa: E402
from legal_skill_guard.utils.hashing import sha256_file  # noqa: E402

PYTHON = ROOT / ".venv/bin/python"
GIT = Path("/media/sangfor/vdb/legal-skill-forensics-20261015.pr9fln/git-runtime/usr/bin/git")
os.environ["GIT_EXEC_PATH"] = str(GIT.parent.parent / "lib/git-core")
OLD = ROOT / "runs/legal_openexempt_direct_skills_online_20261020_run01"
NEW_ID = "legal_openexempt_ace_TRAIN_reflect_online_20261020_run01"
CONFIG = ROOT / "configs/openexempt_ace_TRAIN_reflect_online_20261020_run01.json"
CONFIG_SHA = "3c2d0820eb140aa04c08508e65e2a214d24ffbd601c730128cb2ea02bbf779cd"
PARENT_HEAD = "83d76e6b122a3c7f525bd5ea6c46db4453910b02"
COMMITS = ("588bff4", "fa988f9", "1fbfa9e", "52ef2be", "5cc0da7", "72b6243", "5dc1a71", "7a11c65")
OUT = ROOT / "artifacts/launches/openexempt_direct_to_ace_20261020"


def read(path):
    return json.loads(path.read_text())


def now():
    return datetime.now(UTC).isoformat()


def start_ticks(pid):
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]
    except FileNotFoundError:
        return None


def git(*args):
    return subprocess.check_output([str(GIT), *args], cwd=ROOT, text=True).strip()


def main():
    OUT.mkdir(exist_ok=False)
    RunStore.immutable_json(OUT / "queued.json", {
        "at": now(), "main_pid": 338014, "main_start_ticks": "449772508",
        "target_run": NEW_ID, "config_sha256": CONFIG_SHA,
        "commits": [git("rev-parse", commit) for commit in COMMITS],
        "score_independent_complete_run_handoff": True,
        "no_hot_edit_of_active_main_or_ledger": True,
    })
    deadline = time.monotonic() + 6 * 3600
    while start_ticks(338014) == "449772508":
        if time.monotonic() > deadline:
            raise TimeoutError("Observation deadline only; did not stop/restart the live main")
        time.sleep(10)
    if start_ticks(3613253) != "446037091":
        raise RuntimeError("The single frozen model service changed or disappeared")
    with (ROOT / "artifacts/openexempt_training.lock").open("a") as training_lock:
        fcntl.flock(training_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        complete = read(OLD / "completion.json")
        if complete["status"] != "completed_bounded_mechanism_study" or len(complete["batch_summary"]) != 4:
            raise RuntimeError("Main did not complete the declared four-batch stream")
        receipt = read(OLD / "terminal_preservation.json")
        if len(receipt["paths"]) != 2:
            raise RuntimeError("Both terminal backups are required")
        for item in receipt["paths"]:
            if sha256_file(Path(item["path"])) != item["sha256"]:
                raise RuntimeError("A main terminal backup changed")
        frozen = read(ROOT / "configs/openexempt_direct_skills_online_20261020_run01.frozen.json")
        if any(sha256_file(ROOT / name) != digest for name, digest in frozen["files"].items()):
            raise RuntimeError("Main frozen bytes changed before source transition")
        if git("rev-parse", "HEAD") != PARENT_HEAD or git("status", "--porcelain", "--untracked-files=no"):
            raise RuntimeError("Main tracked source changed; preserve it and do not overwrite")
        if (ROOT / "runs" / NEW_ID).exists() or CONFIG.with_suffix(".frozen.json").exists():
            raise FileExistsError("The declared ACE Run ID or frozen profile already exists")
        RunStore.immutable_json(OUT / "main_terminal_verified.json", {
            "at": now(), "completion_sha256": sha256_file(OLD / "completion.json"),
            "terminal_receipt_sha256": sha256_file(OLD / "terminal_preservation.json"),
            "unchanged_main_bindings": len(frozen["files"]), "source_head": PARENT_HEAD,
            "model_pid_and_start_ticks_unchanged": True,
        })
        subprocess.run([str(GIT), "-c", "user.name=Codex", "-c", "user.email=codex@localhost",
                        "cherry-pick", *COMMITS], cwd=ROOT, check=True)
        if sha256_file(CONFIG) != CONFIG_SHA:
            raise RuntimeError("ACE profile differs from the previously declared config")
        ledger = ROOT / "artifacts/teacher_invocation_budget_reconstruction_20261015.json"
        with ledger.with_suffix(ledger.suffix + ".lock").open("a+") as budget_lock:
            fcntl.flock(budget_lock, fcntl.LOCK_EX)
            before = read(ledger)
            if before["max_invocations"] != 1537 or before["model"] != "gpt-5.6-sol":
                raise RuntimeError("Teacher ledger changed; never reset or guess its count")
            RunStore.immutable_json(OUT / "ledger_before_explicit_extension.json", before)
            from experiments.openexempt_online import preserve

            names = [str(p.relative_to(ROOT)) for p in OUT.glob("*.json")]
            names.append(str(Path(__file__).relative_to(ROOT)))
            backed = preserve(NEW_ID, "before_ledger_extension", names)
            RunStore.immutable_json(OUT / "before_extension_preservation.json", backed)
            after = copy.deepcopy(before)
            after["max_invocations"] = 1733
            RunStore.atomic_json(ledger, after)
            if {k: v for k, v in after.items() if k != "max_invocations"} != {
                    k: v for k, v in before.items() if k != "max_invocations"}:
                raise RuntimeError("Ledger history was not preserved")
        freeze_code = (
            "from pathlib import Path; from experiments.openexempt_online import freeze; "
            "from experiments.openexempt_ace_online import validate_profile; "
            "from legal_skill_guard.learning.experiment import read; "
            "r=Path.cwd(); c=r/'configs/openexempt_ace_TRAIN_reflect_online_20261020_run01.json'; "
            "validate_profile(read(c)); "
            "extra=[r/'experiments/openexempt_ace_online.py', *r.glob('third_party/ace/prompts/*.py'), "
            "r/'third_party/ace/LICENSE.txt', r/'third_party/ace/NOTICE.md', "
            "r/'artifacts/launches/openexempt_direct_to_ace_20261020.py']; "
            "print({'ACE_frozen_bindings':len(freeze(c,additional_sources=extra)['files'])})"
        )
        subprocess.run([str(PYTHON), "-c", freeze_code], cwd=ROOT, check=True)
        RunStore.immutable_json(OUT / "starting_declared_ACE_once.json", {
            "at": now(), "target_run": NEW_ID, "new_source_head": git("rev-parse", "HEAD"),
            "config_sha256": CONFIG_SHA, "profile_contract_version": 13,
            "optional14_and_closed_feedback_not_enabled_in_this_comparison": True,
            "teacher_ledger_limit": 1733, "historical_lower_bound_and_reservations_preserved": True,
        })
    print("Starting the declared ACE comparison; no dialogue is required", flush=True)
    os.chdir(ROOT)
    os.execv(str(PYTHON), [str(PYTHON), "-m", "experiments.openexempt_ace_online", "run", str(CONFIG)])


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        if OUT.is_dir() and not (OUT / "handoff_failed.json").exists():
            RunStore.immutable_json(OUT / "handoff_failed.json", {
                "at": now(), "error": repr(error), "traceback": traceback.format_exc(),
                "no_restart_no_fallback_no_training_score_overwrite": True,
            })
        raise
