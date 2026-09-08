#!/usr/bin/env python3
"""Fail-closed CPU audit of the publication-facing 128-case protocol.

This script deliberately distinguishes static protocol readiness from the
run-bound GPU/model qualifications.  It never treats a historical runtime
artifact as evidence for the current implementation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

from legal_skill_guard.skills.loader import ALLOWED_SKILL_DOMAINS

ROOT = Path(__file__).resolve().parents[1]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "reports/artifacts/paper_protocol_readiness.json",
    )
    args = parser.parse_args()

    experiment_path = ROOT / "configs/experiments/main_experiment.yaml"
    corpus_config_path = ROOT / "configs/data/main_corpus.yaml"
    batch_path = ROOT / "configs/data/main_training_batches.yaml"
    roles_path = ROOT / "configs/models/roles.yaml"
    prompt_path = ROOT / "configs/prompts/skill_teacher_zh.txt"
    executor_path = ROOT / "legal_skill_guard/experiment/executor.py"
    runner_path = ROOT / "legal_skill_guard/experiment/runner.py"
    memory_path = ROOT / "legal_skill_guard/skills/memory.py"
    skill_schema_path = ROOT / "legal_skill_guard/schemas/skill.py"
    teacher_path = ROOT / "legal_skill_guard/evolution/teacher.py"
    diagnosis_path = ROOT / "legal_skill_guard/evolution/diagnosis.py"
    intervention_path = ROOT / "legal_skill_guard/experiment/intervention_isolation.py"
    productivity_path = ROOT / "legal_skill_guard/experiment/batch_productivity.py"
    client_response_path = ROOT / "legal_skill_guard/environment/client_response.py"
    state_manager_path = ROOT / "legal_skill_guard/agent/state_manager.py"
    visibility_path = ROOT / "legal_skill_guard/data_visibility.py"
    visibility_config_path = ROOT / "configs/data/visibility.yaml"
    retired_engine_path = ROOT / "legal_skill_guard/skills/engine.py"
    acceptance_path = ROOT / "legal_skill_guard/evolution/acceptance.py"
    readme_path = ROOT / "README.md"
    execution_doc_path = ROOT / "docs/operations/main_experiment_execution.md"
    retired_pretraining_paths = (
        ROOT / "scripts/probe_investigation_plans.py",
        ROOT / "scripts/probe_main_dialogues.py",
        ROOT / "scripts/probe_training_sampling_qualification.py",
        ROOT / "scripts/audit_investigation_plan_semantics.py",
        ROOT / "legal_skill_guard/evaluation/investigation_plan_audit.py",
        ROOT / "legal_skill_guard/experiment/sampling_qualification.py",
    )

    experiment = yaml.safe_load(experiment_path.read_text(encoding="utf-8"))
    corpus_config = yaml.safe_load(corpus_config_path.read_text(encoding="utf-8"))
    batch_plan = yaml.safe_load(batch_path.read_text(encoding="utf-8"))
    roles = yaml.safe_load(roles_path.read_text(encoding="utf-8"))
    teacher_prompt = prompt_path.read_text(encoding="utf-8")
    executor_source = executor_path.read_text(encoding="utf-8")
    runner_source = runner_path.read_text(encoding="utf-8")
    memory_source = memory_path.read_text(encoding="utf-8")
    skill_schema_source = skill_schema_path.read_text(encoding="utf-8")
    teacher_source = teacher_path.read_text(encoding="utf-8")
    diagnosis_source = diagnosis_path.read_text(encoding="utf-8")
    intervention_source = intervention_path.read_text(encoding="utf-8")
    productivity_source = productivity_path.read_text(encoding="utf-8")
    client_response_source = client_response_path.read_text(encoding="utf-8")
    state_manager_source = state_manager_path.read_text(encoding="utf-8")
    visibility_source = visibility_path.read_text(encoding="utf-8")
    visibility_config = yaml.safe_load(visibility_config_path.read_text(encoding="utf-8"))
    acceptance_source = acceptance_path.read_text(encoding="utf-8")
    readme_source = readme_path.read_text(encoding="utf-8")
    execution_doc_source = execution_doc_path.read_text(encoding="utf-8")

    core_path = ROOT / corpus_config["core_cases"]
    provenance_path = ROOT / corpus_config["provenance"]
    selection_path = ROOT / corpus_config["selection_manifest"]
    external_path = ROOT / experiment["data"]["external_evaluation"]
    core = load_jsonl(core_path)
    provenance = load_jsonl(provenance_path)
    external = load_jsonl(external_path)
    core_ids = [str(case["id"]) for case in core]
    provenance_ids = [str(case["id"]) for case in provenance]
    batches = list(batch_plan.get("batches", []))
    batch_ids = [str(batch.get("batch_id")) for batch in batches]
    flattened_ids = [str(case_id) for batch in batches for case_id in batch.get("case_ids", [])]
    expected_case_ids = [f"lsg_cn_{index:04d}" for index in range(1, 129)]
    expected_batch_ids = [f"training_batch_{index:02d}" for index in range(1, 9)]

    quality_path = ROOT / corpus_config["quality_report"]
    casewise_path = ROOT / corpus_config["casewise_quality_report"]
    contamination_path = ROOT / corpus_config["contamination_report"]
    batch_report_path = ROOT / corpus_config["training_batch_report"]
    opening_boundary_path = ROOT / corpus_config["opening_information_boundary_report"]
    opening_adjudications_path = (
        ROOT / "configs/qualification/opening_information_boundary_adjudications.yaml"
    )
    quality = load_json(quality_path)
    casewise = load_json(casewise_path)
    contamination = load_json(contamination_path)
    batch_report = load_json(batch_report_path)
    opening_boundary = load_json(opening_boundary_path)
    corpus_hashes = corpus_config["hashes"]

    domains = {str(item["annotation"]["legal_domain"]) for item in provenance}
    persona_counts = {
        str(batch["batch_id"]): Counter(batch.get("persona_assignment", {}).values())
        for batch in batches
    }
    prospective_links = [batch.get("prospective_validation_for") for batch in batches]
    expected_links: list[str | None] = [None] + expected_batch_ids[:-1]
    execution = experiment["execution"]
    prospective = experiment["prospective_validation"]
    learning_curve = experiment["learning_curve"]
    sentinel_by_block = learning_curve.get("sentinel_case_ids_by_block", {})
    domain_by_case = {
        str(item["id"]): str(item["annotation"]["legal_domain"])
        for item in provenance
    }

    checks: dict[str, bool] = {
        "experiment_protocol_is_prospective_128": (
            experiment.get("status") == "prompt_memory_protocol_gpu_requalification_required"
            and int(execution.get("evolution_rounds", 0)) == 8
        ),
        "corpus_declares_128_train_and_no_fixed_validation": (
            corpus_config.get("status") == "frozen_128_cpu_audited_runtime_requalification_required"
            and int(corpus_config.get("formal_cases", 0)) == 128
            and corpus_config.get("formal_split") == {"train": 128}
            and int(corpus_config.get("fixed_internal_validation_cases", -1)) == 0
        ),
        "core_and_provenance_are_canonical_128": (
            core_ids == expected_case_ids
            and provenance_ids == expected_case_ids
            and len(set(core_ids)) == 128
            and all(item.get("split") == "train" for item in provenance)
        ),
        "all_frozen_input_hashes_match": (
            digest(core_path) == corpus_hashes.get("core_sha256")
            and digest(provenance_path) == corpus_hashes.get("provenance_sha256")
            and digest(selection_path) == corpus_hashes.get("selection_sha256")
            and digest(batch_path) == corpus_hashes.get("training_batches_sha256")
        ),
        "batch_plan_is_exact_8_by_16_partition": (
            batch_plan.get("schema_version") == 2
            and batch_ids == expected_batch_ids
            and all(len(batch.get("case_ids", [])) == 16 for batch in batches)
            and len(flattened_ids) == len(set(flattened_ids)) == 128
            and set(flattened_ids) == set(core_ids)
        ),
        "prospective_links_are_adjacent_and_complete": (
            prospective_links == expected_links
            and batch_plan.get("candidate_validation", {}).get("mode")
            == "embedded_next_training_block"
            and batch_plan.get("candidate_validation", {}).get("shared_control_per_case") is True
            and batch_plan.get("candidate_validation", {}).get("final_batch_candidate_policy")
            == "no_candidate_generation"
        ),
        "one_balanced_predeclared_persona_per_case": all(
            set(batch.get("persona_assignment", {})) == set(batch.get("case_ids", []))
            and persona_counts[str(batch["batch_id"])]
            == Counter({"P_WD": 4, "P_WS": 4, "P_CS": 4, "P_CD": 4})
            for batch in batches
        ),
        "all_domains_supported_by_skill_runtime": (
            domains <= ALLOWED_SKILL_DOMAINS and domains | {"general"} == ALLOWED_SKILL_DOMAINS
        ),
        "prospective_gate_configuration_is_complete": (
            prospective.get("mode") == "embedded_next_training_block"
            and prospective.get("fixed_pool") is False
            and prospective.get("paired") is True
            and prospective.get("shared_control_per_case") is True
            and prospective.get("require_no_leakage") is True
            and prospective.get("require_no_safety_regression") is True
            and int(prospective.get("maximum_validation_blocks", 0)) == 3
            and int(prospective.get("minimum_exposed_cases", 0)) >= 2
            and int(prospective.get("minimum_exposed_domains", 0)) >= 2
            and int(execution.get("provisional_candidate_budget_per_block", 0))
            >= int(execution.get("teacher_call_budget_per_round", 0))
            and int(execution.get("maximum_concurrent_provisional_candidates", 0))
            >= int(execution.get("provisional_candidate_budget_per_block", 0))
            * int(prospective.get("maximum_validation_blocks", 0))
        ),
        "trajectory_matrix_and_seed_contract_are_frozen": (
            int(experiment["trajectory_sampling"].get("group_size", 0)) == 4
            and experiment["trajectory_sampling"].get("training_group_seeds") == [42]
            and experiment["trajectory_sampling"].get("external_evaluation_seeds") == [42]
        ),
        "primary_endpoint_matches_fact_efficiency_claim": (
            experiment.get("evaluation", {}).get("primary_endpoint")
            == "unique_disclosed_facts_per_question"
            and {
                "unique_disclosed_facts",
                "fact_coverage",
                "resolution",
            }
            <= set(experiment.get("evaluation", {}).get("secondary_endpoints", []))
        ),
        "prequential_learning_curve_is_outcome_blind_and_balanced": (
            learning_curve.get("mode") == "prequential_fixed_shadow"
            and learning_curve.get("status") == "frozen_before_next_formal_run"
            and int(learning_curve.get("cases_per_block", 0)) == 8
            and int(learning_curve.get("bootstrap_samples", 0)) >= 1000
            and learning_curve.get("empty_library_identity_shortcut") is True
            and "never_teacher" in str(learning_curve.get("evidence_role", ""))
            and set(sentinel_by_block) == set(expected_batch_ids)
            and all(
                len(sentinel_by_block.get(batch_id, []))
                == len(set(sentinel_by_block.get(batch_id, [])))
                == 8
                and set(sentinel_by_block.get(batch_id, []))
                <= set(batches[index].get("case_ids", []))
                and Counter(
                    batches[index]["persona_assignment"][case_id]
                    for case_id in sentinel_by_block.get(batch_id, [])
                )
                == Counter({"P_WD": 2, "P_WS": 2, "P_CS": 2, "P_CD": 2})
                and len(
                    {
                        domain_by_case[case_id]
                        for case_id in sentinel_by_block.get(batch_id, [])
                    }
                )
                == 8
                for index, batch_id in enumerate(expected_batch_ids)
            )
        ),
        "teacher_prompt_obeys_future_data_boundary": (
            "provisional" in teacher_prompt
            and ("下一未见" in teacher_prompt or "后续连续未见" in teacher_prompt)
            and "固定18" not in teacher_prompt
            and "验收池" not in teacher_prompt
        ),
        "executor_has_only_current_candidate_lifecycle": (
            "validate_preceding_block_candidates" in executor_source
            and "validate_provisional_candidate" in executor_source
            and "embedded candidate evaluation lacks one shared control per case" in executor_source
            and 'Literal["ACCEPT", "REJECT", "DEFER"]' in acceptance_source
            and "maximum_validation_blocks" in executor_source
            and "prior_audit_artifacts" in executor_source
            and "provisionals_ready" in executor_source
            and "internal_acceptance_split" not in executor_source
            and "candidate_audit_budget_per_round" not in executor_source
            and "validation_pair_seeds" not in executor_source
        ),
        "retired_pretraining_probe_surface_is_absent": (
            "readiness_validation" not in experiment
            and not any(path.exists() for path in retired_pretraining_paths)
            and "investigation_plan_probe" not in executor_source
            and "dialogue_contract_probe" not in executor_source
            and "training_sampling_qualification" not in executor_source
        ),
        "formal_scoring_binds_full_prompt_memory_to_executor_library": (
            "def skill_memory_contract_report(" in intervention_source
            and "expected_memory=expected_memory" in intervention_source
            and "expected_skill_libraries=self._training_skill_memory_contract(" in executor_source
            and "expected_skill_libraries={empty_hash: []}" in executor_source
            and executor_source.count("expected_skill_libraries={") >= 3
            and "executor-owned skill memory contract failed before semantic scoring"
            in executor_source
        ),
        "client_projection_excludes_evaluator_gap_labels": (
            'for key in ("fact_id", "client_belief")' in visibility_source
            and "facts.gap_type"
            not in visibility_config["client_simulator_prompt"].get("allow", [])
            and "facts.gap_type"
            in visibility_config["client_simulator_prompt"].get("deny", [])
        ),
        "client_route_contract_failure_cannot_close_target": (
            "if selection is None:" in client_response_source
            and "self.last_route_guard_violations = last_guard_violations"
            in client_response_source
            and "self.last_route_passed = False" in client_response_source
            and 'self.last_response_kind = "contract_fallback"' in client_response_source
            and "route_contract_failed = response_kind == \"contract_fallback\""
            in state_manager_source
            and "not route_contract_failed" in state_manager_source
        ),
        "teacher_lifecycle_matches_create_only_executor": (
            'ProposalType = Literal["CREATE", "NOOP"]' in diagnosis_source
            and "CREATE、REFINE" not in teacher_prompt
            and "DEPRECATE 候选" not in teacher_prompt
        ),
        "question_formulation_is_a_learnable_policy_difference": (
            executor_source.count("normalize_question(action.content)") >= 1
            and teacher_source.count("normalize_question(action.content)") >= 1
            and 'return "question_formulation"' in teacher_source
            and '"expected_information": action.expected_information' in teacher_source
        ),
        "candidate_exposure_rotation_and_pairwise_safety_are_fail_closed": (
            "candidate assignment block_index must be non-negative" in executor_source
            and executor_source.count("block_index=round_index - 1") >= 2
            and "block_index=validation_round_index - 1" in executor_source
            and "candidate_validation_ages" in executor_source
            and "def age_priority" in executor_source
            and "sorted({ages[item.skill_id] for item in items}, reverse=True)"
            in executor_source
            and "candidate_wide_health_passed" in executor_source
            and "matrix_coverage_passed" in executor_source
            and "candidate_contract_health_passed" in executor_source
            and "candidate_matrix_coverage_passed" in executor_source
            and "attribution_issue_codes_are_local_recovery" in executor_source
            and "candidate pair health report lacks complete issue provenance"
            in executor_source
            and "insufficient_healthy_pair_fraction_before_outcomes" in executor_source
            and "safety_regression = any(" in acceptance_source
            and "for item in exposed" in acceptance_source
        ),
        "deferred_candidates_preserve_fresh_nomination_capacity": (
            execution.get("provisional_candidate_budget_per_block") == 2
            and execution.get("maximum_concurrent_provisional_candidates") == 6
            and "def fresh_candidate_nomination_slots" in executor_source
            and "carryover_count=len(deferred_candidates)" in executor_source
            and "candidate_budget=candidate_nomination_slots" in executor_source
        ),
        "weak_baseline_productivity_reaches_teacher_evidence": (
            execution.get("provisional_candidate_budget_per_block") == 2
            and experiment.get("training_batch_productivity_review", {}).get("action")
            == "record_diagnostic_and_continue_to_teacher_evidence"
            and "continue_with_low_productivity_review_flag" in productivity_source
            and "stop before semantic scoring or Luna" not in executor_source
        ),
        "same_round_teacher_calls_see_prior_staged_candidates": (
            "existing.append(candidate)" in executor_source
            and "existing_by_id[candidate.skill_id] = candidate" in executor_source
        ),
        "candidate_identity_binds_valid_teacher_response_hash": (
            "def _teacher_proposal_matches_candidate" in executor_source
            and "proposal.usable_candidate" in executor_source
            and "candidate_provenance.diagnosis_hash == proposal.response_sha256"
            in executor_source
        ),
        "skills_are_one_prompt_memory_intervention": (
            "render_skill_memory" in runner_source
            and "SkillEngine" not in runner_source
            and "engine.apply" not in runner_source
            and "fixed session skill memory" in runner_source
            and "applicability_cues" in memory_source
            and "question_guidance" in memory_source
            and "recommended_action_pattern" not in memory_source
            and "candidate_action" not in memory_source
            and "SourceWitness" in teacher_source
            and "SourceReplayEngine" not in teacher_source
            and not retired_engine_path.exists()
            and 'allowed_methods = {"candidate_without", "training_policy_sample"}'
            in executor_source
            and "external_test_skill_library_isolation.json" in executor_source
            and [item.get("arm_id") for item in experiment.get("comparison_arms", [])]
            == [
                "control_no_library",
                "ungated_source_grounded_skills",
                "legal_skill_guard",
            ]
        ),
        "prompt_skill_memory_has_bounded_admission_capacity": (
            "MAX_POLICY_SKILL_DOCUMENT_CHARACTERS" in memory_source
            and "MAX_SESSION_SKILL_MEMORY_CHARACTERS" in memory_source
            and "skill_memory_capacity_issues" in memory_source
            and "admit_active_skills_by_prompt_capacity" in memory_source
            and "admit_active_skills_by_prompt_capacity" in executor_source
            and "prompt_capacity_rejections" in executor_source
            and "source_round_then_grounding_report_order_outcome_blind_first_fit"
            in executor_source
            and "max_length=240" in skill_schema_source
        ),
        "quality_report_is_current_and_passed": (
            quality.get("status") == "passed"
            and quality.get("cases") == 128
            and quality.get("core_sha256") == digest(core_path)
            and quality.get("provenance_sha256") == digest(provenance_path)
            and corpus_hashes.get("deterministic_quality_report_sha256") == digest(quality_path)
        ),
        "casewise_report_is_current_and_passed": (
            casewise.get("status") == "passed"
            and casewise.get("counts", {}).get("cases") == 128
            and casewise.get("core_sha256") == digest(core_path)
            and casewise.get("provenance_sha256") == digest(provenance_path)
            and casewise.get("selection_sha256") == digest(selection_path)
            and casewise.get("edge_integrity", {}).get("canonical_contiguous_case_ids") is True
            and not casewise.get("edge_integrity", {}).get("fact_id_failures")
            and not casewise.get("edge_integrity", {}).get("empty_or_whitespace_fields")
            and not casewise.get("edge_integrity", {}).get("within_case_duplicate_fields")
            and not casewise.get("edge_integrity", {}).get("case_digest_failures")
            and not casewise.get("edge_integrity", {}).get("unsupported_fact_ids")
            and not casewise.get("edge_integrity", {}).get("source_authority_failures")
            and not casewise.get("edge_integrity", {}).get("authoring_identity_failures")
            and corpus_hashes.get("casewise_quality_report_sha256") == digest(casewise_path)
        ),
        "contamination_report_is_current_and_passed": (
            contamination.get("status") == "passed"
            and contamination.get("formal_core_cases") == 128
            and contamination.get("external_cases") == 30
            and contamination.get("formal_core_sha256") == digest(core_path)
            and contamination.get("selection_sha256") == digest(selection_path)
            and not contamination.get("exact_50_character_overlaps")
            and not contamination.get("external_case_ids_in_behavior_assets")
            and corpus_hashes.get("contamination_report_sha256") == digest(contamination_path)
        ),
        "batch_balance_report_is_current_and_passed": (
            batch_report.get("status") == "passed"
            and batch_report.get("design") == "balanced_sequential_embedded_skill_blocks"
            and batch_report.get("training", {}).get("cases") == 128
            and len(batch_report.get("batches", {})) == 8
            and corpus_hashes.get("training_batch_report_sha256") == digest(batch_report_path)
        ),
        "opening_boundary_is_researcher_adjudicated_and_current": (
            opening_boundary.get("status") == "passed"
            and opening_boundary.get("case_count") == 128
            and opening_boundary.get("fact_count") == 852
            and opening_boundary.get("data_sha256") == digest(core_path)
            and opening_boundary.get("adjudications_sha256")
            == digest(opening_adjudications_path)
            and opening_boundary.get("adjudication_corpus_matches") is True
            and opening_boundary.get("unreviewed_flag_count") == 0
            and opening_boundary.get("adjudicated_leakage_count") == 0
            and not opening_boundary.get("stale_adjudications")
            and opening_boundary.get("flagged_count")
            == len(opening_boundary.get("flagged", []))
            and corpus_hashes.get("opening_information_boundary_report_sha256")
            == digest(opening_boundary_path)
        ),
        "official_cn30_is_frozen_held_out_and_not_used_for_debugging": (
            len(external) == 30
            and experiment["data"].get("training_split") == "train"
            and experiment["data"].get("external_evaluation_status")
            == "held_out_frozen_test_not_used_for_debugging"
            and corpus_config.get("external_benchmark_policy", {}).get(
                "dlawbench_public_cn30"
            )
            == "held_out_frozen_external_test"
            and corpus_config.get("external_benchmark_policy", {}).get(
                "current_payload_sha256"
            )
            == digest(external_path)
            and corpus_config.get("external_benchmark_policy", {}).get(
                "used_for_runtime_debugging"
            )
            is False
            and corpus_config.get("external_benchmark_policy", {}).get(
                "used_for_model_prompt_or_threshold_selection"
            )
            is False
            and corpus_config.get("external_benchmark_policy", {}).get(
                "evaluation_after_library_freeze_only"
            )
            is True
            and corpus_config.get("external_benchmark_policy", {}).get("may_enter_training")
            is False
            and corpus_config.get("external_benchmark_policy", {}).get(
                "may_enter_skill_teacher_context"
            )
            is False
        ),
        "roles_are_frozen_for_same_protocol": (
            roles.get("status") == "static_role_assignment_frozen_gpu_requalification_required"
            and "embedded_next_block_skill_gate" in roles.get("non_llm_components", [])
        ),
        "gpu_start_sequence_requires_current_component_qualifications": all(
            document.find("scripts/start_main_model_services.sh")
            < document.find("scripts/qualify_client_simulator.py --run-id <run-id>")
            < document.find("scripts/qualify_local_judge.py")
            < document.find(
                "scripts/run_main_experiment.py --run-id <run-id> preflight --probe-codex"
            )
            < document.find("--fresh --confirm I_CONFIRM_MAIN_TRAINING")
            for document in (readme_source, execution_doc_source)
        ),
    }

    runtime_requirements = list(corpus_config.get("requalification_requirements", []))
    report = {
        "schema_version": 2,
        "status": (
            "static_protocol_passed_gpu_requalification_required"
            if all(checks.values())
            else "static_protocol_failed"
        ),
        "claim_boundary": {
            "static_data_and_execution_contract_audited": all(checks.values()),
            "gpu_model_chain_qualified": False,
            "formal_training_completed": False,
            "official_external_evaluation_completed": False,
        },
        "design": {
            "cases": len(core),
            "blocks": len(batches),
            "cases_per_block": [len(batch.get("case_ids", [])) for batch in batches],
            "training_trajectories": len(core)
            * int(experiment["trajectory_sampling"]["group_size"]),
            "candidate_source_blocks": 7,
            "embedded_candidate_evaluation_blocks": 7,
            "maximum_provisional_candidates": 7
            * int(execution["provisional_candidate_budget_per_block"]),
            "maximum_concurrent_provisional_candidates": int(
                execution["maximum_concurrent_provisional_candidates"]
            ),
            "additional_candidate_validation_sessions": 0,
            "maximum_additional_learning_curve_shadow_sessions": (
                (len(batches) - 1) * int(learning_curve["cases_per_block"])
            ),
            "learning_curve_sentinels_per_block": int(learning_curve["cases_per_block"]),
            "shared_control_sessions_per_candidate_block": 16,
            "official_external_cases": len(external),
            "domains": sorted(domains),
        },
        "checks": checks,
        "failed_checks": sorted(name for name, passed in checks.items() if not passed),
        "runtime_requalification_required": runtime_requirements,
        "protocol_hashes": {
            "experiment": digest(experiment_path),
            "roles": digest(roles_path),
            "corpus_config": digest(corpus_config_path),
            "batch_plan": digest(batch_path),
            "teacher_prompt": digest(prompt_path),
            "executor": digest(executor_path),
            "acceptance": digest(acceptance_path),
            "runner": digest(runner_path),
            "skill_memory": digest(memory_path),
            "teacher": digest(teacher_path),
            "diagnosis": digest(diagnosis_path),
            "intervention_isolation": digest(intervention_path),
            "batch_productivity": digest(productivity_path),
            "client_response": digest(client_response_path),
            "state_manager": digest(state_manager_path),
            "data_visibility": digest(visibility_path),
            "visibility_config": digest(visibility_config_path),
            "opening_boundary_report": digest(opening_boundary_path),
            "opening_boundary_adjudications": digest(opening_adjudications_path),
            "readme": digest(readme_path),
            "execution_document": digest(execution_doc_path),
        },
        "interpretation": (
            "Passing this report establishes only that the frozen 128-case data and the "
            "next-block provisional lifecycle agree statically. It is not evidence of model "
            "qualification, learned skills, improvement, or benchmark performance."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not all(checks.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
