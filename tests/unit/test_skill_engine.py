from pathlib import Path

import pytest

from legal_skill_guard.agent.state_manager import StateManager
from legal_skill_guard.schemas.action import StructuredAction
from legal_skill_guard.schemas.skill import SkillContract
from legal_skill_guard.schemas.state import FactObservation, FactSlot, StatePatch
from legal_skill_guard.skills.engine import SkillEngine, condition_matches
from legal_skill_guard.skills.loader import (
    find_lexical_near_duplicates,
    find_structural_duplicates,
    find_trigger_conflicts,
    load_skill_directory,
    validate_skill_static,
)
from legal_skill_guard.verifiers.deterministic import StopGate, verify_action

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def skills() -> list[SkillContract]:
    return load_skill_directory(ROOT / "skills/seed", active_only=True)


def high_unknown_state():
    manager = StateManager()
    state = manager.initial("session", "开场", persona="P_WS")
    return manager.merge(
        state,
        StatePatch(
            observations=[
                FactObservation(
                    fact_id="notice_date",
                    label="通知日期",
                    status="unknown",
                    criticality="high",
                )
            ]
        ),
        1,
    )


def test_all_seed_skills_load_and_have_unique_ids(skills: list[SkillContract]) -> None:
    assert len(skills) == 10
    assert len({skill.skill_id for skill in skills}) == 10
    assert not any(validate_skill_static(skill) for skill in skills)


def test_static_validation_rejects_teacher_placeholder_and_unknown_state_path(
    skills: list[SkillContract],
) -> None:
    skill = skills[0].model_copy(deep=True)
    skill.skill_id = "evolved.descriptive_snake_case_id"
    skill.preconditions[0].field = "state.facts.claimed_high_count"
    issues = validate_skill_static(skill)
    assert "placeholder_or_test_skill_id" in issues
    assert "unsupported_condition_field:state.facts.claimed_high_count" in issues


def test_static_validation_rejects_unexecutable_and_specific_operation(
    skills: list[SkillContract],
) -> None:
    skill = skills[0].model_copy(deep=True)
    skill.operation.new_action_type = "invented_action"
    skill.operation.target_selector = "invented_selector"
    skill.operation.target_id = "case_specific_fact"
    issues = validate_skill_static(skill)
    assert "unsupported_new_action_type:invented_action" in issues
    assert "unsupported_target_selector:invented_selector" in issues
    assert "over_specific_operation_target_id" in issues


def test_structural_duplicate_is_detected_despite_renaming(
    skills: list[SkillContract],
) -> None:
    candidate = skills[0].model_copy(deep=True)
    candidate.skill_id = "evolved.renamed_duplicate"
    candidate.name = "Renamed duplicate"
    candidate.preconditions.reverse()
    assert find_structural_duplicates(candidate, skills) == [skills[0].skill_id]


def test_candidate_conflict_and_near_duplicate_checks(
    skills: list[SkillContract],
) -> None:
    candidate = skills[0].model_copy(deep=True)
    candidate.skill_id = "evolved.conflicting_copy"
    candidate.operation.reason = "different_reason"
    assert find_trigger_conflicts(candidate, skills)
    candidate.operation = skills[0].operation.model_copy(deep=True)
    assert find_lexical_near_duplicates(candidate, skills) == [skills[0].skill_id]


def test_premature_final_is_redirected(skills: list[SkillContract]) -> None:
    state = high_unknown_state()
    state.persona = "P_WD"
    action = StructuredAction(action_type="final", content="直接回答")
    state.candidate_action = action.model_dump(mode="python")
    decision = SkillEngine(skills).apply(state, action)
    assert decision.final.action_type == "clarify"
    assert decision.final.target_id == "notice_date"
    assert "general.premature_final_guard" in decision.activated_skill_ids
    assert all(
        result.passed
        for result in verify_action(state, decision)
        if result.severity == "severe"
    )


def test_skill_does_not_trigger_when_precondition_false(skills: list[SkillContract]) -> None:
    state = high_unknown_state()
    action = StructuredAction(action_type="ask", target_type="fact", target_id="notice_date")
    premature = next(s for s in skills if s.skill_id == "general.premature_final_guard")
    assert not all(condition_matches(c, state, action) for c in premature.preconditions)


def test_repeated_target_is_replaced_after_strategic_intervention(
    skills: list[SkillContract],
) -> None:
    state = high_unknown_state()
    state.persona = "P_WD"
    state.asked_targets = ["notice_date"]
    next(item for item in state.facts if item.fact_id == "notice_date").criticality = "medium"
    state.facts.append(FactSlot(fact_id="evidence", label="相关证据", status="unknown"))
    action = StructuredAction(action_type="ask", target_type="fact", target_id="notice_date")
    decision = SkillEngine(skills).apply(state, action)
    assert decision.final.target_id == "evidence"
    assert "general.repeated_question_guard" in decision.activated_skill_ids


@pytest.mark.parametrize(
    ("operation", "expected"),
    [
        ({"type": "allow"}, "ask"),
        ({"type": "block", "reason": "risk"}, "abstain"),
        ({"type": "replace_type", "new_action_type": "verify"}, "verify"),
        ({"type": "replace_target", "target_id": "f2", "target_type": "fact"}, "ask"),
        (
            {
                "type": "replace_type_and_target",
                "new_action_type": "clarify",
                "target_id": "f2",
                "target_type": "fact",
            },
            "clarify",
        ),
        ({"type": "add_constraint", "constraint": "short"}, "ask"),
        ({"type": "request_state", "reason": "missing"}, "clarify"),
        ({"type": "force_abstain", "reason": "budget"}, "abstain"),
    ],
)
def test_every_whitelisted_operation(operation: dict, expected: str) -> None:
    skill = SkillContract.model_validate(
        {
            "skill_id": "test.operation",
            "name": "operation",
            "version": "1.0.0",
            "level": "strategic",
            "status": "active",
            "description": "test",
            "preconditions": [
                {"field": "candidate_action.action_type", "op": "eq", "value": "ask"}
            ],
            "reads": ["candidate_action"],
            "operation": operation,
            "expected_effects": ["test"],
            "validators": ["no_hidden_fields"],
            "failure_modes": ["none"],
            "guardrails": {"max_activations_per_session": 1},
            "provenance": {"source": "manual_seed"},
        }
    )
    state = high_unknown_state()
    state.facts.append(FactSlot(fact_id="f2", label="事实2", status="unknown"))
    action = StructuredAction(action_type="ask", target_type="fact", target_id="notice_date")
    decision = SkillEngine([skill]).apply(state, action)
    assert decision.final.action_type == expected
    if operation["type"] == "replace_target":
        assert decision.final.target_id == "f2"
    if operation["type"] == "add_constraint":
        assert "short" in decision.final.constraints


def test_stop_gate_redirects_unsafe_final() -> None:
    state = high_unknown_state()
    verdict, reason = StopGate().evaluate(state, StructuredAction(action_type="final"))
    assert (verdict, reason) == ("REDIRECT", "high_criticality_unknown")
