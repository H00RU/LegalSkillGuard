"""Compact, complete K-group evidence for global-playbook reflection.

Every healthy training case reaches the teacher scheduler.  The four raw
trajectories remain immutable artifacts, while this module deterministically
compresses their action/outcome structure into one case card.  Relative outcome
differences are retained when present; a tied group is recorded as a tied group,
not discarded or relabelled as a fabricated positive contrast.
"""

from __future__ import annotations

import statistics
from collections import Counter
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from legal_skill_guard.evaluation.semantic import TrajectoryEvaluation
from legal_skill_guard.schemas.experiment import ResearchTrajectory
from legal_skill_guard.schemas.state import NON_SUBSTANTIVE_FACT_IDS


class GroupEvidenceModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TrajectoryGroupEvidencePatch(GroupEvidenceModel):
    """Immutable binding from one teacher card to all four source artifacts."""

    schema_version: Literal[4] = 4
    round_index: int
    partition: str
    group_id: str
    case_id: str
    domain: str
    persona: str
    skill_library_version: str
    trajectory_ids: list[str] = Field(min_length=4, max_length=4)
    trajectory_sha256: dict[str, str]
    evaluation_sha256: dict[str, str]
    card: dict[str, Any]

    @model_validator(mode="after")
    def validate_inner_card_contract(self) -> TrajectoryGroupEvidencePatch:
        """Bind the flexible card body to the current non-evidentiary schema.

        The trajectory summaries intentionally remain a JSON document rather
        than a second hierarchy of Pydantic models.  The security- and replay-
        relevant envelope is nevertheless closed here so an outer schema-4
        wrapper cannot smuggle in a legacy card or a full StatePatch whose
        opening anchors look like evidence.
        """

        card = self.card
        if card.get("schema_version") != 4:
            raise ValueError("group evidence inner card must use schema_version 4")
        for field in (
            "group_id",
            "case_id",
            "domain",
            "persona",
            "skill_library_version",
        ):
            if card.get(field) != getattr(self, field):
                raise ValueError(f"group evidence inner/outer binding mismatch: {field}")
        agenda = card.get("opening_inquiry_agenda")
        if not isinstance(agenda, list):
            raise ValueError("group evidence opening agenda must be a narrow list")
        expected_keys = {"target_id", "label", "criticality", "target_kind"}
        for index, item in enumerate(agenda):
            if not isinstance(item, dict) or set(item) != expected_keys:
                raise ValueError(f"group evidence opening agenda item {index} has invalid shape")
            if not str(item["target_id"]).strip() or not str(item["label"]).strip():
                raise ValueError(f"group evidence opening agenda item {index} is empty")
            if item["criticality"] not in {"high", "medium", "low"}:
                raise ValueError(
                    f"group evidence opening agenda item {index} has invalid criticality"
                )
            if item["target_kind"] not in {"client_fact", "evidence_or_third_party"}:
                raise ValueError(
                    f"group evidence opening agenda item {index} has invalid target kind"
                )
        if card.get("undisclosed_hidden_facts_included") is not False:
            raise ValueError("group evidence card must exclude undisclosed hidden facts")
        summaries = card.get("trajectory_summaries")
        if not isinstance(summaries, list) or len(summaries) != 4:
            raise ValueError("group evidence card must contain four trajectory summaries")
        catalog_keys = {"target_id", "label", "criticality", "target_kind"}
        target_state_keys = {"target_id", "status", "asked"}
        for row_index, row in enumerate(summaries):
            if not isinstance(row, dict):
                raise ValueError(f"group evidence trajectory summary {row_index} is invalid")
            catalog = row.get("visible_target_catalog")
            turns = row.get("turn_outline")
            if not isinstance(catalog, list) or not isinstance(turns, list):
                raise ValueError(
                    f"group evidence trajectory summary {row_index} lacks visible agenda state"
                )
            target_ids: set[str] = set()
            for item_index, item in enumerate(catalog):
                if not isinstance(item, dict) or set(item) != catalog_keys:
                    raise ValueError(
                        "group evidence visible target catalog item has invalid shape: "
                        f"{row_index}/{item_index}"
                    )
                target_id = str(item["target_id"])
                if not target_id or target_id in target_ids:
                    raise ValueError("group evidence visible target catalog IDs are invalid")
                target_ids.add(target_id)
            for turn_index, turn in enumerate(turns):
                if not isinstance(turn, dict):
                    raise ValueError(
                        f"group evidence turn outline {row_index}/{turn_index} is invalid"
                    )
                remaining = turn.get("visible_unresolved_targets_before_action")
                if not isinstance(remaining, list):
                    raise ValueError(
                        "group evidence turn lacks visible unresolved agenda: "
                        f"{row_index}/{turn_index}"
                    )
                for item in remaining:
                    if (
                        not isinstance(item, dict)
                        or set(item) != target_state_keys
                        or str(item["target_id"]) not in target_ids
                        or item["status"] not in {"unknown", "disputed"}
                        or not isinstance(item["asked"], bool)
                    ):
                        raise ValueError(
                            "group evidence visible unresolved target projection is invalid"
                        )
        return self


def _effective_action(step: Any) -> Any:
    final = getattr(getattr(step, "action_decision", None), "final", None)
    return final if final is not None else step.proposed_action


def _target_label(step: Any) -> str:
    action = _effective_action(step)
    target_id = str(getattr(action, "target_id", "") or "")
    for fact in (getattr(step, "state_before", {}) or {}).get("facts", []):
        if isinstance(fact, dict) and str(fact.get("fact_id") or "") == target_id:
            return str(fact.get("label") or target_id)
    return str(getattr(action, "expected_information", "") or target_id)


def _opening_agenda_targets(trajectory: ResearchTrajectory) -> list[dict[str, Any]]:
    """Expose investigation targets without mislabelling opening anchors as evidence.

    The agenda is an opening-grounded, non-binding list of still-unknown targets.
    Its internal ``evidence_labels`` only record which public phrase grounded target
    creation; they are not evidence that the target is true or answered.  Teacher
    cards therefore use the same narrow target projection as the legacy
    trajectory-level teacher view instead of serialising the state patch verbatim.
    """

    agenda = getattr(trajectory, "opening_inquiry_agenda", None)
    observations = list(getattr(agenda, "observations", []) or [])
    return [
        {
            "target_id": str(item.fact_id),
            "label": str(item.label),
            "criticality": str(item.criticality),
            "target_kind": str(item.target_kind),
        }
        for item in observations
    ]


def _visible_target_projection(
    step: Any,
) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    """Project action-time visible agenda metadata, never answers or hidden labels.

    The stable catalog avoids repeating labels on every turn.  The per-turn list
    then records which visible targets remained unresolved and whether the lawyer
    had already tried them.  Together they let the teacher distinguish exhausted
    questioning from an overlooked next step without exposing hidden facts,
    client answers, or a system-selected next action.
    """

    state = getattr(step, "state_before", {}) or {}
    asked = {str(item) for item in state.get("asked_targets", [])}
    catalog: list[dict[str, str]] = []
    remaining: list[dict[str, Any]] = []
    for fact in state.get("facts", []):
        if not isinstance(fact, dict):
            continue
        target_id = str(fact.get("fact_id") or "")
        if not target_id or target_id in NON_SUBSTANTIVE_FACT_IDS:
            continue
        label = str(fact.get("label") or "").strip()
        criticality = str(fact.get("criticality") or "medium")
        target_kind = str(fact.get("target_kind") or "client_fact")
        if not label:
            continue
        catalog.append(
            {
                "target_id": target_id,
                "label": label,
                "criticality": criticality,
                "target_kind": target_kind,
            }
        )
        status = str(fact.get("status") or "unknown")
        if status in {"unknown", "disputed"}:
            remaining.append(
                {
                    "target_id": target_id,
                    "status": status,
                    "asked": target_id in asked,
                }
            )
    catalog.sort(key=lambda item: item["target_id"])
    remaining.sort(key=lambda item: item["target_id"])
    return catalog, remaining


def _trajectory_card(
    trajectory: ResearchTrajectory,
    evaluation: TrajectoryEvaluation,
) -> dict[str, Any]:
    # Teacher evidence is built from interactions that actually reached the
    # client.  A low-quality lawyer question is still an interaction and remains
    # visible here; there is no hidden rejected-action or synthetic termination
    # channel in the current protocol.
    process_steps = [
        step for step in trajectory.steps if getattr(step, "rendered_question", None)
    ]
    new_fact_ids: set[str] = set()
    cumulative = 0
    fact_auc = 0
    outline: list[dict[str, Any]] = []
    full_turns: list[dict[str, Any]] = []
    response_counts: dict[str, int] = {}
    behavior_warning_counts: Counter[str] = Counter()
    rejected_attempt_violation_counts: Counter[str] = Counter()
    policy_repair_turn_count = 0
    policy_attempt_count = 0
    first_new_fact_turn: int | None = None
    visible_target_catalog: dict[str, dict[str, str]] = {}
    for step in trajectory.steps:
        policy_attempts = list(getattr(step, "policy_attempts", []) or [])
        policy_attempt_count += len(policy_attempts)
        policy_repair_turn_count += int(len(policy_attempts) > 1)
        for attempt in policy_attempts[:-1]:
            for issue in dict.fromkeys(
                str(item).removeprefix("warning:model_behavior:")
                for item in (getattr(attempt, "health_violations", []) or [])
            ):
                if issue:
                    rejected_attempt_violation_counts[issue.split(":", 1)[0]] += 1
    for step in process_steps:
        step_catalog, unresolved_before_action = _visible_target_projection(step)
        for item in step_catalog:
            target_id = item["target_id"]
            previous = visible_target_catalog.setdefault(target_id, item)
            if previous != item:
                raise ValueError(
                    "visible target metadata changed within one trajectory: " + target_id
                )
        delivered = bool(step.rendered_question)
        kind = str(step.client_response_kind or "blocked_pre_client")
        if delivered:
            response_counts[kind] = response_counts.get(kind, 0) + 1
        disclosed = (
            sorted(str(item) for item in step.client_selected_fact_ids)
            if delivered and kind == "new_hidden_fact"
            else []
        )
        before = len(new_fact_ids)
        new_fact_ids.update(disclosed)
        gained = len(new_fact_ids) - before
        if delivered:
            cumulative += gained
            fact_auc += cumulative
        if gained and first_new_fact_turn is None:
            first_new_fact_turn = int(step.turn)
        action = _effective_action(step)
        for issue in dict.fromkeys(
            str(item).removeprefix("warning:model_behavior:")
            for item in (getattr(step, "post_skill_health_violations", []) or [])
        ):
            if issue:
                behavior_warning_counts[issue.split(":", 1)[0]] += 1
        compact = {
            "turn": int(step.turn),
            "action_type": str(action.action_type),
            "target_kind": str(getattr(action, "target_type", "") or ""),
            "target_label": _target_label(step),
            "question": str(step.rendered_question or ""),
            "delivered_to_client": delivered,
            "response_kind": kind,
            "new_disclosed_fact_count": gained,
            "visible_unresolved_targets_before_action": unresolved_before_action,
        }
        outline.append(compact)
        full_turns.append(
            {
                **compact,
                "client_response": str(step.client_response or ""),
            }
        )
    questions = sum(bool(step.rendered_question) for step in process_steps)
    safety = evaluation.safety_metrics
    hard_safety_flags = sorted(
        name
        for name, value in {
            "unsupported_claim": safety.unsupported_claim_rate,
            "belief_as_fact": safety.belief_as_fact_rate,
            "hidden_field_leak": float(bool(safety.hidden_field_leak)),
        }.items()
        if float(value) > 0
    )
    process_failure_flags = sorted(
        name
        for name, value in {
            "premature_final": safety.premature_final_rate,
            "emergency_turn_ceiling": float(
                getattr(trajectory, "status", "") == "max_turns_forced_memo"
            ),
            "repeated_question": safety.repeated_question_rate,
            "policy_fallback": evaluation.operational_metrics.policy_fallback_rate,
            "client_fallback": evaluation.operational_metrics.client_fallback_rate,
        }.items()
        if float(value) > 0
    )
    wasted = sum(
        response_counts.get(kind, 0)
        for kind in ("unavailable", "opening_repeat", "repeated_hidden_fact")
    )
    facts = len(new_fact_ids)
    # Hard legal-safety failures dominate. Within that boundary, actual facts
    # dominate efficiency; repeated and unavailable responses remain explicit
    # process failures but do not erase facts already elicited earlier.
    rank_vector = [
        -len(hard_safety_flags),
        facts,
        float(evaluation.reward.final_reward),
        -wasted,
        -questions,
        fact_auc,
    ]
    return {
        "trajectory_id": trajectory.trajectory_id,
        "sample_index": trajectory.sample_index,
        "final_reward": evaluation.reward.final_reward,
        "rank_vector": rank_vector,
        "new_fact_count": facts,
        "question_count": questions,
        "facts_per_question": round(facts / questions, 6) if questions else 0.0,
        "first_new_fact_turn": first_new_fact_turn,
        "fact_acquisition_auc": fact_auc,
        "response_kind_counts": dict(sorted(response_counts.items())),
        "terminal_status": getattr(trajectory, "status", "unknown"),
        "terminal_reason": (
            str(trajectory.steps[-1].stop_gate_reason or "") if trajectory.steps else ""
        ),
        "behavior_warning_counts": dict(sorted(behavior_warning_counts.items())),
        "rejected_attempt_violation_counts": dict(
            sorted(rejected_attempt_violation_counts.items())
        ),
        "policy_repair_turn_count": policy_repair_turn_count,
        "policy_attempt_count": policy_attempt_count,
        "visible_target_catalog": [
            visible_target_catalog[target_id] for target_id in sorted(visible_target_catalog)
        ],
        "hard_safety_flags": hard_safety_flags,
        "process_failure_flags": process_failure_flags,
        "safety_flags": sorted({*hard_safety_flags, *process_failure_flags}),
        "turn_outline": outline,
        "full_turns": full_turns,
    }


def build_group_evidence_card(
    group_id: str,
    members: list[ResearchTrajectory],
    evaluations: dict[str, TrajectoryEvaluation],
) -> dict[str, Any]:
    """Build one teacher-facing card in which every K member contributes."""

    if len(members) != 4:
        raise ValueError("formal group evidence requires exactly four trajectories")
    if len({item.case_id for item in members}) != 1:
        raise ValueError("group evidence spans cases")
    if len({item.domain for item in members}) != 1:
        raise ValueError("group evidence spans domains")
    if len({item.persona for item in members}) != 1:
        raise ValueError("group evidence spans personas")
    if len({item.skill_library_version for item in members}) != 1:
        raise ValueError("group evidence spans skill libraries")
    rows = [
        _trajectory_card(item, evaluations[item.trajectory_id])
        for item in sorted(members, key=lambda value: value.sample_index)
    ]
    vectors = [tuple(row["rank_vector"]) for row in rows]
    rewards = [float(row["final_reward"]) for row in rows]
    mean = statistics.fmean(rewards)
    std = statistics.pstdev(rewards)
    for row in rows:
        row["group_relative_advantage"] = (
            round((float(row["final_reward"]) - mean) / std, 6) if std > 1.0e-8 else 0.0
        )
    best_vector = max(vectors)
    worst_vector = min(vectors)
    best_ids = [row["trajectory_id"] for row in rows if tuple(row["rank_vector"]) == best_vector]
    worst_ids = [row["trajectory_id"] for row in rows if tuple(row["rank_vector"]) == worst_vector]
    representative_ids = list(dict.fromkeys([best_ids[0], worst_ids[0]]))
    full_by_id = {row["trajectory_id"]: row.pop("full_turns") for row in rows}
    common_failures = [
        kind
        for kind in ("unavailable", "opening_repeat", "repeated_hidden_fact")
        if all(int(row["response_kind_counts"].get(kind, 0)) > 0 for row in rows)
    ]
    trajectory = members[0]
    status_counts = Counter(str(row["terminal_status"]) for row in rows)
    warning_counts: Counter[str] = Counter()
    rejected_attempt_counts: Counter[str] = Counter()
    for row in rows:
        warning_counts.update(
            {str(key): int(value) for key, value in row["behavior_warning_counts"].items()}
        )
        rejected_attempt_counts.update(
            {
                str(key): int(value)
                for key, value in row["rejected_attempt_violation_counts"].items()
            }
        )
    return {
        "schema_version": 4,
        "group_id": group_id,
        "case_id": trajectory.case_id,
        "domain": trajectory.domain,
        "persona": trajectory.persona,
        "opening": trajectory.opening,
        "opening_inquiry_agenda": _opening_agenda_targets(trajectory),
        "skill_library_version": trajectory.skill_library_version,
        "group_size": len(rows),
        "group_relative_status": (
            "process_differentiated" if len(set(vectors)) > 1 else "process_tied"
        ),
        "reward_std": round(std, 6),
        "best_trajectory_ids": best_ids,
        "worst_trajectory_ids": worst_ids,
        "common_failure_types": common_failures,
        "status_counts": dict(sorted(status_counts.items())),
        "zero_new_fact_rate": round(
            sum(int(row["new_fact_count"]) == 0 for row in rows) / len(rows), 6
        ),
        "behavior_warning_counts": dict(sorted(warning_counts.items())),
        "rejected_attempt_violation_counts": dict(
            sorted(rejected_attempt_counts.items())
        ),
        "policy_repair_turn_rate": round(
            sum(int(row["policy_repair_turn_count"]) for row in rows)
            / max(sum(len(row["turn_outline"]) for row in rows), 1),
            6,
        ),
        "trajectory_summaries": rows,
        "representative_full_dialogues": {
            trajectory_id: full_by_id[trajectory_id] for trajectory_id in representative_ids
        },
        "undisclosed_hidden_facts_included": False,
    }


def group_evidence_fingerprint(card: dict[str, Any]) -> str:
    """Stable helper kept local to avoid coupling evidence cards to filenames."""

    from legal_skill_guard.utils.hashing import canonical_json_sha256

    return canonical_json_sha256(card)
