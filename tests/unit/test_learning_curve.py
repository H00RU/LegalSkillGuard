from __future__ import annotations

from types import SimpleNamespace

import pytest

from legal_skill_guard.experiment.learning_curve import (
    DEVELOPMENT_CURVE_METRICS,
    PREQUENTIAL_CURVE_METRICS,
    build_prequential_sentinel_report,
)


def _trajectory(
    *,
    trajectory_id: str,
    method: str,
    case_id: str,
    persona: str = "P_WD",
    seed: int = 42,
    sample_index: int = 0,
    library_version: str,
    exposed_skill_ids: tuple[str, ...] = (),
    question_turns: int = 2,
    initial_plan: dict[str, object] | None = None,
    partition: str = "development_sentinel_02",
) -> SimpleNamespace:
    return SimpleNamespace(
        trajectory_id=trajectory_id,
        run_id="run_learning_curve",
        partition=partition,
        group_id=f"sentinel.{case_id}.{persona}.seed_{seed}",
        method=method,
        case_id=case_id,
        domain="civil",
        jurisdiction="CN",
        persona=persona,
        seed=seed,
        sample_index=sample_index,
        model_id="Qwen/Qwen3-8B",
        model_revision="frozen-revision",
        skill_library_version=library_version,
        skill_delivery_mode="prompt_memory" if exposed_skill_ids else "none",
        exposed_skill_ids=sorted(exposed_skill_ids),
        skill_memory_sha256=("b" if exposed_skill_ids else "a") * 64,
        status="memo_submitted",
        opening=f"opening:{case_id}",
        max_turns=8,
        initial_investigation_plan=initial_plan or {"facts": []},
        planning_attempts=[],
        planning_safe_partial=False,
        initial_visible_state_coverage_attempts=[],
        initial_visible_state_covered_target_ids=[],
        initial_visible_state_coverage_token_usage={"prompt_tokens": 0},
        steps=[
            SimpleNamespace(
                rendered_question=f"question-{index}",
                action_decision=SimpleNamespace(
                    activated_skill_ids=[], retrieved_skill_ids=list(exposed_skill_ids)
                ),
            )
            for index in range(question_turns)
        ],
    )


def _evaluation(
    trajectory: SimpleNamespace,
    *,
    reward: float,
    resolution: float,
    elicitation: float = 0.5,
    fidelity: float = 1.0,
    critical_fact_recall: float = 0.5,
    repeated_question_rate: float = 0.0,
    policy_fallback_rate: float = 0.0,
    disclosed_facts: int = 1,
    evidence_gaps: int = 0,
) -> SimpleNamespace:
    return SimpleNamespace(
        schema_version=13,
        trajectory_id=trajectory.trajectory_id,
        case_id=trajectory.case_id,
        judge_model="openai/gpt-oss-20b",
        judge_qualification_contract_sha256="judge-contract",
        official_metrics=SimpleNamespace(
            resolution=resolution,
            elicitation=elicitation,
            fidelity=fidelity,
        ),
        safety_metrics=SimpleNamespace(
            critical_fact_recall=critical_fact_recall,
            repeated_question_rate=repeated_question_rate,
        ),
        operational_metrics=SimpleNamespace(policy_fallback_rate=policy_fallback_rate),
        reward=SimpleNamespace(final_reward=reward),
        mechanism_signals=SimpleNamespace(
            newly_elicited_fact_count=disclosed_facts,
            identified_evidence_gap_count=evidence_gaps,
        ),
    )


def _paired_cell(
    *,
    case_id: str,
    persona: str,
    baseline_reward: float,
    current_reward: float,
    baseline_resolution: float,
    current_resolution: float,
) -> tuple[SimpleNamespace, SimpleNamespace, SimpleNamespace, SimpleNamespace]:
    baseline = _trajectory(
        trajectory_id=f"empty-{case_id}-{persona}",
        method="control_no_library",
        case_id=case_id,
        persona=persona,
        library_version="empty-hash",
        question_turns=1,
        partition="development_sentinel_02_empty_shadow",
    )
    current = _trajectory(
        trajectory_id=f"current-{case_id}-{persona}",
        method="legal_skill_guard",
        case_id=case_id,
        persona=persona,
        library_version="current-hash",
        exposed_skill_ids=("skill.ask_next",),
        question_turns=2,
        partition="development_sentinel_02",
    )
    return (
        baseline,
        _evaluation(
            baseline,
            reward=baseline_reward,
            resolution=baseline_resolution,
            disclosed_facts=1,
        ),
        current,
        _evaluation(
            current,
            reward=current_reward,
            resolution=current_resolution,
            disclosed_facts=2,
        ),
    )


def test_prequential_report_pairs_exact_cells_and_bootstraps_case_clusters() -> None:
    cells = [
        _paired_cell(
            case_id="case_a",
            persona="P_WD",
            baseline_reward=0.2,
            current_reward=0.4,
            baseline_resolution=0.3,
            current_resolution=0.5,
        ),
        _paired_cell(
            case_id="case_a",
            persona="P_CD",
            baseline_reward=0.3,
            current_reward=0.3,
            baseline_resolution=0.4,
            current_resolution=0.4,
        ),
        _paired_cell(
            case_id="case_b",
            persona="P_WD",
            baseline_reward=0.1,
            current_reward=0.4,
            baseline_resolution=0.2,
            current_resolution=0.5,
        ),
    ]
    empty = [cell[0] for cell in reversed(cells)]
    current = [cell[2] for cell in cells]
    empty_evaluations = {cell[1].trajectory_id: cell[1] for cell in cells}
    current_evaluations = {cell[3].trajectory_id: cell[3] for cell in cells}

    kwargs = {
        "sentinel_id": "S2",
        "current_trajectories": current,
        "current_evaluations": current_evaluations,
        "current_partition": "development_sentinel_02",
        "current_library_version": "current-hash",
        "current_skill_ids": {"skill.ask_next"},
        "empty_library_version": "empty-hash",
        "empty_partition": "development_sentinel_02_empty_shadow",
        "empty_trajectories": empty,
        "empty_evaluations": empty_evaluations,
        "bootstrap_samples": 500,
        "bootstrap_seed": 17,
    }
    first = build_prequential_sentinel_report(**kwargs)
    second = build_prequential_sentinel_report(**kwargs)

    assert DEVELOPMENT_CURVE_METRICS == (
        ("official_metrics", "resolution"),
        ("official_metrics", "elicitation"),
        ("official_metrics", "fidelity"),
        ("safety_metrics", "critical_fact_recall"),
        ("safety_metrics", "repeated_question_rate"),
        ("operational_metrics", "policy_fallback_rate"),
    )
    assert len(PREQUENTIAL_CURVE_METRICS) == 11
    assert first["pair_count"] == 3
    assert first["case_cluster_count"] == 2
    assert [item["case_id"] for item in first["cases"]] == ["case_a", "case_b"]
    assert first["cases"][0]["paired_delta_mean"]["reward"] == 0.1
    assert first["cases"][1]["paired_delta_mean"]["reward"] == 0.3
    assert first["metrics"]["reward"]["pair_mean_delta"] == pytest.approx(0.166667)
    assert first["metrics"]["reward"]["case_cluster_estimate"]["mean_delta"] == 0.2
    assert first["metrics"]["question_turns"]["case_cluster_estimate"]["mean_delta"] == 1.0
    assert (
        first["metrics"]["reward"]["case_cluster_estimate"]
        == second["metrics"]["reward"]["case_cluster_estimate"]
    )
    assert first["initial_infrastructure_identity"]["passed"] is True
    assert first["initial_infrastructure_identity"]["stepwise_intervention_isolation"] == (
        "required_prompt_memory_pre_scoring_gate_not_verified_here"
    )
    assert first["partition_mapping"] == {
        "current": "development_sentinel_02",
        "empty": "development_sentinel_02_empty_shadow",
    }


@pytest.mark.parametrize(
    "method",
    [
        "training_policy_sample",
        "candidate_without",
        "legal_skill_guard",
        "control_no_library",
    ],
)
def test_empty_current_library_uses_explicit_zero_identity_baseline(method: str) -> None:
    current = _trajectory(
        trajectory_id="empty-current",
        method=method,
        case_id="case_a",
        library_version="empty-hash",
        question_turns=3,
    )
    evaluation = _evaluation(current, reward=0.4, resolution=0.5, disclosed_facts=2)

    report = build_prequential_sentinel_report(
        sentinel_id="S0",
        current_trajectories=[current],
        current_evaluations={current.trajectory_id: evaluation},
        current_partition="development_sentinel_02",
        current_library_version="empty-hash",
        current_skill_ids=set(),
        empty_library_version="empty-hash",
        empty_partition="development_sentinel_02",
        identity_baseline=True,
        bootstrap_samples=100,
        bootstrap_seed=23,
    )

    assert report["identity_baseline"] is True
    assert all(report["pairs"][0]["paired_delta"][name] == 0 for name in report["metrics"])
    assert all(
        metric["case_cluster_estimate"]["lower"] == 0
        and metric["case_cluster_estimate"]["upper"] == 0
        for metric in report["metrics"].values()
    )


def test_training_sentinel_reuses_each_normal_sample_zero_method_in_shadow() -> None:
    cells = []
    for case_id, method in (
        ("case_candidate", "candidate_without"),
        ("case_exploration", "training_policy_sample"),
    ):
        empty = _trajectory(
            trajectory_id=f"empty-{case_id}",
            method=method,
            case_id=case_id,
            library_version="empty-hash",
            partition="training_batch_03_empty_shadow",
        )
        current = _trajectory(
            trajectory_id=f"current-{case_id}",
            method=method,
            case_id=case_id,
            library_version="current-hash",
            exposed_skill_ids=("skill.ask_next",),
            partition="training_batch_03",
        )
        cells.append(
            (
                empty,
                _evaluation(empty, reward=0.2, resolution=0.3),
                current,
                _evaluation(current, reward=0.3, resolution=0.4),
            )
        )

    report = build_prequential_sentinel_report(
        sentinel_id="S3",
        current_trajectories=[cell[2] for cell in cells],
        current_evaluations={cell[3].trajectory_id: cell[3] for cell in cells},
        current_partition="training_batch_03",
        current_library_version="current-hash",
        current_skill_ids={"skill.ask_next"},
        empty_partition="training_batch_03_empty_shadow",
        empty_library_version="empty-hash",
        empty_trajectories=[cell[0] for cell in cells],
        empty_evaluations={cell[1].trajectory_id: cell[1] for cell in cells},
        bootstrap_samples=100,
    )

    assert report["initial_infrastructure_identity"]["method_pairs"] == [
        ("candidate_without", "candidate_without"),
        ("training_policy_sample", "training_policy_sample"),
    ]
    assert report["pair_count"] == 2


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        ({"persona": "P_CD"}, "not paired exactly"),
        (
            {"initial_investigation_plan": {"facts": [{"fact_id": "different"}]}},
            "initial infrastructure identity",
        ),
        ({"method": "training_policy_sample"}, "method pair is not compatible"),
    ],
)
def test_prequential_report_rejects_unmatched_or_nonisolated_arms(
    mutation: dict[str, object], match: str
) -> None:
    baseline, baseline_evaluation, current, current_evaluation = _paired_cell(
        case_id="case_a",
        persona="P_WD",
        baseline_reward=0.2,
        current_reward=0.4,
        baseline_resolution=0.3,
        current_resolution=0.5,
    )
    for field, value in mutation.items():
        setattr(current, field, value)

    with pytest.raises(ValueError, match=match):
        build_prequential_sentinel_report(
            sentinel_id="S1",
            current_trajectories=[current],
            current_evaluations={current.trajectory_id: current_evaluation},
            current_partition="development_sentinel_02",
            current_library_version="current-hash",
            current_skill_ids={"skill.ask_next"},
            empty_library_version="empty-hash",
            empty_partition="development_sentinel_02_empty_shadow",
            empty_trajectories=[baseline],
            empty_evaluations={baseline.trajectory_id: baseline_evaluation},
            bootstrap_samples=100,
        )


def test_prequential_report_rejects_evaluator_or_skill_membership_drift() -> None:
    baseline, baseline_evaluation, current, current_evaluation = _paired_cell(
        case_id="case_a",
        persona="P_WD",
        baseline_reward=0.2,
        current_reward=0.4,
        baseline_resolution=0.3,
        current_resolution=0.5,
    )
    current_evaluation.judge_model = "different-judge"
    with pytest.raises(ValueError, match="incompatible judges"):
        build_prequential_sentinel_report(
            sentinel_id="S1",
            current_trajectories=[current],
            current_evaluations={current.trajectory_id: current_evaluation},
            current_partition="development_sentinel_02",
            current_library_version="current-hash",
            current_skill_ids={"skill.ask_next"},
            empty_library_version="empty-hash",
            empty_partition="development_sentinel_02_empty_shadow",
            empty_trajectories=[baseline],
            empty_evaluations={baseline.trajectory_id: baseline_evaluation},
            bootstrap_samples=100,
        )

    current_evaluation.judge_model = baseline_evaluation.judge_model
    with pytest.raises(ValueError, match="outside the declared library"):
        build_prequential_sentinel_report(
            sentinel_id="S1",
            current_trajectories=[current],
            current_evaluations={current.trajectory_id: current_evaluation},
            current_partition="development_sentinel_02",
            current_library_version="current-hash",
            current_skill_ids={"different.skill"},
            empty_library_version="empty-hash",
            empty_partition="development_sentinel_02_empty_shadow",
            empty_trajectories=[baseline],
            empty_evaluations={baseline.trajectory_id: baseline_evaluation},
            bootstrap_samples=100,
        )


def test_identity_baseline_is_fail_closed_for_nonempty_or_duplicate_inputs() -> None:
    current = _trajectory(
        trajectory_id="current",
        method="legal_skill_guard",
        case_id="case_a",
        library_version="current-hash",
        exposed_skill_ids=("skill.ask_next",),
    )
    evaluation = _evaluation(current, reward=0.4, resolution=0.5)

    with pytest.raises(ValueError, match="only when the current library is empty"):
        build_prequential_sentinel_report(
            sentinel_id="S1",
            current_trajectories=[current],
            current_evaluations={current.trajectory_id: evaluation},
            current_partition="development_sentinel_02",
            current_library_version="current-hash",
            current_skill_ids={"skill.ask_next"},
            empty_library_version="empty-hash",
            empty_partition="development_sentinel_02_empty_shadow",
            identity_baseline=True,
            bootstrap_samples=100,
        )

    with pytest.raises(ValueError, match="must not receive duplicate"):
        build_prequential_sentinel_report(
            sentinel_id="S0",
            current_trajectories=[current],
            current_evaluations={current.trajectory_id: evaluation},
            current_partition="development_sentinel_02",
            current_library_version="empty-hash",
            current_skill_ids=set(),
            empty_library_version="empty-hash",
            empty_partition="development_sentinel_02",
            empty_trajectories=[],
            empty_evaluations={},
            identity_baseline=True,
            bootstrap_samples=100,
        )
