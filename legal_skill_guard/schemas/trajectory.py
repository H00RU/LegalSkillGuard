"""Phase 1 trajectory records; later phases extend, rather than replace, this contract."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Message(StrictModel):
    role: Literal["system", "user", "assistant"]
    content: str


class Action(StrictModel):
    tool: Literal["talk_to_client", "write_memo"]
    content: str
    parse_mode: Literal["json", "json_fragment", "fallback"]
    raw_model_output: str


class TokenUsage(StrictModel):
    prompt: int = 0
    completion: int = 0

    @property
    def total(self) -> int:
        return self.prompt + self.completion


class TrajectoryStep(StrictModel):
    turn: int = Field(ge=0)
    visible_input: list[Message]
    state_before: dict[str, Any] = Field(default_factory=dict)
    proposed_action: Action
    retrieved_skill_ids: list[str] = Field(default_factory=list)
    activated_skill_ids: list[str] = Field(default_factory=list)
    action_after_skills: Action
    rendered_question: str | None = None
    client_response: str | None = None
    client_input_sha256: str | None = None
    state_patch: dict[str, Any] = Field(default_factory=dict)
    state_after: dict[str, Any] = Field(default_factory=dict)
    verifier_results: list[dict[str, Any]] = Field(default_factory=list)
    latency_ms: int = Field(ge=0)
    token_usage: TokenUsage
    lawyer_finish_reason: str | None = None
    client_finish_reason: str | None = None


class Trajectory(StrictModel):
    schema_version: int = 1
    trajectory_id: str
    run_id: str
    method: Literal["B0_direct", "B1_prompted_multiturn"]
    case_id: str
    jurisdiction: Literal["CN"]
    persona: str
    seed: int
    model_id: str
    model_revision: str
    status: Literal["memo_submitted", "max_turns_forced_memo", "error"]
    opening: str
    max_turns: int
    steps: list[TrajectoryStep]
    memo: str
    elapsed_seconds: float = Field(ge=0)
    created_at: datetime
    error: str | None = None

    @property
    def token_usage(self) -> TokenUsage:
        return TokenUsage(
            prompt=sum(step.token_usage.prompt for step in self.steps),
            completion=sum(step.token_usage.completion for step in self.steps),
        )
