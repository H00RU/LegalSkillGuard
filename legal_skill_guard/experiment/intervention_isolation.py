"""Sole-intervention checks for progressively disclosed skill memories.

Control and treatment share case, frozen policy snapshot and random stream.  The
declared intervention is a fixed session-level full-document bundle shown directly
to the frozen lawyer before each complete next-action decision. A public-opening-
only, non-binding inquiry agenda is shared byte-for-byte by both arms; it is common
infrastructure rather than a skill-conditioned planner or action selector.
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
    extract_rendered_experience_memory,
    extract_rendered_skill_memory,
    parse_rendered_experience_memory,
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
    "opening_inquiry_agenda",
    "opening_agenda_visible_input",
    "opening_agenda_attempts",
    "opening_agenda_safe_partial",
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
    expected_skills_by_id: Mapping[str, SkillContract] | None = None,
) -> list[str]:
    """Audit the catalog and model-selected execution cards actually delivered.

    Trajectory-level IDs and hashes are declarations. This check independently
    extracts the system-prompt suffix seen by the lawyer, so stale metadata cannot
    make an absent, changed, or cross-turn skill document look delivered.
    """

    issues: list[str] = []
    actual = _exposed_ids(trajectory)
    observed_mode = str(getattr(trajectory, "skill_delivery_mode", "") or "")
    expected_mode = observed_mode if expected_ids else "none"
    if actual != expected_ids:
        issues.append("trajectory_exposed_skill_ids_mismatch")
    if observed_mode != expected_mode or (
        expected_ids and observed_mode not in {"prompt_memory", "experience_memory"}
    ):
        issues.append("trajectory_skill_delivery_mode_mismatch")
    memory_sha = str(getattr(trajectory, "skill_memory_sha256", "") or "")
    if len(memory_sha) != 64:
        issues.append("trajectory_skill_memory_sha256_invalid")
    if (
        expected_memory is not None
        and hashlib.sha256(expected_memory.encode("utf-8")).hexdigest() != memory_sha
    ):
        issues.append("trajectory_skill_memory_sha256_mismatch_expected_document")
    observed_memories: list[str] = []
    actual_planner_ids = {
        str(item) for item in getattr(trajectory, "planner_exposed_skill_ids", [])
    }
    if actual_planner_ids:
        issues.append("retired_planner_skill_exposure_present")
    planner_sha = str(getattr(trajectory, "planner_skill_memory_sha256", "") or "")
    if len(planner_sha) != 64:
        issues.append("trajectory_planner_skill_memory_sha256_invalid")
    planning_input = list(getattr(trajectory, "planning_visible_input", []))
    planning_attempts = list(getattr(trajectory, "planning_attempts", []))
    initial_plan = getattr(trajectory, "initial_investigation_plan", None)
    initial_observations = list(
        (
            initial_plan.get("observations", [])
            if isinstance(initial_plan, Mapping)
            else getattr(initial_plan, "observations", [])
        )
        or []
    )
    if (
        planning_input
        or planning_attempts
        or initial_observations
        or bool(getattr(trajectory, "planning_safe_partial", False))
    ):
        issues.append("retired_planner_artifact_present")
    steps = list(getattr(trajectory, "steps", []))
    if not steps:
        issues.append("trajectory_has_no_policy_turn_for_skill_memory_audit")
    for step in steps:
        decision = getattr(step, "action_decision", None)
        retrieved = {str(item) for item in getattr(decision, "retrieved_skill_ids", [])}
        expected_turn_ids = expected_ids
        if retrieved != expected_turn_ids:
            issues.append("turn_skill_memory_exposure_mismatch")
        activated = [
            str(item) for item in getattr(decision, "activated_skill_ids", [])
        ]
        if activated:
            issues.append("retired_self_reported_skill_activation_present")
        if (
            getattr(step, "continuation_decision", None) is not None
            or getattr(step, "continuation_attempts", [])
            or getattr(step, "continuation_visible_input", [])
            or getattr(step, "target_selection_attempts", [])
        ):
            issues.append("retired_factored_policy_artifact_present")
        if any(
            isinstance(item, dict) and item.get("skill_id")
            for item in getattr(decision, "changes", [])
        ):
            issues.append("retired_runtime_skill_action_rewrite_observed")
        visible_input = list(getattr(step, "visible_input", []))
        prompt_views: list[tuple[str, list[Any]]] = [("policy", visible_input)]
        for stage, prompt_view in prompt_views:
            system_messages = [
                item for item in prompt_view if getattr(item, "role", None) == "system"
            ]
            if len(system_messages) != 1:
                issues.append(f"turn_{stage}_system_prompt_missing_or_ambiguous")
                continue
            try:
                if observed_mode == "experience_memory":
                    rendered_memory = extract_rendered_experience_memory(
                        str(system_messages[0].content)
                    )
                    prompt_ids = set(parse_rendered_experience_memory(rendered_memory))
                else:
                    rendered_memory = extract_rendered_skill_memory(
                        str(system_messages[0].content)
                    )
                    prompt_ids = set(parse_rendered_skill_memory(rendered_memory))
            except (ValueError, TypeError, json.JSONDecodeError):
                issues.append(f"turn_{stage}_skill_memory_document_unparseable")
                continue
            observed_memories.append(rendered_memory)
            if prompt_ids != expected_ids:
                issues.append(f"turn_{stage}_actual_prompt_skill_ids_mismatch")
            if expected_memory is not None and rendered_memory != expected_memory:
                issues.append(f"turn_{stage}_actual_prompt_skill_document_mismatch")
            if hashlib.sha256(rendered_memory.encode("utf-8")).hexdigest() != memory_sha:
                issues.append(f"turn_{stage}_actual_prompt_skill_memory_sha256_mismatch")
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
                expected_skills_by_id={skill.skill_id: skill for skill in expected_skills},
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
        "scope": "executor_owned_fixed_skill_documents_before_scoring",
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
    if (
        getattr(current, "partition", None) != current_partition
        or getattr(empty, "partition", None) != empty_partition
    ):
        return {
            **base,
            "passed": False,
            "exposed": False,
            "reason": "skill_library_pair_partition_mismatch",
        }
    if (getattr(current, "method", None), getattr(empty, "method", None)) not in (
        _SKILL_LIBRARY_METHOD_PAIRS
    ):
        return {
            **base,
            "passed": False,
            "exposed": False,
            "reason": "skill_library_pair_method_mismatch",
        }
    if getattr(current, "skill_library_version", None) == getattr(
        empty, "skill_library_version", None
    ):
        return {
            **base,
            "passed": False,
            "exposed": False,
            "reason": "skill_library_intervention_missing",
        }
    for field in _SKILL_LIBRARY_IDENTITY_FIELDS:
        left = _plain(getattr(empty, field, None))
        right = _plain(getattr(current, field, None))
        if left != right:
            return {
                **base,
                "passed": False,
                "exposed": False,
                "reason": "skill_library_pair_identity_mismatch",
                "first_difference": _difference_record((f"trajectory.{field}", left, right)),
            }
    empty_ids = _exposed_ids(empty)
    current_ids = _exposed_ids(current)
    if empty_ids or not current_ids <= intervention_skill_ids:
        return {
            **base,
            "passed": False,
            "exposed": bool(current_ids),
            "reason": "skill_library_prompt_exposure_mismatch",
            "empty_exposed_skill_ids": sorted(empty_ids),
            "current_exposed_skill_ids": sorted(current_ids),
        }
    issues = [
        *skill_memory_delivery_issues(empty, expected_ids=set()),
        *skill_memory_delivery_issues(
            current,
            expected_ids=current_ids,
        ),
    ]
    if issues:
        return {
            **base,
            "passed": False,
            "exposed": True,
            "reason": issues[0],
            "delivery_issues": sorted(set(issues)),
        }
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
    if getattr(empty, "skill_memory_sha256", None) == getattr(current, "skill_memory_sha256", None):
        return {
            **base,
            "passed": False,
            "exposed": True,
            "reason": "skill_library_prompt_memory_intervention_missing",
        }
    return {
        **base,
        "passed": True,
        "exposed": True,
        "exposed_intervention_skill_ids": sorted(current_ids),
        "reason": "skill_library_is_sole_policy_memory_intervention",
    }


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
    skill-independent infrastructure check. The global playbook is delivered
    directly to the policy; the opening-only agenda must remain identical and is
    never part of the intervention.
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
                matrix_failures.append(
                    {"reason": f"{arm}_partition_mismatch", "trajectory_id": row.trajectory_id}
                )
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
            matrix_failures.append(
                {
                    "case_id": key[0],
                    "reason": "skill_library_pair_matrix_incomplete",
                    "current_count": len(current_members),
                    "empty_count": len(empty_members),
                }
            )
            continue
        pairs.append(
            _audit_library_pair(
                empty_members[0],
                current_members[0],
                intervention_skill_ids=declared,
                current_partition=current_partition,
                empty_partition=empty_partition,
            )
        )
    failed = [item for item in pairs if not item["passed"]]
    return {
        "schema_version": 3,
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


def final_training_holdout_intervention_isolation_report(
    selected_trajectories: list[ResearchTrajectory],
    empty_trajectories: list[ResearchTrajectory],
    selected_skill_ids: set[str],
    selected_partition: str,
    empty_partition: str,
) -> dict[str, Any]:
    """Audit the library intervention used by the final B8 freeze safeguard.

    This wrapper keeps the safeguard's engineering role explicit and also gives
    an empty selected library a deterministic fail-closed artifact.  The ordinary
    skill-library isolation audit deliberately rejects an empty intervention and
    remains unchanged for development and external-effect analyses.
    """

    declared = {str(item) for item in selected_skill_ids}
    if not declared or "" in declared:
        return {
            "schema_version": 1,
            "scope": "same_B8_accumulated_library_diagnostic",
            "claim_role": (
                "cumulative_library_diagnostic_not_independent_confirmatory_claim"
            ),
            "passed": False,
            "selected_partition": selected_partition,
            "empty_partition": empty_partition,
            "selected_skill_ids": sorted(declared),
            "failure_count": 1,
            "failure_reasons": ["selected_library_is_empty"],
            "underlying_skill_library_isolation": None,
            "uses_reward_or_semantic_outcome": False,
        }
    underlying = skill_library_intervention_isolation_report(
        selected_trajectories,
        empty_trajectories,
        declared,
        selected_partition,
        empty_partition,
    )
    return {
        "schema_version": 1,
        "scope": "same_B8_accumulated_library_diagnostic",
        "claim_role": "cumulative_library_diagnostic_not_independent_confirmatory_claim",
        "passed": underlying.get("passed") is True,
        "selected_partition": selected_partition,
        "empty_partition": empty_partition,
        "selected_skill_ids": sorted(declared),
        "failure_count": int(underlying.get("failure_count", 0)),
        "failure_reasons": sorted(
            {
                str(item.get("reason"))
                for item in [
                    *underlying.get("pairs", []),
                    *underlying.get("matrix_failures", []),
                ]
                if isinstance(item, Mapping)
                and item.get("passed") is not True
                and item.get("reason")
            }
        ),
        "underlying_skill_library_isolation": underlying,
        "uses_reward_or_semantic_outcome": False,
    }


def parent_library_intervention_isolation_report(
    current_trajectories: list[ResearchTrajectory],
    parent_trajectories: list[ResearchTrajectory],
    current_skills: list[SkillContract],
    parent_skills: list[SkillContract],
    current_partition: str,
    parent_partition: str,
) -> dict[str, Any]:
    """Audit a created-or-updated playbook increment against its exact parent.

    The parent arm may itself expose skills.  We therefore rerender both complete
    executor-owned libraries, require every unchanged parent artifact to be
    byte-equivalent, and prove that only the declared created or updated playbook
    can change prompt memory.  The renderer retains domain routing only for frozen
    comparison arms; the current method exposes one global playbook to every case.
    """

    current_by_id = {skill.skill_id: skill for skill in current_skills}
    parent_by_id = {skill.skill_id: skill for skill in parent_skills}
    matrix_failures: list[dict[str, Any]] = []
    if len(current_by_id) != len(current_skills) or len(parent_by_id) != len(parent_skills):
        matrix_failures.append({"reason": "duplicate_skill_id_in_declared_library"})
    current_ids = set(current_by_id)
    parent_ids = set(parent_by_id)
    changed_parent_ids = {
        skill_id
        for skill_id in parent_ids & current_ids
        if canonical_json_sha256(_plain(parent_by_id[skill_id]))
        != canonical_json_sha256(_plain(current_by_id[skill_id]))
    }
    cohort_ids = (current_ids - parent_ids) | changed_parent_ids
    if not cohort_ids or not parent_ids <= current_ids:
        matrix_failures.append(
            {"reason": "current_library_has_no_created_or_updated_playbook_increment"}
        )
    changed_outside_cohort = sorted(
        skill_id
        for skill_id in parent_ids & current_ids
        if skill_id not in cohort_ids
        if canonical_json_sha256(_plain(parent_by_id[skill_id]))
        != canonical_json_sha256(_plain(current_by_id[skill_id]))
    )
    if changed_outside_cohort:
        matrix_failures.append(
            {
                "reason": "parent_skill_document_changed_outside_declared_increment",
                "skill_ids": changed_outside_cohort,
            }
        )
    invalid_update_versions = sorted(
        skill_id
        for skill_id in changed_parent_ids
        if tuple(int(item) for item in current_by_id[skill_id].version.split("."))
        != (
            int(parent_by_id[skill_id].version.split(".")[0]),
            int(parent_by_id[skill_id].version.split(".")[1]),
            int(parent_by_id[skill_id].version.split(".")[2]) + 1,
        )
    )
    if invalid_update_versions:
        matrix_failures.append(
            {
                "reason": "updated_playbook_version_not_incremented",
                "skill_ids": invalid_update_versions,
            }
        )
    if current_partition == parent_partition:
        matrix_failures.append({"reason": "parent_cohort_partitions_not_distinct"})

    def index(rows: list[ResearchTrajectory], partition: str, arm: str) -> dict[Any, list[Any]]:
        values: dict[Any, list[Any]] = defaultdict(list)
        if not rows:
            matrix_failures.append({"reason": f"{arm}_arm_empty"})
        for row in rows:
            if row.partition != partition:
                matrix_failures.append(
                    {"reason": f"{arm}_partition_mismatch", "trajectory_id": row.trajectory_id}
                )
                continue
            values[_library_key(row)].append(row)
        return values

    current = index(current_trajectories, current_partition, "accumulated_current_library")
    parent = index(parent_trajectories, parent_partition, "exact_parent_library")
    pairs: list[dict[str, Any]] = []
    for key in sorted(set(current) | set(parent)):
        current_members = current.get(key, [])
        parent_members = parent.get(key, [])
        if len(current_members) != 1 or len(parent_members) != 1:
            matrix_failures.append(
                {
                    "case_id": key[0],
                    "reason": "parent_cohort_pair_matrix_incomplete",
                    "current_count": len(current_members),
                    "parent_count": len(parent_members),
                }
            )
            continue
        current_row = current_members[0]
        parent_row = parent_members[0]
        base = {
            "case_id": str(current_row.case_id),
            "parent_trajectory_id": str(parent_row.trajectory_id),
            "current_trajectory_id": str(current_row.trajectory_id),
        }
        failure: dict[str, Any] | None = None
        if (current_row.method, parent_row.method) not in _SKILL_LIBRARY_METHOD_PAIRS:
            failure = {**base, "reason": "parent_cohort_pair_method_mismatch"}
        elif current_row.skill_library_version == parent_row.skill_library_version:
            failure = {**base, "reason": "parent_cohort_intervention_missing"}
        else:
            for field in _SKILL_LIBRARY_IDENTITY_FIELDS:
                left = _plain(getattr(parent_row, field, None))
                right = _plain(getattr(current_row, field, None))
                if left != right:
                    failure = {
                        **base,
                        "reason": "parent_cohort_pair_identity_mismatch",
                        "first_difference": _difference_record(
                            (f"trajectory.{field}", left, right)
                        ),
                    }
                    break
        if failure is not None:
            pairs.append({**failure, "passed": False, "cohort_exposed": False})
            continue

        parent_memory, expected_parent_ids = render_skill_memory(
            parent_skills, domain=parent_row.domain
        )
        current_memory, expected_current_ids = render_skill_memory(
            current_skills, domain=current_row.domain
        )
        expected_parent = set(expected_parent_ids)
        expected_current = set(expected_current_ids)
        parent_by_id = {skill.skill_id: skill for skill in parent_skills}
        current_by_id = {skill.skill_id: skill for skill in current_skills}
        expected_changed = {
            skill_id
            for skill_id in expected_current
            if skill_id not in parent_by_id
            or canonical_json_sha256(
                current_by_id[skill_id].model_dump(
                    mode="json", exclude={"status", "evaluation"}
                )
            )
            != canonical_json_sha256(
                parent_by_id[skill_id].model_dump(
                    mode="json", exclude={"status", "evaluation"}
                )
            )
        }
        if not expected_changed <= cohort_ids:
            pairs.append(
                {
                    **base,
                    "passed": False,
                    "cohort_exposed": bool(expected_changed),
                    "reason": "parent_cohort_playbook_change_mismatch",
                    "expected_parent_skill_ids": sorted(expected_parent),
                    "expected_current_skill_ids": sorted(expected_current),
                }
            )
            continue
        delivery_issues = [
            *skill_memory_delivery_issues(
                parent_row,
                expected_ids=expected_parent,
                expected_memory=parent_memory,
            ),
            *skill_memory_delivery_issues(
                current_row,
                expected_ids=expected_current,
                expected_memory=current_memory,
            ),
        ]
        if delivery_issues:
            pairs.append(
                {
                    **base,
                    "passed": False,
                    "cohort_exposed": bool(expected_changed),
                    "reason": sorted(set(delivery_issues))[0],
                    "delivery_issues": sorted(set(delivery_issues)),
                }
            )
            continue
        if not expected_changed:
            if (
                parent_memory != current_memory
                or parent_row.skill_memory_sha256 != current_row.skill_memory_sha256
            ):
                pairs.append(
                    {
                        **base,
                        "passed": False,
                        "cohort_exposed": False,
                        "reason": "nonapplicable_cohort_prompt_memory_drift",
                    }
                )
                continue
            difference = _first_difference(
                _observable_trace_payload(parent_row),
                _observable_trace_payload(current_row),
                path="trajectory",
            )
            if difference is not None:
                pairs.append(
                    {
                        **base,
                        "passed": False,
                        "cohort_exposed": False,
                        "reason": "nonapplicable_cohort_trace_divergence",
                        "first_difference": _difference_record(difference),
                    }
                )
                continue
            pairs.append(
                {
                    **base,
                    "passed": True,
                    "cohort_exposed": False,
                    "exposed_cohort_skill_ids": [],
                    "reason": "no_applicable_cohort_skill_trace_identical",
                }
            )
            continue
        if parent_memory == current_memory or parent_row.skill_memory_sha256 == (
            current_row.skill_memory_sha256
        ):
            pairs.append(
                {
                    **base,
                    "passed": False,
                    "cohort_exposed": True,
                    "reason": "applicable_cohort_prompt_memory_intervention_missing",
                }
            )
            continue
        pairs.append(
            {
                **base,
                "passed": True,
                "cohort_exposed": True,
                "exposed_cohort_skill_ids": sorted(expected_changed),
                "reason": "exact_cohort_is_sole_policy_memory_intervention",
            }
        )

    failed = [item for item in pairs if not item["passed"]]
    current_rows = [members[0] for members in current.values() if len(members) == 1]
    cohort_skill_exposure: dict[str, dict[str, Any]] = {}
    for skill_id in sorted(cohort_ids):
        skill = current_by_id[skill_id]
        expected_rows = [
            row
            for row in current_rows
            if skill.domain == "general" or row.domain == skill.domain
        ]
        expected_case_ids = {str(row.case_id) for row in expected_rows}
        observed_pairs = [
            item
            for item in pairs
            if skill_id in set(item.get("exposed_cohort_skill_ids") or [])
        ]
        observed_case_ids = {str(item["case_id"]) for item in observed_pairs}
        cohort_skill_exposure[skill_id] = {
            "domain": skill.domain,
            "expected_case_count": len(expected_case_ids),
            "expected_pair_count": len(expected_rows),
            "observed_case_count": len(observed_case_ids),
            "observed_pair_count": len(observed_pairs),
            "routing_complete": (
                len(observed_pairs) == len(expected_rows)
                and observed_case_ids == expected_case_ids
            ),
        }
    return {
        "schema_version": 1,
        "scope": "new_skill_increment_sole_change_from_exact_parent_library",
        "passed": not failed and not matrix_failures,
        "current_partition": current_partition,
        "parent_partition": parent_partition,
        "current_skill_ids": sorted(current_ids),
        "parent_skill_ids": sorted(parent_ids),
        "new_skill_increment_ids": sorted(cohort_ids),
        "pair_count": len(pairs),
        "cohort_exposed_pair_count": sum(bool(item["cohort_exposed"]) for item in pairs),
        "cohort_exposed_case_count": len(
            {str(item["case_id"]) for item in pairs if item["cohort_exposed"]}
        ),
        "cohort_skill_exposure": cohort_skill_exposure,
        "failed_pair_count": len(failed),
        "matrix_failure_count": len(matrix_failures),
        "failure_count": len(failed) + len(matrix_failures),
        "uses_reward_or_semantic_outcome": False,
        "pairs": pairs,
        "matrix_failures": matrix_failures,
    }
