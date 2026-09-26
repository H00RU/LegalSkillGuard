from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from legal_skill_guard.experiment.executor import ExecutionError
from scripts.run_main_experiment import (
    LOCKED_COMMANDS,
    _parse_args,
    command_run_lock,
    teacher_usage_status,
)


@pytest.mark.parametrize("command", sorted(LOCKED_COMMANDS))
def test_mutating_commands_take_a_nonblocking_same_run_lock(tmp_path: Path, command: str) -> None:
    with (
        command_run_lock(tmp_path, "same_run", command),
        pytest.raises(ExecutionError, match="already owns run"),
        command_run_lock(tmp_path, "same_run", command),
    ):
        raise AssertionError("a second same-run command must not enter")

    with command_run_lock(tmp_path, "same_run", command):
        pass


def test_run_lock_does_not_serialize_distinct_runs(tmp_path: Path) -> None:
    with (
        command_run_lock(tmp_path, "run_one", "train"),
        command_run_lock(tmp_path, "run_two", "external-test"),
    ):
        pass


@pytest.mark.parametrize("contender", ["external-test", "seed-sensitivity"])
def test_different_mutating_commands_conflict_on_the_same_run(
    tmp_path: Path, contender: str
) -> None:
    with (
        command_run_lock(tmp_path, "same_run", "train"),
        pytest.raises(ExecutionError, match="already owns run"),
        command_run_lock(tmp_path, "same_run", contender),
    ):
        raise AssertionError("all mutating commands must share one same-run lock")


def test_status_does_not_create_or_acquire_a_run_lock(tmp_path: Path) -> None:
    with command_run_lock(tmp_path, "observed_run", "status"):
        pass
    assert not (tmp_path / "runs" / ".locks").exists()


def test_status_remains_available_while_mutating_command_holds_lock(tmp_path: Path) -> None:
    with (
        command_run_lock(tmp_path, "observed_run", "train"),
        command_run_lock(tmp_path, "observed_run", "status"),
    ):
        pass


def test_teacher_status_separates_current_run_cache_from_shared_global_budget(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "runs/formal_run"
    run_cache = run_root / "cache/skill_teacher"
    success = run_cache / "skill_teacher_batch/success.json"
    success.parent.mkdir(parents=True)
    success.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "invocation": {
                    "budget_reservation": {"sequence": 4},
                    "estimated_luna_credits": 0.125,
                },
            }
        ),
        encoding="utf-8",
    )
    failure = run_cache / "_failures/skill_teacher_batch/failure.json"
    failure.parent.mkdir(parents=True)
    failure.write_text(
        json.dumps({"budget_reservation": {"sequence": 5}}),
        encoding="utf-8",
    )

    shared_root = tmp_path / "runs/main_experiment_shared"
    old_shared_response = shared_root / "codex_cache/skill_teacher_batch/old.json"
    old_shared_response.parent.mkdir(parents=True)
    old_shared_response.write_text(
        json.dumps(
            {
                "invocation": {
                    "budget_reservation": {"sequence": 1},
                    "estimated_luna_credits": 99.0,
                }
            }
        ),
        encoding="utf-8",
    )
    budget_path = shared_root / "luna_invocation_budget.json"
    budget_path.write_text(
        json.dumps(
            {
                "max_invocations": 200,
                "reservations": [{"sequence": index} for index in range(1, 6)],
            }
        ),
        encoding="utf-8",
    )
    executor = SimpleNamespace(
        store=SimpleNamespace(root=run_root),
        teacher_client=SimpleNamespace(cache_root=run_cache),
        shared_teacher_root=shared_root,
        experiment={"execution": {"teacher_total_invocation_budget": 200}},
    )

    assert teacher_usage_status(executor) == {
        "luna_run_successful_response_cache_entries": 1,
        "luna_run_failure_artifacts": 1,
        "luna_run_invalid_cache_artifacts": 0,
        "luna_run_invocations_observed": 2,
        "luna_run_calls_with_measured_usage": 1,
        "luna_run_estimated_credits": 0.125,
        "luna_global_invocations_reserved": 5,
        "luna_global_invocation_hard_limit": 200,
        "luna_global_invocations_available": 195,
    }


@pytest.mark.parametrize("mode", ["--fresh", "--resume"])
def test_train_requires_one_explicit_start_mode(mode: str) -> None:
    args = _parse_args(
        [
            "--run-id",
            "formal_run",
            "train",
            mode,
            "--confirm",
            "I_CONFIRM_MAIN_TRAINING",
        ]
    )
    assert args.fresh is (mode == "--fresh")
    assert args.resume is (mode == "--resume")


def test_train_rejects_missing_or_ambiguous_start_mode() -> None:
    common = [
        "--run-id",
        "formal_run",
        "train",
        "--confirm",
        "I_CONFIRM_MAIN_TRAINING",
    ]
    with pytest.raises(SystemExit):
        _parse_args(common)
    with pytest.raises(SystemExit):
        _parse_args([*common, "--fresh", "--resume"])
