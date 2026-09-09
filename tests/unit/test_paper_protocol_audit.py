from pathlib import Path

from scripts.audit_paper_protocol import (
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
下一未见块承担配对验收。
K=4 包含 candidate_with 和 candidate_without。
"""

    assert not legacy_text_issues(
        Path("README.md"),
        retired,
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
        "rationale": "来源证据不能替代下一未见块的配对验收。",
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


def test_repository_report_describes_only_the_direct_accumulation_design() -> None:
    report = build_report(ROOT)

    assert report["schema_version"] == 3
    assert report["design"] == {
        **report["design"],
        "training_cases": 128,
        "training_blocks": 8,
        "cases_per_block": [16] * 8,
        "training_persona": "P_WD",
        "trajectories_per_case": 4,
        "base_training_trajectories": 512,
        "teacher_calls_per_block": 3,
        "maximum_teacher_calls": 24,
        "maximum_new_skills": 24,
        "per_candidate_validation_sessions": 0,
        "prequential_shadow_sessions_upper_bound": 56,
        "maintenance_blocks": [2, 4, 6, 8],
        "final_block_generates_skills": True,
        "external_cases": 30,
        "external_personas": 4,
        "external_arms": ["control_no_library", "legal_skill_evolve"],
    }
    assert "maximum_provisional_candidates" not in report["design"]
    assert "embedded_candidate_evaluation_blocks" not in report["design"]
    assert {
        "five_hard_trust_gates_directly_admit_to_active_library",
        "all_eight_blocks_generate_and_accumulate_skills",
        "whole_library_prequential_curve_is_diagnostic_only",
        "maintenance_is_whole_library_every_two_blocks",
        "official_cn30_is_frozen_and_never_used_for_debug_or_learning",
    } <= set(report["checks"])
