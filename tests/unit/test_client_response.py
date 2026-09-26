from __future__ import annotations

import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from legal_skill_guard.environment.client_response import (
    ClientSimulator,
    DisclosureSignals,
    client_fact_attribute_sufficiency_violations,
    client_fact_selection_schema,
    client_generation_request_sha256,
    disclosure_from_signals,
    parse_fact_selection_decision,
)
from legal_skill_guard.inference.openai_client import ChatResponse, GenerationConfig

ROOT = Path(__file__).resolve().parents[2]


def test_frozen_lawyer_and_client_token_budgets_remain_role_specific() -> None:
    roles = yaml.safe_load((ROOT / "configs/models/roles.yaml").read_text())["roles"]

    assert roles["lawyer_policy"]["max_tokens"] == 1200
    assert roles["client_fact_selector"]["max_tokens"] == 2048
    assert roles["client_fact_selector"]["model_id"] == "openai/gpt-oss-20b"
    assert roles["client_fact_selector"]["reasoning_effort"] == "medium"


def test_client_request_hash_binds_the_complete_generation_envelope() -> None:
    messages = [{"role": "user", "content": "测试"}]
    first = GenerationConfig(0.0, 1.0, 100, 42, reasoning_effort="medium")
    second = GenerationConfig(0.0, 1.0, 100, 43, reasoning_effort="medium")

    assert client_generation_request_sha256(
        model="model-a", messages=messages, generation=first
    ) != client_generation_request_sha256(
        model="model-a", messages=messages, generation=second
    )


class QueueClient:
    model = "frozen-test-model"

    def __init__(self, outputs: list[str]) -> None:
        self.outputs = list(outputs)
        self.messages: list[list[dict[str, str]]] = []
        self.generations: list[GenerationConfig] = []

    def generate(self, messages, generation):
        self.messages.append(messages)
        self.generations.append(generation)
        return ChatResponse(
            content=self.outputs.pop(0),
            finish_reason="stop",
            prompt_tokens=10,
            completion_tokens=5,
            raw_id="test",
        )


class LengthThenRouteClient:
    model = "frozen-test-model"

    def __init__(self) -> None:
        self.generations: list[GenerationConfig] = []

    def generate(self, messages, generation):
        self.generations.append(generation)
        if len(self.generations) == 1:
            return ChatResponse(
                content='{"question_actor":"客户","fact_ids":["F1',
                finish_reason="length",
                prompt_tokens=10,
                completion_tokens=generation.max_tokens,
                raw_id="truncated",
            )
        return ChatResponse(
            content=route_output(["F1", "O1"], "F1"),
            finish_reason="stop",
            prompt_tokens=10,
            completion_tokens=20,
            raw_id="repaired",
        )


def route_output(ids: list[str], selected: str | None) -> str:
    return json.dumps(
        {
            "question_actor": "客户",
            "question_event": "测试事件",
            "question_attribute": "测试属性",
            "selected_relation": "direct_answer" if selected else "not_answer",
            "fact_ids": [selected] if selected else [],
        },
        ensure_ascii=False,
    )


def test_route_parser_accepts_explicit_premise_correction() -> None:
    value = json.dumps(
        {
            "question_actor": "对方",
            "question_event": "书面通知",
            "question_attribute": "通知内容",
            "selected_relation": "premise_correction",
            "fact_ids": ["F1"],
        },
        ensure_ascii=False,
    )

    parsed = parse_fact_selection_decision(value, ["F1", "O1"])

    assert parsed is not None
    assert parsed.fact_ids == ["F1"]
    assert parsed.selected_relation == "premise_correction"


def test_length_truncated_selector_repairs_with_low_reasoning_only_on_retry() -> None:
    router = LengthThenRouteClient()
    client = ClientSimulator.from_template_file(
        case_view={
            "id": "c1",
            "opening": "客户来咨询合同争议",
            "facts": [
                {
                    "fact_id": "F1",
                    "client_belief": "对方在2025年2月书面拒绝付款。",
                    "gap_type": "undisputed",
                }
            ],
        },
        persona={"persona_id": "P_WD", "who": {"zh": "测试"}, "voice": {"zh": "简短"}},
        model=router,  # type: ignore[arg-type]
        template_path=ROOT / "configs/prompts/client_fact_selector_zh.txt",
        generation=GenerationConfig(
            temperature=0,
            top_p=1,
            max_tokens=2048,
            seed=42,
            reasoning_effort="medium",
        ),
        max_selection_attempts=2,
    )

    response, _ = client.respond("对方何时书面拒绝付款？", 42)

    assert [item.reasoning_effort for item in router.generations] == ["medium", "low"]
    assert client.last_selection_attempts[0].endswith('["F1')
    assert client.last_selected_fact_ids == ["F1"]
    assert client.last_response_kind == "new_hidden_fact"
    assert client.last_safe_fallback is False
    assert "2025年2月" in response.content


def simulator(
    model: QueueClient,
    persona_id: str = "P_WD",
    disclosure_model: QueueClient | None = None,
) -> ClientSimulator:
    return ClientSimulator.from_template_file(
        case_view={
            "id": "c1",
            "opening": "客户来咨询合同争议",
            "facts": [
                {
                    "fact_id": "F1",
                    "client_belief": "对方在2025年2月书面拒绝付款。",
                    "gap_type": "undisputed",
                }
            ],
        },
        persona={"persona_id": persona_id, "who": {"zh": "测试"}, "voice": {"zh": "简短"}},
        model=model,
        disclosure_model=disclosure_model,
        template_path=ROOT / "configs/prompts/client_fact_selector_zh.txt",
        disclosure_template_path=ROOT / "configs/prompts/client_fact_disclosure_zh.txt",
        generation=GenerationConfig(
            temperature=0,
            top_p=1,
            max_tokens=1200,
            seed=42,
            reasoning_effort="medium",
        ),
        max_selection_attempts=2,
    )


def test_fact_routing_and_resistant_disclosure_use_separate_model_roles() -> None:
    router = QueueClient([route_output(["F1", "O1"], "F1")])
    disclosure = QueueClient(
        [
            json.dumps(
                {
                    "sensitive_personal_misconduct": True,
                    "accusatory_presumption": True,
                    "coercive_pressure": False,
                    "purpose_explained": False,
                }
            )
        ]
    )
    client = simulator(router, persona_id="P_CS", disclosure_model=disclosure)

    client.respond("你是不是故意拒绝付款？", 3)

    assert len(router.messages) == 1
    assert len(disclosure.messages) == 1
    assert client.last_response_kind == "withheld"


def test_one_route_decision_renders_only_the_selected_dataset_fact() -> None:
    model = QueueClient([route_output(["F1", "O1"], "F1")])
    client = simulator(model)

    response, _ = client.respond("对方何时明确拒绝付款？", 7)

    assert len(model.messages) == 1
    assert response.content == "按我的理解，对方在2025年2月书面拒绝付款。"
    assert client.last_response_kind == "new_hidden_fact"
    assert client.last_selected_fact_ids == ["F1"]


def test_irrelevant_history_cannot_change_the_same_routing_request() -> None:
    first_model = QueueClient([route_output(["F1", "O1"], "F1")])
    second_model = QueueClient([route_output(["F1", "O1"], "F1")])
    first = simulator(first_model)
    second = simulator(second_model)
    second.history.append(("无关问题", "现有信息里没有这项具体情况。"))

    _, first_hash = first.respond("对方何时明确拒绝付款？", 11)
    _, second_hash = second.respond("对方何时明确拒绝付款？", 11)

    assert first_model.messages == second_model.messages
    assert first_hash == second_hash


def test_system_owned_routing_question_canonicalizes_paraphrases_but_keeps_history() -> None:
    first_model = QueueClient([route_output(["F1", "O1"], "F1")])
    second_model = QueueClient([route_output(["F1", "O1"], "F1")])
    first = simulator(first_model)
    second = simulator(second_model)

    first_wording = "对方究竟是哪一个月写信拒付的？"
    second_wording = "请说明书面拒绝付款发生的时间。"
    semantic_target = "对方书面拒绝付款的时间"
    _, first_hash = first.respond(
        first_wording,
        11,
        routing_question=semantic_target,
    )
    _, second_hash = second.respond(
        second_wording,
        11,
        routing_question=semantic_target,
    )

    assert first_model.messages == second_model.messages
    assert first_hash == second_hash
    assert first_model.messages[0][-1]["content"] == f"律师本轮问题：{semantic_target}"
    assert first.history[0][0] == first_wording
    assert second.history[0][0] == second_wording


def test_canonical_routing_does_not_replace_wording_seen_by_disclosure_policy() -> None:
    route_first = QueueClient([route_output(["F1", "O1"], "F1")])
    route_second = QueueClient([route_output(["F1", "O1"], "F1")])
    signals = json.dumps(
        {
            "sensitive_personal_misconduct": True,
            "accusatory_presumption": True,
            "coercive_pressure": False,
            "purpose_explained": False,
        }
    )
    disclosure_first = QueueClient([signals])
    disclosure_second = QueueClient([signals])
    first = simulator(route_first, persona_id="P_CS", disclosure_model=disclosure_first)
    second = simulator(route_second, persona_id="P_CS", disclosure_model=disclosure_second)

    first_wording = "你是不是故意书面拒绝付款？"
    second_wording = "请核对是否曾以书面方式拒绝付款。"
    semantic_target = "是否书面拒绝付款"
    first.respond(first_wording, 17, routing_question=semantic_target)
    second.respond(second_wording, 17, routing_question=semantic_target)

    assert route_first.messages == route_second.messages
    assert disclosure_first.messages[0][-1]["content"] == f"律师本轮问题：{first_wording}"
    assert disclosure_second.messages[0][-1]["content"] == f"律师本轮问题：{second_wording}"
    assert first.history[0][0] == first_wording
    assert second.history[0][0] == second_wording


def test_persona_cannot_change_the_same_routing_request_or_hash() -> None:
    direct_model = QueueClient([route_output(["F1", "O1"], None)] * 2)
    resistant_model = QueueClient([route_output(["F1", "O1"], None)] * 2)
    direct = simulator(direct_model, persona_id="P_WD")
    resistant = simulator(resistant_model, persona_id="P_CD")

    _, direct_hash = direct.respond("银行审核人员的姓名和工号是什么？", 13)
    _, resistant_hash = resistant.respond("银行审核人员的姓名和工号是什么？", 13)

    assert direct_model.messages == resistant_model.messages
    assert direct_hash == resistant_hash


def test_route_parser_rejects_incomplete_or_internally_inconsistent_assessments() -> None:
    missing = json.dumps(
        {
            "question_actor": "客户",
            "question_event": "付款",
            "question_attribute": "时间",
            "selected_relation": "not_answer",
            "fact_ids": ["F1"],
        }
    )
    inconsistent = json.loads(route_output(["F1", "O1"], None))
    inconsistent["fact_ids"] = ["F1"]

    assert parse_fact_selection_decision(missing, ["F1", "O1"]) is None
    assert (
        parse_fact_selection_decision(json.dumps(inconsistent), ["F1", "O1"])
        is None
    )


def test_route_parser_rejects_empty_match_with_answer_relation() -> None:
    value = json.loads(route_output(["F1", "O1"], None))
    value["selected_relation"] = "partial_answer"

    assert parse_fact_selection_decision(json.dumps(value), ["F1", "O1"]) is None


def test_current_route_parser_rejects_legacy_fact_id_only_object() -> None:
    assert parse_fact_selection_decision('{"fact_ids":["F1"]}', ["F1", "O1"]) is None


def test_disclosure_is_derived_from_atomic_signals_not_a_free_model_verdict() -> None:
    ordinary = DisclosureSignals(False, True, True, False)
    sensitive_accusation = DisclosureSignals(True, True, False, False)
    sensitive_pressure = DisclosureSignals(True, True, True, False)
    explained = DisclosureSignals(True, True, True, True)

    assert disclosure_from_signals("P_CS", ordinary) == "disclose"
    assert disclosure_from_signals("P_CS", sensitive_accusation) == "withhold"
    assert disclosure_from_signals("P_CD", sensitive_accusation) == "disclose"
    assert disclosure_from_signals("P_CD", sensitive_pressure) == "withhold"
    assert disclosure_from_signals("P_CD", explained) == "disclose"


def test_resistant_persona_can_withhold_only_after_a_fact_has_matched() -> None:
    signals = json.dumps(
        {
            "sensitive_personal_misconduct": True,
            "accusatory_presumption": True,
            "coercive_pressure": True,
            "purpose_explained": False,
        }
    )
    model = QueueClient([route_output(["F1", "O1"], "F1"), signals])
    client = simulator(model, persona_id="P_CD")

    response, _ = client.respond("别绕弯子，你到底故意做没做？", 19)

    assert len(model.messages) == 2
    assert client.last_matched_fact_ids == ["F1"]
    assert client.last_selected_fact_ids == []
    assert client.last_response_kind == "withheld"
    assert "对方在2025年2月" not in response.content


def test_valid_empty_route_is_unavailable_not_a_transport_fallback() -> None:
    model = QueueClient([route_output(["F1", "O1"], None)] * 2)
    client = simulator(model)

    client.respond("银行审核人的工号是什么？", 23)

    assert client.last_response_kind == "unavailable"


def test_exact_question_reuses_first_route_and_cannot_flip_unavailable_to_fact() -> None:
    router = QueueClient(
        [
            route_output(["F1", "O1"], None),
            route_output(["F1", "O1"], None),
            # This third answer would create a false gain if the identical
            # question were sent through the semantic router again.
            route_output(["F1", "O1"], "F1"),
        ]
    )
    client = simulator(router)

    first, _ = client.respond(
        "对方何时书面拒绝付款？",
        42,
        routing_question="书面拒绝付款的具体时间",
    )
    second, _ = client.respond(
        "对方何时书面拒绝付款？",
        42,
        routing_question="问题所指的具体时间",
    )

    assert len(router.messages) == 2
    assert first.content == second.content
    assert client.last_response_kind == "unavailable"
    assert client.last_selected_fact_ids == []
    assert client.last_safe_fallback is False
    assert client.last_route_passed is True
    assert not client.last_safe_fallback


def test_first_empty_route_gets_one_same_router_semantic_recheck() -> None:
    router = QueueClient(
        [
            route_output(["F1", "O1"], None),
            route_output(["F1", "O1"], "F1"),
        ]
    )
    client = simulator(router)

    response, _ = client.respond("对方何时书面拒绝付款？", 42)

    assert len(router.messages) == 2
    assert router.generations[0].reasoning_effort == "medium"
    assert router.generations[1].reasoning_effort == "low"
    assert "再独立复核一次主体、事件和所问属性" in router.messages[1][-1]["content"]
    assert client.last_selected_fact_ids == ["F1"]
    assert client.last_response_kind == "new_hidden_fact"
    assert "2025年2月" in response.content


def test_empty_route_is_rechecked_only_once_even_with_three_attempt_budget() -> None:
    router = QueueClient(
        [
            route_output(["F1", "O1"], None),
            route_output(["F1", "O1"], None),
            # A third vote must never overturn two valid empty decisions.
            route_output(["F1", "O1"], "F1"),
        ]
    )
    client = simulator(router)
    client.max_selection_attempts = 3

    response, _ = client.respond("对方何时书面拒绝付款？", 42)

    assert len(router.messages) == 2
    assert response.content == "现有信息里没有这项具体情况，我需要再核实。"
    assert client.last_response_kind == "unavailable"
    assert client.last_selected_fact_ids == []
    assert [
        item["attribute_gate_disposition"]
        for item in client.last_selection_attempt_records
    ] == ["empty_recheck_requested", "not_applicable"]


def test_valid_empty_route_survives_malformed_or_rejected_optional_recheck() -> None:
    router = QueueClient(
        [
            route_output(["F1", "O1"], None),
            "",
            route_output(["F1", "O1"], "F1"),
        ]
    )
    client = simulator(router)
    client.max_selection_attempts = 3

    response, _ = client.respond("市监局是否正式受理变更申请？", 29)

    assert len(router.messages) == 3
    assert response.content == "现有信息里没有这项具体情况，我需要再核实。"
    assert client.last_response_kind == "unavailable"
    assert client.last_route_passed is True
    assert client.last_safe_fallback is False
    assert client.last_matched_fact_ids == []
    assert client.last_selected_fact_ids == []
    assert client.last_selection_attempt_records[-1][
        "deterministic_compatibility_violations"
    ] == ["formal_acceptance_not_stated"]


def test_attribute_sufficiency_contract_covers_only_literal_requested_fields() -> None:
    examples = [
        (
            "登记申请是否已被市监局正式受理？",
            "市监局认为材料不足，因此没有完成变更登记。",
            "formal_acceptance_not_stated",
        ),
        (
            "房屋是否登记在另一家公司名下？",
            "工作地点挂着另一家公司的名牌。",
            "registration_relation_not_stated",
        ),
        (
            "是否回答了健康告知中的全部询问？",
            "保险公司称客户没有告知慢性支气管炎。",
            "questionnaire_completion_not_stated",
        ),
        (
            "三名股东分别实际缴纳了多少出资？",
            "三名股东首期出资合计一千万元并分别有明确金额。",
            "itemized_amounts_not_stated",
        ),
        (
            "您是通过什么方式申请取消订单的？",
            "我在票务平台购票后及时申请退票。",
            "application_channel_not_stated",
        ),
        (
            "市场禁入决定的上位法依据是什么？",
            "暂行办法是行政机关发布的文件。",
            "legal_basis_not_stated",
        ),
        (
            "招标方和财政部门是否有权处理该类质疑事项？",
            "招标公司审查后维持了原中标结果。",
            "authority_status_not_stated",
        ),
        (
            "您实际使用该标识时所针对的消费者群体是哪些？",
            "多个平台上的消费者和媒体已经用这句话指代特定款香水。",
            "target_audience_not_stated",
        ),
        (
            "请问您与境外客户之间是否存在书面合同？",
            "卖方必须了解买方标准，即使合同和交易习惯从未提及。",
            "instrument_existence_not_stated",
        ),
        (
            "双方在变更抚养关系上是否有过协商？",
            "2022年离婚时约定次子随母亲生活。",
            "negotiation_event_not_stated",
        ),
        (
            "参与交易的关联公司分别叫什么名称？",
            "乙公司与我签约采购碎石供给甲公司。",
            "specific_entity_names_not_stated",
        ),
    ]

    for question, belief, expected in examples:
        assert expected in client_fact_attribute_sufficiency_violations(
            question, belief
        )

    controls = [
        (
            "房屋登记到夫妻双方名下发生在什么时候？",
            "房屋在次月就改成了夫妻两人的名字。",
        ),
        (
            "您通过什么方式申请退款？",
            "我通过手机应用提交了退款申请。",
        ),
        (
            "决定的法律依据是什么？",
            "该决定依据某条例第十条作出。",
        ),
        (
            "该机构是否有权处理这项申请？",
            "授权文件载明该机构有权处理这类申请。",
        ),
        (
            "平台通过什么方式发送续费提醒？",
            "平台通过站内信发送续费提醒。",
        ),
        (
            "这项服务面向哪类目标客户？",
            "这项服务主要面向企业客户。",
        ),
        (
            "该险种的客户群体是哪些？",
            "该险种的客户群体为众包骑手。",
        ),
        (
            "请问双方是否签订过书面合同？",
            "双方没有签订书面合同，订单通过邮件确认。",
        ),
        (
            "员工是否同意续签原劳动合同？",
            "合同到期后公司通知他续签，但他主动拒绝。",
        ),
        (
            "双方最终是否签署了新的书面劳动合同？",
            "合同到期后公司通知他续签，但他主动拒绝。",
        ),
        (
            "双方在变更抚养关系上是否有过协商？",
            "双方曾通过微信协商变更孩子的直接抚养安排。",
        ),
        (
            "参与交易的关联公司分别叫什么名称？",
            "企业名称为华星有限责任公司。",
        ),
    ]
    for question, belief in controls:
        assert client_fact_attribute_sufficiency_violations(question, belief) == []


def test_attribute_insufficient_model_selection_is_audited_contract_failure() -> None:
    invalid = route_output(["F1", "O1"], "F1")
    model = QueueClient([invalid, invalid])
    client = simulator(model)

    response, _ = client.respond("市监局是否正式受理变更申请？", 29)

    assert response.content == "现有信息里没有这项具体情况，我需要再核实。"
    assert client.last_response_kind == "contract_fallback"
    assert client.last_route_passed is False
    assert client.last_route_candidate_fact_id == "F1"
    assert client.last_route_guard_violations == [
        "formal_acceptance_not_stated"
    ]
    assert client.last_matched_fact_ids == []
    assert client.last_selected_fact_ids == []
    assert client.last_safe_fallback


def test_attribute_insufficient_selection_can_be_corrected_by_same_router() -> None:
    model = QueueClient(
        [
            route_output(["F1", "O1"], "F1"),
            route_output(["F1", "O1"], None),
        ]
    )
    client = simulator(model)

    response, _ = client.respond("市监局是否正式受理变更申请？", 29)

    assert response.content == "现有信息里没有这项具体情况，我需要再核实。"
    assert client.last_response_kind == "unavailable"
    assert client.last_route_passed is True
    assert client.last_route_candidate_fact_id is None
    assert client.last_route_guard_violations == []
    assert client.last_matched_fact_ids == []
    assert client.last_selected_fact_ids == []
    assert client.last_safe_fallback is False
    assert len(model.messages) == 2
    assert [item.reasoning_effort for item in model.generations] == ["medium", "low"]
    assert "没有明确陈述本问题所问的具体属性" in model.messages[1][-1]["content"]
    assert model.generations[1].response_schema["properties"]["fact_ids"]["maxItems"] == 0


def test_partial_answer_cannot_bypass_attribute_gate_for_atomic_question() -> None:
    partial = json.loads(route_output(["F1", "O1"], "F1"))
    partial["selected_relation"] = "partial_answer"
    model = QueueClient(
        [
            json.dumps(partial, ensure_ascii=False),
            route_output(["F1", "O1"], None),
        ]
    )
    client = simulator(model)

    response, _ = client.respond("市监局是否正式受理变更申请？", 29)

    assert response.content == "现有信息里没有这项具体情况，我需要再核实。"
    assert client.last_response_kind == "unavailable"
    assert client.last_selected_fact_ids == []
    assert client.last_route_passed is True
    assert client.last_selection_attempt_records[0]["selected_relation"] == "partial_answer"
    assert client.last_selection_attempt_records[0][
        "deterministic_compatibility_violations"
    ] == ["formal_acceptance_not_stated"]
    assert client.last_selection_attempt_records[0]["attribute_gate_disposition"] == (
        "rejected"
    )


def test_partial_answer_cannot_bypass_failed_attribute_gate_for_compound_question() -> None:
    partial = json.loads(route_output(["F1", "O1"], "F1"))
    partial["selected_relation"] = "partial_answer"
    model = QueueClient(
        [
            json.dumps(partial, ensure_ascii=False),
            route_output(["F1", "O1"], None),
        ]
    )
    client = simulator(model)

    response, _ = client.respond(
        "您是否正式提交了变更申请，以及市监局是否已经受理？",
        29,
    )

    assert response.content == "现有信息里没有这项具体情况，我需要再核实。"
    assert client.last_response_kind == "unavailable"
    assert client.last_selected_fact_ids == []
    assert client.last_route_passed is True
    assert client.last_selection_attempt_records[0]["selected_relation"] == "partial_answer"
    assert "formal_acceptance_not_stated" in client.last_selection_attempt_records[0][
        "deterministic_compatibility_violations"
    ]
    assert client.last_selection_attempt_records[0]["attribute_gate_disposition"] == (
        "rejected"
    )


def test_contract_existence_question_cannot_gain_unrelated_contract_belief() -> None:
    """Regression for the false gain observed in the R8 company-law trace."""

    model = QueueClient(
        [
            route_output(["F6", "O1"], "F6"),
            route_output(["F6", "O1"], None),
        ]
    )
    client = ClientSimulator.from_template_file(
        case_view={
            "id": "company_cross_border_regression",
            "opening": "我们向境外客户销售设备后发生质量争议。",
            "facts": [
                {
                    "fact_id": "F6",
                    "client_belief": (
                        "卖方必须主动了解并满足买方所在国一切非强制标准，"
                        "即使合同和交易习惯从未提及。"
                    ),
                    "gap_type": "disputed",
                }
            ],
        },
        persona={"persona_id": "P_WD", "who": {"zh": "客户"}, "voice": {"zh": "简短"}},
        model=model,  # type: ignore[arg-type]
        template_path=ROOT / "configs/prompts/client_fact_selector_zh.txt",
        generation=GenerationConfig(
            temperature=0,
            top_p=1,
            max_tokens=2048,
            seed=42,
            reasoning_effort="medium",
        ),
        max_selection_attempts=2,
    )

    response, _ = client.respond("请问双方是否存在书面合同？", 42)

    assert response.content == "现有信息里没有这项具体情况，我需要再核实。"
    assert client.last_response_kind == "unavailable"
    assert client.last_selected_fact_ids == []
    assert client.last_route_passed is True
    assert len(model.messages) == 2
    assert "F6" in model.messages[1][-1]["content"]


def test_empty_allowed_fact_set_has_a_valid_empty_only_schema() -> None:
    schema = client_fact_selection_schema([])

    Draft202012Validator.check_schema(schema)
    fact_ids = schema["properties"]["fact_ids"]
    assert fact_ids["maxItems"] == 0
    assert "enum" not in fact_ids["items"]
