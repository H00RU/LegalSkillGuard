"""Deterministic pre-scoring health contract for persisted trajectories."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from legal_skill_guard.agent.memo_health import memo_health_violations
from legal_skill_guard.agent.stateful_policy import (
    POLICY_FALLBACK_REASONS,
    action_question_quality_violations,
    blocking_policy_health_violations,
    policy_behavior_issue_is_soft,
    policy_health_violations,
)
from legal_skill_guard.data_visibility import find_online_payload_forbidden_fields
from legal_skill_guard.environment.client_response import (
    disclosed_fact_indices,
    opening_fact_candidates,
    response_violations,
)
from legal_skill_guard.experiment.intervention_isolation import (
    skill_memory_delivery_issues,
)
from legal_skill_guard.schemas.action import StructuredAction
from legal_skill_guard.schemas.experiment import (
    PolicyEnvelope,
    ResearchTrajectory,
    current_trajectory_contract_issues,
)
from legal_skill_guard.schemas.state import NON_SUBSTANTIVE_FACT_IDS, ConsultationState
from legal_skill_guard.text_normalization import normalize_question

REPEATED_RESPONSE_MARKERS = ("已经说明", "已经说过", "刚才说过")
UNAVAILABLE_RESPONSE_MARKERS = ("不知道", "不清楚", "不太确定", "没有这项具体情况")
@dataclass(frozen=True)
class TrajectoryHealthIssue:
    """One blocking process-contract defect with enough context to audit it."""

    code: str
    trajectory_id: str
    turn: int
    detail: str

    def as_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "trajectory_id": self.trajectory_id,
            "turn": self.turn,
            "detail": self.detail,
        }


def _normalized(value: str) -> str:
    return normalize_question(value)


def _client_route_valid(step: Any) -> bool | None:
    current = getattr(step, "client_route_decision_valid", None)
    if current is not None:
        return bool(current)
    return getattr(step, "legacy_client_relevance_passed", None)


def _record(
    issues: list[TrajectoryHealthIssue],
    trajectory: ResearchTrajectory,
    turn: int,
    code: str,
    detail: object,
) -> None:
    issues.append(
        TrajectoryHealthIssue(
            code=code,
            trajectory_id=trajectory.trajectory_id,
            turn=turn,
            detail=str(detail)[:1000],
        )
    )


def blocking_policy_fallback_reasons(step: Any) -> set[str]:
    """Return fallbacks that indicate execution failure rather than bad policy.

    StopGate's explicit ``abstain`` -> ``final`` redirect preserves an otherwise
    scoreable model decision when visible substance can support a conditional
    memo.  The model's poor terminal choice remains in the trajectory and is
    counted by operational/quality metrics; treating the deterministic redirect
    as process corruption would instead censor a legitimate negative example.
    Repair-exhaustion fallbacks, including the same terminal fallback without
    this auditable StopGate provenance, remain blocking.
    """

    proposed_reason = str(getattr(step.proposed_action, "reason", "") or "")
    final_reason = str(getattr(step.action_decision.final, "reason", "") or "")
    post_skill_reasons = {
        str(change.get("after", {}).get("reason") or "")
        for change in step.action_decision.changes
        if change.get("source") == "post_skill_health_gate"
        and isinstance(change.get("after"), dict)
    }
    reasons = {proposed_reason, final_reason, *post_skill_reasons} & set(
        POLICY_FALLBACK_REASONS
    )
    conditional_redirect = any(
        change.get("source") == "stop_gate"
        and change.get("reason") == "conditional_memo_available"
        and isinstance(change.get("after"), dict)
        and change["after"].get("reason")
        == "safe_fallback_conditional_memo_available"
        for change in step.action_decision.changes
    )
    if conditional_redirect and proposed_reason not in POLICY_FALLBACK_REASONS:
        reasons.discard("safe_fallback_conditional_memo_available")
    return reasons


def trajectory_health_issues(
    trajectory: ResearchTrajectory,
    evaluator_case: dict[str, Any],
    *,
    require_current_contract: bool = True,
    expected_run_id: str | None = None,
) -> list[TrajectoryHealthIssue]:
    """Return hard defects that make a trajectory unsafe to score or teach from.

    The checks are contract based rather than quality-threshold based. They do not
    require that an untrained model already performs well; they only reject data
    that violates grounding, state, safety, or executable dialogue invariants.
    """

    issues: list[TrajectoryHealthIssue] = []
    if trajectory.status == "error" or trajectory.error:
        _record(issues, trajectory, 0, "trajectory_execution_error", trajectory.error)
    # Reaching the bounded episode horizon is a genuine frozen-policy outcome,
    # not corrupted research data.  It must remain scoreable and visible to the
    # teacher; otherwise the weakest repetition/continuation failures disappear
    # from exactly the training evidence meant to improve them.  The report below
    # records it as a quality outcome, while fallbacks, leakage, grounding and
    # state-integrity defects remain blocking.
    if trajectory.memo_safe_fallback:
        _record(issues, trajectory, 0, "memo_fallback_used", "bounded model repair exhausted")
    if trajectory.planning_safe_partial:
        _record(
            issues,
            trajectory,
            0,
            "partial_investigation_plan_used",
            len(trajectory.initial_investigation_plan.observations),
        )
    if require_current_contract:
        for contract_issue in current_trajectory_contract_issues(
            trajectory,
            expected_run_id=expected_run_id,
        ):
            _record(
                issues,
                trajectory,
                contract_issue.turn,
                contract_issue.code,
                contract_issue.detail,
            )
        existing_codes = {item.code for item in issues}
        for delivery_issue in skill_memory_delivery_issues(
            trajectory,
            expected_ids=set(trajectory.exposed_skill_ids),
        ):
            if delivery_issue not in existing_codes:
                _record(
                    issues,
                    trajectory,
                    0,
                    delivery_issue,
                    "actual stored lawyer system prompt failed skill-memory delivery audit",
                )
                existing_codes.add(delivery_issue)
    if trajectory.schema_version >= 15 and (
        trajectory.initial_visible_state_coverage_attempts
        or trajectory.initial_visible_state_covered_target_ids
        or trajectory.initial_visible_state_coverage_token_usage.total
    ):
        _record(
            issues,
            trajectory,
            0,
            "retired_initial_visible_state_coverage_present",
            "protocol_15_requires_empty_compatibility_fields",
        )
    elif trajectory.schema_version >= 14:
        initial_applied = sorted(
            item.target_id
            for item in trajectory.initial_visible_state_coverage_attempts
            if item.applied
        )
        initial_persisted = sorted(trajectory.initial_visible_state_covered_target_ids)
        if initial_applied != initial_persisted:
            _record(
                issues,
                trajectory,
                0,
                "initial_visible_state_coverage_provenance_mismatch",
                {"applied_attempts": initial_applied, "persisted": initial_persisted},
            )
        planned = {
            item.fact_id: item for item in trajectory.initial_investigation_plan.observations
        }
        first_state_fact_rows = (
            trajectory.steps[0].state_before.get("facts", []) if trajectory.steps else []
        )
        first_state_facts = {
            str(item.get("fact_id") or ""): item
            for item in first_state_fact_rows
            if isinstance(item, dict)
        }
        for attempt in trajectory.initial_visible_state_coverage_attempts:
            if (
                not attempt.parse_valid
                or attempt.applied
                != (
                    attempt.answers_target
                    and attempt.deterministic_compatible is not False
                    and not attempt.deterministic_compatibility_violations
                )
            ):
                _record(
                    issues,
                    trajectory,
                    0,
                    "initial_visible_state_coverage_invalid_decision",
                    attempt.model_dump(mode="json"),
                )
            if attempt.target_id not in planned:
                _record(
                    issues,
                    trajectory,
                    0,
                    "initial_visible_state_coverage_invalid_target",
                    attempt.target_id,
                )
            if attempt.applied and trajectory.steps:
                persisted = first_state_facts.get(attempt.target_id) or {}
                if (
                    persisted.get("status") != "client_claimed"
                    or persisted.get("value") != trajectory.opening
                ):
                    _record(
                        issues,
                        trajectory,
                        0,
                        "initial_visible_state_coverage_not_persisted",
                        attempt.target_id,
                    )
    visible_text = (
        trajectory.opening
        + "\n"
        + "\n".join(step.client_response or "" for step in trajectory.steps)
    )
    visible_dialogue = [
        (step.rendered_question, step.client_response)
        for step in trajectory.steps
        if step.rendered_question is not None and step.client_response is not None
    ]
    unavailable_questions = [
        step.rendered_question
        for step in trajectory.steps
        if step.rendered_question is not None
        and step.client_response_kind == "unavailable"
    ]
    withheld_questions = [
        step.rendered_question
        for step in trajectory.steps
        if step.rendered_question is not None
        and step.client_response_kind == "withheld"
    ]
    for violation in memo_health_violations(
        trajectory.memo,
        visible_text,
        unavailable_questions,
        visible_dialogue,
        withheld_questions,
    ):
        _record(issues, trajectory, 0, f"memo_{violation}", trajectory.memo)

    hidden_facts = list(evaluator_case.get("facts", []))
    opening_facts = opening_fact_candidates(trajectory.opening)
    facts = [*opening_facts, *hidden_facts]
    beliefs = [str(fact.get("client_belief") or "") for fact in facts]
    valid_fact_ids = {str(fact.get("fact_id") or "") for fact in facts}
    hidden_by_id = {str(fact.get("fact_id") or ""): fact for fact in hidden_facts}
    opening_by_id = {str(fact.get("fact_id") or ""): fact for fact in opening_facts}
    disclosed_hidden_ids: set[str] = set()
    grounding_history: list[tuple[str, str]] = []

    for step in trajectory.steps:
        turn = step.turn
        try:
            persisted_state = ConsultationState.model_validate(
                {
                    key: value
                    for key, value in step.state_before.items()
                    if key in ConsultationState.model_fields
                }
            )
            # Admission is based on the action that was actually executed after
            # the auditable skill layer, not on the frozen lawyer's intermediate
            # proposal.  A skill is allowed to repair a bad proposal; rejecting
            # that trajectory would make useful skill interventions impossible to
            # learn or evaluate.  The same state patch remains in the envelope, so
            # hidden/management facts and state regressions still fail closed.
            # The rendered question and verifier results below independently check
            # the persisted surface action.  Model fallbacks remain hard failures
            # through POLICY_FALLBACK_REASONS.
            persisted_envelope = PolicyEnvelope(
                state_patch=step.state_patch,
                action=step.action_decision.final,
            )
            persisted_policy_issues = blocking_policy_health_violations(
                policy_health_violations(persisted_envelope, persisted_state)
            )
        except ValueError as exc:
            persisted_policy_issues = [f"invalid_persisted_policy_state:{exc}"]
        for violation in persisted_policy_issues:
            _record(
                issues,
                trajectory,
                turn,
                "persisted_policy_contract_failure",
                violation,
            )
        fallback_reasons = blocking_policy_fallback_reasons(step)
        if fallback_reasons:
            _record(
                issues,
                trajectory,
                turn,
                "policy_fallback_used",
                sorted(fallback_reasons),
            )
        for observation in step.state_patch.observations:
            if observation.fact_id in NON_SUBSTANTIVE_FACT_IDS:
                _record(
                    issues,
                    trajectory,
                    turn,
                    "management_fact_patch",
                    observation.fact_id,
                )

        online_payload = {
            "visible_input": [item.model_dump(mode="json") for item in step.visible_input],
            "state_before": step.state_before,
            "state_patch": step.state_patch.model_dump(mode="json"),
            "state_after": step.state_after,
            "proposed_action": step.proposed_action.model_dump(mode="json"),
            "final_action": step.action_decision.final.model_dump(mode="json"),
        }
        forbidden_fields = find_online_payload_forbidden_fields(online_payload)
        if forbidden_fields:
            _record(
                issues,
                trajectory,
                turn,
                "hidden_field_leak",
                sorted(forbidden_fields),
            )

        question = step.rendered_question
        if question:
            if re.search(r"[a-z]+_[a-z_]+", question):
                _record(issues, trajectory, turn, "snake_case_question", question)
            for violation in action_question_quality_violations(
                StructuredAction(action_type="ask", content=question)
            ):
                if not policy_behavior_issue_is_soft(violation):
                    _record(issues, trajectory, turn, violation, question)

        client_response = step.client_response
        if client_response is not None:
            if step.client_safe_fallback:
                _record(
                    issues,
                    trajectory,
                    turn,
                    "client_selection_fallback_used",
                    [
                        item.raw_output
                        for item in [
                            *step.client_opening_selection_attempts,
                            *step.client_selection_attempts,
                        ]
                    ],
                )
            selected_ids = step.client_selected_fact_ids
            if trajectory.schema_version >= 12:
                opening_ids = step.client_opening_reference_ids
                kind = step.client_response_kind
                if any(item.startswith("O") for item in selected_ids):
                    _record(
                        issues,
                        trajectory,
                        turn,
                        "public_opening_recorded_as_hidden_disclosure",
                        selected_ids,
                    )
                if any(item not in hidden_by_id for item in selected_ids):
                    _record(
                        issues,
                        trajectory,
                        turn,
                        "client_invalid_hidden_fact_id",
                        selected_ids,
                    )
                if any(item not in opening_by_id for item in opening_ids):
                    _record(
                        issues,
                        trajectory,
                        turn,
                        "client_invalid_opening_reference_id",
                        opening_ids,
                    )
                expected_shape = {
                    "new_hidden_fact": (1, 0),
                    "repeated_hidden_fact": (1, 0),
                    "opening_repeat": (0, 1),
                    "withheld": (0, 0),
                    "unavailable": (0, 0),
                    "contract_fallback": (0, 0),
                }.get(kind or "")
                if expected_shape != (len(selected_ids), len(opening_ids)):
                    _record(
                        issues,
                        trajectory,
                        turn,
                        "client_response_provenance_mismatch",
                        {
                            "kind": kind,
                            "hidden": selected_ids,
                            "opening": opening_ids,
                        },
                    )
                if trajectory.schema_version >= 15:
                    matched_ids = list(step.client_matched_fact_ids)
                    disclosure_decisions = dict(step.client_disclosure_decisions)
                    if kind in {"new_hidden_fact", "repeated_hidden_fact"}:
                        if matched_ids != selected_ids or any(
                            item not in hidden_by_id for item in matched_ids
                        ):
                            _record(
                                issues,
                                trajectory,
                                turn,
                                "client_match_provenance_mismatch",
                                {
                                    "kind": kind,
                                    "matched": matched_ids,
                                    "selected": selected_ids,
                                },
                            )
                        expected_decisions = {
                            item: "disclose" for item in matched_ids
                        }
                    elif kind == "opening_repeat":
                        if matched_ids != opening_ids or any(
                            item not in opening_by_id for item in matched_ids
                        ):
                            _record(
                                issues,
                                trajectory,
                                turn,
                                "client_match_provenance_mismatch",
                                {
                                    "kind": kind,
                                    "matched": matched_ids,
                                    "opening": opening_ids,
                                },
                            )
                        expected_decisions = {
                            item: "disclose" for item in matched_ids
                        }
                    elif kind == "withheld":
                        valid_withheld_match = bool(
                            len(matched_ids) == 1
                            and matched_ids[0] in hidden_by_id
                            and not selected_ids
                            and not opening_ids
                        )
                        if not valid_withheld_match:
                            _record(
                                issues,
                                trajectory,
                                turn,
                                "client_withheld_match_provenance_mismatch",
                                {
                                    "matched": matched_ids,
                                    "hidden": selected_ids,
                                    "opening": opening_ids,
                                },
                            )
                        expected_decisions = {
                            item: "withhold" for item in matched_ids
                        }
                    else:
                        if matched_ids:
                            _record(
                                issues,
                                trajectory,
                                turn,
                                "client_match_provenance_mismatch",
                                {"kind": kind, "matched": matched_ids},
                            )
                        expected_decisions = {}
                    if disclosure_decisions != expected_decisions:
                        _record(
                            issues,
                            trajectory,
                            turn,
                            "client_disclosure_decision_provenance_mismatch",
                            {
                                "kind": kind,
                                "matched": matched_ids,
                                "decisions": disclosure_decisions,
                                "expected": expected_decisions,
                            },
                        )
                if kind == "new_hidden_fact" and selected_ids:
                    selected_id = selected_ids[0]
                    belief = str(hidden_by_id.get(selected_id, {}).get("client_belief") or "")
                    if selected_id in disclosed_hidden_ids:
                        _record(
                            issues,
                            trajectory,
                            turn,
                            "client_repeated_fact_marked_new",
                            selected_id,
                        )
                    if belief and belief not in client_response:
                        _record(
                            issues,
                            trajectory,
                            turn,
                            "client_response_not_grounded_in_selected_belief",
                            {"selected": selected_id, "response": client_response},
                        )
                    disclosed_hidden_ids.add(selected_id)
                elif kind == "repeated_hidden_fact" and selected_ids:
                    if selected_ids[0] not in disclosed_hidden_ids:
                        _record(
                            issues,
                            trajectory,
                            turn,
                            "client_undisclosed_fact_marked_repeated",
                            selected_ids[0],
                        )
                    if not any(marker in client_response for marker in REPEATED_RESPONSE_MARKERS):
                        _record(
                            issues,
                            trajectory,
                            turn,
                            "client_repeat_response_missing_marker",
                            client_response,
                        )
                elif kind == "opening_repeat" and opening_ids:
                    belief = str(opening_by_id.get(opening_ids[0], {}).get("client_belief") or "")
                    if belief and belief not in client_response:
                        _record(
                            issues,
                            trajectory,
                            turn,
                            "client_opening_repeat_not_grounded",
                            {"selected": opening_ids[0], "response": client_response},
                        )
                    if not any(marker in client_response for marker in REPEATED_RESPONSE_MARKERS):
                        _record(
                            issues,
                            trajectory,
                            turn,
                            "client_repeat_response_missing_marker",
                            client_response,
                        )
                elif kind == "unavailable" and not any(
                    marker in client_response for marker in UNAVAILABLE_RESPONSE_MARKERS
                ):
                    _record(
                        issues,
                        trajectory,
                        turn,
                        "client_unavailable_response_missing_marker",
                        client_response,
                    )
                elif kind == "withheld":
                    target_id = step.action_decision.final.target_id
                    after_facts = {
                        str(item.get("fact_id") or ""): item
                        for item in step.state_after.get("facts", [])
                        if isinstance(item, dict)
                    }
                    after_asked = {
                        str(item) for item in step.state_after.get("asked_targets", [])
                    }
                    if not target_id or target_id not in after_facts:
                        _record(
                            issues,
                            trajectory,
                            turn,
                            "client_withheld_target_missing_from_state",
                            target_id,
                        )
                    else:
                        after_target = after_facts[target_id]
                        if after_target.get("status") != "unknown":
                            _record(
                                issues,
                                trajectory,
                                turn,
                                "client_withheld_target_state_changed",
                                {
                                    "target_id": target_id,
                                    "status": after_target.get("status"),
                                },
                            )
                        if target_id in after_asked:
                            _record(
                                issues,
                                trajectory,
                                turn,
                                "client_withheld_target_marked_asked",
                                target_id,
                            )
                    matching_interactions = [
                        item
                        for item in step.state_after.get("interactions", [])
                        if isinstance(item, dict)
                        and item.get("turn") == turn
                        and item.get("target_id") == target_id
                    ]
                    persisted_interaction = (
                        matching_interactions[-1] if matching_interactions else None
                    )
                    if (
                        persisted_interaction is None
                        or persisted_interaction.get("response_kind") != "withheld"
                        or bool(persisted_interaction.get("new_information"))
                        or bool(persisted_interaction.get("disclosed_fact_ids"))
                    ):
                        _record(
                            issues,
                            trajectory,
                            turn,
                            "client_withheld_interaction_provenance_mismatch",
                            persisted_interaction,
                        )
                if (
                    kind
                    in {
                        "new_hidden_fact",
                        "repeated_hidden_fact",
                        "opening_repeat",
                        "withheld",
                    }
                    and _client_route_valid(step) is not True
                ):
                    _record(
                        issues,
                        trajectory,
                        turn,
                        "client_selected_fact_without_valid_route",
                        {"kind": kind, "route_valid": _client_route_valid(step)},
                    )
                if kind == "unavailable" and _client_route_valid(step) is not True:
                    _record(
                        issues,
                        trajectory,
                        turn,
                        "client_unavailable_without_valid_empty_route",
                        {"kind": kind, "route_valid": _client_route_valid(step)},
                    )
                if kind == "contract_fallback" and _client_route_valid(step) is not False:
                    _record(
                        issues,
                        trajectory,
                        turn,
                        "client_fallback_without_failed_route",
                        {"kind": kind, "route_valid": _client_route_valid(step)},
                    )
                if (kind == "contract_fallback") != step.client_safe_fallback:
                    _record(
                        issues,
                        trajectory,
                        turn,
                        "client_fallback_provenance_mismatch",
                        {"kind": kind, "safe_fallback": step.client_safe_fallback},
                    )
                if trajectory.schema_version >= 15 and (
                    step.visible_state_coverage_attempts
                    or step.visible_state_covered_target_ids
                ):
                    _record(
                        issues,
                        trajectory,
                        turn,
                        "retired_visible_state_coverage_present",
                        "protocol_15_requires_empty_compatibility_fields",
                    )
                elif trajectory.schema_version >= 13:
                    applied_coverage = sorted(
                        item.target_id
                        for item in step.visible_state_coverage_attempts
                        if item.applied
                    )
                    persisted_coverage = sorted(step.visible_state_covered_target_ids)
                    if applied_coverage != persisted_coverage:
                        _record(
                            issues,
                            trajectory,
                            turn,
                            "visible_state_coverage_provenance_mismatch",
                            {
                                "applied_attempts": applied_coverage,
                                "persisted": persisted_coverage,
                            },
                        )
                    if persisted_coverage and kind != "new_hidden_fact":
                        _record(
                            issues,
                            trajectory,
                            turn,
                            "visible_state_coverage_without_new_visible_fact",
                            {"kind": kind, "covered": persisted_coverage},
                        )
                    before_facts = {
                        str(item.get("fact_id") or ""): item
                        for item in step.state_before.get("facts", [])
                        if isinstance(item, dict)
                    }
                    proposed_facts = {
                        item.fact_id: item.model_dump(mode="json")
                        for item in step.state_patch.observations
                    }
                    after_facts = {
                        str(item.get("fact_id") or ""): item
                        for item in step.state_after.get("facts", [])
                        if isinstance(item, dict)
                    }
                    for attempt in step.visible_state_coverage_attempts:
                        if (
                            not attempt.parse_valid
                            or attempt.applied
                            != (
                                attempt.answers_target
                                and attempt.deterministic_compatible is not False
                                and not attempt.deterministic_compatibility_violations
                            )
                        ):
                            _record(
                                issues,
                                trajectory,
                                turn,
                                "visible_state_coverage_invalid_decision",
                                attempt.model_dump(mode="json"),
                            )
                        before = before_facts.get(attempt.target_id) or proposed_facts.get(
                            attempt.target_id
                        )
                        if before is None or before.get("status") != "unknown":
                            _record(
                                issues,
                                trajectory,
                                turn,
                                "visible_state_coverage_invalid_target",
                                attempt.target_id,
                            )
                        if attempt.applied:
                            after = after_facts.get(attempt.target_id) or {}
                            if (
                                after.get("status") != "client_claimed"
                                or after.get("value") != client_response
                            ):
                                _record(
                                    issues,
                                    trajectory,
                                    turn,
                                    "visible_state_coverage_not_persisted",
                                    attempt.target_id,
                                )
            else:
                # Compatibility audit for pre-protocol-12 artifacts.  O identifiers
                # were historically mixed into the disclosure namespace.
                if len(selected_ids) > 1:
                    _record(
                        issues,
                        trajectory,
                        turn,
                        "client_multiple_selected_facts",
                        selected_ids,
                    )
                if selected_ids:
                    selected_id = selected_ids[0]
                    if _client_route_valid(step) is not True:
                        _record(
                            issues,
                            trajectory,
                            turn,
                            "client_selected_fact_without_valid_route",
                            {
                                "selected": selected_id,
                                "legacy_relevance_attempts": len(
                                    step.legacy_client_relevance_attempts
                                ),
                                "route_valid": _client_route_valid(step),
                            },
                        )
                    if selected_id not in valid_fact_ids:
                        _record(
                            issues,
                            trajectory,
                            turn,
                            "client_invalid_selected_fact_id",
                            selected_id,
                        )
                    else:
                        selected_index = next(
                            index
                            for index, fact in enumerate(facts)
                            if str(fact.get("fact_id") or "") == selected_id
                        )
                        disclosed_before = disclosed_fact_indices(facts, grounding_history)
                        grounded = beliefs[selected_index] in client_response
                        repeated = selected_index in disclosed_before and any(
                            marker in client_response for marker in REPEATED_RESPONSE_MARKERS
                        )
                        if not grounded and not repeated:
                            _record(
                                issues,
                                trajectory,
                                turn,
                                "client_response_not_grounded_in_selected_belief",
                                {"selected": selected_id, "response": client_response},
                            )
                elif not any(marker in client_response for marker in UNAVAILABLE_RESPONSE_MARKERS):
                    _record(
                        issues,
                        trajectory,
                        turn,
                        "client_ungrounded_empty_selection_response",
                        client_response,
                    )
            if re.search(r"[a-z]+_[a-z_]+", client_response):
                _record(
                    issues,
                    trajectory,
                    turn,
                    "snake_case_client_response",
                    client_response,
                )
            for violation in response_violations(client_response):
                _record(issues, trajectory, turn, f"client_{violation}", client_response)
            grounding_history.append((question or "", client_response))

        for result in step.verifier_results:
            if not result.passed and result.severity in {"error", "severe"}:
                _record(
                    issues,
                    trajectory,
                    turn,
                    "verifier_failure",
                    f"{result.validator_id}:{result.severity}:{result.detail}",
                )
    return issues


def official_evaluation_health_report(
    trajectories: list[ResearchTrajectory],
    evaluator_cases: dict[str, dict[str, Any]],
    *,
    expected_run_id: str | None = None,
) -> dict[str, Any]:
    """Keep a safe memo-renderer failure as an observed evaluation outcome.

    The ordinary health report already retains emergency-horizon trajectories as
    genuine policy outcomes in training and evaluation.  Official evaluation also
    keeps a deterministic memo renderer fallback when the resulting memo itself is
    healthy; resampling it away would bias the comparison.  Policy fallbacks and
    all other process defects remain blocking.
    """

    report = trajectory_health_report(
        trajectories,
        evaluator_cases,
        expected_run_id=expected_run_id,
    )
    by_id = {item.trajectory_id: item for item in trajectories}
    observed: list[dict[str, Any]] = []
    blocking: list[dict[str, Any]] = []
    for issue in report["issues"]:
        trajectory = by_id[str(issue["trajectory_id"])]
        scoreable = (
            issue["code"] == "memo_fallback_used"
            and trajectory.memo_safe_fallback
            and not trajectory.memo_health_violations
            and not trajectory.error
        )
        (observed if scoreable else blocking).append(issue)
    observed_counts = dict(sorted(Counter(item["code"] for item in observed).items()))
    report["issues"] = blocking
    report["blocking_issue_count"] = len(blocking)
    report["counts"] = dict(sorted(Counter(item["code"] for item in blocking).items()))
    report["issues_truncated"] = 0
    report["healthy"] = not blocking
    report["quality_diagnostics"]["observed_terminal_outcomes"] = {
        "count": len(observed),
        "counts": observed_counts,
        "trajectory_ids": sorted({str(item["trajectory_id"]) for item in observed}),
        "disposition": "score_as_observed_without_resampling",
    }
    return report


def trajectory_health_report(
    trajectories: list[ResearchTrajectory],
    evaluator_cases: dict[str, dict[str, Any]],
    *,
    require_current_contract: bool = True,
    expected_run_id: str | None = None,
) -> dict[str, object]:
    """Build a persisted pre-scoring gate report for a complete rollout matrix."""

    issues = [
        issue
        for trajectory in trajectories
        for issue in trajectory_health_issues(
            trajectory,
            evaluator_cases[trajectory.case_id],
            require_current_contract=require_current_contract,
            expected_run_id=expected_run_id,
        )
    ]
    counts: dict[str, int] = {}
    for issue in issues:
        counts[issue.code] = counts.get(issue.code, 0) + 1
    semantic_repetitions = [
        {
            "trajectory_id": trajectory.trajectory_id,
            "turn": step.turn,
            "selected": (
                step.client_selected_fact_ids[0]
                if step.client_selected_fact_ids
                else step.client_opening_reference_ids[0]
                if step.client_opening_reference_ids
                else None
            ),
            "response_kind": step.client_response_kind,
            "question": step.rendered_question,
        }
        for trajectory in trajectories
        for step in trajectory.steps
        if step.client_response
        and (
            step.client_response_kind in {"opening_repeat", "repeated_hidden_fact"}
            or (
                trajectory.schema_version < 12
                and step.client_selected_fact_ids
                and any(
                    marker in step.client_response for marker in REPEATED_RESPONSE_MARKERS
                )
            )
        )
    ]
    behavior_warnings: list[dict[str, object]] = []
    emergency_horizon_trajectories = [
        {
            "trajectory_id": trajectory.trajectory_id,
            "turn": trajectory.steps[-1].turn if trajectory.steps else 0,
            "max_turns": trajectory.max_turns,
        }
        for trajectory in trajectories
        if trajectory.status == "max_turns_forced_memo"
    ]
    def add_behavior_warning(
        trajectory: ResearchTrajectory,
        seen_warning_keys: set[tuple[int, str]],
        turn: int,
        code: str,
        detail: object,
    ) -> None:
        raw_code = str(code).removeprefix("warning:model_behavior:")
        key = (turn, raw_code)
        if key in seen_warning_keys:
            return
        seen_warning_keys.add(key)
        behavior_warnings.append(
            {
                "code": raw_code,
                "trajectory_id": trajectory.trajectory_id,
                "turn": turn,
                "detail": str(detail)[:1000],
            }
        )

    for trajectory in trajectories:
        seen_warning_keys: set[tuple[int, str]] = set()

        if trajectory.status == "abstained" and trajectory.steps:
            final_state = trajectory.steps[-1].state_after
            substantive = [
                fact
                for fact in final_state.get("facts", [])
                if fact.get("fact_id") not in NON_SUBSTANTIVE_FACT_IDS
                and fact.get("status") in {"client_claimed", "corroborated", "disputed"}
            ]
            if substantive:
                add_behavior_warning(
                    trajectory,
                    seen_warning_keys,
                    trajectory.steps[-1].turn,
                    "abstention_with_substantive_visible_state",
                    [fact.get("fact_id") for fact in substantive],
                )

        seen_questions: set[str] = set()
        for step in trajectory.steps:
            for finding in [
                *step.policy_health_violations,
                *step.post_skill_health_violations,
            ]:
                if policy_behavior_issue_is_soft(finding):
                    add_behavior_warning(
                        trajectory,
                        seen_warning_keys,
                        step.turn,
                        finding,
                        step.rendered_question or finding,
                    )
            question = step.rendered_question
            if question:
                question_key = _normalized(question)
                if question_key in seen_questions:
                    add_behavior_warning(
                        trajectory,
                        seen_warning_keys,
                        step.turn,
                        "exact_repeated_question",
                        question,
                    )
                seen_questions.add(question_key)
                if question.startswith("请补充一个尚未说明"):
                    add_behavior_warning(
                        trajectory,
                        seen_warning_keys,
                        step.turn,
                        "generic_fallback_question",
                        question,
                    )
                for finding in action_question_quality_violations(
                    StructuredAction(action_type="ask", content=question)
                ):
                    if policy_behavior_issue_is_soft(finding):
                        add_behavior_warning(
                            trajectory,
                            seen_warning_keys,
                            step.turn,
                            finding,
                            question,
                        )
            for result in step.verifier_results:
                if not result.passed and result.severity == "warning":
                    add_behavior_warning(
                        trajectory,
                        seen_warning_keys,
                        step.turn,
                        f"verifier_warning:{result.validator_id}",
                        result.detail,
                    )
    behavior_warning_counts: dict[str, int] = {}
    for warning in behavior_warnings:
        code = str(warning["code"])
        behavior_warning_counts[code] = behavior_warning_counts.get(code, 0) + 1
    safe_partial_agendas = [
        {
            "trajectory_id": trajectory.trajectory_id,
            "attempts": len(trajectory.opening_agenda_attempts),
            "retained_targets": len(trajectory.opening_inquiry_agenda.observations),
            "last_violations": (
                trajectory.opening_agenda_attempts[-1].health_violations
                if trajectory.opening_agenda_attempts
                else []
            ),
        }
        for trajectory in trajectories
        if trajectory.opening_agenda_safe_partial
    ]
    visible_state_coverage = [
        {
            "trajectory_id": trajectory.trajectory_id,
            "turn": step.turn,
            "target_ids": list(step.visible_state_covered_target_ids),
        }
        for trajectory in trajectories
        for step in trajectory.steps
        if step.visible_state_covered_target_ids
    ]
    repaired_pre_skill_proposals = [
        {
            "trajectory_id": trajectory.trajectory_id,
            "turn": step.turn,
            "violations": list(step.policy_health_violations),
            "activated_skill_ids": list(step.action_decision.activated_skill_ids),
        }
        for trajectory in trajectories
        for step in trajectory.steps
        if blocking_policy_health_violations(step.policy_health_violations)
        and step.action_decision.activated_skill_ids
        and not blocking_policy_health_violations(step.post_skill_health_violations)
        and step.action_decision.final != step.proposed_action
    ]
    return {
        "schema_version": 2,
        "healthy": not issues,
        "trajectory_count": len(trajectories),
        "visible_state_coverage_application_count": len(visible_state_coverage),
        "visible_state_coverage_applications": visible_state_coverage,
        "blocking_issue_count": len(issues),
        "counts": dict(sorted(counts.items())),
        "issues": [issue.as_dict() for issue in issues[:100]],
        "issues_truncated": max(0, len(issues) - 100),
        # A semantically repeated question is a genuine policy-quality defect and is
        # penalized by the reward.  It is not a grounding/process corruption: keeping
        # it scoreable is necessary for the teacher to observe and improve the policy.
        "quality_diagnostics": {
            "model_behavior_warning_count": len(behavior_warnings),
            "model_behavior_warning_counts": dict(sorted(behavior_warning_counts.items())),
            "model_behavior_warnings": behavior_warnings[:100],
            "model_behavior_warnings_truncated": max(0, len(behavior_warnings) - 100),
            "client_semantic_repetition_no_new_information": len(semantic_repetitions),
            "opening_agenda_safe_partial_recovery": len(safe_partial_agendas),
            "skill_repaired_pre_skill_proposal": len(repaired_pre_skill_proposals),
            "emergency_turn_ceiling_reached_count": len(
                emergency_horizon_trajectories
            ),
            "emergency_turn_ceiling_reached": emergency_horizon_trajectories[:20],
            "examples": semantic_repetitions[:20],
            "semantic_repetition_examples": semantic_repetitions[:20],
            "opening_agenda_safe_partial_examples": safe_partial_agendas[:20],
            "skill_repaired_pre_skill_examples": repaired_pre_skill_proposals[:20],
        },
    }
