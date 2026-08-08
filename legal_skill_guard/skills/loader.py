"""Load and statically validate immutable YAML Skill Contracts."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from legal_skill_guard.schemas.skill import Condition, SkillContract

ALLOWED_CONDITION_FIELDS = {
    "candidate_action.action_type",
    "candidate_action.target_type",
    "candidate_action.target_id",
    "candidate_action.reason",
    "state.turn",
    "state.domain",
    "state.persona",
    "state.high_critical_unknown_count",
    "state.unresolved_conflict_count",
    "state.client_claimed_high_count",
    "state.corroborated_count",
    "state.all_remaining_facts_not_available",
    "state.candidate_target_repeated",
    "state.candidate_target_unavailable",
}

ALLOWED_READS = {
    "candidate_action",
    "facts.status",
    "facts.criticality",
    "facts.evidence_ids",
    "unresolved_conflicts",
    "asked_targets",
    "turn",
    "max_turns",
    "persona",
    "state.turn",
    "state.domain",
    "state.persona",
    "state.high_critical_unknown_count",
    "state.unresolved_conflict_count",
    "state.client_claimed_high_count",
    "state.corroborated_count",
    "state.all_remaining_facts_not_available",
    "state.candidate_target_repeated",
    "state.candidate_target_unavailable",
}
ALLOWED_ACTION_TYPES = {
    "ask",
    "clarify",
    "verify",
    "retrieve",
    "summarize",
    "final",
    "abstain",
}
ALLOWED_TARGET_TYPES = {"fact", "issue", "evidence", "law", "session", "none"}
ALLOWED_TARGET_SELECTORS = {
    "highest_information_gain_unresolved_fact",
    "first_unresolved_conflict",
    "highest_unverified_claim",
}


def validate_skill_static(skill: SkillContract) -> list[str]:
    issues: list[str] = []
    if "descriptive_snake_case_id" in skill.skill_id or skill.skill_id.startswith("test."):
        issues.append("placeholder_or_test_skill_id")
    for read in skill.reads:
        if read not in ALLOWED_READS:
            issues.append(f"unsupported_read:{read}")

    def visit(condition: object) -> None:
        field = getattr(condition, "field", None)
        if field and field not in ALLOWED_CONDITION_FIELDS:
            issues.append(f"unsupported_condition_field:{field}")
        op = getattr(condition, "op", None)
        value = getattr(condition, "value", None)
        if field in {"candidate_action.target_id", "candidate_action.reason"} and (
            op not in {"truthy", "eq", "ne"} or isinstance(value, str)
        ):
            issues.append(f"over_specific_string_condition:{field}")
        for child in [*getattr(condition, "all", []), *getattr(condition, "any", [])]:
            visit(child)

    for condition in [*skill.preconditions, *skill.guardrails.disable_if]:
        visit(condition)
    operation = skill.operation
    if (
        operation.type in {"replace_type", "replace_type_and_target"}
        and not operation.new_action_type
    ):
        issues.append("replace_type_missing_new_action_type")
    if operation.type == "add_constraint" and not operation.constraint:
        issues.append("add_constraint_missing_constraint")
    if operation.type in {"replace_target", "replace_type_and_target"} and not (
        operation.target_id or operation.target_selector
    ):
        issues.append("replace_target_missing_target")
    if operation.new_action_type and operation.new_action_type not in ALLOWED_ACTION_TYPES:
        issues.append(f"unsupported_new_action_type:{operation.new_action_type}")
    if operation.target_type and operation.target_type not in ALLOWED_TARGET_TYPES:
        issues.append(f"unsupported_target_type:{operation.target_type}")
    if operation.target_selector and operation.target_selector not in ALLOWED_TARGET_SELECTORS:
        issues.append(f"unsupported_target_selector:{operation.target_selector}")
    if operation.target_id:
        issues.append("over_specific_operation_target_id")
    return sorted(set(issues))


def find_structural_duplicates(
    candidate: SkillContract, existing: list[SkillContract]
) -> list[str]:
    """Find contracts with the same executable trigger and intervention."""

    def canonical_conditions(conditions: list[Condition]) -> list[str]:
        return sorted(
            json.dumps(
                item.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
            )
            for item in conditions
        )

    def signature(skill: SkillContract) -> str:
        value = {
            "domain": skill.domain,
            "level": skill.level,
            "preconditions": canonical_conditions(skill.preconditions),
            "operation": skill.operation.model_dump(mode="json", exclude_none=True),
            "disable_if": canonical_conditions(skill.guardrails.disable_if),
        }
        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    target = signature(candidate)
    return sorted(skill.skill_id for skill in existing if signature(skill) == target)


def find_trigger_conflicts(
    candidate: SkillContract, existing: list[SkillContract]
) -> list[str]:
    """Find same-level contracts with identical triggers but different operations."""

    def trigger(skill: SkillContract) -> str:
        conditions = sorted(
            json.dumps(
                item.model_dump(mode="json"), ensure_ascii=False, sort_keys=True
            )
            for item in skill.preconditions
        )
        return json.dumps(conditions, ensure_ascii=False)

    candidate_trigger = trigger(candidate)
    operation = candidate.operation.model_dump(mode="json", exclude_none=True)
    return sorted(
        skill.skill_id
        for skill in existing
        if skill.domain == candidate.domain
        and skill.level == candidate.level
        and trigger(skill) == candidate_trigger
        and skill.operation.model_dump(mode="json", exclude_none=True) != operation
    )


def find_lexical_near_duplicates(
    candidate: SkillContract,
    existing: list[SkillContract],
    *,
    threshold: float = 0.85,
) -> list[str]:
    """Flag near-identical names/descriptions using deterministic character trigrams."""

    def trigrams(skill: SkillContract) -> set[str]:
        text = "".join(f"{skill.name} {skill.description}".lower().split())
        return {text[index : index + 3] for index in range(max(1, len(text) - 2))}

    target = trigrams(candidate)
    matches: list[str] = []
    for skill in existing:
        other = trigrams(skill)
        union = target | other
        similarity = len(target & other) / len(union) if union else 1.0
        if similarity >= threshold:
            matches.append(skill.skill_id)
    return sorted(matches)


def load_skill(path: Path) -> SkillContract:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    skill = SkillContract.model_validate(value)
    issues = validate_skill_static(skill)
    if issues:
        raise ValueError(f"Static skill validation failed for {path}: {issues}")
    return skill


def load_skill_directory(path: Path, *, active_only: bool = False) -> list[SkillContract]:
    skills = [load_skill(item) for item in sorted(path.glob("*.yaml"))]
    ids = [skill.skill_id for skill in skills]
    if len(ids) != len(set(ids)):
        raise ValueError(f"Duplicate skill IDs under {path}")
    return [skill for skill in skills if not active_only or skill.status == "active"]


def render_text_skills(skills: list[SkillContract]) -> str:
    return "\n".join(
        f"- {skill.name}：{skill.description.strip()}"
        for skill in skills
        if skill.status == "active"
    )
