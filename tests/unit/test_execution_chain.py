from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from legal_skill_guard.agent.state_manager import StateManager
from legal_skill_guard.agent.stateful_policy import atomic_factual_target_projection
from legal_skill_guard.environment.dlawbench_adapter import DLawBenchAdapter
from legal_skill_guard.evaluation.qualification import semantic_judge_qualification_sha256
from legal_skill_guard.evaluation.semantic import (
    SemanticEvaluator,
    _belief_as_fact_rate,
    build_fact_judgment_prompt,
    build_official_grounding_judgment_prompt,
    chunk_claim_spans,
    fact_judgment_schema,
    fact_wire_contract_issues,
    grounding_judgment_schema,
    grounding_wire_contract_issues,
    memo_claim_spans,
    monotone_expected_action_scores,
    normalize_exact_visible_grounding,
    normalize_official_grounding_contract,
    official_grounding_judgment_schema,
    parse_fact_judgment,
    parse_grounding_judgment,
    parse_official_grounding_judgment,
    policy_fallback_used,
    rubric_judgment_schema,
)
from legal_skill_guard.evaluation.statistics import (
    PairedEstimate,
    benjamini_hochberg,
    clustered_mean_deltas,
    paired_bootstrap_interval,
    paired_sign_flip_p_value,
)
from legal_skill_guard.evolution.acceptance import (
    AuditDecision,
    MechanismDirectionGate,
    PairOutcome,
)
from legal_skill_guard.evolution.diagnosis import SkillDiagnosis
from legal_skill_guard.evolution.reward import RewardParameters
from legal_skill_guard.evolution.teacher import (
    SourceForkWitness,
    SourceWitness,
    TeacherProposal,
)
from legal_skill_guard.experiment.batches import load_training_batch_plan
from legal_skill_guard.experiment.executor import (
    ExecutionError,
    MainExperimentExecutor,
    ProspectiveCandidateAudit,
    TrainingSummary,
    _teacher_proposal_matches_candidate,
    _validate_persona_seed_protocol,
    candidate_pair_health_selection,
    fresh_candidate_nomination_slots,
    paired_behavior_estimates,
    parallel_map_ordered,
    prospective_audit_teacher_feedback,
    prospective_exposure_minima,
    require_distinct_learning_traces,
    select_causally_aligned_contrast,
    select_causally_aligned_contrasts,
    select_diverse_teacher_groups,
    skill_contract_definition_sha256,
    skill_document_semantic_sha256,
    skill_library_sha256,
    teacher_response_cache_root,
    tf_grpo_teacher_evidence_groups,
    trajectory_behavior_summary,
    trajectory_learning_signature,
    verify_model_manifest,
)
from legal_skill_guard.experiment.runner import (
    INVESTIGATION_PLAN_SCHEMA,
    InvestigationPlanningError,
    TrajectoryRunner,
    asks_response_event_existence,
    counterfactual_followup_target,
    counterfactual_initial_target,
    counterfactual_target_guidance,
    parse_investigation_plan,
    planner_target_has_recoverable_observable_core,
    policy_sampling_seed,
    policy_stream_index,
    response_event_terms_in,
    shared_component_seed,
    termination_contract_check,
    uses_counterfactual_target_allocation,
)
from legal_skill_guard.experiment.storage import RunStore, trajectory_identity
from legal_skill_guard.experiment.trajectory_health import trajectory_health_report
from legal_skill_guard.inference.codex_cli_client import (
    CodexCLIClient,
    CodexInvocationError,
    run_process_tree,
    strict_output_schema,
    strict_output_schema_issues,
)
from legal_skill_guard.inference.openai_client import (
    ChatResponse,
    GenerationConfig,
    ReplayCachedChatClient,
)
from legal_skill_guard.inference.structured_openai_client import (
    StructuredModelInvocationError,
)
from legal_skill_guard.schemas.experiment import (
    ResearchTrajectory,
    assert_current_trajectory_contract,
    current_trajectory_contract_issues,
)
from legal_skill_guard.schemas.state import FactObservation, FactSlot, Interaction, StatePatch
from legal_skill_guard.schemas.trajectory import Message
from legal_skill_guard.skills.memory import (
    extract_rendered_skill_memory,
    parse_rendered_skill_memory,
    render_skill_memory,
)
from legal_skill_guard.skills.registry import SkillRegistry
from legal_skill_guard.utils.hashing import canonical_json_sha256
from tests.skill_fixtures import synthetic_skills

TEST_REWARD_PARAMETERS = RewardParameters(
    elicitation_weight=0.45,
    resolution_weight=0.45,
    fidelity_weight=0.10,
    extra_turn_penalty=0.02,
    repeated_question_penalty=0.05,
    premature_final_cap=0.35,
    unsupported_claim_cap=0.25,
    hidden_field_leak_reward=0.0,
)


class ScriptedChatClient:
    def __init__(self, responses: list[str], model: str = "test-model") -> None:
        self.model = model
        self.responses = list(responses)
        self.seen: list[list[dict[str, str]]] = []
        self.generations: list[GenerationConfig] = []

    def is_ready(self) -> bool:
        return True

    def generate(self, messages, generation):
        self.seen.append(messages)
        self.generations.append(generation)
        system = str(messages[0].get("content") or "") if messages else ""
        if "O编号是开场已公开陈述" in system and "：- O" in system and "\n- F" not in system:
            return ChatResponse(
                content='{"fact_ids":[]}',
                finish_reason="stop",
                prompt_tokens=10,
                completion_tokens=5,
                raw_id="test-opening-pass",
            )
        return ChatResponse(
            content=self.responses.pop(0),
            finish_reason="stop",
            prompt_tokens=10,
            completion_tokens=5,
            raw_id="test",
        )


def _policy(action: dict, observations: list[dict]) -> str:
    return json.dumps(
        {
            "state_patch": {
                "observations": observations,
                "issue_labels": [],
                "risk_flags_add": [],
            },
            "action": {
                "target_type": "fact" if action["action_type"] != "final" else "session",
                "target_id": action.get("target_id"),
                "reason": "test",
                "expected_information": "可观察事实",
                "content": action.get("content", ""),
                "constraints": [],
                "confidence": 0.8,
                **{"action_type": action["action_type"]},
            },
        },
        ensure_ascii=False,
    )


def _case() -> dict:
    return {
        "id": "case_test",
        "jurisdiction": "CN",
        "language": "zh",
        "opening": "我与对方签了合同，现在对履行情况有争议。",
        "facts": [
            {
                "fact_id": "F1",
                "client_belief": "合同签署日期是2025年1月2日。",
                "court_record": "合同落款日期为2025年1月2日。",
                "gap_type": "aligned",
            },
            {
                "fact_id": "F2",
                "client_belief": "对方在2025年2月书面拒绝继续履行。",
                "court_record": "2025年2月的邮件载有拒绝履行内容。",
                "gap_type": "aligned",
            },
        ],
        "evaluation_criteria": {
            "expected_inquiries": ["询问合同日期和拒绝履行文件"],
            "memo_expectations": ["区分客户陈述与待核文件"],
        },
    }


def _runner() -> tuple[TrajectoryRunner, ScriptedChatClient, ScriptedChatClient]:
    unknowns = [
        {
            "fact_id": "F1",
            "label": "合同签署日期",
            "status": "unknown",
            "value": None,
            "evidence_labels": [],
            "confidence": 0.5,
            "criticality": "medium",
            "target_kind": "client_fact",
        },
        {
            "fact_id": "F2",
            "label": "拒绝履行书面内容",
            "status": "unknown",
            "value": None,
            "evidence_labels": [],
            "confidence": 0.5,
            "criticality": "medium",
            "target_kind": "client_fact",
        },
    ]
    policy = ScriptedChatClient(
        [
            _policy(
                {"action_type": "ask", "target_id": "F1", "content": "合同是哪天签署的？"},
                unknowns,
            ),
            _policy(
                {
                    "action_type": "ask",
                    "target_id": "F2",
                    "content": "对方是否通过书面文件明确拒绝继续履行？",
                },
                [
                    {
                        **unknowns[0],
                        "status": "client_claimed",
                        "value": "合同签署日期是2025年1月2日。",
                        "confidence": 0.7,
                    }
                ],
            ),
            _policy(
                {"action_type": "final", "content": "形成初步备忘录"},
                [
                    {
                        **unknowns[1],
                        "status": "client_claimed",
                        "value": "对方在2025年2月书面拒绝继续履行。",
                        "confidence": 0.7,
                    }
                ],
            ),
        ]
    )
    selector = ScriptedChatClient(
        [
            '{"fact_ids":["F1"]}',
            '{"fact_ids":["F2"]}',
        ]
    )
    memo = ScriptedChatClient(
        [
            "## 案情概要\n据客户陈述存在合同履行争议。\n"
            "## 关键事实\n客户称合同于2025年1月2日签署，对方于2025年2月书面拒绝履行。\n"
            "## 法律问题\n具体权利义务需结合合同和书面文件核实。\n"
            "## 风险评估\n现有信息尚未经独立核验，结论可能变化。\n"
            "## 下一步建议\n可先核实合同原件和拒绝履行文件。\n"
            "本分析不替代持证律师的正式意见。"
        ]
    )
    root = Path(__file__).resolve().parents[2]
    generation = GenerationConfig(temperature=0, top_p=1, max_tokens=500, seed=42)
    return (
        TrajectoryRunner(
            policy_client=policy,
            client_selector=selector,
            memo_client=memo,
            policy_prompt_path=root / "configs/prompts/consultation_policy_zh.txt",
            client_prompt_path=root / "configs/prompts/client_fact_selector_zh.txt",
            client_disclosure_prompt_path=(root / "configs/prompts/client_fact_disclosure_zh.txt"),
            memo_prompt_path=root / "configs/prompts/memo_writer_zh.txt",
            policy_generation=generation,
            client_generation=generation,
            memo_generation=generation,
            model_revision="test-revision",
            max_policy_attempts=3,
            max_client_selection_attempts=2,
            max_memo_attempts=3,
        ),
        policy,
        selector,
    )


def test_prospective_exposure_minima_respect_candidate_scope() -> None:
    policy = {
        "minimum_exposed_sessions": 4,
        "minimum_exposed_cases": 4,
        "minimum_exposed_domains": 2,
        "domain_minimum_exposed_sessions": 1,
        "domain_minimum_exposed_cases": 1,
    }
    assert prospective_exposure_minima("general", policy) == (4, 4, 2)
    assert prospective_exposure_minima("criminal", policy) == (1, 1, 1)


def test_real_multiturn_chain_stores_grounded_dialogue_without_hidden_labels() -> None:
    runner, policy, selector = _runner()
    trajectory = runner.run(
        raw_case=_case(),
        persona={
            "persona_id": "P_WD",
            "who": {"zh": "当事人"},
            "voice": {"zh": "简短"},
        },
        skills=[],
        trajectory_id="traj_test",
        run_id="run_test",
        method="training_policy_sample",
        partition="training_round_01",
        seed=42,
        sample_index=0,
        max_turns=3,
        group_id="group_test",
        skill_library_version="empty",
    )
    assert trajectory.schema_version == 16
    assert trajectory.initial_visible_state_coverage_attempts == []
    assert trajectory.initial_visible_state_covered_target_ids == []
    assert trajectory.initial_visible_state_coverage_token_usage.total == 0
    assert all(step.visible_state_coverage_attempts == [] for step in trajectory.steps)
    assert all(step.visible_state_covered_target_ids == [] for step in trajectory.steps)
    assert "state_coverage_verifier" not in runner.preflight()
    assert trajectory.status == "memo_submitted"
    assert trajectory.steps[-1].turn == 3
    assert trajectory.steps[-1].stop_gate_verdict == "PASS"
    assert trajectory.steps[-1].stop_gate_reason == "sufficient_visible_state"
    assert [step.client_selected_fact_ids for step in trajectory.steps[:2]] == [["F1"], ["F2"]]
    assert all(step.client_route_decision_valid is True for step in trajectory.steps[:2])
    serialized_trajectory = json.dumps(trajectory.model_dump(mode="json"), ensure_ascii=False)
    assert "client_route_decision_valid" in serialized_trajectory
    assert "client_relevance_attempts" not in serialized_trajectory
    assert "client_relevance_passed" not in serialized_trajectory
    assert all(name in trajectory.memo for name in ("案情概要", "关键事实", "下一步建议"))
    online_payload = json.dumps([item.seen for item in (policy, selector)], ensure_ascii=False)
    assert "court_record" not in online_payload
    assert "evaluation_criteria" not in online_payload
    assert "memo_expectations" not in online_payload
    assert all(item.response_schema is not None for item in policy.generations)
    assert all(
        item.response_schema_name == "legal_skill_guard_policy_action"
        for item in policy.generations
    )


def test_one_interaction_qualification_status_is_part_of_current_schema() -> None:
    runner, _, _ = _runner()
    trajectory = runner.run(
        raw_case=_case(),
        persona={"persona_id": "P_WD", "who": {"zh": "当事人"}, "voice": {"zh": "简短"}},
        skills=[],
        trajectory_id="diagnostic_one_turn",
        run_id="run_test",
        method="training_policy_sample",
        partition="diagnostic_training_sampling_current",
        seed=42,
        sample_index=0,
        max_turns=3,
        group_id="diagnostic_group",
        skill_library_version="empty",
        diagnostic_interaction_limit=1,
    )
    assert trajectory.schema_version == 16
    assert trajectory.status == "diagnostic_interaction_limit"
    assert len(trajectory.steps) == 1
    assert trajectory.memo == ""


def test_runner_keeps_withheld_target_open_then_records_later_disclosure() -> None:
    runner, _, _ = _runner()
    runtime_fact_id = "dialogue_fact_" + hashlib.sha256("是否伪造合同".encode()).hexdigest()[:16]
    target = {
        "fact_id": runtime_fact_id,
        "label": "是否伪造合同",
        "status": "unknown",
        "value": None,
        "evidence_labels": [],
        "confidence": 0.5,
        "criticality": "high",
        "target_kind": "client_fact",
    }
    policy = ScriptedChatClient(
        [
            _policy(
                {
                    "action_type": "ask",
                    "target_id": runtime_fact_id,
                    "content": "你是不是故意伪造了合同日期？",
                },
                [target],
            ),
            _policy(
                {
                    "action_type": "ask",
                    "target_id": runtime_fact_id,
                    "content": (
                        "我不是在预设您违法，这只用于评估证据风险；请只核对您是否伪造过合同日期。"
                    ),
                },
                [],
            ),
            _policy({"action_type": "final", "content": "形成初步备忘录"}, []),
        ]
    )
    selector = ScriptedChatClient(
        [
            '{"fact_ids":["F1"]}',
            '{"sensitive_personal_misconduct":true,"accusatory_presumption":true,'
            '"coercive_pressure":false,"purpose_explained":false}',
            '{"fact_ids":["F1"]}',
            '{"sensitive_personal_misconduct":true,"accusatory_presumption":false,'
            '"coercive_pressure":false,"purpose_explained":true}',
        ]
    )
    runner.policy_client = policy
    runner.client_selector = selector
    runner.client_disclosure_classifier = selector

    trajectory = runner.run(
        raw_case={
            **_case(),
            "facts": [
                {
                    **_case()["facts"][0],
                    "client_belief": "我曾经故意改动过合同签署日期。",
                },
                _case()["facts"][1],
            ],
        },
        persona={
            "persona_id": "P_CS",
            "who": {"zh": "起初不信任外人的客户"},
            "voice": {"zh": "简短回避"},
        },
        skills=[],
        trajectory_id="traj_withheld_then_disclosed",
        run_id="run_test",
        method="training_policy_sample",
        partition="training_round_01",
        seed=42,
        sample_index=0,
        max_turns=3,
        group_id="group_withheld",
        skill_library_version="empty",
    )

    first, second = trajectory.steps[:2]
    assert first.client_response_kind == "withheld"
    assert first.client_matched_fact_ids == ["F1"]
    assert first.client_disclosure_decisions == {"F1": "withhold"}
    assert first.client_selected_fact_ids == []
    assert "2025年1月2日" not in (first.client_response or "")
    first_state = first.state_after
    runtime_target_id = first_state["interactions"][-1]["target_id"]
    first_target = next(
        item for item in first_state["facts"] if item["fact_id"] == runtime_target_id
    )
    assert first_target["status"] == "unknown"
    assert first_state["asked_targets"] == []
    assert first_state["interactions"][-1]["response_kind"] == "withheld"

    assert second.client_response_kind == "new_hidden_fact"
    assert second.client_matched_fact_ids == ["F1"]
    assert second.client_disclosure_decisions == {"F1": "disclose"}
    assert second.client_selected_fact_ids == ["F1"]
    second_target = next(
        item for item in second.state_after["facts"] if item["fact_id"] == runtime_target_id
    )
    assert second_target["status"] == "client_claimed"
    assert second.state_after["asked_targets"] == [runtime_target_id]
    # Fact routing is intentionally history-invariant; resistance history is
    # represented by disclosure state, not by changing the semantic question.
    second_selection_messages = selector.seen[2]
    assert not any(
        "你是不是故意伪造了合同日期" in item["content"] for item in second_selection_messages
    )
    assert any(
        "请只核对您是否伪造过合同日期" in item["content"] for item in second_selection_messages
    )
    healthy_report = trajectory_health_report([trajectory], {trajectory.case_id: _case()})
    assert not any("withheld" in code for code in healthy_report["counts"])

    corrupted = trajectory.model_copy(deep=True)
    corrupted_first = corrupted.steps[0]
    corrupted_first.client_matched_fact_ids = []
    corrupted_first.client_disclosure_decisions = {"F1": "disclose"}
    corrupted_first.client_selected_fact_ids = ["F1"]
    corrupted_first.client_route_decision_valid = False
    corrupted_target = next(
        item
        for item in corrupted_first.state_after["facts"]
        if item["fact_id"] == runtime_target_id
    )
    corrupted_target["status"] = "not_available"
    corrupted_first.state_after["asked_targets"] = [runtime_target_id]
    corrupted_interaction = corrupted_first.state_after["interactions"][-1]
    corrupted_interaction["new_information"] = True
    corrupted_interaction["disclosed_fact_ids"] = ["F1"]
    corrupted_report = trajectory_health_report([corrupted], {corrupted.case_id: _case()})
    assert {
        "client_response_provenance_mismatch",
        "client_withheld_match_provenance_mismatch",
        "client_disclosure_decision_provenance_mismatch",
        "client_selected_fact_without_valid_route",
        "client_withheld_target_state_changed",
        "client_withheld_target_marked_asked",
        "client_withheld_interaction_provenance_mismatch",
    }.issubset(corrupted_report["counts"])


def test_training_fact_presentation_shuffle_is_seeded_and_priority_preserving() -> None:
    from legal_skill_guard.experiment.runner import (  # noqa: PLC0415
        policy_fact_presentation_seed,
    )

    runner, _, _ = _runner()
    state = StateManager().initial("presentation", "客户开场。", max_turns=6)
    state = StateManager().merge(
        state,
        StatePatch(
            observations=[
                FactObservation(
                    fact_id=fact_id,
                    label=label,
                    status="unknown",
                    criticality=criticality,
                )
                for fact_id, label, criticality in (
                    ("high_a", "高优先事实甲", "high"),
                    ("high_b", "高优先事实乙", "high"),
                    ("high_c", "高优先事实丙", "high"),
                    ("medium_a", "中优先事实甲", "medium"),
                    ("medium_b", "中优先事实乙", "medium"),
                    ("low_a", "低优先事实甲", "low"),
                )
            ]
        ),
        0,
    )
    original_ids = [item.fact_id for item in state.facts]
    displayed_orders: list[list[str]] = []
    for sample_index in range(4):
        messages = runner._visible_messages(
            "客户开场。",
            [],
            state,
            1,
            fact_presentation_seed=policy_fact_presentation_seed(42, sample_index, 1),
        )
        payload_text = messages[-1].content.split("：\n", 1)[1].split("\n终止一致性检查", 1)[0]
        payload = json.loads(payload_text)
        displayed_orders.append([item["fact_id"] for item in payload["facts"]])
        assert [item["criticality"] for item in payload["facts"]] == [
            "high",
            "high",
            "high",
            "medium",
            "medium",
            "low",
        ]
        assert set(displayed_orders[-1]) == {
            "high_a",
            "high_b",
            "high_c",
            "medium_a",
            "medium_b",
            "low_a",
        }
    assert len({tuple(item) for item in displayed_orders}) >= 2
    assert [item.fact_id for item in state.facts] == original_ids
    assert policy_fact_presentation_seed(42, 0, 1) == 420_000
    assert policy_fact_presentation_seed(42, 3, 4) == 420_303


def test_unresolved_targets_prompt_preserves_adaptive_stop_choice() -> None:
    runner, _, _ = _runner()
    state = StateManager().initial("adaptive-stop", "客户开场。", max_turns=24)
    state = StateManager().merge(
        state,
        StatePatch(
            observations=[
                FactObservation(
                    fact_id="remaining_material_gap",
                    label="尚待材料核验的事项",
                    status="unknown",
                    criticality="high",
                    target_kind="evidence_or_third_party",
                )
            ]
        ),
        0,
    )
    message = runner._visible_messages("客户开场。", [], state, 3)[-1].content
    assert "不构成必须继续或必须结束的系统规则" in message
    assert "若选择终止，不得声称未知事项已经查明" in message
    assert "若没有针对剩余目标的具体可见依据，请选择" not in message


def test_nonterminal_last_turn_is_recorded_as_horizon_exhaustion() -> None:
    runner, policy, selector = _runner()
    third_unknown = {
        "fact_id": "F3",
        "label": "履行经过的书面材料",
        "status": "unknown",
        "value": None,
        "evidence_labels": [],
        "confidence": 0.5,
        "criticality": "medium",
    }
    policy.responses[-1] = _policy(
        {
            "action_type": "ask",
            "target_id": "F3",
            "content": "您是否还有其他能够直接核实履行经过的材料？",
        },
        [third_unknown],
    )
    selector.responses.extend(
        [
            '{"fact_ids":[]}',
            '{"answers_question":false}',
            '{"answers_question":false}',
            '{"fact_ids":[]}',
        ]
    )
    trajectory = runner.run(
        raw_case=_case(),
        persona={"persona_id": "P_WD", "who": {"zh": "当事人"}, "voice": {"zh": "简短"}},
        skills=[],
        trajectory_id="traj_horizon",
        run_id="run_test",
        method="training_policy_sample",
        partition="training_round_01",
        seed=42,
        sample_index=0,
        max_turns=3,
        group_id="group_test",
        skill_library_version="empty",
    )
    assert trajectory.status == "max_turns_forced_memo"
    assert trajectory.steps[-1].stop_gate_verdict == "EXHAUSTED"
    assert trajectory.steps[-1].stop_gate_reason == ("dialogue_horizon_exhausted_after_interaction")
    assert len([step for step in trajectory.steps if step.client_response is not None]) == 3


def test_nonrepairable_management_patch_is_discarded_before_state_merge() -> None:
    runner, policy, _ = _runner()
    invalid = _policy(
        {"action_type": "final", "content": ""},
        [
            {
                "fact_id": "opening_statement",
                "label": "客户开场陈述",
                "status": "client_claimed",
                "value": _case()["opening"],
                "evidence_labels": [],
                "confidence": 1.0,
                "criticality": "low",
            }
        ],
    )
    policy.responses = [invalid, invalid, invalid]
    trajectory = runner.run(
        raw_case=_case(),
        persona={"persona_id": "P_WD", "who": {"zh": "当事人"}, "voice": {"zh": "简短"}},
        skills=[],
        trajectory_id="traj_discard_management_patch",
        run_id="run_test",
        method="training_policy_sample",
        partition="training_round_01",
        seed=42,
        sample_index=0,
        max_turns=1,
        group_id="group_test",
        skill_library_version="empty",
    )
    step = trajectory.steps[0]
    assert step.state_patch.observations == []
    opening_facts = [
        item for item in step.state_after["facts"] if item["fact_id"] == "opening_statement"
    ]
    assert len(opening_facts) == 1
    assert opening_facts[0]["source_turns"] == [0]


def test_policy_repair_receives_the_rejected_json_it_must_edit() -> None:
    runner, policy, _ = _runner()
    invalid = _policy(
        {
            "action_type": "ask",
            "target_id": "opening_statement",
            "content": "请重复开场？",
        },
        [],
    )
    repaired = _policy(
        {
            "action_type": "ask",
            "target_id": "payment_document",
            "content": "您目前有哪一份付款凭证？",
        },
        [],
    )
    policy.responses = [invalid, repaired]
    runner.run(
        raw_case=_case(),
        persona={"persona_id": "P_WD", "who": {"zh": "当事人"}, "voice": {"zh": "简短"}},
        skills=[],
        trajectory_id="traj_policy_repair_context",
        run_id="run_test",
        method="training_policy_sample",
        partition="training_round_01",
        seed=42,
        sample_index=0,
        max_turns=1,
        group_id="group_test",
        skill_library_version="empty",
    )
    assert policy.seen[1][-2] == {"role": "assistant", "content": invalid}
    assert "上一份JSON违反契约" in policy.seen[1][-1]["content"]


def test_empty_policy_completion_uses_bounded_role_repair_without_refeeding() -> None:
    runner, policy, _ = _runner()
    repaired = _policy(
        {
            "action_type": "ask",
            "target_id": "payment_document",
            "content": "您目前有哪一份付款凭证？",
        },
        [],
    )
    policy.responses = ["", repaired]
    state = StateManager().initial("empty-policy-role-repair", _case()["opening"], max_turns=6)
    state.facts.append(
        FactSlot(
            fact_id="payment_document",
            label="付款凭证",
            status="unknown",
            criticality="high",
        )
    )

    envelope, attempts, violations = runner._generate_policy(
        [Message(role="system", content="只输出动作JSON")], state, 42
    )

    assert envelope.action.target_id == "payment_document"
    assert violations == []
    assert len(attempts) == 2
    assert attempts[0].raw_output == ""
    assert attempts[0].parse_mode == "fallback"
    assert "invalid_structured_output" in attempts[0].health_violations
    assert all(message["role"] != "assistant" for message in policy.seen[1])
    assert "invalid_structured_output" in policy.seen[1][-1]["content"]


def test_counterfactual_initial_targets_form_two_matched_continuation_pairs() -> None:
    state = StateManager().initial("counterfactual-allocation", "开场", max_turns=6)
    state.facts.extend(
        [
            FactSlot(
                fact_id="target_a",
                label="目标A",
                status="unknown",
                criticality="high",
                target_kind="client_fact",
            ),
            FactSlot(
                fact_id="target_b",
                label="目标B",
                status="unknown",
                criticality="medium",
                target_kind="evidence_or_third_party",
            ),
            FactSlot(
                fact_id="already_known",
                label="已知事实",
                status="client_claimed",
                value="开场可见",
                target_kind="client_fact",
            ),
        ]
    )

    allocated = [
        counterfactual_initial_target(state, index, replicates_per_target=2) for index in range(4)
    ]

    assert [item.fact_id if item else None for item in allocated] == [
        "target_a",
        "target_a",
        "target_b",
        "target_b",
    ]

    with pytest.raises(ValueError, match="replicates_per_target must be positive"):
        counterfactual_initial_target(state, 0, replicates_per_target=0)


def test_counterfactual_followup_targets_fork_inside_each_matched_pair() -> None:
    state = StateManager().initial("counterfactual-followup", "开场", max_turns=6)
    state.facts.extend(
        [
            FactSlot(
                fact_id="next_a",
                label="后续目标A",
                status="unknown",
                criticality="high",
                target_kind="client_fact",
            ),
            FactSlot(
                fact_id="next_b",
                label="后续目标B",
                status="unknown",
                criticality="medium",
                target_kind="client_fact",
            ),
        ]
    )

    allocated = [
        counterfactual_followup_target(state, index, branches_per_pair=2) for index in range(4)
    ]

    assert [item.fact_id if item else None for item in allocated] == [
        None,
        "next_a",
        None,
        "next_a",
    ]


def test_counterfactual_followup_does_not_immediately_retry_withheld_first_target() -> None:
    state = StateManager().initial("counterfactual-withheld", "开场", max_turns=6)
    state.facts.extend(
        [
            FactSlot(
                fact_id="withheld_first",
                label="首轮暂未披露事实",
                status="unknown",
                criticality="high",
                target_kind="client_fact",
            ),
            FactSlot(
                fact_id="next_a",
                label="后续目标A",
                status="unknown",
                criticality="high",
                target_kind="client_fact",
            ),
            FactSlot(
                fact_id="next_b",
                label="后续目标B",
                status="unknown",
                criticality="medium",
                target_kind="client_fact",
            ),
        ]
    )
    state.interactions.append(
        Interaction(
            turn=1,
            action_type="ask",
            target_id="withheld_first",
            question="请说明首轮事实？",
            response_kind="withheld",
        )
    )

    assert state.asked_targets == []
    allocated = [
        counterfactual_followup_target(state, index, branches_per_pair=2) for index in range(2)
    ]
    assert [item.fact_id if item else None for item in allocated] == [
        None,
        "next_a",
    ]


def test_counterfactual_followup_prefers_visible_client_fact_over_external_gap() -> None:
    state = StateManager().initial("counterfactual-client-first", "开场", max_turns=6)
    state.facts.extend(
        [
            FactSlot(
                fact_id="external_record",
                label="第三方记录",
                status="unknown",
                criticality="high",
                target_kind="evidence_or_third_party",
            ),
            FactSlot(
                fact_id="client_event",
                label="客户亲历事件",
                status="unknown",
                criticality="medium",
                target_kind="client_fact",
            ),
        ]
    )

    allocated = counterfactual_followup_target(state, 1, branches_per_pair=2)

    assert allocated is not None
    assert allocated.fact_id == "client_event"


def test_counterfactual_initial_target_uses_same_model_repair_and_fails_closed() -> None:
    runner, policy, _ = _runner()
    state = StateManager().initial("counterfactual-repair", "合同履行发生争议。", max_turns=6)
    target_a = FactSlot(
        fact_id="payment_time",
        label="客户实际付款时间",
        status="unknown",
        criticality="high",
        target_kind="client_fact",
    )
    target_b = FactSlot(
        fact_id="delivery_time",
        label="对方实际交付时间",
        status="unknown",
        criticality="high",
        target_kind="client_fact",
    )
    state.facts.extend([target_a, target_b])
    wrong = _policy(
        {
            "action_type": "ask",
            "target_id": "delivery_time",
            "content": "对方实际是在什么时候交付的？",
        },
        [],
    )
    repaired = _policy(
        {
            "action_type": "ask",
            "target_id": "payment_time",
            "content": "您付款的具体时间是什么时候？",
        },
        [],
    )
    policy.responses = [wrong, repaired]

    envelope, attempts, violations = runner._generate_policy(
        [Message(role="system", content="只输出动作JSON")],
        state,
        42,
        required_target=target_a,
    )

    assert envelope.action.target_id == "payment_time"
    assert violations == []
    assert any(
        item.startswith("counterfactual_initial_target_mismatch:payment_time:")
        for item in attempts[0].health_violations
    )
    assert all(
        "counterfactual_initial_target_assignment:payment_time" in item.deterministic_changes
        for item in attempts
    )
    assert "target_id必须精确等于payment_time" in policy.seen[1][-1]["content"]

    policy.responses = [wrong, wrong, wrong]
    with pytest.raises(RuntimeError, match="assignment failed closed"):
        runner._generate_policy(
            [Message(role="system", content="只输出动作JSON")],
            state,
            42,
            required_target=target_a,
        )


def test_stagnated_policy_repair_drops_rejected_assistant_anchor() -> None:
    runner, policy, _ = _runner()
    state = StateManager().initial(
        "stagnated-policy-role-repair",
        "我在保安公司工作期间与公司发生社会保险安排争议，公司称我已签字同意改领补助。",
        max_turns=6,
    )
    state.facts.append(
        FactSlot(
            fact_id="signed_agreement_details",
            label="是否签署过替代社保的补助协议？",
            status="unknown",
            criticality="high",
        )
    )
    compound = _policy(
        {
            "action_type": "ask",
            "target_id": "signed_agreement_details",
            "content": (
                "您是否签署了替代社会保险的补助协议？如果签署了，请说明协议的具体内容和签署过程。"
            ),
        },
        [],
    )
    repaired = _policy(
        {
            "action_type": "ask",
            "target_id": "signed_agreement_details",
            "content": "您是否签署过替代社保的补助协议？",
        },
        [],
    )
    policy.responses = [compound, compound, repaired]

    envelope, attempts, violations = runner._generate_policy(
        [Message(role="system", content="只输出动作JSON")], state, 42
    )

    assert envelope.action.content == "您是否签署过替代社保的补助协议？"
    assert violations == []
    assert len(attempts) == 3
    assert policy.seen[1][-2] == {"role": "assistant", "content": compound}
    assert all(message["role"] != "assistant" for message in policy.seen[2])
    assert "multiple_primary_questions" in policy.seen[2][-1]["content"]


def test_policy_repair_budget_covers_sequential_violation_transitions() -> None:
    runner, policy, _ = _runner()
    runner.max_policy_attempts = 5
    state = StateManager().initial(
        "sequential-policy-role-repair",
        "我在保安公司工作期间与公司发生社会保险安排争议，公司称我已签字同意改领补助。",
        max_turns=6,
    )
    state.facts.append(
        FactSlot(
            fact_id="signed_agreement_details",
            label="是否签署过替代社保的补助协议？",
            status="unknown",
            criticality="high",
        )
    )
    state = StateManager().mark_interaction(
        state,
        turn=1,
        action_type="ask",
        target_id="signed_agreement_details",
        question="您是否在任职期间签署了替代社会保险的补助协议？",
        response_kind="withheld",
    )
    compound = _policy(
        {
            "action_type": "ask",
            "target_id": "signed_agreement_details",
            "content": "您是否签署了替代社会保险的补助协议？如果签了，协议中具体写了哪些内容？",
        },
        [],
    )
    repeated = _policy(
        {
            "action_type": "ask",
            "target_id": "signed_agreement_details",
            "content": "您是否在任职期间签署了替代社会保险的补助协议？",
        },
        [],
    )
    invalid_final_value = json.loads(_policy({"action_type": "final", "content": ""}, []))
    invalid_final_value["action"]["reason"] = "剩余目标无法获取或信息价值较低。"
    invalid_final = json.dumps(invalid_final_value, ensure_ascii=False)
    valid_final_value = json.loads(_policy({"action_type": "final", "content": ""}, []))
    valid_final_value["action"]["reason"] = (
        "本次未披露替代社保协议的签署情况，当前可见事实足以形成以已披露事实为限的条件性初步分析。"
    )
    valid_final = json.dumps(valid_final_value, ensure_ascii=False)
    policy.responses = [compound, compound, repeated, invalid_final, valid_final]

    envelope, attempts, violations = runner._generate_policy(
        [Message(role="system", content="只输出动作JSON")], state, 42
    )

    assert envelope.action.action_type == "final"
    assert violations == []
    assert len(attempts) == 5
    assert attempts[0].health_violations == ["multiple_primary_questions"]
    assert attempts[1].health_violations == ["multiple_primary_questions"]
    assert attempts[2].health_violations == ["repeated_question_text"]
    assert "terminal_unsupported_blanket_low_value_claim" in attempts[3].health_violations
    assert attempts[4].health_violations == []


def test_exact_repeat_repair_does_not_refeed_rejected_action() -> None:
    runner, policy, _ = _runner()
    state = StateManager().initial("repeat-repair-clean-context", "合同履行发生争议。", max_turns=6)
    state.facts.append(
        FactSlot(
            fact_id="payment_status",
            label="客户是否实际付款",
            status="unknown",
            criticality="high",
        )
    )
    state = StateManager().mark_interaction(
        state,
        turn=1,
        action_type="ask",
        target_id="payment_status",
        question="您是否实际付款",
        response_kind="withheld",
    )
    repeated = _policy(
        {
            "action_type": "ask",
            "target_id": "payment_status",
            "content": "您是否实际付款？",
        },
        [],
    )
    invalid_final_value = json.loads(_policy({"action_type": "final", "content": ""}, []))
    invalid_final_value["action"]["reason"] = "剩余目标无法获取或信息价值较低。"
    invalid_final = json.dumps(invalid_final_value, ensure_ascii=False)
    repaired_final_value = json.loads(_policy({"action_type": "final", "content": ""}, []))
    repaired_final_value["action"]["reason"] = (
        "当前可见事实已足以形成以已披露事实为限的条件性初步分析。"
    )
    repaired = json.dumps(repaired_final_value, ensure_ascii=False)
    policy.responses = [repeated, invalid_final, repaired]

    envelope, attempts, violations = runner._generate_policy(
        [Message(role="system", content="只输出动作JSON")], state, 42
    )

    assert envelope.action.action_type == "final"
    assert len(attempts) == 3
    assert violations == []
    assert all(message["role"] != "assistant" for message in policy.seen[1])
    assert "本轮不得选择这些目标" in policy.seen[1][-1]["content"]
    assert "本轮只修复上一稿final的理由表述" in policy.seen[2][-1]["content"]


def test_pre_scoring_health_gate_blocks_persisted_management_patch(tmp_path: Path) -> None:
    runner, _, _ = _runner()
    trajectory = runner.run(
        raw_case=_case(),
        persona={"persona_id": "P_WD", "who": {"zh": "当事人"}, "voice": {"zh": "简短"}},
        skills=[],
        trajectory_id="traj_contaminated_state_patch",
        run_id="run_test",
        method="training_policy_sample",
        partition="training_round_01",
        seed=42,
        sample_index=0,
        max_turns=3,
        group_id="group_test",
        skill_library_version="empty",
    )
    contaminated = trajectory.model_copy(deep=True)
    contaminated.steps[0].state_patch = StatePatch(
        observations=[
            FactObservation(
                fact_id="opening_statement",
                label="客户开场陈述",
                status="client_claimed",
                value=trajectory.opening,
            )
        ]
    )
    report = trajectory_health_report([contaminated], {contaminated.case_id: _case()})
    assert report["healthy"] is False
    assert report["counts"]["management_fact_patch"] == 1
    assert report["counts"]["persisted_policy_contract_failure"] >= 1

    executor = object.__new__(MainExperimentExecutor)
    executor.store = RunStore(tmp_path / "runs", "health_gate_test")
    executor.experiment = {"execution": {"judge_workers": 1}}
    executor.evaluator = SimpleNamespace(
        evaluate=lambda *_: pytest.fail("semantic judge must not run after contract failure")
    )
    adapter = SimpleNamespace(evaluator_case=lambda _: _case())
    with pytest.raises(ExecutionError, match="pre-scoring trajectory health contract failed"):
        MainExperimentExecutor.score_trajectories(executor, [contaminated], adapter)
    persisted = json.loads(
        (executor.store.root / "health/pre_scoring_health_training_round_01.json").read_text(
            encoding="utf-8"
        )
    )
    assert persisted["counts"]["management_fact_patch"] == 1
    assert persisted["counts"]["persisted_policy_contract_failure"] >= 1


def test_pre_scoring_health_rejects_retired_runtime_skill_rewrite() -> None:
    runner, _, _ = _runner()
    trajectory = runner.run(
        raw_case=_case(),
        persona={"persona_id": "P_WD", "who": {"zh": "当事人"}, "voice": {"zh": "简短"}},
        skills=[],
        trajectory_id="traj_skill_repaired_proposal",
        run_id="run_test",
        method="training_policy_sample",
        partition="training_round_01",
        seed=42,
        sample_index=0,
        max_turns=3,
        group_id="group_test",
        skill_library_version="empty",
    )
    repaired = trajectory.model_copy(deep=True)
    step = repaired.steps[0]
    invalid = step.proposed_action.model_copy(
        update={
            "expected_information": "付款日期和金额",
            "content": "您付款的日期和金额分别是什么？",
        }
    )
    executed = step.action_decision.final
    step.proposed_action = invalid
    step.action_decision.original = invalid
    step.action_decision.activated_skill_ids = ["fixture.atomic_repair"]
    step.action_decision.changes = [
        {
            "skill_id": "fixture.atomic_repair",
            "before": invalid.model_dump(mode="json"),
            "after": executed.model_dump(mode="json"),
        }
    ]
    step.policy_health_violations = ["multiple_primary_questions"]
    step.post_skill_health_violations = []

    report = trajectory_health_report([repaired], {repaired.case_id: _case()})

    assert report["healthy"] is False
    assert report["counts"]["retired_runtime_skill_executor_observed"] == 1


def test_protocol15_health_blocks_missing_and_changed_target_kind_provenance() -> None:
    runner, _, _ = _runner()
    trajectory = runner.run(
        raw_case=_case(),
        persona={"persona_id": "P_WD", "who": {"zh": "当事人"}, "voice": {"zh": "简短"}},
        skills=[],
        trajectory_id="traj_target_kind_provenance",
        run_id="run_test",
        method="training_policy_sample",
        partition="training_round_01",
        seed=42,
        sample_index=0,
        max_turns=3,
        group_id="group_test",
        skill_library_version="empty",
    )

    missing = trajectory.model_copy(deep=True)
    missing.steps[0].state_before["facts"][0].pop("target_kind")
    missing_report = trajectory_health_report([missing], {missing.case_id: _case()})
    assert missing_report["counts"]["target_kind_missing"] == 1

    mismatched = trajectory.model_copy(deep=True)
    mismatched.steps[0].state_patch.observations[0].target_kind = "evidence_or_third_party"
    mismatch_report = trajectory_health_report([mismatched], {mismatched.case_id: _case()})
    assert mismatch_report["counts"]["target_kind_provenance_mismatch"] >= 1


def test_current_trajectory_contract_is_explicit_and_legacy_audit_is_opt_in() -> None:
    runner, _, _ = _runner()
    current = runner.run(
        raw_case=_case(),
        persona={"persona_id": "P_WD", "who": {"zh": "当事人"}, "voice": {"zh": "简短"}},
        skills=[],
        trajectory_id="traj_current_contract",
        run_id="run_test",
        method="training_policy_sample",
        partition="training_round_01",
        seed=42,
        sample_index=0,
        max_turns=3,
        group_id="group_test",
        skill_library_version="empty",
    )
    assert current_trajectory_contract_issues(current, expected_run_id="run_test") == []
    assert_current_trajectory_contract(current, expected_run_id="run_test")
    run_issues = current_trajectory_contract_issues(current, expected_run_id="different_run")
    assert [item.code for item in run_issues] == ["trajectory_run_id_mismatch"]

    legacy_payload = current.model_dump(mode="json")
    legacy_payload["schema_version"] = 14
    legacy_payload["steps"][0]["state_patch"]["observations"][0].pop("target_kind")
    with pytest.raises(ValueError, match="active ResearchTrajectory requires"):
        ResearchTrajectory.model_validate(legacy_payload)
    legacy = ResearchTrajectory.model_validate_historical(legacy_payload)
    assert legacy.schema_version == 14
    assert legacy.steps[0].state_patch.observations[0].target_kind is None
    assert [item.code for item in current_trajectory_contract_issues(legacy)] == [
        "trajectory_schema_version_mismatch"
    ]
    historical_report = trajectory_health_report(
        [legacy],
        {legacy.case_id: _case()},
        require_current_contract=False,
    )
    assert "trajectory_schema_version_mismatch" not in historical_report["counts"]


def test_scoring_refuses_stale_judge_contract_cache(tmp_path: Path) -> None:
    runner, _, _ = _runner()
    trajectory = runner.run(
        raw_case=_case(),
        persona={"persona_id": "P_WD", "who": {"zh": "当事人"}, "voice": {"zh": "简短"}},
        skills=[],
        trajectory_id="traj_stale_judge_contract",
        run_id="run_test",
        method="training_policy_sample",
        partition="training_round_01",
        seed=42,
        sample_index=0,
        max_turns=3,
        group_id="group_test",
        skill_library_version="empty",
    )
    executor = object.__new__(MainExperimentExecutor)
    executor.store = RunStore(tmp_path / "runs", trajectory.run_id)
    executor.experiment = {"execution": {"judge_workers": 1}}
    executor.judge_qualification_contract_sha256 = "a" * 64
    executor.evaluator = SimpleNamespace(
        evaluate=lambda *_: pytest.fail("stale score must not be reused or overwritten")
    )
    executor.store.atomic_json(
        executor.store.evaluation_path(trajectory.trajectory_id),
        {
            "schema_version": 13,
            "judge_qualification_contract_sha256": "b" * 64,
        },
    )
    adapter = SimpleNamespace(evaluator_case=lambda _: _case())
    with pytest.raises(ExecutionError, match="stale semantic evaluation contract"):
        MainExperimentExecutor.score_trajectories(executor, [trajectory], adapter)


def test_scoring_refuses_stale_evolution_metric_schema(tmp_path: Path) -> None:
    runner, _, _ = _runner()
    trajectory = runner.run(
        raw_case=_case(),
        persona={"persona_id": "P_WD", "who": {"zh": "当事人"}, "voice": {"zh": "简短"}},
        skills=[],
        trajectory_id="traj_stale_evaluation_schema",
        run_id="run_test",
        method="training_policy_sample",
        partition="training_round_01",
        seed=42,
        sample_index=0,
        max_turns=3,
        group_id="group_test",
        skill_library_version="empty",
    )
    executor = object.__new__(MainExperimentExecutor)
    executor.store = RunStore(tmp_path / "runs", trajectory.run_id)
    executor.experiment = {"execution": {"judge_workers": 1}}
    executor.judge_qualification_contract_sha256 = "a" * 64
    executor.evaluator = SimpleNamespace(
        evaluate=lambda *_: pytest.fail("stale score must not be reused or overwritten")
    )
    executor.store.atomic_json(
        executor.store.evaluation_path(trajectory.trajectory_id),
        {
            "schema_version": 8,
            "judge_qualification_contract_sha256": "a" * 64,
        },
    )
    adapter = SimpleNamespace(evaluator_case=lambda _: _case())
    with pytest.raises(ExecutionError, match="stale semantic evaluation schema"):
        MainExperimentExecutor.score_trajectories(executor, [trajectory], adapter)


def test_pre_scoring_health_gate_blocks_abstention_with_visible_substance() -> None:
    runner, _, _ = _runner()
    trajectory = runner.run(
        raw_case=_case(),
        persona={"persona_id": "P_WD", "who": {"zh": "当事人"}, "voice": {"zh": "简短"}},
        skills=[],
        trajectory_id="traj_bad_abstention",
        run_id="run_test",
        method="training_policy_sample",
        partition="training_round_01",
        seed=42,
        sample_index=0,
        max_turns=1,
        group_id="group_test",
        skill_library_version="empty",
    )
    # Runtime repair should prevent this state.  Mutate only the persisted status to
    # prove the independent pre-scoring contract still fails closed.
    trajectory.status = "abstained"
    report = trajectory_health_report([trajectory], {trajectory.case_id: _case()})
    assert report["healthy"] is False
    assert report["counts"] == {"abstention_with_substantive_visible_state": 1}


def test_pre_scoring_health_preserves_semantic_repeat_as_quality_signal() -> None:
    runner, _, _ = _runner()
    trajectory = runner.run(
        raw_case=_case(),
        persona={"persona_id": "P_WD", "who": {"zh": "当事人"}, "voice": {"zh": "简短"}},
        skills=[],
        trajectory_id="traj_semantic_repeat",
        run_id="run_test",
        method="training_policy_sample",
        partition="training_round_01",
        seed=42,
        sample_index=0,
        max_turns=3,
        group_id="group_test",
        skill_library_version="empty",
    )
    repeated = trajectory.model_copy(deep=True)
    repeated.steps[1].client_selected_fact_ids = ["F1"]
    repeated.steps[1].client_matched_fact_ids = ["F1"]
    repeated.steps[1].client_disclosure_decisions = {"F1": "disclose"}
    repeated.steps[1].client_response_kind = "repeated_hidden_fact"
    repeated.steps[1].client_route_decision_valid = True
    repeated.steps[1].client_response = "这项情况我刚才已经说明，目前没有更多可确认的信息。"
    report = trajectory_health_report([repeated], {repeated.case_id: _case()})
    assert report["healthy"] is True
    assert report["counts"] == {}
    assert report["quality_diagnostics"]["client_semantic_repetition_no_new_information"] == 1


def test_pre_scoring_health_rejects_unavailable_without_valid_empty_route() -> None:
    runner, _, _ = _runner()
    trajectory = runner.run(
        raw_case=_case(),
        persona={"persona_id": "P_WD", "who": {"zh": "当事人"}, "voice": {"zh": "简短"}},
        skills=[],
        trajectory_id="traj_invalid_unavailable_route",
        run_id="run_test",
        method="training_policy_sample",
        partition="training_round_01",
        seed=42,
        sample_index=0,
        max_turns=3,
        group_id="group_test",
        skill_library_version="empty",
    )
    corrupted = trajectory.model_copy(deep=True)
    step = corrupted.steps[0]
    step.client_response_kind = "unavailable"
    step.client_route_decision_valid = False
    step.client_safe_fallback = False
    step.client_selected_fact_ids = []
    step.client_opening_reference_ids = []
    step.client_matched_fact_ids = []
    step.client_disclosure_decisions = {}

    report = trajectory_health_report([corrupted], {corrupted.case_id: _case()})

    assert report["healthy"] is False
    assert report["counts"]["client_unavailable_without_valid_empty_route"] == 1


def test_pre_scoring_health_separates_grounded_public_opening_reference() -> None:
    runner, _, _ = _runner()
    trajectory = runner.run(
        raw_case=_case(),
        persona={"persona_id": "P_WD", "who": {"zh": "当事人"}, "voice": {"zh": "简短"}},
        skills=[],
        trajectory_id="traj_opening_grounding",
        run_id="run_test",
        method="training_policy_sample",
        partition="training_round_01",
        seed=42,
        sample_index=0,
        max_turns=3,
        group_id="group_test",
        skill_library_version="empty",
    )
    grounded = trajectory.model_copy(deep=True)
    grounded.steps[0].client_selected_fact_ids = []
    grounded.steps[0].client_opening_reference_ids = ["O1"]
    grounded.steps[0].client_matched_fact_ids = ["O1"]
    grounded.steps[0].client_disclosure_decisions = {"O1": "disclose"}
    grounded.steps[0].client_response_kind = "opening_repeat"
    grounded.steps[0].client_route_decision_valid = True
    grounded.steps[
        0
    ].client_response = (
        "开场时我已经说明过：我与对方签了合同，现在对履行情况有争议；目前没有更多可确认的信息。"
    )
    report = trajectory_health_report([grounded], {grounded.case_id: _case()})
    assert report["healthy"] is True
    assert report["counts"] == {}


def test_adaptive_termination_contract_is_independent_of_configured_horizon() -> None:
    assert all(termination_contract_check(turns)["passed"] for turns in (4, 6, 8))


def test_investigation_planner_accepts_visible_fact_agenda_and_rejects_legal_task() -> None:
    state = StateManager().initial("planner", "房屋分割咨询。", max_turns=6)
    valid = json.dumps(
        {
            "issue_labels": ["房屋分割方案及证据基础"],
            "unknowns": [
                {
                    "fact_id": "current_market_value",
                    "label": "房屋当前市场价值",
                    "criticality": "high",
                    "target_kind": "evidence_or_third_party",
                },
                {
                    "fact_id": "family_care_contribution",
                    "label": "客户实际承担的家庭照料投入",
                    "criticality": "medium",
                    "target_kind": "client_fact",
                },
            ],
        },
        ensure_ascii=False,
    )
    patch, mode, violations, changes = parse_investigation_plan(valid, state)
    assert mode == "json"
    assert violations == []
    assert changes == []
    assert [item.fact_id for item in patch.observations] == [
        "current_market_value",
        "family_care_contribution",
    ]
    assert [item.target_kind for item in patch.observations] == [
        "evidence_or_third_party",
        "client_fact",
    ]

    invalid = json.dumps(
        {
            "issue_labels": ["房屋分割"],
            "unknowns": [
                {
                    "fact_id": "required_documents",
                    "label": "离婚所需材料清单",
                    "criticality": "medium",
                    "target_kind": "client_fact",
                }
            ],
        },
        ensure_ascii=False,
    )
    _, _, violations, _ = parse_investigation_plan(invalid, state)
    assert violations == ["unsafe_planner_target:required_documents"]


def test_investigation_planner_rejects_unknown_without_explicit_target_kind() -> None:
    state = StateManager().initial("planner-missing-target-kind", "合同履行发生争议。", max_turns=6)
    missing_target_kind = json.dumps(
        {
            "issue_labels": ["合同履行"],
            "unknowns": [
                {
                    "fact_id": "delivery_date",
                    "label": "货物实际交付日期",
                    "criticality": "high",
                }
            ],
        },
        ensure_ascii=False,
    )

    patch, mode, violations, changes = parse_investigation_plan(missing_target_kind, state)

    assert mode == "json"
    assert patch.observations == []
    assert violations == ["invalid_planner_unknown_schema:0"]
    assert changes == []


def test_investigation_planner_disambiguates_copied_ids_after_a_safe_split() -> None:
    state = StateManager().initial("planner-split-id", "房屋抵债争议。", max_turns=6)
    value = json.dumps(
        {
            "issue_labels": ["抵债履行"],
            "unknowns": [
                {
                    "fact_id": "execution_details",
                    "label": "房屋抵债的具体履行方式",
                    "criticality": "high",
                    "target_kind": "client_fact",
                },
                {
                    "fact_id": "execution_details",
                    "label": "房屋是否已经完成交付",
                    "criticality": "high",
                    "target_kind": "client_fact",
                },
            ],
        },
        ensure_ascii=False,
    )
    patch, _, violations, changes = parse_investigation_plan(value, state)
    assert violations == []
    assert len({item.fact_id for item in patch.observations}) == 2
    assert any(item.startswith("disambiguate_duplicate_planner_fact_id:") for item in changes)


def test_investigation_planner_rejects_unestablished_client_payment_attributes() -> None:
    state = StateManager().initial(
        "planner-payment-presupposition",
        "房屋原由丈夫购置，婚后加上了我的名字。",
        max_turns=6,
    )
    value = json.dumps(
        {
            "issue_labels": ["房屋分割"],
            "unknowns": [
                {
                    "fact_id": "client_payment_amount",
                    "label": "婚后我实际支付的房屋出资金额",
                    "criticality": "high",
                    "target_kind": "client_fact",
                }
            ],
        },
        ensure_ascii=False,
    )
    patch, _, violations, changes = parse_investigation_plan(value, state)
    assert patch.observations == []
    assert violations == ["presupposes_unestablished_client_payment:client_payment_amount"]
    assert any(item.endswith(":presupposes_unestablished_client_payment") for item in changes)

    existence = json.dumps(
        {
            "issue_labels": ["房屋分割"],
            "unknowns": [
                {
                    "fact_id": "client_contribution",
                    "label": "客户是否对房屋有实际出资或投入",
                    "criticality": "high",
                    "target_kind": "client_fact",
                }
            ],
        },
        ensure_ascii=False,
    )
    patch, _, violations, _ = parse_investigation_plan(existence, state)
    assert violations == []
    assert [item.fact_id for item in patch.observations] == ["client_contribution"]


def test_investigation_planner_preserves_official_procedure_mechanism() -> None:
    state = StateManager().initial(
        "planner-procedure-mechanism",
        "我在民事执行中接受房屋抵债，尚未过户时房屋又被纳入追缴。",
        max_turns=24,
    )
    value = json.dumps(
        {
            "issue_labels": ["执行抵债与追缴"],
            "unknowns": [
                {
                    "fact_id": "private_deed_date",
                    "label": "抵债协议签署的具体日期",
                    "criticality": "high",
                    "target_kind": "client_fact",
                },
                {
                    "fact_id": "private_deed_payment",
                    "label": "抵债协议中已支付的款项金额",
                    "criticality": "medium",
                    "target_kind": "client_fact",
                },
                {
                    "fact_id": "criminal_judgment_date",
                    "label": "关联刑事判决生效的具体日期",
                    "criticality": "high",
                    "target_kind": "client_fact",
                },
                {
                    "fact_id": "criminal_judgment_number",
                    "label": "关联刑事判决的案号",
                    "criticality": "low",
                    "target_kind": "client_fact",
                },
                {
                    "fact_id": "execution_order_exists",
                    "label": "法院是否作出以物抵债执行裁定",
                    "criticality": "high",
                    "target_kind": "client_fact",
                },
            ],
        },
        ensure_ascii=False,
    )

    patch, _, violations, changes = parse_investigation_plan(value, state)

    assert violations == [
        "introduces_unestablished_private_transaction_mechanism:private_deed_date",
        "introduces_unestablished_private_transaction_mechanism:private_deed_payment",
        "presupposes_unestablished_response_event:criminal_judgment_date",
        "presupposes_unestablished_response_event:criminal_judgment_number",
    ]
    assert [item.fact_id for item in patch.observations] == ["execution_order_exists"]
    assert any(
        item.endswith(":introduces_unestablished_private_transaction_mechanism") for item in changes
    )

    existence_value = json.dumps(
        {
            "issue_labels": ["执行抵债"],
            "unknowns": [
                {
                    "fact_id": "execution_order_exists",
                    "label": "法院抵债裁定书是否已出具",
                    "criticality": "high",
                    "target_kind": "client_fact",
                }
            ],
        },
        ensure_ascii=False,
    )
    existence_patch, _, existence_violations, _ = parse_investigation_plan(existence_value, state)
    assert existence_violations == []
    assert [item.fact_id for item in existence_patch.observations] == ["execution_order_exists"]

    private_state = StateManager().initial(
        "planner-private-deed",
        "我与债务人签订了房屋抵债协议，但还没有办理过户。",
        max_turns=24,
    )
    private_value = json.dumps(
        {
            "issue_labels": ["私人抵债协议"],
            "unknowns": [
                {
                    "fact_id": "private_deed_date",
                    "label": "抵债协议签署的具体日期",
                    "criticality": "high",
                    "target_kind": "client_fact",
                }
            ],
        },
        ensure_ascii=False,
    )
    private_patch, _, private_violations, _ = parse_investigation_plan(private_value, private_state)
    assert private_violations == []
    assert [item.fact_id for item in private_patch.observations] == ["private_deed_date"]


def test_investigation_planner_rejects_high_priority_date_refinement_of_opening_event() -> None:
    state = StateManager().initial(
        "planner-date",
        "房屋婚后登记到了夫妻双方名下。",
        max_turns=6,
    )
    value = json.dumps(
        {
            "issue_labels": ["房屋分割"],
            "unknowns": [
                {
                    "fact_id": "registration_exact_date",
                    "label": "房屋登记到双方名下的具体日期",
                    "criticality": "high",
                    "target_kind": "client_fact",
                }
            ],
        },
        ensure_ascii=False,
    )
    patch, _, violations, changes = parse_investigation_plan(value, state)
    assert violations == []
    assert patch.observations[0].criticality == "medium"
    assert "cap_opening_event_date_criticality:registration_exact_date:high->medium" in changes


def test_investigation_planner_caps_generic_time_refinement_when_stage_is_known() -> None:
    state = StateManager().initial(
        "planner-stage-time",
        "房屋婚前购买，婚后登记到了夫妻双方名下。",
        max_turns=6,
    )
    value = json.dumps(
        {
            "issue_labels": ["房屋分割"],
            "unknowns": [
                {
                    "fact_id": "purchase_time",
                    "label": "房屋最初购买的时间",
                    "criticality": "high",
                    "target_kind": "client_fact",
                }
            ],
        },
        ensure_ascii=False,
    )
    patch, _, violations, changes = parse_investigation_plan(value, state)
    assert violations == []
    assert patch.observations[0].criticality == "medium"
    assert "cap_opening_event_date_criticality:purchase_time:high->medium" in changes


def test_investigation_planner_downgrades_identifiers_and_stably_orders_criticality() -> None:
    state = StateManager().initial(
        "planner-identifier-priority",
        "行政机关作出处理后发生争议。",
        max_turns=24,
    )
    rejected = json.dumps(
        {
            "issue_labels": ["行政处理"],
            "unknowns": [
                {
                    "fact_id": "decision_number",
                    "label": "行政决定的具体文号",
                    "criticality": "high",
                    "target_kind": "client_fact",
                }
            ],
        },
        ensure_ascii=False,
    )
    patch, _, violations, changes = parse_investigation_plan(rejected, state)
    assert violations == []
    assert patch.observations[0].criticality == "low"
    assert "cap_precise_identifier_criticality:decision_number:high->low" in changes

    accepted = json.dumps(
        {
            "issue_labels": ["行政处理"],
            "unknowns": [
                {
                    "fact_id": "decision_number",
                    "label": "行政决定的具体文号",
                    "criticality": "medium",
                    "target_kind": "client_fact",
                },
                {
                    "fact_id": "decision_content",
                    "label": "行政决定载明的具体内容",
                    "criticality": "high",
                    "target_kind": "client_fact",
                },
            ],
        },
        ensure_ascii=False,
    )
    patch, _, violations, changes = parse_investigation_plan(accepted, state)
    assert violations == []
    assert [item.fact_id for item in patch.observations] == [
        "decision_content",
        "decision_number",
    ]
    assert any(
        item.startswith("stable_sort_planner_targets_by_model_criticality:") for item in changes
    )

    document_name = json.dumps(
        {
            "issue_labels": ["行政处理"],
            "unknowns": [
                {
                    "fact_id": "credential_name",
                    "label": "资质证明文件的名称",
                    "criticality": "high",
                    "target_kind": "client_fact",
                },
                {
                    "fact_id": "credential_content",
                    "label": "资质证明文件的具体内容",
                    "criticality": "high",
                    "target_kind": "client_fact",
                },
            ],
        },
        ensure_ascii=False,
    )
    patch, _, violations, _ = parse_investigation_plan(document_name, state)
    assert violations == []
    assert [item.criticality for item in patch.observations] == ["high", "medium"]


def test_investigation_planner_preserves_safe_items_and_audits_long_id_shortening() -> None:
    state = StateManager().initial("planner-partial", "合同履行发生争议。", max_turns=6)
    long_id = "original_financial_responsibility_removal_agreement_effectiveness"
    value = json.dumps(
        {
            "issue_labels": ["合同履行"],
            "unknowns": [
                {
                    "fact_id": long_id,
                    "label": "双方解除原付款安排时实际签署的协议内容",
                    "criticality": "high",
                    "target_kind": "client_fact",
                },
                {
                    "fact_id": "legal_result",
                    "label": "该协议是否具有法律效力",
                    "criticality": "high",
                    "target_kind": "client_fact",
                },
            ],
        },
        ensure_ascii=False,
    )
    patch, _, violations, changes = parse_investigation_plan(value, state)
    assert violations == ["unsafe_planner_target:legal_result"]
    assert len(patch.observations) == 1
    assert patch.observations[0].fact_id != long_id
    assert len(patch.observations[0].fact_id) <= 64
    assert changes and changes[0].startswith(f"shorten_planner_fact_id:{long_id}->")


def test_planner_drops_attributes_of_response_event_denied_by_opening() -> None:
    state = StateManager().initial(
        "planner-no-response",
        "我们连续三次申请行政补偿都没有答复。",
        max_turns=24,
    )
    value = json.dumps(
        {
            "issue_labels": ["行政补偿申请未答复"],
            "unknowns": [
                {
                    "fact_id": "decision_content",
                    "label": "区政府作出的行政补偿决定的具体内容",
                    "criticality": "high",
                    "target_kind": "client_fact",
                },
                {
                    "fact_id": "nonresponse_reason",
                    "label": "区政府未作出答复的具体理由",
                    "criticality": "high",
                    "target_kind": "client_fact",
                },
            ],
        },
        ensure_ascii=False,
    )

    patch, mode, violations, changes = parse_investigation_plan(value, state)

    assert mode == "json"
    assert violations == ["presupposes_opening_negated_response_event:decision_content"]
    assert [item.fact_id for item in patch.observations] == ["nonresponse_reason"]
    assert "reject_planner_target:decision_content:区政府作出的行政补偿决定的具体内容" in changes
    assert (
        "reject_planner_reason:decision_content:presupposes_opening_negated_response_event"
        in changes
    )


def test_planner_drops_content_of_response_event_not_established_by_opening() -> None:
    assert asks_response_event_existence("银行是否实际发出提前清偿通知")
    assert asks_response_event_existence("是否已有对相关人员的处罚决定")
    assert asks_response_event_existence("处罚决定是否已经作出")
    assert asks_response_event_existence("刑事追缴决定是否已实际作出")
    assert asks_response_event_existence("刑事追缴决定是否已实际收到")
    assert asks_response_event_existence("执法机关是否开具了处罚决定书")
    assert asks_response_event_existence("是否已通知相关诉讼当事人")
    assert asks_response_event_existence("银行是否有任何书面或口头回应")
    assert asks_response_event_existence("政府部门有无正式回复")
    assert asks_response_event_existence("对方是否已正式回应质疑")
    assert asks_response_event_existence("主管部门有无回复申请")
    assert not asks_response_event_existence("对方回应质疑的具体内容")
    assert not asks_response_event_existence("对方是否已说明回应的具体理由")
    assert not asks_response_event_existence("刑事追缴决定作出机关是否已经存在")
    assert not asks_response_event_existence("刑事追缴决定所依据的文件是否已经存在")
    assert not asks_response_event_existence("执法机关开具的处罚决定书具体引用哪些条款")
    assert response_event_terms_in("是否有其他部门参与决定补偿金额") == set()
    assert response_event_terms_in("是否已有对相关人员的处罚决定") == {"决定"}
    assert response_event_terms_in("银行是否有任何书面或口头回应") == {"回应"}
    assert response_event_terms_in("我在工地受伤并已被认定工伤") == set()
    assert response_event_terms_in("我在工地受伤但尚未被认定工伤") == set()
    assert asks_response_event_existence("文体部门退件决定书是否实际作出")
    state = StateManager().initial(
        "planner-unestablished-notice",
        "银行要求公司提前清偿贷款，理由涉及迟延和保证人风险。",
        max_turns=24,
    )
    value = json.dumps(
        {
            "issue_labels": ["提前清偿是否适当"],
            "unknowns": [
                {
                    "fact_id": "notice_content",
                    "label": "银行要求提前清偿贷款的具体通知内容",
                    "criticality": "high",
                    "target_kind": "client_fact",
                },
                {
                    "fact_id": "notice_existence",
                    "label": "银行是否实际发出提前清偿通知",
                    "criticality": "high",
                    "target_kind": "client_fact",
                },
                {
                    "fact_id": "notice_sender",
                    "label": "银行发出提前清偿通知的发送方",
                    "criticality": "medium",
                    "target_kind": "client_fact",
                },
                {
                    "fact_id": "personnel_decision_existence",
                    "label": "是否已有对相关人员的处罚决定",
                    "criticality": "medium",
                    "target_kind": "client_fact",
                },
                {
                    "fact_id": "party_notification_action",
                    "label": "是否已通知相关诉讼当事人",
                    "criticality": "medium",
                    "target_kind": "client_fact",
                },
            ],
        },
        ensure_ascii=False,
    )

    patch, mode, violations, changes = parse_investigation_plan(value, state)

    assert mode == "json"
    assert violations == [
        "presupposes_unestablished_response_event:notice_content",
        "presupposes_unestablished_response_event:notice_sender",
    ]
    assert [item.fact_id for item in patch.observations] == [
        "notice_existence",
        "personnel_decision_existence",
        "party_notification_action",
    ]
    assert (
        "reject_planner_reason:notice_content:presupposes_unestablished_response_event" in changes
    )

    established_determination = StateManager().initial(
        "planner-established-determination",
        "我在工地受伤并已被认定工伤。",
        max_turns=24,
    )
    determination_value = json.dumps(
        {
            "issue_labels": ["工伤待遇"],
            "unknowns": [
                {
                    "fact_id": "work_injury_certification_basis",
                    "label": "工伤认定决定书认定依据",
                    "criticality": "high",
                    "target_kind": "client_fact",
                }
            ],
        },
        ensure_ascii=False,
    )
    determination_patch, _, determination_violations, _ = parse_investigation_plan(
        determination_value, established_determination
    )
    assert determination_violations == []
    assert [item.fact_id for item in determination_patch.observations] == [
        "work_injury_certification_basis"
    ]

    unestablished_determination = StateManager().initial(
        "planner-unestablished-determination",
        "我在工地受伤但尚未被认定工伤。",
        max_turns=24,
    )
    _, _, unestablished_violations, _ = parse_investigation_plan(
        determination_value, unestablished_determination
    )
    assert unestablished_violations == [
        "presupposes_unestablished_response_event:work_injury_certification_basis"
    ]

    compound_value = json.dumps(
        {
            "issue_labels": ["提前清偿是否适当"],
            "unknowns": [
                {
                    "fact_id": "notice_content_compound",
                    "label": "对方通知或告知相关招用行为的具体内容是什么",
                    "criticality": "high",
                    "target_kind": "client_fact",
                }
            ],
        },
        ensure_ascii=False,
    )
    _, _, compound_violations, compound_changes = parse_investigation_plan(compound_value, state)
    assert compound_violations == [
        "presupposes_unestablished_response_event:notice_content_compound",
        "unsafe_planner_target:notice_content_compound",
    ]
    compound_reason = next(
        change
        for change in compound_changes
        if change.startswith("reject_planner_reason:notice_content_compound:")
    )
    assert "multiple_primary_questions" in compound_reason
    assert "presupposes_unestablished_response_event" in compound_reason


def test_planner_does_not_treat_missing_delivery_evidence_as_no_notice_event() -> None:
    state = StateManager().initial(
        "planner-missing-delivery-evidence",
        "市监局认为没有向9名成员送达会议通知的证据，补正后仍不予登记。",
        max_turns=24,
    )
    value = json.dumps(
        {
            "issue_labels": ["会议通知程序事实"],
            "unknowns": [
                {
                    "fact_id": "notice_recipients",
                    "label": "会议通知的具体收件人",
                    "criticality": "high",
                    "target_kind": "client_fact",
                }
            ],
        },
        ensure_ascii=False,
    )

    patch, _, violations, _ = parse_investigation_plan(value, state)

    assert violations == []
    assert [item.fact_id for item in patch.observations] == ["notice_recipients"]


def test_planner_projects_only_literal_safe_atomic_prefixes() -> None:
    state = StateManager().initial(
        "planner-atomic-projection",
        "公司出具的监测报告发生争议。",
        max_turns=6,
    )
    value = json.dumps(
        {
            "issue_labels": ["报告事实与人员行为"],
            "unknowns": [
                {
                    "fact_id": "monitoring_reports",
                    "label": ("客户具体出具了哪些监测报告，包括报告编号、时间、涉及地区和行业"),
                    "criticality": "high",
                    "target_kind": "client_fact",
                },
                {
                    "fact_id": "sampling_method",
                    "label": ("业务人员实际采用的采样方法是否符合规范，是否存在不规范采样行为"),
                    "criticality": "high",
                    "target_kind": "client_fact",
                },
                {
                    "fact_id": "payment_details",
                    "label": "客户已垫付的补偿金额及具体支付方式",
                    "criticality": "high",
                    "target_kind": "client_fact",
                },
                {
                    "fact_id": "legal_outcome",
                    "label": "客户期望的法律后果是什么，包括刑事责任和行政处罚",
                    "criticality": "medium",
                    "target_kind": "client_fact",
                },
            ],
        },
        ensure_ascii=False,
    )
    patch, _, violations, changes = parse_investigation_plan(value, state)
    assert [item.label for item in patch.observations] == [
        "客户具体出具了哪些监测报告",
        "业务人员实际采用的采样方法",
    ]
    assert violations == [
        "presupposes_unestablished_client_payment:payment_details",
        "unsafe_planner_target:payment_details",
        "unsafe_planner_target:legal_outcome",
    ]
    assert (
        len([item for item in changes if item.startswith("project_planner_label_to_atomic_core:")])
        == 2
    )
    assert (
        atomic_factual_target_projection(
            "legal_outcome", "客户期望的法律后果是什么，包括刑事责任和行政处罚"
        )
        is None
    )
    assert (
        atomic_factual_target_projection(
            "criminal_legal_basis", "执法机关认定公司和个人构成犯罪的具体法律依据"
        )
        is None
    )
    assert (
        atomic_factual_target_projection("data_use_purpose", "对方插件获取数据的具体使用目的")
        == "对方插件获取数据的具体使用目的"
    )
    assert atomic_factual_target_projection("infringing_product", "实际销售的侵权产品") is None
    assert atomic_factual_target_projection("illegal_profit", "客户实际保留的非法获利金额") is None
    assert atomic_factual_target_projection("symptoms", "治疗后出现的症状及持续时间") is None
    assert atomic_factual_target_projection("product", "产品名称以及供应商信息") == "产品名称"
    assert atomic_factual_target_projection("outcome", "客户预期效果及当前实际状态") is None
    assert (
        atomic_factual_target_projection("pledge_effect", "股权质押是否已依法生效并具备法律约束力")
        is None
    )
    assert (
        atomic_factual_target_projection("employment_relation", "对方与员工实际存在的劳动关系")
        is None
    )
    assert atomic_factual_target_projection("evidence", "是否存在直接证据证明数据被干预") is None
    assert atomic_factual_target_projection("compliance", "公司是否已知并遵守环保法规") is None
    assert atomic_factual_target_projection("agreements", "是否签署过保密和竞业协议") is None
    assert atomic_factual_target_projection("measurement", "监测数据的具体数值和趋势") is None
    assert atomic_factual_target_projection("knowledge", "客户对共同犯罪计划的了解程度") is None
    assert atomic_factual_target_projection("knowledge", "客户是否知晓资金将被转交他人") is None
    assert atomic_factual_target_projection("knowledge", "银行是否已知悉客户采取的措施") is None
    assert atomic_factual_target_projection("agreement", "调解协议是否已经生效") is None
    assert atomic_factual_target_projection("loss_basis", "客户主张的损失计算依据") is None
    assert atomic_factual_target_projection("evidence", "付款的具体凭证和金额明细") is None
    assert atomic_factual_target_projection("awareness", "客户是否察觉到行为异常") is None
    assert (
            atomic_factual_target_projection("compensation", "实际垫付的金额以及具体项目")
        == "实际垫付的金额"
    )
    assert atomic_factual_target_projection("land", "取得土地的具体情况及证明文件") is None
    assert atomic_factual_target_projection("future", "政府承诺的补偿何时能够兑现") is None
    assert atomic_factual_target_projection("authority", "监护人的身份和权限如何") is None
    assert atomic_factual_target_projection("criminal_money", "客户收到的诈骗资金金额") is None
    linked_contact_event = "双方是否保持联系，频率如何"
    assert atomic_factual_target_projection("contact", linked_contact_event) == linked_contact_event
    linked_agreement_event = "保密和竞业协议签署时间"
    assert (
        atomic_factual_target_projection("agreements", linked_agreement_event)
        == linked_agreement_event
    )
    assert atomic_factual_target_projection("sentence", "刑事罚金的判决依据") is None
    assert atomic_factual_target_projection("application", "申请材料是否完整、有效") is None
    assert atomic_factual_target_projection("comparison", "实际培训内容与宣传图是否一致") is None
    assert atomic_factual_target_projection("impact", "是否产生其他法律或现实后果") is None
    one_contract = "客户与对方签署的合同时间"
    assert atomic_factual_target_projection("one_contract", one_contract) == one_contract
    assert atomic_factual_target_projection("notice", "机关是否已向公司履行告知义务") is None
    assert atomic_factual_target_projection("source", "短视频中AI语音的具体来源确认") is None
    assert atomic_factual_target_projection("rule", "暂行办法是否已被废止、修订或失效") is None
    assert atomic_factual_target_projection("citation", "暂行办法的全称及发布机关") is None
    caregiver_name = "参与照顾孩子的亲属或第三方的姓名"
    assert atomic_factual_target_projection("caregiver_name", caregiver_name) == caregiver_name
    contact = "丈夫及其家人在B省的联系方式"
    assert atomic_factual_target_projection("contact_method", contact) == contact
    assert atomic_factual_target_projection("materials", "离婚分割所需准备的具体材料") is None
    statement_date = "执法机关或第三方提及的产品使用日期"
    assert atomic_factual_target_projection("statement_date", statement_date) == statement_date
    unmentioned = "其他未提及的承诺内容"
    assert atomic_factual_target_projection("unmentioned", unmentioned) == unmentioned
    agency_statement = "执法机关或第三方对产品使用情况的具体陈述内容"
    assert (
        atomic_factual_target_projection("agency_statement", agency_statement) == agency_statement
    )
    participant_content = "参与者在培训过程中实际接触到的具体内容"
    assert (
        atomic_factual_target_projection("participant_content", participant_content)
        == participant_content
    )
    participant_name = "参与污染行为的第三方姓名"
    assert (
        atomic_factual_target_projection("participant_name", participant_name) == participant_name
    )
    assert (
        atomic_factual_target_projection("participant_identifier", "参与污染行为的第三方身份证号码")
        is None
    )
    cited_law = "住建局作出决定所依据的具体法律、法规或规章名称"
    assert atomic_factual_target_projection("cited_law", cited_law) == cited_law
    cited_policy_file = "行政补偿决定所依据的法律或政策文件名称"
    assert (
        atomic_factual_target_projection("cited_policy_file", cited_policy_file)
        == cited_policy_file
    )
    product_clause = "购买产品的合同或协议中关于产品功能的描述"
    assert atomic_factual_target_projection("product_clause", product_clause) == product_clause


def test_atomic_projection_rejects_distinct_events_across_temporal_boundary() -> None:
    # “签约前”与“签约后”各自包含一组独立交易，并非同一事件的关联属性。
    assert atomic_factual_target_projection("trades", "签约前后分别进行了哪些交易") is None


@pytest.mark.parametrize(
    ("fact_id", "label", "expected"),
    [
        (
            "charge_details",
            "自动扣费发生的具体时间、金额及对应账单编号",
            "自动扣费发生的具体时间",
        ),
        (
            "capital_details",
            "各股东实际出资金额以及到账时间",
            "各股东实际出资金额",
        ),
        (
            "notice_received",
            "是否收到过续费提醒以及具体接收方式",
            "是否收到过续费提醒",
        ),
        (
            "notice_content",
            "收到的续费提醒内容是否包含明确的费用金额、生效时间及取消途径",
            "收到的续费提醒内容",
        ),
        (
            "transfer_window",
            "提供电话转接服务的具体时间范围以及操作方式",
            "提供电话转接服务的具体时间范围",
        ),
    ],
)
def test_atomic_projection_preserves_safe_core_of_one_observable_event(
    fact_id: str, label: str, expected: str
) -> None:
    assert atomic_factual_target_projection(fact_id, label) == expected


def test_atomic_projection_does_not_launder_distinct_or_unsafe_compounds() -> None:
    assert atomic_factual_target_projection("agreements", "是否签署过保密和竞业协议") is None
    assert (
        atomic_factual_target_projection("misconduct", "是否存在伪造证据或虚假陈述的初步证据")
        is None
    )


def test_investigation_planner_normalizes_non_ascii_internal_id_without_losing_target() -> None:
    state = StateManager().initial("planner-id", "公司产品遭到网络测评。", max_turns=6)
    value = json.dumps(
        {
            "issue_labels": ["网络测评事实"],
            "unknowns": [
                {
                    "fact_id": "博主是否实际测试产品",
                    "label": "博主是否实际测试过涉案产品",
                    "criticality": "high",
                    "target_kind": "client_fact",
                }
            ],
        },
        ensure_ascii=False,
    )
    patch, _, violations, changes = parse_investigation_plan(value, state)
    assert violations == []
    assert len(patch.observations) == 1
    assert re.fullmatch(r"planned_fact_[a-f0-9]{20}", patch.observations[0].fact_id)
    assert patch.observations[0].label == "博主是否实际测试过涉案产品"
    assert changes == [
        f"normalize_planner_fact_id:博主是否实际测试产品->{patch.observations[0].fact_id}"
    ]


def test_investigation_planner_rejects_agenda_containing_only_client_outcome() -> None:
    state = StateManager().initial("planner-outcome", "行政申请被退件。", max_turns=6)
    value = json.dumps(
        {
            "issue_labels": ["行政处理"],
            "unknowns": [
                {
                    "fact_id": "client_desired_outcome",
                    "label": "客户希望撤销通知并重新处理的具体诉求和预期结果",
                    "criticality": "high",
                    "target_kind": "client_fact",
                }
            ],
        },
        ensure_ascii=False,
    )
    patch, _, violations, _ = parse_investigation_plan(value, state)
    assert patch.observations == []
    assert violations == ["unsafe_planner_target:client_desired_outcome"]


def test_planner_exhaustion_fails_closed_instead_of_using_partial_plan() -> None:
    runner, _, _ = _runner()
    response = json.dumps(
        {
            "issue_labels": ["价值争议"],
            "unknowns": [
                {
                    "fact_id": "market_value",
                    "label": "争议财产目前的市场价值",
                    "criticality": "high",
                    "target_kind": "client_fact",
                },
                {
                    "fact_id": "legal_result",
                    "label": "离婚所需材料清单",
                    "criticality": "high",
                    "target_kind": "client_fact",
                },
            ],
        },
        ensure_ascii=False,
    )
    planner = ScriptedChatClient([response, response, response])
    runner.planner_prompt = "只输出规划JSON"
    runner.planner_client = planner
    runner.max_planning_attempts = 3
    runner.planner_repair_generation = GenerationConfig(
        temperature=0.2, top_p=0.9, max_tokens=500, seed=42
    )
    state = StateManager().initial("partial-planner", "财产价值发生争议。", max_turns=6)
    with pytest.raises(InvestigationPlanningError) as captured:
        runner._generate_investigation_plan("财产价值发生争议。", state, 42)
    attempts = captured.value.attempts
    assert len(attempts) == 3
    assert all(
        item.health_violations == ["unsafe_planner_target:legal_result"] for item in attempts
    )
    assert "离婚所需材料清单" in planner.seen[1][-1]["content"]
    assert "必须逐项从unknowns中删除" in planner.seen[2][-1]["content"]
    assert all(
        any(
            change.startswith("planner_repair_mandatory_drop:")
            for change in attempt.deterministic_changes
        )
        for attempt in attempts
    )


def test_planner_rebuilds_clean_json_after_deletion_only_stagnation() -> None:
    runner, _, _ = _runner()
    rejected = json.dumps(
        {
            "issue_labels": ["价值争议"],
            "unknowns": [
                {
                    "fact_id": "market_value",
                    "label": "争议财产目前的市场价值",
                    "criticality": "high",
                    "target_kind": "client_fact",
                },
                {
                    "fact_id": "legal_result",
                    "label": "离婚所需材料清单",
                    "criticality": "high",
                    "target_kind": "client_fact",
                },
            ],
        },
        ensure_ascii=False,
    )
    clean = json.dumps(
        {
            "issue_labels": ["价值争议"],
            "unknowns": [
                {
                    "fact_id": "market_value",
                    "label": "争议财产目前的市场价值",
                    "criticality": "high",
                    "target_kind": "client_fact",
                }
            ],
        },
        ensure_ascii=False,
    )
    planner = ScriptedChatClient([rejected, rejected, clean])
    runner.planner_prompt = "只输出规划JSON"
    runner.planner_client = planner
    runner.max_planning_attempts = 3
    state = StateManager().initial("planner-clean-rebuild", "财产价值发生争议。", max_turns=6)

    patch, attempts, safe_partial = runner._generate_investigation_plan(
        "财产价值发生争议。", state, 42
    )

    assert safe_partial is False
    assert [item.fact_id for item in patch.observations] == ["market_value"]
    assert len(attempts) == 3
    assert (
        "planner_repair_rebuild_from_approved_targets_after_drop_stagnation"
        in attempts[1].deterministic_changes
    )
    clean_request = planner.seen[2][-1]["content"]
    assert "不要再参考或复述上一稿全文" in clean_request
    assert "争议财产目前的市场价值" in clean_request
    assert clean_request.count("离婚所需材料清单") == 1


def test_planner_rebuilds_from_approved_targets_after_mixed_stagnation() -> None:
    runner, _, _ = _runner()
    rejected = json.dumps(
        {
            "issue_labels": ["商标刑事程序事实核查"],
            "unknowns": [
                {
                    "fact_id": "battery_source_chain",
                    "label": "电池产品的采购渠道及供应商信息",
                    "criticality": "high",
                    "target_kind": "client_fact",
                },
                {
                    "fact_id": "subjective_knowledge_details",
                    "label": "客户是否知悉商标侵权风险",
                    "criticality": "high",
                    "target_kind": "client_fact",
                },
                {
                    "fact_id": "civil_case_evidence_submission",
                    "label": "民事裁判文书是否已作为刑事证据提交",
                    "criticality": "high",
                    "target_kind": "evidence_or_third_party",
                },
            ],
        },
        ensure_ascii=False,
    )
    repaired = json.dumps(
        {
            "issue_labels": ["商标刑事程序事实核查"],
            "unknowns": [
                {
                    "fact_id": "battery_source_chain",
                    "label": "电池产品的采购渠道及供应商信息",
                    "criticality": "high",
                    "target_kind": "client_fact",
                },
                {
                    "fact_id": "subjective_knowledge_details",
                    "label": "采购电池时卖方对商品标识来源的实际说明",
                    "criticality": "high",
                    "target_kind": "client_fact",
                },
                {
                    "fact_id": "civil_case_evidence_submission",
                    "label": "客户是否实际收到相关民事裁判文书",
                    "criticality": "high",
                    "target_kind": "client_fact",
                },
            ],
        },
        ensure_ascii=False,
    )
    planner = ScriptedChatClient([rejected, rejected, repaired])
    runner.planner_prompt = "只输出规划JSON"
    runner.planner_client = planner
    runner.max_planning_attempts = 3
    opening = "客户因销售电池被追究刑事责任，并提到相关民事纠纷。"
    state = StateManager().initial("planner-mixed-rebuild", opening, max_turns=6)

    patch, attempts, safe_partial = runner._generate_investigation_plan(opening, state, 42)

    assert safe_partial is False
    assert [item.fact_id for item in patch.observations] == [
        "battery_source_chain",
        "subjective_knowledge_details",
        "civil_case_evidence_submission",
    ]
    assert len(attempts) == 3
    assert (
        "planner_repair_rebuild_from_approved_targets_after_mixed_stagnation"
        in attempts[1].deterministic_changes
    )
    rebuild_request = planner.seen[2][-1]["content"]
    assert "不要再参考或复述上一稿全文" in rebuild_request
    assert "电池产品的采购渠道及供应商信息" in rebuild_request
    assert rebuild_request.count("客户是否知悉商标侵权风险") == 1
    assert "上一稿JSON" not in rebuild_request


def test_planner_editor_batches_all_mandatory_legal_deletions() -> None:
    runner, _, _ = _runner()
    rejected = json.dumps(
        {
            "issue_labels": ["损害争议"],
            "unknowns": [
                {
                    "fact_id": "actual_loss_amount",
                    "label": "客户实际发生的损失金额",
                    "criticality": "high",
                    "target_kind": "client_fact",
                },
                {
                    "fact_id": "legal_basis",
                    "label": "客户主张赔偿的具体法律依据",
                    "criticality": "medium",
                    "target_kind": "client_fact",
                },
                {
                    "fact_id": "evidence_quality",
                    "label": "现有记录的证据充分性",
                    "criticality": "medium",
                    "target_kind": "client_fact",
                },
            ],
        },
        ensure_ascii=False,
    )
    accepted = json.dumps(
        {
            "issue_labels": ["损害争议"],
            "unknowns": [
                {
                    "fact_id": "actual_loss_amount",
                    "label": "客户实际发生的损失金额",
                    "criticality": "high",
                    "target_kind": "client_fact",
                }
            ],
        },
        ensure_ascii=False,
    )
    planner = ScriptedChatClient([rejected, accepted])
    runner.planner_prompt = "只输出规划JSON"
    runner.planner_client = planner
    runner.max_planning_attempts = 3
    runner.planner_repair_generation = GenerationConfig(
        temperature=0.2, top_p=0.9, max_tokens=500, seed=42
    )
    state = StateManager().initial("planner-batch-drop", "发生了实际损失。", max_turns=6)

    patch, attempts, safe_partial = runner._generate_investigation_plan(
        "发生了实际损失。", state, 42
    )

    assert safe_partial is False
    assert [item.fact_id for item in patch.observations] == ["actual_loss_amount"]
    assert any(
        change.startswith("planner_repair_mandatory_drop:")
        and "客户主张赔偿的具体法律依据" in change
        and "现有记录的证据充分性" in change
        for change in attempts[0].deterministic_changes
    )
    repair_request = planner.seen[1][-1]["content"]
    assert "必须逐项从unknowns中删除" in repair_request
    assert "客户主张赔偿的具体法律依据" in repair_request
    assert "现有记录的证据充分性" in repair_request


def test_planner_editor_preserves_observable_core_while_removing_legal_label() -> None:
    assert planner_target_has_recoverable_observable_core(
        "客户是否已采取具体措施补正违约行为",
        "abstract_marker:违约行为",
    )
    assert not planner_target_has_recoverable_observable_core(
        "客户主张赔偿的具体法律依据",
        "abstract_marker:法律依据",
    )
    assert planner_target_has_recoverable_observable_core(
        "孩子当前生活状况是否符合最佳利益原则",
        "legal_or_evidentiary_judgment",
    )
    assert not planner_target_has_recoverable_observable_core(
        "现有记录的证据充分性",
        "legal_or_evidentiary_judgment",
    )
    assert planner_target_has_recoverable_observable_core(
        "涉案商品的销售数量、单价及非法获利金额",
        "abstract_marker:非法获利",
    )
    runner, _, _ = _runner()
    rejected = json.dumps(
        {
            "issue_labels": ["贷款履行争议"],
            "unknowns": [
                {
                    "fact_id": "breach_compliance_actions",
                    "label": "客户是否已采取具体措施补正违约行为",
                    "criticality": "high",
                    "target_kind": "client_fact",
                },
                {
                    "fact_id": "loan_terms",
                    "label": "贷款合同中的加速到期条款内容",
                    "criticality": "medium",
                    "target_kind": "client_fact",
                },
            ],
        },
        ensure_ascii=False,
    )
    accepted = json.dumps(
        {
            "issue_labels": ["贷款履行争议"],
            "unknowns": [
                {
                    "fact_id": "remedial_measures",
                    "label": "客户实际采取的补正措施",
                    "criticality": "high",
                    "target_kind": "client_fact",
                },
                {
                    "fact_id": "loan_terms",
                    "label": "贷款合同中的加速到期条款内容",
                    "criticality": "medium",
                    "target_kind": "client_fact",
                },
            ],
        },
        ensure_ascii=False,
    )
    planner = ScriptedChatClient([rejected, accepted])
    runner.planner_prompt = "只输出规划JSON"
    runner.planner_client = planner
    state = StateManager().initial("planner-observable-core", "银行要求提前还款。", max_turns=6)

    patch, attempts, safe_partial = runner._generate_investigation_plan(
        "银行要求提前还款。", state, 42
    )

    assert safe_partial is False
    # The already-valid contract target keeps its original position; the rejected
    # legalised target is the only item the repair may replace.
    assert [item.label for item in patch.observations] == [
        "贷款合同中的加速到期条款内容",
        "客户实际采取的补正措施",
    ]
    assert any(
        change.startswith("planner_repair_mandatory_factual_reframe:")
        for change in attempts[0].deterministic_changes
    )
    assert not any(
        change.startswith("planner_repair_mandatory_drop:")
        for change in attempts[0].deterministic_changes
    )
    assert "不得删除该调查维度" in planner.seen[1][-1]["content"]
    assert planner.generations[0].response_schema is None
    assert all(
        generation.response_schema == INVESTIGATION_PLAN_SCHEMA
        for generation in planner.generations[1:]
    )


def test_planner_editor_drops_only_persistently_unreframed_legalized_target() -> None:
    rejected = json.dumps(
        {
            "issue_labels": ["贷款履行争议"],
            "unknowns": [
                {
                    "fact_id": "breach_date",
                    "label": "贷款违约行为开始的具体日期",
                    "criticality": "medium",
                    "target_kind": "client_fact",
                },
                {
                    "fact_id": "loan_terms",
                    "label": "贷款合同中的加速到期条款内容",
                    "criticality": "high",
                    "target_kind": "client_fact",
                },
            ],
        },
        ensure_ascii=False,
    )
    accepted = json.dumps(
        {
            "issue_labels": ["贷款履行争议"],
            "unknowns": [
                {
                    "fact_id": "loan_terms",
                    "label": "贷款合同中的加速到期条款内容",
                    "criticality": "high",
                    "target_kind": "client_fact",
                }
            ],
        },
        ensure_ascii=False,
    )
    runner, _, _ = _runner()
    planner = ScriptedChatClient([rejected, rejected, accepted])
    runner.planner_prompt = "只输出规划JSON"
    runner.planner_client = planner
    state = StateManager().initial(
        "planner-stagnant-legal-label", "银行要求提前还款。", max_turns=6
    )

    patch, attempts, _ = runner._generate_investigation_plan("银行要求提前还款。", state, 42)

    assert [item.fact_id for item in patch.observations] == ["loan_terms"]
    assert any(
        change.startswith("planner_repair_mandatory_factual_reframe:")
        for change in attempts[0].deterministic_changes
    )
    assert any(
        change.startswith("planner_repair_mandatory_drop:")
        for change in attempts[1].deterministic_changes
    )


def test_planner_editor_batches_deletions_and_single_core_atomicization() -> None:
    runner, _, _ = _runner()
    rejected = json.dumps(
        {
            "issue_labels": ["音频使用争议"],
            "unknowns": [
                {
                    "fact_id": "legal_basis",
                    "label": "客户主张赔偿的法律依据",
                    "criticality": "medium",
                    "target_kind": "client_fact",
                },
                {
                    "fact_id": "audio_details",
                    "label": "客户提供的音频内容及实际使用情况",
                    "criticality": "high",
                    "target_kind": "client_fact",
                },
            ],
        },
        ensure_ascii=False,
    )
    accepted = json.dumps(
        {
            "issue_labels": ["音频使用争议"],
            "unknowns": [
                {
                    "fact_id": "audio_use",
                    "label": "客户提供的音频实际使用情况",
                    "criticality": "high",
                    "target_kind": "client_fact",
                },
            ],
        },
        ensure_ascii=False,
    )
    planner = ScriptedChatClient([rejected, accepted])
    runner.planner_prompt = "只输出规划JSON"
    runner.planner_client = planner
    runner.max_planning_attempts = 3
    runner.planner_repair_generation = GenerationConfig(
        temperature=0.2, top_p=0.9, max_tokens=500, seed=42
    )
    state = StateManager().initial("planner-mixed-batch", "音频使用发生争议。", max_turns=6)

    patch, attempts, _ = runner._generate_investigation_plan("音频使用发生争议。", state, 42)

    assert [item.fact_id for item in patch.observations] == ["audio_use"]
    changes = attempts[0].deterministic_changes
    assert any(change.startswith("planner_repair_mandatory_drop:") for change in changes)
    assert any(change.startswith("planner_repair_mandatory_atomicize:") for change in changes)
    repair_request = planner.seen[1][-1]["content"]
    assert "客户主张赔偿的法律依据" in repair_request
    assert "客户提供的音频内容及实际使用情况" in repair_request
    assert "只从每个原项中保留一个" in repair_request


def test_planner_editor_preserves_safe_core_and_drops_unsafe_compounds() -> None:
    runner, _, _ = _runner()
    rejected = json.dumps(
        {
            "issue_labels": ["商标使用争议"],
            "unknowns": [
                {
                    "fact_id": "consumer_perception",
                    "label": "消费者对该标识的实际理解",
                    "criticality": "high",
                    "target_kind": "client_fact",
                },
                {
                    "fact_id": "usage_details",
                    "label": "该标识的实际使用方式以及持续时间",
                    "criticality": "high",
                    "target_kind": "client_fact",
                },
                {
                    "fact_id": "usage_scope",
                    "label": "该标识的使用频率以及覆盖范围",
                    "criticality": "medium",
                    "target_kind": "client_fact",
                },
                {
                    "fact_id": "evidence_quality",
                    "label": "现有材料的证据充分性",
                    "criticality": "medium",
                    "target_kind": "client_fact",
                },
            ],
        },
        ensure_ascii=False,
    )
    destructively_shrunk = json.dumps(
        {
            "issue_labels": ["商标使用争议"],
            "unknowns": [
                {
                    "fact_id": "consumer_perception",
                    "label": "消费者对该标识的实际理解",
                    "criticality": "high",
                    "target_kind": "client_fact",
                }
            ],
        },
        ensure_ascii=False,
    )
    planner = ScriptedChatClient([rejected, destructively_shrunk])
    runner.planner_prompt = "只输出规划JSON"
    runner.planner_client = planner
    runner.max_planning_attempts = 4
    state = StateManager().initial("planner-split-conservation", "标识已经实际使用。", max_turns=6)

    patch, attempts, _ = runner._generate_investigation_plan("标识已经实际使用。", state, 42)

    assert [item.fact_id for item in patch.observations] == [
        "consumer_perception",
        "usage_scope",
    ]
    assert patch.observations[1].label == "该标识的使用频率"
    assert attempts[1].health_violations == []
    assert len(planner.seen) == 2


def test_planner_accepts_response_existence_after_splitting_compound_topic() -> None:
    runner, _, _ = _runner()
    first = json.dumps(
        {
            "issue_labels": ["食品安全赔偿主张可行性"],
            "unknowns": [
                {
                    "fact_id": "product_manufacturer_identity",
                    "label": "该减肥食品的实际生产厂商是谁",
                    "criticality": "high",
                    "target_kind": "client_fact",
                },
                {
                    "fact_id": "product_label_compliance",
                    "label": "该减肥食品的标签是否符合国家食品安全标准",
                    "criticality": "high",
                    "target_kind": "client_fact",
                },
                {
                    "fact_id": "seller_notification_content",
                    "label": "卖家是否已向您告知产品来源或成分相关问题",
                    "criticality": "medium",
                    "target_kind": "client_fact",
                },
            ],
        },
        ensure_ascii=False,
    )
    repaired = json.dumps(
        {
            "issue_labels": ["食品安全赔偿主张可行性"],
            "unknowns": [
                {
                    "fact_id": "product_manufacturer_identity",
                    "label": "该减肥食品的实际生产厂商是谁",
                    "criticality": "high",
                    "target_kind": "client_fact",
                },
                {
                    "fact_id": "product_label_compliance",
                    "label": "该减肥食品的标签内容",
                    "criticality": "high",
                    "target_kind": "client_fact",
                },
                {
                    "fact_id": "seller_response_existence",
                    "label": "卖家是否曾就产品来源或成分问题作出回应",
                    "criticality": "medium",
                    "target_kind": "client_fact",
                },
            ],
        },
        ensure_ascii=False,
    )
    planner = ScriptedChatClient([first, repaired])
    runner.planner_prompt = "只输出规划JSON"
    runner.planner_client = planner
    runner.max_planning_attempts = 3
    state = StateManager().initial(
        "planner-response-topic", "卖家因减肥食品来源和成分问题被调查。", max_turns=24
    )

    patch, attempts, _ = runner._generate_investigation_plan(
        "卖家因减肥食品来源和成分问题被调查。", state, 42
    )

    assert [item.fact_id for item in patch.observations] == [
        "product_manufacturer_identity",
        "product_label_compliance",
        "seller_response_existence",
    ]
    assert len(attempts) == 2
    assert attempts[-1].health_violations == []


def test_planner_projection_avoids_unnecessary_fragmenting_repair() -> None:
    runner, _, _ = _runner()
    first = json.dumps(
        {
            "issue_labels": ["履行争议"],
            "unknowns": [
                {
                    "fact_id": "collection_method",
                    "label": "客户是否曾尝试催收货款以及具体方式",
                    "criticality": "high",
                    "target_kind": "client_fact",
                },
                {
                    "fact_id": "delivery_schedule",
                    "label": "试剂供应的具体时间以及频率",
                    "criticality": "medium",
                    "target_kind": "client_fact",
                },
            ],
        },
        ensure_ascii=False,
    )
    replacement = json.dumps(
        {
            "issue_labels": ["履行争议"],
            "unknowns": [
                {
                    "fact_id": "delivery_time",
                    "label": "试剂供应的具体时间",
                    "criticality": "medium",
                    "target_kind": "client_fact",
                },
                {
                    "fact_id": "delivery_frequency",
                    "label": "试剂供应的具体频率",
                    "criticality": "medium",
                    "target_kind": "client_fact",
                },
            ],
        },
        ensure_ascii=False,
    )
    planner = ScriptedChatClient([first, replacement])
    runner.planner_prompt = "只输出规划JSON"
    runner.planner_client = planner
    state = StateManager().initial("planner-volume-floor", "医院拖欠货款。", max_turns=6)

    patch, attempts, _ = runner._generate_investigation_plan("医院拖欠货款。", state, 42)

    assert [item.fact_id for item in patch.observations] == [
        "collection_method",
        "delivery_schedule",
    ]
    assert patch.observations[1].label == "试剂供应的具体时间"
    assert attempts[0].health_violations == []
    assert len(planner.seen) == 1


def test_planner_repair_cannot_rewrite_an_already_safe_target() -> None:
    runner, _, _ = _runner()
    first = json.dumps(
        {
            "issue_labels": ["交付争议"],
            "unknowns": [
                {
                    "fact_id": "delivery_place",
                    "label": "货物实际交付地点",
                    "criticality": "high",
                    "target_kind": "client_fact",
                },
                {
                    "fact_id": "legal_result",
                    "label": "合同是否具有法律效力",
                    "criticality": "high",
                    "target_kind": "client_fact",
                },
            ],
        },
        ensure_ascii=False,
    )
    rewritten = json.dumps(
        {
            "issue_labels": ["交付争议"],
            "unknowns": [
                {
                    "fact_id": "delivery_place",
                    "label": "货物实际交付时间",
                    "criticality": "high",
                    "target_kind": "client_fact",
                }
            ],
        },
        ensure_ascii=False,
    )
    planner = ScriptedChatClient([first, rewritten])
    runner.planner_prompt = "只输出规划JSON"
    runner.planner_client = planner
    runner.max_planning_attempts = 2
    state = StateManager().initial("planner-safe-target-rewrite", "合同履行发生争议。", max_turns=6)

    patch, attempts, safe_partial = runner._generate_investigation_plan(
        "合同履行发生争议。", state, 42
    )

    assert safe_partial is False
    assert len(patch.observations) == 1
    restored = patch.observations[0]
    assert restored.fact_id == "delivery_place"
    assert restored.label == "货物实际交付地点"
    assert restored.criticality == "high"
    assert restored.target_kind == "client_fact"
    assert attempts[1].health_violations == []
    assert "restore_preserved_planner_target:delivery_place" in attempts[1].deterministic_changes


def test_planner_repair_transport_preserves_large_first_draft_without_expansion() -> None:
    runner, _, _ = _runner()

    safe_targets = [
        {
            "fact_id": fact_id,
            "label": label,
            "criticality": "high",
            "target_kind": "client_fact",
        }
        for fact_id, label in [
            ("delivery_place", "货物实际交付地点"),
            ("delivery_quantity", "货物实际交付数量"),
            ("delivery_method", "货物实际交付方式"),
            ("delivery_condition", "货物交付时的外观状态"),
            ("payment_amount", "客户实际支付的金额"),
            ("payment_method", "客户实际付款的方式"),
            ("delivered_model", "对方实际交付的货物型号"),
            ("defect_manifestation", "客户发现的货物问题具体表现"),
            ("retained_quantity", "客户目前持有的货物数量"),
        ]
    ]
    rejected_target = {
        "fact_id": "legal_result",
        "label": "合同是否具有法律效力",
        "criticality": "high",
        "target_kind": "client_fact",
    }
    first = json.dumps(
        {"issue_labels": ["交付争议"], "unknowns": [*safe_targets, rejected_target]},
        ensure_ascii=False,
    )
    # The editor deletes the unsafe target and accidentally omits one approved
    # target.  The deterministic immutable-state merge must restore it without
    # mistaking the default structured transport bound (8) for a semantic limit.
    repaired = json.dumps(
        {"issue_labels": ["交付争议"], "unknowns": safe_targets[:8]},
        ensure_ascii=False,
    )
    planner = ScriptedChatClient([first, repaired])
    runner.planner_prompt = "只输出规划JSON"
    runner.planner_client = planner
    runner.max_planning_attempts = 2
    state = StateManager().initial(
        "planner-large-first-draft",
        "客户已经付款，合同货物交付后发现质量问题。",
        max_turns=6,
    )

    patch, attempts, safe_partial = runner._generate_investigation_plan(
        "客户已经付款，合同货物交付后发现质量问题。", state, 42
    )

    assert safe_partial is False
    assert [item.fact_id for item in patch.observations] == [
        item["fact_id"] for item in safe_targets
    ]
    assert attempts[1].health_violations == []
    assert (
        "align_planner_repair_transport_bound_to_first_draft:8->10"
        in attempts[0].deterministic_changes
    )
    assert planner.generations[1].response_schema is not None
    assert planner.generations[1].response_schema["properties"]["unknowns"]["maxItems"] == 10


def test_planner_focus_exits_when_exact_stagnant_target_disappears() -> None:
    runner, _, _ = _runner()

    def plan(fact_id: str, label: str) -> str:
        return json.dumps(
            {
                "issue_labels": ["履行争议"],
                "unknowns": [
                    {
                        "fact_id": fact_id,
                        "label": label,
                        "criticality": "high",
                        "target_kind": "client_fact",
                    }
                ],
            },
            ensure_ascii=False,
        )

    first = plan("dangling_company", "执法机关认定公司")
    second = plan("dangling_company", "执法机关认定公司")
    changed_target = plan("dangling_person", "监管机关要求个人")
    accepted = plan("delivery_place", "货物实际交付的地点")
    planner = ScriptedChatClient([first, second, changed_target, accepted])
    runner.planner_prompt = "只输出规划JSON"
    runner.planner_client = planner
    runner.max_planning_attempts = 4
    runner.planner_repair_generation = GenerationConfig(
        temperature=0.2, top_p=0.9, max_tokens=500, seed=42
    )
    state = StateManager().initial("planner-focus-exit", "合同履行发生争议。", max_turns=6)

    patch, attempts, _ = runner._generate_investigation_plan("合同履行发生争议。", state, 42)

    assert [item.fact_id for item in patch.observations] == ["delivery_place"]
    assert "本轮只修改上述唯一一个label" in planner.seen[2][-1]["content"]
    assert "本轮只修改上述唯一一个label" not in planner.seen[3][-1]["content"]
    assert any(
        change == "planner_repair_focus_after_stagnation:执法机关认定公司"
        for change in attempts[2].deterministic_changes
    )


def test_truncated_planner_retry_replans_without_refeeding_malformed_output() -> None:
    runner, _, _ = _runner()
    truncated = (
        '{"issue_labels":["履行争议"],"unknowns":['
        '{"fact_id":"sentinel_unclosed","label":"SENTINEL_TRUNCATED_OUTPUT"'
    )
    repaired = json.dumps(
        {
            "issue_labels": ["履行争议"],
            "unknowns": [
                {
                    "fact_id": "actual_payment_amount",
                    "label": "客户实际支付的金额",
                    "criticality": "high",
                    "target_kind": "client_fact",
                }
            ],
        },
        ensure_ascii=False,
    )
    planner = ScriptedChatClient([truncated, repaired])
    runner.planner_prompt = "只输出规划JSON"
    runner.planner_client = planner
    runner.max_planning_attempts = 3
    runner.planner_repair_generation = GenerationConfig(
        temperature=0.2, top_p=0.9, max_tokens=500, seed=42
    )
    opening = "客户称已经支付合同款项，但实际支付金额存在争议。"
    state = StateManager().initial("truncated-planner", opening, max_turns=6)

    patch, attempts, safe_partial = runner._generate_investigation_plan(opening, state, 42)

    assert safe_partial is False
    assert len(attempts) == 2
    assert attempts[0].health_violations == ["invalid_planner_json"]
    assert [item.fact_id for item in patch.observations] == ["actual_payment_amount"]
    assert len(planner.seen[1]) == 3
    assert all("SENTINEL_TRUNCATED_OUTPUT" not in message["content"] for message in planner.seen[1])
    assert "最小充分图谱" in planner.seen[1][-1]["content"]
    assert planner.generations[0].temperature == 0
    assert planner.generations[1].temperature == 0.2


def test_planner_normalizes_opening_date_priority_without_retry() -> None:
    runner, _, _ = _runner()
    rejected = json.dumps(
        {
            "issue_labels": ["登记争议"],
            "unknowns": [
                {
                    "fact_id": "house_registration_date",
                    "label": "房屋登记到双方名下的具体日期",
                    "criticality": "high",
                    "target_kind": "client_fact",
                }
            ],
        },
        ensure_ascii=False,
    )
    planner = ScriptedChatClient([rejected])
    runner.planner_prompt = "只输出规划JSON"
    runner.planner_client = planner
    runner.max_planning_attempts = 3
    runner.planner_repair_generation = GenerationConfig(
        temperature=0.2, top_p=0.9, max_tokens=500, seed=42
    )
    opening = "房屋婚前购买，婚后登记到了双方名下。"
    state = StateManager().initial("planner-priority", opening, max_turns=6)

    patch, attempts, _ = runner._generate_investigation_plan(opening, state, 42)

    assert patch.observations[0].criticality == "medium"
    assert len(attempts) == 1
    assert attempts[0].health_violations == []
    assert (
        "cap_opening_event_date_criticality:house_registration_date:high->medium"
        in attempts[0].deterministic_changes
    )

    time_variant = rejected.replace("具体日期", "具体时间")
    time_patch, _, time_violations, time_changes = parse_investigation_plan(time_variant, state)
    assert time_violations == []
    assert time_patch.observations[0].criticality == "medium"
    assert "cap_opening_event_date_criticality:house_registration_date:high->medium" in time_changes


def test_failed_planner_persists_every_rejected_attempt_in_trajectory() -> None:
    runner, _, _ = _runner()
    invalid = json.dumps(
        {
            "issue_labels": ["法律结果"],
            "unknowns": [
                {
                    "fact_id": "legal_result",
                    "label": "该协议是否具有法律效力",
                    "criticality": "high",
                    "target_kind": "client_fact",
                }
            ],
        },
        ensure_ascii=False,
    )
    runner.planner_prompt = "只输出规划JSON"
    runner.planner_client = ScriptedChatClient([invalid, invalid, invalid])
    runner.max_planning_attempts = 3
    trajectory = runner.run(
        raw_case=_case(),
        persona={"persona_id": "P_WD", "who": {"zh": "当事人"}, "voice": {"zh": "简短"}},
        skills=[],
        trajectory_id="traj_failed_planner_audit",
        run_id="run_test",
        method="training_policy_sample",
        partition="training_round_01",
        seed=42,
        sample_index=0,
        max_turns=3,
        group_id="group_test",
        skill_library_version="empty",
    )
    assert trajectory.status == "error"
    assert trajectory.error and "InvestigationPlanningError" in trajectory.error
    assert len(trajectory.planning_attempts) == 3
    assert all(
        attempt.health_violations == ["unsafe_planner_target:legal_result"]
        for attempt in trajectory.planning_attempts
    )


def test_judge_qualification_fingerprint_excludes_unrelated_role_changes(
    tmp_path: Path,
) -> None:
    contract_paths = (
        "configs/prompts/semantic_judge_zh.txt",
        "data/training/legal_skill_guard_dlawbench_style_cn.jsonl",
        "data/training/legal_skill_guard_dlawbench_style_cn.provenance.jsonl",
        "legal_skill_guard/evaluation/semantic.py",
        "legal_skill_guard/inference/structured_openai_client.py",
        "scripts/qualify_local_judge.py",
    )
    for relative in contract_paths:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"contract:{relative}\n", encoding="utf-8")
    unrelated = tmp_path / "configs/prompts/consultation_planner_zh.txt"
    unrelated.write_text("planner:first\n", encoding="utf-8")
    judge_role = {"model_id": "judge", "revision": "frozen", "temperature": 0.0}

    original = semantic_judge_qualification_sha256(tmp_path, judge_role)
    unrelated.write_text("planner:changed\n", encoding="utf-8")
    assert semantic_judge_qualification_sha256(tmp_path, judge_role) == original

    training_data = tmp_path / "data/training/legal_skill_guard_dlawbench_style_cn.jsonl"
    training_data.write_text("qualification corpus changed\n", encoding="utf-8")
    assert semantic_judge_qualification_sha256(tmp_path, judge_role) != original

    prompt = tmp_path / "configs/prompts/semantic_judge_zh.txt"
    prompt.write_text("judge prompt changed\n", encoding="utf-8")
    assert semantic_judge_qualification_sha256(tmp_path, judge_role) != original


def test_operational_metric_counts_post_skill_policy_fallback() -> None:
    step = SimpleNamespace(
        proposed_action=SimpleNamespace(reason="model_action"),
        action_decision=SimpleNamespace(
            final=SimpleNamespace(reason="safe_fallback_no_grounded_unresolved_target"),
            changes=[
                {
                    "source": "post_skill_health_gate",
                    "after": {"reason": "safe_fallback_no_grounded_unresolved_target"},
                }
            ],
        ),
    )
    assert policy_fallback_used(step)


def test_operational_metric_counts_conditional_memo_policy_fallback() -> None:
    step = SimpleNamespace(
        proposed_action=SimpleNamespace(reason="safe_fallback_conditional_memo_available"),
        action_decision=SimpleNamespace(
            final=SimpleNamespace(reason="safe_fallback_conditional_memo_available"),
            changes=[],
        ),
    )

    assert policy_fallback_used(step)


def test_prompt_skill_is_exposed_but_never_rewrites_scripted_policy_action() -> None:
    runner, policy, selector = _runner()
    skill = synthetic_skills()[0]
    first, second, final = policy.responses
    repeated = _policy(
        {"action_type": "ask", "target_id": "F1", "content": "合同是哪天签署的？"},
        [],
    )
    policy.responses = [first, repeated, repeated, repeated, final]
    trajectory = runner.run(
        raw_case=_case(),
        domain="insurance_contract",
        persona={"persona_id": "P_WD", "who": {"zh": "当事人"}, "voice": {"zh": "简短"}},
        skills=[skill],
        trajectory_id="traj_skill_repair",
        run_id="run_test",
        method="training_policy_sample",
        partition="training_round_01",
        seed=42,
        sample_index=0,
        max_turns=3,
        group_id="group_test",
        skill_library_version="fixture",
    )
    second_step = trajectory.steps[1]
    assert trajectory.domain == "insurance_contract"
    assert second_step.proposed_action.target_id == "F2"
    assert second_step.action_decision.final.target_id == "F2"
    assert trajectory.exposed_skill_ids == [skill.skill_id]
    assert second_step.action_decision.retrieved_skill_ids == [skill.skill_id]
    assert second_step.action_decision.activated_skill_ids == []
    assert not any(
        item.startswith(("repeated_fact_target", "ask_target_not_unresolved"))
        for item in second_step.post_skill_health_violations
    )
    assert not any(
        item.get("skill_id")
        for item in second_step.action_decision.changes
    )
    assert selector.responses == []


def test_prompt_skill_document_is_identical_in_every_policy_turn() -> None:
    runner, policy, _ = _runner()
    skill = synthetic_skills()[0]
    memory, expected_ids = render_skill_memory([skill], domain="insurance_contract")

    trajectory = runner.run(
        raw_case=_case(),
        domain="insurance_contract",
        persona={"persona_id": "P_WD", "who": {"zh": "当事人"}, "voice": {"zh": "简短"}},
        skills=[skill],
        trajectory_id="traj_prompt_memory_delivery",
        run_id="run_test",
        method="training_policy_sample",
        partition="training_batch_01",
        seed=42,
        sample_index=0,
        max_turns=3,
        group_id="group_prompt_memory_delivery",
        skill_library_version="fixture",
    )

    system_messages = [messages[0]["content"] for messages in policy.seen]
    assert len(system_messages) == len(trajectory.steps) == 3
    assert len(set(system_messages)) == 1
    assert all(memory in message for message in system_messages)
    assert all(skill.skill_id in message for message in system_messages)
    assert trajectory.exposed_skill_ids == expected_ids
    assert all(
        step.action_decision.retrieved_skill_ids == expected_ids for step in trajectory.steps
    )
    assert all('"active_skills"' not in messages[-1]["content"] for messages in policy.seen)


def test_training_allocation_guidance_does_not_corrupt_skill_memory_suffix() -> None:
    runner, _, _ = _runner()
    skill = synthetic_skills()[0]
    memory, expected_ids = render_skill_memory([skill], domain="insurance_contract")
    state = StateManager().initial(
        "training-guidance",
        "客户开场。",
        max_turns=24,
        domain="insurance_contract",
    )
    target = FactSlot(
        fact_id="contract_date",
        label="合同签署日期",
        status="unknown",
        criticality="high",
        target_kind="client_fact",
    )
    state = StateManager().merge(
        state,
        StatePatch(
            observations=[
                FactObservation(
                    fact_id=target.fact_id,
                    label=target.label,
                    status=target.status,
                    criticality=target.criticality,
                    target_kind=target.target_kind,
                )
            ]
        ),
        0,
    )

    messages = runner._visible_messages(
        "客户开场。",
        [],
        state,
        1,
        policy_method_guidance=memory,
        policy_sampling_guidance=counterfactual_target_guidance(target),
    )
    system_prompt = messages[0].content

    assert "训练期结构化反事实首问" in system_prompt
    assert system_prompt.endswith(memory)
    assert parse_rendered_skill_memory(
        extract_rendered_skill_memory(system_prompt)
    ) == expected_ids


def test_empty_library_policy_turns_contain_no_skill_document_or_legacy_state_field() -> None:
    runner, policy, _ = _runner()
    skill_id = synthetic_skills()[-1].skill_id
    empty_memory, expected_ids = render_skill_memory([], domain="insurance_contract")

    trajectory = runner.run(
        raw_case=_case(),
        domain="insurance_contract",
        persona={"persona_id": "P_WD", "who": {"zh": "当事人"}, "voice": {"zh": "简短"}},
        skills=[],
        trajectory_id="traj_empty_prompt_memory",
        run_id="run_test",
        method="training_policy_sample",
        partition="training_batch_01",
        seed=42,
        sample_index=0,
        max_turns=3,
        group_id="group_empty_prompt_memory",
        skill_library_version="empty",
    )

    system_messages = [messages[0]["content"] for messages in policy.seen]
    assert len(system_messages) == len(trajectory.steps) == 3
    assert len(set(system_messages)) == 1
    assert all(empty_memory in message for message in system_messages)
    assert all(skill_id not in message for message in system_messages)
    assert trajectory.exposed_skill_ids == expected_ids == []
    assert all(step.action_decision.retrieved_skill_ids == [] for step in trajectory.steps)
    assert all('"active_skills"' not in messages[-1]["content"] for messages in policy.seen)


class ScriptedJudge:
    model = "judge-test"

    def __init__(self, values: list[dict]) -> None:
        self.values = list(values)
        self.calls: list[str] = []
        self.user_prompts: list[str] = []

    def generate_json(self, *, purpose, system_prompt, user_prompt, output_schema):
        self.calls.append(purpose)
        self.user_prompts.append(user_prompt)
        return SimpleNamespace(
            value=self.values.pop(0),
            model=self.model,
            request_sha256=f"request-{purpose}",
            response_sha256=f"response-{purpose}",
        )


class FirstRubricSchemaFailureJudge(ScriptedJudge):
    def generate_json(self, *, purpose, system_prompt, user_prompt, output_schema):
        if purpose == "semantic_rubric":
            self.calls.append(purpose)
            self.user_prompts.append(user_prompt)
            raise StructuredModelInvocationError("memo_expectation_scores is too long")
        return super().generate_json(
            purpose=purpose,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            output_schema=output_schema,
        )


class FirstTwoFactInvocationFailuresJudge(ScriptedJudge):
    """Emulate one complete fact unit exhausting both bounded attempts."""

    def __init__(self, values: list[dict]) -> None:
        super().__init__(values)
        self.fact_calls = 0

    def generate_json(self, *, purpose, system_prompt, user_prompt, output_schema):
        if purpose.startswith("semantic_facts"):
            self.calls.append(purpose)
            self.user_prompts.append(user_prompt)
            self.fact_calls += 1
            if self.fact_calls <= 2:
                raise StructuredModelInvocationError("finish_reason='length'")
            fact_ids = output_schema["properties"]["facts"]["required"]
            return SimpleNamespace(
                value={
                    "facts": {
                        fact_id: {
                            "discovery": "covered",
                            "accuracy": "correct",
                            "substantive_discovery": "covered",
                            "substantive_accuracy": "correct",
                            "memo_excerpt": fact_id,
                            "reason": "测试",
                        }
                        for fact_id in fact_ids
                    }
                },
                model=self.model,
                request_sha256=f"request-facts-{self.fact_calls}",
                response_sha256=f"response-facts-{self.fact_calls}",
            )
        if purpose.startswith("semantic_grounding"):
            self.calls.append(purpose)
            self.user_prompts.append(user_prompt)
            claim_ids = output_schema["properties"]["claims"]["required"]
            return SimpleNamespace(
                value={
                    "claims": {
                        claim_id: {
                            "classification": "grounded",
                            "basis": "案件事实或对话",
                        }
                        for claim_id in claim_ids
                    }
                },
                model=self.model,
                request_sha256="request-grounding",
                response_sha256="response-grounding",
            )
        return super().generate_json(
            purpose=purpose,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            output_schema=output_schema,
        )


class SchemaDrivenGroundingJudge(ScriptedJudge):
    """Return exhaustive chunk decisions from the exact schema under test."""

    def generate_json(self, *, purpose, system_prompt, user_prompt, output_schema):
        if purpose == "semantic_grounding":
            self.calls.append(purpose)
            self.user_prompts.append(user_prompt)
            claim_ids = output_schema["properties"]["claims"]["required"]
            chunk_number = sum(item == "semantic_grounding" for item in self.calls)
            return SimpleNamespace(
                value={
                    "claims": {
                        claim_id: {
                            "classification": "grounded",
                            "basis": "案件事实或对话",
                        }
                        for claim_id in claim_ids
                    }
                },
                model=self.model,
                request_sha256=f"request-grounding-{chunk_number}",
                response_sha256=f"response-grounding-{chunk_number}",
            )
        return super().generate_json(
            purpose=purpose,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            output_schema=output_schema,
        )


class FirstTwoGroundingInvocationFailuresJudge(ScriptedJudge):
    """Emulate a primary and first repair that exhaust their output budgets."""

    def __init__(self, values: list[dict]) -> None:
        super().__init__(values)
        self.grounding_calls = 0

    def generate_json(self, *, purpose, system_prompt, user_prompt, output_schema):
        if purpose.startswith("semantic_grounding"):
            self.calls.append(purpose)
            self.user_prompts.append(user_prompt)
            self.grounding_calls += 1
            if self.grounding_calls <= 2:
                raise StructuredModelInvocationError("finish_reason='length'")
            claim_ids = output_schema["properties"]["claims"]["required"]
            return SimpleNamespace(
                value={
                    "claims": {
                        claim_id: {
                            "classification": "grounded",
                            "basis": "案件事实或对话",
                        }
                        for claim_id in claim_ids
                    }
                },
                model=self.model,
                request_sha256="request-grounding-second-repair",
                response_sha256="response-grounding-second-repair",
            )
        return super().generate_json(
            purpose=purpose,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            output_schema=output_schema,
        )


def test_rubric_schema_freezes_case_specific_array_lengths() -> None:
    properties = rubric_judgment_schema(6, 5)["properties"]
    assert properties["expected_action_scores"]["minItems"] == 6
    assert properties["expected_action_scores"]["maxItems"] == 6
    assert properties["memo_expectation_scores"]["minItems"] == 5
    assert properties["memo_expectation_scores"]["maxItems"] == 5


def test_paired_inquiry_scores_cannot_lose_credit_under_exact_question_extension() -> None:
    reconciled, inherited = monotone_expected_action_scores(
        ["是否已经向保险人披露健康情况？"],
        [
            "是否已经向保险人披露健康情况？",
            "拒赔通知援引了哪项条款？",
        ],
        [1, 0, 0],
        [0, 1, 0],
    )
    assert reconciled == [1, 1, 0]
    assert inherited == [0]


def test_paired_inquiry_scores_are_untouched_without_exact_question_prefix() -> None:
    reconciled, inherited = monotone_expected_action_scores(
        ["基线问题"],
        ["经过技能改写的问题"],
        [1, 0],
        [0, 1],
    )
    assert reconciled == [0, 1]
    assert inherited == []


def test_claim_chunking_preserves_exact_ids_order_and_text() -> None:
    spans = {f"C{index:03d}": f"主张{index}。" for index in range(1, 16)}
    chunks = chunk_claim_spans(spans, 6)
    assert [list(chunk) for chunk in chunks] == [
        [f"C{index:03d}" for index in range(1, 7)],
        [f"C{index:03d}" for index in range(7, 13)],
        [f"C{index:03d}" for index in range(13, 16)],
    ]
    assert {key: value for chunk in chunks for key, value in chunk.items()} == spans


def test_semantic_grounding_uses_bounded_chunks_and_records_complete_trace() -> None:
    runner, _, _ = _runner()
    trajectory = runner.run(
        raw_case=_case(),
        persona={"persona_id": "P_WD", "who": {"zh": "当事人"}, "voice": {"zh": "简短"}},
        skills=[],
        trajectory_id="traj_chunked_grounding",
        run_id="run_test",
        method="training_policy_sample",
        partition="training_round_01",
        seed=42,
        sample_index=0,
        max_turns=3,
        group_id="group_test",
        skill_library_version="empty",
    )
    trajectory.memo = "\n".join(f"客户陈述事项{index}。" for index in range(1, 16))
    rubric = {
        "memo_expectation_scores": [1],
        "expected_action_scores": [1],
        "analysis": "完整",
    }
    facts = {
        "facts": {
            fact_id: {
                "discovery": "covered",
                "accuracy": "correct",
                "substantive_discovery": "covered",
                "substantive_accuracy": "correct",
                "memo_excerpt": fact_id,
                "reason": "测试",
            }
            for fact_id in ("F1", "F2")
        }
    }
    judge = SchemaDrivenGroundingJudge([rubric, facts])
    evaluation = SemanticEvaluator(
        judge,
        "blind judge",
        judge_qualification_contract_sha256="a" * 64,
        reward_parameters=TEST_REWARD_PARAMETERS,
        max_attempts=2,
        grounding_claims_per_call=6,
    ).evaluate(trajectory, _case())
    assert judge.calls == [
        "semantic_rubric",
        "semantic_facts",
        "semantic_grounding",
        "semantic_grounding",
        "semantic_grounding",
    ]
    assert [len(trace.claim_ids) for trace in evaluation.grounding_chunks] == [6, 6, 3]
    assert [
        claim_id for trace in evaluation.grounding_chunks for claim_id in trace.claim_ids
    ] == list(memo_claim_spans(trajectory.memo))
    assert all(trace.attempts == 1 for trace in evaluation.grounding_chunks)
    assert evaluation.grounding_repair_used is False
    assert evaluation.official_metrics.fidelity == 1.0


def test_semantic_grounding_second_bounded_repair_is_distinct_and_audited() -> None:
    runner, _, _ = _runner()
    trajectory = runner.run(
        raw_case=_case(),
        persona={"persona_id": "P_WD", "who": {"zh": "当事人"}, "voice": {"zh": "简短"}},
        skills=[],
        trajectory_id="traj_grounding_second_repair",
        run_id="run_test",
        method="training_policy_sample",
        partition="training_round_01",
        seed=42,
        sample_index=0,
        max_turns=3,
        group_id="group_test",
        skill_library_version="empty",
    )
    trajectory.memo = "客户已经付款。"
    rubric = {
        "memo_expectation_scores": [1],
        "expected_action_scores": [1],
        "analysis": "完整",
    }
    facts = {
        "facts": {
            fact_id: {
                "discovery": "covered",
                "accuracy": "correct",
                "substantive_discovery": "covered",
                "substantive_accuracy": "correct",
                "memo_excerpt": fact_id,
                "reason": "测试",
            }
            for fact_id in ("F1", "F2")
        }
    }
    judge = FirstTwoGroundingInvocationFailuresJudge([rubric, facts])
    evaluation = SemanticEvaluator(
        judge,
        "blind judge",
        judge_qualification_contract_sha256="a" * 64,
        reward_parameters=TEST_REWARD_PARAMETERS,
        max_attempts=3,
        grounding_claims_per_call=6,
    ).evaluate(trajectory, _case())
    assert judge.calls[-3:] == [
        "semantic_grounding",
        "semantic_grounding_repair",
        "semantic_grounding_repair",
    ]
    assert "第1次有界结构修复" in judge.user_prompts[-2]
    assert "第2次有界结构修复" in judge.user_prompts[-1]
    assert judge.user_prompts[-2] != judge.user_prompts[-1]
    assert evaluation.grounding_chunks[0].attempts == 3
    assert evaluation.grounding_repair_used is True


def test_semantic_grounding_subdivides_only_length_exhausted_multi_claim_unit() -> None:
    runner, _, _ = _runner()
    trajectory = runner.run(
        raw_case=_case(),
        persona={"persona_id": "P_WD", "who": {"zh": "当事人"}, "voice": {"zh": "简短"}},
        skills=[],
        trajectory_id="traj_grounding_adaptive_split",
        run_id="run_test",
        method="training_policy_sample",
        partition="training_round_01",
        seed=42,
        sample_index=0,
        max_turns=3,
        group_id="group_test",
        skill_library_version="empty",
    )
    trajectory.memo = "\n".join(f"客户陈述事项{index}。" for index in range(1, 4))
    rubric = {
        "memo_expectation_scores": [1],
        "expected_action_scores": [1],
        "analysis": "完整",
    }
    facts = {
        "facts": {
            fact_id: {
                "discovery": "covered",
                "accuracy": "correct",
                "substantive_discovery": "covered",
                "substantive_accuracy": "correct",
                "memo_excerpt": fact_id,
                "reason": "测试",
            }
            for fact_id in ("F1", "F2")
        }
    }
    judge = FirstTwoGroundingInvocationFailuresJudge([rubric, facts])
    evaluation = SemanticEvaluator(
        judge,
        "blind judge",
        judge_qualification_contract_sha256="a" * 64,
        reward_parameters=TEST_REWARD_PARAMETERS,
        max_attempts=2,
        grounding_claims_per_call=3,
    ).evaluate(trajectory, _case())
    assert judge.calls[-4:] == [
        "semantic_grounding",
        "semantic_grounding_repair",
        "semantic_grounding",
        "semantic_grounding",
    ]
    assert [trace.claim_ids for trace in evaluation.grounding_chunks] == [
        ["C001"],
        ["C002", "C003"],
    ]
    assert all(trace.attempts == 1 for trace in evaluation.grounding_chunks)
    assert evaluation.grounding_repair_used is True
    assert evaluation.grounding_normalizations == [
        "adaptive_length_split:1:C001,C002,C003->C001|C002,C003"
    ]
    assert evaluation.official_metrics.fidelity == 1.0


def test_semantic_facts_subdivide_only_length_exhausted_multi_fact_unit() -> None:
    runner, _, _ = _runner()
    trajectory = runner.run(
        raw_case=_case(),
        persona={"persona_id": "P_WD", "who": {"zh": "当事人"}, "voice": {"zh": "简短"}},
        skills=[],
        trajectory_id="traj_fact_adaptive_split",
        run_id="run_test",
        method="training_policy_sample",
        partition="training_round_01",
        seed=42,
        sample_index=0,
        max_turns=3,
        group_id="group_test",
        skill_library_version="empty",
    )
    rubric = {
        "memo_expectation_scores": [1],
        "expected_action_scores": [1],
        "analysis": "完整",
    }
    judge = FirstTwoFactInvocationFailuresJudge([rubric])
    evaluation = SemanticEvaluator(
        judge,
        "blind judge",
        judge_qualification_contract_sha256="a" * 64,
        reward_parameters=TEST_REWARD_PARAMETERS,
        max_attempts=2,
        grounding_claims_per_call=6,
    ).evaluate(trajectory, _case())
    assert judge.calls[:5] == [
        "semantic_rubric",
        "semantic_facts",
        "semantic_facts_repair",
        "semantic_facts",
        "semantic_facts",
    ]
    assert [trace.fact_ids for trace in evaluation.fact_chunks] == [["F1"], ["F2"]]
    assert all(trace.attempts == 1 for trace in evaluation.fact_chunks)
    assert evaluation.fact_repair_used is True
    assert evaluation.fact_normalizations == [
        "adaptive_length_split:1:F1,F2->F1|F2"
    ]
    assert evaluation.official_metrics.fact_coverage == 1.0


def test_grounding_prompt_distinguishes_attribution_from_verification() -> None:
    fact_prompt = build_fact_judgment_prompt(
        _case(),
        "客户（开场）：我称已经支付了10万元。",
        "据客户陈述，其已经支付10万元，但付款凭证尚待核验。",
    )
    prompt = build_official_grounding_judgment_prompt(
        _case(),
        "客户（开场）：我称已经支付了10万元。",
        "据客户陈述，其已经支付10万元，但付款凭证尚待核验。",
    )
    assert "案件事实或完整对话任一处" in prompt
    assert "客户提出问题、律师追问或客户表示不知道" in prompt
    assert "grounded、unsupported、non_claim" not in prompt
    assert "classification只有三类" in prompt
    assert "non_claim" in prompt
    assert "没有标注引文" in prompt
    assert "分析某项边界" in prompt
    assert "不能因为案件材料没有直接" in prompt
    assert "分析表明某事实已发生" in prompt
    assert "分别核对行为主体、相对方、行为、对象和法律方向" in fact_prompt
    assert "把甲实施的行为写成乙实施" in fact_prompt
    assert "Accuracy的正确性基准是案件记录，不是客户认知" in fact_prompt
    assert "逐字陈述案件记录" in fact_prompt
    assert "不要求每个事实都附带独立法律分析" in fact_prompt
    assert "Discovery与Accuracy必须正交" in fact_prompt
    assert "实质missed只用于没有具体命题的话题占位" in fact_prompt
    assert "不输出grounded_claims" in fact_prompt
    assert "客户（开场）：我称已经支付了10万元。" in prompt


def test_keyed_fact_schema_requires_every_fact_and_has_no_parallel_partitions() -> None:
    schema = fact_judgment_schema({"F2", "F1"})
    facts = schema["properties"]["facts"]
    assert facts["required"] == ["F1", "F2"]
    assert facts["additionalProperties"] is False
    assert "covered_fact_ids" not in schema["properties"]
    parsed, changes = parse_fact_judgment(
        {
            "facts": {
                "F1": {
                    "discovery": "covered",
                    "accuracy": "correct",
                    "substantive_discovery": "missed",
                    "substantive_accuracy": "not_applicable",
                    "memo_excerpt": "",
                    "reason": "",
                },
                "F2": {
                    "discovery": "missed",
                    "accuracy": "not_applicable",
                    "substantive_discovery": "covered",
                    "substantive_accuracy": "incorrect",
                    "memo_excerpt": "",
                    "reason": "",
                },
            },
            "grounded_claims": [],
            "unsupported_claims": [],
        },
        {"F1", "F2"},
    )
    assert parsed.covered_fact_ids == ["F1"]
    assert parsed.missed_fact_ids == ["F2"]
    assert parsed.substantive_covered_fact_ids == ["F2"]
    assert parsed.substantive_incorrect_fact_ids == ["F2"]
    assert changes == []


def test_fact_wire_contract_rejects_verbatim_record_miss() -> None:
    case = _case()
    value = {
        "facts": {
            fact["fact_id"]: {
                "discovery": "missed",
                "accuracy": "not_applicable",
                "substantive_discovery": "missed",
                "substantive_accuracy": "not_applicable",
                "memo_excerpt": "",
                "reason": "",
            }
            for fact in case["facts"]
        }
    }
    memo = case["facts"][0]["court_record"]
    issues = fact_wire_contract_issues(value, case, memo)
    assert any(item.startswith("F1:verbatim_court_record_misclassified:") for item in issues)


def test_fact_wire_contract_rejects_missed_reason_that_describes_inversion() -> None:
    case = _case()
    value = {
        "facts": {
            fact["fact_id"]: {
                "discovery": "missed",
                "accuracy": "not_applicable",
                "substantive_discovery": "missed",
                "substantive_accuracy": "not_applicable",
                "memo_excerpt": "",
                "reason": (
                    "Memo incorrectly states that the client performed the act."
                    if fact["fact_id"] == "F1"
                    else "memo没有涉及该事实"
                ),
            }
            for fact in case["facts"]
        }
    }
    issues = fact_wire_contract_issues(value, case, "客户实施了相关行为。")
    assert "F1:missed_reason_describes_incorrect_proposition" in issues


def test_fact_wire_contract_does_not_confuse_incorrect_ruling_with_incorrect_memo() -> None:
    case = _case()
    case["facts"][0]["court_record"] = "虚假材料导致部分错误执行异议裁定"
    value = {
        "facts": {
            fact["fact_id"]: {
                "discovery": "missed",
                "accuracy": "not_applicable",
                "substantive_discovery": "missed",
                "substantive_accuracy": "not_applicable",
                "memo_excerpt": "",
                "reason": (
                    "memo未提及虚假材料导致的错误裁定"
                    if fact["fact_id"] == "F1"
                    else "memo没有涉及该事实"
                ),
            }
            for fact in case["facts"]
        }
    }

    assert fact_wire_contract_issues(value, case, "未形成关于相关裁定的判断。") == []


def test_fact_wire_contract_rejects_explicit_chinese_memo_inversion() -> None:
    case = _case()
    value = {
        "facts": {
            fact["fact_id"]: {
                "discovery": "missed",
                "accuracy": "not_applicable",
                "substantive_discovery": "missed",
                "substantive_accuracy": "not_applicable",
                "memo_excerpt": "",
                "reason": (
                    "备忘录的结论与案情事实相反"
                    if fact["fact_id"] == "F1"
                    else "memo没有涉及该事实"
                ),
            }
            for fact in case["facts"]
        }
    }

    assert "F1:missed_reason_describes_incorrect_proposition" in (
        fact_wire_contract_issues(value, case, "客户实施了相关行为。")
    )


def test_grounding_wire_contract_rejects_claim_absent_from_memo() -> None:
    value = {
        "visible_grounded_claims": [{"claim": "memo真实原文", "basis": "客户开场"}],
        "benchmark_only_grounded_claims": [{"claim": "由隐藏事实反向生成的句子", "basis": "F2"}],
        "unsupported_claims": [],
    }
    assert grounding_wire_contract_issues(value, "memo真实原文。") == [
        "benchmark_only_grounded_claims[0]:claim_not_verbatim_memo_excerpt"
    ]


def test_keyed_grounding_schema_freezes_and_exhaustively_classifies_memo_spans() -> None:
    spans = memo_claim_spans("客户已经付款。\n若合同无效，需另行评估。")
    assert spans == {
        "C001": "客户已经付款。",
        "C002": "若合同无效，需另行评估。",
    }
    schema = grounding_judgment_schema(spans)
    assert schema["properties"]["claims"]["required"] == ["C001", "C002"]
    visible, benchmark_only, unsupported = parse_grounding_judgment(
        {
            "claims": {
                "C001": {
                    "classification": "visible_grounded",
                    "basis": "客户开场",
                },
                "C002": {"classification": "non_claim", "basis": "未断言的条件分析"},
            }
        },
        spans,
    )
    assert [item.claim for item in visible] == ["客户已经付款。"]
    assert benchmark_only == []
    assert unsupported == []


def test_memo_claim_spans_excludes_only_fixed_document_structure() -> None:
    spans = memo_claim_spans(
        "<!-- typed_fact_ledger -->\n"
        "**案情概要**\n"
        "客户称已经付款。\n"
        "**风险评估**\n"
        "若合同无效，仍需另行评估。\n"
        "<!-- /typed_fact_ledger -->"
    )
    assert spans == {
        "C001": "客户称已经付款。",
        "C002": "若合同无效，仍需另行评估。",
    }


def test_topic_only_discovery_is_audited_as_unresolved_not_incorrect() -> None:
    result, changes = parse_fact_judgment(
        {
            "facts": {
                "F1": {
                    "discovery": "covered",
                    "accuracy": "not_applicable",
                    "substantive_discovery": "missed",
                    "substantive_accuracy": "not_applicable",
                    "memo_excerpt": "房屋是否属于夫妻共同财产",
                    "reason": "只提出问题，没有形成可判断真假的事实命题",
                }
            }
        },
        {"F1"},
    )
    assert changes == []
    assert result.covered_fact_ids == ["F1"]
    assert result.correct_fact_ids == []
    assert result.incorrect_facts == []
    assert result.unresolved_fact_ids == ["F1"]
    assert result.substantive_missed_fact_ids == ["F1"]


def test_official_grounding_schema_uses_case_or_dialogue_union() -> None:
    spans = memo_claim_spans("客户已经付款。\n尚需核验担保人涉诉详情。")
    schema = official_grounding_judgment_schema(spans)
    assert schema["properties"]["claims"]["required"] == ["C001", "C002"]
    grounded, unsupported = parse_official_grounding_judgment(
        {
            "claims": {
                "C001": {"classification": "grounded", "basis": "F1或客户开场"},
                "C002": {"classification": "non_claim", "basis": "信息缺口提示"},
            }
        },
        spans,
    )
    assert [item.claim for item in grounded] == ["客户已经付款。"]
    assert unsupported == []


def test_exact_attributed_client_answer_normalization_is_narrow_and_audited() -> None:
    spans = memo_claim_spans(
        "据客户在咨询中的单方陈述：公司向我借款300万元。\n"
        "据客户陈述：公司向我借款300万元，因此法院已经判我胜诉。"
    )
    value = {
        "claims": {
            "C001": {"classification": "unsupported", "basis": ""},
            "C002": {"classification": "unsupported", "basis": ""},
        }
    }
    normalized, changes = normalize_exact_visible_grounding(
        value,
        spans,
        "律师（第1轮）：借款情况？\n客户：公司向我借款300万元。",
    )
    assert normalized["claims"]["C001"]["classification"] == "visible_grounded"
    assert normalized["claims"]["C002"]["classification"] == "unsupported"
    assert changes == ["C001:exact_attributed_client_answer"]
    assert value["claims"]["C001"]["classification"] == "unsupported"


def test_official_grounding_normalizes_exact_disputed_answer_and_open_issue() -> None:
    spans = memo_claim_spans(
        "- 客户本轮陈述（尚未独立核验）：按我的理解，法院不能一并审理。\n"
        "2. 该请求是否可以一并审理；\n"
        "3. 投保时健康告知是否涉及客户所称疾病；\n"
        "现在工程款被拖欠。\n"
        "客户已经获得赔偿。"
    )
    value = {
        "claims": {
            "C001": {"classification": "unsupported", "basis": "与案件真值相反"},
            "C002": {"classification": "unsupported", "basis": "未找到一并审理事实"},
            "C003": {"classification": "unsupported", "basis": "误将客户所称当成客户陈述"},
            "C004": {"classification": "unsupported", "basis": "忽略开场"},
            "C005": {"classification": "unsupported", "basis": "无来源"},
        }
    }
    normalized, changes = normalize_official_grounding_contract(
        value,
        spans,
        "律师（第1轮）：您怎么理解？\n"
        "客户：按我的理解，法院不能一并审理。\n"
        "客户（开场）：现在工程款被拖欠。",
    )
    assert normalized["claims"]["C001"]["classification"] == "grounded"
    assert normalized["claims"]["C002"]["classification"] == "non_claim"
    assert normalized["claims"]["C003"]["classification"] == "non_claim"
    assert normalized["claims"]["C004"]["classification"] == "grounded"
    assert normalized["claims"]["C005"]["classification"] == "unsupported"
    assert changes == [
        "C001:exact_attributed_client_answer_from_unsupported",
        "C002:explicit_nonclaim_from_unsupported",
        "C003:explicit_nonclaim_from_unsupported",
        "C004:exact_client_clause_from_unsupported",
    ]
    assert value["claims"]["C001"]["classification"] == "unsupported"


def test_belief_as_fact_ignores_typed_attribution_but_catches_model_assertion() -> None:
    case = {
        "facts": [
            {
                "fact_id": "F1",
                "gap_type": "disputed",
                "client_belief": "法院不能在交通事故赔偿案中一并审理。",
                "court_record": "法院可以一并审理。",
            }
        ]
    }
    ledger = (
        "<!-- typed_fact_ledger -->\n"
        "- 客户本轮陈述（尚未独立核验）：法院不能在交通事故赔偿案中一并审理。\n"
        "<!-- /typed_fact_ledger -->"
    )
    assert _belief_as_fact_rate(SimpleNamespace(memo=ledger), case) == 0.0
    categorical = ledger + "\n风险评估\n法院不能在交通事故赔偿案中一并审理。"
    assert _belief_as_fact_rate(SimpleNamespace(memo=categorical), case) == 1.0


def test_semantic_judge_repairs_bad_partition_and_computes_official_metrics() -> None:
    runner, _, _ = _runner()
    trajectory = runner.run(
        raw_case=_case(),
        persona={"persona_id": "P_WD", "who": {"zh": "当事人"}, "voice": {"zh": "简短"}},
        skills=[],
        trajectory_id="traj_eval",
        run_id="run_test",
        method="training_policy_sample",
        partition="training_round_01",
        seed=42,
        sample_index=0,
        max_turns=3,
        group_id="group_test",
        skill_library_version="empty",
    )
    rubric = {
        "memo_expectation_scores": [1],
        "expected_action_scores": [1],
        "analysis": "完整",
    }
    invalid_facts = {
        "covered_fact_ids": ["F1"],
        "missed_fact_ids": [],
        "correct_fact_ids": ["F1"],
        "incorrect_facts": [],
        "grounded_claims": [
            {"claim": "主张一", "basis": "F1"},
            {"claim": "主张二", "basis": "F2"},
        ],
        "unsupported_claims": [],
    }
    valid_facts = {
        "facts": {
            "F1": {
                "discovery": "covered",
                "accuracy": "correct",
                "substantive_discovery": "covered",
                "substantive_accuracy": "correct",
                "memo_excerpt": "F1",
                "reason": "明确陈述",
            },
            "F2": {
                "discovery": "covered",
                "accuracy": "correct",
                "substantive_discovery": "missed",
                "substantive_accuracy": "not_applicable",
                "memo_excerpt": "相关话题",
                "reason": "只有话题占位",
            },
        },
    }
    claim_spans = memo_claim_spans(trajectory.memo)
    grounding = {
        "claims": {
            claim_id: {"classification": "grounded", "basis": "F1或对话"}
            for claim_id in claim_spans
        }
    }
    judge = ScriptedJudge([rubric, invalid_facts, valid_facts, grounding])
    result = SemanticEvaluator(
        judge,
        "blind judge",
        judge_qualification_contract_sha256="a" * 64,
        reward_parameters=TEST_REWARD_PARAMETERS,
        max_attempts=2,
    ).evaluate(trajectory, _case())
    assert judge.calls == [
        "semantic_rubric",
        "semantic_facts",
        "semantic_facts_repair",
        "semantic_grounding",
    ]
    fact_prompt = judge.user_prompts[1]
    assert "预期追问共有1项" in judge.user_prompts[0]
    assert "memo评分点共有1项" in judge.user_prompts[0]
    assert "仅在对话出现而memo未涉及仍算missed" in fact_prompt
    assert "不输出grounded_claims" in fact_prompt
    assert "案件事实或完整对话" in judge.user_prompts[3]
    assert "明确引入且没有断言条件已经发生的条件分析" in judge.user_prompts[3]
    assert "missing_discovery_ids=['F2']" in judge.user_prompts[2]
    assert result.fact_repair_used is True
    assert result.fact_normalizations == []
    assert result.official_metrics.model_dump() == {
        "fact_coverage": 1.0,
        "inquiry": 1.0,
        "elicitation": 1.0,
        "fact_resolution": 1.0,
        "issue_resolution": 1.0,
        "resolution": 1.0,
        "fidelity": 1.0,
    }
    assert result.training_metrics.model_dump() == {
        "substantive_fact_coverage": 1.0,
        "inquiry": 1.0,
        "elicitation": 1.0,
        "substantive_fact_resolution": 0.5,
        "issue_resolution": 1.0,
        "resolution": 0.75,
    }
    assert result.training_fact_provenance.model_dump() == {
        "elicited_hidden_fact_ids": ["F1", "F2"],
        "resolved_elicited_fact_ids": ["F1"],
        "memo_only_substantive_fact_ids": [],
    }
    assert result.safety_metrics.hidden_field_leak is False
    # DLawBench Fidelity treats either case facts or dialogue as a valid source.
    # Benchmark-only support remains auditable but is not a hallucination penalty.
    assert result.safety_metrics.unsupported_claim_rate == 0.0
    assert result.fact_judgment.benchmark_only_grounded_claims == []
    assert result.operational_metrics.model_dump() == {
        "policy_repair_rate": 0.0,
        "policy_fallback_rate": 0.0,
        "client_repair_rate": 0.0,
        "client_fallback_rate": 0.0,
        "memo_retry": False,
        "memo_guardrail_intervention": False,
        "memo_fallback": False,
    }


def test_training_fact_credit_is_locked_to_online_disclosure_provenance() -> None:
    runner, _, _ = _runner()
    trajectory = runner.run(
        raw_case=_case(),
        persona={"persona_id": "P_WD", "who": {"zh": "当事人"}, "voice": {"zh": "简短"}},
        skills=[],
        trajectory_id="traj_provenance_locked",
        run_id="run_test",
        method="training_policy_sample",
        partition="training_round_01",
        seed=42,
        sample_index=0,
        max_turns=3,
        group_id="group_test",
        skill_library_version="empty",
    )
    # The memo still mentions both benchmark facts, but the persisted online trace
    # contains only the first disclosure.  Official DLawBench memo discovery may
    # credit both; evolution must not reward the unelicited F2.
    trajectory.steps = [trajectory.steps[0], trajectory.steps[-1]]
    rubric = {
        "memo_expectation_scores": [1],
        "expected_action_scores": [1],
        "analysis": "完整",
    }
    facts = {
        "facts": {
            fact_id: {
                "discovery": "covered",
                "accuracy": "correct",
                "substantive_discovery": "covered",
                "substantive_accuracy": "correct",
                "memo_excerpt": fact_id,
                "reason": "memo明确写到",
            }
            for fact_id in ("F1", "F2")
        }
    }
    grounding = {
        "claims": {
            claim_id: {"classification": "grounded", "basis": "案件事实或对话"}
            for claim_id in memo_claim_spans(trajectory.memo)
        }
    }
    result = SemanticEvaluator(
        ScriptedJudge([rubric, facts, grounding]),
        "blind judge",
        judge_qualification_contract_sha256="a" * 64,
        reward_parameters=TEST_REWARD_PARAMETERS,
        max_attempts=2,
    ).evaluate(trajectory, _case())
    assert result.official_metrics.fact_coverage == 1.0
    assert result.training_metrics.substantive_fact_coverage == 0.5
    assert result.training_metrics.substantive_fact_resolution == 0.5
    assert result.training_fact_provenance.model_dump() == {
        "elicited_hidden_fact_ids": ["F1"],
        "resolved_elicited_fact_ids": ["F1"],
        "memo_only_substantive_fact_ids": ["F2"],
    }


def test_semantic_judge_deduplicates_fact_ids_without_rejudging() -> None:
    runner, _, _ = _runner()
    trajectory = runner.run(
        raw_case=_case(),
        persona={"persona_id": "P_WD", "who": {"zh": "当事人"}, "voice": {"zh": "简短"}},
        skills=[],
        trajectory_id="traj_duplicate_fact",
        run_id="run_test",
        method="training_policy_sample",
        partition="training_round_01",
        seed=42,
        sample_index=0,
        max_turns=3,
        group_id="group_test",
        skill_library_version="empty",
    )
    judge = ScriptedJudge(
        [
            {
                "memo_expectation_scores": [1],
                "expected_action_scores": [1],
                "analysis": "完整",
            },
            {
                "covered_fact_ids": ["F1"],
                "missed_fact_ids": ["F2"],
                "correct_fact_ids": [],
                "incorrect_facts": [
                    {"fact_id": "F1", "memo_excerpt": "原文", "reason": "理由一"},
                    {"fact_id": "F1", "memo_excerpt": "原文", "reason": "理由二"},
                ],
                "grounded_claims": [{"claim": "主张", "basis": "F1"}],
                "unsupported_claims": [],
            },
            {
                "claims": {
                    claim_id: {"classification": "grounded", "basis": "F1"}
                    for claim_id in memo_claim_spans(trajectory.memo)
                }
            },
        ]
    )
    result = SemanticEvaluator(
        judge,
        "blind judge",
        judge_qualification_contract_sha256="a" * 64,
        reward_parameters=TEST_REWARD_PARAMETERS,
        max_attempts=2,
    ).evaluate(trajectory, _case())
    assert judge.calls == ["semantic_rubric", "semantic_facts", "semantic_grounding"]
    assert result.fact_repair_used is False
    assert result.fact_normalizations == ["incorrect_facts:removed_duplicate:F1"]
    assert len(result.fact_judgment.incorrect_facts) == 1
    assert result.fact_judgment.incorrect_facts[0].reason == "理由一"
    assert result.official_metrics.fact_coverage == 0.5
    assert result.official_metrics.fact_resolution == 0.0


def test_semantic_judge_repairs_schema_invocation_failure() -> None:
    runner, _, _ = _runner()
    trajectory = runner.run(
        raw_case=_case(),
        persona={"persona_id": "P_WD", "who": {"zh": "当事人"}, "voice": {"zh": "简短"}},
        skills=[],
        trajectory_id="traj_schema_repair",
        run_id="run_test",
        method="training_policy_sample",
        partition="training_round_01",
        seed=42,
        sample_index=0,
        max_turns=3,
        group_id="group_test",
        skill_library_version="empty",
    )
    rubric = {
        "memo_expectation_scores": [1],
        "expected_action_scores": [1],
        "analysis": "完整",
    }
    facts = {
        "covered_fact_ids": ["F1", "F2"],
        "missed_fact_ids": [],
        "correct_fact_ids": ["F1", "F2"],
        "incorrect_facts": [],
        "grounded_claims": [{"claim": "主张", "basis": "F1、F2"}],
        "unsupported_claims": [],
    }
    grounding = {
        "claims": {
            claim_id: {"classification": "grounded", "basis": "F1、F2"}
            for claim_id in memo_claim_spans(trajectory.memo)
        }
    }
    judge = FirstRubricSchemaFailureJudge([rubric, facts, grounding])
    result = SemanticEvaluator(
        judge,
        "blind judge",
        judge_qualification_contract_sha256="a" * 64,
        reward_parameters=TEST_REWARD_PARAMETERS,
        max_attempts=2,
    ).evaluate(trajectory, _case())
    assert judge.calls == [
        "semantic_rubric",
        "semantic_rubric_repair",
        "semantic_facts",
        "semantic_grounding",
    ]
    assert "expected_action_scores只输出1项" in judge.user_prompts[1]
    assert result.official_metrics.resolution == 1.0


def _resume_trajectory(**updates: object) -> ResearchTrajectory:
    value: dict[str, object] = {
        "trajectory_id": "traj_resume",
        "group_id": "training_batch_01.case_test.P_WD.seed_42",
        "sample_index": 0,
        "run_id": "run_resume",
        "method": "training_policy_sample",
        "partition": "training_batch_01",
        "case_id": "case_test",
        "domain": "civil",
        "persona": "P_WD",
        "seed": 42,
        "model_id": "model/test",
        "model_revision": "revision-1",
        "skill_library_version": "empty",
        "skill_delivery_mode": "none",
        "exposed_skill_ids": [],
        "skill_memory_sha256": "a" * 64,
        "status": "memo_submitted",
        "opening": "测试开场。",
        "max_turns": 6,
        "steps": [],
        "memo": "测试备忘录。",
        "elapsed_seconds": 1.0,
        "created_at": "2026-08-23T00:00:00+00:00",
    }
    value.update(updates)
    return ResearchTrajectory.model_validate(value)


def _resume_executor(tmp_path: Path) -> MainExperimentExecutor:
    executor = object.__new__(MainExperimentExecutor)
    executor.run_id = "run_resume"
    executor.store = RunStore(tmp_path, executor.run_id)
    executor.experiment = {"emergency_turn_ceiling": 6}
    return executor


def _resume_call(executor: MainExperimentExecutor, runner: SimpleNamespace) -> ResearchTrajectory:
    adapter = SimpleNamespace(
        evaluator_case=lambda case_id: {"id": case_id},
        case_domain=lambda _case_id: "civil",
    )
    return MainExperimentExecutor._load_or_run(
        executor,
        runner=runner,
        adapter=adapter,
        case_id="case_test",
        persona={"persona_id": "P_WD"},
        skills=[],
        trajectory_id="traj_resume",
        method="training_policy_sample",
        partition="training_batch_01",
        seed=42,
        sample_index=0,
        group_id="training_batch_01.case_test.P_WD.seed_42",
        skill_hash="empty",
    )


@pytest.mark.parametrize(
    ("field", "drifted_value"),
    [
        ("trajectory_id", "traj_other"),
        ("run_id", "run_other"),
        ("partition", "training_batch_02"),
        ("method", "control_no_library"),
        ("case_id", "case_other"),
        ("persona", "P_WS"),
        ("seed", 43),
        ("sample_index", 1),
        ("group_id", "group_other"),
        ("skill_library_version", "library_other"),
        ("model_id", "model/other"),
        ("model_revision", "revision-other"),
    ],
)
def test_resume_rejects_every_non_error_trajectory_identity_drift(
    tmp_path: Path, field: str, drifted_value: object
) -> None:
    executor = _resume_executor(tmp_path)
    path = executor.store.trajectory_path("training_batch_01", "traj_resume")
    executor.store.save_model(path, _resume_trajectory(**{field: drifted_value}))

    def unexpected_run(**_kwargs: object) -> ResearchTrajectory:
        raise AssertionError("identity drift must be refused, not silently rerun")

    runner = SimpleNamespace(
        policy_client=SimpleNamespace(model="model/test"),
        model_revision="revision-1",
        run=unexpected_run,
    )
    with pytest.raises(ExecutionError, match="resume identity drift") as caught:
        _resume_call(executor, runner)
    assert field in str(caught.value)


def test_resume_reuses_only_an_exact_non_error_trajectory_identity(tmp_path: Path) -> None:
    executor = _resume_executor(tmp_path)
    expected = _resume_trajectory()
    path = executor.store.trajectory_path("training_batch_01", "traj_resume")
    executor.store.save_model(path, expected)

    def unexpected_run(**_kwargs: object) -> ResearchTrajectory:
        raise AssertionError("an exact completed trajectory must be reused")

    runner = SimpleNamespace(
        policy_client=SimpleNamespace(model="model/test"),
        model_revision="revision-1",
        run=unexpected_run,
    )
    assert _resume_call(executor, runner) == expected


def test_error_trajectory_is_persisted_and_rerun_on_resume(tmp_path: Path) -> None:
    executor = _resume_executor(tmp_path)
    results = [
        _resume_trajectory(status="error", error="model service unavailable", memo=""),
        _resume_trajectory(),
    ]
    calls = 0

    def run(**_kwargs: object) -> ResearchTrajectory:
        nonlocal calls
        calls += 1
        return results.pop(0)

    runner = SimpleNamespace(
        policy_client=SimpleNamespace(model="model/test"),
        model_revision="revision-1",
        run=run,
    )
    path = executor.store.trajectory_path("training_batch_01", "traj_resume")
    assert _resume_call(executor, runner).status == "error"
    assert executor.store.load_model(path, ResearchTrajectory).status == "error"
    assert _resume_call(executor, runner).status == "memo_submitted"
    assert calls == 2
    assert executor.store.load_model(path, ResearchTrajectory).status == "memo_submitted"


def test_run_store_detects_manifest_tampering_and_identity_is_stable(tmp_path: Path) -> None:
    store = RunStore(tmp_path, "run_01")
    first = trajectory_identity(
        run_id="run_01",
        partition="train",
        method="training_policy_sample",
        case_id="c1",
        persona="P_WD",
        seed=42,
        sample_index=0,
        skill_library_version="empty",
    )
    second = trajectory_identity(
        run_id="run_01",
        partition="train",
        method="training_policy_sample",
        case_id="c1",
        persona="P_WD",
        seed=42,
        sample_index=0,
        skill_library_version="empty",
    )
    assert first == second
    path = store.write_manifest("run", {"schema_version": 1, "model": "qwen"})
    assert store.read_manifest("run")["model"] == "qwen"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["model"] = "changed"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        store.read_manifest("run")


def test_run_store_round_trips_evaluation_without_computed_field_leak(
    tmp_path: Path,
) -> None:
    runner, _, _ = _runner()
    trajectory = runner.run(
        raw_case=_case(),
        persona={"persona_id": "P_WD", "who": {"zh": "当事人"}, "voice": {"zh": "简短"}},
        skills=[],
        trajectory_id="traj_round_trip",
        run_id="run_test",
        method="training_policy_sample",
        partition="training_round_01",
        seed=42,
        sample_index=0,
        max_turns=3,
        group_id="group_test",
        skill_library_version="empty",
    )
    judge = ScriptedJudge(
        [
            {
                "memo_expectation_scores": [1],
                "expected_action_scores": [1],
                "analysis": "完整",
            },
            {
                "covered_fact_ids": ["F1", "F2"],
                "missed_fact_ids": [],
                "correct_fact_ids": ["F1", "F2"],
                "incorrect_facts": [],
                "grounded_claims": [{"claim": "主张", "basis": "对话"}],
                "unsupported_claims": [],
            },
            {
                "claims": {
                    claim_id: {"classification": "grounded", "basis": "对话"}
                    for claim_id in memo_claim_spans(trajectory.memo)
                }
            },
        ]
    )
    evaluation = SemanticEvaluator(
        judge,
        "blind judge",
        judge_qualification_contract_sha256="a" * 64,
        reward_parameters=TEST_REWARD_PARAMETERS,
        max_attempts=2,
    ).evaluate(trajectory, _case())
    store = RunStore(tmp_path, "round_trip")
    path = store.evaluation_path(evaluation.trajectory_id)
    store.save_model(path, evaluation)
    persisted = json.loads(path.read_text(encoding="utf-8"))
    assert "total_claims" not in persisted["fact_judgment"]
    assert persisted["judge_qualification_contract_sha256"] == "a" * 64
    assert store.load_model(path, type(evaluation)) == evaluation
    persisted["fact_judgment"]["total_claims"] = evaluation.fact_judgment.total_claims
    path.write_text(json.dumps(persisted), encoding="utf-8")
    assert store.load_model(path, type(evaluation)) == evaluation


def test_model_manifest_verifier_detects_weight_tampering(tmp_path: Path) -> None:
    snapshot = tmp_path / "model"
    snapshot.mkdir()
    weight = snapshot / "weights.bin"
    weight.write_bytes(b"frozen-weight")
    import hashlib  # noqa: PLC0415

    manifest = {
        "model_id": "model/test",
        "revision": "revision-1",
        "snapshot": "model",
        "files": {
            "weights.bin": {
                "bytes": weight.stat().st_size,
                "sha256": hashlib.sha256(weight.read_bytes()).hexdigest(),
            }
        },
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    role = {
        "model_id": "model/test",
        "revision": "revision-1",
        "local_snapshot": "model",
        "manifest": "manifest.json",
    }
    assert verify_model_manifest(tmp_path, role)["passed"] is True
    weight.write_bytes(b"changed-weight")
    result = verify_model_manifest(tmp_path, role)
    assert result["passed"] is False
    assert result["hash_mismatches"][0]["file"] == "weights.bin"


def test_model_manifest_can_require_verified_upstream_weight_hashes(tmp_path: Path) -> None:
    import hashlib  # noqa: PLC0415

    snapshot = tmp_path / "model"
    snapshot.mkdir()
    weight = snapshot / "model.safetensors"
    weight.write_bytes(b"official-weight")
    digest = hashlib.sha256(weight.read_bytes()).hexdigest()
    manifest = {
        "model_id": "model/test",
        "revision": "revision-1",
        "snapshot": "model",
        "upstream_hashes_verified": True,
        "files": {
            weight.name: {
                "bytes": weight.stat().st_size,
                "sha256": digest,
                "upstream_sha256": digest,
            }
        },
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    role = {
        "model_id": "model/test",
        "revision": "revision-1",
        "local_snapshot": "model",
        "manifest": "manifest.json",
        "require_upstream_hashes_verified": True,
    }
    assert verify_model_manifest(tmp_path, role)["passed"] is True
    manifest["files"][weight.name]["upstream_sha256"] = "unverified"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    result = verify_model_manifest(tmp_path, role)
    assert result["passed"] is False
    assert result["metadata_mismatches"][0]["field"].endswith("upstream_sha256")


def test_parallel_executor_preserves_declared_matrix_order() -> None:
    assert parallel_map_ordered(
        [3, 1, 2], lambda value: value * 10, max_workers=3, label="test_parallel"
    ) == [30, 10, 20]


def test_parallel_executor_fail_fast_cancels_units_that_have_not_started() -> None:
    seen: list[int] = []

    def fail_first(value: int) -> int:
        seen.append(value)
        if value == 1:
            raise RuntimeError("invalid atomic result")
        return value

    with pytest.raises(ExecutionError, match="failed fast"):
        parallel_map_ordered(
            [1, 2, 3],
            fail_first,
            max_workers=1,
            label="test_parallel_fail_fast",
            fail_fast=True,
        )
    assert seen == [1]


def test_parallel_executor_fail_fast_on_error_trajectory_status() -> None:
    seen: list[int] = []
    failed = ResearchTrajectory.model_construct(
        trajectory_id="trajectory-error",
        status="error",
        error="model service unavailable",
    )
    succeeded = ResearchTrajectory.model_construct(
        trajectory_id="trajectory-success",
        status="memo_submitted",
        error=None,
    )

    def return_trajectory(value: int) -> ResearchTrajectory:
        seen.append(value)
        return failed if value == 1 else succeeded

    with pytest.raises(ExecutionError, match="error trajectory trajectory-error"):
        parallel_map_ordered(
            [1, 2, 3],
            return_trajectory,
            max_workers=1,
            label="test_error_trajectory_fail_fast",
            fail_fast=True,
        )
    assert seen == [1]


def test_codex_adapter_retries_forbidden_tool_event_and_never_caches_it(tmp_path: Path) -> None:
    executable = tmp_path / "codex"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    calls = 0

    def command_runner(command, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return subprocess.CompletedProcess(command, 0, '{"type":"command_execution"}')
        output = Path(command[command.index("--output-last-message") + 1])
        output.write_text('{"ready":true}', encoding="utf-8")
        return subprocess.CompletedProcess(
            command,
            0,
            '{"type":"item.completed"}\n'
            '{"type":"turn.completed","usage":{"input_tokens":20000,'
            '"cached_input_tokens":10000,"output_tokens":1000,'
            '"reasoning_output_tokens":100}}',
        )

    client = CodexCLIClient(
        model="gpt-5.6-luna",
        cache_root=tmp_path / "cache",
        retries=1,
        executable=str(executable),
        command_runner=command_runner,
    )
    response = client.generate_json(
        purpose="test",
        system_prompt="system",
        user_prompt="user",
        output_schema={"type": "object"},
    )
    assert calls == 2
    assert response.value == {"ready": True}
    assert client.generate_json(
        purpose="test",
        system_prompt="system",
        user_prompt="user",
        output_schema={"type": "object"},
    ).cache_hit
    assert calls == 2


def test_codex_adapter_rejects_cross_run_cache_identity_drift(tmp_path: Path) -> None:
    executable = tmp_path / "codex"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)

    def command_runner(command, **kwargs):
        output = Path(command[command.index("--output-last-message") + 1])
        output.write_text('{"ready":true}', encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, '{"type":"item.completed"}')

    client = CodexCLIClient(
        model="gpt-5.6-luna",
        cache_root=tmp_path / "cache",
        retries=0,
        executable=str(executable),
        command_runner=command_runner,
    )
    response = client.generate_json(
        purpose="preflight",
        system_prompt="system",
        user_prompt="user",
        output_schema={"type": "object"},
    )
    cache_path = tmp_path / "cache" / "preflight" / f"{response.request_sha256}.json"
    cached = json.loads(cache_path.read_text(encoding="utf-8"))
    cached["model"] = "different-model"
    cache_path.write_text(json.dumps(cached), encoding="utf-8")

    with pytest.raises(CodexInvocationError, match="cache contract mismatch"):
        client.generate_json(
            purpose="preflight",
            system_prompt="system",
            user_prompt="user",
            output_schema={"type": "object"},
        )


def test_codex_preflight_reports_canonical_executable_identity(tmp_path: Path) -> None:
    executable = tmp_path / "codex-real"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    symlink = tmp_path / "codex"
    symlink.symlink_to(executable)

    def command_runner(command, **kwargs):
        assert command[0] == str(symlink)
        return subprocess.CompletedProcess(command, 0, "Logged in using ChatGPT")

    client = CodexCLIClient(
        model="teacher-test",
        cache_root=tmp_path / "cache",
        retries=0,
        executable=str(symlink),
        command_runner=command_runner,
    )
    report = client.preflight()
    assert report["ready"] is True
    assert report["executable"] == str(executable.resolve())


def test_codex_timeout_terminates_and_reaps_entire_process_group(tmp_path: Path) -> None:
    child_pid_path = tmp_path / "child.pid"
    executable = tmp_path / "process-tree.sh"
    executable.write_text(
        f"#!/bin/sh\nsleep 60 &\necho $! > {child_pid_path}\nwait\n",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    with pytest.raises(subprocess.TimeoutExpired):
        run_process_tree(
            [str(executable)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=0.2,
            check=False,
        )
    child_pid = int(child_pid_path.read_text(encoding="utf-8"))
    with pytest.raises(ProcessLookupError):
        os.kill(child_pid, 0)


def test_process_tree_delivers_explicit_input_through_stdin_pipe() -> None:
    completed = run_process_tree(
        [sys.executable, "-c", "import sys; print(sys.stdin.read())"],
        input="teacher prompt",
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=5,
        check=False,
    )
    assert completed.returncode == 0
    assert completed.stdout.strip() == "teacher prompt"


def test_teacher_schema_is_normalized_to_strict_structured_outputs_subset() -> None:
    raw = SkillDiagnosis.model_json_schema()
    assert strict_output_schema_issues(raw)
    normalized = strict_output_schema(raw)
    assert strict_output_schema_issues(normalized) == []
    skill = normalized["$defs"]["SkillContract"]
    assert skill["required"] == list(skill["properties"])
    assert {
        "objective",
        "applicability_cues",
        "procedure",
        "question_guidance",
        "expected_effects",
        "contraindications",
        "failure_modes",
    } <= set(skill["properties"])
    assert {
        "preconditions",
        "operation",
        "reads",
        "validators",
        "guardrails",
    }.isdisjoint(skill["properties"])


def test_codex_rejects_invalid_schema_before_budget_reservation(tmp_path: Path) -> None:
    budget_path = tmp_path / "budget.json"
    client = CodexCLIClient(
        model="gpt-5.6-luna",
        cache_root=tmp_path / "cache",
        executable="must-not-be-resolved",
        invocation_budget_path=budget_path,
        max_invocations=48,
    )
    with pytest.raises(CodexInvocationError, match="output schema violates strict"):
        client.generate_json(
            purpose="invalid_schema",
            system_prompt="system",
            user_prompt="user",
            output_schema={
                "type": "object",
                "properties": {"ready": {"type": "boolean", "default": True}},
                "additionalProperties": False,
            },
        )
    assert not budget_path.exists()


def test_codex_adapter_fails_closed_when_every_attempt_uses_tools(tmp_path: Path) -> None:
    executable = tmp_path / "codex"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)

    def command_runner(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, '{"type":"web_search"}')

    client = CodexCLIClient(
        model="teacher-test",
        cache_root=tmp_path / "cache",
        retries=0,
        executable=str(executable),
        command_runner=command_runner,
    )
    with pytest.raises(CodexInvocationError, match="forbidden tool call"):
        client.generate_json(
            purpose="test",
            system_prompt="system",
            user_prompt="user",
            output_schema={"type": "object"},
        )
    artifacts = list((tmp_path / "cache" / "_failures" / "test").glob("*.json"))
    assert len(artifacts) == 1
    artifact = json.loads(artifacts[0].read_text(encoding="utf-8"))
    assert artifact["error_message"] == "Codex attempted a forbidden tool call"
    assert artifact["event_log_tail"] == '{"type":"web_search"}'
    assert "system" not in artifacts[0].read_text(encoding="utf-8")


def test_codex_adapter_persists_nonzero_transport_failure(tmp_path: Path) -> None:
    executable = tmp_path / "codex"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)

    def command_runner(command, **kwargs):
        return subprocess.CompletedProcess(
            command,
            1,
            '{"type":"error","message":"transport unavailable"}\n',
        )

    client = CodexCLIClient(
        model="teacher-test",
        cache_root=tmp_path / "cache",
        retries=0,
        executable=str(executable),
        command_runner=command_runner,
    )
    with pytest.raises(CodexInvocationError, match="Codex exited 1"):
        client.generate_json(
            purpose="skill_teacher",
            system_prompt="private system prompt",
            user_prompt="private user prompt",
            output_schema={"type": "object"},
        )
    artifacts = list((tmp_path / "cache" / "_failures" / "skill_teacher").glob("*.json"))
    assert len(artifacts) == 1
    artifact_text = artifacts[0].read_text(encoding="utf-8")
    artifact = json.loads(artifact_text)
    assert artifact["returncode"] == 1
    assert artifact["failure_events"] == [{"type": "error", "message": "transport unavailable"}]
    assert "private system prompt" not in artifact_text
    assert "private user prompt" not in artifact_text


def test_codex_adapter_persists_timeout_failure(tmp_path: Path) -> None:
    executable = tmp_path / "codex"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)

    def command_runner(command, **kwargs):
        raise subprocess.TimeoutExpired(command, timeout=kwargs["timeout"])

    client = CodexCLIClient(
        model="teacher-test",
        cache_root=tmp_path / "cache",
        retries=0,
        executable=str(executable),
        command_runner=command_runner,
    )
    with pytest.raises(CodexInvocationError, match="TimeoutExpired"):
        client.generate_json(
            purpose="skill_teacher",
            system_prompt="system",
            user_prompt="user",
            output_schema={"type": "object"},
        )
    artifacts = list((tmp_path / "cache" / "_failures" / "skill_teacher").glob("*.json"))
    assert len(artifacts) == 1
    artifact = json.loads(artifacts[0].read_text(encoding="utf-8"))
    assert artifact["error_type"] == "TimeoutExpired"
    assert artifact["returncode"] is None


def test_codex_adapter_enforces_persistent_hard_invocation_budget(tmp_path: Path) -> None:
    executable = tmp_path / "codex"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    calls = 0

    def command_runner(command, **kwargs):
        nonlocal calls
        calls += 1
        output = Path(command[command.index("--output-last-message") + 1])
        output.write_text('{"ready":true}', encoding="utf-8")
        return subprocess.CompletedProcess(
            command,
            0,
            '{"type":"item.completed"}\n'
            '{"type":"turn.completed","usage":{"input_tokens":20000,'
            '"cached_input_tokens":10000,"output_tokens":1000,'
            '"reasoning_output_tokens":100}}',
        )

    budget_path = tmp_path / "budget.json"
    client = CodexCLIClient(
        model="gpt-5.6-luna",
        cache_root=tmp_path / "cache",
        retries=0,
        executable=str(executable),
        command_runner=command_runner,
        invocation_budget_path=budget_path,
        max_invocations=1,
    )
    first = client.generate_json(
        purpose="test",
        system_prompt="system",
        user_prompt="first",
        output_schema={"type": "object"},
    )
    assert first.invocation["budget_reservation"]["sequence"] == 1
    assert first.invocation["usage"]["input_tokens"] == 20000
    assert first.invocation["estimated_luna_credits"] == 0.085
    assert client.generate_json(
        purpose="test",
        system_prompt="system",
        user_prompt="first",
        output_schema={"type": "object"},
    ).cache_hit
    with pytest.raises(CodexInvocationError, match="hard invocation budget exhausted"):
        client.generate_json(
            purpose="test",
            system_prompt="system",
            user_prompt="second",
            output_schema={"type": "object"},
        )
    assert calls == 1
    assert len(json.loads(budget_path.read_text(encoding="utf-8"))["reservations"]) == 1


def test_teacher_response_cache_isolated_between_runs_and_reused_within_run(
    tmp_path: Path,
) -> None:
    executable = tmp_path / "codex"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    calls = 0

    def command_runner(command, **kwargs):
        nonlocal calls
        calls += 1
        output = Path(command[command.index("--output-last-message") + 1])
        output.write_text('{"ready":true}', encoding="utf-8")
        return subprocess.CompletedProcess(
            command,
            0,
            '{"type":"turn.completed","usage":{"input_tokens":1000,'
            '"cached_input_tokens":0,"output_tokens":100,"reasoning_output_tokens":0}}',
        )

    budget_path = tmp_path / "runs/main_experiment_shared/luna_invocation_budget.json"

    def client(run_id: str) -> CodexCLIClient:
        store = RunStore(tmp_path / "runs", run_id)
        return CodexCLIClient(
            model="gpt-5.6-luna",
            cache_root=teacher_response_cache_root(store),
            retries=0,
            executable=str(executable),
            command_runner=command_runner,
            invocation_budget_path=budget_path,
            max_invocations=4,
        )

    first_run = client("formal_run_one")
    same_run = client("formal_run_one")
    second_run = client("formal_run_two")
    request = {
        "purpose": "skill_teacher_batch",
        "system_prompt": "system",
        "user_prompt": "same evidence",
        "output_schema": {"type": "object"},
    }

    assert first_run.cache_root == same_run.cache_root
    assert first_run.cache_root != second_run.cache_root
    assert first_run.generate_json(**request).cache_hit is False
    assert same_run.generate_json(**request).cache_hit is True
    assert second_run.generate_json(**request).cache_hit is False
    assert calls == 2
    assert len(json.loads(budget_path.read_text(encoding="utf-8"))["reservations"]) == 2


def test_codex_budget_status_reports_capacity_without_reserving(tmp_path: Path) -> None:
    budget_path = tmp_path / "budget.json"
    client = CodexCLIClient(
        model="gpt-5.6-luna",
        cache_root=tmp_path / "cache",
        executable="unused",
        invocation_budget_path=budget_path,
        max_invocations=3,
    )
    assert client.invocation_budget_status() == {
        "hard_limit": 3,
        "reserved": 0,
        "available": 3,
    }
    assert not budget_path.exists()
    budget_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "model": "gpt-5.6-luna",
                "max_invocations": 3,
                "reservations": [{"sequence": 1}],
            }
        ),
        encoding="utf-8",
    )
    assert client.invocation_budget_status() == {
        "hard_limit": 3,
        "reserved": 1,
        "available": 2,
    }


def test_paired_statistics_are_deterministic_and_bh_monotone() -> None:
    deltas = [0.1, 0.2, -0.05, 0.3]
    first = paired_bootstrap_interval(deltas, samples=500, seed=7)
    second = paired_bootstrap_interval(deltas, samples=500, seed=7)
    assert first == second
    assert paired_sign_flip_p_value(deltas, samples=500, seed=7) == paired_sign_flip_p_value(
        deltas, samples=500, seed=7
    )
    adjusted = benjamini_hochberg({"a": 0.01, "b": 0.03, "c": 0.2})
    assert 0 <= adjusted["a"] <= adjusted["b"] <= adjusted["c"] <= 1


def test_paired_statistics_cluster_persona_seed_repetitions_by_case() -> None:
    deltas = clustered_mean_deltas(
        ["case_b", "case_a", "case_a", "case_b"],
        [0.0, 0.2, 0.4, 0.0],
        [0.4, 0.4, 0.2, 0.2],
    )
    assert deltas == pytest.approx([0.0, 0.3])


def test_teacher_group_budget_covers_cases_before_repeating_one_case() -> None:
    groups = []
    for case_index, case_id in enumerate(("case_a", "case_b", "case_c")):
        for persona_index in range(3):
            group = SimpleNamespace(
                informative=True,
                std_reward=1.0 - case_index * 0.1 - persona_index * 0.01,
                group_id=f"{case_id}.{persona_index}",
            )
            trajectory = SimpleNamespace(
                case_id=case_id,
                domain=f"domain_{case_index}",
                persona=f"persona_{persona_index}",
            )
            groups.append((group, {f"t_{case_id}_{persona_index}": trajectory}))
    selected = select_diverse_teacher_groups(groups, budget=4, maximum_per_case=2)
    selected_cases = [next(iter(mapped.values())).case_id for _, mapped in selected]
    assert set(selected_cases[:3]) == {"case_a", "case_b", "case_c"}
    assert Counter(selected_cases).most_common(1)[0][1] == 2


def test_training_random_streams_vary_only_for_sampled_policy() -> None:
    assert policy_sampling_seed(42, 0, 1) != policy_sampling_seed(42, 1, 1)
    assert shared_component_seed(42, 1) == shared_component_seed(42, 1)
    assert shared_component_seed(42, 1) != shared_component_seed(42, 2)


def test_embedded_candidate_arms_share_policy_stream_but_exploration_does_not() -> None:
    assert policy_stream_index("candidate_without", 0) == 0
    assert policy_stream_index("candidate_with", 1) == 0
    assert policy_stream_index("candidate_with", 2) == 0
    assert policy_stream_index("training_policy_sample", 3) == 3
    assert policy_stream_index(
        "training_policy_sample", 1, counterfactual_pair_size=2
    ) == 0
    assert policy_stream_index(
        "training_policy_sample", 3, counterfactual_pair_size=2
    ) == 2


def test_counterfactual_target_allocation_never_masks_embedded_candidate_effect() -> None:
    assert uses_counterfactual_target_allocation("training_policy_sample") is True
    assert uses_counterfactual_target_allocation("candidate_without") is False
    assert uses_counterfactual_target_allocation("candidate_with") is False


def test_surface_paraphrase_cannot_become_teacher_contrast() -> None:
    action = SimpleNamespace(action_type="ask", target_type="fact", target_id="F1")
    first_step = SimpleNamespace(
        action_decision=SimpleNamespace(final=action),
        rendered_question="合同何时签署？",
        client_selected_fact_ids=[],
    )
    second_step = SimpleNamespace(
        action_decision=SimpleNamespace(final=action),
        rendered_question="请说明合同签署时间。",
        client_selected_fact_ids=[],
    )
    first = SimpleNamespace(steps=[first_step])
    second = SimpleNamespace(steps=[second_step])
    assert trajectory_learning_signature(first) == trajectory_learning_signature(second)
    group = SimpleNamespace(
        model_copy=lambda update: SimpleNamespace(**update),
        informative=True,
        skip_reason=None,
    )
    guarded = require_distinct_learning_traces(group, {"a": first, "b": second})
    assert guarded.informative is False
    assert guarded.skip_reason == "identical_policy_trace"


def test_teacher_contrast_requires_shared_state_policy_fork_and_fact_gain() -> None:
    from legal_skill_guard.evolution.advantage import (  # noqa: PLC0415
        AdvantageGroup,
        ScoredMember,
    )
    from legal_skill_guard.schemas.action import StructuredAction  # noqa: PLC0415

    shared_first = StructuredAction(
        action_type="ask", target_type="fact", target_id="F1", content="第一项事实？"
    )
    positive_second = StructuredAction(
        action_type="ask", target_type="fact", target_id="F2", content="第二项事实？"
    )
    negative_second = StructuredAction(action_type="final", content="")

    def step(turn, state, action, facts):
        return SimpleNamespace(
            turn=turn,
            state_before=state,
            proposed_action=action,
            client_response_kind="new_hidden_fact" if facts else None,
            client_selected_fact_ids=facts,
            client_response="已回答" if facts else None,
        )

    positive = SimpleNamespace(
        steps=[
            step(1, {"session_id": "positive", "turn": 0}, shared_first, ["F1"]),
            step(2, {"session_id": "positive", "turn": 1}, positive_second, ["F2"]),
        ]
    )
    negative = SimpleNamespace(
        steps=[
            step(1, {"session_id": "negative", "turn": 0}, shared_first, ["F1"]),
            step(2, {"session_id": "negative", "turn": 1}, negative_second, []),
        ]
    )
    group = AdvantageGroup(
        group_id="g",
        members=[
            ScoredMember(trajectory_id="positive", reward=0.4),
            ScoredMember(trajectory_id="negative", reward=0.1),
        ],
        mean_reward=0.25,
        std_reward=0.15,
        informative=True,
    )
    selection = select_causally_aligned_contrast(
        group, {"positive": positive, "negative": negative}
    )
    assert selection is not None
    assert selection.highest_id == "positive"
    assert selection.lowest_id == "negative"
    assert selection.aligned_divergence_turn == 2
    assert selection.immediate_fact_gain == 1
    assert selection.fact_gain == 1
    assert selection.selection_basis == "shared_visible_state_immediate_fact_gain_policy_fork"

    # A fact-bearing branch with a lower declared reward is useful diagnostic
    # evidence, but it is not a TF-GRPO-style winner and must not reach the teacher.
    memo_confounded_group = group.model_copy(
        update={
            "members": [
                ScoredMember(trajectory_id="positive", reward=0.1),
                ScoredMember(trajectory_id="negative", reward=0.4),
            ],
            "mean_reward": 0.25,
            "std_reward": 0.15,
        }
    )
    memo_confounded = select_causally_aligned_contrast(
        memo_confounded_group, {"positive": positive, "negative": negative}
    )
    assert memo_confounded is None

    # Two different facts obtained at the divergence are ordinary rollout
    # variation, not an immediate fact-gain contrast.  A later difference in
    # trajectory totals cannot be attributed to either local action alone.
    positive.steps = [
        step(1, {"session_id": "positive", "turn": 0}, positive_second, ["F2"]),
        step(2, {"session_id": "positive", "turn": 1}, shared_first, ["F1"]),
    ]
    negative.steps = [
        step(1, {"session_id": "negative", "turn": 0}, shared_first, ["F1"]),
    ]
    assert (
        select_causally_aligned_contrast(group, {"positive": positive, "negative": negative})
        is None
    )

    # Wording alone is not an executable skill fork, even if the environment gives
    # the paraphrases different outcomes.
    paraphrase = StructuredAction(
        action_type="ask", target_type="fact", target_id="F1", content="请问第一项事实？"
    )
    positive.steps = [step(1, {"session_id": "positive", "turn": 0}, paraphrase, ["F1"])]
    negative.steps = [step(1, {"session_id": "negative", "turn": 0}, shared_first, [])]
    assert (
        select_causally_aligned_contrast(group, {"positive": positive, "negative": negative})
        is None
    )


def test_causal_state_signature_uses_the_policy_patch_execution_state() -> None:
    from legal_skill_guard.experiment.executor import _causal_state_signature  # noqa: PLC0415
    from legal_skill_guard.schemas.action import StructuredAction  # noqa: PLC0415
    from legal_skill_guard.schemas.state import ConsultationState  # noqa: PLC0415

    state = ConsultationState(session_id="shared", max_turns=8)
    action = StructuredAction(
        action_type="ask",
        target_type="fact",
        target_id="F1",
        content="合同何时签订？",
    )
    base = SimpleNamespace(
        turn=1,
        state_before=state.model_dump(mode="json"),
        proposed_action=action,
        state_patch=StatePatch(),
    )
    patched = SimpleNamespace(
        turn=1,
        state_before=state.model_dump(mode="json"),
        proposed_action=action,
        state_patch=StatePatch(
            observations=[
                FactObservation(
                    fact_id="F1",
                    label="合同签订时间",
                    status="unknown",
                    criticality="high",
                    target_kind="client_fact",
                )
            ]
        ),
    )

    assert _causal_state_signature(base) != _causal_state_signature(patched)


def test_causal_state_signature_excludes_current_action_derived_criticality() -> None:
    from legal_skill_guard.experiment.executor import _causal_state_signature  # noqa: PLC0415
    from legal_skill_guard.schemas.action import StructuredAction  # noqa: PLC0415
    from legal_skill_guard.schemas.state import ConsultationState  # noqa: PLC0415

    state = ConsultationState(
        session_id="shared",
        max_turns=8,
        facts=[
            FactSlot(
                fact_id="F1",
                label="关键事实",
                status="unknown",
                criticality="high",
                target_kind="client_fact",
            )
        ],
    )
    final_step = SimpleNamespace(
        turn=2,
        state_before=state.model_dump(mode="json"),
        proposed_action=StructuredAction(action_type="final", content=""),
        state_patch=StatePatch(),
    )
    ask_step = SimpleNamespace(
        turn=2,
        state_before=state.model_dump(mode="json"),
        proposed_action=StructuredAction(
            action_type="ask",
            target_type="fact",
            target_id="F1",
            content="请说明关键事实。",
        ),
        state_patch=StatePatch(),
    )

    # The current actions are the treatment difference.  Their derived target
    # criticality must not be mistaken for a different pre-action state.
    assert _causal_state_signature(final_step) == _causal_state_signature(ask_step)


def test_causal_fork_uses_executed_actions_after_existing_skills() -> None:
    from legal_skill_guard.evolution.advantage import (  # noqa: PLC0415
        AdvantageGroup,
        ScoredMember,
    )
    from legal_skill_guard.schemas.action import (  # noqa: PLC0415
        ActionDecision,
        StructuredAction,
    )
    from legal_skill_guard.schemas.state import ConsultationState  # noqa: PLC0415

    state = ConsultationState(
        session_id="shared",
        max_turns=8,
        facts=[
            FactSlot(fact_id="F1", label="事实一", target_kind="client_fact"),
            FactSlot(fact_id="F2", label="事实二", target_kind="client_fact"),
        ],
    ).model_dump(mode="json")
    proposed_f1 = StructuredAction(
        action_type="ask", target_type="fact", target_id="F1", content="事实一？"
    )
    proposed_f2 = StructuredAction(
        action_type="ask", target_type="fact", target_id="F2", content="事实二？"
    )
    executed = StructuredAction(
        action_type="ask", target_type="fact", target_id="F1", content="事实一？"
    )

    def step(proposed, response_kind, selected):
        return SimpleNamespace(
            turn=1,
            state_before=state,
            state_patch=StatePatch(),
            proposed_action=proposed,
            action_decision=ActionDecision(original=proposed, final=executed),
            client_response_kind=response_kind,
            client_selected_fact_ids=selected,
            client_response="已回答" if selected else "不知道",
        )

    positive = SimpleNamespace(steps=[step(proposed_f1, "new_hidden_fact", ["F1"])])
    negative = SimpleNamespace(steps=[step(proposed_f2, "unavailable", [])])
    group = AdvantageGroup(
        group_id="same-executed-action",
        members=[
            ScoredMember(trajectory_id="positive", reward=0.5),
            ScoredMember(trajectory_id="negative", reward=0.2),
        ],
        mean_reward=0.35,
        std_reward=0.15,
        informative=True,
    )

    assert (
        select_causally_aligned_contrast(group, {"positive": positive, "negative": negative})
        is None
    )


def test_teacher_contrast_keeps_same_target_question_formulation_fork() -> None:
    from legal_skill_guard.evolution.advantage import (  # noqa: PLC0415
        AdvantageGroup,
        ScoredMember,
    )
    from legal_skill_guard.schemas.action import StructuredAction  # noqa: PLC0415
    from legal_skill_guard.schemas.state import ConsultationState  # noqa: PLC0415

    state = ConsultationState(
        session_id="shared",
        max_turns=8,
        facts=[
            FactSlot(
                fact_id="F1",
                label="合同签署日期",
                target_kind="client_fact",
                criticality="high",
            )
        ],
    ).model_dump(mode="json")
    precise = StructuredAction(
        action_type="ask",
        target_type="fact",
        target_id="F1",
        expected_information="合同签署的具体日期",
        content="合同具体是哪一天签署的？",
    )
    vague = StructuredAction(
        action_type="ask",
        target_type="fact",
        target_id="F1",
        expected_information="合同相关情况",
        content="合同方面是什么情况？",
    )

    def step(action, response_kind, selected):
        return SimpleNamespace(
            turn=1,
            state_before=state,
            state_patch=StatePatch(),
            proposed_action=action,
            client_response_kind=response_kind,
            client_selected_fact_ids=selected,
            client_response="2024年1月3日" if selected else "不知道",
            policy_health_violations=[],
            post_skill_health_violations=[],
            verifier_results=[],
        )

    positive = SimpleNamespace(steps=[step(precise, "new_hidden_fact", ["F1"])])
    negative = SimpleNamespace(steps=[step(vague, "unavailable", [])])
    group = AdvantageGroup(
        group_id="same-target-question-formulation",
        members=[
            ScoredMember(trajectory_id="positive", reward=0.6),
            ScoredMember(trajectory_id="negative", reward=0.2),
        ],
        mean_reward=0.4,
        std_reward=0.2,
        informative=True,
    )

    selection = select_causally_aligned_contrast(
        group, {"positive": positive, "negative": negative}
    )
    assert selection is not None
    assert selection.aligned_divergence_turn == 1
    assert selection.immediate_fact_gain == 1
    assert selection.fact_gain == 1

    # Punctuation and spacing alone remain the same auditable formulation.
    negative.steps[0].proposed_action = precise.model_copy(
        update={
            "content": " 合同具体是哪一天签署的 ! ",
            "expected_information": "合同签署的具体日期。",
        }
    )
    assert (
        select_causally_aligned_contrast(
            group, {"positive": positive, "negative": negative}
        )
        is None
    )


def test_teacher_contrast_accepts_direct_information_efficiency_when_later_caught_up() -> None:
    from legal_skill_guard.evolution.advantage import (  # noqa: PLC0415
        AdvantageGroup,
        ScoredMember,
    )
    from legal_skill_guard.schemas.action import StructuredAction  # noqa: PLC0415

    informative = StructuredAction(
        action_type="ask", target_type="fact", target_id="F1", content="关键日期是什么？"
    )
    zero_information = StructuredAction(
        action_type="ask", target_type="fact", target_id="F2", content="无法确认的细节是什么？"
    )
    shared = {
        "session_id": "ignored",
        "turn": 0,
        "high_critical_unknown_count": 2,
        "unavailable_turn_count": 0,
        "facts": [
            {"fact_id": "F1", "target_kind": "client_fact", "status": "unknown"},
            {"fact_id": "F2", "target_kind": "client_fact", "status": "unknown"},
        ],
    }

    def step(turn, state, action, kind, facts):
        return SimpleNamespace(
            turn=turn,
            state_before=state,
            proposed_action=action,
            client_response_kind=kind,
            client_selected_fact_ids=facts,
            client_response="回答" if kind == "new_hidden_fact" else "不知道",
        )

    positive = SimpleNamespace(steps=[step(1, shared, informative, "new_hidden_fact", ["F1"])])
    negative = SimpleNamespace(
        steps=[
            step(1, shared, zero_information, "unavailable", []),
            step(2, {**shared, "turn": 1}, informative, "new_hidden_fact", ["F1"]),
        ]
    )
    group = AdvantageGroup(
        group_id="efficiency",
        members=[
            ScoredMember(trajectory_id="positive", reward=0.5),
            ScoredMember(trajectory_id="negative", reward=0.4),
        ],
        mean_reward=0.45,
        std_reward=0.05,
        informative=True,
    )

    selection = select_causally_aligned_contrast(
        group, {"positive": positive, "negative": negative}
    )
    assert selection is not None
    assert selection.highest_id == "positive"
    assert selection.lowest_id == "negative"
    assert selection.aligned_divergence_turn == 1
    assert selection.immediate_fact_gain == 1
    assert selection.fact_gain == 0
    assert selection.reward_gap == 0.1
    assert selection.selection_basis == (
        "shared_visible_state_immediate_information_efficiency_policy_fork"
    )

    # Earlier information is not a safe winner if that branch ultimately loses
    # unique coverage; the held-out gate must never be asked to rescue such evidence.
    negative.steps.append(
        step(3, {**shared, "turn": 2}, zero_information, "new_hidden_fact", ["F2"])
    )
    assert (
        select_causally_aligned_contrast(group, {"positive": positive, "negative": negative})
        is None
    )

    # A later fact seen only on the positive branch is not attributable to the
    # earlier action fork. It must not turn a clean immediate efficiency signal
    # into a purported durable coverage gain.
    positive.steps = [
        step(1, shared, informative, "new_hidden_fact", ["F1"]),
        step(2, {**shared, "turn": 1}, zero_information, "new_hidden_fact", ["F2"]),
    ]
    negative.steps = [
        step(1, shared, zero_information, "unavailable", []),
        step(2, {**shared, "turn": 1}, informative, "new_hidden_fact", ["F1"]),
    ]
    assert (
        select_causally_aligned_contrast(group, {"positive": positive, "negative": negative})
        is None
    )


def test_teacher_contrast_admits_only_grounded_zero_information_stop_fork() -> None:
    from legal_skill_guard.evolution.advantage import (  # noqa: PLC0415
        AdvantageGroup,
        ScoredMember,
    )
    from legal_skill_guard.schemas.action import StructuredAction  # noqa: PLC0415

    final = StructuredAction(action_type="final", content="")
    needless_question = StructuredAction(
        action_type="ask",
        target_type="fact",
        target_id="remaining_detail",
        content="还有其他细节吗？",
    )
    shared_state = {
        "session_id": "ignored",
        "turn": 2,
        "high_critical_unknown_count": 0,
        "unavailable_turn_count": 1,
        "all_remaining_facts_not_available": False,
        "facts": [
            {
                "fact_id": "remaining_detail",
                "target_kind": "client_fact",
                "status": "unknown",
            }
        ],
    }

    def step(action, response_kind):
        return SimpleNamespace(
            turn=3,
            state_before=shared_state,
            proposed_action=action,
            action_decision=SimpleNamespace(final=action),
            client_response_kind=response_kind,
            client_selected_fact_ids=[],
        )

    positive = SimpleNamespace(steps=[step(final, None)])
    negative = SimpleNamespace(steps=[step(needless_question, "unavailable")])
    group = AdvantageGroup(
        group_id="safe-stop",
        members=[
            ScoredMember(trajectory_id="positive", reward=0.6),
            ScoredMember(trajectory_id="negative", reward=0.4),
        ],
        mean_reward=0.5,
        std_reward=0.1,
        informative=True,
    )

    selection = select_causally_aligned_contrast(
        group, {"positive": positive, "negative": negative}
    )

    assert selection is not None
    assert selection.highest_id == "positive"
    assert selection.lowest_id == "negative"
    assert selection.fact_gain == 0
    assert selection.selection_basis == (
        "shared_visible_state_true_zero_question_to_safe_final_fork"
    )
    assert selection.signal_family == "safe_stop"

    # Removing prior unanswerability makes stopping speculative, so it is excluded.
    positive.steps[0].state_before = {**shared_state, "unavailable_turn_count": 0}
    negative.steps[0].state_before = {**shared_state, "unavailable_turn_count": 0}
    assert (
        select_causally_aligned_contrast(group, {"positive": positive, "negative": negative})
        is None
    )


def test_teacher_contrast_treats_external_evidence_gap_as_positive_signal() -> None:
    from legal_skill_guard.evolution.advantage import (  # noqa: PLC0415
        AdvantageGroup,
        ScoredMember,
    )
    from legal_skill_guard.schemas.action import StructuredAction  # noqa: PLC0415

    ask_gap = StructuredAction(
        action_type="ask",
        target_type="fact",
        target_id="external_record",
        content="能否调取该记录？",
    )
    final = StructuredAction(action_type="final", content="")
    shared_state = {
        "session_id": "ignored",
        "turn": 0,
        "high_critical_unknown_count": 0,
        "unavailable_turn_count": 0,
        "evidence_or_third_party_unresolved_count": 1,
        "asked_targets": [],
        "interactions": [],
        "facts": [
            {
                "fact_id": "external_record",
                "status": "unknown",
                "target_kind": "evidence_or_third_party",
            }
        ],
    }

    def step(action, response_kind):
        return SimpleNamespace(
            turn=1,
            state_before=shared_state,
            proposed_action=action,
            action_decision=SimpleNamespace(final=action),
            client_response_kind=response_kind,
            client_selected_fact_ids=[],
            client_safe_fallback=False,
            policy_health_violations=[],
            post_skill_health_violations=[],
        )

    gap = SimpleNamespace(steps=[step(ask_gap, "unavailable")])
    stopped = SimpleNamespace(steps=[step(final, None)])
    group = AdvantageGroup(
        group_id="gap-fork",
        members=[
            ScoredMember(trajectory_id="gap", reward=0.6),
            ScoredMember(trajectory_id="stopped", reward=0.4),
        ],
        mean_reward=0.5,
        std_reward=0.1,
        informative=True,
    )

    selections = select_causally_aligned_contrasts(group, {"gap": gap, "stopped": stopped})
    assert len(selections) == 1
    assert selections[0].signal_family == "evidence_gap_identification"
    assert selections[0].immediate_gap_gain == 1
    assert selections[0].gap_gain == 1

    # Even a higher-scoring final cannot call the still-unresolved evidence target
    # a needless zero-information question.
    reversed_group = group.model_copy(
        update={
            "members": [
                ScoredMember(trajectory_id="gap", reward=0.4),
                ScoredMember(trajectory_id="stopped", reward=0.6),
            ]
        }
    )
    assert (
        select_causally_aligned_contrast(reversed_group, {"gap": gap, "stopped": stopped}) is None
    )


def test_different_elicitation_outcome_is_teacher_visible() -> None:
    action = SimpleNamespace(action_type="ask", target_type="fact", target_id="F1")
    empty = SimpleNamespace(
        steps=[
            SimpleNamespace(
                action_decision=SimpleNamespace(final=action),
                rendered_question="合同何时签署？",
                client_selected_fact_ids=[],
            )
        ]
    )
    elicited = SimpleNamespace(
        steps=[
            SimpleNamespace(
                action_decision=SimpleNamespace(final=action),
                rendered_question="合同何时签署？",
                client_selected_fact_ids=["F1"],
            )
        ]
    )
    assert trajectory_learning_signature(empty) != trajectory_learning_signature(elicited)


def test_behavior_summary_does_not_count_repeated_fact_as_new_information() -> None:
    def step(target_id: str, selected: list[str]):
        return SimpleNamespace(
            rendered_question=f"询问{target_id}",
            client_selected_fact_ids=selected,
            action_decision=SimpleNamespace(
                final=SimpleNamespace(target_id=target_id),
                activated_skill_ids=[],
            ),
        )

    trajectory = SimpleNamespace(
        case_id="case_a",
        domain="contract",
        persona="P_WD",
        steps=[step("target_a", ["O2"]), step("target_b", ["O2"]), step("target_c", ["F1"])],
    )

    summary = trajectory_behavior_summary([trajectory], set())

    assert summary["mean_question_turns"] == 3.0
    assert summary["mean_answered_question_turns"] == 3.0
    assert summary["answered_question_rate"] == 1.0
    assert summary["mean_information_bearing_turns"] == 1.0
    assert summary["information_bearing_question_rate"] == pytest.approx(1 / 3, abs=1e-6)
    assert summary["mean_unique_disclosed_facts"] == 1.0
    assert summary["mean_unique_disclosed_facts_per_question"] == pytest.approx(
        1 / 3, abs=1e-6
    )
    assert summary["pooled_unique_disclosed_facts_per_question"] == pytest.approx(
        1 / 3, abs=1e-6
    )


def test_paired_behavior_estimates_measure_new_information_not_just_more_turns() -> None:
    def step(target_id: str, selected: list[str]):
        return SimpleNamespace(
            rendered_question=f"询问{target_id}",
            client_selected_fact_ids=selected,
            action_decision=SimpleNamespace(
                final=SimpleNamespace(target_id=target_id),
                activated_skill_ids=[],
            ),
        )

    control = SimpleNamespace(
        case_id="case_a",
        domain="contract",
        steps=[step("target_a", ["O1"])],
    )
    treatment = SimpleNamespace(
        case_id="case_a",
        domain="contract",
        steps=[step("target_a", ["O1"]), step("target_b", ["F1"])],
    )
    report = paired_behavior_estimates(
        [control],
        [treatment],
        set(),
        bootstrap_samples=100,
        confidence_level=0.95,
        seed=7,
    )
    assert report["metrics"]["question_turns"]["mean_delta"] == 1.0
    assert report["metrics"]["information_bearing_turns"]["mean_delta"] == 1.0
    assert report["metrics"]["unique_disclosed_facts"]["mean_delta"] == 1.0
    assert report["metrics"]["unique_disclosed_facts_per_question"]["mean_delta"] == 0.5


def test_training_batches_continue_after_noop_and_resume_without_regeneration(
    tmp_path: Path,
) -> None:
    execution_order: list[tuple[str, int]] = []
    (tmp_path / "skills/bootstrap").mkdir(parents=True)

    def executor_with(generate):
        executor = object.__new__(MainExperimentExecutor)
        executor.root = tmp_path
        executor.run_id = "resume_test"
        executor.store = RunStore(tmp_path / "runs", executor.run_id)
        executor.judge_qualification_contract_sha256 = "a" * 64
        executor.registry = SimpleNamespace(current=lambda: None)
        executor.candidate_root = executor.store.root / "skills/candidates"
        executor.local_model = "model/test"
        executor.local_revision = "revision-1"
        executor.experiment = {
            "execution": {
                "evolution_rounds": 2,
                "provisional_candidate_budget_per_block": 2,
            },
            "personas": ["P_WD"],
            "trajectory_sampling": {
                "group_size": 1,
                "training_group_seeds": [42],
            },
            "learning_curve": {"evidence_role": "development_only_never_teacher"},
            "skill_evolution": {"initial_library": "skills/bootstrap"},
        }
        executor.training_plan = SimpleNamespace(
            batches=[
                SimpleNamespace(
                    batch_id="training_batch_01",
                    prospective_validation_for=None,
                    case_ids=["case_01"],
                    persona_assignment={"case_01": "P_WD"},
                ),
                SimpleNamespace(
                    batch_id="training_batch_02",
                    prospective_validation_for="training_batch_01",
                    case_ids=["case_02"],
                    persona_assignment={"case_02": "P_WD"},
                ),
            ]
        )
        executor.generate_training_round = generate

        def score(trajectories, adapter, **kwargs):
            del adapter, kwargs
            round_index = int(trajectories[0].partition.rsplit("_", 1)[1])
            execution_order.append(("score", round_index))
            for trajectory in trajectories:
                executor.store.atomic_json(
                    executor.store.evaluation_path(trajectory.trajectory_id),
                    {
                        "schema_version": 13,
                        "trajectory_id": trajectory.trajectory_id,
                        "case_id": trajectory.case_id,
                        "judge_qualification_contract_sha256": "a" * 64,
                    },
                )
            partition = trajectories[0].partition
            executor.store.atomic_json(
                executor.store.root / "health" / f"pre_scoring_health_{partition}.json",
                {"healthy": True, "counts": {}},
            )
            return {}

        executor.score_trajectories = score
        executor._validate_learning_curve_point_artifact = lambda **_: {
            "identity_baseline": True
        }

        def prepare_curve(*, round_index, **kwargs):
            del kwargs
            execution_order.append(("curve", round_index))
            value = {"round": round_index, "identity_baseline": True}
            executor.store.atomic_json(
                executor.store.root
                / "reports"
                / f"development_curve_point_{round_index:02d}.json",
                value,
            )
            return value

        executor.prepare_development_curve_point = prepare_curve

        def curve_summary():
            completed = len(
                list((executor.store.root / "reports").glob("learning_checkpoint_*.json"))
            )
            value = {
                "run_id": executor.run_id,
                "status": "complete" if completed == 2 else "partial",
                "completed_points": completed,
            }
            executor.store.atomic_json(
                executor.store.root / "reports/development_learning_curve.json",
                value,
            )
            return value

        executor.write_development_learning_curve_summary = curve_summary
        def propose_candidates(**kwargs):
            execution_order.append(("propose", int(kwargs["round_index"])))
            return []

        executor.propose_candidates = propose_candidates

        def revalidate(*, round_index, candidates, carryover_candidates=None):
            del carryover_candidates
            executor.store.atomic_json(
                executor.store.root
                / "reports"
                / f"candidate_source_grounding_round_{round_index:02d}.json",
                {
                    "run_id": executor.run_id,
                    "round": round_index,
                    "valid_candidate_files": [],
                },
            )
            return candidates

        executor.revalidate_candidate_source_grounding = revalidate

        def validate_preceding(
            *, round_index, case_limit, run_manifest_sha256, trajectories, evaluations
        ):
            del case_limit, run_manifest_sha256, trajectories, evaluations
            execution_order.append(("validate", round_index))
            batch_id = f"training_batch_{round_index:02d}"
            source_id = None if round_index == 1 else f"training_batch_{round_index - 1:02d}"
            value = {
                "schema_version": 1,
                "run_id": executor.run_id,
                "validation_batch_id": batch_id,
                "source_batch_id": source_id,
                "status": (
                    "no_predecessor_candidates"
                    if source_id is None
                    else "next_unseen_block_validation_complete"
                ),
                "baseline_active_skill_ids": [],
                "baseline_skill_library_sha256": skill_library_sha256([]),
                "provisional_skill_ids": [],
                "audit_artifacts": {},
                "accepted_skill_ids": [],
                "deferred_skill_ids": [],
                "rejected_skill_ids": [],
                "output_active_skill_ids": [],
                "output_skill_library_sha256": skill_library_sha256([]),
                "completed_at": "2026-08-27T00:00:00+00:00",
            }
            executor.store.atomic_json(
                executor.store.root / "reports" / f"prospective_validation_{batch_id}.json",
                value,
            )
            return [], value

        executor.validate_preceding_block_candidates = validate_preceding
        executor.active_skills = lambda: []
        executor.main_adapter = object()
        executor.store.write_manifest("run", {"schema_version": 2, "run_id": executor.run_id})
        executor.verify_run_manifest = lambda: executor.store.read_manifest("run")
        return executor

    calls: list[int] = []

    def first_generate(round_index, *, case_limit=None, input_skills=None):
        del case_limit
        assert input_skills == []
        calls.append(round_index)
        execution_order.append(("generate", round_index))
        batch_id = f"training_batch_{round_index:02d}"
        case_id = f"case_{round_index:02d}"
        library_hash = skill_library_sha256([])
        trajectory_id = trajectory_identity(
            run_id="resume_test",
            partition=batch_id,
            method="training_policy_sample",
            case_id=case_id,
            persona="P_WD",
            seed=42,
            sample_index=0,
            skill_library_version=library_hash,
        )
        trajectory = _resume_trajectory(
            trajectory_id=trajectory_id,
            group_id=f"{batch_id}.{case_id}.P_WD.seed_42",
            run_id="resume_test",
            partition=batch_id,
            case_id=case_id,
            skill_library_version=library_hash,
        )
        first.store.save_model(first.store.trajectory_path(batch_id, trajectory_id), trajectory)
        return [trajectory]

    first = executor_with(first_generate)
    first_summary = MainExperimentExecutor.train(first)
    assert first_summary.rounds_completed == 2
    assert calls == [1, 2]
    assert execution_order == [
        ("generate", 1),
        ("score", 1),
        ("curve", 1),
        ("validate", 1),
        ("propose", 1),
        ("generate", 2),
        ("score", 2),
        ("curve", 2),
        ("validate", 2),
    ]
    report = json.loads(
        (tmp_path / "runs/resume_test/reports/learning_checkpoint_02.json").read_text(
            encoding="utf-8"
        )
    )
    assert report["status"] == "measured_prequential_learning_checkpoint"
    assert report["accepted_from_preceding_block"] == []

    def must_not_generate(round_index, *, case_limit=None, input_skills=None):
        del input_skills
        pytest.fail("completed checkpoint must not regenerate trajectories")

    resumed = executor_with(must_not_generate)
    resumed_summary = MainExperimentExecutor.train(resumed)
    assert resumed_summary.rounds_completed == 2
    assert execution_order == [
        ("generate", 1),
        ("score", 1),
        ("curve", 1),
        ("validate", 1),
        ("propose", 1),
        ("generate", 2),
        ("score", 2),
        ("curve", 2),
        ("validate", 2),
    ]


def test_accepted_skill_is_loaded_by_the_next_training_batch(tmp_path: Path) -> None:
    executor = object.__new__(MainExperimentExecutor)
    executor.root = tmp_path
    executor.run_id = "skill_carryover_test"
    (tmp_path / "skills/bootstrap").mkdir(parents=True)
    executor.registry = SkillRegistry(tmp_path / "skill_versions")
    executor.experiment = {
        "skill_evolution": {"initial_library": "skills/bootstrap"}
    }

    candidate = synthetic_skills()[-1]
    candidate.status = "active"
    audit = _completed_candidate_audit(
        skill_id=candidate.skill_id,
        source_batch_id="training_batch_01",
        validation_batch_id="training_batch_02",
    )
    audit = audit.model_copy(
        update={"decision": audit.decision.model_copy(update={"decision": "ACCEPT"})}
    )
    MainExperimentExecutor._activate_accepted_skill(executor, candidate, audit)

    executor.training_plan = SimpleNamespace(
        batches=[
            SimpleNamespace(
                batch_id="training_batch_01",
                case_ids=["case_01"],
                persona_assignment={"case_01": "P_WD"},
            ),
            SimpleNamespace(
                batch_id="training_batch_02",
                case_ids=["case_02"],
                persona_assignment={"case_02": "P_WD"},
            ),
        ]
    )
    executor.experiment = {
        "skill_evolution": {"initial_library": "skills/bootstrap"},
        "trajectory_sampling": {
            "group_size": 1,
            "training_group_seeds": [42],
        },
        "execution": {"rollout_workers": 1},
    }
    executor.main_adapter = SimpleNamespace(persona=lambda _: {"id": "P_WD"})
    executor._runner = lambda **_: object()
    observed_skills: list[list[str]] = []

    def load_or_run(**kwargs):
        observed_skills.append([item.skill_id for item in kwargs["skills"]])
        return SimpleNamespace(
            status="memo_submitted",
            trajectory_id=kwargs["trajectory_id"],
        )

    executor._load_or_run = load_or_run
    values = MainExperimentExecutor.generate_training_round(executor, 2)

    assert len(values) == 1
    assert observed_skills == [[candidate.skill_id]]
    assert executor.registry.current() is not None


def test_training_round_uses_checkpoint_library_instead_of_post_crash_registry(
    tmp_path: Path,
) -> None:
    executor = object.__new__(MainExperimentExecutor)
    executor.root = tmp_path
    executor.run_id = "resume_library_binding"
    executor.training_plan = SimpleNamespace(
        batches=[
            SimpleNamespace(
                batch_id="training_batch_01",
                case_ids=["case_01"],
                persona_assignment={"case_01": "P_WD"},
            )
        ]
    )
    executor.experiment = {
        "trajectory_sampling": {"group_size": 1, "training_group_seeds": [42]},
        "execution": {
            "rollout_workers": 1,
            "provisional_candidate_budget_per_block": 2,
        },
    }
    post_crash_skill = synthetic_skills()[0].model_copy(deep=True)
    post_crash_skill.status = "active"
    executor.active_skills = lambda: [post_crash_skill]
    executor.main_adapter = SimpleNamespace(persona=lambda _: {"id": "P_WD"})
    executor._runner = lambda **_: object()
    observed: list[list[str]] = []

    def load_or_run(**kwargs):
        observed.append([item.skill_id for item in kwargs["skills"]])
        return SimpleNamespace(status="memo_submitted", trajectory_id=kwargs["trajectory_id"])

    executor._load_or_run = load_or_run

    MainExperimentExecutor.generate_training_round(executor, 1, input_skills=[])

    assert observed == [[]]


def test_accepted_candidate_cohort_publishes_one_library_version(tmp_path: Path) -> None:
    executor = object.__new__(MainExperimentExecutor)
    executor.root = tmp_path
    executor.run_id = "cohort_activation"
    (tmp_path / "skills/bootstrap").mkdir(parents=True)
    executor.registry = SkillRegistry(tmp_path / "skill_versions")
    executor.experiment = {"skill_evolution": {"initial_library": "skills/bootstrap"}}
    candidates = [item.model_copy(deep=True) for item in synthetic_skills()[:2]]
    for candidate in candidates:
        candidate.status = "provisional"
    audits = []
    for candidate in candidates:
        audit = _completed_candidate_audit(
            skill_id=candidate.skill_id,
            source_batch_id="training_batch_01",
            validation_batch_id="training_batch_02",
        )
        audits.append(
            audit.model_copy(
                update={"decision": audit.decision.model_copy(update={"decision": "ACCEPT"})}
            )
        )

    version = MainExperimentExecutor._activate_accepted_skills(
        executor,
        candidates,
        audits,
    )

    assert executor.registry.current() == version
    assert len([path for path in executor.registry.versions.iterdir() if path.is_dir()]) == 1
    manifest = executor.registry.validate(version, require_current_static_schema=True)
    assert manifest["skills"] == sorted(candidate.skill_id for candidate in candidates)
    assert manifest["evidence"]["transaction"] == "prospective_validation_cohort"


def test_candidate_trials_preserve_irrelevant_case_exploration() -> None:
    executor = object.__new__(MainExperimentExecutor)
    executor.experiment = {
        "execution": {"provisional_candidate_budget_per_block": 2}
    }
    domains = {
        "labor_case": "labor_employment",
        "civil_a": "consumer_contract",
        "civil_b": "tort_liability",
        "civil_c": "marriage_family",
    }
    executor.main_adapter = SimpleNamespace(case_domain=lambda case_id: domains[case_id])
    general, domain = [item.model_copy(deep=True) for item in synthetic_skills()[:2]]
    general.domain = "general"
    domain.domain = "labor_employment"

    assigned = MainExperimentExecutor._embedded_candidate_assignments(
        executor,
        [general, domain],
        list(domains),
        block_index=1,
    )

    assert [item.skill_id for item in assigned["labor_case"]] == [domain.skill_id]
    assert all(
        [item.skill_id for item in assigned[case_id]] == [general.skill_id]
        for case_id in ("civil_a", "civil_b", "civil_c")
    )


def test_two_general_candidate_trials_split_formal_case_support() -> None:
    executor = object.__new__(MainExperimentExecutor)
    executor.experiment = {
        "execution": {"provisional_candidate_budget_per_block": 2}
    }
    executor.main_adapter = SimpleNamespace(case_domain=lambda _: "general")
    candidates = [item.model_copy(deep=True) for item in synthetic_skills()[:2]]
    for candidate in candidates:
        candidate.domain = "general"
    candidates.sort(key=lambda item: item.skill_id)
    case_ids = [f"case_{index}" for index in range(8)]

    assigned = MainExperimentExecutor._embedded_candidate_assignments(
        executor,
        candidates,
        case_ids,
        block_index=1,
    )

    assert [[item.skill_id for item in assigned[case_id]] for case_id in case_ids] == [
        [candidates[(index + 1) % 2].skill_id] for index in range(8)
    ]


def test_same_domain_candidate_trials_rotate_across_singleton_domain_blocks() -> None:
    executor = object.__new__(MainExperimentExecutor)
    executor.experiment = {
        "execution": {"provisional_candidate_budget_per_block": 2}
    }
    executor.main_adapter = SimpleNamespace(case_domain=lambda _: "labor_employment")
    candidates = [item.model_copy(deep=True) for item in synthetic_skills()[:2]]
    for candidate in candidates:
        candidate.domain = "labor_employment"
    candidates.sort(key=lambda item: item.skill_id)

    first = MainExperimentExecutor._embedded_candidate_assignments(
        executor,
        candidates,
        ["block_02_labor_case"],
        block_index=1,
    )
    second = MainExperimentExecutor._embedded_candidate_assignments(
        executor,
        candidates,
        ["block_03_labor_case"],
        block_index=2,
    )

    assert [item.skill_id for item in first["block_02_labor_case"]] == [
        candidates[1].skill_id
    ]
    assert [item.skill_id for item in second["block_03_labor_case"]] == [
        candidates[0].skill_id
    ]


def test_older_deferred_candidate_precedes_newcomer_without_starving_it() -> None:
    executor = object.__new__(MainExperimentExecutor)
    executor.experiment = {
        "execution": {"maximum_concurrent_provisional_candidates": 6}
    }
    executor.main_adapter = SimpleNamespace(case_domain=lambda _: "labor_employment")
    older, newcomer = [item.model_copy(deep=True) for item in synthetic_skills()[:2]]
    older.domain = newcomer.domain = "labor_employment"
    ages = {older.skill_id: 2, newcomer.skill_id: 0}

    assigned = MainExperimentExecutor._embedded_candidate_assignments(
        executor,
        [newcomer, older],
        ["labor_case_a", "labor_case_b"],
        block_index=5,
        candidate_validation_ages=ages,
    )

    assert [item.skill_id for item in assigned["labor_case_a"]] == [older.skill_id]
    assert [item.skill_id for item in assigned["labor_case_b"]] == [newcomer.skill_id]


def test_fresh_candidate_budget_is_not_reduced_by_valid_carryovers() -> None:
    assert fresh_candidate_nomination_slots(
        fresh_budget=2,
        concurrent_budget=6,
        carryover_count=2,
    ) == 2
    assert fresh_candidate_nomination_slots(
        fresh_budget=2,
        concurrent_budget=6,
        carryover_count=4,
    ) == 2
    with pytest.raises(ExecutionError, match="reserved fresh nomination capacity"):
        fresh_candidate_nomination_slots(
            fresh_budget=2,
            concurrent_budget=6,
            carryover_count=5,
        )


def test_tf_grpo_teacher_evidence_excludes_candidate_treatment() -> None:
    group_id = "training_batch_02.case_02.P_WD.seed_42"
    shared_hash = "a" * 64
    rows = [
        SimpleNamespace(
            trajectory_id="control",
            group_id=group_id,
            method="candidate_without",
            skill_library_version=shared_hash,
        ),
        SimpleNamespace(
            trajectory_id="treatment",
            group_id=group_id,
            method="candidate_with",
            skill_library_version="b" * 64,
        ),
        SimpleNamespace(
            trajectory_id="explore_1",
            group_id=group_id,
            method="training_policy_sample",
            skill_library_version=shared_hash,
        ),
        SimpleNamespace(
            trajectory_id="explore_2",
            group_id=group_id,
            method="training_policy_sample",
            skill_library_version=shared_hash,
        ),
    ]

    selected = tf_grpo_teacher_evidence_groups(rows, {group_id})

    assert [item.trajectory_id for item in selected[group_id]] == [
        "control",
        "explore_1",
        "explore_2",
    ]


def test_candidate_cohort_deduplicates_renamed_prompt_document(tmp_path: Path) -> None:
    original = synthetic_skills()[0]
    alias = original.model_copy(
        deep=True,
        update={"skill_id": "general.renamed_alias", "name": "Renamed alias"},
    )
    assert skill_document_semantic_sha256(original) == skill_document_semantic_sha256(alias)
    paths: list[Path] = []
    for candidate in (original, alias):
        path = tmp_path / f"{candidate.skill_id}.yaml"
        path.write_text(
            yaml.safe_dump(candidate.model_dump(mode="json"), sort_keys=False),
            encoding="utf-8",
        )
        paths.append(path)

    unique, duplicates = MainExperimentExecutor._deduplicate_candidate_paths(paths)

    assert unique == [paths[0]]
    assert duplicates == [
        {
            "candidate_path": str(paths[1]),
            "canonical_path": str(paths[0]),
            "canonical_skill_id": original.skill_id,
            "reason": "duplicate_document",
        }
    ]


def test_candidate_cohort_rejects_one_id_with_two_documents(tmp_path: Path) -> None:
    original = synthetic_skills()[0]
    changed = original.model_copy(
        deep=True,
        update={"description": original.description + " 该版本提出了不同的额外建议。"},
    )
    paths = [tmp_path / "first.yaml", tmp_path / "second.yaml"]
    for path, candidate in zip(paths, (original, changed), strict=True):
        path.write_text(
            yaml.safe_dump(candidate.model_dump(mode="json"), sort_keys=False),
            encoding="utf-8",
        )

    with pytest.raises(ExecutionError, match="reuses one skill_id"):
        MainExperimentExecutor._deduplicate_candidate_paths(paths)


def test_prospective_report_is_durable_before_library_pointer_commit(tmp_path: Path) -> None:
    executor = object.__new__(MainExperimentExecutor)
    executor.root = tmp_path
    executor.run_id = "prospective_transaction"
    executor.store = RunStore(tmp_path / "runs", executor.run_id)
    executor.training_plan = SimpleNamespace(
        batches=[
            SimpleNamespace(batch_id="training_batch_01"),
            SimpleNamespace(
                batch_id="training_batch_02",
                prospective_validation_for="training_batch_01",
            ),
        ]
    )
    executor.experiment = {"execution": {"provisional_candidate_budget_per_block": 2}}
    candidate = synthetic_skills()[0].model_copy(deep=True)
    candidate.status = "provisional"
    candidate_path = executor.store.root / "skills" / "candidates" / f"{candidate.skill_id}.yaml"
    candidate_path.parent.mkdir(parents=True)
    candidate_path.write_text(
        yaml.safe_dump(candidate.model_dump(mode="json"), sort_keys=False),
        encoding="utf-8",
    )
    executor.store.write_manifest(
        "training_batch_01__provisionals_ready",
        {
            "input_active_skill_ids": [],
            "input_skill_library_sha256": skill_library_sha256([]),
        },
    )
    executor._validate_provisionals_ready_checkpoint = lambda **_: ({}, [candidate_path])
    audit = _completed_candidate_audit(
        skill_id=candidate.skill_id,
        source_batch_id="training_batch_01",
        validation_batch_id="training_batch_02",
    )
    audit = audit.model_copy(
        update={"decision": audit.decision.model_copy(update={"decision": "ACCEPT"})}
    )
    audit_path = (
        executor.store.root
        / "prospective_audits"
        / f"training_batch_01__on__training_batch_02__{candidate.skill_id}.json"
    )
    executor.store.save_model(audit_path, audit)
    executor.validate_provisional_candidate = lambda *args, **kwargs: audit
    active: list = []
    executor.active_skills = lambda: list(active)
    report_path = executor.store.root / "reports/prospective_validation_training_batch_02.json"

    def commit(candidates, audits):
        assert report_path.is_file(), "commit intent must precede the pointer switch"
        active[:] = MainExperimentExecutor._merged_accepted_library(active, candidates, audits)
        return f"library_{skill_library_sha256(active)[:16]}"

    executor._activate_accepted_skills = commit

    accepted, report = MainExperimentExecutor.validate_preceding_block_candidates(
        executor,
        round_index=2,
        case_limit=None,
        run_manifest_sha256="a" * 64,
        trajectories=[],
        evaluations={},
    )

    assert accepted == [candidate.skill_id]
    assert report["activation_transaction"]["protocol"] == (
        "durable_intent_then_single_pointer_commit_v1"
    )
    assert [item.skill_id for item in active] == [candidate.skill_id]

    # Simulate a crash after the durable report write but before publication.
    active.clear()
    resumed, resumed_report = MainExperimentExecutor.validate_preceding_block_candidates(
        executor,
        round_index=2,
        case_limit=None,
        run_manifest_sha256="a" * 64,
        trajectories=[],
        evaluations={},
    )
    assert resumed == [candidate.skill_id]
    assert resumed_report == report
    assert [item.skill_id for item in active] == [candidate.skill_id]


def test_training_k4_embeds_at_most_one_candidate_and_keeps_three_prompt_peers(
    tmp_path: Path,
) -> None:
    executor = object.__new__(MainExperimentExecutor)
    executor.root = tmp_path
    executor.run_id = "embedded_candidates"
    executor.training_plan = SimpleNamespace(
        batches=[
            SimpleNamespace(
                batch_id="training_batch_02",
                case_ids=["case_02"],
                persona_assignment={"case_02": "P_WD"},
            )
        ]
    )
    executor.experiment = {
        "trajectory_sampling": {"group_size": 4, "training_group_seeds": [42]},
        "execution": {
            "rollout_workers": 1,
            "provisional_candidate_budget_per_block": 2,
        },
    }
    executor.main_adapter = SimpleNamespace(
        persona=lambda _: {"id": "P_WD"},
        case_domain=lambda _: "general",
    )
    executor.active_skills = lambda: []
    executor._runner = lambda **_: object()

    candidate_paths = []
    staged_candidates = synthetic_skills()[:2]
    for candidate in staged_candidates:
        candidate.status = "provisional"
        path = tmp_path / f"{candidate.skill_id}.yaml"
        path.write_text(
            yaml.safe_dump(candidate.model_dump(mode="json"), sort_keys=False),
            encoding="utf-8",
        )
        candidate_paths.append(path)

    observed: list[dict] = []

    def load_or_run(**kwargs):
        observed.append(kwargs)
        return SimpleNamespace(status="memo_submitted", trajectory_id=kwargs["trajectory_id"])

    executor._load_or_run = load_or_run
    values = MainExperimentExecutor.generate_training_round(
        executor,
        1,
        preceding_candidates=candidate_paths,
    )

    assert len(values) == len(observed) == 4
    assert [item["method"] for item in observed] == [
        "candidate_without",
        "candidate_with",
        "training_policy_sample",
        "training_policy_sample",
    ]
    assert [[skill.skill_id for skill in item["skills"]] for item in observed] == [
        [],
        [staged_candidates[0].skill_id],
        [],
        [],
    ]
    assert [item["sample_index"] for item in observed] == [0, 1, 2, 3]
    assert len({item["trajectory_id"] for item in observed}) == 4


def test_sparse_embedded_candidate_audit_uses_only_assigned_shared_controls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executor = object.__new__(MainExperimentExecutor)
    executor.root = tmp_path
    executor.run_id = "embedded_audit"
    executor.store = RunStore(tmp_path / "runs", executor.run_id)
    executor.training_plan = SimpleNamespace(
        batches=[
            SimpleNamespace(batch_id="training_batch_01"),
            SimpleNamespace(
                batch_id="training_batch_02",
                prospective_validation_for="training_batch_01",
                case_ids=["case_02", "case_other_candidate"],
                persona_assignment={
                    "case_02": "P_WD",
                    "case_other_candidate": "P_WD",
                },
            ),
            SimpleNamespace(
                batch_id="training_batch_03",
                prospective_validation_for="training_batch_02",
                case_ids=["case_03"],
                persona_assignment={"case_03": "P_WD"},
            ),
        ]
    )
    executor.experiment = {
        "trajectory_sampling": {"training_group_seeds": [42]},
        "prospective_validation": {
            "minimum_exposed_sessions": 1,
            "minimum_exposed_cases": 1,
            "minimum_exposed_domains": 1,
            "minimum_mean_delta": 0.02,
            "minimum_material_harm_delta": 0.02,
            "maximum_harmful_pair_rate": 0.15,
            "bootstrap_samples": 100,
            "confidence_level": 0.95,
            "require_positive_confidence_lower": False,
            "maximum_global_mean_reward_drop": 0.01,
            "maximum_validation_blocks": 3,
        },
        "statistical_seed": 42,
    }
    executor.main_adapter = SimpleNamespace(
        evaluator_case=lambda _: {},
        case_domain=lambda case_id: (
            "procedure_evidence" if case_id == "case_other_candidate" else "general"
        ),
    )
    executor._candidate_source_signal_family = lambda _: "fact_elicitation"
    executor._runner = lambda **_: pytest.fail("embedded audit must not create a runner")
    monkeypatch.setattr(
        "legal_skill_guard.experiment.executor.trajectory_health_report",
        lambda *args, **kwargs: {
            "healthy": True,
            "blocking_issue_count": 0,
            "counts": {},
        },
    )

    candidate = synthetic_skills()[0]
    candidate.status = "provisional"
    candidate_path = tmp_path / f"{candidate.skill_id}.yaml"
    candidate_path.write_text(
        yaml.safe_dump(candidate.model_dump(mode="json"), sort_keys=False),
        encoding="utf-8",
    )
    other_candidate = synthetic_skills()[1]
    other_candidate.status = "provisional"
    other_candidate_path = tmp_path / f"{other_candidate.skill_id}.yaml"
    other_candidate_path.write_text(
        yaml.safe_dump(other_candidate.model_dump(mode="json"), sort_keys=False),
        encoding="utf-8",
    )
    enabled = candidate.model_copy(deep=True)
    enabled.status = "active"
    other_enabled = other_candidate.model_copy(deep=True)
    other_enabled.status = "active"
    baseline_hash = skill_library_sha256([])
    candidate_hash = skill_library_sha256([enabled])
    other_candidate_hash = skill_library_sha256([other_enabled])
    group_id = "training_batch_02.case_02.P_WD.seed_42"
    baseline = _resume_trajectory(
        trajectory_id="traj_control",
        group_id=group_id,
        run_id=executor.run_id,
        partition="training_batch_02",
        method="candidate_without",
        case_id="case_02",
        domain="general",
        sample_index=0,
        skill_library_version=baseline_hash,
    )
    treatment = _resume_trajectory(
        trajectory_id="traj_treatment",
        group_id=group_id,
        run_id=executor.run_id,
        partition="training_batch_02",
        method="candidate_with",
        case_id="case_02",
        domain="general",
        sample_index=1,
        skill_library_version=candidate_hash,
        skill_delivery_mode="prompt_memory",
        exposed_skill_ids=[candidate.skill_id],
        skill_memory_sha256="b" * 64,
    )
    other_group_id = "training_batch_02.case_other_candidate.P_WD.seed_42"
    other_baseline = _resume_trajectory(
        trajectory_id="traj_other_control",
        group_id=other_group_id,
        run_id=executor.run_id,
        partition="training_batch_02",
        method="candidate_without",
        case_id="case_other_candidate",
        domain="general",
        sample_index=0,
        skill_library_version=baseline_hash,
    )
    other_treatment = _resume_trajectory(
        trajectory_id="traj_other_treatment",
        group_id=other_group_id,
        run_id=executor.run_id,
        partition="training_batch_02",
        method="candidate_with",
        case_id="case_other_candidate",
        domain="general",
        sample_index=1,
        skill_library_version=other_candidate_hash,
        skill_delivery_mode="prompt_memory",
        exposed_skill_ids=[other_candidate.skill_id],
        skill_memory_sha256="c" * 64,
    )

    def evaluation(reward: float):
        return SimpleNamespace(
            reward=SimpleNamespace(final_reward=reward),
            rubric_judgment=SimpleNamespace(expected_action_scores=[]),
            training_metrics=SimpleNamespace(
                substantive_fact_coverage=0.0,
                resolution=0.0,
            ),
            official_metrics=SimpleNamespace(fidelity=1.0),
            safety_metrics=SimpleNamespace(
                repeated_question_rate=0.0,
                premature_final_rate=0.0,
                unsupported_claim_rate=0.0,
                belief_as_fact_rate=0.0,
                critical_fact_recall=0.0,
                hidden_field_leak=False,
            ),
            operational_metrics=SimpleNamespace(
                policy_fallback_rate=0.0,
                client_fallback_rate=0.0,
                memo_fallback=False,
            ),
            mechanism_signals=SimpleNamespace(
                newly_elicited_fact_count=0,
                identified_evidence_gap_count=0,
            ),
        )

    audit = MainExperimentExecutor.validate_provisional_candidate(
        executor,
        candidate_path,
        source_round_index=1,
        validation_round_index=2,
        trajectories=[baseline, treatment, other_baseline, other_treatment],
        evaluations={
            "traj_control": evaluation(0.4),
            # Prompt exposure is the treatment, so its judged effect is retained;
            # the separate mechanism-direction gate still prevents score-only
            # acceptance when no fact/gap/efficiency mechanism is observed.
            "traj_treatment": evaluation(0.7),
            "traj_other_control": evaluation(0.4),
            "traj_other_treatment": evaluation(0.4),
        },
        baseline_skills=[],
        cohort_candidate_paths=[candidate_path, other_candidate_path],
    )

    assert audit.baseline_trajectory_ids == ["traj_control"]
    assert audit.candidate_trajectory_ids == ["traj_treatment"]
    assert audit.decision.reason == "held_out_mechanism_direction_failed"
    assert audit.mechanism_direction_gate is not None
    assert audit.mechanism_direction_gate.reason == "claimed_fact_mechanism_not_reproduced"
    assert audit.current_outcomes[0].delta == pytest.approx(0.3)
    assert audit.current_outcomes[0].raw_reward_with == 0.7


def test_candidate_accumulates_positive_evidence_across_unseen_blocks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executor = object.__new__(MainExperimentExecutor)
    executor.root = tmp_path
    executor.run_id = "cumulative_audit"
    executor.store = RunStore(tmp_path / "runs", executor.run_id)
    executor.training_plan = SimpleNamespace(
        batches=[
            SimpleNamespace(batch_id="training_batch_01"),
            SimpleNamespace(
                batch_id="training_batch_02",
                prospective_validation_for="training_batch_01",
                case_ids=["case_02"],
            ),
            SimpleNamespace(
                batch_id="training_batch_03",
                prospective_validation_for="training_batch_02",
                case_ids=["case_03"],
            ),
            SimpleNamespace(
                batch_id="training_batch_04",
                prospective_validation_for="training_batch_03",
                case_ids=["case_04"],
            ),
        ]
    )
    executor.experiment = {
        "trajectory_sampling": {"training_group_seeds": [42]},
        "prospective_validation": {
            "minimum_exposed_sessions": 2,
            "minimum_exposed_cases": 2,
            "minimum_exposed_domains": 1,
            "minimum_mean_delta": 0.02,
            "minimum_material_harm_delta": 0.02,
            "maximum_harmful_pair_rate": 0.15,
            "bootstrap_samples": 100,
            "confidence_level": 0.95,
            "require_positive_confidence_lower": False,
            "maximum_global_mean_reward_drop": 0.01,
            "maximum_validation_blocks": 3,
        },
        "statistical_seed": 42,
    }
    executor.main_adapter = SimpleNamespace(evaluator_case=lambda _: {})
    executor._candidate_source_signal_family = lambda _: "fact_elicitation"
    monkeypatch.setattr(
        "legal_skill_guard.experiment.executor.trajectory_health_report",
        lambda *args, **kwargs: {
            "healthy": True,
            "blocking_issue_count": 0,
            "counts": {},
            "issues": [],
        },
    )
    candidate = synthetic_skills()[0]
    candidate.status = "provisional"
    candidate_path = tmp_path / "skills/candidates" / f"{candidate.skill_id}.yaml"
    candidate_path.parent.mkdir(parents=True)
    candidate_path.write_text(
        yaml.safe_dump(candidate.model_dump(mode="json"), sort_keys=False),
        encoding="utf-8",
    )
    enabled = candidate.model_copy(deep=True)
    enabled.status = "active"
    baseline_hash = skill_library_sha256([])
    candidate_hash = skill_library_sha256([enabled])

    def trajectory(batch: str, case_id: str, treatment: bool):
        return SimpleNamespace(
            trajectory_id=f"{batch}_{case_id}_{'with' if treatment else 'without'}",
            group_id=f"{batch}.{case_id}.P_WD.seed_42",
            partition=batch,
            method="candidate_with" if treatment else "candidate_without",
            case_id=case_id,
                domain="general",
                skill_library_version=candidate_hash if treatment else baseline_hash,
                skill_delivery_mode="prompt_memory" if treatment else "none",
                exposed_skill_ids=[candidate.skill_id] if treatment else [],
                skill_memory_sha256=("b" if treatment else "a") * 64,
                status="memo_submitted",
            steps=[
                SimpleNamespace(
                        rendered_question=None,
                        action_decision=SimpleNamespace(
                            retrieved_skill_ids=[candidate.skill_id] if treatment else [],
                            activated_skill_ids=[],
                        ),
                )
            ],
        )

    def evaluation(reward: float, fact_count: int):
        return SimpleNamespace(
            reward=SimpleNamespace(final_reward=reward),
            rubric_judgment=SimpleNamespace(expected_action_scores=[]),
            training_metrics=SimpleNamespace(
                substantive_fact_coverage=float(fact_count), resolution=0.0
            ),
            official_metrics=SimpleNamespace(fidelity=1.0),
            safety_metrics=SimpleNamespace(
                repeated_question_rate=0.0,
                premature_final_rate=0.0,
                unsupported_claim_rate=0.0,
                belief_as_fact_rate=0.0,
                critical_fact_recall=0.0,
                hidden_field_leak=False,
            ),
            operational_metrics=SimpleNamespace(
                policy_fallback_rate=0.0,
                client_fallback_rate=0.0,
                memo_fallback=False,
            ),
            mechanism_signals=SimpleNamespace(
                newly_elicited_fact_count=fact_count,
                identified_evidence_gap_count=0,
            ),
        )

    first_pair = [
        trajectory("training_batch_02", "case_02", False),
        trajectory("training_batch_02", "case_02", True),
    ]
    first_evaluations = {
        first_pair[0].trajectory_id: evaluation(0.40, 0),
        first_pair[1].trajectory_id: evaluation(0.45, 1),
    }
    first = MainExperimentExecutor.validate_provisional_candidate(
        executor,
        candidate_path,
        source_round_index=1,
        validation_round_index=2,
        trajectories=first_pair,
        evaluations=first_evaluations,
        baseline_skills=[],
        activate_on_accept=False,
    )
    assert first.decision.decision == "DEFER"
    assert first.validation_batch_ids == ["training_batch_02"]
    assert first.decision.mean_delta_reward == 0.05

    second_pair = [
        trajectory("training_batch_03", "case_03", False),
        trajectory("training_batch_03", "case_03", True),
    ]
    second_evaluations = {
        second_pair[0].trajectory_id: evaluation(0.40, 0),
        second_pair[1].trajectory_id: evaluation(0.45, 1),
    }
    second = MainExperimentExecutor.validate_provisional_candidate(
        executor,
        candidate_path,
        source_round_index=2,
        validation_round_index=3,
        trajectories=second_pair,
        evaluations=second_evaluations,
        baseline_skills=[],
        activate_on_accept=False,
    )
    assert second.decision.decision == "ACCEPT"
    assert second.validation_batch_ids == ["training_batch_02", "training_batch_03"]
    assert len(second.current_outcomes) == 1
    assert len(second.outcomes) == 2
    assert second.decision.exposed_cases == 2
    assert len(second.prior_audit_artifacts) == 1


def test_candidate_pair_health_quarantines_recovery_before_outcomes() -> None:
    reports = [
        {
            "case_id": f"case_{index}",
            "baseline_trajectory_id": f"control_{index}",
            "candidate_trajectory_id": f"treatment_{index}",
            "report": {
                "healthy": index != 0,
                "counts": {"policy_fallback_used": 1} if index == 0 else {},
                "issues": (
                    [
                        {
                            "code": "policy_fallback_used",
                            "trajectory_id": "treatment_0",
                            "turn": 3,
                            "detail": "policy_contract_safe_fallback",
                        }
                    ]
                    if index == 0
                    else []
                ),
            },
        }
        for index in range(4)
    ]

    selection = candidate_pair_health_selection(reports, minimum_healthy_pair_fraction=0.75)

    assert selection["healthy"] is True
    assert selection["eligible_case_ids"] == ["case_1", "case_2", "case_3"]
    assert selection["excluded_pair_count"] == 1
    assert selection["eligible_pair_fraction"] == 0.75
    assert selection["selection_uses_reward_or_candidate_outcome"] is False


def test_singleton_pair_quarantine_is_insufficient_evidence_not_candidate_failure() -> None:
    selection = candidate_pair_health_selection(
        [
            {
                "case_id": "case_sparse",
                "baseline_trajectory_id": "control_sparse",
                "candidate_trajectory_id": "treatment_sparse",
                "report": {
                    "healthy": False,
                    "counts": {"policy_fallback_used": 1},
                    "issues": [
                        {
                            "code": "policy_fallback_used",
                            "trajectory_id": "treatment_sparse",
                            "turn": 2,
                            "detail": "policy_contract_safe_fallback",
                        }
                    ],
                },
            }
        ],
        minimum_healthy_pair_fraction=0.75,
    )

    assert selection["candidate_wide_health_passed"] is True
    assert selection["matrix_coverage_passed"] is False
    assert selection["healthy"] is False
    assert selection["hard_treatment_issue_count"] == 0
    assert selection["eligible_case_ids"] == []


def test_singleton_quarantine_defers_cumulatively_until_validation_horizon(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executor = object.__new__(MainExperimentExecutor)
    executor.root = tmp_path
    executor.run_id = "singleton_quarantine_horizon"
    executor.store = RunStore(tmp_path / "runs", executor.run_id)
    executor.training_plan = SimpleNamespace(
        batches=[
            SimpleNamespace(batch_id="training_batch_01"),
            SimpleNamespace(
                batch_id="training_batch_02",
                prospective_validation_for="training_batch_01",
                case_ids=["case_02"],
            ),
            SimpleNamespace(
                batch_id="training_batch_03",
                prospective_validation_for="training_batch_02",
                case_ids=["case_03"],
            ),
            SimpleNamespace(
                batch_id="training_batch_04",
                prospective_validation_for="training_batch_03",
                case_ids=["case_04"],
            ),
            SimpleNamespace(
                batch_id="training_batch_05",
                prospective_validation_for="training_batch_04",
                case_ids=["case_05"],
            ),
        ]
    )
    executor.experiment = {
        "trajectory_sampling": {"training_group_seeds": [42]},
        "prospective_validation": {
            "minimum_exposed_sessions": 1,
            "minimum_exposed_cases": 1,
            "minimum_exposed_domains": 1,
            "minimum_mean_delta": 0.02,
            "minimum_material_harm_delta": 0.02,
            "maximum_harmful_pair_rate": 0.15,
            "bootstrap_samples": 100,
            "confidence_level": 0.95,
            "require_positive_confidence_lower": False,
            "maximum_global_mean_reward_drop": 0.01,
            "maximum_validation_blocks": 3,
            "minimum_healthy_pair_fraction": 0.75,
        },
        "statistical_seed": 42,
    }
    executor.main_adapter = SimpleNamespace(evaluator_case=lambda _: {})
    executor._candidate_source_signal_family = lambda _: "fact_elicitation"

    def quarantined_pair_health(trajectories, *args, **kwargs):
        treatment = next(item for item in trajectories if item.method == "candidate_with")
        return {
            "healthy": False,
            "blocking_issue_count": 1,
            "counts": {"policy_fallback_used": 1},
            "issues": [
                {
                    "code": "policy_fallback_used",
                    "trajectory_id": treatment.trajectory_id,
                    "turn": 2,
                    "detail": "policy_contract_safe_fallback",
                }
            ],
        }

    monkeypatch.setattr(
        "legal_skill_guard.experiment.executor.trajectory_health_report",
        quarantined_pair_health,
    )
    candidate = synthetic_skills()[0]
    candidate.status = "provisional"
    candidate_path = tmp_path / "skills/candidates" / f"{candidate.skill_id}.yaml"
    candidate_path.parent.mkdir(parents=True)
    candidate_path.write_text(
        yaml.safe_dump(candidate.model_dump(mode="json"), sort_keys=False),
        encoding="utf-8",
    )
    enabled = candidate.model_copy(deep=True)
    enabled.status = "active"
    baseline_hash = skill_library_sha256([])
    candidate_hash = skill_library_sha256([enabled])

    def trajectory(batch: str, case_id: str, treatment: bool):
        return SimpleNamespace(
            trajectory_id=f"{batch}_{case_id}_{'with' if treatment else 'without'}",
            group_id=f"{batch}.{case_id}.P_WD.seed_42",
            partition=batch,
            method="candidate_with" if treatment else "candidate_without",
            case_id=case_id,
            domain="general",
            skill_library_version=candidate_hash if treatment else baseline_hash,
            skill_delivery_mode="prompt_memory" if treatment else "none",
            exposed_skill_ids=[candidate.skill_id] if treatment else [],
            skill_memory_sha256=("b" if treatment else "a") * 64,
            status="memo_submitted",
            steps=[
                SimpleNamespace(
                    rendered_question=None,
                    action_decision=SimpleNamespace(
                        retrieved_skill_ids=[candidate.skill_id] if treatment else [],
                        activated_skill_ids=[],
                    ),
                )
            ],
        )

    audits = []
    for source_round, validation_round, case_id in [
        (1, 2, "case_02"),
        (2, 3, "case_03"),
        (3, 4, "case_04"),
    ]:
        batch_id = f"training_batch_{validation_round:02d}"
        pair = [
            trajectory(batch_id, case_id, False),
            trajectory(batch_id, case_id, True),
        ]
        audits.append(
            MainExperimentExecutor.validate_provisional_candidate(
                executor,
                candidate_path,
                source_round_index=source_round,
                validation_round_index=validation_round,
                trajectories=pair,
                evaluations={},
                baseline_skills=[],
                activate_on_accept=False,
            )
        )

    first, second, terminal = audits
    assert first.decision.decision == "DEFER"
    assert first.decision.reason == "insufficient_independent_exposure_coverage"
    assert first.validation_batch_ids == ["training_batch_02"]
    assert first.candidate_contract_health_passed is True
    assert first.candidate_matrix_coverage_passed is False
    assert first.current_outcomes == []
    assert first.outcomes == []

    assert second.decision.decision == "DEFER"
    assert second.validation_batch_ids == ["training_batch_02", "training_batch_03"]
    assert len(second.prior_audit_artifacts) == 1
    assert second.current_outcomes == []
    assert second.outcomes == []

    # The third quarantined block exhausts the declared horizon before the final
    # training block, so the bounded evidence chain resolves to rejection.
    assert terminal.validation_batch_id == "training_batch_04"
    assert terminal.validation_batch_id != executor.training_plan.batches[-1].batch_id
    assert terminal.decision.decision == "REJECT"
    assert (
        terminal.decision.reason
        == "insufficient_prospective_exposure_after_validation_horizon"
    )
    assert terminal.validation_batch_ids == [
        "training_batch_02",
        "training_batch_03",
        "training_batch_04",
    ]
    assert len(terminal.prior_audit_artifacts) == 2
    assert terminal.candidate_contract_health_passed is True
    assert terminal.candidate_matrix_coverage_passed is False
    assert terminal.current_outcomes == []
    assert terminal.outcomes == []
    assert (
        executor.store.root / "skills/rejected" / f"{candidate.skill_id}.yaml"
    ).is_file()


@pytest.mark.parametrize(
    "recovery_code", ["client_selection_fallback_used", "memo_fallback_used"]
)
def test_nonpolicy_model_recovery_quarantines_pair_instead_of_rejecting_candidate(
    recovery_code: str,
) -> None:
    selection = candidate_pair_health_selection(
        [
            {
                "case_id": "case_recovery",
                "baseline_trajectory_id": "control_recovery",
                "candidate_trajectory_id": "treatment_recovery",
                "report": {
                    "healthy": False,
                    "counts": {recovery_code: 1},
                    "issues": [
                        {
                            "code": recovery_code,
                            "trajectory_id": "treatment_recovery",
                            "turn": 2,
                            "detail": "bounded model recovery",
                        }
                    ],
                },
            }
        ],
        minimum_healthy_pair_fraction=0.75,
    )

    assert selection["candidate_wide_health_passed"] is True
    assert selection["matrix_coverage_passed"] is False
    assert selection["hard_treatment_issue_count"] == 0


def test_persisted_policy_failure_requires_same_trajectory_policy_fallback() -> None:
    def selection(codes: list[str]) -> dict[str, object]:
        return candidate_pair_health_selection(
            [
                {
                    "case_id": "case_policy",
                    "baseline_trajectory_id": "control_policy",
                    "candidate_trajectory_id": "treatment_policy",
                    "report": {
                        "healthy": False,
                        "counts": dict(Counter(codes)),
                        "issues": [
                            {
                                "code": code,
                                "trajectory_id": "treatment_policy",
                                "turn": 1,
                                "detail": "policy health",
                            }
                            for code in codes
                        ],
                    },
                }
            ],
            minimum_healthy_pair_fraction=0.75,
        )

    unanchored = selection(["persisted_policy_contract_failure"])
    anchored = selection(
        ["persisted_policy_contract_failure", "policy_fallback_used"]
    )

    assert unanchored["candidate_wide_health_passed"] is False
    assert unanchored["hard_treatment_issue_count"] == 1
    assert anchored["candidate_wide_health_passed"] is True
    assert anchored["hard_treatment_issue_count"] == 0


def test_truncated_candidate_health_provenance_fails_closed() -> None:
    with pytest.raises(ExecutionError, match="lacks complete issue provenance"):
        candidate_pair_health_selection(
            [
                {
                    "case_id": "case_truncated",
                    "baseline_trajectory_id": "control_truncated",
                    "candidate_trajectory_id": "treatment_truncated",
                    "report": {
                        "healthy": False,
                        "blocking_issue_count": 1,
                        "counts": {"hidden_field_leak": 1},
                        "issues": [],
                        "issues_truncated": 1,
                    },
                }
            ],
            minimum_healthy_pair_fraction=0.75,
        )


def test_candidate_pair_health_keeps_hard_treatment_defect_candidate_wide() -> None:
    selection = candidate_pair_health_selection(
        [
            {
                "case_id": "case_0",
                "baseline_trajectory_id": "control_0",
                "candidate_trajectory_id": "treatment_0",
                "report": {
                    "healthy": False,
                    "counts": {"hidden_field_leak": 1},
                    "issues": [
                        {
                            "code": "hidden_field_leak",
                            "trajectory_id": "treatment_0",
                            "turn": 1,
                            "detail": "forbidden evaluator field",
                        }
                    ],
                },
            },
            *[
                {
                    "case_id": f"case_{index}",
                    "baseline_trajectory_id": f"control_{index}",
                    "candidate_trajectory_id": f"treatment_{index}",
                    "report": {"healthy": True, "counts": {}, "issues": []},
                }
                for index in range(1, 4)
            ],
        ],
        minimum_healthy_pair_fraction=0.75,
    )

    assert selection["eligible_fraction_passed"] is True
    assert selection["healthy"] is False
    assert selection["hard_treatment_issue_count"] == 1


def _completed_candidate_audit(
    *, skill_id: str, source_batch_id: str, validation_batch_id: str
) -> ProspectiveCandidateAudit:
    return ProspectiveCandidateAudit(
        skill_id=skill_id,
        source_batch_id=source_batch_id,
        validation_batch_id=validation_batch_id,
        validation_case_ids=["case_secret"],
        pair_seeds=[42],
        decision=AuditDecision(
            decision="REJECT",
            reason="positive_mean_but_risk_or_harmful_tail",
            pairs=2,
            exposed_pairs=1,
            exposed_cases=1,
            exposed_domains=1,
            mean_delta_reward=0.03,
            median_delta_reward=0.03,
            harmful_pair_rate=0.0,
            severe_risk_count=0,
            unsupported_claim_delta=0.1,
            premature_final_delta=0.0,
            belief_as_fact_delta=0.0,
            repeated_question_delta=0.0,
            critical_fact_recall_delta=0.0,
            policy_fallback_delta=0.0,
            client_fallback_delta=0.0,
            memo_fallback_delta=0.0,
        ),
        paired_estimate=PairedEstimate(
            pairs=1,
            mean_delta=0.03,
            median_delta=0.03,
            confidence_level=0.95,
            lower=-0.01,
            upper=0.07,
            bootstrap_samples=100,
            seed=42,
        ),
        global_regression_passed=True,
        outcomes=[
            PairOutcome(
                pair_id="pair_secret",
                case_id="case_secret",
                domain="contract",
                exposed=True,
                reward_without=0.4,
                reward_with=0.43,
                unsupported_claim_delta=0.1,
                newly_elicited_fact_delta=1.0,
            )
        ],
        baseline_trajectory_ids=["baseline_secret"],
        candidate_trajectory_ids=["candidate_secret"],
        candidate_contract_health_passed=True,
        candidate_matrix_coverage_passed=True,
        source_signal_family="fact_elicitation",
        mechanism_direction_gate=MechanismDirectionGate(
            signal_family="fact_elicitation",
            exposed_cases=1,
            mean_newly_elicited_fact_delta=1.0,
            mean_identified_evidence_gap_delta=0.0,
            mean_question_turn_delta=0.0,
            passed=True,
            reason="fact_gain_positive_without_gap_regression",
        ),
        completed_at="2026-08-31T00:00:00+00:00",
    )


def test_deferred_candidate_audit_chain_cannot_skip_an_unseen_block(
    tmp_path: Path,
) -> None:
    executor = object.__new__(MainExperimentExecutor)
    executor.store = RunStore(tmp_path / "runs", "deferred_chain")
    executor.training_plan = SimpleNamespace(
        batches=[
            SimpleNamespace(batch_id=f"training_batch_{index:02d}")
            for index in range(1, 5)
        ]
    )
    audit = _completed_candidate_audit(
        skill_id="skill_skipped_block",
        source_batch_id="training_batch_03",
        validation_batch_id="training_batch_04",
    )
    audit = audit.model_copy(
        update={
            "validation_batch_ids": ["training_batch_02", "training_batch_04"],
            "decision": audit.decision.model_copy(update={"decision": "DEFER"}),
        }
    )
    executor.store.save_model(
        executor.store.root / "prospective_audits/skipped.json",
        audit,
    )

    with pytest.raises(ExecutionError, match="chain is not contiguous"):
        MainExperimentExecutor._prior_deferred_candidate_audit(
            executor,
            skill_id="skill_skipped_block",
            source_batch_id="training_batch_04",
        )


def test_teacher_feedback_uses_only_completed_observable_case_anonymous_audits(
    tmp_path: Path,
) -> None:
    executor = object.__new__(MainExperimentExecutor)
    executor.run_id = "feedback_test"
    executor.store = RunStore(tmp_path / "runs", executor.run_id)
    executor.training_plan = SimpleNamespace(
        batches=[
            SimpleNamespace(batch_id="training_batch_01"),
            SimpleNamespace(batch_id="training_batch_02"),
            SimpleNamespace(batch_id="training_batch_03"),
        ]
    )
    audit_root = executor.store.root / "prospective_audits"
    first = _completed_candidate_audit(
        skill_id="skill_first",
        source_batch_id="training_batch_01",
        validation_batch_id="training_batch_02",
    )
    future = _completed_candidate_audit(
        skill_id="skill_future",
        source_batch_id="training_batch_02",
        validation_batch_id="training_batch_03",
    )
    executor.store.save_model(audit_root / "first.json", first)
    executor.store.save_model(audit_root / "future.json", future)

    feedback = MainExperimentExecutor._completed_validation_feedback_for_teacher(executor, 2)

    assert [item["skill_id"] for item in feedback] == ["skill_first"]
    serialized = json.dumps(feedback, ensure_ascii=False, sort_keys=True)
    assert "case_secret" not in serialized
    assert "pair_secret" not in serialized
    assert "baseline_secret" not in serialized
    assert feedback[0]["exposed_domain_outcomes"] == [
        {
            "domain": "contract",
            "exposed_pairs": 1,
            "mean_reward_delta": 0.03,
            "minimum_reward_delta": 0.03,
            "harmful_pair_rate": 0.0,
            "mean_newly_elicited_fact_delta": 1.0,
            "mean_identified_evidence_gap_delta": 0.0,
            "mean_question_turn_delta": 0.0,
            "mean_unsupported_claim_delta": 0.1,
            "mean_premature_final_delta": 0.0,
            "mean_belief_as_fact_delta": 0.0,
            "mean_repeated_question_delta": 0.0,
            "mean_critical_fact_recall_delta": 0.0,
            "mean_policy_fallback_delta": 0.0,
            "mean_client_fallback_delta": 0.0,
            "mean_memo_fallback_delta": 0.0,
        }
    ]
    assert len(feedback[0]["audit_artifact_sha256"]) == 64
    assert feedback[0]["candidate_contract_health_passed"] is True
    assert feedback[0]["candidate_matrix_coverage_passed"] is True
    assert "candidate_health_passed" not in feedback[0]
    assert prospective_audit_teacher_feedback(first)["decision"]["reason"] == (
        "positive_mean_but_risk_or_harmful_tail"
    )


def test_frozen_training_batches_exactly_partition_formal_splits() -> None:
    root = Path(__file__).resolve().parents[2]
    adapter = DLawBenchAdapter(
        root / "data/training/legal_skill_guard_dlawbench_style_cn.jsonl",
        root / "third_party/DLawBench/config/personas.json",
        root / "data/training/legal_skill_guard_dlawbench_style_cn.provenance.jsonl",
    )
    plan = load_training_batch_plan(root / "configs/data/main_training_batches.yaml", adapter)
    assert [len(item.case_ids) for item in plan.batches] == [16] * 8
    assert [item.prospective_validation_for for item in plan.batches] == [
        None,
        "training_batch_01",
        "training_batch_02",
        "training_batch_03",
        "training_batch_04",
        "training_batch_05",
        "training_batch_06",
        "training_batch_07",
    ]
    assert len({case_id for batch in plan.batches for case_id in batch.case_ids}) == 128
    assert all(
        len({adapter.case_domain(item) for item in batch.case_ids}) >= 13 for batch in plan.batches
    )


def test_paired_runner_reuses_only_exact_requests_within_one_run(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    executor = object.__new__(MainExperimentExecutor)
    executor.root = root
    executor.run_id = "paired_cache_contract"
    executor.store = RunStore(tmp_path / "runs", executor.run_id)
    executor.roles = yaml.safe_load((root / "configs/models/roles.yaml").read_text())
    executor.experiment = yaml.safe_load(
        (root / "configs/experiments/main_experiment.yaml").read_text()
    )
    executor.local_revision = "frozen_revision_a"
    executor.local_client = SimpleNamespace(model="frozen-local-model")
    executor.client_selector_revision = "frozen_client_revision"
    executor.client_selector_client = SimpleNamespace(model="frozen-client-model")
    executor.client_disclosure_client = executor.local_client
    executor.planner_client = executor.local_client
    executor.shared_experiment_root = tmp_path / "shared"

    first = MainExperimentExecutor._runner(
        executor, paired=True, cache_namespace="acceptance_candidate_a"
    )
    second = MainExperimentExecutor._runner(
        executor, paired=True, cache_namespace="prospective_validation_02"
    )

    assert isinstance(first.policy_client, ReplayCachedChatClient)
    assert first.policy_client.cache_root == second.policy_client.cache_root
    assert first.client_selector.cache_root == second.client_selector.cache_root
    assert first.memo_client.cache_root == second.memo_client.cache_root
    assert str(first.policy_client.cache_root).startswith(str(executor.store.root))

    executor.local_revision = "frozen_revision_b"
    changed_model = MainExperimentExecutor._runner(
        executor, paired=True, cache_namespace="acceptance_candidate_a"
    )
    assert changed_model.policy_client.cache_root != first.policy_client.cache_root

    nonpaired_a = MainExperimentExecutor._runner(
        executor, paired=False, cache_namespace="training_batch_01"
    )
    nonpaired_b = MainExperimentExecutor._runner(
        executor, paired=False, cache_namespace="training_batch_02"
    )
    assert isinstance(nonpaired_a.policy_client, ReplayCachedChatClient)
    assert nonpaired_a.policy_client.cache_root == nonpaired_b.policy_client.cache_root
    assert nonpaired_a.memo_client.cache_root == nonpaired_b.memo_client.cache_root
    # The client router is deterministic infrastructure.  Its exact request key
    # already binds model, current question, disclosure state and finite beliefs,
    # so byte-identical requests may be reused across partitions in the same run.
    assert nonpaired_a.client_selector.cache_root == nonpaired_b.client_selector.cache_root


def test_prompt_memory_uses_skill_knowledge_without_development_outcomes() -> None:
    skill = synthetic_skills()[-1]
    skill.evaluation.mean_delta_reward = 0.75
    skill.provenance.source_case_ids = ["hidden-development-case"]

    memory, exposed = render_skill_memory([skill], domain=skill.domain)

    assert skill.name in memory
    assert skill.description in memory
    assert '"procedure"' in memory
    assert '"question_guidance"' in memory
    assert "candidate_action" not in memory
    assert "0.75" not in memory
    assert "hidden-development-case" not in memory
    assert "不会在你作答后调用规则引擎修改动作" in memory
    assert exposed == [skill.skill_id]


def test_candidate_identity_ignores_invalid_same_name_teacher_sibling() -> None:
    candidate = synthetic_skills()[0].model_copy(deep=True)
    candidate.status = "candidate"
    candidate.provenance.source = "tf_grpo"
    candidate.provenance.source_evidence_cluster_id = "cluster-a"
    candidate.provenance.source_signal_family = "fact_elicitation"
    candidate.provenance.source_case_ids = ["case-a"]
    candidate.provenance.source_trajectory_ids = ["positive", "negative"]
    candidate.provenance.generator_model = "gpt-5.6-luna"
    candidate.provenance.diagnosis_hash = "b" * 64
    diagnosis = SkillDiagnosis.model_validate(
        {
            "group_id": "batch-a",
            "failure_state": {"turn": 1},
            "behavior_difference": {
                "positive_action": "继续询问一个尚未说明的关键事实",
                "negative_action": "在相同状态下直接结束事实询问",
            },
            "causal_hypothesis": "具体追问可能取得新的客户事实，仍待未见案件验证。",
            "proposed_change": "CREATE",
            "skill_scope": candidate.domain,
            "candidate_skill": candidate,
        }
    )
    witness = SourceWitness(
        evidence_cluster_id="cluster-a",
        signal_family="fact_elicitation",
        forks=[
            SourceForkWitness(
                group_id="group-a",
                case_id="case-a",
                domain=candidate.domain,
                divergence_turn=1,
                visible_state_sha256="a" * 64,
                positive_trajectory_id="positive",
                negative_trajectory_id="negative",
                positive_action={"action_type": "ask"},
                negative_action={"action_type": "final"},
                reward_gap=0.2,
            )
        ],
    )
    valid = TeacherProposal(
        group_id="batch-a",
        request_sha256="a" * 64,
        response_sha256="b" * 64,
        teacher_model="gpt-5.6-luna",
        parse_status="valid_candidate",
        source_group_ids=["group-a"],
        source_witness=witness,
        diagnosis=diagnosis,
    )
    invalid_sibling = valid.model_copy(
        deep=True,
        update={
            "response_sha256": "c" * 64,
            "parse_status": "invalid_candidate",
            "static_issues": ["lexical_near_duplicate"],
        },
    )
    stored = candidate.model_copy(deep=True)
    stored.status = "provisional"

    assert _teacher_proposal_matches_candidate(valid, stored) is True
    assert _teacher_proposal_matches_candidate(invalid_sibling, stored) is False


def test_ungated_ablation_loads_source_grounded_candidate_after_audit_metadata_change(
    tmp_path: Path,
) -> None:
    executor = object.__new__(MainExperimentExecutor)
    executor.root = tmp_path
    executor.run_id = "ablation_test"
    executor.store = RunStore(tmp_path / "runs", executor.run_id)
    executor.experiment = {"execution": {"evolution_rounds": 1}}
    candidate = synthetic_skills()[-1]
    candidate.status = "candidate"
    candidate_path = executor.store.root / "skills/candidates" / f"{candidate.skill_id}.yaml"
    candidate_path.parent.mkdir(parents=True)
    candidate_path.write_text(
        yaml.safe_dump(candidate.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    contract_hash = skill_contract_definition_sha256(candidate)
    relative = str(candidate_path.relative_to(tmp_path))
    report_path = executor.store.root / "reports/candidate_source_grounding_round_01.json"
    report_path.parent.mkdir(parents=True)
    report_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "status": "provisional_candidates_staged_after_source_grounding",
                "valid_candidate_files": [relative],
                "records": [
                    {
                        "candidate_file": relative,
                        "candidate_contract_sha256": contract_hash,
                        "valid": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    candidate.status = "rejected"
    candidate.evaluation.mean_delta_reward = -0.2
    candidate_path.write_text(
        yaml.safe_dump(candidate.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    loaded = MainExperimentExecutor.source_grounded_skills_for_ablation(executor)

    assert [item.skill_id for item in loaded] == [candidate.skill_id]
    assert loaded[0].status == "active"
    assert skill_contract_definition_sha256(loaded[0]) == contract_hash


def test_external_test_refuses_to_consume_benchmark_with_empty_library(tmp_path: Path) -> None:
    executor = object.__new__(MainExperimentExecutor)
    executor.root = tmp_path
    executor.run_id = "empty_library"
    executor.store = RunStore(tmp_path / "runs", executor.run_id)
    executor.active_skills = lambda: []
    executor.registry = SimpleNamespace(current=lambda: None)
    run_hash = "b" * 64
    summary = TrainingSummary(
        run_id=executor.run_id,
        run_manifest_sha256=run_hash,
        trajectory_schema_version=16,
        evaluation_schema_version=13,
        rounds_completed=3,
        round_completion_manifests={},
        round_completion_set_sha256=canonical_json_sha256({}),
        accepted_skill_ids=[],
        active_skill_ids=[],
        active_skill_library_version="bootstrap_empty",
        active_skill_library_sha256=skill_library_sha256([]),
        development_learning_curve_sha256="c" * 64,
        completed_at="2026-08-22T00:00:00+00:00",
    )
    frozen_path = executor.store.root / "manifests/training_complete.json"
    executor.store.atomic_json(frozen_path, {"schema_version": 2})
    executor._verified_run_manifest_sha256 = lambda: run_hash
    executor._load_validated_training_summary = lambda **kwargs: summary

    with pytest.raises(ExecutionError, match="empty accepted skill library"):
        MainExperimentExecutor.external_test(executor)


def test_main_persona_and_dialogue_seed_matrices_are_frozen_and_separated() -> None:
    root = Path(__file__).resolve().parents[2]
    config = yaml.safe_load(
        (root / "configs/experiments/main_experiment.yaml").read_text(encoding="utf-8")
    )
    personas = ["P_WD", "P_WS", "P_CS", "P_CD"]
    sampling = config["trajectory_sampling"]
    sensitivity = config["seed_sensitivity"]

    assert config["personas"] == personas
    assert config["statistical_seed"] == 42
    assert sampling["training_group_seeds"] == [42]
    assert sampling["external_evaluation_seeds"] == [42]
    assert config["evaluation"]["aggregate"] == "paired_case_persona_mean"

    assert sensitivity["affects_candidate_selection"] is False
    assert sensitivity["affects_primary_inference"] is False
    assert sensitivity["primary_seed_reused"] == 42
    assert sensitivity["additional_dialogue_seeds"] == [43, 44]
    assert sensitivity["personas"] == personas
    assert set(sensitivity["additional_dialogue_seeds"]).isdisjoint(
        sampling["external_evaluation_seeds"]
    )

    external_path = root / config["data"]["external_evaluation"]
    if not external_path.is_file():
        pytest.skip("Run scripts/prepare_dlawbench.py first")
    external = DLawBenchAdapter(
        external_path,
        root / "third_party/DLawBench/config/personas.json",
    )
    sensitivity_cases = sensitivity["external_case_ids"]
    assert len(sensitivity_cases) == len(set(sensitivity_cases)) == 6
    assert set(sensitivity_cases).issubset(external.case_ids())
    _validate_persona_seed_protocol(
        config,
        available_personas=tuple(personas),
        external_case_ids=external.case_ids(),
    )

    drifted = json.loads(json.dumps(config))
    drifted["trajectory_sampling"]["external_evaluation_seeds"] = [42, 43]
    with pytest.raises(ValueError, match="primary external evaluation"):
        _validate_persona_seed_protocol(
            drifted,
            available_personas=tuple(personas),
            external_case_ids=external.case_ids(),
        )

    drifted_metrics = json.loads(json.dumps(config))
    drifted_metrics["evaluation"]["behavior_metrics"].remove(
        "unique_disclosed_facts_per_question"
    )
    with pytest.raises(ValueError, match="implemented reporting contract"):
        _validate_persona_seed_protocol(
            drifted_metrics,
            available_personas=tuple(personas),
            external_case_ids=external.case_ids(),
        )

    prospective_pairs_per_block = 16 * len(sampling["training_group_seeds"])
    external_pairs = (
        len(external.case_ids()) * len(personas) * len(sampling["external_evaluation_seeds"])
    )
    sensitivity_new_trajectories = (
        len(sensitivity_cases) * len(personas) * len(sensitivity["additional_dialogue_seeds"]) * 2
    )
    assert prospective_pairs_per_block == 16
    assert external_pairs == 120
    assert sensitivity_new_trajectories == 96
