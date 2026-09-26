"""Direct prompt-memory delivery for one learned legal-consultation playbook.

The durable research artifact remains a full, auditable skill document.  Its
actionable fields are projected into one compact cross-domain playbook delivered
with every visible policy state.  The same frozen lawyer directly authors the next
action; no trigger engine, domain router, retriever or action rewriter is involved.
"""

from __future__ import annotations

import json

from legal_skill_guard.schemas.skill import SkillContract

# The local serving contract is 16,384 tokens.  Across 7,343 historical policy
# turns, the largest no-skill prompt was 3,742 Qwen tokens.  These conservative
# character ceilings leave room for that observed state/dialogue, chat-template
# overhead and the configured completion while still allowing the one compact
# global playbook.  They are admission invariants, never runtime truncation or
# retrieval rules.
MAX_POLICY_SKILL_DOCUMENT_CHARACTERS = 3_000
MAX_SESSION_SKILL_MEMORY_CHARACTERS = 4_000
GLOBAL_PLAYBOOK_SKILL_ID = "general.legal_fact_elicitation_playbook"

EMPTY_SKILL_MEMORY = (
    "本会话的当前工作库没有适用咨询技能文档。请仅依据客户开场、可见对话和在线状态自主决策。"
)
EMPTY_PLANNER_SKILL_MEMORY = (
    "本会话的当前工作库没有咨询技能文档。请仅依据客户开场建立事实调查计划。"
)
SKILL_MEMORY_HEADER = (
    "以下是从既往训练轨迹归纳的一份始终可用的多轮法律事实调查经验手册，不是待完成清单，"
    "也不是当前案件事实。请把它作为外部工作记忆，与客户开场、可见对话和在线状态一起完成"
    "本轮唯一的完整动作决策：自主结束，或选择下一目标并组织一个问题。procedure 是目标排序与"
    "低收益转移办法，question_guidance 是问法原则，contraindications 是应避免的动作，"
    "failure_modes 是已观察到的失败模式；contraindications 或 failure_modes 非空不表示整份手册"
    "不可用。不得机械完成全部条目或拼接多个问题。手册不规定固定提问数，可以影响继续或停止，"
    "但最终动作必须由你自主生成。系统不会把手册编译成动作或在输出后改写。"
    "不得引用来源或假设不可见事实："
)
PLANNER_SKILL_MEMORY_HEADER = (
    "以下是当前工作库中与公开案件领域匹配的结构化咨询技能文档。"
    "它们只用于改善会话前事实调查计划：补足由客户开场自然引出的高价值可回答事实维度、"
    "调整目标优先级，并避开文档明确记录的低收益方向。"
    "不得据此猜测客户答案、隐藏事实、法律结论或评测标准；不得把文档写成固定问题清单，"
    "也不得因为技能存在而凑固定目标数量。当前规划技能文档为："
)
# Historical schema-21/22 renderers retained only for archive validation.  The
# current runtime exposes the complete fixed bundle and never expands a
# model-reported subset.
SELECTED_SKILL_CARD_HEADER = (
    "你已在上一离散阶段自主选择以下技能执行卡。仅在当前可见状态仍满足每张卡的全部适用线索且无排除条件时，"
    "用其decision_rule落实已选目标，并用question_form_rule组织问题。若有两张卡，它们只能分别承担"
    "互补的通用与领域作用，不得叠加问题或调和出卡外目标。所有卡均不得增加问题或改变停止决定："
)
EXPERIENCE_MEMORY_HEADER = (
    "以下是独立ExpeL经验池在非官方训练案件上归纳的经验和按公开开场检索的成功咨询示例。"
    "它们不是当前案件事实或法律结论；只能把其中的方法迁移到当前可见信息，不得复制示例中的事实，"
    "不得因经验存在而延长咨询："
)


def applicable_skill_documents(
    skills: list[SkillContract],
    *,
    domain: str,
) -> list[SkillContract]:
    """Render Ours globally while preserving frozen domain routing for baselines."""

    active = [skill for skill in skills if skill.status == "active"]
    playbooks = [skill for skill in active if skill.skill_id == GLOBAL_PLAYBOOK_SKILL_ID]
    if playbooks:
        if len(playbooks) != 1 or len(active) != 1 or playbooks[0].domain != "general":
            raise ValueError("Ours permits exactly one active global playbook")
        return playbooks
    return sorted(
        (skill for skill in active if skill.domain in {"general", domain}),
        key=lambda skill: skill.skill_id,
    )


def policy_skill_document(skill: SkillContract) -> dict[str, object]:
    """Project the complete auditable document without private provenance."""

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


def skill_execution_card(skill: SkillContract) -> dict[str, object]:
    """Project only fields needed by a frozen model to apply a skill.

    ``description`` and expected effects remain outside the compact execution
    card.  Failure patterns stay visible because they are the concrete blacklist
    learned from low-yield trajectories rather than outcome promises.
    """

    return {
        "skill_id": skill.skill_id,
        "domain": skill.domain,
        "intervention_scope": "consultation_action_decision",
        "may_change_stop_decision": True,
        "additional_question_budget": 0,
        "applicability_mode": "all_cues_required",
        "applicability_cues": skill.applicability_cues,
        "decision_rule": skill.procedure,
        "question_form_rule": skill.question_guidance,
        "exclude_when": skill.contraindications,
        "known_failure_patterns": skill.failure_modes,
    }


def skill_catalog_entry(skill: SkillContract) -> dict[str, object]:
    """Project the complete actionable runtime document without audit narrative."""

    if skill.skill_id == GLOBAL_PLAYBOOK_SKILL_ID:
        # The global playbook is always delivered; it is not selected by the
        # historical trigger/card protocol. Rendering trigger metadata such as
        # ``additional_question_budget=0`` and ``exclude_when`` made an always-on
        # document look conditionally disabled to the small frozen lawyer. Keep
        # the teacher-authored schema fields verbatim so the treatment remains
        # one auditable prompt document rather than an implicit control API.
        return policy_skill_document(skill)
    return {
        "name": skill.name,
        "objective": skill.objective,
        "description": skill.description,
        **skill_execution_card(skill),
    }


def render_selected_skill_card(skill: SkillContract) -> str:
    """Render one legacy schema-21/22 selected execution card."""

    return SELECTED_SKILL_CARD_HEADER + "\n" + json.dumps(
        skill_execution_card(skill), ensure_ascii=False, sort_keys=True
    )


def render_selected_skill_cards(skills: list[SkillContract]) -> list[str]:
    """Render legacy schema-21/22 selected cards for archive validation."""

    if len(skills) > 2:
        raise ValueError("at most two selected skill cards may be expanded")
    domains = [skill.domain for skill in skills]
    if len(skills) == 2 and domains.count("general") != 1:
        raise ValueError("two selected cards must contain exactly one general skill")
    if len({skill.skill_id for skill in skills}) != len(skills):
        raise ValueError("selected skill cards contain duplicate identifiers")
    return [render_selected_skill_card(skill) for skill in skills]


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
    """Validate exact runtime bundles for Ours or a frozen comparison library."""

    active = [skill for skill in skills if skill.status == "active"]
    issues = [
        f"skill_document_character_budget_exceeded:{skill.skill_id}"
        for skill in active
        if policy_skill_document_character_count(skill) > MAX_POLICY_SKILL_DOCUMENT_CHARACTERS
    ]
    domains = {"general", *(skill.domain for skill in active)}
    for domain in domains:
        applicable = applicable_skill_documents(active, domain=domain)
        if not applicable:
            continue
        payload = [skill_catalog_entry(skill) for skill in applicable]
        rendered = (
            SKILL_MEMORY_HEADER
            + "\n"
            + json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        if len(rendered) > MAX_SESSION_SKILL_MEMORY_CHARACTERS:
            issues.append(f"skill_memory_character_budget_exceeded:{domain}")
    return sorted(set(issues))


def render_skill_memory(skills: list[SkillContract], *, domain: str) -> tuple[str, list[str]]:
    """Render one fixed skill catalog and return its delivered identifiers."""

    applicable = applicable_skill_documents(skills, domain=domain)
    skill_ids = [skill.skill_id for skill in applicable]
    if not applicable:
        return (EMPTY_SKILL_MEMORY, [])
    issues = skill_memory_capacity_issues(applicable)
    if issues:
        raise ValueError("skill-memory capacity contract failed: " + ", ".join(issues))
    payload = [skill_catalog_entry(skill) for skill in applicable]
    rendered = (
        SKILL_MEMORY_HEADER
        + "\n"
        + json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return (rendered, skill_ids)


def render_planner_skill_memory(
    skills: list[SkillContract], *, domain: str
) -> tuple[str, list[str]]:
    """Render the same applicable documents for the pre-dialogue planner.

    Planning and turn-level questioning are two decisions of one frozen lawyer
    system.  The active global playbook therefore informs both stages, while the
    planner-specific header prevents action/termination language from becoming a
    fixed question script.  The document payload is byte-identical to the policy
    payload so one learned artifact cannot silently mean two different things.
    """

    applicable = applicable_skill_documents(skills, domain=domain)
    skill_ids = [skill.skill_id for skill in applicable]
    if not applicable:
        return (EMPTY_PLANNER_SKILL_MEMORY, [])
    issues = skill_memory_capacity_issues(applicable)
    if issues:
        raise ValueError("planner skill-memory capacity contract failed: " + ", ".join(issues))
    payload = [skill_catalog_entry(skill) for skill in applicable]
    return (
        PLANNER_SKILL_MEMORY_HEADER
        + "\n"
        + json.dumps(payload, ensure_ascii=False, sort_keys=True),
        skill_ids,
    )


def parse_rendered_skill_memory(value: str) -> list[str]:
    """Return IDs from an exact renderer product; reject lookalike text."""

    if value == EMPTY_SKILL_MEMORY:
        return []
    prefix = SKILL_MEMORY_HEADER + "\n"
    if not value.startswith(prefix):
        raise ValueError("policy prompt does not contain a current skill-memory document")
    payload = json.loads(value.removeprefix(prefix))
    if not isinstance(payload, list) or any(
        not isinstance(item, dict) or not isinstance(item.get("skill_id"), str) for item in payload
    ):
        raise ValueError("skill-memory document payload is invalid")
    skill_ids = [str(item["skill_id"]) for item in payload]
    if skill_ids != sorted(set(skill_ids)):
        raise ValueError("skill-memory document identifiers are not unique and sorted")
    return skill_ids


def parse_rendered_planner_skill_memory(value: str) -> list[str]:
    """Return IDs from an exact planner-memory renderer product."""

    if value == EMPTY_PLANNER_SKILL_MEMORY:
        return []
    prefix = PLANNER_SKILL_MEMORY_HEADER + "\n"
    if not value.startswith(prefix):
        raise ValueError("planner prompt does not contain a current skill-memory document")
    payload = json.loads(value.removeprefix(prefix))
    if not isinstance(payload, list) or any(
        not isinstance(item, dict) or not isinstance(item.get("skill_id"), str)
        for item in payload
    ):
        raise ValueError("planner skill-memory document payload is invalid")
    skill_ids = [str(item["skill_id"]) for item in payload]
    if skill_ids != sorted(set(skill_ids)):
        raise ValueError("planner skill-memory identifiers are not unique and sorted")
    return skill_ids


def parse_rendered_experience_memory(value: str) -> list[str]:
    """Return all auditable ExpeL memory IDs from an exact prompt payload."""

    prefix = EXPERIENCE_MEMORY_HEADER + "\n"
    if not value.startswith(prefix):
        raise ValueError("policy prompt does not contain an ExpeL experience-memory document")
    payload = json.loads(value.removeprefix(prefix))
    if not isinstance(payload, dict) or set(payload) != {
        "insights",
        "retrieved_training_successes",
    }:
        raise ValueError("experience-memory payload is invalid")
    insights = payload["insights"]
    examples = payload["retrieved_training_successes"]
    if not isinstance(insights, list) or not isinstance(examples, list):
        raise ValueError("experience-memory collections are invalid")
    ids = [str(item.get("insight_id") or "") for item in insights if isinstance(item, dict)] + [
        str(item.get("memory_id") or "") for item in examples if isinstance(item, dict)
    ]
    if (
        len(ids) != len(insights) + len(examples)
        or any(not item for item in ids)
        or len(ids) != len(set(ids))
    ):
        raise ValueError("experience-memory identifiers are missing or duplicated")
    return sorted(ids)


def extract_rendered_skill_memory(system_prompt: str) -> str:
    """Extract the exact embedded session memory from the frozen policy prompt."""

    if EMPTY_SKILL_MEMORY in system_prompt:
        return EMPTY_SKILL_MEMORY
    marker = SKILL_MEMORY_HEADER + "\n"
    offset = system_prompt.rfind(marker)
    if offset < 0:
        raise ValueError("policy system prompt is missing its skill-memory document")
    payload_offset = offset + len(marker)
    _, payload_length = json.JSONDecoder().raw_decode(system_prompt[payload_offset:])
    value = system_prompt[offset : payload_offset + payload_length]
    parse_rendered_skill_memory(value)
    return value


def extract_rendered_planner_skill_memory(system_prompt: str) -> str:
    """Extract the exact embedded planner memory from a stored system prompt."""

    if EMPTY_PLANNER_SKILL_MEMORY in system_prompt:
        return EMPTY_PLANNER_SKILL_MEMORY
    marker = PLANNER_SKILL_MEMORY_HEADER + "\n"
    offset = system_prompt.rfind(marker)
    if offset < 0:
        raise ValueError("planner system prompt is missing its skill-memory document")
    payload_offset = offset + len(marker)
    _, payload_length = json.JSONDecoder().raw_decode(system_prompt[payload_offset:])
    value = system_prompt[offset : payload_offset + payload_length]
    parse_rendered_planner_skill_memory(value)
    return value


def extract_rendered_experience_memory(system_prompt: str) -> str:
    """Extract the exact embedded ExpeL memory from a stored policy prompt."""

    marker = EXPERIENCE_MEMORY_HEADER + "\n"
    offset = system_prompt.rfind(marker)
    if offset < 0:
        raise ValueError("policy system prompt is missing its experience-memory document")
    payload_offset = offset + len(marker)
    _, payload_length = json.JSONDecoder().raw_decode(system_prompt[payload_offset:])
    value = system_prompt[offset : payload_offset + payload_length]
    parse_rendered_experience_memory(value)
    return value
