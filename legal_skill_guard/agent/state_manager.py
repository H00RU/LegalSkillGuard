"""Rule-validated state merging; model extraction never receives hidden benchmark fields."""

from __future__ import annotations

import hashlib
import re

from legal_skill_guard.schemas.state import (
    Conflict,
    ConsultationState,
    Evidence,
    FactObservation,
    FactSlot,
    Issue,
    StatePatch,
)


def stable_id(prefix: str, value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")[:24]
    suffix = hashlib.sha256(value.encode()).hexdigest()[:8]
    return f"{prefix}_{slug or suffix}_{suffix}"


class StateManager:
    def initial(
        self, session_id: str, opening: str, max_turns: int = 6, persona: str = "unknown"
    ) -> ConsultationState:
        state = ConsultationState(session_id=session_id, max_turns=max_turns, persona=persona)
        if opening.strip():
            state.facts.append(
                FactSlot(
                    fact_id="opening_statement",
                    label="客户开场陈述",
                    status="client_claimed",
                    value=opening.strip(),
                    source_turns=[0],
                    criticality="medium",
                    confidence=1.0,
                )
            )
        return state

    def merge(self, state: ConsultationState, patch: StatePatch, turn: int) -> ConsultationState:
        updated = state.model_copy(deep=True)
        updated.turn = turn
        facts = {fact.fact_id: fact for fact in updated.facts}
        for observation in patch.observations:
            self._merge_observation(updated, facts, observation, turn)
        issues = {issue.label for issue in updated.issues}
        for label in patch.issue_labels:
            label = label.strip()
            if label and label not in issues:
                updated.issues.append(
                    Issue(issue_id=stable_id("issue", label), label=label, status="active")
                )
                issues.add(label)
        updated.risk_flags = list(dict.fromkeys([*updated.risk_flags, *patch.risk_flags_add]))
        return updated

    def mark_asked(self, state: ConsultationState, target_id: str | None) -> ConsultationState:
        updated = state.model_copy(deep=True)
        if target_id:
            updated.asked_targets = list(dict.fromkeys([*updated.asked_targets, target_id]))
        return updated

    def _merge_observation(
        self,
        state: ConsultationState,
        facts: dict[str, FactSlot],
        observation: FactObservation,
        turn: int,
    ) -> None:
        fact_id = observation.fact_id.strip() or stable_id("fact", observation.label)
        current = facts.get(fact_id)
        evidence_ids: list[str] = []
        for label in observation.evidence_labels:
            evidence_id = stable_id("evidence", label)
            evidence_ids.append(evidence_id)
            if not any(item.evidence_id == evidence_id for item in state.evidence):
                state.evidence.append(
                    Evidence(
                        evidence_id=evidence_id,
                        label=label,
                        availability="claimed_available",
                        supports=[fact_id],
                    )
                )
        if current is None:
            current = FactSlot(
                fact_id=fact_id,
                label=observation.label,
                status=observation.status,
                value=observation.value,
                source_turns=[turn] if observation.status != "unknown" else [],
                evidence_ids=evidence_ids,
                confidence=observation.confidence,
                criticality=observation.criticality,
            )
            state.facts.append(current)
            facts[fact_id] = current
            return
        if (
            current.value
            and observation.value
            and current.value.strip() != observation.value.strip()
            and observation.status not in {"unknown", "not_available"}
        ):
            state.unresolved_conflicts.append(
                Conflict(
                    fact_id=fact_id,
                    prior_value=current.value,
                    new_value=observation.value,
                    source_turns=list(dict.fromkeys([*current.source_turns, turn])),
                )
            )
            current.status = "disputed"
            current.confidence = min(current.confidence, observation.confidence)
        else:
            current.status = observation.status
            current.value = observation.value if observation.value is not None else current.value
            current.confidence = observation.confidence
        current.label = observation.label or current.label
        current.criticality = observation.criticality
        current.source_turns = list(dict.fromkeys([*current.source_turns, turn]))
        current.evidence_ids = list(dict.fromkeys([*current.evidence_ids, *evidence_ids]))
