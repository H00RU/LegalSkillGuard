"""Rule-validated state merging; model extraction never receives hidden benchmark fields."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from legal_skill_guard.schemas.state import (
    ClientResponseKind,
    Conflict,
    ConsultationState,
    Evidence,
    FactObservation,
    FactSlot,
    Interaction,
    Issue,
    StatePatch,
)

NON_EVIDENTIARY_LABELS = frozenset(
    {
        "opening_statement",
        "client_statement",
        "client_response",
        "客户开场陈述",
        "客户陈述",
        "客户口述",
        "当事人陈述",
    }
)


def is_concrete_evidence_label(value: str) -> bool:
    normalized = re.sub(r"[\W_]+", "", value).lower()
    return bool(normalized) and normalized not in {
        re.sub(r"[\W_]+", "", item).lower() for item in NON_EVIDENTIARY_LABELS
    }


def stable_id(prefix: str, value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")[:24]
    suffix = hashlib.sha256(value.encode()).hexdigest()[:8]
    return f"{prefix}_{slug or suffix}_{suffix}"


class StateManager:
    def initial(
        self,
        session_id: str,
        opening: str,
        *,
        max_turns: int,
        persona: str = "unknown",
        domain: str = "general",
    ) -> ConsultationState:
        state = ConsultationState(
            session_id=session_id,
            max_turns=max_turns,
            persona=persona,
            domain=domain,
        )
        if opening.strip():
            state.facts.append(
                FactSlot(
                    fact_id="opening_statement",
                    label="客户开场陈述",
                    status="client_claimed",
                    value=opening.strip(),
                    source_turns=[0],
                    criticality="low",
                    confidence=1.0,
                    target_kind="client_fact",
                )
            )
            # Preserve the verbatim opening for audit, but also expose its sentence-level
            # claims as substantive visible facts.  This is deliberately lexical rather
            # than a legal/semantic extractor: it cannot import hidden case labels, and it
            # prevents the policy model from having to reconstruct every already-stated
            # fact before it can choose the first useful question.
            opening_claims = [
                item.strip(" ，,。；;！？!?\t")
                for item in re.split(r"[。；;！？!?\n]+", opening.strip())
                if len(item.strip(" ，,。；;！？!?\t")) >= 4
            ]
            for index, claim in enumerate(opening_claims, start=1):
                state.facts.append(
                    FactSlot(
                        fact_id=f"opening_claim_{index:02d}",
                        label=f"开场明确陈述{index}",
                        status="client_claimed",
                        value=claim,
                        source_turns=[0],
                        criticality="medium",
                        confidence=1.0,
                        target_kind="client_fact",
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
    def mark_interaction(
        self,
        state: ConsultationState,
        *,
        turn: int,
        action_type: str,
        target_id: str | None,
        question: str,
        target_not_available: bool = False,
        target_answered: bool = False,
        client_response: str | None = None,
        response_kind: ClientResponseKind | None = None,
        disclosed_fact_ids: list[str] | None = None,
    ) -> ConsultationState:
        updated = state.model_copy(deep=True)
        # A matched client belief and the client's willingness to disclose it are
        # separate facts.  ``withheld`` records a real conversational response, but
        # it must not be collapsed into either "answered" or "not available".  In
        # particular, retaining the target as unresolved lets a later, materially
        # different question or a safer conversational context try again without a
        # hard-coded retry counter.
        withheld = response_kind == "withheld"
        route_contract_failed = response_kind == "contract_fallback"
        if withheld or route_contract_failed:
            target_not_available = False
            target_answered = False
            disclosed_fact_ids = []
            covered: set[str] = set()
        else:
            covered = set()
        if target_id and target_answered and not withheld:
            covered.add(target_id)
        # Neither a withheld answer nor an invalid routing completion establishes
        # that the target was substantively exhausted.  Keep it eligible for a
        # materially different follow-up or, for a contract failure, a clean rerun.
        if target_id and not withheld and not route_contract_failed:
            updated.asked_targets = list(dict.fromkeys([*updated.asked_targets, target_id]))
        for fact in updated.facts:
            if fact.fact_id in covered and client_response and fact.status in {
                "unknown",
                "disputed",
            }:
                # Protocol 15 updates only the target that was actually asked and
                # answered. Cross-slot semantic coverage is retired; a compound
                # visible answer cannot close a second structured target implicitly.
                fact.status = "client_claimed"
                fact.value = client_response.strip()
                fact.source_turns = list(dict.fromkeys([*fact.source_turns, turn]))
                fact.confidence = max(fact.confidence, 0.7)
            elif (
                fact.fact_id == target_id
                and target_not_available
                and fact.status in {"unknown", "disputed"}
            ):
                fact.status = "not_available"
                fact.value = None
        updated.interactions.append(
            Interaction(
                turn=turn,
                action_type=action_type,
                target_id=target_id,
                question=question,
                response_kind=response_kind,
                new_information=response_kind == "new_hidden_fact",
                disclosed_fact_ids=list(disclosed_fact_ids or []),
                covered_target_ids=sorted(covered),
            )
        )
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
            if not is_concrete_evidence_label(label):
                continue
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
        normalized_status = (
            "corroborated"
            if evidence_ids
            else "client_claimed"
            if observation.status == "corroborated"
            else observation.status
        )
        normalized_criticality = (
            "low"
            if fact_id
            in {"opening_statement", "client_name", "client_identity", "client_introduction"}
            else observation.criticality
        )
        if current is None:
            current = FactSlot(
                fact_id=fact_id,
                label=observation.label,
                status=normalized_status,
                value=observation.value,
                source_turns=[turn] if observation.status != "unknown" else [],
                evidence_ids=evidence_ids,
                confidence=observation.confidence,
                criticality=normalized_criticality,
                target_kind=observation.target_kind,
            )
            state.facts.append(current)
            facts[fact_id] = current
            return
        # A policy patch is extracted before the client answers the current question.
        # It may enrich visible facts, but it must not erase a prior answer or revive a
        # target that the client already said was unavailable. Without this monotonic
        # guard, a weak policy can rewrite ``not_available`` to ``unknown`` and ask the
        # same question indefinitely.
        if observation.status == "unknown" and current.status != "unknown":
            return
        if current.status == "not_available" and observation.status != "not_available":
            return
        if observation.status == "disputed" and current.value and observation.value:
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
        elif current.status != "disputed":
            current.status = normalized_status
            current.value = observation.value if observation.value is not None else current.value
            current.confidence = observation.confidence
        current.label = observation.label or current.label
        current.criticality = normalized_criticality
        # A missing kind is parseable only for historical audit.  It must not
        # erase an already-authored planner kind during a merge; the persisted
        # observation remains untyped and current trajectory health will reject it.
        if observation.target_kind is not None:
            current.target_kind = observation.target_kind
        current.source_turns = list(dict.fromkeys([*current.source_turns, turn]))
        current.evidence_ids = list(dict.fromkeys([*current.evidence_ids, *evidence_ids]))


def reconstruct_execution_state(
    state_before: dict[str, Any],
    patch: StatePatch,
    *,
    turn: int,
    candidate_action: dict[str, Any] | None = None,
) -> ConsultationState:
    """Rebuild the exact state in which the proposed policy action was evaluated.

    Trajectories persist the state before policy inference and the policy's patch
    separately. Causal comparison and source witnessing must both
    merge those records exactly as the online runner does.
    """

    payload = {
        key: value
        for key, value in state_before.items()
        if key in ConsultationState.model_fields
    }
    base = ConsultationState.model_validate(payload)
    merged = StateManager().merge(base, patch, turn)
    merged.candidate_action = candidate_action
    return merged
