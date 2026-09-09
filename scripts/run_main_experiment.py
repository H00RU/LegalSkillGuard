#!/usr/bin/env python3
"""Preflight, run, resume, and freeze the LegalSkillEvolve main experiment."""

from __future__ import annotations

import argparse
import errno
import fcntl
import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from legal_skill_guard.experiment.executor import ExecutionError, MainExperimentExecutor
from legal_skill_guard.experiment.storage import safe_component
from legal_skill_guard.inference.codex_cli_client import CodexInvocationError

ROOT = Path(__file__).resolve().parents[1]
TRAIN_CONFIRMATION = "I_CONFIRM_MAIN_TRAINING"
TEST_CONFIRMATION = "I_CONFIRM_FROZEN_EXTERNAL_TEST"
SENSITIVITY_CONFIRMATION = "I_CONFIRM_SECONDARY_SEED_SENSITIVITY"
LOCKED_COMMANDS = frozenset({"train", "external-test", "seed-sensitivity"})


def teacher_usage_status(executor: MainExperimentExecutor) -> dict[str, int | float]:
    """Summarize this run's teacher artifacts and the shared hard budget separately."""

    budget_path = executor.shared_teacher_root / "luna_invocation_budget.json"
    budget = (
        json.loads(budget_path.read_text(encoding="utf-8")) if budget_path.is_file() else None
    )
    run_cache_root = executor.teacher_client.cache_root
    successful_responses = 0
    failure_artifacts = 0
    invalid_artifacts = 0
    measured_calls = 0
    estimated_credits = 0.0
    observed_reservations: set[int] = set()
    for path in run_cache_root.rglob("*.json") if run_cache_root.is_dir() else []:
        try:
            cached = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            invalid_artifacts += 1
            continue
        if not isinstance(cached, dict):
            invalid_artifacts += 1
            continue
        relative_parts = path.relative_to(run_cache_root).parts
        is_failure = "_failures" in relative_parts
        if is_failure:
            failure_artifacts += 1
            reservation = cached.get("budget_reservation") or {}
        else:
            invocation = cached.get("invocation")
            if not isinstance(invocation, dict):
                invalid_artifacts += 1
                continue
            successful_responses += 1
            reservation = invocation.get("budget_reservation") or {}
            estimate = invocation.get("estimated_luna_credits")
            if estimate is not None:
                estimated_credits += float(estimate)
                measured_calls += 1
        sequence = reservation.get("sequence") if isinstance(reservation, dict) else None
        if isinstance(sequence, int):
            observed_reservations.add(sequence)

    hard_limit = (
        int(budget["max_invocations"])
        if budget
        else int(executor.experiment["execution"]["teacher_total_invocation_budget"])
    )
    global_reserved = len(budget["reservations"]) if budget else 0
    return {
        "luna_run_successful_response_cache_entries": successful_responses,
        "luna_run_failure_artifacts": failure_artifacts,
        "luna_run_invalid_cache_artifacts": invalid_artifacts,
        "luna_run_invocations_observed": len(observed_reservations),
        "luna_run_calls_with_measured_usage": measured_calls,
        "luna_run_estimated_credits": round(estimated_credits, 6),
        "luna_global_invocations_reserved": global_reserved,
        "luna_global_invocation_hard_limit": hard_limit,
        "luna_global_invocations_available": max(hard_limit - global_reserved, 0),
    }


@contextmanager
def command_run_lock(root: Path, run_id: str, command: str) -> Iterator[None]:
    """Fail immediately when another mutating command owns the same run."""

    if command not in LOCKED_COMMANDS:
        yield
        return
    lock_path = root / "runs" / ".locks" / f"{safe_component(run_id)}.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if exc.errno not in {errno.EACCES, errno.EAGAIN}:
                raise
            raise ExecutionError(f"another experiment command already owns run {run_id!r}") from exc
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _execute_command(args: argparse.Namespace) -> None:
    executor = MainExperimentExecutor(ROOT, args.run_id)
    if args.command == "preflight":
        report = executor.preflight(probe_codex=args.probe_codex)
        print(report.model_dump_json(indent=2))
        raise SystemExit(0 if report.ready else 2)
    if args.command == "status":
        root = executor.store.root
        value = {
            "run_id": args.run_id,
            "exists": root.is_dir(),
            "trajectory_files": len(list((root / "trajectories").rglob("*.json"))),
            "evaluation_files": len(list((root / "evaluations").glob("*.json"))),
            "teacher_proposals": len(list((root / "teacher").rglob("*.json"))),
            "source_grounded_admission_reports": len(
                list((root / "reports").glob("skill_admission_round_*.json"))
            ),
            "library_maintenance_reports": len(
                list((root / "reports").glob("library_maintenance_*.json"))
            ),
            "training_complete": (root / "manifests/training_complete.json").is_file(),
            "external_test_complete": (root / "reports/external_test.json").is_file(),
            "seed_sensitivity_complete": (
                root / "reports/external_seed_sensitivity.json"
            ).is_file(),
            **teacher_usage_status(executor),
        }
        print(json.dumps(value, ensure_ascii=False, indent=2))
        return
    if args.command == "train":
        if args.confirm != TRAIN_CONFIRMATION:
            raise SystemExit(
                f"Refusing main training: --confirm must equal {TRAIN_CONFIRMATION}"
            )
        start_mode = "fresh" if args.fresh else "resume"
        executor.assert_training_start_mode(start_mode)
        report = executor.preflight(probe_codex=True)
        if not report.ready:
            print(report.model_dump_json(indent=2))
            raise SystemExit("Refusing main training because preflight did not pass")
        executor.write_run_manifest(overwrite=False)
        summary = executor.train()
        print(summary.model_dump_json(indent=2))
        return
    if args.command == "external-test":
        if args.confirm != TEST_CONFIRMATION:
            raise SystemExit(
                f"Refusing external test: --confirm must equal {TEST_CONFIRMATION}"
            )
        report = executor.preflight(probe_codex=True)
        if not report.ready:
            print(report.model_dump_json(indent=2))
            raise SystemExit("Refusing external test because preflight did not pass")
        print(json.dumps(executor.external_test(), ensure_ascii=False, indent=2))
        return
    if args.command == "seed-sensitivity":
        if args.confirm != SENSITIVITY_CONFIRMATION:
            raise SystemExit(
                "Refusing secondary sensitivity: --confirm must equal "
                f"{SENSITIVITY_CONFIRMATION}"
            )
        report = executor.preflight(probe_codex=False)
        if not report.ready:
            print(report.model_dump_json(indent=2))
            raise SystemExit("Refusing secondary sensitivity because preflight did not pass")
        print(json.dumps(executor.external_seed_sensitivity(), ensure_ascii=False, indent=2))
        return


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True, help="Stable semantic run identifier")
    commands = parser.add_subparsers(dest="command", required=True)
    preflight = commands.add_parser("preflight", help="Check data, model, endpoints and auth")
    preflight.add_argument("--probe-codex", action="store_true")
    train = commands.add_parser(
        "train", help="Start fresh or explicitly resume the training/evolution loop"
    )
    train.add_argument("--confirm", required=True, metavar=TRAIN_CONFIRMATION)
    start_mode = train.add_mutually_exclusive_group(required=True)
    start_mode.add_argument(
        "--fresh",
        action="store_true",
        help="Require this run ID to contain no formal training artifacts",
    )
    start_mode.add_argument(
        "--resume",
        action="store_true",
        help="Require and verify this run ID's immutable manifest before resuming",
    )
    external = commands.add_parser(
        "external-test",
        help="Run the frozen no-library versus evolved-library contrast on public cases",
    )
    external.add_argument("--confirm", required=True, metavar=TEST_CONFIRMATION)
    sensitivity = commands.add_parser(
        "seed-sensitivity",
        help="Run the predeclared secondary dialogue-seed robustness subset",
    )
    sensitivity.add_argument("--confirm", required=True, metavar=SENSITIVITY_CONFIRMATION)
    commands.add_parser("status", help="Show immutable run manifests and artifact counts")
    return parser.parse_args(argv)


def main() -> None:
    args = _parse_args()

    try:
        with command_run_lock(ROOT, args.run_id, args.command):
            _execute_command(args)
    except (CodexInvocationError, ExecutionError, FileExistsError, ValueError) as exc:
        raise SystemExit(f"Experiment stopped safely: {exc}") from exc


if __name__ == "__main__":
    main()
