#!/usr/bin/env python3
"""Read-only monitor for the schema-4 sequential prospective main run.

Only hash-bound schema-4 checkpoints and their bound prequential curve points count
as frozen development evidence.  Raw trajectories and uncheckpointed curve files
are reported as resumable diagnostics, never as paper results.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

from legal_skill_guard.experiment.executor import (
    implementation_sha256,
    load_formal_initial_skill_library,
)
from legal_skill_guard.schemas.experiment import (
    CURRENT_TRAJECTORY_SCHEMA_VERSION,
    ResearchTrajectory,
)
from legal_skill_guard.utils.hashing import canonical_json_sha256, sha256_file

ROOT = Path(__file__).resolve().parents[1]

TERMINAL_OK = {"memo_submitted", "abstained"}
TRAJECTORY_SCHEMA = CURRENT_TRAJECTORY_SCHEMA_VERSION
EVALUATION_SCHEMA = 13
CHECKPOINT_SCHEMA = 4
LEARNING_CHECKPOINT_SCHEMA = 2
CURVE_POINT_SCHEMA = 1
CURVE_SUMMARY_SCHEMA = 1
CURVE_METRICS = (
    "resolution",
    "elicitation",
    "fidelity",
    "critical_fact_recall",
    "repeated_question_rate",
    "policy_fallback_rate",
    "reward",
    "question_turns",
    "unique_disclosed_facts",
    "unique_disclosed_facts_per_question",
    "identified_evidence_gaps",
)
CORE_CURVE_METRICS = (
    "resolution",
    "elicitation",
    "critical_fact_recall",
    "reward",
    "unique_disclosed_facts",
    "unique_disclosed_facts_per_question",
    "question_turns",
    "repeated_question_rate",
)


def _json_object(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _manifest(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    value = _json_object(path)
    if value is None:
        return None, "missing_or_unreadable"
    declared = value.get("content_sha256")
    content = {key: item for key, item in value.items() if key != "content_sha256"}
    if not isinstance(declared, str):
        return None, "missing_content_sha256"
    if canonical_json_sha256(content) != declared:
        return None, "content_sha256_mismatch"
    return value, None


def _artifact_ok(root: Path, record: object) -> bool:
    if not isinstance(record, dict):
        return False
    relative_value = record.get("path")
    expected = record.get("sha256")
    if not isinstance(relative_value, str) or not isinstance(expected, str):
        return False
    relative = Path(relative_value)
    if relative.is_absolute() or ".." in relative.parts:
        return False
    path = root / relative
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return path.is_file() and sha256_file(path) == expected


def _artifact_matches(root: Path, record: object, expected_path: Path) -> bool:
    """Verify both artifact bytes and the protocol-owned path."""

    if not _artifact_ok(root, record) or not isinstance(record, dict):
        return False
    return (root / str(record["path"])).resolve() == expected_path.resolve()


def _string_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _finite_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _curve_metric_delta(metric: object) -> dict[str, Any] | None:
    if not isinstance(metric, dict):
        return None
    estimate = metric.get("case_cluster_estimate")
    if not isinstance(estimate, dict):
        return None
    required = (
        metric.get("empty_library_mean"),
        metric.get("current_library_mean"),
        metric.get("pair_mean_delta"),
        estimate.get("mean_delta"),
        estimate.get("lower"),
        estimate.get("upper"),
    )
    if not all(_finite_number(item) for item in required):
        return None
    return {
        "empty_library_mean": metric["empty_library_mean"],
        "current_library_mean": metric["current_library_mean"],
        "mean_delta": estimate["mean_delta"],
        "confidence_lower": estimate["lower"],
        "confidence_upper": estimate["upper"],
    }


def _development_curve_point_contract(
    root: Path,
    run_id: str,
    batch_id: str,
    round_index: int,
    run_manifest_sha256: str | None,
    *,
    expected_pair_count: int,
    expected_sentinel_ids: list[str] | None = None,
    expected_evidence_role: str | None = None,
    bound_record: object | None = None,
    expected_input_ids: object | None = None,
    expected_input_hash: object | None = None,
) -> dict[str, Any]:
    """Validate one curve point and distinguish diagnostics from bound evidence."""

    path = root / "runs" / run_id / "reports" / f"development_curve_point_{round_index:02d}.json"
    value = _json_object(path)
    if value is None:
        return {
            "status": "absent" if not path.exists() else "invalid",
            "issues": [] if not path.exists() else ["curve_point_unreadable"],
        }

    issues: list[str] = []
    hash_bound = bound_record is not None
    if hash_bound and not _artifact_matches(root, bound_record, path):
        issues.append("curve_point_artifact_mismatch")
    expected_fields = {
        "schema_version",
        "run_id",
        "run_manifest_sha256",
        "round",
        "batch_id",
        "case_limit",
        "status",
        "evidence_role",
        "sentinel_case_ids",
        "input_active_skill_ids",
        "input_skill_library_sha256",
        "empty_skill_library_sha256",
        "identity_baseline",
        "current_trajectory_artifacts",
        "current_evaluation_artifacts",
        "empty_trajectory_artifacts",
        "empty_evaluation_artifacts",
        "intervention_isolation_artifact",
        "curve",
        "completed_at",
    }
    if set(value) != expected_fields:
        issues.append("curve_point_fields_drift")
    if not (
        value.get("schema_version") == CURVE_POINT_SCHEMA
        and value.get("run_id") == run_id
        and value.get("run_manifest_sha256") == run_manifest_sha256
        and value.get("round") == round_index
        and value.get("batch_id") == batch_id
        and value.get("status") == "prequential_fixed_shadow_complete"
        and isinstance(value.get("evidence_role"), str)
        and (
            expected_evidence_role is None
            or value.get("evidence_role") == expected_evidence_role
        )
        and isinstance(value.get("identity_baseline"), bool)
    ):
        issues.append("curve_point_binding_mismatch")
    input_ids = value.get("input_active_skill_ids")
    if not _string_list(input_ids) or input_ids != sorted(set(input_ids or [])):
        issues.append("curve_input_skill_ids_invalid")
    if expected_input_ids is not None and input_ids != expected_input_ids:
        issues.append("curve_input_skill_ids_mismatch")
    if (
        expected_input_hash is not None
        and value.get("input_skill_library_sha256") != expected_input_hash
    ):
        issues.append("curve_input_skill_hash_mismatch")
    sentinels = value.get("sentinel_case_ids")
    if not _string_list(sentinels) or not sentinels or len(sentinels) != len(set(sentinels or [])):
        issues.append("curve_sentinel_set_invalid")
    if expected_sentinel_ids is not None and sentinels != expected_sentinel_ids:
        issues.append("curve_sentinel_set_mismatch")

    curve = value.get("curve")
    metrics: dict[str, Any] = {}
    pair_rows: list[Any] = []
    case_rows: list[Any] = []
    if not isinstance(curve, dict):
        issues.append("curve_statistics_missing")
    else:
        if not (
            curve.get("report_type") == "prequential_current_library_vs_empty_library"
            and curve.get("sentinel_id") == batch_id
            and curve.get("direction") == "current_library_minus_empty_library"
            and curve.get("identity_baseline") is value.get("identity_baseline")
            and curve.get("current_library_version")
            == value.get("input_skill_library_sha256")
            and curve.get("empty_library_version") == value.get("empty_skill_library_sha256")
            and curve.get("current_skill_ids") == input_ids
            and curve.get("pair_count") == expected_pair_count
            and curve.get("partition_mapping")
            == {
                "current": batch_id,
                "empty": (
                    batch_id
                    if value.get("identity_baseline") is True
                    else f"learning_curve_shadow_{batch_id}"
                ),
            }
        ):
            issues.append("curve_statistics_binding_mismatch")
        pair_rows = curve.get("pairs") if isinstance(curve.get("pairs"), list) else []
        case_rows = curve.get("cases") if isinstance(curve.get("cases"), list) else []
        if len(pair_rows) != expected_pair_count:
            issues.append("curve_pair_matrix_incomplete")
        if (
            not sentinels
            or curve.get("case_cluster_count") != len(sentinels)
            or len(case_rows) != len(sentinels)
            or {str(row.get("case_id")) for row in case_rows if isinstance(row, dict)}
            != set(sentinels)
        ):
            issues.append("curve_case_clusters_incomplete")
        metrics = curve.get("metrics") if isinstance(curve.get("metrics"), dict) else {}
        if set(metrics) != set(CURVE_METRICS):
            issues.append("curve_metric_set_mismatch")
        if any(_curve_metric_delta(metrics.get(name)) is None for name in CURVE_METRICS):
            issues.append("curve_metric_statistics_invalid")

    current_ids = {
        str(row.get("current_trajectory_id"))
        for row in pair_rows
        if isinstance(row, dict) and isinstance(row.get("current_trajectory_id"), str)
    }
    empty_ids = {
        str(row.get("empty_trajectory_id"))
        for row in pair_rows
        if isinstance(row, dict) and isinstance(row.get("empty_trajectory_id"), str)
    }
    run_root = root / "runs" / run_id
    for field, expected_ids, base in (
        ("current_trajectory_artifacts", current_ids, run_root / "trajectories" / batch_id),
        ("current_evaluation_artifacts", current_ids, run_root / "evaluations"),
    ):
        records = value.get(field)
        if (
            not isinstance(records, dict)
            or set(records) != expected_ids
            or not all(
                _artifact_matches(root, records[trajectory_id], base / f"{trajectory_id}.json")
                for trajectory_id in expected_ids
            )
        ):
            issues.append(f"{field}_mismatch")

    identity = value.get("identity_baseline") is True
    empty_trajectory_records = value.get("empty_trajectory_artifacts")
    empty_evaluation_records = value.get("empty_evaluation_artifacts")
    if identity:
        if (
            input_ids != []
            or value.get("input_skill_library_sha256")
            != value.get("empty_skill_library_sha256")
            or empty_trajectory_records != {}
            or empty_evaluation_records != {}
            or value.get("intervention_isolation_artifact") is not None
            or empty_ids != current_ids
        ):
            issues.append("identity_curve_contract_mismatch")
        for name in CURVE_METRICS:
            delta = _curve_metric_delta(metrics.get(name))
            if delta is not None and any(
                float(delta[field]) != 0.0
                for field in ("mean_delta", "confidence_lower", "confidence_upper")
            ):
                issues.append("identity_curve_nonzero_delta")
                break
        isolation_status = "identity_by_construction"
    else:
        for field, records, base in (
            (
                "empty_trajectory_artifacts",
                empty_trajectory_records,
                run_root / "trajectories" / f"learning_curve_shadow_{batch_id}",
            ),
            ("empty_evaluation_artifacts", empty_evaluation_records, run_root / "evaluations"),
        ):
            if (
                not isinstance(records, dict)
                or set(records) != empty_ids
                or not all(
                    _artifact_matches(
                        root, records[trajectory_id], base / f"{trajectory_id}.json"
                    )
                    for trajectory_id in empty_ids
                )
            ):
                issues.append(f"{field}_mismatch")
        isolation_path = (
            root
            / "runs"
            / run_id
            / "health"
            / f"development_curve_intervention_isolation_{batch_id}.json"
        )
        isolation_record = value.get("intervention_isolation_artifact")
        isolation = _json_object(isolation_path)
        if not _artifact_matches(root, isolation_record, isolation_path) or not (
            isolation
            and isolation.get("passed") is True
            and isolation.get("pair_count") == expected_pair_count
            and isolation.get("current_partition") == batch_id
            and isolation.get("empty_partition") == f"learning_curve_shadow_{batch_id}"
        ):
            issues.append("curve_intervention_isolation_mismatch")
            isolation_status = "invalid"
        else:
            isolation_status = "verified"

    core_deltas = {
        name: delta
        for name in CORE_CURVE_METRICS
        if (delta := _curve_metric_delta(metrics.get(name))) is not None
    }
    status = "invalid" if issues else ("verified" if hash_bound else "diagnostic_uncheckpointed")
    return {
        "status": status,
        "hash_bound_by_checkpoint": hash_bound and not issues,
        "issues": sorted(set(issues)),
        "identity_baseline": value.get("identity_baseline"),
        "evidence_role": value.get("evidence_role"),
        "sentinel_case_ids": sentinels if _string_list(sentinels) else [],
        "pair_count": curve.get("pair_count") if isinstance(curve, dict) else None,
        "case_cluster_count": (
            curve.get("case_cluster_count") if isinstance(curve, dict) else None
        ),
        "input_active_skill_ids": input_ids if _string_list(input_ids) else [],
        "input_skill_library_sha256": value.get("input_skill_library_sha256"),
        "intervention_isolation": isolation_status,
        "core_metric_deltas": core_deltas,
        "artifact": _record_for_report(root, path),
    }


def _record_for_report(root: Path, path: Path) -> dict[str, str] | None:
    if not path.is_file():
        return None
    try:
        relative = path.resolve().relative_to(root.resolve())
    except ValueError:
        return None
    return {"path": str(relative), "sha256": sha256_file(path)}


def classify_batch_progress(
    *, expected: int, successful: int, errors: int, checkpoint_stage: str | None
) -> tuple[str, list[str]]:
    """Classify process progress without turning weak model yield into corruption."""

    if successful < expected:
        if errors:
            return "resumable_rollout_failure", [
                "error_trajectories_must_be_rerun",
                "complete_matrix_required_before_scoring",
            ]
        return "rollout_in_progress", ["complete_matrix_required_before_scoring"]
    if checkpoint_stage == "complete":
        return "complete", []
    if checkpoint_stage == "provisionals_ready":
        return "block_completion_pending", []
    return "rollout_complete_downstream_pending", []


def _run_manifest_contract(
    root: Path,
    run_id: str,
    *,
    experiment_path: Path,
    roles_path: Path,
    data_path: Path,
    batch_path: Path,
    experiment: dict[str, Any],
) -> dict[str, Any]:
    path = root / "runs" / run_id / "manifests/run.json"
    manifest, error = _manifest(path)
    if manifest is None:
        return {"status": "unverified", "error": error, "path": str(path)}
    try:
        _, initial_binding = load_formal_initial_skill_library(root, experiment)
        initial_library_error = None
    except (OSError, ValueError, RuntimeError, yaml.YAMLError) as exc:
        initial_binding = {"path": None, "id": None, "sha256": None}
        initial_library_error = str(exc)
    checks = {
        "schema_version": manifest.get("schema_version") == 3,
        "run_id": manifest.get("run_id") == run_id,
        "experiment_config": manifest.get("experiment_config_sha256")
        == sha256_file(experiment_path),
        "roles_config": manifest.get("roles_config_sha256") == sha256_file(roles_path),
        "data_config": manifest.get("data_config_sha256") == sha256_file(data_path),
        "training_batch_plan": manifest.get("training_batch_plan_sha256")
        == sha256_file(batch_path),
        "initial_skill_library_path": manifest.get("initial_skill_library_path")
        == initial_binding["path"],
        "initial_skill_library_id": manifest.get("initial_skill_library_id")
        == initial_binding["id"],
        "initial_skill_library_sha256": manifest.get("initial_skill_library_sha256")
        == initial_binding["sha256"],
        "implementation": manifest.get("implementation_sha256") == implementation_sha256(root),
    }
    return {
        "status": "verified" if all(checks.values()) else "invalid",
        "checks": checks,
        "initial_skill_library_error": initial_library_error,
        "sha256": sha256_file(path),
        "path": str(path.relative_to(root)),
    }


def _checkpoint_contract(
    root: Path,
    run_id: str,
    batch_id: str,
    round_index: int,
    run_manifest_sha256: str | None,
    *,
    expected_pair_count: int,
    expected_sentinel_ids: list[str],
    expected_evidence_role: str,
) -> dict[str, Any]:
    run_root = root / "runs" / run_id
    ready_path = run_root / "manifests" / f"{batch_id}__provisionals_ready.json"
    complete_path = run_root / "manifests" / f"{batch_id}__complete.json"
    ready, ready_error = _manifest(ready_path)
    complete, complete_error = _manifest(complete_path)
    if ready is None:
        return {
            "status": "absent" if not ready_path.exists() else "invalid",
            "stage": None,
            "issues": [ready_error] if ready_path.exists() else [],
        }
    issues: list[str] = []
    ready_fields = {
        "schema_version",
        "run_id",
        "run_manifest_sha256",
        "round",
        "batch_id",
        "stage",
        "case_limit",
        "trajectory_schema_version",
        "evaluation_schema_version",
        "judge_qualification_contract_sha256",
        "input_active_skill_ids",
        "input_skill_library_sha256",
        "expected_matrix",
        "expected_matrix_sha256",
        "trajectory_artifacts",
        "evaluation_artifacts",
        "pre_scoring_health_artifact",
        "development_curve_artifact",
        "provisional_artifacts",
        "content_sha256",
    }
    if not (
        set(ready) == ready_fields
        and ready.get("schema_version") == CHECKPOINT_SCHEMA
        and ready.get("run_id") == run_id
        and ready.get("round") == round_index
        and ready.get("batch_id") == batch_id
        and ready.get("stage") == "provisionals_ready"
        and ready.get("run_manifest_sha256") == run_manifest_sha256
        and ready.get("trajectory_schema_version") == TRAJECTORY_SCHEMA
        and ready.get("evaluation_schema_version") == EVALUATION_SCHEMA
    ):
        issues.append("provisionals_ready_binding_mismatch")
    matrix = ready.get("expected_matrix")
    if not isinstance(matrix, list) or ready.get("expected_matrix_sha256") != canonical_json_sha256(
        matrix
    ):
        issues.append("expected_matrix_mismatch")
    for field, base in (
        ("trajectory_artifacts", run_root / "trajectories" / batch_id),
        ("evaluation_artifacts", run_root / "evaluations"),
    ):
        records = ready.get(field)
        expected_ids = {
            str(item.get("trajectory_id")) for item in matrix or [] if isinstance(item, dict)
        }
        if not isinstance(records, dict) or set(records) != expected_ids:
            issues.append(f"{field}_set_mismatch")
        elif not all(
            _artifact_matches(root, records[trajectory_id], base / f"{trajectory_id}.json")
            for trajectory_id in expected_ids
        ):
            issues.append(f"{field}_content_mismatch")
    if not _artifact_matches(
        root,
        ready.get("pre_scoring_health_artifact"),
        run_root / "health" / f"pre_scoring_health_{batch_id}.json",
    ):
        issues.append("pre_scoring_health_artifact_mismatch")
    provisionals = ready.get("provisional_artifacts")
    provisional_ids = [
        str(record.get("skill_id"))
        for record in provisionals or []
        if isinstance(record, dict) and isinstance(record.get("skill_id"), str)
    ]
    if (
        not isinstance(provisionals, list)
        or len(provisional_ids) != len(provisionals)
        or len(provisional_ids) != len(set(provisional_ids))
        or not all(
            isinstance(record, dict)
            and set(record) == {"path", "sha256", "skill_id", "contract_sha256"}
            and isinstance(record.get("contract_sha256"), str)
            and _artifact_matches(
                root,
                record,
                run_root / "skills" / "candidates" / f"{record['skill_id']}.yaml",
            )
            for record in provisionals or []
        )
    ):
        issues.append("provisional_artifacts_mismatch")
    input_ids = ready.get("input_active_skill_ids")
    if not _string_list(input_ids) or input_ids != sorted(set(input_ids or [])):
        issues.append("input_skill_ids_invalid")
    curve = _development_curve_point_contract(
        root,
        run_id,
        batch_id,
        round_index,
        run_manifest_sha256,
        expected_pair_count=expected_pair_count,
        expected_sentinel_ids=expected_sentinel_ids,
        expected_evidence_role=expected_evidence_role,
        bound_record=ready.get("development_curve_artifact"),
        expected_input_ids=input_ids,
        expected_input_hash=ready.get("input_skill_library_sha256"),
    )
    if curve["status"] != "verified":
        issues.append("development_curve_artifact_mismatch")
    if issues:
        return {
            "status": "invalid",
            "stage": "provisionals_ready",
            "issues": sorted(set(issues)),
            "development_curve": curve,
        }
    if complete is None:
        if complete_path.exists():
            return {
                "status": "invalid",
                "stage": "provisionals_ready",
                "issues": [complete_error],
            }
        return {
            "status": "verified",
            "stage": "provisionals_ready",
            "provisional_skill_ids": sorted(provisional_ids),
            "input_active_skill_ids": input_ids,
            "input_skill_library_sha256": ready.get("input_skill_library_sha256"),
            "development_curve": curve,
            "ready_sha256": sha256_file(ready_path),
        }
    complete_fields = {
        "schema_version",
        "run_id",
        "run_manifest_sha256",
        "round",
        "batch_id",
        "stage",
        "case_limit",
        "trajectory_schema_version",
        "evaluation_schema_version",
        "judge_qualification_contract_sha256",
        "pre_validation_active_skill_ids",
        "pre_validation_skill_library_sha256",
        "accepted_skill_ids",
        "training_input_active_skill_ids",
        "training_input_skill_library_sha256",
        "expected_matrix_sha256",
        "provisionals_ready_manifest_sha256",
        "provisional_skill_ids",
        "candidate_source_grounding_artifact",
        "prospective_validation_artifact",
        "development_curve_artifact",
        "learning_checkpoint_artifact",
        "output_active_skill_ids",
        "output_skill_library_version",
        "output_skill_library_sha256",
        "completed_at",
        "content_sha256",
    }
    if not (
        set(complete) == complete_fields
        and complete.get("schema_version") == CHECKPOINT_SCHEMA
        and complete.get("run_id") == run_id
        and complete.get("round") == round_index
        and complete.get("batch_id") == batch_id
        and complete.get("stage") == "complete"
        and complete.get("run_manifest_sha256") == run_manifest_sha256
        and complete.get("provisionals_ready_manifest_sha256") == sha256_file(ready_path)
        and complete.get("expected_matrix_sha256") == ready.get("expected_matrix_sha256")
        and complete.get("development_curve_artifact")
        == ready.get("development_curve_artifact")
        and complete.get("provisional_skill_ids") == sorted(provisional_ids)
    ):
        issues.append("complete_binding_mismatch")
    expected_artifact_paths = {
        "candidate_source_grounding_artifact": (
            run_root / "reports" / f"candidate_source_grounding_round_{round_index:02d}.json"
        ),
        "prospective_validation_artifact": (
            run_root / "reports" / f"prospective_validation_{batch_id}.json"
        ),
        "learning_checkpoint_artifact": (
            run_root / "reports" / f"learning_checkpoint_{round_index:02d}.json"
        ),
    }
    for field, expected_path in expected_artifact_paths.items():
        if not _artifact_matches(root, complete.get(field), expected_path):
            issues.append(f"{field}_mismatch")
    # A block evaluates candidates produced by its predecessor.  Candidates that
    # pass are deliberately added *after* this block's frozen trajectories and
    # before the following block.  Therefore the output library must equal the
    # input library plus the accepted predecessor candidates; requiring output to
    # equal input would make every successful prospective transition invalid.
    complete_input_ids = complete.get("training_input_active_skill_ids")
    accepted_ids = complete.get("accepted_skill_ids")
    output_ids = complete.get("output_active_skill_ids")
    if not all(
        isinstance(value, list) and all(isinstance(item, str) for item in value)
        for value in (complete_input_ids, accepted_ids, output_ids)
    ):
        issues.append("skill_transition_ids_invalid")
    else:
        expected_output_ids = sorted({*complete_input_ids, *accepted_ids})
        if output_ids != expected_output_ids:
            issues.append("prospective_skill_transition_mismatch")
        if not accepted_ids and complete.get("output_skill_library_sha256") != complete.get(
            "training_input_skill_library_sha256"
        ):
            issues.append("unexplained_skill_library_hash_change")
    if not (
        complete.get("training_input_active_skill_ids") == ready.get("input_active_skill_ids")
        and complete.get("training_input_skill_library_sha256")
        == ready.get("input_skill_library_sha256")
        and complete.get("pre_validation_active_skill_ids")
        == complete.get("training_input_active_skill_ids")
        and complete.get("pre_validation_skill_library_sha256")
        == complete.get("training_input_skill_library_sha256")
    ):
        issues.append("block_input_library_binding_mismatch")

    learning_path = run_root / "reports" / f"learning_checkpoint_{round_index:02d}.json"
    learning = _json_object(learning_path)
    learning_fields = {
        "schema_version",
        "run_id",
        "checkpoint",
        "batch_id",
        "status",
        "accepted_from_preceding_block",
        "measured_input_active_skill_ids",
        "measured_input_skill_library_sha256",
        "development_curve_artifact",
        "active_skill_ids",
        "active_skill_library_sha256",
        "evidence_role",
        "curve_identity_baseline",
        "completed_at",
    }
    if not _artifact_matches(root, complete.get("learning_checkpoint_artifact"), learning_path):
        issues.append("learning_checkpoint_artifact_mismatch")
    if learning is None or not (
        set(learning) == learning_fields
        and learning.get("schema_version") == LEARNING_CHECKPOINT_SCHEMA
        and learning.get("run_id") == run_id
        and learning.get("checkpoint") == round_index
        and learning.get("batch_id") == batch_id
        and learning.get("status") == "measured_prequential_learning_checkpoint"
        and learning.get("accepted_from_preceding_block") == accepted_ids
        and learning.get("measured_input_active_skill_ids") == complete_input_ids
        and learning.get("measured_input_skill_library_sha256")
        == complete.get("training_input_skill_library_sha256")
        and learning.get("development_curve_artifact")
        == complete.get("development_curve_artifact")
        and learning.get("active_skill_ids") == output_ids
        and learning.get("active_skill_library_sha256")
        == complete.get("output_skill_library_sha256")
        and learning.get("evidence_role") == curve.get("evidence_role")
        and learning.get("curve_identity_baseline") == curve.get("identity_baseline")
    ):
        issues.append("learning_checkpoint_binding_mismatch")
    return {
        "status": "invalid" if issues else "verified",
        "stage": "complete",
        "issues": sorted(set(issues)),
        "accepted_from_preceding": complete.get("accepted_skill_ids", []),
        "provisional_skill_ids": complete.get("provisional_skill_ids", []),
        "candidate_source_grounding_artifact": complete.get(
            "candidate_source_grounding_artifact"
        ),
        "prospective_validation_artifact": complete.get(
            "prospective_validation_artifact"
        ),
        "output_active_skill_ids": complete.get("output_active_skill_ids", []),
        "output_skill_library_sha256": complete.get("output_skill_library_sha256"),
        "development_curve": {
            **curve,
            "output_active_skill_ids": output_ids if _string_list(output_ids) else [],
            "output_skill_library_sha256": complete.get("output_skill_library_sha256"),
            "accepted_from_preceding_block": (
                accepted_ids if _string_list(accepted_ids) else []
            ),
            "learning_checkpoint": _record_for_report(root, learning_path),
        },
        "complete_sha256": sha256_file(complete_path),
    }


def _development_curve_summary_contract(
    root: Path,
    run_id: str,
    batches: list[dict[str, Any]],
    checkpoints: dict[str, dict[str, Any]],
    expected_evidence_role: str,
) -> dict[str, Any]:
    """Validate the plot-ready view against immutable block evidence."""

    path = root / "runs" / run_id / "reports" / "development_learning_curve.json"
    summary = _json_object(path)
    if summary is None:
        return {
            "status": "absent" if not path.exists() else "invalid",
            "issues": [] if not path.exists() else ["curve_summary_unreadable"],
        }
    issues: list[str] = []
    expected_fields = {
        "schema_version",
        "run_id",
        "status",
        "evidence_role",
        "expected_points",
        "completed_points",
        "direction",
        "points",
        "series",
        "updated_at",
    }
    if set(summary) != expected_fields or not (
        summary.get("schema_version") == CURVE_SUMMARY_SCHEMA
        and summary.get("run_id") == run_id
        and summary.get("direction") == "current_input_library_minus_empty_library"
        and summary.get("expected_points") == len(batches)
        and summary.get("evidence_role") == expected_evidence_role
    ):
        issues.append("curve_summary_binding_mismatch")
    completed = [
        (index, str(batch["batch_id"]), checkpoints[str(batch["batch_id"])])
        for index, batch in enumerate(batches, start=1)
        if checkpoints[str(batch["batch_id"])].get("status") == "verified"
        and checkpoints[str(batch["batch_id"])].get("stage") == "complete"
    ]
    expected_completed = len(completed)
    expected_status = "complete" if expected_completed == len(batches) else "partial"
    points = summary.get("points")
    if (
        not isinstance(points, list)
        or summary.get("completed_points") != expected_completed
        or summary.get("status") != expected_status
        or len(points) != expected_completed
    ):
        issues.append("curve_summary_point_count_mismatch")
        points = points if isinstance(points, list) else []

    expected_point_fields = {
        "round",
        "batch_id",
        "input_active_skill_ids",
        "input_skill_library_sha256",
        "output_active_skill_ids",
        "output_skill_library_sha256",
        "accepted_from_preceding_block",
        "identity_baseline",
        "pair_count",
        "case_cluster_count",
        "artifact",
    }
    for point, (round_index, batch_id, checkpoint) in zip(points, completed, strict=False):
        curve = checkpoint.get("development_curve") or {}
        if not isinstance(point, dict) or set(point) != expected_point_fields or not (
            point.get("round") == round_index
            and point.get("batch_id") == batch_id
            and point.get("input_active_skill_ids") == curve.get("input_active_skill_ids")
            and point.get("input_skill_library_sha256")
            == curve.get("input_skill_library_sha256")
            and point.get("output_active_skill_ids") == curve.get("output_active_skill_ids")
            and point.get("output_skill_library_sha256")
            == curve.get("output_skill_library_sha256")
            and point.get("accepted_from_preceding_block")
            == curve.get("accepted_from_preceding_block")
            and point.get("identity_baseline") == curve.get("identity_baseline")
            and point.get("pair_count") == curve.get("pair_count")
            and point.get("case_cluster_count") == curve.get("case_cluster_count")
            and point.get("artifact") == curve.get("artifact")
        ):
            issues.append(f"curve_summary_point_drift:{batch_id}")

    series = summary.get("series")
    expected_metric_set = set(CURVE_METRICS) if completed else set()
    if not isinstance(series, dict) or set(series) != expected_metric_set:
        issues.append("curve_summary_metric_set_mismatch")
        series = series if isinstance(series, dict) else {}
    for metric_name in CURVE_METRICS:
        if not completed:
            break
        rows = series.get(metric_name)
        if not isinstance(rows, list) or len(rows) != expected_completed:
            issues.append(f"curve_summary_series_incomplete:{metric_name}")
            continue
        for row, (round_index, batch_id, checkpoint) in zip(rows, completed, strict=False):
            curve = checkpoint["development_curve"]
            metric = curve.get("core_metric_deltas", {}).get(metric_name)
            if metric is None:
                point_path = root / str(curve["artifact"]["path"])
                point = _json_object(point_path) or {}
                metric = _curve_metric_delta(
                    (point.get("curve") or {}).get("metrics", {}).get(metric_name)
                )
            if not isinstance(row, dict) or metric is None or not (
                row.get("round") == round_index
                and row.get("batch_id") == batch_id
                and row.get("empty_library_mean") == metric["empty_library_mean"]
                and row.get("current_library_mean") == metric["current_library_mean"]
                and row.get("mean_delta") == metric["mean_delta"]
                and row.get("confidence_lower") == metric["confidence_lower"]
                and row.get("confidence_upper") == metric["confidence_upper"]
            ):
                issues.append(f"curve_summary_series_drift:{batch_id}:{metric_name}")

    return {
        "status": "invalid" if issues else "verified",
        "issues": sorted(set(issues)),
        "summary_state": summary.get("status"),
        "completed_points": summary.get("completed_points"),
        "expected_points": summary.get("expected_points"),
        "artifact": _record_for_report(root, path),
    }


def _training_complete_contract(
    root: Path,
    run_id: str,
    run_manifest_sha256: str | None,
    batches: list[dict[str, Any]],
    checkpoints: dict[str, dict[str, Any]],
    curve_summary: dict[str, Any],
) -> dict[str, Any]:
    path = root / "runs" / run_id / "manifests/training_complete.json"
    summary, error = _manifest(path)
    if summary is None:
        return {
            "status": "absent" if not path.exists() else "invalid",
            "error": error,
        }
    batch_ids = [str(batch["batch_id"]) for batch in batches]
    expected_hashes = {
        batch_id: checkpoints[batch_id].get("complete_sha256") for batch_id in batch_ids
    }
    expected_validation_hashes = {
        batch_id: sha256_file(
            root / "runs" / run_id / "reports" / f"prospective_validation_{batch_id}.json"
        )
        for batch_id in batch_ids
        if (
            root / "runs" / run_id / "reports" / f"prospective_validation_{batch_id}.json"
        ).is_file()
    }
    expected_fields = {
        "schema_version",
        "run_id",
        "run_manifest_sha256",
        "trajectory_schema_version",
        "evaluation_schema_version",
        "case_limit",
        "rounds_completed",
        "round_completion_manifests",
        "round_completion_set_sha256",
        "accepted_skill_ids",
        "rejected_skill_ids",
        "prospective_validation_reports",
        "active_skill_ids",
        "active_skill_library_version",
        "active_skill_library_sha256",
        "development_learning_curve_sha256",
        "completed_at",
        "content_sha256",
    }
    checks = {
        "fields": set(summary) == expected_fields,
        "schema": summary.get("schema_version") == CHECKPOINT_SCHEMA,
        "identity": summary.get("run_id") == run_id
        and summary.get("run_manifest_sha256") == run_manifest_sha256
        and summary.get("trajectory_schema_version") == TRAJECTORY_SCHEMA
        and summary.get("evaluation_schema_version") == EVALUATION_SCHEMA,
        "all_blocks": summary.get("rounds_completed") == len(batch_ids)
        and set(summary.get("round_completion_manifests", {})) == set(batch_ids),
        "block_hashes": summary.get("round_completion_manifests") == expected_hashes,
        "block_set_hash": summary.get("round_completion_set_sha256")
        == canonical_json_sha256(expected_hashes),
        "prospective_reports": summary.get("prospective_validation_reports")
        == expected_validation_hashes,
        "final_has_no_provisional": not checkpoints.get(batch_ids[-1], {}).get(
            "provisional_skill_ids"
        ),
        "all_checkpoints_verified": all(
            checkpoints[item]["status"] == "verified" and checkpoints[item]["stage"] == "complete"
            for item in batch_ids
        ),
        "final_active_library": summary.get("active_skill_ids")
        == checkpoints.get(batch_ids[-1], {}).get("output_active_skill_ids")
        and summary.get("active_skill_library_sha256")
        == checkpoints.get(batch_ids[-1], {}).get("output_skill_library_sha256"),
        "development_curve": curve_summary.get("status") == "verified"
        and curve_summary.get("summary_state") == "complete"
        and summary.get("development_learning_curve_sha256")
        == (curve_summary.get("artifact") or {}).get("sha256"),
    }
    return {
        "status": "verified" if all(checks.values()) else "invalid",
        "checks": checks,
        "sha256": sha256_file(path),
        "accepted_skill_ids": summary.get("accepted_skill_ids", []),
        "rejected_skill_ids": summary.get("rejected_skill_ids", []),
        "active_skill_ids": summary.get("active_skill_ids", []),
    }


def _trajectory_signals(trajectories: list[ResearchTrajectory]) -> dict[str, Any]:
    question_turns = 0
    new_fact_turns = 0
    disclosed_facts: set[tuple[str, str]] = set()
    skill_exposures: Counter[str] = Counter()
    cases_with_new_fact: set[str] = set()
    for trajectory in trajectories:
        skill_exposures.update(getattr(trajectory, "exposed_skill_ids", []))
        for step in trajectory.steps:
            if step.rendered_question:
                question_turns += 1
            if getattr(step, "client_response_kind", None) == "new_hidden_fact":
                new_fact_turns += 1
                cases_with_new_fact.add(trajectory.case_id)
                disclosed_facts.update(
                    (trajectory.case_id, str(fact_id))
                    for fact_id in getattr(step, "client_selected_fact_ids", [])
                    if str(fact_id).startswith("F")
                )
    return {
        "trajectories": len(trajectories),
        "question_turns": question_turns,
        "new_hidden_fact_turns": new_fact_turns,
        "unique_case_fact_pairs_disclosed": len(disclosed_facts),
        "cases_with_new_hidden_fact": len(cases_with_new_fact),
        "new_fact_per_question": round(new_fact_turns / question_turns, 6)
        if question_turns
        else None,
        "skill_exposure_session_counts": dict(sorted(skill_exposures.items())),
    }


def _active_skill_usage(
    trajectories: list[ResearchTrajectory], active_skill_ids: list[str]
) -> dict[str, Any]:
    """Aggregate SAGE-style usage without counting candidate treatment arms."""

    active = set(active_skill_ids)
    exposed_sessions = 0
    exposed_ids: set[str] = set()
    case_ids: set[str] = set()
    domains: set[str] = set()
    per_skill: dict[str, dict[str, Any]] = {}
    for trajectory in trajectories:
        if trajectory.method == "candidate_with":
            continue
        exposed = active.intersection(getattr(trajectory, "exposed_skill_ids", []))
        if exposed:
            exposed_sessions += 1
        for skill_id in exposed:
            exposed_ids.add(skill_id)
            case_ids.add(trajectory.case_id)
            domains.add(trajectory.domain)
            row = per_skill.setdefault(
                skill_id, {"exposed_sessions": 0, "case_ids": set(), "domains": set()}
            )
            row["exposed_sessions"] += 1
            row["case_ids"].add(trajectory.case_id)
            row["domains"].add(trajectory.domain)
    return {
        "scope": "terminal_training_trajectories_excluding_candidate_with_treatments",
        "active_skill_count": len(active),
        "exposed_skill_count": len(exposed_ids),
        "exposed_session_count": exposed_sessions,
        "covered_case_count": len(case_ids),
        "covered_domain_count": len(domains),
        "exposed_skill_ids": sorted(exposed_ids),
        "per_skill": [
            {
                "skill_id": skill_id,
                "exposed_session_count": per_skill[skill_id]["exposed_sessions"],
                "covered_case_count": len(per_skill[skill_id]["case_ids"]),
                "covered_domain_count": len(per_skill[skill_id]["domains"]),
            }
            for skill_id in sorted(per_skill)
        ],
    }


def _candidate_pipeline_counts(
    root: Path,
    run_id: str,
    batches: list[dict[str, Any]],
    checkpoints: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    proposed_ids: set[str] = set()
    source_report_count = 0
    reports_bound = True
    malformed = False
    for round_index, batch in enumerate(batches, start=1):
        batch_id = str(batch["batch_id"])
        path = (
            root
            / "runs"
            / run_id
            / "reports"
            / f"candidate_source_grounding_round_{round_index:02d}.json"
        )
        value = _json_object(path)
        if value is None:
            if path.exists():
                malformed = True
            continue
        source_report_count += 1
        records = value.get("records")
        if not isinstance(records, list):
            malformed = True
            continue
        for record in records:
            if not isinstance(record, dict):
                malformed = True
                continue
            if record.get("lifecycle") == "new_teacher_candidate" and isinstance(
                record.get("skill_id"), str
            ):
                proposed_ids.add(str(record["skill_id"]))
        checkpoint = checkpoints[batch_id]
        bound = checkpoint.get("candidate_source_grounding_artifact")
        if not (
            checkpoint.get("status") == "verified"
            and checkpoint.get("stage") == "complete"
            and _artifact_matches(root, bound, path)
        ):
            reports_bound = False

    provisional_ids = {
        str(skill_id)
        for checkpoint in checkpoints.values()
        if checkpoint.get("status") == "verified"
        for skill_id in checkpoint.get("provisional_skill_ids", [])
    }
    if malformed:
        source_status = "invalid"
        proposed_count: int | None = None
    elif not source_report_count:
        source_status = "absent"
        proposed_count = None
    elif reports_bound:
        source_status = "verified"
        proposed_count = len(proposed_ids)
    else:
        source_status = "diagnostic_unbound"
        proposed_count = len(proposed_ids)
    return {
        "teacher_proposal_source_status": source_status,
        "teacher_proposed_distinct_count": proposed_count,
        "teacher_proposed_skill_ids": sorted(proposed_ids) if proposed_count is not None else None,
        "hash_bound_provisional_distinct_count": len(provisional_ids),
        "hash_bound_provisional_skill_ids": sorted(provisional_ids),
    }


def _exposed_positive_safe_counts(audit: dict[str, Any]) -> tuple[int, int] | None:
    outcomes = audit.get("outcomes")
    if not isinstance(outcomes, list):
        return None
    exposed = [row for row in outcomes if isinstance(row, dict) and row.get("exposed") is True]
    safe_positive = 0
    for row in exposed:
        reward_without = row.get("reward_without")
        reward_with = row.get("reward_with")
        nonincreasing_risks = (
            "unsupported_claim_delta",
            "premature_final_delta",
            "belief_as_fact_delta",
            "repeated_question_delta",
            "policy_fallback_delta",
            "client_fallback_delta",
            "memo_fallback_delta",
        )
        if not (_finite_number(reward_without) and _finite_number(reward_with)):
            return None
        if not all(_finite_number(row.get(field)) for field in nonincreasing_risks):
            return None
        recall_delta = row.get("critical_fact_recall_delta")
        if not _finite_number(recall_delta) or not isinstance(row.get("severe_risk_with"), bool):
            return None
        no_safety_regression = (
            row["severe_risk_with"] is False
            and all(float(row[field]) <= 0.0 for field in nonincreasing_risks)
            and float(recall_delta) >= 0.0
        )
        if float(reward_with) > float(reward_without) and no_safety_regression:
            safe_positive += 1
    return len(exposed), safe_positive


def build_report(root: Path, run_id: str) -> dict[str, Any]:
    experiment_path = root / "configs/experiments/main_experiment.yaml"
    roles_path = root / "configs/models/roles.yaml"
    data_path = root / "configs/data/main_corpus.yaml"
    experiment = yaml.safe_load(experiment_path.read_text(encoding="utf-8"))
    batch_path = root / experiment["data"]["training_batches"]
    batch_plan = yaml.safe_load(batch_path.read_text(encoding="utf-8"))
    batches = list(batch_plan["batches"])
    run_manifest = _run_manifest_contract(
        root,
        run_id,
        experiment_path=experiment_path,
        roles_path=roles_path,
        data_path=data_path,
        batch_path=batch_path,
        experiment=experiment,
    )
    manifest_sha = run_manifest.get("sha256") if run_manifest["status"] == "verified" else None
    group_size = int(experiment["trajectory_sampling"]["group_size"])
    seeds = [int(item) for item in experiment["trajectory_sampling"]["training_group_seeds"]]
    run_root = root / "runs" / run_id
    batch_rows: list[dict[str, Any]] = []
    checkpoints: dict[str, dict[str, Any]] = {}
    all_current: list[ResearchTrajectory] = []
    all_frozen: list[ResearchTrajectory] = []
    hard_blockers: list[str] = []
    first_noncomplete: str | None = None
    predecessor_complete = True
    curve_config = experiment.get("learning_curve") or {}
    sentinels_by_block = curve_config.get("sentinel_case_ids_by_block") or {}
    curve_evidence_role = str(curve_config.get("evidence_role") or "")
    for round_index, batch in enumerate(batches, start=1):
        batch_id = str(batch["batch_id"])
        expected = len(batch["case_ids"]) * len(seeds) * group_size
        expected_sentinels = [
            str(case_id)
            for case_id in sentinels_by_block.get(batch_id, [])
            if case_id in set(batch["case_ids"])
        ]
        expected_curve_pairs = len(expected_sentinels) * len(seeds)
        valid: list[ResearchTrajectory] = []
        invalid = 0
        for path in sorted((run_root / "trajectories" / batch_id).glob("*.json")):
            value = _json_object(path)
            if value is None or value.get("schema_version") != TRAJECTORY_SCHEMA:
                invalid += 1
                continue
            try:
                trajectory = ResearchTrajectory.model_validate(value)
            except Exception:
                invalid += 1
                continue
            if (
                trajectory.run_id != run_id
                or trajectory.partition != batch_id
                or trajectory.method
                not in {"training_policy_sample", "candidate_without", "candidate_with"}
                or trajectory.case_id not in batch["case_ids"]
                or trajectory.persona != batch["persona_assignment"].get(trajectory.case_id)
                or trajectory.seed not in seeds
                or not 0 <= trajectory.sample_index < group_size
            ):
                invalid += 1
                continue
            valid.append(trajectory)
        successes = [item for item in valid if item.status in TERMINAL_OK]
        errors = [item for item in valid if item.status == "error"]
        checkpoint = _checkpoint_contract(
            root,
            run_id,
            batch_id,
            round_index,
            manifest_sha,
            expected_pair_count=expected_curve_pairs,
            expected_sentinel_ids=expected_sentinels,
            expected_evidence_role=curve_evidence_role,
        )
        curve = checkpoint.get("development_curve")
        if curve is None:
            curve = _development_curve_point_contract(
                root,
                run_id,
                batch_id,
                round_index,
                manifest_sha,
                expected_pair_count=expected_curve_pairs,
                expected_sentinel_ids=expected_sentinels,
                expected_evidence_role=curve_evidence_role,
            )
        if curve.get("status") not in {"absent", "verified", "diagnostic_uncheckpointed"}:
            hard_blockers.append(f"{batch_id}:development_curve_invalid")
        checkpoints[batch_id] = checkpoint
        if predecessor_complete:
            progress, blockers = classify_batch_progress(
                expected=expected,
                successful=len(successes),
                errors=len(errors),
                checkpoint_stage=(
                    checkpoint["stage"] if checkpoint["status"] == "verified" else None
                ),
            )
            if invalid or checkpoint["status"] == "invalid" or run_manifest["status"] == "invalid":
                progress = "invalid_artifact_contract"
                blockers = ["current_protocol_or_hash_binding_failed"]
        else:
            progress, blockers = "waiting_for_predecessor", []
        if first_noncomplete is None and progress != "complete":
            first_noncomplete = batch_id
        hard_blockers.extend(f"{batch_id}:{reason}" for reason in blockers)
        predecessor_complete = progress == "complete"
        all_current.extend(successes)
        if progress == "complete":
            all_frozen.extend(successes)
        batch_rows.append(
            {
                "batch_id": batch_id,
                "prospective_validation_for": batch.get("prospective_validation_for"),
                "expected_training_trajectories": expected,
                "successful_trajectories": len(successes),
                "error_trajectories": len(errors),
                "invalid_trajectories": invalid,
                "progress": progress,
                "blocking_reasons": blockers,
                "checkpoint": checkpoint,
                "development_curve": curve,
                "observed_signals": _trajectory_signals(successes),
            }
        )
    curve_summary = _development_curve_summary_contract(
        root, run_id, batches, checkpoints, curve_evidence_role
    )
    training_complete = _training_complete_contract(
        root, run_id, manifest_sha, batches, checkpoints, curve_summary
    )
    external_path = run_root / "reports/external_test.json"
    external = _json_object(external_path)
    external_verified = bool(
        external
        and external.get("schema_version") == 6
        and external.get("run_id") == run_id
        and external.get("run_manifest_sha256") == manifest_sha
        and training_complete.get("status") == "verified"
        and external.get("training_complete_sha256") == training_complete.get("sha256")
    )
    if (
        run_manifest["status"] != "verified"
        or any(row["progress"] == "invalid_artifact_contract" for row in batch_rows)
        or curve_summary["status"] == "invalid"
        or training_complete["status"] == "invalid"
    ):
        paper_status = "invalid_or_unverified_run_no_formal_claim"
    elif external_verified:
        paper_status = "official_external_effect_estimate_available"
    elif training_complete["status"] == "verified":
        paper_status = "frozen_training_complete_external_test_pending"
    else:
        paper_status = "verified_training_in_progress_no_effect_claim"
    prospective_reports = sorted((run_root / "reports").glob("prospective_validation_*.json"))
    prospective_decisions = []
    candidate_audits: list[dict[str, Any]] = []
    for path in prospective_reports:
        value = _json_object(path)
        if value:
            validation_batch_id = str(value.get("validation_batch_id") or "")
            validation_checkpoint = checkpoints.get(validation_batch_id, {})
            report_hash_bound = bool(
                validation_checkpoint.get("status") == "verified"
                and validation_checkpoint.get("stage") == "complete"
                and _artifact_matches(
                    root,
                    validation_checkpoint.get("prospective_validation_artifact"),
                    path,
                )
            )
            prospective_decisions.append(
                {
                    "validation_batch_id": value.get("validation_batch_id"),
                    "source_batch_id": value.get("source_batch_id"),
                    "provisional_skill_ids": value.get("provisional_skill_ids", []),
                    "accepted_skill_ids": value.get("accepted_skill_ids", []),
                    "deferred_skill_ids": value.get("deferred_skill_ids", []),
                    "rejected_skill_ids": value.get("rejected_skill_ids", []),
                }
            )
            for skill_id, record in sorted((value.get("audit_artifacts") or {}).items()):
                if not _artifact_ok(root, record):
                    candidate_audits.append(
                        {"skill_id": skill_id, "status": "invalid_audit_artifact"}
                    )
                    continue
                audit = _json_object(root / str(record["path"]))
                if audit is None:
                    candidate_audits.append(
                        {"skill_id": skill_id, "status": "unreadable_audit_artifact"}
                    )
                    continue
                decision = audit.get("decision") or {}
                mechanism = audit.get("mechanism_direction_gate") or {}
                positive_safe = _exposed_positive_safe_counts(audit)
                candidate_audits.append(
                    {
                        "skill_id": skill_id,
                        "status": "verified",
                        "evidence_status": (
                            "verified_checkpoint_bound"
                            if report_hash_bound
                            else "diagnostic_uncheckpointed"
                        ),
                        "validation_batch_id": audit.get("validation_batch_id"),
                        "validation_blocks": len(audit.get("validation_batch_ids") or []),
                        "decision": decision.get("decision"),
                        "reason": decision.get("reason"),
                        "exposed_pairs": decision.get("exposed_pairs"),
                        "exposed_cases": decision.get("exposed_cases"),
                        "exposed_domains": decision.get("exposed_domains"),
                        "mean_delta_reward": decision.get("mean_delta_reward"),
                        "harmful_pair_rate": decision.get("harmful_pair_rate"),
                        "source_signal_family": audit.get("source_signal_family"),
                        "mechanism_passed": mechanism.get("passed"),
                        "newly_elicited_fact_delta": mechanism.get(
                            "mean_newly_elicited_fact_delta"
                        ),
                        "identified_evidence_gap_delta": mechanism.get(
                            "mean_identified_evidence_gap_delta"
                        ),
                        "question_turn_delta": mechanism.get("mean_question_turn_delta"),
                        "exposed_outcome_count": (
                            positive_safe[0] if positive_safe is not None else None
                        ),
                        "positive_safe_exposed_count": (
                            positive_safe[1] if positive_safe is not None else None
                        ),
                        "positive_safe_exposed_rate": (
                            round(positive_safe[1] / positive_safe[0], 6)
                            if positive_safe is not None and positive_safe[0]
                            else None
                        ),
                    }
                )
    latest_candidate_audits: dict[str, dict[str, Any]] = {}
    for row in candidate_audits:
        skill_id = str(row["skill_id"])
        prior = latest_candidate_audits.get(skill_id)
        if prior is None or int(row.get("validation_blocks") or 0) >= int(
            prior.get("validation_blocks") or 0
        ):
            latest_candidate_audits[skill_id] = row
    lifecycle_counts = Counter(
        str(row.get("decision"))
        for row in latest_candidate_audits.values()
        if row.get("status") == "verified"
    )
    completed_checkpoints = [
        row["checkpoint"]
        for row in batch_rows
        if row["checkpoint"].get("status") == "verified"
        and row["checkpoint"].get("stage") == "complete"
    ]
    current_active_skill_ids = (
        completed_checkpoints[-1].get("output_active_skill_ids", [])
        if completed_checkpoints
        else []
    )
    candidate_pipeline = _candidate_pipeline_counts(
        root, run_id, batches, checkpoints
    )
    auditable_usage_rows = [
        row
        for row in latest_candidate_audits.values()
        if row.get("status") == "verified"
        and row.get("evidence_status") == "verified_checkpoint_bound"
        and row.get("exposed_outcome_count") is not None
    ]
    exposed_audit_total = sum(
        int(row["exposed_outcome_count"]) for row in auditable_usage_rows
    )
    positive_safe_total = sum(
        int(row["positive_safe_exposed_count"]) for row in auditable_usage_rows
    )
    diagnostic_usage_rows = [
        row
        for row in latest_candidate_audits.values()
        if row.get("status") == "verified"
        and row.get("evidence_status") == "diagnostic_uncheckpointed"
        and row.get("exposed_outcome_count") is not None
    ]
    diagnostic_exposed_total = sum(
        int(row["exposed_outcome_count"]) for row in diagnostic_usage_rows
    )
    diagnostic_positive_safe_total = sum(
        int(row["positive_safe_exposed_count"]) for row in diagnostic_usage_rows
    )
    candidate_effect_usage = {
        "status": (
            "absent"
            if not auditable_usage_rows
            else ("no_exposed_outcome" if not exposed_audit_total else "observed")
        ),
        "exposed_outcome_count": (
            exposed_audit_total if auditable_usage_rows else None
        ),
        "positive_safe_exposed_count": (
            positive_safe_total if auditable_usage_rows else None
        ),
        "positive_safe_exposed_rate": (
            round(positive_safe_total / exposed_audit_total, 6)
            if exposed_audit_total
            else None
        ),
        "definition": (
            "reward_with>reward_without; severe_risk_with=false; unsupported, premature, "
            "belief-as-fact, repeated-question and fallback deltas <=0; "
            "critical-fact-recall delta >=0"
        ),
        "diagnostic_uncheckpointed": {
            "audit_count": len(diagnostic_usage_rows),
            "exposed_outcome_count": (
                diagnostic_exposed_total if diagnostic_usage_rows else None
            ),
            "positive_safe_exposed_count": (
                diagnostic_positive_safe_total if diagnostic_usage_rows else None
            ),
            "positive_safe_exposed_rate": (
                round(diagnostic_positive_safe_total / diagnostic_exposed_total, 6)
                if diagnostic_exposed_total
                else None
            ),
        },
    }
    active_usage = _active_skill_usage(all_frozen, current_active_skill_ids)
    active_usage["evidence_status"] = (
        "verified_completed_blocks" if all_frozen else "absent_no_completed_block"
    )
    active_usage["diagnostic_including_uncheckpointed"] = _active_skill_usage(
        all_current, current_active_skill_ids
    )
    return {
        "schema_version": 4,
        "run_id": run_id,
        "protocol": "128_case_8x16_bounded_cumulative_embedded_candidates",
        "evidence_ownership": run_manifest,
        "current_stage": {
            "first_noncomplete_batch": first_noncomplete,
            "hard_blockers": hard_blockers,
        },
        "batches": batch_rows,
        "aggregate_observed_signals": _trajectory_signals(all_current),
        "prospective_decisions": prospective_decisions,
        "skill_lifecycle": {
            "candidate_pipeline": candidate_pipeline,
            "latest_decision_counts": dict(sorted(lifecycle_counts.items())),
            "current_active_skill_ids": current_active_skill_ids,
            "current_active_skill_count": len(current_active_skill_ids),
            "latest_candidate_audits": [
                latest_candidate_audits[skill_id] for skill_id in sorted(latest_candidate_audits)
            ],
            "active_skill_usage": active_usage,
            "candidate_exposed_effect_usage": candidate_effect_usage,
        },
        "formal_artifacts": {
            "development_learning_curve_contract": curve_summary,
            "training_complete_contract": training_complete,
            "external_test_contract": {
                "status": "verified"
                if external_verified
                else ("absent" if not external_path.exists() else "invalid")
            },
        },
        "paper_claim_status": paper_status,
        "interpretation": (
            "Observed trajectories before a hash-bound provisionals-ready checkpoint are "
            "diagnostic only; an uncheckpointed curve point is diagnostic too. Development "
            "deltas require the schema-4 checkpoint chain, while final skill-effect claims "
            "require the frozen training chain and official external paired report."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = build_report(ROOT, args.run_id)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
