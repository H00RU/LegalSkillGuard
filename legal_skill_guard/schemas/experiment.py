"""Trajectory contract for stateful skill and evolution experiments."""

from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from legal_skill_guard.opening_agenda_contract import (
    opening_agenda_attribute_from_label,
    opening_agenda_fact_id,
    opening_agenda_topic_issue,
    opening_attribute_is_explicitly_answered,
)
from legal_skill_guard.schemas.action import ActionDecision, StructuredAction
from legal_skill_guard.schemas.state import (
    NON_SUBSTANTIVE_FACT_IDS,
    TARGET_KINDS,
    ClientResponseKind,
    DisclosureDecision,
    StatePatch,
)
from legal_skill_guard.schemas.trajectory import Message, TokenUsage
from legal_skill_guard.verifiers.deterministic import VerificationResult


class ExperimentModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


CURRENT_TRAJECTORY_SCHEMA_VERSION = 27
VISIBLE_STATE_PAYLOAD_MARKER = (
    "以下状态只来自可见对话；运行时异常熔断上限不是咨询目标，故不展示：\n"
)


def policy_visible_dialogue_row(
    question: object,
    answer: object,
    response_kind: object,
) -> tuple[str, str] | None:
    """Project one audited client exchange into verbatim policy dialogue.

    A routing-contract failure is an infrastructure outcome, not a client
    statement.  Its step and state-ledger row remain auditable, while its generic
    fallback prose must not become evidence in the next lawyer prompt or memo.
    """

    if question is None or answer is None or response_kind == "contract_fallback":
        return None
    return str(question), str(answer)


def policy_visible_state_projection(
    state: dict[str, Any],
    *,
    fact_presentation_seed: int | None = None,
) -> dict[str, Any]:
    """Project persisted dialogue state into the policy-visible wire payload.

    This is the sole state projection used by both the online writer and the
    trajectory contract.  A seeded training presentation may permute facts only
    within a criticality tier; it never drops or rewrites a fact.
    """

    raw_facts = state.get("facts", [])
    facts = [
        json.loads(json.dumps(item, ensure_ascii=False))
        for item in raw_facts
        if isinstance(item, dict)
        and item.get("fact_id") != "opening_statement"
        and not str(item.get("fact_id") or "").startswith("opening_claim_")
    ]
    if fact_presentation_seed is not None:
        by_criticality: dict[str, list[dict[str, Any]]] = {}
        for item in facts:
            by_criticality.setdefault(str(item.get("criticality") or ""), []).append(item)
        rng = random.Random(fact_presentation_seed)
        facts = []
        for criticality in ("high", "medium", "low"):
            tier = list(by_criticality.pop(criticality, []))
            rng.shuffle(tier)
            facts.extend(tier)
        for criticality in sorted(by_criticality):
            tier = list(by_criticality[criticality])
            rng.shuffle(tier)
            facts.extend(tier)

    interactions = [
        {
            "turn": item.get("turn"),
            "action_type": item.get("action_type"),
            "target_id": item.get("target_id"),
            "response_kind": item.get("response_kind"),
            "new_information": item.get("new_information"),
        }
        for item in state.get("interactions", [])
        if isinstance(item, dict)
    ]
    asked_targets = list(state.get("asked_targets", []))
    return {
        "interaction_count": len(interactions),
        "domain": state.get("domain"),
        "persona": state.get("persona"),
        "issues": json.loads(
            json.dumps(state.get("issues", []), ensure_ascii=False)
        ),
        "facts": facts,
        "evidence": json.loads(
            json.dumps(state.get("evidence", []), ensure_ascii=False)
        ),
        "asked_targets": asked_targets,
        # Questions and answers are already present verbatim as chat messages.
        # This outcome ledger therefore excludes duplicated question text and the
        # simulator-private disclosed_fact_ids while retaining every visible row
        # and every visible field of that row.
        "interactions": interactions,
        "unresolved_conflicts": json.loads(
            json.dumps(state.get("unresolved_conflicts", []), ensure_ascii=False)
        ),
        "risk_flags": list(state.get("risk_flags", [])),
        "information_yield": {
            "new_hidden_fact_turns": sum(
                item.get("response_kind") == "new_hidden_fact" for item in interactions
            ),
            "opening_repeat_turns": sum(
                item.get("response_kind") == "opening_repeat" for item in interactions
            ),
            "repeated_hidden_fact_turns": sum(
                item.get("response_kind") == "repeated_hidden_fact"
                for item in interactions
            ),
            "unavailable_targets": sum(
                item.get("status") == "not_available"
                and item.get("fact_id") in asked_targets
                for item in raw_facts
                if isinstance(item, dict)
            ),
            "contract_fallback_turns": sum(
                item.get("response_kind") == "contract_fallback" for item in interactions
            ),
            "unasked_actionable_targets": sum(
                item.get("status") in {"unknown", "disputed"}
                and item.get("fact_id") not in asked_targets
                and item.get("fact_id") not in NON_SUBSTANTIVE_FACT_IDS
                for item in raw_facts
                if isinstance(item, dict)
            ),
        },
    }


def _policy_visible_facts_match(
    expected: object,
    observed: object,
) -> bool:
    """Accept exact facts or the declared same-tier training presentation."""

    if observed == expected:
        return True
    if not isinstance(expected, list) or not isinstance(observed, list):
        return False
    if not all(isinstance(item, dict) for item in [*expected, *observed]):
        return False
    expected_wire = sorted(
        json.dumps(item, ensure_ascii=False, sort_keys=True) for item in expected
    )
    observed_wire = sorted(
        json.dumps(item, ensure_ascii=False, sort_keys=True) for item in observed
    )
    if observed_wire != expected_wire:
        return False
    rank = {"high": 0, "medium": 1, "low": 2}
    observed_ranks = [rank.get(str(item.get("criticality")), 3) for item in observed]
    return observed_ranks == sorted(observed_ranks)


@dataclass(frozen=True)
class TargetKindProvenanceIssue:
    """One missing, invalid, or contradictory current target-kind lineage."""

    code: Literal[
        "target_kind_missing",
        "target_kind_invalid",
        "target_kind_provenance_mismatch",
    ]
    turn: int
    location: str
    fact_id: str
    actual: object
    expected: str | None = None

    def detail(self) -> dict[str, object]:
        value: dict[str, object] = {
            "location": self.location,
            "fact_id": self.fact_id,
            "actual": self.actual,
        }
        if self.expected is not None:
            value["expected"] = self.expected
        return value


@dataclass(frozen=True)
class CurrentTrajectoryContractIssue:
    """One reason an artifact is not admissible under the active protocol."""

    code: str
    turn: int
    detail: object


def trajectory_target_kind_provenance_issues(
    trajectory: Any,
) -> list[TargetKindProvenanceIssue]:
    """Audit the authored kind lineage without inventing a compatibility default.

    The initial plan, every persisted pre-action fact, every policy observation,
    and every post-action fact share one immutable target-kind namespace.  A
    historical ``None`` remains parseable, but it can never establish or alter
    that lineage.
    """

    issues: list[TargetKindProvenanceIssue] = []
    emitted: set[tuple[object, ...]] = set()
    lineage: dict[str, str] = {}

    def record(
        *,
        code: Literal[
            "target_kind_missing",
            "target_kind_invalid",
            "target_kind_provenance_mismatch",
        ],
        turn: int,
        location: str,
        fact_id: str,
        actual: object,
        expected: str | None = None,
    ) -> None:
        key = (code, turn, location, fact_id, repr(actual), expected)
        if key in emitted:
            return
        emitted.add(key)
        issues.append(
            TargetKindProvenanceIssue(
                code=code,
                turn=turn,
                location=location,
                fact_id=fact_id,
                actual=actual,
                expected=expected,
            )
        )

    def observe(
        *,
        fact_id: object,
        target_kind: object,
        turn: int,
        location: str,
    ) -> None:
        normalized_id = str(fact_id or "")
        if target_kind is None or target_kind == "":
            record(
                code="target_kind_missing",
                turn=turn,
                location=location,
                fact_id=normalized_id,
                actual=target_kind,
            )
            return
        if target_kind not in TARGET_KINDS:
            record(
                code="target_kind_invalid",
                turn=turn,
                location=location,
                fact_id=normalized_id,
                actual=target_kind,
            )
            return
        normalized_kind = str(target_kind)
        prior = lineage.get(normalized_id)
        if prior is not None and prior != normalized_kind:
            record(
                code="target_kind_provenance_mismatch",
                turn=turn,
                location=location,
                fact_id=normalized_id,
                actual=normalized_kind,
                expected=prior,
            )
            return
        lineage[normalized_id] = normalized_kind

    initial_plan = getattr(trajectory, "initial_investigation_plan", None)
    for index, observation in enumerate(getattr(initial_plan, "observations", [])):
        observe(
            fact_id=getattr(observation, "fact_id", ""),
            target_kind=getattr(observation, "target_kind", None),
            turn=0,
            location=f"initial_investigation_plan.observations[{index}]",
        )
    opening_agenda = getattr(trajectory, "opening_inquiry_agenda", None)
    for index, observation in enumerate(getattr(opening_agenda, "observations", [])):
        observe(
            fact_id=getattr(observation, "fact_id", ""),
            target_kind=getattr(observation, "target_kind", None),
            turn=0,
            location=f"opening_inquiry_agenda.observations[{index}]",
        )

    for step_index, step in enumerate(getattr(trajectory, "steps", [])):
        turn = int(getattr(step, "turn", step_index + 1) or step_index + 1)
        for state_name in ("state_before",):
            state = getattr(step, state_name, {})
            facts = state.get("facts", []) if isinstance(state, dict) else []
            if not isinstance(facts, list):
                continue
            for fact_index, fact in enumerate(facts):
                if not isinstance(fact, dict):
                    continue
                observe(
                    fact_id=fact.get("fact_id"),
                    target_kind=fact.get("target_kind"),
                    turn=turn,
                    location=f"steps[{step_index}].{state_name}.facts[{fact_index}]",
                )

        state_patch = getattr(step, "state_patch", None)
        for observation_index, observation in enumerate(getattr(state_patch, "observations", [])):
            observe(
                fact_id=getattr(observation, "fact_id", ""),
                target_kind=getattr(observation, "target_kind", None),
                turn=turn,
                location=(f"steps[{step_index}].state_patch.observations[{observation_index}]"),
            )

        state_after = getattr(step, "state_after", {})
        after_facts = state_after.get("facts", []) if isinstance(state_after, dict) else []
        if isinstance(after_facts, list):
            for fact_index, fact in enumerate(after_facts):
                if not isinstance(fact, dict):
                    continue
                observe(
                    fact_id=fact.get("fact_id"),
                    target_kind=fact.get("target_kind"),
                    turn=turn,
                    location=f"steps[{step_index}].state_after.facts[{fact_index}]",
                )
    return issues


def current_trajectory_contract_issues(
    trajectory: Any,
    *,
    expected_run_id: str | None = None,
) -> list[CurrentTrajectoryContractIssue]:
    """Return the complete reusable admission contract for a current artifact."""

    issues: list[CurrentTrajectoryContractIssue] = []
    schema_version = int(getattr(trajectory, "schema_version", 0) or 0)
    if schema_version != CURRENT_TRAJECTORY_SCHEMA_VERSION:
        issues.append(
            CurrentTrajectoryContractIssue(
                code="trajectory_schema_version_mismatch",
                turn=0,
                detail={
                    "expected": CURRENT_TRAJECTORY_SCHEMA_VERSION,
                    "actual": schema_version,
                },
            )
        )
    actual_run_id = str(getattr(trajectory, "run_id", "") or "")
    if expected_run_id is not None and actual_run_id != expected_run_id:
        issues.append(
            CurrentTrajectoryContractIssue(
                code="trajectory_run_id_mismatch",
                turn=0,
                detail={"expected": expected_run_id, "actual": actual_run_id},
            )
        )
    if str(getattr(trajectory, "status", "")) == "behavior_guard_terminated":
        issues.append(
            CurrentTrajectoryContractIssue(
                code="retired_behavior_guard_terminal_status",
                turn=0,
                detail="archived_reader_compatibility_only",
            )
        )
    if schema_version == CURRENT_TRAJECTORY_SCHEMA_VERSION:
        issues.extend(
            CurrentTrajectoryContractIssue(
                code=item.code,
                turn=item.turn,
                detail=item.detail(),
            )
            for item in trajectory_target_kind_provenance_issues(trajectory)
        )
        delivery_mode = str(getattr(trajectory, "skill_delivery_mode", "") or "")
        exposed = [str(item) for item in getattr(trajectory, "exposed_skill_ids", [])]
        memory_sha = str(getattr(trajectory, "skill_memory_sha256", "") or "")
        planner_exposed = [
            str(item) for item in getattr(trajectory, "planner_exposed_skill_ids", [])
        ]
        planner_memory_sha = str(getattr(trajectory, "planner_skill_memory_sha256", "") or "")
        if len(exposed) != len(set(exposed)) or exposed != sorted(exposed):
            issues.append(
                CurrentTrajectoryContractIssue(
                    code="skill_memory_ids_not_unique_and_sorted",
                    turn=0,
                    detail=exposed,
                )
            )
        if not re.fullmatch(r"[0-9a-f]{64}", memory_sha):
            issues.append(
                CurrentTrajectoryContractIssue(
                    code="skill_memory_sha256_invalid",
                    turn=0,
                    detail=memory_sha,
                )
            )
        if planner_exposed:
            issues.append(
                CurrentTrajectoryContractIssue(
                    code="retired_planner_skill_exposure_present",
                    turn=0,
                    detail=planner_exposed,
                )
            )
        if not re.fullmatch(r"[0-9a-f]{64}", planner_memory_sha):
            issues.append(
                CurrentTrajectoryContractIssue(
                    code="planner_skill_memory_sha256_invalid",
                    turn=0,
                    detail=planner_memory_sha,
                )
            )
        planning_visible_input = list(
            getattr(trajectory, "planning_visible_input", []) or []
        )
        planning_attempts = list(getattr(trajectory, "planning_attempts", []) or [])
        initial_plan = getattr(trajectory, "initial_investigation_plan", None)
        initial_observations = list(getattr(initial_plan, "observations", []) or [])
        if planning_visible_input or planning_attempts or initial_observations or bool(
            getattr(trajectory, "planning_safe_partial", False)
        ):
            issues.append(
                CurrentTrajectoryContractIssue(
                    code="retired_planner_artifact_present",
                    turn=0,
                    detail={
                        "visible_input_count": len(planning_visible_input),
                        "attempt_count": len(planning_attempts),
                        "initial_observation_count": len(initial_observations),
                        "safe_partial": bool(
                            getattr(trajectory, "planning_safe_partial", False)
                        ),
                    },
                )
            )
        opening_agenda = getattr(trajectory, "opening_inquiry_agenda", None)
        opening_agenda_observations = list(
            getattr(opening_agenda, "observations", []) or []
        )
        opening_agenda_visible_input = list(
            getattr(trajectory, "opening_agenda_visible_input", []) or []
        )
        opening_agenda_attempts = list(
            getattr(trajectory, "opening_agenda_attempts", []) or []
        )
        opening_agenda_safe_partial = bool(
            getattr(trajectory, "opening_agenda_safe_partial", False)
        )
        agenda_attempt_contract_valid = bool(opening_agenda_attempts) and bool(
            opening_agenda_visible_input
        )
        empty_agenda_disposition_valid = bool(opening_agenda_observations) or (
            agenda_attempt_contract_valid
            and (
                opening_agenda_safe_partial
                or not list(
                    getattr(opening_agenda_attempts[-1], "health_violations", []) or []
                )
            )
        )
        # Schema 27 formal trajectories always carry the public-opening request
        # and its bounded attempts.  The resulting patch may be empty, but a
        # completely absent agenda artifact is not an audited empty outcome.
        if not agenda_attempt_contract_valid or not empty_agenda_disposition_valid:
            issues.append(
                CurrentTrajectoryContractIssue(
                    code="opening_agenda_artifact_incomplete",
                    turn=0,
                    detail={
                        "observation_count": len(opening_agenda_observations),
                        "visible_input_count": len(opening_agenda_visible_input),
                        "attempt_count": len(opening_agenda_attempts),
                        "safe_partial": opening_agenda_safe_partial,
                    },
                )
            )
        if opening_agenda_visible_input:
            roles = [str(getattr(item, "role", "")) for item in opening_agenda_visible_input]
            contents = [
                str(getattr(item, "content", "")) for item in opening_agenda_visible_input
            ]
            expected_user = "客户公开开场：\n" + str(getattr(trajectory, "opening", ""))
            if roles != ["system", "user"] or contents[-1] != expected_user:
                issues.append(
                    CurrentTrajectoryContractIssue(
                        code="opening_agenda_visible_boundary_invalid",
                        turn=0,
                        detail={
                            "roles": roles,
                            "user_matches_opening": contents[-1:] == [expected_user],
                        },
                    )
                )
        opening_agenda_identities: set[tuple[str, str]] = set()
        for index, observation in enumerate(opening_agenda_observations):
            fact_id = str(getattr(observation, "fact_id", "") or "")
            label = str(getattr(observation, "label", "") or "")
            evidence_labels = list(getattr(observation, "evidence_labels", []) or [])
            anchors = [
                str(item).removeprefix("public_opening_anchor:")
                for item in evidence_labels
                if str(item).startswith("public_opening_anchor:")
            ]
            opening = str(getattr(trajectory, "opening", ""))
            anchor = anchors[0] if len(anchors) == 1 else ""
            attribute = opening_agenda_attribute_from_label(anchor, label)
            identity = (anchor, str(attribute or ""))
            duplicate = identity in opening_agenda_identities
            opening_agenda_identities.add(identity)
            if (
                attribute is None
                or fact_id != opening_agenda_fact_id(label)
                or getattr(observation, "status", None) != "unknown"
                or getattr(observation, "value", None) is not None
                or getattr(observation, "target_kind", None) != "client_fact"
                or float(getattr(observation, "confidence", -1.0)) != 0.5
                or getattr(observation, "criticality", None) != "medium"
                or len(anchors) != 1
                or opening_agenda_topic_issue(anchor, opening) is not None
                or (
                    attribute is not None
                    and opening_attribute_is_explicitly_answered(
                        opening, anchor, attribute
                    )
                )
                or duplicate
            ):
                issues.append(
                    CurrentTrajectoryContractIssue(
                        code="opening_agenda_target_contract_invalid",
                        turn=0,
                        detail={"index": index, "fact_id": fact_id},
                    )
                )
        steps = list(getattr(trajectory, "steps", []) or [])
        completed_dialogue: list[tuple[str, str]] = []
        for step_index, step in enumerate(steps):
            messages = list(getattr(step, "visible_input", []) or [])
            roles = [str(getattr(item, "role", "")) for item in messages]
            contents = [str(getattr(item, "content", "")) for item in messages]
            expected_history: list[tuple[str, str]] = []
            for question, answer in completed_dialogue:
                expected_history.extend([("assistant", question), ("user", answer)])
            observed_history = list(zip(roles[1:-1], contents[1:-1], strict=False))
            failures: list[str] = []
            if len(messages) < 2 or roles[:1] != ["system"] or roles[-1:] != ["user"]:
                failures.append("message_role_envelope")
            if observed_history != expected_history:
                failures.append("prior_dialogue_not_verbatim")

            state_payload: dict[str, Any] | None = None
            if contents:
                marker_offset = contents[-1].find(VISIBLE_STATE_PAYLOAD_MARKER)
                if marker_offset >= 0:
                    raw_payload = contents[-1][
                        marker_offset + len(VISIBLE_STATE_PAYLOAD_MARKER) :
                    ]
                    try:
                        decoded, _ = json.JSONDecoder().raw_decode(raw_payload)
                    except json.JSONDecodeError:
                        decoded = None
                    if isinstance(decoded, dict):
                        state_payload = decoded
            if state_payload is None:
                failures.append("visible_state_payload_missing")
            else:
                state_before = getattr(step, "state_before", {}) or {}
                expected_payload = policy_visible_state_projection(state_before)
                expected_keys = set(expected_payload)
                if set(state_payload) != expected_keys:
                    failures.append("visible_state_keys_drift")
                for key in (
                    "interaction_count",
                    "domain",
                    "persona",
                    "issues",
                    "evidence",
                    "asked_targets",
                    "interactions",
                    "unresolved_conflicts",
                    "risk_flags",
                    "information_yield",
                ):
                    if state_payload.get(key) != expected_payload[key]:
                        failures.append(
                            "interaction_ledger_drift"
                            if key == "interactions"
                            else f"{key}_drift"
                        )
                if not _policy_visible_facts_match(
                    expected_payload["facts"], state_payload.get("facts")
                ):
                    failures.append("facts_drift")
                for key in ("domain", "persona"):
                    if (
                        expected_payload[key] != getattr(trajectory, key, None)
                        or state_payload.get(key) != getattr(trajectory, key, None)
                    ) and f"{key}_drift" not in failures:
                        failures.append(f"{key}_drift")
                if "disclosed_fact_ids" in json.dumps(
                    state_payload, ensure_ascii=False, sort_keys=True
                ):
                    failures.append("private_disclosure_key_exposed")
            if failures:
                issues.append(
                    CurrentTrajectoryContractIssue(
                        code="visible_policy_history_invalid",
                        turn=int(getattr(step, "turn", step_index + 1) or step_index + 1),
                        detail={"step_index": step_index, "failures": failures},
                    )
                )

            dialogue_row = policy_visible_dialogue_row(
                getattr(step, "rendered_question", None),
                getattr(step, "client_response", None),
                getattr(step, "client_response_kind", None),
            )
            if dialogue_row is not None:
                completed_dialogue.append(dialogue_row)

        if opening_agenda_observations and steps:
            first_state = getattr(steps[0], "state_before", {}) or {}
            first_facts = {
                str(item.get("fact_id") or ""): item
                for item in first_state.get("facts", [])
                if isinstance(item, dict)
            }
            propagation_failures: list[dict[str, object]] = []
            for observation in opening_agenda_observations:
                fact_id = str(getattr(observation, "fact_id", "") or "")
                fact = first_facts.get(fact_id)
                if fact is None:
                    propagation_failures.append(
                        {"fact_id": fact_id, "reason": "missing_from_first_state"}
                    )
                    continue
                mismatched = {
                    key: fact.get(key)
                    for key, expected in {
                        "label": str(getattr(observation, "label", "") or ""),
                        "status": "unknown",
                        "value": None,
                        "target_kind": "client_fact",
                        "evidence_ids": [],
                    }.items()
                    if fact.get(key) != expected
                }
                if mismatched:
                    propagation_failures.append(
                        {
                            "fact_id": fact_id,
                            "reason": "state_value_mismatch",
                            "actual": mismatched,
                        }
                    )
            leaked_anchor_evidence = [
                str(item.get("label") or "")
                for item in first_state.get("evidence", [])
                if isinstance(item, dict)
                and str(item.get("label") or "").startswith("public_opening_anchor:")
            ]
            if propagation_failures or leaked_anchor_evidence:
                issues.append(
                    CurrentTrajectoryContractIssue(
                        code="opening_agenda_state_propagation_invalid",
                        turn=int(getattr(steps[0], "turn", 1) or 1),
                        detail={
                            "target_failures": propagation_failures,
                            "opening_anchor_evidence": leaked_anchor_evidence,
                        },
                    )
                )
        if (delivery_mode == "none") != (not exposed):
            issues.append(
                CurrentTrajectoryContractIssue(
                    code="skill_memory_delivery_mode_mismatch",
                    turn=0,
                    detail={"mode": delivery_mode, "exposed_skill_ids": exposed},
                )
            )
        for step_index, step in enumerate(getattr(trajectory, "steps", [])):
            turn = int(getattr(step, "turn", step_index + 1) or step_index + 1)
            continuation = getattr(step, "continuation_decision", None)
            target_attempts = list(getattr(step, "target_selection_attempts", []))
            continuation_attempts = list(getattr(step, "continuation_attempts", []))
            continuation_visible = list(getattr(step, "continuation_visible_input", []))
            if (
                continuation is not None
                or continuation_attempts
                or continuation_visible
                or target_attempts
            ):
                issues.append(
                    CurrentTrajectoryContractIssue(
                        code="retired_factored_policy_artifact_present",
                        turn=turn,
                        detail={
                            "continuation_decision": continuation is not None,
                            "continuation_attempt_count": len(continuation_attempts),
                            "continuation_prompt_count": len(continuation_visible),
                            "target_attempt_count": len(target_attempts),
                        },
                    )
                )
            decision = getattr(step, "action_decision", None)
            retrieved = sorted(str(item) for item in getattr(decision, "retrieved_skill_ids", []))
            # The fixed session documents are visible to the single complete
            # policy action, including terminal actions.
            expected_turn_exposure = exposed
            activated = list(getattr(decision, "activated_skill_ids", []))
            skill_changes = [
                item
                for item in getattr(decision, "changes", [])
                if isinstance(item, dict) and item.get("skill_id")
            ]
            if retrieved != expected_turn_exposure:
                issues.append(
                    CurrentTrajectoryContractIssue(
                        code="turn_skill_memory_exposure_mismatch",
                        turn=turn,
                        detail={"expected": expected_turn_exposure, "actual": retrieved},
                    )
                )
            if (
                activated
                or len(activated) != len(set(activated))
                or any(item not in retrieved for item in activated)
            ):
                issues.append(
                    CurrentTrajectoryContractIssue(
                        code="retired_self_reported_skill_activation_present",
                        turn=turn,
                        detail={
                            "activated_skill_ids": activated,
                        },
                    )
                )
            if skill_changes:
                issues.append(
                    CurrentTrajectoryContractIssue(
                        code="retired_runtime_skill_action_rewrite_observed",
                        turn=turn,
                        detail={"skill_change_count": len(skill_changes)},
                    )
                )
    return issues


def assert_current_trajectory_contract(
    trajectory: Any,
    *,
    expected_run_id: str | None = None,
) -> None:
    """Fail closed before a current artifact enters scoring or evolution."""

    issues = current_trajectory_contract_issues(
        trajectory,
        expected_run_id=expected_run_id,
    )
    if issues:
        summary = "; ".join(f"{item.code}@turn{item.turn}:{item.detail}" for item in issues)
        raise ValueError(f"current trajectory contract failed: {summary}")


class PolicyEnvelope(ExperimentModel):
    state_patch: StatePatch = Field(default_factory=StatePatch)
    action: StructuredAction


class PolicyActionOutput(ExperimentModel):
    """Runtime policy boundary: state is owned by planner/controller, not the policy."""

    action: StructuredAction


class PolicyAttempt(ExperimentModel):
    raw_output: str
    parse_mode: Literal["json", "json_fragment", "fallback"]
    deterministic_changes: list[str] = Field(default_factory=list)
    health_violations: list[str] = Field(default_factory=list)
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    finish_reason: str | None = None


class ContinuationDecision(ExperimentModel):
    """Legacy reader payload for retired factorized-policy trajectories."""

    continue_inquiry: bool
    reason: str = Field(min_length=1, max_length=160)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class ContinuationAttempt(ExperimentModel):
    """Legacy reader payload; current trajectories must leave this absent."""

    raw_output: str
    parse_mode: Literal["json", "json_fragment", "fallback"]
    health_violations: list[str] = Field(default_factory=list)
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    finish_reason: str | None = None


class MemoAttempt(ExperimentModel):
    raw_output: str
    health_violations: list[str] = Field(default_factory=list)
    deterministic_changes: list[str] = Field(default_factory=list)
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    finish_reason: str | None = None


class ClientSelectionAttempt(ExperimentModel):
    raw_output: str
    selected_fact_id: str | None = None
    selected_relation: Literal[
        "direct_answer",
        "partial_answer",
        "premise_correction",
        "not_answer",
    ] | None = None
    deterministic_compatibility_violations: list[str] = Field(default_factory=list)
    attribute_gate_disposition: Literal[
        "not_applicable",
        "passed",
        "rejected",
        "empty_recheck_requested",
    ] = "not_applicable"


class LegacyClientRelevanceAttempt(ExperimentModel):
    """Read-only payload used only when auditing pre-protocol-37 artifacts."""

    raw_output: str
    verifier_model_id: str | None = None
    selected_fact_id: str
    verification_trigger: Literal[
        "selector_candidate",
        "deterministic_direct_answer_recovery_after_empty",
        "deterministic_presupposition_recovery_after_empty",
        "exhaustive_after_empty_cooperative_selection",
        "exhaustive_after_empty_repeated_selection",
    ] = "selector_candidate"
    parse_valid: bool
    answers_question: bool | None = None
    question_actor: str | None = None
    question_predicate: str | None = None
    question_attribute: str | None = None
    candidate_actor: str | None = None
    candidate_predicate: str | None = None
    candidate_attribute: str | None = None
    candidate_assertion_source: (
        Literal[
            "direct_client_fact",
            "reported_other_claim",
            "client_worry_or_inference",
            "document_content",
            "other",
        ]
        | None
    ) = None
    same_actor: bool | None = None
    same_predicate: bool | None = None
    same_attribute: bool | None = None
    proposition_alignment_passed: bool | None = None
    deterministic_compatible: bool | None = None
    # Narrow, auditable override for correcting a false premise about an
    # event/document that the hidden client belief says did not exist.
    deterministic_presupposition_correction: bool = False
    deterministic_direct_answer: bool = False
    deterministic_incremental_over_opening: bool | None = None
    deterministic_compatibility_violations: list[str] = Field(default_factory=list)


class VisibleStateCoverageAttempt(ExperimentModel):
    target_id: str
    target_label: str
    raw_output: str = ""
    verifier_model_id: str | None = None
    model_called: bool
    parse_valid: bool
    answers_target: bool
    deterministic_compatible: bool | None = None
    deterministic_compatibility_violations: list[str] = Field(default_factory=list)
    applied: bool
    request_sha256: str | None = None


class TargetSelectionAttempt(ExperimentModel):
    """Legacy reader payload for retired target-selection-head trajectories.

    ``proposed_*`` remains a plural wire field so historical trajectories can be
    inspected with one reader.  Since schema 21 it must be the singleton mirror of
    ``selected_target_id``; current runs never contain an internal candidate list.

    Current complete-action trajectories never populate this object.  The fields
    remain on the wire solely so historical artifacts can be inspected with one
    reader; the current contract rejects their presence.
    """

    raw_output: str
    parse_mode: Literal["json", "json_fragment", "fallback"]
    selected_skill_ids: list[str] = Field(default_factory=list)
    expanded_skill_cards: list[str] = Field(default_factory=list)
    selected_target_id: str | None = None
    proposed_target_ids: list[str] = Field(default_factory=list)
    proposed_skill_ids_by_target: dict[str, list[str]] = Field(default_factory=dict)
    allowed_target_ids: list[str] = Field(default_factory=list)
    health_violations: list[str] = Field(default_factory=list)
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    finish_reason: str | None = None


class ResearchStep(ExperimentModel):
    turn: int = Field(ge=1)
    visible_input: list[Message]
    # Read-only compatibility fields for pre-unified-action artifacts. Current
    # writers leave all four empty and the current contract enforces that rule.
    continuation_visible_input: list[Message] = Field(default_factory=list)
    continuation_decision: ContinuationDecision | None = None
    continuation_attempts: list[ContinuationAttempt] = Field(default_factory=list)
    target_selection_attempts: list[TargetSelectionAttempt] = Field(default_factory=list)
    state_before: dict[str, object]
    state_patch: StatePatch
    state_after: dict[str, object]
    raw_policy_output: str
    parse_mode: Literal["json", "json_fragment", "fallback"]
    policy_attempts: list[PolicyAttempt] = Field(default_factory=list)
    policy_health_violations: list[str] = Field(default_factory=list)
    post_skill_health_violations: list[str] = Field(default_factory=list)
    proposed_action: StructuredAction
    action_decision: ActionDecision
    rendered_question: str | None = None
    client_response: str | None = None
    client_input_sha256: str | None = None
    client_opening_selection_attempts: list[ClientSelectionAttempt] = Field(default_factory=list)
    client_selection_attempts: list[ClientSelectionAttempt] = Field(default_factory=list)
    client_disclosure_attempts: list[ClientSelectionAttempt] = Field(default_factory=list)
    client_route_decision_valid: bool | None = None
    # Historical input remains parseable for explicit archive audits, but these
    # fields are never serialized into a current trajectory.
    legacy_client_relevance_attempts: list[LegacyClientRelevanceAttempt] = Field(
        default_factory=list,
        validation_alias="client_relevance_attempts",
        exclude=True,
    )
    legacy_client_relevance_passed: bool | None = Field(
        default=None,
        validation_alias="client_relevance_passed",
        exclude=True,
    )
    client_response_kind: ClientResponseKind | None = None
    client_opening_reference_ids: list[str] = Field(default_factory=list)
    # Match and disclosure are distinct axes.  In particular, a withheld turn
    # has a matched hidden fact but no disclosed/selected fact.
    client_matched_fact_ids: list[str] = Field(default_factory=list)
    client_disclosure_decisions: dict[str, DisclosureDecision] = Field(default_factory=dict)
    client_selected_fact_ids: list[str] = Field(default_factory=list)
    # Retired at trajectory protocol 15.  Kept only so historical protocol-13/14
    # artifacts remain interpretable; current runners must persist an empty list.
    visible_state_coverage_attempts: list[VisibleStateCoverageAttempt] = Field(default_factory=list)
    visible_state_covered_target_ids: list[str] = Field(default_factory=list)
    client_safe_fallback: bool = False
    verifier_results: list[VerificationResult] = Field(default_factory=list)
    stop_gate_verdict: str
    stop_gate_reason: str
    token_usage: TokenUsage
    lawyer_finish_reason: str | None = None
    client_finish_reason: str | None = None


class ResearchTrajectory(ExperimentModel):
    schema_version: int = CURRENT_TRAJECTORY_SCHEMA_VERSION
    trajectory_id: str
    group_id: str | None = None
    sample_index: int = 0
    run_id: str
    method: Literal[
        "control_no_library",
        "legal_skill_evolve",
        "training_policy_sample",
        "luna_direct",
        "expel_adapted",
    ]
    partition: str
    case_id: str
    domain: str = "general"
    jurisdiction: Literal["CN"] = "CN"
    persona: str
    seed: int
    model_id: str
    model_revision: str
    skill_library_version: str
    skill_delivery_mode: Literal["none", "prompt_memory", "experience_memory"] = "none"
    exposed_skill_ids: list[str] = Field(default_factory=list)
    skill_memory_sha256: str = ""
    # Retired in schema 25.  Kept empty only so older artifacts remain readable;
    # current admission rejects any active planning prompt, attempt, or exposure.
    planner_exposed_skill_ids: list[str] = Field(default_factory=list)
    planner_skill_memory_sha256: str = ""
    # ``behavior_guard_terminated`` is accepted only to read archived runs.  No
    # current execution path emits it and no formal endpoint selects it.
    status: Literal[
        "memo_submitted",
        "abstained",
        "behavior_guard_terminated",
        "max_turns_forced_memo",
        "diagnostic_interaction_limit",
        "diagnostic_final",
        "diagnostic_abstain",
        "error",
    ]
    opening: str
    max_turns: int
    steps: list[ResearchStep]
    # Retired pre-dialogue planner compatibility fields (schema 25).
    initial_investigation_plan: StatePatch = Field(default_factory=StatePatch)
    planning_visible_input: list[Message] = Field(default_factory=list)
    planning_attempts: list[PolicyAttempt] = Field(default_factory=list)
    planning_safe_partial: bool = False
    # Retired at protocol 15; current artifacts must leave these compatibility
    # fields empty/zero rather than importing a historical cross-slot closure.
    initial_visible_state_coverage_attempts: list[VisibleStateCoverageAttempt] = Field(
        default_factory=list
    )
    initial_visible_state_covered_target_ids: list[str] = Field(default_factory=list)
    initial_visible_state_coverage_token_usage: TokenUsage = Field(default_factory=TokenUsage)
    # Schema 27 common infrastructure.  This is not the retired skill-conditioned
    # planner above: it is generated once from the public opening only, is identical
    # across comparison arms/K members, supplies no action order, and remains open
    # through the ordinary new_visible_gap policy action.
    opening_inquiry_agenda: StatePatch = Field(default_factory=StatePatch)
    opening_agenda_visible_input: list[Message] = Field(default_factory=list)
    opening_agenda_attempts: list[PolicyAttempt] = Field(default_factory=list)
    opening_agenda_safe_partial: bool = False
    memo: str
    memo_attempts: list[MemoAttempt] = Field(default_factory=list)
    memo_health_violations: list[str] = Field(default_factory=list)
    memo_safe_fallback: bool = False
    elapsed_seconds: float = Field(ge=0)
    created_at: datetime
    error: str | None = None

    @field_validator("schema_version")
    @classmethod
    def require_current_schema_for_active_construction(
        cls,
        value: int,
        info: ValidationInfo,
    ) -> int:
        """Prevent active code from labeling a new object as a legacy protocol.

        Historical parsing is an explicit operation so old artifacts remain
        inspectable without allowing an ordinary constructor or resume path to
        produce anything except the current contract.
        """

        context = info.context if isinstance(info.context, dict) else {}
        if value != CURRENT_TRAJECTORY_SCHEMA_VERSION and not context.get(
            "allow_historical_trajectory_schema"
        ):
            raise ValueError(
                "active ResearchTrajectory requires schema_version "
                f"{CURRENT_TRAJECTORY_SCHEMA_VERSION}; use model_validate_historical "
                "for a read-only legacy audit"
            )
        return value

    @classmethod
    def model_validate_historical(cls, value: Any) -> Self:
        """Parse a legacy trajectory only for explicit read-only audit code."""

        return cls.model_validate(
            value,
            context={"allow_historical_trajectory_schema": True},
        )

    @classmethod
    def model_validate_historical_json(
        cls,
        value: str | bytes | bytearray,
    ) -> Self:
        """JSON counterpart of :meth:`model_validate_historical`."""

        return cls.model_validate_json(
            value,
            context={"allow_historical_trajectory_schema": True},
        )
