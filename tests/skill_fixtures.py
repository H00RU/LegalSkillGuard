"""Synthetic prompt-skill documents used by unit and registry tests."""

from __future__ import annotations

from legal_skill_guard.schemas.skill import SkillContract


def _skill(
    skill_id: str,
    *,
    name: str,
    domain: str,
    objective: str,
    description: str,
    applicability_cues: list[str],
    procedure: list[str],
    question_guidance: list[str],
    expected_effects: list[str],
    contraindications: list[str],
    failure_modes: list[str],
) -> SkillContract:
    return SkillContract.model_validate(
        {
            "schema_version": 2,
            "skill_id": skill_id,
            "name": name,
            "version": "1.0.0",
            "domain": domain,
            "status": "active",
            "objective": objective,
            "description": description,
            "applicability_cues": applicability_cues,
            "procedure": procedure,
            "question_guidance": question_guidance,
            "expected_effects": expected_effects,
            "contraindications": contraindications,
            "failure_modes": failure_modes,
            "provenance": {"source": "manual_seed"},
        }
    )


def synthetic_skills() -> list[SkillContract]:
    """Return distinct, statically valid documents in a stable order."""

    return [
        _skill(
            "general.opening_gap_probe",
            name="区分开场陈述与待查属性",
            domain="general",
            objective="fact_elicitation",
            description="在不重复客户开场的前提下，把事件中仍未说明的关键属性转成一个具体事实问题。",
            applicability_cues=["客户已经说明事件结果，但某个会改变初步分析的经过仍不清楚"],
            procedure=["核实开场已经明确的内容", "询问尚未说明的单一事件属性"],
            question_guidance=["问题只指向一个对象的一次连贯事件"],
            expected_effects=["减少开场复述", "提高新事实取得概率"],
            contraindications=["该属性已经由客户明确说明"],
            failure_modes=["把同义改写误当成新的事实缺口"],
        ),
        _skill(
            "procedure.external_evidence_boundary",
            name="区分客户认知与外部证据",
            domain="procedure_evidence",
            objective="evidence_gap_identification",
            description="当关键内容依赖记录或第三方时，明确证据来源和现实可得性，而不要求客户猜测结论。",
            applicability_cues=["争点取决于客户未必亲历的记录或第三方行为"],
            procedure=["区分客户可陈述的事实与外部证据", "记录需要后续核实的证据来源"],
            question_guidance=["只询问客户是否持有或见过相关材料"],
            expected_effects=["形成清楚的待核证据缺口"],
            contraindications=["客户已经完整陈述亲历经过且不依赖外部记录"],
            failure_modes=["把法律判断错误地转交客户回答"],
        ),
        _skill(
            "consumer.single_event_question",
            name="围绕单一消费事件提问",
            domain="consumer_contract",
            objective="fact_elicitation",
            description="把消费争议中的主体、行为和结果组织成一个连贯问题，避免混入另一独立事件。",
            applicability_cues=["同一交易中存在尚未说明的具体履行或沟通过程"],
            procedure=["确认本轮唯一事件对象", "询问该事件的实际经过和结果"],
            question_guidance=["不用斜杠或并列清单拼接多个问法"],
            expected_effects=["提高回答与调查目标的一致性"],
            contraindications=["需要核实的是另一主体掌握的外部记录"],
            failure_modes=["把两个独立交易压缩成表面上的单一问题"],
        ),
        _skill(
            "general.conditional_safe_stop",
            name="条件性初步分析与安全结束",
            domain="general",
            objective="safe_stop",
            description="在可见信息足以支持条件性分析时，明确已知内容和待核事项并安全结束事实询问。",
            applicability_cues=["继续询问不能取得会改变当前分析的客户可回答信息"],
            procedure=["确认现有事实足以形成条件性分析", "列明待核事项后结束询问"],
            question_guidance=["结束前不要用问题形式暗示确定法律结论"],
            expected_effects=["减少无增量交流", "保留事实不确定性的可见边界"],
            contraindications=["仍存在明显可回答且会改变分析的独立事实缺口"],
            failure_modes=["把暂时不愿回答误判为永久不可取得"],
        ),
        _skill(
            "marriage.sensitive_fact_reapproach",
            name="敏感家庭事实的中性询问",
            domain="marriage_family",
            objective="fact_elicitation",
            description="涉及敏感家庭经历时，说明事实用途并使用中性措辞询问一个与法律分析相关的事实。",
            applicability_cues=["客户对家庭关系中的敏感经过表现出顾虑"],
            procedure=["说明询问与初步分析的关系", "使用无指责预设的措辞询问该事实"],
            question_guidance=["避免把争议责任写进问题前提"],
            expected_effects=["降低无谓的披露阻力"],
            contraindications=["该信息与争点无关或会造成不必要的隐私收集"],
            failure_modes=["目的说明过长而形成施压"],
        ),
    ]
