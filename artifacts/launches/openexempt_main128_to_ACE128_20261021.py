"""One terminal-gated Run02 -> declared ACE128 handoff, not a scheduler.

No source merge, model change, score selection, retry, TEST access or qualification
generation. An interrupted/incomplete main cannot start the successor.
"""

from __future__ import annotations

import copy
import fcntl
import hashlib
import json
import os
import sys
import tarfile
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path("/media/sangfor/vdb/legal-skill-evolve")
sys.path.insert(0, str(ROOT))
from experiments.openexempt_ace_online import validate_profile  # noqa: E402
from experiments.openexempt_online import freeze, preserve  # noqa: E402
from legal_skill_guard.experiment.storage import RunStore  # noqa: E402
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha  # noqa: E402
from legal_skill_guard.utils.hashing import sha256_file as sha  # noqa: E402

PYTHON = ROOT / ".venv/bin/python"
MAIN_ID = "legal_openexempt_closed_feedback_public_assets128_20261021_run02"
MAIN = ROOT / "runs" / MAIN_ID
MAIN_FROZEN = ROOT / "configs/openexempt_closed_feedback_public_assets128_20261021_run02.frozen.json"
MAIN_FROZEN_SHA = "1ccf0dbc19e19cdf9ee05fcebab5f737d70408c459b1d6b6327d7c81818a347e"
CONFIG = ROOT / "configs/openexempt_ace_public_assets128_20261021_run01.json"
CONFIG_SHA = "a9af3fc85c9e8395e95e37241b73ab9c392e338e51a6a02345f215371ef57c8f"
PACKET_SHA = "ef17d71b8b12f433f73d8c41afb04c506346614e69891cde66840d6daf6c7c45"
OUT = ROOT / "artifacts/launches/openexempt_main128_to_ACE128_20261021"


def read(path):
    return json.loads(path.read_text())


def now():
    return datetime.now(UTC).isoformat()


def start_ticks(pid):
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]
    except (FileNotFoundError, ProcessLookupError):
        return None


def unchanged(pins):
    if any(not (ROOT / name).is_file() or sha(ROOT / name) != digest
           for name, digest in pins.items()):
        raise RuntimeError("Declared source/data/environment changed; no automatic source transition")


def main():
    OUT.mkdir(exist_ok=False)
    if start_ticks(1047861) != "452655332" or start_ticks(3613253) != "446037091":
        raise RuntimeError("Queue only against the exact currently living main and frozen8B service")
    if sha(MAIN_FROZEN) != MAIN_FROZEN_SHA or sha(CONFIG) != CONFIG_SHA:
        raise RuntimeError("The declared main manifest or ACE profile changed")
    cfg = read(CONFIG)
    validate_profile(cfg)
    parent = read(ROOT / "configs/openexempt_closed_feedback_public_assets128_20261021_run02.json")
    if (cfg["comparison_reference_run"] != MAIN_ID or cfg["generation"] != parent["generation"]
            or cfg["teacher"]["total_invocation_budget"] != 3317
            or sha(ROOT / cfg["input_packet"]) != PACKET_SHA):
        raise RuntimeError("Keep the declared same128 stream, execution profile and prospective ceiling")
    if CONFIG.with_suffix(".frozen.json").exists() or (ROOT / "runs" / cfg["run_id"]).exists():
        raise FileExistsError("Never overwrite an existing successor freeze or run")
    extras = [Path(__file__).resolve(), CONFIG, MAIN_FROZEN, ROOT / cfg["protocol"],
              ROOT / "experiments/openexempt_ace_online.py", ROOT / "third_party/ace/LICENSE.txt",
              ROOT / "third_party/ace/NOTICE.md", *ROOT.glob("third_party/ace/**/*.py")]
    pins = dict(read(MAIN_FROZEN)["files"])
    pins.update({str(p.relative_to(ROOT)): sha(p) for p in extras})
    unchanged(pins)
    ledger = ROOT / cfg["teacher"]["ledger"]
    with ledger.with_suffix(ledger.suffix + ".lock").open("a+") as budget_lock:
        fcntl.flock(budget_lock, fcntl.LOCK_EX)
        initial = read(ledger)
        if initial["max_invocations"] != 1765 or initial["model"] != cfg["teacher"]["model"]:
            raise RuntimeError("Do not hotchange or reset the live main's teacher ledger")
        RunStore.immutable_json(OUT / "ledger_at_queue_not_modified.json", initial)
    RunStore.immutable_json(OUT / "queued.json", {
        "at": now(), "main_PID": 1047861, "main_start_ticks": "452655332",
        "model_PID": 3613253, "model_start_ticks": "446037091",
        "target_run": cfg["run_id"], "config_sha256": CONFIG_SHA,
        "source_data_environment_pins": pins, "waiting_not_successor_training": True,
        "score_independent_full128_terminal_handoff": True,
        "no_live_ledger_extension_or_successor_freeze": True,
        "no_git_source_transition_or_new_model_or_TEST": True,
    })
    queue_names = [str(p.relative_to(ROOT)) for p in OUT.glob("*.json")]
    RunStore.immutable_json(OUT / "queued_preservation.json", preserve(
        cfg["run_id"], "queued_after_main128", queue_names + [str(p.relative_to(ROOT)) for p in extras]))
    print("Waiting for the exact main128 process; ACE is not frozen or training", flush=True)
    while start_ticks(1047861) == "452655332":
        time.sleep(30)
    with (ROOT / "artifacts/openexempt_training.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        complete = read(MAIN / "completion.json")
        if (complete["status"] != "completed_bounded_mechanism_study"
                or len(complete["batch_summary"]) != 8
                or any(complete["prequential_skills"][f]["tasks"] != 128 for f in ("EC", "EV"))):
            raise RuntimeError("Main did not complete the full128/eight batches; do not start ACE")
        publication = read(MAIN / "publications/b8.json")
        if publication["bank"] != complete["bank"] or publication["bank_sha256"] != csha(complete["bank"]):
            raise RuntimeError("The actual final main publication is inconsistent")
        batches = [MAIN / f"batches/b{i}_prequential_records.json" for i in range(1, 9)]
        observed = [r for path in batches for r in read(path)["skills"]]
        expected = {(i, family) for i in range(181, 309) for family in ("EC", "EV")}
        if len(observed) != 256 or {(r["case_id"], r["family"]) for r in observed} != expected:
            raise RuntimeError("Require actual first forecasts for all128 sources, not repeated batch counts")
        terminal = read(MAIN / "terminal_preservation.json")
        archives = [Path(v["path"]) for v in terminal["paths"]]
        if (len(archives) != 2 or len({p.resolve() for p in archives}) != 2
                or len({p.stat().st_dev for p in archives}) != 2
                or any(sha(Path(v["path"])) != v["sha256"] for v in terminal["paths"])):
            raise RuntimeError("Require intact main terminal archives on two actual filesystems")
        critical = [MAIN / "completion.json", MAIN / "publications/b8.json", *batches]
        for path in archives:
            with tarfile.open(path) as archive:
                for item in critical:
                    member = archive.extractfile(str(item.relative_to(ROOT)))
                    if member is None or hashlib.sha256(member.read()).hexdigest() != sha(item):
                        raise RuntimeError("Current complete128 records differ from the terminal archive")
        unchanged(pins)
        if start_ticks(3613253) != "446037091":
            raise RuntimeError("The single frozen8B model changed or disappeared")
        if CONFIG.with_suffix(".frozen.json").exists() or (ROOT / "runs" / cfg["run_id"]).exists():
            raise FileExistsError("Successor already exists; never retry or overwrite")
        RunStore.immutable_json(OUT / "main_terminal_verified.json", {
            "at": now(), "completion_sha256": sha(MAIN / "completion.json"),
            "terminal_receipt_sha256": sha(MAIN / "terminal_preservation.json"),
            "bound_files_unchanged": len(pins), "all128_required_not_score_selected": True,
            "actual_two_archive_devices": [p.stat().st_dev for p in archives],
        })
        with ledger.with_suffix(ledger.suffix + ".lock").open("a+") as budget_lock:
            fcntl.flock(budget_lock, fcntl.LOCK_EX)
            before = read(ledger)
            if ({k: v for k, v in before.items() if k != "reservations"}
                    != {k: v for k, v in initial.items() if k != "reservations"}
                    or before["reservations"][:len(initial["reservations"])] != initial["reservations"]):
                raise RuntimeError("Teacher ledger history or original ceiling changed")
            reserved = before.get("historical_count_lower_bound", 0) + len(before["reservations"])
            if reserved + cfg["planned_teacher_transport_attempts_max"] > 3317:
                raise RuntimeError("The prospective ceiling cannot cover the declared whole ACE stream")
            RunStore.immutable_json(OUT / "ledger_before_explicit_extension.json", before)
            names = [str(p.relative_to(ROOT)) for p in OUT.glob("*.json")]
            RunStore.immutable_json(OUT / "before_extension_preservation.json", preserve(
                cfg["run_id"], "before_explicit_ACE128_budget_extension", names))
            after = copy.deepcopy(before)
            after["max_invocations"] = 3317
            RunStore.atomic_json(ledger, after)
        freeze_extras = extras + [OUT / "queued.json", OUT / "main_terminal_verified.json",
                                  OUT / "ledger_before_explicit_extension.json"]
        manifest = freeze(CONFIG, additional_sources=freeze_extras)
        RunStore.immutable_json(OUT / "starting_ACE128_once.json", {
            "at": now(), "target_run": cfg["run_id"], "config_sha256": CONFIG_SHA,
            "frozen_files": len(manifest["files"]), "teacher_ceiling": 3317,
            "historical_lower_bound_and_all_reservations_preserved": True,
            "not_three_repeats_or_finalTEST": True, "no_extra_GPU_qualification": True,
        })
    os.chdir(ROOT)
    os.execv(str(PYTHON), [str(PYTHON), "-m", "experiments.openexempt_ace_online", "run", str(CONFIG)])


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        if OUT.is_dir() and not (OUT / "handoff_failed.json").exists():
            RunStore.immutable_json(OUT / "handoff_failed.json", {
                "at": now(), "error": repr(error), "traceback": traceback.format_exc(),
                "no_main_stop_or_restart_no_fallback_no_score_overwrite": True,
            })
        raise
