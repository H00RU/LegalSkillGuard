#!/usr/bin/env python3
"""Freeze, construct, execute and summarize official paper baselines."""

from __future__ import annotations

import argparse
import errno
import fcntl
import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from legal_skill_guard.experiment.executor import ExecutionError
from legal_skill_guard.experiment.official_baselines import (
    OFFICIAL_ARM_IDS,
    OfficialBaselineController,
)
from legal_skill_guard.experiment.storage import safe_component
from legal_skill_guard.inference.codex_cli_client import CodexInvocationError

ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_CONFIRMATION = "I_CONFIRM_BASELINE_OFFICIAL_CN30"
MUTATING_COMMANDS = {
    "freeze-protocol",
    "build-luna-direct",
    "train-expel",
    "bind-ours-training",
    "run-official-arm",
}


@contextmanager
def command_lock(run_id: str, command: str) -> Iterator[None]:
    if command not in MUTATING_COMMANDS:
        yield
        return
    path = ROOT / "runs" / ".locks" / f"{safe_component(run_id)}.official-baselines.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if exc.errno not in {errno.EACCES, errno.EAGAIN}:
                raise
            raise ExecutionError(
                f"another official-baseline command already owns run {run_id!r}"
            ) from exc
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("freeze-protocol")
    build_luna = commands.add_parser("build-luna-direct")
    build_luna.add_argument(
        "--reuse-from-run-id",
        help=(
            "Reuse an exact compatible frozen Luna-Direct response cache and bind the "
            "resulting unchanged static library to this run's current protocol"
        ),
    )
    commands.add_parser("train-expel")
    bind_ours = commands.add_parser("bind-ours-training")
    bind_ours.add_argument("--training-run-id", required=True)
    official = commands.add_parser("run-official-arm")
    official.add_argument("--arm", choices=OFFICIAL_ARM_IDS, required=True)
    official.add_argument("--confirm", required=True, metavar=OFFICIAL_CONFIRMATION)
    commands.add_parser("results")
    commands.add_parser("status")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    controller = OfficialBaselineController(ROOT, args.run_id)
    try:
        with command_lock(args.run_id, args.command):
            if args.command == "freeze-protocol":
                value = controller.freeze_protocol()
            elif args.command == "build-luna-direct":
                value = controller.build_luna_direct(
                    reuse_from_run_id=args.reuse_from_run_id
                )
            elif args.command == "train-expel":
                value = controller.train_expel()
            elif args.command == "bind-ours-training":
                value = controller.bind_ours_training_source(args.training_run_id)
            elif args.command == "run-official-arm":
                if args.confirm != OFFICIAL_CONFIRMATION:
                    raise SystemExit(
                        "refusing official data access: --confirm must equal "
                        f"{OFFICIAL_CONFIRMATION}"
                    )
                value = controller.run_official_arm(args.arm)
            elif args.command == "results":
                value = controller.reveal_completed_baselines()
            else:
                value = controller.status()
            print(json.dumps(value, ensure_ascii=False, indent=2))
    except (CodexInvocationError, ExecutionError, FileExistsError, ValueError) as exc:
        raise SystemExit(f"Official baseline stage stopped safely: {exc}") from exc


if __name__ == "__main__":
    main()
