from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import yaml

from legal_skill_guard.experiment.executor import implementation_sha256
from legal_skill_guard.schemas.experiment import ResearchTrajectory
from legal_skill_guard.utils.hashing import canonical_json_sha256, sha256_file
from scripts.audit_main_run_progress import (
    _exposed_positive_safe_counts,
    build_report,
    classify_batch_progress,
)

EVIDENCE_ROLE = "development_diagnostic_only_never_teacher_or_candidate_acceptance"


def _manifest(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({**value, "content_sha256": canonical_json_sha256(value)}),
        encoding="utf-8",
    )


def _record(root: Path, path: Path) -> dict[str, str]:
    return {"path": str(path.relative_to(root)), "sha256": sha256_file(path)}


def _project(root: Path) -> tuple[Path, str]:
    experiment_path = root / "configs/experiments/main_experiment.yaml"
    roles_path = root / "configs/models/roles.yaml"
    data_path = root / "configs/data/main_corpus.yaml"
    batch_path = root / "configs/data/main_training_batches.yaml"
    for path in (experiment_path, roles_path, data_path, batch_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    experiment = {
        "data": {"training_batches": "configs/data/main_training_batches.yaml"},
        "skill_evolution": {"initial_library": "skills/bootstrap"},
        "trajectory_sampling": {"group_size": 1, "training_group_seeds": [42]},
        "learning_curve": {
            "evidence_role": EVIDENCE_ROLE,
            "sentinel_case_ids_by_block": {"training_batch_01": ["case1"]},
        },
    }
    batch = {
        "batches": [
            {
                "batch_id": "training_batch_01",
                "prospective_validation_for": None,
                "case_ids": ["case1"],
                "persona_assignment": {"case1": "P_WD"},
            }
        ]
    }
    experiment_path.write_text(yaml.safe_dump(experiment), encoding="utf-8")
    roles_path.write_text("roles: {}\n", encoding="utf-8")
    data_path.write_text("schema_version: 1\n", encoding="utf-8")
    batch_path.write_text(yaml.safe_dump(batch), encoding="utf-8")
    bootstrap = root / "skills/bootstrap"
    bootstrap.mkdir(parents=True, exist_ok=True)
    (bootstrap / ".gitkeep").write_text("", encoding="utf-8")
    run_id = "formal_run"
    run_manifest_path = root / "runs/formal_run/manifests/run.json"
    _manifest(
        run_manifest_path,
        {
            "schema_version": 3,
            "run_id": run_id,
            "experiment_config_sha256": sha256_file(experiment_path),
            "roles_config_sha256": sha256_file(roles_path),
            "data_config_sha256": sha256_file(data_path),
            "training_batch_plan_sha256": sha256_file(batch_path),
            "initial_skill_library_path": "skills/bootstrap",
            "initial_skill_library_id": "bootstrap_empty",
            "initial_skill_library_sha256": canonical_json_sha256([]),
            "implementation_sha256": implementation_sha256(root),
            "prompt_hashes": {},
        },
    )
    trajectory = ResearchTrajectory(
        schema_version=16,
        trajectory_id="traj_test",
        group_id="training_batch_01.case1.P_WD.seed_42",
        sample_index=0,
        run_id=run_id,
        method="training_policy_sample",
        partition="training_batch_01",
        case_id="case1",
        domain="general",
        persona="P_WD",
        seed=42,
        model_id="Qwen/Test",
        model_revision="frozen",
        skill_library_version=canonical_json_sha256([]),
        skill_delivery_mode="none",
        exposed_skill_ids=[],
        skill_memory_sha256="a" * 64,
        status="memo_submitted",
        opening="测试开场",
        max_turns=24,
        steps=[],
        memo=(
            "## 案情概要\n测试。\n## 关键事实\n待核实。\n## 法律问题\n待分析。\n"
            "## 风险评估\n信息有限。\n## 下一步建议\n补充材料。\n"
            "本备忘录仅基于客户单方陈述作研究性初步分析，不替代持证律师正式意见。"
        ),
        elapsed_seconds=0.1,
        created_at=datetime.now(UTC),
    )
    trajectory_path = root / "runs/formal_run/trajectories/training_batch_01/traj_test.json"
    trajectory_path.parent.mkdir(parents=True, exist_ok=True)
    trajectory_path.write_text(
        json.dumps(trajectory.model_dump(mode="json"), ensure_ascii=False),
        encoding="utf-8",
    )
    return trajectory_path, run_id


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


def _curve_point(root: Path, trajectory_path: Path) -> Path:
    run_root = root / "runs/formal_run"
    evaluation = run_root / "evaluations/traj_test.json"
    evaluation.parent.mkdir(parents=True, exist_ok=True)
    evaluation.write_text("{}", encoding="utf-8")
    empty = canonical_json_sha256([])
    path = run_root / "reports/development_curve_point_01.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    metrics = {
        name: _metric()
        for name in (
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
    }
    pair = {
        "pair_id": "pair_test",
        "case_id": "case1",
        "persona": "P_WD",
        "seed": 42,
        "sample_index": 0,
        "empty_trajectory_id": "traj_test",
        "current_trajectory_id": "traj_test",
        "empty_library": {name: 0.0 for name in metrics},
        "current_library": {name: 0.0 for name in metrics},
        "paired_delta": {name: 0.0 for name in metrics},
    }
    curve = {
        "report_type": "prequential_current_library_vs_empty_library",
        "sentinel_id": "training_batch_01",
        "direction": "current_library_minus_empty_library",
        "identity_baseline": True,
        "current_library_version": empty,
        "empty_library_version": empty,
        "partition_mapping": {
            "current": "training_batch_01",
            "empty": "training_batch_01",
        },
        "current_skill_ids": [],
        "pair_count": 1,
        "case_cluster_count": 1,
        "bootstrap": {"unit": "case_id", "samples": 100, "confidence_level": 0.95, "seed": 42},
        "initial_infrastructure_identity": {
            "passed": True,
            "stepwise_intervention_isolation": "identity_by_construction",
        },
        "metrics": metrics,
        "cases": [{"case_id": "case1", "pair_count": 1}],
        "pairs": [pair],
    }
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "run_id": "formal_run",
                "run_manifest_sha256": sha256_file(run_root / "manifests/run.json"),
                "round": 1,
                "batch_id": "training_batch_01",
                "case_limit": None,
                "status": "prequential_fixed_shadow_complete",
                "evidence_role": EVIDENCE_ROLE,
                "sentinel_case_ids": ["case1"],
                "input_active_skill_ids": [],
                "input_skill_library_sha256": empty,
                "empty_skill_library_sha256": empty,
                "identity_baseline": True,
                "current_trajectory_artifacts": {"traj_test": _record(root, trajectory_path)},
                "current_evaluation_artifacts": {"traj_test": _record(root, evaluation)},
                "empty_trajectory_artifacts": {},
                "empty_evaluation_artifacts": {},
                "intervention_isolation_artifact": None,
                "curve": curve,
                "completed_at": "2026-09-07T00:00:00+00:00",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def _ready(root: Path, trajectory_path: Path, *, corrupt_hash: bool = False) -> Path:
    run_root = root / "runs/formal_run"
    evaluation = run_root / "evaluations/traj_test.json"
    health = run_root / "health/pre_scoring_health_training_batch_01.json"
    curve_path = _curve_point(root, trajectory_path)
    evaluation.parent.mkdir(parents=True, exist_ok=True)
    health.parent.mkdir(parents=True, exist_ok=True)
    evaluation.write_text("{}", encoding="utf-8")
    health.write_text('{"healthy": true}', encoding="utf-8")
    run_manifest = run_root / "manifests/run.json"
    matrix = [{"trajectory_id": "traj_test"}]
    trajectory_record = _record(root, trajectory_path)
    if corrupt_hash:
        trajectory_record["sha256"] = "0" * 64
    path = run_root / "manifests/training_batch_01__provisionals_ready.json"
    _manifest(
        path,
        {
            "schema_version": 4,
            "run_id": "formal_run",
            "run_manifest_sha256": sha256_file(run_manifest),
            "round": 1,
            "batch_id": "training_batch_01",
            "stage": "provisionals_ready",
            "case_limit": None,
            "trajectory_schema_version": 16,
            "evaluation_schema_version": 13,
            "judge_qualification_contract_sha256": "a" * 64,
            "input_active_skill_ids": [],
            "input_skill_library_sha256": canonical_json_sha256([]),
            "expected_matrix": matrix,
            "expected_matrix_sha256": canonical_json_sha256(matrix),
            "trajectory_artifacts": {"traj_test": trajectory_record},
            "evaluation_artifacts": {"traj_test": _record(root, evaluation)},
            "pre_scoring_health_artifact": _record(root, health),
            "development_curve_artifact": _record(root, curve_path),
            "provisional_artifacts": [],
        },
    )
    return path


def _complete(root: Path, ready_path: Path) -> Path:
    run_root = root / "runs/formal_run"
    source = run_root / "reports/candidate_source_grounding_round_01.json"
    prospective = run_root / "reports/prospective_validation_training_batch_01.json"
    learning = run_root / "reports/learning_checkpoint_01.json"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("{}", encoding="utf-8")
    prospective.write_text(
        json.dumps(
            {
                "validation_batch_id": "training_batch_01",
                "source_batch_id": None,
                "provisional_skill_ids": [],
                "accepted_skill_ids": [],
                "rejected_skill_ids": [],
            }
        ),
        encoding="utf-8",
    )
    empty = canonical_json_sha256([])
    curve_path = run_root / "reports/development_curve_point_01.json"
    learning.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "run_id": "formal_run",
                "checkpoint": 1,
                "batch_id": "training_batch_01",
                "status": "measured_prequential_learning_checkpoint",
                "accepted_from_preceding_block": [],
                "measured_input_active_skill_ids": [],
                "measured_input_skill_library_sha256": empty,
                "development_curve_artifact": _record(root, curve_path),
                "active_skill_ids": [],
                "active_skill_library_sha256": empty,
                "evidence_role": EVIDENCE_ROLE,
                "curve_identity_baseline": True,
                "completed_at": "2026-09-07T00:00:01+00:00",
            }
        ),
        encoding="utf-8",
    )
    path = run_root / "manifests/training_batch_01__complete.json"
    _manifest(
        path,
        {
            "schema_version": 4,
            "run_id": "formal_run",
            "run_manifest_sha256": sha256_file(run_root / "manifests/run.json"),
            "round": 1,
            "batch_id": "training_batch_01",
            "stage": "complete",
            "case_limit": None,
            "trajectory_schema_version": 16,
            "evaluation_schema_version": 13,
            "judge_qualification_contract_sha256": "a" * 64,
            "pre_validation_active_skill_ids": [],
            "pre_validation_skill_library_sha256": empty,
            "accepted_skill_ids": [],
            "training_input_active_skill_ids": [],
            "training_input_skill_library_sha256": empty,
            "expected_matrix_sha256": canonical_json_sha256([{"trajectory_id": "traj_test"}]),
            "provisionals_ready_manifest_sha256": sha256_file(ready_path),
            "provisional_skill_ids": [],
            "candidate_source_grounding_artifact": _record(root, source),
            "prospective_validation_artifact": _record(root, prospective),
            "development_curve_artifact": _record(root, curve_path),
            "learning_checkpoint_artifact": _record(root, learning),
            "output_active_skill_ids": [],
            "output_skill_library_version": "bootstrap_empty",
            "output_skill_library_sha256": empty,
            "completed_at": "2026-08-27T00:00:00+00:00",
        },
    )
    return path


def _curve_summary(root: Path) -> Path:
    run_root = root / "runs/formal_run"
    point_path = run_root / "reports/development_curve_point_01.json"
    point = json.loads(point_path.read_text(encoding="utf-8"))
    curve = point["curve"]
    learning = json.loads(
        (run_root / "reports/learning_checkpoint_01.json").read_text(encoding="utf-8")
    )
    value = {
        "schema_version": 1,
        "run_id": "formal_run",
        "status": "complete",
        "evidence_role": EVIDENCE_ROLE,
        "expected_points": 1,
        "completed_points": 1,
        "direction": "current_input_library_minus_empty_library",
        "points": [
            {
                "round": 1,
                "batch_id": "training_batch_01",
                "input_active_skill_ids": point["input_active_skill_ids"],
                "input_skill_library_sha256": point["input_skill_library_sha256"],
                "output_active_skill_ids": learning["active_skill_ids"],
                "output_skill_library_sha256": learning["active_skill_library_sha256"],
                "accepted_from_preceding_block": learning[
                    "accepted_from_preceding_block"
                ],
                "identity_baseline": point["identity_baseline"],
                "pair_count": curve["pair_count"],
                "case_cluster_count": curve["case_cluster_count"],
                "artifact": _record(root, point_path),
            }
        ],
        "series": {
            name: [
                {
                    "round": 1,
                    "batch_id": "training_batch_01",
                    "empty_library_mean": metric["empty_library_mean"],
                    "current_library_mean": metric["current_library_mean"],
                    "mean_delta": metric["case_cluster_estimate"]["mean_delta"],
                    "confidence_lower": metric["case_cluster_estimate"]["lower"],
                    "confidence_upper": metric["case_cluster_estimate"]["upper"],
                }
            ]
            for name, metric in curve["metrics"].items()
        },
        "updated_at": "2026-09-07T00:00:02+00:00",
    }
    path = run_root / "reports/development_learning_curve.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_progress_classification_is_process_not_quality_gate() -> None:
    assert classify_batch_progress(
        expected=64, successful=63, errors=1, checkpoint_stage=None
    ) == (
        "resumable_rollout_failure",
        ["error_trajectories_must_be_rerun", "complete_matrix_required_before_scoring"],
    )
    assert classify_batch_progress(
        expected=64, successful=64, errors=0, checkpoint_stage="provisionals_ready"
    ) == ("block_completion_pending", [])


def test_raw_current_trajectory_is_diagnostic_not_frozen(tmp_path: Path) -> None:
    _project(tmp_path)
    report = build_report(tmp_path, "formal_run")
    assert report["evidence_ownership"]["status"] == "verified"
    assert report["batches"][0]["progress"] == "rollout_complete_downstream_pending"
    assert report["paper_claim_status"] == "verified_training_in_progress_no_effect_claim"


def test_uncheckpointed_curve_is_diagnostic_only(tmp_path: Path) -> None:
    trajectory_path, _ = _project(tmp_path)
    _curve_point(tmp_path, trajectory_path)
    report = build_report(tmp_path, "formal_run")
    assert report["batches"][0]["development_curve"]["status"] == (
        "diagnostic_uncheckpointed"
    )
    assert report["paper_claim_status"] == "verified_training_in_progress_no_effect_claim"


def test_schema4_ready_checkpoint_binds_curve(tmp_path: Path) -> None:
    trajectory_path, _ = _project(tmp_path)
    _ready(tmp_path, trajectory_path)
    report = build_report(tmp_path, "formal_run")
    assert report["batches"][0]["checkpoint"]["status"] == "verified"
    assert report["batches"][0]["development_curve"]["status"] == "verified"
    assert report["batches"][0]["development_curve"]["identity_baseline"] is True
    assert report["batches"][0]["development_curve"]["core_metric_deltas"]["reward"][
        "mean_delta"
    ] == 0.0
    assert report["batches"][0]["progress"] == "block_completion_pending"


def test_curve_bytes_changed_after_ready_fail_closed(tmp_path: Path) -> None:
    trajectory_path, _ = _project(tmp_path)
    _ready(tmp_path, trajectory_path)
    point_path = tmp_path / "runs/formal_run/reports/development_curve_point_01.json"
    point = json.loads(point_path.read_text(encoding="utf-8"))
    point["curve"]["metrics"]["reward"]["case_cluster_estimate"]["mean_delta"] = 1.0
    point_path.write_text(json.dumps(point), encoding="utf-8")

    report = build_report(tmp_path, "formal_run")

    assert report["batches"][0]["progress"] == "invalid_artifact_contract"
    assert "development_curve_artifact_mismatch" in report["batches"][0]["checkpoint"][
        "issues"
    ]


def test_checkpoint_hash_drift_fails_closed(tmp_path: Path) -> None:
    trajectory_path, _ = _project(tmp_path)
    _ready(tmp_path, trajectory_path, corrupt_hash=True)
    report = build_report(tmp_path, "formal_run")
    assert report["batches"][0]["progress"] == "invalid_artifact_contract"
    assert "trajectory_artifacts_content_mismatch" in report["batches"][0][
        "checkpoint"
    ]["issues"]


def test_complete_checkpoint_rejects_transition_not_bound_by_learning_checkpoint(
    tmp_path: Path,
) -> None:
    trajectory_path, _ = _project(tmp_path)
    ready_path = _ready(tmp_path, trajectory_path)
    complete_path = _complete(tmp_path, ready_path)
    value = json.loads(complete_path.read_text(encoding="utf-8"))
    value.pop("content_sha256")
    value["accepted_skill_ids"] = ["skill_a"]
    value["output_active_skill_ids"] = ["skill_a"]
    value["output_skill_library_version"] = "library_skill_a"
    value["output_skill_library_sha256"] = "b" * 64
    _manifest(complete_path, value)

    report = build_report(tmp_path, "formal_run")

    assert report["batches"][0]["checkpoint"]["status"] == "invalid"
    assert "learning_checkpoint_binding_mismatch" in report["batches"][0]["checkpoint"][
        "issues"
    ]


def test_complete_training_and_external_claim_require_full_hash_chain(tmp_path: Path) -> None:
    trajectory_path, _ = _project(tmp_path)
    ready_path = _ready(tmp_path, trajectory_path)
    complete_path = _complete(tmp_path, ready_path)
    curve_summary_path = _curve_summary(tmp_path)
    run_root = tmp_path / "runs/formal_run"
    completion_hashes = {"training_batch_01": sha256_file(complete_path)}
    prospective_path = run_root / "reports/prospective_validation_training_batch_01.json"
    summary_path = run_root / "manifests/training_complete.json"
    _manifest(
        summary_path,
        {
            "schema_version": 4,
            "run_id": "formal_run",
            "run_manifest_sha256": sha256_file(run_root / "manifests/run.json"),
            "trajectory_schema_version": 16,
            "evaluation_schema_version": 13,
            "case_limit": None,
            "rounds_completed": 1,
            "round_completion_manifests": completion_hashes,
            "round_completion_set_sha256": canonical_json_sha256(completion_hashes),
            "accepted_skill_ids": [],
            "rejected_skill_ids": [],
            "prospective_validation_reports": {
                "training_batch_01": sha256_file(prospective_path)
            },
            "active_skill_ids": [],
            "active_skill_library_version": "bootstrap_empty",
            "active_skill_library_sha256": canonical_json_sha256([]),
            "development_learning_curve_sha256": sha256_file(curve_summary_path),
            "completed_at": "2026-08-27T00:00:01+00:00",
        },
    )
    frozen = build_report(tmp_path, "formal_run")
    assert frozen["formal_artifacts"]["training_complete_contract"]["status"] == "verified"
    assert frozen["formal_artifacts"]["development_learning_curve_contract"]["status"] == (
        "verified"
    )
    assert frozen["paper_claim_status"] == "frozen_training_complete_external_test_pending"
    external = run_root / "reports/external_test.json"
    external.write_text(
        json.dumps(
            {
                "schema_version": 6,
                "run_id": "formal_run",
                "run_manifest_sha256": sha256_file(run_root / "manifests/run.json"),
                "training_complete_sha256": sha256_file(summary_path),
            }
        ),
        encoding="utf-8",
    )
    tested = build_report(tmp_path, "formal_run")
    assert tested["paper_claim_status"] == "official_external_effect_estimate_available"


def test_skill_usage_fields_do_not_infer_missing_candidate_evidence(tmp_path: Path) -> None:
    _project(tmp_path)
    report = build_report(tmp_path, "formal_run")
    lifecycle = report["skill_lifecycle"]
    assert lifecycle["candidate_pipeline"] == {
        "teacher_proposal_source_status": "absent",
        "teacher_proposed_distinct_count": None,
        "teacher_proposed_skill_ids": None,
        "hash_bound_provisional_distinct_count": 0,
        "hash_bound_provisional_skill_ids": [],
    }
    assert lifecycle["active_skill_usage"]["active_skill_count"] == 0
    assert lifecycle["active_skill_usage"]["exposed_session_count"] == 0
    assert lifecycle["candidate_exposed_effect_usage"]["status"] == "absent"
    assert lifecycle["candidate_exposed_effect_usage"][
        "positive_safe_exposed_rate"
    ] is None


def test_positive_safe_exposure_rate_uses_only_complete_audit_outcomes() -> None:
    safe = {
        "exposed": True,
        "reward_without": 0.1,
        "reward_with": 0.2,
        "severe_risk_with": False,
        "unsupported_claim_delta": 0.0,
        "premature_final_delta": 0.0,
        "belief_as_fact_delta": 0.0,
        "repeated_question_delta": 0.0,
        "policy_fallback_delta": 0.0,
        "client_fallback_delta": 0.0,
        "memo_fallback_delta": 0.0,
        "critical_fact_recall_delta": 0.1,
    }
    regressed = {**safe, "reward_with": 0.3, "unsupported_claim_delta": 1.0}
    assert _exposed_positive_safe_counts({"outcomes": [safe, regressed]}) == (2, 1)
    assert _exposed_positive_safe_counts({}) is None
