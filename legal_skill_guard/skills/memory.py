"""Prompt-memory delivery for learned legal consultation skills.

The learned intervention is the presence of a fixed, structured skill document
bundle in the frozen lawyer model's context.  Skills are selected once from the
case domain and the same bundle is delivered on every lawyer decision turn.  No
runtime component rewrites the model's proposed action.
"""

from __future__ import annotations

import json

from legal_skill_guard.schemas.skill import SkillContract

# The local serving contract is 16,384 tokens.  Across 7,343 historical policy
# turns, the largest no-skill prompt was 3,742 Qwen tokens.  These conservative
# character ceilings leave room for that observed state/dialogue, chat-template
# overhead and the configured completion while still allowing the expected small
# general+domain library.  They are admission invariants, never runtime truncation
# or retrieval rules.
MAX_POLICY_SKILL_DOCUMENT_CHARACTERS = 2_000
MAX_SESSION_SKILL_MEMORY_CHARACTERS = 8_000

EMPTY_SKILL_MEMORY = (
    "本会话没有已验收的咨询技能文档。请仅依据客户开场、可见对话和在线状态自主决策。"
)
SKILL_MEMORY_HEADER = (
    "以下是从既往训练轨迹归纳、并经后续未见案件前瞻门禁保留的结构化咨询技能文档。"
    "它们不是案件事实，也不是必须机械执行的命令；请结合当前可见状态自主选择和运用。"
    "不得引用技能来源、不得假设文档中没有出现的客户事实，也不得为了展示技能而延长咨询。"
    "本会话技能包固定不变，系统不会在你作答后调用规则引擎修改动作："
)


def applicable_skill_documents(
    skills: list[SkillContract],
    *,
    domain: str,
) -> list[SkillContract]:
    """Return the stable session-level skill bundle for one visible domain."""

    return sorted(
        (
            skill
            for skill in skills
            if skill.status == "active" and skill.domain in {"general", domain}
        ),
        key=lambda skill: skill.skill_id,
    )


def policy_skill_document(skill: SkillContract) -> dict[str, object]:
    """Project policy-facing knowledge without provenance or selection outcomes."""

    return {
        "skill_id": skill.skill_id,
        "name": skill.name,
        "domain": skill.domain,
        "objective": skill.objective,
        "description": skill.description,
        "applicability_cues": skill.applicability_cues,
        "procedure": skill.procedure,
        "question_guidance": skill.question_guidance,
        "expected_effects": skill.expected_effects,
        "contraindications": skill.contraindications,
        "failure_modes": skill.failure_modes,
    }


def policy_skill_document_character_count(skill: SkillContract) -> int:
    """Measure the exact policy-facing JSON document, excluding private metadata."""

    return len(
        json.dumps(
            policy_skill_document(skill),
            ensure_ascii=False,
            sort_keys=True,
        )
    )


def skill_memory_capacity_issues(skills: list[SkillContract]) -> list[str]:
    """Validate every active general+domain bundle without selecting at runtime."""

    active = [skill for skill in skills if skill.status == "active"]
    issues = [
        f"skill_document_character_budget_exceeded:{skill.skill_id}"
        for skill in active
        if policy_skill_document_character_count(skill)
        > MAX_POLICY_SKILL_DOCUMENT_CHARACTERS
    ]
    domains = {skill.domain for skill in active if skill.domain != "general"} or {
        "general"
    }
    for domain in sorted(domains):
        applicable = applicable_skill_documents(active, domain=domain)
        if not applicable:
            continue
        payload = [policy_skill_document(skill) for skill in applicable]
        rendered = SKILL_MEMORY_HEADER + "\n" + json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
        )
        if len(rendered) > MAX_SESSION_SKILL_MEMORY_CHARACTERS:
            issues.append(f"skill_memory_character_budget_exceeded:{domain}")
    return sorted(set(issues))


def admit_active_skills_by_prompt_capacity(
    baseline: list[SkillContract],
    ordered_candidates: list[SkillContract],
) -> tuple[list[SkillContract], dict[str, list[str]]]:
    """Admit an outcome-blind ordered cohort under the frozen prompt budget.

    Callers choose the immutable precedence order before observing candidate
    effects.  This function never truncates a document and never chooses skills
    from the current dialogue.  It simply prevents individually valid documents
    from becoming an over-capacity ``general + domain`` bundle when combined.
    """

    if any(skill.status != "active" for skill in [*baseline, *ordered_candidates]):
        raise ValueError("prompt-capacity admission requires active skill projections")
    baseline_issues = skill_memory_capacity_issues(baseline)
    if baseline_issues:
        raise ValueError(
            "baseline skill memory already violates capacity: "
            + ", ".join(baseline_issues)
        )
    seen_ids = {skill.skill_id for skill in baseline}
    if len(seen_ids) != len(baseline):
        raise ValueError("baseline skill memory contains duplicate identifiers")

    admitted: list[SkillContract] = []
    rejected: dict[str, list[str]] = {}
    for candidate in ordered_candidates:
        if candidate.skill_id in seen_ids:
            raise ValueError(
                f"prompt-capacity cohort contains duplicate identifier: {candidate.skill_id}"
            )
        seen_ids.add(candidate.skill_id)
        issues = skill_memory_capacity_issues([*baseline, *admitted, candidate])
        if issues:
            rejected[candidate.skill_id] = issues
        else:
            admitted.append(candidate)
    return admitted, rejected


def render_skill_memory(skills: list[SkillContract], *, domain: str) -> tuple[str, list[str]]:
    """Render one fixed skill bundle and return its delivered identifiers."""

    applicable = applicable_skill_documents(skills, domain=domain)
    skill_ids = [skill.skill_id for skill in applicable]
    if not applicable:
        return (EMPTY_SKILL_MEMORY, [])
    issues = skill_memory_capacity_issues(applicable)
    if issues:
        raise ValueError("skill-memory capacity contract failed: " + ", ".join(issues))
    payload = [policy_skill_document(skill) for skill in applicable]
    rendered = SKILL_MEMORY_HEADER + "\n" + json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
    )
    return (rendered, skill_ids)


def parse_rendered_skill_memory(value: str) -> list[str]:
    """Return IDs from an exact renderer product; reject lookalike text."""

    if value == EMPTY_SKILL_MEMORY:
        return []
    prefix = SKILL_MEMORY_HEADER + "\n"
    if not value.startswith(prefix):
        raise ValueError("policy prompt does not contain a current skill-memory document")
    payload = json.loads(value.removeprefix(prefix))
    if not isinstance(payload, list) or any(
        not isinstance(item, dict) or not isinstance(item.get("skill_id"), str)
        for item in payload
    ):
        raise ValueError("skill-memory document payload is invalid")
    skill_ids = [str(item["skill_id"]) for item in payload]
    if skill_ids != sorted(set(skill_ids)):
        raise ValueError("skill-memory document identifiers are not unique and sorted")
    return skill_ids


def extract_rendered_skill_memory(system_prompt: str) -> str:
    """Extract the exact session memory appended to the frozen policy prompt."""

    if system_prompt.endswith(EMPTY_SKILL_MEMORY):
        return EMPTY_SKILL_MEMORY
    marker = SKILL_MEMORY_HEADER + "\n"
    offset = system_prompt.rfind(marker)
    if offset < 0:
        raise ValueError("policy system prompt is missing its skill-memory suffix")
    value = system_prompt[offset:]
    parse_rendered_skill_memory(value)
    return value
