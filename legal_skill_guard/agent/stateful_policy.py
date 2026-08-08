"""Parse state-patch plus action envelopes and deterministically render actions."""

from __future__ import annotations

import json

from legal_skill_guard.agent.phase1_policy import _balanced_json_objects
from legal_skill_guard.schemas.action import StructuredAction
from legal_skill_guard.schemas.experiment import PolicyEnvelope
from legal_skill_guard.schemas.state import ConsultationState, StatePatch


def parse_policy_envelope(text: str) -> tuple[PolicyEnvelope, str]:
    raw = text.strip()
    candidates = [raw, *_balanced_json_objects(raw)]
    for index, candidate in enumerate(candidates):
        try:
            value = json.loads(candidate)
            return PolicyEnvelope.model_validate(value), "json" if index == 0 else "json_fragment"
        except (json.JSONDecodeError, ValueError):
            continue
    fallback = StructuredAction(
        action_type="ask",
        target_type="session",
        reason="invalid_structured_output",
        content=raw[:500] or "请进一步说明与本次咨询有关的关键时间、文件和处理经过。",
        confidence=0.0,
    )
    return PolicyEnvelope(state_patch=StatePatch(), action=fallback), "fallback"


def render_action(action: StructuredAction, state: ConsultationState) -> str:
    if action.content.strip() and not action.constraints:
        return action.content.strip()
    label = next(
        (fact.label for fact in state.facts if fact.fact_id == action.target_id),
        action.target_id or "这一关键情况",
    )
    prefix = {
        "ask": "请说明",
        "clarify": "为避免理解偏差，请进一步说明",
        "verify": "为核实该情况，请说明是否有材料能够证明",
        "summarize": "请确认我对以下情况的理解是否准确：",
    }.get(action.action_type, "请说明")
    question = f"{prefix}{label}？"
    if "single_specific_nonjudgmental_question" in action.constraints:
        question = f"为了准确理解情况，{question}"
    return question

