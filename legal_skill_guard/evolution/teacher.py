"""TF-GRPO contrast packaging and prompt-skill teacher proposals.

The teacher learns a document that is shown to the frozen lawyer before it acts.
Source evidence is a separate, system-owned witness.  Nothing in this module
executes a skill or rewrites a lawyer action.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from legal_skill_guard.agent.state_manager import reconstruct_execution_state
from legal_skill_guard.evaluation.semantic import TrajectoryEvaluation
from legal_skill_guard.evolution.advantage import AdvantageGroup, ContrastSelection
from legal_skill_guard.evolution.diagnosis import (
    SkillDiagnosis,
    TeacherDiagnosisDraft,
    diagnosis_quality_issues,
)
from legal_skill_guard.inference.codex_cli_client import strict_output_schema
from legal_skill_guard.schemas.experiment import ResearchTrajectory
from legal_skill_guard.schemas.skill import SkillContract, SkillEvaluation
from legal_skill_guard.schemas.state import ConsultationState, StatePatch
from legal_skill_guard.skills.loader import (
    find_lexical_near_duplicates,
    find_scope_redundancies,
    find_structural_duplicates,
    skill_interface_catalog,
    validate_skill_static,
)
from legal_skill_guard.skills.memory import policy_skill_document
from legal_skill_guard.text_normalization import normalize_question
from legal_skill_guard.utils.hashing import canonical_json_sha256

SignalFamily = Literal[
    "fact_elicitation",
    "evidence_gap_identification",
    "safe_stop",
]


class TeacherModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceForkWitness(TeacherModel):
    """One immutable same-state action fork supporting a prompt hypothesis."""

    group_id: str
    case_id: str
    domain: str
    divergence_turn: int
    visible_state_sha256: str
    positive_trajectory_id: str
    negative_trajectory_id: str
    positive_action: dict[str, object]
    negative_action: dict[str, object]
    reward_gap: float


class SourceWitness(TeacherModel):
    """System-owned causal evidence, deliberately separate from policy advice."""

    schema_version: Literal[1] = 1
    evidence_cluster_id: str
    signal_family: SignalFamily
    forks: list[SourceForkWitness] = Field(min_length=1)


class TeacherProposal(TeacherModel):
    schema_version: Literal[2] = 2
    group_id: str
    request_sha256: str
    response_sha256: str
    teacher_model: str
    parse_status: str
    static_issues: list[str] = Field(default_factory=list)
    source_group_ids: list[str] = Field(default_factory=list)
    source_witness: SourceWitness | None = None
    diagnosis: SkillDiagnosis

    @property
    def usable_candidate(self) -> SkillContract | None:
        if self.parse_status != "valid_candidate" or self.static_issues:
            return None
        return self.diagnosis.candidate_skill


def candidate_overlap_issues(
    candidate: SkillContract,
    *,
    historical_skills: list[SkillContract],
    runtime_skills: list[SkillContract],
) -> list[str]:
    """Reject copied advice without reviving the retired trigger engine."""

    delivered = [
        skill for skill in runtime_skills if skill.status in {"active", "provisional"}
    ]
    same_scope_history = [
        skill for skill in historical_skills if skill.domain == candidate.domain
    ]
    return sorted(
        {
            *(
                f"structural_duplicate:{item}"
                for item in find_structural_duplicates(candidate, historical_skills)
            ),
            *(
                f"scope_redundancy:{item}"
                for item in find_scope_redundancies(candidate, delivered)
            ),
            *(
                f"lexical_near_duplicate:{item}"
                for item in find_lexical_near_duplicates(candidate, same_scope_history)
            ),
        }
    )


class TeacherResponse(Protocol):
    value: dict[str, Any]
    model: str
    request_sha256: str
    response_sha256: str


class TeacherClient(Protocol):
    model: str

    def generate_json(
        self,
        *,
        purpose: str,
        system_prompt: str,
        user_prompt: str,
        output_schema: dict[str, Any],
    ) -> TeacherResponse: ...


def _compact_batch_teacher_state(state: ConsultationState) -> dict[str, Any]:
    """Expose only action-time visible state, without persona or answer text."""

    return {
        "turn": state.turn,
        "max_turns": state.max_turns,
        "domain": state.domain,
        "visible_fact_plan": [
            {
                "fact_id": fact.fact_id,
                "label": fact.label,
                "status": fact.status,
                "criticality": fact.criticality,
                "target_kind": fact.target_kind,
            }
            for fact in state.facts
        ],
        "asked_target_ids": list(state.asked_targets),
        "prior_interaction_outcomes": [
            {
                "turn": item.turn,
                "action_type": item.action_type,
                "target_id": item.target_id,
                "response_kind": item.response_kind,
                "new_information": item.new_information,
                "disclosed_fact_ids": list(item.disclosed_fact_ids),
            }
            for item in state.interactions
        ],
        "unresolved_conflict_fact_ids": [
            conflict.fact_id for conflict in state.unresolved_conflicts
        ],
        "risk_flags": list(state.risk_flags),
    }


def _schema_invalid_proposal(
    *,
    group_id: str,
    response: TeacherResponse,
    error: ValidationError,
    normalization_changes: list[str] | None = None,
) -> TeacherProposal:
    """Quarantine malformed teacher output without inventing a candidate."""

    del normalization_changes  # accepted only for explicit legacy caller diagnostics
    first = error.errors(include_url=False, include_input=False)[0]
    location = ".".join(str(item) for item in first.get("loc", ())) or "root"
    issue = (
        f"teacher_output_schema_invalid:{location}:"
        f"{first.get('type', 'validation_error')}"
    )
    diagnosis = SkillDiagnosis.model_validate(
        {
            "group_id": group_id,
            "failure_state": {"turn": None, "relevant_fields": []},
            "behavior_difference": {
                "positive_action": "教师输出未通过结构校验",
                "negative_action": "教师输出未通过结构校验",
            },
            "causal_hypothesis": "教师输出未通过结构校验，未形成候选文档",
            "proposed_change": "NOOP",
            "skill_scope": "general",
            "known_risks": [issue],
            "candidate_skill": None,
        }
    )
    return TeacherProposal(
        group_id=group_id,
        request_sha256=response.request_sha256,
        response_sha256=response.response_sha256,
        teacher_model=response.model,
        parse_status="invalid_candidate",
        static_issues=[issue],
        source_group_ids=[],
        source_witness=None,
        diagnosis=diagnosis,
    )


def _materialize_teacher_diagnosis(draft: TeacherDiagnosisDraft) -> SkillDiagnosis:
    """Attach empty system-owned metadata to a teacher-authored document draft."""

    candidate = (
        SkillContract.model_validate(
            {
                **draft.candidate_skill.model_dump(mode="json"),
                "provenance": {"source": "tf_grpo"},
                "evaluation": SkillEvaluation().model_dump(mode="json"),
            }
        )
        if draft.candidate_skill is not None
        else None
    )
    return SkillDiagnosis(
        group_id=draft.group_id,
        failure_state=draft.failure_state,
        behavior_difference=draft.behavior_difference,
        causal_hypothesis=draft.causal_hypothesis,
        proposed_change=draft.proposed_change,
        skill_scope=draft.skill_scope,
        known_risks=draft.known_risks,
        candidate_skill=candidate,
    )
def _effective_action(step: Any) -> Any:
    final = getattr(getattr(step, "action_decision", None), "final", None)
    return final if final is not None else step.proposed_action


def _execution_state(step: Any) -> ConsultationState:
    return reconstruct_execution_state(
        step.state_before,
        getattr(step, "state_patch", StatePatch()),
        turn=step.turn,
        candidate_action=step.proposed_action.model_dump(mode="json"),
    )


_CAUSAL_STATE_EXCLUSIONS = {
    "session_id",
    "persona",
    "candidate_action",
    "active_skills",
    "candidate_target_repeated",
    "candidate_target_unavailable",
    "candidate_target_low_value",
    "candidate_target_already_known",
    "candidate_target_is_client_fact",
    "candidate_target_is_evidence_gap",
    "candidate_target_criticality",
}


def _causal_state_payload(step: Any) -> dict[str, Any]:
    payload = {
        key: value
        for key, value in _execution_state(step).model_dump(mode="json").items()
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
    return payload


def _action_payload(step: Any) -> dict[str, object]:
    action = _effective_action(step)
    return {
        "action_type": action.action_type,
        "target_type": action.target_type,
        "target_id": action.target_id,
        "content": action.content,
        "expected_information": action.expected_information,
        "constraints": list(action.constraints),
    }


def _learnable_action_signature(step: Any) -> tuple[object, ...]:
    action = _effective_action(step)
    return (
        action.action_type,
        action.target_type,
        action.target_id,
        normalize_question(action.content),
        normalize_question(action.expected_information),
        tuple(action.constraints),
    )


def _target_kind(state: ConsultationState, target_id: str | None) -> str | None:
    return next(
        (fact.target_kind for fact in state.facts if fact.fact_id == target_id),
        None,
    )


def _behavior_family(positive_step: Any, negative_step: Any) -> str:
    positive = _effective_action(positive_step)
    negative = _effective_action(negative_step)
    terminal = {"final", "abstain"}
    inquiry = {"ask", "clarify", "verify", "retrieve", "summarize"}
    if negative.action_type in terminal and positive.action_type in inquiry:
        return "continue_inquiry"
    if positive.action_type in terminal and negative.action_type in inquiry:
        return "safe_stop"
    if (positive.target_type, positive.target_id) != (
        negative.target_type,
        negative.target_id,
    ):
        return "target_selection"
    if positive.action_type != negative.action_type:
        return "action_choice"
    if (
        normalize_question(positive.content),
        normalize_question(positive.expected_information),
    ) != (
        normalize_question(negative.content),
        normalize_question(negative.expected_information),
    ):
        return "question_formulation"
    if tuple(positive.constraints) != tuple(negative.constraints):
        return "question_constraint"
    return "other_policy_difference"


def _source_fork(
    group: AdvantageGroup,
    selection: ContrastSelection,
    trajectories: dict[str, ResearchTrajectory],
) -> tuple[SourceForkWitness | None, list[str]]:
    """Validate one system-selected causal fork independently of skill prose."""

    turn = selection.aligned_divergence_turn
    if turn is None:
        return None, ["source_grounding_missing_aligned_divergence_turn"]
    positive = trajectories.get(selection.highest_id)
    negative = trajectories.get(selection.lowest_id)
    if positive is None:
        return None, ["source_grounding_missing_highest_trajectory"]
    if negative is None:
        return None, ["source_grounding_missing_lowest_trajectory"]
    positive_step = next((item for item in positive.steps if item.turn == turn), None)
    negative_step = next((item for item in negative.steps if item.turn == turn), None)
    if positive_step is None:
        return None, ["source_grounding_divergence_turn_absent_from_highest_trajectory"]
    if negative_step is None:
        return None, ["source_grounding_divergence_turn_absent_from_lowest_trajectory"]
    try:
        positive_state = _execution_state(positive_step)
        _execution_state(negative_step)
        positive_state_hash = canonical_json_sha256(_causal_state_payload(positive_step))
        negative_state_hash = canonical_json_sha256(_causal_state_payload(negative_step))
    except (AttributeError, ValueError):
        return None, ["source_grounding_invalid_visible_state"]
    if positive_state_hash != negative_state_hash:
        return None, ["source_grounding_not_a_shared_visible_state"]
    if _learnable_action_signature(positive_step) == _learnable_action_signature(negative_step):
        return None, ["source_grounding_no_learnable_action_difference"]
    if selection.reward_gap is None or selection.reward_gap <= 0:
        return None, ["source_grounding_nonpositive_reward_gap"]
    positive_action = _effective_action(positive_step)
    issues: list[str] = []
    if selection.signal_family == "fact_elicitation":
        if (selection.immediate_fact_gain or 0) <= 0:
            issues.append("source_grounding_missing_immediate_fact_gain")
        if _target_kind(positive_state, positive_action.target_id) != "client_fact":
            issues.append("source_grounding_positive_target_not_client_fact")
    elif selection.signal_family == "evidence_gap_identification":
        if (selection.immediate_gap_gain or 0) <= 0:
            issues.append("source_grounding_missing_immediate_evidence_gap_gain")
        if _target_kind(positive_state, positive_action.target_id) != "evidence_or_third_party":
            issues.append("source_grounding_positive_target_not_evidence_gap")
    elif selection.signal_family == "safe_stop":
        if positive_action.action_type not in {"final", "abstain"}:
            issues.append("source_grounding_positive_action_not_safe_stop")
    if issues:
        return None, sorted(set(issues))
    return (
        SourceForkWitness(
            group_id=group.group_id,
            case_id=positive.case_id,
            domain=positive.domain,
            divergence_turn=turn,
            visible_state_sha256=positive_state_hash,
            positive_trajectory_id=positive.trajectory_id,
            negative_trajectory_id=negative.trajectory_id,
            positive_action=_action_payload(positive_step),
            negative_action=_action_payload(negative_step),
            reward_gap=float(selection.reward_gap),
        ),
        [],
    )


def teacher_evidence_cluster_summaries(
    contrasts: list[
        tuple[AdvantageGroup, ContrastSelection, dict[str, ResearchTrajectory]]
    ],
) -> list[dict[str, Any]]:
    """Group strict causal forks into reusable behavioral hypotheses.

    A single same-state fork may nominate a domain-bounded provisional document;
    cross-domain support is required before the source evidence may nominate a
    general document.  Actual efficacy is never decided here: the next unseen
    block owns that decision.
    """

    clustered: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for group, selection, trajectories in contrasts:
        witness, issues = _source_fork(group, selection, trajectories)
        if witness is None or issues:
            continue
        positive = trajectories[selection.highest_id]
        negative = trajectories[selection.lowest_id]
        positive_step = next(
            item for item in positive.steps if item.turn == witness.divergence_turn
        )
        negative_step = next(
            item for item in negative.steps if item.turn == witness.divergence_turn
        )
        positive_action = _effective_action(positive_step)
        negative_action = _effective_action(negative_step)
        state = _execution_state(negative_step)
        family = _behavior_family(positive_step, negative_step)
        clustered[
            (
                selection.signal_family,
                negative_action.action_type,
                positive_action.action_type,
                family,
            )
        ].append(
            {
                "group_id": group.group_id,
                "case_id": positive.case_id,
                "domain": positive.domain,
                "persona": positive.persona,
                "reward_gap": float(selection.reward_gap or 0.0),
                "immediate_fact_gain": int(selection.immediate_fact_gain or 0),
                "fact_gain": int(selection.fact_gain or 0),
                "immediate_gap_gain": int(selection.immediate_gap_gain or 0),
                "gap_gain": int(selection.gap_gain or 0),
                "positive_target_kind": _target_kind(state, positive_action.target_id),
                "negative_target_kind": _target_kind(state, negative_action.target_id),
                "positive_target_label": next(
                    (
                        fact.label
                        for fact in state.facts
                        if fact.fact_id == positive_action.target_id
                    ),
                    None,
                ),
                "negative_target_label": next(
                    (
                        fact.label
                        for fact in state.facts
                        if fact.fact_id == negative_action.target_id
                    ),
                    None,
                ),
                "high_critical_unknown": state.high_critical_unknown_count > 0,
                "prior_unavailable": state.unavailable_turn_count > 0,
            }
        )

    summaries: list[dict[str, Any]] = []

    def summarize(
        key: tuple[str, str, str, str],
        members: list[dict[str, Any]],
        scope: str,
    ) -> dict[str, Any]:
        signal, negative_type, positive_type, family = key
        cases = sorted({str(item["case_id"]) for item in members})
        domains = sorted({str(item["domain"]) for item in members})
        eligible = len(domains) >= 2 if scope == "general" else bool(cases)
        base_id = f"{signal}__{negative_type}_to_{positive_type}__{family}"
        cluster_id = base_id if scope == "general" else f"{base_id}__scope_{scope}"
        critical_values = sorted({bool(item["high_critical_unknown"]) for item in members})
        unavailable_values = sorted({bool(item["prior_unavailable"]) for item in members})
        return {
            "cluster_id": cluster_id,
            "evidence_scope": scope,
            "signal_family": signal,
            "negative_action_type": negative_type,
            "positive_action_type": positive_type,
            "behavior_family": family,
            "teacher_expressible": True,
            "ineligible_reason": (
                None if eligible else "general_scope_requires_two_source_domains"
            ),
            "shared_visible_context": {
                "high_critical_unknown": (
                    critical_values[0] if len(critical_values) == 1 else None
                ),
                "prior_unavailable": (
                    unavailable_values[0] if len(unavailable_values) == 1 else None
                ),
                "observed_positive_target_kinds": sorted(
                    {
                        str(item["positive_target_kind"])
                        for item in members
                        if item["positive_target_kind"] is not None
                    }
                ),
                "observed_negative_target_kinds": sorted(
                    {
                        str(item["negative_target_kind"])
                        for item in members
                        if item["negative_target_kind"] is not None
                    }
                ),
                "positive_target_labels": sorted(
                    {
                        str(item["positive_target_label"])
                        for item in members
                        if item["positive_target_label"]
                    }
                )[:12],
                "negative_target_labels": sorted(
                    {
                        str(item["negative_target_label"])
                        for item in members
                        if item["negative_target_label"]
                    }
                )[:12],
            },
            "group_ids": sorted(str(item["group_id"]) for item in members),
            "source_case_ids": cases,
            "source_domains": domains,
            "source_personas": sorted({str(item["persona"]) for item in members}),
            "group_count": len(members),
            "source_case_count": len(cases),
            "source_domain_count": len(domains),
            "total_immediate_fact_gain": sum(
                int(item["immediate_fact_gain"]) for item in members
            ),
            "total_fact_gain": sum(int(item["fact_gain"]) for item in members),
            "total_immediate_gap_gain": sum(
                int(item["immediate_gap_gain"]) for item in members
            ),
            "total_gap_gain": sum(int(item["gap_gain"]) for item in members),
            "total_reward_gap": round(
                sum(float(item["reward_gap"]) for item in members), 6
            ),
            "positive_end_to_end_reward_gap_groups": sum(
                float(item["reward_gap"]) > 0 for item in members
            ),
            "eligible": eligible,
            "eligible_skill_scopes": [scope] if eligible else [],
        }

    for key, members in clustered.items():
        summaries.append(summarize(key, members, "general"))
        by_domain: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for member in members:
            by_domain[str(member["domain"])].append(member)
        for domain, domain_members in sorted(by_domain.items()):
            summaries.append(summarize(key, domain_members, domain))
    return sorted(
        summaries,
        key=lambda item: (
            not bool(item["eligible"]),
            -int(item["source_case_count"]),
            -int(item["source_domain_count"]),
            -int(item["group_count"]),
            -float(item["total_reward_gap"]),
            str(item["cluster_id"]),
        ),
    )


def select_teacher_evidence_clusters(
    clusters: list[dict[str, Any]],
    *,
    attempted_fingerprints: set[str],
    attempted_cluster_ids: set[str],
    budget: int,
) -> list[tuple[dict[str, Any], str]]:
    """Cover distinct behaviors before retrying a growing prior cluster."""

    if budget < 0:
        raise ValueError("teacher cluster budget must be non-negative")
    if budget == 0:
        return []
    selectable: list[tuple[dict[str, Any], str]] = []
    for cluster in clusters:
        if not bool(cluster.get("eligible")):
            continue
        fingerprint = canonical_json_sha256(
            {
                "cluster_id": cluster["cluster_id"],
                "group_ids": cluster["group_ids"],
            }
        )
        if fingerprint not in attempted_fingerprints:
            selectable.append((cluster, fingerprint))
    selectable.sort(
        key=lambda item: (
            str(item[0]["cluster_id"]) in attempted_cluster_ids,
            -int(item[0].get("source_case_count", 0)),
            -int(item[0].get("source_domain_count", 0)),
            -int(item[0].get("group_count", 0)),
            str(item[0]["cluster_id"]),
        )
    )

    def behavior_key(cluster: dict[str, Any]) -> tuple[object, ...]:
        explicit = (
            cluster.get("signal_family"),
            cluster.get("negative_action_type"),
            cluster.get("positive_action_type"),
            cluster.get("behavior_family", cluster.get("operation_family")),
        )
        if any(item is not None for item in explicit):
            return explicit
        return (str(cluster.get("cluster_id", "")).split("__scope_", 1)[0],)

    selected: list[tuple[dict[str, Any], str]] = []
    seen_behaviors: set[tuple[object, ...]] = set()
    seen_fingerprints: set[str] = set()
    for item in selectable:
        key = behavior_key(item[0])
        if key in seen_behaviors:
            continue
        selected.append(item)
        seen_behaviors.add(key)
        seen_fingerprints.add(item[1])
        if len(selected) == budget:
            return selected
    for item in selectable:
        if item[1] in seen_fingerprints:
            continue
        selected.append(item)
        if len(selected) == budget:
            break
    return selected


def candidate_context_scope_issues(
    candidate: SkillContract,
    evidence_cluster: dict[str, Any],
) -> list[str]:
    """Bind declared scope/objective to evidence without policing prose as code."""

    issues: list[str] = []
    eligible_scopes = [
        str(item) for item in evidence_cluster.get("eligible_skill_scopes", [])
    ]
    if not bool(evidence_cluster.get("eligible", bool(eligible_scopes))):
        issues.append("candidate_uses_ineligible_evidence_cluster")
    if eligible_scopes and candidate.domain not in eligible_scopes:
        issues.append(f"candidate_domain_not_allowed_by_evidence:{candidate.domain}")
    signal = evidence_cluster.get("signal_family")
    if signal is not None and candidate.objective != signal:
        issues.append(
            f"candidate_objective_mismatch:{candidate.objective}!={signal}"
        )
    provenance = candidate.provenance
    cluster_id = str(evidence_cluster.get("cluster_id") or "")
    if (
        provenance.source_evidence_cluster_id is not None
        and provenance.source_evidence_cluster_id != cluster_id
    ):
        issues.append("teacher_claimed_different_source_cluster")
    if (
        provenance.source_signal_family is not None
        and provenance.source_signal_family != signal
    ):
        issues.append("teacher_claimed_different_signal_family")
    return sorted(set(issues))


def candidate_source_grounding_issues(
    diagnosis: SkillDiagnosis,
    selection: ContrastSelection,
    trajectories: dict[str, ResearchTrajectory],
    *,
    failure_turn_override: int | None = None,
    existing_skills: list[SkillContract] | None = None,
) -> list[str]:
    """Verify source causality without mechanically executing the document."""

    del existing_skills
    candidate = diagnosis.candidate_skill
    if candidate is None:
        return []
    failure_turn = (
        failure_turn_override
        if failure_turn_override is not None
        else diagnosis.failure_state.turn
    )
    if failure_turn is None:
        return ["source_grounding_missing_divergence_turn"]
    if (
        selection.aligned_divergence_turn is None
        or failure_turn != selection.aligned_divergence_turn
    ):
        return ["source_grounding_failure_turn_not_aligned_divergence"]
    synthetic_group = AdvantageGroup(
        group_id=diagnosis.group_id,
        members=[],
        mean_reward=0.0,
        std_reward=0.0,
        informative=True,
    )
    witness, issues = _source_fork(synthetic_group, selection, trajectories)
    if witness is None:
        return issues
    if candidate.domain not in {"general", witness.domain}:
        issues.append("source_failure_domain_does_not_retrieve_skill")
    if candidate.objective != selection.signal_family:
        issues.append("source_failure_objective_mismatch")
    return sorted(set(issues))


def candidate_batch_source_grounding_issues(
    diagnosis: SkillDiagnosis,
    contrasts: list[
        tuple[AdvantageGroup, ContrastSelection, dict[str, ResearchTrajectory]]
    ],
    *,
    existing_skills: list[SkillContract] | None = None,
) -> tuple[list[str], list[str]]:
    """Require at least one system-verifiable source fork for a candidate."""

    del existing_skills
    if diagnosis.candidate_skill is None:
        return [], []
    supported: list[str] = []
    failures: list[str] = []
    for group, selection, trajectories in contrasts:
        issues = candidate_source_grounding_issues(
            diagnosis,
            selection,
            trajectories,
            failure_turn_override=selection.aligned_divergence_turn,
        )
        if issues:
            failures.append(f"{group.group_id}:{'|'.join(issues)}")
        else:
            supported.append(group.group_id)
    if supported:
        return [], supported
    issues = ["batch_source_support_cases:0<1"]
    issues.extend(f"batch_source_witness_failure:{item}" for item in failures[:3])
    return sorted(set(issues)), []


def _build_source_witness(
    *,
    evidence_cluster_id: str,
    signal_family: SignalFamily,
    contrasts: list[
        tuple[AdvantageGroup, ContrastSelection, dict[str, ResearchTrajectory]]
    ],
    supported_group_ids: list[str],
) -> SourceWitness | None:
    supported = set(supported_group_ids)
    forks: list[SourceForkWitness] = []
    for group, selection, trajectories in contrasts:
        if group.group_id not in supported:
            continue
        witness, issues = _source_fork(group, selection, trajectories)
        if witness is not None and not issues:
            forks.append(witness)
    if not forks:
        return None
    return SourceWitness(
        evidence_cluster_id=evidence_cluster_id,
        signal_family=signal_family,
        forks=forks,
    )


class SkillTeacher:
    def __init__(self, client: TeacherClient, prompt_path: Path) -> None:
        self.client = client
        self.prompt = (
            prompt_path.read_text(encoding="utf-8")
            .strip()
            .replace(
                "{allowed_skill_interface}",
                json.dumps(
                    skill_interface_catalog(), ensure_ascii=False, sort_keys=True
                ),
            )
        )

    @staticmethod
    def _teacher_trajectory(
        trajectory: ResearchTrajectory,
        focus_turn: int,
        *,
        include_state: bool,
    ) -> dict[str, Any]:
        step = next(item for item in trajectory.steps if item.turn == focus_turn)
        payload: dict[str, Any] = {
            "trajectory_id": trajectory.trajectory_id,
            "case_id": trajectory.case_id,
            "domain": trajectory.domain,
            "status": trajectory.status,
            "step": {
                "turn": step.turn,
                "action": _action_payload(step),
                "client_response_kind": step.client_response_kind,
                "client_selected_fact_ids": list(step.client_selected_fact_ids),
                "stop_gate_verdict": step.stop_gate_verdict,
                "policy_health_violations": list(step.policy_health_violations),
                "post_policy_health_violations": list(
                    step.post_skill_health_violations
                ),
            },
        }
        if include_state:
            payload["step"]["visible_state_before_action"] = (
                _compact_batch_teacher_state(_execution_state(step))
            )
        return payload

    def _system_prompt(
        self,
        *,
        existing_skills: list[SkillContract],
        prior_validation_feedback: list[dict[str, Any]],
        contrast_payload: dict[str, Any],
    ) -> str:
        return (
            self.prompt.replace(
                "{existing_skill_payload}",
                json.dumps(
                    [
                        {
                            "status": item.status,
                            "version": item.version,
                            **policy_skill_document(item),
                        }
                        for item in existing_skills
                    ],
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            )
            .replace(
                "{prior_validation_feedback_payload}",
                json.dumps(
                    prior_validation_feedback, ensure_ascii=False, sort_keys=True
                ),
            )
            .replace(
                "{contrast_payload}",
                json.dumps(contrast_payload, ensure_ascii=False, sort_keys=True),
            )
        )

    @staticmethod
    def _bind_candidate(
        *,
        candidate: SkillContract,
        response: TeacherResponse,
        evidence_cluster: dict[str, Any],
        contrasts: list[
            tuple[AdvantageGroup, ContrastSelection, dict[str, ResearchTrajectory]]
        ],
        supported_group_ids: list[str],
    ) -> SourceWitness | None:
        supported = set(supported_group_ids)
        candidate.status = "candidate"
        candidate.evaluation = SkillEvaluation()
        candidate.provenance.source = "tf_grpo"
        candidate.provenance.source_evidence_cluster_id = str(
            evidence_cluster["cluster_id"]
        )
        candidate.provenance.source_signal_family = evidence_cluster["signal_family"]
        candidate.provenance.generator_model = response.model
        candidate.provenance.diagnosis_hash = response.response_sha256
        candidate.provenance.source_case_ids = sorted(
            {
                trajectories[selection.highest_id].case_id
                for group, selection, trajectories in contrasts
                if group.group_id in supported
            }
        )
        candidate.provenance.source_trajectory_ids = list(
            dict.fromkeys(
                trajectory_id
                for group, selection, _ in contrasts
                if group.group_id in supported
                for trajectory_id in (selection.highest_id, selection.lowest_id)
            )
        )
        return _build_source_witness(
            evidence_cluster_id=str(evidence_cluster["cluster_id"]),
            signal_family=evidence_cluster["signal_family"],
            contrasts=contrasts,
            supported_group_ids=supported_group_ids,
        )

    def propose(
        self,
        *,
        group: AdvantageGroup,
        selection: ContrastSelection,
        trajectories: dict[str, ResearchTrajectory],
        evaluations: dict[str, TrajectoryEvaluation],
        existing_skills: list[SkillContract],
    ) -> TeacherProposal:
        """Compatibility entry point for one causal group."""

        del evaluations
        return self.propose_batch(
            batch_id=group.group_id,
            contrasts=[(group, selection, trajectories)],
            evaluations={},
            existing_skills=existing_skills,
            runtime_skills=[item for item in existing_skills if item.status == "active"],
            prior_validation_feedback=[],
            purpose="skill_teacher",
        )

    def propose_batch(
        self,
        *,
        batch_id: str,
        evidence_cluster_id: str | None = None,
        contrasts: list[
            tuple[AdvantageGroup, ContrastSelection, dict[str, ResearchTrajectory]]
        ],
        evaluations: dict[str, TrajectoryEvaluation],
        existing_skills: list[SkillContract],
        runtime_skills: list[SkillContract],
        prior_validation_feedback: list[dict[str, Any]] | None = None,
        purpose: str = "skill_teacher_batch",
    ) -> TeacherProposal:
        """Synthesize one document from exactly one eligible evidence cluster."""

        del evaluations
        if not contrasts:
            raise ValueError("batch teacher requires at least one causal contrast")
        clusters = teacher_evidence_cluster_summaries(contrasts)
        if evidence_cluster_id is None:
            clusters = [item for item in clusters if bool(item["eligible"])]
            if not clusters:
                raise ValueError("batch teacher has no eligible source evidence cluster")
            evidence_cluster = clusters[0]
        else:
            matching = [
                item for item in clusters if item["cluster_id"] == evidence_cluster_id
            ]
            if len(matching) != 1:
                raise ValueError(
                    "batch teacher evidence cluster selection did not resolve exactly once: "
                    f"{evidence_cluster_id}"
                )
            evidence_cluster = matching[0]
        group_ids = set(evidence_cluster["group_ids"])
        selected_contrasts = [
            item for item in contrasts if item[0].group_id in group_ids
        ]
        contrast_records: list[dict[str, Any]] = []
        for group, selection, trajectories in selected_contrasts:
            turn = selection.aligned_divergence_turn
            if turn is None:
                continue
            contrast_records.append(
                {
                    "group_id": group.group_id,
                    "selection": selection.model_dump(mode="json"),
                    "positive": self._teacher_trajectory(
                        trajectories[selection.highest_id], turn, include_state=False
                    ),
                    "negative": self._teacher_trajectory(
                        trajectories[selection.lowest_id], turn, include_state=True
                    ),
                }
            )
        payload = {
            "batch_id": batch_id,
            "selection_rule": (
                "Use exactly this eligible evidence cluster. Produce one coherent "
                "prompt-skill document or NOOP; unseen efficacy is not established here."
            ),
            "evidence_clusters": [
                {**evidence_cluster, "contrasts": contrast_records}
            ],
        }
        system = self._system_prompt(
            existing_skills=existing_skills,
            prior_validation_feedback=prior_validation_feedback or [],
            contrast_payload=payload,
        )
        response = self.client.generate_json(
            purpose=purpose,
            system_prompt=system,
            user_prompt=(
                f"只处理训练批{batch_id}给出的一个证据簇。非NOOP时，"
                "candidate_skill必须是一个自然语言咨询方法文档；group_id必须完全"
                "等于批ID，skill_scope必须等于candidate_skill.domain。"
            ),
            output_schema=strict_output_schema(TeacherDiagnosisDraft.model_json_schema()),
        )
        try:
            diagnosis = _materialize_teacher_diagnosis(
                TeacherDiagnosisDraft.model_validate(response.value)
            )
        except ValidationError as exc:
            return _schema_invalid_proposal(
                group_id=batch_id,
                response=response,
                error=exc,
            )
        issues = diagnosis_quality_issues(diagnosis)
        if diagnosis.group_id != batch_id:
            issues.append("group_id_mismatch")
        candidate = diagnosis.candidate_skill
        supported_group_ids: list[str] = []
        source_witness: SourceWitness | None = None
        if candidate is not None:
            issues.extend(candidate_context_scope_issues(candidate, evidence_cluster))
            issues.extend(validate_skill_static(candidate))
            grounding_issues, supported_group_ids = (
                candidate_batch_source_grounding_issues(
                    diagnosis,
                    selected_contrasts,
                    existing_skills=runtime_skills,
                )
            )
            issues.extend(grounding_issues)
            if not grounding_issues:
                source_witness = self._bind_candidate(
                    candidate=candidate,
                    response=response,
                    evidence_cluster=evidence_cluster,
                    contrasts=selected_contrasts,
                    supported_group_ids=supported_group_ids,
                )
                issues.extend(
                    candidate_overlap_issues(
                        candidate,
                        historical_skills=existing_skills,
                        runtime_skills=runtime_skills,
                    )
                )
        parse_status = (
            "noop"
            if diagnosis.proposed_change == "NOOP"
            else "invalid_candidate"
            if issues or candidate is None
            else "valid_candidate"
        )
        return TeacherProposal(
            group_id=batch_id,
            request_sha256=response.request_sha256,
            response_sha256=response.response_sha256,
            teacher_model=response.model,
            parse_status=parse_status,
            static_issues=sorted(set(issues)),
            source_group_ids=supported_group_ids,
            source_witness=source_witness,
            diagnosis=diagnosis,
        )
