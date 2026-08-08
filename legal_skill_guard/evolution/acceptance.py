"""Paired skill audit decision state machine and global regression gate."""

from __future__ import annotations

import statistics
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Decision = Literal["ACCEPT", "REJECT", "DEFER", "REPAIR"]


class PairOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pair_id: str
    triggered: bool
    reward_without: float
    reward_with: float
    severe_risk_with: bool = False
    unsupported_claim_delta: float = 0.0
    premature_final_delta: float = 0.0

    @property
    def delta(self) -> float:
        return self.reward_with - self.reward_without


class AcceptanceThresholds(BaseModel):
    model_config = ConfigDict(extra="forbid")
    minimum_triggered_pairs: int = Field(default=10, ge=1)
    minimum_mean_delta: float = 0.02
    maximum_harmful_pair_rate: float = Field(default=0.15, ge=0.0, le=1.0)


class AuditDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Decision
    reason: str
    pairs: int
    triggered_pairs: int
    mean_delta_reward: float
    median_delta_reward: float
    harmful_pair_rate: float
    severe_risk_count: int
    unsupported_claim_delta: float
    premature_final_delta: float


def decide_skill(
    outcomes: list[PairOutcome], thresholds: AcceptanceThresholds | None = None
) -> AuditDecision:
    limits = thresholds or AcceptanceThresholds()
    triggered = [outcome for outcome in outcomes if outcome.triggered]
    deltas = [outcome.delta for outcome in triggered]
    mean = statistics.fmean(deltas) if deltas else 0.0
    median = statistics.median(deltas) if deltas else 0.0
    harmful = sum(delta < 0 for delta in deltas) / len(deltas) if deltas else 0.0
    severe = sum(outcome.severe_risk_with for outcome in triggered)
    unsupported = statistics.fmean(
        [outcome.unsupported_claim_delta for outcome in triggered]
    ) if triggered else 0.0
    premature = statistics.fmean(
        [outcome.premature_final_delta for outcome in triggered]
    ) if triggered else 0.0
    if len(triggered) < limits.minimum_triggered_pairs:
        decision, reason = "DEFER", "insufficient_triggered_pairs"
    elif severe > 0 or mean <= 0:
        decision, reason = "REJECT", "severe_risk_or_nonpositive_mean"
    elif harmful > limits.maximum_harmful_pair_rate or unsupported > 0 or premature > 0:
        decision, reason = "REPAIR", "positive_mean_but_risk_or_harmful_tail"
    elif mean < limits.minimum_mean_delta:
        decision, reason = "DEFER", "positive_but_below_effect_threshold"
    else:
        decision, reason = "ACCEPT", "all_acceptance_constraints_satisfied"
    return AuditDecision(
        decision=decision,
        reason=reason,
        pairs=len(outcomes),
        triggered_pairs=len(triggered),
        mean_delta_reward=round(mean, 6),
        median_delta_reward=round(median, 6),
        harmful_pair_rate=round(harmful, 6),
        severe_risk_count=severe,
        unsupported_claim_delta=round(unsupported, 6),
        premature_final_delta=round(premature, 6),
    )


def global_regression_passes(
    baseline_reward: float, candidate_reward: float, maximum_drop: float = 0.01
) -> bool:
    return candidate_reward >= baseline_reward - maximum_drop

