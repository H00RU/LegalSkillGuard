"""Deterministic retrieval, activation and execution for Skill Contracts."""

from __future__ import annotations

import copy
from collections import Counter
from typing import Any

from legal_skill_guard.schemas.action import ActionDecision, StructuredAction
from legal_skill_guard.schemas.skill import Condition, SkillContract
from legal_skill_guard.schemas.state import ConsultationState


def resolve_field(state: ConsultationState, action: StructuredAction, path: str) -> Any:
    if path == "state.candidate_target_repeated":
        return bool(action.target_id and action.target_id in state.asked_targets)
    if path == "state.candidate_target_unavailable":
        return any(
            fact.fact_id == action.target_id and fact.status == "not_available"
            for fact in state.facts
        )
    root: Any
    if path.startswith("state."):
        root = state.model_dump(mode="python")
        parts = path.split(".")[1:]
    elif path.startswith("candidate_action."):
        root = action.model_dump(mode="python")
        parts = path.split(".")[1:]
    else:
        raise ValueError(f"Condition path must start with state. or candidate_action.: {path}")
    for part in parts:
        root = root.get(part) if isinstance(root, dict) else getattr(root, part, None)
    return root


def condition_matches(
    condition: Condition, state: ConsultationState, action: StructuredAction
) -> bool:
    if condition.all:
        return all(condition_matches(child, state, action) for child in condition.all)
    if condition.any:
        return any(condition_matches(child, state, action) for child in condition.any)
    actual = resolve_field(state, action, condition.field or "")
    expected = condition.value
    operations = {
        "eq": lambda: actual == expected,
        "ne": lambda: actual != expected,
        "gt": lambda: actual is not None and actual > expected,
        "gte": lambda: actual is not None and actual >= expected,
        "lt": lambda: actual is not None and actual < expected,
        "lte": lambda: actual is not None and actual <= expected,
        "in": lambda: actual in expected,
        "contains": lambda: expected in actual if actual is not None else False,
        "truthy": lambda: bool(actual) is bool(expected),
    }
    return bool(operations[condition.op or "eq"]())


class SkillEngine:
    def __init__(self, skills: list[SkillContract]) -> None:
        ids = [skill.skill_id for skill in skills]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate skill_id")
        level_order = {"strategic": 0, "functional": 1, "atomic": 2}
        safety_priority = {
            "general.conflict_clarification": 0,
            "general.premature_final_guard": 1,
            "general.belief_fact_separation": 2,
            "general.critical_fact_first": 3,
            "general.dialogue_budget_guard": 4,
            "general.repeated_question_guard": 0,
            "general.unanswerable_fact_fallback": 1,
            "general.evidence_before_conclusion": 2,
            "general.final_grounding_check": 3,
            "general.persona_adaptation": 4,
        }
        self.skills = sorted(
            skills,
            key=lambda skill: (
                level_order[skill.level],
                safety_priority.get(skill.skill_id, 100),
                skill.skill_id,
            ),
        )
        self.activations: Counter[str] = Counter()

    def retrieve(self, state: ConsultationState, action: StructuredAction) -> list[SkillContract]:
        del action
        return [
            skill
            for skill in self.skills
            if skill.status == "active" and skill.domain in {"general", state.domain}
        ]

    def activate(
        self,
        candidates: list[SkillContract],
        state: ConsultationState,
        action: StructuredAction,
    ) -> list[SkillContract]:
        active: list[SkillContract] = []
        levels: Counter[str] = Counter()
        for skill in candidates:
            if self.activations[skill.skill_id] >= skill.guardrails.max_activations_per_session:
                continue
            if any(condition_matches(c, state, action) for c in skill.guardrails.disable_if):
                continue
            if not all(condition_matches(c, state, action) for c in skill.preconditions):
                continue
            if levels[skill.level] >= 1:
                continue
            active.append(skill)
            levels[skill.level] += 1
        return active

    def apply(self, state: ConsultationState, action: StructuredAction) -> ActionDecision:
        candidates = self.retrieve(state, action)
        final = action.model_copy(deep=True)
        changes: list[dict[str, object]] = []
        blocked: list[str] = []
        executed: list[SkillContract] = []
        levels: Counter[str] = Counter()
        for skill in candidates:
            if self.activations[skill.skill_id] >= skill.guardrails.max_activations_per_session:
                continue
            if levels[skill.level] >= 1:
                continue
            if any(condition_matches(c, state, final) for c in skill.guardrails.disable_if):
                continue
            if not all(condition_matches(c, state, final) for c in skill.preconditions):
                continue
            before = final.model_dump(mode="python")
            operation = skill.operation
            if operation.type == "allow":
                pass
            elif operation.type == "block":
                blocked.append(skill.skill_id)
                final = StructuredAction(
                    action_type="abstain",
                    target_type="session",
                    reason=operation.reason or "blocked_by_skill",
                    content="现有信息不足，暂不作确定性结论。",
                )
            elif operation.type in {"replace_type", "replace_type_and_target"}:
                final.action_type = operation.new_action_type  # type: ignore[assignment]
                final.content = ""
            elif operation.type == "force_abstain":
                final.action_type = "abstain"
                final.target_type = "session"
                final.reason = operation.reason or "forced_abstain"
                final.content = "现有可见信息不足，以下仅提供条件性分析。"
            elif operation.type == "request_state":
                final.action_type = "clarify"
                final.reason = operation.reason or "state_required"
                final.content = ""
            if operation.type in {"replace_target", "replace_type_and_target"}:
                target_replaced = self._replace_target(
                    final,
                    operation.target_selector,
                    operation.target_type,
                    operation.target_id,
                    state,
                )
                if target_replaced:
                    final.content = ""
                elif operation.type == "replace_target":
                    final = StructuredAction(
                        action_type="abstain",
                        target_type="session",
                        reason="no_safe_alternative_target",
                        content="客户已无法提供其他关键事实，以下仅作条件性分析。",
                    )
            if operation.type == "add_constraint" and operation.constraint:
                final.constraints = list(dict.fromkeys([*final.constraints, operation.constraint]))
            after = final.model_dump(mode="python")
            if before != after:
                changes.append({"skill_id": skill.skill_id, "before": before, "after": after})
            self.activations[skill.skill_id] += 1
            levels[skill.level] += 1
            executed.append(skill)
        return ActionDecision(
            original=action,
            final=final,
            retrieved_skill_ids=[skill.skill_id for skill in candidates],
            activated_skill_ids=[skill.skill_id for skill in executed],
            blocked_skill_ids=blocked,
            changes=changes,
        )

    @staticmethod
    def _replace_target(
        action: StructuredAction,
        selector: str | None,
        target_type: str | None,
        target_id: str | None,
        state: ConsultationState,
    ) -> bool:
        selected = target_id
        if selector == "highest_information_gain_unresolved_fact":
            ranks = {"high": 0, "medium": 1, "low": 2}
            candidates = sorted(
                (
                    fact
                    for fact in state.facts
                    if fact.status in {"unknown", "client_claimed", "disputed"}
                    and fact.fact_id not in state.asked_targets
                ),
                key=lambda fact: (ranks[fact.criticality], fact.fact_id),
            )
            selected = candidates[0].fact_id if candidates else None
        elif selector == "first_unresolved_conflict":
            selected = state.unresolved_conflicts[0].fact_id if state.unresolved_conflicts else None
        elif selector == "highest_unverified_claim":
            ranks = {"high": 0, "medium": 1, "low": 2}
            candidates = sorted(
                (fact for fact in state.facts if fact.status == "client_claimed"),
                key=lambda fact: (ranks[fact.criticality], fact.fact_id),
            )
            selected = candidates[0].fact_id if candidates else None
        if selected:
            action.target_type = (target_type or "fact")  # type: ignore[assignment]
            action.target_id = selected
            return True
        return False

    def fork(self) -> SkillEngine:
        return SkillEngine(copy.deepcopy(self.skills))
