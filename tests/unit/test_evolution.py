import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from legal_skill_guard.evolution.advantage import (
    AdvantageGroup,
    ContrastSelection,
    ScoredMember,
    TrajectoryContrastPatch,
    compute_advantages,
    select_contrasts,
)
from legal_skill_guard.evolution.diagnosis import (
    BehaviorDifference,
    FailureState,
    SkillDiagnosis,
    TeacherDiagnosisDraft,
    diagnosis_quality_issues,
    parse_diagnosis,
)
from legal_skill_guard.evolution.group_evidence import (
    TrajectoryGroupEvidencePatch,
    build_group_evidence_card,
)
from legal_skill_guard.evolution.reward import (
    RewardComponents,
    RewardParameters,
    balanced_elicitation,
    no_substantive_dialogue_inquiry,
    proposed_final_was_redirected,
    trajectory_reward,
)
from legal_skill_guard.evolution.teacher import (
    EXISTING_PLAYBOOK_MAX_PATCH_OPERATIONS,
    INITIAL_PLAYBOOK_MAX_PATCH_OPERATIONS,
    PLAYBOOK_SKILL_ID,
    PlaybookModeArtifact,
    PlaybookPatchDraft,
    PlaybookReduceArtifact,
    SkillTeacher,
    TeacherProtocolError,
    _allowed_applicability_cues,
    _apply_playbook_patch,
    _compact_batch_teacher_state,
    _playbook_patch_output_schema,
    _schema_invalid_proposal,
    candidate_batch_source_grounding_issues,
    candidate_context_scope_issues,
    candidate_overlap_issues,
    candidate_source_grounding_issues,
    causal_visible_state_sha256,
    playbook_interface_catalog,
    playbook_map_input_binding_sha256,
    playbook_reduce_input_binding_sha256,
    select_teacher_evidence_clusters,
    teacher_evidence_cluster_summaries,
    teacher_evidence_fingerprint,
)
from legal_skill_guard.schemas.action import ActionDecision, StructuredAction
from legal_skill_guard.schemas.skill import SkillContract
from legal_skill_guard.schemas.state import (
    ConsultationState,
    FactObservation,
    FactSlot,
    Interaction,
    StatePatch,
)
from legal_skill_guard.skills.loader import validate_skill_static
from legal_skill_guard.skills.registry import SkillRegistry

REWARD_PARAMETERS = RewardParameters(
    elicitation_weight=0.45,
    resolution_weight=0.45,
    fidelity_weight=0.10,
    extra_turn_penalty=0.02,
    repeated_question_penalty=0.05,
    premature_final_cap=0.35,
    unsupported_claim_cap=0.25,
    hidden_field_leak_reward=0.0,
)


def prompt_skill(
    skill_id: str = "fact_elicitation.missing_relation",
    *,
    domain: str = "general",
    objective: str = "fact_elicitation",
    status: str = "candidate",
) -> SkillContract:
    return SkillContract.model_validate(
        {
            "schema_version": 2,
            "skill_id": skill_id,
            "name": "围绕未明关系作具体追问",
            "version": "1.0.0",
            "domain": domain,
            "status": status,
            "objective": objective,
            "description": "当关键关系仍不清楚时，用一个可回答的具体问题核实关系本身。",
            "applicability_cues": ["现有陈述提到有关主体，但双方关系尚不明确"],
            "procedure": ["区分已经陈述的结果与尚未说明的关系", "询问关系形成的具体经过"],
            "question_guidance": ["一次只询问一个事实属性，避免要求客户作法律判断"],
            "expected_effects": ["增加可用于后续分析的客户事实"],
            "contraindications": ["该关系已由客户明确说明时不再重复询问"],
            "failure_modes": ["问题过于抽象时客户可能仍无法回答"],
            "provenance": {"source": "tf_grpo"},
        }
    )


def causal_contrast(
    case_id: str = "case_a",
    domain: str = "labor_employment",
    *,
    group_id: str | None = None,
    positive_action: StructuredAction | None = None,
    negative_action: StructuredAction | None = None,
    state_update: dict | None = None,
) -> tuple[AdvantageGroup, ContrastSelection, dict[str, object]]:
    high_id = f"{case_id}.high"
    low_id = f"{case_id}.low"
    positive_action = positive_action or StructuredAction(
        action_type="ask",
        target_type="fact",
        target_id="F2",
        content="双方的实际关系是怎样形成的？",
    )
    negative_action = negative_action or StructuredAction(
        action_type="ask",
        target_type="fact",
        target_id="F3",
        content="争议发生后对方采取了什么具体行动？",
    )
    state = ConsultationState(
        session_id=f"session-{case_id}",
        max_turns=8,
        turn=1,
        domain=domain,
        persona="P_WD",
        facts=[
            FactSlot(
                fact_id="F1",
                label="已经陈述的争议结果",
                status="client_claimed",
                value="已经发生争议",
                criticality="medium",
                target_kind="client_fact",
            ),
            FactSlot(
                fact_id="F2",
                label="双方实际关系",
                status="unknown",
                criticality="high",
                target_kind="client_fact",
            ),
            FactSlot(
                fact_id="F3",
                label="争议发生后对方采取的具体行动",
                status="unknown",
                criticality="medium",
                target_kind="client_fact",
            ),
        ],
    )
    if state_update:
        state = state.model_copy(update=state_update)

    def step(action: StructuredAction, selected: list[str]) -> SimpleNamespace:
        return SimpleNamespace(
            turn=1,
            state_before=state.model_dump(mode="json"),
            state_patch=StatePatch(),
            proposed_action=action,
            action_decision=ActionDecision(original=action, final=action),
            rendered_question=(action.content or None),
            client_response=("客户补充了关系事实。" if selected else None),
            client_response_kind=("new_hidden_fact" if selected else "unavailable"),
            client_selected_fact_ids=selected,
            stop_gate_verdict="ALLOW",
            policy_health_violations=[],
            post_skill_health_violations=[],
        )

    high = SimpleNamespace(
        trajectory_id=high_id,
        case_id=case_id,
        domain=domain,
        persona="P_WD",
        status="memo_submitted",
        initial_investigation_plan=StatePatch(),
        steps=[step(positive_action, ["F2"])],
    )
    low = SimpleNamespace(
        trajectory_id=low_id,
        case_id=case_id,
        domain=domain,
        persona="P_WD",
        status="memo_submitted",
        initial_investigation_plan=StatePatch(),
        steps=[step(negative_action, [])],
    )
    group = AdvantageGroup(
        group_id=group_id or f"{case_id}.P_WD::fact_elicitation",
        members=[
            ScoredMember(trajectory_id=high_id, reward=0.7),
            ScoredMember(trajectory_id=low_id, reward=0.5),
        ],
        mean_reward=0.6,
        std_reward=0.1,
        informative=True,
    )
    selection = ContrastSelection(
        highest_id=high_id,
        lowest_id=low_id,
        aligned_divergence_turn=1,
        immediate_fact_gain=1,
        fact_gain=1,
        immediate_gap_gain=0,
        gap_gain=0,
        reward_gap=0.2,
        signal_family="fact_elicitation",
    )
    return group, selection, {high_id: high, low_id: low}


def test_batch_teacher_state_contains_only_visible_nonpersona_interface() -> None:
    state = ConsultationState(
        session_id="private-session-id",
        max_turns=8,
        domain="labor_employment",
        persona="P_WD",
        facts=[
            FactSlot(
                fact_id="F1",
                label="劳动合同解除日期",
                status="client_claimed",
                value="不应重复塞入教师提示的完整客户陈述",
                evidence_ids=["E1"],
                criticality="high",
                target_kind="client_fact",
            )
        ],
        asked_targets=["F1"],
        interactions=[
            Interaction(
                turn=1,
                action_type="ask",
                target_id="F1",
                question="不应重复塞入教师提示的历史问题",
            )
        ],
        candidate_action={"action_type": "ask", "target_id": "F1"},
    )
    payload = _compact_batch_teacher_state(state)
    rendered = str(payload)
    assert payload["visible_fact_plan"][0]["label"] == "劳动合同解除日期"
    assert "private-session-id" not in rendered
    assert "完整客户陈述" not in rendered
    assert "历史问题" not in rendered
    assert "P_WD" not in rendered
    assert "candidate_action" not in rendered


def test_rejected_document_is_history_but_not_a_runtime_reservation() -> None:
    rejected = prompt_skill(status="rejected")
    candidate = rejected.model_copy(deep=True)
    candidate.skill_id = "fact_elicitation.refined_relation"
    candidate.status = "candidate"
    candidate.description = "当关系仍不清楚时，先区分主体，再用单一问题确认实际关系。"
    issues = candidate_overlap_issues(
        candidate, historical_skills=[rejected], runtime_skills=[rejected]
    )
    assert not any(item.startswith("scope_redundancy:") for item in issues)
    assert not any(item.startswith("lexical_near_duplicate:") for item in issues)


def test_cluster_selection_prefers_an_unattempted_mechanism_before_revisiting() -> None:
    attempted = {
        "cluster_id": "already_attempted",
        "group_ids": ["old.1", "old.2", "new.3"],
        "source_case_count": 3,
        "source_domain_count": 2,
        "source_domains": ["criminal", "labor_employment"],
        "group_count": 3,
        "eligible": True,
        "eligible_skill_scopes": ["general"],
        "evidence_scope": "general",
        "signal_family": "fact_elicitation",
        "negative_action_type": "final",
        "positive_action_type": "ask",
        "behavior_family": "continue_inquiry",
        "total_fact_gain": 20,
    }
    unseen = {
        **attempted,
        "cluster_id": "unseen_target_choice",
        "group_ids": ["unseen.1"],
        "source_case_count": 1,
        "source_domain_count": 1,
        "source_domains": ["criminal"],
        "group_count": 1,
        "eligible_skill_scopes": ["criminal"],
        "evidence_scope": "criminal",
        "negative_action_type": "ask",
        "behavior_family": "target_selection",
        "total_fact_gain": 1,
    }
    selected = select_teacher_evidence_clusters(
        [attempted, unseen],
        attempted_fingerprints=set(),
        completed_cluster_ids=set(),
        budget=1,
        attempted_cluster_ids={"already_attempted"},
    )

    assert selected[0][0]["cluster_id"] == "unseen_target_choice"


def test_noop_cluster_reopens_only_at_a_geometric_support_milestone() -> None:
    initial = {
        "cluster_id": "evidence_limited_noop",
        "group_ids": ["case.1", "case.2"],
        "source_case_count": 2,
        "source_domain_count": 2,
        "source_domains": ["criminal", "labor_employment"],
        "group_count": 2,
        "eligible": True,
        "eligible_skill_scopes": ["general"],
        "evidence_scope": "general",
        "signal_family": "fact_elicitation",
        "negative_action_type": "final",
        "positive_action_type": "ask",
        "behavior_family": "continue_inquiry",
        "total_fact_gain": 2,
    }
    attempted = teacher_evidence_fingerprint(initial)
    three_cases = {
        **initial,
        "group_ids": ["case.1", "case.2", "case.3"],
        "source_case_count": 3,
        "group_count": 3,
        "total_fact_gain": 3,
    }
    four_cases = {
        **three_cases,
        "group_ids": ["case.1", "case.2", "case.3", "case.4"],
        "source_case_count": 4,
        "group_count": 4,
        "total_fact_gain": 4,
    }

    assert teacher_evidence_fingerprint(three_cases) == attempted
    assert (
        select_teacher_evidence_clusters(
            [three_cases],
            attempted_fingerprints={attempted},
            completed_cluster_ids=set(),
            budget=1,
        )
        == []
    )
    reconsidered = select_teacher_evidence_clusters(
        [four_cases],
        attempted_fingerprints={attempted},
        completed_cluster_ids=set(),
        budget=1,
    )
    assert reconsidered[0][0]["cluster_id"] == "evidence_limited_noop"
    assert reconsidered[0][1] != attempted
    assert (
        select_teacher_evidence_clusters(
            [four_cases],
            attempted_fingerprints=set(),
            completed_cluster_ids={"evidence_limited_noop"},
            budget=1,
        )
        == []
    )


def test_history_blocks_exact_rename_and_live_general_blocks_domain_copy() -> None:
    rejected = prompt_skill(status="rejected")
    renamed = rejected.model_copy(update={"skill_id": "fact_elicitation.renamed"})
    issues = candidate_overlap_issues(renamed, historical_skills=[rejected], runtime_skills=[])
    assert f"structural_duplicate:{rejected.skill_id}" in issues

    active = rejected.model_copy(update={"status": "active"})
    domain_copy = active.model_copy(
        update={"skill_id": "fact_elicitation.labor_copy", "domain": "labor_employment"}
    )
    issues = candidate_overlap_issues(
        domain_copy, historical_skills=[active], runtime_skills=[active]
    )
    assert f"scope_redundancy:{active.skill_id}" in issues


def _minimal_trajectory_contrast_payload() -> dict[str, object]:
    group = AdvantageGroup(
        group_id="case.P_WD",
        members=[
            ScoredMember(trajectory_id="high", reward=1.0),
            ScoredMember(trajectory_id="low", reward=0.0),
        ],
        mean_reward=0.5,
        std_reward=0.5,
        informative=True,
    )
    return {
        "schema_version": 3,
        "round_index": 1,
        "partition": "training_batch_01",
        "group": group.model_dump(mode="json"),
        "selection": {
            "highest_id": "high",
            "lowest_id": "low",
            "signal_family": "fact_elicitation",
        },
        "trajectory_ids": ["high", "low"],
        "trajectory_sha256": {"high": "a" * 64, "low": "b" * 64},
        "evaluation_sha256": {"high": "c" * 64, "low": "d" * 64},
    }


def test_trajectory_contrast_rejects_legacy_schema_and_implicit_signal_family() -> None:
    payload = _minimal_trajectory_contrast_payload()
    assert TrajectoryContrastPatch.model_validate(payload).selection.signal_family == (
        "fact_elicitation"
    )
    legacy = dict(payload)
    legacy["schema_version"] = 2
    with pytest.raises(ValueError, match="Input should be 3"):
        TrajectoryContrastPatch.model_validate(legacy)
    implicit = dict(payload)
    implicit["selection"] = {"highest_id": "high", "lowest_id": "low"}
    with pytest.raises(ValueError, match="explicit signal_family"):
        TrajectoryContrastPatch.model_validate(implicit)


def test_reward_applies_safety_caps_and_leak_zero() -> None:
    risky = trajectory_reward(
        RewardComponents(
            elicitation=1,
            resolution=1,
            fidelity=1,
            turns=2,
            repeated_question_rate=0,
            premature_final=True,
        ),
        REWARD_PARAMETERS,
    )
    assert risky.final_reward == 0.35
    leaked = trajectory_reward(
        RewardComponents(
            elicitation=1,
            resolution=1,
            fidelity=1,
            turns=1,
            repeated_question_rate=0,
            hidden_field_leak=True,
        ),
        REWARD_PARAMETERS,
    )
    assert leaked.final_reward == 0


def test_legacy_behavior_guard_termination_remains_interpretable() -> None:
    guarded = trajectory_reward(
        RewardComponents(
            elicitation=1,
            resolution=1,
            fidelity=1,
            turns=2,
            repeated_question_rate=0,
            behavior_guard_terminated=True,
        ),
        REWARD_PARAMETERS,
    )

    assert guarded.uncapped_reward > REWARD_PARAMETERS.behavior_guard_cap
    assert guarded.final_reward == REWARD_PARAMETERS.behavior_guard_cap
    assert guarded.applied_caps == ["behavior_guard_cap"]


def test_reward_preserves_negative_official_fidelity() -> None:
    result = trajectory_reward(
        RewardComponents(
            elicitation=0.2,
            resolution=0.2,
            fidelity=-0.6667,
            turns=1,
            repeated_question_rate=0,
            unsupported_claim=True,
        ),
        REWARD_PARAMETERS,
    )
    assert result.base_reward == 0.11333
    assert result.final_reward == 0.11333
    assert "unsupported_claim_cap" in result.applied_caps


def test_training_reward_requires_substantive_inquiry() -> None:
    assert balanced_elicitation(1.0, 0.0) == 0.0
    assert balanced_elicitation(1.0, 0.5) == pytest.approx(2 / 3)
    result = trajectory_reward(
        RewardComponents(
            elicitation=0.0,
            resolution=1.0,
            fidelity=1.0,
            turns=0,
            repeated_question_rate=0.0,
            no_substantive_inquiry=True,
        ),
        REWARD_PARAMETERS,
    )
    assert result.final_reward == 0.25
    assert "zero_inquiry_cap" in result.applied_caps


def test_zero_inquiry_cap_uses_observed_questions_not_semantic_rubric_score() -> None:
    assert no_substantive_dialogue_inquiry(expected_inquiry_count=3, question_turns=0)
    assert not no_substantive_dialogue_inquiry(expected_inquiry_count=3, question_turns=4)
    assert not no_substantive_dialogue_inquiry(expected_inquiry_count=0, question_turns=0)


def test_premature_final_uses_proposed_action_before_retired_rewrite_field() -> None:
    step = {
        "proposed_action": {"action_type": "final"},
        "action_decision": {"final": {"action_type": "clarify"}},
        "stop_gate_verdict": "REDIRECT",
    }
    assert proposed_final_was_redirected(step)


def test_advantage_skips_low_variance_and_selects_contrasts() -> None:
    flat = compute_advantages(
        "flat", [ScoredMember(trajectory_id=f"t{i}", reward=0.5) for i in range(4)]
    )
    assert not flat.informative
    varied = compute_advantages(
        "varied",
        [
            ScoredMember(trajectory_id="low", reward=0.1, turns=2),
            ScoredMember(trajectory_id="middle", reward=0.4, turns=1),
            ScoredMember(trajectory_id="unsafe", reward=0.6, premature_final=True),
            ScoredMember(trajectory_id="high", reward=0.9, turns=4),
        ],
    )
    selection = select_contrasts(varied)
    assert selection.highest_id == "high"
    assert selection.lowest_id == "low"
    assert selection.safety_failure_id == "unsafe"


def test_invalid_teacher_output_becomes_noop() -> None:
    diagnosis, mode = parse_diagnosis("not json", "group-1")
    assert diagnosis.proposed_change == "NOOP"
    assert mode == "fallback_noop"


def test_clustered_candidate_does_not_require_one_teacher_authored_failure_turn() -> None:
    """Per-fork system witnesses, not aggregate teacher prose, bind divergence turns."""

    diagnosis = SkillDiagnosis(
        group_id="multi-source-cluster",
        failure_state=FailureState(
            turn=None,
            relevant_fields=["focus_visible_state_before_action", "comparative_outcomes"],
        ),
        behavior_difference=BehaviorDifference(
            positive_action="在多个同状态分叉中使用更可回答的开放式亲历问题",
            negative_action="在多个同状态分叉中使用较封闭且低信息量的确认问题",
        ),
        causal_hypothesis="跨案件对照支持开放式亲历提问可能增加单位问题取得的客户事实。",
        proposed_change="CREATE",
        skill_scope="general",
        candidate_skill=prompt_skill(domain="general"),
    )

    assert "missing_failure_turn" not in diagnosis_quality_issues(diagnosis)


def test_candidate_cannot_turn_post_action_outcome_into_applicability_cue() -> None:
    candidate = prompt_skill(domain="labor_employment")
    evidence_cluster = {
        "eligible": True,
        "eligible_skill_scopes": ["labor_employment"],
        "signal_family": "fact_elicitation",
        "cluster_id": "source-cluster",
    }
    issues = candidate_context_scope_issues(
        candidate,
        evidence_cluster,
        allowed_applicability_cues={"当前仍有尚未询问的高重要性事实目标。"},
    )

    assert any(
        issue.startswith("applicability_cue_not_visible_before_source_action:") for issue in issues
    )


def test_immediate_unavailable_is_not_misread_as_prior_applicability_state() -> None:
    negative = StructuredAction(
        action_type="ask",
        target_type="fact",
        target_id="F2",
        content="双方实际关系是什么？",
    )
    group, selection, trajectories = causal_contrast(negative_action=negative)
    cues = _allowed_applicability_cues([(group, selection, trajectories)])

    assert "此前已有目标被客户明确表示不知道或暂不可得。" not in cues
    assert not any("至少有一项已由开场" in cue for cue in cues)

    trajectories[selection.lowest_id].steps[0].client_response_kind = "opening_repeat"
    cues = _allowed_applicability_cues([(group, selection, trajectories)])
    assert any("至少有一项已由开场" in cue for cue in cues)


def test_single_case_domain_skill_requires_its_visible_causal_cue() -> None:
    candidate = prompt_skill(domain="labor_employment")
    generic_cue = "当前仍有尚未询问的高重要性事实目标。"
    domain_cue = (
        "当前公开案件领域为“labor_employment”，且仍有与可见争议直接相关的未询问客户事实目标。"
    )
    candidate.applicability_cues = [generic_cue]
    issues = candidate_context_scope_issues(
        candidate,
        {
            "eligible": True,
            "eligible_skill_scopes": ["labor_employment"],
            "signal_family": "fact_elicitation",
            "cluster_id": "single-case-domain-source",
            "source_case_count": 1,
        },
        allowed_applicability_cues={
            generic_cue,
            domain_cue,
        },
        required_applicability_cues={domain_cue},
    )

    assert f"candidate_missing_required_causal_cue:{domain_cue}" in issues


def test_teacher_cannot_claim_unimplemented_skill_lifecycle_operation() -> None:
    with pytest.raises(ValidationError) as caught:
        TeacherDiagnosisDraft.model_validate(
            {
                "group_id": "batch",
                "failure_state": {"turn": 1, "relevant_fields": []},
                "behavior_difference": {
                    "positive_action": "继续询问尚未明确的客户事实",
                    "negative_action": "在事实未明时结束咨询",
                },
                "causal_hypothesis": "继续询问可能取得分析所需事实，仍待未见案件验证。",
                "proposed_change": "DEPRECATE",
                "skill_scope": "general",
                "candidate_skill": None,
            }
        )

    assert any(
        error["loc"] == ("proposed_change",) and error["type"] == "literal_error"
        for error in caught.value.errors()
    )


def test_invalid_teacher_schema_is_quarantined() -> None:
    with pytest.raises(ValidationError) as caught:
        TeacherDiagnosisDraft.model_validate({"group_id": "batch"})
    proposal = _schema_invalid_proposal(
        group_id="batch",
        response=SimpleNamespace(
            request_sha256="a" * 64,
            response_sha256="b" * 64,
            model="teacher-test",
        ),
        error=caught.value,
    )
    assert proposal.schema_version == 3
    assert proposal.parse_status == "invalid_candidate"
    assert proposal.usable_candidate is None
    assert proposal.source_witness is None


def test_source_witness_accepts_document_without_executable_replay() -> None:
    group, selection, trajectories = causal_contrast()
    second_group, second_selection, second_trajectories = causal_contrast(
        "case_b", "labor_employment"
    )
    skill = prompt_skill(domain="labor_employment")
    diagnosis = SkillDiagnosis(
        group_id=group.group_id,
        failure_state=FailureState(turn=1, relevant_fields=["visible_fact_plan"]),
        behavior_difference=BehaviorDifference(
            positive_action="继续询问一个尚未说明的关系事实",
            negative_action="在同一可见状态下直接结束咨询",
        ),
        causal_hypothesis="明确追问未说明关系可能增加可用于分析的事实，仍需未见块验证。",
        proposed_change="CREATE",
        skill_scope="labor_employment",
        candidate_skill=skill,
    )
    assert candidate_source_grounding_issues(diagnosis, selection, trajectories) == []
    issues, supported = candidate_batch_source_grounding_issues(
        diagnosis,
        [
            (group, selection, trajectories),
            (second_group, second_selection, second_trajectories),
        ],
    )
    assert issues == []
    assert supported == [group.group_id, second_group.group_id]


def test_source_grounding_uses_system_divergence_for_one_and_many_sources() -> None:
    first_group, first_selection, first_trajectories = causal_contrast(
        "labor_a", "labor_employment"
    )
    second_group, second_selection, second_trajectories = causal_contrast(
        "labor_b", "labor_employment"
    )
    diagnosis = SkillDiagnosis(
        group_id="teacher-authored-diagnostic",
        # Deliberately wrong: this prose field must not decide the artifact gate.
        failure_state=FailureState(turn=99, relevant_fields=["visible_fact_plan"]),
        behavior_difference=BehaviorDifference(
            positive_action="继续询问一个尚未说明的关系事实",
            negative_action="在相同可见状态下直接结束咨询",
        ),
        causal_hypothesis="明确追问未说明关系可能增加可用于分析的事实，仍需后续评估。",
        proposed_change="CREATE",
        skill_scope="labor_employment",
        candidate_skill=prompt_skill(domain="labor_employment"),
    )

    assert (
        candidate_source_grounding_issues(
            diagnosis,
            first_selection,
            first_trajectories,
        )
        == []
    )
    one_issues, one_supported = candidate_batch_source_grounding_issues(
        diagnosis,
        [(first_group, first_selection, first_trajectories)],
    )
    many_issues, many_supported = candidate_batch_source_grounding_issues(
        diagnosis,
        [
            (first_group, first_selection, first_trajectories),
            (second_group, second_selection, second_trajectories),
        ],
    )
    assert one_issues == []
    assert many_issues == []
    assert one_supported == [first_group.group_id]
    assert many_supported == [first_group.group_id, second_group.group_id]


def test_general_source_grounding_requires_two_cases_across_two_domains() -> None:
    first_group, first_selection, first_trajectories = causal_contrast(
        "labor_a", "labor_employment"
    )
    same_group, same_selection, same_trajectories = causal_contrast("labor_b", "labor_employment")
    cross_group, cross_selection, cross_trajectories = causal_contrast(
        "commercial_a", "company_commercial"
    )
    diagnosis = SkillDiagnosis(
        group_id="general-source-scope",
        failure_state=FailureState(turn=1, relevant_fields=["visible_fact_plan"]),
        behavior_difference=BehaviorDifference(
            positive_action="继续询问一个未覆盖的高价值事实",
            negative_action="在同一可见状态下直接结束咨询",
        ),
        causal_hypothesis="该跨域方法可能增加事实获取，仍需后续累计评估。",
        proposed_change="CREATE",
        skill_scope="general",
        candidate_skill=prompt_skill(domain="general"),
    )

    one_issues, _ = candidate_batch_source_grounding_issues(
        diagnosis,
        [(first_group, first_selection, first_trajectories)],
    )
    same_domain_issues, _ = candidate_batch_source_grounding_issues(
        diagnosis,
        [
            (first_group, first_selection, first_trajectories),
            (same_group, same_selection, same_trajectories),
        ],
    )
    cross_domain_issues, supported = candidate_batch_source_grounding_issues(
        diagnosis,
        [
            (first_group, first_selection, first_trajectories),
            (cross_group, cross_selection, cross_trajectories),
        ],
    )

    assert "general_source_support_cases:1<2" in one_issues
    assert "general_source_support_domains:1<2" in one_issues
    assert same_domain_issues == ["general_source_support_domains:1<2"]
    assert cross_domain_issues == []
    assert supported == [first_group.group_id, cross_group.group_id]


def test_source_witness_rejects_different_visible_state_at_claimed_divergence() -> None:
    group, selection, trajectories = causal_contrast()
    high = trajectories[selection.highest_id]
    high.steps[0].state_before["asked_targets"] = ["F2"]
    skill = prompt_skill(domain="labor_employment", objective="safe_stop")
    diagnosis = SkillDiagnosis(
        group_id=group.group_id,
        failure_state=FailureState(turn=1),
        behavior_difference=BehaviorDifference(
            positive_action="继续询问尚未说明的事实",
            negative_action="在相同状态下直接结束",
        ),
        causal_hypothesis="该方法可能改变事实获取，需要独立检验。",
        proposed_change="CREATE",
        skill_scope="labor_employment",
        candidate_skill=skill,
    )
    issues = candidate_source_grounding_issues(diagnosis, selection, trajectories)
    assert issues == ["source_grounding_visible_state_mismatch_at_divergence"]


def test_causal_state_hash_binds_the_actual_visible_dialogue_history() -> None:
    _, selection, trajectories = causal_contrast()
    high = trajectories[selection.highest_id]
    low = trajectories[selection.lowest_id]
    common_system = {"role": "system", "content": "同一方法与状态"}
    high.steps[0].visible_input = [
        common_system,
        {"role": "assistant", "content": "此前问句甲？"},
        {"role": "user", "content": "相同的结构化结果"},
    ]
    low.steps[0].visible_input = [
        common_system,
        {"role": "assistant", "content": "此前问句乙？"},
        {"role": "user", "content": "相同的结构化结果"},
    ]

    assert causal_visible_state_sha256(high.steps[0]) != causal_visible_state_sha256(low.steps[0])


def test_domain_cluster_accepts_one_exact_case_but_general_requires_cross_domain() -> None:
    first = causal_contrast("labor_a", "labor_employment")
    summaries = teacher_evidence_cluster_summaries([first])
    general = next(item for item in summaries if item["evidence_scope"] == "general")
    scoped = next(item for item in summaries if item["evidence_scope"] == "labor_employment")
    assert general["eligible"] is False
    assert scoped["eligible"] is True
    assert scoped["ineligible_reason"] is None

    second = causal_contrast("labor_b", "labor_employment")
    summaries = teacher_evidence_cluster_summaries([first, second])
    scoped = next(item for item in summaries if item["evidence_scope"] == "labor_employment")
    assert scoped["eligible"] is True
    assert scoped["ineligible_reason"] is None
    assert scoped["behavior_family"] == "target_selection"

    terminal_source = causal_contrast(
        "terminal_source",
        "labor_employment",
        negative_action=StructuredAction(action_type="final", target_type="none", content=""),
    )
    terminal_summaries = teacher_evidence_cluster_summaries([terminal_source])
    terminal_scoped = next(
        item for item in terminal_summaries if item["evidence_scope"] == "labor_employment"
    )
    assert terminal_scoped["eligible"] is True
    assert terminal_scoped["teacher_expressible"] is True
    assert terminal_scoped["ineligible_reason"] is None

    same_domain_second = causal_contrast("labor_b", "labor_employment")
    summaries = teacher_evidence_cluster_summaries([first, same_domain_second])
    scoped = next(item for item in summaries if item["evidence_scope"] == "labor_employment")
    assert scoped["eligible"] is True
    assert scoped["source_case_count"] == 2

    second = causal_contrast("criminal_a", "criminal")
    summaries = teacher_evidence_cluster_summaries([first, second])
    general = next(item for item in summaries if item["evidence_scope"] == "general")
    assert general["eligible"] is True
    assert general["source_domain_count"] == 2


def test_clusters_keep_system_target_kind_transitions_separate() -> None:
    client_to_client = causal_contrast(
        "client_transition",
        positive_action=StructuredAction(
            action_type="ask",
            target_type="fact",
            target_id="F2",
            content="双方实际关系是什么？",
        ),
        negative_action=StructuredAction(
            action_type="ask",
            target_type="evidence",
            target_id="F1",
            content="争议结果是什么？",
        ),
    )
    evidence_to_client = causal_contrast(
        "evidence_transition",
        positive_action=StructuredAction(
            action_type="ask",
            target_type="fact",
            target_id="F2",
            content="双方实际关系是什么？",
        ),
        negative_action=StructuredAction(
            action_type="ask",
            target_type="fact",
            target_id="E1",
            content="书面证据是否留存？",
        ),
    )
    # Keep the model-authored target_type deliberately unhelpful.  The
    # transition must be determined by the planner-owned fact slots.
    _, evidence_selection, evidence_trajectories = evidence_to_client
    for trajectory in evidence_trajectories.values():
        trajectory.steps[0].state_before["facts"].append(
            {
                "fact_id": "E1",
                "label": "书面证据是否留存",
                "status": "unknown",
                "criticality": "medium",
                "target_kind": "evidence_or_third_party",
            }
        )
    evidence_negative = evidence_trajectories[evidence_selection.lowest_id]
    assert evidence_negative.steps[0].proposed_action.target_id == "E1"

    summaries = teacher_evidence_cluster_summaries([client_to_client, evidence_to_client])
    transitions = {
        (item["negative_target_kind"], item["positive_target_kind"])
        for item in summaries
        if item["evidence_scope"] == "general"
    }

    assert transitions == {
        ("client_fact", "client_fact"),
        ("evidence_or_third_party", "client_fact"),
    }


def test_clusters_do_not_merge_distinct_negative_transition_outcomes() -> None:
    unavailable = causal_contrast("unavailable_case", "labor_employment")
    opening_repeat = causal_contrast("opening_repeat_case", "labor_employment")
    _, opening_selection, opening_trajectories = opening_repeat
    opening_trajectories[opening_selection.lowest_id].steps[
        0
    ].client_response_kind = "opening_repeat"

    summaries = teacher_evidence_cluster_summaries([unavailable, opening_repeat])
    scoped = [item for item in summaries if item["evidence_scope"] == "labor_employment"]

    assert {
        (item["negative_transition_outcome"], item["positive_transition_outcome"])
        for item in scoped
    } == {
        ("unavailable", "new_hidden_fact"),
        ("opening_repeat", "new_hidden_fact"),
    }
    assert all(item["source_case_count"] == 1 for item in scoped)


def test_same_causal_fork_cannot_schedule_two_outcome_labeled_skills() -> None:
    fact_group, fact_selection, trajectories = causal_contrast(
        "dual_outcome_case", "intellectual_property"
    )
    gap_group = fact_group.model_copy(
        update={"group_id": "dual_outcome_case.P_WD::evidence_gap_identification"}
    )
    gap_selection = fact_selection.model_copy(
        update={
            "signal_family": "evidence_gap_identification",
            "immediate_gap_gain": 1,
            "gap_gain": 1,
        }
    )
    summaries = teacher_evidence_cluster_summaries(
        [
            (fact_group, fact_selection, trajectories),
            (gap_group, gap_selection, trajectories),
        ]
    )
    scoped = [
        item
        for item in summaries
        if item["eligible"] and item["evidence_scope"] == "intellectual_property"
    ]
    assert {item["signal_family"] for item in scoped} == {
        "fact_elicitation",
        "evidence_gap_identification",
    }
    assert len({tuple(item["source_causal_fork_sha256s"]) for item in scoped}) == 1

    selected = select_teacher_evidence_clusters(
        scoped,
        attempted_fingerprints=set(),
        completed_cluster_ids=set(),
        budget=2,
        signal_priority=["fact_elicitation", "evidence_gap_identification"],
    )
    assert len(selected) == 1
    assert selected[0][0]["signal_family"] == "fact_elicitation"

    assert (
        select_teacher_evidence_clusters(
            scoped,
            attempted_fingerprints=set(),
            completed_cluster_ids=set(),
            budget=2,
            completed_source_causal_fork_sha256s=set(selected[0][0]["source_causal_fork_sha256s"]),
        )
        == []
    )


def test_teacher_rejects_semantic_target_alias_and_question_paraphrase() -> None:
    precise = StructuredAction(
        action_type="ask",
        target_type="fact",
        target_id="F2",
        expected_information="双方实际关系形成的具体经过",
        content="双方的实际关系是通过什么具体经过形成的？",
        constraints=["一次只问一个事实"],
    )
    vague = StructuredAction(
        action_type="ask",
        target_type="fact",
        target_id="F2_alias",
        expected_information="双方关系情况",
        content="你们之间是什么情况？",
        constraints=["简短回答"],
    )
    contrast = causal_contrast(
        "labor_formulation",
        "labor_employment",
        positive_action=precise,
        negative_action=vague,
    )

    second_contrast = causal_contrast(
        "labor_formulation_b",
        "labor_employment",
        positive_action=precise,
        negative_action=vague,
    )
    contrasts = [contrast, second_contrast]
    for _, _, trajectories in contrasts:
        for trajectory in trajectories.values():
            trajectory.steps[0].state_before["facts"].append(
                {
                    "fact_id": "F2_alias",
                    "label": "双方实际关系",
                    "status": "unknown",
                    "criticality": "high",
                    "target_kind": "client_fact",
                }
            )

    assert teacher_evidence_cluster_summaries(contrasts) == []


def test_cluster_selection_covers_distinct_behavior_before_scope_alias() -> None:
    def cluster(cluster_id: str, behavior: str, cases: int, attempted: bool = False) -> dict:
        return {
            "cluster_id": cluster_id,
            "group_ids": [f"{cluster_id}.{index}" for index in range(cases)],
            "source_case_count": cases,
            "source_domain_count": 2,
            "group_count": cases,
            "eligible": True,
            "signal_family": "fact_elicitation",
            "negative_action_type": "final" if behavior == "continue" else "ask",
            "positive_action_type": "ask",
            "behavior_family": behavior,
            "attempted": attempted,
        }

    values = [
        cluster("continuation", "continue", 8),
        cluster("continuation__scope_labor", "continue", 7),
        cluster("target", "target", 2),
    ]
    selected = select_teacher_evidence_clusters(
        values,
        attempted_fingerprints=set(),
        completed_cluster_ids=set(),
        budget=2,
    )
    assert [item[0]["cluster_id"] for item in selected] == ["continuation", "target"]


def test_cluster_selection_prefers_durable_fact_or_gap_gain_over_large_noisy_cluster() -> None:
    noisy = {
        "cluster_id": "large_question_wording_cluster",
        "group_ids": [f"noisy.{index}" for index in range(12)],
        "source_case_count": 12,
        "source_domain_count": 8,
        "group_count": 12,
        "eligible": True,
        "signal_family": "fact_elicitation",
        "negative_action_type": "ask",
        "positive_action_type": "ask",
        "behavior_family": "question_formulation",
        "total_fact_gain": 0,
        "total_gap_gain": 0,
        "total_immediate_fact_gain": 1,
        "total_immediate_gap_gain": 0,
        "total_reward_gap": 4.0,
    }
    durable = {
        "cluster_id": "smaller_durable_target_cluster",
        "group_ids": ["durable.1", "durable.2"],
        "source_case_count": 2,
        "source_domain_count": 2,
        "group_count": 2,
        "eligible": True,
        "signal_family": "fact_elicitation",
        "negative_action_type": "ask",
        "positive_action_type": "ask",
        "behavior_family": "target_choice",
        "total_fact_gain": 2,
        "total_gap_gain": 0,
        "total_immediate_fact_gain": 2,
        "total_immediate_gap_gain": 0,
        "total_reward_gap": 1.0,
    }
    selected = select_teacher_evidence_clusters(
        [noisy, durable],
        attempted_fingerprints=set(),
        completed_cluster_ids=set(),
        budget=1,
    )
    assert selected[0][0]["cluster_id"] == "smaller_durable_target_cluster"


def test_cluster_selection_obeys_prequential_signal_priority_before_raw_gain() -> None:
    fact = {
        "cluster_id": "fact_recovery",
        "group_ids": ["fact.1"],
        "source_case_count": 1,
        "source_domain_count": 1,
        "group_count": 1,
        "eligible": True,
        "evidence_scope": "labor_employment",
        "eligible_skill_scopes": ["labor_employment"],
        "source_domains": ["labor_employment"],
        "signal_family": "fact_elicitation",
        "negative_action_type": "ask",
        "positive_action_type": "ask",
        "behavior_family": "target_selection",
        "total_fact_gain": 1,
        "total_gap_gain": 0,
    }
    gap = {
        **fact,
        "cluster_id": "large_gap_gain",
        "group_ids": ["gap.1"],
        "signal_family": "evidence_gap_identification",
        "total_fact_gain": 0,
        "total_gap_gain": 20,
    }
    selected = select_teacher_evidence_clusters(
        [gap, fact],
        attempted_fingerprints=set(),
        completed_cluster_ids=set(),
        budget=1,
        signal_priority=["fact_elicitation", "evidence_gap_identification", "safe_stop"],
    )

    assert selected[0][0]["cluster_id"] == "fact_recovery"


def test_cluster_selection_budget_three_covers_scope_mechanism_and_domain() -> None:
    def cluster(
        cluster_id: str,
        *,
        scope: str,
        behavior: str,
        gain: int,
    ) -> dict:
        return {
            "cluster_id": cluster_id,
            "group_ids": [f"{cluster_id}.group"],
            "source_case_count": 1,
            "source_domain_count": 2 if scope == "general" else 1,
            "source_domains": (["labor_employment", "criminal"] if scope == "general" else [scope]),
            "group_count": 1,
            "eligible": True,
            "eligible_skill_scopes": [scope],
            "evidence_scope": scope,
            "signal_family": "fact_elicitation",
            "negative_action_type": "ask",
            "positive_action_type": "ask",
            "behavior_family": behavior,
            "total_fact_gain": gain,
        }

    values = [
        cluster(
            "general_continue",
            scope="general",
            behavior="continue_inquiry",
            gain=10,
        ),
        cluster(
            "general_target",
            scope="general",
            behavior="target_choice",
            gain=9,
        ),
        cluster(
            "labor_formulation",
            scope="labor_employment",
            behavior="question_formulation",
            gain=2,
        ),
        cluster(
            "criminal_evidence",
            scope="criminal",
            behavior="evidence_target_choice",
            gain=1,
        ),
    ]
    selected = select_teacher_evidence_clusters(
        values,
        attempted_fingerprints=set(),
        completed_cluster_ids=set(),
        budget=3,
    )

    assert [item[0]["cluster_id"] for item in selected] == [
        "general_continue",
        "labor_formulation",
        "criminal_evidence",
    ]
    assert {item[0]["evidence_scope"] for item in selected} >= {
        "general",
        "labor_employment",
    }
    assert len({item[0]["behavior_family"] for item in selected}) == 3


def test_cluster_selection_never_repeats_a_fingerprint() -> None:
    general = {
        "cluster_id": "general_continue",
        "group_ids": ["shared.group"],
        "source_case_count": 2,
        "source_domain_count": 2,
        "source_domains": ["labor_employment", "criminal"],
        "group_count": 2,
        "eligible": True,
        "eligible_skill_scopes": ["general"],
        "evidence_scope": "general",
        "signal_family": "fact_elicitation",
        "negative_action_type": "final",
        "positive_action_type": "ask",
        "behavior_family": "continue_inquiry",
        "total_fact_gain": 3,
    }
    labor = {
        **general,
        "cluster_id": "labor_target",
        "group_ids": ["labor.group"],
        "source_case_count": 1,
        "source_domain_count": 1,
        "source_domains": ["labor_employment"],
        "group_count": 1,
        "eligible_skill_scopes": ["labor_employment"],
        "evidence_scope": "labor_employment",
        "behavior_family": "target_choice",
        "total_fact_gain": 2,
    }
    selected = select_teacher_evidence_clusters(
        [general, dict(general), labor],
        attempted_fingerprints=set(),
        completed_cluster_ids=set(),
        budget=3,
    )

    assert [item[0]["cluster_id"] for item in selected] == [
        "general_continue",
        "labor_target",
    ]
    assert len({fingerprint for _, fingerprint in selected}) == len(selected)

    retried = select_teacher_evidence_clusters(
        [general, dict(general), labor],
        attempted_fingerprints={selected[0][1]},
        completed_cluster_ids=set(),
        budget=3,
    )
    assert [item[0]["cluster_id"] for item in retried] == ["labor_target"]


def test_cluster_selection_does_not_invent_missing_scope_coverage() -> None:
    values = [
        {
            "cluster_id": f"general_{index}",
            "group_ids": [f"general.{index}"],
            "source_case_count": 2,
            "source_domain_count": 2,
            "source_domains": ["labor_employment", "criminal"],
            "group_count": 2,
            "eligible": True,
            "eligible_skill_scopes": ["general"],
            "evidence_scope": "general",
            "signal_family": "fact_elicitation",
            "negative_action_type": "ask",
            "positive_action_type": "ask",
            "behavior_family": behavior,
            "total_fact_gain": 3 - index,
        }
        for index, behavior in enumerate(["continue_inquiry", "target_choice"])
    ]
    selected = select_teacher_evidence_clusters(
        values,
        attempted_fingerprints=set(),
        completed_cluster_ids=set(),
        budget=3,
    )

    assert len(selected) == 2
    assert {item[0]["evidence_scope"] for item in selected} == {"general"}


def test_candidate_scope_and_objective_are_bound_to_cluster() -> None:
    candidate = prompt_skill(domain="general")
    cluster = {
        "eligible": True,
        "eligible_skill_scopes": ["criminal"],
        "signal_family": "safe_stop",
        "cluster_id": "safe_stop_cluster",
    }
    assert candidate_context_scope_issues(candidate, cluster) == [
        "candidate_domain_not_allowed_by_evidence:general",
        "candidate_objective_mismatch:fact_elicitation!=safe_stop",
    ]


class FakeTeacherClient:
    model = "gpt-test"

    def __init__(self, value: dict) -> None:
        self.value = value
        self.output_schema: dict | None = None
        self.system_prompt: str | None = None
        self.user_prompt: str | None = None

    def generate_json(self, **kwargs):
        self.output_schema = kwargs["output_schema"]
        self.system_prompt = kwargs["system_prompt"]
        self.user_prompt = kwargs["user_prompt"]
        return SimpleNamespace(
            value=self.value,
            model=self.model,
            request_sha256="a" * 64,
            response_sha256="b" * 64,
        )


def test_complete_group_card_keeps_all_members_and_marks_real_process_difference() -> None:
    def trajectory(index: int, *, gained: bool) -> SimpleNamespace:
        action = StructuredAction(
            action_type="ask",
            target_type="fact",
            target_id="F1",
            reason="核实客户能够直接回答的关键事实",
            expected_information="关键履行事实",
            content="请说明实际履行经过？",
        )
        step = SimpleNamespace(
            turn=1,
            proposed_action=action,
            action_decision=SimpleNamespace(final=action),
            state_before={
                "facts": [
                    {
                        "fact_id": "F1",
                        "label": "实际履行经过",
                    }
                ]
            },
            rendered_question=action.content,
            client_response="客户说明了履行经过" if gained else "客户目前不知道",
            client_response_kind="new_hidden_fact" if gained else "unavailable",
            client_selected_fact_ids=["F1"] if gained else [],
            stop_gate_verdict="CONTINUE",
            stop_gate_reason="action_allowed",
            policy_attempts=[],
            post_skill_health_violations=[],
        )
        return SimpleNamespace(
            trajectory_id=f"trajectory_{index}",
            sample_index=index,
            case_id="case_a",
            domain="labor_employment",
            persona="P_WD",
            skill_library_version="bootstrap_empty",
            opening="客户称劳动合同履行发生争议。",
            opening_inquiry_agenda=SimpleNamespace(
                observations=[
                    FactObservation(
                        fact_id="opening_agenda履行时间",
                        label="合同实际履行时间",
                        status="unknown",
                        value=None,
                        evidence_labels=["public_opening_anchor:合同履行"],
                        confidence=0.5,
                        criticality="high",
                        target_kind="client_fact",
                    )
                ]
            ),
            status="memo_submitted",
            steps=[step],
        )

    members = [trajectory(index, gained=index == 0) for index in range(4)]
    # Exhausting the bounded episode is a genuine policy outcome: it remains in
    # the complete K-group and is explicitly visible to the teacher as a failure.
    members[-1].status = "max_turns_forced_memo"
    evaluations = {
        item.trajectory_id: SimpleNamespace(
            reward=SimpleNamespace(final_reward=0.8 if index == 0 else 0.2),
            safety_metrics=SimpleNamespace(
                premature_final_rate=0.0,
                unsupported_claim_rate=0.0,
                belief_as_fact_rate=0.0,
                repeated_question_rate=0.0,
                hidden_field_leak=False,
            ),
            operational_metrics=SimpleNamespace(
                policy_fallback_rate=0.0,
                client_fallback_rate=0.0,
            ),
        )
        for index, item in enumerate(members)
    }

    card = build_group_evidence_card("group_a", members, evaluations)

    assert card["group_size"] == 4
    assert len(card["trajectory_summaries"]) == 4
    assert card["group_relative_status"] == "process_differentiated"
    assert card["schema_version"] == 4
    assert card["opening_inquiry_agenda"] == [
        {
            "target_id": "opening_agenda履行时间",
            "label": "合同实际履行时间",
            "criticality": "high",
            "target_kind": "client_fact",
        }
    ]
    assert "public_opening_anchor" not in json.dumps(
        card["opening_inquiry_agenda"], ensure_ascii=False
    )
    assert card["best_trajectory_ids"] == ["trajectory_0"]
    assert card["trajectory_summaries"][-1]["process_failure_flags"] == [
        "emergency_turn_ceiling"
    ]
    assert set(card["representative_full_dialogues"]) == {
        "trajectory_0",
        "trajectory_1",
    }
    assert card["undisclosed_hidden_facts_included"] is False
    first_summary = card["trajectory_summaries"][0]
    assert first_summary["visible_target_catalog"] == [
        {
            "target_id": "F1",
            "label": "实际履行经过",
            "criticality": "medium",
            "target_kind": "client_fact",
        }
    ]
    assert first_summary["turn_outline"][0][
        "visible_unresolved_targets_before_action"
    ] == [{"target_id": "F1", "status": "unknown", "asked": False}]
    with pytest.raises(ValueError, match="exactly four"):
        build_group_evidence_card("group_short", members[:3], evaluations)


def _group_evidence_patch_payload() -> dict[str, object]:
    card = {
        "schema_version": 4,
        "group_id": "group_a",
        "case_id": "case_a",
        "domain": "labor_employment",
        "persona": "P_WD",
        "skill_library_version": "bootstrap_empty",
        "opening_inquiry_agenda": [
            {
                "target_id": "opening_agenda_contract_date",
                "label": "劳动合同签订时间",
                "criticality": "high",
                "target_kind": "client_fact",
            }
        ],
        "trajectory_summaries": [
            {
                "visible_target_catalog": [
                    {
                        "target_id": "target_a",
                        "label": "当时可见的待核实事实",
                        "criticality": "high",
                        "target_kind": "client_fact",
                    }
                ],
                "turn_outline": [
                    {
                        "visible_unresolved_targets_before_action": [
                            {
                                "target_id": "target_a",
                                "status": "unknown",
                                "asked": False,
                            }
                        ]
                    }
                ],
            }
            for _ in range(4)
        ],
        "undisclosed_hidden_facts_included": False,
    }
    return {
        "schema_version": 4,
        "round_index": 1,
        "partition": "training_batch_01",
        "group_id": "group_a",
        "case_id": "case_a",
        "domain": "labor_employment",
        "persona": "P_WD",
        "skill_library_version": "bootstrap_empty",
        "trajectory_ids": [f"trajectory_{index}" for index in range(4)],
        "trajectory_sha256": {f"trajectory_{index}": "a" * 64 for index in range(4)},
        "evaluation_sha256": {f"trajectory_{index}": "b" * 64 for index in range(4)},
        "card": card,
    }


def test_group_evidence_patch_rejects_legacy_outer_and_inner_card_schemas() -> None:
    payload = _group_evidence_patch_payload()
    assert TrajectoryGroupEvidencePatch.model_validate(payload).card["schema_version"] == 4

    legacy_outer = _group_evidence_patch_payload()
    legacy_outer["schema_version"] = 3
    with pytest.raises(ValidationError, match="Input should be 4"):
        TrajectoryGroupEvidencePatch.model_validate(legacy_outer)

    legacy_inner = _group_evidence_patch_payload()
    legacy_inner["card"]["schema_version"] = 3  # type: ignore[index]
    with pytest.raises(ValidationError, match="inner card must use schema_version 4"):
        TrajectoryGroupEvidencePatch.model_validate(legacy_inner)


def test_group_evidence_patch_rejects_full_state_agenda_and_binding_drift() -> None:
    full_state = _group_evidence_patch_payload()
    agenda = full_state["card"]["opening_inquiry_agenda"]  # type: ignore[index]
    agenda[0]["evidence_labels"] = ["public_opening_anchor:劳动合同"]  # type: ignore[index]
    with pytest.raises(ValidationError, match="agenda item 0 has invalid shape"):
        TrajectoryGroupEvidencePatch.model_validate(full_state)

    mismatched = _group_evidence_patch_payload()
    mismatched["card"]["case_id"] = "different_case"  # type: ignore[index]
    with pytest.raises(ValidationError, match="inner/outer binding mismatch: case_id"):
        TrajectoryGroupEvidencePatch.model_validate(mismatched)


def _playbook_map_card(group_id: str, *, status: str = "process_tied") -> dict[str, object]:
    return {
        "group_id": group_id,
        "case_id": f"case_{group_id}",
        "domain": "contract_commercial",
        "group_relative_status": status,
        "trajectory_summaries": [
            {"trajectory_id": f"{group_id}.trajectory_{index}"} for index in range(4)
        ],
    }


def test_playbook_map_explicitly_accounts_for_every_group() -> None:
    client = FakeTeacherClient(
        {
            "package_id": "map_01",
            "modes": [
                {
                    "mode_type": "failure",
                    "mechanism": "连续追问客户不可获得的信息会产生无收益回合",
                    "observable_context": "前一目标已经得到无法回答的回应",
                    "actionable_lesson": "转向客户本人经历且尚未询问的事实维度",
                    "risky_actions_to_avoid": ["换一种措辞继续追问同一未知信息"],
                    "source_group_ids": ["group_1"],
                    "evidence_limitations": ["只观察到共同失败，未观察到正向策略"],
                }
            ],
            "no_new_mode_group_ids": ["group_3", "group_2"],
        }
    )
    teacher = SkillTeacher(
        client=client,
        prompt_path=Path(__file__).resolve().parents[2] / "configs/prompts/skill_teacher_zh.txt",
        baseline_policy_paths=[
            Path(__file__).resolve().parents[2] / "configs/prompts/consultation_policy_zh.txt",
        ],
    )

    evidence_cards = [
        _playbook_map_card("group_1"),
        _playbook_map_card("group_2"),
        _playbook_map_card("group_3"),
    ]
    artifact = teacher.extract_playbook_modes(
        package_id="map_01",
        evidence_cards=evidence_cards,
        current_playbook=None,
    )

    assert artifact.schema_version == 2
    assert json.loads(client.user_prompt)["current_playbook"] is None
    assert artifact.input_binding_sha256 == playbook_map_input_binding_sha256(
        package_id="map_01",
        evidence_cards=evidence_cards,
        current_playbook=None,
    )
    assert artifact.input_binding_sha256 == playbook_map_input_binding_sha256(
        package_id="map_01",
        evidence_cards=json.loads(client.user_prompt)["group_evidence_cards"],
        current_playbook=None,
    )
    assert artifact.source_group_ids == ["group_1", "group_2", "group_3"]
    assert artifact.no_new_mode_group_ids == ["group_3", "group_2"]
    assert artifact.modes[0].source_group_ids == ["group_1"]

    legacy = artifact.model_dump(mode="json")
    legacy["schema_version"] = 1
    with pytest.raises(ValidationError, match="Input should be 2"):
        PlaybookModeArtifact.model_validate(legacy)

    changed_cards = json.loads(json.dumps(evidence_cards))
    changed_cards[0]["case_id"] = "different_case"
    assert artifact.input_binding_sha256 != playbook_map_input_binding_sha256(
        package_id="map_01",
        evidence_cards=changed_cards,
        current_playbook=None,
    )


def test_playbook_map_request_and_binding_include_the_exact_parent_playbook() -> None:
    client = FakeTeacherClient(
        {
            "package_id": "map_parent_bound",
            "modes": [],
            "no_new_mode_group_ids": ["group_1"],
        }
    )
    teacher = SkillTeacher(
        client=client,
        prompt_path=Path(__file__).resolve().parents[2] / "configs/prompts/skill_teacher_zh.txt",
        baseline_policy_paths=[
            Path(__file__).resolve().parents[2] / "configs/prompts/consultation_policy_zh.txt",
        ],
    )
    parent = prompt_skill(
        skill_id=PLAYBOOK_SKILL_ID,
        domain="general",
        status="active",
    )
    cards = [_playbook_map_card("group_1")]

    artifact = teacher.extract_playbook_modes(
        package_id="map_parent_bound",
        evidence_cards=cards,
        current_playbook=parent,
    )

    request = json.loads(client.user_prompt)
    assert request["schema_version"] == 2
    assert request["current_playbook"]["skill_id"] == PLAYBOOK_SKILL_ID
    assert request["current_playbook"]["version"] == parent.version
    assert request["current_playbook"]["procedure"] == parent.procedure
    assert "provenance" not in request["current_playbook"]
    assert artifact.input_binding_sha256 == playbook_map_input_binding_sha256(
        package_id="map_parent_bound",
        evidence_cards=cards,
        current_playbook=parent,
    )

    next_version = parent.model_copy(update={"version": "1.0.1"})
    changed_document = parent.model_copy(
        update={"procedure": [*parent.procedure, "先核实当前可回答的事实属性"]}
    )
    assert artifact.input_binding_sha256 != playbook_map_input_binding_sha256(
        package_id="map_parent_bound",
        evidence_cards=cards,
        current_playbook=next_version,
    )
    assert artifact.input_binding_sha256 != playbook_map_input_binding_sha256(
        package_id="map_parent_bound",
        evidence_cards=cards,
        current_playbook=changed_document,
    )


def test_playbook_map_cannot_silently_ignore_a_group() -> None:
    client = FakeTeacherClient(
        {
            "package_id": "map_01",
            "modes": [],
            "no_new_mode_group_ids": ["group_1"],
        }
    )
    teacher = SkillTeacher(
        client=client,
        prompt_path=Path(__file__).resolve().parents[2] / "configs/prompts/skill_teacher_zh.txt",
        baseline_policy_paths=[
            Path(__file__).resolve().parents[2] / "configs/prompts/consultation_policy_zh.txt",
        ],
    )

    with pytest.raises(TeacherProtocolError, match="account for every source group"):
        teacher.extract_playbook_modes(
            package_id="map_01",
            evidence_cards=[_playbook_map_card("group_1"), _playbook_map_card("group_2")],
            current_playbook=None,
        )


def test_playbook_patch_changes_only_the_declared_clause() -> None:
    current = prompt_skill(
        skill_id=PLAYBOOK_SKILL_ID,
        domain="general",
        status="active",
    )
    old_procedure = list(current.procedure)
    patch = PlaybookPatchDraft.model_validate(
        {
            "package_id": "reduce_01",
            "synthesis_summary": "来源轨迹支持把低收益追问改为转向客户可回答的经历事实。",
            "operations": [
                {
                    "operation": "REPLACE",
                    "field": "procedure",
                    "target": old_procedure[1],
                    "value": "遇到不可回答后，转向尚未询问且客户本人经历的事实",
                    "source_group_ids": ["group_1"],
                    "rationale": "共同失败显示继续追问相同未知信息不会增加事实。",
                }
            ],
            "noop_reason": None,
        }
    )

    fields, issues = _apply_playbook_patch(current, patch)

    assert issues == []
    assert fields["procedure"][0] == old_procedure[0]
    assert fields["procedure"][1] != old_procedure[1]
    assert fields["question_guidance"] == current.question_guidance
    assert fields["contraindications"] == current.contraindications
    assert fields["failure_modes"] == current.failure_modes


def test_playbook_patch_schema_keeps_initial_creation_broad_but_updates_local() -> None:
    initial = _playbook_patch_output_schema(
        package_id="reduce_initial",
        maximum_operations=INITIAL_PLAYBOOK_MAX_PATCH_OPERATIONS,
    )
    update = _playbook_patch_output_schema(
        package_id="reduce_update",
        maximum_operations=EXISTING_PLAYBOOK_MAX_PATCH_OPERATIONS,
    )

    assert initial["properties"]["operations"]["maxItems"] == 8
    assert update["properties"]["operations"]["maxItems"] == 2


def test_playbook_teacher_interface_exposes_only_the_fixed_global_document() -> None:
    interface = playbook_interface_catalog()

    assert set(interface) == {
        "schema_version",
        "fixed_playbook_identity",
        "editable_fields",
        "patch_operation_capacity",
    }
    assert interface["fixed_playbook_identity"] == {
        "skill_id": PLAYBOOK_SKILL_ID,
        "domain": "general",
        "objective": "fact_elicitation",
    }
    assert interface["editable_fields"] == {
        "procedure": {"maximum_items": 5, "maximum_characters_per_item": 180},
        "question_guidance": {
            "maximum_items": 4,
            "maximum_characters_per_item": 180,
        },
        "contraindications": {"maximum_items": 5, "maximum_characters_per_item": 180},
        "failure_modes": {"maximum_items": 5, "maximum_characters_per_item": 180},
    }
    assert interface["patch_operation_capacity"] == {
        "initial_creation": INITIAL_PLAYBOOK_MAX_PATCH_OPERATIONS,
        "existing_playbook_update": EXISTING_PLAYBOOK_MAX_PATCH_OPERATIONS,
    }


def test_skill_teacher_prompt_does_not_receive_the_generic_skill_catalog() -> None:
    teacher = SkillTeacher(
        client=FakeTeacherClient({}),
        prompt_path=Path(__file__).resolve().parents[2]
        / "configs/prompts/skill_teacher_zh.txt",
        baseline_policy_paths=[
            Path(__file__).resolve().parents[2]
            / "configs/prompts/consultation_policy_zh.txt",
        ],
    )

    assert "{playbook_interface_catalog}" not in teacher.prompt
    assert '"skill_domains"' not in teacher.prompt
    assert '"objectives"' not in teacher.prompt
    assert '"fixed_playbook_identity"' in teacher.prompt
    assert '"general.legal_fact_elicitation_playbook"' in teacher.prompt


def test_existing_playbook_teacher_request_binds_two_operation_local_budget() -> None:
    client = FakeTeacherClient(
        {
            "package_id": "reduce_update",
            "synthesis_summary": "本批机制已由当前手册表达，保留已有有效工作记忆。",
            "operations": [],
            "noop_reason": "正向前瞻反馈下没有来源支持的新增机制或可定位回归。",
        }
    )
    teacher = SkillTeacher(
        client=client,
        prompt_path=Path(__file__).resolve().parents[2]
        / "configs/prompts/skill_teacher_zh.txt",
        baseline_policy_paths=[
            Path(__file__).resolve().parents[2]
            / "configs/prompts/consultation_policy_zh.txt",
        ],
    )
    artifact = PlaybookModeArtifact(
        package_id="map_01",
        input_binding_sha256="c" * 64,
        request_sha256="a" * 64,
        response_sha256="b" * 64,
        teacher_model="gpt-test",
        source_group_ids=["group_1"],
        modes=[],
        no_new_mode_group_ids=["group_1"],
    )
    current = prompt_skill(
        skill_id=PLAYBOOK_SKILL_ID,
        domain="general",
        status="active",
    )

    proposal, patch = teacher.propose_playbook_update(
        package_id="reduce_update",
        evidence_cards=[_playbook_map_card("group_1")],
        mode_artifacts=[artifact],
        current_playbook=current,
        library_feedback={"status": "primary_endpoint_nonnegative"},
    )

    assert patch.operations == []
    assert proposal.parse_status == "valid_noop"
    assert client.output_schema is not None
    assert client.output_schema["properties"]["operations"]["maxItems"] == 2
    assert client.user_prompt is not None
    assert json.loads(client.user_prompt)["maximum_patch_operations"] == 2

    reduce_binding = playbook_reduce_input_binding_sha256(
        package_id="reduce_update",
        mode_artifacts=[artifact],
        current_playbook=current,
        library_feedback={"status": "primary_endpoint_nonnegative"},
        maximum_operations=EXISTING_PLAYBOOK_MAX_PATCH_OPERATIONS,
    )
    reduce_artifact = PlaybookReduceArtifact(
        package_id="reduce_update",
        input_binding_sha256=reduce_binding,
        proposal=proposal,
        patch=patch,
    )
    assert reduce_artifact.schema_version == 2
    legacy_reduce = reduce_artifact.model_dump(mode="json")
    legacy_reduce["schema_version"] = 1
    with pytest.raises(ValidationError, match="Input should be 2"):
        PlaybookReduceArtifact.model_validate(legacy_reduce)
    assert reduce_binding != playbook_reduce_input_binding_sha256(
        package_id="reduce_update",
        mode_artifacts=[artifact],
        current_playbook=current,
        library_feedback={"status": "primary_endpoint_negative"},
        maximum_operations=EXISTING_PLAYBOOK_MAX_PATCH_OPERATIONS,
    )


@pytest.mark.parametrize(
    ("value", "expected_issue"),
    [
        (
            "1. 先确认主体。2. 再追问行为。3. 最后核对证据。",
            "operation_0:embedded_numbered_list",
        ),
        (
            "不要追问法律结论；不要重复已有事实；不要要求客户猜测第三方记录",
            "operation_0:multiple_semicolon_clauses",
        ),
    ],
)
def test_playbook_patch_rejects_packed_mini_documents(
    value: str,
    expected_issue: str,
) -> None:
    patch = PlaybookPatchDraft.model_validate(
        {
            "package_id": "reduce_atomicity",
            "synthesis_summary": "来源轨迹支持一条可独立替换的局部规则，而不是内嵌规则清单。",
            "operations": [
                {
                    "operation": "ADD",
                    "field": "procedure",
                    "target": None,
                    "value": value,
                    "source_group_ids": ["group_1"],
                    "rationale": "保持每个文档条款可在后续块中独立替换，避免连带遗忘。",
                }
            ],
            "noop_reason": None,
        }
    )

    _, issues = _apply_playbook_patch(None, patch)

    assert expected_issue in issues


def test_static_validation_rejects_retired_runtime_language() -> None:
    candidate = prompt_skill()
    candidate.procedure = ["读取 candidate_action 后执行 replace_target"]
    issues = validate_skill_static(candidate)
    assert "retired_runtime_language:candidate_action" in issues
    assert "retired_runtime_language:replace_target" in issues


def test_registry_freeze_is_immutable_and_can_rollback(tmp_path: Path) -> None:
    repository_root = Path(__file__).resolve().parents[2]
    registry = SkillRegistry(tmp_path / "versions")
    registry.freeze(
        "v0.1.0",
        repository_root / "skills/bootstrap",
        parent_version=None,
        evidence={"tests": "pass"},
    )
    registry.activate("v0.1.0")
    registry.freeze(
        "v0.2.0",
        repository_root / "skills/bootstrap",
        parent_version="v0.1.0",
        evidence={"audit": "pass"},
    )
    registry.activate("v0.2.0")
    pointer = registry.rollback()
    assert pointer["version"] == "v0.1.0"
