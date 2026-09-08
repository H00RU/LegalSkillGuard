from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from legal_skill_guard.experiment.executor import (
    ExecutionError,
    MainExperimentExecutor,
    skill_library_sha256,
)
from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.schemas.experiment import ResearchTrajectory
from legal_skill_guard.utils.hashing import sha256_file
from tests.skill_fixtures import synthetic_skills


def _executor(tmp_path: Path, *, run_id: str = "curve_contract") -> MainExperimentExecutor:
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
            "provisional_candidate_budget_per_block": 2,
        },
        "personas": ["P_WD"],
        "trajectory_sampling": {
            "group_size": 1,
            "training_group_seeds": [42],
        },
        "learning_curve": {
            "bootstrap_samples": 100,
            "bootstrap_seed": 17,
            "evidence_role": "development_only_never_teacher_or_acceptance",
        },
        "prospective_validation": {"confidence_level": 0.95},
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
    executor.learning_curve_sentinels = {"training_batch_01": ["case_test"]}
    executor.registry = SimpleNamespace(current=lambda: None)
    executor.active_skills = lambda: []
    executor.main_adapter = object()
    return executor


def _trajectory_evaluation(trajectory: ResearchTrajectory) -> SimpleNamespace:
    return SimpleNamespace(
        schema_version=13,
        trajectory_id=trajectory.trajectory_id,
        case_id=trajectory.case_id,
        judge_model="openai/gpt-oss-20b",
        judge_qualification_contract_sha256="a" * 64,
        official_metrics=SimpleNamespace(
            resolution=0.4,
            elicitation=0.5,
            fidelity=1.0,
        ),
        safety_metrics=SimpleNamespace(
            critical_fact_recall=0.5,
            repeated_question_rate=0.0,
        ),
        operational_metrics=SimpleNamespace(policy_fallback_rate=0.0),
        reward=SimpleNamespace(final_reward=0.45),
        mechanism_signals=SimpleNamespace(
            newly_elicited_fact_count=1,
            identified_evidence_gap_count=0,
        ),
    )


def _persist_empty_library_training_cell(
    executor: MainExperimentExecutor,
) -> tuple[ResearchTrajectory, dict[str, SimpleNamespace]]:
    empty_hash = skill_library_sha256([])
    expected = executor._training_round_expected_matrix(
        1,
        case_limit=None,
        input_skill_library_sha256=empty_hash,
        input_skills=[],
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
            "created_at": "2026-09-07T00:00:00+00:00",
        }
    )
    executor.store.save_model(
        executor.store.trajectory_path(trajectory.partition, trajectory.trajectory_id),
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
    evaluation = _trajectory_evaluation(trajectory)
    original_load_model = executor.store.load_model

    def load_model(path: Path, model: type[object]) -> object:
        if path == executor.store.evaluation_path(trajectory.trajectory_id):
            return evaluation
        return original_load_model(path, model)

    # The test isolates executor binding semantics; the in-memory evaluation has
    # the complete metric interface while the on-disk bytes remain a real hashed
    # artifact for drift checks.
    executor.store.load_model = load_model  # type: ignore[method-assign]
    return trajectory, {trajectory.trajectory_id: evaluation}


def _prepare_identity_point(
    executor: MainExperimentExecutor,
) -> tuple[ResearchTrajectory, dict[str, object], str]:
    executor.store.write_manifest(
        "run", {"schema_version": 2, "run_id": executor.run_id}
    )
    run_hash = sha256_file(executor.store.root / "manifests/run.json")
    trajectory, evaluations = _persist_empty_library_training_cell(executor)
    point = executor.prepare_development_curve_point(
        round_index=1,
        case_limit=None,
        run_manifest_sha256=run_hash,
        input_skills=[],
        trajectories=[trajectory],
        evaluations=evaluations,
    )
    return trajectory, point, run_hash


def test_empty_library_curve_is_identity_bound_without_shadow_rollout(
    tmp_path: Path,
) -> None:
    executor = _executor(tmp_path)
    executor.generate_learning_curve_shadow = lambda **_: pytest.fail(
        "an empty input library must not spend a duplicate shadow rollout"
    )

    trajectory, point, run_hash = _prepare_identity_point(executor)

    assert point["run_manifest_sha256"] == run_hash
    assert point["identity_baseline"] is True
    assert point["input_active_skill_ids"] == []
    assert point["input_skill_library_sha256"] == skill_library_sha256([])
    assert point["empty_trajectory_artifacts"] == {}
    assert point["empty_evaluation_artifacts"] == {}
    assert point["intervention_isolation_artifact"] is None
    assert point["curve"]["partition_mapping"] == {
        "current": "training_batch_01",
        "empty": "training_batch_01",
    }
    pair = point["curve"]["pairs"][0]
    assert pair["current_trajectory_id"] == trajectory.trajectory_id
    assert pair["empty_trajectory_id"] == trajectory.trajectory_id
    assert all(value == 0 for value in pair["paired_delta"].values())
    shadow_root = (
        executor.store.root / "trajectories/learning_curve_shadow_training_batch_01"
    )
    assert not shadow_root.exists()


class _ReachedSemanticScoring(RuntimeError):
    pass


def _nonempty_curve_executor(tmp_path: Path) -> tuple[MainExperimentExecutor, object, object]:
    executor = _executor(tmp_path, run_id="nonempty_curve")
    skill = synthetic_skills()[0]
    current = SimpleNamespace(trajectory_id="current")
    empty = SimpleNamespace(trajectory_id="empty")
    executor._learning_curve_current_trajectories = lambda **_: [current]
    executor.generate_learning_curve_shadow = lambda **_: [empty]
    return executor, skill, current


def test_nonempty_curve_runs_whole_library_isolation_before_semantic_scoring(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executor, skill, current = _nonempty_curve_executor(tmp_path)
    events: list[str] = []

    def isolate(*_args: object, **_kwargs: object) -> dict[str, object]:
        events.append("whole_library_isolation")
        return {
            "schema_version": 1,
            "passed": True,
            "current_partition": "training_batch_01",
            "empty_partition": "learning_curve_shadow_training_batch_01",
            "pair_count": 1,
            "failure_count": 0,
        }

    def score(*_args: object, **_kwargs: object) -> dict[str, object]:
        events.append("semantic_score")
        raise _ReachedSemanticScoring

    monkeypatch.setattr(
        "legal_skill_guard.experiment.executor.skill_library_intervention_isolation_report",
        isolate,
    )
    executor.score_trajectories = score

    with pytest.raises(_ReachedSemanticScoring):
        executor.prepare_development_curve_point(
            round_index=1,
            case_limit=None,
            run_manifest_sha256="b" * 64,
            input_skills=[skill],
            trajectories=[current],
            evaluations={"current": object()},
        )

    assert events == ["whole_library_isolation", "semantic_score"]
    isolation = json.loads(
        (
            executor.store.root
            / "health/development_curve_intervention_isolation_training_batch_01.json"
        ).read_text(encoding="utf-8")
    )
    assert isolation["passed"] is True


def test_nonempty_curve_contamination_fails_before_semantic_scoring(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executor, skill, current = _nonempty_curve_executor(tmp_path)
    semantic_score_called = False

    monkeypatch.setattr(
        "legal_skill_guard.experiment.executor.skill_library_intervention_isolation_report",
        lambda *_args, **_kwargs: {
            "schema_version": 1,
            "passed": False,
            "current_partition": "training_batch_01",
            "empty_partition": "learning_curve_shadow_training_batch_01",
            "pair_count": 1,
            "failure_count": 1,
        },
    )

    def score(*_args: object, **_kwargs: object) -> dict[str, object]:
        nonlocal semantic_score_called
        semantic_score_called = True
        return {}

    executor.score_trajectories = score

    with pytest.raises(ExecutionError, match="not a sole skill-library intervention"):
        executor.prepare_development_curve_point(
            round_index=1,
            case_limit=None,
            run_manifest_sha256="b" * 64,
            input_skills=[skill],
            trajectories=[current],
            evaluations={"current": object()},
        )

    assert semantic_score_called is False
    isolation = json.loads(
        (
            executor.store.root
            / "health/development_curve_intervention_isolation_training_batch_01.json"
        ).read_text(encoding="utf-8")
    )
    assert isolation["passed"] is False


def test_provisionals_checkpoint_rejects_curve_artifact_hash_drift(
    tmp_path: Path,
) -> None:
    executor = _executor(tmp_path, run_id="curve_hash_drift")
    trajectory, _, run_hash = _prepare_identity_point(executor)
    executor.store.atomic_json(
        executor.store.root / "health/pre_scoring_health_training_batch_01.json",
        {"healthy": True, "counts": {}},
    )
    curve_path = executor._learning_curve_point_path(1)
    executor._write_provisionals_ready_checkpoint(
        round_index=1,
        case_limit=None,
        run_manifest_sha256=run_hash,
        input_skills=[],
        trajectories=[trajectory],
        candidates=[],
        development_curve_artifact=executor._relative_artifact_record(curve_path),
    )
    point = json.loads(curve_path.read_text(encoding="utf-8"))
    point["post_checkpoint_edit"] = True
    executor.store.atomic_json(curve_path, point)

    with pytest.raises(ExecutionError, match="artifact is missing or changed"):
        executor._validate_provisionals_ready_checkpoint(
            round_index=1,
            case_limit=None,
            run_manifest_sha256=run_hash,
            expected_input_skill_ids=[],
            expected_input_skill_library_sha256=skill_library_sha256([]),
        )


def test_learning_checkpoint_rejects_curve_input_library_binding_drift(
    tmp_path: Path,
) -> None:
    executor = _executor(tmp_path, run_id="curve_input_drift")
    _, _, run_hash = _prepare_identity_point(executor)
    curve_path = executor._learning_curve_point_path(1)

    with pytest.raises(ExecutionError, match="binding mismatch"):
        executor.write_learning_checkpoint(
            round_index=1,
            case_limit=None,
            run_manifest_sha256=run_hash,
            accepted_skill_ids=[],
            input_skills=[synthetic_skills()[0]],
            development_curve_artifact=executor._relative_artifact_record(curve_path),
        )
