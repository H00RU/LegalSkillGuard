"""Structured teacher diagnoses and candidate-skill update proposals."""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from legal_skill_guard.agent.phase1_policy import _balanced_json_objects
from legal_skill_guard.schemas.skill import SkillContract

ProposalType = Literal["CREATE", "REFINE", "REPAIR", "MERGE", "SPLIT", "DEPRECATE", "NOOP"]


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

