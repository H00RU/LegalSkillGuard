"""Trajectory contract for stateful skill and evolution experiments."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from legal_skill_guard.schemas.action import ActionDecision, StructuredAction
from legal_skill_guard.schemas.state import StatePatch
from legal_skill_guard.schemas.trajectory import Message, TokenUsage
from legal_skill_guard.verifiers.deterministic import VerificationResult


class ExperimentModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PolicyEnvelope(ExperimentModel):
    state_patch: StatePatch = Field(default_factory=StatePatch)
    action: StructuredAction


class ResearchStep(ExperimentModel):
    turn: int = Field(ge=1)
    visible_input: list[Message]
    state_before: dict[str, object]
    state_patch: StatePatch
    state_after: dict[str, object]
    raw_policy_output: str
    parse_mode: Literal["json", "json_fragment", "fallback"]
    proposed_action: StructuredAction
    action_decision: ActionDecision
    rendered_question: str | None = None
    client_response: str | None = None
    client_input_sha256: str | None = None
    verifier_results: list[VerificationResult] = Field(default_factory=list)
    stop_gate_verdict: str
    stop_gate_reason: str
    token_usage: TokenUsage
    lawyer_finish_reason: str | None = None
    client_finish_reason: str | None = None


class ResearchTrajectory(ExperimentModel):
    schema_version: int = 2
    trajectory_id: str
    group_id: str | None = None
    sample_index: int = 0
    run_id: str
    method: Literal[
        "B2_static_text_skills",
        "B3_static_executable_skills",
        "B5_tfgrpo_no_gate",
        "Ours_legal_skill_guard",
    ]
    partition: str
    case_id: str
    jurisdiction: Literal["CN"] = "CN"
    persona: str
    seed: int
    model_id: str
    model_revision: str
    skill_library_version: str
    status: Literal["memo_submitted", "abstained", "max_turns_forced_memo", "error"]
    opening: str
    max_turns: int
    steps: list[ResearchStep]
    memo: str
    elapsed_seconds: float = Field(ge=0)
    created_at: datetime
    error: str | None = None

