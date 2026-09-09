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
    parse_diagnosis,
)
from legal_skill_guard.evolution.reward import (
    RewardComponents,
    RewardParameters,
    balanced_elicitation,
    proposed_final_was_redirected,
    trajectory_reward,
)
from legal_skill_guard.evolution.teacher import (
    SkillTeacher,
    _compact_batch_teacher_state,
    _schema_invalid_proposal,
    candidate_batch_source_grounding_issues,
    candidate_context_scope_issues,
    candidate_overlap_issues,
    candidate_source_grounding_issues,
    select_teacher_evidence_clusters,
    teacher_evidence_cluster_summaries,
)
from legal_skill_guard.schemas.action import ActionDecision, StructuredAction
from legal_skill_guard.schemas.skill import SkillContract
from legal_skill_guard.schemas.state import ConsultationState, FactSlot, Interaction, StatePatch
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
        action_type="final", target_type="none", content=""
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
        attempted_cluster_ids={"already_attempted"},
        budget=1,
    )

    assert selected[0][0]["cluster_id"] == "unseen_target_choice"


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
    assert proposal.schema_version == 2
    assert proposal.parse_status == "invalid_candidate"
    assert proposal.usable_candidate is None
    assert proposal.source_witness is None


def test_source_witness_accepts_document_without_executable_replay() -> None:
    group, selection, trajectories = causal_contrast()
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
        diagnosis, [(group, selection, trajectories)]
    )
    assert issues == []
    assert supported == [group.group_id]


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
    assert one_issues == many_issues == []
    assert one_supported == [first_group.group_id]
    assert many_supported == [first_group.group_id, second_group.group_id]


def test_source_witness_allows_independent_state_but_rejects_wrong_objective() -> None:
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
    assert issues == ["source_failure_objective_mismatch"]


def test_clusters_allow_local_hypothesis_but_require_cross_domain_generalization() -> None:
    first = causal_contrast("labor_a", "labor_employment")
    summaries = teacher_evidence_cluster_summaries([first])
    general = next(item for item in summaries if item["evidence_scope"] == "general")
    scoped = next(item for item in summaries if item["evidence_scope"] == "labor_employment")
    assert general["eligible"] is False
    assert scoped["eligible"] is True
    assert scoped["ineligible_reason"] is None
    assert scoped["behavior_family"] == "continue_inquiry"

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


def test_cluster_labels_same_target_different_question_as_formulation() -> None:
    precise = StructuredAction(
        action_type="ask",
        target_type="fact",
        target_id="F2",
        expected_information="双方实际关系形成的具体经过",
        content="双方的实际关系是通过什么具体经过形成的？",
    )
    vague = StructuredAction(
        action_type="ask",
        target_type="fact",
        target_id="F2",
        expected_information="双方关系情况",
        content="你们之间是什么情况？",
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
    summaries = teacher_evidence_cluster_summaries([contrast, second_contrast])

    scoped = next(item for item in summaries if item["evidence_scope"] == "labor_employment")
    assert scoped["eligible"] is True
    assert scoped["behavior_family"] == "question_formulation"


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
        attempted_cluster_ids=set(),
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
        attempted_cluster_ids=set(),
        budget=1,
    )
    assert selected[0][0]["cluster_id"] == "smaller_durable_target_cluster"


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
        attempted_cluster_ids=set(),
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
        attempted_cluster_ids=set(),
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
        attempted_cluster_ids=set(),
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
        attempted_cluster_ids=set(),
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

    def generate_json(self, **kwargs):
        self.output_schema = kwargs["output_schema"]
        self.system_prompt = kwargs["system_prompt"]
        return SimpleNamespace(
            value=self.value,
            model=self.model,
            request_sha256="a" * 64,
            response_sha256="b" * 64,
        )


def test_teacher_authors_only_document_and_system_binds_source_witness() -> None:
    group, selection, trajectories = causal_contrast()
    second_group, second_selection, second_trajectories = causal_contrast(
        "case_b", "labor_employment"
    )
    draft = prompt_skill(domain="labor_employment").model_dump(mode="json", exclude={"provenance"})
    value = {
        "group_id": group.group_id,
        "failure_state": {"turn": 1, "relevant_fields": ["visible_fact_plan"]},
        "behavior_difference": {
            "positive_action": "继续询问一个尚未说明的关系事实",
            "negative_action": "在相同可见状态下直接结束咨询",
        },
        "causal_hypothesis": "具体追问关系可能增加有效事实，尚需下一未见训练块检验。",
        "proposed_change": "CREATE",
        "skill_scope": "labor_employment",
        "known_risks": ["客户可能确实不了解该关系"],
        "candidate_skill": draft,
    }
    client = FakeTeacherClient(value)
    teacher = SkillTeacher(
        client=client,
        prompt_path=Path(__file__).resolve().parents[2] / "configs/prompts/skill_teacher_zh.txt",
        baseline_policy_paths=[
            Path(__file__).resolve().parents[2] / "configs/prompts/consultation_planner_zh.txt",
            Path(__file__).resolve().parents[2] / "configs/prompts/consultation_policy_zh.txt",
        ],
    )
    proposal = teacher.propose_batch(
        batch_id=group.group_id,
        contrasts=[
            (group, selection, trajectories),
            (second_group, second_selection, second_trajectories),
        ],
        evaluations={},
        existing_skills=[],
        runtime_skills=[],
    )
    assert proposal.parse_status == "valid_candidate"
    assert proposal.source_witness is not None
    assert proposal.source_witness.forks[0].visible_state_sha256
    candidate = proposal.usable_candidate
    assert candidate is not None
    assert candidate.provenance.source_case_ids == ["case_a", "case_b"]
    assert candidate.provenance.generator_model == "gpt-test"
    schema_text = str(client.output_schema)
    assert "provenance" not in schema_text
    assert "evaluation" not in schema_text
    assert "preconditions" not in schema_text
    assert "operation" not in schema_text
    assert client.system_prompt is not None
    assert '"initial_plan"' in client.system_prompt
    assert '"steps"' in client.system_prompt
    assert '"client_response"' in client.system_prompt
    assert "客户补充了关系事实" in client.system_prompt


def test_teacher_history_exposes_status_and_document_but_not_private_outcomes() -> None:
    client = FakeTeacherClient({})
    teacher = SkillTeacher(
        client=client,
        prompt_path=Path(__file__).resolve().parents[2] / "configs/prompts/skill_teacher_zh.txt",
        baseline_policy_paths=[
            Path(__file__).resolve().parents[2] / "configs/prompts/consultation_planner_zh.txt",
            Path(__file__).resolve().parents[2] / "configs/prompts/consultation_policy_zh.txt",
        ],
    )
    historical = prompt_skill()
    historical.status = "rejected"
    historical.provenance.source_case_ids = ["private-case"]

    prompt = teacher._system_prompt(
        existing_skills=[historical],
        contrast_payload={},
    )

    assert '"status": "rejected"' in prompt
    assert historical.description in prompt
    assert "private-case" not in prompt
    assert "mean_delta_reward" not in prompt
    assert '"provenance"' not in prompt
    assert "consultation_planner_zh.txt" in prompt
    assert "consultation_policy_zh.txt" in prompt
    assert "{baseline_policy_contract}" not in prompt
    assert "{method_guidance}" not in prompt
    assert "当前工作库没有适用咨询技能文档" in prompt


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
