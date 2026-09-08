"""Outcome-blind group quarantine for training-time attribution failures."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# These outcomes replace or finish model behavior with deterministic safety text.
# They are safe to persist and inspect, but they cannot be credited to the sampled
# policy.  A complete K group containing one of them is therefore unavailable for
# relative attribution.  All other health defects remain globally blocking.
ATTRIBUTION_ANCHOR_CODES = frozenset(
    {
        "client_selection_fallback_used",
        "memo_fallback_used",
        "policy_fallback_used",
    }
)
ATTRIBUTION_LOCAL_CODES = frozenset(
    {
        *ATTRIBUTION_ANCHOR_CODES,
        # The persisted policy produced by a policy-safe fallback can retain the
        # original blocked violation for audit.  It is local only when the same
        # trajectory also has ``policy_fallback_used``.
        "persisted_policy_contract_failure",
    }
)


def attribution_issue_codes_are_local_recovery(codes: set[str]) -> bool:
    """Return whether one trajectory contains only anchored model recovery.

    Client, memo and policy fallbacks replace model behavior and are therefore
    attribution-local.  A persisted policy-contract failure is local only when
    the same trajectory records the policy fallback that produced it; on its own
    it remains a fatal execution defect.
    """

    anchored = bool(codes & ATTRIBUTION_ANCHOR_CODES)
    policy_contract_is_anchored = (
        "persisted_policy_contract_failure" not in codes
        or "policy_fallback_used" in codes
    )
    return anchored and codes <= ATTRIBUTION_LOCAL_CODES and policy_contract_is_anchored


class TrainingGroupAttributionPolicy(BaseModel):
    """Predeclared minimum usable matrix after outcome-blind group quarantine."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["frozen_pre_reward_complete_group_quarantine"]
    expected_groups: int = Field(ge=1)
    group_size: int = Field(ge=2)
    minimum_scoreable_groups: int = Field(ge=1)
    minimum_scoreable_group_fraction: float = Field(gt=0.0, le=1.0)
    action: Literal["exclude_complete_attribution_group_or_stop_before_semantic_scoring"]

    @model_validator(mode="after")
    def validate_internal_bounds(self) -> TrainingGroupAttributionPolicy:
        if self.minimum_scoreable_groups > self.expected_groups:
            raise ValueError("minimum scoreable groups cannot exceed expected groups")
        return self


def training_group_attribution_review(
    trajectories: Sequence[Any],
    *,
    health_report: dict[str, Any],
    policy: TrainingGroupAttributionPolicy,
) -> dict[str, Any]:
    """Select complete scoreable groups without consulting rewards or judge output.

    Only deterministic model-replacement fallbacks are quarantinable.  Their full
    K group is excluded so no relative advantage is computed from an incomplete or
    partially non-model group.  A different health defect, an incomplete matrix, or
    excessive attrition still fails closed before semantic scoring.
    """

    by_group: dict[str, list[Any]] = defaultdict(list)
    trajectory_by_id: dict[str, Any] = {}
    duplicate_trajectory_ids: set[str] = set()
    for trajectory in trajectories:
        trajectory_id = str(trajectory.trajectory_id)
        group_id = str(trajectory.group_id or "")
        if trajectory_id in trajectory_by_id:
            duplicate_trajectory_ids.add(trajectory_id)
        trajectory_by_id[trajectory_id] = trajectory
        by_group[group_id].append(trajectory)

    matrix_failures: list[str] = []
    if duplicate_trajectory_ids:
        matrix_failures.append("duplicate_trajectory_ids")
    if "" in by_group:
        matrix_failures.append("missing_group_id")
    if len(by_group) != policy.expected_groups:
        matrix_failures.append("group_count_mismatch")
    malformed_group_ids: list[str] = []
    for group_id, members in sorted(by_group.items()):
        if not group_id or len(members) != policy.group_size:
            malformed_group_ids.append(group_id)
            continue
        if len({str(item.case_id) for item in members}) != 1:
            malformed_group_ids.append(group_id)
        if len({str(item.partition) for item in members}) != 1:
            malformed_group_ids.append(group_id)
        if len({str(item.persona) for item in members}) != 1:
            malformed_group_ids.append(group_id)
        if len({int(item.seed) for item in members}) != 1:
            malformed_group_ids.append(group_id)
        if sorted(int(item.sample_index) for item in members) != list(range(policy.group_size)):
            malformed_group_ids.append(group_id)
    if malformed_group_ids:
        matrix_failures.append("malformed_complete_groups")

    issue_rows = health_report.get("issues") or []
    issues_truncated = int(health_report.get("issues_truncated") or 0)
    if issues_truncated:
        matrix_failures.append("health_issue_records_truncated")
    issues_by_trajectory: dict[str, list[dict[str, Any]]] = defaultdict(list)
    unknown_issue_trajectory_ids: set[str] = set()
    for row in issue_rows:
        if not isinstance(row, dict):
            matrix_failures.append("invalid_health_issue_record")
            continue
        trajectory_id = str(row.get("trajectory_id") or "")
        if trajectory_id not in trajectory_by_id:
            unknown_issue_trajectory_ids.add(trajectory_id)
        issues_by_trajectory[trajectory_id].append(row)
    if unknown_issue_trajectory_ids:
        matrix_failures.append("unknown_health_issue_trajectory")

    local_trigger_ids: set[str] = set()
    fatal_issue_rows: list[dict[str, Any]] = []
    for trajectory_id, rows in sorted(issues_by_trajectory.items()):
        codes = {str(row.get("code") or "") for row in rows}
        if attribution_issue_codes_are_local_recovery(codes):
            local_trigger_ids.add(trajectory_id)
        else:
            fatal_issue_rows.extend(rows)

    excluded_group_ids = {
        str(trajectory_by_id[trajectory_id].group_id)
        for trajectory_id in local_trigger_ids
        if trajectory_id in trajectory_by_id
    }
    scoreable_group_ids = sorted(set(by_group) - excluded_group_ids)
    excluded_trajectory_ids = sorted(
        str(item.trajectory_id)
        for group_id in excluded_group_ids
        for item in by_group.get(group_id, [])
    )
    scoreable_trajectory_ids = sorted(
        str(item.trajectory_id)
        for group_id in scoreable_group_ids
        for item in by_group.get(group_id, [])
    )
    scoreable_fraction = len(scoreable_group_ids) / len(by_group) if by_group else 0.0
    threshold_checks = {
        "minimum_scoreable_groups": (len(scoreable_group_ids) >= policy.minimum_scoreable_groups),
        "minimum_scoreable_group_fraction": (
            scoreable_fraction >= policy.minimum_scoreable_group_fraction
        ),
    }
    scoring_eligible = (
        not matrix_failures and not fatal_issue_rows and all(threshold_checks.values())
    )
    exclusion_reason_counts = Counter(
        str(row.get("code") or "")
        for trajectory_id in local_trigger_ids
        for row in issues_by_trajectory[trajectory_id]
    )
    return {
        "schema_version": 1,
        "scope": "training_candidate_attribution_before_semantic_scoring",
        "policy": policy.model_dump(mode="json"),
        "selection_timing": "before_reward_and_semantic_judgment",
        "selection_uses_reward_or_candidate_outcome": False,
        "quarantine_unit": "complete_k_group",
        "observed_groups": len(by_group),
        "observed_trajectories": len(trajectories),
        "scoreable_groups": len(scoreable_group_ids),
        "scoreable_trajectories": len(scoreable_trajectory_ids),
        "scoreable_group_fraction": round(scoreable_fraction, 6),
        "excluded_groups": len(excluded_group_ids),
        "excluded_trajectories": len(excluded_trajectory_ids),
        "local_trigger_trajectories": sorted(local_trigger_ids),
        "excluded_group_ids": sorted(excluded_group_ids),
        "excluded_trajectory_ids": excluded_trajectory_ids,
        "scoreable_group_ids": scoreable_group_ids,
        "scoreable_trajectory_ids": scoreable_trajectory_ids,
        "exclusion_reason_counts": dict(sorted(exclusion_reason_counts.items())),
        "fatal_issue_count": len(fatal_issue_rows),
        "fatal_issues": fatal_issue_rows[:100],
        "matrix_failures": sorted(set(matrix_failures)),
        "threshold_checks": threshold_checks,
        "scoring_eligible": scoring_eligible,
        "decision": (
            "score_full_matrix_but_attribute_only_scoreable_groups"
            if scoring_eligible
            else "stop_before_semantic_scoring"
        ),
    }
