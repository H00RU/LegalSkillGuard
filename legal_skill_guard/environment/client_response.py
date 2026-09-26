"""Grounded and reproducible client responses for legal consultations.

The client environment has three deliberately separate responsibilities:

1. route the lawyer's natural question to at most one item in the client's
   finite knowledge set, followed by a small frozen check that the selected
   text actually states the exact attribute requested; a rejected selection
   may be returned to the same router for one bounded correction;
2. decide whether a resistant persona discloses an already matched hidden fact;
3. render only dataset text, never model-generated evidence.

The router is not a quality judge.  It receives no score, rubric, skill, arm,
court record, or dialogue-policy metadata.  Python validates the finite
identifier/schema boundary and a short, frozen set of literal attribute-
sufficiency contracts.  It never chooses a different fact, rewrites a rejected
selection into an empty one, or infers a legal answer.  Instead, the same frozen
router must correct its own decision within the existing attempt budget.  Only
an unrepaired selection is a routing-contract failure; a model-returned empty
correction is valid evidence that the finite client knowledge cannot answer.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, replace
from pathlib import Path

from legal_skill_guard.inference.openai_client import (
    ChatClient,
    ChatResponse,
    GenerationConfig,
)
from legal_skill_guard.schemas.state import ClientResponseKind, DisclosureDecision
from legal_skill_guard.text_normalization import normalize_question
from legal_skill_guard.utils.hashing import canonical_json_sha256

CLIENT_FACT_SELECTION_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "question_actor": {"type": "string", "maxLength": 64},
        "question_event": {"type": "string", "maxLength": 96},
        "question_attribute": {"type": "string", "maxLength": 96},
        "selected_relation": {
            "type": "string",
            "enum": [
                "direct_answer",
                "partial_answer",
                "premise_correction",
                "not_answer",
            ],
        },
        "fact_ids": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 1,
        }
    },
    "required": [
        "question_actor",
        "question_event",
        "question_attribute",
        "selected_relation",
        "fact_ids",
    ],
    "additionalProperties": False,
}


def client_fact_selection_schema(valid_fact_ids: list[str]) -> dict[str, object]:
    """Bind structured decoding to the exact finite knowledge set."""

    fact_id_items: dict[str, object] = {"type": "string"}
    if valid_fact_ids:
        fact_id_items["enum"] = valid_fact_ids
    return {
        "type": "object",
        "properties": {
            "question_actor": {"type": "string", "maxLength": 64},
            "question_event": {"type": "string", "maxLength": 96},
            "question_attribute": {"type": "string", "maxLength": 96},
            "selected_relation": {
                "type": "string",
                "enum": [
                    "direct_answer",
                    "partial_answer",
                    "premise_correction",
                    "not_answer",
                ],
            },
            "fact_ids": {
                "type": "array",
                "items": fact_id_items,
                "maxItems": 1 if valid_fact_ids else 0,
            }
        },
        "required": [
            "question_actor",
            "question_event",
            "question_attribute",
            "selected_relation",
            "fact_ids",
        ],
        "additionalProperties": False,
    }


CLIENT_DISCLOSURE_SIGNALS_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "sensitive_personal_misconduct": {"type": "boolean"},
        "accusatory_presumption": {"type": "boolean"},
        "coercive_pressure": {"type": "boolean"},
        "purpose_explained": {"type": "boolean"},
    },
    "required": [
        "sensitive_personal_misconduct",
        "accusatory_presumption",
        "coercive_pressure",
        "purpose_explained",
    ],
    "additionalProperties": False,
}


CLIENT_ROUTE_STRUCTURE_REPAIR_INSTRUCTION = (
    "上一输出结构或字段关系无效。仅返回符合给定schema的完整JSON对象。"
    "fact_ids为空时selected_relation必须为not_answer；"
    "selected_relation为direct_answer、partial_answer或premise_correction时，"
    "fact_ids必须且只能包含一个候选编号。"
)

CLIENT_ROUTE_EMPTY_RECHECK_INSTRUCTION = (
    "上一输出认为全部候选都不能回答。请在同一候选集合中再独立复核一次主体、事件和"
    "所问属性，特别检查是否有候选明确否定问题前提、给出较粗但真实的属性值，或在混合"
    "表述中明确陈述了所问事实。不得因同案相关或关键词相同而选择；若仍无直接、部分或"
    "前提纠正答案，保持fact_ids为空且selected_relation为not_answer。"
)


def client_generation_request_sha256(
    *,
    model: str,
    messages: list[dict[str, str]],
    generation: GenerationConfig,
) -> str:
    """Bind an audited client request to its complete generation envelope."""

    return canonical_json_sha256(
        {
            "model": model,
            "messages": messages,
            "generation": {
                "temperature": generation.temperature,
                "top_p": generation.top_p,
                "max_tokens": generation.max_tokens,
                "seed": generation.seed,
                "disable_thinking": generation.disable_thinking,
                "reasoning_effort": generation.reasoning_effort,
                "response_schema": generation.response_schema,
                "response_schema_name": generation.response_schema_name,
            },
        }
    )


EVENT_CONCEPT_PATTERNS: dict[str, tuple[str, ...]] = {
    "purchase": ("购买", "购房", "买房", "购置"),
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
        "转账",
    ),
    "signing": ("签署", "签订", "订立", "落款"),
    "notice": ("通知", "告知", "送达", "收到", "答复"),
    "filing": ("起诉", "立案", "仲裁", "复议", "报案", "申请执行"),
    "physical_injury": ("受伤", "伤情", "损伤", "挫伤", "伤势"),
    "physical_assault": ("殴打", "击打", "打伤", "施暴", "暴力行为"),
    "contract_renewal": ("续签", "续订"),
    "employment_termination": ("解除劳动合同", "终止劳动合同", "离职协议"),
    "employment_continuation": ("继续工作", "继续用工", "仍在工作", "仍按原约定付薪"),
}


def event_concepts(value: str) -> set[str]:
    return {
        concept
        for concept, patterns in EVENT_CONCEPT_PATTERNS.items()
        if any(pattern in value for pattern in patterns)
    }


def localized(value: object, language: str = "zh") -> str:
    if isinstance(value, dict):
        return str(value.get(language) or value.get("en") or "")
    return str(value or "")


def opening_fact_candidates(opening: str) -> list[dict[str, str]]:
    claims = [
        item.strip(" ，,。；;！？!?\t")
        for item in re.split(r"[。；;！？!?\n]+", opening.strip())
        if len(item.strip(" ，,。；;！？!?\t")) >= 4
    ]
    return [
        {"fact_id": f"O{index}", "client_belief": claim, "source": "opening"}
        for index, claim in enumerate(claims, start=1)
    ]


@dataclass(frozen=True)
class FactSelectionDecision:
    fact_ids: list[str]
    question_actor: str = ""
    question_event: str = ""
    question_attribute: str = ""
    selected_relation: str = "not_answer"


def _json_objects(value: str) -> list[str]:
    raw = value.strip()
    return [raw, *re.findall(r"\{[^{}]*\}", raw, flags=re.DOTALL)]


def parse_fact_selection_decision(
    value: str, valid_fact_ids: list[str] | tuple[str, ...]
) -> FactSelectionDecision | None:
    """Parse exactly one finite-set routing decision.

    Only the current auditable actor/event/attribute/relation shape is accepted.
    Readers for historical fact-id-only artifacts live under ``tests/legacy_support``;
    accepting that abbreviated object in the live parser would bypass the current
    routing contract.
    """

    valid = set(valid_fact_ids)
    for candidate in _json_objects(value):
        try:
            data = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(data, dict):
            continue
        fact_ids = data.get("fact_ids")
        if not isinstance(fact_ids, list) or len(fact_ids) > 1:
            continue
        normalized = [str(item) for item in fact_ids]
        if any(item not in valid for item in normalized):
            continue
        required = set(CLIENT_FACT_SELECTION_SCHEMA["required"])
        if set(data) != required:
            continue
        if not all(
            isinstance(data.get(key), str)
            for key in ("question_actor", "question_event", "question_attribute")
        ):
            continue
        selected_relation = data.get("selected_relation")
        if selected_relation not in {
            "direct_answer",
            "partial_answer",
            "premise_correction",
            "not_answer",
        }:
            continue
        if normalized and selected_relation not in {
            "direct_answer",
            "partial_answer",
            "premise_correction",
        }:
            continue
        if not normalized and selected_relation != "not_answer":
            continue
        return FactSelectionDecision(
            fact_ids=normalized,
            question_actor=data["question_actor"],
            question_event=data["question_event"],
            question_attribute=data["question_attribute"],
            selected_relation=str(selected_relation),
        )
    return None


def parse_fact_selection(
    value: str, valid_fact_ids: list[str] | tuple[str, ...]
) -> list[str] | None:
    parsed = parse_fact_selection_decision(value, valid_fact_ids)
    return None if parsed is None else parsed.fact_ids


def client_fact_attribute_sufficiency_violations(
    question: str, candidate_belief: str
) -> list[str]:
    """Reject a selected belief that omits a narrowly typed requested attribute.

    This is deliberately not a second semantic router.  The checks neither rank
    facts nor recover a match after the model returns none.  They only verify
    literal evidence for eight high-precision attribute forms whose absence
    cannot answer the question: formal acceptance, registered ownership,
    completion of every questionnaire item, itemised amounts, an application
    channel, a legal/authorisation basis, authority status, and an identified
    target audience.
    """

    query = re.sub(r"\s+", "", question)
    belief = re.sub(r"\s+", "", candidate_belief)
    violations: list[str] = []

    # Existence of an instrument is a distinct attribute from mentioning that
    # instrument in a hypothetical or legal proposition.  A previous router
    # treated “即使合同和交易习惯从未提及” as a premise correction to “是否有
    # 书面合同”, creating a false fact gain.  Require the candidate itself to
    # assert formation/existence or non-existence of the requested instrument.
    instrument = (
        r"(?:书面)?(?:合同|协议|订单|通知(?:书)?|决定(?:书)?|判决(?:书)?|"
        r"裁定(?:书)?|文件|文书)"
    )
    existence_verb = r"(?:存在|签订|签署|订立|形成|收到|取得|持有|作出|出具)"
    asks_instrument_existence = bool(
        re.search(rf"(?:是否存在|有无|有没有).{{0,8}}{instrument}", query)
        or re.search(rf"(?:是否|有无|有没有).{{0,8}}{existence_verb}.{{0,8}}{instrument}", query)
        or re.search(rf"{instrument}.{{0,12}}(?:是否存在|有无|有没有)", query)
        or re.search(rf"{instrument}.{{0,8}}(?:是否)?{existence_verb}", query)
    )
    states_instrument_existence = bool(
        re.search(
            rf"(?:已经|已|曾|双方|我们|我|对方)?.{{0,8}}"
            rf"(?:签订|签署|订立|形成|收到|取得|持有|存在|有).{{0,8}}{instrument}",
            belief,
        )
        or re.search(
            rf"{instrument}.{{0,12}}(?:已经|已|曾)?(?:签订|签署|订立|形成|收到|取得|持有|存在)",
            belief,
        )
        or re.search(
            rf"(?:没有|未|尚未|从未|不存在|未曾).{{0,12}}"
            rf"(?:签订|签署|订立|形成|收到|取得|持有)?{instrument}",
            belief,
        )
        or re.search(
            rf"{instrument}.{{0,6}}(?:没有|尚未|从未|不存在|未曾)"
            rf"(?:被)?(?:签订|签署|订立|形成|收到|取得|持有|作出|出具)",
            belief,
        )
        or re.search(rf"{instrument}.{{0,4}}不存在", belief)
        or re.search(r"(?:拒绝|不同意|未同意).{0,8}(?:续签|签订|签署|订立)", belief)
        or re.search(r"(?:续签|签订|签署|订立).{0,8}(?:被拒绝|遭拒绝|拒绝|不同意)", belief)
    )
    if asks_instrument_existence and not states_instrument_existence:
        violations.append("instrument_existence_not_stated")

    if "受理" in query and "受理" not in belief:
        violations.append("formal_acceptance_not_stated")

    asks_registered_owner = re.search(
        r"(登记.{0,10}名下|产权.{0,8}(?:属于|归属|名下)|"
        r"权属.{0,8}(?:属于|归属|名下))",
        query,
    )
    states_registered_owner = bool(
        re.search(r"(登记|产权|权属|所有权|不动产权证|房产证)", belief)
        or re.search(r"(?:改成|写在|加上|加到).{0,12}(?:名字|名下)", belief)
        or re.search(
            r"(?:名字|名下).{0,12}(?:改成|登记|写入|加上|加到)", belief
        )
    )
    if asks_registered_owner and not states_registered_owner:
        violations.append("registration_relation_not_stated")

    asks_complete_questionnaire = bool(
        re.search(r"(回答|填写|勾选|告知)", query)
        and re.search(r"(全部|所有|每一|各项)", query)
    )
    states_complete_questionnaire = bool(
        re.search(r"(回答|填写|勾选|告知)", belief)
        and re.search(r"(全部|所有|每一|各项)", belief)
    )
    if asks_complete_questionnaire and not states_complete_questionnaire:
        violations.append("questionnaire_completion_not_stated")

    asks_negotiation_event = bool(re.search(r"(?:协商|商量|沟通)", query))
    states_negotiation_event = bool(re.search(r"(?:协商|商量|沟通)", belief))
    if asks_negotiation_event and not states_negotiation_event:
        violations.append("negotiation_event_not_stated")

    asks_specific_entity_name = bool(
        re.search(r"(?:叫什么|具体(?:的)?).{0,5}(?:名称|名字)", query)
        or re.search(r"分别.{0,8}(?:名称|名字)", query)
    )
    states_specific_entity_name = bool(
        re.search(
            r"(?:企业名称为|公司名称为|名称是|名称为|名为|叫做).{1,20}",
            belief,
        )
        or re.search(
            r"[\u4e00-\u9fffA-Za-z0-9]{2,}"
            r"(?:有限责任公司|股份有限公司|集团有限公司)",
            belief,
        )
    )
    if asks_specific_entity_name and not states_specific_entity_name:
        violations.append("specific_entity_names_not_stated")

    if "分别" in query and re.search(r"(多少|金额|数额|出资)", query):
        amount_expressions = re.findall(
            r"(?:\d+(?:\.\d+)?|[一二三四五六七八九十百千万两]+)"
            r"(?:万|千|百)?元",
            belief,
        )
        if len(amount_expressions) < 2:
            violations.append("itemized_amounts_not_stated")

    asks_application_event = re.search(r"(申请|办理|提交|取消|退款|退票)", query)
    asks_method = re.search(
        r"(?:什么|何种|哪种|具体).{0,4}(?:方式|渠道|途径)|"
        r"(?:通过|经由|如何|怎么).{0,8}(?:申请|办理|提交|取消|退款|退票)",
        query,
    )
    states_application_method = re.search(
        r"(?:通过|经由|使用|登录).{0,12}"
        r"(?:申请|办理|提交|取消|退款|退票)|"
        r"在.{0,8}(?:平台|APP|App|app|应用|网站|柜台)"
        r"(?:上|内)?(?:申请|办理|提交|取消|退款|退票)|"
        r"(?:申请|办理|提交|取消|退款|退票).{0,12}"
        r"(?:渠道|方式|平台|APP|App|app|网站|柜台|电话|线下|线上)",
        belief,
    )
    if asks_application_event and asks_method and not states_application_method:
        violations.append("application_channel_not_stated")

    asks_legal_basis = re.search(
        r"(?:上位法|法律|法定|授权).{0,8}(?:依据|条款)|"
        r"(?:依据|条款).{0,8}(?:上位法|法律|法定|授权)",
        query,
    )
    states_legal_basis = re.search(
        r"(依据|根据|条例|法律|授权|第.{0,8}条)", belief
    )
    if asks_legal_basis and not states_legal_basis:
        violations.append("legal_basis_not_stated")

    asks_authority_status = re.search(
        r"(?:是否|有无).{0,12}(?:有权|有权限|"
        r"(?:具有|具备|享有|拥有).{0,12}(?:权限|权力|职权))",
        query,
    )
    states_authority_status = re.search(
        r"(?:有权|无权|权限|授权|职权|职责范围)", belief
    )
    if asks_authority_status and not states_authority_status:
        violations.append("authority_status_not_stated")

    asks_target_audience = bool(
        re.search(
            r"(?:目标(?:受众|人群|群体|客户|用户)|"
            r"(?:消费者|消费|客户|用户|受众)(?:群体|人群|类型|类别|对象)|"
            r"服务对象)",
            query,
        )
        or re.search(
            r"(?:面向|针对|服务于|适用于).{0,12}"
            r"(?:谁|哪些人|哪类|何种)(?:目标)?"
            r"(?:消费者|客户|用户|人群|群体|受众|对象)",
            query,
        )
    )
    audience_category = (
        r"(?:儿童|未成年人|青少年|成年人|老年人|男性|女性|"
        r"孕妇|学生|职工|劳动者|骑手|驾驶员|旅客|患者|居民|"
        r"企业|机构|商户|个人|专业人士)"
    )
    states_target_audience = bool(
        re.search(
            rf"(?:面向|针对|服务于|适用于).{{0,18}}{audience_category}",
            belief,
        )
        or re.search(
            rf"(?:目标受众|目标人群|目标群体|客户群体|"
            rf"用户群体|消费者群体|服务对象)"
            rf"(?:是|为|包括|主要是).{{0,18}}{audience_category}",
            belief,
        )
        or re.search(
            rf"{audience_category}.{{0,8}}(?:消费者|客户|用户|人群|群体|受众)",
            belief,
        )
    )
    if asks_target_audience and not states_target_audience:
        violations.append("target_audience_not_stated")

    return violations


@dataclass(frozen=True)
class DisclosureSignals:
    sensitive_personal_misconduct: bool
    accusatory_presumption: bool
    coercive_pressure: bool
    purpose_explained: bool


def parse_disclosure_signals(value: str) -> DisclosureSignals | None:
    for candidate in _json_objects(value):
        try:
            data = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(data, dict) or set(data) != set(
            CLIENT_DISCLOSURE_SIGNALS_SCHEMA["required"]
        ):
            continue
        sensitive = data["sensitive_personal_misconduct"]
        accusatory = data["accusatory_presumption"]
        coercive = data["coercive_pressure"]
        explained = data["purpose_explained"]
        if (
            isinstance(sensitive, bool)
            and isinstance(accusatory, bool)
            and isinstance(coercive, bool)
            and isinstance(explained, bool)
        ):
            return DisclosureSignals(sensitive, accusatory, coercive, explained)
    return None


def disclosure_from_signals(
    persona_id: str, signals: DisclosureSignals
) -> DisclosureDecision:
    if signals.purpose_explained or not signals.sensitive_personal_misconduct:
        return "disclose"
    if persona_id == "P_CS" and (
        signals.accusatory_presumption or signals.coercive_pressure
    ):
        return "withhold"
    if persona_id == "P_CD" and signals.coercive_pressure:
        return "withhold"
    return "disclose"


@dataclass
class ClientSimulator:
    case_view: dict
    persona: dict
    model: ChatClient
    prompt_template: str
    disclosure_prompt: str
    generation: GenerationConfig
    max_selection_attempts: int
    disclosure_model: ChatClient | None = None
    history: list[tuple[str, str]] = field(default_factory=list)
    disclosed_fact_ids: set[str] = field(default_factory=set, init=False)
    # The client is a fixed environment, not a fresh semantic judge on every turn.
    # Once an exact lawyer question has been routed against this case/persona, a
    # later byte-normalized repeat must keep the same finite-knowledge relation.
    # Without this memory, the router could first return ``not_answer`` and later
    # map the identical question to a hidden fact merely because another target was
    # disclosed in between, creating a false TF-GRPO advantage.
    route_decisions_by_question: dict[str, FactSelectionDecision] = field(
        default_factory=dict, init=False
    )
    last_selection_attempts: list[str] = field(default_factory=list, init=False)
    last_selection_attempt_records: list[dict[str, object]] = field(
        default_factory=list, init=False
    )
    last_opening_selection_attempts: list[str] = field(default_factory=list, init=False)
    last_disclosure_attempts: list[str] = field(default_factory=list, init=False)
    last_route_passed: bool | None = field(default=None, init=False)
    last_route_candidate_fact_id: str | None = field(default=None, init=False)
    last_route_guard_violations: list[str] = field(default_factory=list, init=False)
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
        disclosure_template_path: Path | None = None,
        disclosure_model: ChatClient | None = None,
    ) -> ClientSimulator:
        if max_selection_attempts < 1:
            raise ValueError("client max_selection_attempts must be positive")
        return cls(
            case_view=case_view,
            persona=persona,
            model=model,
            prompt_template=template_path.read_text(encoding="utf-8").strip(),
            disclosure_prompt=(
                disclosure_template_path.read_text(encoding="utf-8").strip()
                if disclosure_template_path is not None
                else ""
            ),
            generation=generation,
            max_selection_attempts=max_selection_attempts,
            disclosure_model=disclosure_model,
        )

    def _all_candidates(self) -> list[dict[str, object]]:
        hidden = [dict(item, source="hidden") for item in self.case_view.get("facts", [])]
        opening = opening_fact_candidates(str(self.case_view.get("opening") or ""))
        return [*hidden, *opening]

    def _messages_for_facts(
        self, lawyer_question: str, facts: list[dict[str, object]]
    ) -> list[dict[str, str]]:
        rows = []
        for fact in facts:
            fact_id = str(fact["fact_id"])
            source = "开场陈述" if fact_id.startswith("O") else "客户有限认知"
            rows.append(f"- {fact_id} [{source}]：{fact['client_belief']}")
        system = self.prompt_template.format(
            persona_id=str(self.persona.get("persona_id") or ""),
            persona_who=localized(self.persona.get("who")),
            persona_voice=localized(self.persona.get("voice")),
            facts_block="\n".join(rows),
        )
        # Deliberately omit dialogue history and disclosure state. Generated lawyer
        # questions must be self-contained; neither irrelevant preceding turns nor
        # another fact's disclosure may alter which fixed client belief answers the
        # same current question. The state machine classifies a selected belief as
        # new, repeated, or opening information only after this semantic routing.
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": f"律师本轮问题：{lawyer_question.strip()}"},
        ]

    def _messages(self, lawyer_question: str) -> list[dict[str, str]]:
        return self._messages_for_facts(lawyer_question, self._all_candidates())

    def _disclosure_messages(
        self, lawyer_question: str, matched_belief: str
    ) -> list[dict[str, str]]:
        system = self.disclosure_prompt.format(
            persona_id=str(self.persona.get("persona_id") or ""),
            persona_who=localized(self.persona.get("who")),
            persona_voice=localized(self.persona.get("voice")),
            matched_belief=matched_belief,
        )
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": f"律师本轮问题：{lawyer_question.strip()}"},
        ]

    def _reset_audit(self) -> None:
        self.last_selection_attempts = []
        self.last_selection_attempt_records = []
        self.last_opening_selection_attempts = []
        self.last_disclosure_attempts = []
        self.last_route_passed = None
        self.last_route_candidate_fact_id = None
        self.last_route_guard_violations = []
        self.last_matched_fact_ids = []
        self.last_selected_fact_ids = []
        self.last_opening_reference_ids = []
        self.last_disclosure_decision = None
        self.last_response_kind = None
        self.last_safe_fallback = False

    def respond(
        self,
        lawyer_question: str,
        seed: int,
        *,
        routing_question: str | None = None,
    ) -> tuple[ChatResponse, str]:
        """Route one question against the finite client knowledge set.

        ``routing_question`` is an optional system-owned semantic target label.
        The stateful runner supplies it for planned targets so two policy samples
        asking the same visible target through harmless paraphrases see the same
        client routing problem.  The actual lawyer wording is still retained in
        dialogue history and drives resistant-persona disclosure, so coercive or
        purpose-explaining language is not erased.
        """

        self._reset_audit()
        semantic_question = str(routing_question or lawyer_question).strip()
        if not semantic_question:
            semantic_question = lawyer_question.strip()
        exact_question_key = normalize_question(lawyer_question)
        candidates = self._all_candidates()
        valid_ids = [str(item["fact_id"]) for item in candidates]
        allowed_fact_ids = list(valid_ids)
        by_id = {str(item["fact_id"]): item for item in candidates}
        selection_messages = self._messages_for_facts(semantic_question, candidates)
        selection_hashes: list[str] = []
        disclosure_hashes: list[str] = []
        responses: list[ChatResponse] = []
        selection: FactSelectionDecision | None = None
        valid_empty_selection: FactSelectionDecision | None = None
        repair_instruction: str | None = None
        empty_recheck_used = False
        last_guard_candidate_id: str | None = None
        last_guard_violations: list[str] = []

        cached_selection = self.route_decisions_by_question.get(exact_question_key)
        if cached_selection is not None:
            cached_payload = json.dumps(
                {
                    "question_actor": cached_selection.question_actor,
                    "question_event": cached_selection.question_event,
                    "question_attribute": cached_selection.question_attribute,
                    "selected_relation": cached_selection.selected_relation,
                    "fact_ids": list(cached_selection.fact_ids),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            selection = cached_selection
            self.last_selection_attempts.append(cached_payload)
            selection_hashes.append(
                canonical_json_sha256(
                    {
                        "exact_question_route_replay": exact_question_key,
                        "selection": cached_payload,
                    }
                )
            )
            responses.append(
                ChatResponse(
                    content=cached_payload,
                    finish_reason="stop",
                    prompt_tokens=0,
                    completion_tokens=0,
                    raw_id=None,
                )
            )
            cached_guard_violations: list[str] = []
            if cached_selection.fact_ids:
                cached_id = cached_selection.fact_ids[0]
                cached_guard_violations = client_fact_attribute_sufficiency_violations(
                    semantic_question, str(by_id[cached_id]["client_belief"])
                )
            cached_partial_invalid = bool(
                cached_selection.fact_ids
                and cached_selection.selected_relation == "partial_answer"
                and cached_guard_violations
            )
            self.last_selection_attempt_records.append(
                {
                    "raw_output": cached_payload,
                    "selected_fact_id": (
                        cached_selection.fact_ids[0]
                        if cached_selection.fact_ids
                        else None
                    ),
                    "selected_relation": cached_selection.selected_relation,
                    "deterministic_compatibility_violations": cached_guard_violations,
                    "attribute_gate_disposition": (
                        "rejected"
                        if cached_partial_invalid
                        else "passed"
                        if cached_selection.fact_ids
                        else "not_applicable"
                    ),
                }
            )
            if cached_partial_invalid:
                # Defensive invalidation for an in-process cache created under a
                # different contract. Current entries are cached only after this
                # same check passes, so formal runs do not normally take this path.
                self.route_decisions_by_question.pop(exact_question_key, None)
                cached_selection = None
                selection = None

        for attempt_index in range(
            0 if cached_selection is not None else self.max_selection_attempts
        ):
            messages = list(selection_messages)
            if repair_instruction is not None:
                messages.append({"role": "user", "content": repair_instruction})
            elif attempt_index:
                messages.append(
                    {
                        "role": "user",
                        "content": CLIENT_ROUTE_STRUCTURE_REPAIR_INSTRUCTION,
                    }
                )
            attempt_generation = self.generation
            if attempt_index and self.generation.reasoning_effort in {"medium", "high"}:
                # Every retry is already a narrower contract-repair task: either the
                # prior output was structurally invalid, or a literal attribute gate
                # removed candidates that cannot answer the question.  Re-entering
                # medium/high hidden reasoning on that finite repair can consume the
                # output budget without emitting JSON, even when the narrowed schema
                # contains a single valid candidate.  Keep the first semantic route at
                # the frozen configured effort, then use the same frozen model and
                # evidence at low effort for all bounded repairs.  This changes neither
                # the candidate set nor the accepted relation and never infers a match.
                attempt_generation = replace(self.generation, reasoning_effort="low")
            response_schema = client_fact_selection_schema(allowed_fact_ids)
            request_generation = replace(
                attempt_generation,
                seed=seed + attempt_index,
                response_schema=response_schema,
                response_schema_name="legal_skill_guard_client_fact_route",
            )
            selection_hashes.append(
                client_generation_request_sha256(
                    model=self.model.model,
                    messages=messages,
                    generation=request_generation,
                )
            )
            response = self.model.generate(messages, request_generation)
            responses.append(response)
            self.last_selection_attempts.append(response.content)
            selection = parse_fact_selection_decision(response.content, allowed_fact_ids)
            if selection is None:
                self.last_selection_attempt_records.append(
                    {
                        "raw_output": response.content,
                        "selected_fact_id": None,
                        "selected_relation": None,
                        "deterministic_compatibility_violations": [],
                        "attribute_gate_disposition": "not_applicable",
                    }
                )
                repair_instruction = CLIENT_ROUTE_STRUCTURE_REPAIR_INSTRUCTION
                continue
            if not selection.fact_ids:
                # This is already a structurally valid model decision.  Keep it
                # transactionally while allowing one optional semantic recheck;
                # only another valid route may supersede it.  A malformed output
                # or a candidate rejected by the literal attribute gate cannot
                # retroactively turn a valid empty route into contract failure.
                valid_empty_selection = selection
                request_empty_recheck = bool(
                    not empty_recheck_used
                    and attempt_index + 1 < self.max_selection_attempts
                )
                self.last_selection_attempt_records.append(
                    {
                        "raw_output": response.content,
                        "selected_fact_id": None,
                        "selected_relation": selection.selected_relation,
                        "deterministic_compatibility_violations": [],
                        "attribute_gate_disposition": (
                            "empty_recheck_requested"
                            if request_empty_recheck
                            else "not_applicable"
                        ),
                    }
                )
                if request_empty_recheck:
                    # An empty decision is semantically valid only after one
                    # bounded same-router self-check.  This uses the existing
                    # attempt budget and the same finite candidates; Python does
                    # not restore a fact, rank candidates, or infer an answer.
                    empty_recheck_used = True
                    selection = None
                    repair_instruction = CLIENT_ROUTE_EMPTY_RECHECK_INSTRUCTION
                    continue
                break
            selected_id = selection.fact_ids[0]
            guard_violations = client_fact_attribute_sufficiency_violations(
                semantic_question, str(by_id[selected_id]["client_belief"])
            )
            if not guard_violations:
                self.last_selection_attempt_records.append(
                    {
                        "raw_output": response.content,
                        "selected_fact_id": selected_id,
                        "selected_relation": selection.selected_relation,
                        "deterministic_compatibility_violations": [],
                        "attribute_gate_disposition": "passed",
                    }
                )
                break
            self.last_selection_attempt_records.append(
                {
                    "raw_output": response.content,
                    "selected_fact_id": selected_id,
                    "selected_relation": selection.selected_relation,
                    "deterministic_compatibility_violations": guard_violations,
                    "attribute_gate_disposition": "rejected",
                }
            )
            last_guard_candidate_id = selected_id
            last_guard_violations = guard_violations
            allowed_fact_ids = [
                fact_id
                for fact_id in valid_ids
                if not client_fact_attribute_sufficiency_violations(
                    semantic_question, str(by_id[fact_id]["client_belief"])
                )
            ]
            excluded_fact_ids = [
                fact_id for fact_id in valid_ids if fact_id not in allowed_fact_ids
            ]
            selection = None
            repair_instruction = (
                "上一选择的候选文本没有明确陈述本问题所问的具体属性，不能作为答案。"
                f"文字充分性检查已排除候选编号：{','.join(excluded_fact_ids)}。"
                "请只在其余候选中重新比较；只有另一候选明确回答该属性时才选择它，否则必须"
                "令fact_ids为空且selected_relation为not_answer。不得根据同案背景、"
                "关键词或法律推断补足缺失属性。"
            )

        if selection is None and valid_empty_selection is not None:
            selection = valid_empty_selection

        if selection is not None and exact_question_key:
            self.route_decisions_by_question.setdefault(exact_question_key, selection)

        if selection is None:
            self.last_safe_fallback = True
            self.last_route_passed = False
            self.last_route_candidate_fact_id = last_guard_candidate_id
            self.last_route_guard_violations = last_guard_violations
            self.last_response_kind = "contract_fallback"
            content = unavailable_fact_response(str(self.persona.get("persona_id") or ""))
        elif not selection.fact_ids:
            self.last_route_passed = True
            self.last_response_kind = "unavailable"
            content = unavailable_fact_response(str(self.persona.get("persona_id") or ""))
        else:
            selected_id = selection.fact_ids[0]
            selected = by_id[selected_id]
            selected_belief = str(selected["client_belief"])
            persona_id = str(self.persona.get("persona_id") or "")
            self.last_route_candidate_fact_id = selected_id
            self.last_matched_fact_ids = [selected_id]
            self.last_route_passed = True
            disclosure: DisclosureDecision = "disclose"

            if (  # noqa: SIM102 - keep disclosure eligibility separate from persona policy
                selected_id.startswith("F")
                and selected_id not in self.disclosed_fact_ids
            ):
                if persona_id in {"P_CS", "P_CD"}:
                    messages = self._disclosure_messages(lawyer_question, selected_belief)
                    for attempt_index in range(self.max_selection_attempts):
                        disclosure_client = self.disclosure_model or self.model
                        disclosure_generation = GenerationConfig(
                            temperature=0.0,
                            top_p=1.0,
                            max_tokens=96,
                            seed=seed + 5_000 + attempt_index,
                            disable_thinking=True,
                            response_schema=CLIENT_DISCLOSURE_SIGNALS_SCHEMA,
                            response_schema_name=(
                                "legal_skill_guard_client_disclosure_signals"
                            ),
                        )
                        disclosure_hashes.append(
                            client_generation_request_sha256(
                                model=disclosure_client.model,
                                messages=messages,
                                generation=disclosure_generation,
                            )
                        )
                        response = disclosure_client.generate(
                            messages, disclosure_generation
                        )
                        responses.append(response)
                        self.last_disclosure_attempts.append(response.content)
                        signals = parse_disclosure_signals(response.content)
                        if signals is not None:
                            disclosure = disclosure_from_signals(persona_id, signals)
                            break
                        messages = [
                            *messages,
                            {
                                "role": "user",
                                "content": (
                                    "上一输出结构无效。只返回给定的四个原子判断字段。"
                                ),
                            },
                        ]
                    else:
                        self.last_safe_fallback = True
                        self.last_route_passed = False
                        self.last_matched_fact_ids = []
                        self.last_response_kind = "contract_fallback"
                        content = unavailable_fact_response(persona_id)

            if self.last_response_kind != "contract_fallback":
                self.last_disclosure_decision = disclosure
                if selected_id.startswith("O"):
                    self.last_opening_reference_ids = [selected_id]
                    self.last_response_kind = "opening_repeat"
                    content = repeated_opening_response(selected_belief, persona_id)
                elif disclosure == "withhold":
                    self.last_response_kind = "withheld"
                    content = withheld_fact_response(persona_id)
                elif selected_id in self.disclosed_fact_ids:
                    self.last_selected_fact_ids = [selected_id]
                    self.last_response_kind = "repeated_hidden_fact"
                    content = repeated_fact_response(persona_id)
                else:
                    self.disclosed_fact_ids.add(selected_id)
                    self.last_selected_fact_ids = [selected_id]
                    self.last_response_kind = "new_hidden_fact"
                    content = render_grounded_client_response(
                        selected_belief, persona_id
                    )

        last = responses[-1]
        rendered = ChatResponse(
            content=content,
            finish_reason=last.finish_reason,
            prompt_tokens=sum(item.prompt_tokens for item in responses),
            completion_tokens=sum(item.completion_tokens for item in responses),
            raw_id=last.raw_id,
        )
        self.history.append((lawyer_question, rendered.content))
        return rendered, canonical_json_sha256(
            {
                "selection_request_hashes": selection_hashes,
                "disclosure_request_hashes": disclosure_hashes,
            }
        )


def render_grounded_client_response(belief: str, persona_id: str) -> str:
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
    suffix = "目前没有更多可确认的信息。"
    if persona_id == "P_CS":
        suffix = "我现在没有更多信息。"
    elif persona_id == "P_CD":
        suffix = "这点别再绕着问了，我目前没有更多可确认的信息。"
    return f"开场时我已经说明过：{belief}；{suffix}"


def withheld_fact_response(persona_id: str) -> str:
    if persona_id == "P_CD":
        return "我不接受这种盘问方式。请先说明为什么必须了解这件事。"
    return "这个问题我现在还不想细说。"


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
    r"(?:构成|属于).{0,12}(?:违法|侵权|违约|不正当竞争)",
)
LEGAL_OPINION_QUALIFIERS = ("我认为", "按我的理解", "我感觉", "我担心", "我觉得", "可能")


def disclosed_fact_indices(facts: list[dict], history: list[tuple[str, str]]) -> set[int]:
    dialogue = "".join(answer for _, answer in history)
    disclosed: set[int] = set()
    for index, fact in enumerate(facts):
        value = str(fact.get("client_belief") or "")
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
