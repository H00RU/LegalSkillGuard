from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from legal_skill_guard.experiment.executor import ExecutionError, MainExperimentExecutor
from legal_skill_guard.experiment.storage import (
    ImmutableArtifactConflictError,
    RunStore,
)
from legal_skill_guard.utils.hashing import canonical_json_sha256, sha256_file


def test_immutable_json_is_idempotent_but_never_replaces_content(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    RunStore.immutable_json(path, {"b": [2, 3], "a": 1})
    original_bytes = path.read_bytes()

    assert RunStore.immutable_json(path, {"a": 1, "b": [2, 3]}) == path
    assert path.read_bytes() == original_bytes

    with pytest.raises(
        ImmutableArtifactConflictError,
        match=r"existing_sha256=.*requested_sha256=",
    ):
        RunStore.immutable_json(path, {"a": 2, "b": [2, 3]})
    assert path.read_bytes() == original_bytes


def test_manifest_and_report_binding_reject_old_or_different_content(
    tmp_path: Path,
) -> None:
    store = RunStore(tmp_path / "runs", "run_01")
    manifest_path = store.write_manifest("run", {"schema_version": 1, "model": "qwen"})
    original_bytes = manifest_path.read_bytes()

    assert (
        store.write_manifest("run", {"model": "qwen", "schema_version": 1})
        == manifest_path
    )
    assert manifest_path.read_bytes() == original_bytes
    with pytest.raises(ImmutableArtifactConflictError, match="immutable JSON artifact conflict"):
        store.write_manifest("run", {"schema_version": 1, "model": "other"})

    manifest_sha256 = sha256_file(manifest_path)
    report_path = store.root / "reports" / "probe.json"
    RunStore.immutable_json(
        report_path,
        {
            "run_id": "run_01",
            "run_manifest_sha256": manifest_sha256,
            "passed": True,
        },
    )
    assert store.read_run_bound_json(
        report_path,
        run_manifest_sha256=manifest_sha256,
    )["passed"]
    with pytest.raises(ValueError, match="manifest mismatch"):
        store.read_run_bound_json(report_path, run_manifest_sha256="0" * 64)

    old_report_path = store.root / "reports" / "old_probe.json"
    RunStore.immutable_json(old_report_path, {"run_id": "run_01", "passed": True})
    with pytest.raises(ValueError, match="manifest mismatch"):
        store.read_run_bound_json(
            old_report_path,
            run_manifest_sha256=manifest_sha256,
        )


def _write(path: Path, value: str = "{}\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")
    return path


def _minimal_executor(tmp_path: Path) -> MainExperimentExecutor:
    executor = MainExperimentExecutor.__new__(MainExperimentExecutor)
    executor.root = tmp_path
    executor.run_id = "run_bound"
    executor.store = RunStore(tmp_path / "runs", executor.run_id)
    executor.experiment_path = _write(tmp_path / "configs/experiments/main.yaml")
    executor.roles_path = _write(tmp_path / "configs/models/roles.yaml")
    executor.data_path = _write(tmp_path / "configs/data/data.yaml")
    executor.training_batch_path = _write(tmp_path / "configs/data/batches.yaml")
    executor.personas_path = _write(tmp_path / "configs/data/personas.yaml")
    _write(tmp_path / "configs/prompts/prompt.txt", "frozen prompt\n")
    _write(tmp_path / "scripts/run_main_experiment.py", "# frozen entrypoint\n")
    _write(tmp_path / "legal_skill_guard/example.py", "VALUE = 1\n")
    _write(tmp_path / "skills/bootstrap/.gitkeep", "")

    lawyer_snapshot = tmp_path / "models/lawyer"
    judge_snapshot = tmp_path / "models/judge"
    for snapshot in (lawyer_snapshot, judge_snapshot):
        _write(snapshot / "config.json")
        _write(snapshot / "model.safetensors.index.json")
    lawyer_manifest = _write(tmp_path / "models/lawyer_manifest.json")
    judge_manifest = _write(tmp_path / "models/judge_manifest.json")
    _write(tmp_path / "reports/artifacts/local_judge_qualification.json")
    _write(
        executor.store.root / "qualifications/client_simulator/report.json"
    )
    _write(
        executor.store.root / "qualifications/client_simulator/binding.json"
    )
    core = _write(tmp_path / "data/core.jsonl")
    provenance = _write(tmp_path / "data/provenance.json")
    selection = _write(tmp_path / "data/selection.json")
    source_catalog = _write(tmp_path / "data/sources.json")
    quality = _write(tmp_path / "data/quality.json")
    casewise = _write(tmp_path / "data/casewise.json")
    contamination = _write(tmp_path / "data/contamination.json")
    opening_boundary = _write(tmp_path / "data/opening_boundary.json")
    external = _write(tmp_path / "data/external.jsonl")

    executor.roles = {
        "roles": {
            "lawyer_policy": {
                "local_snapshot": str(lawyer_snapshot.relative_to(tmp_path)),
                "manifest": str(lawyer_manifest.relative_to(tmp_path)),
            },
            "semantic_judge": {
                "local_snapshot": str(judge_snapshot.relative_to(tmp_path)),
                "manifest": str(judge_manifest.relative_to(tmp_path)),
            },
        }
    }
    executor.data_config = {
        "core_cases": str(core.relative_to(tmp_path)),
        "provenance": str(provenance.relative_to(tmp_path)),
        "selection_manifest": str(selection.relative_to(tmp_path)),
        "source_catalog": str(source_catalog.relative_to(tmp_path)),
        "quality_report": str(quality.relative_to(tmp_path)),
        "casewise_quality_report": str(casewise.relative_to(tmp_path)),
        "contamination_report": str(contamination.relative_to(tmp_path)),
        "opening_information_boundary_report": str(
            opening_boundary.relative_to(tmp_path)
        ),
    }
    executor.experiment = {
        "data": {"external_evaluation": str(external.relative_to(tmp_path))},
        "skill_evolution": {"initial_library": "skills/bootstrap"},
    }
    executor.training_plan = SimpleNamespace(batches=[])
    executor.local_model = "qwen"
    executor.local_revision = "frozen"
    executor.client_selector_model = "client-router"
    executor.client_selector_revision = "client-frozen"
    executor.teacher_client = SimpleNamespace(model="teacher")
    executor.judge_client = SimpleNamespace(model="judge")
    return executor


def test_run_manifest_has_stable_binding_and_rejects_reuse_after_change(
    tmp_path: Path,
) -> None:
    executor = _minimal_executor(tmp_path)
    path = executor.write_run_manifest()
    original_bytes = path.read_bytes()
    first = json.loads(original_bytes)

    assert first["schema_version"] == 3
    assert first["initial_skill_library_path"] == "skills/bootstrap"
    assert first["initial_skill_library_id"] == "bootstrap_empty"
    assert first["initial_skill_library_sha256"] == canonical_json_sha256([])
    assert len(first["binding_sha256"]) == 64
    assert executor.write_run_manifest() == path
    assert path.read_bytes() == original_bytes

    (tmp_path / "configs/prompts/prompt.txt").write_text(
        "changed prompt\n", encoding="utf-8"
    )
    with pytest.raises(ExecutionError, match="prompt_hashes"):
        executor.write_run_manifest()
    assert path.read_bytes() == original_bytes

    with pytest.raises(ExecutionError, match="run manifests are immutable"):
        executor.write_run_manifest(overwrite=True)


def test_formal_initial_library_rejects_any_legacy_contract_or_artifact(
    tmp_path: Path,
) -> None:
    executor = _minimal_executor(tmp_path)
    unexpected = tmp_path / "skills/bootstrap/legacy.json"
    unexpected.write_text("{}\n", encoding="utf-8")

    with pytest.raises(ExecutionError, match="requires an empty skills/bootstrap"):
        executor.initial_skill_library()
    unexpected.unlink()
    (tmp_path / "skills/bootstrap/legacy.yaml").write_text("invalid: true\n", encoding="utf-8")
    with pytest.raises(ValueError):
        executor.initial_skill_library()


def test_fresh_training_allows_qualification_but_rejects_formal_request_cache(
    tmp_path: Path,
) -> None:
    executor = _minimal_executor(tmp_path)
    _write(executor.store.root / "reports/preflight.json")
    _write(executor.store.root / "cache/local_judge/preflight/result.json")
    executor.assert_training_start_mode("fresh")

    formal_cache = _write(
        executor.store.root / "cache/paired_exact_requests/revision/request.json"
    )
    with pytest.raises(ExecutionError, match="--fresh requires"):
        executor.assert_training_start_mode("fresh")
    formal_cache.unlink()

    executor.write_run_manifest()
    with pytest.raises(ExecutionError, match="--fresh requires"):
        executor.assert_training_start_mode("fresh")
    executor.assert_training_start_mode("resume")


def test_resume_requires_an_existing_manifest(tmp_path: Path) -> None:
    executor = _minimal_executor(tmp_path)
    with pytest.raises(ExecutionError, match="--resume requires"):
        executor.assert_training_start_mode("resume")


def test_run_manifest_binds_component_scoped_client_qualification(
    tmp_path: Path,
) -> None:
    executor = _minimal_executor(tmp_path)
    local_root = executor.store.root / "qualifications/client_simulator"
    report = local_root / "report.json"
    binding = local_root / "binding.json"
    historical_report = _write(tmp_path / "runs/source/qualifications/client/report.json")
    historical_binding = _write(tmp_path / "runs/source/qualifications/client/binding.json")
    report.unlink()
    binding.unlink()
    evidence = tmp_path / "configs/qualification/client_simulator_evidence.yaml"
    _write(
        evidence,
        "\n".join(
            (
                "schema_version: 1",
                "status: approved_component_scoped_evidence",
                "source_run_id: source",
                "report_path: runs/source/qualifications/client/report.json",
                f"report_sha256: {sha256_file(historical_report)}",
                "binding_path: runs/source/qualifications/client/binding.json",
                f"binding_sha256: {sha256_file(historical_binding)}",
                "",
            )
        ),
    )

    manifest = json.loads(executor.write_run_manifest().read_text(encoding="utf-8"))

    assert manifest["client_qualification_path"] == (
        "runs/source/qualifications/client/report.json"
    )
    assert manifest["client_qualification_sha256"] == sha256_file(historical_report)
    assert manifest["client_qualification_binding_path"] == (
        "runs/source/qualifications/client/binding.json"
    )
