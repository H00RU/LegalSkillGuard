from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from legal_skill_guard.experiment.executor import (
    COHORT_GATE_ENDPOINT_DIRECTIONS,
    COHORT_PARENT_EFFECT_DIRECTION,
    LEARNING_CHECKPOINT_SCHEMA,
    _expected_final_training_holdout_config,
    _expected_practical_retention_gate,
    final_training_holdout_safeguard_disposition,
)
from legal_skill_guard.utils.hashing import canonical_json_sha256, sha256_file
from scripts.audit_main_run_progress import (
    CURVE_METRICS,
    EVALUATION_SCHEMA,
    HEALTHY_TERMINAL,
    MONITOR_SCHEMA,
    PRIMARY_METRIC,
    TERMINAL_COMPLETE,
    TRAJECTORY_SCHEMA,
    _curve_point_contract,
    _final_training_holdout_contract,
    _library_effect_disposition_contract,
    _protocol_contract,
    _unsupported_schema_artifacts,
    build_report,
    classify_batch_progress,
)

RUN_ID = "formal_run"
RUN_MANIFEST_SHA = "run-manifest-sha"
EVIDENCE_ROLE = (
    "development_increment_diagnostic_and_next_teacher_direction_"
    "never_external_test"
)
EMPTY_LIBRARY_HASH = canonical_json_sha256([])


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _record(root: Path, path: Path) -> dict[str, str]:
    return {"path": str(path.relative_to(root)), "sha256": sha256_file(path)}


def _cohort_validation() -> dict[str, Any]:
    endpoint_rules = {
        name: {"direction": direction, "margin": 0.0}
        for name, direction in COHORT_GATE_ENDPOINT_DIRECTIONS.items()
    }
    return {
        "status": "frozen_before_next_formal_run",
        "timing": "next_unseen_training_block_before_teacher",
        "comparator": "exact_parent_library",
        "decision_role": "descriptive_increment_measurement_before_teacher_never_skill_veto",
        "single_block_effect_can_prune_or_rollback": False,
        "interval_uncertainty_alone_blocks_accumulation": False,
        "final_block_new_skill_budget": 0,
        "minimum_exposed_cases_for_interpretation": 1,
        "global_playbook_requires_full_cohort_exposure": True,
        "primary_signal": {
            "decision_rule": "primary_positive_point_estimate",
            "endpoints": [PRIMARY_METRIC],
            "threshold": 0.0,
        },
        "practical_effect_classifier": _expected_practical_retention_gate(
            COHORT_PARENT_EFFECT_DIRECTION
        ),
        "interval_diagnostic": {
            "schema_version": 1,
            "decision_rule": "case_cluster_pareto_noninferiority",
            "effect_direction": COHORT_PARENT_EFFECT_DIRECTION,
            "primary_endpoint": PRIMARY_METRIC,
            "protected_endpoints": [
                name for name in COHORT_GATE_ENDPOINT_DIRECTIONS if name != PRIMARY_METRIC
            ],
            "endpoint_rules": endpoint_rules,
        },
    }


def _final_safeguard() -> dict[str, Any]:
    return _expected_final_training_holdout_config()


def _protocol_objects() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
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
        sentinels[batch_id] = selected
    experiment = {
        "data": {
            "training_batches": "configs/data/main_training_batches.yaml",
            "external_evaluation_status": (
                "frozen_public_benchmark_previously_evaluated_aggregate_aware"
            ),
        },
        "skill_evolution": {"initial_library": "skills/bootstrap"},
        "skill_admission": {
            "mode": "group_evidence_global_playbook_evolution",
            "per_candidate_outcome_gate": False,
            "effect_assessment": "descriptive_next_block_increment_then_final_library_test",
            "maintenance_interval_blocks": 2,
        },
        "trajectory_sampling": {
            "group_size": 4,
            "training_group_seeds": [42],
        },
        "execution": {
            "evolution_rounds": 8,
            "maximum_new_skills_per_block": 1,
            "teacher_call_budget_per_round": 3,
        },
        "evaluation": {"primary_endpoint": PRIMARY_METRIC},
        "learning_curve": {
            "mode": "prequential_fixed_shadow",
            "no_pending_cohort_identity_shortcut": True,
            "evidence_role": EVIDENCE_ROLE,
            "incremental_effect_diagnostic": _cohort_validation(),
            "final_cumulative_freeze_safeguard": _final_safeguard(),
            "sentinel_case_ids_by_block": sentinels,
        },
    }
    batch_plan = {
        "schema_version": 3,
        "design": "balanced_sequential_skill_accumulation_blocks",
        "training_cases": 128,
        "training_batches": 8,
        "cases_per_batch": 16,
        "skill_accumulation": {
            "mode": "group_evidence_global_playbook_evolution",
            "first_source_batch": "training_batch_01",
            "final_source_batch": "training_batch_07",
            "effect_assessment": (
                "descriptive_prequential_exact_parent_increment_or_library_identity"
            ),
            "maintenance_interval_blocks": 2,
            "final_batch_generates_skills": False,
        },
        "batches": batches,
    }
    corpus = {
        "external_benchmark_policy": {
            "dlawbench_public_cn30": "frozen_public_benchmark_previously_evaluated",
            "prior_frozen_library_evaluation_completed": True,
            "aggregate_results_used_for_protocol_diagnosis": True,
            "case_level_results_used_for_training_or_skill_selection": False,
            "exposed_to_training_lawyer_or_skill_teacher": False,
            "used_for_runtime_debugging": True,
            "used_for_model_prompt_or_threshold_selection": False,
            "evaluation_after_library_freeze_only": True,
            "may_enter_training": False,
            "may_enter_skill_teacher_context": False,
        }
    }
    return experiment, batch_plan, corpus


def _write_project(root: Path) -> None:
    experiment, batch_plan, corpus = _protocol_objects()
    values = {
        root / "configs/experiments/main_experiment.yaml": experiment,
        root / "configs/data/main_training_batches.yaml": batch_plan,
        root / "configs/data/main_corpus.yaml": corpus,
        root / "configs/models/roles.yaml": {"roles": {}},
    }
    for path, value in values.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(value, allow_unicode=True), encoding="utf-8")
    bootstrap = root / "skills/bootstrap"
    bootstrap.mkdir(parents=True, exist_ok=True)
    (bootstrap / ".gitkeep").write_text("", encoding="utf-8")


def _estimate(delta: float, *, cases: int = 2) -> dict[str, Any]:
    return {
        "pairs": cases,
        "mean_delta": delta,
        "median_delta": delta,
        "lower": delta,
        "upper": delta,
        "confidence_level": 0.95,
        "bootstrap_samples": 100,
        "seed": 42,
    }


def _metric(delta: float, *, identity: bool = False) -> dict[str, Any]:
    value = {
        "parent_library_mean": 1.0,
        "current_library_mean": 1.0 + delta,
        "pair_mean_delta": delta,
        "pair_median_delta": delta,
        "case_cluster_estimate": _estimate(delta),
    }
    if identity:
        value["current_library_mean"] = 1.0
    return value


def _curve_pairs() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    pairs = [
        {
            "pair_id": f"pair-{index}",
            "case_id": f"case-{index}",
            "current_trajectory_id": f"current-{index}",
            "parent_trajectory_id": f"parent-{index}",
        }
        for index in (1, 2)
    ]
    cases = [
        {"case_id": f"case-{index}", "pair_count": 1}
        for index in (1, 2)
    ]
    return pairs, cases


def _write_exact_parent_point(root: Path, *, primary_delta: float = 0.1) -> dict[str, Any]:
    run_root = root / f"runs/{RUN_ID}"
    source = run_root / "manifests/training_batch_01__complete.json"
    _write_json(source, {"stage": "direct_skill_accumulation_complete"})
    pairs, cases = _curve_pairs()
    current_records: dict[str, dict[str, str]] = {}
    current_scores: dict[str, dict[str, str]] = {}
    parent_records: dict[str, dict[str, str]] = {}
    parent_scores: dict[str, dict[str, str]] = {}
    for pair in pairs:
        current_id = pair["current_trajectory_id"]
        parent_id = pair["parent_trajectory_id"]
        current_path = run_root / f"trajectories/training_batch_02/{current_id}.json"
        parent_path = (
            run_root
            / f"trajectories/cohort_parent_shadow_training_batch_02/{parent_id}.json"
        )
        current_score = run_root / f"evaluations/{current_id}.json"
        parent_score = run_root / f"evaluations/{parent_id}.json"
        for path in (current_path, parent_path, current_score, parent_score):
            _write_json(path, {"id": path.stem})
        current_records[current_id] = _record(root, current_path)
        current_scores[current_id] = _record(root, current_score)
        parent_records[parent_id] = _record(root, parent_path)
        parent_scores[parent_id] = _record(root, parent_score)
    isolation_path = (
        run_root
        / "health/parent_cohort_intervention_isolation_training_batch_02.json"
    )
    _write_json(
        isolation_path,
        {
            "passed": True,
            "cohort_exposed_case_count": 2,
            "cohort_skill_exposure": {
                "new-skill": {
                    "routing_complete": True,
                    "observed_case_count": 2,
                    "observed_pair_count": 2,
                    "domain": "general",
                    "expected_case_count": 2,
                    "expected_pair_count": 2,
                }
            },
        },
    )
    metrics = {
        name: _metric(primary_delta if name == PRIMARY_METRIC else 0.0)
        for name in CURVE_METRICS
    }
    point = {
        "schema_version": 2,
        "run_id": RUN_ID,
        "run_manifest_sha256": RUN_MANIFEST_SHA,
        "round": 2,
        "batch_id": "training_batch_02",
        "case_limit": None,
        "status": "prequential_parent_increment_diagnostic_complete",
        "evidence_role": EVIDENCE_ROLE,
        "sentinel_case_ids": ["case-1", "case-2"],
        "source_round": 1,
        "source_batch_id": "training_batch_01",
        "source_block_artifact": _record(root, source),
        "input_active_skill_ids": ["base-skill", "new-skill"],
        "input_skill_library_version": "accumulated-v2",
        "input_skill_library_sha256": "accumulated-hash",
        "parent_active_skill_ids": ["base-skill"],
        "parent_skill_library_version": "parent-v1",
        "parent_skill_library_sha256": "parent-hash",
        "new_skill_increment_ids": ["new-skill"],
        "identity_baseline": False,
        "current_trajectory_artifacts": current_records,
        "current_evaluation_artifacts": current_scores,
        "parent_trajectory_artifacts": parent_records,
        "parent_evaluation_artifacts": parent_scores,
        "intervention_isolation_artifact": _record(root, isolation_path),
        "curve": {
            "report_type": "prequential_new_skill_increment_vs_exact_parent_library",
            "sentinel_id": "training_batch_02",
            "direction": COHORT_PARENT_EFFECT_DIRECTION,
            "identity_baseline": False,
            "current_library_version": "accumulated-hash",
            "parent_library_version": "parent-hash",
            "current_skill_ids": ["base-skill", "new-skill"],
            "parent_skill_ids": ["base-skill"],
            "new_skill_increment_ids": ["new-skill"],
            "partition_mapping": {
                "current": "training_batch_02",
                "parent": "cohort_parent_shadow_training_batch_02",
            },
            "pair_count": 2,
            "case_cluster_count": 2,
            "bootstrap": {
                "unit": "case_id",
                "samples": 100,
                "confidence_level": 0.95,
                "seed": 42,
            },
            "metrics": metrics,
            "cases": cases,
            "pairs": pairs,
        },
        "completed_at": "2026-09-15T00:00:00+00:00",
    }
    path = run_root / "reports/development_curve_point_02.json"
    _write_json(path, point)
    return point


def _write_identity_point(root: Path) -> dict[str, Any]:
    run_root = root / f"runs/{RUN_ID}"
    pairs, cases = _curve_pairs()
    current_records: dict[str, dict[str, str]] = {}
    current_scores: dict[str, dict[str, str]] = {}
    for pair in pairs:
        pair["parent_trajectory_id"] = pair["current_trajectory_id"]
        trajectory_id = pair["current_trajectory_id"]
        trajectory = run_root / f"trajectories/training_batch_01/{trajectory_id}.json"
        score = run_root / f"evaluations/{trajectory_id}.json"
        _write_json(trajectory, {"id": trajectory_id})
        _write_json(score, {"id": trajectory_id})
        current_records[trajectory_id] = _record(root, trajectory)
        current_scores[trajectory_id] = _record(root, score)
    point = {
        "schema_version": 3,
        "run_id": RUN_ID,
        "run_manifest_sha256": RUN_MANIFEST_SHA,
        "round": 1,
        "batch_id": "training_batch_01",
        "case_limit": None,
        "status": "prequential_no_pending_cohort_identity_complete",
        "evidence_role": EVIDENCE_ROLE,
        "sentinel_case_ids": ["case-1", "case-2"],
        "input_active_skill_ids": ["retained-skill"],
        "input_skill_library_version": "retained-v1",
        "input_skill_library_sha256": "retained-hash",
        "parent_active_skill_ids": ["retained-skill"],
        "parent_skill_library_version": "retained-v1",
        "parent_skill_library_sha256": "retained-hash",
        "new_skill_increment_ids": [],
        "identity_baseline": True,
        "current_trajectory_artifacts": current_records,
        "current_evaluation_artifacts": current_scores,
        "parent_trajectory_artifacts": {},
        "parent_evaluation_artifacts": {},
        "intervention_isolation_artifact": None,
        "curve": {
            "report_type": "prequential_current_library_identity",
            "sentinel_id": "training_batch_01",
            "direction": COHORT_PARENT_EFFECT_DIRECTION,
            "identity_baseline": True,
            "no_pending_cohort": True,
            "current_library_version": "retained-hash",
            "parent_library_version": "retained-hash",
            "current_skill_ids": ["retained-skill"],
            "parent_skill_ids": ["retained-skill"],
            "new_skill_increment_ids": [],
            "partition_mapping": {
                "current": "training_batch_01",
                "parent": "training_batch_01",
            },
            "pair_count": 2,
            "case_cluster_count": 2,
            "bootstrap": {
                "unit": "case_id",
                "samples": 100,
                "confidence_level": 0.95,
                "seed": 42,
            },
            "metrics": {name: _metric(0.0, identity=True) for name in CURVE_METRICS},
            "cases": cases,
            "pairs": pairs,
        },
        "completed_at": "2026-09-15T00:00:00+00:00",
    }
    _write_json(run_root / "reports/development_curve_point_01.json", point)
    return point


def _curve_contract(
    root: Path,
    *,
    batch_id: str,
    round_index: int,
    input_ids: list[str],
    input_hash: str,
    input_version: str,
) -> dict[str, Any]:
    return _curve_point_contract(
        root,
        RUN_ID,
        batch_id,
        round_index,
        RUN_MANIFEST_SHA,
        expected_sentinel_ids=["case-1", "case-2"],
        expected_evidence_role=EVIDENCE_ROLE,
        expected_input_ids=input_ids,
        expected_input_hash=input_hash,
        expected_input_version=input_version,
        bound_record=_record(
            root,
            root
            / f"runs/{RUN_ID}/reports/development_curve_point_{round_index:02d}.json",
        ),
    )


def _write_final_holdout(root: Path, *, selected: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    run_root = root / f"runs/{RUN_ID}"
    selected_ids = ["final-skill"] if selected else []
    selected_version = "final-v1" if selected else "bootstrap_empty"
    selected_hash = "final-hash" if selected else EMPTY_LIBRARY_HASH
    cohort_path = run_root / "reports/library_effect_disposition_08.json"
    _write_json(
        cohort_path,
        {
            "decision": "continue_training_no_pending_cohort",
            "completed_at": "2026-09-15T00:01:00+00:00",
        },
    )
    arms_path = run_root / "reports/final_training_holdout_arms_frozen.json"
    _write_json(
        arms_path,
        {
            "schema_version": 1,
            "run_id": RUN_ID,
            "run_manifest_sha256": RUN_MANIFEST_SHA,
            "round": 8,
            "batch_id": "training_batch_08",
            "case_limit": None,
            "status": "all_B8_comparison_arms_frozen_before_increment_diagnostic",
            "scope": "same_B8_accumulated_library_diagnostic",
            "claim_role": "cumulative_library_diagnostic_not_independent_confirmatory_claim",
            "arm_freeze_timing": "before_B8_increment_diagnostic",
            "library_effect_disposition_absent_at_initial_freeze": True,
            "has_new_skill_increment": False,
            "comparison_arm_names": ["current_B8", "empty_B8_shadow"],
            "current_arm": {
                "arm_name": "current_B8",
                "partition": "training_batch_08",
                "registry_version": selected_version,
                "active_skill_ids": selected_ids,
                "skill_library_sha256": selected_hash,
                "trajectory_artifacts": {},
                "evaluation_artifacts": {},
            },
            "parent_arm": None,
            "empty_arm": {
                "arm_name": "empty_B8_shadow",
                "partition": "learning_curve_shadow_training_batch_08",
                "registry_version": None,
                "active_skill_ids": [],
                "skill_library_sha256": EMPTY_LIBRARY_HASH,
                "trajectory_artifacts": {},
                "evaluation_artifacts": {},
            },
            "input_active_skill_ids": selected_ids,
            "input_skill_library_version": selected_version,
            "input_skill_library_sha256": selected_hash,
            "empty_skill_library_sha256": EMPTY_LIBRARY_HASH,
            "completed_at": "2026-09-15T00:00:00+00:00",
        },
    )
    isolation_path = run_root / "health/final_training_holdout_intervention_isolation.json"
    isolation = {
        "schema_version": 1,
        "scope": "same_B8_accumulated_library_diagnostic",
        "passed": True,
        "uses_reward_or_semantic_outcome": False,
    }
    _write_json(isolation_path, isolation)
    primary_delta = 0.1 if selected else 0.0
    metrics = {
        name: {
            "empty_library_mean": 1.0,
            "current_library_mean": 1.0 + (primary_delta if name == PRIMARY_METRIC else 0.0),
            "pair_mean_delta": primary_delta if name == PRIMARY_METRIC else 0.0,
            "pair_median_delta": primary_delta if name == PRIMARY_METRIC else 0.0,
            "case_cluster_estimate": _estimate(
                primary_delta if name == PRIMARY_METRIC else 0.0
            ),
        }
        for name in CURVE_METRICS
    }
    report_path = run_root / "reports/final_training_holdout.json"
    report = {
        "schema_version": 1,
        "run_id": RUN_ID,
        "run_manifest_sha256": RUN_MANIFEST_SHA,
        "round": 8,
        "batch_id": "training_batch_08",
        "case_limit": None,
        "status": "same_B8_selected_library_vs_empty_complete",
        "scope": "same_B8_accumulated_library_diagnostic",
        "claim_role": "cumulative_library_diagnostic_not_independent_confirmatory_claim",
        "selection_source": "current_library_without_B7_increment",
        "increment_diagnostic_decision": "continue_training_no_pending_cohort",
        "all_comparison_arms_frozen_before_increment_diagnostic": True,
        "arms_frozen_artifact": _record(root, arms_path),
        "increment_diagnostic_artifact": _record(root, cohort_path),
        "selected_arm_name": "current_B8",
        "selected_partition": "training_batch_08",
        "selected_active_skill_ids": selected_ids,
        "selected_skill_library_version": selected_version,
        "selected_skill_library_sha256": selected_hash,
        "empty_partition": "learning_curve_shadow_training_batch_08",
        "empty_skill_library_sha256": EMPTY_LIBRARY_HASH,
        "intervention_isolation_artifact": _record(root, isolation_path),
        "curve": {
            "report_type": "prequential_current_library_vs_empty_library",
            "direction": "current_library_minus_empty_library",
            "identity_baseline": not selected,
            "current_library_version": selected_hash,
            "current_skill_ids": selected_ids,
            "bootstrap": {
                "unit": "case_id",
                "samples": 100,
                "confidence_level": 0.95,
                "seed": 42,
            },
            "metrics": metrics,
        },
        "completed_at": "2026-09-15T00:02:00+00:00",
    }
    _write_json(report_path, report)
    deterministic = {
        **final_training_holdout_safeguard_disposition(
            report,
            isolation,
            gate_config=_final_safeguard(),
        ),
        "run_id": RUN_ID,
        "run_manifest_sha256": RUN_MANIFEST_SHA,
        "round": 8,
        "batch_id": "training_batch_08",
        "selected_arm_name": "current_B8",
        "selected_active_skill_ids": selected_ids,
        "selected_skill_library_version": selected_version,
        "selected_skill_library_sha256": selected_hash,
        "arms_frozen_artifact": _record(root, arms_path),
        "increment_diagnostic_artifact": _record(root, cohort_path),
        "final_training_holdout_artifact": _record(root, report_path),
        "intervention_isolation_artifact": _record(root, isolation_path),
    }
    disposition_path = run_root / "reports/final_training_holdout_disposition.json"
    _write_json(
        disposition_path,
        {**deterministic, "completed_at": "2026-09-15T00:03:00+00:00"},
    )
    completion = {
        "output_active_skill_ids": selected_ids,
        "output_skill_library_version": selected_version,
        "output_skill_library_sha256": selected_hash,
    }
    return completion, {"learning_curve": {"final_cumulative_freeze_safeguard": _final_safeguard()}}


def test_progress_classification_tracks_current_artifact_chain() -> None:
    assert classify_batch_progress(
        expected=64,
        successful=63,
        errors=0,
        scored=0,
        completion_status="absent",
    )[0] == "rollout_in_progress"
    assert classify_batch_progress(
        expected=64,
        successful=64,
        errors=0,
        scored=63,
        completion_status="absent",
    )[0] == "semantic_scoring_in_progress"
    assert classify_batch_progress(
        expected=64,
        successful=64,
        errors=0,
        scored=64,
        completion_status="absent",
    )[0] == "teacher_and_skill_transition_pending"
    assert classify_batch_progress(
        expected=64,
        successful=64,
        errors=0,
        scored=64,
        completion_status="verified",
    ) == ("complete", [])


def test_progress_counts_real_horizon_outcomes_not_retired_guard_status() -> None:
    assert "max_turns_forced_memo" in TERMINAL_COMPLETE
    assert "max_turns_forced_memo" not in HEALTHY_TERMINAL
    assert "behavior_guard_terminated" not in TERMINAL_COMPLETE
    assert "behavior_guard_terminated" not in HEALTHY_TERMINAL


def test_protocol_contract_requires_exact_parent_identity_and_benchmark_disclosure() -> None:
    experiment, batches, corpus = _protocol_objects()
    contract = _protocol_contract(experiment, batches, corpus)

    assert contract["status"] == "supported"
    assert contract["checks"]["exact_parent_or_identity_design"] is True
    assert contract["checks"]["teacher_scope_not_filtered_by_next_block_case_mix"] is True
    assert contract["checks"]["external_test_declared_benchmark_aware"] is True

    corpus["external_benchmark_policy"][
        "case_level_results_used_for_training_or_skill_selection"
    ] = True
    assert _protocol_contract(experiment, batches, corpus)["status"] == "unsupported_configuration"


def test_empty_run_report_is_current_protocol_and_does_not_open_cn30(tmp_path: Path) -> None:
    _write_project(tmp_path)

    report = build_report(tmp_path, RUN_ID)

    assert report["schema_version"] == MONITOR_SCHEMA
    assert report["protocol_status"] == "supported"
    assert report["data_boundary"]["public_cn30_read_by_this_monitor"] is False
    assert report["data_boundary"]["public_cn30_prior_aggregate_evaluation_observed"] is True
    assert report["batches"][0]["progress"] == "rollout_in_progress"


def test_current_library_identity_curve_and_disposition_are_verified(tmp_path: Path) -> None:
    _write_identity_point(tmp_path)
    curve = _curve_contract(
        tmp_path,
        batch_id="training_batch_01",
        round_index=1,
        input_ids=["retained-skill"],
        input_hash="retained-hash",
        input_version="retained-v1",
    )
    point_path = tmp_path / f"runs/{RUN_ID}/reports/development_curve_point_01.json"
    disposition_path = tmp_path / f"runs/{RUN_ID}/reports/library_effect_disposition_01.json"
    expected = {
        "schema_version": 3,
        "scope": "no_new_increment_cumulative_library_identity",
        "comparator": "exact_same_current_library",
        "direction": COHORT_PARENT_EFFECT_DIRECTION,
        "bootstrap_unit": "case_id",
        "candidate_level_effect_claim": False,
        "automatic_skill_pruning": False,
        "identity_baseline": True,
        "new_skill_increment_ids": [],
        "parent_active_skill_ids": ["retained-skill"],
        "parent_skill_library_version": "retained-v1",
        "parent_skill_library_sha256": "retained-hash",
        "interval_diagnostic": None,
        "practical_effect_classifier": None,
        "cohort_transition": "no_pending_cohort",
        "diagnostic_flags": [],
        "decision": "continue_training_no_pending_cohort",
        "action": "no_increment_to_compare_continue_to_teacher",
        "run_id": RUN_ID,
        "run_manifest_sha256": RUN_MANIFEST_SHA,
        "round": 1,
        "batch_id": "training_batch_01",
        "input_active_skill_ids": ["retained-skill"],
        "input_skill_library_version": "retained-v1",
        "input_skill_library_sha256": "retained-hash",
        "development_curve_artifact": _record(tmp_path, point_path),
        "completed_at": "2026-09-15T00:01:00+00:00",
    }
    _write_json(disposition_path, expected)

    disposition = _library_effect_disposition_contract(
        tmp_path,
        RUN_ID,
        "training_batch_01",
        1,
        RUN_MANIFEST_SHA,
        expected_input_ids=["retained-skill"],
        expected_input_hash="retained-hash",
        expected_input_version="retained-v1",
        experiment={},
        curve=curve,
    )

    assert curve["status"] == "verified"
    assert curve["identity_baseline"] is True
    assert curve["primary_metric"]["comparator"] == "exact_same_current_library"
    assert disposition["status"] == "verified"
    assert disposition["decision"] == "continue_training_no_pending_cohort"
    assert disposition["cohort_transition"] == "no_pending_cohort"


def test_exact_parent_curve_uses_only_new_increment_difference(tmp_path: Path) -> None:
    _write_exact_parent_point(tmp_path)

    curve = _curve_contract(
        tmp_path,
        batch_id="training_batch_02",
        round_index=2,
        input_ids=["base-skill", "new-skill"],
        input_hash="accumulated-hash",
        input_version="accumulated-v2",
    )

    assert curve["status"] == "verified"
    assert curve["comparator"] == "exact_parent_library"
    assert curve["parent_active_skill_ids"] == ["base-skill"]
    assert curve["new_skill_increment_ids"] == ["new-skill"]
    assert curve["primary_metric"]["mean_delta"] == 0.1


def test_exact_parent_disposition_recomputes_and_rejects_dishonest_continue(
    tmp_path: Path,
) -> None:
    _write_exact_parent_point(tmp_path, primary_delta=-0.1)
    curve = _curve_contract(
        tmp_path,
        batch_id="training_batch_02",
        round_index=2,
        input_ids=["base-skill", "new-skill"],
        input_hash="accumulated-hash",
        input_version="accumulated-v2",
    )
    path = tmp_path / f"runs/{RUN_ID}/reports/library_effect_disposition_02.json"
    _write_json(
        path,
        {
            "schema_version": 2,
            "decision": "continue_training",
            "completed_at": "2026-09-15T00:01:00+00:00",
        },
    )
    experiment = {
        "learning_curve": {"incremental_effect_diagnostic": _cohort_validation()}
    }

    disposition = _library_effect_disposition_contract(
        tmp_path,
        RUN_ID,
        "training_batch_02",
        2,
        RUN_MANIFEST_SHA,
        expected_input_ids=["base-skill", "new-skill"],
        expected_input_hash="accumulated-hash",
        expected_input_version="accumulated-v2",
        experiment=experiment,
        curve=curve,
    )

    assert disposition["status"] == "invalid"
    assert "library_effect_disposition_recompute_failed" not in disposition["issues"]
    assert "library_effect_disposition_binding_invalid" in disposition["issues"]


def test_historical_empty_shadow_and_training_halt_are_diagnostic_only(tmp_path: Path) -> None:
    run_root = tmp_path / f"runs/{RUN_ID}"
    _write_json(
        run_root / "reports/development_curve_point_01.json",
        {"schema_version": 1, "status": "prequential_fixed_shadow_complete"},
    )
    _write_json(
        run_root / "manifests/training_halted.json",
        {"schema_version": 1, "stage": "halted_on_prequential_primary_regression"},
    )
    _write_json(
        run_root / "reports/learning_checkpoint_01.json",
        {
            "schema_version": 3,
            "status": "measured_prequential_learning_checkpoint",
        },
    )

    unsupported = _unsupported_schema_artifacts(run_root)

    assert {item.get("classification") for item in unsupported} >= {
        "historical_diagnostic_not_current_evidence",
        "historical_decisive_regression_protocol",
    }
    checkpoint_issue = next(
        item
        for item in unsupported
        if item.get("path") == "reports/learning_checkpoint_01.json"
    )
    assert checkpoint_issue["required_schema"] == (
        f"schema{LEARNING_CHECKPOINT_SCHEMA}_cohort_selection"
    )


def test_nonempty_selected_library_can_pass_B8_safeguard(tmp_path: Path) -> None:
    completion, experiment = _write_final_holdout(tmp_path, selected=True)

    result = _final_training_holdout_contract(
        tmp_path,
        RUN_ID,
        RUN_MANIFEST_SHA,
        completion,
        experiment,
    )

    assert result["status"] == "verified"
    assert result["decision"] == "allow_accumulated_library_freeze_and_external"
    assert result["selected_active_skill_ids"] == ["final-skill"]


def test_empty_selected_library_cannot_fake_B8_advancement_pass(tmp_path: Path) -> None:
    completion, experiment = _write_final_holdout(tmp_path, selected=False)

    result = _final_training_holdout_contract(
        tmp_path,
        RUN_ID,
        RUN_MANIFEST_SHA,
        completion,
        experiment,
    )

    assert result["status"] == "invalid"
    assert "final_training_holdout_selected_library_curve_invalid" in result["issues"]
    assert "final_training_holdout_disposition_invalid" not in result["issues"]


def test_current_schema_constants_remain_bound() -> None:
    assert TRAJECTORY_SCHEMA == 27
    assert EVALUATION_SCHEMA == 14
    assert set(CURVE_METRICS) == set(COHORT_GATE_ENDPOINT_DIRECTIONS)
