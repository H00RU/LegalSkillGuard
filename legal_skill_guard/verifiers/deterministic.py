"""Deterministic process, leakage and safety checks."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from legal_skill_guard.data_visibility import find_online_payload_forbidden_fields
from legal_skill_guard.schemas.action import ActionDecision, StructuredAction
from legal_skill_guard.schemas.state import ConsultationState
from legal_skill_guard.text_normalization import normalize_question


class VerificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    validator_id: str
    passed: bool
    severity: str = "error"
    detail: str = ""


def verify_action(
    state: ConsultationState,
    decision: ActionDecision,
    rendered_question: str | None = None,
) -> list[VerificationResult]:
    action = decision.final
    final_target_repeated = bool(
        not rendered_question
        and action.target_id
        and any(
            item.target_id == action.target_id and item.action_type == action.action_type
            for item in state.interactions
        )
    )
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
                action.target_type != "fact" or not action.target_id or action.target_id in fact_ids
            ),
        ),
        VerificationResult(
            validator_id="question_not_repeated",
            passed=action.action_type not in {"ask", "clarify", "verify"}
            or (
                not final_target_repeated
                and (
                    not rendered_question
                    or normalize_question(rendered_question)
                    not in {normalize_question(item.question) for item in state.interactions}
                )
            ),
            severity="warning",
        ),
        VerificationResult(
            validator_id="fixed_skill_documents_without_runtime_rewrite",
            passed=(
                len(decision.activated_skill_ids) <= 2
                and len(decision.activated_skill_ids)
                == len(set(decision.activated_skill_ids))
                and set(decision.activated_skill_ids).issubset(decision.retrieved_skill_ids)
                and not any(
                    isinstance(item, dict) and item.get("skill_id")
                    for item in decision.changes
                )
            ),
            severity="warning",
        ),
    ]
    return results


class StopGate:
    def evaluate(self, state: ConsultationState, action: StructuredAction) -> tuple[str, str]:
        if action.action_type not in {"final", "abstain"}:
            return "PASS", "not_a_terminal_action"
        if action.action_type == "abstain":
            # Abstention is a valid policy outcome, including when the model leaves
            # an answerable target unresolved.  Replacing it with a synthesized
            # question changes the behavior under evaluation and can manufacture
            # elicitation credit.  Quality/safety metrics must observe the model's
            # terminal choice instead of a deterministic proxy decision.
            return "PASS", "explicit_abstention"
        if state.substantive_fact_count == 0:
            # Premature termination is a policy outcome, not an infrastructure
            # failure.  Replacing it with a deterministic question would hide the
            # very behaviour that learned documents are intended to improve.
            return "PASS", "premature_final_without_substantive_fact"
        if state.actionable_unresolved_fact_count or state.unresolved_conflict_count:
            # Unknowns and conflicts must remain explicit in the conditional memo,
            # but their mere existence cannot deterministically force another turn.
            # Whether another question has positive information value is the behavior
            # under study and may be changed by an executable skill.  Hard-redirection
            # here erased both premature-final and endless-questioning signals.
            return "PASS", "conditional_visible_state_with_unresolved_targets"
        return "PASS", "sufficient_visible_state"
