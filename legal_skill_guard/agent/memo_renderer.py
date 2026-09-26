"""Shared, leakage-safe final memo renderer for all experimental methods."""

from __future__ import annotations

import re
from pathlib import Path

from legal_skill_guard.agent.memo_health import (
    TYPED_FACT_LEDGER_END,
    TYPED_FACT_LEDGER_HEADING,
    TYPED_FACT_LEDGER_START,
    deterministic_safe_memo,
    drop_question_only_coordinated_negative_examples,
    memo_health_violations,
    neutralize_client_position_reversals,
    neutralize_known_completed_event_recasts,
    neutralize_known_external_action_recasts,
    neutralize_known_temporal_answer_recasts,
    neutralize_procedural_artifact_acquisition,
    neutralize_question_only_negative_claims,
    neutralize_unavailable_negative_claims,
    neutralize_withheld_answer_recasts,
)
from legal_skill_guard.inference.openai_client import ChatClient, GenerationConfig
from legal_skill_guard.schemas.experiment import MemoAttempt
from legal_skill_guard.schemas.trajectory import TokenUsage


def _render_typed_factual_sections(
    memo: str,
    *,
    opening: str,
    dialogue: list[tuple[str, str]],
    response_kinds: list[str | None],
) -> str:
    """Replace model-written factual prose with the typed visible record.

    The local model still writes legal issues, risk analysis, and next steps.  It
    does not get a second opportunity to paraphrase facts: both factual sections
    are rendered from the typed conversation record, preventing omissions,
    contradictions, and unavailable/withheld answers from becoming case facts.
    """

    if len(response_kinds) != len(dialogue):
        raise ValueError("dialogue response kinds must align one-to-one with dialogue")
    # The heading is reserved for deterministic output.  If a model happens to
    # emit it, demote that heading before adding the authoritative ledger so the
    # downstream health checker cannot mistake model prose for typed evidence.
    memo = memo.replace(TYPED_FACT_LEDGER_START, "")
    memo = memo.replace(TYPED_FACT_LEDGER_END, "")
    memo = memo.replace(TYPED_FACT_LEDGER_HEADING, "**模型生成事实摘要**")

    lines: list[str] = []
    for (question, answer), kind in zip(dialogue, response_kinds, strict=True):
        if kind in {"new_hidden_fact", "repeated_hidden_fact"}:
            lines.append("- 客户本轮陈述（尚未独立核验）：" + answer.strip())
        elif kind == "unavailable":
            lines.append("- 待客户补充核实的问题：" + question.strip())
        elif kind == "withheld":
            lines.append("- 客户本轮暂未披露、仍开放的问题：" + question.strip())
        elif kind == "contract_fallback":
            lines.append("- 本轮会话协议失败，未据此认定任何案件事实：" + question.strip())
    if not lines:
        lines.append("- 本轮未取得超出客户开场陈述的新事实。")

    factual_sections = (
        TYPED_FACT_LEDGER_START
        + "\n**案情概要**\n"
        "客户开场陈述（尚未独立核验）："
        + opening.strip()
        + "\n\n**关键事实**\n"
        + TYPED_FACT_LEDGER_HEADING
        + "\n"
        + "\n".join(lines)
        + "\n"
        + TYPED_FACT_LEDGER_END
    )
    heading_index = memo.find("法律问题")
    if heading_index >= 0:
        # Retain the complete model-written legal-analysis suffix, including
        # optional Markdown markers such as ``**法律问题**``.
        insert_at = memo.rfind("\n", 0, heading_index) + 1
        return factual_sections + "\n\n" + memo[insert_at:].lstrip()
    return factual_sections + "\n\n" + memo


def dialogue_text(opening: str, history: list[tuple[str, str]]) -> str:
    lines = [f"客户（开场）：{opening}"]
    for index, (question, answer) in enumerate(history, start=1):
        lines.extend((f"律师（第{index}轮）：{question}", f"客户：{answer}"))
    return "\n".join(lines)


def _redact_ungrounded_offence(memo: str, offence: str) -> str:
    """Remove one unsupported charge without inventing a replacement doctrine.

    This is the offence analogue of redacting an ungrounded law name or article:
    it only weakens an unsupported label into an explicitly unresolved risk.  It
    never adds a charge, legal test, or conclusion.  A disjunctive second charge is
    deleted outright so a visible-text-grounded first charge remains grammatical.
    """

    escaped = re.escape(offence)
    unresolved_risk = "待检索核实的具体刑事风险"
    value = re.sub(rf"(?:或|、){escaped}", "", memo)
    value = re.sub(
        rf"是否符合{escaped}(?:等(?:相关)?罪名)?构成要件",
        "是否存在需进一步检索核实的刑事法律风险",
        value,
    )
    value = re.sub(
        rf"符合{escaped}(?:等(?:相关)?罪名)?构成要件",
        "存在需进一步检索核实的刑事法律风险",
        value,
    )
    value = re.sub(
        rf"是否(?:可能)?构成{escaped}(?:或其他相关罪名)?",
        "是否存在需进一步检索核实的刑事法律风险",
        value,
    )
    value = re.sub(
        rf"(?:可能)?(?:涉及|涉嫌){escaped}",
        "可能存在需进一步检索核实的刑事法律风险",
        value,
    )
    value = re.sub(
        rf"构成{escaped}",
        "涉及需进一步检索核实的刑事法律风险",
        value,
    )
    # The neutral replacement must not itself look like a named offence to the
    # downstream ``...罪`` detector.  "待检索核实的具体罪名" was re-captured as
    # "待检索核实的具体罪", so an otherwise deterministic safety rewrite forced
    # every bounded regeneration attempt into the generic memo fallback.
    value = value.replace(f"{offence}等罪名", unresolved_risk)
    return value.replace(offence, unresolved_risk)


def render_terminal_memo(
    *,
    client: ChatClient,
    prompt_path: Path,
    opening: str,
    dialogue: list[tuple[str, str]],
    unavailable_questions: list[str],
    generation: GenerationConfig,
    max_attempts: int,
    dialogue_response_kinds: list[str | None] | None = None,
) -> tuple[str, TokenUsage, str | None, list[MemoAttempt], list[str], bool]:
    """Generate one shared memo with bounded repair and deterministic safe fallback."""

    if max_attempts < 1:
        raise ValueError("memo max_attempts must be positive")

    dialogue_questions = {question for question, _ in dialogue}
    unknown_questions = sorted(set(unavailable_questions) - dialogue_questions)
    if unknown_questions:
        raise ValueError(
            "unavailable questions must come from the visible dialogue: "
            + "; ".join(unknown_questions)
        )
    unavailable_questions = list(dict.fromkeys(unavailable_questions))
    typed_response_kinds_provided = dialogue_response_kinds is not None
    if dialogue_response_kinds is None:
        dialogue_response_kinds = [None] * len(dialogue)
    if len(dialogue_response_kinds) != len(dialogue):
        raise ValueError("dialogue response kinds must align one-to-one with dialogue")
    withheld_questions = list(
        dict.fromkeys(
            question
            for (question, _), kind in zip(
                dialogue, dialogue_response_kinds, strict=True
            )
            if kind == "withheld"
        )
    )
    visible_text = dialogue_text(opening, dialogue)
    grounding_text = opening + "\n" + "\n".join(answer for _, answer in dialogue)
    prompt = prompt_path.read_text(encoding="utf-8").format(opening=opening, dialogue=visible_text)
    if unavailable_questions or withheld_questions:
        status_lines = [
            "\n\n以下回答状态由确定性会话控制器提供，必须逐项遵守："
        ]
        status_lines.extend(
            f"- [unavailable/客户确实不知道] {question}"
            for question in unavailable_questions
        )
        status_lines.extend(
            f"- [withheld/客户本轮暂不披露] {question}"
            for question in withheld_questions
        )
        status_lines.append(
            "unavailable只能写待客户补充，不得写成未发生/没有；"
            "withheld只能写客户本轮暂未披露且问题仍开放，不得写成"
            "客户不知道，也不得替客户填入任何肯定或否定答案。"
        )
        prompt += "\n".join(status_lines)
    attempts: list[MemoAttempt] = []
    usage = TokenUsage()
    response = None
    for attempt_index in range(max_attempts):
        messages = [{"role": "user", "content": prompt}]
        if attempts:
            # Give the model one ordinary edit opportunity.  If consecutive
            # attempts hit the same contract family, stop anchoring the next
            # completion on the rejected prose and regenerate from the unchanged
            # visible record plus the explicit repair instruction.  This mirrors
            # the policy editor's bounded anti-stagnation rule; it neither accepts
            # nor deterministically authors an unsafe memo.
            repair_stagnated = (
                len(attempts) >= 2
                and attempts[-1].health_violations
                == attempts[-2].health_violations
            )
            if not repair_stagnated:
                messages.append({"role": "assistant", "content": attempts[-1].raw_output})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "先前生成结果未通过研究安全契约："
                        + "；".join(attempts[-1].health_violations)
                        + "。请直接编辑上一稿：保留有可见来源且没有被拒的段落，只修正违规句，"
                        "然后只输出法律问题、风险评估、下一步建议三个标题的完整替代稿；"
                        "不得输出会被确定性账本替换的案情概要或关键事实，也不得新增原始"
                        "可见对话之外的事实。"
                        "只能保留对话可支持的事实和宽泛待核实法律问题；若违规项是"
                        "ungrounded_law_article、ungrounded_case_number、"
                        "ungrounded_narrow_offense或ungrounded_procedural_deadline，"
                        "必须删除未经检索支持的条号、案号、具体罪名或期限数字，改成宽泛且"
                        "有条件的法律问题；ungrounded_narrow_offense冒号后已经给出必须删除的"
                        "具体罪名，若同句另有可见材料同词根支持的罪名，只保留后者作为待核问题；"
                        "若违规项是uncalibrated_offense_elements_conclusion，不得断言行为已经"
                        "符合构成要件，必须改成是否符合仍待结合主观、客观事实和法律检索核实；"
                        "若违规项是uncalibrated_legal_invariance_conclusion，不得断言某技术、"
                        "行为或情节当然不影响认定、性质、责任、效力或结果；若违规项是"
                        "unretrieved_specific_legal_rule，删除未经检索的要件清单，仅保留待核"
                        "法律问题；"
                        "若违规项是"
                        "uncalibrated_legal_conclusion，必须删除没有归属于客户或对方的"
                        "确定性法律结论，改成真正开放且说明仍待事实、材料和法律检索"
                        "核实的表述；但‘不必然、并非当然、并不肯定’这类否定确定性"
                        "的校准表述可以保留。在案情概要和关键事实中，来源归属以句号"
                        "为边界：每个句号后的新事实陈述都必须重新明确写‘客户称’或"
                        "‘据客户转述’，不能让前一句的归属覆盖后一句；若是政府、对方"
                        "或其他主体的立场，写成‘据客户转述，某主体表示/主张……’，"
                        "不得把该立场写成你的法律结论；"
                        "若违规项是"
                        "analysis_fact_attribution_outside_typed_ledger，确定性事实账本已经完整"
                        "保留客户开场和后续回答；删除法律问题、风险评估或建议中任何主体"
                        "另行陈述、确认、承认、表示、主张、认为或认定的具体事实，包括但"
                        "不限于‘客户称/据客户陈述/对方主张/法院认定/行政机关表示’，"
                        "改为‘基于上述尚未独立核验的单方陈述’后作开放、条件性"
                        "分析，不得重新改写或补充事实。"
                        "若违规项是"
                        "unqualified_procedural_recommendation，必须删除直接采取该程序的"
                        "建议，改为先核实法域、管辖、程序状态、条件和期限，再由持证律师"
                        "评估是否存在相应路径。如果原句要求‘获取/出具司法鉴定报告’，"
                        "只能改为核实是否已有该报告；若尚无报告，是否需要新做鉴定"
                        "必须留待核实上述程序条件后由持证律师评估。"
                        "不得用换词方式保留违规结论。"
                        "若违规项是unavailable_answer_recast_as_negative，客户对该问题的回答"
                        "只是未知或待核实；删除‘尚未、未、没有、从未’等否定事实断言，"
                        "统一改成该事项尚待客户补充核实，不得把会话中未取得答案写成未发生。"
                        "若违规项是withheld_answer_recast_as_known_or_unavailable，客户只是"
                        "本轮暂未披露；必须写明该问题仍开放，不得写成客户不知道，"
                        "也不得替客户填入肯定或否定事实。"
                        "若违规项是question_example_recast_as_negative，律师问题列举了多个"
                        "可能行为，但客户只明确否定其中一项；删除客户未明确否定的其他行为，"
                        "不得把问题中的例子扩写成客户已经确认的否定事实。"
                        "若违规项是client_position_reversed，必须按客户原话恢复其实际观点，"
                        "不得把‘可能负有义务’反写成‘认为无需履行’，也不得替客户判断该观点"
                        "在法律上是否正确。若违规项是known_temporal_answer_recast_as_unknown，"
                        "客户已经明确陈述了事件先后；必须保留该单方陈述的先后关系，只能写"
                        "该陈述或材料尚未独立核验，不能写成客户没有说明或时间关系未知。"
                        "若违规项是known_external_action_recast_as_pending，客户已经明确陈述"
                        "某机构完成了相关行为；必须保留这是客户单方陈述并注明尚未独立核验，"
                        "不能把‘公安已查明’等表述反写成‘尚待公安核实’。"
                        "若违规项是known_completed_event_recast_as_uncertain，客户已经明确"
                        "陈述某事件完成；必须保留该单方陈述并注明尚未独立核验，不能改写成"
                        "该事件可能发生或是否发生尚待核实。"
                    ),
                }
            )
        response = client.generate(
            messages,
            GenerationConfig(
                temperature=generation.temperature,
                top_p=generation.top_p,
                max_tokens=generation.max_tokens,
                seed=generation.seed + attempt_index,
                disable_thinking=generation.disable_thinking,
            ),
        )
        usage.prompt += response.prompt_tokens
        usage.completion += response.completion_tokens
        # A lawyer question may itself invent a doctrine or citation.  Only the
        # opening and client answers can ground those claims in no-RAG experiments.
        normalized_memo, neutralized_concepts = neutralize_unavailable_negative_claims(
            response.content,
            unavailable_questions,
        )
        deterministic_changes: list[str] = []
        if neutralized_concepts:
            deterministic_changes.append(
                "neutralize_unavailable_negative_claims:"
                + ",".join(neutralized_concepts)
            )
        normalized_memo, neutralized_withheld = neutralize_withheld_answer_recasts(
            normalized_memo, withheld_questions
        )
        if neutralized_withheld:
            deterministic_changes.append(
                "neutralize_withheld_answer_recasts:"
                + ",".join(neutralized_withheld)
            )
        normalized_memo, restored_client_positions = (
            neutralize_client_position_reversals(normalized_memo, dialogue)
        )
        if restored_client_positions:
            deterministic_changes.append(
                "neutralize_client_position_reversals:"
                + ",".join(restored_client_positions)
            )
        normalized_memo, restored_temporal_answers = (
            neutralize_known_temporal_answer_recasts(normalized_memo, dialogue)
        )
        if restored_temporal_answers:
            deterministic_changes.append(
                "neutralize_known_temporal_answer_recasts:"
                + ",".join(restored_temporal_answers)
            )
        normalized_memo, restored_external_actions = (
            neutralize_known_external_action_recasts(normalized_memo, dialogue)
        )
        if restored_external_actions:
            deterministic_changes.append(
                "neutralize_known_external_action_recasts:"
                + ",".join(restored_external_actions)
            )
        normalized_memo, restored_completed_events = (
            neutralize_known_completed_event_recasts(normalized_memo, dialogue)
        )
        if restored_completed_events:
            deterministic_changes.append(
                "neutralize_known_completed_event_recasts:"
                + ",".join(restored_completed_events)
            )
        normalized_memo, dropped_question_examples = (
            drop_question_only_coordinated_negative_examples(normalized_memo, dialogue)
        )
        if dropped_question_examples:
            deterministic_changes.append(
                "drop_question_only_coordinated_negative_examples:"
                + ",".join(dropped_question_examples)
            )
        normalized_memo, neutralized_question_concepts = (
            neutralize_question_only_negative_claims(normalized_memo, dialogue)
        )
        if neutralized_question_concepts:
            deterministic_changes.append(
                "neutralize_question_only_negative_claims:"
                + ",".join(neutralized_question_concepts)
            )
        normalized_memo, neutralized_procedural_artifacts = (
            neutralize_procedural_artifact_acquisition(normalized_memo)
        )
        if neutralized_procedural_artifacts:
            deterministic_changes.append(
                "neutralize_procedural_artifact_acquisition:"
                + ",".join(neutralized_procedural_artifacts)
            )
        if typed_response_kinds_provided:
            normalized_memo = _render_typed_factual_sections(
                normalized_memo,
                opening=opening,
                dialogue=dialogue,
                response_kinds=dialogue_response_kinds,
            )
            deterministic_changes.append("render_typed_fact_ledger")
        violations = memo_health_violations(
            normalized_memo,
            grounding_text,
            unavailable_questions,
            dialogue,
            withheld_questions,
        )
        # A fixed disclaimer and removal of ungrounded law-book names are narrow
        # provenance normalizations, not substantive legal conclusions.  Apply them
        # independently before deciding whether substantive regeneration is needed;
        # coupling them to unrelated violations made an otherwise safe omission recur
        # on every regenerated draft.
        if violations:
            citations = sorted(
                {
                    item.split(":", 1)[1]
                    for item in violations
                    if item.startswith("ungrounded_law_citation:")
                }
            )
            for citation in citations:
                normalized_memo = normalized_memo.replace(citation, "相关法律规范")
            if citations:
                deterministic_changes.append("redact_ungrounded_law_citations")
            articles = sorted(
                {
                    item.split(":", 1)[1]
                    for item in violations
                    if item.startswith("ungrounded_law_article:")
                }
            )
            for article in articles:
                normalized_memo = normalized_memo.replace(article, "相关条款")
            if articles:
                deterministic_changes.append("redact_ungrounded_law_articles")
            offences = sorted(
                {
                    item.split(":", 1)[1]
                    for item in violations
                    if item.startswith("ungrounded_narrow_offense:")
                }
            )
            for offence in offences:
                normalized_memo = _redact_ungrounded_offence(normalized_memo, offence)
            if offences:
                deterministic_changes.append("redact_ungrounded_narrow_offenses")
            if "missing_preliminary_disclaimer" in violations:
                normalized_memo = (
                    normalized_memo.rstrip() + "\n\n本备忘录仅基于客户单方陈述作研究性初步分析，"
                    "不替代持证律师结合完整材料提供的正式意见。"
                )
                deterministic_changes.append("append_preliminary_disclaimer")
            violations = memo_health_violations(
                normalized_memo,
                grounding_text,
                unavailable_questions,
                dialogue,
                withheld_questions,
            )
        attempts.append(
            MemoAttempt(
                raw_output=response.content,
                health_violations=violations,
                deterministic_changes=deterministic_changes,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                finish_reason=response.finish_reason,
            )
        )
        if response.finish_reason != "length" and not violations:
            return normalized_memo, usage, response.finish_reason, attempts, [], False

    fallback = deterministic_safe_memo(
        opening, dialogue, dialogue_response_kinds=dialogue_response_kinds
    )
    if typed_response_kinds_provided:
        # The fallback copies typed dialogue outcomes just as the normal memo
        # path does.  Render those copied facts and unanswered questions inside
        # the same reserved ledger before applying recast detectors; otherwise
        # a grounded negative answer near an unanswered question can be mistaken
        # for a model-invented negative assertion.
        fallback = _render_typed_factual_sections(
            fallback,
            opening=opening,
            dialogue=dialogue,
            response_kinds=dialogue_response_kinds,
        )
    fallback_violations = memo_health_violations(
        fallback,
        grounding_text,
        unavailable_questions,
        dialogue,
        withheld_questions,
    )
    if fallback_violations:
        raise RuntimeError(f"Deterministic memo fallback invalid: {fallback_violations}")
    assert response is not None
    return fallback, usage, response.finish_reason, attempts, [], True
