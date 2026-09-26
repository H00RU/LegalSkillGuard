"""One leakage-safe multi-turn LegalSkillEvolve trajectory."""

from __future__ import annotations

import copy
import hashlib
import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from legal_skill_guard.agent.action_parser import _balanced_json_objects
from legal_skill_guard.agent.memo_renderer import render_terminal_memo
from legal_skill_guard.agent.state_manager import StateManager
from legal_skill_guard.agent.stateful_policy import (
    action_question_quality_violations,
    action_target_alignment_confirmed,
    atomic_factual_target_projection,
    blocking_policy_health_violations,
    factual_target_question_safety_violations,
    normalize_policy_envelope,
    parse_policy_envelope,
    policy_health_violations,
    policy_repair_instruction,
    render_action,
    specific_numeric_anchors,
)
from legal_skill_guard.data_visibility import Audience, assert_online_view_safe, project_case
from legal_skill_guard.environment.client_response import (
    ClientSimulator,
    event_concepts,
)
from legal_skill_guard.inference.codex_cli_client import strict_output_schema
from legal_skill_guard.inference.openai_client import ChatResponse, GenerationConfig
from legal_skill_guard.opening_agenda_contract import (
    OPENING_AGENDA_ATTRIBUTE_LABELS,
    opening_agenda_fact_id,
    opening_agenda_label,
    opening_agenda_topic_issue,
    opening_attribute_is_explicitly_answered,
)
from legal_skill_guard.schemas.action import ActionDecision, StructuredAction
from legal_skill_guard.schemas.experiment import (
    VISIBLE_STATE_PAYLOAD_MARKER,
    ClientSelectionAttempt,
    PolicyActionOutput,
    PolicyAttempt,
    PolicyEnvelope,
    ResearchStep,
    ResearchTrajectory,
    VisibleStateCoverageAttempt,
    policy_visible_dialogue_row,
    policy_visible_state_projection,
)
from legal_skill_guard.schemas.skill import SkillContract
from legal_skill_guard.schemas.state import (
    NON_SUBSTANTIVE_FACT_IDS,
    ConsultationState,
    DisclosureDecision,
    FactObservation,
    FactSlot,
    StatePatch,
)
from legal_skill_guard.schemas.trajectory import Message, TokenUsage
from legal_skill_guard.skills.memory import (
    EMPTY_PLANNER_SKILL_MEMORY,
    render_skill_memory,
)
from legal_skill_guard.verifiers.deterministic import StopGate, verify_action

NEW_VISIBLE_GAP_TARGET_ID = "new_visible_gap"

OPENING_INQUIRY_AGENDA_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "targets": {
            "type": "array",
            "minItems": 0,
            # Transport ceiling only.  The prompt explicitly forbids filling this
            # bound merely to create a fixed-size or fixed-turn consultation plan.
            "maxItems": 8,
            "items": {
                "type": "object",
                "properties": {
                    "topic_excerpt": {
                        "type": "string",
                        "minLength": 2,
                        "maxLength": 48,
                    },
                    "attribute": {
                        "type": "string",
                        "enum": [
                            "time",
                            "place",
                            "amount",
                            "content",
                            "method",
                            "reason",
                            "status",
                            "result",
                            "duration",
                            "frequency",
                        ],
                    },
                },
                "required": ["topic_excerpt", "attribute"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["targets"],
    "additionalProperties": False,
}


def parse_opening_inquiry_agenda(
    text: str,
    *,
    opening: str,
    state: ConsultationState,
) -> tuple[StatePatch, str, list[str], list[str]]:
    """Parse an opening-only, non-binding set of client-answerable fact dimensions.

    The agenda is shared infrastructure for every comparison arm.  It never sees
    hidden facts, does not select the next action, and remains open through the
    ordinary ``new_visible_gap`` sentinel.  Deterministic code only rejects unsafe
    or already-known attributes; the target label is rendered only from the exact
    opening excerpt and the closed attribute vocabulary.
    """

    raw = text.strip()
    value: object | None = None
    parse_mode = "fallback"
    for index, candidate in enumerate([raw, *_balanced_json_objects(raw)]):
        try:
            parsed = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(parsed, dict):
            value = parsed
            parse_mode = "json" if index == 0 else "json_fragment"
            break
    if not isinstance(value, dict) or set(value) != {"targets"}:
        return StatePatch(), parse_mode, ["invalid_opening_agenda_object"], []
    targets = value.get("targets")
    if not isinstance(targets, list) or not 0 <= len(targets) <= 8:
        return StatePatch(), parse_mode, ["invalid_opening_agenda_cardinality"], []
    if not targets:
        return StatePatch(), parse_mode, [], []

    observations: list[FactObservation] = []
    violations: list[str] = []
    changes: list[str] = []
    seen: set[str] = set()
    opening_anchors = specific_numeric_anchors(opening)
    for index, item in enumerate(targets):
        if not isinstance(item, dict) or set(item) != {"topic_excerpt", "attribute"}:
            violations.append(f"agenda_target_{index}:invalid_shape")
            continue
        topic_excerpt = str(item.get("topic_excerpt") or "").strip()
        attribute = str(item.get("attribute") or "").strip()
        topic_issue = opening_agenda_topic_issue(topic_excerpt, opening)
        if topic_issue is not None:
            violations.append(f"agenda_target_{index}:{topic_issue}")
            changes.append(
                f"drop_ungrounded_opening_agenda_target:{index}"
                if topic_issue == "opening_topic_not_exactly_grounded"
                else f"drop_invalid_opening_agenda_topic:{index}"
            )
            continue
        if attribute not in OPENING_AGENDA_ATTRIBUTE_LABELS:
            violations.append(f"agenda_target_{index}:invalid_attribute")
            continue
        topic_identity = re.sub(
            r"[^\u4e00-\u9fffA-Za-z0-9]", "", topic_excerpt
        ).lower()
        identity = f"{topic_identity}:{attribute}"
        if identity in seen:
            violations.append(f"agenda_target_{index}:duplicate_topic_attribute")
            continue
        seen.add(identity)
        label = opening_agenda_label(topic_excerpt, attribute)
        target_id = opening_agenda_fact_id(label)
        probe = StructuredAction(
            action_type="ask",
            target_type="fact",
            target_id=target_id,
            expected_information=label,
            content=f"{label}？",
        )
        target_issues = factual_target_question_safety_violations(target_id, label)
        target_issues.extend(
            issue
            for issue in action_question_quality_violations(probe)
            if issue
            in {
                "multiple_primary_questions",
                "question_requests_legal_judgment_from_client",
                "generic_or_abstract_question",
            }
        )
        unseen_anchors = specific_numeric_anchors(label) - opening_anchors
        if unseen_anchors:
            target_issues.append("unseen_specific_numeric_anchor")
        if opening_attribute_is_explicitly_answered(
            opening, topic_excerpt, attribute
        ):
            target_issues.append("opening_already_answers_target")
        if target_issues:
            violations.append(
                f"agenda_target_{index}:" + "|".join(sorted(set(target_issues)))
            )
            changes.append(f"drop_invalid_opening_agenda_target:{target_id}")
            continue
        observations.append(
            FactObservation(
                fact_id=target_id,
                label=label,
                status="unknown",
                value=None,
                evidence_labels=[f"public_opening_anchor:{topic_excerpt}"],
                confidence=0.5,
                criticality="medium",
                target_kind="client_fact",
            )
        )
    if not observations:
        violations.append("opening_agenda_has_no_safe_target")
    observations.sort(key=lambda item: item.fact_id)
    return StatePatch(observations=observations), parse_mode, violations, changes

INVESTIGATION_PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "issue_labels": {
            "type": "array",
            "minItems": 1,
            "maxItems": 4,
            "items": {"type": "string", "minLength": 1},
        },
        "unknowns": {
            "type": "array",
            "minItems": 1,
            # A transport bound against structured enumeration loops, not a target
            # plan length.  The prompt stops when independent decision dimensions
            # are exhausted and may validly return any smaller number.
            "maxItems": 8,
            "items": {
                "type": "object",
                "properties": {
                    "fact_id": {"type": "string", "minLength": 1},
                    "label": {"type": "string", "minLength": 1},
                    "criticality": {"type": "string", "enum": ["high", "medium", "low"]},
                    "target_kind": {
                        "type": "string",
                        "enum": ["client_fact", "evidence_or_third_party"],
                    },
                },
                "required": ["fact_id", "label", "criticality", "target_kind"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["issue_labels", "unknowns"],
    "additionalProperties": False,
}


def asks_response_event_existence(label: str) -> bool:
    """Whether the response event itself, rather than one of its attributes, is queried."""

    event = r"(?:答复|回复|回应|决定(?:书)?|通知(?:书)?|裁定(?:书)?|判决(?:书)?|裁判)"
    direct_existence = bool(
        re.search(
            rf"(?:是否|有无|有没有).{{0,16}}(?:已有|发出|收到|获得|作出|给出|出具|开具|"
            # A natural Chinese existence question may put a fairly long
            # instrument description between ``存在`` and the event noun, e.g.
            # “是否存在关于子女抚养权的书面协议或判决”.  The previous 12-character
            # window misclassified that question as if it presupposed a judgment.
            # This is still bounded and still requires an explicit existence verb,
            # so attributes such as a judgment's date/content remain guarded.
            rf"送达|存在|发生).{{0,32}}{event}",
            label,
        )
        or re.search(
            r"(?:是否|有无|有没有)(?:已经|已|实际|曾经|曾)?"
            r"(?:通知(?:书)?|答复|回复|回应).{0,20}",
            label,
        )
        or re.search(
            r"(?:是否|有无|有没有).{0,24}(?:答复|回复|回应|通知(?:书)?)"
            r"(?:本身)?(?:存在|发生|发出|收到|作出|给出|出具|送达)?"
            r"(?:[？?。.]?$)",
            label,
        )
        or re.search(
            rf"{event}(?:本身)?(?:是否|有无|有没有)"
            rf"(?:(?:已经|已|实际|曾经|曾)){{0,2}}"
            rf"(?:存在|发出|收到|作出|出具|开具|给出|获得|送达|发生)",
            label,
        )
    )
    if direct_existence:
        return True
    # Ordinary Chinese places the event's object after the verb: “是否回应质疑”、
    # “有无回复申请”.  That remains a yes/no event-existence question.  In contrast,
    # a suffix requesting content/reason/time/method/actor is an attribute of an
    # event whose existence must first be established.
    yes_no_event = re.search(
        r"(?:是否|有无|有没有).{0,24}(?:答复|回复|回应|通知(?:书)?)(?P<suffix>.{0,24})$",
        label.strip().rstrip("？?。."),
    )
    if not yes_no_event:
        return False
    suffix = yes_no_event.group("suffix")
    attribute_suffix = re.search(
        r"(?:的)?(?:具体)?(?:内容|原文|理由|原因|时间|日期|方式|渠道|发送方|"
        r"作出方|主体|态度|说法|表述|结果)",
        suffix,
    )
    return not bool(attribute_suffix)


def response_event_terms_in(label: str) -> set[str]:
    """Find response-event nouns without treating ordinary ``决定`` verbs as events."""

    terms = {term for term in ("答复", "回复", "回应") if term in label}
    # ``通知`` is also a common normative-instrument noun.  In targets such as
    # “收费所依据的政策文件或通知”, it names the possible source of a rule; it
    # is not a notice event sent to or received by the client.  Treating every
    # occurrence as a response event made the planner demand proof that a policy
    # instrument had first been delivered before it could even ask whether that
    # instrument existed.  Keep the exemption tied to an explicit legal-basis
    # construction so ordinary notice content/date/recipient targets remain under
    # the response-event existence guard.
    notification_is_normative_instrument = bool(
        re.search(
            r"(?:所依据|依据|根据).{0,24}(?:政策|规范性)?"
            r"(?:文件|规定|办法|方案)(?:或|和|及|与|、)?通知",
            label,
        )
        or re.search(
            r"(?:政策|规范性)文件(?:或|和|及|与|、)通知.{0,16}"
            r"(?:名称|内容|条款|规定)",
            label,
        )
    )
    if "通知" in label and not notification_is_normative_instrument:
        terms.add("通知")
    decision_is_document_or_disposition = bool(
        re.search(
            r"(?:处罚|处理|追缴|补偿|行政|征收|许可|复议|处分|驳回|撤销|不予)"
            r".{0,4}决定(?:书)?",
            label,
        )
        or re.search(
            r"决定书|决定(?:本身)?(?:是否|有无|有没有|内容|原文|理由|时间|日期|"
            r"编号|文号|机关|作出|收到|送达|生效)",
            label,
        )
        or re.search(r"(?:作出|收到|送达|发出|获得|已有|存在).{0,8}决定", label)
    )
    if decision_is_document_or_disposition:
        terms.add("决定")
    for term in ("裁定", "判决", "裁判"):
        if term in label:
            terms.add(term)
    return terms


class GenerativeClient(Protocol):
    model: str

    def is_ready(self) -> bool: ...

    def generate(
        self, messages: list[dict[str, str]], generation: GenerationConfig
    ) -> ChatResponse: ...


class InvestigationPlanningError(ValueError):
    """A failed-closed plan with every rejected model attempt retained for audit."""

    def __init__(self, message: str, attempts: list[PolicyAttempt]) -> None:
        super().__init__(message)
        self.attempts = attempts


def policy_sampling_seed(base_seed: int, sample_index: int, turn: int) -> int:
    """Independent, reproducible random stream for the sampled lawyer policy."""

    return base_seed * 10_000 + sample_index * 100 + turn


def policy_fact_presentation_seed(base_seed: int, sample_index: int, turn: int) -> int:
    """Return a deterministic seed for training-only list presentation.

    This does not add, remove, or reprioritize facts.  It only removes a serialisation
    position bias among facts carrying the same author-assigned criticality.  The
    presentation stream is the immediately preceding integer to the corresponding
    policy-decoding seed, making both sources explicit and reproducible while retaining
    the mapping qualified by the first-action diversity probe.
    """

    return policy_sampling_seed(base_seed, sample_index, turn - 1)


def shared_component_seed(base_seed: int, offset: int) -> int:
    """Common random number for non-policy components inside one TF-GRPO group."""

    return base_seed * 10_000 + offset


def investigation_planning_seed(base_seed: int) -> int:
    """Hold the visible-input agenda fixed inside one TF-GRPO group.

    The planner is upstream infrastructure, not one of the sampled lawyer
    actions.  Giving every K member a different agenda confounds a policy
    contrast with a different action space.  Lawyer decoding retains its
    independent ``sample_index`` stream below, so this common seed removes the
    nuisance intervention without collapsing policy exploration.
    """

    return shared_component_seed(base_seed, 0)


def client_environment_seed(base_seed: int) -> int:
    """Hold the simulated client's random stream fixed across dialogue turns.

    The exact request cache already distinguishes the question, persona, candidate
    facts and their disclosed status.  Adding the turn number made an otherwise
    identical client state answer the same question differently merely because the
    lawyer reached it one turn later, contaminating policy contrasts with environment
    noise.  Different experimental dialogue seeds may still define different client
    environments, but every arm within one group observes a stable response function.
    """

    return shared_component_seed(base_seed, 1)


def client_routing_question(
    action: StructuredAction,
    state: ConsultationState,
    rendered_question: str,
) -> str:
    """Return the system-owned semantic query used only for client fact routing.

    Policy wording remains visible to the client and to disclosure behavior. Fact
    routing canonicalizes only surfaces that positively align with the declared
    visible-state target. An unconfirmed paraphrase keeps its actual wording, so a stale
    or incorrect ``target_id`` cannot launder an irrelevant question into a fact.
    This removes proven harmless paraphrase noise without correcting policy errors.
    """

    # Target-label canonicalization may remove harmless conversational wording,
    # but it must never turn a behaviorally invalid question into a different,
    # answerable one.  In particular, replacing “是否依法处理” with a factual
    # agenda label would manufacture client yield for a legal-judgment question;
    # replacing a compound question would hide which attribute was actually
    # asked.  Such exhausted same-model repair failures remain scoreable exactly
    # as authored and are routed on their natural surface.
    if action_question_quality_violations(action):
        return rendered_question.strip()

    target_id = str(action.target_id or "")
    # Runtime targets are authored by the lawyer itself.  Their internal labels
    # exist only so the state machine can close or retry one dialogue dimension;
    # they are not a semantic substitute for the natural question.  Routing on
    # a generic runtime label such as ``问题所指文件的具体内容`` would erase the
    # very predicate that the client simulator must match.
    if target_id.startswith("dialogue_fact_"):
        return rendered_question.strip()
    if target_id:
        label = next(
            (
                str(fact.label).strip()
                for fact in state.facts
                if str(fact.fact_id) == target_id and str(fact.label).strip()
            ),
            "",
        )
        if label and action_target_alignment_confirmed(action, label):
            return label
    return rendered_question.strip()


def policy_stream_index(
    method: str,
    sample_index: int,
) -> int:
    """Return the base policy stream used by one experimental arm."""

    if sample_index < 0:
        raise ValueError("sample_index must be non-negative")
    return sample_index


TRAINING_BRANCH_TURNS = (1,)
TRAINING_EXACT_PREFIX_MEMBERS = (0, 1, 2, 3)
TRAINING_PREFIX_STREAM = 0


def training_policy_branch_turn(case_id: str) -> int:
    """Return the predeclared first-turn branch for every training K group.

    Delaying the independent streams to turns 2--4 left many cases with only one
    obvious target by the time sampling diverged.  Standard group-relative
    exploration starts every rollout from the same initial prompt and gives each
    member its own random stream immediately; no prompt perturbation, target
    assignment, candidate list, or skill-free treatment branch is introduced.
    """

    normalized = case_id.strip()
    if not normalized:
        raise ValueError("training branch case_id must be non-empty")
    return TRAINING_BRANCH_TURNS[0]


def policy_sampling_stream_index(
    method: str,
    sample_index: int,
    *,
    case_id: str,
    turn: int,
) -> int:
    """Resolve evaluation streams and the training four-way exact-prefix branch."""

    base = policy_stream_index(method, sample_index)
    if turn < 1:
        raise ValueError("policy sampling turn must be positive")
    if (
        method == "training_policy_sample"
        and sample_index in TRAINING_EXACT_PREFIX_MEMBERS
        and turn < training_policy_branch_turn(case_id)
    ):
        return TRAINING_PREFIX_STREAM
    return base


OBSERVABLE_CORE_MARKERS = (
    "采取",
    "实施",
    "实际",
    "具体",
    "发生",
    "时间",
    "日期",
    "金额",
    "数量",
    "方式",
    "内容",
    "过程",
    "步骤",
    "措施",
    "补正",
    "整改",
    "支付",
    "交付",
    "签署",
    "提交",
    "发送",
    "通知",
    "沟通",
    "说明",
    "收到",
    "使用",
    "生产",
    "销售",
    "提供",
    "获取",
    "复制",
    "传播",
    "转让",
    "停止",
    "删除",
    "下架",
    "收入",
    "支出",
    "损失",
)

RECOVERABLE_LEGAL_CHARACTERIZATION_CODES = {
    "abstract_marker:侵权行为",
    "abstract_marker:违法行为",
    "abstract_marker:违约行为",
    "abstract_marker:不正当竞争行为",
    "abstract_marker:诈骗行为",
    "abstract_marker:竞业行为",
    "abstract_marker:假冒",
    "abstract_marker:侵权",
    "abstract_marker:非法获利",
}

# A legal/evidentiary comparison can still contain a plainly observable object
# worth preserving.  For example, ``孩子当前生活状况是否符合最佳利益原则``
# must not be accepted as written, but deleting it also deletes the useful
# ``孩子当前生活状况`` dimension.  These nouns describe observable attributes;
# their presence only routes the draft to the bounded model editor below.  The
# edited label still has to pass the complete factual-question safety contract.
OBSERVABLE_STATE_CORE_MARKERS = (
    "行为",
    "措施",
    "处置",
    "沟通",
    "原话",
    "内容",
    "金额",
    "时间",
    "日期",
    "方式",
    "经过",
    "过程",
    "结果",
    "现状",
    "状况",
    "状态",
    "安排",
    "照料",
    "居住",
    "收入",
    "损失",
    "付款",
    "交付",
    "使用",
    "生产",
    "销售",
)


def planner_target_has_recoverable_observable_core(label: str, reason: str) -> bool:
    """Whether a rejected abstract label can retain an observable factual core.

    This only routes a model draft back to the bounded planner editor; it never
    accepts or rewrites a target deterministically.  The edited replacement must
    still pass the complete factual-question safety contract.
    """

    codes = set(reason.split("|"))
    has_legal_characterization = bool(codes & RECOVERABLE_LEGAL_CHARACTERIZATION_CODES)
    has_legal_judgment = "legal_or_evidentiary_judgment" in codes
    if not (has_legal_characterization or has_legal_judgment):
        return False
    if any(
        code.startswith(
            (
                "sensitive_personal_identifier",
                "generic_or_sensitive_identity_request",
                "generic_mechanical_expansion",
            )
        )
        for code in codes
    ):
        return False
    if has_legal_judgment:
        return any(marker in label for marker in OBSERVABLE_STATE_CORE_MARKERS)
    return any(marker in label for marker in OBSERVABLE_CORE_MARKERS)


def _usage(responses: list[ChatResponse]) -> TokenUsage:
    return TokenUsage(
        prompt=sum(item.prompt_tokens for item in responses),
        completion=sum(item.completion_tokens for item in responses),
    )


def finalize_horizon_verdict(
    *,
    turn: int,
    max_turns: int,
    action: StructuredAction,
    verdict: str,
    reason: str,
) -> tuple[str, str]:
    """Record budget exhaustion without overwriting a safety redirect."""

    if turn < max_turns or action.action_type in {"final", "abstain"}:
        return verdict, reason
    horizon_reason = "dialogue_horizon_exhausted_after_interaction"
    if verdict == "REDIRECT":
        return verdict, f"{reason};{horizon_reason}"
    return "EXHAUSTED", horizon_reason


def termination_contract_check(max_turns: int) -> dict[str, object]:
    """Executable preflight contract for adaptive stopping at the horizon."""

    manager = StateManager()
    gate = StopGate()
    sufficient = manager.initial("termination-contract-sufficient", "开场", max_turns=max_turns)
    sufficient.turn = max_turns
    sufficient.facts.append(
        FactSlot(
            fact_id="contract_fact",
            label="已核实的实质事实",
            status="corroborated",
            value="已核实",
            criticality="high",
            target_kind="client_fact",
        )
    )
    unsafe = manager.initial("termination-contract-unsafe", "开场", max_turns=max_turns)
    unsafe.turn = max_turns
    unsafe.facts.append(
        FactSlot(
            fact_id="contract_unknown",
            label="尚未查明的关键事实",
            status="unknown",
            criticality="high",
            target_kind="client_fact",
        )
    )
    unsafe.facts.append(
        FactSlot(
            fact_id="contract_visible_claim",
            label="客户已陈述的实质背景",
            status="client_claimed",
            value="已有事实基础",
            criticality="medium",
            target_kind="client_fact",
        )
    )
    client_claimed = manager.initial(
        "termination-contract-client-claimed", "开场", max_turns=max_turns
    )
    client_claimed.facts.append(
        FactSlot(
            fact_id="contract_client_claim",
            label="客户明确陈述的实质事实",
            status="client_claimed",
            value="客户陈述",
            criticality="high",
            target_kind="client_fact",
        )
    )
    final_at_horizon = gate.evaluate(sufficient, StructuredAction(action_type="final"))
    conditional_final = gate.evaluate(client_claimed, StructuredAction(action_type="final"))
    conditional_unknown_final = gate.evaluate(unsafe, StructuredAction(action_type="final"))
    no_information = manager.initial("termination-contract-no-info", "开场", max_turns=max_turns)
    no_information = manager.mark_interaction(
        no_information,
        turn=1,
        action_type="ask",
        target_id=None,
        question="是否还有可确认的实质事实？",
    )
    explicit_abstention = gate.evaluate(no_information, StructuredAction(action_type="abstain"))
    unresolved_abstention = gate.evaluate(unsafe, StructuredAction(action_type="abstain"))
    conditional_abstention = gate.evaluate(sufficient, StructuredAction(action_type="abstain"))
    exhausted_ask = finalize_horizon_verdict(
        turn=max_turns,
        max_turns=max_turns,
        action=StructuredAction(action_type="ask", target_type="fact", target_id="contract_fact"),
        verdict="PASS",
        reason="not_a_terminal_action",
    )
    checks = {
        "sufficient_final_at_horizon": final_at_horizon == ("PASS", "sufficient_visible_state"),
        "client_claim_supports_conditional_final": conditional_final
        == ("PASS", "sufficient_visible_state"),
        "unresolved_target_allows_conditional_final": conditional_unknown_final
        == ("PASS", "conditional_visible_state_with_unresolved_targets"),
        "explicit_abstention_preserved": explicit_abstention == ("PASS", "explicit_abstention"),
        "unresolved_abstention_preserved": unresolved_abstention == ("PASS", "explicit_abstention"),
        "conditional_abstention_preserved": conditional_abstention
        == ("PASS", "explicit_abstention"),
        "nonterminal_at_horizon_exhausted": exhausted_ask
        == ("EXHAUSTED", "dialogue_horizon_exhausted_after_interaction"),
    }
    return {"passed": all(checks.values()), "checks": checks}


class TrajectoryRunner:
    """Run a frozen policy, bounded client selector, skills, stop gate, and memo."""

    def __init__(
        self,
        *,
        policy_client: GenerativeClient,
        client_selector: GenerativeClient,
        memo_client: GenerativeClient,
        policy_prompt_path: Path,
        client_prompt_path: Path,
        client_disclosure_prompt_path: Path,
        memo_prompt_path: Path,
        policy_generation: GenerationConfig,
        client_generation: GenerationConfig,
        memo_generation: GenerationConfig,
        model_revision: str,
        max_policy_attempts: int,
        max_client_selection_attempts: int,
        max_memo_attempts: int,
        opening_agenda_prompt_path: Path,
        opening_agenda_generation: GenerationConfig | None = None,
        opening_agenda_client: GenerativeClient | None = None,
        max_opening_agenda_attempts: int = 2,
        shuffle_equal_criticality_fact_presentation: bool = False,
        client_disclosure_classifier: GenerativeClient | None = None,
    ) -> None:
        if (
            min(
                max_policy_attempts,
                max_client_selection_attempts,
                max_memo_attempts,
            )
            < 1
        ):
            raise ValueError("trajectory generation attempt limits must be positive")
        self.policy_client = policy_client
        self.opening_agenda_client = opening_agenda_client or policy_client
        self.client_selector = client_selector
        self.client_disclosure_classifier = client_disclosure_classifier or client_selector
        self.memo_client = memo_client
        self.policy_prompt = policy_prompt_path.read_text(encoding="utf-8").strip()
        self.client_prompt_path = client_prompt_path
        self.client_disclosure_prompt_path = client_disclosure_prompt_path
        self.memo_prompt_path = memo_prompt_path
        self.opening_agenda_prompt = opening_agenda_prompt_path.read_text(
            encoding="utf-8"
        ).strip()
        self.policy_generation = policy_generation
        # Legacy planner helpers remain temporarily importable for historical
        # parser regression tests, but no constructor argument or ``run`` branch
        # can enable them. These inert defaults are outside the executable
        # experiment protocol and can be removed with the parser-only code.
        self.planner_client = policy_client
        self.planner_prompt: str | None = None
        self.planner_repair_prompt: str | None = None
        self.planner_generation = policy_generation
        self.planner_repair_generation = policy_generation
        self.max_planning_attempts = 3
        self.policy_output_schema = strict_output_schema(PolicyActionOutput.model_json_schema())
        # Bound only the transport representation.  These limits do not select an
        # action, target, question count, or dialogue horizon; they prevent a sampled
        # string/array loop from consuming the whole completion budget.
        self._bound_policy_output_schema(self.policy_output_schema)
        self.client_generation = client_generation
        self.memo_generation = memo_generation
        self.opening_agenda_generation = opening_agenda_generation or GenerationConfig(
            temperature=0.0,
            top_p=1.0,
            max_tokens=min(policy_generation.max_tokens, 900),
            seed=policy_generation.seed,
            disable_thinking=policy_generation.disable_thinking,
        )
        self.model_revision = model_revision
        self.max_policy_attempts = max_policy_attempts
        self.max_client_selection_attempts = max_client_selection_attempts
        self.max_memo_attempts = max_memo_attempts
        if max_opening_agenda_attempts < 1:
            raise ValueError("opening agenda attempt limit must be positive")
        self.max_opening_agenda_attempts = max_opening_agenda_attempts
        self.shuffle_equal_criticality_fact_presentation = (
            shuffle_equal_criticality_fact_presentation
        )
        self.state_manager = StateManager()
        self.stop_gate = StopGate()

    @staticmethod
    def _bound_policy_output_schema(schema: dict[str, object]) -> None:
        string_limits = {
            "target_id": 80,
            "reason": 400,
            "expected_information": 240,
            "content": 300,
        }
        array_limits = {"constraints": 6}

        def visit(node: object, field_name: str | None = None) -> None:
            if not isinstance(node, dict):
                return
            if node.get("type") == "string":
                node["maxLength"] = string_limits.get(field_name, 160)
            if node.get("type") == "array":
                node["maxItems"] = array_limits.get(field_name, 8)
            for name, child in (node.get("properties") or {}).items():
                visit(child, str(name))
            for child in (node.get("$defs") or {}).values():
                visit(child)
            visit(node.get("items"), field_name)
            for child in node.get("anyOf") or []:
                visit(child, field_name)

        visit(schema)

    def _visible_policy_target_ids(
        self,
        state: ConsultationState,
    ) -> list[str]:
        """Return open tracked targets plus the lawyer-authored fact sentinel.

        Existing slots remain useful state, but they are an advisory memory rather
        than a closed question space.  The frozen lawyer may always author one new
        observable fact dimension grounded in the opening, visible dialogue, and
        delivered skill document.  The normalizer gives that dimension a stable
        runtime ID; it never chooses its content.
        """

        visible_targets = {
            str(item.fact_id)
            for item in state.facts
            if str(item.fact_id)
            and item.status in {"unknown", "disputed"}
            and item.fact_id not in state.asked_targets
            and item.fact_id not in NON_SUBSTANTIVE_FACT_IDS
        }
        visible_targets.add(NEW_VISIBLE_GAP_TARGET_ID)
        return sorted(visible_targets)

    def _policy_output_schema_for_state(
        self,
        state: ConsultationState,
    ) -> dict[str, object]:
        """Bind target identifiers without closing the lawyer's question space.

        The interface enumerates tracked open targets and one ``new_visible_gap``
        sentinel.  Selecting the sentinel means that the model itself supplies the
        factual dimension and question; deterministic code only assigns a stable
        runtime identifier.  This prevents invented join keys without letting an
        upstream planner decide which legal-consultation questions are available.
        """

        visible_target_ids = self._visible_policy_target_ids(state)
        schema = copy.deepcopy(self.policy_output_schema)
        action_schema = schema["$defs"]["StructuredAction"]
        # There is no retrieval tool in this experiment.  Keeping ``retrieve`` in
        # guided decoding and converting it to ``verify`` afterwards changed a
        # sampled lawyer action and blurred attribution.
        action_schema["properties"]["action_type"] = {
            "type": "string",
            "enum": ["ask", "clarify", "verify", "summarize", "final", "abstain"],
        }
        # The rationale is the model's compact visible deliberation inside the
        # same action, not a second decision stage.  Require nonempty content so
        # the target enum is sampled after a real policy judgment rather than as
        # the first low-entropy content token.
        action_schema["properties"]["reason"]["minLength"] = 8
        if not visible_target_ids:
            # An empty string enum is not a valid guided-decoding language for
            # xgrammar and produces an HTTP 400 before the frozen lawyer can
            # choose to stop.  When the visible state contains no question target,
            # express that same closed-world boundary directly: the model still
            # authors final versus abstain and its rationale, but no factual action
            # or fabricated target ID is representable.
            action_schema["properties"]["action_type"] = {
                "type": "string",
                "enum": ["final", "abstain"],
            }
            action_schema["properties"]["target_type"] = {
                "type": "string",
                "enum": ["session", "none"],
            }
            action_schema["properties"]["target_id"] = {"type": "null"}
            return schema
        target_schema = action_schema["properties"]["target_id"]
        target_schema["anyOf"][0] = {
            "type": "string",
            "enum": visible_target_ids,
            "maxLength": 80,
        }
        return schema

    def preflight(self) -> dict[str, bool]:
        checks = {
            "policy_client": self.policy_client.is_ready(),
            "client_selector": self.client_selector.is_ready(),
            "client_disclosure_classifier": self.client_disclosure_classifier.is_ready(),
            "memo_client": self.memo_client.is_ready(),
        }
        if self.opening_agenda_prompt is not None:
            checks["opening_agenda_client"] = self.opening_agenda_client.is_ready()
        return checks

    def run(
        self,
        *,
        raw_case: dict,
        domain: str = "general",
        persona: dict,
        skills: list,
        trajectory_id: str,
        run_id: str,
        method: str,
        partition: str,
        seed: int,
        sample_index: int,
        max_turns: int,
        group_id: str | None,
        skill_library_version: str,
        diagnostic_interaction_limit: int | None = None,
        policy_memory_override: str | None = None,
        exposed_memory_ids: list[str] | None = None,
    ) -> ResearchTrajectory:
        if diagnostic_interaction_limit is not None:
            if diagnostic_interaction_limit < 1:
                raise ValueError("diagnostic_interaction_limit must be positive")
            if not partition.startswith("diagnostic_"):
                raise ValueError(
                    "diagnostic_interaction_limit is restricted to diagnostic partitions"
                )
        started = time.monotonic()
        created_at = datetime.now(UTC)
        _ = policy_stream_index(method, sample_index)
        raw_case_id = str(raw_case.get("id") or "").strip()
        if method == "training_policy_sample" and not raw_case_id:
            raise ValueError("training exact-prefix branching requires a case id")
        branch_case_id = raw_case_id or trajectory_id
        lawyer_case = project_case(raw_case, Audience.LAWYER_AGENT)
        client_case = project_case(raw_case, Audience.CLIENT_SIMULATOR)
        assert_online_view_safe(lawyer_case)
        opening = str(lawyer_case["opening"])
        persona_id = str(persona.get("persona_id") or "unknown")
        state = self.state_manager.initial(
            trajectory_id,
            opening,
            max_turns=max_turns,
            persona=persona_id,
            domain=domain,
        )
        if policy_memory_override is None:
            if exposed_memory_ids is not None:
                raise ValueError("exposed_memory_ids require an explicit policy_memory_override")
            skill_memory, exposed_skill_ids = render_skill_memory(skills, domain=domain)
        else:
            if skills:
                raise ValueError("policy_memory_override cannot be combined with skill documents")
            skill_memory = policy_memory_override.strip()
            exposed_skill_ids = list(exposed_memory_ids or [])
            if not skill_memory:
                raise ValueError("policy_memory_override cannot be blank")
            if not exposed_skill_ids:
                raise ValueError(
                    "an explicit policy memory must expose at least one auditable memory id"
                )
            if exposed_skill_ids != sorted(set(exposed_skill_ids)):
                raise ValueError("exposed memory identifiers must be unique and sorted")
        if policy_memory_override is None:
            delivered_skill_ids = {
                skill.skill_id
                for skill in skills
                if isinstance(skill, SkillContract) and skill.skill_id in exposed_skill_ids
            }
            if delivered_skill_ids != set(exposed_skill_ids):
                raise ValueError("rendered skill catalog does not match applicable skill documents")
        skill_memory_sha256 = hashlib.sha256(skill_memory.encode("utf-8")).hexdigest()
        # Retain the historical fields as an explicit empty compatibility
        # sentinel.  The retired investigation planner has no production
        # constructor, preflight, model call, or learned-skill exposure path.
        planner_exposed_skill_ids: list[str] = []
        planner_skill_memory_sha256 = hashlib.sha256(
            EMPTY_PLANNER_SKILL_MEMORY.encode("utf-8")
        ).hexdigest()
        client = ClientSimulator.from_template_file(
            case_view=client_case,
            persona=persona,
            model=self.client_selector,  # type: ignore[arg-type]
            disclosure_model=self.client_disclosure_classifier,  # type: ignore[arg-type]
            template_path=self.client_prompt_path,
            disclosure_template_path=self.client_disclosure_prompt_path,
            generation=self.client_generation,
            max_selection_attempts=self.max_client_selection_attempts,
        )
        dialogue: list[tuple[str, str]] = []
        dialogue_response_kinds: list[str | None] = []
        steps: list[ResearchStep] = []
        status = "max_turns_forced_memo"
        error_text: str | None = None
        memo = ""
        memo_attempts = []
        memo_violations: list[str] = []
        memo_safe_fallback = False
        initial_plan = StatePatch()
        planning_attempts: list[PolicyAttempt] = []
        planning_safe_partial = False
        planning_visible_input: list[Message] = []
        initial_coverage_attempts: list[VisibleStateCoverageAttempt] = []
        initial_covered_target_ids: list[str] = []
        initial_coverage_usage = TokenUsage()
        opening_inquiry_agenda = StatePatch()
        opening_agenda_attempts: list[PolicyAttempt] = []
        opening_agenda_safe_partial = False
        opening_agenda_visible_input: list[Message] = []
        try:
            if self.opening_agenda_prompt is not None:
                (
                    opening_inquiry_agenda,
                    opening_agenda_attempts,
                    opening_agenda_safe_partial,
                    opening_agenda_visible_input,
                ) = self._generate_opening_inquiry_agenda(
                    opening,
                    state,
                    shared_component_seed(seed, 7),
                )
                state = self.state_manager.merge(state, opening_inquiry_agenda, turn=0)
            for turn in range(1, max_turns + 1):
                state_before = state.model_dump(mode="json")
                sampling_stream_index = policy_sampling_stream_index(
                    method,
                    sample_index,
                    case_id=branch_case_id,
                    turn=turn,
                )
                visible_messages = self._visible_messages(
                    opening,
                    dialogue,
                    state,
                    turn,
                    policy_method_guidance=skill_memory,
                    policy_sampling_guidance="",
                    fact_presentation_seed=(
                        policy_fact_presentation_seed(seed, sampling_stream_index, turn)
                        if self.shuffle_equal_criticality_fact_presentation
                        else None
                    ),
                )
                envelope, attempts, violations = self._generate_policy(
                    visible_messages,
                    state,
                    policy_sampling_seed(seed, sampling_stream_index, turn),
                )
                merged = self.state_manager.merge(state, envelope.state_patch, turn)
                merged.candidate_action = envelope.action.model_dump(mode="json")
                # Learned skills act only through the policy context.  The model's
                # proposed action is therefore also the post-skill action; static
                # safety and termination gates below remain shared infrastructure
                # in every experimental arm and are not learned skill executors.
                decision = ActionDecision(
                    original=envelope.action.model_copy(deep=True),
                    final=envelope.action.model_copy(deep=True),
                    # The complete fixed document bundle is visible to the one
                    # model call that jointly chooses stop/continue, target, and
                    # wording.  We do not use unreliable self-reported activation.
                    retrieved_skill_ids=list(exposed_skill_ids),
                    activated_skill_ids=[],
                )
                decision = self._normalize_nonterminal_operation(decision)
                post_skill_violations = policy_health_violations(
                    PolicyEnvelope(action=decision.final), merged
                )
                post_skill_blocking = blocking_policy_health_violations(post_skill_violations)
                if post_skill_blocking:
                    # Learned documents no longer rewrite actions.  Therefore an
                    # action that passed against its envelope but fails immediately
                    # after merging the same visible state patch is a validation
                    # boundary defect, not a recoverable policy event.  Fail before
                    # client interaction instead of laundering it through a
                    # deterministic fallback that would contaminate attribution.
                    raise RuntimeError(
                        "post-merge policy health invariant failed: "
                        + ";".join(post_skill_blocking)
                    )
                rendered = (
                    render_action(decision.final, merged)
                    if decision.final.action_type in {"ask", "clarify", "verify", "summarize"}
                    else None
                )
                verdict, reason = self.stop_gate.evaluate(merged, decision.final)
                verifier_results = verify_action(merged, decision, rendered)
                blocking_verifier_results = [
                    item
                    for item in verifier_results
                    if not item.passed and item.severity in {"error", "severe"}
                ]
                if blocking_verifier_results:
                    raise RuntimeError(
                        "action verifier failed closed: "
                        + ";".join(
                            f"{item.validator_id}:{item.detail}"
                            for item in blocking_verifier_results
                        )
                    )
                client_response = None
                client_hash = None
                client_attempts: list[ClientSelectionAttempt] = []
                client_disclosure_attempts: list[ClientSelectionAttempt] = []
                client_opening_attempts: list[ClientSelectionAttempt] = []
                client_route_decision_valid: bool | None = None
                client_response_kind = None
                client_opening_references: list[str] = []
                client_matched: list[str] = []
                client_disclosure_decisions: dict[str, DisclosureDecision] = {}
                client_selected: list[str] = []
                visible_state_coverage_attempts: list[VisibleStateCoverageAttempt] = []
                visible_state_covered_target_ids: list[str] = []
                client_fallback = False
                client_finish = None
                token_usage = _usage(
                    [
                        ChatResponse(
                            content=item.raw_output,
                            finish_reason=item.finish_reason,
                            prompt_tokens=item.prompt_tokens,
                            completion_tokens=item.completion_tokens,
                            raw_id=None,
                        )
                        for item in attempts
                    ]
                )
                state_after = merged
                if decision.final.action_type in {"ask", "clarify", "verify", "summarize"}:
                    assert rendered is not None
                    response, client_hash = client.respond(
                        rendered,
                        client_environment_seed(seed),
                        routing_question=client_routing_question(
                            decision.final,
                            merged,
                            rendered,
                        ),
                    )
                    client_response = response.content
                    client_finish = response.finish_reason
                    token_usage.prompt += response.prompt_tokens
                    token_usage.completion += response.completion_tokens
                    client_attempts = [
                        ClientSelectionAttempt.model_validate(item)
                        for item in client.last_selection_attempt_records
                    ]
                    client_disclosure_attempts = [
                        ClientSelectionAttempt(raw_output=item)
                        for item in client.last_disclosure_attempts
                    ]
                    client_opening_attempts = [
                        ClientSelectionAttempt(raw_output=item)
                        for item in client.last_opening_selection_attempts
                    ]
                    client_route_decision_valid = client.last_route_passed
                    client_response_kind = client.last_response_kind
                    client_opening_references = list(client.last_opening_reference_ids)
                    client_matched = list(client.last_matched_fact_ids)
                    if client.last_disclosure_decision is not None:
                        client_disclosure_decisions = {
                            fact_id: client.last_disclosure_decision for fact_id in client_matched
                        }
                    client_selected = list(client.last_selected_fact_ids)
                    client_fallback = client.last_safe_fallback
                    dialogue_row = policy_visible_dialogue_row(
                        rendered,
                        client_response,
                        client_response_kind,
                    )
                    if dialogue_row is not None:
                        dialogue.append(dialogue_row)
                        dialogue_response_kinds.append(client_response_kind)
                    # ``withheld`` is intentionally neither unavailable nor
                    # answered.  StateManager records the exchange but preserves
                    # the unresolved target and its retry eligibility.
                    client_withheld = client_response_kind == "withheld"
                    state_after = self.state_manager.mark_interaction(
                        merged,
                        turn=turn,
                        action_type=decision.final.action_type,
                        target_id=decision.final.target_id,
                        question=rendered,
                        target_not_available=(
                            client_response_kind == "unavailable" and not client_withheld
                        ),
                        target_answered=(
                            not client_withheld
                            and client_response_kind
                            in {
                                "new_hidden_fact",
                                "repeated_hidden_fact",
                                "opening_repeat",
                            }
                            and client_route_decision_valid is True
                        ),
                        client_response=client_response,
                        response_kind=client_response_kind,
                        disclosed_fact_ids=client_selected,
                    )
                    verdict, reason = finalize_horizon_verdict(
                        turn=turn,
                        max_turns=max_turns,
                        action=decision.final,
                        verdict=verdict,
                        reason=reason,
                    )
                step = ResearchStep(
                    turn=turn,
                    visible_input=visible_messages,
                    state_before=state_before,
                    state_patch=envelope.state_patch,
                    state_after=state_after.model_dump(mode="json"),
                    raw_policy_output=attempts[-1].raw_output,
                    parse_mode=attempts[-1].parse_mode,
                    policy_attempts=attempts,
                    policy_health_violations=violations,
                    post_skill_health_violations=post_skill_violations,
                    proposed_action=envelope.action,
                    action_decision=decision,
                    rendered_question=rendered,
                    client_response=client_response,
                    client_input_sha256=client_hash,
                    client_opening_selection_attempts=client_opening_attempts,
                    client_selection_attempts=client_attempts,
                    client_disclosure_attempts=client_disclosure_attempts,
                    client_route_decision_valid=client_route_decision_valid,
                    client_response_kind=client_response_kind,
                    client_opening_reference_ids=client_opening_references,
                    client_matched_fact_ids=client_matched,
                    client_disclosure_decisions=client_disclosure_decisions,
                    client_selected_fact_ids=client_selected,
                    visible_state_coverage_attempts=visible_state_coverage_attempts,
                    visible_state_covered_target_ids=visible_state_covered_target_ids,
                    client_safe_fallback=client_fallback,
                    verifier_results=verifier_results,
                    stop_gate_verdict=verdict,
                    stop_gate_reason=reason,
                    token_usage=token_usage,
                    lawyer_finish_reason=attempts[-1].finish_reason,
                    client_finish_reason=client_finish,
                )
                steps.append(step)
                state = state_after
                if decision.final.action_type in {"final", "abstain"} and verdict != "REDIRECT":
                    status = (
                        f"diagnostic_{decision.final.action_type}"
                        if diagnostic_interaction_limit is not None
                        else "abstained"
                        if decision.final.action_type == "abstain"
                        else "memo_submitted"
                    )
                    break
                if (
                    diagnostic_interaction_limit is not None
                    and turn >= diagnostic_interaction_limit
                ):
                    status = "diagnostic_interaction_limit"
                    break

            if diagnostic_interaction_limit is None:
                (
                    memo,
                    _,
                    _,
                    memo_attempts,
                    memo_violations,
                    memo_safe_fallback,
                ) = render_terminal_memo(
                    client=self.memo_client,  # type: ignore[arg-type]
                    prompt_path=self.memo_prompt_path,
                    opening=opening,
                    dialogue=dialogue,
                    unavailable_questions=[
                        step.rendered_question
                        for step in steps
                        if step.rendered_question is not None
                        and step.client_response_kind == "unavailable"
                    ],
                    dialogue_response_kinds=dialogue_response_kinds,
                    generation=GenerationConfig(
                        temperature=self.memo_generation.temperature,
                        top_p=self.memo_generation.top_p,
                        max_tokens=self.memo_generation.max_tokens,
                        seed=shared_component_seed(seed, 99),
                        disable_thinking=self.memo_generation.disable_thinking,
                    ),
                    max_attempts=self.max_memo_attempts,
                )
        except Exception as exc:  # artifact captures one failed unit; the matrix can resume
            status = "error"
            error_text = f"{type(exc).__name__}: {exc}"
        return ResearchTrajectory(
            trajectory_id=trajectory_id,
            group_id=group_id,
            sample_index=sample_index,
            run_id=run_id,
            method=method,
            partition=partition,
            case_id=str(raw_case["id"]),
            domain=domain,
            persona=persona_id,
            seed=seed,
            model_id=self.policy_client.model,
            model_revision=self.model_revision,
            skill_library_version=skill_library_version,
            skill_delivery_mode=(
                "experience_memory"
                if policy_memory_override is not None
                else "prompt_memory"
                if exposed_skill_ids
                else "none"
            ),
            exposed_skill_ids=exposed_skill_ids,
            skill_memory_sha256=skill_memory_sha256,
            planner_exposed_skill_ids=planner_exposed_skill_ids,
            planner_skill_memory_sha256=planner_skill_memory_sha256,
            planning_visible_input=planning_visible_input,
            status=status,
            opening=opening,
            max_turns=max_turns,
            steps=steps,
            initial_investigation_plan=initial_plan,
            planning_attempts=planning_attempts,
            planning_safe_partial=planning_safe_partial,
            initial_visible_state_coverage_attempts=initial_coverage_attempts,
            initial_visible_state_covered_target_ids=initial_covered_target_ids,
            initial_visible_state_coverage_token_usage=initial_coverage_usage,
            opening_inquiry_agenda=opening_inquiry_agenda,
            opening_agenda_visible_input=opening_agenda_visible_input,
            opening_agenda_attempts=opening_agenda_attempts,
            opening_agenda_safe_partial=opening_agenda_safe_partial,
            memo=memo,
            memo_attempts=memo_attempts,
            memo_health_violations=memo_violations,
            memo_safe_fallback=memo_safe_fallback,
            elapsed_seconds=round(time.monotonic() - started, 3),
            created_at=created_at,
            error=error_text,
        )

    def _visible_messages(
        self,
        opening: str,
        dialogue: list[tuple[str, str]],
        state: ConsultationState,
        turn: int,
        *,
        policy_method_guidance: str | None = None,
        policy_sampling_guidance: str | None = None,
        fact_presentation_seed: int | None = None,
    ) -> list[Message]:
        system = (
            self.policy_prompt.replace("{opening}", opening)
            .replace("{sampling_guidance}", policy_sampling_guidance or "（无）")
            .replace(
                "{method_guidance}",
                policy_method_guidance
                or "本会话的当前工作库没有适用咨询技能文档。请仅依据可见状态自主决策。",
            )
        )
        messages = [Message(role="system", content=system)]
        for question, answer in dialogue:
            messages.append(Message(role="assistant", content=question))
            messages.append(Message(role="user", content=answer))
        # The online writer and offline trajectory contract deliberately share one
        # pure projection.  Training may change only the display order of facts in
        # one criticality tier; the underlying state and every projected value stay
        # identical.
        state_payload = policy_visible_state_projection(
            state.model_dump(mode="json"),
            fact_presentation_seed=fact_presentation_seed,
        )
        messages.append(
            Message(
                role="user",
                content=(
                    "请依据当前可见记录和本会话方法文档，自主选择下一步行动。"
                    + VISIBLE_STATE_PAYLOAD_MARKER
                    + json.dumps(state_payload, ensure_ascii=False, sort_keys=True)
                    + (
                        "\n终止一致性检查：当前仍有未解决目标；这只是可见状态，不构成必须继续或必须结束的"
                        "系统规则。若选择终止，不得声称未知事项已经查明，并应在条件性初步"
                        "分析中保留可能影响结论的待核事项。"
                        if state.actionable_unresolved_fact_count
                        else ""
                    )
                ),
            )
        )
        return messages

    def _generate_opening_inquiry_agenda(
        self,
        opening: str,
        state: ConsultationState,
        seed: int,
    ) -> tuple[StatePatch, list[PolicyAttempt], bool, list[Message]]:
        """Generate one skill-agnostic, opening-only fact agenda shared by all arms."""

        assert self.opening_agenda_prompt is not None
        base = [
            {"role": "system", "content": self.opening_agenda_prompt},
            {"role": "user", "content": f"客户公开开场：\n{opening}"},
        ]
        visible_input = [Message.model_validate(item) for item in base]
        request_messages = list(base)
        attempts: list[PolicyAttempt] = []
        best_partial: StatePatch | None = None
        best_partial_size = 0
        for attempt_index in range(self.max_opening_agenda_attempts):
            response = self.opening_agenda_client.generate(
                request_messages,
                GenerationConfig(
                    temperature=self.opening_agenda_generation.temperature,
                    top_p=self.opening_agenda_generation.top_p,
                    max_tokens=self.opening_agenda_generation.max_tokens,
                    seed=seed + attempt_index,
                    disable_thinking=self.opening_agenda_generation.disable_thinking,
                    response_schema=OPENING_INQUIRY_AGENDA_SCHEMA,
                    response_schema_name="legal_skill_guard_opening_inquiry_agenda",
                ),
            )
            patch, parse_mode, violations, changes = parse_opening_inquiry_agenda(
                response.content,
                opening=opening,
                state=state,
            )
            attempts.append(
                PolicyAttempt(
                    raw_output=response.content,
                    parse_mode=parse_mode,
                    deterministic_changes=changes,
                    health_violations=violations,
                    prompt_tokens=response.prompt_tokens,
                    completion_tokens=response.completion_tokens,
                    finish_reason=response.finish_reason,
                )
            )
            if patch.observations and len(patch.observations) > best_partial_size:
                best_partial = patch
                best_partial_size = len(patch.observations)
            if not violations:
                return patch, attempts, False, visible_input
            request_messages = [
                *base,
                {
                    "role": "user",
                    "content": (
                        "上一输出含有无效、已知、复合或要求法律判断的事实维度："
                        + "；".join(violations)
                        + "。请重新输出完整议程；每项只保留一个由开场支持、客户可观察且"
                        "开场尚未回答的事实属性。不得解释。"
                    ),
                },
            ]
        if best_partial is not None:
            return best_partial, attempts, True, visible_input
        # This arm-invariant agenda is optional visible context, not a gate or a
        # replacement policy.  If every bounded proposal was rejected, retain the
        # attempts and an explicit empty agenda rather than fabricating a target
        # or invalidating an otherwise attributable dialogue. The frozen lawyer
        # still has its ordinary ``new_visible_gap`` action on the first turn.
        return StatePatch(), attempts, True, visible_input

    def _generate_investigation_plan(
        self,
        opening: str,
        state: ConsultationState,
        seed: int,
        *,
        planner_skill_memory: str = EMPTY_PLANNER_SKILL_MEMORY,
    ) -> tuple[StatePatch, list[PolicyAttempt], bool, list[Message]]:
        """Build a skill-informed visible-input fact agenda before dialogue.

        All K members in one case group receive the same batch-start library and
        request seed, so this intervention changes the available inquiry space
        without confounding within-group comparisons.
        """

        assert self.planner_prompt is not None
        planner_system = self.planner_prompt + "\n\n" + planner_skill_memory
        planner_repair_system = (
            str(self.planner_repair_prompt or "") + "\n\n" + planner_skill_memory
        )
        base = [
            {"role": "system", "content": planner_system},
            {"role": "user", "content": f"客户开场：\n{opening}"},
        ]
        visible_input = [Message.model_validate(item) for item in base]

        def rejected_items_from(changes: list[str]) -> list[tuple[str, str]]:
            rejected_by_id: dict[str, dict[str, str]] = {}
            for change in changes:
                if change.startswith("reject_planner_target:"):
                    _, fact_id, label = change.split(":", 2)
                    rejected_by_id.setdefault(fact_id, {})["label"] = label
                elif change.startswith("reject_planner_reason:"):
                    _, fact_id, reason = change.split(":", 2)
                    rejected_by_id.setdefault(fact_id, {})["reason"] = reason
            return [
                (item["label"], item.get("reason", "unsafe"))
                for item in rejected_by_id.values()
                if item.get("label")
            ]

        request_messages = list(base)
        attempts: list[PolicyAttempt] = []
        active_repair_focus: str | None = None
        base_repair_transport_bound = int(
            INVESTIGATION_PLAN_SCHEMA["properties"]["unknowns"]["maxItems"]
        )
        # The first draft intentionally uses unconstrained decoding so that the
        # frozen planner keeps its natural planning distribution.  If that draft
        # contains more targets than the structured repair transport's default
        # array bound, a later editor must still be able to carry every already-safe
        # target.  Freeze the repair ceiling to the first draft's actual size; this
        # is a transport allowance, not permission for the editor to expand the
        # original agenda.
        repair_transport_bound = base_repair_transport_bound
        # Repairs are model-authored complete JSON objects, but already-safe targets
        # are immutable state, not editable prose.  Accumulate those targets here and
        # merge them back after every later parse.  This prevents a repair of one bad
        # label from silently deleting or rewriting an unrelated, valid inquiry.
        preserved_safe_targets: list[FactObservation] = []
        for attempt_index in range(self.max_planning_attempts):
            transport_overflow = False
            overflow_candidate_targets: list[FactObservation] = []
            active_generation = (
                self.planner_generation if attempt_index == 0 else self.planner_repair_generation
            )
            response_schema = None
            if attempt_index > 0:
                response_schema = json.loads(json.dumps(INVESTIGATION_PLAN_SCHEMA))
                response_schema["properties"]["unknowns"]["maxItems"] = repair_transport_bound
            response = self.planner_client.generate(
                request_messages,
                GenerationConfig(
                    temperature=active_generation.temperature,
                    top_p=active_generation.top_p,
                    max_tokens=active_generation.max_tokens,
                    seed=seed + attempt_index,
                    disable_thinking=active_generation.disable_thinking,
                    # The frozen planner's first draft already has a stable outer
                    # contract and should retain its natural planning distribution.
                    # Strict constrained decoding is reserved for rejected-draft
                    # editing, where Qwen otherwise copied malformed top-level
                    # structures across every remaining attempt.
                    response_schema=response_schema,
                    response_schema_name="legal_skill_guard_investigation_plan",
                ),
            )
            patch, parse_mode, violations, deterministic_changes = parse_investigation_plan(
                response.content, state
            )
            if attempt_index == 0 and violations:
                first_draft_target_count = 0
                planner_candidates = [
                    response.content.strip(),
                    *_balanced_json_objects(response.content),
                ]
                for candidate in planner_candidates:
                    try:
                        parsed_candidate = json.loads(candidate)
                    except json.JSONDecodeError:
                        continue
                    candidate_unknowns = (
                        parsed_candidate.get("unknowns")
                        if isinstance(parsed_candidate, dict)
                        else None
                    )
                    if isinstance(candidate_unknowns, list):
                        first_draft_target_count = len(candidate_unknowns)
                        break
                if first_draft_target_count > repair_transport_bound:
                    deterministic_changes.append(
                        "align_planner_repair_transport_bound_to_first_draft:"
                        f"{repair_transport_bound}->{first_draft_target_count}"
                    )
                    repair_transport_bound = first_draft_target_count
            if preserved_safe_targets:
                parsed_observations = list(patch.observations)
                current_by_id = {item.fact_id: item for item in patch.observations}
                current_by_label = {item.label: item for item in patch.observations}
                merged_observations: list[FactObservation] = []
                preserved_ids = {item.fact_id for item in preserved_safe_targets}
                preserved_labels = {item.label for item in preserved_safe_targets}
                for preserved in preserved_safe_targets:
                    current = current_by_id.get(preserved.fact_id)
                    same_label_item = current_by_label.get(preserved.label)
                    if current is not None and current != preserved:
                        # The preserved target is immutable state.  Once the
                        # deterministic merge restores it, the attempted rewrite
                        # is useful audit evidence but is no longer present in the
                        # plan that can reach a trajectory.  Treating the already
                        # repaired artifact as blocking made bounded editing loop
                        # on an identical, safe plan until exhaustion.
                        deterministic_changes.append(
                            f"restore_preserved_planner_target:{preserved.fact_id}"
                        )
                    elif current is None and same_label_item is not None:
                        deterministic_changes.append(
                            "restore_preserved_planner_target_id:"
                            f"{same_label_item.fact_id}->{preserved.fact_id}"
                        )
                    elif current is None:
                        deterministic_changes.append(
                            f"restore_omitted_preserved_planner_target:{preserved.fact_id}"
                        )
                    merged_observations.append(preserved.model_copy(deep=True))
                merged_observations.extend(
                    item
                    for item in patch.observations
                    if item.fact_id not in preserved_ids and item.label not in preserved_labels
                )
                if len(merged_observations) > repair_transport_bound:
                    transport_overflow = True
                    violations.append("planner_repair_exceeds_target_transport_bound")
                    deterministic_changes.append(
                        "planner_repair_safe_target_overflow:"
                        f"{len(merged_observations)}>{repair_transport_bound}"
                    )
                    overflow_candidate_targets = [
                        item
                        for item in parsed_observations
                        if item.fact_id not in preserved_ids and item.label not in preserved_labels
                    ]
                patch = patch.model_copy(update={"observations": merged_observations})
            known_safe_ids = {item.fact_id for item in preserved_safe_targets}
            known_safe_labels = {item.label for item in preserved_safe_targets}
            # Treat the accumulated safe agenda as committed state.  A repair
            # draft whose individually valid targets overflow the bounded complete
            # plan is not a valid transaction: promoting its new targets here
            # would make every later repair restore more items than the transport
            # can represent.  Keep the prior committed targets and let the next
            # model-authored revision select a bounded subset from the new pool.
            if not transport_overflow:
                for item in patch.observations:
                    if item.fact_id not in known_safe_ids and item.label not in known_safe_labels:
                        preserved_safe_targets.append(item.model_copy(deep=True))
                        known_safe_ids.add(item.fact_id)
                        known_safe_labels.add(item.label)
            current_safe_targets = [
                {
                    "fact_id": item.fact_id,
                    "label": item.label,
                    "criticality": item.criticality,
                    "target_kind": item.target_kind,
                }
                for item in patch.observations
            ]
            if active_repair_focus:
                deterministic_changes.append(
                    f"planner_repair_focus_after_stagnation:{active_repair_focus}"
                )
            attempts.append(
                PolicyAttempt(
                    raw_output=response.content,
                    parse_mode=parse_mode,
                    deterministic_changes=deterministic_changes,
                    health_violations=violations,
                    prompt_tokens=response.prompt_tokens,
                    completion_tokens=response.completion_tokens,
                    finish_reason=response.finish_reason,
                )
            )
            if not violations:
                # Only a fully valid revision may enter the trajectory. Safe targets
                # are carried across edits deterministically; rejected targets never
                # enter this accumulation and therefore cannot be laundered by retry.
                return patch, attempts, False, visible_input
            rejected_items = rejected_items_from(deterministic_changes)
            rejected_labels = [label for label, _ in rejected_items]
            rejected_reasons = [reason for _, reason in rejected_items]
            rejected_label_instruction = (
                "本轮被拒的原始中文label为："
                + json.dumps(rejected_labels, ensure_ascii=False)
                + "。不得原样重复这些label；不能安全原子化时就删除该项。"
                if rejected_labels
                else ""
            )
            previous_rejected_items = (
                rejected_items_from(attempts[-2].deterministic_changes)
                if len(attempts) >= 2
                else []
            )
            stagnated = bool(rejected_labels) and (
                (
                    len(attempts) >= 2
                    and attempts[-1].health_violations == attempts[-2].health_violations
                )
                or (
                    bool(previous_rejected_items)
                    and sorted(rejected_items) == sorted(previous_rejected_items)
                )
            )
            # Pure legal/evidentiary judgments with no observable nucleus are
            # deleted in one revision.  A legal comparison or abstract legal label
            # that still names an explicit observable core is instead routed to the
            # same bounded editor for de-legalization.  It is never auto-accepted:
            # the complete replacement must pass the ordinary safety contract.
            factual_reframe_items = [
                (label, reason)
                for label, reason in rejected_items
                # Give the bounded semantic editor one opportunity after the first
                # draft to preserve an observable core while removing a legal
                # characterization.  If its replacement is still rejected for the
                # same class on a later attempt, route it to mandatory deletion so
                # there remains an actual generation turn in which to execute that
                # instruction.  Previously deletion was first decided only after the
                # final response, making a bounded multi-edit contract impossible
                # to satisfy even when the rest of the plan was sound.
                if attempt_index == 0
                and not stagnated
                and planner_target_has_recoverable_observable_core(label, reason)
            ]
            factual_reframe_labels = {label for label, _ in factual_reframe_items}
            mandatory_drop_items = [
                (label, reason)
                for label, reason in rejected_items
                if label not in factual_reframe_labels
                and (
                    any(
                        code.startswith(("abstract_", "legal_or_evidentiary_judgment"))
                        or code
                        in {
                            "question_requests_legal_judgment_from_client",
                            "sensitive_personal_identifier",
                            "generic_or_sensitive_identity_request",
                            "generic_mechanical_expansion",
                            "generic_instrument_without_observable_attribute",
                            "presupposes_opening_negated_response_event",
                            "unobservable_third_party_internal_process",
                        }
                        for code in reason.split("|")
                    )
                    # An unestablished event attribute gets one genuine semantic
                    # rewrite opportunity.  If the editor then repeats the same
                    # rejected proposition, remove that optional target and rebuild
                    # from the already-approved plan instead of exhausting the whole
                    # trajectory.  No rejected target is accepted and no hidden fact
                    # is invented; this only makes the bounded repair contract
                    # converge safely when the frozen small editor is copy-anchored.
                    or (
                        stagnated
                        and any(
                            code == "multiple_primary_questions"
                            or (
                                code == "presupposes_unestablished_response_event"
                                and all(
                                    "presupposes_unestablished_response_event"
                                    in other_reason.split("|")
                                    for _, other_reason in rejected_items
                                )
                            )
                            for code in reason.split("|")
                        )
                    )
                )
            ]
            mechanism_drop_items = [
                (label, reason)
                for label, reason in rejected_items
                if "introduces_unestablished_private_transaction_mechanism" in reason.split("|")
            ]
            for item in mechanism_drop_items:
                if item not in mandatory_drop_items:
                    mandatory_drop_items.append(item)
            valid_existence_labels = [
                item.label
                for item in patch.observations
                if asks_response_event_existence(item.label)
            ]
            unestablished_items = [
                (label, reason)
                for label, reason in rejected_items
                if "presupposes_unestablished_response_event" in reason.split("|")
            ]
            unestablished_client_action_items = [
                (label, reason)
                for label, reason in rejected_items
                if "presupposes_unestablished_client_payment" in reason.split("|")
            ]
            unestablished_drop_items = [
                (label, reason)
                for label, reason in unestablished_items
                if any(
                    response_event_terms_in(label) & response_event_terms_in(valid_label)
                    for valid_label in valid_existence_labels
                )
            ]
            unestablished_reframe_items = [
                item for item in unestablished_items if item not in unestablished_drop_items
            ]
            for item in unestablished_drop_items:
                if item not in mandatory_drop_items:
                    mandatory_drop_items.append(item)
            mandatory_atomicize_items = [
                (label, reason)
                for label, reason in rejected_items
                if label not in {item[0] for item in mandatory_drop_items}
                and "multiple_primary_questions" in reason.split("|")
            ]
            ambiguous_actor_items = [
                (label, reason)
                for label, reason in rejected_items
                if label not in {item[0] for item in mandatory_drop_items}
                and "ambiguous_actor_reference" in reason.split("|")
            ]
            has_batch_intervention = bool(
                mandatory_drop_items
                or mandatory_atomicize_items
                or ambiguous_actor_items
                or unestablished_reframe_items
                or unestablished_client_action_items
                or factual_reframe_items
            )
            mandatory_drop_labels = {label for label, _ in mandatory_drop_items}
            deletion_only_stagnation = bool(
                stagnated
                and rejected_labels
                and set(rejected_labels) <= mandatory_drop_labels
                and current_safe_targets
            )
            mixed_repair_stagnation = bool(
                stagnated
                and rejected_labels
                and current_safe_targets
                and not deletion_only_stagnation
                and parse_mode != "fallback"
            )
            zero_safe_repair_stagnation = bool(
                stagnated
                and rejected_labels
                and not current_safe_targets
                and has_batch_intervention
                and parse_mode != "fallback"
            )
            focus_still_rejected = bool(
                active_repair_focus and active_repair_focus in rejected_labels
            )
            next_repair_focus = (
                active_repair_focus
                if focus_still_rejected
                else rejected_labels[0]
                if stagnated and not has_batch_intervention
                else None
            )
            if mandatory_drop_items:
                attempts[-1].deterministic_changes.append(
                    "planner_repair_mandatory_drop:"
                    + json.dumps(
                        [label for label, _ in mandatory_drop_items],
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                )
            if mandatory_atomicize_items:
                attempts[-1].deterministic_changes.append(
                    "planner_repair_mandatory_atomicize:"
                    + json.dumps(
                        [label for label, _ in mandatory_atomicize_items],
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                )
            if ambiguous_actor_items:
                attempts[-1].deterministic_changes.append(
                    "planner_repair_mandatory_actor_disambiguation:"
                    + json.dumps(
                        [label for label, _ in ambiguous_actor_items],
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                )
            if unestablished_reframe_items:
                attempts[-1].deterministic_changes.append(
                    "planner_repair_mandatory_existence_reframe:"
                    + json.dumps(
                        [label for label, _ in unestablished_reframe_items],
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                )
            if unestablished_client_action_items:
                attempts[-1].deterministic_changes.append(
                    "planner_repair_mandatory_client_action_existence_reframe:"
                    + json.dumps(
                        [label for label, _ in unestablished_client_action_items],
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                )
            if factual_reframe_items:
                attempts[-1].deterministic_changes.append(
                    "planner_repair_mandatory_factual_reframe:"
                    + json.dumps(
                        [label for label, _ in factual_reframe_items],
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                )
            repair_instruction = (
                "上一稿不合格。违规码："
                + json.dumps(violations, ensure_ascii=False)
                + "。"
                + rejected_label_instruction
                + "。只处理被拒目标；保留其他合格目标，不新增议题或机械补位。"
                "同一时间属性的年/月/日合为一个时间目标；法律或证据评价改成原label"
                "明确包含的底层客观事实，没有事实核心就删除。输出完整替代JSON。"
            )
            if transport_overflow:
                # Atomicising several rejected compound targets can legitimately
                # yield more individually safe candidates than fit in the frozen
                # complete-plan transport.  The overflowing draft is never partly
                # accepted and its new targets are not made immutable.  Ask the
                # bounded editor to author one complete plan from the previously
                # committed targets plus the visible candidate pool, with an
                # explicit remaining capacity.  No hidden case fact or evaluator
                # label is used in this reduction.
                attempts[-1].deterministic_changes.append(
                    "planner_repair_rebuild_within_transport_bound"
                )
                remaining_capacity = repair_transport_bound - len(preserved_safe_targets)
                request_messages = [
                    {"role": "system", "content": planner_repair_system},
                    {
                        "role": "user",
                        "content": (
                            "客户开场：\n"
                            + opening
                            + "\n\n上一稿中的目标逐项检查虽可作为事实问题，但合并恢复已通过"
                            "目标后超过完整计划的传输上限。上一稿不是合格计划，不得原样"
                            "复制，也不得新增、改写或拆分目标。issue_labels保持为："
                            + json.dumps(patch.issue_labels, ensure_ascii=False)
                            + "。下列先前已通过目标必须按给定字段和顺序原样置于unknowns"
                            "开头："
                            + json.dumps(
                                [
                                    {
                                        "fact_id": item.fact_id,
                                        "label": item.label,
                                        "criticality": item.criticality,
                                        "target_kind": item.target_kind,
                                    }
                                    for item in preserved_safe_targets
                                ],
                                ensure_ascii=False,
                                separators=(",", ":"),
                            )
                            + "。然后只能从下列候选中按原字段、原相对顺序选择至多"
                            + str(remaining_capacity)
                            + "项；优先保留最会改变当前咨询分析的独立核心维度，近义或"
                            "次要项可以不选："
                            + json.dumps(
                                [
                                    {
                                        "fact_id": item.fact_id,
                                        "label": item.label,
                                        "criticality": item.criticality,
                                        "target_kind": item.target_kind,
                                    }
                                    for item in overflow_candidate_targets
                                ],
                                ensure_ascii=False,
                                separators=(",", ":"),
                            )
                            + "。unknowns总数不得超过"
                            + str(repair_transport_bound)
                            + "。只输出一个完整替代JSON。"
                        ),
                    },
                ]
            elif parse_mode == "fallback" and "invalid_planner_json" in violations:
                # A length-truncated object is not an editable structured artifact.
                # Re-feeding it consumes more context and deterministically continues
                # the same enumeration.  Re-plan from the same visible opening with a
                # concise minimal-sufficient instruction; no facts are recovered from
                # or silently accepted out of the malformed response.
                request_messages = [
                    *base,
                    {
                        "role": "user",
                        "content": (
                            repair_instruction + "上一次输出未闭合，不要续写或重复穷举。"
                            "请从开场重新生成最小充分图谱，合并近义项，"
                            "优先保留会改变当前法律分析的独立核心维度，"
                            "并确保整个JSON在本次输出内闭合。"
                        ),
                    },
                ]
            elif zero_safe_repair_stagnation:
                # If every target in two consecutive drafts is rejected, the
                # deletion-only editor has no valid object it can emit because the
                # plan schema requires at least one unknown.  Re-feeding the bad
                # JSON copy-anchors a small model, while asking it to output an
                # empty array would contradict the schema.  Start a bounded fresh
                # plan from the same public opening instead.  The old labels are
                # carried only as a forbidden list; no hidden fact, evaluator
                # label, deterministic target, or partial rejected plan is used.
                attempts[-1].deterministic_changes.append(
                    "planner_repair_replan_from_opening_after_zero_safe_stagnation"
                )
                request_messages = [
                    {"role": "system", "content": planner_system},
                    {
                        "role": "user",
                        "content": (
                            "客户开场：\n"
                            + opening
                            + "\n\n连续两稿没有任何unknown通过事实问题门禁。"
                            "不要再参考或复述上一稿JSON，也不得输出空unknowns。"
                            "请仅根据上述公开开场重新生成一份最小事实调查计划："
                            "先选客户能根据亲历、沟通或已见文书回答的实际内容、"
                            "行为、时间、结果或当前状态；不让客户判断合法性、"
                            "证据充分性、程序合规性或机关权限。"
                            "以下旧label已被拒绝，不得原样重复："
                            + json.dumps(rejected_labels, ensure_ascii=False)
                            + "。不得猜测隐藏事实，不为凑数量扩展无关议题。"
                            "只输出符合系统schema的完整JSON。"
                        ),
                    },
                ]
            elif deletion_only_stagnation:
                # Re-feeding a semantically rejected label after the bounded editor
                # has twice classified it as deletion-only makes small models copy
                # that label again even when the instruction says to remove it. Do
                # not accept the filtered partial object. Instead ask for a fresh,
                # complete JSON object containing exactly the already-approved
                # targets, then pass that model-authored object through the ordinary
                # parser and safety gate on the next attempt. This generic repair
                # neither invents facts nor reads hidden case labels.
                attempts[-1].deterministic_changes.append(
                    "planner_repair_rebuild_from_approved_targets_after_drop_stagnation"
                )
                request_messages = [
                    {"role": "system", "content": planner_repair_system},
                    {
                        "role": "user",
                        "content": (
                            "客户开场：\n"
                            + opening
                            + "\n\n连续两稿仍重复了下列已被门禁判定为只能删除的目标："
                            + json.dumps(rejected_labels, ensure_ascii=False)
                            + "。这些目标必须逐项从unknowns中删除，不得在新稿中出现。"
                            "不要再参考或复述上一稿全文。请输出一个全新的完整JSON，"
                            "issue_labels保持为："
                            + json.dumps(patch.issue_labels, ensure_ascii=False)
                            + "；unknowns必须且只能包含下列已经通过门禁的目标，按给定"
                            "顺序和字段原样输出，不得增删改写："
                            + json.dumps(
                                current_safe_targets,
                                ensure_ascii=False,
                                separators=(",", ":"),
                            )
                            + "。只输出完整替代稿JSON。"
                        ),
                    },
                ]
            elif mixed_repair_stagnation:
                # Re-feeding a complete draft that contains several persistent
                # defect classes makes a small structured editor copy the same bad
                # labels even when each individual instruction is correct. Rebuild
                # from immutable approved targets plus a compact typed worklist.
                # The model still authors every retained/reframed target, the normal
                # parser and safety gate still judge the complete result, and no
                # hidden case fact or deterministic replacement is introduced.
                attempts[-1].deterministic_changes.append(
                    "planner_repair_rebuild_from_approved_targets_after_mixed_stagnation"
                )
                rejected_worklist = [
                    {"label": label, "reason": reason} for label, reason in rejected_items
                ]
                request_messages = [
                    {"role": "system", "content": planner_repair_system},
                    {
                        "role": "user",
                        "content": (
                            "客户开场：\n"
                            + opening
                            + "\n\n连续两稿仍重复多类不合格目标。不要再参考或复述上一稿全文。"
                            "请从已经通过门禁的不可变目标和下列待处理清单重建完整JSON。"
                            "issue_labels保持为："
                            + json.dumps(patch.issue_labels, ensure_ascii=False)
                            + "；下列已通过目标必须按给定字段和顺序原样保留："
                            + json.dumps(
                                current_safe_targets,
                                ensure_ascii=False,
                                separators=(",", ":"),
                            )
                            + "。待处理清单为："
                            + json.dumps(
                                rejected_worklist,
                                ensure_ascii=False,
                                separators=(",", ":"),
                            )
                            + "。逐项按系统规则去法律化、改成不预设发生的存在性事实、"
                            "原子化，或者在没有安全客观核心时删除；原被拒label不得原样"
                            "出现。不得新增清单以外的议题或事实维度。只输出完整替代稿JSON。"
                        ),
                    },
                ]
            else:
                labels_for_editor = (
                    [
                        label
                        for label, _ in [
                            *mandatory_drop_items,
                            *mandatory_atomicize_items,
                            *ambiguous_actor_items,
                            *unestablished_reframe_items,
                            *unestablished_client_action_items,
                            *factual_reframe_items,
                        ]
                    ]
                    if has_batch_intervention
                    else [next_repair_focus]
                    if next_repair_focus
                    else rejected_labels
                )
                reasons_for_editor = (
                    [
                        reason
                        for _, reason in [
                            *mandatory_drop_items,
                            *mandatory_atomicize_items,
                            *ambiguous_actor_items,
                            *unestablished_reframe_items,
                            *unestablished_client_action_items,
                            *factual_reframe_items,
                        ]
                    ]
                    if has_batch_intervention
                    else [reason for label, reason in rejected_items if label == next_repair_focus]
                    if next_repair_focus
                    else rejected_reasons
                )
                request_messages = [
                    {"role": "system", "content": planner_repair_system},
                    {
                        "role": "user",
                        "content": (
                            "客户开场：\n"
                            + opening
                            + "\n\n上一稿JSON：\n"
                            + response.content
                            + "\n\n违规码："
                            + json.dumps(violations, ensure_ascii=False)
                            + "\n被拒的原始中文label："
                            + json.dumps(labels_for_editor, ensure_ascii=False)
                            + "\n门禁给出的结构化原因："
                            + json.dumps(reasons_for_editor, ensure_ascii=False)
                            + (
                                "\n下列上一稿目标已经通过门禁，必须按给出的fact_id、label和"
                                "criticality逐项原样保留，不得删除、改写或换序："
                                + json.dumps(
                                    current_safe_targets,
                                    ensure_ascii=False,
                                    separators=(",", ":"),
                                )
                                + "。"
                                if current_safe_targets
                                else ""
                            )
                            + (
                                "\n检测到连续两稿完全相同。本轮只修改上述唯一一个label，"
                                "其他unknown必须原样保留；该label必须拆分、去法律化或删除，"
                                "不得再原样输出。"
                                if next_repair_focus
                                else ""
                            )
                            + (
                                "\n下列明确列出的目标属于抽象概念、法律/证据判断或其他"
                                "不可安全修复项，本轮必须逐项从unknowns中删除，禁止改写、"
                                "替换或据此新增事实："
                                + json.dumps(
                                    [label for label, _ in mandatory_drop_items],
                                    ensure_ascii=False,
                                )
                                + "。此指令不适用于其他被拒目标。"
                                if mandatory_drop_items
                                else ""
                            )
                            + (
                                "\n下列各项把开场的司法或公权力程序错换成了"
                                "未建立的私人协议、合同或付款机制。本轮必须把它们"
                                "从unknowns中删除，不得原样保留或另造私人交易："
                                + json.dumps(
                                    [label for label, _ in mechanism_drop_items],
                                    ensure_ascii=False,
                                )
                                + "。"
                                if mechanism_drop_items
                                else ""
                            )
                            + (
                                "\n下列各项确实跨越不同对象、不同事件或互不依赖的答案。"
                                "本轮只从每个原项中保留一个会直接改变当前咨询分析、且客户"
                                "可凭亲历或已见文件回答的原子事实核心；不得扩成多个碎槽，"
                                "不得新增原项没有的事实。无法选择安全核心时删除该项："
                                + json.dumps(
                                    [label for label, _ in mandatory_atomicize_items],
                                    ensure_ascii=False,
                                )
                                + "。"
                                if mandatory_atomicize_items
                                else ""
                            )
                            + (
                                "\n下列各项把事故或事件与工作活动相联系，却没有说明是谁的"
                                "工作，容易把第三方行为错误问成客户本人行为。本轮必须保持"
                                "原有可观察关系维度，并仅依据客户开场补出明确行为人；若开场"
                                "未给出姓名或身份，就使用‘事故中行为人’或‘相关人员’等"
                                "中性称谓，禁止默认改成‘您’："
                                + json.dumps(
                                    [label for label, _ in ambiguous_actor_items],
                                    ensure_ascii=False,
                                )
                                + "。"
                                if ambiguous_actor_items
                                else ""
                            )
                            + (
                                "\n下列各项错误预设了一份尚未由开场建立的通知、决定、"
                                "答复或回应。本轮必须把每项改成同一对象是否实际发出、"
                                "收到、作出或发生的单一存在性目标；禁止改成内容、日期、"
                                "发送方、接收人、依据、方式或其他正向属性："
                                + json.dumps(
                                    [label for label, _ in unestablished_reframe_items],
                                    ensure_ascii=False,
                                )
                                + "。"
                                + "原项若是文号、案号或编号，不得改问‘编号是否"
                                "已确定’；只能改问对应的文书、判决、裁定或决定是否"
                                "实际作出，或删除该项。"
                                if unestablished_reframe_items
                                else ""
                            )
                            + (
                                "\n下列各项错误预设客户已经付款、出资、还贷或缴纳，"
                                "并直接追问金额、方式、时间等属性。开场尚未建立该行为，"
                                "本轮必须把同一行为的这些项合并为一个不预设发生的存在性"
                                "或实际投入目标，例如询问客户是否存在实际出资、还贷、"
                                "家务照料或其他贡献；不得继续保留金额、方式、时间等"
                                "正向属性，也不得为每个被拒项各造一个同义存在目标："
                                + json.dumps(
                                    [label for label, _ in unestablished_client_action_items],
                                    ensure_ascii=False,
                                )
                                + "。"
                                if unestablished_client_action_items
                                else ""
                            )
                            + (
                                "\n下列各项含有不应预先认定的法律化称谓，但同时保留了"
                                "可观察事实核心。本轮必须去掉侵权、违法、犯罪、违约、"
                                "诈骗或不正当竞争等定性，只保留原项已经表达的具体行为、"
                                "措施、沟通、时间、金额、方式或结果；不得新增案件事实，"
                                "若原项是纠正某种被定性行为的措施及证据，只保留‘客户在"
                                "所述事件后实际采取的措施’这一原有行动维度，不保留定性词"
                                "或证据这一第二维度；"
                                "原项若以客户本人是否知悉、知晓、知道或了解为目标，必须"
                                "去掉法律定性，改问客户当时把具体商品、来源、款项或任务"
                                "理解成什么，或者对方当时如何说明；若询问的是对方是否"
                                "知悉，必须改问客户实际作出的告知、发送、说明或其他"
                                "可观察沟通；"
                                "也不得删除该调查维度："
                                + json.dumps(
                                    [label for label, _ in factual_reframe_items],
                                    ensure_ascii=False,
                                )
                                + "。"
                                if factual_reframe_items
                                else ""
                            )
                            + "\n上一稿已被拒，禁止原样复制。"
                            "现在严格按系统规则编辑，只输出完整修订后的替代稿JSON。"
                        ),
                    },
                ]
            active_repair_focus = next_repair_focus
        raise InvestigationPlanningError(
            "investigation planner failed closed without a fully valid replacement: "
            + ";".join(attempts[-1].health_violations),
            attempts,
        )

    def _generate_policy(
        self,
        messages: list[Message],
        state: ConsultationState,
        seed: int,
    ) -> tuple[PolicyEnvelope, list[PolicyAttempt], list[str]]:
        base = [item.model_dump(mode="json") for item in messages]
        response_schema = self._policy_output_schema_for_state(state)
        request_messages = list(base)
        attempts: list[PolicyAttempt] = []
        envelope = None
        violations: list[str] = []
        previous_rejected_signature: tuple[str, str | None, str, tuple[str, ...]] | None = None
        for attempt_index in range(self.max_policy_attempts):
            is_repair = attempt_index > 0
            response = self.policy_client.generate(
                request_messages,
                GenerationConfig(
                    # Exploration belongs to the first sampled policy action.  A
                    # contract repair edits representation/target alignment and is
                    # deliberately lower-variance, while remaining the same model.
                    temperature=(
                        min(self.policy_generation.temperature, 0.2)
                        if is_repair
                        else self.policy_generation.temperature
                    ),
                    top_p=self.policy_generation.top_p,
                    max_tokens=self.policy_generation.max_tokens,
                    seed=seed + attempt_index,
                    disable_thinking=self.policy_generation.disable_thinking,
                    response_schema=response_schema,
                    response_schema_name="legal_skill_guard_policy_action",
                ),
            )
            envelope, parse_mode = parse_policy_envelope(response.content)
            envelope, deterministic_changes = normalize_policy_envelope(envelope, state)
            violations = policy_health_violations(envelope, state)
            attempts.append(
                PolicyAttempt(
                    raw_output=response.content,
                    parse_mode=parse_mode,
                    deterministic_changes=deterministic_changes,
                    health_violations=violations,
                    prompt_tokens=response.prompt_tokens,
                    completion_tokens=response.completion_tokens,
                    finish_reason=response.finish_reason,
                )
            )
            blocking = blocking_policy_health_violations(violations)
            if not blocking:
                return envelope, attempts, violations
            repair_violations = list(dict.fromkeys(blocking))
            rejected_signature = (
                envelope.action.action_type,
                envelope.action.target_id,
                re.sub(r"\s+", "", envelope.action.content),
                tuple(repair_violations),
            )
            repair_stagnated = rejected_signature == previous_rejected_signature
            previous_rejected_signature = rejected_signature
            # Only a complete, parseable rejected action is an editable artifact.
            # Feeding a length-truncated or malformed completion back as assistant
            # context caused Qwen to continue the corruption instead of repairing it.
            # The same applies when a repair reproduces the same target, question,
            # and violations: retaining that rejected assistant turn anchors the
            # next completion to copy it again.  Rebuild from the unchanged visible
            # state plus the explicit repair contract; the same frozen model still
            # authors the replacement and all ordinary gates remain in force.
            editable_previous = (
                response.finish_reason != "length"
                and parse_mode != "fallback"
                # An exact repeat is not useful editable content. Re-feeding it as
                # the assistant's latest turn anchors small models to copy the same
                # action despite a repair instruction that forbids that target.
                # Rebuild from the unchanged visible state and the explicit allowed
                # target set instead; the next model action still passes every
                # ordinary policy and question-health gate.
                and "repeated_question_text"
                not in {
                    str(item).removeprefix("warning:model_behavior:")
                    for item in repair_violations
                }
                and not repair_stagnated
            )
            # A repair edits the same joint action; it must receive the exact
            # selected execution cards again.  Dropping this context while still
            # recording ``activated_skill_ids`` made repaired questions look
            # skill-conditioned even though the repairing model could no longer
            # see the selected skill.  Keep action identity and intervention
            # delivery invariant across every bounded realization attempt.
            request_messages = [*base]
            if editable_previous:
                request_messages.append({"role": "assistant", "content": response.content})
            request_messages.append(
                {
                    "role": "user",
                    "content": policy_repair_instruction(
                        repair_violations,
                        state,
                    ),
                }
            )
        assert envelope is not None
        # Behaviour-only defects are valid lawyer outputs and returned on the first
        # attempt. Only integrity/safety failures enter this bounded repair path.
        blocking = blocking_policy_health_violations(violations)
        raise RuntimeError(
            "lawyer action remained structurally invalid after bounded repair: "
            + ";".join(sorted(set(violations)))
        )

    @staticmethod
    def _normalize_nonterminal_operation(decision: ActionDecision) -> ActionDecision:
        if decision.final.action_type != "retrieve":
            return decision
        before = decision.final.model_dump(mode="json")
        decision.final = StructuredAction(
            action_type="verify",
            target_type=decision.final.target_type,
            target_id=decision.final.target_id,
            reason="no_rag_request_visible_material",
            expected_information=decision.final.expected_information,
            content=decision.final.content,
            constraints=decision.final.constraints,
            confidence=decision.final.confidence,
        )
        decision.changes.append(
            {
                "source": "no_rag_normalization",
                "before": before,
                "after": decision.final.model_dump(mode="json"),
            }
        )
        return decision


def parse_investigation_plan(
    text: str, state: ConsultationState
) -> tuple[StatePatch, str, list[str], list[str]]:
    """Parse and validate a local planner agenda without hidden case labels."""

    raw = text.strip()
    value = None
    parse_mode = "fallback"
    for index, candidate in enumerate([raw, *_balanced_json_objects(raw)]):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            value = parsed
            parse_mode = "json" if index == 0 else "json_fragment"
            break
    if value is None:
        return StatePatch(), "fallback", ["invalid_planner_json"], []
    if set(value) != {"issue_labels", "unknowns"}:
        return StatePatch(), parse_mode, ["invalid_planner_top_level_keys"], []
    issue_labels = value.get("issue_labels")
    unknowns = value.get("unknowns")
    if not isinstance(issue_labels, list) or not all(
        isinstance(item, str) and item.strip() for item in issue_labels
    ):
        return StatePatch(), parse_mode, ["invalid_planner_issue_labels"], []
    if not isinstance(unknowns, list) or not unknowns:
        return StatePatch(), parse_mode, ["planner_has_no_unknowns"], []

    observations: list[FactObservation] = []
    violations: list[str] = []
    deterministic_changes: list[str] = []
    existing_ids = {fact.fact_id for fact in state.facts}
    seen_ids: set[str] = set()
    seen_labels: set[str] = set()
    required_keys = {"fact_id", "label", "criticality", "target_kind"}
    opening = next(
        (str(fact.value or "") for fact in state.facts if fact.fact_id == "opening_statement"),
        "",
    )
    opening_denies_response_event = bool(
        re.search(
            r"(?:没有|并未|尚未|从未|均未|一直未|未曾).{0,16}"
            r"(?:收到|获得|作出|给出|出具|送达)?(?:答复|回复|回应|决定|通知)"
            r"(?![^，。；;]{0,8}(?:证据|凭证|记录))",
            opening,
        )
        or re.search(
            r"(?:答复|回复|回应|决定|通知).{0,8}(?:都)?(?:没有|并未|尚未|均未)"
            r"(?![^，。；;]{0,8}(?:证据|凭证|记录))",
            opening,
        )
    )
    opening_response_events = response_event_terms_in(opening)
    # A completed formal determination establishes the public decision event even
    # when the opening uses ordinary Chinese (“已被认定工伤”) rather than naming a
    # decision document. Keep this visible-state inference here, not in the generic
    # label parser: a planned label containing “被认定” is not itself evidence that
    # the event occurred.
    for match in re.finditer(r"(?:已经|已|业经|被).{0,8}认定", opening):
        prefix = opening[max(0, match.start() - 4) : match.start()]
        if not re.search(r"(?:未|没有|尚未|从未|不曾).{0,3}$", prefix):
            opening_response_events.add("决定")
            break
    if re.search(
        r"(?:行政机关|行政部门|政府|法院|仲裁机构|[\u4e00-\u9fff]{1,8}局)"
        r".{0,16}(?:作出|给予|予以).{0,8}(?:处理|处罚|处分|驳回|撤销|不予)",
        opening,
    ) or re.search(
        r"(?:行政机关|行政部门|政府|法院|仲裁机构|[\u4e00-\u9fff]{1,8}(?:局|部门))"
        r".{0,24}(?:退件|拒绝|驳回|不予)",
        opening,
    ):
        # An explicitly completed official disposition establishes that some
        # decision exists even when the opening uses the ordinary word “处理”.
        opening_response_events.add("决定")
    opening_has_relative_chronology = any(
        marker in opening for marker in ("此前", "之后", "随后", "前", "后", "期间", "次月", "当时")
    )
    opening_establishes_client_payment = bool(
        re.search(
            r"(?:我|本人|我们|客户).{0,20}(?:支付|付款|缴纳|还贷|偿还|出资)",
            opening,
        )
        or re.search(
            r"(?:支付|付款|缴纳|还贷|偿还|出资).{0,16}(?:由我|本人|我们|客户)",
            opening,
        )
        or re.search(r"(?:我们|双方|夫妻).{0,12}(?:共同还贷|共同出资|共同支付)", opening)
    )
    opening_establishes_private_transaction = bool(
        re.search(r"(?:协议|合同|约定|签署|签订)", opening)
    )
    opening_establishes_official_procedure = bool(
        re.search(
            r"(?:法院|执行|公安|侦查|刑案|行政机关|行政部门|"
            r"政府|仲裁|复议|诉讼|审判|查封|追缴)",
            opening,
        )
    )
    for index, item in enumerate(unknowns):
        item_violation_count = len(violations)
        if not isinstance(item, dict) or set(item) != required_keys:
            violations.append(f"invalid_planner_unknown_schema:{index}")
            continue
        fact_id = str(item.get("fact_id") or "").strip()
        label = str(item.get("label") or "").strip()
        criticality = str(item.get("criticality") or "")
        target_kind = str(item.get("target_kind") or "")
        if re.fullmatch(r"[a-z][a-z0-9_]+", fact_id) and len(fact_id) > 64:
            original_fact_id = fact_id
            suffix = hashlib.sha256(fact_id.encode("utf-8")).hexdigest()[:12]
            fact_id = f"{fact_id[:48].rstrip('_')}_{suffix}"
            deterministic_changes.append(f"shorten_planner_fact_id:{original_fact_id}->{fact_id}")
        elif fact_id and not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", fact_id):
            # ``fact_id`` is an internal join key, not legal content.  Small local
            # models occasionally put the sound Chinese label in this field despite
            # the explicit snake_case contract.  Preserve the target and derive a
            # stable, collision-resistant key from both model fields; never translate,
            # invent, or alter the legal proposition itself.
            original_fact_id = fact_id
            suffix = hashlib.sha256(f"{original_fact_id}\0{label}".encode()).hexdigest()[:20]
            fact_id = f"planned_fact_{suffix}"
            deterministic_changes.append(f"normalize_planner_fact_id:{original_fact_id}->{fact_id}")
        if not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", fact_id):
            violations.append(f"invalid_planner_fact_id:{fact_id or index}")
            continue
        if fact_id in existing_ids:
            violations.append(f"duplicate_planner_fact_id:{fact_id}")
        elif fact_id in seen_ids:
            # ``fact_id`` is only an internal join key.  During a requested split,
            # small models often copy the source key onto two different, otherwise
            # safe labels.  Preserve both model-authored propositions and derive a
            # stable unique key for the later one; a repeated label is still caught
            # independently below and cannot be laundered by this normalization.
            original_fact_id = fact_id
            suffix = hashlib.sha256(f"{original_fact_id}\0{label}".encode()).hexdigest()[:12]
            fact_id = f"{original_fact_id[:48].rstrip('_')}_{suffix}"
            if fact_id in existing_ids or fact_id in seen_ids:
                violations.append(f"duplicate_planner_fact_id:{original_fact_id}")
            else:
                deterministic_changes.append(
                    f"disambiguate_duplicate_planner_fact_id:{original_fact_id}->{fact_id}"
                )
        if label in seen_labels:
            violations.append(f"duplicate_planner_label:{label}")
        if criticality not in {"high", "medium", "low"}:
            violations.append(f"invalid_planner_criticality:{fact_id}")
        if target_kind not in {"client_fact", "evidence_or_third_party"}:
            violations.append(f"invalid_planner_target_kind:{fact_id}")
        document_join_key_only = bool(
            re.search(r"(?:文号|案号|文件编号|决定编号|通知编号)$", label)
        )
        precise_identifier_only = bool(
            document_join_key_only
            or re.search(r"(?:银行账户号码|银行卡号|账号)$", label)
            or re.search(r"(?:具体)?(?:姓名|全称)$", label)
            or re.search(
                r"(?:文件|材料|文书|通知书|决定书|判决书).{0,4}"
                r"(?:具体)?名称$",
                label,
            )
            or re.search(
                r"(?:项目|产品|试剂|人员|客户|员工|女子|施工方|产权人)"
                r".{0,10}(?:具体)?名称$",
                label,
            )
        )
        capped_identifier_criticality = "low" if document_join_key_only else "medium"
        identifier_rank = {"high": 0, "medium": 1, "low": 2}
        if (
            precise_identifier_only
            and criticality in identifier_rank
            and identifier_rank[criticality] < identifier_rank[capped_identifier_criticality]
        ):
            # Precise join keys can matter later for party or document matching, but
            # by themselves they do not outrank conduct, terms, performance, harm,
            # or document content. The exception is encoded by asking the operative
            # role/relationship rather than merely a literal name or number.
            original_criticality = criticality
            criticality = capped_identifier_criticality
            deterministic_changes.append(
                f"cap_precise_identifier_criticality:{fact_id}:"
                f"{original_criticality}->{criticality}"
            )
        asks_temporal_refinement = any(
            marker in label
            for marker in (
                "日期",
                "时间",
                "何时",
                "什么时候",
                "哪一天",
                "哪年",
                "哪月",
            )
        )
        if (
            criticality == "high"
            and asks_temporal_refinement
            and opening_has_relative_chronology
            and event_concepts(label) & event_concepts(opening)
        ):
            # The target itself is a sound factual join key; only its rank is
            # disproportionate once the opening already establishes the legally
            # relevant before/after sequence.  Normalize that representation defect
            # exactly as we do for document identifiers instead of asking the model
            # to paraphrase the same date until the retry budget is exhausted.
            criticality = "medium"
            deterministic_changes.append(
                f"cap_opening_event_date_criticality:{fact_id}:high->medium"
            )
        label_response_events = response_event_terms_in(label)
        response_event_existence_asked = asks_response_event_existence(label)
        label_negates_response_event = bool(
            re.search(
                r"(?:未|没有|尚未|从未).{0,12}(?:答复|回复|回应|决定|通知)"
                r"|(?:答复|回复|回应|决定|通知).{0,8}(?:未|没有|尚未|从未)",
                label,
            )
        )
        presupposes_positive_response_attributes = bool(
            label_response_events
            and not response_event_existence_asked
            and not label_negates_response_event
            and not any(
                marker in label
                for marker in ("诉求", "预期结果", "现实目标", "希望撤销", "希望变更")
            )
        )
        if opening_denies_response_event and presupposes_positive_response_attributes:
            violations.append(f"presupposes_opening_negated_response_event:{fact_id}")
        elif presupposes_positive_response_attributes and not (
            label_response_events & opening_response_events
        ):
            violations.append(f"presupposes_unestablished_response_event:{fact_id}")
        asks_client_payment_existence = bool(
            re.search(
                r"(?:是否|有无|有没有).{0,20}(?:支付|付款|缴纳|还贷|偿还|出资|投入)",
                label,
            )
            or re.search(
                r"(?:支付|付款|缴纳|还贷|偿还|出资|投入).{0,12}(?:是否|有无|有没有)",
                label,
            )
        )
        presupposes_client_payment_attribute = bool(
            re.search(
                r"(?:我|本人|我们|客户|你|您).{0,18}(?:实际)?"
                r"(?:支付|付款|缴纳|还贷|偿还|出资).{0,18}"
                r"(?:金额|数额|方式|时间|日期|渠道|来源)",
                label,
            )
        )
        if (
            presupposes_client_payment_attribute
            and not asks_client_payment_existence
            and not opening_establishes_client_payment
        ):
            violations.append(f"presupposes_unestablished_client_payment:{fact_id}")
        introduces_private_transaction_mechanism = bool(
            re.search(
                r"(?:协议|合同).{0,16}(?:签署|签订|付款|支付|价款|金额|"
                r"交付义务|履行义务)",
                label,
            )
            or re.search(
                r"(?:签署|签订|付款|支付|价款).{0,12}(?:协议|合同)",
                label,
            )
        )
        if (
            opening_establishes_official_procedure
            and not opening_establishes_private_transaction
            and introduces_private_transaction_mechanism
        ):
            # The guard does not invent the correct legal mechanism.  It only
            # prevents a visible official process from being silently replaced by
            # an unmentioned private transaction; the local planner must repair or
            # drop the proposition using the opening alone.
            violations.append(f"introduces_unestablished_private_transaction_mechanism:{fact_id}")
        # Surface projection may narrow a compound observable target, but it must
        # never erase a semantic violation already established from the opening
        # (for example, a payment attribute when no client payment was established).
        projected_label = atomic_factual_target_projection(fact_id, label) if label else None
        atomic_label = (
            projected_label
            if len(violations) == item_violation_count or projected_label == label
            else None
        )
        if atomic_label and atomic_label != label:
            deterministic_changes.append(
                f"project_planner_label_to_atomic_core:{fact_id}:{label}->{atomic_label}"
            )
            label = atomic_label
        if not label or atomic_label is None:
            violations.append(f"unsafe_planner_target:{fact_id}")
            if label:
                deterministic_changes.append(f"reject_planner_target:{fact_id}:{label}")
                reasons = factual_target_question_safety_violations(fact_id, label)
                # Preserve every item-level cause already emitted before the
                # question-safety check.  Otherwise a compound surface form can
                # hide a more important semantic failure such as presupposing a
                # notification that the opening never established, and the editor
                # keeps splitting the content instead of dropping that branch.
                for item_reason in violations[item_violation_count:]:
                    normalized_reason = (
                        item_reason[: -(len(fact_id) + 1)]
                        if fact_id and item_reason.endswith(f":{fact_id}")
                        else item_reason
                    )
                    if (
                        normalized_reason not in reasons
                        and normalized_reason != "unsafe_planner_target"
                    ):
                        reasons.append(normalized_reason)
                deterministic_changes.append(
                    f"reject_planner_reason:{fact_id}:{'|'.join(reasons) or 'unsafe'}"
                )
        item_violations = violations[item_violation_count:]
        already_explained = any(
            change.startswith(f"reject_planner_target:{fact_id}:")
            for change in deterministic_changes
        )
        if item_violations and label and not already_explained:
            # Every item-level rejection must identify the Chinese label and a
            # machine-readable reason for the repair editor.  Previously only the
            # question-safety gate emitted this mapping, so priority/criticality
            # failures supplied a bare code and the local editor copied the same
            # unknown until exhaustion.
            reason_codes = [
                reason[: -(len(fact_id) + 1)]
                if fact_id and reason.endswith(f":{fact_id}")
                else reason
                for reason in item_violations
            ]
            deterministic_changes.append(f"reject_planner_target:{fact_id}:{label}")
            deterministic_changes.append(
                f"reject_planner_reason:{fact_id}:{'|'.join(reason_codes)}"
            )
        seen_ids.add(fact_id)
        seen_labels.add(label)
        if len(violations) == item_violation_count:
            observations.append(
                FactObservation(
                    fact_id=fact_id,
                    label=label,
                    status="unknown",
                    value=None,
                    evidence_labels=[],
                    confidence=0.0,
                    criticality=criticality,  # type: ignore[arg-type]
                    target_kind=target_kind,  # type: ignore[arg-type]
                )
            )
    outcome_markers = ("诉求", "预期结果", "现实目标", "现实期望", "希望实现")
    if observations and all(
        any(marker in item.label for marker in outcome_markers) for item in observations
    ):
        violations.append("planner_has_only_outcome_targets")
    criticality_rank = {"high": 0, "medium": 1, "low": 2}
    ordered_observations = sorted(
        observations,
        key=lambda item: criticality_rank[item.criticality],
    )
    if [item.fact_id for item in ordered_observations] != [item.fact_id for item in observations]:
        deterministic_changes.append(
            "stable_sort_planner_targets_by_model_criticality:"
            + json.dumps(
                [item.fact_id for item in ordered_observations],
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
        observations = ordered_observations
    return (
        StatePatch(
            observations=observations,
            issue_labels=[item.strip() for item in issue_labels],
            risk_flags_add=[],
        ),
        parse_mode,
        violations,
        deterministic_changes,
    )
