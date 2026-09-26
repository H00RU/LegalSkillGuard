"""End-to-end main experiment matrix, evolution loop, and external evaluation."""

from __future__ import annotations

import json
import math
import statistics
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, TypeVar, cast

import yaml
from pydantic import BaseModel, ConfigDict, Field

from legal_skill_guard.agent.state_manager import reconstruct_execution_state
from legal_skill_guard.agent.stateful_policy import blocking_policy_health_violations
from legal_skill_guard.environment.dlawbench_adapter import DLawBenchAdapter
from legal_skill_guard.evaluation.qualification import (
    CLIENT_QUALIFICATION_FIXTURE_SCHEMA_VERSION,
    CLIENT_QUALIFICATION_REPORT_SCHEMA_VERSION,
    SEMANTIC_JUDGE_QUALIFICATION_REPORT_SCHEMA_VERSION,
    client_simulator_qualification_component_hashes,
    client_simulator_qualification_sha256,
    semantic_judge_qualification_data_contract_checks,
    semantic_judge_qualification_sha256,
)
from legal_skill_guard.evaluation.semantic import (
    SemanticEvaluator,
    TrajectoryEvaluation,
    policy_fallback_used,
)
from legal_skill_guard.evaluation.statistics import (
    benjamini_hochberg,
    clustered_mean_deltas,
    paired_bootstrap_interval,
    paired_sign_flip_p_value,
)
from legal_skill_guard.evolution.advantage import (
    AdvantageGroup,
    ContrastSelection,
)
from legal_skill_guard.evolution.group_evidence import (
    TrajectoryGroupEvidencePatch,
    build_group_evidence_card,
    group_evidence_fingerprint,
)
from legal_skill_guard.evolution.reward import (
    RewardParameters,
)
from legal_skill_guard.evolution.teacher import (
    EXISTING_PLAYBOOK_MAX_PATCH_OPERATIONS,
    INITIAL_PLAYBOOK_MAX_PATCH_OPERATIONS,
    PLAYBOOK_SKILL_ID,
    PlaybookModeArtifact,
    PlaybookReduceArtifact,
    SkillTeacher,
    TeacherProposal,
    TeacherProtocolError,
    _playbook_mode_output_schema,
    _playbook_patch_output_schema,
    causal_visible_state_sha256,
    materialize_playbook_proposal,
    playbook_map_input_binding_sha256,
    playbook_map_request_payload,
    playbook_reduce_input_binding_sha256,
    playbook_reduce_request_payload,
    structural_action_signature,
)
from legal_skill_guard.experiment.batch_productivity import (
    TrainingBatchProductivityThresholds,
    training_batch_productivity_review,
)
from legal_skill_guard.experiment.batches import load_training_batch_plan
from legal_skill_guard.experiment.group_attribution import (
    TrainingGroupAttributionPolicy,
    training_group_attribution_review,
)
from legal_skill_guard.experiment.intervention_isolation import (
    final_training_holdout_intervention_isolation_report,
    parent_library_intervention_isolation_report,
    skill_library_intervention_isolation_report,
    skill_memory_contract_report,
)
from legal_skill_guard.experiment.learning_curve import (
    COHORT_PARENT_EFFECT_DIRECTION,
    PREQUENTIAL_CURVE_METRICS,
    build_current_library_identity_report,
    build_parent_cohort_sentinel_report,
    build_prequential_sentinel_report,
    cohort_pareto_disposition,
)
from legal_skill_guard.experiment.runner import (
    TRAINING_BRANCH_TURNS,
    TRAINING_EXACT_PREFIX_MEMBERS,
    TRAINING_PREFIX_STREAM,
    TrajectoryRunner,
    termination_contract_check,
)
from legal_skill_guard.experiment.storage import RunStore, safe_component, trajectory_identity
from legal_skill_guard.experiment.trajectory_health import (
    blocking_policy_fallback_reasons,
    official_evaluation_health_report,
    trajectory_health_report,
)
from legal_skill_guard.inference.codex_cli_client import (
    CodexCLIClient,
    CodexInvocationError,
    strict_output_schema_issues,
)
from legal_skill_guard.inference.openai_client import (
    ChatClient,
    GenerationConfig,
    ReplayCachedChatClient,
)
from legal_skill_guard.inference.structured_openai_client import (
    StructuredModelInvocationError,
    StructuredOpenAIClient,
)
from legal_skill_guard.schemas.experiment import (
    ResearchStep,
    ResearchTrajectory,
    current_trajectory_contract_issues,
    trajectory_target_kind_provenance_issues,
)
from legal_skill_guard.schemas.skill import SkillContract
from legal_skill_guard.schemas.state import ConsultationState, StatePatch
from legal_skill_guard.skills.loader import (
    load_skill,
    load_skill_directory,
    validate_skill_static,
)
from legal_skill_guard.skills.memory import (
    policy_skill_document,
    skill_memory_capacity_issues,
)
from legal_skill_guard.skills.registry import SkillRegistry
from legal_skill_guard.utils.hashing import canonical_json_sha256, sha256_file

T = TypeVar("T")
R = TypeVar("R")


class ExecutionError(RuntimeError):
    """An experiment stage is incomplete; persisted units may be resumed safely."""


def locked_external_protocol_integrity(run_root: Path) -> dict[str, Any]:
    """Describe whether a run may enter the locked public-benchmark stage.

    A run-local protocol-amendment record is necessarily outside the immutable
    ``run.json`` binding that was created before training.  The main command has
    no mixed-protocol external-test mode, so every such run is rejected.  This
    establishes run-local protocol integrity only; because method-level CN30
    aggregates were previously observed, it does not establish an independent
    confirmatory claim.  The check deliberately uses artifact names, not their
    JSON contents: a malformed amendment record must fail closed as well.
    """

    amendment_paths: set[Path] = set()
    for directory_name in ("manifests", "reports", "protocol_amendments"):
        directory = run_root / directory_name
        if not directory.is_dir():
            continue
        for path in directory.rglob("*"):
            relative_name = str(path.relative_to(run_root)).lower()
            in_amendment_directory = "protocol_amendments" in path.parts
            named_amendment = "protocol" in relative_name and "amendment" in relative_name
            if (path.is_file() or path.is_symlink()) and (
                in_amendment_directory or named_amendment
            ):
                amendment_paths.add(path)
    relative_paths = sorted(str(path.relative_to(run_root)) for path in amendment_paths)
    return {
        "passed": not relative_paths,
        "mode": "benchmark_aware_locked_reevaluation",
        "policy": "no_run_local_protocol_amendment_after_immutable_manifest",
        "protocol_amendment_artifacts": relative_paths,
        "protocol_amendment_set_sha256": canonical_json_sha256(relative_paths),
    }


def assert_locked_external_protocol_integrity(run_root: Path) -> dict[str, Any]:
    """Fail closed before a formal external benchmark can be opened or resumed."""

    integrity = locked_external_protocol_integrity(run_root)
    if not integrity["passed"]:
        raise ExecutionError(
            "locked external benchmark reevaluation is forbidden because this run contains "
            "a protocol-amendment artifact outside its immutable run manifest; "
            "rerun all arms under one frozen protocol with a new run_id. "
            f"artifacts={integrity['protocol_amendment_artifacts']}"
        )
    return integrity


class ExecutionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PreflightReport(ExecutionModel):
    ready: bool
    checks: dict[str, Any]


class TrainingSummary(ExecutionModel):
    schema_version: Literal[6] = 6
    run_id: str
    run_manifest_sha256: str
    trajectory_schema_version: Literal[27]
    evaluation_schema_version: Literal[14]
    case_limit: int | None = None
    rounds_completed: int
    round_completion_manifests: dict[str, str]
    round_completion_set_sha256: str
    admitted_skill_ids: list[str]
    rejected_skill_ids: list[str] = Field(default_factory=list)
    skill_admission_reports: dict[str, str] = Field(default_factory=dict)
    library_maintenance_reports: dict[str, str] = Field(default_factory=dict)
    active_skill_ids: list[str]
    active_skill_library_version: str
    active_skill_library_sha256: str
    development_learning_curve_sha256: str
    final_training_holdout_arms_frozen_artifact: dict[str, str]
    final_training_holdout_artifact: dict[str, str]
    final_training_holdout_disposition_artifact: dict[str, str]
    final_training_holdout_intervention_isolation_artifact: dict[str, str]
    completed_at: str
    # RunStore manifests add this verified envelope field when read.  It is not
    # part of the content being hashed and is therefore absent during creation.
    content_sha256: str | None = None


EXTERNAL_METHODS = Literal[
    "control_no_library",
    "legal_skill_evolve",
]

PAIRED_BEHAVIOR_METRICS: tuple[str, ...] = (
    "question_turns",
    "distinct_targets",
    "answered_question_turns",
    "information_bearing_turns",
    "unique_disclosed_facts",
    "unique_disclosed_facts_per_question",
    "identified_evidence_gaps",
    "f_or_g_signal_turns",
)
OFFICIAL_METRICS: tuple[str, ...] = (
    "fact_coverage",
    "inquiry",
    "elicitation",
    "fact_resolution",
    "issue_resolution",
    "resolution",
    "fidelity",
)
SAFETY_METRICS: tuple[str, ...] = (
    "premature_final_rate",
    "unsupported_claim_rate",
    "belief_as_fact_rate",
    "repeated_question_rate",
    "critical_fact_recall",
)
OPERATIONAL_METRICS: tuple[str, ...] = (
    "policy_repair_rate",
    "policy_fallback_rate",
    "client_repair_rate",
    "client_fallback_rate",
    "memo_retry",
    "memo_guardrail_intervention",
    "memo_fallback",
)
JUDGE_DIAGNOSTIC_METRICS: tuple[str, ...] = (
    "rubric_repair_rate",
    "fact_repair_rate",
    "grounding_repair_rate",
    "rubric_normalization_rate",
    "fact_normalization_rate",
    "grounding_normalization_rate",
)

EXPECTED_ROLE_ASSIGNMENT_STATUS = "static_role_assignment_frozen_gpu_requalification_required"
DIRECT_SKILL_ADMISSION_REPORT_PREFIX = "skill_admission_round_"
DIRECT_SKILL_ADMISSION_STATUS = "group_evidence_playbook_admitted_to_working_library"
DIRECT_SKILL_ADMISSION_ROLE = "group_evidence_playbook_trust_gate"
PARENT_COHORT_CURVE_POINT_SCHEMA = 2
PARENT_COHORT_CURVE_STATUS = "prequential_parent_increment_diagnostic_complete"
CURRENT_LIBRARY_IDENTITY_CURVE_POINT_SCHEMA = 3
CURRENT_LIBRARY_IDENTITY_CURVE_STATUS = "prequential_no_pending_cohort_identity_complete"
PARENT_COHORT_SHADOW_PREFIX = "cohort_parent_shadow_"
FINAL_TRAINING_HOLDOUT_ARMS_SCHEMA = 1
FINAL_TRAINING_HOLDOUT_REPORT_SCHEMA = 1
FINAL_TRAINING_HOLDOUT_DISPOSITION_SCHEMA = 1
FINAL_TRAINING_HOLDOUT_SCOPE = "same_B8_accumulated_library_diagnostic"
TRAINING_RUN_EXTERNAL_EVIDENCE_ROLE = (
    "benchmark_aware_locked_public_benchmark_reevaluation_not_pristine_confirmatory"
)
TRAINING_RUN_EXTERNAL_PUBLICATION_ROLE = (
    "same_training_run_two_arm_mechanism_diagnostic_not_four_arm_main_table"
)
LEGACY_COHORT_REJECTION_BLOCK_STAGE = "provisional_cohort_rejected_validation_block_complete"
LEARNING_CHECKPOINT_SCHEMA = 5
DEVELOPMENT_CURVE_SUMMARY_SCHEMA = 3
DEVELOPMENT_CURVE_SUMMARY_DIRECTION = (
    "current_library_minus_exact_parent_or_same_current_library_by_point"
)
FINAL_BLOCK_TEACHER_SKIP_STATUS = "skipped_final_block_zero_candidate_budget"
PLAYBOOK_TEACHER_MANIFEST_SCHEMA = 3
PLAYBOOK_TEACHER_COMPLETE_STATUS = "complete_group_evidence_playbook_reflection"
LEGACY_REJECTED_COHORT_TEACHER_SKIP_STATUS = "skipped_rejected_cohort_validation_block"
COHORT_GATE_PRIMARY_ENDPOINT = "unique_disclosed_facts_per_question"
COHORT_GATE_ENDPOINT_DIRECTIONS: dict[str, str] = {
    "unique_disclosed_facts_per_question": "higher",
    "unique_disclosed_facts": "higher",
    "identified_evidence_gaps": "higher",
    "resolution": "higher",
    "elicitation": "higher",
    "fidelity": "higher",
    "critical_fact_recall": "higher",
    "reward": "higher",
    "question_turns": "lower",
    "premature_final_rate": "lower",
    "unsupported_claim_rate": "lower",
    "belief_as_fact_rate": "lower",
    "hidden_field_leak": "lower",
    "repeated_question_rate": "lower",
    "policy_fallback_rate": "lower",
    "client_fallback_rate": "lower",
}
COHORT_RETENTION_DECISION_RULE = "primary_benefit_practical_safety_noninferiority"
COHORT_RETENTION_PROTECTED_MARGINS: dict[str, float] = {
    "unique_disclosed_facts": 0.0,
    "critical_fact_recall": 0.05,
    "premature_final_rate": 0.05,
    "unsupported_claim_rate": 0.05,
    "belief_as_fact_rate": 0.02,
    "hidden_field_leak": 0.0,
    "repeated_question_rate": 0.05,
    "policy_fallback_rate": 0.0,
    "client_fallback_rate": 0.0,
}
COHORT_RETENTION_DIAGNOSTIC_ENDPOINTS: tuple[str, ...] = (
    "identified_evidence_gaps",
    "resolution",
    "elicitation",
    "fidelity",
    "reward",
    "question_turns",
)
FINAL_TRAINING_HOLDOUT_ADVANCEMENT_ENDPOINTS: tuple[str, ...] = (
    "unique_disclosed_facts_per_question",
)


def _playbook_teacher_evidence_created(
    manifest: Mapping[str, Any], *, round_index: int, total_rounds: int
) -> bool:
    """Validate the schema-3 playbook-teacher lifecycle and return checkpoint state.

    A non-final block creates teacher evidence even when the reducer returns NOOP:
    the complete-K-group cards and their bounded map/reduce transaction are the
    evidence.  B8 is an observation-only block and therefore creates none.  This
    deliberately does not read the retired schema-2 contrast-bank flags.
    """

    issues: list[str] = []
    final_block = round_index == total_rounds
    if manifest.get("schema_version") != PLAYBOOK_TEACHER_MANIFEST_SCHEMA:
        issues.append("schema_version")
    if manifest.get("round") != round_index:
        issues.append("round")
    if manifest.get("candidate_outcome_feedback_used") is not False:
        issues.append("candidate_outcome_feedback_used")
    if manifest.get("final_block_generates_skills") is not False:
        issues.append("final_block_generates_skills")

    cards = manifest.get("group_evidence_cards")
    packages = manifest.get("teacher_packages")
    records = manifest.get("teacher_proposal_records")
    candidates = manifest.get("candidate_files")
    if not all(isinstance(value, list) for value in (cards, packages, records, candidates)):
        issues.append("collection_types")
        cards, packages, records, candidates = [], [], [], []

    if final_block:
        if manifest.get("status") != FINAL_BLOCK_TEACHER_SKIP_STATUS:
            issues.append("status")
        if manifest.get("evidence_unit") != "none_final_observation_block":
            issues.append("evidence_unit")
        if manifest.get("teacher_update_unit") != "none_final_block":
            issues.append("teacher_update_unit")
        if manifest.get("candidate_budget") != 0:
            issues.append("candidate_budget")
        if manifest.get("teacher_calls") != 0:
            issues.append("teacher_calls")
        if manifest.get("resumed_teacher_packages") != 0:
            issues.append("resumed_teacher_packages")
        if manifest.get("candidate_count") != 0:
            issues.append("candidate_count")
        if cards or packages or records or candidates:
            issues.append("final_block_collections")
        evidence_created = False
    else:
        if manifest.get("status") != PLAYBOOK_TEACHER_COMPLETE_STATUS:
            issues.append("status")
        if manifest.get("evidence_unit") != "complete_k_group_case_card":
            issues.append("evidence_unit")
        if manifest.get("teacher_update_unit") != "one_cross_domain_playbook_exact_local_patch":
            issues.append("teacher_update_unit")
        if manifest.get("all_scoreable_cases_represented") is not True:
            issues.append("all_scoreable_cases_represented")
        observed = manifest.get("observed_group_count")
        scoreable = manifest.get("scoreable_group_count")
        excluded = manifest.get("attribution_excluded_group_ids")
        represented = manifest.get("represented_case_ids")
        if not isinstance(observed, int) or observed <= 0:
            issues.append("observed_group_count")
        if not isinstance(scoreable, int) or scoreable <= 0:
            issues.append("scoreable_group_count")
        if not isinstance(excluded, list):
            issues.append("attribution_excluded_group_ids")
            excluded = []
        if not isinstance(represented, list):
            issues.append("represented_case_ids")
            represented = []
        if isinstance(observed, int) and isinstance(scoreable, int):
            if scoreable + len(excluded) != observed:
                issues.append("attribution_partition")
            if len(cards) != scoreable or len(represented) != scoreable:
                issues.append("evidence_coverage")
        calls = manifest.get("teacher_calls")
        resumed = manifest.get("resumed_teacher_packages")
        if not isinstance(calls, int) or calls < 0:
            issues.append("teacher_calls")
        if not isinstance(resumed, int) or resumed < 0:
            issues.append("resumed_teacher_packages")
        if (
            isinstance(calls, int)
            and isinstance(resumed, int)
            and (calls + resumed != len(packages) or len(packages) != 3)
        ):
            issues.append("teacher_package_accounting")
        candidate_count = manifest.get("candidate_count")
        if not isinstance(candidate_count, int) or candidate_count < 0:
            issues.append("candidate_count")
        elif candidate_count != len(candidates):
            issues.append("candidate_file_accounting")
        evidence_created = True

    if issues:
        raise ExecutionError(
            "schema-3 playbook teacher lifecycle is invalid: " + ",".join(sorted(set(issues)))
        )
    return evidence_created


def _expected_practical_retention_gate(effect_direction: str) -> dict[str, Any]:
    return {
        "decision_rule": COHORT_RETENTION_DECISION_RULE,
        "effect_direction": effect_direction,
        "primary_endpoint": COHORT_GATE_PRIMARY_ENDPOINT,
        "primary_threshold": 0.0,
        "protected_endpoint_margins": dict(COHORT_RETENTION_PROTECTED_MARGINS),
        "diagnostic_endpoints": list(COHORT_RETENTION_DIAGNOSTIC_ENDPOINTS),
    }


def practical_retention_gate_disposition(
    curve: Mapping[str, Any], *, gate_config: Mapping[str, Any]
) -> dict[str, Any]:
    """Require positive primary benefit and predeclared practical safety bounds.

    The gate selects only a whole source-round cohort on the next unseen training
    block.  It never attributes an effect to one document.  Bootstrap intervals
    remain uncertainty diagnostics; the predeclared paired point estimates own
    the mechanical online-learning transition.
    """

    expected = _expected_practical_retention_gate(str(gate_config.get("effect_direction")))
    if dict(gate_config) != expected:
        raise ExecutionError("practical retention gate configuration drift")
    if curve.get("direction") != gate_config["effect_direction"]:
        raise ExecutionError("practical retention gate effect direction drift")
    metrics = curve.get("metrics")
    if not isinstance(metrics, Mapping) or set(metrics) != set(COHORT_GATE_ENDPOINT_DIRECTIONS):
        raise ExecutionError("practical retention gate endpoint panel is incomplete")

    primary = str(gate_config["primary_endpoint"])
    primary_threshold = float(gate_config["primary_threshold"])
    protected = {
        str(name): float(margin)
        for name, margin in gate_config["protected_endpoint_margins"].items()
    }
    diagnostics = [str(item) for item in gate_config["diagnostic_endpoints"]]
    if (
        set([primary, *protected, *diagnostics]) != set(COHORT_GATE_ENDPOINT_DIRECTIONS)
        or len([primary, *protected, *diagnostics]) != len(COHORT_GATE_ENDPOINT_DIRECTIONS)
        or any(margin < 0 for margin in protected.values())
    ):
        raise ExecutionError("practical retention endpoint roles overlap or drift")

    endpoint_dispositions: dict[str, dict[str, Any]] = {}
    oriented_means: dict[str, float] = {}
    for endpoint, direction in COHORT_GATE_ENDPOINT_DIRECTIONS.items():
        metric = metrics.get(endpoint)
        estimate = metric.get("case_cluster_estimate") if isinstance(metric, Mapping) else None
        if not isinstance(estimate, Mapping):
            raise ExecutionError(f"practical retention endpoint estimate is missing: {endpoint}")
        raw_mean = float(estimate["mean_delta"])
        if not math.isfinite(raw_mean):
            raise ExecutionError(f"practical retention endpoint estimate is non-finite: {endpoint}")
        oriented = raw_mean if direction == "higher" else -raw_mean
        oriented_means[endpoint] = 0.0 if oriented == 0 else oriented
        role = (
            "primary"
            if endpoint == primary
            else "protected"
            if endpoint in protected
            else "diagnostic"
        )
        margin = 0.0 if role == "primary" else protected[endpoint] if role == "protected" else None
        passed = (
            oriented > primary_threshold
            if role == "primary"
            else oriented >= -protected[endpoint]
            if role == "protected"
            else None
        )
        endpoint_dispositions[endpoint] = {
            "role": role,
            "direction": direction,
            "raw_mean_delta": raw_mean,
            "oriented_mean_delta": oriented_means[endpoint],
            "margin": margin,
            "passed": passed,
        }

    primary_passed = bool(endpoint_dispositions[primary]["passed"])
    protected_regressions = [
        endpoint for endpoint in protected if endpoint_dispositions[endpoint]["passed"] is False
    ]
    return {
        "decision_rule": gate_config["decision_rule"],
        "effect_direction": gate_config["effect_direction"],
        "endpoint_dispositions": endpoint_dispositions,
        "primary_endpoint": primary,
        "primary_threshold": primary_threshold,
        "primary_oriented_mean_delta": oriented_means[primary],
        "primary_passed": primary_passed,
        "protected_endpoint_margins": protected,
        "protected_regressions": protected_regressions,
        "diagnostic_endpoints": diagnostics,
        "passed": primary_passed and not protected_regressions,
        "uncertainty_alone_blocks_retention": False,
    }


def _expected_final_training_holdout_config() -> dict[str, Any]:
    return {
        "enabled": True,
        "status": "frozen_before_next_formal_run",
        "timing": "after_B8_increment_diagnostic_before_training_complete",
        "arm_freeze_timing": "before_B8_increment_diagnostic",
        "scope": FINAL_TRAINING_HOLDOUT_SCOPE,
        "claim_role": ("cumulative_library_diagnostic_not_independent_confirmatory_claim"),
        "comparator": "fixed_empty_library",
        "effect_direction": "selected_final_library_minus_empty_library",
        "endpoint_set": "primary_and_practical_safety_with_full_16_diagnostics",
        "retention_gate": _expected_practical_retention_gate("current_library_minus_empty_library"),
        "advancement": {
            "decision_rule": "primary_positive_point_estimate",
            "endpoints": list(FINAL_TRAINING_HOLDOUT_ADVANCEMENT_ENDPOINTS),
            "threshold": 0.0,
        },
        "isolation_required": True,
        "performance_nonpass_blocks_external": False,
        "isolation_failure_action": "fail_closed_on_intervention_contamination",
    }


def final_training_holdout_safeguard_disposition(
    report: Mapping[str, Any],
    isolation: Mapping[str, Any],
    *,
    gate_config: Mapping[str, Any],
) -> dict[str, Any]:
    """Report final B8 performance and fail closed only on contamination.

    B8 is a development diagnostic, not the held-out official benchmark.  Its
    performance panel is preserved in full, but it cannot prune the accumulated
    library or block the external comparison.  Intervention-isolation failure is
    different: it means the comparison contract itself is contaminated and must
    still fail closed.
    """

    expected_config = _expected_final_training_holdout_config()
    if dict(gate_config) != expected_config:
        raise ExecutionError("final training holdout safeguard configuration drift")
    if set(PREQUENTIAL_CURVE_METRICS) != set(COHORT_GATE_ENDPOINT_DIRECTIONS):
        raise ExecutionError("final training holdout endpoint panel drift")
    if report.get("scope") != FINAL_TRAINING_HOLDOUT_SCOPE:
        raise ExecutionError("final training holdout report scope drift")
    curve = report.get("curve")
    if not isinstance(curve, Mapping):
        raise ExecutionError("final training holdout report lacks curve data")
    selected_skill_ids = report.get("selected_active_skill_ids")
    if (
        not isinstance(selected_skill_ids, list)
        or not all(isinstance(item, str) and item for item in selected_skill_ids)
    ) and selected_skill_ids != []:
        raise ExecutionError("final training holdout selected skill IDs are invalid")
    identity_baseline = curve.get("identity_baseline")
    if (
        curve.get("direction") != "current_library_minus_empty_library"
        or not isinstance(identity_baseline, bool)
        or identity_baseline != (selected_skill_ids == [])
    ):
        raise ExecutionError("final training holdout effect direction drift")
    bootstrap = curve.get("bootstrap")
    if not isinstance(bootstrap, Mapping) or bootstrap.get("unit") != "case_id":
        raise ExecutionError("final training holdout requires case-cluster bootstrap")
    metrics = curve.get("metrics")
    if not isinstance(metrics, Mapping) or set(metrics) != set(COHORT_GATE_ENDPOINT_DIRECTIONS):
        raise ExecutionError("final training holdout endpoint set is incomplete")

    practical_gate = practical_retention_gate_disposition(
        curve,
        gate_config=gate_config["retention_gate"],
    )

    advancement_config = gate_config["advancement"]
    advancement_threshold = float(advancement_config["threshold"])
    advancement_means = {
        endpoint: practical_gate["endpoint_dispositions"][endpoint]["oriented_mean_delta"]
        for endpoint in FINAL_TRAINING_HOLDOUT_ADVANCEMENT_ENDPOINTS
    }
    advancement_passed = any(value > advancement_threshold for value in advancement_means.values())
    isolation_passed = isolation.get("passed") is True
    retention_passed = bool(practical_gate["passed"])
    performance_panel_passed = bool(retention_passed and advancement_passed)
    failure_reasons = [
        *(["primary_or_protected_endpoint_nonpass"] if not retention_passed else []),
        *(["no_advancement"] if retention_passed and not advancement_passed else []),
        *(["intervention_isolation_failed"] if not isolation_passed else []),
    ]
    return {
        "schema_version": FINAL_TRAINING_HOLDOUT_DISPOSITION_SCHEMA,
        "scope": FINAL_TRAINING_HOLDOUT_SCOPE,
        "claim_role": gate_config["claim_role"],
        "comparator": gate_config["comparator"],
        "effect_direction": gate_config["effect_direction"],
        "bootstrap_unit": "case_id",
        "automatic_skill_pruning": False,
        "post_outcome_tuning_allowed": False,
        "teacher_call_allowed_after_nonpass": False,
        "endpoint_set": gate_config["endpoint_set"],
        "decision_rule": gate_config["retention_gate"]["decision_rule"],
        "retention_gate": practical_gate,
        "retention_gate_passed": retention_passed,
        "advancement": {
            "decision_rule": advancement_config["decision_rule"],
            "endpoints": list(FINAL_TRAINING_HOLDOUT_ADVANCEMENT_ENDPOINTS),
            "threshold": advancement_threshold,
            "oriented_mean_deltas": advancement_means,
            "passed": advancement_passed,
        },
        "intervention_isolation_passed": isolation_passed,
        "failure_reasons": failure_reasons,
        "performance_panel_passed": performance_panel_passed,
        "performance_nonpass_blocks_external": False,
        "training_freeze_allowed": isolation_passed,
        "external_test_allowed": isolation_passed,
        "decision": (
            "allow_accumulated_library_freeze_and_external"
            if isolation_passed
            else "fail_closed_intervention_isolation"
        ),
        "action": (
            "freeze_accumulated_library_with_performance_diagnostic"
            if isolation_passed
            else gate_config["isolation_failure_action"]
        ),
    }


def _role_assignment_status_check(roles: dict[str, Any]) -> dict[str, Any]:
    value = roles.get("status")
    return {
        "value": value,
        "passed": value == EXPECTED_ROLE_ASSIGNMENT_STATUS,
    }


def skill_contract_definition_sha256(skill: SkillContract) -> str:
    """Hash immutable behavior fields while allowing audited status metadata to change."""

    return canonical_json_sha256(skill.model_dump(mode="json", exclude={"status", "evaluation"}))


def _teacher_proposal_matches_candidate(
    proposal: TeacherProposal,
    candidate: SkillContract,
) -> bool:
    """Bind a stored candidate to the one valid proposal that authored it.

    Skill identifiers and evidence-cluster labels are teacher-visible strings and
    are therefore not unique identities.  The system-owned response hash, bound
    provenance and immutable document definition are.  Invalid/rejected sibling
    proposals must never make an otherwise valid candidate look ambiguous.
    """

    proposed = proposal.usable_candidate
    witness = proposal.source_witness
    group_witness = proposal.group_evidence_witness
    if proposed is None or (witness is None and group_witness is None):
        return False
    provenance = proposed.provenance
    candidate_provenance = candidate.provenance
    return bool(
        provenance.diagnosis_hash
        and provenance.diagnosis_hash == proposal.response_sha256
        and provenance.generator_model == proposal.teacher_model
        and (
            (
                witness is not None
                and witness.evidence_cluster_id == provenance.source_evidence_cluster_id
                and witness.signal_family == provenance.source_signal_family
            )
            or (
                group_witness is not None
                and group_witness.package_id == provenance.source_evidence_cluster_id
                and proposal.group_id == f"{group_witness.package_id}::playbook"
                and provenance.source_signal_family == "fact_elicitation"
            )
        )
        and candidate_provenance.diagnosis_hash == proposal.response_sha256
        and candidate_provenance.source_evidence_cluster_id == provenance.source_evidence_cluster_id
        and candidate_provenance.source_signal_family == provenance.source_signal_family
        and skill_contract_definition_sha256(proposed)
        == skill_contract_definition_sha256(candidate)
    )


def skill_document_semantic_sha256(skill: SkillContract) -> str:
    """Hash the learned prompt document independently of naming and provenance.

    Teacher calls in one round are independent and may rename the same proposed
    guidance.  Treating those aliases as separate next-block treatments wastes a
    K arm and makes the apparent candidate count depend on wording rather than on
    distinct interventions.  Scope and objective remain in the hash; lifecycle,
    identity, and evidence bookkeeping do not.
    """

    return canonical_json_sha256(
        skill.model_dump(
            mode="json",
            exclude={
                "skill_id",
                "name",
                "version",
                "status",
                "provenance",
                "evaluation",
            },
        )
    )


def _step_response_kind(step: ResearchStep) -> str | None:
    """Read protocol-12 provenance, conservatively interpreting legacy artifacts."""

    response_kind = getattr(step, "client_response_kind", None)
    if response_kind:
        return str(response_kind)
    selected = [str(item) for item in getattr(step, "client_selected_fact_ids", [])]
    if any(item.startswith("F") for item in selected):
        return "new_hidden_fact"
    if any(item.startswith("O") for item in selected):
        return "opening_repeat"
    if getattr(step, "client_response", None):
        return (
            "contract_fallback" if getattr(step, "client_safe_fallback", False) else "unavailable"
        )
    return None


def _new_hidden_fact_ids(step: ResearchStep) -> set[str]:
    if _step_response_kind(step) != "new_hidden_fact":
        return set()
    return {
        str(item)
        for item in getattr(step, "client_selected_fact_ids", [])
        if str(item).startswith("F")
    }


def trajectory_behavior_values(
    trajectory: ResearchTrajectory, active_skill_ids: set[str]
) -> dict[str, float]:
    """Return per-session behavior values suitable for paired case inference."""

    question_steps = [step for step in trajectory.steps if step.rendered_question]
    disclosed_fact_ids: set[str] = set()
    identified_evidence_gap_ids: set[str] = set()
    new_information_turns = 0
    f_or_g_signal_turns = 0
    for step in question_steps:
        selected = _new_hidden_fact_ids(step)
        identified_gaps = _identified_evidence_gap_ids(step)
        if selected - disclosed_fact_ids:
            new_information_turns += 1
        if selected or identified_gaps:
            f_or_g_signal_turns += 1
        disclosed_fact_ids.update(selected)
        identified_evidence_gap_ids.update(identified_gaps)
    # Exposure is executor-owned prompt provenance.  The current Ours policy
    # receives its complete global playbook on every turn and has no runtime
    # trigger/selection action.  Consequently ``activated_skill_ids`` is retired
    # self-report metadata and must not be presented as a treatment mechanism.
    session_skills = set(getattr(trajectory, "exposed_skill_ids", [])) & active_skill_ids
    question_turns = len(question_steps)
    return {
        "question_turns": float(question_turns),
        "distinct_targets": float(
            len(
                {
                    step.action_decision.final.target_id
                    for step in question_steps
                    if step.action_decision.final.target_id
                }
            )
        ),
        "answered_question_turns": float(
            sum(
                _step_response_kind(step)
                in {"new_hidden_fact", "repeated_hidden_fact", "opening_repeat"}
                for step in question_steps
            )
        ),
        "information_bearing_turns": float(new_information_turns),
        "unique_disclosed_facts": float(len(disclosed_fact_ids)),
        "unique_disclosed_facts_per_question": (
            float(len(disclosed_fact_ids)) / question_turns if question_turns else 0.0
        ),
        "identified_evidence_gaps": float(len(identified_evidence_gap_ids)),
        "f_or_g_signal_turns": float(f_or_g_signal_turns),
        "prompt_memory_exposed": float(bool(session_skills)),
        "exposed_skill_document_count": float(len(session_skills)),
    }


def trajectory_behavior_summary(
    trajectories: list[ResearchTrajectory], active_skill_ids: set[str]
) -> dict[str, Any]:
    """Summarize observable behavior and controlled skill-memory exposure."""

    question_counts: list[int] = []
    distinct_target_counts: list[int] = []
    answered_turn_counts: list[int] = []
    new_information_turn_counts: list[int] = []
    unique_disclosed_fact_counts: list[int] = []
    unique_disclosed_fact_efficiencies: list[float] = []
    identified_evidence_gap_counts: list[int] = []
    f_or_g_signal_turn_counts: list[int] = []
    exposed_sessions = 0
    exposed_cases: set[str] = set()
    exposed_domains: set[str] = set()
    exposure_counts: Counter[str] = Counter()
    for trajectory in trajectories:
        values = trajectory_behavior_values(trajectory, active_skill_ids)
        question_counts.append(int(values["question_turns"]))
        distinct_target_counts.append(int(values["distinct_targets"]))
        answered_turn_counts.append(int(values["answered_question_turns"]))
        new_information_turn_counts.append(int(values["information_bearing_turns"]))
        unique_disclosed_fact_counts.append(int(values["unique_disclosed_facts"]))
        unique_disclosed_fact_efficiencies.append(
            float(values["unique_disclosed_facts_per_question"])
        )
        identified_evidence_gap_counts.append(int(values["identified_evidence_gaps"]))
        f_or_g_signal_turn_counts.append(int(values["f_or_g_signal_turns"]))
        session_skills = set(getattr(trajectory, "exposed_skill_ids", [])) & active_skill_ids
        if session_skills:
            exposed_sessions += 1
            exposed_cases.add(trajectory.case_id)
            exposed_domains.add(trajectory.domain)
            exposure_counts.update(session_skills)
    total_questions = sum(question_counts)
    total_answered_turns = sum(answered_turn_counts)
    total_new_information_turns = sum(new_information_turn_counts)
    sessions = len(trajectories)
    return {
        "mean_question_turns": round(statistics.fmean(question_counts), 6)
        if question_counts
        else 0.0,
        "mean_distinct_targets": round(statistics.fmean(distinct_target_counts), 6)
        if distinct_target_counts
        else 0.0,
        "mean_answered_question_turns": round(statistics.fmean(answered_turn_counts), 6)
        if answered_turn_counts
        else 0.0,
        "answered_question_rate": round(total_answered_turns / total_questions, 6)
        if total_questions
        else 0.0,
        "mean_information_bearing_turns": round(statistics.fmean(new_information_turn_counts), 6)
        if new_information_turn_counts
        else 0.0,
        "information_bearing_question_rate": round(total_new_information_turns / total_questions, 6)
        if total_questions
        else 0.0,
        "mean_unique_disclosed_facts": round(statistics.fmean(unique_disclosed_fact_counts), 6)
        if unique_disclosed_fact_counts
        else 0.0,
        "mean_unique_disclosed_facts_per_question": round(
            statistics.fmean(unique_disclosed_fact_efficiencies), 6
        )
        if unique_disclosed_fact_efficiencies
        else 0.0,
        "pooled_unique_disclosed_facts_per_question": round(
            sum(unique_disclosed_fact_counts) / total_questions, 6
        )
        if total_questions
        else 0.0,
        "mean_identified_evidence_gaps": round(statistics.fmean(identified_evidence_gap_counts), 6)
        if identified_evidence_gap_counts
        else 0.0,
        "mean_f_or_g_signal_turns": round(statistics.fmean(f_or_g_signal_turn_counts), 6)
        if f_or_g_signal_turn_counts
        else 0.0,
        "prompt_memory_exposure_semantics": (
            "executor_recorded_full_document_delivery_not_model_self_report"
        ),
        "sessions_with_prompt_memory_exposure": exposed_sessions,
        "prompt_memory_exposure_session_rate": round(exposed_sessions / sessions, 6)
        if sessions
        else 0.0,
        "prompt_memory_exposed_cases": len(exposed_cases),
        "prompt_memory_exposed_domains": len(exposed_domains),
        "prompt_memory_exposure_counts": dict(sorted(exposure_counts.items())),
    }


def paired_behavior_estimates(
    control: list[ResearchTrajectory],
    treatment: list[ResearchTrajectory],
    active_skill_ids: set[str],
    *,
    bootstrap_samples: int,
    confidence_level: float,
    seed: int,
) -> dict[str, Any]:
    """Estimate observable behavior changes on paired case-clustered sessions."""

    if len(control) != len(treatment):
        raise ValueError("paired behavior matrix has unequal arm sizes")
    estimates: dict[str, Any] = {}
    for metric_name in PAIRED_BEHAVIOR_METRICS:
        before_values = [trajectory_behavior_values(item, set())[metric_name] for item in control]
        after_values = [
            trajectory_behavior_values(item, active_skill_ids)[metric_name] for item in treatment
        ]
        deltas = clustered_mean_deltas(
            [item.case_id for item in control], before_values, after_values
        )
        estimates[metric_name] = paired_bootstrap_interval(
            deltas,
            samples=bootstrap_samples,
            confidence_level=confidence_level,
            seed=seed,
        ).model_dump(mode="json")
    return {
        "direction": "legal_skill_evolve_minus_control_no_library",
        "cluster_unit": "case_id",
        "metrics": estimates,
        "interpretation": (
            "Question-turn growth alone is not evidence of improvement. New information, "
            "unique disclosed facts (F), identified external evidence gaps (G), "
            "inquiry/resolution, repetition and controlled skill exposure must move coherently."
        ),
    }


def _load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected YAML object: {path}")
    return value


def _validate_persona_seed_protocol(
    experiment: dict[str, Any],
    *,
    available_personas: tuple[str, ...],
    external_case_ids: tuple[str, ...] | None,
) -> None:
    """Fail closed if primary and secondary sampling roles are conflated."""

    personas = [str(item) for item in experiment.get("personas") or []]
    if personas != ["P_WD", "P_WS", "P_CS", "P_CD"]:
        raise ValueError("main experiment must retain the frozen four-persona order")
    if tuple(personas) != available_personas:
        raise ValueError("configured personas do not equal the pinned DLawBench personas")

    sampling = experiment.get("trajectory_sampling") or {}
    group_size = int(sampling.get("group_size", 0))
    if group_size != 4:
        raise ValueError("training must use four policy rollouts per case (K=4)")
    expected_branching = {
        "status": "frozen_before_next_formal_run",
        "exact_prefix_members": list(TRAINING_EXACT_PREFIX_MEMBERS),
        "prefix_stream": TRAINING_PREFIX_STREAM,
        "branch_turns": list(TRAINING_BRANCH_TURNS),
        "assignment": "fixed_first_turn_independent_streams",
    }
    if sampling.get("training_exact_prefix_branching") != expected_branching:
        raise ValueError("training exact-prefix branch schedule differs from protocol")
    if bool(sampling.get("shuffle_equal_criticality_fact_presentation", False)):
        raise ValueError("training fact presentation shuffling must remain disabled")
    if [int(item) for item in sampling.get("training_group_seeds") or []] != [42]:
        raise ValueError("training K4 dialogue seed must remain 42")
    if [int(item) for item in sampling.get("external_evaluation_seeds") or []] != [42]:
        raise ValueError("primary external evaluation must use only dialogue seed 42")
    if int(experiment.get("statistical_seed", -1)) != 42:
        raise ValueError("statistical resampling seed must remain explicitly frozen at 42")
    if (experiment.get("evaluation") or {}).get("aggregate") != "paired_case_persona_mean":
        raise ValueError("primary aggregation must not treat dialogue seeds as sample units")
    evaluation = experiment.get("evaluation") or {}
    declared_metric_contract = {
        "official_metrics": OFFICIAL_METRICS,
        "behavior_metrics": PAIRED_BEHAVIOR_METRICS,
        "safety_metrics": SAFETY_METRICS,
        "operational_metrics": OPERATIONAL_METRICS,
        "judge_diagnostics": JUDGE_DIAGNOSTIC_METRICS,
    }
    for field_name, expected in declared_metric_contract.items():
        if tuple(str(item) for item in evaluation.get(field_name) or []) != expected:
            raise ValueError(
                f"evaluation {field_name} differs from the implemented reporting contract"
            )
    if evaluation.get("primary_endpoint") != "unique_disclosed_facts_per_question":
        raise ValueError("main endpoint must remain the deterministic fact-efficiency ratio")
    required_companions = {
        "unique_disclosed_facts",
        "fact_coverage",
        "resolution",
    }
    if not required_companions <= set(evaluation.get("secondary_endpoints") or []):
        raise ValueError(
            "fact-efficiency primary endpoint requires completeness/resolution companions"
        )
    if evaluation.get("multiplicity") != "benjamini_hochberg_secondary":
        raise ValueError("secondary endpoints must retain Benjamini-Hochberg correction")
    if evaluation.get("report_effect_size") is not True:
        raise ValueError("paired effect sizes must remain enabled")
    if evaluation.get("report_paired_95ci") is not True:
        raise ValueError("paired 95% intervals must remain enabled")

    execution = experiment.get("execution") or {}
    admission = experiment.get("skill_admission") or {}
    learnable_objectives = formal_learnable_skill_objectives(experiment)
    new_skill_budget = int(execution.get("maximum_new_skills_per_block", 0))
    teacher_call_budget = int(execution.get("teacher_call_budget_per_round", 0))
    if admission.get("mode") != "group_evidence_global_playbook_evolution":
        raise ValueError("skill admission must use complete-group global-playbook evolution")
    if admission.get("per_candidate_outcome_gate") is not False:
        raise ValueError("the main run must not reintroduce per-candidate outcome gates")
    if new_skill_budget != 1 or teacher_call_budget != 3:
        raise ValueError(
            "each source block must use two map calls and one reduce call for one playbook update"
        )
    if int(admission.get("maintenance_interval_blocks", 0)) != 2:
        raise ValueError("library maintenance must be reported every two blocks")
    if tuple(str(item) for item in admission.get("allowed_objectives") or []) != (
        learnable_objectives
    ):
        raise ValueError("skill admission objective boundary differs from skill evolution")

    sensitivity = experiment.get("seed_sensitivity") or {}
    if sensitivity.get("status") != "secondary_after_primary_external_test":
        raise ValueError("seed sensitivity must remain downstream of the primary test")
    if bool(sensitivity.get("affects_candidate_selection")) or bool(
        sensitivity.get("affects_primary_inference")
    ):
        raise ValueError("secondary dialogue seeds cannot affect selection or primary inference")
    if int(sensitivity.get("primary_seed_reused", -1)) != 42:
        raise ValueError("seed sensitivity must reuse primary dialogue seed 42")
    if [int(item) for item in sensitivity.get("additional_dialogue_seeds") or []] != [43, 44]:
        raise ValueError("secondary dialogue seeds must remain frozen at 43 and 44")
    if [str(item) for item in sensitivity.get("personas") or []] != personas:
        raise ValueError("seed sensitivity must use the same four-persona stress matrix")
    sensitivity_cases = [str(item) for item in sensitivity.get("external_case_ids") or []]
    if len(sensitivity_cases) != len(set(sensitivity_cases)) or len(sensitivity_cases) != 6:
        raise ValueError("seed sensitivity must use six unique predeclared external cases")
    if external_case_ids is not None:
        unknown_cases = sorted(set(sensitivity_cases) - set(external_case_ids))
        if unknown_cases:
            raise ValueError(f"seed sensitivity references unknown external cases: {unknown_cases}")


def _atomic_yaml(path: Path, skill: SkillContract) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        yaml.safe_dump(
            skill.model_dump(mode="json", exclude_none=True),
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    temporary.replace(path)


def _stage_unique_teacher_candidate(
    candidate: SkillContract,
    *,
    candidate_root: Path,
    round_candidate_documents: dict[str, str],
    round_document_owners: dict[str, str],
) -> tuple[Path | None, SkillContract | None, str, str | None, list[str]]:
    """Stage one teacher document without turning predictable naming noise into a crash.

    A byte-identical definition at the same path is an interrupted-write replay and
    remains idempotent.  Reusing one identifier for different bytes is instead an
    invalid proposal: preserve the original artifact, record the conflict, and let
    the other independent proposals in the block continue.
    """

    document_hash = skill_document_semantic_sha256(candidate)
    prior_document_for_id = round_candidate_documents.get(candidate.skill_id)
    prior_document_owner = round_document_owners.get(document_hash)
    if prior_document_for_id is not None:
        if prior_document_for_id != document_hash:
            return (
                None,
                None,
                "rejected_same_round_skill_id_conflict",
                candidate.skill_id,
                ["same_round_skill_id_reused_for_different_document"],
            )
        return (
            None,
            None,
            "deduplicated_same_round_skill_id",
            candidate.skill_id,
            [],
        )
    if prior_document_owner is not None:
        return (
            None,
            None,
            "deduplicated_same_round_document",
            prior_document_owner,
            [],
        )

    destination = candidate_root / f"{candidate.skill_id}.yaml"
    staged = candidate
    if destination.exists():
        prior = load_skill(destination)
        if skill_contract_definition_sha256(prior) != skill_contract_definition_sha256(candidate):
            return (
                None,
                None,
                "rejected_existing_skill_id_conflict",
                prior.skill_id,
                ["existing_skill_id_reused_for_different_contract"],
            )
        if prior.status != "candidate":
            staged = prior.model_copy(update={"status": "candidate"})
            _atomic_yaml(destination, staged)
    else:
        _atomic_yaml(destination, staged)
    round_candidate_documents[candidate.skill_id] = document_hash
    round_document_owners[document_hash] = candidate.skill_id
    return destination, staged, "staged_unique_candidate", None, []


def skill_library_sha256(skills: list[SkillContract]) -> str:
    return canonical_json_sha256(
        [item.model_dump(mode="json") for item in sorted(skills, key=lambda row: row.skill_id)]
    )


FORMAL_INITIAL_SKILL_LIBRARY_ID = "bootstrap_empty"
FORMAL_LEARNABLE_SKILL_OBJECTIVES = ("fact_elicitation",)
FORMAL_TERMINATION_POLICY_OWNER = "frozen_lawyer_with_prompt_skill_memory"


def formal_learnable_skill_objectives(experiment: dict[str, Any]) -> tuple[str, ...]:
    """Return the frozen objective boundary for the formal learned library.

    The formal library has one evolving global investigation playbook. Its procedure
    may cover target ordering, evidence gaps, low-yield target switching and
    information-preserving stop/continue guidance, but the frozen Qwen remains
    the sole action author.  These documents are prompt memory, not executable
    stop rules, and the ordinary safety gates remain shared across all arms.
    """

    evolution = experiment.get("skill_evolution") or {}
    configured = tuple(str(item) for item in evolution.get("learnable_objectives") or [])
    if configured != FORMAL_LEARNABLE_SKILL_OBJECTIVES:
        raise ValueError("formal learned objective must be the unified fact_elicitation playbook")
    if evolution.get("termination_policy_owner") != FORMAL_TERMINATION_POLICY_OWNER:
        raise ValueError("formal termination policy must remain frozen-Qwen prompt policy")
    return configured


def formal_skill_document_issues(
    skill: SkillContract,
    *,
    learnable_objectives: tuple[str, ...],
) -> list[str]:
    """Enforce the formal learned-document objective boundary.

    Legal, source-grounding and hidden-information safety are validated by the
    adjacent hard gates.  The unified document may describe when another target
    is low-yield or when visible high-value facts appear exhausted.  It still
    cannot execute, replace or rewrite a model action.
    """

    issues: list[str] = []
    if skill.objective not in set(learnable_objectives):
        issues.append(f"objective_outside_formal_learned_boundary:{skill.objective}")
    return sorted(set(issues))


def load_formal_initial_skill_library(
    root: Path, experiment: dict[str, Any]
) -> tuple[list[SkillContract], dict[str, str]]:
    """Resolve and enforce the formal protocol's semantically empty start library.

    The configured path is part of the experimental treatment.  Resolve it once,
    reject aliases to any other directory, parse every YAML contract (including
    inactive ones), and reject any non-housekeeping artifact.  This prevents a
    valid legacy skill from silently turning S0 into a warm-start condition.
    """

    configured = (experiment.get("skill_evolution") or {}).get("initial_library")
    if not isinstance(configured, str) or not configured.strip():
        raise ExecutionError("skill_evolution.initial_library must be a project-relative path")
    configured_path = Path(configured)
    if configured_path.is_absolute():
        raise ExecutionError("skill_evolution.initial_library must be project-relative")
    root_resolved = root.resolve()
    initial_path = (root / configured_path).resolve()
    expected_path = (root / "skills" / "bootstrap").resolve()
    if initial_path != expected_path:
        raise ExecutionError("formal protocol initial_library must resolve to skills/bootstrap")
    try:
        initial_path.relative_to(root_resolved)
    except ValueError as exc:
        raise ExecutionError("initial skill library resolves outside the project root") from exc
    if not initial_path.is_dir():
        raise ExecutionError("formal initial skill library directory is missing")

    unexpected = sorted(
        str(path.relative_to(initial_path))
        for path in initial_path.rglob("*")
        if path.is_file() and path.name != ".gitkeep"
    )
    # Parse the directory even when an unexpected YAML file is present so an
    # invalid legacy contract cannot be mistaken for an empty active subset.
    skills = load_skill_directory(initial_path, active_only=False)
    if unexpected or skills:
        detail = unexpected or sorted(item.skill_id for item in skills)
        raise ExecutionError(
            f"formal protocol requires an empty skills/bootstrap library; found={detail}"
        )
    binding = {
        "path": str(initial_path.relative_to(root_resolved)),
        "id": FORMAL_INITIAL_SKILL_LIBRARY_ID,
        "sha256": skill_library_sha256(skills),
    }
    return skills, binding


def trajectory_learning_signature(trajectory: ResearchTrajectory) -> str:
    """Hash action targets and elicitation outcomes, excluding surface paraphrases."""

    return canonical_json_sha256(
        [
            {
                "structural_action": structural_action_signature(
                    step,
                    execution_state=_execution_state_for_step(step),
                ),
                "client_response_kind": _step_response_kind(step),
                "new_hidden_fact_ids": sorted(_new_hidden_fact_ids(step)),
            }
            for step in trajectory.steps
        ]
    )


def require_distinct_learning_traces(
    group: AdvantageGroup, members: dict[str, ResearchTrajectory]
) -> AdvantageGroup:
    """Reject surface/judge noise when target choices and elicited facts match."""

    signatures = {trajectory_learning_signature(item) for item in members.values()}
    if len(signatures) >= 2:
        return group
    return group.model_copy(update={"informative": False, "skip_reason": "identical_policy_trace"})


def tf_grpo_teacher_evidence_groups(
    trajectories: list[ResearchTrajectory],
    scoreable_group_ids: set[str],
) -> dict[str, list[ResearchTrajectory]]:
    """Select same-current-library policy samples for teacher contrast mining."""

    allowed_methods = {"training_policy_sample"}
    by_group: dict[str, list[ResearchTrajectory]] = {}
    for trajectory in trajectories:
        if trajectory.group_id in scoreable_group_ids and trajectory.method in allowed_methods:
            by_group.setdefault(str(trajectory.group_id), []).append(trajectory)
    if set(by_group) != scoreable_group_ids:
        raise ExecutionError("scoreable attribution groups lack current-prompt teacher evidence")
    for group_id, members in by_group.items():
        if len(members) < 3:
            raise ExecutionError(
                "TF-GRPO requires at least three same-library policy traces: "
                f"group={group_id}; traces={len(members)}"
            )
        if len({item.skill_library_version for item in members}) != 1:
            raise ExecutionError(f"TF-GRPO teacher evidence spans prompt libraries: {group_id}")
        opening_agenda_hashes = {
            canonical_json_sha256(item.opening_inquiry_agenda.model_dump(mode="json"))
            for item in members
        }
        if len(opening_agenda_hashes) != 1:
            raise ExecutionError(
                f"TF-GRPO teacher evidence spans shared opening agendas: {group_id}"
            )
    return by_group


def prequential_input_library_feedback(
    report: Mapping[str, Any],
    *,
    primary_endpoint: str,
    case_domains: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Convert the previous working library's paired point into next-step guidance.

    This is cohort-level online training feedback, not a per-candidate acceptance
    test.  It is deterministic and outcome-lagged: the teacher receives the
    completed current K-group evidence plus exact-parent/current process pairs
    from the just-finished unseen block.  It never receives future-block or
    official-test outcomes.  The caller separately binds the evaluated document
    transition so an UPDATE can preserve, retract, or narrow an attributable
    clause instead of freely rewriting the playbook.
    """

    curve = report.get("curve")
    if not isinstance(curve, Mapping):
        raise ExecutionError("prequential feedback report lacks curve data")
    direction = str(curve.get("direction") or "")
    if direction != COHORT_PARENT_EFFECT_DIRECTION:
        raise ExecutionError("prequential feedback has an unexpected effect direction")
    metrics = curve.get("metrics")
    if not isinstance(metrics, Mapping) or primary_endpoint not in metrics:
        raise ExecutionError("prequential feedback lacks the declared primary endpoint")

    names = (
        primary_endpoint,
        "unique_disclosed_facts",
        "question_turns",
        "identified_evidence_gaps",
        "repeated_question_rate",
        "reward",
        "premature_final_rate",
        "unsupported_claim_rate",
        "belief_as_fact_rate",
        "hidden_field_leak",
        "policy_fallback_rate",
        "client_fallback_rate",
    )
    compact: dict[str, dict[str, float]] = {}
    for name in names:
        metric = metrics.get(name)
        if not isinstance(metric, Mapping):
            continue
        estimate = metric.get("case_cluster_estimate")
        if not isinstance(estimate, Mapping):
            raise ExecutionError(f"prequential metric lacks case estimate: {name}")
        compact[name] = {
            "mean_delta": float(estimate["mean_delta"]),
            "confidence_lower": float(estimate["lower"]),
            "confidence_upper": float(estimate["upper"]),
        }

    identity = bool(curve.get("identity_baseline"))
    primary_delta = compact[primary_endpoint]["mean_delta"]
    fact_delta = compact.get("unique_disclosed_facts", {}).get("mean_delta", 0.0)
    question_delta = compact.get("question_turns", {}).get("mean_delta", 0.0)
    gap_delta = compact.get("identified_evidence_gaps", {}).get("mean_delta", 0.0)
    if identity:
        status = "current_library_identity_no_new_increment"
        priority = ["fact_elicitation", "evidence_gap_identification", "safe_stop"]
        guidance = (
            "当前没有上一块新增集合；本块输入库与自身相同，identity点不提供效果方向。"
            "仅从本块合格来源对照继续寻找互补、非重复且可归因的方法。"
        )
    elif primary_delta < 0 and fact_delta < 0:
        status = "primary_endpoint_and_fact_count_regression"
        priority = ["fact_elicitation", "evidence_gap_identification", "safe_stop"]
        guidance = (
            "当前整库相对精确父库少取得事实且主指标下降；优先从来源对照归纳新的事实排序、"
            "分解或追问方法。不得因重复率下降、证据缺口或reward上升而继续强化提前转证据或停止。"
        )
    elif primary_delta < 0 and question_delta > 0:
        status = "primary_endpoint_regression_from_question_cost"
        priority = ["safe_stop", "fact_elicitation", "evidence_gap_identification"]
        guidance = (
            "当前事实效率下降且提问增加；仅在事实和证据均不损失的来源对照中优先归纳安全停止，"
            "同时保留事实获取能力。"
        )
    elif primary_delta < 0:
        status = "primary_endpoint_regression"
        priority = ["fact_elicitation", "safe_stop", "evidence_gap_identification"]
        guidance = "当前整库主指标下降；优先纠正事实获取，不把伴随指标改善当成主目标成功。"
    else:
        status = "primary_endpoint_nonnegative"
        priority = ["fact_elicitation", "evidence_gap_identification", "safe_stop"]
        guidance = "当前整库主指标未下降；继续寻找互补、非重复且来源可归因的方法。"
    domain_diagnostics: dict[str, Any] = {}
    if case_domains is not None:
        cases = curve.get("cases")
        if not isinstance(cases, list):
            raise ExecutionError("prequential feedback lacks per-case paired diagnostics")
        cases_by_domain: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        paired_process_by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
        raw_pairs = curve.get("pairs")
        if raw_pairs is not None and not isinstance(raw_pairs, list):
            raise ExecutionError("prequential feedback has malformed paired process evidence")
        for pair in raw_pairs or []:
            if not isinstance(pair, Mapping):
                raise ExecutionError("prequential feedback has a malformed pair record")
            case_id = str(pair.get("case_id") or "")
            parent_process = pair.get("parent_process")
            current_process = pair.get("current_process")
            if (
                not case_id
                or not isinstance(parent_process, Mapping)
                or not isinstance(current_process, Mapping)
            ):
                # Schema-2 historical artifacts predate process-bearing pairs.
                # They remain readable but cannot support trajectory-level update
                # attribution in a new teacher request.
                continue
            compact_current_process = {
                key: current_process.get(key)
                for key in (
                    "trajectory_id",
                    "question_count",
                    "new_fact_count",
                    "facts_per_question",
                    "undisclosed_hidden_facts_included",
                )
            }
            compact_current_process["turns_source"] = (
                "matching_trajectory_id_in_current_group_evidence_card"
            )
            paired_delta = pair.get("paired_delta") or {}
            paired_metric_names = {
                primary_endpoint,
                "unique_disclosed_facts",
                "question_turns",
                "identified_evidence_gaps",
                "repeated_question_rate",
                "premature_final_rate",
                "unsupported_claim_rate",
                "policy_fallback_rate",
                "client_fallback_rate",
            }
            paired_process_by_case[case_id].append(
                {
                    "pair_id": str(pair.get("pair_id") or ""),
                    "case_id": case_id,
                    "parent_process": dict(parent_process),
                    # The same current trajectory is already present, turn for
                    # turn, in this package's K-group card.  Reference it here
                    # rather than duplicating the transcript inside the prompt.
                    "current_process": compact_current_process,
                    "paired_delta": {
                        name: paired_delta[name]
                        for name in sorted(paired_metric_names)
                        if name in paired_delta
                    },
                }
            )
        for case in cases:
            if not isinstance(case, Mapping):
                raise ExecutionError("prequential feedback has a malformed case diagnostic")
            case_id = str(case.get("case_id") or "")
            domain = str(case_domains.get(case_id) or "")
            deltas = case.get("paired_delta_mean")
            if not case_id or not domain or not isinstance(deltas, Mapping):
                raise ExecutionError(
                    f"prequential feedback cannot attribute case to a domain: {case_id!r}"
                )
            cases_by_domain[domain].append(case)

        domain_metric_names = tuple(name for name in names if name in compact)
        for domain, domain_cases in sorted(cases_by_domain.items()):
            domain_metrics: dict[str, dict[str, float]] = {}
            for name in domain_metric_names:
                values: list[float] = []
                for case in domain_cases:
                    deltas = case["paired_delta_mean"]
                    if name not in deltas:
                        raise ExecutionError(
                            f"prequential domain feedback lacks metric {name}: {domain}"
                        )
                    values.append(float(deltas[name]))
                domain_metrics[name] = {
                    "mean_delta": round(statistics.fmean(values), 6),
                    "minimum_case_delta": round(min(values), 6),
                    "maximum_case_delta": round(max(values), 6),
                }
            primary_values = [
                float(case["paired_delta_mean"][primary_endpoint]) for case in domain_cases
            ]
            fact_values = [
                float(case["paired_delta_mean"].get("unique_disclosed_facts", 0.0))
                for case in domain_cases
            ]
            tolerance = 1.0e-9
            if identity:
                domain_status = "identity_no_prior_increment"
            elif (
                statistics.fmean(primary_values) < -tolerance
                and statistics.fmean(fact_values) < -tolerance
            ):
                domain_status = "primary_endpoint_and_fact_count_regression"
            elif statistics.fmean(primary_values) < -tolerance:
                domain_status = "primary_endpoint_regression"
            elif statistics.fmean(primary_values) > tolerance:
                domain_status = "primary_endpoint_improvement"
            else:
                domain_status = "primary_endpoint_tied"
            domain_diagnostics[domain] = {
                "case_ids": sorted(str(case["case_id"]) for case in domain_cases),
                "case_count": len(domain_cases),
                "status": domain_status,
                "primary_case_outcomes": {
                    "improved": sum(value > tolerance for value in primary_values),
                    "tied": sum(abs(value) <= tolerance for value in primary_values),
                    "regressed": sum(value < -tolerance for value in primary_values),
                },
                "metric_deltas": domain_metrics,
                "paired_process_evidence": [
                    item
                    for case in sorted(domain_cases, key=lambda item: str(item["case_id"]))
                    for item in paired_process_by_case.get(str(case["case_id"]), [])
                ],
            }

    return {
        "schema_version": 1,
        "feedback_unit": (
            "no_new_increment_current_library_identity"
            if identity
            else "accumulated_input_library_vs_exact_parent_on_unseen_next_block"
        ),
        "comparator": ("exact_same_current_library" if identity else "exact_parent_library"),
        "candidate_level_effect_claim": False,
        "identity_baseline": identity,
        "status": status,
        "primary_endpoint": primary_endpoint,
        "signal_family_priority": priority,
        "metric_deltas": compact,
        "tradeoff_observed": bool(primary_delta < 0 and gap_delta > 0),
        "teacher_guidance": guidance,
        "domain_attribution": {
            "available": case_domains is not None,
            "unit": "exact_same_case_random_stream_global_playbook_increment",
            "candidate_level_effect_claim": False,
            "single_global_playbook_exposed_per_training_case": True,
        },
        "domain_diagnostics": domain_diagnostics,
    }


def add_document_transition_feedback(
    feedback: Mapping[str, Any],
    *,
    current_skills: list[SkillContract],
    parent_skills: list[SkillContract],
    declared_increment_ids: set[str],
) -> dict[str, Any]:
    """Bind teacher feedback to the exact document transition being evaluated.

    Runtime receives one complete global playbook.  This teacher-only view exposes
    the preceding version and exact changed fields so a regression can be repaired
    instead of prompting an unconstrained rewrite.
    """

    current_by_id = {skill.skill_id: skill for skill in current_skills}
    parent_by_id = {skill.skill_id: skill for skill in parent_skills}
    if len(current_by_id) != len(current_skills) or len(parent_by_id) != len(parent_skills):
        raise ExecutionError("document transition feedback contains duplicate skill IDs")
    removed = sorted(set(parent_by_id) - set(current_by_id))
    if removed:
        raise ExecutionError(f"document transition removed parent skills: {removed}")
    changed_or_created = {
        skill_id
        for skill_id, current in current_by_id.items()
        if skill_id not in parent_by_id
        or skill_document_semantic_sha256(current)
        != skill_document_semantic_sha256(parent_by_id[skill_id])
    }
    if changed_or_created != declared_increment_ids:
        raise ExecutionError(
            "teacher document transition differs from the declared created-or-updated cohort"
        )

    transitions: dict[str, dict[str, Any]] = {}
    for skill_id in sorted(changed_or_created):
        current = current_by_id[skill_id]
        parent = parent_by_id.get(skill_id)
        current_document = policy_skill_document(current)
        parent_document = policy_skill_document(parent) if parent is not None else None
        changed_fields = {
            field: {
                "parent": parent_document.get(field) if parent_document is not None else None,
                "current": current_document.get(field),
            }
            for field in current_document
            if field not in {"skill_id", "domain", "objective"}
            and (
                parent_document is None or parent_document.get(field) != current_document.get(field)
            )
        }
        transitions[current.domain] = {
            "operation": "CREATE" if parent is None else "UPDATE",
            "skill_id": skill_id,
            "parent_version": parent.version if parent is not None else None,
            "current_version": current.version,
            "changed_fields": changed_fields,
        }
    return {
        **dict(feedback),
        "document_transition_semantics": ("exact_parent_to_current_created_or_updated_documents"),
        "document_transitions": transitions,
    }


def _execution_state_for_step(step: Any) -> ConsultationState | None:
    """Return the exact execution state; tolerate only deliberately partial test doubles."""

    try:
        return reconstruct_execution_state(
            step.state_before,
            getattr(step, "state_patch", StatePatch()),
            turn=step.turn,
            candidate_action=step.proposed_action.model_dump(mode="json"),
        )
    except (AttributeError, ValueError):
        if isinstance(step, ResearchStep):
            raise
        return None


def _learnable_action_signature(step: ResearchStep) -> tuple[Any, ...]:
    """Project an action onto behavior represented by the source-witness interface."""

    return structural_action_signature(
        step,
        execution_state=_execution_state_for_step(step),
    )


def _trajectory_elicited_fact_ids(trajectory: ResearchTrajectory) -> set[str]:
    # Current teacher evidence is current-schema-only.  Historical or malformed
    # target-kind provenance remains auditable but cannot silently enter F/G
    # contrast selection.
    if isinstance(trajectory, ResearchTrajectory) and (
        trajectory.schema_version < 15 or trajectory_target_kind_provenance_issues(trajectory)
    ):
        return set()
    return {
        fact_id
        for step in trajectory.steps
        if _step_response_kind(step) == "new_hidden_fact"
        for fact_id in _new_hidden_fact_ids(step)
    }


def _effective_step_action(step: ResearchStep) -> Any:
    final = getattr(getattr(step, "action_decision", None), "final", None)
    return final if final is not None else getattr(step, "proposed_action", None)


def _step_target_kind(step: ResearchStep) -> str:
    """Read the system-owned target type from the exact visible execution state."""

    target_id = getattr(_effective_step_action(step), "target_id", None)
    if not target_id:
        return "none"
    state = _execution_state_for_step(step)
    if state is not None:
        for fact in state.facts:
            if fact.fact_id == target_id:
                return str(fact.target_kind or "unknown")
    else:
        for fact in step.state_before.get("facts") or []:
            if isinstance(fact, dict) and str(fact.get("fact_id") or "") == target_id:
                return str(fact.get("target_kind") or "unknown")
    return "unknown"


def _identified_evidence_gap_ids(step: ResearchStep) -> set[str]:
    """Derive a first healthy evidence-gap identification without changing reward."""

    action = _effective_step_action(step)
    target_id = getattr(action, "target_id", None)
    if (
        not target_id
        or getattr(action, "action_type", None) not in {"ask", "clarify", "verify"}
        or _step_response_kind(step) != "unavailable"
        or bool(getattr(step, "client_safe_fallback", False))
        or _step_uses_policy_fallback(step)
        or _step_target_kind(step) != "evidence_or_third_party"
    ):
        return set()
    if _step_has_blocking_health(step):
        return set()
    prior_targets = {str(item) for item in (step.state_before.get("asked_targets") or [])} | {
        str(item.get("target_id"))
        for item in (step.state_before.get("interactions") or [])
        if isinstance(item, dict) and item.get("target_id")
    }
    return set() if str(target_id) in prior_targets else {str(target_id)}


def _trajectory_identified_evidence_gap_ids(
    trajectory: ResearchTrajectory,
) -> set[str]:
    return {
        target_id for step in trajectory.steps for target_id in _identified_evidence_gap_ids(step)
    }


def _step_uses_policy_fallback(step: ResearchStep) -> bool:
    return policy_fallback_used(step)


def _step_has_blocking_health(step: ResearchStep) -> bool:
    violations = [
        *getattr(step, "policy_health_violations", []),
        *getattr(step, "post_skill_health_violations", []),
    ]
    if blocking_policy_health_violations(violations):
        return True
    return any(
        not bool(getattr(result, "passed", False))
        and str(getattr(result, "severity", "error")) in {"error", "severe"}
        for result in getattr(step, "verifier_results", [])
    )


def select_trajectory_level_contrasts(
    group: AdvantageGroup,
    members: dict[str, ResearchTrajectory],
) -> list[ContrastSelection]:
    """Select outcome-superior whole trajectories as skill hypotheses.

    Source rollouts are exploratory GRPO samples, not causal treatment pairs.  A
    source contrast therefore needs a positive reward difference plus an observable
    dominance mechanism (more facts, the same nonzero fact count with fewer
    questions, more correctly identified external evidence gaps without a
    fact-count regression, or fewer questions without losing information).  Fact
    and gap eligibility compares outcome counts rather than planner identifiers:
    independently useful trajectories need not recover a superset of byte-identical
    target IDs. Every claimed fork must nevertheless share the exact causal
    pre-action state. The source evidence supports only a candidate hypothesis and
    its hard trust gate; it does not establish a standalone causal effect.
    Downstream prequential and final comparisons evaluate the accumulated working
    library rather than retroactively attributing its effect to one document.
    """

    scored = {item.trajectory_id: item for item in group.members}
    candidates: dict[str, list[tuple[tuple[float, ...], ContrastSelection]]] = {
        "fact_elicitation": [],
        "evidence_gap_identification": [],
        "safe_stop": [],
    }

    def question_count(trajectory: ResearchTrajectory) -> int:
        return sum(bool(step.rendered_question) for step in trajectory.steps)

    def same_causal_pre_state(
        positive_step: ResearchStep,
        negative_step: ResearchStep,
    ) -> bool:
        # Unit fixtures may deliberately use partial SimpleNamespace steps.  The
        # production path is always a current-schema ResearchStep and must pass
        # the exact same projection later used by the source-witness hard gate.
        if not isinstance(positive_step, ResearchStep) or not isinstance(
            negative_step, ResearchStep
        ):
            return True
        try:
            return causal_visible_state_sha256(positive_step) == causal_visible_state_sha256(
                negative_step
            )
        except (AttributeError, ValueError):
            return False

    def first_divergence(
        positive: ResearchTrajectory,
        negative: ResearchTrajectory,
    ) -> int | None:
        for positive_step, negative_step in zip(positive.steps, negative.steps, strict=False):
            if positive_step.turn != negative_step.turn:
                return None
            # Once the client-visible histories differ, a later action contrast
            # is no longer a causal fork.  Reject it before ranking or persistence
            # instead of writing a patch that the teacher silently discards.
            if not same_causal_pre_state(positive_step, negative_step):
                return None
            if _learnable_action_signature(positive_step) != _learnable_action_signature(
                negative_step
            ):
                return positive_step.turn
        return None

    for positive_id, positive in members.items():
        positive_reward = scored[positive_id].reward
        positive_facts = _trajectory_elicited_fact_ids(positive)
        positive_gaps = _trajectory_identified_evidence_gap_ids(positive)
        positive_questions = question_count(positive)
        for negative_id, negative in members.items():
            if positive_id == negative_id:
                continue
            reward_gap = positive_reward - scored[negative_id].reward
            if reward_gap <= 0:
                continue
            divergence = first_divergence(positive, negative)
            if divergence is None:
                continue
            divergence_turn = divergence
            negative_facts = _trajectory_elicited_fact_ids(negative)
            negative_gaps = _trajectory_identified_evidence_gap_ids(negative)
            negative_questions = question_count(negative)
            fact_count_gain = len(positive_facts) - len(negative_facts)
            gap_count_gain = len(positive_gaps) - len(negative_gaps)
            positive_divergence_step = next(
                (step for step in positive.steps if step.turn == divergence_turn),
                None,
            )
            negative_divergence_step = next(
                (step for step in negative.steps if step.turn == divergence_turn),
                None,
            )
            immediate_fact_gain = len(
                _new_hidden_fact_ids(positive_divergence_step)
                if positive_divergence_step is not None
                else set()
            ) - len(
                _new_hidden_fact_ids(negative_divergence_step)
                if negative_divergence_step is not None
                else set()
            )
            immediate_gap_gain = len(
                _identified_evidence_gap_ids(positive_divergence_step)
                if positive_divergence_step is not None
                else set()
            ) - len(
                _identified_evidence_gap_ids(negative_divergence_step)
                if negative_divergence_step is not None
                else set()
            )
            # Equal final fact sets do not imply a stopping contrast.  An exact-
            # state ask->ask fork that reaches the same non-empty information in
            # fewer questions is a target-ordering efficiency hypothesis.  It is
            # learnable by prompt memory as a target-ordering method. Immediate fact recovery is
            # the strongest witness; when both fork actions initially yield the
            # same outcome, require a globally clean superior continuation and
            # let the next unseen block test the weaker ordering hypothesis.
            positive_divergence_action = (
                _effective_step_action(positive_divergence_step)
                if positive_divergence_step is not None
                else None
            )
            negative_divergence_action = (
                _effective_step_action(negative_divergence_step)
                if negative_divergence_step is not None
                else None
            )
            ask_action_types = {"ask", "clarify", "verify"}
            information_preserving_target_efficiency = (
                len(positive_facts) > 0
                and positive_facts == negative_facts
                and positive_gaps == negative_gaps
                and positive_questions < negative_questions
                and getattr(positive_divergence_action, "action_type", None) in ask_action_types
                and getattr(negative_divergence_action, "action_type", None) in ask_action_types
            )
            fact_efficiency_gain = (
                len(positive_facts) > 0
                and fact_count_gain == 0
                and positive_questions < negative_questions
                and (
                    positive_facts != negative_facts
                    or immediate_fact_gain > 0
                    or information_preserving_target_efficiency
                )
            )
            positive_fq = len(positive_facts) / positive_questions if positive_questions else 0.0
            negative_fq = len(negative_facts) / negative_questions if negative_questions else 0.0
            fact_efficiency_non_degraded = positive_fq + 1.0e-12 >= negative_fq
            positive_is_globally_hard_safe = not any(
                (
                    scored[positive_id].premature_final,
                    scored[positive_id].unsupported_claim,
                    scored[positive_id].belief_as_fact,
                    scored[positive_id].repeated_question,
                    scored[positive_id].hidden_field_leak,
                    scored[positive_id].policy_fallback,
                    scored[positive_id].client_fallback,
                )
            )
            positive_step_is_healthy = bool(
                positive_divergence_step is not None
                and not getattr(positive_divergence_step, "client_safe_fallback", False)
                and not _step_uses_policy_fallback(positive_divergence_step)
                and not _step_has_blocking_health(positive_divergence_step)
            )
            negative_step_is_healthy = bool(
                negative_divergence_step is not None
                and not getattr(negative_divergence_step, "client_safe_fallback", False)
                and not _step_uses_policy_fallback(negative_divergence_step)
                and not _step_has_blocking_health(negative_divergence_step)
            )
            source_fork_is_healthy = positive_step_is_healthy and negative_step_is_healthy
            # A source witness is anchored at the first exact-state policy fork.
            # A fact/gap obtained immediately from that healthy fork is already
            # attributable to the contrasted action; a later unrelated defect
            # cannot travel backward in time and erase that observation.  By
            # contrast, delayed gains and stopping claims depend on the whole
            # continuation and therefore still require a globally clean positive
            # trajectory.  This keeps local causal evidence without laundering a
            # later unsafe continuation into a transferable method.
            immediate_fact_witness = immediate_fact_gain > 0
            immediate_gap_witness = immediate_gap_gain > 0
            common = {
                "highest_id": positive_id,
                "lowest_id": negative_id,
                "safety_failure_id": (
                    negative_id
                    if any(
                        (
                            scored[negative_id].premature_final,
                            scored[negative_id].unsupported_claim,
                            scored[negative_id].belief_as_fact,
                            scored[negative_id].repeated_question,
                            scored[negative_id].hidden_field_leak,
                            scored[negative_id].policy_fallback,
                            scored[negative_id].client_fallback,
                        )
                    )
                    else None
                ),
                "efficient_failure_id": (
                    negative_id if negative_questions > positive_questions else None
                ),
                "aligned_divergence_turn": divergence_turn,
                "positive_fact_count": len(positive_facts),
                "negative_fact_count": len(negative_facts),
                "immediate_fact_gain": immediate_fact_gain,
                "fact_gain": fact_count_gain,
                "immediate_gap_gain": immediate_gap_gain,
                "gap_gain": gap_count_gain,
                "reward_gap": round(reward_gap, 6),
            }
            if (
                (fact_count_gain > 0 or fact_efficiency_gain)
                and gap_count_gain >= 0
                and fact_efficiency_non_degraded
                and (positive_is_globally_hard_safe or immediate_fact_witness)
                and source_fork_is_healthy
            ):
                selection = ContrastSelection(
                    **common,
                    selection_basis=(
                        "trajectory_level_fact_dominance"
                        if fact_count_gain > 0
                        else "trajectory_level_fact_efficiency"
                    ),
                    signal_family="fact_elicitation",
                )
                candidates["fact_elicitation"].append(
                    (
                        (
                            float(fact_count_gain),
                            float(negative_questions - positive_questions),
                            float(gap_count_gain),
                            reward_gap,
                            float(-divergence_turn),
                        ),
                        selection,
                    )
                )
            if (
                gap_count_gain > 0
                and fact_count_gain >= 0
                and fact_efficiency_non_degraded
                and (positive_is_globally_hard_safe or immediate_gap_witness)
                and source_fork_is_healthy
            ):
                selection = ContrastSelection(
                    **common,
                    selection_basis="trajectory_level_evidence_gap_dominance",
                    signal_family="evidence_gap_identification",
                )
                candidates["evidence_gap_identification"].append(
                    (
                        (
                            float(gap_count_gain),
                            float(fact_count_gain),
                            float(negative_questions - positive_questions),
                            reward_gap,
                            float(-divergence_turn),
                        ),
                        selection,
                    )
                )
            if (
                positive_facts == negative_facts
                and positive_gaps == negative_gaps
                and positive_questions < negative_questions
                and not immediate_fact_witness
                and not immediate_gap_witness
                and not information_preserving_target_efficiency
                and positive_is_globally_hard_safe
                and source_fork_is_healthy
            ):
                selection = ContrastSelection(
                    **common,
                    selection_basis="trajectory_level_information_preserving_efficiency",
                    signal_family="safe_stop",
                )
                candidates["safe_stop"].append(
                    (
                        (
                            float(negative_questions - positive_questions),
                            reward_gap,
                            float(-divergence_turn),
                        ),
                        selection,
                    )
                )
    return [
        max(candidates[family], key=lambda item: (item[0], item[1].highest_id))[1]
        for family in (
            "fact_elicitation",
            "evidence_gap_identification",
            "safe_stop",
        )
        if candidates[family]
    ]


def implementation_sha256(root: Path) -> str:
    paths = sorted(
        [*root.glob("legal_skill_guard/**/*.py"), root / "scripts/run_main_experiment.py"]
    )
    return canonical_json_sha256(
        {str(path.relative_to(root)): sha256_file(path) for path in paths if path.is_file()}
    )


def teacher_response_cache_root(store: RunStore) -> Path:
    """Return the response-cache namespace owned by exactly one formal run."""

    return store.root / "cache" / "skill_teacher"


def _structured_codex_request_sha256(
    *,
    client: CodexCLIClient,
    purpose: str,
    system_prompt: str,
    user_payload: Mapping[str, Any],
    output_schema: dict[str, Any],
) -> str:
    """Rebuild the adapter-v1 request digest used by ``CodexCLIClient``.

    Resumable teacher credit is granted only when a persisted playbook stage is
    bound to the exact prompt, logical input and Structured Output schema that
    the current teacher would submit.  Merely finding a response-cache file with
    the same model name is not sufficient.
    """

    return canonical_json_sha256(
        {
            "adapter_schema_version": 1,
            "purpose": purpose,
            "model": client.model,
            "reasoning_effort": client.reasoning_effort,
            "system_prompt": system_prompt,
            "user_prompt": json.dumps(user_payload, ensure_ascii=False, sort_keys=True),
            "output_schema": output_schema,
        }
    )


def _playbook_teacher_preflight_card() -> dict[str, Any]:
    """Return a label-free synthetic card for the live map-interface probe."""

    group_id = "preflight.playbook_map.group"
    summaries = [
        {
            "trajectory_id": f"preflight_trajectory_{index}",
            "sample_index": index,
            "final_reward": 0.0,
            "rank_vector": [0, 0, 0, 0, 0],
            "new_fact_count": 0,
            "question_count": 1,
            "facts_per_question": 0.0,
            "first_new_fact_turn": None,
            "fact_acquisition_auc": 0,
            "response_kind_counts": {"unavailable": 1},
            "safety_flags": [],
            "visible_target_catalog": [
                {
                    "target_id": "preflight_target",
                    "label": "待核实的客户事实",
                    "criticality": "medium",
                    "target_kind": "client_fact",
                }
            ],
            "turn_outline": [
                {
                    "turn": 1,
                    "action_type": "ask",
                    "target_kind": "fact",
                    "target_label": "待核实的客户事实",
                    "question": "请说明这一项您目前能够确认的事实。",
                    "response_kind": "unavailable",
                    "new_disclosed_fact_count": 0,
                    "visible_unresolved_targets_before_action": [
                        {
                            "target_id": "preflight_target",
                            "status": "unknown",
                            "asked": False,
                        }
                    ],
                }
            ],
            "group_relative_advantage": 0.0,
        }
        for index in range(4)
    ]
    return {
        "schema_version": 4,
        "group_id": group_id,
        "case_id": "preflight_synthetic_case",
        "domain": "contract_commercial",
        "persona": "P_WD",
        "opening": "我想核实一项与争议有关的事实。",
        "opening_inquiry_agenda": [
            {
                "target_id": "preflight_target",
                "label": "待核实的客户事实",
                "criticality": "medium",
                "target_kind": "client_fact",
            }
        ],
        "skill_library_version": FORMAL_INITIAL_SKILL_LIBRARY_ID,
        "group_size": 4,
        "group_relative_status": "process_tied",
        "reward_std": 0.0,
        "best_trajectory_ids": [],
        "worst_trajectory_ids": [],
        "common_failure_types": ["unavailable"],
        "trajectory_summaries": summaries,
        "representative_full_dialogues": {},
        "undisclosed_hidden_facts_included": False,
    }


def parallel_map_ordered(
    items: list[T],
    function: Callable[[T], R],
    *,
    max_workers: int,
    label: str,
    fail_fast: bool = False,
) -> list[R]:
    """Run resumable units in order; fail-fast also rejects error trajectories."""

    if max_workers < 1:
        raise ValueError(f"{label} max_workers must be positive")
    if not items:
        return []
    values: list[R | None] = [None] * len(items)
    failures: list[str] = []
    progress_interval = max(1, len(items) // 20)
    print(f"{label}_start units={len(items)} workers={max_workers}", flush=True)
    pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix=label)
    try:
        pending = {pool.submit(function, item): index for index, item in enumerate(items)}
        for completed, future in enumerate(as_completed(pending), start=1):
            index = pending[future]
            try:
                value = future.result()
                if fail_fast and isinstance(value, ResearchTrajectory) and value.status == "error":
                    raise ExecutionError(
                        f"error trajectory {value.trajectory_id}: {value.error or 'unknown error'}"
                    )
                values[index] = value
            except Exception as exc:  # every other scheduled unit remains resumable
                failures.append(f"index={index}:{type(exc).__name__}:{exc}")
                if fail_fast:
                    for outstanding in pending:
                        if outstanding is not future:
                            outstanding.cancel()
                    pool.shutdown(wait=False, cancel_futures=True)
                    raise ExecutionError(f"{label} failed fast; first={failures[0]}") from exc
            if completed % progress_interval == 0 or completed == len(items):
                print(
                    f"{label}_progress completed={completed}/{len(items)} failures={len(failures)}",
                    flush=True,
                )
    except BaseException:
        # ``ThreadPoolExecutor.__exit__`` performs ``shutdown(wait=True)``.  Under
        # Ctrl-C that previously kept every already-queued rollout alive, so a
        # rejected run silently wrote another 91 trajectories after the operator had
        # stopped it.  Cancel units that have not started; at most ``max_workers``
        # already-running resumable units are allowed to finish their atomic write.
        for future in pending:
            future.cancel()
        pool.shutdown(wait=False, cancel_futures=True)
        raise
    else:
        pool.shutdown(wait=True)
    if failures:
        raise ExecutionError(f"{label} has {len(failures)} failed units; first={failures[0]}")
    return [cast(R, value) for value in values]


def select_diverse_teacher_groups(
    groups: list[tuple[AdvantageGroup, dict[str, ResearchTrajectory]]],
    *,
    budget: int,
    maximum_per_case: int = 2,
    minimum_source_domains: int = 0,
) -> list[tuple[AdvantageGroup, dict[str, ResearchTrajectory]]]:
    """Preserve required source-domain coverage, then case diversity."""

    if budget < 0 or maximum_per_case < 1 or minimum_source_domains < 0:
        raise ValueError("teacher selection budgets must be non-negative and positive")
    if minimum_source_domains > budget:
        raise ValueError("required teacher source domains exceed the evidence budget")
    # Callers pass only groups supported by a source-evidence cluster.  Whole-
    # trajectory reward variance is not a second admission gate: the frozen memo
    # renderer can erase the end-to-end reward benefit of a locally productive
    # inquiry.  Downstream prequential and final comparisons assess the accumulated
    # working library; they do not turn this source ranking into single-skill causality.
    informative = sorted(
        groups,
        key=lambda item: (-item[0].std_reward, item[0].group_id),
    )
    selected: list[tuple[AdvantageGroup, dict[str, ResearchTrajectory]]] = []
    case_counts: Counter[str] = Counter()

    def case_id(item: tuple[AdvantageGroup, dict[str, ResearchTrajectory]]) -> str:
        return next(iter(item[1].values())).case_id

    def domain(item: tuple[AdvantageGroup, dict[str, ResearchTrajectory]]) -> str:
        return next(iter(item[1].values())).domain

    available_domains = {domain(item) for item in informative}
    if minimum_source_domains > len(available_domains):
        raise ValueError("eligible evidence truncation cannot preserve source-domain coverage")
    selected_domains: set[str] = set()
    for item in informative:
        current_domain = domain(item)
        if current_domain in selected_domains:
            continue
        selected.append(item)
        case_counts[case_id(item)] += 1
        selected_domains.add(current_domain)
        if len(selected_domains) >= minimum_source_domains:
            break

    for item in informative:
        if item in selected:
            continue
        current_case = case_id(item)
        if current_case in case_counts:
            continue
        selected.append(item)
        case_counts[current_case] += 1
        if len(selected) >= budget:
            return selected
    for item in informative:
        current_case = case_id(item)
        if item in selected or case_counts[current_case] >= maximum_per_case:
            continue
        selected.append(item)
        case_counts[current_case] += 1
        if len(selected) >= budget:
            break
    return selected


def verify_model_manifest(root: Path, role: dict[str, Any]) -> dict[str, Any]:
    """Verify one frozen snapshot against its checked-in per-file digest manifest."""

    manifest_path = root / str(role["manifest"])
    result: dict[str, Any] = {
        "passed": False,
        "manifest_path": str(manifest_path.relative_to(root)),
        "manifest_sha256": None,
        "metadata_mismatches": [],
        "missing_files": [],
        "hash_mismatches": [],
    }
    if not manifest_path.is_file():
        result["missing_files"] = [str(manifest_path.relative_to(root))]
        return result
    result["manifest_sha256"] = sha256_file(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_metadata = {
        "model_id": str(role["model_id"]),
        "revision": str(role["revision"]),
        "snapshot": str(role["local_snapshot"]),
    }
    for key, expected in expected_metadata.items():
        if manifest.get(key) != expected:
            result["metadata_mismatches"].append(
                {"field": key, "expected": expected, "actual": manifest.get(key)}
            )
    if role.get("require_upstream_hashes_verified") and not manifest.get(
        "upstream_hashes_verified"
    ):
        result["metadata_mismatches"].append(
            {"field": "upstream_hashes_verified", "expected": True, "actual": False}
        )
    snapshot = root / str(role["local_snapshot"])
    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        result["metadata_mismatches"].append({"field": "files", "reason": "empty_or_invalid"})
        return result
    for name, expected in files.items():
        path = snapshot / str(name)
        if not path.is_file():
            result["missing_files"].append(str(name))
            continue
        expected_bytes = int(expected.get("bytes", -1))
        expected_sha256 = str(expected.get("sha256") or "")
        if (
            role.get("require_upstream_hashes_verified")
            and str(name).endswith(".safetensors")
            and expected.get("upstream_sha256") != expected_sha256
        ):
            result["metadata_mismatches"].append(
                {
                    "field": f"files.{name}.upstream_sha256",
                    "expected": expected_sha256,
                    "actual": expected.get("upstream_sha256"),
                }
            )
        actual_bytes = path.stat().st_size
        if actual_bytes != expected_bytes:
            result["hash_mismatches"].append(
                {
                    "file": str(name),
                    "expected_bytes": expected_bytes,
                    "actual_bytes": actual_bytes,
                    "reason": "size",
                }
            )
            continue
        actual_sha256 = sha256_file(path)
        if actual_sha256 != expected_sha256:
            result["hash_mismatches"].append(
                {
                    "file": str(name),
                    "expected_sha256": expected_sha256,
                    "actual_sha256": actual_sha256,
                    "reason": "sha256",
                }
            )
    result["passed"] = not any(
        result[key] for key in ("metadata_mismatches", "missing_files", "hash_mismatches")
    )
    return result


class MainExperimentExecutor:
    """Own all matrices so no stage silently changes cases, seeds, prompts, or models."""

    def __init__(
        self,
        root: Path,
        run_id: str,
        *,
        allow_external_data_access: bool = True,
    ) -> None:
        self.root = root
        self.run_id = run_id
        self.experiment_path = root / "configs/experiments/main_experiment.yaml"
        self.roles_path = root / "configs/models/roles.yaml"
        self.data_path = root / "configs/data/main_corpus.yaml"
        self.experiment = _load_yaml(self.experiment_path)
        self.roles = _load_yaml(self.roles_path)
        self.data_config = _load_yaml(self.data_path)
        self.store = RunStore(root / "runs", run_id)
        if (self.store.root / "SUPERSEDED.md").is_file():
            raise ExecutionError(f"run is explicitly superseded and cannot be resumed: {run_id}")
        self.registry = SkillRegistry(self.store.root / "skills" / "versions")
        self.candidate_root = self.store.root / "skills" / "candidates"
        self.personas_path = root / "third_party/DLawBench/config/personas.json"
        self.main_adapter = DLawBenchAdapter(
            root / self.experiment["data"]["training_cases"],
            self.personas_path,
            root / self.experiment["data"]["provenance"],
        )
        self.training_batch_path = root / self.experiment["data"]["training_batches"]
        self.training_plan = load_training_batch_plan(self.training_batch_path, self.main_adapter)
        self.learning_curve_sentinels = self._validate_learning_curve_configuration()
        # Baseline construction and independent ExpeL training must not parse the
        # official CN30 payload merely because they reuse the consultation runtime.
        # The default preserves the existing main-experiment interface; the
        # evaluation-only controller opts in only after its protocol is frozen.
        self.external_adapter = (
            DLawBenchAdapter(
                root / self.experiment["data"]["external_evaluation"],
                self.personas_path,
            )
            if allow_external_data_access
            else None
        )
        _validate_persona_seed_protocol(
            self.experiment,
            available_personas=self.main_adapter.persona_keys,
            external_case_ids=(
                self.external_adapter.case_ids() if self.external_adapter is not None else None
            ),
        )
        lawyer = self.roles["roles"]["lawyer_policy"]
        shared_local_fields = ("model_id", "revision", "local_snapshot", "base_url")
        for role_name in (
            "opening_inquiry_agenda",
            "client_disclosure_classifier",
            "memo_renderer",
        ):
            role = self.roles["roles"][role_name]
            mismatches = [
                field for field in shared_local_fields if role.get(field) != lawyer.get(field)
            ]
            if mismatches:
                raise ValueError(
                    f"{role_name} must share the frozen lawyer service; mismatches={mismatches}"
                )
        self.local_model = str(lawyer["model_id"])
        self.local_revision = str(lawyer["revision"])
        self.local_base_url = str(lawyer["base_url"])
        self.local_client = ChatClient(
            self.local_base_url,
            self.local_model,
            expected_model_root=root / str(lawyer["local_snapshot"]),
            expected_max_model_len=int(lawyer["runtime_limits"]["max_model_len"]),
        )
        selector_role = self.roles["roles"]["client_fact_selector"]
        if selector_role["runtime"] != "local_vllm":
            raise ValueError("client_fact_selector runtime must be local_vllm")
        self.client_selector_model = str(selector_role["model_id"])
        self.client_selector_revision = str(selector_role["revision"])
        self.client_selector_client = ChatClient(
            str(selector_role["base_url"]),
            self.client_selector_model,
            expected_model_root=root / str(selector_role["local_snapshot"]),
            expected_max_model_len=int(
                self.roles["roles"]["semantic_judge"]["runtime_limits"]["max_model_len"]
            ),
        )
        self.client_disclosure_client = self.local_client
        execution = self.experiment["execution"]
        self.training_batch_productivity_thresholds = (
            TrainingBatchProductivityThresholds.model_validate(
                self.experiment["training_batch_productivity_review"]
            )
        )
        self.training_group_attribution_policy = TrainingGroupAttributionPolicy.model_validate(
            self.experiment["training_group_attribution"]
        )
        expected_training_trajectories = (
            self.training_plan.cases_per_batch
            * len(self.experiment["trajectory_sampling"]["training_group_seeds"])
            * int(self.experiment["trajectory_sampling"]["group_size"])
        )
        if (
            self.training_batch_productivity_thresholds.expected_cases
            != self.training_plan.cases_per_batch
            or self.training_batch_productivity_thresholds.expected_trajectories
            != expected_training_trajectories
        ):
            raise ValueError("training-batch productivity policy does not match the frozen matrix")
        expected_training_groups = self.training_plan.cases_per_batch * len(
            self.experiment["trajectory_sampling"]["training_group_seeds"]
        )
        if (
            self.training_group_attribution_policy.expected_groups != expected_training_groups
            or self.training_group_attribution_policy.group_size
            != int(self.experiment["trajectory_sampling"]["group_size"])
        ):
            raise ValueError("training-group attribution policy does not match the frozen matrix")
        teacher_role = self.roles["roles"]["skill_teacher"]
        judge_role = self.roles["roles"]["semantic_judge"]
        selector_judge_shared_fields = (
            "model_id",
            "revision",
            "local_snapshot",
            "manifest",
            "base_url",
        )
        selector_judge_mismatches = [
            field
            for field in selector_judge_shared_fields
            if selector_role.get(field) != judge_role.get(field)
        ]
        if selector_judge_mismatches:
            raise ValueError(
                "client_fact_selector must share the frozen local judge service while "
                "remaining a prompt- and cache-isolated role; mismatches="
                f"{selector_judge_mismatches}"
            )
        # Teacher responses are evidence produced by one formal run and therefore
        # remain run-scoped.  Only the invocation budget ledger is project-scoped so
        # independent runs cannot evade the user's cumulative Luna hard limit.
        self.shared_experiment_root = root / "runs" / "main_experiment_shared"
        self.shared_teacher_root = self.shared_experiment_root
        self.teacher_client = CodexCLIClient(
            model=str(teacher_role["model_id"]),
            cache_root=teacher_response_cache_root(self.store),
            reasoning_effort=str(teacher_role["reasoning_effort"]),
            timeout_seconds=int(execution["codex_timeout_seconds"]),
            retries=int(execution["codex_retries"]),
            executable=str(teacher_role["executable"]),
            invocation_budget_path=(self.shared_teacher_root / "luna_invocation_budget.json"),
            max_invocations=int(execution["teacher_total_invocation_budget"]),
        )
        if judge_role["runtime"] != "local_vllm_structured":
            raise ValueError("semantic_judge runtime must be local_vllm_structured")
        self.judge_client = StructuredOpenAIClient(
            base_url=str(judge_role["base_url"]),
            model=str(judge_role["model_id"]),
            model_revision=str(judge_role["revision"]),
            cache_root=self.store.root / "cache" / "local_judge",
            reasoning_effort=str(judge_role["reasoning_effort"]),
            max_completion_tokens=int(judge_role["max_completion_tokens"]),
            timeout_seconds=int(execution["judge_timeout_seconds"]),
            retries=int(execution["judge_retries"]),
            expected_model_root=root / str(judge_role["local_snapshot"]),
            expected_max_model_len=int(judge_role["runtime_limits"]["max_model_len"]),
        )
        self.judge_repair_client = StructuredOpenAIClient(
            base_url=str(judge_role["base_url"]),
            model=str(judge_role["model_id"]),
            model_revision=str(judge_role["revision"]),
            cache_root=self.store.root / "cache" / "local_judge",
            reasoning_effort=str(judge_role["reasoning_effort"]),
            max_completion_tokens=int(judge_role["repair_max_completion_tokens"]),
            timeout_seconds=int(execution["judge_timeout_seconds"]),
            retries=int(execution["judge_retries"]),
            expected_model_root=root / str(judge_role["local_snapshot"]),
            expected_max_model_len=int(judge_role["runtime_limits"]["max_model_len"]),
        )
        self.teacher = SkillTeacher(
            self.teacher_client,
            root / "configs/prompts/skill_teacher_zh.txt",
            baseline_policy_paths=[
                root / "configs/prompts/consultation_policy_zh.txt",
            ],
        )
        self.judge_qualification_contract_sha256 = semantic_judge_qualification_sha256(
            root, judge_role
        )
        self.evaluator = SemanticEvaluator(
            self.judge_client,
            (root / "configs/prompts/semantic_judge_zh.txt").read_text(encoding="utf-8"),
            judge_qualification_contract_sha256=(self.judge_qualification_contract_sha256),
            reward_parameters=RewardParameters.model_validate(self.experiment["reward"]),
            max_attempts=int(execution["semantic_judgment_attempts"]),
            repair_judge=self.judge_repair_client,
            grounding_claims_per_call=int(judge_role["grounding_claims_per_call"]),
        )

    def _validate_learning_curve_configuration(self) -> dict[str, list[str]]:
        """Bind a fixed, outcome-blind cooperative-persona sentinel sample to every block."""

        curve = self.experiment.get("learning_curve")
        if not isinstance(curve, dict):
            raise ValueError("main experiment requires a learning_curve configuration")
        if (
            curve.get("mode") != "prequential_fixed_shadow"
            or curve.get("status") != "frozen_before_next_formal_run"
            or curve.get("no_pending_cohort_identity_shortcut") is not True
            or curve.get("evidence_role")
            != ("development_increment_diagnostic_and_next_teacher_direction_never_external_test")
        ):
            raise ValueError("learning-curve role or lifecycle differs from the frozen protocol")
        cases_per_block = int(curve.get("cases_per_block", 0))
        if cases_per_block < 4:
            raise ValueError("learning-curve requires at least four sentinel cases per block")
        if int(curve.get("bootstrap_samples", 0)) < 100:
            raise ValueError("learning-curve bootstrap budget is too small")
        cohort_validation = curve.get("incremental_effect_diagnostic")
        if not isinstance(cohort_validation, dict):
            raise ValueError("learning-curve incremental effect diagnostic is missing")
        expected_lifecycle = {
            "status": "frozen_before_next_formal_run",
            "timing": "next_unseen_training_block_before_teacher",
            "comparator": "exact_parent_library",
            "decision_role": ("descriptive_increment_measurement_before_teacher_never_skill_veto"),
            "single_block_effect_can_prune_or_rollback": False,
            "interval_uncertainty_alone_blocks_accumulation": False,
            "final_block_new_skill_budget": 0,
            "minimum_exposed_cases_for_interpretation": 1,
            "global_playbook_requires_full_cohort_exposure": True,
            "primary_signal": {
                "decision_rule": "primary_positive_point_estimate",
                "endpoints": ["unique_disclosed_facts_per_question"],
                "threshold": 0.0,
            },
        }
        if set(cohort_validation) != {
            *expected_lifecycle,
            "practical_effect_classifier",
            "interval_diagnostic",
        }:
            raise ValueError("increment diagnostic fields drifted")
        lifecycle = {key: cohort_validation.get(key) for key in expected_lifecycle}
        if lifecycle != expected_lifecycle:
            raise ValueError("increment diagnostic lifecycle drifted")
        retention_gate = cohort_validation.get("practical_effect_classifier")
        if retention_gate != _expected_practical_retention_gate(COHORT_PARENT_EFFECT_DIRECTION):
            raise ValueError("incremental practical-effect classifier drifted")
        pareto_gate = cohort_validation.get("interval_diagnostic")
        if not isinstance(pareto_gate, dict):
            raise ValueError("increment diagnostic Pareto classifier is missing")
        protected = list(pareto_gate.get("protected_endpoints") or [])
        expected_protected = [
            name for name in COHORT_GATE_ENDPOINT_DIRECTIONS if name != COHORT_GATE_PRIMARY_ENDPOINT
        ]
        expected_rules = {
            name: {"direction": direction, "margin": 0.0}
            for name, direction in COHORT_GATE_ENDPOINT_DIRECTIONS.items()
        }
        if (
            set(COHORT_GATE_ENDPOINT_DIRECTIONS) != set(PREQUENTIAL_CURVE_METRICS)
            or pareto_gate.get("schema_version") != 1
            or pareto_gate.get("decision_rule") != "case_cluster_pareto_noninferiority"
            or pareto_gate.get("effect_direction") != COHORT_PARENT_EFFECT_DIRECTION
            or pareto_gate.get("primary_endpoint") != COHORT_GATE_PRIMARY_ENDPOINT
            or protected != expected_protected
            or pareto_gate.get("endpoint_rules") != expected_rules
        ):
            raise ValueError("increment diagnostic Pareto endpoint contract drifted")
        final_safeguard = curve.get("final_cumulative_freeze_safeguard")
        if not isinstance(final_safeguard, dict) or final_safeguard != (
            _expected_final_training_holdout_config()
        ):
            raise ValueError("final training holdout safeguard configuration drifted")
        declared = curve.get("sentinel_case_ids_by_block")
        if not isinstance(declared, dict):
            raise ValueError("learning-curve sentinel map is missing")
        expected_batch_ids = [batch.batch_id for batch in self.training_plan.batches]
        if set(declared) != set(expected_batch_ids):
            raise ValueError("learning-curve sentinel blocks differ from the training plan")
        training_persona = self.training_plan.coverage_requirements.training_persona
        validated: dict[str, list[str]] = {}
        for batch in self.training_plan.batches:
            raw_ids = declared.get(batch.batch_id)
            if not isinstance(raw_ids, list) or not all(isinstance(item, str) for item in raw_ids):
                raise ValueError(f"invalid learning-curve sentinel list: {batch.batch_id}")
            case_ids = list(raw_ids)
            if len(case_ids) != len(set(case_ids)) or len(case_ids) != cases_per_block:
                raise ValueError(f"learning-curve sentinel cardinality drift: {batch.batch_id}")
            if not set(case_ids) <= set(batch.case_ids):
                raise ValueError(f"learning-curve sentinel escapes its block: {batch.batch_id}")
            personas = {batch.persona_assignment[case_id] for case_id in case_ids}
            if personas != {training_persona}:
                raise ValueError(f"learning-curve training persona drift: {batch.batch_id}")
            if cases_per_block == len(batch.case_ids) and case_ids != list(batch.case_ids):
                raise ValueError(f"full-block learning-curve order drift: {batch.batch_id}")
            validated[batch.batch_id] = case_ids
        return validated

    def _client_qualification_evidence(
        self,
    ) -> tuple[Path, Path, bool, dict[str, Any] | None, bool]:
        """Resolve the exact client-simulator evidence bound to this run.

        A qualification is component-scoped: when the current run has no local
        copy, the approved evidence pointer may bind an unchanged component to a
        prior immutable report.  Preflight and the run manifest must resolve the
        same paths; otherwise preflight can pass while manifest creation fails.
        A partial local qualification deliberately blocks reuse.
        """

        qualification_root = self.store.root / "qualifications" / "client_simulator"
        binding_path = qualification_root / "binding.json"
        report_path = qualification_root / "report.json"
        if report_path.is_file() or binding_path.is_file():
            return report_path, binding_path, False, None, True

        evidence_path = self.root / "configs/qualification/client_simulator_evidence.yaml"
        if not evidence_path.is_file():
            return report_path, binding_path, False, None, True
        evidence = _load_yaml(evidence_path)
        referenced_report = self.root / str(evidence.get("report_path", ""))
        referenced_binding = self.root / str(evidence.get("binding_path", ""))
        integrity = bool(
            evidence.get("schema_version") == 1
            and evidence.get("status") == "approved_component_scoped_evidence"
            and referenced_report.is_file()
            and referenced_binding.is_file()
            and sha256_file(referenced_report) == evidence.get("report_sha256")
            and sha256_file(referenced_binding) == evidence.get("binding_sha256")
        )
        if integrity:
            return referenced_report, referenced_binding, True, evidence, True
        return report_path, binding_path, False, evidence, False

    def _teacher_budget_ledger_reservations(
        self,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Read and validate the project-wide hard-budget ledger without reserving a call."""

        path = self.teacher_client.invocation_budget_path
        if path is None or self.teacher_client.max_invocations is None:
            return [], "teacher_hard_budget_not_configured"
        if not path.is_file():
            return [], None
        try:
            ledger = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            return [], f"teacher_budget_ledger_unreadable:{type(exc).__name__}"
        reservations = ledger.get("reservations") if isinstance(ledger, dict) else None
        if (
            not isinstance(ledger, dict)
            or ledger.get("schema_version") != 1
            or ledger.get("model") != self.teacher_client.model
            or ledger.get("max_invocations") != self.teacher_client.max_invocations
            or not isinstance(reservations, list)
        ):
            return [], "teacher_budget_ledger_contract_mismatch"
        expected_sequences = list(range(1, len(reservations) + 1))
        actual_sequences = [
            item.get("sequence") if isinstance(item, dict) else None for item in reservations
        ]
        if actual_sequences != expected_sequences or not all(
            isinstance(item, dict)
            and isinstance(item.get("reserved_at"), str)
            and isinstance(item.get("purpose"), str)
            and isinstance(item.get("request_sha256"), str)
            # Schema-v1 records every real transport attempt.  Historical
            # clients could retry one logical request, so attempts greater
            # than one are legitimate budget consumption rather than ledger
            # corruption.  (Current resumable map/reduce credit remains more
            # restrictive in _trusted_teacher_cache_issue below.)
            and isinstance(item.get("attempt"), int)
            and not isinstance(item.get("attempt"), bool)
            and item["attempt"] >= 1
            for item in reservations
        ):
            return [], "teacher_budget_ledger_reservations_invalid"
        return reservations, None

    def _playbook_teacher_round_resume_inputs(
        self,
        round_index: int,
    ) -> tuple[
        list[list[dict[str, Any]]],
        SkillContract | None,
        dict[str, Any],
    ]:
        """Reconstruct the exact current map/reduce inputs for trusted resume credit."""

        batch = self.training_plan.batches[round_index - 1]
        health_path = self.store.root / "health" / f"pre_scoring_health_{batch.batch_id}.json"
        health = json.loads(health_path.read_text(encoding="utf-8"))
        attribution = (health.get("quality_diagnostics") or {}).get(
            "training_group_attribution_review"
        )
        if not isinstance(attribution, dict) or attribution.get("scoring_eligible") is not True:
            raise ExecutionError("teacher resume inputs lack eligible group attribution")
        scoreable_group_ids = {str(item) for item in attribution.get("scoreable_group_ids") or []}
        if not scoreable_group_ids:
            raise ExecutionError("teacher resume inputs contain no scoreable groups")

        evidence_root = self.store.root / "evidence" / "group_cards"
        patches = [
            self.store.load_model(path, TrajectoryGroupEvidencePatch)
            for path in sorted(evidence_root.glob(f"round_{round_index:02d}_*.json"))
        ]
        if any(patch.partition != batch.batch_id for patch in patches):
            raise ExecutionError("teacher resume evidence partition drift")
        cards_by_group = {patch.group_id: patch.card for patch in patches}
        if len(cards_by_group) != len(patches) or set(cards_by_group) != scoreable_group_ids:
            raise ExecutionError("teacher resume evidence does not bind every scoreable group")
        ordered_cards = sorted(
            cards_by_group.values(), key=lambda item: (str(item["case_id"]), str(item["group_id"]))
        )
        map_packages = [ordered_cards[index::2] for index in range(2)]
        if any(not package for package in map_packages):
            raise ExecutionError("teacher resume requires two nonempty map packages")

        curve_path = self._learning_curve_point_path(round_index)
        curve_point = json.loads(curve_path.read_text(encoding="utf-8"))
        input_version = curve_point.get("input_skill_library_version")
        if not isinstance(input_version, str) or not input_version:
            raise ExecutionError("teacher resume curve lacks the input library version")
        runtime_skills = self._skills_for_library_version(input_version)
        if (
            sorted(skill.skill_id for skill in runtime_skills)
            != curve_point.get("input_active_skill_ids")
            or skill_library_sha256(runtime_skills)
            != curve_point.get("input_skill_library_sha256")
        ):
            raise ExecutionError("teacher resume curve input library drift")
        if len(runtime_skills) > 1 or any(
            skill.skill_id != PLAYBOOK_SKILL_ID for skill in runtime_skills
        ):
            raise ExecutionError("teacher resume input is not the single global playbook")
        current_playbook = runtime_skills[0] if runtime_skills else None

        library_feedback = prequential_input_library_feedback(
            curve_point,
            primary_endpoint=str(self.experiment["evaluation"]["primary_endpoint"]),
            case_domains={
                case_id: self.main_adapter.case_domain(case_id)
                for case_id in self.main_adapter.case_ids(
                    self.experiment["data"]["training_split"]
                )
            },
        )
        identity_feedback = bool(curve_point.get("identity_baseline"))
        parent_skills = (
            list(runtime_skills)
            if identity_feedback
            else self._skills_for_library_version(
                str(curve_point.get("parent_skill_library_version") or "")
            )
        )
        library_feedback = add_document_transition_feedback(
            library_feedback,
            current_skills=runtime_skills,
            parent_skills=parent_skills,
            declared_increment_ids=(
                set()
                if identity_feedback
                else {str(item) for item in curve_point.get("new_skill_increment_ids") or []}
            ),
        )
        return map_packages, current_playbook, library_feedback

    def _trusted_teacher_cache_issue(
        self,
        *,
        purpose: str,
        request_sha256: str,
        response_sha256: str,
        expected_value: dict[str, Any],
        expected_request_sha256: str,
        ledger_reservations: list[dict[str, Any]],
        ledger_issue: str | None,
    ) -> str | None:
        """Return ``None`` only for an exact response-cache and hard-ledger binding."""

        if request_sha256 != expected_request_sha256:
            return "teacher_request_binding_mismatch"
        cache_path = self.teacher_client.cache_root / purpose / f"{request_sha256}.json"
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            return f"missing_or_invalid_response_cache:{type(exc).__name__}"
        value = cached.get("value") if isinstance(cached, dict) else None
        invocation = cached.get("invocation") if isinstance(cached, dict) else None
        if (
            not isinstance(cached, dict)
            or cached.get("schema_version") != 1
            or cached.get("request_sha256") != request_sha256
            or cached.get("response_sha256") != response_sha256
            or cached.get("model") != self.teacher_client.model
            or cached.get("purpose") != purpose
            or value != expected_value
            or canonical_json_sha256(value) != response_sha256
            or not isinstance(invocation, dict)
            or invocation.get("returncode") != 0
            or invocation.get("tool_events_detected") is not False
        ):
            return "response_cache_contract_mismatch"
        if ledger_issue is not None:
            return ledger_issue
        reservation = invocation.get("budget_reservation")
        if (
            not isinstance(reservation, dict)
            or reservation.get("purpose") != purpose
            or reservation.get("request_sha256") != request_sha256
            or reservation.get("attempt") != 1
            or sum(reservation == item for item in ledger_reservations) != 1
        ):
            return "response_cache_budget_reservation_mismatch"
        return None

    def _trusted_persisted_playbook_teacher_calls(
        self,
        round_index: int,
        *,
        ledger_reservations: list[dict[str, Any]],
        ledger_issue: str | None,
    ) -> dict[str, Any]:
        """Verify resumable map/reduce stages, never retired proposal artifacts."""

        batch_id = self.training_plan.batches[round_index - 1].batch_id
        teacher_root = self.store.root / "teacher" / f"round_{round_index:02d}"
        map_paths = [teacher_root / f"{batch_id}.playbook_map_{index:02d}.json" for index in (1, 2)]
        reduce_path = teacher_root / f"{batch_id}.playbook_reduce.json"
        stage_paths = [*map_paths, reduce_path]
        existing_stage_paths = [path for path in stage_paths if path.is_file()]
        legacy_paths = sorted(teacher_root.glob("proposal_*.json"))
        required_stages = ["map_01", "map_02", "reduce"]
        if not existing_stage_paths:
            return {
                "trusted_count": 0,
                "trusted_stages": [],
                "trusted_files": [],
                "required_stages": required_stages,
                "remaining_stages": required_stages,
                "uncredited_stage_reasons": {
                    stage: "artifact_absent" for stage in required_stages
                },
                "resume_input_binding_status": "not_needed_no_persisted_stages",
                "ignored_files": {},
                "legacy_proposal_files_ignored": [
                    str(path.relative_to(self.root)) for path in legacy_paths
                ],
            }

        ignored: dict[str, str] = {}
        trusted_stages: list[str] = []
        trusted_files: list[str] = []
        try:
            map_packages, current_playbook, library_feedback = (
                self._playbook_teacher_round_resume_inputs(round_index)
            )
        except (
            ExecutionError,
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            ValueError,
        ) as exc:
            reason = f"playbook_resume_input_contract_invalid:{type(exc).__name__}"
            for path in existing_stage_paths:
                ignored[str(path.relative_to(self.root))] = reason
            return {
                "trusted_count": 0,
                "trusted_stages": [],
                "trusted_files": [],
                "required_stages": required_stages,
                "remaining_stages": required_stages,
                "uncredited_stage_reasons": {
                    stage: (
                        reason
                        if stage_paths[index].is_file()
                        else "artifact_absent"
                    )
                    for index, stage in enumerate(required_stages)
                },
                "resume_input_binding_status": "unavailable_conservative_no_credit",
                "resume_input_binding_issue": reason,
                "ignored_files": ignored,
                "legacy_proposal_files_ignored": [
                    str(path.relative_to(self.root)) for path in legacy_paths
                ],
            }

        trusted_maps: list[PlaybookModeArtifact] = []
        for index, (path, cards) in enumerate(zip(map_paths, map_packages, strict=True), start=1):
            if not path.is_file():
                continue
            relative = str(path.relative_to(self.root))
            package_id = f"{batch_id}.playbook_map_{index:02d}"
            expected_groups = sorted(str(card["group_id"]) for card in cards)
            try:
                artifact = self.store.load_model(path, PlaybookModeArtifact)
            except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                ignored[relative] = f"invalid_playbook_map_artifact:{type(exc).__name__}"
                continue
            accounted = {
                group_id for mode in artifact.modes for group_id in mode.source_group_ids
            } | set(artifact.no_new_mode_group_ids)
            expected_binding = playbook_map_input_binding_sha256(
                package_id=package_id,
                evidence_cards=cards,
                current_playbook=current_playbook,
            )
            if (
                artifact.package_id != package_id
                or artifact.teacher_model != self.teacher_client.model
                or artifact.input_binding_sha256 != expected_binding
                or artifact.source_group_ids != expected_groups
                or accounted != set(expected_groups)
            ):
                ignored[relative] = "playbook_map_artifact_binding_mismatch"
                continue
            expected_value = {
                "package_id": artifact.package_id,
                "modes": [mode.model_dump(mode="json") for mode in artifact.modes],
                "no_new_mode_group_ids": artifact.no_new_mode_group_ids,
            }
            request_payload = playbook_map_request_payload(
                package_id=package_id,
                evidence_cards=cards,
                current_playbook=current_playbook,
            )
            expected_request = _structured_codex_request_sha256(
                client=self.teacher_client,
                purpose="playbook_mode_extraction",
                system_prompt=self.teacher.mode_prompt,
                user_payload=request_payload,
                output_schema=_playbook_mode_output_schema(package_id=package_id),
            )
            issue = self._trusted_teacher_cache_issue(
                purpose="playbook_mode_extraction",
                request_sha256=artifact.request_sha256,
                response_sha256=artifact.response_sha256,
                expected_value=expected_value,
                expected_request_sha256=expected_request,
                ledger_reservations=ledger_reservations,
                ledger_issue=ledger_issue,
            )
            if issue is not None:
                ignored[relative] = issue
                continue
            trusted_maps.append(artifact)
            trusted_stages.append(f"map_{index:02d}")
            trusted_files.append(relative)

        if reduce_path.is_file():
            relative = str(reduce_path.relative_to(self.root))
            if len(trusted_maps) != 2:
                ignored[relative] = "playbook_reduce_requires_two_trusted_maps"
            else:
                package_id = f"{batch_id}.playbook_reduce"
                maximum_operations = (
                    INITIAL_PLAYBOOK_MAX_PATCH_OPERATIONS
                    if current_playbook is None
                    else EXISTING_PLAYBOOK_MAX_PATCH_OPERATIONS
                )
                try:
                    artifact = self.store.load_model(reduce_path, PlaybookReduceArtifact)
                except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                    ignored[relative] = (
                        f"invalid_playbook_reduce_artifact:{type(exc).__name__}"
                    )
                else:
                    expected_binding = playbook_reduce_input_binding_sha256(
                        package_id=package_id,
                        mode_artifacts=trusted_maps,
                        current_playbook=current_playbook,
                        library_feedback=library_feedback,
                        maximum_operations=maximum_operations,
                    )
                    proposal = artifact.proposal
                    if (
                        artifact.package_id != package_id
                        or artifact.input_binding_sha256 != expected_binding
                        or artifact.patch.package_id != package_id
                        or proposal.group_id != f"{package_id}::playbook"
                        or proposal.teacher_model != self.teacher_client.model
                    ):
                        ignored[relative] = "playbook_reduce_artifact_binding_mismatch"
                    else:
                        expected_value = artifact.patch.model_dump(mode="json")
                        request_payload = playbook_reduce_request_payload(
                            package_id=package_id,
                            mode_artifacts=trusted_maps,
                            current_playbook=current_playbook,
                            library_feedback=library_feedback,
                            maximum_operations=maximum_operations,
                        )
                        expected_request = _structured_codex_request_sha256(
                            client=self.teacher_client,
                            purpose="playbook_patch_curation",
                            system_prompt=self.teacher.prompt,
                            user_payload=request_payload,
                            output_schema=_playbook_patch_output_schema(
                                package_id=package_id,
                                maximum_operations=maximum_operations,
                            ),
                        )
                        issue = self._trusted_teacher_cache_issue(
                            purpose="playbook_patch_curation",
                            request_sha256=proposal.request_sha256,
                            response_sha256=proposal.response_sha256,
                            expected_value=expected_value,
                            expected_request_sha256=expected_request,
                            ledger_reservations=ledger_reservations,
                            ledger_issue=ledger_issue,
                        )
                        if issue is None:
                            try:
                                expected_proposal = materialize_playbook_proposal(
                                    package_id=package_id,
                                    evidence_cards=[
                                        card for package in map_packages for card in package
                                    ],
                                    mode_artifacts=trusted_maps,
                                    current_playbook=current_playbook,
                                    patch=artifact.patch,
                                    teacher_model=self.teacher_client.model,
                                    request_sha256=proposal.request_sha256,
                                    response_sha256=proposal.response_sha256,
                                )
                            except (TeacherProtocolError, ValueError):
                                issue = "playbook_reduce_proposal_replay_failed"
                            else:
                                if expected_proposal != proposal:
                                    issue = "playbook_reduce_proposal_materialization_mismatch"
                        if issue is None:
                            trusted_stages.append("reduce")
                            trusted_files.append(relative)
                        else:
                            ignored[relative] = issue
        ignored_reason_by_path = {
            str(path.relative_to(self.root)): ignored.get(str(path.relative_to(self.root)))
            for path in stage_paths
        }
        uncredited_stage_reasons = {
            stage: (
                ignored_reason_by_path[str(path.relative_to(self.root))]
                if path.is_file()
                else "artifact_absent"
            )
            for stage, path in zip(required_stages, stage_paths, strict=True)
            if stage not in trusted_stages
        }
        return {
            "trusted_count": len(trusted_stages),
            "trusted_stages": trusted_stages,
            "trusted_files": trusted_files,
            "required_stages": required_stages,
            "remaining_stages": [
                stage for stage in required_stages if stage not in trusted_stages
            ],
            "uncredited_stage_reasons": uncredited_stage_reasons,
            "resume_input_binding_status": "exact_reconstructed",
            "ignored_files": ignored,
            "legacy_proposal_files_ignored": [
                str(path.relative_to(self.root)) for path in legacy_paths
            ],
        }

    def _teacher_invocation_budget_contract(
        self,
        teacher_budget: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Return the exact worst-case new map/reduce calls still required."""

        configured_call_budget = int(
            self.experiment["execution"]["teacher_call_budget_per_round"]
        )
        formal_stages = ("map_01", "map_02", "reduce")
        formal_call_budget = len(formal_stages)
        protocol_issue = (
            None
            if configured_call_budget == formal_call_budget
            else (
                "teacher_call_budget_must_equal_two_maps_plus_one_reduce:"
                f"configured={configured_call_budget}"
            )
        )
        ledger_reservations, ledger_issue = self._teacher_budget_ledger_reservations()
        unfinished_rounds: list[int] = []
        persisted_by_round: dict[str, dict[str, Any]] = {}
        remaining_by_round: dict[str, int] = {}
        untrusted_persisted_stages_by_round: dict[str, dict[str, str]] = {}
        maximum_new_calls = 0
        for round_index in range(1, len(self.training_plan.batches) + 1):
            batch_id = self.training_plan.batches[round_index - 1].batch_id
            block_complete = (
                self.store.root
                / "manifests"
                / f"{self._direct_block_manifest_name(batch_id)}.json"
            )
            if block_complete.is_file():
                continue
            unfinished_rounds.append(round_index)
            if round_index == len(self.training_plan.batches):
                persisted = {
                    "trusted_count": 0,
                    "trusted_stages": [],
                    "trusted_files": [],
                    "required_stages": [],
                    "remaining_stages": [],
                    "uncredited_stage_reasons": {},
                    "resume_input_binding_status": "final_observation_block_no_teacher_calls",
                    "ignored_files": {},
                    "legacy_proposal_files_ignored": [],
                }
                remaining = 0
            else:
                persisted = self._trusted_persisted_playbook_teacher_calls(
                    round_index,
                    ledger_reservations=ledger_reservations,
                    ledger_issue=ledger_issue,
                )
                remaining = formal_call_budget - int(persisted["trusted_count"])
            persisted_by_round[str(round_index)] = persisted
            remaining_by_round[str(round_index)] = remaining
            ignored_files = persisted.get("ignored_files")
            if isinstance(ignored_files, dict) and ignored_files:
                untrusted_persisted_stages_by_round[str(round_index)] = {
                    str(path): str(reason) for path, reason in ignored_files.items()
                }
            maximum_new_calls += remaining
        available = int(teacher_budget.get("available", -1)) if teacher_budget else -1
        budget_status_issue: str | None = None
        if teacher_budget is not None and self.teacher_client.max_invocations is not None:
            expected_reserved = len(ledger_reservations)
            expected_limit = int(self.teacher_client.max_invocations)
            expected_available = max(expected_limit - expected_reserved, 0)
            if (
                int(teacher_budget.get("reserved", -1)) != expected_reserved
                or int(teacher_budget.get("hard_limit", -1)) != expected_limit
                or available != expected_available
            ):
                budget_status_issue = "teacher_budget_status_does_not_match_hard_ledger"
        return {
            "passed": (
                teacher_budget is not None
                and protocol_issue is None
                and ledger_issue is None
                and budget_status_issue is None
                and not untrusted_persisted_stages_by_round
                and available >= maximum_new_calls
            ),
            "formal_teacher_stages_per_learning_block": list(formal_stages),
            "configured_teacher_call_budget_per_round": configured_call_budget,
            "teacher_protocol_issue": protocol_issue,
            "maximum_formal_new_calls": maximum_new_calls,
            "unfinished_teacher_rounds": unfinished_rounds,
            "trusted_persisted_teacher_calls_by_round": persisted_by_round,
            "remaining_new_calls_by_round": remaining_by_round,
            "untrusted_persisted_stages_by_round": untrusted_persisted_stages_by_round,
            "hard_ledger_contract_issue": ledger_issue,
            "budget_status_contract_issue": budget_status_issue,
            **(teacher_budget or {}),
        }

    def _playbook_teacher_structured_probe(self) -> dict[str, Any]:
        """Exercise the current map interface without writing a formal teacher artifact."""

        package_id = "preflight.playbook_map"
        card = _playbook_teacher_preflight_card()
        try:
            artifact = self.teacher.extract_playbook_modes(
                package_id=package_id,
                evidence_cards=[card],
                current_playbook=None,
                purpose="preflight_playbook_mode_extraction",
            )
        except (CodexInvocationError, TeacherProtocolError, ValueError) as exc:
            return {
                "requested": True,
                "passed": False,
                "error_type": type(exc).__name__,
                "error_sha256": canonical_json_sha256({"error": str(exc)}),
            }
        expected_binding = playbook_map_input_binding_sha256(
            package_id=package_id,
            evidence_cards=[card],
            current_playbook=None,
        )
        return {
            "requested": True,
            "passed": (
                artifact.package_id == package_id
                and artifact.input_binding_sha256 == expected_binding
                and artifact.source_group_ids == [str(card["group_id"])]
                and artifact.teacher_model == self.teacher_client.model
            ),
            "request_sha256": artifact.request_sha256,
            "response_sha256": artifact.response_sha256,
            "input_binding_sha256": artifact.input_binding_sha256,
            "schema": "PlaybookModeBatchDraft",
            "purpose": "preflight_playbook_mode_extraction",
        }

    def preflight(self, *, probe_codex: bool = False) -> PreflightReport:
        hashes = self.data_config["hashes"]
        paths = {
            "core_sha256": self.root / self.data_config["core_cases"],
            "provenance_sha256": self.root / self.data_config["provenance"],
            "selection_sha256": self.root / self.data_config["selection_manifest"],
            "training_batches_sha256": self.training_batch_path,
            "source_catalog_sha256": self.root / self.data_config["source_catalog"],
        }
        data_hashes = {
            key: {
                "passed": path.is_file() and sha256_file(path) == str(hashes[key]),
                "actual": sha256_file(path) if path.is_file() else None,
                "expected": str(hashes[key]),
            }
            for key, path in paths.items()
        }
        current_core_sha256 = data_hashes["core_sha256"]["actual"]
        current_provenance_sha256 = data_hashes["provenance_sha256"]["actual"]
        current_selection_sha256 = data_hashes["selection_sha256"]["actual"]

        def audit_report_contract(
            config_key: str,
            report_hash_key: str,
            input_checks: dict[str, tuple[str, Any]],
        ) -> dict[str, Any]:
            path = self.root / self.data_config[config_key]
            expected_report_sha256 = hashes.get(report_hash_key)
            if not path.is_file():
                return {
                    "passed": False,
                    "path": str(path.relative_to(self.root)),
                    "report_exists": False,
                    "expected_report_sha256": expected_report_sha256,
                }
            report = json.loads(path.read_text(encoding="utf-8"))
            actual_report_sha256 = sha256_file(path)
            checks_for_report = {
                "status_passed": report.get("status") == "passed",
                "report_hash_matches": bool(expected_report_sha256)
                and actual_report_sha256 == expected_report_sha256,
                **{
                    name: report.get(field) == expected
                    for name, (field, expected) in input_checks.items()
                },
            }
            return {
                "passed": all(checks_for_report.values()),
                "path": str(path.relative_to(self.root)),
                "report_exists": True,
                "actual_report_sha256": actual_report_sha256,
                "expected_report_sha256": expected_report_sha256,
                "contract_checks": checks_for_report,
            }

        corpus_audit_reports = {
            "deterministic_quality": audit_report_contract(
                "quality_report",
                "deterministic_quality_report_sha256",
                {
                    "core_matches": ("core_sha256", current_core_sha256),
                    "provenance_matches": (
                        "provenance_sha256",
                        current_provenance_sha256,
                    ),
                },
            ),
            "casewise_quality": audit_report_contract(
                "casewise_quality_report",
                "casewise_quality_report_sha256",
                {
                    "core_matches": ("core_sha256", current_core_sha256),
                    "provenance_matches": (
                        "provenance_sha256",
                        current_provenance_sha256,
                    ),
                    "selection_matches": ("selection_sha256", current_selection_sha256),
                },
            ),
            "external_contamination": audit_report_contract(
                "contamination_report",
                "contamination_report_sha256",
                {
                    "core_matches": ("formal_core_sha256", current_core_sha256),
                    "selection_matches": ("selection_sha256", current_selection_sha256),
                    "selected_case_count": (
                        "selected_source_cases",
                        int(self.data_config["formal_cases"]),
                    ),
                },
            ),
            "opening_information_boundary": audit_report_contract(
                "opening_information_boundary_report",
                "opening_information_boundary_report_sha256",
                {
                    "core_matches": ("data_sha256", current_core_sha256),
                    "case_count": ("case_count", int(self.data_config["formal_cases"])),
                    "fact_count": ("fact_count", int(self.data_config["fact_pairs"])),
                },
            ),
        }
        corpus_audits_ready = all(report["passed"] for report in corpus_audit_reports.values())
        model_snapshot = self.root / self.roles["roles"]["lawyer_policy"]["local_snapshot"]
        model_index = model_snapshot / "model.safetensors.index.json"
        missing_model_files: list[str] = []
        if model_index.is_file():
            index_value = json.loads(model_index.read_text(encoding="utf-8"))
            weight_files = sorted(set(index_value.get("weight_map", {}).values()))
            missing_model_files = [
                name for name in weight_files if not (model_snapshot / name).is_file()
            ]
        else:
            weight_files = []
            missing_model_files = [model_index.name]
        model_ready = bool(weight_files) and not missing_model_files
        model_manifest = verify_model_manifest(self.root, self.roles["roles"]["lawyer_policy"])
        local_endpoint = self.local_client.readiness()
        client_selector_endpoint = self.client_selector_client.readiness()
        local_ready = bool(local_endpoint["ready"])
        client_selector_ready = bool(client_selector_endpoint["ready"])
        judge_role = self.roles["roles"]["semantic_judge"]
        judge_snapshot = self.root / judge_role["local_snapshot"]
        judge_index = judge_snapshot / "model.safetensors.index.json"
        judge_missing_files: list[str] = []
        if judge_index.is_file():
            judge_index_value = json.loads(judge_index.read_text(encoding="utf-8"))
            judge_weight_files = sorted(set(judge_index_value.get("weight_map", {}).values()))
            judge_missing_files = [
                name for name in judge_weight_files if not (judge_snapshot / name).is_file()
            ]
        else:
            judge_weight_files = []
            judge_missing_files = [judge_index.name]
        judge_model_ready = bool(judge_weight_files) and not judge_missing_files
        judge_model_manifest = verify_model_manifest(
            self.root, self.roles["roles"]["semantic_judge"]
        )
        judge_endpoint = self.judge_client.preflight()
        qualification_path = self.root / "reports/artifacts/local_judge_qualification.json"
        if qualification_path.is_file():
            qualification = json.loads(qualification_path.read_text(encoding="utf-8"))
            qualification_contract = {
                "report_passed": bool(qualification.get("passed")),
                "report_schema_matches": qualification.get("schema_version")
                == SEMANTIC_JUDGE_QUALIFICATION_REPORT_SCHEMA_VERSION,
                "base_url_matches": qualification.get("base_url")
                == self.judge_client.base_url
                == str(judge_role["base_url"]).rstrip("/"),
                "model_matches": qualification.get("model") == self.judge_client.model,
                "revision_matches": qualification.get("model_revision")
                == str(judge_role["revision"]),
                "protocol_matches": qualification.get("qualification_protocol")
                == int(judge_role["qualification_protocol"]),
                "judge_contract_matches": qualification.get("judge_qualification_contract_sha256")
                == semantic_judge_qualification_sha256(self.root, judge_role),
                "reasoning_effort_matches": qualification.get("reasoning_effort")
                == self.judge_client.reasoning_effort,
                "token_budget_matches": qualification.get("max_completion_tokens")
                == self.judge_client.max_completion_tokens,
                "repair_token_budget_matches": qualification.get("repair_max_completion_tokens")
                == self.judge_repair_client.max_completion_tokens,
                "workers_match": qualification.get("workers")
                == int(self.experiment["execution"]["judge_workers"]),
                "semantic_judge_role_matches": qualification.get("semantic_judge_role_sha256")
                == canonical_json_sha256(judge_role),
                "endpoint_preflight_passed": (qualification.get("preflight") or {}).get("ready")
                is True,
                "no_execution_failures": qualification.get("failures") == [],
                "no_threshold_failures": qualification.get("threshold_failures") == [],
                **semantic_judge_qualification_data_contract_checks(self.root, qualification),
            }
            judge_qualified = all(qualification_contract.values())
        else:
            qualification = None
            qualification_contract = {"report_exists": False}
            judge_qualified = False
        (
            client_qualification_path,
            client_qualification_binding_path,
            client_qualification_reused,
            client_evidence,
            client_evidence_integrity,
        ) = self._client_qualification_evidence()
        selector_role = self.roles["roles"]["client_fact_selector"]
        if client_qualification_path.is_file() and client_qualification_binding_path.is_file():
            client_qualification = json.loads(client_qualification_path.read_text(encoding="utf-8"))
            client_qualification_binding = json.loads(
                client_qualification_binding_path.read_text(encoding="utf-8")
            )
            expected_client_components = client_simulator_qualification_component_hashes(self.root)
            binding_fields = (
                "qualification_protocol",
                "model",
                "model_revision",
                "disclosure_model",
                "disclosure_model_revision",
                "selector_endpoint_contract",
                "disclosure_endpoint_contract",
                "client_simulator_qualification_contract_sha256",
                *sorted(expected_client_components),
            )
            client_qualification_contract = {
                "report_passed": bool(client_qualification.get("passed")),
                "report_schema_matches": client_qualification.get("schema_version")
                == CLIENT_QUALIFICATION_REPORT_SCHEMA_VERSION,
                "fixture_schema_matches": client_qualification.get("fixture_schema_version")
                == CLIENT_QUALIFICATION_FIXTURE_SCHEMA_VERSION,
                "run_or_component_scope_matches": (
                    client_qualification.get("run_id")
                    == client_qualification_binding.get("run_id")
                    == (
                        client_evidence.get("source_run_id")
                        if client_qualification_reused and client_evidence is not None
                        else self.run_id
                    )
                ),
                "component_evidence_integrity": client_evidence_integrity,
                "protocol_matches": client_qualification.get("qualification_protocol")
                == client_qualification_binding.get("qualification_protocol")
                == int(selector_role["qualification_protocol"]),
                "model_matches": client_qualification.get("model") == self.client_selector_model,
                "revision_matches": client_qualification.get("model_revision")
                == self.client_selector_revision,
                "contract_matches": client_qualification.get(
                    "client_simulator_qualification_contract_sha256"
                )
                == client_simulator_qualification_sha256(
                    self.root,
                    selector_role,
                    self.roles["roles"]["client_disclosure_classifier"],
                ),
                "disclosure_model_matches": client_qualification.get("disclosure_model")
                == self.local_model,
                "disclosure_revision_matches": client_qualification.get("disclosure_model_revision")
                == self.local_revision,
                "selector_endpoint_contract_matches": client_qualification.get(
                    "selector_endpoint_contract"
                )
                == client_qualification_binding.get("selector_endpoint_contract")
                == client_selector_endpoint,
                "disclosure_endpoint_contract_matches": client_qualification.get(
                    "disclosure_endpoint_contract"
                )
                == client_qualification_binding.get("disclosure_endpoint_contract")
                == local_endpoint,
                "component_hashes_match": all(
                    client_qualification.get(key)
                    == client_qualification_binding.get(key)
                    == expected
                    for key, expected in expected_client_components.items()
                ),
                "binding_fields_match": all(
                    client_qualification.get(key) == client_qualification_binding.get(key)
                    for key in binding_fields
                ),
                "binding_hash_matches": client_qualification.get("qualification_binding_sha256")
                == canonical_json_sha256(client_qualification_binding),
                # Component evidence may be moved under rejected_diagnostics after
                # its source run is closed.  The immutable report must retain the
                # binding path at which it was originally issued; the approved
                # evidence pointer separately binds the archived physical path and
                # both file hashes.  Requiring the archived path inside the old
                # report would make honest archival invalidate an unchanged
                # component qualification.
                "binding_path_matches": client_qualification.get("qualification_binding_path")
                == (
                    "runs/"
                    + str(client_evidence.get("source_run_id"))
                    + "/qualifications/client_simulator/binding.json"
                    if client_qualification_reused and client_evidence is not None
                    else str(client_qualification_binding_path.relative_to(self.root))
                ),
                "cross_domain_cases": int(client_qualification.get("case_count") or 0)
                >= int(selector_role["qualification_min_cases"]),
                "contrast_count": int(client_qualification.get("contrast_count") or 0)
                >= int(selector_role["qualification_min_contrasts"]),
                "withhold_coverage": int(client_qualification.get("withhold_count") or 0) >= 2,
                "transition_coverage": int(client_qualification.get("transition_chain_count") or 0)
                >= 2,
                "match_accuracy": float(client_qualification.get("match_accuracy") or 0.0)
                >= float(selector_role["qualification_min_match_accuracy"]),
                "matched_accuracy": float(client_qualification.get("matched_accuracy") or 0.0)
                >= float(selector_role["qualification_min_matched_accuracy"]),
                "unmatched_accuracy": float(client_qualification.get("unmatched_accuracy") or 0.0)
                >= float(selector_role["qualification_min_unmatched_accuracy"]),
                "disclosure_accuracy": float(client_qualification.get("disclosure_accuracy") or 0.0)
                >= float(selector_role["qualification_min_disclosure_accuracy"]),
                "response_kind_accuracy": float(
                    client_qualification.get("response_kind_accuracy") or 0.0
                )
                >= float(selector_role["qualification_min_response_kind_accuracy"]),
                "transition_accuracy": float(client_qualification.get("transition_accuracy") or 0.0)
                >= float(selector_role["qualification_min_transition_accuracy"]),
                "contract_fallback_rate": float(
                    client_qualification.get("contract_fallback_rate") or 0.0
                )
                <= float(selector_role["qualification_max_contract_fallback_rate"]),
                "no_threshold_failures": client_qualification.get("threshold_failures") == [],
            }
            client_qualified = all(client_qualification_contract.values())
        else:
            client_qualification = None
            client_qualification_binding = None
            client_qualification_contract = {
                "report_exists": client_qualification_path.is_file(),
                "binding_exists": client_qualification_binding_path.is_file(),
            }
            client_qualified = False
        codex_auth = self.teacher_client.preflight()
        configured_teacher_executable = Path(
            str(self.roles["roles"]["skill_teacher"]["executable"])
        )
        playbook_map_schema = _playbook_mode_output_schema(
            package_id="preflight.playbook_map"
        )
        playbook_reduce_schema = _playbook_patch_output_schema(
            package_id="preflight.playbook_reduce",
            maximum_operations=INITIAL_PLAYBOOK_MAX_PATCH_OPERATIONS,
        )
        teacher_transport_contract = {
            "configured_executable_is_absolute": configured_teacher_executable.is_absolute(),
            "resolved_executable_matches": codex_auth.get("executable")
            == str(configured_teacher_executable.resolve()),
            "authenticated": bool(codex_auth.get("ready")),
            "zero_automatic_retries": self.teacher_client.retries == 0,
            "process_tree_timeout_seconds": self.teacher_client.timeout_seconds,
            "strict_playbook_map_schema": not strict_output_schema_issues(
                playbook_map_schema
            ),
            "strict_playbook_reduce_schema": not strict_output_schema_issues(
                playbook_reduce_schema
            ),
        }
        teacher_transport_ready = (
            all(
                value
                for key, value in teacher_transport_contract.items()
                if key != "process_tree_timeout_seconds"
            )
            and int(teacher_transport_contract["process_tree_timeout_seconds"]) >= 600
        )
        codex_probe: dict[str, Any] = {"requested": probe_codex, "passed": None}
        if probe_codex and codex_auth["ready"]:
            codex_probe = self._playbook_teacher_structured_probe()
        judge_probe: dict[str, Any] = {"requested": probe_codex, "passed": None}
        if probe_codex and judge_endpoint["ready"]:
            try:
                response = self.judge_client.generate_json(
                    purpose="preflight",
                    system_prompt="你是无工具的本地结构化评审组件。",
                    user_prompt='只返回 {"ready": true}。',
                    output_schema={
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["ready"],
                        "properties": {"ready": {"type": "boolean", "const": True}},
                    },
                )
            except StructuredModelInvocationError as exc:
                judge_probe = {
                    "requested": True,
                    "passed": False,
                    "error_type": type(exc).__name__,
                    "error_sha256": canonical_json_sha256({"error": str(exc)}),
                }
            else:
                judge_probe = {
                    "requested": True,
                    "passed": response.value == {"ready": True},
                    "request_sha256": response.request_sha256,
                    "response_sha256": response.response_sha256,
                }
        teacher_budget = self.teacher_client.invocation_budget_status()
        teacher_budget_contract = self._teacher_invocation_budget_contract(teacher_budget)
        teacher_budget_ready = bool(teacher_budget_contract["passed"])
        try:
            initial_skills, initial_library_binding = self.initial_skill_library()
        except (ExecutionError, OSError, ValueError, yaml.YAMLError) as exc:
            initial_library_check: dict[str, Any] = {
                "passed": False,
                "configured_path": (self.experiment.get("skill_evolution") or {}).get(
                    "initial_library"
                ),
                "error": str(exc),
            }
        else:
            initial_library_check = {
                "passed": not initial_skills,
                "skill_count": len(initial_skills),
                **initial_library_binding,
            }
        checks = {
            "experiment_status": {
                "value": self.experiment.get("status"),
                "passed": self.experiment.get("status")
                == "shared_opening_agenda_group_evidence_gpu_requalification_required",
            },
            "role_assignment_status": _role_assignment_status_check(self.roles),
            "data_hashes": data_hashes,
            "corpus_status": {
                "value": self.data_config.get("status"),
                "passed": self.data_config.get("status")
                == "frozen_128_cpu_audited_runtime_requalification_required",
            },
            "corpus_audit_reports": corpus_audit_reports,
            "model_snapshot_complete": model_ready,
            "model_snapshot_missing_files": missing_model_files,
            "model_manifest_integrity": model_manifest,
            "local_vllm_ready": local_ready,
            "local_vllm_endpoint_contract": local_endpoint,
            "client_selector_vllm_ready": client_selector_ready,
            "client_selector_vllm_endpoint_contract": client_selector_endpoint,
            "judge_snapshot_complete": judge_model_ready,
            "judge_snapshot_missing_files": judge_missing_files,
            "judge_model_manifest_integrity": judge_model_manifest,
            "judge_vllm_ready": judge_endpoint,
            "judge_qualification": {
                "passed": judge_qualified,
                "path": str(qualification_path.relative_to(self.root)),
                "report_sha256": sha256_file(qualification_path)
                if qualification_path.is_file()
                else None,
                "contract_checks": qualification_contract,
            },
            "judge_structured_probe": judge_probe,
            "client_simulator_qualification": {
                "passed": client_qualified,
                "path": str(client_qualification_path.relative_to(self.root)),
                "evidence_scope": (
                    "component_scoped_reuse" if client_qualification_reused else "current_run"
                ),
                "report_sha256": sha256_file(client_qualification_path)
                if client_qualification_path.is_file()
                else None,
                "contract_checks": client_qualification_contract,
            },
            "codex_authenticated": codex_auth,
            "teacher_transport_contract": {
                "passed": teacher_transport_ready,
                "checks": teacher_transport_contract,
            },
            "teacher_invocation_budget": teacher_budget_contract,
            "codex_structured_probe": codex_probe,
            "main_cases": len(self.main_adapter.case_ids()),
            "training_cases": len(
                self.main_adapter.case_ids(self.experiment["data"]["training_split"])
            ),
            "fixed_internal_validation_cases": int(
                self.data_config["fixed_internal_validation_cases"]
            ),
            "training_batches": len(self.training_plan.batches),
            "cases_per_training_batch": self.training_plan.cases_per_batch,
            "training_batch_plan_sha256": sha256_file(self.training_batch_path),
            "external_cases": (
                len(self.external_adapter.case_ids()) if self.external_adapter is not None else None
            ),
            "initial_skill_library": initial_library_check,
            "formal_learned_objective_boundary": {
                "passed": True,
                "learnable_objectives": list(formal_learnable_skill_objectives(self.experiment)),
                "termination_policy_owner": FORMAL_TERMINATION_POLICY_OWNER,
            },
            "comparison_arm_contract": {
                "expected": [
                    "control_no_library",
                    "legal_skill_evolve",
                ],
                "actual": [
                    str(item.get("arm_id")) for item in self.experiment.get("comparison_arms", [])
                ],
            },
            "active_skill_static_issues": {
                item.skill_id: sorted(
                    set(
                        [
                            *validate_skill_static(item),
                            *formal_skill_document_issues(
                                item,
                                learnable_objectives=formal_learnable_skill_objectives(
                                    self.experiment
                                ),
                            ),
                        ]
                    )
                )
                for item in self.active_skills()
            },
            "adaptive_termination_contract": termination_contract_check(
                int(self.experiment["emergency_turn_ceiling"])
            ),
        }
        ready = (
            bool(checks["experiment_status"]["passed"])
            and bool(checks["role_assignment_status"]["passed"])
            and all(item["passed"] for item in data_hashes.values())
            and bool(checks["corpus_status"]["passed"])
            and corpus_audits_ready
            and model_ready
            and bool(model_manifest["passed"])
            and local_ready
            and client_selector_ready
            and judge_model_ready
            and bool(judge_model_manifest["passed"])
            and bool(judge_endpoint["ready"])
            and judge_qualified
            and client_qualified
            and bool(codex_auth["ready"])
            and teacher_transport_ready
            and teacher_budget_ready
            and (not probe_codex or bool(codex_probe["passed"]))
            and (not probe_codex or bool(judge_probe["passed"]))
            and checks["main_cases"] == 128
            and checks["training_cases"] == 128
            and checks["fixed_internal_validation_cases"] == 0
            and checks["training_batches"] == 8
            and checks["cases_per_training_batch"] == 16
            and checks["external_cases"] == 30
            and bool(checks["initial_skill_library"]["passed"])
            and checks["comparison_arm_contract"]["actual"]
            == checks["comparison_arm_contract"]["expected"]
            and not any(checks["active_skill_static_issues"].values())
            and bool(checks["adaptive_termination_contract"]["passed"])
        )
        return PreflightReport(ready=ready, checks=checks)

    def write_run_manifest(self, *, overwrite: bool = False) -> Path:
        if overwrite:
            raise ExecutionError("run manifests are immutable; use a new run_id for a new binding")
        (
            client_qualification_path,
            client_qualification_binding_path,
            _,
            _,
            client_evidence_integrity,
        ) = self._client_qualification_evidence()
        if not (
            client_evidence_integrity
            and client_qualification_path.is_file()
            and client_qualification_binding_path.is_file()
        ):
            raise ExecutionError("qualified client-simulator evidence is unavailable")
        _, initial_library_binding = self.initial_skill_library()
        prompt_files = sorted((self.root / "configs/prompts").glob("*.txt"))
        binding = {
            "schema_version": 3,
            "run_id": self.run_id,
            "experiment_config_sha256": sha256_file(self.experiment_path),
            "roles_config_sha256": sha256_file(self.roles_path),
            "data_config_sha256": sha256_file(self.data_path),
            "prompt_hashes": {path.name: sha256_file(path) for path in prompt_files},
            "implementation_sha256": implementation_sha256(self.root),
            "model_artifact_hashes": {
                name: sha256_file(
                    self.root / self.roles["roles"]["lawyer_policy"]["local_snapshot"] / name
                )
                for name in ("config.json", "model.safetensors.index.json")
            },
            "model_manifest_sha256": sha256_file(
                self.root / self.roles["roles"]["lawyer_policy"]["manifest"]
            ),
            "judge_model_artifact_hashes": {
                name: sha256_file(
                    self.root / self.roles["roles"]["semantic_judge"]["local_snapshot"] / name
                )
                for name in ("config.json", "model.safetensors.index.json")
            },
            "judge_model_manifest_sha256": sha256_file(
                self.root / self.roles["roles"]["semantic_judge"]["manifest"]
            ),
            "judge_qualification_sha256": sha256_file(
                self.root / "reports/artifacts/local_judge_qualification.json"
            ),
            "client_qualification_path": str(client_qualification_path.relative_to(self.root)),
            "client_qualification_sha256": sha256_file(client_qualification_path),
            "client_qualification_binding_path": str(
                client_qualification_binding_path.relative_to(self.root)
            ),
            "client_qualification_binding_sha256": sha256_file(client_qualification_binding_path),
            "core_sha256": sha256_file(self.root / self.data_config["core_cases"]),
            "provenance_sha256": sha256_file(self.root / self.data_config["provenance"]),
            "selection_sha256": sha256_file(self.root / self.data_config["selection_manifest"]),
            "training_batch_plan_sha256": sha256_file(self.training_batch_path),
            "initial_skill_library_path": initial_library_binding["path"],
            "initial_skill_library_id": initial_library_binding["id"],
            "initial_skill_library_sha256": initial_library_binding["sha256"],
            "source_catalog_sha256": sha256_file(self.root / self.data_config["source_catalog"]),
            "corpus_quality_report_sha256": sha256_file(
                self.root / self.data_config["quality_report"]
            ),
            "corpus_casewise_quality_report_sha256": sha256_file(
                self.root / self.data_config["casewise_quality_report"]
            ),
            "corpus_contamination_report_sha256": sha256_file(
                self.root / self.data_config["contamination_report"]
            ),
            "corpus_opening_information_boundary_report_sha256": sha256_file(
                self.root / self.data_config["opening_information_boundary_report"]
            ),
            "external_cases_sha256": sha256_file(
                self.root / self.experiment["data"]["external_evaluation"]
            ),
            "personas_sha256": sha256_file(self.personas_path),
            "model_id": self.local_model,
            "model_revision": self.local_revision,
            "client_selector_model": self.client_selector_model,
            "client_selector_revision": self.client_selector_revision,
            "teacher_model": self.teacher_client.model,
            "judge_model": self.judge_client.model,
        }
        binding_sha256 = canonical_json_sha256(binding)
        path = self.store.root / "manifests" / "run.json"
        if path.is_file():
            prior = self.store.read_manifest("run")
            prior_binding = {
                key: value
                for key, value in prior.items()
                if key
                not in {
                    "binding_sha256",
                    "content_sha256",
                    "created_at",
                    "status",
                }
            }
            mismatches = sorted(
                {
                    key
                    for key in set(binding) | set(prior_binding)
                    if prior_binding.get(key) != binding.get(key)
                }
            )
            if prior.get("binding_sha256") != binding_sha256:
                mismatches.append("binding_sha256")
            if mismatches:
                raise ExecutionError(
                    "immutable run manifest does not match the current experiment "
                    f"binding ({', '.join(sorted(set(mismatches)))}); "
                    "use a new run_id instead of reusing or overwriting this run"
                )
            return path
        value = {
            **binding,
            "binding_sha256": binding_sha256,
            "created_at": datetime.now(UTC).isoformat(),
            "status": "initialized",
        }
        return self.store.write_manifest("run", value, overwrite=False)

    def verify_run_manifest(self) -> dict[str, Any]:
        """Verify current code inputs against the immutable run manifest."""
        self.write_run_manifest(overwrite=False)
        return self.store.read_manifest("run")

    def initial_skill_library(self) -> tuple[list[SkillContract], dict[str, str]]:
        """Return the one configured, parsed and empty formal starting library."""

        return load_formal_initial_skill_library(self.root, self.experiment)

    def formal_training_artifacts(self) -> list[Path]:
        """List artifacts proving that this run ID is not a fresh formal run.

        Component qualification and endpoint preflight caches may leave a run
        directory before training.  They are deliberately not treated as formal
        progress.  Conversely, every training checkpoint, learned-skill artifact,
        scored trajectory, teacher artifact and formal report is fail-closed.
        """

        run_root = self.store.root
        found: set[Path] = set()

        def add_files(path: Path) -> None:
            if path.is_file():
                found.add(path)
            elif path.is_dir():
                found.update(item for item in path.rglob("*") if item.is_file())

        add_files(run_root / "manifests")
        for directory in (
            "skills",
            "evaluations",
            "teacher",
            "evidence",
        ):
            add_files(run_root / directory)

        trajectories_root = run_root / "trajectories"
        if trajectories_root.is_dir():
            for path in trajectories_root.iterdir():
                if path.name.startswith("diagnostic_"):
                    continue
                add_files(path)

        reports_root = run_root / "reports"
        formal_report_names = {
            "development_learning_curve.json",
            "external_test.json",
            "external_seed_sensitivity.json",
        }
        formal_report_prefixes = (
            DIRECT_SKILL_ADMISSION_REPORT_PREFIX,
            "learning_checkpoint_",
            "library_maintenance_",
            "development_curve_point_",
        )
        if reports_root.is_dir():
            for path in reports_root.rglob("*"):
                if path.is_file() and (
                    path.name in formal_report_names or path.name.startswith(formal_report_prefixes)
                ):
                    found.add(path)

        health_root = run_root / "health"
        if health_root.is_dir():
            for path in health_root.rglob("*"):
                if path.is_file() and path.name != "diagnostic_health.json":
                    found.add(path)

        formal_namespaces = {
            *(batch.batch_id for batch in self.training_plan.batches),
            "external_test",
            "external_seed_sensitivity",
        }
        cache_root = run_root / "cache"
        if cache_root.is_dir():
            for request_cache in (
                "paired_exact_requests",
                "client_selector_exact_requests",
                "client_disclosure_exact_requests",
            ):
                add_files(cache_root / request_cache)
            for path in cache_root.rglob("*"):
                if not path.is_file():
                    continue
                parts = set(path.relative_to(cache_root).parts)
                if parts & formal_namespaces or any(
                    part.startswith("learning_curve_shadow_") for part in parts
                ):
                    found.add(path)
        return sorted(found, key=lambda path: str(path))

    def assert_training_start_mode(self, mode: Literal["fresh", "resume"]) -> None:
        """Fail closed when the operator's requested start semantics are false."""

        if mode not in {"fresh", "resume"}:
            raise ValueError(f"unsupported training start mode: {mode}")
        manifest_path = self.store.root / "manifests" / "run.json"
        if mode == "fresh":
            artifacts = self.formal_training_artifacts()
            if artifacts:
                relative = [str(path.relative_to(self.store.root)) for path in artifacts[:8]]
                raise ExecutionError(
                    f"--fresh requires a run ID with no formal training artifacts; found={relative}"
                )
            # Parsing here makes an accidental warm start fail before any online
            # readiness probe or manifest creation.
            self.initial_skill_library()
            return
        if not manifest_path.is_file():
            raise ExecutionError("--resume requires an existing immutable run manifest")
        halt_path = self.store.root / "manifests" / "training_halted.json"
        if halt_path.exists() or halt_path.is_symlink():
            raise ExecutionError(
                "--resume is forbidden after a decisive prequential training halt; "
                "start a new run_id from the frozen initial library"
            )
        self.verify_run_manifest()

    def active_skills(self) -> list[SkillContract]:
        version = self.registry.current()
        if version is not None:
            self.registry.validate(version, require_current_static_schema=True)
            return load_skill_directory(self.registry.versions / version, active_only=True)
        initial, _ = self.initial_skill_library()
        return initial

    def external_arm_specs(self, active: list[SkillContract]) -> list[dict[str, Any]]:
        """Resolve the frozen no-library control and learned-library treatment."""

        available: dict[str, dict[str, Any]] = {
            "control_no_library": {
                "skills": [],
                "inference_role": "primary_control",
                "knowledge_source": "none",
            },
            "legal_skill_evolve": {
                "skills": active,
                "inference_role": "primary_treatment",
                "knowledge_source": "source_grounded_evolved_prompt_skill_memory",
            },
        }
        configured = self.experiment.get("comparison_arms", [])
        configured_ids = [str(item.get("arm_id")) for item in configured]
        required = list(available)
        if configured_ids != required:
            raise ExecutionError(
                "comparison arm order/coverage differs from the frozen contract: "
                f"expected={required}; actual={configured_ids}"
            )
        specs: list[dict[str, Any]] = []
        for config in configured:
            arm_id = str(config["arm_id"])
            value = {**available[arm_id], **config, "arm_id": arm_id}
            value["intervention_sha256"] = canonical_json_sha256(
                {
                    "arm_id": arm_id,
                    "skills": [item.model_dump(mode="json") for item in value["skills"]],
                    "delivery": "single_global_playbook_prompt_memory",
                    "selection_contract": value.get("selection_contract"),
                }
            )
            specs.append(value)
        return specs

    def _runner(self, *, paired: bool, cache_namespace: str) -> TrajectoryRunner:
        # Block-level empty-library shadows and final paired arms may evaluate an
        # identical library on the same case/persona/seed cells. Keep those exact
        # request replays shared inside this run: ReplayCachedChatClient
        # hashes the complete model/messages/generation payload, so a changed
        # case, prompt, skill memory, seed, schema, or decoding setting is a miss.
        # The run-scoped root deliberately prevents artifacts from a different
        # formal run being imported as evidence. ``cache_namespace`` remains a
        # call-site label for runner construction; it is deliberately not a cache
        # salt that forces byte-identical requests to run again.
        replay_cache_root = (
            self.store.root
            / "cache"
            / "paired_exact_requests"
            / safe_component(self.local_revision)
        )
        client_cache_root = (
            self.store.root
            / "cache"
            / "client_selector_exact_requests"
            / safe_component(self.client_selector_revision)
        )
        disclosure_cache_root = (
            self.store.root
            / "cache"
            / "client_disclosure_exact_requests"
            / safe_component(self.local_revision)
        )
        # Exact request replay is also required inside formal training.  Ordinary
        # TF-GRPO samples retain independent sampling seeds, while an embedded
        # candidate control/treatment intentionally shares stream zero.  Keeping
        # this concern independent from ``paired`` preserves training temperature
        # while making the candidate the sole intervention in its paired estimate.
        policy: Any = ReplayCachedChatClient(
            self.local_client,
            replay_cache_root / "lawyer_policy",
        )
        # Exact replay makes identical client and memo requests common-random-number
        # controls without forcing the lawyer onto a program-selected target.
        selector: Any = ReplayCachedChatClient(
            self.client_selector_client,
            client_cache_root,
        )
        disclosure_classifier: Any = ReplayCachedChatClient(
            self.client_disclosure_client,
            disclosure_cache_root,
        )
        memo_local: Any = ReplayCachedChatClient(
            self.local_client,
            replay_cache_root / "memo_renderer",
        )
        lawyer = self.roles["roles"]["lawyer_policy"]
        opening_agenda = self.roles["roles"]["opening_inquiry_agenda"]
        client = self.roles["roles"]["client_fact_selector"]
        memo = self.roles["roles"]["memo_renderer"]
        policy_temperature = (
            float(lawyer["paired_evaluation_temperature"])
            if paired
            else float(lawyer["training_temperature"])
        )
        return TrajectoryRunner(
            policy_client=policy,
            opening_agenda_client=policy,
            client_selector=selector,
            client_disclosure_classifier=disclosure_classifier,
            memo_client=memo_local,
            policy_prompt_path=self.root / "configs/prompts/consultation_policy_zh.txt",
            opening_agenda_prompt_path=(
                self.root / "configs/prompts/opening_inquiry_agenda_zh.txt"
            ),
            client_prompt_path=self.root / "configs/prompts/client_fact_selector_zh.txt",
            client_disclosure_prompt_path=(
                self.root / "configs/prompts/client_fact_disclosure_zh.txt"
            ),
            memo_prompt_path=self.root / "configs/prompts/memo_writer_zh.txt",
            policy_generation=GenerationConfig(
                temperature=policy_temperature,
                top_p=float(lawyer["top_p"]),
                max_tokens=int(lawyer["max_tokens"]),
                seed=42,
            ),
            opening_agenda_generation=GenerationConfig(
                temperature=float(opening_agenda["temperature"]),
                top_p=float(opening_agenda["top_p"]),
                max_tokens=int(opening_agenda["max_tokens"]),
                seed=42,
                disable_thinking=True,
            ),
            client_generation=GenerationConfig(
                temperature=float(client["temperature"]),
                top_p=1.0,
                max_tokens=int(client["max_tokens"]),
                seed=42,
                reasoning_effort=client.get("reasoning_effort"),
            ),
            memo_generation=GenerationConfig(
                temperature=float(memo["temperature"]),
                top_p=1.0,
                max_tokens=int(memo["max_tokens"]),
                seed=42,
            ),
            model_revision=self.local_revision,
            max_policy_attempts=int(self.experiment["execution"]["policy_repair_attempts"]),
            max_opening_agenda_attempts=int(
                opening_agenda["max_attempts"]
            ),
            max_client_selection_attempts=int(
                self.experiment["execution"]["client_selection_attempts"]
            ),
            max_memo_attempts=int(self.experiment["execution"]["memo_generation_attempts"]),
            shuffle_equal_criticality_fact_presentation=(
                not paired
                and bool(
                    self.experiment["trajectory_sampling"].get(
                        "shuffle_equal_criticality_fact_presentation", False
                    )
                )
            ),
        )

    def generate_training_round(
        self,
        round_index: int,
        *,
        case_limit: int | None = None,
        input_skills: list[SkillContract] | None = None,
    ) -> list[ResearchTrajectory]:
        if not 1 <= round_index <= len(self.training_plan.batches):
            raise ValueError(f"training batch index out of range: {round_index}")
        declared_batch = self.training_plan.batches[round_index - 1]
        partition = declared_batch.batch_id
        case_ids = list(declared_batch.case_ids)
        if case_limit is not None:
            case_ids = case_ids[:case_limit]
        # The exact batch-start library belongs to the block checkpoint, not to
        # whatever registry pointer happens to be current after a crash.  Skills
        # learned from this block are committed only after all K=4 trajectories
        # and their learning-curve point have been frozen.
        skills = list(input_skills) if input_skills is not None else self.active_skills()
        group_size = int(self.experiment["trajectory_sampling"]["group_size"])
        active_hash = skill_library_sha256(skills)
        runner = self._runner(paired=False, cache_namespace=partition)
        requests: list[tuple[Any, ...]] = []
        for case_id in case_ids:
            persona_id = declared_batch.persona_assignment[case_id]
            persona = self.main_adapter.persona(persona_id)
            for seed in self.experiment["trajectory_sampling"]["training_group_seeds"]:
                group_id = f"{partition}.{case_id}.{persona_id}.seed_{seed}"
                for sample_index in range(group_size):
                    method = "training_policy_sample"
                    identity = trajectory_identity(
                        run_id=self.run_id,
                        partition=partition,
                        method=method,
                        case_id=case_id,
                        persona=persona_id,
                        seed=int(seed),
                        sample_index=sample_index,
                        skill_library_version=active_hash,
                    )
                    requests.append(
                        (
                            case_id,
                            persona,
                            int(seed),
                            sample_index,
                            group_id,
                            identity,
                            method,
                            skills,
                            active_hash,
                        )
                    )

        def run_one(request: tuple[Any, ...]) -> ResearchTrajectory:
            (
                case_id,
                persona,
                seed,
                sample_index,
                group_id,
                identity,
                method,
                arm_skills,
                arm_hash,
            ) = request
            return self._load_or_run(
                runner=runner,
                adapter=self.main_adapter,
                case_id=case_id,
                persona=persona,
                skills=arm_skills,
                trajectory_id=identity,
                method=method,
                partition=partition,
                seed=seed,
                sample_index=sample_index,
                group_id=group_id,
                skill_hash=arm_hash,
            )

        values = parallel_map_ordered(
            requests,
            run_one,
            max_workers=int(self.experiment["execution"]["rollout_workers"]),
            label=f"{partition}_rollout",
            fail_fast=True,
        )
        failures = [value.trajectory_id for value in values if value.status == "error"]
        if failures:
            raise ExecutionError(f"training round has {len(failures)} failed units: {failures[:5]}")
        return values

    @staticmethod
    def _training_skill_memory_contract(
        input_skills: list[SkillContract],
    ) -> dict[str, list[SkillContract]]:
        """Return the one batch-start prompt library allowed in every K=4 arm."""

        return {skill_library_sha256(input_skills): list(input_skills)}

    def _learning_curve_current_trajectories(
        self,
        *,
        round_index: int,
        trajectories: list[ResearchTrajectory],
        input_skill_library_sha256: str,
    ) -> list[ResearchTrajectory]:
        """Select the predeclared sample-0 current-library cell from the K=4 matrix."""

        batch = self.training_plan.batches[round_index - 1]
        available_case_ids = {item.case_id for item in trajectories}
        sentinel_case_ids = [
            case_id
            for case_id in self.learning_curve_sentinels[batch.batch_id]
            if case_id in available_case_ids
        ]
        if not sentinel_case_ids:
            raise ExecutionError(f"learning-curve sentinel has no generated case: {batch.batch_id}")
        seeds = [
            int(item) for item in self.experiment["trajectory_sampling"]["training_group_seeds"]
        ]
        selected: list[ResearchTrajectory] = []
        for case_id in sentinel_case_ids:
            for seed in seeds:
                matches = [
                    item
                    for item in trajectories
                    if item.case_id == case_id
                    and item.seed == seed
                    and item.sample_index == 0
                    and item.skill_library_version == input_skill_library_sha256
                    and item.method == "training_policy_sample"
                ]
                if len(matches) != 1:
                    raise ExecutionError(
                        "learning-curve current cell is not unique: "
                        f"batch={batch.batch_id}; case={case_id}; seed={seed}; "
                        f"matches={len(matches)}"
                    )
                selected.append(matches[0])
        return selected

    def _previous_block_skill_increment(
        self,
        *,
        round_index: int,
        input_version: str,
        input_skills: list[SkillContract],
    ) -> dict[str, Any] | None:
        """Resolve the exact created-or-updated document increment from the prior block.

        An increment is measured on its first unseen block.  The preceding block
        checkpoint, immutable registry manifest, document hashes and every
        unchanged parent document must agree.  Stable same-ID updates are part of
        the increment; otherwise the run cannot guess a comparator after outcomes
        exist.
        """

        if round_index == 1:
            return None
        previous_batch = self.training_plan.batches[round_index - 2]
        previous_path = (
            self.store.root
            / "manifests"
            / f"{self._direct_block_manifest_name(previous_batch.batch_id)}.json"
        )
        try:
            previous = self.store.read_manifest(
                self._direct_block_manifest_name(previous_batch.batch_id)
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise ExecutionError(
                "parent-increment diagnostic requires the preceding block checkpoint"
            ) from exc
        input_ids = sorted(skill.skill_id for skill in input_skills)
        input_hash = skill_library_sha256(input_skills)
        if (
            previous.get("round") != round_index - 1
            or previous.get("batch_id") != previous_batch.batch_id
            or previous.get("output_active_skill_ids") != input_ids
            or previous.get("output_skill_library_version") != input_version
            or previous.get("output_skill_library_sha256") != input_hash
        ):
            raise ExecutionError("preceding block does not bind the current input library")
        if previous.get("stage") == LEGACY_COHORT_REJECTION_BLOCK_STAGE:
            raise ExecutionError(
                "legacy rejected-cohort predecessor cannot enter direct accumulation"
            )
        cohort_ids = sorted(str(item) for item in previous.get("admitted_skill_ids") or [])
        if not cohort_ids:
            if (
                previous.get("input_active_skill_ids") != input_ids
                or previous.get("input_skill_library_version") != input_version
                or previous.get("input_skill_library_sha256") != input_hash
            ):
                raise ExecutionError("empty preceding increment changed the library identity")
            return None

        parent_version = str(previous.get("input_skill_library_version") or "")
        parent_ids = [str(item) for item in previous.get("input_active_skill_ids") or []]
        parent_hash = str(previous.get("input_skill_library_sha256") or "")
        parent_skills = self._skills_for_library_version(parent_version)
        if (
            sorted(skill.skill_id for skill in parent_skills) != parent_ids
            or skill_library_sha256(parent_skills) != parent_hash
        ):
            raise ExecutionError("preceding block exact parent library bytes drifted")
        current_by_id = {skill.skill_id: skill for skill in input_skills}
        parent_by_id = {skill.skill_id: skill for skill in parent_skills}
        changed_or_created = {
            skill_id
            for skill_id, current_skill in current_by_id.items()
            if skill_id not in parent_by_id
            or skill_contract_definition_sha256(current_skill)
            != skill_contract_definition_sha256(parent_by_id[skill_id])
        }
        if changed_or_created != set(cohort_ids):
            raise ExecutionError(
                "preceding published playbook increment differs from created/updated documents"
            )
        removed_parent = sorted(set(parent_by_id) - set(current_by_id))
        if removed_parent:
            raise ExecutionError(f"current library removed the parent playbook: {removed_parent}")
        if input_version == FORMAL_INITIAL_SKILL_LIBRARY_ID:
            raise ExecutionError("a non-empty accumulated increment lacks a registry version")
        registry_manifest = self.registry.validate(
            input_version, require_current_static_schema=True
        )
        evidence = registry_manifest.get("evidence")
        if (
            registry_manifest.get("parent_version") != parent_version
            or not isinstance(evidence, dict)
            or evidence.get("source_round") != round_index - 1
            or sorted(str(item) for item in evidence.get("admitted_skill_ids") or []) != cohort_ids
            or evidence.get("admission_report_sha256")
            != previous["skill_admission_artifact"]["sha256"]
        ):
            raise ExecutionError("accumulated registry lineage does not bind its exact parent")
        return {
            "source_round": round_index - 1,
            "source_batch_id": previous_batch.batch_id,
            "source_block_artifact": self._relative_artifact_record(previous_path),
            "cohort_skill_ids": cohort_ids,
            "parent_version": parent_version,
            "parent_skill_ids": parent_ids,
            "parent_skill_library_sha256": parent_hash,
            "parent_skills": parent_skills,
        }

    def generate_parent_cohort_shadow(
        self,
        *,
        round_index: int,
        current_trajectories: list[ResearchTrajectory],
        parent_skills: list[SkillContract],
    ) -> list[ResearchTrajectory]:
        """Run the exact parent library on the cohort's first unseen block cells."""

        if not current_trajectories:
            raise ExecutionError("parent-cohort shadow requires current trajectories")
        batch = self.training_plan.batches[round_index - 1]
        partition = f"{PARENT_COHORT_SHADOW_PREFIX}{batch.batch_id}"
        parent_hash = skill_library_sha256(parent_skills)
        runner = self._runner(paired=False, cache_namespace=partition)
        requests: list[tuple[ResearchTrajectory, str]] = []
        for current in current_trajectories:
            identity = trajectory_identity(
                run_id=self.run_id,
                partition=partition,
                method=current.method,
                case_id=current.case_id,
                persona=current.persona,
                seed=current.seed,
                sample_index=current.sample_index,
                skill_library_version=parent_hash,
            )
            requests.append((current, identity))

        def run_one(request: tuple[ResearchTrajectory, str]) -> ResearchTrajectory:
            current, identity = request
            return self._load_or_run(
                runner=runner,
                adapter=self.main_adapter,
                case_id=current.case_id,
                persona=self.main_adapter.persona(current.persona),
                skills=parent_skills,
                trajectory_id=identity,
                method=current.method,
                partition=partition,
                seed=current.seed,
                sample_index=current.sample_index,
                group_id=current.group_id,
                skill_hash=parent_hash,
            )

        values = parallel_map_ordered(
            requests,
            run_one,
            max_workers=int(self.experiment["execution"]["rollout_workers"]),
            label=f"{partition}_rollout",
            fail_fast=True,
        )
        failures = [item.trajectory_id for item in values if item.status == "error"]
        if failures:
            raise ExecutionError(
                f"parent-cohort shadow has {len(failures)} failed units: {failures[:5]}"
            )
        expected_paths = {
            self.store.trajectory_path(partition, item.trajectory_id).resolve() for item in values
        }
        actual_paths = {
            path.resolve()
            for path in (self.store.root / "trajectories" / partition).glob("*.json")
            if path.is_file()
        }
        if actual_paths != expected_paths:
            raise ExecutionError("parent-cohort shadow directory contains a stale matrix")
        return values

    def generate_learning_curve_shadow(
        self,
        *,
        round_index: int,
        current_trajectories: list[ResearchTrajectory],
    ) -> list[ResearchTrajectory]:
        """Generate only the empty-library half of a fixed prequential sentinel."""

        if not current_trajectories:
            raise ExecutionError("learning-curve shadow requires current trajectories")
        batch = self.training_plan.batches[round_index - 1]
        partition = f"learning_curve_shadow_{batch.batch_id}"
        empty_hash = skill_library_sha256([])
        runner = self._runner(paired=False, cache_namespace=partition)
        requests: list[tuple[ResearchTrajectory, str]] = []
        for current in current_trajectories:
            identity = trajectory_identity(
                run_id=self.run_id,
                partition=partition,
                method=current.method,
                case_id=current.case_id,
                persona=current.persona,
                seed=current.seed,
                sample_index=current.sample_index,
                skill_library_version=empty_hash,
            )
            requests.append((current, identity))

        def run_one(request: tuple[ResearchTrajectory, str]) -> ResearchTrajectory:
            current, identity = request
            return self._load_or_run(
                runner=runner,
                adapter=self.main_adapter,
                case_id=current.case_id,
                persona=self.main_adapter.persona(current.persona),
                skills=[],
                trajectory_id=identity,
                method=current.method,
                partition=partition,
                seed=current.seed,
                sample_index=current.sample_index,
                # Keep the normal K=4 group identity so the pair is matched to
                # the exact policy stream; the separate partition owns storage.
                group_id=current.group_id,
                skill_hash=empty_hash,
            )

        values = parallel_map_ordered(
            requests,
            run_one,
            max_workers=int(self.experiment["execution"]["rollout_workers"]),
            label=f"{partition}_rollout",
            fail_fast=True,
        )
        failures = [item.trajectory_id for item in values if item.status == "error"]
        if failures:
            raise ExecutionError(
                f"learning-curve shadow has {len(failures)} failed units: {failures[:5]}"
            )
        expected_paths = {
            self.store.trajectory_path(partition, item.trajectory_id).resolve() for item in values
        }
        actual_paths = {
            path.resolve()
            for path in (self.store.root / "trajectories" / partition).glob("*.json")
            if path.is_file()
        }
        if actual_paths != expected_paths:
            raise ExecutionError("learning-curve shadow directory contains a stale matrix")
        return values

    def _learning_curve_point_path(self, round_index: int) -> Path:
        return self.store.root / "reports" / f"development_curve_point_{round_index:02d}.json"

    def _library_effect_disposition_path(self, round_index: int) -> Path:
        return self.store.root / "reports" / f"library_effect_disposition_{round_index:02d}.json"

    def _final_training_holdout_arms_path(self) -> Path:
        return self.store.root / "reports" / "final_training_holdout_arms_frozen.json"

    def _final_training_holdout_report_path(self) -> Path:
        return self.store.root / "reports" / "final_training_holdout.json"

    def _final_training_holdout_disposition_path(self) -> Path:
        return self.store.root / "reports" / "final_training_holdout_disposition.json"

    def _final_training_holdout_isolation_path(self) -> Path:
        return self.store.root / "health" / "final_training_holdout_intervention_isolation.json"

    def _freeze_final_training_holdout_arms(
        self,
        *,
        round_index: int,
        case_limit: int | None,
        run_manifest_sha256: str,
        input_version: str,
        input_skills: list[SkillContract],
        current: list[ResearchTrajectory],
        current_evaluations: Mapping[str, TrajectoryEvaluation],
        empty: list[ResearchTrajectory],
        empty_evaluations: Mapping[str, TrajectoryEvaluation],
        parent_context: Mapping[str, Any] | None,
        parent: list[ResearchTrajectory] | None,
        parent_evaluations: Mapping[str, TrajectoryEvaluation] | None,
    ) -> dict[str, Any]:
        """Freeze every B8 arm before any cohort outcome disposition exists."""

        if round_index != len(self.training_plan.batches):
            raise ExecutionError("final training holdout arms may only be frozen on B8")
        batch = self.training_plan.batches[round_index - 1]
        input_ids = sorted(skill.skill_id for skill in input_skills)
        input_hash = skill_library_sha256(input_skills)
        empty_hash = skill_library_sha256([])
        empty_partition = f"learning_curve_shadow_{batch.batch_id}"

        def arm_record(
            *,
            name: str,
            partition: str,
            registry_version: str | None,
            skills: list[SkillContract],
            trajectories: list[ResearchTrajectory],
            evaluations: Mapping[str, TrajectoryEvaluation],
        ) -> dict[str, Any]:
            trajectory_ids = sorted(item.trajectory_id for item in trajectories)
            if set(trajectory_ids) != set(evaluations):
                raise ExecutionError(f"final holdout {name} evaluation matrix is incomplete")
            return {
                "arm_name": name,
                "partition": partition,
                "registry_version": registry_version,
                "active_skill_ids": sorted(skill.skill_id for skill in skills),
                "skill_library_sha256": skill_library_sha256(skills),
                "trajectory_artifacts": {
                    trajectory_id: self._relative_artifact_record(
                        self.store.trajectory_path(partition, trajectory_id)
                    )
                    for trajectory_id in trajectory_ids
                },
                "evaluation_artifacts": {
                    trajectory_id: self._relative_artifact_record(
                        self.store.evaluation_path(trajectory_id)
                    )
                    for trajectory_id in trajectory_ids
                },
            }

        if (parent_context is None) != (parent is None):
            raise ExecutionError("final holdout exact-parent arm presence drift")
        if (parent is None) != (parent_evaluations is None):
            raise ExecutionError("final holdout exact-parent evaluation presence drift")
        current_arm = arm_record(
            name="current_B8",
            partition=batch.batch_id,
            registry_version=input_version,
            skills=input_skills,
            trajectories=current,
            evaluations=current_evaluations,
        )
        empty_arm = arm_record(
            name="empty_B8_shadow",
            partition=empty_partition,
            registry_version=None,
            skills=[],
            trajectories=empty,
            evaluations=empty_evaluations,
        )
        parent_arm = None
        if parent_context is not None and parent is not None and parent_evaluations is not None:
            parent_skills = list(parent_context["parent_skills"])
            parent_arm = arm_record(
                name="exact_parent_B8_shadow",
                partition=f"{PARENT_COHORT_SHADOW_PREFIX}{batch.batch_id}",
                registry_version=str(parent_context["parent_version"]),
                skills=parent_skills,
                trajectories=parent,
                evaluations=parent_evaluations,
            )
        deterministic = {
            "schema_version": FINAL_TRAINING_HOLDOUT_ARMS_SCHEMA,
            "run_id": self.run_id,
            "run_manifest_sha256": run_manifest_sha256,
            "round": round_index,
            "batch_id": batch.batch_id,
            "case_limit": case_limit,
            "status": "all_B8_comparison_arms_frozen_before_increment_diagnostic",
            "scope": FINAL_TRAINING_HOLDOUT_SCOPE,
            "claim_role": ("cumulative_library_diagnostic_not_independent_confirmatory_claim"),
            "arm_freeze_timing": "before_B8_increment_diagnostic",
            "library_effect_disposition_absent_at_initial_freeze": True,
            "has_new_skill_increment": parent_context is not None,
            "comparison_arm_names": [
                "current_B8",
                *(["exact_parent_B8_shadow"] if parent_context is not None else []),
                "empty_B8_shadow",
            ],
            "current_arm": current_arm,
            "parent_arm": parent_arm,
            "empty_arm": empty_arm,
            "input_active_skill_ids": input_ids,
            "input_skill_library_version": input_version,
            "input_skill_library_sha256": input_hash,
            "empty_skill_library_sha256": empty_hash,
        }
        path = self._final_training_holdout_arms_path()
        if path.is_file():
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ExecutionError("final training holdout arm freeze is unreadable") from exc
            if (
                not isinstance(value, dict)
                or {key: item for key, item in value.items() if key != "completed_at"}
                != deterministic
                or not value.get("completed_at")
            ):
                raise ExecutionError("final training holdout arm freeze drifted")
            return value
        if self._library_effect_disposition_path(round_index).exists():
            raise ExecutionError(
                "B8 cohort disposition predates the mandatory all-arm freeze; "
                "same run cannot recover without selective-execution ambiguity"
            )
        value = {**deterministic, "completed_at": datetime.now(UTC).isoformat()}
        self.store.immutable_json(path, value)
        return value

    def _load_frozen_final_training_holdout_arms(
        self,
        *,
        run_manifest_sha256: str,
        case_limit: int | None,
    ) -> tuple[
        dict[str, Any],
        dict[str, tuple[list[ResearchTrajectory], dict[str, TrajectoryEvaluation]]],
    ]:
        """Validate the immutable B8 arm matrix and load its scored artifacts."""

        rounds = len(self.training_plan.batches)
        batch = self.training_plan.batches[-1]
        path = self._final_training_holdout_arms_path()
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ExecutionError("final training holdout arm freeze is missing") from exc
        expected_fields = {
            "schema_version",
            "run_id",
            "run_manifest_sha256",
            "round",
            "batch_id",
            "case_limit",
            "status",
            "scope",
            "claim_role",
            "arm_freeze_timing",
            "library_effect_disposition_absent_at_initial_freeze",
            "has_new_skill_increment",
            "comparison_arm_names",
            "current_arm",
            "parent_arm",
            "empty_arm",
            "input_active_skill_ids",
            "input_skill_library_version",
            "input_skill_library_sha256",
            "empty_skill_library_sha256",
            "completed_at",
        }
        if not isinstance(value, dict) or set(value) != expected_fields:
            raise ExecutionError("final training holdout arm freeze fields drifted")
        bindings = {
            "schema_version": FINAL_TRAINING_HOLDOUT_ARMS_SCHEMA,
            "run_id": self.run_id,
            "run_manifest_sha256": run_manifest_sha256,
            "round": rounds,
            "batch_id": batch.batch_id,
            "case_limit": case_limit,
            "status": "all_B8_comparison_arms_frozen_before_increment_diagnostic",
            "scope": FINAL_TRAINING_HOLDOUT_SCOPE,
            "claim_role": ("cumulative_library_diagnostic_not_independent_confirmatory_claim"),
            "arm_freeze_timing": "before_B8_increment_diagnostic",
            "library_effect_disposition_absent_at_initial_freeze": True,
            "empty_skill_library_sha256": skill_library_sha256([]),
        }
        drift = [key for key, expected in bindings.items() if value.get(key) != expected]
        if drift or not value.get("completed_at"):
            raise ExecutionError(f"final training holdout arm freeze binding drift: {drift}")
        pending = value.get("has_new_skill_increment")
        if not isinstance(pending, bool):
            raise ExecutionError("final training holdout pending-cohort flag is invalid")
        expected_names = [
            "current_B8",
            *(["exact_parent_B8_shadow"] if pending else []),
            "empty_B8_shadow",
        ]
        if value.get("comparison_arm_names") != expected_names or (
            (value.get("parent_arm") is not None) != pending
        ):
            raise ExecutionError("final training holdout potential arm set drifted")

        sentinel_case_ids = [
            case_id
            for case_id in self.learning_curve_sentinels[batch.batch_id]
            if case_limit is None or case_id in set(list(batch.case_ids)[:case_limit])
        ]
        expected_pairs = len(sentinel_case_ids) * len(
            self.experiment["trajectory_sampling"]["training_group_seeds"]
        )
        loaded: dict[str, tuple[list[ResearchTrajectory], dict[str, TrajectoryEvaluation]]] = {}

        def load_arm(
            field: str,
            *,
            expected_name: str,
            expected_partition: str,
            expected_registry_version: str | None,
            expected_skills: list[SkillContract],
        ) -> None:
            arm = value.get(field)
            required = {
                "arm_name",
                "partition",
                "registry_version",
                "active_skill_ids",
                "skill_library_sha256",
                "trajectory_artifacts",
                "evaluation_artifacts",
            }
            if not isinstance(arm, dict) or set(arm) != required:
                raise ExecutionError(f"final training holdout {field} fields drifted")
            expected_ids = sorted(skill.skill_id for skill in expected_skills)
            expected_hash = skill_library_sha256(expected_skills)
            if (
                arm.get("arm_name") != expected_name
                or arm.get("partition") != expected_partition
                or arm.get("registry_version") != expected_registry_version
                or arm.get("active_skill_ids") != expected_ids
                or arm.get("skill_library_sha256") != expected_hash
            ):
                raise ExecutionError(f"final training holdout {field} identity drifted")
            trajectory_records = arm.get("trajectory_artifacts")
            evaluation_records = arm.get("evaluation_artifacts")
            if (
                not isinstance(trajectory_records, dict)
                or not isinstance(evaluation_records, dict)
                or set(trajectory_records) != set(evaluation_records)
                or len(trajectory_records) != expected_pairs
            ):
                raise ExecutionError(f"final training holdout {field} matrix drifted")
            trajectories: list[ResearchTrajectory] = []
            evaluations: dict[str, TrajectoryEvaluation] = {}
            for trajectory_id in sorted(trajectory_records):
                trajectory_path = self._verify_artifact_record(
                    trajectory_records[trajectory_id],
                    expected_path=self.store.trajectory_path(expected_partition, trajectory_id),
                    label=f"final training holdout {field} trajectory",
                )
                evaluation_path = self._verify_artifact_record(
                    evaluation_records[trajectory_id],
                    expected_path=self.store.evaluation_path(trajectory_id),
                    label=f"final training holdout {field} evaluation",
                )
                trajectory = self.store.load_model(trajectory_path, ResearchTrajectory)
                evaluation = self.store.load_model(evaluation_path, TrajectoryEvaluation)
                if (
                    trajectory.trajectory_id != trajectory_id
                    or trajectory.partition != expected_partition
                    or trajectory.skill_library_version != expected_hash
                    or evaluation.trajectory_id != trajectory_id
                    or evaluation.case_id != trajectory.case_id
                ):
                    raise ExecutionError(f"final training holdout {field} artifact binding drift")
                trajectories.append(trajectory)
                evaluations[trajectory_id] = evaluation
            keys = {
                (item.case_id, item.persona, item.seed, item.sample_index) for item in trajectories
            }
            expected_keys = {
                (case_id, batch.persona_assignment[case_id], int(seed), 0)
                for case_id in sentinel_case_ids
                for seed in self.experiment["trajectory_sampling"]["training_group_seeds"]
            }
            if keys != expected_keys:
                raise ExecutionError(f"final training holdout {field} cells drifted")
            loaded[field] = (trajectories, evaluations)

        input_version = str(value.get("input_skill_library_version") or "")
        input_skills = self._skills_for_library_version(input_version)
        if value.get("input_active_skill_ids") != sorted(
            skill.skill_id for skill in input_skills
        ) or value.get("input_skill_library_sha256") != skill_library_sha256(input_skills):
            raise ExecutionError("final training holdout input library drifted")
        load_arm(
            "current_arm",
            expected_name="current_B8",
            expected_partition=batch.batch_id,
            expected_registry_version=input_version,
            expected_skills=input_skills,
        )
        load_arm(
            "empty_arm",
            expected_name="empty_B8_shadow",
            expected_partition=f"learning_curve_shadow_{batch.batch_id}",
            expected_registry_version=None,
            expected_skills=[],
        )
        if pending:
            context = self._previous_block_skill_increment(
                round_index=rounds,
                input_version=input_version,
                input_skills=input_skills,
            )
            if context is None:
                raise ExecutionError("final training holdout exact-parent lineage drifted")
            load_arm(
                "parent_arm",
                expected_name="exact_parent_B8_shadow",
                expected_partition=f"{PARENT_COHORT_SHADOW_PREFIX}{batch.batch_id}",
                expected_registry_version=str(context["parent_version"]),
                expected_skills=list(context["parent_skills"]),
            )
        return value, loaded

    def _ensure_final_training_holdout_safeguard(
        self,
        *,
        run_manifest_sha256: str,
        case_limit: int | None,
        create_if_missing: bool,
    ) -> dict[str, dict[str, str]]:
        """Recompute and persist the cumulative-library B8 diagnostic."""

        rounds = len(self.training_plan.batches)
        batch = self.training_plan.batches[-1]
        frozen, loaded = self._load_frozen_final_training_holdout_arms(
            run_manifest_sha256=run_manifest_sha256,
            case_limit=case_limit,
        )
        input_version = str(frozen["input_skill_library_version"])
        input_skills = self._skills_for_library_version(input_version)
        curve_point = self._validate_learning_curve_point_artifact(
            round_index=rounds,
            case_limit=case_limit,
            run_manifest_sha256=run_manifest_sha256,
            expected_input_skill_ids=list(frozen["input_active_skill_ids"]),
            expected_input_skill_library_sha256=str(frozen["input_skill_library_sha256"]),
            expected_input_skill_library_version=input_version,
        )
        cohort_disposition = self._load_validated_library_effect_disposition(
            round_index=rounds,
            run_manifest_sha256=run_manifest_sha256,
            input_version=input_version,
            input_skills=input_skills,
            curve_point=curve_point,
            require_continue=False,
        )
        if str(frozen["completed_at"]) > str(cohort_disposition["completed_at"]):
            raise ExecutionError("final B8 arms were not frozen before the increment diagnostic")
        decision = cohort_disposition.get("decision")
        pending = bool(frozen["has_new_skill_increment"])
        if pending:
            if decision != "observe_increment_continue_training":
                raise ExecutionError("final training diagnostic increment decision drifted")
            selected_field = "current_arm"
            selection_source = "B7_increment_retained_by_direct_accumulation"
        else:
            if decision != "continue_training_no_pending_cohort":
                raise ExecutionError("final training holdout identity decision drifted")
            selected_field = "current_arm"
            selection_source = "current_library_without_B7_increment"
        selected_arm = frozen[selected_field]
        empty_arm = frozen["empty_arm"]
        if not isinstance(selected_arm, Mapping) or not isinstance(empty_arm, Mapping):
            raise ExecutionError("final training holdout selected arm metadata is invalid")
        selected_version = str(selected_arm["registry_version"])
        selected_skills = self._skills_for_library_version(selected_version)
        selected_ids = sorted(skill.skill_id for skill in selected_skills)
        selected_hash = skill_library_sha256(selected_skills)
        if (
            selected_arm.get("active_skill_ids") != selected_ids
            or selected_arm.get("skill_library_sha256") != selected_hash
        ):
            raise ExecutionError("final training holdout selected library bytes drifted")
        active = self.active_skills()
        active_version = self.registry.current() or FORMAL_INITIAL_SKILL_LIBRARY_ID
        if (
            active_version != selected_version
            or sorted(skill.skill_id for skill in active) != selected_ids
            or skill_library_sha256(active) != selected_hash
        ):
            raise ExecutionError("active registry does not match the mechanically selected B8 arm")

        selected_trajectories, selected_evaluations = loaded[selected_field]
        empty_trajectories, empty_evaluations = loaded["empty_arm"]
        selected_partition = str(selected_arm["partition"])
        empty_partition = str(empty_arm["partition"])
        isolation = final_training_holdout_intervention_isolation_report(
            selected_trajectories,
            empty_trajectories,
            set(selected_ids),
            selected_partition,
            empty_partition,
        )
        isolation_path = self._final_training_holdout_isolation_path()
        if isolation_path.is_file():
            persisted_isolation = json.loads(isolation_path.read_text(encoding="utf-8"))
            if canonical_json_sha256(persisted_isolation) != canonical_json_sha256(isolation):
                raise ExecutionError("final training holdout isolation artifact drifted")
        elif create_if_missing:
            self.store.immutable_json(isolation_path, isolation)
        else:
            raise ExecutionError("final training holdout isolation artifact is missing")

        empty_hash = skill_library_sha256([])
        if selected_ids:
            curve = build_prequential_sentinel_report(
                sentinel_id=f"{batch.batch_id}.final_training_holdout",
                current_trajectories=selected_trajectories,
                current_evaluations=selected_evaluations,
                current_partition=selected_partition,
                current_library_version=selected_hash,
                current_skill_ids=set(selected_ids),
                empty_partition=empty_partition,
                empty_library_version=empty_hash,
                empty_trajectories=empty_trajectories,
                empty_evaluations=empty_evaluations,
                identity_baseline=False,
                bootstrap_samples=int(self.experiment["learning_curve"]["bootstrap_samples"]),
                confidence_level=float(self.experiment["learning_curve"]["confidence_level"]),
                bootstrap_seed=int(self.experiment["learning_curve"]["bootstrap_seed"]),
            )
        else:
            curve = build_prequential_sentinel_report(
                sentinel_id=f"{batch.batch_id}.final_training_holdout",
                current_trajectories=selected_trajectories,
                current_evaluations=selected_evaluations,
                current_partition=selected_partition,
                current_library_version=empty_hash,
                current_skill_ids=set(),
                empty_partition=selected_partition,
                empty_library_version=empty_hash,
                identity_baseline=True,
                bootstrap_samples=int(self.experiment["learning_curve"]["bootstrap_samples"]),
                confidence_level=float(self.experiment["learning_curve"]["confidence_level"]),
                bootstrap_seed=int(self.experiment["learning_curve"]["bootstrap_seed"]),
            )
        curve["initial_infrastructure_identity"]["stepwise_intervention_isolation"] = (
            "passed_by_bound_final_training_holdout_isolation_artifact"
            if isolation.get("passed") is True
            else "failed_by_bound_final_training_holdout_isolation_artifact"
        )
        arms_path = self._final_training_holdout_arms_path()
        cohort_disposition_path = self._library_effect_disposition_path(rounds)
        isolation_record = self._relative_artifact_record(isolation_path)
        deterministic_report = {
            "schema_version": FINAL_TRAINING_HOLDOUT_REPORT_SCHEMA,
            "run_id": self.run_id,
            "run_manifest_sha256": run_manifest_sha256,
            "round": rounds,
            "batch_id": batch.batch_id,
            "case_limit": case_limit,
            "status": "same_B8_selected_library_vs_empty_complete",
            "scope": FINAL_TRAINING_HOLDOUT_SCOPE,
            "claim_role": ("cumulative_library_diagnostic_not_independent_confirmatory_claim"),
            "selection_source": selection_source,
            "increment_diagnostic_decision": decision,
            "all_comparison_arms_frozen_before_increment_diagnostic": True,
            "arms_frozen_artifact": self._relative_artifact_record(arms_path),
            "increment_diagnostic_artifact": self._relative_artifact_record(
                cohort_disposition_path
            ),
            "selected_arm_name": selected_arm["arm_name"],
            "selected_partition": selected_partition,
            "selected_active_skill_ids": selected_ids,
            "selected_skill_library_version": selected_version,
            "selected_skill_library_sha256": selected_hash,
            "empty_partition": empty_partition,
            "empty_skill_library_sha256": empty_hash,
            "intervention_isolation_artifact": isolation_record,
            "curve": curve,
        }
        report_path = self._final_training_holdout_report_path()
        if report_path.is_file():
            report = json.loads(report_path.read_text(encoding="utf-8"))
            if {
                key: item for key, item in report.items() if key != "completed_at"
            } != deterministic_report or not report.get("completed_at"):
                raise ExecutionError("final training holdout report drifted")
        elif create_if_missing:
            report = {
                **deterministic_report,
                "completed_at": datetime.now(UTC).isoformat(),
            }
            self.store.immutable_json(report_path, report)
        else:
            raise ExecutionError("final training holdout report is missing")

        gate_config = self.experiment["learning_curve"].get("final_cumulative_freeze_safeguard")
        if not isinstance(gate_config, Mapping):
            raise ExecutionError("final training holdout safeguard is not configured")
        deterministic_disposition = {
            **final_training_holdout_safeguard_disposition(
                report,
                isolation,
                gate_config=gate_config,
            ),
            "run_id": self.run_id,
            "run_manifest_sha256": run_manifest_sha256,
            "round": rounds,
            "batch_id": batch.batch_id,
            "selected_arm_name": selected_arm["arm_name"],
            "selected_active_skill_ids": selected_ids,
            "selected_skill_library_version": selected_version,
            "selected_skill_library_sha256": selected_hash,
            "arms_frozen_artifact": self._relative_artifact_record(arms_path),
            "increment_diagnostic_artifact": self._relative_artifact_record(
                cohort_disposition_path
            ),
            "final_training_holdout_artifact": self._relative_artifact_record(report_path),
            "intervention_isolation_artifact": isolation_record,
        }
        disposition_path = self._final_training_holdout_disposition_path()
        if disposition_path.is_file():
            final_disposition = json.loads(disposition_path.read_text(encoding="utf-8"))
            if {
                key: item for key, item in final_disposition.items() if key != "completed_at"
            } != deterministic_disposition or not final_disposition.get("completed_at"):
                raise ExecutionError("final training holdout disposition drifted")
        elif create_if_missing:
            final_disposition = {
                **deterministic_disposition,
                "completed_at": datetime.now(UTC).isoformat(),
            }
            self.store.immutable_json(disposition_path, final_disposition)
        else:
            raise ExecutionError("final training holdout disposition is missing")
        if final_disposition.get("training_freeze_allowed") is not True:
            raise ExecutionError(
                "final B8 intervention-isolation safeguard failed before "
                "training_complete, teacher reuse, or external access: "
                f"reasons={final_disposition.get('failure_reasons')}"
            )
        return {
            "arms_frozen": self._relative_artifact_record(arms_path),
            "report": self._relative_artifact_record(report_path),
            "disposition": self._relative_artifact_record(disposition_path),
            "isolation": isolation_record,
        }

    def _expected_library_effect_disposition(
        self,
        *,
        round_index: int,
        run_manifest_sha256: str,
        input_version: str,
        input_skills: list[SkillContract],
        curve_point: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Recompute the deterministic disposition bound to one block input."""

        batch = self.training_plan.batches[round_index - 1]
        point_path = self._learning_curve_point_path(round_index)
        input_ids = sorted(skill.skill_id for skill in input_skills)
        input_hash = skill_library_sha256(input_skills)
        try:
            persisted_curve_point = json.loads(point_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ExecutionError("development curve point is missing or unreadable") from exc
        if not isinstance(persisted_curve_point, dict) or canonical_json_sha256(
            persisted_curve_point
        ) != canonical_json_sha256(dict(curve_point)):
            raise ExecutionError(
                "library-effect disposition curve argument differs from persisted artifact"
            )
        point_schema = curve_point.get("schema_version")
        if (
            point_schema
            not in {
                PARENT_COHORT_CURVE_POINT_SCHEMA,
                CURRENT_LIBRARY_IDENTITY_CURVE_POINT_SCHEMA,
            }
            or curve_point.get("run_id") != self.run_id
            or curve_point.get("run_manifest_sha256") != run_manifest_sha256
            or curve_point.get("round") != round_index
            or curve_point.get("batch_id") != batch.batch_id
            or curve_point.get("input_active_skill_ids") != input_ids
            or curve_point.get("input_skill_library_sha256") != input_hash
        ):
            raise ExecutionError("library-effect disposition curve binding drift")
        curve = curve_point.get("curve")
        if not isinstance(curve, Mapping):
            raise ExecutionError("library-effect disposition lacks a curve")
        if point_schema == CURRENT_LIBRARY_IDENTITY_CURVE_POINT_SCHEMA:
            if (
                curve_point.get("input_skill_library_version") != input_version
                or curve.get("direction") != COHORT_PARENT_EFFECT_DIRECTION
                or curve.get("identity_baseline") is not True
                or curve.get("no_pending_cohort") is not True
                or curve_point.get("new_skill_increment_ids") != []
                or curve_point.get("parent_active_skill_ids") != input_ids
                or curve_point.get("parent_skill_library_version") != input_version
                or curve_point.get("parent_skill_library_sha256") != input_hash
            ):
                raise ExecutionError("retained-library identity disposition binding drift")
            return {
                "schema_version": 3,
                "scope": "no_new_increment_cumulative_library_identity",
                "comparator": "exact_same_current_library",
                "direction": COHORT_PARENT_EFFECT_DIRECTION,
                "bootstrap_unit": "case_id",
                "candidate_level_effect_claim": False,
                "automatic_skill_pruning": False,
                "identity_baseline": True,
                "new_skill_increment_ids": [],
                "parent_active_skill_ids": input_ids,
                "parent_skill_library_version": input_version,
                "parent_skill_library_sha256": input_hash,
                "interval_diagnostic": None,
                "practical_effect_classifier": None,
                "cohort_transition": "no_pending_cohort",
                "diagnostic_flags": [],
                "decision": "continue_training_no_pending_cohort",
                "action": "no_increment_to_compare_continue_to_teacher",
                "run_id": self.run_id,
                "run_manifest_sha256": run_manifest_sha256,
                "round": round_index,
                "batch_id": batch.batch_id,
                "input_active_skill_ids": input_ids,
                "input_skill_library_version": input_version,
                "input_skill_library_sha256": input_hash,
                "development_curve_artifact": self._relative_artifact_record(point_path),
            }
        if curve.get("direction") == COHORT_PARENT_EFFECT_DIRECTION:
            if (
                point_schema != PARENT_COHORT_CURVE_POINT_SCHEMA
                or curve_point.get("input_skill_library_version") != input_version
            ):
                raise ExecutionError("parent-cohort disposition point binding drift")
            validation = self.experiment.get("learning_curve", {}).get(
                "incremental_effect_diagnostic"
            )
            pareto_gate = (
                validation.get("interval_diagnostic") if isinstance(validation, Mapping) else None
            )
            if not isinstance(pareto_gate, Mapping):
                raise ExecutionError("incremental interval diagnostic is not configured")
            interval_diagnostic = cohort_pareto_disposition(
                curve_point,
                gate_config=pareto_gate,
            )
            retention_gate = validation.get("practical_effect_classifier")
            if not isinstance(retention_gate, Mapping):
                raise ExecutionError("incremental practical-effect classifier is missing")
            practical_gate = practical_retention_gate_disposition(
                curve,
                gate_config=retention_gate,
            )
            isolation_record = curve_point.get("intervention_isolation_artifact")
            isolation_path = self._verify_artifact_record(
                isolation_record,
                expected_path=(
                    self.store.root
                    / "health"
                    / f"parent_cohort_intervention_isolation_{batch.batch_id}.json"
                ),
                label="parent-cohort disposition isolation",
            )
            isolation = json.loads(isolation_path.read_text(encoding="utf-8"))
            minimum_exposed = int(validation["minimum_exposed_cases_for_interpretation"])
            exposed_cases = int(isolation.get("cohort_exposed_case_count", -1))
            skill_exposure = isolation.get("cohort_skill_exposure")
            if not isinstance(skill_exposure, Mapping) or set(skill_exposure) != set(
                curve_point["new_skill_increment_ids"]
            ):
                raise ExecutionError("parent-cohort global-playbook exposure audit is missing")
            if len(skill_exposure) != 1:
                raise ExecutionError("formal parent-cohort diagnostic requires one global playbook")
            exposure_failures: dict[str, list[str]] = {}
            for skill_id, raw_exposure in skill_exposure.items():
                if not isinstance(raw_exposure, Mapping):
                    raise ExecutionError("parent-cohort skill exposure row is invalid")
                reasons = [
                    *(
                        ["incomplete_global_playbook_cohort_exposure"]
                        if raw_exposure.get("routing_complete") is not True
                        else []
                    ),
                    *(
                        ["fewer_than_minimum_unique_cases"]
                        if int(raw_exposure.get("observed_case_count", -1)) < minimum_exposed
                        else []
                    ),
                    *(
                        ["fewer_than_minimum_pairs"]
                        if int(raw_exposure.get("observed_pair_count", -1)) < minimum_exposed
                        else []
                    ),
                ]
                if raw_exposure.get("domain") == "general" and (
                    int(raw_exposure.get("expected_case_count", -1))
                    != int(curve.get("case_cluster_count", -2))
                    or int(raw_exposure.get("expected_pair_count", -1))
                    != int(curve.get("pair_count", -2))
                ):
                    reasons.append("global_playbook_not_exposed_to_full_cohort")
                if reasons:
                    exposure_failures[str(skill_id)] = reasons
            global_playbook_exposure = dict(next(iter(skill_exposure.values())))
            global_playbook_exposure_failures = sorted(
                {reason for reasons in exposure_failures.values() for reason in reasons}
            )
            exposure_passed = bool(isolation.get("passed") is True and not exposure_failures)
            advancement_config = validation.get("primary_signal")
            if not isinstance(advancement_config, Mapping):
                raise ExecutionError("incremental primary-signal rule is missing")
            threshold = float(advancement_config["threshold"])
            advancement_estimates: dict[str, float] = {}
            for endpoint in advancement_config["endpoints"]:
                disposition = practical_gate["endpoint_dispositions"].get(endpoint)
                if not isinstance(disposition, Mapping):
                    raise ExecutionError(
                        f"incremental primary-signal endpoint is missing: {endpoint}"
                    )
                advancement_estimates[str(endpoint)] = float(disposition["oriented_mean_delta"])
            advancement_passed = any(value > threshold for value in advancement_estimates.values())
            performance_panel_passed = bool(
                practical_gate["passed"] and exposure_passed and advancement_passed
            )
            diagnostic_flags = [
                *(
                    ["primary_or_protected_endpoint_nonpass"]
                    if not practical_gate["passed"]
                    else []
                ),
                *(["insufficient_exposure"] if not exposure_passed else []),
                *(
                    ["no_advancement"]
                    if practical_gate["passed"] and not advancement_passed
                    else []
                ),
            ]
            return {
                "schema_version": 3,
                "scope": "new_skill_increment_against_exact_parent",
                "comparator": "exact_parent_library",
                "direction": COHORT_PARENT_EFFECT_DIRECTION,
                "bootstrap_unit": "case_id",
                "candidate_level_effect_claim": False,
                "automatic_skill_pruning": False,
                "source_round": curve_point["source_round"],
                "new_skill_increment_ids": curve_point["new_skill_increment_ids"],
                "parent_active_skill_ids": curve_point["parent_active_skill_ids"],
                "parent_skill_library_version": curve_point["parent_skill_library_version"],
                "parent_skill_library_sha256": curve_point["parent_skill_library_sha256"],
                "interval_diagnostic": interval_diagnostic,
                "practical_effect_classifier": practical_gate,
                "diagnostic_checks": {
                    "minimum_exposed_cases_for_interpretation": minimum_exposed,
                    "global_playbook_requires_full_cohort_exposure": validation[
                        "global_playbook_requires_full_cohort_exposure"
                    ],
                    "observed_exposed_case_count": exposed_cases,
                    "global_playbook_exposure": global_playbook_exposure,
                    "global_playbook_exposure_failures": (
                        global_playbook_exposure_failures
                    ),
                    "exposure_passed": exposure_passed,
                    "primary_signal_decision_rule": advancement_config["decision_rule"],
                    "primary_signal_endpoints": list(advancement_config["endpoints"]),
                    "primary_signal_threshold": threshold,
                    "primary_signal_oriented_mean_deltas": advancement_estimates,
                    "primary_signal_positive": advancement_passed,
                },
                "performance_panel_passed": performance_panel_passed,
                "cohort_transition": "retain_increment_for_cross_block_evolution",
                "diagnostic_flags": diagnostic_flags,
                "decision": "observe_increment_continue_training",
                "action": "report_increment_and_continue_to_teacher_without_rollback",
                "run_id": self.run_id,
                "run_manifest_sha256": run_manifest_sha256,
                "round": round_index,
                "batch_id": batch.batch_id,
                "input_active_skill_ids": input_ids,
                "input_skill_library_version": input_version,
                "input_skill_library_sha256": input_hash,
                "development_curve_artifact": self._relative_artifact_record(point_path),
            }
        raise ExecutionError(
            "development curve point is not a current exact-parent or retained-identity artifact"
        )

    def _load_validated_library_effect_disposition(
        self,
        *,
        round_index: int,
        run_manifest_sha256: str,
        input_version: str,
        input_skills: list[SkillContract],
        curve_point: Mapping[str, Any],
        require_continue: bool,
    ) -> dict[str, Any]:
        """Require an immutable disposition to equal its pure curve derivation."""

        deterministic = self._expected_library_effect_disposition(
            round_index=round_index,
            run_manifest_sha256=run_manifest_sha256,
            input_version=input_version,
            input_skills=input_skills,
            curve_point=curve_point,
        )
        path = self._library_effect_disposition_path(round_index)
        if not path.is_file():
            raise ExecutionError("library-effect disposition artifact is missing")
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ExecutionError("library-effect disposition artifact is unreadable") from exc
        if not isinstance(value, dict):
            raise ExecutionError("library-effect disposition artifact must be an object")
        prior_deterministic = {key: item for key, item in value.items() if key != "completed_at"}
        if (
            prior_deterministic != deterministic
            or not isinstance(value.get("completed_at"), str)
            or not value["completed_at"]
        ):
            raise ExecutionError("library-effect disposition differs from resumed state")
        continue_decisions = {
            "continue_training_no_pending_cohort",
            "observe_increment_continue_training",
        }
        if require_continue and value.get("decision") not in continue_decisions:
            raise ExecutionError(
                "completed block lacks a continue-training library-effect disposition"
            )
        return value

    def write_library_effect_disposition(
        self,
        *,
        round_index: int,
        run_manifest_sha256: str,
        input_version: str,
        input_skills: list[SkillContract],
        curve_point: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Persist an exact-parent increment diagnostic or library identity."""
        deterministic = self._expected_library_effect_disposition(
            round_index=round_index,
            run_manifest_sha256=run_manifest_sha256,
            input_version=input_version,
            input_skills=input_skills,
            curve_point=curve_point,
        )
        path = self._library_effect_disposition_path(round_index)
        if path.is_file():
            value = self._load_validated_library_effect_disposition(
                round_index=round_index,
                run_manifest_sha256=run_manifest_sha256,
                input_version=input_version,
                input_skills=input_skills,
                curve_point=curve_point,
                require_continue=False,
            )
        else:
            value = {**deterministic, "completed_at": datetime.now(UTC).isoformat()}
            self.store.immutable_json(path, value)

        if value["decision"] not in {
            "continue_training_no_pending_cohort",
            "observe_increment_continue_training",
        }:
            raise ExecutionError("unknown library-effect disposition decision")
        return value

    def _prepare_current_library_identity_curve_point(
        self,
        *,
        round_index: int,
        case_limit: int | None,
        run_manifest_sha256: str,
        input_version: str,
        input_skills: list[SkillContract],
        current: list[ResearchTrajectory],
        current_evaluations: dict[str, TrajectoryEvaluation],
    ) -> dict[str, Any]:
        """Record no pending cohort without running a meaningless shadow arm."""

        batch = self.training_plan.batches[round_index - 1]
        input_ids = sorted(skill.skill_id for skill in input_skills)
        input_hash = skill_library_sha256(input_skills)
        curve = build_current_library_identity_report(
            sentinel_id=batch.batch_id,
            trajectories=current,
            evaluations=current_evaluations,
            partition=batch.batch_id,
            library_version=input_hash,
            skill_ids=set(input_ids),
            bootstrap_samples=int(self.experiment["learning_curve"]["bootstrap_samples"]),
            confidence_level=float(self.experiment["learning_curve"]["confidence_level"]),
            bootstrap_seed=int(self.experiment["learning_curve"]["bootstrap_seed"]),
        )

        def artifact_map(
            values: list[ResearchTrajectory], *, evaluation: bool
        ) -> dict[str, dict[str, str]]:
            return {
                item.trajectory_id: self._relative_artifact_record(
                    self.store.evaluation_path(item.trajectory_id)
                    if evaluation
                    else self.store.trajectory_path(batch.batch_id, item.trajectory_id)
                )
                for item in values
            }

        value = {
            "schema_version": CURRENT_LIBRARY_IDENTITY_CURVE_POINT_SCHEMA,
            "run_id": self.run_id,
            "run_manifest_sha256": run_manifest_sha256,
            "round": round_index,
            "batch_id": batch.batch_id,
            "case_limit": case_limit,
            "status": CURRENT_LIBRARY_IDENTITY_CURVE_STATUS,
            "evidence_role": self.experiment["learning_curve"]["evidence_role"],
            "sentinel_case_ids": [
                case_id
                for case_id in self.learning_curve_sentinels[batch.batch_id]
                if case_id in {item.case_id for item in current}
            ],
            "input_active_skill_ids": input_ids,
            "input_skill_library_version": input_version,
            "input_skill_library_sha256": input_hash,
            "parent_active_skill_ids": input_ids,
            "parent_skill_library_version": input_version,
            "parent_skill_library_sha256": input_hash,
            "new_skill_increment_ids": [],
            "identity_baseline": True,
            "current_trajectory_artifacts": artifact_map(current, evaluation=False),
            "current_evaluation_artifacts": artifact_map(current, evaluation=True),
            "parent_trajectory_artifacts": {},
            "parent_evaluation_artifacts": {},
            "intervention_isolation_artifact": None,
            "curve": curve,
            "completed_at": datetime.now(UTC).isoformat(),
        }
        self.store.immutable_json(self._learning_curve_point_path(round_index), value)
        return self._validate_current_library_identity_curve_point_artifact(
            point=value,
            round_index=round_index,
            case_limit=case_limit,
            run_manifest_sha256=run_manifest_sha256,
            input_version=input_version,
            input_skills=input_skills,
        )

    def _prepare_parent_cohort_curve_point(
        self,
        *,
        round_index: int,
        case_limit: int | None,
        run_manifest_sha256: str,
        input_version: str,
        input_skills: list[SkillContract],
        current: list[ResearchTrajectory],
        current_evaluations: dict[str, TrajectoryEvaluation],
        context: Mapping[str, Any],
        frozen_parent: list[ResearchTrajectory] | None = None,
        frozen_parent_evaluations: dict[str, TrajectoryEvaluation] | None = None,
    ) -> dict[str, Any]:
        """Measure one accumulated increment against its exact parent before teaching."""

        batch = self.training_plan.batches[round_index - 1]
        input_ids = sorted(skill.skill_id for skill in input_skills)
        input_hash = skill_library_sha256(input_skills)
        parent_skills = list(context["parent_skills"])
        parent_ids = sorted(skill.skill_id for skill in parent_skills)
        parent_hash = skill_library_sha256(parent_skills)
        parent_partition = f"{PARENT_COHORT_SHADOW_PREFIX}{batch.batch_id}"
        if (frozen_parent is None) != (frozen_parent_evaluations is None):
            raise ExecutionError("pre-frozen parent arm/evaluation presence drift")
        parent = (
            list(frozen_parent)
            if frozen_parent is not None
            else self.generate_parent_cohort_shadow(
                round_index=round_index,
                current_trajectories=current,
                parent_skills=parent_skills,
            )
        )
        isolation = parent_library_intervention_isolation_report(
            current,
            parent,
            input_skills,
            parent_skills,
            batch.batch_id,
            parent_partition,
        )
        isolation_path = (
            self.store.root
            / "health"
            / f"parent_cohort_intervention_isolation_{batch.batch_id}.json"
        )
        self.store.immutable_json(isolation_path, isolation)
        if isolation.get("passed") is not True:
            raise ExecutionError(
                "parent-cohort curve is not an exact sole library intervention: "
                f"batch={batch.batch_id}; failures={isolation.get('failure_count')}"
            )
        parent_evaluations = (
            dict(frozen_parent_evaluations)
            if frozen_parent_evaluations is not None
            else self.score_trajectories(
                parent,
                self.main_adapter,
                expected_skill_libraries={parent_hash: parent_skills},
                # This arm estimates observed library performance; it does not
                # create teacher evidence.  A syntactically safe terminal memo
                # fallback is therefore a genuine model outcome, exactly as in
                # held-out evaluation, rather than a reason to regenerate the
                # same matched rollout forever.  Training-group attribution
                # remains fail-closed and quarantines such groups separately.
                score_observed_terminal_failures=True,
            )
        )
        curve = build_parent_cohort_sentinel_report(
            sentinel_id=batch.batch_id,
            current_trajectories=current,
            current_evaluations=current_evaluations,
            current_partition=batch.batch_id,
            current_library_version=input_hash,
            current_skill_ids=set(input_ids),
            parent_trajectories=parent,
            parent_evaluations=parent_evaluations,
            parent_partition=parent_partition,
            parent_library_version=parent_hash,
            parent_skill_ids=set(parent_ids),
            new_skill_increment_ids=set(context["cohort_skill_ids"]),
            bootstrap_samples=int(self.experiment["learning_curve"]["bootstrap_samples"]),
            confidence_level=float(self.experiment["learning_curve"]["confidence_level"]),
            bootstrap_seed=int(self.experiment["learning_curve"]["bootstrap_seed"]),
        )
        curve["initial_infrastructure_identity"]["stepwise_intervention_isolation"] = (
            "passed_by_bound_exact_parent_executor_artifact"
        )

        def artifact_map(
            values: list[ResearchTrajectory], *, partition: str, evaluation: bool
        ) -> dict[str, dict[str, str]]:
            return {
                item.trajectory_id: self._relative_artifact_record(
                    self.store.evaluation_path(item.trajectory_id)
                    if evaluation
                    else self.store.trajectory_path(partition, item.trajectory_id)
                )
                for item in values
            }

        value = {
            "schema_version": PARENT_COHORT_CURVE_POINT_SCHEMA,
            "run_id": self.run_id,
            "run_manifest_sha256": run_manifest_sha256,
            "round": round_index,
            "batch_id": batch.batch_id,
            "case_limit": case_limit,
            "status": PARENT_COHORT_CURVE_STATUS,
            "evidence_role": self.experiment["learning_curve"]["evidence_role"],
            "sentinel_case_ids": [
                case_id
                for case_id in self.learning_curve_sentinels[batch.batch_id]
                if case_id in {item.case_id for item in current}
            ],
            "source_round": int(context["source_round"]),
            "source_batch_id": str(context["source_batch_id"]),
            "source_block_artifact": context["source_block_artifact"],
            "input_active_skill_ids": input_ids,
            "input_skill_library_version": input_version,
            "input_skill_library_sha256": input_hash,
            "parent_active_skill_ids": parent_ids,
            "parent_skill_library_version": str(context["parent_version"]),
            "parent_skill_library_sha256": parent_hash,
            "new_skill_increment_ids": list(context["cohort_skill_ids"]),
            "identity_baseline": False,
            "current_trajectory_artifacts": artifact_map(
                current, partition=batch.batch_id, evaluation=False
            ),
            "current_evaluation_artifacts": artifact_map(
                current, partition=batch.batch_id, evaluation=True
            ),
            "parent_trajectory_artifacts": artifact_map(
                parent, partition=parent_partition, evaluation=False
            ),
            "parent_evaluation_artifacts": artifact_map(
                parent, partition=parent_partition, evaluation=True
            ),
            "intervention_isolation_artifact": self._relative_artifact_record(isolation_path),
            "curve": curve,
            "completed_at": datetime.now(UTC).isoformat(),
        }
        self.store.immutable_json(self._learning_curve_point_path(round_index), value)
        return self._validate_parent_cohort_curve_point_artifact(
            point=value,
            round_index=round_index,
            case_limit=case_limit,
            run_manifest_sha256=run_manifest_sha256,
            input_version=input_version,
            input_skills=input_skills,
            context=context,
        )

    def _validate_current_library_identity_curve_point_artifact(
        self,
        *,
        point: Mapping[str, Any],
        round_index: int,
        case_limit: int | None,
        run_manifest_sha256: str,
        input_version: str,
        input_skills: list[SkillContract],
    ) -> dict[str, Any]:
        """Recompute a no-pending-cohort current-equals-parent identity point."""

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
            "input_skill_library_version",
            "input_skill_library_sha256",
            "parent_active_skill_ids",
            "parent_skill_library_version",
            "parent_skill_library_sha256",
            "new_skill_increment_ids",
            "identity_baseline",
            "current_trajectory_artifacts",
            "current_evaluation_artifacts",
            "parent_trajectory_artifacts",
            "parent_evaluation_artifacts",
            "intervention_isolation_artifact",
            "curve",
            "completed_at",
        }
        if set(point) != expected_fields:
            raise ExecutionError("retained-library identity point fields drifted")
        batch = self.training_plan.batches[round_index - 1]
        input_ids = sorted(skill.skill_id for skill in input_skills)
        input_hash = skill_library_sha256(input_skills)
        declared_cases = list(batch.case_ids)
        if case_limit is not None:
            declared_cases = declared_cases[:case_limit]
        sentinel_ids = [
            case_id
            for case_id in self.learning_curve_sentinels[batch.batch_id]
            if case_id in set(declared_cases)
        ]
        bindings = {
            "schema_version": CURRENT_LIBRARY_IDENTITY_CURVE_POINT_SCHEMA,
            "run_id": self.run_id,
            "run_manifest_sha256": run_manifest_sha256,
            "round": round_index,
            "batch_id": batch.batch_id,
            "case_limit": case_limit,
            "status": CURRENT_LIBRARY_IDENTITY_CURVE_STATUS,
            "evidence_role": self.experiment["learning_curve"]["evidence_role"],
            "sentinel_case_ids": sentinel_ids,
            "input_active_skill_ids": input_ids,
            "input_skill_library_version": input_version,
            "input_skill_library_sha256": input_hash,
            "parent_active_skill_ids": input_ids,
            "parent_skill_library_version": input_version,
            "parent_skill_library_sha256": input_hash,
            "new_skill_increment_ids": [],
            "identity_baseline": True,
            "parent_trajectory_artifacts": {},
            "parent_evaluation_artifacts": {},
            "intervention_isolation_artifact": None,
        }
        drift = [key for key, expected in bindings.items() if point.get(key) != expected]
        if drift:
            raise ExecutionError(f"retained-library identity point binding drift: {drift}")
        if not sentinel_ids:
            raise ExecutionError("retained-library identity sentinel is empty")
        curve = point.get("curve")
        expected_pairs = len(sentinel_ids) * len(
            self.experiment["trajectory_sampling"]["training_group_seeds"]
        )
        if not isinstance(curve, dict) or any(
            (
                curve.get("report_type") != "prequential_current_library_identity",
                curve.get("direction") != COHORT_PARENT_EFFECT_DIRECTION,
                curve.get("identity_baseline") is not True,
                curve.get("no_pending_cohort") is not True,
                curve.get("current_library_version") != input_hash,
                curve.get("parent_library_version") != input_hash,
                curve.get("current_skill_ids") != input_ids,
                curve.get("parent_skill_ids") != input_ids,
                curve.get("new_skill_increment_ids") != [],
                curve.get("partition_mapping")
                != {"current": batch.batch_id, "parent": batch.batch_id},
                curve.get("pair_count") != expected_pairs,
                curve.get("case_cluster_count") != len(sentinel_ids),
            )
        ):
            raise ExecutionError("retained-library identity statistic binding drift")
        pairs = curve.get("pairs")
        if not isinstance(pairs, list) or len(pairs) != expected_pairs:
            raise ExecutionError("retained-library identity pair records are incomplete")
        trajectory_ids = {str(item.get("current_trajectory_id")) for item in pairs}
        if (
            len(trajectory_ids) != expected_pairs
            or {str(item.get("parent_trajectory_id")) for item in pairs} != trajectory_ids
        ):
            raise ExecutionError("retained-library identity trajectory binding drift")

        def verify_artifact_map(value: object, *, evaluation: bool, label: str) -> None:
            if not isinstance(value, dict) or set(value) != trajectory_ids:
                raise ExecutionError(f"{label} artifact set is incomplete")
            for trajectory_id in sorted(trajectory_ids):
                expected_path = (
                    self.store.evaluation_path(trajectory_id)
                    if evaluation
                    else self.store.trajectory_path(batch.batch_id, trajectory_id)
                )
                self._verify_artifact_record(
                    value[trajectory_id], expected_path=expected_path, label=label
                )

        verify_artifact_map(
            point["current_trajectory_artifacts"],
            evaluation=False,
            label="retained-library identity trajectory",
        )
        verify_artifact_map(
            point["current_evaluation_artifacts"],
            evaluation=True,
            label="retained-library identity evaluation",
        )
        trajectories = [
            self.store.load_model(
                self.store.trajectory_path(batch.batch_id, trajectory_id),
                ResearchTrajectory,
            )
            for trajectory_id in sorted(trajectory_ids)
        ]
        evaluations = {
            trajectory_id: self.store.load_model(
                self.store.evaluation_path(trajectory_id), TrajectoryEvaluation
            )
            for trajectory_id in sorted(trajectory_ids)
        }
        recomputed = build_current_library_identity_report(
            sentinel_id=batch.batch_id,
            trajectories=trajectories,
            evaluations=evaluations,
            partition=batch.batch_id,
            library_version=input_hash,
            skill_ids=set(input_ids),
            bootstrap_samples=int(self.experiment["learning_curve"]["bootstrap_samples"]),
            confidence_level=float(self.experiment["learning_curve"]["confidence_level"]),
            bootstrap_seed=int(self.experiment["learning_curve"]["bootstrap_seed"]),
        )
        if canonical_json_sha256(recomputed) != canonical_json_sha256(curve):
            raise ExecutionError("retained-library identity statistic drift")
        return dict(point)

    def _validate_parent_cohort_curve_point_artifact(
        self,
        *,
        point: Mapping[str, Any],
        round_index: int,
        case_limit: int | None,
        run_manifest_sha256: str,
        input_version: str,
        input_skills: list[SkillContract],
        context: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Recompute a persisted next-block exact-parent cohort comparison."""

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
            "source_round",
            "source_batch_id",
            "source_block_artifact",
            "input_active_skill_ids",
            "input_skill_library_version",
            "input_skill_library_sha256",
            "parent_active_skill_ids",
            "parent_skill_library_version",
            "parent_skill_library_sha256",
            "new_skill_increment_ids",
            "identity_baseline",
            "current_trajectory_artifacts",
            "current_evaluation_artifacts",
            "parent_trajectory_artifacts",
            "parent_evaluation_artifacts",
            "intervention_isolation_artifact",
            "curve",
            "completed_at",
        }
        if set(point) != expected_fields:
            raise ExecutionError("parent-cohort development point fields drifted")
        batch = self.training_plan.batches[round_index - 1]
        input_ids = sorted(skill.skill_id for skill in input_skills)
        input_hash = skill_library_sha256(input_skills)
        parent_skills = list(context["parent_skills"])
        parent_ids = sorted(skill.skill_id for skill in parent_skills)
        parent_hash = skill_library_sha256(parent_skills)
        declared_cases = list(batch.case_ids)
        if case_limit is not None:
            declared_cases = declared_cases[:case_limit]
        sentinel_ids = [
            case_id
            for case_id in self.learning_curve_sentinels[batch.batch_id]
            if case_id in set(declared_cases)
        ]
        bindings = {
            "schema_version": PARENT_COHORT_CURVE_POINT_SCHEMA,
            "run_id": self.run_id,
            "run_manifest_sha256": run_manifest_sha256,
            "round": round_index,
            "batch_id": batch.batch_id,
            "case_limit": case_limit,
            "status": PARENT_COHORT_CURVE_STATUS,
            "evidence_role": self.experiment["learning_curve"]["evidence_role"],
            "sentinel_case_ids": sentinel_ids,
            "source_round": context["source_round"],
            "source_batch_id": context["source_batch_id"],
            "source_block_artifact": context["source_block_artifact"],
            "input_active_skill_ids": input_ids,
            "input_skill_library_version": input_version,
            "input_skill_library_sha256": input_hash,
            "parent_active_skill_ids": parent_ids,
            "parent_skill_library_version": context["parent_version"],
            "parent_skill_library_sha256": parent_hash,
            "new_skill_increment_ids": context["cohort_skill_ids"],
            "identity_baseline": False,
        }
        drift = [key for key, expected in bindings.items() if point.get(key) != expected]
        if drift:
            raise ExecutionError(f"parent-cohort development point binding drift: {drift}")
        self._verify_artifact_record(
            point["source_block_artifact"],
            expected_path=(
                self.store.root
                / "manifests"
                / f"{self._direct_block_manifest_name(str(context['source_batch_id']))}.json"
            ),
            label="parent-cohort source block",
        )
        curve = point.get("curve")
        parent_partition = f"{PARENT_COHORT_SHADOW_PREFIX}{batch.batch_id}"
        expected_pairs = len(sentinel_ids) * len(
            self.experiment["trajectory_sampling"]["training_group_seeds"]
        )
        if not isinstance(curve, dict) or any(
            (
                curve.get("report_type")
                != "prequential_new_skill_increment_vs_exact_parent_library",
                curve.get("sentinel_id") != batch.batch_id,
                curve.get("direction") != COHORT_PARENT_EFFECT_DIRECTION,
                curve.get("current_library_version") != input_hash,
                curve.get("parent_library_version") != parent_hash,
                curve.get("current_skill_ids") != input_ids,
                curve.get("parent_skill_ids") != parent_ids,
                curve.get("new_skill_increment_ids") != context["cohort_skill_ids"],
                curve.get("partition_mapping")
                != {"current": batch.batch_id, "parent": parent_partition},
                curve.get("pair_count") != expected_pairs,
                curve.get("case_cluster_count") != len(sentinel_ids),
            )
        ):
            raise ExecutionError("parent-cohort curve statistic binding drift")
        pairs = curve.get("pairs")
        if not isinstance(pairs, list) or len(pairs) != expected_pairs:
            raise ExecutionError("parent-cohort curve pair records are incomplete")
        current_ids = {str(item.get("current_trajectory_id")) for item in pairs}
        parent_trajectory_ids = {str(item.get("parent_trajectory_id")) for item in pairs}
        if len(current_ids) != expected_pairs or len(parent_trajectory_ids) != expected_pairs:
            raise ExecutionError("parent-cohort curve trajectory identities collide")

        def verify_artifact_map(
            value: object,
            *,
            expected_ids: set[str],
            partition: str | None,
            evaluation: bool,
            label: str,
        ) -> None:
            if not isinstance(value, dict) or set(value) != expected_ids:
                raise ExecutionError(f"{label} artifact set is incomplete")
            for trajectory_id in sorted(expected_ids):
                expected_path = (
                    self.store.evaluation_path(trajectory_id)
                    if evaluation
                    else self.store.trajectory_path(str(partition), trajectory_id)
                )
                self._verify_artifact_record(
                    value[trajectory_id], expected_path=expected_path, label=label
                )

        verify_artifact_map(
            point["current_trajectory_artifacts"],
            expected_ids=current_ids,
            partition=batch.batch_id,
            evaluation=False,
            label="parent-cohort current trajectory",
        )
        verify_artifact_map(
            point["current_evaluation_artifacts"],
            expected_ids=current_ids,
            partition=None,
            evaluation=True,
            label="parent-cohort current evaluation",
        )
        verify_artifact_map(
            point["parent_trajectory_artifacts"],
            expected_ids=parent_trajectory_ids,
            partition=parent_partition,
            evaluation=False,
            label="parent-cohort parent trajectory",
        )
        verify_artifact_map(
            point["parent_evaluation_artifacts"],
            expected_ids=parent_trajectory_ids,
            partition=None,
            evaluation=True,
            label="parent-cohort parent evaluation",
        )
        current_trajectories = [
            self.store.load_model(
                self.store.trajectory_path(batch.batch_id, trajectory_id),
                ResearchTrajectory,
            )
            for trajectory_id in sorted(current_ids)
        ]
        current_evaluations = {
            trajectory_id: self.store.load_model(
                self.store.evaluation_path(trajectory_id), TrajectoryEvaluation
            )
            for trajectory_id in sorted(current_ids)
        }
        parent_trajectories = [
            self.store.load_model(
                self.store.trajectory_path(parent_partition, trajectory_id),
                ResearchTrajectory,
            )
            for trajectory_id in sorted(parent_trajectory_ids)
        ]
        parent_evaluations = {
            trajectory_id: self.store.load_model(
                self.store.evaluation_path(trajectory_id), TrajectoryEvaluation
            )
            for trajectory_id in sorted(parent_trajectory_ids)
        }
        isolation_path = self._verify_artifact_record(
            point["intervention_isolation_artifact"],
            expected_path=(
                self.store.root
                / "health"
                / f"parent_cohort_intervention_isolation_{batch.batch_id}.json"
            ),
            label="parent-cohort intervention isolation",
        )
        persisted_isolation = json.loads(isolation_path.read_text(encoding="utf-8"))
        recomputed_isolation = parent_library_intervention_isolation_report(
            current_trajectories,
            parent_trajectories,
            input_skills,
            parent_skills,
            batch.batch_id,
            parent_partition,
        )
        if recomputed_isolation.get("passed") is not True or canonical_json_sha256(
            recomputed_isolation
        ) != canonical_json_sha256(persisted_isolation):
            raise ExecutionError("parent-cohort intervention isolation artifact drift")
        recomputed_curve = build_parent_cohort_sentinel_report(
            sentinel_id=batch.batch_id,
            current_trajectories=current_trajectories,
            current_evaluations=current_evaluations,
            current_partition=batch.batch_id,
            current_library_version=input_hash,
            current_skill_ids=set(input_ids),
            parent_trajectories=parent_trajectories,
            parent_evaluations=parent_evaluations,
            parent_partition=parent_partition,
            parent_library_version=parent_hash,
            parent_skill_ids=set(parent_ids),
            new_skill_increment_ids=set(context["cohort_skill_ids"]),
            bootstrap_samples=int(self.experiment["learning_curve"]["bootstrap_samples"]),
            confidence_level=float(self.experiment["learning_curve"]["confidence_level"]),
            bootstrap_seed=int(self.experiment["learning_curve"]["bootstrap_seed"]),
        )
        recomputed_curve["initial_infrastructure_identity"]["stepwise_intervention_isolation"] = (
            "passed_by_bound_exact_parent_executor_artifact"
        )
        if canonical_json_sha256(recomputed_curve) != canonical_json_sha256(curve):
            raise ExecutionError("parent-cohort curve statistic drift")
        return dict(point)

    def _validate_learning_curve_point_artifact(
        self,
        *,
        round_index: int,
        case_limit: int | None,
        run_manifest_sha256: str,
        expected_input_skill_ids: list[str],
        expected_input_skill_library_sha256: str,
        expected_input_skill_library_version: str | None = None,
        artifact_record: object | None = None,
    ) -> dict[str, Any]:
        """Validate one immutable prequential point and every artifact it cites."""

        batch = self.training_plan.batches[round_index - 1]
        point_path = self._learning_curve_point_path(round_index)
        if artifact_record is not None:
            self._verify_artifact_record(
                artifact_record,
                expected_path=point_path,
                label="development learning-curve point",
            )
        try:
            point = json.loads(point_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ExecutionError(
                f"invalid development learning-curve point: {batch.batch_id}"
            ) from exc
        input_version = expected_input_skill_library_version
        if input_version is None:
            if round_index != 1:
                raise ExecutionError("non-initial development point requires its registry version")
            input_version = FORMAL_INITIAL_SKILL_LIBRARY_ID
        input_skills: list[SkillContract] = []
        parent_context: dict[str, Any] | None = None
        if round_index == 1:
            expected_empty_hash = skill_library_sha256([])
            if (
                expected_input_skill_ids != []
                or expected_input_skill_library_sha256 != expected_empty_hash
                or input_version != FORMAL_INITIAL_SKILL_LIBRARY_ID
            ):
                raise ExecutionError(
                    "development point input library binding mismatch: version/hash drifted"
                )
        else:
            input_skills = self._skills_for_library_version(input_version)
            if (
                sorted(skill.skill_id for skill in input_skills) != expected_input_skill_ids
                or skill_library_sha256(input_skills) != expected_input_skill_library_sha256
            ):
                raise ExecutionError("development point input library version/hash drifted")
            parent_context = self._previous_block_skill_increment(
                round_index=round_index,
                input_version=input_version,
                input_skills=input_skills,
            )
        if parent_context is not None:
            if not isinstance(point, dict):
                raise ExecutionError("parent-cohort development point must be an object")
            return self._validate_parent_cohort_curve_point_artifact(
                point=point,
                round_index=round_index,
                case_limit=case_limit,
                run_manifest_sha256=run_manifest_sha256,
                input_version=input_version,
                input_skills=input_skills,
                context=parent_context,
            )
        if isinstance(point, dict) and point.get("schema_version") == (
            CURRENT_LIBRARY_IDENTITY_CURVE_POINT_SCHEMA
        ):
            return self._validate_current_library_identity_curve_point_artifact(
                point=point,
                round_index=round_index,
                case_limit=case_limit,
                run_manifest_sha256=run_manifest_sha256,
                input_version=input_version,
                input_skills=input_skills,
            )
        if isinstance(point, dict) and point.get("schema_version") == (
            PARENT_COHORT_CURVE_POINT_SCHEMA
        ):
            raise ExecutionError("parent-increment point has no preceding accumulated increment")
        raise ExecutionError(
            "development curve point uses a retired fixed-empty schema; start a fresh run"
        )

    def prepare_development_curve_point(
        self,
        *,
        round_index: int,
        case_limit: int | None,
        run_manifest_sha256: str,
        input_version: str | None = None,
        input_skills: list[SkillContract],
        trajectories: list[ResearchTrajectory],
        evaluations: dict[str, TrajectoryEvaluation],
        frozen_parent: list[ResearchTrajectory] | None = None,
        frozen_parent_evaluations: dict[str, TrajectoryEvaluation] | None = None,
    ) -> dict[str, Any]:
        """Measure the input library before any current-block teacher decision."""

        input_ids = sorted(item.skill_id for item in input_skills)
        input_hash = skill_library_sha256(input_skills)
        resolved_input_version = input_version or (
            self.registry.current() or FORMAL_INITIAL_SKILL_LIBRARY_ID
        )
        point_path = self._learning_curve_point_path(round_index)
        if point_path.is_file():
            return self._validate_learning_curve_point_artifact(
                round_index=round_index,
                case_limit=case_limit,
                run_manifest_sha256=run_manifest_sha256,
                expected_input_skill_ids=input_ids,
                expected_input_skill_library_sha256=input_hash,
                expected_input_skill_library_version=resolved_input_version,
            )

        current = self._learning_curve_current_trajectories(
            round_index=round_index,
            trajectories=trajectories,
            input_skill_library_sha256=input_hash,
        )
        current_ids = {item.trajectory_id for item in current}
        current_evaluations = {
            trajectory_id: evaluations[trajectory_id] for trajectory_id in current_ids
        }
        parent_context = self._previous_block_skill_increment(
            round_index=round_index,
            input_version=resolved_input_version,
            input_skills=input_skills,
        )
        if parent_context is not None:
            return self._prepare_parent_cohort_curve_point(
                round_index=round_index,
                case_limit=case_limit,
                run_manifest_sha256=run_manifest_sha256,
                input_version=resolved_input_version,
                input_skills=input_skills,
                current=current,
                current_evaluations=current_evaluations,
                context=parent_context,
                frozen_parent=frozen_parent,
                frozen_parent_evaluations=frozen_parent_evaluations,
            )
        if frozen_parent is not None or frozen_parent_evaluations is not None:
            raise ExecutionError("pre-frozen parent arm supplied without a pending cohort")
        return self._prepare_current_library_identity_curve_point(
            round_index=round_index,
            case_limit=case_limit,
            run_manifest_sha256=run_manifest_sha256,
            input_version=resolved_input_version,
            input_skills=input_skills,
            current=current,
            current_evaluations=current_evaluations,
        )

    def score_trajectories(
        self,
        trajectories: list[ResearchTrajectory],
        adapter: DLawBenchAdapter,
        *,
        expected_skill_libraries: Mapping[str, list[SkillContract]] | None = None,
        score_observed_terminal_failures: bool = False,
    ) -> dict[str, TrajectoryEvaluation]:
        partitions = sorted({trajectory.partition for trajectory in trajectories})
        report_name = "pre_scoring_health_" + "__".join(partitions)
        evaluator_cases = {
            case_id: adapter.evaluator_case(case_id)
            for case_id in {trajectory.case_id for trajectory in trajectories}
        }
        report_builder = (
            official_evaluation_health_report
            if score_observed_terminal_failures
            else trajectory_health_report
        )
        health_report = report_builder(
            trajectories, evaluator_cases, expected_run_id=self.store.run_id
        )
        quality_diagnostics = cast(dict[str, Any], health_report["quality_diagnostics"])
        memory_contract_report = (
            skill_memory_contract_report(trajectories, expected_skill_libraries)
            if expected_skill_libraries is not None
            else None
        )
        if memory_contract_report is not None:
            quality_diagnostics["skill_memory_contract"] = memory_contract_report
        if memory_contract_report is not None and not memory_contract_report["passed"]:
            failure_count = int(memory_contract_report["failure_count"])
            counts = cast(dict[str, int], health_report["counts"])
            counts["skill_memory_contract_failure"] = failure_count
            health_report["blocking_issue_count"] = (
                int(health_report["blocking_issue_count"]) + failure_count
            )
            health_report["healthy"] = False
            issues = cast(list[dict[str, Any]], health_report["issues"])
            available_issue_slots = max(0, 100 - len(issues))
            for row in memory_contract_report["rows"]:
                if row["passed"] or available_issue_slots == 0:
                    continue
                issues.append(
                    {
                        "code": "skill_memory_contract_failure",
                        "trajectory_id": row["trajectory_id"],
                        "turn": 0,
                        "detail": ",".join(row["issues"]),
                    }
                )
                available_issue_slots -= 1
            health_report["issues_truncated"] = max(
                0,
                int(health_report["blocking_issue_count"]) - len(issues),
            )
        productivity_review: dict[str, Any] | None = None
        attribution_review: dict[str, Any] | None = None
        training_plan = getattr(self, "training_plan", None)
        productivity_thresholds = getattr(self, "training_batch_productivity_thresholds", None)
        attribution_policy = getattr(self, "training_group_attribution_policy", None)
        if training_plan is not None:
            batches_by_id = {batch.batch_id: batch for batch in training_plan.batches}
            if len(partitions) == 1 and partitions[0] in batches_by_id:
                declared_batch = batches_by_id[partitions[0]]
                quality_diagnostics = cast(dict[str, Any], health_report["quality_diagnostics"])
                if productivity_thresholds is not None:
                    # Productivity is descriptive and uses the complete generated
                    # matrix.  It is intentionally computed before any attribution
                    # quarantine, so exclusions cannot hide a futile rollout batch.
                    productivity_review = training_batch_productivity_review(
                        trajectories,
                        expected_case_ids=declared_batch.case_ids,
                        thresholds=productivity_thresholds,
                    )
                    quality_diagnostics["training_batch_productivity_review"] = productivity_review
                if attribution_policy is not None:
                    attribution_review = training_group_attribution_review(
                        trajectories,
                        health_report=cast(dict[str, Any], health_report),
                        policy=attribution_policy,
                    )
                    quality_diagnostics["training_group_attribution_review"] = attribution_review
        health_path = self.store.root / "health" / f"{report_name}.json"
        self.store.atomic_json(health_path, health_report)
        if memory_contract_report is not None and not memory_contract_report["passed"]:
            raise ExecutionError(
                "executor-owned skill memory contract failed before semantic scoring; "
                f"report={health_path}; failed_trajectories="
                f"{memory_contract_report['failure_count']}"
            )
        if not health_report["healthy"] and not (
            attribution_review and attribution_review["scoring_eligible"]
        ):
            raise ExecutionError(
                "pre-scoring trajectory health contract failed; "
                f"report={health_path}; counts={health_report['counts']}"
            )

        def score_one(trajectory: ResearchTrajectory) -> TrajectoryEvaluation:
            path = self.store.evaluation_path(trajectory.trajectory_id)
            failure_path = (
                self.store.root
                / "health"
                / "semantic_failures"
                / f"{trajectory.trajectory_id}.json"
            )
            if path.is_file():
                persisted = json.loads(path.read_text(encoding="utf-8"))
                expected_schema = int(TrajectoryEvaluation.model_fields["schema_version"].default)
                if persisted.get("schema_version") != expected_schema:
                    raise ExecutionError(
                        "stale semantic evaluation schema; preserve and quarantine "
                        f"the old artifact before rescoring: trajectory_id="
                        f"{trajectory.trajectory_id}, expected={expected_schema}, "
                        f"actual={persisted.get('schema_version')}"
                    )
                actual_contract = persisted.get("judge_qualification_contract_sha256")
                if actual_contract != self.judge_qualification_contract_sha256:
                    raise ExecutionError(
                        "stale semantic evaluation contract; preserve and quarantine "
                        f"the old artifact before rescoring: trajectory_id="
                        f"{trajectory.trajectory_id}, expected="
                        f"{self.judge_qualification_contract_sha256}, "
                        f"actual={actual_contract}"
                    )
                return TrajectoryEvaluation.model_validate(persisted)
            try:
                value = self.evaluator.evaluate(
                    trajectory, adapter.evaluator_case(trajectory.case_id)
                )
            except Exception as exc:
                self.store.atomic_json(
                    failure_path,
                    {
                        "schema_version": 1,
                        "status": "failed",
                        "failed_at": datetime.now(UTC).isoformat(),
                        "trajectory_id": trajectory.trajectory_id,
                        "case_id": trajectory.case_id,
                        "partition": trajectory.partition,
                        "judge_model": self.judge_client.model,
                        "error_type": type(exc).__name__,
                        "error_message": str(exc)[:2000],
                    },
                )
                raise
            self.store.save_model(path, value)
            if failure_path.is_file():
                prior = json.loads(failure_path.read_text(encoding="utf-8"))
                prior.update(
                    {
                        "status": "recovered",
                        "recovered_at": datetime.now(UTC).isoformat(),
                        "evaluation_path": str(path.relative_to(self.root)),
                        "evaluation_sha256": sha256_file(path),
                    }
                )
                self.store.atomic_json(failure_path, prior)
            return value

        values = parallel_map_ordered(
            trajectories,
            score_one,
            max_workers=int(self.experiment["execution"]["judge_workers"]),
            label="semantic_scoring",
            # A lost judge endpoint is an execution-integrity failure, not a bad
            # model-quality outcome.  Stop scheduling the remainder of the
            # matrix after the first exhausted request; completed evaluations
            # remain atomic and resumable on the next invocation.
            fail_fast=True,
        )
        return {
            trajectory.trajectory_id: value
            for trajectory, value in zip(trajectories, values, strict=True)
        }

    def propose_candidates(
        self,
        *,
        round_index: int,
        trajectories: list[ResearchTrajectory],
        evaluations: dict[str, TrajectoryEvaluation],
        candidate_budget: int | None = None,
    ) -> list[Path]:
        """Map every healthy K-group and locally edit one compact global playbook."""

        partitions = {item.partition for item in trajectories}
        if len(partitions) != 1:
            raise ExecutionError("playbook teacher trajectories span partitions")
        partition = next(iter(partitions))
        health_path = self.store.root / "health" / f"pre_scoring_health_{partition}.json"
        if not health_path.is_file():
            raise ExecutionError("playbook teacher is missing pre-scoring health report")
        health_report = json.loads(health_path.read_text(encoding="utf-8"))
        attribution = (health_report.get("quality_diagnostics") or {}).get(
            "training_group_attribution_review"
        )
        if not isinstance(attribution, dict) or not attribution.get("scoring_eligible"):
            raise ExecutionError("playbook teacher requires eligible K-group attribution")
        scoreable_group_ids = {str(item) for item in attribution.get("scoreable_group_ids") or []}
        configured_calls = int(self.experiment["execution"]["teacher_call_budget_per_round"])
        maximum_updates = int(self.experiment["execution"]["maximum_new_skills_per_block"])
        if candidate_budget is None:
            candidate_budget = maximum_updates
        final_block = round_index == len(self.training_plan.batches)
        if candidate_budget == 0:
            if not final_block:
                raise ExecutionError("only the final observation block may skip reflection")
            self.store.write_manifest(
                f"teacher_round_{round_index:02d}",
                {
                    "schema_version": 3,
                    "status": FINAL_BLOCK_TEACHER_SKIP_STATUS,
                    "round": round_index,
                    "evidence_unit": "none_final_observation_block",
                    "all_scoreable_cases_represented": True,
                    "represented_case_ids": [],
                    "group_evidence_cards": [],
                    "group_relative_status_counts": {},
                    "teacher_update_unit": "none_final_block",
                    "current_block_enters_cumulative_teacher_evidence": False,
                    "round_trajectory_contrast_patches": 0,
                    "teacher_packages": [],
                    "teacher_call_budget": configured_calls,
                    "teacher_calls": 0,
                    "resumed_teacher_packages": 0,
                    "teacher_budget_status_before_round": None,
                    "candidate_outcome_feedback_used": False,
                    "input_library_prequential_feedback": None,
                    "candidate_budget": 0,
                    "candidate_files": [],
                    "teacher_proposal_records": [],
                    "candidate_count": 0,
                    "final_block_generates_skills": False,
                },
                overwrite=True,
            )
            return []
        grouped = tf_grpo_teacher_evidence_groups(trajectories, scoreable_group_ids)
        observed_policy_trajectories = [
            item for item in trajectories if item.method == "training_policy_sample"
        ]
        observed_group_ids = {str(item.group_id) for item in observed_policy_trajectories}
        excluded_group_ids = {str(item) for item in attribution.get("excluded_group_ids") or []}
        if scoreable_group_ids & excluded_group_ids:
            raise ExecutionError("training attribution overlaps scoreable and excluded groups")
        if scoreable_group_ids | excluded_group_ids != observed_group_ids:
            raise ExecutionError(
                "training attribution does not partition every observed policy group"
            )
        expected_cases = {
            item.case_id
            for item in observed_policy_trajectories
            if str(item.group_id) in scoreable_group_ids
        }
        excluded_cases = {
            item.case_id
            for item in observed_policy_trajectories
            if str(item.group_id) in excluded_group_ids
        }
        represented_cases = {next(iter(members)).case_id for members in grouped.values() if members}
        if represented_cases != expected_cases:
            raise ExecutionError(
                "every attribution-scoreable training case must enter playbook reflection; "
                f"missing={sorted(expected_cases - represented_cases)}"
            )

        evidence_root = self.store.root / "evidence" / "group_cards"
        cards: list[dict[str, Any]] = []
        evidence_records: list[dict[str, Any]] = []
        for group_id, members in sorted(grouped.items()):
            card = build_group_evidence_card(group_id, members, evaluations)
            patch = TrajectoryGroupEvidencePatch(
                round_index=round_index,
                partition=partition,
                group_id=group_id,
                case_id=str(card["case_id"]),
                domain=str(card["domain"]),
                persona=str(card["persona"]),
                skill_library_version=str(card["skill_library_version"]),
                trajectory_ids=sorted(item.trajectory_id for item in members),
                trajectory_sha256={
                    item.trajectory_id: sha256_file(
                        self.store.trajectory_path(partition, item.trajectory_id)
                    )
                    for item in members
                },
                evaluation_sha256={
                    item.trajectory_id: sha256_file(self.store.evaluation_path(item.trajectory_id))
                    for item in members
                },
                card=card,
            )
            patch_path = evidence_root / (
                f"round_{round_index:02d}_{canonical_json_sha256(group_id)[:16]}.json"
            )
            if patch_path.is_file():
                prior = self.store.load_model(patch_path, TrajectoryGroupEvidencePatch)
                if canonical_json_sha256(prior.model_dump(mode="json")) != canonical_json_sha256(
                    patch.model_dump(mode="json")
                ):
                    raise ExecutionError(f"group evidence card drift: {patch_path}")
            else:
                self.store.save_model(patch_path, patch)
            cards.append(card)
            evidence_records.append(
                {
                    "group_id": group_id,
                    "case_id": card["case_id"],
                    "domain": card["domain"],
                    "relative_status": card["group_relative_status"],
                    "card_sha256": group_evidence_fingerprint(card),
                    "patch_file": str(patch_path.relative_to(self.root)),
                    "patch_sha256": sha256_file(patch_path),
                }
            )

        if candidate_budget < 0 or candidate_budget > maximum_updates:
            raise ExecutionError("invalid playbook update budget")
        if final_block and candidate_budget != 0:
            raise ExecutionError("the final observation block cannot create unobserved updates")
        if not final_block and candidate_budget == 0:
            raise ExecutionError("only the final observation block may skip reflection")

        curve_path = self._learning_curve_point_path(round_index)
        if not curve_path.is_file():
            raise ExecutionError("playbook teacher scheduling requires the prequential point")
        curve_point = json.loads(curve_path.read_text(encoding="utf-8"))
        library_feedback = prequential_input_library_feedback(
            curve_point,
            primary_endpoint=str(self.experiment["evaluation"]["primary_endpoint"]),
            case_domains={
                case_id: self.main_adapter.case_domain(case_id)
                for case_id in self.main_adapter.case_ids(self.experiment["data"]["training_split"])
            },
        )
        runtime_skills = self.active_skills()
        if sorted(skill.skill_id for skill in runtime_skills) != curve_point.get(
            "input_active_skill_ids"
        ) or skill_library_sha256(runtime_skills) != curve_point.get("input_skill_library_sha256"):
            raise ExecutionError("teacher feedback input library drifted from the curve point")
        identity_feedback = bool(curve_point.get("identity_baseline"))
        parent_skills = (
            list(runtime_skills)
            if identity_feedback
            else self._skills_for_library_version(
                str(curve_point.get("parent_skill_library_version") or "")
            )
        )
        library_feedback = add_document_transition_feedback(
            library_feedback,
            current_skills=runtime_skills,
            parent_skills=parent_skills,
            declared_increment_ids=(
                set()
                if identity_feedback
                else {str(item) for item in curve_point.get("new_skill_increment_ids") or []}
            ),
        )

        if final_block:
            raise ExecutionError("final observation block reached nonzero playbook scheduling")
        if configured_calls != 3 or maximum_updates != 1 or candidate_budget != 1:
            raise ExecutionError(
                "playbook evolution requires exactly two map calls, one reduce call, and one update"
            )
        if len(runtime_skills) > 1 or any(
            skill.skill_id != PLAYBOOK_SKILL_ID for skill in runtime_skills
        ):
            raise ExecutionError("working library is not the single-playbook treatment")
        current_playbook = runtime_skills[0] if runtime_skills else None

        ordered_cards = sorted(
            cards, key=lambda item: (str(item["case_id"]), str(item["group_id"]))
        )
        map_packages = [ordered_cards[index::2] for index in range(2)]
        if any(not package for package in map_packages):
            raise ExecutionError("playbook map-reduce requires two nonempty card packages")
        teacher_root = self.store.root / "teacher" / f"round_{round_index:02d}"
        batch_id = self.training_plan.batches[round_index - 1].batch_id
        map_paths = [teacher_root / f"{batch_id}.playbook_map_{index:02d}.json" for index in (1, 2)]
        reduce_path = teacher_root / f"{batch_id}.playbook_reduce.json"
        if reduce_path.is_file() and not all(path.is_file() for path in map_paths):
            raise ExecutionError("playbook reduce artifact exists before both map artifacts")

        existing_stage_paths = [path for path in [*map_paths, reduce_path] if path.is_file()]
        if existing_stage_paths:
            ledger_reservations, ledger_issue = self._teacher_budget_ledger_reservations()
            trusted_resume = self._trusted_persisted_playbook_teacher_calls(
                round_index,
                ledger_reservations=ledger_reservations,
                ledger_issue=ledger_issue,
            )
            ignored_resume_files = trusted_resume.get("ignored_files")
            if not isinstance(ignored_resume_files, dict) or ignored_resume_files:
                raise ExecutionError(
                    "persisted playbook teacher stage is not bound to the current "
                    f"input/cache/hard-ledger contract: {ignored_resume_files}"
                )
            if len(trusted_resume.get("trusted_files") or []) != len(existing_stage_paths):
                raise ExecutionError("persisted playbook teacher stage trust accounting drift")

        budget_status = self.teacher_client.invocation_budget_status()
        required_calls = sum(not path.is_file() for path in map_paths) + int(
            not reduce_path.is_file()
        )
        if budget_status is not None and budget_status["available"] < required_calls:
            raise ExecutionError(
                "playbook teacher cannot finish its resumable stages within Luna hard budget: "
                f"required={required_calls}; available={budget_status['available']}"
            )

        calls = 0
        resumed = 0
        mode_artifacts: list[PlaybookModeArtifact] = []
        for index, (package_cards, path) in enumerate(
            zip(map_packages, map_paths, strict=True), start=1
        ):
            package_id = f"{batch_id}.playbook_map_{index:02d}"
            expected_group_ids = sorted(str(card["group_id"]) for card in package_cards)
            expected_input_binding = playbook_map_input_binding_sha256(
                package_id=package_id,
                evidence_cards=package_cards,
                current_playbook=current_playbook,
            )
            if path.is_file():
                artifact = self.store.load_model(path, PlaybookModeArtifact)
                accounted_group_ids = {
                    group_id for mode in artifact.modes for group_id in mode.source_group_ids
                } | set(artifact.no_new_mode_group_ids)
                if (
                    artifact.package_id != package_id
                    or artifact.input_binding_sha256 != expected_input_binding
                    or artifact.source_group_ids != expected_group_ids
                    or accounted_group_ids != set(expected_group_ids)
                ):
                    raise ExecutionError(f"persisted playbook map binding drift: {path}")
                resumed += 1
            else:
                artifact = self.teacher.extract_playbook_modes(
                    package_id=package_id,
                    evidence_cards=package_cards,
                    current_playbook=current_playbook,
                    purpose="playbook_mode_extraction",
                )
                self.store.save_model(path, artifact, overwrite=False)
                calls += 1
            mode_artifacts.append(artifact)

        reduce_package_id = f"{batch_id}.playbook_reduce"
        reduce_maximum_operations = (
            INITIAL_PLAYBOOK_MAX_PATCH_OPERATIONS
            if current_playbook is None
            else EXISTING_PLAYBOOK_MAX_PATCH_OPERATIONS
        )
        expected_reduce_input_binding = playbook_reduce_input_binding_sha256(
            package_id=reduce_package_id,
            mode_artifacts=mode_artifacts,
            current_playbook=current_playbook,
            library_feedback=library_feedback,
            maximum_operations=reduce_maximum_operations,
        )
        if reduce_path.is_file():
            reduce_artifact = self.store.load_model(reduce_path, PlaybookReduceArtifact)
            if (
                reduce_artifact.package_id != reduce_package_id
                or reduce_artifact.input_binding_sha256 != expected_reduce_input_binding
                or reduce_artifact.proposal.group_id != f"{reduce_package_id}::playbook"
                or reduce_artifact.patch.package_id != reduce_package_id
            ):
                raise ExecutionError("persisted playbook reduce binding drift")
            resumed += 1
        else:
            proposal, patch = self.teacher.propose_playbook_update(
                package_id=reduce_package_id,
                evidence_cards=ordered_cards,
                mode_artifacts=mode_artifacts,
                current_playbook=current_playbook,
                library_feedback=library_feedback,
                purpose="playbook_patch_curation",
            )
            reduce_artifact = PlaybookReduceArtifact(
                package_id=reduce_package_id,
                input_binding_sha256=expected_reduce_input_binding,
                proposal=proposal,
                patch=patch,
            )
            self.store.save_model(reduce_path, reduce_artifact, overwrite=False)
            calls += 1
        proposal = reduce_artifact.proposal
        patch_payload = reduce_artifact.patch.model_dump(mode="json")

        candidate_paths: list[Path] = []
        candidate = proposal.usable_candidate
        disposition = "noop"
        if candidate is not None:
            candidate_root = self.store.root / "skills" / "candidates" / f"round_{round_index:02d}"
            destination = candidate_root / f"{candidate.skill_id}.yaml"
            if destination.is_file():
                prior = load_skill(destination)
                if skill_contract_definition_sha256(prior) != skill_contract_definition_sha256(
                    candidate
                ):
                    raise ExecutionError(f"persisted playbook candidate drift: {destination}")
            else:
                _atomic_yaml(destination, candidate)
            candidate_paths.append(destination)
            disposition = str(proposal.diagnosis.proposed_change).lower()
        elif proposal.parse_status != "valid_noop":
            raise ExecutionError("playbook teacher produced neither a valid candidate nor NOOP")

        package_records = [
            {
                "package_id": artifact.package_id,
                "stage": "map",
                "case_ids": sorted(str(card["case_id"]) for card in package_cards),
                "source_group_ids": artifact.source_group_ids,
                "mode_count": len(artifact.modes),
                "no_new_mode_group_ids": artifact.no_new_mode_group_ids,
                "artifact_file": str(path.relative_to(self.root)),
                "artifact_sha256": sha256_file(path),
            }
            for artifact, package_cards, path in zip(
                mode_artifacts, map_packages, map_paths, strict=True
            )
        ]
        package_records.append(
            {
                "package_id": reduce_package_id,
                "stage": "reduce",
                "source_group_ids": sorted(str(card["group_id"]) for card in ordered_cards),
                "operation_count": len(patch_payload.get("operations") or []),
                "artifact_file": str(reduce_path.relative_to(self.root)),
                "artifact_sha256": sha256_file(reduce_path),
            }
        )
        proposal_records = [
            {
                "group_id": proposal.group_id,
                "domain": proposal.diagnosis.skill_scope,
                "parse_status": proposal.parse_status,
                "static_issues": proposal.static_issues,
                "deterministic_normalizations": proposal.deterministic_normalizations,
                "source_group_ids": proposal.source_group_ids,
                "candidate_skill_id": candidate.skill_id if candidate is not None else None,
                "operation": proposal.diagnosis.proposed_change,
                "patch_operation_count": len(patch_payload.get("operations") or []),
                "staging_disposition": disposition,
            }
        ]

        self.store.write_manifest(
            f"teacher_round_{round_index:02d}",
            {
                "schema_version": 3,
                "status": "complete_group_evidence_playbook_reflection",
                "round": round_index,
                "evidence_unit": "complete_k_group_case_card",
                "all_scoreable_cases_represented": represented_cases == expected_cases,
                "observed_group_count": len(observed_group_ids),
                "scoreable_group_count": len(scoreable_group_ids),
                "attribution_excluded_group_ids": sorted(excluded_group_ids),
                "attribution_exclusion_reason_counts": dict(
                    sorted((attribution.get("exclusion_reason_counts") or {}).items())
                ),
                "represented_case_ids": sorted(represented_cases),
                "attribution_excluded_case_ids": sorted(excluded_cases),
                "group_evidence_cards": evidence_records,
                "group_relative_status_counts": dict(
                    sorted(Counter(str(card["group_relative_status"]) for card in cards).items())
                ),
                "teacher_update_unit": "one_cross_domain_playbook_exact_local_patch",
                "teacher_packages": package_records,
                "teacher_call_budget": configured_calls,
                "teacher_calls": calls,
                "resumed_teacher_packages": resumed,
                "teacher_budget_status_before_round": budget_status,
                "candidate_outcome_feedback_used": False,
                "input_library_prequential_feedback": library_feedback,
                "candidate_budget": candidate_budget,
                "candidate_files": [str(path.relative_to(self.root)) for path in candidate_paths],
                "teacher_proposal_records": proposal_records,
                "candidate_count": len(candidate_paths),
                "final_block_generates_skills": False,
            },
            overwrite=True,
        )
        return candidate_paths

    def admit_source_grounded_candidates(
        self,
        *,
        round_index: int,
        candidates: list[Path],
    ) -> list[Path]:
        """Admit the exact locally patched playbook through trust/safety gates only."""

        proposal_root = self.store.root / "teacher" / f"round_{round_index:02d}"
        proposal_paths = sorted(proposal_root.glob("*.playbook_reduce.json"))
        if len(proposal_paths) != 1:
            raise ExecutionError("playbook admission requires exactly one reduce proposal")
        proposal_path = proposal_paths[0]
        reduce_artifact = self.store.load_model(proposal_path, PlaybookReduceArtifact)
        proposal = reduce_artifact.proposal

        patches: dict[str, tuple[Path, TrajectoryGroupEvidencePatch]] = {}
        for path in sorted((self.store.root / "evidence" / "group_cards").glob("*.json")):
            patch = self.store.load_model(path, TrajectoryGroupEvidencePatch)
            if patch.round_index == round_index:
                if patch.group_id in patches:
                    raise ExecutionError(f"duplicate group evidence patch: {patch.group_id}")
                patches[patch.group_id] = (path, patch)

        active = self.active_skills()
        if len(active) > 1 or any(
            skill.skill_id != PLAYBOOK_SKILL_ID or skill.domain != "general" for skill in active
        ):
            raise ExecutionError("active working library is not the single-playbook treatment")
        prior = active[0] if active else None
        if skill_memory_capacity_issues(active):
            raise ExecutionError("active playbook violates prompt-memory capacity")

        maximum = int(self.experiment["execution"]["maximum_new_skills_per_block"])
        if maximum != 1 or len(candidates) > 1:
            raise ExecutionError("playbook candidates exceed the per-block update budget")
        admitted: list[Path] = []
        records: list[dict[str, Any]] = []
        output_by_id = {skill.skill_id: skill for skill in active}
        for path in sorted(candidates):
            candidate = load_skill(path)
            issues: list[str] = []
            if not _teacher_proposal_matches_candidate(proposal, candidate):
                issues.append("teacher_proposal_candidate_binding_mismatch")
            issues.extend(
                formal_skill_document_issues(
                    candidate,
                    learnable_objectives=formal_learnable_skill_objectives(self.experiment),
                )
            )
            issues.extend(validate_skill_static(candidate))
            if candidate.domain != "general" or candidate.skill_id != PLAYBOOK_SKILL_ID:
                issues.append("unstable_playbook_identity")
            operation = proposal.diagnosis.proposed_change
            if prior is None:
                if operation != "CREATE" or candidate.version != "1.0.0":
                    issues.append("invalid_playbook_create_transition")
            else:
                major, minor, patch_version = (int(item) for item in prior.version.split("."))
                if operation != "UPDATE" or candidate.skill_id != prior.skill_id:
                    issues.append("invalid_playbook_update_identity")
                if candidate.version != f"{major}.{minor}.{patch_version + 1}":
                    issues.append("invalid_playbook_update_version")
                if skill_document_semantic_sha256(candidate) == skill_document_semantic_sha256(
                    prior
                ):
                    issues.append("playbook_update_has_no_document_change")
            witness = proposal.group_evidence_witness
            if witness is None:
                issues.append("group_evidence_witness_missing")
            else:
                if witness.domain != "general":
                    issues.append("group_evidence_domain_mismatch")
                expected_case_ids: set[str] = set()
                expected_trajectory_ids: set[str] = set()
                for group_id in witness.evidence_group_ids:
                    patch_entry = patches.get(group_id)
                    if patch_entry is None:
                        issues.append(f"group_evidence_patch_missing:{group_id}")
                        continue
                    patch_path, evidence_patch = patch_entry
                    expected_card_hash = witness.evidence_card_sha256.get(group_id)
                    if group_evidence_fingerprint(evidence_patch.card) != expected_card_hash:
                        issues.append(f"group_evidence_card_hash_mismatch:{group_id}")
                    if sha256_file(patch_path) == "":
                        issues.append(f"group_evidence_patch_unreadable:{group_id}")
                    expected_case_ids.add(evidence_patch.case_id)
                    expected_trajectory_ids.update(evidence_patch.trajectory_ids)
                    for trajectory_id in evidence_patch.trajectory_ids:
                        trajectory_path = self.store.trajectory_path(
                            evidence_patch.partition, trajectory_id
                        )
                        evaluation_path = self.store.evaluation_path(trajectory_id)
                        if sha256_file(trajectory_path) != evidence_patch.trajectory_sha256.get(
                            trajectory_id
                        ):
                            issues.append(f"group_evidence_trajectory_drift:{trajectory_id}")
                        if sha256_file(evaluation_path) != evidence_patch.evaluation_sha256.get(
                            trajectory_id
                        ):
                            issues.append(f"group_evidence_evaluation_drift:{trajectory_id}")
                if set(witness.source_case_ids) != expected_case_ids:
                    issues.append("group_evidence_case_binding_mismatch")
                if set(witness.source_trajectory_ids) != expected_trajectory_ids:
                    issues.append("group_evidence_trajectory_binding_mismatch")
                prior_case_ids = (
                    set(prior.provenance.source_case_ids) if prior is not None else set()
                )
                prior_trajectory_ids = (
                    set(prior.provenance.source_trajectory_ids) if prior is not None else set()
                )
                if set(candidate.provenance.source_case_ids) != (
                    prior_case_ids | expected_case_ids
                ):
                    issues.append("candidate_cumulative_case_binding_mismatch")
                if set(candidate.provenance.source_trajectory_ids) != (
                    prior_trajectory_ids | expected_trajectory_ids
                ):
                    issues.append("candidate_cumulative_trajectory_binding_mismatch")
            if not issues:
                candidate.status = "active"
                _atomic_yaml(path, candidate)
                output_by_id[candidate.skill_id] = candidate
                admitted.append(path)
            else:
                candidate.status = "rejected"
                _atomic_yaml(path, candidate)
            records.append(
                {
                    "skill_id": candidate.skill_id,
                    "domain": candidate.domain,
                    "operation": operation,
                    "candidate_file": str(path.relative_to(self.root)),
                    "candidate_sha256": sha256_file(path),
                    "candidate_contract_sha256": skill_contract_definition_sha256(candidate),
                    "teacher_proposal_file": (str(proposal_path.relative_to(self.root))),
                    "valid": not issues,
                    "issues": sorted(set(issues)),
                }
            )

        output = sorted(output_by_id.values(), key=lambda item: item.skill_id)
        capacity_issues = skill_memory_capacity_issues(output)
        if capacity_issues:
            raise ExecutionError(
                f"playbook update violates prompt-memory capacity: {capacity_issues}"
            )
        output_hash = skill_library_sha256(output)
        output_version = (
            f"library_{output_hash[:16]}"
            if admitted
            else (self.registry.current() or FORMAL_INITIAL_SKILL_LIBRARY_ID)
        )
        report_path = self._skill_admission_report_path(round_index)
        self.store.atomic_json(
            report_path,
            {
                "schema_version": 6,
                "run_id": self.run_id,
                "round": round_index,
                "status": DIRECT_SKILL_ADMISSION_STATUS,
                "admission_role": DIRECT_SKILL_ADMISSION_ROLE,
                "per_candidate_outcome_gate": False,
                "baseline_active_skill_ids": sorted(skill.skill_id for skill in active),
                "baseline_skill_library_sha256": skill_library_sha256(active),
                "records": records,
                "new_candidate_files": [str(path.relative_to(self.root)) for path in candidates],
                "deduplicated_candidates": [],
                "prompt_capacity_admission_order": [load_skill(path).skill_id for path in admitted],
                "prompt_capacity_rejections": {},
                "admitted_skill_files": [str(path.relative_to(self.root)) for path in admitted],
                "admitted_skill_ids": sorted(load_skill(path).skill_id for path in admitted),
                "output_active_skill_ids": [skill.skill_id for skill in output],
                "output_skill_library_sha256": output_hash,
                "output_skill_library_version": output_version,
                "invalid_candidate_files": [
                    record["candidate_file"] for record in records if not record["valid"]
                ],
                "grounding_implementation_sha256": sha256_file(
                    self.root / "legal_skill_guard/evolution/group_evidence.py"
                ),
                "teacher_prompt_sha256": sha256_file(
                    self.root / "configs/prompts/skill_teacher_zh.txt"
                ),
                "mode_extractor_prompt_sha256": sha256_file(
                    self.root / "configs/prompts/skill_mode_extractor_zh.txt"
                ),
                "completed_at": datetime.now(UTC).isoformat(),
            },
        )
        return admitted

    def _activate_source_grounded_skills(
        self,
        *,
        round_index: int,
        candidate_paths: list[Path],
    ) -> str:
        """Atomically publish one block's hard-gate-passing playbook version."""

        report_path = self._skill_admission_report_path(round_index)
        if not report_path.is_file():
            raise ExecutionError("source-grounded activation report is missing")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if (
            report.get("schema_version") != 6
            or report.get("run_id") != self.run_id
            or report.get("round") != round_index
            or report.get("per_candidate_outcome_gate") is not False
        ):
            raise ExecutionError("source-grounded activation report binding drift")
        declared_files = sorted(str(item) for item in report["admitted_skill_files"])
        actual_files = sorted(str(path.relative_to(self.root)) for path in candidate_paths)
        if declared_files != actual_files:
            raise ExecutionError("source-grounded activation cohort differs from report")

        active = self.active_skills()
        if (
            sorted(skill.skill_id for skill in active) != report["baseline_active_skill_ids"]
            or skill_library_sha256(active) != report["baseline_skill_library_sha256"]
        ):
            # An interrupted activation is idempotent when the exact target is
            # already current; any other pointer state is unsafe to guess through.
            if (
                sorted(skill.skill_id for skill in active) == report["output_active_skill_ids"]
                and skill_library_sha256(active) == report["output_skill_library_sha256"]
            ):
                target = str(report["output_skill_library_version"])
                if target == FORMAL_INITIAL_SKILL_LIBRARY_ID:
                    if self.registry.current() is not None:
                        raise ExecutionError(
                            "empty bootstrap output has an active registry pointer"
                        )
                else:
                    self.registry.validate(target, require_current_static_schema=True)
                    if self.registry.current() != target:
                        self.registry.activate(target)
                return target
            raise ExecutionError("active library differs from admission baseline")

        merged_by_id = {skill.skill_id: skill for skill in active}
        for path in candidate_paths:
            candidate = load_skill(path)
            merged_by_id[candidate.skill_id] = candidate
        merged = sorted(merged_by_id.values(), key=lambda skill: skill.skill_id)
        if any(skill.status != "active" for skill in merged):
            raise ExecutionError("only active source-grounded documents may be published")
        if [skill.skill_id for skill in merged] != report[
            "output_active_skill_ids"
        ] or skill_library_sha256(merged) != report["output_skill_library_sha256"]:
            raise ExecutionError("source-grounded output library differs from report")
        version = str(report["output_skill_library_version"])
        if not candidate_paths:
            return version
        destination = self.registry.versions / version
        if destination.exists():
            self.registry.validate(version, require_current_static_schema=True)
        else:
            self.registry.create_version(
                version,
                merged,
                parent_version=(self.registry.current() or FORMAL_INITIAL_SKILL_LIBRARY_ID),
                evidence={
                    "transaction": "group_evidence_global_playbook_admission",
                    "source_round": round_index,
                    "admitted_skill_ids": report["admitted_skill_ids"],
                    "admission_report": str(report_path.relative_to(self.root)),
                    "admission_report_sha256": sha256_file(report_path),
                    "uses_candidate_outcomes": False,
                },
            )
        if self.registry.current() != version:
            self.registry.activate(version)
        return version

    @staticmethod
    def _trajectory_protocol_version() -> int:
        return int(ResearchTrajectory.model_fields["schema_version"].default)

    @staticmethod
    def _evaluation_protocol_version() -> int:
        return int(TrajectoryEvaluation.model_fields["schema_version"].default)

    def _verified_run_manifest_sha256(self) -> str:
        self.verify_run_manifest()
        path = self.store.root / "manifests" / "run.json"
        if not path.is_file():
            raise ExecutionError("verified run manifest file is missing")
        return sha256_file(path)

    def _training_round_expected_matrix(
        self,
        round_index: int,
        *,
        case_limit: int | None,
        input_skill_library_sha256: str,
        input_skills: list[SkillContract] | None = None,
    ) -> list[dict[str, Any]]:
        """Reconstruct every frozen rollout cell independently of persisted outputs."""

        declared_batch = self.training_plan.batches[round_index - 1]
        case_ids = list(declared_batch.case_ids)
        if case_limit is not None:
            case_ids = case_ids[:case_limit]
        records: list[dict[str, Any]] = []
        group_size = int(self.experiment["trajectory_sampling"]["group_size"])
        active_skills = list(input_skills) if input_skills is not None else self.active_skills()
        if skill_library_sha256(active_skills) != input_skill_library_sha256:
            raise ExecutionError("training input skill library hash mismatch")
        for case_id in case_ids:
            persona_id = declared_batch.persona_assignment[case_id]
            for seed_value in self.experiment["trajectory_sampling"]["training_group_seeds"]:
                seed = int(seed_value)
                group_id = f"{declared_batch.batch_id}.{case_id}.{persona_id}.seed_{seed}"
                for sample_index in range(group_size):
                    method = "training_policy_sample"
                    skill_hash = input_skill_library_sha256
                    trajectory_id = trajectory_identity(
                        run_id=self.run_id,
                        partition=declared_batch.batch_id,
                        method=method,
                        case_id=case_id,
                        persona=str(persona_id),
                        seed=seed,
                        sample_index=sample_index,
                        skill_library_version=skill_hash,
                    )
                    records.append(
                        {
                            "trajectory_id": trajectory_id,
                            "run_id": self.run_id,
                            "partition": declared_batch.batch_id,
                            "method": method,
                            "case_id": case_id,
                            "persona": str(persona_id),
                            "seed": seed,
                            "sample_index": sample_index,
                            "group_id": group_id,
                            "skill_library_version": skill_hash,
                            "model_id": self.local_model,
                            "model_revision": self.local_revision,
                        }
                    )
        return records

    def _relative_artifact_record(self, path: Path) -> dict[str, str]:
        try:
            relative = path.resolve().relative_to(self.root.resolve())
        except ValueError as exc:
            raise ExecutionError(f"artifact escapes project root: {path}") from exc
        if not path.is_file():
            raise ExecutionError(f"checkpoint artifact is missing: {path}")
        return {"path": str(relative), "sha256": sha256_file(path)}

    def _verify_artifact_record(
        self,
        record: object,
        *,
        expected_path: Path | None,
        label: str,
    ) -> Path:
        if not isinstance(record, dict) or set(record) != {"path", "sha256"}:
            raise ExecutionError(f"invalid {label} artifact binding")
        relative_value = record.get("path")
        expected_hash = record.get("sha256")
        if not isinstance(relative_value, str) or not isinstance(expected_hash, str):
            raise ExecutionError(f"invalid {label} artifact binding values")
        relative = Path(relative_value)
        if relative.is_absolute() or ".." in relative.parts:
            raise ExecutionError(f"unsafe {label} artifact path: {relative_value}")
        path = self.root / relative
        try:
            path.resolve().relative_to(self.root.resolve())
        except ValueError as exc:
            raise ExecutionError(f"{label} artifact escapes project root") from exc
        if expected_path is not None and path.resolve() != expected_path.resolve():
            raise ExecutionError(
                f"{label} artifact path mismatch: expected={expected_path}, actual={path}"
            )
        if not path.is_file() or sha256_file(path) != expected_hash:
            raise ExecutionError(f"{label} artifact is missing or changed: {relative_value}")
        return path

    @staticmethod
    def _deduplicate_candidate_paths(
        candidates: list[Path],
    ) -> tuple[list[Path], list[dict[str, str]]]:
        """Return one path per skill ID and per learned document/scope.

        Input order is the deterministic precedence order.  Exact aliases are
        recoverable teacher noise, while one ID naming different content is an
        integrity failure and must stop the round.
        """

        unique: list[Path] = []
        duplicates: list[dict[str, str]] = []
        by_id: dict[str, tuple[str, Path]] = {}
        by_document: dict[str, tuple[str, Path]] = {}
        for path in candidates:
            candidate = load_skill(path)
            document_hash = skill_document_semantic_sha256(candidate)
            prior_id = by_id.get(candidate.skill_id)
            if prior_id is not None and prior_id[0] != document_hash:
                raise ExecutionError(
                    "candidate cohort reuses one skill_id for different documents: "
                    f"{candidate.skill_id}"
                )
            prior_document = by_document.get(document_hash)
            if prior_id is not None or prior_document is not None:
                canonical_path = prior_id[1] if prior_id is not None else prior_document[1]
                canonical_skill_id = (
                    candidate.skill_id if prior_id is not None else prior_document[0]
                )
                duplicates.append(
                    {
                        "candidate_path": str(path),
                        "canonical_path": str(canonical_path),
                        "canonical_skill_id": canonical_skill_id,
                        "reason": (
                            "duplicate_skill_id" if prior_id is not None else "duplicate_document"
                        ),
                    }
                )
                continue
            by_id[candidate.skill_id] = (document_hash, path)
            by_document[document_hash] = (candidate.skill_id, path)
            unique.append(path)
        return unique, duplicates

    @staticmethod
    def _direct_block_manifest_name(batch_id: str) -> str:
        return f"{batch_id}__complete"

    def _skill_admission_report_path(self, round_index: int) -> Path:
        return (
            self.store.root
            / "reports"
            / f"{DIRECT_SKILL_ADMISSION_REPORT_PREFIX}{round_index:02d}.json"
        )

    def _skills_for_library_version(self, version: str) -> list[SkillContract]:
        if version == FORMAL_INITIAL_SKILL_LIBRARY_ID:
            skills, _ = self.initial_skill_library()
            return skills
        self.registry.validate(version, require_current_static_schema=True)
        return load_skill_directory(self.registry.versions / version, active_only=True)

    def _load_direct_admission_report(
        self,
        *,
        round_index: int,
        expected_baseline_ids: list[str],
        expected_baseline_hash: str,
    ) -> tuple[dict[str, Any], list[Path]]:
        path = self._skill_admission_report_path(round_index)
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ExecutionError("direct skill-admission report is missing or invalid") from exc
        if (
            report.get("schema_version") != 6
            or report.get("run_id") != self.run_id
            or report.get("round") != round_index
            or report.get("status") != DIRECT_SKILL_ADMISSION_STATUS
            or report.get("admission_role") != DIRECT_SKILL_ADMISSION_ROLE
            or report.get("per_candidate_outcome_gate") is not False
            or report.get("baseline_active_skill_ids") != expected_baseline_ids
            or report.get("baseline_skill_library_sha256") != expected_baseline_hash
        ):
            raise ExecutionError("direct skill-admission report binding drift")

        records = report.get("records")
        if not isinstance(records, list):
            raise ExecutionError("direct skill-admission records are invalid")
        record_by_id: dict[str, dict[str, Any]] = {}
        for record in records:
            if not isinstance(record, dict) or not isinstance(record.get("skill_id"), str):
                raise ExecutionError("invalid direct skill-admission record")
            skill_id = str(record["skill_id"])
            if skill_id in record_by_id:
                raise ExecutionError("duplicate skill in direct admission report")
            relative = Path(str(record.get("candidate_file") or ""))
            if relative.is_absolute() or ".." in relative.parts:
                raise ExecutionError("unsafe direct-admission candidate path")
            candidate_path = self.root / relative
            expected_path = self.candidate_root / f"round_{round_index:02d}" / f"{skill_id}.yaml"
            if candidate_path.resolve() != expected_path.resolve() or not candidate_path.is_file():
                raise ExecutionError("direct-admission candidate artifact is unavailable")
            candidate = load_skill(candidate_path)
            if (
                candidate.skill_id != skill_id
                or sha256_file(candidate_path) != record.get("candidate_sha256")
                or skill_contract_definition_sha256(candidate)
                != record.get("candidate_contract_sha256")
            ):
                raise ExecutionError("direct-admission candidate artifact drift")
            expected_status = "active" if bool(record.get("valid")) else "rejected"
            if candidate.status != expected_status:
                raise ExecutionError("direct-admission candidate lifecycle drift")
            record_by_id[skill_id] = record

        admitted_files = [str(item) for item in report.get("admitted_skill_files") or []]
        admitted_paths = [self.root / item for item in admitted_files]
        admitted_ids = sorted(load_skill(path).skill_id for path in admitted_paths)
        if admitted_ids != sorted(
            str(item) for item in report.get("admitted_skill_ids") or []
        ) or any(not bool(record_by_id[skill_id].get("valid")) for skill_id in admitted_ids):
            raise ExecutionError("direct-admission cohort membership drift")
        return report, admitted_paths

    def write_library_maintenance_report(
        self,
        *,
        round_index: int,
        input_skills: list[SkillContract],
    ) -> Path | None:
        """Record periodic whole-library hygiene without inventing attribution."""

        interval = int(self.experiment["skill_admission"]["maintenance_interval_blocks"])
        final_round = len(self.training_plan.batches)
        if round_index % interval != 0 and round_index != final_round:
            return None
        active = self.active_skills()
        static_issues: dict[str, list[str]] = {}
        for skill in active:
            issues = validate_skill_static(skill)
            if issues:
                static_issues[skill.skill_id] = issues
        documents: dict[str, list[str]] = {}
        for skill in active:
            documents.setdefault(skill_document_semantic_sha256(skill), []).append(skill.skill_id)
        duplicate_groups = [
            sorted(skill_ids) for skill_ids in documents.values() if len(skill_ids) > 1
        ]
        capacity_issues = skill_memory_capacity_issues(active)
        batch_id = self.training_plan.batches[round_index - 1].batch_id
        observed_trajectories = [
            self.store.load_model(path, ResearchTrajectory)
            for path in sorted((self.store.root / "trajectories" / batch_id).glob("*.json"))
        ]
        exposure_summary = trajectory_behavior_summary(
            observed_trajectories,
            {skill.skill_id for skill in input_skills},
        )
        curve_path = self._learning_curve_point_path(round_index)
        curve_artifact = self._relative_artifact_record(curve_path)
        curve = json.loads(curve_path.read_text(encoding="utf-8"))
        library_feedback = prequential_input_library_feedback(
            curve,
            primary_endpoint=str(self.experiment["evaluation"]["primary_endpoint"]),
            case_domains={
                case_id: self.main_adapter.case_domain(case_id)
                for case_id in self.main_adapter.case_ids(self.experiment["data"]["training_split"])
            },
        )
        primary_regression = not bool(
            library_feedback["identity_baseline"]
        ) and "regression" in str(library_feedback["status"])
        hard_hygiene_issue = bool(static_issues or duplicate_groups or capacity_issues)
        deterministic_value = {
            "schema_version": 1,
            "run_id": self.run_id,
            "round": round_index,
            "batch_id": batch_id,
            "status": (
                "healthy"
                if not hard_hygiene_issue and not primary_regression
                else "requires_operator_review"
            ),
            "maintenance_scope": "whole_working_library",
            "automatic_candidate_effect_pruning": False,
            "reason": (
                "individual skill effects are not identifiable from cumulative block outcomes; "
                "exact duplicates and hard-invalid documents are prevented at admission; "
                "a negative paired primary endpoint changes subsequent teacher direction "
                "without being misreported as a healthy library"
            ),
            "observed_input_skill_ids": sorted(skill.skill_id for skill in input_skills),
            "observed_input_skill_library_sha256": skill_library_sha256(input_skills),
            "output_active_skill_ids": sorted(skill.skill_id for skill in active),
            "output_skill_library_sha256": skill_library_sha256(active),
            "observed_input_library_exposure": exposure_summary,
            "domain_counts": dict(sorted(Counter(skill.domain for skill in active).items())),
            "objective_counts": dict(sorted(Counter(skill.objective for skill in active).items())),
            "static_issues": static_issues,
            "exact_duplicate_groups": duplicate_groups,
            "prompt_capacity_issues": capacity_issues,
            "prequential_curve_artifact": curve_artifact,
            "prequential_primary_metric": curve["curve"]["metrics"].get(
                self.experiment["evaluation"]["primary_endpoint"]
            ),
            "prequential_training_feedback": library_feedback,
            "actions": [
                *(
                    ["prioritize_fact_recovery_in_subsequent_teacher_round"]
                    if primary_regression
                    else []
                ),
                *(["operator_review_static_or_capacity_issue"] if hard_hygiene_issue else []),
            ],
        }
        path = self.store.root / "reports" / f"library_maintenance_{round_index:02d}.json"
        if path.is_file():
            try:
                prior = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ExecutionError("library maintenance report is unreadable") from exc
            if not isinstance(prior, dict):
                raise ExecutionError("library maintenance report is not an object")
            prior_deterministic = {
                key: item for key, item in prior.items() if key != "completed_at"
            }
            if (
                prior_deterministic != deterministic_value
                or not isinstance(prior.get("completed_at"), str)
                or not prior["completed_at"]
            ):
                raise ExecutionError("library maintenance report differs from resumed state")
            return path
        value = {
            **deterministic_value,
            "completed_at": datetime.now(UTC).isoformat(),
        }
        self.store.immutable_json(path, value)
        return path

    def write_learning_checkpoint(
        self,
        *,
        round_index: int,
        case_limit: int | None,
        run_manifest_sha256: str,
        admitted_skill_ids: list[str],
        input_skills: list[SkillContract],
        development_curve_artifact: Mapping[str, Any],
        input_version: str | None = None,
    ) -> dict[str, Any]:
        """Bind one measured input library, its curve point, and the committed output library."""

        batch = self.training_plan.batches[round_index - 1]
        curve_path = self._verify_artifact_record(
            development_curve_artifact,
            expected_path=self._learning_curve_point_path(round_index),
            label="development curve point",
        )
        try:
            curve_point = json.loads(curve_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ExecutionError("development curve point is unreadable") from exc
        if not isinstance(curve_point, dict):
            raise ExecutionError("development curve point must be an object")

        input_ids = sorted(skill.skill_id for skill in input_skills)
        input_hash = skill_library_sha256(input_skills)
        if (
            curve_point.get("input_active_skill_ids") != input_ids
            or curve_point.get("input_skill_library_sha256") != input_hash
            or (
                input_version is not None
                and curve_point.get("input_skill_library_version") not in {None, input_version}
            )
        ):
            raise ExecutionError("learning checkpoint input-library binding mismatch")

        disposition_path = self._library_effect_disposition_path(round_index)
        try:
            disposition = json.loads(disposition_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ExecutionError("learning checkpoint lacks library-effect disposition") from exc
        if not isinstance(disposition, dict) or not isinstance(disposition.get("decision"), str):
            raise ExecutionError("learning checkpoint has invalid library-effect disposition")

        teacher_path = self.store.root / "manifests" / f"teacher_round_{round_index:02d}.json"
        try:
            teacher_manifest = json.loads(teacher_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ExecutionError("learning checkpoint lacks playbook-teacher manifest") from exc
        teacher_evidence_created = _playbook_teacher_evidence_created(
            teacher_manifest,
            round_index=round_index,
            total_rounds=len(self.training_plan.batches),
        )

        active = self.active_skills()
        active_ids = sorted(skill.skill_id for skill in active)
        active_hash = skill_library_sha256(active)
        deterministic = {
            "schema_version": LEARNING_CHECKPOINT_SCHEMA,
            "run_id": self.run_id,
            "checkpoint": round_index,
            "batch_id": batch.batch_id,
            "status": "measured_prequential_learning_checkpoint",
            "admitted_from_current_block": sorted(admitted_skill_ids),
            "measured_input_active_skill_ids": input_ids,
            "measured_input_skill_library_sha256": input_hash,
            "development_curve_artifact": dict(development_curve_artifact),
            "active_skill_ids": active_ids,
            "active_skill_library_sha256": active_hash,
            "teacher_evidence_created": teacher_evidence_created,
            "cohort_decision": disposition["decision"],
            "rejected_from_input_skill_ids": [],
            "evidence_role": str(self.experiment["learning_curve"]["evidence_role"]),
            "curve_identity_baseline": bool(curve_point.get("identity_baseline")),
        }
        path = self.store.root / "reports" / f"learning_checkpoint_{round_index:02d}.json"
        if path.is_file():
            prior = json.loads(path.read_text(encoding="utf-8"))
            if (
                {key: value for key, value in prior.items() if key != "completed_at"}
                != deterministic
                or not isinstance(prior.get("completed_at"), str)
                or not prior["completed_at"]
            ):
                raise ExecutionError("learning checkpoint differs from resumed state")
            return prior
        value = {**deterministic, "completed_at": datetime.now(UTC).isoformat()}
        self.store.immutable_json(path, value)
        return value

    def write_development_learning_curve_summary(self) -> dict[str, Any]:
        """Materialize the cumulative prequential series from immutable point artifacts."""

        points: list[dict[str, Any]] = []
        series: dict[str, list[dict[str, Any]]] = {
            metric: [] for metric in PREQUENTIAL_CURVE_METRICS
        }
        for round_index, batch in enumerate(self.training_plan.batches, start=1):
            curve_path = self._learning_curve_point_path(round_index)
            checkpoint_path = (
                self.store.root / "reports" / f"learning_checkpoint_{round_index:02d}.json"
            )
            if not curve_path.is_file() and not checkpoint_path.is_file():
                break
            if not curve_path.is_file() or not checkpoint_path.is_file():
                raise ExecutionError(f"partial learning-curve checkpoint pair: {batch.batch_id}")
            curve_point = json.loads(curve_path.read_text(encoding="utf-8"))
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            if not isinstance(curve_point, dict) or not isinstance(checkpoint, dict):
                raise ExecutionError("learning-curve point/checkpoint is not an object")
            curve = curve_point.get("curve")
            if not isinstance(curve, dict) or not isinstance(curve.get("metrics"), dict):
                raise ExecutionError(f"learning-curve metrics are unavailable: {batch.batch_id}")
            identity = bool(curve_point.get("identity_baseline"))
            comparator = "exact_same_current_library" if identity else "exact_parent_library"
            point: dict[str, Any] = {
                "round": round_index,
                "batch_id": batch.batch_id,
                "input_active_skill_ids": list(curve_point.get("input_active_skill_ids") or []),
                "input_skill_library_sha256": str(
                    curve_point.get("input_skill_library_sha256") or ""
                ),
                "output_active_skill_ids": list(checkpoint.get("active_skill_ids") or []),
                "output_skill_library_sha256": str(
                    checkpoint.get("active_skill_library_sha256") or ""
                ),
                "admitted_from_current_block": list(
                    checkpoint.get("admitted_from_current_block") or []
                ),
                "current_block_teacher_evidence_created": bool(
                    checkpoint.get("teacher_evidence_created")
                ),
                "identity_baseline": identity,
                "comparator": comparator,
                "pair_count": int(curve.get("pair_count", 0)),
                "case_cluster_count": int(curve.get("case_cluster_count", 0)),
                "artifact": self._relative_artifact_record(curve_path),
                "parent_active_skill_ids": list(curve_point.get("parent_active_skill_ids") or []),
                "parent_skill_library_version": str(
                    curve_point.get("parent_skill_library_version") or ""
                ),
                "parent_skill_library_sha256": str(
                    curve_point.get("parent_skill_library_sha256") or ""
                ),
                "observed_parent_increment_ids": list(
                    curve_point.get("new_skill_increment_ids") or []
                ),
                "cohort_disposition_artifact": self._relative_artifact_record(
                    self._library_effect_disposition_path(round_index)
                ),
            }
            points.append(point)
            for metric_name in PREQUENTIAL_CURVE_METRICS:
                metric = curve["metrics"].get(metric_name)
                estimate = metric.get("case_cluster_estimate") if isinstance(metric, dict) else None
                if not isinstance(metric, dict) or not isinstance(estimate, dict):
                    raise ExecutionError(
                        f"learning-curve metric is incomplete: {batch.batch_id}/{metric_name}"
                    )
                series[metric_name].append(
                    {
                        "round": round_index,
                        "batch_id": batch.batch_id,
                        "comparator": comparator,
                        "current_library_mean": metric.get("current_library_mean"),
                        "parent_library_mean": metric.get("parent_library_mean"),
                        "mean_delta": estimate.get("mean_delta"),
                        "confidence_lower": estimate.get("lower"),
                        "confidence_upper": estimate.get("upper"),
                    }
                )

        value = {
            "schema_version": DEVELOPMENT_CURVE_SUMMARY_SCHEMA,
            "run_id": self.run_id,
            "status": ("complete" if len(points) == len(self.training_plan.batches) else "partial"),
            "evidence_role": str(self.experiment["learning_curve"]["evidence_role"]),
            "expected_points": len(self.training_plan.batches),
            "completed_points": len(points),
            "direction": DEVELOPMENT_CURVE_SUMMARY_DIRECTION,
            "points": points,
            "series": series,
        }
        path = self.store.root / "reports" / "development_learning_curve.json"
        self.store.atomic_json(path, value)
        return value

    def _write_direct_block_complete(
        self,
        *,
        round_index: int,
        case_limit: int | None,
        run_manifest_sha256: str,
        input_version: str,
        input_skills: list[SkillContract],
        trajectories: list[ResearchTrajectory],
        admission_report: dict[str, Any],
        learning_report: dict[str, Any],
        maintenance_path: Path | None,
    ) -> dict[str, Any]:
        batch = self.training_plan.batches[round_index - 1]
        name = self._direct_block_manifest_name(batch.batch_id)
        path = self.store.root / "manifests" / f"{name}.json"
        if path.is_file():
            return self._validate_direct_block_complete(
                round_index=round_index,
                case_limit=case_limit,
                run_manifest_sha256=run_manifest_sha256,
                expected_input_ids=sorted(skill.skill_id for skill in input_skills),
                expected_input_hash=skill_library_sha256(input_skills),
                expected_input_version=input_version,
            )
        expected_matrix = self._training_round_expected_matrix(
            round_index,
            case_limit=case_limit,
            input_skill_library_sha256=skill_library_sha256(input_skills),
            input_skills=input_skills,
        )
        expected_by_id = {item["trajectory_id"]: item for item in expected_matrix}
        actual_by_id = {item.trajectory_id: item for item in trajectories}
        if set(actual_by_id) != set(expected_by_id) or len(actual_by_id) != len(trajectories):
            raise ExecutionError("block output differs from the frozen training matrix")
        for trajectory_id, expected in expected_by_id.items():
            trajectory = actual_by_id[trajectory_id]
            if any(getattr(trajectory, key) != value for key, value in expected.items()):
                raise ExecutionError(f"training trajectory identity drift: {trajectory_id}")
        admission_path = self._skill_admission_report_path(round_index)
        persisted_admission = json.loads(admission_path.read_text(encoding="utf-8"))
        if canonical_json_sha256(persisted_admission) != canonical_json_sha256(admission_report):
            raise ExecutionError("skill-admission argument differs from persisted bytes")
        learning_path = self.store.root / "reports" / f"learning_checkpoint_{round_index:02d}.json"
        persisted_learning = json.loads(learning_path.read_text(encoding="utf-8"))
        if canonical_json_sha256(persisted_learning) != canonical_json_sha256(learning_report):
            raise ExecutionError("learning-checkpoint argument differs from persisted bytes")
        curve_path = self._verify_artifact_record(
            learning_report["development_curve_artifact"],
            expected_path=self._learning_curve_point_path(round_index),
            label="development curve point",
        )
        try:
            curve_point = json.loads(curve_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ExecutionError("development curve point is unreadable") from exc
        if not isinstance(curve_point, dict):
            raise ExecutionError("development curve point must be an object")
        if curve_point.get("schema_version") in {
            PARENT_COHORT_CURVE_POINT_SCHEMA,
            CURRENT_LIBRARY_IDENTITY_CURVE_POINT_SCHEMA,
        }:
            curve_point = self._validate_learning_curve_point_artifact(
                round_index=round_index,
                case_limit=case_limit,
                run_manifest_sha256=run_manifest_sha256,
                expected_input_skill_ids=sorted(skill.skill_id for skill in input_skills),
                expected_input_skill_library_sha256=skill_library_sha256(input_skills),
                expected_input_skill_library_version=input_version,
                artifact_record=learning_report["development_curve_artifact"],
            )
        self._load_validated_library_effect_disposition(
            round_index=round_index,
            run_manifest_sha256=run_manifest_sha256,
            input_version=input_version,
            input_skills=input_skills,
            curve_point=curve_point,
            require_continue=True,
        )
        teacher_path = self.store.root / "manifests" / f"teacher_round_{round_index:02d}.json"
        health_path = self.store.root / "health" / f"pre_scoring_health_{batch.batch_id}.json"
        value = {
            "schema_version": 5,
            "run_id": self.run_id,
            "run_manifest_sha256": run_manifest_sha256,
            "round": round_index,
            "batch_id": batch.batch_id,
            "stage": "direct_skill_accumulation_complete",
            "case_limit": case_limit,
            "trajectory_schema_version": self._trajectory_protocol_version(),
            "evaluation_schema_version": self._evaluation_protocol_version(),
            "judge_qualification_contract_sha256": self.judge_qualification_contract_sha256,
            "input_active_skill_ids": sorted(skill.skill_id for skill in input_skills),
            "input_skill_library_version": input_version,
            "input_skill_library_sha256": skill_library_sha256(input_skills),
            "expected_matrix_sha256": canonical_json_sha256(expected_matrix),
            "trajectory_artifacts": {
                trajectory_id: self._relative_artifact_record(
                    self.store.trajectory_path(batch.batch_id, trajectory_id)
                )
                for trajectory_id in sorted(actual_by_id)
            },
            "evaluation_artifacts": {
                trajectory_id: self._relative_artifact_record(
                    self.store.evaluation_path(trajectory_id)
                )
                for trajectory_id in sorted(actual_by_id)
            },
            "health_artifact": self._relative_artifact_record(health_path),
            "teacher_artifact": self._relative_artifact_record(teacher_path),
            "skill_admission_artifact": self._relative_artifact_record(admission_path),
            "development_curve_artifact": learning_report["development_curve_artifact"],
            "learning_checkpoint_artifact": self._relative_artifact_record(learning_path),
            "maintenance_artifact": (
                self._relative_artifact_record(maintenance_path)
                if maintenance_path is not None
                else None
            ),
            "admitted_skill_ids": list(admission_report["admitted_skill_ids"]),
            "rejected_skill_ids": sorted(
                str(item["skill_id"])
                for item in admission_report["records"]
                if not bool(item.get("valid"))
            ),
            "output_active_skill_ids": list(admission_report["output_active_skill_ids"]),
            "output_skill_library_version": admission_report["output_skill_library_version"],
            "output_skill_library_sha256": admission_report["output_skill_library_sha256"],
            "completed_at": datetime.now(UTC).isoformat(),
        }
        self.store.write_manifest(name, value, overwrite=False)
        return self._validate_direct_block_complete(
            round_index=round_index,
            case_limit=case_limit,
            run_manifest_sha256=run_manifest_sha256,
            expected_input_ids=value["input_active_skill_ids"],
            expected_input_hash=value["input_skill_library_sha256"],
            expected_input_version=input_version,
        )

    def _validate_direct_block_complete(
        self,
        *,
        round_index: int,
        case_limit: int | None,
        run_manifest_sha256: str,
        expected_input_ids: list[str],
        expected_input_hash: str,
        expected_input_version: str,
    ) -> dict[str, Any]:
        batch = self.training_plan.batches[round_index - 1]
        name = self._direct_block_manifest_name(batch.batch_id)
        try:
            complete = self.store.read_manifest(name)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise ExecutionError(f"invalid direct block completion: {batch.batch_id}") from exc
        bindings = {
            "schema_version": 5,
            "run_id": self.run_id,
            "run_manifest_sha256": run_manifest_sha256,
            "round": round_index,
            "batch_id": batch.batch_id,
            "stage": "direct_skill_accumulation_complete",
            "case_limit": case_limit,
            "trajectory_schema_version": self._trajectory_protocol_version(),
            "evaluation_schema_version": self._evaluation_protocol_version(),
            "judge_qualification_contract_sha256": self.judge_qualification_contract_sha256,
            "input_active_skill_ids": expected_input_ids,
            "input_skill_library_version": expected_input_version,
            "input_skill_library_sha256": expected_input_hash,
        }
        drift = [key for key, value in bindings.items() if complete.get(key) != value]
        if drift:
            raise ExecutionError(
                f"direct block completion binding drift: {batch.batch_id}; fields={drift}"
            )
        input_skills = self._skills_for_library_version(expected_input_version)
        if (
            sorted(skill.skill_id for skill in input_skills) != expected_input_ids
            or skill_library_sha256(input_skills) != expected_input_hash
        ):
            raise ExecutionError("direct block input library bytes drifted")
        expected_matrix = self._training_round_expected_matrix(
            round_index,
            case_limit=case_limit,
            input_skill_library_sha256=expected_input_hash,
            input_skills=input_skills,
        )
        if complete.get("expected_matrix_sha256") != canonical_json_sha256(expected_matrix):
            raise ExecutionError("direct block expected matrix drifted")
        expected_ids = {item["trajectory_id"] for item in expected_matrix}
        for field, label in (
            ("trajectory_artifacts", "training trajectory"),
            ("evaluation_artifacts", "semantic evaluation"),
        ):
            records = complete.get(field)
            if not isinstance(records, dict) or set(records) != expected_ids:
                raise ExecutionError(f"direct block {label} artifact set drifted")
            for trajectory_id, record in records.items():
                expected_path = (
                    self.store.trajectory_path(batch.batch_id, trajectory_id)
                    if field == "trajectory_artifacts"
                    else self.store.evaluation_path(trajectory_id)
                )
                self._verify_artifact_record(record, expected_path=expected_path, label=label)
        admission_path = self._verify_artifact_record(
            complete["skill_admission_artifact"],
            expected_path=self._skill_admission_report_path(round_index),
            label="direct skill admission",
        )
        admission, _ = self._load_direct_admission_report(
            round_index=round_index,
            expected_baseline_ids=expected_input_ids,
            expected_baseline_hash=expected_input_hash,
        )
        if sha256_file(admission_path) != complete["skill_admission_artifact"]["sha256"]:
            raise ExecutionError("direct skill-admission report hash drifted")
        for key in (
            "admitted_skill_ids",
            "output_active_skill_ids",
            "output_skill_library_version",
            "output_skill_library_sha256",
        ):
            if complete.get(key) != admission.get(key):
                raise ExecutionError(f"direct skill transition drift: {key}")
        if round_index == len(self.training_plan.batches) and complete.get("admitted_skill_ids"):
            raise ExecutionError(
                "final training block cannot admit a new increment without a later "
                "training block to observe it"
            )
        output_skills = self._skills_for_library_version(
            str(complete["output_skill_library_version"])
        )
        if (
            sorted(skill.skill_id for skill in output_skills) != complete["output_active_skill_ids"]
            or skill_library_sha256(output_skills) != complete["output_skill_library_sha256"]
        ):
            raise ExecutionError("direct block output library bytes drifted")
        curve_path = self._verify_artifact_record(
            complete["development_curve_artifact"],
            expected_path=self._learning_curve_point_path(round_index),
            label="development curve point",
        )
        try:
            curve_point = json.loads(curve_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ExecutionError("development curve point is unreadable") from exc
        if not isinstance(curve_point, dict):
            raise ExecutionError("development curve point must be an object")
        if curve_point.get("schema_version") in {
            PARENT_COHORT_CURVE_POINT_SCHEMA,
            CURRENT_LIBRARY_IDENTITY_CURVE_POINT_SCHEMA,
        }:
            curve_point = self._validate_learning_curve_point_artifact(
                round_index=round_index,
                case_limit=case_limit,
                run_manifest_sha256=run_manifest_sha256,
                expected_input_skill_ids=expected_input_ids,
                expected_input_skill_library_sha256=expected_input_hash,
                expected_input_skill_library_version=expected_input_version,
                artifact_record=complete["development_curve_artifact"],
            )
        self._load_validated_library_effect_disposition(
            round_index=round_index,
            run_manifest_sha256=run_manifest_sha256,
            input_version=expected_input_version,
            input_skills=input_skills,
            curve_point=curve_point,
            require_continue=True,
        )
        learning_path = self._verify_artifact_record(
            complete["learning_checkpoint_artifact"],
            expected_path=(
                self.store.root / "reports" / f"learning_checkpoint_{round_index:02d}.json"
            ),
            label="learning checkpoint",
        )
        learning = json.loads(learning_path.read_text(encoding="utf-8"))
        if (
            learning.get("schema_version") != LEARNING_CHECKPOINT_SCHEMA
            or learning.get("measured_input_active_skill_ids") != expected_input_ids
            or learning.get("measured_input_skill_library_sha256") != expected_input_hash
            or learning.get("admitted_from_current_block") != complete["admitted_skill_ids"]
            or learning.get("active_skill_ids") != complete["output_active_skill_ids"]
            or learning.get("active_skill_library_sha256")
            != complete["output_skill_library_sha256"]
            or learning.get("development_curve_artifact")
            != self._relative_artifact_record(curve_path)
        ):
            raise ExecutionError("direct learning checkpoint drifted")
        self._verify_artifact_record(
            complete["health_artifact"],
            expected_path=(
                self.store.root / "health" / f"pre_scoring_health_{batch.batch_id}.json"
            ),
            label="pre-scoring health",
        )
        teacher_path = self._verify_artifact_record(
            complete["teacher_artifact"],
            expected_path=(self.store.root / "manifests" / f"teacher_round_{round_index:02d}.json"),
            label="teacher round",
        )
        teacher_manifest = json.loads(teacher_path.read_text(encoding="utf-8"))
        expected_teacher_evidence_created = round_index < len(self.training_plan.batches)
        if (
            _playbook_teacher_evidence_created(
                teacher_manifest,
                round_index=round_index,
                total_rounds=len(self.training_plan.batches),
            )
            is not expected_teacher_evidence_created
            or learning.get("teacher_evidence_created") is not expected_teacher_evidence_created
        ):
            raise ExecutionError("direct teacher/checkpoint evidence lifecycle drifted")
        maintenance = complete.get("maintenance_artifact")
        interval = int(self.experiment["skill_admission"]["maintenance_interval_blocks"])
        expected_maintenance = round_index % interval == 0 or round_index == len(
            self.training_plan.batches
        )
        if expected_maintenance != (maintenance is not None):
            raise ExecutionError("library-maintenance schedule drifted")
        if maintenance is not None:
            self._verify_artifact_record(
                maintenance,
                expected_path=(
                    self.store.root / "reports" / f"library_maintenance_{round_index:02d}.json"
                ),
                label="library maintenance",
            )
        return complete

    def _load_validated_training_summary(
        self,
        *,
        run_manifest_sha256: str,
    ) -> TrainingSummary:
        path = self.store.root / "manifests" / "training_complete.json"
        if not path.is_file():
            raise ExecutionError("training_complete manifest is missing")
        try:
            summary = TrainingSummary.model_validate(self.store.read_manifest("training_complete"))
        except (ValueError, TypeError, OSError, json.JSONDecodeError) as exc:
            raise ExecutionError("training_complete is not current schema-6") from exc
        rounds = len(self.training_plan.batches)
        if (
            summary.run_id != self.run_id
            or summary.run_manifest_sha256 != run_manifest_sha256
            or summary.rounds_completed != rounds
        ):
            raise ExecutionError("training_complete binding drift")
        bootstrap, _ = self.initial_skill_library()
        previous_ids = sorted(skill.skill_id for skill in bootstrap)
        previous_hash = skill_library_sha256(bootstrap)
        previous_version = FORMAL_INITIAL_SKILL_LIBRARY_ID
        completion_hashes: dict[str, str] = {}
        admission_hashes: dict[str, str] = {}
        maintenance_hashes: dict[str, str] = {}
        admitted: list[str] = []
        rejected: list[str] = []
        for round_index, batch in enumerate(self.training_plan.batches, start=1):
            complete_path = (
                self.store.root
                / "manifests"
                / f"{self._direct_block_manifest_name(batch.batch_id)}.json"
            )
            try:
                stored = json.loads(complete_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ExecutionError("training block checkpoint is unreadable") from exc
            if stored.get("stage") == LEGACY_COHORT_REJECTION_BLOCK_STAGE:
                raise ExecutionError(
                    "legacy cohort-rejection checkpoint is not a current formal result"
                )
            complete = self._validate_direct_block_complete(
                round_index=round_index,
                case_limit=summary.case_limit,
                run_manifest_sha256=run_manifest_sha256,
                expected_input_ids=previous_ids,
                expected_input_hash=previous_hash,
                expected_input_version=previous_version,
            )
            completion_hashes[batch.batch_id] = sha256_file(complete_path)
            if complete.get("skill_admission_artifact") is not None:
                admission_hashes[batch.batch_id] = complete["skill_admission_artifact"]["sha256"]
            if complete.get("maintenance_artifact") is not None:
                maintenance_hashes[batch.batch_id] = complete["maintenance_artifact"]["sha256"]
            admitted.extend(complete["admitted_skill_ids"])
            rejected.extend(complete["rejected_skill_ids"])
            previous_ids = list(complete["output_active_skill_ids"])
            previous_hash = str(complete["output_skill_library_sha256"])
            previous_version = str(complete["output_skill_library_version"])
        if (
            summary.round_completion_manifests != completion_hashes
            or summary.round_completion_set_sha256 != canonical_json_sha256(completion_hashes)
            or summary.skill_admission_reports != admission_hashes
            or summary.library_maintenance_reports != maintenance_hashes
            or summary.admitted_skill_ids != admitted
            or summary.rejected_skill_ids != rejected
        ):
            raise ExecutionError("training_complete accumulated evidence drift")
        curve_path = self.store.root / "reports" / "development_learning_curve.json"
        curve = json.loads(curve_path.read_text(encoding="utf-8"))
        if (
            summary.development_learning_curve_sha256 != sha256_file(curve_path)
            or curve.get("status") != "complete"
            or curve.get("completed_points") != rounds
        ):
            raise ExecutionError("final development learning curve binding drift")
        active = self.active_skills()
        if (
            summary.active_skill_ids != sorted(skill.skill_id for skill in active)
            or summary.active_skill_library_sha256 != skill_library_sha256(active)
            or summary.active_skill_library_version
            != (self.registry.current() or FORMAL_INITIAL_SKILL_LIBRARY_ID)
            or summary.active_skill_ids != previous_ids
            or summary.active_skill_library_sha256 != previous_hash
            or summary.active_skill_library_version != previous_version
        ):
            raise ExecutionError("training_complete frozen skill library drift")
        final_holdout = self._ensure_final_training_holdout_safeguard(
            run_manifest_sha256=run_manifest_sha256,
            case_limit=summary.case_limit,
            create_if_missing=False,
        )
        summary_holdout = {
            "arms_frozen": summary.final_training_holdout_arms_frozen_artifact,
            "report": summary.final_training_holdout_artifact,
            "disposition": summary.final_training_holdout_disposition_artifact,
            "isolation": (summary.final_training_holdout_intervention_isolation_artifact),
        }
        if summary_holdout != final_holdout:
            raise ExecutionError("training_complete final B8 safeguard binding drift")
        return summary

    def train(self, *, case_limit: int | None = None) -> TrainingSummary:
        """Run eight sequential source-grounded skill-accumulation blocks."""

        rounds = int(self.experiment["execution"]["evolution_rounds"])
        if rounds != len(self.training_plan.batches):
            raise ExecutionError("evolution_rounds must match the accumulation block plan")
        run_manifest_sha256 = self._verified_run_manifest_sha256()
        complete_path = self.store.root / "manifests" / "training_complete.json"
        if complete_path.is_file():
            summary = self._load_validated_training_summary(run_manifest_sha256=run_manifest_sha256)
            if summary.case_limit != case_limit:
                raise ExecutionError("training_complete case_limit differs from requested matrix")
            return summary

        bootstrap, _ = self.initial_skill_library()
        previous_ids = sorted(skill.skill_id for skill in bootstrap)
        previous_hash = skill_library_sha256(bootstrap)
        previous_version = FORMAL_INITIAL_SKILL_LIBRARY_ID
        completion_hashes: dict[str, str] = {}
        admission_hashes: dict[str, str] = {}
        maintenance_hashes: dict[str, str] = {}
        admitted: list[str] = []
        rejected: list[str] = []
        rounds_completed = 0
        final_holdout_artifacts: dict[str, dict[str, str]] | None = None
        for round_index, batch in enumerate(self.training_plan.batches, start=1):
            block_name = self._direct_block_manifest_name(batch.batch_id)
            block_path = self.store.root / "manifests" / f"{block_name}.json"
            if block_path.is_file():
                stored_block = json.loads(block_path.read_text(encoding="utf-8"))
                if stored_block.get("stage") == LEGACY_COHORT_REJECTION_BLOCK_STAGE:
                    raise ExecutionError(
                        "legacy cohort-rejection checkpoint cannot resume under the "
                        "direct-accumulation protocol; use a fresh run_id"
                    )
                else:
                    block = self._validate_direct_block_complete(
                        round_index=round_index,
                        case_limit=case_limit,
                        run_manifest_sha256=run_manifest_sha256,
                        expected_input_ids=previous_ids,
                        expected_input_hash=previous_hash,
                        expected_input_version=previous_version,
                    )
            else:
                current = self.active_skills()
                current_ids = sorted(skill.skill_id for skill in current)
                current_hash = skill_library_sha256(current)
                admission_path = self._skill_admission_report_path(round_index)
                disposition_path = self._library_effect_disposition_path(round_index)
                if (
                    round_index == rounds
                    and disposition_path.is_file()
                    and not self._final_training_holdout_arms_path().is_file()
                ):
                    raise ExecutionError(
                        "B8 disposition exists without the mandatory pre-disposition all-arm freeze"
                    )
                if current_ids == previous_ids and current_hash == previous_hash:
                    input_skills = self._skills_for_library_version(previous_version)
                elif admission_path.is_file():
                    interrupted = json.loads(admission_path.read_text(encoding="utf-8"))
                    if (
                        interrupted.get("baseline_active_skill_ids") != previous_ids
                        or interrupted.get("baseline_skill_library_sha256") != previous_hash
                        or interrupted.get("output_active_skill_ids") != current_ids
                        or interrupted.get("output_skill_library_sha256") != current_hash
                    ):
                        raise ExecutionError("active library does not match interrupted transition")
                    input_skills = self._skills_for_library_version(previous_version)
                else:
                    raise ExecutionError("active library does not match completed block chain")

                trajectories = self.generate_training_round(
                    round_index,
                    case_limit=case_limit,
                    input_skills=input_skills,
                )
                evaluations = self.score_trajectories(
                    trajectories,
                    self.main_adapter,
                    expected_skill_libraries=self._training_skill_memory_contract(input_skills),
                )
                frozen_parent: list[ResearchTrajectory] | None = None
                frozen_parent_evaluations: dict[str, TrajectoryEvaluation] | None = None
                if round_index == rounds:
                    input_hash = skill_library_sha256(input_skills)
                    current_for_holdout = self._learning_curve_current_trajectories(
                        round_index=round_index,
                        trajectories=trajectories,
                        input_skill_library_sha256=input_hash,
                    )
                    current_holdout_evaluations = {
                        item.trajectory_id: evaluations[item.trajectory_id]
                        for item in current_for_holdout
                    }
                    empty_for_holdout = self.generate_learning_curve_shadow(
                        round_index=round_index,
                        current_trajectories=current_for_holdout,
                    )
                    empty_hash = skill_library_sha256([])
                    empty_holdout_evaluations = self.score_trajectories(
                        empty_for_holdout,
                        self.main_adapter,
                        expected_skill_libraries={empty_hash: []},
                        score_observed_terminal_failures=True,
                    )
                    final_parent_context = self._previous_block_skill_increment(
                        round_index=round_index,
                        input_version=previous_version,
                        input_skills=input_skills,
                    )
                    if final_parent_context is not None:
                        frozen_parent = self.generate_parent_cohort_shadow(
                            round_index=round_index,
                            current_trajectories=current_for_holdout,
                            parent_skills=list(final_parent_context["parent_skills"]),
                        )
                        parent_hash = skill_library_sha256(
                            list(final_parent_context["parent_skills"])
                        )
                        frozen_parent_evaluations = self.score_trajectories(
                            frozen_parent,
                            self.main_adapter,
                            expected_skill_libraries={
                                parent_hash: list(final_parent_context["parent_skills"])
                            },
                            score_observed_terminal_failures=True,
                        )
                    self._freeze_final_training_holdout_arms(
                        round_index=round_index,
                        case_limit=case_limit,
                        run_manifest_sha256=run_manifest_sha256,
                        input_version=previous_version,
                        input_skills=input_skills,
                        current=current_for_holdout,
                        current_evaluations=current_holdout_evaluations,
                        empty=empty_for_holdout,
                        empty_evaluations=empty_holdout_evaluations,
                        parent_context=final_parent_context,
                        parent=frozen_parent,
                        parent_evaluations=frozen_parent_evaluations,
                    )
                curve_point = self.prepare_development_curve_point(
                    round_index=round_index,
                    case_limit=case_limit,
                    run_manifest_sha256=run_manifest_sha256,
                    input_version=previous_version,
                    input_skills=input_skills,
                    trajectories=trajectories,
                    evaluations=evaluations,
                    frozen_parent=frozen_parent,
                    frozen_parent_evaluations=frozen_parent_evaluations,
                )
                disposition = self.write_library_effect_disposition(
                    round_index=round_index,
                    run_manifest_sha256=run_manifest_sha256,
                    input_version=previous_version,
                    input_skills=input_skills,
                    curve_point=curve_point,
                )
                development_curve_artifact = self._relative_artifact_record(
                    self._learning_curve_point_path(round_index)
                )
                if disposition["decision"] not in {
                    "continue_training_no_pending_cohort",
                    "observe_increment_continue_training",
                }:
                    raise ExecutionError("unknown prequential diagnostic transition")
                if round_index == rounds:
                    final_holdout_artifacts = self._ensure_final_training_holdout_safeguard(
                        run_manifest_sha256=run_manifest_sha256,
                        case_limit=case_limit,
                        create_if_missing=True,
                    )
                if admission_path.is_file():
                    admission_report, admitted_paths = self._load_direct_admission_report(
                        round_index=round_index,
                        expected_baseline_ids=previous_ids,
                        expected_baseline_hash=previous_hash,
                    )
                else:
                    final_round_budget = int(
                        self.experiment["learning_curve"]["incremental_effect_diagnostic"][
                            "final_block_new_skill_budget"
                        ]
                    )
                    candidate_budget = (
                        final_round_budget
                        if round_index == rounds
                        else int(self.experiment["execution"]["maximum_new_skills_per_block"])
                    )
                    candidate_paths = self.propose_candidates(
                        round_index=round_index,
                        trajectories=trajectories,
                        evaluations=evaluations,
                        candidate_budget=candidate_budget,
                    )
                    admitted_paths = self.admit_source_grounded_candidates(
                        round_index=round_index,
                        candidates=candidate_paths,
                    )
                    admission_report, admitted_paths = self._load_direct_admission_report(
                        round_index=round_index,
                        expected_baseline_ids=previous_ids,
                        expected_baseline_hash=previous_hash,
                    )
                committed_version = self._activate_source_grounded_skills(
                    round_index=round_index,
                    candidate_paths=admitted_paths,
                )
                if committed_version != admission_report["output_skill_library_version"]:
                    raise ExecutionError("direct skill activation committed wrong version")
                learning = self.write_learning_checkpoint(
                    round_index=round_index,
                    case_limit=case_limit,
                    run_manifest_sha256=run_manifest_sha256,
                    admitted_skill_ids=list(admission_report["admitted_skill_ids"]),
                    input_skills=input_skills,
                    input_version=previous_version,
                    development_curve_artifact=development_curve_artifact,
                )
                maintenance_path = self.write_library_maintenance_report(
                    round_index=round_index,
                    input_skills=input_skills,
                )
                block = self._write_direct_block_complete(
                    round_index=round_index,
                    case_limit=case_limit,
                    run_manifest_sha256=run_manifest_sha256,
                    input_version=previous_version,
                    input_skills=input_skills,
                    trajectories=trajectories,
                    admission_report=admission_report,
                    learning_report=learning,
                    maintenance_path=maintenance_path,
                )

            if round_index == rounds and block.get("admitted_skill_ids"):
                raise ExecutionError(
                    "final training block produced an increment with no later development block"
                )
            if round_index == rounds and final_holdout_artifacts is None:
                final_holdout_artifacts = self._ensure_final_training_holdout_safeguard(
                    run_manifest_sha256=run_manifest_sha256,
                    case_limit=case_limit,
                    create_if_missing=False,
                )
            completion_hashes[batch.batch_id] = sha256_file(block_path)
            if block.get("skill_admission_artifact") is not None:
                admission_hashes[batch.batch_id] = block["skill_admission_artifact"]["sha256"]
            if block.get("maintenance_artifact") is not None:
                maintenance_hashes[batch.batch_id] = block["maintenance_artifact"]["sha256"]
            admitted.extend(block["admitted_skill_ids"])
            rejected.extend(block["rejected_skill_ids"])
            previous_ids = list(block["output_active_skill_ids"])
            previous_hash = str(block["output_skill_library_sha256"])
            previous_version = str(block["output_skill_library_version"])
            rounds_completed = round_index
            self.write_development_learning_curve_summary()

        curve = self.write_development_learning_curve_summary()
        if curve["completed_points"] != rounds:
            raise ExecutionError("training completed without all prequential curve points")
        active = self.active_skills()
        if final_holdout_artifacts is None:
            raise ExecutionError("training completed without the final B8 freeze safeguard")
        summary = TrainingSummary(
            run_id=self.run_id,
            run_manifest_sha256=run_manifest_sha256,
            trajectory_schema_version=self._trajectory_protocol_version(),
            evaluation_schema_version=self._evaluation_protocol_version(),
            case_limit=case_limit,
            rounds_completed=rounds_completed,
            round_completion_manifests=completion_hashes,
            round_completion_set_sha256=canonical_json_sha256(completion_hashes),
            admitted_skill_ids=admitted,
            rejected_skill_ids=rejected,
            skill_admission_reports=admission_hashes,
            library_maintenance_reports=maintenance_hashes,
            active_skill_ids=sorted(skill.skill_id for skill in active),
            active_skill_library_version=(
                self.registry.current() or FORMAL_INITIAL_SKILL_LIBRARY_ID
            ),
            active_skill_library_sha256=skill_library_sha256(active),
            development_learning_curve_sha256=sha256_file(
                self.store.root / "reports" / "development_learning_curve.json"
            ),
            final_training_holdout_arms_frozen_artifact=final_holdout_artifacts["arms_frozen"],
            final_training_holdout_artifact=final_holdout_artifacts["report"],
            final_training_holdout_disposition_artifact=final_holdout_artifacts["disposition"],
            final_training_holdout_intervention_isolation_artifact=(
                final_holdout_artifacts["isolation"]
            ),
            completed_at=datetime.now(UTC).isoformat(),
        )
        self.store.write_manifest(
            "training_complete",
            summary.model_dump(mode="json", exclude={"content_sha256"}),
            overwrite=False,
        )
        return self._load_validated_training_summary(run_manifest_sha256=run_manifest_sha256)

    def validated_external_ready_training_freeze(
        self,
    ) -> tuple[TrainingSummary, list[SkillContract], dict[str, Any]]:
        """Load one non-empty, full-matrix training freeze that may enter CN30.

        This public boundary is shared by the training-run diagnostic and the
        four-arm paper-table controller.  In particular, the latter can validate
        the source run without constructing an external-data adapter or invoking
        the domain router first.
        """

        protocol_integrity = assert_locked_external_protocol_integrity(self.store.root)
        run_manifest_sha256 = self._verified_run_manifest_sha256()
        frozen_path = self.store.root / "manifests" / "training_complete.json"
        if not frozen_path.is_file():
            raise ExecutionError("external test requires a frozen training_complete manifest")
        active = self.active_skills()
        active_hash = skill_library_sha256(active)
        summary = self._load_validated_training_summary(run_manifest_sha256=run_manifest_sha256)
        if summary.case_limit is not None:
            raise ExecutionError(
                "external test requires the complete frozen 128-case training matrix"
            )
        if summary.active_skill_library_version != (
            self.registry.current() or FORMAL_INITIAL_SKILL_LIBRARY_ID
        ):
            raise ExecutionError("active skill library version changed after training freeze")
        if active_hash != summary.active_skill_library_sha256:
            raise ExecutionError("active skill library changed after training freeze")
        if not active:
            raise ExecutionError(
                "external test is not informative with an empty learned skill library; "
                "preserve the completed no-skill training result and apply the "
                "predeclared method stop rule before consuming the held-out public "
                "external benchmark"
            )
        return summary, active, protocol_integrity

    def external_test(self) -> dict[str, Any]:
        summary, active, protocol_integrity = self.validated_external_ready_training_freeze()
        run_manifest_sha256 = summary.run_manifest_sha256
        frozen_path = self.store.root / "manifests" / "training_complete.json"
        active_hash = summary.active_skill_library_sha256
        arm_specs = self.external_arm_specs(active)
        arm_by_id = {str(item["arm_id"]): item for item in arm_specs}
        values: dict[str, list[ResearchTrajectory]] = {
            str(item["arm_id"]): [] for item in arm_specs
        }
        partition = "external_test"
        runner = self._runner(paired=True, cache_namespace=partition)
        requests: list[tuple[Any, ...]] = []
        for case_id in self.external_adapter.case_ids():
            for persona_id in self.experiment["personas"]:
                persona = self.external_adapter.persona(persona_id)
                for seed in self.experiment["trajectory_sampling"]["external_evaluation_seeds"]:
                    for arm in arm_specs:
                        method = str(arm["arm_id"])
                        skills = list(arm["skills"])
                        intervention_hash = str(arm["intervention_sha256"])
                        identity = trajectory_identity(
                            run_id=self.run_id,
                            partition=partition,
                            method=method,
                            case_id=case_id,
                            persona=persona_id,
                            seed=int(seed),
                            sample_index=0,
                            skill_library_version=intervention_hash,
                        )
                        requests.append(
                            (
                                case_id,
                                persona,
                                skills,
                                identity,
                                method,
                                int(seed),
                                f"external.{case_id}.{persona_id}.seed_{seed}",
                                intervention_hash,
                            )
                        )

        def run_one(request: tuple[Any, ...]) -> ResearchTrajectory:
            (
                case_id,
                persona,
                skills,
                trajectory_id,
                method,
                seed,
                group_id,
                skill_hash,
            ) = request
            return self._load_or_run(
                runner=runner,
                adapter=self.external_adapter,
                case_id=case_id,
                persona=persona,
                skills=skills,
                trajectory_id=trajectory_id,
                method=method,
                partition=partition,
                seed=seed,
                sample_index=0,
                group_id=group_id,
                skill_hash=skill_hash,
                # The treatment is one global playbook and the control has no
                # documents, so neither arm needs case-level skill routing.
                domain_override="general",
            )

        completed = parallel_map_ordered(
            requests,
            run_one,
            max_workers=int(self.experiment["execution"]["rollout_workers"]),
            label="external_test_rollout",
            fail_fast=True,
        )
        for request, trajectory in zip(requests, completed, strict=True):
            method = str(request[4])
            values[method].append(trajectory)
        all_values = [trajectory for arm in arm_specs for trajectory in values[str(arm["arm_id"])]]
        failed = [item.trajectory_id for item in all_values if item.status == "error"]
        if failed:
            raise ExecutionError(f"external test rollout failures: {failed[:5]}")
        isolation = skill_library_intervention_isolation_report(
            values["legal_skill_evolve"],
            values["control_no_library"],
            {item.skill_id for item in active},
            partition,
            partition,
            require_distinct_partitions=False,
        )
        isolation_path = self.store.root / "health" / "external_test_skill_library_isolation.json"
        self.store.atomic_json(isolation_path, isolation)
        if not isolation["passed"]:
            raise ExecutionError(
                "external-test skill-library intervention isolation failed before "
                f"semantic scoring: report={isolation_path}; "
                f"failures={isolation['failure_count']}"
            )
        evaluations = self.score_trajectories(
            all_values,
            self.external_adapter,
            expected_skill_libraries={
                str(arm["intervention_sha256"]): list(arm["skills"]) for arm in arm_specs
            },
        )
        report: dict[str, Any] = {
            "schema_version": 8,
            "run_id": self.run_id,
            "run_manifest_sha256": run_manifest_sha256,
            "trajectory_schema_version": self._trajectory_protocol_version(),
            "training_complete_sha256": sha256_file(frozen_path),
            "round_completion_manifests": summary.round_completion_manifests,
            "round_completion_set_sha256": summary.round_completion_set_sha256,
            "evidence_role": TRAINING_RUN_EXTERNAL_EVIDENCE_ROLE,
            "publication_role": TRAINING_RUN_EXTERNAL_PUBLICATION_ROLE,
            "locked_external_protocol_integrity": protocol_integrity,
            "skill_library_intervention_isolation": self._relative_artifact_record(isolation_path),
            "arms": {},
            "comparison_contract": {
                "primary_paired_contrast": ("legal_skill_evolve_minus_control_no_library"),
                "additional_candidate_admission_contrasts": False,
                "arms": [
                    {
                        "arm_id": item["arm_id"],
                        "inference_role": item["inference_role"],
                        "knowledge_source": item["knowledge_source"],
                        "intervention_sha256": item["intervention_sha256"],
                        "executable_skill_ids": [skill.skill_id for skill in item["skills"]],
                        "selection_contract": item.get("selection_contract"),
                    }
                    for item in arm_specs
                ],
            },
        }
        official_names = tuple(self.experiment["evaluation"]["official_metrics"])
        safety_names = tuple(self.experiment["evaluation"]["safety_metrics"])
        operational_names = tuple(self.experiment["evaluation"]["operational_metrics"])
        judge_diagnostic_extractors = {
            "rubric_repair_rate": lambda item: float(item.rubric_repair_used),
            "fact_repair_rate": lambda item: float(item.fact_repair_used),
            "grounding_repair_rate": lambda item: float(item.grounding_repair_used),
            "rubric_normalization_rate": lambda item: float(bool(item.rubric_normalizations)),
            "fact_normalization_rate": lambda item: float(bool(item.fact_normalizations)),
            "grounding_normalization_rate": lambda item: float(bool(item.grounding_normalizations)),
        }
        judge_diagnostic_names = tuple(self.experiment["evaluation"]["judge_diagnostics"])
        for method, trajectories in values.items():
            metrics = [evaluations[item.trajectory_id].official_metrics for item in trajectories]
            safety = [evaluations[item.trajectory_id].safety_metrics for item in trajectories]
            report["arms"][method] = {
                "official_metrics": {
                    key: round(statistics.fmean(getattr(item, key) for item in metrics), 6)
                    for key in official_names
                },
                "safety_metrics": {
                    key: round(statistics.fmean(getattr(item, key) for item in safety), 6)
                    for key in safety_names
                },
                "operational_metrics": {
                    key: round(
                        statistics.fmean(
                            float(getattr(evaluations[item.trajectory_id].operational_metrics, key))
                            for item in trajectories
                        ),
                        6,
                    )
                    for key in operational_names
                },
                "judge_diagnostics": {
                    key: round(
                        statistics.fmean(
                            judge_diagnostic_extractors[key](evaluations[item.trajectory_id])
                            for item in trajectories
                        ),
                        6,
                    )
                    for key in judge_diagnostic_names
                },
                "behavior": trajectory_behavior_summary(
                    trajectories,
                    {item.skill_id for item in arm_by_id[method]["skills"]},
                ),
                "inference_role": arm_by_id[method]["inference_role"],
                "knowledge_source": arm_by_id[method]["knowledge_source"],
                "intervention_sha256": arm_by_id[method]["intervention_sha256"],
                "sessions": len(trajectories),
            }
        control = values["control_no_library"]
        treatment = values["legal_skill_evolve"]
        if len(control) != len(treatment):
            raise ExecutionError("external paired matrix has unequal arm sizes")
        for before, after in zip(control, treatment, strict=True):
            if before.group_id != after.group_id:
                raise ExecutionError("external paired matrix order/group mismatch")
        bootstrap = int(self.experiment["evaluation"]["bootstrap_samples"])
        confidence = float(self.experiment["evaluation"]["confidence_level"])
        bootstrap_seed = int(self.experiment["statistical_seed"])
        paired: dict[str, Any] = {}
        raw_p_values: dict[str, float] = {}
        for metric_name in (*official_names, *safety_names, *operational_names):
            section = (
                "official_metrics"
                if metric_name in official_names
                else "safety_metrics"
                if metric_name in safety_names
                else "operational_metrics"
            )
            before_values = [
                float(getattr(getattr(evaluations[item.trajectory_id], section), metric_name))
                for item in control
            ]
            after_values = [
                float(getattr(getattr(evaluations[item.trajectory_id], section), metric_name))
                for item in treatment
            ]
            # Personas and seeds repeat the same legal case and are not independent
            # experimental units.  Estimate uncertainty on case-mean paired deltas.
            deltas = clustered_mean_deltas(
                [item.case_id for item in control], before_values, after_values
            )
            paired[metric_name] = paired_bootstrap_interval(
                deltas,
                samples=bootstrap,
                confidence_level=confidence,
                seed=bootstrap_seed,
            ).model_dump(mode="json")
            raw_p_values[metric_name] = paired_sign_flip_p_value(
                deltas,
                samples=int(self.experiment["evaluation"]["randomization_samples"]),
                seed=bootstrap_seed,
            )
            paired[metric_name]["paired_p_value"] = raw_p_values[metric_name]
        report["paired_treatment_minus_control"] = paired
        paired_behavior = paired_behavior_estimates(
            control,
            treatment,
            {item.skill_id for item in active},
            bootstrap_samples=bootstrap,
            confidence_level=confidence,
            seed=bootstrap_seed,
        )
        for metric_name in PAIRED_BEHAVIOR_METRICS:
            before_values = [
                trajectory_behavior_values(item, set())[metric_name] for item in control
            ]
            after_values = [
                trajectory_behavior_values(item, {skill.skill_id for skill in active})[metric_name]
                for item in treatment
            ]
            deltas = clustered_mean_deltas(
                [item.case_id for item in control], before_values, after_values
            )
            p_value = paired_sign_flip_p_value(
                deltas,
                samples=int(self.experiment["evaluation"]["randomization_samples"]),
                seed=bootstrap_seed,
            )
            paired_behavior["metrics"][metric_name]["paired_p_value"] = p_value
            raw_p_values[metric_name] = p_value
        report["paired_behavior_treatment_minus_control"] = paired_behavior
        secondary = list(self.experiment["evaluation"]["secondary_endpoints"])
        adjusted = benjamini_hochberg({name: raw_p_values[name] for name in secondary})
        report["inference"] = {
            "primary_endpoint": self.experiment["evaluation"]["primary_endpoint"],
            "primary_p_value": raw_p_values[self.experiment["evaluation"]["primary_endpoint"]],
            "secondary_benjamini_hochberg": adjusted,
            "direction": "legal_skill_evolve_minus_control_no_library",
            "cluster_unit": "case_id",
            "case_clusters": len(set(item.case_id for item in control)),
            "session_pairs": len(control),
        }
        report["artifact_hashes"] = {
            item.trajectory_id: {
                "trajectory_sha256": sha256_file(
                    self.store.trajectory_path(item.partition, item.trajectory_id)
                ),
                "evaluation_sha256": sha256_file(self.store.evaluation_path(item.trajectory_id)),
            }
            for item in all_values
        }
        report["active_skill_library_sha256"] = active_hash
        report["completed_at"] = datetime.now(UTC).isoformat()
        self.store.atomic_json(self.store.root / "reports" / "external_test.json", report)
        return report

    def external_seed_sensitivity(self) -> dict[str, Any]:
        """Measure dialogue-seed stability after the frozen primary external test.

        This secondary analysis is deliberately downstream of both skill selection
        and the primary external report.  It cannot activate skills, change the
        library, or enter primary/BH inference.  Seed 42 trajectories are reused
        from the primary test; only the predeclared small subset receives new seeds.
        """

        assert_locked_external_protocol_integrity(self.store.root)
        run_manifest_sha256 = self._verified_run_manifest_sha256()
        frozen_path = self.store.root / "manifests" / "training_complete.json"
        primary_report_path = self.store.root / "reports" / "external_test.json"
        if not frozen_path.is_file():
            raise ExecutionError("seed sensitivity requires frozen training_complete")
        if not primary_report_path.is_file():
            raise ExecutionError("seed sensitivity requires completed primary external test")

        active = self.active_skills()
        active_hash = skill_library_sha256(active)
        training_summary = self._load_validated_training_summary(
            run_manifest_sha256=run_manifest_sha256
        )
        if training_summary.case_limit is not None:
            raise ExecutionError(
                "external seed sensitivity requires the complete frozen 128-case training matrix"
            )
        if training_summary.active_skill_library_version != (
            self.registry.current() or FORMAL_INITIAL_SKILL_LIBRARY_ID
        ):
            raise ExecutionError("active skill library version changed after training freeze")
        if active_hash != training_summary.active_skill_library_sha256:
            raise ExecutionError("active skill library changed after training freeze")
        try:
            primary_report = json.loads(primary_report_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ExecutionError("primary external report is unreadable") from exc
        if not isinstance(primary_report, dict) or primary_report.get("run_id") != self.run_id:
            raise ExecutionError("primary external report belongs to a different run")
        if (
            primary_report.get("schema_version") != 8
            or primary_report.get("evidence_role") != TRAINING_RUN_EXTERNAL_EVIDENCE_ROLE
            or primary_report.get("publication_role") != TRAINING_RUN_EXTERNAL_PUBLICATION_ROLE
        ):
            raise ExecutionError(
                "primary external report does not use the current benchmark-aware contract"
            )
        expected_primary_bindings = {
            "run_manifest_sha256": run_manifest_sha256,
            "trajectory_schema_version": self._trajectory_protocol_version(),
            "training_complete_sha256": sha256_file(frozen_path),
            "round_completion_manifests": training_summary.round_completion_manifests,
            "round_completion_set_sha256": training_summary.round_completion_set_sha256,
        }
        primary_binding_mismatches = [
            field
            for field, expected in expected_primary_bindings.items()
            if primary_report.get(field) != expected
        ]
        if primary_binding_mismatches:
            raise ExecutionError(
                "primary external report training binding changed: "
                + ", ".join(primary_binding_mismatches)
            )
        if primary_report.get("active_skill_library_sha256") != active_hash:
            raise ExecutionError("primary external test used a different frozen skill library")
        primary_report_sha256 = sha256_file(primary_report_path)

        sensitivity = self.experiment["seed_sensitivity"]
        if sensitivity.get("status") != "secondary_after_primary_external_test":
            raise ExecutionError("seed sensitivity protocol status is not executable")
        if bool(sensitivity.get("affects_candidate_selection")) or bool(
            sensitivity.get("affects_primary_inference")
        ):
            raise ExecutionError("seed sensitivity must remain outside selection and inference")
        primary_seed = int(sensitivity["primary_seed_reused"])
        main_seeds = [
            int(item)
            for item in self.experiment["trajectory_sampling"]["external_evaluation_seeds"]
        ]
        if main_seeds != [primary_seed]:
            raise ExecutionError(
                "primary external matrix must contain exactly the reused sensitivity seed"
            )
        additional_seeds = [int(item) for item in sensitivity["additional_dialogue_seeds"]]
        if not additional_seeds or len(additional_seeds) != len(set(additional_seeds)):
            raise ExecutionError("sensitivity dialogue seeds must be non-empty and unique")
        if primary_seed in additional_seeds:
            raise ExecutionError("sensitivity seeds must exclude the primary dialogue seed")
        case_ids = [str(item) for item in sensitivity["external_case_ids"]]
        personas = [str(item) for item in sensitivity["personas"]]
        if not case_ids or len(case_ids) != len(set(case_ids)):
            raise ExecutionError("sensitivity external cases must be non-empty and unique")
        unknown_cases = sorted(set(case_ids) - set(self.external_adapter.case_ids()))
        if unknown_cases:
            raise ExecutionError(f"unknown sensitivity external cases: {unknown_cases}")
        if personas != [str(item) for item in self.experiment["personas"]]:
            raise ExecutionError("sensitivity personas must equal the frozen four-persona matrix")

        report_path = self.store.root / "reports" / "external_seed_sensitivity.json"
        if report_path.is_file():
            report = json.loads(report_path.read_text(encoding="utf-8"))
            if report.get("active_skill_library_sha256") != active_hash:
                raise ExecutionError("persisted seed sensitivity used a different skill library")
            expected_contract = {
                "run_id": self.run_id,
                "run_manifest_sha256": run_manifest_sha256,
                "trajectory_schema_version": self._trajectory_protocol_version(),
                "training_complete_sha256": sha256_file(frozen_path),
                "round_completion_manifests": (training_summary.round_completion_manifests),
                "round_completion_set_sha256": (training_summary.round_completion_set_sha256),
                "status": "secondary_sampling_robustness_only",
                "publication_role": TRAINING_RUN_EXTERNAL_PUBLICATION_ROLE,
                "affects_candidate_selection": False,
                "affects_primary_inference": False,
                "case_ids": case_ids,
                "personas": personas,
                "primary_seed_reused": primary_seed,
                "additional_dialogue_seeds": additional_seeds,
                "primary_external_report_sha256": primary_report_sha256,
            }
            mismatches = [
                key for key, expected in expected_contract.items() if report.get(key) != expected
            ]
            if mismatches:
                raise ExecutionError(
                    "persisted seed sensitivity contract changed: " + ", ".join(mismatches)
                )
            trajectory_artifacts = report.get("trajectory_artifacts")
            if not isinstance(trajectory_artifacts, dict) or not trajectory_artifacts:
                raise ExecutionError("persisted seed sensitivity lacks trajectory artifacts")
            for trajectory_id, artifact in trajectory_artifacts.items():
                if not isinstance(artifact, dict):
                    raise ExecutionError("invalid persisted sensitivity trajectory artifact")
                partition_name = artifact.get("partition")
                expected_sha256 = artifact.get("sha256")
                if partition_name not in {"external_test", "external_seed_sensitivity"}:
                    raise ExecutionError("invalid persisted sensitivity trajectory partition")
                artifact_path = self.store.trajectory_path(partition_name, trajectory_id)
                if not artifact_path.is_file() or sha256_file(artifact_path) != expected_sha256:
                    raise ExecutionError(
                        f"persisted sensitivity trajectory is missing or changed: {trajectory_id}"
                    )
            return report

        primary_arm_by_id = {str(item["arm_id"]): item for item in self.external_arm_specs(active)}
        methods: tuple[tuple[str, list[SkillContract], str], ...] = tuple(
            (
                method,
                list(primary_arm_by_id[method]["skills"]),
                str(primary_arm_by_id[method]["intervention_sha256"]),
            )
            for method in ("control_no_library", "legal_skill_evolve")
        )
        skill_hashes = {method: intervention_hash for method, _, intervention_hash in methods}
        values_by_seed: dict[int, dict[str, list[ResearchTrajectory]]] = {
            seed: {method: [] for method, _, _ in methods}
            for seed in [primary_seed, *additional_seeds]
        }

        # Seed 42 is already part of the immutable primary matrix. Refuse to
        # regenerate it under a different partition or cache namespace.
        for case_id in case_ids:
            for persona_id in personas:
                for method, _, _ in methods:
                    identity = trajectory_identity(
                        run_id=self.run_id,
                        partition="external_test",
                        method=cast(Any, method),
                        case_id=case_id,
                        persona=persona_id,
                        seed=primary_seed,
                        sample_index=0,
                        skill_library_version=skill_hashes[method],
                    )
                    path = self.store.trajectory_path("external_test", identity)
                    if not path.is_file():
                        raise ExecutionError(
                            "primary seed trajectory missing from completed external test: "
                            f"{case_id}/{persona_id}/{method}"
                        )
                    values_by_seed[primary_seed][method].append(
                        self.store.load_model(path, ResearchTrajectory)
                    )

        partition = "external_seed_sensitivity"
        runner = self._runner(paired=True, cache_namespace=partition)
        requests: list[tuple[Any, ...]] = []
        for seed in additional_seeds:
            for case_id in case_ids:
                for persona_id in personas:
                    persona = self.external_adapter.persona(persona_id)
                    for method, skills, _ in methods:
                        identity = trajectory_identity(
                            run_id=self.run_id,
                            partition=partition,
                            method=cast(Any, method),
                            case_id=case_id,
                            persona=persona_id,
                            seed=seed,
                            sample_index=0,
                            skill_library_version=skill_hashes[method],
                        )
                        requests.append(
                            (
                                case_id,
                                persona,
                                skills,
                                identity,
                                method,
                                seed,
                                f"seed_sensitivity.{case_id}.{persona_id}.seed_{seed}",
                                skill_hashes[method],
                            )
                        )

        def run_one(request: tuple[Any, ...]) -> ResearchTrajectory:
            (
                case_id,
                persona,
                skills,
                identity,
                method,
                seed,
                group_id,
                skill_hash,
            ) = request
            return self._load_or_run(
                runner=runner,
                adapter=self.external_adapter,
                case_id=case_id,
                persona=persona,
                skills=skills,
                trajectory_id=identity,
                method=cast(Any, method),
                partition=partition,
                seed=seed,
                sample_index=0,
                group_id=group_id,
                skill_hash=skill_hash,
                domain_override="general",
            )

        completed = parallel_map_ordered(
            requests,
            run_one,
            max_workers=int(self.experiment["execution"]["rollout_workers"]),
            label="external_seed_sensitivity_rollout",
            fail_fast=True,
        )
        for request, trajectory in zip(requests, completed, strict=True):
            values_by_seed[int(request[5])][str(request[4])].append(trajectory)
        all_values = [
            trajectory
            for seed_values in values_by_seed.values()
            for method_values in seed_values.values()
            for trajectory in method_values
        ]
        failed = [item.trajectory_id for item in all_values if item.status == "error"]
        if failed:
            raise ExecutionError(f"seed sensitivity rollout failures: {failed[:5]}")
        evaluations = self.score_trajectories(
            all_values,
            self.external_adapter,
            expected_skill_libraries={
                intervention_hash: list(skills) for _, skills, intervention_hash in methods
            },
        )

        metric_sections: dict[str, str] = {
            "unique_disclosed_facts_per_question": "behavior",
            "unique_disclosed_facts": "behavior",
            "fact_coverage": "official_metrics",
            "inquiry": "official_metrics",
            "elicitation": "official_metrics",
            "fact_resolution": "official_metrics",
            "issue_resolution": "official_metrics",
            "resolution": "official_metrics",
            "fidelity": "official_metrics",
            "premature_final_rate": "safety_metrics",
            "unsupported_claim_rate": "safety_metrics",
            "belief_as_fact_rate": "safety_metrics",
            "repeated_question_rate": "safety_metrics",
            "critical_fact_recall": "safety_metrics",
        }
        bootstrap_samples = int(self.experiment["evaluation"]["bootstrap_samples"])
        confidence = float(self.experiment["evaluation"]["confidence_level"])
        statistical_seed = int(self.experiment["statistical_seed"])
        metrics: dict[str, Any] = {}
        for metric_name, section in metric_sections.items():
            per_seed: dict[str, Any] = {}
            seed_deltas: list[float] = []
            for seed, by_method in values_by_seed.items():
                control = by_method["control_no_library"]
                treatment = by_method["legal_skill_evolve"]
                if len(control) != len(treatment) or any(
                    before.group_id != after.group_id
                    for before, after in zip(control, treatment, strict=True)
                ):
                    raise ExecutionError(f"seed {seed} sensitivity pairs are misaligned")
                if section == "behavior":
                    before_values = [
                        trajectory_behavior_values(item, set())[metric_name] for item in control
                    ]
                    after_values = [
                        trajectory_behavior_values(item, {skill.skill_id for skill in active})[
                            metric_name
                        ]
                        for item in treatment
                    ]
                else:
                    before_values = [
                        float(
                            getattr(
                                getattr(evaluations[item.trajectory_id], section),
                                metric_name,
                            )
                        )
                        for item in control
                    ]
                    after_values = [
                        float(
                            getattr(
                                getattr(evaluations[item.trajectory_id], section),
                                metric_name,
                            )
                        )
                        for item in treatment
                    ]
                case_deltas = clustered_mean_deltas(
                    [item.case_id for item in control], before_values, after_values
                )
                estimate = paired_bootstrap_interval(
                    case_deltas,
                    samples=bootstrap_samples,
                    confidence_level=confidence,
                    seed=statistical_seed,
                )
                seed_deltas.append(estimate.mean_delta)
                per_seed[str(seed)] = {
                    "control_mean": round(statistics.fmean(before_values), 6),
                    "legal_skill_evolve_mean": round(statistics.fmean(after_values), 6),
                    "paired_case_cluster_estimate": estimate.model_dump(mode="json"),
                }
            primary_delta = per_seed[str(primary_seed)]["paired_case_cluster_estimate"][
                "mean_delta"
            ]
            primary_direction = (
                "positive" if primary_delta > 0 else "negative" if primary_delta < 0 else "zero"
            )
            consistent = sum(
                (value > 0 and primary_delta > 0)
                or (value < 0 and primary_delta < 0)
                or (value == 0 and primary_delta == 0)
                for value in seed_deltas
            )
            metrics[metric_name] = {
                "per_seed": per_seed,
                "primary_direction": primary_direction,
                "same_direction_seed_count": consistent,
                "total_seed_count": len(seed_deltas),
                "mean_delta_range": [
                    round(min(seed_deltas), 6),
                    round(max(seed_deltas), 6),
                ],
            }

        trajectory_artifacts = {
            item.trajectory_id: {
                "partition": item.partition,
                "sha256": sha256_file(
                    self.store.trajectory_path(item.partition, item.trajectory_id)
                ),
            }
            for item in all_values
        }
        report = {
            "schema_version": 1,
            "status": "secondary_sampling_robustness_only",
            "run_id": self.run_id,
            "run_manifest_sha256": run_manifest_sha256,
            "trajectory_schema_version": self._trajectory_protocol_version(),
            "training_complete_sha256": sha256_file(frozen_path),
            "round_completion_manifests": training_summary.round_completion_manifests,
            "round_completion_set_sha256": training_summary.round_completion_set_sha256,
            "publication_role": TRAINING_RUN_EXTERNAL_PUBLICATION_ROLE,
            "affects_candidate_selection": False,
            "affects_primary_inference": False,
            "requires_primary_external_test": True,
            "case_selection_rule": "every_fifth_public_cn_record_from_frozen_order",
            "case_ids": case_ids,
            "personas": personas,
            "primary_seed_reused": primary_seed,
            "additional_dialogue_seeds": additional_seeds,
            "all_dialogue_seeds": [primary_seed, *additional_seeds],
            "primary_trajectory_count_reused": len(case_ids) * len(personas) * 2,
            "new_trajectory_count": len(completed),
            "case_clusters": len(case_ids),
            "metrics": metrics,
            "trajectory_artifacts": trajectory_artifacts,
            "trajectory_set_sha256": canonical_json_sha256(trajectory_artifacts),
            "active_skill_library_sha256": active_hash,
            "primary_external_report_sha256": primary_report_sha256,
            "completed_at": datetime.now(UTC).isoformat(),
        }
        self.store.atomic_json(report_path, report)
        return report

    def _load_or_run(
        self,
        *,
        runner: TrajectoryRunner,
        adapter: DLawBenchAdapter,
        case_id: str,
        persona: dict[str, Any],
        skills: list[SkillContract],
        trajectory_id: str,
        method: Literal[
            "control_no_library",
            "legal_skill_evolve",
            "training_policy_sample",
            "luna_direct",
            "expel_adapted",
        ],
        partition: str,
        seed: int,
        sample_index: int,
        group_id: str,
        skill_hash: str,
        domain_override: str | None = None,
        diagnostic_interaction_limit: int | None = None,
        policy_memory_override: str | None = None,
        exposed_memory_ids: list[str] | None = None,
    ) -> ResearchTrajectory:
        path = self.store.trajectory_path(partition, trajectory_id)
        effective_domain = domain_override or adapter.case_domain(case_id)
        prior_contract_issues: list[Any] = []
        if path.is_file():
            prior = self.store.load_model(path, ResearchTrajectory)
            if prior.status != "error":
                # The path alone is not a sufficient resume key: a copied, stale,
                # or manually edited artifact could otherwise be reused under the
                # current matrix cell and silently break paired attribution.
                expected_identity = {
                    "trajectory_id": trajectory_id,
                    "run_id": self.run_id,
                    "partition": partition,
                    "method": method,
                    "case_id": case_id,
                    "persona": str(persona["persona_id"]),
                    "seed": seed,
                    "sample_index": sample_index,
                    "group_id": group_id,
                    "skill_library_version": skill_hash,
                    "model_id": runner.policy_client.model,
                    "model_revision": runner.model_revision,
                    "domain": effective_domain,
                }
                identity_drift = [
                    field
                    for field, expected in expected_identity.items()
                    if getattr(prior, field) != expected
                ]
                if identity_drift:
                    raise ExecutionError(
                        "refusing persisted non-error trajectory with resume identity drift: "
                        f"{trajectory_id}; fields={identity_drift}"
                    )
                prior_contract_issues = current_trajectory_contract_issues(
                    prior,
                    expected_run_id=self.run_id,
                )
            # A deterministic memo fallback is deliberately a blocking health
            # outcome, not a completed resumable unit.  Returning it here made a
            # stopped run reload the same unhealthy artifact forever, so an amended
            # renderer could never recover through the normal model path.
            blocking_policy_fallback = any(
                blocking_policy_fallback_reasons(step) for step in prior.steps
            )
            if (
                prior.status != "error"
                and not prior.memo_safe_fallback
                and not blocking_policy_fallback
                and not prior_contract_issues
                and prior.opening_agenda_visible_input
                and prior.opening_agenda_attempts
            ):
                return prior
        value = runner.run(
            raw_case=adapter.evaluator_case(case_id),
            domain=effective_domain,
            persona=persona,
            skills=skills,
            trajectory_id=trajectory_id,
            run_id=self.run_id,
            method=method,
            partition=partition,
            seed=seed,
            sample_index=sample_index,
            max_turns=int(self.experiment["emergency_turn_ceiling"]),
            group_id=group_id,
            skill_library_version=skill_hash,
            diagnostic_interaction_limit=diagnostic_interaction_limit,
            policy_memory_override=policy_memory_override,
            exposed_memory_ids=exposed_memory_ids,
        )
        # A grounded empty agenda is an audited, valid outcome: the auxiliary
        # opening-only role may find no safe unknown attribute, while the lawyer
        # still retains its ordinary ``new_visible_gap`` action.  Require the
        # visible request and bounded attempts, not a fabricated observation.
        if value.status != "error" and (
            not value.opening_agenda_visible_input or not value.opening_agenda_attempts
        ):
            raise ExecutionError(
                "formal trajectory completed without audited opening-agenda evidence: "
                f"{trajectory_id}"
            )
        self.store.save_model(path, value, overwrite=path.exists())
        return value
