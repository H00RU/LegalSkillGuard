"""Training-pool trajectory reward with hard legal-safety caps."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RewardComponents(BaseModel):
    model_config = ConfigDict(extra="forbid")

    elicitation: float = Field(ge=0.0, le=1.0)
    resolution: float = Field(ge=0.0, le=1.0)
    fidelity: float = Field(ge=0.0, le=1.0)
    turns: int = Field(ge=0)
    repeated_question_rate: float = Field(ge=0.0, le=1.0)
    premature_final: bool = False
    unsupported_claim: bool = False
    hidden_field_leak: bool = False


class RewardResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_reward: float
    cost_penalty: float
    uncapped_reward: float
    final_reward: float
    applied_caps: list[str]


def proposed_final_was_redirected(step: Mapping[str, Any]) -> bool:
    """Detect a premature final from the pre-intervention action, not its rewrite."""

    proposed = step.get("proposed_action") or {}
    return (
        isinstance(proposed, Mapping)
        and proposed.get("action_type") == "final"
        and step.get("stop_gate_verdict") == "REDIRECT"
    )


def trajectory_reward(value: RewardComponents) -> RewardResult:
    base = 0.45 * value.elicitation + 0.45 * value.resolution + 0.10 * value.fidelity
    cost = 0.02 * max(value.turns - 1, 0) + 0.05 * value.repeated_question_rate
    uncapped = base - cost
    reward = uncapped
    caps: list[str] = []
    if value.premature_final:
        reward = min(reward, 0.35)
        caps.append("premature_final_cap")
    if value.unsupported_claim:
        reward = min(reward, 0.25)
        caps.append("unsupported_claim_cap")
    if value.hidden_field_leak:
        reward = 0.0
        caps.append("hidden_field_leak_zero")
    return RewardResult(
        base_reward=round(base, 6),
        cost_penalty=round(cost, 6),
        uncapped_reward=round(uncapped, 6),
        final_reward=round(max(reward, 0.0), 6),
        applied_caps=caps,
    )
