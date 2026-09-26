"""Shared deterministic contract for public-opening inquiry targets."""

from __future__ import annotations

import hashlib
import re

OPENING_AGENDA_ATTRIBUTE_LABELS: dict[str, str] = {
    "time": "发生时间",
    "place": "发生地点",
    "amount": "涉及金额",
    "content": "具体内容",
    "method": "实施方式",
    "reason": "具体原因",
    "status": "当前状态",
    "result": "具体结果",
    "duration": "持续时间",
    "frequency": "发生次数",
}

OPENING_AGENDA_RENDERED_SUFFIXES = frozenset(OPENING_AGENDA_ATTRIBUTE_LABELS.values())

_GENERIC_TOPICS = {
    "客户",
    "本人",
    "自己",
    "对方",
    "公司",
    "单位",
    "事情",
    "情况",
    "问题",
    "纠纷",
    "案件",
    "项目",
    "结果",
    "处理",
}
_QUESTION_TOPIC_PATTERN = re.compile(
    r"(?:是否|有无|有没有|如何|怎么|什么|为何|为什么|哪(?:个|些|一|种|类|项|方)?)"
)
_PURE_ACTOR_PATTERN = re.compile(
    r"^(?:我|我们|本人|客户|对方|双方|卖方|买方|原告|被告|申请人|被申请人|"
    r"上诉人|被上诉人|员工|职工|劳动者|经营者|消费者|平台|银行|法院|机关|"
    r"部门|机构|公司|单位|店方|店铺|商户|医院|学校|物业|业主)$"
)
_LEGAL_TOPIC_PATTERN = re.compile(
    r"(?:是否合法|法律责任|法律关系|法律效力|适用(?:什么)?法律|合同适用规则|"
    r"处理权限|有无权限|是否有权|应否承担|赔偿责任)"
)


def opening_agenda_label(topic_excerpt: str, attribute: str) -> str:
    """Render the only admissible label for one closed-set attribute."""

    return f"{topic_excerpt}的{OPENING_AGENDA_ATTRIBUTE_LABELS[attribute]}"


def opening_agenda_fact_id(label: str) -> str:
    """Return the stable identifier bound to a rendered agenda label."""

    identity = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", label).lower()
    return f"opening_agenda_{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:16]}"


def opening_agenda_topic_issue(topic_excerpt: str, opening: str) -> str | None:
    """Return the shared rejection code for an unsafe/ungrounded topic span."""

    topic_identity = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", topic_excerpt).lower()
    if (
        len(topic_identity) < 2
        or len(topic_excerpt) > 48
        or topic_identity in _GENERIC_TOPICS
        or topic_excerpt not in opening
    ):
        return "opening_topic_not_exactly_grounded"
    if _QUESTION_TOPIC_PATTERN.search(topic_excerpt):
        return "query_shaped_opening_topic"
    if _PURE_ACTOR_PATTERN.fullmatch(topic_identity):
        return "actor_only_opening_topic"
    if _LEGAL_TOPIC_PATTERN.search(topic_excerpt):
        return "legal_opening_topic"
    return None


def opening_agenda_attribute_from_label(anchor: str, label: str) -> str | None:
    """Recover the unique closed attribute whose deterministic label matches."""

    matches = [
        attribute
        for attribute, suffix in OPENING_AGENDA_ATTRIBUTE_LABELS.items()
        if label == f"{anchor}的{suffix}"
    ]
    return matches[0] if len(matches) == 1 else None


def opening_attribute_is_explicitly_answered(
    opening: str,
    topic_excerpt: str,
    attribute: str,
) -> bool:
    """Detect only explicit opening answers to one closed observable attribute."""

    clauses = [
        item.strip()
        for item in re.split(r"[，,。；;！？!?\n]+", opening)
        if item.strip()
    ]
    clauses = [item for item in clauses if topic_excerpt in item] or [opening]
    compact_topic = re.sub(r"\s+", "", topic_excerpt)
    absent_event = re.compile(
        r"(?:从未|未曾|尚未|没有|并未|未)(?:.{0,8})" + re.escape(compact_topic)
    )
    attribute_patterns = {
        "time": (
            r"(?:前天|昨天|今日|今天|明天|去年|今年|明年|当日|当天|"
            r"(?:19|20)\d{2}年|\d{1,2}月\d{1,2}日|\d{1,2}[时点])"
        ),
        "place": (
            r"(?:地点|地址|位于|坐落|在.{1,18}(?:店|公司|单位|医院|法院|"
            r"现场|平台|省|市|区|县|镇|村|路|室))"
        ),
        "amount": (
            r"(?:金额|数额|价款|费用|共计|合计|"
            r"(?:\d+(?:\.\d+)?|[一二三四五六七八九十百千万两]+)"
            r"(?:万|千|百)?元)"
        ),
        "content": r"(?:内容为|具体为|载明|写明|明确约定|原文为|[:]|“[^”]+”)",
        "method": r"(?:通过|采用|经由|以.{0,12}方式|口头|书面|网上|实地)",
        "reason": r"(?:因为|由于|缘于|因.{1,18}|以.{1,18}为由|原因是)",
        "status": r"(?:目前|当前|至今|仍然|仍|已经|已|尚未|正在|准备|待|完成|终止|继续)",
        "result": r"(?:最终|结果|导致|造成|因此|出现|改善|不利|有利|成功|失败|驳回|维持|取消)",
        "duration": r"(?:持续|历时|为期|从.{1,18}(?:至|到).{1,18}|(?:日|天|月|年)之久)",
        "frequency": (
            r"(?:多次|数次|反复|每次|(?:\d+|[一二三四五六七八九十百千万两]+)次)"
        ),
    }
    for clause in clauses:
        compact = re.sub(r"\s+", "", clause)
        if attribute != "reason" and absent_event.search(compact):
            return True
        if re.search(attribute_patterns[attribute], compact):
            return True
    return False
