"""Trajectory contract for stateful skill and evolution experiments."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from legal_skill_guard.schemas.action import ActionDecision, StructuredAction
from legal_skill_guard.schemas.state import (
    TARGET_KINDS,
    ClientResponseKind,
    DisclosureDecision,
    StatePatch,
)
from legal_skill_guard.schemas.trajectory import Message, TokenUsage
from legal_skill_guard.verifiers.deterministic import VerificationResult


class ExperimentModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


CURRENT_TRAJECTORY_SCHEMA_VERSION = 16


@dataclass(frozen=True)
class TargetKindProvenanceIssue:
    """One missing, invalid, or contradictory current target-kind lineage."""

    code: Literal[
        "target_kind_missing",
        "target_kind_invalid",
        "target_kind_provenance_mismatch",
    ]
    turn: int
    location: str
    fact_id: str
    actual: object
    expected: str | None = None

    def detail(self) -> dict[str, object]:
        value: dict[str, object] = {
            "location": self.location,
            "fact_id": self.fact_id,
            "actual": self.actual,
        }
        if self.expected is not None:
            value["expected"] = self.expected
        return value


@dataclass(frozen=True)
class CurrentTrajectoryContractIssue:
    """One reason an artifact is not admissible under the active protocol."""

    code: str
    turn: int
    detail: object


def trajectory_target_kind_provenance_issues(
    trajectory: Any,
) -> list[TargetKindProvenanceIssue]:
    """Audit the authored kind lineage without inventing a compatibility default.

    The initial plan, every persisted pre-action fact, every policy observation,
    and every post-action fact share one immutable target-kind namespace.  A
    historical ``None`` remains parseable, but it can never establish or alter
    that lineage.
    """

    issues: list[TargetKindProvenanceIssue] = []
    emitted: set[tuple[object, ...]] = set()
    lineage: dict[str, str] = {}

    def record(
        *,
        code: Literal[
            "target_kind_missing",
            "target_kind_invalid",
            "target_kind_provenance_mismatch",
        ],
        turn: int,
        location: str,
        fact_id: str,
        actual: object,
        expected: str | None = None,
    ) -> None:
        key = (code, turn, location, fact_id, repr(actual), expected)
        if key in emitted:
            return
        emitted.add(key)
        issues.append(
            TargetKindProvenanceIssue(
                code=code,
                turn=turn,
                location=location,
                fact_id=fact_id,
                actual=actual,
                expected=expected,
            )
        )

    def observe(
        *,
        fact_id: object,
        target_kind: object,
        turn: int,
        location: str,
    ) -> None:
        normalized_id = str(fact_id or "")
        if target_kind is None or target_kind == "":
            record(
                code="target_kind_missing",
                turn=turn,
                location=location,
                fact_id=normalized_id,
                actual=target_kind,
            )
            return
        if target_kind not in TARGET_KINDS:
            record(
                code="target_kind_invalid",
                turn=turn,
                location=location,
                fact_id=normalized_id,
                actual=target_kind,
            )
            return
        normalized_kind = str(target_kind)
        prior = lineage.get(normalized_id)
        if prior is not None and prior != normalized_kind:
            record(
                code="target_kind_provenance_mismatch",
                turn=turn,
                location=location,
                fact_id=normalized_id,
                actual=normalized_kind,
                expected=prior,
            )
            return
        lineage[normalized_id] = normalized_kind

    initial_plan = getattr(trajectory, "initial_investigation_plan", None)
    for index, observation in enumerate(getattr(initial_plan, "observations", [])):
        observe(
            fact_id=getattr(observation, "fact_id", ""),
            target_kind=getattr(observation, "target_kind", None),
            turn=0,
            location=f"initial_investigation_plan.observations[{index}]",
        )

    for step_index, step in enumerate(getattr(trajectory, "steps", [])):
        turn = int(getattr(step, "turn", step_index + 1) or step_index + 1)
        for state_name in ("state_before",):
            state = getattr(step, state_name, {})
            facts = state.get("facts", []) if isinstance(state, dict) else []
            if not isinstance(facts, list):
                continue
            for fact_index, fact in enumerate(facts):
                if not isinstance(fact, dict):
                    continue
                observe(
                    fact_id=fact.get("fact_id"),
                    target_kind=fact.get("target_kind"),
                    turn=turn,
                    location=f"steps[{step_index}].{state_name}.facts[{fact_index}]",
                )

        state_patch = getattr(step, "state_patch", None)
        for observation_index, observation in enumerate(
            getattr(state_patch, "observations", [])
        ):
            observe(
                fact_id=getattr(observation, "fact_id", ""),
                target_kind=getattr(observation, "target_kind", None),
                turn=turn,
                location=(
                    f"steps[{step_index}].state_patch.observations[{observation_index}]"
                ),
            )

        state_after = getattr(step, "state_after", {})
        after_facts = (
            state_after.get("facts", []) if isinstance(state_after, dict) else []
        )
        if isinstance(after_facts, list):
            for fact_index, fact in enumerate(after_facts):
                if not isinstance(fact, dict):
                    continue
                observe(
                    fact_id=fact.get("fact_id"),
                    target_kind=fact.get("target_kind"),
                    turn=turn,
                    location=f"steps[{step_index}].state_after.facts[{fact_index}]",
                )
    return issues


def current_trajectory_contract_issues(
    trajectory: Any,
    *,
    expected_run_id: str | None = None,
) -> list[CurrentTrajectoryContractIssue]:
    """Return the complete reusable admission contract for a current artifact."""

    issues: list[CurrentTrajectoryContractIssue] = []
    schema_version = int(getattr(trajectory, "schema_version", 0) or 0)
    if schema_version != CURRENT_TRAJECTORY_SCHEMA_VERSION:
        issues.append(
            CurrentTrajectoryContractIssue(
                code="trajectory_schema_version_mismatch",
                turn=0,
                detail={
                    "expected": CURRENT_TRAJECTORY_SCHEMA_VERSION,
                    "actual": schema_version,
                },
            )
        )
    actual_run_id = str(getattr(trajectory, "run_id", "") or "")
    if expected_run_id is not None and actual_run_id != expected_run_id:
        issues.append(
            CurrentTrajectoryContractIssue(
                code="trajectory_run_id_mismatch",
                turn=0,
                detail={"expected": expected_run_id, "actual": actual_run_id},
            )
        )
    if schema_version == CURRENT_TRAJECTORY_SCHEMA_VERSION:
        issues.extend(
            CurrentTrajectoryContractIssue(
                code=item.code,
                turn=item.turn,
                detail=item.detail(),
            )
            for item in trajectory_target_kind_provenance_issues(trajectory)
        )
        delivery_mode = str(getattr(trajectory, "skill_delivery_mode", "") or "")
        exposed = [str(item) for item in getattr(trajectory, "exposed_skill_ids", [])]
        memory_sha = str(getattr(trajectory, "skill_memory_sha256", "") or "")
        if len(exposed) != len(set(exposed)) or exposed != sorted(exposed):
            issues.append(
                CurrentTrajectoryContractIssue(
                    code="skill_memory_ids_not_unique_and_sorted",
                    turn=0,
                    detail=exposed,
                )
            )
        if not re.fullmatch(r"[0-9a-f]{64}", memory_sha):
            issues.append(
                CurrentTrajectoryContractIssue(
                    code="skill_memory_sha256_invalid",
                    turn=0,
                    detail=memory_sha,
                )
            )
        if (delivery_mode == "none") != (not exposed):
            issues.append(
                CurrentTrajectoryContractIssue(
                    code="skill_memory_delivery_mode_mismatch",
                    turn=0,
                    detail={"mode": delivery_mode, "exposed_skill_ids": exposed},
                )
            )
        for step_index, step in enumerate(getattr(trajectory, "steps", [])):
            turn = int(getattr(step, "turn", step_index + 1) or step_index + 1)
            decision = getattr(step, "action_decision", None)
            retrieved = sorted(
                str(item) for item in getattr(decision, "retrieved_skill_ids", [])
            )
            activated = list(getattr(decision, "activated_skill_ids", []))
            skill_changes = [
                item
                for item in getattr(decision, "changes", [])
                if isinstance(item, dict) and item.get("skill_id")
            ]
            if retrieved != exposed:
                issues.append(
                    CurrentTrajectoryContractIssue(
                        code="turn_skill_memory_exposure_mismatch",
                        turn=turn,
                        detail={"expected": exposed, "actual": retrieved},
                    )
                )
            if activated or skill_changes:
                issues.append(
                    CurrentTrajectoryContractIssue(
                        code="retired_runtime_skill_executor_observed",
                        turn=turn,
                        detail={
                            "activated_skill_ids": activated,
                            "skill_change_count": len(skill_changes),
                        },
                    )
                )
    return issues


def assert_current_trajectory_contract(
    trajectory: Any,
    *,
    expected_run_id: str | None = None,
) -> None:
    """Fail closed before a current artifact enters scoring or evolution."""

    issues = current_trajectory_contract_issues(
        trajectory,
        expected_run_id=expected_run_id,
    )
    if issues:
        summary = "; ".join(
            f"{item.code}@turn{item.turn}:{item.detail}" for item in issues
        )
        raise ValueError(f"current trajectory contract failed: {summary}")


class PolicyEnvelope(ExperimentModel):
    state_patch: StatePatch = Field(default_factory=StatePatch)
    action: StructuredAction


class PolicyActionOutput(ExperimentModel):
    """Runtime policy boundary: state is owned by planner/controller, not the policy."""

    action: StructuredAction


class PolicyAttempt(ExperimentModel):
    raw_output: str
    parse_mode: Literal["json", "json_fragment", "fallback"]
    deterministic_changes: list[str] = Field(default_factory=list)
    health_violations: list[str] = Field(default_factory=list)
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    finish_reason: str | None = None


class MemoAttempt(ExperimentModel):
    raw_output: str
    health_violations: list[str] = Field(default_factory=list)
    deterministic_changes: list[str] = Field(default_factory=list)
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    finish_reason: str | None = None


class ClientSelectionAttempt(ExperimentModel):
    raw_output: str
    selected_fact_id: str | None = None
    deterministic_compatibility_violations: list[str] = Field(default_factory=list)


class LegacyClientRelevanceAttempt(ExperimentModel):
    """Read-only payload used only when auditing pre-protocol-37 artifacts."""

    raw_output: str
    verifier_model_id: str | None = None
    selected_fact_id: str
    verification_trigger: Literal[
        "selector_candidate",
        "deterministic_direct_answer_recovery_after_empty",
        "deterministic_presupposition_recovery_after_empty",
        "exhaustive_after_empty_cooperative_selection",
        "exhaustive_after_empty_repeated_selection",
    ] = "selector_candidate"
    parse_valid: bool
    answers_question: bool | None = None
    question_actor: str | None = None
    question_predicate: str | None = None
    question_attribute: str | None = None
    candidate_actor: str | None = None
    candidate_predicate: str | None = None
    candidate_attribute: str | None = None
    candidate_assertion_source: Literal[
        "direct_client_fact",
        "reported_other_claim",
        "client_worry_or_inference",
        "document_content",
        "other",
    ] | None = None
    same_actor: bool | None = None
    same_predicate: bool | None = None
    same_attribute: bool | None = None
    proposition_alignment_passed: bool | None = None
    deterministic_compatible: bool | None = None
    # Narrow, auditable override for correcting a false premise about an
    # event/document that the hidden client belief says did not exist.
    deterministic_presupposition_correction: bool = False
    deterministic_direct_answer: bool = False
    deterministic_incremental_over_opening: bool | None = None
    deterministic_compatibility_violations: list[str] = Field(default_factory=list)


class VisibleStateCoverageAttempt(ExperimentModel):
    target_id: str
    target_label: str
    raw_output: str = ""
    verifier_model_id: str | None = None
    model_called: bool
    parse_valid: bool
    answers_target: bool
    deterministic_compatible: bool | None = None
    deterministic_compatibility_violations: list[str] = Field(default_factory=list)
    applied: bool
    request_sha256: str | None = None


class ResearchStep(ExperimentModel):
    turn: int = Field(ge=1)
    visible_input: list[Message]
    state_before: dict[str, object]
    state_patch: StatePatch
    state_after: dict[str, object]
    raw_policy_output: str
    parse_mode: Literal["json", "json_fragment", "fallback"]
    policy_attempts: list[PolicyAttempt] = Field(default_factory=list)
    policy_health_violations: list[str] = Field(default_factory=list)
    post_skill_health_violations: list[str] = Field(default_factory=list)
    proposed_action: StructuredAction
    action_decision: ActionDecision
    rendered_question: str | None = None
    client_response: str | None = None
    client_input_sha256: str | None = None
    client_opening_selection_attempts: list[ClientSelectionAttempt] = Field(
        default_factory=list
    )
    client_selection_attempts: list[ClientSelectionAttempt] = Field(default_factory=list)
    client_disclosure_attempts: list[ClientSelectionAttempt] = Field(default_factory=list)
    client_route_decision_valid: bool | None = None
    # Historical input remains parseable for explicit archive audits, but these
    # fields are never serialized into a current trajectory.
    legacy_client_relevance_attempts: list[LegacyClientRelevanceAttempt] = Field(
        default_factory=list,
        validation_alias="client_relevance_attempts",
        exclude=True,
    )
    legacy_client_relevance_passed: bool | None = Field(
        default=None,
        validation_alias="client_relevance_passed",
        exclude=True,
    )
    client_response_kind: ClientResponseKind | None = None
    client_opening_reference_ids: list[str] = Field(default_factory=list)
    # Match and disclosure are distinct axes.  In particular, a withheld turn
    # has a matched hidden fact but no disclosed/selected fact.
    client_matched_fact_ids: list[str] = Field(default_factory=list)
    client_disclosure_decisions: dict[str, DisclosureDecision] = Field(
        default_factory=dict
    )
    client_selected_fact_ids: list[str] = Field(default_factory=list)
    # Retired at trajectory protocol 15.  Kept only so historical protocol-13/14
    # artifacts remain interpretable; current runners must persist an empty list.
    visible_state_coverage_attempts: list[VisibleStateCoverageAttempt] = Field(
        default_factory=list
    )
    visible_state_covered_target_ids: list[str] = Field(default_factory=list)
    client_safe_fallback: bool = False
    verifier_results: list[VerificationResult] = Field(default_factory=list)
    stop_gate_verdict: str
    stop_gate_reason: str
    token_usage: TokenUsage
    lawyer_finish_reason: str | None = None
    client_finish_reason: str | None = None


class ResearchTrajectory(ExperimentModel):
    schema_version: int = CURRENT_TRAJECTORY_SCHEMA_VERSION
    trajectory_id: str
    group_id: str | None = None
    sample_index: int = 0
    run_id: str
    method: Literal[
        "control_no_library",
        "legal_skill_evolve",
        "training_policy_sample",
    ]
    partition: str
    case_id: str
    domain: str = "general"
    jurisdiction: Literal["CN"] = "CN"
    persona: str
    seed: int
    model_id: str
    model_revision: str
    skill_library_version: str
    skill_delivery_mode: Literal["none", "prompt_memory"] = "none"
    exposed_skill_ids: list[str] = Field(default_factory=list)
    skill_memory_sha256: str = ""
    status: Literal[
        "memo_submitted",
        "abstained",
        "max_turns_forced_memo",
        "diagnostic_interaction_limit",
        "diagnostic_final",
        "diagnostic_abstain",
        "error",
    ]
    opening: str
    max_turns: int
    steps: list[ResearchStep]
    initial_investigation_plan: StatePatch = Field(default_factory=StatePatch)
    planning_attempts: list[PolicyAttempt] = Field(default_factory=list)
    planning_safe_partial: bool = False
    # Retired at protocol 15; current artifacts must leave these compatibility
    # fields empty/zero rather than importing a historical cross-slot closure.
    initial_visible_state_coverage_attempts: list[VisibleStateCoverageAttempt] = Field(
        default_factory=list
    )
    initial_visible_state_covered_target_ids: list[str] = Field(default_factory=list)
    initial_visible_state_coverage_token_usage: TokenUsage = Field(default_factory=TokenUsage)
    memo: str
    memo_attempts: list[MemoAttempt] = Field(default_factory=list)
    memo_health_violations: list[str] = Field(default_factory=list)
    memo_safe_fallback: bool = False
    elapsed_seconds: float = Field(ge=0)
    created_at: datetime
    error: str | None = None

    @field_validator("schema_version")
    @classmethod
    def require_current_schema_for_active_construction(
        cls,
        value: int,
        info: ValidationInfo,
    ) -> int:
        """Prevent active code from labeling a new object as a legacy protocol.

        Historical parsing is an explicit operation so old artifacts remain
        inspectable without allowing an ordinary constructor or resume path to
        produce anything except the current contract.
        """

        context = info.context if isinstance(info.context, dict) else {}
        if (
            value != CURRENT_TRAJECTORY_SCHEMA_VERSION
            and not context.get("allow_historical_trajectory_schema")
        ):
            raise ValueError(
                "active ResearchTrajectory requires schema_version "
                f"{CURRENT_TRAJECTORY_SCHEMA_VERSION}; use model_validate_historical "
                "for a read-only legacy audit"
            )
        return value

    @classmethod
    def model_validate_historical(cls, value: Any) -> Self:
        """Parse a legacy trajectory only for explicit read-only audit code."""

        return cls.model_validate(
            value,
            context={"allow_historical_trajectory_schema": True},
        )

    @classmethod
    def model_validate_historical_json(
        cls,
        value: str | bytes | bytearray,
    ) -> Self:
        """JSON counterpart of :meth:`model_validate_historical`."""

        return cls.model_validate_json(
            value,
            context={"allow_historical_trajectory_schema": True},
        )
