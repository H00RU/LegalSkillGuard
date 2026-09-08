"""Leakage-safe structured state for facts disclosed in the visible dialogue."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

FactStatus = Literal[
    "unknown", "client_claimed", "corroborated", "disputed", "irrelevant", "not_available"
]
Criticality = Literal["high", "medium", "low"]
TargetKind = Literal["client_fact", "evidence_or_third_party"]
TARGET_KINDS = frozenset({"client_fact", "evidence_or_third_party"})
DisclosureDecision = Literal["disclose", "withhold"]
ClientResponseKind = Literal[
    "new_hidden_fact",
    "repeated_hidden_fact",
    "opening_repeat",
    "withheld",
    "unavailable",
    "contract_fallback",
]


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
    # ``client_fact`` is an ordinary dialogue target that the client may answer
    # from experience, communication or an already-seen document.  An
    # ``evidence_or_third_party`` target is still a legally useful inquiry, but its
    # answer may require a later record request, expert examination or third-party
    # verification.  Keeping the distinction in state prevents a correct legal
    # evidence question from being mistaken for a failed fact-elicitation action.
    # ``None`` exists only so historical artifacts written before protocol 15 can
    # still be parsed for an explicit compatibility audit.  Current trajectories
    # must carry an authored kind and are rejected by the trajectory-health gate
    # when this field is absent; never infer ``client_fact`` from omission.
    target_kind: TargetKind | None = None


class FactObservation(StateModel):
    fact_id: str
    label: str
    status: FactStatus
    value: str | None = None
    evidence_labels: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    criticality: Criticality = "medium"
    target_kind: TargetKind | None = None


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


class Interaction(StateModel):
    turn: int
    action_type: Literal["ask", "clarify", "verify", "summarize"]
    target_id: str | None = None
    question: str
    response_kind: ClientResponseKind | None = None
    new_information: bool = False
    disclosed_fact_ids: list[str] = Field(default_factory=list)
    covered_target_ids: list[str] = Field(default_factory=list)


_KNOWN_TARGET_STOP_PHRASES = (
    "客户",
    "您",
    "我方",
    "我司",
    "是否",
    "有无",
    "目前",
    "当前",
    "已经",
    "实际",
    "具体",
    "曾经",
    "曾",
    "进行过",
    "进行",
    "就",
    "明确",
    "相关",
    "情况",
)


def _semantic_fact_text(value: str) -> str:
    normalized = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", value).lower()
    for phrase in _KNOWN_TARGET_STOP_PHRASES:
        normalized = normalized.replace(phrase, "")
    return normalized


def _character_bigrams(value: str) -> set[str]:
    return {value[index : index + 2] for index in range(max(0, len(value) - 1))}


def candidate_action_targets_known_fact(facts: list[FactSlot], action: dict[str, object]) -> bool:
    """Conservatively expose a semantically repeated visible fact to learned skills.

    Exact IDs remain authoritative.  The lexical branch only detects high-overlap
    paraphrases against values already stated in the visible dialogue; it neither
    imports hidden facts nor blocks an action by itself.  Candidate skills must still
    survive paired acceptance before this feature can change the active policy.
    """

    if action.get("action_type") != "ask":
        return False
    target = action.get("target_id")
    if any(
        fact.fact_id == target
        and fact.status in {"client_claimed", "corroborated", "disputed"}
        and bool(fact.value)
        for fact in facts
    ):
        return True
    target_fact = next((fact for fact in facts if fact.fact_id == target), None)
    raw_target = str(
        (target_fact.label if target_fact is not None else "")
        or action.get("expected_information")
        or action.get("content")
        or ""
    )
    normalized_target = _semantic_fact_text(raw_target)
    if len(normalized_target) < 4:
        return False
    target_bigrams = _character_bigrams(normalized_target)
    if len(target_bigrams) < 3:
        return False
    for fact in facts:
        if fact.status not in {"client_claimed", "corroborated", "disputed"} or not fact.value:
            continue
        normalized_known = _semantic_fact_text(fact.value)
        if normalized_target in normalized_known:
            return True
        overlap = len(target_bigrams & _character_bigrams(normalized_known)) / len(target_bigrams)
        if overlap >= 0.60 and len(target_bigrams & _character_bigrams(normalized_known)) >= 3:
            return True
    return False


class ConsultationState(StateModel):
    session_id: str
    max_turns: int = Field(ge=1)
    turn: int = Field(default=0, ge=0)
    domain: str = "general"
    persona: str = "unknown"
    issues: list[Issue] = Field(default_factory=list)
    facts: list[FactSlot] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    asked_targets: list[str] = Field(default_factory=list)
    interactions: list[Interaction] = Field(default_factory=list)
    unresolved_conflicts: list[Conflict] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    candidate_action: dict[str, object] | None = None
    active_skills: list[str] = Field(default_factory=list)

    @computed_field
    @property
    def high_critical_unknown_count(self) -> int:
        return sum(
            f.criticality == "high"
            and f.status == "unknown"
            and f.fact_id not in self.asked_targets
            and f.fact_id not in NON_SUBSTANTIVE_FACT_IDS
            for f in self.facts
        )

    @computed_field
    @property
    def actionable_unresolved_fact_count(self) -> int:
        return sum(
            f.status in {"unknown", "disputed"}
            and f.fact_id not in self.asked_targets
            and f.fact_id not in NON_SUBSTANTIVE_FACT_IDS
            for f in self.facts
        )

    @computed_field
    @property
    def client_fact_unresolved_count(self) -> int:
        return sum(
            f.target_kind == "client_fact"
            and f.status in {"unknown", "disputed"}
            and f.fact_id not in self.asked_targets
            and f.fact_id not in NON_SUBSTANTIVE_FACT_IDS
            for f in self.facts
        )

    @computed_field
    @property
    def evidence_or_third_party_unresolved_count(self) -> int:
        return sum(
            f.target_kind == "evidence_or_third_party"
            and f.status in {"unknown", "disputed"}
            and f.fact_id not in self.asked_targets
            and f.fact_id not in NON_SUBSTANTIVE_FACT_IDS
            for f in self.facts
        )

    @computed_field
    @property
    def unresolved_conflict_count(self) -> int:
        return len(self.unresolved_conflicts)

    @computed_field
    @property
    def client_claimed_high_count(self) -> int:
        handled = {
            item.target_id
            for item in self.interactions
            if item.action_type in {"clarify", "verify"}
        }
        return sum(
            f.criticality == "high"
            and f.status == "client_claimed"
            and f.fact_id not in handled
            and f.fact_id not in NON_SUBSTANTIVE_FACT_IDS
            for f in self.facts
        )

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
    def dialogue_horizon_reached(self) -> bool:
        """Whether the configured client-interaction budget has been consumed."""

        return len(self.interactions) >= self.max_turns

    @computed_field
    @property
    def candidate_target_repeated(self) -> bool:
        action = self.candidate_action or {}
        target = action.get("target_id")
        action_type = action.get("action_type")
        content = re.sub(r"[\W_]+", "", str(action.get("content") or "")).lower()
        if content:
            return any(
                re.sub(r"[\W_]+", "", item.question).lower() == content
                for item in self.interactions
            )
        return bool(
            target
            and any(
                item.target_id == target and item.action_type == action_type
                for item in self.interactions
            )
        )

    @computed_field
    @property
    def candidate_target_unavailable(self) -> bool:
        target = (self.candidate_action or {}).get("target_id")
        return any(f.fact_id == target and f.status == "not_available" for f in self.facts)

    @computed_field
    @property
    def candidate_target_is_client_fact(self) -> bool:
        target = (self.candidate_action or {}).get("target_id")
        return any(
            f.fact_id == target and f.target_kind == "client_fact" for f in self.facts
        )

    @computed_field
    @property
    def candidate_target_is_evidence_gap(self) -> bool:
        target = (self.candidate_action or {}).get("target_id")
        return any(
            f.fact_id == target and f.target_kind == "evidence_or_third_party"
            for f in self.facts
        )

    @computed_field
    @property
    def candidate_target_low_value(self) -> bool:
        target = (self.candidate_action or {}).get("target_id")
        return bool(target and target in NON_SUBSTANTIVE_FACT_IDS)

    @computed_field
    @property
    def candidate_target_already_known(self) -> bool:
        return candidate_action_targets_known_fact(self.facts, self.candidate_action or {})

    @computed_field
    @property
    def candidate_target_criticality(self) -> Criticality | None:
        """Visible priority of the action's target, if it names a planned fact."""

        target = (self.candidate_action or {}).get("target_id")
        return next(
            (fact.criticality for fact in self.facts if fact.fact_id == target),
            None,
        )

    @computed_field
    @property
    def substantive_fact_count(self) -> int:
        return sum(
            f.fact_id not in NON_SUBSTANTIVE_FACT_IDS
            and f.status in {"client_claimed", "corroborated", "disputed"}
            for f in self.facts
        )

    @computed_field
    @property
    def new_hidden_fact_turn_count(self) -> int:
        return sum(item.response_kind == "new_hidden_fact" for item in self.interactions)

    @computed_field
    @property
    def opening_repeat_turn_count(self) -> int:
        return sum(item.response_kind == "opening_repeat" for item in self.interactions)

    @computed_field
    @property
    def repeated_hidden_fact_turn_count(self) -> int:
        return sum(
            item.response_kind == "repeated_hidden_fact" for item in self.interactions
        )

    @computed_field
    @property
    def unavailable_turn_count(self) -> int:
        return sum(item.response_kind == "unavailable" for item in self.interactions)


NON_SUBSTANTIVE_FACT_IDS = frozenset(
    {
        "opening_statement",
        "client_name",
        "client_identity",
        "client_introduction",
    }
)
