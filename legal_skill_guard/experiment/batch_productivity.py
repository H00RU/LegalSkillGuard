"""Predeclared productivity diagnostics for complete training batches."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TrainingBatchProductivityThresholds(BaseModel):
    """Conservative diagnostic floors, never a skill-effect acceptance test."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["frozen_predeclared_productivity_diagnostic"]
    expected_cases: int = Field(ge=1)
    expected_trajectories: int = Field(ge=1)
    minimum_cases_with_new_hidden_fact: int = Field(ge=1)
    minimum_trajectory_question_rate: float = Field(ge=0.0, le=1.0)
    minimum_trajectory_new_hidden_fact_rate: float = Field(ge=0.0, le=1.0)
    minimum_new_hidden_fact_per_question: float = Field(ge=0.0, le=1.0)
    review_if_failed_checks_at_least: int = Field(ge=2)
    action: Literal["record_diagnostic_and_continue_to_teacher_evidence"]

    @model_validator(mode="after")
    def validate_internal_bounds(self) -> TrainingBatchProductivityThresholds:
        if self.minimum_cases_with_new_hidden_fact > self.expected_cases:
            raise ValueError("minimum case coverage cannot exceed the declared batch")
        if self.review_if_failed_checks_at_least > 4:
            raise ValueError("review trigger cannot exceed the four declared checks")
        if self.expected_trajectories % self.expected_cases:
            raise ValueError(
                "expected trajectory count must divide evenly across expected cases"
            )
        return self


def _new_hidden_fact_ids(step: Any) -> set[str]:
    if getattr(step, "client_response_kind", None) != "new_hidden_fact":
        return set()
    return {
        str(item)
        for item in getattr(step, "client_selected_fact_ids", [])
        if str(item).startswith("F")
    }


def training_batch_productivity_review(
    trajectories: Sequence[Any],
    *,
    expected_case_ids: Sequence[str],
    thresholds: TrainingBatchProductivityThresholds,
) -> dict[str, Any]:
    """Describe a full batch before semantic scoring without judging model quality.

    The decision is deliberately conjunctive: one weak descriptive metric cannot
    even trigger a review flag. A weak frozen policy is exactly the setting in
    which contrastive teacher evidence may be useful, so this report must not
    prevent semantic scoring or teacher access to valid positive/negative forks.
    """

    expected_cases = [str(item) for item in expected_case_ids]
    if len(expected_cases) != len(set(expected_cases)):
        raise ValueError("expected_case_ids must be unique")
    if len(expected_cases) != thresholds.expected_cases:
        raise ValueError("configured productivity case count does not match the batch")
    observed_cases = sorted({str(item.case_id) for item in trajectories})
    expected_per_case = thresholds.expected_trajectories // thresholds.expected_cases
    per_case_counts = Counter(str(item.case_id) for item in trajectories)
    trajectory_ids = [str(item.trajectory_id) for item in trajectories]
    matrix_checks = {
        "case_ids_exact": set(observed_cases) == set(expected_cases),
        "trajectory_count_exact": len(trajectories) == thresholds.expected_trajectories,
        "trajectory_ids_unique": len(trajectory_ids) == len(set(trajectory_ids)),
        "per_case_counts_exact": all(
            per_case_counts.get(case_id, 0) == expected_per_case
            for case_id in expected_cases
        ),
    }
    if not all(matrix_checks.values()):
        raise ValueError(
            "training batch productivity review requires the complete declared matrix"
        )

    question_count = 0
    trajectories_with_question = 0
    trajectories_with_new_fact = 0
    cases_with_new_fact: set[str] = set()
    new_fact_turn_count = 0
    unique_case_fact_pairs: set[tuple[str, str]] = set()
    for trajectory in trajectories:
        trajectory_questions = 0
        trajectory_facts: set[str] = set()
        for step in trajectory.steps:
            if getattr(step, "rendered_question", None):
                trajectory_questions += 1
            selected = _new_hidden_fact_ids(step)
            if selected:
                new_fact_turn_count += 1
                trajectory_facts.update(selected)
                unique_case_fact_pairs.update(
                    (str(trajectory.case_id), fact_id) for fact_id in selected
                )
        question_count += trajectory_questions
        if trajectory_questions:
            trajectories_with_question += 1
        if trajectory_facts:
            trajectories_with_new_fact += 1
            cases_with_new_fact.add(str(trajectory.case_id))

    trajectory_count = len(trajectories)
    observed = {
        "case_count": len(observed_cases),
        "trajectory_count": trajectory_count,
        "question_count": question_count,
        "new_hidden_fact_turn_count": new_fact_turn_count,
        "unique_case_fact_pair_count": len(unique_case_fact_pairs),
        "cases_with_new_hidden_fact": len(cases_with_new_fact),
        "trajectories_with_question": trajectories_with_question,
        "trajectory_question_rate": round(
            trajectories_with_question / trajectory_count, 6
        ),
        "trajectories_with_new_hidden_fact": trajectories_with_new_fact,
        "trajectory_new_hidden_fact_rate": round(
            trajectories_with_new_fact / trajectory_count, 6
        ),
        "new_hidden_fact_per_question": round(
            new_fact_turn_count / question_count, 6
        )
        if question_count
        else 0.0,
    }
    checks = {
        "minimum_cases_with_new_hidden_fact": (
            observed["cases_with_new_hidden_fact"]
            >= thresholds.minimum_cases_with_new_hidden_fact
        ),
        "minimum_trajectory_question_rate": (
            observed["trajectory_question_rate"]
            >= thresholds.minimum_trajectory_question_rate
        ),
        "minimum_trajectory_new_hidden_fact_rate": (
            observed["trajectory_new_hidden_fact_rate"]
            >= thresholds.minimum_trajectory_new_hidden_fact_rate
        ),
        "minimum_new_hidden_fact_per_question": (
            observed["new_hidden_fact_per_question"]
            >= thresholds.minimum_new_hidden_fact_per_question
        ),
    }
    failed_checks = sorted(key for key, passed in checks.items() if not passed)
    review_required = (
        len(failed_checks) >= thresholds.review_if_failed_checks_at_least
    )
    return {
        "schema_version": 1,
        "scope": "complete_training_batch_before_semantic_scoring",
        "policy": "productivity_diagnostic_not_effect_or_health_acceptance",
        "matrix_checks": matrix_checks,
        "thresholds": thresholds.model_dump(mode="json"),
        "observed": observed,
        "checks": checks,
        "failed_checks": failed_checks,
        "review_required": review_required,
        "decision": (
            "continue_with_low_productivity_review_flag"
            if review_required
            else "continue_to_semantic_scoring"
        ),
    }
