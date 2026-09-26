import json
from pathlib import Path

import pytest

from legal_skill_guard.agent.state_manager import StateManager
from legal_skill_guard.agent.stateful_policy import (
    action_question_quality_violations,
    action_target_alignment_violations,
    blocking_policy_health_violations,
    executable_fallback_can_repair,
    factual_target_question_safety_violations,
    normalize_policy_envelope,
    parse_policy_envelope,
    policy_health_violations,
    policy_repair_instruction,
    render_action,
    safe_factual_fallback,
    safe_factual_question_surface,
    visible_target_atomic_units,
)
from legal_skill_guard.inference.openai_client import (
    ChatResponse,
    GenerationConfig,
    ReplayCachedChatClient,
)
from legal_skill_guard.schemas.action import StructuredAction
from legal_skill_guard.schemas.experiment import PolicyEnvelope
from legal_skill_guard.schemas.state import FactObservation, FactSlot, StatePatch
from legal_skill_guard.verifiers.deterministic import StopGate
from scripts.audit_trajectory_health import audit
from tests.legacy_support.client_simulator_protocol35 import (
    CLIENT_RELEVANCE_ANALYSIS_SCHEMA,
    ClientSimulator,
    asks_communication_content,
    asks_communication_existence,
    client_fact_selection_schema,
    cognitive_subject_role,
    deterministic_relevance_compatibility,
    direct_answer_attribute_explicit_match,
    direct_answer_attribute_violations,
    disclosed_fact_indices,
    event_attribute_compatible,
    hidden_fact_adds_information,
    hidden_fact_adds_question_information,
    opening_fact_candidates,
    parse_fact_selection,
    parse_fact_selection_decision,
    parse_relevance_analysis,
    parse_relevance_check,
    presupposition_correction_match,
    relationship_context_roles,
    render_grounded_client_response,
    response_violations,
    sanitize_client_response,
    structured_proposition_alignment_passed,
    transition_stage_compatible,
)


class CountingClient:
    model = "counting-model"

    def __init__(self) -> None:
        self.calls = 0

    def is_ready(self) -> bool:
        return True

    def generate(self, messages, generation):
        self.calls += 1
        return ChatResponse("固定回答", "stop", 10, 2, f"id-{self.calls}")


class FactSevenSelector:
    model = "fact-six-selector"

    def generate(self, messages, generation):
        if "answers_question" in messages[-1]["content"]:
            return ChatResponse('{"answers_question":true}', "stop", 10, 2, "relevance")
        return ChatResponse('{"fact_ids":["F7"]}', "stop", 10, 2, "selector")


class FactThreeSelector:
    model = "fact-three-selector"

    def generate(self, messages, generation):
        if "answers_question" in messages[-1]["content"]:
            return ChatResponse('{"answers_question":true}', "stop", 10, 2, "relevance")
        return ChatResponse('{"fact_ids":["F3"]}', "stop", 10, 2, "selector")


class FactFourSelector:
    model = "fact-four-selector"

    def generate(self, messages, generation):
        return ChatResponse('{"fact_ids":["F4"]}', "stop", 10, 2, "selector")


class OpeningSelector:
    model = "opening-selector"

    def generate(self, messages, generation):
        if "answers_question" in messages[-1]["content"]:
            return ChatResponse('{"answers_question":true}', "stop", 10, 2, "relevance")
        return ChatResponse('{"fact_ids":["O1"]}', "stop", 10, 2, "selector")


class HiddenBeforeOpeningSelector:
    model = "hidden-before-opening-selector"

    def generate(self, messages, generation):
        if "answers_question" in messages[-1]["content"]:
            return ChatResponse('{"answers_question":true}', "stop", 10, 2, "relevance")
        prompt = "\n".join(message["content"] for message in messages)
        selected = "F1" if "F1" in prompt else "O1" if "O1" in prompt else None
        return ChatResponse(
            json.dumps({"fact_ids": [selected] if selected else []}),
            "stop",
            10,
            2,
            "selector",
        )


class RejectingRelevanceVerifier:
    model = "independent-relevance-verifier"

    def generate(self, messages, generation):
        return ChatResponse('{"answers_question":false}', "stop", 10, 2, "verifier")


class EmptyFactSelector:
    model = "empty-fact-selector"

    def generate(self, messages, generation):
        return ChatResponse('{"fact_ids":[]}', "stop", 10, 2, "selector-empty")


class EmptyThenTruncatedThenStrictEmptySelector:
    model = "empty-truncated-strict-empty-selector"

    def __init__(self) -> None:
        self.generations: list[GenerationConfig] = []

    def generate(self, messages, generation):
        self.generations.append(generation)
        call = len(self.generations)
        if call == 1:
            return ChatResponse(
                '{"fact_ids":[],"disclosure":"disclose"}',
                "stop",
                10,
                2,
                "initial-empty",
            )
        if call == 2:
            return ChatResponse(
                "<think>逐项检查候选但尚未形成结构化决定",
                "length",
                10,
                768,
                "recall-truncated",
            )
        return ChatResponse(
            '{"fact_ids":[],"disclosure":"disclose"}',
            "stop",
            10,
            2,
            "strict-empty",
        )


class WithholdThenDiscloseSelector:
    model = "withhold-then-disclose-selector"

    def __init__(self, fact_id: str = "F1") -> None:
        self.fact_id = fact_id
        self.selection_calls = 0
        self.disclosure_calls = 0
        self.generations: list[GenerationConfig] = []

    def generate(self, messages, generation):
        if "answers_question" in messages[-1]["content"]:
            return ChatResponse('{"answers_question":true}', "stop", 10, 2, "relevance")
        if generation.response_schema_name == "legal_skill_guard_client_disclosure_v1":
            self.disclosure_calls += 1
            disclosure = "withhold" if self.disclosure_calls == 1 else "disclose"
            return ChatResponse(
                json.dumps({"disclosure": disclosure}),
                "stop",
                10,
                2,
                f"disclosure-{self.disclosure_calls}",
            )
        self.selection_calls += 1
        self.generations.append(generation)
        return ChatResponse(
            json.dumps({"fact_ids": [self.fact_id], "disclosure": "disclose"}),
            "stop",
            10,
            2,
            f"selector-{self.selection_calls}",
        )


class LengthThenDisclosureSelector:
    model = "length-then-disclosure-selector"

    def __init__(self) -> None:
        self.disclosure_generations: list[GenerationConfig] = []

    def generate(self, messages, generation):
        if "answers_question" in messages[-1]["content"]:
            return ChatResponse('{"answers_question":true}', "stop", 10, 2, "relevance")
        if generation.response_schema_name == "legal_skill_guard_client_disclosure_v1":
            self.disclosure_generations.append(generation)
            if len(self.disclosure_generations) == 1:
                return ChatResponse("<think>尚未输出决定", "length", 10, 768, "truncated")
            return ChatResponse('{"disclosure":"disclose"}', "stop", 10, 2, "repaired")
        return ChatResponse(
            '{"fact_ids":["F1"],"disclosure":"disclose"}',
            "stop",
            10,
            2,
            "selector",
        )


class ApprovingRelevanceVerifier:
    model = "approving-relevance-verifier"

    def generate(self, messages, generation):
        return ChatResponse('{"answers_question":true}', "stop", 10, 2, "verifier")


class RecordingFactThreeSelectorAndVerifier:
    model = "recording-fact-three-selector-and-verifier"

    def __init__(self) -> None:
        self.calls: list[list[dict[str, str]]] = []

    def generate(self, messages, generation):
        self.calls.append(messages)
        if "answers_question" in messages[-1]["content"]:
            content = '{"answers_question":true}'
        else:
            content = '{"fact_ids":["F3"]}'
        return ChatResponse(content, "stop", 10, 2, f"call-{len(self.calls)}")


class EmptyThenFactSelector:
    model = "empty-then-fact-selector"

    def __init__(self) -> None:
        self.calls = 0
        self.selection_prompts: list[list[dict[str, str]]] = []

    def generate(self, messages, generation):
        self.calls += 1
        self.selection_prompts.append(messages)
        selected = [] if self.calls == 1 else ["F3"]
        return ChatResponse(
            json.dumps({"fact_ids": selected}), "stop", 10, 2, f"selector-{self.calls}"
        )


class MalformedThenEmptyOpeningSelector:
    model = "malformed-then-empty-opening-selector"

    def __init__(self) -> None:
        self.calls = 0
        self.last_messages = []

    def generate(self, messages, generation):
        self.calls += 1
        self.last_messages = messages
        content = "不知道。" if self.calls == 1 else '{"fact_ids":[]}'
        return ChatResponse(content, "stop", 10, 2, f"selector-{self.calls}")


class InvalidRelevanceVerifier:
    model = "invalid-relevance-verifier"

    def generate(self, messages, generation):
        return ChatResponse('{"answers_question":"maybe"}', "stop", 10, 2, "invalid")


class TruncatedThenStructuredRelevanceVerifier:
    model = "truncated-then-structured-relevance-verifier"

    def __init__(self) -> None:
        self.generations: list[GenerationConfig] = []
        self.messages: list[list[dict[str, str]]] = []

    def generate(self, messages, generation):
        self.generations.append(generation)
        self.messages.append(messages)
        if len(self.generations) == 1:
            return ChatResponse("<think>尚未形成结构化结论", "length", 10, 1200, "truncated")
        return ChatResponse(
            json.dumps(
                {
                    "question_actor": "客户",
                    "question_predicate": "收到书面通知",
                    "question_attribute": "收到时间",
                    "candidate_actor": "客户",
                    "candidate_predicate": "收到书面通知",
                    "candidate_attribute": "2024年3月1日",
                    "candidate_assertion_source": "direct_client_fact",
                    "same_actor": True,
                    "same_predicate": True,
                    "same_attribute": True,
                    "answers_question": True,
                },
                ensure_ascii=False,
            ),
            "stop",
            10,
            120,
            "structured-repair",
        )


class FirstRemainingFactSelector:
    model = "first-remaining-fact-selector"

    def __init__(self) -> None:
        self.selection_prompts: list[str] = []

    def generate(self, messages, generation):
        prompt = "\n".join(message["content"] for message in messages)
        self.selection_prompts.append(prompt)
        for fact_id in ("F1", "F2", "F3"):
            if fact_id in prompt:
                return ChatResponse(
                    json.dumps({"fact_ids": [fact_id]}),
                    "stop",
                    10,
                    2,
                    f"selector-{fact_id}",
                )
        return ChatResponse('{"fact_ids":[]}', "stop", 10, 2, "selector-empty")


def test_renderer_preserves_natural_content_when_constraint_is_added() -> None:
    state = StateManager().initial("render", "开场", max_turns=6)
    action = StructuredAction(
        action_type="ask",
        target_type="fact",
        target_id="event_time",
        content="您在什么日期收到书面决定？",
        constraints=["single_specific_nonjudgmental_question"],
    )
    assert render_action(action, state) == "您在什么日期收到书面决定？"


@pytest.mark.parametrize(
    "content",
    (
        "债权人要求您承担出资责任的法律依据是什么？是否有相关法律条文或证据支持这一主张？",
        "债权人说他们没查清楚公司担保的法律程序，这是否符合法律规定？",
        "是否已触发相关责任或违约条款？",
    ),
)
def test_renderer_does_not_apply_case_specific_sentence_rewrites(content: str) -> None:
    state = StateManager().initial("render-no-case-rewrite", "开场", max_turns=6)
    action = StructuredAction(
        action_type="ask",
        target_type="fact",
        target_id="planned_fact",
        content=content,
    )

    assert render_action(action, state) == content


def test_invalid_structured_policy_output_is_always_blocking() -> None:
    envelope, mode = parse_policy_envelope('{"state_patch": {')
    violations = policy_health_violations(
        envelope, StateManager().initial("invalid-json", "开场", max_turns=6)
    )
    assert mode == "fallback"
    assert "invalid_structured_output" in violations
    assert "invalid_structured_output" in blocking_policy_health_violations(violations)


def test_policy_parser_closes_only_a_missing_outer_object_brace() -> None:
    raw = """{
      "action": {
        "action_type": "ask",
        "target_type": "fact",
        "target_id": "child_caregiver",
        "reason": "照料状态会改变分析",
        "expected_information": "孩子由谁照料",
        "content": "孩子目前由谁照料？",
        "constraints": [],
        "confidence": 0.8
    }"""
    envelope, mode = parse_policy_envelope(raw)
    assert mode == "json_missing_outer_closure"
    assert envelope.action.target_id == "child_caregiver"
    assert envelope.action.content == "孩子目前由谁照料？"

    _, invalid_mode = parse_policy_envelope('{"action": {')
    assert invalid_mode == "fallback"


def test_terminal_null_content_is_normalized_to_empty_string() -> None:
    envelope, mode = parse_policy_envelope(
        json.dumps(
            {
                "state_patch": {"observations": [], "issue_labels": [], "risk_flags_add": []},
                "action": {"action_type": "final", "content": None},
            }
        )
    )
    assert mode == "json"
    assert envelope.action.action_type == "final"
    assert envelope.action.content == ""


def test_terminal_string_null_target_is_canonicalized() -> None:
    envelope, mode = parse_policy_envelope(
        json.dumps(
            {
                "action": {
                    "action_type": "final",
                    "target_type": "fact",
                    "target_id": "null",
                    "content": "",
                }
            }
        )
    )
    assert mode == "json"
    assert envelope.action.target_type == "session"
    assert envelope.action.target_id is None
    assert (
        policy_health_violations(
            envelope, StateManager().initial("terminal-null", "开场", max_turns=6)
        )
        == []
    )


def test_terminal_real_fact_target_is_not_silently_discarded() -> None:
    envelope, mode = parse_policy_envelope(
        json.dumps(
            {
                "action": {
                    "action_type": "final",
                    "target_type": "fact",
                    "target_id": "F1",
                    "content": "",
                }
            }
        )
    )
    assert mode == "json"
    assert envelope.action.target_id == "F1"
    assert "terminal_action_invalid_target" in policy_health_violations(
        envelope, StateManager().initial("terminal-real-target", "开场", max_turns=6)
    )


def test_action_only_runtime_policy_output_gets_empty_state_patch() -> None:
    envelope, mode = parse_policy_envelope(
        json.dumps(
            {
                "action": {
                    "action_type": "ask",
                    "target_type": "fact",
                    "target_id": "payment_date",
                    "reason": "该时间会影响期限分析",
                    "expected_information": "实际付款日期",
                    "content": "实际付款发生在哪一天？",
                    "constraints": [],
                    "confidence": 0.8,
                }
            },
            ensure_ascii=False,
        )
    )
    assert mode == "json"
    assert envelope.state_patch == StatePatch()
    assert envelope.action.target_id == "payment_date"


def test_policy_normalization_drops_echo_and_creates_missing_safe_target() -> None:
    state = StateManager().initial("normalize", "客户已经说明合同发生争议。", max_turns=6)
    envelope = PolicyEnvelope(
        state_patch=StatePatch(
            observations=[
                FactObservation(
                    fact_id="opening_claim_01",
                    label="改写后的开场标签",
                    status="client_claimed",
                    value="客户已经说明合同发生争议",
                )
            ]
        ),
        action=StructuredAction(
            action_type="ask",
            target_type="fact",
            target_id="payment_date",
            expected_information="付款时间",
            content="实际付款发生在哪一天？",
        ),
    )
    normalized, changes = normalize_policy_envelope(envelope, state)
    canonical_target = normalized.action.target_id
    assert canonical_target is not None
    assert canonical_target.startswith("dialogue_fact_")
    assert changes == [
        "drop_unchanged_observation:opening_claim_01",
        f"canonicalize_runtime_target:payment_date->{canonical_target}",
        f"create_missing_action_target:{canonical_target}",
    ]
    assert [item.fact_id for item in normalized.state_patch.observations] == [canonical_target]
    assert normalized.state_patch.observations[0].label == "付款时间"


def test_policy_normalization_reuses_one_unasked_visible_semantic_target() -> None:
    state = StateManager().initial("reuse-visible", "客户申请取消订单。", max_turns=7)
    state.facts.extend(
        [
            FactSlot(
                fact_id="cancellation_policy_content",
                label="订单中明确记载的取消规则具体内容",
                status="unknown",
            ),
            FactSlot(
                fact_id="booking_terms_access",
                label="预订发生的具体时间",
                status="not_available",
            ),
            FactSlot(
                fact_id="refusal_reason_details",
                label="客栈拒绝退款的具体时间",
                status="not_available",
            ),
        ]
    )
    envelope = PolicyEnvelope(
        action=StructuredAction(
            action_type="ask",
            target_type="fact",
            target_id="policy_terms_detail",
            expected_information="订单中关于取消规则的具体条款内容",
            content="订单中关于取消规则的具体条款内容是什么？",
        )
    )
    normalized, changes = normalize_policy_envelope(envelope, state)
    assert normalized.action.target_id == "cancellation_policy_content"
    assert normalized.state_patch.observations == []
    assert changes == [
        "reuse_visible_aligned_target:policy_terms_detail->cancellation_policy_content"
    ]


def test_ambiguous_visible_target_identity_is_not_chosen_by_infrastructure() -> None:
    state = StateManager().initial("ambiguous-reuse", "客户申请取消订单。", max_turns=7)
    state.facts.extend(
        [
            FactSlot(
                fact_id="booking_terms_content",
                label="预订时展示的取消规则具体内容",
                status="not_available",
            ),
            FactSlot(
                fact_id="refusal_terms_content",
                label="客栈拒绝退款时引用的取消规则具体内容",
                status="not_available",
            ),
        ]
    )
    envelope = PolicyEnvelope(
        action=StructuredAction(
            action_type="ask",
            target_type="fact",
            target_id="new_visible_gap",
            expected_information="取消规则的具体内容",
            content="取消规则的具体内容是什么？",
        )
    )

    normalized, changes = normalize_policy_envelope(envelope, state)
    violations = policy_health_violations(normalized, state)

    assert normalized.action.target_id not in {
        "booking_terms_content",
        "refusal_terms_content",
    }
    assert any(item.startswith("create_missing_action_target:") for item in changes)
    assert (
        "new_fact_target_duplicates_visible_target:"
        "booking_terms_content,refusal_terms_content"
    ) in violations


def test_observation_bearing_new_target_reuses_one_exhausted_identity() -> None:
    state = StateManager().initial("observation-reuse", "客户接受医美项目。", max_turns=6)
    state.facts.append(
        FactSlot(
            fact_id="treatment_time",
            label="接受医美项目的发生时间",
            status="not_available",
        )
    )
    state.asked_targets.append("treatment_time")
    envelope = PolicyEnvelope(
        state_patch=StatePatch(
            observations=[
                FactObservation(
                    fact_id="fresh_treatment_time",
                    label="医美项目发生的具体时间",
                    status="unknown",
                )
            ]
        ),
        action=StructuredAction(
            action_type="ask",
            target_type="fact",
            target_id="fresh_treatment_time",
            expected_information="医美项目发生的具体时间",
            content="您接受医美项目的具体时间是什么时候？",
        ),
    )

    normalized, changes = normalize_policy_envelope(envelope, state)
    violations = policy_health_violations(normalized, state)

    assert normalized.action.target_id == "treatment_time"
    assert normalized.state_patch.observations == []
    assert changes == [
        "drop_runtime_target_alias:fresh_treatment_time",
        "reuse_exhausted_aligned_target:fresh_treatment_time->treatment_time",
    ]
    assert "target_not_available:treatment_time" in violations
    assert "repeated_fact_target:treatment_time" in violations


def test_open_gap_expected_dimension_must_match_visible_question() -> None:
    state = StateManager().initial("open-gap-self-alignment", "客户接受医美项目。", max_turns=6)
    envelope = PolicyEnvelope(
        action=StructuredAction(
            action_type="ask",
            target_type="fact",
            target_id="new_visible_gap",
            expected_information="怀疑机构资质的具体原因",
            content="您接受医美项目的具体时间是什么时候？",
        )
    )

    normalized, _ = normalize_policy_envelope(envelope, state)

    assert "question_target_misaligned" in policy_health_violations(normalized, state)


def test_document_external_arrangement_is_not_rebound_to_internal_clause() -> None:
    state = StateManager().initial("external-arrangement", "跨境货物买卖发生争议。", max_turns=6)
    state.facts.append(
        FactSlot(
            fact_id="contract_quality_clause",
            label="合同中是否约定了质量标准的具体内容",
            status="client_claimed",
        )
    )
    envelope = PolicyEnvelope(
        action=StructuredAction(
            action_type="ask",
            target_type="fact",
            target_id="new_visible_gap",
            expected_information="合同外其他书面或口头约定",
            content="除了合同外，是否有其他书面或口头约定涉及产品质量标准？",
        )
    )

    normalized, _ = normalize_policy_envelope(envelope, state)

    assert normalized.action.target_id != "contract_quality_clause"
    assert len(normalized.state_patch.observations) == 1


def test_contract_clause_identity_distinguishes_position_and_paraphrase() -> None:
    state = StateManager().initial(
        "contract-clause-identity", "跨境货物买卖发生争议。", max_turns=6
    )
    state.facts.append(
        FactSlot(
            fact_id="contract_quality_clause",
            label="合同中是否约定了质量标准的具体内容",
            status="not_available",
        )
    )
    counterparty_position = PolicyEnvelope(
        action=StructuredAction(
            action_type="ask",
            target_type="fact",
            target_id="new_visible_gap",
            expected_information="对方主张的质量标准",
            content="对方主张的质量标准是什么？",
        )
    )
    contract_paraphrase = PolicyEnvelope(
        action=StructuredAction(
            action_type="ask",
            target_type="fact",
            target_id="new_visible_gap",
            expected_information="合同中约定的质量标准具体内容",
            content="合同中约定的质量标准具体是什么？",
        )
    )

    position_normalized, _ = normalize_policy_envelope(counterparty_position, state)
    clause_normalized, _ = normalize_policy_envelope(contract_paraphrase, state)

    assert position_normalized.action.target_id != "contract_quality_clause"
    assert clause_normalized.action.target_id == "contract_quality_clause"


@pytest.mark.parametrize(
    ("visible_label", "expected", "question"),
    [
        (
            "店方多次处理的持续时间",
            "店方首次处理的发生时间",
            "店方第一次处理是在什么时间？",
        ),
        (
            "公司解除劳动合同",
            "解除后的工资结算时间",
            "解除劳动合同后，公司在什么时候结算工资？",
        ),
        (
            "后续接续施工的具体范围以及实际完成情况",
            "后续接续施工的实际完成情况",
            "后续接续施工实际完成到什么程度？",
        ),
        (
            "合同中是否约定了适用法律规则和质量标准",
            "合同中约定的适用法律规则",
            "合同中约定的适用法律规则是什么？",
        ),
    ],
)
def test_new_fact_identity_does_not_collapse_distinct_complete_dimensions(
    visible_label: str,
    expected: str,
    question: str,
) -> None:
    state = StateManager().initial("strict-fact-identity", "客户已经说明争议背景。", max_turns=6)
    state.facts.append(
        FactSlot(
            fact_id="exhausted_visible_fact",
            label=visible_label,
            status="not_available",
        )
    )
    state.asked_targets.append("exhausted_visible_fact")
    envelope = PolicyEnvelope(
        action=StructuredAction(
            action_type="ask",
            target_type="fact",
            target_id="new_visible_gap",
            expected_information=expected,
            content=question,
        )
    )

    normalized, changes = normalize_policy_envelope(envelope, state)

    assert normalized.action.target_id != "exhausted_visible_fact"
    assert len(normalized.state_patch.observations) == 1
    assert not any(item.startswith("reuse_exhausted_aligned_target:") for item in changes)


def test_new_fact_identity_reuses_the_same_duration_dimension() -> None:
    state = StateManager().initial("duration-identity", "履行发生迟延。", max_turns=6)
    state.facts.append(
        FactSlot(
            fact_id="delay_duration",
            label="迟延发生的具体时间长度",
            status="not_available",
        )
    )
    envelope = PolicyEnvelope(
        action=StructuredAction(
            action_type="ask",
            target_type="fact",
            target_id="new_visible_gap",
            expected_information="迟延的具体持续时长",
            content="迟延一共持续了多长时间？",
        )
    )

    normalized, _ = normalize_policy_envelope(envelope, state)

    assert normalized.action.target_id == "delay_duration"


def test_new_fact_metadata_conflict_cannot_be_hidden_by_surface_rebinding() -> None:
    state = StateManager().initial("metadata-conflict", "客户已付款。", max_turns=6)
    state.facts.append(
        FactSlot(
            fact_id="payment_time",
            label="实际付款时间",
            status="not_available",
        )
    )
    envelope = PolicyEnvelope(
        action=StructuredAction(
            action_type="ask",
            target_type="fact",
            target_id="new_visible_gap",
            expected_information="实际付款金额",
            content="这笔款项具体是什么时候支付的？",
        )
    )

    normalized, _ = normalize_policy_envelope(envelope, state)
    violations = policy_health_violations(normalized, state)

    assert normalized.action.target_id != "payment_time"
    assert "question_target_misaligned" in violations


def test_renderer_never_exposes_snake_case_slot() -> None:
    state = StateManager().initial("render-slot", "开场", max_turns=6)
    state.facts.append(FactSlot(fact_id="event_time", label="event_time"))
    action = StructuredAction(action_type="ask", target_type="fact", target_id="event_time")
    question = render_action(action, state)
    assert "event_time" not in question
    assert "关键时间" in question


def test_client_response_detects_and_sanitizes_internal_slots() -> None:
    value = "event_time是9月2日，这明显是侵权。"
    assert response_violations(value)
    sanitized = sanitize_client_response(value)
    assert "event_time" not in sanitized
    assert sanitized.startswith("按我的理解，")


def test_fact_selection_parser_is_strict_and_single_fact() -> None:
    valid_ids = ["F1", "F2", "F3"]
    assert parse_fact_selection('{"fact_ids":["F1"]}', valid_ids) == ["F1"]
    assert parse_fact_selection('说明 {"fact_ids":[]}', valid_ids) == []
    assert parse_fact_selection('{"fact_ids":["F0","F1"]}', valid_ids) is None
    assert parse_fact_selection('{"fact_ids":["F9"]}', valid_ids) is None
    assert parse_fact_selection('{"fact_ids":["F1"],"answer":"编造"}', valid_ids) is None
    current = parse_fact_selection_decision(
        '{"fact_ids":["F1"],"disclosure":"withhold"}', valid_ids
    )
    assert current is not None
    assert current.fact_ids == ["F1"]
    assert current.disclosure == "withhold"
    assert current.legacy_format is False
    legacy = parse_fact_selection_decision('{"fact_ids":["F2"]}', valid_ids)
    assert legacy is not None
    assert legacy.disclosure == "disclose"
    assert legacy.legacy_format is True
    assert (
        parse_fact_selection_decision('{"fact_ids":[],"disclosure":"withhold"}', valid_ids) is None
    )
    assert parse_relevance_check('{"answers_question":true}') is True
    assert parse_relevance_check('{"answers_question":false}') is False
    assert parse_relevance_check('{"answers_question":"true"}') is None


def test_structured_relevance_analysis_is_strict_and_auditable() -> None:
    value = {
        "question_actor": "客户",
        "question_predicate": "是否告知",
        "question_attribute": "全部询问",
        "candidate_actor": "保险公司",
        "candidate_predicate": "提出拒赔理由",
        "candidate_attribute": "声称客户未告知疾病",
        "candidate_assertion_source": "reported_other_claim",
        "same_actor": False,
        "same_predicate": False,
        "same_attribute": False,
        "answers_question": False,
    }
    assert set(value) == set(CLIENT_RELEVANCE_ANALYSIS_SCHEMA["required"])
    encoded = json.dumps(value, ensure_ascii=False)
    assert parse_relevance_analysis(encoded) == value
    assert parse_relevance_check(encoded) is False

    malformed = dict(value)
    malformed["unexpected"] = True
    assert parse_relevance_analysis(json.dumps(malformed, ensure_ascii=False)) is None


@pytest.mark.parametrize("persona_id", ["P_CS", "P_CD"])
def test_resistant_persona_withholding_does_not_hide_fact_match_or_force_unavailable(
    persona_id: str,
) -> None:
    belief = "平台在2022年8月10日通过站内消息发送过续费提醒。"
    selector = WithholdThenDiscloseSelector("F1")
    simulator = ClientSimulator(
        case_view={
            "opening": "我发现平台自动续费。",
            "facts": [{"fact_id": "F1", "client_belief": belief}],
        },
        persona={"persona_id": persona_id},
        model=selector,  # type: ignore[arg-type]
        relevance_model=ApprovingRelevanceVerifier(),  # type: ignore[arg-type]
        retry_empty_selection=True,
        prompt_template="{persona_who}{persona_voice}\n{facts_block}\n{disclosed_fact_ids}",
        relevance_prompt="判断候选事实是否直接回答问题。",
        generation=GenerationConfig(temperature=0, top_p=1, max_tokens=96, seed=42),
        max_selection_attempts=2,
    )

    first, _ = simulator.respond(
        "你们为什么隐瞒续费提醒？马上交代。",
        42,
    )

    assert simulator.last_matched_fact_ids == ["F1"]
    assert simulator.last_selected_fact_ids == []
    assert simulator.last_disclosure_decision == "withhold"
    assert simulator.last_response_kind == "withheld"
    assert "2022年8月10日" not in first.content
    assert simulator.disclosed_fact_ids == set()

    second, _ = simulator.respond(
        "我询问提醒情况只是为了判断平台是否履行告知义务；您是否记得它有没有发过？",
        43,
    )

    assert simulator.last_response_kind == "new_hidden_fact"
    assert simulator.last_selected_fact_ids == ["F1"]
    assert simulator.last_disclosure_decision == "disclose"
    assert "2022年8月10日" in second.content
    assert simulator.disclosed_fact_ids == {"F1"}
    assert simulator.history[0][0] == "你们为什么隐瞒续费提醒？马上交代。"
    assert all(
        item.response_schema == client_fact_selection_schema(["F1"])
        for item in selector.generations
    )
    assert all(
        item.response_schema_name == "legal_skill_guard_client_fact_selection_v3"
        for item in selector.generations
    )


def test_p_cs_repairs_length_truncated_disclosure_without_defaulting() -> None:
    selector = LengthThenDisclosureSelector()
    simulator = ClientSimulator(
        case_view={
            "opening": "房屋被纳入刑事追缴。",
            "facts": [
                {
                    "fact_id": "F1",
                    "client_belief": "公安已经立案并对房屋作出追缴决定。",
                }
            ],
        },
        persona={"persona_id": "P_CS"},
        model=selector,  # type: ignore[arg-type]
        relevance_model=ApprovingRelevanceVerifier(),  # type: ignore[arg-type]
        prompt_template="{persona_who}{persona_voice}\n{facts_block}\n{disclosed_fact_ids}",
        relevance_prompt="判断候选事实是否直接回答问题。",
        generation=GenerationConfig(temperature=0, top_p=1, max_tokens=96, seed=42),
        max_selection_attempts=2,
        recall_max_tokens=768,
        recall_disable_thinking=False,
        retry_empty_selection=True,
    )

    response, _ = simulator.respond(
        "关联刑案是否已经立案并作出追缴决定？",
        42,
    )

    assert simulator.last_safe_fallback is False
    assert simulator.last_response_kind == "new_hidden_fact"
    assert simulator.last_disclosure_decision == "disclose"
    assert "已经立案" in response.content
    assert len(simulator.last_disclosure_attempts) == 2
    first, repaired = selector.disclosure_generations
    assert first.disable_thinking is False and first.max_tokens == 768
    assert repaired.disable_thinking is True and repaired.max_tokens == 32


def test_event_attribute_guard_rejects_dates_for_a_different_event() -> None:
    question = "这套房屋是什么时候购买的？"
    assert event_attribute_compatible(question, "我们结婚后一个月登记成夫妻两人名字。") is False
    assert event_attribute_compatible(question, "这套房是他在婚前购买的。") is True
    assert (
        event_attribute_compatible(
            "房屋登记到双方名下的具体日期是什么时候？",
            "我们2009年1月登记结婚，房屋在次月就改成了夫妻两人的名字。",
        )
        is True
    )
    assert (
        event_attribute_compatible(
            "丈夫婚前购买房屋的准确日期是哪一天？",
            "我们2009年1月登记结婚，房屋在次月改成夫妻两人的名字。",
        )
        is False
    )


def test_cognitive_subject_guard_rejects_client_counterparty_role_swap() -> None:
    assert cognitive_subject_role("您是否知道不治疗可能导致不可逆后果？") == "client"
    assert cognitive_subject_role("按我的理解，他知道不治疗可能导致不可逆后果。") == (
        "counterparty"
    )
    assert cognitive_subject_role("您是否清楚丈夫知道不治疗可能导致不可逆后果？") == (
        "counterparty"
    )
    assert deterministic_relevance_compatibility(
        "您是否知道不治疗可能导致不可逆后果？",
        "按我的理解，他知道不治疗可能导致不可逆后果。",
    ) == (False, ["cognitive_subject_mismatch:client->counterparty"])
    assert deterministic_relevance_compatibility(
        "您是否清楚丈夫知道不治疗可能导致不可逆后果？",
        "按我的理解，他知道不治疗可能导致不可逆后果。",
    ) == (True, [])


def test_cognitive_purpose_requires_knowledge_or_explicit_purpose() -> None:
    question = "您当时对这笔钱款的具体用途是否有所了解？"
    movement_only = "三名老人共交付6万元，我随后把钱交给他人并获利1700元。"
    explicit_knowledge = (
        "我在出发前就知道这份差事是到各地帮助收取诈骗资金并从中获利。"
    )
    explicit_purpose = "这笔钱是为了支付涉案货款。"

    assert "requested_cognitive_purpose_missing" in direct_answer_attribute_violations(
        question, movement_only
    )
    assert "requested_cognitive_purpose_missing" not in direct_answer_attribute_violations(
        question, explicit_knowledge
    )
    assert "requested_cognitive_purpose_missing" not in direct_answer_attribute_violations(
        question, explicit_purpose
    )


def test_client_simulator_vetoes_semantically_approved_wrong_cognitive_subject() -> None:
    simulator = ClientSimulator(
        case_view={
            "facts": [
                {
                    "fact_id": "F3",
                    "client_belief": "他知道不系统治疗可能产生不可逆后果。",
                }
            ]
        },
        persona={"persona_id": "P_WD"},
        model=FactThreeSelector(),  # type: ignore[arg-type]
        prompt_template="{persona_who}{persona_voice}\n{facts_block}\n{disclosed_fact_ids}",
        relevance_prompt="判断候选事实是否直接回答问题。",
        generation=GenerationConfig(temperature=0, top_p=1, max_tokens=10, seed=42),
        max_selection_attempts=2,
    )
    response, _ = simulator.respond("您是否知道不治疗可能导致不可逆后果？", 42)
    assert simulator.last_selected_fact_ids == []
    assert simulator.last_safe_fallback is False
    assert "需要再核实" in response.content
    assert all(
        attempt["deterministic_compatibility_violations"]
        == ["cognitive_subject_mismatch:client->counterparty"]
        for attempt in simulator.last_relevance_attempts
    )
    assert (
        event_attribute_compatible("房屋何时登记到夫妻双方名下？", "婚后次月房本改成夫妻两人名字。")
        is True
    )


def test_direct_answer_attribute_contract_rejects_partial_or_ambiguous_answers() -> None:
    assert direct_answer_attribute_violations(
        "宣传通过什么渠道、声称什么功效？",
        "店家宣传可以降三高。",
    ) == ["requested_channel_missing"]
    assert direct_answer_attribute_violations(
        "你本人是否投加或指使员工投加？",
        "我们购买后投加到处理末端。",
    ) == ["requested_individual_actor_ambiguous"]
    assert direct_answer_attribute_violations(
        "每次交易采用什么收款方式？",
        "我要求卖家提供银行卡。",
    ) == ["requested_payment_method_missing"]
    assert (
        direct_answer_attribute_violations(
            "每次交易采用什么收款方式？",
            "上线通过银行卡转账给卖家。",
        )
        == []
    )
    assert direct_answer_attribute_violations(
        "行政机关认定规划问题所依据的文件或资料名称是什么？",
        "审批局2020年11月同意建设项目并要求在当年开工。",
    ) == ["requested_basis_document_role_missing"]
    assert (
        direct_answer_attribute_violations(
            "行政机关认定规划问题所依据的文件或资料名称是什么？",
            "拒绝主要依据是已经到期规划的报批稿。",
        )
        == []
    )
    assert direct_answer_attribute_violations(
        "您在案件审理前是否尝试向有关部门报告相关情况？",
        "我在出发前知道是帮助收取诈骗资金，随后添加上线接受安排。",
    ) == ["requested_authority_report_action_missing"]
    assert (
        direct_answer_attribute_violations(
            "您在案件审理前是否尝试向有关部门报告相关情况？",
            "我在开庭前主动向公安机关报告了相关情况。",
        )
        == []
    )
    assert direct_answer_attribute_violations(
        "实际使用该标识的地理范围是哪些地区？",
        "多个平台上的消费者用这句话指代特定款香水。",
    ) == ["requested_geographic_range_missing"]
    assert (
        direct_answer_attribute_violations(
            "实际使用该标识的地理范围是哪些地区？",
            "我们从2020年开始在中国销售该香水。",
        )
        == []
    )
    assert direct_answer_attribute_violations(
        "实际使用该标识时所针对的消费者群体是哪些？",
        "我们从2020年开始在中国销售以该标识命名的香水。",
    ) == ["requested_target_audience_missing"]
    assert (
        direct_answer_attribute_violations(
            "实际使用该标识时所针对的消费者群体是哪些？",
            "该香水主要面向中国的成年女性消费者。",
        )
        == []
    )
    assert direct_answer_attribute_explicit_match(
        "这项服务面向哪类目标客户？",
        "这项服务主要面向企业客户。",
    )
    assert direct_answer_attribute_violations(
        "这套房屋最初购置的具体时间是什么时候？",
        "该房屋由丈夫婚前购买，我没有参与取得产权。",
    ) == ["requested_precise_time_missing"]
    assert direct_answer_attribute_violations(
        "该房屋购置时的出资来源是否全部或部分由你方出资？",
        "房屋最初由他婚前购买，我没有参与取得产权。",
    ) == ["requested_purchase_funding_missing"]
    assert (
        direct_answer_attribute_violations(
            "该房屋购置时的出资来源是否全部或部分由你方出资？",
            "购房款全部由丈夫婚前全款支付，我没有出资。",
        )
        == []
    )
    assert direct_answer_attribute_violations(
        "房产证上登记的产权人份额是什么？",
        "房屋在婚后改成夫妻两人的名字。",
    ) == ["requested_registered_ownership_share_missing"]
    assert (
        direct_answer_attribute_violations(
            "房产证上登记的产权人份额是什么？",
            "不动产登记为双方共同共有，没有记载具体比例。",
        )
        == []
    )
    assert (
        direct_answer_attribute_violations(
            "你将名字加到房产证上的具体时间是什么时候？",
            "我们2009年1月结婚，房屋在次月改成夫妻两人的名字。",
        )
        == []
    )
    assert deterministic_relevance_compatibility(
        "房屋婚后将你名字加上的具体日期是什么时候？",
        "我们2009年1月结婚，房屋在次月改成夫妻两人的名字。",
    ) == (True, [])
    assert direct_answer_attribute_explicit_match(
        "房屋婚后将你名字加上的具体日期是什么时候？",
        "我们2009年1月结婚，房屋在次月改成夫妻两人的名字。",
    )
    assert direct_answer_attribute_explicit_match(
        "丈夫何时把你的名字加到房屋登记上？",
        "我们2009年1月结婚，房屋在次月改成夫妻两人的名字。",
    )
    assert not direct_answer_attribute_explicit_match(
        "婚后共同偿还房贷的具体时间是什么？",
        "我们2009年1月结婚，房屋在次月改成夫妻两人的名字。",
    )
    assert direct_answer_attribute_explicit_match(
        "孩子母亲采取了哪些制止措施？",
        "动手的是继父，她没有制止。",
    )
    assert deterministic_relevance_compatibility(
        "你们现在正在谈离婚吗？",
        "我们2009年登记结婚，次月房屋改成夫妻双方名字。",
    ) == (False, ["different_event_concept"])
    assert (
        event_attribute_compatible(
            "房屋购置时的出资来源是什么？",
            "我们结婚后一个月把房屋登记成夫妻双方名字。",
        )
        is False
    )
    assert (
        event_attribute_compatible(
            "小儿子受伤的具体情况是怎样的？",
            "我探望时发现孩子受伤，公安查明继父两次用物品殴打孩子。",
        )
        is True
    )
    assert deterministic_relevance_compatibility(
        "婚后共同偿还房贷的具体时间是什么？",
        "我们2009年1月结婚，房屋在次月改成夫妻两人的名字。",
    ) == (False, ["different_event_concept"])
    assert (
        event_attribute_compatible(
            "婚后共同偿还房贷的具体时间是什么？",
            "婚后我们从2010年起每月共同还贷。",
        )
        is True
    )
    assert deterministic_relevance_compatibility(
        "你是否对该房屋有实际出资或贡献？",
        "房屋最初由他婚前购买，我没有参与取得产权。",
    ) == (True, [])
    assert deterministic_relevance_compatibility(
        "小儿子受伤后是否已经获得了医疗或照料？",
        "我探望时发现孩子受伤并报警，公安查明继父两次殴打孩子。",
    ) == (False, ["requested_medical_or_care_response_missing"])
    assert deterministic_relevance_compatibility(
        "母亲在照料孩子期间是否有不当行为或疏忽？",
        "继父已经被治安处罚，证明并非普通管教。",
    ) == (False, ["observable_action_subject_mismatch:mother->stepfather"])
    assert (
        deterministic_relevance_compatibility(
            "母亲在孩子受伤时采取了哪些保护措施？",
            "动手的是继父，母亲没有制止。",
        )[0]
        is not False
    )
    assert deterministic_relevance_compatibility(
        "是否存在书面或口头确认员工继续工作的记录？",
        "公司多次通过口头和微信通知员工续签，但员工主动拒绝。",
    ) == (False, ["different_event_concept"])
    assert (
        event_attribute_compatible(
            "员工是否同意续签或继续履行原合同？",
            "公司多次通知续签，但员工主动拒绝。",
        )
        is True
    )
    assert (
        event_attribute_compatible(
            "双方是否就劳动合同续签达成一致或存在书面协议？",
            "员工与原公司签过解除协议，确认解除日前工资没有拖欠。",
        )
        is False
    )
    assert direct_answer_attribute_violations(
        "公司出具的不真实报告具体有哪些类型和内容？",
        "报告涉及五个地市、44家委托单位和多个行业监测项目。",
    ) == ["requested_report_content_missing"]
    assert (
        direct_answer_attribute_violations(
            "检测报告具体记载了哪些数据或结论？",
            "检测报告载明废水COD浓度超标。",
        )
        == []
    )
    assert (
        direct_answer_attribute_violations(
            "请问具体是哪些部门或人员参与了报告制作及数据处理？",
            "吴某平负责行政、财务和销售，罗某鹏负责实验室数据分析，"
            "郑某钊负责采样取数，练某春负责编写报告。",
        )
        == []
    )
    assert (
        direct_answer_attribute_violations(
            "公司内部对检测报告的审核及数据校验具体流程是怎样的？",
            "报告由实验室分析、现场采样和报告编制岗位依次处理。",
        )
        == []
    )
    assert (
        direct_answer_attribute_violations(
            "作为总经理，您是否知情并参与了涉及数据造假的检测报告相关决策过程？",
            "我负责公司全面管理，具体业务由各部门主管负责。",
        )
        == []
    )
    assert direct_answer_attribute_violations(
        "验资报告中是否明确记载增资资金已经完成出资？",
        "资金虽然经过账户流转，但我没有看到验资报告记载出资已经完成。",
    ) == []
    assert (
        direct_answer_attribute_violations(
            "小儿子目前是由谁实际在照顾他？",
            "孩子被接回后在我这里生活愉快，也已经适应新的学校。",
        )
        == []
    )
    assert (
        direct_answer_attribute_violations(
            "小儿子目前是由谁实际在照顾他？",
            "离婚后一直由母亲照料。",
        )
        == []
    )
    assert (
        hidden_fact_adds_question_information(
            "小儿子目前是由谁实际在照顾他？",
            "离婚后由母亲照料的小儿子近期受伤，现在暂时跟我生活。",
            "孩子被接回后在我这里生活愉快，也已经适应新的学校。",
        )
        is False
    )
    assert (
        hidden_fact_adds_question_information(
            "小儿子现在跟谁生活？",
            "离婚后由母亲照料的小儿子被发现受伤，现在跟我生活。",
            "孩子被接回后在我这里生活愉快，也已经适应新的学校。",
        )
        is False
    )
    assert (
        hidden_fact_adds_question_information(
            "孩子被接回后目前的生活和就学情况怎样？",
            "离婚后由母亲照料的小儿子近期受伤，现在暂时跟我生活。",
            "孩子被接回后在我这里生活愉快，也已经适应新的学校。",
        )
        is None
    )
    assert direct_answer_attribute_violations(
        "客户在申请经营许可前是否与行政机关有过沟通？",
        "审批局先称规划核准不属于其业务，后以不符合规划为由拒绝许可。",
    ) == ["requested_pre_application_communication_missing"]
    assert (
        direct_answer_attribute_violations(
            "客户在申请经营许可前是否与行政机关有过沟通？",
            "提交申请前我曾向审批局咨询，工作人员作了口头答复。",
        )
        == []
    )
    assert direct_answer_attribute_violations(
        "对方将获取的数据用于何种具体商业目的？",
        "对方获取用户cookie并绕开风控、突破正常访问权限批量爬取。",
    ) == ["requested_data_use_purpose_missing"]
    assert (
        direct_answer_attribute_violations(
            "对方将获取的数据用于何种具体商业目的？",
            "对方将数据加工成价格监测、市场分析和定制API并有偿提供。",
        )
        == []
    )


@pytest.mark.parametrize(
    ("question", "irrelevant_term", "violation"),
    [
        (
            "购销合同是否约定逾期利息以及具体利率标准？",
            "双方于2022年1月1日签订购销合同，并约定每月结算货款。",
            "requested_overdue_interest_term_missing",
        ),
        (
            "平台与商户协议对数据使用范围和限制具体如何约定？",
            "平台与商户协议约定，经授权合法持有商品数据并享有相应加工利用利益。",
            "requested_data_use_scope_term_missing",
        ),
        (
            "购销合同约定的供货频率是多久一次？",
            "双方约定每月结算货款。",
            "requested_supply_frequency_term_missing",
        ),
        (
            "续签后的劳动合同实际内容或口头约定的具体条款是什么？",
            "公司多次通知员工续签，但员工主动拒绝。",
            "requested_renewal_terms_missing",
        ),
    ],
)
def test_contract_specific_term_cannot_recover_a_different_contract_term(
    question: str,
    irrelevant_term: str,
    violation: str,
) -> None:
    violations = direct_answer_attribute_violations(question, irrelevant_term)
    assert violation in violations
    assert not direct_answer_attribute_explicit_match(question, irrelevant_term)


@pytest.mark.parametrize(
    ("question", "answer"),
    [
        (
            "购销合同是否约定逾期利息以及具体利率标准？",
            "合同约定逾期付款按一年期LPR加计百分之三计算利息。",
        ),
        (
            "平台与商户协议对数据使用范围和限制具体如何约定？",
            "协议约定商品数据仅限用于店铺经营分析，不得向第三方提供。",
        ),
        (
            "购销合同约定的供货频率是多久一次？",
            "合同约定供应商每周供货一次。",
        ),
        (
            "双方在购销合同中约定的付款条件是什么？",
            "双方约定每月结算货款。",
        ),
        (
            "续签后的劳动合同实际内容或口头约定的具体条款是什么？",
            "双方续签时约定合同期限两年，工资为每月一万元。",
        ),
    ],
)
def test_contract_specific_term_accepts_same_explicit_attribute(question: str, answer: str) -> None:
    assert direct_answer_attribute_violations(question, answer) == []
    assert direct_answer_attribute_explicit_match(question, answer)


@pytest.mark.parametrize(
    "answer",
    [
        "形式发票记载型号、数量和单价，但没有特定质量标准。",
        "形式发票列明具体型号、数量和价格，但未载明ECE R27质量标准。",
        "后续数次交易也未书面约定产品质量标准。",
    ],
)
def test_contract_quality_term_accepts_explicit_same_topic_absence(
    answer: str,
) -> None:
    question = "合同中对产品质量标准的具体约定是什么？"
    assert deterministic_relevance_compatibility(question, answer) == (True, [])


def test_contract_term_dispute_does_not_masquerade_as_clause_content() -> None:
    question = "合同中关于质量标准的具体约定内容是什么？"
    opening = "双方对合同适用规则、质量标准是否约定及如何确定存在争议。"

    assert "requested_contract_term_missing" in direct_answer_attribute_violations(
        question, opening
    )
    assert not direct_answer_attribute_explicit_match(question, opening)


def test_contract_applicable_law_term_accepts_plain_language_absence() -> None:
    question = "合同中关于适用法律的条款具体内容是什么？"
    answer = "双方没选法律，中国法院就只能适用中国国内合同法。"

    assert direct_answer_attribute_violations(question, answer) == []
    assert direct_answer_attribute_explicit_match(question, answer)


def test_contract_quality_term_does_not_accept_a_broad_dispute_or_other_topic() -> None:
    question = "合同中对产品质量标准的具体约定是什么？"
    for non_answer in (
        "双方对质量标准是否约定存在争议。",
        "合同中没有约定逾期付款利率。",
        "买方后来口头表示继续沿用此前交易的规格，且此前没有提出质量异议。",
    ):
        compatible, violations = deterministic_relevance_compatibility(question, non_answer)
        assert compatible is False
        assert any(
            item in violations
            for item in (
                "requested_contract_term_missing",
                "requested_quality_standard_term_missing",
            )
        )


def test_contract_assent_question_is_not_misclassified_as_term_content() -> None:
    question = "关于双方是否就劳动合同续签达成一致或存在口头约定，请说明一项具体事实？"
    refusal = "合同到期后公司多次通过口头和微信通知他续签，但他主动拒绝。"
    assert direct_answer_attribute_violations(question, refusal) == []
    assert deterministic_relevance_compatibility(question, refusal) == (True, [])

    content_question = "续签后的劳动合同实际内容或口头约定的具体条款是什么？"
    assert "requested_contract_term_missing" in direct_answer_attribute_violations(
        content_question, refusal
    )


def test_refused_renewal_answers_only_the_new_contract_signature_question() -> None:
    refusal = "合同到期后公司多次通过口头和微信通知他续签，但他主动拒绝。"
    signature_question = "双方最终是否签署了新的书面劳动合同？"
    assert direct_answer_attribute_explicit_match(signature_question, refusal)
    assert deterministic_relevance_compatibility(signature_question, refusal) == (True, [])

    notice_only = "合同到期后公司通过微信通知员工续签。"
    assert not direct_answer_attribute_explicit_match(signature_question, notice_only)
    assert deterministic_relevance_compatibility(signature_question, notice_only) == (
        False,
        ["different_event_concept"],
    )

    unrelated_refusal = "员工拒绝调岗，但继续在原岗位工作。"
    assert not direct_answer_attribute_explicit_match(signature_question, unrelated_refusal)


def test_payment_schedule_is_payment_but_not_supply_frequency() -> None:
    schedule = "双方于2022年1月1日签订购销合同，并约定每月结算货款。"
    assert deterministic_relevance_compatibility(
        "双方在合同中约定的付款条件是什么？", schedule
    ) == (True, [])
    assert deterministic_relevance_compatibility(
        "购销合同约定的供货频率是多久一次？", schedule
    ) == (False, ["requested_supply_frequency_term_missing"])


def test_presupposition_correction_is_a_direct_answer_only_for_the_same_object() -> None:
    question = "银行发出的提前清偿通知中具体提到了哪些理由？"
    correction = "银行没有向公司发出宣布贷款提前到期的通知。"
    assert presupposition_correction_match(question, correction)
    assert deterministic_relevance_compatibility(question, correction) == (True, [])
    assert not presupposition_correction_match(
        question,
        "公司没有签署新的担保协议。",
    )
    assert not presupposition_correction_match(
        "银行是否发出过提前清偿通知？",
        correction,
    )
    assert not presupposition_correction_match(
        "双方就续签劳动合同达成的书面协议具体写了什么？",
        "员工与原公司签过解除协议，确认解除日前的工资没有拖欠。",
    )
    assert not presupposition_correction_match(
        "不真实报告具体记载了哪些检测数据或结论？",
        "主管人员没有亲自编写每份报告，只是默许或放任。",
    )
    assert presupposition_correction_match(
        "双方签署的续签协议具体写了什么？",
        "双方从未签署任何续签协议。",
    )


def test_case_0007_health_disclosure_is_not_missing_document_correction() -> None:
    question = "您在投保时是否实际阅读并确认了电子健康告知书的内容？"
    rejection_reason = (
        "保险公司的拒赔理由是我投保时没有告知慢性支气管炎，并称这一情况严重影响其承保决定。"
    )

    assert not presupposition_correction_match(question, rejection_reason)

    simulator = ClientSimulator(
        case_view={
            "opening": "我通过互联网投保了一份防癌险，后来确诊并申请理赔。",
            "facts": [{"fact_id": "F6", "client_belief": rejection_reason}],
        },
        persona={"persona_id": "P_WD"},
        model=EmptyFactSelector(),  # type: ignore[arg-type]
        prompt_template="{persona_who}{persona_voice}\n{facts_block}\n{disclosed_fact_ids}",
        relevance_prompt="判断候选事实是否直接回答问题。",
        generation=GenerationConfig(temperature=0, top_p=1, max_tokens=10, seed=42),
        max_selection_attempts=2,
    )

    simulator.respond(
        question,
        42,
    )

    assert simulator.last_selected_fact_ids == []
    assert simulator.last_response_kind == "unavailable"
    assert simulator.last_relevance_attempts == []


def test_assessment_method_requires_the_requested_risk_subject() -> None:
    question = "银行评估保证人风险所依据的具体标准是什么？"
    assert direct_answer_attribute_violations(
        question,
        "合同把任何逾期列作提前到期事件。",
    ) == ["requested_assessment_subject_missing"]
    assert (
        direct_answer_attribute_violations(
            question,
            "保证人执行案件已经和解终结，贷款另有多份人保和物保。",
        )
        == []
    )


def test_contract_term_question_rejects_notice_belief_and_accepts_clause_belief() -> None:
    question = "贷款合同中是否包含有关提前清偿贷款的条款？"
    notice_belief = "银行没有向公司发出宣布贷款提前到期的通知。"
    clause_belief = "合同把任何逾期列作提前到期事件。"

    compatible, violations = deterministic_relevance_compatibility(question, notice_belief)
    assert compatible is False
    assert "requested_contract_term_missing" in violations
    assert deterministic_relevance_compatibility(question, clause_belief) == (True, [])


def test_agreement_content_question_distinguishes_terms_from_metadata_and_effect() -> None:
    question = "您签署的补助协议具体写了哪些内容？请详细说明。"
    substantive_term = "双方约定不缴社保而将相关费用作为补助发放。"
    document_origin = "这份不缴社保约定是公司事先打印好的。"
    signature_effect = "我本人签了字，可能已经放弃要求公司参保的权利。"

    assert deterministic_relevance_compatibility(question, substantive_term) == (True, [])
    for non_term in (document_origin, signature_effect):
        compatible, violations = deterministic_relevance_compatibility(question, non_term)
        assert compatible is False
        assert "requested_contract_term_missing" in violations


def test_agreement_content_question_accepts_same_object_nonexistence_correction() -> None:
    assert deterministic_relevance_compatibility(
        "双方签署的补助协议具体内容是什么？",
        "双方并未签署补助协议。",
    ) == (True, [])


def test_agreement_provenance_question_does_not_require_substantive_term() -> None:
    assert deterministic_relevance_compatibility(
        "这份约定由谁提供，是公司预先打印还是由您起草？",
        "这份不缴社保约定是公司事先打印好的。",
    ) == (None, [])


def test_reminder_content_rejects_delivery_salience_but_accepts_message_substance() -> None:
    question = "平台发送的续费提醒具体包含哪些内容？"
    delivery_salience = "平台虽发过站内消息，但没有弹窗，查看路径也不清楚。"
    substantive_message = "站内消息写明会员将在8月20日续费30元。"

    compatible, violations = deterministic_relevance_compatibility(question, delivery_salience)
    assert compatible is False
    assert "requested_communication_content_missing" in violations
    assert deterministic_relevance_compatibility(question, substantive_message) == (True, [])


def test_case_0017_existence_question_meta_instruction_does_not_request_content() -> None:
    question = "平台是否发送了续费提醒？请说明一项事实。"
    fact = "平台在2022年8月10日发过站内消息，但没有弹窗，查看路径也不清楚，我实际很难注意到。"

    assert not asks_communication_content(question)
    assert asks_communication_existence(question)
    assert deterministic_relevance_compatibility(question, fact) == (True, [])


def test_client_simulator_matches_the_observed_question_and_keeps_surface_history() -> None:
    model = RecordingFactThreeSelectorAndVerifier()
    simulator = ClientSimulator(
        case_view={
            "opening": "我购买的视频会员最近再次自动扣费，我不记得是否收到过有效的续费提醒。",
            "facts": [
                {
                    "fact_id": "F3",
                    "client_belief": (
                        "平台在2022年8月10日发过站内消息，但没有弹窗，"
                        "查看路径也不清楚，我实际很难注意到。"
                    ),
                }
            ],
        },
        persona={"persona_id": "P_WD"},
        model=model,  # type: ignore[arg-type]
        prompt_template="{persona_who}{persona_voice}\n{facts_block}\n{disclosed_fact_ids}",
        relevance_prompt="判断候选事实是否直接回答问题。",
        generation=GenerationConfig(temperature=0, top_p=1, max_tokens=10, seed=42),
        max_selection_attempts=2,
    )
    surface_question = "平台是否发送了续费提醒？请说明一项事实。"

    response, _ = simulator.respond(surface_question, 42)

    assert simulator.last_selected_fact_ids == ["F3"]
    assert simulator.last_response_kind == "new_hidden_fact"
    assert "2022年8月10日" in response.content
    assert len(model.calls) == 2
    assert all(surface_question in call[-1]["content"] for call in model.calls)
    assert simulator.history[-1][0] == surface_question


def test_communication_method_question_still_accepts_delivery_fact() -> None:
    assert deterministic_relevance_compatibility(
        "平台通过什么方式发送续费提醒？",
        "平台虽发过站内消息，但没有弹窗，查看路径也不清楚。",
    ) == (None, [])


def test_written_reply_reason_is_communication_content() -> None:
    assert deterministic_relevance_compatibility(
        "审批局前后两次书面答复分别用了什么理由？",
        "审批局先称规划核准不属于其业务，后又以不符合燃气规划为由拒绝许可。",
    ) == (True, [])


def test_attributed_statement_content_rejects_document_provenance() -> None:
    question = "公司具体是怎么说您已签字同意改领补助的？请提供相关细节。"
    document_origin = "这份不缴社保约定是公司事先打印好的，并不是我主动起草提出的条件。"
    client_effect_belief = "我本人在约定上签了字并领取补助，可能已经放弃要求公司参保的权利。"
    client_exit_belief = "因为我曾同意拿补助，我也许不能再要求公司支付经济补偿。"
    client_future_notice = "我准备在解除通知中明确写明未缴社会保险费。"
    substantive_statement = "公司当时解释说，签字领取补助就表示我自愿放弃要求公司参保。"

    for non_statement in (
        document_origin,
        client_effect_belief,
        client_exit_belief,
        client_future_notice,
    ):
        compatible, violations = deterministic_relevance_compatibility(question, non_statement)
        assert compatible is False
        assert (
            "requested_communication_content_missing" in violations
            or "requested_attributed_statement_subject_mismatch" in violations
        )
    assert deterministic_relevance_compatibility(question, substantive_statement) == (
        True,
        [],
    )


def test_agreement_provenance_is_not_mistaken_for_attributed_statement_request() -> None:
    assert deterministic_relevance_compatibility(
        "这份约定由谁提供，是公司预先打印还是由您起草？",
        "这份不缴社保约定是公司事先打印好的。",
    ) == (None, [])


def test_missing_notice_corrects_communication_content_presupposition() -> None:
    assert deterministic_relevance_compatibility(
        "银行发出的提前清偿通知具体写了哪些内容？",
        "银行没有向公司发出宣布贷款提前到期的通知。",
    ) == (True, [])


def test_formal_notice_existence_rejects_a_generic_demand_outcome() -> None:
    question = "银行是否已经向贵公司发出了要求提前清偿贷款的通知？"
    generic_demand = "公司一笔尚在展期内的贷款被银行要求提前清偿。"
    explicit_no_notice = "银行没有向公司发出宣布贷款提前到期的通知。"

    compatible, violations = deterministic_relevance_compatibility(question, generic_demand)
    assert compatible is False
    assert "requested_communication_existence_missing" in violations
    assert deterministic_relevance_compatibility(question, explicit_no_notice) == (
        True,
        [],
    )


def test_notice_type_modifier_is_not_mistaken_for_a_content_request() -> None:
    question = "银行是否发出了要求提前清偿贷款的通知？"
    assert "requested_communication_content_missing" not in direct_answer_attribute_violations(
        question,
        "银行没有发出宣布贷款提前到期的通知。",
    )
    compatible, violations = deterministic_relevance_compatibility(
        "该通知具体要求了什么？",
        "银行只通过电话联系，没有留下书面材料。",
    )
    assert compatible is False
    assert "requested_communication_content_missing" in violations


def test_client_specific_remedial_action_cannot_be_answered_by_indeterminate_others() -> None:
    compatible, violations = deterministic_relevance_compatibility(
        "您已采取了哪些具体行动来退缴所得资金？",
        "部分人员有自首、坦白、认罪认罚并主动退缴违法所得。",
    )
    assert compatible is False
    assert "requested_client_action_only_indeterminate_others" in violations
    assert deterministic_relevance_compatibility(
        "您已采取了哪些具体行动来退缴所得资金？",
        "我已主动退缴全部违法所得。",
    ) != (False, ["requested_client_action_only_indeterminate_others"])


@pytest.mark.parametrize(
    ("question", "belief", "violation"),
    [
        (
            "是谁实际指示您进行工作内容的？",
            "工作地点挂着数字公司的名牌，沟通工具也带有该公司字样。",
            "requested_directing_actor_identity_missing",
        ),
        (
            "对方具体招揽了哪些员工？",
            "对方通过高薪招募在职员工后获取技术资料。",
            "requested_recruited_person_identity_missing",
        ),
        (
            "变更登记申请是否已被市监局正式受理？",
            "市监局发过补正告知，补充材料仍被认为证据不足。",
            "requested_application_acceptance_missing",
        ),
    ],
)
def test_requested_attribute_must_be_present_in_related_candidate(
    question: str, belief: str, violation: str
) -> None:
    compatible, violations = deterministic_relevance_compatibility(question, belief)
    assert compatible is False
    assert violation in violations


def test_positive_message_existence_is_distinct_from_message_content() -> None:
    delivery_fact = "平台虽发过站内消息，但没有弹窗，查看路径也不清楚。"
    assert deterministic_relevance_compatibility("平台是否发过续费提醒消息？", delivery_fact) == (
        True,
        [],
    )
    compatible, violations = deterministic_relevance_compatibility(
        "平台发送的续费提醒具体包含哪些内容？", delivery_fact
    )
    assert compatible is False
    assert "requested_communication_content_missing" in violations


def test_selected_presupposed_notice_is_corrected_even_when_llm_rejects_it() -> None:
    simulator = ClientSimulator(
        case_view={
            "opening": "银行要求公司提前清偿贷款，理由涉及迟延和保证人风险。",
            "facts": [
                {
                    "fact_id": "F4",
                    "client_belief": "银行没有向公司发出宣布贷款提前到期的通知。",
                }
            ],
        },
        persona={"persona_id": "P_WD"},
        model=FactFourSelector(),  # type: ignore[arg-type]
        relevance_model=RejectingRelevanceVerifier(),  # type: ignore[arg-type]
        prompt_template="{persona_who}{persona_voice}\n{facts_block}\n{disclosed_fact_ids}",
        relevance_prompt="判断候选事实是否直接回答问题。",
        generation=GenerationConfig(temperature=0, top_p=1, max_tokens=10, seed=42),
        max_selection_attempts=2,
    )

    response, _ = simulator.respond("银行发出的提前清偿通知中具体提到了哪些理由？", 42)

    assert simulator.last_selected_fact_ids == ["F4"]
    assert simulator.last_response_kind == "new_hidden_fact"
    assert simulator.last_safe_fallback is False
    assert "没有向公司发出" in response.content
    assert simulator.last_relevance_attempts[-1]["answers_question"] is False
    assert simulator.last_relevance_attempts[-1]["deterministic_presupposition_correction"] is True


def test_unique_explicit_no_action_recovers_after_set_level_empty_decision() -> None:
    simulator = ClientSimulator(
        case_view={
            "opening": "孩子遭继父殴打。",
            "facts": [
                {
                    "fact_id": "F4",
                    "client_belief": "孩子母亲没有制止继父的殴打行为。",
                },
                {"fact_id": "F5", "client_belief": "孩子现在跟我生活。"},
            ],
        },
        persona={"persona_id": "P_WD"},
        model=EmptyFactSelector(),  # type: ignore[arg-type]
        prompt_template="{persona_who}{persona_voice}\n{facts_block}\n{disclosed_fact_ids}",
        relevance_prompt="判断候选事实是否直接回答问题。",
        generation=GenerationConfig(temperature=0, top_p=1, max_tokens=10, seed=42),
        max_selection_attempts=2,
    )

    response, _ = simulator.respond("孩子母亲采取了哪些制止措施？", 42)

    assert simulator.last_selected_fact_ids == ["F4"]
    assert simulator.last_response_kind == "new_hidden_fact"
    assert "没有制止" in response.content
    assert simulator.last_relevance_attempts[-1]["verification_trigger"] == (
        "deterministic_presupposition_recovery_after_empty"
    )


def test_unique_explicit_contract_term_recovers_after_set_level_empty_decision() -> None:
    simulator = ClientSimulator(
        case_view={
            "opening": "公司把社保费用改成补助。",
            "facts": [
                {
                    "fact_id": "F1",
                    "client_belief": "双方约定不缴社保而将相关费用作为补助发放。",
                },
                {"fact_id": "F2", "client_belief": "协议由公司预先打印。"},
            ],
        },
        persona={"persona_id": "P_WD"},
        model=EmptyFactSelector(),  # type: ignore[arg-type]
        prompt_template="{persona_who}{persona_voice}\n{facts_block}\n{disclosed_fact_ids}",
        relevance_prompt="判断候选事实是否直接回答问题。",
        generation=GenerationConfig(temperature=0, top_p=1, max_tokens=10, seed=42),
        max_selection_attempts=2,
    )

    response, _ = simulator.respond("补助协议具体约定了哪些内容？", 42)

    assert simulator.last_selected_fact_ids == ["F1"]
    assert "约定不缴社保" in response.content
    assert simulator.last_relevance_attempts[-1]["verification_trigger"] == (
        "deterministic_direct_answer_recovery_after_empty"
    )


def test_multiple_closed_contract_answers_recover_one_stable_fact_after_empty() -> None:
    simulator = ClientSimulator(
        case_view={
            "opening": "双方对质量标准是否约定存在争议。",
            "facts": [
                {
                    "fact_id": "F2",
                    "client_belief": "形式发票记载型号、数量和单价，但没有特定质量标准。",
                },
                {
                    "fact_id": "F3",
                    "client_belief": "后续数次交易也未书面约定产品质量标准。",
                },
            ],
        },
        persona={"persona_id": "P_WS"},
        model=EmptyFactSelector(),  # type: ignore[arg-type]
        prompt_template="{persona_who}{persona_voice}\n{facts_block}\n{disclosed_fact_ids}",
        relevance_prompt="判断候选事实是否直接回答问题。",
        generation=GenerationConfig(temperature=0, top_p=1, max_tokens=10, seed=42),
        max_selection_attempts=2,
    )

    response, _ = simulator.respond("合同中关于质量标准的具体约定内容是什么？", 42)

    assert simulator.last_selected_fact_ids == ["F2"]
    assert simulator.last_response_kind == "new_hidden_fact"
    assert "没有特定质量标准" in response.content
    assert simulator.last_relevance_attempts[-1]["verification_trigger"] == (
        "deterministic_direct_answer_recovery_after_empty"
    )


def test_start_year_directly_answers_start_date_for_same_mark() -> None:
    assert direct_answer_attribute_explicit_match(
        "您实际使用该标识的具体起始日期是什么时候？",
        "我们从2020年开始在中国销售以该标识命名的香水。",
    )
    assert not direct_answer_attribute_explicit_match(
        "您实际使用该标识的具体起始日期是什么时候？",
        "我们从2020年开始销售另一款无关产品。",
    )


def test_presupposition_correction_audit_field_crosses_strict_trajectory_schema() -> None:
    from legal_skill_guard.schemas.experiment import LegacyClientRelevanceAttempt

    attempt = LegacyClientRelevanceAttempt.model_validate(
        {
            "raw_output": '{"answers_question":false}',
            "verifier_model_id": "frozen-relevance-model",
            "selected_fact_id": "F4",
            "verification_trigger": "exhaustive_after_empty_cooperative_selection",
            "parse_valid": True,
            "answers_question": False,
            "deterministic_compatible": True,
            "deterministic_presupposition_correction": True,
            "deterministic_incremental_over_opening": True,
            "deterministic_compatibility_violations": [],
        }
    )

    assert attempt.deterministic_presupposition_correction is True
    assert attempt.model_dump()["deterministic_presupposition_correction"] is True


def test_question_quality_rejects_bare_noun_phrases() -> None:
    for content in ("医疗程序", "可观察事实的属性"):
        action = StructuredAction(
            action_type="ask",
            target_type="fact",
            target_id="target",
            content=content,
        )
        assert "generic_or_abstract_question" in action_question_quality_violations(action)


def test_client_simulator_uses_independent_relevance_verifier() -> None:
    simulator = ClientSimulator(
        case_view={"facts": [{"fact_id": "F3", "client_belief": "我收到了一份通知。"}]},
        persona={"persona_id": "P_WD"},
        model=FactThreeSelector(),  # type: ignore[arg-type]
        prompt_template="{persona_who}{persona_voice}\n{facts_block}\n{disclosed_fact_ids}",
        relevance_prompt="判断候选事实是否直接回答问题。",
        generation=GenerationConfig(temperature=0, top_p=1, max_tokens=10, seed=42),
        max_selection_attempts=2,
        relevance_model=RejectingRelevanceVerifier(),  # type: ignore[arg-type]
    )
    response, _ = simulator.respond("您收到了什么？", 42)
    assert simulator.last_selected_fact_ids == []
    assert simulator.last_safe_fallback is False
    assert "需要再核实" in response.content
    assert all(
        attempt["verifier_model_id"] == "independent-relevance-verifier"
        for attempt in simulator.last_relevance_attempts
    )


def test_client_simulator_exhausts_validly_rejected_candidates_without_fallback() -> None:
    selector = FirstRemainingFactSelector()
    simulator = ClientSimulator(
        case_view={
            "facts": [
                {"fact_id": "F1", "client_belief": "我在展会上见过对方。"},
                {"fact_id": "F2", "client_belief": "合同由同事保管。"},
                {"fact_id": "F3", "client_belief": "我收到过一封通知。"},
            ]
        },
        persona={"persona_id": "P_WD"},
        model=selector,  # type: ignore[arg-type]
        prompt_template="{persona_who}{persona_voice}\n{facts_block}\n{disclosed_fact_ids}",
        relevance_prompt="判断候选事实是否直接回答问题。",
        generation=GenerationConfig(temperature=0, top_p=1, max_tokens=10, seed=42),
        max_selection_attempts=2,
        relevance_model=RejectingRelevanceVerifier(),  # type: ignore[arg-type]
    )

    response, _ = simulator.respond("您如何将作品用于商业推广？", 42)

    assert simulator.last_selected_fact_ids == []
    assert simulator.last_safe_fallback is False
    assert simulator.last_relevance_passed is None
    assert [item["selected_fact_id"] for item in simulator.last_relevance_attempts] == [
        "F1",
        "F2",
        "F3",
    ]
    assert "F1" in selector.selection_prompts[0]
    assert "F1" not in selector.selection_prompts[1]
    assert "F2" not in selector.selection_prompts[2]
    assert "需要再核实" in response.content


def test_unique_deterministic_disclosed_match_recovers_after_empty_selection() -> None:
    simulator = ClientSimulator(
        case_view={
            "opening": "我们已经实际使用该标识。",
            "facts": [
                {
                    "fact_id": "F5",
                    "client_belief": "我们从2020年开始在中国销售以该标识命名的香水。",
                }
            ],
        },
        persona={"persona_id": "P_WD"},
        model=EmptyFactSelector(),  # type: ignore[arg-type]
        prompt_template="{persona_who}{persona_voice}\n{facts_block}\n{disclosed_fact_ids}",
        relevance_prompt="判断候选事实是否直接回答问题。",
        generation=GenerationConfig(temperature=0, top_p=1, max_tokens=10, seed=42),
        max_selection_attempts=2,
        relevance_model=ApprovingRelevanceVerifier(),  # type: ignore[arg-type]
    )
    simulator.disclosed_fact_ids.add("F5")

    response, _ = simulator.respond("实际使用该标识的地理范围是哪些地区？", 42)

    assert simulator.last_selected_fact_ids == ["F5"]
    assert simulator.last_response_kind == "repeated_hidden_fact"
    assert simulator.last_safe_fallback is False
    assert "刚才" in response.content
    assert simulator.last_relevance_attempts[-1]["verification_trigger"] == (
        "deterministic_direct_answer_recovery_after_empty"
    )


def test_client_simulator_rechecks_first_empty_new_fact_retrieval() -> None:
    selector = EmptyThenFactSelector()
    simulator = ClientSimulator(
        case_view={
            "opening": "存在房产争议。",
            "facts": [
                {
                    "fact_id": "F3",
                    "client_belief": "房屋在登记结婚次月改成夫妻两个人的名字。",
                }
            ],
        },
        persona={"persona_id": "P_WD"},
        model=selector,  # type: ignore[arg-type]
        prompt_template="{persona_who}{persona_voice}\n{facts_block}\n{disclosed_fact_ids}",
        relevance_prompt="判断候选事实是否直接回答问题。",
        generation=GenerationConfig(temperature=0, top_p=1, max_tokens=10, seed=42),
        max_selection_attempts=2,
        relevance_model=ApprovingRelevanceVerifier(),  # type: ignore[arg-type]
        retry_empty_selection=True,
    )

    response, _ = simulator.respond("你将名字加到房产证上的时间是什么时候？", 42)

    assert selector.calls == 2
    assert selector.selection_prompts[0] == selector.selection_prompts[1]
    assert simulator.last_selected_fact_ids == ["F3"]
    assert simulator.last_response_kind == "new_hidden_fact"
    assert "夫妻两个人的名字" in response.content


def test_client_simulator_repairs_malformed_opening_selection_without_relabeling_it() -> None:
    selector = MalformedThenEmptyOpeningSelector()
    simulator = ClientSimulator(
        case_view={
            "opening": "丈夫未经我同意把孩子带到外省。",
            "facts": [],
        },
        persona={"persona_id": "P_CS"},
        model=selector,  # type: ignore[arg-type]
        prompt_template="{persona_who}{persona_voice}\n{facts_block}\n{disclosed_fact_ids}",
        relevance_prompt="判断候选事实是否直接回答问题。",
        generation=GenerationConfig(temperature=0, top_p=1, max_tokens=10, seed=42),
        max_selection_attempts=2,
    )
    simulator.history.append(("您知道丈夫目前的位置吗？", "这个我不清楚。"))

    response, _ = simulator.respond("您是否知道丈夫的联系方式", 42)

    assert selector.calls == 2
    assert len(simulator.last_opening_selection_attempts) == 2
    assert simulator.last_opening_selection_attempts[0] == "不知道。"
    assert simulator.last_response_kind == "unavailable"
    assert simulator.last_safe_fallback is False
    assert "不清楚" in response.content
    assert "只执行候选事实编号选择" in selector.last_messages[-1]["content"]


def test_cooperative_persona_treats_two_empty_selections_as_final() -> None:
    simulator = ClientSimulator(
        case_view={
            "opening": "存在房产争议。",
            "facts": [
                {
                    "fact_id": "F3",
                    "client_belief": "房屋在登记结婚次月改成夫妻两个人的名字。",
                }
            ],
        },
        persona={"persona_id": "P_WD"},
        model=EmptyFactSelector(),  # type: ignore[arg-type]
        prompt_template="{persona_who}{persona_voice}\n{facts_block}\n{disclosed_fact_ids}",
        relevance_prompt="判断候选事实是否直接回答问题。",
        generation=GenerationConfig(temperature=0, top_p=1, max_tokens=10, seed=42),
        max_selection_attempts=2,
        relevance_model=ApprovingRelevanceVerifier(),  # type: ignore[arg-type]
    )

    response, _ = simulator.respond("你将名字加到房产证上的原因是什么？", 42)

    assert simulator.last_selected_fact_ids == []
    assert simulator.last_response_kind == "unavailable"
    assert "核实" in response.content
    assert simulator.last_relevance_attempts == []


def test_client_selector_repairs_truncated_recall_with_strict_json_mode() -> None:
    selector = EmptyThenTruncatedThenStrictEmptySelector()
    simulator = ClientSimulator(
        case_view={
            "opening": "",
            "facts": [
                {
                    "fact_id": "F1",
                    "client_belief": "建筑公司把工程转包给刘某。",
                }
            ],
        },
        persona={"persona_id": "P_CD"},
        model=selector,  # type: ignore[arg-type]
        prompt_template="{persona_who}{persona_voice}\n{facts_block}\n{disclosed_fact_ids}",
        relevance_prompt="判断候选事实是否直接回答问题。",
        generation=GenerationConfig(
            temperature=0,
            top_p=1,
            max_tokens=96,
            seed=42,
            disable_thinking=True,
        ),
        max_selection_attempts=2,
        recall_max_tokens=768,
        recall_disable_thinking=False,
        retry_empty_selection=True,
    )

    response, _ = simulator.respond("是否还有其他责任主体？", 42)

    assert simulator.last_safe_fallback is False
    assert simulator.last_response_kind == "unavailable"
    assert "不知道" in response.content
    assert len(selector.generations) == 3
    initial, recall, strict_repair = selector.generations
    assert initial.max_tokens == 96 and initial.disable_thinking is True
    assert recall.max_tokens == 768 and recall.disable_thinking is False
    assert strict_repair.max_tokens == 96 and strict_repair.disable_thinking is True


def test_empty_set_decision_is_not_overridden_by_per_fact_semantic_verdict() -> None:
    simulator = ClientSimulator(
        case_view={
            "opening": "公司贷款发生短暂迟延，目前正在争议是否提前到期。",
            "facts": [
                {
                    "fact_id": "F2",
                    "client_belief": "公司在两天后支付了当期利息，迟延已经纠正。",
                }
            ],
        },
        persona={"persona_id": "P_WD"},
        model=EmptyFactSelector(),  # type: ignore[arg-type]
        prompt_template="{persona_who}{persona_voice}\n{facts_block}\n{disclosed_fact_ids}",
        relevance_prompt="判断候选事实是否直接回答问题。",
        generation=GenerationConfig(temperature=0, top_p=1, max_tokens=10, seed=42),
        max_selection_attempts=2,
        relevance_model=ApprovingRelevanceVerifier(),  # type: ignore[arg-type]
    )

    response, _ = simulator.respond("公司为纠正迟延具体采取了什么行动？", 42)

    assert simulator.last_selected_fact_ids == []
    assert simulator.last_response_kind == "unavailable"
    assert "核实" in response.content
    assert simulator.last_relevance_attempts == []


def test_client_simulator_keeps_repeated_relevance_protocol_failure_as_fallback() -> None:
    simulator = ClientSimulator(
        case_view={"facts": [{"fact_id": "F3", "client_belief": "我收到过一封通知。"}]},
        persona={"persona_id": "P_WD"},
        model=FactThreeSelector(),  # type: ignore[arg-type]
        prompt_template="{persona_who}{persona_voice}\n{facts_block}\n{disclosed_fact_ids}",
        relevance_prompt="判断候选事实是否直接回答问题。",
        generation=GenerationConfig(temperature=0, top_p=1, max_tokens=10, seed=42),
        max_selection_attempts=2,
        relevance_model=InvalidRelevanceVerifier(),  # type: ignore[arg-type]
    )

    simulator.respond("您收到了什么？", 42)

    assert simulator.last_selected_fact_ids == []
    assert simulator.last_safe_fallback is True
    assert simulator.last_relevance_passed is False
    assert len(simulator.last_relevance_attempts) == 2
    assert all(not item["parse_valid"] for item in simulator.last_relevance_attempts)


def test_structured_relevance_repairs_only_a_malformed_thinking_completion() -> None:
    verifier = TruncatedThenStructuredRelevanceVerifier()
    simulator = ClientSimulator(
        case_view={
            "opening": "我收到过一份通知。",
            "facts": [
                {
                    "fact_id": "F3",
                    "client_belief": "我于2024年3月1日收到书面通知。",
                }
            ],
        },
        persona={"persona_id": "P_WD"},
        model=FactThreeSelector(),  # type: ignore[arg-type]
        prompt_template="{persona_who}{persona_voice}\n{facts_block}\n{disclosed_fact_ids}",
        relevance_prompt="判断候选事实是否直接回答问题。",
        generation=GenerationConfig(temperature=0, top_p=1, max_tokens=96, seed=42),
        max_selection_attempts=2,
        relevance_model=verifier,  # type: ignore[arg-type]
        relevance_generation=GenerationConfig(
            temperature=0,
            top_p=1,
            max_tokens=1200,
            seed=42,
            disable_thinking=False,
            response_schema=CLIENT_RELEVANCE_ANALYSIS_SCHEMA,
            response_schema_name="client_proposition_entailment",
        ),
    )

    response, _ = simulator.respond("您是在什么时间收到书面通知的？", 42)

    assert simulator.last_safe_fallback is False
    assert simulator.last_relevance_passed is True
    assert simulator.last_selected_fact_ids == ["F3"]
    assert "2024年3月1日" in response.content
    assert [item["parse_valid"] for item in simulator.last_relevance_attempts] == [
        False,
        True,
    ]
    assert len(verifier.generations) == 2
    assert verifier.generations[0].disable_thinking is False
    assert verifier.generations[1].disable_thinking is True
    assert verifier.messages[0] == verifier.messages[1]


def test_structured_relevance_requires_predicate_and_attribute_alignment() -> None:
    value = {
        "question_actor": "客户",
        "question_predicate": "是否告知病史",
        "question_attribute": "告知行为",
        "candidate_actor": "客户",
        "candidate_predicate": "患有慢性支气管炎",
        "candidate_attribute": "既往病史",
        "candidate_assertion_source": "direct_client_fact",
        "same_actor": True,
        "same_predicate": False,
        "same_attribute": True,
        "answers_question": True,
    }
    analysis = parse_relevance_analysis(json.dumps(value, ensure_ascii=False))
    assert analysis is not None
    assert structured_proposition_alignment_passed(analysis) is False
    aligned = dict(value)
    aligned["same_predicate"] = True
    assert structured_proposition_alignment_passed(aligned) is True


def test_explicit_polar_subattribute_recovers_only_a_literal_compound_answer() -> None:
    question = "站内消息是否设置弹窗、查看路径是否清楚？"
    direct_answer = (
        "平台在2022年8月10日发过站内消息，但没有弹窗，查看路径也不清楚，我实际很难注意到。"
    )
    unrelated_topic = "平台在2022年8月10日发过站内消息。"
    external_claim = "保险公司的拒赔理由是我投保时没有告知慢性支气管炎。"

    assert direct_answer_attribute_explicit_match(question, direct_answer) is True
    assert direct_answer_attribute_explicit_match(question, unrelated_topic) is False
    assert (
        direct_answer_attribute_explicit_match(
            "您在投保时是否明确告知了健康告知书中的所有问题？",
            external_claim,
        )
        is False
    )


def test_client_simulator_restates_public_opening_instead_of_claiming_unknown() -> None:
    opening = "孩子长期使用郑某文学习和参赛。孩子明确希望继续使用这个名字。"
    assert opening_fact_candidates(opening) == [
        {"fact_id": "O1", "client_belief": "孩子长期使用郑某文学习和参赛", "source": "opening"},
        {"fact_id": "O2", "client_belief": "孩子明确希望继续使用这个名字", "source": "opening"},
    ]
    simulator = ClientSimulator(
        case_view={"opening": opening, "facts": []},
        persona={"persona_id": "P_WD"},
        model=OpeningSelector(),  # type: ignore[arg-type]
        prompt_template="{persona_who}{persona_voice}\n{facts_block}\n{disclosed_fact_ids}",
        relevance_prompt="判断候选事实是否直接回答问题。",
        generation=GenerationConfig(temperature=0, top_p=1, max_tokens=10, seed=42),
        max_selection_attempts=2,
    )
    response, _ = simulator.respond("孩子现在使用什么名字？", 42)
    assert simulator.last_selected_fact_ids == []
    assert simulator.last_opening_reference_ids == ["O1"]
    assert simulator.last_response_kind == "opening_repeat"
    assert simulator.last_relevance_passed is True
    assert "孩子长期使用郑某文" in response.content
    assert "不知道" not in response.content


def test_client_simulator_prefers_new_hidden_answer_over_public_opening() -> None:
    simulator = ClientSimulator(
        case_view={
            "opening": "合同到期后公司仍让我继续上班。",
            "facts": [
                {
                    "fact_id": "F1",
                    "client_belief": "合同到期后公司继续按月发工资并缴纳社保。",
                }
            ],
        },
        persona={"persona_id": "P_WD"},
        model=HiddenBeforeOpeningSelector(),  # type: ignore[arg-type]
        prompt_template="{persona_who}{persona_voice}\n{facts_block}\n{disclosed_fact_ids}",
        relevance_prompt="判断候选事实是否直接回答问题。",
        generation=GenerationConfig(temperature=0, top_p=1, max_tokens=10, seed=42),
        max_selection_attempts=2,
    )

    response, _ = simulator.respond("合同到期后工资和社保怎样处理？", 42)

    assert simulator.last_response_kind == "new_hidden_fact"
    assert simulator.last_selected_fact_ids == ["F1"]
    assert simulator.last_opening_reference_ids == []
    assert "继续按月发工资" in response.content


def test_hidden_fact_fully_stated_in_opening_cannot_be_counted_as_new() -> None:
    opening = "我在五月收到书面解除通知。"
    belief = "我在五月收到书面解除通知。"
    assert hidden_fact_adds_information(opening, belief) is False
    assert hidden_fact_adds_information(opening, belief + "通知没有写理由。") is None
    simulator = ClientSimulator(
        case_view={
            "opening": opening,
            "facts": [{"fact_id": "F1", "client_belief": belief}],
        },
        persona={"persona_id": "P_WD"},
        model=HiddenBeforeOpeningSelector(),  # type: ignore[arg-type]
        prompt_template="{persona_who}{persona_voice}\n{facts_block}\n{disclosed_fact_ids}",
        relevance_prompt="判断候选事实是否直接回答问题。",
        generation=GenerationConfig(temperature=0, top_p=1, max_tokens=10, seed=42),
        max_selection_attempts=2,
    )

    simulator.respond("你在什么时候收到书面解除通知？", 42)

    assert simulator.last_response_kind == "opening_repeat"
    assert simulator.last_selected_fact_ids == []
    assert simulator.last_opening_reference_ids == ["O1"]
    assert simulator.last_relevance_attempts[0]["deterministic_incremental_over_opening"] is False


def test_unconfirmed_target_paraphrase_remains_scoreable_without_surface_rewrite() -> None:
    manager = StateManager()
    state = manager.initial("alignment", "我与原公司发生劳动争议。", max_turns=6)
    state.facts.append(
        FactSlot(
            fact_id="financial_responsibility",
            label="客户实际支付给原公司的费用金额",
            status="unknown",
        )
    )
    envelope = PolicyEnvelope(
        action=StructuredAction(
            action_type="ask",
            target_type="fact",
            target_id="financial_responsibility",
            reason="核实费用承担",
            expected_information="客户实际支付给原公司的费用金额",
            content="您是否已经申请劳动仲裁？",
        )
    )

    assert action_target_alignment_violations(
        envelope.action, "客户实际支付给原公司的费用金额"
    ) == []
    normalized, changes = normalize_policy_envelope(envelope, state)
    assert changes == []
    assert normalized.action.content == envelope.action.content
    assert action_target_alignment_violations(
        normalized.action, "客户实际支付给原公司的费用金额"
    ) == []


def test_target_alignment_accepts_ordinary_witness_paraphrase() -> None:
    action = StructuredAction(
        action_type="ask",
        target_type="fact",
        target_id="third_party_witnesses",
        content="是否有其他人知道你遭受辱骂和贬损的情况？",
    )

    assert action_target_alignment_violations(action, "是否有第三方目击者或知情人") == []

    unrelated = action.model_copy(update={"content": "您是否向公安机关提交过书面材料？"})
    assert action_target_alignment_violations(unrelated, "是否有第三方目击者或知情人") == []


def test_target_alignment_accepts_order_inverted_natural_chinese_paraphrases() -> None:
    pairs = (
        (
            "孩子当前实际居住地和监护人信息",
            "孩子现在具体住在什么地方，是由谁在照顾他？",
            "孩子被带离原住所的具体时间",
        ),
        (
            "购买犬只的具体时间",
            "您是在什么时候从宠物公司购买这只犬的？",
            "是否已向宠物公司提出退货请求及对方回应",
        ),
    )
    for index, (label, content, distractor) in enumerate(pairs):
        action = StructuredAction(
            action_type="ask",
            target_type="fact",
            target_id="visible_target",
            expected_information=label,
            content=content,
        )
        assert action_target_alignment_violations(action, label) == []
        state = StateManager().initial(f"natural-alignment-{index}", "发生争议。", max_turns=6)
        state.facts.extend(
            [
                FactSlot(fact_id="visible_target", label=label, status="unknown"),
                FactSlot(fact_id="distractor", label=distractor, status="unknown"),
            ]
        )
        assert "question_target_misaligned" not in policy_health_violations(
            PolicyEnvelope(action=action), state
        )


def test_target_alignment_accepts_effect_magnitude_as_observable_change() -> None:
    state = StateManager().initial(
        "effect-magnitude-alignment",
        "公司在怀孕期间调整了我的岗位和待遇。",
        max_turns=6,
    )
    state.facts.extend(
        [
            FactSlot(
                fact_id="treatment_impact",
                label="待遇变更对实际收入的影响程度",
                status="unknown",
            ),
            FactSlot(
                fact_id="position_details",
                label="调岗后的工作岗位和收入构成",
                status="unknown",
            ),
        ]
    )

    for content in (
        "调岗后你的收入构成具体发生了哪些变化？",
        "调岗后你的实际收入相比之前发生了哪些具体变化？",
    ):
        action = StructuredAction(
            action_type="ask",
            target_type="fact",
            target_id="treatment_impact",
            expected_information="待遇变更对实际收入的影响程度",
            content=content,
        )
        assert "question_target_misaligned" not in policy_health_violations(
            PolicyEnvelope(action=action), state
        )


def test_target_alignment_still_rejects_a_different_changed_attribute() -> None:
    state = StateManager().initial(
        "effect-magnitude-negative-alignment",
        "公司在怀孕期间调整了我的岗位和待遇。",
        max_turns=6,
    )
    state.facts.extend(
        [
            FactSlot(
                fact_id="treatment_impact",
                label="待遇变更对实际收入的影响程度",
                status="unknown",
            ),
            FactSlot(
                fact_id="position_name_change",
                label="调岗后的岗位名称变化",
                status="unknown",
            ),
        ]
    )
    action = StructuredAction(
        action_type="ask",
        target_type="fact",
        target_id="treatment_impact",
        expected_information="待遇变更对实际收入的影响程度",
        content="调岗后你的岗位名称发生了哪些变化？",
    )

    assert "question_target_misaligned" in policy_health_violations(
        PolicyEnvelope(action=action), state
    )


def test_selected_open_id_cannot_launder_an_unavailable_competing_target() -> None:
    state = StateManager().initial(
        "target-id-laundering",
        "客户称接受医美项目后怀疑机构资质。",
        max_turns=6,
    )
    state.facts.extend(
        [
            FactSlot(
                fact_id="qualification_reason",
                label="怀疑机构资质的具体原因",
                status="unknown",
            ),
            FactSlot(
                fact_id="treatment_time",
                label="接受医美项目的发生时间",
                status="not_available",
            ),
        ]
    )
    state.asked_targets.append("treatment_time")
    envelope = PolicyEnvelope(
        action=StructuredAction(
            action_type="ask",
            target_type="fact",
            target_id="qualification_reason",
            expected_information="接受医美项目的发生时间",
            content="您接受这次医美项目的具体时间是什么时候？",
        )
    )

    violations = policy_health_violations(envelope, state)

    assert "question_target_misaligned" in violations
    assert "question_target_misaligned" in blocking_policy_health_violations(violations)


def test_target_alignment_rejects_unbound_coordinated_institutional_actors() -> None:
    action = StructuredAction(
        action_type="ask",
        target_type="fact",
        target_id="decision_status",
        content="招标方和财政部门是否已经作出了最终处理决定？",
    )

    assert action_target_alignment_violations(action, "最终处理决定是否实际作出") == [
        "question_target_unbound_coordinated_actors:招标方+财政部门"
    ]
    assert (
        action_target_alignment_violations(action, "招标方和财政部门是否已经作出最终处理决定") == []
    )


def test_target_alignment_distinguishes_intervention_from_client_contact_attempt() -> None:
    label = "是否有第三方机构介入（如学校、医疗机构）"
    contact_attempt = StructuredAction(
        action_type="ask",
        target_type="fact",
        target_id="third_party_involvement",
        content="您是否曾尝试联系学校或医疗机构协助解决问题？",
    )
    actual_intervention = contact_attempt.model_copy(
        update={"content": "是否有学校、医疗机构或其他第三方实际介入此事？"}
    )

    assert action_target_alignment_violations(contact_attempt, label) == [
        "question_target_misaligned"
    ]
    assert action_target_alignment_violations(actual_intervention, label) == []


def test_target_alignment_stage_error_is_left_for_policy_repair() -> None:
    manager = StateManager()
    state = manager.initial("stage-alignment", "孩子近期被发现受伤。", max_turns=6)
    label = "母亲在儿子受伤事件中实际采取了哪些制止、保护、求助或送医等处置行为"
    state.facts.append(
        FactSlot(
            fact_id="caregiver_incident_response",
            label=label,
            status="unknown",
        )
    )
    envelope = PolicyEnvelope(
        action=StructuredAction(
            action_type="ask",
            target_type="fact",
            target_id="caregiver_incident_response",
            expected_information=label,
            content="母亲在发现孩子受伤后采取了哪些具体保护措施？",
        )
    )

    assert action_target_alignment_violations(envelope.action, label) == [
        "question_target_misaligned"
    ]
    normalized, changes = normalize_policy_envelope(envelope, state)
    assert changes == []
    assert normalized.action.content == envelope.action.content


def test_runtime_target_id_is_derived_from_visible_label_not_misleading_model_key() -> None:
    state = StateManager().initial("runtime-target", "我与原公司发生劳动争议。", max_turns=6)
    envelope = PolicyEnvelope(
        state_patch=StatePatch(
            observations=[
                FactObservation(
                    fact_id="financial_responsibility",
                    label="客户是否已经申请劳动仲裁",
                    status="unknown",
                )
            ]
        ),
        action=StructuredAction(
            action_type="ask",
            target_type="fact",
            target_id="financial_responsibility",
            reason="核实已经发生的程序",
            expected_information="客户是否已经申请劳动仲裁",
            content="您是否已经申请劳动仲裁？",
        ),
    )

    normalized, changes = normalize_policy_envelope(envelope, state)

    assert normalized.action.target_id is not None
    assert normalized.action.target_id.startswith("dialogue_fact_")
    assert normalized.state_patch.observations[0].fact_id == normalized.action.target_id
    assert changes == [
        "canonicalize_runtime_target:financial_responsibility->" + normalized.action.target_id
    ]


def test_relationship_context_guard_rejects_different_caregiver_stage() -> None:
    question = "孩子与继父共同生活期间的具体生活状况是怎样的？"
    later_fact = "孩子被接回后在我这里生活愉快，也已经适应新的学校。"
    assert relationship_context_roles(question) == {"stepfather"}
    assert relationship_context_roles(later_fact) == {"client"}
    assert deterministic_relevance_compatibility(question, later_fact) == (
        False,
        ["relationship_context_mismatch"],
    )
    assert deterministic_relevance_compatibility(
        "孩子目前与您共同生活的状况怎样？", later_fact
    ) == (True, [])


def test_relationship_context_guard_preserves_matching_and_ambiguous_roles() -> None:
    assert deterministic_relevance_compatibility(
        "次子随母亲生活时由谁日常照料？",
        "离婚时约定次子随母亲生活。",
    ) == (True, [])
    assert deterministic_relevance_compatibility(
        "孩子跟对方生活时的就学情况怎样？",
        "孩子后来跟母亲生活并转入附近学校。",
    ) == (None, [])


def test_transition_stage_guard_compares_only_the_same_named_transition() -> None:
    assert (
        transition_stage_compatible("签约前发生了哪些交易？", "这些交易都发生在签约后。") is False
    )
    assert deterministic_relevance_compatibility(
        "签约前发生了哪些交易？", "这些交易都发生在签约后。"
    ) == (False, ["transition_stage_mismatch"])
    assert transition_stage_compatible("签约前发生了哪些交易？", "离职后我才发现相关记录。") is None

    assert (
        transition_stage_compatible(
            "离婚后是否就抚养权变更重新协商过？",
            "2022年离婚时约定长子随父亲生活、次子随母亲生活。",
        )
        is False
    )
    assert deterministic_relevance_compatibility(
        "离婚后是否就抚养权变更重新协商过？",
        "2022年离婚时约定长子随父亲生活、次子随母亲生活。",
    ) == (False, ["transition_stage_mismatch"])
    assert (
        transition_stage_compatible(
            "离婚后是否就抚养权变更重新协商过？",
            "离婚后双方重新协商，将次子改由父亲直接抚养。",
        )
        is not False
    )
    assert (
        transition_stage_compatible(
            "离婚时对子女抚养作了什么原始约定？",
            "2022年离婚时约定长子随父亲生活、次子随母亲生活。",
        )
        is not False
    )


def test_policy_health_rejects_empty_nonterminal_action() -> None:
    state = StateManager().initial("empty-question", "开场", max_turns=6)
    state.facts.append(FactSlot(fact_id="agreement", label="双方约定", status="unknown"))
    envelope = PolicyEnvelope(
        action=StructuredAction(
            action_type="summarize",
            target_type="fact",
            target_id="agreement",
            content="",
        )
    )
    violations = policy_health_violations(envelope, state)
    assert "nonterminal_action_missing_content" in violations
    assert blocking_policy_health_violations(violations) == [
        "nonterminal_action_missing_content"
    ]
    assert executable_fallback_can_repair("nonterminal_action_missing_content")


def test_grounded_client_renderer_uses_only_pinned_belief() -> None:
    belief = "我只收到过一份书面通知。"
    rendered = render_grounded_client_response(belief, "P_WD")
    assert rendered == "按我的理解，" + belief
    assert "已经提交" not in rendered


def test_trajectory_audit_treats_client_response_violations_as_hard(
    tmp_path: Path,
) -> None:
    trajectory = {
        "opening": "开场",
        "memo": (
            "案情概要\n初步咨询。\n关键事实\n客户称有一项事实。\n法律问题\n"
            "仍需核实。\n风险评估\n目前不能确认结论。\n下一步建议\n先整理材料。"
            "本分析不替代持证律师的正式意见。"
        ),
        "steps": [
            {
                "turn": 1,
                "policy_attempts": [],
                "policy_health_violations": [],
                "action_decision": {
                    "changes": [],
                    "activated_skill_ids": [],
                    "final": {"action_type": "ask"},
                },
                "state_patch": {"observations": []},
                "rendered_question": None,
                "client_response": "event_time是9月2日。",
                "verifier_results": [],
            }
        ],
    }
    path = tmp_path / "trajectory.json"
    path.write_text(json.dumps(trajectory, ensure_ascii=False), encoding="utf-8")
    result = audit([path])
    assert result["healthy"] is False
    assert result["hard_failures"] == {
        "client_slot_label:event_time": 1,
        "snake_case_client_responses": 1,
    }


def test_trajectory_audit_checks_selected_belief_grounding(tmp_path: Path) -> None:
    from scripts import audit_trajectory_health as health

    health.CLIENT_BELIEFS["grounding_case"] = ["合同约定付款日期为3月1日。"]
    trajectory = {
        "case_id": "grounding_case",
        "opening": "合同咨询",
        "memo": (
            "案情概要\n初步咨询。\n关键事实\n客户称有一项事实。\n法律问题\n"
            "仍需核实。\n风险评估\n目前不能确认结论。\n下一步建议\n先整理材料。"
            "本分析不替代持证律师的正式意见。"
        ),
        "steps": [
            {
                "turn": 1,
                "policy_attempts": [],
                "policy_health_violations": [],
                "action_decision": {"changes": [], "activated_skill_ids": []},
                "state_patch": {"observations": []},
                "rendered_question": "何时付款？",
                "client_response": "我已经把合同作为证据提交了。",
                "client_selected_fact_ids": ["F1"],
                "client_route_decision_valid": True,
                "client_selection_attempts": [{"raw_output": '{"fact_ids":["F1"]}'}],
                "verifier_results": [],
            }
        ],
    }
    path = tmp_path / "grounding.json"
    path.write_text(json.dumps(trajectory, ensure_ascii=False), encoding="utf-8")
    result = audit([path])
    assert result["hard_failures"] == {"client_response_not_grounded_in_selected_belief": 1}


def test_trajectory_audit_protocol12_keeps_opening_repeat_out_of_disclosures(
    tmp_path: Path,
) -> None:
    trajectory = {
        "schema_version": 13,
        "case_id": "opening_repeat_case",
        "opening": "我已经签了合同。",
        "memo": (
            "案情概要\n初步咨询。\n关键事实\n客户称已经签了合同。\n法律问题\n"
            "仍需核实。\n风险评估\n目前不能确认结论。\n下一步建议\n先整理材料。"
            "本分析不替代持证律师的正式意见。"
        ),
        "steps": [
            {
                "turn": 1,
                "policy_attempts": [],
                "policy_health_violations": [],
                "action_decision": {"changes": [], "activated_skill_ids": []},
                "state_patch": {"observations": []},
                "rendered_question": "您已经签了合同吗？",
                "client_response": (
                    "开场时我已经说明过：我已经签了合同；目前没有更多可确认的信息。"
                ),
                "client_response_kind": "opening_repeat",
                "client_opening_reference_ids": ["O1"],
                "client_selected_fact_ids": [],
                "client_route_decision_valid": True,
                "client_selection_attempts": [],
                "client_safe_fallback": False,
                "verifier_results": [],
            }
        ],
    }
    path = tmp_path / "opening_repeat.json"
    path.write_text(json.dumps(trajectory, ensure_ascii=False), encoding="utf-8")

    result = audit([path])

    assert result["healthy"] is True
    assert result["metrics"]["client_semantic_repetition_no_new_information"] == 1


def _withheld_audit_trajectory() -> dict[str, object]:
    return {
        "schema_version": 15,
        "case_id": "withheld_case",
        "opening": "我想咨询一份合同。",
        "memo": (
            "案情概要\n客户希望咨询一份合同。\n关键事实\n合同签署日期仍待确认。\n"
            "法律问题\n需结合履行期限进一步分析。\n风险评估\n当前信息不足，不能作确定判断。\n"
            "下一步建议\n在客户愿意时再确认签署日期。"
            "本分析不替代持证律师的正式意见。"
        ),
        "steps": [
            {
                "turn": 1,
                "policy_attempts": [],
                "policy_health_violations": [],
                "action_decision": {
                    "changes": [],
                    "activated_skill_ids": [],
                    "final": {
                        "action_type": "ask",
                        "target_type": "fact",
                        "target_id": "I1",
                        "reason": "确认履行时间",
                    },
                },
                "state_patch": {"observations": []},
                "rendered_question": "为判断履行期限，您现在愿意说明合同签署日期吗？",
                "client_response": "这个问题我现在还不想细说。",
                "client_response_kind": "withheld",
                "client_opening_reference_ids": [],
                "client_selected_fact_ids": [],
                "client_route_decision_valid": True,
                "client_selection_attempts": [],
                "client_safe_fallback": False,
                "state_after": {
                    "facts": [{"fact_id": "I1", "status": "unknown"}],
                    "asked_targets": [],
                    "interactions": [
                        {
                            "turn": 1,
                            "target_id": "I1",
                            "response_kind": "withheld",
                            "new_information": False,
                            "disclosed_fact_ids": [],
                        }
                    ],
                },
                "verifier_results": [],
            }
        ],
    }


def test_trajectory_audit_accepts_consistent_withheld_provenance(tmp_path: Path) -> None:
    path = tmp_path / "withheld.json"
    path.write_text(
        json.dumps(_withheld_audit_trajectory(), ensure_ascii=False),
        encoding="utf-8",
    )

    result = audit([path])

    assert result["healthy"] is True
    assert not any("withheld" in key for key in result["hard_failures"])


def test_trajectory_audit_rejects_withheld_that_closes_or_discloses_target(
    tmp_path: Path,
) -> None:
    trajectory = _withheld_audit_trajectory()
    step = trajectory["steps"][0]  # type: ignore[index]
    step["client_selected_fact_ids"] = ["F1"]  # type: ignore[index]
    step["client_route_decision_valid"] = False  # type: ignore[index]
    state_after = step["state_after"]  # type: ignore[index]
    state_after["facts"][0]["status"] = "not_available"  # type: ignore[index]
    state_after["asked_targets"] = ["I1"]  # type: ignore[index]
    state_after["interactions"][0]["new_information"] = True  # type: ignore[index]
    state_after["interactions"][0]["disclosed_fact_ids"] = ["F1"]  # type: ignore[index]
    path = tmp_path / "withheld_invalid.json"
    path.write_text(json.dumps(trajectory, ensure_ascii=False), encoding="utf-8")

    result = audit([path])

    assert result["healthy"] is False
    assert {
        "client_response_provenance_mismatch",
        "client_selected_fact_without_valid_route",
        "client_withheld_target_state_changed",
        "client_withheld_target_marked_asked",
        "client_withheld_interaction_provenance_mismatch",
    }.issubset(result["hard_failures"])


def test_replay_cache_returns_exact_response_without_second_generation(
    tmp_path: Path,
) -> None:
    delegate = CountingClient()
    client = ReplayCachedChatClient(delegate, tmp_path / "cache")  # type: ignore[arg-type]
    generation = GenerationConfig(0.7, 0.9, 64, 42)
    messages = [{"role": "user", "content": "同一输入"}]
    first = client.generate(messages, generation)
    second = client.generate(messages, generation)
    assert first == second
    assert delegate.calls == 1
    assert (client.hits, client.misses) == (1, 1)
    cache_path = next((tmp_path / "cache").glob("*.json"))
    cached = json.loads(cache_path.read_text(encoding="utf-8"))
    cached["response"]["content"] = "tampered"
    cache_path.write_text(json.dumps(cached), encoding="utf-8")
    with pytest.raises(RuntimeError, match="Replay cache hash mismatch"):
        client.generate(messages, generation)


def test_stop_gate_allows_sufficient_final_at_configured_horizon() -> None:
    state = StateManager().initial("budget", "开场", max_turns=6)
    state.turn = 6
    state.facts.append(
        FactSlot(
            fact_id="critical",
            label="关键事实",
            status="corroborated",
            value="已核实",
            criticality="high",
        )
    )
    assert StopGate().evaluate(state, StructuredAction(action_type="final")) == (
        "PASS",
        "sufficient_visible_state",
    )


def test_stop_gate_preserves_abstention_when_substantive_claim_exists() -> None:
    state = StateManager().initial("early", "开场", max_turns=6)
    state.turn = 1
    state.facts.append(
        FactSlot(
            fact_id="dispute_action",
            label="对方具体行为",
            status="client_claimed",
            value="拒绝履行",
            criticality="high",
        )
    )
    assert StopGate().evaluate(state, StructuredAction(action_type="abstain")) == (
        "PASS",
        "explicit_abstention",
    )


def test_stop_gate_allows_abstention_after_no_information_interaction() -> None:
    manager = StateManager()
    state = manager.initial("no-information", "开场", max_turns=6)
    state = manager.mark_interaction(
        state,
        turn=1,
        action_type="ask",
        target_id=None,
        question="是否还有可确认的实质事实？",
    )
    assert StopGate().evaluate(state, StructuredAction(action_type="abstain")) == (
        "PASS",
        "explicit_abstention",
    )


def test_stop_gate_allows_client_claimed_fact_with_conditional_memo() -> None:
    state = StateManager().initial("client-claimed", "开场", max_turns=6)
    state.facts.append(
        FactSlot(
            fact_id="payment",
            label="客户所述付款",
            status="client_claimed",
            value="客户称已经付款",
            criticality="high",
        )
    )
    assert StopGate().evaluate(state, StructuredAction(action_type="final")) == (
        "PASS",
        "sufficient_visible_state",
    )


def test_policy_rejects_epistemically_inconsistent_terminal_reason_without_fixed_turns() -> None:
    state = StateManager().initial("terminal-consistency", "客户已说明争议背景。", max_turns=24)
    state.facts.append(
        FactSlot(
            fact_id="injury_circumstances",
            label="受伤的具体经过",
            status="unknown",
            criticality="high",
        )
    )
    blanket = PolicyEnvelope(
        action=StructuredAction(
            action_type="final",
            target_type="session",
            reason="剩余目标价值较低，客户大概率无法回答，答案不会实质改变分析。",
        )
    )
    assert "terminal_unsupported_blanket_low_value_claim" in policy_health_violations(
        blanket, state
    )

    contradictory = PolicyEnvelope(
        action=StructuredAction(
            action_type="final",
            target_type="session",
            reason="受伤的具体经过尚待进一步核实，并将直接影响责任分析。",
        )
    )
    assert "terminal_reason_admits_material_unresolved_target" in policy_health_violations(
        contradictory, state
    )

    grounded_conditional = PolicyEnvelope(
        action=StructuredAction(
            action_type="final",
            target_type="session",
            reason="受伤的精确日期仅留作病历核对，现有先后顺序已足以形成条件性分析。",
        )
    )
    assert not any(
        item.startswith("terminal_")
        for item in policy_health_violations(grounded_conditional, state)
    )

    disclosed_act_conditional = PolicyEnvelope(
        action=StructuredAction(
            action_type="final",
            target_type="session",
            reason=(
                "基于现有披露信息，可形成条件性初步分析：签署协议并领取补助"
                "可能影响社会保险权益，外部缴费记录留作后续材料分析。"
            ),
        )
    )
    assert not any(
        item.startswith("terminal_")
        for item in policy_health_violations(disclosed_act_conditional, state)
    )

    explicitly_direct_gap = PolicyEnvelope(
        action=StructuredAction(
            action_type="final",
            target_type="session",
            reason="尚未取得的事故经过可能直接影响责任分析。",
        )
    )
    assert "terminal_reason_admits_material_unresolved_target" in policy_health_violations(
        explicitly_direct_gap, state
    )

    for reason in (
        "当前信息不足以形成条件性初步分析，仍需进一步获取关键事实。",
        "剩余目标具有较高信息价值，建议继续调查。",
        "现有事实不足以支持明确判断，尚待补充客户可回答的事实。",
    ):
        envelope = PolicyEnvelope(
            action=StructuredAction(
                action_type="final",
                target_type="session",
                reason=reason,
            )
        )
        assert "terminal_reason_admits_material_unresolved_target" in (
            policy_health_violations(envelope, state)
        )


def test_terminal_reason_repair_continues_with_unasked_grounded_target() -> None:
    state = StateManager().initial("terminal-repair-continue", "客户已说明争议背景。", max_turns=24)
    state.facts.append(
        FactSlot(
            fact_id="injury_circumstances",
            label="受伤的具体经过",
            status="unknown",
            criticality="high",
        )
    )

    instruction = policy_repair_instruction(
        ["terminal_reason_admits_material_unresolved_target"], state
    )

    assert "当前可直接选择的未问目标：injury_circumstances（受伤的具体经过）" in instruction
    assert "本轮不得继续改写final理由" in instruction
    assert "继续询问" in instruction
    assert "必须保持final" not in instruction


def test_multiple_question_repair_requires_one_narrow_interrogative() -> None:
    state = StateManager().initial("atomic-question-repair", "客户已说明争议背景。", max_turns=24)
    state.facts.append(
        FactSlot(
            fact_id="compensation_documents",
            label="已提交的退赔凭证",
            status="unknown",
            criticality="high",
        )
    )

    instruction = policy_repair_instruction(["multiple_primary_questions"], state)

    assert "保持原action.target_id" in instruction
    assert "恰好一个疑问句且全文最多一个问号" in instruction
    assert "只询问其中信息价值最高的一个可观察属性" in instruction
    assert "您提交的退赔凭证具体是什么" in instruction


def test_target_alignment_repair_preserves_actor_event_and_stage() -> None:
    state = StateManager().initial("alignment-repair", "客户已说明争议背景。", max_turns=24)
    state.facts.append(
        FactSlot(
            fact_id="third_party_involvement",
            label="是否有第三方机构实际介入",
            status="unknown",
            criticality="high",
        )
    )

    instruction = policy_repair_instruction(["question_target_misaligned"], state)

    assert "保持原action.target_id" in instruction
    assert "事实主语、实际行为或状态、对象和事件阶段" in instruction
    assert "不得把第三方是否实际介入替换成客户是否尝试联系第三方" in instruction
    assert "不得加入目标标签没有绑定的并列行为主体" in instruction
    assert "expected_information必须直接沿用" in instruction
    assert "content也必须以该label原文为事实核心" in instruction

    actor_instruction = policy_repair_instruction(
        ["question_target_unbound_coordinated_actors:招标方+财政部门"], state
    )
    assert "未绑定并列主体是：招标方+财政部门" in actor_instruction
    assert "必须从content、expected_information和reason中删除" in actor_instruction


def test_question_repair_does_not_force_a_new_target_after_agenda_exhaustion() -> None:
    manager = StateManager()
    state = manager.initial("repair-exhausted", "客户已说明争议背景。", max_turns=24)
    state.facts.append(
        FactSlot(
            fact_id="payment_details",
            label="客户实际付款情况",
            status="unknown",
            criticality="high",
        )
    )
    state = manager.mark_interaction(
        state,
        turn=1,
        action_type="ask",
        target_id="payment_details",
        question="客户实际付款情况是什么？",
        target_not_available=True,
        client_response="目前不知道。",
        response_kind="unavailable",
    )

    instruction = policy_repair_instruction(
        [
            "ask_target_not_unresolved:payment_details:not_available",
            "repeated_fact_target:payment_details",
            "question_target_misaligned",
        ],
        state,
    )

    assert "当前可直接选择的未问目标：无" in instruction
    assert "不得为了避免结束而虚构新目标" in instruction
    assert "已有实质事实时必须输出final" in instruction
    assert "不能改用final或abstain逃避" not in instruction


def test_new_runtime_target_alignment_is_checked_before_state_merge() -> None:
    state = StateManager().initial("runtime-target-alignment", "客户已说明争议背景。", max_turns=24)
    envelope = PolicyEnvelope(
        state_patch=StatePatch(
            observations=[
                FactObservation(
                    fact_id="new_payment_target",
                    label="客户实际付款金额",
                    status="unknown",
                    criticality="high",
                )
            ]
        ),
        action=StructuredAction(
            action_type="ask",
            target_type="fact",
            target_id="new_payment_target",
            reason="核实付款",
            expected_information="客户实际付款金额",
            content="您是否已经申请劳动仲裁？",
        ),
    )

    assert "question_target_misaligned" in policy_health_violations(envelope, state)


def test_single_evidence_existence_question_is_not_misread_as_two_questions() -> None:
    action = StructuredAction(
        action_type="ask",
        target_type="fact",
        target_id="third_party_records",
        expected_information="是否有第三方通讯记录可佐证暴力行为",
        content="您是否有第三方通讯记录可以佐证对方的辱骂和贬损行为？",
    )

    assert "multiple_primary_questions" not in action_question_quality_violations(action)


def test_terminal_reason_repair_preserves_final_after_targets_are_exhausted() -> None:
    state = StateManager().initial("terminal-repair-final", "客户已说明争议背景。", max_turns=24)
    state.facts.append(
        FactSlot(
            fact_id="injury_circumstances",
            label="受伤的具体经过",
            status="not_available",
            criticality="high",
        )
    )

    instruction = policy_repair_instruction(
        ["terminal_reason_admits_material_unresolved_target"], state
    )

    assert "当前可直接选择的未问目标：无" in instruction
    assert "必须保持final" in instruction
    assert "本轮不得继续改写final理由" not in instruction


def test_unavailable_target_repair_does_not_reselect_withheld_target_or_force_new_fact() -> None:
    state = StateManager().initial("target-reselection", "客户已说明争议背景。", max_turns=24)
    state.facts.extend(
        [
            FactSlot(
                fact_id="usage_scope",
                label="标识的实际使用方式",
                status="not_available",
                criticality="high",
            ),
            FactSlot(
                fact_id="usage_start_date",
                label="标识的实际使用起始时间",
                status="unknown",
                criticality="high",
            ),
        ]
    )
    state = StateManager().mark_interaction(
        state,
        turn=1,
        action_type="ask",
        target_id="usage_start_date",
        question="您从哪一年开始使用该标识？",
        response_kind="withheld",
    )

    instruction = policy_repair_instruction(
        [
            "ask_target_not_unresolved:usage_scope:not_available",
            "target_not_available:usage_scope",
            "repeated_fact_target:usage_scope",
        ],
        state,
    )

    assert "当前可直接选择的未问目标：无" in instruction
    assert "本轮不得选择这些目标" in instruction
    assert "usage_start_date" in instruction
    assert "不能改用final或abstain逃避" not in instruction


def test_terminal_reason_preserves_withheld_as_distinct_from_unavailable() -> None:
    state = StateManager().initial("withheld-terminal", "客户已说明争议背景。", max_turns=24)
    state.facts.append(
        FactSlot(
            fact_id="usage_start_date",
            label="标识的实际使用起始时间",
            status="unknown",
            criticality="high",
        )
    )
    state = StateManager().mark_interaction(
        state,
        turn=1,
        action_type="ask",
        target_id="usage_start_date",
        question="您从哪一年开始使用该标识？",
        response_kind="withheld",
    )

    collapsed = PolicyEnvelope(
        action=StructuredAction(
            action_type="final",
            target_type="session",
            reason="关键使用方式、起始时间及异议理由仍不可得，无法形成完整分析。",
        )
    )
    assert "terminal_collapses_withheld_into_unavailable" in policy_health_violations(
        collapsed, state
    )

    preserved = PolicyEnvelope(
        action=StructuredAction(
            action_type="final",
            target_type="session",
            reason="起始时间本次未披露；现有事实足以形成以已披露内容为限的条件性分析。",
        )
    )
    assert "terminal_collapses_withheld_into_unavailable" not in (
        policy_health_violations(preserved, state)
    )

    instruction = policy_repair_instruction(["terminal_collapses_withheld_into_unavailable"], state)
    assert "usage_start_date（标识的实际使用起始时间）" in instruction
    assert "withheld只表示客户本次未披露" in instruction
    assert "保持final" in instruction


def test_stop_gate_preserves_abstention_while_grounded_target_remains() -> None:
    state = StateManager().initial("unresolved", "开场", max_turns=6)
    state.facts.append(
        FactSlot(
            fact_id="document_content",
            label="文件具体内容",
            status="unknown",
            criticality="high",
        )
    )
    assert StopGate().evaluate(state, StructuredAction(action_type="abstain")) == (
        "PASS",
        "explicit_abstention",
    )


def test_policy_health_accepts_two_substantive_unknowns_and_unresolved_target() -> None:
    state = StateManager().initial("healthy-policy", "开场", max_turns=6)
    envelope = PolicyEnvelope(
        state_patch=StatePatch(
            observations=[
                FactObservation(
                    fact_id="notice_content",
                    label="通知内容",
                    status="unknown",
                    criticality="high",
                ),
                FactObservation(
                    fact_id="available_documents",
                    label="现有文件",
                    status="unknown",
                    criticality="medium",
                ),
            ]
        ),
        action=StructuredAction(
            action_type="ask",
            target_type="fact",
            target_id="notice_content",
            content="对方向您发出的书面通知具体要求什么？",
        ),
    )
    assert policy_health_violations(envelope, state) == []


def test_policy_health_blocks_management_fact_but_scores_known_ask_target() -> None:
    state = StateManager().initial("unhealthy-policy", "开场", max_turns=6)
    state.facts.append(
        FactSlot(
            fact_id="transfer_agreement",
            label="转让协议",
            status="client_claimed",
            value="已经签署",
        )
    )
    envelope = PolicyEnvelope(
        state_patch=StatePatch(
            observations=[
                FactObservation(
                    fact_id="client_identity",
                    label="客户身份",
                    status="client_claimed",
                    value="股东",
                )
            ]
        ),
        action=StructuredAction(
            action_type="ask",
            target_type="fact",
            target_id="transfer_agreement",
            content="是否签署转让协议？",
        ),
    )
    violations = policy_health_violations(envelope, state)
    assert any(item.startswith("forbidden_management_facts") for item in violations)
    known_target = "ask_target_not_unresolved:transfer_agreement:client_claimed"
    assert known_target in violations
    assert known_target not in blocking_policy_health_violations(violations)
    assert blocking_policy_health_violations(violations) == [
        "forbidden_management_facts:client_identity"
    ]
    assert not any("minimum=" in item for item in violations)


def test_policy_health_scores_repeated_fact_target_without_contract_repair() -> None:
    manager = StateManager()
    state = manager.initial("repeated-target", "开场", max_turns=6)
    state.facts.append(FactSlot(fact_id="payment_time", label="付款时间", status="unknown"))
    state = manager.mark_interaction(
        state,
        turn=1,
        action_type="ask",
        target_id="payment_time",
        question="付款发生在什么时候？",
    )
    envelope = PolicyEnvelope(
        state_patch=StatePatch(),
        action=StructuredAction(
            action_type="ask",
            target_type="fact",
            target_id="payment_time",
            content="请再说一次付款时间？",
        ),
    )
    violations = policy_health_violations(envelope, state)
    assert "repeated_fact_target:payment_time" in violations
    assert blocking_policy_health_violations(violations) == []


def test_policy_health_scores_question_repeat_that_differs_only_by_punctuation() -> None:
    manager = StateManager()
    state = manager.initial("punctuation-repeat", "开场", max_turns=6)
    state.facts.append(FactSlot(fact_id="payment_time", label="付款时间", status="unknown"))
    state = manager.mark_interaction(
        state,
        turn=1,
        action_type="ask",
        target_id="payment_time",
        question="付款发生在什么时候",
        response_kind="withheld",
    )
    envelope = PolicyEnvelope(
        state_patch=StatePatch(),
        action=StructuredAction(
            action_type="ask",
            target_type="fact",
            target_id="payment_time",
            content="付款发生在什么时候？",
        ),
    )

    violations = policy_health_violations(envelope, state)

    assert "repeated_question_text" in violations
    assert blocking_policy_health_violations(violations) == []


def test_policy_health_does_not_treat_route_contract_fallback_as_a_prior_question() -> None:
    manager = StateManager()
    state = manager.initial("route-fallback-retry", "开场", max_turns=6)
    state.facts.append(FactSlot(fact_id="payment_time", label="付款时间", status="unknown"))
    state = manager.mark_interaction(
        state,
        turn=1,
        action_type="ask",
        target_id="payment_time",
        question="付款发生在什么时候？",
        target_not_available=True,
        target_answered=True,
        client_response="现有信息里没有这项具体情况，我需要再核实。",
        response_kind="contract_fallback",
        disclosed_fact_ids=["F1"],
    )
    envelope = PolicyEnvelope(
        state_patch=StatePatch(),
        action=StructuredAction(
            action_type="ask",
            target_type="fact",
            target_id="payment_time",
            content="付款发生在什么时候？",
        ),
    )

    violations = policy_health_violations(envelope, state)

    assert state.asked_targets == []
    assert next(item for item in state.facts if item.fact_id == "payment_time").status == "unknown"
    assert "repeated_question_text" not in violations
    assert not any(item.startswith("repeated_fact_target:") for item in violations)
    assert not any(
        item.startswith("repeated_action_target_without_content:") for item in violations
    )


def test_policy_patch_cannot_revive_unavailable_target() -> None:
    manager = StateManager()
    state = manager.initial("unavailable-target", "开场", max_turns=6)
    state.facts.append(FactSlot(fact_id="agreement", label="协议", status="unknown"))
    state = manager.mark_interaction(
        state,
        turn=1,
        action_type="ask",
        target_id="agreement",
        question="是否签过协议？",
        target_not_available=True,
    )
    patch = StatePatch(
        observations=[
            FactObservation(
                fact_id="agreement",
                label="协议",
                status="unknown",
                value=None,
            )
        ]
    )
    envelope = PolicyEnvelope(
        state_patch=patch,
        action=StructuredAction(
            action_type="verify",
            target_type="fact",
            target_id="agreement",
            content="请再找一下协议。",
        ),
    )
    violations = policy_health_violations(envelope, state)
    assert "state_status_regression:agreement" in violations
    assert "target_not_available:agreement" in violations
    assert "repeated_fact_target:agreement" in violations
    merged = manager.merge(state, patch, turn=2)
    agreement = next(item for item in merged.facts if item.fact_id == "agreement")
    assert agreement.status == "not_available"


def test_state_does_not_treat_client_statement_as_independent_evidence() -> None:
    manager = StateManager()
    state = manager.initial("evidence-boundary", "开场", max_turns=6)
    state = manager.merge(
        state,
        StatePatch(
            observations=[
                FactObservation(
                    fact_id="payment",
                    label="付款情况",
                    status="corroborated",
                    value="已经付款",
                    evidence_labels=["opening_statement"],
                )
            ]
        ),
        turn=1,
    )
    payment = next(item for item in state.facts if item.fact_id == "payment")
    assert payment.status == "client_claimed"
    assert payment.evidence_ids == []
    assert state.evidence == []


def test_valid_empty_client_selection_marks_target_not_available() -> None:
    manager = StateManager()
    state = manager.initial("unavailable-target", "开场", max_turns=6)
    state.facts.append(FactSlot(fact_id="certificate_number", label="证书编号", status="unknown"))
    state = manager.mark_interaction(
        state,
        turn=1,
        action_type="ask",
        target_id="certificate_number",
        question="证书编号是什么？",
        target_not_available=True,
    )
    target = next(item for item in state.facts if item.fact_id == "certificate_number")
    assert target.status == "not_available"


def test_relevance_validated_client_answer_is_written_to_exact_target() -> None:
    manager = StateManager()
    state = manager.initial("answered-target", "合同履行发生争议。", max_turns=6)
    state.facts.append(FactSlot(fact_id="payment_date", label="付款日期", status="unknown"))
    state = manager.mark_interaction(
        state,
        turn=1,
        action_type="ask",
        target_id="payment_date",
        question="付款发生在哪一天？",
        target_answered=True,
        client_response="按我的理解，付款发生在2025年3月1日。",
    )
    target = next(item for item in state.facts if item.fact_id == "payment_date")
    assert target.status == "client_claimed"
    assert target.value == "按我的理解，付款发生在2025年3月1日。"
    assert target.source_turns == [1]


def test_question_quality_rejects_abstract_and_legal_judgment_questions() -> None:
    abstract = StructuredAction(action_type="ask", target_type="fact", content="请说明纠纷后果？")
    judgment = StructuredAction(
        action_type="ask", target_type="fact", content="是否构成恶意逃避债务？"
    )
    assert action_question_quality_violations(abstract) == ["generic_or_abstract_question"]
    assert action_question_quality_violations(judgment) == [
        "question_requests_legal_judgment_from_client"
    ]


@pytest.mark.parametrize(
    ("content", "expected_findings"),
    [
        ("请说明纠纷后果？", ["generic_or_abstract_question"]),
        ("是否构成恶意逃避债务？", ["question_requests_legal_judgment_from_client"]),
        (
            "客户是否提供合同、合同文本、合同文本、合同文本、合同文本？",
            ["excessive_phrase_repetition"],
        ),
        (
            "章程是否具有法律效力？是否符合公司法规定？",
            ["question_requests_legal_judgment_from_client", "multiple_primary_questions"],
        ),
    ],
)
def test_lawyer_behavior_findings_remain_visible_but_nonblocking(
    content: str,
    expected_findings: list[str],
) -> None:
    state = StateManager().initial("scoreable-behavior", "客户已说明争议背景。", max_turns=6)
    envelope = PolicyEnvelope(
        action=StructuredAction(
            action_type="ask",
            target_type="session",
            content=content,
        )
    )

    findings = policy_health_violations(envelope, state)

    assert findings == expected_findings
    assert blocking_policy_health_violations(findings) == []


def test_question_quality_allows_conditional_detail_of_the_same_record() -> None:
    action = StructuredAction(
        action_type="ask",
        target_type="fact",
        content="您是否取得孩子伤痕的医学诊断记录？如果有，请描述记录的内容。",
    )
    assert "multiple_primary_questions" not in action_question_quality_violations(action)

    unrelated = action.model_copy(
        update={"content": "您是否取得孩子伤痕的医学诊断记录？如果有，请说明事故伤情。"}
    )
    assert "multiple_primary_questions" in action_question_quality_violations(unrelated)


def test_question_quality_rejects_structured_decoding_repetition_loop() -> None:
    action = StructuredAction(
        action_type="ask",
        target_type="fact",
        content="客户是否提供合同、合同文本、合同文本、合同文本、合同文本？",
    )
    assert "excessive_phrase_repetition" in action_question_quality_violations(action)


def test_question_quality_rejects_identical_coordinated_phrase() -> None:
    action = StructuredAction(
        action_type="ask",
        target_type="fact",
        content="客户是否知道或知道原公司作出决定的时间？",
    )
    assert "excessive_phrase_repetition" in action_question_quality_violations(action)


def test_repetition_detector_allows_nested_legal_noun_phrases() -> None:
    state = StateManager().initial("legal-noun", "公司涉及虚假报告争议。", max_turns=6)
    state.facts.append(
        FactSlot(
            fact_id="staff_roles",
            label="管理人员和业务人员的具体角色",
            status="unknown",
        )
    )
    envelope = PolicyEnvelope(
        action=StructuredAction(
            action_type="ask",
            target_type="fact",
            target_id="staff_roles",
            reason="该事实影响刑事责任和责任分配，目前尚未获取。",
            expected_information="管理人员和业务人员的具体角色",
            content="管理人员和业务人员分别承担了哪些具体角色？",
        )
    )
    assert "action_metadata_excessive_phrase_repetition:reason" not in (
        policy_health_violations(envelope, state)
    )


def test_question_quality_rejects_unresolved_deictic_target() -> None:
    action = StructuredAction(
        action_type="ask",
        target_type="fact",
        content="客户是否知道该事实的详细信息？",
    )
    assert "generic_or_abstract_question" in action_question_quality_violations(action)


def test_question_quality_rejects_role_reversing_help_prompt() -> None:
    action = StructuredAction(
        action_type="ask",
        target_type="fact",
        content="您需要我提供什么帮助？",
    )
    assert "generic_or_abstract_question" in action_question_quality_violations(action)


def test_question_quality_rejects_client_legal_rule_knowledge() -> None:
    action = StructuredAction(
        action_type="ask",
        target_type="fact",
        content="您是否知道原告诉讼的诉讼时效？",
    )
    assert "question_requests_legal_judgment_from_client" in (
        action_question_quality_violations(action)
    )


def test_question_quality_rejects_client_legal_relationship_classification() -> None:
    action = StructuredAction(
        action_type="ask",
        target_type="fact",
        content="公司代表是否是劳动关系中的主体？",
    )
    assert "question_requests_legal_judgment_from_client" in (
        action_question_quality_violations(action)
    )


def test_question_quality_rejects_client_responsibility_existence_judgment() -> None:
    action = StructuredAction(
        action_type="ask",
        target_type="fact",
        content="公司是否在该事件中存在责任或义务？",
    )
    assert "question_requests_legal_judgment_from_client" in (
        action_question_quality_violations(action)
    )


def test_question_quality_allows_current_factual_employment_status() -> None:
    action = StructuredAction(
        action_type="ask",
        target_type="fact",
        content="您目前是否仍然与保安公司保持劳动关系？",
    )
    assert action_question_quality_violations(action) == []


def test_policy_health_rejects_unseen_precise_numeric_anchor() -> None:
    state = StateManager().initial("unseen-date", "客户称2022年7月入职。", max_turns=6)
    state.facts.append(FactSlot(fact_id="agreement_date", label="协议签署日期", status="unknown"))
    unseen = PolicyEnvelope(
        action=StructuredAction(
            action_type="ask",
            target_type="fact",
            target_id="agreement_date",
            content="您是否在2023年10月1日之前签署过协议？",
        )
    )
    visible = unseen.model_copy(deep=True)
    visible.action.content = "您是否在2022年7月之前签署过协议？"
    assert "unseen_specific_numeric_anchor:2023年10月1日" in policy_health_violations(unseen, state)
    assert not any(
        item.startswith("unseen_specific_numeric_anchor:")
        for item in policy_health_violations(visible, state)
    )


def test_policy_health_rejects_repetition_in_action_metadata() -> None:
    state = StateManager().initial("metadata-loop", "存在劳动争议。", max_turns=6)
    state.facts.append(
        FactSlot(fact_id="company_statement", label="公司的实际说明", status="unknown")
    )
    repeated = "公司代表作出说明"
    envelope = PolicyEnvelope(
        action=StructuredAction(
            action_type="ask",
            target_type="fact",
            target_id="company_statement",
            reason="，".join([repeated] * 5),
            content="公司代表当时具体说明了什么？",
        )
    )
    violations = policy_health_violations(envelope, state)
    assert "action_metadata_excessive_phrase_repetition:reason" in violations
    assert blocking_policy_health_violations(violations) == []


def test_policy_health_rejects_unsafe_model_created_fact_slot() -> None:
    state = StateManager().initial("unsafe-new-slot", "存在劳动争议。", max_turns=6)
    envelope = PolicyEnvelope(
        state_patch=StatePatch(
            observations=[
                FactObservation(
                    fact_id="fact_id_0000",
                    label="该事实的详细信息",
                    status="unknown",
                )
            ]
        ),
        action=StructuredAction(
            action_type="ask",
            target_type="fact",
            target_id="fact_id_0000",
            content="客户是否知道该事实的详细信息？",
        ),
    )
    issues = policy_health_violations(envelope, state)
    assert any(item.startswith("unsafe_new_fact_target:fact_id_0000:") for item in issues)


def test_policy_normalization_repairs_repetition_without_retargeting() -> None:
    state = StateManager().initial("repetition-loop", "存在合同争议。", max_turns=6)
    state.facts.append(
        FactSlot(fact_id="agreement_document", label="解除协议文本", status="unknown")
    )
    envelope = PolicyEnvelope(
        action=StructuredAction(
            action_type="ask",
            target_type="fact",
            target_id="agreement_document",
            expected_information="解除协议文本",
            content="客户是否提供合同、合同文本、合同文本、合同文本、合同文本？",
        )
    )
    normalized, changes = normalize_policy_envelope(envelope, state)
    assert normalized.action.target_id == "agreement_document"
    assert normalized.action.content == envelope.action.content
    assert changes == []
    assert "excessive_phrase_repetition" in action_question_quality_violations(normalized.action)


def test_policy_normalization_preserves_delimited_illustrative_suffix_for_scoring() -> None:
    state = StateManager().initial("illustration", "存在产品宣传争议。", max_turns=6)
    state.facts.append(
        FactSlot(fact_id="advertising_text", label="宣传材料的文字内容", status="unknown")
    )
    envelope = PolicyEnvelope(
        action=StructuredAction(
            action_type="ask",
            target_type="fact",
            target_id="advertising_text",
            content="您能提供宣传材料中的文字内容吗？例如广告语、宣传页或视频脚本？",
        )
    )
    normalized, changes = normalize_policy_envelope(envelope, state)
    assert normalized.action.content == envelope.action.content
    assert changes == []
    assert "multiple_primary_questions" in action_question_quality_violations(
        normalized.action
    )


def test_policy_normalization_preserves_comma_delimited_examples_for_scoring() -> None:
    state = StateManager().initial("comma-illustration", "存在商业使用争议。", max_turns=6)
    state.facts.append(FactSlot(fact_id="usage", label="实际商业使用方式", status="unknown"))
    envelope = PolicyEnvelope(
        action=StructuredAction(
            action_type="ask",
            target_type="fact",
            target_id="usage",
            expected_information="实际商业使用方式",
            content="请说明实际商业使用的具体方式，例如广告、包装或宣传材料。",
        )
    )
    normalized, changes = normalize_policy_envelope(envelope, state)
    assert normalized.action.target_id == "usage"
    assert normalized.action.content == envelope.action.content
    assert changes == []


def test_policy_normalization_does_not_hide_bad_surface_while_creating_target() -> None:
    state = StateManager().initial("including-suffix", "客户称受伤后接受治疗。", max_turns=6)
    envelope = PolicyEnvelope(
        action=StructuredAction(
            action_type="ask",
            target_type="fact",
            target_id="medical_records",
            expected_information="医疗记录",
            content="您是否可以提供一份完整的医疗记录，包括诊断结果、治疗过程和费用明细？",
        )
    )
    normalized, changes = normalize_policy_envelope(envelope, state)
    assert normalized.action.target_id == "medical_records"
    assert normalized.action.content == envelope.action.content
    assert normalized.state_patch.observations == []
    assert changes == []
    assert "multiple_primary_questions" in action_question_quality_violations(
        normalized.action
    )
    # The question quality is scoreable, but a fact target absent from both visible
    # state and the same envelope's patch remains a genuine protocol failure.
    assert blocking_policy_health_violations(
        policy_health_violations(normalized, state)
    ) == ["factual_target_missing_from_state:medical_records"]


def test_open_gap_sentinel_materializes_before_compound_behavior_is_scored() -> None:
    state = StateManager().initial("open-gap-compound", "存在跨境买卖争议。", max_turns=6)
    envelope = PolicyEnvelope(
        action=StructuredAction(
            action_type="ask",
            target_type="fact",
            target_id="new_visible_gap",
            expected_information="合同约定的适用法律规则及质量标准",
            content="合同是否约定了适用法律规则以及质量标准？",
        )
    )

    normalized, changes = normalize_policy_envelope(envelope, state)
    issues = policy_health_violations(normalized, state)

    assert normalized.action.target_id.startswith("dialogue_fact_")
    assert [item.fact_id for item in normalized.state_patch.observations] == [
        normalized.action.target_id
    ]
    assert any(item.startswith("canonicalize_runtime_target:new_visible_gap->") for item in changes)
    assert "multiple_primary_questions" in issues
    assert not any(item.startswith("factual_target_missing_from_state:") for item in issues)
    assert blocking_policy_health_violations(issues) == []


def test_open_gap_identity_does_not_collapse_distinct_declared_dimensions() -> None:
    state = StateManager().initial("open-gap-identity", "某公司参加项目投标。", max_turns=6)
    broad = PolicyEnvelope(
        action=StructuredAction(
            action_type="ask",
            target_type="fact",
            target_id="new_visible_gap",
            expected_information="公司参与项目投标的具体情况",
            content="公司参与项目投标的情况怎样，例如投标时间和文件内容？",
        )
    )
    timestamp = PolicyEnvelope(
        action=StructuredAction(
            action_type="ask",
            target_type="fact",
            target_id="new_visible_gap",
            expected_information="项目投标的具体时间",
            content="该项目具体是在什么时候投标的？",
        )
    )

    broad_normalized, _ = normalize_policy_envelope(broad, state)
    timestamp_normalized, _ = normalize_policy_envelope(timestamp, state)
    broad_repeat = broad.model_copy(deep=True)
    broad_repeat.action.content = "请介绍公司参与该项目投标的具体情况。"
    broad_repeat, _ = normalize_policy_envelope(broad_repeat, state)

    # The declared one-attribute semantic dimension owns runtime identity; the
    # natural-language surface may vary without minting a fresh target.
    assert broad_normalized.state_patch.observations[0].label == "公司参与项目投标的具体情况"
    assert timestamp_normalized.state_patch.observations[0].label == "项目投标的具体时间"
    assert broad_repeat.state_patch.observations[0].label == "公司参与项目投标的具体情况"
    assert broad_normalized.action.target_id != timestamp_normalized.action.target_id
    assert broad_normalized.action.target_id == broad_repeat.action.target_id


def test_policy_normalization_preserves_one_conditional_document_target() -> None:
    state = StateManager().initial("conditional-document", "存在贷款展期争议。", max_turns=6)
    state.facts.append(
        FactSlot(fact_id="extension_terms", label="展期协议的迟延条款", status="unknown")
    )
    envelope = PolicyEnvelope(
        action=StructuredAction(
            action_type="ask",
            target_type="fact",
            target_id="extension_terms",
            expected_information="贷款展期协议中关于利息支付迟延的约定内容",
            content="贷款展期协议中是否有关于利息支付迟延的约定？如果有，请说明具体内容。",
        )
    )
    normalized, changes = normalize_policy_envelope(envelope, state)
    assert normalized.action.target_id == "extension_terms"
    assert normalized.action.content == envelope.action.content
    assert changes == []
    assert "multiple_primary_questions" not in action_question_quality_violations(
        normalized.action
    )


@pytest.mark.parametrize(
    ("target_label", "question"),
    [
        (
            "后续接续施工的具体范围以及实际完成情况",
            "后续是否由第三方接续施工？如果有，具体范围是什么？",
        ),
        (
            "新单位主营业务模式以及新单位主要产品线",
            "新单位的主营业务模式是怎样的？主要产品线有哪些？",
        ),
    ],
)
def test_policy_normalization_preserves_visible_compound_question_for_scoring(
    target_label: str,
    question: str,
) -> None:
    state = StateManager().initial("compound-surface", "客户已经说明了争议背景。", max_turns=6)
    state.facts.append(
        FactSlot(fact_id="planned_fact", label=target_label, status="unknown")
    )
    envelope = PolicyEnvelope(
        action=StructuredAction(
            action_type="ask",
            target_type="fact",
            target_id="planned_fact",
            expected_information=target_label,
            content=question,
        )
    )

    normalized, changes = normalize_policy_envelope(envelope, state)

    assert normalized.action.target_id == "planned_fact"
    assert normalized.action.expected_information == target_label
    assert normalized.action.content == question
    assert action_question_quality_violations(normalized.action) == [
        "multiple_primary_questions"
    ]
    assert action_target_alignment_violations(normalized.action, target_label) == []
    assert blocking_policy_health_violations(
        policy_health_violations(normalized, state)
    ) == []
    assert changes == []


def test_policy_normalization_does_not_project_to_an_unmentioned_compound_unit() -> None:
    state = StateManager().initial("compound-misaligned", "客户已经说明了争议背景。", max_turns=6)
    state.facts.append(
        FactSlot(
            fact_id="planned_fact",
            label="新单位主营业务模式及产品线",
            status="unknown",
        )
    )
    envelope = PolicyEnvelope(
        action=StructuredAction(
            action_type="ask",
            target_type="fact",
            target_id="planned_fact",
            content="您是否申请过劳动仲裁？如果申请过，结果是什么？",
        )
    )

    normalized, changes = normalize_policy_envelope(envelope, state)

    assert changes == []
    assert normalized.action.content == envelope.action.content
    assert "multiple_primary_questions" in action_question_quality_violations(normalized.action)


def test_policy_normalization_does_not_rewrite_a_legal_surface_question() -> None:
    state = StateManager().initial("surface", "父亲已经办理孩子姓名变更。", max_turns=6)
    state.facts.append(
        FactSlot(
            fact_id="name_change_procedure",
            label="父亲办理姓名变更时采用的具体程序",
            status="unknown",
        )
    )
    envelope = PolicyEnvelope(
        action=StructuredAction(
            action_type="ask",
            target_type="fact",
            target_id="name_change_procedure",
            expected_information="父亲办理姓名变更时采用的具体程序",
            content="父亲办理姓名变更时，是依据什么法律程序或文件进行的？",
        )
    )
    normalized, changes = normalize_policy_envelope(envelope, state)
    assert normalized.action.target_id == "name_change_procedure"
    assert normalized.action.expected_information == envelope.action.expected_information
    assert normalized.action.content == envelope.action.content
    assert changes == []
    assert action_question_quality_violations(normalized.action) == ["multiple_primary_questions"]


def test_question_quality_rejects_legal_limitation_judgment() -> None:
    action = StructuredAction(
        action_type="ask",
        target_type="fact",
        content="二倍工资请求权的主张是否已超过法定时效？",
    )
    assert action_question_quality_violations(action) == [
        "question_requests_legal_judgment_from_client"
    ]


def test_question_quality_rejects_multiple_legal_questions() -> None:
    action = StructuredAction(
        action_type="ask",
        target_type="fact",
        content="章程是否具有法律效力？是否符合公司法规定？",
    )
    assert action_question_quality_violations(action) == [
        "question_requests_legal_judgment_from_client",
        "multiple_primary_questions",
    ]


def test_question_quality_rejects_observed_legal_judgment_leaks() -> None:
    questions = (
        "您签署的改领补助协议是否有效？",
        "招标方和财政部门在处理质疑过程中是否依法依规进行？",
        "财政部门介入处理是否有明确的法定授权依据？",
        "您公司提交的证据材料是否涵盖了质疑事项的全部关键点？",
        "该项目是否存在实际施工人与总包方之间的挂靠关系？",
        "您认为该行为可能涉及哪些法律责任？",
        "是否存在第三方能证明材料真实性？",
    )
    for question in questions:
        assert "question_requests_legal_judgment_from_client" in (
            action_question_quality_violations(
                StructuredAction(action_type="ask", target_type="fact", content=question)
            )
        ), question


def test_question_quality_rejects_question_mark_separated_second_request() -> None:
    action = StructuredAction(
        action_type="ask",
        target_type="fact",
        content="执法机关认定违法的具体依据是什么？是否涉及具体执法文书",
    )
    assert "multiple_primary_questions" in action_question_quality_violations(action)


def test_question_quality_allows_conditional_details_after_the_same_event() -> None:
    action = StructuredAction(
        action_type="ask",
        target_type="fact",
        content="您是否签署过改领补助协议？如果签署了，请描述协议具体内容。",
    )
    assert "multiple_primary_questions" not in action_question_quality_violations(action)


def test_question_quality_rejects_legal_relationship_and_liability_variants() -> None:
    questions = (
        "个人是否在法律上被明确排除在责任范围之外？",
        "请说明公司与股东之间的法律关系？",
        "请说明个人责任的性质？",
        "公司是否对债务承担连带责任？",
        "是否涉及法律上的侵权行为？",
    )
    for question in questions:
        issues = action_question_quality_violations(
            StructuredAction(action_type="ask", target_type="fact", content=question)
        )
        assert "question_requests_legal_judgment_from_client" in issues


def test_question_quality_rejects_normative_variants_seen_across_plan_probe() -> None:
    questions = (
        "该化妆品店是否具备合法的医美资质？",
        "实际使用的产品是否符合国家相关法规和标准？",
        "住建局是否遵循了法定程序？",
        "实际采样方法是否符合相关技术规范？",
        "合作社是否应当承担环境损害责任？",
        "客户是否已满十二岁并具备法律行为能力？",
        "客户持有的证据是否能够证明对方违反协议？",
        "客户是否知道所参与的交易是非法的？",
        "客户是否直接参与了诈骗行为？",
        "主管机关是否履行了法定程序义务？",
        "招标方和财政部门是否有权处理该类质疑事项？",
        "该机构是否具备处理这项申请的权限？",
        "客户在合同履行过程中是否存在违约？",
        "客户目前持有的能够证明对方违反协议的证据材料是什么？",
        "平台是否知晓或应知商家销售盗版电子书？",
        "合作社是否知晓或应当知晓保护植物的存在？",
        "客户是否意识到其行为涉及诈骗犯罪？",
        "客户是否知道交付过程存在违法性？",
        "补救措施对拆迁补偿可能产生什么影响？",
        "购房合同是否真实有效？",
        "购房款是否真实支付且来源合法？",
        "被执行公司是否参与制造虚假诉讼？",
        "住建局作出决定所依据的上位法条文是什么？",
    )
    for question in questions:
        issues = action_question_quality_violations(
            StructuredAction(action_type="ask", target_type="fact", content=question)
        )
        assert "question_requests_legal_judgment_from_client" in issues, question


def test_question_quality_allows_reading_effect_from_judgment_document() -> None:
    action = StructuredAction(
        action_type="ask",
        target_type="evidence",
        content="生效判决是否已明确免除保证责任？",
    )
    assert action_question_quality_violations(action) == []


def test_question_quality_allows_official_statement_and_adjudication_knowledge() -> None:
    questions = (
        "审批局最初核准项目时是否明确项目符合规划要求？",
        "客户是否知晓科技公司法定代表人因集资诈骗被判刑的情况？",
    )
    for question in questions:
        assert (
            action_question_quality_violations(
                StructuredAction(action_type="ask", target_type="fact", content=question)
            )
            == []
        )


def test_question_quality_rejects_cross_category_bundles_but_allows_same_attribute_forms() -> None:
    rejected = (
        "请说明转账的频率和用途？",
        "请说明孩子的生活状况和健康情况？",
        "请说明对方的真实意图及双方是否另有约定？",
        "请说明实际效果和学员反馈？",
        "请说明购房人是否真实存在且实际购买了房产？",
        "请说明财产当前市场价值及评估方式？",
        "请说明对方的具体说法及是否另有承诺？",
    )
    for question in rejected:
        assert "multiple_primary_questions" in action_question_quality_violations(
            StructuredAction(action_type="ask", target_type="fact", content=question)
        )
    allowed = (
        "双方是否有书面或口头约定？",
        "对方目前的主张或态度是什么？",
        "合同的具体条款和条件是什么？",
        "行政机关认定规划问题所依据的文件或资料名称是什么？",
        "学校或医疗机构是否留存有孩子使用该姓名的相关记录？",
    )
    for question in allowed:
        assert "multiple_primary_questions" not in action_question_quality_violations(
            StructuredAction(action_type="ask", target_type="fact", content=question)
        )

    atomic_context_questions = (
        "施工项目的具体范围是什么？",
        "目前谁负责保存与该员工相关的雇佣记录和文件？",
        "该治理产品使用频率或周期是什么？",
        "该治理产品由谁具体操作或使用？",
        "是否存在第三方检测报告或数据？",
        "该治理产品的使用说明或操作方式是什么？",
        "离婚后关于小儿子抚养权的约定或法院判决内容是什么？",
        "与兼职人员沟通的方式是什么？",
        "与兼职人员沟通的频率是什么？",
        "贷款合同中关于违约及加速到期的具体条款内容是什么？",
        "医疗记录或诊断文件中关于面部异常的具体描述是什么？",
        "与对方沟通挂牌交易进展的具体内容是什么？",
        "与对方沟通挂牌交易进展的具体时间是什么？",
        "申请过程中与文体部门沟通的具体人员姓名是什么？",
    )
    for question in atomic_context_questions:
        assert "multiple_primary_questions" not in action_question_quality_violations(
            StructuredAction(action_type="ask", target_type="fact", content=question)
        )

    still_bundled = StructuredAction(
        action_type="ask",
        target_type="fact",
        content="行政机关认定规划问题所依据的文件名称和具体内容是什么？",
    )
    assert "multiple_primary_questions" in action_question_quality_violations(still_bundled)


def test_question_quality_allows_anaphoric_context_for_the_same_event_only() -> None:
    same_event = StructuredAction(
        action_type="ask",
        target_type="fact",
        content="您能描述辱骂和贬损的具体内容，以及这些行为通常发生的场景吗？",
    )
    assert "multiple_primary_questions" not in action_question_quality_violations(same_event)
    same_event_with_venue = same_event.model_copy(
        update={"content": "您能描述对方辱骂和贬损您的内容，以及这些行为通常发生在什么场合吗？"}
    )
    assert "multiple_primary_questions" not in action_question_quality_violations(
        same_event_with_venue
    )

    independent_act = same_event.model_copy(
        update={"content": "请说明对方辱骂的具体内容，以及是否还有肢体行为？"}
    )
    assert "multiple_primary_questions" in action_question_quality_violations(independent_act)


def test_question_quality_does_not_count_a_factual_recap_as_a_second_request() -> None:
    atomic_recap = StructuredAction(
        action_type="ask",
        target_type="fact",
        content="您提到的辱骂和贬损行为，具体都包含哪些内容？",
    )
    assert "multiple_primary_questions" not in action_question_quality_violations(atomic_recap)

    two_real_questions = atomic_recap.model_copy(
        update={
            "content": "您提到的辱骂和贬损行为，具体都包含哪些内容？这些行为通常发生在什么场景下？"
        }
    )
    assert "multiple_primary_questions" in action_question_quality_violations(
        two_real_questions
    )


def test_target_alignment_accepts_grounded_atomic_projection_of_compound_label() -> None:
    projections = (
        (
            "孩子年龄以及本人对姓名变更的意愿",
            "孩子目前的年龄",
            "孩子目前的年龄是多少？",
        ),
        (
            "受伤部位以及治疗情况（如医院名称、诊断证明、医疗费用明细）",
            "受伤部位",
            "您受伤的具体部位是什么？",
        ),
        (
            "事故经过细节（如车辆位置、转向动作、是否抢道、信号灯状态）",
            "事故发生时车辆的具体位置和转向动作",
            "事故发生时，您的摩托车和汽车是在什么位置？",
        ),
    )
    for label, expected, question in projections:
        action = StructuredAction(
            action_type="ask",
            target_type="fact",
            target_id="planned_fact",
            expected_information=expected,
            content=question,
        )
        assert action_target_alignment_violations(action, label) == []

    unrelated = StructuredAction(
        action_type="ask",
        target_type="fact",
        target_id="planned_fact",
        expected_information="事故发生后是否报警",
        content="事故发生后您是否报警？",
    )
    assert action_target_alignment_violations(
        unrelated,
        "事故经过细节（如车辆位置、转向动作、是否抢道、信号灯状态）",
    ) == []


def test_question_quality_allows_single_clause_and_technical_scope_propositions() -> None:
    questions = (
        "您与原始提供方签订的协议中，是否有关于商业用途的具体限制条款？",
        "在AI产品开发过程中，每家公司具体负责了哪些技术环节或内容？",
    )
    for question in questions:
        assert "multiple_primary_questions" not in action_question_quality_violations(
            StructuredAction(action_type="ask", target_type="fact", content=question)
        )


def test_question_quality_treats_event_and_document_context_as_atomic() -> None:
    from legal_skill_guard.agent.stateful_policy import (
        factual_target_question_safety_violations,
    )

    labels = (
        "您与建筑公司签订的劳动合同中约定的工资金额",
        "您与建筑公司签订的劳动合同中约定的工资支付周期",
        "参与培训和兼职的人员遭受的具体损失金额",
        "你购买二手名表时与卖家沟通的具体内容是什么",
        "参与培训和兼职的人员是否已遭受损失",
    )
    for label in labels:
        assert factual_target_question_safety_violations("planned_fact", label) == []

    assert "multiple_primary_questions" in factual_target_question_safety_violations(
        "planned_fact", "参与培训和兼职的人员当前的状况和是否已遭受损失"
    )


def test_planner_target_rejects_unobservable_third_party_internal_reasoning() -> None:
    from legal_skill_guard.agent.stateful_policy import (
        factual_target_question_safety_violations,
    )

    rejected = (
        "银行评估保证人风险所进行的具体分析内容",
        "平台内部审核决定的具体依据和流程",
        "行政机关内部研判所采用的方法",
    )
    for label in rejected:
        assert factual_target_question_safety_violations("planned_fact", label) == [
            "unobservable_third_party_internal_process"
        ]

    assert (
        factual_target_question_safety_violations("planned_fact", "银行通知书载明的提前到期理由")
        == []
    )


def test_planner_treats_infringement_notice_as_observable_communication() -> None:
    assert (
        factual_target_question_safety_violations("notice_sent", "客户是否向平台提交过侵权通知")
        == []
    )
    assert (
        factual_target_question_safety_violations(
            "notice_received", "平台是否收到客户提交的侵权告知"
        )
        == []
    )
    assert (
        factual_target_question_safety_violations("notice_action", "平台是否对侵权投诉采取处理措施")
        == []
    )

    assert factual_target_question_safety_violations(
        "accused_product", "侵权电子书的具体销售数量"
    ) == ["abstract_marker:侵权"]
    assert factual_target_question_safety_violations(
        "internal_detection", "平台是否启用侵权自动检测系统"
    ) == ["abstract_marker:侵权"]


def test_question_quality_rejects_intent_and_true_evidence_sufficiency_variants() -> None:
    rejected = (
        "博主发布测评时是否具有主观贬损我司产品的意图？",
        "现有证据是否足以证明丈夫使用侮辱性语言？",
    )
    for question in rejected:
        assert "question_requests_legal_judgment_from_client" in (
            action_question_quality_violations(
                StructuredAction(action_type="ask", target_type="fact", content=question)
            )
        )


def test_question_quality_allows_factual_witness_or_evidence_source_inquiry() -> None:
    for question in (
        "是否有证人或证据能够反映丈夫使用侮辱性语言的经过？",
        "是否有邻居或亲属能够证明孩子受伤的具体经过？",
    ):
        assert "question_requests_legal_judgment_from_client" not in (
            action_question_quality_violations(
                StructuredAction(action_type="ask", target_type="fact", content=question)
            )
        )


def test_question_quality_allows_factual_victim_identity_and_loss_inquiry() -> None:
    for question in (
        "您是否知道被诈骗的受害人是谁，以及他们具体遭受了哪些损失？",
        "被诈骗受害人是否明确及具体受损情况？",
    ):
        assert "question_requests_legal_judgment_from_client" not in (
            action_question_quality_violations(
                StructuredAction(action_type="ask", target_type="fact", content=question)
            )
        )
    assert "question_requests_legal_judgment_from_client" in (
        action_question_quality_violations(
            StructuredAction(
                action_type="ask",
                target_type="fact",
                content="您是否知道上线的行为属于诈骗？",
            )
        )
    )


def test_alignment_accepts_age_as_atomic_paraphrase_of_compound_target() -> None:
    for question in ("孩子现在多大了？", "孩子现在几岁？", "孩子现在多少岁了？"):
        action = StructuredAction(
            action_type="ask",
            target_type="fact",
            target_id="minor_intention_relevance",
            expected_information="孩子的年龄",
            content=question,
        )
        assert action_target_alignment_violations(
            action,
            "孩子年龄及本人对姓名变更的意愿",
        ) == []


def test_fact_selection_schema_restricts_generation_to_current_candidates() -> None:
    schema = client_fact_selection_schema(["F2", "F7"])
    assert schema["properties"]["fact_ids"]["items"]["enum"] == ["F2", "F7"]


def test_client_relevance_requires_the_requested_calendar_granularity() -> None:
    from tests.legacy_support.client_simulator_protocol35 import (
        deterministic_relevance_compatibility,
    )

    relative_only = "我们在对方申请前已经广泛宣传使用该域名并形成知名度。"
    compatible, violations = deterministic_relevance_compatibility(
        "您首次使用该名称是在哪一年？", relative_only
    )
    assert compatible is False
    assert "requested_calendar_year_missing" in violations

    compatible, violations = deterministic_relevance_compatibility(
        "该名称首次使用的月份", "我们在2020年开始使用该名称。"
    )
    assert compatible is False
    assert "requested_calendar_month_missing" in violations

    compatible, violations = deterministic_relevance_compatibility(
        "您首次使用该名称是在哪一年？", "我们从2020年开始持续使用。"
    )
    assert "requested_calendar_year_missing" not in violations


def test_client_relevance_keeps_document_contents_and_external_reasons_distinct() -> None:
    compatible, violations = deterministic_relevance_compatibility(
        "现有户籍档案、学校记录和医疗证明具体记载什么？",
        "父亲向派出所申请改回户籍姓名，此后双方协商没有结果。",
    )
    assert compatible is False
    assert "requested_document_contents_missing" in violations

    compatible, violations = deterministic_relevance_compatibility(
        "文体部门具体指出哪些材料无法核实？",
        "通知认为新负责人无法核实且审批手续不符合要求。",
    )
    assert compatible is False
    assert "requested_unverifiable_material_items_missing" in violations

    compatible, violations = deterministic_relevance_compatibility(
        "建筑公司拒绝承担待遇时提出了哪些抗辩理由？",
        "我担心双方没有劳动关系就意味着公司完全不负责任。",
    )
    assert compatible is False
    assert any(
        item.startswith("requested_attributed_statement_subject_mismatch") for item in violations
    )

    compatible, violations = deterministic_relevance_compatibility(
        "建筑公司说为什么不承担工伤待遇？",
        "建筑公司没有为我缴纳工伤保险费，我担心因此没有保险基金可以支付。",
    )
    assert compatible is False
    assert "requested_attributed_statement_subject_mismatch" in violations

    compatible, violations = deterministic_relevance_compatibility(
        "建筑公司说为什么不承担工伤待遇？",
        "建筑公司以双方不存在劳动关系为由拒绝承担待遇。",
    )
    assert compatible is not False
    assert "requested_attributed_statement_subject_mismatch" not in violations
    full_opening = (
        "我在工地受伤并被认定工伤，但用工和承包关系复杂，"
        "建筑公司以双方不存在劳动关系为由拒绝承担待遇"
    )
    assert asks_communication_content("建筑公司说为什么不承担工伤待遇？")
    assert direct_answer_attribute_explicit_match(
        "建筑公司说为什么不承担工伤待遇？",
        full_opening,
    )

    compatible, violations = deterministic_relevance_compatibility(
        "您在投保时是否明确告知了健康告知书中的所有问题？",
        "保险公司的拒赔理由是我投保时没有告知慢性支气管炎，并称这一情况严重影响其承保决定。",
    )
    assert compatible is False
    assert "reported_external_claim_not_client_actual_action" in violations

    compatible, violations = deterministic_relevance_compatibility(
        "保险公司具体怎样说明慢性支气管炎对承保决定的影响？",
        "保险公司称慢性支气管炎严重影响承保决定。",
    )
    assert "reported_external_claim_not_client_actual_action" not in violations

    compatible, violations = deterministic_relevance_compatibility(
        "工伤认定决定书具体写了什么结论？",
        "工伤认定决定书写明事故伤害构成工伤，并由建筑公司承担责任。",
    )
    assert compatible is not False
    assert "requested_document_contents_missing" not in violations


def test_client_relevance_keeps_registration_separate_from_asset_use() -> None:
    compatible, violations = deterministic_relevance_compatibility(
        "婚后你是否对该房屋有实际使用或管理？",
        "我们2009年1月登记结婚，房屋在次月改成了夫妻两人的名字。",
    )
    assert compatible is False
    assert "requested_asset_use_or_management_missing" in violations

    compatible, violations = deterministic_relevance_compatibility(
        "婚后你是否对该房屋有实际使用或管理？",
        "加名后我一直居住在该房屋，并负责出租和收租。",
    )
    assert compatible is not False
    assert "requested_asset_use_or_management_missing" not in violations


def test_client_relevance_does_not_treat_historical_registration_as_current_status() -> None:
    historical = "我们2009年1月登记结婚，房屋在次月改成了夫妻两人的名字。"
    compatible, violations = deterministic_relevance_compatibility(
        "这套房屋目前产权登记在谁的名下？", historical
    )
    assert compatible is False
    assert "requested_current_status_only_historical" in violations

    current = "房屋自2009年登记为双方共有后，至今仍登记在我们两人名下。"
    compatible, violations = deterministic_relevance_compatibility(
        "这套房屋目前产权登记在谁的名下？", current
    )
    assert compatible is not False
    assert "requested_current_status_only_historical" not in violations


def test_client_relevance_does_not_treat_historical_caregiver_as_current_status() -> None:
    historical = "离婚后，孩子母亲与卿某登记结婚，次子随后与母亲和继父共同生活。"
    compatible, violations = deterministic_relevance_compatibility(
        "小儿子现在跟谁生活？", historical
    )
    assert compatible is False
    assert "requested_current_status_only_historical" in violations


def test_client_relevance_requires_clock_time_when_question_asks_what_time() -> None:
    compatible, violations = deterministic_relevance_compatibility(
        "你实际在几点支付定金？",
        "我支付100元定金后立即告诉客服已经下单。",
    )
    assert compatible is False
    assert "requested_precise_time_missing" in violations

    compatible, violations = deterministic_relevance_compatibility(
        "你实际在几点支付定金？",
        "我在19时40分支付了100元定金。",
    )
    assert compatible is not False
    assert "requested_precise_time_missing" not in violations


def test_client_relevance_requires_actual_child_custody_disposition() -> None:
    question = "离婚后关于小儿子抚养权的约定或法院判决内容是什么？"
    actual_arrangement = "2022年离婚时约定长子随我生活，次子随母亲生活。"
    unrelated_caregiver_conduct = (
        "动手的是继父而不是孩子母亲，我担心仅凭她没有制止还不足以变更抚养关系。"
    )

    compatible, violations = deterministic_relevance_compatibility(question, actual_arrangement)
    assert compatible is not False
    assert "requested_child_custody_arrangement_missing" not in violations
    assert "requested_contract_term_missing" not in violations

    compatible, violations = deterministic_relevance_compatibility(
        question, unrelated_caregiver_conduct
    )
    assert compatible is False
    assert "requested_child_custody_arrangement_missing" in violations


def test_planner_target_safety_rejects_client_side_evaluative_shortcuts() -> None:
    from legal_skill_guard.agent.stateful_policy import (
        factual_target_question_safety_violations,
    )

    rejected = (
        "原人身安全保护令目前是否仍然有效",
        "保险公司是否提供了充分证据证明投保前存在健康问题",
        "合理补偿的具体计算标准",
        "该产品是否具有合法的环保声明",
    )
    for label in rejected:
        assert factual_target_question_safety_violations("planned_fact", label) == [
            "legal_or_evidentiary_judgment"
        ]


def test_planner_target_safety_rejects_bare_instrument_and_ambiguous_actor() -> None:
    assert factual_target_question_safety_violations("agreement_legality", "改领补助协议") == [
        "generic_instrument_without_observable_attribute"
    ]
    assert factual_target_question_safety_violations(
        "work_activity_connection", "事故与工作活动的关联细节"
    ) == ["ambiguous_actor_reference"]

    assert (
        factual_target_question_safety_violations(
            "signed_agreement_details", "客户签署的改领补助协议具体内容"
        )
        == []
    )
    assert (
        factual_target_question_safety_violations(
            "work_activity_connection", "事故中行为人与工作活动的关联细节"
        )
        == []
    )
    assert (
        factual_target_question_safety_violations(
            "internal_decision_record", "公司内部关于废水处理设施的决策记录"
        )
        == []
    )

    assert factual_target_question_safety_violations(
        "signed_agreement_details", "是否签署过改领补助协议及协议具体内容"
    ) == ["multiple_primary_questions"]
    assert factual_target_question_safety_violations(
        "proceeding_compliance", "招标方和财政部门处理程序"
    ) == ["legal_or_evidentiary_judgment"]


def test_planner_target_safety_rejects_observed_legal_judgment_labels() -> None:
    labels = (
        "财政部门介入处理是否有明确的法定授权依据",
        "已提交的证据材料是否覆盖质疑事项的全部关键点",
        "已提交的证据材料是否实际覆盖质疑事项",
        "项目是否存在实际施工人与总包方的挂靠关系",
        "您认为该行为可能涉及哪些法律责任",
        "是否存在第三方能证明材料真实性",
    )
    for label in labels:
        assert factual_target_question_safety_violations("planned_fact", label) == [
            "legal_or_evidentiary_judgment"
        ], label

    assert (
        factual_target_question_safety_violations(
            "official_document", "处罚决定书载明的法律责任内容"
        )
        == []
    )


def test_factual_target_safety_accepts_an_atomic_client_facing_question_label() -> None:
    from legal_skill_guard.agent.stateful_policy import (
        factual_target_question_safety_violations,
    )

    for label in (
        "您实际工作的单位名称是什么？",
        "您在哪家医院进行工伤治疗？",
        "您希望主张哪些工伤待遇项目？",
        "宠物公司具体如何承诺犬只健康状况",
        "争议电路的物理连接方式具体如何实现",
        "事故具体发生地点（如路口名称、道路标志标线）",
        "已准备的证明标识独特性的证据类型（如创意设计过程、行业罕见性说明）",
    ):
        assert factual_target_question_safety_violations("planned_fact", label) == []
    assert factual_target_question_safety_violations(
        "planned_fact",
        "子女是否有其他收入，如有请说明具体金额？",
    ) == []


def test_factual_target_safety_treats_context_and_synonym_pairs_as_one_dimension() -> None:
    atomic_labels = (
        "丈夫将孩子带往外省的具体原因或意图",
        "是否有第三方机构或人员对儿子的身心健康状况进行过评估或记录",
        "您购买该疗程时预期获得的具体效果或服务是什么",
        "购买犬只时是否签署了合同或协议",
        "该治理产品的制造商或供应商名称",
        "与兼职人员签订的合同条款和条件",
        "兼职人员或其他客户的具体投诉和反馈内容",
        "卖家是否曾就产品来源或成分问题作出回应",
        "客户开始使用该英文软件名称和域名的具体日期",
        "客户在推广该英文软件名称和域名时使用的宣传材料具体内容",
    )
    for label in atomic_labels:
        assert factual_target_question_safety_violations("planned_fact", label) == []

    # Distinct promised subjects still remain independently useful and must split.
    assert factual_target_question_safety_violations(
        "planned_fact", "合同中关于犬只健康和纯种的承诺内容"
    ) == ["multiple_primary_questions"]
    assert factual_target_question_safety_violations(
        "planned_fact", "卖家回应中说明的产品来源和具体成分"
    ) == ["multiple_primary_questions"]
    assert factual_target_question_safety_violations(
        "planned_fact", "客户使用的软件名称和具体起始时间"
    ) == ["multiple_primary_questions"]


def test_factual_target_safety_does_not_count_event_or_instrument_context_as_answers() -> None:
    atomic_labels = (
        "对方实施骚扰及伤害行为的具体时间",
        "对方实施骚扰及伤害行为的具体方式",
        "丈夫是否曾以何种方式否认限制通讯或暴力行为",
        "是否留存有医疗机构出具的伤情鉴定或治疗记录",
        "医疗机构出具的伤情鉴定或治疗记录具体内容",
        "是否持有家人因骚扰行为产生的医疗诊断或治疗记录",
        "家人因骚扰行为产生的医疗诊断或治疗内容",
        "商标审查部门是否出具过拒绝理由或显著性异议的书面内容",
        "是否有第三方市场调研、消费者问卷或销售数据佐证该表达的识别功能",
        "客户保存的软件名称使用证据类型",
        "客户是否保存软件名称使用证据",
        "平台是否保存商家上传内容的审核日志或预警记录",
    )
    for label in atomic_labels:
        assert factual_target_question_safety_violations("planned_fact", label) == []


def test_question_quality_rejects_role_reversed_legal_and_procedural_questions() -> None:
    rejected = (
        "根据中国法律，婚姻期间取得的财产一般如何分割？",
        "离婚时需要准备哪些具体材料？",
        "房产登记时需要哪些具体文件？",
        "法院在审理抚养费调整案件时，通常会审查哪些收入和财产情况？",
        "仲裁庭一般会考虑什么证据？",
    )
    for question in rejected:
        assert "question_requests_legal_judgment_from_client" in (
            action_question_quality_violations(
                StructuredAction(action_type="ask", target_type="fact", content=question)
            )
        )
    allowed = StructuredAction(
        action_type="ask", target_type="evidence", content="您目前有哪一份房产登记文件？"
    )
    assert action_question_quality_violations(allowed) == []
    assert factual_target_question_safety_violations(
        "authority_general_practice",
        "法院在审理抚养费调整案件时通常会审查哪些收入证明及财产调查手段",
    ) == ["question_requests_legal_judgment_from_client"]
    assert factual_target_question_safety_violations(
        "authority_general_practice_nominalized",
        "法院可能审查的收入证明类型及财产调查手段",
    ) == ["question_requests_legal_judgment_from_client"]
    assert factual_target_question_safety_violations(
        "documented_authority_findings",
        "法院判决书具体写明了哪些认定事实",
    ) == []


def test_authority_and_statutory_deadline_guard_is_shared_by_plan_and_question() -> None:
    unsafe_labels = (
        "财政部门对招标事项是否有直接处理权限",
        "财政部门对投标质疑的法定处理权限范围",
        "质疑提交是否在法定期限内完成",
        "诉讼时效是否已经届满",
    )
    for label in unsafe_labels:
        assert factual_target_question_safety_violations("planned_fact", label) == [
            "legal_or_evidentiary_judgment"
        ]
        assert "question_requests_legal_judgment_from_client" in (
            action_question_quality_violations(
                StructuredAction(action_type="ask", target_type="fact", content=f"{label}？")
            )
        )

    observable_labels = (
        "质疑事项正式提交的具体日期",
        "授权委托书中载明的代理权限范围",
        "通知书中写明的答复期限",
    )
    for label in observable_labels:
        assert factual_target_question_safety_violations("planned_fact", label) == []


def test_question_quality_rejects_sensitive_financial_identifier_and_abstract_impact() -> None:
    from legal_skill_guard.agent.stateful_policy import (
        factual_target_question_safety_violations,
    )

    assert factual_target_question_safety_violations(
        "recipient_account", "收款人的银行账户号码"
    ) == ["sensitive_personal_identifier"]
    assert factual_target_question_safety_violations(
        "property_impact", "转账行为对夫妻共同财产的实际影响"
    ) == ["legal_or_evidentiary_judgment"]
    assert "multiple_primary_questions" in factual_target_question_safety_violations(
        "statement_or_intent", "丈夫在转账时的具体表述或意图"
    )
    assert factual_target_question_safety_violations("identity", "收款人的具体身份信息") == [
        "generic_or_sensitive_identity_request"
    ]
    assert factual_target_question_safety_violations(
        "other_cases", "收款人是否涉及其他与付款方相关的案件或纠纷"
    ) == ["generic_mechanical_expansion"]
    assert factual_target_question_safety_violations(
        "other_conduct", "收款人是否参与付款方的其他行为（如共同消费、投资等）"
    ) == ["generic_mechanical_expansion"]
    assert factual_target_question_safety_violations("bank_details", "收款人的银行账户信息") == [
        "sensitive_personal_identifier"
    ]


def test_question_quality_allows_one_event_frame_but_rejects_cross_semantic_bundle() -> None:
    classification = StructuredAction(
        action_type="ask",
        target_type="fact",
        content="请说明电商平台是否构成不正当竞争？",
    )
    coherent_event_frame = StructuredAction(
        action_type="ask",
        target_type="fact",
        content="请说明事故发生的时间、地点、经过及造成的结果？",
    )
    cross_semantic_bundle = StructuredAction(
        action_type="ask",
        target_type="fact",
        content="请说明转账的频率和用途？",
    )
    assert "question_requests_legal_judgment_from_client" in (
        action_question_quality_violations(classification)
    )
    assert "multiple_primary_questions" not in action_question_quality_violations(
        coherent_event_frame
    )
    assert "multiple_primary_questions" in action_question_quality_violations(cross_semantic_bundle)


def test_question_quality_preserves_single_position_reason_and_workflow_actor() -> None:
    atomic_questions = (
        "建筑公司具体以什么理由主张与您不存在劳动关系？",
        "哪些部门或人员具体参与了报告制作及数据处理？",
        "公司内部报告审核和数据校验由谁负责？",
    )
    for question in atomic_questions:
        assert "multiple_primary_questions" not in action_question_quality_violations(
            StructuredAction(action_type="ask", target_type="fact", content=question)
        )

    bundled_document_request = StructuredAction(
        action_type="ask",
        target_type="fact",
        content="您是否已取得工伤认定决定书？如果有，请提供文号。",
    )
    assert "multiple_primary_questions" not in action_question_quality_violations(
        bundled_document_request
    )


def test_question_quality_treats_governing_calculation_method_as_one_proposition() -> None:
    atomic = (
        "污水处理费是依据何种具体方法和参数进行计算的？",
        "该费用依据什么公式及费率计算？",
    )
    for question in atomic:
        assert "multiple_primary_questions" not in action_question_quality_violations(
            StructuredAction(action_type="ask", target_type="fact", content=question)
        )

    genuinely_bundled = (
        "收费的法律依据和计算方法分别是什么？",
        "请说明收费金额和计算方法？",
    )
    for question in genuinely_bundled:
        assert "multiple_primary_questions" in action_question_quality_violations(
            StructuredAction(action_type="ask", target_type="fact", content=question)
        )


def test_question_quality_allows_embedded_evidence_topic_and_rejects_two_actions() -> None:
    evidence_topic = StructuredAction(
        action_type="ask",
        target_type="fact",
        content="您是否进行过关于该商标是否存在混淆可能性的消费者调查或专家意见？",
    )
    assert "multiple_primary_questions" not in action_question_quality_violations(
        evidence_topic
    )
    independent = evidence_topic.model_copy(
        update={"content": "您是否签署合同以及对方是否支付款项？"}
    )
    assert "multiple_primary_questions" in action_question_quality_violations(independent)


def test_target_alignment_accepts_event_detail_and_process_time_paraphrases() -> None:
    pairs = (
        ("实际排污行为的具体情况", "您实际排污的具体情况是怎样的？"),
        ("协商过程的具体时间", "您和父亲是什么时候开始协商孩子姓名变更的？"),
    )
    for label, content in pairs:
        action = StructuredAction(
            action_type="ask",
            target_type="fact",
            target_id="visible_target",
            expected_information=label,
            content=content,
        )
        assert action_target_alignment_violations(action, label) == []


def test_question_quality_preserves_one_event_timestamp_without_allowing_bundles() -> None:
    atomic_timestamps = (
        "您支付预付款的具体日期和时间是什么时候？",
        "您收到退件决定书的具体日期是什么？",
        "双方签署协议的时间是哪一天？",
    )
    for question in atomic_timestamps:
        assert "multiple_primary_questions" not in action_question_quality_violations(
            StructuredAction(action_type="ask", target_type="fact", content=question)
        )

    real_bundles = (
        "请说明支付预付款的日期和金额？",
        "请说明退件决定书的名称和日期？",
    )
    for question in real_bundles:
        assert "multiple_primary_questions" in action_question_quality_violations(
            StructuredAction(action_type="ask", target_type="fact", content=question)
        )


def test_target_alignment_recognizes_explicit_before_after_temporal_relation() -> None:
    label = "确诊疾病与投保行为在时间顺序上的具体关联"
    question = StructuredAction(
        action_type="ask",
        target_type="fact",
        expected_information=label,
        content="您是在投保之前还是之后确诊慢性支气管炎的？",
    )
    assert action_target_alignment_violations(question, label) == []


def test_target_alignment_recognizes_duration_paraphrases_without_conflating_timestamp() -> None:
    label = "迟延发生的具体时间长度"
    for content in (
        "这次迟延具体持续了多少天？",
        "贷款迟延的具体天数是多少？",
        "这次迟延持续了多久？",
    ):
        question = StructuredAction(
            action_type="ask",
            target_type="fact",
            target_id="delay_duration",
            expected_information="迟延的具体天数",
            content=content,
        )
        assert action_target_alignment_violations(question, label) == []

    timestamp = StructuredAction(
        action_type="ask",
        target_type="fact",
        target_id="delay_duration",
        expected_information="付款日期",
        content="您是哪一天支付贷款的？",
    )
    assert action_target_alignment_violations(timestamp, label) == []


def test_question_quality_treats_relationship_duration_as_one_fact() -> None:
    for content in (
        "您与公交公司连续订立固定期限劳动合同的总工作年限是多少？",
        "您与公司连续订立固定期限劳动合同的总工作年限是多久？",
    ):
        action = StructuredAction(action_type="ask", target_type="fact", content=content)
        assert "multiple_primary_questions" not in action_question_quality_violations(action)


def test_planner_safety_rejects_bundled_property_loss_and_casualties() -> None:
    label = "事故直接导致的财产损失及人员伤亡情况"
    assert factual_target_question_safety_violations("direct_loss", label) == [
        "multiple_primary_questions"
    ]
    action = StructuredAction(
        action_type="ask",
        target_type="fact",
        content="事故直接导致的财产损失金额及人员伤亡情况是什么？",
    )
    assert "multiple_primary_questions" in action_question_quality_violations(action)


def test_question_quality_allows_reported_authority_factual_basis() -> None:
    factual_questions = (
        "交警在事故责任认定时，是基于哪些具体事实或证据认定司机和乘客各担一半责任的？",
        "交警在事故责任认定书中，是如何具体认定司机和乘客各承担一半责任的？",
    )
    for content in factual_questions:
        action = StructuredAction(action_type="ask", target_type="fact", content=content)
        assert "question_requests_legal_judgment_from_client" not in (
            action_question_quality_violations(action)
        )

    normative = StructuredAction(
        action_type="ask",
        target_type="fact",
        content="您认为司机和乘客的责任应当如何划分？",
    )
    assert "question_requests_legal_judgment_from_client" in (
        action_question_quality_violations(normative)
    )


def test_multiple_question_repair_separates_existence_and_role_options() -> None:
    state = StateManager().initial("atomic-repair", "客户需要核实关系。", max_turns=6)
    instruction = policy_repair_instruction(["multiple_primary_questions"], state)
    assert "禁止‘是否有……如果有/具体……’" in instruction
    assert "禁止‘是否A，或者是否B’" in instruction


def test_planner_target_safety_preserves_single_relational_units() -> None:
    from legal_skill_guard.agent.stateful_policy import (
        factual_target_question_safety_violations,
    )

    linked_units = (
        "培训费用与兼职收益分配的实际比例",
        "购房人交易记录与身份信息的对应关系",
    )
    for label in linked_units:
        assert factual_target_question_safety_violations("planned_fact", label) == []


def test_skill_question_surface_projects_compound_target_to_one_atomic_attribute() -> None:
    rendered = safe_factual_question_surface(
        "plan_execution_requirements",
        "改制方案的签署主体以及改制方案的签署日期",
        target_kind="client_fact",
    )

    assert rendered == (
        "改制方案的签署主体",
        "关于改制方案的签署主体，请说明您亲历或现有文件能够确认的一项具体事实？",
    )


def test_skill_question_surface_preserves_one_relational_target() -> None:
    rendered = safe_factual_question_surface(
        "record_identity_relation",
        "购房人交易记录与身份信息的对应关系",
        target_kind="client_fact",
    )

    assert rendered == (
        "购房人交易记录与身份信息的对应关系",
        "关于购房人交易记录与身份信息的对应关系，请说明您亲历或现有文件能够确认的一项具体事实？",
    )


def test_skill_question_surface_never_splits_lexical_involvement_predicate() -> None:
    rendered = safe_factual_question_surface(
        "approval_documents",
        "批复程序中是否涉及相关审批文件及法规依据",
        target_kind="evidence_or_third_party",
    )

    assert rendered == (
        "批复程序中是否涉及相关审批文件及法规依据",
        "批复程序中是否涉及相关审批文件及法规依据？",
    )


def test_target_coordination_never_splits_lexical_ji_or_he() -> None:
    labels = (
        "公司是否及时发出解除通知",
        "受伤后您是否及时向建筑公司或承包方报告",
        "双方是否和好及恢复共同生活",
    )

    for index, label in enumerate(labels):
        assert visible_target_atomic_units(label) == [label]
        rendered = safe_factual_question_surface(f"lexical_{index}", label)
        assert rendered == (label, f"{label}？")


def test_target_coordination_rejects_incomplete_explicit_units() -> None:
    label = "公司是否以及解除通知的送达日期"

    assert visible_target_atomic_units(label) == []
    assert safe_factual_question_surface("incomplete", label) is None


def test_skill_question_surface_preserves_shared_predicate_actor_coordination() -> None:
    rendered = safe_factual_question_surface(
        "question_handling",
        "招标方和财政部门是否实际处理了质疑事项",
        target_kind="client_fact",
    )

    assert rendered == (
        "招标方和财政部门是否实际处理了质疑事项",
        "招标方和财政部门是否实际处理了质疑事项？",
    )


def test_skill_question_surface_drops_trailing_examples_before_rendering() -> None:
    rendered = safe_factual_question_surface(
        "work_role",
        "你在水产品收购中具体负责哪些工作内容？例如采购、运输、财务等",
        target_kind="client_fact",
    )

    assert rendered == (
        "你在水产品收购中具体负责哪些工作内容",
        "你在水产品收购中具体负责哪些工作内容？",
    )


def test_skill_question_surface_does_not_skip_short_first_coordination_unit() -> None:
    rendered = safe_factual_question_surface(
        "abusive_content",
        "辱骂和贬损的具体内容及使用场景",
        target_kind="client_fact",
    )

    assert rendered == (
        "辱骂和贬损的具体内容及使用场景",
        "关于辱骂和贬损的具体内容及使用场景，请说明您亲历或现有文件能够确认的一项具体事实？",
    )


def test_question_quality_rejects_single_sentence_example_list() -> None:
    action = StructuredAction(
        action_type="ask",
        target_type="fact",
        content="请说明登记情况，包括登记时间、产权比例和抵押状态。",
    )
    assert "multiple_primary_questions" in action_question_quality_violations(action)


def test_question_quality_rejects_presupposed_classification_and_legal_threshold() -> None:
    questions = (
        "对方实施了哪些具体的不正当竞争行为？",
        "您能提供侵权行为持续的具体时间段吗？",
        "相似性是否达到法律认定的实质性相似标准？",
        "您提到的纠纷是否确实属于不正当竞争类型？",
        "关于产品设计是否被抄袭，您能说明具体事实吗？",
        "是否可以确认这是对方直接抄袭了我方的设计？",
    )
    for question in questions:
        assert "question_requests_legal_judgment_from_client" in (
            action_question_quality_violations(
                StructuredAction(action_type="ask", target_type="fact", content=question)
            )
        )


def test_question_quality_allows_reading_classification_from_document() -> None:
    action = StructuredAction(
        action_type="ask",
        target_type="evidence",
        content="行政处罚决定书将哪一项具体行为认定为违法？",
    )
    assert action_question_quality_violations(action) == []


def test_question_quality_distinguishes_contract_responsibility_text_from_legal_opinion() -> None:
    document_questions = (
        "分包合同中是否有关于工资支付责任的特别约定？",
        "分包合同中是否有明确约定工资支付责任由哪一方承担？",
    )
    for question in document_questions:
        assert (
            action_question_quality_violations(
                StructuredAction(action_type="ask", target_type="fact", content=question)
            )
            == []
        )

    direct_opinion = StructuredAction(
        action_type="ask",
        target_type="fact",
        content="您是否应承担工资支付责任？",
    )
    assert "question_requests_legal_judgment_from_client" in (
        action_question_quality_violations(direct_opinion)
    )


def test_misconduct_disjunction_is_split_by_planner_and_action_contracts() -> None:
    from legal_skill_guard.agent.stateful_policy import (
        factual_target_question_safety_violations,
    )

    label = "是否存在伪造证据或虚假陈述的初步证据"
    assert factual_target_question_safety_violations("planned_fact", label) == [
        "multiple_primary_questions"
    ]
    action = StructuredAction(
        action_type="ask",
        target_type="fact",
        content="您是否发现购房人存在伪造证据或虚假陈述的行为？",
    )
    assert "multiple_primary_questions" in action_question_quality_violations(action)


def test_question_quality_allows_single_document_inventory_fact() -> None:
    action = StructuredAction(
        action_type="ask",
        target_type="evidence",
        content="您目前能提供的一份书面材料是什么？",
    )
    assert action_question_quality_violations(action) == []


def test_disclosed_fact_indices_matches_prior_answer_chunks() -> None:
    facts = [
        {"client_belief": "设备租赁单写明应在六月底归还。"},
        {"client_belief": "我没有收到书面续租通知。"},
    ]
    history = [("归还期限是什么？", "设备租赁单写明应在六月底归还。")]
    assert disclosed_fact_indices(facts, history) == {0}


def test_disclosed_fact_indices_ignores_short_shared_boilerplate() -> None:
    facts = [
        {"client_belief": "我按租赁单约定补交了一笔押金。"},
        {"client_belief": "租赁单还写了逾期归还的计费方式。"},
    ]
    history = [("押金呢？", "我按租赁单约定补交了一笔押金。")]
    assert disclosed_fact_indices(facts, history) == {0}


def test_client_repetition_control_uses_exact_selected_id_not_overlapping_text() -> None:
    from tests.legacy_support.client_simulator_protocol35 import ClientSimulator

    simulator = ClientSimulator(
        case_view={
            "facts": [
                {"fact_id": "F1", "client_belief": "先前租赁单写明了设备数量。"},
                *(
                    {"fact_id": f"F{index + 1}", "client_belief": f"无关事实{index}"}
                    for index in range(1, 6)
                ),
                {"fact_id": "F7", "client_belief": "对方迟迟没有返还设备押金。"},
            ]
        },
        persona={"persona_id": "P_WD"},
        model=FactSevenSelector(),  # type: ignore[arg-type]
        prompt_template=("{persona_who}{persona_voice}\n{facts_block}\n{disclosed_fact_ids}"),
        relevance_prompt="判断候选事实是否直接回答问题。",
        generation=GenerationConfig(temperature=0, top_p=1, max_tokens=10, seed=42),
        max_selection_attempts=2,
    )
    simulator.disclosed_fact_ids.add("F1")
    simulator.history.append(("租赁单约定什么？", "按我的理解，先前租赁单写明了设备数量。"))
    response, _ = simulator.respond("押金返还情况？", 42)
    assert "对方迟迟没有返还设备押金" in response.content
    assert "已经说明" not in response.content
    assert simulator.disclosed_fact_ids == {"F1", "F7"}


def test_safe_factual_fallback_prefers_unasked_substantive_unknown() -> None:
    state = StateManager().initial("fallback-policy", "开场", max_turns=6)
    state.facts.append(
        FactSlot(
            fact_id="written_notice",
            label="书面通知内容",
            status="unknown",
            criticality="high",
        )
    )
    action = safe_factual_fallback(state)
    assert action.target_id == "written_notice"
    assert action.action_type == "ask"
    assert "书面通知内容" in action.content


def test_repeated_question_repair_does_not_reselect_withheld_target() -> None:
    manager = StateManager()
    state = manager.initial("withheld-repair", "合同履行发生争议。", max_turns=6)
    state.facts.extend(
        [
            FactSlot(
                fact_id="withheld_payment",
                label="客户是否实际付款",
                status="unknown",
                criticality="high",
            ),
            FactSlot(
                fact_id="delivery_date",
                label="货物实际交付日期",
                status="unknown",
                criticality="high",
            ),
        ]
    )
    state = manager.mark_interaction(
        state,
        turn=1,
        action_type="ask",
        target_id="withheld_payment",
        question="您是否实际付款？",
        response_kind="withheld",
    )

    instruction = policy_repair_instruction(["repeated_question_text"], state)

    assert "本轮不得选择这些目标" in instruction
    assert "当前可直接选择的未问目标：delivery_date（货物实际交付日期）" in instruction
    assert "禁止再选的目标：withheld_payment" in instruction


def test_safe_factual_fallback_never_invents_withheld_retry() -> None:
    manager = StateManager()
    state = manager.initial("withheld-fallback", "合同履行发生争议。", max_turns=6)
    state.facts.append(
        FactSlot(
            fact_id="withheld_payment",
            label="客户是否实际付款？",
            status="unknown",
            criticality="high",
        )
    )
    state = manager.mark_interaction(
        state,
        turn=1,
        action_type="ask",
        target_id="withheld_payment",
        question="您是否实际付款？",
        response_kind="withheld",
    )

    action = safe_factual_fallback(state)

    assert action.action_type == "final"
    assert action.target_id is None


def test_safe_factual_fallback_strips_terminal_question_mark_from_label() -> None:
    state = StateManager().initial("fallback-punctuation", "开场", max_turns=6)
    state.facts.append(
        FactSlot(
            fact_id="social_security",
            label="公司是否持续缴纳社保？",
            status="unknown",
            criticality="high",
        )
    )

    action = safe_factual_fallback(state)

    assert action.content == "公司是否持续缴纳社保？"
    assert action_question_quality_violations(action) == []


def test_safe_factual_fallback_skips_abstract_unknown_labels() -> None:
    state = StateManager().initial("fallback-abstract", "开场", max_turns=6)
    state.facts.extend(
        [
            FactSlot(
                fact_id="dispute_details",
                label="纠纷具体细节",
                status="unknown",
                criticality="high",
            ),
            FactSlot(
                fact_id="dispute_focus",
                label="争议焦点",
                status="unknown",
                criticality="high",
            ),
        ]
    )
    action = safe_factual_fallback(state)
    assert action.target_type == "session"
    assert action.action_type == "abstain"
    assert action.reason == "safe_fallback_no_grounded_unresolved_target"


def test_safe_factual_fallback_skips_legal_basis_unknown_label() -> None:
    state = StateManager().initial("fallback-legal", "开场", max_turns=6)
    state.facts.append(
        FactSlot(
            fact_id="legal_basis",
            label="承担责任的法律依据",
            status="unknown",
            criticality="high",
        )
    )
    action = safe_factual_fallback(state)
    assert action.target_type == "session"
    assert action.action_type == "abstain"
    assert "法律依据" not in action.content


def test_safe_fallback_submits_conditional_memo_when_visible_facts_exist() -> None:
    state = StateManager().initial(
        "fallback-final",
        "我已经收到对方书面解除合同的通知。",
        max_turns=6,
    )
    action = safe_factual_fallback(state)
    assert action.action_type == "final"
    assert action.reason == "safe_fallback_conditional_memo_available"


def test_safe_factual_fallback_skips_semantically_repeated_alias_label() -> None:
    manager = StateManager()
    state = manager.initial("fallback-alias", "开场", max_turns=6)
    state.facts.extend(
        [
            FactSlot(
                fact_id="infringing_behavior",
                label="侵权行为类型",
                status="unknown",
                criticality="high",
            ),
            FactSlot(
                fact_id="infringing_behavior_type",
                label="侵权行为类型",
                status="unknown",
                criticality="high",
            ),
            FactSlot(
                fact_id="specific_action",
                label="对方实施的具体行为",
                status="unknown",
                criticality="high",
            ),
        ]
    )
    state = manager.mark_interaction(
        state,
        turn=1,
        action_type="ask",
        target_id="infringing_behavior",
        question="关于侵权行为类型，请说明一项具体事实？",
    )
    action = safe_factual_fallback(state)
    assert action.target_id == "specific_action"
    assert "侵权行为类型" not in action.content


def test_question_quality_preserves_label_when_fallback_template_is_checked() -> None:
    action = StructuredAction(
        action_type="ask",
        target_type="fact",
        content="关于侵权行为类型，请说明您亲历或现有文件能够确认的具体事实？",
    )
    assert "generic_or_abstract_question" in action_question_quality_violations(action)


def test_safe_factual_fallback_abstains_after_distinct_topics_are_exhausted() -> None:
    state = StateManager().initial("fallback-exhausted", "开场", max_turns=6)
    for turn, question in enumerate(
        (
            "对方最近一次与争议直接相关的具体行动是什么？",
            "您目前能提供的、与争议直接相关的一份书面材料是什么？",
            "目前尚未说明的事实中，哪一次具体通知、决定或实际处理最直接影响了您？",
        ),
        start=1,
    ):
        state = StateManager().mark_interaction(
            state,
            turn=turn,
            action_type="ask",
            target_id=None,
            question=question,
        )
    action = safe_factual_fallback(state)
    assert action.action_type == "abstain"
    assert action.reason == "safe_fallback_no_grounded_unresolved_target"


def test_executable_fallback_rejects_state_defects_but_allows_action_repairs() -> None:
    assert not executable_fallback_can_repair("forbidden_management_facts:client_identity")
    assert not executable_fallback_can_repair("corroborated_without_concrete_evidence:payment")
    assert not executable_fallback_can_repair("state_status_regression:document_content")
    assert executable_fallback_can_repair("multiple_primary_questions")
    assert executable_fallback_can_repair("excessive_phrase_repetition")
    assert not executable_fallback_can_repair("invalid_structured_state")
