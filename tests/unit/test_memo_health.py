import pytest

from legal_skill_guard.agent.memo_health import (
    client_position_reversal_violations,
    deterministic_safe_memo,
    drop_question_only_coordinated_negative_examples,
    known_completed_event_recast_as_uncertain_violations,
    known_external_action_recast_as_pending_violations,
    known_temporal_answer_recast_as_unknown_violations,
    memo_health_violations,
    neutralize_client_position_reversals,
    neutralize_known_completed_event_recasts,
    neutralize_known_external_action_recasts,
    neutralize_known_temporal_answer_recasts,
    neutralize_procedural_artifact_acquisition,
    neutralize_unavailable_negative_claims,
    neutralize_withheld_answer_recasts,
    unavailable_negative_claim_violations,
    withheld_answer_recast_violations,
)
from legal_skill_guard.agent.memo_renderer import render_terminal_memo
from legal_skill_guard.inference.openai_client import ChatResponse, GenerationConfig


class DoctrineEchoClient:
    model = "doctrine-echo"

    def generate(self, messages, generation):
        return ChatResponse(
            content=(
                "案情概要\n客户咨询。\n关键事实\n客户称公司欠款。\n"
                "法律问题\n原股东是否承担连带责任？\n风险评估\n尚需核实。\n"
                "下一步建议\n整理文件。\n本分析不替代持证律师的正式意见。"
            ),
            finish_reason="stop",
            prompt_tokens=10,
            completion_tokens=10,
            raw_id="echo",
        )


class NoDisclaimerClient:
    model = "no-disclaimer"

    def generate(self, messages, generation):
        return ChatResponse(
            content=(
                "案情概要\n客户咨询。\n关键事实\n客户称收到通知。\n"
                "法律问题\n责任主体仍需核实。\n风险评估\n目前不能确认结论。\n"
                "下一步建议\n先整理原始文件。"
            ),
            finish_reason="stop",
            prompt_tokens=10,
            completion_tokens=10,
            raw_id="no-disclaimer",
        )


class UngroundedCitationClient:
    model = "ungrounded-citation"

    def generate(self, messages, generation):
        return ChatResponse(
            content=(
                "案情概要\n客户咨询。\n关键事实\n客户称收到通知。\n"
                "法律问题\n需结合《示例法》核实责任。\n风险评估\n目前不能确认结论。\n"
                "下一步建议\n先整理原始文件。"
            ),
            finish_reason="stop",
            prompt_tokens=10,
            completion_tokens=10,
            raw_id="citation",
        )


class UngroundedOffenceClient:
    model = "ungrounded-offence"

    def generate(self, messages, generation):
        return ChatResponse(
            content=(
                "案情概要\n客户咨询劳动争议。\n关键事实\n客户称公司未缴社保。\n"
                "法律问题\n是否构成诈骗罪仍需核实。\n风险评估\n目前不能确认结论。\n"
                "下一步建议\n先整理劳动合同。\n"
                "本分析不替代持证律师的正式意见。"
            ),
            finish_reason="stop",
            prompt_tokens=10,
            completion_tokens=10,
            raw_id="offence",
        )


class UnavailableNegativeClient:
    model = "unavailable-negative"

    def generate(self, messages, generation):
        return ChatResponse(
            content=(
                "案情概要\n客户称丈夫殴打致听觉受损，治疗费由妹妹垫付，"
                "但尚未向公安机关报案或向社区、妇联求助。\n"
                "关键事实\n客户称丈夫殴打致听觉受损。\n"
                "法律问题\n保护路径仍待核实。\n风险评估\n目前不能确认结论。\n"
                "下一步建议\n先补充材料。\n本分析不替代持证律师的正式意见。"
            ),
            finish_reason="stop",
            prompt_tokens=10,
            completion_tokens=10,
            raw_id="unavailable-negative",
        )


class HedgedAnsweredNegativeClient:
    model = "hedged-answered-negative"

    def generate(self, messages, generation):
        return ChatResponse(
            content=(
                "案情概要\n客户咨询许可争议。\n"
                "关键事实\n客户未与行政机关沟通。\n"
                "法律问题\n沟通情况对程序的影响仍待核实。\n"
                "风险评估\n目前不能确认结论。\n"
                "下一步建议\n先整理沟通记录。\n"
                "本分析不替代持证律师的正式意见。"
            ),
            finish_reason="stop",
            prompt_tokens=10,
            completion_tokens=10,
            raw_id="hedged-answered-negative",
        )


class EmptyMemoClient:
    model = "empty-memo"

    def generate(self, messages, generation):
        return ChatResponse(
            content="",
            finish_reason="stop",
            prompt_tokens=10,
            completion_tokens=0,
            raw_id="empty-memo",
        )


class SentenceLocalAttributionRepairClient:
    model = "sentence-local-attribution-repair"

    def __init__(self) -> None:
        self.calls = 0

    def generate(self, messages, generation):
        self.calls += 1
        if self.calls == 1:
            content = (
                "案情概要\n客户咨询政府承诺争议。\n"
                "关键事实\n客户称政府承诺补偿。政府不承担替代责任。\n"
                "法律问题\n责任性质仍待核实。\n风险评估\n目前不能确认结论。\n"
                "下一步建议\n先整理原始文件。\n"
                "本分析不替代持证律师的正式意见。"
            )
        else:
            assert "来源归属以句号为边界" in messages[-1]["content"]
            content = (
                "案情概要\n客户咨询政府承诺争议。\n"
                "关键事实\n客户称政府承诺补偿。据客户转述，政府主张不承担替代责任。\n"
                "法律问题\n责任性质仍待核实。\n风险评估\n目前不能确认结论。\n"
                "下一步建议\n先整理原始文件。\n"
                "本分析不替代持证律师的正式意见。"
            )
        return ChatResponse(
            content=content,
            finish_reason="stop",
            prompt_tokens=10,
            completion_tokens=10,
            raw_id=f"sentence-local-attribution-{self.calls}",
        )


def test_memo_rejects_unseen_specific_law_citation() -> None:
    memo = (
        "案情概要\n客户称有经销争议。\n关键事实\n对方开店。\n法律问题\n"
        "是否违反《反不正当竞争法》并侵犯商业秘密？\n风险评估\n尚需核实。\n"
        "下一步建议\n整理文件。"
    )
    issues = memo_health_violations(memo, "客户说对方开店。")
    assert "ungrounded_law_citation:《反不正当竞争法》" in issues


def test_renderer_repair_requires_sentence_local_source_attribution(tmp_path) -> None:
    prompt = tmp_path / "memo.txt"
    prompt.write_text("开场：{opening}\n对话：{dialogue}", encoding="utf-8")
    client = SentenceLocalAttributionRepairClient()
    memo, _, _, attempts, _, safe_fallback = render_terminal_memo(
        client=client,
        prompt_path=prompt,
        opening="客户咨询政府承诺争议。",
        dialogue=[("政府怎么说？", "政府承诺补偿，但表示不承担替代责任。")],
        unavailable_questions=[],
        generation=GenerationConfig(temperature=0, top_p=1, max_tokens=200, seed=42),
        max_attempts=3,
    )

    assert len(attempts) == 2
    assert attempts[0].health_violations == ["uncalibrated_legal_conclusion"]
    assert attempts[1].health_violations == []
    assert "据客户转述，政府主张不承担替代责任" in memo
    assert safe_fallback is False


def test_renderer_rebuilds_from_visible_record_after_repeated_repair_family(
    tmp_path,
) -> None:
    """A repeated rejected draft must not anchor the final bounded attempt."""

    class StagnatingClient:
        model = "stagnating-analysis-fact"

        def __init__(self) -> None:
            self.calls = 0
            self.roles: list[list[str]] = []

        def generate(self, messages, generation):
            del generation
            self.calls += 1
            self.roles.append([str(item["role"]) for item in messages])
            risk = (
                "客户称其已经付款，责任仍待核实。"
                if self.calls < 3
                else "基于上述尚未独立核验的单方陈述，付款责任仍待核实。"
            )
            return ChatResponse(
                content=(
                    "法律问题\n付款责任仍待核实。\n"
                    f"风险评估\n{risk}\n"
                    "下一步建议\n先核实原始付款材料。\n"
                    "本分析不替代持证律师结合完整材料提供的正式意见。"
                ),
                finish_reason="stop",
                prompt_tokens=10,
                completion_tokens=10,
                raw_id=f"stagnating-{self.calls}",
            )

    prompt = tmp_path / "memo.txt"
    prompt.write_text("开场：{opening}\n对话：{dialogue}", encoding="utf-8")
    client = StagnatingClient()
    memo, _, _, attempts, _, safe_fallback = render_terminal_memo(
        client=client,
        prompt_path=prompt,
        opening="客户咨询付款争议。",
        dialogue=[("是否已经付款？", "我已经付款。")],
        dialogue_response_kinds=["new_hidden_fact"],
        unavailable_questions=[],
        generation=GenerationConfig(temperature=0, top_p=1, max_tokens=200, seed=42),
        max_attempts=3,
    )

    assert [item.health_violations for item in attempts] == [
        ["analysis_fact_attribution_outside_typed_ledger"],
        ["analysis_fact_attribution_outside_typed_ledger"],
        [],
    ]
    assert client.roles == [
        ["user"],
        ["user", "assistant", "user"],
        ["user", "user"],
    ]
    assert "基于上述尚未独立核验的单方陈述" in memo
    assert safe_fallback is False


def test_memo_allows_conditional_analysis_and_optional_procedure() -> None:
    memo = (
        "案情概要\n客户称有合同争议。\n关键事实\n客户称收到通知。\n"
        "法律问题\n责任主体仍需核实。\n风险评估\n若材料属实，可能存在风险，"
        "仍需结合适用法律核实。\n下一步建议\n必要时可考虑提起诉讼。"
        "本分析不替代持证律师的正式意见。"
    )
    assert memo_health_violations(memo, "客户称有合同争议并收到通知。") == []


def test_memo_health_distinguishes_negated_certainty_from_categorical_conclusion() -> None:
    template = (
        "## 案情概要\n客户咨询食品争议。\n"
        "## 关键事实\n客户称卖家被刑事立案。\n"
        "## 法律问题\n民事责任仍待核实。\n"
        "## 风险评估\n{risk}\n"
        "## 下一步建议\n先整理原始文件。\n"
        "本备忘录不替代持证律师结合完整材料提供的正式意见。"
    )
    calibrated = template.format(risk="刑事立案不必然等同于民事责任成立。")
    categorical = template.format(risk="刑事立案必然等同于民事责任成立。")

    assert memo_health_violations(calibrated, "客户称卖家被刑事立案。") == []
    assert "uncalibrated_legal_conclusion" in memo_health_violations(
        categorical, "客户称卖家被刑事立案。"
    )


def test_deterministic_safe_memo_passes_contract() -> None:
    memo = deterministic_safe_memo("客户咨询合同纠纷。", [("有文件吗？", "有一份合同。")])
    assert memo_health_violations(memo, "客户咨询合同纠纷。有一份合同。") == []


def test_deterministic_safe_memo_attributes_client_legal_claim() -> None:
    dialogue = [("您怎么看？", "我认为对方显然已构成侵权。肯定应当承担责任。")]
    memo = deterministic_safe_memo("客户咨询纠纷。", dialogue)
    assert memo.count("客户单方陈述（尚未核验）") == 2
    assert memo_health_violations(memo, "客户咨询纠纷。" + dialogue[0][1]) == []


def test_memo_health_does_not_treat_attributed_counterparty_position_as_advice() -> None:
    memo = (
        "## 案情概要\n客户咨询欠款。\n"
        "## 关键事实\n医院主张因财政审批未完成，故不承担逾期责任。\n"
        "## 法律问题\n该抗辩是否成立仍需核实。\n"
        "## 风险评估\n可能取决于合同约定。\n"
        "## 下一步建议\n先核实原始合同。\n"
        "本备忘录不替代持证律师结合完整材料提供的正式意见。"
    )
    assert memo_health_violations(memo, "医院解释财政审批未完成。") == []


def test_memo_health_distinguishes_prior_procedure_status_check_from_advice() -> None:
    memo = (
        "## 案情概要\n客户咨询姓名变更争议。\n"
        "## 关键事实\n现有程序状态尚未核实。\n"
        "## 法律问题\n救济路径取决于具体行政处理。\n"
        "## 风险评估\n需要核实管辖和期限。\n"
        "## 下一步建议\n先核实是否已申请复议，再由持证律师评估可能路径。\n"
        "本备忘录不替代持证律师结合完整材料提供的正式意见。"
    )
    assert memo_health_violations(memo, "客户咨询姓名变更争议。") == []


def test_memo_health_still_blocks_direct_unqualified_procedure_advice() -> None:
    memo = (
        "## 案情概要\n客户咨询行政争议。\n"
        "## 关键事实\n客户收到处理决定。\n"
        "## 法律问题\n具体程序仍待核实。\n"
        "## 风险评估\n可能存在期限风险。\n"
        "## 下一步建议\n立即申请复议。\n"
        "本备忘录不替代持证律师结合完整材料提供的正式意见。"
    )
    assert "unqualified_procedural_recommendation:申请复议" in memo_health_violations(
        memo, "客户收到处理决定。"
    )


def test_memo_health_allows_procedure_itself_to_be_checked_for_readiness() -> None:
    memo = (
        "## 案情概要\n客户咨询电子数据毁损争议。\n"
        "## 关键事实\n客户称对方删除服务器数据，尚待材料核验。\n"
        "## 法律问题\n可能的保全路径仍待核实。\n"
        "## 风险评估\n是否具备相应条件尚不能确认。\n"
        "## 下一步建议\n先核实证据保全的法域、管辖、程序状态、条件及期限，"
        "再由持证律师评估是否具备启动程序的条件。\n"
        "本备忘录不替代持证律师结合完整材料提供的正式意见。"
    )
    assert memo_health_violations(memo, "客户称对方删除服务器数据。") == []


def test_memo_health_allows_procedure_named_only_as_later_evaluation_path() -> None:
    memo = (
        "## 案情概要\n客户咨询电子数据毁损争议。\n"
        "## 关键事实\n客户称对方删除服务器数据，尚待材料核验。\n"
        "## 法律问题\n可能的保全路径仍待核实。\n"
        "## 风险评估\n是否具备相应条件尚不能确认。\n"
        "## 下一步建议\n建议补充备份记录，以明确法律风险及证据保全路径。"
        "待材料完备后，由持证律师核实法域、管辖、程序状态、适用条件及期限，"
        "再评估是否启动相应程序。\n"
        "本备忘录不替代持证律师结合完整材料提供的正式意见。"
    )
    assert memo_health_violations(memo, "客户称对方删除服务器数据。") == []


def test_memo_health_allows_verifying_existing_procedural_artifacts() -> None:
    memo = (
        "## 案情概要\n客户咨询电子数据毁损争议。\n"
        "## 关键事实\n客户称对方删除服务器数据，尚待材料核验。\n"
        "## 法律问题\n可能的保全路径仍待核实。\n"
        "## 风险评估\n是否具备相应条件尚不能确认。\n"
        "## 下一步建议\n建议客户补充现有司法鉴定报告，并核实已采取的证据保全措施和记录。\n"
        "本备忘录不替代持证律师结合完整材料提供的正式意见。"
    )
    assert memo_health_violations(memo, "客户称对方删除服务器数据。") == []


def test_memo_health_still_blocks_instruction_to_obtain_new_appraisal_report() -> None:
    memo = (
        "## 案情概要\n客户咨询电子数据毁损争议。\n"
        "## 关键事实\n客户称对方删除服务器数据。\n"
        "## 法律问题\n具体路径仍待核实。\n"
        "## 风险评估\n可能存在证据灭失风险。\n"
        "## 下一步建议\n获取电子数据毁损的司法鉴定报告。\n"
        "本备忘录不替代持证律师结合完整材料提供的正式意见。"
    )
    assert "unqualified_procedural_recommendation:司法鉴定" in memo_health_violations(
        memo, "客户称对方删除服务器数据。"
    )


def test_renderer_normalization_recasts_report_acquisition_as_existing_status_check() -> None:
    memo = "## 下一步建议\n获取电子数据毁损的司法鉴定报告及技术资料。"
    normalized, changed = neutralize_procedural_artifact_acquisition(memo)
    assert changed == ["司法鉴定"]
    assert "核实是否已有电子数据毁损的司法鉴定报告" in normalized
    assert "获取电子数据毁损的司法鉴定报告" not in normalized


def test_memo_health_does_not_let_generic_verification_launder_direct_advice() -> None:
    memo = (
        "## 案情概要\n客户咨询电子数据毁损争议。\n"
        "## 关键事实\n客户称对方删除服务器数据，尚待材料核验。\n"
        "## 法律问题\n可能的保全路径仍待核实。\n"
        "## 风险评估\n是否具备相应条件尚不能确认。\n"
        "## 下一步建议\n先核实服务器材料，然后申请证据保全。\n"
        "本备忘录不替代持证律师结合完整材料提供的正式意见。"
    )
    assert "unqualified_procedural_recommendation:证据保全" in memo_health_violations(
        memo, "客户称对方删除服务器数据。"
    )


def test_memo_health_allows_readiness_checks_before_other_procedures() -> None:
    memo = (
        "## 案情概要\n客户咨询合同争议。\n"
        "## 关键事实\n客户称存在仲裁条款，尚待核验。\n"
        "## 法律问题\n争议解决路径仍待核实。\n"
        "## 风险评估\n具体管辖和期限尚不能确认。\n"
        "## 下一步建议\n申请仲裁前先核实管辖、程序状态和期限。\n"
        "本备忘录不替代持证律师结合完整材料提供的正式意见。"
    )
    assert memo_health_violations(memo, "客户称存在仲裁条款。") == []


def test_memo_health_blocks_unretrieved_article_charge_case_number_and_deadline() -> None:
    memo = (
        "## 案情概要\n客户咨询。\n"
        "## 关键事实\n客户称发生争议。\n"
        "## 法律问题\n是否构成诈骗罪仍待核实。\n"
        "## 风险评估\n可能涉及《示例法》第1015条及（2025）示民初123号。\n"
        "## 下一步建议\n可在十五日内申请复议。\n"
        "本备忘录不替代持证律师结合完整材料提供的正式意见。"
    )
    issues = memo_health_violations(memo, "客户称发生争议。")
    assert "ungrounded_law_citation:《示例法》" in issues
    assert "ungrounded_law_article:第1015条" in issues
    assert "ungrounded_case_number:（2025）示民初123号" in issues
    assert "ungrounded_narrow_offense:诈骗罪" in issues
    assert "ungrounded_procedural_deadline:十五日内" in issues


def test_memo_health_allows_broad_criminal_risk_without_naming_an_offence() -> None:
    memo = (
        "## 案情概要\n客户咨询报告真实性。\n"
        "## 关键事实\n客户称存在不真实报告。\n"
        "## 法律问题\n是否可能涉及相关刑事犯罪，单位和个人责任如何区分。\n"
        "## 风险评估\n若属实，可能面临刑事责任，具体罪名仍需检索核实。\n"
        "## 下一步建议\n先核实原始报告和人员分工。\n"
        "本备忘录不替代持证律师结合完整材料提供的正式意见。"
    )
    assert memo_health_violations(memo, "客户称存在不真实报告。") == []


def test_memo_health_does_not_invent_offence_across_an_evidence_list() -> None:
    memo = (
        "## 案情概要\n客户咨询环境刑事风险。\n"
        "## 关键事实\n客户称公司正面临刑事调查。\n"
        "## 法律问题\n是否涉及相关刑事犯罪仍待检索核实。\n"
        "## 风险评估\n具体责任取决于主客观事实及届时适用法律。\n"
        "## 下一步建议\n建议客户补充核实治理产品使用时间、监测数据异常情况、"
        "刑事调查罪名及证据类型、第三方检测记录等关键信息。\n"
        "本备忘录不替代持证律师结合完整材料提供的正式意见。"
    )
    assert memo_health_violations(memo, "客户称公司正面临刑事调查。") == []


def test_memo_health_allows_explicitly_broad_related_offence_category() -> None:
    memo = (
        "## 案情概要\n客户咨询监测报告真实性。\n"
        "## 关键事实\n客户称报告数据不真实。\n"
        "## 法律问题\n是否可能涉及环境污染相关罪名仍待检索。\n"
        "## 风险评估\n若属实，可能面临刑事责任。\n"
        "## 下一步建议\n先核实原始数据和人员分工。\n"
        "本备忘录不替代持证律师结合完整材料提供的正式意见。"
    )
    assert memo_health_violations(memo, "客户称报告数据不真实。") == []


def test_memo_health_allows_conditional_offence_when_visible_conduct_uses_same_stem() -> None:
    memo = (
        "## 案情概要\n客户称参与实施诈骗。\n"
        "## 关键事实\n客户称收取诈骗资金。\n"
        "## 法律问题\n客户是否构成诈骗罪共犯仍待核实。\n"
        "## 风险评估\n可能涉及刑事责任，具体地位取决于分工。\n"
        "## 下一步建议\n先核实分工和资金流向。\n"
        "本备忘录不替代持证律师结合完整材料提供的正式意见。"
    )
    assert memo_health_violations(memo, "客户称参与实施诈骗并收取诈骗资金。") == []


def test_memo_health_blocks_second_offence_without_visible_conduct_stem() -> None:
    memo = (
        "## 案情概要\n客户称参与实施诈骗。\n"
        "## 关键事实\n客户称收取诈骗资金。\n"
        "## 法律问题\n是否构成诈骗罪或掩饰、隐瞒犯罪所得罪仍待核实。\n"
        "## 风险评估\n可能涉及刑事责任。\n"
        "## 下一步建议\n先核实分工和资金流向。\n"
        "本备忘录不替代持证律师结合完整材料提供的正式意见。"
    )
    assert "ungrounded_narrow_offense:掩饰、隐瞒犯罪所得罪" in memo_health_violations(
        memo, "客户称参与实施诈骗并收取诈骗资金。"
    )


def test_memo_health_blocks_categorical_offence_elements_despite_later_caveat() -> None:
    memo = (
        "## 案情概要\n客户称参与实施诈骗。\n"
        "## 关键事实\n客户称收取诈骗资金。\n"
        "## 法律问题\n客户是否构成诈骗罪仍待核实。\n"
        "## 风险评估\n客户行为符合诈骗罪构成要件，但仍需核实具体分工。\n"
        "## 下一步建议\n先核实分工和资金流向。\n"
        "本备忘录不替代持证律师结合完整材料提供的正式意见。"
    )
    assert "uncalibrated_offense_elements_conclusion" in memo_health_violations(
        memo, "客户称参与实施诈骗并收取诈骗资金。"
    )


def test_memo_health_blocks_conditional_elements_for_ungrounded_offence() -> None:
    memo = (
        "## 案情概要\n客户咨询房屋分割。\n"
        "## 关键事实\n客户称房屋婚后登记。\n"
        "## 法律问题\n房屋性质仍需核实。\n"
        "## 风险评估\n是否符合诈骗罪构成要件仍需核实。\n"
        "## 下一步建议\n先整理登记文件。\n"
        "本备忘录不替代持证律师结合完整材料提供的正式意见。"
    )
    assert "ungrounded_narrow_offense:诈骗罪" in memo_health_violations(
        memo, "客户咨询房屋分割，房屋婚后登记。"
    )


def test_memo_health_allows_open_offence_elements_question() -> None:
    memo = (
        "## 案情概要\n客户称参与实施诈骗。\n"
        "## 关键事实\n客户称收取诈骗资金。\n"
        "## 法律问题\n客户是否构成诈骗罪仍待核实。\n"
        "## 风险评估\n是否符合诈骗罪构成要件仍需结合具体分工和法律检索核实。\n"
        "## 下一步建议\n先核实分工和资金流向。\n"
        "本备忘录不替代持证律师结合完整材料提供的正式意见。"
    )
    assert memo_health_violations(
        memo, "客户称参与实施诈骗并收取诈骗资金。"
    ) == []


def test_memo_health_allows_explicit_negation_of_offence_elements_conclusion() -> None:
    memo = (
        "## 案情概要\n客户称报告数据不真实。\n"
        "## 关键事实\n客户称采样方法尚未核实。\n"
        "## 法律问题\n单位和个人刑事责任仍待核实。\n"
        "## 风险评估\n目前无法断言已符合犯罪构成要件。\n"
        "## 下一步建议\n先核实原始报告和人员分工。\n"
        "本备忘录不替代持证律师结合完整材料提供的正式意见。"
    )
    assert memo_health_violations(memo, "客户称报告数据不真实。") == []


def test_memo_health_blocks_absolute_invariance_and_unretrieved_element_list() -> None:
    base = (
        "## 案情概要\n客户称参与实施诈骗。\n"
        "## 关键事实\n客户称使用AI拟声。\n"
        "## 法律问题\n共同犯罪地位仍待核实。\n"
        "## 风险评估\n{risk}\n"
        "## 下一步建议\n先核实分工和资金流向。\n"
        "本备忘录不替代持证律师结合完整材料提供的正式意见。"
    )
    invariance = memo_health_violations(
        base.format(risk="AI技术不影响共犯性质。"), "客户称参与实施诈骗并使用AI拟声。"
    )
    assert "uncalibrated_legal_invariance_conclusion" in invariance
    rule = memo_health_violations(
        base.format(risk="单位犯罪需满足主体资格、主观故意和危害后果等要件。"),
        "客户称参与实施诈骗并使用AI拟声。",
    )
    assert "unretrieved_specific_legal_rule" in rule


def test_memo_health_allows_generic_reference_to_statutory_conditions() -> None:
    memo = (
        "## 案情概要\n客户咨询家庭暴力保护。\n"
        "## 关键事实\n客户称丈夫将其打伤。\n"
        "## 法律问题\n是否可以申请人身保护令仍待核实。\n"
        "## 风险评估\n申请保护令需满足法定条件，尚待结合材料核验。\n"
        "## 下一步建议\n先整理医疗记录和报警材料。\n"
        "本备忘录不替代持证律师结合完整材料提供的正式意见。"
    )
    assert memo_health_violations(memo, "客户称丈夫将其打伤。") == []


def test_memo_health_allows_open_question_about_unspecified_other_conditions() -> None:
    memo = (
        "## 案情概要\n客户称银行主张贷款提前到期。\n"
        "## 关键事实\n客户称一次迟延已经补正。\n"
        "## 法律问题\n该条款是否构成单方解除权，是否需满足其他条件？\n"
        "## 风险评估\n具体法律效果仍待结合合同原文和法律检索核实。\n"
        "## 下一步建议\n先核实合同原文和银行通知。\n"
        "本备忘录不替代持证律师结合完整材料提供的正式意见。"
    )
    assert memo_health_violations(
        memo,
        "客户称银行主张贷款提前到期，一次迟延已经补正。",
    ) == []


def test_memo_health_blocks_single_unretrieved_specific_condition() -> None:
    memo = (
        "## 案情概要\n客户咨询家庭暴力保护。\n"
        "## 关键事实\n客户称丈夫将其打伤。\n"
        "## 法律问题\n是否可以申请人身保护令仍待核实。\n"
        "## 风险评估\n申请保护令必须满足已经报警的条件。\n"
        "## 下一步建议\n先整理医疗记录和报警材料。\n"
        "本备忘录不替代持证律师结合完整材料提供的正式意见。"
    )
    assert "unretrieved_specific_legal_rule" in memo_health_violations(
        memo, "客户称丈夫将其打伤。"
    )


def test_memo_health_rejects_unknown_answers_recast_as_negative_facts() -> None:
    questions = [
        "您是否已经向公安机关报案了？",
        "您是否已经向社区或妇联寻求帮助了？",
    ]
    memo = (
        "案情概要\n客户称遭受家庭暴力，但尚未向公安机关报案或向社区、妇联求助。\n"
        "关键事实\n报案和求助情况尚待核实。\n法律问题\n保护路径仍待核实。\n"
        "风险评估\n目前不能确认结论。\n下一步建议\n先补充材料。\n"
        "本分析不替代持证律师的正式意见。"
    )
    assert unavailable_negative_claim_violations(memo, questions) == [
        "unavailable_answer_recast_as_negative:authority_report",
        "unavailable_answer_recast_as_negative:seek_support",
    ]


def test_memo_health_allows_unknown_status_described_as_pending_verification() -> None:
    questions = ["您是否已经向公安机关报案了？"]
    memo = (
        "案情概要\n客户咨询家庭暴力保护。\n关键事实\n报案情况尚待客户补充核实。\n"
        "法律问题\n保护路径仍待核实。\n风险评估\n目前不能确认结论。\n"
        "下一步建议\n先核实是否已经报案。\n本分析不替代持证律师的正式意见。"
    )
    assert memo_health_violations(memo, "客户称遭丈夫殴打。", questions) == []


def test_unavailable_document_content_is_not_recast_as_document_omission() -> None:
    question = "您提交的医疗证明文件中具体列出了哪些诊断记录？"
    memo = (
        "案情概要\n客户咨询保险理赔。\n"
        "关键事实\n据客户转述，其医疗证明文件未具体列明诊断记录。\n"
        "法律问题\n拒赔依据仍待核实。\n风险评估\n目前不能确认结论。\n"
        "下一步建议\n先补充材料。\n本分析不替代持证律师的正式意见。"
    )
    issues = memo_health_violations(
        memo,
        "现有信息里没有这项具体情况，我需要再核实。",
        [question],
        [(question, "现有信息里没有这项具体情况，我需要再核实。")],
    )
    assert "unavailable_answer_recast_as_negative:document_content" in issues
    normalized, changes = neutralize_unavailable_negative_claims(memo, [question])
    assert changes == ["document_content"]
    assert "未具体列明" not in normalized
    assert "文件所载具体内容尚待客户补充核实" in normalized

    submission_claim = memo.replace(
        "其医疗证明文件未具体列明诊断记录",
        "客户未提交相关医疗证明文件",
    )
    submission_issues = memo_health_violations(
        submission_claim,
        "现有信息里没有这项具体情况，我需要再核实。",
        [question],
        [(question, "现有信息里没有这项具体情况，我需要再核实。")],
    )
    assert "unavailable_answer_recast_as_negative:document_submission" in (
        submission_issues
    )
    normalized_submission, submission_changes = neutralize_unavailable_negative_claims(
        submission_claim, [question]
    )
    assert submission_changes == ["document_submission"]
    assert "未提交" not in normalized_submission


def test_unavailable_medical_document_does_not_erase_grounded_questionnaire_content() -> None:
    question = "您申请理赔时提交的医疗证明文件中，具体包含哪些诊断记录？"
    grounded = "客户称投保时的电子健康告知未列明慢性支气管炎。"
    unsupported = "客户称理赔材料中未包含慢性支气管炎诊断记录。"

    assert unavailable_negative_claim_violations(grounded, [question]) == []
    assert neutralize_unavailable_negative_claims(grounded, [question]) == (
        grounded,
        [],
    )
    assert unavailable_negative_claim_violations(unsupported, [question]) == [
        "unavailable_answer_recast_as_negative:document_content"
    ]


def test_conditional_and_open_question_negations_remain_legal_analysis() -> None:
    unavailable = ["投保时是否存在被询问病史但未告知的情况？"]
    calibrated = (
        "法律问题\n保险公司拒赔所依据的未告知病史是否属于询问范围？\n"
        "风险评估\n若该病史未被询问，客户是否仍需申报尚待核实。"
    )

    assert unavailable_negative_claim_violations(calibrated, unavailable) == []
    assert neutralize_unavailable_negative_claims(calibrated, unavailable) == (
        calibrated,
        [],
    )


def test_memo_health_rejects_reversing_client_obligation_position() -> None:
    dialogue = [
        (
            "投保时是否告知过既往病史？",
            "按我的理解，即使健康告知没有问到，我也可能负有主动申报既往病史的义务。",
        )
    ]
    reversed_memo = (
        "案情概要\n客户咨询保险理赔，客户认为无需主动申报既往病史。\n"
        "关键事实\n客户称电子健康告知没有问到该病史。\n"
        "法律问题\n告知范围仍待核实。\n风险评估\n目前不能确认结论。\n"
        "下一步建议\n先核对保单。\n本分析不替代持证律师的正式意见。"
    )
    assert client_position_reversal_violations(reversed_memo, dialogue) == [
        "client_position_reversed:申报"
    ]
    assert "client_position_reversed:申报" in memo_health_violations(
        reversed_memo,
        dialogue[0][1],
        [],
        dialogue,
    )
    normalized, changes = neutralize_client_position_reversals(
        reversed_memo, dialogue
    )
    assert changes == ["申报"]
    assert "认为无需主动申报" not in normalized
    assert "可能负有主动申报既往病史的义务" in normalized
    assert client_position_reversal_violations(normalized, dialogue) == []


def test_memo_health_rejects_erasing_explicit_client_temporal_relation() -> None:
    dialogue = [
        (
            "您何时患有慢性支气管炎？",
            "按我的理解，我投保前患有慢性支气管炎。",
        )
    ]
    recast_unknown = (
        "案情概要\n客户咨询保险理赔。\n"
        "关键事实\n客户称患有慢性支气管炎，但未明确该病史是否在投保时已经存在。\n"
        "法律问题\n告知范围仍待核实。\n风险评估\n目前不能确认结论。\n"
        "下一步建议\n先核对病历。\n本分析不替代持证律师的正式意见。"
    )
    assert known_temporal_answer_recast_as_unknown_violations(
        recast_unknown, dialogue
    ) == ["known_temporal_answer_recast_as_unknown:投保"]
    assert "known_temporal_answer_recast_as_unknown:投保" in memo_health_violations(
        recast_unknown,
        dialogue[0][1],
        [],
        dialogue,
    )
    normalized, changes = neutralize_known_temporal_answer_recasts(
        recast_unknown, dialogue
    )
    assert changes == ["投保"]
    assert "未明确该病史是否在投保时已经存在" not in normalized
    assert "投保前患有慢性支气管炎" in normalized
    assert known_temporal_answer_recast_as_unknown_violations(normalized, dialogue) == []


def test_independent_verification_does_not_erase_client_temporal_statement() -> None:
    dialogue = [
        (
            "您何时患有慢性支气管炎？",
            "按我的理解，我投保前患有慢性支气管炎。",
        )
    ]
    calibrated = (
        "案情概要\n客户咨询保险理赔。\n"
        "关键事实\n客户称其投保前患有慢性支气管炎，该陈述尚待病历独立核验。\n"
        "法律问题\n告知范围仍待核实。\n风险评估\n目前不能确认结论。\n"
        "下一步建议\n先核对病历。\n本分析不替代持证律师的正式意见。"
    )
    assert known_temporal_answer_recast_as_unknown_violations(calibrated, dialogue) == []


def test_unavailable_document_issuance_is_not_recast_as_nonissuance() -> None:
    question = "孩子受伤后是否去医院就诊，医院出具了哪些伤情诊断证明？"
    memo = (
        "案情概要\n客户咨询抚养争议。\n"
        "关键事实\n据客户转述，就医治疗情况尚待客户补充核实，医院未出具诊断证明。\n"
        "法律问题\n相关事实的法律影响仍待核实。\n风险评估\n目前不能确认结论。\n"
        "下一步建议\n先补充现有材料。\n本分析不替代持证律师的正式意见。"
    )
    issues = memo_health_violations(
        memo,
        "现有信息里没有这项具体情况，我需要再核实。",
        [question],
        [(question, "现有信息里没有这项具体情况，我需要再核实。")],
    )
    assert "unavailable_answer_recast_as_negative:document_issuance" in issues
    normalized, changes = neutralize_unavailable_negative_claims(memo, [question])
    assert "document_issuance" in changes
    assert "医院未出具" not in normalized
    assert "文件出具或开具情况尚待客户补充核实" in normalized


def test_hospital_examination_wording_is_treated_as_medical_status() -> None:
    question = "孩子受伤后是否去医院检查，医院出具的诊断证明写了什么？"
    memo = (
        "案情概要\n客户咨询抚养争议。\n"
        "关键事实\n客户称孩子受伤后未就医，诊断证明情况尚待核实。\n"
        "法律问题\n相关影响仍待核实。\n风险评估\n目前不能确认结论。\n"
        "下一步建议\n先整理现有材料。\n本分析不替代持证律师的正式意见。"
    )
    assert "unavailable_answer_recast_as_negative:medical_treatment" in (
        unavailable_negative_claim_violations(memo, [question])
    )
    normalized, changes = neutralize_unavailable_negative_claims(memo, [question])
    assert "medical_treatment" in changes
    assert "未就医" not in normalized
    assert "就医治疗情况尚待客户补充核实" in normalized


def test_unavailable_witness_status_is_not_recast_as_no_witness() -> None:
    question = "是否有邻居、亲属或其他人能够证明孩子受伤的经过及继父的行为？"
    memo = (
        "案情概要\n客户咨询抚养争议。\n"
        "关键事实\n据客户转述，尚无邻居、亲属或其他人能证明孩子受伤经过。\n"
        "法律问题\n证明情况仍待核实。\n风险评估\n目前不能确认结论。\n"
        "下一步建议\n先补充现有材料。\n本分析不替代持证律师的正式意见。"
    )
    issues = unavailable_negative_claim_violations(memo, [question])
    assert "unavailable_answer_recast_as_negative:witness_availability" in issues
    normalized, changes = neutralize_unavailable_negative_claims(memo, [question])
    assert "witness_availability" in changes
    assert "尚无邻居" not in normalized
    assert "证人或其他证明来源情况尚待客户补充核实" in normalized


def test_bare_no_witness_wording_is_also_an_unsupported_negative() -> None:
    question = "是否有邻居或亲属能够证明孩子受伤的具体经过？"
    memo = "据客户转述，无邻居或亲属能证明孩子受伤经过。"

    assert unavailable_negative_claim_violations(memo, [question]) == [
        "unavailable_answer_recast_as_negative:witness_availability"
    ]
    normalized, changes = neutralize_unavailable_negative_claims(memo, [question])
    assert changes == ["witness_availability"]
    assert "无邻居" not in normalized


def test_generic_unknown_negative_overlap_catches_unlisted_client_fact() -> None:
    question = "孩子是否表达过对未来抚养安排的真实意愿？"
    memo = "客户称孩子未表达对未来抚养安排的真实意愿。"

    assert unavailable_negative_claim_violations(memo, [question]) == [
        "unavailable_answer_recast_as_negative:generic_question_overlap"
    ]
    normalized, changes = neutralize_unavailable_negative_claims(memo, [question])
    assert changes == ["generic_question_overlap"]
    assert "未表达" not in normalized
    assert "该未获回答问题所涉事实尚待客户补充核实" in normalized


def test_explicit_unresolved_question_entry_is_not_a_negative_fact_assertion() -> None:
    question = (
        "您投保前是否患有慢性支气管炎或其他被健康告知书询问过的疾病，"
        "但未在投保时告知保险公司？"
    )
    pending_entry = f"- 待向客户补充核实：{question}"

    assert unavailable_negative_claim_violations(pending_entry, [question]) == []
    assert unavailable_negative_claim_violations(
        "客户投保前患有慢性支气管炎，但未在投保时告知保险公司。",
        [question],
    ) == ["unavailable_answer_recast_as_negative:disclosure"]


def test_exact_answered_statement_outranks_related_unavailable_negative_warning() -> None:
    unavailable_question = (
        "投保前您是否患有慢性支气管炎，但未在健康告知中披露？"
    )
    answered_question = "保险公司拒赔时具体指出了什么理由？"
    answered = (
        "保险公司的拒赔理由是我投保时没有告知慢性支气管炎，"
        "并称这一情况严重影响其承保决定。"
    )
    memo_sentence = f"据客户陈述，{answered}"
    dialogue = [
        (unavailable_question, "现有信息里没有这项具体情况，我需要再核实。"),
        (answered_question, answered),
    ]

    assert unavailable_negative_claim_violations(
        memo_sentence,
        [unavailable_question],
    ) == ["unavailable_answer_recast_as_negative:disclosure"]
    assert unavailable_negative_claim_violations(
        memo_sentence,
        [unavailable_question],
        dialogue,
    ) == []


def test_typed_deterministic_fallback_keeps_grounded_negative_and_unknown_separate(
    tmp_path,
) -> None:
    prompt = tmp_path / "memo.txt"
    prompt.write_text("开场：{opening}\n对话：{dialogue}", encoding="utf-8")
    dialogue = [
        (
            "投保时的电子健康告知书具体包含哪些病史询问项目？",
            "电子健康告知列出了疾病或症状，但其中没有慢性支气管炎。",
        ),
        (
            "您投保前是否患有慢性支气管炎，但未在投保时告知保险公司？",
            "现有信息里没有这项具体情况，我需要再核实。",
        ),
    ]

    memo, _, _, attempts, _, safe_fallback = render_terminal_memo(
        client=EmptyMemoClient(),
        prompt_path=prompt,
        opening="客户投保防癌险后遭拒赔。",
        dialogue=dialogue,
        unavailable_questions=[dialogue[1][0]],
        dialogue_response_kinds=["new_hidden_fact", "unavailable"],
        generation=GenerationConfig(temperature=0, top_p=1, max_tokens=100, seed=42),
        max_attempts=1,
    )

    assert len(attempts) == 1
    assert safe_fallback is True
    assert "其中没有慢性支气管炎" in memo
    assert "待客户补充核实的问题：您投保前是否患有慢性支气管炎" in memo
    assert memo_health_violations(
        memo,
        "客户投保防癌险后遭拒赔。" + "".join(answer for _, answer in dialogue),
        [dialogue[1][0]],
        dialogue,
    ) == []


def test_generic_unknown_negative_overlap_does_not_match_shared_case_object() -> None:
    question = "是否有邻居能够证明孩子受伤的经过？"
    unrelated = "客户未向医院提供孩子受伤后的检查材料。"

    assert unavailable_negative_claim_violations(unrelated, [question]) == []


def test_withheld_answer_cannot_be_recast_as_ignorance_or_client_fact() -> None:
    question = "您是否在工作期间签署过一份关于改领补助的协议？"
    for memo in (
        "关键事实\n客户称其是否签署改领补助协议尚不清楚。\n法律问题\n协议效力待核实。",
        "关键事实\n客户称其在工作期间签署过改领补助协议。\n法律问题\n协议效力待核实。",
    ):
        assert withheld_answer_recast_violations(memo, [question]) == [
            "withheld_answer_recast_as_known_or_unavailable"
        ]
        normalized, changes = neutralize_withheld_answer_recasts(memo, [question])
        assert changes == ["withheld_status"]
        assert "客户本轮暂未披露该问题所涉事实，该问题仍开放" in normalized


def test_withheld_illness_question_does_not_erase_disclosed_questionnaire_content() -> None:
    question = "您投保前是否患有慢性支气管炎，但未在投保时告知保险公司？"
    disclosed = "客户称投保时电子健康告知书未列明慢性支气管炎。"
    recast = "客户称其投保前未患慢性支气管炎。"

    assert withheld_answer_recast_violations(disclosed, [question]) == []
    assert neutralize_withheld_answer_recasts(disclosed, [question]) == (
        disclosed,
        [],
    )
    assert withheld_answer_recast_violations(recast, [question]) == [
        "withheld_answer_recast_as_known_or_unavailable"
    ]


def test_memo_preserves_reported_completed_external_action() -> None:
    dialogue = [
        (
            "孩子受伤后您采取了什么措施？",
            "我探望时发现孩子受伤并报警，公安已经查明继父两次用物品殴打孩子。",
        )
    ]
    recast = (
        "案情概要\n客户咨询抚养争议。\n"
        "关键事实\n客户称继父存在殴打行为，但尚待公安机关核实。\n"
        "法律问题\n相关事实的法律影响仍待核实。\n风险评估\n目前不能确认结论。\n"
        "下一步建议\n先核对现有材料。\n本分析不替代持证律师的正式意见。"
    )
    assert known_external_action_recast_as_pending_violations(recast, dialogue) == [
        "known_external_action_recast_as_pending:公安机关"
    ]
    assert "known_external_action_recast_as_pending:公安机关" in memo_health_violations(
        recast, dialogue[0][1], [], dialogue
    )
    normalized, changes = neutralize_known_external_action_recasts(recast, dialogue)
    assert changes == ["公安机关"]
    assert "公安已经查明继父两次用物品殴打孩子" in normalized
    assert "该陈述及相关材料尚未独立核验" in normalized
    assert "尚待公安机关核实" not in normalized


def test_independent_verification_does_not_reverse_external_action() -> None:
    dialogue = [
        (
            "警方如何处理？",
            "公安已经查明继父两次用物品殴打孩子。",
        )
    ]
    calibrated = (
        "客户称公安已经查明继父两次用物品殴打孩子；"
        "该客户陈述及相关材料尚待独立核验。"
    )
    assert known_external_action_recast_as_pending_violations(calibrated, dialogue) == []


def test_memo_preserves_reported_completed_adverse_disposition() -> None:
    dialogue = [
        (
            "申请变更抚养关系的具体事由是什么？",
            "继父已经被治安处罚，证明这不是普通管教，而是造成实际伤害的暴力行为。",
        )
    ]
    recast = (
        "案情概要\n客户咨询抚养争议。\n"
        "关键事实\n客户称继父实施过暴力行为。\n"
        "法律问题\n相关影响仍待核实。\n"
        "风险评估\n客户称继父施暴行为可能构成治安处罚。\n"
        "下一步建议\n先整理现有材料。\n本分析不替代持证律师的正式意见。"
    )
    issue = "known_completed_event_recast_as_uncertain:治安处罚"
    assert known_completed_event_recast_as_uncertain_violations(recast, dialogue) == [
        issue
    ]
    assert issue in memo_health_violations(recast, dialogue[0][1], [], dialogue)
    normalized, changes = neutralize_known_completed_event_recasts(recast, dialogue)
    assert changes == ["治安处罚"]
    assert "继父已经被治安处罚" in normalized
    assert "该陈述及相关材料尚未独立核验" in normalized
    assert "可能构成治安处罚" not in normalized


def test_independent_verification_does_not_downgrade_completed_event() -> None:
    dialogue = [("是否已有处罚？", "继父已经被治安处罚。")]
    calibrated = "客户称继父已经被治安处罚；该陈述及处罚材料尚待独立核验。"
    assert known_completed_event_recast_as_uncertain_violations(calibrated, dialogue) == []


def test_renderer_replays_real_memo_fidelity_failure_without_fallback(tmp_path) -> None:
    """Regression replay from run12/lsg_cn_0006/P_CD, not a synthetic shortcut."""

    bad_memo = (
        "**案情概要**\n客户称离婚后孩子受伤，现已申请变更直接抚养关系。\n\n"
        "**关键事实**\n客户称其探望时发现孩子受伤并报警，公安查明继父两次用物品"
        "殴打孩子。据客户转述，孩子受伤后未就医，医院未出具诊断证明。"
        "客户称孩子七岁并愿与客户生活。客户称动手的是继父，母亲没有制止。"
        "据客户转述，尚无邻居、亲属或其他人能证明孩子受伤经过。\n\n"
        "**法律问题**\n相关事实的法律影响仍待核实。\n\n"
        "**风险评估**\n客户称继父存在殴打行为，但尚待公安机关核实。\n\n"
        "**下一步建议**\n先整理现有材料。\n"
        "本备忘录仅基于客户单方陈述作研究性初步分析，不替代持证律师的正式意见。"
    )

    class ReplayMemoClient:
        model = "run12-replay"

        def generate(self, messages, generation):
            return ChatResponse(
                content=bad_memo,
                finish_reason="stop",
                prompt_tokens=10,
                completion_tokens=10,
                raw_id="run12-replay",
            )

    questions_and_answers = [
        (
            "孩子受伤的具体原因是什么？",
            "我探望时发现孩子受伤并报警，公安已经查明继父两次用物品殴打孩子。",
        ),
        (
            "孩子受伤后是否去医院就诊，医院出具了哪些伤情诊断证明？",
            "这件事我现在确实不知道，不能凭空说。",
        ),
        ("孩子是否表达过真实意愿？", "孩子七岁，明确表示愿意跟我生活。"),
        ("您申请变更抚养关系的具体事由是什么？", "动手的是继父，母亲没有制止。"),
        (
            "是否有邻居、亲属或其他人能够证明孩子受伤经过？",
            "这件事我现在确实不知道，不能凭空说。",
        ),
    ]
    prompt = tmp_path / "memo.txt"
    prompt.write_text("开场：{opening}\n对话：{dialogue}", encoding="utf-8")
    memo, _, _, attempts, _, safe_fallback = render_terminal_memo(
        client=ReplayMemoClient(),
        prompt_path=prompt,
        opening="孩子受伤，已申请变更直接抚养关系。",
        dialogue=questions_and_answers,
        unavailable_questions=[questions_and_answers[1][0], questions_and_answers[4][0]],
        generation=GenerationConfig(temperature=0, top_p=1, max_tokens=400, seed=42),
        max_attempts=2,
    )

    assert len(attempts) == 1
    assert attempts[0].health_violations == []
    assert safe_fallback is False
    assert "未就医" not in memo
    assert "医院未出具" not in memo
    assert "尚无邻居" not in memo
    assert "尚待公安机关核实" not in memo
    assert "公安已经查明继父两次用物品殴打孩子" in memo
    assert "该陈述及相关材料尚未独立核验" in memo
    assert {
        "neutralize_unavailable_negative_claims:medical_treatment,document_issuance,witness_availability",
        "neutralize_known_external_action_recasts:公安机关",
    }.issubset(set(attempts[0].deterministic_changes))


def test_memo_health_does_not_cross_match_unrelated_negative_subject() -> None:
    assert unavailable_negative_claim_violations(
        "医院付款情况待核实；客户尚未支付律师费用。",
        ["医院是否已经支付货款？"],
    ) == []


def test_unavailable_notice_does_not_erase_grounded_health_disclosure() -> None:
    question = "您是否收到保险公司出具的正式拒赔通知书？"
    grounded_disclosure = "保险公司称客户投保时没有告知慢性支气管炎。"
    assert unavailable_negative_claim_violations(
        grounded_disclosure, [question]
    ) == []
    assert neutralize_unavailable_negative_claims(
        grounded_disclosure, [question]
    ) == (grounded_disclosure, [])

    unsupported_delivery = "客户没有收到保险公司出具的正式拒赔通知书。"
    assert unavailable_negative_claim_violations(
        unsupported_delivery, [question]
    ) == ["unavailable_answer_recast_as_negative:notice"]


def test_typed_fact_ledger_preserves_known_insurance_facts_after_safety_rewrite(
    tmp_path,
) -> None:
    class MixedInsuranceMemoClient:
        model = "mixed-insurance-memo"

        def generate(self, messages, generation):
            return ChatResponse(
                content=(
                    "案情概要\n客户通过互联网投保防癌险后遭拒赔。\n"
                    "关键事实\n投保前疾病情况、理赔医疗文件及诊断时间线均待"
                    "客户补充核实。\n"
                    "法律问题\n拒赔理由是否成立仍待核实。\n"
                    "风险评估\n目前不能确认结论。\n"
                    "下一步建议\n先核实原始文件。\n"
                    "本分析不替代持证律师的正式意见。"
                ),
                finish_reason="stop",
                prompt_tokens=10,
                completion_tokens=10,
                raw_id="mixed-insurance-memo",
            )

    dialogue = [
        (
            "投保时的电子健康告知书具体包含哪些病史询问项目？",
            "电子健康告知列出了需要回答的疾病、体征或症状，但其中没有慢性支气管炎。",
        ),
        (
            "您投保前是否患有慢性支气管炎或其他被健康告知书询问过的疾病，但未在投保时告知保险公司？",
            "现有信息里没有这项具体情况，我需要再核实。",
        ),
        (
            "保险公司拒赔时具体指出您未在投保前告知哪些既往病史？",
            "保险公司的拒赔理由是我投保时没有告知慢性支气管炎。",
        ),
        (
            "您申请理赔时提交的医疗证明文件中，具体包含哪些关于慢性支气管炎的诊断记录？",
            "现有信息里没有这项具体情况，我需要再核实。",
        ),
        (
            "您确诊慢性支气管炎的具体时间与投保行为在时间顺序上是如何关联的？",
            "现有信息里没有这项具体情况，我需要再核实。",
        ),
    ]
    prompt = tmp_path / "memo.txt"
    prompt.write_text("开场：{opening}\n对话：{dialogue}", encoding="utf-8")
    memo, _, _, attempts, _, safe_fallback = render_terminal_memo(
        client=MixedInsuranceMemoClient(),
        prompt_path=prompt,
        opening="客户投保防癌险后遭拒赔。",
        dialogue=dialogue,
        unavailable_questions=[dialogue[1][0], dialogue[3][0], dialogue[4][0]],
        dialogue_response_kinds=[
            "new_hidden_fact",
            "unavailable",
            "new_hidden_fact",
            "unavailable",
            "unavailable",
        ],
        generation=GenerationConfig(temperature=0, top_p=1, max_tokens=300, seed=42),
        max_attempts=2,
    )

    assert safe_fallback is False
    assert attempts[0].health_violations == []
    assert "render_typed_fact_ledger" in attempts[0].deterministic_changes
    assert "结构化会话事实状态（确定性记录）" in memo
    assert "其中没有慢性支气管炎" in memo
    assert "拒赔理由是我投保时没有告知慢性支气管炎" in memo
    assert "待客户补充核实的问题：您投保前是否患有慢性支气管炎" in memo


def test_unavailable_work_time_does_not_attach_unrelated_nonrenewal_negation() -> None:
    question = "劳动合同到期后，该员工实际继续工作的具体时间段是怎样的？"
    calibrated = (
        "若员工实际继续工作且未续签合同，可能形成事实劳动关系；"
        "员工主张是否成立尚待核实实际工作时间。"
    )
    assert unavailable_negative_claim_violations(calibrated, [question]) == []
    assert neutralize_unavailable_negative_claims(calibrated, [question]) == (
        calibrated,
        [],
    )

    unsupported = "客户称员工在合同到期后并未继续工作。"
    assert unavailable_negative_claim_violations(unsupported, [question]) == [
        "unavailable_answer_recast_as_negative:work_or_performance"
    ]


def test_unavailable_promise_content_does_not_erase_visible_nonperformance() -> None:
    question = "政府方面承诺的具体内容是什么？"
    for grounded_nonperformance in (
        "客户称政府后续未兑现承诺。",
        "客户称政府后续未履行承诺。",
    ):
        assert unavailable_negative_claim_violations(
            grounded_nonperformance, [question]
        ) == []
        assert neutralize_unavailable_negative_claims(
            grounded_nonperformance, [question]
        ) == (grounded_nonperformance, [])

    unsupported_nonexistence = "客户称政府没有承诺给予补偿。"
    assert unavailable_negative_claim_violations(
        unsupported_nonexistence, ["政府是否承诺给予补偿？"]
    ) == ["unavailable_answer_recast_as_negative:agreement"]


def test_lack_of_consent_does_not_negate_the_grounded_use_event() -> None:
    question = "您是否主动向该软件提供身份信息用于其功能的使用？"
    for grounded_use in (
        "软件未经同意使用我的姓名和肖像创设AI角色。",
        "软件未获同意使用我的姓名和肖像创设AI角色。",
        "软件未取得授权使用我的姓名和肖像创设AI角色。",
    ):
        assert unavailable_negative_claim_violations(grounded_use, [question]) == []
        assert neutralize_unavailable_negative_claims(grounded_use, [question]) == (
            grounded_use,
            [],
        )

    unsupported_negative = "软件并未使用我的姓名和肖像。"
    assert unavailable_negative_claim_violations(unsupported_negative, [question]) == [
        "unavailable_answer_recast_as_negative:work_or_performance"
    ]


def test_memo_health_neutralizes_only_bad_clause_and_preserves_visible_facts() -> None:
    memo = (
        "客户称丈夫殴打致听觉受损，治疗费由妹妹垫付，但尚未向公安机关报案或向社区、妇联求助。"
    )
    normalized, changes = neutralize_unavailable_negative_claims(
        memo,
        [
            "您是否已经向公安机关报案了？",
            "您是否已经向社区或妇联寻求帮助了？",
        ],
    )
    assert changes == ["authority_report", "seek_support"]
    assert "丈夫殴打致听觉受损" in normalized
    assert "治疗费由妹妹垫付" in normalized
    assert "报案或向有关机关报告的情况" in normalized
    assert "向相关机构求助的情况" in normalized
    assert "尚待客户补充核实" in normalized
    assert "尚未向公安机关报案" not in normalized


def test_shared_renderer_allows_conditional_legal_issue_without_specific_citation(
    tmp_path,
) -> None:
    prompt = tmp_path / "memo.txt"
    prompt.write_text("开场：{opening}\n对话：{dialogue}", encoding="utf-8")
    memo, _, _, attempts, _, safe_fallback = render_terminal_memo(
        client=DoctrineEchoClient(),
        prompt_path=prompt,
        opening="客户咨询公司欠款。",
        dialogue=[("原股东是否承担连带责任？", "我不知道。")],
        unavailable_questions=["原股东是否承担连带责任？"],
        generation=GenerationConfig(temperature=0, top_p=1, max_tokens=100, seed=42),
        max_attempts=3,
    )
    assert len(attempts) == 1
    assert attempts[0].health_violations == []
    assert safe_fallback is False
    assert "连带责任" in memo


def test_shared_renderer_appends_only_missing_fixed_disclaimer(tmp_path) -> None:
    prompt = tmp_path / "memo.txt"
    prompt.write_text("开场：{opening}\n对话：{dialogue}", encoding="utf-8")
    memo, _, _, attempts, _, safe_fallback = render_terminal_memo(
        client=NoDisclaimerClient(),
        prompt_path=prompt,
        opening="客户咨询通知争议。",
        dialogue=[("收到什么？", "我收到一份通知。")],
        unavailable_questions=[],
        generation=GenerationConfig(temperature=0, top_p=1, max_tokens=100, seed=42),
        max_attempts=3,
    )
    assert len(attempts) == 1
    assert attempts[0].deterministic_changes == ["append_preliminary_disclaimer"]
    assert attempts[0].raw_output.endswith("先整理原始文件。")
    assert "不替代持证律师" in memo
    assert safe_fallback is False


def test_shared_renderer_neutralizes_unknown_negative_without_fallback(tmp_path) -> None:
    prompt = tmp_path / "memo.txt"
    prompt.write_text("开场：{opening}\n对话：{dialogue}", encoding="utf-8")
    memo, _, _, attempts, _, safe_fallback = render_terminal_memo(
        client=UnavailableNegativeClient(),
        prompt_path=prompt,
        opening="客户咨询家庭暴力保护。",
        dialogue=[
            ("您是否已经向公安机关报案了？", "现有信息里没有这项具体情况，我需要再核实。"),
            ("您是否已经向社区或妇联寻求帮助？", "这个我不清楚。"),
        ],
        unavailable_questions=[
            "您是否已经向公安机关报案了？",
            "您是否已经向社区或妇联寻求帮助？",
        ],
        generation=GenerationConfig(temperature=0, top_p=1, max_tokens=100, seed=42),
        max_attempts=3,
    )
    assert len(attempts) == 1
    assert attempts[0].deterministic_changes == [
        "neutralize_unavailable_negative_claims:authority_report,seek_support"
    ]
    assert attempts[0].health_violations == []
    assert safe_fallback is False
    assert "丈夫殴打致听觉受损" in memo
    assert "治疗费由妹妹垫付" in memo
    assert "尚未向公安机关报案" not in memo
    assert "尚待客户补充核实" in memo


def test_shared_renderer_neutralizes_negative_fact_contradicting_hedged_answer(
    tmp_path,
) -> None:
    prompt = tmp_path / "memo.txt"
    prompt.write_text("开场：{opening}\n对话：{dialogue}", encoding="utf-8")
    question = "您是否曾与行政机关沟通？"
    memo, _, _, attempts, _, safe_fallback = render_terminal_memo(
        client=HedgedAnsweredNegativeClient(),
        prompt_path=prompt,
        opening="客户咨询许可争议。",
        dialogue=[
            (
                question,
                "这个我不太确定，不过按我的理解，我曾向审批窗口当面说明情况。",
            )
        ],
        # The structured simulator outcome is new_hidden_fact, not unavailable.
        unavailable_questions=[],
        generation=GenerationConfig(temperature=0, top_p=1, max_tokens=100, seed=42),
        max_attempts=3,
    )
    assert len(attempts) == 1
    assert attempts[0].deterministic_changes == [
        "neutralize_question_only_negative_claims:communication"
    ]
    assert "客户未与行政机关沟通" not in memo
    assert "沟通协商情况尚待客户补充核实" in memo
    assert attempts[0].health_violations == []
    assert safe_fallback is False


def test_memo_does_not_expand_one_negative_answer_to_all_question_examples() -> None:
    dialogue = [
        (
            "母亲在事件中采取了哪些制止、保护、求助或送医等处置？",
            "动手的是继父，母亲当时没有制止。",
        )
    ]
    memo = (
        "案情概要\n客户咨询抚养争议。\n"
        "关键事实\n客户称母亲未采取制止、保护或送医等行为。\n"
        "法律问题\n抚养安排是否需要调整仍待核实。\n"
        "风险评估\n目前仅能确认客户称母亲未制止。\n"
        "下一步建议\n继续核实其他处置。\n"
        "本分析不替代持证律师的正式意见。"
    )

    assert memo_health_violations(memo, "母亲当时没有制止。", [], dialogue) == [
        "question_example_recast_as_negative:medical_treatment"
    ]
    normalized, changes = drop_question_only_coordinated_negative_examples(memo, dialogue)
    assert changes == ["medical_treatment"]
    assert "未采取制止、保护" in normalized
    assert "送医" not in normalized
    assert memo_health_violations(normalized, "母亲当时没有制止。", [], dialogue) == []


def test_typed_ledger_forbids_a_second_model_written_fact_attribution() -> None:
    memo = (
        "<!-- typed_fact_ledger -->\n"
        "**案情概要**\n客户开场陈述（尚未独立核验）：公司报告涉嫌造假。\n"
        "**关键事实**\n**结构化会话事实状态（确定性记录）**\n"
        "- 客户本轮陈述（尚未独立核验）：张某负责编写报告。\n"
        "<!-- /typed_fact_ledger -->\n"
        "**法律问题**\n责任边界尚待核实。\n"
        "**风险评估**\n客户称其未参与报告编制，但可能涉及管理责任。\n"
        "**下一步建议**\n基于上述单方陈述继续核实。\n"
        "本分析不替代持证律师的正式意见。"
    )
    assert "analysis_fact_attribution_outside_typed_ledger" in memo_health_violations(
        memo,
        "公司报告涉嫌造假。\n张某负责编写报告。",
    )

    safe = memo.replace(
        "客户称其未参与报告编制，但可能涉及管理责任。",
        "基于上述尚未独立核验的单方陈述，具体管理责任尚待核实。",
    )
    assert "analysis_fact_attribution_outside_typed_ledger" not in memo_health_violations(
        safe,
        "公司报告涉嫌造假。\n张某负责编写报告。",
    )


def test_typed_ledger_allows_provenance_reminder_to_verify_client_statement() -> None:
    memo = (
        "<!-- typed_fact_ledger -->\n"
        "**\u6848\u60c5\u6982\u8981**\n\u5ba2\u6237\u5f00\u573a\u9648\u8ff0\uff08\u5c1a\u672a\u72ec\u7acb\u6838\u9a8c\uff09\uff1a\u516c\u53f8\u4ea4\u6613\u53d1\u751f\u4e89\u8bae\u3002\n"
        "**\u5173\u952e\u4e8b\u5b9e**\n**\u7ed3\u6784\u5316\u4f1a\u8bdd\u4e8b\u5b9e\u72b6\u6001\uff08\u786e\u5b9a\u6027\u8bb0\u5f55\uff09**\n"
        "- \u5ba2\u6237\u672c\u8f6e\u9648\u8ff0"
        "\uff08\u5c1a\u672a\u72ec\u7acb\u6838\u9a8c\uff09\uff1a"
        "\u6709\u4e00\u4efd\u5408\u540c\u3002\n"
        "<!-- /typed_fact_ledger -->\n"
        "**\u6cd5\u5f8b\u95ee\u9898**\n\u8d23\u4efb\u8fb9\u754c\u5c1a\u5f85\u6838\u5b9e\u3002\n"
        "**\u98ce\u9669\u8bc4\u4f30**\n\u4e0d\u80fd\u636e\u6b64\u786e\u8ba4\u8d23\u4efb\u3002\n"
        "**\u4e0b\u4e00\u6b65\u5efa\u8bae**\n\u5f85\u7ed3\u5408\u539f\u59cb\u6587\u4ef6\u6838\u5b9e\u5ba2\u6237\u9648\u8ff0\u53ca\u4e89\u8bae\u65b9\u8bf4\u6cd5\u3002\n"
        "\u672c\u5206\u6790\u4e0d\u66ff\u4ee3\u6301\u8bc1\u5f8b\u5e08\u7684\u6b63\u5f0f\u610f\u89c1\u3002"
    )
    assert "analysis_fact_attribution_outside_typed_ledger" not in memo_health_violations(
        memo,
        "\u516c\u53f8\u4ea4\u6613\u53d1\u751f\u4e89\u8bae\u3002\n\u6709\u4e00\u4efd\u5408\u540c\u3002",
    )


def test_typed_ledger_still_forbids_client_narrative_introduced_with_chen_shu() -> None:
    memo = (
        "<!-- typed_fact_ledger -->\n"
        "**\u6848\u60c5\u6982\u8981**\n\u5ba2\u6237\u5f00\u573a\u9648\u8ff0\uff08\u5c1a\u672a\u72ec\u7acb\u6838\u9a8c\uff09\uff1a\u516c\u53f8\u4ea4\u6613\u53d1\u751f\u4e89\u8bae\u3002\n"
        "**\u5173\u952e\u4e8b\u5b9e**\n**\u7ed3\u6784\u5316\u4f1a\u8bdd\u4e8b\u5b9e\u72b6\u6001\uff08\u786e\u5b9a\u6027\u8bb0\u5f55\uff09**\n"
        "- \u5ba2\u6237\u672c\u8f6e\u9648\u8ff0"
        "\uff08\u5c1a\u672a\u72ec\u7acb\u6838\u9a8c\uff09\uff1a"
        "\u6709\u4e00\u4efd\u5408\u540c\u3002\n"
        "<!-- /typed_fact_ledger -->\n"
        "**\u6cd5\u5f8b\u95ee\u9898**\n\u5ba2\u6237\u9648\u8ff0\u5176\u5df2\u7ecf\u53d6\u5f97\u9274\u5b9a\u62a5\u544a\u3002\n"
        "**\u98ce\u9669\u8bc4\u4f30**\n\u7ed3\u8bba\u5c1a\u5f85\u6838\u5b9e\u3002\n"
        "**\u4e0b\u4e00\u6b65\u5efa\u8bae**\n\u7ee7\u7eed\u6838\u5b9e\u3002\n"
        "\u672c\u5206\u6790\u4e0d\u66ff\u4ee3\u6301\u8bc1\u5f8b\u5e08\u7684\u6b63\u5f0f\u610f\u89c1\u3002"
    )
    assert "analysis_fact_attribution_outside_typed_ledger" in memo_health_violations(
        memo,
        "\u516c\u53f8\u4ea4\u6613\u53d1\u751f\u4e89\u8bae\u3002\n\u6709\u4e00\u4efd\u5408\u540c\u3002",
    )


def test_typed_ledger_allows_open_legal_position_analysis() -> None:
    memo = (
        "<!-- typed_fact_ledger -->\n"
        "**\u6848\u60c5\u6982\u8981**\n\u5ba2\u6237\u5f00\u573a\u9648\u8ff0\uff08\u5c1a\u672a\u72ec\u7acb\u6838\u9a8c\uff09\uff1a\u4ea4\u6613\u53d1\u751f\u4e89\u8bae\u3002\n"
        "**\u5173\u952e\u4e8b\u5b9e**\n**\u7ed3\u6784\u5316\u4f1a\u8bdd\u4e8b\u5b9e\u72b6\u6001\uff08\u786e\u5b9a\u6027\u8bb0\u5f55\uff09**\n"
        "- \u5ba2\u6237\u672c\u8f6e\u9648\u8ff0"
        "\uff08\u5c1a\u672a\u72ec\u7acb\u6838\u9a8c\uff09\uff1a"
        "\u5bf9\u65b9\u8981\u6c42\u8d54\u507f\u3002\n"
        "<!-- /typed_fact_ledger -->\n"
        "**\u6cd5\u5f8b\u95ee\u9898**\n\u5bf9\u65b9\u4e3b\u5f20\u662f\u5426\u6784\u6210\u53ef\u652f\u6301\u7684\u8bf7\u6c42\uff1f\n"
        "**\u98ce\u9669\u8bc4\u4f30**\n\u5bf9\u65b9\u4e3b\u5f20\u9700\u8fdb\u4e00\u6b65\u6838\u5b9e\u8bc1\u636e\u3002\n"
        "**\u4e0b\u4e00\u6b65\u5efa\u8bae**\n\u6838\u5b9e\u5bf9\u65b9\u4e3b\u5f20\u7684\u5177\u4f53\u5185\u5bb9\u3002\n"
        "\u672c\u5206\u6790\u4e0d\u66ff\u4ee3\u6301\u8bc1\u5f8b\u5e08\u7684\u6b63\u5f0f\u610f\u89c1\u3002"
    )
    assert "analysis_fact_attribution_outside_typed_ledger" not in memo_health_violations(
        memo,
        "\u4ea4\u6613\u53d1\u751f\u4e89\u8bae\u3002\n\u5bf9\u65b9\u8981\u6c42\u8d54\u507f\u3002",
    )

    referenced_term = memo.replace(
        "\u6838\u5b9e\u5bf9\u65b9\u4e3b\u5f20\u7684\u5177\u4f53\u5185\u5bb9\u3002",
        "\u6838\u5b9e\u5bf9\u65b9\u6240\u79f0\u6807\u51c6\u7684\u5177\u4f53\u5185\u5bb9\u3002",
    )
    assert "analysis_fact_attribution_outside_typed_ledger" not in memo_health_violations(
        referenced_term,
        "\u4ea4\u6613\u53d1\u751f\u4e89\u8bae\u3002\n\u5bf9\u65b9\u8981\u6c42\u8d54\u507f\u3002",
    )


def test_typed_ledger_does_not_treat_client_requested_name_as_attribution() -> None:
    """Regression for run28/B3: ``\u540d\u79f0`` must not be parsed as verb ``\u79f0``."""

    memo = (
        "<!-- typed_fact_ledger -->\n"
        "**\u6848\u60c5\u6982\u8981**\n\u5ba2\u6237\u5f00\u573a\u9648\u8ff0\uff08\u5c1a\u672a\u72ec\u7acb\u6838\u9a8c\uff09\uff1a\u8fc1\u5740\u8bb8\u53ef\u53d1\u751f\u4e89\u8bae\u3002\n"
        "**\u5173\u952e\u4e8b\u5b9e**\n**\u7ed3\u6784\u5316\u4f1a\u8bdd\u4e8b\u5b9e\u72b6\u6001\uff08\u786e\u5b9a\u6027\u8bb0\u5f55\uff09**\n"
        "- \u672c\u8f6e\u672a\u53d6\u5f97\u8d85\u51fa\u5ba2\u6237\u5f00\u573a\u9648\u8ff0\u7684"
        "\u65b0\u4e8b\u5b9e\u3002\n"
        "<!-- /typed_fact_ledger -->\n"
        "**\u6cd5\u5f8b\u95ee\u9898**\n\u8bb8\u53ef\u7a0b\u5e8f\u662f\u5426\u5408\u6cd5\u4ecd\u5f85\u6838\u5b9e\u3002\n"
        "**\u98ce\u9669\u8bc4\u4f30**\n\u76ee\u524d\u65e0\u6cd5\u786e\u8ba4\u7ed3\u8bba\u3002\n"
        "**\u4e0b\u4e00\u6b65\u5efa\u8bae**\n\u5efa\u8bae\u5ba2\u6237\u8865\u5145\u8fc1\u5740\u52a0\u6cb9\u7ad9\u540d\u79f0\u53ca\u8bb8\u53ef\u6750\u6599\u3002\n"
        "\u672c\u5206\u6790\u4e0d\u66ff\u4ee3\u6301\u8bc1\u5f8b\u5e08\u7684\u6b63\u5f0f\u610f\u89c1\u3002"
    )
    assert "analysis_fact_attribution_outside_typed_ledger" not in memo_health_violations(
        memo,
        "\u8fc1\u5740\u8bb8\u53ef\u53d1\u751f\u4e89\u8bae\u3002",
    )


def _memo_with_typed_ledger_analysis(sentence: str) -> str:
    return (
        "<!-- typed_fact_ledger -->\n"
        "**案情概要**\n客户开场陈述（尚未独立核验）：交易发生争议。\n"
        "**关键事实**\n**结构化会话事实状态（确定性记录）**\n"
        "- 本轮未取得超出客户开场陈述的新事实。\n"
        "<!-- /typed_fact_ledger -->\n"
        f"**法律问题**\n{sentence}\n"
        "**风险评估**\n结论尚待核实。\n"
        "**下一步建议**\n继续核实。\n"
        "本分析不替代持证律师的正式意见。"
    )


@pytest.mark.parametrize(
    "sentence",
    (
        "客户称其已经付款。",
        "客户确认其已经付款。",
        "对方承认已经收到货物。",
        "客户反映对方已经解除合同。",
        "据客户介绍，其已经付款。",
    ),
)
def test_typed_ledger_reporter_contract_catches_clause_leading_facts(
    sentence: str,
) -> None:
    assert "analysis_fact_attribution_outside_typed_ledger" in memo_health_violations(
        _memo_with_typed_ledger_analysis(sentence),
        "交易发生争议。",
    )


@pytest.mark.parametrize(
    "sentence",
    (
        "建议客户补充迁址加油站名称及许可材料。",
        "建议客户补充迁址加油站全称及许可材料。",
        "建议客户补充迁址加油站简称及许可材料。",
        "建议客户提供经办人员职称及联系方式。",
        "客户名称尚待核实。",
        "客户全称尚待核实。",
        "客户简称尚待核实。",
        "客户职称尚待核实。",
        "核实对方所称标准的具体内容。",
    ),
)
def test_typed_ledger_reporter_contract_does_not_parse_nominal_cheng(
    sentence: str,
) -> None:
    assert "analysis_fact_attribution_outside_typed_ledger" not in memo_health_violations(
        _memo_with_typed_ledger_analysis(sentence),
        "交易发生争议。",
    )


def test_typed_ledger_forbids_position_that_introduces_completed_event() -> None:
    memo = (
        "<!-- typed_fact_ledger -->\n"
        "**\u6848\u60c5\u6982\u8981**\n\u5ba2\u6237\u5f00\u573a\u9648\u8ff0\uff08\u5c1a\u672a\u72ec\u7acb\u6838\u9a8c\uff09\uff1a\u4ea4\u6613\u53d1\u751f\u4e89\u8bae\u3002\n"
        "**\u5173\u952e\u4e8b\u5b9e**\n**\u7ed3\u6784\u5316\u4f1a\u8bdd\u4e8b\u5b9e\u72b6\u6001\uff08\u786e\u5b9a\u6027\u8bb0\u5f55\uff09**\n"
        "- \u5ba2\u6237\u672c\u8f6e\u9648\u8ff0"
        "\uff08\u5c1a\u672a\u72ec\u7acb\u6838\u9a8c\uff09\uff1a"
        "\u6709\u4e00\u4efd\u5408\u540c\u3002\n"
        "<!-- /typed_fact_ledger -->\n"
        "**\u6cd5\u5f8b\u95ee\u9898**\n\u5ba2\u6237\u4e3b\u5f20\u5176\u5df2\u7ecf\u4ed8\u6b3e\u3002\n"
        "**\u98ce\u9669\u8bc4\u4f30**\n\u8d23\u4efb\u5c1a\u5f85\u6838\u5b9e\u3002\n"
        "**\u4e0b\u4e00\u6b65\u5efa\u8bae**\n\u7ee7\u7eed\u6838\u5b9e\u3002\n"
        "\u672c\u5206\u6790\u4e0d\u66ff\u4ee3\u6301\u8bc1\u5f8b\u5e08\u7684\u6b63\u5f0f\u610f\u89c1\u3002"
    )
    assert "analysis_fact_attribution_outside_typed_ledger" in memo_health_violations(
        memo,
        "\u4ea4\u6613\u53d1\u751f\u4e89\u8bae\u3002\n\u6709\u4e00\u4efd\u5408\u540c\u3002",
    )


def test_shared_renderer_redacts_only_ungrounded_law_name(tmp_path) -> None:
    prompt = tmp_path / "memo.txt"
    prompt.write_text("开场：{opening}\n对话：{dialogue}", encoding="utf-8")
    memo, _, _, attempts, _, safe_fallback = render_terminal_memo(
        client=UngroundedCitationClient(),
        prompt_path=prompt,
        opening="客户咨询通知争议。",
        dialogue=[("收到什么？", "我收到一份通知。")],
        unavailable_questions=[],
        generation=GenerationConfig(temperature=0, top_p=1, max_tokens=100, seed=42),
        max_attempts=3,
    )
    assert len(attempts) == 1
    assert attempts[0].deterministic_changes == [
        "redact_ungrounded_law_citations",
        "append_preliminary_disclaimer",
    ]
    assert "《示例法》" in attempts[0].raw_output
    assert "《示例法》" not in memo
    assert "相关法律规范" in memo
    assert safe_fallback is False


def test_shared_renderer_weakens_unsupported_offence_without_regeneration(tmp_path) -> None:
    prompt = tmp_path / "memo.txt"
    prompt.write_text("开场：{opening}\n对话：{dialogue}", encoding="utf-8")
    memo, _, _, attempts, _, safe_fallback = render_terminal_memo(
        client=UngroundedOffenceClient(),
        prompt_path=prompt,
        opening="客户咨询公司未缴社保。",
        dialogue=[("有劳动合同吗？", "我有劳动合同。")],
        unavailable_questions=[],
        generation=GenerationConfig(temperature=0, top_p=1, max_tokens=100, seed=42),
        max_attempts=3,
    )
    assert len(attempts) == 1
    assert attempts[0].deterministic_changes == [
        "redact_ungrounded_narrow_offenses"
    ]
    assert "诈骗罪" in attempts[0].raw_output
    assert "诈骗罪" not in memo
    assert "需进一步检索核实的刑事法律风险" in memo
    assert safe_fallback is False


def test_shared_renderer_weakens_unsupported_offence_in_elements_phrase(tmp_path) -> None:
    class ElementsClient:
        model = "elements"

        def generate(self, messages, generation):
            return ChatResponse(
                content=(
                    "案情概要\n客户咨询房屋分割。\n关键事实\n客户称房屋婚后登记。\n"
                    "法律问题\n房屋性质仍需核实。\n"
                    "风险评估\n是否符合诈骗罪构成要件仍需核实。\n"
                    "下一步建议\n先整理登记文件。\n"
                    "本分析不替代持证律师的正式意见。"
                ),
                finish_reason="stop",
                prompt_tokens=10,
                completion_tokens=10,
                raw_id="elements",
            )

    prompt = tmp_path / "memo.txt"
    prompt.write_text("开场：{opening}\n对话：{dialogue}", encoding="utf-8")
    memo, _, _, attempts, _, safe_fallback = render_terminal_memo(
        client=ElementsClient(),
        prompt_path=prompt,
        opening="客户咨询房屋分割。",
        dialogue=[("何时登记？", "房屋婚后登记。")],
        unavailable_questions=[],
        generation=GenerationConfig(temperature=0, top_p=1, max_tokens=100, seed=42),
        max_attempts=3,
    )
    assert len(attempts) == 1
    assert attempts[0].deterministic_changes == [
        "redact_ungrounded_narrow_offenses"
    ]
    assert "诈骗罪" not in memo
    assert "是否存在需进一步检索核实的刑事法律风险" in memo
    assert safe_fallback is False


def test_shared_renderer_offence_redaction_does_not_create_a_new_offence_match(
    tmp_path,
) -> None:
    class CompoundOffenceClient:
        model = "compound-offence"

        def generate(self, messages, generation):
            return ChatResponse(
                content=(
                    "案情概要\n客户咨询养殖污染争议。\n"
                    "关键事实\n客户称参与排放安排，具体作用尚待核实。\n"
                    "法律问题\n是否构成污染环境罪或其他相关罪名仍需核实。\n"
                    "风险评估\n可能涉及环境刑事风险，但责任尚不能确定。\n"
                    "下一步建议\n评估是否符合污染环境罪等罪名构成要件。\n"
                    "本分析不替代持证律师的正式意见。"
                ),
                finish_reason="stop",
                prompt_tokens=10,
                completion_tokens=10,
                raw_id="compound-offence",
            )

    prompt = tmp_path / "memo.txt"
    prompt.write_text("开场：{opening}\n对话：{dialogue}", encoding="utf-8")
    memo, _, _, attempts, _, safe_fallback = render_terminal_memo(
        client=CompoundOffenceClient(),
        prompt_path=prompt,
        opening="客户咨询养殖污染争议。",
        dialogue=[("参与方式是什么？", "我参与过排放安排。")],
        unavailable_questions=[],
        generation=GenerationConfig(temperature=0, top_p=1, max_tokens=100, seed=42),
        max_attempts=3,
    )
    assert len(attempts) == 1
    assert attempts[0].health_violations == []
    assert attempts[0].deterministic_changes == [
        "redact_ungrounded_narrow_offenses"
    ]
    assert "污染环境罪" not in memo
    assert "需进一步检索核实的刑事法律风险" in memo
    assert safe_fallback is False
