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
    ScoredMember,
    TrajectoryContrastPatch,
    compute_advantages,
)
from legal_skill_guard.evolution.diagnosis import TeacherDiagnosisDraft
from legal_skill_guard.evolution.reward import (
    RewardParameters,
)
from legal_skill_guard.evolution.teacher import (
    SkillTeacher,
    TeacherProposal,
    candidate_batch_source_grounding_issues,
    select_teacher_evidence_clusters,
    teacher_evidence_cluster_summaries,
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
    admit_active_skills_by_prompt_capacity,
    skill_memory_capacity_issues,
)
from legal_skill_guard.skills.registry import SkillRegistry
from legal_skill_guard.text_normalization import normalize_question
from legal_skill_guard.utils.hashing import canonical_json_sha256, sha256_file

T = TypeVar("T")
R = TypeVar("R")


class ExecutionError(RuntimeError):
    """An experiment stage is incomplete; persisted units may be resumed safely."""


class ExecutionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PreflightReport(ExecutionModel):
    ready: bool
    checks: dict[str, Any]


class TrainingSummary(ExecutionModel):
    schema_version: Literal[5] = 5
    run_id: str
    run_manifest_sha256: str
    trajectory_schema_version: Literal[16]
    evaluation_schema_version: Literal[13]
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
DIRECT_SKILL_ADMISSION_STATUS = "source_grounded_skills_admitted_to_working_library"
DIRECT_SKILL_ADMISSION_ROLE = "hard_trust_gate_not_candidate_efficacy_test"


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
        and candidate_provenance.source_evidence_cluster_id == witness.evidence_cluster_id
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
        "sessions_with_skill_exposure": exposed_sessions,
        "skill_exposure_session_rate": round(exposed_sessions / sessions, 6) if sessions else 0.0,
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
    external_case_ids: tuple[str, ...],
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
        raise ValueError("training must use four independent policy rollouts per case (K=4)")
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
    new_skill_budget = int(execution.get("maximum_new_skills_per_block", 0))
    teacher_call_budget = int(execution.get("teacher_call_budget_per_round", 0))
    if admission.get("mode") != "source_grounded_direct_admission":
        raise ValueError("skill admission must use source-grounded direct admission")
    if admission.get("per_candidate_outcome_gate") is not False:
        raise ValueError("the main run must not reintroduce per-candidate outcome gates")
    if new_skill_budget != 3 or teacher_call_budget != 3:
        raise ValueError("each source block must allow zero to three teacher skills")
    if int(admission.get("maintenance_interval_blocks", 0)) != 2:
        raise ValueError("library maintenance must be reported every two blocks")

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
    return by_group


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

    action = _effective_step_action(step)
    target_id = str(getattr(action, "target_id", "") or "")
    target_label = ""
    state = _execution_state_for_step(step)
    if state is not None:
        target_label = next(
            (str(fact.label) for fact in state.facts if str(fact.fact_id) == target_id),
            "",
        )
    else:
        for fact in getattr(step, "state_before", {}).get("facts") or []:
            if isinstance(fact, dict) and str(fact.get("fact_id") or "") == target_id:
                target_label = str(fact.get("label") or "")
                break
    # Planner identifiers are bookkeeping, not policy behavior.  Prefer the
    # skill-visible semantic label (or declared expected information) and fall
    # back to the raw identifier only when no semantic projection is available.
    # This prevents two aliases for the same question target from fabricating a
    # learnable fork.
    semantic_target = (
        normalize_question(target_label)
        or normalize_question(action.expected_information)
        or target_id
    )
    return (
        action.action_type,
        action.target_type,
        semantic_target,
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
    target IDs.  It does *not* need two trajectories to revisit a byte-identical
    intermediate state.  The source evidence supports only a candidate hypothesis
    and its hard trust gate; it does not establish a standalone causal effect.
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

    def first_divergence(
        positive: ResearchTrajectory,
        negative: ResearchTrajectory,
    ) -> int | None:
        for positive_step, negative_step in zip(positive.steps, negative.steps, strict=False):
            if positive_step.turn != negative_step.turn:
                return min(positive_step.turn, negative_step.turn)
            if _learnable_action_signature(positive_step) != _learnable_action_signature(
                negative_step
            ):
                return positive_step.turn
        if len(positive.steps) != len(negative.steps):
            return min(len(positive.steps), len(negative.steps)) + 1
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
            divergence_turn = first_divergence(positive, negative)
            if divergence_turn is None:
                continue
            negative_facts = _trajectory_elicited_fact_ids(negative)
            negative_gaps = _trajectory_identified_evidence_gap_ids(negative)
            negative_questions = question_count(negative)
            fact_count_gain = len(positive_facts) - len(negative_facts)
            gap_count_gain = len(positive_gaps) - len(negative_gaps)
            fact_efficiency_gain = (
                len(positive_facts) > 0
                and fact_count_gain == 0
                and positive_facts != negative_facts
                and positive_questions < negative_questions
            )
            common = {
                "highest_id": positive_id,
                "lowest_id": negative_id,
                "safety_failure_id": (
                    negative_id
                    if scored[negative_id].premature_final or scored[negative_id].unsupported_claim
                    else None
                ),
                "efficient_failure_id": (
                    negative_id if negative_questions > positive_questions else None
                ),
                "aligned_divergence_turn": divergence_turn,
                "positive_fact_count": len(positive_facts),
                "negative_fact_count": len(negative_facts),
                "immediate_fact_gain": 0,
                "fact_gain": max(0, fact_count_gain),
                "immediate_gap_gain": 0,
                "gap_gain": max(0, gap_count_gain),
                "reward_gap": round(reward_gap, 6),
            }
            if fact_count_gain > 0 or fact_efficiency_gain:
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
            if gap_count_gain > 0 and fact_count_gain >= 0:
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
            self.teacher_client,
            root / "configs/prompts/skill_teacher_zh.txt",
            baseline_policy_paths=[
                root / "configs/prompts/consultation_planner_zh.txt",
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
            or curve.get("empty_library_identity_shortcut") is not True
            or "never_teacher" not in str(curve.get("evidence_role", ""))
        ):
            raise ValueError("learning-curve role or lifecycle differs from the frozen protocol")
        cases_per_block = int(curve.get("cases_per_block", 0))
        if cases_per_block < 4:
            raise ValueError("learning-curve requires at least four sentinel cases per block")
        if int(curve.get("bootstrap_samples", 0)) < 100:
            raise ValueError("learning-curve bootstrap budget is too small")
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

    def _trusted_persisted_teacher_proposals(self, round_index: int) -> dict[str, Any]:
        """Count only resumable proposals bound to their exact successful response cache.

        The teacher manifest is written after all selected calls.  A process may
        therefore stop after one or more proposal files have been committed but
        before that manifest exists.  Those calls must not be budgeted twice, but
        a loose file count would let malformed or copied artifacts bypass the hard
        ledger.  This verifier mirrors the response-cache contract and binds the
        filename fingerprint, batch identity and teacher-authored diagnosis.
        """

        batch = self.training_plan.batches[round_index - 1]
        prefix = f"{batch.batch_id}.semantic_advantage"
        proposal_root = self.store.root / "teacher" / f"round_{round_index:02d}"
        cache_root = self.teacher_client.cache_root / "skill_teacher_batch"
        trusted_files: list[str] = []
        ignored_files: dict[str, str] = {}
        trusted_requests: set[str] = set()
        trusted_fingerprints: set[str] = set()
        for path in sorted(proposal_root.glob("proposal_*.json")):
            relative = str(path.relative_to(self.root))
            fingerprint = path.stem.removeprefix("proposal_")
            if len(fingerprint) != 16 or any(
                character not in "0123456789abcdef" for character in fingerprint
            ):
                ignored_files[relative] = "invalid_evidence_fingerprint_filename"
                continue
            try:
                proposal = self.store.load_model(path, TeacherProposal)
            except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                ignored_files[relative] = f"invalid_proposal:{type(exc).__name__}"
                continue
            expected_group_id = f"{prefix}.{fingerprint[:12]}"
            if proposal.group_id != expected_group_id:
                ignored_files[relative] = "proposal_group_identity_mismatch"
                continue
            if proposal.teacher_model != self.teacher_client.model:
                ignored_files[relative] = "proposal_teacher_model_mismatch"
                continue
            cache_path = cache_root / f"{proposal.request_sha256}.json"
            try:
                cached = json.loads(cache_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                ignored_files[relative] = f"missing_or_invalid_response_cache:{type(exc).__name__}"
                continue
            value = cached.get("value") if isinstance(cached, dict) else None
            cache_valid = (
                isinstance(cached, dict)
                and cached.get("schema_version") == 1
                and cached.get("request_sha256") == proposal.request_sha256
                and cached.get("response_sha256") == proposal.response_sha256
                and cached.get("model") == self.teacher_client.model
                and cached.get("purpose") == "skill_teacher_batch"
                and isinstance(value, dict)
                and isinstance(cached.get("invocation"), dict)
                and canonical_json_sha256(value) == proposal.response_sha256
            )
            if not cache_valid:
                ignored_files[relative] = "response_cache_contract_mismatch"
                continue
            try:
                draft = TeacherDiagnosisDraft.model_validate(value)
            except ValueError as exc:
                ignored_files[relative] = f"invalid_cached_teacher_diagnosis:{type(exc).__name__}"
                continue
            persisted_diagnosis = proposal.diagnosis
            if (
                draft.group_id != expected_group_id
                or persisted_diagnosis.group_id != expected_group_id
                or draft.model_dump(mode="json", exclude={"candidate_skill"})
                != persisted_diagnosis.model_dump(mode="json", exclude={"candidate_skill"})
            ):
                ignored_files[relative] = "cached_diagnosis_identity_mismatch"
                continue
            draft_candidate = draft.candidate_skill
            persisted_candidate = persisted_diagnosis.candidate_skill
            if (draft_candidate is None) != (persisted_candidate is None):
                ignored_files[relative] = "cached_candidate_presence_mismatch"
                continue
            if (
                draft_candidate is not None
                and persisted_candidate is not None
                and draft_candidate.model_dump(mode="json")
                != persisted_candidate.model_dump(mode="json", exclude={"provenance"})
            ):
                ignored_files[relative] = "cached_candidate_document_mismatch"
                continue
            if proposal.request_sha256 in trusted_requests:
                ignored_files[relative] = "duplicate_teacher_request"
                continue
            if fingerprint in trusted_fingerprints:
                ignored_files[relative] = "duplicate_evidence_fingerprint"
                continue
            trusted_requests.add(proposal.request_sha256)
            trusted_fingerprints.add(fingerprint)
            trusted_files.append(relative)
        return {
            "trusted_count": len(trusted_files),
            "trusted_files": trusted_files,
            "ignored_files": ignored_files,
        }

    def _teacher_invocation_budget_contract(
        self,
        teacher_budget: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Return the conservative number of genuinely new teacher calls remaining."""

        call_budget = int(self.experiment["execution"]["teacher_call_budget_per_round"])
        unfinished_rounds: list[int] = []
        persisted_by_round: dict[str, dict[str, Any]] = {}
        remaining_by_round: dict[str, int] = {}
        maximum_new_calls = 0
        for round_index in range(1, len(self.training_plan.batches) + 1):
            manifest = (
                self.store.root / "manifests" / f"teacher_round_{round_index:02d}.json"
            )
            if manifest.is_file():
                continue
            unfinished_rounds.append(round_index)
            persisted = self._trusted_persisted_teacher_proposals(round_index)
            trusted = min(int(persisted["trusted_count"]), call_budget)
            remaining = max(call_budget - trusted, 0)
            persisted_by_round[str(round_index)] = persisted
            remaining_by_round[str(round_index)] = remaining
            maximum_new_calls += remaining
        available = int(teacher_budget.get("available", -1)) if teacher_budget else -1
        return {
            "passed": teacher_budget is not None and available >= maximum_new_calls,
            "maximum_formal_new_calls": maximum_new_calls,
            "unfinished_teacher_rounds": unfinished_rounds,
            "trusted_persisted_proposals_by_round": persisted_by_round,
            "remaining_new_calls_by_round": remaining_by_round,
            **(teacher_budget or {}),
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
                == "direct_skill_accumulation_gpu_requalification_required",
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
            "external_cases": len(self.external_adapter.case_ids()),
            "initial_skill_library": initial_library_check,
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
                    "delivery": "fixed_session_prompt_memory",
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
        # Exact replay holds byte-identical requests fixed. Ordinary TF-GRPO members
        # receive independent plan seeds; candidate control/treatment share stream
        # zero and may differ only through their declared prompt memory.
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
        mismatches = [field for field, expected in bindings.items() if point.get(field) != expected]
        if mismatches:
            raise ExecutionError(
                "development learning-curve point binding mismatch: "
                f"batch={batch.batch_id}; fields={mismatches}"
            )
        if not expected_sentinel_ids:
            raise ExecutionError(f"development learning-curve sentinel is empty: {batch.batch_id}")

        curve = point.get("curve")
        if not isinstance(curve, dict):
            raise ExecutionError("development learning-curve statistic is missing")
        current_partition = batch.batch_id
        empty_partition = (
            current_partition if identity_baseline else f"learning_curve_shadow_{batch.batch_id}"
        )
        if any(
            (
                curve.get("sentinel_id") != batch.batch_id,
                curve.get("identity_baseline") is not identity_baseline,
                curve.get("current_library_version") != expected_input_skill_library_sha256,
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
            raise ExecutionError(f"development learning-curve pair count drift: {batch.batch_id}")
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
            if (
                point["empty_trajectory_artifacts"] != {}
                or point["empty_evaluation_artifacts"] != {}
            ):
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
            confidence_level=float(self.experiment["learning_curve"]["confidence_level"]),
            bootstrap_seed=int(self.experiment["learning_curve"]["bootstrap_seed"]),
        )
        recomputed_curve["initial_infrastructure_identity"]["stepwise_intervention_isolation"] = (
            "identity_by_construction" if identity_baseline else "passed_by_bound_executor_artifact"
        )
        if canonical_json_sha256(recomputed_curve) != canonical_json_sha256(curve):
            raise ExecutionError(f"development learning-curve statistic drift: {batch.batch_id}")
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
            confidence_level=float(self.experiment["learning_curve"]["confidence_level"]),
            bootstrap_seed=int(self.experiment["learning_curve"]["bootstrap_seed"]),
        )
        curve["initial_infrastructure_identity"]["stepwise_intervention_isolation"] = (
            "identity_by_construction" if identity_baseline else "passed_by_bound_executor_artifact"
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
        # Candidate outcomes are deliberately unavailable at nomination time.  The
        # teacher sees only frozen source contrasts and existing documents; skill
        # utility is measured later at whole-library level.
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
        trajectory_selections: dict[str, list[ContrastSelection]] = {}
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
                else select_trajectory_level_contrasts(group, mapped)
            )
            if not selections:
                group = group.model_copy(
                    update={
                        "informative": False,
                        "skip_reason": "no_reward_positive_trajectory_level_mechanism",
                    }
                )
            else:
                trajectory_selections[group_id] = selections
            groups.append((group, mapped))
        # Exploratory source contrasts nominate source-grounded methods rather than
        # causal efficacy claims.  Passing documents enter the next block's working
        # library; downstream blocks measure the cumulative library, not one tiny
        # candidate-vs-control cell.
        evidence_root = self.store.root / "evidence" / "trajectory_contrasts"
        new_patch_count = 0
        for group, mapped in groups:
            selections = trajectory_selections.get(group.group_id) or []
            if not selections:
                continue
            group_partitions = {item.partition for item in mapped.values()}
            if len(group_partitions) != 1:
                raise ExecutionError(f"trajectory contrast spans partitions: {group.group_id}")
            for selection in selections:
                evidence_group_id = f"{group.group_id}::{selection.signal_family}"
                evidence_group = group.model_copy(update={"group_id": evidence_group_id})
                patch = TrajectoryContrastPatch(
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
                    prior = self.store.load_model(patch_path, TrajectoryContrastPatch)
                    if canonical_json_sha256(
                        prior.model_dump(mode="json")
                    ) != canonical_json_sha256(patch.model_dump(mode="json")):
                        raise ExecutionError(f"trajectory contrast patch drift: {patch_path}")
                else:
                    self.store.save_model(patch_path, patch)
                    new_patch_count += 1

        accumulated_contrasts: list[
            tuple[AdvantageGroup, ContrastSelection, dict[str, ResearchTrajectory]]
        ] = []
        accumulated_evaluations: dict[str, TrajectoryEvaluation] = {}
        evidence_rounds: set[int] = set()
        for patch_path in sorted(evidence_root.glob("*.json")):
            patch = self.store.load_model(patch_path, TrajectoryContrastPatch)
            evidence_rounds.add(patch.round_index)
            mapped: dict[str, ResearchTrajectory] = {}
            for trajectory_id in patch.trajectory_ids:
                trajectory_path = self.store.trajectory_path(patch.partition, trajectory_id)
                evaluation_path = self.store.evaluation_path(trajectory_id)
                if sha256_file(trajectory_path) != patch.trajectory_sha256[trajectory_id]:
                    raise ExecutionError(f"trajectory contrast trajectory drift: {trajectory_id}")
                if sha256_file(evaluation_path) != patch.evaluation_sha256[trajectory_id]:
                    raise ExecutionError(f"trajectory contrast evaluation drift: {trajectory_id}")
                mapped[trajectory_id] = self.store.load_model(trajectory_path, ResearchTrajectory)
                accumulated_evaluations[trajectory_id] = self.store.load_model(
                    evaluation_path, TrajectoryEvaluation
                )
            if any(item.method != "training_policy_sample" for item in mapped.values()):
                raise ExecutionError(
                    "trajectory contrast bank contains non-training traffic; "
                    f"fresh run required: {patch_path}"
                )
            if (
                len(mapped) < 3
                or len({item.skill_library_version for item in mapped.values()}) != 1
            ):
                raise ExecutionError(
                    f"trajectory contrast bank lacks three same-prompt traces: {patch_path}"
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
            evidence_scope = str(cluster["evidence_scope"])
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
                minimum_source_domains=2 if evidence_scope == "general" else 1,
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
            staging_issues: list[str] = []
            if candidate is not None:
                (
                    destination,
                    staged_candidate,
                    staging_disposition,
                    duplicate_of,
                    staging_issues,
                ) = _stage_unique_teacher_candidate(
                    candidate,
                    candidate_root=self.candidate_root,
                    round_candidate_documents=round_candidate_documents,
                    round_document_owners=round_document_owners,
                )
                if destination is not None and staged_candidate is not None:
                    candidate_paths.append(destination)
                    # A later teacher call in the same block must see and be
                    # checked against the document just staged.  Otherwise two
                    # sequential calls can emit near-identical sibling skills:
                    # they are not byte-identical, so the exact same-round hash
                    # guard alone would miss the duplication.
                    existing.append(staged_candidate)
                    existing_by_id[staged_candidate.skill_id] = staged_candidate
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
                    "staging_issues": staging_issues,
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
                "trajectory_contrast_groups": len(trajectory_selections),
                "groups_without_trajectory_contrast_reasons": dict(
                    sorted(
                        Counter(
                            group.skip_reason
                            for group, _ in groups
                            if group.group_id not in trajectory_selections and group.skip_reason
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
                    "distinct_cluster_syntheses_from_cumulative_trajectory_contrasts"
                ),
                "pre_reward_attribution_scoreable_groups": len(scoreable_group_ids),
                "pre_reward_attribution_excluded_group_ids": list(
                    attribution_review.get("excluded_group_ids") or []
                ),
                "evidence_lifecycle": (
                    "trajectory_contrast_to_source_grounded_direct_working_library"
                ),
                "new_trajectory_contrast_patches": new_patch_count,
                "cumulative_trajectory_contrast_patches": len(accumulated_contrasts),
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
                "candidate_outcome_feedback_used": False,
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

    def write_learning_checkpoint(
        self,
        *,
        round_index: int,
        case_limit: int | None,
        run_manifest_sha256: str,
        admitted_skill_ids: list[str],
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
            "schema_version": 3,
            "run_id": self.run_id,
            "checkpoint": round_index,
            "batch_id": batch_id,
            "status": "measured_prequential_learning_checkpoint",
            "admitted_from_current_block": sorted(admitted_skill_ids),
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
                checkpoint.get("schema_version") != 3
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
                "output_skill_library_sha256": checkpoint["active_skill_library_sha256"],
                "admitted_from_current_block": checkpoint["admitted_from_current_block"],
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
            "status": ("complete" if len(points) == len(self.training_plan.batches) else "partial"),
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

    def admit_source_grounded_candidates(
        self,
        *,
        round_index: int,
        candidates: list[Path],
    ) -> list[Path]:
        """Admit source-grounded documents without a per-candidate outcome gate.

        This is deliberately a trust gate, not an efficacy test.  It verifies the
        teacher proposal, immutable source trajectory/evaluation evidence, document
        safety, duplicate identity and prompt capacity.  Every passing document is
        active in the next block; library-level downstream curves measure utility.
        """

        evidence_patches: dict[str, TrajectoryContrastPatch] = {}
        for patch_path in sorted(
            (self.store.root / "evidence" / "trajectory_contrasts").glob("*.json")
        ):
            patch = self.store.load_model(patch_path, TrajectoryContrastPatch)
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

        raw_candidates = sorted(candidates)
        all_candidates, deduplicated = self._deduplicate_candidate_paths(raw_candidates)
        new_candidates = list(all_candidates)
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
        candidate_budget = int(self.experiment["execution"]["maximum_new_skills_per_block"])
        if len(all_candidates) > candidate_budget:
            raise ExecutionError("teacher candidates exceed the declared per-block skill budget")
        active_capacity_baseline = self.active_skills()
        active_by_id = {skill.skill_id: skill for skill in active_capacity_baseline}
        active_documents = {
            skill_document_semantic_sha256(skill): skill.skill_id
            for skill in active_capacity_baseline
        }
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
            proposal = proposals.get(candidate.skill_id)
            issues: list[str]
            prior_active = active_by_id.get(candidate.skill_id)
            duplicate_active_id = prior_active is not None and skill_contract_definition_sha256(
                prior_active
            ) == skill_contract_definition_sha256(candidate)
            duplicate_active_document = active_documents.get(
                skill_document_semantic_sha256(candidate)
            )
            if prior_active is not None and not duplicate_active_id:
                issues = ["active_skill_id_definition_conflict"]
            elif duplicate_active_id:
                issues = ["exact_duplicate_of_active_skill_id"]
            elif duplicate_active_document is not None:
                issues = [f"exact_duplicate_of_active_document:{duplicate_active_document}"]
            elif proposal is None:
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
                else:
                    # One source and many sources use the same system-owned
                    # witness gate.  A teacher-authored diagnostic turn must
                    # never make a domain candidate stricter than a general
                    # candidate.
                    issues, _ = candidate_batch_source_grounding_issues(
                        proposal.diagnosis,
                        contrast_contexts,
                        existing_skills=active_capacity_baseline,
                    )
            if not issues:
                candidate.status = "active"
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

        # Source-valid candidates must fit together with the exact active library
        # before the next block starts.  The source-order first fit is outcome-blind.
        enabled_for_capacity: list[SkillContract] = []
        path_by_id: dict[str, Path] = {}
        for candidate_path in valid:
            candidate = load_skill(candidate_path)
            enabled_for_capacity.append(candidate)
            path_by_id[candidate.skill_id] = candidate_path
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
                record["candidate_contract_sha256"] = skill_contract_definition_sha256(candidate)
            valid = [
                candidate_path
                for candidate_path in valid
                if load_skill(candidate_path).skill_id in admitted_ids
            ]
        output_skills = sorted(
            [*active_capacity_baseline, *(load_skill(path) for path in valid)],
            key=lambda skill: skill.skill_id,
        )
        output_hash = skill_library_sha256(output_skills)
        output_version = (
            f"library_{output_hash[:16]}"
            if valid
            else (self.registry.current() or FORMAL_INITIAL_SKILL_LIBRARY_ID)
        )
        report_path = self._skill_admission_report_path(round_index)
        self.store.atomic_json(
            report_path,
            {
                "schema_version": 5,
                "run_id": self.run_id,
                "round": round_index,
                "status": DIRECT_SKILL_ADMISSION_STATUS,
                "admission_role": DIRECT_SKILL_ADMISSION_ROLE,
                "per_candidate_outcome_gate": False,
                "baseline_active_skill_ids": sorted(active_by_id),
                "baseline_skill_library_sha256": skill_library_sha256(active_capacity_baseline),
                "records": records,
                "new_candidate_files": [
                    str(path.relative_to(self.root)) for path in new_candidates
                ],
                "deduplicated_candidates": deduplication_records,
                "prompt_capacity_admission_order": [
                    candidate.skill_id for candidate in enabled_for_capacity
                ],
                "prompt_capacity_rejections": capacity_rejected,
                "admitted_skill_files": [str(path.relative_to(self.root)) for path in valid],
                "admitted_skill_ids": sorted(admitted_ids),
                "output_active_skill_ids": [skill.skill_id for skill in output_skills],
                "output_skill_library_sha256": output_hash,
                "output_skill_library_version": output_version,
                "invalid_candidate_files": [
                    *(record["candidate_file"] for record in records if not record["valid"]),
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

    def _activate_source_grounded_skills(
        self,
        *,
        round_index: int,
        candidate_paths: list[Path],
    ) -> str:
        """Atomically publish one block's hard-gate-passing document cohort."""

        report_path = self._skill_admission_report_path(round_index)
        if not report_path.is_file():
            raise ExecutionError("source-grounded activation report is missing")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if (
            report.get("schema_version") != 5
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

        merged = sorted(
            [*active, *(load_skill(path) for path in candidate_paths)],
            key=lambda skill: skill.skill_id,
        )
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
                parent_version=self.registry.current(),
                evidence={
                    "transaction": "source_grounded_direct_admission",
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
            report.get("schema_version") != 5
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
            expected_path = self.candidate_root / f"{skill_id}.yaml"
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
        deterministic_value = {
            "schema_version": 1,
            "run_id": self.run_id,
            "round": round_index,
            "batch_id": batch_id,
            "status": (
                "healthy"
                if not static_issues and not duplicate_groups and not capacity_issues
                else "requires_operator_review"
            ),
            "maintenance_scope": "whole_working_library",
            "automatic_candidate_effect_pruning": False,
            "reason": (
                "individual skill effects are not identifiable from cumulative block outcomes; "
                "exact duplicates and hard-invalid documents are prevented at admission"
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
            "actions": [],
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
        learning_path = self._verify_artifact_record(
            complete["learning_checkpoint_artifact"],
            expected_path=(
                self.store.root / "reports" / f"learning_checkpoint_{round_index:02d}.json"
            ),
            label="learning checkpoint",
        )
        learning = json.loads(learning_path.read_text(encoding="utf-8"))
        if (
            learning.get("schema_version") != 3
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
        for field, expected_path, label in (
            (
                "health_artifact",
                self.store.root / "health" / f"pre_scoring_health_{batch.batch_id}.json",
                "pre-scoring health",
            ),
            (
                "teacher_artifact",
                self.store.root / "manifests" / f"teacher_round_{round_index:02d}.json",
                "teacher round",
            ),
        ):
            self._verify_artifact_record(complete[field], expected_path=expected_path, label=label)
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
            raise ExecutionError("training_complete is not current schema-5") from exc
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
            complete = self._validate_direct_block_complete(
                round_index=round_index,
                case_limit=summary.case_limit,
                run_manifest_sha256=run_manifest_sha256,
                expected_input_ids=previous_ids,
                expected_input_hash=previous_hash,
                expected_input_version=previous_version,
            )
            complete_path = (
                self.store.root
                / "manifests"
                / f"{self._direct_block_manifest_name(batch.batch_id)}.json"
            )
            completion_hashes[batch.batch_id] = sha256_file(complete_path)
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
        for round_index, batch in enumerate(self.training_plan.batches, start=1):
            block_name = self._direct_block_manifest_name(batch.batch_id)
            block_path = self.store.root / "manifests" / f"{block_name}.json"
            if block_path.is_file():
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
                self.prepare_development_curve_point(
                    round_index=round_index,
                    case_limit=case_limit,
                    run_manifest_sha256=run_manifest_sha256,
                    input_skills=input_skills,
                    trajectories=trajectories,
                    evaluations=evaluations,
                )
                development_curve_artifact = self._relative_artifact_record(
                    self._learning_curve_point_path(round_index)
                )
                if admission_path.is_file():
                    admission_report, admitted_paths = self._load_direct_admission_report(
                        round_index=round_index,
                        expected_baseline_ids=previous_ids,
                        expected_baseline_hash=previous_hash,
                    )
                else:
                    candidate_paths = self.propose_candidates(
                        round_index=round_index,
                        trajectories=trajectories,
                        evaluations=evaluations,
                        candidate_budget=int(
                            self.experiment["execution"]["maximum_new_skills_per_block"]
                        ),
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

            completion_hashes[batch.batch_id] = sha256_file(block_path)
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
                "external test is not informative with an empty learned skill library; "
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
            "schema_version": 6,
            "run_id": self.run_id,
            "run_manifest_sha256": run_manifest_sha256,
            "trajectory_schema_version": self._trajectory_protocol_version(),
            "training_complete_sha256": sha256_file(frozen_path),
            "round_completion_manifests": summary.round_completion_manifests,
            "round_completion_set_sha256": summary.round_completion_set_sha256,
            "skill_library_intervention_isolation": self._relative_artifact_record(isolation_path),
            "arms": {},
            "comparison_contract": {
                "primary_confirmatory_contrast": ("legal_skill_evolve_minus_control_no_library"),
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
