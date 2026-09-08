from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from legal_skill_guard.experiment.executor import (
    ExecutionError,
    MainExperimentExecutor,
    _role_assignment_status_check,
    _same_string_multiset,
    skill_library_sha256,
)
from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.schemas.experiment import ResearchTrajectory
from legal_skill_guard.utils.hashing import canonical_json_sha256, sha256_file


def test_role_assignment_status_is_an_explicit_preflight_contract() -> None:
    expected = "static_role_assignment_frozen_gpu_requalification_required"
    assert _role_assignment_status_check({"status": expected}) == {
        "value": expected,
        "passed": True,
    }


def test_artifact_membership_is_order_independent_but_duplicate_sensitive() -> None:
    assert _same_string_multiset(["candidate_b", "candidate_a"], ["candidate_a", "candidate_b"])
    assert not _same_string_multiset(
        ["candidate_a", "candidate_a"], ["candidate_a", "candidate_b"]
    )
    assert not _same_string_multiset("candidate_a", ["candidate_a"])
    assert _role_assignment_status_check({"status": "legacy_ready"}) == {
        "value": "legacy_ready",
        "passed": False,
    }


def _freeze_executor(tmp_path: Path, run_id: str) -> MainExperimentExecutor:
    executor = object.__new__(MainExperimentExecutor)
    executor.root = tmp_path
    executor.run_id = run_id
    executor.store = RunStore(tmp_path / "runs", run_id)
    executor.candidate_root = executor.store.root / "skills/candidates"
    executor.judge_qualification_contract_sha256 = "a" * 64
    executor.local_model = "model/test"
    executor.local_revision = "revision-1"
    executor.experiment = {
        "execution": {
            "evolution_rounds": 1,
            "provisional_candidate_budget_per_block": 1,
        },
        "personas": ["P_WD"],
        "trajectory_sampling": {
            "group_size": 1,
            "training_group_seeds": [42],
        },
    }
    executor.training_plan = SimpleNamespace(
        batches=[
            SimpleNamespace(
                batch_id="training_batch_01",
                prospective_validation_for=None,
                case_ids=["case_test"],
                persona_assignment={"case_test": "P_WD"},
            )
        ]
    )
    executor.registry = SimpleNamespace(current=lambda: None)
    executor.active_skills = lambda: []
    executor._validate_learning_curve_point_artifact = lambda **_: {
        "identity_baseline": True
    }
    return executor


def _write_run_manifest(executor: MainExperimentExecutor) -> str:
    executor.store.write_manifest("run", {"schema_version": 2, "run_id": executor.run_id})
    return sha256_file(executor.store.root / "manifests/run.json")


def _freeze_provisionals_ready(
    executor: MainExperimentExecutor,
    run_manifest_sha256: str,
) -> tuple[dict[str, object], ResearchTrajectory]:
    empty_hash = skill_library_sha256([])
    expected = executor._training_round_expected_matrix(
        1,
        case_limit=None,
        input_skill_library_sha256=empty_hash,
    )[0]
    trajectory = ResearchTrajectory.model_validate(
        {
            **expected,
            "domain": "civil",
            "jurisdiction": "CN",
            "status": "memo_submitted",
            "opening": "测试开场。",
            "max_turns": 6,
            "steps": [],
            "memo": "测试备忘录。",
            "elapsed_seconds": 1.0,
            "created_at": "2026-08-24T00:00:00+00:00",
        }
    )
    executor.store.save_model(
        executor.store.trajectory_path("training_batch_01", trajectory.trajectory_id),
        trajectory,
    )
    executor.store.atomic_json(
        executor.store.evaluation_path(trajectory.trajectory_id),
        {
            "schema_version": 13,
            "trajectory_id": trajectory.trajectory_id,
            "case_id": trajectory.case_id,
            "judge_qualification_contract_sha256": "a" * 64,
        },
    )
    executor.store.atomic_json(
        executor.store.root / "health" / "pre_scoring_health_training_batch_01.json",
        {"healthy": True, "counts": {}},
    )
    curve_path = executor.store.root / "reports/development_curve_point_01.json"
    executor.store.atomic_json(curve_path, {"test_fixture": True})
    checkpoint = executor._write_provisionals_ready_checkpoint(
        round_index=1,
        case_limit=None,
        run_manifest_sha256=run_manifest_sha256,
        input_skills=[],
        trajectories=[trajectory],
        candidates=[],
        development_curve_artifact=executor._relative_artifact_record(curve_path),
    )
    return checkpoint, trajectory


def _validate_provisionals_ready(
    executor: MainExperimentExecutor,
    run_manifest_sha256: str,
) -> None:
    executor._validate_provisionals_ready_checkpoint(
        round_index=1,
        case_limit=None,
        run_manifest_sha256=run_manifest_sha256,
        expected_input_skill_ids=[],
        expected_input_skill_library_sha256=skill_library_sha256([]),
    )


@pytest.mark.parametrize("artifact", ["trajectory", "evaluation"])
def test_provisionals_ready_rejects_bound_artifact_hash_drift(
    tmp_path: Path,
    artifact: str,
) -> None:
    executor = _freeze_executor(tmp_path, "hash_drift")
    run_hash = _write_run_manifest(executor)
    _, trajectory = _freeze_provisionals_ready(executor, run_hash)
    path = (
        executor.store.trajectory_path("training_batch_01", trajectory.trajectory_id)
        if artifact == "trajectory"
        else executor.store.evaluation_path(trajectory.trajectory_id)
    )
    value = json.loads(path.read_text(encoding="utf-8"))
    value["post_checkpoint_edit"] = True
    executor.store.atomic_json(path, value)

    with pytest.raises(ExecutionError, match="missing or changed"):
        _validate_provisionals_ready(executor, run_hash)


def test_provisionals_ready_rejects_schema_14_even_if_manifest_hash_is_rewritten(
    tmp_path: Path,
) -> None:
    executor = _freeze_executor(tmp_path, "schema_14")
    run_hash = _write_run_manifest(executor)
    _, trajectory = _freeze_provisionals_ready(executor, run_hash)
    trajectory_path = executor.store.trajectory_path("training_batch_01", trajectory.trajectory_id)
    value = json.loads(trajectory_path.read_text(encoding="utf-8"))
    value["schema_version"] = 14
    executor.store.atomic_json(trajectory_path, value)

    manifest_path = executor.store.root / "manifests" / "training_batch_01__provisionals_ready.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["trajectory_artifacts"][trajectory.trajectory_id]["sha256"] = sha256_file(
        trajectory_path
    )
    content = {key: item for key, item in manifest.items() if key != "content_sha256"}
    manifest["content_sha256"] = canonical_json_sha256(content)
    executor.store.atomic_json(manifest_path, manifest)

    with pytest.raises(ExecutionError, match="current protocol 16"):
        _validate_provisionals_ready(executor, run_hash)


def test_provisionals_ready_rejects_checkpoint_copied_from_another_run(
    tmp_path: Path,
) -> None:
    old = _freeze_executor(tmp_path, "old_run")
    old_run_hash = _write_run_manifest(old)
    _freeze_provisionals_ready(old, old_run_hash)

    copied_root = tmp_path / "runs" / "new_run"
    shutil.copytree(old.store.root, copied_root)
    current = _freeze_executor(tmp_path, "new_run")
    current.store.atomic_json(
        current.store.root / "manifests/run.json",
        {
            "schema_version": 2,
            "run_id": "new_run",
            "content_sha256": canonical_json_sha256({"schema_version": 2, "run_id": "new_run"}),
        },
    )
    current_run_hash = sha256_file(current.store.root / "manifests/run.json")

    with pytest.raises(ExecutionError, match="binding mismatch"):
        _validate_provisionals_ready(current, current_run_hash)


def test_training_complete_rejects_wrong_summary_run_id(tmp_path: Path) -> None:
    executor = _freeze_executor(tmp_path, "current_run")
    run_hash = _write_run_manifest(executor)
    executor.store.write_manifest(
        "training_complete",
        {
            "schema_version": 4,
            "run_id": "copied_run",
            "run_manifest_sha256": run_hash,
            "trajectory_schema_version": 16,
            "evaluation_schema_version": 13,
            "case_limit": None,
            "rounds_completed": 1,
            "round_completion_manifests": {"training_batch_01": "c" * 64},
            "round_completion_set_sha256": "d" * 64,
            "accepted_skill_ids": [],
            "rejected_skill_ids": [],
            "prospective_validation_reports": {"training_batch_01": "e" * 64},
            "active_skill_ids": [],
            "active_skill_library_version": "bootstrap_empty",
            "active_skill_library_sha256": skill_library_sha256([]),
            "development_learning_curve_sha256": "f" * 64,
            "completed_at": "2026-08-24T00:00:00+00:00",
        },
    )

    with pytest.raises(ExecutionError, match="binding drift"):
        executor._load_validated_training_summary(run_manifest_sha256=run_hash)


def test_train_explicitly_rejects_legacy_round_checkpoint(tmp_path: Path) -> None:
    executor = _freeze_executor(tmp_path, "legacy_round")
    _write_run_manifest(executor)
    executor.verify_run_manifest = lambda: executor.store.read_manifest("run")
    executor.generate_training_round = lambda *args, **kwargs: pytest.fail(
        "legacy checkpoint must be rejected before rollout"
    )
    executor.store.write_manifest(
        "training_batch_01__provisionals_ready",
        {
            "schema_version": 1,
            "round": 1,
            "stage": "complete",
        },
    )

    with pytest.raises(ExecutionError, match="legacy candidates-ready checkpoint"):
        MainExperimentExecutor.train(executor)
