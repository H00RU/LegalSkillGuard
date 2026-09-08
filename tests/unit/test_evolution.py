from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from legal_skill_guard.evolution.acceptance import (
    AcceptanceThresholds,
    PairOutcome,
    decide_skill,
    global_regression_passes,
    mechanism_direction_gate,
)
from legal_skill_guard.evolution.advantage import (
    AdvantageGroup,
    CausalEvidencePatch,
    ContrastSelection,
    ScoredMember,
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
            "evaluation": {},
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
        steps=[step(positive_action, ["F2"])],
    )
    low = SimpleNamespace(
        trajectory_id=low_id,
        case_id=case_id,
        domain=domain,
        persona="P_WD",
        status="memo_submitted",
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


def test_history_blocks_exact_rename_and_live_general_blocks_domain_copy() -> None:
    rejected = prompt_skill(status="rejected")
    renamed = rejected.model_copy(update={"skill_id": "fact_elicitation.renamed"})
    issues = candidate_overlap_issues(
        renamed, historical_skills=[rejected], runtime_skills=[]
    )
    assert f"structural_duplicate:{rejected.skill_id}" in issues

    active = rejected.model_copy(update={"status": "active"})
    domain_copy = active.model_copy(
        update={"skill_id": "fact_elicitation.labor_copy", "domain": "labor_employment"}
    )
    issues = candidate_overlap_issues(
        domain_copy, historical_skills=[active], runtime_skills=[active]
    )
    assert f"scope_redundancy:{active.skill_id}" in issues


def _minimal_causal_patch_payload() -> dict[str, object]:
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
        "schema_version": 2,
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


def test_causal_patch_rejects_legacy_schema_and_implicit_signal_family() -> None:
    payload = _minimal_causal_patch_payload()
    assert CausalEvidencePatch.model_validate(payload).selection.signal_family == (
        "fact_elicitation"
    )
    legacy = dict(payload)
    legacy["schema_version"] = 1
    with pytest.raises(ValueError, match="Input should be 2"):
        CausalEvidencePatch.model_validate(legacy)
    implicit = dict(payload)
    implicit["selection"] = {"highest_id": "high", "lowest_id": "low"}
    with pytest.raises(ValueError, match="explicit signal_family"):
        CausalEvidencePatch.model_validate(implicit)


def acceptance_thresholds(**updates) -> AcceptanceThresholds:
    values = {
        "minimum_exposed_pairs": 10,
        "minimum_exposed_cases": 1,
        "minimum_exposed_domains": 1,
        "minimum_mean_delta": 0.02,
        "minimum_material_harm_delta": 0.02,
        "maximum_harmful_pair_rate": 0.15,
    }
    values.update(updates)
    return AcceptanceThresholds.model_validate(values)


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


def outcomes(
    count: int,
    delta: float,
    *,
    harmful: int = 0,
    severe: bool = False,
    unsupported: float = 0,
) -> list[PairOutcome]:
    values = []
    for index in range(count):
        pair_delta = -0.03 if index < harmful else delta
        values.append(
            PairOutcome(
                pair_id=str(index),
                exposed=True,
                reward_without=0.4,
                reward_with=0.4 + pair_delta,
                severe_risk_with=severe and index == 0,
                unsupported_claim_delta=unsupported,
            )
        )
    return values


def test_acceptance_paths_and_safety_fail_closed() -> None:
    limits = acceptance_thresholds()
    assert decide_skill(outcomes(5, 0.1), limits).decision == "DEFER"
    assert decide_skill(outcomes(10, -0.01), limits).decision == "REJECT"
    assert decide_skill(outcomes(10, 0.1, harmful=2), limits).decision == "REJECT"
    assert decide_skill(outcomes(10, 0.1), limits).decision == "ACCEPT"
    assert decide_skill(outcomes(10, 0.1, severe=True), limits).decision == "REJECT"
    assert decide_skill(outcomes(10, 0.1, unsupported=0.01), limits).decision == "REJECT"


def test_sparse_positive_defers_but_observed_risk_rejects() -> None:
    sparse = outcomes(2, 0.1)
    assert decide_skill(sparse, acceptance_thresholds()).decision == "DEFER"
    sparse[0].client_fallback_delta = 1.0
    assert decide_skill(sparse, acceptance_thresholds()).decision == "REJECT"


def test_safety_regression_cannot_be_cancelled_by_another_pair() -> None:
    values = outcomes(2, 0.1)
    for index, item in enumerate(values):
        item.case_id = f"case_{index}"
        item.domain = f"domain_{index}"
    values[0].unsupported_claim_delta = 1.0
    values[1].unsupported_claim_delta = -1.0

    decision = decide_skill(
        values,
        acceptance_thresholds(
            minimum_exposed_pairs=2,
            minimum_exposed_cases=2,
            minimum_exposed_domains=2,
            minimum_mean_delta=0.0,
        ),
    )

    assert decision.unsupported_claim_delta == 0.0
    assert decision.decision == "REJECT"
    assert decision.reason == "positive_mean_but_risk_or_harmful_tail"


def test_acceptance_requires_independent_case_and_domain_coverage() -> None:
    repeated = outcomes(12, 0.1)
    for item in repeated:
        item.case_id = "case_a"
        item.domain = "labor"
    limits = acceptance_thresholds(
        minimum_exposed_pairs=8,
        minimum_exposed_cases=3,
        minimum_exposed_domains=2,
    )
    assert decide_skill(repeated, limits).decision == "DEFER"
    independent = outcomes(12, 0.1)
    for index, item in enumerate(independent):
        item.case_id = f"case_{index % 3}"
        item.domain = "labor" if index % 2 else "contract"
    assert decide_skill(independent, limits).decision == "ACCEPT"


@pytest.mark.parametrize(
    ("family", "fact_delta", "gap_delta", "question_delta", "passed"),
    [
        ("fact_elicitation", 1.0, 0.0, 1.0, True),
        ("fact_elicitation", 0.0, 1.0, 1.0, False),
        ("evidence_gap_identification", 0.0, 1.0, 1.0, True),
        ("evidence_gap_identification", 1.0, 0.0, 1.0, False),
        ("safe_stop", 0.0, 0.0, -1.0, True),
        ("safe_stop", 0.0, 0.0, 0.0, False),
    ],
)
def test_mechanism_direction_gate_requires_claimed_effect(
    family: str,
    fact_delta: float,
    gap_delta: float,
    question_delta: float,
    passed: bool,
) -> None:
    values = outcomes(4, 0.1)
    for index, item in enumerate(values):
        item.case_id = f"case_{index % 2}"
        item.newly_elicited_fact_delta = fact_delta
        item.identified_evidence_gap_delta = gap_delta
        item.question_turn_delta = question_delta
    assert mechanism_direction_gate(values, family).passed is passed  # type: ignore[arg-type]


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


def test_source_witness_rejects_nonshared_state_and_wrong_objective() -> None:
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
    assert "source_grounding_not_a_shared_visible_state" in issues


def test_clusters_allow_local_hypothesis_but_require_cross_domain_generalization() -> None:
    first = causal_contrast("labor_a", "labor_employment")
    summaries = teacher_evidence_cluster_summaries([first])
    general = next(item for item in summaries if item["evidence_scope"] == "general")
    scoped = next(item for item in summaries if item["evidence_scope"] == "labor_employment")
    assert general["eligible"] is False
    assert scoped["eligible"] is True
    assert scoped["behavior_family"] == "continue_inquiry"

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

    summaries = teacher_evidence_cluster_summaries([contrast])

    scoped = next(
        item for item in summaries if item["evidence_scope"] == "labor_employment"
    )
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
    draft = prompt_skill(domain="labor_employment").model_dump(
        mode="json", exclude={"provenance", "evaluation"}
    )
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
        prompt_path=Path(__file__).resolve().parents[2]
        / "configs/prompts/skill_teacher_zh.txt",
    )
    proposal = teacher.propose_batch(
        batch_id=group.group_id,
        contrasts=[(group, selection, trajectories)],
        evaluations={},
        existing_skills=[],
        runtime_skills=[],
    )
    assert proposal.parse_status == "valid_candidate"
    assert proposal.source_witness is not None
    assert proposal.source_witness.forks[0].visible_state_sha256
    candidate = proposal.usable_candidate
    assert candidate is not None
    assert candidate.provenance.source_case_ids == ["case_a"]
    assert candidate.provenance.generator_model == "gpt-test"
    schema_text = str(client.output_schema)
    assert "provenance" not in schema_text
    assert "evaluation" not in schema_text
    assert "preconditions" not in schema_text
    assert "operation" not in schema_text


def test_teacher_history_exposes_status_and_document_but_not_private_outcomes() -> None:
    client = FakeTeacherClient({})
    teacher = SkillTeacher(
        client=client,
        prompt_path=Path(__file__).resolve().parents[2]
        / "configs/prompts/skill_teacher_zh.txt",
    )
    historical = prompt_skill()
    historical.status = "rejected"
    historical.evaluation.mean_delta_reward = -0.4
    historical.provenance.source_case_ids = ["private-case"]

    prompt = teacher._system_prompt(
        existing_skills=[historical],
        prior_validation_feedback=[],
        contrast_payload={},
    )

    assert '"status": "rejected"' in prompt
    assert historical.description in prompt
    assert "private-case" not in prompt
    assert "mean_delta_reward" not in prompt
    assert '"provenance"' not in prompt


def test_diagnosis_quality_does_not_claim_unseen_efficacy() -> None:
    candidate = prompt_skill()
    candidate.evaluation.mean_delta_reward = 0.2
    diagnosis = SkillDiagnosis(
        group_id="g",
        failure_state=FailureState(turn=1),
        behavior_difference=BehaviorDifference(
            positive_action="询问尚未明确的事实关系",
            negative_action="直接结束当前咨询过程",
        ),
        causal_hypothesis="具体追问可能增加事实信息，仍需下一块确认。",
        proposed_change="CREATE",
        skill_scope="general",
        candidate_skill=candidate,
    )
    assert "teacher_claimed_unseen_evaluation" in diagnosis_quality_issues(diagnosis)


def test_static_validation_rejects_retired_runtime_language() -> None:
    candidate = prompt_skill()
    candidate.procedure = ["读取 candidate_action 后执行 replace_target"]
    issues = validate_skill_static(candidate)
    assert "retired_runtime_language:candidate_action" in issues
    assert "retired_runtime_language:replace_target" in issues


def test_global_regression_gate() -> None:
    assert global_regression_passes(0.5, 0.49, maximum_drop=0.01)
    assert not global_regression_passes(0.5, 0.48, maximum_drop=0.01)


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
    if not global_regression_passes(0.5, 0.47, maximum_drop=0.01):
        pointer = registry.rollback()
    assert pointer["version"] == "v0.1.0"
