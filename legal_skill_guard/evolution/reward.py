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
    # Backward-compatible default keeps historical fixtures interpretable.  The
    # formal LegalSkillEvolve config gives this deterministic policy endpoint the
    # largest weight because the paper's target is more disclosed facts per
    # question, not memo fluency alone.
    fact_efficiency_weight: float = Field(default=0.0, ge=0.0)
    extra_turn_penalty: float = Field(ge=0.0)
    repeated_question_penalty: float = Field(ge=0.0)
    premature_final_cap: float
    unsupported_claim_cap: float
    # Archived-schema compatibility only.  The active experiment does not
    # configure this retired cap and current execution cannot reach it.
    behavior_guard_cap: float = Field(default=0.25, ge=0.0)
    zero_inquiry_cap: float = Field(default=0.25, ge=0.0)
    hidden_field_leak_reward: float

    @model_validator(mode="after")
    def weights_sum_to_one(self) -> RewardParameters:
        total = (
            self.elicitation_weight
            + self.resolution_weight
            + self.fidelity_weight
            + self.fact_efficiency_weight
        )
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
    fact_efficiency: float = Field(default=0.0, ge=0.0, le=1.0)
    turns: int = Field(ge=0)
    repeated_question_rate: float = Field(ge=0.0, le=1.0)
    premature_final: bool = False
    unsupported_claim: bool = False
    # Archived-schema compatibility only; the current runner never emits this
    # outcome.  Keeping the cap makes historical evaluations reproducible without
    # reintroducing the retired control flow into current training.
    behavior_guard_terminated: bool = False
    no_substantive_inquiry: bool = False
    hidden_field_leak: bool = False


class RewardResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_reward: float
    cost_penalty: float
    uncapped_reward: float
    final_reward: float
    applied_caps: list[str]


def no_substantive_dialogue_inquiry(
    *, expected_inquiry_count: int, question_turns: int
) -> bool:
    """Return whether a case with an inquiry rubric received no lawyer question.

    DLawBench's semantic ``inquiry`` score measures whether the completed session
    satisfies its expected-inquiry rubric; a zero score does not mean that the
    lawyer asked zero questions.  The hard cap is an anti-no-inquiry safeguard,
    so it must be driven by the observed dialogue rather than by that semantic
    outcome.  Keeping this boundary explicit prevents a productive trajectory
    from being flattened to the same reward as an actually silent policy.
    """

    if expected_inquiry_count < 0 or question_turns < 0:
        raise ValueError("inquiry counts cannot be negative")
    return expected_inquiry_count > 0 and question_turns == 0


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
        + parameters.fact_efficiency_weight * value.fact_efficiency
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
    # Preserve archived reward interpretation without restoring the retired
    # control flow to current execution or formal reporting.
    if value.behavior_guard_terminated:
        reward = min(reward, parameters.behavior_guard_cap)
        caps.append("behavior_guard_cap")
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
