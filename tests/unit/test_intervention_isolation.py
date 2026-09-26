from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

import pytest

from legal_skill_guard.experiment.executor import ExecutionError, MainExperimentExecutor
from legal_skill_guard.experiment.intervention_isolation import (
    final_training_holdout_intervention_isolation_report,
    parent_library_intervention_isolation_report,
    skill_library_intervention_isolation_report,
    skill_memory_contract_report,
    skill_memory_delivery_issues,
)
from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.schemas.skill import Provenance, SkillContract
from legal_skill_guard.schemas.trajectory import Message
from legal_skill_guard.skills.memory import (
    EMPTY_PLANNER_SKILL_MEMORY,
    EMPTY_SKILL_MEMORY,
    SKILL_MEMORY_HEADER,
    render_selected_skill_card,
    render_skill_memory,
)


def _rendered_memory(skill_ids: list[str]) -> str:
    if not skill_ids:
        return EMPTY_SKILL_MEMORY
    return (
        SKILL_MEMORY_HEADER
        + "\n"
        + json.dumps(
            [{"skill_id": item} for item in sorted(skill_ids)],
            ensure_ascii=False,
            sort_keys=True,
        )
    )


def _action(target_id: str) -> dict[str, object]:
    return {
        "action_type": "ask",
        "target_type": "fact",
        "target_id": target_id,
        "reason": f"询问{target_id}",
        "expected_information": target_id,
        "content": f"请说明{target_id}？",
        "constraints": [],
        "confidence": 0.8,
    }


def _skill(
    *, description: str = "先确认争议所涉合同关系，再依次询问未明确的关键事实。"
) -> SkillContract:
    return SkillContract(
        skill_id="skill.fact_priority",
        name="合同事实优先询问",
        version="1.0.0",
        domain="contract",
        objective="fact_elicitation",
        description=description,
        applicability_cues=["合同争议且关键履行事实尚未明确"],
        procedure=["先识别尚未回答的高重要性事实，再提出一个原子问题"],
        question_guidance=["一次只询问一个客户能够直接回答的事实"],
        expected_effects=["减少重复提问并提高新增事实取得率"],
        contraindications=["客户已明确表示该事实无法获知时不要机械重问"],
        failure_modes=["把多个事实合并成一个问题会降低可回答性"],
        status="active",
        provenance=Provenance(source="tf_grpo"),
    )


def _step(
    trajectory_id: str,
    *,
    retrieved_skill_ids: list[str],
    raw_output: str = "frozen generation",
    activated_skill_ids: list[str] | None = None,
    rendered_memory: str = EMPTY_SKILL_MEMORY,
) -> SimpleNamespace:
    action = _action("fact_a")
    activated = list(activated_skill_ids or [])
    return SimpleNamespace(
        turn=1,
        visible_input=[
            Message(role="system", content="冻结律师基础协议\n" + rendered_memory),
            Message(role="user", content="visible state"),
        ],
        state_before={"session_id": trajectory_id, "turn": 0, "facts": []},
        state_patch={"observations": [], "issue_labels": [], "risk_flags_add": []},
        state_after={"session_id": trajectory_id, "turn": 1, "facts": []},
        raw_policy_output=raw_output,
        parse_mode="json",
        policy_attempts=[],
        policy_health_violations=[],
        post_skill_health_violations=[],
        target_selection_attempts=[],
        proposed_action=action,
        action_decision=SimpleNamespace(
            original=action,
            final=action,
            retrieved_skill_ids=list(retrieved_skill_ids),
            activated_skill_ids=activated,
            blocked_skill_ids=[],
            changes=(
                [{"skill_id": activated[0], "before": action, "after": action}] if activated else []
            ),
        ),
        rendered_question=str(action["content"]),
        client_response="现有信息里没有这项具体情况，我需要再核实。",
        client_input_sha256="client-request",
        client_response_kind="unavailable",
        client_selected_fact_ids=[],
        stop_gate_verdict="CONTINUE",
        stop_gate_reason="continue",
        lawyer_finish_reason="stop",
    )


def _trajectory(
    *,
    trajectory_id: str,
    method: str,
    library_hash: str,
    exposed_skill_ids: list[str],
    partition: str = "training_batch_02",
    sample_index: int | None = None,
    raw_output: str = "frozen generation",
    activated_skill_ids: list[str] | None = None,
) -> SimpleNamespace:
    exposed = sorted(exposed_skill_ids)
    rendered_memory = _rendered_memory(exposed)
    return SimpleNamespace(
        trajectory_id=trajectory_id,
        group_id="training_batch_02.case_a.P_WD.seed_42",
        sample_index=sample_index if sample_index is not None else 0,
        run_id="run_test",
        method=method,
        partition=partition,
        case_id="case_a",
        domain="contract",
        jurisdiction="CN",
        persona="P_WD",
        seed=42,
        model_id="model/test",
        model_revision="revision-1",
        skill_library_version=library_hash,
        skill_delivery_mode="prompt_memory" if exposed else "none",
        exposed_skill_ids=exposed,
        skill_memory_sha256=hashlib.sha256(rendered_memory.encode("utf-8")).hexdigest(),
        planner_exposed_skill_ids=[],
        planner_skill_memory_sha256=hashlib.sha256(
            EMPTY_PLANNER_SKILL_MEMORY.encode("utf-8")
        ).hexdigest(),
        status="memo_submitted",
        opening="合同履行发生争议。",
        max_turns=8,
        steps=[
            _step(
                trajectory_id,
                retrieved_skill_ids=exposed,
                raw_output=raw_output,
                activated_skill_ids=activated_skill_ids,
                rendered_memory=rendered_memory,
            )
        ],
        initial_investigation_plan={"observations": []},
        planning_visible_input=[],
        planning_attempts=[],
        planning_safe_partial=False,
        initial_visible_state_coverage_attempts=[],
        initial_visible_state_covered_target_ids=[],
        initial_visible_state_coverage_token_usage={"prompt": 0, "completion": 0},
        memo="同一份条件性分析。",
        memo_attempts=[],
        memo_health_violations=[],
        memo_safe_fallback=False,
        elapsed_seconds=1.0,
        created_at="2026-09-07T00:00:00+00:00",
        error=None,
    )


def _library_pair() -> tuple[list[SimpleNamespace], list[SimpleNamespace]]:
    current = _trajectory(
        trajectory_id="traj_current",
        method="training_policy_sample",
        library_hash="current_hash",
        exposed_skill_ids=["skill.ask_priority", "skill.avoid_repeat"],
        partition="training_batch_03_curve_current",
        sample_index=2,
    )
    empty = _trajectory(
        trajectory_id="traj_empty",
        method="training_policy_sample",
        library_hash="empty_hash",
        exposed_skill_ids=[],
        partition="training_batch_03_curve_empty",
        sample_index=2,
    )
    return [current], [empty]


def test_generic_delivery_audit_accepts_direct_policy_memory_without_planner() -> None:
    trajectory = _trajectory(
        trajectory_id="traj_dual_injection",
        method="training_policy_sample",
        library_hash="library_hash",
        exposed_skill_ids=["skill.fact_priority"],
    )

    issues = skill_memory_delivery_issues(
        trajectory,
        expected_ids={"skill.fact_priority"},
    )

    assert "retired_planner_skill_exposure_present" not in issues
    assert "retired_planner_artifact_present" not in issues


def test_generic_delivery_audit_rejects_retired_planner_artifact() -> None:
    trajectory = _trajectory(
        trajectory_id="traj_planner_drift",
        method="training_policy_sample",
        library_hash="library_hash",
        exposed_skill_ids=["skill.fact_priority"],
    )
    trajectory.planner_exposed_skill_ids = ["skill.fact_priority"]
    trajectory.planning_visible_input = [
        Message(role="system", content="退役规划器协议\n" + EMPTY_PLANNER_SKILL_MEMORY)
    ]

    issues = skill_memory_delivery_issues(
        trajectory,
        expected_ids={"skill.fact_priority"},
    )

    assert "retired_planner_skill_exposure_present" in issues
    assert "retired_planner_artifact_present" in issues


def _library_trajectory(
    *,
    trajectory_id: str,
    library_hash: str,
    skills: list[SkillContract],
    partition: str,
    case_id: str,
    domain: str,
) -> SimpleNamespace:
    """Build a trace whose prompt bytes come from the declared real documents."""

    rendered_memory, exposed_ids = render_skill_memory(skills, domain=domain)
    trajectory = _trajectory(
        trajectory_id=trajectory_id,
        method="training_policy_sample",
        library_hash=library_hash,
        exposed_skill_ids=exposed_ids,
        partition=partition,
    )
    trajectory.case_id = case_id
    trajectory.domain = domain
    trajectory.group_id = f"training_batch_02.{case_id}.P_WD.seed_42"
    trajectory.steps[0].visible_input[0].content = "冻结律师基础协议\n" + rendered_memory
    trajectory.skill_memory_sha256 = hashlib.sha256(rendered_memory.encode("utf-8")).hexdigest()
    return trajectory


def _cohort_skill(
    skill_id: str,
    *,
    domain: str,
    description: str,
) -> SkillContract:
    return _skill(description=description).model_copy(
        update={
            "skill_id": skill_id,
            "name": skill_id.replace(".", " "),
            "domain": domain,
        }
    )


def test_executor_owned_memory_contract_rejects_tampered_document_with_updated_self_hash() -> None:
    skill = _skill()
    expected_memory, expected_ids = render_skill_memory([skill], domain="contract")
    trajectory = _trajectory(
        trajectory_id="traj_tampered",
        method="training_policy_sample",
        library_hash="executor_owned_library",
        exposed_skill_ids=expected_ids,
    )
    tampered_memory = expected_memory.replace(
        "合同争议且关键履行事实尚未明确", "机械重复已经回答的低价值事实"
    )
    assert tampered_memory != expected_memory
    trajectory.steps[0].visible_input[0].content = "冻结律师基础协议\n" + tampered_memory
    # An artifact can consistently lie about its own prompt bytes.  The formal
    # check must compare those bytes with the executor-owned SkillContract.
    trajectory.skill_memory_sha256 = hashlib.sha256(tampered_memory.encode("utf-8")).hexdigest()

    report = skill_memory_contract_report(
        [trajectory],
        {"executor_owned_library": [skill]},
    )

    assert report["passed"] is False
    assert report["failure_count"] == 1
    assert "turn_policy_actual_prompt_skill_document_mismatch" in report["rows"][0]["issues"]
    assert (
        "trajectory_skill_memory_sha256_mismatch_expected_document" in report["rows"][0]["issues"]
    )


def test_executor_owned_memory_contract_requires_an_observed_policy_turn() -> None:
    trajectory = _trajectory(
        trajectory_id="traj_empty",
        method="training_policy_sample",
        library_hash="empty_library",
        exposed_skill_ids=[],
    )
    trajectory.steps = []

    report = skill_memory_contract_report([trajectory], {"empty_library": []})

    assert report["passed"] is False
    assert report["rows"][0]["issues"] == ["trajectory_has_no_policy_turn_for_skill_memory_audit"]


def test_executor_owned_memory_contract_accepts_complete_document_exposure() -> None:
    skill = _skill()
    trajectory = _library_trajectory(
        trajectory_id="traj_selected",
        library_hash="executor_owned_library",
        skills=[skill],
        partition="training_batch_02",
        case_id="case_a",
        domain="contract",
    )
    report = skill_memory_contract_report(
        [trajectory],
        {"executor_owned_library": [skill]},
    )

    assert report["passed"] is True


def test_executor_owned_memory_contract_rejects_retired_factored_artifacts() -> None:
    skill = _skill()
    trajectory = _library_trajectory(
        trajectory_id="traj_misattributed_selection",
        library_hash="executor_owned_library",
        skills=[skill],
        partition="training_batch_02",
        case_id="case_a",
        domain="contract",
    )
    step = trajectory.steps[0]
    step.action_decision.activated_skill_ids = [skill.skill_id]
    step.action_decision.changes = []
    step.target_selection_attempts = [
        SimpleNamespace(
            selected_skill_ids=[skill.skill_id],
            expanded_skill_cards=[render_selected_skill_card(skill)],
            selected_target_id="communication_records",
            proposed_target_ids=["communication_records", "payment_record"],
            proposed_skill_ids_by_target={
                "communication_records": [skill.skill_id],
                "payment_record": [skill.skill_id],
            },
        )
    ]

    report = skill_memory_contract_report(
        [trajectory],
        {"executor_owned_library": [skill]},
    )

    assert report["passed"] is False
    assert "retired_factored_policy_artifact_present" in report["rows"][0]["issues"]
    assert "retired_self_reported_skill_activation_present" in report["rows"][0]["issues"]


def test_score_gate_rejects_prompt_bytes_not_owned_by_executor(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    skill = _skill()
    expected_memory, expected_ids = render_skill_memory([skill], domain="contract")
    trajectory = _trajectory(
        trajectory_id="traj_tampered_score_gate",
        method="training_policy_sample",
        library_hash="executor_owned_library",
        exposed_skill_ids=expected_ids,
    )
    tampered_memory = expected_memory.replace(
        "合同争议且关键履行事实尚未明确", "机械重复已经回答的低价值事实"
    )
    trajectory.steps[0].visible_input[0].content = "冻结律师基础协议\n" + tampered_memory
    trajectory.skill_memory_sha256 = hashlib.sha256(tampered_memory.encode("utf-8")).hexdigest()
    monkeypatch.setattr(
        "legal_skill_guard.experiment.executor.trajectory_health_report",
        lambda *_args, **_kwargs: {
            "schema_version": 2,
            "healthy": True,
            "trajectory_count": 1,
            "blocking_issue_count": 0,
            "counts": {},
            "issues": [],
            "issues_truncated": 0,
            "quality_diagnostics": {},
        },
    )
    executor = MainExperimentExecutor.__new__(MainExperimentExecutor)
    executor.store = RunStore(tmp_path / "runs", "run_test")
    executor.experiment = {"execution": {"judge_workers": 1}}
    executor.evaluator = SimpleNamespace(
        evaluate=lambda *_args: pytest.fail("semantic judge must not see forged prompt bytes")
    )
    adapter = SimpleNamespace(evaluator_case=lambda _case_id: {})

    with pytest.raises(ExecutionError, match="executor-owned skill memory contract"):
        MainExperimentExecutor.score_trajectories(
            executor,
            [trajectory],
            adapter,
            expected_skill_libraries={"executor_owned_library": [skill]},
        )

    persisted = json.loads(
        (executor.store.root / "health/pre_scoring_health_training_batch_02.json").read_text(
            encoding="utf-8"
        )
    )
    assert persisted["healthy"] is False
    assert persisted["counts"]["skill_memory_contract_failure"] == 1


def test_skill_library_pair_accepts_fixed_document_bundle() -> None:
    current, empty = _library_pair()
    report = skill_library_intervention_isolation_report(
        current,
        empty,
        {"skill.ask_priority", "skill.avoid_repeat"},
        "training_batch_03_curve_current",
        "training_batch_03_curve_empty",
    )
    assert report["passed"] is True
    assert report["exposed_pair_count"] == 1
    assert report["pairs"][0]["exposed_intervention_skill_ids"] == [
        "skill.ask_priority",
        "skill.avoid_repeat",
    ]


def test_final_holdout_isolation_wraps_the_same_strict_pair_audit() -> None:
    current, empty = _library_pair()

    report = final_training_holdout_intervention_isolation_report(
        current,
        empty,
        {"skill.ask_priority", "skill.avoid_repeat"},
        "training_batch_03_curve_current",
        "training_batch_03_curve_empty",
    )

    assert report["passed"] is True
    assert report["scope"] == "same_B8_accumulated_library_diagnostic"
    assert report["underlying_skill_library_isolation"]["passed"] is True
    assert report["uses_reward_or_semantic_outcome"] is False


def test_final_holdout_isolation_fails_closed_for_empty_selected_library() -> None:
    _, empty = _library_pair()

    report = final_training_holdout_intervention_isolation_report(
        empty,
        empty,
        set(),
        "training_batch_03_curve_empty",
        "training_batch_03_curve_empty",
    )

    assert report["passed"] is False
    assert report["failure_reasons"] == ["selected_library_is_empty"]
    assert report["underlying_skill_library_isolation"] is None


def test_external_pair_allows_one_partition_but_keeps_prompt_isolation() -> None:
    current, empty = _library_pair()
    current[0].partition = "external_test"
    current[0].method = "legal_skill_evolve"
    empty[0].partition = "external_test"
    empty[0].method = "control_no_library"
    report = skill_library_intervention_isolation_report(
        current,
        empty,
        {"skill.ask_priority", "skill.avoid_repeat"},
        "external_test",
        "external_test",
        require_distinct_partitions=False,
    )
    assert report["passed"] is True
    assert report["scope"].endswith("external_test")


def test_skill_library_pair_rejects_undeclared_document() -> None:
    current, empty = _library_pair()
    current[0].exposed_skill_ids.append("skill.undeclared")
    current[0].steps[0].action_decision.retrieved_skill_ids.append("skill.undeclared")
    report = skill_library_intervention_isolation_report(
        current,
        empty,
        {"skill.ask_priority", "skill.avoid_repeat"},
        "training_batch_03_curve_current",
        "training_batch_03_curve_empty",
    )
    assert report["passed"] is False
    assert report["pairs"][0]["reason"] == "skill_library_prompt_exposure_mismatch"


def test_skill_library_pair_rejects_retired_planner_difference() -> None:
    current, empty = _library_pair()
    current[0].initial_investigation_plan = {"observations": [{"fact_id": "different"}]}
    report = skill_library_intervention_isolation_report(
        current,
        empty,
        {"skill.ask_priority", "skill.avoid_repeat"},
        "training_batch_03_curve_current",
        "training_batch_03_curve_empty",
    )
    assert report["passed"] is False
    assert report["pairs"][0]["reason"] == "retired_planner_artifact_present"


def test_skill_library_pair_rejects_retired_continuation_head_artifacts() -> None:
    current, empty = _library_pair()
    for row in (current[0], empty[0]):
        memory = _rendered_memory(list(row.exposed_skill_ids))
        row.steps[0].continuation_visible_input = [
            Message(role="system", content="冻结继续决策\n" + memory),
            Message(role="user", content="相同可见状态"),
        ]
        row.steps[0].continuation_decision = SimpleNamespace(
            continue_inquiry=True,
            reason="仍有可回答事实",
            confidence=0.8,
        )
        row.steps[0].continuation_attempts = [{"raw_output": "same"}]
    current[0].steps[0].continuation_decision.reason = "技能臂发生了漂移"

    report = skill_library_intervention_isolation_report(
        current,
        empty,
        {"skill.ask_priority", "skill.avoid_repeat"},
        "training_batch_03_curve_current",
        "training_batch_03_curve_empty",
    )

    assert report["passed"] is False
    assert "retired_factored_policy_artifact_present" in report["pairs"][0]["reason"]


def test_parent_library_audit_reports_complete_general_and_domain_exposure() -> None:
    parent_skill = _cohort_skill(
        "general.parent_guard",
        domain="general",
        description="先核实已经明确的信息，再避免重复询问并保留尚待核实事项。",
    )
    general_cohort = _cohort_skill(
        "general.new_gap_probe",
        domain="general",
        description="识别尚未回答且会改变分析的事实，每轮只提出一个具体问题。",
    )
    domain_cohort = _cohort_skill(
        "contract.new_performance_probe",
        domain="contract",
        description="合同争议中优先核实履行时间、方式和结果中的一个未明事实。",
    )
    parent_skills = [parent_skill]
    current_skills = [parent_skill, general_cohort, domain_cohort]
    cases = [
        ("case_contract_a", "contract"),
        ("case_contract_b", "contract"),
        ("case_evidence", "procedure_evidence"),
    ]
    current = [
        _library_trajectory(
            trajectory_id=f"current_{case_id}",
            library_hash="current_hash",
            skills=current_skills,
            partition="training_batch_02",
            case_id=case_id,
            domain=domain,
        )
        for case_id, domain in cases
    ]
    parent = [
        _library_trajectory(
            trajectory_id=f"parent_{case_id}",
            library_hash="parent_hash",
            skills=parent_skills,
            partition="cohort_parent_shadow_training_batch_02",
            case_id=case_id,
            domain=domain,
        )
        for case_id, domain in cases
    ]

    report = parent_library_intervention_isolation_report(
        current,
        parent,
        current_skills,
        parent_skills,
        "training_batch_02",
        "cohort_parent_shadow_training_batch_02",
    )

    assert report["passed"] is True
    assert report["cohort_exposed_case_count"] == 3
    assert report["cohort_exposed_pair_count"] == 3
    assert report["cohort_skill_exposure"][general_cohort.skill_id] == {
        "domain": "general",
        "expected_case_count": 3,
        "expected_pair_count": 3,
        "observed_case_count": 3,
        "observed_pair_count": 3,
        "routing_complete": True,
    }
    assert report["cohort_skill_exposure"][domain_cohort.skill_id] == {
        "domain": "contract",
        "expected_case_count": 2,
        "expected_pair_count": 2,
        "observed_case_count": 2,
        "observed_pair_count": 2,
        "routing_complete": True,
    }


def test_parent_library_audit_requires_identical_trace_when_cohort_not_applicable() -> None:
    parent_skill = _cohort_skill(
        "general.parent_guard",
        domain="general",
        description="先核实已经明确的信息，再避免重复询问并保留尚待核实事项。",
    )
    domain_cohort = _cohort_skill(
        "contract.new_performance_probe",
        domain="contract",
        description="合同争议中优先核实履行时间、方式和结果中的一个未明事实。",
    )
    parent_skills = [parent_skill]
    current_skills = [parent_skill, domain_cohort]
    current = _library_trajectory(
        trajectory_id="current_nonapplicable",
        library_hash="current_hash",
        skills=current_skills,
        partition="training_batch_02",
        case_id="case_evidence",
        domain="procedure_evidence",
    )
    parent = _library_trajectory(
        trajectory_id="parent_nonapplicable",
        library_hash="parent_hash",
        skills=parent_skills,
        partition="cohort_parent_shadow_training_batch_02",
        case_id="case_evidence",
        domain="procedure_evidence",
    )

    report = parent_library_intervention_isolation_report(
        [current],
        [parent],
        current_skills,
        parent_skills,
        "training_batch_02",
        "cohort_parent_shadow_training_batch_02",
    )
    assert report["passed"] is True
    assert report["pairs"][0]["reason"] == ("no_applicable_cohort_skill_trace_identical")

    current.steps[0].raw_policy_output = "different generation"
    failed = parent_library_intervention_isolation_report(
        [current],
        [parent],
        current_skills,
        parent_skills,
        "training_batch_02",
        "cohort_parent_shadow_training_batch_02",
    )
    assert failed["passed"] is False
    assert failed["pairs"][0]["reason"] == "nonapplicable_cohort_trace_divergence"


def test_parent_library_audit_rejects_changed_parent_document() -> None:
    parent_skill = _cohort_skill(
        "general.parent_guard",
        domain="general",
        description="先核实已经明确的信息，再避免重复询问并保留尚待核实事项。",
    )
    changed_parent = parent_skill.model_copy(
        update={"description": "这是同一标识下被擅自修改的父库文档。"}
    )
    cohort = _cohort_skill(
        "general.new_gap_probe",
        domain="general",
        description="识别尚未回答且会改变分析的事实，每轮只提出一个具体问题。",
    )
    parent_skills = [parent_skill]
    current_skills = [changed_parent, cohort]
    current = _library_trajectory(
        trajectory_id="current_changed_parent",
        library_hash="current_hash",
        skills=current_skills,
        partition="training_batch_02",
        case_id="case_contract",
        domain="contract",
    )
    parent = _library_trajectory(
        trajectory_id="parent_unchanged",
        library_hash="parent_hash",
        skills=parent_skills,
        partition="cohort_parent_shadow_training_batch_02",
        case_id="case_contract",
        domain="contract",
    )

    report = parent_library_intervention_isolation_report(
        [current],
        [parent],
        current_skills,
        parent_skills,
        "training_batch_02",
        "cohort_parent_shadow_training_batch_02",
    )

    assert report["passed"] is False
    assert report["matrix_failures"] == [
        {
            "reason": "updated_playbook_version_not_incremented",
            "skill_ids": [parent_skill.skill_id],
        }
    ]
