"""Structured teacher diagnoses and prompt-skill document proposals."""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from legal_skill_guard.agent.action_parser import _balanced_json_objects
from legal_skill_guard.schemas.skill import SkillContract, SkillDocumentDraft

# The current executor stages a new immutable prompt document or stages nothing.
# Lifecycle operations require an explicit base-document identity and different
# activation semantics; advertising them here while treating every non-NOOP value
# as CREATE would make the audit trail false.
ProposalType = Literal["CREATE", "NOOP"]


class DiagnosisModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FailureState(DiagnosisModel):
    turn: int | None = None
    relevant_fields: list[str] = Field(default_factory=list)


class BehaviorDifference(DiagnosisModel):
    positive_action: str
    negative_action: str


class SkillDiagnosis(DiagnosisModel):
    group_id: str
    failure_state: FailureState
    behavior_difference: BehaviorDifference
    causal_hypothesis: str
    proposed_change: ProposalType
    skill_scope: str
    known_risks: list[str] = Field(default_factory=list)
    candidate_skill: SkillContract | None = None


class TeacherDiagnosisDraft(DiagnosisModel):
    """Structured-output contract containing only fields the teacher may author."""

    group_id: str
    failure_state: FailureState
    behavior_difference: BehaviorDifference
    causal_hypothesis: str
    proposed_change: ProposalType
    skill_scope: str
    known_risks: list[str] = Field(default_factory=list)
    candidate_skill: SkillDocumentDraft | None = None


def diagnosis_quality_issues(diagnosis: SkillDiagnosis) -> list[str]:
    """Check proposal completeness without pretending to judge unseen efficacy."""

    issues: list[str] = []
    placeholders = {"高分轨迹行为", "低分轨迹行为", "positive action", "negative action"}
    if diagnosis.proposed_change == "NOOP":
        if diagnosis.candidate_skill is not None:
            issues.append("noop_contains_candidate")
        return issues
    if diagnosis.candidate_skill is None:
        issues.append("non_noop_missing_candidate")
    positive = diagnosis.behavior_difference.positive_action.strip().lower()
    negative = diagnosis.behavior_difference.negative_action.strip().lower()
    if positive in placeholders or negative in placeholders:
        issues.append("placeholder_behavior_difference")
    if positive == negative or len(positive) < 8 or len(negative) < 8:
        issues.append("non_specific_behavior_difference")
    if diagnosis.failure_state.turn is None:
        issues.append("missing_failure_turn")
    if len(diagnosis.causal_hypothesis.strip()) < 12:
        issues.append("non_specific_causal_hypothesis")
    skill = diagnosis.candidate_skill
    if skill is not None and diagnosis.skill_scope != skill.domain:
        issues.append("diagnosis_skill_scope_mismatch")
    return sorted(set(issues))


def parse_diagnosis(text: str, group_id: str) -> tuple[SkillDiagnosis, str]:
    raw = text.strip()
    for index, candidate in enumerate([raw, *_balanced_json_objects(raw)]):
        try:
            value = json.loads(candidate)
            value.setdefault("group_id", group_id)
            return SkillDiagnosis.model_validate(value), "json" if index == 0 else "json_fragment"
        except (json.JSONDecodeError, ValueError):
            continue
    return (
        SkillDiagnosis(
            group_id=group_id,
            failure_state=FailureState(),
            behavior_difference=BehaviorDifference(
                positive_action="unparsed", negative_action="unparsed"
            ),
            causal_hypothesis="Teacher output could not be validated; no update is allowed.",
            proposed_change="NOOP",
            skill_scope="general",
            known_risks=["invalid_teacher_output"],
        ),
        "fallback_noop",
    )
