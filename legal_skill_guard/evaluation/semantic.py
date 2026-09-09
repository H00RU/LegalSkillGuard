"""DLawBench-compatible semantic scoring with a blinded structured judge."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from hashlib import sha256
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from legal_skill_guard.agent.stateful_policy import POLICY_FALLBACK_REASONS
from legal_skill_guard.data_visibility import find_online_payload_forbidden_fields
from legal_skill_guard.evolution.reward import (
    RewardComponents,
    RewardParameters,
    RewardResult,
    balanced_elicitation,
    trajectory_reward,
)
from legal_skill_guard.inference.structured_openai_client import (
    StructuredModelInvocationError,
)
from legal_skill_guard.schemas.experiment import (
    ResearchTrajectory,
    trajectory_target_kind_provenance_issues,
)


class EvaluationModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RubricJudgment(EvaluationModel):
    memo_expectation_scores: list[Literal[0, 1]]
    expected_action_scores: list[Literal[0, 1]]
    analysis: str


def rubric_judgment_schema(action_count: int, memo_count: int) -> dict[str, Any]:
    """Constrain per-case rubric arrays to their exact declared cardinalities."""

    if action_count < 0 or memo_count < 0:
        raise ValueError("rubric cardinalities cannot be negative")
    schema = RubricJudgment.model_json_schema()
    properties = schema["properties"]
    for name, count in (
        ("expected_action_scores", action_count),
        ("memo_expectation_scores", memo_count),
    ):
        properties[name]["minItems"] = count
        properties[name]["maxItems"] = count
    return schema


class IncorrectFact(EvaluationModel):
    fact_id: str
    memo_excerpt: str
    reason: str


class UnsupportedClaim(EvaluationModel):
    claim: str
    reason: str


class GroundedClaim(EvaluationModel):
    claim: str
    basis: str


class FactJudgment(EvaluationModel):
    covered_fact_ids: list[str]
    missed_fact_ids: list[str]
    correct_fact_ids: list[str]
    incorrect_facts: list[IncorrectFact]
    unresolved_fact_ids: list[str] = Field(default_factory=list)
    substantive_covered_fact_ids: list[str] = Field(default_factory=list)
    substantive_missed_fact_ids: list[str] = Field(default_factory=list)
    substantive_correct_fact_ids: list[str] = Field(default_factory=list)
    substantive_incorrect_fact_ids: list[str] = Field(default_factory=list)
    substantive_unresolved_fact_ids: list[str] = Field(default_factory=list)
    grounded_claims: list[GroundedClaim]
    benchmark_only_grounded_claims: list[GroundedClaim] = Field(default_factory=list)
    unsupported_claims: list[UnsupportedClaim]

    @model_validator(mode="before")
    @classmethod
    def accept_consistent_legacy_total_claims(cls, value: Any) -> Any:
        """Load artifacts written before computed fields were excluded from storage."""

        if not isinstance(value, dict) or "total_claims" not in value:
            return value
        normalized = dict(value)
        stored = normalized.pop("total_claims")
        derived = len(normalized.get("grounded_claims") or []) + len(
            normalized.get("unsupported_claims") or []
        )
        if stored != derived:
            raise ValueError(
                f"stored total_claims={stored} differs from derived total_claims={derived}"
            )
        return normalized

    @computed_field
    @property
    def total_claims(self) -> int:
        """Derive the denominator from the explicit official-style partition."""

        return len(self.grounded_claims) + len(self.unsupported_claims)


def fact_judgment_schema(fact_ids: set[str] | list[str] | tuple[str, ...]) -> dict[str, Any]:
    """Require one keyed decision for every fact instead of fragile parallel ID lists."""

    ordered = sorted(set(fact_ids))
    if not ordered:
        raise ValueError("fact judgment requires at least one fact ID")
    decision = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "discovery",
            "accuracy",
            "substantive_discovery",
            "substantive_accuracy",
            "memo_excerpt",
            "reason",
        ],
        "properties": {
            "discovery": {"type": "string", "enum": ["covered", "missed"]},
            "accuracy": {
                "type": "string",
                "enum": ["correct", "incorrect", "not_applicable"],
            },
            "substantive_discovery": {
                "type": "string",
                "enum": ["covered", "missed"],
            },
            "substantive_accuracy": {
                "type": "string",
                "enum": ["correct", "incorrect", "not_applicable"],
            },
            "memo_excerpt": {"type": "string"},
            "reason": {"type": "string"},
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["facts"],
        "properties": {
            "facts": {
                "type": "object",
                "additionalProperties": False,
                "required": ordered,
                "properties": {fact_id: deepcopy(decision) for fact_id in ordered},
            },
        },
    }


def memo_claim_spans(memo: str) -> dict[str, str]:
    """Freeze auditable memo excerpts before the judge sees hidden case facts."""

    # The typed ledger uses HTML comments as machine-readable boundaries. They
    # and the fixed Markdown section titles are document structure, not factual
    # or legal propositions. Sending fragments such as ``<!`` to the reasoning
    # judge created a recurrent all-reasoning/no-body failure in the first chunk.
    # Remove only these closed structural forms; client attributions, questions,
    # conditional analysis, legal conclusions and advice remain frozen and judged.
    memo = re.sub(r"<!--.*?-->", "", memo, flags=re.DOTALL)
    structural_titles = {
        "案情概要",
        "关键事实",
        "结构化会话事实状态（确定性记录）",
        "法律问题",
        "风险评估",
        "下一步建议",
    }
    spans: dict[str, str] = {}
    seen: set[str] = set()
    for raw in re.split(r"(?<=[。！？!?；])|\n+", memo):
        excerpt = raw.strip()
        title = re.sub(r"^\*{1,3}|\*{1,3}$", "", excerpt).strip()
        if title in structural_titles and re.fullmatch(r"\*{1,3}.*\*{1,3}", excerpt):
            continue
        normalized = re.sub(r"\s+", "", excerpt)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        spans[f"C{len(spans) + 1:03d}"] = excerpt
    if not spans:
        raise ValueError("grounding requires at least one memo span")
    return spans


def grounding_judgment_schema(claim_spans: dict[str, str]) -> dict[str, Any]:
    """Classify every pre-frozen memo span without letting the judge invent text."""

    decision = {
        "type": "object",
        "additionalProperties": False,
        "required": ["classification", "basis"],
        "properties": {
            "classification": {
                "type": "string",
                "enum": [
                    "visible_grounded",
                    "benchmark_only_grounded",
                    "unsupported",
                    "non_claim",
                ],
            },
            "basis": {"type": "string"},
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["claims"],
        "properties": {
            "claims": {
                "type": "object",
                "additionalProperties": False,
                "required": list(claim_spans),
                "properties": {
                    claim_id: deepcopy(decision) for claim_id in claim_spans
                },
            }
        },
    }


def official_grounding_judgment_schema(claim_spans: dict[str, str]) -> dict[str, Any]:
    """DLawBench grounding: case facts OR dialogue support a claim."""

    decision = {
        "type": "object",
        "additionalProperties": False,
        "required": ["classification", "basis"],
        "properties": {
            "classification": {
                "type": "string",
                "enum": ["grounded", "unsupported", "non_claim"],
            },
            "basis": {"type": "string"},
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["claims"],
        "properties": {
            "claims": {
                "type": "object",
                "additionalProperties": False,
                "required": list(claim_spans),
                "properties": {
                    claim_id: deepcopy(decision) for claim_id in claim_spans
                },
            }
        },
    }


def parse_official_grounding_judgment(
    value: dict[str, Any], claim_spans: dict[str, str]
) -> tuple[list[GroundedClaim], list[UnsupportedClaim]]:
    """Parse an exhaustive three-class DLawBench grounding judgment."""

    decisions = value.get("claims")
    if not isinstance(decisions, dict) or set(decisions) != set(claim_spans):
        raise ValueError("official grounding claim IDs do not match frozen memo spans")
    grounded: list[GroundedClaim] = []
    unsupported: list[UnsupportedClaim] = []
    for claim_id, excerpt in claim_spans.items():
        decision = decisions[claim_id]
        classification = decision.get("classification")
        basis = str(decision.get("basis") or "")
        if classification == "grounded":
            grounded.append(GroundedClaim(claim=excerpt, basis=basis))
        elif classification == "unsupported":
            unsupported.append(UnsupportedClaim(claim=excerpt, reason=basis))
        elif classification != "non_claim":
            raise ValueError(
                f"invalid official grounding classification for {claim_id}: "
                f"{classification}"
            )
    return grounded, unsupported


def normalize_exact_visible_grounding(
    value: dict[str, Any],
    claim_spans: dict[str, str],
    dialogue: str,
) -> tuple[dict[str, Any], list[str]]:
    """Correct only exact, explicitly attributed copies of client answers.

    This is deliberately narrower than semantic matching: an excerpt must consist
    solely of a known attribution prefix followed by one complete client answer.
    It therefore cannot make a paraphrase, a lawyer question, or an additional
    memo assertion source-grounded. Corrections are returned for audit and rate
    caps in judge qualification.
    """

    claims = value.get("claims")
    if not isinstance(claims, dict) or set(claims) != set(claim_spans):
        return value, []

    client_answers = _dialogue_client_answers(dialogue)

    if not client_answers:
        return value, []

    prefixes = (
        "客户本轮陈述（尚未独立核验）：",
        "客户单方陈述（尚未核验）：",
        "据客户在咨询中的单方陈述：",
        "据客户在咨询中的陈述：",
        "据客户单方陈述：",
        "据客户陈述：",
        "据其陈述：",
        "客户陈述：",
        "客户称：",
    )
    normalized = deepcopy(value)
    changes: list[str] = []
    for claim_id, excerpt in claim_spans.items():
        decision = normalized["claims"][claim_id]
        if decision.get("classification") not in {
            "unsupported",
            "benchmark_only_grounded",
        }:
            continue
        attributed = excerpt.strip()
        matched_prefix = next(
            (prefix for prefix in prefixes if attributed.startswith(prefix)), None
        )
        if matched_prefix is None:
            continue
        attributed = attributed[len(matched_prefix) :].strip()
        source = client_answers.get(_canonical_source_text(attributed))
        if source is None:
            continue
        decision["classification"] = "visible_grounded"
        decision["basis"] = f"deterministic exact client answer: {source}"
        changes.append(f"{claim_id}:exact_attributed_client_answer")
    return normalized, changes


def _dialogue_client_answers(dialogue: str) -> dict[str, str]:
    """Index complete visible client answers for narrow extractive grounding."""

    answers: dict[str, str] = {}
    answer_index = 0
    for raw_line in dialogue.splitlines():
        line = raw_line.strip()
        if not line.startswith("客户："):
            continue
        answer_index += 1
        answer = line.removeprefix("客户：").strip()
        if answer:
            answers[_canonical_source_text(answer)] = f"dialogue round {answer_index}"
    return answers


def _dialogue_client_clauses(dialogue: str) -> dict[str, str]:
    """Index exact opening/answer clauses without attempting semantic matching."""

    clauses: dict[str, str] = {}
    answer_index = 0
    for raw_line in dialogue.splitlines():
        line = raw_line.strip()
        if line.startswith("客户（开场）："):
            text = line.removeprefix("客户（开场）：").strip()
            basis = "client opening"
        elif line.startswith("客户："):
            answer_index += 1
            text = line.removeprefix("客户：").strip()
            basis = f"dialogue round {answer_index}"
        else:
            continue
        for clause in re.split(r"(?<=[。！？!?])", text):
            clause = clause.strip()
            if clause:
                clauses[_canonical_source_text(clause)] = basis
    return clauses


def _clearly_nonclaim_memo_span(excerpt: str) -> bool:
    """Recognise only explicit questions, limitations and open hypotheses.

    These are categories already fixed as ``non_claim`` by the grounding prompt.
    The deterministic check prevents a frozen judge from converting an open legal
    issue or an epistemic limitation into an alleged fabricated case fact.  It is
    intentionally inapplicable to attributed client/counterparty statements.
    """

    value = re.sub(r"^\s*(?:[-*]|\d+[.\u3001]|[\uff08(]\d+[\uff09)])\s*", "", excerpt).strip()
    attributed = re.search(
        r"(?:\u5ba2\u6237(?:\u672c\u8f6e)?(?:\u79f0|\u8868\u793a|\u4e3b\u5f20|\u8ba4\u4e3a|\u8fa9\u79f0|\u89e3\u91ca|\u9648\u8ff0)|"
        r"\u636e\u5ba2\u6237.{0,6}(?:\u9648\u8ff0|\u8f6c\u8ff0)|"
        r"(?:\u5bf9\u65b9|\u76f8\u5bf9\u65b9|\u4fdd\u9669\u516c\u53f8|\u516c\u53f8|\u653f\u5e9c|\u6cd5\u9662)"
        r".{0,8}(?:\u79f0|\u8868\u793a|\u4e3b\u5f20|\u8ba4\u4e3a|\u8fa9\u79f0|\u89e3\u91ca|\u9648\u8ff0))",
        value,
    )
    if attributed:
        return False
    if value.startswith(
        ("\u82e5", "\u5982\u679c", "\u5047\u8bbe", "\u5728\u2026\u2026\u60c5\u51b5\u4e0b")
    ):
        return True
    if re.search(
        r"(?:\u5c1a\u672a\u660e\u786e|\u5c1a\u672a\u786e\u8ba4|\u5c1a\u5f85|\u6709\u5f85|\u5f85\u6838\u5b9e|\u5f85\u6838\u9a8c|"
        r"\u4fe1\u606f\u4e0d\u8db3|\u73b0\u6709\u4fe1\u606f.{0,8}\u4e0d\u8db3|\u65e0\u6cd5\u5224\u65ad|\u4e0d\u80fd\u786e\u8ba4|\u65e0\u6cd5\u786e\u8ba4)",
        value,
    ):
        return True
    # A frozen span is already split at a full stop, question mark or semicolon.
    # With no attributed speaker and an explicit interrogative operator, the
    # remaining unit is an open legal/factual issue, not an affirmative claim.
    return bool(
        re.search(
            r"(?:\u662f\u5426|\u80fd\u5426|\u53ef\u5426|\u6709\u65e0|\u5982\u4f55|\u4f55\u79cd|\u54ea\u4e9b)",
            value,
        )
    )


def normalize_official_grounding_contract(
    value: dict[str, Any],
    claim_spans: dict[str, str],
    dialogue: str,
) -> tuple[dict[str, Any], list[str]]:
    """Enforce deterministic edges of the official case-or-dialogue contract.

    The model still performs every semantic grounding decision.  Normalisation is
    limited to two mechanically auditable cases: an exact attributed copy of a
    visible client answer is grounded, and an explicit question/limitation is not
    a factual claim.  Both changes are persisted in the evaluation audit trail.
    """

    claims = value.get("claims")
    if not isinstance(claims, dict) or set(claims) != set(claim_spans):
        return value, []
    client_answers = _dialogue_client_answers(dialogue)
    client_clauses = _dialogue_client_clauses(dialogue)
    prefixes = (
        "客户开场陈述（尚未独立核验）：",
        "\u5ba2\u6237\u672c\u8f6e\u9648\u8ff0\uff08\u5c1a\u672a\u72ec\u7acb\u6838\u9a8c\uff09\uff1a",
        "\u5ba2\u6237\u5355\u65b9\u9648\u8ff0\uff08\u5c1a\u672a\u6838\u9a8c\uff09\uff1a",
        "\u636e\u5ba2\u6237\u5728\u54a8\u8be2\u4e2d\u7684\u5355\u65b9\u9648\u8ff0\uff1a",
        "\u636e\u5ba2\u6237\u5728\u54a8\u8be2\u4e2d\u7684\u9648\u8ff0\uff1a",
        "\u636e\u5ba2\u6237\u5355\u65b9\u9648\u8ff0\uff1a",
        "\u636e\u5ba2\u6237\u9648\u8ff0\uff1a",
        "\u636e\u5176\u9648\u8ff0\uff1a",
        "\u5ba2\u6237\u9648\u8ff0\uff1a",
        "\u5ba2\u6237\u79f0\uff1a",
    )
    normalized = deepcopy(value)
    changes: list[str] = []
    for claim_id, excerpt in claim_spans.items():
        decision = normalized["claims"][claim_id]
        attributed = re.sub(
            r"^\s*(?:[-*]|\d+[.、]|[（(]\d+[）)])\s*",
            "",
            excerpt,
        ).strip()
        matched_prefix = next(
            (prefix for prefix in prefixes if attributed.startswith(prefix)), None
        )
        if matched_prefix is not None:
            answer = attributed[len(matched_prefix) :].strip()
            source = client_answers.get(
                _canonical_source_text(answer)
            ) or client_clauses.get(_canonical_source_text(answer))
            if source is not None and decision.get("classification") != "grounded":
                prior = str(decision.get("classification"))
                decision["classification"] = "grounded"
                decision["basis"] = f"deterministic exact client answer: {source}"
                changes.append(
                    f"{claim_id}:exact_attributed_client_answer_from_{prior}"
                )
                continue
        bare_excerpt = attributed
        exact_clause_source = client_clauses.get(_canonical_source_text(bare_excerpt))
        if exact_clause_source is not None and decision.get("classification") != "grounded":
            prior = str(decision.get("classification"))
            decision["classification"] = "grounded"
            decision["basis"] = f"deterministic exact client clause: {exact_clause_source}"
            changes.append(f"{claim_id}:exact_client_clause_from_{prior}")
            continue
        if (
            decision.get("classification") != "non_claim"
            and _clearly_nonclaim_memo_span(excerpt)
        ):
            prior = str(decision.get("classification"))
            decision["classification"] = "non_claim"
            decision["basis"] = "deterministic explicit question or information limitation"
            changes.append(f"{claim_id}:explicit_nonclaim_from_{prior}")
    return normalized, changes


def _canonical_source_text(text: str) -> str:
    return re.sub(r"[\s。！？!?；;]+$", "", re.sub(r"\s+", "", text))


def parse_grounding_judgment(
    value: dict[str, Any], claim_spans: dict[str, str] | None = None,
) -> tuple[list[GroundedClaim], list[GroundedClaim], list[UnsupportedClaim]]:
    """Parse the keyed four-way wire contract, retaining legacy artifact support."""

    if "claims" in value:
        if claim_spans is None:
            raise ValueError("keyed grounding judgment requires frozen claim spans")
        decisions = value.get("claims")
        if not isinstance(decisions, dict) or set(decisions) != set(claim_spans):
            raise ValueError("grounding claim IDs do not match frozen memo spans")
        visible: list[GroundedClaim] = []
        benchmark_only: list[GroundedClaim] = []
        unsupported: list[UnsupportedClaim] = []
        for claim_id, excerpt in claim_spans.items():
            decision = decisions[claim_id]
            classification = decision.get("classification")
            basis = str(decision.get("basis") or "")
            if classification == "visible_grounded":
                visible.append(GroundedClaim(claim=excerpt, basis=basis))
            elif classification == "benchmark_only_grounded":
                benchmark_only.append(GroundedClaim(claim=excerpt, basis=basis))
            elif classification == "unsupported":
                unsupported.append(UnsupportedClaim(claim=excerpt, reason=basis))
            elif classification != "non_claim":
                raise ValueError(
                    f"invalid grounding classification for {claim_id}: {classification}"
                )
        return visible, benchmark_only, unsupported

    visible = [
        GroundedClaim.model_validate(item)
        for item in value.get("visible_grounded_claims", [])
    ]
    benchmark_only = [
        GroundedClaim.model_validate(item)
        for item in value.get("benchmark_only_grounded_claims", [])
    ]
    unsupported = [
        UnsupportedClaim.model_validate(item) for item in value.get("unsupported_claims", [])
    ]
    partitions = [
        {item.claim for item in visible},
        {item.claim for item in benchmark_only},
        {item.claim for item in unsupported},
    ]
    overlap = (partitions[0] & partitions[1]) | (partitions[0] & partitions[2]) | (
        partitions[1] & partitions[2]
    )
    if overlap:
        raise ValueError(f"grounding partition overlap: {sorted(overlap)}")
    return visible, benchmark_only, unsupported


def grounding_wire_contract_issues(value: dict[str, Any], memo: str) -> list[str]:
    """Require every judged claim to be an auditable excerpt of the final memo."""

    normalized_memo = re.sub(r"\s+", "", memo)
    issues: list[str] = []
    for field in (
        "visible_grounded_claims",
        "benchmark_only_grounded_claims",
        "unsupported_claims",
    ):
        items = value.get(field)
        if not isinstance(items, list):
            continue
        for index, item in enumerate(items):
            claim = str(item.get("claim") or "") if isinstance(item, dict) else ""
            normalized_claim = re.sub(r"\s+", "", claim)
            if not normalized_claim or normalized_claim not in normalized_memo:
                issues.append(f"{field}[{index}]:claim_not_verbatim_memo_excerpt")
    return issues


def parse_fact_judgment(value: dict[str, Any], all_ids: set[str]) -> tuple[FactJudgment, list[str]]:
    """Convert the exact keyed wire contract while retaining legacy artifact support."""

    if "facts" not in value:
        normalized, changes = normalize_fact_judgment_duplicates(value)
        result = FactJudgment.model_validate(normalized)
        if not result.substantive_covered_fact_ids and not result.substantive_missed_fact_ids:
            result.substantive_covered_fact_ids = list(result.covered_fact_ids)
            result.substantive_missed_fact_ids = list(result.missed_fact_ids)
            result.substantive_correct_fact_ids = list(result.correct_fact_ids)
            result.substantive_incorrect_fact_ids = [
                item.fact_id for item in result.incorrect_facts
            ]
        issues = fact_partition_issues(result, all_ids)
        if issues:
            raise ValueError("; ".join(issues))
        return result, changes

    facts = value.get("facts")
    if not isinstance(facts, dict) or set(facts) != all_ids:
        missing = sorted(all_ids - set(facts or {})) if isinstance(facts, dict) else sorted(all_ids)
        unknown = sorted(set(facts or {}) - all_ids) if isinstance(facts, dict) else []
        raise ValueError(f"keyed fact decision mismatch: missing={missing}, unknown={unknown}")
    covered: list[str] = []
    missed: list[str] = []
    correct: list[str] = []
    incorrect: list[dict[str, str]] = []
    substantive_covered: list[str] = []
    substantive_missed: list[str] = []
    substantive_correct: list[str] = []
    substantive_incorrect: list[str] = []
    unresolved: list[str] = []
    substantive_unresolved: list[str] = []
    for fact_id in sorted(all_ids):
        item = facts[fact_id]
        if not isinstance(item, dict):
            raise ValueError(f"fact decision is not an object: {fact_id}")
        discovery = item.get("discovery")
        accuracy = item.get("accuracy")
        if discovery == "missed":
            if accuracy != "not_applicable":
                raise ValueError(f"missed fact must use not_applicable accuracy: {fact_id}")
            missed.append(fact_id)
        elif discovery == "covered":
            covered.append(fact_id)
            if accuracy == "correct":
                correct.append(fact_id)
            elif accuracy == "incorrect":
                incorrect.append(
                    {
                        "fact_id": fact_id,
                        "memo_excerpt": str(item.get("memo_excerpt") or ""),
                        "reason": str(item.get("reason") or ""),
                    }
                )
            elif accuracy == "not_applicable":
                unresolved.append(fact_id)
            else:
                raise ValueError(
                    f"covered fact needs correct/incorrect/not_applicable accuracy: {fact_id}"
                )
        else:
            raise ValueError(f"invalid discovery decision: {fact_id}:{discovery}")
        substantive_discovery = item.get("substantive_discovery")
        substantive_accuracy = item.get("substantive_accuracy")
        if substantive_discovery == "missed":
            if substantive_accuracy != "not_applicable":
                raise ValueError(
                    f"substantively missed fact must use not_applicable accuracy: {fact_id}"
                )
            substantive_missed.append(fact_id)
        elif substantive_discovery == "covered":
            substantive_covered.append(fact_id)
            if substantive_accuracy == "correct":
                substantive_correct.append(fact_id)
            elif substantive_accuracy == "incorrect":
                substantive_incorrect.append(fact_id)
            elif substantive_accuracy == "not_applicable":
                substantive_unresolved.append(fact_id)
            else:
                raise ValueError(
                    "substantively covered fact needs correct/incorrect/not_applicable "
                    f"accuracy: {fact_id}"
                )
        else:
            raise ValueError(
                f"invalid substantive discovery decision: {fact_id}:{substantive_discovery}"
            )
    result = FactJudgment.model_validate(
        {
            "covered_fact_ids": covered,
            "missed_fact_ids": missed,
            "correct_fact_ids": correct,
            "incorrect_facts": incorrect,
            "unresolved_fact_ids": unresolved,
            "substantive_covered_fact_ids": substantive_covered,
            "substantive_missed_fact_ids": substantive_missed,
            "substantive_correct_fact_ids": substantive_correct,
            "substantive_incorrect_fact_ids": substantive_incorrect,
            "substantive_unresolved_fact_ids": substantive_unresolved,
            "grounded_claims": value.get("grounded_claims", []),
            "unsupported_claims": value.get("unsupported_claims", []),
        }
    )
    return result, []


def fact_judgment_to_keyed_decisions(
    judgment: FactJudgment, fact_ids: set[str]
) -> dict[str, dict[str, str]]:
    """Canonicalize a validated legacy judgment for lossless chunk merging."""

    covered = set(judgment.covered_fact_ids)
    correct = set(judgment.correct_fact_ids)
    unresolved = set(judgment.unresolved_fact_ids)
    substantive_covered = set(judgment.substantive_covered_fact_ids)
    substantive_correct = set(judgment.substantive_correct_fact_ids)
    substantive_unresolved = set(judgment.substantive_unresolved_fact_ids)
    incorrect = {item.fact_id: item for item in judgment.incorrect_facts}
    substantive_incorrect = set(judgment.substantive_incorrect_fact_ids)
    decisions: dict[str, dict[str, str]] = {}
    for fact_id in sorted(fact_ids):
        item = incorrect.get(fact_id)
        decisions[fact_id] = {
            "discovery": "covered" if fact_id in covered else "missed",
            "accuracy": (
                "correct"
                if fact_id in correct
                else "incorrect"
                if fact_id in incorrect
                else "not_applicable"
            ),
            "substantive_discovery": (
                "covered" if fact_id in substantive_covered else "missed"
            ),
            "substantive_accuracy": (
                "correct"
                if fact_id in substantive_correct
                else "incorrect"
                if fact_id in substantive_incorrect
                else "not_applicable"
            ),
            "memo_excerpt": item.memo_excerpt if item is not None else "",
            "reason": item.reason if item is not None else "",
        }
        if fact_id in unresolved:
            decisions[fact_id]["accuracy"] = "not_applicable"
        if fact_id in substantive_unresolved:
            decisions[fact_id]["substantive_accuracy"] = "not_applicable"
    return decisions


def fact_wire_contract_issues(
    value: dict[str, Any], evaluator_case: dict[str, Any], memo: str
) -> list[str]:
    """Reject self-contradictory keyed fact decisions before scoring.

    This validates the judge's own classification; it never imputes a score. A
    failed first judgment goes through the same bounded repair path, and a second
    failure stops the unit.
    """

    decisions = value.get("facts")
    if not isinstance(decisions, dict):
        return []
    issues: list[str] = []
    for fact in evaluator_case["facts"]:
        fact_id = str(fact["fact_id"])
        decision = decisions.get(fact_id)
        if not isinstance(decision, dict):
            continue
        discovery = decision.get("discovery")
        reason = str(decision.get("reason") or "").strip()
        # Reject a ``missed`` decision only when the rationale explicitly says
        # the memo itself inverted or misstated the proposition.  A broad
        # ``memo ... 错误`` window is unsound in legal text: e.g. “memo未提及虚假
        # 材料导致的错误裁定” uses 错误 to modify the court ruling, not the memo.
        memo_inversion = any(
            re.search(pattern, reason, flags=re.IGNORECASE)
            for pattern in (
                r"\b(?:memo|memorandum)\s+(?:incorrectly|wrongly|falsely|"
                r"contradictorily)\s+(?:states?|says?|asserts?|claims?|describes?)\b",
                r"\b(?:statement|claim|conclusion)\s+in\s+(?:the\s+)?(?:memo|"
                r"memorandum)\s+is\s+(?:incorrect|reversed|opposite|contradictory)\b",
                r"(?:memo|备忘录|文中)(?:错误|不正确|相反)地?"
                r"(?:表述|陈述|认为|认定|声称|写明)",
                r"(?:memo|备忘录|文中)(?:的)?(?:表述|陈述|说法|结论).{0,8}"
                r"(?:写反|说反|相反|错误|不符)",
                r"(?:memo|备忘录|文中)(?:写反|说反)",
            )
        )
        if discovery == "missed" and memo_inversion:
            issues.append(f"{fact_id}:missed_reason_describes_incorrect_proposition")
        court_record = str(fact["court_record"]).strip()
        if court_record and court_record in memo:
            expected = {
                "discovery": "covered",
                "accuracy": "correct",
                "substantive_discovery": "covered",
                "substantive_accuracy": "correct",
            }
            mismatches = [
                f"{field}={decision.get(field)}"
                for field, target in expected.items()
                if decision.get(field) != target
            ]
            if mismatches:
                issues.append(
                    f"{fact_id}:verbatim_court_record_misclassified:"
                    + ",".join(mismatches)
                )
    return issues


def normalize_verbatim_fact_decisions(
    value: dict[str, Any], evaluator_case: dict[str, Any], memo: str
) -> tuple[dict[str, Any], list[str]]:
    """Apply only exact court-record matches that need no semantic judgment."""

    normalized = deepcopy(value)
    decisions = normalized.get("facts")
    if not isinstance(decisions, dict):
        return normalized, []
    changes: list[str] = []
    for fact in evaluator_case["facts"]:
        fact_id = str(fact["fact_id"])
        court_record = str(fact["court_record"]).strip()
        decision = decisions.get(fact_id)
        if not court_record or court_record not in memo or not isinstance(decision, dict):
            continue
        expected = {
            "discovery": "covered",
            "accuracy": "correct",
            "substantive_discovery": "covered",
            "substantive_accuracy": "correct",
        }
        if any(decision.get(field) != target for field, target in expected.items()):
            decision.update(expected)
            decision["memo_excerpt"] = court_record
            decision["reason"] = "最终memo逐字包含案件记录"
            changes.append(f"{fact_id}:verbatim_court_record_exact_match")
    return normalized, changes


def normalize_verbatim_rubric_scores(
    judgment: RubricJudgment, memo_expectations: list[str], memo: str
) -> tuple[RubricJudgment, list[str]]:
    """Set only literal memo-expectation matches to their definitionally exact score."""

    scores = list(judgment.memo_expectation_scores)
    changes: list[str] = []
    for index, (expectation, score) in enumerate(
        zip(memo_expectations, scores, strict=True)
    ):
        if expectation in memo and score != 1:
            scores[index] = 1
            changes.append(f"memo_expectation_{index + 1}:verbatim_exact_match")
    if not changes:
        return judgment, []
    return judgment.model_copy(update={"memo_expectation_scores": scores}), changes


class OfficialMetrics(EvaluationModel):
    fact_coverage: float
    inquiry: float
    elicitation: float
    fact_resolution: float
    issue_resolution: float
    resolution: float
    fidelity: float


class TrainingMetrics(EvaluationModel):
    """Provenance-locked metrics used only for evolution rewards.

    Official DLawBench discovery intentionally asks whether the final memo talks
    about a benchmark fact.  That remains useful for external comparability, but
    it cannot establish that the online lawyer actually elicited the fact.  The
    evolution metrics therefore use the simulator's persisted disclosure IDs and
    only credit memo resolution inside that disclosed set.
    """

    substantive_fact_coverage: float
    inquiry: float
    elicitation: float
    substantive_fact_resolution: float
    issue_resolution: float
    resolution: float


class TrainingFactProvenance(EvaluationModel):
    """Exact fact sets separating dialogue learning signal from memo-only hits."""

    elicited_hidden_fact_ids: list[str]
    resolved_elicited_fact_ids: list[str]
    memo_only_substantive_fact_ids: list[str]


class MechanismSignals(EvaluationModel):
    """Judge-independent F/G signals used to explain the training mechanism.

    ``F`` is an online disclosure that the simulator explicitly persisted as a
    newly elicited benchmark fact.  ``E`` is a clean first inquiry into a planned
    evidence/third-party target with an observable (non-withheld) client outcome;
    ``G`` is the subset of E whose outcome is ``unavailable``.  G is therefore an
    identified evidence gap, not a failed fact-elicitation turn.

    These fields are deliberately outside ``OfficialMetrics``, ``TrainingMetrics``
    and ``RewardResult``: they diagnose *how* a trajectory obtained useful
    information without changing DLawBench's seven public metrics or any reward
    weight.
    """

    source_trajectory_schema_version: int
    target_kind_available: bool
    newly_elicited_fact_ids: list[str]
    newly_elicited_fact_count: int = Field(ge=0)
    evidence_or_third_party_target_ids: list[str]
    evidence_or_third_party_target_count: int | None = Field(default=None, ge=0)
    eligible_evidence_inquiry_target_ids: list[str]
    eligible_evidence_inquiry_count: int | None = Field(default=None, ge=0)
    identified_evidence_gap_ids: list[str]
    identified_evidence_gap_turns: list[int]
    identified_evidence_gap_count: int = Field(ge=0)
    identified_evidence_gap_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    true_zero_identified_evidence_gap: bool | None = None
    evidence_gap_outcome: Literal[
        "unavailable_legacy_target_kind",
        "unavailable_invalid_target_kind_provenance",
        "not_applicable_no_eligible_evidence_inquiries",
        "true_zero",
        "identified",
    ]

    @model_validator(mode="after")
    def validate_derived_partition(self) -> MechanismSignals:
        if self.newly_elicited_fact_count != len(self.newly_elicited_fact_ids):
            raise ValueError("newly elicited fact count differs from persisted IDs")
        if self.identified_evidence_gap_count != len(
            self.identified_evidence_gap_ids
        ):
            raise ValueError("identified evidence gap count differs from persisted IDs")
        if len(self.identified_evidence_gap_turns) != len(
            self.identified_evidence_gap_ids
        ):
            raise ValueError("identified evidence gap turns differ from persisted IDs")
        if not set(self.identified_evidence_gap_ids).issubset(
            self.eligible_evidence_inquiry_target_ids
        ):
            raise ValueError("identified gap IDs must be eligible evidence inquiries")
        expected_evidence_count = (
            len(self.evidence_or_third_party_target_ids)
            if self.target_kind_available
            else None
        )
        if self.evidence_or_third_party_target_count != expected_evidence_count:
            raise ValueError("evidence target count differs from persisted IDs/protocol")
        expected_eligible_count = (
            len(self.eligible_evidence_inquiry_target_ids)
            if self.target_kind_available
            else None
        )
        if self.eligible_evidence_inquiry_count != expected_eligible_count:
            raise ValueError("eligible evidence inquiry count differs from persisted IDs")
        if not set(self.eligible_evidence_inquiry_target_ids).issubset(
            self.evidence_or_third_party_target_ids
        ):
            raise ValueError("eligible evidence inquiries must be classified targets")
        if not self.target_kind_available:
            unavailable_outcome = (
                "unavailable_legacy_target_kind"
                if self.source_trajectory_schema_version < 15
                else "unavailable_invalid_target_kind_provenance"
            )
            expected = (None, None, unavailable_outcome)
        elif not expected_eligible_count:
            expected = (
                None,
                None,
                "not_applicable_no_eligible_evidence_inquiries",
            )
        elif not self.identified_evidence_gap_count:
            expected = (0.0, True, "true_zero")
        else:
            expected = (
                round(
                    self.identified_evidence_gap_count / expected_eligible_count,
                    6,
                ),
                False,
                "identified",
            )
        actual = (
            self.identified_evidence_gap_rate,
            self.true_zero_identified_evidence_gap,
            self.evidence_gap_outcome,
        )
        if actual != expected:
            raise ValueError(
                f"evidence gap outcome differs from derived partition: {actual} != {expected}"
            )
        return self


def _state_before_evidence_target_ids(step: Any) -> set[str]:
    facts = getattr(step, "state_before", {}).get("facts", [])
    return {
        str(item.get("fact_id"))
        for item in facts
        if isinstance(item, dict)
        and item.get("fact_id")
        and item.get("target_kind") == "evidence_or_third_party"
    }


def _blocking_step_health(step: Any) -> bool:
    """Whether the persisted effective action crossed a blocking health path."""

    violations = [
        *getattr(step, "policy_health_violations", []),
        *getattr(step, "post_skill_health_violations", []),
    ]
    if any(not str(item).startswith("warning:") for item in violations):
        return True
    changes = getattr(getattr(step, "action_decision", None), "changes", [])
    if any(
        isinstance(change, dict) and change.get("source") == "post_skill_health_gate"
        for change in changes
    ):
        return True
    return any(
        not bool(getattr(result, "passed", False))
        and str(getattr(result, "severity", "error")) in {"error", "severe"}
        for result in getattr(step, "verifier_results", [])
    )


def derive_mechanism_signals(
    trajectory: ResearchTrajectory,
    valid_fact_ids: set[str] | None = None,
) -> MechanismSignals:
    """Derive auditable F/G behavior signals without invoking a semantic judge.

    Protocol-15 is the first trajectory schema that requires ``target_kind`` at
    the investigation-plan boundary.  Earlier artifacts must remain
    uninterpretable for G rather than silently becoming a zero-evidence case.
    """

    trajectory_schema = int(getattr(trajectory, "schema_version", 0) or 0)
    target_kind_provenance_issues = trajectory_target_kind_provenance_issues(
        trajectory
    )
    target_kind_available = bool(
        trajectory_schema >= 15 and not target_kind_provenance_issues
    )
    elicited: set[str] = set()
    for step in trajectory.steps:
        if getattr(step, "client_response_kind", None) != "new_hidden_fact":
            continue
        for raw_fact_id in getattr(step, "client_selected_fact_ids", []):
            fact_id = str(raw_fact_id)
            if valid_fact_ids is not None:
                if fact_id in valid_fact_ids:
                    elicited.add(fact_id)
            elif fact_id.startswith("F"):
                elicited.add(fact_id)

    evidence_targets: set[str] = set()
    if target_kind_available:
        initial_plan = getattr(trajectory, "initial_investigation_plan", None)
        for observation in getattr(initial_plan, "observations", []):
            if getattr(observation, "target_kind", None) == "evidence_or_third_party":
                evidence_targets.add(str(observation.fact_id))
        for step in trajectory.steps:
            evidence_targets.update(_state_before_evidence_target_ids(step))

    eligible_evidence_inquiry_ids: set[str] = set()
    identified_ids: set[str] = set()
    identified_turns: list[int] = []
    seen_effective_inquiry_targets: set[str] = set()
    if target_kind_available:
        for step in trajectory.steps:
            final_action = step.action_decision.final
            target_id = str(final_action.target_id or "")
            interactive = final_action.action_type in {"ask", "clarify", "verify"}
            evidence_in_current_state = target_id in _state_before_evidence_target_ids(step)
            asked_before = {
                str(item)
                for item in getattr(step, "state_before", {}).get("asked_targets", [])
            }
            first_inquiry = bool(
                target_id
                and target_id not in seen_effective_inquiry_targets
                and target_id not in asked_before
            )
            clean_execution = bool(
                not getattr(step, "client_safe_fallback", False)
                and not policy_fallback_used(step)
                and not _blocking_step_health(step)
            )
            eligible_response = getattr(step, "client_response_kind", None) in {
                "new_hidden_fact",
                "repeated_hidden_fact",
                "opening_repeat",
                "unavailable",
            }
            if (
                interactive
                and evidence_in_current_state
                and first_inquiry
                and clean_execution
                and eligible_response
            ):
                eligible_evidence_inquiry_ids.add(target_id)
            if (
                interactive
                and evidence_in_current_state
                and first_inquiry
                and getattr(step, "client_response_kind", None) == "unavailable"
                and clean_execution
            ):
                identified_ids.add(target_id)
                identified_turns.append(int(step.turn))
            if interactive and target_id:
                seen_effective_inquiry_targets.add(target_id)

    evidence_count = len(evidence_targets) if target_kind_available else None
    eligible_evidence_count = (
        len(eligible_evidence_inquiry_ids) if target_kind_available else None
    )
    gap_count = len(identified_ids)
    if not target_kind_available:
        gap_rate = None
        true_zero = None
        outcome = (
            "unavailable_legacy_target_kind"
            if trajectory_schema < 15
            else "unavailable_invalid_target_kind_provenance"
        )
    elif not eligible_evidence_count:
        gap_rate = None
        true_zero = None
        outcome = "not_applicable_no_eligible_evidence_inquiries"
    elif gap_count == 0:
        gap_rate = 0.0
        true_zero = True
        outcome = "true_zero"
    else:
        gap_rate = round(gap_count / eligible_evidence_count, 6)
        true_zero = False
        outcome = "identified"
    return MechanismSignals(
        source_trajectory_schema_version=trajectory_schema,
        target_kind_available=target_kind_available,
        newly_elicited_fact_ids=sorted(elicited),
        newly_elicited_fact_count=len(elicited),
        evidence_or_third_party_target_ids=sorted(evidence_targets),
        evidence_or_third_party_target_count=evidence_count,
        eligible_evidence_inquiry_target_ids=sorted(eligible_evidence_inquiry_ids),
        eligible_evidence_inquiry_count=eligible_evidence_count,
        identified_evidence_gap_ids=sorted(identified_ids),
        identified_evidence_gap_turns=sorted(identified_turns),
        identified_evidence_gap_count=gap_count,
        identified_evidence_gap_rate=gap_rate,
        true_zero_identified_evidence_gap=true_zero,
        evidence_gap_outcome=outcome,
    )


class SafetyMetrics(EvaluationModel):
    premature_final_rate: float
    unsupported_claim_rate: float
    belief_as_fact_rate: float
    repeated_question_rate: float
    critical_fact_recall: float
    hidden_field_leak: bool


class OperationalMetrics(EvaluationModel):
    policy_repair_rate: float
    policy_fallback_rate: float
    client_repair_rate: float
    client_fallback_rate: float
    memo_retry: bool
    memo_guardrail_intervention: bool
    memo_fallback: bool


def policy_fallback_used(step: Any) -> bool:
    """Count every deterministic policy fallback, including post-skill rewrites."""

    proposed = getattr(step, "proposed_action", None)
    if getattr(proposed, "reason", None) in POLICY_FALLBACK_REASONS:
        return True
    decision = getattr(step, "action_decision", None)
    final = getattr(decision, "final", None)
    if getattr(final, "reason", None) in POLICY_FALLBACK_REASONS:
        return True
    return any(
        change.get("source") == "post_skill_health_gate"
        and isinstance(change.get("after"), dict)
        and change["after"].get("reason") in POLICY_FALLBACK_REASONS
        for change in (getattr(decision, "changes", None) or [])
    )


class GroundingChunkTrace(EvaluationModel):
    """Auditable provenance for one bounded claim-classification request."""

    chunk_index: int = Field(ge=1)
    claim_ids: list[str] = Field(min_length=1)
    request_sha256: str
    response_sha256: str
    attempts: int = Field(ge=1)


class FactChunkTrace(EvaluationModel):
    """Auditable provenance for one bounded fact-classification request."""

    chunk_index: int = Field(ge=1)
    fact_ids: list[str] = Field(min_length=1)
    request_sha256: str
    response_sha256: str
    attempts: int = Field(ge=1)


def _ordered_trace_digest(values: list[str]) -> str:
    """Retain the legacy single-call hash and bind multi-call recovery in order."""

    if not values:
        raise ValueError("trace digest requires at least one value")
    if len(values) == 1:
        return values[0]
    payload = json.dumps(values, ensure_ascii=False, separators=(",", ":"))
    return sha256(payload.encode("utf-8")).hexdigest()


class TrajectoryEvaluation(EvaluationModel):
    # Version 13 records every exact fact-classification subrequest when a rare
    # output-length exhaustion requires lossless subdivision. Executor cache checks
    # use this exact default and therefore reject rather than reinterpret older
    # evaluations.
    schema_version: Literal[13] = 13
    trajectory_id: str
    case_id: str
    judge_model: str
    judge_qualification_contract_sha256: str
    rubric_request_sha256: str
    rubric_response_sha256: str
    fact_request_sha256: str
    fact_response_sha256: str
    fact_chunks: list[FactChunkTrace] = Field(min_length=1)
    grounding_chunks: list[GroundingChunkTrace] = Field(min_length=1)
    rubric_repair_used: bool = False
    fact_repair_used: bool = False
    grounding_repair_used: bool = False
    rubric_normalizations: list[str] = Field(default_factory=list)
    fact_normalizations: list[str] = Field(default_factory=list)
    grounding_normalizations: list[str] = Field(default_factory=list)
    official_metrics: OfficialMetrics
    training_metrics: TrainingMetrics
    training_fact_provenance: TrainingFactProvenance
    mechanism_signals: MechanismSignals
    safety_metrics: SafetyMetrics
    operational_metrics: OperationalMetrics
    reward: RewardResult
    rubric_judgment: RubricJudgment
    fact_judgment: FactJudgment


class StructuredJudgeResponse(Protocol):
    value: dict[str, Any]
    model: str
    request_sha256: str
    response_sha256: str


class StructuredJudgeClient(Protocol):
    model: str

    def generate_json(
        self,
        *,
        purpose: str,
        system_prompt: str,
        user_prompt: str,
        output_schema: dict[str, Any],
    ) -> StructuredJudgeResponse: ...


def normalize_fact_judgment_duplicates(
    value: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Remove only duplicate partition IDs; never infer a missing classification."""

    normalized = deepcopy(value)
    changes: list[str] = []
    for field in (
        "covered_fact_ids",
        "missed_fact_ids",
        "correct_fact_ids",
        "unresolved_fact_ids",
        "substantive_unresolved_fact_ids",
    ):
        items = normalized.get(field)
        if not isinstance(items, list):
            continue
        unique: list[Any] = []
        seen: set[str] = set()
        for item in items:
            if isinstance(item, str) and item in seen:
                changes.append(f"{field}:removed_duplicate:{item}")
                continue
            unique.append(item)
            if isinstance(item, str):
                seen.add(item)
        normalized[field] = unique

    incorrect = normalized.get("incorrect_facts")
    if isinstance(incorrect, list):
        unique_incorrect: list[Any] = []
        seen_incorrect: set[str] = set()
        for item in incorrect:
            fact_id = item.get("fact_id") if isinstance(item, dict) else None
            if isinstance(fact_id, str) and fact_id in seen_incorrect:
                changes.append(f"incorrect_facts:removed_duplicate:{fact_id}")
                continue
            unique_incorrect.append(item)
            if isinstance(fact_id, str):
                seen_incorrect.add(fact_id)
        normalized["incorrect_facts"] = unique_incorrect
    return normalized, changes


def fact_partition_issues(candidate: FactJudgment, all_ids: set[str]) -> list[str]:
    """Describe exact set defects without assigning any omitted fact a score."""

    covered = set(candidate.covered_fact_ids)
    missed = set(candidate.missed_fact_ids)
    correct = set(candidate.correct_fact_ids)
    incorrect = {item.fact_id for item in candidate.incorrect_facts}
    unresolved = set(candidate.unresolved_fact_ids)
    issues: list[str] = []
    if covered & missed:
        issues.append(f"covered_missed_overlap={sorted(covered & missed)}")
    discovery_union = covered | missed
    if all_ids - discovery_union:
        issues.append(f"missing_discovery_ids={sorted(all_ids - discovery_union)}")
    if discovery_union - all_ids:
        issues.append(f"unknown_discovery_ids={sorted(discovery_union - all_ids)}")
    accuracy_overlap = (correct & incorrect) | (correct & unresolved) | (
        incorrect & unresolved
    )
    if accuracy_overlap:
        issues.append(f"accuracy_partition_overlap={sorted(accuracy_overlap)}")
    accuracy_union = correct | incorrect | unresolved
    if covered - accuracy_union:
        issues.append(f"covered_without_accuracy={sorted(covered - accuracy_union)}")
    if accuracy_union - covered:
        issues.append(f"accuracy_ids_outside_covered={sorted(accuracy_union - covered)}")
    return issues


def trajectory_dialogue(trajectory: ResearchTrajectory) -> str:
    lines = [f"客户（开场）：{trajectory.opening}"]
    for step in trajectory.steps:
        if step.rendered_question:
            lines.append(f"律师（第{step.turn}轮）：{step.rendered_question}")
        if step.client_response:
            lines.append(f"客户：{step.client_response}")
    return "\n".join(lines)


def elicited_hidden_fact_ids(
    trajectory: ResearchTrajectory, valid_fact_ids: set[str]
) -> set[str]:
    """Return facts newly disclosed online, never facts merely mentioned in memo.

    Protocol-12 trajectories persist an explicit response kind.  The legacy
    branch is intentionally narrow: an old artifact with no response kind may be
    interpreted as a new disclosure only when it selected a benchmark F-ID.
    Explicit repeated/opening/unavailable outcomes never receive credit.
    """

    elicited: set[str] = set()
    for step in trajectory.steps:
        response_kind = getattr(step, "client_response_kind", None)
        selected = {
            str(item)
            for item in getattr(step, "client_selected_fact_ids", [])
            if str(item) in valid_fact_ids
        }
        if response_kind == "new_hidden_fact" or (
            response_kind is None and selected and step.client_response is not None
        ):
            elicited.update(selected)
    return elicited


def _fact_block(case: dict[str, Any]) -> str:
    return "\n\n".join(
        (
            f"事实{fact['fact_id']}（{fact['gap_type']}）：\n"
            f"客户认知：{fact['client_belief']}\n"
            f"案件记录：{fact['court_record']}"
        )
        for fact in case["facts"]
    )


def build_fact_judgment_prompt(evaluator_case: dict[str, Any], dialogue: str, memo: str) -> str:
    """Build the official and substantive fact-partition contract."""

    return (
        "严格按DLawBench的集合评估口径判断最终memo。"
        "Discovery只比较案件事实集合A与最终memo集合B：只要memo涉及某事实的相关话题，"
        "即使分析错误也算covered；仅在对话出现而memo未涉及仍算missed。输出facts对象必须"
        "逐个使用给定事实ID作为键，不能遗漏或增加键。每个事实的discovery只能是covered或"
        "missed；Accuracy只对covered事实判断，将memo的分析方向和要点与案件记录对照，填"
        "correct或incorrect；若只是提出相关话题、没有形成可判断真假的事实命题，则Discovery"
        "仍可为covered，但accuracy必须填not_applicable，并作为unresolved而非正确事实。"
        "missed事实的accuracy也必须填not_applicable。incorrect时在"
        "memo_excerpt和reason中给出短证据；其他情况也保留这两个字符串键，可填空字符串。"
        "Accuracy比较不能只看关键词重合，必须分别核对行为主体、相对方、行为、对象和法律"
        "方向；memo若把甲实施的行为写成乙实施，或把主张权利的一方写成承担该行为责任的一方，"
        "即使行为名称相同也必须判incorrect。Accuracy的正确性基准是案件记录，不是客户认知；"
        "对disputed事实，如果memo宣称客户认知已核实、正确或可作为确定结论，而它与案件记录"
        "方向相反，必须判incorrect，不能因memo忠实复述了客户原话而判correct。"
        "Discovery与Accuracy必须正交：memo若讨论同一行为或法律关系但把行为主体、相对方或"
        "责任方向写反，仍然是discovery=covered，同时必须accuracy=incorrect；不能用missed"
        "逃避准确性判断。"
        "除上述官方Discovery/Accuracy外，每个事实还必须独立输出substantive_discovery和"
        "substantive_accuracy，供训练时防止话题占位投机。实质覆盖要求memo实际陈述或分析了"
        "该事实区别于同案其他事实的关键命题，例如具体主体、行为、关系、数额、阶段或法律方向；"
        "如果memo逐字陈述案件记录，或用自然同义表达完整复述案件记录的事实命题，必须判为"
        "substantive_discovery=covered；即使该句很短、案件记录本身概括、或没有另写法律意义分析，"
        "也不能降为missed。实质覆盖要求有事实命题，不要求每个事实都附带独立法律分析。"
        "substantive_discovery与substantive_accuracy也必须正交：只要memo提出了指向该事实的"
        "具体命题，即使主体、行为或法律方向错误，也应判substantive_discovery=covered并在"
        "substantive_accuracy中判incorrect；实质missed只用于没有具体命题的话题占位。"
        "只写同一大类话题、列出待核问题、写‘信息不足/尚待核实’，或用任何案件都适用的条件句，"
        "即使按官方宽口径可算discovery=covered，也必须判substantive_discovery=missed且"
        "substantive_accuracy=not_applicable。实质覆盖后再依据案件记录判断correct或incorrect。"
        "不得在reason中声称memo写了memo_excerpt没有表达的十年婚姻、家庭贡献、具体金额等内容；"
        "memo_excerpt必须是最终memo中真实存在且足以支撑该项判断的短片段。"
        "最终逐项复核：若memo逐字包含某个案件记录，该fact_id必须同时判"
        "discovery=covered、accuracy=correct、substantive_discovery=covered、"
        "substantive_accuracy=correct；不得转而拿相反的客户认知要求memo重复错误。"
        "本任务只做事实覆盖与准确性分区，不做主张溯源，不输出grounded_claims或"
        "unsupported_claims。\n\n"
        f"案件事实：\n{_fact_block(evaluator_case)}\n\n完整对话：\n{dialogue}\n\n"
        f"最终memo：\n{memo}"
    )


def build_official_grounding_judgment_prompt(
    evaluator_case: dict[str, Any],
    dialogue: str,
    memo: str,
    *,
    claim_spans: dict[str, str] | None = None,
    chunk_index: int = 1,
    chunk_count: int = 1,
) -> str:
    """Build the three-class grounding task used by DLawBench-compatible scores."""

    frozen_spans = claim_spans or memo_claim_spans(memo)

    return (
        "按DLawBench口径，只判断最终memo中的本案具体主张是否有依据，不评价事实覆盖率或法律分析"
        "是否正确。程序已经把memo冻结为C001等连续原文片段；必须逐个ID分类，不得遗漏、增加、"
        "改写或生成claim文本。classification只有三类：grounded表示能从案件事实或完整对话任一处"
        "找到实质依据；unsupported表示案件事实和完整对话两处都没有依据；non_claim表示标题、"
        "法条或抽象规则、一般策略、纯待办、信息缺口提示，或没有断言条件已经发生的假设分析。"
        "不要区分依据来自开场、后续对话还是案件事实，也不得因为memo没有标注引文或证据尚待核实"
        "就判unsupported。客户提出问题、律师追问或客户表示不知道，本身不证明问题中的事实成立；"
        "但memo只说某项情况仍需核实或建议补充材料时，这是信息限制或待办，应判non_claim，而不是"
        "事实编造。以若/如果/假设明确引入且没有断言条件已经发生的条件分析也判non_claim。"
        "以‘分析某项边界’、‘评估损失与因果’、‘审查某项依据’等任务动词开头，只要求后续开展"
        "分析而没有给出该分析结果的句子，也是纯待办，应判non_claim；不能因为案件材料没有直接"
        "给出待分析事项的结论就判unsupported。反之，‘分析表明某事实已发生’、‘已经查明’或"
        "‘法院已经作出决定’是在肯定具体结果，仍须按grounded或unsupported判断。"
        "memo‘法律问题’中用‘是否/能否/可否/有无/如何’提出的未决问题也是"
        "non_claim；不得因案件真值已有答案而把‘是否X’改当成memo断言X。"
        "只要memo完整归属为客户陈述，且该原话确实出现在完整对话中，就应判"
        "grounded；即使客户理解与离线案件事实相反，也不能判unsupported。"
        "具体金额、日期、人物、事件、程序状态和把某个法律命题错误归因于客户，若两处均无依据，"
        "必须判unsupported。合理法律推论只要其事实前提能由案件事实或对话支持就判grounded。"
        "basis简短写支持事实ID/对话片段，或说明为何两处均无依据；只输出claims对象。"
        f"这是固定分块{chunk_index}/{chunk_count}，只分类本块给出的ID；其他块由相同协议另行处理。\n\n"
        "本块冻结memo片段：\n"
        + "\n".join(
            f"{claim_id}: {excerpt}"
            for claim_id, excerpt in frozen_spans.items()
        )
        + "\n\n"
        f"案件事实：\n{_fact_block(evaluator_case)}\n\n完整对话：\n{dialogue}\n\n"
        f"最终memo：\n{memo}"
    )


def chunk_claim_spans(
    claim_spans: dict[str, str], maximum_claims: int
) -> list[dict[str, str]]:
    """Partition frozen spans without changing IDs, order, text, or denominator."""

    if maximum_claims < 1:
        raise ValueError("maximum claims per grounding chunk must be positive")
    items = list(claim_spans.items())
    return [
        dict(items[index : index + maximum_claims])
        for index in range(0, len(items), maximum_claims)
    ]


def build_grounding_judgment_prompt(
    evaluator_case: dict[str, Any], dialogue: str, memo: str
) -> str:
    """Build official grounding plus a visible-source safety partition."""

    return (
        "只判断最终memo中的本案具体主张能否追溯到案件事实或完整对话，不评价事实覆盖率，"
        "不评价法律分析是否正确，也不要求memo自身附带引文。程序已经把memo冻结为C001等连续"
        "原文片段；必须逐个ID分类，不得遗漏、增加、改写或生成claim文本。classification取值："
        "visible_grounded表示能从客户开场肯定陈述或后续实际回答追溯；"
        "benchmark_only_grounded表示只能从离线案件事实追溯、但可见对话没有披露；"
        "unsupported表示案件事实和可见对话两处都没有依据；non_claim表示标题、法条/抽象规则、"
        "一般策略、纯待办或没有断言条件已发生的假设分析。basis必须准确"
        "写案件事实ID、客户开场或具体对话轮次，禁止把案件事实来源谎写成客户开场。"
        "客户提出‘是否X/能否X/想知道X’只是问题或目标，不是对X的肯定陈述；律师问了X也不是"
        "客户披露X；客户回答‘不知道、不清楚、不确定、没有信息、需要核实’时，X仍未在可见"
        "对话中披露。此后memo即使写‘客户称X但未确认/尚待核实’，也不能放入visible数组；"
        "若X仅与离线案件事实一致，必须放入benchmark_only数组。‘待核实’只能校准确信程度，"
        "不能凭空创造客户来源。反之，客户确实肯定陈述了X，即使没有外部书证，也应放入visible。"
        "以‘若/如果/假设/在……情况下’明确引入、且没有断言该条件已经发生的纯条件分析，不是"
        "对条件事实的主张，应分类non_claim；不得把‘若登记时间早于婚姻建立’拆成‘登记时间"
        "早于婚姻建立’再判unsupported。只有memo另行肯定陈述该条件已经发生时才作前三类分区。"
        "只有案件事实和完整对话两处都没有实质依据的具体主张，才放入unsupported。"
        "法条文本、抽象法律规则、一般诉讼策略、纯粹待办事项不进入任一列表；但‘法院已经"
        "作出生效判决’、‘客户已经胜诉’、‘已经获得赔偿’、具体金额、日期、身份、行为和"
        "程序状态等本案特定陈述必须进入前三类。合理法律推论如果其事实前提有来源，应判grounded；"
        "其分区取决于前提来自visible还是benchmark_only；不得仅因memo没有标注引用、没有列明"
        "证据名称或结论尚未证实而判unsupported。只输出claims对象及每个冻结ID的classification"
        "和basis，不要输出事实ID覆盖判断或额外计数。\n\n冻结memo片段：\n"
        + "\n".join(
            f"{claim_id}: {excerpt}"
            for claim_id, excerpt in memo_claim_spans(memo).items()
        )
        + "\n\n"
        f"案件事实：\n{_fact_block(evaluator_case)}\n\n完整对话：\n{dialogue}\n\n"
        f"最终memo：\n{memo}"
    )


def _mean_binary(values: list[int]) -> float:
    return sum(values) / len(values) if values else 0.0


def _repeated_question_rate(trajectory: ResearchTrajectory) -> float:
    questions = [
        re.sub(r"[\W_]+", "", step.rendered_question).lower()
        for step in trajectory.steps
        if step.rendered_question
    ]
    if not questions:
        return 0.0
    return (len(questions) - len(set(questions))) / len(questions)


def _belief_as_fact_rate(trajectory: ResearchTrajectory, case: dict[str, Any]) -> float:
    mentioned = 0
    categorical = 0
    caution = ("客户称", "若", "如果", "可能", "尚待", "有待", "需核实", "据其陈述")
    # The typed ledger is deterministic source provenance.  It labels every
    # client answer as an unverified client statement and therefore cannot be a
    # lawyer assertion.  Only the model-written analytical suffix can turn a
    # disputed client belief into a categorical memo conclusion.
    memo_without_ledger = re.sub(
        r"<!-- typed_fact_ledger -->.*?<!-- /typed_fact_ledger -->",
        "",
        trajectory.memo,
        flags=re.DOTALL,
    )
    sentences = [
        item for item in re.split(r"[。！？!?\n]", memo_without_ledger) if item.strip()
    ]
    for fact in case["facts"]:
        if fact["gap_type"] != "disputed":
            continue
        chunks = [
            item.strip()
            for item in re.split(r"[，。；、]", fact["client_belief"])
            if len(item.strip()) >= 10
        ]
        matching = [
            sentence for sentence in sentences if any(chunk in sentence for chunk in chunks)
        ]
        if not matching:
            continue
        mentioned += 1
        if any(not any(marker in sentence for marker in caution) for sentence in matching):
            categorical += 1
    return categorical / mentioned if mentioned else 0.0


def _hidden_leak(trajectory: ResearchTrajectory) -> bool:
    for step in trajectory.steps:
        payload = {
            "visible_input": [item.model_dump(mode="json") for item in step.visible_input],
            "state_before": step.state_before,
            "state_patch": step.state_patch.model_dump(mode="json"),
            "state_after": step.state_after,
            "proposed_action": step.proposed_action.model_dump(mode="json"),
            "final_action": step.action_decision.final.model_dump(mode="json"),
        }
        if find_online_payload_forbidden_fields(payload):
            return True
    return False


class SemanticEvaluator:
    """Run rubric, fact, and grounding judgments and compute public metrics."""

    def __init__(
        self,
        judge: StructuredJudgeClient,
        system_prompt: str,
        *,
        judge_qualification_contract_sha256: str,
        reward_parameters: RewardParameters,
        max_attempts: int,
        repair_judge: StructuredJudgeClient | None = None,
        grounding_claims_per_call: int = 64,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("semantic max_attempts must be positive")
        if grounding_claims_per_call < 1:
            raise ValueError("grounding claims per call must be positive")
        if not re.fullmatch(r"[0-9a-f]{64}", judge_qualification_contract_sha256):
            raise ValueError("judge qualification contract must be a SHA-256 digest")
        self.judge = judge
        self.repair_judge = repair_judge or judge
        self.system_prompt = system_prompt
        self.judge_qualification_contract_sha256 = (
            judge_qualification_contract_sha256
        )
        self.reward_parameters = reward_parameters
        self.max_attempts = max_attempts
        self.grounding_claims_per_call = grounding_claims_per_call

    def evaluate(
        self, trajectory: ResearchTrajectory, evaluator_case: dict[str, Any]
    ) -> TrajectoryEvaluation:
        dialogue = trajectory_dialogue(trajectory)
        criteria = evaluator_case["evaluation_criteria"]
        action_count = len(criteria["expected_inquiries"])
        memo_count = len(criteria["memo_expectations"])
        rubric_prompt = (
            "按DLawBench口径逐项判断律师是否执行预期追问、memo是否覆盖预期法律问题。"
            "律师只要在对话中提出了对应的实质问题就算执行，不因客户回答不完整或表示不知道而扣分。"
            "memo只要实质覆盖对应评分点就计1。每项只能为0或1。"
            "必须从第1项到最后一项逐项独立比对，不能只检查前几项；同义实质覆盖也计1。"
            "analysis只需用一两句话引用律师问题或memo短片段作为总体关键依据；分数必须与analysis一致。"
            f"本案预期追问共有{action_count}项，expected_action_scores必须恰好输出"
            f"{action_count}个分数；memo评分点共有{memo_count}项，"
            f"memo_expectation_scores必须恰好输出{memo_count}个分数。"
            "两个数组不可对调、不可多项、不可少项。严格只输出以下英文键JSON，不得改名或增加键："
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
            + f"\n\n完整对话：\n{dialogue}\n\n最终memo：\n{trajectory.memo}"
            + "\n\n最终逐项复核：若最终memo逐字出现或实质同义覆盖某一memo评分点，"
            "该项必须记1；不得因另一个评分点的材料不足连带将它记0。"
        )
        rubric = None
        rubric_response = None
        rubric_error = "unknown"
        rubric_attempt_used = 0
        rubric_normalizations: list[str] = []
        rubric_schema = rubric_judgment_schema(action_count, memo_count)
        prior_rubric_value: dict[str, Any] | None = None
        for attempt in range(self.max_attempts):
            active_judge = self.judge if attempt == 0 else self.repair_judge
            try:
                response = active_judge.generate_json(
                    purpose=("semantic_rubric" if attempt == 0 else "semantic_rubric_repair"),
                    system_prompt=self.system_prompt,
                    user_prompt=(
                        rubric_prompt
                        if attempt == 0
                        else rubric_prompt + "\n\n上一次输出未满足长度或结构约束。不要展开长推理，"
                        f"expected_action_scores只输出{action_count}项，"
                        f"memo_expectation_scores只输出{memo_count}项，直接逐项完整输出。"
                        "上一次待修对象："
                        + json.dumps(prior_rubric_value, ensure_ascii=False, sort_keys=True)
                    ),
                    output_schema=rubric_schema,
                )
            except StructuredModelInvocationError as exc:
                rubric_error = f"{type(exc).__name__}: {exc}"
                continue
            prior_rubric_value = response.value
            try:
                candidate = RubricJudgment.model_validate(response.value)
                expected_lengths = (
                    (candidate.expected_action_scores, criteria["expected_inquiries"]),
                    (candidate.memo_expectation_scores, criteria["memo_expectations"]),
                )
                if any(len(actual) != len(expected) for actual, expected in expected_lengths):
                    raise ValueError("rubric list length mismatch")
                candidate, candidate_rubric_normalizations = (
                    normalize_verbatim_rubric_scores(
                        candidate,
                        criteria["memo_expectations"],
                        trajectory.memo,
                    )
                )
            except ValueError as exc:
                rubric_error = str(exc)
                continue
            rubric = candidate
            rubric_normalizations = candidate_rubric_normalizations
            rubric_response = response
            rubric_attempt_used = attempt + 1
            break
        if rubric is None or rubric_response is None:
            raise ValueError(f"semantic rubric failed bounded repair: {rubric_error}")

        fact_items = list(evaluator_case["facts"])
        ordered_fact_ids = [str(item["fact_id"]) for item in fact_items]
        all_ids = set(ordered_fact_ids)
        fact = None
        fact_traces: list[FactChunkTrace] = []
        pending_fact_chunks: list[tuple[list[dict[str, Any]], str]] = [
            (fact_items, "1")
        ]
        merged_fact_decisions: dict[str, Any] = {}
        fact_repair_used = False
        fact_normalizations: list[str] = []
        covered: set[str] = set()
        correct: set[str] = set()
        substantive_covered: set[str] = set()
        substantive_correct: set[str] = set()
        while pending_fact_chunks:
            chunk_facts, chunk_path = pending_fact_chunks.pop(0)
            chunk_case = {**evaluator_case, "facts": chunk_facts}
            chunk_ids = [str(item["fact_id"]) for item in chunk_facts]
            chunk_id_set = set(chunk_ids)
            facts_prompt = build_fact_judgment_prompt(
                chunk_case, dialogue, trajectory.memo
            )
            fact_response = None
            fact_error = "unknown"
            prior_fact_value: dict[str, Any] | None = None
            attempt_used = 0
            normalized_value: dict[str, Any] | None = None
            chunk_normalizations: list[str] = []
            for attempt in range(self.max_attempts):
                active_judge = self.judge if attempt == 0 else self.repair_judge
                try:
                    response = active_judge.generate_json(
                        purpose=(
                            "semantic_facts"
                            if attempt == 0
                            else "semantic_facts_repair"
                        ),
                        system_prompt=self.system_prompt,
                        user_prompt=(
                            facts_prompt
                            if attempt == 0
                            else facts_prompt
                            + (
                                "\n\n上一次输出未形成合法分区。不要展开长推理，直接使用"
                                "给定fact_id核对全集、互斥和归属。上一次具体结构错误："
                                f"{fact_error[:800]}。上一次待修对象："
                                + json.dumps(
                                    prior_fact_value,
                                    ensure_ascii=False,
                                    sort_keys=True,
                                )
                            )
                        ),
                        output_schema=fact_judgment_schema(chunk_id_set),
                    )
                except StructuredModelInvocationError as exc:
                    fact_error = f"{type(exc).__name__}: {exc}"
                    continue
                prior_fact_value = response.value
                try:
                    candidate_value, exact_normalizations = (
                        normalize_verbatim_fact_decisions(
                            response.value, chunk_case, trajectory.memo
                        )
                    )
                    candidate, candidate_normalizations = parse_fact_judgment(
                        candidate_value, chunk_id_set
                    )
                    wire_issues = fact_wire_contract_issues(
                        candidate_value, chunk_case, trajectory.memo
                    )
                    if wire_issues:
                        raise ValueError("; ".join(wire_issues))
                except ValueError as exc:
                    fact_error = str(exc)
                    continue
                normalized_value = candidate_value
                chunk_normalizations = [
                    *candidate_normalizations,
                    *exact_normalizations,
                ]
                fact_response = response
                attempt_used = attempt + 1
                break
            if fact_response is None or normalized_value is None:
                if len(chunk_facts) > 1 and "finish_reason='length'" in fact_error:
                    midpoint = max(1, len(chunk_facts) // 2)
                    left = chunk_facts[:midpoint]
                    right = chunk_facts[midpoint:]
                    if not left or not right:
                        raise ValueError("adaptive fact split produced an empty unit")
                    pending_fact_chunks = [
                        (left, f"{chunk_path}.1"),
                        (right, f"{chunk_path}.2"),
                        *pending_fact_chunks,
                    ]
                    fact_repair_used = True
                    fact_normalizations.append(
                        "adaptive_length_split:"
                        f"{chunk_path}:"
                        f"{','.join(chunk_ids)}->"
                        f"{','.join(str(item['fact_id']) for item in left)}|"
                        f"{','.join(str(item['fact_id']) for item in right)}"
                    )
                    continue
                raise ValueError(
                    "semantic fact judgment failed bounded repair: "
                    f"chunk_path={chunk_path}; fact_ids={chunk_ids}; {fact_error}"
                )
            decisions = normalized_value.get("facts")
            if not isinstance(decisions, dict):
                decisions = fact_judgment_to_keyed_decisions(candidate, chunk_id_set)
            if set(decisions) != chunk_id_set:
                raise ValueError("fact chunk merge received mismatched fact IDs")
            if set(merged_fact_decisions) & set(decisions):
                raise ValueError("fact chunk merge produced duplicate fact IDs")
            merged_fact_decisions.update(
                {fact_id: decisions[fact_id] for fact_id in sorted(chunk_ids)}
            )
            fact_repair_used = fact_repair_used or attempt_used > 1
            fact_normalizations.extend(chunk_normalizations)
            fact_traces.append(
                FactChunkTrace(
                    chunk_index=len(fact_traces) + 1,
                    fact_ids=chunk_ids,
                    request_sha256=fact_response.request_sha256,
                    response_sha256=fact_response.response_sha256,
                    attempts=attempt_used,
                )
            )

        traced_fact_ids = [fact_id for trace in fact_traces for fact_id in trace.fact_ids]
        if traced_fact_ids != sorted(ordered_fact_ids):
            raise ValueError("fact chunk merge changed frozen fact order or coverage")
        fact, merged_normalizations = parse_fact_judgment(
            {"facts": merged_fact_decisions}, all_ids
        )
        fact_normalizations.extend(merged_normalizations)
        covered = set(fact.covered_fact_ids)
        correct = set(fact.correct_fact_ids)
        substantive_covered = set(fact.substantive_covered_fact_ids)
        substantive_correct = set(fact.substantive_correct_fact_ids)

        claim_spans = memo_claim_spans(trajectory.memo)
        grounding_span_chunks = chunk_claim_spans(
            claim_spans, self.grounding_claims_per_call
        )
        # A frozen reasoning model can occasionally consume its entire completion
        # budget before emitting Structured Outputs even though the same request
        # shape passed qualification.  Keep normal chunks efficient and subdivide
        # only the exact unit that exhausts the output-length budget.  Every child
        # retains the original claim IDs, order and text and uses the same frozen
        # judge, prompt semantics and schema.  A single-claim failure remains
        # fail-closed rather than receiving a heuristic label.
        pending_grounding_chunks: list[tuple[dict[str, str], str]] = [
            (chunk, str(index))
            for index, chunk in enumerate(grounding_span_chunks, start=1)
        ]
        grounding_traces: list[GroundingChunkTrace] = []
        all_grounded_claims: list[GroundedClaim] = []
        all_unsupported_claims: list[UnsupportedClaim] = []
        grounding_repair_used = False
        grounding_normalizations: list[str] = []
        while pending_grounding_chunks:
            chunk_spans, chunk_path = pending_grounding_chunks.pop(0)
            chunk_index = len(grounding_traces) + 1
            planned_chunk_count = chunk_index + len(pending_grounding_chunks)
            grounding_prompt = build_official_grounding_judgment_prompt(
                evaluator_case,
                dialogue,
                trajectory.memo,
                claim_spans=chunk_spans,
                chunk_index=chunk_index,
                chunk_count=planned_chunk_count,
            )
            grounding_response = None
            grounding_error = "unknown"
            prior_grounding_value: dict[str, Any] | None = None
            attempt_used = 0
            chunk_grounded: list[GroundedClaim] = []
            chunk_unsupported: list[UnsupportedClaim] = []
            for attempt in range(self.max_attempts):
                active_judge = self.judge if attempt == 0 else self.repair_judge
                try:
                    response = active_judge.generate_json(
                        purpose=(
                            "semantic_grounding"
                            if attempt == 0
                            else "semantic_grounding_repair"
                        ),
                        system_prompt=self.system_prompt,
                        user_prompt=(
                            grounding_prompt
                            if attempt == 0
                            else grounding_prompt
                            + (
                                f"\n\n这是第{attempt}次有界结构修复。上一次输出未形成合法的本块"
                                "主张分区。不要评价事实覆盖或法律"
                                "正确性，直接对本块每个冻结claim ID重做grounded、unsupported、"
                                "non_claim三类互斥分类。每项basis只写最短必要依据，不展开推理。"
                                "上一次具体结构错误："
                                f"{grounding_error[:800]}。上一次待修对象："
                                + json.dumps(
                                    prior_grounding_value,
                                    ensure_ascii=False,
                                    sort_keys=True,
                                )
                            )
                        ),
                        output_schema=official_grounding_judgment_schema(chunk_spans),
                    )
                except StructuredModelInvocationError as exc:
                    grounding_error = f"{type(exc).__name__}: {exc}"
                    continue
                prior_grounding_value = response.value
                try:
                    normalized_grounding, chunk_normalizations = (
                        normalize_official_grounding_contract(
                            response.value, chunk_spans, dialogue
                        )
                    )
                    (
                        chunk_grounded,
                        chunk_unsupported,
                    ) = parse_official_grounding_judgment(
                        normalized_grounding, chunk_spans
                    )
                    wire_issues = grounding_wire_contract_issues(
                        normalized_grounding, trajectory.memo
                    )
                    if wire_issues:
                        raise ValueError("; ".join(wire_issues))
                except ValueError as exc:
                    grounding_error = str(exc)
                    continue
                grounding_response = response
                attempt_used = attempt + 1
                break
            if grounding_response is None:
                if (
                    len(chunk_spans) > 1
                    and "finish_reason='length'" in grounding_error
                ):
                    items = list(chunk_spans.items())
                    midpoint = max(1, len(items) // 2)
                    left = dict(items[:midpoint])
                    right = dict(items[midpoint:])
                    if not left or not right:
                        raise ValueError("adaptive grounding split produced an empty unit")
                    pending_grounding_chunks = [
                        (left, f"{chunk_path}.1"),
                        (right, f"{chunk_path}.2"),
                        *pending_grounding_chunks,
                    ]
                    grounding_repair_used = True
                    grounding_normalizations.append(
                        "adaptive_length_split:"
                        f"{chunk_path}:"
                        f"{','.join(chunk_spans)}->"
                        f"{','.join(left)}|{','.join(right)}"
                    )
                    continue
                raise ValueError(
                    "semantic grounding judgment failed bounded repair: "
                    f"chunk_path={chunk_path}; "
                    f"claim_ids={list(chunk_spans)}; {grounding_error}"
                )
            grounding_repair_used = grounding_repair_used or attempt_used > 1
            grounding_normalizations.extend(chunk_normalizations)
            grounding_traces.append(
                GroundingChunkTrace(
                    chunk_index=chunk_index,
                    claim_ids=list(chunk_spans),
                    request_sha256=grounding_response.request_sha256,
                    response_sha256=grounding_response.response_sha256,
                    attempts=attempt_used,
                )
            )
            all_grounded_claims.extend(chunk_grounded)
            all_unsupported_claims.extend(chunk_unsupported)

        traced_claim_ids = [
            claim_id for trace in grounding_traces for claim_id in trace.claim_ids
        ]
        if traced_claim_ids != list(claim_spans):
            raise ValueError("grounding chunk merge changed frozen claim order or coverage")
        fact.grounded_claims = all_grounded_claims
        fact.benchmark_only_grounded_claims = []
        fact.unsupported_claims = all_unsupported_claims

        n_facts = len(all_ids)
        fact_coverage = len(covered) / n_facts if n_facts else 0.0
        inquiry = _mean_binary(rubric.expected_action_scores)
        fact_resolution = len(correct) / n_facts if n_facts else 0.0
        issue_resolution = _mean_binary(rubric.memo_expectation_scores)
        fidelity = (
            (fact.total_claims - len(fact.unsupported_claims)) / fact.total_claims
            if fact.total_claims
            else 0.0
        )
        official = OfficialMetrics(
            fact_coverage=round(fact_coverage, 6),
            inquiry=round(inquiry, 6),
            elicitation=round((fact_coverage + inquiry) / 2, 6),
            fact_resolution=round(fact_resolution, 6),
            issue_resolution=round(issue_resolution, 6),
            resolution=round((fact_resolution + issue_resolution) / 2, 6),
            fidelity=round(fidelity, 6),
        )
        # Never let a fluent memo manufacture the policy's learning signal.  The
        # official metrics above retain DLawBench's memo-discovery semantics; the
        # evolution metrics below are locked to facts the client simulator marked
        # as newly disclosed in the online trajectory.
        elicited = elicited_hidden_fact_ids(trajectory, all_ids)
        resolved_elicited = elicited & substantive_correct
        memo_only_substantive = substantive_covered - elicited
        substantive_fact_coverage = len(elicited) / n_facts if n_facts else 0.0
        substantive_fact_resolution = (
            len(resolved_elicited) / n_facts if n_facts else 0.0
        )
        training = TrainingMetrics(
            substantive_fact_coverage=round(substantive_fact_coverage, 6),
            inquiry=round(inquiry, 6),
            elicitation=round(balanced_elicitation(substantive_fact_coverage, inquiry), 6),
            substantive_fact_resolution=round(substantive_fact_resolution, 6),
            issue_resolution=round(issue_resolution, 6),
            resolution=round((substantive_fact_resolution + issue_resolution) / 2, 6),
        )
        disputed_ids = {
            item["fact_id"] for item in evaluator_case["facts"] if item["gap_type"] == "disputed"
        }
        # Execution no longer forces the policy to exhaust a candidate agenda: that
        # would make dialogue length a hidden hard-coded controller and erase the
        # termination behavior skills are meant to improve.  Keep premature stopping
        # observable in the reward instead.  A first-action final is unambiguously
        # premature whenever this benchmark case declares inquiry rubrics; explicit
        # safety redirections remain premature as before.
        interactive_before = 0
        premature = 0
        has_expected_inquiries = bool(
            evaluator_case.get("evaluation_criteria", {}).get("expected_inquiries")
        )
        for step in trajectory.steps:
            if step.proposed_action.action_type == "final" and (
                step.stop_gate_verdict == "REDIRECT"
                or (interactive_before == 0 and has_expected_inquiries)
            ):
                premature += 1
            if step.client_response is not None:
                interactive_before += 1
        safety = SafetyMetrics(
            premature_final_rate=round(premature / max(len(trajectory.steps), 1), 6),
            unsupported_claim_rate=round(
                len(fact.unsupported_claims) / fact.total_claims
                if fact.total_claims
                else 0.0,
                6,
            ),
            belief_as_fact_rate=round(_belief_as_fact_rate(trajectory, evaluator_case), 6),
            repeated_question_rate=round(_repeated_question_rate(trajectory), 6),
            critical_fact_recall=round(
                len(resolved_elicited & disputed_ids) / len(disputed_ids)
                if disputed_ids
                else 0.0,
                6,
            ),
            hidden_field_leak=_hidden_leak(trajectory),
        )
        interactive_steps = [step for step in trajectory.steps if step.client_response is not None]
        operational = OperationalMetrics(
            policy_repair_rate=round(
                sum(len(step.policy_attempts) > 1 for step in trajectory.steps)
                / max(len(trajectory.steps), 1),
                6,
            ),
            policy_fallback_rate=round(
                sum(policy_fallback_used(step) for step in trajectory.steps)
                / max(len(trajectory.steps), 1),
                6,
            ),
            client_repair_rate=round(
                sum(len(step.client_selection_attempts) > 1 for step in interactive_steps)
                / max(len(interactive_steps), 1),
                6,
            ),
            client_fallback_rate=round(
                sum(step.client_safe_fallback for step in interactive_steps)
                / max(len(interactive_steps), 1),
                6,
            ),
            memo_retry=len(trajectory.memo_attempts) > 1,
            memo_guardrail_intervention=any(
                change != "render_typed_fact_ledger"
                for item in trajectory.memo_attempts
                for change in item.deterministic_changes
            ),
            memo_fallback=trajectory.memo_safe_fallback,
        )
        reward = trajectory_reward(
            RewardComponents(
                elicitation=training.elicitation,
                resolution=training.resolution,
                fidelity=official.fidelity,
                turns=sum(bool(step.rendered_question) for step in trajectory.steps),
                repeated_question_rate=safety.repeated_question_rate,
                premature_final=safety.premature_final_rate > 0,
                unsupported_claim=safety.unsupported_claim_rate > 0,
                no_substantive_inquiry=bool(action_count and inquiry == 0),
                hidden_field_leak=safety.hidden_field_leak,
            ),
            self.reward_parameters,
        )
        return TrajectoryEvaluation(
            trajectory_id=trajectory.trajectory_id,
            case_id=trajectory.case_id,
            judge_model=rubric_response.model,
            judge_qualification_contract_sha256=(
                self.judge_qualification_contract_sha256
            ),
            rubric_request_sha256=rubric_response.request_sha256,
            rubric_response_sha256=rubric_response.response_sha256,
            fact_request_sha256=_ordered_trace_digest(
                [trace.request_sha256 for trace in fact_traces]
            ),
            fact_response_sha256=_ordered_trace_digest(
                [trace.response_sha256 for trace in fact_traces]
            ),
            fact_chunks=fact_traces,
            grounding_chunks=grounding_traces,
            rubric_repair_used=rubric_attempt_used > 1,
            fact_repair_used=fact_repair_used,
            grounding_repair_used=grounding_repair_used,
            rubric_normalizations=rubric_normalizations,
            fact_normalizations=fact_normalizations,
            grounding_normalizations=grounding_normalizations,
            official_metrics=official,
            training_metrics=training,
            training_fact_provenance=TrainingFactProvenance(
                elicited_hidden_fact_ids=sorted(elicited),
                resolved_elicited_fact_ids=sorted(resolved_elicited),
                memo_only_substantive_fact_ids=sorted(memo_only_substantive),
            ),
            mechanism_signals=derive_mechanism_signals(trajectory, all_ids),
            safety_metrics=safety,
            operational_metrics=operational,
            reward=reward,
            rubric_judgment=rubric,
            fact_judgment=fact,
        )


def evaluation_to_official_session_scores(evaluation: TrajectoryEvaluation) -> dict[str, Any]:
    """Return the exact score keys consumed by upstream DLawBench metrics.py."""
    metrics = evaluation.official_metrics
    return {
        "FFS": 1.0,
        "MES": metrics.issue_resolution,
        "EAS": metrics.inquiry,
        "discovery_rate": metrics.fact_coverage,
        "absolute_accuracy": metrics.fact_resolution,
        "grounding_rate": metrics.fidelity,
    }


def compact_trajectory_for_teacher(trajectory: ResearchTrajectory) -> dict[str, Any]:
    """Visible-only state/action evidence; evaluator facts and rubrics are excluded."""
    return {
        "trajectory_id": trajectory.trajectory_id,
        "case_id": trajectory.case_id,
        "domain": trajectory.domain,
        "persona": trajectory.persona,
        "status": trajectory.status,
        "opening": trajectory.opening,
        "steps": [
            {
                "turn": step.turn,
                "state_before": step.state_before,
                "proposed_action": step.proposed_action.model_dump(mode="json"),
                "final_action": step.action_decision.final.model_dump(mode="json"),
                "client_response": step.client_response,
                "stop_gate_verdict": step.stop_gate_verdict,
                "policy_health_violations": step.policy_health_violations,
                "post_skill_health_violations": step.post_skill_health_violations,
            }
            for step in trajectory.steps
        ],
        "memo": trajectory.memo,
    }
