"""Retired protocol-35 client implementation for historical regression tests only.

This module is intentionally outside the production package. Current experiment code
uses :mod:`legal_skill_guard.environment.client_response` and must never import this
test support module.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Literal

from legal_skill_guard.inference.openai_client import (
    ChatClient,
    ChatResponse,
    GenerationConfig,
)
from legal_skill_guard.schemas.state import ClientResponseKind, DisclosureDecision
from legal_skill_guard.utils.hashing import canonical_json_sha256

DEFAULT_RELEVANCE_PROMPT = (
    "判断候选客户事实是否直接回答律师本轮索取的对象和属性。候选来源为隐藏事实时，还必须相对"
    "公开开场提供所问属性的实质新增信息；开场已经完整说出的内容不算新增。仅属于同一案件或共享"
    '主题词不算直接回答。只输出 {"answers_question":true} 或 {"answers_question":false}。'
)
DEFAULT_DISCLOSURE_PROMPT = (
    "候选事实已经被独立确认直接回答律师问题。你只按客户人格、问题语气和可见历史判断本轮"
    '披露或暂缓披露。只输出 {{"disclosure":"disclose"}} 或 '
    '{{"disclosure":"withhold"}}。'
)

# The runtime selector is constrained to the current two-axis contract.  Exact
# replay keys include this schema, so responses cached under the former
# ``fact_ids``-only protocol cannot silently enter a new run.  The parser below
# still accepts the old shape as ``disclose`` for historical objects and focused
# regression fixtures; newly generated responses must use this schema.
CLIENT_FACT_SELECTION_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "fact_ids": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 1,
        },
        "disclosure": {"type": "string", "enum": ["disclose", "withhold"]},
    },
    "required": ["fact_ids", "disclosure"],
    "additionalProperties": False,
}


def client_fact_selection_schema(valid_fact_ids: list[str]) -> dict[str, object]:
    """Constrain structured decoding to the current finite candidate set.

    Relevance rejection removes a candidate from the current phase.  Leaving the
    JSON schema open to arbitrary strings allowed a small model to repeat that
    excluded identifier until the format-repair budget was exhausted.  The enum is
    derived only from the same visible candidate block already in the selector
    prompt; it changes no disclosure label and cannot introduce a fact.
    """

    return {
        "type": "object",
        "properties": {
            "fact_ids": {
                "type": "array",
                "items": {"type": "string", "enum": list(valid_fact_ids)},
                "maxItems": 1,
            },
            "disclosure": {"type": "string", "enum": ["disclose", "withhold"]},
        },
        "required": ["fact_ids", "disclosure"],
        "additionalProperties": False,
    }
CLIENT_DISCLOSURE_DECISION_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "disclosure": {"type": "string", "enum": ["disclose", "withhold"]},
    },
    "required": ["disclosure"],
    "additionalProperties": False,
}

# A Boolean-only relevance answer encouraged the small frozen client model to
# classify topical similarity instead of checking whether the candidate entails
# the proposition actually requested by the lawyer.  Keep the verifier inside the
# same client-simulator role, but make its intermediate contract explicit and
# auditable.  The three alignment flags are also checked by Python before a
# candidate can be disclosed, so an internally inconsistent ``true`` is rejected.
CLIENT_RELEVANCE_ANALYSIS_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "question_actor": {"type": "string", "maxLength": 120},
        "question_predicate": {"type": "string", "maxLength": 160},
        "question_attribute": {"type": "string", "maxLength": 160},
        "candidate_actor": {"type": "string", "maxLength": 120},
        "candidate_predicate": {"type": "string", "maxLength": 200},
        "candidate_attribute": {"type": "string", "maxLength": 200},
        "candidate_assertion_source": {
            "type": "string",
            "enum": [
                "direct_client_fact",
                "reported_other_claim",
                "client_worry_or_inference",
                "document_content",
                "other",
            ],
        },
        "same_actor": {"type": "boolean"},
        "same_predicate": {"type": "boolean"},
        "same_attribute": {"type": "boolean"},
        "answers_question": {"type": "boolean"},
    },
    "required": [
        "question_actor",
        "question_predicate",
        "question_attribute",
        "candidate_actor",
        "candidate_predicate",
        "candidate_attribute",
        "candidate_assertion_source",
        "same_actor",
        "same_predicate",
        "same_attribute",
        "answers_question",
    ],
    "additionalProperties": False,
}


EVENT_CONCEPT_PATTERNS: dict[str, tuple[str, ...]] = {
    "purchase": ("购买", "购房", "买房", "买的房", "买下", "购置"),
    "property_registration": (
        "房产登记",
        "产权登记",
        "不动产登记",
        "登记在",
        "登记到",
        "过户",
        "加名",
        "名字加上",
        "名字加到",
        "姓名加上",
        "姓名加到",
        "产权人",
        "房本",
        "房产证",
        "不动产权证",
        "改成夫妻",
        "改成双方",
        "夫妻两人的名字",
        "夫妻两个人的名字",
        "夫妻双方的名字",
        "两个人名下",
        "双方名下",
    ),
    # “婚前/婚后” alone modifies another event (for example 婚前购买 or
    # 婚后加名); it is not itself a request about the marriage event.
    "marriage": ("结婚", "婚姻登记", "登记结婚", "领证"),
    "divorce": ("离婚", "解除婚姻关系"),
    "payment": (
        "付款",
        "支付",
        "结算",
        "货款",
        "缴纳",
        "交款",
        "出资",
        "还款",
        "还贷",
        "偿还",
        "房贷",
        "按揭",
    ),
    "signing": ("签署", "签订", "订立", "落款"),
    "notice": ("通知", "告知", "送达", "收到"),
    "filing": ("起诉", "立案", "仲裁", "复议", "报案", "申请执行"),
    "physical_injury": ("受伤", "伤情", "损伤", "挫伤", "伤势"),
    "physical_assault": ("殴打", "击打", "打伤", "施暴", "暴力行为"),
    "contract_renewal": ("续签", "续订"),
    "employment_termination": (
        "解除劳动合同",
        "劳动合同解除",
        "终止劳动合同",
        "劳动合同终止",
        "解除协议",
        "离职协议",
    ),
    "employment_continuation": (
        "继续工作",
        "继续用工",
        "继续履行原合同",
        "仍在工作",
        "到期后工作",
        "仍按原约定付薪",
    ),
}

COGNITIVE_SUBJECT_PATTERNS: dict[str, tuple[str, ...]] = {
    "client": ("您", "你", "客户", "本人", "我方", "贵公司", "贵单位", "我", "我们", "我司"),
    "counterparty": (
        "他",
        "她",
        "丈夫",
        "妻子",
        "父亲",
        "母亲",
        "继父",
        "继母",
        "对方",
        "上线",
        "银行",
        "平台",
        "医院",
        "店家",
        "博主",
        "行政机关",
        "文体局",
        "住建局",
    ),
}
COGNITIVE_VERBS = ("知道", "知晓", "了解", "清楚", "明知", "意识到", "认识到")

# These roles are extracted only when they are grammatical arguments of a
# living/care relation.  Merely mentioning (for example) a mother elsewhere in
# a sentence must not cause a veto.  First-person and second-person forms are
# the consulting client; named family roles are distinct third parties.
RELATION_ROLE_PATTERNS: dict[str, tuple[str, ...]] = {
    "client": ("您", "你", "我", "本人", "我方"),
    "father": ("父亲", "爸爸"),
    "mother": ("母亲", "妈妈"),
    "stepfather": ("继父",),
    "stepmother": ("继母",),
    "husband": ("丈夫", "老公"),
    "wife": ("妻子", "老婆"),
    "grandparents": ("祖父母", "外祖父母", "爷爷奶奶", "外公外婆"),
    "generic_counterparty": ("对方", "他", "她"),
}
RELATION_PREDICATES = (
    "共同生活",
    "一起生活",
    "生活",
    "居住",
    "同住",
    "照料",
    "照顾",
    "抚养",
    "看护",
)

# Relative stages are compared only for the same explicitly named transition.
# This captures contract/employment/procedure chronology without assuming that
# unrelated occurrences of “之前” and “之后” refer to the same event.
TRANSITION_ANCHOR_PATTERNS: dict[str, tuple[str, ...]] = {
    "agreement": ("签约", "签订协议", "签署协议", "订立合同"),
    "employment_entry": ("入职", "到岗"),
    "employment_exit": ("离职", "解除劳动关系", "终止劳动关系"),
    "marriage": ("结婚", "登记结婚", "离婚"),
    "registration": ("登记", "过户"),
    "payment": ("付款", "支付", "转账"),
    "notice": ("通知", "告知", "送达"),
    "filing": ("起诉", "立案", "申请", "报案"),
    "handover": ("交付", "接回", "搬离", "迁出"),
    "sanction": ("处罚", "处分"),
}


def asks_target_audience(value: str) -> bool:
    """Whether a question requests who a product, service, or message targets."""

    return bool(
        re.search(r"(?:目标|主要|具体)?(?:消费者|客户|用户)(?:群体|人群|类型|类别)", value)
        or re.search(r"(?:目标人群|目标群体|目标受众|受众群体|受众对象)", value)
        or re.search(
            r"(?:面向|针对|服务于).{0,8}(?:哪些|什么|哪类|何种)"
            r"(?:目标)?(?:消费者|客户|用户|人群|群体|受众)",
            value,
        )
    )


def identifies_target_audience(value: str) -> bool:
    """Whether a candidate states an audience attribute rather than place or time."""

    return bool(
        re.search(
            r"(?:面向|针对|服务于|主要客户|目标客户|目标用户|目标人群|目标群体|"
            r"目标受众|受众群体|消费者群体).{0,18}"
            r"(?:儿童|未成年人|青少年|成年人|老年人|男性|女性|孕妇|学生|职工|"
            r"企业|机构|个人|专业人士|消费者|客户|用户|人群|群体|受众)",
            value,
        )
        or re.search(
            r"(?:儿童|未成年人|青少年|成年人|老年人|男性|女性|孕妇|学生|职工|"
            r"企业客户|机构客户|个人消费者|专业人士).{0,12}"
            r"(?:是|为|属于|作为)?(?:主要|目标)?(?:消费者|客户|用户|人群|群体|受众)",
            value,
        )
    )


def asks_asset_use_or_management(value: str) -> bool:
    """Whether the requested attribute is actual use/control of an asset.

    Registration, acquisition and contribution concern the same asset but do not
    answer how it was actually used or managed.  Keeping this as an attribute
    contract (rather than an event-name comparison) also protects visible-state
    coverage, where the candidate is an already rendered client answer.
    """

    asset = r"(?:房屋|房产|住宅|商铺|车辆|设备|财产)"
    attribute = r"(?:实际)?(?:使用|管理|占有|居住|出租|经营|控制)"
    return bool(
        re.search(rf"{asset}.{{0,18}}{attribute}", value)
        or re.search(rf"{attribute}.{{0,18}}{asset}", value)
    )


def identifies_asset_use_or_management(value: str) -> bool:
    """Whether a statement supplies an asset-use/management fact."""

    asset = r"(?:房屋|房产|住宅|商铺|车辆|设备|财产|该房|这套房)"
    predicate = (
        r"(?:使用|管理|占有|居住|入住|出租|收租|经营|控制|保管|维护|维修|装修)"
    )
    return bool(
        re.search(rf"{asset}.{{0,20}}{predicate}", value)
        or re.search(rf"{predicate}.{{0,20}}{asset}", value)
    )


def asks_child_custody_arrangement(value: str) -> bool:
    """Whether the question asks what an existing child-care disposition says."""

    child = r"(?:孩子|子女|长子|次子|儿子|女儿|小儿子|小女儿)"
    disposition = r"(?:抚养权|直接抚养|抚养安排|离婚约定|调解书|判决)"
    requested = r"(?:约定|判决|调解|安排|内容|写明|载明|由谁|随谁)"
    return bool(
        re.search(rf"{child}.{{0,24}}{disposition}.{{0,20}}{requested}", value)
        or re.search(rf"{disposition}.{{0,28}}{child}.{{0,20}}{requested}", value)
        or re.search(
            rf"(?:离婚后|离婚时).{{0,20}}{child}.{{0,12}}"
            rf"(?:抚养权|抚养).{{0,16}}(?:约定|判决|内容)",
            value,
        )
    )


def identifies_child_custody_arrangement(value: str) -> bool:
    """Whether a statement gives the operative child-care allocation."""

    child = r"(?:孩子|子女|长子|次子|儿子|女儿|小儿子|小女儿|[\u4e00-\u9fff]{1,4}某[甲乙丙丁]?)"
    caregiver = r"(?:我|本人|父亲|母亲|爸爸|妈妈|男方|女方|对方)"
    allocation = rf"{child}.{{0,12}}(?:随|跟随|由){caregiver}.{{0,8}}(?:生活|抚养|照料|照顾)?"
    return bool(
        re.search(rf"(?:约定|判决|调解书|调解协议|裁判).{{0,32}}{allocation}", value)
        or re.search(rf"{allocation}.{{0,24}}(?:约定|判决|调解|安排)", value)
        or re.search(rf"(?:离婚后|离婚时).{{0,24}}{allocation}", value)
    )


def cognitive_subject_role(value: str) -> str | None:
    """Return the last explicit subject governing a cognition proposition."""

    subjects = {
        subject: role for role, values in COGNITIVE_SUBJECT_PATTERNS.items() for subject in values
    }
    subject_pattern = "|".join(re.escape(item) for item in sorted(subjects, key=len, reverse=True))
    verb_pattern = "|".join(re.escape(item) for item in COGNITIVE_VERBS)
    matches = list(
        re.finditer(
            rf"(?P<subject>{subject_pattern})"
            rf"(?:本人|个人)?(?:是否|有无|实际|明确|曾经|曾|已经|已|一直|真正)?"
            rf"(?:{verb_pattern})",
            value,
        )
    )
    if not matches:
        return None
    return subjects[matches[-1].group("subject")]


def asks_cognitive_purpose(value: str) -> bool:
    """Whether the client is asked what they knew about an item's purpose.

    A transfer, amount, destination, or profit can be relevant to the same event
    without establishing the person's contemporaneous knowledge of why the item
    was being used.  Keep this as an attribute boundary rather than an offence- or
    case-specific rule.
    """

    cognitive = r"(?:知道|知晓|了解|清楚|明知|意识到|认识到)"
    purpose = r"(?:用途|目的|用来做什么|用于什么|拿来做什么|作何使用|为何使用)"
    client_subject = r"(?:您|你|客户|本人|我方|贵公司|贵单位)"
    return bool(
        re.search(rf"{client_subject}.{{0,40}}{purpose}.{{0,12}}{cognitive}", value)
        or re.search(rf"{client_subject}.{{0,40}}{cognitive}.{{0,24}}{purpose}", value)
    )


def identifies_cognitive_purpose(value: str, *, expected_role: str | None) -> bool:
    """Whether a statement supplies knowledge of purpose, not merely movement."""

    belief_role = cognitive_subject_role(value)
    if belief_role is not None and (expected_role is None or belief_role == expected_role):
        return True
    if expected_role is not None:
        role_terms = COGNITIVE_SUBJECT_PATTERNS.get(expected_role, ())
        subjects = "|".join(
            re.escape(item) for item in sorted(role_terms, key=len, reverse=True)
        )
        verbs = "|".join(re.escape(item) for item in COGNITIVE_VERBS)
        if subjects and re.search(rf"(?:{subjects}).{{0,24}}(?:{verbs})", value):
            return True
    return bool(
        re.search(
            r"(?:用途|目的).{0,8}(?:是|为|包括)|"
            r"(?:用于|用来|拿来|为了|目的是|目的在于).{0,24}[一-鿿A-Za-z0-9]",
            value,
        )
    )


def observable_action_subject_roles(value: str) -> set[str]:
    """Return explicit actors grammatically tied to an observable action."""

    action_pattern = (
        r"(?:采取|实施|作出|进行|参与|指使|制止|阻止|拒绝|支付|通知|告知|"
        r"照料|照顾|殴打|击打|处罚|疏忽|失职|不当行为)"
    )
    roles: set[str] = set()
    for role, terms in RELATION_ROLE_PATTERNS.items():
        for term in terms:
            if re.search(rf"{re.escape(term)}.{{0,20}}{action_pattern}", value):
                roles.add(role)
    return roles


def deterministic_relevance_compatibility(
    question: str, candidate_belief: str
) -> tuple[bool | None, list[str]]:
    """Apply conservative event and cognition-subject vetoes with audit reasons."""

    violations: list[str] = []
    event_compatibility = event_attribute_compatible(question, candidate_belief)
    if event_compatibility is False:
        violations.append("different_event_concept")
    question_role = cognitive_subject_role(question)
    belief_role = cognitive_subject_role(candidate_belief)
    subject_check_applied = question_role is not None and belief_role is not None
    if subject_check_applied and question_role != belief_role:
        violations.append(f"cognitive_subject_mismatch:{question_role}->{belief_role}")
    requested_action_roles = observable_action_subject_roles(question)
    present_action_roles = observable_action_subject_roles(candidate_belief)
    if (
        requested_action_roles
        and present_action_roles
        and requested_action_roles.isdisjoint(present_action_roles)
    ):
        violations.append(
            "observable_action_subject_mismatch:"
            + ",".join(sorted(requested_action_roles))
            + "->"
            + ",".join(sorted(present_action_roles))
        )
    relation_compatibility = relationship_context_compatible(question, candidate_belief)
    if relation_compatibility is False:
        violations.append("relationship_context_mismatch")
    stage_compatibility = transition_stage_compatible(question, candidate_belief)
    if stage_compatibility is False:
        violations.append("transition_stage_mismatch")
    violations.extend(direct_answer_attribute_violations(question, candidate_belief))
    if violations:
        return False, violations
    if (
        event_compatibility is True
        or subject_check_applied
        or relation_compatibility is True
        or stage_compatibility is True
        or presupposition_correction_match(question, candidate_belief)
        or direct_answer_attribute_explicit_match(question, candidate_belief)
    ):
        return True, []
    return None, []


def direct_answer_attribute_violations(question: str, candidate_belief: str) -> list[str]:
    """Reject generic or ambiguous answers to explicitly requested attributes."""

    violations: list[str] = []
    question_cognitive_role = cognitive_subject_role(question)
    if question_cognitive_role is None and re.search(r"(?:您|你)", question):
        question_cognitive_role = "client"
    if asks_cognitive_purpose(question) and not identifies_cognitive_purpose(
        candidate_belief,
        expected_role=question_cognitive_role,
    ):
        violations.append("requested_cognitive_purpose_missing")
    asks_document_contents = bool(
        re.search(
            r"(?:档案|记录|证明|文件|材料|决定书|通知书|申请书|文书|报告|证件)"
            r".{0,20}(?:具体内容|写了什么|写明什么|记载什么|载明什么|哪些内容)",
            question,
        )
        or re.search(
            r"(?:具体内容|写了什么|写明什么|记载什么|载明什么|哪些内容)"
            r".{0,16}(?:档案|记录|证明|文件|材料|决定书|通知书|申请书|文书|报告|证件)",
            question,
        )
    )
    candidate_states_document_contents = bool(
        re.search(
            r"(?:档案|记录|证明|文件|材料|决定书|通知书|申请书|文书|报告|证件|"
            r"户口簿|登记簿).{0,28}(?:写明|载明|记载|显示|结论|内容|为|是|包括)",
            candidate_belief,
        )
        or re.search(
            r"(?:写明|载明|记载|显示|结论|内容).{0,24}"
            r"(?:档案|记录|证明|文件|材料|决定书|通知书|申请书|文书|报告|证件|"
            r"户口簿|登记簿)",
            candidate_belief,
        )
    )
    if asks_document_contents and not candidate_states_document_contents:
        violations.append("requested_document_contents_missing")
    asks_unverifiable_material_items = bool(
        re.search(r"(?:哪些|什么|何种).{0,8}材料.{0,10}(?:无法|不能|未能)核实", question)
        or re.search(r"材料.{0,10}(?:无法|不能|未能)核实.{0,8}(?:哪些|什么|何种)", question)
    )
    candidate_names_unverifiable_material_items = bool(
        re.search(
            r"(?:合同|协议|章程|名单|名册|表格|申请书|证明|证件|许可证|批文|"
            r"票据|凭证|记录|报告|文件|材料).{0,18}(?:无法|不能|未能|难以)核实",
            candidate_belief,
        )
        or re.search(
            r"(?:无法|不能|未能|难以)核实.{0,18}(?:合同|协议|章程|名单|名册|"
            r"表格|申请书|证明|证件|许可证|批文|票据|凭证|记录|报告|文件|材料)",
            candidate_belief,
        )
    )
    if asks_unverifiable_material_items and not candidate_names_unverifiable_material_items:
        violations.append("requested_unverifiable_material_items_missing")
    asks_current_ongoing_state = bool(
        re.search(r"(?:目前|现在|当前|现阶段)", question)
        and re.search(
            r"(?:登记在|产权|控制|占有|居住|生活|照料|照顾|抚养|工作|持有|保管|状态)",
            question,
        )
    )
    candidate_has_current_continuity = bool(
        re.search(r"(?:目前|现在|当前|现阶段|仍然|仍|一直|至今|截至|如今)", candidate_belief)
    )
    candidate_is_only_historical = bool(
        re.search(
            r"(?:19|20)\d{2}年|\d{1,2}月|\d{1,2}日|当时|次月|次年|此前|后来|随后|"
            r"婚后|离婚后|登记后|发生后|离婚时|结婚时",
            candidate_belief,
        )
        and not candidate_has_current_continuity
    )
    if asks_current_ongoing_state and candidate_is_only_historical:
        violations.append("requested_current_status_only_historical")
    custody_arrangement_requested = asks_child_custody_arrangement(question)
    custody_arrangement_present = identifies_child_custody_arrangement(candidate_belief)
    if custody_arrangement_requested and not custody_arrangement_present:
        violations.append("requested_child_custody_arrangement_missing")
    if (
        asks_asset_use_or_management(question)
        and not identifies_asset_use_or_management(candidate_belief)
    ):
        violations.append("requested_asset_use_or_management_missing")
    asks_received_medical_or_care = bool(
        re.search(
            r"(?:是否|有无).{0,12}(?:获得|接受|得到|安排).{0,12}"
            r"(?:医疗|治疗|救治|就医|照料|照顾|护理)",
            question,
        )
    )
    candidate_reports_medical_or_care = bool(
        re.search(
            r"(?:就医|就诊|住院|治疗|救治|医疗|护理|照料|照顾|送医|看医生|"
            r"未.{0,4}(?:就医|治疗|救治|照料|照顾))",
            candidate_belief,
        )
    )
    if asks_received_medical_or_care and not candidate_reports_medical_or_care:
        violations.append("requested_medical_or_care_response_missing")
    if (
        asks_contract_term(question)
        and not contract_term_answer_matches(question, candidate_belief)
        and not (custody_arrangement_requested and custody_arrangement_present)
        and not presupposition_correction_match(question, candidate_belief)
    ):
        violations.append("requested_contract_term_missing")
    violations.extend(contract_subattribute_violations(question, candidate_belief))
    if (
        asks_communication_content(question)
        and not identifies_communication_content(candidate_belief)
        and not presupposition_correction_match(question, candidate_belief)
    ):
        violations.append("requested_communication_content_missing")
    if (
        asks_communication_existence(question)
        and not identifies_communication_existence(candidate_belief)
        and not presupposition_correction_match(question, candidate_belief)
    ):
        violations.append("requested_communication_existence_missing")
    requested_speaker = attributed_statement_subject_role(question)
    if (
        requested_speaker is not None
        and attributed_statement_subject_role(candidate_belief) != requested_speaker
        and not presupposition_correction_match(question, candidate_belief)
    ):
        violations.append("requested_attributed_statement_subject_mismatch")
    if "渠道" in question and not any(
        marker in candidate_belief
        for marker in (
            "网络",
            "平台",
            "公众号",
            "网站",
            "门店",
            "线下",
            "微信",
            "短信",
            "电话",
            "直播",
            "广告",
            "海报",
        )
    ):
        violations.append("requested_channel_missing")
    if re.search(r"(?:你|您)本人是否|是否由(?:你|您)本人", question) and re.search(
        r"(?:我们|我方|公司).{0,16}(?:实施|投加|使用|操作|指使)", candidate_belief
    ) and not re.search(r"(?:我本人|本人|我亲自|我指使)", candidate_belief):
        violations.append("requested_individual_actor_ambiguous")
    asks_client_personal_action = bool(
        re.search(
            r"(?:您|你|本人).{0,12}(?:采取|实施|作出|进行|支付|退缴|赔偿|补偿|"
            r"提交|通知|整改|补正|归还|返还)",
            question,
        )
    )
    candidate_only_names_indeterminate_others = bool(
        re.search(
            r"(?:部分人员|部分人|有人|其他人|他人|若干人|多名人员|"
            r"[一二三四五六七八九十0-9]+人).{0,20}"
            r"(?:采取|实施|作出|进行|支付|退缴|赔偿|补偿|提交|通知|整改|补正|"
            r"归还|返还|提供|帮助)",
            candidate_belief,
        )
        and not re.search(
            r"(?:我本人|本人|我亲自|我已经|我已|我曾|我方|我们).{0,16}"
            r"(?:采取|实施|作出|进行|支付|退缴|赔偿|补偿|提交|通知|整改|补正|"
            r"归还|返还)",
            candidate_belief,
        )
    )
    if asks_client_personal_action and candidate_only_names_indeterminate_others:
        violations.append("requested_client_action_only_indeterminate_others")
    asks_client_actual_action = bool(
        re.search(
            r"(?:您|你|客户|本人).{0,18}(?:是否|有无|有没有|实际|明确|曾经|曾|"
            r"已经|已).{0,12}(?:告知|回答|披露|申报|提交|签署|支付|采取|实施|"
            r"发送|收到|同意|拒绝|参与)",
            question,
        )
        or re.search(
            r"(?:客户|本人).{0,18}(?:是否|有无|实际).{0,12}(?:履行|实施|作出)",
            question,
        )
    )
    candidate_reports_external_claim_about_client_action = bool(
        re.search(
            r"(?:对方|公司|保险公司|银行|平台|机关|部门|单位|医院|学校|"
            r"用人单位|建筑公司).{0,18}(?:称|主张|认为|表示|指称|指控|"
            r"理由是|抗辩).{0,36}(?:我|本人|客户).{0,12}"
            r"(?:未|没有|已|曾|实际)?(?:告知|回答|披露|申报|提交|签署|支付|"
            r"采取|实施|发送|收到|同意|拒绝|参与)",
            candidate_belief,
        )
        or re.search(
            r"(?:对方|公司|保险公司|银行|平台|机关|部门|单位|医院|学校|"
            r"用人单位|建筑公司).{0,12}(?:拒绝|拒赔|处罚|处理|决定).{0,12}"
            r"(?:理由|依据|原因).{0,6}(?:是|为).{0,24}(?:我|本人|客户).{0,12}"
            r"(?:未|没有|已|曾|实际)?(?:告知|回答|披露|申报|提交|签署|支付|"
            r"采取|实施|发送|收到|同意|拒绝|参与)",
            candidate_belief,
        )
    )
    if asks_client_actual_action and candidate_reports_external_claim_about_client_action:
        violations.append("reported_external_claim_not_client_actual_action")
    asks_directing_actor_identity = bool(
        re.search(r"(?:谁|哪一?(?:方|人|主体)).{0,12}(?:指示|指挥|安排|分配|管理)", question)
        or re.search(r"(?:指示|指挥|安排|分配|管理).{0,12}(?:谁|哪一?(?:方|人|主体))", question)
    )
    candidate_identifies_directing_actor = bool(
        re.search(
            r"(?:公司|单位|老板|负责人|经理|主管|法定代表人|雇主|上线|上级|"
            r"[\u4e00-\u9fff]{1,4}某|某[甲乙丙丁]).{0,12}(?:指示|指挥|安排|分配|管理)",
            candidate_belief,
        )
    )
    if asks_directing_actor_identity and not candidate_identifies_directing_actor:
        violations.append("requested_directing_actor_identity_missing")
    asks_recruited_person_identity = bool(
        re.search(
            r"(?:招揽|招募|挖走|挖角).{0,12}(?:哪些|什么|谁|具体).{0,8}(?:员工|人员|人|姓名)",
            question,
        )
        or re.search(
            r"(?:哪些|什么|谁|具体).{0,8}(?:员工|人员|人|姓名).{0,12}(?:招揽|招募|挖走|挖角)",
            question,
        )
        or re.search(
            r"被.{0,8}(?:招揽|招募|挖走|挖角).{0,8}(?:员工|人员|人|姓名)",
            question,
        )
    )
    candidate_identifies_recruited_person = bool(
        re.search(
            r"(?:[\u4e00-\u9fff]{1,4}某|某[甲乙丙丁]|(?:技术|研发|销售|财务|"
            r"行政|人事|生产|项目|部门).{0,6}(?:负责人|经理|主管|员工|人员))"
            r".{0,20}(?:招揽|招募|挖走|挖角|加入)",
            candidate_belief,
        )
        or re.search(
            r"(?:招揽|招募|挖走|挖角|拉拢).{0,20}"
            r"(?:[\u4e00-\u9fff]{1,4}某|某[甲乙丙丁]|[一二三四五六七八九十0-9]+人)",
            candidate_belief,
        )
    )
    if asks_recruited_person_identity and not candidate_identifies_recruited_person:
        violations.append("requested_recruited_person_identity_missing")
    asks_application_acceptance = bool(
        re.search(
            r"(?:申请|申报).{0,16}(?:是否|有无|有没有|已经|已|正式)?.{0,6}(?:受理|收件)",
            question,
        )
    )
    candidate_states_application_acceptance = bool(
        re.search(
            r"(?:申请|申报).{0,16}(?:已经|已|正式|予以|不予|未|尚未|没有).{0,4}"
            r"(?:受理|收件)|(?:受理|不予受理|未受理|受理通知|收件回执)",
            candidate_belief,
        )
    )
    if asks_application_acceptance and not candidate_states_application_acceptance:
        violations.append("requested_application_acceptance_missing")
    if re.search(r"(?:收款|付款|支付|结算)(?:的)?(?:具体)?方式", question) and not re.search(
        r"(?:转账|汇款|现金|扫码|刷卡|支付平台|银行卡.{0,8}(?:交易|收款|支付|转账)|支票|承兑)",
        candidate_belief,
    ):
        violations.append("requested_payment_method_missing")
    asks_basis_document_identity = bool(
        "所依据" in question
        and re.search(r"(?:文件|资料|文书|规划|规定)", question)
        and re.search(r"(?:名称|全称|文号|编号|哪一份|什么文件)", question)
    )
    candidate_identifies_basis_document = bool(
        re.search(
            r"(?:依据|根据|依照|援引|引用|以.{0,16}为由|规定|报批稿|规划稿|规划文件)",
            candidate_belief,
        )
    )
    if asks_basis_document_identity and not candidate_identifies_basis_document:
        violations.append("requested_basis_document_role_missing")
    asks_authority_report = bool(
        re.search(
            r"(?:向|给).{0,12}(?:有关部门|行政机关|办案机关|公安|警方|检察院|法院)"
            r".{0,8}(?:报告|举报|反映|报案|投案|自首)",
            question,
        )
        or re.search(
            r"(?:报告|举报|反映|报案|投案|自首).{0,12}"
            r"(?:有关部门|行政机关|办案机关|公安|警方|检察院|法院)",
            question,
        )
    )
    candidate_reports_to_authority = bool(
        re.search(
            r"(?:向|给).{0,12}(?:有关部门|行政机关|办案机关|公安|警方|检察院|法院)"
            r".{0,8}(?:报告|举报|反映|报案|投案|自首)",
            candidate_belief,
        )
        or re.search(
            r"(?:主动)?(?:报告|举报|反映|报案|投案|自首).{0,12}"
            r"(?:有关部门|行政机关|办案机关|公安|警方|检察院|法院)",
            candidate_belief,
        )
    )
    if asks_authority_report and not candidate_reports_to_authority:
        violations.append("requested_authority_report_action_missing")
    asks_geographic_range = bool(
        re.search(r"(?:地理|地域|地区|区域).{0,6}(?:范围|分布)", question)
        or re.search(r"哪些(?:国家|省份|省|城市|市|区县|县|地区|区域)", question)
    )
    candidate_identifies_geography = bool(
        re.search(
            r"(?:中国|我国|境内|境外|国内|国外|全国|海外|全球|"
            r"[\u4e00-\u9fff]{2,8}(?:省|自治区|特别行政区|市|区|县))",
            candidate_belief,
        )
    )
    if asks_geographic_range and not candidate_identifies_geography:
        violations.append("requested_geographic_range_missing")
    if asks_target_audience(question) and not identifies_target_audience(candidate_belief):
        violations.append("requested_target_audience_missing")
    asks_precise_time = bool(
        re.search(r"(?:具体|准确|确切)(?:的)?(?:日期|时间|时点)", question)
        or re.search(r"(?:日期|时间|时点).{0,5}(?:具体|准确|确切)", question)
        or re.search(r"哪一天|几月几日|几点(?:几分)?|几时(?:几分)?", question)
    )
    candidate_has_precise_time = bool(
        re.search(
            r"\d{4}年|\d{1,2}月|\d{1,2}日|\d{1,2}(?:时|点)(?:\d{1,2}分)?|"
            r"次日|翌日|当天|当日|次月",
            candidate_belief,
        )
    )
    if asks_precise_time and not candidate_has_precise_time:
        violations.append("requested_precise_time_missing")
    asks_calendar_year = bool(
        re.search(r"(?:哪|何|几)一年|(?:具体)?年份|哪年", question)
    )
    candidate_has_calendar_year = bool(
        re.search(r"(?:19|20)\d{2}年|(?:哪|某|当|次|去|今|明)年", candidate_belief)
    )
    if asks_calendar_year and not candidate_has_calendar_year:
        violations.append("requested_calendar_year_missing")
    asks_calendar_month = bool(
        re.search(r"(?:哪|何|几)一?个月|(?:具体)?月份|哪月|几月", question)
    )
    candidate_has_calendar_month = bool(
        re.search(r"\d{1,2}月|(?:某|当|次|上|本|下)月", candidate_belief)
    )
    if asks_calendar_month and not candidate_has_calendar_month:
        violations.append("requested_calendar_month_missing")
    asks_purchase_funding = bool(
        re.search(
            r"(?:购房|购买房屋|房屋.{0,4}(?:购置|购买)|购置房屋).{0,12}"
            r"(?:出资|资金来源|款项来源|购房款|首付)",
            question,
        )
        or re.search(
            r"(?:出资|资金来源|款项来源|购房款|首付).{0,12}"
            r"(?:购房|购买房屋|房屋.{0,4}(?:购置|购买)|购置房屋)",
            question,
        )
    )
    candidate_identifies_purchase_funding = bool(
        re.search(
            r"(?:出资|购房款|首付|按揭款|贷款|房款|全款|资金来源|"
            r"支付.{0,6}(?:购房|房屋|房款)|付款.{0,6}(?:购房|房屋|房款))",
            candidate_belief,
        )
    )
    if asks_purchase_funding and not candidate_identifies_purchase_funding:
        violations.append("requested_purchase_funding_missing")
    asks_registered_ownership_share = bool(
        re.search(
            r"(?:产权|登记|房产证|不动产权证).{0,10}(?:份额|比例|各占|占比)",
            question,
        )
        or re.search(
            r"(?:份额|比例|各占|占比).{0,10}(?:产权|登记|房产证|不动产权证)",
            question,
        )
    )
    candidate_identifies_ownership_share = bool(
        re.search(
            r"(?:共同共有|按份共有|各占|占有.{0,4}(?:份额|比例)|"
            r"份额.{0,6}(?:为|是|记载|明确)|二分之一|一半|[0-9]+(?:\.[0-9]+)?%)",
            candidate_belief,
        )
    )
    if asks_registered_ownership_share and not candidate_identifies_ownership_share:
        violations.append("requested_registered_ownership_share_missing")
    asks_pre_application_communication = bool(
        re.search(
            r"(?:申请|申报).{0,12}前.{0,12}(?:沟通|联系|询问|咨询|交涉)",
            question,
        )
        or re.search(
            r"(?:沟通|联系|询问|咨询|交涉).{0,12}(?:申请|申报).{0,6}前",
            question,
        )
    )
    candidate_places_communication_before_application = bool(
        re.search(
            r"(?:申请|申报).{0,10}前.{0,16}(?:沟通|联系|询问|咨询|交涉|告知|答复)",
            candidate_belief,
        )
        or re.search(
            r"(?:事先|预先|此前).{0,16}(?:沟通|联系|询问|咨询|交涉|告知|答复)",
            candidate_belief,
        )
    )
    if (
        asks_pre_application_communication
        and not candidate_places_communication_before_application
    ):
        violations.append("requested_pre_application_communication_missing")
    asks_data_use_purpose = bool(
        re.search(
            r"(?:数据|信息).{0,12}(?:用于|用途|使用场景|商业目的|经营目的)",
            question,
        )
        or re.search(
            r"(?:用于|用途|使用场景|商业目的|经营目的).{0,12}(?:数据|信息)",
            question,
        )
    )
    candidate_identifies_data_use_purpose = bool(
        re.search(
            r"(?:将|把|利用|使用).{0,10}(?:数据|信息).{0,12}"
            r"(?:用于|加工成|制作成|提供|出售|销售|收费|获利|盈利)",
            candidate_belief,
        )
        or re.search(
            r"(?:数据|信息).{0,12}(?:用于|加工成|制作成|有偿提供|收费提供|"
            r"出售|销售|获利|盈利|价格监测|市场分析|定制API)",
            candidate_belief,
        )
    )
    if asks_data_use_purpose and not candidate_identifies_data_use_purpose:
        violations.append("requested_data_use_purpose_missing")
    asks_caregiver_identity = bool(
        re.search(
            r"(?:由谁|谁).{0,10}(?:照料|照顾|抚养|看护|负责.{0,4}(?:生活|起居))",
            question,
        )
        or re.search(
            r"(?:照料|照顾|抚养|看护).{0,10}(?:人是谁|是谁|由谁)",
            question,
        )
    )
    candidate_identifies_caregiver = bool(
        re.search(
            r"(?:由|跟随)(?:我|本人|父亲|母亲|爸爸|妈妈|继父|继母|丈夫|妻子|"
            r"祖父|祖母|外祖父|外祖母|对方).{0,5}(?:照料|照顾|抚养|看护)",
            candidate_belief,
        )
        or re.search(
            r"(?:我|本人|父亲|母亲|爸爸|妈妈|继父|继母|丈夫|妻子|祖父|祖母|"
            r"外祖父|外祖母|对方).{0,6}(?:实际|主要|直接)?负责.{0,5}"
            r"(?:照料|照顾|抚养|看护|生活|起居)",
            candidate_belief,
        )
        or re.search(
            r"(?:随|跟随|跟|在)(?:我|本人|父亲|母亲|爸爸|妈妈|继父|继母|丈夫|"
            r"妻子|祖父|祖母|外祖父|外祖母|对方).{0,5}(?:这里|那里|处|家中|家里)?"
            r"(?:生活|居住)",
            candidate_belief,
        )
    )
    if asks_caregiver_identity and not candidate_identifies_caregiver:
        violations.append("requested_caregiver_identity_missing")
    asks_report_workflow_or_actor = bool(
        re.search(
            r"(?:哪些?部门(?:或人员)?|哪些?人员(?:或部门)?|谁|何人).{0,24}"
            r"(?:参与|负责|制作|编制|审核|复核|签批|处理)",
            question,
        )
        or re.search(
            r"(?:报告|检测报告).{0,18}"
            r"(?:制作|编制|审核|复核|签批|出具|生成|数据处理|数据校验).{0,16}"
            r"(?:流程|过程|环节|谁|人员|部门|参与|负责|如何|怎样)",
            question,
        )
        or re.search(
            r"(?:流程|过程|环节).{0,16}(?:报告|检测报告).{0,18}"
            r"(?:制作|编制|审核|复核|签批|出具|生成|数据处理|数据校验)",
            question,
        )
    )
    asks_report_content = not asks_report_workflow_or_actor and bool(
        re.search(
            r"(?:报告|检测报告).{0,16}"
            r"(?:内容|记载|写明|载明|显示|列明|反映|"
            r"哪些数据|什么数据|何种数据|数据(?:是|为|如何)|结论|结果)",
            question,
        )
        or re.search(
            r"(?:哪些|什么|何种|具体).{0,6}(?:内容|数据|结论|结果).{0,12}"
            r"(?:报告|检测报告)",
            question,
        )
    )
    candidate_identifies_report_content = bool(
        re.search(
            r"(?:报告|检测报告).{0,28}(?:写明|载明|记载|显示|结论|结果|数据|数值|"
            r"合格|不合格|超标|未检出|检出|浓度|含量)",
            candidate_belief,
        )
        or re.search(
            r"(?:检测|监测).{0,12}(?:数据|数值|结论|结果).{0,16}(?:为|是|显示|表明)",
            candidate_belief,
        )
    )
    if asks_report_content and not candidate_identifies_report_content:
        violations.append("requested_report_content_missing")
    assessment_subject = re.search(
        r"(?:评估|认定|判断)(?P<subject>[\u4e00-\u9fff]{2,8})风险"
        r".{0,16}(?:依据|标准|数据|步骤|方法)",
        question,
    )
    if assessment_subject is not None:
        subject = assessment_subject.group("subject")
        subject_present = subject in candidate_belief
        if "保证人" in subject:
            subject_present = subject_present or bool(
                re.search(r"保证人|担保人|人保|物保|担保", candidate_belief)
            )
        if not subject_present:
            violations.append("requested_assessment_subject_missing")
    return violations


def direct_answer_attribute_explicit_match(question: str, candidate_belief: str) -> bool:
    """Confirm narrow attributes used by exhaustive cooperative recovery.

    This is deliberately stricter than ordinary semantic selection.  It only
    supplies positive evidence when the requested attribute is explicit in the
    candidate, including an explicit negative answer to an action question.
    """

    asks_geographic_range = bool(
        re.search(r"(?:地理|地域|地区|区域).{0,6}(?:范围|分布)", question)
        or re.search(r"哪些(?:国家|省份|省|城市|市|区县|县|地区|区域)", question)
    )
    candidate_identifies_geography = bool(
        re.search(
            r"(?:中国|我国|境内|境外|国内|国外|全国|海外|全球|"
            r"[\u4e00-\u9fff]{2,8}(?:省|自治区|特别行政区|市|区|县))",
            candidate_belief,
        )
    )
    if asks_geographic_range and candidate_identifies_geography:
        return True
    if asks_target_audience(question) and identifies_target_audience(candidate_belief):
        return True
    if (
        asks_contract_term(question)
        and contract_term_answer_matches(question, candidate_belief)
        and not contract_subattribute_violations(question, candidate_belief)
    ):
        return True
    if asks_communication_content(question) and identifies_communication_content(
        candidate_belief
    ):
        return True
    if asks_communication_existence(question) and identifies_communication_existence(
        candidate_belief
    ):
        return True
    if renewal_signature_answer_matches(question, candidate_belief):
        return True

    # Compound natural questions often express a concrete Boolean attribute as
    # one clause (``是否设置弹窗、查看路径是否清楚``).  A verifier can mistakenly
    # summarize the candidate's main predicate as the surrounding event
    # (``发送站内消息``) even though the candidate explicitly answers the queried
    # attribute (``没有弹窗``).  Recover only literal, clause-local polar answers;
    # sharing a topic or actor is insufficient.
    polar_object = re.compile(
        r"(?:是否|有无|有没有)(?:设置|提供|出现|显示|存在|具备|包含|包括)?"
        r"(?P<object>[\u4e00-\u9fffA-Za-z0-9]{1,8})(?=、|，|。|；|？|\?|$)"
    )
    for match in polar_object.finditer(question):
        requested_object = match.group("object")
        if re.search(
            rf"(?:没有|并未|未曾|从未|未|不设|不提供|有|已|设置|提供|出现|显示|"
            rf"存在|具备|包含|包括).{{0,4}}{re.escape(requested_object)}",
            candidate_belief,
        ):
            return True
    polar_state = re.compile(
        r"(?P<object>[\u4e00-\u9fffA-Za-z0-9]{2,10})(?:是否|是不是)"
        r"(?P<state>清楚|明确|显著|可见|可用|完整|有效|一致|正常)"
    )
    for match in polar_state.finditer(question):
        requested_object = match.group("object")
        requested_state = match.group("state")
        if re.search(
            rf"{re.escape(requested_object)}.{{0,6}}(?:不|并不|不够|比较|很|较|"
            rf"十分|非常)?{re.escape(requested_state)}",
            candidate_belief,
        ):
            return True

    # A date may be expressed as a calendar month or as a relative month.  It is
    # a safe exhaustive-recovery signal only when both texts explicitly concern
    # the same audited event (for example, adding a name to the registration).
    # This deliberately does not let a marriage/registration date answer a
    # purchase or repayment-date question.
    asks_precise_time = bool(
        re.search(r"(?:具体|准确|确切)(?:的)?(?:日期|时间|时点)", question)
        or re.search(r"(?:日期|时间|时点).{0,5}(?:具体|准确|确切)", question)
        or re.search(r"哪一天|几月几日|几点(?:几分)?|几时(?:几分)?", question)
    )
    asks_event_time = asks_precise_time or bool(
        re.search(r"(?:何时|什么时候|哪年|哪月)", question)
    )
    candidate_has_precise_time = bool(
        re.search(
            r"\d{4}年|\d{1,2}月|\d{1,2}日|\d{1,2}(?:时|点)(?:\d{1,2}分)?|"
            r"次日|翌日|当天|当日|次月",
            candidate_belief,
        )
    )
    if (
        asks_event_time
        and candidate_has_precise_time
        and event_attribute_compatible(question, candidate_belief) is True
    ):
        return True
    asks_start_time = bool(
        re.search(r"(?:起始|开始).{0,6}(?:日期|时间|时点)", question)
        or re.search(r"(?:何时|什么时候|哪年|哪月).{0,10}(?:开始|起始)", question)
    )
    candidate_states_start_time = bool(
        re.search(
            r"(?:从|自)?(?:19|20)\d{2}年(?:\d{1,2}月)?(?:起|开始)",
            candidate_belief,
        )
    )
    shared_start_object = any(
        marker in question and marker in candidate_belief
        for marker in (
            "标识",
            "商标",
            "软件名称",
            "域名",
            "产品",
            "房屋",
            "合同",
            "协议",
            "工作",
            "经营",
            "销售",
        )
    )
    if asks_start_time and candidate_states_start_time and shared_start_object:
        return True

    asks_recruited_identity = bool(
        re.search(
            r"(?:招揽|招募|挖走|挖角).{0,12}(?:哪些|什么|谁|具体).{0,8}"
            r"(?:员工|人员|人|姓名)",
            question,
        )
        or re.search(
            r"(?:哪些|什么|谁|具体).{0,8}(?:员工|人员|人|姓名).{0,12}"
            r"(?:招揽|招募|挖走|挖角)",
            question,
        )
        or re.search(
            r"被.{0,8}(?:招揽|招募|挖走|挖角).{0,8}(?:员工|人员|人|姓名)",
            question,
        )
    )
    candidate_names_recruited_person = bool(
        re.search(
            r"(?:[\u4e00-\u9fff]{1,4}某|某[甲乙丙丁]|(?:技术|研发|销售|财务|"
            r"行政|人事|生产|项目|部门).{0,6}(?:负责人|经理|主管|员工|人员))"
            r".{0,20}(?:招揽|招募|挖走|挖角|加入)",
            candidate_belief,
        )
        or re.search(
            r"(?:招揽|招募|挖走|挖角|拉拢).{0,20}"
            r"(?:[\u4e00-\u9fff]{1,4}某|某[甲乙丙丁]|[一二三四五六七八九十0-9]+人)",
            candidate_belief,
        )
    )
    if asks_recruited_identity and candidate_names_recruited_person:
        return True

    for match in re.finditer(
        r"采取(?:了|过)?(?:哪些|什么)?(?P<action>[\u4e00-\u9fff]{2,8})(?:措施|行为)",
        question,
    ):
        action = match.group("action")
        if re.search(
            rf"(?:没有|并未|未曾|从未|不曾|不加|未).{{0,4}}{re.escape(action)}",
            candidate_belief,
        ):
            return True
    return False


def contract_subattribute_violations(question: str, candidate_belief: str) -> list[str]:
    """Require a contract answer to address the particular term being requested.

    A statement that a contract contains *some* substantive term is not a closed,
    deterministic answer to a question about a different term.  This distinction
    matters only for the bounded recovery after the model has returned an empty
    set: ordinary model selection may still use semantic context, but deterministic
    recovery must prove that the same observable attribute occurs on both sides.

    The topics below are legal-document attributes rather than case identifiers.
    They therefore apply across contract, labour, lending, data, and procurement
    matters and do not encode the answer to any qualification case.
    """

    violations: list[str] = []

    asks_quality_standard = bool(
        re.search(
            r"(?:质量|产品|技术).{0,10}(?:标准|规格)|(?:标准|规格).{0,10}质量",
            question,
        )
    )
    identifies_quality_standard = bool(
        re.search(
            r"(?:质量|产品|技术).{0,12}(?:标准|规格)|"
            r"(?:标准|规格).{0,12}(?:质量|产品|技术)|ECE\s*R?\d+",
            candidate_belief,
            flags=re.IGNORECASE,
        )
    )
    if asks_quality_standard and not identifies_quality_standard:
        violations.append("requested_quality_standard_term_missing")

    asks_applicable_law = bool(
        re.search(r"(?:适用法律|准据法|适用.{0,6}(?:法律|法|公约))", question)
    )
    identifies_applicable_law = bool(
        re.search(
            r"(?:适用法律|准据法|中国法|外国法|[A-Z]*CISG|联合国.{0,8}公约)",
            candidate_belief,
            flags=re.IGNORECASE,
        )
    )
    if asks_applicable_law and not identifies_applicable_law:
        violations.append("requested_applicable_law_term_missing")

    asks_overdue_interest = bool(
        re.search(r"(?:逾期|迟延).{0,10}(?:利息|利率|罚息)", question)
        or re.search(r"(?:利息|利率|罚息).{0,10}(?:标准|比例|多少|约定)", question)
    )
    identifies_overdue_interest = bool(
        re.search(r"(?:逾期|迟延).{0,12}(?:利息|利率|罚息)", candidate_belief)
        or re.search(
            r"(?:年利率|月利率|日利率|罚息率|LPR|万分之|千分之|百分之)",
            candidate_belief,
        )
    )
    if asks_overdue_interest and not identifies_overdue_interest:
        violations.append("requested_overdue_interest_term_missing")

    asks_payment_condition = bool(
        re.search(r"(?:付款|支付|结算).{0,10}(?:条件|前提|触发|须|需要)", question)
        or re.search(r"(?:条件|前提).{0,10}(?:付款|支付|结算)", question)
    )
    identifies_payment_condition = bool(
        re.search(
            r"(?:付款|支付|结算).{0,18}(?:条件|前提|须|应在|验收|交付|开票|发票|审批)",
            candidate_belief,
        )
        or re.search(
            r"(?:验收|交付|开票|发票|审批).{0,18}(?:后|前|完成).{0,8}(?:付款|支付|结算)",
            candidate_belief,
        )
        or re.search(
            r"(?:每天|每日|每周|每月|每季|每季度|每年|按日|按周|按月|按季|按年)"
            r".{0,8}(?:付款|支付|结算)",
            candidate_belief,
        )
        or re.search(
            r"(?:付款|支付|结算).{0,8}(?:每天|每日|每周|每月|每季|每季度|每年|"
            r"按日|按周|按月|按季|按年)",
            candidate_belief,
        )
    )
    if asks_payment_condition and not identifies_payment_condition:
        violations.append("requested_payment_condition_term_missing")

    asks_payment_deadline = bool(
        re.search(r"(?:付款|支付|结算).{0,12}(?:期限|截止|最迟|日期|时间)", question)
        or re.search(r"(?:期限|截止|最迟).{0,12}(?:付款|支付|结算)", question)
    )
    identifies_payment_deadline = bool(
        re.search(
            r"(?:付款|支付|结算).{0,18}(?:(?:19|20)\d{2}年|\d{1,2}月|\d+日内|期限|截止|最迟)",
            candidate_belief,
        )
        or re.search(
            r"(?:(?:19|20)\d{2}年|\d{1,2}月|\d+日内|期限|截止|最迟).{0,18}(?:付款|支付|结算)",
            candidate_belief,
        )
    )
    if asks_payment_deadline and not identifies_payment_deadline:
        violations.append("requested_payment_deadline_term_missing")

    asks_supply_frequency = bool(
        re.search(r"(?:供货|供应|交付|送货).{0,12}(?:频率|周期|间隔|多久一次|每隔)", question)
        or re.search(r"(?:频率|周期|间隔|多久一次|每隔).{0,12}(?:供货|供应|交付|送货)", question)
    )
    identifies_supply_frequency = bool(
        re.search(
            r"(?:供货|供应|交付|送货).{0,18}(?:每天|每日|每周|每月|每季|每年|每隔|定期|不定期|一次)",
            candidate_belief,
        )
        or re.search(
            r"(?:每天|每日|每周|每月|每季|每年|每隔|定期|不定期).{0,18}(?:供货|供应|交付|送货)",
            candidate_belief,
        )
    )
    if asks_supply_frequency and not identifies_supply_frequency:
        violations.append("requested_supply_frequency_term_missing")

    asks_supply_time = bool(
        re.search(r"(?:供货|供应|交付|送货).{0,12}(?:时间|日期|期限|何时|什么时候)", question)
        or re.search(r"(?:何时|什么时候|日期|期限).{0,12}(?:供货|供应|交付|送货)", question)
    )
    identifies_supply_time = bool(
        re.search(
            r"(?:供货|供应|交付|送货).{0,18}(?:(?:19|20)\d{2}年|\d{1,2}月|\d+日内|期限|之前|之后)",
            candidate_belief,
        )
        or re.search(
            r"(?:(?:19|20)\d{2}年|\d{1,2}月|\d+日内|期限|之前|之后).{0,18}(?:供货|供应|交付|送货)",
            candidate_belief,
        )
    )
    if asks_supply_time and not identifies_supply_time:
        violations.append("requested_supply_time_term_missing")

    asks_data_use_scope = bool(
        re.search(
            r"(?:数据).{0,18}(?:使用|利用|加工).{0,12}(?:范围|限制|边界|用途|目的)",
            question,
        )
        or re.search(
            r"(?:范围|限制|边界|用途|目的).{0,12}(?:数据).{0,12}(?:使用|利用|加工)",
            question,
        )
    )
    identifies_data_use_scope = bool(
        re.search(
            r"(?:数据).{0,18}(?:使用|利用|加工).{0,12}(?:范围|限于|仅限|不得|可以|用途|目的)",
            candidate_belief,
        )
        or re.search(
            r"(?:数据).{0,12}(?:仅限|限于|不得|可以).{0,12}(?:用于|使用|利用|加工|提供)",
            candidate_belief,
        )
        or re.search(
            r"(?:仅限|不得|可以).{0,12}(?:将|对)?(?:该|这些)?数据.{0,12}(?:使用|利用|加工|提供)",
            candidate_belief,
        )
    )
    if asks_data_use_scope and not identifies_data_use_scope:
        violations.append("requested_data_use_scope_term_missing")

    asks_acceleration = bool(
        re.search(r"(?:提前清偿|提前到期|加速到期).{0,16}(?:条款|条件|情形|约定)", question)
        or re.search(r"(?:条款|条件|情形|约定).{0,16}(?:提前清偿|提前到期|加速到期)", question)
    )
    identifies_acceleration = bool(
        re.search(r"(?:提前清偿|提前到期|加速到期)", candidate_belief)
    )
    if asks_acceleration and not identifies_acceleration:
        violations.append("requested_acceleration_term_missing")

    asks_renewal_terms = bool(
        re.search(
            r"(?:续签|续订|续约).{0,18}(?:实际|具体).{0,8}(?:内容|条款|约定)",
            question,
        )
        or re.search(
            r"(?:实际|具体).{0,8}(?:内容|条款|约定).{0,18}(?:续签|续订|续约)",
            question,
        )
    )
    identifies_renewal_terms = bool(
        re.search(
            r"(?:续签|续订|续约).{0,24}(?:期限|工资|薪酬|岗位|工作地点|职责|待遇|条款|内容)",
            candidate_belief,
        )
        or re.search(
            r"(?:期限|工资|薪酬|岗位|工作地点|职责|待遇).{0,24}(?:续签|续订|续约)",
            candidate_belief,
        )
    )
    if asks_renewal_terms and not identifies_renewal_terms:
        violations.append("requested_renewal_terms_missing")

    return violations


def asks_contract_term(question: str) -> bool:
    """Return whether a question requests the substantive content of an agreement.

    Agreement provenance, signature, date, or legal effect are separate attributes.
    Chinese lawyers commonly ask for the content without using the literal word
    ``条款`` (for example, ``协议具体写了哪些内容``), so the contract must cover
    both formal and ordinary phrasings.
    """

    document = r"(?:合同|协议|约定|承诺书)"
    content_request = (
        r"(?:条款|是否包含|"
        r"(?:具体|主要|相关)?内容|写了(?:哪些|什么)|"
        r"写明(?:了)?(?:哪些|什么)?|载明(?:了)?(?:哪些|什么)?|"
        r"包括(?:哪些|什么)|包含(?:哪些|什么)|"
        r"(?:具体|主要|相关)(?:约定|规定)|"
        r"(?:怎样|如何|怎么|是否)(?:具体)?(?:约定|规定)|"
        r"(?:约定|规定)(?:了)?(?:哪些|什么))"
    )
    term_topic = (
        r"(?:供货|供应|交付|送货|付款|支付|结算|逾期|利息|利率|罚息|"
        r"期限|截止|数据|使用|利用|加工|清偿|提前到期|加速到期|"
        r"工资|薪酬|岗位|工作地点|职责|待遇|保险|社保|补助)"
    )
    return bool(
        re.search(rf"{document}.{{0,24}}{content_request}", question)
        or re.search(rf"{content_request}.{{0,16}}{document}", question)
        or re.search(rf"{document}.{{0,24}}(?:约定|规定)(?:的)?{term_topic}", question)
    )


def identifies_contract_term(candidate_belief: str) -> bool:
    """Return whether a belief states a term rather than agreement metadata."""

    # Merely saying that the existence or content of a term is disputed, unknown,
    # or still to be determined does not state that term.  This distinction is
    # especially important in opening statements: otherwise a question asking
    # for the actual clause can be mislabeled as an opening repeat before the
    # simulator reaches hidden beliefs that contain the answer.  Explicit absence
    # (for example, ``未约定质量标准``) is handled separately below by
    # ``contract_term_answer_matches`` and remains a valid direct answer.
    reports_only_term_uncertainty = bool(
        re.search(
            r"(?:对|关于).{0,40}(?:是否|有无|如何).{0,24}"
            r"(?:存在争议|有争议|尚有争议|不清楚|不确定|尚不明确|待核实|需核实)",
            candidate_belief,
        )
        or re.search(
            r"(?:合同|协议|约定|条款|质量标准|适用法律).{0,30}"
            r"(?:是否|有无).{0,20}"
            r"(?:存在争议|有争议|不清楚|不确定|尚不明确|待核实|需核实)",
            candidate_belief,
        )
    )
    if reports_only_term_uncertainty:
        return False

    formal_term = bool(
        re.search(
            r"(?:合同|协议|约定|承诺书).{0,28}(?:条款|约定|规定|写明|载明|"
            r"明确|列作|提前到期|加速到期)",
            candidate_belief,
        )
        or re.search(
            r"(?:条款|约定|规定|写明|载明|明确|列作).{0,20}"
            r"(?:合同|协议|承诺书)",
            candidate_belief,
        )
    )
    # ``双方约定不缴社保而改发补助`` states the bargain directly even though
    # it does not repeat 合同/条款.  Require an agreement-making subject before
    # 约定 and a deontic/substantive continuation after it, which excludes
    # metadata such as ``这份约定是公司预先打印的``.
    substantive_bargain = bool(
        re.search(
            r"(?:双方|当事人|甲方|乙方|公司|单位|雇主|劳动者|借款人|贷款人)"
            r".{0,12}约定(?:不|未|须|应|可|可以|不得|由|将|把|按|若|如|每|任何)",
            candidate_belief,
        )
    )
    return formal_term or substantive_bargain


def contract_term_answer_matches(question: str, candidate_belief: str) -> bool:
    """Recognize a stated term or an explicit same-topic absence of a term.

    A client can answer a request for contractual content by saying that the
    relevant instrument or course of dealing did not contain that term.  The
    previous generic contract-content guard accepted positive clauses but
    rejected these negative answers, even when the same requested topic was
    explicit on both sides.  Keep this recovery closed-world: absence language
    alone is insufficient, and the question and belief must share an audited
    substantive topic.
    """

    if identifies_contract_term(candidate_belief):
        return True
    explicitly_absent = bool(
        re.search(
            r"(?:没有|并未|未曾|从未|未|不含|不包含).{0,10}"
            r"(?:书面)?(?:约定|规定|写明|载明|记载|包含|条款)",
            candidate_belief,
        )
        or re.search(
            r"(?:约定|规定|条款).{0,8}(?:不存在|没有|并未|未曾|从未)",
            candidate_belief,
        )
        or (
            re.search(
                r"(?:合同|协议|承诺书|形式发票|订单|报价单|采购单|"
                r"订单确认|合同附件|技术协议|书面|交易)",
                candidate_belief,
            )
            and re.search(
                r"(?:没有|并未|未曾|从未|未含|不含|不包含).{0,12}"
                r"(?:质量标准|产品标准|技术标准|规格约定|约定规格|"
                r"适用法律|准据法|付款|支付|结算|供货|"
                r"交付|逾期|利息|利率|数据|续签|续订|保险|社保|补助|"
                r"提前到期|违约责任|赔偿)",
                candidate_belief,
            )
        )
        or re.search(
            r"(?:双方|当事人|合同|协议).{0,12}"
            r"(?:没有|没|并未|未曾|未)(?:选|选择|选定|指定|约定).{0,8}"
            r"(?:适用)?(?:法律|准据法)",
            candidate_belief,
        )
        or re.search(
            r"(?:没有|没|并未|未曾|未)(?:选|选择|选定|指定|约定).{0,8}"
            r"(?:适用)?(?:法律|准据法)",
            candidate_belief,
        )
    )
    if not explicitly_absent:
        return False

    shared_topic_patterns = (
        r"(?:质量标准|产品质量|质量|规格|技术标准|产品标准|ECE\s*R?\d+)",
        r"(?:适用法律|准据法|中国法|外国法|[A-Z]*CISG|公约)",
        r"(?:付款|支付|结算)",
        r"(?:供货|供应|交付|送货)",
        r"(?:逾期|利息|利率|罚息|LPR)",
        r"(?:数据.{0,8}(?:使用|利用|加工)|使用范围|用途)",
        r"(?:续签|续订|续约|合同期限|工资|薪酬|岗位|工作地点)",
        r"(?:保险|社保|补助)",
        r"(?:提前清偿|提前到期|加速到期)",
        r"(?:违约责任|赔偿|损失|责任分配)",
    )
    return any(
        re.search(pattern, question, flags=re.IGNORECASE)
        and re.search(pattern, candidate_belief, flags=re.IGNORECASE)
        for pattern in shared_topic_patterns
    )


def asks_communication_content(question: str) -> bool:
    """Return whether a question asks what a communication or speaker said.

    The requested proposition can be introduced by a document/message noun or
    directly by an attributed-speech expression such as ``公司具体怎么说``.
    Provenance, delivery, timing, and the circumstances in which a statement was
    made remain separate attributes.
    """

    communication = (
        r"(?:通知|通知书|提醒|消息|短信|邮件|答复|回复|批复|催告|催告函|函件)"
    )
    content_request = (
        r"(?:(?:具体|主要|相关)?(?:内容|理由|说法)|"
        r"(?:写了|写明|载明|提到)(?:哪些|什么)?|"
        r"说明(?:了)?(?:哪些|什么|何种|具体内容)|"
        r"(?:告知|要求)(?:了)?(?:哪些|什么))"
    )
    attributed_content_request = (
        r"(?:"
        r"(?:具体|详细)?(?:是)?(?:怎么|如何)(?:说|表述|解释|答复|回复|告知)|"
        r"(?:说|称|表示|解释).{0,6}(?:为什么|为何|原因|理由)|"
        r"(?:声称|表示|主张|答复|回复|告知|承诺|解释)(?:的)?"
        r"(?:具体|主要|相关)?(?:内容|说法|理由|表述|原话|细节)|"
        r"(?:具体|主要|相关)?(?:说法|表述|原话|理由)(?:是什么|有哪些|包括|包含)"
        r")"
    )
    return bool(
        re.search(rf"{communication}.{{0,20}}(?:包含|包括)?{content_request}", question)
        or re.search(rf"{content_request}.{{0,16}}{communication}", question)
        or re.search(attributed_content_request, question)
    )


def asks_communication_existence(question: str) -> bool:
    """Whether a question asks if a notice/message/reply actually existed or moved."""

    communication = (
        r"(?:通知|通知书|提醒|消息|短信|邮件|答复|回复|批复|催告|催告函|函件)"
    )
    transmission = r"(?:发出|发过|发送|送达|收到|作出|出具|发布|提供|寄出|寄送)"
    polar = r"(?:是否|有无|有没有)"
    return bool(
        re.search(rf"{polar}.{{0,40}}{transmission}.{{0,32}}{communication}", question)
        or re.search(rf"{polar}.{{0,32}}{communication}.{{0,20}}{transmission}", question)
        or re.search(rf"{communication}.{{0,20}}{polar}.{{0,20}}{transmission}", question)
        or re.search(rf"(?:有无|有没有).{{0,20}}{communication}", question)
    )


def identifies_communication_existence(candidate_belief: str) -> bool:
    """Whether a belief states communication issuance/receipt, not only its outcome."""

    communication = (
        r"(?:通知|通知书|提醒|消息|短信|邮件|答复|回复|批复|催告|催告函|函件)"
    )
    occurrence = (
        r"(?:没有|并未|未曾|从未|未|已|已经|曾|发出|发过|发送|送达|收到|"
        r"作出|出具|发布|提供|寄出|寄送|写明|载明|称)"
    )
    return bool(
        re.search(rf"{occurrence}.{{0,32}}{communication}", candidate_belief)
        or re.search(rf"{communication}.{{0,24}}{occurrence}", candidate_belief)
    )


def attributed_statement_subject_role(value: str) -> str | None:
    """Return the explicit speaker in a direct request/report of what someone said.

    This check is intentionally narrower than generic communication-content
    detection.  It activates only for attributed speech (for example, ``公司怎么
    说``), so a question about a message body without a named speaker is unaffected.
    """

    roles: dict[str, tuple[str, ...]] = {
        "company": ("用人单位", "贵公司", "公司", "单位", "雇主", "我司"),
        "bank": ("银行", "贷款人"),
        "platform": ("平台",),
        "authority": ("行政机关", "审批局", "住建局", "公安机关", "法院", "部门"),
        "counterparty": ("对方", "相对方"),
        "employee": ("员工", "劳动者"),
        "client": ("您", "你", "本人", "客户", "我方", "我"),
    }
    subject_to_role = {
        subject: role for role, subjects in roles.items() for subject in subjects
    }
    subject_pattern = "|".join(
        re.escape(item) for item in sorted(subject_to_role, key=len, reverse=True)
    )
    speech_pattern = (
        r"(?:声称|表示|主张|解释(?:称|说)?|答复称|回复称|承诺|"
        r"(?:说|称|表示|解释).{0,6}(?:为什么|为何|原因|理由)|"
        r"(?:怎么|如何)(?:说|表述|解释)|说法|表述|原话|"
        r"提出.{0,8}(?:理由|抗辩)|(?:拒绝|不同意).{0,8}(?:理由|为由)|"
        r"以.{0,20}为由.{0,8}(?:拒绝|不同意)|"
        r"(?:理由|抗辩).{0,6}(?:是什么|有哪些|包括))"
    )
    matches = list(
        re.finditer(
            rf"(?P<subject>{subject_pattern}).{{0,14}}{speech_pattern}",
            value,
        )
    )
    if not matches:
        return None
    return subject_to_role[matches[-1].group("subject")]


def identifies_communication_content(candidate_belief: str) -> bool:
    """Separate message substance from channel, delivery, timing, and salience."""

    speech_or_reason = bool(
        re.search(
            r"(?:称|表示|告知|写明|载明|提到|说明|答复称|回复称)"
            r".{1,48}(?:。|，|；|、|$)",
            candidate_belief,
        )
        or re.search(
            r"(?:公司|单位|雇主|银行|平台|机关|部门|对方|员工|申请人|"
            r"被申请人|原告|被告|他|她|其).{0,10}要求.{1,40}(?:。|，|；|、|$)",
            candidate_belief,
        )
        or re.search(r"(?:以|因为).{1,32}(?:为由|理由|拒绝|要求)", candidate_belief)
    )
    communication_with_proposition = bool(
        re.search(
            r"(?:通知|通知书|提醒|消息|短信|邮件|答复|回复|批复|催告|催告函|函件)"
            r".{0,24}(?:称|写明|载明|提到|说明|告知|要求|将于|应当|须|不得|理由为|内容为)",
            candidate_belief,
        )
    )
    return speech_or_reason or communication_with_proposition


PRESUPPOSED_OBJECT_PATTERNS: dict[str, tuple[str, ...]] = {
    "notice": ("通知", "通知书", "告知", "告知书", "催告", "催告函", "函件", "送达"),
    "agreement": ("协议", "合同", "约定", "承诺书"),
    "decision": ("决定", "决定书", "答复", "回复", "批复"),
    "record": ("记录", "报告", "证明", "文书", "材料"),
    "procedure": ("报案", "起诉", "仲裁", "复议", "听证", "申请", "申报"),
    "payment": ("付款", "支付", "汇款", "转账", "还款", "缴纳"),
    "signature": ("签字", "签名", "签署", "盖章"),
}

PRESUPPOSED_OBJECT_OCCURRENCE_VERBS: dict[str, tuple[str, ...]] = {
    "notice": ("发出", "发送", "收到", "送达", "作出", "出具", "发布", "寄送"),
    "agreement": ("签署", "签订", "订立", "达成", "形成"),
    "decision": ("作出", "收到", "出具", "发布"),
    "record": ("形成", "制作", "出具", "提供", "保存", "取得"),
    "procedure": ("提起", "提出", "进行", "办理", "启动"),
    "payment": ("作出", "进行", "完成"),
    "signature": ("进行", "完成"),
}


def presupposition_correction_match(question: str, candidate_belief: str) -> bool:
    """Recognize a direct negative correction to a question's false premise.

    A cooperative client asked for the content, reason, time, channel, or manner
    of an assumed notice/agreement/procedure must be allowed to answer that the
    assumed object never existed, was never sent/received, or never occurred.
    The match is deliberately closed-world: question and belief must share one
    audited object family, the question must request a positive attribute, and
    the belief must explicitly negate that same family in a local clause.
    """

    asks_assumed_attribute = bool(
        re.search(
            r"(?:具体)?(?:内容|理由|原因|依据|条款|时间|日期|方式|渠道|过程|经过|结果)"
            r"|(?:写了|写明|记载|提到|载明|如何|怎么|何时|什么时候|哪一天|通过什么)",
            question,
        )
    )
    if asks_assumed_attribute:
        for family, patterns in PRESUPPOSED_OBJECT_PATTERNS.items():
            shared = [item for item in patterns if item in question and item in candidate_belief]
            if not shared:
                continue
            object_pattern = "|".join(
                re.escape(item) for item in sorted(patterns, key=len, reverse=True)
            )
            occurrence_pattern = "|".join(
                re.escape(item)
                for item in PRESUPPOSED_OBJECT_OCCURRENCE_VERBS[family]
            )
            negative = r"(?:没有|并未|未曾|从未|不曾|尚未|未)"
            negative_patterns = (
                # A bare ``没有+对象词`` is not enough.  Several object labels
                # are also ordinary verbs: in ``没有告知慢性支气管炎``, ``告知``
                # means disclosure and does not deny that a ``健康告知书``
                # existed.  A deterministic correction must bind the negation to
                # an audited occurrence predicate (sent/received/signed/etc.) or
                # explicitly state that the object did not exist.
                rf"{negative}.{{0,12}}(?:{occurrence_pattern}).{{0,12}}(?:{object_pattern})",
                rf"(?:{object_pattern}).{{0,8}}(?:不存在|未发生|未发出|未收到|未签署|未签字)",
                rf"(?:{object_pattern}).{{0,8}}{negative}.{{0,6}}(?:{occurrence_pattern})",
            )
            if any(re.search(pattern, candidate_belief) for pattern in negative_patterns):
                return True
    action_terms = (
        "制止",
        "阻止",
        "整改",
        "补正",
        "退缴",
        "补偿",
        "赔偿",
        "归还",
        "返还",
        "提交",
        "付款",
        "支付",
    )
    shared_actions = [
        action for action in action_terms if action in question and action in candidate_belief
    ]
    asks_assumed_action_detail = bool(
        re.search(r"(?:哪些|什么|如何|怎么).{0,12}(?:措施|行动|处理|做法)", question)
        or re.search(
            r"(?:采取|实施|作出|进行).{0,8}(?:哪些|什么).{0,8}(?:措施|行动|处理)",
            question,
        )
        or re.search(
            r"(?:如何|怎么).{0,8}"
            r"(?:制止|阻止|整改|补正|退缴|补偿|赔偿|归还|返还|提交|付款|支付)",
            question,
        )
    )
    if shared_actions and asks_assumed_action_detail:
        negative = r"(?:没有|并未|未曾|从未|不曾|尚未|未|不加)"
        for action in shared_actions:
            if not re.search(rf"{negative}.{{0,6}}{re.escape(action)}", candidate_belief):
                continue
            requested_roles = observable_action_subject_roles(question)
            candidate_roles = observable_action_subject_roles(candidate_belief)
            if requested_roles and candidate_roles and requested_roles.isdisjoint(candidate_roles):
                continue
            return True
    return False


def relationship_context_roles(value: str) -> set[str]:
    """Extract explicit parties in living/care relations.

    The extractor is intentionally relation-local: it does not infer a client's
    family identity from the case and therefore cannot silently equate “我”
    with a named third party.  Ambiguous generic pronouns remain distinguishable
    but never by themselves justify a rejection.
    """

    role_values = {item: role for role, items in RELATION_ROLE_PATTERNS.items() for item in items}
    roles = "|".join(re.escape(item) for item in sorted(role_values, key=len, reverse=True))
    predicates = "|".join(
        re.escape(item) for item in sorted(RELATION_PREDICATES, key=len, reverse=True)
    )
    patterns = (
        rf"(?:与|跟|随|由)(?P<role>{roles})(?:共同|一起)?(?:{predicates})",
        rf"在(?P<role>{roles})(?:这里|那里|处|家中|家里)(?:{predicates})?",
        rf"(?P<role>{roles})(?:负责|实际|直接|主要)?(?:{predicates})",
    )
    found: set[str] = set()
    for pattern in patterns:
        for match in re.finditer(pattern, value):
            found.add(role_values[match.group("role")])
    return found


def relationship_context_compatible(question: str, candidate_belief: str) -> bool | None:
    """Compare explicit parties for the same living/care relation."""

    requested = relationship_context_roles(question)
    present = relationship_context_roles(candidate_belief)
    if not requested or not present:
        return None
    if requested & present:
        return True
    if "generic_counterparty" in requested or "generic_counterparty" in present:
        return None
    return False


def transition_stages(value: str) -> dict[str, set[str]]:
    """Extract before/during/after markers tied to explicit transitions."""

    suffixes = {
        "之前": "before",
        "以前": "before",
        "前": "before",
        "之后": "after",
        "以后": "after",
        "后": "after",
        "期间": "during",
        "时": "during",
    }
    result: dict[str, set[str]] = {}
    for anchor, values in TRANSITION_ANCHOR_PATTERNS.items():
        stages: set[str] = set()
        for item in sorted(values, key=len, reverse=True):
            for suffix, stage in suffixes.items():
                if re.search(rf"{re.escape(item)}(?:完成|发生|生效)?{suffix}", value):
                    stages.add(stage)
        if stages:
            result[anchor] = stages
    return result


def transition_stage_compatible(question: str, candidate_belief: str) -> bool | None:
    """Reject facts tied to the opposite side of the same transition."""

    arrangement = (
        r"(?:约定|协议|合同|条款|抚养权|抚养关系|抚养安排|照料安排|"
        r"登记|责任安排|付款安排)"
    )
    modification = r"(?:变更|修改|调整|重新协商|重新约定|改为|改由|后续协商)"
    formation = r"(?:离婚时|签订时|签署时|订立时|登记时|最初|起初|原先|原始|当初)"
    requests_modification = bool(
        re.search(rf"{arrangement}.{{0,18}}{modification}", question)
        or re.search(rf"{modification}.{{0,18}}{arrangement}", question)
    )
    candidate_states_only_formation = bool(
        (
            re.search(rf"{formation}.{{0,24}}{arrangement}", candidate_belief)
            or re.search(rf"{arrangement}.{{0,24}}{formation}", candidate_belief)
        )
        and not re.search(modification, candidate_belief)
    )
    if requests_modification and candidate_states_only_formation:
        return False

    requested = transition_stages(question)
    present = transition_stages(candidate_belief)
    compared = False
    for anchor in requested.keys() & present.keys():
        compared = True
        if requested[anchor] & present[anchor]:
            continue
        if {"before", "after"} == requested[anchor] | present[anchor]:
            return False
        # A during-stage fact does not necessarily exclude an adjacent stage;
        # keep the semantic model authoritative in that ambiguous situation.
        compared = False
    return True if compared else None


def event_attribute_compatible(question: str, candidate_belief: str) -> bool | None:
    """Reject a candidate about a different real-world event.

    This is a conservative veto layered on top of the semantic model.  It never
    approves a fact: ``None`` means the generic semantic relevance check remains
    authoritative.  A veto is emitted when the question and candidate both name
    event concepts but their sets are disjoint.  A composite question may still
    be answered by a fact covering one of its requested events.  This prevents a
    date for marriage/registration from being accepted as a purchase or payment
    fact merely because both texts contain chronology.
    """

    # Refusing an offered renewal is an explicit negative answer to whether the
    # new employment contract was signed.  Treat that narrow entailment as the
    # same event before the generic concept veto compares ``signing`` with
    # ``contract_renewal``.  A renewal notice alone is deliberately insufficient.
    if renewal_signature_answer_matches(question, candidate_belief):
        return True

    requested = event_concepts(question)
    if not requested:
        return None
    present = event_concepts(candidate_belief)
    if not present:
        return None
    if requested & present:
        return True
    # Purchase and its funding/payment are two views of the same transaction.
    # Treating their concept names as mutually exclusive vetoed correct semantic
    # matches such as “你是否对房屋出资” -> “房屋由他婚前购买，我没有参与取得
    # 产权”.  This only removes a deterministic veto; the frozen semantic verifier
    # must still affirm that the candidate answers the requested attribute.
    related_event_families = ({"purchase", "payment"},)
    return any(requested & family and present & family for family in related_event_families)


def renewal_signature_answer_matches(question: str, candidate_belief: str) -> bool:
    """Match an explicit refusal of renewal to a renewal-signature question."""

    asks_new_employment_signature = bool(
        re.search(
            r"(?:签署|签订|订立).{0,12}(?:新(?:的)?|续签|续订|续约)"
            r".{0,8}(?:书面)?劳动合同",
            question,
        )
        or re.search(
            r"(?:新(?:的)?|续签|续订|续约).{0,8}(?:书面)?劳动合同"
            r".{0,12}(?:签署|签订|订立)",
            question,
        )
    )
    explicitly_refuses_renewal = bool(
        re.search(r"(?:拒绝|不同意|未同意).{0,10}(?:续签|续订|续约)", candidate_belief)
        or re.search(r"(?:续签|续订|续约).{0,14}(?:拒绝|不同意|未同意)", candidate_belief)
    )
    return asks_new_employment_signature and explicitly_refuses_renewal


def event_concepts(value: str) -> set[str]:
    """Return conservative real-world event concepts explicitly named in text."""

    return {
        concept
        for concept, patterns in EVENT_CONCEPT_PATTERNS.items()
        if any(pattern in value for pattern in patterns)
    }


def localized(value: object, language: str = "zh") -> str:
    if isinstance(value, dict):
        return str(value.get(language) or value.get("zh") or value.get("en") or "")
    return str(value or "")


def opening_fact_candidates(opening: str) -> list[dict[str, str]]:
    """Expose already-public opening claims as grounded client answer candidates."""

    claims = [
        item.strip(" ，,。；;！？!?\t")
        for item in re.split(r"[。；;！？!?\n]+", opening.strip())
        if len(item.strip(" ，,。；;！？!?\t")) >= 4
    ]
    return [
        {"fact_id": f"O{index}", "client_belief": claim, "source": "opening"}
        for index, claim in enumerate(claims, start=1)
    ]


def hidden_fact_adds_information(opening: str, belief: str) -> bool | None:
    """Deterministically reject a hidden belief already fully stated in the opening.

    ``None`` leaves partial/semantic overlap to the frozen relevance verifier.  A
    longer belief may add a material attribute and therefore must not be rejected
    merely because the opening is a substring of it.
    """

    def normalize(value: str) -> str:
        return re.sub(r"[，。；：、！？,.;:!?\s‘’“”\"']", "", value)

    normalized_opening = normalize(opening)
    normalized_belief = normalize(belief)
    if len(normalized_belief) >= 4 and normalized_belief in normalized_opening:
        return False
    return None


def hidden_fact_adds_question_information(
    question: str, opening: str, belief: str
) -> bool | None:
    """Reject a hidden belief that only repeats the opening's requested attribute."""

    lexical_increment = hidden_fact_adds_information(opening, belief)
    if lexical_increment is False:
        return False
    asks_current_caregiver = bool(
        re.search(
            r"(?:目前|现在|当前|现阶段).{0,12}(?:由谁|谁|跟谁|与谁)"
            r".{0,10}(?:生活|居住|照料|照顾|抚养|看护)",
            question,
        )
        or re.search(r"(?:由谁|谁).{0,10}(?:实际)?(?:照料|照顾|抚养|看护)", question)
        or re.search(r"(?:跟谁|与谁).{0,10}(?:生活|居住)", question)
    )
    if asks_current_caregiver:
        role_values = {
            item: role
            for role, items in RELATION_ROLE_PATTERNS.items()
            for item in items
        }
        role_pattern = "|".join(
            re.escape(item) for item in sorted(role_values, key=len, reverse=True)
        )
        current_opening_roles: set[str] = set()
        for match in re.finditer(
            rf"(?:目前|现在|当前|现阶段).{{0,12}}(?P<role>{role_pattern})"
            rf".{{0,8}}(?:生活|居住|照料|照顾|抚养|看护)",
            opening,
        ):
            current_opening_roles.add(role_values[match.group("role")])
        belief_roles = relationship_context_roles(belief)
        if current_opening_roles & belief_roles:
            return False
    return None


@dataclass
class ClientSimulator:
    case_view: dict
    persona: dict
    model: ChatClient
    prompt_template: str
    relevance_prompt: str
    generation: GenerationConfig
    max_selection_attempts: int
    relevance_model: ChatClient | None = None
    relevance_generation: GenerationConfig | None = None
    disclosure_prompt: str = DEFAULT_DISCLOSURE_PROMPT
    recall_max_tokens: int = 768
    recall_disable_thinking: bool = False
    retry_empty_selection: bool = False
    history: list[tuple[str, str]] = field(default_factory=list)
    disclosed_fact_ids: set[str] = field(default_factory=set, init=False)
    last_selection_attempts: list[str] = field(default_factory=list, init=False)
    last_opening_selection_attempts: list[str] = field(default_factory=list, init=False)
    last_relevance_attempts: list[dict[str, object]] = field(default_factory=list, init=False)
    last_disclosure_attempts: list[str] = field(default_factory=list, init=False)
    last_relevance_passed: bool | None = field(default=None, init=False)
    # ``matched`` is internal audit state: it may include a fact that the client
    # elected not to disclose.  ``selected`` remains disclosure provenance and is
    # therefore empty on a withheld turn.
    last_matched_fact_ids: list[str] = field(default_factory=list, init=False)
    last_selected_fact_ids: list[str] = field(default_factory=list, init=False)
    last_opening_reference_ids: list[str] = field(default_factory=list, init=False)
    last_disclosure_decision: DisclosureDecision | None = field(default=None, init=False)
    last_response_kind: ClientResponseKind | None = field(default=None, init=False)
    last_safe_fallback: bool = field(default=False, init=False)

    @classmethod
    def from_template_file(
        cls,
        case_view: dict,
        persona: dict,
        model: ChatClient,
        template_path: Path,
        generation: GenerationConfig,
        max_selection_attempts: int,
        relevance_template_path: Path | None = None,
        disclosure_template_path: Path | None = None,
        relevance_model: ChatClient | None = None,
        relevance_generation: GenerationConfig | None = None,
        recall_max_tokens: int = 768,
        recall_disable_thinking: bool = False,
        retry_empty_selection: bool = False,
    ) -> ClientSimulator:
        if max_selection_attempts < 1:
            raise ValueError("client max_selection_attempts must be positive")
        if recall_max_tokens < generation.max_tokens:
            raise ValueError("client recall_max_tokens must cover the primary output budget")
        return cls(
            case_view=case_view,
            persona=persona,
            model=model,
            prompt_template=template_path.read_text(encoding="utf-8").strip(),
            relevance_prompt=(
                relevance_template_path.read_text(encoding="utf-8").strip()
                if relevance_template_path is not None
                else DEFAULT_RELEVANCE_PROMPT
            ),
            disclosure_prompt=(
                disclosure_template_path.read_text(encoding="utf-8").strip()
                if disclosure_template_path is not None
                else DEFAULT_DISCLOSURE_PROMPT
            ),
            generation=generation,
            max_selection_attempts=max_selection_attempts,
            relevance_model=relevance_model,
            relevance_generation=relevance_generation,
            recall_max_tokens=recall_max_tokens,
            recall_disable_thinking=recall_disable_thinking,
            retry_empty_selection=retry_empty_selection,
        )

    def _messages(self, lawyer_question: str) -> list[dict[str, str]]:
        return self._messages_for_facts(lawyer_question, self._selectable_facts())

    def _messages_for_facts(
        self, lawyer_question: str, facts: list[dict[str, object]]
    ) -> list[dict[str, str]]:
        facts_block = "\n".join(f"- {fact['fact_id']}: {fact['client_belief']}" for fact in facts)
        valid_ids = {str(fact["fact_id"]) for fact in facts}
        disclosed = self.disclosed_fact_ids & valid_ids
        template = self.prompt_template.replace(
            "{disclosed_fact_ids}",
            "、".join(sorted(disclosed)) or "无",
        )
        system = template.format(
            persona_id=str(self.persona.get("persona_id") or ""),
            persona_who=localized(self.persona.get("who")),
            persona_voice=localized(self.persona.get("voice")),
            facts_block=facts_block,
        )
        messages = [{"role": "system", "content": system}]
        for previous_question, previous_answer in self.history:
            messages.append({"role": "user", "content": previous_question})
            messages.append({"role": "assistant", "content": previous_answer})
        # Earlier client answers are deliberately retained so that the selector can
        # resolve ordinary references in the lawyer's next question.  Those answers
        # are natural-language assistant messages, however, and a small local model
        # can start role-playing the client instead of obeying the selector JSON
        # contract.  Restate the machine task in the final (highest-recency) user
        # message for every phase; this changes no candidate fact or disclosure
        # policy, it only keeps the transport contract explicit after dialogue
        # history has been appended.
        messages.append(
            {
                "role": "user",
                "content": (
                    f"律师本轮问题：{lawyer_question}\n"
                    "你现在只执行候选事实编号选择；不直接回答律师，也不扮演客户。"
                    '只输出 {"fact_ids":["当前块中的一个编号"],'
                    '"disclosure":"disclose"}；disclosure只是兼容占位符，固定写disclose。'
                    '没有直接答案时只输出 '
                    '{"fact_ids":[],"disclosure":"disclose"}。'
                ),
            }
        )
        return messages

    def _disclosure_messages(
        self,
        lawyer_question: str,
        matched_belief: str,
    ) -> list[dict[str, str]]:
        system = self.disclosure_prompt.format(
            persona_id=str(self.persona.get("persona_id") or ""),
            persona_who=localized(self.persona.get("who")),
            persona_voice=localized(self.persona.get("voice")),
            matched_belief=matched_belief,
        )
        messages = [{"role": "system", "content": system}]
        for previous_question, previous_answer in self.history:
            messages.append({"role": "user", "content": previous_question})
            messages.append({"role": "assistant", "content": previous_answer})
        messages.append(
            {
                "role": "user",
                "content": (
                    f"律师本轮问题：{lawyer_question}\n"
                    "只判断当前人格现在是否披露已确认匹配的事实；不重新选择事实，"
                    '只输出 {"disclosure":"disclose"} 或 '
                    '{"disclosure":"withhold"}。'
                ),
            }
        )
        return messages

    def _selectable_facts(self) -> list[dict[str, object]]:
        return list(self.case_view.get("facts", []))

    def respond(
        self,
        lawyer_question: str,
        seed: int,
    ) -> tuple[ChatResponse, str]:
        """Return a grounded client response to one natural lawyer question.

        The client's observable input is the question the lawyer actually asked.
        Internal target labels and expected-information fields are planning aids;
        substituting either for the rendered question would hide malformed or
        semantically drifting lawyer behavior from the environment and evaluation.
        """

        matching_question = lawyer_question.strip()
        opening_facts: list[dict[str, object]] = list(
            opening_fact_candidates(str(self.case_view.get("opening") or ""))
        )
        hidden_facts: list[dict[str, object]] = list(self.case_view.get("facts", []))
        facts = [*opening_facts, *hidden_facts]
        attempts: list[ChatResponse] = []
        hidden_attempts: list[ChatResponse] = []
        opening_attempts: list[ChatResponse] = []
        relevance_responses: list[ChatResponse] = []
        relevance_records: list[dict[str, object]] = []
        relevance_request_hashes: list[str] = []
        selection_request_hashes: list[str] = []
        disclosure_responses: list[ChatResponse] = []
        disclosure_request_hashes: list[str] = []
        selected_fact_ids: list[str] | None = None
        selected_source: Literal["new_hidden", "repeated_hidden", "opening"] | None = None
        selected_disclosure: DisclosureDecision = "disclose"
        selection_contract_failed = False

        def verify_candidate(
            *,
            selected_id: str,
            selected_belief: str,
            phase_name: Literal["new_hidden", "repeated_hidden", "opening"],
            relevance_seed: int,
            verification_trigger: Literal[
                "selector_candidate",
                "exhaustive_after_empty_cooperative_selection",
                "exhaustive_after_empty_repeated_selection",
            ],
        ) -> tuple[bool, bool | None, bool | None, list[str]]:
            structured_relevance = (
                self.relevance_generation is not None
                and self.relevance_generation.response_schema is not None
            )
            relevance_output_instruction = (
                "按系统给定的命题对齐 JSON schema 输出；不得省略字段。"
                if structured_relevance
                else (
                    '只输出 {"answers_question":true} 或 '
                    '{"answers_question":false}。'
                )
            )
            relevance_messages = [
                {"role": "system", "content": self.relevance_prompt},
                {
                    "role": "user",
                    "content": (
                        f"律师问题：{matching_question}\n"
                        f"公开开场：{self.case_view.get('opening') or '无'}\n"
                        "候选来源："
                        f"{'隐藏事实' if phase_name != 'opening' else '公开开场'}\n"
                        f"候选客户事实：{selected_belief}\n"
                        f"{relevance_output_instruction}"
                    ),
                },
            ]
            relevance_model = self.relevance_model or self.model
            relevance_generation = self.relevance_generation or GenerationConfig(
                temperature=0.0,
                top_p=1.0,
                max_tokens=32,
                seed=relevance_seed,
                disable_thinking=self.generation.disable_thinking,
            )
            structured_contract_required = (
                relevance_generation.response_schema is not None
            )

            def run_relevance_attempt(
                generation: GenerationConfig,
            ) -> tuple[ChatResponse, dict[str, object] | None, bool | None]:
                response = relevance_model.generate(relevance_messages, generation)
                relevance_responses.append(response)
                relevance_request_hashes.append(canonical_json_sha256(relevance_messages))
                return (
                    response,
                    parse_relevance_analysis(response.content),
                    parse_relevance_check(response.content),
                )

            primary_generation = replace(relevance_generation, seed=relevance_seed)
            relevance, relevance_analysis, relevance_value = run_relevance_attempt(
                primary_generation
            )
            relevance_attempt_values = [
                (relevance, relevance_analysis, relevance_value)
            ]
            # Qwen's bounded thinking is needed for difficult proposition alignment,
            # but a length-truncated thought without the required JSON is a protocol
            # failure, not a semantic rejection. Repair only that malformed result
            # once with the identical prompt/schema and direct structured decoding.
            # A valid primary answer is never second-guessed, and a malformed repair
            # remains a hard failure rather than being accepted through a fallback.
            if structured_contract_required and relevance_analysis is None:
                repair_generation = replace(
                    primary_generation,
                    disable_thinking=True,
                )
                relevance, relevance_analysis, relevance_value = run_relevance_attempt(
                    repair_generation
                )
                relevance_attempt_values.append(
                    (relevance, relevance_analysis, relevance_value)
                )
            proposition_alignment_passed = structured_proposition_alignment_passed(
                relevance_analysis
            )
            deterministic_compatibility, deterministic_violations = (
                deterministic_relevance_compatibility(matching_question, selected_belief)
            )
            deterministic_incremental = (
                hidden_fact_adds_question_information(
                    matching_question,
                    str(self.case_view.get("opening") or ""),
                    selected_belief,
                )
                if phase_name != "opening"
                else None
            )
            deterministic_violations = list(deterministic_violations)
            deterministic_presupposition_correction = (
                phase_name != "opening"
                and presupposition_correction_match(matching_question, selected_belief)
            )
            deterministic_direct_answer = direct_answer_attribute_explicit_match(
                matching_question, selected_belief
            )
            accepted = (
                (
                    relevance_value is True
                    or deterministic_presupposition_correction
                    or deterministic_direct_answer
                )
                and (
                    not structured_contract_required
                    or proposition_alignment_passed
                    or deterministic_presupposition_correction
                    or deterministic_direct_answer
                )
                and deterministic_compatibility is not False
                and deterministic_incremental is not False
                and not deterministic_violations
            )
            for (
                attempt_response,
                attempt_analysis,
                attempt_value,
            ) in relevance_attempt_values:
                relevance_records.append(
                    {
                        "raw_output": attempt_response.content,
                        "verifier_model_id": relevance_model.model,
                        "selected_fact_id": selected_id,
                        "verification_trigger": verification_trigger,
                        "parse_valid": attempt_value is not None,
                        "answers_question": attempt_value,
                        "question_actor": (
                            attempt_analysis.get("question_actor")
                            if attempt_analysis is not None
                            else None
                        ),
                        "question_predicate": (
                            attempt_analysis.get("question_predicate")
                            if attempt_analysis is not None
                            else None
                        ),
                        "question_attribute": (
                            attempt_analysis.get("question_attribute")
                            if attempt_analysis is not None
                            else None
                        ),
                        "candidate_actor": (
                            attempt_analysis.get("candidate_actor")
                            if attempt_analysis is not None
                            else None
                        ),
                        "candidate_predicate": (
                            attempt_analysis.get("candidate_predicate")
                            if attempt_analysis is not None
                            else None
                        ),
                        "candidate_attribute": (
                            attempt_analysis.get("candidate_attribute")
                            if attempt_analysis is not None
                            else None
                        ),
                        "candidate_assertion_source": (
                            attempt_analysis.get("candidate_assertion_source")
                            if attempt_analysis is not None
                            else None
                        ),
                        "same_actor": (
                            attempt_analysis.get("same_actor")
                            if attempt_analysis is not None
                            else None
                        ),
                        "same_predicate": (
                            attempt_analysis.get("same_predicate")
                            if attempt_analysis is not None
                            else None
                        ),
                        "same_attribute": (
                            attempt_analysis.get("same_attribute")
                            if attempt_analysis is not None
                            else None
                        ),
                        "proposition_alignment_passed": (
                            structured_proposition_alignment_passed(attempt_analysis)
                        ),
                        "deterministic_compatible": deterministic_compatibility,
                        "deterministic_presupposition_correction": (
                            deterministic_presupposition_correction
                        ),
                        "deterministic_direct_answer": deterministic_direct_answer,
                        "deterministic_incremental_over_opening": deterministic_incremental,
                        "deterministic_compatibility_violations": deterministic_violations,
                    }
                )
            rejection_reasons = list(deterministic_violations)
            if deterministic_incremental is False:
                rejection_reasons.append("fully_disclosed_in_public_opening")
            if (
                relevance_value is False
                and not deterministic_presupposition_correction
                and not deterministic_direct_answer
            ):
                rejection_reasons.append("semantic_not_direct_answer")
            elif relevance_value is None:
                rejection_reasons.append("invalid_relevance_output")
            elif structured_contract_required and not proposition_alignment_passed:
                rejection_reasons.append("proposition_alignment_not_established")
            return (
                accepted,
                relevance_value,
                deterministic_compatibility,
                rejection_reasons,
            )

        undisclosed_hidden = [
            fact
            for fact in hidden_facts
            if str(fact.get("fact_id") or "") not in self.disclosed_fact_ids
        ]
        disclosed_hidden = [
            fact
            for fact in hidden_facts
            if str(fact.get("fact_id") or "") in self.disclosed_fact_ids
        ]
        # New hidden client beliefs are the only information-bearing answers. Public
        # opening claims and previously disclosed beliefs are considered only after
        # the new-belief set is exhausted, so they classify repetition without
        # starving a directly responsive hidden fact.
        phases = [
            ("new_hidden", undisclosed_hidden, self.max_selection_attempts),
            ("repeated_hidden", disclosed_hidden, self.max_selection_attempts),
            # Opening classification is provenance-bearing too: treating a repeated
            # public fact as unavailable changes the target state, while accepting a
            # malformed response would hide a protocol failure.  Give it the same
            # bounded format-repair budget as the hidden phases rather than failing
            # after one model lapse.  Exhausting the budget remains a hard fallback.
            ("opening", opening_facts, self.max_selection_attempts),
        ]
        for phase_index, (phase_name, phase_facts, invalid_attempt_limit) in enumerate(phases):
            if not phase_facts:
                continue
            remaining_phase_facts = list(phase_facts)
            phase_selection: list[str] | None = None
            invalid_selection_attempts = 0
            invalid_relevance_attempts_by_fact: dict[str, int] = {}
            empty_selection_retries = 0
            attempt_index = 0
            rejected_guidance = ""
            while remaining_phase_facts:
                selection_messages = self._messages_for_facts(
                    matching_question, remaining_phase_facts
                )
                if rejected_guidance:
                    selection_messages[-1]["content"] = (
                        selection_messages[-1]["content"]
                        + "\n"
                        + rejected_guidance
                        + "请只在当前剩余编号中重新逐字比对；若没有事实直接回答，"
                        '返回 {"fact_ids":[],"disclosure":"disclose"}。'
                    )
                valid_fact_ids = [
                    str(fact["fact_id"]) for fact in remaining_phase_facts
                ]
                rejected_fact_id: str | None = None
                relevance_retry_pending = False
                rejection_reasons: list[str] = []
                selection_request_hashes.append(canonical_json_sha256(selection_messages))
                # Candidate selection is deliberately the high-recall stage of a
                # two-stage router.  A separately recorded proposition verifier and
                # deterministic compatibility checks remain the precision gate for
                # the single selected fact.  Repeating a schema-valid empty answer
                # with longer hidden reasoning doubled the dominant no-match path
                # without recovering the real-world semantic misses that motivated
                # the retry, so only malformed transport receives a bounded repair.
                recall_pass = self.retry_empty_selection and empty_selection_retries > 0
                strict_format_repair = invalid_selection_attempts > 0
                candidate = self.model.generate(
                    selection_messages,
                    GenerationConfig(
                        temperature=self.generation.temperature,
                        top_p=self.generation.top_p,
                        max_tokens=(
                            self.generation.max_tokens
                            if strict_format_repair
                            else self.recall_max_tokens
                            if recall_pass
                            else self.generation.max_tokens
                        ),
                        seed=seed + phase_index * 100 + attempt_index,
                        disable_thinking=(
                            True
                            if strict_format_repair
                            else self.recall_disable_thinking
                            if recall_pass
                            else True
                        ),
                        response_schema=client_fact_selection_schema(valid_fact_ids),
                        response_schema_name="legal_skill_guard_client_fact_selection_v3",
                    ),
                )
                attempts.append(candidate)
                if phase_name == "opening":
                    opening_attempts.append(candidate)
                else:
                    hidden_attempts.append(candidate)
                selection_decision = parse_fact_selection_decision(
                    candidate.content, valid_fact_ids
                )
                phase_selection = (
                    selection_decision.fact_ids if selection_decision is not None else None
                )
                phase_disclosure: DisclosureDecision = (
                    selection_decision.disclosure
                    if selection_decision is not None
                    else "disclose"
                )
                attempt_index += 1
                if phase_selection == []:
                    if (
                        self.retry_empty_selection
                        and phase_name == "new_hidden"
                        and empty_selection_retries < 1
                    ):
                        empty_selection_retries += 1
                        rejected_guidance = ""
                        phase_selection = None
                        continue
                    # A schema-valid empty selection is a joint comparison against
                    # the complete finite candidate set.  Do not subsequently test every
                    # candidate with separate yes/no calls: even a small per-call
                    # false-positive rate compounds across the set and can turn a
                    # merely related fact into a fabricated answer.  This rule is
                    # persona-independent and applies equally to undisclosed,
                    # repeated, and opening facts.
                    deterministic_corrections: list[
                        tuple[str, bool | None, list[str], bool | None, bool]
                    ] = []
                    for fact in remaining_phase_facts:
                        fact_id = str(fact["fact_id"])
                        belief = str(fact["client_belief"])
                        is_presupposition_correction = presupposition_correction_match(
                            matching_question, belief
                        )
                        is_explicit_direct_answer = direct_answer_attribute_explicit_match(
                            matching_question, belief
                        )
                        if not (
                            is_presupposition_correction or is_explicit_direct_answer
                        ):
                            continue
                        compatibility, violations = deterministic_relevance_compatibility(
                            matching_question, belief
                        )
                        incremental = (
                            hidden_fact_adds_question_information(
                                matching_question,
                                str(self.case_view.get("opening") or ""),
                                belief,
                            )
                            if phase_name != "opening"
                            else None
                        )
                        if compatibility is False or violations or incremental is False:
                            continue
                        deterministic_corrections.append(
                            (
                                fact_id,
                                compatibility,
                                list(violations),
                                incremental,
                                is_presupposition_correction,
                            )
                        )
                    # A unique deterministic match is an audited direct answer, not
                    # a semantic rescue.  Multiple presupposition corrections remain
                    # ambiguous because they may negate different assumed events.
                    # Multiple *positive direct-answer* matches are different: every
                    # item has independently passed the same closed attribute,
                    # compatibility and opening-increment checks, so returning one
                    # stable fact is safer than falsely claiming that the client has
                    # no answer.  The fact-id tie break controls response order only;
                    # it does not turn a non-answer into an eligible candidate.
                    recoverable_corrections = sorted(
                        deterministic_corrections,
                        key=lambda item: item[0],
                    )
                    if len(recoverable_corrections) == 1 or (
                        recoverable_corrections
                        and not any(item[4] for item in recoverable_corrections)
                    ):
                        (
                            correction_id,
                            compatibility,
                            violations,
                            incremental,
                            is_presupposition_correction,
                        ) = recoverable_corrections[0]
                        phase_selection = [correction_id]
                        selected_fact_ids = phase_selection
                        selected_source = phase_name
                        # This compatibility branch exists only for an old-format
                        # selector that incorrectly returned an empty match.  It has
                        # no disclosure field, so the documented legacy default is
                        # ``disclose``.  Current structured generations cannot encode
                        # withholding as an empty list.
                        selected_disclosure = "disclose"
                        relevance_records.append(
                            {
                                "raw_output": "",
                                "verifier_model_id": "deterministic_python",
                                "selected_fact_id": correction_id,
                                "verification_trigger": (
                                    "deterministic_presupposition_recovery_after_empty"
                                    if is_presupposition_correction
                                    else "deterministic_direct_answer_recovery_after_empty"
                                ),
                                "parse_valid": True,
                                "answers_question": (
                                    None if is_presupposition_correction else True
                                ),
                                "deterministic_compatible": compatibility,
                                "deterministic_presupposition_correction": (
                                    is_presupposition_correction
                                ),
                                "deterministic_incremental_over_opening": incremental,
                                "deterministic_compatibility_violations": violations,
                            }
                        )
                    break
                if phase_selection is None:
                    invalid_selection_attempts += 1
                    if invalid_selection_attempts >= invalid_attempt_limit:
                        selection_contract_failed = True
                        break
                    rejected_guidance = "上一选择格式错误。"
                    continue
                if phase_selection:
                    selected_id = phase_selection[0]
                    selected_belief = str(
                        next(
                            fact["client_belief"]
                            for fact in remaining_phase_facts
                            if str(fact["fact_id"]) == selected_id
                        )
                    )
                    (
                        accepted,
                        relevance_value,
                        deterministic_compatibility,
                        rejection_reasons,
                    ) = verify_candidate(
                        selected_id=selected_id,
                        selected_belief=selected_belief,
                        phase_name=phase_name,
                        relevance_seed=seed + 1000 + phase_index * 100 + attempt_index,
                        verification_trigger="selector_candidate",
                    )
                    if accepted:
                        selected_fact_ids = phase_selection
                        selected_source = phase_name
                        # A public opening or an already disclosed belief cannot
                        # meaningfully be withheld.  The distinction applies only to
                        # the first release of a hidden client belief.
                        selected_disclosure = (
                            phase_disclosure if phase_name == "new_hidden" else "disclose"
                        )
                        break
                    if relevance_value is None and deterministic_compatibility is not False:
                        relevance_retry_pending = True
                        invalid_relevance_attempts_by_fact[selected_id] = (
                            invalid_relevance_attempts_by_fact.get(selected_id, 0) + 1
                        )
                        if (
                            invalid_relevance_attempts_by_fact[selected_id]
                            >= invalid_attempt_limit
                        ):
                            selection_contract_failed = True
                            break
                    else:
                        # A valid semantic rejection or deterministic veto is evidence
                        # that this exact candidate cannot answer the question. Remove
                        # it from the finite set so the selector cannot cycle through
                        # already rejected beliefs and so candidate exhaustion has a
                        # precise non-fallback meaning.
                        rejected_fact_id = selected_id
                        remaining_phase_facts = [
                            fact
                            for fact in remaining_phase_facts
                            if str(fact["fact_id"]) != selected_id
                        ]
                    phase_selection = None
                # Do not echo an excluded identifier into the next model input. A
                # small selector can copy that identifier even though it is no
                # longer in the facts block, turning a valid semantic rejection
                # into an artificial parse failure. The audit record above keeps
                # the exact identifier and reasons; the selector only needs the
                # finite, current candidate set.
                rejected_guidance = (
                    "上一候选已被复核排除。"
                    if rejected_fact_id
                    else "上一相关性复核输出无效，候选集合未改变。"
                    if relevance_retry_pending
                    else "上一选择格式错误。"
                )
            if not remaining_phase_facts and selected_fact_ids is None:
                phase_selection = []
            if selected_fact_ids:
                break
            if selection_contract_failed:
                break

        if selected_fact_ids and selected_source == "new_hidden":
            persona_id = str(self.persona.get("persona_id") or "")
            # Cooperative personas have no withholding state in their frozen
            # definition.  Resistant personas receive one separate, focused model
            # decision so semantic matching cannot be distorted to express reluctance.
            if persona_id in {"P_WD", "P_WS"}:
                selected_disclosure = "disclose"
            else:
                selected_belief = str(
                    next(
                        fact["client_belief"]
                        for fact in hidden_facts
                        if str(fact["fact_id"]) == selected_fact_ids[0]
                    )
                )
                disclosure_messages = self._disclosure_messages(
                    lawyer_question,
                    selected_belief,
                )
                disclosure_request_hashes.append(
                    canonical_json_sha256(disclosure_messages)
                )
                disclosure_response = self.model.generate(
                    disclosure_messages,
                    GenerationConfig(
                        temperature=0.0,
                        top_p=1.0,
                        max_tokens=(
                            self.recall_max_tokens if persona_id == "P_CS" else 32
                        ),
                        seed=seed + 5000,
                        disable_thinking=(
                            self.recall_disable_thinking
                            if persona_id == "P_CS"
                            else True
                        ),
                        response_schema=CLIENT_DISCLOSURE_DECISION_SCHEMA,
                        response_schema_name="legal_skill_guard_client_disclosure_v1",
                    ),
                )
                disclosure_responses.append(disclosure_response)
                focused_disclosure = parse_disclosure_decision(
                    disclosure_response.content
                )
                if focused_disclosure is None and persona_id == "P_CS":
                    # P_CS receives bounded reasoning because its withholding rule
                    # has the only non-trivial sensitivity boundary. On an occasional
                    # length-truncated rationale, retry the identical decision with
                    # thinking disabled and the same strict schema. This is a
                    # transport repair by the same frozen model, not a default
                    # disclosure decision: failure of the second response still
                    # fails closed and remains a contract_fallback.
                    disclosure_repair_messages = [
                        *disclosure_messages,
                        {
                            "role": "user",
                            "content": (
                                "上一输出未形成可解析决定。不要继续解释；仅按同一人格"
                                '规则输出 {"disclosure":"disclose"} 或 '
                                '{"disclosure":"withhold"}。'
                            ),
                        },
                    ]
                    disclosure_request_hashes.append(
                        canonical_json_sha256(disclosure_repair_messages)
                    )
                    disclosure_response = self.model.generate(
                        disclosure_repair_messages,
                        GenerationConfig(
                            temperature=0.0,
                            top_p=1.0,
                            max_tokens=32,
                            seed=seed + 5001,
                            disable_thinking=True,
                            response_schema=CLIENT_DISCLOSURE_DECISION_SCHEMA,
                            response_schema_name=(
                                "legal_skill_guard_client_disclosure_v1"
                            ),
                        ),
                    )
                    disclosure_responses.append(disclosure_response)
                    focused_disclosure = parse_disclosure_decision(
                        disclosure_response.content
                    )
                if focused_disclosure is None:
                    selection_contract_failed = True
                    selected_fact_ids = None
                    selected_source = None
                else:
                    selected_disclosure = focused_disclosure

        self.last_opening_selection_attempts = [item.content for item in opening_attempts]
        self.last_selection_attempts = [item.content for item in hidden_attempts]
        self.last_relevance_attempts = relevance_records
        self.last_disclosure_attempts = [item.content for item in disclosure_responses]
        self.last_safe_fallback = selected_fact_ids is None and selection_contract_failed
        selected_fact_ids = selected_fact_ids or []
        self.last_matched_fact_ids = list(selected_fact_ids)
        self.last_disclosure_decision = (
            selected_disclosure if selected_fact_ids else None
        )
        self.last_relevance_passed = (
            True
            if selected_fact_ids
            else (False if self.last_safe_fallback else None)
        )
        self.last_selected_fact_ids = (
            list(selected_fact_ids)
            if selected_source in {"new_hidden", "repeated_hidden"}
            and selected_disclosure == "disclose"
            else []
        )
        self.last_opening_reference_ids = (
            list(selected_fact_ids)
            if selected_source == "opening" and selected_disclosure == "disclose"
            else []
        )
        facts_by_id = {str(fact["fact_id"]): fact for fact in facts}
        if self.last_safe_fallback:
            self.last_response_kind = "contract_fallback"
            content = unavailable_fact_response(str(self.persona.get("persona_id") or ""))
        elif selected_source == "new_hidden" and selected_disclosure == "withhold":
            self.last_response_kind = "withheld"
            content = withheld_fact_response(str(self.persona.get("persona_id") or ""))
        elif selected_source == "repeated_hidden":
            self.last_response_kind = "repeated_hidden_fact"
            content = repeated_fact_response(str(self.persona.get("persona_id") or ""))
        elif selected_source == "new_hidden":
            self.last_response_kind = "new_hidden_fact"
            belief = str(facts_by_id[selected_fact_ids[0]].get("client_belief") or "").strip()
            content = render_grounded_client_response(
                belief, str(self.persona.get("persona_id") or "")
            )
            self.disclosed_fact_ids.add(selected_fact_ids[0])
        elif selected_source == "opening":
            self.last_response_kind = "opening_repeat"
            belief = str(facts_by_id[selected_fact_ids[0]].get("client_belief") or "").strip()
            content = repeated_opening_response(
                belief, str(self.persona.get("persona_id") or "")
            )
        else:
            self.last_response_kind = "unavailable"
            content = unavailable_fact_response(str(self.persona.get("persona_id") or ""))

        last = (
            attempts[-1]
            if attempts
            else ChatResponse(
                content="",
                finish_reason="stop",
                prompt_tokens=0,
                completion_tokens=0,
                raw_id=None,
            )
        )
        response = ChatResponse(
            content=content,
            finish_reason=last.finish_reason,
            prompt_tokens=sum(
                item.prompt_tokens
                for item in [*attempts, *relevance_responses, *disclosure_responses]
            ),
            completion_tokens=sum(
                item.completion_tokens
                for item in [*attempts, *relevance_responses, *disclosure_responses]
            ),
            raw_id=last.raw_id,
        )
        self.history.append((lawyer_question, response.content))
        return response, canonical_json_sha256(
            {
                "selection_request_hashes": selection_request_hashes,
                "relevance_request_hashes": relevance_request_hashes,
                "disclosure_request_hashes": disclosure_request_hashes,
            }
        )


def parse_fact_selection(
    value: str, valid_fact_ids: list[str] | tuple[str, ...]
) -> list[str] | None:
    """Compatibility view of one grounded fact-selection decision.

    Historical code and fixtures consumed only the selected identifier list.  New
    runtime code uses :func:`parse_fact_selection_decision` so that matching and
    disclosure cannot be conflated.
    """

    parsed = parse_fact_selection_decision(value, valid_fact_ids)
    return None if parsed is None else parsed.fact_ids


@dataclass(frozen=True)
class FactSelectionDecision:
    fact_ids: list[str]
    disclosure: DisclosureDecision
    legacy_format: bool = False


def parse_fact_selection_decision(
    value: str, valid_fact_ids: list[str] | tuple[str, ...]
) -> FactSelectionDecision | None:
    """Parse the match/disclosure axes without treating withholding as no match.

    The former ``{"fact_ids": ...}`` shape is deliberately read as ``disclose``
    so archived objects and unit fixtures remain interpretable.  A current-format
    empty match may not carry ``withhold``: withholding necessarily identifies the
    belief that was matched, while an empty list means no candidate answers.
    """

    raw = value.strip()
    candidates = [raw, *re.findall(r"\{[^{}]*\}", raw, flags=re.DOTALL)]
    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(data, dict) or set(data) not in (
            {"fact_ids"},
            {"fact_ids", "disclosure"},
        ):
            continue
        legacy_format = set(data) == {"fact_ids"}
        disclosure = data.get("disclosure", "disclose")
        if disclosure not in {"disclose", "withhold"}:
            continue
        fact_ids = data["fact_ids"]
        if not isinstance(fact_ids, list) or len(fact_ids) > 1:
            continue
        selected: list[str] = []
        for fact_id in fact_ids:
            normalized = str(fact_id)
            if normalized not in valid_fact_ids:
                break
            selected.append(normalized)
        else:
            if not selected and disclosure == "withhold":
                continue
            return FactSelectionDecision(
                fact_ids=selected,
                disclosure=disclosure,
                legacy_format=legacy_format,
            )
    return None


def parse_relevance_analysis(value: str) -> dict[str, object] | None:
    """Parse the auditable proposition-alignment relevance contract."""

    raw = value.strip()
    candidates = [raw, *re.findall(r"\{[^{}]*\}", raw, flags=re.DOTALL)]
    required = set(CLIENT_RELEVANCE_ANALYSIS_SCHEMA["required"])
    source_values = set(
        CLIENT_RELEVANCE_ANALYSIS_SCHEMA["properties"]["candidate_assertion_source"][
            "enum"
        ]
    )
    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(data, dict) or set(data) != required:
            continue
        if not all(
            isinstance(data[field], str)
            for field in (
                "question_actor",
                "question_predicate",
                "question_attribute",
                "candidate_actor",
                "candidate_predicate",
                "candidate_attribute",
            )
        ):
            continue
        if data["candidate_assertion_source"] not in source_values:
            continue
        if not all(
            isinstance(data[field], bool)
            for field in (
                "same_actor",
                "same_predicate",
                "same_attribute",
                "answers_question",
            )
        ):
            continue
        return data
    return None


def structured_proposition_alignment_passed(
    analysis: dict[str, object] | None,
) -> bool:
    """Require semantic predicate and requested-attribute alignment.

    The grammatical actor may differ for passive statements or document-author
    viewpoints, as allowed by the frozen prompt. Sharing an actor alone can never
    make a different action answer the question.
    """

    return bool(
        analysis is not None
        and analysis.get("same_predicate") is True
        and analysis.get("same_attribute") is True
    )


def parse_relevance_check(value: str) -> bool | None:
    """Parse the focused semantic check; malformed output is never treated as approval."""

    analysis = parse_relevance_analysis(value)
    if analysis is not None:
        return bool(analysis["answers_question"])
    raw = value.strip()
    candidates = [raw, *re.findall(r"\{[^{}]*\}", raw, flags=re.DOTALL)]
    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        if (
            isinstance(data, dict)
            and set(data) == {"answers_question"}
            and isinstance(data["answers_question"], bool)
        ):
            return data["answers_question"]
    return None


def parse_disclosure_decision(value: str) -> DisclosureDecision | None:
    """Parse one focused persona disclosure decision exactly."""

    raw = value.strip()
    candidates = [raw, *re.findall(r"\{[^{}]*\}", raw, flags=re.DOTALL)]
    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        if (
            isinstance(data, dict)
            and set(data) == {"disclosure"}
            and data["disclosure"] in {"disclose", "withhold"}
        ):
            return data["disclosure"]
    return None


def render_grounded_client_response(belief: str, persona_id: str) -> str:
    """Render only a benchmark client belief, so the simulator cannot invent evidence."""

    prefixes = {
        "P_WD": "按我的理解，",
        "P_WS": "这个我不太确定，不过按我的理解，",
        "P_CS": "我只能说，按我的理解，",
        "P_CD": "你听我说，按我的理解，",
    }
    return prefixes.get(persona_id, "按我的理解，") + belief


def repeated_fact_response(persona_id: str) -> str:
    if persona_id == "P_CD":
        return "这点我刚才已经说过了，目前没有更多可确认的信息。"
    if persona_id == "P_CS":
        return "刚才说过了，我没有更多信息。"
    return "这项情况我刚才已经说明，目前没有更多可确认的信息。"


def repeated_opening_response(belief: str, persona_id: str) -> str:
    """Restate a public claim and make its zero information gain explicit."""

    suffix = "目前没有更多可确认的信息。"
    if persona_id == "P_CS":
        suffix = "我现在没有更多信息。"
    elif persona_id == "P_CD":
        suffix = "这点别再绕着问了，我目前没有更多可确认的信息。"
    return f"开场时我已经说明过：{belief}；{suffix}"


def withheld_fact_response(persona_id: str) -> str:
    """Render hesitation without leaking the matched hidden belief."""

    if persona_id == "P_CD":
        return "我不接受这种盘问方式。请先说明为什么必须了解这件事。"
    if persona_id == "P_CS":
        return "这个问题我现在还不想细说。"
    if persona_id == "P_WS":
        return "这个问题让我有些不安，我想先缓一缓再说。"
    return "这个问题我暂时不方便回答；请先说明它与咨询有什么关系。"


def unavailable_fact_response(persona_id: str) -> str:
    if persona_id == "P_CD":
        return "这件事我现在确实不知道，不能凭空说。"
    if persona_id == "P_CS":
        return "这个我不清楚。"
    if persona_id == "P_WS":
        return "这个我不太确定，现有信息里没有，我需要再核实。"
    return "现有信息里没有这项具体情况，我需要再核实。"


SLOT_LABELS = {
    "event_time": "关键时间",
    "client_name": "姓名",
    "opening_statement": "开场所述情况",
    "case_type": "案件类型",
    "dispute_type": "争议类型",
    "dispute_details": "纠纷经过",
}
LEGAL_CONCLUSION_PATTERNS = (
    r"明显(?:是|属于).{0,10}(?:违法|侵权)",
    r"(?:应当|应该)承担.{0,8}责任",
    r"属于(?:越权|滥用职权)",
    r"具有法律效力",
    r"应视为.{0,12}(?:有效|无效|履行)",
    r"意味着.{0,12}(?:义务|责任).{0,8}(?:履行|免除)",
    r"(?:构成|属于).{0,12}(?:违法|侵权|违约|不正当竞争)",
    r"(?:肯定|当然|显然).{0,12}(?:违法|侵权|违约)",
)
LEGAL_OPINION_QUALIFIERS = (
    "我认为",
    "按我的理解",
    "我感觉",
    "我担心",
    "我觉得",
    "我猜",
    "可能",
)


def disclosed_fact_indices(facts: list[dict], history: list[tuple[str, str]]) -> set[int]:
    """Conservatively match which hidden fact beliefs were already disclosed."""

    dialogue = "".join(answer for _, answer in history)
    disclosed: set[int] = set()
    for index, fact in enumerate(facts):
        value = str(fact.get("client_belief") or "")
        # Short boilerplate such as “按协议约定” occurs across independent facts and
        # must not make an undisclosed fact look disclosed.  Eight Chinese characters
        # is the minimum supported anchor; exact longer clauses remain conservative.
        chunks = [item for item in re.split(r"[，。；、\s]+", value) if len(item) >= 8]
        if any(chunk in dialogue for chunk in chunks):
            disclosed.add(index)
    return disclosed


def response_violations(value: str) -> list[str]:
    issues = [f"slot_label:{item}" for item in SLOT_LABELS if item in value]
    if any(re.search(pattern, value) for pattern in LEGAL_CONCLUSION_PATTERNS) and not any(
        marker in value for marker in LEGAL_OPINION_QUALIFIERS
    ):
        issues.append("unqualified_legal_conclusion")
    return issues


def sanitize_client_response(value: str, *, remove_false_prior_claim: bool = False) -> str:
    result = value.strip()
    if remove_false_prior_claim:
        result = result.replace("我之前已经说过。", "").replace("我已经说过。", "").strip()
    for slot, label in SLOT_LABELS.items():
        result = result.replace(slot, label)
    if any(re.search(pattern, result) for pattern in LEGAL_CONCLUSION_PATTERNS) and not any(
        marker in result for marker in LEGAL_OPINION_QUALIFIERS
    ):
        result = f"按我的理解，{result}"
    return result
