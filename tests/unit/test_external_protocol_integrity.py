from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import scripts.run_main_experiment as main_cli
from legal_skill_guard.experiment.executor import (
    ExecutionError,
    MainExperimentExecutor,
    assert_locked_external_protocol_integrity,
    locked_external_protocol_integrity,
)
from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.utils.hashing import canonical_json_sha256


def _write_protocol_amendment(run_root: Path) -> Path:
    path = run_root / "reports/exploratory_protocol_amendment_round_06.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    # Malformed content is intentional: detection must not trust or need to parse
    # a run-local declaration that the frozen protocol changed.
    path.write_text("{not-valid-json", encoding="utf-8")
    return path


def test_clean_run_has_a_hash_bound_empty_protocol_amendment_set(tmp_path: Path) -> None:
    integrity = locked_external_protocol_integrity(tmp_path / "runs/clean")

    assert integrity == {
        "passed": True,
        "mode": "benchmark_aware_locked_reevaluation",
        "policy": "no_run_local_protocol_amendment_after_immutable_manifest",
        "protocol_amendment_artifacts": [],
        "protocol_amendment_set_sha256": canonical_json_sha256([]),
    }


def test_protocol_amendment_record_fails_closed_even_when_malformed(tmp_path: Path) -> None:
    run_root = tmp_path / "runs/amended"
    path = _write_protocol_amendment(run_root)

    integrity = locked_external_protocol_integrity(run_root)

    assert integrity["passed"] is False
    assert integrity["protocol_amendment_artifacts"] == [
        str(path.relative_to(run_root))
    ]
    with pytest.raises(ExecutionError, match="protocol-amendment artifact"):
        assert_locked_external_protocol_integrity(run_root)


@pytest.mark.parametrize("method_name", ["external_test", "external_seed_sensitivity"])
def test_external_stages_reject_amendment_before_run_manifest_or_data_access(
    tmp_path: Path,
    method_name: str,
) -> None:
    executor = object.__new__(MainExperimentExecutor)
    executor.store = RunStore(tmp_path / "runs", "amended")
    _write_protocol_amendment(executor.store.root)
    executor._verified_run_manifest_sha256 = lambda: pytest.fail(
        "the immutable manifest and external adapter must not be reached"
    )

    with pytest.raises(ExecutionError, match="protocol-amendment artifact"):
        getattr(MainExperimentExecutor, method_name)(executor)


def test_main_cli_rejects_amendment_before_constructing_external_executor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_id = "amended"
    _write_protocol_amendment(tmp_path / "runs" / run_id)

    def forbidden_constructor(*args: object, **kwargs: object) -> None:
        raise AssertionError("executor construction would parse the held-out external dataset")

    monkeypatch.setattr(main_cli, "ROOT", tmp_path)
    monkeypatch.setattr(main_cli, "MainExperimentExecutor", forbidden_constructor)
    args = SimpleNamespace(
        run_id=run_id,
        command="external-test",
        confirm=main_cli.TEST_CONFIRMATION,
    )

    with pytest.raises(ExecutionError, match="protocol-amendment artifact"):
        main_cli._execute_command(args)


def test_status_does_not_call_existing_mixed_protocol_report_locked_valid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_id = "amended"
    store = RunStore(tmp_path / "runs", run_id)
    external_report = store.root / "reports/external_test.json"
    external_report.parent.mkdir(parents=True)
    external_report.write_text("{}", encoding="utf-8")
    _write_protocol_amendment(store.root)

    executor = SimpleNamespace(store=store)
    monkeypatch.setattr(main_cli, "ROOT", tmp_path)
    monkeypatch.setattr(main_cli, "MainExperimentExecutor", lambda *args: executor)
    monkeypatch.setattr(main_cli, "teacher_usage_status", lambda value: {})

    main_cli._execute_command(SimpleNamespace(run_id=run_id, command="status"))
    status = json.loads(capsys.readouterr().out)

    assert status["external_test_complete"] is True
    assert status["locked_external_test_protocol_valid"] is False
    assert status["locked_external_protocol_integrity"]["passed"] is False
