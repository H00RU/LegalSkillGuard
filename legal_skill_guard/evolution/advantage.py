"""TF-GRPO group-relative advantage and contrast selection."""

from __future__ import annotations

import statistics

from pydantic import BaseModel, ConfigDict


class ScoredMember(BaseModel):
    model_config = ConfigDict(extra="forbid")
    trajectory_id: str
    reward: float
    premature_final: bool = False
    unsupported_claim: bool = False
    turns: int = 0
    advantage: float | None = None


class AdvantageGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")
    group_id: str
    members: list[ScoredMember]
    mean_reward: float
    std_reward: float
    informative: bool
    skip_reason: str | None = None


class ContrastSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    highest_id: str
    lowest_id: str
    safety_failure_id: str | None = None
    efficient_failure_id: str | None = None


def compute_advantages(
    group_id: str, members: list[ScoredMember], epsilon: float = 1.0e-8
) -> AdvantageGroup:
    if len(members) < 2:
        raise ValueError("A trajectory group requires at least two members")
    rewards = [member.reward for member in members]
    mean = statistics.fmean(rewards)
    std = statistics.pstdev(rewards)
    informative = std > epsilon
    updated = [member.model_copy(deep=True) for member in members]
    if informative:
        for member in updated:
            member.advantage = round((member.reward - mean) / (std + epsilon), 6)
    return AdvantageGroup(
        group_id=group_id,
        members=updated,
        mean_reward=round(mean, 6),
        std_reward=round(std, 6),
        informative=informative,
        skip_reason=None if informative else "low_variance_group",
    )


def select_contrasts(group: AdvantageGroup) -> ContrastSelection:
    if not group.informative:
        raise ValueError("Cannot select contrasts from an uninformative group")
    ordered = sorted(group.members, key=lambda member: (member.reward, member.trajectory_id))
    safety = next(
        (
            member.trajectory_id
            for member in reversed(ordered)
            if member.premature_final or member.unsupported_claim
        ),
        None,
    )
    efficient = min(ordered, key=lambda member: (member.turns, member.reward)).trajectory_id
    return ContrastSelection(
        highest_id=ordered[-1].trajectory_id,
        lowest_id=ordered[0].trajectory_id,
        safety_failure_id=safety,
        efficient_failure_id=efficient,
    )

