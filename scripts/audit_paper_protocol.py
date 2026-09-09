#!/usr/bin/env python3
"""Fail-closed static audit for the publication-facing LegalSkillEvolve protocol.

The audit answers one narrow question: does the checked-in execution surface
describe the current 128-case direct skill-accumulation experiment?  It does not
qualify GPU services, judge model quality, learned-skill quality, or benchmark
performance.  Historical reports and the explicitly retired top-level blueprint
are deliberately outside the execution truth set.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]

ACTIVE_CODE_PATHS = (
    "legal_skill_guard/experiment/executor.py",
    "legal_skill_guard/experiment/runner.py",
    "legal_skill_guard/experiment/batches.py",
    "legal_skill_guard/evolution/teacher.py",
    "legal_skill_guard/schemas/experiment.py",
    "legal_skill_guard/schemas/skill.py",
    "legal_skill_guard/skills/memory.py",
    "scripts/run_main_experiment.py",
    "scripts/audit_main_run_progress.py",
)
ACTIVE_CONFIG_PATHS = (
    "configs/experiments/main_experiment.yaml",
    "configs/data/main_corpus.yaml",
    "configs/data/main_training_batches.yaml",
    "configs/models/roles.yaml",
)
ACTIVE_DOCUMENT_PATHS = (
    "README.md",
    "docs/architecture/current_research_protocol.md",
    "docs/architecture/evaluation_contract.md",
    "docs/architecture/llm_role_decisions.md",
    "docs/architecture/no_hardcoded_behavior.md",
    "docs/data/main_corpus_card.md",
    "docs/operations/main_experiment_execution.md",
    "reports/main_experiment_current_status.md",
)

# These match retired lifecycle semantics, not ordinary uses of "candidate" or
# the current provenance field.  In particular, ``provenance`` must never be
# mistaken for the retired ``provisional`` state.
LEGACY_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("prospective", re.compile(r"prospective", re.IGNORECASE)),
    ("provisional", re.compile(r"provisional", re.IGNORECASE)),
    ("candidate_with", re.compile(r"candidate_with", re.IGNORECASE)),
    ("candidate_without", re.compile(r"candidate_without", re.IGNORECASE)),
    ("42_plus_18", re.compile(r"(?<!\d)42\s*\+\s*18(?!\d)")),
    (
        "per_candidate_outcome_lifecycle",
        re.compile(r"\b(?:ACCEPT|DEFER|REJECT)\b"),
    ),
    (
        "embedded_candidate_gate",
        re.compile(r"embedded_next_block_skill_gate", re.IGNORECASE),
    ),
    (
        "per_candidate_validation",
        re.compile(r"逐候选.{0,16}(?:验收|准入|效果门|配对)", re.IGNORECASE),
    ),
    (
        "next_unseen_candidate_gate",
        re.compile(r"(?:下一|后续).{0,8}未见.{0,20}(?:配对|验收|准入|门禁)"),
    ),
    ("prospective_gate_zh", re.compile(r"前瞻(?:检验|验收|准入|门禁)")),
)

LEGACY_EXECUTOR_SYMBOLS = {
    "AcceptanceThresholds",
    "AuditDecision",
    "PairOutcome",
    "ProspectiveCandidateAudit",
    "candidate_intervention_isolation_report",
    "decide_skill",
    "fresh_candidate_nomination_slots",
    "mechanism_direction_gate",
    "prospective_audit_teacher_feedback",
    "prospective_exposure_minima",
    "validate_preceding_block_candidates",
    "validate_provisional_candidate",
}

RETIREMENT_MARKERS = (
    "历史",
    "旧",
    "退役",
    "已取消",
    "不再",
    "不存在",
    "不使用",
    "不做",
    "不以",
    "不把",
    "不会",
    "不产生",
    "不反向",
    "不恢复",
    "没有",
    "不得恢复",
    "不能恢复",
    "不是现役",
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load a JSONL artifact without silently skipping malformed records."""

    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a YAML mapping: {path}")
    return value


def _retired_context(line: str) -> bool:
    """Return true only for an explicit, publication-facing retirement statement."""

    return any(marker in line for marker in RETIREMENT_MARKERS)


def legacy_text_issues(
    path: Path,
    text: str,
    *,
    allow_explicit_retirement: bool,
) -> list[str]:
    """Find retired protocol language in active configuration, prompts, or docs."""

    issues: list[str] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for label, pattern in LEGACY_PATTERNS:
            if not pattern.search(line):
                continue
            if allow_explicit_retirement and _retired_context(line):
                continue
            issues.append(f"{path.as_posix()}:{line_number}:{label}")
    return issues


def legacy_yaml_issues(path: Path, value: object) -> list[str]:
    """Inspect YAML keys and prose while allowing explicit removal declarations."""

    issues: list[str] = []

    def visit(item: object, location: str) -> None:
        if isinstance(item, dict):
            for key, child in item.items():
                key_text = str(key)
                for label, pattern in LEGACY_PATTERNS:
                    if pattern.search(key_text):
                        issues.append(f"{path.as_posix()}:{location}.{key}:{label}_key")
                visit(child, f"{location}.{key}")
        elif isinstance(item, list):
            for index, child in enumerate(item):
                visit(child, f"{location}[{index}]")
        elif isinstance(item, str):
            for line_number, line in enumerate(item.splitlines(), start=1):
                for label, pattern in LEGACY_PATTERNS:
                    if pattern.search(line) and not _retired_context(line):
                        issues.append(f"{path.as_posix()}:{location}:line{line_number}:{label}")

    visit(value, "$")
    return sorted(set(issues))


def legacy_python_issues(path: Path, text: str) -> list[str]:
    """Find executable legacy names/strings using the AST, ignoring comments."""

    tree = ast.parse(text, filename=str(path))
    issues: set[str] = set()
    for node in ast.walk(tree):
        token: str | None = None
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            token = node.name
        elif isinstance(node, ast.alias):
            token = node.asname or node.name.rsplit(".", 1)[-1]
        elif isinstance(node, ast.Name):
            token = node.id
        elif isinstance(node, ast.Attribute):
            token = node.attr
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            token = node.value
        if token is None:
            continue
        if token in LEGACY_EXECUTOR_SYMBOLS:
            issues.add(f"{path.as_posix()}:{getattr(node, 'lineno', 0)}:legacy_symbol:{token}")
        for label, pattern in LEGACY_PATTERNS:
            if pattern.search(token):
                issues.add(f"{path.as_posix()}:{getattr(node, 'lineno', 0)}:{label}")
    return sorted(issues)


def _class_method_sources(text: str, class_name: str, method_name: str) -> list[str]:
    tree = ast.parse(text)
    values: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != class_name:
            continue
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
                child.name == method_name
            ):
                segment = ast.get_source_segment(text, child)
                values.append(segment or "")
    return values


def _protocol_paths(root: Path) -> dict[str, Path]:
    return {
        "experiment": root / "configs/experiments/main_experiment.yaml",
        "corpus_config": root / "configs/data/main_corpus.yaml",
        "batch_plan": root / "configs/data/main_training_batches.yaml",
        "roles": root / "configs/models/roles.yaml",
        "teacher_prompt": root / "configs/prompts/skill_teacher_zh.txt",
        "executor": root / "legal_skill_guard/experiment/executor.py",
        "runner": root / "legal_skill_guard/experiment/runner.py",
        "teacher": root / "legal_skill_guard/evolution/teacher.py",
        "memory": root / "legal_skill_guard/skills/memory.py",
        "batch_schema": root / "legal_skill_guard/experiment/batches.py",
        "skill_schema": root / "legal_skill_guard/schemas/skill.py",
        "trajectory_schema": root / "legal_skill_guard/schemas/experiment.py",
        "run_progress": root / "scripts/audit_main_run_progress.py",
        "run_cli": root / "scripts/run_main_experiment.py",
    }


def build_report(root: Path = ROOT) -> dict[str, Any]:
    """Build, but do not persist, the current static-protocol audit report."""

    root = root.resolve()
    paths = _protocol_paths(root)
    experiment = _load_yaml(paths["experiment"])
    corpus_config = _load_yaml(paths["corpus_config"])
    batch_plan = _load_yaml(paths["batch_plan"])
    roles = _load_yaml(paths["roles"])

    core_path = root / str(corpus_config["core_cases"])
    provenance_path = root / str(corpus_config["provenance"])
    selection_path = root / str(corpus_config["selection_manifest"])
    external_path = root / str(experiment["data"]["external_evaluation"])
    core = load_jsonl(core_path)
    provenance = load_jsonl(provenance_path)
    external = load_jsonl(external_path)

    batches = list(batch_plan.get("batches") or [])
    expected_case_ids = [f"lsg_cn_{index:04d}" for index in range(1, 129)]
    expected_batch_ids = [f"training_batch_{index:02d}" for index in range(1, 9)]
    core_ids = [str(item.get("id")) for item in core]
    provenance_ids = [str(item.get("id")) for item in provenance]
    batch_ids = [str(item.get("batch_id")) for item in batches]
    flattened_ids = [str(case_id) for batch in batches for case_id in batch.get("case_ids", [])]
    domain_by_case = {
        str(item.get("id")): str(item.get("annotation", {}).get("legal_domain"))
        for item in provenance
    }
    domains = sorted(set(domain_by_case.values()))

    execution = experiment.get("execution", {})
    admission = experiment.get("skill_admission", {})
    learning_curve = experiment.get("learning_curve", {})
    sentinels = learning_curve.get("sentinel_case_ids_by_block", {})
    training_persona = str(batch_plan.get("coverage_requirements", {}).get("training_persona", ""))
    skill_accumulation = batch_plan.get("skill_accumulation", {})

    code_sources = {
        relative: (root / relative).read_text(encoding="utf-8") for relative in ACTIVE_CODE_PATHS
    }
    prompt_paths = sorted((root / "configs/prompts").glob("*.txt"))
    prompt_sources = {
        path.relative_to(root).as_posix(): path.read_text(encoding="utf-8") for path in prompt_paths
    }
    document_sources = {
        relative: (root / relative).read_text(encoding="utf-8")
        for relative in ACTIVE_DOCUMENT_PATHS
    }
    executor_source = code_sources["legal_skill_guard/experiment/executor.py"]
    run_progress_source = code_sources["scripts/audit_main_run_progress.py"]
    teacher_source = code_sources["legal_skill_guard/evolution/teacher.py"]
    memory_source = code_sources["legal_skill_guard/skills/memory.py"]
    teacher_prompt = prompt_sources["configs/prompts/skill_teacher_zh.txt"]
    train_methods = _class_method_sources(executor_source, "MainExperimentExecutor", "train")

    code_legacy_issues = sorted(
        issue
        for relative, source in code_sources.items()
        for issue in legacy_python_issues(Path(relative), source)
    )
    config_values = {
        "configs/experiments/main_experiment.yaml": experiment,
        "configs/data/main_corpus.yaml": corpus_config,
        "configs/data/main_training_batches.yaml": batch_plan,
        "configs/models/roles.yaml": roles,
    }
    config_legacy_issues = sorted(
        {
            *(
                issue
                for relative, value in config_values.items()
                for issue in legacy_yaml_issues(Path(relative), value)
            ),
            *(
                issue
                for relative in ACTIVE_CONFIG_PATHS
                for issue in legacy_text_issues(
                    Path(relative),
                    (root / relative).read_text(encoding="utf-8"),
                    allow_explicit_retirement=True,
                )
            ),
        }
    )
    prompt_legacy_issues = sorted(
        issue
        for relative, source in prompt_sources.items()
        for issue in legacy_text_issues(Path(relative), source, allow_explicit_retirement=True)
    )
    document_legacy_issues = sorted(
        issue
        for relative, source in document_sources.items()
        for issue in legacy_text_issues(Path(relative), source, allow_explicit_retirement=True)
    )

    blueprint_path = root.parent / "LegalSkillGuard项目框架与完整实验实施方案.md"
    blueprint_marker_ok = True
    if blueprint_path.is_file():
        blueprint_head = "\n".join(blueprint_path.read_text(encoding="utf-8").splitlines()[:14])
        blueprint_marker_ok = "历史蓝图" in blueprint_head and "禁止执行" in blueprint_head

    corpus_hashes = corpus_config.get("hashes", {})
    external_policy = corpus_config.get("external_benchmark_policy", {})
    arm_ids = [str(item.get("arm_id")) for item in experiment.get("comparison_arms", [])]
    roles_by_name = roles.get("roles", {})
    lawyer_role = roles_by_name.get("lawyer_policy", {})
    teacher_role = roles_by_name.get("skill_teacher", {})
    judge_role = roles_by_name.get("semantic_judge", {})
    non_llm_components = [str(item) for item in roles.get("non_llm_components", [])]

    sentinels_ok = (
        isinstance(sentinels, dict)
        and set(sentinels) == set(expected_batch_ids)
        and all(
            len(sentinels.get(batch_id, [])) == len(set(sentinels.get(batch_id, []))) == 8
            and set(sentinels.get(batch_id, [])) <= set(batches[index].get("case_ids", []))
            and {
                batches[index].get("persona_assignment", {}).get(case_id)
                for case_id in sentinels.get(batch_id, [])
            }
            == {"P_WD"}
            for index, batch_id in enumerate(expected_batch_ids)
        )
    )

    teacher_selection_markers = (
        "def select_teacher_evidence_clusters(" in teacher_source
        and "evidence_scope" in teacher_source
        and "seen_fingerprints" in teacher_source
        and "general =" in teacher_source
        and "domain_specific =" in teacher_source
        and "budget >= 2 and general and domain_specific" in teacher_source
    )
    direct_executor_markers = (
        len(train_methods) == 1
        and "self.propose_candidates(" in train_methods[0]
        and "self.admit_source_grounded_candidates(" in train_methods[0]
        and "self._activate_source_grounded_skills(" in train_methods[0]
        and "self.write_library_maintenance_report(" in train_methods[0]
        and "if round_index < rounds" not in train_methods[0]
        and "source_grounded_skills_admitted_to_working_library" in executor_source
        and "hard_trust_gate_not_candidate_efficacy_test" in executor_source
        and '"per_candidate_outcome_gate": False' in executor_source
        and '"maintenance_scope": "whole_working_library"' in executor_source
        and '"automatic_candidate_effect_pruning": False' in executor_source
    )
    same_library_k4_markers = (
        'method = "training_policy_sample"' in executor_source
        and '"skill_library_version": skill_hash' in executor_source
        and "def _training_skill_memory_contract(" in executor_source
        and "return {skill_library_sha256(input_skills): list(input_skills)}" in executor_source
    )

    teacher_sees = set(teacher_role.get("sees", []))
    teacher_forbidden = set(teacher_role.get("forbidden", []))
    lawyer_sees = set(lawyer_role.get("sees", []))
    lawyer_forbidden = set(lawyer_role.get("forbidden", []))
    judge_forbidden = set(judge_role.get("forbidden", []))
    role_rationales = "\n".join(
        str(value.get("rationale", ""))
        for value in roles_by_name.values()
        if isinstance(value, dict)
    )
    readme_source = document_sources["README.md"]
    protocol_doc = document_sources["docs/architecture/current_research_protocol.md"]
    evaluation_doc = document_sources["docs/architecture/evaluation_contract.md"]
    roles_doc = document_sources["docs/architecture/llm_role_decisions.md"]
    execution_doc = document_sources["docs/operations/main_experiment_execution.md"]

    checks: dict[str, bool] = {
        "current_protocol_declares_128_cases_and_8_rounds": (
            experiment.get("status") == "direct_skill_accumulation_gpu_requalification_required"
            and int(execution.get("evolution_rounds", 0)) == 8
            and corpus_config.get("formal_split") == {"train": 128}
            and int(corpus_config.get("fixed_internal_validation_cases", -1)) == 0
        ),
        "canonical_corpus_is_exactly_128_train_cases": (
            core_ids == expected_case_ids
            and provenance_ids == expected_case_ids
            and len(set(core_ids)) == 128
            and all(item.get("split") == "train" for item in provenance)
        ),
        "frozen_corpus_and_batch_hashes_match": (
            digest(core_path) == corpus_hashes.get("core_sha256")
            and digest(provenance_path) == corpus_hashes.get("provenance_sha256")
            and digest(selection_path) == corpus_hashes.get("selection_sha256")
            and digest(paths["batch_plan"]) == corpus_hashes.get("training_batches_sha256")
        ),
        "batch_plan_is_schema3_exact_8_by_16_partition": (
            batch_plan.get("schema_version") == 3
            and batch_plan.get("design") == "balanced_sequential_skill_accumulation_blocks"
            and int(batch_plan.get("training_cases", 0)) == 128
            and int(batch_plan.get("training_batches", 0)) == 8
            and int(batch_plan.get("cases_per_batch", 0)) == 16
            and batch_ids == expected_batch_ids
            and all(len(batch.get("case_ids", [])) == 16 for batch in batches)
            and len(flattened_ids) == len(set(flattened_ids)) == 128
            and set(flattened_ids) == set(core_ids)
        ),
        "training_uses_one_controlled_cooperative_persona": (
            training_persona == "P_WD"
            and all(
                set(batch.get("persona_assignment", {})) == set(batch.get("case_ids", []))
                and set(batch.get("persona_assignment", {}).values()) == {"P_WD"}
                for batch in batches
            )
        ),
        "k4_uses_one_batch_start_library_without_candidate_arms": (
            int(experiment.get("trajectory_sampling", {}).get("group_size", 0)) == 4
            and experiment.get("trajectory_sampling", {}).get("training_group_seeds") == [42]
            and same_library_k4_markers
        ),
        "teacher_budget_is_zero_to_three_and_scope_diverse": (
            int(execution.get("teacher_call_budget_per_round", -1)) == 3
            and int(execution.get("maximum_new_skills_per_block", -1)) == 3
            and int(execution.get("maximum_teacher_groups_per_case", 0)) >= 1
            and teacher_selection_markers
            and "零至三个" in teacher_prompt
            and "通用" in teacher_prompt
            and "领域" in teacher_prompt
        ),
        "five_hard_trust_gates_directly_admit_to_active_library": (
            admission.get("mode") == "source_grounded_direct_admission"
            and admission.get("require_no_leakage") is True
            and admission.get("require_no_hard_safety_violation") is True
            and admission.get("require_source_grounding") is True
            and admission.get("reject_exact_semantic_duplicates") is True
            and admission.get("enforce_prompt_capacity") is True
            and admission.get("per_candidate_outcome_gate") is False
            and admission.get("effect_assessment") == "downstream_library_level_only"
            and direct_executor_markers
        ),
        "all_eight_blocks_generate_and_accumulate_skills": (
            skill_accumulation.get("mode") == "source_grounded_direct_admission"
            and skill_accumulation.get("first_source_batch") == expected_batch_ids[0]
            and skill_accumulation.get("final_source_batch") == expected_batch_ids[-1]
            and skill_accumulation.get("final_batch_generates_skills") is True
        ),
        "whole_library_prequential_curve_is_diagnostic_only": (
            learning_curve.get("mode") == "prequential_fixed_shadow"
            and learning_curve.get("status") == "frozen_before_next_formal_run"
            and int(learning_curve.get("cases_per_block", 0)) == 8
            and learning_curve.get("empty_library_identity_shortcut") is True
            and "never_teacher" in str(learning_curve.get("evidence_role", ""))
            and "skill_admission" in str(learning_curve.get("evidence_role", ""))
            and sentinels_ok
        ),
        "maintenance_is_whole_library_every_two_blocks": (
            int(admission.get("maintenance_interval_blocks", 0)) == 2
            and int(skill_accumulation.get("maintenance_interval_blocks", 0)) == 2
            and "round_index % interval != 0" in executor_source
        ),
        "final_external_test_has_exactly_two_skill_intervention_arms": (
            arm_ids == ["control_no_library", "legal_skill_evolve"]
            and experiment.get("trajectory_sampling", {}).get("external_evaluation_seeds") == [42]
            and experiment.get("personas") == ["P_WD", "P_WS", "P_CS", "P_CD"]
        ),
        "primary_endpoint_is_fact_efficiency_with_quality_companions": (
            experiment.get("evaluation", {}).get("primary_endpoint")
            == "unique_disclosed_facts_per_question"
            and {
                "unique_disclosed_facts",
                "fact_coverage",
                "resolution",
                "critical_fact_recall",
            }
            <= set(experiment.get("evaluation", {}).get("secondary_endpoints", []))
        ),
        "official_cn30_is_frozen_and_never_used_for_debug_or_learning": (
            len(external) == 30
            and experiment.get("data", {}).get("external_evaluation_status")
            == "held_out_frozen_test_not_used_for_debugging"
            and external_policy.get("dlawbench_public_cn30") == "held_out_frozen_external_test"
            and external_policy.get("current_payload_sha256") == digest(external_path)
            and external_policy.get("used_for_runtime_debugging") is False
            and external_policy.get("used_for_model_prompt_or_threshold_selection") is False
            and external_policy.get("evaluation_after_library_freeze_only") is True
            and external_policy.get("may_enter_training") is False
            and external_policy.get("may_enter_skill_teacher_context") is False
        ),
        "model_roles_preserve_intervention_and_information_boundaries": (
            lawyer_role.get("model_id") == "Qwen/Qwen3-8B"
            and "fixed_session_skill_documents" in lawyer_sees
            and {"client_belief_labels", "court_record", "evaluation_criteria"} <= lawyer_forbidden
            and teacher_role.get("model_id") == "gpt-5.6-luna"
            and {
                "training_trajectory_contrast_clusters",
                "training_offline_scores",
                "current_skill_documents",
            }
            <= teacher_sees
            and {
                "future_block_hidden_labels",
                "external_benchmark_cases",
                "arm_test_results",
            }
            <= teacher_forbidden
            and judge_role.get("model_id") == "openai/gpt-oss-20b"
            and {"skill_teacher_trace", "skill_identity", "arm_name"} <= judge_forbidden
            and "硬门" in role_rationales
            and "直接写入工作库" in role_rationales
            and "累计工作库" in role_rationales
        ),
        "non_llm_roles_name_direct_admission_prequential_and_maintenance": (
            "embedded_next_block_skill_gate" not in non_llm_components
            and any("direct" in item for item in non_llm_components)
            and any("prequential" in item for item in non_llm_components)
            and any("maintenance" in item for item in non_llm_components)
        ),
        "skills_are_fixed_prompt_documents_not_runtime_actions": (
            "render_skill_memory" in code_sources["legal_skill_guard/experiment/runner.py"]
            and "applicability_cues" in memory_source
            and "question_guidance" in memory_source
            and "candidate_action" not in memory_source
            and 'SkillStatus = Literal["candidate", "active", "rejected", "deprecated"]'
            in code_sources["legal_skill_guard/schemas/skill.py"]
        ),
        "active_code_contains_no_retired_execution_semantics": not code_legacy_issues,
        "active_configs_and_prompts_contain_no_retired_execution_semantics": (
            not config_legacy_issues and not prompt_legacy_issues
        ),
        "executor_and_monitor_share_current_admission_artifact_name": (
            "skill_admission_round_" in executor_source
            and "skill_admission_round_" in run_progress_source
            and "candidate_source_grounding_round_" not in executor_source
            and "candidate_source_grounding_round_" not in run_progress_source
        ),
        "current_documents_only_mention_old_protocol_as_retired": (not document_legacy_issues),
        "documentation_truth_sources_describe_the_executable_protocol": (
            readme_source.startswith("# LegalSkillEvolve")
            and "现役执行真源" in protocol_doc
            and "128案全部属于顺序训练过程" in protocol_doc
            and "第八块仍可生成并入库" in protocol_doc
            and "五类准入硬门" in evaluation_doc
            and "主终点" in evaluation_doc
            and "gpt-5.6-luna" in roles_doc
            and "gpt-oss-20b" in roles_doc
            and "Qwen3-8B" in roles_doc
            and "8块×16案" in execution_doc
            and "--fresh --confirm I_CONFIRM_MAIN_TRAINING" in execution_doc
            and "--resume --confirm I_CONFIRM_MAIN_TRAINING" in execution_doc
            and "docs/architecture/current_research_protocol.md" in readme_source
            and "docs/architecture/evaluation_contract.md" in readme_source
            and "docs/operations/main_experiment_execution.md" in readme_source
        ),
        "retired_top_level_blueprint_is_explicitly_non_executable": blueprint_marker_ok,
    }

    maintenance_blocks = [
        index
        for index in range(1, len(batches) + 1)
        if index % int(admission.get("maintenance_interval_blocks", 1)) == 0
    ]
    maximum_teacher_calls = len(batches) * int(execution.get("teacher_call_budget_per_round", 0))
    checks_passed = all(checks.values())
    protocol_hash_paths = {
        **paths,
        **{f"prompt_{path.stem}": path for path in prompt_paths if path != paths["teacher_prompt"]},
        **{
            f"document_{Path(relative).stem}": root / relative for relative in ACTIVE_DOCUMENT_PATHS
        },
    }
    return {
        "schema_version": 3,
        "status": (
            "static_direct_protocol_passed_gpu_requalification_required"
            if checks_passed
            else "static_direct_protocol_failed"
        ),
        "claim_boundary": {
            "static_data_and_execution_contract_audited": checks_passed,
            "gpu_model_chain_qualified": False,
            "formal_training_completed": False,
            "official_external_evaluation_completed": False,
            "official_cn30_previously_used_for_debugging": False,
        },
        "design": {
            "training_cases": len(core),
            "training_blocks": len(batches),
            "cases_per_block": [len(batch.get("case_ids", [])) for batch in batches],
            "training_persona": training_persona,
            "trajectories_per_case": int(
                experiment.get("trajectory_sampling", {}).get("group_size", 0)
            ),
            "base_training_trajectories": len(core)
            * int(experiment.get("trajectory_sampling", {}).get("group_size", 0)),
            "teacher_calls_per_block": int(execution.get("teacher_call_budget_per_round", 0)),
            "maximum_teacher_calls": maximum_teacher_calls,
            "maximum_new_skills": len(batches)
            * int(execution.get("maximum_new_skills_per_block", 0)),
            "per_candidate_validation_sessions": 0,
            "prequential_shadow_sessions_upper_bound": max(0, len(batches) - 1)
            * int(learning_curve.get("cases_per_block", 0)),
            "maintenance_blocks": maintenance_blocks,
            "final_block_generates_skills": skill_accumulation.get("final_batch_generates_skills"),
            "external_cases": len(external),
            "external_personas": len(experiment.get("personas", [])),
            "external_arms": arm_ids,
            "training_domains": domains,
        },
        "checks": checks,
        "failed_checks": sorted(name for name, passed in checks.items() if not passed),
        "legacy_semantic_issues": {
            "active_code": code_legacy_issues,
            "active_configs": config_legacy_issues,
            "active_prompts": prompt_legacy_issues,
            "current_documents": document_legacy_issues,
            "excluded_history": [
                "reports/historical/**",
                "reports/artifacts/rejected*/**",
                "runs/rejected_diagnostics/**",
                "top-level blueprint when marked 历史蓝图·禁止执行",
            ],
        },
        "protocol_hashes": {
            name: digest(path)
            for name, path in sorted(protocol_hash_paths.items())
            if path.is_file()
        },
        "interpretation": (
            "Passing establishes only static agreement on the 128-case, 8-by-16, "
            "source-grounded direct skill-accumulation protocol: K=4 shares one "
            "block-start library, hard trust gates admit documents directly, effects "
            "are observed prequentially at whole-library level, every second block is "
            "maintained, and CN30 remains untouched until the frozen two-arm external "
            "test. It is not evidence of runtime qualification, learned improvement, "
            "or benchmark performance."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "reports/artifacts/paper_protocol_readiness.json",
    )
    args = parser.parse_args()
    report = build_report(ROOT)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["failed_checks"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
