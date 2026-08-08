"""Leakage-safe structured state for facts disclosed in the visible dialogue."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

FactStatus = Literal[
    "unknown", "client_claimed", "corroborated", "disputed", "irrelevant", "not_available"
]
Criticality = Literal["high", "medium", "low"]


class StateModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FactSlot(StateModel):
    fact_id: str
    label: str
    status: FactStatus = "unknown"
    value: str | None = None
    source_turns: list[int] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    criticality: Criticality = "medium"


class FactObservation(StateModel):
    fact_id: str
    label: str
    status: FactStatus
    value: str | None = None
    evidence_labels: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    criticality: Criticality = "medium"


class StatePatch(StateModel):
    observations: list[FactObservation] = Field(default_factory=list)
    issue_labels: list[str] = Field(default_factory=list)
    risk_flags_add: list[str] = Field(default_factory=list)


class Issue(StateModel):
    issue_id: str
    label: str
    status: Literal["candidate", "active", "resolved"] = "candidate"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    required_fact_ids: list[str] = Field(default_factory=list)


class Evidence(StateModel):
    evidence_id: str
    label: str
    availability: Literal["unknown", "claimed_available", "provided", "not_available"]
    supports: list[str] = Field(default_factory=list)


class Conflict(StateModel):
    fact_id: str
    prior_value: str | None
    new_value: str | None
    source_turns: list[int]


class ConsultationState(StateModel):
    session_id: str
    turn: int = Field(default=0, ge=0)
    domain: str = "general"
    persona: str = "unknown"
    max_turns: int = Field(default=6, ge=1)
    issues: list[Issue] = Field(default_factory=list)
    facts: list[FactSlot] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    asked_targets: list[str] = Field(default_factory=list)
    unresolved_conflicts: list[Conflict] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    candidate_action: dict[str, object] | None = None
    active_skills: list[str] = Field(default_factory=list)

    @computed_field
    @property
    def high_critical_unknown_count(self) -> int:
        return sum(f.criticality == "high" and f.status == "unknown" for f in self.facts)

    @computed_field
    @property
    def unresolved_conflict_count(self) -> int:
        return len(self.unresolved_conflicts)

    @computed_field
    @property
    def client_claimed_high_count(self) -> int:
        return sum(f.criticality == "high" and f.status == "client_claimed" for f in self.facts)

    @computed_field
    @property
    def corroborated_count(self) -> int:
        return sum(f.status == "corroborated" for f in self.facts)

    @computed_field
    @property
    def all_remaining_facts_not_available(self) -> bool:
        remaining = [f for f in self.facts if f.status in {"unknown", "not_available"}]
        return bool(remaining) and all(f.status == "not_available" for f in remaining)

    @computed_field
    @property
    def candidate_target_repeated(self) -> bool:
        target = (self.candidate_action or {}).get("target_id")
        return bool(target and target in self.asked_targets)

    @computed_field
    @property
    def candidate_target_unavailable(self) -> bool:
        target = (self.candidate_action or {}).get("target_id")
        return any(f.fact_id == target and f.status == "not_available" for f in self.facts)
