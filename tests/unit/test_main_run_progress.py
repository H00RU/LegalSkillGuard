from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from legal_skill_guard.experiment.executor import implementation_sha256
from legal_skill_guard.schemas.action import ActionDecision, StructuredAction
from legal_skill_guard.schemas.experiment import ResearchStep, ResearchTrajectory
from legal_skill_guard.schemas.state import FactObservation, StatePatch
from legal_skill_guard.schemas.trajectory import TokenUsage
from legal_skill_guard.utils.hashing import canonical_json_sha256, sha256_file
from scripts.audit_main_run_progress import (
    CURVE_METRICS,
    PRIMARY_METRIC,
    _expected_matrix,
    _maintenance_contract,
    build_report,
    classify_batch_progress,
)

RUN_ID = "formal_run"
MODEL_ID = "Qwen/Qwen3-8B"
MODEL_REVISION = "frozen-revision"
EVIDENCE_ROLE = "development_diagnostic_only_never_teacher_or_skill_admission"
EMPTY_LIBRARY_HASH = canonical_json_sha256([])


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _write_manifest(path: Path, value: dict[str, object]) -> None:
    _write_json(path, {**value, "content_sha256": canonical_json_sha256(value)})


def _record(root: Path, path: Path) -> dict[str, str]:
    return {"path": str(path.relative_to(root)), "sha256": sha256_file(path)}


def _metric(value: float = 0.0) -> dict[str, object]:
    return {
        "empty_library_mean": value,
        "current_library_mean": value,
        "pair_mean_delta": 0.0,
        "pair_median_delta": 0.0,
        "case_cluster_estimate": {
            "mean_delta": 0.0,
            "lower": 0.0,
            "upper": 0.0,
        },
    }


def _project(root: Path) -> dict[str, Any]:
    experiment_path = root / "configs/experiments/main_experiment.yaml"
    roles_path = root / "configs/models/roles.yaml"
    corpus_path = root / "configs/data/main_corpus.yaml"
    batch_path = root / "configs/data/main_training_batches.yaml"
    bootstrap = root / "skills/bootstrap"
    bootstrap.mkdir(parents=True, exist_ok=True)
    (bootstrap / ".gitkeep").write_text("", encoding="utf-8")
    case_ids = [f"case_{index:03d}" for index in range(1, 129)]
    batches = []
    sentinels: dict[str, list[str]] = {}
    for round_index in range(1, 9):
        batch_id = f"training_batch_{round_index:02d}"
        selected = case_ids[(round_index - 1) * 16 : round_index * 16]
        batches.append(
            {
                "batch_id": batch_id,
                "case_ids": selected,
                "persona_assignment": {case_id: "P_WD" for case_id in selected},
            }
        )
        sentinels[batch_id] = selected[:8]
    experiment = {
        "schema_version": 1,
        "data": {
            "training_batches": "configs/data/main_training_batches.yaml",
            "external_evaluation_status": "held_out_frozen_test_not_used_for_debugging",
        },
        "skill_evolution": {"initial_library": "skills/bootstrap"},
        "skill_admission": {
            "mode": "source_grounded_direct_admission",
            "per_candidate_outcome_gate": False,
            "maintenance_interval_blocks": 2,
        },
        "trajectory_sampling": {
            "group_size": 4,
            "training_group_seeds": [42],
        },
        "execution": {
            "evolution_rounds": 8,
            "maximum_new_skills_per_block": 3,
            "teacher_call_budget_per_round": 3,
        },
        "evaluation": {"primary_endpoint": PRIMARY_METRIC},
        "learning_curve": {
            "evidence_role": EVIDENCE_ROLE,
            "sentinel_case_ids_by_block": sentinels,
        },
    }
    batch_plan = {
        "schema_version": 3,
        "design": "balanced_sequential_skill_accumulation_blocks",
        "training_cases": 128,
        "training_batches": 8,
        "cases_per_batch": 16,
        "batches": batches,
    }
    corpus = {
        "schema_version": 7,
        "external_benchmark_policy": {
            "used_for_runtime_debugging": False,
            "used_for_model_prompt_or_threshold_selection": False,
            "evaluation_after_library_freeze_only": True,
            "may_enter_training": False,
            "may_enter_skill_teacher_context": False,
        },
    }
    for path, value in (
        (experiment_path, experiment),
        (batch_path, batch_plan),
        (corpus_path, corpus),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(value, allow_unicode=True), encoding="utf-8")
    roles_path.parent.mkdir(parents=True, exist_ok=True)
    roles_path.write_text("roles: {}\n", encoding="utf-8")
    run_manifest_path = root / f"runs/{RUN_ID}/manifests/run.json"
    _write_manifest(
        run_manifest_path,
        {
            "schema_version": 3,
            "run_id": RUN_ID,
            "experiment_config_sha256": sha256_file(experiment_path),
            "roles_config_sha256": sha256_file(roles_path),
            "data_config_sha256": sha256_file(corpus_path),
            "training_batch_plan_sha256": sha256_file(batch_path),
            "initial_skill_library_path": "skills/bootstrap",
            "initial_skill_library_id": "bootstrap_empty",
            "initial_skill_library_sha256": EMPTY_LIBRARY_HASH,
            "implementation_sha256": implementation_sha256(root),
            "model_id": MODEL_ID,
            "model_revision": MODEL_REVISION,
        },
    )
    return {
        "experiment": experiment,
        "batches": batches,
        "run_manifest_path": run_manifest_path,
    }


def _question_step() -> ResearchStep:
    action = StructuredAction(
        action_type="ask",
        target_type="fact",
        target_id="F1",
        reason="需要确认交易事实",
        expected_information="交易时间",
        content="交易发生在什么时间？",
        confidence=0.8,
    )
    return ResearchStep(
        turn=1,
        visible_input=[],
        state_before={},
        state_patch=StatePatch(
            observations=[
                FactObservation(
                    fact_id="F1",
                    label="交易时间",
                    status="client_claimed",
                    value="2025年1月",
                    target_kind="client_fact",
                )
            ]
        ),
        state_after={},
        raw_policy_output="{}",
        parse_mode="json",
        proposed_action=action,
        action_decision=ActionDecision(original=action, final=action),
        rendered_question=action.content,
        client_response="2025年1月。",
        client_response_kind="new_hidden_fact",
        client_selected_fact_ids=["F1"],
        stop_gate_verdict="CONTINUE",
        stop_gate_reason="还有待核事实",
        token_usage=TokenUsage(),
    )


def _write_trajectory(
    root: Path,
    row: dict[str, Any],
    *,
    exposed_skill_ids: list[str] | None = None,
    with_yield: bool = False,
) -> Path:
    exposed = sorted(exposed_skill_ids or [])
    trajectory = ResearchTrajectory(
        schema_version=16,
        trajectory_id=row["trajectory_id"],
        group_id=row["group_id"],
        sample_index=row["sample_index"],
        run_id=RUN_ID,
        method="training_policy_sample",
        partition=row["partition"],
        case_id=row["case_id"],
        domain="marriage_family" if int(row["case_id"].split("_")[-1]) % 2 else "criminal",
        persona=row["persona"],
        seed=row["seed"],
        model_id=MODEL_ID,
        model_revision=MODEL_REVISION,
        skill_library_version=row["skill_library_version"],
        skill_delivery_mode="prompt_memory" if exposed else "none",
        exposed_skill_ids=exposed,
        skill_memory_sha256="a" * 64,
        status="memo_submitted",
        opening="测试开场",
        max_turns=24,
        steps=[_question_step()] if with_yield else [],
        memo=(
            "## 案情概要\n测试。\n## 关键事实\n待核实。\n## 法律问题\n待分析。\n"
            "## 风险评估\n信息有限。\n## 下一步建议\n补充材料。\n"
            "本备忘录仅基于客户单方陈述作研究性初步分析，不替代持证律师正式意见。"
        ),
        elapsed_seconds=0.1,
        created_at=datetime.now(UTC),
    )
    path = root / f"runs/{RUN_ID}/trajectories/{row['partition']}/{row['trajectory_id']}.json"
    _write_json(path, trajectory.model_dump(mode="json"))
    return path


def _write_evaluation(root: Path, row: dict[str, Any], *, gap: bool = False) -> Path:
    gap_ids = ["E1"] if gap else []
    value = {
        "schema_version": 13,
        "trajectory_id": row["trajectory_id"],
        "case_id": row["case_id"],
        "mechanism_signals": {
            "target_kind_available": True,
            "identified_evidence_gap_ids": gap_ids,
            "identified_evidence_gap_count": len(gap_ids),
            "evidence_gap_outcome": "identified" if gap else "true_zero",
        },
        "reward": {"final_reward": 0.5},
    }
    path = root / f"runs/{RUN_ID}/evaluations/{row['trajectory_id']}.json"
    _write_json(path, value)
    return path


def _matrix(context: dict[str, Any], round_index: int, input_hash: str) -> list[dict[str, Any]]:
    return _expected_matrix(
        run_id=RUN_ID,
        batch=context["batches"][round_index - 1],
        input_skill_library_sha256=input_hash,
        model_id=MODEL_ID,
        model_revision=MODEL_REVISION,
    )


def _write_curve_point(
    root: Path,
    context: dict[str, Any],
    round_index: int,
    matrix: list[dict[str, Any]],
    input_ids: list[str],
    input_hash: str,
) -> Path:
    batch_id = f"training_batch_{round_index:02d}"
    sentinels = context["experiment"]["learning_curve"]["sentinel_case_ids_by_block"][batch_id]
    selected = [row for row in matrix if row["case_id"] in sentinels and row["sample_index"] == 0]
    metrics = {name: _metric() for name in CURVE_METRICS}
    pairs = [
        {
            "pair_id": f"pair_{row['trajectory_id']}",
            "case_id": row["case_id"],
            "persona": row["persona"],
            "seed": row["seed"],
            "sample_index": 0,
            "empty_trajectory_id": row["trajectory_id"],
            "current_trajectory_id": row["trajectory_id"],
            "empty_library": {name: 0.0 for name in metrics},
            "current_library": {name: 0.0 for name in metrics},
            "paired_delta": {name: 0.0 for name in metrics},
        }
        for row in selected
    ]
    current_trajectories = {
        row["trajectory_id"]: _record(
            root,
            root / f"runs/{RUN_ID}/trajectories/{batch_id}/{row['trajectory_id']}.json",
        )
        for row in selected
    }
    current_scores = {
        row["trajectory_id"]: _record(
            root, root / f"runs/{RUN_ID}/evaluations/{row['trajectory_id']}.json"
        )
        for row in selected
    }
    assert not input_ids, "test fixture currently constructs identity curve points"
    value = {
        "schema_version": 1,
        "run_id": RUN_ID,
        "run_manifest_sha256": sha256_file(context["run_manifest_path"]),
        "round": round_index,
        "batch_id": batch_id,
        "case_limit": None,
        "status": "prequential_fixed_shadow_complete",
        "evidence_role": EVIDENCE_ROLE,
        "sentinel_case_ids": sentinels,
        "input_active_skill_ids": input_ids,
        "input_skill_library_sha256": input_hash,
        "empty_skill_library_sha256": EMPTY_LIBRARY_HASH,
        "identity_baseline": True,
        "current_trajectory_artifacts": current_trajectories,
        "current_evaluation_artifacts": current_scores,
        "empty_trajectory_artifacts": {},
        "empty_evaluation_artifacts": {},
        "intervention_isolation_artifact": None,
        "curve": {
            "report_type": "prequential_current_library_vs_empty_library",
            "sentinel_id": batch_id,
            "direction": "current_library_minus_empty_library",
            "identity_baseline": True,
            "current_library_version": input_hash,
            "empty_library_version": EMPTY_LIBRARY_HASH,
            "partition_mapping": {"current": batch_id, "empty": batch_id},
            "current_skill_ids": input_ids,
            "pair_count": len(pairs),
            "case_cluster_count": len(sentinels),
            "bootstrap": {
                "unit": "case_id",
                "samples": 100,
                "confidence_level": 0.95,
                "seed": 42,
            },
            "initial_infrastructure_identity": {"passed": True},
            "metrics": metrics,
            "cases": [{"case_id": case_id, "pair_count": 1} for case_id in sentinels],
            "pairs": pairs,
        },
        "completed_at": "2026-09-09T00:00:00+00:00",
    }
    path = root / f"runs/{RUN_ID}/reports/development_curve_point_{round_index:02d}.json"
    _write_json(path, value)
    return path


def _complete_block(
    root: Path,
    context: dict[str, Any],
    round_index: int,
    *,
    soft_warning_count: int = 0,
    admitted_skill_id: str | None = None,
) -> dict[str, Any]:
    batch_id = f"training_batch_{round_index:02d}"
    input_ids: list[str] = []
    input_hash = EMPTY_LIBRARY_HASH
    input_version = "bootstrap_empty"
    output_ids = [admitted_skill_id] if admitted_skill_id else []
    output_hash = (
        canonical_json_sha256([{"skill_id": admitted_skill_id}])
        if admitted_skill_id
        else input_hash
    )
    output_version = f"library_{output_hash[:16]}" if admitted_skill_id else input_version
    matrix = _matrix(context, round_index, input_hash)
    trajectory_paths: dict[str, Path] = {}
    evaluation_paths: dict[str, Path] = {}
    for index, row in enumerate(matrix):
        trajectory_paths[row["trajectory_id"]] = _write_trajectory(root, row, with_yield=index == 0)
        evaluation_paths[row["trajectory_id"]] = _write_evaluation(root, row, gap=index == 0)
    health_path = root / f"runs/{RUN_ID}/health/pre_scoring_health_{batch_id}.json"
    warning_counts = {"generic_question": soft_warning_count} if soft_warning_count else {}
    _write_json(
        health_path,
        {
            "schema_version": 2,
            "healthy": True,
            "trajectory_count": 64,
            "blocking_issue_count": 0,
            "counts": {},
            "issues": [],
            "issues_truncated": 0,
            "quality_diagnostics": {
                "model_behavior_warning_count": soft_warning_count,
                "model_behavior_warning_counts": warning_counts,
            },
        },
    )
    teacher_path = root / f"runs/{RUN_ID}/manifests/teacher_round_{round_index:02d}.json"
    candidate_path = None
    proposal_path = None
    if admitted_skill_id:
        candidate_path = root / f"runs/{RUN_ID}/skills/candidates/{admitted_skill_id}.yaml"
        candidate_path.parent.mkdir(parents=True, exist_ok=True)
        candidate_path.write_text(
            f"schema_version: 2\nskill_id: {admitted_skill_id}\nstatus: active\n",
            encoding="utf-8",
        )
        proposal_path = (
            root / f"runs/{RUN_ID}/teacher/round_{round_index:02d}/proposal_cluster.json"
        )
        _write_json(proposal_path, {"skill_id": admitted_skill_id})
    candidate_relative = str(candidate_path.relative_to(root)) if candidate_path else None
    proposal_relative = str(proposal_path.relative_to(root)) if proposal_path else None
    _write_manifest(
        teacher_path,
        {
            "schema_version": 2,
            "round": round_index,
            "end_to_end_reward_informative_groups": 2,
            "trajectory_contrast_groups": 1,
            "groups_without_trajectory_contrast_reasons": {"low_variance": 15},
            "selected_groups": 1 if admitted_skill_id else 0,
            "selected_case_ids": [matrix[0]["case_id"]] if admitted_skill_id else [],
            "selected_domains": ["marriage_family"] if admitted_skill_id else [],
            "selected_personas": ["P_WD"] if admitted_skill_id else [],
            "teacher_update_unit": (
                "distinct_cluster_syntheses_from_cumulative_trajectory_contrasts"
            ),
            "pre_reward_attribution_scoreable_groups": 16,
            "pre_reward_attribution_excluded_group_ids": [],
            "evidence_lifecycle": "trajectory_contrast_to_source_grounded_direct_working_library",
            "new_trajectory_contrast_patches": 1,
            "cumulative_trajectory_contrast_patches": round_index,
            "cumulative_evidence_rounds": list(range(1, round_index + 1)),
            "teacher_evidence_group_budget": 15,
            "teacher_evidence_clusters": (
                [{"cluster_id": "cluster_general", "eligible": True}]
                if admitted_skill_id
                else []
            ),
            "eligible_teacher_evidence_clusters": 1 if admitted_skill_id else 0,
            "attempted_evidence_cluster_ids": (
                ["cluster_general"] if admitted_skill_id else []
            ),
            "attempted_evidence_fingerprints": (["e" * 64] if admitted_skill_id else []),
            "attempted_evidence_cluster_id": (
                "cluster_general" if admitted_skill_id else None
            ),
            "attempted_evidence_fingerprint": "e" * 64 if admitted_skill_id else None,
            "teacher_call_budget": 3,
            "configured_teacher_call_budget": 3,
            "available_new_candidate_slots": 3,
            "teacher_calls": 1 if admitted_skill_id else 0,
            "resumed_teacher_proposals": 0,
            "teacher_budget_status_before_round": None,
            "candidate_outcome_feedback_used": False,
            "teacher_proposal_parse_status": (
                "valid_candidate" if admitted_skill_id else "empty_feedback_noop"
            ),
            "teacher_proposal_records": (
                [
                    {
                        "cluster_id": "cluster_general",
                        "evidence_fingerprint": "e" * 64,
                        "proposal_file": proposal_relative,
                        "proposal_batch_id": f"{batch_id}.semantic_advantage.cluster",
                        "selected_group_ids": ["group_1"],
                        "parse_status": "valid_candidate",
                        "source_group_ids": ["group_1"],
                        "candidate_skill_id": admitted_skill_id,
                        "staging_disposition": "staged_unique_candidate",
                        "duplicate_of_skill_id": None,
                    }
                ]
                if admitted_skill_id
                else []
            ),
            "teacher_source_group_ids": ["group_1"] if admitted_skill_id else [],
            "candidate_files": [candidate_relative] if candidate_relative else [],
        },
    )
    admission_path = root / f"runs/{RUN_ID}/reports/skill_admission_round_{round_index:02d}.json"
    _write_json(
        admission_path,
        {
            "schema_version": 5,
            "run_id": RUN_ID,
            "round": round_index,
            "status": "source_grounded_skills_admitted_to_working_library",
            "admission_role": "hard_trust_gate_not_candidate_efficacy_test",
            "per_candidate_outcome_gate": False,
            "baseline_active_skill_ids": input_ids,
            "baseline_skill_library_sha256": input_hash,
            "records": (
                [
                    {
                        "skill_id": admitted_skill_id,
                        "candidate_file": candidate_relative,
                        "candidate_sha256": sha256_file(candidate_path),
                        "candidate_contract_sha256": "f" * 64,
                        "teacher_proposal_file": proposal_relative,
                        "lifecycle": "new_teacher_candidate",
                        "valid": True,
                        "issues": [],
                    }
                ]
                if admitted_skill_id and candidate_path
                else []
            ),
            "new_candidate_files": [candidate_relative] if candidate_relative else [],
            "deduplicated_candidates": [],
            "prompt_capacity_admission_order": output_ids,
            "prompt_capacity_rejections": {},
            "admitted_skill_files": [candidate_relative] if candidate_relative else [],
            "admitted_skill_ids": output_ids,
            "output_active_skill_ids": output_ids,
            "output_skill_library_sha256": output_hash,
            "output_skill_library_version": output_version,
            "invalid_candidate_files": [],
            "grounding_implementation_sha256": "b" * 64,
            "teacher_prompt_sha256": "c" * 64,
            "completed_at": "2026-09-09T00:00:01+00:00",
        },
    )
    curve_path = _write_curve_point(root, context, round_index, matrix, input_ids, input_hash)
    learning_path = root / f"runs/{RUN_ID}/reports/learning_checkpoint_{round_index:02d}.json"
    _write_json(
        learning_path,
        {
            "schema_version": 3,
            "run_id": RUN_ID,
            "checkpoint": round_index,
            "batch_id": batch_id,
            "status": "measured_prequential_learning_checkpoint",
            "admitted_from_current_block": output_ids,
            "measured_input_active_skill_ids": [],
            "measured_input_skill_library_sha256": input_hash,
            "development_curve_artifact": _record(root, curve_path),
            "active_skill_ids": output_ids,
            "active_skill_library_sha256": output_hash,
            "evidence_role": EVIDENCE_ROLE,
            "curve_identity_baseline": True,
            "completed_at": "2026-09-09T00:00:02+00:00",
        },
    )
    maintenance_path = None
    if round_index in {2, 4, 6, 8}:
        maintenance_path = (
            root / f"runs/{RUN_ID}/reports/library_maintenance_{round_index:02d}.json"
        )
        _write_json(
            maintenance_path,
            {
                "schema_version": 1,
                "run_id": RUN_ID,
                "round": round_index,
                "batch_id": batch_id,
                "status": "healthy",
                "maintenance_scope": "whole_working_library",
                "automatic_candidate_effect_pruning": False,
                "reason": "library hygiene",
                "observed_input_skill_ids": [],
                "observed_input_skill_library_sha256": input_hash,
                "output_active_skill_ids": [],
                "output_skill_library_sha256": input_hash,
                "domain_counts": {},
                "objective_counts": {},
                "static_issues": {},
                "exact_duplicate_groups": [],
                "prompt_capacity_issues": [],
                "prequential_curve_artifact": _record(root, curve_path),
                "prequential_primary_metric": _metric(),
                "actions": [],
                "completed_at": "2026-09-09T00:00:03+00:00",
            },
        )
    complete_path = root / f"runs/{RUN_ID}/manifests/{batch_id}__complete.json"
    _write_manifest(
        complete_path,
        {
            "schema_version": 5,
            "run_id": RUN_ID,
            "run_manifest_sha256": sha256_file(context["run_manifest_path"]),
            "round": round_index,
            "batch_id": batch_id,
            "stage": "direct_skill_accumulation_complete",
            "case_limit": None,
            "trajectory_schema_version": 16,
            "evaluation_schema_version": 13,
            "judge_qualification_contract_sha256": "d" * 64,
            "input_active_skill_ids": [],
            "input_skill_library_version": input_version,
            "input_skill_library_sha256": input_hash,
            "expected_matrix_sha256": canonical_json_sha256(matrix),
            "trajectory_artifacts": {
                trajectory_id: _record(root, path)
                for trajectory_id, path in sorted(trajectory_paths.items())
            },
            "evaluation_artifacts": {
                trajectory_id: _record(root, path)
                for trajectory_id, path in sorted(evaluation_paths.items())
            },
            "health_artifact": _record(root, health_path),
            "teacher_artifact": _record(root, teacher_path),
            "skill_admission_artifact": _record(root, admission_path),
            "development_curve_artifact": _record(root, curve_path),
            "learning_checkpoint_artifact": _record(root, learning_path),
            "maintenance_artifact": (
                _record(root, maintenance_path) if maintenance_path is not None else None
            ),
            "admitted_skill_ids": output_ids,
            "rejected_skill_ids": [],
            "output_active_skill_ids": output_ids,
            "output_skill_library_version": output_version,
            "output_skill_library_sha256": output_hash,
            "completed_at": "2026-09-09T00:00:04+00:00",
        },
    )
    return {
        "complete_path": complete_path,
        "admission_path": admission_path,
        "curve_path": curve_path,
        "maintenance_path": maintenance_path,
    }


def _write_curve_summary(root: Path, context: dict[str, Any]) -> Path:
    points = []
    for round_index in range(1, 9):
        batch_id = f"training_batch_{round_index:02d}"
        curve_path = root / f"runs/{RUN_ID}/reports/development_curve_point_{round_index:02d}.json"
        points.append(
            {
                "round": round_index,
                "batch_id": batch_id,
                "input_active_skill_ids": [],
                "input_skill_library_sha256": EMPTY_LIBRARY_HASH,
                "output_active_skill_ids": [],
                "output_skill_library_sha256": EMPTY_LIBRARY_HASH,
                "admitted_from_current_block": [],
                "identity_baseline": True,
                "pair_count": 8,
                "case_cluster_count": 8,
                "artifact": _record(root, curve_path),
            }
        )
    series = {
        name: [
            {
                "round": round_index,
                "batch_id": f"training_batch_{round_index:02d}",
                "empty_library_mean": 0.0,
                "current_library_mean": 0.0,
                "mean_delta": 0.0,
                "confidence_lower": 0.0,
                "confidence_upper": 0.0,
            }
            for round_index in range(1, 9)
        ]
        for name in CURVE_METRICS
    }
    path = root / f"runs/{RUN_ID}/reports/development_learning_curve.json"
    _write_json(
        path,
        {
            "schema_version": 1,
            "run_id": RUN_ID,
            "status": "complete",
            "evidence_role": EVIDENCE_ROLE,
            "expected_points": 8,
            "completed_points": 8,
            "direction": "current_input_library_minus_empty_library",
            "points": points,
            "series": series,
            "updated_at": "2026-09-09T00:01:00+00:00",
        },
    )
    return path


def test_progress_classification_tracks_current_direct_chain() -> None:
    assert classify_batch_progress(
        expected=64,
        successful=63,
        errors=1,
        scored=0,
        completion_status="absent",
    ) == (
        "resumable_rollout_failure",
        ["error_trajectories_must_be_rerun", "complete_matrix_required_before_scoring"],
    )
    assert classify_batch_progress(
        expected=64,
        successful=64,
        errors=0,
        scored=32,
        completion_status="absent",
    ) == ("semantic_scoring_in_progress", ["complete_scoring_matrix_required"])
    assert classify_batch_progress(
        expected=64,
        successful=64,
        errors=0,
        scored=64,
        completion_status="verified",
    ) == ("complete", [])


def test_partial_current_run_reports_live_yield_without_claiming_effect(tmp_path: Path) -> None:
    context = _project(tmp_path)
    row = _matrix(context, 1, EMPTY_LIBRARY_HASH)[0]
    _write_trajectory(tmp_path, row, with_yield=True)

    report = build_report(tmp_path, RUN_ID)

    assert report["protocol_status"] == "supported"
    assert report["evidence_ownership"]["status"] == "verified"
    assert report["batches"][0]["trajectories"]["successful"] == 1
    assert report["batches"][0]["dialogue_yield"]["question_turns"] == 1
    assert report["batches"][0]["dialogue_yield"]["unique_disclosed_facts_per_question"] == 1.0
    assert report["batches"][0]["progress"] == "rollout_in_progress"
    assert report["paper_claim_status"] == "verified_training_in_progress_no_final_effect_claim"
    assert report["data_boundary"]["public_cn30_used_for_debugging"] is False
    assert report["data_boundary"]["public_cn30_read_by_this_monitor"] is False


def test_schema5_block_reports_every_direct_learning_stage(tmp_path: Path) -> None:
    context = _project(tmp_path)
    _complete_block(tmp_path, context, 1, soft_warning_count=2)

    report = build_report(tmp_path, RUN_ID)
    batch = report["batches"][0]

    assert batch["progress"] == "complete"
    assert batch["trajectories"]["successful"] == 64
    assert batch["semantic_scoring"]["scored"] == 64
    assert batch["hard_health"]["status"] == "verified"
    assert batch["hard_health"]["issue_count"] == 0
    assert batch["soft_behavior"]["warning_count"] == 2
    assert batch["dialogue_yield"]["question_turns"] == 1
    assert batch["dialogue_yield"]["unique_disclosed_facts_across_sessions"] == 1
    assert batch["evidence_gaps"]["identified_count"] == 1
    assert batch["contrast_and_teacher"]["trajectory_contrast_group_count"] == 1
    assert batch["contrast_and_teacher"]["teacher_calls"] == 0
    assert batch["contrast_and_teacher"]["candidate_count"] == 0
    assert batch["candidate_admission"]["admitted_count"] == 0
    assert batch["candidate_admission"]["rejected_count"] == 0
    assert batch["skill_transition"]["input_active_skill_count"] == 0
    assert batch["skill_transition"]["output_active_skill_count"] == 0
    assert batch["skill_exposure_and_domain_coverage"]["observed_training_domain_count"] == 2
    assert batch["prequential_primary_metric"]["mean_delta"] == 0.0
    assert batch["maintenance"]["status"] == "not_scheduled"


def test_admitted_skill_becomes_the_next_block_input_without_same_block_effect_claim(
    tmp_path: Path,
) -> None:
    context = _project(tmp_path)
    _complete_block(
        tmp_path,
        context,
        1,
        admitted_skill_id="skill_fact_sequence",
    )

    report = build_report(tmp_path, RUN_ID)
    source = report["batches"][0]
    following = report["batches"][1]

    assert source["candidate_admission"]["candidate_count"] == 1
    assert source["candidate_admission"]["admitted_skill_ids"] == [
        "skill_fact_sequence"
    ]
    assert source["skill_transition"]["input_active_skill_count"] == 0
    assert source["skill_transition"]["output_active_skill_count"] == 1
    assert source["prequential_primary_metric"]["mean_delta"] == 0.0
    assert following["skill_transition"]["input_active_skill_ids"] == [
        "skill_fact_sequence"
    ]
    assert following["progress"] == "rollout_in_progress"


def test_bound_artifact_byte_drift_fails_closed(tmp_path: Path) -> None:
    context = _project(tmp_path)
    _complete_block(tmp_path, context, 1)
    first = next((tmp_path / f"runs/{RUN_ID}/trajectories/training_batch_01").glob("*.json"))
    value = json.loads(first.read_text(encoding="utf-8"))
    value["memo"] += " 被修改"
    _write_json(first, value)

    report = build_report(tmp_path, RUN_ID)

    assert report["batches"][0]["progress"] == "invalid_artifact_contract"
    assert "trajectory_artifacts_invalid" in report["batches"][0]["completion_contract"]["issues"]
    assert report["paper_claim_status"] == "invalid_or_unverified_run_no_formal_claim"


def test_noncurrent_block_schema_is_reported_as_unsupported(tmp_path: Path) -> None:
    _project(tmp_path)
    path = tmp_path / f"runs/{RUN_ID}/manifests/training_batch_01__complete.json"
    _write_manifest(path, {"schema_version": 4, "run_id": RUN_ID})

    report = build_report(tmp_path, RUN_ID)

    assert report["protocol_status"] == "unsupported_schema"
    assert report["unsupported_artifacts"][0]["actual_schema"] == 4
    assert report.get("batches", []) == []


def test_maintenance_contract_is_required_only_on_even_blocks(tmp_path: Path) -> None:
    path = tmp_path / f"runs/{RUN_ID}/reports/library_maintenance_01.json"
    _write_json(path, {"schema_version": 1})
    result = _maintenance_contract(
        tmp_path,
        RUN_ID,
        "training_batch_01",
        1,
        expected_input_ids=[],
        expected_input_hash=EMPTY_LIBRARY_HASH,
        expected_output_ids=[],
        expected_output_hash=EMPTY_LIBRARY_HASH,
        curve={},
        bound_record=None,
    )
    assert result["status"] == "invalid"
    assert result["issues"] == ["unscheduled_maintenance_artifact"]


def test_full_schema5_training_summary_binds_all_eight_blocks(tmp_path: Path) -> None:
    context = _project(tmp_path)
    block_records = [_complete_block(tmp_path, context, round_index) for round_index in range(1, 9)]
    curve_summary = _write_curve_summary(tmp_path, context)
    completion_hashes = {
        f"training_batch_{index:02d}": sha256_file(record["complete_path"])
        for index, record in enumerate(block_records, start=1)
    }
    admission_hashes = {
        f"training_batch_{index:02d}": sha256_file(record["admission_path"])
        for index, record in enumerate(block_records, start=1)
    }
    maintenance_hashes = {
        f"training_batch_{index:02d}": sha256_file(record["maintenance_path"])
        for index, record in enumerate(block_records, start=1)
        if record["maintenance_path"] is not None
    }
    summary_path = tmp_path / f"runs/{RUN_ID}/manifests/training_complete.json"
    _write_manifest(
        summary_path,
        {
            "schema_version": 5,
            "run_id": RUN_ID,
            "run_manifest_sha256": sha256_file(context["run_manifest_path"]),
            "trajectory_schema_version": 16,
            "evaluation_schema_version": 13,
            "case_limit": None,
            "rounds_completed": 8,
            "round_completion_manifests": completion_hashes,
            "round_completion_set_sha256": canonical_json_sha256(completion_hashes),
            "admitted_skill_ids": [],
            "rejected_skill_ids": [],
            "skill_admission_reports": admission_hashes,
            "library_maintenance_reports": maintenance_hashes,
            "active_skill_ids": [],
            "active_skill_library_version": "bootstrap_empty",
            "active_skill_library_sha256": EMPTY_LIBRARY_HASH,
            "development_learning_curve_sha256": sha256_file(curve_summary),
            "completed_at": "2026-09-09T00:02:00+00:00",
        },
    )

    report = build_report(tmp_path, RUN_ID)

    assert all(batch["progress"] == "complete" for batch in report["batches"])
    assert report["formal_artifacts"]["development_learning_curve_contract"]["status"] == "verified"
    assert report["formal_artifacts"]["training_complete_contract"]["status"] == ("verified")
    assert report["paper_claim_status"] == (
        "frozen_training_complete_external_test_remains_untouched"
    )
