"""Structured consultation actions shared by the skill and verifier layers."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ActionType = Literal["ask", "clarify", "verify", "retrieve", "summarize", "final", "abstain"]
TargetType = Literal["fact", "issue", "evidence", "law", "session", "none"]


class StructuredAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_type: ActionType
    target_type: TargetType = "none"
    target_id: str | None = None
    reason: str = ""
    expected_information: str = ""
    content: str = ""
    constraints: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class ActionDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    original: StructuredAction
    final: StructuredAction
    retrieved_skill_ids: list[str] = Field(default_factory=list)
    activated_skill_ids: list[str] = Field(default_factory=list)
    blocked_skill_ids: list[str] = Field(default_factory=list)
    changes: list[dict[str, object]] = Field(default_factory=list)

