from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from legal_skill_guard.experiment.executor import MainExperimentExecutor
from legal_skill_guard.experiment.group_attribution import (
    TrainingGroupAttributionPolicy,
    training_group_attribution_review,
)
from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.schemas.state import StatePatch


def _policy(*, minimum_groups: int = 12) -> TrainingGroupAttributionPolicy:
    return TrainingGroupAttributionPolicy(
        status="frozen_pre_reward_complete_group_quarantine",
        expected_groups=16,
        group_size=4,
        minimum_scoreable_groups=minimum_groups,
        minimum_scoreable_group_fraction=0.75,
        action="exclude_complete_attribution_group_or_stop_before_semantic_scoring",
    )


def _matrix() -> list[SimpleNamespace]:
    return [
        SimpleNamespace(
            trajectory_id=f"traj_{group_index:02d}_{sample_index}",
            group_id=f"training_batch_01.case_{group_index:02d}.P_CS.seed_42",
            case_id=f"case_{group_index:02d}",
            partition="training_batch_01",
            persona="P_CS",
            seed=42,
            sample_index=sample_index,
            opening_inquiry_agenda=StatePatch(),
        )
        for group_index in range(16)
        for sample_index in range(4)
    ]


def _report(*issues: tuple[str, str]) -> dict[str, object]:
    return {
        "issues": [
            {
                "code": code,
                "trajectory_id": trajectory_id,
                "turn": 1,
                "detail": "test",
            }
            for trajectory_id, code in issues
        ],
        "issues_truncated": 0,
    }


def test_local_fallbacks_quarantine_complete_groups_before_reward() -> None:
    review = training_group_attribution_review(
        _matrix(),
        health_report=_report(
            ("traj_01_0", "policy_fallback_used"),
            ("traj_01_0", "persisted_policy_contract_failure"),
            ("traj_05_2", "memo_fallback_used"),
            ("traj_08_1", "client_selection_fallback_used"),
            ("traj_12_3", "policy_fallback_used"),
        ),
        policy=_policy(),
    )

    assert review["scoring_eligible"] is True
    assert review["selection_uses_reward_or_candidate_outcome"] is False
    assert review["scoreable_groups"] == 12
    assert review["excluded_groups"] == 4
    assert review["excluded_trajectories"] == 16
    assert len(review["scoreable_trajectory_ids"]) == 48
    assert review["fatal_issue_count"] == 0


def test_unanchored_policy_contract_failure_remains_globally_blocking() -> None:
    review = training_group_attribution_review(
        _matrix(),
        health_report=_report(
            ("traj_01_0", "persisted_policy_contract_failure"),
        ),
        policy=_policy(),
    )

    assert review["scoring_eligible"] is False
    assert review["excluded_groups"] == 0
    assert review["fatal_issue_count"] == 1


def test_nonlocal_health_defect_cannot_be_hidden_by_fallback_anchor() -> None:
    review = training_group_attribution_review(
        _matrix(),
        health_report=_report(
            ("traj_01_0", "policy_fallback_used"),
            ("traj_01_0", "hidden_field_leak"),
        ),
        policy=_policy(),
    )

    assert review["scoring_eligible"] is False
    assert review["excluded_groups"] == 0
    assert review["fatal_issue_count"] == 2


def test_excessive_outcome_blind_attrition_stops_before_scoring() -> None:
    review = training_group_attribution_review(
        _matrix(),
        health_report=_report(
            *((f"traj_{group_index:02d}_0", "memo_fallback_used") for group_index in range(5))
        ),
        policy=_policy(),
    )

    assert review["scoreable_groups"] == 11
    assert review["scoring_eligible"] is False
    assert review["threshold_checks"] == {
        "minimum_scoreable_groups": False,
        "minimum_scoreable_group_fraction": False,
    }


def test_incomplete_group_matrix_remains_globally_blocking() -> None:
    trajectories = _matrix()[:-1]
    review = training_group_attribution_review(
        trajectories,
        health_report=_report(),
        policy=_policy(),
    )

    assert review["scoring_eligible"] is False
    assert "malformed_complete_groups" in review["matrix_failures"]


def test_different_opening_agendas_stop_group_before_reward_attribution() -> None:
    trajectories = _matrix()
    trajectories[0].opening_inquiry_agenda = StatePatch(
        issue_labels=["合同履行"],
    )
    review = training_group_attribution_review(
        trajectories,
        health_report=_report(),
        policy=_policy(),
    )

    assert review["scoring_eligible"] is False
    assert "group_opening_inquiry_agenda_mismatch" in review["matrix_failures"]
    assert review["plan_misaligned_group_ids"] == [
        "training_batch_01.case_00.P_CS.seed_42"
    ]


class _DummyEvaluation(BaseModel):
    trajectory_id: str


def test_training_scoring_persists_full_matrix_but_quarantines_attribution_groups(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    trajectories = _matrix()
    issues = _report(
        ("traj_01_0", "policy_fallback_used"),
        ("traj_01_0", "persisted_policy_contract_failure"),
        ("traj_05_2", "memo_fallback_used"),
        ("traj_12_3", "policy_fallback_used"),
    )
    health = {
        "schema_version": 2,
        "healthy": False,
        "trajectory_count": 64,
        "blocking_issue_count": 4,
        "counts": {
            "memo_fallback_used": 1,
            "persisted_policy_contract_failure": 1,
            "policy_fallback_used": 2,
        },
        "issues": issues["issues"],
        "issues_truncated": 0,
        "quality_diagnostics": {},
    }
    monkeypatch.setattr(
        "legal_skill_guard.experiment.executor.trajectory_health_report",
        lambda *_args, **_kwargs: health,
    )
    calls: list[str] = []
    executor = MainExperimentExecutor.__new__(MainExperimentExecutor)
    executor.store = RunStore(tmp_path / "runs", "run_test")
    executor.experiment = {"execution": {"judge_workers": 4}}
    executor.training_plan = SimpleNamespace(
        batches=[SimpleNamespace(batch_id="training_batch_01", case_ids=[])],
    )
    executor.training_batch_productivity_thresholds = None
    executor.training_group_attribution_policy = _policy()
    executor.evaluator = SimpleNamespace(
        evaluate=lambda trajectory, _case: (
            calls.append(trajectory.trajectory_id)
            or _DummyEvaluation(trajectory_id=trajectory.trajectory_id)
        )
    )
    adapter = SimpleNamespace(evaluator_case=lambda _case_id: {})

    evaluations = MainExperimentExecutor.score_trajectories(executor, trajectories, adapter)

    assert len(evaluations) == 64
    assert len(calls) == 64
    persisted = json.loads(
        (executor.store.root / "health/pre_scoring_health_training_batch_01.json").read_text(
            encoding="utf-8"
        )
    )
    review = persisted["quality_diagnostics"]["training_group_attribution_review"]
    assert review["scoreable_groups"] == 13
    assert review["excluded_groups"] == 3
    assert review["scoring_eligible"] is True
