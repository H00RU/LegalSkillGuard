from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from legal_skill_guard.evolution.teacher import (
    PLAYBOOK_SKILL_ID,
    PlaybookModeArtifact,
    playbook_map_input_binding_sha256,
)
from legal_skill_guard.experiment.executor import (
    COHORT_GATE_ENDPOINT_DIRECTIONS,
    COHORT_PARENT_EFFECT_DIRECTION,
    ExecutionError,
    MainExperimentExecutor,
    _expected_final_training_holdout_config,
    _expected_practical_retention_gate,
    _playbook_teacher_evidence_created,
    add_document_transition_feedback,
    final_training_holdout_safeguard_disposition,
    prequential_input_library_feedback,
    skill_library_sha256,
)
from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.schemas.experiment import ResearchTrajectory
from legal_skill_guard.utils.hashing import sha256_file
from scripts.audit_main_run_progress import (
    CURVE_METRICS,
    _curve_summary_contract,
    _teacher_contract,
)
from tests.skill_fixtures import synthetic_skills


def _executor(tmp_path: Path, *, run_id: str = "curve_contract") -> MainExperimentExecutor:
    executor = object.__new__(MainExperimentExecutor)
    executor.root = tmp_path
    executor.run_id = run_id
    executor.store = RunStore(tmp_path / "runs", run_id)
    executor.candidate_root = executor.store.root / "skills/candidates"
    executor.judge_qualification_contract_sha256 = "a" * 64
    executor.local_model = "model/test"
    executor.local_revision = "revision-1"
    executor.experiment = {
        "execution": {
            "maximum_new_skills_per_block": 1,
            "teacher_call_budget_per_round": 3,
        },
        "personas": ["P_WD"],
        "trajectory_sampling": {
            "group_size": 1,
            "training_group_seeds": [42],
        },
        "learning_curve": {
            "bootstrap_samples": 100,
            "bootstrap_seed": 17,
            "confidence_level": 0.95,
            "evidence_role": "development_only_never_teacher_or_acceptance",
            "next_block_scope_feasibility": {
                "minimum_matching_sentinel_cases": 1,
            },
        },
        "evaluation": {"primary_endpoint": "unique_disclosed_facts_per_question"},
        "skill_admission": {"maintenance_interval_blocks": 2},
    }
    executor.training_plan = SimpleNamespace(
        batches=[
            SimpleNamespace(
                batch_id="training_batch_01",
                case_ids=["case_test"],
                persona_assignment={"case_test": "P_WD"},
            )
        ]
    )
    executor.learning_curve_sentinels = {"training_batch_01": ["case_test"]}
    executor.registry = SimpleNamespace(current=lambda: None)
    executor.active_skills = lambda: []
    executor.main_adapter = object()
    return executor


def _trajectory_evaluation(trajectory: ResearchTrajectory) -> SimpleNamespace:
    return SimpleNamespace(
        schema_version=14,
        trajectory_id=trajectory.trajectory_id,
        case_id=trajectory.case_id,
        judge_model="openai/gpt-oss-20b",
        judge_qualification_contract_sha256="a" * 64,
        official_metrics=SimpleNamespace(
            resolution=0.4,
            elicitation=0.5,
            fidelity=1.0,
        ),
        safety_metrics=SimpleNamespace(
            critical_fact_recall=0.5,
            premature_final_rate=0.0,
            unsupported_claim_rate=0.0,
            belief_as_fact_rate=0.0,
            hidden_field_leak=False,
            repeated_question_rate=0.0,
        ),
        operational_metrics=SimpleNamespace(
            policy_fallback_rate=0.0,
            client_fallback_rate=0.0,
        ),
        reward=SimpleNamespace(final_reward=0.45),
        mechanism_signals=SimpleNamespace(
            newly_elicited_fact_count=1,
            identified_evidence_gap_count=0,
        ),
    )


def test_prequential_regression_feedback_prioritizes_fact_recovery() -> None:
    def metric(delta: float) -> dict[str, object]:
        return {
            "case_cluster_estimate": {
                "mean_delta": delta,
                "lower": delta - 0.1,
                "upper": delta + 0.1,
            }
        }

    report = {
        "curve": {
            "direction": COHORT_PARENT_EFFECT_DIRECTION,
            "identity_baseline": False,
            "metrics": {
                "unique_disclosed_facts_per_question": metric(-0.05),
                "unique_disclosed_facts": metric(-0.25),
                "question_turns": metric(-1.0),
                "identified_evidence_gaps": metric(0.75),
                "repeated_question_rate": metric(-0.18),
                "reward": metric(0.05),
            },
            "cases": [
                {
                    "case_id": "consumer_a",
                    "paired_delta_mean": {
                        "unique_disclosed_facts_per_question": -0.2,
                        "unique_disclosed_facts": -1.0,
                        "question_turns": 0.0,
                        "identified_evidence_gaps": 1.0,
                        "repeated_question_rate": 0.0,
                        "reward": -0.1,
                    },
                },
                {
                    "case_id": "labor_a",
                    "paired_delta_mean": {
                        "unique_disclosed_facts_per_question": 0.1,
                        "unique_disclosed_facts": 0.5,
                        "question_turns": -1.0,
                        "identified_evidence_gaps": 0.5,
                        "repeated_question_rate": -0.1,
                        "reward": 0.2,
                    },
                },
            ],
            "pairs": [
                {
                    "pair_id": "pair-consumer",
                    "case_id": "consumer_a",
                    "paired_delta": {
                        "unique_disclosed_facts_per_question": -0.2,
                        "unique_disclosed_facts": -1.0,
                    },
                    "parent_process": {
                        "trajectory_id": "parent-consumer",
                        "turns": [{"question": "购买后发生了什么？"}],
                    },
                    "current_process": {
                        "trajectory_id": "current-consumer",
                        "turns": [{"question": "商家内部如何审批？"}],
                    },
                },
                {
                    "pair_id": "pair-labor",
                    "case_id": "labor_a",
                    "paired_delta": {
                        "unique_disclosed_facts_per_question": 0.1,
                        "unique_disclosed_facts": 0.5,
                    },
                    "parent_process": {
                        "trajectory_id": "parent-labor",
                        "turns": [{"question": "解除经过是什么？"}],
                    },
                    "current_process": {
                        "trajectory_id": "current-labor",
                        "turns": [{"question": "通知时间和方式是什么？"}],
                    },
                },
            ],
        }
    }

    feedback = prequential_input_library_feedback(
        report,
        primary_endpoint="unique_disclosed_facts_per_question",
        case_domains={
            "consumer_a": "consumer_contract",
            "labor_a": "labor_employment",
        },
    )

    assert feedback["status"] == "primary_endpoint_and_fact_count_regression"
    assert feedback["comparator"] == "exact_parent_library"
    assert feedback["tradeoff_observed"] is True
    assert feedback["signal_family_priority"][0] == "fact_elicitation"
    assert feedback["domain_attribution"]["available"] is True
    assert feedback["domain_diagnostics"]["consumer_contract"]["status"] == (
        "primary_endpoint_and_fact_count_regression"
    )
    assert feedback["domain_diagnostics"]["labor_employment"]["status"] == (
        "primary_endpoint_improvement"
    )
    consumer_process = feedback["domain_diagnostics"]["consumer_contract"][
        "paired_process_evidence"
    ]
    assert [item["case_id"] for item in consumer_process] == ["consumer_a"]
    assert consumer_process[0]["current_process"]["trajectory_id"] == "current-consumer"
    assert consumer_process[0]["current_process"]["turns_source"] == (
        "matching_trajectory_id_in_current_group_evidence_card"
    )
    assert "turns" not in consumer_process[0]["current_process"]
    assert set(consumer_process[0]["paired_delta"]) == {
        "unique_disclosed_facts",
        "unique_disclosed_facts_per_question",
    }
    assert "labor_a" not in str(consumer_process)


def test_document_transition_feedback_exposes_only_exact_changed_fields() -> None:
    parent = synthetic_skills()[2]
    current = parent.model_copy(
        update={
            "version": "1.0.1",
            "procedure": ["确认本轮唯一事件对象", "优先询问客户亲历的履行经过和结果"],
        }
    )

    feedback = add_document_transition_feedback(
        {"domain_diagnostics": {"consumer_contract": {"status": "primary_endpoint_regression"}}},
        current_skills=[current],
        parent_skills=[parent],
        declared_increment_ids={parent.skill_id},
    )

    transition = feedback["document_transitions"]["consumer_contract"]
    assert transition["operation"] == "UPDATE"
    assert transition["skill_id"] == parent.skill_id
    assert transition["parent_version"] == "1.0.0"
    assert transition["current_version"] == "1.0.1"
    assert set(transition["changed_fields"]) == {"procedure"}
    assert transition["changed_fields"]["procedure"]["parent"] == parent.procedure
    assert transition["changed_fields"]["procedure"]["current"] == current.procedure

    with pytest.raises(ExecutionError, match="declared created-or-updated cohort"):
        add_document_transition_feedback(
            {},
            current_skills=[current],
            parent_skills=[parent],
            declared_increment_ids=set(),
        )


def test_prequential_identity_feedback_is_exact_same_current_library() -> None:
    report = {
        "curve": {
            "direction": COHORT_PARENT_EFFECT_DIRECTION,
            "identity_baseline": True,
            "metrics": {
                "unique_disclosed_facts_per_question": {
                    "case_cluster_estimate": {
                        "mean_delta": 0.0,
                        "lower": 0.0,
                        "upper": 0.0,
                    }
                }
            },
        }
    }

    feedback = prequential_input_library_feedback(
        report,
        primary_endpoint="unique_disclosed_facts_per_question",
    )

    assert feedback["status"] == "current_library_identity_no_new_increment"
    assert feedback["comparator"] == "exact_same_current_library"
    assert feedback["feedback_unit"] == "no_new_increment_current_library_identity"


def test_schema3_playbook_teacher_lifecycle_creates_nonfinal_checkpoint_evidence() -> None:
    manifest = {
        "schema_version": 3,
        "status": "complete_group_evidence_playbook_reflection",
        "round": 1,
        "evidence_unit": "complete_k_group_case_card",
        "all_scoreable_cases_represented": True,
        "observed_group_count": 16,
        "scoreable_group_count": 15,
        "attribution_excluded_group_ids": ["excluded_group"],
        "represented_case_ids": [f"case_{index:02d}" for index in range(15)],
        "group_evidence_cards": [{"case_id": f"case_{index:02d}"} for index in range(15)],
        "teacher_update_unit": "one_cross_domain_playbook_exact_local_patch",
        "teacher_packages": [
            {"package_id": "map_01"},
            {"package_id": "map_02"},
            {"package_id": "reduce_01"},
        ],
        "teacher_calls": 3,
        "resumed_teacher_packages": 0,
        "candidate_budget": 1,
        "candidate_outcome_feedback_used": False,
        "candidate_files": ["candidate.yaml"],
        "teacher_proposal_records": [{"candidate_skill_id": "domain.test"}],
        "candidate_count": 1,
        "final_block_generates_skills": False,
    }

    assert _playbook_teacher_evidence_created(manifest, round_index=1, total_rounds=8) is True


def test_schema3_playbook_teacher_lifecycle_does_not_accept_retired_schema2_flag() -> None:
    with pytest.raises(ExecutionError, match="schema-3 playbook teacher lifecycle is invalid"):
        _playbook_teacher_evidence_created(
            {
                "schema_version": 2,
                "round": 1,
                "current_block_enters_cumulative_teacher_evidence": True,
            },
            round_index=1,
            total_rounds=8,
        )


def test_final_zero_budget_skips_contrast_and_teacher_calls(tmp_path: Path) -> None:
    executor = _executor(tmp_path, run_id="final_zero_budget")
    health_path = executor.store.root / "health/pre_scoring_health_training_batch_01.json"
    executor.store.atomic_json(
        health_path,
        {
            "quality_diagnostics": {
                "training_group_attribution_review": {
                    "scoring_eligible": True,
                    "scoreable_group_ids": ["must-not-be-consumed"],
                    "excluded_group_ids": [],
                }
            }
        },
    )
    executor.teacher_client = SimpleNamespace(
        invocation_budget_status=lambda: pytest.fail("teacher client was accessed")
    )

    candidates = executor.propose_candidates(
        round_index=1,
        trajectories=[SimpleNamespace(partition="training_batch_01")],
        evaluations={},
        candidate_budget=0,
    )

    assert candidates == []
    assert not (executor.store.root / "evidence/trajectory_contrasts").exists()
    assert not (executor.store.root / "teacher/round_01").exists()
    manifest = executor.store.read_manifest("teacher_round_01")
    assert manifest["status"] == "skipped_final_block_zero_candidate_budget"
    assert manifest["current_block_enters_cumulative_teacher_evidence"] is False
    assert manifest["teacher_calls"] == 0
    assert manifest["round_trajectory_contrast_patches"] == 0
    assert manifest["candidate_files"] == []
    # The monitor's frozen protocol has eight blocks; transplant this exact
    # writer artifact to B8 to exercise its final-block contract.
    value = executor.store.read_manifest("teacher_round_01")
    value.pop("content_sha256")
    value["round"] = 8
    executor.store.write_manifest("teacher_round_08", value, overwrite=True)
    monitored = _teacher_contract(
        tmp_path,
        executor.run_id,
        8,
        bound_record=None,
    )
    assert monitored["status"] == "diagnostic_unbound"
    assert monitored["issues"] == []


def test_resumed_playbook_map_rejects_parent_playbook_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executor = _executor(tmp_path, run_id="map_parent_drift")
    executor.experiment["data"] = {"training_split": "training"}
    executor.training_plan = SimpleNamespace(
        batches=[
            SimpleNamespace(batch_id="training_batch_01"),
            SimpleNamespace(batch_id="training_batch_02"),
        ]
    )
    current_playbook = synthetic_skills()[0].model_copy(
        update={
            "skill_id": PLAYBOOK_SKILL_ID,
            "version": "1.0.1",
            "domain": "general",
            "status": "active",
            "objective": "fact_elicitation",
        }
    )
    previous_playbook = current_playbook.model_copy(update={"version": "1.0.0"})
    executor.active_skills = lambda: [current_playbook]
    executor.main_adapter = SimpleNamespace(
        case_ids=lambda _split: [],
        case_domain=lambda _case_id: "general",
    )
    executor.teacher_client = SimpleNamespace(
        invocation_budget_status=lambda: {"available": 3},
        invocation_budget_path=None,
        max_invocations=None,
    )
    executor.teacher = SimpleNamespace(
        extract_playbook_modes=lambda **_kwargs: pytest.fail(
            "a parent-drifted persisted map must be rejected before a new map call"
        )
    )

    groups: dict[str, list[SimpleNamespace]] = {}
    trajectories: list[SimpleNamespace] = []
    for group_index in range(2):
        group_id = f"group_{group_index}"
        members = [
            SimpleNamespace(
                trajectory_id=f"{group_id}.trajectory_{sample_index}",
                group_id=group_id,
                case_id=f"case_{group_index}",
                domain="general",
                persona="P_WD",
                partition="training_batch_01",
                method="training_policy_sample",
                skill_library_version="L1",
            )
            for sample_index in range(4)
        ]
        groups[group_id] = members
        trajectories.extend(members)
        for member in members:
            executor.store.atomic_json(
                executor.store.trajectory_path(member.partition, member.trajectory_id),
                {"trajectory_id": member.trajectory_id},
            )
            executor.store.atomic_json(
                executor.store.evaluation_path(member.trajectory_id),
                {"trajectory_id": member.trajectory_id},
            )

    def card_for(group_id: str, members: list[SimpleNamespace]) -> dict[str, object]:
        member = members[0]
        return {
            "schema_version": 4,
            "group_id": group_id,
            "case_id": member.case_id,
            "domain": member.domain,
            "persona": member.persona,
            "skill_library_version": member.skill_library_version,
            "opening_inquiry_agenda": [],
            "group_relative_status": "process_tied",
            "trajectory_summaries": [
                {"visible_target_catalog": [], "turn_outline": []} for _ in members
            ],
            "undisclosed_hidden_facts_included": False,
        }

    monkeypatch.setattr(
        "legal_skill_guard.experiment.executor.tf_grpo_teacher_evidence_groups",
        lambda _trajectories, _scoreable: groups,
    )
    monkeypatch.setattr(
        "legal_skill_guard.experiment.executor.build_group_evidence_card",
        lambda group_id, members, _evaluations: card_for(group_id, members),
    )
    executor.store.atomic_json(
        executor.store.root / "health/pre_scoring_health_training_batch_01.json",
        {
            "quality_diagnostics": {
                "training_group_attribution_review": {
                    "scoring_eligible": True,
                    "scoreable_group_ids": sorted(groups),
                    "excluded_group_ids": [],
                }
            }
        },
    )
    executor.store.atomic_json(
        executor._learning_curve_point_path(1),
        {
            "input_active_skill_ids": [PLAYBOOK_SKILL_ID],
            "input_skill_library_sha256": skill_library_sha256([current_playbook]),
            "identity_baseline": True,
            "new_skill_increment_ids": [],
            "curve": {
                "direction": COHORT_PARENT_EFFECT_DIRECTION,
                "identity_baseline": True,
                "metrics": {
                    "unique_disclosed_facts_per_question": {
                        "case_cluster_estimate": {
                            "mean_delta": 0.0,
                            "lower": 0.0,
                            "upper": 0.0,
                        }
                    }
                },
                "cases": [],
            },
        },
    )

    first_card = card_for("group_0", groups["group_0"])
    package_id = "training_batch_01.playbook_map_01"
    persisted = PlaybookModeArtifact(
        package_id=package_id,
        input_binding_sha256=playbook_map_input_binding_sha256(
            package_id=package_id,
            evidence_cards=[first_card],
            current_playbook=previous_playbook,
        ),
        request_sha256="a" * 64,
        response_sha256="b" * 64,
        teacher_model="gpt-test",
        source_group_ids=["group_0"],
        modes=[],
        no_new_mode_group_ids=["group_0"],
    )
    executor.store.save_model(
        executor.store.root
        / "teacher/round_01/training_batch_01.playbook_map_01.json",
        persisted,
    )

    with pytest.raises(ExecutionError, match="persisted playbook teacher stage is not bound"):
        executor.propose_candidates(
            round_index=1,
            trajectories=trajectories,  # type: ignore[arg-type]
            evaluations={},
        )


def test_legacy_contrast_only_teacher_manifest_is_rejected(
    tmp_path: Path,
) -> None:
    executor = _executor(tmp_path, run_id="teacher_scope_schema2")
    executor.store.write_manifest(
        "teacher_round_01",
        {
            "schema_version": 2,
            "status": "teacher_evidence_processed",
            "round": 1,
            "current_block_enters_cumulative_teacher_evidence": True,
            "end_to_end_reward_informative_groups": 2,
            "trajectory_contrast_groups": 2,
            "groups_without_trajectory_contrast_reasons": {},
            "selected_groups": 2,
            "teacher_update_unit": (
                "distinct_cluster_syntheses_from_cumulative_trajectory_contrasts"
            ),
            "evidence_lifecycle": ("trajectory_contrast_to_source_grounded_direct_working_library"),
            "round_trajectory_contrast_patches": 2,
            "created_trajectory_contrast_patches_this_invocation": 2,
            "new_trajectory_contrast_patches": 2,
            "cumulative_trajectory_contrast_patches": 2,
            "teacher_evidence_clusters": [
                {"cluster_id": "learnable"},
                {"cluster_id": "stop"},
            ],
            "source_eligible_teacher_evidence_clusters": 2,
            "eligible_teacher_evidence_clusters": 2,
            "teacher_scope_eligibility": {
                "schema_version": 2,
                "decision_timing": "after_source_grounding_before_teacher_synthesis",
                "uses_reward_or_semantic_outcome": False,
                "uses_next_block_case_mix": False,
                "learnable_objectives": [
                    "fact_elicitation",
                    "evidence_gap_identification",
                    "safe_stop",
                ],
                "termination_policy_owner": "frozen_lawyer_with_prompt_skill_memory",
                "source_eligible_cluster_count": 2,
                "teacher_eligible_cluster_count": 2,
                "teacher_eligible_cluster_ids": ["learnable", "stop"],
                "objective_excluded_cluster_count": 0,
                "objective_excluded_cluster_ids": [],
                "objective_exclusion_reason": "signal_family_outside_formal_objectives",
            },
            "previously_attempted_eligible_cluster_ids": [],
            "completed_eligible_cluster_ids_skipped": [],
            "unchanged_support_milestones_skipped": [],
            "support_milestone_reconsidered_cluster_ids": [],
            "planned_evidence_cluster_ids": [],
            "attempted_evidence_cluster_ids": [],
            "attempted_evidence_fingerprints": [],
            "teacher_call_budget": 6,
            "configured_teacher_call_budget": 6,
            "available_new_candidate_slots": 3,
            "teacher_calls": 0,
            "resumed_teacher_proposals": 0,
            "candidate_outcome_feedback_used": False,
            "teacher_proposal_records": [],
            "candidate_files": [],
        },
    )

    monitored = _teacher_contract(
        tmp_path,
        executor.run_id,
        1,
        bound_record=None,
    )

    assert monitored["status"] == "invalid"
    assert "teacher_binding_invalid" in monitored["issues"]


def test_teacher_contract_accepts_pre_reward_complete_group_quarantine(
    tmp_path: Path,
) -> None:
    executor = _executor(tmp_path, run_id="teacher_group_quarantine")
    scoreable_cases = [f"case_{index:02d}" for index in range(15)]
    scoreable_groups = [f"group_{index:02d}" for index in range(15)]
    excluded_group = "training_batch_01.case_15.P_WD.seed_42"
    executor.store.write_manifest(
        "teacher_round_01",
        {
            "schema_version": 3,
            "status": "complete_group_evidence_playbook_reflection",
            "round": 1,
            "evidence_unit": "complete_k_group_case_card",
            "all_scoreable_cases_represented": True,
            "observed_group_count": 16,
            "scoreable_group_count": 15,
            "attribution_excluded_group_ids": [excluded_group],
            "attribution_exclusion_reason_counts": {"policy_fallback_used": 1},
            "represented_case_ids": scoreable_cases,
            "attribution_excluded_case_ids": ["case_15"],
            "group_evidence_cards": [
                {
                    "case_id": case_id,
                    "group_id": group_id,
                    "relative_status": "process_differentiated",
                }
                for case_id, group_id in zip(scoreable_cases, scoreable_groups, strict=True)
            ],
            "teacher_packages": [
                {
                    "package_id": "map_01",
                    "stage": "map",
                    "source_group_ids": scoreable_groups[::2],
                },
                {
                    "package_id": "map_02",
                    "stage": "map",
                    "source_group_ids": scoreable_groups[1::2],
                },
                {
                    "package_id": "reduce_01",
                    "stage": "reduce",
                    "source_group_ids": scoreable_groups,
                },
            ],
            "teacher_calls": 3,
            "resumed_teacher_packages": 0,
            "candidate_outcome_feedback_used": False,
            "teacher_proposal_records": [],
            "candidate_files": [],
            "final_block_generates_skills": False,
        },
    )

    monitored = _teacher_contract(
        tmp_path,
        executor.run_id,
        1,
        bound_record=None,
    )

    assert monitored["status"] == "diagnostic_unbound"
    assert monitored["issues"] == []
    assert monitored["new_contrast_patch_count"] == 15
    assert monitored["teacher_scope_eligibility"] == {
        "all_scoreable_cases_represented": True,
        "observed_group_count": 16,
        "scoreable_group_count": 15,
        "attribution_excluded_group_ids": [excluded_group],
        "attribution_excluded_case_ids": ["case_15"],
        "attribution_exclusion_reason_counts": {"policy_fallback_used": 1},
    }


def test_curve_summary_schema3_uses_exact_same_identity_not_fixed_empty(
    tmp_path: Path,
) -> None:
    executor = _executor(tmp_path, run_id="curve_summary_schema2")
    empty_hash = skill_library_sha256([])
    metric = {
        "current_library_mean": 0.5,
        "parent_library_mean": 0.5,
        "case_cluster_estimate": {
            "mean_delta": 0.0,
            "lower": 0.0,
            "upper": 0.0,
        },
    }
    point_path = executor._learning_curve_point_path(1)
    point = {
        "schema_version": 3,
        "input_active_skill_ids": [],
        "input_skill_library_sha256": empty_hash,
        "parent_active_skill_ids": [],
        "parent_skill_library_version": "bootstrap_empty",
        "parent_skill_library_sha256": empty_hash,
        "new_skill_increment_ids": [],
        "identity_baseline": True,
        "curve": {
            "identity_baseline": True,
            "pair_count": 1,
            "case_cluster_count": 1,
            "metrics": {name: deepcopy(metric) for name in CURVE_METRICS},
        },
    }
    executor.store.atomic_json(point_path, point)
    disposition_path = executor._library_effect_disposition_path(1)
    executor.store.atomic_json(disposition_path, {"decision": "continue_training"})
    checkpoint = {
        "schema_version": 5,
        "batch_id": "training_batch_01",
        "development_curve_artifact": executor._relative_artifact_record(point_path),
        "active_skill_ids": [],
        "active_skill_library_sha256": empty_hash,
        "admitted_from_current_block": [],
        "teacher_evidence_created": False,
    }
    executor.store.atomic_json(
        executor.store.root / "reports/learning_checkpoint_01.json",
        checkpoint,
    )

    summary = executor.write_development_learning_curve_summary()

    assert summary["schema_version"] == 3
    assert summary["direction"] == (
        "current_library_minus_exact_parent_or_same_current_library_by_point"
    )
    assert summary["points"][0]["comparator"] == "exact_same_current_library"
    assert summary["points"][0]["current_block_teacher_evidence_created"] is False
    assert "fixed_empty" not in repr(summary)
    completion = {
        "status": "verified",
        "input_active_skill_ids": [],
        "input_skill_library_sha256": empty_hash,
        "output_active_skill_ids": [],
        "output_skill_library_sha256": empty_hash,
        "admitted_skill_ids": [],
        "rejected_new_skill_increment_ids": [],
        "development_curve": {
            "comparator": "exact_same_current_library",
            "identity_baseline": True,
            "parent_active_skill_ids": [],
            "parent_skill_library_version": "bootstrap_empty",
            "parent_skill_library_sha256": empty_hash,
            "new_skill_increment_ids": [],
            "pair_count": 1,
            "case_cluster_count": 1,
            "metrics": point["curve"]["metrics"],
            "artifact": executor._relative_artifact_record(point_path),
        },
        "learning_checkpoint": {"teacher_evidence_created": False},
    }
    monitored = _curve_summary_contract(
        tmp_path,
        executor.run_id,
        [{"batch_id": "training_batch_01"}],
        {"training_batch_01": completion},
        executor.experiment["learning_curve"]["evidence_role"],
    )
    assert monitored["status"] == "verified"
    assert monitored["issues"] == []


def _incremental_effect_diagnostic_config() -> dict[str, object]:
    endpoint_rules = {
        name: {"direction": direction, "margin": 0.0}
        for name, direction in COHORT_GATE_ENDPOINT_DIRECTIONS.items()
    }
    return {
        "status": "frozen_before_next_formal_run",
        "timing": "next_unseen_training_block_before_teacher",
        "comparator": "exact_parent_library",
        "decision_role": "descriptive_increment_measurement_before_teacher_never_skill_veto",
        "single_block_effect_can_prune_or_rollback": False,
        "interval_uncertainty_alone_blocks_accumulation": False,
        "final_block_new_skill_budget": 0,
        "minimum_exposed_cases_for_interpretation": 1,
        "global_playbook_requires_full_cohort_exposure": True,
        "primary_signal": {
            "decision_rule": "primary_positive_point_estimate",
            "endpoints": ["unique_disclosed_facts_per_question"],
            "threshold": 0.0,
        },
        "practical_effect_classifier": _expected_practical_retention_gate(
            COHORT_PARENT_EFFECT_DIRECTION
        ),
        "interval_diagnostic": {
            "schema_version": 1,
            "decision_rule": "case_cluster_pareto_noninferiority",
            "effect_direction": COHORT_PARENT_EFFECT_DIRECTION,
            "primary_endpoint": "unique_disclosed_facts_per_question",
            "protected_endpoints": [
                name
                for name in COHORT_GATE_ENDPOINT_DIRECTIONS
                if name != "unique_disclosed_facts_per_question"
            ],
            "endpoint_rules": endpoint_rules,
        },
    }


def _final_holdout_report(
    endpoint_means: dict[str, float] | None = None,
) -> dict[str, object]:
    means = {name: 0.0 for name in COHORT_GATE_ENDPOINT_DIRECTIONS}
    means.update(endpoint_means or {})
    return {
        "scope": "same_B8_accumulated_library_diagnostic",
        "selected_active_skill_ids": ["general.final"],
        "curve": {
            "direction": "current_library_minus_empty_library",
            "identity_baseline": False,
            "bootstrap": {"unit": "case_id"},
            "metrics": {
                name: {"case_cluster_estimate": {"mean_delta": mean}}
                for name, mean in means.items()
            },
        },
    }


def test_final_training_diagnostic_reports_advancement_without_pruning() -> None:
    disposition = final_training_holdout_safeguard_disposition(
        _final_holdout_report({"unique_disclosed_facts_per_question": 0.01}),
        {"passed": True},
        gate_config=_expected_final_training_holdout_config(),
    )

    assert disposition["decision"] == "allow_accumulated_library_freeze_and_external"
    assert disposition["training_freeze_allowed"] is True
    assert disposition["retention_gate_passed"] is True
    assert disposition["advancement"]["passed"] is True
    assert disposition["automatic_skill_pruning"] is False
    assert disposition["claim_role"] == (
        "cumulative_library_diagnostic_not_independent_confirmatory_claim"
    )


def test_final_training_diagnostic_reports_regression_without_blocking_external() -> None:
    disposition = final_training_holdout_safeguard_disposition(
        _final_holdout_report(
            {
                "unique_disclosed_facts_per_question": -0.025,
                "reward": -0.007292,
                "question_turns": 0.3125,
            }
        ),
        {"passed": True},
        gate_config=_expected_final_training_holdout_config(),
    )

    assert disposition["decision"] == "allow_accumulated_library_freeze_and_external"
    assert disposition["training_freeze_allowed"] is True
    assert disposition["external_test_allowed"] is True
    assert disposition["performance_panel_passed"] is False
    assert disposition["retention_gate"]["primary_passed"] is False
    assert disposition["retention_gate"]["protected_regressions"] == []
    assert disposition["failure_reasons"] == [
        "primary_or_protected_endpoint_nonpass",
    ]


def test_final_training_holdout_fails_closed_on_isolation_failure() -> None:
    disposition = final_training_holdout_safeguard_disposition(
        _final_holdout_report({"unique_disclosed_facts_per_question": 0.01}),
        {"passed": False},
        gate_config=_expected_final_training_holdout_config(),
    )

    assert disposition["training_freeze_allowed"] is False
    assert disposition["failure_reasons"] == ["intervention_isolation_failed"]
    assert disposition["teacher_call_allowed_after_nonpass"] is False


def test_B8_arm_freeze_refuses_to_follow_an_existing_cohort_disposition(
    tmp_path: Path,
) -> None:
    executor = _executor(tmp_path, run_id="late_final_arm_freeze")
    skill = synthetic_skills()[0]
    current = SimpleNamespace(trajectory_id="current")
    empty = SimpleNamespace(trajectory_id="empty")
    executor._relative_artifact_record = lambda path: {
        "path": str(path),
        "sha256": "a" * 64,
    }
    executor.store.atomic_json(
        executor._library_effect_disposition_path(1),
        {"decision": "continue_training"},
    )

    with pytest.raises(ExecutionError, match="predates the mandatory all-arm freeze"):
        executor._freeze_final_training_holdout_arms(
            round_index=1,
            case_limit=None,
            run_manifest_sha256="b" * 64,
            input_version="library_current",
            input_skills=[skill],
            current=[current],  # type: ignore[list-item]
            current_evaluations={"current": object()},  # type: ignore[dict-item]
            empty=[empty],  # type: ignore[list-item]
            empty_evaluations={"empty": object()},  # type: ignore[dict-item]
            parent_context=None,
            parent=None,
            parent_evaluations=None,
        )

    assert not executor._final_training_holdout_arms_path().exists()


def _parent_cohort_point(
    executor: MainExperimentExecutor,
    *,
    endpoint_means: dict[str, float] | None = None,
    exposure_case_count: int = 2,
    exposure_pair_count: int = 2,
) -> tuple[dict[str, object], list[object], str]:
    executor.experiment["learning_curve"]["incremental_effect_diagnostic"] = (
        _incremental_effect_diagnostic_config()
    )
    parent_skill, _, _, cohort_skill, _ = synthetic_skills()
    input_skills = [parent_skill, cohort_skill]
    input_ids = sorted(skill.skill_id for skill in input_skills)
    parent_ids = [parent_skill.skill_id]
    input_hash = skill_library_sha256(input_skills)
    parent_hash = skill_library_sha256([parent_skill])
    run_hash = "c" * 64
    means = {name: 0.0 for name in COHORT_GATE_ENDPOINT_DIRECTIONS}
    means.update(endpoint_means or {})

    metrics: dict[str, object] = {}
    for name, mean in means.items():
        metrics[name] = {
            "case_cluster_estimate": {
                "pairs": 2,
                "mean_delta": mean,
                "median_delta": mean,
                # Deliberately cross zero: interval uncertainty is diagnostic,
                # while the frozen retention decision uses observed directions.
                "lower": mean - 0.1,
                "upper": mean + 0.1,
                "confidence_level": 0.95,
                "bootstrap_samples": 100,
                "seed": 17,
            }
        }
    isolation_path = (
        executor.store.root / "health/parent_cohort_intervention_isolation_training_batch_01.json"
    )
    executor.store.atomic_json(
        isolation_path,
        {
            "schema_version": 1,
            "passed": True,
            "cohort_exposed_case_count": exposure_case_count,
            "cohort_exposed_pair_count": exposure_pair_count,
            "cohort_skill_exposure": {
                cohort_skill.skill_id: {
                    "domain": "general",
                    "expected_case_count": 2,
                    "expected_pair_count": 2,
                    "observed_case_count": exposure_case_count,
                    "observed_pair_count": exposure_pair_count,
                    "routing_complete": (exposure_case_count == 2 and exposure_pair_count == 2),
                }
            },
        },
    )
    point: dict[str, object] = {
        "schema_version": 2,
        "run_id": executor.run_id,
        "run_manifest_sha256": run_hash,
        "round": 1,
        "batch_id": "training_batch_01",
        "source_round": 0,
        "input_active_skill_ids": input_ids,
        "input_skill_library_version": "accumulated_v1",
        "input_skill_library_sha256": input_hash,
        "parent_active_skill_ids": parent_ids,
        "parent_skill_library_version": "parent_v0",
        "parent_skill_library_sha256": parent_hash,
        "new_skill_increment_ids": [cohort_skill.skill_id],
        "intervention_isolation_artifact": executor._relative_artifact_record(isolation_path),
        "curve": {
            "direction": COHORT_PARENT_EFFECT_DIRECTION,
            "identity_baseline": False,
            "pair_count": 2,
            "case_cluster_count": 2,
            "bootstrap": {
                "unit": "case_id",
                "samples": 100,
                "confidence_level": 0.95,
                "seed": 17,
            },
            "metrics": metrics,
            "cases": [
                {"case_id": "case_a", "pair_count": 1},
                {"case_id": "case_b", "pair_count": 1},
            ],
            "pairs": [
                {"pair_id": "pair_a", "case_id": "case_a"},
                {"pair_id": "pair_b", "case_id": "case_b"},
            ],
        },
    }
    executor.store.atomic_json(executor._learning_curve_point_path(1), point)
    return point, input_skills, run_hash


def _parent_cohort_disposition(
    executor: MainExperimentExecutor,
    *,
    endpoint_means: dict[str, float] | None = None,
    exposure_case_count: int = 2,
    exposure_pair_count: int = 2,
) -> dict[str, object]:
    point, input_skills, run_hash = _parent_cohort_point(
        executor,
        endpoint_means=endpoint_means,
        exposure_case_count=exposure_case_count,
        exposure_pair_count=exposure_pair_count,
    )
    return executor._expected_library_effect_disposition(
        round_index=1,
        run_manifest_sha256=run_hash,
        input_version="accumulated_v1",
        input_skills=input_skills,  # type: ignore[arg-type]
        curve_point=point,
    )


def test_parent_cohort_gate_retains_nonregressing_advancement_despite_wide_ci(
    tmp_path: Path,
) -> None:
    executor = _executor(tmp_path, run_id="cohort_observed_pass")

    disposition = _parent_cohort_disposition(
        executor,
        endpoint_means={"unique_disclosed_facts_per_question": 0.01},
    )

    assert disposition["decision"] == "observe_increment_continue_training"
    assert disposition["cohort_transition"] == "retain_increment_for_cross_block_evolution"
    assert disposition["diagnostic_flags"] == []
    assert disposition["interval_diagnostic"]["decision"] == "inconclusive"
    assert disposition["practical_effect_classifier"]["passed"] is True
    assert disposition["practical_effect_classifier"]["uncertainty_alone_blocks_retention"] is False


def test_parent_cohort_gate_reports_diagnostic_endpoint_without_veto(
    tmp_path: Path,
) -> None:
    executor = _executor(tmp_path, run_id="cohort_observed_regression")

    disposition = _parent_cohort_disposition(
        executor,
        endpoint_means={
            "unique_disclosed_facts_per_question": 0.01,
            "fidelity": -0.001,
        },
    )

    assert disposition["decision"] == "observe_increment_continue_training"
    assert disposition["cohort_transition"] == "retain_increment_for_cross_block_evolution"
    assert disposition["diagnostic_flags"] == []
    assert disposition["interval_diagnostic"]["decision"] == "inconclusive"
    fidelity = disposition["practical_effect_classifier"]["endpoint_dispositions"]["fidelity"]
    assert fidelity["role"] == "diagnostic"
    assert fidelity["passed"] is None


def test_parent_cohort_gate_retains_primary_gain_with_practical_safety(
    tmp_path: Path,
) -> None:
    executor = _executor(tmp_path, run_id="cohort_B5_counterfactual")

    disposition = _parent_cohort_disposition(
        executor,
        endpoint_means={
            "unique_disclosed_facts_per_question": 0.055556,
            "unique_disclosed_facts": 0.0,
            "identified_evidence_gaps": -0.0625,
            "resolution": -0.035714,
            "elicitation": -0.065923,
            "fidelity": -0.03125,
            "critical_fact_recall": 0.0,
            "reward": -0.006051,
            "question_turns": -0.875,
            "premature_final_rate": 0.0,
            "unsupported_claim_rate": 0.03125,
            "belief_as_fact_rate": 0.0,
            "hidden_field_leak": 0.0,
            "repeated_question_rate": -0.107639,
            "policy_fallback_rate": 0.0,
            "client_fallback_rate": 0.0,
        },
    )

    assert disposition["decision"] == "observe_increment_continue_training"
    assert disposition["cohort_transition"] == "retain_increment_for_cross_block_evolution"
    gate = disposition["practical_effect_classifier"]
    assert gate["passed"] is True
    assert gate["protected_regressions"] == []
    assert gate["endpoint_dispositions"]["fidelity"]["role"] == "diagnostic"


def test_increment_diagnostic_reports_material_protected_safety_regression(
    tmp_path: Path,
) -> None:
    executor = _executor(tmp_path, run_id="cohort_material_safety_regression")

    disposition = _parent_cohort_disposition(
        executor,
        endpoint_means={
            "unique_disclosed_facts_per_question": 0.02,
            "unsupported_claim_rate": 0.06,
        },
    )

    assert disposition["decision"] == "observe_increment_continue_training"
    assert disposition["cohort_transition"] == "retain_increment_for_cross_block_evolution"
    assert disposition["performance_panel_passed"] is False
    gate = disposition["practical_effect_classifier"]
    assert gate["passed"] is False
    assert gate["protected_regressions"] == ["unsupported_claim_rate"]
    assert gate["endpoint_dispositions"]["unsupported_claim_rate"]["passed"] is False


def test_increment_diagnostic_reports_insufficient_exposure_without_rollback(
    tmp_path: Path,
) -> None:
    executor = _executor(tmp_path, run_id="cohort_low_exposure")

    disposition = _parent_cohort_disposition(
        executor,
        endpoint_means={"unique_disclosed_facts_per_question": 0.01},
        exposure_case_count=0,
        exposure_pair_count=0,
    )

    assert disposition["decision"] == "observe_increment_continue_training"
    assert disposition["cohort_transition"] == "retain_increment_for_cross_block_evolution"
    assert disposition["performance_panel_passed"] is False
    assert disposition["diagnostic_flags"] == ["insufficient_exposure"]
    failures = disposition["diagnostic_checks"]["global_playbook_exposure_failures"]
    assert failures == [
        "fewer_than_minimum_pairs",
        "fewer_than_minimum_unique_cases",
        "incomplete_global_playbook_cohort_exposure",
    ]


def test_increment_diagnostic_reports_no_primary_signal_without_rollback(
    tmp_path: Path,
) -> None:
    executor = _executor(tmp_path, run_id="cohort_no_advancement")

    disposition = _parent_cohort_disposition(executor)

    assert disposition["decision"] == "observe_increment_continue_training"
    assert disposition["cohort_transition"] == "retain_increment_for_cross_block_evolution"
    assert disposition["performance_panel_passed"] is False
    assert disposition["diagnostic_flags"] == ["primary_or_protected_endpoint_nonpass"]
    assert disposition["practical_effect_classifier"]["passed"] is False
    assert disposition["diagnostic_checks"]["exposure_passed"] is True


def test_library_disposition_rejects_argument_that_differs_from_bound_curve_file(
    tmp_path: Path,
) -> None:
    executor = _executor(tmp_path, run_id="curve_argument_drift")
    persisted, input_skills, run_hash = _parent_cohort_point(executor)
    argument = deepcopy(persisted)
    argument["curve"]["metrics"]["unique_disclosed_facts_per_question"]["case_cluster_estimate"][
        "mean_delta"
    ] = 0.08

    with pytest.raises(ExecutionError, match="argument differs from persisted artifact"):
        executor.write_library_effect_disposition(
            round_index=1,
            run_manifest_sha256=run_hash,
            input_version="accumulated_v1",
            input_skills=input_skills,
            curve_point=argument,
        )

    assert not executor._library_effect_disposition_path(1).exists()
    assert not (executor.store.root / "manifests/training_halted.json").exists()


def _persist_empty_library_training_cell(
    executor: MainExperimentExecutor,
) -> tuple[ResearchTrajectory, dict[str, SimpleNamespace]]:
    empty_hash = skill_library_sha256([])
    expected = executor._training_round_expected_matrix(
        1,
        case_limit=None,
        input_skill_library_sha256=empty_hash,
        input_skills=[],
    )[0]
    trajectory = ResearchTrajectory.model_validate(
        {
            **expected,
            "domain": "civil",
            "jurisdiction": "CN",
            "status": "memo_submitted",
            "opening": "测试开场。",
            "max_turns": 6,
            "steps": [],
            "memo": "测试备忘录。",
            "elapsed_seconds": 1.0,
            "created_at": "2026-09-07T00:00:00+00:00",
        }
    )
    executor.store.save_model(
        executor.store.trajectory_path(trajectory.partition, trajectory.trajectory_id),
        trajectory,
    )
    executor.store.atomic_json(
        executor.store.evaluation_path(trajectory.trajectory_id),
        {
            "schema_version": 13,
            "trajectory_id": trajectory.trajectory_id,
            "case_id": trajectory.case_id,
            "judge_qualification_contract_sha256": "a" * 64,
        },
    )
    evaluation = _trajectory_evaluation(trajectory)
    original_load_model = executor.store.load_model

    def load_model(path: Path, model: type[object]) -> object:
        if path == executor.store.evaluation_path(trajectory.trajectory_id):
            return evaluation
        return original_load_model(path, model)

    # The test isolates executor binding semantics; the in-memory evaluation has
    # the complete metric interface while the on-disk bytes remain a real hashed
    # artifact for drift checks.
    executor.store.load_model = load_model  # type: ignore[method-assign]
    return trajectory, {trajectory.trajectory_id: evaluation}


def _prepare_identity_point(
    executor: MainExperimentExecutor,
) -> tuple[ResearchTrajectory, dict[str, object], str]:
    executor.store.write_manifest("run", {"schema_version": 2, "run_id": executor.run_id})
    run_hash = sha256_file(executor.store.root / "manifests/run.json")
    trajectory, evaluations = _persist_empty_library_training_cell(executor)
    point = executor.prepare_development_curve_point(
        round_index=1,
        case_limit=None,
        run_manifest_sha256=run_hash,
        input_skills=[],
        trajectories=[trajectory],
        evaluations=evaluations,
    )
    return trajectory, point, run_hash


def test_empty_library_curve_is_identity_bound_without_shadow_rollout(
    tmp_path: Path,
) -> None:
    executor = _executor(tmp_path)
    executor.generate_learning_curve_shadow = lambda **_: pytest.fail(
        "an empty input library must not spend a duplicate shadow rollout"
    )

    trajectory, point, run_hash = _prepare_identity_point(executor)

    assert point["run_manifest_sha256"] == run_hash
    assert point["identity_baseline"] is True
    assert point["schema_version"] == 3
    assert point["input_active_skill_ids"] == []
    assert point["input_skill_library_sha256"] == skill_library_sha256([])
    assert point["parent_active_skill_ids"] == []
    assert point["parent_skill_library_version"] == "bootstrap_empty"
    assert point["parent_skill_library_sha256"] == skill_library_sha256([])
    assert point["parent_trajectory_artifacts"] == {}
    assert point["parent_evaluation_artifacts"] == {}
    assert point["intervention_isolation_artifact"] is None
    assert point["curve"]["partition_mapping"] == {
        "current": "training_batch_01",
        "parent": "training_batch_01",
    }
    pair = point["curve"]["pairs"][0]
    assert pair["current_trajectory_id"] == trajectory.trajectory_id
    assert pair["parent_trajectory_id"] == trajectory.trajectory_id
    assert all(value == 0 for value in pair["paired_delta"].values())
    shadow_root = executor.store.root / "trajectories/learning_curve_shadow_training_batch_01"
    assert not shadow_root.exists()


def _nonempty_curve_executor(tmp_path: Path) -> tuple[MainExperimentExecutor, object, object]:
    executor = _executor(tmp_path, run_id="nonempty_curve")
    skill = synthetic_skills()[0]
    current = SimpleNamespace(trajectory_id="current")
    executor._learning_curve_current_trajectories = lambda **_: [current]
    return executor, skill, current


def test_nonempty_curve_without_pending_cohort_uses_retained_identity_without_shadow(
    tmp_path: Path,
) -> None:
    executor, skill, current = _nonempty_curve_executor(tmp_path)
    calls: list[dict[str, object]] = []
    executor._previous_block_skill_increment = lambda **_: None
    executor.generate_learning_curve_shadow = lambda **_: pytest.fail(
        "a retained-library identity point must not spend an empty shadow rollout"
    )
    executor._prepare_current_library_identity_curve_point = lambda **kwargs: (
        calls.append(kwargs) or {"kind": "retained_identity"}
    )

    result = executor.prepare_development_curve_point(
        round_index=1,
        case_limit=None,
        run_manifest_sha256="b" * 64,
        input_skills=[skill],
        trajectories=[current],
        evaluations={"current": object()},
    )

    assert result == {"kind": "retained_identity"}
    assert len(calls) == 1
    assert calls[0]["input_skills"] == [skill]
    assert calls[0]["current"] == [current]


def test_learning_checkpoint_rejects_curve_input_library_binding_drift(
    tmp_path: Path,
) -> None:
    executor = _executor(tmp_path, run_id="curve_input_drift")
    _, _, run_hash = _prepare_identity_point(executor)
    curve_path = executor._learning_curve_point_path(1)

    with pytest.raises(ExecutionError, match="binding mismatch"):
        executor.write_learning_checkpoint(
            round_index=1,
            case_limit=None,
            run_manifest_sha256=run_hash,
            admitted_skill_ids=[],
            input_skills=[synthetic_skills()[0]],
            development_curve_artifact=executor._relative_artifact_record(curve_path),
        )
