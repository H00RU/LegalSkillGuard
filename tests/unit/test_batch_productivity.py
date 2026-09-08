import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from legal_skill_guard.experiment.batch_productivity import (
    TrainingBatchProductivityThresholds,
    training_batch_productivity_review,
)
from legal_skill_guard.experiment.executor import MainExperimentExecutor
from legal_skill_guard.experiment.storage import RunStore

CASE_IDS = [f"case_{index:02d}" for index in range(14)]


def _thresholds(**changes: object) -> TrainingBatchProductivityThresholds:
    values: dict[str, object] = {
        "status": "frozen_predeclared_productivity_diagnostic",
        "expected_cases": 14,
        "expected_trajectories": 224,
        "minimum_cases_with_new_hidden_fact": 7,
        "minimum_trajectory_question_rate": 0.50,
        "minimum_trajectory_new_hidden_fact_rate": 0.20,
        "minimum_new_hidden_fact_per_question": 0.05,
        "review_if_failed_checks_at_least": 2,
        "action": "record_diagnostic_and_continue_to_teacher_evidence",
    }
    values.update(changes)
    return TrainingBatchProductivityThresholds.model_validate(values)


def _matrix(*, fact_members_per_case: int, question_members_per_case: int = 16):
    trajectories = []
    for case_id in CASE_IDS:
        for member in range(16):
            asks = member < question_members_per_case
            gets_fact = member < fact_members_per_case
            trajectories.append(
                SimpleNamespace(
                    trajectory_id=f"{case_id}.member_{member:02d}",
                    case_id=case_id,
                    steps=[
                        SimpleNamespace(
                            rendered_question="请说明相关事实。" if asks else None,
                            client_response_kind=(
                                "new_hidden_fact" if gets_fact else "unavailable"
                            ),
                            client_selected_fact_ids=["F1"] if gets_fact else [],
                        )
                    ],
                )
            )
    return trajectories


def test_complete_productive_batch_continues_to_semantic_scoring() -> None:
    report = training_batch_productivity_review(
        _matrix(fact_members_per_case=4),
        expected_case_ids=CASE_IDS,
        thresholds=_thresholds(),
    )

    assert report["matrix_checks"] == {
        "case_ids_exact": True,
        "trajectory_count_exact": True,
        "trajectory_ids_unique": True,
        "per_case_counts_exact": True,
    }
    assert report["failed_checks"] == []
    assert report["review_required"] is False
    assert report["decision"] == "continue_to_semantic_scoring"


def test_one_weak_metric_does_not_stop_the_formal_batch() -> None:
    report = training_batch_productivity_review(
        _matrix(fact_members_per_case=3),
        expected_case_ids=CASE_IDS,
        thresholds=_thresholds(),
    )

    assert report["failed_checks"] == [
        "minimum_trajectory_new_hidden_fact_rate"
    ]
    assert report["review_required"] is False


def test_multiple_low_productivity_signals_raise_diagnostic_flag() -> None:
    trajectories = _matrix(fact_members_per_case=0)
    for case_index in range(6):
        trajectory = trajectories[case_index * 16]
        trajectory.steps[0].client_response_kind = "new_hidden_fact"
        trajectory.steps[0].client_selected_fact_ids = ["F1"]

    report = training_batch_productivity_review(
        trajectories,
        expected_case_ids=CASE_IDS,
        thresholds=_thresholds(),
    )

    assert report["observed"]["cases_with_new_hidden_fact"] == 6
    assert report["observed"]["new_hidden_fact_per_question"] == pytest.approx(
        6 / 224, abs=1e-6
    )
    assert len(report["failed_checks"]) == 3
    assert report["review_required"] is True
    assert report["decision"] == "continue_with_low_productivity_review_flag"


def test_incomplete_or_duplicate_matrix_fails_before_productivity_interpretation() -> None:
    trajectories = _matrix(fact_members_per_case=4)
    trajectories[-1].trajectory_id = trajectories[0].trajectory_id

    with pytest.raises(ValueError, match="complete declared matrix"):
        training_batch_productivity_review(
            trajectories,
            expected_case_ids=CASE_IDS,
            thresholds=_thresholds(),
        )


def test_productivity_policy_literals_and_bounds_are_fail_closed() -> None:
    with pytest.raises(ValidationError):
        _thresholds(status="mutable")
    with pytest.raises(ValidationError):
        _thresholds(review_if_failed_checks_at_least=5)
    with pytest.raises(ValidationError):
        _thresholds(unexpected=True)


def test_executor_persists_low_productivity_review_and_continues_to_judge(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    trajectories = _matrix(fact_members_per_case=0)
    for trajectory in trajectories:
        trajectory.partition = "training_batch_01"
    for case_index in range(6):
        trajectory = trajectories[case_index * 16]
        trajectory.steps[0].client_response_kind = "new_hidden_fact"
        trajectory.steps[0].client_selected_fact_ids = ["F1"]

    monkeypatch.setattr(
        "legal_skill_guard.experiment.executor.trajectory_health_report",
        lambda *_args, **_kwargs: {
            "healthy": True,
            "counts": {},
            "quality_diagnostics": {},
        },
    )
    executor = MainExperimentExecutor.__new__(MainExperimentExecutor)
    executor.store = RunStore(tmp_path / "runs", "run_test")
    executor.experiment = {"execution": {"judge_workers": 1}}
    executor.training_plan = SimpleNamespace(
        batches=[
            SimpleNamespace(
                batch_id="training_batch_01",
                case_ids=tuple(CASE_IDS),
            )
        ]
    )
    executor.training_batch_productivity_thresholds = _thresholds()
    adapter = SimpleNamespace(evaluator_case=lambda _case_id: {})
    semantic_scoring_started: list[bool] = []
    monkeypatch.setattr(
        "legal_skill_guard.experiment.executor.parallel_map_ordered",
        lambda items, _fn, **_kwargs: [
            semantic_scoring_started.append(True) or object() for _ in items
        ],
    )

    evaluations = MainExperimentExecutor.score_trajectories(
        executor, trajectories, adapter
    )

    report_path = (
        executor.store.root
        / "health/pre_scoring_health_training_batch_01.json"
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    review = report["quality_diagnostics"][
        "training_batch_productivity_review"
    ]
    assert review["review_required"] is True
    assert review["decision"] == (
        "continue_with_low_productivity_review_flag"
    )
    assert len(semantic_scoring_started) == len(trajectories)
    assert len(evaluations) == len(trajectories)
