"""Deterministic process, leakage and safety checks."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from legal_skill_guard.data_visibility import find_online_payload_forbidden_fields
from legal_skill_guard.schemas.action import ActionDecision, StructuredAction
from legal_skill_guard.schemas.state import ConsultationState


class VerificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    validator_id: str
    passed: bool
    severity: str = "error"
    detail: str = ""


def verify_action(state: ConsultationState, decision: ActionDecision) -> list[VerificationResult]:
    action = decision.final
    fact_ids = {fact.fact_id for fact in state.facts}
    results = [
        VerificationResult(
            validator_id="no_hidden_fields",
            passed=not find_online_payload_forbidden_fields(
                {"state": state.model_dump(mode="json"), "action": action.model_dump(mode="json")}
            ),
            severity="severe",
        ),
        VerificationResult(
            validator_id="target_exists",
            passed=(
                action.target_type != "fact"
                or not action.target_id
                or action.target_id in fact_ids
            ),
        ),
        VerificationResult(
            validator_id="question_not_repeated",
            passed=action.action_type not in {"ask", "clarify", "verify"}
            or not action.target_id
            or action.target_id not in state.asked_targets,
            severity="warning",
        ),
        VerificationResult(
            validator_id="skill_precondition_changed_action",
            passed=not decision.activated_skill_ids or bool(decision.changes),
            severity="warning",
        ),
    ]
    return results


class StopGate:
    def evaluate(self, state: ConsultationState, action: StructuredAction) -> tuple[str, str]:
        if action.action_type not in {"final", "abstain"}:
            return "PASS", "not_a_terminal_action"
        if action.action_type == "abstain":
            return "PASS", "explicit_abstention"
        if state.unresolved_conflict_count:
            return "REDIRECT", "unresolved_disputed_fact"
        if state.high_critical_unknown_count:
            return "REDIRECT", "high_criticality_unknown"
        if state.client_claimed_high_count:
            return "REDIRECT", "high_criticality_claim_uncorroborated"
        if state.turn >= state.max_turns or state.all_remaining_facts_not_available:
            return "ABSTAIN", "dialogue_budget_or_unavailable"
        return "PASS", "sufficient_visible_state"
