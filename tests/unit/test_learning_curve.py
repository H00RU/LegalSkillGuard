from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from legal_skill_guard.experiment.learning_curve import (
    COHORT_PARETO_DECISION_RULE,
    DEVELOPMENT_CURVE_METRICS,
    PREQUENTIAL_CURVE_METRICS,
    build_current_library_identity_report,
    build_parent_cohort_sentinel_report,
    build_prequential_sentinel_report,
    cohort_pareto_disposition,
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
        opening_inquiry_agenda=initial_plan or {"observations": []},
        initial_investigation_plan={"observations": []},
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
    premature_final_rate: float = 0.0,
    unsupported_claim_rate: float = 0.0,
    belief_as_fact_rate: float = 0.0,
    hidden_field_leak: bool = False,
    client_fallback_rate: float = 0.0,
    disclosed_facts: int = 1,
    evidence_gaps: int = 0,
) -> SimpleNamespace:
    return SimpleNamespace(
        schema_version=14,
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
            premature_final_rate=premature_final_rate,
            unsupported_claim_rate=unsupported_claim_rate,
            belief_as_fact_rate=belief_as_fact_rate,
            hidden_field_leak=hidden_field_leak,
        ),
        operational_metrics=SimpleNamespace(
            policy_fallback_rate=policy_fallback_rate,
            client_fallback_rate=client_fallback_rate,
        ),
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
        method="legal_skill_evolve",
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
        ("safety_metrics", "premature_final_rate"),
        ("safety_metrics", "unsupported_claim_rate"),
        ("safety_metrics", "belief_as_fact_rate"),
        ("safety_metrics", "hidden_field_leak"),
        ("safety_metrics", "repeated_question_rate"),
        ("operational_metrics", "policy_fallback_rate"),
        ("operational_metrics", "client_fallback_rate"),
    )
    assert len(PREQUENTIAL_CURVE_METRICS) == 16
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
        "legal_skill_evolve",
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


def test_training_sentinel_reuses_normal_sample_zero_method_in_shadow() -> None:
    cells = []
    for case_id, method in (
        ("case_a", "training_policy_sample"),
        ("case_b", "training_policy_sample"),
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
        ["training_policy_sample", "training_policy_sample"],
    ]
    assert report["pair_count"] == 2


def test_parent_cohort_report_binds_exact_parent_and_declared_created_increment() -> None:
    parent_rows = []
    current_rows = []
    parent_evaluations = {}
    current_evaluations = {}
    for case_id in ("case_a", "case_b"):
        parent = _trajectory(
            trajectory_id=f"parent-{case_id}",
            method="training_policy_sample",
            case_id=case_id,
            library_version="parent-hash",
            exposed_skill_ids=("general.parent",),
            question_turns=2,
            partition="parent_shadow",
        )
        current = _trajectory(
            trajectory_id=f"current-{case_id}",
            method="training_policy_sample",
            case_id=case_id,
            library_version="current-hash",
            exposed_skill_ids=("general.parent", "general.new"),
            question_turns=2,
            partition="training_batch_02",
        )
        parent_rows.append(parent)
        current_rows.append(current)
        parent_evaluations[parent.trajectory_id] = _evaluation(
            parent, reward=0.2, resolution=0.3, disclosed_facts=1
        )
        current_evaluations[current.trajectory_id] = _evaluation(
            current, reward=0.4, resolution=0.5, disclosed_facts=2
        )

    report = build_parent_cohort_sentinel_report(
        sentinel_id="training_batch_02",
        current_trajectories=current_rows,
        current_evaluations=current_evaluations,
        current_partition="training_batch_02",
        current_library_version="current-hash",
        current_skill_ids={"general.parent", "general.new"},
        parent_trajectories=parent_rows,
        parent_evaluations=parent_evaluations,
        parent_partition="parent_shadow",
        parent_library_version="parent-hash",
        parent_skill_ids={"general.parent"},
        new_skill_increment_ids={"general.new"},
        bootstrap_samples=100,
        bootstrap_seed=17,
    )

    assert report["direction"] == "current_library_minus_parent_library"
    assert report["parent_skill_ids"] == ["general.parent"]
    assert report["new_skill_increment_ids"] == ["general.new"]
    assert report["metrics"]["unique_disclosed_facts"]["parent_library_mean"] == 1.0
    assert report["metrics"]["unique_disclosed_facts"][
        "case_cluster_estimate"
    ]["mean_delta"] == 1.0
    assert "empty_library" not in report["pairs"][0]
    assert report["pairs"][0]["parent_process"]["question_count"] == 2
    assert report["pairs"][0]["current_process"]["question_count"] == 2
    assert report["pairs"][0]["parent_process"]["turns"][0]["question"] == "question-0"
    assert report["pairs"][0]["current_process"]["undisclosed_hidden_facts_included"] is False

    with pytest.raises(ValueError, match="created-or-updated"):
        build_parent_cohort_sentinel_report(
            sentinel_id="training_batch_02",
            current_trajectories=current_rows,
            current_evaluations=current_evaluations,
            current_partition="training_batch_02",
            current_library_version="current-hash",
            current_skill_ids={"general.parent", "general.new"},
            parent_trajectories=parent_rows,
            parent_evaluations=parent_evaluations,
            parent_partition="parent_shadow",
            parent_library_version="parent-hash",
            parent_skill_ids={"general.parent"},
            new_skill_increment_ids={"different.new"},
            bootstrap_samples=100,
        )


def test_parent_cohort_report_accepts_declared_same_id_document_update() -> None:
    parent = _trajectory(
        trajectory_id="parent-case-a",
        method="training_policy_sample",
        case_id="case_a",
        library_version="parent-hash",
        exposed_skill_ids=("domain.civil.fact_investigation",),
        question_turns=3,
        partition="parent_shadow",
    )
    current = _trajectory(
        trajectory_id="current-case-a",
        method="training_policy_sample",
        case_id="case_a",
        library_version="current-hash",
        exposed_skill_ids=("domain.civil.fact_investigation",),
        question_turns=2,
        partition="training_batch_03",
    )
    parent_evaluation = _evaluation(
        parent, reward=0.2, resolution=0.3, disclosed_facts=1
    )
    current_evaluation = _evaluation(
        current, reward=0.4, resolution=0.5, disclosed_facts=2
    )

    report = build_parent_cohort_sentinel_report(
        sentinel_id="training_batch_03",
        current_trajectories=[current],
        current_evaluations={current.trajectory_id: current_evaluation},
        current_partition="training_batch_03",
        current_library_version="current-hash",
        current_skill_ids={"domain.civil.fact_investigation"},
        parent_trajectories=[parent],
        parent_evaluations={parent.trajectory_id: parent_evaluation},
        parent_partition="parent_shadow",
        parent_library_version="parent-hash",
        parent_skill_ids={"domain.civil.fact_investigation"},
        new_skill_increment_ids={"domain.civil.fact_investigation"},
        bootstrap_samples=100,
        bootstrap_seed=17,
    )

    assert report["current_skill_ids"] == ["domain.civil.fact_investigation"]
    assert report["parent_skill_ids"] == ["domain.civil.fact_investigation"]
    assert report["new_skill_increment_ids"] == ["domain.civil.fact_investigation"]
    assert report["metrics"]["unique_disclosed_facts_per_question"][
        "case_cluster_estimate"
    ]["mean_delta"] > 0
    assert report["pairs"][0]["parent_process"]["question_count"] == 3
    assert report["pairs"][0]["current_process"]["question_count"] == 2


def test_current_library_identity_reuses_observations_with_exact_zero_deltas() -> None:
    current = _trajectory(
        trajectory_id="retained-case-a",
        method="training_policy_sample",
        case_id="case_a",
        library_version="retained-hash",
        exposed_skill_ids=("general.retained",),
        question_turns=3,
        partition="training_batch_03",
    )
    evaluation = _evaluation(
        current,
        reward=0.4,
        resolution=0.5,
        disclosed_facts=2,
    )

    report = build_current_library_identity_report(
        sentinel_id="training_batch_03",
        trajectories=[current],
        evaluations={current.trajectory_id: evaluation},
        partition="training_batch_03",
        library_version="retained-hash",
        skill_ids={"general.retained"},
        bootstrap_samples=100,
        bootstrap_seed=17,
    )

    assert report["report_type"] == "prequential_current_library_identity"
    assert report["direction"] == "current_library_minus_parent_library"
    assert report["no_pending_cohort"] is True
    assert report["current_skill_ids"] == ["general.retained"]
    assert report["parent_skill_ids"] == ["general.retained"]
    assert report["new_skill_increment_ids"] == []
    assert report["partition_mapping"] == {
        "current": "training_batch_03",
        "parent": "training_batch_03",
    }
    pair = report["pairs"][0]
    assert pair["current_trajectory_id"] == current.trajectory_id
    assert pair["parent_trajectory_id"] == current.trajectory_id
    assert all(value == 0 for value in pair["paired_delta"].values())
    assert all(
        metric["case_cluster_estimate"]["mean_delta"] == 0
        for metric in report["metrics"].values()
    )


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        ({"persona": "P_CD"}, "not paired exactly"),
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


def test_prequential_statistics_defer_shared_plan_check_to_isolation_artifact() -> None:
    baseline, baseline_evaluation, current, current_evaluation = _paired_cell(
        case_id="case_a",
        persona="P_WD",
        baseline_reward=0.2,
        current_reward=0.4,
        baseline_resolution=0.3,
        current_resolution=0.5,
    )
    current.initial_investigation_plan = {"facts": [{"fact_id": "skill-mediated"}]}
    report = build_prequential_sentinel_report(
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
    assert report["initial_infrastructure_identity"]["passed"] is True


def test_identity_baseline_is_fail_closed_for_nonempty_or_duplicate_inputs() -> None:
    current = _trajectory(
        trajectory_id="current",
        method="legal_skill_evolve",
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


def _cohort_gate_config() -> dict[str, object]:
    return {
        "schema_version": 1,
        "decision_rule": COHORT_PARETO_DECISION_RULE,
        "effect_direction": "current_library_minus_parent_library",
        "primary_endpoint": "unique_disclosed_facts_per_question",
        "protected_endpoints": ["unique_disclosed_facts", "question_turns"],
        "endpoint_rules": {
            "unique_disclosed_facts_per_question": {
                "direction": "higher",
                "margin": 0.02,
            },
            "unique_disclosed_facts": {"direction": "higher", "margin": 0.0},
            "question_turns": {"direction": "lower", "margin": 0.0},
        },
    }


def _cohort_curve(
    *,
    primary_interval: tuple[float, float] = (-0.02, 0.08),
    fact_interval: tuple[float, float] = (0.0, 0.5),
    question_interval: tuple[float, float] = (-0.5, -0.1),
) -> dict[str, object]:
    def estimate(mean: float, interval: tuple[float, float]) -> dict[str, object]:
        return {
            "pairs": 2,
            "mean_delta": mean,
            "median_delta": mean,
            "confidence_level": 0.95,
            "lower": interval[0],
            "upper": interval[1],
            "bootstrap_samples": 500,
            "seed": 17,
        }

    return {
        "direction": "current_library_minus_parent_library",
        "pair_count": 3,
        "case_cluster_count": 2,
        "bootstrap": {
            "unit": "case_id",
            "samples": 500,
            "confidence_level": 0.95,
            "seed": 17,
        },
        "metrics": {
            "unique_disclosed_facts_per_question": {
                "case_cluster_estimate": estimate(0.03, primary_interval),
            },
            "unique_disclosed_facts": {
                "case_cluster_estimate": estimate(0.25, fact_interval),
            },
            "question_turns": {
                "case_cluster_estimate": estimate(-0.3, question_interval),
            },
        },
        "cases": [
            {"case_id": "case_a", "pair_count": 2},
            {"case_id": "case_b", "pair_count": 1},
        ],
        "pairs": [
            {"pair_id": "pair_a_1", "case_id": "case_a"},
            {"pair_id": "pair_a_2", "case_id": "case_a"},
            {"pair_id": "pair_b_1", "case_id": "case_b"},
        ],
    }


def test_cohort_pareto_disposition_passes_only_when_all_intervals_are_noninferior() -> None:
    disposition = cohort_pareto_disposition(
        {"curve": _cohort_curve()},
        gate_config=_cohort_gate_config(),
    )

    assert disposition["decision"] == "pass"
    assert disposition["interval_noninferiority_passed"] is True
    assert disposition["harmed_endpoints"] == []
    assert disposition["inconclusive_endpoints"] == []
    assert disposition["endpoint_dispositions"][
        "unique_disclosed_facts_per_question"
    ]["noninferiority_threshold"] == -0.02
    assert disposition["endpoint_dispositions"][
        "unique_disclosed_facts_per_question"
    ]["decision"] == "pass"
    assert disposition["endpoint_dispositions"]["question_turns"][
        "oriented_estimate"
    ] == {
        "mean_delta": 0.3,
        "median_delta": 0.3,
        "lower": 0.1,
        "upper": 0.5,
    }


def test_cohort_pareto_disposition_harm_precedes_an_inconclusive_primary() -> None:
    curve = _cohort_curve(
        primary_interval=(-0.03, 0.01),
        question_interval=(0.02, 0.08),
    )
    disposition = cohort_pareto_disposition(
        curve,
        gate_config=_cohort_gate_config(),
    )

    assert disposition["decision"] == "harm"
    assert disposition["interval_noninferiority_passed"] is False
    assert disposition["harmed_endpoints"] == ["question_turns"]
    assert disposition["inconclusive_endpoints"] == [
        "unique_disclosed_facts_per_question"
    ]
    assert disposition["endpoint_dispositions"]["question_turns"]["decision"] == "harm"


def test_cohort_pareto_disposition_keeps_boundary_overlap_inconclusive() -> None:
    curve = _cohort_curve(primary_interval=(-0.03, -0.02))
    disposition = cohort_pareto_disposition(
        curve,
        gate_config=_cohort_gate_config(),
    )

    assert disposition["decision"] == "inconclusive"
    assert disposition["interval_noninferiority_passed"] is False
    assert disposition["harmed_endpoints"] == []
    assert disposition["inconclusive_endpoints"] == [
        "unique_disclosed_facts_per_question"
    ]


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        ("bootstrap_unit", "requires case_id bootstrap"),
        ("estimate_pairs", "case-bootstrap binding drifted"),
        ("estimate_samples", "case-bootstrap binding drifted"),
        ("estimate_seed", "case-bootstrap binding drifted"),
        ("estimate_confidence", "case-bootstrap binding drifted"),
        ("case_count", "case records do not match"),
        ("pair_count", "pair records do not match"),
        ("per_case_pair_binding", "pair records do not bind"),
        ("missing_metric", "endpoint estimate is missing"),
    ],
)
def test_cohort_pareto_disposition_rejects_case_bootstrap_binding_drift(
    mutation: str,
    match: str,
) -> None:
    curve = _cohort_curve()
    if mutation == "bootstrap_unit":
        curve["bootstrap"]["unit"] = "trajectory_id"  # type: ignore[index]
    elif mutation == "estimate_pairs":
        curve["metrics"]["unique_disclosed_facts"]["case_cluster_estimate"][  # type: ignore[index]
            "pairs"
        ] = 3
    elif mutation == "estimate_samples":
        curve["metrics"]["unique_disclosed_facts"]["case_cluster_estimate"][  # type: ignore[index]
            "bootstrap_samples"
        ] = 501
    elif mutation == "estimate_seed":
        curve["metrics"]["unique_disclosed_facts"]["case_cluster_estimate"][  # type: ignore[index]
            "seed"
        ] = 18
    elif mutation == "estimate_confidence":
        curve["metrics"]["unique_disclosed_facts"]["case_cluster_estimate"][  # type: ignore[index]
            "confidence_level"
        ] = 0.9
    elif mutation == "case_count":
        curve["case_cluster_count"] = 3
    elif mutation == "pair_count":
        curve["pair_count"] = 4
    elif mutation == "per_case_pair_binding":
        curve["pairs"][1]["case_id"] = "case_b"  # type: ignore[index]
    else:
        del curve["metrics"]["unique_disclosed_facts"]  # type: ignore[index]

    with pytest.raises(ValueError, match=match):
        cohort_pareto_disposition(curve, gate_config=_cohort_gate_config())


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        ("extra_field", "configuration fields drifted"),
        ("duplicate_endpoint", "unique by role"),
        ("missing_rule", "rules do not match"),
        ("invalid_direction", "direction is invalid"),
        ("negative_margin", "margin must be non-negative"),
        ("nonfinite_margin", "finite number"),
        ("nonstring_endpoint", "unique by role"),
        ("schema_bool", "unsupported.*schema"),
        ("non_parent_direction", "must compare.*parent"),
        ("direction_drift", "effect direction does not match"),
    ],
)
def test_cohort_pareto_disposition_rejects_unfrozen_or_invalid_gate_config(
    mutation: str,
    match: str,
) -> None:
    config = deepcopy(_cohort_gate_config())
    curve = _cohort_curve()
    if mutation == "extra_field":
        config["posthoc_override"] = True
    elif mutation == "duplicate_endpoint":
        config["protected_endpoints"] = [
            "unique_disclosed_facts_per_question",
            "question_turns",
        ]
    elif mutation == "missing_rule":
        del config["endpoint_rules"]["question_turns"]  # type: ignore[index]
    elif mutation == "invalid_direction":
        config["endpoint_rules"]["question_turns"]["direction"] = "minimize"  # type: ignore[index]
    elif mutation == "negative_margin":
        config["endpoint_rules"]["question_turns"]["margin"] = -0.1  # type: ignore[index]
    elif mutation == "nonfinite_margin":
        config["endpoint_rules"]["question_turns"]["margin"] = float("nan")  # type: ignore[index]
    elif mutation == "nonstring_endpoint":
        config["protected_endpoints"] = [1, "question_turns"]
    elif mutation == "schema_bool":
        config["schema_version"] = True
    elif mutation == "non_parent_direction":
        config["effect_direction"] = "current_library_minus_empty_library"
    else:
        curve["direction"] = "current_library_minus_empty_library"

    with pytest.raises(ValueError, match=match):
        cohort_pareto_disposition(curve, gate_config=config)
