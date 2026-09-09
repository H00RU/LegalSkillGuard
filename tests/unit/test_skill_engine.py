"""Contract tests for schema-2 prompt-memory skills.

The retired runtime rule engine is intentionally absent.  These tests protect
the policy-facing document boundary, deterministic session delivery and the
immutable library lifecycle that replaced it.
"""

from __future__ import annotations

import importlib.util
import inspect
import json
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from legal_skill_guard.schemas.skill import SkillContract
from legal_skill_guard.skills.loader import (
    find_lexical_near_duplicates,
    find_scope_redundancies,
    find_structural_duplicates,
    load_skill,
    load_skill_directory,
    skill_interface_catalog,
    validate_skill_static,
)
from legal_skill_guard.skills.memory import (
    MAX_POLICY_SKILL_DOCUMENT_CHARACTERS,
    MAX_SESSION_SKILL_MEMORY_CHARACTERS,
    admit_active_skills_by_prompt_capacity,
    applicable_skill_documents,
    policy_skill_document_character_count,
    render_skill_memory,
    skill_memory_capacity_issues,
)
from legal_skill_guard.skills.registry import SkillRegistry
from tests.skill_fixtures import synthetic_skills

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def skills() -> list[SkillContract]:
    return synthetic_skills()


def _write_skill(path: Path, skill: SkillContract) -> None:
    path.write_text(
        yaml.safe_dump(
            skill.model_dump(mode="json", exclude_none=True),
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def test_synthetic_documents_use_current_schema_and_pass_static_gate(
    skills: list[SkillContract],
) -> None:
    assert len(skills) == len({skill.skill_id for skill in skills}) == 5
    assert all(skill.schema_version == 2 for skill in skills)
    assert all(validate_skill_static(skill) == [] for skill in skills)


def test_prompt_skill_document_and_session_memory_have_frozen_capacity() -> None:
    skill = synthetic_skills()[0].model_copy(deep=True)
    skill.description = "问" * 500
    skill.procedure = ["核实" + "事" * 238] * 5
    # Pydantic list de-duplication is deliberately bypassed here to exercise the
    # defense-in-depth renderer/static gate on a mutated in-memory artifact.
    assert policy_skill_document_character_count(skill) > MAX_POLICY_SKILL_DOCUMENT_CHARACTERS
    assert "skill_document_character_budget_exceeded" in validate_skill_static(skill)
    assert skill_memory_capacity_issues([skill]) == [
        f"skill_document_character_budget_exceeded:{skill.skill_id}"
    ]
    with pytest.raises(ValueError, match="capacity contract"):
        render_skill_memory([skill], domain=skill.domain)

    ordinary = synthetic_skills()[0]
    assert policy_skill_document_character_count(ordinary) < MAX_POLICY_SKILL_DOCUMENT_CHARACTERS
    memory, _ = render_skill_memory([ordinary], domain=ordinary.domain)
    assert len(memory) < MAX_SESSION_SKILL_MEMORY_CHARACTERS


def test_prompt_capacity_admits_an_ordered_cohort_before_combined_overflow() -> None:
    template = synthetic_skills()[0]
    candidates: list[SkillContract] = []
    for index in range(8):
        payload = template.model_dump(mode="json")
        payload.update(
            {
                "skill_id": f"lsg.general.capacity_{index}",
                "name": f"容量测试技能{index}",
                "domain": "general",
                "status": "active",
                "description": "在可见咨询状态下保持问题具体且优先核实关键事实。" * 15,
                "applicability_cues": ["客户开场仍缺少影响法律路径的具体事实。" * 5],
                "procedure": ["先区分已知陈述与尚待客户确认的事实，再询问一个具体问题。" * 5],
                "question_guidance": ["一次只询问一个客户能够理解并直接回答的事实。" * 5],
                "expected_effects": ["以较少问题取得更多互不重复的关键事实。" * 5],
                "contraindications": ["所需信息只能由外部材料核验时，不继续向客户追问。" * 5],
                "failure_modes": ["问题过于抽象时，客户可能无法提供对应事实。" * 5],
            }
        )
        candidate = SkillContract.model_validate(payload)
        assert (
            policy_skill_document_character_count(candidate)
            < MAX_POLICY_SKILL_DOCUMENT_CHARACTERS
        )
        candidates.append(candidate)

    admitted, rejected = admit_active_skills_by_prompt_capacity([], candidates)

    assert admitted
    assert rejected
    assert [item.skill_id for item in admitted] == [
        item.skill_id for item in candidates[: len(admitted)]
    ]
    assert skill_memory_capacity_issues(admitted) == []
    assert set(rejected) == {item.skill_id for item in candidates[len(admitted) :]}


@pytest.mark.parametrize("retired_field", ["preconditions", "operation", "candidate_action"])
def test_schema_forbids_retired_executable_fields(
    skills: list[SkillContract], retired_field: str
) -> None:
    payload = skills[0].model_dump(mode="json")
    payload[retired_field] = [] if retired_field == "preconditions" else {}
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        SkillContract.model_validate(payload)


def test_schema_forbids_unknown_document_fields(skills: list[SkillContract]) -> None:
    payload = skills[0].model_dump(mode="json")
    payload["teacher_private_reasoning"] = "not policy-facing"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        SkillContract.model_validate(payload)


@pytest.mark.parametrize(
    ("marker", "expected_issue"),
    [
        ("candidate_action", "retired_runtime_language:candidate_action"),
        ("state.some_flag", "retired_runtime_language:state."),
        ("replace_target", "retired_runtime_language:replace_target"),
        ("replace_type", "retired_runtime_language:replace_type"),
        ("rerank_target_concepts", "retired_runtime_language:rerank_target_concepts"),
        ("force_abstain", "retired_runtime_language:force_abstain"),
        (
            "max_activations_per_session",
            "retired_runtime_language:max_activations_per_session",
        ),
        ("触发器", "retired_runtime_language:触发器"),
        ("触发后", "retired_runtime_language:触发后"),
        ("动作改写", "retired_runtime_language:动作改写"),
    ],
)
def test_static_gate_rejects_old_runtime_language(
    skills: list[SkillContract], marker: str, expected_issue: str
) -> None:
    candidate = skills[0].model_copy(deep=True)
    candidate.description = f"这是长度充足的咨询方法说明，但包含退役实现术语 {marker}。"
    assert expected_issue in validate_skill_static(candidate)


@pytest.mark.parametrize(
    "identifier",
    [
        "lsg_cn_0007",
        "case_cn_0002",
        "traj_deadbeef",
        "F3",
        "O2",
        "P_CD",
        "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    ],
)
def test_policy_document_cannot_leak_source_identifiers(
    skills: list[SkillContract], identifier: str
) -> None:
    candidate = skills[0].model_copy(deep=True)
    candidate.question_guidance = [f"询问时参考来源标识 {identifier} 的原始信息"]
    issues = validate_skill_static(candidate)
    assert any(issue.startswith("source_identifier_in_policy_document:") for issue in issues)


@pytest.mark.parametrize("phrase", ["第3轮停止", "二轮后结束", "5轮以内完成"])
def test_policy_document_cannot_encode_a_fixed_dialogue_horizon(
    skills: list[SkillContract], phrase: str
) -> None:
    candidate = skills[0].model_copy(deep=True)
    candidate.procedure = [f"核实当前信息并在{phrase}"]
    assert "fixed_dialogue_turn_count" in validate_skill_static(candidate)


@pytest.mark.parametrize(
    ("phrase", "issue"),
    [
        ("读取隐藏事实后再询问", "outcome_or_hidden_label_language"),
        ("依据裁判得分选择问法", "outcome_or_hidden_label_language"),
        ("采用该方法即可保证胜诉", "guaranteed_legal_outcome"),
        ("采用该方法必然无罪", "guaranteed_legal_outcome"),
    ],
)
def test_static_gate_rejects_hidden_outcome_or_guarantee_language(
    skills: list[SkillContract], phrase: str, issue: str
) -> None:
    candidate = skills[0].model_copy(deep=True)
    candidate.expected_effects = [phrase]
    assert issue in validate_skill_static(candidate)


def test_static_gate_requires_an_actionable_procedure(skills: list[SkillContract]) -> None:
    candidate = skills[0].model_copy(deep=True)
    candidate.procedure = ["保持专业、审慎和耐心的整体工作风格"]
    assert "procedure_not_actionable" in validate_skill_static(candidate)


def test_static_gate_rejects_placeholder_identity_and_unsupported_scope(
    skills: list[SkillContract],
) -> None:
    candidate = skills[0].model_copy(deep=True)
    candidate.skill_id = "test.placeholder"
    candidate.domain = "imaginary_domain"
    assert validate_skill_static(candidate) == [
        "placeholder_or_test_skill_id",
        "unsupported_skill_domain:imaginary_domain",
    ]


def test_static_gate_checks_system_owned_provenance_consistency(
    skills: list[SkillContract],
) -> None:
    candidate = skills[0].model_copy(deep=True)
    candidate.provenance.source_signal_family = "safe_stop"
    candidate.provenance.source_case_ids = ["source-a", "source-a"]
    candidate.provenance.source_trajectory_ids = ["trajectory-a", "trajectory-a"]
    assert validate_skill_static(candidate) == [
        "duplicate_source_case_ids",
        "duplicate_source_trajectory_ids",
        "source_signal_family_mismatch",
    ]


def test_schema_normalizes_whitespace_and_rejects_blank_or_duplicate_list_items(
    skills: list[SkillContract],
) -> None:
    payload = skills[0].model_dump(mode="json")
    payload["applicability_cues"] = ["  一个可见线索  "]
    normalized = SkillContract.model_validate(payload)
    assert normalized.applicability_cues == ["一个可见线索"]

    payload["applicability_cues"] = ["同一线索", "同一线索"]
    with pytest.raises(ValidationError, match="cannot contain duplicate items"):
        SkillContract.model_validate(payload)
    payload["applicability_cues"] = ["   "]
    with pytest.raises(ValidationError, match="cannot contain blank items"):
        SkillContract.model_validate(payload)


def test_teacher_interface_is_natural_document_only() -> None:
    interface = skill_interface_catalog()
    assert interface["schema_version"] == 2
    assert interface["source_evidence_is_system_owned"] is True
    assert set(interface["policy_document_fields"]) == {
        "applicability_cues",
        "procedure",
        "question_guidance",
        "expected_effects",
        "contraindications",
        "failure_modes",
    }
    assert set(interface["objectives"]) == {
        "fact_elicitation",
        "evidence_gap_identification",
        "safe_stop",
    }


def test_teacher_prompt_describes_prompt_documents_not_old_execution_dsl() -> None:
    prompt = (ROOT / "configs/prompts/skill_teacher_zh.txt").read_text(encoding="utf-8")
    for field in (
        "applicability_cues",
        "procedure",
        "question_guidance",
        "expected_effects",
        "contraindications",
        "failure_modes",
    ):
        assert field in prompt
    for retired in (
        "candidate_action",
        "recommended_action_pattern",
        "operation_source_replay_semantics",
        "max_activations_per_session",
    ):
        assert retired not in prompt
    assert "直接成为工作技能" in prompt
    assert "不用单个候选的小样本收益决定准入" in prompt
    assert "{baseline_policy_contract}" in prompt
    assert "相同问题的近义改写" in prompt


def test_applicable_documents_are_active_general_plus_matching_domain_only(
    skills: list[SkillContract],
) -> None:
    candidate = skills[2].model_copy(deep=True)
    candidate.skill_id = "consumer.pending_candidate"
    candidate.status = "candidate"
    selected = applicable_skill_documents(
        [candidate, *reversed(skills)], domain="marriage_family"
    )
    assert [skill.skill_id for skill in selected] == [
        "general.conditional_safe_stop",
        "general.opening_gap_probe",
        "marriage.sensitive_fact_reapproach",
    ]


def test_skill_memory_is_deterministic_and_contains_only_policy_facing_fields(
    skills: list[SkillContract],
) -> None:
    first_text, first_ids = render_skill_memory(skills, domain="marriage_family")
    second_text, second_ids = render_skill_memory(
        list(reversed(skills)), domain="marriage_family"
    )
    assert (first_text, first_ids) == (second_text, second_ids)
    header, serialized = first_text.split("\n", maxsplit=1)
    assert "本会话技能包固定不变" in header
    payload = json.loads(serialized)
    assert [item["skill_id"] for item in payload] == first_ids
    assert all("provenance" not in item for item in payload)
    assert all("evaluation" not in item for item in payload)
    assert all(
        set(item)
        == {
            "skill_id",
            "name",
            "domain",
            "objective",
            "description",
            "applicability_cues",
            "procedure",
            "question_guidance",
            "expected_effects",
            "contraindications",
            "failure_modes",
        }
        for item in payload
    )


def test_empty_memory_is_explicit_and_stable() -> None:
    assert render_skill_memory([], domain="criminal") == (
        "本会话的当前工作库没有适用咨询技能文档。请仅依据客户开场、可见对话和在线状态自主决策。",
        [],
    )


def test_delivery_api_has_no_action_rewrite_input_and_engine_module_is_absent(
    skills: list[SkillContract],
) -> None:
    parameters = inspect.signature(render_skill_memory).parameters
    assert list(parameters) == ["skills", "domain"]
    first = render_skill_memory(skills, domain="consumer_contract")
    second = render_skill_memory(skills, domain="consumer_contract")
    assert first == second
    assert importlib.util.find_spec("legal_skill_guard.skills.engine") is None


def test_structural_duplicate_ignores_identity_but_respects_scope(
    skills: list[SkillContract],
) -> None:
    original = skills[0]
    duplicate = original.model_copy(deep=True)
    duplicate.skill_id = "general.same_opening_method"
    duplicate.version = "2.0.0"
    duplicate.provenance.source = "tf_grpo"
    assert find_structural_duplicates(duplicate, skills) == [original.skill_id]

    duplicate.domain = "marriage_family"
    assert find_structural_duplicates(duplicate, skills) == []


def test_identical_document_in_broader_scope_makes_narrow_copy_redundant(
    skills: list[SkillContract],
) -> None:
    broad = skills[0]
    narrow = broad.model_copy(deep=True)
    narrow.skill_id = "marriage.same_opening_method"
    narrow.domain = "marriage_family"
    assert find_scope_redundancies(narrow, [broad]) == [broad.skill_id]

    broad_candidate = narrow.model_copy(deep=True)
    broad_candidate.skill_id = "general.new_broad_method"
    broad_candidate.domain = "general"
    assert find_scope_redundancies(broad_candidate, [narrow]) == []


def test_lexical_near_duplicate_catches_copy_edit_but_not_complementary_advice(
    skills: list[SkillContract],
) -> None:
    original = skills[0]
    copy_edit = original.model_copy(deep=True)
    copy_edit.skill_id = "general.opening_gap_probe_copy"
    copy_edit.description = original.description + "请保持简洁。"
    assert original.skill_id in find_lexical_near_duplicates(copy_edit, [original])

    complementary = skills[3]
    assert find_lexical_near_duplicates(complementary, [original]) == []


def test_directory_loader_validates_documents_and_active_filter(
    tmp_path: Path, skills: list[SkillContract]
) -> None:
    active = skills[0]
    candidate = skills[1].model_copy(deep=True)
    candidate.status = "candidate"
    _write_skill(tmp_path / "active.yaml", active)
    _write_skill(tmp_path / "candidate.yaml", candidate)

    assert [skill.skill_id for skill in load_skill_directory(tmp_path)] == [
        active.skill_id,
        candidate.skill_id,
    ]
    assert [skill.skill_id for skill in load_skill_directory(tmp_path, active_only=True)] == [
        active.skill_id
    ]


def test_directory_loader_rejects_static_violation_and_duplicate_ids(
    tmp_path: Path, skills: list[SkillContract]
) -> None:
    invalid = skills[0].model_copy(deep=True)
    invalid.description = "这个文档试图读取 candidate_action 并改变模型已经输出的行动。"
    _write_skill(tmp_path / "invalid.yaml", invalid)
    with pytest.raises(ValueError, match="retired_runtime_language:candidate_action"):
        load_skill(tmp_path / "invalid.yaml")

    (tmp_path / "invalid.yaml").unlink()
    _write_skill(tmp_path / "first.yaml", skills[0])
    duplicate = skills[0].model_copy(deep=True)
    duplicate.description = "这个不同的正文仍然错误复用了同一个不可变技能标识。"
    _write_skill(tmp_path / "second.yaml", duplicate)
    with pytest.raises(ValueError, match="Duplicate skill IDs"):
        load_skill_directory(tmp_path)


def test_registry_freezes_activates_and_rolls_back_prompt_documents(
    tmp_path: Path, skills: list[SkillContract]
) -> None:
    registry = SkillRegistry(tmp_path / "versions")
    first = registry.create_version(
        "v1", skills[:2], parent_version=None, evidence={"kind": "source_binding"}
    )
    assert first.is_dir()
    registry.activate("v1")
    assert registry.current() == "v1"

    registry.create_version(
        "v2", skills[:3], parent_version="v1", evidence={"kind": "prospective_accept"}
    )
    registry.activate("v2")
    assert registry.current() == "v2"
    registry.rollback()
    assert registry.current() == "v1"


def test_registry_rejects_duplicate_ids_and_detects_byte_tampering(
    tmp_path: Path, skills: list[SkillContract]
) -> None:
    registry = SkillRegistry(tmp_path / "versions")
    with pytest.raises(ValueError, match="duplicate skill IDs"):
        registry.create_version(
            "duplicate", [skills[0], skills[0]], parent_version=None, evidence={}
        )

    directory = registry.create_version(
        "clean", skills[:1], parent_version=None, evidence={}
    )
    skill_path = next(directory.glob("*.yaml"))
    skill_path.write_text(skill_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        registry.validate("clean")


def test_registry_activation_applies_current_static_document_gate(
    tmp_path: Path, skills: list[SkillContract]
) -> None:
    invalid = skills[0].model_copy(deep=True)
    invalid.description = "这个结构有效的文档仍然包含过时的动作改写说明，因此不能进入正式库。"
    registry = SkillRegistry(tmp_path / "versions")
    registry.create_version("invalid", [invalid], parent_version=None, evidence={})
    assert registry.validate("invalid")["version"] == "invalid"
    with pytest.raises(ValueError, match="Static skill validation failed"):
        registry.activate("invalid")
