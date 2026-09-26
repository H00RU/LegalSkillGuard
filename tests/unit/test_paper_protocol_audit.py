from pathlib import Path

from scripts.audit_paper_protocol import (
    ACTIVE_CODE_PATHS,
    ACTIVE_CONFIG_PATHS,
    ACTIVE_DOCUMENT_PATHS,
    ROOT,
    _class_method_sources,
    build_report,
    legacy_python_issues,
    legacy_text_issues,
    legacy_yaml_issues,
)


def test_document_scanner_allows_only_explicit_retirement_statements() -> None:
    retired = """
旧 prospective 协议已经退役。
不再设置 provisional 状态，也不做逐候选配对验收。
不以小样本逐候选验收阻断技能积累。
"""
    active = """
候选进入 provisional 状态。
下一未见块承担逐候选配对验收。
K=4 包含 candidate_with 和 candidate_without。
"""
    current_joint_cohort = """
通过硬门的候选共同形成 provisional cohort，并在下一未见块与精确父库联合比较。
文件中的 new_skill_increment_ids 绑定联合干预，不是逐候选暂存状态。
"""

    assert not legacy_text_issues(
        Path("README.md"),
        retired,
        allow_explicit_retirement=True,
    )
    assert not legacy_text_issues(
        Path("README.md"),
        current_joint_cohort,
        allow_explicit_retirement=True,
    )
    issues = legacy_text_issues(
        Path("README.md"),
        active,
        allow_explicit_retirement=True,
    )
    assert {item.rsplit(":", 1)[-1] for item in issues} >= {
        "provisional",
        "next_unseen_candidate_gate",
        "candidate_with",
        "candidate_without",
    }


def test_python_scanner_ignores_comments_and_provenance_but_rejects_old_code() -> None:
    clean = """
# The provisional lifecycle is retired.
provenance = "tf_grpo"
new_skill_increment_ids = ["skill_current"]
mode = "training_policy_sample"
"""
    stale = """
def validate_provisional_candidate():
    return {"method": "candidate_with", "prospective_audits": []}
"""

    assert not legacy_python_issues(Path("clean.py"), clean)
    issues = legacy_python_issues(Path("stale.py"), stale)
    assert any("legacy_symbol:validate_provisional_candidate" in item for item in issues)
    assert any(item.endswith(":candidate_with") for item in issues)
    assert any(item.endswith(":prospective") for item in issues)


def test_yaml_scanner_rejects_old_keys_and_active_next_block_gate() -> None:
    value = {
        "prospective_validation": {"mode": "embedded_next_block"},
        "rationale": "来源证据不能替代下一未见块的逐候选配对验收。",
        "preparation_note": "不做逐候选效果验收。",
    }

    issues = legacy_yaml_issues(Path("config.yaml"), value)
    assert any("prospective_key" in item for item in issues)
    assert any("next_unseen_candidate_gate" in item for item in issues)
    assert not any("preparation_note" in item for item in issues)


def test_class_method_extractor_exposes_duplicate_runtime_definitions() -> None:
    source = """
class MainExperimentExecutor:
    def train(self):
        return "old"

    def train(self):
        return "new"
"""

    methods = _class_method_sources(source, "MainExperimentExecutor", "train")
    assert len(methods) == 2
    assert 'return "old"' in methods[0]
    assert 'return "new"' in methods[1]


def test_active_truth_set_covers_current_protocol_components_only() -> None:
    assert {
        "legal_skill_guard/agent/stateful_policy.py",
        "legal_skill_guard/experiment/intervention_isolation.py",
        "legal_skill_guard/experiment/learning_curve.py",
        "legal_skill_guard/experiment/official_baselines.py",
        "scripts/run_official_baselines.py",
    } <= set(ACTIVE_CODE_PATHS)
    assert "configs/experiments/official_baselines.yaml" in ACTIVE_CONFIG_PATHS
    assert "docs/architecture/artifact_naming.md" in ACTIVE_DOCUMENT_PATHS
    assert "reports/main_experiment_current_status.md" not in ACTIVE_DOCUMENT_PATHS


def test_repository_report_describes_the_current_direct_accumulation_design() -> None:
    report = build_report(ROOT)

    assert report["schema_version"] == 6
    assert report["status"] == "static_current_protocol_passed_gpu_requalification_required"
    assert not report["failed_checks"]
    assert all(report["checks"].values())
    assert not any(
        issues
        for label, issues in report["legacy_semantic_issues"].items()
        if label != "excluded_history"
    )
    assert report["design"] == {
        **report["design"],
        "training_cases": 128,
        "training_blocks": 8,
        "cases_per_block": [16] * 8,
        "training_persona": "P_WD",
        "trajectories_per_case": 4,
        "base_training_trajectories": 512,
        "teacher_calls_per_block": 3,
        "maximum_teacher_calls": 21,
        "maximum_new_skills": 7,
        "per_candidate_validation_sessions": 0,
        "prequential_shadow_sessions_upper_bound": 128,
        "final_holdout_empty_shadow_sessions": 16,
        "maintenance_blocks": [2, 4, 6, 8],
        "final_block_generates_skills": False,
        "external_cases": 30,
        "external_personas": 4,
        "training_run_diagnostic_arms": ["control_no_library", "legal_skill_evolve"],
        "external_arms": [
            "control_no_library",
            "luna_direct",
            "expel_adapted",
            "legal_skill_evolve",
        ],
    }
    assert "maximum_provisional_candidates" not in report["design"]
    assert "embedded_candidate_evaluation_blocks" not in report["design"]
    assert {
            "k4_uses_predeclared_four_way_exact_visible_input_forks",
            "teacher_map_reduce_covers_all_case_cards",
            "teacher_preserves_group_relative_signal_without_dropping_ties",
            "teacher_source_scope_is_not_filtered_by_next_block_case_mix",
            "one_versioned_global_playbook_with_exact_local_edits",
        "five_hard_trust_gates_directly_admit_working_documents",
        "first_seven_blocks_generate_and_final_block_only_observes",
        "exact_parent_increment_is_diagnostic_and_every_block_keeps_learning",
            "teacher_receives_global_exact_parent_feedback_without_outcome_gate",
        "final_B8_reports_performance_and_fails_closed_only_on_isolation",
        "maintenance_is_whole_library_every_two_blocks",
        "training_run_external_is_two_arm_mechanism_diagnostic",
        "four_arm_main_table_is_executable_with_one_shared_route",
        "four_arm_main_table_binds_frozen_ours_before_adapter_route_or_model",
        "external_report_declares_benchmark_aware_locked_reevaluation",
        "official_cn30_prior_aggregate_use_is_disclosed_and_excluded_from_learning",
        "client_routing_requires_positive_target_alignment_before_canonicalization",
        "retired_investigation_planner_is_production_unreachable",
    } <= set(report["checks"])
    assert report["claim_boundary"] == {
        "static_data_and_execution_contract_audited": True,
        "gpu_model_chain_qualified": "not_assessed",
        "formal_training_completed": "not_assessed",
        "official_external_evaluation_completed": "not_assessed",
        "historical_cn30_aggregate_observed": True,
        "cn30_pristine_confirmatory_claim_allowed": False,
        "cn30_exposed_to_training_lawyer_or_teacher": False,
    }
    assert "benchmark-aware rather than a pristine confirmatory test" in report["interpretation"]
    assert "remains untouched" not in report["interpretation"]
