"""Sole-intervention checks for prompt-delivered skill memories.

Control and treatment share case, frozen planner/policy snapshot and random stream.
The declared intervention is the session-level skill-document bundle present in
both the session planner and every later policy prompt.  The model-authored plan and
dialogue are downstream mediators and may therefore diverge; a plan-identity or
post-policy activation-prefix test would erase the intervention we want to measure.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Mapping
from typing import Any

from legal_skill_guard.schemas.experiment import ResearchTrajectory
from legal_skill_guard.schemas.skill import SkillContract
from legal_skill_guard.skills.memory import (
    extract_rendered_skill_memory,
    parse_rendered_skill_memory,
    render_skill_memory,
)
from legal_skill_guard.utils.hashing import canonical_json_sha256

_SKILL_LIBRARY_IDENTITY_FIELDS = (
    "run_id",
    "group_id",
    "case_id",
    "domain",
    "jurisdiction",
    "persona",
    "seed",
    "sample_index",
    "model_id",
    "model_revision",
    "opening",
    "max_turns",
)

_SKILL_LIBRARY_METHOD_PAIRS = {
    ("training_policy_sample", "training_policy_sample"),
    ("legal_skill_evolve", "control_no_library"),
}

def _plain(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if hasattr(value, "__dict__"):
        return {
            str(key): _plain(item)
            for key, item in vars(value).items()
            if not str(key).startswith("_")
        }
    return value


def _without_session_identity(value: Any) -> Any:
    value = _plain(value)
    if isinstance(value, dict):
        return {
            key: _without_session_identity(item)
            for key, item in value.items()
            if key != "session_id"
        }
    if isinstance(value, list):
        return [_without_session_identity(item) for item in value]
    return value


def _first_difference(control: Any, treatment: Any, *, path: str) -> tuple[str, Any, Any] | None:
    if type(control) is not type(treatment):
        return path, control, treatment
    if isinstance(control, dict):
        for key in sorted(set(control) | set(treatment)):
            child = f"{path}.{key}"
            if key not in control or key not in treatment:
                return child, control.get(key, "<missing>"), treatment.get(key, "<missing>")
            difference = _first_difference(control[key], treatment[key], path=child)
            if difference is not None:
                return difference
        return None
    if isinstance(control, list):
        if len(control) != len(treatment):
            return f"{path}.length", len(control), len(treatment)
        for index, (left, right) in enumerate(zip(control, treatment, strict=True)):
            difference = _first_difference(left, right, path=f"{path}[{index}]")
            if difference is not None:
                return difference
        return None
    return (path, control, treatment) if control != treatment else None


def _difference_record(difference: tuple[str, Any, Any]) -> dict[str, Any]:
    field, control, treatment = difference
    return {
        "field": field,
        "control_sha256": canonical_json_sha256(control),
        "treatment_sha256": canonical_json_sha256(treatment),
    }


def _observable_trace_payload(trajectory: Any) -> dict[str, Any]:
    """Remove artifact identity while retaining every observable rollout field."""

    value = _without_session_identity(trajectory)
    ignored = {
        "trajectory_id",
        "partition",
        "skill_library_version",
        "skill_delivery_mode",
        "exposed_skill_ids",
        "skill_memory_sha256",
        "created_at",
        "elapsed_seconds",
    }
    return {key: item for key, item in value.items() if key not in ignored}


def _exposed_ids(trajectory: Any) -> set[str]:
    return {str(item) for item in getattr(trajectory, "exposed_skill_ids", [])}


def skill_memory_delivery_issues(
    trajectory: Any,
    *,
    expected_ids: set[str],
    expected_memory: str | None = None,
) -> list[str]:
    """Audit the skill document actually present in every stored policy prompt.

    Trajectory-level IDs and hashes are declarations. This check independently
    extracts the system-prompt suffix seen by the lawyer, so stale metadata cannot
    make an absent, changed, or cross-turn skill document look delivered.
    """

    issues: list[str] = []
    actual = _exposed_ids(trajectory)
    expected_mode = "prompt_memory" if expected_ids else "none"
    if actual != expected_ids:
        issues.append("trajectory_exposed_skill_ids_mismatch")
    if str(getattr(trajectory, "skill_delivery_mode", "") or "") != expected_mode:
        issues.append("trajectory_skill_delivery_mode_mismatch")
    memory_sha = str(getattr(trajectory, "skill_memory_sha256", "") or "")
    if len(memory_sha) != 64:
        issues.append("trajectory_skill_memory_sha256_invalid")
    if expected_memory is not None and hashlib.sha256(
        expected_memory.encode("utf-8")
    ).hexdigest() != memory_sha:
        issues.append("trajectory_skill_memory_sha256_mismatch_expected_document")
    observed_memories: list[str] = []
    steps = list(getattr(trajectory, "steps", []))
    if not steps:
        issues.append("trajectory_has_no_policy_turn_for_skill_memory_audit")
    for step in steps:
        decision = getattr(step, "action_decision", None)
        retrieved = {str(item) for item in getattr(decision, "retrieved_skill_ids", [])}
        if retrieved != expected_ids:
            issues.append("turn_skill_memory_exposure_mismatch")
        if getattr(decision, "activated_skill_ids", []):
            issues.append("retired_runtime_skill_activation_observed")
        if any(
            isinstance(item, dict) and item.get("skill_id")
            for item in getattr(decision, "changes", [])
        ):
            issues.append("retired_runtime_skill_action_rewrite_observed")
        visible_input = list(getattr(step, "visible_input", []))
        system_messages = [
            item for item in visible_input if getattr(item, "role", None) == "system"
        ]
        if len(system_messages) != 1:
            issues.append("turn_policy_system_prompt_missing_or_ambiguous")
            continue
        try:
            rendered_memory = extract_rendered_skill_memory(
                str(system_messages[0].content)
            )
            prompt_ids = set(parse_rendered_skill_memory(rendered_memory))
        except (ValueError, TypeError, json.JSONDecodeError):
            issues.append("turn_skill_memory_document_unparseable")
            continue
        observed_memories.append(rendered_memory)
        if prompt_ids != expected_ids:
            issues.append("turn_actual_prompt_skill_ids_mismatch")
        if expected_memory is not None and rendered_memory != expected_memory:
            issues.append("turn_actual_prompt_skill_document_mismatch")
        if hashlib.sha256(rendered_memory.encode("utf-8")).hexdigest() != memory_sha:
            issues.append("turn_actual_prompt_skill_memory_sha256_mismatch")
    if len(set(observed_memories)) > 1:
        issues.append("session_skill_memory_changed_between_turns")
    return sorted(set(issues))


def skill_memory_contract_report(
    trajectories: list[ResearchTrajectory],
    expected_libraries: Mapping[str, list[SkillContract]],
) -> dict[str, Any]:
    """Bind every actual policy prompt to its executor-owned skill library.

    A trajectory's IDs and memory hash are self-declarations.  Formal callers
    therefore supply the exact library assigned to each intervention identity;
    the audit rerenders that library for the public case domain and compares the
    full document bytes actually seen on every policy turn.
    """

    rows: list[dict[str, Any]] = []
    for trajectory in trajectories:
        library_key = str(trajectory.skill_library_version)
        expected_skills = expected_libraries.get(library_key)
        if expected_skills is None:
            issues = ["trajectory_skill_library_identity_not_owned_by_executor"]
            expected_ids: list[str] = []
        else:
            expected_memory, expected_ids = render_skill_memory(
                expected_skills,
                domain=trajectory.domain,
            )
            issues = skill_memory_delivery_issues(
                trajectory,
                expected_ids=set(expected_ids),
                expected_memory=expected_memory,
            )
        rows.append(
            {
                "trajectory_id": trajectory.trajectory_id,
                "skill_library_version": library_key,
                "expected_exposed_skill_ids": expected_ids,
                "observed_exposed_skill_ids": list(trajectory.exposed_skill_ids),
                "passed": not issues,
                "issues": issues,
            }
        )
    failed = [row for row in rows if not row["passed"]]
    return {
        "schema_version": 1,
        "scope": "executor_owned_full_prompt_skill_document_before_scoring",
        "passed": not failed,
        "trajectory_count": len(rows),
        "failure_count": len(failed),
        "uses_reward_or_semantic_outcome": False,
        "rows": rows,
    }


def _library_key(trajectory: Any) -> tuple[str, str, int, int]:
    return (
        str(getattr(trajectory, "case_id", "") or ""),
        str(getattr(trajectory, "persona", "") or ""),
        int(getattr(trajectory, "seed", 0)),
        int(getattr(trajectory, "sample_index", 0)),
    )


def _audit_library_pair(
    empty: Any,
    current: Any,
    *,
    intervention_skill_ids: set[str],
    current_partition: str,
    empty_partition: str,
) -> dict[str, Any]:
    base = {
        "case_id": str(getattr(current, "case_id", "") or ""),
        "empty_trajectory_id": str(getattr(empty, "trajectory_id", "") or ""),
        "current_trajectory_id": str(getattr(current, "trajectory_id", "") or ""),
    }
    if getattr(current, "partition", None) != current_partition or getattr(
        empty, "partition", None
    ) != empty_partition:
        return {**base, "passed": False, "exposed": False,
                "reason": "skill_library_pair_partition_mismatch"}
    if (getattr(current, "method", None), getattr(empty, "method", None)) not in (
        _SKILL_LIBRARY_METHOD_PAIRS
    ):
        return {**base, "passed": False, "exposed": False,
                "reason": "skill_library_pair_method_mismatch"}
    if getattr(current, "skill_library_version", None) == getattr(
        empty, "skill_library_version", None
    ):
        return {**base, "passed": False, "exposed": False,
                "reason": "skill_library_intervention_missing"}
    for field in _SKILL_LIBRARY_IDENTITY_FIELDS:
        left = _plain(getattr(empty, field, None))
        right = _plain(getattr(current, field, None))
        if left != right:
            return {**base, "passed": False, "exposed": False,
                    "reason": "skill_library_pair_identity_mismatch",
                    "first_difference": _difference_record((f"trajectory.{field}", left, right))}
    empty_ids = _exposed_ids(empty)
    current_ids = _exposed_ids(current)
    if empty_ids or not current_ids <= intervention_skill_ids:
        return {**base, "passed": False, "exposed": bool(current_ids),
                "reason": "skill_library_prompt_exposure_mismatch",
                "empty_exposed_skill_ids": sorted(empty_ids),
                "current_exposed_skill_ids": sorted(current_ids)}
    issues = [
        *skill_memory_delivery_issues(empty, expected_ids=set()),
        *skill_memory_delivery_issues(current, expected_ids=current_ids),
    ]
    if issues:
        return {**base, "passed": False, "exposed": True,
                "reason": issues[0], "delivery_issues": sorted(set(issues))}
    if not current_ids:
        if getattr(empty, "skill_memory_sha256", None) != getattr(
            current, "skill_memory_sha256", None
        ):
            return {
                **base,
                "passed": False,
                "exposed": False,
                "reason": "nonapplicable_skill_memory_hash_drift",
            }
        difference = _first_difference(
            _observable_trace_payload(empty),
            _observable_trace_payload(current),
            path="trajectory",
        )
        if difference is not None:
            return {
                **base,
                "passed": False,
                "exposed": False,
                "reason": "nonapplicable_skill_trace_divergence",
                "first_difference": _difference_record(difference),
            }
        return {
            **base,
            "passed": True,
            "exposed": False,
            "exposed_intervention_skill_ids": [],
            "reason": "no_applicable_prompt_skill_trace_identical",
        }
    if getattr(empty, "skill_memory_sha256", None) == getattr(
        current, "skill_memory_sha256", None
    ):
        return {**base, "passed": False, "exposed": True,
                "reason": "skill_library_prompt_memory_intervention_missing"}
    return {**base, "passed": True, "exposed": True,
            "exposed_intervention_skill_ids": sorted(current_ids),
            "reason": "skill_library_is_sole_prompt_memory_intervention"}


def skill_library_intervention_isolation_report(
    current_trajectories: list[ResearchTrajectory],
    empty_trajectories: list[ResearchTrajectory],
    intervention_skill_ids: set[str],
    current_partition: str,
    empty_partition: str,
    *,
    require_distinct_partitions: bool = True,
) -> dict[str, Any]:
    """Audit current-library versus empty-library prompt-memory arms.

    Development shadow arms use distinct partitions.  The frozen external test
    deliberately stores its paired methods in one partition, so it opts out of
    only that storage-layout assertion while retaining every identity, prompt and
    skill-independent infrastructure check.  The skill-visible model-authored plan
    is intentionally allowed to differ and is part of the measured intervention.
    """

    declared = {str(item) for item in intervention_skill_ids}
    if not declared or "" in declared:
        raise ValueError("intervention_skill_ids must contain non-empty identifiers")
    matrix_failures: list[dict[str, Any]] = []
    if require_distinct_partitions and current_partition == empty_partition:
        matrix_failures.append({"reason": "skill_library_partitions_not_distinct"})

    def index(rows: list[ResearchTrajectory], partition: str, arm: str) -> dict[Any, list[Any]]:
        values: dict[Any, list[Any]] = defaultdict(list)
        if not rows:
            matrix_failures.append({"reason": f"{arm}_arm_empty"})
        for row in rows:
            if row.partition != partition:
                matrix_failures.append({"reason": f"{arm}_partition_mismatch",
                                        "trajectory_id": row.trajectory_id})
                continue
            values[_library_key(row)].append(row)
        return values

    current = index(current_trajectories, current_partition, "current_library")
    empty = index(empty_trajectories, empty_partition, "empty_library")
    pairs: list[dict[str, Any]] = []
    for key in sorted(set(current) | set(empty)):
        current_members = current.get(key, [])
        empty_members = empty.get(key, [])
        if len(current_members) != 1 or len(empty_members) != 1:
            matrix_failures.append({"case_id": key[0],
                                    "reason": "skill_library_pair_matrix_incomplete",
                                    "current_count": len(current_members),
                                    "empty_count": len(empty_members)})
            continue
        pairs.append(
            _audit_library_pair(
                empty_members[0], current_members[0],
                intervention_skill_ids=declared,
                current_partition=current_partition,
                empty_partition=empty_partition,
            )
        )
    failed = [item for item in pairs if not item["passed"]]
    return {
        "schema_version": 2,
        "scope": (
            "whole_skill_library_sole_prompt_memory_intervention_for_learning_curve"
            if require_distinct_partitions
            else "whole_skill_library_sole_prompt_memory_intervention_for_external_test"
        ),
        "passed": not failed and not matrix_failures,
        "current_partition": current_partition,
        "empty_partition": empty_partition,
        "intervention_skill_ids": sorted(declared),
        "pair_count": len(pairs),
        "exposed_pair_count": sum(bool(item["exposed"]) for item in pairs),
        "failed_pair_count": len(failed),
        "matrix_failure_count": len(matrix_failures),
        "failure_count": len(failed) + len(matrix_failures),
        "uses_reward_or_semantic_outcome": False,
        "pairs": pairs,
        "matrix_failures": matrix_failures,
    }
