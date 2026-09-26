"""TF-GRPO contrast packaging and prompt-skill teacher proposals.

The teacher learns a document that is shown to the frozen lawyer before it acts.
Source evidence is a separate, system-owned witness.  Nothing in this module
executes a skill or rewrites a lawyer action.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Annotated, Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from legal_skill_guard.agent.state_manager import reconstruct_execution_state
from legal_skill_guard.evaluation.semantic import TrajectoryEvaluation
from legal_skill_guard.evolution.advantage import AdvantageGroup, ContrastSelection
from legal_skill_guard.evolution.diagnosis import (
    SkillDiagnosis,
    TeacherBatchDiagnosisDraft,
    TeacherDiagnosisDraft,
    diagnosis_quality_issues,
)
from legal_skill_guard.inference.codex_cli_client import strict_output_schema
from legal_skill_guard.schemas.experiment import ResearchTrajectory
from legal_skill_guard.schemas.skill import SkillContract
from legal_skill_guard.schemas.state import ConsultationState, StatePatch
from legal_skill_guard.skills.loader import (
    find_lexical_near_duplicates,
    find_scope_redundancies,
    find_structural_duplicates,
    validate_skill_static,
)
from legal_skill_guard.skills.memory import (
    EMPTY_SKILL_MEMORY,
    GLOBAL_PLAYBOOK_SKILL_ID,
    policy_skill_document,
)
from legal_skill_guard.text_normalization import normalize_question
from legal_skill_guard.utils.hashing import canonical_json_sha256

SignalFamily = Literal[
    "fact_elicitation",
    "evidence_gap_identification",
    "safe_stop",
]


class TeacherProtocolError(RuntimeError):
    """The teacher response cannot be bound to the declared evidence package."""


def _domain_teacher_output_schema(
    *,
    package_id: str,
    requirements: list[dict[str, Any]],
) -> dict[str, Any]:
    """Bind structured output cardinality and identifiers to one package.

    The generic Pydantic model only knows the global upper bound.  A package,
    however, is an atomic transaction: every declared domain must receive one
    explicit CREATE/UPDATE/NOOP decision.  Encoding the exact cardinality and
    identifier sets in the request prevents a short, superficially valid list
    from being mistaken for a complete teacher decision.
    """

    schema = strict_output_schema(TeacherBatchDiagnosisDraft.model_json_schema())
    update_count = len(requirements)
    updates = schema["properties"]["updates"]
    updates["minItems"] = update_count
    updates["maxItems"] = update_count
    schema["properties"]["batch_id"]["enum"] = [package_id]
    draft_properties = schema["$defs"]["TeacherDiagnosisDraft"]["properties"]
    draft_properties["group_id"]["enum"] = [str(item["required_group_id"]) for item in requirements]
    draft_properties["skill_scope"]["enum"] = [str(item["domain"]) for item in requirements]
    return schema


BASELINE_CONTRACT_SUMMARY = (
    "冻结提示声明了开场锚定、客户事实优先、单目标提问、避免重复和适时结束等原则；"
    "这些是输入契约，不代表冻结模型已经稳定执行。来源若显示同状态下持续违反而较优轨迹"
    "稳定执行，可学习新增了明确条件、排序或状态转换步骤的执行技能，但不能只复述口号。"
)


class TeacherModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceForkWitness(TeacherModel):
    """One immutable high/low trajectory divergence supporting a hypothesis."""

    group_id: str
    case_id: str
    domain: str
    divergence_turn: int
    visible_state_sha256: str
    positive_trajectory_id: str
    negative_trajectory_id: str
    positive_action: dict[str, object]
    negative_action: dict[str, object]
    reward_gap: float


class SourceWitness(TeacherModel):
    """System-owned source contrast, deliberately separate from policy advice."""

    schema_version: Literal[1] = 1
    evidence_cluster_id: str
    signal_family: SignalFamily
    forks: list[SourceForkWitness] = Field(min_length=1)


class GroupEvidenceWitness(TeacherModel):
    """System-owned binding from a domain update to complete K-group cards."""

    schema_version: Literal[1] = 1
    package_id: str
    domain: str
    evidence_group_ids: list[str] = Field(min_length=1)
    source_case_ids: list[str] = Field(min_length=1)
    source_trajectory_ids: list[str] = Field(min_length=3)
    evidence_card_sha256: dict[str, str]


class TeacherProposal(TeacherModel):
    schema_version: Literal[2, 3] = 3
    group_id: str
    request_sha256: str
    response_sha256: str
    teacher_model: str
    parse_status: str
    static_issues: list[str] = Field(default_factory=list)
    deterministic_normalizations: list[str] = Field(default_factory=list)
    source_group_ids: list[str] = Field(default_factory=list)
    source_witness: SourceWitness | None = None
    group_evidence_witness: GroupEvidenceWitness | None = None
    diagnosis: SkillDiagnosis

    @property
    def usable_candidate(self) -> SkillContract | None:
        if self.parse_status != "valid_candidate" or self.static_issues:
            return None
        return self.diagnosis.candidate_skill


class PlaybookModeDraft(TeacherModel):
    """One source-bound success/failure mechanism extracted from K-group cards."""

    mode_type: Literal["success", "failure"]
    mechanism: str = Field(min_length=12, max_length=300)
    observable_context: str = Field(min_length=8, max_length=240)
    actionable_lesson: str = Field(min_length=12, max_length=240)
    risky_actions_to_avoid: list[str] = Field(default_factory=list, max_length=3)
    source_group_ids: list[str] = Field(min_length=1, max_length=8)
    evidence_limitations: list[str] = Field(default_factory=list, max_length=3)


class PlaybookModeBatchDraft(TeacherModel):
    """Bounded map-stage output for one disjoint subset of source cards."""

    package_id: str
    modes: list[PlaybookModeDraft] = Field(default_factory=list, max_length=8)
    no_new_mode_group_ids: list[str] = Field(default_factory=list, max_length=8)


class PlaybookModeArtifact(TeacherModel):
    """Auditable model response for one playbook map package."""

    schema_version: Literal[2] = 2
    package_id: str
    input_binding_sha256: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    request_sha256: str
    response_sha256: str
    teacher_model: str
    source_group_ids: list[str] = Field(min_length=1)
    modes: list[PlaybookModeDraft] = Field(default_factory=list, max_length=8)
    no_new_mode_group_ids: list[str] = Field(default_factory=list, max_length=8)


PlaybookEditableField = Literal[
    "procedure",
    "question_guidance",
    "contraindications",
    "failure_modes",
]
PLAYBOOK_ITEM_MAX_CHARACTERS = 180


class PlaybookPatchOperation(TeacherModel):
    """One exact, source-bound edit to the compact consultation playbook."""

    operation: Literal["ADD", "REPLACE", "DELETE"]
    field: PlaybookEditableField
    target: Annotated[str, Field(max_length=240)] | None
    value: Annotated[str, Field(max_length=PLAYBOOK_ITEM_MAX_CHARACTERS)] | None
    source_group_ids: list[str] = Field(min_length=1, max_length=16)
    rationale: str = Field(min_length=12, max_length=300)


class PlaybookPatchDraft(TeacherModel):
    """Reduce-stage output; empty operations is an explicit evidence-grounded NOOP."""

    package_id: str
    synthesis_summary: str = Field(min_length=12, max_length=500)
    operations: list[PlaybookPatchOperation] = Field(default_factory=list, max_length=8)
    noop_reason: str | None = Field(default=None, max_length=500)


class PlaybookReduceArtifact(TeacherModel):
    """Atomic reduce result containing the exact patch and materialized proposal."""

    schema_version: Literal[2] = 2
    package_id: str
    input_binding_sha256: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    proposal: TeacherProposal
    patch: PlaybookPatchDraft


# Backward-compatible public name for callers and persisted contracts.  The
# identifier itself is owned by the prompt-memory module that renders it.
PLAYBOOK_SKILL_ID = GLOBAL_PLAYBOOK_SKILL_ID
PLAYBOOK_NAME = "多轮法律事实调查经验手册"
PLAYBOOK_DESCRIPTION = (
    "从多案咨询轨迹中归纳的可执行事实调查经验，"
    "用于在当前可见信息下选择高价值、可回答且不重复的下一问题。"
)
PLAYBOOK_APPLICABILITY_CUES = [
    "客户正在进行法律咨询，且仍需通过对话补充与争议处理有关的可回答事实。"
]
PLAYBOOK_EXPECTED_EFFECTS = ["在不牺牲事实完整性和法律安全的前提下，提高每次提问获得新事实的效率。"]
PLAYBOOK_FIELD_LIMITS: dict[PlaybookEditableField, int] = {
    "procedure": 5,
    "question_guidance": 4,
    "contraindications": 5,
    "failure_modes": 5,
}
INITIAL_PLAYBOOK_MAX_PATCH_OPERATIONS = 8
EXISTING_PLAYBOOK_MAX_PATCH_OPERATIONS = 2


def playbook_interface_catalog() -> dict[str, object]:
    """Return the narrow editing interface for the one formal global playbook.

    The generic skill schema also supports domain-specific documents and three
    objectives for comparison baselines.  Exposing that larger catalog to the
    formal playbook teacher incorrectly suggested that it could choose a domain,
    objective, or document family.  This contract contains only the fixed identity
    and the four fields the reduce-stage patch is actually allowed to edit.
    """

    return {
        "schema_version": 1,
        "fixed_playbook_identity": {
            "skill_id": PLAYBOOK_SKILL_ID,
            "domain": "general",
            "objective": "fact_elicitation",
        },
        "editable_fields": {
            field: {
                "maximum_items": maximum,
                "maximum_characters_per_item": PLAYBOOK_ITEM_MAX_CHARACTERS,
            }
            for field, maximum in PLAYBOOK_FIELD_LIMITS.items()
        },
        "patch_operation_capacity": {
            "initial_creation": INITIAL_PLAYBOOK_MAX_PATCH_OPERATIONS,
            "existing_playbook_update": EXISTING_PLAYBOOK_MAX_PATCH_OPERATIONS,
        },
    }


def playbook_map_request_payload(
    *,
    package_id: str,
    evidence_cards: list[dict[str, Any]],
    current_playbook: SkillContract | None,
) -> dict[str, Any]:
    """Return the exact logical map input independently of transport metadata."""

    return {
        "schema_version": 2,
        "package_id": package_id,
        "current_playbook": (
            policy_skill_document(current_playbook) | {"version": current_playbook.version}
            if current_playbook is not None
            else None
        ),
        "group_evidence_cards": evidence_cards,
    }


def playbook_map_input_binding_sha256(
    *,
    package_id: str,
    evidence_cards: list[dict[str, Any]],
    current_playbook: SkillContract | None,
) -> str:
    return canonical_json_sha256(
        playbook_map_request_payload(
            package_id=package_id,
            evidence_cards=evidence_cards,
            current_playbook=current_playbook,
        )
    )


def playbook_reduce_request_payload(
    *,
    package_id: str,
    mode_artifacts: list[PlaybookModeArtifact],
    current_playbook: SkillContract | None,
    library_feedback: dict[str, Any] | None,
    maximum_operations: int,
) -> dict[str, Any]:
    """Return the exact logical reduce input used by the teacher request."""

    return {
        "schema_version": 1,
        "package_id": package_id,
        "current_playbook": (
            policy_skill_document(current_playbook) | {"version": current_playbook.version}
            if current_playbook is not None
            else None
        ),
        "mode_artifacts": [
            {
                "package_id": artifact.package_id,
                "source_group_ids": artifact.source_group_ids,
                "modes": [mode.model_dump(mode="json") for mode in artifact.modes],
            }
            for artifact in mode_artifacts
        ],
        "input_library_prequential_feedback": library_feedback,
        "field_capacity": PLAYBOOK_FIELD_LIMITS,
        "maximum_patch_operations": maximum_operations,
    }


def playbook_reduce_input_binding_sha256(
    *,
    package_id: str,
    mode_artifacts: list[PlaybookModeArtifact],
    current_playbook: SkillContract | None,
    library_feedback: dict[str, Any] | None,
    maximum_operations: int,
) -> str:
    return canonical_json_sha256(
        playbook_reduce_request_payload(
            package_id=package_id,
            mode_artifacts=mode_artifacts,
            current_playbook=current_playbook,
            library_feedback=library_feedback,
            maximum_operations=maximum_operations,
        )
    )


_EMBEDDED_NUMBERED_CLAUSE = re.compile(r"(?:^|[。；;]\s*)[（(]?\d+[.、)）]")


def _playbook_clause_atomicity_issues(value: str) -> list[str]:
    """Reject packed mini-documents that defeat clause-level local editing.

    This is a document-shape invariant, not a behavioral rule. Each stored list
    item must remain independently replaceable in a later block; numbered lists
    and chains of several semicolon-separated directives belong in separate patch
    operations instead.
    """

    issues: list[str] = []
    if _EMBEDDED_NUMBERED_CLAUSE.search(value):
        issues.append("embedded_numbered_list")
    if value.count("；") + value.count(";") > 1:
        issues.append("multiple_semicolon_clauses")
    return issues


def _playbook_mode_output_schema(*, package_id: str) -> dict[str, Any]:
    schema = strict_output_schema(PlaybookModeBatchDraft.model_json_schema())
    schema["properties"]["package_id"]["enum"] = [package_id]
    return schema


def _playbook_patch_output_schema(
    *, package_id: str, maximum_operations: int
) -> dict[str, Any]:
    schema = strict_output_schema(PlaybookPatchDraft.model_json_schema())
    schema["properties"]["package_id"]["enum"] = [package_id]
    schema["properties"]["operations"]["maxItems"] = maximum_operations
    return schema


def _next_patch_version(version: str) -> str:
    major, minor, patch = (int(item) for item in version.split("."))
    return f"{major}.{minor}.{patch + 1}"


def _apply_playbook_patch(
    current: SkillContract | None,
    patch: PlaybookPatchDraft,
) -> tuple[dict[PlaybookEditableField, list[str]], list[str]]:
    """Apply exact bounded edits without allowing an LLM to rewrite untouched text."""

    fields: dict[PlaybookEditableField, list[str]] = {
        field: list(getattr(current, field)) if current is not None else []
        for field in PLAYBOOK_FIELD_LIMITS
    }
    issues: list[str] = []
    touched_targets: set[tuple[str, str]] = set()
    for index, operation in enumerate(patch.operations):
        values = fields[operation.field]
        target = operation.target.strip() if operation.target is not None else None
        value = operation.value.strip() if operation.value is not None else None
        prefix = f"operation_{index}"
        if value is not None:
            issues.extend(
                f"{prefix}:{issue}" for issue in _playbook_clause_atomicity_issues(value)
            )
        if operation.operation == "ADD":
            if target is not None or not value:
                issues.append(f"{prefix}:invalid_add_shape")
                continue
            if value in values:
                issues.append(f"{prefix}:duplicate_add")
                continue
            values.append(value)
        elif operation.operation == "REPLACE":
            if not target or not value:
                issues.append(f"{prefix}:invalid_replace_shape")
                continue
            key = (operation.field, target)
            if key in touched_targets:
                issues.append(f"{prefix}:target_edited_twice")
                continue
            touched_targets.add(key)
            if target not in values:
                issues.append(f"{prefix}:replace_target_not_found")
                continue
            if value != target and value in values:
                issues.append(f"{prefix}:replace_creates_duplicate")
                continue
            values[values.index(target)] = value
        else:
            if not target or value is not None:
                issues.append(f"{prefix}:invalid_delete_shape")
                continue
            key = (operation.field, target)
            if key in touched_targets:
                issues.append(f"{prefix}:target_edited_twice")
                continue
            touched_targets.add(key)
            if target not in values:
                issues.append(f"{prefix}:delete_target_not_found")
                continue
            values.remove(target)

    for field, maximum in PLAYBOOK_FIELD_LIMITS.items():
        values = fields[field]
        if not values:
            issues.append(f"empty_playbook_field:{field}")
        if len(values) > maximum:
            issues.append(f"playbook_field_capacity_exceeded:{field}")
        if len(values) != len(set(values)):
            issues.append(f"duplicate_playbook_item:{field}")
        if any(len(item) > 240 for item in values):
            issues.append(f"playbook_item_too_long:{field}")
    return fields, sorted(set(issues))


def materialize_playbook_proposal(
    *,
    package_id: str,
    evidence_cards: list[dict[str, Any]],
    mode_artifacts: list[PlaybookModeArtifact],
    current_playbook: SkillContract | None,
    patch: PlaybookPatchDraft,
    teacher_model: str,
    request_sha256: str,
    response_sha256: str,
) -> TeacherProposal:
    """Deterministically replay one model-authored patch into its system proposal.

    The model authors only ``PlaybookPatchDraft``.  Candidate bytes, provenance,
    witnesses and diagnosis metadata are owned by the system and must therefore
    be exactly reproducible when an interrupted reduce artifact is resumed.
    """

    card_by_group = {str(card["group_id"]): card for card in evidence_cards}
    if len(card_by_group) != len(evidence_cards):
        raise TeacherProtocolError("playbook evidence contains duplicate group IDs")
    mapped_groups = [
        group_id for artifact in mode_artifacts for group_id in artifact.source_group_ids
    ]
    if len(mapped_groups) != len(set(mapped_groups)) or set(mapped_groups) != set(
        card_by_group
    ):
        raise TeacherProtocolError("playbook map artifacts do not partition all evidence cards")
    if current_playbook is not None and (
        current_playbook.skill_id != PLAYBOOK_SKILL_ID
        or current_playbook.domain != "general"
        or current_playbook.objective != "fact_elicitation"
    ):
        raise ValueError("current playbook has an incompatible identity")

    maximum_operations = (
        INITIAL_PLAYBOOK_MAX_PATCH_OPERATIONS
        if current_playbook is None
        else EXISTING_PLAYBOOK_MAX_PATCH_OPERATIONS
    )
    if patch.package_id != package_id:
        raise TeacherProtocolError(f"playbook patch package id mismatch: {package_id}")
    if len(patch.operations) > maximum_operations:
        raise TeacherProtocolError(
            "playbook patch exceeds the current document-local edit budget: "
            f"{package_id}: {len(patch.operations)} > {maximum_operations}"
        )
    if patch.operations and patch.noop_reason is not None:
        raise TeacherProtocolError("nonempty playbook patch cannot contain noop_reason")
    if not patch.operations and not (patch.noop_reason or "").strip():
        raise TeacherProtocolError("empty playbook patch requires a noop_reason")

    mode_groups = {
        group_id
        for artifact in mode_artifacts
        for mode in artifact.modes
        for group_id in mode.source_group_ids
    }
    used_groups: set[str] = set()
    for index, operation in enumerate(patch.operations):
        cited = set(operation.source_group_ids)
        if len(cited) != len(operation.source_group_ids) or not cited <= mode_groups:
            raise TeacherProtocolError(
                f"playbook patch source binding invalid: {package_id}:{index}"
            )
        used_groups.update(cited)

    candidate: SkillContract | None = None
    if patch.operations:
        fields, patch_issues = _apply_playbook_patch(current_playbook, patch)
        if patch_issues:
            raise TeacherProtocolError(
                "playbook patch cannot be applied exactly: " + ",".join(patch_issues)
            )
        current_definition = (
            {field: list(getattr(current_playbook, field)) for field in PLAYBOOK_FIELD_LIMITS}
            if current_playbook is not None
            else None
        )
        if current_definition == fields:
            raise TeacherProtocolError("playbook patch makes no document change")
        source_cards = [card_by_group[group_id] for group_id in sorted(used_groups)]
        current_case_ids = {str(card["case_id"]) for card in source_cards}
        current_trajectory_ids = {
            str(row["trajectory_id"])
            for card in source_cards
            for row in card.get("trajectory_summaries", [])
        }
        prior_case_ids = (
            set(current_playbook.provenance.source_case_ids)
            if current_playbook is not None
            else set()
        )
        prior_trajectory_ids = (
            set(current_playbook.provenance.source_trajectory_ids)
            if current_playbook is not None
            else set()
        )
        candidate = SkillContract.model_validate(
            {
                "schema_version": 2,
                "skill_id": PLAYBOOK_SKILL_ID,
                "name": PLAYBOOK_NAME,
                "version": (
                    _next_patch_version(current_playbook.version)
                    if current_playbook is not None
                    else "1.0.0"
                ),
                "domain": "general",
                "objective": "fact_elicitation",
                "description": PLAYBOOK_DESCRIPTION,
                "applicability_cues": PLAYBOOK_APPLICABILITY_CUES,
                **fields,
                "expected_effects": PLAYBOOK_EXPECTED_EFFECTS,
                "status": "candidate",
                "provenance": {
                    "source": "tf_grpo",
                    "source_evidence_cluster_id": package_id,
                    "source_signal_family": "fact_elicitation",
                    "source_case_ids": sorted(prior_case_ids | current_case_ids),
                    "source_trajectory_ids": sorted(
                        prior_trajectory_ids | current_trajectory_ids
                    ),
                    "generator_model": teacher_model,
                    "diagnosis_hash": response_sha256,
                },
            }
        )
        issues = validate_skill_static(candidate)
        if issues:
            raise TeacherProtocolError(
                "playbook candidate failed static validation: " + ",".join(issues)
            )

    witness_cards = [card_by_group[group_id] for group_id in sorted(used_groups)]
    witness = (
        GroupEvidenceWitness(
            package_id=package_id,
            domain="general",
            evidence_group_ids=sorted(used_groups),
            source_case_ids=sorted(str(card["case_id"]) for card in witness_cards),
            source_trajectory_ids=sorted(
                {
                    str(row["trajectory_id"])
                    for card in witness_cards
                    for row in card.get("trajectory_summaries", [])
                }
            ),
            evidence_card_sha256={
                str(card["group_id"]): canonical_json_sha256(card) for card in witness_cards
            },
        )
        if witness_cards
        else None
    )
    operation = (
        "UPDATE"
        if candidate is not None and current_playbook is not None
        else "CREATE"
        if candidate is not None
        else "NOOP"
    )
    diagnosis = SkillDiagnosis.model_validate(
        {
            "group_id": f"{package_id}::playbook",
            "failure_state": {"turn": None, "relevant_fields": []},
            "behavior_difference": {
                "positive_action": "采用跨案件证据支持的目标排序、问题组织与低收益转移方法",
                "negative_action": "继续沿用证据中反复出现的低收益、重复或不可回答询问模式",
            },
            "causal_hypothesis": patch.synthesis_summary,
            "proposed_change": operation,
            "skill_scope": "general",
            "known_risks": sorted(
                {
                    limitation
                    for artifact in mode_artifacts
                    for mode in artifact.modes
                    for limitation in mode.evidence_limitations
                }
            ),
            "candidate_skill": candidate.model_dump(mode="json") if candidate is not None else None,
        }
    )
    return TeacherProposal(
        group_id=diagnosis.group_id,
        request_sha256=request_sha256,
        response_sha256=response_sha256,
        teacher_model=teacher_model,
        parse_status="valid_candidate" if candidate is not None else "valid_noop",
        static_issues=[],
        deterministic_normalizations=["exact_playbook_patch_applied_by_system"],
        source_group_ids=sorted(used_groups),
        source_witness=None,
        group_evidence_witness=witness,
        diagnosis=diagnosis,
    )


def candidate_overlap_issues(
    candidate: SkillContract,
    *,
    historical_skills: list[SkillContract],
    runtime_skills: list[SkillContract],
) -> list[str]:
    """Reject copied advice without reviving the retired trigger engine."""

    delivered = [skill for skill in runtime_skills if skill.status == "active"]
    same_scope_delivered = [skill for skill in delivered if skill.domain == candidate.domain]
    return sorted(
        {
            *(
                f"structural_duplicate:{item}"
                for item in find_structural_duplicates(candidate, historical_skills)
            ),
            *(f"scope_redundancy:{item}" for item in find_scope_redundancies(candidate, delivered)),
            *(
                f"lexical_near_duplicate:{item}"
                for item in find_lexical_near_duplicates(candidate, same_scope_delivered)
            ),
        }
    )


class TeacherResponse(Protocol):
    value: dict[str, Any]
    model: str
    request_sha256: str
    response_sha256: str


class TeacherClient(Protocol):
    model: str

    def generate_json(
        self,
        *,
        purpose: str,
        system_prompt: str,
        user_prompt: str,
        output_schema: dict[str, Any],
    ) -> TeacherResponse: ...


def _compact_batch_teacher_state(state: ConsultationState) -> dict[str, Any]:
    """Expose only action-time visible state, without persona or answer text."""

    return {
        "turn": state.turn,
        "max_turns": state.max_turns,
        "domain": state.domain,
        "visible_fact_plan": [
            {
                "fact_id": fact.fact_id,
                "label": fact.label,
                "status": fact.status,
                "criticality": fact.criticality,
                "target_kind": fact.target_kind,
            }
            for fact in state.facts
        ],
        "asked_target_ids": list(state.asked_targets),
        "prior_interaction_outcomes": [
            {
                "turn": item.turn,
                "action_type": item.action_type,
                "target_id": item.target_id,
                "response_kind": item.response_kind,
                "new_information": item.new_information,
                "disclosed_fact_ids": list(item.disclosed_fact_ids),
            }
            for item in state.interactions
        ],
        "unresolved_conflict_fact_ids": [
            conflict.fact_id for conflict in state.unresolved_conflicts
        ],
        "risk_flags": list(state.risk_flags),
    }


def _allowed_applicability_cues(
    contrasts: list[tuple[AdvantageGroup, ContrastSelection, dict[str, ResearchTrajectory]]],
) -> list[str]:
    """Build the exact cue vocabulary supported before every source fork.

    These sentences are deliberately generated from structured state and typed
    provenance rather than inferred from client answer text.  An
    ``opening_repeat``/``repeated_hidden_fact`` transition may certify that an
    item was already visible before the action; an immediate ``unavailable`` can
    never do so.  A one-case domain hypothesis receives a domain-bounded visible
    dispute cue rather than an exact source target label: exact labels made a
    learned document effectively unusable on every later case.  Cross-case skills
    receive only predicates shared by every source state.
    """

    states: list[ConsultationState] = []
    negative_steps: list[Any] = []
    for _, selection, trajectories in contrasts:
        turn = selection.aligned_divergence_turn
        if turn is None:
            continue
        positive = trajectories[selection.highest_id]
        negative = trajectories[selection.lowest_id]
        positive_step = next((item for item in positive.steps if item.turn == turn), None)
        negative_step = next((item for item in negative.steps if item.turn == turn), None)
        if positive_step is None or negative_step is None:
            continue
        state = _execution_state(positive_step)
        states.append(state)
        negative_steps.append(negative_step)
    if not states:
        return []

    cues: list[str] = []
    if all(state.high_critical_unknown_count > 0 for state in states):
        cues.append("当前仍有尚未询问的高重要性事实目标。")
    if all(state.client_fact_unresolved_count > 0 for state in states):
        cues.append("当前仍有尚未询问、客户可能直接回答的事实目标。")
    if all(
        any(
            fact.target_kind == "evidence_or_third_party"
            and fact.status in {"unknown", "disputed"}
            and fact.fact_id not in state.asked_targets
            for fact in state.facts
        )
        for state in states
    ):
        cues.append("当前仍有尚未核实的外部证据或第三方信息目标。")
    if all(state.unavailable_turn_count > 0 for state in states):
        cues.append("此前已有目标被客户明确表示不知道或暂不可得。")
    low_yield_target_visible_before_action: list[bool] = []
    for state, step in zip(states, negative_steps, strict=True):
        target_id = str(_effective_action(step).target_id or "")
        target_fact = next(
            (fact for fact in state.facts if fact.fact_id == target_id),
            None,
        )
        prior_unavailable = any(
            item.target_id == target_id and item.response_kind == "unavailable"
            for item in state.interactions
        )
        already_visible = (
            target_fact is not None
            and target_fact.status
            in {"client_claimed", "corroborated", "disputed", "not_available"}
        ) or target_id in state.asked_targets
        # opening_repeat/repeated_hidden_fact is produced after the action, but
        # certifies that the requested information was already present in the
        # *pre-action* opening/dialogue.  Unlike an immediate ``unavailable``, it
        # does not reveal a new future client state.
        preexisting_visibility_confirmed = step.client_response_kind in {
            "opening_repeat",
            "repeated_hidden_fact",
        }
        low_yield_target_visible_before_action.append(
            prior_unavailable or already_visible or preexisting_visibility_confirmed
        )
    if all(low_yield_target_visible_before_action):
        cues.append(
            "当前正在考虑的下一询问目标中，至少有一项已由开场或可见对话回答，或此前已被客户明确表示不可得。"
        )
    if all(state.asked_targets for state in states):
        cues.append("咨询已经取得至少一次客户回答，正在比较下一项询问目标。")
    if all(state.unresolved_conflicts for state in states):
        cues.append("当前可见陈述中仍存在尚未澄清的事实冲突。")

    # A one-case domain source supports a domain-bounded method hypothesis, not
    # a source-label lookup table.  The public domain and unresolved client-fact
    # surface are both visible before action and remain meaningful on later cases.
    if len(states) == 1 and states[0].client_fact_unresolved_count > 0:
        cues.append(
            f"当前公开案件领域为“{states[0].domain}”，且仍有与可见争议直接相关的"
            "未询问客户事实目标。"
        )

    # Every source state has at least one visible plan target.  This last cue is
    # an honest, non-outcome fallback for unusual evidence-gap forks; it avoids
    # forcing the teacher to invent a condition merely to satisfy the schema.
    if not cues:
        cues.append("当前可见调查图谱中仍存在尚未处理的事实或证据目标。")
    return list(dict.fromkeys(cues))


def _required_applicability_cues(
    allowed_cues: list[str],
    *,
    evidence_cluster: dict[str, Any],
) -> list[str]:
    """Require the visible causal discriminator, not merely generic unknowns."""

    required: list[str] = []
    domain_prefix = "当前公开案件领域为“"
    if (
        str(evidence_cluster.get("evidence_scope") or "") != "general"
        and int(evidence_cluster.get("source_case_count") or 0) == 1
    ):
        required.extend(cue for cue in allowed_cues if cue.startswith(domain_prefix))
    if str(evidence_cluster.get("negative_transition_outcome") or "") in {
        "opening_repeat",
        "repeated_hidden_fact",
    }:
        required.extend(
            cue for cue in allowed_cues if cue.startswith("当前正在考虑的下一询问目标中")
        )
    if bool((evidence_cluster.get("observed_context_summary") or {}).get("prior_unavailable")):
        required.extend(cue for cue in allowed_cues if cue.startswith("此前已有目标被客户明确表示"))
    return list(dict.fromkeys(required))


def _schema_invalid_proposal(
    *,
    group_id: str,
    response: TeacherResponse,
    error: ValidationError,
    normalization_changes: list[str] | None = None,
) -> TeacherProposal:
    """Quarantine malformed teacher output without inventing a candidate."""

    del normalization_changes  # accepted only for explicit legacy caller diagnostics
    first = error.errors(include_url=False, include_input=False)[0]
    location = ".".join(str(item) for item in first.get("loc", ())) or "root"
    issue = f"teacher_output_schema_invalid:{location}:{first.get('type', 'validation_error')}"
    diagnosis = SkillDiagnosis.model_validate(
        {
            "group_id": group_id,
            "failure_state": {"turn": None, "relevant_fields": []},
            "behavior_difference": {
                "positive_action": "教师输出未通过结构校验",
                "negative_action": "教师输出未通过结构校验",
            },
            "causal_hypothesis": "教师输出未通过结构校验，未形成候选文档",
            "proposed_change": "NOOP",
            "skill_scope": "general",
            "known_risks": [issue],
            "candidate_skill": None,
        }
    )
    return TeacherProposal(
        group_id=group_id,
        request_sha256=response.request_sha256,
        response_sha256=response.response_sha256,
        teacher_model=response.model,
        parse_status="invalid_candidate",
        static_issues=[issue],
        source_group_ids=[],
        source_witness=None,
        diagnosis=diagnosis,
    )


def _materialize_teacher_diagnosis(draft: TeacherDiagnosisDraft) -> SkillDiagnosis:
    """Attach empty system-owned metadata to a teacher-authored document draft."""

    candidate = (
        SkillContract.model_validate(
            {
                **draft.candidate_skill.model_dump(mode="json"),
                "provenance": {"source": "tf_grpo"},
            }
        )
        if draft.candidate_skill is not None
        else None
    )
    return SkillDiagnosis(
        group_id=draft.group_id,
        failure_state=draft.failure_state,
        behavior_difference=draft.behavior_difference,
        causal_hypothesis=draft.causal_hypothesis,
        proposed_change=draft.proposed_change,
        skill_scope=draft.skill_scope,
        known_risks=draft.known_risks,
        candidate_skill=candidate,
    )


def _effective_action(step: Any) -> Any:
    final = getattr(getattr(step, "action_decision", None), "final", None)
    return final if final is not None else step.proposed_action


def _execution_state(step: Any) -> ConsultationState:
    return reconstruct_execution_state(
        step.state_before,
        getattr(step, "state_patch", StatePatch()),
        turn=step.turn,
        candidate_action=step.proposed_action.model_dump(mode="json"),
    )


def semantic_action_target(
    step: Any,
    *,
    execution_state: ConsultationState | None = None,
) -> str:
    """Return the transport-id-independent target visible to learned skills.

    State ``fact_id`` values are transport identifiers.  The target label is
    the stable, skill-visible meaning of an action. Raw identifiers remain the
    final fail-closed fallback so genuinely distinct unlabelled targets are not
    collapsed. Terminal actions have one fixed target and never inherit the
    model-authored ``expected_information`` text.
    """

    action = _effective_action(step)
    if action.action_type in {"final", "abstain"}:
        return "__terminal__"
    target_id = str(getattr(action, "target_id", "") or "")
    target_label = ""
    if execution_state is not None:
        target_label = next(
            (str(fact.label) for fact in execution_state.facts if str(fact.fact_id) == target_id),
            "",
        )
    else:
        state_before = getattr(step, "state_before", {})
        if isinstance(state_before, dict):
            for fact in state_before.get("facts") or []:
                if isinstance(fact, dict) and str(fact.get("fact_id") or "") == target_id:
                    target_label = str(fact.get("label") or "")
                    break
    return normalize_question(target_label) or target_id


def system_action_target_kind(
    step: Any,
    *,
    execution_state: ConsultationState | None = None,
) -> str:
    """Resolve target kind from system-owned visible state, never model self-report.

    ``action.target_type`` is generated text and is not causal: the same visible
    target has occasionally been labelled both ``fact`` and ``evidence`` while
    producing the same rendered question.  Formal trajectories always carry the
    system-owned ``target_kind``.  ``unknown`` is a fail-closed compatibility
    value for deliberately partial test or historical records.
    """

    action = _effective_action(step)
    if action.action_type in {"final", "abstain"}:
        return "none"
    target_id = str(getattr(action, "target_id", "") or "")
    if execution_state is not None:
        return str(
            next(
                (
                    fact.target_kind
                    for fact in execution_state.facts
                    if str(fact.fact_id) == target_id
                ),
                "unknown",
            )
        )
    state_before = getattr(step, "state_before", {})
    if isinstance(state_before, dict):
        for fact in state_before.get("facts") or []:
            if isinstance(fact, dict) and str(fact.get("fact_id") or "") == target_id:
                return str(fact.get("target_kind") or "unknown")
    return "unknown"


def structural_action_signature(
    step: Any,
    *,
    execution_state: ConsultationState | None = None,
) -> tuple[object, ...]:
    """Project an action onto a durable, structural skill-learning decision.

    Surface question wording is excluded so simulator sensitivity to a paraphrase
    cannot become durable policy memory. This projection uses the system-owned
    target kind rather than the model-authored ``target_type`` so an alias cannot
    be laundered into a persistent skill fork.
    """

    action = _effective_action(step)
    return (
        action.action_type,
        system_action_target_kind(step, execution_state=execution_state),
        semantic_action_target(step, execution_state=execution_state),
    )


_CAUSAL_STATE_EXCLUSIONS = {
    "session_id",
    "persona",
    "candidate_action",
    "active_skills",
    "candidate_target_repeated",
    "candidate_target_unavailable",
    "candidate_target_low_value",
    "candidate_target_already_known",
    "candidate_target_is_client_fact",
    "candidate_target_is_evidence_gap",
    "candidate_target_criticality",
}


def _causal_state_payload(step: Any) -> dict[str, Any]:
    payload = {
        key: value
        for key, value in _execution_state(step).model_dump(mode="json").items()
        if key not in _CAUSAL_STATE_EXCLUSIONS
    }
    interactions = payload.get("interactions")
    if isinstance(interactions, list):
        payload["interactions"] = [
            {key: value for key, value in item.items() if key != "question"}
            if isinstance(item, dict)
            else item
            for item in interactions
        ]
    return payload


def causal_visible_state_sha256(step: Any) -> str:
    """Hash the complete pre-action policy input for a causal source fork.

    The structured state alone is insufficient after turn one: two trajectories
    can reach equivalent counters while retaining different natural-language
    dialogue histories, and the lawyer sees those histories verbatim.  Production
    ``ResearchStep`` records therefore bind both the normalized execution state
    and the exact visible message list.  Lightweight unit fixtures written before
    ``visible_input`` existed retain a state-only compatibility path.
    """

    visible_input = getattr(step, "visible_input", None)
    if visible_input is None:
        return canonical_json_sha256(_causal_state_payload(step))
    messages = [
        item.model_dump(mode="json") if hasattr(item, "model_dump") else item
        for item in visible_input
    ]
    return canonical_json_sha256(
        {
            "execution_state": _causal_state_payload(step),
            "policy_visible_input": messages,
        }
    )


def _action_payload(step: Any) -> dict[str, object]:
    action = _effective_action(step)
    return {
        "action_type": action.action_type,
        "target_type": action.target_type,
        "target_id": action.target_id,
        "content": action.content,
        "expected_information": action.expected_information,
        "constraints": list(action.constraints),
    }


def _learnable_action_signature(step: Any) -> tuple[object, ...]:
    return structural_action_signature(step, execution_state=_execution_state(step))


def _target_kind(state: ConsultationState, target_id: str | None) -> str | None:
    return next(
        (fact.target_kind for fact in state.facts if fact.fact_id == target_id),
        None,
    )


def _behavior_family(positive_step: Any, negative_step: Any) -> str:
    positive = _effective_action(positive_step)
    negative = _effective_action(negative_step)
    terminal = {"final", "abstain"}
    inquiry = {"ask", "clarify", "verify", "retrieve", "summarize"}
    if negative.action_type in terminal and positive.action_type in inquiry:
        return "continue_inquiry"
    if positive.action_type in terminal and negative.action_type in inquiry:
        return "safe_stop"
    positive_state = _execution_state(positive_step)
    negative_state = _execution_state(negative_step)
    positive_structure = structural_action_signature(positive_step, execution_state=positive_state)
    negative_structure = structural_action_signature(negative_step, execution_state=negative_state)
    if positive_structure[1:] != negative_structure[1:]:
        return "target_selection"
    if positive.action_type != negative.action_type:
        return "action_choice"
    return "other_policy_difference"


def _source_fork(
    group: AdvantageGroup,
    selection: ContrastSelection,
    trajectories: dict[str, ResearchTrajectory],
) -> tuple[SourceForkWitness | None, list[str]]:
    """Validate one system-selected trajectory contrast independently of skill prose."""

    turn = selection.aligned_divergence_turn
    if turn is None:
        return None, ["source_grounding_missing_aligned_divergence_turn"]
    positive = trajectories.get(selection.highest_id)
    negative = trajectories.get(selection.lowest_id)
    if positive is None:
        return None, ["source_grounding_missing_highest_trajectory"]
    if negative is None:
        return None, ["source_grounding_missing_lowest_trajectory"]
    positive_step = next((item for item in positive.steps if item.turn == turn), None)
    negative_step = next((item for item in negative.steps if item.turn == turn), None)
    if positive_step is None:
        return None, ["source_grounding_divergence_turn_absent_from_highest_trajectory"]
    if negative_step is None:
        return None, ["source_grounding_divergence_turn_absent_from_lowest_trajectory"]
    try:
        positive_state_hash = causal_visible_state_sha256(positive_step)
        negative_state_hash = causal_visible_state_sha256(negative_step)
    except (AttributeError, ValueError):
        return None, ["source_grounding_invalid_visible_state"]
    if positive_state_hash != negative_state_hash:
        return None, ["source_grounding_visible_state_mismatch_at_divergence"]
    if _learnable_action_signature(positive_step) == _learnable_action_signature(negative_step):
        return None, ["source_grounding_no_structural_action_difference"]
    if selection.reward_gap is None or selection.reward_gap <= 0:
        return None, ["source_grounding_nonpositive_reward_gap"]
    issues: list[str] = []
    if selection.signal_family == "fact_elicitation":
        fact_efficiency = (
            selection.selection_basis == "trajectory_level_fact_efficiency"
            and (selection.fact_gain or 0) == 0
            and sum(bool(step.rendered_question) for step in positive.steps)
            < sum(bool(step.rendered_question) for step in negative.steps)
        )
        if (selection.fact_gain or 0) <= 0 and not fact_efficiency:
            issues.append("source_grounding_missing_trajectory_fact_gain")
    elif selection.signal_family == "evidence_gap_identification":
        if (selection.gap_gain or 0) <= 0:
            issues.append("source_grounding_missing_trajectory_evidence_gap_gain")
    elif (
        selection.signal_family == "safe_stop"
        and selection.selection_basis != "trajectory_level_information_preserving_efficiency"
    ):
        issues.append("source_grounding_missing_information_preserving_efficiency")
    if issues:
        return None, sorted(set(issues))
    return (
        SourceForkWitness(
            group_id=group.group_id,
            case_id=positive.case_id,
            domain=positive.domain,
            divergence_turn=turn,
            visible_state_sha256=positive_state_hash,
            positive_trajectory_id=positive.trajectory_id,
            negative_trajectory_id=negative.trajectory_id,
            positive_action=_action_payload(positive_step),
            negative_action=_action_payload(negative_step),
            reward_gap=float(selection.reward_gap),
        ),
        [],
    )


def teacher_evidence_cluster_summaries(
    contrasts: list[tuple[AdvantageGroup, ContrastSelection, dict[str, ResearchTrajectory]]],
) -> list[dict[str, Any]]:
    """Group trajectory-level high/low contrasts into behavioral hypotheses.

    A domain-bounded document may be nominated from one exact, replayable
    same-input contrast; a general document requires at least two independent
    cases across two domains.  Nomination establishes source provenance, not
    efficacy, which remains a separately reported whole-library diagnostic.
    """

    clustered: dict[tuple[str, str, str, str, str, str, str, str], list[dict[str, Any]]] = (
        defaultdict(list)
    )
    for group, selection, trajectories in contrasts:
        witness, issues = _source_fork(group, selection, trajectories)
        if witness is None or issues:
            continue
        positive = trajectories[selection.highest_id]
        negative = trajectories[selection.lowest_id]
        positive_step = next(
            item for item in positive.steps if item.turn == witness.divergence_turn
        )
        negative_step = next(
            item for item in negative.steps if item.turn == witness.divergence_turn
        )
        positive_action = _effective_action(positive_step)
        negative_action = _effective_action(negative_step)
        state = _execution_state(negative_step)
        family = _behavior_family(positive_step, negative_step)
        positive_kind = system_action_target_kind(
            positive_step, execution_state=_execution_state(positive_step)
        )
        negative_kind = system_action_target_kind(negative_step, execution_state=state)
        positive_outcome = str(positive_step.client_response_kind or "terminal_or_no_response")
        negative_outcome = str(negative_step.client_response_kind or "terminal_or_no_response")
        clustered[
            (
                selection.signal_family,
                negative_action.action_type,
                positive_action.action_type,
                family,
                negative_kind,
                positive_kind,
                negative_outcome,
                positive_outcome,
            )
        ].append(
            {
                "group_id": group.group_id,
                "case_id": positive.case_id,
                "domain": positive.domain,
                "persona": positive.persona,
                "reward_gap": float(selection.reward_gap or 0.0),
                # The same exact causal fork can support more than one measured
                # outcome (for example, both a fact and an evidence-gap gain).
                # It is still one source event and must not consume two teacher
                # calls or materialize two near-identical skill documents.
                "source_causal_fork_sha256": canonical_json_sha256(
                    {
                        "case_id": witness.case_id,
                        "domain": witness.domain,
                        "divergence_turn": witness.divergence_turn,
                        "visible_state_sha256": witness.visible_state_sha256,
                        "positive_trajectory_id": witness.positive_trajectory_id,
                        "negative_trajectory_id": witness.negative_trajectory_id,
                        "positive_action": witness.positive_action,
                        "negative_action": witness.negative_action,
                    }
                ),
                "immediate_fact_gain": int(selection.immediate_fact_gain or 0),
                "fact_gain": int(selection.fact_gain or 0),
                "immediate_gap_gain": int(selection.immediate_gap_gain or 0),
                "gap_gain": int(selection.gap_gain or 0),
                "positive_target_kind": positive_kind,
                "negative_target_kind": negative_kind,
                "positive_transition_outcome": positive_outcome,
                "negative_transition_outcome": negative_outcome,
                "positive_target_label": next(
                    (
                        fact.label
                        for fact in state.facts
                        if fact.fact_id == positive_action.target_id
                    ),
                    None,
                ),
                "negative_target_label": next(
                    (
                        fact.label
                        for fact in state.facts
                        if fact.fact_id == negative_action.target_id
                    ),
                    None,
                ),
                "high_critical_unknown": state.high_critical_unknown_count > 0,
                "prior_unavailable": state.unavailable_turn_count > 0,
            }
        )

    summaries: list[dict[str, Any]] = []

    def summarize(
        key: tuple[str, str, str, str, str, str, str, str],
        members: list[dict[str, Any]],
        scope: str,
    ) -> dict[str, Any]:
        (
            signal,
            negative_type,
            positive_type,
            family,
            negative_kind,
            positive_kind,
            negative_outcome,
            positive_outcome,
        ) = key
        cases = sorted({str(item["case_id"]) for item in members})
        domains = sorted({str(item["domain"]) for item in members})
        # Scope controls the breadth of the claim made at nomination time.
        # A domain-bounded document may be proposed from one exact, replayable
        # same-input contrast; that is source evidence, not an efficacy claim.
        # A general document claims cross-domain applicability and therefore
        # still requires independent support from at least two legal domains.
        source_scope_eligible = (
            len(domains) >= 2 and len(cases) >= 2 if scope == "general" else len(cases) >= 1
        )
        # The fixed skill bundle is visible to both stages of the frozen policy:
        # the binary continue/stop choice and, on a continue branch, the closed-
        # catalog target choice.  Consequently exact-state target-selection,
        # continue-inquiry and information-preserving safe-stop forks are all
        # executable.  Surface-only question wording remains inexpressible.
        teacher_expressible = bool(
            (
                family == "target_selection"
                and negative_type in {"ask", "clarify", "verify", "retrieve", "summarize"}
                and positive_type in {"ask", "clarify", "verify", "retrieve", "summarize"}
            )
            or family in {"continue_inquiry", "safe_stop"}
        )
        eligible = source_scope_eligible and teacher_expressible
        base_id = (
            f"{signal}__{negative_type}_to_{positive_type}__{family}"
            f"__{negative_kind}_to_{positive_kind}"
            f"__{negative_outcome}_to_{positive_outcome}"
        )
        cluster_id = base_id if scope == "general" else f"{base_id}__scope_{scope}"
        critical_values = sorted({bool(item["high_critical_unknown"]) for item in members})
        unavailable_values = sorted({bool(item["prior_unavailable"]) for item in members})
        return {
            "cluster_id": cluster_id,
            "evidence_scope": scope,
            "signal_family": signal,
            "negative_action_type": negative_type,
            "positive_action_type": positive_type,
            "behavior_family": family,
            "negative_target_kind": negative_kind,
            "positive_target_kind": positive_kind,
            "negative_transition_outcome": negative_outcome,
            "positive_transition_outcome": positive_outcome,
            "teacher_expressible": teacher_expressible,
            "ineligible_reason": (
                None
                if eligible
                else "runtime_scope_requires_same_state_decision_fork"
                if not teacher_expressible
                else "general_scope_requires_two_source_domains"
                if scope == "general"
                else "domain_scope_requires_one_exact_source_case"
            ),
            "observed_context_summary": {
                "high_critical_unknown": (
                    critical_values[0] if len(critical_values) == 1 else None
                ),
                "prior_unavailable": (
                    unavailable_values[0] if len(unavailable_values) == 1 else None
                ),
                "observed_positive_target_kinds": sorted(
                    {
                        str(item["positive_target_kind"])
                        for item in members
                        if item["positive_target_kind"] is not None
                    }
                ),
                "observed_negative_target_kinds": sorted(
                    {
                        str(item["negative_target_kind"])
                        for item in members
                        if item["negative_target_kind"] is not None
                    }
                ),
                "positive_target_labels": sorted(
                    {
                        str(item["positive_target_label"])
                        for item in members
                        if item["positive_target_label"]
                    }
                )[:12],
                "negative_target_labels": sorted(
                    {
                        str(item["negative_target_label"])
                        for item in members
                        if item["negative_target_label"]
                    }
                )[:12],
            },
            "group_ids": sorted(str(item["group_id"]) for item in members),
            "source_causal_fork_sha256s": sorted(
                {str(item["source_causal_fork_sha256"]) for item in members}
            ),
            "source_case_ids": cases,
            "source_domains": domains,
            "source_personas": sorted({str(item["persona"]) for item in members}),
            "group_count": len(members),
            "source_case_count": len(cases),
            "source_domain_count": len(domains),
            "total_immediate_fact_gain": sum(int(item["immediate_fact_gain"]) for item in members),
            "total_fact_gain": sum(int(item["fact_gain"]) for item in members),
            "total_immediate_gap_gain": sum(int(item["immediate_gap_gain"]) for item in members),
            "total_gap_gain": sum(int(item["gap_gain"]) for item in members),
            "total_reward_gap": round(sum(float(item["reward_gap"]) for item in members), 6),
            "positive_end_to_end_reward_gap_groups": sum(
                float(item["reward_gap"]) > 0 for item in members
            ),
            "eligible": eligible,
            "eligible_skill_scopes": [scope] if eligible else [],
        }

    for key, members in clustered.items():
        summaries.append(summarize(key, members, "general"))
        by_domain: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for member in members:
            by_domain[str(member["domain"])].append(member)
        for domain, domain_members in sorted(by_domain.items()):
            summaries.append(summarize(key, domain_members, domain))
    return sorted(
        summaries,
        key=lambda item: (
            not bool(item["eligible"]),
            -int(item["source_case_count"]),
            -int(item["source_domain_count"]),
            -int(item["group_count"]),
            -float(item["total_reward_gap"]),
            str(item["cluster_id"]),
        ),
    )


def teacher_evidence_milestone(cluster: dict[str, Any]) -> dict[str, int]:
    """Return a bounded, outcome-blind support tier for one evidence cluster.

    A NOOP at the first two supported cases is not proof that the mechanism can
    never become learnable.  Conversely, calling the teacher after every added
    trajectory spent most of the audited run on effectively unchanged evidence.
    Powers-of-two tiers provide deterministic exponential backoff: a cluster may
    be reconsidered only after its independent case or domain support reaches a
    materially larger scale (2, 4, 8, ...), while a completed CREATE is terminal.
    """

    def tier(field: str) -> int:
        value = cluster.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f"teacher evidence cluster has invalid {field}")
        return 1 << (value.bit_length() - 1)

    return {
        "source_case_power_of_two_floor": tier("source_case_count"),
        "source_domain_power_of_two_floor": tier("source_domain_count"),
    }


def teacher_evidence_fingerprint(cluster: dict[str, Any]) -> str:
    """Bind a cluster identity to its current geometric support milestone."""

    cluster_id = str(cluster.get("cluster_id") or "")
    if not cluster_id:
        raise ValueError("teacher evidence cluster has no cluster_id")
    return canonical_json_sha256(
        {
            "cluster_id": cluster_id,
            "support_milestone": teacher_evidence_milestone(cluster),
        }
    )


def select_teacher_evidence_clusters(
    clusters: list[dict[str, Any]],
    *,
    attempted_fingerprints: set[str],
    completed_cluster_ids: set[str],
    budget: int,
    attempted_cluster_ids: set[str] | None = None,
    signal_priority: list[str] | None = None,
    completed_source_causal_fork_sha256s: set[str] | None = None,
) -> list[tuple[dict[str, Any], str]]:
    """Prefer novel durable evidence with bounded NOOP reconsideration."""

    if budget < 0:
        raise ValueError("teacher cluster budget must be non-negative")
    if budget == 0:
        return []
    completed_source_forks = completed_source_causal_fork_sha256s or set()
    selectable: list[tuple[dict[str, Any], str]] = []
    for cluster in clusters:
        if not bool(cluster.get("eligible")):
            continue
        # A successfully materialized CREATE completes this mechanism/scope.
        # NOOP and invalid attempts may be reconsidered, but only after their
        # outcome-blind support milestone grows geometrically.
        if str(cluster.get("cluster_id")) in completed_cluster_ids:
            continue
        source_forks = {
            str(item) for item in cluster.get("source_causal_fork_sha256s", []) if str(item)
        }
        # A second outcome label over exactly the source fork(s) that already
        # produced an admitted document is not independent learning evidence.
        if source_forks and source_forks <= completed_source_forks:
            continue
        fingerprint = teacher_evidence_fingerprint(cluster)
        if fingerprint not in attempted_fingerprints:
            selectable.append((cluster, fingerprint))

    signal_rank = {signal: index for index, signal in enumerate(signal_priority or [])}
    prior_cluster_ids = attempted_cluster_ids or set()

    def rank_key(item: tuple[dict[str, Any], str]) -> tuple[object, ...]:
        cluster = item[0]
        return (
            str(cluster.get("cluster_id")) in prior_cluster_ids,
            signal_rank.get(str(cluster.get("signal_family")), len(signal_rank)),
            -int(cluster.get("total_fact_gain", 0)) - int(cluster.get("total_gap_gain", 0)),
            -int(cluster.get("total_immediate_fact_gain", 0))
            - int(cluster.get("total_immediate_gap_gain", 0)),
            -int(cluster.get("source_case_count", 0)),
            -int(cluster.get("source_domain_count", 0)),
            -int(cluster.get("group_count", 0)),
            -float(cluster.get("total_reward_gap", 0.0)),
            str(cluster["cluster_id"]),
        )

    selectable.sort(key=rank_key)

    # The same evidence can be present more than once after merging summaries.
    # Keep its strongest-ranked representation, but never spend two teacher slots
    # on one source fingerprint.
    deduplicated: list[tuple[dict[str, Any], str]] = []
    known_fingerprints: set[str] = set()
    known_causal_sources: set[tuple[str, tuple[str, ...]]] = set()
    for item in selectable:
        if item[1] in known_fingerprints:
            continue
        cluster = item[0]
        causal_source = (
            str(cluster.get("evidence_scope") or ""),
            tuple(sorted(str(value) for value in cluster.get("source_causal_fork_sha256s", []))),
        )
        if causal_source[1] and causal_source in known_causal_sources:
            continue
        known_fingerprints.add(item[1])
        if causal_source[1]:
            known_causal_sources.add(causal_source)
        deduplicated.append(item)
    selectable = deduplicated

    def behavior_key(cluster: dict[str, Any]) -> tuple[object, ...]:
        explicit = (
            cluster.get("signal_family"),
            cluster.get("negative_action_type"),
            cluster.get("positive_action_type"),
            cluster.get("behavior_family", cluster.get("operation_family")),
            cluster.get("negative_target_kind"),
            cluster.get("positive_target_kind"),
            cluster.get("negative_transition_outcome"),
            cluster.get("positive_transition_outcome"),
        )
        if any(item is not None for item in explicit):
            return explicit
        return (str(cluster.get("cluster_id", "")).split("__scope_", 1)[0],)

    def evidence_scope(cluster: dict[str, Any]) -> str | None:
        scope = cluster.get("evidence_scope")
        if isinstance(scope, str) and scope:
            return scope
        eligible_scopes = cluster.get("eligible_skill_scopes")
        if (
            isinstance(eligible_scopes, list)
            and len(eligible_scopes) == 1
            and isinstance(eligible_scopes[0], str)
            and eligible_scopes[0]
        ):
            return eligible_scopes[0]
        cluster_id = str(cluster.get("cluster_id", ""))
        if "__scope_" in cluster_id:
            return cluster_id.split("__scope_", 1)[1]
        return None

    def domain_keys(cluster: dict[str, Any]) -> set[str]:
        scope = evidence_scope(cluster)
        if scope is not None:
            # General evidence is deliberately not treated as covering every
            # source domain: a domain-bounded document should remain novel.
            return set() if scope == "general" else {scope}
        domains = cluster.get("source_domains", [])
        if not isinstance(domains, list):
            return set()
        return {str(domain) for domain in domains if str(domain)}

    selected: list[tuple[dict[str, Any], str]] = []
    seen_behaviors: set[tuple[object, ...]] = set()
    seen_domains: set[str] = set()
    seen_fingerprints: set[str] = set()

    def add(item: tuple[dict[str, Any], str]) -> None:
        selected.append(item)
        seen_behaviors.add(behavior_key(item[0]))
        seen_domains.update(domain_keys(item[0]))
        seen_fingerprints.add(item[1])

    def most_diverse(
        candidates: list[tuple[dict[str, Any], str]],
    ) -> tuple[dict[str, Any], str]:
        positions = {item[1]: index for index, item in enumerate(selectable)}
        return max(
            candidates,
            key=lambda item: (
                behavior_key(item[0]) not in seen_behaviors,
                len(domain_keys(item[0]) - seen_domains),
                -positions[item[1]],
            ),
        )

    general = [item for item in selectable if evidence_scope(item[0]) == "general"]
    domain_specific = [
        item for item in selectable if evidence_scope(item[0]) not in {None, "general"}
    ]

    # Reserve scope coverage before filling the remaining attempt budget.  This
    # is independent of the smaller admitted-document cap.
    if budget >= 2 and general and domain_specific:
        scoped = general + domain_specific
        first = min(scoped, key=rank_key)
        add(first)
        opposite = domain_specific if evidence_scope(first[0]) == "general" else general
        add(most_diverse(opposite))
    elif selectable:
        add(selectable[0])

    while len(selected) < budget:
        remaining = [item for item in selectable if item[1] not in seen_fingerprints]
        if not remaining:
            break
        add(most_diverse(remaining))
    return selected


def candidate_context_scope_issues(
    candidate: SkillContract,
    evidence_cluster: dict[str, Any],
    *,
    allowed_applicability_cues: set[str] | None = None,
    required_applicability_cues: set[str] | None = None,
) -> list[str]:
    """Bind declared scope/objective and action-time cues to source evidence.

    Applicability text is part of the treatment delivered to the frozen lawyer.
    It therefore cannot be free-form teacher prose inferred from an outcome that
    occurred *after* the source action.  The executor supplies a small catalog of
    deterministic, action-time-visible cue sentences and the teacher may only
    select exact members of that catalog.  Procedure and question wording remain
    natural-language teacher work; the treatment boundary is the observable
    condition under which that work may be used.
    """

    issues: list[str] = []
    eligible_scopes = [str(item) for item in evidence_cluster.get("eligible_skill_scopes", [])]
    if not bool(evidence_cluster.get("eligible", bool(eligible_scopes))):
        issues.append("candidate_uses_ineligible_evidence_cluster")
    if eligible_scopes and candidate.domain not in eligible_scopes:
        issues.append(f"candidate_domain_not_allowed_by_evidence:{candidate.domain}")
    signal = evidence_cluster.get("signal_family")
    if signal is not None and candidate.objective != signal:
        issues.append(f"candidate_objective_mismatch:{candidate.objective}!={signal}")
    provenance = candidate.provenance
    cluster_id = str(evidence_cluster.get("cluster_id") or "")
    if (
        provenance.source_evidence_cluster_id is not None
        and provenance.source_evidence_cluster_id != cluster_id
    ):
        issues.append("teacher_claimed_different_source_cluster")
    if provenance.source_signal_family is not None and provenance.source_signal_family != signal:
        issues.append("teacher_claimed_different_signal_family")
    if allowed_applicability_cues is not None:
        unsupported = sorted(set(candidate.applicability_cues) - allowed_applicability_cues)
        if unsupported:
            issues.extend(
                f"applicability_cue_not_visible_before_source_action:{item}" for item in unsupported
            )
    if required_applicability_cues is not None:
        missing = sorted(required_applicability_cues - set(candidate.applicability_cues))
        issues.extend(f"candidate_missing_required_causal_cue:{item}" for item in missing)
    return sorted(set(issues))


def candidate_source_grounding_issues(
    diagnosis: SkillDiagnosis,
    selection: ContrastSelection,
    trajectories: dict[str, ResearchTrajectory],
    *,
    existing_skills: list[SkillContract] | None = None,
) -> list[str]:
    """Verify the system-selected source contrast without claiming causality.

    ``failure_state.turn`` is teacher-authored diagnostic prose.  It is not a
    trustworthy artifact binding and therefore cannot decide admission.  The
    immutable ``ContrastSelection`` owns the divergence turn for both single-
    and multi-source candidates.
    """

    del existing_skills
    candidate = diagnosis.candidate_skill
    if candidate is None:
        return []
    if selection.aligned_divergence_turn is None:
        return ["source_grounding_missing_aligned_divergence_turn"]
    synthetic_group = AdvantageGroup(
        group_id=diagnosis.group_id,
        members=[],
        mean_reward=0.0,
        std_reward=0.0,
        informative=True,
    )
    witness, issues = _source_fork(synthetic_group, selection, trajectories)
    if witness is None:
        return issues
    if candidate.domain not in {"general", witness.domain}:
        issues.append("source_failure_domain_does_not_retrieve_skill")
    if candidate.objective != selection.signal_family:
        issues.append("source_failure_objective_mismatch")
    return sorted(set(issues))


def candidate_batch_source_grounding_issues(
    diagnosis: SkillDiagnosis,
    contrasts: list[tuple[AdvantageGroup, ContrastSelection, dict[str, ResearchTrajectory]]],
    *,
    existing_skills: list[SkillContract] | None = None,
) -> tuple[list[str], list[str]]:
    """Bind the candidate's claimed scope to system-verifiable source forks.

    One exact replayable fork can ground a domain-bounded nomination.  A
    ``general`` document makes a broader applicability claim and therefore
    requires at least two independent cases across at least two domains.  This
    is a source-provenance gate, not an efficacy test.
    """

    del existing_skills
    if diagnosis.candidate_skill is None:
        return [], []
    supported: list[str] = []
    failures: list[str] = []
    for group, selection, trajectories in contrasts:
        issues = candidate_source_grounding_issues(
            diagnosis,
            selection,
            trajectories,
        )
        if issues:
            failures.append(f"{group.group_id}:{'|'.join(issues)}")
        else:
            supported.append(group.group_id)
    supported_case_ids = {
        str(trajectories[selection.highest_id].case_id)
        for group, selection, trajectories in contrasts
        if group.group_id in supported
    }
    supported_domains = {
        str(trajectories[selection.highest_id].domain)
        for group, selection, trajectories in contrasts
        if group.group_id in supported
    }
    candidate = diagnosis.candidate_skill
    assert candidate is not None
    if candidate.domain != "general" and len(supported_case_ids) >= 1:
        return [], supported
    if (
        candidate.domain == "general"
        and len(supported_case_ids) >= 2
        and len(supported_domains) >= 2
    ):
        return [], supported
    issues = (
        [
            issue
            for actual, minimum, issue in (
                (
                    len(supported_case_ids),
                    2,
                    f"general_source_support_cases:{len(supported_case_ids)}<2",
                ),
                (
                    len(supported_domains),
                    2,
                    f"general_source_support_domains:{len(supported_domains)}<2",
                ),
            )
            if actual < minimum
        ]
        if candidate.domain == "general"
        else [f"domain_source_support_cases:{len(supported_case_ids)}<1"]
    )
    issues.extend(f"batch_source_witness_failure:{item}" for item in failures[:3])
    return sorted(set(issues)), supported


def _build_source_witness(
    *,
    evidence_cluster_id: str,
    signal_family: SignalFamily,
    contrasts: list[tuple[AdvantageGroup, ContrastSelection, dict[str, ResearchTrajectory]]],
    supported_group_ids: list[str],
) -> SourceWitness | None:
    supported = set(supported_group_ids)
    forks: list[SourceForkWitness] = []
    for group, selection, trajectories in contrasts:
        if group.group_id not in supported:
            continue
        witness, issues = _source_fork(group, selection, trajectories)
        if witness is not None and not issues:
            forks.append(witness)
    if not forks:
        return None
    return SourceWitness(
        evidence_cluster_id=evidence_cluster_id,
        signal_family=signal_family,
        forks=forks,
    )


class SkillTeacher:
    def __init__(
        self,
        client: TeacherClient,
        prompt_path: Path,
        *,
        baseline_policy_paths: list[Path],
    ) -> None:
        self.client = client
        if not baseline_policy_paths:
            raise ValueError("skill teacher requires the frozen baseline policy contract")
        baseline_sections: list[str] = []
        for path in baseline_policy_paths:
            content = path.read_text(encoding="utf-8").strip()
            # Show the teacher the actual empty-library baseline, not an unresolved
            # template token that could be mistaken for missing policy context.
            content = content.replace("{method_guidance}", EMPTY_SKILL_MEMORY)
            baseline_sections.append(f"--- {path.name} ---\n{content}")
        self.baseline_policy_contract = "\n\n".join(baseline_sections)
        self.prompt = (
            prompt_path.read_text(encoding="utf-8")
            .strip()
            .replace(
                "{playbook_interface_catalog}",
                json.dumps(playbook_interface_catalog(), ensure_ascii=False, sort_keys=True),
            )
            .replace("{baseline_policy_contract}", self.baseline_policy_contract)
        )
        mode_prompt_path = prompt_path.with_name("skill_mode_extractor_zh.txt")
        self.mode_prompt = (
            mode_prompt_path.read_text(encoding="utf-8")
            .strip()
            .replace("{baseline_policy_contract}", self.baseline_policy_contract)
        )

    @staticmethod
    def _teacher_trajectory(
        trajectory: ResearchTrajectory,
        focus_turn: int,
        *,
        include_state: bool,
    ) -> dict[str, Any]:
        focus_step = next(item for item in trajectory.steps if item.turn == focus_turn)
        payload: dict[str, Any] = {
            "trajectory_id": trajectory.trajectory_id,
            "case_id": trajectory.case_id,
            "domain": trajectory.domain,
            "status": trajectory.status,
            "focus_turn": focus_turn,
            "opening_inquiry_agenda": [
                {
                    "target_id": item.fact_id,
                    "label": item.label,
                    "criticality": item.criticality,
                    "target_kind": item.target_kind,
                }
                for item in trajectory.opening_inquiry_agenda.observations
            ],
            # Applicability is decided at the fork.  Only the visible dialogue
            # prefix is placed next to the action-time state.  Later turns are
            # intentionally absent: aggregate downstream outcomes are supplied
            # separately and may motivate a hypothesis, but cannot become a
            # purported pre-action cue.
            "visible_dialogue_prefix_before_action": [
                {
                    "turn": step.turn,
                    "rendered_question": step.rendered_question,
                    "client_response": step.client_response,
                    "client_response_kind": step.client_response_kind,
                    "client_selected_fact_ids": list(step.client_selected_fact_ids),
                }
                for step in trajectory.steps
                if step.turn < focus_turn
            ],
            "focus_action": _action_payload(focus_step),
            "focus_immediate_transition_outcome_only": {
                "client_response": focus_step.client_response,
                "client_response_kind": focus_step.client_response_kind,
                "client_selected_fact_ids": list(focus_step.client_selected_fact_ids),
                "stop_gate_verdict": focus_step.stop_gate_verdict,
                "policy_health_violations": list(focus_step.policy_health_violations),
                "post_policy_health_violations": list(focus_step.post_skill_health_violations),
            },
        }
        if include_state:
            payload["focus_visible_state_before_action"] = _compact_batch_teacher_state(
                _execution_state(focus_step)
            )
        return payload

    def _system_prompt(
        self,
        *,
        existing_skills: list[SkillContract],
        runtime_skills: list[SkillContract] | None = None,
        contrast_payload: dict[str, Any],
    ) -> str:
        runtime_ids = {
            item.skill_id
            for item in (
                runtime_skills
                if runtime_skills is not None
                else [item for item in existing_skills if item.status == "active"]
            )
        }
        return self.prompt.replace(
            "{existing_skill_payload}",
            json.dumps(
                [
                    {
                        "status": item.status,
                        "runtime_active_in_current_library": (item.skill_id in runtime_ids),
                        "version": item.version,
                        **policy_skill_document(item),
                    }
                    for item in existing_skills
                ],
                ensure_ascii=False,
                sort_keys=True,
            ),
        ).replace(
            "{contrast_payload}",
            json.dumps(contrast_payload, ensure_ascii=False, sort_keys=True),
        )

    @staticmethod
    def _bind_candidate(
        *,
        candidate: SkillContract,
        response: TeacherResponse,
        evidence_cluster: dict[str, Any],
        contrasts: list[tuple[AdvantageGroup, ContrastSelection, dict[str, ResearchTrajectory]]],
        supported_group_ids: list[str],
    ) -> SourceWitness | None:
        supported = set(supported_group_ids)
        candidate.status = "candidate"
        candidate.provenance.source = "tf_grpo"
        candidate.provenance.source_evidence_cluster_id = str(evidence_cluster["cluster_id"])
        candidate.provenance.source_signal_family = evidence_cluster["signal_family"]
        candidate.provenance.generator_model = response.model
        candidate.provenance.diagnosis_hash = response.response_sha256
        candidate.provenance.source_case_ids = sorted(
            {
                trajectories[selection.highest_id].case_id
                for group, selection, trajectories in contrasts
                if group.group_id in supported
            }
        )
        candidate.provenance.source_trajectory_ids = list(
            dict.fromkeys(
                trajectory_id
                for group, selection, _ in contrasts
                if group.group_id in supported
                for trajectory_id in (selection.highest_id, selection.lowest_id)
            )
        )
        return _build_source_witness(
            evidence_cluster_id=str(evidence_cluster["cluster_id"]),
            signal_family=evidence_cluster["signal_family"],
            contrasts=contrasts,
            supported_group_ids=supported_group_ids,
        )

    def propose(
        self,
        *,
        group: AdvantageGroup,
        selection: ContrastSelection,
        trajectories: dict[str, ResearchTrajectory],
        evaluations: dict[str, TrajectoryEvaluation],
        existing_skills: list[SkillContract],
    ) -> TeacherProposal:
        """Convenience entry point for one trajectory-contrast group."""

        del evaluations
        return self.propose_batch(
            batch_id=group.group_id,
            contrasts=[(group, selection, trajectories)],
            evaluations={},
            existing_skills=existing_skills,
            runtime_skills=[item for item in existing_skills if item.status == "active"],
            purpose="skill_teacher",
        )

    def extract_playbook_modes(
        self,
        *,
        package_id: str,
        evidence_cards: list[dict[str, Any]],
        current_playbook: SkillContract | None,
        purpose: str = "playbook_mode_extraction",
    ) -> PlaybookModeArtifact:
        """Map a disjoint card package into source-bound success/failure modes."""

        if not evidence_cards:
            raise ValueError("playbook map package must contain evidence cards")
        card_by_group = {str(card["group_id"]): card for card in evidence_cards}
        if len(card_by_group) != len(evidence_cards):
            raise ValueError("playbook map package contains duplicate group IDs")
        request_payload = playbook_map_request_payload(
            package_id=package_id,
            evidence_cards=evidence_cards,
            current_playbook=current_playbook,
        )
        response = self.client.generate_json(
            purpose=purpose,
            system_prompt=self.mode_prompt,
            user_prompt=json.dumps(request_payload, ensure_ascii=False, sort_keys=True),
            output_schema=_playbook_mode_output_schema(package_id=package_id),
        )
        try:
            draft = PlaybookModeBatchDraft.model_validate(response.value)
        except ValidationError as exc:
            raise TeacherProtocolError(
                f"playbook mode package schema violation: {package_id}: {exc}"
            ) from exc
        if draft.package_id != package_id:
            raise TeacherProtocolError(f"playbook mode package id mismatch: {package_id}")
        allowed_groups = set(card_by_group)
        no_new_groups = set(draft.no_new_mode_group_ids)
        if (
            len(no_new_groups) != len(draft.no_new_mode_group_ids)
            or not no_new_groups <= allowed_groups
        ):
            raise TeacherProtocolError(f"playbook no-new-mode binding invalid: {package_id}")
        cited_groups: set[str] = set()
        for index, mode in enumerate(draft.modes):
            cited = set(mode.source_group_ids)
            if len(cited) != len(mode.source_group_ids) or not cited <= allowed_groups:
                raise TeacherProtocolError(
                    f"playbook mode source binding invalid: {package_id}:{index}"
                )
            cited_groups.update(cited)
            if mode.mode_type == "success" and any(
                card_by_group[group_id].get("group_relative_status") != "process_differentiated"
                for group_id in cited
            ):
                raise TeacherProtocolError(
                    f"playbook success mode cites a tied group: {package_id}:{index}"
                )
        if cited_groups & no_new_groups or cited_groups | no_new_groups != allowed_groups:
            raise TeacherProtocolError(
                f"playbook map did not explicitly account for every source group: {package_id}"
            )
        return PlaybookModeArtifact(
            package_id=package_id,
            input_binding_sha256=playbook_map_input_binding_sha256(
                package_id=package_id,
                evidence_cards=evidence_cards,
                current_playbook=current_playbook,
            ),
            request_sha256=response.request_sha256,
            response_sha256=response.response_sha256,
            teacher_model=response.model,
            source_group_ids=sorted(allowed_groups),
            modes=draft.modes,
            # Preserve the model response order so the resumable artifact stays
            # byte-equivalent to its exact response-cache value.  Membership is
            # validated above as a set; ordering has no protocol semantics.
            no_new_mode_group_ids=list(draft.no_new_mode_group_ids),
        )

    def propose_playbook_update(
        self,
        *,
        package_id: str,
        evidence_cards: list[dict[str, Any]],
        mode_artifacts: list[PlaybookModeArtifact],
        current_playbook: SkillContract | None,
        library_feedback: dict[str, Any] | None,
        purpose: str = "playbook_patch_curation",
    ) -> tuple[TeacherProposal, PlaybookPatchDraft]:
        """Reduce modes into one exact local patch of the stable global playbook."""

        if len(mode_artifacts) < 1:
            raise ValueError("playbook curation requires at least one mode artifact")
        card_by_group = {str(card["group_id"]): card for card in evidence_cards}
        mapped_groups = [
            group_id for artifact in mode_artifacts for group_id in artifact.source_group_ids
        ]
        if len(mapped_groups) != len(set(mapped_groups)) or set(mapped_groups) != set(
            card_by_group
        ):
            raise TeacherProtocolError("playbook map artifacts do not partition all evidence cards")
        if current_playbook is not None and (
            current_playbook.skill_id != PLAYBOOK_SKILL_ID
            or current_playbook.domain != "general"
            or current_playbook.objective != "fact_elicitation"
        ):
            raise ValueError("current playbook has an incompatible identity")

        maximum_operations = (
            INITIAL_PLAYBOOK_MAX_PATCH_OPERATIONS
            if current_playbook is None
            else EXISTING_PLAYBOOK_MAX_PATCH_OPERATIONS
        )
        payload = playbook_reduce_request_payload(
            package_id=package_id,
            mode_artifacts=mode_artifacts,
            current_playbook=current_playbook,
            library_feedback=library_feedback,
            maximum_operations=maximum_operations,
        )
        response = self.client.generate_json(
            purpose=purpose,
            system_prompt=self.prompt,
            user_prompt=json.dumps(payload, ensure_ascii=False, sort_keys=True),
            output_schema=_playbook_patch_output_schema(
                package_id=package_id,
                maximum_operations=maximum_operations,
            ),
        )
        try:
            patch = PlaybookPatchDraft.model_validate(response.value)
        except ValidationError as exc:
            raise TeacherProtocolError(
                f"playbook patch schema violation: {package_id}: {exc}"
            ) from exc
        proposal = materialize_playbook_proposal(
            package_id=package_id,
            evidence_cards=evidence_cards,
            mode_artifacts=mode_artifacts,
            current_playbook=current_playbook,
            patch=patch,
            teacher_model=response.model,
            request_sha256=response.request_sha256,
            response_sha256=response.response_sha256,
        )
        return proposal, patch

    def propose_batch(
        self,
        *,
        batch_id: str,
        evidence_cluster_id: str | None = None,
        contrasts: list[tuple[AdvantageGroup, ContrastSelection, dict[str, ResearchTrajectory]]],
        evaluations: dict[str, TrajectoryEvaluation],
        existing_skills: list[SkillContract],
        runtime_skills: list[SkillContract],
        library_feedback: dict[str, Any] | None = None,
        purpose: str = "skill_teacher_batch",
    ) -> TeacherProposal:
        """Synthesize one document from exactly one eligible evidence cluster."""

        del evaluations
        if not contrasts:
            raise ValueError("batch teacher requires at least one trajectory contrast")
        clusters = teacher_evidence_cluster_summaries(contrasts)
        if evidence_cluster_id is None:
            clusters = [item for item in clusters if bool(item["eligible"])]
            if not clusters:
                raise ValueError("batch teacher has no eligible source evidence cluster")
            evidence_cluster = clusters[0]
        else:
            matching = [item for item in clusters if item["cluster_id"] == evidence_cluster_id]
            if len(matching) != 1:
                raise ValueError(
                    "batch teacher evidence cluster selection did not resolve exactly once: "
                    f"{evidence_cluster_id}"
                )
            evidence_cluster = matching[0]
        group_ids = set(evidence_cluster["group_ids"])
        selected_contrasts = [item for item in contrasts if item[0].group_id in group_ids]
        allowed_applicability_cues = _allowed_applicability_cues(selected_contrasts)
        required_applicability_cues = _required_applicability_cues(
            allowed_applicability_cues,
            evidence_cluster=evidence_cluster,
        )
        contrast_records: list[dict[str, Any]] = []
        for group, selection, trajectories in selected_contrasts:
            turn = selection.aligned_divergence_turn
            if turn is None:
                continue
            positive = trajectories[selection.highest_id]
            negative = trajectories[selection.lowest_id]

            def behavior_counts(trajectory: ResearchTrajectory) -> dict[str, int | float]:
                question_steps = [step for step in trajectory.steps if step.rendered_question]
                prior_unavailable: set[str] = set()
                unavailable_reasks = 0
                new_facts: set[str] = set()
                for step in question_steps:
                    target_id = str(_effective_action(step).target_id or "")
                    if target_id and target_id in prior_unavailable:
                        unavailable_reasks += 1
                    if step.client_response_kind == "unavailable" and target_id:
                        prior_unavailable.add(target_id)
                    if step.client_response_kind == "new_hidden_fact":
                        new_facts.update(str(item) for item in step.client_selected_fact_ids)
                return {
                    "questions": len(question_steps),
                    "new_facts": len(new_facts),
                    "unavailable_responses": sum(
                        step.client_response_kind == "unavailable" for step in question_steps
                    ),
                    "reasks_after_prior_unavailable": unavailable_reasks,
                    "facts_per_question": (
                        round(len(new_facts) / len(question_steps), 6) if question_steps else 0.0
                    ),
                }

            positive_counts = behavior_counts(positive)
            negative_counts = behavior_counts(negative)
            positive_score = next(
                item for item in group.members if item.trajectory_id == positive.trajectory_id
            )
            positive_downstream_flags = sorted(
                name
                for name, flagged in {
                    "premature_final": positive_score.premature_final,
                    "unsupported_claim": positive_score.unsupported_claim,
                    "belief_as_fact": positive_score.belief_as_fact,
                    "repeated_question": positive_score.repeated_question,
                    "hidden_field_leak": positive_score.hidden_field_leak,
                    "policy_fallback": positive_score.policy_fallback,
                    "client_fallback": positive_score.client_fallback,
                }.items()
                if flagged
            )
            contrast_records.append(
                {
                    "group_id": group.group_id,
                    "selection": selection.model_dump(mode="json"),
                    "causal_fork_contract": {
                        "same_case_persona_environment_and_opening_agenda": True,
                        "same_visible_state_before_first_action_divergence": True,
                        "only_lawyer_policy_sampling_stream_differs": True,
                        "source_witness_scope": (
                            "first_divergence_action_and_its_immediate_transition"
                        ),
                        "positive_downstream_trajectory_flags": positive_downstream_flags,
                        "downstream_flags_are_not_transferable_skill_evidence": True,
                    },
                    "comparative_outcomes": {
                        "positive": positive_counts,
                        "negative": negative_counts,
                        "delta_positive_minus_negative": {
                            key: round(float(positive_counts[key]) - float(negative_counts[key]), 6)
                            for key in positive_counts
                        },
                    },
                    "positive": self._teacher_trajectory(positive, turn, include_state=True),
                    "negative": self._teacher_trajectory(negative, turn, include_state=True),
                }
            )
        payload = {
            "batch_id": batch_id,
            "selection_rule": (
                "Use exactly this eligible evidence cluster. Produce one coherent "
                "prompt-skill document or NOOP; unseen efficacy is not established here."
            ),
            "allowed_applicability_cues": allowed_applicability_cues,
            "required_applicability_cues": required_applicability_cues,
            "applicability_cue_contract": (
                "candidate_skill.applicability_cues must contain only exact strings "
                "from allowed_applicability_cues and must include every string in "
                "required_applicability_cues; each string is deterministically derived "
                "from state visible before every claimed source action"
            ),
            "frozen_baseline_contract_and_observed_execution_gap": (BASELINE_CONTRACT_SUMMARY),
            "evidence_clusters": [{**evidence_cluster, "contrasts": contrast_records}],
            "input_library_prequential_feedback": library_feedback,
        }
        system = self._system_prompt(
            existing_skills=existing_skills,
            runtime_skills=runtime_skills,
            contrast_payload=payload,
        )
        response = self.client.generate_json(
            purpose=purpose,
            system_prompt=system,
            user_prompt=(
                f"只处理训练批{batch_id}给出的一个证据簇。非NOOP时，"
                "candidate_skill必须是一个自然语言咨询方法文档；group_id必须完全"
                "等于批ID，skill_scope必须等于candidate_skill.domain。"
            ),
            output_schema=strict_output_schema(TeacherDiagnosisDraft.model_json_schema()),
        )
        try:
            diagnosis = _materialize_teacher_diagnosis(
                TeacherDiagnosisDraft.model_validate(response.value)
            )
        except ValidationError as exc:
            return _schema_invalid_proposal(
                group_id=batch_id,
                response=response,
                error=exc,
            )
        issues = diagnosis_quality_issues(diagnosis)
        if diagnosis.group_id != batch_id:
            issues.append("group_id_mismatch")
        candidate = diagnosis.candidate_skill
        supported_group_ids: list[str] = []
        source_witness: SourceWitness | None = None
        if candidate is not None:
            issues.extend(
                candidate_context_scope_issues(
                    candidate,
                    evidence_cluster,
                    allowed_applicability_cues=set(allowed_applicability_cues),
                    required_applicability_cues=set(required_applicability_cues),
                )
            )
            issues.extend(validate_skill_static(candidate))
            grounding_issues, supported_group_ids = candidate_batch_source_grounding_issues(
                diagnosis,
                selected_contrasts,
                existing_skills=runtime_skills,
            )
            issues.extend(grounding_issues)
            if not grounding_issues:
                source_witness = self._bind_candidate(
                    candidate=candidate,
                    response=response,
                    evidence_cluster=evidence_cluster,
                    contrasts=selected_contrasts,
                    supported_group_ids=supported_group_ids,
                )
                issues.extend(
                    candidate_overlap_issues(
                        candidate,
                        historical_skills=existing_skills,
                        runtime_skills=runtime_skills,
                    )
                )
        parse_status = (
            "noop"
            if diagnosis.proposed_change == "NOOP"
            else "invalid_candidate"
            if issues or candidate is None
            else "valid_candidate"
        )
        return TeacherProposal(
            group_id=batch_id,
            request_sha256=response.request_sha256,
            response_sha256=response.response_sha256,
            teacher_model=response.model,
            parse_status=parse_status,
            static_issues=sorted(set(issues)),
            source_group_ids=supported_group_ids,
            source_witness=source_witness,
            diagnosis=diagnosis,
        )
