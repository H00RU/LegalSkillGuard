#!/usr/bin/env python3
"""Read-only progress audit for the schema-5 direct skill-accumulation run.

The monitor understands exactly the frozen 128-case design: eight ordered blocks,
sixteen cases per block, and four ``training_policy_sample`` trajectories per
case.  Files observed before a schema-5 block completion manifest are useful live
diagnostics; only artifacts hash-bound by that manifest are reported as verified
block evidence.

The public Chinese 30-case benchmark is outside this monitor.  It is a held-out
external test that has not been used for training, debugging, prompt selection, or
threshold selection.
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
from legal_skill_guard.experiment.storage import trajectory_identity
from legal_skill_guard.schemas.experiment import (
    CURRENT_TRAJECTORY_SCHEMA_VERSION,
    ResearchTrajectory,
)
from legal_skill_guard.utils.hashing import canonical_json_sha256, sha256_file

ROOT = Path(__file__).resolve().parents[1]

MONITOR_SCHEMA = 5
BLOCK_SCHEMA = 5
TRAINING_SUMMARY_SCHEMA = 5
TEACHER_SCHEMA = 2
ADMISSION_SCHEMA = 5
LEARNING_CHECKPOINT_SCHEMA = 3
HEALTH_SCHEMA = 2
CURVE_POINT_SCHEMA = 1
CURVE_SUMMARY_SCHEMA = 1
MAINTENANCE_SCHEMA = 1
TRAJECTORY_SCHEMA = CURRENT_TRAJECTORY_SCHEMA_VERSION
EVALUATION_SCHEMA = 13

EXPECTED_BLOCKS = 8
EXPECTED_CASES_PER_BLOCK = 16
EXPECTED_GROUP_SIZE = 4
EXPECTED_TRAINING_SEEDS = [42]
EXPECTED_TRAJECTORIES_PER_BLOCK = 64
EXPECTED_TRAINING_CASES = 128
EXPECTED_PERSONA = "P_WD"
PRIMARY_METRIC = "unique_disclosed_facts_per_question"
TERMINAL_OK = {"memo_submitted", "abstained"}
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
    PRIMARY_METRIC,
    "identified_evidence_gaps",
)


def _json_object(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _yaml_object(path: Path) -> dict[str, Any] | None:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
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
    if not _artifact_ok(root, record) or not isinstance(record, dict):
        return False
    return (root / str(record["path"])).resolve() == expected_path.resolve()


def _record_for_report(root: Path, path: Path) -> dict[str, str] | None:
    if not path.is_file():
        return None
    try:
        relative = path.resolve().relative_to(root.resolve())
    except ValueError:
        return None
    return {"path": str(relative), "sha256": sha256_file(path)}


def _string_list(value: object, *, sorted_unique: bool = False) -> bool:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        return False
    return not sorted_unique or value == sorted(set(value))


def _finite_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _nonnegative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _curve_metric_delta(metric: object) -> dict[str, Any] | None:
    if not isinstance(metric, dict):
        return None
    estimate = metric.get("case_cluster_estimate")
    if not isinstance(estimate, dict):
        return None
    values = (
        metric.get("empty_library_mean"),
        metric.get("current_library_mean"),
        metric.get("pair_mean_delta"),
        estimate.get("mean_delta"),
        estimate.get("lower"),
        estimate.get("upper"),
    )
    if not all(_finite_number(item) for item in values):
        return None
    return {
        "name": PRIMARY_METRIC,
        "empty_library_mean": metric["empty_library_mean"],
        "current_library_mean": metric["current_library_mean"],
        "mean_delta": estimate["mean_delta"],
        "confidence_lower": estimate["lower"],
        "confidence_upper": estimate["upper"],
    }


def _protocol_contract(
    experiment: dict[str, Any],
    batch_plan: dict[str, Any],
    corpus_config: dict[str, Any],
) -> dict[str, Any]:
    batches = batch_plan.get("batches")
    batches = batches if isinstance(batches, list) else []
    case_lists = [batch.get("case_ids") for batch in batches if isinstance(batch, dict)]
    all_cases = [
        str(case_id)
        for case_ids in case_lists
        if isinstance(case_ids, list)
        for case_id in case_ids
    ]
    assignments_ok = all(
        isinstance(batch, dict)
        and isinstance(batch.get("case_ids"), list)
        and isinstance(batch.get("persona_assignment"), dict)
        and len(batch["case_ids"]) == EXPECTED_CASES_PER_BLOCK
        and set(batch["persona_assignment"]) == set(batch["case_ids"])
        and set(batch["persona_assignment"].values()) == {EXPECTED_PERSONA}
        for batch in batches
    )
    sampling = experiment.get("trajectory_sampling") or {}
    admission = experiment.get("skill_admission") or {}
    execution = experiment.get("execution") or {}
    data = experiment.get("data") or {}
    external_policy = corpus_config.get("external_benchmark_policy") or {}
    checks = {
        "batch_plan_schema": batch_plan.get("schema_version") == 3,
        "direct_block_design": batch_plan.get("design")
        == "balanced_sequential_skill_accumulation_blocks",
        "training_case_count": batch_plan.get("training_cases") == EXPECTED_TRAINING_CASES,
        "block_count": len(batches) == EXPECTED_BLOCKS,
        "cases_per_block": batch_plan.get("cases_per_batch") == EXPECTED_CASES_PER_BLOCK
        and all(len(case_ids) == EXPECTED_CASES_PER_BLOCK for case_ids in case_lists),
        "unique_case_partition": len(all_cases) == EXPECTED_TRAINING_CASES
        and len(set(all_cases)) == EXPECTED_TRAINING_CASES,
        "cooperative_training_persona": assignments_ok,
        "group_size": sampling.get("group_size") == EXPECTED_GROUP_SIZE,
        "training_seed": sampling.get("training_group_seeds") == EXPECTED_TRAINING_SEEDS,
        "eight_learning_rounds": execution.get("evolution_rounds") == EXPECTED_BLOCKS,
        "candidate_budget": execution.get("maximum_new_skills_per_block") == 3
        and execution.get("teacher_call_budget_per_round") == 3,
        "direct_admission": admission.get("mode") == "source_grounded_direct_admission"
        and admission.get("per_candidate_outcome_gate") is False,
        "maintenance_schedule": admission.get("maintenance_interval_blocks") == 2,
        "primary_metric": (experiment.get("evaluation") or {}).get("primary_endpoint")
        == PRIMARY_METRIC,
        "external_test_declared_untouched": data.get("external_evaluation_status")
        == "held_out_frozen_test_not_used_for_debugging"
        and external_policy.get("used_for_runtime_debugging") is False
        and external_policy.get("used_for_model_prompt_or_threshold_selection") is False
        and external_policy.get("evaluation_after_library_freeze_only") is True
        and external_policy.get("may_enter_training") is False
        and external_policy.get("may_enter_skill_teacher_context") is False,
    }
    return {
        "status": "supported" if all(checks.values()) else "unsupported_configuration",
        "checks": checks,
        "block_count": len(batches),
        "training_case_count": len(all_cases),
        "expected_trajectories_per_block": EXPECTED_TRAJECTORIES_PER_BLOCK,
    }


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
    path = root / "runs" / run_id / "manifests" / "run.json"
    manifest, error = _manifest(path)
    if manifest is None:
        return {
            "status": "unverified" if not path.exists() else "invalid",
            "error": error,
            "path": str(path),
        }
    try:
        _, initial = load_formal_initial_skill_library(root, experiment)
        initial_error = None
    except (OSError, ValueError, RuntimeError, yaml.YAMLError) as exc:
        initial = {"path": None, "id": None, "sha256": None}
        initial_error = str(exc)
    checks = {
        "schema": manifest.get("schema_version") == 3,
        "run_id": manifest.get("run_id") == run_id,
        "experiment_config": manifest.get("experiment_config_sha256")
        == sha256_file(experiment_path),
        "roles_config": manifest.get("roles_config_sha256") == sha256_file(roles_path),
        "corpus_config": manifest.get("data_config_sha256") == sha256_file(data_path),
        "batch_plan": manifest.get("training_batch_plan_sha256") == sha256_file(batch_path),
        "initial_library_path": manifest.get("initial_skill_library_path") == initial["path"],
        "initial_library_id": manifest.get("initial_skill_library_id") == initial["id"],
        "initial_library_hash": manifest.get("initial_skill_library_sha256") == initial["sha256"],
        "implementation": manifest.get("implementation_sha256") == implementation_sha256(root),
    }
    return {
        "status": "verified" if all(checks.values()) else "invalid",
        "checks": checks,
        "initial_skill_library_error": initial_error,
        "sha256": sha256_file(path),
        "path": str(path.relative_to(root)),
        "model_id": manifest.get("model_id"),
        "model_revision": manifest.get("model_revision"),
        "initial_skill_library_id": manifest.get("initial_skill_library_id"),
        "initial_skill_library_sha256": manifest.get("initial_skill_library_sha256"),
    }


def _unsupported_schema_artifacts(run_root: Path) -> list[dict[str, Any]]:
    expectations = (
        (run_root / "manifests", "training_batch_*__complete.json", BLOCK_SCHEMA),
        (run_root / "manifests", "teacher_round_*.json", TEACHER_SCHEMA),
        (run_root / "reports", "skill_admission_round_*.json", ADMISSION_SCHEMA),
        (run_root / "reports", "learning_checkpoint_*.json", LEARNING_CHECKPOINT_SCHEMA),
        (run_root / "reports", "library_maintenance_*.json", MAINTENANCE_SCHEMA),
    )
    unsupported: list[dict[str, Any]] = []
    for directory, pattern, expected_schema in expectations:
        for path in sorted(directory.glob(pattern)):
            value = _json_object(path)
            actual = value.get("schema_version") if value is not None else None
            if value is not None and actual != expected_schema:
                unsupported.append(
                    {
                        "path": str(path.relative_to(run_root)),
                        "actual_schema": actual,
                        "required_schema": expected_schema,
                    }
                )
    summary_path = run_root / "manifests" / "training_complete.json"
    summary = _json_object(summary_path)
    if summary is not None and summary.get("schema_version") != TRAINING_SUMMARY_SCHEMA:
        unsupported.append(
            {
                "path": str(summary_path.relative_to(run_root)),
                "actual_schema": summary.get("schema_version"),
                "required_schema": TRAINING_SUMMARY_SCHEMA,
            }
        )
    for path in sorted((run_root / "manifests").glob("training_batch_*__*.json")):
        if not path.name.endswith("__complete.json"):
            unsupported.append(
                {
                    "path": str(path.relative_to(run_root)),
                    "actual_schema": (_json_object(path) or {}).get("schema_version"),
                    "required_schema": "schema5_direct_block_completion_only",
                }
            )
    for path in sorted((run_root / "trajectories").glob("training_batch_*/*.json")):
        value = _json_object(path)
        if value is None:
            continue
        if (
            value.get("schema_version") != TRAJECTORY_SCHEMA
            or value.get("method") != "training_policy_sample"
        ):
            unsupported.append(
                {
                    "path": str(path.relative_to(run_root)),
                    "actual_schema": value.get("schema_version"),
                    "required_schema": TRAJECTORY_SCHEMA,
                    "actual_method": value.get("method"),
                    "required_method": "training_policy_sample",
                }
            )
    return unsupported


def _expected_matrix(
    *,
    run_id: str,
    batch: dict[str, Any],
    input_skill_library_sha256: str,
    model_id: str,
    model_revision: str,
) -> list[dict[str, Any]]:
    batch_id = str(batch["batch_id"])
    records: list[dict[str, Any]] = []
    for case_id in batch["case_ids"]:
        persona = str(batch["persona_assignment"][case_id])
        for seed in EXPECTED_TRAINING_SEEDS:
            group_id = f"{batch_id}.{case_id}.{persona}.seed_{seed}"
            for sample_index in range(EXPECTED_GROUP_SIZE):
                trajectory_id = trajectory_identity(
                    run_id=run_id,
                    partition=batch_id,
                    method="training_policy_sample",
                    case_id=str(case_id),
                    persona=persona,
                    seed=seed,
                    sample_index=sample_index,
                    skill_library_version=input_skill_library_sha256,
                )
                records.append(
                    {
                        "trajectory_id": trajectory_id,
                        "run_id": run_id,
                        "partition": batch_id,
                        "method": "training_policy_sample",
                        "case_id": str(case_id),
                        "persona": persona,
                        "seed": seed,
                        "sample_index": sample_index,
                        "group_id": group_id,
                        "skill_library_version": input_skill_library_sha256,
                        "model_id": model_id,
                        "model_revision": model_revision,
                    }
                )
    return records


def _scan_trajectories(
    root: Path,
    run_id: str,
    batch_id: str,
    matrix: list[dict[str, Any]],
) -> dict[str, Any]:
    expected = {str(row["trajectory_id"]): row for row in matrix}
    directory = root / "runs" / run_id / "trajectories" / batch_id
    valid: dict[str, ResearchTrajectory] = {}
    issue_counts: Counter[str] = Counter()
    for path in sorted(directory.glob("*.json")):
        value = _json_object(path)
        if value is None:
            issue_counts["unreadable_trajectory"] += 1
            continue
        if value.get("schema_version") != TRAJECTORY_SCHEMA:
            issue_counts["trajectory_schema_mismatch"] += 1
            continue
        try:
            trajectory = ResearchTrajectory.model_validate(value)
        except Exception:
            issue_counts["trajectory_contract_invalid"] += 1
            continue
        row = expected.get(trajectory.trajectory_id)
        if row is None:
            issue_counts["unexpected_trajectory_identity"] += 1
            continue
        if any(getattr(trajectory, key) != expected_value for key, expected_value in row.items()):
            issue_counts["trajectory_matrix_binding_mismatch"] += 1
            continue
        if trajectory.trajectory_id in valid:
            issue_counts["duplicate_trajectory_identity"] += 1
            continue
        valid[trajectory.trajectory_id] = trajectory
    successful = [item for item in valid.values() if item.status in TERMINAL_OK]
    errors = [item for item in valid.values() if item.status == "error"]
    nonstandard = [item for item in valid.values() if item.status not in TERMINAL_OK | {"error"}]
    return {
        "expected": len(expected),
        "files": sum(1 for _ in directory.glob("*.json")),
        "valid": len(valid),
        "successful": len(successful),
        "errors": len(errors),
        "nonstandard_terminal": len(nonstandard),
        "missing": max(len(expected) - len(valid), 0),
        "invalid": sum(issue_counts.values()),
        "issue_counts": dict(sorted(issue_counts.items())),
        "values": valid,
        "successful_values": successful,
    }


def _scan_evaluations(
    root: Path,
    run_id: str,
    trajectories: dict[str, ResearchTrajectory],
) -> dict[str, Any]:
    directory = root / "runs" / run_id / "evaluations"
    valid: dict[str, dict[str, Any]] = {}
    issue_counts: Counter[str] = Counter()
    gap_total = 0
    gap_scoreable = 0
    gap_outcomes: Counter[str] = Counter()
    rewards: list[float] = []
    for trajectory_id, trajectory in trajectories.items():
        path = directory / f"{trajectory_id}.json"
        if not path.is_file():
            continue
        value = _json_object(path)
        if value is None:
            issue_counts["unreadable_evaluation"] += 1
            continue
        if value.get("schema_version") != EVALUATION_SCHEMA:
            issue_counts["evaluation_schema_mismatch"] += 1
            continue
        if (
            value.get("trajectory_id") != trajectory_id
            or value.get("case_id") != trajectory.case_id
        ):
            issue_counts["evaluation_identity_mismatch"] += 1
            continue
        mechanism = value.get("mechanism_signals")
        if not isinstance(mechanism, dict) or not _nonnegative_int(
            mechanism.get("identified_evidence_gap_count")
        ):
            issue_counts["evaluation_mechanism_signals_invalid"] += 1
            continue
        declared_gap_ids = mechanism.get("identified_evidence_gap_ids")
        if not _string_list(declared_gap_ids) or len(declared_gap_ids) != mechanism.get(
            "identified_evidence_gap_count"
        ):
            issue_counts["evaluation_evidence_gap_partition_invalid"] += 1
            continue
        valid[trajectory_id] = value
        gap_total += int(mechanism["identified_evidence_gap_count"])
        gap_outcomes[str(mechanism.get("evidence_gap_outcome"))] += 1
        if mechanism.get("target_kind_available") is True:
            gap_scoreable += 1
        reward = value.get("reward")
        if isinstance(reward, dict) and _finite_number(reward.get("final_reward")):
            rewards.append(float(reward["final_reward"]))
    expected = len(trajectories)
    return {
        "expected": expected,
        "scored": len(valid),
        "missing": expected - len(valid) - sum(issue_counts.values()),
        "invalid": sum(issue_counts.values()),
        "issue_counts": dict(sorted(issue_counts.items())),
        "mean_reward": round(sum(rewards) / len(rewards), 6) if rewards else None,
        "identified_evidence_gaps": gap_total,
        "evidence_gap_scoreable_evaluations": gap_scoreable,
        "evidence_gap_outcomes": dict(sorted(gap_outcomes.items())),
        "values": valid,
    }


def _trajectory_signals(trajectories: list[ResearchTrajectory]) -> dict[str, Any]:
    question_turns = 0
    new_fact_turns = 0
    per_session_facts = 0
    case_fact_pairs: set[tuple[str, str]] = set()
    cases_with_new_fact: set[str] = set()
    response_kinds: Counter[str] = Counter()
    for trajectory in trajectories:
        session_fact_ids: set[str] = set()
        for step in trajectory.steps:
            if step.rendered_question:
                question_turns += 1
            if step.client_response_kind:
                response_kinds[str(step.client_response_kind)] += 1
            if step.client_response_kind == "new_hidden_fact":
                new_fact_turns += 1
                selected = {str(item) for item in step.client_selected_fact_ids}
                session_fact_ids.update(selected)
                case_fact_pairs.update((trajectory.case_id, item) for item in selected)
                if selected:
                    cases_with_new_fact.add(trajectory.case_id)
        per_session_facts += len(session_fact_ids)
    return {
        "trajectory_count": len(trajectories),
        "question_turns": question_turns,
        "new_hidden_fact_turns": new_fact_turns,
        "unique_disclosed_facts_across_sessions": per_session_facts,
        "unique_case_fact_pairs_disclosed": len(case_fact_pairs),
        "cases_with_new_hidden_fact": len(cases_with_new_fact),
        "unique_disclosed_facts_per_question": (
            round(per_session_facts / question_turns, 6) if question_turns else None
        ),
        "client_response_kind_counts": dict(sorted(response_kinds.items())),
    }


def _skill_exposure(
    trajectories: list[ResearchTrajectory], input_skill_ids: list[str]
) -> dict[str, Any]:
    declared = set(input_skill_ids)
    exposed_sessions = 0
    exposed_ids: set[str] = set()
    exposed_cases: set[str] = set()
    exposed_domains: set[str] = set()
    undeclared: set[str] = set()
    per_skill: dict[str, dict[str, Any]] = {}
    for trajectory in trajectories:
        exposed = set(trajectory.exposed_skill_ids)
        undeclared.update(exposed - declared)
        if exposed:
            exposed_sessions += 1
            exposed_cases.add(trajectory.case_id)
            exposed_domains.add(trajectory.domain)
        for skill_id in exposed:
            exposed_ids.add(skill_id)
            row = per_skill.setdefault(skill_id, {"sessions": 0, "cases": set(), "domains": set()})
            row["sessions"] += 1
            row["cases"].add(trajectory.case_id)
            row["domains"].add(trajectory.domain)
    observed_domains = sorted({trajectory.domain for trajectory in trajectories})
    return {
        "input_skill_count": len(declared),
        "exposed_skill_count": len(exposed_ids),
        "exposed_skill_ids": sorted(exposed_ids),
        "unexposed_input_skill_ids": sorted(declared - exposed_ids),
        "undeclared_exposed_skill_ids": sorted(undeclared),
        "exposed_session_count": exposed_sessions,
        "covered_case_count": len(exposed_cases),
        "covered_domain_count": len(exposed_domains),
        "observed_training_domains": observed_domains,
        "observed_training_domain_count": len(observed_domains),
        "per_skill": [
            {
                "skill_id": skill_id,
                "exposed_session_count": per_skill[skill_id]["sessions"],
                "covered_case_count": len(per_skill[skill_id]["cases"]),
                "covered_domains": sorted(per_skill[skill_id]["domains"]),
            }
            for skill_id in sorted(per_skill)
        ],
    }


def _health_contract(
    root: Path,
    run_id: str,
    batch_id: str,
    *,
    expected_trajectory_count: int,
    bound_record: object | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    path = root / "runs" / run_id / "health" / f"pre_scoring_health_{batch_id}.json"
    value = _json_object(path)
    if value is None:
        status = "absent" if not path.exists() else "invalid"
        return (
            {"status": status, "healthy": None, "issue_count": None, "issue_counts": {}},
            {"status": status, "warning_count": None, "warning_counts": {}},
        )
    issues: list[str] = []
    if bound_record is not None and not _artifact_matches(root, bound_record, path):
        issues.append("health_artifact_mismatch")
    counts = value.get("counts")
    issue_count = value.get("blocking_issue_count")
    if not (
        value.get("schema_version") == HEALTH_SCHEMA
        and value.get("trajectory_count") == expected_trajectory_count
        and _nonnegative_int(issue_count)
        and isinstance(counts, dict)
        and all(isinstance(key, str) and _nonnegative_int(item) for key, item in counts.items())
        and sum(counts.values()) == issue_count
        and value.get("healthy") is (issue_count == 0)
    ):
        issues.append("health_contract_invalid")
    diagnostics = value.get("quality_diagnostics")
    warning_count: int | None = None
    warning_counts: dict[str, int] = {}
    if isinstance(diagnostics, dict):
        raw_count = diagnostics.get("model_behavior_warning_count")
        raw_counts = diagnostics.get("model_behavior_warning_counts")
        if (
            _nonnegative_int(raw_count)
            and isinstance(raw_counts, dict)
            and all(
                isinstance(key, str) and _nonnegative_int(item) for key, item in raw_counts.items()
            )
            and sum(raw_counts.values()) == raw_count
        ):
            warning_count = raw_count
            warning_counts = dict(sorted(raw_counts.items()))
        else:
            issues.append("soft_behavior_contract_invalid")
    else:
        issues.append("soft_behavior_contract_invalid")
    base_status = "verified" if bound_record is not None else "diagnostic_unbound"
    status = "invalid" if issues else base_status
    return (
        {
            "status": status,
            "healthy": value.get("healthy"),
            "issue_count": issue_count,
            "issue_counts": dict(sorted(counts.items())) if isinstance(counts, dict) else {},
            "issues": sorted(set(issues)),
            "artifact": _record_for_report(root, path),
        },
        {
            "status": status,
            "warning_count": warning_count,
            "warning_counts": warning_counts,
            "artifact": _record_for_report(root, path),
        },
    )


def _teacher_contract(
    root: Path,
    run_id: str,
    round_index: int,
    *,
    bound_record: object | None,
) -> dict[str, Any]:
    path = root / "runs" / run_id / "manifests" / f"teacher_round_{round_index:02d}.json"
    value, envelope_error = _manifest(path)
    if value is None:
        return {
            "status": "absent" if not path.exists() else "invalid",
            "issues": [] if not path.exists() else [str(envelope_error)],
        }
    issues: list[str] = []
    if bound_record is not None and not _artifact_matches(root, bound_record, path):
        issues.append("teacher_artifact_mismatch")
    if not (
        value.get("schema_version") == TEACHER_SCHEMA
        and value.get("round") == round_index
        and value.get("teacher_update_unit")
        == "distinct_cluster_syntheses_from_cumulative_trajectory_contrasts"
        and value.get("evidence_lifecycle")
        == "trajectory_contrast_to_source_grounded_direct_working_library"
        and value.get("candidate_outcome_feedback_used") is False
    ):
        issues.append("teacher_binding_invalid")
    integer_fields = (
        "end_to_end_reward_informative_groups",
        "trajectory_contrast_groups",
        "selected_groups",
        "new_trajectory_contrast_patches",
        "cumulative_trajectory_contrast_patches",
        "eligible_teacher_evidence_clusters",
        "teacher_call_budget",
        "configured_teacher_call_budget",
        "available_new_candidate_slots",
        "teacher_calls",
        "resumed_teacher_proposals",
    )
    if not all(_nonnegative_int(value.get(field)) for field in integer_fields):
        issues.append("teacher_counts_invalid")
    records = value.get("teacher_proposal_records")
    candidates = value.get("candidate_files")
    clusters = value.get("teacher_evidence_clusters")
    attempted = value.get("attempted_evidence_cluster_ids")
    fingerprints = value.get("attempted_evidence_fingerprints")
    if not isinstance(records, list) or not all(isinstance(item, dict) for item in records):
        issues.append("teacher_proposal_records_invalid")
        records = []
    if not _string_list(candidates) or len(candidates) != len(set(candidates or [])):
        issues.append("teacher_candidate_files_invalid")
        candidates = []
    if not isinstance(clusters, list) or not all(isinstance(item, dict) for item in clusters):
        issues.append("teacher_evidence_clusters_invalid")
        clusters = []
    if (
        not _string_list(attempted)
        or not _string_list(fingerprints)
        or len(attempted or []) != len(fingerprints or [])
    ):
        issues.append("teacher_attempted_clusters_invalid")
        attempted = []
    if len(records) != len(attempted) or len(candidates) > 3 or len(attempted) > 3:
        issues.append("teacher_candidate_budget_invalid")
    if (
        _nonnegative_int(value.get("teacher_calls"))
        and _nonnegative_int(value.get("resumed_teacher_proposals"))
        and int(value["teacher_calls"]) + int(value["resumed_teacher_proposals"]) != len(records)
    ):
        issues.append("teacher_call_accounting_invalid")
    candidate_ids = sorted(
        {
            str(record["candidate_skill_id"])
            for record in records
            if isinstance(record.get("candidate_skill_id"), str)
        }
    )
    return {
        "status": "invalid"
        if issues
        else ("verified" if bound_record is not None else "diagnostic_unbound"),
        "issues": sorted(set(issues)),
        "informative_group_count": value.get("end_to_end_reward_informative_groups"),
        "trajectory_contrast_group_count": value.get("trajectory_contrast_groups"),
        "new_contrast_patch_count": value.get("new_trajectory_contrast_patches"),
        "cumulative_contrast_patch_count": value.get("cumulative_trajectory_contrast_patches"),
        "evidence_cluster_count": len(clusters),
        "eligible_evidence_cluster_count": value.get("eligible_teacher_evidence_clusters"),
        "attempted_evidence_cluster_count": len(attempted),
        "teacher_calls": value.get("teacher_calls"),
        "resumed_teacher_calls": value.get("resumed_teacher_proposals"),
        "candidate_count": len(candidates),
        "candidate_skill_ids": candidate_ids,
        "groups_without_contrast": value.get("groups_without_trajectory_contrast_reasons", {}),
        "artifact": _record_for_report(root, path),
    }


def _admission_contract(
    root: Path,
    run_id: str,
    round_index: int,
    *,
    expected_input_ids: list[str],
    expected_input_hash: str,
    bound_record: object | None,
) -> dict[str, Any]:
    path = root / "runs" / run_id / "reports" / f"skill_admission_round_{round_index:02d}.json"
    value = _json_object(path)
    if value is None:
        return {
            "status": "absent" if not path.exists() else "invalid",
            "issues": [] if not path.exists() else ["admission_report_unreadable"],
        }
    issues: list[str] = []
    if bound_record is not None and not _artifact_matches(root, bound_record, path):
        issues.append("admission_artifact_mismatch")
    expected_fields = {
        "schema_version",
        "run_id",
        "round",
        "status",
        "admission_role",
        "per_candidate_outcome_gate",
        "baseline_active_skill_ids",
        "baseline_skill_library_sha256",
        "records",
        "new_candidate_files",
        "deduplicated_candidates",
        "prompt_capacity_admission_order",
        "prompt_capacity_rejections",
        "admitted_skill_files",
        "admitted_skill_ids",
        "output_active_skill_ids",
        "output_skill_library_sha256",
        "output_skill_library_version",
        "invalid_candidate_files",
        "grounding_implementation_sha256",
        "teacher_prompt_sha256",
        "completed_at",
    }
    if set(value) != expected_fields:
        issues.append("admission_fields_drift")
    if not (
        value.get("schema_version") == ADMISSION_SCHEMA
        and value.get("run_id") == run_id
        and value.get("round") == round_index
        and value.get("status") == "source_grounded_skills_admitted_to_working_library"
        and value.get("admission_role") == "hard_trust_gate_not_candidate_efficacy_test"
        and value.get("per_candidate_outcome_gate") is False
        and value.get("baseline_active_skill_ids") == expected_input_ids
        and value.get("baseline_skill_library_sha256") == expected_input_hash
    ):
        issues.append("admission_binding_invalid")
    records = value.get("records")
    if not isinstance(records, list) or not all(isinstance(item, dict) for item in records):
        records = []
        issues.append("admission_records_invalid")
    ids = [
        str(record.get("skill_id")) for record in records if isinstance(record.get("skill_id"), str)
    ]
    if len(ids) != len(records) or len(ids) != len(set(ids)) or len(ids) > 3:
        issues.append("admission_candidate_budget_invalid")
    candidate_files = value.get("new_candidate_files")
    if not _string_list(candidate_files) or len(candidate_files) != len(records):
        issues.append("admission_candidate_files_invalid")
    for record in records:
        skill_id = record.get("skill_id")
        candidate_file = record.get("candidate_file")
        candidate_hash = record.get("candidate_sha256")
        if (
            not isinstance(skill_id, str)
            or not isinstance(candidate_file, str)
            or not isinstance(candidate_hash, str)
        ):
            continue
        candidate_path = root / candidate_file
        if (
            candidate_path.resolve()
            != (root / "runs" / run_id / "skills" / "candidates" / f"{skill_id}.yaml").resolve()
            or not candidate_path.is_file()
            or sha256_file(candidate_path) != candidate_hash
        ):
            issues.append(f"candidate_artifact_invalid:{skill_id}")
    admitted_ids = value.get("admitted_skill_ids")
    output_ids = value.get("output_active_skill_ids")
    if not _string_list(admitted_ids, sorted_unique=True):
        admitted_ids = []
        issues.append("admitted_skill_ids_invalid")
    if not _string_list(output_ids, sorted_unique=True):
        output_ids = []
        issues.append("output_skill_ids_invalid")
    valid_ids = sorted(str(record["skill_id"]) for record in records if record.get("valid") is True)
    rejected_ids = sorted(
        str(record["skill_id"]) for record in records if record.get("valid") is False
    )
    if len(valid_ids) + len(rejected_ids) != len(records):
        issues.append("admission_record_decisions_invalid")
    if admitted_ids != valid_ids:
        issues.append("admitted_skill_membership_mismatch")
    if output_ids != sorted({*expected_input_ids, *admitted_ids}):
        issues.append("output_skill_transition_invalid")
    return {
        "status": "invalid"
        if issues
        else ("verified" if bound_record is not None else "diagnostic_unbound"),
        "issues": sorted(set(issues)),
        "candidate_count": len(records),
        "admitted_count": len(admitted_ids),
        "admitted_skill_ids": admitted_ids,
        "rejected_count": len(rejected_ids),
        "rejected_skill_ids": rejected_ids,
        "deduplicated_count": len(value.get("deduplicated_candidates") or []),
        "input_active_skill_ids": expected_input_ids,
        "input_skill_library_sha256": expected_input_hash,
        "output_active_skill_ids": output_ids,
        "output_skill_library_version": value.get("output_skill_library_version"),
        "output_skill_library_sha256": value.get("output_skill_library_sha256"),
        "artifact": _record_for_report(root, path),
    }


def _curve_point_contract(
    root: Path,
    run_id: str,
    batch_id: str,
    round_index: int,
    run_manifest_sha256: str | None,
    *,
    expected_sentinel_ids: list[str],
    expected_evidence_role: str,
    expected_input_ids: list[str],
    expected_input_hash: str,
    bound_record: object | None,
) -> dict[str, Any]:
    path = root / "runs" / run_id / "reports" / f"development_curve_point_{round_index:02d}.json"
    value = _json_object(path)
    if value is None:
        return {
            "status": "absent" if not path.exists() else "invalid",
            "issues": [] if not path.exists() else ["curve_point_unreadable"],
            "primary_metric": None,
        }
    issues: list[str] = []
    if bound_record is not None and not _artifact_matches(root, bound_record, path):
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
    identity = not expected_input_ids
    if set(value) != expected_fields:
        issues.append("curve_point_fields_drift")
    if not (
        value.get("schema_version") == CURVE_POINT_SCHEMA
        and value.get("run_id") == run_id
        and value.get("run_manifest_sha256") == run_manifest_sha256
        and value.get("round") == round_index
        and value.get("batch_id") == batch_id
        and value.get("case_limit") is None
        and value.get("status") == "prequential_fixed_shadow_complete"
        and value.get("evidence_role") == expected_evidence_role
        and value.get("sentinel_case_ids") == expected_sentinel_ids
        and value.get("input_active_skill_ids") == expected_input_ids
        and value.get("input_skill_library_sha256") == expected_input_hash
        and value.get("identity_baseline") is identity
    ):
        issues.append("curve_point_binding_invalid")
    curve = value.get("curve")
    expected_pairs = len(expected_sentinel_ids) * len(EXPECTED_TRAINING_SEEDS)
    metric = None
    if not isinstance(curve, dict):
        issues.append("curve_statistics_missing")
    else:
        metrics = curve.get("metrics")
        if not isinstance(metrics, dict) or set(metrics) != set(CURVE_METRICS):
            issues.append("curve_metric_set_invalid")
            metrics = {}
        metric = _curve_metric_delta(metrics.get(PRIMARY_METRIC))
        if metric is None:
            issues.append("primary_metric_invalid")
        if not (
            curve.get("report_type") == "prequential_current_library_vs_empty_library"
            and curve.get("sentinel_id") == batch_id
            and curve.get("direction") == "current_library_minus_empty_library"
            and curve.get("identity_baseline") is identity
            and curve.get("current_library_version") == expected_input_hash
            and curve.get("current_skill_ids") == expected_input_ids
            and curve.get("pair_count") == expected_pairs
            and curve.get("case_cluster_count") == len(expected_sentinel_ids)
        ):
            issues.append("curve_statistics_binding_invalid")
        pairs = curve.get("pairs")
        cases = curve.get("cases")
        if not isinstance(pairs, list) or len(pairs) != expected_pairs:
            issues.append("curve_pairs_incomplete")
            pairs = []
        if not isinstance(cases, list) or len(cases) != len(expected_sentinel_ids):
            issues.append("curve_cases_incomplete")
        current_ids = {
            str(row.get("current_trajectory_id")) for row in pairs if isinstance(row, dict)
        }
        empty_ids = {str(row.get("empty_trajectory_id")) for row in pairs if isinstance(row, dict)}
        current_records = value.get("current_trajectory_artifacts")
        current_scores = value.get("current_evaluation_artifacts")
        if (
            not isinstance(current_records, dict)
            or set(current_records) != current_ids
            or not all(
                _artifact_matches(
                    root,
                    current_records[trajectory_id],
                    root / "runs" / run_id / "trajectories" / batch_id / f"{trajectory_id}.json",
                )
                for trajectory_id in current_ids
            )
        ):
            issues.append("curve_current_trajectory_artifacts_invalid")
        if (
            not isinstance(current_scores, dict)
            or set(current_scores) != current_ids
            or not all(
                _artifact_matches(
                    root,
                    current_scores[trajectory_id],
                    root / "runs" / run_id / "evaluations" / f"{trajectory_id}.json",
                )
                for trajectory_id in current_ids
            )
        ):
            issues.append("curve_current_evaluation_artifacts_invalid")
        if identity:
            if (
                value.get("empty_trajectory_artifacts") != {}
                or value.get("empty_evaluation_artifacts") != {}
                or value.get("intervention_isolation_artifact") is not None
                or current_ids != empty_ids
            ):
                issues.append("curve_identity_arm_invalid")
        else:
            shadow = f"learning_curve_shadow_{batch_id}"
            empty_records = value.get("empty_trajectory_artifacts")
            empty_scores = value.get("empty_evaluation_artifacts")
            if (
                not isinstance(empty_records, dict)
                or set(empty_records) != empty_ids
                or not all(
                    _artifact_matches(
                        root,
                        empty_records[trajectory_id],
                        root / "runs" / run_id / "trajectories" / shadow / f"{trajectory_id}.json",
                    )
                    for trajectory_id in empty_ids
                )
            ):
                issues.append("curve_empty_trajectory_artifacts_invalid")
            if (
                not isinstance(empty_scores, dict)
                or set(empty_scores) != empty_ids
                or not all(
                    _artifact_matches(
                        root,
                        empty_scores[trajectory_id],
                        root / "runs" / run_id / "evaluations" / f"{trajectory_id}.json",
                    )
                    for trajectory_id in empty_ids
                )
            ):
                issues.append("curve_empty_evaluation_artifacts_invalid")
            isolation_path = (
                root
                / "runs"
                / run_id
                / "health"
                / f"development_curve_intervention_isolation_{batch_id}.json"
            )
            if not _artifact_matches(
                root, value.get("intervention_isolation_artifact"), isolation_path
            ):
                issues.append("curve_intervention_isolation_invalid")
    status = (
        "invalid" if issues else ("verified" if bound_record is not None else "diagnostic_unbound")
    )
    return {
        "status": status,
        "issues": sorted(set(issues)),
        "identity_baseline": value.get("identity_baseline"),
        "input_active_skill_ids": value.get("input_active_skill_ids"),
        "input_skill_library_sha256": value.get("input_skill_library_sha256"),
        "pair_count": (curve or {}).get("pair_count") if isinstance(curve, dict) else None,
        "case_cluster_count": (curve or {}).get("case_cluster_count")
        if isinstance(curve, dict)
        else None,
        "primary_metric": metric,
        "evidence_role": value.get("evidence_role"),
        "artifact": _record_for_report(root, path),
    }


def _learning_contract(
    root: Path,
    run_id: str,
    batch_id: str,
    round_index: int,
    *,
    expected_input_ids: list[str],
    expected_input_hash: str,
    expected_output_ids: list[str],
    expected_output_hash: str,
    expected_admitted_ids: list[str],
    expected_evidence_role: str,
    curve: dict[str, Any],
    bound_record: object | None,
) -> dict[str, Any]:
    path = root / "runs" / run_id / "reports" / f"learning_checkpoint_{round_index:02d}.json"
    value = _json_object(path)
    if value is None:
        return {
            "status": "absent" if not path.exists() else "invalid",
            "issues": [] if not path.exists() else ["learning_checkpoint_unreadable"],
        }
    issues: list[str] = []
    if bound_record is not None and not _artifact_matches(root, bound_record, path):
        issues.append("learning_checkpoint_artifact_mismatch")
    expected_fields = {
        "schema_version",
        "run_id",
        "checkpoint",
        "batch_id",
        "status",
        "admitted_from_current_block",
        "measured_input_active_skill_ids",
        "measured_input_skill_library_sha256",
        "development_curve_artifact",
        "active_skill_ids",
        "active_skill_library_sha256",
        "evidence_role",
        "curve_identity_baseline",
        "completed_at",
    }
    if set(value) != expected_fields:
        issues.append("learning_checkpoint_fields_drift")
    if not (
        value.get("schema_version") == LEARNING_CHECKPOINT_SCHEMA
        and value.get("run_id") == run_id
        and value.get("checkpoint") == round_index
        and value.get("batch_id") == batch_id
        and value.get("status") == "measured_prequential_learning_checkpoint"
        and value.get("admitted_from_current_block") == expected_admitted_ids
        and value.get("measured_input_active_skill_ids") == expected_input_ids
        and value.get("measured_input_skill_library_sha256") == expected_input_hash
        and value.get("development_curve_artifact") == curve.get("artifact")
        and value.get("active_skill_ids") == expected_output_ids
        and value.get("active_skill_library_sha256") == expected_output_hash
        and value.get("evidence_role") == expected_evidence_role
        and value.get("curve_identity_baseline") == curve.get("identity_baseline")
    ):
        issues.append("learning_checkpoint_binding_invalid")
    return {
        "status": "invalid"
        if issues
        else ("verified" if bound_record is not None else "diagnostic_unbound"),
        "issues": sorted(set(issues)),
        "admitted_from_current_block": value.get("admitted_from_current_block", []),
        "measured_input_active_skill_ids": value.get("measured_input_active_skill_ids", []),
        "active_skill_ids": value.get("active_skill_ids", []),
        "artifact": _record_for_report(root, path),
    }


def _maintenance_contract(
    root: Path,
    run_id: str,
    batch_id: str,
    round_index: int,
    *,
    expected_input_ids: list[str],
    expected_input_hash: str,
    expected_output_ids: list[str],
    expected_output_hash: str,
    curve: dict[str, Any],
    bound_record: object | None,
) -> dict[str, Any]:
    scheduled = round_index in {2, 4, 6, 8}
    path = root / "runs" / run_id / "reports" / f"library_maintenance_{round_index:02d}.json"
    value = _json_object(path)
    if not scheduled:
        if value is not None or bound_record is not None:
            return {
                "status": "invalid",
                "scheduled": False,
                "issues": ["unscheduled_maintenance_artifact"],
            }
        return {"status": "not_scheduled", "scheduled": False, "issues": []}
    if value is None:
        return {
            "status": "absent" if not path.exists() else "invalid",
            "scheduled": True,
            "issues": [] if not path.exists() else ["maintenance_report_unreadable"],
        }
    issues: list[str] = []
    if bound_record is not None and not _artifact_matches(root, bound_record, path):
        issues.append("maintenance_artifact_mismatch")
    if not (
        value.get("schema_version") == MAINTENANCE_SCHEMA
        and value.get("run_id") == run_id
        and value.get("round") == round_index
        and value.get("batch_id") == batch_id
        and value.get("maintenance_scope") == "whole_working_library"
        and value.get("automatic_candidate_effect_pruning") is False
        and value.get("observed_input_skill_ids") == expected_input_ids
        and value.get("observed_input_skill_library_sha256") == expected_input_hash
        and value.get("output_active_skill_ids") == expected_output_ids
        and value.get("output_skill_library_sha256") == expected_output_hash
        and value.get("prequential_curve_artifact") == curve.get("artifact")
        and value.get("prequential_primary_metric") is not None
        and value.get("actions") == []
    ):
        issues.append("maintenance_binding_invalid")
    return {
        "status": "invalid"
        if issues
        else ("verified" if bound_record is not None else "diagnostic_unbound"),
        "scheduled": True,
        "issues": sorted(set(issues)),
        "library_health": value.get("status"),
        "domain_counts": value.get("domain_counts", {}),
        "objective_counts": value.get("objective_counts", {}),
        "static_issues": value.get("static_issues", {}),
        "exact_duplicate_groups": value.get("exact_duplicate_groups", []),
        "prompt_capacity_issues": value.get("prompt_capacity_issues", []),
        "artifact": _record_for_report(root, path),
    }


def _block_completion_contract(
    root: Path,
    run_id: str,
    batch: dict[str, Any],
    round_index: int,
    run_manifest_sha256: str | None,
    matrix: list[dict[str, Any]],
    *,
    expected_input_ids: list[str],
    expected_input_hash: str,
    expected_input_version: str,
    expected_sentinel_ids: list[str],
    expected_evidence_role: str,
) -> dict[str, Any]:
    batch_id = str(batch["batch_id"])
    run_root = root / "runs" / run_id
    path = run_root / "manifests" / f"{batch_id}__complete.json"
    value, error = _manifest(path)
    if value is None:
        return {
            "status": "absent" if not path.exists() else "invalid",
            "issues": [] if not path.exists() else [str(error)],
            "stage": None,
        }
    issues: list[str] = []
    expected_fields = {
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
        "input_skill_library_version",
        "input_skill_library_sha256",
        "expected_matrix_sha256",
        "trajectory_artifacts",
        "evaluation_artifacts",
        "health_artifact",
        "teacher_artifact",
        "skill_admission_artifact",
        "development_curve_artifact",
        "learning_checkpoint_artifact",
        "maintenance_artifact",
        "admitted_skill_ids",
        "rejected_skill_ids",
        "output_active_skill_ids",
        "output_skill_library_version",
        "output_skill_library_sha256",
        "completed_at",
        "content_sha256",
    }
    if set(value) != expected_fields:
        issues.append("block_completion_fields_drift")
    if not (
        value.get("schema_version") == BLOCK_SCHEMA
        and value.get("run_id") == run_id
        and value.get("run_manifest_sha256") == run_manifest_sha256
        and value.get("round") == round_index
        and value.get("batch_id") == batch_id
        and value.get("stage") == "direct_skill_accumulation_complete"
        and value.get("case_limit") is None
        and value.get("trajectory_schema_version") == TRAJECTORY_SCHEMA
        and value.get("evaluation_schema_version") == EVALUATION_SCHEMA
        and value.get("input_active_skill_ids") == expected_input_ids
        and value.get("input_skill_library_sha256") == expected_input_hash
        and value.get("input_skill_library_version") == expected_input_version
        and value.get("expected_matrix_sha256") == canonical_json_sha256(matrix)
    ):
        issues.append("block_completion_binding_invalid")
    expected_ids = {str(row["trajectory_id"]) for row in matrix}
    for field, directory in (
        ("trajectory_artifacts", run_root / "trajectories" / batch_id),
        ("evaluation_artifacts", run_root / "evaluations"),
    ):
        records = value.get(field)
        if (
            not isinstance(records, dict)
            or set(records) != expected_ids
            or not all(
                _artifact_matches(root, records[trajectory_id], directory / f"{trajectory_id}.json")
                for trajectory_id in expected_ids
            )
        ):
            issues.append(f"{field}_invalid")
    health, soft = _health_contract(
        root,
        run_id,
        batch_id,
        expected_trajectory_count=len(matrix),
        bound_record=value.get("health_artifact"),
    )
    teacher = _teacher_contract(
        root, run_id, round_index, bound_record=value.get("teacher_artifact")
    )
    admission = _admission_contract(
        root,
        run_id,
        round_index,
        expected_input_ids=expected_input_ids,
        expected_input_hash=expected_input_hash,
        bound_record=value.get("skill_admission_artifact"),
    )
    curve = _curve_point_contract(
        root,
        run_id,
        batch_id,
        round_index,
        run_manifest_sha256,
        expected_sentinel_ids=expected_sentinel_ids,
        expected_evidence_role=expected_evidence_role,
        expected_input_ids=expected_input_ids,
        expected_input_hash=expected_input_hash,
        bound_record=value.get("development_curve_artifact"),
    )
    output_ids = value.get("output_active_skill_ids")
    output_ids = output_ids if _string_list(output_ids, sorted_unique=True) else []
    admitted_ids = value.get("admitted_skill_ids")
    admitted_ids = admitted_ids if _string_list(admitted_ids, sorted_unique=True) else []
    rejected_ids = value.get("rejected_skill_ids")
    rejected_ids = rejected_ids if _string_list(rejected_ids, sorted_unique=True) else []
    if not _string_list(value.get("output_active_skill_ids"), sorted_unique=True):
        issues.append("block_output_skill_ids_invalid")
    if not _string_list(value.get("admitted_skill_ids"), sorted_unique=True) or not _string_list(
        value.get("rejected_skill_ids"), sorted_unique=True
    ):
        issues.append("block_skill_decision_ids_invalid")
    if output_ids != sorted({*expected_input_ids, *admitted_ids}):
        issues.append("block_skill_transition_invalid")
    if (
        admitted_ids != admission.get("admitted_skill_ids")
        or rejected_ids != admission.get("rejected_skill_ids")
        or output_ids != admission.get("output_active_skill_ids")
        or value.get("output_skill_library_sha256") != admission.get("output_skill_library_sha256")
        or value.get("output_skill_library_version")
        != admission.get("output_skill_library_version")
    ):
        issues.append("block_admission_transition_mismatch")
    learning = _learning_contract(
        root,
        run_id,
        batch_id,
        round_index,
        expected_input_ids=expected_input_ids,
        expected_input_hash=expected_input_hash,
        expected_output_ids=output_ids,
        expected_output_hash=str(value.get("output_skill_library_sha256") or ""),
        expected_admitted_ids=admitted_ids,
        expected_evidence_role=expected_evidence_role,
        curve=curve,
        bound_record=value.get("learning_checkpoint_artifact"),
    )
    maintenance = _maintenance_contract(
        root,
        run_id,
        batch_id,
        round_index,
        expected_input_ids=expected_input_ids,
        expected_input_hash=expected_input_hash,
        expected_output_ids=output_ids,
        expected_output_hash=str(value.get("output_skill_library_sha256") or ""),
        curve=curve,
        bound_record=value.get("maintenance_artifact"),
    )
    required = (health, soft, teacher, admission, curve, learning, maintenance)
    if any(item.get("status") == "invalid" for item in required):
        issues.append("bound_block_artifact_invalid")
    if health.get("status") != "verified" or health.get("healthy") is not True:
        issues.append("bound_hard_health_not_verified")
    if teacher.get("status") != "verified":
        issues.append("bound_teacher_not_verified")
    if admission.get("status") != "verified":
        issues.append("bound_admission_not_verified")
    if curve.get("status") != "verified" or learning.get("status") != "verified":
        issues.append("bound_learning_evidence_not_verified")
    expected_maintenance_status = "verified" if round_index in {2, 4, 6, 8} else "not_scheduled"
    if maintenance.get("status") != expected_maintenance_status:
        issues.append("bound_maintenance_schedule_invalid")
    return {
        "status": "invalid" if issues else "verified",
        "stage": value.get("stage"),
        "issues": sorted(set(issues)),
        "sha256": sha256_file(path),
        "artifact": _record_for_report(root, path),
        "input_active_skill_ids": value.get("input_active_skill_ids", []),
        "input_skill_library_version": value.get("input_skill_library_version"),
        "input_skill_library_sha256": value.get("input_skill_library_sha256"),
        "admitted_skill_ids": admitted_ids,
        "rejected_skill_ids": rejected_ids,
        "output_active_skill_ids": output_ids,
        "output_skill_library_version": value.get("output_skill_library_version"),
        "output_skill_library_sha256": value.get("output_skill_library_sha256"),
        "health": health,
        "soft_behavior": soft,
        "teacher": teacher,
        "admission": admission,
        "development_curve": curve,
        "learning_checkpoint": learning,
        "maintenance": maintenance,
    }


def classify_batch_progress(
    *,
    expected: int,
    successful: int,
    errors: int,
    scored: int,
    completion_status: str,
) -> tuple[str, list[str]]:
    """Classify execution progress without treating weak policy yield as corruption."""

    if successful < expected:
        if errors:
            return "resumable_rollout_failure", [
                "error_trajectories_must_be_rerun",
                "complete_matrix_required_before_scoring",
            ]
        return "rollout_in_progress", ["complete_matrix_required_before_scoring"]
    if scored < expected:
        return "semantic_scoring_in_progress", ["complete_scoring_matrix_required"]
    if completion_status == "verified":
        return "complete", []
    if completion_status == "invalid":
        return "invalid_artifact_contract", ["schema5_block_contract_failed"]
    return "teacher_and_skill_transition_pending", []


def _curve_summary_contract(
    root: Path,
    run_id: str,
    batches: list[dict[str, Any]],
    completions: dict[str, dict[str, Any]],
    expected_evidence_role: str,
) -> dict[str, Any]:
    path = root / "runs" / run_id / "reports" / "development_learning_curve.json"
    value = _json_object(path)
    if value is None:
        return {
            "status": "absent" if not path.exists() else "invalid",
            "issues": [] if not path.exists() else ["curve_summary_unreadable"],
        }
    issues: list[str] = []
    completed = [
        (index, str(batch["batch_id"]), completions[str(batch["batch_id"])])
        for index, batch in enumerate(batches, start=1)
        if completions[str(batch["batch_id"])].get("status") == "verified"
    ]
    points = value.get("points")
    series = value.get("series")
    expected_status = "complete" if len(completed) == len(batches) else "partial"
    if not (
        value.get("schema_version") == CURVE_SUMMARY_SCHEMA
        and value.get("run_id") == run_id
        and value.get("status") == expected_status
        and value.get("evidence_role") == expected_evidence_role
        and value.get("expected_points") == len(batches)
        and value.get("completed_points") == len(completed)
        and value.get("direction") == "current_input_library_minus_empty_library"
        and isinstance(points, list)
        and len(points) == len(completed)
        and isinstance(series, dict)
    ):
        issues.append("curve_summary_binding_invalid")
        points = points if isinstance(points, list) else []
        series = series if isinstance(series, dict) else {}
    expected_point_fields = {
        "round",
        "batch_id",
        "input_active_skill_ids",
        "input_skill_library_sha256",
        "output_active_skill_ids",
        "output_skill_library_sha256",
        "admitted_from_current_block",
        "identity_baseline",
        "pair_count",
        "case_cluster_count",
        "artifact",
    }
    for point, (round_index, batch_id, completion) in zip(points, completed, strict=False):
        curve = completion["development_curve"]
        if (
            not isinstance(point, dict)
            or set(point) != expected_point_fields
            or not (
                point.get("round") == round_index
                and point.get("batch_id") == batch_id
                and point.get("input_active_skill_ids") == completion.get("input_active_skill_ids")
                and point.get("input_skill_library_sha256")
                == completion.get("input_skill_library_sha256")
                and point.get("output_active_skill_ids")
                == completion.get("output_active_skill_ids")
                and point.get("output_skill_library_sha256")
                == completion.get("output_skill_library_sha256")
                and point.get("admitted_from_current_block") == completion.get("admitted_skill_ids")
                and point.get("identity_baseline") == curve.get("identity_baseline")
                and point.get("pair_count") == curve.get("pair_count")
                and point.get("case_cluster_count") == curve.get("case_cluster_count")
                and point.get("artifact") == curve.get("artifact")
            )
        ):
            issues.append(f"curve_summary_point_invalid:{batch_id}")
    if completed and set(series) != set(CURVE_METRICS):
        issues.append("curve_summary_metric_set_invalid")
    return {
        "status": "invalid" if issues else "verified",
        "issues": sorted(set(issues)),
        "summary_state": value.get("status"),
        "completed_points": value.get("completed_points"),
        "expected_points": value.get("expected_points"),
        "artifact": _record_for_report(root, path),
    }


def _training_complete_contract(
    root: Path,
    run_id: str,
    run_manifest_sha256: str | None,
    batches: list[dict[str, Any]],
    completions: dict[str, dict[str, Any]],
    curve_summary: dict[str, Any],
) -> dict[str, Any]:
    path = root / "runs" / run_id / "manifests" / "training_complete.json"
    value, error = _manifest(path)
    if value is None:
        return {
            "status": "absent" if not path.exists() else "invalid",
            "issues": [] if not path.exists() else [str(error)],
        }
    issues: list[str] = []
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
        "admitted_skill_ids",
        "rejected_skill_ids",
        "skill_admission_reports",
        "library_maintenance_reports",
        "active_skill_ids",
        "active_skill_library_version",
        "active_skill_library_sha256",
        "development_learning_curve_sha256",
        "completed_at",
        "content_sha256",
    }
    if set(value) != expected_fields:
        issues.append("training_complete_fields_drift")
    batch_ids = [str(batch["batch_id"]) for batch in batches]
    completion_hashes = {batch_id: completions[batch_id].get("sha256") for batch_id in batch_ids}
    admission_hashes = {
        batch_id: (completions[batch_id].get("admission") or {}).get("artifact", {}).get("sha256")
        for batch_id in batch_ids
    }
    maintenance_hashes = {
        batch_id: (completions[batch_id].get("maintenance") or {}).get("artifact", {}).get("sha256")
        for index, batch_id in enumerate(batch_ids, start=1)
        if index in {2, 4, 6, 8}
    }
    all_admitted = [
        skill_id
        for batch_id in batch_ids
        for skill_id in completions[batch_id].get("admitted_skill_ids", [])
    ]
    all_rejected = [
        skill_id
        for batch_id in batch_ids
        for skill_id in completions[batch_id].get("rejected_skill_ids", [])
    ]
    final = completions[batch_ids[-1]]
    if not (
        value.get("schema_version") == TRAINING_SUMMARY_SCHEMA
        and value.get("run_id") == run_id
        and value.get("run_manifest_sha256") == run_manifest_sha256
        and value.get("trajectory_schema_version") == TRAJECTORY_SCHEMA
        and value.get("evaluation_schema_version") == EVALUATION_SCHEMA
        and value.get("case_limit") is None
        and value.get("rounds_completed") == EXPECTED_BLOCKS
        and all(completions[batch_id].get("status") == "verified" for batch_id in batch_ids)
        and value.get("round_completion_manifests") == completion_hashes
        and value.get("round_completion_set_sha256") == canonical_json_sha256(completion_hashes)
        and value.get("skill_admission_reports") == admission_hashes
        and value.get("library_maintenance_reports") == maintenance_hashes
        and value.get("admitted_skill_ids") == all_admitted
        and value.get("rejected_skill_ids") == all_rejected
        and value.get("active_skill_ids") == final.get("output_active_skill_ids")
        and value.get("active_skill_library_version") == final.get("output_skill_library_version")
        and value.get("active_skill_library_sha256") == final.get("output_skill_library_sha256")
        and curve_summary.get("status") == "verified"
        and curve_summary.get("summary_state") == "complete"
        and value.get("development_learning_curve_sha256")
        == (curve_summary.get("artifact") or {}).get("sha256")
    ):
        issues.append("training_complete_binding_invalid")
    return {
        "status": "invalid" if issues else "verified",
        "issues": sorted(set(issues)),
        "sha256": sha256_file(path),
        "rounds_completed": value.get("rounds_completed"),
        "admitted_skill_ids": value.get("admitted_skill_ids", []),
        "rejected_skill_ids": value.get("rejected_skill_ids", []),
        "active_skill_ids": value.get("active_skill_ids", []),
    }


def build_report(root: Path, run_id: str) -> dict[str, Any]:
    experiment_path = root / "configs" / "experiments" / "main_experiment.yaml"
    roles_path = root / "configs" / "models" / "roles.yaml"
    data_path = root / "configs" / "data" / "main_corpus.yaml"
    experiment = _yaml_object(experiment_path) or {}
    corpus_config = _yaml_object(data_path) or {}
    batch_relative = (experiment.get("data") or {}).get("training_batches")
    batch_path = root / str(batch_relative or "configs/data/main_training_batches.yaml")
    batch_plan = _yaml_object(batch_path) or {}
    batches = batch_plan.get("batches")
    batches = batches if isinstance(batches, list) else []
    protocol = _protocol_contract(experiment, batch_plan, corpus_config)
    run_root = root / "runs" / run_id
    unsupported = _unsupported_schema_artifacts(run_root)
    data_boundary = {
        "training_case_count": EXPECTED_TRAINING_CASES,
        "training_role": "eight_ordered_skill_accumulation_blocks",
        "public_cn30_role": "held_out_external_test_after_skill_library_freeze_only",
        "public_cn30_used_for_debugging": False,
        "public_cn30_read_by_this_monitor": False,
    }
    if unsupported:
        return {
            "schema_version": MONITOR_SCHEMA,
            "run_id": run_id,
            "protocol": "128_case_8x16_schema5_direct_skill_accumulation",
            "protocol_status": "unsupported_schema",
            "unsupported_artifacts": unsupported,
            "data_boundary": data_boundary,
            "paper_claim_status": "unsupported_historical_run_no_current_claim",
            "interpretation": (
                "This run contains artifacts from a different execution schema. "
                "They are not reinterpreted as current training evidence."
            ),
        }
    if protocol["status"] != "supported":
        return {
            "schema_version": MONITOR_SCHEMA,
            "run_id": run_id,
            "protocol": "128_case_8x16_schema5_direct_skill_accumulation",
            "protocol_status": protocol["status"],
            "protocol_contract": protocol,
            "data_boundary": data_boundary,
            "paper_claim_status": "unsupported_configuration_no_current_claim",
        }
    manifest = _run_manifest_contract(
        root,
        run_id,
        experiment_path=experiment_path,
        roles_path=roles_path,
        data_path=data_path,
        batch_path=batch_path,
        experiment=experiment,
    )
    manifest_sha = manifest.get("sha256") if manifest.get("status") == "verified" else None
    run_manifest_value = _json_object(run_root / "manifests" / "run.json") or {}
    model_id = str(run_manifest_value.get("model_id") or "")
    model_revision = str(run_manifest_value.get("model_revision") or "")
    input_ids = []
    input_hash = str(run_manifest_value.get("initial_skill_library_sha256") or "")
    input_version = str(run_manifest_value.get("initial_skill_library_id") or "")
    evidence_role = str((experiment.get("learning_curve") or {}).get("evidence_role") or "")
    sentinels_by_block = (experiment.get("learning_curve") or {}).get(
        "sentinel_case_ids_by_block"
    ) or {}
    batch_rows: list[dict[str, Any]] = []
    completions: dict[str, dict[str, Any]] = {}
    all_observed: list[ResearchTrajectory] = []
    prior_complete = True
    first_noncomplete: str | None = None
    hard_blockers: list[str] = []
    for round_index, batch in enumerate(batches, start=1):
        batch_id = str(batch["batch_id"])
        matrix = _expected_matrix(
            run_id=run_id,
            batch=batch,
            input_skill_library_sha256=input_hash,
            model_id=model_id,
            model_revision=model_revision,
        )
        trajectory_scan = _scan_trajectories(root, run_id, batch_id, matrix)
        evaluations = _scan_evaluations(root, run_id, trajectory_scan["values"])
        expected_sentinels = [
            str(case_id)
            for case_id in sentinels_by_block.get(batch_id, [])
            if case_id in set(batch["case_ids"])
        ]
        completion = _block_completion_contract(
            root,
            run_id,
            batch,
            round_index,
            manifest_sha,
            matrix,
            expected_input_ids=input_ids,
            expected_input_hash=input_hash,
            expected_input_version=input_version,
            expected_sentinel_ids=expected_sentinels,
            expected_evidence_role=evidence_role,
        )
        completions[batch_id] = completion
        if completion.get("status") == "verified":
            hard_health = completion["health"]
            soft_behavior = completion["soft_behavior"]
            teacher = completion["teacher"]
            admission = completion["admission"]
            curve = completion["development_curve"]
            learning = completion["learning_checkpoint"]
            maintenance = completion["maintenance"]
        else:
            hard_health, soft_behavior = _health_contract(
                root,
                run_id,
                batch_id,
                expected_trajectory_count=len(matrix),
                bound_record=None,
            )
            teacher = _teacher_contract(root, run_id, round_index, bound_record=None)
            admission = _admission_contract(
                root,
                run_id,
                round_index,
                expected_input_ids=input_ids,
                expected_input_hash=input_hash,
                bound_record=None,
            )
            curve = _curve_point_contract(
                root,
                run_id,
                batch_id,
                round_index,
                manifest_sha,
                expected_sentinel_ids=expected_sentinels,
                expected_evidence_role=evidence_role,
                expected_input_ids=input_ids,
                expected_input_hash=input_hash,
                bound_record=None,
            )
            output_ids = admission.get("output_active_skill_ids", input_ids)
            output_hash = admission.get("output_skill_library_sha256", input_hash)
            learning = _learning_contract(
                root,
                run_id,
                batch_id,
                round_index,
                expected_input_ids=input_ids,
                expected_input_hash=input_hash,
                expected_output_ids=output_ids if isinstance(output_ids, list) else input_ids,
                expected_output_hash=str(output_hash or ""),
                expected_admitted_ids=admission.get("admitted_skill_ids", []),
                expected_evidence_role=evidence_role,
                curve=curve,
                bound_record=None,
            )
            maintenance = _maintenance_contract(
                root,
                run_id,
                batch_id,
                round_index,
                expected_input_ids=input_ids,
                expected_input_hash=input_hash,
                expected_output_ids=output_ids if isinstance(output_ids, list) else input_ids,
                expected_output_hash=str(output_hash or ""),
                curve=curve,
                bound_record=None,
            )
        progress, blockers = classify_batch_progress(
            expected=len(matrix),
            successful=trajectory_scan["successful"],
            errors=trajectory_scan["errors"],
            scored=evaluations["scored"],
            completion_status=str(completion.get("status")),
        )
        if not prior_complete:
            progress = "waiting_for_predecessor"
            blockers = []
        elif (
            manifest.get("status") == "invalid"
            or trajectory_scan["invalid"]
            or evaluations["invalid"]
            or hard_health.get("status") == "invalid"
        ):
            progress = "invalid_artifact_contract"
            blockers = ["current_schema_or_hash_binding_failed"]
        elif hard_health.get("healthy") is False:
            progress = "hard_health_blocked"
            blockers = ["pre_scoring_hard_health_failed"]
        if first_noncomplete is None and progress != "complete":
            first_noncomplete = batch_id
        hard_blockers.extend(f"{batch_id}:{item}" for item in blockers)
        successful_values = trajectory_scan["successful_values"]
        all_observed.extend(successful_values)
        exposure = _skill_exposure(successful_values, input_ids)
        if exposure["undeclared_exposed_skill_ids"]:
            progress = "invalid_artifact_contract"
            blockers = [*blockers, "undeclared_skill_exposure"]
            hard_blockers.append(f"{batch_id}:undeclared_skill_exposure")
        batch_rows.append(
            {
                "round": round_index,
                "batch_id": batch_id,
                "expected_training_trajectories": len(matrix),
                "trajectories": {
                    key: value
                    for key, value in trajectory_scan.items()
                    if key not in {"values", "successful_values"}
                },
                "semantic_scoring": {
                    key: value for key, value in evaluations.items() if key != "values"
                },
                "hard_health": hard_health,
                "soft_behavior": soft_behavior,
                "dialogue_yield": _trajectory_signals(successful_values),
                "evidence_gaps": {
                    "identified_count": evaluations["identified_evidence_gaps"],
                    "scoreable_evaluations": evaluations["evidence_gap_scoreable_evaluations"],
                    "outcome_counts": evaluations["evidence_gap_outcomes"],
                },
                "contrast_and_teacher": teacher,
                "candidate_admission": admission,
                "skill_transition": {
                    "input_active_skill_ids": input_ids,
                    "input_active_skill_count": len(input_ids),
                    "admitted_skill_ids": admission.get("admitted_skill_ids", []),
                    "admitted_skill_count": admission.get("admitted_count", 0),
                    "rejected_skill_ids": admission.get("rejected_skill_ids", []),
                    "rejected_skill_count": admission.get("rejected_count", 0),
                    "output_active_skill_ids": admission.get("output_active_skill_ids", input_ids),
                    "output_active_skill_count": len(
                        admission.get("output_active_skill_ids", input_ids)
                    ),
                },
                "skill_exposure_and_domain_coverage": exposure,
                "prequential_primary_metric": curve.get("primary_metric"),
                "development_curve": curve,
                "learning_checkpoint": learning,
                "maintenance": maintenance,
                "completion_contract": completion,
                "progress": progress,
                "blocking_reasons": blockers,
            }
        )
        prior_complete = progress == "complete"
        if completion.get("status") == "verified":
            input_ids = list(completion["output_active_skill_ids"])
            input_hash = str(completion["output_skill_library_sha256"])
            input_version = str(completion["output_skill_library_version"])
    curve_summary = _curve_summary_contract(root, run_id, batches, completions, evidence_role)
    training_complete = _training_complete_contract(
        root, run_id, manifest_sha, batches, completions, curve_summary
    )
    invalid = (
        manifest.get("status") != "verified"
        or any(row["progress"] == "invalid_artifact_contract" for row in batch_rows)
        or curve_summary.get("status") == "invalid"
        or training_complete.get("status") == "invalid"
    )
    if invalid:
        paper_status = "invalid_or_unverified_run_no_formal_claim"
    elif training_complete.get("status") == "verified":
        paper_status = "frozen_training_complete_external_test_remains_untouched"
    else:
        paper_status = "verified_training_in_progress_no_final_effect_claim"
    current_skills = []
    for row in batch_rows:
        if row["completion_contract"].get("status") == "verified":
            current_skills = row["skill_transition"]["output_active_skill_ids"]
    aggregate_exposure = _skill_exposure(all_observed, current_skills)
    return {
        "schema_version": MONITOR_SCHEMA,
        "run_id": run_id,
        "protocol": "128_case_8x16_schema5_direct_skill_accumulation",
        "protocol_status": "supported",
        "protocol_contract": protocol,
        "data_boundary": data_boundary,
        "evidence_ownership": manifest,
        "current_stage": {
            "first_noncomplete_batch": first_noncomplete,
            "hard_blockers": hard_blockers,
        },
        "batches": batch_rows,
        "aggregate_observed_dialogue_yield": _trajectory_signals(all_observed),
        "skill_library": {
            "current_active_skill_ids": current_skills,
            "current_active_skill_count": len(current_skills),
            "observed_exposure": aggregate_exposure,
        },
        "formal_artifacts": {
            "development_learning_curve_contract": curve_summary,
            "training_complete_contract": training_complete,
            "external_test": "not_read_by_training_progress_monitor",
        },
        "paper_claim_status": paper_status,
        "interpretation": (
            "Raw current-schema files are live diagnostics. A block contributes frozen "
            "training evidence only after its schema-5 completion manifest hash-binds the "
            "64 trajectories, 64 semantic scores, hard/soft health report, teacher evidence, "
            "0-3 candidate trust-gate report, prequential curve, learning checkpoint, and "
            "scheduled library maintenance. The held-out public Chinese 30-case test is not "
            "read or inferred by this monitor."
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
