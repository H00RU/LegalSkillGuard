#!/usr/bin/env python3
"""Qualify the frozen local judge on controlled Chinese legal contrasts."""

from __future__ import annotations

import argparse
import json
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import yaml

from legal_skill_guard.evaluation.qualification import (
    SEMANTIC_JUDGE_QUALIFICATION_CASE_COUNT,
    SEMANTIC_JUDGE_QUALIFICATION_CASES,
    SEMANTIC_JUDGE_QUALIFICATION_REPORT_SCHEMA_VERSION,
    semantic_judge_qualification_component_hashes,
    semantic_judge_qualification_sha256,
)
from legal_skill_guard.evaluation.semantic import (
    FactJudgment,
    GroundedClaim,
    RubricJudgment,
    UnsupportedClaim,
    build_fact_judgment_prompt,
    build_grounding_judgment_prompt,
    build_official_grounding_judgment_prompt,
    chunk_claim_spans,
    fact_judgment_schema,
    fact_wire_contract_issues,
    grounding_judgment_schema,
    grounding_wire_contract_issues,
    memo_claim_spans,
    normalize_exact_visible_grounding,
    normalize_official_grounding_contract,
    normalize_verbatim_fact_decisions,
    normalize_verbatim_rubric_scores,
    official_grounding_judgment_schema,
    parse_fact_judgment,
    parse_grounding_judgment,
    parse_official_grounding_judgment,
    rubric_judgment_schema,
)
from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.inference.structured_openai_client import StructuredOpenAIClient
from legal_skill_guard.utils.hashing import canonical_json_sha256

ROOT = Path(__file__).resolve().parents[1]


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _select_training_cases() -> list[dict[str, Any]]:
    """Load the exact frozen eight-case/domain qualification panel."""

    case_rows = _load_jsonl(
        ROOT / "data/training/legal_skill_guard_dlawbench_style_cn.jsonl"
    )
    case_ids = [str(item["id"]) for item in case_rows]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("training corpus contains duplicate case identifiers")
    cases = {str(item["id"]): item for item in case_rows}
    provenance = _load_jsonl(
        ROOT / "data/training/legal_skill_guard_dlawbench_style_cn.provenance.jsonl"
    )
    provenance_ids = [str(item["id"]) for item in provenance]
    if len(provenance_ids) != len(set(provenance_ids)):
        raise ValueError("training provenance contains duplicate case identifiers")
    provenance_by_id = {str(item["id"]): item for item in provenance}
    selected: list[dict[str, Any]] = []
    for case_id, expected_domain in SEMANTIC_JUDGE_QUALIFICATION_CASES:
        case = cases.get(case_id)
        provenance_row = provenance_by_id.get(case_id)
        if case is None or provenance_row is None:
            raise ValueError(
                f"frozen qualification case is missing from corpus/provenance: {case_id}"
            )
        actual_split = str(provenance_row.get("split"))
        actual_domain = str(provenance_row.get("annotation", {}).get("legal_domain"))
        if actual_split != "train" or actual_domain != expected_domain:
            raise ValueError(
                "frozen qualification case provenance mismatch: "
                f"case_id={case_id} expected_split=train actual_split={actual_split} "
                f"expected_domain={expected_domain} actual_domain={actual_domain}"
            )
        case = dict(case)
        case["legal_domain"] = expected_domain
        selected.append(case)
    return selected


def _fact_block(case: dict[str, Any]) -> str:
    return "\n\n".join(
        (
            f"事实{fact['fact_id']}（{fact['gap_type']}）：\n"
            f"客户认知：{fact['client_belief']}\n"
            f"案件记录：{fact['court_record']}"
        )
        for fact in case["facts"]
    )


def _full_dialogue_and_memo(case: dict[str, Any]) -> tuple[str, str]:
    lines = [f"客户（开场）：{case['opening']}"]
    facts = case["facts"]
    for index, inquiry in enumerate(case["evaluation_criteria"]["expected_inquiries"]):
        lines.extend(
            [
                f"律师（第{index + 1}轮）：{inquiry}",
                "客户：我会按这个问题的范围如实说明现有情况并提供材料；"
                "不能确认的部分会明确标为待核验。",
            ]
        )
    memo = "\n".join(
        [
            "## 已核实事实",
            *[f"- {fact['court_record']}" for fact in facts],
            "## 法律问题与分析",
            *[f"- {item}" for item in case["evaluation_criteria"]["memo_expectations"]],
            "## 限制",
            "以上事实均以客户提交的相应材料为前提，正式意见仍需核验原件。",
        ]
    )
    return "\n".join(lines), memo


def _sparse_dialogue_and_memo(case: dict[str, Any]) -> tuple[str, str]:
    return (
        f"客户（开场）：{case['opening']}",
        "现有信息不足，暂时不能判断；需要以后再进行完整咨询和材料核验。",
    )


def _dialogue_only_facts_and_generic_memo(case: dict[str, Any]) -> tuple[str, str]:
    lines = [f"客户（开场）：{case['opening']}"]
    for index, fact in enumerate(case["facts"], start=1):
        lines.extend(
            [
                f"律师（第{index}轮）：请说明一项相关具体事实。",
                f"客户：{fact['client_belief']}",
            ]
        )
    memo = (
        "## 案情概要\n客户已经口头陈述若干情况。\n"
        "## 关键事实\n本备忘录暂不列示任何具体事实，均待以后整理和核验。\n"
        "## 法律问题\n信息不足，暂不分析。\n"
        "## 风险评估\n无法判断。\n"
        "## 下一步建议\n另行整理材料。"
    )
    return "\n".join(lines), memo


def _attributed_client_memo(case: dict[str, Any]) -> tuple[str, str]:
    """A client allegation is source-grounded without becoming a verified fact."""

    allegation = str(case["facts"][0]["client_belief"])
    dialogue = (
        f"客户（开场）：{case['opening']}\n"
        f"律师（第1轮）：请只陈述你目前对一项关键事实的认识。\n客户：{allegation}"
    )
    memo = (
        "## 客户陈述\n"
        f"据客户在咨询中的单方陈述：{allegation}\n"
        "以上仅记录客户的单方陈述，不代表相关事实已经由书证、对方陈述或司法文书核实。"
    )
    return dialogue, memo


def _poisoned_dialogue_and_memo(case: dict[str, Any]) -> tuple[str, str]:
    lines = [f"客户（开场）：{case['opening']}"]
    for index, fact in enumerate(case["facts"]):
        lines.extend(
            [
                f"律师（第{index + 1}轮）：请说说你对相关事实的理解。",
                f"客户：{fact['client_belief']}",
            ]
        )
    disputed = [fact for fact in case["facts"] if fact["gap_type"] == "disputed"]
    asserted = disputed or case["facts"][:1]
    memo = "\n".join(
        [
            "## 已核实的确定结论",
            *[
                "- 客户的下述认知已经核实且法律方向正确，可直接作为确定结论："
                f"{fact['client_belief']}"
                for fact in asserted
            ],
            "## 结论",
            "法院已经作出生效判决，客户全部胜诉并当然获得三倍惩罚性赔偿。",
        ]
    )
    return "\n".join(lines), memo


def _legal_direction_anchors() -> list[dict[str, Any]]:
    """Target previously observed subject and legal-direction inversions."""

    return [
        {
            "id": "anchor_joint_registration",
            "opening": "丈夫婚前购买的房屋，婚后已经登记到夫妻双方名下。",
            "facts": [
                {
                    "fact_id": "F1",
                    "gap_type": "aligned",
                    "client_belief": "房屋婚后登记到夫妻双方名下。",
                    "court_record": "房屋现登记为共同共有，应作为夫妻共同财产依法分割。",
                }
            ],
            "dialogue": "客户（开场）：丈夫婚前购买的房屋，婚后已经登记到夫妻双方名下。",
            "memo": "案涉房屋虽然婚后登记在双方名下，但仍然只是丈夫的个人财产。",
            "expected_incorrect": ["F1"],
            "expected_substantive_covered": ["F1"],
            "expected_substantive_correct": [],
        },
        {
            "id": "anchor_internal_fiscal_approval",
            "opening": "医院收货后拖欠货款，称内部财政审批尚未完成。",
            "facts": [
                {
                    "fact_id": "F1",
                    "gap_type": "disputed",
                    "client_belief": "医院说财政审批没完成，所以不承担逾期责任。",
                    "court_record": "内部财政审批流程不构成免除合同付款及逾期责任的事由。",
                }
            ],
            "dialogue": "客户（开场）：医院收货后拖欠货款，称内部财政审批尚未完成。",
            "memo": "财政审批没有完成可能使医院免除付款及逾期责任。",
            "expected_incorrect": ["F1"],
            "expected_substantive_covered": ["F1"],
            "expected_substantive_correct": [],
        },
        {
            "id": "anchor_scraper_subject_direction",
            "opening": "我方运营平台，对方绕过风控抓取数据并收费。",
            "facts": [
                {
                    "fact_id": "F1",
                    "gap_type": "aligned",
                    "client_belief": "对方插件绕过我方风控抓取平台数据并制作收费产品。",
                    "court_record": "被诉抓取方绕过平台措施并商业化利用数据，平台方主张制止。",
                }
            ],
            "dialogue": "客户（开场）：我方运营平台，对方绕过风控抓取数据并收费。",
            "memo": "客户作为平台方实施抓取，因此客户可能承担侵权或违约责任。",
            "expected_incorrect": ["F1"],
            "expected_substantive_covered": ["F1"],
            "expected_substantive_correct": [],
        },
        {
            "id": "anchor_topic_placeholder_precision",
            "opening": "丈夫婚前购买的房屋，婚后登记到夫妻双方名下。",
            "facts": [
                {
                    "fact_id": "F1",
                    "gap_type": "aligned",
                    "client_belief": "双方目前都按600万元估算房屋价值。",
                    "court_record": "诉讼中双方均认可房屋市场价值600万元。",
                },
                {
                    "fact_id": "F2",
                    "gap_type": "aligned",
                    "client_belief": "十余年婚姻中的家庭贡献应计入分割衡量。",
                    "court_record": "分割时考虑婚姻存续十余年及双方家庭贡献。",
                },
                {
                    "fact_id": "F3",
                    "gap_type": "aligned",
                    "client_belief": "房屋婚后登记到夫妻双方名下。",
                    "court_record": "婚后共同登记使房屋成为夫妻共同财产。",
                },
            ],
            "dialogue": "客户（开场）：丈夫婚前购买的房屋，婚后登记到夫妻双方名下。",
            "memo": (
                "婚后共同登记使房屋成为夫妻共同财产。至于分割比例应结合相关因素；"
                "房屋市场价值和估值依据目前信息不足，均尚待核实。"
            ),
            "expected_incorrect": [],
            "expected_substantive_covered": ["F3"],
            "expected_substantive_correct": ["F3"],
        },
    ]


def _qualify_legal_anchor(
    client: StructuredOpenAIClient,
    repair_client: StructuredOpenAIClient,
    system_prompt: str,
    anchor: dict[str, Any],
) -> tuple[dict[str, Any], str | None]:
    case = {"opening": anchor["opening"], "facts": anchor["facts"]}
    prompt = _fact_prompt(case, anchor["dialogue"], anchor["memo"])
    error = "unknown"
    prior_value: dict[str, Any] | None = None
    for attempt in range(2):
        active = client if attempt == 0 else repair_client
        try:
            response = active.generate_json(
                purpose=(
                    f"qualification_{anchor['id']}_facts"
                    if attempt == 0
                    else f"qualification_{anchor['id']}_facts_repair"
                ),
                system_prompt=system_prompt,
                user_prompt=(
                    prompt
                    if attempt == 0
                    else prompt
                    + "\n\n请修复上一次对象并保持案件主体方向。结构错误："
                    + error[:800]
                    + "。上一次待修对象："
                    + json.dumps(prior_value, ensure_ascii=False, sort_keys=True)
                ),
                output_schema=fact_judgment_schema({fact["fact_id"] for fact in anchor["facts"]}),
            )
            prior_value = response.value
            judgment, _ = _validate_facts(case, response.value, anchor["memo"])
        except Exception as exc:
            error = f"{type(exc).__name__}:{exc}"
            continue
        actual = sorted(item.fact_id for item in judgment.incorrect_facts)
        expected = sorted(anchor["expected_incorrect"])
        substantive_covered = sorted(judgment.substantive_covered_fact_ids)
        substantive_correct = sorted(judgment.substantive_correct_fact_ids)
        expected_substantive_covered = sorted(anchor["expected_substantive_covered"])
        expected_substantive_correct = sorted(anchor["expected_substantive_correct"])
        passed = (
            actual == expected
            and substantive_covered == expected_substantive_covered
            and substantive_correct == expected_substantive_correct
        )
        if not passed and attempt == 0:
            error = (
                f"contract_mismatch:incorrect={actual}:"
                f"substantive_covered={substantive_covered}:"
                f"substantive_correct={substantive_correct}"
            )
            continue
        return (
            {
                "anchor_id": anchor["id"],
                "passed": passed,
                "expected_incorrect": expected,
                "actual_incorrect": actual,
                "expected_substantive_covered": expected_substantive_covered,
                "actual_substantive_covered": substantive_covered,
                "expected_substantive_correct": expected_substantive_correct,
                "actual_substantive_correct": substantive_correct,
                "request_sha256": response.request_sha256,
                "repair_used": attempt > 0,
            },
            None
            if passed
            else (
                f"{anchor['id']}:contract_mismatch:incorrect={actual}:"
                f"substantive_covered={substantive_covered}:"
                f"substantive_correct={substantive_correct}"
            ),
        )
    return (
        {
            "anchor_id": anchor["id"],
            "passed": False,
            "expected_incorrect": sorted(anchor["expected_incorrect"]),
            "actual_incorrect": [],
            "repair_used": True,
        },
        f"{anchor['id']}:failed_bounded_repair:{error}",
    )


def _qualify_visible_source_anchor(
    client: StructuredOpenAIClient,
    repair_client: StructuredOpenAIClient,
    system_prompt: str,
) -> tuple[dict[str, Any], str | None]:
    """Require exact visible sources and exclude unasserted hypothetical conditions."""

    anchor_id = "anchor_question_is_not_visible_disclosure"
    case = {
        "opening": "离婚前法院已签发保护令。我想知道离婚后保护令是否仍在有效期。",
        "facts": [
            {
                "fact_id": "F1",
                "gap_type": "aligned",
                "client_belief": "我认为保护令离婚后仍有效。",
                "court_record": "保护令在离婚后仍在有效期内。",
            }
        ],
    }
    dialogue = (
        "客户（开场）：离婚前法院已签发保护令。我想知道离婚后保护令是否仍在有效期。\n"
        "律师（第1轮）：保护令离婚后是否仍在有效期？\n"
        "客户：这个我不确定，现有信息里没有，我需要再核实。\n"
        "律师（第2轮）：您是否收到法院关于补充材料的通知？\n"
        "客户：我昨天收到法院短信，要求本周补交材料。"
    )
    memo = (
        "- 客户称离婚前法院已签发保护令。\n"
        "- 客户称保护令离婚后仍在有效期内，但尚待核实。\n"
        "- 客户昨天收到法院短信，要求本周补交材料。\n"
        "- 若保护令已经失效，继续主张其效力可能面临风险。\n"
        "- 法院已经决定对前夫拘留十日。"
    )
    prompt = build_grounding_judgment_prompt(case, dialogue, memo)
    error = "unknown"
    prior_value: dict[str, Any] | None = None
    for attempt in range(2):
        active = client if attempt == 0 else repair_client
        try:
            response = active.generate_json(
                purpose=(
                    f"qualification_{anchor_id}_grounding"
                    if attempt == 0
                    else f"qualification_{anchor_id}_grounding_repair"
                ),
                system_prompt=system_prompt,
                user_prompt=(
                    prompt
                    if attempt == 0
                    else prompt
                    + "\n\n请重新对全部冻结claim ID作可见、仅离线、无来源、非事实主张四类分区。"
                    + f"结构错误：{error[:800]}。上一次待修对象："
                    + json.dumps(prior_value, ensure_ascii=False, sort_keys=True)
                ),
                output_schema=grounding_judgment_schema(memo_claim_spans(memo)),
            )
            prior_value = response.value
            visible, benchmark_only, unsupported, _ = _validate_source_audit_grounding(
                response.value, memo, dialogue
            )
        except Exception as exc:
            error = f"{type(exc).__name__}:{exc}"
            continue
        visible_text = "\n".join(item.claim for item in visible)
        benchmark_text = "\n".join(item.claim for item in benchmark_only)
        unsupported_text = "\n".join(item.claim for item in unsupported)
        all_text = visible_text + "\n" + benchmark_text + "\n" + unsupported_text
        nonvisible_text = benchmark_text + "\n" + unsupported_text
        later_dialogue_claims = [
            item for item in visible if "短信" in item.claim or "补交材料" in item.claim
        ]
        later_dialogue_basis_accurate = bool(later_dialogue_claims) and all(
            "开场" not in item.basis
            and any(
                marker in item.basis.lower()
                for marker in (
                    "对话",
                    "第2轮",
                    "客户回答",
                    "dialogue round 2",
                    "round 2",
                )
            )
            for item in later_dialogue_claims
        )
        passed = (
            "签发保护令" in visible_text
            and "仍在有效期" not in visible_text
            and "仍在有效期" in nonvisible_text
            and later_dialogue_basis_accurate
            and "保护令已经失效" not in all_text
            and "拘留十日" in unsupported_text
        )
        row = {
            "anchor_id": anchor_id,
            "passed": passed,
            "visible_claims": [item.claim for item in visible],
            "benchmark_only_claims": [item.claim for item in benchmark_only],
            "unsupported_claims": [item.claim for item in unsupported],
            "later_dialogue_claims": [
                item.model_dump(mode="json") for item in later_dialogue_claims
            ],
            "later_dialogue_basis_accurate": later_dialogue_basis_accurate,
            "hypothetical_condition_excluded": "保护令已经失效" not in all_text,
            "request_sha256": response.request_sha256,
            "repair_used": attempt > 0,
        }
        return (
            row,
            None if passed else f"{anchor_id}:source_partition_mismatch:{row}",
        )
    return (
        {"anchor_id": anchor_id, "passed": False, "repair_used": True},
        f"{anchor_id}:failed_bounded_repair:{error}",
    )


def _qualify_official_grounding_anchor(
    client: StructuredOpenAIClient,
    repair_client: StructuredOpenAIClient,
    system_prompt: str,
) -> tuple[dict[str, Any], str | None]:
    """Guard the official union rule and unknown-answer directionality."""

    anchor_id = "anchor_official_grounding_union_and_unknown_answer"
    case = {
        "opening": "银行以保证人涉诉为由拒绝贷款展期，但具体涉诉材料尚未给我。",
        "facts": [
            {
                "fact_id": "F1",
                "gap_type": "aligned",
                "client_belief": "银行提到保证人涉诉。",
                "court_record": "银行在拒绝展期通知中列明保证人涉诉风险。",
            },
            {
                "fact_id": "F2",
                "gap_type": "disputed",
                "client_belief": "客户认为银行无权以保证人涉诉为由拒绝展期。",
                "court_record": "银行可依展期协议进行风险审查。",
            },
        ],
    }
    dialogue = (
        "客户（开场）：银行以保证人涉诉为由拒绝贷款展期，但具体涉诉材料尚未给我。\n"
        "律师（第1轮）：展期协议是否明确约定了利息迟延后果？\n"
        "客户：我不知道，手头没有完整协议，需要核实。\n"
        "律师（第2轮）：您如何理解银行拒绝展期的权利？\n"
        "客户：按我的理解，银行无权以保证人涉诉为由拒绝展期。"
    )
    memo = (
        "- 银行曾以保证人涉诉为由拒绝贷款展期。\n"
        "- 保证人涉诉的具体情况和材料尚待核实。\n"
        "- 客户称展期协议未约定利息迟延后果。\n"
        "- 展期协议是否约定利息迟延后果。\n"
        "- 客户本轮陈述（尚未独立核验）：按我的理解，银行无权以保证人涉诉为由拒绝展期。\n"
        "- 若协议确有相关约定，应结合条款进一步分析。"
    )
    prompt = build_official_grounding_judgment_prompt(case, dialogue, memo)
    error = "unknown"
    prior_value: dict[str, Any] | None = None
    for attempt in range(2):
        active = client if attempt == 0 else repair_client
        try:
            response = active.generate_json(
                purpose=(
                    f"qualification_{anchor_id}_grounding"
                    if attempt == 0
                    else f"qualification_{anchor_id}_grounding_repair"
                ),
                system_prompt=system_prompt,
                user_prompt=(
                    prompt
                    if attempt == 0
                    else prompt
                    + "\n\n请按案件事实或对话任一支持的官方并集口径重做三分类。"
                    + f"结构或方向错误：{error[:800]}。上一次待修对象："
                    + json.dumps(prior_value, ensure_ascii=False, sort_keys=True)
                ),
                output_schema=official_grounding_judgment_schema(memo_claim_spans(memo)),
            )
            prior_value = response.value
            grounded, _, unsupported, _ = _validate_grounding(
                response.value, memo, dialogue=dialogue
            )
        except Exception as exc:
            error = f"{type(exc).__name__}:{exc}"
            continue
        grounded_text = "\n".join(item.claim for item in grounded)
        unsupported_text = "\n".join(item.claim for item in unsupported)
        passed = (
            "以保证人涉诉为由" in grounded_text
            and "保证人涉诉的具体情况" not in unsupported_text
            and "客户称展期协议未约定" in unsupported_text
            and "展期协议是否约定" not in unsupported_text
            and "银行无权以保证人涉诉为由" in grounded_text
            and "若协议确有相关约定" not in unsupported_text
        )
        row = {
            "anchor_id": anchor_id,
            "passed": passed,
            "grounded_claims": [item.claim for item in grounded],
            "unsupported_claims": [item.claim for item in unsupported],
            "request_sha256": response.request_sha256,
            "repair_used": attempt > 0,
        }
        if not passed and attempt == 0:
            error = f"classification_direction_mismatch:{row}"
            continue
        return (
            row,
            None if passed else f"{anchor_id}:classification_direction_mismatch:{row}",
        )
    return (
        {"anchor_id": anchor_id, "passed": False, "repair_used": True},
        f"{anchor_id}:failed_bounded_repair:{error}",
    )


def _rubric_prompt(case: dict[str, Any], dialogue: str, memo: str) -> str:
    criteria = case["evaluation_criteria"]
    return (
        "按DLawBench口径逐项判断律师是否执行预期追问、memo是否覆盖预期法律问题。"
        "律师只要在对话中提出了对应的实质问题就算执行，不因客户回答不完整或表示不知道而扣分。"
        "memo只要实质覆盖对应评分点就计1。每项只能为0或1。"
        "必须从第1项到最后一项逐项独立比对，不能只检查前几项；同义实质覆盖也计1。"
        "analysis只需用一两句话引用律师问题或memo短片段作为总体关键依据；分数必须与analysis一致。"
        "输出列表长度必须与输入列表一致。严格只输出以下英文键JSON，不得改名或增加键："
        '{"memo_expectation_scores":[0或1,...],'
        '"expected_action_scores":[0或1,...],"analysis":"一两句话"}。\n\n'
        "预期追问：\n"
        + "\n".join(
            f"{index + 1}. {item}" for index, item in enumerate(criteria["expected_inquiries"])
        )
        + "\n\nmemo评分点：\n"
        + "\n".join(
            f"{index + 1}. {item}" for index, item in enumerate(criteria["memo_expectations"])
        )
        + f"\n\n完整对话：\n{dialogue}\n\n最终memo：\n{memo}"
        + "\n\n最终逐项复核：若最终memo逐字出现或实质同义覆盖某一memo评分点，"
        "该项必须记1；不得因另一个评分点的材料不足连带将它记0。"
    )


def _fact_prompt(case: dict[str, Any], dialogue: str, memo: str) -> str:
    return build_fact_judgment_prompt(case, dialogue, memo)


def _validate_rubric(
    case: dict[str, Any], value: dict[str, Any], memo: str
) -> tuple[RubricJudgment, list[str]]:
    result = RubricJudgment.model_validate(value)
    criteria = case["evaluation_criteria"]
    expected = len(criteria["expected_inquiries"])
    memos = len(criteria["memo_expectations"])
    if len(result.expected_action_scores) != expected:
        raise ValueError("inquiry rubric length mismatch")
    if len(result.memo_expectation_scores) != memos:
        raise ValueError("memo rubric length mismatch")
    return normalize_verbatim_rubric_scores(
        result, criteria["memo_expectations"], memo
    )


def _validate_facts(
    case: dict[str, Any], value: dict[str, Any], memo: str
) -> tuple[FactJudgment, list[str]]:
    all_ids = {fact["fact_id"] for fact in case["facts"]}
    normalized, exact_normalizations = normalize_verbatim_fact_decisions(
        value, case, memo
    )
    result, parser_normalizations = parse_fact_judgment(normalized, all_ids)
    issues = fact_wire_contract_issues(normalized, case, memo)
    if issues:
        raise ValueError("; ".join(issues))
    return result, [*parser_normalizations, *exact_normalizations]


def _validate_source_audit_grounding(
    value: dict[str, Any], memo: str, dialogue: str,
) -> tuple[
    list[GroundedClaim],
    list[GroundedClaim],
    list[UnsupportedClaim],
    list[str],
]:
    spans = memo_claim_spans(memo)
    normalized, normalizations = normalize_exact_visible_grounding(
        value, spans, dialogue
    )
    result = parse_grounding_judgment(normalized, spans)
    issues = grounding_wire_contract_issues(normalized, memo)
    if issues:
        raise ValueError("; ".join(issues))
    return (*result, normalizations)


def _validate_grounding(
    value: dict[str, Any],
    memo: str,
    claim_spans: dict[str, str] | None = None,
    *,
    dialogue: str = "",
) -> tuple[
    list[GroundedClaim],
    list[GroundedClaim],
    list[UnsupportedClaim],
    list[str],
]:
    spans = claim_spans or memo_claim_spans(memo)
    normalized, normalizations = normalize_official_grounding_contract(
        value, spans, dialogue
    )
    grounded, unsupported = parse_official_grounding_judgment(
        normalized, spans
    )
    issues = grounding_wire_contract_issues(normalized, memo)
    if issues:
        raise ValueError("; ".join(issues))
    return grounded, [], unsupported, normalizations


def _mean_binary(values: list[int]) -> float:
    return statistics.fmean(values) if values else 0.0


def _qualify_case(
    client: StructuredOpenAIClient,
    repair_client: StructuredOpenAIClient,
    system_prompt: str,
    case: dict[str, Any],
    case_index: int,
    case_count: int,
    grounding_claims_per_call: int,
) -> tuple[dict[str, Any], list[str]]:
    print(
        f"case_start index={case_index}/{case_count} id={case['id']} domain={case['legal_domain']}",
        flush=True,
    )
    scenario_results: dict[str, Any] = {}
    failures: list[str] = []
    for scenario, builder in (
        ("full", _full_dialogue_and_memo),
        ("sparse", _sparse_dialogue_and_memo),
        ("dialogue_only", _dialogue_only_facts_and_generic_memo),
        ("attributed_client", _attributed_client_memo),
        ("poisoned", _poisoned_dialogue_and_memo),
    ):
        print(f"scenario_start id={case['id']} scenario={scenario}", flush=True)
        dialogue, memo = builder(case)
        try:
            rubric = None
            rubric_response = None
            rubric_error: Exception | None = None
            rubric_repair_used = False
            rubric_normalizations: list[str] = []
            prior_rubric_value: dict[str, Any] | None = None
            for attempt in range(2):
                try:
                    active_client = client if attempt == 0 else repair_client
                    response = active_client.generate_json(
                        purpose=(
                            f"qualification_{case['id']}_{scenario}_rubric"
                            if attempt == 0
                            else f"qualification_{case['id']}_{scenario}_rubric_repair"
                        ),
                        system_prompt=system_prompt,
                        user_prompt=(
                            _rubric_prompt(case, dialogue, memo)
                            + (
                                "\n\n上一次输出不完整或内部不一致。不要展开长推理，直接逐项核对分数、证据和长度。"
                                "上一次待修对象："
                                + json.dumps(prior_rubric_value, ensure_ascii=False, sort_keys=True)
                                if attempt
                                else ""
                            )
                        ),
                        output_schema=rubric_judgment_schema(
                            len(case["evaluation_criteria"]["expected_inquiries"]),
                            len(case["evaluation_criteria"]["memo_expectations"]),
                        ),
                    )
                    prior_rubric_value = response.value
                    rubric, rubric_normalizations = _validate_rubric(
                        case, response.value, memo
                    )
                    rubric_response = response
                    rubric_repair_used = attempt > 0
                    break
                except Exception as exc:
                    rubric_error = exc
            if rubric is None or rubric_response is None:
                raise ValueError(f"rubric failed bounded repair: {rubric_error}")

            facts = None
            fact_response = None
            fact_error: Exception | None = None
            fact_repair_used = False
            fact_normalizations: list[str] = []
            prior_fact_value: dict[str, Any] | None = None
            for attempt in range(2):
                try:
                    active_client = client if attempt == 0 else repair_client
                    response = active_client.generate_json(
                        purpose=(
                            f"qualification_{case['id']}_{scenario}_facts"
                            if attempt == 0
                            else f"qualification_{case['id']}_{scenario}_facts_repair"
                        ),
                        system_prompt=system_prompt,
                        user_prompt=(
                            _fact_prompt(case, dialogue, memo)
                            + (
                                "\n\n上一次输出不完整或集合不合法。不要展开长推理，直接核对事实分区和全部主张分区。"
                                f"上一次具体结构错误：{str(fact_error)[:800]}。"
                                "上一次待修对象："
                                + json.dumps(prior_fact_value, ensure_ascii=False, sort_keys=True)
                                if attempt
                                else ""
                            )
                        ),
                        output_schema=fact_judgment_schema(
                            {fact["fact_id"] for fact in case["facts"]}
                        ),
                    )
                    prior_fact_value = response.value
                    facts, fact_normalizations = _validate_facts(case, response.value, memo)
                    fact_response = response
                    fact_repair_used = attempt > 0
                    break
                except Exception as exc:
                    fact_error = exc
            if facts is None or fact_response is None:
                raise ValueError(f"facts failed bounded repair: {fact_error}")

            grounding_responses = []
            grounding_repair_used = False
            visible_grounded_claims: list[GroundedClaim] = []
            benchmark_only_grounded_claims: list[GroundedClaim] = []
            unsupported_claims: list[UnsupportedClaim] = []
            grounding_normalizations: list[str] = []
            frozen_spans = memo_claim_spans(memo)
            grounding_chunks = chunk_claim_spans(
                frozen_spans, grounding_claims_per_call
            )
            grounding_chunk_rows: list[dict[str, Any]] = []
            for chunk_index, chunk_spans in enumerate(grounding_chunks, start=1):
                grounding_response = None
                grounding_error: Exception | None = None
                prior_grounding_value: dict[str, Any] | None = None
                for attempt in range(2):
                    try:
                        active_client = client if attempt == 0 else repair_client
                        response = active_client.generate_json(
                            purpose=(
                                f"qualification_{case['id']}_{scenario}_grounding_"
                                f"chunk_{chunk_index}"
                                if attempt == 0
                                else f"qualification_{case['id']}_{scenario}_grounding_"
                                f"chunk_{chunk_index}_repair"
                            ),
                            system_prompt=system_prompt,
                            user_prompt=(
                                build_official_grounding_judgment_prompt(
                                    case,
                                    dialogue,
                                    memo,
                                    claim_spans=chunk_spans,
                                    chunk_index=chunk_index,
                                    chunk_count=len(grounding_chunks),
                                )
                                + (
                                    "\n\n上一次输出不完整或本块主张分区不合法。不要评价事实覆盖"
                                    "或法律正确性，直接对本块每个冻结claim ID重做grounded、"
                                    "unsupported、non_claim三类互斥分类。上一次具体结构错误："
                                    f"{str(grounding_error)[:800]}。上一次待修对象："
                                    + json.dumps(
                                        prior_grounding_value,
                                        ensure_ascii=False,
                                        sort_keys=True,
                                    )
                                    if attempt
                                    else ""
                                )
                            ),
                            output_schema=official_grounding_judgment_schema(
                                chunk_spans
                            ),
                        )
                        prior_grounding_value = response.value
                        (
                            chunk_grounded,
                            chunk_benchmark_only,
                            chunk_unsupported,
                            chunk_normalizations,
                        ) = _validate_grounding(
                            response.value,
                            memo,
                            chunk_spans,
                            dialogue=dialogue,
                        )
                        grounding_response = response
                        visible_grounded_claims.extend(chunk_grounded)
                        benchmark_only_grounded_claims.extend(chunk_benchmark_only)
                        unsupported_claims.extend(chunk_unsupported)
                        grounding_normalizations.extend(chunk_normalizations)
                        grounding_repair_used = grounding_repair_used or attempt > 0
                        grounding_chunk_rows.append(
                            {
                                "chunk_index": chunk_index,
                                "claim_ids": list(chunk_spans),
                                "request_sha256": response.request_sha256,
                                "cache_hit": response.cache_hit,
                                "repair_used": attempt > 0,
                            }
                        )
                        grounding_responses.append(response)
                        break
                    except Exception as exc:
                        grounding_error = exc
                if grounding_response is None:
                    raise ValueError(
                        "grounding failed bounded repair: "
                        f"chunk={chunk_index}/{len(grounding_chunks)}; "
                        f"claim_ids={list(chunk_spans)}; {grounding_error}"
                    )
            traced_ids = [
                claim_id
                for chunk in grounding_chunk_rows
                for claim_id in chunk["claim_ids"]
            ]
            if traced_ids != list(frozen_spans):
                raise ValueError("grounding chunks changed frozen claim order or coverage")
            facts.grounded_claims = [
                *visible_grounded_claims,
                *benchmark_only_grounded_claims,
            ]
            facts.benchmark_only_grounded_claims = benchmark_only_grounded_claims
            facts.unsupported_claims = unsupported_claims
        except Exception as exc:  # qualification records every fail-closed reason
            failure = f"{case['id']}:{scenario}:{type(exc).__name__}:{exc}"
            failures.append(failure)
            print(f"scenario_failed {failure}", flush=True)
            continue
        scenario_results[scenario] = {
            "inquiry": _mean_binary(rubric.expected_action_scores),
            "issue_resolution": _mean_binary(rubric.memo_expectation_scores),
            "fact_coverage": len(facts.covered_fact_ids) / len(case["facts"]),
            "fact_resolution": len(facts.correct_fact_ids) / len(case["facts"]),
            "substantive_fact_coverage": len(facts.substantive_covered_fact_ids)
            / len(case["facts"]),
            "substantive_fact_resolution": len(facts.substantive_correct_fact_ids)
            / len(case["facts"]),
            "incorrect_fact_count": len(facts.incorrect_facts),
            "unsupported_claim_count": len(facts.unsupported_claims),
            "grounded_claim_count": len(facts.grounded_claims),
            "visible_grounded_claim_count": len(facts.grounded_claims)
            - len(facts.benchmark_only_grounded_claims),
            "benchmark_only_grounded_claim_count": len(
                facts.benchmark_only_grounded_claims
            ),
            "rubric_repair_used": rubric_repair_used,
            "fact_repair_used": fact_repair_used,
            "grounding_repair_used": grounding_repair_used,
            "rubric_normalizations": rubric_normalizations,
            "fact_normalizations": fact_normalizations,
            "grounding_normalizations": grounding_normalizations,
            "rubric_request_sha256": rubric_response.request_sha256,
            "rubric_cache_hit": rubric_response.cache_hit,
            "fact_request_sha256": fact_response.request_sha256,
            "fact_cache_hit": fact_response.cache_hit,
            "grounding_chunks": grounding_chunk_rows,
        }
        print(f"scenario_complete id={case['id']} scenario={scenario}", flush=True)
    return (
        {
            "case_id": case["id"],
            "legal_domain": case["legal_domain"],
            "scenarios": scenario_results,
        },
        failures,
    )


def _parse_args(
    judge_role: dict[str, Any], argv: list[str] | None = None
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    frozen_base_url = str(judge_role["base_url"])
    parser.add_argument(
        "--base-url",
        choices=(frozen_base_url,),
        default=frozen_base_url,
        help="formal qualification endpoint is frozen by configs/models/roles.yaml",
    )
    frozen_model = str(judge_role["model_id"])
    parser.add_argument(
        "--model",
        choices=(frozen_model,),
        default=frozen_model,
        help="formal qualification model is frozen by configs/models/roles.yaml",
    )
    parser.add_argument(
        "--cases",
        type=int,
        choices=(SEMANTIC_JUDGE_QUALIFICATION_CASE_COUNT,),
        default=SEMANTIC_JUDGE_QUALIFICATION_CASE_COUNT,
        help=(
            "formal panel size is frozen; only "
            f"{SEMANTIC_JUDGE_QUALIFICATION_CASE_COUNT} is accepted"
        ),
    )
    parser.add_argument(
        "--workers",
        type=int,
        choices=(8,),
        default=8,
        help="formal qualification concurrency is frozen at 8 workers",
    )
    frozen_effort = str(judge_role["reasoning_effort"])
    parser.add_argument(
        "--reasoning-effort",
        choices=(frozen_effort,),
        default=frozen_effort,
        help="formal qualification effort is frozen by configs/models/roles.yaml",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "reports/artifacts/local_judge_qualification.json",
    )
    return parser.parse_args(argv)


def main() -> None:
    judge_role = yaml.safe_load((ROOT / "configs/models/roles.yaml").read_text(encoding="utf-8"))[
        "roles"
    ]["semantic_judge"]
    qualification_protocol = int(judge_role["qualification_protocol"])
    args = _parse_args(judge_role)
    client = StructuredOpenAIClient(
        base_url=args.base_url,
        model=args.model,
        model_revision=str(judge_role["revision"]),
        cache_root=(
            ROOT
            / "runs/qualification_cache/local_judge"
            / args.reasoning_effort
            / f"protocol_{qualification_protocol}"
        ),
        reasoning_effort=args.reasoning_effort,
        max_completion_tokens=int(judge_role["max_completion_tokens"]),
        timeout_seconds=900,
        retries=0,
        expected_model_root=ROOT / str(judge_role["local_snapshot"]),
        expected_max_model_len=int(judge_role["runtime_limits"]["max_model_len"]),
    )
    repair_client = StructuredOpenAIClient(
        base_url=args.base_url,
        model=args.model,
        model_revision=str(judge_role["revision"]),
        cache_root=(
            ROOT
            / "runs/qualification_cache/local_judge"
            / args.reasoning_effort
            / f"protocol_{qualification_protocol}"
        ),
        reasoning_effort=args.reasoning_effort,
        max_completion_tokens=int(judge_role["repair_max_completion_tokens"]),
        timeout_seconds=900,
        retries=0,
        expected_model_root=ROOT / str(judge_role["local_snapshot"]),
        expected_max_model_len=int(judge_role["runtime_limits"]["max_model_len"]),
    )
    preflight = client.preflight()
    if not preflight["ready"]:
        raise SystemExit(f"local judge is unavailable: {preflight}")
    system_prompt = (ROOT / "configs/prompts/semantic_judge_zh.txt").read_text(encoding="utf-8")
    cases = _select_training_cases()
    grounding_claims_per_call = int(judge_role["grounding_claims_per_call"])
    print(
        f"qualification_start model={args.model} cases={len(cases)} "
        f"scenario_units={len(cases) * 5} "
        f"grounding_claims_per_call={grounding_claims_per_call} "
        "bounded_repair_attempts=2",
        flush=True,
    )
    if args.workers < 1:
        raise SystemExit("--workers must be positive")
    ordered_rows: list[dict[str, Any] | None] = [None] * len(cases)
    failures: list[str] = []
    with ThreadPoolExecutor(
        max_workers=args.workers, thread_name_prefix="judge_qualification"
    ) as pool:
        pending = {
            pool.submit(
                _qualify_case,
                client,
                repair_client,
                system_prompt,
                case,
                index + 1,
                len(cases),
                grounding_claims_per_call,
            ): index
            for index, case in enumerate(cases)
        }
        for future in as_completed(pending):
            index = pending[future]
            row, case_failures = future.result()
            ordered_rows[index] = row
            failures.extend(case_failures)
    rows = [row for row in ordered_rows if row is not None]
    anchor_rows: list[dict[str, Any]] = []
    for anchor in _legal_direction_anchors():
        row, failure = _qualify_legal_anchor(client, repair_client, system_prompt, anchor)
        anchor_rows.append(row)
        if failure:
            failures.append(failure)
    visible_source_anchor, visible_source_failure = _qualify_visible_source_anchor(
        client, repair_client, system_prompt
    )
    # The production scorer intentionally uses DLawBench's union grounding task:
    # case facts OR the complete dialogue can ground a memo claim.  Fine-grained
    # attribution to opening/later-dialogue/benchmark-only sources is retained as
    # a frozen diagnostic, but it does not enter reward, group selection, candidate
    # acceptance, or final metrics.  Do not let an unused auxiliary task qualify or
    # disqualify the judge used by the production data path.
    diagnostic_failures = (
        [visible_source_failure] if visible_source_failure is not None else []
    )
    official_grounding_anchor, official_grounding_failure = (
        _qualify_official_grounding_anchor(client, repair_client, system_prompt)
    )
    if official_grounding_failure:
        failures.append(official_grounding_failure)

    complete_rows = [row for row in rows if len(row["scenarios"]) == 5]
    full_quality = [
        statistics.fmean(
            [
                row["scenarios"]["full"]["inquiry"],
                row["scenarios"]["full"]["issue_resolution"],
                row["scenarios"]["full"]["fact_resolution"],
            ]
        )
        for row in complete_rows
    ]
    sparse_quality = [
        statistics.fmean(
            [
                row["scenarios"]["sparse"]["inquiry"],
                row["scenarios"]["sparse"]["issue_resolution"],
            ]
        )
        for row in complete_rows
    ]
    dialogue_only_coverage = [
        row["scenarios"]["dialogue_only"]["fact_coverage"] for row in complete_rows
    ]
    full_unsupported = [
        row["scenarios"]["full"]["unsupported_claim_count"] for row in complete_rows
    ]
    attributed_unsupported = [
        row["scenarios"]["attributed_client"]["unsupported_claim_count"] for row in complete_rows
    ]
    attributed_grounded = [
        row["scenarios"]["attributed_client"]["grounded_claim_count"] for row in complete_rows
    ]
    full_inquiry = [row["scenarios"]["full"]["inquiry"] for row in complete_rows]
    full_issue = [row["scenarios"]["full"]["issue_resolution"] for row in complete_rows]
    full_fact_resolution = [row["scenarios"]["full"]["fact_resolution"] for row in complete_rows]
    full_substantive_fact_resolution = [
        row["scenarios"]["full"]["substantive_fact_resolution"] for row in complete_rows
    ]
    dialogue_only_substantive_coverage = [
        row["scenarios"]["dialogue_only"]["substantive_fact_coverage"] for row in complete_rows
    ]
    poisoned_detection = [
        int(
            row["scenarios"]["poisoned"]["incorrect_fact_count"] > 0
            and row["scenarios"]["poisoned"]["unsupported_claim_count"] > 0
        )
        for row in complete_rows
    ]
    repair_flags = [
        bool(scenario[repair_key])
        for row in complete_rows
        for scenario in row["scenarios"].values()
        for repair_key in (
            "rubric_repair_used",
            "fact_repair_used",
            "grounding_repair_used",
        )
    ]
    fact_normalization_flags = [
        bool(scenario["fact_normalizations"])
        for row in complete_rows
        for scenario in row["scenarios"].values()
    ]
    rubric_normalization_flags = [
        bool(scenario["rubric_normalizations"])
        for row in complete_rows
        for scenario in row["scenarios"].values()
    ]
    grounding_normalization_flags = [
        any(
            item.endswith("_from_unsupported")
            for item in scenario["grounding_normalizations"]
        )
        for row in complete_rows
        for scenario in row["scenarios"].values()
    ]
    grounding_any_normalization_flags = [
        bool(scenario["grounding_normalizations"])
        for row in complete_rows
        for scenario in row["scenarios"].values()
    ]
    monotonic = [
        int(full > sparse) for full, sparse in zip(full_quality, sparse_quality, strict=True)
    ]
    aggregates = {
        "schema_complete_rate": len(complete_rows) / len(rows) if rows else 0.0,
        "full_quality_mean": statistics.fmean(full_quality) if full_quality else 0.0,
        "sparse_quality_mean": statistics.fmean(sparse_quality) if sparse_quality else 1.0,
        "dialogue_only_coverage_mean": (
            statistics.fmean(dialogue_only_coverage) if dialogue_only_coverage else 1.0
        ),
        "full_unsupported_claim_mean": (
            statistics.fmean(full_unsupported) if full_unsupported else 1.0
        ),
        "attributed_unsupported_claim_mean": (
            statistics.fmean(attributed_unsupported) if attributed_unsupported else 1.0
        ),
        "attributed_grounded_claim_case_min": (
            min(attributed_grounded) if attributed_grounded else 0
        ),
        "poisoned_detection_rate": (
            statistics.fmean(poisoned_detection) if poisoned_detection else 0.0
        ),
        "monotonic_case_rate": statistics.fmean(monotonic) if monotonic else 0.0,
        "repair_rate": statistics.fmean(repair_flags) if repair_flags else 1.0,
        "fact_normalization_rate": (
            statistics.fmean(fact_normalization_flags) if fact_normalization_flags else 1.0
        ),
        "rubric_normalization_rate": (
            statistics.fmean(rubric_normalization_flags)
            if rubric_normalization_flags
            else 1.0
        ),
        "grounding_normalization_rate": (
            statistics.fmean(grounding_normalization_flags)
            if grounding_normalization_flags
            else 1.0
        ),
        # Descriptive only: grounded->non_claim taxonomy normalisation changes
        # the claim denominator but cannot hide an unsupported assertion.  The
        # thresholded rate above retains the original 5% cap specifically for
        # safety-critical unsupported->grounded/non_claim corrections.
        "grounding_any_normalization_rate": (
            statistics.fmean(grounding_any_normalization_flags)
            if grounding_any_normalization_flags
            else 1.0
        ),
        "full_inquiry_case_min": min(full_inquiry) if full_inquiry else 0.0,
        "full_issue_case_min": min(full_issue) if full_issue else 0.0,
        "full_fact_resolution_case_min": (
            min(full_fact_resolution) if full_fact_resolution else 0.0
        ),
        "full_substantive_fact_resolution_case_min": (
            min(full_substantive_fact_resolution) if full_substantive_fact_resolution else 0.0
        ),
        "dialogue_only_substantive_coverage_mean": (
            statistics.fmean(dialogue_only_substantive_coverage)
            if dialogue_only_substantive_coverage
            else 1.0
        ),
        "legal_direction_anchor_rate": (
            statistics.fmean(int(row["passed"]) for row in anchor_rows) if anchor_rows else 0.0
        ),
        "visible_source_anchor_rate": float(visible_source_anchor["passed"]),
        "official_grounding_anchor_rate": float(official_grounding_anchor["passed"]),
    }
    thresholds = {
        "schema_complete_rate": 1.0,
        "full_quality_mean_min": 0.9,
        "sparse_quality_mean_max": 0.2,
        "dialogue_only_coverage_mean_max": 0.2,
        "full_unsupported_claim_mean_max": 0.0,
        "attributed_unsupported_claim_mean_max": 0.0,
        "attributed_grounded_claim_case_min": 1,
        "poisoned_detection_rate_min": 0.75,
        "monotonic_case_rate_min": 1.0,
        "repair_rate_max": 0.05,
        "fact_normalization_rate_max": 0.05,
        "rubric_normalization_rate_max": 0.05,
        "grounding_normalization_rate_max": 0.05,
        "full_inquiry_case_min": 1.0,
        "full_issue_case_min": 1.0,
        "full_fact_resolution_case_min": 1.0,
        "full_substantive_fact_resolution_case_min": 1.0,
        "dialogue_only_substantive_coverage_mean_max": 0.0,
        "legal_direction_anchor_rate_min": 1.0,
        "official_grounding_anchor_rate_min": 1.0,
    }
    threshold_checks = {
        "schema_complete_rate": aggregates["schema_complete_rate"]
        == thresholds["schema_complete_rate"],
        "full_quality_mean_min": aggregates["full_quality_mean"]
        >= thresholds["full_quality_mean_min"],
        "sparse_quality_mean_max": aggregates["sparse_quality_mean"]
        <= thresholds["sparse_quality_mean_max"],
        "dialogue_only_coverage_mean_max": aggregates["dialogue_only_coverage_mean"]
        <= thresholds["dialogue_only_coverage_mean_max"],
        "full_unsupported_claim_mean_max": aggregates["full_unsupported_claim_mean"]
        <= thresholds["full_unsupported_claim_mean_max"],
        "attributed_unsupported_claim_mean_max": aggregates["attributed_unsupported_claim_mean"]
        <= thresholds["attributed_unsupported_claim_mean_max"],
        "attributed_grounded_claim_case_min": aggregates["attributed_grounded_claim_case_min"]
        >= thresholds["attributed_grounded_claim_case_min"],
        "poisoned_detection_rate_min": aggregates["poisoned_detection_rate"]
        >= thresholds["poisoned_detection_rate_min"],
        "monotonic_case_rate_min": aggregates["monotonic_case_rate"]
        >= thresholds["monotonic_case_rate_min"],
        "repair_rate_max": aggregates["repair_rate"] <= thresholds["repair_rate_max"],
        "fact_normalization_rate_max": aggregates["fact_normalization_rate"]
        <= thresholds["fact_normalization_rate_max"],
        "rubric_normalization_rate_max": aggregates["rubric_normalization_rate"]
        <= thresholds["rubric_normalization_rate_max"],
        "grounding_normalization_rate_max": aggregates["grounding_normalization_rate"]
        <= thresholds["grounding_normalization_rate_max"],
        "full_inquiry_case_min": aggregates["full_inquiry_case_min"]
        >= thresholds["full_inquiry_case_min"],
        "full_issue_case_min": aggregates["full_issue_case_min"]
        >= thresholds["full_issue_case_min"],
        "full_fact_resolution_case_min": aggregates["full_fact_resolution_case_min"]
        >= thresholds["full_fact_resolution_case_min"],
        "full_substantive_fact_resolution_case_min": aggregates[
            "full_substantive_fact_resolution_case_min"
        ]
        >= thresholds["full_substantive_fact_resolution_case_min"],
        "dialogue_only_substantive_coverage_mean_max": aggregates[
            "dialogue_only_substantive_coverage_mean"
        ]
        <= thresholds["dialogue_only_substantive_coverage_mean_max"],
        "legal_direction_anchor_rate_min": aggregates["legal_direction_anchor_rate"]
        >= thresholds["legal_direction_anchor_rate_min"],
        "official_grounding_anchor_rate_min": aggregates[
            "official_grounding_anchor_rate"
        ]
        >= thresholds["official_grounding_anchor_rate_min"],
    }
    threshold_failures = [name for name, ok in threshold_checks.items() if not ok]
    passed = not failures and not threshold_failures
    qualification_components = semantic_judge_qualification_component_hashes(ROOT)
    report = {
        "schema_version": SEMANTIC_JUDGE_QUALIFICATION_REPORT_SCHEMA_VERSION,
        "qualification_protocol": qualification_protocol,
        "passed": passed,
        "model": args.model,
        "base_url": args.base_url,
        "model_revision": str(judge_role["revision"]),
        "judge_qualification_contract_sha256": semantic_judge_qualification_sha256(
            ROOT, judge_role
        ),
        **qualification_components,
        "semantic_judge_role_sha256": canonical_json_sha256(judge_role),
        "reasoning_effort": args.reasoning_effort,
        "max_completion_tokens": int(judge_role["max_completion_tokens"]),
        "repair_max_completion_tokens": int(judge_role["repair_max_completion_tokens"]),
        "workers": args.workers,
        "preflight": preflight,
        "training_cases_only": True,
        "qualification_case_ids": [
            case_id for case_id, _ in SEMANTIC_JUDGE_QUALIFICATION_CASES
        ],
        "qualification_legal_domains": [
            legal_domain for _, legal_domain in SEMANTIC_JUDGE_QUALIFICATION_CASES
        ],
        "case_count": len(rows),
        "thresholds": thresholds,
        "aggregates": aggregates,
        "failures": failures,
        "diagnostic_failures": diagnostic_failures,
        "threshold_failures": threshold_failures,
        "cases": rows,
        "legal_direction_anchors": anchor_rows,
        "visible_source_anchor": visible_source_anchor,
        "official_grounding_anchor": official_grounding_anchor,
    }
    try:
        RunStore.immutable_json(args.output, report)
    except FileExistsError as exc:
        raise SystemExit(
            "refusing to overwrite a different immutable judge qualification; "
            "preserve the existing report under reports/historical before a new "
            f"contract attempt: {args.output}"
        ) from exc
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if passed else 2)


if __name__ == "__main__":
    main()
