"""Load and statically validate immutable prompt-memory skill documents."""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from legal_skill_guard.schemas.skill import SkillContract
from legal_skill_guard.skills.memory import (
    MAX_POLICY_SKILL_DOCUMENT_CHARACTERS,
    policy_skill_document_character_count,
)

ALLOWED_SKILL_DOMAINS = {
    "general",
    "administrative",
    "company_commercial",
    "consumer_contract",
    "criminal",
    "environment_resources",
    "finance_bankruptcy",
    "insurance_contract",
    "intellectual_property",
    "labor_employment",
    "marriage_family",
    "personality_privacy",
    "procedure_evidence",
    "real_estate_construction",
    "tort_liability",
}
ALLOWED_OBJECTIVES = {
    "fact_elicitation",
    "evidence_gap_identification",
    "safe_stop",
}
DOCUMENT_FIELDS = (
    "name",
    "description",
    "applicability_cues",
    "procedure",
    "question_guidance",
    "expected_effects",
    "contraindications",
    "failure_modes",
)
RETIRED_RUNTIME_MARKERS = (
    "candidate_action",
    "state.",
    "replace_target",
    "replace_type",
    "rerank_target_concepts",
    "force_abstain",
    "max_activations_per_session",
    "触发器",
    "触发后",
    "动作改写",
)
PROVENANCE_IDENTIFIER_PATTERNS = (
    re.compile(r"\blsg_cn_\d+\b", re.IGNORECASE),
    re.compile(r"\bcase_cn_\d+\b", re.IGNORECASE),
    re.compile(r"\btraj_[0-9a-f]+\b", re.IGNORECASE),
    re.compile(r"(?<![A-Za-z0-9_])[FO]\d+(?![A-Za-z0-9_])"),
    re.compile(r"\bP_(?:WD|WS|CS|CD)\b"),
    re.compile(r"\b[0-9a-f]{32,64}\b", re.IGNORECASE),
)
FIXED_TURN_PATTERN = re.compile(
    r"(?:第\s*(?:\d+|[一二两三四五六七八九十]+)\s*轮|"
    r"(?:\d+|[一二两三四五六七八九十]+)\s*轮(?:后|内|以内|之内))"
)
ACTIONABLE_PROCEDURE_MARKERS = (
    "询问",
    "核实",
    "确认",
    "区分",
    "比较",
    "优先",
    "转向",
    "停止",
    "结束",
    "记录",
    "说明",
    "避免",
    "形成",
    "列明",
)


def skill_interface_catalog() -> dict[str, object]:
    """Return the complete teacher-facing prompt-document interface."""

    return {
        "schema_version": 2,
        "skill_domains": sorted(ALLOWED_SKILL_DOMAINS),
        "objectives": sorted(ALLOWED_OBJECTIVES),
        "policy_document_fields": {
            "applicability_cues": "1-5 visible, natural-language applicability cues",
            "procedure": "1-5 ordered and executable consultation steps",
            "question_guidance": "1-4 concrete question-formulation principles",
            "expected_effects": "1-5 observable intended effects",
            "contraindications": "1-5 visible situations where the advice should not be used",
            "failure_modes": "1-5 ways the strategy can fail or cause harm",
        },
        "source_evidence_is_system_owned": True,
        "forbidden_designs": [
            "candidate_action or post-answer action rewriting",
            "state.* machine predicates or runtime triggers",
            "case, trajectory, fact or persona identifiers",
            "fixed dialogue-turn counts",
            "hidden answers, source quotations, evaluator scores or external-test outcomes",
        ],
    }


def _document_strings(skill: SkillContract) -> list[str]:
    values = [skill.name, skill.description]
    for field_name in DOCUMENT_FIELDS[2:]:
        values.extend(getattr(skill, field_name))
    return values


def validate_skill_static(skill: SkillContract) -> list[str]:
    """Validate only properties that are knowable without outcome data.

    Source grounding is checked by the admission report, while downstream
    efficacy is measured only for the accumulated working library.  In particular,
    this gate must not resurrect either a per-candidate outcome test or the retired
    runtime rule engine by demanding an exact action rewrite from a document that
    the lawyer reads before choosing its action.
    """

    issues: list[str] = []
    if skill.schema_version != 2:
        issues.append(f"unsupported_skill_schema:{skill.schema_version}")
    if skill.domain not in ALLOWED_SKILL_DOMAINS:
        issues.append(f"unsupported_skill_domain:{skill.domain}")
    if skill.objective not in ALLOWED_OBJECTIVES:
        issues.append(f"unsupported_skill_objective:{skill.objective}")
    if (
        policy_skill_document_character_count(skill)
        > MAX_POLICY_SKILL_DOCUMENT_CHARACTERS
    ):
        issues.append("skill_document_character_budget_exceeded")
    if (
        "descriptive_snake_case_id" in skill.skill_id
        or "specific_behavior_name" in skill.skill_id
        or skill.skill_id.startswith(("test.", "fixture."))
    ):
        issues.append("placeholder_or_test_skill_id")

    provenance = skill.provenance
    if (
        provenance.source_signal_family is not None
        and provenance.source_signal_family != skill.objective
    ):
        issues.append("source_signal_family_mismatch")
    if len(provenance.source_case_ids) != len(set(provenance.source_case_ids)):
        issues.append("duplicate_source_case_ids")
    if len(provenance.source_trajectory_ids) != len(
        set(provenance.source_trajectory_ids)
    ):
        issues.append("duplicate_source_trajectory_ids")

    document = "\n".join(_document_strings(skill))
    lowered = document.lower()
    for marker in RETIRED_RUNTIME_MARKERS:
        if marker.lower() in lowered:
            issues.append(f"retired_runtime_language:{marker}")
    for pattern in PROVENANCE_IDENTIFIER_PATTERNS:
        if pattern.search(document):
            issues.append(f"source_identifier_in_policy_document:{pattern.pattern}")
    if FIXED_TURN_PATTERN.search(document):
        issues.append("fixed_dialogue_turn_count")
    if any(marker in document for marker in ("隐藏事实", "标准答案", "裁判得分", "奖励分数")):
        issues.append("outcome_or_hidden_label_language")
    if any(marker in document for marker in ("保证胜诉", "必然胜诉", "保证立案", "必然无罪")):
        issues.append("guaranteed_legal_outcome")
    if not any(
        marker in step for step in skill.procedure for marker in ACTIONABLE_PROCEDURE_MARKERS
    ):
        issues.append("procedure_not_actionable")
    return sorted(set(issues))


def _document_payload(skill: SkillContract, *, include_domain: bool) -> dict[str, object]:
    payload: dict[str, object] = {
        "objective": skill.objective,
        "description": skill.description,
        "applicability_cues": skill.applicability_cues,
        "procedure": skill.procedure,
        "question_guidance": skill.question_guidance,
        "expected_effects": skill.expected_effects,
        "contraindications": skill.contraindications,
        "failure_modes": skill.failure_modes,
    }
    if include_domain:
        payload["domain"] = skill.domain
    return payload


def _signature(skill: SkillContract, *, include_domain: bool) -> str:
    return json.dumps(
        _document_payload(skill, include_domain=include_domain),
        ensure_ascii=False,
        sort_keys=True,
    )


def find_structural_duplicates(
    candidate: SkillContract, existing: list[SkillContract]
) -> list[str]:
    """Find byte-equivalent policy advice in the same declared scope."""

    target = _signature(candidate, include_domain=True)
    return sorted(
        skill.skill_id
        for skill in existing
        if _signature(skill, include_domain=True) == target
    )


def find_scope_redundancies(
    candidate: SkillContract, existing: list[SkillContract]
) -> list[str]:
    """Find an identical document already available over an equal/broader domain."""

    target = _signature(candidate, include_domain=False)
    return sorted(
        skill.skill_id
        for skill in existing
        if _signature(skill, include_domain=False) == target
        and (skill.domain == "general" or skill.domain == candidate.domain)
    )


def find_lexical_near_duplicates(
    candidate: SkillContract,
    existing: list[SkillContract],
    *,
    threshold: float = 0.9,
) -> list[str]:
    """Flag nearly copied documents without treating complementary advice as conflict."""

    def trigrams(skill: SkillContract) -> set[str]:
        text = "".join(" ".join(_document_strings(skill)).lower().split())
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
