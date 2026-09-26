#!/usr/bin/env python3
"""Run the fresh Ours training and one locked four-arm CN30 paper table.

The pipeline is intentionally a thin process supervisor.  Scientific decisions,
resume validation, immutable manifests and benchmark-access gates remain owned by
the two audited experiment CLIs.  ``--detach`` starts one session-independent
child whose log and stage state live outside both scientific run directories.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from legal_skill_guard.experiment.storage import safe_component

ROOT = Path(__file__).resolve().parents[1]
TRAIN_CONFIRMATION = "I_CONFIRM_MAIN_TRAINING"
OFFICIAL_CONFIRMATION = "I_CONFIRM_BASELINE_OFFICIAL_CN30"
OFFICIAL_ARMS = (
    "control_no_library",
    "luna_direct",
    "expel_adapted",
    "legal_skill_evolve",
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _pipeline_name(training_run_id: str, evaluation_run_id: str) -> str:
    return f"{safe_component(training_run_id)}__{safe_component(evaluation_run_id)}"


def _paths(training_run_id: str, evaluation_run_id: str) -> tuple[Path, Path]:
    name = _pipeline_name(training_run_id, evaluation_run_id)
    root = ROOT / "runs" / "pipeline_logs"
    return root / f"{name}.log", root / f"{name}.status.json"


def _atomic_status(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


@contextmanager
def _pipeline_lock(training_run_id: str, evaluation_run_id: str) -> Iterator[None]:
    name = _pipeline_name(training_run_id, evaluation_run_id)
    path = ROOT / "runs" / ".locks" / f"{name}.paper-pipeline.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise SystemExit(f"another paper pipeline already owns {name}") from exc
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _run_stage(
    *,
    name: str,
    command: list[str],
    status_path: Path,
    common_status: dict[str, object],
) -> None:
    started_at = _now()
    _atomic_status(
        status_path,
        {
            **common_status,
            "status": "running",
            "stage": name,
            "stage_started_at": started_at,
            "command": command,
        },
    )
    print(
        json.dumps(
            {"event": "stage_start", "stage": name, "at": started_at},
            ensure_ascii=False,
        ),
        flush=True,
    )
    completed = subprocess.run(command, cwd=ROOT, check=False)
    if completed.returncode != 0:
        failed_at = _now()
        _atomic_status(
            status_path,
            {
                **common_status,
                "status": "failed",
                "stage": name,
                "stage_started_at": started_at,
                "failed_at": failed_at,
                "returncode": completed.returncode,
                "command": command,
            },
        )
        raise SystemExit(f"paper pipeline failed at {name}: {completed.returncode}")
    print(
        json.dumps(
            {"event": "stage_complete", "stage": name, "at": _now()},
            ensure_ascii=False,
        ),
        flush=True,
    )


def _assert_fresh_run(
    run_id: str, *, allowed_top_level: frozenset[str] = frozenset()
) -> None:
    root = ROOT / "runs" / safe_component(run_id)
    if not root.exists():
        return
    unexpected = sorted(
        path.name for path in root.iterdir() if path.name not in allowed_top_level
    )
    if unexpected:
        raise SystemExit(
            "fresh pipeline refuses a run directory containing non-qualification "
            f"artifacts: root={root}, unexpected={unexpected}"
        )


def _execute(args: argparse.Namespace) -> None:
    if args.training_run_id == args.evaluation_run_id:
        raise SystemExit("training and evaluation run IDs must differ")
    if args.mode == "fresh":
        # Run-scoped qualifications and preflight response caches are
        # prerequisites, not training observations.  The scientific executor
        # independently rejects every formal training artifact under ``--fresh``.
        _assert_fresh_run(
            args.training_run_id,
            allowed_top_level=frozenset({"qualifications", "cache"}),
        )
        _assert_fresh_run(args.evaluation_run_id)
    log_path, status_path = _paths(args.training_run_id, args.evaluation_run_id)
    common_status: dict[str, object] = {
        "schema_version": 1,
        "pipeline": "fresh_ours_then_locked_four_arm_cn30",
        "training_run_id": args.training_run_id,
        "evaluation_run_id": args.evaluation_run_id,
        "luna_direct_reuse_source_run_id": args.reuse_luna_from_run_id,
        "pid": os.getpid(),
        "log_path": str(log_path.relative_to(ROOT)),
        "started_at": _now(),
    }
    python = sys.executable
    stages: list[tuple[str, list[str]]] = [
        (
            "training_preflight",
            [
                python,
                "scripts/run_main_experiment.py",
                "--run-id",
                args.training_run_id,
                "preflight",
                "--probe-codex",
            ],
        ),
        (
            "ours_training",
            [
                python,
                "scripts/run_main_experiment.py",
                "--run-id",
                args.training_run_id,
                "train",
                f"--{args.mode}",
                "--confirm",
                TRAIN_CONFIRMATION,
            ],
        ),
        (
            "main_table_freeze_protocol",
            [
                python,
                "scripts/run_official_baselines.py",
                "--run-id",
                args.evaluation_run_id,
                "freeze-protocol",
            ],
        ),
        (
            "main_table_rebind_luna_direct",
            [
                python,
                "scripts/run_official_baselines.py",
                "--run-id",
                args.evaluation_run_id,
                "build-luna-direct",
                "--reuse-from-run-id",
                args.reuse_luna_from_run_id,
            ],
        ),
        (
            "main_table_train_expel",
            [
                python,
                "scripts/run_official_baselines.py",
                "--run-id",
                args.evaluation_run_id,
                "train-expel",
            ],
        ),
        (
            "main_table_bind_ours",
            [
                python,
                "scripts/run_official_baselines.py",
                "--run-id",
                args.evaluation_run_id,
                "bind-ours-training",
                "--training-run-id",
                args.training_run_id,
            ],
        ),
    ]
    for arm in OFFICIAL_ARMS:
        stages.append(
            (
                f"main_table_arm_{arm}",
                [
                    python,
                    "scripts/run_official_baselines.py",
                    "--run-id",
                    args.evaluation_run_id,
                    "run-official-arm",
                    "--arm",
                    arm,
                    "--confirm",
                    OFFICIAL_CONFIRMATION,
                ],
            )
        )
    stages.append(
        (
            "main_table_results",
            [
                python,
                "scripts/run_official_baselines.py",
                "--run-id",
                args.evaluation_run_id,
                "results",
            ],
        )
    )
    with _pipeline_lock(args.training_run_id, args.evaluation_run_id):
        for stage_name, command in stages:
            _run_stage(
                name=stage_name,
                command=command,
                status_path=status_path,
                common_status=common_status,
            )
        _atomic_status(
            status_path,
            {
                **common_status,
                "status": "complete",
                "stage": "complete",
                "completed_at": _now(),
                "result_reports": [
                    (
                        f"runs/{args.evaluation_run_id}/reports/"
                        f"official_{arm}_aggregate.json"
                    )
                    for arm in OFFICIAL_ARMS
                ],
            },
        )


def _detach(args: argparse.Namespace) -> None:
    log_path, status_path = _paths(args.training_run_id, args.evaluation_run_id)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--training-run-id",
        args.training_run_id,
        "--evaluation-run-id",
        args.evaluation_run_id,
        "--reuse-luna-from-run-id",
        args.reuse_luna_from_run_id,
        "--mode",
        args.mode,
    ]
    with log_path.open("ab", buffering=0) as log:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
        )
    print(
        json.dumps(
            {
                "status": "detached",
                "pid": process.pid,
                "log": str(log_path.relative_to(ROOT)),
                "state": str(status_path.relative_to(ROOT)),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--training-run-id", required=True)
    parser.add_argument("--evaluation-run-id", required=True)
    parser.add_argument("--reuse-luna-from-run-id", required=True)
    parser.add_argument("--mode", choices=("fresh", "resume"), default="fresh")
    parser.add_argument(
        "--detach",
        action="store_true",
        help="Launch a session-independent child and return its PID/log paths",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    safe_component(args.training_run_id)
    safe_component(args.evaluation_run_id)
    safe_component(args.reuse_luna_from_run_id)
    if args.detach:
        _detach(args)
    else:
        _execute(args)


if __name__ == "__main__":
    main()
