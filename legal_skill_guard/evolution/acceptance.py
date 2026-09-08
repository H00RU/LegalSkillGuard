"""Paired skill audit decision state machine and global regression gate."""

from __future__ import annotations

import statistics
from collections import defaultdict
from math import ceil
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Decision = Literal["ACCEPT", "REJECT", "DEFER"]
SignalFamily = Literal["fact_elicitation", "evidence_gap_identification", "safe_stop"]


class PairOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pair_id: str
    case_id: str = ""
    domain: str = "general"
    exposed: bool
    reward_without: float
    reward_with: float
    # ``reward_with`` is the paired-consistent reward used for the decision.
    # Keep the independently judged value so every monotonicity reconciliation
    # remains visible in the audit instead of silently rewriting an evaluation.
    raw_reward_with: float | None = None
    paired_inquiry_inherited_indices: list[int] = Field(default_factory=list)
    severe_risk_with: bool = False
    unsupported_claim_delta: float = 0.0
    premature_final_delta: float = 0.0
    belief_as_fact_delta: float = 0.0
    repeated_question_delta: float = 0.0
    critical_fact_recall_delta: float = 0.0
    policy_fallback_delta: float = 0.0
    client_fallback_delta: float = 0.0
    memo_fallback_delta: float = 0.0
    newly_elicited_fact_delta: float = 0.0
    identified_evidence_gap_delta: float = 0.0
    question_turn_delta: float = 0.0

    @property
    def delta(self) -> float:
        return self.reward_with - self.reward_without


class AcceptanceThresholds(BaseModel):
    model_config = ConfigDict(extra="forbid")
    minimum_exposed_pairs: int = Field(ge=1)
    minimum_exposed_cases: int = Field(ge=1)
    minimum_exposed_domains: int = Field(ge=1)
    minimum_mean_delta: float
    minimum_material_harm_delta: float = Field(ge=0.0)
    maximum_harmful_pair_rate: float = Field(ge=0.0, le=1.0)


class AuditDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Decision
    reason: str
    pairs: int
    exposed_pairs: int
    exposed_cases: int
    exposed_domains: int
    mean_delta_reward: float
    median_delta_reward: float
    material_harm_delta_threshold: float = 0.0
    harmful_pair_rate: float
    severe_risk_count: int
    unsupported_claim_delta: float
    premature_final_delta: float
    belief_as_fact_delta: float
    repeated_question_delta: float
    critical_fact_recall_delta: float
    policy_fallback_delta: float
    client_fallback_delta: float
    memo_fallback_delta: float


class MechanismDirectionGate(BaseModel):
    """Held-out direction check for the mechanism claimed by source contrasts.

    This is not another weighted reward.  It asks whether a candidate that passed
    the existing paired reward/safety gate also moves its claimed observable
    mechanism in the expected direction without sacrificing the other information
    channel.  Persona repetitions are collapsed to case means, just as in the main
    acceptance decision.
    """

    model_config = ConfigDict(extra="forbid")
    signal_family: SignalFamily
    exposed_cases: int = Field(ge=0)
    mean_newly_elicited_fact_delta: float
    mean_identified_evidence_gap_delta: float
    mean_question_turn_delta: float
    passed: bool
    reason: str


def mechanism_direction_gate(
    outcomes: list[PairOutcome], signal_family: SignalFamily
) -> MechanismDirectionGate:
    exposed = [item for item in outcomes if item.exposed]
    by_case: dict[str, list[PairOutcome]] = defaultdict(list)
    for outcome in exposed:
        by_case[outcome.case_id or outcome.pair_id].append(outcome)

    def case_cluster_mean(field: str) -> float:
        if not by_case:
            return 0.0
        return statistics.fmean(
            statistics.fmean(float(getattr(item, field)) for item in rows)
            for rows in by_case.values()
        )

    fact_delta = case_cluster_mean("newly_elicited_fact_delta")
    gap_delta = case_cluster_mean("identified_evidence_gap_delta")
    question_delta = case_cluster_mean("question_turn_delta")
    if not by_case:
        passed = False
        reason = "not_evaluable_no_exposed_case"
    elif signal_family == "fact_elicitation":
        # Source selection deliberately admits two fact-elicitation mechanisms:
        # durable extra coverage, and earlier/more efficient acquisition of the
        # same eventual facts.  The held-out gate must preserve that definition.
        # Requiring strictly more final facts rejected a real paired improvement
        # that obtained the same fact with one fewer question, even though the
        # source evidence and reward both explicitly treat that as useful.
        durable_gain = fact_delta > 0 and gap_delta >= 0
        efficient_gain = fact_delta >= 0 and gap_delta >= 0 and question_delta < 0
        passed = durable_gain or efficient_gain
        reason = (
            "fact_gain_positive_without_gap_regression"
            if durable_gain
            else "fact_efficiency_positive_without_information_regression"
            if efficient_gain
            else "claimed_fact_mechanism_not_reproduced"
        )
    elif signal_family == "evidence_gap_identification":
        passed = gap_delta > 0 and fact_delta >= 0
        reason = (
            "gap_gain_positive_without_fact_regression"
            if passed
            else "claimed_evidence_gap_mechanism_not_reproduced"
        )
    else:
        passed = question_delta < 0 and fact_delta >= 0 and gap_delta >= 0
        reason = (
            "question_reduction_without_information_regression"
            if passed
            else "claimed_safe_stop_mechanism_not_reproduced"
        )
    return MechanismDirectionGate(
        signal_family=signal_family,
        exposed_cases=len(by_case),
        mean_newly_elicited_fact_delta=round(fact_delta, 6),
        mean_identified_evidence_gap_delta=round(gap_delta, 6),
        mean_question_turn_delta=round(question_delta, 6),
        passed=passed,
        reason=reason,
    )


def decide_skill(outcomes: list[PairOutcome], thresholds: AcceptanceThresholds) -> AuditDecision:
    limits = thresholds
    exposed = [outcome for outcome in outcomes if outcome.exposed]
    by_case: dict[str, list[PairOutcome]] = defaultdict(list)
    for outcome in exposed:
        by_case[outcome.case_id or outcome.pair_id].append(outcome)
    deltas = [statistics.fmean(item.delta for item in rows) for rows in by_case.values()]
    domains = {item.domain for item in exposed}

    def clustered_mean(field: str) -> float:
        if not by_case:
            return 0.0
        return statistics.fmean(
            statistics.fmean(float(getattr(item, field)) for item in rows)
            for rows in by_case.values()
        )

    mean = statistics.fmean(deltas) if deltas else 0.0
    median = statistics.median(deltas) if deltas else 0.0
    # A bounded composite reward is not measured with infinite precision: judge
    # discretisation and one changed low-weight rubric item can create tiny paired
    # differences that are not practically harmful.  Count only case-clustered
    # drops beyond the predeclared material-harm margin.  Safety regressions remain
    # separate zero-tolerance gates below and are never absorbed by this margin.
    harmful = (
        sum(delta < -limits.minimum_material_harm_delta for delta in deltas) / len(deltas)
        if deltas
        else 0.0
    )
    severe = sum(outcome.severe_risk_with for outcome in exposed)
    unsupported = clustered_mean("unsupported_claim_delta")
    premature = clustered_mean("premature_final_delta")
    belief_as_fact = clustered_mean("belief_as_fact_delta")
    repeated = clustered_mean("repeated_question_delta")
    critical_recall = clustered_mean("critical_fact_recall_delta")
    policy_fallback = clustered_mean("policy_fallback_delta")
    client_fallback = clustered_mean("client_fallback_delta")
    memo_fallback = clustered_mean("memo_fallback_delta")
    # These fields are legal-safety and execution-integrity gates, not symmetric
    # optimization targets.  A regression in one paired observation cannot be
    # cancelled by an improvement in another case.  Keep the clustered means above
    # for transparent reporting, but apply the predeclared zero-tolerance decision
    # to every exposed pair independently.
    safety_regression = any(
        item.unsupported_claim_delta > 0
        or item.premature_final_delta > 0
        or item.belief_as_fact_delta > 0
        or item.repeated_question_delta > 0
        or item.critical_fact_recall_delta < 0
        or item.policy_fallback_delta > 0
        or item.client_fallback_delta > 0
        or item.memo_fallback_delta > 0
        for item in exposed
    )
    harmful_count = sum(
        delta < -limits.minimum_material_harm_delta for delta in deltas
    )
    # Safety evidence is directional even when exposure coverage is sparse. A
    # single non-safety composite loss is different: with four exposed cases,
    # one loss mechanically estimates a 25% tail and can never satisfy a 15%
    # limit. Carry that net-positive candidate to the next unseen block until the
    # denominator can represent one tolerated loss; do not either activate it or
    # permanently reject it from one discrete observation.
    one_harm_minimum_denominator = (
        ceil(1.0 / limits.maximum_harmful_pair_rate)
        if limits.maximum_harmful_pair_rate > 0
        else 0
    )
    if severe > 0 or (exposed and mean <= 0):
        decision, reason = "REJECT", "severe_risk_or_nonpositive_mean"
    elif safety_regression:
        decision, reason = "REJECT", "positive_mean_but_risk_or_harmful_tail"
    elif harmful > limits.maximum_harmful_pair_rate:
        if (
            harmful_count == 1
            and len(deltas) < one_harm_minimum_denominator
        ):
            decision, reason = (
                "DEFER",
                "single_nonsafety_harm_requires_more_unseen_evidence",
            )
        else:
            decision, reason = "REJECT", "positive_mean_but_risk_or_harmful_tail"
    elif (
        len(exposed) < limits.minimum_exposed_pairs
        or len(by_case) < limits.minimum_exposed_cases
        or len(domains) < limits.minimum_exposed_domains
    ):
        # Domain assignment is fixed before outcomes.  Sparse exposure therefore
        # means the immediately next block contained too few applicable cases;
        # carry the candidate forward within the bounded validation horizon.
        decision, reason = "DEFER", "insufficient_independent_exposure_coverage"
    elif mean < limits.minimum_mean_delta:
        decision, reason = "REJECT", "positive_but_below_effect_threshold"
    else:
        decision, reason = "ACCEPT", "all_acceptance_constraints_satisfied"
    return AuditDecision(
        decision=decision,
        reason=reason,
        pairs=len(outcomes),
        exposed_pairs=len(exposed),
        exposed_cases=len(by_case),
        exposed_domains=len(domains),
        mean_delta_reward=round(mean, 6),
        median_delta_reward=round(median, 6),
        material_harm_delta_threshold=round(limits.minimum_material_harm_delta, 6),
        harmful_pair_rate=round(harmful, 6),
        severe_risk_count=severe,
        unsupported_claim_delta=round(unsupported, 6),
        premature_final_delta=round(premature, 6),
        belief_as_fact_delta=round(belief_as_fact, 6),
        repeated_question_delta=round(repeated, 6),
        critical_fact_recall_delta=round(critical_recall, 6),
        policy_fallback_delta=round(policy_fallback, 6),
        client_fallback_delta=round(client_fallback, 6),
        memo_fallback_delta=round(memo_fallback, 6),
    )


def global_regression_passes(
    baseline_reward: float, candidate_reward: float, *, maximum_drop: float
) -> bool:
    return candidate_reward >= baseline_reward - maximum_drop
