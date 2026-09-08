"""Training-pool trajectory reward with hard legal-safety caps."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RewardParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    elicitation_weight: float = Field(ge=0.0)
    resolution_weight: float = Field(ge=0.0)
    fidelity_weight: float = Field(ge=0.0)
    extra_turn_penalty: float = Field(ge=0.0)
    repeated_question_penalty: float = Field(ge=0.0)
    premature_final_cap: float
    unsupported_claim_cap: float
    zero_inquiry_cap: float = Field(default=0.25, ge=0.0)
    hidden_field_leak_reward: float

    @model_validator(mode="after")
    def weights_sum_to_one(self) -> RewardParameters:
        total = self.elicitation_weight + self.resolution_weight + self.fidelity_weight
        if abs(total - 1.0) > 1.0e-9:
            raise ValueError(f"reward weights must sum to 1.0, got {total}")
        return self


class RewardComponents(BaseModel):
    model_config = ConfigDict(extra="forbid")

    elicitation: float = Field(ge=0.0, le=1.0)
    resolution: float = Field(ge=0.0, le=1.0)
    # The pinned DLawBench evaluator computes
    # ``(total_claims - len(ungrounded_claims)) / total_claims``.  Its LLM
    # judge can return an inconsistent count (more ungrounded items than
    # total claims), so the official metric can be negative.  Preserve that
    # penalty instead of clipping or silently discarding the trajectory.
    fidelity: float = Field(le=1.0)
    turns: int = Field(ge=0)
    repeated_question_rate: float = Field(ge=0.0, le=1.0)
    premature_final: bool = False
    unsupported_claim: bool = False
    no_substantive_inquiry: bool = False
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


def trajectory_reward(value: RewardComponents, parameters: RewardParameters) -> RewardResult:
    base = (
        parameters.elicitation_weight * value.elicitation
        + parameters.resolution_weight * value.resolution
        + parameters.fidelity_weight * value.fidelity
    )
    cost = (
        parameters.extra_turn_penalty * max(value.turns - 1, 0)
        + parameters.repeated_question_penalty * value.repeated_question_rate
    )
    uncapped = base - cost
    reward = uncapped
    caps: list[str] = []
    if value.premature_final:
        reward = min(reward, parameters.premature_final_cap)
        caps.append("premature_final_cap")
    if value.unsupported_claim:
        reward = min(reward, parameters.unsupported_claim_cap)
        caps.append("unsupported_claim_cap")
    if value.no_substantive_inquiry:
        reward = min(reward, parameters.zero_inquiry_cap)
        caps.append("zero_inquiry_cap")
    if value.hidden_field_leak:
        reward = parameters.hidden_field_leak_reward
        caps.append("hidden_field_leak_zero")
    return RewardResult(
        base_reward=round(base, 6),
        cost_penalty=round(cost, 6),
        uncapped_reward=round(uncapped, 6),
        final_reward=round(max(reward, 0.0), 6),
        applied_caps=caps,
    )


def balanced_elicitation(fact_coverage: float, inquiry: float) -> float:
    """Require both memo discovery and substantive inquiry for training reward.

    DLawBench's reported elicitation remains the official arithmetic mean.  The
    evolution signal uses the harmonic mean so a rich opening copied into a memo
    cannot substitute for asking any expected question.
    """

    if min(fact_coverage, inquiry) <= 0:
        return 0.0
    return 2 * fact_coverage * inquiry / (fact_coverage + inquiry)
