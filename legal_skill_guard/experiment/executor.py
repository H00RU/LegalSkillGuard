"""End-to-end main experiment matrix, evolution loop, and external evaluation."""

from __future__ import annotations

import json
import statistics
from collections import Counter
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, TypeVar, cast

import yaml
from pydantic import BaseModel, ConfigDict, Field

from legal_skill_guard.agent.state_manager import reconstruct_execution_state
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
    monotone_expected_action_scores,
    policy_fallback_used,
)
from legal_skill_guard.evaluation.statistics import (
    PairedEstimate,
    benjamini_hochberg,
    clustered_mean_deltas,
    paired_bootstrap_interval,
    paired_sign_flip_p_value,
)
from legal_skill_guard.evolution.acceptance import (
    AcceptanceThresholds,
    AuditDecision,
    MechanismDirectionGate,
    PairOutcome,
    SignalFamily,
    decide_skill,
    global_regression_passes,
    mechanism_direction_gate,
)
from legal_skill_guard.evolution.advantage import (
    AdvantageGroup,
    CausalEvidencePatch,
    ContrastSelection,
    ScoredMember,
    compute_advantages,
)
from legal_skill_guard.evolution.diagnosis import TeacherDiagnosisDraft
from legal_skill_guard.evolution.reward import (
    RewardComponents,
    RewardParameters,
    balanced_elicitation,
    trajectory_reward,
)
from legal_skill_guard.evolution.teacher import (
    SkillTeacher,
    TeacherProposal,
    candidate_batch_source_grounding_issues,
    candidate_source_grounding_issues,
    select_teacher_evidence_clusters,
    teacher_evidence_cluster_summaries,
)
from legal_skill_guard.experiment.batch_productivity import (
    TrainingBatchProductivityThresholds,
    training_batch_productivity_review,
)
from legal_skill_guard.experiment.batches import load_training_batch_plan
from legal_skill_guard.experiment.group_attribution import (
    ATTRIBUTION_LOCAL_CODES,
    TrainingGroupAttributionPolicy,
    attribution_issue_codes_are_local_recovery,
    training_group_attribution_review,
)
from legal_skill_guard.experiment.intervention_isolation import (
    candidate_intervention_isolation_report,
    skill_library_intervention_isolation_report,
    skill_memory_contract_report,
)
from legal_skill_guard.experiment.learning_curve import build_prequential_sentinel_report
from legal_skill_guard.experiment.runner import TrajectoryRunner, termination_contract_check
from legal_skill_guard.experiment.storage import RunStore, safe_component, trajectory_identity
from legal_skill_guard.experiment.trajectory_health import trajectory_health_report
from legal_skill_guard.inference.codex_cli_client import (
    CodexCLIClient,
    CodexInvocationError,
    strict_output_schema,
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
    MAX_POLICY_SKILL_DOCUMENT_CHARACTERS,
    MAX_SESSION_SKILL_MEMORY_CHARACTERS,
    admit_active_skills_by_prompt_capacity,
    skill_memory_capacity_issues,
)
from legal_skill_guard.skills.registry import SkillRegistry
from legal_skill_guard.text_normalization import normalize_question
from legal_skill_guard.utils.hashing import canonical_json_sha256, sha256_file


def prospective_exposure_minima(
    candidate_domain: str,
    policy: dict[str, Any],
) -> tuple[int, int, int]:
    """Return next-block exposure support appropriate to a skill's scope.

    General skills claim cross-domain utility and therefore retain the broader
    coverage requirement. A domain document is delivered only inside its declared
    domain. The unseen block measures controlled document exposure rather than a
    post-policy runtime rule.
    """

    if candidate_domain == "general":
        return (
            int(policy["minimum_exposed_sessions"]),
            int(policy["minimum_exposed_cases"]),
            int(policy["minimum_exposed_domains"]),
        )
    return (
        int(policy["domain_minimum_exposed_sessions"]),
        int(policy["domain_minimum_exposed_cases"]),
        1,
    )


class ExecutionError(RuntimeError):
    """An experiment stage is incomplete; persisted units may be resumed safely."""


def fresh_candidate_nomination_slots(
    *, fresh_budget: int, concurrent_budget: int, carryover_count: int
) -> int:
    """Reserve fresh teacher nominations independently of live carry-overs.

    The concurrent capacity is sized for the full bounded DEFER horizon.  A
    healthy lifecycle must therefore leave the complete per-block fresh budget
    available after the current block resolves candidates at their horizon.  A
    violation is state drift, not a reason to silently reduce the teacher call
    budget and turn a source block into an accidental NOOP.
    """

    if fresh_budget < 1:
        raise ValueError("fresh candidate budget must be positive")
    if concurrent_budget < fresh_budget:
        raise ValueError("concurrent candidate budget cannot be smaller than fresh budget")
    if carryover_count < 0:
        raise ValueError("carry-over candidate count cannot be negative")
    available = concurrent_budget - carryover_count
    if available < fresh_budget:
        raise ExecutionError(
            "live carry-over candidates exhausted the reserved fresh nomination capacity"
        )
    return fresh_budget


T = TypeVar("T")
R = TypeVar("R")


def _same_string_multiset(left: object, right: object) -> bool:
    """Compare unordered artifact memberships without hiding duplicates."""

    return bool(
        isinstance(left, list)
        and isinstance(right, list)
        and all(isinstance(item, str) for item in [*left, *right])
        and Counter(left) == Counter(right)
    )


def candidate_pair_health_selection(
    pair_reports: list[dict[str, Any]], *, minimum_healthy_pair_fraction: float
) -> dict[str, Any]:
    """Select outcome-blind healthy pairs for an embedded candidate audit.

    A shared-control pair is the indivisible statistical unit.  A fail-closed
    recovery removes that complete pair before semantic outcomes are inspected;
    it is never converted into positive evidence.  A non-recovery defect on the
    treatment side still rejects the whole candidate, while a bad control can
    only quarantine its own pair.
    """

    if not 0.0 < minimum_healthy_pair_fraction <= 1.0:
        raise ValueError("minimum healthy candidate-pair fraction must be in (0, 1]")
    counts: Counter[str] = Counter()
    eligible_case_ids: list[str] = []
    excluded_pairs: list[dict[str, Any]] = []
    hard_treatment_issues: list[dict[str, Any]] = []
    for row in pair_reports:
        report = row["report"]
        issues = [dict(item) for item in report.get("issues", [])]
        report_counts = {
            str(key): int(value) for key, value in report.get("counts", {}).items()
        }
        issues_truncated = int(report.get("issues_truncated", 0))
        blocking_issue_count = int(
            report.get("blocking_issue_count", len(issues) + issues_truncated)
        )
        report_integrity_failed = (
            issues_truncated < 0
            or any(value < 0 for value in report_counts.values())
            or blocking_issue_count != len(issues) + issues_truncated
            or sum(report_counts.values()) != blocking_issue_count
            or not isinstance(report.get("healthy"), bool)
            or bool(report.get("healthy")) != (blocking_issue_count == 0)
        )
        if issues_truncated or report_integrity_failed:
            raise ExecutionError(
                "candidate pair health report lacks complete issue provenance: "
                f"case_id={row['case_id']}"
            )
        for key, value in report_counts.items():
            counts[str(key)] += int(value)
        if bool(report.get("healthy")):
            eligible_case_ids.append(str(row["case_id"]))
            continue
        treatment_id = str(row["candidate_trajectory_id"])
        treatment_issues = [
            item for item in issues if str(item.get("trajectory_id") or "") == treatment_id
        ]
        treatment_codes = {str(item.get("code") or "") for item in treatment_issues}
        if attribution_issue_codes_are_local_recovery(treatment_codes):
            treatment_hard = []
        else:
            treatment_hard = treatment_issues
            if not issues:
                treatment_hard = [
                    {
                        "code": "unclassified_candidate_pair_health_failure",
                        "trajectory_id": treatment_id,
                        "turn": 0,
                        "detail": "health report was unhealthy without issue provenance",
                    }
                ]
        hard_treatment_issues.extend(treatment_hard)
        excluded_pairs.append(
            {
                "case_id": str(row["case_id"]),
                "baseline_trajectory_id": str(row["baseline_trajectory_id"]),
                "candidate_trajectory_id": treatment_id,
                "issue_codes": sorted({str(item.get("code") or "") for item in issues}),
                "issues": issues,
                "exclusion_timing": "before_reward_and_semantic_judgment",
            }
        )
    pair_count = len(pair_reports)
    eligible_fraction = len(eligible_case_ids) / pair_count if pair_count else 0.0
    fraction_passed = eligible_fraction >= minimum_healthy_pair_fraction
    return {
        "schema_version": 2,
        "scope": "embedded_candidate_pair_health_before_outcomes",
        "selection_timing": "before_reward_and_semantic_judgment",
        "selection_uses_reward_or_candidate_outcome": False,
        "quarantine_unit": "complete_shared_control_candidate_pair",
        "quarantinable_health_codes": sorted(ATTRIBUTION_LOCAL_CODES),
        "conditional_quarantine_rule": (
            "persisted_policy_contract_failure_requires_same_trajectory_policy_fallback"
        ),
        "pair_count": pair_count,
        "eligible_pair_count": len(eligible_case_ids),
        "eligible_pair_fraction": round(eligible_fraction, 6),
        "minimum_healthy_pair_fraction": minimum_healthy_pair_fraction,
        "eligible_fraction_passed": fraction_passed,
        "eligible_case_ids": eligible_case_ids,
        "excluded_pair_count": len(excluded_pairs),
        "excluded_pairs": excluded_pairs,
        "hard_treatment_issue_count": len(hard_treatment_issues),
        "hard_treatment_issues": hard_treatment_issues,
        # A treatment-side contract defect is evidence that this candidate run
        # is invalid and must be rejected.  Outcome-blind pair quarantine is
        # different: it reduces the usable matrix and may require another unseen
        # block, but it says nothing about candidate efficacy.
        "candidate_wide_health_passed": not hard_treatment_issues,
        "matrix_coverage_passed": fraction_passed,
        "blocking_issue_count": len(hard_treatment_issues) + int(not fraction_passed),
        "counts": dict(sorted(counts.items())),
        "healthy": not hard_treatment_issues and fraction_passed,
    }


class ExecutionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PreflightReport(ExecutionModel):
    ready: bool
    checks: dict[str, Any]


class ProspectiveCandidateAudit(ExecutionModel):
    schema_version: Literal[5] = 5
    skill_id: str
    source_batch_id: str
    validation_batch_id: str
    validation_case_ids: list[str]
    validation_batch_ids: list[str] = Field(default_factory=list)
    prior_audit_artifacts: list[dict[str, str]] = Field(default_factory=list)
    pair_seeds: list[int]
    decision: AuditDecision
    paired_estimate: PairedEstimate | None
    global_regression_passed: bool
    # ``outcomes`` is cumulative across the bounded prospective horizon.  The
    # current-block subset remains explicit so the audit can be checked without
    # mistaking a prior block's result for a fresh observation.
    outcomes: list[PairOutcome]
    current_outcomes: list[PairOutcome] = Field(default_factory=list)
    baseline_trajectory_ids: list[str]
    candidate_trajectory_ids: list[str]
    candidate_contract_health_passed: bool
    candidate_matrix_coverage_passed: bool | None
    candidate_health_report: str | None = None
    candidate_health_counts: dict[str, int] = Field(default_factory=dict)
    source_signal_family: SignalFamily
    mechanism_direction_gate: MechanismDirectionGate | None = None
    completed_at: str


def prospective_audit_teacher_feedback(audit: ProspectiveCandidateAudit) -> dict[str, Any]:
    """Return compact, case-anonymous feedback from a completed next-block audit.

    A rejected contract must not remain only a rollback event: later synthesis needs
    to know which held-out mechanism reproduced and which efficacy or safety gate
    failed.  Aggregate by legal domain so the teacher can learn from the failure
    without receiving case IDs, pair IDs, raw questions, or hidden facts that could
    encourage case-specific rules.
    """

    exposed_by_domain: dict[str, list[PairOutcome]] = {}
    for outcome in audit.outcomes:
        if outcome.exposed:
            exposed_by_domain.setdefault(outcome.domain, []).append(outcome)

    def mean(rows: list[PairOutcome], field: str) -> float:
        return round(statistics.fmean(float(getattr(row, field)) for row in rows), 6)

    material_harm_delta_threshold = audit.decision.material_harm_delta_threshold
    domain_outcomes: list[dict[str, Any]] = []
    for domain, rows in sorted(exposed_by_domain.items()):
        deltas = [row.delta for row in rows]
        domain_outcomes.append(
            {
                "domain": domain,
                "exposed_pairs": len(rows),
                "mean_reward_delta": round(statistics.fmean(deltas), 6),
                "minimum_reward_delta": round(min(deltas), 6),
                "harmful_pair_rate": round(
                    sum(delta < -material_harm_delta_threshold for delta in deltas) / len(deltas),
                    6,
                ),
                "mean_newly_elicited_fact_delta": mean(rows, "newly_elicited_fact_delta"),
                "mean_identified_evidence_gap_delta": mean(rows, "identified_evidence_gap_delta"),
                "mean_question_turn_delta": mean(rows, "question_turn_delta"),
                "mean_unsupported_claim_delta": mean(rows, "unsupported_claim_delta"),
                "mean_premature_final_delta": mean(rows, "premature_final_delta"),
                "mean_belief_as_fact_delta": mean(rows, "belief_as_fact_delta"),
                "mean_repeated_question_delta": mean(rows, "repeated_question_delta"),
                "mean_critical_fact_recall_delta": mean(rows, "critical_fact_recall_delta"),
                "mean_policy_fallback_delta": mean(rows, "policy_fallback_delta"),
                "mean_client_fallback_delta": mean(rows, "client_fallback_delta"),
                "mean_memo_fallback_delta": mean(rows, "memo_fallback_delta"),
            }
        )

    return {
        "skill_id": audit.skill_id,
        "source_batch_id": audit.source_batch_id,
        "validation_batch_id": audit.validation_batch_id,
        "validation_blocks": len(audit.validation_batch_ids),
        "source_signal_family": audit.source_signal_family,
        "decision": audit.decision.model_dump(mode="json"),
        "paired_estimate": (
            audit.paired_estimate.model_dump(mode="json")
            if audit.paired_estimate is not None
            else None
        ),
        "global_regression_passed": audit.global_regression_passed,
        "candidate_contract_health_passed": audit.candidate_contract_health_passed,
        "candidate_matrix_coverage_passed": audit.candidate_matrix_coverage_passed,
        "mechanism_direction_gate": (
            audit.mechanism_direction_gate.model_dump(mode="json")
            if audit.mechanism_direction_gate is not None
            else None
        ),
        "exposed_domain_outcomes": domain_outcomes,
    }


class TrainingSummary(ExecutionModel):
    schema_version: Literal[4] = 4
    run_id: str
    run_manifest_sha256: str
    trajectory_schema_version: Literal[16]
    evaluation_schema_version: Literal[13]
    case_limit: int | None = None
    rounds_completed: int
    round_completion_manifests: dict[str, str]
    round_completion_set_sha256: str
    accepted_skill_ids: list[str]
    rejected_skill_ids: list[str] = Field(default_factory=list)
    prospective_validation_reports: dict[str, str] = Field(default_factory=dict)
    active_skill_ids: list[str]
    active_skill_library_version: str
    active_skill_library_sha256: str
    development_learning_curve_sha256: str
    completed_at: str
    # RunStore manifests add this verified envelope field when read.  It is not
    # part of the content being hashed and is therefore absent during creation.
    content_sha256: str | None = None


EXTERNAL_METHODS = Literal[
    "control_no_library",
    "ungated_source_grounded_skills",
    "legal_skill_guard",
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
    if proposed is None or witness is None:
        return False
    provenance = proposed.provenance
    candidate_provenance = candidate.provenance
    return bool(
        provenance.diagnosis_hash
        and provenance.diagnosis_hash == proposal.response_sha256
        and provenance.generator_model == proposal.teacher_model
        and witness.evidence_cluster_id == provenance.source_evidence_cluster_id
        and witness.signal_family == provenance.source_signal_family
        and candidate_provenance.diagnosis_hash == proposal.response_sha256
        and candidate_provenance.source_evidence_cluster_id
        == witness.evidence_cluster_id
        and candidate_provenance.source_signal_family == witness.signal_family
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
        "skill_exposed": float(bool(session_skills)),
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
        session_skills = (
            set(getattr(trajectory, "exposed_skill_ids", [])) & active_skill_ids
        )
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
        "sessions_with_skill_exposure": exposed_sessions,
        "skill_exposure_session_rate": round(exposed_sessions / sessions, 6)
        if sessions
        else 0.0,
        "skill_exposed_cases": len(exposed_cases),
        "skill_exposed_domains": len(exposed_domains),
        "skill_exposure_counts": dict(sorted(exposure_counts.items())),
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
        "direction": "legal_skill_guard_minus_control_no_library",
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
    external_case_ids: tuple[str, ...],
) -> None:
    """Fail closed if primary and secondary sampling roles are conflated."""

    personas = [str(item) for item in experiment.get("personas") or []]
    if personas != ["P_WD", "P_WS", "P_CS", "P_CD"]:
        raise ValueError("main experiment must retain the frozen four-persona order")
    if tuple(personas) != available_personas:
        raise ValueError("configured personas do not equal the pinned DLawBench personas")

    sampling = experiment.get("trajectory_sampling") or {}
    if sampling.get("counterfactual_initial_target_allocation") is not True:
        raise ValueError(
            "training must use the frozen planner-authored counterfactual first-target allocation"
        )
    group_size = int(sampling.get("group_size", 0))
    target_replicates = int(sampling.get("counterfactual_initial_target_replicates", 0))
    if target_replicates != 2 or group_size != 4 or group_size % target_replicates:
        raise ValueError(
            "training must use two planner-target variants with two stochastic "
            "continuations each (K=4)"
        )
    if sampling.get("counterfactual_followup_target_allocation") is not True:
        raise ValueError(
            "training must create the declared second-turn fork inside each matched pair"
        )
    if bool(sampling.get("shuffle_equal_criticality_fact_presentation", False)):
        raise ValueError(
            "presentation shuffling must remain disabled when counterfactual allocation is active"
        )
    if [int(item) for item in sampling.get("training_group_seeds") or []] != [42]:
        raise ValueError(
            "training and embedded next-block validation must share dialogue seed 42"
        )
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
    prospective = experiment.get("prospective_validation") or {}
    fresh_candidate_budget = int(
        execution.get("provisional_candidate_budget_per_block", 0)
    )
    teacher_call_budget = int(execution.get("teacher_call_budget_per_round", 0))
    concurrent_candidate_budget = int(
        execution.get("maximum_concurrent_provisional_candidates", 0)
    )
    validation_horizon = int(prospective.get("maximum_validation_blocks", 0))
    if fresh_candidate_budget < teacher_call_budget or teacher_call_budget < 1:
        raise ValueError(
            "fresh candidate budget must cover every declared teacher call"
        )
    if concurrent_candidate_budget < fresh_candidate_budget * validation_horizon:
        raise ValueError(
            "concurrent provisional capacity must reserve fresh nominations across "
            "the complete DEFER horizon"
        )

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


def skill_library_sha256(skills: list[SkillContract]) -> str:
    return canonical_json_sha256(
        [item.model_dump(mode="json") for item in sorted(skills, key=lambda row: row.skill_id)]
    )


FORMAL_INITIAL_SKILL_LIBRARY_ID = "bootstrap_empty"


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
        raise ExecutionError(
            "formal protocol initial_library must resolve to skills/bootstrap"
        )
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
            "formal protocol requires an empty skills/bootstrap library; "
            f"found={detail}"
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
                "action_type": step.action_decision.final.action_type,
                "target_type": step.action_decision.final.target_type,
                "target_id": step.action_decision.final.target_id,
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
    """Select only same-current-prompt traces for teacher contrast mining.

    ``candidate_with`` is held-out intervention traffic.  Feeding it back into
    TF-GRPO would let an unaccepted document teach its own successor and would mix
    two prompts inside one advantage group.
    """

    allowed_methods = {"candidate_without", "training_policy_sample"}
    by_group: dict[str, list[ResearchTrajectory]] = {}
    for trajectory in trajectories:
        if (
            trajectory.group_id in scoreable_group_ids
            and trajectory.method in allowed_methods
        ):
            by_group.setdefault(str(trajectory.group_id), []).append(trajectory)
    if set(by_group) != scoreable_group_ids:
        raise ExecutionError("scoreable attribution groups lack current-prompt teacher evidence")
    for group_id, members in by_group.items():
        if len(members) < 3:
            raise ExecutionError(
                "TF-GRPO requires at least three same-prompt traces after excluding "
                f"candidate treatment: group={group_id}; traces={len(members)}"
            )
        if len({item.skill_library_version for item in members}) != 1:
            raise ExecutionError(f"TF-GRPO teacher evidence spans prompt libraries: {group_id}")
    return by_group


_CAUSAL_STATE_EXCLUSIONS = {
    "session_id",
    # ``state_before`` carries the preceding turn's candidate action. Causal
    # alignment and source witnessing instead evaluate the current proposed action.
    "candidate_action",
    "candidate_target_repeated",
    "candidate_target_unavailable",
    "candidate_target_low_value",
    "candidate_target_already_known",
    "candidate_target_is_client_fact",
    "candidate_target_is_evidence_gap",
    # This is derived from the current candidate action just like the flags
    # above.  Keeping it in the pre-action signature made an otherwise shared
    # final-vs-ask fork compare ``None`` with the asked target's criticality,
    # so continuation and priority-upgrade evidence was silently discarded.
    "candidate_target_criticality",
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


def _causal_state_signature(step: ResearchStep) -> str:
    """Identify the executable pre-action state modulo surface paraphrases.

    The skill interface can condition on prior target/outcome records but cannot
    condition on the exact wording of an earlier, already-rendered question.  Keeping
    that wording in the matching key would incorrectly split states that are
    identical for every executable skill field.
    """

    execution_state = _execution_state_for_step(step)
    payload = {
        key: value
        for key, value in (
            execution_state.model_dump(mode="json")
            if execution_state is not None
            else step.state_before
        ).items()
        if key not in _CAUSAL_STATE_EXCLUSIONS
    }
    interactions = payload.get("interactions")
    if isinstance(interactions, list):
        payload["interactions"] = [
            {key: value for key, value in item.items() if key != "question"}
            if isinstance(item, dict)
            else item
            for item in interactions
        ]
    return canonical_json_sha256(payload)


def _learnable_action_signature(step: ResearchStep) -> tuple[Any, ...]:
    """Project an action onto behavior represented by the source-witness interface."""

    action = _effective_step_action(step)
    return (
        action.action_type,
        action.target_type,
        action.target_id,
        normalize_question(action.content),
        normalize_question(action.expected_information),
        tuple(action.constraints),
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
    """Read the frozen planner type from the exact skill-visible execution state."""

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


def _step_is_true_zero_information(step: ResearchStep) -> bool:
    if _new_hidden_fact_ids(step) or _identified_evidence_gap_ids(step):
        return False
    if (
        bool(getattr(step, "client_safe_fallback", False))
        or _step_uses_policy_fallback(step)
        or _step_has_blocking_health(step)
    ):
        return False
    response_kind = _step_response_kind(step)
    action = _effective_step_action(step)
    if (
        response_kind in {"unavailable", "opening_repeat", "repeated_hidden_fact"}
        and getattr(action, "action_type", None) in {"ask", "clarify", "verify"}
        and _step_target_kind(step) not in {"client_fact", "evidence_or_third_party"}
    ):
        return False
    return response_kind in {
        "unavailable",
        "opening_repeat",
        "repeated_hidden_fact",
    } or (getattr(action, "action_type", None) in {"final", "abstain"} and response_kind is None)


def _step_uses_policy_fallback(step: ResearchStep) -> bool:
    return policy_fallback_used(step)


def _step_has_blocking_health(step: ResearchStep) -> bool:
    violations = [
        *getattr(step, "policy_health_violations", []),
        *getattr(step, "post_skill_health_violations", []),
    ]
    if any(not str(item).startswith("warning:") for item in violations):
        return True
    return any(
        not bool(getattr(result, "passed", False))
        and str(getattr(result, "severity", "error")) in {"error", "severe"}
        for result in getattr(step, "verifier_results", [])
    )


def _unresolved_evidence_gap_count(state_before: dict[str, Any]) -> int:
    explicit = state_before.get("evidence_or_third_party_unresolved_count")
    if isinstance(explicit, int):
        return explicit
    asked = {str(item) for item in (state_before.get("asked_targets") or [])}
    return sum(
        isinstance(item, dict)
        and item.get("target_kind") == "evidence_or_third_party"
        and item.get("status") in {"unknown", "disputed"}
        and str(item.get("fact_id") or "") not in asked
        for item in (state_before.get("facts") or [])
    )


def select_causally_aligned_contrasts(
    group: AdvantageGroup,
    members: dict[str, ResearchTrajectory],
) -> list[ContrastSelection]:
    """Choose a locally attributable policy fork from a shared visible state.

    Whole-trajectory reward extrema can differ because of memo rendering even though
    the skill language changes only the lawyer's next action.  Conversely, a genuinely
    useful inquiry can obtain a new fact that the frozen memo renderer later fails to
    use, but a TF-GRPO-style teacher contrast must still distinguish a winner under the
    declared reward.  Fact elicitation and first identification of an external
    evidence gap are separate local signal families.  The latter is derived when an
    ``evidence_or_third_party`` target correctly yields ``unavailable``; it must not
    be mislabeled as a failed client-fact question. Neither mechanism signal changes
    the official reward, which remains a necessary positive gate.
    This admits both durable coverage gains and direct information-efficiency gains where
    the negative branch eventually catches up.  Merely obtaining two different facts at
    the fork, or a later fact-count difference without an immediate zero-information
    contrast, is not locally attributable evidence.  A third, deliberately narrow
    family captures safe stopping: from the same state, final must outperform an extra question that
    immediately yields only unavailable/repeated/opening information, without losing
    any unique fact, and the state must already show no high-critical unknown plus
    prior unanswerability (or all remaining facts unavailable).  This prevents the
    fact-only filter from making candidate search structurally blind to efficiency,
    while excluding speculative stopping.  Next-block paired validation remains the
    only authority that can activate any family.
    """

    scored = {item.trajectory_id: item for item in group.members}
    fact_candidates: list[tuple[int, int, int, float, int, str, str]] = []
    gap_candidates: list[tuple[int, int, float, int, str, str]] = []
    stop_candidates: list[tuple[float, int, int, str, str]] = []
    for positive_id, positive in members.items():
        positive_score = scored[positive_id].reward
        positive_fact_ids = _trajectory_elicited_fact_ids(positive)
        positive_gap_ids = _trajectory_identified_evidence_gap_ids(positive)
        for negative_id, negative in members.items():
            if positive_id == negative_id:
                continue
            negative_score = scored[negative_id].reward
            negative_fact_ids = _trajectory_elicited_fact_ids(negative)
            negative_gap_ids = _trajectory_identified_evidence_gap_ids(negative)
            eventual_extra_facts = positive_fact_ids - negative_fact_ids
            eventual_lost_facts = negative_fact_ids - positive_fact_ids
            fact_gain = len(eventual_extra_facts)
            reward_gap = positive_score - negative_score
            for positive_step, negative_step in zip(positive.steps, negative.steps, strict=False):
                if positive_step.turn != negative_step.turn:
                    break
                if _causal_state_signature(positive_step) != _causal_state_signature(negative_step):
                    break
                if _learnable_action_signature(positive_step) != _learnable_action_signature(
                    negative_step
                ):
                    positive_immediate_facts = _new_hidden_fact_ids(positive_step)
                    negative_immediate_facts = _new_hidden_fact_ids(negative_step)
                    positive_immediate_gaps = _identified_evidence_gap_ids(positive_step)
                    negative_immediate_gaps = _identified_evidence_gap_ids(negative_step)
                    negative_zero_information = _step_is_true_zero_information(negative_step)
                    immediate_fact_gain = len(positive_immediate_facts) - len(
                        negative_immediate_facts
                    )
                    eventual_gain_is_locally_grounded = not eventual_lost_facts and (
                        not eventual_extra_facts
                        or eventual_extra_facts.issubset(positive_immediate_facts)
                    )
                    if (
                        eventual_gain_is_locally_grounded
                        and reward_gap > 0
                        and immediate_fact_gain > 0
                        and not negative_immediate_facts
                        and not negative_immediate_gaps
                        and negative_zero_information
                        and positive_gap_ids.issuperset(negative_gap_ids)
                    ):
                        safe_continuation_context = (
                            int(positive_step.state_before.get("high_critical_unknown_count") or 0)
                            > 0
                            and int(positive_step.state_before.get("unavailable_turn_count") or 0)
                            == 0
                        )
                        fact_candidates.append(
                            (
                                int(safe_continuation_context),
                                immediate_fact_gain,
                                fact_gain,
                                reward_gap,
                                positive_step.turn,
                                positive_id,
                                negative_id,
                            )
                        )
                    eventual_extra_gaps = positive_gap_ids - negative_gap_ids
                    eventual_lost_gaps = negative_gap_ids - positive_gap_ids
                    immediate_gap_gain = len(positive_immediate_gaps) - len(negative_immediate_gaps)
                    eventual_gap_gain_is_locally_grounded = not eventual_lost_gaps and (
                        not eventual_extra_gaps
                        or eventual_extra_gaps.issubset(positive_immediate_gaps)
                    )
                    if (
                        reward_gap > 0
                        and immediate_gap_gain > 0
                        and not negative_immediate_facts
                        and not negative_immediate_gaps
                        and negative_zero_information
                        and eventual_gap_gain_is_locally_grounded
                        and positive_fact_ids == negative_fact_ids
                    ):
                        gap_candidates.append(
                            (
                                immediate_gap_gain,
                                len(eventual_extra_gaps),
                                reward_gap,
                                positive_step.turn,
                                positive_id,
                                negative_id,
                            )
                        )
                    positive_effective_action = _effective_step_action(positive_step)
                    positive_final = positive_effective_action.action_type == "final"
                    negative_nonterminal = _effective_step_action(negative_step).action_type in {
                        "ask",
                        "clarify",
                        "verify",
                        "retrieve",
                        "summarize",
                    }
                    execution_state = _execution_state_for_step(positive_step)
                    state_before = (
                        execution_state.model_dump(mode="json")
                        if execution_state is not None
                        else positive_step.state_before
                    )
                    no_high_critical_unknown = (
                        int(state_before.get("high_critical_unknown_count") or 0) == 0
                    )
                    prior_unanswerability = int(
                        state_before.get("unavailable_turn_count") or 0
                    ) > 0 or bool(state_before.get("all_remaining_facts_not_available"))
                    if (
                        positive_final
                        and negative_nonterminal
                        and negative_zero_information
                        and positive_fact_ids.issuperset(negative_fact_ids)
                        and positive_gap_ids.issuperset(negative_gap_ids)
                        and reward_gap > 0
                        and no_high_critical_unknown
                        and prior_unanswerability
                        and _unresolved_evidence_gap_count(state_before) == 0
                    ):
                        stop_candidates.append(
                            (
                                reward_gap,
                                int(bool(state_before.get("all_remaining_facts_not_available"))),
                                positive_step.turn,
                                positive_id,
                                negative_id,
                            )
                        )
                    break
    selections: list[ContrastSelection] = []
    if fact_candidates:
        _, immediate_fact_gain, fact_gain, reward_gap, turn, positive_id, negative_id = max(
            fact_candidates,
            key=lambda item: (
                item[0],
                item[1],
                item[2],
                item[3],
                -item[4],
                item[5],
                item[6],
            ),
        )
        selection_basis = (
            "shared_visible_state_immediate_fact_gain_policy_fork"
            if fact_gain > 0
            else "shared_visible_state_immediate_information_efficiency_policy_fork"
        )
        selections.append(
            ContrastSelection(
                highest_id=positive_id,
                lowest_id=negative_id,
                safety_failure_id=(
                    negative_id
                    if scored[negative_id].premature_final or scored[negative_id].unsupported_claim
                    else None
                ),
                efficient_failure_id=negative_id,
                aligned_divergence_turn=turn,
                positive_fact_count=len(_trajectory_elicited_fact_ids(members[positive_id])),
                negative_fact_count=len(_trajectory_elicited_fact_ids(members[negative_id])),
                immediate_fact_gain=immediate_fact_gain,
                fact_gain=fact_gain,
                immediate_gap_gain=0,
                gap_gain=len(
                    _trajectory_identified_evidence_gap_ids(members[positive_id])
                    - _trajectory_identified_evidence_gap_ids(members[negative_id])
                ),
                reward_gap=round(reward_gap, 6),
                selection_basis=selection_basis,
                signal_family="fact_elicitation",
            )
        )
    if gap_candidates:
        immediate_gap_gain, gap_gain, reward_gap, turn, positive_id, negative_id = max(
            gap_candidates,
            key=lambda item: (item[0], item[1], item[2], -item[3], item[4], item[5]),
        )
        selections.append(
            ContrastSelection(
                highest_id=positive_id,
                lowest_id=negative_id,
                safety_failure_id=(
                    negative_id
                    if scored[negative_id].premature_final or scored[negative_id].unsupported_claim
                    else None
                ),
                efficient_failure_id=negative_id,
                aligned_divergence_turn=turn,
                positive_fact_count=len(_trajectory_elicited_fact_ids(members[positive_id])),
                negative_fact_count=len(_trajectory_elicited_fact_ids(members[negative_id])),
                immediate_fact_gain=0,
                fact_gain=0,
                immediate_gap_gain=immediate_gap_gain,
                gap_gain=gap_gain,
                reward_gap=round(reward_gap, 6),
                selection_basis=(
                    "shared_visible_state_immediate_evidence_gap_policy_fork"
                    if gap_gain > 0
                    else "shared_visible_state_evidence_gap_efficiency_policy_fork"
                ),
                signal_family="evidence_gap_identification",
            )
        )
    if stop_candidates:
        reward_gap, _, turn, positive_id, negative_id = max(
            stop_candidates,
            key=lambda item: (item[1], item[0], -item[2], item[3], item[4]),
        )
        selections.append(
            ContrastSelection(
                highest_id=positive_id,
                lowest_id=negative_id,
                safety_failure_id=(
                    negative_id
                    if scored[negative_id].premature_final or scored[negative_id].unsupported_claim
                    else None
                ),
                efficient_failure_id=negative_id,
                aligned_divergence_turn=turn,
                positive_fact_count=len(_trajectory_elicited_fact_ids(members[positive_id])),
                negative_fact_count=len(_trajectory_elicited_fact_ids(members[negative_id])),
                immediate_fact_gain=0,
                fact_gain=0,
                immediate_gap_gain=0,
                gap_gain=0,
                reward_gap=round(reward_gap, 6),
                selection_basis=("shared_visible_state_true_zero_question_to_safe_final_fork"),
                signal_family="safe_stop",
            )
        )
    return selections


def select_causally_aligned_contrast(
    group: AdvantageGroup,
    members: dict[str, ResearchTrajectory],
) -> ContrastSelection | None:
    """Compatibility wrapper returning the first family in deterministic order."""

    selections = select_causally_aligned_contrasts(group, members)
    return selections[0] if selections else None


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
) -> list[tuple[AdvantageGroup, dict[str, ResearchTrajectory]]]:
    """Prioritize one informative contrast per case before spending repeats."""

    if budget < 0 or maximum_per_case < 1:
        raise ValueError("teacher selection budgets must be non-negative and positive")
    # Callers pass only groups already admitted by a causal evidence cluster.
    # Whole-trajectory reward variance is not a second admission gate: the frozen
    # memo renderer can erase the end-to-end reward benefit of a locally productive
    # inquiry, while paired candidate acceptance still protects final efficacy.
    informative = sorted(
        groups,
        key=lambda item: (-item[0].std_reward, item[0].group_id),
    )
    selected: list[tuple[AdvantageGroup, dict[str, ResearchTrajectory]]] = []
    case_counts: Counter[str] = Counter()

    def case_id(item: tuple[AdvantageGroup, dict[str, ResearchTrajectory]]) -> str:
        return next(iter(item[1].values())).case_id

    for item in informative:
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

    def __init__(self, root: Path, run_id: str) -> None:
        self.root = root
        self.run_id = run_id
        self.experiment_path = root / "configs/experiments/main_experiment.yaml"
        self.roles_path = root / "configs/models/roles.yaml"
        self.data_path = root / "configs/data/main_corpus.yaml"
        self.experiment = _load_yaml(self.experiment_path)
        self.roles = _load_yaml(self.roles_path)
        self.data_config = _load_yaml(self.data_path)
        self.store = RunStore(root / "runs", run_id)
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
        self.external_adapter = DLawBenchAdapter(
            root / self.experiment["data"]["external_evaluation"],
            self.personas_path,
        )
        _validate_persona_seed_protocol(
            self.experiment,
            available_personas=self.main_adapter.persona_keys,
            external_case_ids=self.external_adapter.case_ids(),
        )
        lawyer = self.roles["roles"]["lawyer_policy"]
        shared_local_fields = ("model_id", "revision", "local_snapshot", "base_url")
        for role_name in ("client_disclosure_classifier", "memo_renderer"):
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
        planner_role = self.roles["roles"]["consultation_planner"]
        if planner_role["runtime"] != "local_vllm":
            raise ValueError("consultation_planner runtime must be local_vllm")
        planner_snapshot_fields = ("model_id", "revision", "local_snapshot", "base_url")
        planner_snapshot_mismatches = [
            field
            for field in planner_snapshot_fields
            if planner_role.get(field) != lawyer.get(field)
        ]
        if planner_snapshot_mismatches:
            raise ValueError(
                "consultation_planner must share the frozen lawyer snapshot; "
                f"mismatches={planner_snapshot_mismatches}"
            )
        self.planner_model = str(planner_role["model_id"])
        self.planner_revision = str(planner_role["revision"])
        # The planner cache is project-level infrastructure and is shared only by
        # byte-identical model, prompt, message and generation requests, so a
        # qualified opening plan is replayed unchanged in the formal matrix instead
        # of being resampled merely because the run id or worker scheduling changed.
        # Teacher *responses* are evidence produced by one formal run and therefore
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
        self.planner_client = ReplayCachedChatClient(
            self.local_client,
            self.shared_experiment_root / "consultation_planner_cache" / self.planner_revision,
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
            self.teacher_client, root / "configs/prompts/skill_teacher_zh.txt"
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
        """Bind a fixed, balanced, outcome-blind sentinel sample to every block."""

        curve = self.experiment.get("learning_curve")
        if not isinstance(curve, dict):
            raise ValueError("main experiment requires a learning_curve configuration")
        if (
            curve.get("mode") != "prequential_fixed_shadow"
            or curve.get("status") != "frozen_before_next_formal_run"
            or curve.get("empty_library_identity_shortcut") is not True
            or "never_teacher" not in str(curve.get("evidence_role", ""))
        ):
            raise ValueError("learning-curve role or lifecycle differs from the frozen protocol")
        cases_per_block = int(curve.get("cases_per_block", 0))
        if cases_per_block < 4 or cases_per_block % 4:
            raise ValueError("learning-curve sentinels must be balanced across four personas")
        if int(curve.get("bootstrap_samples", 0)) < 100:
            raise ValueError("learning-curve bootstrap budget is too small")
        declared = curve.get("sentinel_case_ids_by_block")
        if not isinstance(declared, dict):
            raise ValueError("learning-curve sentinel map is missing")
        expected_batch_ids = [batch.batch_id for batch in self.training_plan.batches]
        if set(declared) != set(expected_batch_ids):
            raise ValueError("learning-curve sentinel blocks differ from the training plan")
        expected_persona_count = cases_per_block // 4
        validated: dict[str, list[str]] = {}
        for batch in self.training_plan.batches:
            raw_ids = declared.get(batch.batch_id)
            if not isinstance(raw_ids, list) or not all(
                isinstance(item, str) for item in raw_ids
            ):
                raise ValueError(f"invalid learning-curve sentinel list: {batch.batch_id}")
            case_ids = list(raw_ids)
            if len(case_ids) != len(set(case_ids)) or len(case_ids) != cases_per_block:
                raise ValueError(f"learning-curve sentinel cardinality drift: {batch.batch_id}")
            if not set(case_ids) <= set(batch.case_ids):
                raise ValueError(f"learning-curve sentinel escapes its block: {batch.batch_id}")
            personas = Counter(batch.persona_assignment[case_id] for case_id in case_ids)
            if personas != Counter(
                {
                    "P_WD": expected_persona_count,
                    "P_WS": expected_persona_count,
                    "P_CS": expected_persona_count,
                    "P_CD": expected_persona_count,
                }
            ):
                raise ValueError(f"learning-curve persona imbalance: {batch.batch_id}")
            if len({self.main_adapter.case_domain(case_id) for case_id in case_ids}) != len(
                case_ids
            ):
                raise ValueError(f"learning-curve domain duplication: {batch.batch_id}")
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
                "binding_path_matches": client_qualification.get("qualification_binding_path")
                == str(client_qualification_binding_path.relative_to(self.root)),
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
        teacher_schema = strict_output_schema(TeacherDiagnosisDraft.model_json_schema())
        teacher_transport_contract = {
            "configured_executable_is_absolute": configured_teacher_executable.is_absolute(),
            "resolved_executable_matches": codex_auth.get("executable")
            == str(configured_teacher_executable.resolve()),
            "authenticated": bool(codex_auth.get("ready")),
            "zero_automatic_retries": self.teacher_client.retries == 0,
            "process_tree_timeout_seconds": self.teacher_client.timeout_seconds,
            "strict_skill_diagnosis_schema": not strict_output_schema_issues(teacher_schema),
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
            try:
                response = self.teacher_client.generate_json(
                    purpose="preflight",
                    system_prompt=(
                        "这是技能教师结构契约资格探针，不调用工具、不生成技能。"
                        "严格按schema返回一个NOOP诊断。"
                    ),
                    user_prompt=(
                        "group_id必须为preflight；proposed_change必须为NOOP；"
                        "candidate_skill必须为null；skill_scope为general。"
                    ),
                    output_schema=teacher_schema,
                )
            except CodexInvocationError as exc:
                codex_probe = {
                    "requested": True,
                    "passed": False,
                    "error_type": type(exc).__name__,
                    "error_sha256": canonical_json_sha256({"error": str(exc)}),
                }
            else:
                diagnosis = TeacherDiagnosisDraft.model_validate(response.value)
                codex_probe = {
                    "requested": True,
                    "passed": (
                        diagnosis.group_id == "preflight"
                        and diagnosis.proposed_change == "NOOP"
                        and diagnosis.candidate_skill is None
                        and diagnosis.skill_scope == "general"
                    ),
                    "request_sha256": response.request_sha256,
                    "response_sha256": response.response_sha256,
                    "schema": "TeacherDiagnosisDraft",
                }
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
        candidate_rounds = max(len(self.training_plan.batches) - 1, 0)
        unfinished_teacher_rounds = [
            round_index
            for round_index in range(1, candidate_rounds + 1)
            if not (
                self.store.root / "manifests" / f"teacher_round_{round_index:02d}.json"
            ).is_file()
        ]
        maximum_formal_teacher_calls = len(unfinished_teacher_rounds) * int(
            self.experiment["execution"]["teacher_call_budget_per_round"]
        )
        teacher_budget_ready = bool(
            teacher_budget is not None
            and teacher_budget["available"] >= maximum_formal_teacher_calls
        )
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
                == "prompt_memory_protocol_gpu_requalification_required",
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
            "teacher_invocation_budget": {
                "passed": teacher_budget_ready,
                "maximum_formal_new_calls": maximum_formal_teacher_calls,
                "unfinished_teacher_rounds": unfinished_teacher_rounds,
                **(teacher_budget or {}),
            },
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
            "external_cases": len(self.external_adapter.case_ids()),
            "initial_skill_library": initial_library_check,
            "comparison_arm_contract": {
                "expected": [
                    "control_no_library",
                    "ungated_source_grounded_skills",
                    "legal_skill_guard",
                ],
                "actual": [
                    str(item.get("arm_id")) for item in self.experiment.get("comparison_arms", [])
                ],
            },
            "active_skill_static_issues": {
                item.skill_id: validate_skill_static(item) for item in self.active_skills()
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
            "prospective_audits",
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
            "candidate_source_grounding_round_",
            "learning_checkpoint_",
            "prospective_validation_",
        )
        if reports_root.is_dir():
            for path in reports_root.rglob("*"):
                if path.is_file() and (
                    path.name in formal_report_names
                    or path.name.startswith(formal_report_prefixes)
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
                relative = [
                    str(path.relative_to(self.store.root)) for path in artifacts[:8]
                ]
                raise ExecutionError(
                    "--fresh requires a run ID with no formal training artifacts; "
                    f"found={relative}"
                )
            # Parsing here makes an accidental warm start fail before any online
            # readiness probe or manifest creation.
            self.initial_skill_library()
            return
        if not manifest_path.is_file():
            raise ExecutionError("--resume requires an existing immutable run manifest")
        self.verify_run_manifest()

    def active_skills(self) -> list[SkillContract]:
        version = self.registry.current()
        if version is not None:
            self.registry.validate(version, require_current_static_schema=True)
            return load_skill_directory(self.registry.versions / version, active_only=True)
        initial, _ = self.initial_skill_library()
        return initial

    def _candidate_validation_ages(
        self,
        candidates: list[SkillContract],
        *,
        source_batch_id: str,
    ) -> dict[str, int]:
        """Return outcome-blind completed validation-block counts.

        A candidate first nominated in ``source_batch_id`` has age zero.  A
        carry-over has exactly one contiguous DEFER audit ending in that source
        block.  Scheduling may use this lifecycle age, but never its rewards or
        safety values, so a later newcomer cannot steal every scarce same-domain
        case from a candidate approaching its declared horizon.
        """

        ages: dict[str, int] = {}
        for candidate in candidates:
            prior = self._prior_deferred_candidate_audit(
                skill_id=candidate.skill_id,
                source_batch_id=source_batch_id,
            )
            ages[candidate.skill_id] = (
                len(prior[1].validation_batch_ids) if prior is not None else 0
            )
        return ages

    def _embedded_candidate_assignments(
        self,
        candidates: list[SkillContract],
        case_ids: list[str],
        *,
        block_index: int,
        candidate_validation_ages: dict[str, int] | None = None,
    ) -> dict[str, list[SkillContract]]:
        """Preassign at most one candidate treatment to each unseen case.

        The other trajectories in the K group must remain samples from the same
        current-library prompt used for TF-GRPO.  Installing two candidates in one
        K=4 case previously left only two comparable current-policy trajectories
        and allowed validation traffic to consume the learning signal.  Domain
        candidates rotate over matching cases and across consecutive blocks;
        general candidates rotate over the remaining cases.  Candidates with
        more completed DEFER blocks are scheduled before newcomers, and equal-age
        siblings still rotate by the explicit zero-based block index.  Assignment
        uses only frozen block position, lifecycle age and domain/scope metadata,
        never rewards, hidden facts, evaluator scores or runtime randomness.
        """

        if block_index < 0:
            raise ValueError("candidate assignment block_index must be non-negative")
        ordered = sorted(candidates, key=lambda item: item.skill_id)
        candidate_ids = {item.skill_id for item in ordered}
        ages = candidate_validation_ages or {skill_id: 0 for skill_id in candidate_ids}
        if set(ages) != candidate_ids or any(
            not isinstance(age, int) or age < 0 for age in ages.values()
        ):
            raise ExecutionError("candidate validation ages do not match the cohort")
        general = [item for item in ordered if item.domain == "general"]
        domain_specific = [item for item in ordered if item.domain != "general"]

        def age_priority(items: list[SkillContract]) -> list[SkillContract]:
            """Put older hypotheses first while rotating only equal-age peers."""

            prioritized: list[SkillContract] = []
            for age in sorted({ages[item.skill_id] for item in items}, reverse=True):
                siblings = [item for item in items if ages[item.skill_id] == age]
                offset = block_index % len(siblings)
                prioritized.extend([*siblings[offset:], *siblings[:offset]])
            return prioritized

        assignments: dict[str, list[SkillContract]] = {case_id: [] for case_id in case_ids}
        remaining: list[str] = []
        domain_offsets: Counter[str] = Counter()
        domain_priority: dict[str, list[SkillContract]] = {}
        for case_id in case_ids:
            domain = self.main_adapter.case_domain(case_id) if domain_specific else "general"
            matching = domain_priority.setdefault(
                domain,
                age_priority([item for item in domain_specific if item.domain == domain]),
            )
            if matching:
                assignments[case_id] = [
                    matching[domain_offsets[domain] % len(matching)]
                ]
                domain_offsets[domain] += 1
            else:
                remaining.append(case_id)
        if general:
            general = age_priority(general)
            # A tiny diagnostic matrix can expose fewer candidates than the
            # formal block.  Never stack hypotheses in the same case merely to
            # make a probe appear exhaustive.
            for index, case_id in enumerate(remaining):
                assignments[case_id] = [general[index % len(general)]]
        budget = int(
            self.experiment.get("execution", {}).get(
                "maximum_concurrent_provisional_candidates",
                max(1, len(ordered)),
            )
        )
        if any(len(values) > 1 for values in assignments.values()):
            raise ExecutionError("a case cannot contain more than one provisional treatment")
        if len(ordered) > budget:
            raise ExecutionError("candidate cohort exceeds the declared block budget")
        return assignments

    @staticmethod
    def _embedded_case_arm_specs(
        *,
        active_skills: list[SkillContract],
        active_hash: str,
        assigned_candidates: list[SkillContract],
        group_size: int,
    ) -> list[tuple[str, list[SkillContract], str]]:
        """Build a K group with one treatment and at least three prompt peers."""

        arm_specs: list[tuple[str, list[SkillContract], str]] = []
        if len(assigned_candidates) > 1:
            raise ExecutionError("only one provisional candidate may be assigned to a case")
        if assigned_candidates and group_size < 4:
            raise ExecutionError(
                "embedded validation requires K>=4 to retain three current-prompt traces"
            )
        if assigned_candidates:
            arm_specs.append(("candidate_without", active_skills, active_hash))
            for candidate in assigned_candidates:
                enabled = candidate.model_copy(deep=True)
                enabled.status = "active"
                candidate_library = [*active_skills, enabled]
                arm_specs.append(
                    (
                        "candidate_with",
                        candidate_library,
                        skill_library_sha256(candidate_library),
                    )
                )
        while len(arm_specs) < group_size:
            arm_specs.append(("training_policy_sample", active_skills, active_hash))
        if len(arm_specs) != group_size:
            raise ExecutionError("case-level embedded arm count differs from K")
        return arm_specs

    def source_grounded_skills_for_ablation(self) -> list[SkillContract]:
        """Load source-grounded candidates without using next-block outcomes.

        This counterfactual library is used only in the frozen external ablation.  It
        never participates in later training batches, candidate selection, or the
        active registry.  Reports and candidate bytes are re-hashed so a stale or
        hand-edited rejected candidate cannot silently enter the arm.  If every
        document cannot coexist under the frozen prompt budget, source-round then
        report order performs an outcome-blind first fit; no document is truncated.
        """

        by_id: dict[str, SkillContract] = {}
        ordered_ids: list[str] = []
        for round_index in range(1, int(self.experiment["execution"]["evolution_rounds"]) + 1):
            report_path = (
                self.store.root
                / "reports"
                / f"candidate_source_grounding_round_{round_index:02d}.json"
            )
            if not report_path.is_file():
                continue
            report = json.loads(report_path.read_text(encoding="utf-8"))
            if report.get("status") != "provisional_candidates_staged_after_source_grounding":
                raise ExecutionError(f"invalid candidate grounding report: {report_path}")
            records = {
                str(item["candidate_file"]): item
                for item in report.get("records", [])
                if bool(item.get("valid"))
            }
            declared = [str(item) for item in report.get("valid_candidate_files", [])]
            if set(records) != set(declared):
                raise ExecutionError(
                    f"source-grounding report valid-file mismatch: round={round_index}"
                )
            for relative in declared:
                candidate_path = self.root / relative
                record = records[relative]
                if not candidate_path.is_file():
                    raise ExecutionError(f"source-grounded candidate missing: {relative}")
                candidate = load_skill(candidate_path)
                if skill_contract_definition_sha256(candidate) != record.get(
                    "candidate_contract_sha256"
                ):
                    raise ExecutionError(f"source-grounded candidate contract drift: {relative}")
                issues = validate_skill_static(candidate)
                if issues:
                    raise ExecutionError(
                        f"source-grounded candidate no longer passes static validation: "
                        f"{candidate.skill_id}: {issues}"
                    )
                prior = by_id.get(candidate.skill_id)
                if prior is not None and skill_contract_definition_sha256(
                    prior
                ) != skill_contract_definition_sha256(candidate):
                    raise ExecutionError(
                        f"source-grounded ablation has conflicting skill_id: {candidate.skill_id}"
                    )
                enabled = candidate.model_copy(deep=True)
                enabled.status = "active"
                if candidate.skill_id not in by_id:
                    ordered_ids.append(candidate.skill_id)
                by_id[candidate.skill_id] = enabled
        ordered = [by_id[skill_id] for skill_id in ordered_ids]
        admitted, rejected = admit_active_skills_by_prompt_capacity([], ordered)
        self._ungated_prompt_capacity_contract = {
            "policy": "source_round_then_grounding_report_order_outcome_blind_first_fit",
            "maximum_policy_skill_document_characters": (
                MAX_POLICY_SKILL_DOCUMENT_CHARACTERS
            ),
            "maximum_session_skill_memory_characters": (
                MAX_SESSION_SKILL_MEMORY_CHARACTERS
            ),
            "considered_skill_ids": ordered_ids,
            "admitted_skill_ids": [skill.skill_id for skill in admitted],
            "capacity_omissions": rejected,
            "uses_candidate_outcomes": False,
            "truncates_documents": False,
        }
        return admitted

    def external_arm_specs(self, active: list[SkillContract]) -> list[dict[str, Any]]:
        """Resolve the preregistered primary arms and explanatory ablations."""

        ungated = self.source_grounded_skills_for_ablation()
        available: dict[str, dict[str, Any]] = {
            "control_no_library": {
                "skills": [],
                "inference_role": "primary_control",
                "knowledge_source": "none",
            },
            "ungated_source_grounded_skills": {
                "skills": ungated,
                "inference_role": "explanatory_prospective_gate_ablation",
                "knowledge_source": (
                    "source_grounded_candidates_without_prospective_gate_under_frozen_"
                    "prompt_capacity"
                ),
                "selection_contract": self._ungated_prompt_capacity_contract,
            },
            "legal_skill_guard": {
                "skills": active,
                "inference_role": "primary_treatment",
                "knowledge_source": "accepted_prompt_skill_memory",
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
                    "delivery": "fixed_session_prompt_memory",
                    "selection_contract": value.get("selection_contract"),
                }
            )
            specs.append(value)
        return specs

    @staticmethod
    def _merged_accepted_library(
        active: list[SkillContract],
        candidates: list[SkillContract],
        audits: list[ProspectiveCandidateAudit],
    ) -> list[SkillContract]:
        """Build the exact post-validation library without publishing it."""

        candidate_by_id = {item.skill_id: item for item in candidates}
        audit_by_id = {item.skill_id: item for item in audits}
        if len(candidate_by_id) != len(candidates):
            raise ExecutionError("accepted activation cohort contains duplicate skill IDs")
        if set(candidate_by_id) != set(audit_by_id):
            raise ExecutionError("accepted activation cohort and audit set differ")
        if any(item.decision.decision != "ACCEPT" for item in audits):
            raise ExecutionError("only ACCEPT audits may enter an activation cohort")

        active_by_id = {item.skill_id: item for item in active}
        for candidate in candidates:
            prior = active_by_id.get(candidate.skill_id)
            if prior is not None and skill_contract_definition_sha256(
                prior
            ) != skill_contract_definition_sha256(candidate):
                raise ExecutionError(
                    "active library contains a different definition for accepted skill: "
                    f"{candidate.skill_id}"
                )
            enabled = candidate.model_copy(deep=True)
            enabled.status = "active"
            audit = audit_by_id[candidate.skill_id]
            enabled.evaluation.paired_cases = audit.decision.pairs
            enabled.evaluation.exposed_pairs = audit.decision.exposed_pairs
            enabled.evaluation.exposed_cases = audit.decision.exposed_cases
            enabled.evaluation.exposed_domains = audit.decision.exposed_domains
            enabled.evaluation.mean_delta_reward = audit.decision.mean_delta_reward
            enabled.evaluation.median_delta_reward = audit.decision.median_delta_reward
            enabled.evaluation.harmful_pair_rate = audit.decision.harmful_pair_rate
            enabled.evaluation.severe_risk_count = audit.decision.severe_risk_count
            enabled.evaluation.accepted_at = audit.completed_at
            active_by_id[enabled.skill_id] = enabled
        result = [active_by_id[skill_id] for skill_id in sorted(active_by_id)]
        capacity_issues = skill_memory_capacity_issues(result)
        if capacity_issues:
            raise ExecutionError(
                "accepted skill cohort exceeds the frozen prompt-memory capacity: "
                f"{capacity_issues}"
            )
        return result

    def _activate_accepted_skills(
        self,
        candidates: list[SkillContract],
        audits: list[ProspectiveCandidateAudit],
    ) -> str:
        """Idempotently publish one accepted cohort as one library version.

        The caller first persists a prospective-validation commit record and then
        invokes this method.  A process loss on either side is recoverable: an
        immutable version may exist without being current, and a persisted commit
        record may be replayed until its single pointer switch succeeds.
        """

        candidate_by_id = {item.skill_id: item for item in candidates}
        audit_by_id = {item.skill_id: item for item in audits}
        active = self._merged_accepted_library(self.active_skills(), candidates, audits)
        library_hash = skill_library_sha256(active)
        version = f"library_{library_hash[:16]}"
        destination = self.registry.versions / version
        if destination.exists():
            self.registry.validate(version, require_current_static_schema=True)
        else:
            self.registry.create_version(
                version,
                active,
                parent_version=self.registry.current(),
                evidence={
                    "transaction": "prospective_validation_cohort",
                    "candidate_skill_ids": sorted(candidate_by_id),
                    "audit_decisions": {
                        skill_id: audit_by_id[skill_id].decision.model_dump(mode="json")
                        for skill_id in sorted(audit_by_id)
                    },
                    "audit_completed_at": {
                        skill_id: audit_by_id[skill_id].completed_at
                        for skill_id in sorted(audit_by_id)
                    },
                },
            )
        if self.registry.current() != version:
            self.registry.activate(version)
        return version

    def _activate_accepted_skill(
        self, candidate: SkillContract, audit: ProspectiveCandidateAudit
    ) -> str:
        """Compatibility wrapper for one-candidate audit call sites."""

        return self._activate_accepted_skills([candidate], [audit])

    def _runner(self, *, paired: bool, cache_namespace: str) -> TrajectoryRunner:
        # Prospective candidate validations repeatedly evaluate an
        # identical baseline library on the same case/persona/seed cells.  Keep
        # those *request* replays shared inside this run: ReplayCachedChatClient
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
        # and counterfactual target allocation while making the candidate the sole
        # intervention in its causal pair.
        policy: Any = ReplayCachedChatClient(
            self.local_client,
            replay_cache_root / "lawyer_policy",
        )
        # The training-only first-target allocation is a declared deterministic
        # intervention; the frozen lawyer still authors every natural question and
        # supplies the subsequent stochastic policy behaviour. Exact replay makes
        # identical client and memo requests common-random-number controls.
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
        # Initial agendas are shared infrastructure.  Exact replay holds the plan
        # fixed across TF-GRPO group members as well as across paired evaluation arms;
        # only the lawyer policy remains stochastic after the declared target fork.
        planner_local: Any = self.planner_client
        lawyer = self.roles["roles"]["lawyer_policy"]
        planner = self.roles["roles"]["consultation_planner"]
        client = self.roles["roles"]["client_fact_selector"]
        memo = self.roles["roles"]["memo_renderer"]
        policy_temperature = (
            float(lawyer["paired_evaluation_temperature"])
            if paired
            else float(lawyer["training_temperature"])
        )
        return TrajectoryRunner(
            policy_client=policy,
            client_selector=selector,
            client_disclosure_classifier=disclosure_classifier,
            memo_client=memo_local,
            policy_prompt_path=self.root / "configs/prompts/consultation_policy_zh.txt",
            client_prompt_path=self.root / "configs/prompts/client_fact_selector_zh.txt",
            client_disclosure_prompt_path=(
                self.root / "configs/prompts/client_fact_disclosure_zh.txt"
            ),
            memo_prompt_path=self.root / "configs/prompts/memo_writer_zh.txt",
            planner_prompt_path=self.root / "configs/prompts/consultation_planner_zh.txt",
            planner_repair_prompt_path=(
                self.root / "configs/prompts/consultation_planner_repair_zh.txt"
            ),
            planner_client=planner_local,
            policy_generation=GenerationConfig(
                temperature=policy_temperature,
                top_p=float(lawyer["top_p"]),
                max_tokens=int(lawyer["max_tokens"]),
                seed=42,
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
            planner_generation=GenerationConfig(
                temperature=float(planner["temperature"]),
                top_p=float(planner["top_p"]),
                max_tokens=int(planner["max_tokens"]),
                seed=42,
                disable_thinking=not bool(planner["enable_thinking"]),
            ),
            planner_repair_generation=GenerationConfig(
                temperature=float(planner["repair_temperature"]),
                top_p=float(planner["repair_top_p"]),
                max_tokens=int(planner["repair_max_tokens"]),
                seed=42,
                disable_thinking=not bool(planner["repair_enable_thinking"]),
            ),
            model_revision=self.local_revision,
            max_policy_attempts=int(self.experiment["execution"]["policy_repair_attempts"]),
            max_client_selection_attempts=int(
                self.experiment["execution"]["client_selection_attempts"]
            ),
            max_memo_attempts=int(self.experiment["execution"]["memo_generation_attempts"]),
            max_planning_attempts=int(
                self.experiment["execution"]["consultation_planning_attempts"]
            ),
            shuffle_equal_criticality_fact_presentation=(
                not paired
                and bool(
                    self.experiment["trajectory_sampling"].get(
                        "shuffle_equal_criticality_fact_presentation", False
                    )
                )
            ),
            counterfactual_initial_target_allocation=(
                not paired
                and bool(
                    self.experiment["trajectory_sampling"].get(
                        "counterfactual_initial_target_allocation", False
                    )
                )
            ),
            counterfactual_initial_target_replicates=int(
                self.experiment["trajectory_sampling"].get(
                    "counterfactual_initial_target_replicates", 1
                )
            ),
            counterfactual_followup_target_allocation=(
                not paired
                and bool(
                    self.experiment["trajectory_sampling"].get(
                        "counterfactual_followup_target_allocation", False
                    )
                )
            ),
        )

    def generate_training_round(
        self,
        round_index: int,
        *,
        case_limit: int | None = None,
        preceding_candidates: list[Path] | None = None,
        input_skills: list[SkillContract] | None = None,
    ) -> list[ResearchTrajectory]:
        if not 1 <= round_index <= len(self.training_plan.batches):
            raise ValueError(f"training batch index out of range: {round_index}")
        declared_batch = self.training_plan.batches[round_index - 1]
        partition = declared_batch.batch_id
        case_ids = list(declared_batch.case_ids)
        if case_limit is not None:
            case_ids = case_ids[:case_limit]
        # The exact pre-validation library belongs to the block checkpoint, not
        # to whatever registry pointer happens to be current after a crash.  In
        # particular, a process may stop after the preceding candidates were
        # activated but before this block's provisional manifest was committed.
        # Supplying the checkpoint-owned input makes that resume replay the same
        # trajectory identities and prompts instead of silently training on the
        # post-validation library.
        skills = list(input_skills) if input_skills is not None else self.active_skills()
        candidate_paths = sorted(preceding_candidates or [])
        candidate_skills = [load_skill(path) for path in candidate_paths]
        budget = int(
            self.experiment["execution"].get(
                "maximum_concurrent_provisional_candidates", 6
            )
        )
        if len(candidate_skills) > budget:
            raise ExecutionError("preceding candidate count exceeds the declared block budget")
        group_size = int(self.experiment["trajectory_sampling"]["group_size"])
        if candidate_skills and group_size < 4:
            raise ExecutionError(
                "embedded candidate validation requires K>=4 for three teacher-evidence traces"
            )
        for candidate in candidate_skills:
            if candidate.status != "provisional":
                raise ExecutionError(
                    f"embedded next-block use requires a provisional skill: {candidate.skill_id}"
                )
            issues = validate_skill_static(candidate)
            if issues:
                raise ExecutionError(f"candidate static validation failed: {issues}")
        enabled_candidates = [candidate.model_copy(deep=True) for candidate in candidate_skills]
        for candidate in enabled_candidates:
            candidate.status = "active"
        _, capacity_rejections = admit_active_skills_by_prompt_capacity(
            skills,
            enabled_candidates,
        )
        if capacity_rejections:
            raise ExecutionError(
                "embedded next-block candidate cohort violates the frozen prompt-memory "
                f"capacity: {capacity_rejections}"
            )
        active_hash = skill_library_sha256(skills)
        candidate_ages = (
            self._candidate_validation_ages(
                candidate_skills,
                source_batch_id=self.training_plan.batches[round_index - 2].batch_id,
            )
            if candidate_skills and round_index > 1
            else {candidate.skill_id: 0 for candidate in candidate_skills}
        )
        candidate_assignments = self._embedded_candidate_assignments(
            candidate_skills,
            case_ids,
            block_index=round_index - 1,
            candidate_validation_ages=candidate_ages,
        )
        runner = self._runner(paired=False, cache_namespace=partition)
        requests: list[tuple[Any, ...]] = []
        for case_id in case_ids:
            persona_id = declared_batch.persona_assignment[case_id]
            persona = self.main_adapter.persona(persona_id)
            arm_specs = self._embedded_case_arm_specs(
                active_skills=skills,
                active_hash=active_hash,
                assigned_candidates=candidate_assignments[case_id],
                group_size=group_size,
            )
            for seed in self.experiment["trajectory_sampling"]["training_group_seeds"]:
                group_id = f"{partition}.{case_id}.{persona_id}.seed_{seed}"
                for sample_index, (method, arm_skills, arm_hash) in enumerate(arm_specs):
                    identity = trajectory_identity(
                        run_id=self.run_id,
                        partition=partition,
                        method=method,
                        case_id=case_id,
                        persona=persona_id,
                        seed=int(seed),
                        sample_index=sample_index,
                        skill_library_version=arm_hash,
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
                            arm_skills,
                            arm_hash,
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
        preceding_candidates: list[Path],
    ) -> dict[str, list[SkillContract]]:
        """Return every executor-owned prompt library allowed in one block."""

        libraries: list[list[SkillContract]] = [list(input_skills)]
        for path in sorted(preceding_candidates):
            candidate = load_skill(path)
            enabled = candidate.model_copy(deep=True)
            enabled.status = "active"
            libraries.append([*input_skills, enabled])
        return {skill_library_sha256(library): library for library in libraries}

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
            int(item)
            for item in self.experiment["trajectory_sampling"]["training_group_seeds"]
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
                    and item.method in {"candidate_without", "training_policy_sample"}
                ]
                if len(matches) != 1:
                    raise ExecutionError(
                        "learning-curve current cell is not unique: "
                        f"batch={batch.batch_id}; case={case_id}; seed={seed}; "
                        f"matches={len(matches)}"
                    )
                selected.append(matches[0])
        return selected

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
            self.store.trajectory_path(partition, item.trajectory_id).resolve()
            for item in values
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
        return (
            self.store.root
            / "reports"
            / f"development_curve_point_{round_index:02d}.json"
        )

    def _validate_learning_curve_point_artifact(
        self,
        *,
        round_index: int,
        case_limit: int | None,
        run_manifest_sha256: str,
        expected_input_skill_ids: list[str],
        expected_input_skill_library_sha256: str,
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
        if not isinstance(point, dict) or set(point) != expected_fields:
            raise ExecutionError(
                f"development learning-curve point fields drifted: {batch.batch_id}"
            )
        declared_batch_cases = list(batch.case_ids)
        if case_limit is not None:
            declared_batch_cases = declared_batch_cases[:case_limit]
        expected_sentinel_ids = [
            case_id
            for case_id in self.learning_curve_sentinels[batch.batch_id]
            if case_id in set(declared_batch_cases)
        ]
        expected_empty_hash = skill_library_sha256([])
        identity_baseline = not expected_input_skill_ids
        bindings = {
            "schema_version": 1,
            "run_id": self.run_id,
            "run_manifest_sha256": run_manifest_sha256,
            "round": round_index,
            "batch_id": batch.batch_id,
            "case_limit": case_limit,
            "status": "prequential_fixed_shadow_complete",
            "evidence_role": self.experiment["learning_curve"]["evidence_role"],
            "sentinel_case_ids": expected_sentinel_ids,
            "input_active_skill_ids": expected_input_skill_ids,
            "input_skill_library_sha256": expected_input_skill_library_sha256,
            "empty_skill_library_sha256": expected_empty_hash,
            "identity_baseline": identity_baseline,
        }
        mismatches = [
            field for field, expected in bindings.items() if point.get(field) != expected
        ]
        if mismatches:
            raise ExecutionError(
                "development learning-curve point binding mismatch: "
                f"batch={batch.batch_id}; fields={mismatches}"
            )
        if not expected_sentinel_ids:
            raise ExecutionError(
                f"development learning-curve sentinel is empty: {batch.batch_id}"
            )

        curve = point.get("curve")
        if not isinstance(curve, dict):
            raise ExecutionError("development learning-curve statistic is missing")
        current_partition = batch.batch_id
        empty_partition = (
            current_partition
            if identity_baseline
            else f"learning_curve_shadow_{batch.batch_id}"
        )
        if any(
            (
                curve.get("sentinel_id") != batch.batch_id,
                curve.get("identity_baseline") is not identity_baseline,
                curve.get("current_library_version")
                != expected_input_skill_library_sha256,
                curve.get("empty_library_version") != expected_empty_hash,
                curve.get("current_skill_ids") != expected_input_skill_ids,
                curve.get("partition_mapping")
                != {"current": current_partition, "empty": empty_partition},
                curve.get("case_cluster_count") != len(expected_sentinel_ids),
            )
        ):
            raise ExecutionError(
                f"development learning-curve statistic binding drift: {batch.batch_id}"
            )
        expected_pairs = len(expected_sentinel_ids) * len(
            self.experiment["trajectory_sampling"]["training_group_seeds"]
        )
        if curve.get("pair_count") != expected_pairs:
            raise ExecutionError(
                f"development learning-curve pair count drift: {batch.batch_id}"
            )
        pair_rows = curve.get("pairs")
        if not isinstance(pair_rows, list) or len(pair_rows) != expected_pairs:
            raise ExecutionError("development learning-curve pair records are incomplete")
        current_ids = {str(row.get("current_trajectory_id")) for row in pair_rows}
        empty_ids = {str(row.get("empty_trajectory_id")) for row in pair_rows}
        if len(current_ids) != expected_pairs or len(empty_ids) != expected_pairs:
            raise ExecutionError("development learning-curve trajectory identities collide")

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
                    value[trajectory_id],
                    expected_path=expected_path,
                    label=f"{label} {trajectory_id}",
                )

        verify_artifact_map(
            point["current_trajectory_artifacts"],
            expected_ids=current_ids,
            partition=current_partition,
            evaluation=False,
            label="development current trajectory",
        )
        verify_artifact_map(
            point["current_evaluation_artifacts"],
            expected_ids=current_ids,
            partition=None,
            evaluation=True,
            label="development current evaluation",
        )
        persisted_isolation: dict[str, Any] | None = None
        if identity_baseline:
            if point["empty_trajectory_artifacts"] != {} or point[
                "empty_evaluation_artifacts"
            ] != {}:
                raise ExecutionError("identity learning-curve point duplicated the empty arm")
            if point["intervention_isolation_artifact"] is not None:
                raise ExecutionError("identity learning-curve point cannot cite an intervention")
        else:
            verify_artifact_map(
                point["empty_trajectory_artifacts"],
                expected_ids=empty_ids,
                partition=empty_partition,
                evaluation=False,
                label="development empty trajectory",
            )
            verify_artifact_map(
                point["empty_evaluation_artifacts"],
                expected_ids=empty_ids,
                partition=None,
                evaluation=True,
                label="development empty evaluation",
            )
            isolation_path = self._verify_artifact_record(
                point["intervention_isolation_artifact"],
                expected_path=(
                    self.store.root
                    / "health"
                    / f"development_curve_intervention_isolation_{batch.batch_id}.json"
                ),
                label="development skill-library intervention isolation",
            )
            isolation = json.loads(isolation_path.read_text(encoding="utf-8"))
            if (
                isolation.get("passed") is not True
                or isolation.get("current_partition") != current_partition
                or isolation.get("empty_partition") != empty_partition
                or isolation.get("pair_count") != expected_pairs
            ):
                raise ExecutionError(
                    f"development skill-library isolation failed: {batch.batch_id}"
                )
            persisted_isolation = isolation

        current_trajectories = [
            self.store.load_model(
                self.store.trajectory_path(current_partition, trajectory_id),
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
        empty_trajectories = (
            []
            if identity_baseline
            else [
                self.store.load_model(
                    self.store.trajectory_path(empty_partition, trajectory_id),
                    ResearchTrajectory,
                )
                for trajectory_id in sorted(empty_ids)
            ]
        )
        empty_evaluations = (
            {}
            if identity_baseline
            else {
                trajectory_id: self.store.load_model(
                    self.store.evaluation_path(trajectory_id), TrajectoryEvaluation
                )
                for trajectory_id in sorted(empty_ids)
            }
        )
        if not identity_baseline:
            recomputed_isolation = skill_library_intervention_isolation_report(
                current_trajectories,
                empty_trajectories,
                set(expected_input_skill_ids),
                current_partition,
                empty_partition,
            )
            if canonical_json_sha256(recomputed_isolation) != canonical_json_sha256(
                persisted_isolation
            ):
                raise ExecutionError(
                    f"development skill-library isolation artifact drift: {batch.batch_id}"
                )
        recomputed_curve = build_prequential_sentinel_report(
            sentinel_id=batch.batch_id,
            current_trajectories=current_trajectories,
            current_evaluations=current_evaluations,
            current_partition=current_partition,
            current_library_version=expected_input_skill_library_sha256,
            current_skill_ids=set(expected_input_skill_ids),
            empty_partition=empty_partition,
            empty_library_version=expected_empty_hash,
            empty_trajectories=None if identity_baseline else empty_trajectories,
            empty_evaluations=None if identity_baseline else empty_evaluations,
            identity_baseline=identity_baseline,
            bootstrap_samples=int(self.experiment["learning_curve"]["bootstrap_samples"]),
            confidence_level=float(
                self.experiment["prospective_validation"]["confidence_level"]
            ),
            bootstrap_seed=int(self.experiment["learning_curve"]["bootstrap_seed"]),
        )
        recomputed_curve["initial_infrastructure_identity"][
            "stepwise_intervention_isolation"
        ] = (
            "identity_by_construction"
            if identity_baseline
            else "passed_by_bound_executor_artifact"
        )
        if canonical_json_sha256(recomputed_curve) != canonical_json_sha256(curve):
            raise ExecutionError(
                f"development learning-curve statistic drift: {batch.batch_id}"
            )
        return point

    def prepare_development_curve_point(
        self,
        *,
        round_index: int,
        case_limit: int | None,
        run_manifest_sha256: str,
        input_skills: list[SkillContract],
        trajectories: list[ResearchTrajectory],
        evaluations: dict[str, TrajectoryEvaluation],
    ) -> dict[str, Any]:
        """Measure the input library before any current-block teacher decision."""

        batch = self.training_plan.batches[round_index - 1]
        input_ids = sorted(item.skill_id for item in input_skills)
        input_hash = skill_library_sha256(input_skills)
        point_path = self._learning_curve_point_path(round_index)
        if point_path.is_file():
            return self._validate_learning_curve_point_artifact(
                round_index=round_index,
                case_limit=case_limit,
                run_manifest_sha256=run_manifest_sha256,
                expected_input_skill_ids=input_ids,
                expected_input_skill_library_sha256=input_hash,
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
        empty_hash = skill_library_sha256([])
        identity_baseline = not input_skills
        empty: list[ResearchTrajectory] = []
        empty_evaluations: dict[str, TrajectoryEvaluation] = {}
        isolation_artifact: dict[str, str] | None = None
        empty_partition = batch.batch_id
        if not identity_baseline:
            empty_partition = f"learning_curve_shadow_{batch.batch_id}"
            empty = self.generate_learning_curve_shadow(
                round_index=round_index,
                current_trajectories=current,
            )
            isolation = skill_library_intervention_isolation_report(
                current,
                empty,
                set(input_ids),
                batch.batch_id,
                empty_partition,
            )
            isolation_path = (
                self.store.root
                / "health"
                / f"development_curve_intervention_isolation_{batch.batch_id}.json"
            )
            self.store.immutable_json(isolation_path, isolation)
            if isolation.get("passed") is not True:
                raise ExecutionError(
                    "development curve is not a sole skill-library intervention: "
                    f"batch={batch.batch_id}; failures={isolation.get('failure_count')}"
                )
            isolation_artifact = self._relative_artifact_record(isolation_path)
            empty_evaluations = self.score_trajectories(
                empty,
                self.main_adapter,
                enforce_candidate_intervention_isolation=False,
                expected_skill_libraries={empty_hash: []},
            )

        curve = build_prequential_sentinel_report(
            sentinel_id=batch.batch_id,
            current_trajectories=current,
            current_evaluations=current_evaluations,
            current_partition=batch.batch_id,
            current_library_version=input_hash,
            current_skill_ids=set(input_ids),
            empty_partition=empty_partition,
            empty_library_version=empty_hash,
            empty_trajectories=None if identity_baseline else empty,
            empty_evaluations=None if identity_baseline else empty_evaluations,
            identity_baseline=identity_baseline,
            bootstrap_samples=int(self.experiment["learning_curve"]["bootstrap_samples"]),
            confidence_level=float(
                self.experiment["prospective_validation"]["confidence_level"]
            ),
            bootstrap_seed=int(self.experiment["learning_curve"]["bootstrap_seed"]),
        )
        curve["initial_infrastructure_identity"]["stepwise_intervention_isolation"] = (
            "identity_by_construction"
            if identity_baseline
            else "passed_by_bound_executor_artifact"
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
            "schema_version": 1,
            "run_id": self.run_id,
            "run_manifest_sha256": run_manifest_sha256,
            "round": round_index,
            "batch_id": batch.batch_id,
            "case_limit": case_limit,
            "status": "prequential_fixed_shadow_complete",
            "evidence_role": self.experiment["learning_curve"]["evidence_role"],
            "sentinel_case_ids": [
                case_id
                for case_id in self.learning_curve_sentinels[batch.batch_id]
                if case_id in {item.case_id for item in current}
            ],
            "input_active_skill_ids": input_ids,
            "input_skill_library_sha256": input_hash,
            "empty_skill_library_sha256": empty_hash,
            "identity_baseline": identity_baseline,
            "current_trajectory_artifacts": artifact_map(
                current, partition=batch.batch_id, evaluation=False
            ),
            "current_evaluation_artifacts": artifact_map(
                current, partition=batch.batch_id, evaluation=True
            ),
            "empty_trajectory_artifacts": artifact_map(
                empty, partition=empty_partition, evaluation=False
            ),
            "empty_evaluation_artifacts": artifact_map(
                empty, partition=empty_partition, evaluation=True
            ),
            "intervention_isolation_artifact": isolation_artifact,
            "curve": curve,
            "completed_at": datetime.now(UTC).isoformat(),
        }
        self.store.immutable_json(point_path, value)
        return self._validate_learning_curve_point_artifact(
            round_index=round_index,
            case_limit=case_limit,
            run_manifest_sha256=run_manifest_sha256,
            expected_input_skill_ids=input_ids,
            expected_input_skill_library_sha256=input_hash,
        )

    def score_trajectories(
        self,
        trajectories: list[ResearchTrajectory],
        adapter: DLawBenchAdapter,
        *,
        enforce_candidate_intervention_isolation: bool = True,
        expected_skill_libraries: Mapping[str, list[SkillContract]] | None = None,
    ) -> dict[str, TrajectoryEvaluation]:
        partitions = sorted({trajectory.partition for trajectory in trajectories})
        report_name = "pre_scoring_health_" + "__".join(partitions)
        evaluator_cases = {
            case_id: adapter.evaluator_case(case_id)
            for case_id in {trajectory.case_id for trajectory in trajectories}
        }
        health_report = trajectory_health_report(
            trajectories,
            evaluator_cases,
            expected_run_id=self.store.run_id,
        )
        isolation_report = (
            candidate_intervention_isolation_report(trajectories)
            if enforce_candidate_intervention_isolation
            else {
                "schema_version": 2,
                "scope": "candidate_prompt_intervention_not_applicable_to_learning_curve_shadow",
                "passed": True,
                "pair_count": 0,
                "exposed_pair_count": 0,
                "failed_pair_count": 0,
                "matrix_failure_count": 0,
                "failure_count": 0,
                "uses_reward_or_semantic_outcome": False,
                "pairs": [],
                "matrix_failures": [],
            }
        )
        quality_diagnostics = cast(dict[str, Any], health_report["quality_diagnostics"])
        quality_diagnostics["candidate_intervention_isolation"] = isolation_report
        memory_contract_report = (
            skill_memory_contract_report(trajectories, expected_skill_libraries)
            if expected_skill_libraries is not None
            else None
        )
        if memory_contract_report is not None:
            quality_diagnostics["skill_memory_contract"] = memory_contract_report
        if not isolation_report["passed"]:
            failure_count = int(isolation_report["failure_count"])
            counts = cast(dict[str, int], health_report["counts"])
            counts["candidate_intervention_isolation_failure"] = failure_count
            health_report["blocking_issue_count"] = int(
                health_report["blocking_issue_count"]
            ) + failure_count
            health_report["healthy"] = False
            issues = cast(list[dict[str, Any]], health_report["issues"])
            available_issue_slots = max(0, 100 - len(issues))
            for pair in isolation_report["pairs"]:
                if pair["passed"] or available_issue_slots == 0:
                    continue
                difference = pair.get("first_difference") or {}
                issues.append(
                    {
                        "code": "candidate_intervention_isolation_failure",
                        "trajectory_id": pair["candidate_trajectory_id"],
                        "turn": int(difference.get("turn") or 0),
                        "detail": f"{pair['reason']}:{difference.get('field') or 'n/a'}",
                    }
                )
                available_issue_slots -= 1
            for failure in isolation_report["matrix_failures"]:
                if available_issue_slots == 0:
                    break
                issues.append(
                    {
                        "code": "candidate_intervention_isolation_failure",
                        "trajectory_id": "",
                        "turn": 0,
                        "detail": (
                            f"{failure['reason']}:{failure['partition']}:{failure['group_id']}"
                        ),
                    }
                )
                available_issue_slots -= 1
            health_report["issues_truncated"] = max(
                0,
                int(health_report["blocking_issue_count"]) - len(issues),
            )
        if memory_contract_report is not None and not memory_contract_report["passed"]:
            failure_count = int(memory_contract_report["failure_count"])
            counts = cast(dict[str, int], health_report["counts"])
            counts["skill_memory_contract_failure"] = failure_count
            health_report["blocking_issue_count"] = int(
                health_report["blocking_issue_count"]
            ) + failure_count
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
        if not isolation_report["passed"]:
            raise ExecutionError(
                "candidate intervention isolation is infrastructure-invalid; "
                "stop the complete batch before semantic scoring and do not classify "
                f"the candidate; report={health_path}; "
                f"failed_pairs={isolation_report['failure_count']}"
            )
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
        prior_validation_feedback = self._completed_validation_feedback_for_teacher(round_index)
        partitions = {item.partition for item in trajectories}
        if len(partitions) != 1:
            raise ExecutionError("candidate proposal trajectories span partitions")
        partition = next(iter(partitions))
        health_path = self.store.root / "health" / f"pre_scoring_health_{partition}.json"
        if not health_path.is_file():
            raise ExecutionError("candidate proposal is missing pre-scoring health report")
        health_report = json.loads(health_path.read_text(encoding="utf-8"))
        attribution_review = (health_report.get("quality_diagnostics") or {}).get(
            "training_group_attribution_review"
        )
        if not isinstance(attribution_review, dict) or not attribution_review.get(
            "scoring_eligible"
        ):
            raise ExecutionError(
                "candidate proposal requires an eligible training-group attribution review"
            )
        scoreable_group_ids = {
            str(item) for item in attribution_review.get("scoreable_group_ids") or []
        }
        by_group = tf_grpo_teacher_evidence_groups(trajectories, scoreable_group_ids)
        groups: list[tuple[AdvantageGroup, dict[str, ResearchTrajectory]]] = []
        causal_selections: dict[str, list[ContrastSelection]] = {}
        for group_id, members in by_group.items():
            mapped = {item.trajectory_id: item for item in members}
            group = compute_advantages(
                group_id,
                [
                    ScoredMember(
                        trajectory_id=item.trajectory_id,
                        reward=evaluations[item.trajectory_id].reward.final_reward,
                        premature_final=(
                            evaluations[item.trajectory_id].safety_metrics.premature_final_rate > 0
                        ),
                        unsupported_claim=(
                            evaluations[item.trajectory_id].safety_metrics.unsupported_claim_rate
                            > 0
                        ),
                        turns=sum(bool(step.rendered_question) for step in item.steps),
                    )
                    for item in members
                ],
                epsilon=float(self.experiment["skill_evolution"]["group_advantage_epsilon"]),
            )
            group = require_distinct_learning_traces(group, mapped)
            selections = (
                []
                if group.skip_reason == "identical_policy_trace"
                else select_causally_aligned_contrasts(group, mapped)
            )
            if not selections:
                group = group.model_copy(
                    update={
                        "informative": False,
                        "skip_reason": "no_shared_state_locally_attributable_policy_fork",
                    }
                )
            else:
                causal_selections[group_id] = selections
            groups.append((group, mapped))
        # A genuine shared-state counterfactual policy fork is enough to nominate
        # a domain-bounded provisional hypothesis after deterministic source
        # replay; it is not evidence of cross-case efficacy. Persist every fork so
        # general hypotheses and lexical rerank rules can still require repeated
        # cumulative support, while the next unseen block retains sole authority
        # to activate a scoped provisional candidate.
        evidence_root = self.store.root / "evidence" / "causal_contrasts"
        new_patch_count = 0
        for group, mapped in groups:
            selections = causal_selections.get(group.group_id) or []
            if not selections:
                continue
            group_partitions = {item.partition for item in mapped.values()}
            if len(group_partitions) != 1:
                raise ExecutionError(f"causal evidence group spans partitions: {group.group_id}")
            for selection in selections:
                evidence_group_id = f"{group.group_id}::{selection.signal_family}"
                evidence_group = group.model_copy(update={"group_id": evidence_group_id})
                patch = CausalEvidencePatch(
                    round_index=round_index,
                    partition=next(iter(group_partitions)),
                    group=evidence_group,
                    selection=selection,
                    trajectory_ids=sorted(mapped),
                    trajectory_sha256={
                        trajectory_id: sha256_file(
                            self.store.trajectory_path(next(iter(group_partitions)), trajectory_id)
                        )
                        for trajectory_id in sorted(mapped)
                    },
                    evaluation_sha256={
                        trajectory_id: sha256_file(self.store.evaluation_path(trajectory_id))
                        for trajectory_id in sorted(mapped)
                    },
                )
                patch_path = evidence_root / (
                    f"round_{round_index:02d}_{canonical_json_sha256(evidence_group_id)[:16]}.json"
                )
                if patch_path.is_file():
                    prior = self.store.load_model(patch_path, CausalEvidencePatch)
                    if canonical_json_sha256(
                        prior.model_dump(mode="json")
                    ) != canonical_json_sha256(patch.model_dump(mode="json")):
                        raise ExecutionError(f"causal evidence patch drift: {patch_path}")
                else:
                    self.store.save_model(patch_path, patch)
                    new_patch_count += 1

        accumulated_contrasts: list[
            tuple[AdvantageGroup, ContrastSelection, dict[str, ResearchTrajectory]]
        ] = []
        accumulated_evaluations: dict[str, TrajectoryEvaluation] = {}
        evidence_rounds: set[int] = set()
        for patch_path in sorted(evidence_root.glob("*.json")):
            patch = self.store.load_model(patch_path, CausalEvidencePatch)
            evidence_rounds.add(patch.round_index)
            mapped: dict[str, ResearchTrajectory] = {}
            for trajectory_id in patch.trajectory_ids:
                trajectory_path = self.store.trajectory_path(patch.partition, trajectory_id)
                evaluation_path = self.store.evaluation_path(trajectory_id)
                if sha256_file(trajectory_path) != patch.trajectory_sha256[trajectory_id]:
                    raise ExecutionError(f"causal evidence trajectory drift: {trajectory_id}")
                if sha256_file(evaluation_path) != patch.evaluation_sha256[trajectory_id]:
                    raise ExecutionError(f"causal evidence evaluation drift: {trajectory_id}")
                mapped[trajectory_id] = self.store.load_model(trajectory_path, ResearchTrajectory)
                accumulated_evaluations[trajectory_id] = self.store.load_model(
                    evaluation_path, TrajectoryEvaluation
                )
            if any(
                item.method not in {"candidate_without", "training_policy_sample"}
                for item in mapped.values()
            ):
                raise ExecutionError(
                    "causal evidence bank contains candidate-treatment traffic; "
                    f"fresh run required: {patch_path}"
                )
            if len(mapped) < 3 or len(
                {item.skill_library_version for item in mapped.values()}
            ) != 1:
                raise ExecutionError(
                    "causal evidence bank lacks three same-prompt traces: "
                    f"{patch_path}"
                )
            accumulated_contrasts.append((patch.group, patch.selection, mapped))

        evidence_budget = int(
            self.experiment["execution"].get(
                "teacher_evidence_group_budget_per_candidate",
                self.experiment["execution"].get("teacher_evidence_group_budget_per_round", 15),
            )
        )
        configured_call_budget = int(self.experiment["execution"]["teacher_call_budget_per_round"])
        if candidate_budget is None:
            candidate_budget = configured_call_budget
        if candidate_budget < 0:
            raise ExecutionError("candidate budget cannot be negative")
        call_budget = min(configured_call_budget, candidate_budget)
        evidence_clusters = teacher_evidence_cluster_summaries(accumulated_contrasts)
        eligible_evidence_clusters = [item for item in evidence_clusters if bool(item["eligible"])]

        # Never spend a later teacher call on byte-identical cumulative evidence.
        attempted_fingerprints: set[str] = set()
        attempted_cluster_ids: set[str] = set()
        for prior_manifest_path in sorted(
            (self.store.root / "manifests").glob("teacher_round_*.json")
        ):
            prior_manifest = json.loads(prior_manifest_path.read_text(encoding="utf-8"))
            if int(prior_manifest.get("round", round_index)) >= round_index:
                continue
            for fingerprint in prior_manifest.get("attempted_evidence_fingerprints", []):
                attempted_fingerprints.add(str(fingerprint))
            legacy_fingerprint = prior_manifest.get("attempted_evidence_fingerprint")
            if legacy_fingerprint:
                attempted_fingerprints.add(str(legacy_fingerprint))
            for cluster_id in prior_manifest.get("attempted_evidence_cluster_ids", []):
                attempted_cluster_ids.add(str(cluster_id))
            legacy_cluster_id = prior_manifest.get("attempted_evidence_cluster_id")
            if legacy_cluster_id:
                attempted_cluster_ids.add(str(legacy_cluster_id))

        chosen_clusters = select_teacher_evidence_clusters(
            evidence_clusters,
            attempted_fingerprints=attempted_fingerprints,
            attempted_cluster_ids=attempted_cluster_ids,
            budget=call_budget,
        )
        context_by_id = {item[0].group_id: item for item in accumulated_contrasts}
        attempts: list[dict[str, Any]] = []
        selected_group_map: dict[str, tuple[AdvantageGroup, dict[str, ResearchTrajectory]]] = {}
        proposal_dir = self.store.root / "teacher" / f"round_{round_index:02d}"
        batch_prefix = f"{self.training_plan.batches[round_index - 1].batch_id}.semantic_advantage"
        for cluster, fingerprint in chosen_clusters:
            eligible_group_ids = set(cluster["group_ids"])
            selected_groups = select_diverse_teacher_groups(
                [
                    (group, mapped)
                    for group, _, mapped in accumulated_contrasts
                    if group.group_id in eligible_group_ids
                ],
                budget=evidence_budget,
                maximum_per_case=int(
                    self.experiment["execution"]["maximum_teacher_groups_per_case"]
                ),
            )
            for group, mapped in selected_groups:
                selected_group_map[group.group_id] = (group, mapped)
            attempts.append(
                {
                    "cluster": cluster,
                    "fingerprint": fingerprint,
                    "selected_groups": selected_groups,
                    "contrasts": [context_by_id[group.group_id] for group, _ in selected_groups],
                    "proposal_path": proposal_dir / f"proposal_{fingerprint[:16]}.json",
                    "batch_id": f"{batch_prefix}.{fingerprint[:12]}",
                }
            )

        # Keep failed documents in the teacher's history so it cannot silently
        # replay or rename a rejected hypothesis. A rejected prompt skill is
        # negative evidence, not a permanent reservation on an advice topic.
        runtime_skills = self.active_skills()
        existing_by_id: dict[str, SkillContract] = {}
        for skill in [
            *load_skill_directory(self.candidate_root),
            *load_skill_directory(self.store.root / "skills" / "rejected"),
            *runtime_skills,
        ]:
            existing_by_id[skill.skill_id] = skill
        existing = list(existing_by_id.values())
        candidate_paths: list[Path] = []
        round_candidate_documents: dict[str, str] = {}
        round_document_owners: dict[str, str] = {}
        missing_proposals = sum(not attempt["proposal_path"].is_file() for attempt in attempts)
        budget_status = self.teacher_client.invocation_budget_status()
        if budget_status is not None and budget_status["available"] < missing_proposals:
            raise ExecutionError(
                "skill-teacher round cannot start atomically within the frozen hard "
                "invocation budget: "
                f"round={round_index}; selected_groups={len(selected_group_map)}; "
                f"selected_clusters={len(attempts)}; "
                f"worst_case_new_calls={missing_proposals}; "
                f"available={budget_status['available']}; "
                f"reserved={budget_status['reserved']}; "
                f"hard_limit={budget_status['hard_limit']}"
            )
        calls = 0
        resumed_proposals = 0
        proposals: list[TeacherProposal] = []
        proposal_records: list[dict[str, Any]] = []
        for attempt in attempts:
            proposal_path = attempt["proposal_path"]
            batch_id = str(attempt["batch_id"])
            if proposal_path.is_file():
                proposal = self.store.load_model(proposal_path, TeacherProposal)
                if proposal.group_id != batch_id:
                    raise ExecutionError(
                        "persisted teacher batch proposal mismatch: "
                        f"expected={batch_id}; actual={proposal.group_id}"
                    )
                resumed_proposals += 1
            else:
                proposal = self.teacher.propose_batch(
                    batch_id=batch_id,
                    evidence_cluster_id=str(attempt["cluster"]["cluster_id"]),
                    contrasts=attempt["contrasts"],
                    evaluations=accumulated_evaluations,
                    existing_skills=existing,
                    runtime_skills=runtime_skills,
                    prior_validation_feedback=prior_validation_feedback,
                )
                calls += 1
                self.store.save_model(
                    proposal_path,
                    proposal,
                    overwrite=False,
                )
            proposals.append(proposal)
            candidate = proposal.usable_candidate
            staging_disposition = "no_usable_candidate"
            duplicate_of: str | None = None
            if candidate is not None:
                document_hash = skill_document_semantic_sha256(candidate)
                prior_document_for_id = round_candidate_documents.get(candidate.skill_id)
                prior_document_owner = round_document_owners.get(document_hash)
                if prior_document_for_id is not None:
                    if prior_document_for_id != document_hash:
                        raise ExecutionError(
                            "teacher reused a same-round skill_id for a different document: "
                            f"{candidate.skill_id}"
                        )
                    staging_disposition = "deduplicated_same_round_skill_id"
                    duplicate_of = candidate.skill_id
                elif prior_document_owner is not None:
                    staging_disposition = "deduplicated_same_round_document"
                    duplicate_of = prior_document_owner
                else:
                    round_candidate_documents[candidate.skill_id] = document_hash
                    round_document_owners[document_hash] = candidate.skill_id
                    destination = self.candidate_root / f"{candidate.skill_id}.yaml"
                    if destination.exists():
                        prior = load_skill(destination)
                        if canonical_json_sha256(
                            prior.model_dump(mode="json")
                        ) != canonical_json_sha256(candidate.model_dump(mode="json")):
                            raise ExecutionError(
                                "teacher reused a candidate skill_id for a different contract: "
                                f"{candidate.skill_id}"
                            )
                    else:
                        _atomic_yaml(destination, candidate)
                    candidate_paths.append(destination)
                    # A later teacher call in the same block must see and be
                    # checked against the document just staged.  Otherwise two
                    # sequential calls can emit near-identical sibling skills:
                    # they are not byte-identical, so the exact same-round hash
                    # guard alone would miss the duplication.
                    existing.append(candidate)
                    existing_by_id[candidate.skill_id] = candidate
                    staging_disposition = "staged_unique_candidate"
            proposal_records.append(
                {
                    "cluster_id": attempt["cluster"]["cluster_id"],
                    "evidence_fingerprint": attempt["fingerprint"],
                    "proposal_file": str(proposal_path.relative_to(self.root)),
                    "proposal_batch_id": batch_id,
                    "selected_group_ids": [
                        group.group_id for group, _ in attempt["selected_groups"]
                    ],
                    "parse_status": proposal.parse_status,
                    "source_group_ids": proposal.source_group_ids,
                    "candidate_skill_id": (candidate.skill_id if candidate is not None else None),
                    "staging_disposition": staging_disposition,
                    "duplicate_of_skill_id": duplicate_of,
                }
            )
        selected_groups = list(selected_group_map.values())
        self.store.write_manifest(
            f"teacher_round_{round_index:02d}",
            {
                "schema_version": 2,
                "round": round_index,
                "end_to_end_reward_informative_groups": sum(
                    group.informative for group, _ in groups
                ),
                "causal_evidence_groups": len(causal_selections),
                "groups_without_causal_evidence_reasons": dict(
                    sorted(
                        Counter(
                            group.skip_reason
                            for group, _ in groups
                            if group.group_id not in causal_selections and group.skip_reason
                        ).items()
                    )
                ),
                "selected_groups": len(selected_groups),
                "selected_case_ids": sorted(
                    {next(iter(mapped.values())).case_id for _, mapped in selected_groups}
                ),
                "selected_domains": sorted(
                    {next(iter(mapped.values())).domain for _, mapped in selected_groups}
                ),
                "selected_personas": sorted(
                    {next(iter(mapped.values())).persona for _, mapped in selected_groups}
                ),
                "teacher_update_unit": (
                    "distinct_cluster_syntheses_from_cumulative_causal_evidence"
                ),
                "pre_reward_attribution_scoreable_groups": len(scoreable_group_ids),
                "pre_reward_attribution_excluded_group_ids": list(
                    attribution_review.get("excluded_group_ids") or []
                ),
                "evidence_lifecycle": "causal_patch_to_candidate_to_validated_active_skill",
                "new_causal_evidence_patches": new_patch_count,
                "cumulative_causal_evidence_patches": len(accumulated_contrasts),
                "cumulative_evidence_rounds": sorted(evidence_rounds),
                "teacher_evidence_group_budget": evidence_budget,
                "teacher_evidence_clusters": evidence_clusters,
                "eligible_teacher_evidence_clusters": len(eligible_evidence_clusters),
                "attempted_evidence_cluster_ids": [
                    attempt["cluster"]["cluster_id"] for attempt in attempts
                ],
                "attempted_evidence_fingerprints": [attempt["fingerprint"] for attempt in attempts],
                # Singular fields retain readable compatibility with old manifests.
                "attempted_evidence_cluster_id": (
                    attempts[0]["cluster"]["cluster_id"] if attempts else None
                ),
                "attempted_evidence_fingerprint": (
                    attempts[0]["fingerprint"] if attempts else None
                ),
                "teacher_call_budget": call_budget,
                "configured_teacher_call_budget": configured_call_budget,
                "available_new_candidate_slots": candidate_budget,
                "teacher_calls": calls,
                "resumed_teacher_proposals": resumed_proposals,
                "teacher_budget_status_before_round": budget_status,
                "prior_validation_feedback": prior_validation_feedback,
                "prior_validation_feedback_count": len(prior_validation_feedback),
                "prior_validation_feedback_sha256": canonical_json_sha256(
                    prior_validation_feedback
                ),
                "teacher_proposal_parse_status": (
                    proposals[0].parse_status if proposals else "empty_feedback_noop"
                ),
                "teacher_proposal_records": proposal_records,
                "teacher_source_group_ids": sorted(
                    {group_id for proposal in proposals for group_id in proposal.source_group_ids}
                ),
                "candidate_files": [str(path.relative_to(self.root)) for path in candidate_paths],
            },
            overwrite=True,
        )
        return candidate_paths

    def _completed_validation_feedback_for_teacher(self, round_index: int) -> list[dict[str, Any]]:
        """Load only validation evidence already observable at this training round."""

        if not 1 <= round_index <= len(self.training_plan.batches):
            raise ExecutionError(f"invalid teacher round index: {round_index}")
        batch_positions = {
            batch.batch_id: index for index, batch in enumerate(self.training_plan.batches, start=1)
        }
        latest_by_skill: dict[str, tuple[int, Path, ProspectiveCandidateAudit]] = {}
        audit_root = self.store.root / "prospective_audits"
        for audit_path in sorted(audit_root.glob("*.json")):
            audit = self.store.load_model(audit_path, ProspectiveCandidateAudit)
            source_position = batch_positions.get(audit.source_batch_id)
            validation_position = batch_positions.get(audit.validation_batch_id)
            if source_position is None or validation_position is None:
                raise ExecutionError(
                    f"prospective audit references a batch outside the frozen plan: {audit_path}"
                )
            if validation_position != source_position + 1:
                raise ExecutionError(
                    f"prospective audit is not bound to the immediately next block: {audit_path}"
                )
            if validation_position > round_index:
                continue
            prior = latest_by_skill.get(audit.skill_id)
            if prior is None or validation_position > prior[0]:
                latest_by_skill[audit.skill_id] = (
                    validation_position,
                    audit_path,
                    audit,
                )
        feedback: list[dict[str, Any]] = []
        for _, audit_path, audit in latest_by_skill.values():
            item = prospective_audit_teacher_feedback(audit)
            item["audit_artifact_sha256"] = sha256_file(audit_path)
            feedback.append(item)
        feedback.sort(
            key=lambda item: (
                batch_positions[str(item["validation_batch_id"])],
                str(item["source_batch_id"]),
                str(item["skill_id"]),
            )
        )
        return feedback

    def _candidate_source_signal_family(self, candidate: SkillContract) -> SignalFamily:
        """Resolve one immutable F/G/stop provenance family for a teacher candidate."""

        matching: list[TeacherProposal] = []
        for proposal_path in sorted((self.store.root / "teacher").glob("round_*/*.json")):
            proposal = self.store.load_model(proposal_path, TeacherProposal)
            if _teacher_proposal_matches_candidate(proposal, candidate):
                matching.append(proposal)
        if len(matching) != 1:
            raise ExecutionError(
                "candidate must resolve to exactly one run-bound teacher proposal: "
                f"skill_id={candidate.skill_id}; proposals={len(matching)}"
            )
        source_group_ids = matching[0].source_group_ids
        if not source_group_ids:
            raise ExecutionError(
                f"candidate has no source-grounded contrast IDs: {candidate.skill_id}"
            )
        evidence_patches: dict[str, CausalEvidencePatch] = {}
        for patch_path in sorted(
            (self.store.root / "evidence" / "causal_contrasts").glob("*.json")
        ):
            patch = self.store.load_model(patch_path, CausalEvidencePatch)
            evidence_patches[patch.group.group_id] = patch
        missing = sorted(set(source_group_ids) - set(evidence_patches))
        if missing:
            raise ExecutionError(
                "candidate source contrast is absent from the immutable evidence bank: "
                f"skill_id={candidate.skill_id}; missing={missing}"
            )
        families = {
            evidence_patches[group_id].selection.signal_family for group_id in source_group_ids
        }
        if len(families) != 1:
            raise ExecutionError(
                "candidate source contrasts span mechanism families: "
                f"skill_id={candidate.skill_id}; families={sorted(families)}"
            )
        return cast(SignalFamily, next(iter(families)))

    def _prior_deferred_candidate_audit(
        self,
        *,
        skill_id: str,
        source_batch_id: str,
    ) -> tuple[Path, ProspectiveCandidateAudit] | None:
        """Resolve the immediately preceding cumulative audit for a carry-over.

        A provisional can occupy an arm in more than one *unseen* block, but the
        evidence chain must be contiguous.  Loading only the audit whose
        validation block is the current source block prevents accidental reuse of
        an older or already resolved candidate.
        """

        matches: list[tuple[Path, ProspectiveCandidateAudit]] = []
        for path in sorted((self.store.root / "prospective_audits").glob("*.json")):
            raw = json.loads(path.read_text(encoding="utf-8"))
            if raw.get("schema_version") != 5 or raw.get("skill_id") != skill_id:
                continue
            audit = ProspectiveCandidateAudit.model_validate(raw)
            if audit.validation_batch_id == source_batch_id:
                matches.append((path, audit))
        if not matches:
            return None
        if len(matches) != 1:
            raise ExecutionError(
                "deferred candidate has multiple audits for the same validation block: "
                f"skill_id={skill_id}; source_batch={source_batch_id}"
            )
        path, audit = matches[0]
        if audit.decision.decision != "DEFER":
            raise ExecutionError(
                "only a DEFER audit may stage a candidate into another unseen block: "
                f"skill_id={skill_id}; decision={audit.decision.decision}"
            )
        expected_chain = [
            batch.batch_id
            for batch in self.training_plan.batches
            if batch.batch_id in set(audit.validation_batch_ids)
        ]
        if audit.validation_batch_ids != expected_chain or not audit.validation_batch_ids:
            raise ExecutionError(f"deferred candidate validation chain is invalid: {skill_id}")
        if audit.validation_batch_ids[-1] != source_batch_id:
            raise ExecutionError(f"deferred candidate chain is not contiguous: {skill_id}")
        batch_positions = {
            batch.batch_id: index for index, batch in enumerate(self.training_plan.batches)
        }
        validation_positions = [
            batch_positions[batch_id] for batch_id in audit.validation_batch_ids
        ]
        source_position = batch_positions[source_batch_id]
        if validation_positions != list(
            range(validation_positions[0], source_position + 1)
        ):
            raise ExecutionError(f"deferred candidate chain is not contiguous: {skill_id}")
        return path, audit

    def validate_provisional_candidate(
        self,
        candidate_path: Path,
        *,
        source_round_index: int,
        validation_round_index: int,
        trajectories: list[ResearchTrajectory],
        evaluations: dict[str, TrajectoryEvaluation],
        baseline_skills: list[SkillContract],
        case_limit: int | None = None,
        activate_on_accept: bool = True,
        cohort_candidate_paths: list[Path] | None = None,
    ) -> ProspectiveCandidateAudit:
        candidate = load_skill(candidate_path)
        if not (
            1 <= source_round_index < validation_round_index <= len(self.training_plan.batches)
            and validation_round_index == source_round_index + 1
        ):
            raise ExecutionError("prospective validation must use the immediately next block")
        source_batch = self.training_plan.batches[source_round_index - 1]
        validation_batch = self.training_plan.batches[validation_round_index - 1]
        if validation_batch.prospective_validation_for != source_batch.batch_id:
            raise ExecutionError("batch plan does not bind this prospective predecessor")
        if candidate.status != "provisional":
            raise ExecutionError(
                f"next-block validation requires a provisional skill: {candidate.skill_id}"
            )
        declared_validation_case_ids = list(validation_batch.case_ids)
        if case_limit is not None:
            declared_validation_case_ids = declared_validation_case_ids[:case_limit]
        cohort_paths = sorted(cohort_candidate_paths or [candidate_path])
        cohort_candidates = [load_skill(path) for path in cohort_paths]
        if [item.skill_id for item in cohort_candidates].count(candidate.skill_id) != 1:
            raise ExecutionError(
                "candidate must appear exactly once in its embedded validation cohort: "
                f"{candidate.skill_id}"
            )
        candidate_assignments = self._embedded_candidate_assignments(
            cohort_candidates,
            declared_validation_case_ids,
            block_index=validation_round_index - 1,
            candidate_validation_ages=self._candidate_validation_ages(
                cohort_candidates,
                source_batch_id=source_batch.batch_id,
            ),
        )
        validation_case_ids = [
            case_id
            for case_id in declared_validation_case_ids
            if candidate.skill_id
            in {item.skill_id for item in candidate_assignments[case_id]}
        ]
        pair_seeds = [
            int(seed) for seed in self.experiment["trajectory_sampling"]["training_group_seeds"]
        ]
        audit_path = (
            self.store.root
            / "prospective_audits"
            / (
                f"{source_batch.batch_id}__on__{validation_batch.batch_id}__"
                f"{candidate.skill_id}.json"
            )
        )
        if audit_path.is_file():
            prior = self.store.load_model(audit_path, ProspectiveCandidateAudit)
            if (
                prior.source_batch_id != source_batch.batch_id
                or prior.validation_batch_id != validation_batch.batch_id
                or prior.validation_case_ids != validation_case_ids
                or prior.pair_seeds != pair_seeds
            ):
                raise ExecutionError("prospective audit matrix identity drift")
            if prior.decision.decision == "ACCEPT" and activate_on_accept:
                self._activate_accepted_skill(candidate, prior)
            return prior
        prior_deferred = self._prior_deferred_candidate_audit(
            skill_id=candidate.skill_id,
            source_batch_id=source_batch.batch_id,
        )
        prior_audit_path = prior_deferred[0] if prior_deferred is not None else None
        prior_audit = prior_deferred[1] if prior_deferred is not None else None
        validation_batch_ids = [
            *(prior_audit.validation_batch_ids if prior_audit is not None else []),
            validation_batch.batch_id,
        ]
        prior_audit_artifacts = [
            *(prior_audit.prior_audit_artifacts if prior_audit is not None else []),
            *(
                [self._relative_artifact_record(prior_audit_path)]
                if prior_audit_path is not None
                else []
            ),
        ]
        prior_outcomes = list(prior_audit.outcomes) if prior_audit is not None else []
        prior_baseline_trajectory_ids = (
            list(prior_audit.baseline_trajectory_ids) if prior_audit is not None else []
        )
        prior_candidate_trajectory_ids = (
            list(prior_audit.candidate_trajectory_ids) if prior_audit is not None else []
        )
        issues = validate_skill_static(candidate)
        if issues:
            raise ExecutionError(f"candidate static validation failed: {issues}")
        source_signal_family = self._candidate_source_signal_family(candidate)
        if any(item.skill_id == candidate.skill_id for item in baseline_skills):
            raise ExecutionError("provisional skill is already active before validation")
        enabled = candidate.model_copy(deep=True)
        enabled.status = "active"
        candidate_skills = [*baseline_skills, enabled]
        baseline_hash = skill_library_sha256(baseline_skills)
        candidate_hash = skill_library_sha256(candidate_skills)
        if not validation_case_ids:
            # A domain-scoped hypothesis may have no matching case in the
            # immediately following balanced block.  It must neither consume an
            # unrelated trajectory arm nor be mistaken for a negative efficacy
            # result.  Preserve its prior DEFER evidence and let the bounded
            # horizon resolve it explicitly.
            has_applicable_case = candidate.domain == "general" or any(
                self.main_adapter.case_domain(case_id) == candidate.domain
                for case_id in declared_validation_case_ids
            )
            defer_reason = (
                "candidate_assignment_capacity_unavailable_in_validation_block"
                if has_applicable_case
                else "no_applicable_domain_case_in_validation_block"
            )
            if prior_audit is not None:
                decision = prior_audit.decision.model_copy(
                    update={
                        "decision": "DEFER",
                        "reason": defer_reason,
                    }
                )
            else:
                decision = AuditDecision(
                    decision="DEFER",
                    reason=defer_reason,
                    pairs=0,
                    exposed_pairs=0,
                    exposed_cases=0,
                    exposed_domains=0,
                    mean_delta_reward=0.0,
                    median_delta_reward=0.0,
                    harmful_pair_rate=0.0,
                    severe_risk_count=0,
                    unsupported_claim_delta=0.0,
                    premature_final_delta=0.0,
                    belief_as_fact_delta=0.0,
                    repeated_question_delta=0.0,
                    critical_fact_recall_delta=0.0,
                    policy_fallback_delta=0.0,
                    client_fallback_delta=0.0,
                    memo_fallback_delta=0.0,
                )
            maximum_validation_blocks = int(
                self.experiment["prospective_validation"].get(
                    "maximum_validation_blocks", 3
                )
            )
            if (
                len(validation_batch_ids) >= maximum_validation_blocks
                or validation_round_index == len(self.training_plan.batches)
            ):
                decision = decision.model_copy(
                    update={
                        "decision": "REJECT",
                        "reason": (
                            "candidate_assignment_capacity_unavailable_within_"
                            "validation_horizon"
                            if has_applicable_case
                            else "no_applicable_domain_case_within_validation_horizon"
                        ),
                    }
                )
                rejected = candidate.model_copy(deep=True)
                rejected.status = "rejected"
                _atomic_yaml(
                    self.store.root / "skills" / "rejected" / f"{candidate.skill_id}.yaml",
                    rejected,
                )
            mechanism_gate = mechanism_direction_gate(prior_outcomes, source_signal_family)
            audit = ProspectiveCandidateAudit(
                skill_id=candidate.skill_id,
                source_batch_id=source_batch.batch_id,
                validation_batch_id=validation_batch.batch_id,
                validation_case_ids=[],
                validation_batch_ids=validation_batch_ids,
                prior_audit_artifacts=prior_audit_artifacts,
                pair_seeds=pair_seeds,
                decision=decision,
                paired_estimate=None,
                global_regression_passed=True,
                outcomes=prior_outcomes,
                current_outcomes=[],
                baseline_trajectory_ids=prior_baseline_trajectory_ids,
                candidate_trajectory_ids=prior_candidate_trajectory_ids,
                candidate_contract_health_passed=True,
                candidate_matrix_coverage_passed=None,
                candidate_health_report=None,
                candidate_health_counts={},
                source_signal_family=source_signal_family,
                mechanism_direction_gate=mechanism_gate,
                completed_at=datetime.now(UTC).isoformat(),
            )
            self.store.save_model(audit_path, audit, overwrite=True)
            return audit
        by_case_baseline = {
            item.case_id: item
            for item in trajectories
            if item.partition == validation_batch.batch_id
            # The block has one shared control for every case, while a sparse
            # candidate owns only its preassigned subset. Controls belonging
            # to another candidate are not members of this prospective matrix.
            and item.case_id in validation_case_ids
            and item.method == "candidate_without"
            and item.skill_library_version == baseline_hash
        }
        by_case_candidate = {
            item.case_id: item
            for item in trajectories
            if item.partition == validation_batch.batch_id
            and item.case_id in validation_case_ids
            and item.method == "candidate_with"
            and item.skill_library_version == candidate_hash
        }
        if set(by_case_baseline) != set(validation_case_ids):
            raise ExecutionError("embedded candidate evaluation lacks one shared control per case")
        if set(by_case_candidate) != set(validation_case_ids):
            raise ExecutionError(
                f"embedded candidate treatment matrix is incomplete: {candidate.skill_id}"
            )
        baseline_values = [by_case_baseline[case_id] for case_id in validation_case_ids]
        candidate_values = [by_case_candidate[case_id] for case_id in validation_case_ids]
        failed = [
            item.trajectory_id
            for item in [*baseline_values, *candidate_values]
            if item.status == "error"
        ]
        if failed:
            raise ExecutionError(f"candidate audit rollout failures: {failed[:5]}")
        evaluator_cases = {
            case_id: self.main_adapter.evaluator_case(case_id) for case_id in validation_case_ids
        }
        pair_health_reports = [
            {
                "case_id": case_id,
                "baseline_trajectory_id": by_case_baseline[case_id].trajectory_id,
                "candidate_trajectory_id": by_case_candidate[case_id].trajectory_id,
                "report": trajectory_health_report(
                    [by_case_baseline[case_id], by_case_candidate[case_id]],
                    {case_id: evaluator_cases[case_id]},
                    expected_run_id=self.store.run_id,
                ),
            }
            for case_id in validation_case_ids
        ]
        candidate_health = candidate_pair_health_selection(
            pair_health_reports,
            minimum_healthy_pair_fraction=float(
                self.experiment["prospective_validation"].get("minimum_healthy_pair_fraction", 0.75)
            ),
        )
        candidate_health_path = (
            self.store.root
            / "health"
            / (
                f"embedded_candidate_health_{source_batch.batch_id}_on_"
                f"{validation_batch.batch_id}_{candidate.skill_id}.json"
            )
        )
        self.store.atomic_json(candidate_health_path, candidate_health)
        if not candidate_health["candidate_wide_health_passed"]:
            exposed = [
                item
                for item in candidate_values
                if candidate.skill_id in item.exposed_skill_ids
            ]
            decision = AuditDecision(
                decision="REJECT",
                reason="candidate_pre_scoring_health_contract_failed",
                pairs=len(candidate_values),
                exposed_pairs=len(exposed),
                exposed_cases=len({item.case_id for item in exposed}),
                exposed_domains=len({item.domain for item in exposed}),
                mean_delta_reward=0.0,
                median_delta_reward=0.0,
                harmful_pair_rate=0.0,
                severe_risk_count=int(candidate_health["hard_treatment_issue_count"]),
                unsupported_claim_delta=0.0,
                premature_final_delta=0.0,
                belief_as_fact_delta=0.0,
                repeated_question_delta=0.0,
                critical_fact_recall_delta=0.0,
                policy_fallback_delta=0.0,
                client_fallback_delta=0.0,
                memo_fallback_delta=0.0,
            )
            candidate.status = "rejected"
            rejected_path = self.store.root / "skills" / "rejected" / f"{candidate.skill_id}.yaml"
            _atomic_yaml(rejected_path, candidate)
            audit = ProspectiveCandidateAudit(
                skill_id=candidate.skill_id,
                source_batch_id=source_batch.batch_id,
                validation_batch_id=validation_batch.batch_id,
                validation_case_ids=validation_case_ids,
                validation_batch_ids=validation_batch_ids,
                prior_audit_artifacts=prior_audit_artifacts,
                pair_seeds=pair_seeds,
                decision=decision,
                paired_estimate=None,
                global_regression_passed=False,
                outcomes=prior_outcomes,
                current_outcomes=[],
                baseline_trajectory_ids=[
                    *prior_baseline_trajectory_ids,
                    *(item.trajectory_id for item in baseline_values),
                ],
                candidate_trajectory_ids=[
                    *prior_candidate_trajectory_ids,
                    *(item.trajectory_id for item in candidate_values),
                ],
                candidate_contract_health_passed=False,
                candidate_matrix_coverage_passed=bool(
                    candidate_health["matrix_coverage_passed"]
                ),
                candidate_health_report=str(candidate_health_path.relative_to(self.root)),
                candidate_health_counts={
                    str(key): int(value) for key, value in candidate_health["counts"].items()
                },
                source_signal_family=source_signal_family,
                completed_at=datetime.now(UTC).isoformat(),
            )
            self.store.save_model(audit_path, audit, overwrite=True)
            return audit
        eligible_case_ids = set(candidate_health["eligible_case_ids"])
        baseline_values = [
            by_case_baseline[case_id]
            for case_id in validation_case_ids
            if case_id in eligible_case_ids
        ]
        candidate_values = [
            by_case_candidate[case_id]
            for case_id in validation_case_ids
            if case_id in eligible_case_ids
        ]
        acceptance = self.experiment["prospective_validation"]
        minimum_sessions, minimum_cases, minimum_domains = prospective_exposure_minima(
            candidate.domain,
            acceptance,
        )
        # Candidate health is an acceptance prerequisite, not a scoring result.
        # Check it before evaluating the control arm so an unhealthy treatment is
        # recorded as a deterministic rejection instead of surfacing as an
        # unrelated control-scoring exception.  The strict health contract is not
        # relaxed: no unhealthy treatment trajectory reaches semantic scoring.
        baseline_eval = {
            item.trajectory_id: evaluations[item.trajectory_id] for item in baseline_values
        }
        candidate_eval = {
            item.trajectory_id: evaluations[item.trajectory_id] for item in candidate_values
        }
        current_outcomes: list[PairOutcome] = []
        for without, with_skill in zip(baseline_values, candidate_values, strict=True):
            before = baseline_eval[without.trajectory_id]
            after = candidate_eval[with_skill.trajectory_id]
            exposed = candidate.skill_id in with_skill.exposed_skill_ids
            if not exposed:
                raise ExecutionError(
                    "assigned candidate treatment did not expose its skill document: "
                    f"{candidate.skill_id}:{with_skill.trajectory_id}"
                )
            control_questions = [
                str(step.rendered_question) for step in without.steps if step.rendered_question
            ]
            treatment_questions = [
                str(step.rendered_question) for step in with_skill.steps if step.rendered_question
            ]
            reconciled_scores, inherited_indices = monotone_expected_action_scores(
                control_questions,
                treatment_questions,
                before.rubric_judgment.expected_action_scores,
                after.rubric_judgment.expected_action_scores,
            )
            paired_reward = after.reward
            if inherited_indices:
                inquiry = (
                    sum(reconciled_scores) / len(reconciled_scores) if reconciled_scores else 0.0
                )
                paired_reward = trajectory_reward(
                    RewardComponents(
                        elicitation=balanced_elicitation(
                            after.training_metrics.substantive_fact_coverage,
                            inquiry,
                        ),
                        resolution=after.training_metrics.resolution,
                        fidelity=after.official_metrics.fidelity,
                        turns=len(treatment_questions),
                        repeated_question_rate=(after.safety_metrics.repeated_question_rate),
                        premature_final=(after.safety_metrics.premature_final_rate > 0),
                        unsupported_claim=(after.safety_metrics.unsupported_claim_rate > 0),
                        no_substantive_inquiry=bool(reconciled_scores and inquiry == 0),
                        hidden_field_leak=after.safety_metrics.hidden_field_leak,
                    ),
                    self.evaluator.reward_parameters,
                )
            current_outcomes.append(
                PairOutcome(
                    pair_id=without.group_id or without.trajectory_id,
                    case_id=without.case_id,
                    domain=without.domain,
                    exposed=True,
                    reward_without=before.reward.final_reward,
                    reward_with=paired_reward.final_reward,
                    raw_reward_with=after.reward.final_reward,
                    paired_inquiry_inherited_indices=inherited_indices,
                    severe_risk_with=(
                        after.safety_metrics.hidden_field_leak or with_skill.status == "error"
                    ),
                    unsupported_claim_delta=(
                        after.safety_metrics.unsupported_claim_rate
                        - before.safety_metrics.unsupported_claim_rate
                    ),
                    premature_final_delta=(
                        after.safety_metrics.premature_final_rate
                        - before.safety_metrics.premature_final_rate
                    ),
                    belief_as_fact_delta=(
                        after.safety_metrics.belief_as_fact_rate
                        - before.safety_metrics.belief_as_fact_rate
                    ),
                    repeated_question_delta=(
                        after.safety_metrics.repeated_question_rate
                        - before.safety_metrics.repeated_question_rate
                    ),
                    critical_fact_recall_delta=(
                        after.safety_metrics.critical_fact_recall
                        - before.safety_metrics.critical_fact_recall
                    ),
                    policy_fallback_delta=(
                        after.operational_metrics.policy_fallback_rate
                        - before.operational_metrics.policy_fallback_rate
                    ),
                    client_fallback_delta=(
                        after.operational_metrics.client_fallback_rate
                        - before.operational_metrics.client_fallback_rate
                    ),
                    memo_fallback_delta=(
                        float(after.operational_metrics.memo_fallback)
                        - float(before.operational_metrics.memo_fallback)
                    ),
                    newly_elicited_fact_delta=(
                        float(after.mechanism_signals.newly_elicited_fact_count)
                        - float(before.mechanism_signals.newly_elicited_fact_count)
                    ),
                    identified_evidence_gap_delta=(
                        float(after.mechanism_signals.identified_evidence_gap_count)
                        - float(before.mechanism_signals.identified_evidence_gap_count)
                    ),
                    question_turn_delta=(
                        float(len(treatment_questions)) - float(len(control_questions))
                    ),
                )
            )
        outcomes = [*prior_outcomes, *current_outcomes]
        outcome_ids = [item.pair_id for item in outcomes]
        if len(outcome_ids) != len(set(outcome_ids)):
            raise ExecutionError(
                f"cumulative prospective outcome identity collision: {candidate.skill_id}"
            )
        decision = decide_skill(
            outcomes,
            AcceptanceThresholds(
                minimum_exposed_pairs=minimum_sessions,
                minimum_exposed_cases=minimum_cases,
                minimum_exposed_domains=minimum_domains,
                minimum_mean_delta=float(acceptance["minimum_mean_delta"]),
                minimum_material_harm_delta=float(acceptance["minimum_material_harm_delta"]),
                maximum_harmful_pair_rate=float(acceptance["maximum_harmful_pair_rate"]),
            ),
        )
        mechanism_gate = mechanism_direction_gate(outcomes, source_signal_family)
        if decision.decision == "ACCEPT" and not mechanism_gate.passed:
            decision = decision.model_copy(
                update={
                    "decision": "REJECT",
                    "reason": "held_out_mechanism_direction_failed",
                }
            )
        if (
            decision.decision == "ACCEPT"
            and not candidate_health["matrix_coverage_passed"]
        ):
            # Quarantined pairs were removed before outcomes were read.  Too few
            # remaining pairs cannot prove efficacy, but neither can it prove a
            # sound candidate harmful.  Preserve valid observed outcomes and use
            # the bounded next-block horizon instead of a false negative.
            decision = decision.model_copy(
                update={
                    "decision": "DEFER",
                    "reason": "insufficient_healthy_pair_fraction_before_outcomes",
                }
            )
        exposed_by_case: dict[str, list[float]] = {}
        for item in outcomes:
            if item.exposed:
                exposed_by_case.setdefault(item.case_id, []).append(item.delta)
        exposed_deltas = [statistics.fmean(values) for values in exposed_by_case.values()]
        estimate = (
            paired_bootstrap_interval(
                exposed_deltas,
                samples=int(acceptance["bootstrap_samples"]),
                confidence_level=float(acceptance["confidence_level"]),
                seed=int(self.experiment["statistical_seed"]),
            )
            if exposed_deltas
            else None
        )
        if (
            decision.decision == "ACCEPT"
            and bool(acceptance["require_positive_confidence_lower"])
            and estimate is not None
            and estimate.lower <= 0
        ):
            decision = decision.model_copy(
                update={
                    "decision": "REJECT",
                    "reason": "case_cluster_confidence_interval_not_strictly_positive",
                }
            )
        global_pass = True
        if outcomes:
            baseline_mean = statistics.fmean(item.reward_without for item in outcomes)
            candidate_mean = statistics.fmean(item.reward_with for item in outcomes)
            global_pass = global_regression_passes(
                baseline_mean,
                candidate_mean,
                maximum_drop=float(acceptance["maximum_global_mean_reward_drop"]),
            )
        if decision.decision == "ACCEPT" and not global_pass:
            decision = decision.model_copy(
                update={"decision": "REJECT", "reason": "global_regression_gate_failed"}
            )
        maximum_validation_blocks = int(acceptance.get("maximum_validation_blocks", 3))
        if maximum_validation_blocks < 1:
            raise ExecutionError("maximum_validation_blocks must be at least one")
        if decision.decision == "DEFER" and (
            len(validation_batch_ids) >= maximum_validation_blocks
            or validation_round_index == len(self.training_plan.batches)
        ):
            decision = decision.model_copy(
                update={
                    "decision": "REJECT",
                    "reason": "insufficient_prospective_exposure_after_validation_horizon",
                }
            )
        candidate.evaluation.paired_cases = len({item.case_id for item in outcomes})
        candidate.evaluation.exposed_pairs = decision.exposed_pairs
        candidate.evaluation.exposed_cases = decision.exposed_cases
        candidate.evaluation.exposed_domains = decision.exposed_domains
        candidate.evaluation.mean_delta_reward = decision.mean_delta_reward
        candidate.evaluation.median_delta_reward = decision.median_delta_reward
        candidate.evaluation.harmful_pair_rate = decision.harmful_pair_rate
        candidate.evaluation.severe_risk_count = decision.severe_risk_count
        if decision.decision == "ACCEPT":
            candidate.status = "active"
            candidate.evaluation.accepted_at = datetime.now(UTC).isoformat()
        elif decision.decision == "REJECT":
            candidate.status = "rejected"
            rejected_path = self.store.root / "skills" / "rejected" / f"{candidate.skill_id}.yaml"
            _atomic_yaml(rejected_path, candidate)
        audit = ProspectiveCandidateAudit(
            skill_id=candidate.skill_id,
            source_batch_id=source_batch.batch_id,
            validation_batch_id=validation_batch.batch_id,
            validation_case_ids=validation_case_ids,
            validation_batch_ids=validation_batch_ids,
            prior_audit_artifacts=prior_audit_artifacts,
            pair_seeds=pair_seeds,
            decision=decision,
            paired_estimate=estimate,
            global_regression_passed=global_pass,
            outcomes=outcomes,
            current_outcomes=current_outcomes,
            baseline_trajectory_ids=[
                *prior_baseline_trajectory_ids,
                *(item.trajectory_id for item in baseline_values),
            ],
            candidate_trajectory_ids=[
                *prior_candidate_trajectory_ids,
                *(item.trajectory_id for item in candidate_values),
            ],
            candidate_contract_health_passed=True,
            candidate_matrix_coverage_passed=bool(
                candidate_health["matrix_coverage_passed"]
            ),
            candidate_health_report=str(candidate_health_path.relative_to(self.root)),
            candidate_health_counts={
                str(key): int(value) for key, value in candidate_health["counts"].items()
            },
            source_signal_family=source_signal_family,
            mechanism_direction_gate=mechanism_gate,
            completed_at=datetime.now(UTC).isoformat(),
        )
        self.store.save_model(audit_path, audit, overwrite=True)
        if decision.decision == "ACCEPT" and activate_on_accept:
            self._activate_accepted_skill(candidate, audit)
        return audit

    def write_learning_checkpoint(
        self,
        *,
        round_index: int,
        case_limit: int | None,
        run_manifest_sha256: str,
        accepted_skill_ids: list[str],
        input_skills: list[SkillContract],
        development_curve_artifact: dict[str, str],
    ) -> dict[str, Any]:
        """Bind the measured input library to the post-block library transition."""

        batch_id = self.training_plan.batches[round_index - 1].batch_id
        input_ids = sorted(item.skill_id for item in input_skills)
        input_hash = skill_library_sha256(input_skills)
        curve_point = self._validate_learning_curve_point_artifact(
            round_index=round_index,
            case_limit=case_limit,
            run_manifest_sha256=run_manifest_sha256,
            expected_input_skill_ids=input_ids,
            expected_input_skill_library_sha256=input_hash,
            artifact_record=development_curve_artifact,
        )
        active = self.active_skills()
        report_path = self.store.root / "reports" / f"learning_checkpoint_{round_index:02d}.json"
        value = {
            "schema_version": 2,
            "run_id": self.run_id,
            "checkpoint": round_index,
            "batch_id": batch_id,
            "status": "measured_prequential_learning_checkpoint",
            "accepted_from_preceding_block": sorted(accepted_skill_ids),
            "measured_input_active_skill_ids": input_ids,
            "measured_input_skill_library_sha256": input_hash,
            "development_curve_artifact": development_curve_artifact,
            "active_skill_ids": sorted(item.skill_id for item in active),
            "active_skill_library_sha256": skill_library_sha256(active),
            "evidence_role": self.experiment["learning_curve"]["evidence_role"],
            "curve_identity_baseline": curve_point["identity_baseline"],
            "completed_at": datetime.now(UTC).isoformat(),
        }
        if report_path.is_file():
            prior = json.loads(report_path.read_text(encoding="utf-8"))
            comparable = {key: item for key, item in value.items() if key != "completed_at"}
            prior_comparable = {key: item for key, item in prior.items() if key != "completed_at"}
            if prior_comparable != comparable:
                raise ExecutionError("learning checkpoint differs from resumed state")
            return prior
        self.store.atomic_json(report_path, value)
        return value

    def write_development_learning_curve_summary(self) -> dict[str, Any]:
        """Materialize a plot-ready view from immutable per-block curve points."""

        points: list[dict[str, Any]] = []
        series: dict[str, list[dict[str, Any]]] = {}
        for round_index, batch in enumerate(self.training_plan.batches, start=1):
            checkpoint_path = (
                self.store.root / "reports" / f"learning_checkpoint_{round_index:02d}.json"
            )
            point_path = self._learning_curve_point_path(round_index)
            if not checkpoint_path.is_file() or not point_path.is_file():
                continue
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            point = json.loads(point_path.read_text(encoding="utf-8"))
            if (
                checkpoint.get("schema_version") != 2
                or checkpoint.get("batch_id") != batch.batch_id
                or checkpoint.get("development_curve_artifact")
                != self._relative_artifact_record(point_path)
            ):
                raise ExecutionError(
                    f"development learning-curve checkpoint drift: {batch.batch_id}"
                )
            curve = point["curve"]
            point_record = {
                "round": round_index,
                "batch_id": batch.batch_id,
                "input_active_skill_ids": point["input_active_skill_ids"],
                "input_skill_library_sha256": point["input_skill_library_sha256"],
                "output_active_skill_ids": checkpoint["active_skill_ids"],
                "output_skill_library_sha256": checkpoint[
                    "active_skill_library_sha256"
                ],
                "accepted_from_preceding_block": checkpoint[
                    "accepted_from_preceding_block"
                ],
                "identity_baseline": point["identity_baseline"],
                "pair_count": curve["pair_count"],
                "case_cluster_count": curve["case_cluster_count"],
                "artifact": self._relative_artifact_record(point_path),
            }
            points.append(point_record)
            for metric_name, metric in curve["metrics"].items():
                series.setdefault(metric_name, []).append(
                    {
                        "round": round_index,
                        "batch_id": batch.batch_id,
                        "empty_library_mean": metric["empty_library_mean"],
                        "current_library_mean": metric["current_library_mean"],
                        "mean_delta": metric["case_cluster_estimate"]["mean_delta"],
                        "confidence_lower": metric["case_cluster_estimate"]["lower"],
                        "confidence_upper": metric["case_cluster_estimate"]["upper"],
                    }
                )
        value = {
            "schema_version": 1,
            "run_id": self.run_id,
            "status": (
                "complete"
                if len(points) == len(self.training_plan.batches)
                else "partial"
            ),
            "evidence_role": self.experiment["learning_curve"]["evidence_role"],
            "expected_points": len(self.training_plan.batches),
            "completed_points": len(points),
            "direction": "current_input_library_minus_empty_library",
            "points": points,
            "series": series,
            "updated_at": datetime.now(UTC).isoformat(),
        }
        self.store.atomic_json(
            self.store.root / "reports" / "development_learning_curve.json",
            value,
        )
        return value

    def revalidate_candidate_source_grounding(
        self,
        *,
        round_index: int,
        candidates: list[Path],
        carryover_candidates: list[Path] | None = None,
    ) -> list[Path]:
        """Fail closed for candidates produced before or after the grounding gate.

        A resumed run may contain teacher artifacts created by an older implementation.
        Replaying their declared failure state here prevents resume semantics from
        bypassing the same source-grounding contract applied to new proposals.
        """

        evidence_patches: dict[str, CausalEvidencePatch] = {}
        for patch_path in sorted(
            (self.store.root / "evidence" / "causal_contrasts").glob("*.json")
        ):
            patch = self.store.load_model(patch_path, CausalEvidencePatch)
            if patch.group.group_id in evidence_patches:
                raise ExecutionError(f"duplicate cumulative evidence group: {patch.group.group_id}")
            evidence_patches[patch.group.group_id] = patch
        proposal_entries: dict[str, list[tuple[Path, TeacherProposal]]] = {}
        proposal_root = self.store.root / "teacher" / f"round_{round_index:02d}"
        for proposal_path in sorted(proposal_root.glob("*.json")):
            proposal = self.store.load_model(proposal_path, TeacherProposal)
            candidate = proposal.diagnosis.candidate_skill
            if candidate is not None:
                proposal_entries.setdefault(candidate.skill_id, []).append(
                    (proposal_path, proposal)
                )

        raw_carryovers = sorted(carryover_candidates or [])
        raw_candidates = sorted(candidates)
        all_candidates, deduplicated = self._deduplicate_candidate_paths(
            [*raw_carryovers, *raw_candidates]
        )
        carryovers = [path for path in all_candidates if path in set(raw_carryovers)]
        new_candidates = [path for path in all_candidates if path not in set(raw_carryovers)]
        for record in deduplicated:
            duplicate_path = Path(record["candidate_path"])
            canonical_path = Path(record["canonical_path"])
            if duplicate_path != canonical_path and duplicate_path in raw_candidates:
                duplicate = load_skill(duplicate_path)
                duplicate.status = "rejected"
                _atomic_yaml(duplicate_path, duplicate)
        deduplication_records = [
            {
                "candidate_file": str(Path(record["candidate_path"]).relative_to(self.root)),
                "canonical_file": str(Path(record["canonical_path"]).relative_to(self.root)),
                "canonical_skill_id": record["canonical_skill_id"],
                "reason": record["reason"],
            }
            for record in deduplicated
        ]
        candidate_budget = int(
            self.experiment["execution"].get(
                "maximum_concurrent_provisional_candidates", 6
            )
        )
        if len(all_candidates) > candidate_budget:
            raise ExecutionError("staged candidates exceed the declared next-block budget")
        active_capacity_baseline = self.active_skills()
        active_capacity_issues = skill_memory_capacity_issues(active_capacity_baseline)
        if active_capacity_issues:
            raise ExecutionError(
                "active skill library violates the frozen prompt-memory capacity before "
                f"candidate staging: {active_capacity_issues}"
            )

        proposals: dict[str, TeacherProposal] = {}
        proposal_paths: dict[str, Path] = {}
        for candidate_path in new_candidates:
            candidate = load_skill(candidate_path)
            entries = proposal_entries.get(candidate.skill_id, [])
            matching = [
                (path, proposal)
                for path, proposal in entries
                if _teacher_proposal_matches_candidate(proposal, candidate)
            ]
            if len(matching) != 1:
                raise ExecutionError(
                    "candidate must resolve to one same-round teacher proposal by source "
                    f"cluster: skill_id={candidate.skill_id}; matches={len(matching)}"
                )
            proposal_paths[candidate.skill_id], proposals[candidate.skill_id] = matching[0]

        valid: list[Path] = []
        records: list[dict[str, Any]] = []
        # Candidate order is not semantic.  Persist one canonical ordering so a
        # multi-candidate teacher round and the path-sorted checkpoint bind the
        # same artifact membership.
        for candidate_path in all_candidates:
            candidate = load_skill(candidate_path)
            if candidate_path in set(carryovers):
                prior = self._prior_deferred_candidate_audit(
                    skill_id=candidate.skill_id,
                    source_batch_id=self.training_plan.batches[round_index - 1].batch_id,
                )
                issues = validate_skill_static(candidate)
                if candidate.status != "provisional":
                    issues.append("deferred_candidate_is_not_provisional")
                if prior is None:
                    issues.append("deferred_candidate_audit_missing")
                if issues:
                    raise ExecutionError(
                        "deferred candidate cannot be carried into the next unseen block: "
                        f"skill_id={candidate.skill_id}; issues={sorted(set(issues))}"
                    )
                valid.append(candidate_path)
                records.append(
                    {
                        "skill_id": candidate.skill_id,
                        "candidate_file": str(candidate_path.relative_to(self.root)),
                        "candidate_sha256": sha256_file(candidate_path),
                        "candidate_contract_sha256": skill_contract_definition_sha256(candidate),
                        "teacher_proposal_file": None,
                        "lifecycle": "deferred_from_prior_unseen_block",
                        "prior_audit_file": str(prior[0].relative_to(self.root)),
                        "prior_audit_sha256": sha256_file(prior[0]),
                        "valid": True,
                        "issues": [],
                    }
                )
                continue
            proposal = proposals.get(candidate.skill_id)
            issues: list[str]
            if proposal is None:
                issues = ["source_grounding_teacher_proposal_missing"]
            else:
                source_group_ids = proposal.source_group_ids or [proposal.group_id]
                contrast_contexts: list[
                    tuple[
                        AdvantageGroup,
                        ContrastSelection,
                        dict[str, ResearchTrajectory],
                    ]
                ] = []
                construction_issues: list[str] = []
                for source_group_id in source_group_ids:
                    patch = evidence_patches.get(source_group_id)
                    if patch is None:
                        construction_issues.append(
                            f"source_grounding_evidence_patch_missing:{source_group_id}"
                        )
                        continue
                    group_members: dict[str, ResearchTrajectory] = {}
                    for trajectory_id in patch.trajectory_ids:
                        trajectory_path = self.store.trajectory_path(patch.partition, trajectory_id)
                        evaluation_path = self.store.evaluation_path(trajectory_id)
                        if sha256_file(trajectory_path) != patch.trajectory_sha256[trajectory_id]:
                            construction_issues.append(
                                f"source_grounding_trajectory_drift:{trajectory_id}"
                            )
                            continue
                        if sha256_file(evaluation_path) != patch.evaluation_sha256[trajectory_id]:
                            construction_issues.append(
                                f"source_grounding_evaluation_drift:{trajectory_id}"
                            )
                            continue
                        group_members[trajectory_id] = self.store.load_model(
                            trajectory_path, ResearchTrajectory
                        )
                    if len(group_members) != len(patch.trajectory_ids):
                        continue
                    contrast_contexts.append((patch.group, patch.selection, group_members))
                if construction_issues:
                    issues = construction_issues
                elif len(source_group_ids) > 1:
                    issues, _ = candidate_batch_source_grounding_issues(
                        proposal.diagnosis,
                        contrast_contexts,
                        existing_skills=active_capacity_baseline,
                    )
                else:
                    group, selection, group_members = contrast_contexts[0]
                    issues = candidate_source_grounding_issues(
                        proposal.diagnosis,
                        selection,
                        group_members,
                        existing_skills=active_capacity_baseline,
                    )
            if not issues:
                candidate.status = "provisional"
                _atomic_yaml(candidate_path, candidate)
                valid.append(candidate_path)
            else:
                candidate.status = "rejected"
                _atomic_yaml(candidate_path, candidate)
            records.append(
                {
                    "skill_id": candidate.skill_id,
                    "candidate_file": str(candidate_path.relative_to(self.root)),
                    "candidate_sha256": sha256_file(candidate_path),
                    "candidate_contract_sha256": skill_contract_definition_sha256(candidate),
                    "teacher_proposal_file": (
                        str(proposal_paths[candidate.skill_id].relative_to(self.root))
                        if candidate.skill_id in proposal_paths
                        else None
                    ),
                    "lifecycle": "new_teacher_candidate",
                    "valid": not issues,
                    "issues": sorted(set(issues)),
                }
            )

        # Static/source-valid candidates must also fit *together* with the exact
        # input library before any of them consumes next-block GPU trajectories.
        # Carryovers precede new candidates; within each class the path order is
        # frozen above.  This order is independent of prospective outcomes.
        enabled_for_capacity: list[SkillContract] = []
        path_by_id: dict[str, Path] = {}
        for candidate_path in valid:
            candidate = load_skill(candidate_path)
            enabled = candidate.model_copy(deep=True)
            enabled.status = "active"
            enabled_for_capacity.append(enabled)
            path_by_id[enabled.skill_id] = candidate_path
        capacity_admitted, capacity_rejected = admit_active_skills_by_prompt_capacity(
            active_capacity_baseline,
            enabled_for_capacity,
        )
        admitted_ids = {candidate.skill_id for candidate in capacity_admitted}
        if capacity_rejected:
            record_by_id = {str(record["skill_id"]): record for record in records}
            for skill_id, capacity_issues in capacity_rejected.items():
                candidate_path = path_by_id[skill_id]
                candidate = load_skill(candidate_path)
                candidate.status = "rejected"
                _atomic_yaml(candidate_path, candidate)
                record = record_by_id[skill_id]
                record["valid"] = False
                record["lifecycle"] = f"{record['lifecycle']}_prompt_capacity_rejected"
                record["issues"] = [
                    *record.get("issues", []),
                    *(f"cohort_{issue}" for issue in capacity_issues),
                ]
                record["candidate_sha256"] = sha256_file(candidate_path)
                record["candidate_contract_sha256"] = skill_contract_definition_sha256(
                    candidate
                )
            valid = [
                candidate_path
                for candidate_path in valid
                if load_skill(candidate_path).skill_id in admitted_ids
            ]
        report_path = (
            self.store.root / "reports" / f"candidate_source_grounding_round_{round_index:02d}.json"
        )
        self.store.atomic_json(
            report_path,
            {
                "schema_version": 4,
                "run_id": self.run_id,
                "round": round_index,
                "status": "provisional_candidates_staged_after_source_grounding",
                "records": records,
                "deferred_candidate_files": [
                    str(path.relative_to(self.root)) for path in carryovers if path in valid
                ],
                "new_candidate_files": [
                    str(path.relative_to(self.root)) for path in new_candidates
                ],
                "deduplicated_candidates": deduplication_records,
                "prompt_capacity_admission_order": [
                    candidate.skill_id for candidate in enabled_for_capacity
                ],
                "prompt_capacity_rejections": capacity_rejected,
                "valid_candidate_files": [str(path.relative_to(self.root)) for path in valid],
                "invalid_candidate_files": [
                    *(
                        record["candidate_file"]
                        for record in records
                        if not record["valid"]
                    ),
                    *(
                        record["candidate_file"]
                        for record in deduplication_records
                        if record["candidate_file"] != record["canonical_file"]
                    ),
                ],
                "grounding_implementation_sha256": sha256_file(
                    self.root / "legal_skill_guard/evolution/teacher.py"
                ),
                "teacher_prompt_sha256": sha256_file(
                    self.root / "configs/prompts/skill_teacher_zh.txt"
                ),
                "completed_at": datetime.now(UTC).isoformat(),
            },
        )
        return valid

    @staticmethod
    def _trajectory_protocol_version() -> int:
        return int(ResearchTrajectory.model_fields["schema_version"].default)

    @staticmethod
    def _evaluation_protocol_version() -> int:
        return int(TrajectoryEvaluation.model_fields["schema_version"].default)

    @staticmethod
    def _round_manifest_names(batch_id: str) -> tuple[str, str]:
        return (f"{batch_id}__provisionals_ready", f"{batch_id}__complete")

    def _verified_run_manifest_sha256(self) -> str:
        self.verify_run_manifest()
        path = self.store.root / "manifests" / "run.json"
        if not path.is_file():
            raise ExecutionError("verified run manifest file is missing")
        return sha256_file(path)

    def _preceding_provisional_paths(
        self,
        *,
        round_index: int,
        case_limit: int | None,
        run_manifest_sha256: str,
    ) -> list[Path]:
        """Load candidates produced by the immediately preceding block.

        These candidates are consumed by the current block's normal K group;
        this function performs no rollout and creates no validation partition.
        """

        if round_index == 1:
            return []
        source_round = round_index - 1
        source_batch = self.training_plan.batches[source_round - 1]
        current_batch = self.training_plan.batches[round_index - 1]
        if current_batch.prospective_validation_for != source_batch.batch_id:
            raise ExecutionError("current block is not bound to its immediate predecessor")
        provisional_name, _ = self._round_manifest_names(source_batch.batch_id)
        raw = self.store.read_manifest(provisional_name)
        _, paths = self._validate_provisionals_ready_checkpoint(
            round_index=source_round,
            case_limit=case_limit,
            run_manifest_sha256=run_manifest_sha256,
            expected_input_skill_ids=list(raw["input_active_skill_ids"]),
            expected_input_skill_library_sha256=str(raw["input_skill_library_sha256"]),
        )
        fresh_budget = int(
            self.experiment["execution"].get("provisional_candidate_budget_per_block", 2)
        )
        budget = int(
            self.experiment["execution"].get(
                "maximum_concurrent_provisional_candidates", fresh_budget * 3
            )
        )
        if len(paths) > budget:
            raise ExecutionError("preceding candidate count exceeds the declared block budget")
        return paths

    def _training_round_expected_matrix(
        self,
        round_index: int,
        *,
        case_limit: int | None,
        input_skill_library_sha256: str,
        preceding_candidates: list[Path] | None = None,
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
            raise ExecutionError("embedded training input skill library hash mismatch")
        candidate_skills = [load_skill(path) for path in sorted(preceding_candidates or [])]
        candidate_ages = (
            self._candidate_validation_ages(
                candidate_skills,
                source_batch_id=self.training_plan.batches[round_index - 2].batch_id,
            )
            if candidate_skills and round_index > 1
            else {candidate.skill_id: 0 for candidate in candidate_skills}
        )
        candidate_assignments = self._embedded_candidate_assignments(
            candidate_skills,
            case_ids,
            block_index=round_index - 1,
            candidate_validation_ages=candidate_ages,
        )
        for case_id in case_ids:
            persona_id = declared_batch.persona_assignment[case_id]
            case_arm_specs = self._embedded_case_arm_specs(
                active_skills=active_skills,
                active_hash=input_skill_library_sha256,
                assigned_candidates=candidate_assignments[case_id],
                group_size=group_size,
            )
            for seed_value in self.experiment["trajectory_sampling"]["training_group_seeds"]:
                seed = int(seed_value)
                group_id = f"{declared_batch.batch_id}.{case_id}.{persona_id}.seed_{seed}"
                for sample_index, (method, _, skill_hash) in enumerate(case_arm_specs):
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

    def _candidate_ready_records(self, candidates: list[Path]) -> list[dict[str, str]]:
        records: list[dict[str, str]] = []
        for candidate_path in sorted(candidates):
            candidate = load_skill(candidate_path)
            artifact = self._relative_artifact_record(candidate_path)
            records.append(
                {
                    **artifact,
                    "skill_id": candidate.skill_id,
                    "contract_sha256": skill_contract_definition_sha256(candidate),
                }
            )
        return records

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

    def _validate_candidate_records(
        self,
        records: object,
    ) -> list[Path]:
        if not isinstance(records, list):
            raise ExecutionError("round checkpoint provisional_artifacts must be a list")
        paths: list[Path] = []
        seen_ids: set[str] = set()
        seen_documents: dict[str, str] = {}
        for record in records:
            expected_fields = {"path", "sha256", "skill_id", "contract_sha256"}
            if not isinstance(record, dict) or set(record) != expected_fields:
                raise ExecutionError("invalid candidate artifact binding")
            relative = record.get("path")
            skill_id = record.get("skill_id")
            expected_contract = record.get("contract_sha256")
            expected_file_hash = record.get("sha256")
            if not all(
                isinstance(item, str)
                for item in (relative, skill_id, expected_contract, expected_file_hash)
            ):
                raise ExecutionError("invalid candidate artifact binding values")
            candidate_path = self.root / str(relative)
            expected_candidate_path = self.candidate_root / f"{skill_id}.yaml"
            if candidate_path.resolve() != expected_candidate_path.resolve():
                raise ExecutionError(f"candidate artifact path mismatch: {relative}")
            if not candidate_path.is_file():
                raise ExecutionError(f"candidate artifact is missing: {relative}")
            candidate = load_skill(candidate_path)
            if candidate.skill_id != skill_id:
                raise ExecutionError(f"candidate skill_id drift: {relative}")
            if skill_contract_definition_sha256(candidate) != expected_contract:
                raise ExecutionError(f"candidate prompt-document contract drift: {relative}")
            if sha256_file(candidate_path) != expected_file_hash:
                raise ExecutionError(f"provisional candidate bytes changed: {relative}")
            if candidate.status != "provisional":
                raise ExecutionError(f"checkpoint skill is not provisional: {relative}")
            if skill_id in seen_ids:
                raise ExecutionError(f"duplicate candidate in round checkpoint: {skill_id}")
            document_hash = skill_document_semantic_sha256(candidate)
            if document_hash in seen_documents:
                raise ExecutionError(
                    "duplicate prompt document in round checkpoint: "
                    f"{skill_id}; canonical={seen_documents[document_hash]}"
                )
            seen_ids.add(str(skill_id))
            seen_documents[document_hash] = str(skill_id)
            paths.append(candidate_path)
        return paths

    def _write_provisionals_ready_checkpoint(
        self,
        *,
        round_index: int,
        case_limit: int | None,
        run_manifest_sha256: str,
        input_skills: list[SkillContract],
        trajectories: list[ResearchTrajectory],
        candidates: list[Path],
        development_curve_artifact: dict[str, str],
        preceding_candidates: list[Path] | None = None,
    ) -> dict[str, Any]:
        batch_id = self.training_plan.batches[round_index - 1].batch_id
        input_hash = skill_library_sha256(input_skills)
        expected_matrix = self._training_round_expected_matrix(
            round_index,
            case_limit=case_limit,
            input_skill_library_sha256=input_hash,
            preceding_candidates=preceding_candidates,
            input_skills=input_skills,
        )
        actual_by_id = {item.trajectory_id: item for item in trajectories}
        if len(actual_by_id) != len(trajectories):
            raise ExecutionError("training round returned duplicate trajectory IDs")
        expected_by_id = {item["trajectory_id"]: item for item in expected_matrix}
        if set(actual_by_id) != set(expected_by_id):
            raise ExecutionError("training round output differs from the frozen matrix")
        for trajectory_id, expected in expected_by_id.items():
            trajectory = actual_by_id[trajectory_id]
            drift = [
                field
                for field, expected_value in expected.items()
                if getattr(trajectory, field) != expected_value
            ]
            if trajectory.schema_version != self._trajectory_protocol_version():
                drift.append("schema_version")
            if drift:
                raise ExecutionError(
                    "training trajectory identity drift before checkpoint: "
                    f"{trajectory_id}; fields={sorted(set(drift))}"
                )
        trajectory_artifacts = {
            trajectory_id: self._relative_artifact_record(
                self.store.trajectory_path(batch_id, trajectory_id)
            )
            for trajectory_id in expected_by_id
        }
        evaluation_artifacts = {
            trajectory_id: self._relative_artifact_record(self.store.evaluation_path(trajectory_id))
            for trajectory_id in expected_by_id
        }
        health_path = self.store.root / "health" / f"pre_scoring_health_{batch_id}.json"
        provisional_name, _ = self._round_manifest_names(batch_id)
        self.store.write_manifest(
            provisional_name,
            {
                "schema_version": 4,
                "run_id": self.run_id,
                "run_manifest_sha256": run_manifest_sha256,
                "round": round_index,
                "batch_id": batch_id,
                "stage": "provisionals_ready",
                "case_limit": case_limit,
                "trajectory_schema_version": self._trajectory_protocol_version(),
                "evaluation_schema_version": self._evaluation_protocol_version(),
                "judge_qualification_contract_sha256": (self.judge_qualification_contract_sha256),
                "input_active_skill_ids": sorted(item.skill_id for item in input_skills),
                "input_skill_library_sha256": input_hash,
                "expected_matrix": expected_matrix,
                "expected_matrix_sha256": canonical_json_sha256(expected_matrix),
                "trajectory_artifacts": trajectory_artifacts,
                "evaluation_artifacts": evaluation_artifacts,
                "pre_scoring_health_artifact": self._relative_artifact_record(health_path),
                "development_curve_artifact": development_curve_artifact,
                "provisional_artifacts": self._candidate_ready_records(candidates),
            },
            overwrite=False,
        )
        return self._validate_provisionals_ready_checkpoint(
            round_index=round_index,
            case_limit=case_limit,
            run_manifest_sha256=run_manifest_sha256,
            expected_input_skill_ids=sorted(item.skill_id for item in input_skills),
            expected_input_skill_library_sha256=input_hash,
        )[0]

    def _validate_provisionals_ready_checkpoint(
        self,
        *,
        round_index: int,
        case_limit: int | None,
        run_manifest_sha256: str,
        expected_input_skill_ids: list[str],
        expected_input_skill_library_sha256: str,
    ) -> tuple[dict[str, Any], list[Path]]:
        batch_id = self.training_plan.batches[round_index - 1].batch_id
        provisional_name, _ = self._round_manifest_names(batch_id)
        try:
            checkpoint = self.store.read_manifest(provisional_name)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise ExecutionError(
                f"invalid provisionals-ready manifest envelope: {batch_id}"
            ) from exc
        if checkpoint.get("schema_version") != 4:
            raise ExecutionError(f"legacy candidates-ready checkpoint is not resumable: {batch_id}")
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
        if set(checkpoint) != expected_fields:
            raise ExecutionError(f"round candidates-ready manifest fields drifted: {batch_id}")
        bindings = {
            "schema_version": 4,
            "run_id": self.run_id,
            "run_manifest_sha256": run_manifest_sha256,
            "round": round_index,
            "batch_id": batch_id,
            "stage": "provisionals_ready",
            "case_limit": case_limit,
            "trajectory_schema_version": self._trajectory_protocol_version(),
            "evaluation_schema_version": self._evaluation_protocol_version(),
            "judge_qualification_contract_sha256": (self.judge_qualification_contract_sha256),
            "input_active_skill_ids": expected_input_skill_ids,
            "input_skill_library_sha256": expected_input_skill_library_sha256,
        }
        mismatches = [
            field for field, expected in bindings.items() if checkpoint.get(field) != expected
        ]
        if mismatches:
            raise ExecutionError(
                f"round candidates-ready binding mismatch: batch={batch_id}; fields={mismatches}"
            )
        active_by_id = {item.skill_id: item for item in self.active_skills()}
        if not set(expected_input_skill_ids) <= set(active_by_id):
            raise ExecutionError("checkpoint input skill library is unavailable")
        checkpoint_input_skills = [active_by_id[item] for item in expected_input_skill_ids]
        expected_matrix = self._training_round_expected_matrix(
            round_index,
            case_limit=case_limit,
            input_skill_library_sha256=expected_input_skill_library_sha256,
            preceding_candidates=self._preceding_provisional_paths(
                round_index=round_index,
                case_limit=case_limit,
                run_manifest_sha256=run_manifest_sha256,
            ),
            input_skills=checkpoint_input_skills,
        )
        if checkpoint.get("expected_matrix") != expected_matrix or checkpoint.get(
            "expected_matrix_sha256"
        ) != canonical_json_sha256(expected_matrix):
            raise ExecutionError(f"round expected trajectory matrix drift: {batch_id}")
        expected_by_id = {item["trajectory_id"]: item for item in expected_matrix}
        trajectory_artifacts = checkpoint.get("trajectory_artifacts")
        evaluation_artifacts = checkpoint.get("evaluation_artifacts")
        if not isinstance(trajectory_artifacts, dict) or set(trajectory_artifacts) != set(
            expected_by_id
        ):
            raise ExecutionError(f"round trajectory artifact set is incomplete: {batch_id}")
        if not isinstance(evaluation_artifacts, dict) or set(evaluation_artifacts) != set(
            expected_by_id
        ):
            raise ExecutionError(f"round evaluation artifact set is incomplete: {batch_id}")
        expected_trajectory_paths: set[Path] = set()
        for trajectory_id, expected in expected_by_id.items():
            trajectory_path = self.store.trajectory_path(batch_id, trajectory_id)
            expected_trajectory_paths.add(trajectory_path.resolve())
            self._verify_artifact_record(
                trajectory_artifacts[trajectory_id],
                expected_path=trajectory_path,
                label=f"trajectory {trajectory_id}",
            )
            try:
                trajectory = self.store.load_model(trajectory_path, ResearchTrajectory)
            except Exception as exc:
                raise ExecutionError(
                    f"trajectory is not current protocol {self._trajectory_protocol_version()}: "
                    f"{trajectory_id}"
                ) from exc
            drift = [
                field
                for field, expected_value in expected.items()
                if getattr(trajectory, field) != expected_value
            ]
            if trajectory.schema_version != self._trajectory_protocol_version():
                drift.append("schema_version")
            if drift:
                raise ExecutionError(
                    f"round trajectory identity drift: {trajectory_id}; fields={drift}"
                )
            evaluation_path = self.store.evaluation_path(trajectory_id)
            self._verify_artifact_record(
                evaluation_artifacts[trajectory_id],
                expected_path=evaluation_path,
                label=f"evaluation {trajectory_id}",
            )
            try:
                evaluation = json.loads(evaluation_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ExecutionError(f"invalid evaluation artifact: {trajectory_id}") from exc
            if not isinstance(evaluation, dict) or any(
                (
                    evaluation.get("schema_version") != self._evaluation_protocol_version(),
                    evaluation.get("trajectory_id") != trajectory_id,
                    evaluation.get("case_id") != expected["case_id"],
                    evaluation.get("judge_qualification_contract_sha256")
                    != self.judge_qualification_contract_sha256,
                )
            ):
                raise ExecutionError(f"evaluation identity or protocol drift: {trajectory_id}")
        partition_root = self.store.root / "trajectories" / batch_id
        actual_trajectory_paths = {
            path.resolve() for path in partition_root.glob("*.json") if path.is_file()
        }
        if actual_trajectory_paths != expected_trajectory_paths:
            raise ExecutionError(
                f"round trajectory directory is not the exact frozen matrix: {batch_id}"
            )
        health_path = self.store.root / "health" / f"pre_scoring_health_{batch_id}.json"
        self._verify_artifact_record(
            checkpoint.get("pre_scoring_health_artifact"),
            expected_path=health_path,
            label="pre-scoring health",
        )
        self._validate_learning_curve_point_artifact(
            round_index=round_index,
            case_limit=case_limit,
            run_manifest_sha256=run_manifest_sha256,
            expected_input_skill_ids=expected_input_skill_ids,
            expected_input_skill_library_sha256=expected_input_skill_library_sha256,
            artifact_record=checkpoint.get("development_curve_artifact"),
        )
        candidates = self._validate_candidate_records(checkpoint.get("provisional_artifacts"))
        return checkpoint, candidates

    def validate_preceding_block_candidates(
        self,
        *,
        round_index: int,
        case_limit: int | None,
        run_manifest_sha256: str,
        trajectories: list[ResearchTrajectory],
        evaluations: dict[str, TrajectoryEvaluation],
    ) -> tuple[list[str], dict[str, Any]]:
        """Validate only the immediately preceding block's provisional skills."""

        validation_batch = self.training_plan.batches[round_index - 1]
        report_path = (
            self.store.root / "reports" / f"prospective_validation_{validation_batch.batch_id}.json"
        )
        baseline = self.active_skills()
        baseline_ids = sorted(item.skill_id for item in baseline)
        baseline_hash = skill_library_sha256(baseline)
        if round_index == 1:
            value = {
                "schema_version": 1,
                "run_id": self.run_id,
                "validation_batch_id": validation_batch.batch_id,
                "source_batch_id": None,
                "status": "no_predecessor_candidates",
                "baseline_active_skill_ids": baseline_ids,
                "baseline_skill_library_sha256": baseline_hash,
                "provisional_skill_ids": [],
                "audit_artifacts": {},
                "accepted_skill_ids": [],
                "deferred_skill_ids": [],
                "rejected_skill_ids": [],
                "output_active_skill_ids": baseline_ids,
                "output_skill_library_sha256": baseline_hash,
                "completed_at": datetime.now(UTC).isoformat(),
            }
            if report_path.is_file():
                prior = json.loads(report_path.read_text(encoding="utf-8"))
                if {k: v for k, v in prior.items() if k != "completed_at"} != {
                    k: v for k, v in value.items() if k != "completed_at"
                }:
                    raise ExecutionError("round-1 prospective boundary drift")
                return [], prior
            self.store.atomic_json(report_path, value)
            return [], value

        source_round_index = round_index - 1
        source_batch = self.training_plan.batches[source_round_index - 1]
        if validation_batch.prospective_validation_for != source_batch.batch_id:
            raise ExecutionError("current block is not the declared next-block validator")
        provisional_name, _ = self._round_manifest_names(source_batch.batch_id)
        raw = self.store.read_manifest(provisional_name)
        _, provisional_paths = self._validate_provisionals_ready_checkpoint(
            round_index=source_round_index,
            case_limit=case_limit,
            run_manifest_sha256=run_manifest_sha256,
            expected_input_skill_ids=list(raw["input_active_skill_ids"]),
            expected_input_skill_library_sha256=str(raw["input_skill_library_sha256"]),
        )
        fresh_budget = int(
            self.experiment["execution"].get("provisional_candidate_budget_per_block", 2)
        )
        budget = int(
            self.experiment["execution"].get(
                "maximum_concurrent_provisional_candidates", fresh_budget * 3
            )
        )
        if len(provisional_paths) > budget:
            raise ExecutionError(
                "provisional candidate count exceeds the predeclared next-block budget"
            )
        if report_path.is_file():
            prior = json.loads(report_path.read_text(encoding="utf-8"))
            if (
                prior.get("run_id") != self.run_id
                or prior.get("validation_batch_id") != validation_batch.batch_id
                or prior.get("source_batch_id") != source_batch.batch_id
                or prior.get("provisional_skill_ids")
                != sorted(load_skill(path).skill_id for path in provisional_paths)
            ):
                raise ExecutionError("prospective validation report identity drift")
            observed_decisions: dict[str, str] = {}
            accepted_candidates: list[SkillContract] = []
            accepted_audits: list[ProspectiveCandidateAudit] = []
            for path in provisional_paths:
                skill = load_skill(path)
                record = (prior.get("audit_artifacts") or {}).get(skill.skill_id)
                if not isinstance(record, dict):
                    raise ExecutionError("prospective validation audit record is missing")
                audit_path = self._verify_artifact_record(
                    {key: record[key] for key in ("path", "sha256")},
                    expected_path=(
                        self.store.root
                        / "prospective_audits"
                        / (
                            f"{source_batch.batch_id}__on__{validation_batch.batch_id}__"
                            f"{skill.skill_id}.json"
                        )
                    ),
                    label=f"prospective audit {skill.skill_id}",
                )
                audit = self.store.load_model(audit_path, ProspectiveCandidateAudit)
                observed_decisions[skill.skill_id] = audit.decision.decision
                if audit.decision.decision == "ACCEPT":
                    accepted_candidates.append(skill)
                    accepted_audits.append(audit)
            declared_ids = [
                *(str(item) for item in prior.get("accepted_skill_ids") or []),
                *(str(item) for item in prior.get("deferred_skill_ids") or []),
                *(str(item) for item in prior.get("rejected_skill_ids") or []),
            ]
            if len(declared_ids) != len(set(declared_ids)):
                raise ExecutionError("resumed prospective decision sets overlap")
            declared_decisions = {
                **{str(skill_id): "ACCEPT" for skill_id in prior.get("accepted_skill_ids") or []},
                **{str(skill_id): "DEFER" for skill_id in prior.get("deferred_skill_ids") or []},
                **{str(skill_id): "REJECT" for skill_id in prior.get("rejected_skill_ids") or []},
            }
            if observed_decisions != declared_decisions:
                raise ExecutionError("resumed prospective candidate decisions drifted")
            transaction = prior.get("activation_transaction")
            if accepted_candidates and (
                not isinstance(transaction, dict)
                or transaction.get("protocol")
                != "durable_intent_then_single_pointer_commit_v1"
                or transaction.get("required") is not True
                or transaction.get("accepted_skill_ids")
                != list(prior.get("accepted_skill_ids") or [])
                or transaction.get("target_library_version")
                != f"library_{str(prior.get('output_skill_library_sha256'))[:16]}"
            ):
                raise ExecutionError("prospective activation transaction binding drift")
            if accepted_candidates:
                committed_version = self._activate_accepted_skills(
                    accepted_candidates,
                    accepted_audits,
                )
                if committed_version != transaction["target_library_version"]:
                    raise ExecutionError("resumed prospective activation version drift")
            active_by_id = {item.skill_id: item for item in self.active_skills()}
            output_ids = list(prior.get("output_active_skill_ids") or [])
            if set(output_ids) != set(active_by_id):
                raise ExecutionError("resumed prospective output library membership drift")
            output_library = [active_by_id[item] for item in sorted(output_ids)]
            if skill_library_sha256(output_library) != prior.get(
                "output_skill_library_sha256"
            ):
                raise ExecutionError("resumed prospective output library drift")
            return list(prior.get("accepted_skill_ids") or []), prior

        audited: list[tuple[Path, Path, ProspectiveCandidateAudit]] = []
        for candidate_path in sorted(provisional_paths):
            audit = self.validate_provisional_candidate(
                candidate_path,
                source_round_index=source_round_index,
                validation_round_index=round_index,
                trajectories=trajectories,
                evaluations=evaluations,
                baseline_skills=baseline,
                case_limit=case_limit,
                activate_on_accept=False,
                cohort_candidate_paths=provisional_paths,
            )
            audit_path = (
                self.store.root
                / "prospective_audits"
                / (
                    f"{source_batch.batch_id}__on__{validation_batch.batch_id}__"
                    f"{audit.skill_id}.json"
                )
            )
            audited.append((candidate_path, audit_path, audit))

        # Prompt-memory documents are independently evaluated interventions, not
        # post-policy action rewrites. Every independently accepted document can
        # coexist in the library; exact aliases were removed before this stage.
        passing = sorted(
            (item for item in audited if item[2].decision.decision == "ACCEPT"),
            key=lambda item: (
                -float(item[2].decision.mean_delta_reward),
                float(item[2].decision.harmful_pair_rate),
                -int(item[2].decision.exposed_cases),
                item[2].skill_id,
            ),
        )
        selected_ids = {item[2].skill_id for item in passing}
        resolved_by_id = {item[2].skill_id: item for item in audited}
        deferred_ids = {
            item[2].skill_id for item in audited if item[2].decision.decision == "DEFER"
        }

        audit_records: dict[str, dict[str, Any]] = {}
        accepted: list[str] = []
        deferred: list[str] = []
        rejected: list[str] = []
        for candidate_path in sorted(provisional_paths):
            _, audit_path, audit = resolved_by_id[load_skill(candidate_path).skill_id]
            audit_records[audit.skill_id] = {
                **self._relative_artifact_record(audit_path),
                "decision": audit.decision.decision,
            }
            if audit.skill_id in selected_ids:
                accepted.append(audit.skill_id)
            elif audit.skill_id in deferred_ids:
                deferred.append(audit.skill_id)
            else:
                rejected.append(audit.skill_id)
        accepted_candidates = [load_skill(item[0]) for item in passing]
        accepted_audits = [item[2] for item in passing]
        active_after = self._merged_accepted_library(
            baseline,
            accepted_candidates,
            accepted_audits,
        )
        activation_version = f"library_{skill_library_sha256(active_after)[:16]}"
        value = {
            "schema_version": 1,
            "run_id": self.run_id,
            "validation_batch_id": validation_batch.batch_id,
            "source_batch_id": source_batch.batch_id,
            "status": "embedded_next_block_evaluation_complete",
            "baseline_active_skill_ids": baseline_ids,
            "baseline_skill_library_sha256": baseline_hash,
            "provisional_skill_ids": sorted(
                load_skill(path).skill_id for path in provisional_paths
            ),
            "audit_artifacts": audit_records,
            "accepted_skill_ids": accepted,
            "deferred_skill_ids": deferred,
            "rejected_skill_ids": rejected,
            "output_active_skill_ids": sorted(item.skill_id for item in active_after),
            "output_skill_library_sha256": skill_library_sha256(active_after),
            "activation_transaction": {
                "protocol": "durable_intent_then_single_pointer_commit_v1",
                "required": bool(accepted),
                "target_library_version": activation_version if accepted else None,
                "accepted_skill_ids": accepted,
            },
            "completed_at": datetime.now(UTC).isoformat(),
        }
        # The report is the durable commit intent.  Never move the active-library
        # pointer first: if the process exits after this atomic write, resume can
        # idempotently publish the one cohort version from the bound audits.
        self.store.atomic_json(report_path, value)
        if accepted_candidates:
            committed_version = self._activate_accepted_skills(
                accepted_candidates,
                accepted_audits,
            )
            if committed_version != activation_version:
                raise ExecutionError("prospective activation committed an unexpected version")
        committed = self.active_skills()
        if (
            sorted(item.skill_id for item in committed) != value["output_active_skill_ids"]
            or skill_library_sha256(committed) != value["output_skill_library_sha256"]
        ):
            raise ExecutionError("prospective activation did not reach its durable commit intent")
        return accepted, value

    def _write_round_complete_checkpoint(
        self,
        *,
        round_index: int,
        case_limit: int | None,
        run_manifest_sha256: str,
        provisionals_ready: dict[str, Any],
        prospective_report: dict[str, Any],
        accepted_from_preceding: list[str],
        learning_report: dict[str, Any],
    ) -> dict[str, Any]:
        batch_id = self.training_plan.batches[round_index - 1].batch_id
        provisional_name, complete_name = self._round_manifest_names(batch_id)
        provisional_manifest_path = self.store.root / "manifests" / f"{provisional_name}.json"
        source_report_path = (
            self.store.root / "reports" / f"candidate_source_grounding_round_{round_index:02d}.json"
        )
        prospective_path = self.store.root / "reports" / f"prospective_validation_{batch_id}.json"
        learning_path = self.store.root / "reports" / f"learning_checkpoint_{round_index:02d}.json"
        for supplied, persisted, label in (
            (prospective_report, prospective_path, "prospective validation"),
            (learning_report, learning_path, "learning checkpoint"),
        ):
            actual = json.loads(persisted.read_text(encoding="utf-8"))
            if canonical_json_sha256(actual) != canonical_json_sha256(supplied):
                raise ExecutionError(f"{label} argument differs from persisted bytes")
        active = self.active_skills()
        active_ids = sorted(item.skill_id for item in active)
        active_hash = skill_library_sha256(active)
        if (
            prospective_report["baseline_active_skill_ids"]
            != provisionals_ready["input_active_skill_ids"]
            or prospective_report["baseline_skill_library_sha256"]
            != provisionals_ready["input_skill_library_sha256"]
            or prospective_report["output_active_skill_ids"] != active_ids
            or prospective_report["output_skill_library_sha256"] != active_hash
        ):
            raise ExecutionError("embedded candidate decision differs from the block skill state")
        if (
            learning_report.get("schema_version") != 2
            or learning_report.get("measured_input_active_skill_ids")
            != provisionals_ready["input_active_skill_ids"]
            or learning_report.get("measured_input_skill_library_sha256")
            != provisionals_ready["input_skill_library_sha256"]
            or learning_report.get("development_curve_artifact")
            != provisionals_ready["development_curve_artifact"]
            or learning_report.get("active_skill_ids") != active_ids
            or learning_report.get("active_skill_library_sha256") != active_hash
        ):
            raise ExecutionError("learning checkpoint differs from the block skill transition")
        provisionals = self._validate_candidate_records(provisionals_ready["provisional_artifacts"])
        value = {
            "schema_version": 4,
            "run_id": self.run_id,
            "run_manifest_sha256": run_manifest_sha256,
            "round": round_index,
            "batch_id": batch_id,
            "stage": "complete",
            "case_limit": case_limit,
            "trajectory_schema_version": self._trajectory_protocol_version(),
            "evaluation_schema_version": self._evaluation_protocol_version(),
            "judge_qualification_contract_sha256": (self.judge_qualification_contract_sha256),
            "pre_validation_active_skill_ids": prospective_report["baseline_active_skill_ids"],
            "pre_validation_skill_library_sha256": prospective_report[
                "baseline_skill_library_sha256"
            ],
            "accepted_skill_ids": sorted(accepted_from_preceding),
            "training_input_active_skill_ids": provisionals_ready["input_active_skill_ids"],
            "training_input_skill_library_sha256": provisionals_ready["input_skill_library_sha256"],
            "expected_matrix_sha256": provisionals_ready["expected_matrix_sha256"],
            "provisionals_ready_manifest_sha256": sha256_file(provisional_manifest_path),
            "provisional_skill_ids": sorted(load_skill(path).skill_id for path in provisionals),
            "candidate_source_grounding_artifact": self._relative_artifact_record(
                source_report_path
            ),
            "prospective_validation_artifact": self._relative_artifact_record(prospective_path),
            "development_curve_artifact": provisionals_ready[
                "development_curve_artifact"
            ],
            "learning_checkpoint_artifact": self._relative_artifact_record(learning_path),
            "output_active_skill_ids": active_ids,
            "output_skill_library_version": (
                self.registry.current() or FORMAL_INITIAL_SKILL_LIBRARY_ID
            ),
            "output_skill_library_sha256": active_hash,
            "completed_at": datetime.now(UTC).isoformat(),
        }
        self.store.write_manifest(complete_name, value, overwrite=False)
        return self._validate_round_complete_checkpoint(
            round_index=round_index,
            case_limit=case_limit,
            run_manifest_sha256=run_manifest_sha256,
            expected_pre_validation_skill_ids=list(prospective_report["baseline_active_skill_ids"]),
            expected_pre_validation_skill_library_sha256=str(
                prospective_report["baseline_skill_library_sha256"]
            ),
        )

    def _validate_round_complete_checkpoint(
        self,
        *,
        round_index: int,
        case_limit: int | None,
        run_manifest_sha256: str,
        expected_pre_validation_skill_ids: list[str],
        expected_pre_validation_skill_library_sha256: str,
    ) -> dict[str, Any]:
        batch_id = self.training_plan.batches[round_index - 1].batch_id
        provisional_name, complete_name = self._round_manifest_names(batch_id)
        try:
            complete = self.store.read_manifest(complete_name)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise ExecutionError(f"invalid round-complete manifest envelope: {batch_id}") from exc
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
        if complete.get("schema_version") != 4 or set(complete) != expected_fields:
            raise ExecutionError(f"round complete is not current schema-4: {batch_id}")
        bindings = {
            "run_id": self.run_id,
            "run_manifest_sha256": run_manifest_sha256,
            "round": round_index,
            "batch_id": batch_id,
            "stage": "complete",
            "case_limit": case_limit,
            "trajectory_schema_version": self._trajectory_protocol_version(),
            "evaluation_schema_version": self._evaluation_protocol_version(),
            "judge_qualification_contract_sha256": (self.judge_qualification_contract_sha256),
            "pre_validation_active_skill_ids": expected_pre_validation_skill_ids,
            "pre_validation_skill_library_sha256": (expected_pre_validation_skill_library_sha256),
        }
        mismatches = [
            field for field, expected in bindings.items() if complete.get(field) != expected
        ]
        if mismatches:
            raise ExecutionError(
                f"round complete binding mismatch: {batch_id}; fields={mismatches}"
            )
        prospective_path = self._verify_artifact_record(
            complete["prospective_validation_artifact"],
            expected_path=(self.store.root / "reports" / f"prospective_validation_{batch_id}.json"),
            label="prospective validation report",
        )
        prospective = json.loads(prospective_path.read_text(encoding="utf-8"))
        if (
            prospective.get("baseline_active_skill_ids") != expected_pre_validation_skill_ids
            or prospective.get("baseline_skill_library_sha256")
            != expected_pre_validation_skill_library_sha256
            or sorted(prospective.get("accepted_skill_ids") or []) != complete["accepted_skill_ids"]
            or prospective.get("output_active_skill_ids") != complete["output_active_skill_ids"]
            or prospective.get("output_skill_library_sha256")
            != complete["output_skill_library_sha256"]
        ):
            raise ExecutionError(f"prospective transition drift: {batch_id}")
        if (
            complete["training_input_active_skill_ids"] != expected_pre_validation_skill_ids
            or complete["training_input_skill_library_sha256"]
            != expected_pre_validation_skill_library_sha256
        ):
            raise ExecutionError(f"embedded block input drift: {batch_id}")
        provisionals_ready, provisional_paths = self._validate_provisionals_ready_checkpoint(
            round_index=round_index,
            case_limit=case_limit,
            run_manifest_sha256=run_manifest_sha256,
            expected_input_skill_ids=list(complete["training_input_active_skill_ids"]),
            expected_input_skill_library_sha256=str(
                complete["training_input_skill_library_sha256"]
            ),
        )
        provisional_manifest_path = self.store.root / "manifests" / f"{provisional_name}.json"
        if (
            complete["provisionals_ready_manifest_sha256"] != sha256_file(provisional_manifest_path)
            or complete["expected_matrix_sha256"] != provisionals_ready["expected_matrix_sha256"]
            or complete["provisional_skill_ids"]
            != sorted(load_skill(path).skill_id for path in provisional_paths)
            or complete["development_curve_artifact"]
            != provisionals_ready["development_curve_artifact"]
        ):
            raise ExecutionError(f"provisional stage-chain drift: {batch_id}")
        source_path = self._verify_artifact_record(
            complete["candidate_source_grounding_artifact"],
            expected_path=(
                self.store.root
                / "reports"
                / f"candidate_source_grounding_round_{round_index:02d}.json"
            ),
            label="candidate source-grounding report",
        )
        source_report = json.loads(source_path.read_text(encoding="utf-8"))
        if (
            source_report.get("run_id") != self.run_id
            or source_report.get("round") != round_index
            or not _same_string_multiset(
                source_report.get("valid_candidate_files"),
                [str(path.relative_to(self.root)) for path in provisional_paths],
            )
        ):
            raise ExecutionError(f"candidate source-grounding drift: {batch_id}")
        learning_path = self._verify_artifact_record(
            complete["learning_checkpoint_artifact"],
            expected_path=(
                self.store.root / "reports" / f"learning_checkpoint_{round_index:02d}.json"
            ),
            label="learning checkpoint",
        )
        learning = json.loads(learning_path.read_text(encoding="utf-8"))
        if (
            learning.get("schema_version") != 2
            or learning.get("checkpoint") != round_index
            or learning.get("batch_id") != batch_id
            or learning.get("measured_input_active_skill_ids")
            != complete["training_input_active_skill_ids"]
            or learning.get("measured_input_skill_library_sha256")
            != complete["training_input_skill_library_sha256"]
            or learning.get("development_curve_artifact")
            != complete["development_curve_artifact"]
            or learning.get("active_skill_ids") != complete["output_active_skill_ids"]
            or learning.get("active_skill_library_sha256")
            != complete["output_skill_library_sha256"]
        ):
            raise ExecutionError(f"learning checkpoint drift: {batch_id}")
        active_by_id = {item.skill_id: item for item in self.active_skills()}
        output_ids = complete["output_active_skill_ids"]
        if not set(output_ids) <= set(active_by_id):
            raise ExecutionError(f"round output library is unavailable: {batch_id}")
        output_subset = [active_by_id[item] for item in output_ids]
        if skill_library_sha256(output_subset) != complete["output_skill_library_sha256"]:
            raise ExecutionError(f"round output skill library bytes drifted: {batch_id}")
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
            raise ExecutionError("training_complete is not current prospective schema-4") from exc
        if (
            summary.run_id != self.run_id
            or summary.run_manifest_sha256 != run_manifest_sha256
            or summary.trajectory_schema_version != self._trajectory_protocol_version()
            or summary.evaluation_schema_version != self._evaluation_protocol_version()
        ):
            raise ExecutionError("training_complete binding drift")
        rounds = len(self.training_plan.batches)
        if summary.rounds_completed != rounds:
            raise ExecutionError("training_complete does not contain all eight blocks")
        expected_manifest_keys = {batch.batch_id for batch in self.training_plan.batches}
        if set(summary.round_completion_manifests) != expected_manifest_keys:
            raise ExecutionError("training_complete round manifest set is incomplete")

        bootstrap, _ = self.initial_skill_library()
        previous_ids = sorted(item.skill_id for item in bootstrap)
        previous_hash = skill_library_sha256(bootstrap)
        accepted: list[str] = []
        rejected: list[str] = []
        completion_hashes: dict[str, str] = {}
        validation_hashes: dict[str, str] = {}
        final_complete: dict[str, Any] | None = None
        for round_index, batch in enumerate(self.training_plan.batches, start=1):
            _, complete_name = self._round_manifest_names(batch.batch_id)
            complete_path = self.store.root / "manifests" / f"{complete_name}.json"
            if not complete_path.is_file():
                raise ExecutionError(f"missing block completion: {batch.batch_id}")
            complete = self._validate_round_complete_checkpoint(
                round_index=round_index,
                case_limit=summary.case_limit,
                run_manifest_sha256=run_manifest_sha256,
                expected_pre_validation_skill_ids=previous_ids,
                expected_pre_validation_skill_library_sha256=previous_hash,
            )
            complete_hash = sha256_file(complete_path)
            completion_hashes[batch.batch_id] = complete_hash
            if summary.round_completion_manifests[batch.batch_id] != complete_hash:
                raise ExecutionError(f"block completion hash drift: {batch.batch_id}")
            validation_path = (
                self.store.root / "reports" / f"prospective_validation_{batch.batch_id}.json"
            )
            validation_hashes[batch.batch_id] = sha256_file(validation_path)
            validation = json.loads(validation_path.read_text(encoding="utf-8"))
            accepted.extend(validation.get("accepted_skill_ids") or [])
            rejected.extend(validation.get("rejected_skill_ids") or [])
            previous_ids = list(complete["output_active_skill_ids"])
            previous_hash = str(complete["output_skill_library_sha256"])
            final_complete = complete
        if self.training_plan.batches[-1].prospective_validation_for is None:
            raise ExecutionError("final block must validate its predecessor")
        if final_complete is None or final_complete["provisional_skill_ids"]:
            raise ExecutionError("the final block must not leave unvalidated candidates")
        if summary.round_completion_set_sha256 != canonical_json_sha256(completion_hashes):
            raise ExecutionError("training_complete block completion set drift")
        if summary.accepted_skill_ids != accepted or summary.rejected_skill_ids != rejected:
            raise ExecutionError("training_complete prospective decisions drift")
        if summary.prospective_validation_reports != validation_hashes:
            raise ExecutionError("training_complete prospective report set drift")
        curve_path = self.store.root / "reports" / "development_learning_curve.json"
        try:
            curve_summary = json.loads(curve_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ExecutionError("final development learning curve is missing") from exc
        if (
            summary.development_learning_curve_sha256 != sha256_file(curve_path)
            or curve_summary.get("run_id") != self.run_id
            or curve_summary.get("status") != "complete"
            or curve_summary.get("completed_points") != rounds
        ):
            raise ExecutionError("final development learning curve binding drift")
        active = self.active_skills()
        if (
            summary.active_skill_ids != sorted(item.skill_id for item in active)
            or summary.active_skill_library_sha256 != skill_library_sha256(active)
            or summary.active_skill_library_version
            != (self.registry.current() or FORMAL_INITIAL_SKILL_LIBRARY_ID)
            or summary.active_skill_ids != previous_ids
            or summary.active_skill_library_sha256 != previous_hash
        ):
            raise ExecutionError("training_complete frozen skill library drift")
        return summary

    def train(self, *, case_limit: int | None = None) -> TrainingSummary:
        rounds = int(self.experiment["execution"]["evolution_rounds"])
        if rounds != len(self.training_plan.batches):
            raise ExecutionError("evolution_rounds must match the prospective block plan")
        run_manifest_sha256 = self._verified_run_manifest_sha256()
        training_complete_path = self.store.root / "manifests" / "training_complete.json"
        if training_complete_path.is_file():
            summary = self._load_validated_training_summary(run_manifest_sha256=run_manifest_sha256)
            if summary.case_limit != case_limit:
                raise ExecutionError(
                    "frozen training_complete case_limit differs from requested matrix"
                )
            return summary

        bootstrap = load_skill_directory(self.root / "skills" / "bootstrap", active_only=True)
        previous_ids = sorted(item.skill_id for item in bootstrap)
        previous_hash = skill_library_sha256(bootstrap)
        accepted: list[str] = []
        rejected: list[str] = []
        completion_hashes: dict[str, str] = {}
        validation_hashes: dict[str, str] = {}
        rounds_completed = 0
        for round_index, batch in enumerate(self.training_plan.batches, start=1):
            provisional_name, complete_name = self._round_manifest_names(batch.batch_id)
            complete_path = self.store.root / "manifests" / f"{complete_name}.json"
            if complete_path.is_file():
                complete = self._validate_round_complete_checkpoint(
                    round_index=round_index,
                    case_limit=case_limit,
                    run_manifest_sha256=run_manifest_sha256,
                    expected_pre_validation_skill_ids=previous_ids,
                    expected_pre_validation_skill_library_sha256=previous_hash,
                )
                validation_path = (
                    self.store.root / "reports" / f"prospective_validation_{batch.batch_id}.json"
                )
                validation = json.loads(validation_path.read_text(encoding="utf-8"))
                accepted.extend(validation.get("accepted_skill_ids") or [])
                rejected.extend(validation.get("rejected_skill_ids") or [])
                validation_hashes[batch.batch_id] = sha256_file(validation_path)
                previous_ids = list(complete["output_active_skill_ids"])
                previous_hash = str(complete["output_skill_library_sha256"])
                completion_hashes[batch.batch_id] = sha256_file(complete_path)
                rounds_completed = round_index
                continue

            current_active = self.active_skills()
            current_ids = sorted(item.skill_id for item in current_active)
            current_hash = skill_library_sha256(current_active)
            validation_path = (
                self.store.root / "reports" / f"prospective_validation_{batch.batch_id}.json"
            )
            if current_ids == previous_ids and current_hash == previous_hash:
                training_input = list(current_active)
            elif validation_path.is_file():
                resumed_transition = json.loads(validation_path.read_text(encoding="utf-8"))
                if (
                    resumed_transition.get("baseline_active_skill_ids") != previous_ids
                    or resumed_transition.get("baseline_skill_library_sha256") != previous_hash
                    or resumed_transition.get("output_active_skill_ids") != current_ids
                    or resumed_transition.get("output_skill_library_sha256") != current_hash
                ):
                    raise ExecutionError(
                        "active library does not match the completed embedded transition"
                    )
                current_by_id = {item.skill_id: item for item in current_active}
                if not set(previous_ids) <= set(current_by_id):
                    raise ExecutionError("pre-block skill subset is unavailable during resume")
                training_input = [current_by_id[item] for item in previous_ids]
            else:
                raise ExecutionError(
                    "active library does not match the completed prospective chain"
                )
            preceding_candidates = self._preceding_provisional_paths(
                round_index=round_index,
                case_limit=case_limit,
                run_manifest_sha256=run_manifest_sha256,
            )
            training_input_ids = sorted(item.skill_id for item in training_input)
            training_input_hash = skill_library_sha256(training_input)

            provisional_path = self.store.root / "manifests" / f"{provisional_name}.json"
            if provisional_path.is_file():
                provisionals_ready, provisionals = self._validate_provisionals_ready_checkpoint(
                    round_index=round_index,
                    case_limit=case_limit,
                    run_manifest_sha256=run_manifest_sha256,
                    expected_input_skill_ids=training_input_ids,
                    expected_input_skill_library_sha256=training_input_hash,
                )
                development_curve_artifact = dict(
                    provisionals_ready["development_curve_artifact"]
                )
                validation_path = (
                    self.store.root / "reports" / f"prospective_validation_{batch.batch_id}.json"
                )
                prospective_report = json.loads(validation_path.read_text(encoding="utf-8"))
                accepted_now = list(prospective_report.get("accepted_skill_ids") or [])
            else:
                generate_kwargs: dict[str, Any] = {
                    "case_limit": case_limit,
                    "input_skills": training_input,
                }
                if preceding_candidates:
                    generate_kwargs["preceding_candidates"] = preceding_candidates
                trajectories = self.generate_training_round(round_index, **generate_kwargs)
                evaluations = self.score_trajectories(
                    trajectories,
                    self.main_adapter,
                    expected_skill_libraries=self._training_skill_memory_contract(
                        training_input,
                        preceding_candidates,
                    ),
                )
                self.prepare_development_curve_point(
                    round_index=round_index,
                    case_limit=case_limit,
                    run_manifest_sha256=run_manifest_sha256,
                    input_skills=training_input,
                    trajectories=trajectories,
                    evaluations=evaluations,
                )
                development_curve_artifact = self._relative_artifact_record(
                    self._learning_curve_point_path(round_index)
                )
                accepted_now, prospective_report = self.validate_preceding_block_candidates(
                    round_index=round_index,
                    case_limit=case_limit,
                    run_manifest_sha256=run_manifest_sha256,
                    trajectories=trajectories,
                    evaluations=evaluations,
                )
                deferred_ids = set(prospective_report.get("deferred_skill_ids") or [])
                deferred_candidates = [
                    path
                    for path in preceding_candidates
                    if load_skill(path).skill_id in deferred_ids
                ]
                if len(deferred_candidates) != len(deferred_ids):
                    raise ExecutionError(
                        "prospective report references a deferred candidate outside the "
                        "preceding checkpoint"
                    )
                fresh_candidate_budget = int(
                    self.experiment["execution"]["provisional_candidate_budget_per_block"]
                )
                concurrent_budget = int(
                    self.experiment["execution"].get(
                        "maximum_concurrent_provisional_candidates",
                        fresh_candidate_budget * 3,
                    )
                )
                candidate_nomination_slots = fresh_candidate_nomination_slots(
                    fresh_budget=fresh_candidate_budget,
                    concurrent_budget=concurrent_budget,
                    carryover_count=len(deferred_candidates),
                )
                raw_candidates = (
                    self.propose_candidates(
                        round_index=round_index,
                        trajectories=trajectories,
                        evaluations=evaluations,
                        candidate_budget=candidate_nomination_slots,
                    )
                    if round_index < rounds
                    else []
                )
                provisionals = self.revalidate_candidate_source_grounding(
                    round_index=round_index,
                    candidates=raw_candidates,
                    carryover_candidates=deferred_candidates,
                )
                provisionals_ready = self._write_provisionals_ready_checkpoint(
                    round_index=round_index,
                    case_limit=case_limit,
                    run_manifest_sha256=run_manifest_sha256,
                    input_skills=training_input,
                    trajectories=trajectories,
                    candidates=provisionals,
                    development_curve_artifact=development_curve_artifact,
                    preceding_candidates=preceding_candidates,
                )
            validation_path = (
                self.store.root / "reports" / f"prospective_validation_{batch.batch_id}.json"
            )
            validation_hashes[batch.batch_id] = sha256_file(validation_path)
            accepted.extend(accepted_now)
            rejected.extend(prospective_report.get("rejected_skill_ids") or [])
            if round_index == rounds and provisionals:
                raise ExecutionError("the final block cannot produce unvalidated candidates")
            learning_report = self.write_learning_checkpoint(
                round_index=round_index,
                case_limit=case_limit,
                run_manifest_sha256=run_manifest_sha256,
                accepted_skill_ids=accepted_now,
                input_skills=training_input,
                development_curve_artifact=development_curve_artifact,
            )
            complete = self._write_round_complete_checkpoint(
                round_index=round_index,
                case_limit=case_limit,
                run_manifest_sha256=run_manifest_sha256,
                provisionals_ready=provisionals_ready,
                prospective_report=prospective_report,
                accepted_from_preceding=accepted_now,
                learning_report=learning_report,
            )
            previous_ids = list(complete["output_active_skill_ids"])
            previous_hash = str(complete["output_skill_library_sha256"])
            completion_hashes[batch.batch_id] = sha256_file(complete_path)
            rounds_completed = round_index
            self.write_development_learning_curve_summary()

        curve_summary = self.write_development_learning_curve_summary()
        if curve_summary["completed_points"] != rounds:
            raise ExecutionError("training completed without all prequential curve points")
        active = self.active_skills()
        summary = TrainingSummary(
            run_id=self.run_id,
            run_manifest_sha256=run_manifest_sha256,
            trajectory_schema_version=self._trajectory_protocol_version(),
            evaluation_schema_version=self._evaluation_protocol_version(),
            case_limit=case_limit,
            rounds_completed=rounds_completed,
            round_completion_manifests=completion_hashes,
            round_completion_set_sha256=canonical_json_sha256(completion_hashes),
            accepted_skill_ids=accepted,
            rejected_skill_ids=rejected,
            prospective_validation_reports=validation_hashes,
            active_skill_ids=sorted(item.skill_id for item in active),
            active_skill_library_version=(
                self.registry.current() or FORMAL_INITIAL_SKILL_LIBRARY_ID
            ),
            active_skill_library_sha256=skill_library_sha256(active),
            development_learning_curve_sha256=sha256_file(
                self.store.root / "reports" / "development_learning_curve.json"
            ),
            completed_at=datetime.now(UTC).isoformat(),
        )
        self.store.write_manifest(
            "training_complete",
            summary.model_dump(mode="json", exclude={"content_sha256"}),
            overwrite=False,
        )
        return self._load_validated_training_summary(run_manifest_sha256=run_manifest_sha256)

    def external_test(self) -> dict[str, Any]:
        run_manifest_sha256 = self._verified_run_manifest_sha256()
        frozen_path = self.store.root / "manifests" / "training_complete.json"
        if not frozen_path.is_file():
            raise ExecutionError("external test requires a frozen training_complete manifest")
        active = self.active_skills()
        active_hash = skill_library_sha256(active)
        summary = self._load_validated_training_summary(run_manifest_sha256=run_manifest_sha256)
        if summary.active_skill_library_version != (
            self.registry.current() or FORMAL_INITIAL_SKILL_LIBRARY_ID
        ):
            raise ExecutionError("active skill library version changed after training freeze")
        if active_hash != summary.active_skill_library_sha256:
            raise ExecutionError("active skill library changed after training freeze")
        if not active:
            raise ExecutionError(
                "external test is not informative with an empty accepted skill library; "
                "preserve the completed no-skill training result and apply the "
                "predeclared method stop rule before consuming the held-out public "
                "external benchmark"
            )
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
            values["legal_skill_guard"],
            values["control_no_library"],
            {item.skill_id for item in active},
            partition,
            partition,
            require_distinct_partitions=False,
        )
        isolation_path = (
            self.store.root / "health" / "external_test_skill_library_isolation.json"
        )
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
                str(arm["intervention_sha256"]): list(arm["skills"])
                for arm in arm_specs
            },
        )
        report: dict[str, Any] = {
            "schema_version": 6,
            "run_id": self.run_id,
            "run_manifest_sha256": run_manifest_sha256,
            "trajectory_schema_version": self._trajectory_protocol_version(),
            "training_complete_sha256": sha256_file(frozen_path),
            "round_completion_manifests": summary.round_completion_manifests,
            "round_completion_set_sha256": summary.round_completion_set_sha256,
            "skill_library_intervention_isolation": self._relative_artifact_record(
                isolation_path
            ),
            "arms": {},
            "comparison_contract": {
                "primary_confirmatory_contrast": ("legal_skill_guard_minus_control_no_library"),
                "explanatory_ablations_are_not_additional_primary_hypotheses": True,
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
            "grounding_normalization_rate": lambda item: float(
                bool(item.grounding_normalizations)
            ),
        }
        judge_diagnostic_names = tuple(
            self.experiment["evaluation"]["judge_diagnostics"]
        )
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
                            judge_diagnostic_extractors[key](
                                evaluations[item.trajectory_id]
                            )
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
        treatment = values["legal_skill_guard"]
        if len(control) != len(treatment):
            raise ExecutionError("external paired matrix has unequal arm sizes")
        for before, after in zip(control, treatment, strict=True):
            if before.group_id != after.group_id:
                raise ExecutionError("external paired matrix order/group mismatch")
        bootstrap = int(self.experiment["prospective_validation"]["bootstrap_samples"])
        confidence = float(self.experiment["prospective_validation"]["confidence_level"])
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
                trajectory_behavior_values(
                    item, {skill.skill_id for skill in active}
                )[metric_name]
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
        explanatory_contrasts: dict[str, Any] = {}
        for before_id, after_id in (
            ("control_no_library", "ungated_source_grounded_skills"),
            ("ungated_source_grounded_skills", "legal_skill_guard"),
        ):
            before_arm = values[before_id]
            after_arm = values[after_id]
            if len(before_arm) != len(after_arm) or any(
                before.group_id != after.group_id
                for before, after in zip(before_arm, after_arm, strict=True)
            ):
                raise ExecutionError(
                    f"external explanatory contrast is misaligned: {after_id}_minus_{before_id}"
                )
            estimates: dict[str, Any] = {}
            for metric_name in (*official_names, *safety_names, *operational_names):
                section = (
                    "official_metrics"
                    if metric_name in official_names
                    else "safety_metrics"
                    if metric_name in safety_names
                    else "operational_metrics"
                )
                before_metric = [
                    float(getattr(getattr(evaluations[item.trajectory_id], section), metric_name))
                    for item in before_arm
                ]
                after_metric = [
                    float(getattr(getattr(evaluations[item.trajectory_id], section), metric_name))
                    for item in after_arm
                ]
                deltas = clustered_mean_deltas(
                    [item.case_id for item in before_arm], before_metric, after_metric
                )
                estimates[metric_name] = paired_bootstrap_interval(
                    deltas,
                    samples=bootstrap,
                    confidence_level=confidence,
                    seed=bootstrap_seed,
                ).model_dump(mode="json")
            contrast_name = f"{after_id}_minus_{before_id}"
            explanatory_contrasts[contrast_name] = {
                "metrics": estimates,
                "behavior": paired_behavior_estimates(
                    before_arm,
                    after_arm,
                    {item.skill_id for item in arm_by_id[after_id]["skills"]},
                    bootstrap_samples=bootstrap,
                    confidence_level=confidence,
                    seed=bootstrap_seed,
                ),
                "confirmatory": False,
                "interpretation": (
                    "Mechanism explanation only; no additional primary claim or "
                    "post-test candidate selection is permitted."
                ),
            }
        report["explanatory_ablation_contrasts"] = explanatory_contrasts
        secondary = list(self.experiment["evaluation"]["secondary_endpoints"])
        adjusted = benjamini_hochberg({name: raw_p_values[name] for name in secondary})
        report["inference"] = {
            "primary_endpoint": self.experiment["evaluation"]["primary_endpoint"],
            "primary_p_value": raw_p_values[self.experiment["evaluation"]["primary_endpoint"]],
            "secondary_benjamini_hochberg": adjusted,
            "direction": "legal_skill_guard_minus_control_no_library",
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
        if training_summary.active_skill_library_version != (
            self.registry.current() or FORMAL_INITIAL_SKILL_LIBRARY_ID
        ):
            raise ExecutionError("active skill library version changed after training freeze")
        if active_hash != training_summary.active_skill_library_sha256:
            raise ExecutionError("active skill library changed after training freeze")
        primary_report = json.loads(primary_report_path.read_text(encoding="utf-8"))
        if primary_report.get("run_id") != self.run_id:
            raise ExecutionError("primary external report belongs to a different run")
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
            for method in ("control_no_library", "legal_skill_guard")
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
            case_id, persona, skills, identity, method, seed, group_id, skill_hash = request
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
                intervention_hash: list(skills)
                for _, skills, intervention_hash in methods
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
        bootstrap_samples = int(self.experiment["prospective_validation"]["bootstrap_samples"])
        confidence = float(self.experiment["prospective_validation"]["confidence_level"])
        statistical_seed = int(self.experiment["statistical_seed"])
        metrics: dict[str, Any] = {}
        for metric_name, section in metric_sections.items():
            per_seed: dict[str, Any] = {}
            seed_deltas: list[float] = []
            for seed, by_method in values_by_seed.items():
                control = by_method["control_no_library"]
                treatment = by_method["legal_skill_guard"]
                if len(control) != len(treatment) or any(
                    before.group_id != after.group_id
                    for before, after in zip(control, treatment, strict=True)
                ):
                    raise ExecutionError(f"seed {seed} sensitivity pairs are misaligned")
                if section == "behavior":
                    before_values = [
                        trajectory_behavior_values(item, set())[metric_name]
                        for item in control
                    ]
                    after_values = [
                        trajectory_behavior_values(
                            item, {skill.skill_id for skill in active}
                        )[metric_name]
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
                    "legal_skill_guard_mean": round(statistics.fmean(after_values), 6),
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
            "ungated_source_grounded_skills",
            "legal_skill_guard",
            "training_policy_sample",
            "candidate_without",
            "candidate_with",
        ],
        partition: str,
        seed: int,
        sample_index: int,
        group_id: str,
        skill_hash: str,
        diagnostic_interaction_limit: int | None = None,
    ) -> ResearchTrajectory:
        path = self.store.trajectory_path(partition, trajectory_id)
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
            # A deterministic memo fallback is deliberately a blocking health
            # outcome, not a completed resumable unit.  Returning it here made a
            # stopped run reload the same unhealthy artifact forever, so an amended
            # renderer could never recover through the normal model path.
            if prior.status != "error" and not prior.memo_safe_fallback:
                return prior
        value = runner.run(
            raw_case=adapter.evaluator_case(case_id),
            domain=adapter.case_domain(case_id),
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
        )
        self.store.save_model(path, value, overwrite=path.exists())
        return value
