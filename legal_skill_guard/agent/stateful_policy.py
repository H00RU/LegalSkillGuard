"""Parse state-patch plus action envelopes and deterministically render actions."""

from __future__ import annotations

import hashlib
import json
import re

from legal_skill_guard.agent.action_parser import _balanced_json_objects
from legal_skill_guard.agent.state_manager import is_concrete_evidence_label
from legal_skill_guard.schemas.action import StructuredAction
from legal_skill_guard.schemas.experiment import PolicyEnvelope
from legal_skill_guard.schemas.state import (
    NON_SUBSTANTIVE_FACT_IDS,
    ConsultationState,
    FactObservation,
    StatePatch,
)
from legal_skill_guard.text_normalization import normalize_question

POLICY_FALLBACK_REASONS = frozenset(
    {
        "invalid_structured_output",
        "policy_contract_safe_fallback",
        "safe_fallback_topics_exhausted",
        "safe_fallback_conditional_memo_available",
        "safe_fallback_no_grounded_unresolved_target",
    }
)

# Only explicit separators are safe without a Chinese tokenizer or a structured
# planner field.  A bare ``及``/``和``/``与`` is also an ordinary character in words
# such as ``及时`` and ``和好`` (and can connect the actors of one relation).  Older
# negative-lookbehind lists inevitably missed new words and once rendered targets
# such as ``公司是否及时……`` as the meaningless question ``公司是否？``.
# Keep this delimiter deliberately small; ambiguous labels must be repaired by the
# planner instead of being guessed apart at execution time.
ATTRIBUTE_COORDINATION_PATTERN = r"(?:以及|、)"

ABSTRACT_FACT_LABEL_MARKERS = (
    "案件细节",
    "案件详情",
    "客户问题",
    "客户咨询问题",
    "客户争议事项",
    "纠纷类型",
    "纠纷性质",
    "纠纷事项",
    "纠纷主体",
    "纠纷行为",
    "纠纷具体细节",
    "纠纷细节",
    "纠纷具体事实",
    "纠纷具体主张",
    "纠纷涉及的当事人",
    "纠纷涉及的具体行为",
    "争议双方",
    "争议行为",
    "争议具体事项",
    "争议行政行为",
    "争议点",
    "争议焦点",
    "纠纷后果",
    "争议主体",
    "未解决",
    "法律影响",
    "法律后果",
    "法律依据",
    "法律规定",
    "法律条款",
    "法律法规",
    "法律条文",
    "责任归属",
    "责任范围",
    "责任性质",
    "合法性",
    "合规性",
    "有效性",
    "法律效力",
    "证明力",
    "因果关系",
    "主体资格",
    "裁判逻辑",
    "法律认定",
    "法律标准",
    "实质性相似",
    "所需材料",
    "材料清单",
    "需要准备",
    "如何分割",
    "怎么分割",
    "侵权行为",
    "违法行为",
    "违约行为",
    "不正当竞争行为",
    "法律救济",
    "法律措施",
    "主观意图",
    "主观认识",
    "主观故意",
    "认知程度",
    "了解程度",
    "构成犯罪",
    "构成违法",
    "违法所得",
    "非法获利",
    "具体证据",
    "可证明",
    "合规认证",
    "合法注册",
    "侵权",
    "假冒",
    "竞业行为",
    "可执行性",
    "可预期性",
    "法律或现实限制",
    "法律限制",
    "现实限制",
    "法律保护措施",
    "法律结果",
    "法律问题",
    "执行限制",
    "诈骗资金",
    "诈骗过程",
    "诈骗行为",
    "判决依据",
    "量刑依据",
    "法律或现实后果",
    "法律约束力",
    "法律保障",
    "规避竞业限制",
    "规避监管",
    "程序性后果",
    "该事实",
    "这一事实",
    "该信息",
    "这一信息",
    "相关信息",
    "详细信息",
    "单一事实",
    "特定事实",
)


def has_excessive_phrase_repetition(value: str) -> bool:
    """Detect structured-decoding loops in any policy text field."""

    enumerated_items = [
        item.strip(" ：:。！？!?（）()[]【】\"'") for item in re.split(r"[、，,；;/|]", value)
    ]
    repeated_items = {
        item for item in enumerated_items if len(item) >= 2 and enumerated_items.count(item) >= 3
    }
    # An unrestricted back-reference misclassifies ordinary nested noun phrases
    # such as ``刑事责任和责任分配`` or ``合同和合同附件``.  Coordination loops in
    # malformed policy generations repeat the predicate itself (``知道或知道``),
    # whereas repeated comma-separated list items are already handled above.
    loop_predicates = (
        "知道",
        "了解",
        "确认",
        "核实",
        "询问",
        "说明",
        "提供",
        "提交",
        "告知",
        "回答",
        "描述",
        "列明",
        "判断",
        "评估",
        "查明",
        "查询",
        "取得",
        "收到",
        "发送",
        "签署",
        "支付",
    )
    repeated_coordination = any(
        re.search(rf"{predicate}(?:或|和|及|以及|、){predicate}", value)
        for predicate in loop_predicates
    )
    return bool(repeated_items or repeated_coordination)


def has_coordinated_distinct_misconduct(value: str) -> bool:
    """Detect two independently answerable misconduct allegations in one target."""

    evidence_fabrication = r"(?:伪造|变造|篡改|编造).{0,6}(?:证据|材料|文件|记录)"
    false_representation = r"(?:虚假|不实|隐瞒).{0,6}(?:陈述|说明|申报|表示|表述)"
    connector = r"(?:或|或者|和|及|以及|、)"
    return bool(
        re.search(
            rf"(?:{evidence_fabrication}).{{0,8}}{connector}.{{0,8}}(?:{false_representation})",
            value,
        )
        or re.search(
            rf"(?:{false_representation}).{{0,8}}{connector}.{{0,8}}(?:{evidence_fabrication})",
            value,
        )
    )


def specific_numeric_anchors(value: str) -> set[str]:
    """Return precise values that may not be invented in a client question."""

    patterns = (
        r"(?:19|20)\d{2}年(?:\d{1,2}月(?:\d{1,2}日)?)?",
        r"\d+(?:\.\d+)?(?:万元|元|%|％)",
        r"\d+(?:个)?(?:工作)?(?:日|天|月|年)(?:内|前|后|以上|以下|届满)",
    )
    return {match for pattern in patterns for match in re.findall(pattern, value)}


def factual_target_question_safety_violations(fact_id: str, label: str) -> list[str]:
    """Explain why a fact slot cannot safely become a client question."""

    if any(
        marker in label
        for marker in (
            "身份证号码",
            "身份证号",
            "身份证明号码",
            "身份证明信息",
            "银行账户号码",
            "银行账户信息",
            "银行卡号码",
            "银行卡号",
        )
    ):
        return ["sensitive_personal_identifier"]
    if re.search(r"(?:具体)?身份信息$", label):
        return ["generic_or_sensitive_identity_request"]
    generic_scan = re.sub(r"[（(][^）)]*[）)]", "", label)
    if has_coordinated_distinct_misconduct(generic_scan):
        return ["multiple_primary_questions"]
    if re.search(
        r"(?:其他|任何).{0,24}(?:案件|纠纷|交易|行为|活动|处罚记录|关系|关联)$",
        generic_scan,
    ):
        return ["generic_mechanical_expansion"]
    # A bare instrument noun does not tell the policy whether to ask about its
    # existence, execution, text, date, parties, or another observable attribute.
    # Leaving that choice implicit lets a semantic-looking fact_id turn the noun
    # into a legal conclusion (for example ``agreement_legality`` becoming
    # “协议是否有效”).  Reject only the bare noun form; labels that name an
    # observable act, document feature, or record category remain valid.
    if re.search(r"(?:协议|合同|文书|材料|记录|凭证)$", generic_scan) and not re.search(
        r"(?:是否|有无|存在|签署|签订|提交|收到|取得|持有|留存|出具|提供|"
        r"约定|条款|内容|文本|编号|日期|时间|金额|主体|签字|盖章|记载|载明|"
        r"写明|具体|类型|名称|原始|书面|口头|诊断|治疗|申请|调查|检查|维护|"
        r"使用|沟通|支付|交接|证明|报告|流水|转账|决策)",
        generic_scan,
    ):
        return ["generic_instrument_without_observable_attribute"]
    # A relation between an incident and work is actor-dependent.  If the label
    # omits whose work/activity is at issue, the surface policy commonly defaults
    # to “您的工作” even when the opening describes a third-party actor.  Require
    # an explicit or neutral actor in the visible target instead of guessing one.
    if re.search(
        r"(?:事故|事件|行为).{0,16}(?:与|和).{0,12}"
        r"(?:工作|职务|任务).{0,8}(?:关联|关系|联系)",
        generic_scan,
    ) and not re.search(
        r"(?:您|本人|客户|当事人|行为人|相关人员|员工|驾驶人|骑行人|"
        r"受害人|肇事者|对方|第三方|宗某|某某)",
        generic_scan,
    ):
        return ["ambiguous_actor_reference"]
    if re.search(
        r"(?:是否|有无).{0,16}(?:签署|签订|收到|提交|取得|持有|发生|参与|购买)"
        r".{0,20}(?:及|和|以及).{0,12}(?:内容|条款|时间|金额|方式|原因|范围)",
        generic_scan,
    ):
        return ["multiple_primary_questions"]
    if re.search(
        r"(?:对方|银行|平台|用人单位|行政机关|监管机关|公安机关|法院)"
        r".{0,20}(?:内部)?(?:评估|分析|决策|审核|审查|研判)"
        r".{0,16}(?:依据|过程|方法|内容|标准|流程)",
        label,
    ) and not re.search(
        r"(?:通知|文书|文件|函件|邮件|短信|合同|协议).{0,12}"
        r"(?:载明|写明|注明|内容|原文)",
        label,
    ):
        return ["unobservable_third_party_internal_process"]
    # A legal-characterization word can also be part of the ordinary name of a
    # communication artifact.  Asking whether a party sent, received, or acted on
    # an ``侵权通知/告知/投诉`` is an observable event; it does not ask the
    # client to decide whether infringement legally occurred.  Strip only that
    # bounded noun phrase before the abstract-marker scan.  Product descriptions,
    # merits questions, and internal ``侵权检测`` processes remain rejected.
    abstract_scan = re.sub(
        r"侵权(?:通知|告知|投诉|函件|律师函)",
        "权利通知",
        label,
    )
    abstract_marker = next(
        (item for item in ABSTRACT_FACT_LABEL_MARKERS if item in abstract_scan), None
    )
    if abstract_marker:
        return [f"abstract_marker:{abstract_marker}"]
    abstract_suffix = next(
        (
            item
            for item in ("类型", "性质", "效力", "合法性", "合规性", "证明力")
            if label.endswith(item)
        ),
        None,
    )
    concrete_evidence_type = bool(
        abstract_suffix == "类型" and re.search(r"(?:文件|材料|文书|记录|凭证|证据)类型$", label)
    )
    if abstract_suffix and not concrete_evidence_type:
        return [f"abstract_suffix:{abstract_suffix}"]
    # Literal-prefix projection must not turn an unsafe legal proposition into a
    # grammatically dangling client target (for example, projecting
    # ``执法机关认定公司和个人构成犯罪的法律依据`` to
    # ``执法机关认定公司``).  Rejecting the fragment causes the
    # planner to repair it; it does not invent a replacement fact.
    dangling_predicate_object = re.search(
        r"(?:认定|认为|证明|要求|通知|告知|指示|安排|允许|拒绝|同意|承诺|确认)(?:了)?"
        r"(?:该|涉案|本案)?(?:公司|个人|客户|对方|当事人|第三方|员工|人员)$",
        label,
    )
    if dangling_predicate_object:
        return ["dangling_predicate_object"]
    legal_judgment_patterns = (
        r"是否(?:合法|合规|有效|符合|遵守)",
        r"是否.{0,6}(?:仍然|仍|还)?(?:真实)?有效",
        r"(?:是否|有无).{0,16}(?:充分|足够).{0,6}(?:证据|材料)",
        r"(?:证据|材料).{0,12}是否.{0,8}(?:充分|足够)",
        r"是否履行.{0,12}(?:程序|义务|职责|要求)",
        r"是否.{0,16}履行.{0,12}(?:程序|义务|职责|要求)",
        r"(?:知晓|知道|认识到).{0,24}(?:违法|犯罪|诈骗|违约|非法|违法所得|可能涉)",
        r"(?:证据|记录).{0,12}(?:相关性|可靠性|证明力|充分性|合法性|法律后果)",
        r"是否具备.{0,12}(?:资质|认证|许可)",
        r"(?:是否|有无).{0,12}(?:持有|具备|取得).{0,8}"
        r"(?:合法|合规|法定).{0,8}(?:资质|资格|许可|证明)",
        r"(?:是否|有无).{0,12}(?:具有|持有|提供).{0,8}"
        r"(?:合法|合规|法定).{0,8}(?:声明|文件|材料|证明)",
        r"是否真实有效",
        r"刑事罚金.{0,16}民事责任.{0,8}影响",
        r"刑事罚金.{0,16}民事.{0,6}责任.{0,8}影响",
        r"^(?:相关|现有|充分|足够|有效|具体)?证据$",
        r"是否.{0,16}(?:足以|能够).{0,16}(?:覆盖|保障|实现)",
        r"(?:是否|结果).{0,16}(?:可执行|可变现|可启动|可预期|可实现|可完成)",
        r"是否会产生.{0,16}(?:成本|风险)",
        r"优先顺位.{0,16}(?:可执行|是否明确)",
        r"(?:是否|已).{0,12}依法生效",
        r"(?:是否存在|实际存在).{0,12}(?:劳动关系|雇佣关系|劳务关系)",
        r"^(?!.*(?:实际|已经|已|当前|具体发生|采取)).{0,24}"
        r"(?:办理|处理|处置|执行|申请|诉讼|复议|仲裁)程序$",
        r"^(?!.*(?:实际|已经|已|当前|具体发生|采取)).{0,24}"
        r"(?:办理|处理|处置|执行|申请|诉讼|复议|仲裁)流程$",
        r"预计.{0,16}(?:时间|结果|成本|风险)",
        r"是否能.{0,16}实现.{0,12}(?:目标|结果|救济)",
        r"证明.{0,16}符合.{0,12}(?:规划|法律|法规|规范|标准|要求)",
        r"是否存在.{0,12}证据.{0,8}证明",
        r"(?:是否|有无).{0,24}(?:遵守|符合).{0,12}(?:法律|法规|规范|标准)",
        r"是否.{0,16}按照.{0,8}(?:规定|法定|规范|标准).{0,12}(?:程序|要求|方法)",
        r"(?:是否|有无).{0,16}(?:知晓|知道|认识).{0,16}(?:后果|风险)",
        r"(?:是否|有无).{0,8}(?:知悉|知晓|知道|了解)(?!.*(?:通知|告知|送达)(?:内容|时间))",
        r"(?:是否|有无).{0,8}(?:察觉|意识到|认识到)",
        r"(?:知晓|知道|了解).{0,20}(?:可能|会).{0,20}(?:导致|造成|产生)",
        r"(?:共同犯罪|诈骗计划|虚构劳动关系)(?!.*(?:判决|裁定|起诉|指控|通知|文书))",
        r"(?:是否)?可验证$",
        r"计划采取的.{0,12}(?:补救|救济|法律|程序)(?:措施|步骤)",
        r"(?:合同|协议|决定|文书).{0,12}(?:是否|有无).{0,6}(?:已经|已)?生效",
        r"(?:补偿|赔偿|损失|优惠|承诺).{0,16}(?:计算)?依据(?:是什么)?$",
        r"(?:合理)?(?:补偿|赔偿).{0,12}(?:计算)?标准$",
        r"是否.{0,16}(?:履行|落实).{0,8}的依据",
        r"(?:未|没有|尚未|从未).{0,12}(?:答复|回复|回应|决定|通知)"
        r".{0,10}所依据",
        r"(?:流程|程序).{0,8}(?:和|及|与).{0,8}(?:要求|条件)$",
        r"(?:执法|监管|行政|公安|法院).{0,16}发现.{0,6}违法",
        r"何时(?:能够|可以|会).{0,16}(?:兑现|实现|完成|取得|获得)",
        r"(?:监护人|代理人).{0,12}(?:权限|法律地位|资格)",
        r"(?:材料|文件|申请).{0,12}是否(?:完整|有效|真实)(?:[、，,及和或].{0,6})?",
        r".{1,20}(?:与|和).{1,20}是否(?:一致|相同|匹配|对应)",
        r"(?:来源|身份|内容).{0,8}确认$",
        r"(?:法律|法规|规章|办法|规范性文件).{0,16}是否.{0,12}"
        r"(?:废止|修订|失效|有效)",
        r"(?:离婚|起诉|仲裁|复议|执行|登记|申请|报案|维权)?.{0,8}"
        r"所需.{0,8}(?:准备)?(?:文件|材料|手续)",
        r"(?:可能|预计|预期|将会).{0,24}(?:产生|导致|造成|带来|对)?.{0,20}"
        r"(?:影响|变化|后果|结果)$",
        r"(?:行为|安排|事件).{0,16}对.{0,16}(?:财产|权利|责任).{0,8}"
        r"(?:实际)?影响$",
        r"(?:协议|合同|约定|条款|决定|文书).{0,12}"
        r"是否(?:仍然|仍|还)?(?:真实)?有效(?:[？?。]|$)",
        r"(?:是否|有无).{0,16}依法依规",
        r"(?:是否|有无).{0,16}法定授权依据",
        r"(?:证据|材料).{0,20}(?:是否)?(?:覆盖|涵盖).{0,20}"
        r"(?:全部|所有|完整|关键)(?:事项|事实|问题|要点|点)",
        r"(?:证据|材料).{0,20}(?:是否)?(?:覆盖|涵盖).{0,12}"
        r"(?:质疑|争议|待证)(?:事项|事实|问题|要点|点)?",
        r"(?:是否|有无|存在).{0,12}挂靠关系",
        r"(?:认为|判断|可能|是否).{0,24}(?:涉及|承担|构成)?.{0,8}"
        r"(?:哪些|何种|什么)?法律责任",
        r"(?:是否存在|有无).{0,12}(?:第三方|证人).{0,8}"
        r"(?:能|可以)证明.{0,8}(?:真实|真实性)",
    )
    if any(re.search(pattern, label) for pattern in legal_judgment_patterns):
        return ["legal_or_evidentiary_judgment"]
    # A small instruction model sometimes serializes an otherwise atomic factual
    # target as the exact client-facing question (for example, “您实际工作的单位名称
    # 是什么？”).  Wrapping that question in the generic probe below creates two
    # question marks and falsely reports multiple_primary_questions.  Validate an
    # already interrogative label directly; all legal, sensitive and evidentiary
    # exclusions above still apply.
    question_label = re.sub(
        r"[（(](?:(?:如|例如|比如)[^）)]*|[^）)]*(?:/|、)[^）)]*)[）)]",
        "",
        label,
    )
    question_label = re.split(
        r"(?<=[？?。；;，,])\s*(?:例如|比如|举例(?:来说)?|譬如)[，,:：]?",
        question_label,
        maxsplit=1,
    )[0]
    stripped_label = question_label.strip()
    if stripped_label.endswith(("？", "?")) or re.search(
        r"(?:是否|有无|为什么|为何|哪里|哪些|什么|如何|怎么|多少|何时|"
        r"什么时候|哪(?:个|些|一|位|家|项|种|段|天|年|月|日|里|边|方|"
        r"份|套|类|条|次|时候)?)",
        stripped_label,
    ):
        direct_probe = StructuredAction(
            action_type="ask",
            target_type="fact",
            target_id=fact_id,
            content=stripped_label,
        )
        direct_violations = action_question_quality_violations(direct_probe)
        if not direct_violations:
            return []
        return direct_violations
    probe = StructuredAction(
        action_type="ask",
        target_type="fact",
        target_id=fact_id,
        content=f"关于{stripped_label}，请说明您亲历或现有文件能够确认的具体事实？",
    )
    return action_question_quality_violations(probe)


def factual_target_is_question_safe(fact_id: str, label: str) -> bool:
    """Whether a fact slot can be turned into a factual client question safely."""

    return not factual_target_question_safety_violations(fact_id, label)


def atomic_factual_target_projection(fact_id: str, label: str) -> str | None:
    """Retain a model-proposed atomic factual core when its tail is unsafe.

    Every candidate is a literal prefix of the model's label and must independently
    pass the same question-safety contract.  This does not translate the label,
    inspect a case ID, or import evaluator-only facts.
    """

    value = label.strip().rstrip("。；;")
    if not value:
        return None
    if factual_target_is_question_safe(fact_id, value):
        return value
    if has_coordinated_distinct_misconduct(value):
        return None

    # Planner drafts often serialize one observable event together with several
    # attributes even though the online policy consumes one target at a time.  A
    # failed repair used to delete the whole event, shrinking otherwise useful
    # agendas (for example, an auto-charge's time/amount/receipt) to a single
    # unrelated target.  Preserve only a literal, grammatically complete prefix;
    # it still has to pass the full ordinary safety contract below.
    prefix_candidates: list[str] = []
    content_predicate = re.search(
        r"^(.{4,80}内容)是否(?:包含|载明|写明|注明|记载)", value
    )
    if content_predicate:
        prefix_candidates.append(content_predicate.group(1))
    for match in re.finditer(rf"[，,]|{ATTRIBUTE_COORDINATION_PATTERN}", value):
        prefix = value[: match.start()].strip(" ，,；;：:")
        if re.search(r"(?:包括|例如|比如|具体包括)", prefix):
            continue
        if re.search(
            r"(?:时间|日期|金额|数额|名称|编号|时间范围|地理范围|范围|地点|"
            r"位置|频率|持续时间)$",
            prefix,
        ):
            prefix_candidates.append(prefix)
        if re.search(
            r"^(?:是否|有无).{0,60}(?:收到|签署|签订|发生|参与|购买|提交|"
            r"取得|持有|作出|进行过).{0,30}(?:通知|提醒|协议|合同|文件|"
            r"文书|决定|答复|回复|申请|付款|扣费|交易|协商)$",
            prefix,
        ):
            prefix_candidates.append(prefix)
    for candidate in prefix_candidates:
        if len(candidate) >= 4 and factual_target_is_question_safe(fact_id, candidate):
            return candidate
    split_patterns = (
        r"[，,；;]\s*(?:包括|例如|比如|具体包括)",
        r"(?:是否|有无)(?:符合|遵循|履行|满足|达到)(?:法律|法规|法定|规范|标准|要求)",
    )
    for pattern in split_patterns:
        candidate = re.split(pattern, value, maxsplit=1)[0].strip(" ，,；;：:")
        if len(candidate) >= 4 and factual_target_is_question_safe(fact_id, candidate):
            return candidate
    # Other conjunction prefixes are intentionally not projected.  A prefix can
    # be a grammatical fragment or can launder an unsafe legal judgment; only the
    # bounded complete forms above are eligible.
    return None


def parse_policy_envelope(text: str) -> tuple[PolicyEnvelope, str]:
    raw = text.strip()
    # Qwen occasionally emits a schema-complete action but omits only the outermost
    # closing brace despite reporting ``stop``.  Close exactly that transport defect
    # when strings/arrays are balanced and precisely one object remains open.  This
    # neither invents a field nor chooses an action; all ordinary Pydantic and health
    # checks still run on the recovered object, and the audit mode remains explicit.
    object_depth = 0
    array_depth = 0
    in_string = False
    escaped = False
    structurally_possible = True
    for char in raw:
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            object_depth += 1
        elif char == "}":
            object_depth -= 1
            structurally_possible = structurally_possible and object_depth >= 0
        elif char == "[":
            array_depth += 1
        elif char == "]":
            array_depth -= 1
            structurally_possible = structurally_possible and array_depth >= 0
    closure_candidate = (
        raw + "}"
        if structurally_possible
        and not in_string
        and object_depth == 1
        and array_depth == 0
        and raw.startswith("{")
        and raw.endswith("}")
        else None
    )
    candidates: list[tuple[str, str]] = [(raw, "json")]
    if closure_candidate is not None:
        candidates.append((closure_candidate, "json_missing_outer_closure"))
    candidates.extend((item, "json_fragment") for item in _balanced_json_objects(raw))
    for candidate, parse_mode in candidates:
        try:
            value = json.loads(candidate)
            # The current runtime contract makes the policy choose an action only.
            # Keep accepting historical full envelopes for artifact compatibility;
            # a missing patch means exactly an empty incremental patch.
            if isinstance(value, dict) and "action" in value and "state_patch" not in value:
                value["state_patch"] = {}
            # The prompt permits an empty terminal body.  Local instruction models
            # commonly serialize that as JSON null instead of "".  Normalize only
            # this explicitly equivalent terminal representation; malformed factual
            # actions remain schema failures and still fail closed.
            action = value.get("action") if isinstance(value, dict) else None
            if isinstance(action, dict) and action.get("action_type") in {
                "final",
                "abstain",
            }:
                if action.get("content") is None:
                    action["content"] = ""
                # Local instruction models sometimes serialize JSON null as the
                # literal string "null" and carry over the prior factual target
                # type on a terminal action.  These fields have no terminal
                # semantics, so canonicalize only null-like identifiers and the
                # target type; a real non-null target remains visible to the health
                # contract and is rejected rather than silently discarded.
                target_id = action.get("target_id")
                if target_id is None or (
                    isinstance(target_id, str)
                    and target_id.strip().lower() in {"", "null", "none", "nil"}
                ):
                    action["target_id"] = None
                    action["target_type"] = "session"
            return PolicyEnvelope.model_validate(value), parse_mode
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


def normalize_policy_envelope(
    envelope: PolicyEnvelope, state: ConsultationState
) -> tuple[PolicyEnvelope, list[str]]:
    """Normalize auditable interface noise without choosing consultation strategy.

    The local policy sometimes copies unchanged visible slots into an incremental patch
    or proposes a safe factual action with a new target id but omits the corresponding
    unknown slot.  Both are representation defects.  This bridge uses only the model's
    own action and visible state; it never imports a benchmark fact or selects a topic.
    """

    normalized = envelope.model_copy(deep=True)
    changes: list[str] = []
    current = {fact.fact_id: fact for fact in state.facts}
    kept: list[FactObservation] = []
    for observation in normalized.state_patch.observations:
        prior = current.get(observation.fact_id)
        unchanged = bool(
            prior
            and observation.status == prior.status
            and observation.value == prior.value
            and not observation.evidence_labels
        )
        if unchanged:
            changes.append(f"drop_unchanged_observation:{observation.fact_id}")
        else:
            kept.append(observation)
    normalized.state_patch.observations = kept

    action = normalized.action
    if action.action_type in {"final", "abstain"} and (
        action.target_id is not None or action.target_type not in {"session", "none"}
    ):
        # Terminal strategy is already explicit in action_type.  Qwen sometimes
        # copies the active issue join key into a terminal action even though no
        # downstream target exists.  Canonicalize only that transport metadata;
        # do not change whether or why the model chose to terminate.
        changes.append("normalize_terminal_target_to_session")
        normalized.action = action.model_copy(update={"target_id": None, "target_type": "session"})
        action = normalized.action
    # Small instruction models often append an illustrative “例如……” sentence to
    # an otherwise atomic question.  The example adds no requested attribute and can
    # bias the simulated client toward facts the lawyer supplied.  Remove only a
    # clearly delimited illustrative suffix, retain the model's original target and
    # first question verbatim, and accept the projection only if the ordinary quality
    # contract then passes.  This is interface normalization, not target selection.
    if action.action_type in {"ask", "clarify", "verify", "summarize"}:
        illustrative = re.split(
            r"(?<=[？?。；;，,])\s*(?:例如|比如|包括|举例(?:来说)?|譬如)[，,:：]?",
            action.content.strip(),
            maxsplit=1,
        )
        if len(illustrative) == 1:
            illustrative = re.split(
                r"(?<=[？?])\s*具体(?:包括|例如|可以包括).*$",
                action.content.strip(),
                maxsplit=1,
            )
        if len(illustrative) == 2:
            projected_content = illustrative[0].strip().rstrip(" ，,；;。")
            projected = action.model_copy(update={"content": projected_content})
            if projected_content and not action_question_quality_violations(projected):
                changes.append("drop_illustrative_question_suffix")
                normalized.action = projected
                action = normalized.action
        # Surface-question failures remain policy failures.  The health gate below
        # returns their exact violations to the same frozen lawyer for a bounded
        # rewrite on the same target.  Do not synthesize a label-shaped generic
        # question here: that would make deterministic infrastructure, rather than
        # the sampled policy, author the behaviour being compared and can erase
        # relational meaning such as payer/recipient direction.
        #
        # There is one narrower representation case: the frozen planner may expose
        # two explicitly named attributes in one visible target while the policy
        # asks both in a compound surface question.  The target choice is already
        # fixed (and is shared by every comparison arm), so projecting that failed
        # surface to one *model-named* atomic unit does not choose a new topic.  It
        # merely realizes the single-question interface promised to the client.
        # Apply this only when the sampled surface actually fails for multiplicity,
        # only to a current visible target, and only when the chosen unit is visibly
        # aligned with the model's own content/expected-information.  All ordinary
        # question and target-alignment checks still run on the result.
        current_target = current.get(action.target_id or "")
        surface_violations = action_question_quality_violations(action)
        if current_target is not None and "multiple_primary_questions" in surface_violations:
            atomic_units = visible_target_atomic_units(current_target.label)
            model_surface = f"{action.content}\n{action.expected_information}"
            aligned_units = [
                unit
                for unit in atomic_units
                if factual_target_is_question_safe(current_target.fact_id, unit)
                and _alignment_unit_matches(unit, model_surface)
            ]
            if len(atomic_units) > 1 and aligned_units:
                # Preserve the sampled policy's emphasis: when it mentioned more
                # than one visible unit, use the one appearing first in its surface
                # rather than a configured/domain-specific priority.
                def _surface_position(unit: str) -> tuple[int, int]:
                    compact_surface = _alignment_text(model_surface)
                    compact_unit = _alignment_text(unit)
                    positions = [
                        compact_surface.find(value)
                        for value in (compact_unit, *_alignment_bigrams(compact_unit))
                        if compact_surface.find(value) >= 0
                    ]
                    position = min(positions) if positions else len(compact_surface)
                    return position, atomic_units.index(unit)

                selected_unit = min(aligned_units, key=_surface_position)
                rendered = safe_factual_question_surface(
                    current_target.fact_id,
                    selected_unit,
                    target_kind=current_target.target_kind,
                )
                if rendered is not None:
                    surface_label, content = rendered
                    projected = action.model_copy(
                        update={
                            "expected_information": surface_label,
                            "content": content,
                        }
                    )
                    if (
                        not action_question_quality_violations(projected)
                        and not action_target_alignment_violations(
                            projected, current_target.label
                        )
                    ):
                        changes.append(
                            "project_compound_surface_to_visible_atomic_unit:"
                            f"{current_target.fact_id}:{selected_unit}"
                        )
                        normalized.action = projected
                        action = normalized.action
    # Runtime-created targets use a label-derived canonical ID.  The policy still
    # chooses the missing factual dimension and its visible label; a misleading
    # English join key can no longer contradict the actual question or contaminate
    # teacher traces (for example, an ID about finances attached to arbitration).
    target_observation = next(
        (item for item in kept if item.fact_id == action.target_id and item.fact_id not in current),
        None,
    )
    if target_observation is not None:
        prior_target_id = target_observation.fact_id
        canonical_target_id = _canonical_runtime_fact_id(target_observation.label)
        if canonical_target_id != prior_target_id:
            normalized.action = action.model_copy(update={"target_id": canonical_target_id})
            action = normalized.action
            changes.append(f"canonicalize_runtime_target:{prior_target_id}->{canonical_target_id}")
            if canonical_target_id in current:
                kept.remove(target_observation)
                changes.append(f"drop_runtime_target_alias:{prior_target_id}")
            else:
                target_observation.fact_id = canonical_target_id
    patch_ids = {item.fact_id for item in kept}
    if (
        action.action_type in {"ask", "clarify", "verify"}
        and action.target_type == "fact"
        and action.target_id
        and action.target_id not in current
        and action.target_id not in patch_ids
        and re.fullmatch(r"[a-z][a-z0-9_]{1,63}", action.target_id)
        and not action_question_quality_violations(action)
    ):
        label = _question_target_label(action.content, action.expected_information)
        prior_target_id = action.target_id
        # If the sampled question already aligns with exactly one still-open,
        # never-asked visible target, a new English join key is representation
        # noise rather than a new consultation strategy. Bind the action to that
        # target before the client answers so ordinary state transition closes
        # the slot actually asked; do not perform post-hoc semantic auto-closing.
        aligned_open_targets = [
            fact
            for fact in state.facts
            if fact.status in {"unknown", "disputed"}
            and fact.fact_id not in state.asked_targets
            and fact.fact_id not in NON_SUBSTANTIVE_FACT_IDS
            and not action_target_alignment_violations(action, fact.label)
        ]
        if len(aligned_open_targets) == 1:
            visible_target_id = aligned_open_targets[0].fact_id
            normalized.action = action.model_copy(update={"target_id": visible_target_id})
            action = normalized.action
            changes.append(
                f"reuse_visible_aligned_target:{prior_target_id}->{visible_target_id}"
            )
        else:
            canonical_target_id = _canonical_runtime_fact_id(label)
            normalized.action = action.model_copy(update={"target_id": canonical_target_id})
            action = normalized.action
            if canonical_target_id not in current:
                kept.append(
                    FactObservation(
                        fact_id=canonical_target_id,
                        label=label,
                        status="unknown",
                        value=None,
                        evidence_labels=[],
                        confidence=0.0,
                        criticality="medium",
                        # This deterministic recovery is only created for a direct
                        # question addressed to the client.  Persist the provenance
                        # explicitly; omission must never imply ``client_fact``.
                        target_kind="client_fact",
                    )
                )
            changes.append(
                f"canonicalize_runtime_target:{prior_target_id}->{canonical_target_id}"
            )
            if canonical_target_id in current:
                changes.append(f"reuse_canonical_runtime_target:{canonical_target_id}")
            else:
                changes.append(f"create_missing_action_target:{canonical_target_id}")
    return normalized, changes


def exhausted_visible_target_surface_projection(
    envelope: PolicyEnvelope,
    state: ConsultationState,
) -> tuple[PolicyEnvelope, str] | None:
    """Realize one already-chosen visible target after bounded surface repairs fail.

    This is deliberately narrower than an action fallback.  It cannot select a
    target, reopen an asked target, inspect hidden case facts, or repair semantic
    misalignment.  It applies only when the frozen policy has exhausted its edits
    and the *only* remaining blocking defect is a compound question surface for an
    otherwise aligned, currently visible fact target.  The ordinary policy health
    contract is rerun on the projected envelope before it can execute.
    """

    blocking = blocking_policy_health_violations(policy_health_violations(envelope, state))
    if blocking != ["multiple_primary_questions"]:
        return None
    action = envelope.action
    if (
        action.action_type not in {"ask", "clarify", "verify", "summarize"}
        or action.target_type != "fact"
        or not action.target_id
    ):
        return None
    target = next((item for item in state.facts if item.fact_id == action.target_id), None)
    if (
        target is None
        or target.status not in {"unknown", "disputed"}
        or target.fact_id in state.asked_targets
        or action_target_alignment_violations(action, target.label)
    ):
        return None
    rendered = safe_factual_question_surface(
        target.fact_id,
        target.label,
        target_kind=target.target_kind,
    )
    if rendered is None:
        return None
    surface_label, content = rendered
    projected = envelope.model_copy(deep=True)
    projected.action = action.model_copy(
        update={
            "expected_information": surface_label,
            "content": content,
        }
    )
    if blocking_policy_health_violations(policy_health_violations(projected, state)):
        return None
    return (
        projected,
        "project_exhausted_compound_surface_to_visible_target:"
        f"{target.fact_id}:{surface_label}",
    )


def _canonical_runtime_fact_id(label: str) -> str:
    return f"dialogue_fact_{hashlib.sha256(label.encode('utf-8')).hexdigest()[:16]}"


def _question_target_label(question: str, expected_information: str) -> str:
    """Give a missing action target one single-attribute, human-readable label."""

    categories = (
        (
            ("何时", "什么时候", "时间", "日期", "哪天", "哪一天", "哪年", "哪月"),
            "问题所指的具体时间",
        ),
        (("金额", "数额", "价格", "费用", "份额", "比例"), "问题所指的金额或份额"),
        (("文件", "文书", "合同", "协议", "通知", "判决", "裁定"), "问题所指文件的具体内容"),
        (("谁", "姓名", "身份", "主体"), "问题所指人员的身份"),
        (("哪里", "何地", "地点", "地址"), "问题所指的具体地点"),
        (("做了什么", "如何处理", "经过", "行为"), "问题所指的具体行为"),
    )
    for markers, label in categories:
        if any(marker in question for marker in markers):
            return label
    concise = re.sub(r"[，,；;。？！?]+", "", expected_information.strip())
    if concise and len(concise) <= 30 and not re.search(r"(?:以及|包括|分别|、|和)", concise):
        return concise
    return "本轮问题所指的单一事实"


def policy_health_violations(envelope: PolicyEnvelope, state: ConsultationState) -> list[str]:
    """Return semantic contract failures that justify a local-model repair attempt."""

    violations: list[str] = []
    observations = {item.fact_id: item for item in envelope.state_patch.observations}
    current = {item.fact_id: item for item in state.facts}
    forbidden = sorted(set(observations) & NON_SUBSTANTIVE_FACT_IDS)
    if forbidden:
        violations.append(f"forbidden_management_facts:{','.join(forbidden)}")
    unsafe_new_targets = {
        fact_id: factual_target_question_safety_violations(fact_id, item.label)
        for fact_id, item in observations.items()
        if fact_id not in current and factual_target_question_safety_violations(fact_id, item.label)
    }
    for fact_id, reasons in sorted(unsafe_new_targets.items()):
        violations.append(f"unsafe_new_fact_target:{fact_id}:{'|'.join(reasons)}")

    unchanged = [
        fact_id
        for fact_id, item in observations.items()
        if fact_id in current
        and item.status == current[fact_id].status
        and item.value == current[fact_id].value
    ]
    if unchanged:
        violations.append(f"warning:state_patch_repeats_unchanged:{','.join(sorted(unchanged))}")
    unsupported_corroboration = sorted(
        item.fact_id
        for item in observations.values()
        if item.status == "corroborated"
        and not any(is_concrete_evidence_label(label) for label in item.evidence_labels)
    )
    if unsupported_corroboration:
        violations.append(
            "corroborated_without_concrete_evidence:" + ",".join(unsupported_corroboration)
        )
    status_regressions = sorted(
        item.fact_id
        for item in observations.values()
        if item.fact_id in current
        and (
            (item.status == "unknown" and current[item.fact_id].status != "unknown")
            or (current[item.fact_id].status == "not_available" and item.status != "not_available")
        )
    )
    if status_regressions:
        violations.append("state_status_regression:" + ",".join(status_regressions))

    action = envelope.action
    if action.reason == "invalid_structured_output":
        violations.append("invalid_structured_output")
    for field_name, field_value in (
        ("reason", action.reason),
        ("expected_information", action.expected_information),
    ):
        if has_excessive_phrase_repetition(field_value):
            violations.append(f"action_metadata_excessive_phrase_repetition:{field_name}")
    visible_text = "\n".join(
        str(fact.value or "")
        for fact in state.facts
        if fact.status in {"client_claimed", "corroborated", "disputed"}
    )
    supplied_action_text = "\n".join((action.content, action.expected_information, action.reason))
    for anchor in sorted(specific_numeric_anchors(supplied_action_text)):
        if anchor not in visible_text:
            violations.append(f"unseen_specific_numeric_anchor:{anchor}")
    target = action.target_id
    provisional = dict(current)
    for fact_id, observation in observations.items():
        if fact_id not in current or not (
            observation.status == "unknown" and current[fact_id].status != "unknown"
        ):
            provisional[fact_id] = observation
    actionable_unresolved = {
        fact_id
        for fact_id, fact in provisional.items()
        if fact.status in {"unknown", "disputed"}
        and fact_id not in state.asked_targets
        and fact_id not in NON_SUBSTANTIVE_FACT_IDS
    }
    substantive = {
        fact_id
        for fact_id, fact in provisional.items()
        if fact.status in {"client_claimed", "corroborated", "disputed"}
        and fact_id not in NON_SUBSTANTIVE_FACT_IDS
    }
    if action.action_type == "abstain":
        if actionable_unresolved:
            violations.append("premature_abstention_with_grounded_target")
        elif not substantive and not state.interactions:
            violations.append("premature_abstention_without_substantive_investigation")
        elif substantive:
            violations.append("abstention_when_conditional_memo_available")
    if action.action_type == "final" and actionable_unresolved:
        terminal_reason = action.reason.strip()
        blanket_low_value = bool(
            re.search(
                r"(?:剩余|其余|其他).{0,12}(?:目标|事实|信息).{0,28}"
                r"(?:低价值|价值较低|缺乏.{0,6}价值|大概率无法|可能无法|"
                r"不会实质改变|影响有限)",
                terminal_reason,
            )
        )
        admits_material_gap = bool(
            re.search(
                # Detect an explicit admission that another consultation turn still
                # has positive value.  This is intentionally checked only while the
                # online state contains an unasked grounded target: the same words
                # may be proper caveats once every client-answerable target has been
                # tried and the remainder belongs to later document verification.
                r"(?:仍|尚|还)?(?:需|需要|应|优先|尚待|有待).{0,8}"
                r"(?:进一步)?(?:核实|获取|调查|查明|补充|询问|确认)"
                r"|(?:当前|现有).{0,8}(?:信息|事实).{0,8}不足以.{0,12}"
                r"(?:条件性|初步|明确|完整)?.{0,4}(?:分析|判断|结论)"
                r"|(?:剩余|其余|未问|尚有).{0,12}(?:目标|事实|信息).{0,12}"
                r"(?:较高|很高|高|重要|关键).{0,4}(?:信息)?价值"
                r"|建议继续.{0,4}(?:调查|询问|获取|核实|补充)"
                # ``可能影响`` is normal conditional legal analysis when its
                # subject is an already disclosed act (for example, signing an
                # agreement may affect a right).  Treating every such phrase as
                # an admission of a missing material fact rejects exactly the
                # cautious memo rationale that a terminal action should use.
                # Strong prospective wording remains blocked, as does an
                # explicit ``可能直接影响`` admission.
                r"|(?:将|会).{0,6}(?:直接)?影响"
                r"|可能.{0,2}直接影响"
                r"|至关重要",
                terminal_reason,
            )
        )
        # A terminal action may leave explicit unknowns for later document work, but
        # its rationale cannot make an unsupported blanket claim that every remaining
        # independent target is low-yield, nor simultaneously admit those targets are
        # material and still stop.  This checks the action's epistemic consistency;
        # it does not impose a question count or require exhausting the agenda.
        if blanket_low_value:
            violations.append("terminal_unsupported_blanket_low_value_claim")
        if admits_material_gap:
            violations.append("terminal_reason_admits_material_unresolved_target")
        open_withheld_targets = {
            item.target_id
            for item in state.interactions
            if item.response_kind == "withheld"
            and item.target_id
            and item.target_id in provisional
            and provisional[item.target_id].status in {"unknown", "disputed"}
        }
        collapses_withheld_into_unavailable = bool(
            open_withheld_targets
            and re.search(
                r"(?:剩余|其余|关键|上述|相关).{0,50}"
                r"(?:均|都|仍|全部)?(?:不可得|无法(?:获取|提供|回答|披露)|不能(?:提供|回答|披露))",
                terminal_reason,
            )
        )
        if collapses_withheld_into_unavailable:
            violations.append("terminal_collapses_withheld_into_unavailable")
    if action.action_type in {"final", "abstain"} and (
        action.target_id is not None or action.target_type not in {"session", "none"}
    ):
        violations.append("terminal_action_invalid_target")
    fact_actions = {"ask", "clarify", "verify", "summarize"}
    if action.action_type in fact_actions and action.target_type == "fact":
        if not target:
            violations.append("factual_action_missing_target_id")
        elif target not in observations and target not in current:
            violations.append(f"factual_target_missing_from_state:{target}")
        else:
            # Existing state is authoritative for non-regression checks. A policy may
            # not make an answered or unavailable target askable by including a
            # contradictory observation in the same envelope.
            status = current[target].status if target in current else observations[target].status
            if action.action_type == "ask" and status not in {"unknown", "disputed"}:
                violations.append(f"ask_target_not_unresolved:{target}:{status}")
            if status == "not_available":
                violations.append(f"target_not_available:{target}")
            if target in state.asked_targets:
                violations.append(f"repeated_fact_target:{target}")

    normalized_content = normalize_question(action.content)
    repeated_text = normalized_content and any(
        normalize_question(item.question) == normalized_content for item in state.interactions
    )
    if repeated_text:
        violations.append("repeated_question_text")
    elif (
        not normalized_content
        and target
        and any(
            item.target_id == target and item.action_type == action.action_type
            for item in state.interactions
        )
    ):
        violations.append(f"repeated_action_target_without_content:{action.action_type}:{target}")

    violations.extend(action_question_quality_violations(action))
    if target and target in current:
        violations.extend(action_target_alignment_violations(action, current[target].label))
    return violations


def blocking_policy_health_violations(violations: list[str]) -> list[str]:
    return [item for item in violations if not item.startswith("warning:")]


def policy_repair_instruction(violations: list[str], state: ConsultationState) -> str:
    joined = "；".join(violations)
    repeated_question_repair = "repeated_question_text" in violations
    target_reselection_repair = repeated_question_repair or any(
        item.startswith("ask_target_not_unresolved:")
        or item.startswith("target_not_available:")
        or item.startswith("repeated_fact_target:")
        or item.startswith("repeated_action_target_without_content:")
        for item in violations
    )
    withheld_terminal_repair = "terminal_collapses_withheld_into_unavailable" in violations
    terminal_reason_repair = any(
        item
        in {
            "terminal_unsupported_blanket_low_value_claim",
            "terminal_reason_admits_material_unresolved_target",
            "terminal_collapses_withheld_into_unavailable",
        }
        for item in violations
    )
    withheld_target_ids = {
        item.target_id
        for item in state.interactions
        if item.response_kind == "withheld" and item.target_id
    }
    available = [
        f"{fact.fact_id}（{fact.label}）"
        for fact in state.facts
        if fact.status in {"unknown", "disputed"}
        and fact.fact_id not in state.asked_targets
        and not (
            (target_reselection_repair or terminal_reason_repair)
            and fact.fact_id in withheld_target_ids
        )
        and fact.fact_id not in NON_SUBSTANTIVE_FACT_IDS
    ]
    unavailable = [
        fact.fact_id
        for fact in state.facts
        if fact.status == "not_available"
        or fact.fact_id in state.asked_targets
        or (
            (target_reselection_repair or terminal_reason_repair)
            and fact.fact_id in withheld_target_ids
        )
    ]
    current_targets = "、".join(available) or "无"
    exhausted_targets = "、".join(unavailable) or "无"
    existing_ids = "、".join(fact.fact_id for fact in state.facts)
    withheld_targets = (
        "、".join(
            f"{fact.fact_id}（{fact.label}）"
            for fact in state.facts
            if fact.fact_id in withheld_target_ids and fact.status in {"unknown", "disputed"}
        )
        or "无"
    )
    repeated_question_guidance = (
        "本轮是原样重复问题修复。曾返回withheld的目标虽然仍保持开放，但不能由契约"
        "修复器代替策略再次追问；本轮不得选择这些目标。只能改选上列另一未问目标，"
        "若没有则在已有实质事实时输出final。以后只有策略自行提出明显不同且通过普通"
        "健康门禁的问题，才可重新选择withheld目标。"
        if target_reselection_repair and withheld_target_ids
        else ""
    )
    must_repair_question = any(
        item == "multiple_primary_questions"
        or item == "generic_or_abstract_question"
        or item == "excessive_phrase_repetition"
        or item == "question_requests_legal_judgment_from_client"
        or item == "question_target_misaligned"
        or item.startswith("question_target_unbound_coordinated_actors:")
        or item.startswith("unsafe_new_fact_target:")
        or item.startswith("unseen_specific_numeric_anchor:")
        or item.startswith("action_metadata_excessive_phrase_repetition:")
        or item.startswith("factual_target_missing_from_state:")
        for item in violations
    )
    atomic_question_repair = (
        "本轮只修复问题表面：保持原action.target_id，不改选其他事实。content必须改成"
        "恰好一个疑问句且全文最多一个问号；删除第二个问句、条件追问和例示性追问。"
        "若目标标签同时概括多个属性，只询问其中信息价值最高的一个可观察属性，不要求"
        "这一轮覆盖整个标签。例如把‘有哪些凭证？凭证包括什么？’收缩为‘您提交的退赔"
        "凭证具体是什么？’，把‘何时开始和结束？持续多久？’收缩为只问起止时间或只问"
        "持续时长。存在性和后续细节也只能二选一，禁止‘是否有……如果有/具体……’；"
        "身份或工作角色的替代选项改成一个开放式关系问题，禁止‘是否A，或者是否B’。"
        "reason和expected_information也不得暗中追加第二项请求。"
        if "multiple_primary_questions" in violations
        else ""
    )
    unbound_actor_pairs = [
        item.split(":", 1)[1]
        for item in violations
        if item.startswith("question_target_unbound_coordinated_actors:")
    ]
    alignment_question_repair = (
        "本轮只修复目标对齐：保持原action.target_id，并逐项保留目标标签中的事实主语、"
        "实际行为或状态、对象和事件阶段。不得把第三方是否实际介入替换成客户是否尝试"
        "联系第三方，也不得加入目标标签没有绑定的并列行为主体；只把目标标签所指的"
        "同一可观察命题改写成自然问题。"
        + (
            "上一稿自行加入而本轮必须从content、expected_information和reason中删除的"
            "未绑定并列主体是：" + "、".join(unbound_actor_pairs) + "。"
            if unbound_actor_pairs
            else ""
        )
        if "question_target_misaligned" in violations or unbound_actor_pairs
        else ""
    )
    repair_mode = (
        "这次是问题及目标对齐修复，不能改用final或abstain逃避。保留被拒问题中真正缺失、"
        "可由客户回答的一个可观察属性，为它创建不与现有ID重复的新unknown，然后只问这一项。"
        if must_repair_question and not available
        else ""
    )
    no_target_guidance = (
        ""
        if repair_mode
        else "若无可选目标，先重新检查客户目标是否还存在另一项适用且会改变分析的事实维度；"
        "确有则创建一个新的准确unknown并询问，否则已有实质事实时输出final"
        '（content必须为""），不能重复旧目标或abstain。'
    )
    action_repair_guidance = (
        (
            "上一稿final已经承认仍有重要事实缺口，且当前确有可直接选择的未问目标，"
            "因此本轮不得继续改写final理由。action只能从上列未问目标中精确选择一个"
            "继续询问，content只问该标签对应的一个可观察属性，不得改成abstain。"
            if available
            else (
                "本轮只修复上一稿final的理由表述，必须保持final、target_type=session、"
                'target_id=null、content=""，不得退回询问或改成abstain。reason只能说明'
                "当前可见事实已足以形成以已披露事实为限的条件性初步分析；不得声称所有"
                "剩余目标低价值、无法获取，也不得写仍需核实、将直接影响或至关重要。"
            )
        )
        if terminal_reason_repair
        else (
            "先删除所有重复且未变化的state_patch项。若有可选目标，本轮action只能"
            "精确选择其中一个，content只问该标签对应的一个可观察属性。"
            f"{no_target_guidance}"
        )
    )
    withheld_terminal_guidance = (
        f"仍开放的withheld目标是：{withheld_targets}。withheld只表示客户本次未披露，"
        "不等于不可得、客户不知道或无法提供。保持final，但reason必须明确写‘本次未披露’，"
        "不得再把这些目标与其他事项统称为不可得、无法获取或无法提供。"
        if withheld_terminal_repair
        else ""
    )
    return (
        f"上一份JSON违反契约：{joined}。"
        f"当前已有fact_id（不得复制进state_patch）：{existing_ids}。"
        f"当前可直接选择的未问目标：{current_targets}。"
        f"已经询问或不可得、禁止再选的目标：{exhausted_targets}。"
        f"{repeated_question_guidance}"
        f"{atomic_question_repair}"
        f"{alignment_question_repair}"
        f"{repair_mode}"
        f"{action_repair_guidance}"
        f"{withheld_terminal_guidance}"
        "问题不能让客户给出法律规则、责任判断、程序要求或材料清单，不能包含多个问法，"
        "也不能机械重复同一个词组或枚举项。不得使用‘该事实/该信息/详细信息’等无可见指代的"
        "抽象目标；不得在问题、预期信息或理由中加入当前可见状态从未出现的精确日期、金额、"
        "比例或期限阈值。"
        "只输出基于同一可见材料修正后的完整JSON。"
    )


def action_question_quality_violations(action: StructuredAction) -> list[str]:
    if action.action_type not in {"ask", "clarify", "verify", "summarize"}:
        return []
    value = action.content.strip()
    issues: list[str] = []
    if not value:
        issues.append("nonterminal_action_missing_content")
        return issues
    focus = _question_focus(value)
    generic_phrases = (
        "案件具体细节",
        "案件细节",
        "案件详情",
        "客户案件细节",
        "客户问题细节",
        "客户咨询问题细节",
        "客户纠纷问题",
        "客户争议事项",
        "纠纷类型",
        "纠纷性质",
        "纠纷主体",
        "纠纷行为",
        "纠纷事项",
        "纠纷具体细节",
        "纠纷细节",
        "纠纷具体事实",
        "纠纷具体主张",
        "纠纷涉及的当事人",
        "纠纷涉及的具体行为",
        "行为类型",
        "纠纷后果",
        "纠纷的具体后果",
        "争议双方",
        "争议主体",
        "争议行为",
        "争议具体事项",
        "争议行政行为",
        "争议点",
        "争议焦点",
        "争议金额",
        "未解决争议点",
        "法律影响",
        "法律后果",
        "核心问题",
        "这一关键情况",
        "请补充一个尚未说明",
        "该事实",
        "这一事实",
        "该信息",
        "这一信息",
        "相关信息",
        "详细信息",
        "特定事实",
        "需要我提供什么帮助",
        "我能提供什么帮助",
        "希望我提供什么帮助",
    )
    terse_generic = re.fullmatch(
        r"(?:请问|请说明|为避免理解偏差，请进一步说明|关于)?"
        r"(?:具体)?(?:行为|行政行为|争议行政行为|不正当竞争行为)"
        r"(?:的)?(?:类型|细节|具体细节|方法|后果)?[？?]?",
        focus,
    )
    interrogative_or_request_markers = (
        "？",
        "?",
        "是否",
        "有无",
        "能否",
        "可否",
        "什么",
        "怎样",
        "怎么",
        "如何",
        "哪",
        "多少",
        "多久",
        "何时",
        "请说明",
        "请提供",
        "请确认",
        "请描述",
        "请告知",
        "请澄清",
        "说说",
        "能说明",
    )
    non_interrogative = not any(marker in value for marker in interrogative_or_request_markers)
    if any(item in focus for item in generic_phrases) or terse_generic or non_interrogative:
        issues.append("generic_or_abstract_question")
    # Structured decoding can occasionally enter a syntactically valid repetition
    # loop (for example, the same document type emitted dozens of times). Detect
    # repeated list items by structure rather than case vocabulary or a fixed text
    # length, so the contract remains general across legal domains.
    if has_excessive_phrase_repetition(focus):
        issues.append("excessive_phrase_repetition")
    direct_legal_judgment_markers = (
        "根据中国法律",
        "依据中国法律",
        "按照中国法律",
        "根据法律",
        "依据法律",
        "按照法律",
        "是否违法",
        "是否侵权",
        "是否合法",
        "是否符合法律规定",
        "是否符合相关法律",
        "是否符合公司法",
        "是否符合法律",
        "是否构成",
        "是否属于",
        "是否构成恶意",
        "是否构成违约",
        "是否应当承担责任",
        "是否涉及出资义务",
        "是否涉及违约责任",
        "是否意味着",
        "在法律上",
        "法律关系",
        "法律效力",
        "合法性",
        "合规性",
        "有效性",
        "证明力",
        "裁判逻辑",
        "因果关系",
        "主体资格",
        "法律地位",
        "法律主体身份",
        "是否涉及法律上的侵权行为",
        "责任范围",
        "责任归属",
        "个人责任",
        "连带责任",
        "责任的性质",
        "责任性质",
        "责任状态",
        "刑事责任类型",
        "主观动机",
        "不正当竞争意图",
        "是否为假货",
        "是否为独立法人",
        "法律认定",
        "法律评价",
        "法律标准",
        "实质性相似标准",
        "法律行为能力",
        "法律状态",
        "上位法依据",
        "上位法",
        "法定程序",
        "法定义务",
        "程序义务",
        "是否应知",
        "应知",
        "应当知道",
        "应当知晓",
        "是否具备合法",
        "法律风险",
        "法律上",
        "真实有效",
        "来源合法",
        "虚假诉讼",
    )
    source_law_markers = ("法律依据", "法律规定", "法律条款", "法律法规", "法律条文")
    document_markers = (
        "决定书",
        "通知书",
        "判决书",
        "裁定书",
        "起诉状",
        "合同",
        "协议",
        "报告",
        "书面通知",
        "书面文件",
        "生效判决",
        "判决",
    )
    document_read_markers = (
        "载明",
        "写明",
        "注明",
        "列明",
        "约定",
        "规定",
        "条款",
        "引用",
        "提供",
        "内容",
        "名称",
        "编号",
    )
    asks_document_text = any(item in focus for item in document_markers) and any(
        item in focus for item in document_read_markers
    )
    asks_source_law_without_document = (
        any(marker in focus for marker in source_law_markers) and not asks_document_text
    )
    presupposes_legal_classification = (
        bool(
            re.search(
                r"(?:侵权|违法|违约|犯罪|不正当竞争|无效|可撤销)(?:的)?"
                r"(?:行为|事实|证据|时间|责任|后果|情形)",
                focus,
            )
        )
        and not asks_document_text
    )
    asks_legal_threshold = bool(
        re.search(
            r"(?:达到|符合|满足).{0,12}(?:法律认定|法律要求|法律标准|认定标准)",
            focus,
        )
        or re.search(r"(?:实质性相似|混淆可能性|显著性).{0,8}(?:标准|认定)", focus)
        or re.search(
            r"(?:是否|有无)(?:已经|已)?.{0,4}(?:超过|届满|经过).{0,8}"
            r"(?:法定)?(?:时效|期限)",
            focus,
        )
        or re.search(
            r"(?:法定)?(?:时效|期限).{0,8}(?:是否|有无).{0,8}(?:超过|届满|经过)",
            focus,
        )
    )
    asks_client_legal_knowledge = bool(
        re.search(
            r"(?:是否|有无).{0,8}(?:知道|了解|清楚).{0,16}"
            r"(?:诉讼时效|法定期限|法律规定|法律后果|权利义务)",
            focus,
        )
    )
    # These formulations ask the client to supply the lawyer's general legal or
    # procedural answer.  They are different from factual inventory questions such
    # as “您目前有哪些材料” or “通知书写了什么”.
    asks_normative_instruction = bool(
        re.search(
            r"(?:依法|法律上|根据.{0,8}法律|依据.{0,8}法律|按照.{0,8}法律).{0,24}"
            r"(?:如何|怎么|怎样|哪些|什么)",
            focus,
        )
        or re.search(
            r"(?:离婚|起诉|仲裁|复议|执行|登记|申请|报案|维权).{0,12}"
            r"(?:需要|应当|应该|应|须|如何|怎么).{0,12}"
            r"(?:准备|提交|提供|办理|采取|分割|分配|处理|哪些材料|什么材料)",
            focus,
        )
        or re.search(
            r"(?:需要|应当|应该|应|须).{0,8}(?:准备|提交|提供|办理).{0,12}"
            r"(?:哪些|什么|具体)?(?:文件|材料|手续)",
            focus,
        )
        or re.search(
            r"(?:离婚|起诉|仲裁|复议|执行|登记|申请|报案|维权).{0,12}"
            r"需要(?:准备|提交|提供|办理)?(?:哪些|什么|具体).{0,6}(?:文件|材料|手续)",
            focus,
        )
    )
    asks_general_authority_practice = bool(
        re.search(
            r"(?:法院|仲裁庭|仲裁机构|仲裁委|公安机关|检察院|行政机关|监管机关|监管部门)"
            r".{0,24}(?:通常|一般|惯常|可能|通常会|一般会|是否会).{0,16}"
            r"(?:审查|调查|认定|考虑|要求|采用|处理).{0,16}"
            r"(?:哪些|什么|如何|怎么)",
            focus,
        )
        or re.search(
            r"(?:法院|仲裁庭|仲裁机构|仲裁委|公安机关|检察院|行政机关|监管机关|监管部门)"
            r".{0,24}(?:通常|一般|惯常|可能|通常会|一般会|是否会).{0,16}"
            r"(?:哪些|什么).{0,12}(?:事实|材料|证据|因素|情况|标准|手段)",
            focus,
        )
        or re.search(
            r"(?:法院|仲裁庭|仲裁机构|仲裁委|公安机关|检察院|行政机关|监管机关|监管部门)"
            r".{0,24}(?:通常|一般|惯常|可能)(?:会)?.{0,12}"
            r"(?:审查|调查|认定|考虑|要求|采用|处理)(?:的|之).{0,16}"
            r"(?:类型|范围|标准|因素|情况|手段|方式|做法)",
            focus,
        )
    )
    # Asking what facts/evidence an authority recorded as the basis of an already
    # issued decision is document fact-finding, not asking the client to perform
    # the authority's legal allocation.  Keep the exemption source-bound: a bare
    # "how should responsibility be divided" question remains a legal judgment.
    asks_documented_authority_basis = bool(
        re.search(
            r"(?:交警|公安机关|行政机关|监管机关|法院|仲裁机构).{0,24}"
            r"(?:基于|依据).{0,16}(?:哪些|什么)?(?:具体)?(?:事实|证据)",
            focus,
        )
        or re.search(
            r"(?:责任认定书|事故认定书|决定书|判决书|裁定书).{0,20}"
            r"(?:如何|怎样).{0,8}(?:具体)?认定",
            focus,
        )
    )
    responsibility_judgment = (
        bool(
            re.search(
                r"(?:是否|应否|应该|应当|需要).{0,8}(?:承担|负有).{0,8}责任",
                focus,
            )
            or re.search(
                r"(?:是否|有无).{0,12}(?:存在|负有|具有|有).{0,8}(?:责任|义务)",
                focus,
            )
            or re.search(r"责任.{0,4}(?:分配|划分|认定|归属|范围|性质|状态)", focus)
            or re.search(r"(?:是否|应否).{0,24}(?:应当|应该)?承担.{0,24}责任", focus)
        )
        and not asks_document_text
        and not asks_documented_authority_basis
    )
    intent_judgment = bool(re.search(r"(?:是否|有无).{0,16}(?:故意|恶意|意图)", focus))
    classification_judgment = bool(
        re.search(
            r"(?:是否|能否).{0,8}(?:属于|构成|认定为|确认(?:为|是)?).{0,12}"
            r"(?:违法|侵权|违约|犯罪|不正当竞争|抄袭)",
            focus,
        )
        or re.search(r"(?:是否|能否).{0,8}(?:被|系|是).{0,4}(?:抄袭|侵权|违法)", focus)
    )
    reports_an_actor_statement = bool(
        re.search(
            r"(?:明确|表示|告知|答复|回复|载明|写明|认定).{0,16}"
            r"(?:符合|不符合|合法|违法|有效|无效)",
            focus,
        )
    )
    factual_relationship_status = bool(
        re.search(
            r"(?:目前|当前).{0,10}(?:是否)?(?:仍然|仍|还).{0,16}"
            r"(?:与).{0,20}(?:保持|存在|存续).{0,8}"
            r"(?:劳动关系|合同关系|代理关系|婚姻关系)",
            focus,
        )
    )
    legal_relationship_judgment = (
        bool(
            re.search(
                r"(?:是否|能否|是不是|是否为|是否属于).{0,16}"
                r"(?:劳动关系|合同关系|代理关系|婚姻关系).{0,12}"
                r"(?:主体|成立|存在|有效|终止|性质)?",
                focus,
            )
            or re.search(
                r"(?:劳动关系|合同关系|代理关系|婚姻关系).{0,12}"
                r"(?:主体|是否成立|是否存在|是否有效|是否终止|性质)",
                focus,
            )
            or re.search(r"(?:是否|有无|存在).{0,12}挂靠关系", focus)
        )
        and not asks_document_text
        and not reports_an_actor_statement
        and not factual_relationship_status
    )
    compliance_judgment = (
        bool(
            re.search(
                r"(?:是否|有无).{0,12}(?:符合|遵循|履行).{0,16}"
                r"(?:法律|法规|法定|规范|标准|规划要求|程序义务)",
                focus,
            )
            or re.search(
                r"(?:是否|有无).{0,12}(?:持有|具备|取得).{0,8}(?:合法|法定).{0,8}"
                r"(?:资质|资格|许可)",
                focus,
            )
            or re.search(r"(?:是否|有无).{0,16}依法依规", focus)
            or re.search(r"(?:是否|有无).{0,16}法定授权依据", focus)
        )
        and not reports_an_actor_statement
    )
    evidentiary_sufficiency_judgment = bool(
        re.search(r"(?:证据|材料).{0,12}(?:能否|是否能够|足以|可以).{0,8}证明", focus)
        or re.search(
            r"(?:能够|可以|足以)证明.{0,28}(?:的)?(?:证据|材料)"
            r"(?:是|有|包括|具体|什么)",
            focus,
        )
        or re.search(
            r"(?:证据|材料).{0,20}(?:是否)?(?:覆盖|涵盖).{0,20}"
            r"(?:全部|所有|完整|关键)(?:事项|事实|问题|要点|点)",
            focus,
        )
        or re.search(
            r"(?:证据|材料).{0,20}(?:是否)?(?:覆盖|涵盖).{0,12}"
            r"(?:质疑|争议|待证)(?:事项|事实|问题|要点|点)?",
            focus,
        )
        or re.search(
            r"(?:是否存在|有无).{0,12}(?:第三方|证人).{0,8}"
            r"(?:能|可以)证明.{0,8}(?:真实|真实性)",
            focus,
        )
    )
    instrument_validity_judgment = bool(
        re.search(
            r"(?:协议|合同|约定|条款|决定|文书).{0,12}"
            r"是否(?:仍然|仍|还)?(?:真实)?有效(?:[？?。]|$)",
            focus,
        )
    )
    asks_client_legal_responsibility = bool(
        re.search(
            r"(?:认为|判断|可能|是否).{0,24}(?:涉及|承担|构成)?.{0,8}"
            r"(?:哪些|何种|什么)?法律责任",
            focus,
        )
        and not asks_document_text
        and not reports_an_actor_statement
    )
    reports_criminal_adjudication = bool(re.search(r"(?:判决|裁定|被判|判处|定罪|刑事处罚)", focus))
    # A criminal-law noun can modify the person or loss being identified without
    # asking the client to classify conduct.  For example, “被诈骗的受害人是谁、
    # 损失多少” asks two observable case facts; it is not the prohibited question
    # “您是否知道该行为属于诈骗”.  Keep this exemption narrow to victim identity
    # and loss attributes so knowledge-of-illegality questions remain blocked.
    asks_factual_victim_identity_or_loss = bool(
        re.search(
            r"(?:被诈骗|被骗)(?:的)?(?:受害人|被害人).{0,24}"
            r"(?:谁|姓名|身份|是否明确|损失|受损|金额|数额)",
            focus,
        )
        or re.search(
            r"(?:受害人|被害人).{0,16}(?:谁|姓名|身份|是否明确|损失|受损|金额|数额)",
            focus,
        )
    )
    presupposes_criminality = (
        bool(
            re.search(
                r"(?:是否|有无).{0,16}(?:知道|知晓|明知|意识到|认识到|参与|实施).{0,16}"
                r"(?:非法|违法性|犯罪|诈骗|洗钱|赃款)",
                focus,
            )
        )
        and not reports_criminal_adjudication
        and not asks_factual_victim_identity_or_loss
    )
    predictive_legal_effect = bool(
        re.search(
            r"(?:可能|预计|将会).{0,12}(?:对|给).{0,12}"
            r"(?:补偿|赔偿|责任|权利|法律地位).{0,12}(?:影响|后果)",
            focus,
        )
        or re.search(
            r"(?:对|给).{0,12}(?:补偿|赔偿|责任|权利|法律地位).{0,12}"
            r"(?:可能|预计|将会).{0,8}(?:产生)?(?:影响|后果)",
            focus,
        )
    )
    presupposes_breach_or_wrongdoing = bool(
        re.search(
            r"(?:是否|有无).{0,10}(?:存在|涉及).{0,10}"
            r"(?:违约|违法|侵权|犯罪|诈骗|不正当竞争)",
            focus,
        )
    )
    if (
        any(marker in focus for marker in direct_legal_judgment_markers)
        or asks_source_law_without_document
        or responsibility_judgment
        or intent_judgment
        or classification_judgment
        or legal_relationship_judgment
        or presupposes_legal_classification
        or asks_legal_threshold
        or asks_client_legal_knowledge
        or asks_normative_instruction
        or asks_general_authority_practice
        or compliance_judgment
        or evidentiary_sufficiency_judgment
        or instrument_validity_judgment
        or asks_client_legal_responsibility
        or presupposes_criminality
        or predictive_legal_effect
        or presupposes_breach_or_wrongdoing
    ):
        issues.append("question_requests_legal_judgment_from_client")
    conditional_followup = bool(
        re.search(
            r"(?:如果|如)(?:有|是|已|存在|可以|能够|能|签署了|取得了).{0,12}"
            r"(?:请|能否).{0,20}(?:说明|描述|提供|列明|告知)",
            focus,
        )
        or re.search(
            r"(?:如果|如)[^，,。；;？?]{0,20}[，,]\s*"
            r"(?:请|能否|可否).{0,20}(?:说明|描述|提供|列明|告知)",
            focus,
        )
    )
    # “是否存在X；如有，请说明X的细节” is one ordinary conditional
    # intake proposition, not two independent questions.  Limit the exemption to
    # an anaphoric detail/identifier/value request; a conditional clause that
    # introduces another event or actor remains a genuine second question.
    conditional_same_target_detail = bool(
        conditional_followup
        and re.search(
            r"(?:如果|如)[^。；;？?]{0,20}[，,]?\s*(?:请|能否|可否)"
            r".{0,12}(?:说明|描述|提供|列明|告知).{0,16}"
            r"(?:具体)?(?:内容|金额|数额|名称|编号|文号|时间|日期|地点|方式|"
            r"范围|条款|账户|资金流向)",
            focus,
        )
        and not re.search(r"(?:另一个|另一项|其他事件|事故伤情|孩子目前)", focus)
    )
    embedded_evidence_topic_question = bool(
        re.search(
            r"是否.{0,40}(?:关于|针对|围绕).{0,36}是否.{0,36}"
            r"(?:调查|检测|鉴定|评估|报告|意见|材料|记录)",
            focus,
        )
    )
    # DLawBench inquiry units commonly ask several linked attributes of one legal
    # event (for example when/how an injury occurred and what followed).  Treating
    # every lexical category or conjunction as a separate primary question forced
    # those coherent inquiries into a row of tiny, often unanswerable slots.  The
    # contract below rejects genuinely independent questions while allowing one
    # event frame to carry related time/place/manner/result attributes.
    question_clauses = [
        clause.strip() for clause in re.split(r"[；;。？！?]+", focus) if clause.strip()
    ]
    independent_clause_questions = (
        sum(
            bool(
                re.search(
                    r"(?:是否|有无|为什么|为何|何时|哪里|哪些|什么|如何|怎么|多少|"
                    r"哪(?:个|些|一|位|家|项|种|段|天|年|月|日|里|边|方|份|套|"
                    r"类|条|次|时候)?)",
                    clause,
                )
            )
            for clause in question_clauses
        )
        > 1
    )
    coordinated_distinct_instruments = bool(
        re.search(
            r"(?:签署|订立|解除|终止|收到|提交|提供).{0,12}"
            r"[^，,；;]{2,10}(?<!和解)(?:和|及|与)[^，,；;]{2,10}"
            r"(?:协议|合同|文书|记录)",
            focus,
        )
    )
    distinct_temporal_branches = bool(
        re.search(
            r"(?:前后|之前(?:和|及|与|、)之后|前(?:和|及|与|、)后).{0,12}分别"
            r"|分别.{0,12}(?:前后|之前(?:和|及|与|、)之后|前(?:和|及|与|、)后)",
            focus,
        )
    )
    requested_categories = _requested_fact_categories(focus)
    # Closely linked attributes can form one natural event frame.  Other bundles
    # (for example amount + valuation method, current status + a separate loss, or
    # statement + inferred intent) still require independent answers and remain
    # rejected.  This preserves the useful safety boundary without imposing the
    # former one-word-category-per-turn protocol that conflicted with DLawBench's
    # inquiry unit.
    coherent_event_frame_categories = {
        "time",
        "place",
        "party",
        "method",
        "process",
        "conduct",
        "result",
        "health",
    }
    relational_single_proposition = bool(
        "包括" not in focus
        and re.search(
            r"(?:和|及|与).{0,24}(?:比例|一致性|对应关系|关联关系|匹配关系)"
            r"(?:是什么|如何|怎样)?(?:[，,。？！?]|$)",
            focus,
        )
    )
    anaphoric_same_event_context = bool(
        re.search(
            r"(?:内容|说法|用语).{0,20}(?:以及|和|及).{0,12}"
            r"(?:这些|上述|该)(?:行为|言语|表述).{0,16}"
            r"(?:场景|场合|情境|情况下|时候)",
            focus,
        )
    )
    instrument_clause_single_proposition = bool(
        re.search(
            r"(?:合同|协议|约定).{0,36}(?:是否有|有无).{0,28}"
            r"(?:限制|适用|责任|支付|使用|保密|解除|期限)?.{0,8}条款",
            focus,
        )
    )
    technical_scope_synonym = bool(
        re.search(
            r"(?:负责|参与|承担).{0,20}(?:技术)?(?:环节|内容)"
            r"(?:或|和|及)(?:技术)?(?:环节|内容)",
            focus,
        )
    )
    reported_position_reason_single_proposition = bool(
        re.search(
            r"(?:主张|表示|答复|回复|拒绝|否认).{0,28}(?:理由|原因|依据)"
            r"(?:是什么|为何|有哪些|具体|请说明)?",
            focus,
        )
        or re.search(
            r"(?:理由|原因|依据).{0,28}(?:主张|表示|答复|回复|拒绝|否认)",
            focus,
        )
    )
    workflow_participant_single_proposition = bool(
        re.search(
            r"(?:哪些?部门(?:或人员)?|哪些?人员(?:或部门)?|谁|何人).{0,32}"
            r"(?:参与|负责).{0,32}"
            r"(?:制作|编制|处理|审核|复核|签批|分析|采样|销售|管理)",
            focus,
        )
        or re.search(
            r"(?:制作|编制|处理|审核|复核|签批|分析|采样|销售|管理).{0,32}"
            r"(?:由谁|谁负责|谁参与|哪些?部门|哪些?人员)",
            focus,
        )
    )
    # Event nouns and verbs are context when the requested attribute is only the
    # event timestamp.  For example, ``支付预付款的具体日期和时间是什么时候``
    # asks for one temporal value; lexical category matching also sees ``支付``
    # and would otherwise misclassify it as a separate transaction request.
    # Keep the exemption syntactic and narrow so genuine bundles such as
    # ``支付日期和金额`` or ``决定书名称和日期`` remain rejected.
    event_timestamp_single_proposition = bool(
        re.search(
            r"(?:的)?(?:具体)?(?:日期和时间|时间和日期|日期|时间)"
            r"(?:是|为|发生在)?(?:什么|何时|什么时候|哪天|哪一日)?(?:时候)?[？?]?$",
            focus,
        )
        and not re.search(
            r"(?:金额|数额|价格|价值|名称|编号|内容|条款|地点|地址|方式|方法|"
            r"原因|理由|依据|结果|状态|人员|主体|范围)"
            r"(?:和|及|与|、)(?:具体)?(?:日期|时间)"
            r"|(?:日期|时间)(?:和|及|与|、)(?:金额|数额|价格|价值|名称|编号|"
            r"内容|条款|地点|地址|方式|方法|原因|理由|依据|结果|状态|人员|"
            r"主体|范围)",
            focus,
        )
    )
    # The instrument/relationship phrase is context when the sole requested
    # value is its duration.  In "连续订立固定期限劳动合同的总工作年限",
    # ``合同`` is not a second request alongside ``年限``.  Do not exempt labels
    # that explicitly coordinate duration with text, amount, reason, or outcome.
    relationship_duration_single_proposition = bool(
        re.search(
            r"(?:连续)?(?:签订|订立|履行|存续).{0,24}(?:劳动)?合同.{0,16}"
            r"(?:总)?(?:工作)?(?:年限|时长|多久|多少年)",
            focus,
        )
        and not re.search(
            r"(?:内容|条款|金额|数额|原因|理由|结果|状态)"
            r"(?:和|及|与|、).{0,10}(?:年限|时长|期限|多久|多少年)",
            focus,
        )
    )
    # Property/economic loss and human casualties are two independently
    # answerable outcomes even though both belong to one accident frame.  A
    # planner target that bundles them must be split before online questioning.
    distinct_loss_and_casualty_outcomes = bool(
        re.search(
            r"(?:财产|经济).{0,8}(?:损失|损害).{0,8}(?:和|及|与|、).{0,8}"
            r"(?:人员)?(?:伤亡|伤情|受伤|死亡)",
            focus,
        )
        or re.search(
            r"(?:人员)?(?:伤亡|伤情|受伤|死亡).{0,8}(?:和|及|与|、).{0,8}"
            r"(?:财产|经济).{0,8}(?:损失|损害)",
            focus,
        )
    )
    incompatible_attribute_bundle = bool(
        len(requested_categories) > 1
        and not requested_categories <= coherent_event_frame_categories
        and not relational_single_proposition
        # A second clause that explicitly points back to "these/that acts" and
        # asks only for their setting is context for the same event, not another
        # independent fact request.  This preserves natural Chinese intake while
        # still rejecting a content question bundled with a new act or outcome.
        and not anaphoric_same_event_context
        and not instrument_clause_single_proposition
        and not technical_scope_synonym
        and not reported_position_reason_single_proposition
        and not workflow_participant_single_proposition
        and not event_timestamp_single_proposition
        and not relationship_duration_single_proposition
    )
    if (
        value.count("？") + value.count("?") > 1
        or (value.count("是否") > 1 and not embedded_evidence_topic_question)
        or (conditional_followup and not conditional_same_target_detail)
        or independent_clause_questions
        or coordinated_distinct_instruments
        or distinct_temporal_branches
        or distinct_loss_and_casualty_outcomes
        or has_coordinated_distinct_misconduct(focus)
        or incompatible_attribute_bundle
    ):
        issues.append("multiple_primary_questions")
    return issues


_ALIGNMENT_STOP_PHRASES = (
    "请说明",
    "请问",
    "请确认",
    "能否",
    "能够",
    "关于",
    "客户",
    "您",
    "目前",
    "当前",
    "具体",
    "实际",
    "相关",
    "情况",
    "事实",
    "一项",
    "亲历",
    "现有文件",
    "是否",
    "有无",
)


def _alignment_text(value: str) -> str:
    # A before/after question is the ordinary-language form of a planner label
    # that names the temporal ordering between two events. Normalize only these
    # explicit temporal-relation phrases; unrelated time questions still need
    # their event nouns to overlap.
    value = re.sub(
        r"(?:在)?时间顺序上(?:的)?(?:具体)?(?:关联|关系)|时间先后顺序|先后顺序",
        "先后",
        value,
    )
    value = re.sub(r"(?:之前还是之后|前还是后|先还是后)", "先后", value)
    # Duration is commonly phrased as a formal planner attribute ("时间长度")
    # and as an intake question ("持续多少天/多久/具体天数").  Keep this a
    # closed attribute-level equivalence rather than lowering the general lexical
    # overlap threshold, which would also admit unrelated timestamp questions.
    value = re.sub(
        r"(?:发生的)?(?:具体)?时间长度|(?:具体)?持续时长|(?:具体)?时长|"
        r"持续(?:了)?(?:多长时间|多久|多少天)|(?:具体)?天数|多长时间|多久",
        "时长",
        value,
    )
    normalized = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", value).lower()
    for phrase in _ALIGNMENT_STOP_PHRASES:
        normalized = normalized.replace(phrase, "")
    return normalized


def _alignment_bigrams(value: str) -> set[str]:
    return {value[index : index + 2] for index in range(max(0, len(value) - 1))}


_TRAILING_BOOLEAN_OPERATOR = re.compile(r"(?:是否|有无|能否|可否)$")


def _atomic_surface_unit_is_complete(value: str) -> bool:
    """Return whether one literal unit can independently become a safe question."""

    unit = value.strip().rstrip("？?。.!！；;,，：:").strip()
    if len(unit) < 3 or _TRAILING_BOOLEAN_OPERATOR.search(unit):
        return False
    direct = bool(
        re.search(
            r"(?:是否|有无|为什么|为何|哪里|哪些|什么|如何|怎么|"
            r"多少|何时|什么时候|哪(?:个|些|一|位|家|项|种|段|天|"
            r"年|月|日|里|边|方|份|套|类|条|次|时候)?)",
            unit,
        )
    )
    content = (
        unit + "？"
        if direct
        else f"关于{unit}，请说明您亲历或现有文件能够确认的一项具体事实？"
    )
    probe = StructuredAction(action_type="ask", target_type="fact", content=content)
    return not action_question_quality_violations(probe)


def visible_target_atomic_units(value: str) -> list[str]:
    """Return auditable atomic attributes named by one visible target label.

    This is a surface decomposition only: it neither consults hidden facts nor
    invents a replacement topic.  The units are used both to explain a compound
    counterfactual target to the frozen policy and to validate the policy's atomic
    question, so generation and checking cannot disagree about the same label.
    """

    parentheticals = re.findall(r"[（(]([^）)]*)[）)]", value)
    base = re.sub(r"[（(][^）)]*[）)]", "", value).strip()
    split_units = [item.strip() for item in re.split(ATTRIBUTE_COORDINATION_PATTERN, base)]
    # An explicit separator licenses decomposition only when *every* side is an
    # independently safe and complete target.  Never skip a broken first fragment
    # or silently treat an explicit compound as one target; an empty result sends
    # it back to planner repair without changing target rank at execution time.
    if len(split_units) > 1:
        units = (
            split_units
            if all(_atomic_surface_unit_is_complete(item) for item in split_units)
            else []
        )
    else:
        units = [base] if base and _atomic_surface_unit_is_complete(base) else []
    for parenthetical in parentheticals:
        examples = re.sub(r"^(?:如|例如|比如)[:：]?", "", parenthetical).strip()
        units.extend(
            item.strip()
            for item in re.split(r"[、,，；;]", examples)
            if _atomic_surface_unit_is_complete(item)
        )
    return list(dict.fromkeys(item for item in units if item))


def _alignment_target_units(value: str) -> list[str]:
    """Return the full visible target plus explicitly named atomic attributes."""

    base = re.sub(r"[（(][^）)]*[）)]", "", value).strip()
    return list(
        dict.fromkeys(
            item
            for item in (value, base, *visible_target_atomic_units(value))
            if item
        )
    )


def _alignment_unit_matches(source: str, target: str) -> bool:
    left = _alignment_text(source)
    right = _alignment_text(target)
    if len(left) < 2 or len(right) < 2:
        return False
    if left in right or right in left:
        return True
    # Ordinary Chinese questions express an age attribute as “多大/几岁”.  This is
    # a lexical paraphrase of the visible “年龄” unit, not a new target.
    if "年龄" in left and re.search(r"(?:多大|几岁|多少岁)", target):
        return True
    if "年龄" in right and re.search(r"(?:多大|几岁|多少岁)", source):
        return True
    left_bigrams = _alignment_bigrams(left)
    shared = left_bigrams & _alignment_bigrams(right)
    return len(shared) >= 2 and len(shared) / max(1, len(left_bigrams)) >= 0.16


def action_target_alignment_violations(action: StructuredAction, target_label: str) -> list[str]:
    """Reject a surface question that asks about a different subject than its target.

    The check uses only the planner-approved visible label and model output.  It does
    not select a topic or inspect hidden facts; it keeps policy choice and rendered
    question on the same auditable action boundary.
    """

    if action.action_type not in {"ask", "clarify", "verify", "summarize"}:
        return []
    # Do not let a surface paraphrase silently move an event-response target to a
    # later discovery stage.  In safety and care matters, "what the caregiver did
    # during the incident" and "what the caregiver did after learning of the
    # outcome" are different observable facts.  Lexical-overlap scoring alone is
    # intentionally permissive and would otherwise accept this stage mutation.
    target_during_event = bool(
        re.search(
            r"(?:在|于).{0,24}(?:事件|过程|行为|受伤)(?:当)?(?:中|期间|时)",
            target_label,
        )
    )
    question_after_discovery = bool(
        re.search(
            r"(?:发现|得知|知道|获悉).{0,16}(?:受伤|风险|异常).{0,4}(?:后|之后)",
            action.content,
        )
    )
    if target_during_event and question_after_discovery:
        return ["question_target_misaligned"]
    target_third_party_intervention = bool(
        re.search(
            r"(?:第三方|学校|医疗机构|其他机构).{0,12}(?:介入|参与|干预|协助)",
            target_label,
        )
        or re.search(
            r"(?:是否有|有无).{0,8}(?:第三方|学校|医疗机构|其他机构).{0,12}介入",
            target_label,
        )
    )
    question_client_contact_attempt = bool(
        re.search(
            r"(?:您|你|客户).{0,12}(?:尝试|曾|是否).{0,12}"
            r"(?:联系|求助于|寻找).{0,12}(?:第三方|学校|医疗机构|其他机构)",
            action.content,
        )
    )
    if target_third_party_intervention and question_client_contact_attempt:
        return ["question_target_misaligned"]
    # A subjectless existence/status target must not silently expand into a joint
    # proposition about two separately acting institutions.  Such an expansion is
    # not merely stylistic: one client fact may answer one institution but not the
    # other, leaving the disclosure controller unable to bind an honest response.
    # Keep explicitly joint planner targets intact; only reject actors introduced
    # by the surface question itself.
    coordinated_institution = re.search(
        r"(?P<left>[\u4e00-\u9fff]{1,10}(?:方|部门|机关|公司|平台|法院|银行|医院))"
        r"(?:和|及)"
        r"(?P<right>[\u4e00-\u9fff]{1,10}(?:方|部门|机关|公司|平台|法院|银行|医院))"
        r".{0,4}是否",
        action.content,
    )
    if coordinated_institution and not all(
        actor in target_label
        for actor in (
            coordinated_institution.group("left"),
            coordinated_institution.group("right"),
        )
    ):
        return [
            "question_target_unbound_coordinated_actors:"
            + coordinated_institution.group("left")
            + "+"
            + coordinated_institution.group("right")
        ]
    target = _alignment_text(target_label)
    question = _alignment_text(action.content)
    if len(target) < 4 or len(question) < 4:
        return []
    if target in question or question in target:
        return []
    # Formal investigation plans often name a temporal attribute as
    # “X过程的具体时间”, while a natural client question asks “什么时候开始X”.
    # The event anchor and the requested attribute are identical even though
    # character n-gram overlap is sparse.  Keep this equivalence bounded to an
    # explicit temporal interrogative and a non-generic event anchor.
    temporal_anchor = re.sub(
        r"(?:过程)?的?(?:具体)?(?:时间|日期|时点|时间节点)$",
        "",
        target_label,
    ).strip()
    if (
        len(_alignment_text(temporal_anchor)) >= 2
        and _alignment_text(temporal_anchor) in question
        and re.search(r"(?:何时|什么时候|哪天|哪一日|具体时间|时间是)", action.content)
    ):
        return []
    # Likewise, “X行为的具体情况” and “X的具体情况怎样” are the same
    # observable event-detail target.  Require a substantive event anchor and an
    # explicit detail interrogative so this cannot license an unrelated topic.
    detail_anchor = re.sub(
        r"(?:行为|过程)?的?(?:具体)?(?:情况|细节|内容)$",
        "",
        target_label,
    ).strip()
    normalized_detail_anchor = _alignment_text(detail_anchor)
    if (
        len(normalized_detail_anchor) >= 2
        and normalized_detail_anchor in question
        and re.search(r"(?:具体情况|具体细节|具体内容|怎样|如何|哪些|什么)", action.content)
    ):
        return []
    # Chinese consultation questions naturally replace the planner's formal
    # witness nouns with an ordinary-person paraphrase.  This is the same
    # observable proposition (whether another person saw or knew of the event),
    # not a move to a different target.  Keep the equivalence explicit and
    # auditable instead of weakening the general lexical-overlap threshold.
    witness_target = bool(
        re.search(r"(?:第三方|其他人|别人|有人).{0,8}(?:目击|目睹|知情|知道|了解)", target_label)
        or re.search(r"(?:目击者|知情人)", target_label)
    )
    witness_question = bool(
        re.search(r"(?:第三方|其他人|别人|有人).{0,12}(?:目击|目睹|知情|知道|了解)", action.content)
        or re.search(r"(?:目击者|知情人)", action.content)
    )
    if witness_target and witness_question:
        return []
    target_units = _alignment_target_units(target_label)
    if any(_alignment_unit_matches(unit, action.content) for unit in target_units):
        return []
    # A repair may deliberately ask just one attribute of a compound planner label.
    # Use expected_information only as a grounded semantic bridge: it must first
    # align with an explicitly visible target unit, and the question must in turn
    # align with it.  This accepts a genuine atomic projection without trusting
    # metadata that introduces a new topic.
    expected = action.expected_information.strip()
    if expected and any(_alignment_unit_matches(unit, expected) for unit in target_units) and (
        _alignment_unit_matches(expected, action.content)
    ):
        return []
    return ["question_target_misaligned"]


def _question_focus(value: str) -> str:
    """Drop a factual recap before judging what the question actually requests."""

    if not value.startswith(("您提到", "客户称", "根据您", "按您")):
        return value
    parts = re.split(
        r"[，,；;。](?=(?:但|不过|那么)?(?:能否|可否|请问|请说明|您是否|是否|具体))",
        value,
    )
    return parts[-1].strip()


def _requested_fact_categories(value: str) -> set[str]:
    """Approximate independent requested facts; examples within one class stay one fact."""

    scan_value = re.sub(
        r"请说明您亲历或现有文件能够确认的(?:一项)?具体事实",
        "",
        value,
    )
    # Parentheticals and tails introduced by an explicit example marker illustrate
    # the requested attribute; they are not additional primary requests.
    scan_value = re.sub(r"[（(][^）)]*[）)]", "", scan_value)
    scan_value = re.split(r"(?:例如|比如|(?<=[，,])如)(?:[：:，,])?", scan_value, maxsplit=1)[0]

    categories = {
        "time": ("时间", "日期", "何时", "期限", "起止"),
        "place": ("地点", "地址", "位置"),
        "party": (
            "人员",
            "当事人",
            "第三方",
            "身份",
            "姓名",
            "主体",
            "签署人",
            "双方信息",
            "发布机关",
            "谁",
        ),
        "amount": (
            "金额",
            "数额",
            "价格",
            "价值",
            "估值",
            "评估价格",
            "费用",
            "比例",
            "份额",
        ),
        "document": (
            "文件",
            "材料",
            "合同",
            "协议",
            "通知书",
            "决定书",
            "判决书",
            "裁定书",
            "报告书",
            "报告文件",
            "监测报告",
            "检测报告",
            "审计报告",
            "评估报告",
            "报告内容",
            "报告原文",
            "记录",
            "凭证",
        ),
        "content": ("内容", "原文", "条文"),
        "reason": ("原因", "理由", "依据"),
        "source": ("来源",),
        "method": ("方式", "方法"),
        "process": ("过程", "经过", "步骤", "执行情况", "落实情况", "处理情况"),
        "result": ("结果", "进展", "效果", "功效", "伤情", "治疗情况", "损失"),
        "health": ("健康", "心理", "症状", "诊断", "治疗", "医疗"),
        "living_care": ("生活状况", "居住情况", "照顾", "照料", "日常安排"),
        "frequency": ("频率", "次数", "持续时间", "多久"),
        "purpose": ("目的", "用途", "功能", "意图", "动机"),
        "agreement": ("约定", "承诺", "条款", "协议内容", "合同内容"),
        "conduct": (
            "行为",
            "具体行为",
            "实际行为",
            "具体操作",
            "实际操作",
            "履行情况",
            "操作过程",
            "采取措施",
            "具体措施",
        ),
        "status": (
            "当前状态",
            "当前状况",
            "当前的状况",
            "实际状态",
            "登记状态",
            "处理状态",
            "签署情况",
            "法律状态",
            "具体情况",
        ),
        "position": ("主张", "态度", "说法", "表述", "陈述", "辩解", "反馈"),
        "contribution": ("投入", "装修", "贡献", "支出"),
        "procedure": (
            "诉讼",
            "仲裁",
            "复议",
            "手续",
            "申请程序",
            "行政程序",
            "法律程序",
        ),
        "standard": (
            "规范",
            "标准",
            "法定要求",
            "规划要求",
            "监管要求",
            "技术要求",
        ),
        "identity_existence": ("真实存在", "身份真实性", "主体真实性"),
        "transaction": (
            "购买",
            "支付",
            "实际销售",
            "进行销售",
            "销售产品",
            "销售商品",
            "销售设备",
            "销售数量",
            "销售金额",
            "销售渠道",
            "销售行为",
            "交付",
            "收款",
        ),
        "name_or_identifier": (
            "名称",
            "全称",
            "名单",
            "编号",
            "账号",
            "职位",
            "联系方式",
            "具体信息",
        ),
        "composition": ("成分", "配方", "具体构成"),
        "scope": ("范围", "覆盖范围"),
        "measurement_value": ("数值", "读数"),
        "trend": ("趋势", "变化曲线"),
        "knowledge": ("是否已知", "是否知晓", "了解程度", "认知程度"),
        "future_need": ("是否需要", "后续需要", "持续治疗"),
        "income_or_revenue": ("收入", "销售额", "获利", "收益", "营业额"),
        "complaint": ("投诉", "举报"),
        "count": ("数量", "份数", "件数", "人数", "次数", "总量"),
        "adjudication": ("罪名", "裁判结果", "判决结果", "判处结果"),
        "source_or_channel": (
            "采购来源",
            "采购渠道",
            "供货来源",
            "供应渠道",
            "供应商",
            "供货商",
        ),
        "expected_outcome": ("预期效果", "期望效果", "希望结果", "预期结果"),
        "manifestation": ("具体表现",),
        "usage": ("使用情况", "实际使用"),
        "object_or_product": ("产品", "商品", "服务项目"),
        "document_identifier": ("文号", "文件编号"),
        "participation": ("参与程度", "参与环节"),
        "scene": ("具体场景",),
        "followup_action": ("后续处理", "后续措施"),
        "itemization": ("明细", "具体项目", "项目构成"),
    }
    if not re.search(r"(?:、|以及|(?<![涉提参])及|和|(?<!参)与|或|且|包括)", scan_value):
        return set()
    found = {
        category
        for category, markers in categories.items()
        if any(
            (marker != "目的" and marker in scan_value)
            or (marker == "目的" and re.search(r"(?<!项)目的", scan_value))
            for marker in markers
        )
    }
    if len(found) > 1 and re.search(
        r"(?:是否|有无|有没有)(?:已经|已|实际|曾经|曾)?.{0,48}"
        r"(?:作出|给出|发出|收到|获得)?(?:答复|回复|回应)(?:过|了)?"
        r"(?:[？?。.]|$)",
        scan_value.strip(),
    ):
        # In “是否就产品来源或成分问题作出回应”, the coordinated nouns name
        # the topic of one response-existence proposition; the client supplies
        # one boolean answer, not independent source and composition values.
        # Keep attribute questions such as “回应的内容和时间” compound: their
        # requested dimensions occur after the response noun and therefore do
        # not match this terminal event-existence form.
        return set()
    if (
        "name_or_identifier" in found
        and len(found) > 1
        and re.search(
            r"(?:名称|全称|编号|账号|职位|联系方式|具体信息)"
            r"(?:和|及|与|或)[^，,；;？?]{1,16}"
            r"(?:的|时(?!间)|期间|过程中).{0,24}"
            r"(?:时间|日期|方式|渠道|内容|范围|数量|金额|比例|频率|状态)",
            scan_value,
        )
    ):
        # In “软件名称和域名的起始时间”, 名称 is one coordinated object
        # governed by the trailing time attribute; it is not a separate request
        # for the object's identifier.  Preserve genuinely compound coordinate
        # requests such as “软件名称和具体使用时间”, where no shared trailing
        # attribute construction exists.
        found.discard("name_or_identifier")
    if "agreement" in found and re.search(
        r"(?:合同|协议|约定).{0,8}(?:条款|内容|条件)", scan_value
    ):
        found.discard("document")
    if (
        "agreement" in found
        and len(found) > 1
        and re.search(
            r"(?:合同|协议|条款|约定).{0,16}(?:中|约定|载明|规定|关于|适用|限制|内容)",
            scan_value,
        )
    ):
        # The agreement identifies where the requested attribute is found; it is
        # context, not a second answer dimension (for example, a clause's subject or
        # start date).
        found.discard("agreement")
    if "agreement" in found and re.search(
        r"(?:承诺|约定).{0,16}(?:实际)?(?:落实|履行|执行)(?:情况|过程)", scan_value
    ):
        found.discard("agreement")
    if (
        "agreement" in found
        and len(found) > 1
        and re.search(
            r"(?:合同|协议|条款|约定).{0,16}"
            r"(?:签署|订立|生效|解除|终止|报酬)?.{0,8}"
            r"(?:时间|日期|主体|谁|方式|金额)",
            scan_value,
        )
    ):
        found.discard("agreement")
    if "frequency" in found and re.search(r"(?:持续时间|多久)", scan_value):
        found.discard("time")
    if {"reason", "purpose"} <= found and re.search(
        r"(?:原因|理由)(?:或|和|及|与)(?:意图|动机|目的)", scan_value
    ):
        # These are alternative words for one motive proposition, not two
        # independently answerable attributes.
        found.discard("purpose")
    if (
        "transaction" in found
        and "document" in found
        and re.search(
            r"(?:购买|交易|销售).{0,16}(?:是否|有无).{0,8}"
            r"(?:签署|订立).{0,6}(?:合同|协议)",
            scan_value,
        )
    ):
        # The transaction identifies which instrument's existence is requested.
        found.discard("transaction")
    if (
        "transaction" in found
        and "result" in found
        and re.search(
            r"(?:购买|接受|选择).{0,20}(?:预期|期望|希望).{0,12}"
            r"(?:效果|结果|服务)",
            scan_value,
        )
    ):
        # Purchase context does not add a second fact to the client's expected
        # bargain or service outcome.
        found.discard("transaction")
    if (
        "source_or_channel" in found
        and "name_or_identifier" in found
        and re.search(
            r"(?:制造商|供应商|供货商)(?:或|和|及|与)(?:制造商|供应商|供货商)"
            r"(?:名称|全称)?(?:[，,。？！?]|$)",
            scan_value,
        )
    ):
        # Manufacturer/supplier are alternative source roles; the requested answer
        # remains one source identity.
        found.discard("name_or_identifier")
    if "party" in found and re.search(
        r"(?:人员|当事人|负责人|联系人|经办人|工作人员).{0,8}"
        r"(?:姓名|名称|身份)(?:是什么)?(?:[，,。？！?]|$)",
        scan_value,
    ):
        # “人员姓名” is one identity answer, not an actor plus a second identifier
        # proposition.  Additional contact details or roles remain independently
        # detectable and are not erased by this narrow terminal construction.
        found.discard("name_or_identifier")
        if "过程中" in scan_value:
            # The process phrase locates which contact person is meant; it does not
            # request a process narrative in addition to the person's identity.
            found.discard("process")
    if (
        "party" in found
        and "agreement" in found
        and re.search(
            r"与.{0,16}(?:签订|签署|订立).{0,8}(?:合同|协议).{0,8}"
            r"(?:条款|条件|内容)",
            scan_value,
        )
    ):
        # The counterparty phrase identifies whose agreement is being recalled.
        found.discard("party")
    if "complaint" in found and re.search(
        r"(?:投诉|举报)(?:和|及|与|或)(?:反馈|意见|反映).{0,8}(?:内容)?$",
        scan_value,
    ):
        # Complaint/feedback are coordinated labels for one grievance-content
        # dimension in this construction.
        found.discard("position")
        found.discard("content")
    if {"party", "document", "health"}.issubset(found) and re.search(
        r"(?:第三方机构或人员|第三方人员或机构).{0,20}"
        r"(?:身心|身体|心理|健康).{0,10}(?:评估或记录|记录或评估)",
        scan_value,
    ):
        # Party and health phrases modify the provenance and subject of one
        # assessment/record-existence target.
        found.discard("party")
        found.discard("health")
    if "method" in found and "联系方式" in scan_value:
        without_contact_method = scan_value.replace("联系方式", "")
        if not any(marker in without_contact_method for marker in ("方式", "方法")):
            found.discard("method")
    if (
        "living_care" in found
        and "party" in found
        and (
            re.search(r"(?:参与)?照顾.{0,16}(?:谁|姓名|身份|关系)", scan_value)
            or re.search(r"(?:亲属|第三方|人员).{0,16}(?:参与)?照顾", scan_value)
        )
    ):
        # Care describes why the person is relevant; the requested attribute is
        # still only that caregiver's identity or relationship.
        found.discard("living_care")
    if "participation" in found and re.search(r"参与.{0,8}(?:具体|实际)?(?:行为|操作)", scan_value):
        found.discard("participation")
    if "object_or_product" in found and len(found) > 1:
        # A product/service noun ordinarily names the object whose one attribute is
        # requested (usage frequency, operator, effect, etc.); it is not itself a
        # second answer dimension.  A bare “产品或服务项目是什么” still retains the
        # category because no independent attribute category is present.
        found.discard("object_or_product")
    if (
        "party" in found
        and "conduct" in found
        and re.search(
            r"(?:由谁|谁|何人|哪些人|人员身份).{0,16}(?:操作|使用|实施|执行|参与)",
            scan_value,
        )
    ):
        # The conduct is the predicate that identifies which actor is sought; the
        # client supplies one answer—the actor—not a separate conduct narrative.
        found.discard("conduct")
    if (
        "party" in found
        and "document" in found
        and re.search(
            r"第三方.{0,12}(?:检测|监测|审计|评估|市场调研)?(?:报告|记录|数据|问卷|调研)",
            scan_value,
        )
    ):
        # “第三方” modifies the provenance of a report/data item.  It does not ask
        # the client to identify a person in addition to stating whether that item
        # exists.
        found.discard("party")
    if "party" in found and re.search(
        r"第三方.{0,16}(?:市场调研|消费者问卷|销售数据|调查数据)", scan_value
    ):
        found.discard("party")
    if (
        "party" in found
        and len(found) > 1
        and re.search(
            r"(?:人员|当事人|第三方|主管|执法机关|监管机关|行政机关|"
            r"参与者|组织者|客户|对方|相对方).{0,30}"
            r"(?:具体|实际|给予|实施|采取|收到|签署|支付|指示|提及|陈述|说明|"
            r"沟通|联系)",
            scan_value,
        )
        and not re.search(r"(?:身份|姓名|名称|名单|主体是谁)", scan_value)
    ):
        found.discard("party")
    if (
        "party" in found
        and "result" in found
        and re.search(
            r"(?:人员|参与者|员工|客户|消费者|患者|受害人).{0,16}"
            r"(?:遭受|发生|产生).{0,8}(?:损失|损害|伤害|伤情)",
            scan_value,
        )
    ):
        # The person phrase identifies whose single outcome is requested.  It is
        # not an independent identity request unless the wording also asks who the
        # person is (handled by the remaining party markers).
        found.discard("party")
    if (
        "process" in found
        and "content" in found
        and re.search(
            r"(?:在|于).{0,16}(?:过程|期间)(?:中)?.{0,16}(?:具体)?内容",
            scan_value,
        )
    ):
        found.discard("process")
    if (
        "position" in found
        and "content" in found
        and re.search(
            r"(?:(?:陈述|答复|回应|回复|说明|表达).{0,4}(?:具体)?内容|"
            r"具体(?:陈述|答复|回应|回复|说明|表达)内容)",
            scan_value,
        )
    ):
        found.discard("position")
    if (
        "position" in found
        and "time" in found
        and re.search(
            r"(?:陈述|答复|回应|回复|说明|表达).{0,6}(?:时间|日期)",
            scan_value,
        )
    ):
        found.discard("position")
    if re.search(
        r"(?:对|关于).{0,30}(?:使用情况|实际使用).{0,16}"
        r"(?:陈述|说明|答复|回应).{0,8}(?:内容|时间|日期)",
        scan_value,
    ):
        # Product/use identifies the subject of the statement.  The requested
        # attribute is only that statement's content or date.
        found.discard("usage")
        found.discard("object_or_product")
    if (
        "document" in found
        and "content" in found
        and re.search(
            r"(?:文件|材料|合同|协议|通知书|决定书|判决书|裁定书|报告)"
            r".{0,8}(?:具体)?(?:内容|原文|条款)",
            scan_value,
        )
    ):
        found.discard("document")
    if (
        "document" in found
        and "health" in found
        and re.search(
            r"(?:医疗记录|病历|诊断(?:证明|文件|记录)|就诊记录|"
            r"伤情鉴定|治疗记录)",
            scan_value,
        )
    ):
        # Medical/diagnostic wording names the instrument whose existence or
        # recorded content is requested.  It is not a second request for the
        # patient's health status unless that status is separately coordinated.
        found.discard("health")
        found.discard("result")
    if (
        "document" in found
        and "content" in found
        and re.search(r"(?:记录|鉴定|病历).{0,12}(?:具体)?(?:内容|记载|原文)", scan_value)
    ):
        found.discard("document")
    if {"content", "document"} <= found and re.search(
        r"(?:上传|发布|提交|传播).{0,12}内容.{0,6}的"
        r"(?:审核|审查|预警|处理)?(?:日志|记录|报告)",
        scan_value,
    ):
        # “上传内容” names the object monitored by one requested log/record; it
        # does not ask for that uploaded content in addition to the instrument.
        found.discard("content")
    if "conduct" in found and re.search(
        r"(?:行为|事件|操作|处置).{0,4}的(?:具体)?"
        r"(?:时间|日期|地点|方式|方法|原因|理由|持续时间|时长)",
        scan_value,
    ):
        # The event phrase identifies whose one trailing attribute is requested;
        # it is not a second request for a full conduct narrative.
        found.discard("conduct")
    if {"method", "conduct"} <= found and re.search(
        r"(?:以何种|通过哪些|用什么|采取何种)(?:具体)?方式.{0,32}行为",
        scan_value,
    ):
        found.discard("conduct")
    if "conduct" in found and re.search(
        r"行为.{0,8}(?:产生|造成|导致).{0,24}"
        r"(?:医疗|诊断|治疗|病历|记录|鉴定)",
        scan_value,
    ):
        # The conduct is causal context identifying whose medical instrument or
        # contents are sought; the answer is not a second conduct narrative.
        found.discard("conduct")
    if {"health", "content"} <= found and re.search(
        r"(?:医疗|诊断|治疗|病历).{0,12}(?:具体)?内容", scan_value
    ):
        found.discard("health")
    if {"reason", "content"} <= found and re.search(
        r"(?:拒绝理由|驳回理由|审查意见|异议).{0,24}(?:书面)?(?:内容|原文)",
        scan_value,
    ):
        # The reason/opinion phrase is the subject of one requested document
        # content (or its existence), not a separate causal explanation.
        found.discard("reason")
    if (
        "document" in found
        and "content" in found
        and re.search(
            r"(?:合同|协议).{0,32}(?:条款|约定).{0,6}(?:具体)?内容",
            scan_value,
        )
    ):
        # The dispute terms between “合同” and “条款内容” identify which single
        # contractual text is requested; they do not turn the document itself into
        # an additional answer dimension.
        found.discard("document")
    if (
        "document" in found
        and len(found) > 1
        and re.search(
            r"(?:合同|协议|条款).{0,16}(?:中|约定|载明|规定|关于).{0,20}"
            r"(?:金额|数额|工资|报酬|费用|周期|频率|时间|日期|方式)",
            scan_value,
        )
    ):
        # The instrument is only the source of one requested contractual
        # attribute (for example, the agreed wage amount).  Counting both the
        # document and its attribute turns an ordinary atomic question into a
        # false compound.
        found.discard("document")
    if (
        "document" in found
        and "name_or_identifier" in found
        and re.search(
            r"(?:文件|材料|合同|协议|通知书|决定书|判决书|裁定书|报告)"
            r".{0,8}(?:名称|全称|编号|文号)(?:是什么)?(?:[，,。？！?]|$)",
            scan_value,
        )
    ):
        # The instrument is context; its single name or identifier is the answer.
        found.discard("document")
    if (
        "party" in found
        and "document" in found
        and re.search(
            r"(?:谁|何人|哪个(?:人|机构|部门|单位)).{0,16}"
            r"(?:负责)?(?:保存|保管|管理|持有|控制).{0,20}(?:记录|文件|材料)",
            scan_value,
        )
    ):
        # The record/file is the object being held; the only requested answer is
        # the custodian's identity.  Counting both lexical categories rejects an
        # ordinary atomic Chinese question such as “谁负责保存这些记录”.
        found.discard("document")
    if "document" in found and re.search(
            r"(?:学校|医院|医疗机构|第三方|机构|部门|单位).{0,30}"
            r"(?:留存|保存|保管|持有|控制).{0,24}(?:记录|文件|材料)",
            scan_value,
        ):
        # Named institutions identify the possible custodian/source of one
        # record-existence proposition.  Institution words such as 医疗机构 do
        # not additionally request the person's health status.
        found.discard("party")
        found.discard("health")
    if (
        "document" in found
        and len(found) > 1
        and re.search(
            r"(?:文件|材料|通知书|决定书|判决书|裁定书|报告)"
            r".{0,16}(?:送达|收到|签发|作出|提交|确认).{0,12}"
            r"(?:时间|日期|方式|接收人|收件人|签字|状态|是否)",
            scan_value,
        )
    ):
        # The document identifies the event whose one delivery/receipt attribute
        # is requested; it is not a second requested fact.
        found.discard("document")
    if (
        "document" in found
        and "reason" in found
        and re.search(
            r"(?:文件|材料|合同|协议|通知书|决定书|判决书|裁定书|申请)"
            r".{0,10}(?:理由|依据)",
            scan_value,
        )
    ):
        found.discard("document")
    if "reason" in found and re.search(
        r"所依据的.{0,12}(?:法律|法规|规章|规范|标准).{0,8}"
        r"(?:名称|编号)(?:[，,。？！?]|$)",
        scan_value,
    ):
        found.discard("reason")
    if "reason" in found and re.search(
        r"所依据的.{0,20}(?:法律|法规|规章|政策|规范性文件).{0,12}"
        r"(?:文件|规定|意见|办法)",
        scan_value,
    ):
        # “所依据的” links the requested document attribute to an act; it does
        # not ask for a second free-standing reason.
        found.discard("reason")
    if (
        "reason" in found
        and "name_or_identifier" in found
        and re.search(
            r"所依据的.{0,16}(?:文件|材料|文书|资料).{0,6}"
            r"(?:名称|全称|编号|文号)(?:是什么)?(?:[，,。？！?]|$)",
            scan_value,
        )
    ):
        # In “所依据的文件或资料名称”, 依据 is a relation that identifies
        # which instrument is being named; the client still supplies one atomic
        # attribute (the instrument identifier), not a separate free-form reason.
        # Keep bundles such as “名称和具体内容” rejected through the remaining
        # name/content categories.
        found.discard("reason")
    if (
        "party" in found
        and len(found) > 1
        and re.search(
            r"(?:接收人|收件人|签署人|申请人).{0,10}(?:签字)?(?:时间|日期|方式|状态)",
            scan_value,
        )
    ):
        found.discard("party")
    if (
        "document" in found
        and len(found) > 1
        and re.search(
            r"(?:签署|订立|生效|解除|终止).{0,16}(?:合同|协议)"
            r".{0,8}(?:时间|日期|地点|方式|主体)",
            scan_value,
        )
    ):
        found.discard("document")
    if (
        "document" in found
        and len(found) > 1
        and re.search(
            r"(?:合同|协议).{0,12}(?:签署|订立|生效|解除|终止)"
            r".{0,8}(?:时间|日期|地点|方式|主体)",
            scan_value,
        )
    ):
        found.discard("document")
    if (
        "document" in found
        and "result" in found
        and re.search(r"(?:效果|结果).{0,10}(?:报告|记录|文件|资料)", scan_value)
    ):
        found.discard("result")
    if re.search(
        r"(?:购买|销售|支付).{0,14}(?:合同|协议).{0,16}(?:中|关于)",
        scan_value,
    ):
        # The transaction identifies the document; the requested attribute is the
        # clause's function, use, wording, or method.
        found.discard("transaction")
    if (
        "transaction" in found
        and "content" in found
        and re.search(
            r"(?:购买|销售|交易).{0,20}(?:沟通|交谈|对话|陈述|说明).{0,8}(?:内容|原话)",
            scan_value,
        )
    ):
        # The transaction identifies which conversation is being recalled; the
        # answer still has one attribute, namely the communication content.
        found.discard("transaction")
    if re.search(
        r"(?:与|向|同).{0,16}(?:沟通|交谈|协商|对话).{0,30}"
        r"(?:具体)?(?:内容|时间|日期)",
        scan_value,
    ) or re.search(
        r"(?:沟通|交谈|协商|对话).{0,24}(?:具体)?(?:内容|时间|日期)",
        scan_value,
    ):
        # The transaction, dispute or progress phrase identifies the topic of one
        # communication attribute; it is not an independently requested result or
        # process.  Speaker/recipient identity remains governed by the party rules.
        found.discard("transaction")
        found.discard("result")
        found.discard("process")
    if "transaction" in found and re.search(
        r"(?:工资|报酬|款项|费用).{0,8}支付(?:周期|频率|时间|日期|方式)",
        scan_value,
    ):
        found.discard("transaction")
    if (
        "result" in found
        and "amount" in found
        and re.search(r"(?:损失|损害|伤害|赔偿).{0,8}(?:金额|数额|价值|费用)", scan_value)
    ):
        # “loss amount” is one scalar attribute; “loss” is not a second result
        # request merely because it lexically names the quantity being measured.
        found.discard("result")
    if re.search(
        r"(?:合同|协议).{0,16}(?:中|关于).{0,20}"
        r"(?:功能|用途|使用方式|描述)",
        scan_value,
    ):
        found.discard("document")
        found.discard("agreement")
    if "object_or_product" in found and re.search(
        r"(?:产品|商品|服务项目).{0,8}(?:功能|用途|使用方式|使用方法)",
        scan_value,
    ):
        # The product names the object whose single function or method is being
        # requested; it is not an independent answer dimension.
        found.discard("object_or_product")
    if "object_or_product" in found and re.search(
        r"(?:产品|商品|服务项目).{0,8}(?:使用|购买|交付).{0,6}(?:日期|时间)",
        scan_value,
    ):
        found.discard("object_or_product")
    position_term = r"(?:态度|主张|说法|陈述|辩解)"
    same_position_pair = re.search(
        rf"{position_term}.{{0,2}}(?:和|或|及|以及){position_term}", scan_value
    )
    separate_attribute_after_position = re.search(
        rf"{position_term}.{{0,3}}(?:和|及|以及|且).{{0,8}}"
        r"(?:是否|有无|约定|承诺|协议|文件|材料|金额|时间|行为|投入)",
        scan_value,
    )
    if (
        "position" in found
        and re.search(rf"对.{{1,30}}{position_term}", scan_value)
        and (same_position_pair or not separate_attribute_after_position)
    ):
        found.discard("agreement")
        found.discard("document")
    # Asking which documents exist is one evidence-inventory fact, even when examples
    # name several document types.
    if re.search(r"(?:有哪些|是否有|能否提供).{0,16}(?:文件|材料|合同|通知|决议)", scan_value):
        found.discard("content")
        if found <= {"document"}:
            return found
    # A single question cannot establish execution, content or timing for two
    # separately named instruments.  This catches modifier coordination such as
    # “签署保密和竞业协议” without treating the lexical word “和解协议” as a
    # conjunction or hard-coding any case/domain.
    if re.search(
        r"(?:签署|订立|解除|终止|收到|提交|提供).{0,12}"
        r"[^，,；;]{2,10}(?<!和解)(?:和|及|与)[^，,；;]{2,10}(?:协议|合同|文书|记录)",
        scan_value,
    ):
        found.update({"coordinated_instrument_left", "coordinated_instrument_right"})
    return found


def safe_factual_question_surface(
    fact_id: str,
    label: str,
    *,
    target_kind: str = "client_fact",
) -> tuple[str, str] | None:
    """Render one planner target through the same contract used after execution."""

    value = label.strip().rstrip("？?。.!！；;，,：:").strip()
    if not value:
        return None
    without_examples = re.sub(
        r"[（(](?:(?:如|例如|比如)[^）)]*|[^）)]*(?:/|、)[^）)]*)[）)]",
        "",
        value,
    ).strip()
    without_examples = re.split(
        r"(?<=[？?。；;，,])\s*(?:例如|比如|举例(?:来说)?|譬如)[，,:：]?",
        without_examples,
        maxsplit=1,
    )[0].strip().rstrip("？?。.!！；;，,：:").strip()
    # A planner target may deliberately retain a compound investigation concept
    # while the online lawyer asks only one of its observable attributes.  Skill
    # target replacement happens after the lawyer's own atomic-question repair,
    # so its deterministic renderer must enforce the same boundary instead of
    # turning the complete label back into a compound client question.  Preserve
    # genuine relational targets (for example ``A与B的对应关系``); their two nouns
    # define one observable relation rather than two primary questions.
    atomic_units = visible_target_atomic_units(without_examples)
    if not atomic_units:
        return None
    relational_target = bool(
        re.search(r"(?:关系|比例|对应|匹配|差额|联系|关联)(?:情况)?$", without_examples)
    )
    first_atomic_unit = atomic_units[0] if atomic_units else ""
    # Never skip an unsafe or fragmentary first unit and silently ask a later
    # attribute: that would change the visible target's rank semantics.  A skill
    # operation may use the first independently askable literal unit or remain a
    # no-op; the frozen lawyer remains responsible for any richer decomposition.
    candidates = (
        [first_atomic_unit]
        if len(atomic_units) > 1 and not relational_target
        else [without_examples]
    )
    for surface_label in dict.fromkeys(candidates):
        direct_question = None
        if surface_label.endswith(("？", "?")) or re.search(
            r"(?:是否|有无|为什么|为何|哪里|哪些|什么|如何|怎么|多少|何时|什么时候)",
            surface_label,
        ):
            direct_question = surface_label.rstrip("？?") + "？"
        content = direct_question or (
            f"关于{surface_label}，请说明您亲历或现有文件能够确认的一项具体事实？"
            if target_kind != "evidence_or_third_party"
            else f"关于{surface_label}，请确认目前能否提供相应材料或核验线索？"
        )
        action = StructuredAction(
            action_type="ask",
            target_type="fact",
            target_id=fact_id,
            expected_information=surface_label,
            content=content,
        )
        if not action_question_quality_violations(action):
            return surface_label, content
    return None


def safe_factual_fallback(state: ConsultationState) -> StructuredAction:
    """Build a deterministic, case-state-grounded question after failed repairs."""

    # The planner already stores targets in its visible-input value order.
    # Preserve that prior here too; an English join key is not a consultation
    # value signal, even on this fail-closed path.
    withheld_target_ids = {
        interaction.target_id
        for interaction in state.interactions
        if interaction.response_kind == "withheld" and interaction.target_id
    }
    unresolved = [
        fact
        for fact in state.facts
        if fact.status in {"unknown", "disputed"}
        and fact.fact_id not in state.asked_targets
        # A fallback is a transport safety mechanism, not a consultation policy.
        # It must not invent a trust-repair retry after the client withheld. A later
        # model action may still retry that open target with a materially different,
        # ordinarily validated question.
        and fact.fact_id not in withheld_target_ids
        and fact.fact_id not in NON_SUBSTANTIVE_FACT_IDS
    ]
    unresolved = [
        fact
        for fact in unresolved
        if factual_target_is_question_safe(fact.fact_id, fact.label)
        and safe_factual_question_surface(
            fact.fact_id,
            fact.label,
            target_kind=fact.target_kind,
        )
        is not None
        and not any(
            re.sub(r"[\W_]+", "", fact.label).lower()
            in re.sub(r"[\W_]+", "", interaction.question).lower()
            for interaction in state.interactions
        )
    ]
    if unresolved:
        fact = unresolved[0]
        rendered = safe_factual_question_surface(
            fact.fact_id,
            fact.label,
            target_kind=fact.target_kind,
        )
        assert rendered is not None
        surface_label, content = rendered
        return StructuredAction(
            action_type="ask" if fact.status == "unknown" else "clarify",
            target_type="fact",
            target_id=fact.fact_id,
            reason="policy_contract_safe_fallback",
            expected_information=surface_label,
            content=content,
            confidence=1.0,
        )
    # If visible substantive facts already support a cautious conditional memo,
    # ending with ``final`` is the safe operation.  Returning ``abstain`` here used
    # to defeat StopGate's conditional-memo redirect and converted valid terminal
    # model outputs into systematic abstentions.
    if state.substantive_fact_count:
        return StructuredAction(
            action_type="final",
            target_type="session",
            reason="safe_fallback_conditional_memo_available",
            expected_information="",
            content="",
            confidence=1.0,
        )
    # A generic session-level question has no tracked fact target, cannot be marked
    # unavailable, and pressures the client for information outside the case record.
    # End explicitly; the memo preserves unresolved points for later verification.
    return StructuredAction(
        action_type="abstain",
        target_type="session",
        reason="safe_fallback_no_grounded_unresolved_target",
        expected_information="",
        content="当前没有可安全继续追问且尚未问过的具体事实目标，停止继续追问并保留待核验事项。",
        confidence=1.0,
    )


def render_action(action: StructuredAction, state: ConsultationState) -> str:
    label_by_id = {
        "event_time": "与权利义务有关的关键时间",
        "client_name": "与案件有关的当事人身份及角色",
        "opening_statement": "尚未说明的案件经过",
        "case_type": "争议涉及的具体行政或民事行为",
        "dispute_type": "双方具体争议",
        "issue_description": "需要解决的具体问题",
        "dispute_details": "纠纷的具体经过",
    }
    content = action.content.strip()
    if content:
        for fact_id, human_label in label_by_id.items():
            content = content.replace(fact_id, human_label)
        if not re.search(r"[a-z]+_[a-z_]+", content):
            return content
    label = next(
        (fact.label for fact in state.facts if fact.fact_id == action.target_id),
        label_by_id.get(action.target_id or "", "这一关键情况"),
    )
    if re.search(r"[a-z]+_[a-z_]+", label):
        label = label_by_id.get(action.target_id or "", "这一关键情况")
    question = {
        "ask": f"关于{label}，您能说明一项亲历或文件可确认的具体事实吗？",
        "clarify": f"为避免理解偏差，关于{label}，请澄清一项可确认的具体事实？",
        "verify": f"关于{label}，您是否有一份材料可以核实？",
        "summarize": f"请确认我对{label}的这一项事实理解是否准确？",
    }.get(
        action.action_type,
        f"关于{label}，您能说明一项亲历或文件可确认的具体事实吗？",
    )
    return question


def executable_fallback_can_repair(violation: str) -> bool:
    """Return whether an executable guard can safely repair this policy violation."""

    return (
        violation
        in {
            "generic_or_abstract_question",
            "nonterminal_action_missing_content",
            "question_requests_legal_judgment_from_client",
            "multiple_primary_questions",
            "excessive_phrase_repetition",
            "factual_action_missing_target_id",
            "repeated_question_text",
        }
        or violation.startswith("factual_target_missing_from_state:")
        or violation.startswith("target_not_available:")
        or violation.startswith("ask_target_not_unresolved:")
        or violation.startswith("repeated_ask_target:")
        or violation.startswith("repeated_fact_target:")
    )
