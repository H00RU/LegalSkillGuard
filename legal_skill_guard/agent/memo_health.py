"""Deterministic provenance and caution checks for preliminary legal memos."""

from __future__ import annotations

import re

REQUIRED_HEADINGS = ("案情概要", "关键事实", "法律问题", "风险评估", "下一步建议")
TYPED_FACT_LEDGER_HEADING = "**结构化会话事实状态（确定性记录）**"
TYPED_FACT_LEDGER_START = "<!-- typed_fact_ledger -->"
TYPED_FACT_LEDGER_END = "<!-- /typed_fact_ledger -->"


def _without_typed_fact_ledger(memo: str) -> str:
    """Remove the deterministic evidence block while retaining model analysis."""

    before, marker, tail = memo.partition(TYPED_FACT_LEDGER_START)
    if not marker:
        return memo
    _, end_marker, after = tail.partition(TYPED_FACT_LEDGER_END)
    if not end_marker:
        return before
    return before.rstrip() + "\n" + after.lstrip()
PROCEDURAL_ACTIONS = (
    "提起诉讼",
    "申请复议",
    "提起上诉",
    "申请仲裁",
    "申请鉴定",
    "司法鉴定",
    "证据保全",
    "财产保全",
    "申请强制执行",
)
CAUTION_MARKERS = (
    "若",
    "如果",
    "可能",
    "需",
    "需要",
    "尚",
    "有待",
    "取决于",
    "不能",
    "无法",
    "初步",
    "仅凭",
    "在核实",
)
OPTION_MARKERS = ("可", "考虑", "必要时", "视情况", "咨询", "核实后", "在核实")
PROCEDURAL_READINESS_DIMENSIONS = (
    "法域",
    "管辖",
    "程序状态",
    "适用条件",
    "启动条件",
    "条件",
    "期限",
    "路径",
)
LAW_ARTICLE_PATTERN = re.compile(
    r"第[〇零一二三四五六七八九十百千万0-9]{1,12}条"
    r"(?:之[〇零一二三四五六七八九十百千万0-9]{1,4})?"
)
CASE_NUMBER_PATTERN = re.compile(r"[（(][12][0-9]{3}[）)][^，。；;\s]{1,24}号")
PROCEDURAL_DEADLINE_PATTERN = re.compile(
    r"[〇零一二三四五六七八九十百千万0-9]{1,8}(?:个)?(?:工作)?(?:日|天|月|年)内"
)

_REPORTER_ACTORS = (
    "被申请人",
    "申请人",
    "公安机关",
    "行政机关",
    "保险公司",
    "用人单位",
    "相对方",
    "客户",
    "对方",
    "平台",
    "医院",
    "公司",
    "员工",
    "丈夫",
    "妻子",
    "原告",
    "被告",
    "法院",
)
_REPORTER_ACTOR_PATTERN = "(?:" + "|".join(_REPORTER_ACTORS) + ")"
_DIRECT_REPORTER_PATTERN = re.compile(
    rf"^(?P<actor>{_REPORTER_ACTOR_PATTERN})"
    r"(?:本人)?(?:明确|曾|已|当时|目前)?"
    r"(?P<verb>"
    r"答复称|回复称|声称|自称|辩称|陈述|表示|解释|"
    r"确认|承认|否认|反映|介绍|提到|指出|认定|"
    r"抗辩|主张|认为|所称|说|称"
    r")(?P<content>.*)$"
)
_WRAPPED_REPORTER_PATTERN = re.compile(
    rf"^据(?P<actor>{_REPORTER_ACTOR_PATTERN})"
    r"(?P<verb>陈述|转述|介绍|反映)"
    r"(?:[，,: ：]\s*)?(?P<content>.*)$"
)


def _memo_clauses(text: str) -> list[str]:
    """Split prose at clause boundaries while preserving comma attribution."""

    return [item.strip() for item in re.split(r"[。；;！!?？\n]+", text) if item.strip()]


def _clause_reporter(clause: str) -> tuple[str, str, str] | None:
    """Return a clause-leading reporting actor, verb, and reported content.

    Reporting is a grammatical construction at the beginning of a clause, not
    the occurrence of a character within a nearby noun.  Anchoring here prevents
    ``客户……加油站名称`` and ``经办人员职称`` from being interpreted as
    the verb ``称`` without an open-ended list of preceding characters.
    """

    value = clause.strip()
    value = re.sub(r"^(?:[-*]\s*|\d+[.、]\s*)", "", value)
    value = re.sub(
        r"^\*{1,2}(?:案情概要|关键事实|法律问题|风险评估|下一步建议)\*{1,2}\s*",
        "",
        value,
    ).lstrip("：: ")
    wrapped = _WRAPPED_REPORTER_PATTERN.match(value)
    if wrapped:
        remainder = wrapped.group("content").lstrip("，,: ：")
        nested = _DIRECT_REPORTER_PATTERN.match(remainder)
        if nested:
            return (
                nested.group("actor"),
                nested.group("verb"),
                nested.group("content").lstrip("，,: ："),
            )
        return wrapped.group("actor"), wrapped.group("verb"), remainder
    # A factual heading can precede the actual reporter in the same sentence
    # (``客户咨询保险理赔，客户认为……``).  A comma is a phrase boundary,
    # so each comma-delimited segment may begin a reporting construction.  We do
    # not search inside a segment: ``建议客户补充公司全称`` therefore remains a
    # non-attribution advice clause.
    for segment in (item.strip() for item in re.split(r"[，,]", value) if item.strip()):
        direct = _DIRECT_REPORTER_PATTERN.match(segment)
        if direct:
            return (
                direct.group("actor"),
                direct.group("verb"),
                direct.group("content").lstrip("，,: ："),
            )
    return None


def _reporter_introduces_concrete_fact(reporter: tuple[str, str, str]) -> bool:
    """Distinguish a reported fact from a reference to an open legal position."""

    _, verb, content = reporter
    if verb not in {"主张", "认为", "所称"}:
        return True
    return bool(
        re.match(
            r"(?:其|自己|本人|已经|已|曾|未|没有|不存在|[，,:：])",
            content,
        )
    )


def _is_client_reporter(clause: str) -> bool:
    reporter = _clause_reporter(clause)
    return reporter is not None and reporter[0] == "客户"

UNAVAILABLE_ACTION_CONCEPTS: dict[str, re.Pattern[str]] = {
    "authority_report": re.compile(r"报案|报警|举报|投案|自首|向.{0,10}(?:公安|警方).{0,6}报告"),
    "seek_support": re.compile(r"求助|寻求.{0,6}帮助|联系.{0,8}(?:社区|妇联|工会)"),
    "medical_treatment": re.compile(
        r"治疗|就医|就诊|住院|送医|救治|"
        r"(?:去|到|前往).{0,4}(?:医院|医疗机构)|"
        r"(?:医院|医疗机构).{0,6}(?:检查|诊查|看病)"
    ),
    "protective_response": re.compile(r"制止|阻止|保护"),
    "payment": re.compile(r"付款|支付|还款|偿还|缴纳|垫付|结算"),
    "signing": re.compile(r"签署|签订|续签|续订"),
    "notice": re.compile(r"通知|送达|收到"),
    "disclosure": re.compile(r"告知"),
    # ``未兑现/未履行承诺`` negates performance, not the existence of a
    # promise.  Keeping those predicates out of the broad agreement concept
    # prevents an unavailable answer about the promise's *content* from erasing
    # a separately visible claim that the promise was not performed.
    "agreement": re.compile(r"同意|拒绝|认可|(?<!兑现)(?<!履行)承诺"),
    "filing": re.compile(r"申请|起诉|立案|仲裁|复议|执行"),
    "communication": re.compile(r"沟通|协商|交涉|联系|咨询"),
    "possession": re.compile(r"持有|拥有|取得|保留"),
    "work_or_performance": re.compile(r"工作|履行|供货|交付|使用|实施"),
    # An unavailable answer to a document-content question does not establish
    # that the document omitted the requested item.  This is a content-polarity
    # error rather than the possession/notice errors covered above (for example,
    # “现有信息里没有，需要核实” -> “医疗证明未列明诊断记录”).
    "document_content": re.compile(r"列明|列出|包含|记载|载明|写明|注明"),
    "document_submission": re.compile(r"提交|提供|出示"),
    "document_issuance": re.compile(r"出具|开具|制发"),
    "witness_availability": re.compile(
        r"证人|目击者|邻居|亲属|其他人.{0,8}(?:证明|作证)|人员.{0,6}(?:证明|作证)"
    ),
}
UNAVAILABLE_CONTEXT_ANCHORS = re.compile(
    r"公安机关|公安|警方|社区|妇联|工会|医疗机构|医院|法院|仲裁|"
    r"客户|本人|员工|公司|丈夫|妻子|对方|合同|协议|货款|费用|社保|"
    r"许可证|通知|材料|房屋|房产|数据|政府|软件"
)
NEGATIVE_FACT_PATTERN = re.compile(
    r"(?:尚未|尚无|并未|并无|未曾|从未|不存在|没有|"
    r"无(?!法|需|须|效|权|关|论|从|异议)|未)"
    r"(?!核实|核验|确认|查明|明确|获知|了解|掌握|"
    r"经(?:同意|授权)|获(?:得)?(?:同意|授权)|取得(?:同意|授权))"
)
# A verbatim unanswered question may itself contain a negative predicate (for
# example, ``是否患病但未告知？``).  In an explicitly labelled, interrogative
# pending-work entry that predicate is the object of verification, not a memo
# assertion.  Keep this narrow: ordinary prose, entries without a question mark,
# and negative statements followed by unrelated caution remain subject to the
# unsupported-negative gate.
EXPLICIT_UNRESOLVED_QUESTION_ENTRY_PATTERN = re.compile(
    r"^(?:(?:[-*]|\d+[.、])\s*)?"
    r"(?:待向客户补充核实|待客户补充核实的问题|尚待客户补充核实的问题)"
    r"\s*[：:]\s*.+[？?]$"
)
DISTINCTIVE_UNAVAILABLE_CONCEPTS = {
    "authority_report",
    "seek_support",
    "medical_treatment",
    "witness_availability",
}
UNAVAILABLE_NEUTRAL_LABELS = {
    "authority_report": "报案或向有关机关报告的情况",
    "seek_support": "向相关机构求助的情况",
    "medical_treatment": "就医治疗情况",
    "protective_response": "制止或保护情况",
    "payment": "付款或费用承担情况",
    "signing": "签署或续签情况",
    "notice": "通知或送达情况",
    "disclosure": "信息告知或披露情况",
    "agreement": "同意、拒绝或承诺情况",
    "filing": "申请或程序启动情况",
    "communication": "沟通协商情况",
    "possession": "持有或取得情况",
    "work_or_performance": "工作或履行情况",
    "document_content": "文件所载具体内容",
    "document_submission": "文件提交或提供情况",
    "document_issuance": "文件出具或开具情况",
    "witness_availability": "证人或其他证明来源情况",
    "generic_question_overlap": "该未获回答问题所涉事实",
}

NEGATIVE_CONCEPT_TERMS: dict[str, tuple[str, ...]] = {
    "authority_report": ("报案", "报警", "举报", "投案", "自首"),
    "seek_support": ("求助", "寻求帮助"),
    "medical_treatment": (
        "治疗",
        "就医",
        "就诊",
        "住院",
        "送医",
        "救治",
        "去医院",
        "到医院",
        "前往医院",
        "医院检查",
        "医疗检查",
    ),
    "protective_response": ("制止", "阻止", "保护"),
    "payment": ("付款", "支付", "还款", "偿还", "缴纳", "垫付", "结算"),
    "signing": ("签署", "签订", "续签", "续订"),
    "notice": ("通知", "送达", "收到"),
    "disclosure": ("告知",),
    "agreement": ("同意", "拒绝", "认可", "承诺"),
    "filing": ("申请", "起诉", "立案", "仲裁", "复议", "执行"),
    "communication": ("沟通", "协商", "交涉", "联系", "咨询"),
    "possession": ("持有", "拥有", "取得", "保留"),
    "work_or_performance": ("工作", "履行", "供货", "交付", "使用", "实施"),
    "document_content": ("列明", "列出", "包含", "记载", "载明", "写明", "注明"),
    "document_submission": ("提交", "提供", "出示"),
    "document_issuance": ("出具", "开具", "制发"),
    "witness_availability": ("证人", "目击者", "邻居", "亲属", "作证"),
}

EXTERNAL_ACTOR_PATTERNS: dict[str, re.Pattern[str]] = {
    "公安机关": re.compile(r"公安(?:机关)?|警方"),
    "法院": re.compile(r"法院"),
    "仲裁机构": re.compile(r"仲裁(?:机构|委|委员会)?"),
    "行政机关": re.compile(r"行政机关|政府部门|监管部门"),
    "医疗机构": re.compile(r"医院|医疗机构"),
    "保险公司": re.compile(r"保险公司"),
}
COMPLETED_EXTERNAL_ACTION_PATTERN = re.compile(
    r"(?:已经|已|曾)?(?:查明|认定|确认|作出|出具|开具|受理|立案|处理|维持|拒赔)"
)
PENDING_EXTERNAL_ACTION_PATTERN = re.compile(
    r"(?:核实|查明|确认|认定|调查|处理|出具|开具)"
)
COMPLETED_EVENT_STEMS = (
    "治安处罚",
    "行政处罚",
    "刑事立案",
    "立案",
    "受理",
    "拒赔",
    "解除",
    "支付",
    "签署",
    "认定",
    "确认",
    "查明",
)

OBLIGATION_ACTION_STEMS = (
    "申报",
    "告知",
    "披露",
    "支付",
    "赔偿",
    "缴纳",
    "返还",
    "归还",
    "提供",
    "配合",
    "负责",
    "承担",
    "履行",
)
TEMPORAL_EVENT_ANCHORS = (
    "投保",
    "结婚",
    "婚姻登记",
    "事故",
    "签约",
    "签订",
    "签署",
    "入职",
    "离职",
    "确诊",
    "付款",
    "支付",
    "交付",
    "收货",
    "起诉",
    "申请",
    "通知",
    "报警",
    "治疗",
    "住院",
    "购买",
    "施工",
    "离婚",
)


def client_position_reversal_violations(
    memo: str, dialogue: list[tuple[str, str]]
) -> list[str]:
    """Reject an attributed memo sentence that reverses the client's position.

    This deliberately checks only an observable polarity pair: a client statement
    that they may/should/must bear an obligation to perform a named action versus
    a memo attribution saying the client believes that action is unnecessary (or
    the reverse).  It does not adjudicate which legal position is correct and does
    not inspect the lawyer's questions.
    """

    positive_actions: set[str] = set()
    negative_actions: set[str] = set()
    for _, answer in dialogue:
        for sentence in re.split(r"[。；;！？!?]", answer):
            for action in OBLIGATION_ACTION_STEMS:
                if action not in sentence:
                    continue
                if re.search(
                    rf"(?:可能|也许|或许)?(?:仍|也)?(?:负有|具有|需要|应当|应该|必须)"
                    rf"[^。；;]{{0,28}}{re.escape(action)}|"
                    rf"{re.escape(action)}[^。；;]{{0,20}}(?:义务|责任)",
                    sentence,
                ) and not re.search(
                    rf"(?:无需|无须|不需要|不必|不负有|没有)[^，,。；;]{{0,20}}"
                    rf"{re.escape(action)}",
                    sentence,
                ):
                    positive_actions.add(action)
                if re.search(
                    rf"(?:无需|无须|不需要|不必|不负有|没有)[^，,。；;]{{0,20}}"
                    rf"{re.escape(action)}",
                    sentence,
                ):
                    negative_actions.add(action)

    issues: list[str] = []
    for sentence in _memo_clauses(memo):
        if not _is_client_reporter(sentence):
            continue
        for action in sorted(positive_actions):
            if re.search(
                rf"(?:无需|无须|不需要|不必|不负有|没有)[^，,。；;]{{0,20}}"
                rf"{re.escape(action)}",
                sentence,
            ):
                issues.append(f"client_position_reversed:{action}")
        for action in sorted(negative_actions):
            if re.search(
                rf"(?:负有|具有|需要|应当|应该|必须)[^。；;]{{0,28}}"
                rf"{re.escape(action)}|{re.escape(action)}[^。；;]{{0,20}}(?:义务|责任)",
                sentence,
            ) and not re.search(
                rf"(?:无需|无须|不需要|不必|不负有|没有)[^，,。；;]{{0,20}}"
                rf"{re.escape(action)}",
                sentence,
            ):
                issues.append(f"client_position_reversed:{action}")
    return list(dict.fromkeys(issues))


def neutralize_client_position_reversals(
    memo: str, dialogue: list[tuple[str, str]]
) -> tuple[str, list[str]]:
    """Replace only a reversed client-position sentence with its visible source.

    The replacement is extractive: it copies one client answer verbatim and adds
    attribution.  It does not decide whether the client's legal belief is correct
    or generate a different position.
    """

    pieces = re.split(r"([。；;！？!?\n])", memo)
    changes: list[str] = []
    for index in range(0, len(pieces), 2):
        clause = pieces[index]
        violations = client_position_reversal_violations(clause, dialogue)
        if not violations:
            continue
        action = violations[0].split(":", 1)[1]
        source = next(
            (
                answer.strip().rstrip("。；;！？!?")
                for _, answer in dialogue
                if action in answer
                and re.search(r"(?:义务|责任|无需|无须|不需要|不必|负有|应当|应该|必须)", answer)
            ),
            None,
        )
        if source is None:
            continue
        prefix = ""
        numbered = re.match(r"^(\s*(?:[-*]|\d+[.、])\s*)", clause)
        if numbered:
            prefix = numbered.group(1)
        pieces[index] = f"{prefix}据客户陈述，{source}"
        changes.append(action)
    return "".join(pieces), list(dict.fromkeys(changes))


def known_temporal_answer_recast_as_unknown_violations(
    memo: str, dialogue: list[tuple[str, str]]
) -> list[str]:
    """Reject erasing an explicit before/after answer into attributed uncertainty.

    Evidence may remain independently unverified, but the memo cannot say the
    client failed to state a temporal relation that the visible answer states
    explicitly.  Requiring the same bounded event anchor keeps this from treating
    ordinary evidence-calibration language as a contradiction.
    """

    explicit_anchors = {
        anchor
        for _, answer in dialogue
        for anchor in TEMPORAL_EVENT_ANCHORS
        if re.search(rf"{re.escape(anchor)}(?:之)?(?:前|后)", answer)
    }
    issues: list[str] = []
    if not explicit_anchors:
        return issues
    for sentence in _memo_clauses(memo):
        if not _is_client_reporter(sentence):
            continue
        recast_unknown = bool(
            re.search(
                r"(?:未|没有)(?:明确|确认|说明|查明)|"
                r"(?:不清楚|无法确认)|"
                r"(?:时间|先后|是否).{0,16}(?:尚待|有待|需要|需)(?:核实|确认|查明)",
                sentence,
            )
        )
        if not recast_unknown:
            continue
        for anchor in sorted(explicit_anchors):
            if anchor in sentence:
                issues.append(f"known_temporal_answer_recast_as_unknown:{anchor}")
    return list(dict.fromkeys(issues))


def neutralize_known_temporal_answer_recasts(
    memo: str, dialogue: list[tuple[str, str]]
) -> tuple[str, list[str]]:
    """Restore an explicit client before/after statement by extractive replacement."""

    pieces = re.split(r"([。；;！？!?\n])", memo)
    changes: list[str] = []
    for index in range(0, len(pieces), 2):
        clause = pieces[index]
        violations = known_temporal_answer_recast_as_unknown_violations(clause, dialogue)
        if not violations:
            continue
        anchor = violations[0].split(":", 1)[1]
        source = next(
            (
                answer.strip().rstrip("。；;！？!?")
                for _, answer in dialogue
                if re.search(rf"{re.escape(anchor)}(?:之)?(?:前|后)", answer)
            ),
            None,
        )
        if source is None:
            continue
        prefix = ""
        numbered = re.match(r"^(\s*(?:[-*]|\d+[.、])\s*)", clause)
        if numbered:
            prefix = numbered.group(1)
        pieces[index] = f"{prefix}据客户陈述，{source}"
        changes.append(anchor)
    return "".join(pieces), list(dict.fromkeys(changes))


def known_external_action_recast_as_pending_violations(
    memo: str, dialogue: list[tuple[str, str]]
) -> list[str]:
    """Reject changing a reported completed institutional act into a pending act.

    A memo may say that the client's account or supporting material still needs
    independent verification.  It may not instead say that the named institution
    still needs to perform the factual act which the client expressly reported as
    completed (for example, ``公安已经查明`` -> ``尚待公安机关核实``).
    """

    completed_actors: set[str] = set()
    for _, answer in dialogue:
        for sentence in re.split(r"[。；;！？!?]", answer):
            for actor, pattern in EXTERNAL_ACTOR_PATTERNS.items():
                match = pattern.search(sentence)
                if match is None:
                    continue
                tail = sentence[match.end() : match.end() + 32]
                if COMPLETED_EXTERNAL_ACTION_PATTERN.search(tail):
                    completed_actors.add(actor)

    issues: list[str] = []
    for sentence in re.split(r"[。；;！？!?\n]", memo):
        for actor in sorted(completed_actors):
            pattern = EXTERNAL_ACTOR_PATTERNS[actor]
            actor_match = pattern.search(sentence)
            if actor_match is None:
                continue
            pending_before_actor = re.search(
                rf"(?:尚待|有待|仍需|需要|需).{{0,10}}"
                rf"(?:{pattern.pattern}).{{0,12}}{PENDING_EXTERNAL_ACTION_PATTERN.pattern}",
                sentence,
            )
            actor_pending_after = re.search(
                rf"(?:{pattern.pattern}).{{0,10}}(?:尚待|有待|仍需|需要|需)"
                rf".{{0,12}}{PENDING_EXTERNAL_ACTION_PATTERN.pattern}",
                sentence,
            )
            if pending_before_actor or actor_pending_after:
                issues.append(f"known_external_action_recast_as_pending:{actor}")
    return list(dict.fromkeys(issues))


def neutralize_known_external_action_recasts(
    memo: str, dialogue: list[tuple[str, str]]
) -> tuple[str, list[str]]:
    """Restore the visible client report when an institution's act is reversed."""

    pieces = re.split(r"([。；;！？!?\n])", memo)
    changes: list[str] = []
    for index in range(0, len(pieces), 2):
        clause = pieces[index]
        violations = known_external_action_recast_as_pending_violations(clause, dialogue)
        if not violations:
            continue
        actor = violations[0].split(":", 1)[1]
        actor_pattern = EXTERNAL_ACTOR_PATTERNS[actor]
        source = next(
            (
                answer.strip().rstrip("。；;！？!?")
                for _, answer in dialogue
                if actor_pattern.search(answer)
                and COMPLETED_EXTERNAL_ACTION_PATTERN.search(answer)
            ),
            None,
        )
        if source is None:
            continue
        prefix = ""
        numbered = re.match(r"^(\s*(?:[-*]|\d+[.、])\s*)", clause)
        if numbered:
            prefix = numbered.group(1)
        pieces[index] = f"{prefix}据客户陈述，{source}；该陈述及相关材料尚未独立核验"
        changes.append(actor)
    return "".join(pieces), list(dict.fromkeys(changes))


def known_completed_event_recast_as_uncertain_violations(
    memo: str, dialogue: list[tuple[str, str]]
) -> list[str]:
    """Reject downgrading a reported completed event into a possible event.

    Independent verification remains allowed.  The memo may not attribute to the
    client that an event merely *might* occur when the visible client answer says
    it already occurred (for example, ``已被治安处罚`` -> ``可能构成治安处罚``).
    """

    completed = {
        stem
        for _, answer in dialogue
        for stem in COMPLETED_EVENT_STEMS
        if re.search(rf"(?:已经|已|曾经|曾).{{0,4}}{re.escape(stem)}", answer)
    }
    issues: list[str] = []
    for sentence in re.split(r"[。；;！？!?\n]", memo):
        for stem in sorted(completed):
            escaped = re.escape(stem)
            possible_recast = re.search(
                rf"(?:可能|也许|或许)(?:会|被|受到|构成)?[^。；;]{{0,8}}{escaped}",
                sentence,
            )
            unknown_recast = re.search(
                rf"(?:尚待|有待|仍需|需要|需)(?:核实|确认|查明)"
                rf"[^。；;]{{0,12}}(?:是否)?[^。；;]{{0,8}}{escaped}",
                sentence,
            )
            if possible_recast or unknown_recast:
                issues.append(f"known_completed_event_recast_as_uncertain:{stem}")
    return list(dict.fromkeys(issues))


def neutralize_known_completed_event_recasts(
    memo: str, dialogue: list[tuple[str, str]]
) -> tuple[str, list[str]]:
    """Restore the visible client report when a completed event is downgraded."""

    pieces = re.split(r"([。；;！？!?\n])", memo)
    changes: list[str] = []
    for index in range(0, len(pieces), 2):
        clause = pieces[index]
        violations = known_completed_event_recast_as_uncertain_violations(
            clause, dialogue
        )
        if not violations:
            continue
        stem = violations[0].split(":", 1)[1]
        source = next(
            (
                answer.strip().rstrip("。；;！？!?")
                for _, answer in dialogue
                if re.search(
                    rf"(?:已经|已|曾经|曾).{{0,4}}{re.escape(stem)}", answer
                )
            ),
            None,
        )
        if source is None:
            continue
        prefix = ""
        numbered = re.match(r"^(\s*(?:[-*]|\d+[.、])\s*)", clause)
        if numbered:
            prefix = numbered.group(1)
        pieces[index] = f"{prefix}据客户陈述，{source}；该陈述及相关材料尚未独立核验"
        changes.append(stem)
    return "".join(pieces), list(dict.fromkeys(changes))


def question_only_negative_claim_violations(
    memo: str, dialogue: list[tuple[str, str]]
) -> list[str]:
    """Reject negative facts copied from a lawyer's enumerated question.

    A client may answer only one member of a question's examples (for example,
    ``没有制止``).  The memo must not expand that into non-occurrence of every
    other action named by the lawyer (for example, no protection *or medical
    treatment*).  Only client answers—not lawyer wording—can ground negative case
    facts in the no-retrieval memo.
    """

    if not dialogue:
        return []
    supported_negative = {
        concept
        for _, answer in dialogue
        for concept, pattern in UNAVAILABLE_ACTION_CONCEPTS.items()
        if _negates_concept(answer, pattern)
    }
    lawyer_named = {
        concept
        for question, _ in dialogue
        for concept, pattern in UNAVAILABLE_ACTION_CONCEPTS.items()
        if _question_targets_concept(question, concept, pattern)
    }
    memo_negative = {
        concept
        for concept, pattern in UNAVAILABLE_ACTION_CONCEPTS.items()
        if _negates_concept(memo, pattern)
    }
    return [
        f"question_example_recast_as_negative:{concept}"
        for concept in sorted(memo_negative & lawyer_named - supported_negative)
    ]


def drop_question_only_coordinated_negative_examples(
    memo: str, dialogue: list[tuple[str, str]]
) -> tuple[str, list[str]]:
    """Delete only an unsupported coordinated item copied from a question.

    This deliberately cannot rewrite a standalone unsupported negative claim.  It
    only handles a syntactically separable tail such as ``未制止或送医`` ->
    ``未制止``; all other cases remain violations and require bounded regeneration.
    """

    violations = question_only_negative_claim_violations(memo, dialogue)
    concepts = [item.split(":", 1)[1] for item in violations]
    value = memo
    changed: list[str] = []
    for concept in concepts:
        terms = NEGATIVE_CONCEPT_TERMS.get(concept, ())
        if not terms:
            continue
        term_pattern = "|".join(re.escape(item) for item in sorted(terms, key=len, reverse=True))
        pattern = re.compile(
            rf"(?:、|或|及|和|以及)(?:并)?(?:未|没有|无)?"
            rf"(?:采取|进行|接受|得到)?(?:{term_pattern})(?:等行为)?"
        )
        rewritten, count = pattern.subn("", value)
        if count and rewritten != value:
            value = rewritten
            changed.append(concept)
    return value, changed


def neutralize_question_only_negative_claims(
    memo: str, dialogue: list[tuple[str, str]]
) -> tuple[str, list[str]]:
    """Replace a standalone question-derived negative with explicit uncertainty.

    The coordinated-tail normalizer above preserves a supported negative when only
    another item was copied from the lawyer's question.  A standalone unsupported
    clause has no such grounded core to retain.  Replacing only that punctuation-
    bounded clause with an unknown-status label removes the invented fact without
    selecting a different fact, legal rule, or outcome.
    """

    pieces = re.split(r"([，。；;\n])", memo)
    changes: list[str] = []
    for index in range(0, len(pieces), 2):
        clause = pieces[index]
        violations = question_only_negative_claim_violations(clause, dialogue)
        concepts = [item.split(":", 1)[1] for item in violations]
        if not concepts:
            continue
        labels = list(dict.fromkeys(UNAVAILABLE_NEUTRAL_LABELS[item] for item in concepts))
        prefix = ""
        numbered = re.match(r"^(\s*(?:[-*]|\d+[.、])\s*)", clause)
        if numbered:
            prefix = numbered.group(1)
        pieces[index] = prefix + "、".join(labels) + "尚待客户补充核实"
        changes.extend(concepts)
    return "".join(pieces), list(dict.fromkeys(changes))


def _negates_concept(text: str, concept_pattern: re.Pattern[str]) -> bool:
    """Return whether a factual negator directly governs this concept.

    One sentence may contain several events. Treating any ``未`` in that sentence
    as negating every mentioned event caused false positives such as ``若员工继续
    工作且未续签合同……实际工作时间待核实``: the negator governs signing, not
    work. Chinese factual negation normally precedes its predicate, so require the
    concept to occur shortly after the accepted negator and before a clause boundary.
    Epistemic predicates remain excluded by ``NEGATIVE_FACT_PATTERN`` itself.
    """

    for negative in NEGATIVE_FACT_PATTERN.finditer(text):
        if _negation_is_hypothetical_or_interrogative(text, negative.start()):
            continue
        suffix = text[negative.end() : negative.end() + 24]
        boundary = re.search(r"[，。；;！？!?]", suffix)
        scoped = suffix[: boundary.start()] if boundary else suffix
        if concept_pattern.search(scoped):
            return True
    return False


def _negation_is_hypothetical_or_interrogative(text: str, start: int) -> bool:
    """Exclude a conditional or open question from factual-negation gates.

    ``若该病史未被询问`` and ``是否存在未告知病史`` are calibrated
    legal analysis, not claims that an event did not happen.  The previous gate
    treated the surface ``未`` identically in all sections and consequently erased
    valid legal questions and risk conditions from otherwise grounded memos.
    """

    clause_start = max(
        text.rfind("。", 0, start),
        text.rfind("；", 0, start),
        text.rfind(";", 0, start),
        text.rfind("\n", 0, start),
    )
    prefix = text[clause_start + 1 : start]
    return bool(
        re.search(r"(?:若|如果|假如|假设|一旦)[^。；;\n]{0,48}$", prefix)
        or re.search(r"(?:是否|有无|能否|是不是)[^。；;\n]{0,32}$", prefix)
    )


_GENERIC_OVERLAP_STOP_PHRASES = (
    "客户",
    "请问",
    "请说明",
    "目前",
    "当前",
    "具体",
    "实际",
    "已经",
    "是否",
    "有无",
    "哪些",
    "什么",
    "怎么",
    "情况",
    "事实",
    "相关",
    "能够",
    "可以",
)


def _generic_overlap_text(value: str) -> str:
    normalized = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", value).lower()
    for phrase in _GENERIC_OVERLAP_STOP_PHRASES:
        normalized = normalized.replace(phrase, "")
    return normalized


def _longest_common_substring_length(left: str, right: str) -> int:
    """Return exact local overlap length for two short Chinese predicate strings."""

    previous = [0] * (len(right) + 1)
    longest = 0
    for left_char in left:
        current = [0] * (len(right) + 1)
        for index, right_char in enumerate(right, start=1):
            if left_char == right_char:
                current[index] = previous[index - 1] + 1
                longest = max(longest, current[index])
        previous = current
    return longest


def _generic_unavailable_negative_overlap(
    text: str, unavailable_questions: list[str]
) -> bool:
    """Catch an unknown-to-negative rewrite outside the named concept lexicon.

    The match is deliberately local to text governed by a factual negator.  It
    requires the clause's *first* post-negation predicate bigram and a
    five-character contiguous span from the same unavailable question.  Looking
    across the first six characters was too permissive: ``未询问慢性支气管炎``
    matched an unrelated unknown about medical records merely because both named
    the disease.  The named concept lexicon handles predicate synonyms; this
    generic safety net intentionally requires an exact predicate start.
    """

    normalized_questions = [_generic_overlap_text(item) for item in unavailable_questions]
    for negative in NEGATIVE_FACT_PATTERN.finditer(text):
        if _negation_is_hypothetical_or_interrogative(text, negative.start()):
            continue
        suffix = text[negative.end() : negative.end() + 32]
        boundary = re.search(r"[，。；;！？!?]", suffix)
        scoped = suffix[: boundary.start()] if boundary else suffix
        candidate = _generic_overlap_text(scoped)
        if len(candidate) < 5:
            continue
        predicate_bigram = candidate[:2]
        for question in normalized_questions:
            if (
                predicate_bigram in question
                and _longest_common_substring_length(candidate, question) >= 5
            ):
                return True
    return False


def _concept_question_matches_clause(
    question: str,
    clause: str,
    concept: str,
) -> bool:
    """Bind a negative predicate to the same unavailable target.

    A concept such as ``document_content`` is only a predicate family.  It is not
    an identity key: an unknown answer about a medical certificate must not erase
    a separately disclosed statement about an electronic health questionnaire.
    Prefer an explicit shared actor/object anchor; otherwise require a local
    four-character content span after generic wording and predicate terms are
    removed.  Highly distinctive event families remain safe without that span.
    """

    question_anchors = set(UNAVAILABLE_CONTEXT_ANCHORS.findall(question))
    clause_anchors = set(UNAVAILABLE_CONTEXT_ANCHORS.findall(clause))
    if question_anchors & clause_anchors:
        return True
    if concept in DISTINCTIVE_UNAVAILABLE_CONCEPTS:
        return True

    question_value = _generic_overlap_text(question)
    clause_value = _generic_overlap_text(clause)
    for term in NEGATIVE_CONCEPT_TERMS.get(concept, ()):
        question_value = question_value.replace(term, "")
        clause_value = clause_value.replace(term, "")
    for filler in (
        "您",
        "其",
        "该",
        "客户称",
        "据客户转述",
        "并",
        "尚",
        "曾",
        "时",
        "中",
        "的",
        "了",
    ):
        question_value = question_value.replace(filler, "")
        clause_value = clause_value.replace(filler, "")
    return _longest_common_substring_length(question_value, clause_value) >= 4


WITHHELD_TARGET_PREDICATES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("signing", re.compile(r"签署|签字|签订")),
    ("illness", re.compile(r"患有|患病|既往病史|病史")),
    ("cause", re.compile(r"原因")),
    ("reason", re.compile(r"事由|理由")),
    ("intent", re.compile(r"表达|意愿")),
    ("evidence", re.compile(r"证明|证人|目击|邻居|亲属")),
    ("document_content", re.compile(r"包含|列明|记载|写明|注明")),
    ("document_transfer", re.compile(r"提交|提供|出示|取得|持有")),
    ("opposing_basis", re.compile(r"指出|说明|拒赔理由|拒赔依据")),
    ("disclosure", re.compile(r"告知|披露")),
    ("decision", re.compile(r"作出|决定|处理结果")),
    ("payment", re.compile(r"支付|付款|还款|缴纳|结算")),
    ("notice", re.compile(r"收到|通知|送达")),
    ("participation", re.compile(r"参与|负责|工作内容")),
    ("timeline", re.compile(r"时间|何时|先后|之前|之后|投保前|投保后")),
    ("application", re.compile(r"申请|起诉|立案|复议|仲裁")),
)
WITHHELD_UNKNOWN_RECAST_PATTERN = re.compile(
    r"不知道|不清楚|尚不清楚|无法确认|未明确|"
    r"尚待(?:客户)?(?:核实|确认|补充)|有待(?:核实|确认)"
)


def _withheld_target_match(question: str, clause: str) -> bool:
    """Bind a memo fact clause to the primary predicate of a withheld question."""

    matches = [
        (match.start(), name, pattern)
        for name, pattern in WITHHELD_TARGET_PREDICATES
        if (match := pattern.search(question)) is not None
    ]
    if not matches:
        return False
    _, _, primary = min(matches, key=lambda item: item[0])
    if primary.search(clause) is None:
        return False
    return _longest_common_substring_length(
        _generic_overlap_text(question), _generic_overlap_text(clause)
    ) >= 4


def withheld_answer_recast_violations(
    memo: str, withheld_questions: list[str]
) -> list[str]:
    """Reject turning a refusal to disclose into ignorance or an attributed fact.

    Only the factual memo prefix is checked.  A later legal question may properly
    discuss the same issue conditionally.  Opposing-party positions remain valid;
    what is forbidden is attributing a withheld answer to the client as though the
    client had supplied it.
    """

    # The renderer appends this ledger from typed runtime outcomes after all
    # model prose has been normalized.  A fact disclosed on another turn remains
    # a known client statement even if a later, related question was withheld.
    model_memo = _without_typed_fact_ledger(memo)
    factual_prefix = model_memo.partition("法律问题")[0]
    issues: list[str] = []
    for clause in (
        item.strip()
        for item in re.split(r"[。；;\n]", factual_prefix)
        if item.strip()
    ):
        matching = [
            question
            for question in withheld_questions
            if _withheld_target_match(question, clause)
        ]
        if not matching:
            continue
        recast_unknown = WITHHELD_UNKNOWN_RECAST_PATTERN.search(clause) is not None
        attributed_fact = _is_client_reporter(clause)
        if recast_unknown or attributed_fact:
            issues.append("withheld_answer_recast_as_known_or_unavailable")
    return list(dict.fromkeys(issues))


def neutralize_withheld_answer_recasts(
    memo: str, withheld_questions: list[str]
) -> tuple[str, list[str]]:
    """Restore the only supported state: not disclosed this turn, still open."""

    factual_prefix, separator, remainder = memo.partition("法律问题")
    # Preserve comma-linked attribution and objects as one factual sentence.
    # Splitting ``据客户转述，其投保前…`` at the comma detached the
    # provenance marker from the invented answer and let it escape the gate.
    pieces = re.split(r"([。；;\n])", factual_prefix)
    changes: list[str] = []
    for index in range(0, len(pieces), 2):
        clause = pieces[index]
        if not withheld_answer_recast_violations(clause, withheld_questions):
            continue
        pieces[index] = "客户本轮暂未披露该问题所涉事实，该问题仍开放"
        changes.append("withheld_status")
    normalized = "".join(pieces)
    if separator:
        normalized += separator + remainder
    return normalized, list(dict.fromkeys(changes))


def _question_targets_concept(
    question: str, concept: str, concept_pattern: re.Pattern[str]
) -> bool:
    """Distinguish the requested predicate from a document-source modifier.

    In ``是否收到保险公司出具的通知`` the unknown is receipt of the notice;
    ``出具`` only identifies that notice and does not ask whether the insurer
    issued it.  Treating every verb token as a separate target caused one unknown
    answer to erase two different facts.  Direct issuance questions such as
    ``医院出具了哪些证明`` remain in scope.
    """

    if not concept_pattern.search(question):
        return False
    return not (
        concept == "document_issuance"
        and re.search(
            r"(?:收到|接到|取得|持有).{0,16}(?:出具|开具|制发)(?:的)?"
            r".{0,16}(?:通知|决定|文书|证明|报告)",
            question,
        )
    )


def _unavailable_negative_concepts(
    text: str, unavailable_questions: list[str]
) -> list[str]:
    if not NEGATIVE_FACT_PATTERN.search(text):
        return []
    concepts: list[str] = []
    for question in unavailable_questions:
        for concept, pattern in UNAVAILABLE_ACTION_CONCEPTS.items():
            if not _question_targets_concept(question, concept, pattern) or not _negates_concept(
                text, pattern
            ):
                continue
            if not _concept_question_matches_clause(question, text, concept):
                continue
            if concept not in concepts:
                concepts.append(concept)
    if not concepts and _generic_unavailable_negative_overlap(
        text, unavailable_questions
    ):
        concepts.append("generic_question_overlap")
    return concepts


def unavailable_negative_claim_violations(
    memo: str,
    unavailable_questions: list[str],
    dialogue: list[tuple[str, str]] | None = None,
) -> list[str]:
    """Reject turning a client's unknown answer into a negative case fact.

    The gate is deliberately directional: epistemic wording such as “尚待核实”
    remains valid, while “尚未报案/没有付款” is blocked when the corresponding
    polar question received the simulator's unavailable response.  A shared entity
    anchor is required when the question names one, preventing an unrelated negative
    statement elsewhere in the memo from matching only a generic verb.
    """

    issues: list[str] = []
    # The reserved ledger is generated from response_kind, not by the memo model.
    # A grounded answer about a nearby concept must not be erased merely because
    # another typed question was unavailable (for example health-questionnaire
    # scope versus the client's actual pre-insurance diagnosis).
    model_memo = _without_typed_fact_ledger(memo)
    sentences = [
        item.strip() for item in re.split(r"[。；;\n]", model_memo) if item.strip()
    ]
    unavailable_question_set = set(unavailable_questions)
    grounded_answers = [
        answer.strip().rstrip("。！？!?")
        for question, answer in (dialogue or [])
        if question not in unavailable_question_set and answer.strip()
    ]
    for sentence in sentences:
        if EXPLICIT_UNRESOLVED_QUESTION_ENTRY_PATTERN.fullmatch(sentence):
            continue
        # Deterministic fidelity repair may restore an answered client statement
        # verbatim after an unavailable-negative normalizer removed it.  Exact
        # visible provenance outranks a topic-overlap warning from a different,
        # unanswered question; model-authored paraphrases receive no exemption.
        if any(len(answer) >= 8 and answer in sentence for answer in grounded_answers):
            continue
        for concept in _unavailable_negative_concepts(sentence, unavailable_questions):
            issue = f"unavailable_answer_recast_as_negative:{concept}"
            if issue not in issues:
                issues.append(issue)
    return issues


def neutralize_unavailable_negative_claims(
    memo: str, unavailable_questions: list[str]
) -> tuple[str, list[str]]:
    """Replace only unsupported negative clauses with explicit unknown status.

    Section headings and list markers are document structure rather than part of
    the factual claim.  Preserve them when a model places the first clause on the
    same line as its heading (for example, ``下一步建议：核实……未支持……``).
    Dropping that prefix made a safe factual normalization manufacture a missing-
    heading violation and forced an otherwise valid memo into fallback.
    """

    pieces = re.split(r"([，。；;\n])", memo)
    changes: list[str] = []
    for index in range(0, len(pieces), 2):
        clause = pieces[index]
        concepts = _unavailable_negative_concepts(clause, unavailable_questions)
        if not concepts:
            continue
        labels = list(dict.fromkeys(UNAVAILABLE_NEUTRAL_LABELS[item] for item in concepts))
        prefix = ""
        structural_prefix = re.match(
            r"^(\s*(?:#{1,6}\s*)?(?:\*{1,2})?"
            r"(?:案情概要|关键事实|法律问题|风险评估|下一步建议)"
            r"(?:\*{1,2})?\s*[：:]\s*"
            r"(?:(?:[-*]|\d+[.、])\s*)?)",
            clause,
        )
        if structural_prefix:
            prefix = structural_prefix.group(1)
        else:
            numbered = re.match(r"^(\s*(?:[-*]|\d+[.、])\s*)", clause)
            if numbered:
                prefix = numbered.group(1)
        pieces[index] = prefix + "、".join(labels) + "尚待客户补充核实"
        changes.extend(concepts)
    return "".join(pieces), list(dict.fromkeys(changes))


def _is_procedural_status_or_readiness_check(sentence: str, action: str) -> bool:
    """Distinguish procedure verification from advice to initiate a procedure.

    In a no-retrieval memo it is appropriate to flag a procedure for later review,
    provided the text makes the procedure itself the object of a status/readiness
    check.  A generic fact-check followed by an imperative (for example, ``先核实
    材料，然后申请复议``) is still direct procedural advice and must remain blocked.
    """

    escaped = re.escape(action)
    historical_or_status_check = bool(
        re.search(
            rf"(?:是否|有无|曾否|是否已经|是否已|有否).{{0,16}}{escaped}",
            sentence,
        )
    )
    if historical_or_status_check:
        return True

    # The named procedure is directly governed by a verification verb, and the
    # sentence identifies at least one readiness dimension to be checked.  Requiring
    # direct adjacency prevents a broad ``先核实`` anywhere in the sentence from
    # laundering a later imperative to start the procedure.
    dimensions = "|".join(map(re.escape, PROCEDURAL_READINESS_DIMENSIONS))
    direct_readiness_check = re.search(
        rf"(?:核实|确认|查明|了解|评估){escaped}(?:的|是否|程序|状态).{{0,24}}(?:{dimensions})",
        sentence,
    )
    if direct_readiness_check:
        return True

    # Also allow wording that expressly places verification before initiation,
    # such as ``申请仲裁前先核实管辖和期限``.  It does not tell the client to start
    # the procedure; it states what must be resolved before that decision.
    before_initiation_check = re.search(
        rf"{escaped}.{{0,6}}(?:前|之前).{{0,20}}(?:核实|确认|查明|评估).{{0,20}}(?:{dimensions})",
        sentence,
    )
    return bool(before_initiation_check)


def _is_procedural_path_reference(sentence: str, action: str) -> bool:
    """Allow a named procedure used only as the object of later evaluation.

    ``证据保全路径`` and ``申请复议的可行性`` name what counsel may later
    evaluate; they do not instruct the client to initiate that procedure.  Keep
    this deliberately local to the text immediately following the action so a
    generic word such as ``路径`` elsewhere cannot launder direct advice like
    ``然后申请证据保全``.
    """

    escaped = re.escape(action)
    return bool(
        re.search(
            rf"{escaped}(?:的)?(?:路径|可行性|可能性|适用条件|启动条件|程序条件|方案)",
            sentence,
        )
    )


def _is_procedural_artifact_verification(sentence: str, action: str) -> bool:
    """Allow fact gathering about an existing procedural artifact or measure.

    A memo may ask the client to verify or provide an existing appraisal report,
    preservation record, or preservation measure.  That is evidence provenance,
    not advice to initiate the named procedure.  Keep the verification verb local
    and preceding the artifact reference so wording such as ``立即申请证据保全``
    or ``获取司法鉴定报告`` remains blocked.
    """

    escaped = re.escape(action)
    artifact = re.search(
        rf"{escaped}(?:的)?(?:报告|意见|结论|记录|材料|文书|决定|状态|情况|措施)",
        sentence,
    )
    if artifact is None:
        return False
    local_prefix = sentence[max(0, artifact.start() - 96) : artifact.start()]
    return bool(
        re.search(
            r"(?:核实|确认|查明|了解|补充|提供|提交|出示|是否|有无|曾否)",
            local_prefix,
        )
    )


def neutralize_procedural_artifact_acquisition(memo: str) -> tuple[str, list[str]]:
    """Turn an ambiguous command to obtain a report into a status check.

    In a no-retrieval preliminary memo, ``获取司法鉴定报告`` can be read as
    directing the client to commission a new appraisal.  The safe deterministic
    interpretation is only to verify whether such a document already exists.  This
    normalization is deliberately limited to named procedural documents; it does
    not rewrite or permit commands to apply for or initiate a procedure.
    """

    value = memo
    changed: list[str] = []
    document_actions = ("司法鉴定", "申请鉴定")
    document_types = "报告|意见|结论|文书|记录"
    for action in document_actions:
        pattern = re.compile(
            rf"(?:获取|取得|索取|调取|出具)"
            rf"(?=[^。；;\n]{{0,32}}{re.escape(action)}(?:的)?(?:{document_types}))"
        )
        value, count = pattern.subn("核实是否已有", value)
        if count:
            changed.append(action)
    return value, changed


def memo_health_violations(
    memo: str,
    visible_text: str,
    unavailable_questions: list[str] | None = None,
    dialogue: list[tuple[str, str]] | None = None,
    withheld_questions: list[str] | None = None,
) -> list[str]:
    """Return violations that make a no-retrieval preliminary memo unsafe evidence."""

    issues: list[str] = []
    for heading in REQUIRED_HEADINGS:
        if heading not in memo:
            issues.append(f"missing_heading:{heading}")
    if not ("不替代持证律师" in memo or "不能替代持证律师" in memo or "不构成正式法律意见" in memo):
        issues.append("missing_preliminary_disclaimer")

    # Once factual sections have been replaced by the deterministic typed ledger,
    # the model-written legal analysis must not create a second, unaudited source
    # of client facts.  It may reason conditionally from "the above statements",
    # but any concrete client/counterparty attribution belongs in the ledger.
    if TYPED_FACT_LEDGER_START in memo and TYPED_FACT_LEDGER_END in memo:
        analytical_suffix = _without_typed_fact_ledger(memo)
        analytical_suffix = re.sub(
            r"本备忘录仅基于客户单方陈述[^\n]*",
            "",
            analytical_suffix,
        )
        if any(
            reporter is not None and _reporter_introduces_concrete_fact(reporter)
            for reporter in (
                _clause_reporter(item) for item in _memo_clauses(analytical_suffix)
            )
        ):
            issues.append("analysis_fact_attribution_outside_typed_ledger")

    for citation in sorted(set(re.findall(r"《[^》]{2,40}》", memo))):
        if citation not in visible_text:
            issues.append(f"ungrounded_law_citation:{citation}")
    for article in sorted(set(LAW_ARTICLE_PATTERN.findall(memo))):
        if article not in visible_text:
            issues.append(f"ungrounded_law_article:{article}")
    for case_number in sorted(set(CASE_NUMBER_PATTERN.findall(memo))):
        if case_number not in visible_text:
            issues.append(f"ungrounded_case_number:{case_number}")

    # Legal-analysis calibration rules apply to authored analysis, not to the
    # deterministic typed ledger.  The ledger may faithfully quote a client's
    # categorical legal belief (for example, "我担心……必然是共犯").  Treating
    # that quotation as the lawyer's own conclusion makes the safe fallback
    # impossible precisely when it is needed.  Other provenance checks below
    # still police the ledger/model boundary and the ledger itself is rendered
    # only from typed visible outcomes.
    analysis_sentences = _memo_clauses(_without_typed_fact_ledger(memo))
    sentences = analysis_sentences
    for sentence in analysis_sentences:
        if "是否" in sentence or sentence.endswith(("？", "?")):
            continue
        attributed_position = _clause_reporter(sentence) is not None
        categorical = bool(
            re.search(
                r"(?:(?<![不非])必然|(?<![不非])肯定|(?<![不非])显然|"
                r"(?<![不非])当然|无需|不需要|不承担|应当承担|依法应当|"
                r"已经构成|已构成|确定构成|(?<![不非])必定)",
                sentence,
            )
        )
        if (
            categorical
            and not attributed_position
            and not any(marker in sentence for marker in CAUTION_MARKERS)
        ):
            issues.append("uncalibrated_legal_conclusion")
            break

    for sentence in analysis_sentences:
        elements = re.search(r"符合.{0,20}(?:犯罪|罪)?构成要件", sentence)
        if elements:
            prefix = sentence[max(0, elements.start() - 12) : elements.start()]
            if not any(
                marker in prefix
                for marker in (
                    "是否",
                    "可能",
                    "若",
                    "如果",
                    "初步",
                    "无法断言",
                    "不能断言",
                    "尚不能",
                    "不得断言",
                    "未能确认",
                )
            ):
                issues.append("uncalibrated_offense_elements_conclusion")
                break

    for sentence in analysis_sentences:
        invariant = re.search(r"不影响.{0,24}(?:认定|性质|责任|效力|结果)", sentence)
        if invariant:
            prefix = sentence[max(0, invariant.start() - 10) : invariant.start()]
            if not any(marker in prefix for marker in ("可能", "未必", "不一定", "是否")):
                issues.append("uncalibrated_legal_invariance_conclusion")
                break

    # A no-retrieval memo may say that a remedy is subject to the applicable or
    # statutory conditions.  That is calibrated uncertainty, not an invented
    # legal test.  Block only when the model supplies a *specific* condition or
    # element between ``满足`` and ``条件/要件``.  The former broad regex also
    # rejected harmless text such as “申请保护令需满足法定条件，尚待核验”, which
    # forced otherwise sound memos into the deterministic fallback.
    generic_condition_qualifiers = {
        "",
        "一定",
        "具体",
        "法定",
        "相关",
        "相应",
        "其他",
        "适用",
        "特定",
        "相关法定",
        "相应法定",
        "具体法定",
    }
    for sentence in sentences:
        matches = re.finditer(
            r"(?:需|需要|必须|应当)满足(?P<detail>.{0,32}?)(?:条件|要件)",
            sentence,
        )
        if any(
            match.group("detail").strip(" ：:，,、的")
            not in generic_condition_qualifiers
            for match in matches
        ):
            issues.append("unretrieved_specific_legal_rule")
            break

    # Without a retrieval result, a preliminary renderer may discuss broad civil,
    # administrative, or criminal exposure but must not invent a precise offence.
    # Trigger only on explicit charge-assignment syntax, not generic words such as
    # “犯罪风险/是否有罪/罪名待核实”.
    for sentence in sentences:
        # A coordinator by itself is not charge-assignment syntax.  Treating ``、``
        # or ``或`` as an independent lead-in let an ordinary evidence list such as
        # ``监测数据异常情况、刑事调查罪名及证据类型`` cross the list boundary and
        # manufacture the non-existent charge ``监测数据异常情况、刑事调查罪``.
        # First bind the text to an explicit assignment predicate, then enumerate
        # charge-shaped items inside that local clause.  This still catches a real
        # compound expression such as ``构成诈骗罪或掩饰、隐瞒犯罪所得罪``.
        assignment_bodies = re.findall(
            r"(?:涉嫌|涉及|构成|符合|包括|以)"
            r"([^，。；;？?]{2,72})",
            sentence,
        )
        charges = [
            match.group(1).strip(" ：:，,、")
            for body in assignment_bodies
            for match in re.finditer(
                r"([^或及和]{2,24}?(?<!犯)罪)(?!名)",
                body,
            )
        ]
        for charge in charges:
            # A conditional legal issue may name the offence whose conduct stem is
            # already used in the visible client account (e.g. “实施诈骗” ->
            # “是否构成诈骗罪”).  It may not introduce a different offence from
            # parametric memory.  Generic “刑事犯罪/单位犯罪/某类犯罪” never matches
            # because the character immediately before 罪 is 犯.
            stem = charge[:-1].strip()
            broad_legal_category = stem.endswith(("相关", "有关", "类", "其他"))
            if not broad_legal_category and stem not in visible_text:
                issues.append(f"ungrounded_narrow_offense:{charge}")
                break
        if any(item.startswith("ungrounded_narrow_offense:") for item in issues):
            break

    for deadline in sorted(set(PROCEDURAL_DEADLINE_PATTERN.findall(memo))):
        deadline_sentence = next(
            (sentence for sentence in sentences if deadline in sentence), ""
        )
        if (
            deadline not in visible_text
            and any(
                marker in deadline_sentence
                for marker in ("诉讼", "起诉", "复议", "上诉", "仲裁", "申请", "期限")
            )
        ):
            issues.append(f"ungrounded_procedural_deadline:{deadline}")

    next_steps = memo.split("下一步建议", 1)[1] if "下一步建议" in memo else ""
    for action in PROCEDURAL_ACTIONS:
        for sentence in (item.strip() for item in re.split(r"[。\n]", next_steps) if item.strip()):
            # Asking the client/lawyer to verify whether a procedure already happened
            # is a provenance check, not advice to initiate that procedure.  Keep the
            # gate focused on actual imperatives/recommendations.
            if (
                action in sentence
                and not _is_procedural_status_or_readiness_check(sentence, action)
                and not _is_procedural_path_reference(sentence, action)
                and not _is_procedural_artifact_verification(sentence, action)
                and not any(marker in sentence for marker in OPTION_MARKERS)
            ):
                issues.append(f"unqualified_procedural_recommendation:{action}")
                break
    issues.extend(
        unavailable_negative_claim_violations(
            memo,
            unavailable_questions or [],
            dialogue,
        )
    )
    issues.extend(withheld_answer_recast_violations(memo, withheld_questions or []))
    # Recast detectors police model prose.  The reserved ledger is copied from
    # typed visible outcomes and therefore supplies the ground truth these
    # detectors are intended to protect, including legitimate negative answers.
    model_memo = _without_typed_fact_ledger(memo)
    issues.extend(question_only_negative_claim_violations(model_memo, dialogue or []))
    issues.extend(client_position_reversal_violations(model_memo, dialogue or []))
    issues.extend(
        known_temporal_answer_recast_as_unknown_violations(model_memo, dialogue or [])
    )
    issues.extend(
        known_external_action_recast_as_pending_violations(model_memo, dialogue or [])
    )
    issues.extend(
        known_completed_event_recast_as_uncertain_violations(model_memo, dialogue or [])
    )
    return issues


def deterministic_safe_memo(
    opening: str,
    dialogue: list[tuple[str, str]],
    *,
    dialogue_response_kinds: list[str | None] | None = None,
) -> str:
    """Conservative last resort after the local memo model repeatedly violates its contract."""

    unavailable_markers = ("不知道", "不清楚", "不太确定", "没有这项具体情况", "需要再核实")
    def is_unavailable_answer(answer: str) -> bool:
        # Cooperative/defensive persona renderers may hedge a real grounded fact
        # with “不太确定，不过按我的理解…”.  The content after that prefix is still
        # an answer and must not be discarded by the last-resort memo renderer.
        if "按我的理解" in answer:
            return False
        return any(marker in answer for marker in unavailable_markers)

    typed_response_kinds_provided = dialogue_response_kinds is not None
    if dialogue_response_kinds is None:
        dialogue_response_kinds = [None] * len(dialogue)
    if len(dialogue_response_kinds) != len(dialogue):
        raise ValueError("dialogue response kinds must align one-to-one with dialogue")
    answers = []
    unresolved = []
    withheld = []
    for (question, answer), kind in zip(
        dialogue, dialogue_response_kinds, strict=True
    ):
        if kind == "withheld":
            withheld.append(question.strip())
        elif kind == "unavailable" or (kind is None and is_unavailable_answer(answer)):
            unresolved.append(question.strip())
        elif answer.strip():
            answers.append(answer.strip())
    excerpts = [
        f"- 客户单方陈述（尚未核验）：{clause.strip()}。"
        for answer in answers[:3]
        for clause in re.split(r"[。！？!?]+", answer)
        if clause.strip()
    ]
    visible_facts = "\n".join(excerpts)[:700]
    if not visible_facts:
        visible_facts = f"- 客户单方陈述（尚未核验）：{opening[:300]}"
    # In the typed execution path the exact unresolved/withheld questions are
    # inserted once into the reserved ledger by ``_render_typed_factual_sections``.
    # Repeating their full wording in the authored advice section is both
    # redundant and unsafe: a question can contain a grounded premise such as
    # "未授权", which an intentionally conservative negative-fact detector may
    # then mistake for an answer to that unanswered question.  Keep the detailed
    # status in the ledger and make the fallback advice refer to it generically.
    if typed_response_kinds_provided:
        unresolved_lines = []
        if unresolved:
            unresolved_lines.append("- 按结构化会话事实状态逐项补充核实未回答问题。")
        if withheld:
            unresolved_lines.append("- 对客户本轮暂未披露的问题保留开放状态，后续再核实。")
        unresolved_text = "\n".join(unresolved_lines)
    else:
        unresolved_text = "\n".join(
            f"- 待向客户补充核实：{item}" for item in unresolved[:3]
        )
        if withheld:
            withheld_text = "\n".join(
                f"- 客户本轮暂未披露，问题仍开放：{item}"
                for item in withheld[:3]
            )
            unresolved_text = (unresolved_text + "\n" + withheld_text).strip()
    if not unresolved_text:
        unresolved_text = "- 待结合原始文件核实客户陈述及争议方说法。"
    return (
        "## 案情概要\n"
        "以下仅整理客户在本次初步咨询中的单方陈述，不构成确定法律意见。\n\n"
        "## 关键事实\n"
        f"{visible_facts}\n\n"
        "## 法律问题\n"
        "具体请求权基础、责任主体和程序路径仍需结合原始文件及届时有效的中国法核实。\n\n"
        "## 风险评估\n"
        "目前信息未经独立核验，不能据此确认任何一方是否违法、是否承担责任或案件结果。\n\n"
        "## 下一步建议\n"
        f"{unresolved_text}\n"
        "先整理与争议最直接相关的原始文件，并由具备相应资质的专业人员结合完整材料核实法域、程序状态和期限。\n\n"
        "本备忘录仅基于客户单方陈述作研究性初步分析，不替代持证律师结合完整材料提供的正式意见。"
    )
