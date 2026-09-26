#!/usr/bin/env python3
"""Fail-closed static audit for the publication-facing LegalSkillEvolve protocol.

The audit answers one narrow question: does the checked-in execution surface
describe the current 128-case exact-input, direct-accumulation experiment?  It
does not qualify GPU services, judge model quality, learned-skill quality, or
benchmark performance.  Historical reports and the explicitly retired top-level
blueprint are deliberately outside the execution truth set.
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
    "legal_skill_guard/schemas/action.py",
    "legal_skill_guard/agent/stateful_policy.py",
    "legal_skill_guard/experiment/executor.py",
    "legal_skill_guard/experiment/runner.py",
    "legal_skill_guard/experiment/trajectory_health.py",
    "legal_skill_guard/opening_agenda_contract.py",
    "legal_skill_guard/experiment/batches.py",
    "legal_skill_guard/experiment/intervention_isolation.py",
    "legal_skill_guard/experiment/learning_curve.py",
    "legal_skill_guard/experiment/official_baselines.py",
    "legal_skill_guard/evaluation/semantic.py",
    "legal_skill_guard/evolution/group_evidence.py",
    "legal_skill_guard/evolution/teacher.py",
    "legal_skill_guard/schemas/experiment.py",
    "legal_skill_guard/schemas/skill.py",
    "legal_skill_guard/skills/memory.py",
    "scripts/run_main_experiment.py",
    "scripts/audit_main_run_progress.py",
    "scripts/run_official_baselines.py",
)
ACTIVE_CONFIG_PATHS = (
    "configs/experiments/main_experiment.yaml",
    "configs/experiments/official_baselines.yaml",
    "configs/data/main_corpus.yaml",
    "configs/data/main_training_batches.yaml",
    "configs/models/roles.yaml",
)
ACTIVE_DOCUMENT_PATHS = (
    "README.md",
    "docs/architecture/artifact_naming.md",
    "docs/architecture/current_research_protocol.md",
    "docs/architecture/evaluation_contract.md",
    "docs/architecture/llm_role_decisions.md",
    "docs/architecture/no_hardcoded_behavior.md",
    "docs/data/main_corpus_card.md",
    "docs/operations/main_experiment_execution.md",
)

# These match retired lifecycle semantics, not ordinary uses of "candidate" or
# the current provenance field.  In particular, ``provenance`` must never be
# mistaken for the retired ``provisional`` state.
LEGACY_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("prospective", re.compile(r"prospective", re.IGNORECASE)),
    (
        "provisional",
        re.compile(
            r"(?:provisional_(?:candidate|state|skill(?!_cohort))|"
            r"provisional\s+(?:candidate|state)\b|"
            r"provisional\s+skill\b(?!\s+cohort)|"
            r"provisional\s*(?:状态|候选)|"
            r"(?:candidate|skill|候选).{0,16}provisional\s*"
            r"(?:candidate|skill|state|状态))",
            re.IGNORECASE,
        ),
    ),
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
        re.compile(
            r"(?:逐候选.{0,24}(?:下一|后续).{0,8}未见.{0,20}(?:配对|验收|准入|门禁)|"
            r"(?:下一|后续).{0,8}未见.{0,24}逐候选.{0,12}(?:配对|验收|准入|门禁)|"
            r"next_unseen_candidate_gate)",
            re.IGNORECASE,
        ),
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


def _function_sources(text: str, function_name: str) -> list[str]:
    """Return exact sources for top-level functions with ``function_name``."""

    tree = ast.parse(text)
    values: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
            node.name == function_name
        ):
            segment = ast.get_source_segment(text, node)
            values.append(segment or "")
    return values


def _protocol_paths(root: Path) -> dict[str, Path]:
    return {
        "experiment": root / "configs/experiments/main_experiment.yaml",
        "main_table_config": root / "configs/experiments/official_baselines.yaml",
        "corpus_config": root / "configs/data/main_corpus.yaml",
        "batch_plan": root / "configs/data/main_training_batches.yaml",
        "roles": root / "configs/models/roles.yaml",
        "teacher_prompt": root / "configs/prompts/skill_teacher_zh.txt",
        "stateful_policy": root / "legal_skill_guard/agent/stateful_policy.py",
        "executor": root / "legal_skill_guard/experiment/executor.py",
        "runner": root / "legal_skill_guard/experiment/runner.py",
        "trajectory_health": root / "legal_skill_guard/experiment/trajectory_health.py",
        "intervention_isolation": (root / "legal_skill_guard/experiment/intervention_isolation.py"),
        "learning_curve": root / "legal_skill_guard/experiment/learning_curve.py",
        "main_table_controller": (root / "legal_skill_guard/experiment/official_baselines.py"),
        "group_evidence": root / "legal_skill_guard/evolution/group_evidence.py",
        "teacher": root / "legal_skill_guard/evolution/teacher.py",
        "memory": root / "legal_skill_guard/skills/memory.py",
        "batch_schema": root / "legal_skill_guard/experiment/batches.py",
        "skill_schema": root / "legal_skill_guard/schemas/skill.py",
        "trajectory_schema": root / "legal_skill_guard/schemas/experiment.py",
        "run_progress": root / "scripts/audit_main_run_progress.py",
        "run_cli": root / "scripts/run_main_experiment.py",
        "main_table_cli": root / "scripts/run_official_baselines.py",
    }


def build_report(root: Path = ROOT) -> dict[str, Any]:
    """Build, but do not persist, the current static-protocol audit report."""

    root = root.resolve()
    paths = _protocol_paths(root)
    experiment = _load_yaml(paths["experiment"])
    main_table = _load_yaml(paths["main_table_config"])
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
    evolution = experiment.get("skill_evolution", {})
    learning_curve = experiment.get("learning_curve", {})
    sentinels = learning_curve.get("sentinel_case_ids_by_block", {})
    exact_prefix = experiment.get("trajectory_sampling", {}).get(
        "training_exact_prefix_branching", {}
    )
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
    runner_source = code_sources["legal_skill_guard/experiment/runner.py"]
    trajectory_health_source = code_sources[
        "legal_skill_guard/experiment/trajectory_health.py"
    ]
    opening_agenda_contract_source = code_sources[
        "legal_skill_guard/opening_agenda_contract.py"
    ]
    experiment_schema_source = code_sources["legal_skill_guard/schemas/experiment.py"]
    action_schema_source = code_sources["legal_skill_guard/schemas/action.py"]
    stateful_policy_source = code_sources["legal_skill_guard/agent/stateful_policy.py"]
    isolation_source = code_sources["legal_skill_guard/experiment/intervention_isolation.py"]
    learning_curve_source = code_sources["legal_skill_guard/experiment/learning_curve.py"]
    main_table_source = code_sources["legal_skill_guard/experiment/official_baselines.py"]
    run_main_source = code_sources["scripts/run_main_experiment.py"]
    run_progress_source = code_sources["scripts/audit_main_run_progress.py"]
    main_table_cli_source = code_sources["scripts/run_official_baselines.py"]
    teacher_source = code_sources["legal_skill_guard/evolution/teacher.py"]
    group_evidence_source = code_sources["legal_skill_guard/evolution/group_evidence.py"]
    memory_source = code_sources["legal_skill_guard/skills/memory.py"]
    teacher_prompt = prompt_sources["configs/prompts/skill_teacher_zh.txt"]
    mode_extractor_prompt = prompt_sources["configs/prompts/skill_mode_extractor_zh.txt"]
    opening_agenda_prompt = prompt_sources["configs/prompts/opening_inquiry_agenda_zh.txt"]
    train_methods = _class_method_sources(executor_source, "MainExperimentExecutor", "train")
    visible_message_methods = _class_method_sources(
        runner_source, "TrajectoryRunner", "_visible_messages"
    )
    runner_init_methods = _class_method_sources(runner_source, "TrajectoryRunner", "__init__")
    runner_run_methods = _class_method_sources(runner_source, "TrajectoryRunner", "run")
    trajectory_health_issue_functions = _function_sources(
        trajectory_health_source, "trajectory_health_issues"
    )
    main_table_run_methods = _class_method_sources(
        main_table_source, "OfficialBaselineController", "run_official_arm"
    )
    main_table_bind_methods = _class_method_sources(
        main_table_source, "OfficialBaselineController", "bind_ours_training_source"
    )

    code_legacy_issues = sorted(
        issue
        for relative, source in code_sources.items()
        for issue in legacy_python_issues(Path(relative), source)
    )
    config_values = {
        "configs/experiments/main_experiment.yaml": experiment,
        "configs/experiments/official_baselines.yaml": main_table,
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
    diagnostic_arm_ids = [str(item.get("arm_id")) for item in experiment.get("comparison_arms", [])]
    main_table_arm_ids = [str(item.get("arm_id")) for item in main_table.get("arms", [])]
    main_table_official = main_table.get("official_data", {})
    main_table_router = main_table.get("domain_router", {})
    main_table_reporting = main_table.get("reporting", {})
    main_table_shared = main_table.get("shared_runtime", {})
    roles_by_name = roles.get("roles", {})
    lawyer_role = roles_by_name.get("lawyer_policy", {})
    opening_agenda_role = roles_by_name.get("opening_inquiry_agenda", {})
    teacher_role = roles_by_name.get("skill_teacher", {})
    judge_role = roles_by_name.get("semantic_judge", {})
    non_llm_components = [str(item) for item in roles.get("non_llm_components", [])]

    sentinels_ok = (
        isinstance(sentinels, dict)
        and set(sentinels) == set(expected_batch_ids)
        and all(
            len(sentinels.get(batch_id, []))
            == len(set(sentinels.get(batch_id, [])))
            == int(learning_curve.get("cases_per_block", 0))
            and sentinels.get(batch_id, []) == batches[index].get("case_ids", [])
            and {
                batches[index].get("persona_assignment", {}).get(case_id)
                for case_id in sentinels.get(batch_id, [])
            }
            == {"P_WD"}
            for index, batch_id in enumerate(expected_batch_ids)
        )
    )

    exact_visible_source_markers = (
        "def causal_visible_state_sha256(" in teacher_source
        and 'visible_input = getattr(step, "visible_input", None)' in teacher_source
        and '"policy_visible_input": messages' in teacher_source
        and "positive_state_hash = causal_visible_state_sha256(positive_step)" in teacher_source
        and "negative_state_hash = causal_visible_state_sha256(negative_step)" in teacher_source
        and "def structural_action_signature(" in teacher_source
        and "semantic_action_target(" in teacher_source
    )
    source_scope_teacher_markers = (
        "def filter_teacher_clusters_by_next_block_exposure(" not in teacher_source
        and "filter_teacher_clusters_by_next_block_exposure(" not in executor_source
        and "def extract_playbook_modes(" in teacher_source
        and "def propose_playbook_update(" in teacher_source
        and "playbook map artifacts do not partition all evidence cards" in teacher_source
    )
    direct_accumulation_executor_markers = (
        len(train_methods) == 1
        and "self.write_library_effect_disposition(" in train_methods[0]
        and "self.propose_candidates(" in train_methods[0]
        and train_methods[0].index("self.write_library_effect_disposition(")
        < train_methods[0].index("self.propose_candidates(")
        and "self.admit_source_grounded_candidates(" in train_methods[0]
        and "self._activate_source_grounded_skills(" in train_methods[0]
        and "self.write_library_maintenance_report(" in train_methods[0]
        and "if round_index < rounds" not in train_methods[0]
        and "group_evidence_playbook_admitted_to_working_library" in executor_source
        and "group_evidence_playbook_trust_gate" in executor_source
        and "playbook_update_has_no_document_change" in executor_source
        and '"per_candidate_outcome_gate": False' in executor_source
        and '"maintenance_scope": "whole_working_library"' in executor_source
        and '"automatic_candidate_effect_pruning": False' in executor_source
        and "def _load_validated_library_effect_disposition(" in executor_source
        and "def _previous_block_skill_increment(" in executor_source
        and '"new_skill_increment_ids"' in executor_source
        and '"automatic_skill_pruning": False' in executor_source
        and '"decision": "observe_increment_continue_training"' in executor_source
        and '"cohort_transition": "retain_increment_for_cross_block_evolution"' in executor_source
        and "_restore_rejected_cohort_parent" not in train_methods[0]
        and "_write_rejected_cohort_teacher_skip" not in train_methods[0]
        and "_write_rejected_cohort_block_complete" not in train_methods[0]
    )
    same_library_k4_markers = (
        'method = "training_policy_sample"' in executor_source
        and '"skill_library_version": skill_hash' in executor_source
        and "def _training_skill_memory_contract(" in executor_source
        and "return {skill_library_sha256(input_skills): list(input_skills)}" in executor_source
        and "TRAINING_BRANCH_TURNS = (1,)" in runner_source
        and "TRAINING_EXACT_PREFIX_MEMBERS = (0, 1, 2, 3)" in runner_source
        and "TRAINING_PREFIX_STREAM = 0" in runner_source
        and 'method == "training_policy_sample"' in runner_source
        and "turn < training_policy_branch_turn(case_id)" in runner_source
    )

    teacher_sees = set(teacher_role.get("sees", []))
    teacher_forbidden = set(teacher_role.get("forbidden", []))
    lawyer_sees = set(lawyer_role.get("sees", []))
    lawyer_forbidden = set(lawyer_role.get("forbidden", []))
    opening_agenda_forbidden = set(opening_agenda_role.get("forbidden", []))
    judge_forbidden = set(judge_role.get("forbidden", []))
    role_rationales = "\n".join(
        str(value.get("rationale", ""))
        for value in roles_by_name.values()
        if isinstance(value, dict)
    )
    readme_source = document_sources["README.md"]
    artifact_doc = document_sources["docs/architecture/artifact_naming.md"]
    protocol_doc = document_sources["docs/architecture/current_research_protocol.md"]
    evaluation_doc = document_sources["docs/architecture/evaluation_contract.md"]
    roles_doc = document_sources["docs/architecture/llm_role_decisions.md"]
    execution_doc = document_sources["docs/operations/main_experiment_execution.md"]

    main_table_run_order_ok = (
        len(main_table_run_methods) == 1
        and "self._bound_ours_training_source(protocol)" in main_table_run_methods[0]
        and "self._record_official_access(" in main_table_run_methods[0]
        and "self._official_routes(" in main_table_run_methods[0]
        and main_table_run_methods[0].index("self._bound_ours_training_source(protocol)")
        < main_table_run_methods[0].index("self._record_official_access(")
        < main_table_run_methods[0].index("self._official_routes(")
    )
    main_table_bind_fails_closed = (
        len(main_table_bind_methods) == 1
        and "self._validated_ours_training_source(training_run_id)" in main_table_bind_methods[0]
        and '"official_fixed_domain_routes.json"' in main_table_bind_methods[0]
        and 'glob("official_*_aggregate.json")' in main_table_bind_methods[0]
        and 'glob("official_*_artifacts.json")' in main_table_bind_methods[0]
        and 'glob("official_*/*.json")' in main_table_bind_methods[0]
        and "if existing:" in main_table_bind_methods[0]
    )
    practical_safety_endpoints = {
        "unique_disclosed_facts": 0.0,
        "critical_fact_recall": 0.05,
        "premature_final_rate": 0.05,
        "unsupported_claim_rate": 0.05,
        "belief_as_fact_rate": 0.02,
        "hidden_field_leak": 0.0,
        "repeated_question_rate": 0.05,
        "policy_fallback_rate": 0.0,
        "client_fallback_rate": 0.0,
    }
    practical_gate_parent = {
        "decision_rule": "primary_benefit_practical_safety_noninferiority",
        "effect_direction": "current_library_minus_parent_library",
        "primary_endpoint": "unique_disclosed_facts_per_question",
        "primary_threshold": 0.0,
        "protected_endpoint_margins": practical_safety_endpoints,
        "diagnostic_endpoints": [
            "identified_evidence_gaps",
            "resolution",
            "elicitation",
            "fidelity",
            "reward",
            "question_turns",
        ],
    }
    practical_gate_empty = {
        **practical_gate_parent,
        "effect_direction": "current_library_minus_empty_library",
    }

    checks: dict[str, bool] = {
        "current_protocol_declares_128_cases_and_8_rounds": (
            experiment.get("status")
            == "shared_opening_agenda_group_evidence_gpu_requalification_required"
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
        "k4_uses_predeclared_four_way_exact_visible_input_forks": (
            int(experiment.get("trajectory_sampling", {}).get("group_size", 0)) == 4
            and experiment.get("trajectory_sampling", {}).get("training_group_seeds") == [42]
            and exact_prefix
            == {
                "status": "frozen_before_next_formal_run",
                "exact_prefix_members": [0, 1, 2, 3],
                "prefix_stream": 0,
                "branch_turns": [1],
                "assignment": "fixed_first_turn_independent_streams",
            }
            and same_library_k4_markers
            and exact_visible_source_markers
        ),
        "shared_opening_only_agenda_is_nonbinding_and_arm_invariant": (
            opening_agenda_role.get("model_id") == lawyer_role.get("model_id")
            and opening_agenda_role.get("revision") == lawyer_role.get("revision")
            and opening_agenda_role.get("local_snapshot") == lawyer_role.get("local_snapshot")
            and opening_agenda_role.get("shared_across_comparison_arms") is True
            and opening_agenda_role.get("sees") == ["public_opening"]
            and {
                "client_belief_labels",
                "court_record",
                "evaluation_criteria",
                "persona",
                "active_skills",
                "arm_label",
                "trajectory_score",
            }
            <= opening_agenda_forbidden
            and "不是问题清单、固定顺序或最低提问轮数" in opening_agenda_prompt
            and "parse_opening_inquiry_agenda" in runner_source
            and '"required": ["topic_excerpt", "attribute"]' in runner_source
            and "OPENING_AGENDA_ATTRIBUTE_LABELS" in opening_agenda_contract_source
            and "topic_excerpt not in opening" in opening_agenda_contract_source
            and "opening_agenda_fact_id(label)" in runner_source
            and "opening_agenda_fact_id(label)" in code_sources[
                "legal_skill_guard/schemas/experiment.py"
            ]
            and "candidate_action_targets_known_fact(" not in runner_source
            and "逐字、连续摘自公开开场" in opening_agenda_prompt
            and "没有安全且尚未回答的维度时输出空 targets" in opening_agenda_prompt
            and "state = self.state_manager.merge(state, opening_inquiry_agenda, turn=0)"
            in runner_source
            and 'self.roles["roles"]["opening_inquiry_agenda"]' in executor_source
            and 'self.root / "configs/prompts/opening_inquiry_agenda_zh.txt"'
            in executor_source
        ),
        "teacher_map_reduce_covers_all_case_cards": (
            int(execution.get("teacher_call_budget_per_round", -1)) == 3
            and int(execution.get("maximum_new_skills_per_block", -1)) == 1
            and "同一份跨法域文档" in teacher_prompt
            and "ADD、REPLACE、DELETE" in teacher_prompt
            and "不得整份重写" in teacher_prompt
            and "build_group_evidence_card" in executor_source
        ),
        "teacher_preserves_group_relative_signal_without_dropping_ties": (
            "group_relative_status" in executor_source
            and "process_tied" in group_evidence_source
            and "extract_playbook_modes" in teacher_source
            and "playbook success mode cites a tied group" in teacher_source
        ),
        "teacher_card_uses_schema4_action_time_visible_agenda": (
            "schema_version: Literal[4] = 4" in group_evidence_source
            and '"opening_inquiry_agenda": _opening_agenda_targets(trajectory)'
            in group_evidence_source
            and 'expected_keys = {"target_id", "label", "criticality", "target_kind"}'
            in group_evidence_source
            and "group evidence inner card must use schema_version 4" in group_evidence_source
            and '"visible_target_catalog": [' in group_evidence_source
            and '"visible_unresolved_targets_before_action": unresolved_before_action'
            in group_evidence_source
            and "不是客户已经确认的事实，也不是标准答案" in mode_extractor_prompt
            and "visible_unresolved_targets_before_action" in mode_extractor_prompt
        ),
        "one_versioned_global_playbook_with_exact_local_edits": (
            "PLAYBOOK_SKILL_ID = GLOBAL_PLAYBOOK_SKILL_ID" in teacher_source
            and 'GLOBAL_PLAYBOOK_SKILL_ID = "general.legal_fact_elicitation_playbook"'
            in memory_source
            and "INITIAL_PLAYBOOK_MAX_PATCH_OPERATIONS = 8" in teacher_source
            and "EXISTING_PLAYBOOK_MAX_PATCH_OPERATIONS = 2" in teacher_source
            and '"maximum_patch_operations": maximum_operations' in teacher_source
            and "_apply_playbook_patch" in teacher_source
            and "replace_target_not_found" in teacher_source
            and "primary_endpoint_nonnegative" in teacher_prompt
            and "纸面出现过该机制不等于行为有效" in teacher_prompt
            and "持续未被遵循" in teacher_prompt
            and "candidate_cumulative_case_binding_mismatch" in executor_source
        ),
        "teacher_source_scope_is_not_filtered_by_next_block_case_mix": (
            "next_block_scope_feasibility" not in learning_curve and source_scope_teacher_markers
        ),
        "formal_learning_preserves_fact_evidence_and_stop_boundaries": (
            evolution.get("learnable_objectives") == ["fact_elicitation"]
            and evolution.get("termination_policy_owner")
            == "frozen_lawyer_with_prompt_skill_memory"
            and admission.get("allowed_objectives") == ["fact_elicitation"]
            and "formal_skill_document_issues(" in executor_source
            and "低收益转移" in mode_extractor_prompt
            and "高风险动作黑名单" in teacher_prompt
        ),
        "five_hard_trust_gates_directly_admit_working_documents": (
            admission.get("mode") == "group_evidence_global_playbook_evolution"
            and admission.get("require_no_leakage") is True
            and admission.get("require_no_hard_safety_violation") is True
            and admission.get("require_source_grounding") is True
            and admission.get("reject_exact_semantic_duplicates") is True
            and admission.get("enforce_prompt_capacity") is True
            and admission.get("per_candidate_outcome_gate") is False
            and admission.get("effect_assessment")
            == "descriptive_next_block_increment_then_final_library_test"
            and direct_accumulation_executor_markers
        ),
        "first_seven_blocks_generate_and_final_block_only_observes": (
            skill_accumulation.get("mode") == "group_evidence_global_playbook_evolution"
            and skill_accumulation.get("first_source_batch") == expected_batch_ids[0]
            and skill_accumulation.get("final_source_batch") == expected_batch_ids[-2]
            and skill_accumulation.get("final_batch_generates_skills") is False
            and learning_curve.get("incremental_effect_diagnostic", {}).get(
                "final_block_new_skill_budget"
            )
            == 0
        ),
        "exact_parent_increment_is_diagnostic_and_every_block_keeps_learning": (
            learning_curve.get("mode") == "prequential_fixed_shadow"
            and learning_curve.get("status") == "frozen_before_next_formal_run"
            and int(learning_curve.get("cases_per_block", 0)) == 16
            and learning_curve.get("no_pending_cohort_identity_shortcut") is True
            and learning_curve.get("evidence_role")
            == ("development_increment_diagnostic_and_next_teacher_direction_never_external_test")
            and "external_test" in str(learning_curve.get("evidence_role", ""))
            and learning_curve.get("incremental_effect_diagnostic", {}).get("comparator")
            == "exact_parent_library"
            and learning_curve.get("incremental_effect_diagnostic", {}).get("decision_role")
            == "descriptive_increment_measurement_before_teacher_never_skill_veto"
            and learning_curve.get("incremental_effect_diagnostic", {}).get(
                "single_block_effect_can_prune_or_rollback"
            )
            is False
            and learning_curve.get("incremental_effect_diagnostic", {}).get(
                "interval_uncertainty_alone_blocks_accumulation"
            )
            is False
            and learning_curve.get("incremental_effect_diagnostic", {}).get(
                "practical_effect_classifier"
            )
            == practical_gate_parent
            and "def _previous_block_skill_increment(" in executor_source
            and "def _prepare_current_library_identity_curve_point(" in executor_source
            and "no_new_increment_cumulative_library_identity" in executor_source
            and "observe_increment_continue_training" in executor_source
            and "retain_increment_for_cross_block_evolution" in executor_source
            and '"rejected_from_input_skill_ids": []' in executor_source
            and sentinels_ok
        ),
        "teacher_receives_global_exact_parent_feedback_without_outcome_gate": (
            "def prequential_input_library_feedback(" in executor_source
            and '"domain_diagnostics": domain_diagnostics' in executor_source
            and '"paired_process_evidence": [' in executor_source
            and "def add_document_transition_feedback(" in executor_source
            and '"input_library_prequential_feedback": library_feedback' in teacher_source
            and "不能定位时不得凭整库均值大改" in teacher_prompt
            and "精确父版本影子" in protocol_doc
            and "exact_parent_process_pairs" in teacher_sees
            and "exact_parent_document_field_diffs" in teacher_sees
        ),
        "final_B8_reports_performance_and_fails_closed_only_on_isolation": (
            learning_curve.get("final_cumulative_freeze_safeguard")
            == {
                "enabled": True,
                "status": "frozen_before_next_formal_run",
                "timing": ("after_B8_increment_diagnostic_before_training_complete"),
                "arm_freeze_timing": "before_B8_increment_diagnostic",
                "scope": "same_B8_accumulated_library_diagnostic",
                "claim_role": ("cumulative_library_diagnostic_not_independent_confirmatory_claim"),
                "comparator": "fixed_empty_library",
                "effect_direction": "selected_final_library_minus_empty_library",
                "endpoint_set": "primary_and_practical_safety_with_full_16_diagnostics",
                "retention_gate": practical_gate_empty,
                "advancement": {
                    "decision_rule": "primary_positive_point_estimate",
                    "endpoints": ["unique_disclosed_facts_per_question"],
                    "threshold": 0.0,
                },
                "isolation_required": True,
                "performance_nonpass_blocks_external": False,
                "isolation_failure_action": "fail_closed_on_intervention_contamination",
            }
            and "def _freeze_final_training_holdout_arms(" in executor_source
            and "def _ensure_final_training_holdout_safeguard(" in executor_source
            and "final_training_holdout_safeguard_disposition(" in executor_source
            and "same_B8_accumulated_library_diagnostic" in executor_source
            and "def final_training_holdout_intervention_isolation_report(" in isolation_source
            and "selected_library_is_empty" in isolation_source
            and "def cohort_pareto_disposition(" in learning_curve_source
        ),
        "maintenance_is_whole_library_every_two_blocks": (
            int(admission.get("maintenance_interval_blocks", 0)) == 2
            and int(skill_accumulation.get("maintenance_interval_blocks", 0)) == 2
            and "round_index % interval != 0" in executor_source
        ),
        "training_run_external_is_two_arm_mechanism_diagnostic": (
            diagnostic_arm_ids == ["control_no_library", "legal_skill_evolve"]
            and experiment.get("trajectory_sampling", {}).get("external_evaluation_seeds") == [42]
            and experiment.get("personas") == ["P_WD", "P_WS", "P_CS", "P_CD"]
            and "same_training_run_two_arm_mechanism_diagnostic_not_four_arm_main_table"
            in executor_source
            and '"publication_role": TRAINING_RUN_EXTERNAL_PUBLICATION_ROLE' in executor_source
            and "训练run自身的两臂报告只作机制诊断" in readme_source
        ),
        "four_arm_main_table_is_executable_with_one_shared_route": (
            main_table.get("status") == "benchmark_aware_four_arm_main_table_protocol_to_be_frozen"
            and main_table_arm_ids
            == [
                "control_no_library",
                "luna_direct",
                "expel_adapted",
                "legal_skill_evolve",
            ]
            and main_table_official.get("path")
            == experiment.get("data", {}).get("external_evaluation")
            and main_table_official.get("expected_sha256") == digest(external_path)
            and int(main_table_official.get("expected_cases", 0)) == len(external) == 30
            and main_table_official.get("personas") == experiment.get("personas")
            and int(main_table_official.get("dialogue_seed", -1)) == 42
            and main_table_router.get("input") == "public_opening_only"
            and main_table_router.get("shared_across_all_arms_personas_and_seeds") is True
            and main_table_router.get("never_uses_method_library") is True
            and len(set(main_table_router.get("domains", {}))) == 15
            and "general" in main_table_router.get("domains", {})
            and 'set(self.config["domain_router"]["domains"]) != set(ALLOWED_SKILL_DOMAINS)'
            in main_table_source
            and main_table_shared.get("main_experiment_config")
            == "configs/experiments/main_experiment.yaml"
            and main_table_reporting.get("evidence_role")
            == "benchmark_aware_locked_public_benchmark_reevaluation_not_pristine_confirmatory"
            and "OFFICIAL_ARM_IDS = (" in main_table_source
            and '"control_no_library"' in main_table_source
            and '"luna_direct"' in main_table_source
            and '"expel_adapted"' in main_table_source
            and '"legal_skill_evolve"' in main_table_source
            and "def _official_routes(" in main_table_source
            and '"official_fixed_domain_routes.json"' in main_table_source
            and "def _assert_completed_arm_shared_bindings(" in main_table_source
            and 'report.get("official_fixed_domain_routes_artifact") != route_artifact'
            in main_table_source
            and main_table_run_order_ok
        ),
        "four_arm_main_table_binds_frozen_ours_before_adapter_route_or_model": (
            main_table_bind_fails_closed
            and "def _validated_ours_training_source(" in main_table_source
            and "allow_external_data_access=False" in main_table_source
            and "source.validated_external_ready_training_freeze()" in main_table_source
            and "summary.schema_version != 6" in main_table_source
            and "summary.case_limit is not None" in main_table_source
            and "not active" in main_table_source
            and "active_skill_library_sha256" in main_table_source
            and "OURS_TRAINING_BINDING_MANIFEST" in main_table_source
            and 'commands.add_parser("bind-ours-training")' in main_table_cli_source
            and 'bind_ours.add_argument("--training-run-id", required=True)'
            in main_table_cli_source
            and "choices=OFFICIAL_ARM_IDS" in main_table_cli_source
        ),
        "external_report_declares_benchmark_aware_locked_reevaluation": (
            '"schema_version": 8' in executor_source
            and "benchmark_aware_locked_public_benchmark_reevaluation_" in executor_source
            and "same_training_run_two_arm_mechanism_diagnostic_not_four_arm_main_table"
            in executor_source
            and '"publication_role": TRAINING_RUN_EXTERNAL_PUBLICATION_ROLE' in executor_source
            and '"locked_external_protocol_integrity": protocol_integrity' in executor_source
            and '"primary_paired_contrast"' in executor_source
            and "def locked_external_protocol_integrity(" in executor_source
            and "def assert_locked_external_protocol_integrity(" in executor_source
            and '"confirmatory_protocol_integrity"' not in executor_source
            and '"primary_confirmatory_contrast"' not in executor_source
            and '"locked_external_test_protocol_valid"' in run_main_source
            and '"confirmatory_external_test_valid"' not in run_main_source
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
        "official_cn30_prior_aggregate_use_is_disclosed_and_excluded_from_learning": (
            len(external) == 30
            and experiment.get("data", {}).get("external_evaluation_status")
            == "frozen_public_benchmark_previously_evaluated_aggregate_aware"
            and external_policy.get("dlawbench_public_cn30")
            == "frozen_public_benchmark_previously_evaluated"
            and external_policy.get("current_payload_sha256") == digest(external_path)
            and external_policy.get("prior_frozen_library_evaluation_completed") is True
            and external_policy.get("aggregate_results_used_for_protocol_diagnosis") is True
            and external_policy.get("case_level_results_used_for_training_or_skill_selection")
            is False
            and external_policy.get("exposed_to_training_lawyer_or_skill_teacher") is False
            and external_policy.get("used_for_runtime_debugging") is True
            and external_policy.get("used_for_model_prompt_or_threshold_selection") is False
            and external_policy.get("evaluation_after_library_freeze_only") is True
            and external_policy.get("may_enter_training") is False
            and external_policy.get("may_enter_skill_teacher_context") is False
            and external_policy.get("claim_unseen_private_blind_test") is False
        ),
        "model_roles_preserve_intervention_and_information_boundaries": (
            lawyer_role.get("model_id") == "Qwen/Qwen3-8B"
            and "fixed_session_skill_documents" in lawyer_sees
            and {"client_belief_labels", "court_record", "evaluation_criteria"} <= lawyer_forbidden
            and teacher_role.get("model_id") == "gpt-5.6-luna"
            and {
                "complete_k_group_case_cards",
                "training_offline_scores",
                "current_global_playbook",
            }
            <= teacher_sees
            and {
                "future_block_hidden_labels",
                "external_benchmark_cases",
                "arm_test_results",
            }
            <= teacher_forbidden
            and external_policy.get("exposed_to_training_lawyer_or_skill_teacher") is False
            and "external_benchmark_cases" in teacher_forbidden
            and "court_record" in lawyer_forbidden
            and judge_role.get("model_id") == "openai/gpt-oss-20b"
            and {"skill_teacher_trace", "skill_identity", "arm_name"} <= judge_forbidden
            and "硬门" in role_rationales
            and "直接进入工作库" in role_rationales
            and "精确父库" in role_rationales
            and "下一未见块" in role_rationales
        ),
        "lawyer_receives_full_visible_history_and_compact_state": (
            len(visible_message_methods) == 1
            and "for question, answer in dialogue:" in visible_message_methods[0]
            and 'Message(role="assistant", content=question)' in visible_message_methods[0]
            and 'Message(role="user", content=answer)' in visible_message_methods[0]
            and "state_payload = policy_visible_state_projection(" in visible_message_methods[0]
            and "state.model_dump(mode=\"json\")" in visible_message_methods[0]
            and '"asked_targets": asked_targets' in experiment_schema_source
            and '"interactions": interactions' in experiment_schema_source
            and 'item.get("disclosed_fact_ids")' not in experiment_schema_source[
                experiment_schema_source.index("def policy_visible_state_projection(") :
                experiment_schema_source.index("def _policy_visible_facts_match(")
            ]
        ),
        "executable_behavior_defects_are_observed_not_intercepted": (
            "def blocking_policy_health_violations(" in stateful_policy_source
            and "policy_behavior_issue_is_soft(item)" in stateful_policy_source
            and "blocking = blocking_policy_health_violations(violations)" in runner_source
            and "if not blocking:" in runner_source
            and "return envelope, attempts, violations" in runner_source
            and 'if decision.final.action_type in {"ask", "clarify", "verify", "summarize"}:'
            in runner_source
            and "response, client_hash = client.respond(" in runner_source
            and "rendered_question=rendered" in runner_source
            and 'decision.final.action_type in {"final", "abstain"}' in runner_source
            and "finalize_horizon_verdict(" in runner_source
            and "preinteraction_policy_repair_violations" not in runner_source
        ),
        "emergency_horizon_is_scoreable_teacher_evidence_not_integrity_failure": (
            len(trajectory_health_issue_functions) == 1
            and '"max_turns_forced_memo"' not in trajectory_health_issue_functions[0]
            and '"emergency_turn_ceiling_reached"'
            not in trajectory_health_issue_functions[0]
            and "emergency_horizon_trajectories = [" in trajectory_health_source
            and 'if trajectory.status == "max_turns_forced_memo"'
            in trajectory_health_source
            and '"terminal_status": getattr(trajectory, "status", "unknown")'
            in group_evidence_source
            and "安全上限下真实、可评分的策略失败" in protocol_doc
            and "保留全部问答与指标并进入教师证据" in evaluation_doc
        ),
        "training_policy_does_not_heat_heads_to_manufacture_contrasts": (
            float(lawyer_role.get("training_temperature", -1)) == 0.7
            and float(lawyer_role.get("paired_evaluation_temperature", -1)) <= 0.2
            and "training_target_selection_temperature" not in lawyer_role
            and "training_continuation_temperature" not in lawyer_role
            and "paired_target_selection_temperature" not in lawyer_role
            and "paired_continuation_temperature" not in lawyer_role
        ),
        "lawyer_uses_one_complete_action_without_retired_factored_heads": (
            "two_stage_target_policy" not in runner_source
            and "two_stage_target_policy" not in executor_source
            and "_generate_target_selection" not in runner_source
            and "_generate_continuation_decision" not in runner_source
            and "consultation_continuation_gate_zh.txt" not in executor_source
            and 'response_schema_name="legal_skill_guard_policy_action"' in runner_source
            and action_schema_source.index('reason: str = ""')
            < action_schema_source.index("action_type: ActionType")
            and 'action_schema["properties"]["reason"]["minLength"] = 8' in runner_source
        ),
        "client_routing_requires_positive_target_alignment_before_canonicalization": (
            "def action_target_alignment_confirmed(" in stateful_policy_source
            and "attribute" in stateful_policy_source
            and "substantive event/object anchor" in stateful_policy_source
            and "if label and action_target_alignment_confirmed(action, label):" in runner_source
            and "return rendered_question.strip()" in runner_source
        ),
        "runtime_fact_identity_cannot_launder_visible_or_exhausted_targets": (
            "aligned_visible_targets" in stateful_policy_source
            and "len(aligned_visible_targets) == 1" in stateful_policy_source
            and "def action_target_identity_confirmed(" in stateful_policy_source
            and "action_target_identity_confirmed(action, fact.label)"
            in stateful_policy_source
            and "_action_surface_fact_identity_confirmed(action, fact.label)"
            in stateful_policy_source
            and "_fact_identity_surfaces_equivalent" in stateful_policy_source
            and "new_fact_target_duplicates_visible_target:"
            in stateful_policy_source
            and 'fact.status != "irrelevant"' in stateful_policy_source
            and "if target and target in projected:" in stateful_policy_source
        ),
        "non_llm_roles_name_direct_increment_diagnostic_and_maintenance": (
            "embedded_next_block_skill_gate" not in non_llm_components
            and "group_evidence_global_playbook_admission" in non_llm_components
            and "complete_k_group_map_reduce_packaging" in non_llm_components
            and "prequential_exact_parent_increment_diagnostic" in non_llm_components
            and "final_B8_cumulative_freeze_safeguard" in non_llm_components
            and "working_library_maintenance" in non_llm_components
        ),
        "skills_are_fixed_prompt_documents_not_runtime_actions": (
            "render_skill_memory" in code_sources["legal_skill_guard/experiment/runner.py"]
            and "单一全局playbook直接注入" in readme_source
            and all(path.name != "consultation_planner_zh.txt" for path in prompt_paths)
            and "target_selection_rule" not in runner_source
            and "applicability_cues" in memory_source
            and "question_guidance" in memory_source
            and "candidate_action" not in memory_source
            and 'SkillStatus = Literal["candidate", "active", "rejected", "deprecated"]'
            in code_sources["legal_skill_guard/schemas/skill.py"]
        ),
        "ours_global_playbook_has_no_method_specific_domain_router": (
            "public_opening_skill_domain_router" not in roles.get("roles", {})
            and "_external_public_opening_domain_routes" not in executor_source
            and "external_public_opening_domain_routes.json" not in executor_source
            and "official_fixed_domain_router" in roles.get("roles", {})
            and "def _official_routes(" in main_table_source
        ),
        "retired_investigation_planner_is_production_unreachable": (
            len(runner_init_methods) == 1
            and len(runner_run_methods) == 1
            and "planner_prompt_path" not in runner_init_methods[0]
            and "planner_client: GenerativeClient" not in runner_init_methods[0]
            and "planner_generation: GenerationConfig" not in runner_init_methods[0]
            and "_generate_investigation_plan(" not in runner_run_methods[0]
            and "render_planner_skill_memory(" not in runner_run_methods[0]
            and "planner_exposed_skill_ids: list[str] = []" in runner_run_methods[0]
            and "EMPTY_PLANNER_SKILL_MEMORY.encode" in runner_run_methods[0]
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
            and "现役真源" in protocol_doc
            and "自建128案冻结为8块×16案" in protocol_doc
            and "直接进入每轮Qwen的完整行动调用" in protocol_doc
            and "直接进入工作库" in protocol_doc
            and "第8块教师预算为0" in protocol_doc
            and "单块效果不拒收或回滚" in protocol_doc
            and "共享、非绑定的事实议程" in protocol_doc
            and "此前完整问答历史" in protocol_doc
            and "低质量的律师行为" in protocol_doc
            and "必须真实送达客户" in protocol_doc
            and "应急horizon" in protocol_doc
            and "不是需排除或重采样的执行完整性故障" in protocol_doc
            and "不设独立终止端点" in evaluation_doc
            and "Playbook准入" in evaluation_doc
            and "主指标" in evaluation_doc
            and "gpt-5.6-luna" in roles_doc
            and "gpt-oss-20b" in roles_doc
            and "Qwen3-8B" in roles_doc
            and "8块×16案" in execution_doc
            and "精确局部编辑" in execution_doc
            and "--run-id <fresh-run-id>" in execution_doc
            and "final_training_holdout_arms_frozen.json" in artifact_doc
            and "final_training_holdout_disposition.json" in artifact_doc
            and "benchmark-aware" in readme_source
            and "docs/architecture/current_research_protocol.md" in readme_source
            and "docs/architecture/evaluation_contract.md" in readme_source
            and "docs/architecture/artifact_naming.md" in readme_source
            and "docs/operations/main_experiment_execution.md" in readme_source
        ),
        "retired_top_level_blueprint_is_explicitly_non_executable": blueprint_marker_ok,
    }

    maintenance_blocks = [
        index
        for index in range(1, len(batches) + 1)
        if index % int(admission.get("maintenance_interval_blocks", 1)) == 0
    ]
    final_source_batch = str(skill_accumulation.get("final_source_batch") or "")
    source_block_count = (
        batch_ids.index(final_source_batch) + 1 if final_source_batch in batch_ids else 0
    )
    maximum_teacher_calls = source_block_count * int(
        execution.get("teacher_call_budget_per_round", 0)
    )
    checks_passed = all(checks.values())
    protocol_hash_paths = {
        **paths,
        **{f"prompt_{path.stem}": path for path in prompt_paths if path != paths["teacher_prompt"]},
        **{
            f"document_{Path(relative).stem}": root / relative for relative in ACTIVE_DOCUMENT_PATHS
        },
    }
    return {
        "schema_version": 6,
        "status": (
            "static_current_protocol_passed_gpu_requalification_required"
            if checks_passed
            else "static_current_protocol_failed"
        ),
        "claim_boundary": {
            "static_data_and_execution_contract_audited": checks_passed,
            "gpu_model_chain_qualified": "not_assessed",
            "formal_training_completed": "not_assessed",
            "official_external_evaluation_completed": "not_assessed",
            "historical_cn30_aggregate_observed": True,
            "cn30_pristine_confirmatory_claim_allowed": False,
            "cn30_exposed_to_training_lawyer_or_teacher": False,
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
            "maximum_new_skills": source_block_count
            * int(execution.get("maximum_new_skills_per_block", 0)),
            "per_candidate_validation_sessions": 0,
            "prequential_shadow_sessions_upper_bound": (max(0, len(batches) - 1) + 1)
            * int(learning_curve.get("cases_per_block", 0)),
            "final_holdout_empty_shadow_sessions": int(learning_curve.get("cases_per_block", 0)),
            "maintenance_blocks": maintenance_blocks,
            "final_block_generates_skills": skill_accumulation.get("final_batch_generates_skills"),
            "external_cases": len(external),
            "external_personas": len(experiment.get("personas", [])),
            "training_run_diagnostic_arms": diagnostic_arm_ids,
            "external_arms": main_table_arm_ids,
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
            "source-grounded direct-accumulation protocol: K=4 uses a predeclared four-way "
            "exact visible-input fork plus one arm-invariant, opening-only, non-binding agenda. "
            "The lawyer still receives the complete visible dialogue and compact state, and every "
            "attribution-healthy case becomes one complete "
            "group-evidence card. Two disjoint map calls extract source-bound modes and one reduce "
            "call applies bounded exact edits to a single global playbook. Hard trust gates bind "
            "every edit to immutable source artifacts; tied groups can only support failure modes. "
            "The next unseen block compares the new playbook version with its exact parent before "
            "any teacher call. F/Q, practical safety, exposure, and uncertainty are prequential "
            "learning diagnostics and "
            "teacher direction; a single block never rolls back the working library or excludes "
            "that block from teacher evidence. B8 additionally freezes comparison arms before its "
            "increment diagnostic; performance nonpass is reported, while only "
            "intervention-isolation failure blocks the accumulated-library freeze. "
            "The training-run CN30 entry is only a two-arm Ours-versus-empty mechanism "
            "diagnostic. The paper main table instead requires one four-arm controller, one "
            "method-independent fixed route artifact, and an immutable external-ready Ours "
            "training-source binding made before any CN30 adapter, route, or model call "
            "(byte-hash verification remains separately disclosed). Historical method-level "
            "CN30 aggregates have already been observed for protocol diagnosis, so a later "
            "locked CN30 run is benchmark-aware rather than a pristine confirmatory test; "
            "CN30 cases and outcomes remain excluded from the training lawyer and Luna "
            "teacher. Bounded same-model action repair is limited to structural, identity, "
            "privacy, and leakage failures. Executable low-quality questions reach the client "
            "and retain their real question cost, response, reward, warnings, and teacher "
            "evidence; they are neither hidden repairs nor distinct termination endpoints. "
            "Only lawyer-authored final/abstain actions or the hidden emergency horizon end a "
            "session. Reaching that shared safety ceiling is a real, scoreable policy failure "
            "that remains in teacher evidence; it is neither healthy success nor an execution-"
            "integrity defect. Passing is not evidence of runtime qualification, "
            "learned improvement, "
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
