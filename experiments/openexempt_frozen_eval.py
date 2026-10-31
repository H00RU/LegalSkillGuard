"""Frozen EC/EV comparison: existing actors/scorer, no teacher or skill updates.

This entry point is not used until methods, publications and the complete matrix
are fixed. It never imports a TEST packet at module import or plan validation.
"""

from __future__ import annotations

import argparse
import ast
from concurrent.futures import ThreadPoolExecutor, as_completed
import fcntl
import importlib.metadata
import json
import os
import signal
import threading
import traceback
from pathlib import Path

import numpy as np

from experiments.openexempt_ace_online import ACEOnline
from experiments.openexempt_online import (
    CONSOLIDATION_PHASE, Online, actor_payload, freeze, observed_consolidation_inputs,
    paired_effect, preserve,
)
from experiments.openexempt_trace2skill import validate_profile as validate_trace2skill_profile
from experiments.openexempt_teacher_evidence_control import validate_withheld_request
from legal_skill_guard.experiment.storage import RunStore, safe_component
from legal_skill_guard.learning.experiment import INITIAL_PLAYBOOK, Comparison, now, read, sha
from legal_skill_guard.learning.legal_namespace import public_asset_catalog, validate_scopes
from legal_skill_guard.learning.openexempt_ace import generator_payload
from legal_skill_guard.learning import runtime_sources
from legal_skill_guard.learning.task_scoped_skills import validate_scoped_bank
from legal_skill_guard.learning.trace2skill_text import INITIAL_FILES as TRACE2SKILL_INITIAL_FILES, actor_bank as trace2skill_actor_bank
from legal_skill_guard.openexempt import FAMILIES, ROOT, metrics
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha

SHARED_ACTOR_FILES = (
    "experiments/openexempt_online.py",
    "legal_skill_guard/openexempt.py",
    "legal_skill_guard/learning/legal_namespace.py",
    "legal_skill_guard/learning/task_scoped_skills.py",
    "legal_skill_guard/learning/claim_execution.py",
    "legal_skill_guard/learning/publication.py",
    "legal_skill_guard/learning/experiment.py",
    "legal_skill_guard/inference/native.py",
    "legal_skill_guard/inference/openai_client.py",
)
ACE_ACTOR_FILES = (
    "experiments/openexempt_ace_online.py", "legal_skill_guard/learning/openexempt_ace.py",
    "legal_skill_guard/learning/ace_native.py", "third_party/ace/prompts/generator.py",
)
ROLES = {"strong_empty", "evolved", "B1_frozen", "experience", "ablation", "static_law_only"}
PUBLIC_LAW_FIELDS = {
    "complete_public_statutes", "generic_contracts", "actual_actor_systems", "task_boundary",
    "public_skill_interface", "no_cases_targets_trajectories_scores_or_prior_bank",
}
LEARNING_SEEDS = (45, 145, 245)
SINGLE_BASELINE_DESIGN = "single_completed_seed45_20261024"
SINGLE_BASELINE_PROTOCOL = "docs/research/OPENEXEMPT_SINGLE_BASELINE_BUILD_AMENDMENT_20261024.md"
INITIAL_STAGE = "initial_single_build_descriptive"
FINAL_STAGE = "final_three_build_confirmatory"
SUPPLEMENT_STAGE = "adaptive_single_build_fixed_benchmark_supplement"
SUPPLEMENT_PROTOCOL = runtime_sources.ADAPTIVE_PROTOCOL
SUPPLEMENT_DESIGN = "historical_whole_task_local_comparators_v1"
SOURCE_DISJOINT_STAGE = "native_claim_single_build_source_disjoint_IID"
SOURCE_DISJOINT_PROTOCOL = (
    "docs/research/OPENEXEMPT_THIRD_FORMAL_MATCHED_POLICIES_AND_IID_EVAL_20261027.md"
)
SOURCE_DISJOINT_PACKET = "data/packets/openexempt_IID128_prospective_TEST_20261027"
SOURCE_DISJOINT_PACKET_SHA256 = "ec411ca55c7463d3c8c115d4a18a4afaf14d7ca3a5579fe3c125d965f50886e7"
SOURCE_DISJOINT_ARMS = {
    "empty": ("strong_empty", "direct", None),
    "static": ("static_law_only", "direct", "configs/openexempt_direct_law_only_static_20261021_run03.json"),
    "native_claim45": ("evolved", "direct", "configs/openexempt_native_claim_feedback_public_assets128_20261027_run01.json"),
    "native_claim_own_B1_45": ("B1_frozen", "direct", "configs/openexempt_native_claim_feedback_public_assets128_20261027_run01.json"),
    "whole_bank": ("ablation", "direct", "configs/openexempt_native_claim_whole_bank_public_assets128_20261027_run01.json"),
    "legal_scope": ("ablation", "direct", "configs/openexempt_native_claim_legal_scope_public_assets128_20261027_run01.json"),
    "ACE45": ("experience", "ace", "configs/openexempt_ace_public_assets128_20261023_run04.json"),
    "ACE_common45": ("experience", "direct", "configs/openexempt_ace_public_assets128_20261023_run04.json"),
    "text45": ("experience", "direct", "configs/openexempt_trace2skill_text_public_assets128_seed45_20261023_run02.json"),
}
CONTINUED_SOURCE_DISJOINT_STAGE = "completed_stream_continuation_source_disjoint_IID"
CONTINUED_SOURCE_DISJOINT_PROTOCOL = (
    "docs/research/OPENEXEMPT_CONTINUED_BANK_SOURCE_DISJOINT_EVALUATION_20261029.md"
)
CONTINUED_SOURCE_DISJOINT_ARMS = {
    **{name: value for name, value in SOURCE_DISJOINT_ARMS.items()
       if name not in {"whole_bank", "legal_scope"}},
    "task_consolidated45": ("evolved", "direct",
        "configs/openexempt_completed128_task_consolidation_20261028_run01.json"),
    "joint_consolidated45": ("ablation", "direct",
        "configs/openexempt_completed128_joint_consolidation_20261029_run01.json"),
}
CONTINUED_ONLINE_SHA256 = "4f16fdba0c87a159267c37569fe330b3b8a3016e869fb7d237395b7c00ceaff5"
CONTINUED_SOURCE_SNAPSHOTS = {
    "3213e92d8e3a3c2c3b4e565dd3553a17ba9b2e425e68e607232749363e8c1985":
        "openexempt_online_acquisition",
    "a6d5e0be6b87b230c8a777535a0ddda2dab126cf5c4fa188b54ddda4d4611a66":
        "openexempt_online_task_continuation",
}
UTILITY_SOURCE_DISJOINT_STAGE = "complete_output_utility_source_disjoint_IID_v6"
UTILITY_SOURCE_DISJOINT_PROTOCOL = (
    "docs/research/OPENEXEMPT_V6_FINAL_SOURCE_ISOLATED_FROZEN_EVALUATION_20261030.md"
)
UTILITY_SOURCE_DISJOINT_PACKET = "data/packets/openexempt_IID128_confirmatory_TEST_20261030"
UTILITY_SOURCE_DISJOINT_PACKET_SHA256 = "ff29ce066a21e9d4040ac7f51f1f855489dc7ec0723d611e9ec46cb851f3220b"
UTILITY_SOURCE_DISJOINT_ARMS = {
    **{name: value for name, value in SOURCE_DISJOINT_ARMS.items()
       if name in {"empty", "static", "ACE45", "ACE_common45", "text45"}},
    "utility45": ("evolved", "direct", "configs/openexempt_complete_output_utility_public_assets128_20261030_run01.json"),
    "utility_own_B1_45": ("B1_frozen", "direct", "configs/openexempt_complete_output_utility_public_assets128_20261030_run01.json"),
    "strict45": ("ablation", "direct", "configs/openexempt_v6_strict_policy_control_public_assets128_20261030_run01.json"),
    "no_execution45": ("ablation", "direct", "configs/openexempt_v6_teacher_execution_withheld_public_assets128_20261030_run01.json"),
    "projection45": ("version_reference", "direct", "configs/openexempt_task_projection_public_assets128_20261029_run01.json"),
}
SOURCE_DISJOINT_STAGES = (
    SOURCE_DISJOINT_STAGE, CONTINUED_SOURCE_DISJOINT_STAGE, UTILITY_SOURCE_DISJOINT_STAGE,
)


def source_disjoint_profile(cfg):
    """Separate explicit prospective epochs; never relabel an incomplete source."""
    if cfg.get("evaluation_stage") == UTILITY_SOURCE_DISJOINT_STAGE:
        return (UTILITY_SOURCE_DISJOINT_ARMS, UTILITY_SOURCE_DISJOINT_PROTOCOL, "utility45")
    if cfg.get("evaluation_stage") == CONTINUED_SOURCE_DISJOINT_STAGE:
        return (CONTINUED_SOURCE_DISJOINT_ARMS, CONTINUED_SOURCE_DISJOINT_PROTOCOL,
                "task_consolidated45")
    if cfg.get("evaluation_stage") == SOURCE_DISJOINT_STAGE:
        return SOURCE_DISJOINT_ARMS, SOURCE_DISJOINT_PROTOCOL, "native_claim45"
    raise ValueError("Unknown source-disjoint evaluation epoch")


def own_B1_reference(cfg, arm):
    source = arm["source_config"]
    if (cfg.get("evaluation_stage") == CONTINUED_SOURCE_DISJOINT_STAGE
            and arm["name"] in {"task_consolidated45", "joint_consolidated45"}):
        source = SOURCE_DISJOINT_ARMS["native_claim45"][2]
    names = [other["name"] for other in cfg["arms"]
             if other["role"] == "B1_frozen" and other["source_config"] == source]
    if len(names) != 1:
        raise ValueError("Every evolved bank needs its unique actual acquisition B1 reference")
    return names[0]


SOURCE_DISJOINT_LEGACY_RECEIPTS = {
    "configs/openexempt_adaptive_supplement_TEST128_20261027_run01.json":
        "548005dd7feaa41260bbbe278ce6300fc9546fab9645445ab97dbb2e96904a1a",
    "configs/openexempt_adaptive_supplement_TEST128_20261027_run01.frozen.json":
        "21aa08e969cd56144c7f66b80eab0275ccf114293cda1840dafeb89c37af0188",
    "runs/legal_openexempt_adaptive_supplement_TEST128_20261027_run01/completion.json":
        "0120d9f140ed1d6bd92c836141e2168e8bb3b247a323b8ba76f0020a389416d7",
    "runs/legal_openexempt_adaptive_supplement_TEST128_20261027_run01/terminal_preservation.json":
        "41aed51690f777482ddeb0e368536e37c76c674ecfa9777650a04396cb5d0ad4",
}
INITIAL_SOURCE_SNAPSHOTS = {
    "README.md", "tests/test_openexempt_contract.py",
    "experiments/openexempt_frozen_eval.py", "tests/test_openexempt_frozen_eval.py",
    "legal_skill_guard/learning/runtime_sources.py",
}
STAGED_PROTOCOL = "docs/research/OPENEXEMPT_MAIN_TABLE_FIRST_STAGED_REPEATS_20261024.md"
FINAL_DECODING = {"seed": 45, "temperature": 0.6, "top_p": 0.95, "top_k": 20,
                  "context_tokens": 32768, "max_tokens": 8192, "disable_thinking": False}
REPEATED_PROTOCOL_KEYS = (
    "learner", "execution_contract", "execution_contract_version", "skill_commit_policy",
    "candidate_feedback_policy", "frozen_after_first_batch_control", "input_contract",
    "input_packet", "grading_directory", "source_cases", "batch_source_cases", "planned_batches",
    "initial_library_kind", "max_candidate_attempts", "library_token_hard_cap",
    "ace_max_TRAIN_reflection_rounds", "ace_capacity_policy", "stop_policy",
    "ace_bullet_provenance_policy", "ace_failed_output_feedback_policy",
    "admission_contract", "ace_TRAIN_success_contract", "no_validation_set",
    "analysis_mode", "trace_initial_library", "patch_initial_files", "merge_batch_size",
    "max_merge_levels", "translation_calls", "patch_failure_policy", "final_TRAIN_validation_policy",
)

DISPATCH_PROTOCOL = "docs/research/OPENEXEMPT_FROZEN_EVAL_SINGLE_INSTANCE_DISPATCH_20261023.md"


def evaluation_request_workers(cfg):
    """A pre-frozen inference schedule, never an outcome-selected budget."""
    workers = cfg.get("inference_request_workers", 1)
    if type(workers) is not int or workers not in (1, 4):
        raise ValueError("Declare one or four frozen evaluation request workers")
    if workers == 4:
        if (cfg.get("inference_dispatch_protocol") != DISPATCH_PROTOCOL
                or not (ROOT / DISPATCH_PROTOCOL).is_file()
                or cfg.get("inference_dispatch_policy")
                != "four_workers_one_instance_exact_wire_lock_no_retry"):
            raise ValueError("Freeze the explicit single-instance concurrent evaluation protocol")
        argv = read(ROOT / cfg["inference_environment"])["actual_argv"]
        if (argv.count("--max-num-seqs") != 1
                or argv.index("--max-num-seqs") + 1 >= len(argv)
                or argv[argv.index("--max-num-seqs") + 1] != "4"):
            raise ValueError("Four workers require a captured four-sequence single-model environment")
    return workers


def check_primary_contrasts(cfg, source_configs):
    """Freeze all primary controls and three independently learned banks before TEST."""
    design = cfg.get("experience_replication_design")
    if design not in (None, SINGLE_BASELINE_DESIGN):
        raise ValueError("Unknown experience-baseline replication design")
    initial = cfg.get("evaluation_stage") == INITIAL_STAGE
    supplement = cfg.get("evaluation_stage") == SUPPLEMENT_STAGE
    single_build = initial or supplement
    learning_seeds = (45,) if single_build else LEARNING_SEEDS
    single_baselines = single_build or design == SINGLE_BASELINE_DESIGN
    if initial and cfg.get("staged_comparison_protocol") != STAGED_PROTOCOL:
        raise ValueError("Declare the initial-table staged protocol before TEST")
    if not single_build and single_baselines and cfg.get("baseline_build_amendment") != SINGLE_BASELINE_PROTOCOL:
        raise ValueError("Declare the prospective single-baseline amendment")
    def require_same_protocol(names):
        protocols = []
        for name in names:
            source = source_configs[name]
            protocol = {
                **{key: source.get(key) for key in REPEATED_PROTOCOL_KEYS},
                "generation": {k: v for k, v in source["generation"].items() if k != "seed"},
                "teacher": {k: v for k, v in source.get("teacher", {}).items()
                            if k != "total_invocation_budget"},
            }
            if source.get("learner") == "ace_native_online_v4":
                expected = ("same_empty_origin_exact_last_completed_prefix_disclosed"
                            if source.get("continuation_receipt") else
                            "native_empty_section_headers_without_legal_prior")
                if source.get("initial_library_kind") != expected:
                    raise ValueError("ACE repeats must retain the verified empty learning origin")
                # fixed_banks verifies the actual prefix before comparing
                # protocols. An operational continuation is not a warm prior.
                protocol["initial_library_kind"] = "native_empty_section_headers_without_legal_prior"
            protocols.append(protocol)
        if any(protocol != protocols[0] for protocol in protocols[1:]):
            raise ValueError("Independent learning repeats changed a shared protocol field")

    arms = {a["name"]: a for a in cfg["arms"]}
    text_design = cfg.get("external_text_adaptation")
    if text_design not in (None, "trace2skill_text_offline_v1"):
        raise ValueError("Unknown external text-adaptation comparison design")
    text_arms = [a for a in cfg["arms"] if a["role"] == "experience" and a["backend"] == "direct"]
    ace_arms = [a for a in cfg["arms"] if a["role"] == "experience" and a["backend"] == "ace"]
    if text_arms and text_design is None:
        raise ValueError("Explicitly declare the additional adapted method and larger comparison family")
    expected_experience_banks = 1 if single_baselines else 3
    if text_design and (len(text_arms) != expected_experience_banks
                        or len(ace_arms) != expected_experience_banks):
        raise ValueError("Use exactly the declared actual ACE and text-adaptation bank counts")
    evolved = [a["name"] for a in cfg["arms"] if a["role"] == "evolved"]
    evolved.sort(key=lambda name: source_configs[name]["generation"]["seed"])
    if (len(evolved) != len(learning_seeds)
            or tuple(source_configs[n]["generation"]["seed"] for n in evolved) != learning_seeds):
        raise ValueError("Use the exact main learning seeds declared for this analysis stage")
    require_same_protocol(evolved)
    contrasts = cfg.get("primary_contrasts", [])
    if len(contrasts) < (5 if text_design else 4) or len({c["name"] for c in contrasts}) != len(contrasts):
        raise ValueError("Freeze all primary contrasts, including four required control families")
    covered, experience, signatures = set(), set(), set()
    for contrast in contrasts:
        safe_component(contrast["name"])
        before = contrast["before"]
        if (contrast["after"] != evolved or not before or len(before) != len(set(before))
                or any(n not in arms for n in before)):
            raise ValueError("Each primary contrast must align the same three evolved banks")
        roles = {arms[n]["role"] for n in before}
        if len(roles) != 1 or not roles <= {"strong_empty", "B1_frozen", "experience", "static_law_only"}:
            raise ValueError("Primary controls must retain their declared comparison roles")
        role = next(iter(roles))
        if role in {"strong_empty", "static_law_only"}:
            if len(before) != 1:
                raise ValueError("Empty and static predictions are one common arm, not three draws")
        elif role == "experience" and single_baselines:
            if len(before) != 1 or source_configs[before[0]]["generation"]["seed"] != 45:
                raise ValueError("Each amended experience control is one actual completed seed45 bank")
        elif (len(before) != len(learning_seeds)
              or tuple(source_configs[n]["generation"]["seed"] for n in before) != learning_seeds):
            raise ValueError("Align actual control learning runs with this analysis stage")
        if role == "B1_frozen" and any(
                arms[b]["source_config"] != arms[a]["source_config"] for b, a in zip(before, evolved)):
            raise ValueError("Pair each evolution run with its own actual B1 snapshot")
        signature = tuple(before)
        if signature in signatures:
            raise ValueError("Do not rename the same primary contrast as another method")
        signatures.add(signature)
        covered.add(role)
        if role == "experience":
            require_same_protocol(before)
            experience.update(before)
    if (covered != {"strong_empty", "B1_frozen", "experience", "static_law_only"}
            or experience != {n for n, a in arms.items() if a["role"] == "experience"}):
        raise ValueError("Include every declared experience control and all required families")


def check_secondary_contrasts(cfg, source_configs):
    """The two declared single-seed policy ablations, not three repeated controls."""
    arms = {a["name"]: a for a in cfg["arms"]}
    evolved = [n for n, a in arms.items() if a["role"] == "evolved"
               and source_configs[n]["generation"]["seed"] == 45]
    design = cfg.get("ablation_design", "scope_and_feedback_legacy")
    if cfg.get("evaluation_stage") == SUPPLEMENT_STAGE:
        if (design != SUPPLEMENT_DESIGN or len(evolved) != 1
                or cfg.get("historical_comparators_not_matched_new_ablations") is not True):
            raise ValueError("Retain the two old policies as historical comparators, not new matched ablations")
        original = read(ROOT / cfg["initial_evaluation"]["source_config"])
        original_main = next(a for a in original["arms"] if a["role"] == "evolved")
        old_source = read(ROOT / original_main["source_config"])
        controls = {a["name"] for a in cfg["arms"] if a["role"] == "ablation"}
        contrasts = cfg.get("secondary_contrasts", [])
        if (len(controls) != 2 or len(contrasts) != 2
                or {c["before"][0] for c in contrasts if len(c["before"]) == 1} != controls
                or len({c["name"] for c in contrasts}) != 2
                or {c["name"] for c in contrasts} & {c["name"] for c in cfg["primary_contrasts"]}):
            raise ValueError("Keep both distinct historical comparisons in their own fixed family")
        variants = set()
        for contrast in contrasts:
            safe_component(contrast["name"])
            if contrast["after"] != evolved or len(contrast["before"]) != 1:
                raise ValueError("Compare each historical policy only with the revised actual seed45 bank")
            source = source_configs[contrast["before"][0]]
            variant = source.get("ablation_variant")
            if (variant not in ("whole_bank", "task_local") or variant in variants
                    or source.get("skill_commit_policy") != variant
                    or source.get("candidate_feedback_policy") != "carry_partial_and_refine"
                    or source.get("comparison_reference_run") != old_source["run_id"]
                    or source.get("comparison_reference_config_sha256")
                    != original_main["source_config_sha256"]):
                raise ValueError("Do not relabel or reconstruct the historical fixed-policy controls")
            variants.add(variant)
        return
    uniform = cfg.get("learning_execution_schedule") == runtime_sources.CONTROL_SCHEDULE
    if uniform and design != "legal_scope_granularity_v1":
        raise ValueError("The uniform dispatch amendment retains the two granularity controls")
    if design == "legal_scope_granularity_v1":
        expected = {"whole_bank": ("whole_bank", "carry_partial_and_refine"),
                    "task_local": ("task_local", "carry_partial_and_refine")}
    elif design == "scope_and_feedback_legacy":
        # Retain low-level checks of historical plans, never the current formal entry.
        expected = {"whole_bank": ("whole_bank", "carry_partial_and_refine"),
                    "first_commit": ("legal_scope", "batch_only_first_commit")}
    else:
        raise ValueError("Unknown predeclared two-ablation design")
    ablations = [n for n, a in arms.items() if a["role"] == "ablation"]
    contrasts = cfg.get("secondary_contrasts", [])
    if (len(evolved) != 1 or len(ablations) != 2 or len(contrasts) != 2
            or len({c["name"] for c in contrasts}) != 2
            or {c["name"] for c in contrasts} & {c["name"] for c in cfg["primary_contrasts"]}):
        raise ValueError("Declare both single-seed mechanism ablations in a separate comparison family")
    parent = source_configs[evolved[0]]
    if (parent.get("skill_commit_policy"), parent.get("candidate_feedback_policy")) != (
            "legal_scope", "carry_partial_and_refine"):
        raise ValueError("The full method must retain its declared scope and closed-feedback policies")
    seen, variants, uniform_profile = set(), set(), None
    for contrast in contrasts:
        safe_component(contrast["name"])
        before = contrast["before"]
        if (contrast["after"] != evolved or len(before) != 1 or before[0] not in ablations
                or before[0] in seen):
            raise ValueError("Pair each single-seed ablation only with the full method at learning seed45")
        name = before[0]
        source = source_configs[name]
        variant = source.get("ablation_variant")
        if (variant not in expected or variant in variants
                or (source.get("skill_commit_policy"), source.get("candidate_feedback_policy"))
                != expected[variant]
                or source.get("comparison_reference_run") != parent["run_id"]
                or source.get("comparison_reference_config_sha256")
                != arms[evolved[0]]["source_config_sha256"]
                or source["run_id"] == parent["run_id"]):
            raise ValueError("Use the actual independently learned declared policy ablation")
        for key in ("generation", "input_packet", "grading_directory", "source_cases",
                    "batch_source_cases", "planned_batches", "library_token_hard_cap",
                    "max_candidate_attempts", "frozen_after_first_batch_control", "input_contract",
                    "no_validation_set") + (() if uniform else (
                        "phase_dispatch", "inference_environment")):
            if source.get(key) != parent.get(key):
                raise ValueError("Ablation changes an undeclared common condition: " + key)
        if uniform:
            if (not runtime_sources.uniform_control(source)
                    or source.get("phase_dispatch") != runtime_sources.DECLARATION
                    or not source.get("inference_environment")):
                raise ValueError("Both amended controls must declare the identical four-worker profile")
            profile = (csha(source["phase_dispatch"]), source["inference_environment"])
            if uniform_profile is not None and profile != uniform_profile:
                raise ValueError("The two controls cannot use different execution environments")
            uniform_profile = profile
        teachers = [{k: v for k, v in config.get("teacher", {}).items()
                     if k != "total_invocation_budget"} for config in (parent, source)]
        if teachers[0] != teachers[1]:
            raise ValueError("Ablations must retain the common teacher and invocation policy")
        seen.add(name)
        variants.add(variant)


def pooled_complete_claim_metrics(records):
    """Descriptive totals from original grader fields, never a replacement score."""
    result = {}
    fields = ("full_output_claim_tp", "full_output_claim_fp", "full_output_claim_fn")
    for family in FAMILIES:
        rows = [r for r in records if r["family"] == family]
        missing = [r["case_id"] for r in rows if any(k not in r["score"] for k in fields)]
        if missing:
            result[family] = {"available": False, "tasks": len(rows), "f1": None,
                "missing_original_count_case_ids": missing,
                "reason": "original_grader_did_not_emit_complete_claim_counts; no subset or answer recovery"}
            continue
        if any(type(r["score"][k]) is not int or r["score"][k] < 0 for r in rows for k in fields):
            raise ValueError("Pooled claim audits require the original nonnegative integer counts")
        tp, fp, fn = (sum(r["score"][k] for r in rows) for k in fields)
        denominator = 2 * tp + fp + fn
        result[family] = {"available": bool(denominator), "tasks": len(rows),
            "correct_claims": tp, "extra_or_incorrect_predictions": fp,
            "missing_or_incorrect_targets": fn,
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None,
            "f1": 2 * tp / denominator if denominator else None}
    return result


def paired_source_statistics(cfg, records):
    """The declared conditional paired source bootstrap; never load questions or gold."""
    names = {a["name"] for a in cfg["arms"]}
    if set(records) != names:
        raise ValueError("Do not analyze a subset of the frozen arms")
    grids, identities = {}, {}
    for name, rows in records.items():
        grid = {}
        for row in rows:
            key = (row["source_key"], row["family"])
            if key in grid or row["family"] not in FAMILIES:
                raise ValueError("Keep exactly one EC and EV score per source per arm")
            value = row["score"]["f1"]
            if not np.isfinite(value) or not 0 <= value <= 1:
                raise ValueError("Keep valid original F1 scores; never replace missing outcomes")
            if identities.setdefault(row["source_key"], row["case_id"]) != row["case_id"]:
                raise ValueError("Source pairing differs across tasks or arms")
            grid[key] = float(value)
        grids[name] = grid
    keys = sorted(identities)
    expected = {(key, family) for key in keys for family in FAMILIES}
    if (len(keys) != cfg["source_cases"] or len(set(identities.values())) != len(keys)
            or any(set(grid) != expected for grid in grids.values())):
        raise ValueError("Complete the whole source-paired matrix before inference statistics")
    source_disjoint = cfg.get("evaluation_stage") in SOURCE_DISJOINT_STAGES
    primary, secondary = cfg["primary_contrasts"], cfg.get("secondary_contrasts", [])
    if not primary or len(secondary) != (0 if source_disjoint else 2):
        raise ValueError("Prespecify the complete primary and two-ablation secondary families")
    if source_disjoint:
        profile, _, target = source_disjoint_profile(cfg)
        expected = {(target, name) for name in profile if name != target}
        observed = {(c["after"][0], c["before"][0]) for c in primary
                    if len(c["after"]) == len(c["before"]) == 1}
        count = len(profile) - 1
        if len(primary) != count or observed != expected or len({c["name"] for c in primary}) != count:
            raise ValueError("Retain every predeclared paired contrast and both native endpoints")
    contrasts = primary + secondary
    matrices = {name: np.asarray([[grid[key, f] for f in FAMILIES] for key in keys])
                for name, grid in grids.items()}
    differences, repeated = [], []
    initial = cfg.get("evaluation_stage") == INITIAL_STAGE
    supplement = cfg.get("evaluation_stage") == SUPPLEMENT_STAGE
    single_build = initial or supplement or source_disjoint
    expected_main_banks = 1 if single_build else 3
    for j, contrast in enumerate(contrasts):
        after = np.stack([matrices[n] for n in contrast["after"]])
        before = np.stack([matrices[n] for n in contrast["before"]])
        if j < len(primary) and (after.shape[0] != expected_main_banks
                                or before.shape[0] not in (1, expected_main_banks)):
            raise ValueError("Analyze the actual bank counts declared for this stage")
        if j >= len(primary) and (after.shape[0] != 1 or before.shape[0] != 1):
            raise ValueError("Single-seed ablations do not have three independent learning repeats")
        delta = after - before
        differences.append(delta.mean(axis=0))
        repeated.append({"after_F1_percent": (100 * after.mean(axis=1)).tolist(),
                         "before_F1_percent": (100 * before.mean(axis=1)).tolist(),
                         "difference_pp": (100 * delta.mean(axis=1)).tolist(),
                         "difference_range_pp": (100 * np.stack([
                             delta.mean(axis=1).min(axis=0), delta.mean(axis=1).max(axis=0)])).tolist()})
    delta = np.stack(differences, axis=1)
    bootstrap_seed = (2026103092 if cfg.get("evaluation_stage") == UTILITY_SOURCE_DISJOINT_STAGE
                      else 2026102792 if source_disjoint else 2026102192)
    rng = np.random.Generator(np.random.PCG64(bootstrap_seed))
    indices = rng.integers(len(keys), size=(20000, len(keys)))
    draws = delta[indices].mean(axis=1)
    m, secondary_m = len(primary) * len(FAMILIES), len(secondary) * len(FAMILIES)
    ordinary = np.quantile(draws, [0.025, 0.975], axis=0, method="linear")
    adjusted = np.quantile(draws[:, :len(primary)], [0.025 / m, 1 - 0.025 / m],
                           axis=0, method="linear")
    if secondary:
        adjusted = np.concatenate((adjusted,
            np.quantile(draws[:, len(primary):], [0.025 / secondary_m, 1 - 0.025 / secondary_m],
                        axis=0, method="linear")), axis=1)
    result = {}
    for j, contrast in enumerate(contrasts):
        result[contrast["name"]] = {"after": contrast["after"], "before": contrast["before"],
                                   "per_learning_repeat": repeated[j], "endpoints": {}}
        for k, family in enumerate(FAMILIES):
            d = delta[:, j, k]
            result[contrast["name"]]["endpoints"][family] = {
                "difference_pp": float(100 * d.mean()),
                "conditional_95pct_interval_pp": (100 * ordinary[:, j, k]).tolist(),
                "conditional_Bonferroni_interval_pp": (100 * adjusted[:, j, k]).tolist(),
                "adjusted_lower_positive": bool(adjusted[0, j, k] > 0),
                "source_win_tie_loss": [int((d > 1e-12).sum()), int((np.abs(d) <= 1e-12).sum()),
                                        int((d < -1e-12).sum())],
                "sources_difference_at_most_minus_10pp": int((d <= -0.10).sum()),
                "paired_source_differences_pp": (100 * d).tolist()}
    return {"protocol": ("conditional_frozen_bank_source_disjoint_IID" if source_disjoint else
                         "conditional_development_informed_fixed_benchmark_supplement" if supplement else
                         "conditional_single_build_initial_descriptive" if initial else
                         "conditional_paired_source_bootstrap_three_learning_runs"),
            "evaluation_stage": cfg.get("evaluation_stage", "legacy_final"),
            "initial_table_not_a_repeat_selection_or_stopping_gate": initial,
            "confirmatory_analysis": source_disjoint or not single_build,
            "source_disjoint_confirmation_for_actual_frozen_banks": source_disjoint,
            "development_informed_fixed_benchmark_supplement": supplement,
            "experience_replication_design": ("single_actual_seed45_extra_learning_repeats_user_deferred" if source_disjoint else
                "single_actual_seed45_fixed_benchmark_banks" if supplement else
                cfg.get("experience_replication_design", "legacy_three_seed_matched")),
            "shared_experience_predictions_not_independent_learning_repeats": (
                single_build or cfg.get("experience_replication_design") == SINGLE_BASELINE_DESIGN),
            "sources": len(keys), "source_keys_sorted": keys, "endpoints": list(FAMILIES),
            "bootstrap_draws": 20000, "bootstrap_seed": bootstrap_seed,
            "rng": "NumPy Generator PCG64", "numpy_version": np.__version__, "quantile_method": "linear",
            "primary_family_comparisons": m,
            "contrasts": {c["name"]: result[c["name"]] for c in primary},
            "secondary_family_comparisons": secondary_m,
            "secondary_contrasts": {c["name"]: result[c["name"]] for c in secondary},
            "secondary_single_learning_seed45_not_three_repeats_or_matched_actual_compute": None if source_disjoint else True,
            "all_primary_adjusted_lower_bounds_positive": None if initial or supplement else all(
                endpoint["adjusted_lower_positive"] for c in primary
                for endpoint in result[c["name"]]["endpoints"].values()),
            "conditional_on_actual_learned_banks_and_fixed_decoding_not_algorithm_population": True,
            "single_empty_and_static_prediction_not_independent_replicates": True}


def check_ace_learning_origin(source, frozen, out, initial, complete, *, _lineage=None,
                              allow_phase_dispatch=False, adaptive=False):
    """Verify empty-origin TRAIN lineage, including actual timeout continuations.

    This reads TRAIN provenance only, never a TEST packet or target. Returned
    paths must enter the final freeze. It neither restores a state nor calls
    an actor, teacher, scorer, recovery parser or checkpoint selector.
    """
    if (source.get("learner") != "ace_native_online_v4"
            or source.get("ace_failed_output_feedback_policy")
            != "verbatim_public_output_no_answer_recovery"):
        raise ValueError("ACE final banks must use the corrected failed-public-output policy")
    receipt_name = source.get("continuation_receipt")
    if not receipt_name:
        if (initial["playbook"] != INITIAL_PLAYBOOK
                or source.get("initial_library_kind")
                != "native_empty_section_headers_without_legal_prior"
                or initial.get("continued_same_learner_prefix") is not None
                or complete.get("continuation_source_run") is not None
                or complete.get("restored_native_origins", 0) != 0
                or complete.get("restored_teacher_responses", 0) != 0):
            raise ValueError("A fresh ACE repeat must start empty without a hidden inherited prefix")
        return set()
    seen = set() if _lineage is None else set(_lineage)
    if source["run_id"] in seen:
        raise ValueError("An ACE learning lineage cannot contain a cycle")
    seen.add(source["run_id"])
    path = ROOT / receipt_name
    if (frozen["files"].get(receipt_name) != sha(path)
            or source["generation"]["seed"] != 45
            or source.get("initial_library_kind")
            != "same_empty_origin_exact_last_completed_prefix_disclosed"):
        raise ValueError("Bind the declared seed45 exact-prefix continuation before TEST")
    receipt = read(path)
    contract = receipt.get("continuation_contract", "v3_failed_public_output_prefix")
    legacy = contract == "v3_failed_public_output_prefix"
    if contract not in ("v3_failed_public_output_prefix", "same_v4_teacher_timeout_committed_prefix_v1"):
        raise ValueError("Declare the actual ACE continuation contract")
    through = receipt.get("through_batch")
    if (receipt.get("role") != "exact_last_complete_ACE_prefix_not_best_checkpoint"
            or type(through) is not int or not 1 <= through < source["planned_batches"]
            or receipt.get("saved_first_forecast_batch") != through + 1):
        raise ValueError("Use the unique last complete prefix and complete next first forecasts")
    if legacy:
        if (through != 2 or receipt.get("no_parse_failure_in_completed_prefix") is not True
                or receipt.get("zero_B3_TRAIN_or_teacher_import") is not True):
            raise ValueError("The v3 correction still requires its proved unaffected last B2")
    elif (receipt.get("zero_uncommitted_TRAIN_or_teacher_import") is not True
            or receipt.get("original_invalid_predictions_retained") is not True
            or receipt.get("complete_next_first_forecasts_exact_request_only") is not True):
        raise ValueError("Timeout recovery cannot rewrite forecasts or import unfinished learning")
    version_sources = set()
    for name, digest in receipt["files"].items():
        actual = (ROOT / name).resolve()
        if Path(name).is_absolute() or not actual.is_relative_to(ROOT.resolve()):
            raise ValueError("Original ACE continuation artifact changed: " + name)
        if sha(actual) != digest:
            if not allow_phase_dispatch or name not in runtime_sources.HISTORICAL:
                raise ValueError("Original ACE continuation artifact changed: " + name)
            version_sources.update(runtime_sources.verify_revision(ROOT, name, digest, adaptive=adaptive))
    old_path = ROOT / receipt["source_config"]
    old = read(old_path)
    old_out = ROOT / "runs" / old["run_id"]
    if (sha(old_path) != receipt["source_config_sha256"]
            or sha(ROOT / receipt["source_frozen"]) != receipt["source_frozen_sha256"]
            or old.get("learner") != ("ace_native_online_v3" if legacy else "ace_native_online_v4")
            or old["run_id"] != receipt["source_run_id"]
            or not (old_out / "terminal_preservation.json").is_file()
            or (old_out / "completion.json").exists()
            or sorted(p.name for p in (old_out / "publications").glob("b*.json"))
            != sorted(f"b{b}.json" for b in range(1, through + 1))):
        raise ValueError("Continuation must use its actual last stopped empty-origin learner")
    stopped = read(old_out / "failure.json")
    if legacy:
        if stopped["error"] != "InterruptedError('Operator stop at artifact-safe boundary')":
            raise ValueError("The inherited v3 prefix lacks the recorded safe operator stop")
    else:
        failed_name, wire_name = receipt["failed_teacher_attempt"], receipt["failed_teacher_wire_request"]
        if failed_name not in receipt["files"] or wire_name not in receipt["files"]:
            raise ValueError("Bind the actual failed timeout and teacher request")
        failed = read(ROOT / failed_name)
        if (failed.get("error_type") != "TimeoutExpired" or "TimeoutExpired" not in stopped["error"]
                or not failed.get("purpose", "").startswith(old["run_id"] + f"_b{through + 1}_")
                or failed.get("request_sha256") != csha(read(ROOT / wire_name))):
            raise ValueError("Only an actual stopped teacher timeout qualifies for this contract")
    old_frozen = read(ROOT / receipt["source_frozen"])
    if old_frozen["files"][source["input_packet"]] != frozen["files"][source["input_packet"]]:
        raise ValueError("The continued learner must retain its actual original TRAIN packet")
    for key in ("generation", "input_packet", "grading_directory", "source_cases",
                "batch_source_cases", "planned_batches", "execution_contract",
                "execution_contract_version", "library_token_hard_cap",
                "ace_max_TRAIN_reflection_rounds", "ace_bullet_provenance_policy"):
        if source[key] != old[key]:
            raise ValueError("Continuation changed an unaffected learning condition: " + key)
    teacher = lambda c: {k: v for k, v in c["teacher"].items() if k != "total_invocation_budget"}
    if (teacher(source) != teacher(old) or not legacy
            and source["ace_failed_output_feedback_policy"] != old["ace_failed_output_feedback_policy"]):
        raise ValueError("Continuation changed the inherited teacher policy")
    extras, ancestor_origins, ancestor_teachers = version_sources, set(), set()
    old_initial = read(old_out / "initialization.json")
    if old.get("continuation_receipt"):
        prior = read(ROOT / old["continuation_receipt"])
        prior_meta = read(old_out / "continuation.json")
        ancestor_origins, ancestor_teachers = set(prior["native_origins"]), set(prior["teacher_responses"])
        # Actual failed-ancestor counters, not a synthetic completion record.
        accounting = {**stopped, "batch_summary": read(old_out / "batch_summary.json"),
            "continuation_source_run": prior["source_run_id"],
            "restored_native_origins": prior_meta["restored_native_origins"],
            "restored_teacher_responses": prior_meta["restored_teacher_responses"],
            "fresh_native_calls_after_continuation":
                stopped["actual_native_calls"] - prior_meta["restored_native_origins"],
            "fresh_teacher_responses_after_continuation":
                stopped["actual_teacher_responses"] - prior_meta["restored_teacher_responses"]}
        extras.update(check_ace_learning_origin(
            old, old_frozen, old_out, old_initial, accounting, _lineage=seen,
            allow_phase_dispatch=allow_phase_dispatch, adaptive=adaptive))
    elif old_initial["playbook"] != INITIAL_PLAYBOOK:
        raise ValueError("The oldest actual ACE learner must start at the empty section headers")
    parent = csha(INITIAL_PLAYBOOK)
    for batch in range(1, through + 1):
        pub_path = old_out / "publications" / f"b{batch}.json"
        pub = read(pub_path)
        if (pub["parent_playbook_sha256"] != parent
                or pub["playbook_sha256"] != csha(pub["playbook"])
                or csha(read(out / "publications" / f"b{batch}.json")) != csha(pub)):
            raise ValueError("Restored ACE publication is not the exact original prefix")
        parent = pub["playbook_sha256"]
        if read(out / "batches" / f"b{batch}_records.json") != read(
                old_out / "batches" / f"b{batch}_records.json"):
            raise ValueError("Restored first forecasts cannot be rewritten")
    meta = initial.get("continued_same_learner_prefix") or {}
    restored = read(out / "continuation.json")
    if (parent != receipt["parent_playbook_sha256"] or csha(initial["playbook"]) != parent
            or meta.get("receipt") != receipt_name or meta.get("source_run") != old["run_id"]
            or meta.get("through_batch") != through or meta.get("parent_playbook_sha256") != parent
            or initial.get("not_a_new_independent_repeat_when_continued") is not True
            or restored["receipt_sha256"] != sha(path)
            or restored["source_run"] != old["run_id"]
            or restored.get("not_a_new_independent_learning_repeat") is not True
            or complete.get("continuation_source_run") != old["run_id"]
            or complete["batch_summary"][:through] != read(old_out / "batch_summary.json")):
        raise ValueError("The final ACE bank must disclose its single original learning lineage")
    origins, responses = receipt["native_origins"], receipt["teacher_responses"]
    if len(set(origins)) != len(origins) or len(set(responses)) != len(responses):
        raise ValueError("Repeated origins are not additional native or teacher calls")
    stages = tuple(f"b{b}_" for b in range(1, through + 1))
    next_stage = f"b{through + 1}_prequential"
    for name in origins:
        p = ROOT / name
        if (name not in receipt["files"]
                or not (p.is_relative_to(old_out / "native") or name in ancestor_origins)):
            raise ValueError("An inherited native call must belong to the original ACE learner")
        raw = read(p)
        if not (raw["stage"].startswith(stages) or raw["stage"] == next_stage):
            raise ValueError("Never inherit unfinished next-batch TRAIN generations")
    for name in responses:
        p = ROOT / name
        if (name not in receipt["files"]
                or not (p.is_relative_to(old_out / "teacher") or name in ancestor_teachers)
                or not p.parent.name.startswith(stages)):
            raise ValueError("Never inherit unfinished next-batch teacher responses")
    for name in receipt["files"]:
        p = ROOT / name
        if (legacy and p.is_relative_to(old_out / "native") and p.name.endswith(".answer.json")
                and p.parent.name.startswith(("b1_", "b2_")) and read(p)["parse_error"] is not None):
            raise ValueError("The corrected failure branch was already used in the inherited prefix")
    for field, count in (("restored_native_origins", len(origins)),
                         ("restored_teacher_responses", len(responses))):
        if complete.get(field) != count or restored.get(field) != count:
            raise ValueError("Restored ACE origin counts do not match the actual source list")
    if (complete["actual_native_calls"] != len(origins) + complete["fresh_native_calls_after_continuation"]
            or complete["actual_teacher_responses"] != len(responses)
            + complete["fresh_teacher_responses_after_continuation"]):
        raise ValueError("Retain restored and fresh continuation costs separately")
    if legacy and (stopped["actual_native_calls"] != len(origins) + receipt["retired_B3_TRAIN_native"]
            or stopped["actual_teacher_responses"] != len(responses)
            + receipt["retired_B3_teacher_responses"]
            or restored["retired_B3_TRAIN_native_not_imported"] != receipt["retired_B3_TRAIN_native"]
            or restored["retired_B3_teachers_not_imported"] != receipt["retired_B3_teacher_responses"]):
        raise ValueError("Keep stopped B3 work in the recorded cost instead of hiding or reusing it")
    if not legacy:
        attempts = sum(read(ROOT / n)["capacity_transport_attempt_index"] + 1 for n in responses)
        if (stopped["actual_native_calls"] != len(origins) + receipt["retired_uncommitted_TRAIN_native"]
                or stopped["actual_teacher_responses"] != len(responses)
                + receipt["retired_uncommitted_teacher_responses"]
                or stopped["actual_teacher_attempts"] != attempts + receipt["retired_uncommitted_teacher_attempts"]
                or restored["retired_uncommitted_TRAIN_native_not_imported"] != receipt["retired_uncommitted_TRAIN_native"]
                or restored["retired_uncommitted_teacher_responses_not_imported"]
                != receipt["retired_uncommitted_teacher_responses"]
                or restored["retired_uncommitted_teacher_attempts"] != receipt["retired_uncommitted_teacher_attempts"]
                or restored.get("original_invalid_predictions_retained") is not True
                or restored.get("saved_first_forecast_batch") != through + 1
                or restored.get("failed_teacher_usage_unknown_not_zero") != (failed.get("usage") is None)):
            raise ValueError("Keep every retired timeout call, attempt and unknown usage in the lineage")
    train = read(ROOT / source["input_packet"])["rows"]
    expected = {(r["case_id"], r["family"]) for r in train if r["batch"] == through + 1}
    if len(expected) != 2 * source["batch_source_cases"]:
        raise ValueError("The continued batch must retain both task views of every original source")
    before, after = (read(d / f"batches/b{through + 1}_records.json") for d in (old_out, out))
    for role in ("ace", "empty", "empty_direct_numeric"):
        a = {(r["case_id"], r["family"]): r for r in before[role]}
        b = {(r["case_id"], r["family"]): r for r in after[role]}
        if (len(a) != len(before[role]) or len(b) != len(after[role])
                or set(a) != expected or set(b) != expected):
            raise ValueError("Keep the whole original B3 first-forecast denominator")
        for key in a:
            for field in ("raw_call_path", "parsed", "parse_error", "score"):
                if a[key][field] != b[key][field]:
                    raise ValueError("Continued B3 forecasts cannot be rescored or selected")
    return extras | {path, out / "continuation.json", *(ROOT / n for n in receipt["files"]),
            *(out / "publications" / f"b{b}.json" for b in range(1, through + 1)),
            *(out / "batches" / f"b{b}_records.json" for b in range(1, through + 2))}


def check_shared_actor_revision(name, expected, *, allow_phase_dispatch=False, adaptive=False):
    """Allow only the recorded teacher-log-only edit in the shared module.

    Final inference never calls Comparison.teacher_call. Every other AST node
    must match the original hash-bound source; all other actor files still
    require byte identity. The old source joins the final immutable freeze.
    """
    if allow_phase_dispatch and name in runtime_sources.HISTORICAL:
        return runtime_sources.verify_revision(ROOT, name, expected, adaptive=adaptive)
    current = ROOT / name
    if sha(current) == expected:
        return set()
    if name != "legal_skill_guard/learning/experiment.py":
        raise ValueError("Shared task actor/scorer changed since learning: " + name)
    original = ROOT / (
        "artifacts/research/openexempt_legal_scope_20261020/source_snapshots/"
        "experiment_before_teacher_timeout_logs_20261023.py")
    if not original.is_file() or sha(original) != expected:
        raise ValueError("Bind the actual pre-timeout shared module source")
    def inference_ast(text):
        tree = ast.parse(text)
        classes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Comparison"]
        if len(classes) != 1:
            raise ValueError("Expected the actual Comparison implementation")
        methods = classes[0].body
        removed = [n for n in methods if isinstance(n, ast.FunctionDef) and n.name == "teacher_call"]
        if len(removed) != 1:
            raise ValueError("Only the unused teacher transport method may differ")
        classes[0].body = [n for n in methods if n not in removed]
        tree.body = [n for n in tree.body if not (
            isinstance(n, ast.Import) and len(n.names) == 1
            and n.names[0].name == "subprocess" and n.names[0].asname is None)]
        if any(isinstance(n, ast.Name) and n.id == "subprocess" for n in ast.walk(tree)):
            raise ValueError("The new timeout import must not affect native inference")
        return ast.dump(tree, include_attributes=False)
    if inference_ast(original.read_text()) != inference_ast(current.read_text()):
        raise ValueError("A native actor/scorer node changed outside the teacher logging edit")
    return {original}


def check_learning_execution_versions(cfg, source_configs):
    """Bind original banks and explicitly amended controls to their real runtimes."""
    schedule = cfg.get("learning_execution_schedule")
    if cfg.get("evaluation_stage") == SUPPLEMENT_STAGE:
        if (schedule != runtime_sources.ADAPTIVE_SCHEDULE
                or cfg.get("learning_execution_schedule_protocol") != SUPPLEMENT_PROTOCOL):
            raise ValueError("Declare the actual adaptive/retained-control runtime boundary")
        extras = runtime_sources.validate_bundle(ROOT, adaptive=True) | {ROOT / SUPPLEMENT_PROTOCOL}
        if not (ROOT / SUPPLEMENT_PROTOCOL).is_file():
            raise ValueError("Bind the revised fixed-benchmark protocol")
        environments, main_environment = {}, None
        arms = {a["name"]: a for a in cfg["arms"]}
        for name, source in source_configs.items():
            if source.get("source_cases") == 0:
                continue
            arm = arms[name]
            frozen = read((ROOT / arm["source_config"]).with_suffix(".frozen.json"))
            out = ROOT / "runs" / source["run_id"]
            receipts = (read(out / "initialization.json"), read(out / "completion.json"))
            revised = arm["role"] in ("evolved", "B1_frozen")
            if revised:
                environment = runtime_sources.validate_adaptive_learning_receipt(
                    ROOT, source, frozen, *receipts)
                if main_environment is not None and environment != main_environment:
                    raise ValueError("The revised final bank and ownB1 need the same learning service")
                main_environment = environment
            else:
                if source.get("skill_commit_policy") == "adaptive_legal":
                    raise ValueError("A retained comparator cannot become an adaptive run")
                environment = runtime_sources.validate_learning_receipt(
                    ROOT, source, frozen, *receipts,
                    allow_uniform_control=arm["role"] == "ablation")
            limit = "4" if revised or arm["role"] == "ablation" else "1"
            environments.setdefault((str(environment), sha(environment)), set()).add(limit)
            extras.add(environment)
        current = ROOT / cfg["inference_environment"]
        if main_environment != current or not environments or any(len(v) != 1 for v in environments.values()):
            raise ValueError("The supplementary TEST uses the actual revised four-sequence service")
        normalized = []
        for (name, _), limits in environments.items():
            argv = list(read(Path(name))["actual_argv"])
            if argv.count("--max-num-seqs") != 1 or argv.index("--max-num-seqs") + 1 >= len(argv):
                raise ValueError("Capture the one actual service sequence limit")
            index = argv.index("--max-num-seqs")
            if argv[index + 1] != next(iter(limits)):
                raise ValueError("A retained or revised learning service has the wrong sequence limit")
            normalized.append(argv[:index] + argv[index + 2:])
        if any(argv != normalized[0] for argv in normalized[1:]):
            raise ValueError("Retained and revised actors must use the same weights and serving arguments")
        return extras
    if schedule is None:
        if any(source.get("phase_dispatch") is not None for source in source_configs.values()):
            raise ValueError("Declare the changed learning execution schedule before TEST")
        return set()
    uniform = schedule == runtime_sources.CONTROL_SCHEDULE
    protocol_name = runtime_sources.CONTROL_PROTOCOL if uniform else runtime_sources.PROTOCOL
    if (schedule not in (runtime_sources.SCHEDULE, runtime_sources.CONTROL_SCHEDULE)
            or cfg.get("learning_execution_schedule_protocol") != protocol_name):
        raise ValueError("Declare the exact prospective learning execution amendment")
    protocol = ROOT / protocol_name
    if not protocol.is_file():
        raise ValueError("Freeze the prospective learning execution protocol")
    extras, environments = runtime_sources.validate_bundle(ROOT) | {protocol}, {}
    for name, source in source_configs.items():
        if source.get("source_cases") == 0:
            continue  # The static author compiles public law; it does not run 8B learning.
        arm = next(a for a in cfg["arms"] if a["name"] == name)
        control = uniform and arm.get("role") == "ablation"
        if control and not runtime_sources.uniform_control(source):
            raise ValueError("Both replacement controls must use their declared new execution profile")
        frozen = read((ROOT / arm["source_config"]).with_suffix(".frozen.json"))
        out = ROOT / "runs" / source["run_id"]
        environment = runtime_sources.validate_learning_receipt(
            ROOT, source, frozen, read(out / "initialization.json"), read(out / "completion.json"),
            allow_uniform_control=control)
        seed = source["generation"]["seed"]
        group = "ablation45" if control else seed
        environments.setdefault(group, set()).add((str(environment), sha(environment)))
        extras.add(environment)
    initial = cfg.get("evaluation_stage") == INITIAL_STAGE
    seeds = (45,) if initial else LEARNING_SEEDS
    expected_groups = set(seeds) | ({"ablation45"} if uniform else set())
    if set(environments) != expected_groups or any(len(v) != 1 for v in environments.values()):
        raise ValueError("Main, ACE, Text and controls must match their actual within-seed environment")
    if not initial and environments[145] != environments[245]:
        raise ValueError("Both future repeat seeds must use the same captured new single-model environment")
    if uniform and not initial and environments["ablation45"] != environments[145]:
        raise ValueError("Future recipes must use the same captured replacement service as both controls")
    normalized_argv = []
    for group in environments:
        environment = Path(next(iter(environments[group]))[0])
        argv = list(read(environment)["actual_argv"])
        if (argv.count("--max-num-seqs") != 1
                or argv.index("--max-num-seqs") + 1 >= len(argv)):
            raise ValueError("Capture exactly one actual serving sequence limit")
        index = argv.index("--max-num-seqs")
        if argv[index + 1] != ("1" if group == 45 else "4"):
            raise ValueError("The actual service does not match the declared learning-seed boundary")
        normalized_argv.append(argv[:index] + argv[index + 2:])
    if any(argv != normalized_argv[0] for argv in normalized_argv[1:]):
        raise ValueError("The serving transition changed more than the declared sequence limit")
    if initial:
        current = ROOT / cfg["inference_environment"]
        if uniform and (str(current), sha(current)) not in environments["ablation45"]:
            raise ValueError("The common TEST must use the exact captured service of both controls")
        argv = list(read(current)["actual_argv"])
        if argv.count("--max-num-seqs") != 1:
            raise ValueError("Capture the one declared initial TEST service sequence limit")
        index = argv.index("--max-num-seqs")
        if argv[index + 1] != "4" or argv[:index] + argv[index + 2:] != normalized_argv[0]:
            raise ValueError("Initial TEST must use the same weights/dependencies with only the declared sequence change")
        extras.add(current)
    return extras


def check_future_learning_plan(cfg, source_configs):
    """Lock six actual recipes before initial TEST, not six nonexistent banks."""
    stage = cfg.get("evaluation_stage")
    if stage == SUPPLEMENT_STAGE:
        if cfg.get("future_learning_plan") is not None or cfg.get("future_learning_plan_sha256") is not None:
            raise ValueError("Independent learning repeats remain deferred, not a supplementary-stage recipe")
        return set()
    if stage not in (INITIAL_STAGE, FINAL_STAGE):
        return set()  # Small synthetic/legacy protocol checks never execute formal TEST.
    path = runtime_sources.checked_path(ROOT, cfg["future_learning_plan"])
    if (cfg.get("staged_comparison_protocol") != STAGED_PROTOCOL
            or cfg.get("experience_replication_design") is not None
            or sha(path) != cfg.get("future_learning_plan_sha256")):
        raise ValueError("Freeze the exact staged protocol and six-recipe plan before TEST")
    plan = read(path)
    if (plan.get("policy") != "six_recipes_frozen_before_initial_TEST_v1"
            or plan.get("no_TEST_feedback_to_learning") is not True
            or plan.get("future_builds_not_selected_using_initial_scores") is not True
            or plan.get("additional_learning_execution_authorization")
            != "deferred_until_user_review_after_teacher_draft"
            or plan.get("future_recipes_not_completed_banks") is not True):
        raise ValueError("Future recipes do not authorize repeats or score-selected later learning")
    entries = plan.get("learning", [])
    pairs = [(entry.get("kind"), entry.get("seed")) for entry in entries]
    required = {(kind, seed) for kind in ("main", "ace", "text") for seed in (145, 245)}
    if len(entries) != 6 or set(pairs) != required:
        raise ValueError("Predeclare all six additional learning recipes exactly once")
    templates = plan.get("planned_final_arms", [])
    planned = {arm["name"]: arm for arm in templates}
    initial_names = plan.get("initial_arm_names", [])
    actual = {arm["name"]: arm for arm in cfg["arms"]}
    if (len(templates) != 16 or len(planned) != 16 or len(initial_names) != 8
            or len(set(initial_names)) != 8 or not set(initial_names) <= set(planned)
            or set(actual) != (set(initial_names) if stage == INITIAL_STAGE else set(planned))):
        raise ValueError("Keep the exact initial8 subset and full planned16 matrix")
    extras = {path, ROOT / STAGED_PROTOCOL}
    prospective_sources, prospective_paths, run_ids = {}, set(), set()
    for entry in entries:
        config_path = runtime_sources.checked_path(ROOT, entry["source_config"])
        frozen_path = config_path.with_suffix(".frozen.json")
        source, frozen = read(config_path), read(frozen_path)
        if (config_path in prospective_paths or source["run_id"] in run_ids
                or sha(config_path) != entry.get("source_config_sha256")
                or sha(frozen_path) != entry.get("source_frozen_sha256")
                or frozen.get("config_sha256") != sha(config_path)):
            raise ValueError("A predeclared future config/frozen source changed or was duplicated")
        prospective_paths.add(config_path)
        run_ids.add(source["run_id"])
        kind = entry["kind"]
        learner = {"ace": "ace_native_online_v4", "text": "trace2skill_text_offline_v1"}.get(kind)
        # Main historic profiles identify the driver through policy, not a learner label.
        if (source["generation"]["seed"] != entry["seed"]
                or (kind != "main" and source.get("learner") != learner)
                or (kind == "main" and (source.get("skill_commit_policy"),
                    source.get("candidate_feedback_policy")) != ("legal_scope", "carry_partial_and_refine"))
                or source.get("phase_dispatch") != runtime_sources.DECLARATION
                or source.get("inference_environment") != cfg["inference_environment"]
                or source.get("initial_library_publication") or source.get("warm_source_case_ids")
                or source.get("initial_library_prior_exposure_distinct_sources", 0) != 0
                or source.get("continuation_receipt")
                or source.get("source_cases") != cfg["training_source_cases"]
                or source.get("batch_source_cases") != cfg["training_batch_source_cases"]
                or source.get("planned_batches") * source["batch_source_cases"] != source["source_cases"]
                or frozen["files"].get(source["input_packet"]) != cfg["training_packet_sha256"]):
            raise ValueError("Future learning must keep the declared seed, empty origin and TRAIN protocol")
        if any(frozen["files"].get(name) != digest for name, digest in runtime_sources.CURRENT.items()):
            raise ValueError("Each future recipe must freeze the complete declared runtime bundle")
        if stage == INITIAL_STAGE and (ROOT / "runs" / source["run_id"]).exists():
            raise ValueError("Initial TEST must precede every additional learning build")
        for name, digest in frozen["files"].items():
            item = runtime_sources.checked_path(ROOT, name)
            if sha(item) != digest:
                raise ValueError("A future learning source/input changed before TEST: " + name)
            extras.add(item)
        extras.update((config_path, frozen_path))
        expected_roles = {"evolved", "B1_frozen"} if kind == "main" else {"experience"}
        matching = [arm for arm in templates if arm.get("source_config") == entry["source_config"]]
        if (len(matching) != len(expected_roles) or {a["role"] for a in matching} != expected_roles
                or any(a["name"] in initial_names or a.get("bank_sha256") is not None
                       or a.get("backend") != ("ace" if kind == "ace" else "direct")
                       or a.get("source_config_sha256") != sha(config_path) for a in matching)):
            raise ValueError("Future templates must bind each recipe without inventing completed banks")
        prospective_sources.update({arm["name"]: source for arm in matching})
    if set(prospective_sources) != set(planned) - set(initial_names):
        raise ValueError("Every future matrix arm must map to its one predeclared recipe")
    for name, arm in actual.items():
        template = planned[name]
        if name in initial_names:
            if arm != template:
                raise ValueError("An original seed45 bank or role changed between evaluation stages")
        elif ({k: v for k, v in arm.items() if k != "bank_sha256"}
              != {k: v for k, v in template.items() if k != "bank_sha256"}
              or not isinstance(arm.get("bank_sha256"), str) or len(arm["bank_sha256"]) != 64):
            raise ValueError("Final future banks must use the original recipes, not selected replacements")
    primary = plan.get("primary_contrasts", [])
    secondary = plan.get("secondary_contrasts", [])
    projected = [{**contrast, "after": [n for n in contrast["after"] if n in initial_names],
                  "before": [n for n in contrast["before"] if n in initial_names]}
                 for contrast in primary]
    if (cfg["primary_contrasts"] != (projected if stage == INITIAL_STAGE else primary)
            or cfg["secondary_contrasts"] != secondary):
        raise ValueError("Do not select or relabel contrasts after the initial result")
    final = {**cfg, "evaluation_stage": FINAL_STAGE, "arms": templates,
             "primary_contrasts": primary, "secondary_contrasts": secondary}
    all_sources = {**source_configs, **prospective_sources}
    check_primary_contrasts(final, all_sources)
    check_secondary_contrasts(final, all_sources)
    return extras


def check_initial_evaluation(cfg):
    """The final table inherits the initial banks and raw outputs, never their scores."""
    reference = cfg.get("initial_evaluation")
    supplement = cfg.get("evaluation_stage") == SUPPLEMENT_STAGE
    if cfg.get("evaluation_stage") not in (FINAL_STAGE, SUPPLEMENT_STAGE):
        if reference is not None:
            raise ValueError("Only the final stage can reference a completed initial evaluation")
        return set()
    if not isinstance(reference, dict):
        raise ValueError("The final stage must preserve its completed initial8 evaluation")
    path = runtime_sources.checked_path(ROOT, reference["source_config"])
    frozen_path = path.with_suffix(".frozen.json")
    initial, bound = read(path), read(frozen_path)
    if (initial.get("evaluation_stage") != INITIAL_STAGE
            or sha(path) != reference.get("source_config_sha256")
            or bound.get("config_sha256") != sha(path)
            or sha(frozen_path) != reference.get("source_frozen_sha256")):
        raise ValueError("Bind the original initial-stage config and freeze, not a reconstructed table")
    common = ("input_packet", "grading_directory", "generation", "inference_environment",
              "source_cases", "training_packet_sha256") + (() if supplement else (
                  "staged_comparison_protocol", "future_learning_plan", "future_learning_plan_sha256"))
    if any(initial.get(key) != cfg.get(key) for key in common):
        raise ValueError("The final stage changed the initial TEST sources, decoding or future recipe plan")
    arms = {arm["name"]: arm for arm in cfg["arms"]}
    extras = {path, frozen_path}
    if supplement:
        retained = [a for a in initial["arms"] if a["role"] not in ("evolved", "B1_frozen")]
        replaced = {a["name"] for a in initial["arms"]} - {a["name"] for a in retained}
        revised = [a for a in cfg["arms"] if a["role"] in ("evolved", "B1_frozen")]
        if (len(initial["arms"]) != 8 or len(retained) != 6 or len(arms) != 8
                or len(revised) != 2 or {a["role"] for a in revised} != {"evolved", "B1_frozen"}
                or set(cfg.get("retained_initial_arms", [])) != {a["name"] for a in retained}
                or len(cfg.get("retained_initial_arms", [])) != 6
                or any(arms.get(a["name"]) != a for a in retained)
                or replaced & set(arms)):
            raise ValueError("Retain exactly six original conditions and replace both old main snapshots explicitly")
        snapshots = reference.get("preserved_source_snapshots", {})
        if not isinstance(snapshots, dict) or not set(snapshots) <= INITIAL_SOURCE_SNAPSHOTS:
            raise ValueError("Only explicitly unused old documentation/test/evaluator sources may use preserved bytes")
    else:
        planned_initial = read(ROOT / cfg["future_learning_plan"])["initial_arm_names"]
        if (len(initial["arms"]) != 8 or {a["name"] for a in initial["arms"]} != set(planned_initial)
                or any(arms.get(arm["name"]) != arm for arm in initial["arms"])):
            raise ValueError("The final stage must retain every original initial8 bank")
    used_snapshots = set()
    for name, digest in bound["files"].items():
        if sha(runtime_sources.checked_path(ROOT, name)) != digest:
            if supplement and name in runtime_sources.HISTORICAL:
                extras.update(runtime_sources.verify_revision(ROOT, name, digest, adaptive=True))
            elif supplement and name in snapshots:
                original = runtime_sources.checked_path(ROOT, snapshots[name])
                snapshot_dir = ROOT / ("artifacts/research/openexempt_legal_scope_20261020/"
                                       "source_snapshots/initial_eval_20261025")
                if not original.is_relative_to(snapshot_dir) or sha(original) != digest:
                    raise ValueError("The exact original initial-stage unused source changed: " + name)
                extras.add(original)
                used_snapshots.add(name)
            else:
                raise ValueError("An initial-stage frozen source/input changed: " + name)
    if supplement and used_snapshots != set(snapshots):
        raise ValueError("Preserved source snapshots must describe exactly the actual changed unused files")
    out = ROOT / "runs" / safe_component(initial["run_id"])
    if (out / "failure.json").exists():
        raise ValueError("A failed or partial initial TEST cannot be selected for reuse")
    for name, key in (("completion.json", "completion_sha256"),
                      ("predictions_before_any_grading.json", "predictions_sha256"),
                      ("native_origins_before_any_grading.json", "native_origins_sha256"),
                      ("terminal_preservation.json", "terminal_preservation_sha256")):
        item = out / name
        if sha(item) != reference.get(key):
            raise ValueError("The completed initial-stage provenance changed: " + name)
        extras.add(item)
    complete = read(out / "completion.json")
    if (complete.get("status") != "completed_frozen_comparison"
            or complete.get("evaluation_stage") != INITIAL_STAGE or complete.get("teacher_calls") != 0
            or complete.get("bank_sha256") != {a["name"]: a.get("bank_sha256", csha([]))
                                               for a in initial["arms"]}):
        raise ValueError("Require the completed original initial matrix, without teacher feedback")
    return extras


def check_source_disjoint_plan(cfg):
    """Validate the complete new design before opening any source or TEST data."""
    safe_component(cfg["run_id"])
    profile, protocol, target = source_disjoint_profile(cfg)
    utility = cfg.get("evaluation_stage") == UTILITY_SOURCE_DISJOINT_STAGE
    packet = UTILITY_SOURCE_DISJOINT_PACKET if utility else SOURCE_DISJOINT_PACKET
    packet_sha = UTILITY_SOURCE_DISJOINT_PACKET_SHA256 if utility else SOURCE_DISJOINT_PACKET_SHA256
    if (cfg.get("protocol") != protocol
            or cfg.get("statistics_plan") != protocol
            or cfg.get("evaluation_role") != "sealed_frozen_comparison"
            or cfg.get("final_matrix_frozen") is not True
            or cfg.get("no_validation_set") is not True
            or cfg.get("benchmark_development_status") != "source_disjoint_IID_frozen_bank_confirmation"
            or cfg.get("independent_learning_repetitions") != "user_deferred"
            or cfg.get("external_text_adaptation") != "trace2skill_text_offline_v1"
            or cfg.get("reference_arm") != "empty"
            or cfg.get("execution_contract") != "direct_statutory_claims"
            or cfg.get("execution_contract_version") != 14
            or cfg.get("library_token_hard_cap") != 4096
            or cfg.get("input_packet") != packet + "/inputs.json"
            or cfg.get("grading_directory") != packet + "/grading_only"
            or cfg.get("input_packet_sha256") != packet_sha
            or cfg.get("inference_request_workers") != 4
            or cfg.get("inference_dispatch_protocol") != DISPATCH_PROTOCOL
            or cfg.get("inference_dispatch_policy") != "four_workers_one_instance_exact_wire_lock_no_retry"
            or cfg.get("inference_environment") != "artifacts/live_8b_environment_phase_dispatch_20261025.json"
            or "teacher" in cfg or cfg.get("initial_evaluation") is not None
            or cfg.get("future_learning_plan") is not None):
        raise ValueError("Declare the source-disjoint frozen-bank design without learning or old TEST reuse")
    for key, expected in (("source_cases", 128), ("training_source_cases", 128),
                          ("training_batch_source_cases", 16)):
        if type(cfg.get(key)) is not int or cfg[key] != expected:
            raise ValueError("Retain the full 128-source, eight-by-sixteen learning comparison")
    if any(cfg.get("generation", {}).get(k) != v for k, v in FINAL_DECODING.items()):
        raise ValueError("Retain the common frozen decoding and native output budget")
    arms = cfg.get("arms", [])
    if len(arms) != len(profile) or {a.get("name") for a in arms} != set(profile):
        raise ValueError("Freeze every declared condition, including both interfaces of the same ACE bank")
    hashes = {"source_config_sha256", "source_frozen_sha256", "source_completion_sha256",
              "source_publication_sha256", "source_terminal_preservation_sha256", "bank_sha256"}
    for arm in arms:
        name = arm["name"]
        if (arm.get("role"), arm.get("backend"), arm.get("source_config")) != profile[name]:
            raise ValueError("Do not rename historical banks or replace the matched policy sources")
        fields = {"name", "role", "backend"}
        if name != "empty":
            fields |= {"source_config", *hashes}
        if name == "ACE_common45":
            fields |= {"representation_artifact", "representation_sha256"}
        if utility and name in {"utility45", "utility_own_B1_45", "strict45", "no_execution45", "projection45"}:
            fields |= {"source_snapshot", "source_snapshot_sha256"}
        if set(arm) != fields:
            raise ValueError("Bind each actual source, final publication and representation explicitly")
        for key in fields & (hashes | {"representation_sha256", "source_snapshot_sha256"}):
            value = arm[key]
            if not isinstance(value, str) or len(value) != 64 or set(value) - set("0123456789abcdef"):
                raise ValueError("Completed source hashes, not placeholders, are required")
    primary = cfg.get("primary_contrasts", [])
    expected = {(target, name) for name in profile if name != target}
    actual = {(c["after"][0], c["before"][0]) for c in primary
              if len(c.get("after", [])) == len(c.get("before", [])) == 1}
    if (len(primary) != len(profile) - 1 or len({c["name"] for c in primary}) != len(profile) - 1
            or actual != expected or cfg.get("secondary_contrasts", []) != []):
        raise ValueError("Keep every declared paired contrast in one native-endpoint primary family")
    for arm in arms:
        if arm["role"] == "evolved":
            own_B1_reference(cfg, arm)


def ace_common_direct_bank(playbook):
    """Lossless inference-only wrapper, not a rewritten or newly learned ACE bank."""
    if not isinstance(playbook, str):
        raise ValueError("The actual native ACE playbook must be text")
    return [{"id": "ace-document", "hypothesis_ids": ["EC", "EV"], "guidance": {
        "jurisdiction": "ALL", "operators": [], "by_task": [{"tasks": ["EC", "EV"],
            "when": "Apply relevant instructions from this complete learned skill.",
            "procedure": playbook,
            "avoid_when": "Respect the skill's stated conditions and exceptions."}]}}]


def continued_source_snapshot(digest):
    """Resolve only the three exact, preserved execution epochs for this stage."""
    if digest == CONTINUED_ONLINE_SHA256:
        path = ROOT / "experiments/openexempt_online.py"
    elif digest in CONTINUED_SOURCE_SNAPSHOTS:
        path = ROOT / ("artifacts/research/openexempt_legal_scope_20261020/"
            "source_snapshots/continued_eval_20261029/"
            f"{CONTINUED_SOURCE_SNAPSHOTS[digest]}__{digest}.py")
    else:
        raise ValueError("No approved continued-bank source epoch for this hash")
    if not path.is_file() or sha(path) != digest:
        raise ValueError("The exact preserved continued-bank source changed")
    return path


def continued_bank_source(name, source, frozen, complete, publication, out, main, main_frozen):
    """Validate real TRAIN continuation, never select a proposal by its scores."""
    coordinate = name == "task_consolidated45"
    policy = "task_projection_coordinate" if coordinate else "joint_fixed_steps"
    digest = ("a6d5e0be6b87b230c8a777535a0ddda2dab126cf5c4fa188b54ddda4d4611a66"
              if coordinate else CONTINUED_ONLINE_SHA256)
    shared = ("generation", "phase_dispatch", "input_packet", "grading_directory",
              "inference_environment", "execution_contract", "execution_contract_version")
    if (source.get("training_phase") != CONSOLIDATION_PHASE
            or source.get("teacher_update_policy") != policy
            or source.get("teacher_evidence_contract") != "native_claim_task_projection_updates_v5"
            or source.get("candidate_feedback_policy") != "carry_partial_and_refine"
            or source.get("max_candidate_attempts") != 2
            or source.get("task_update_schedule") != (["EC", "EV"] if coordinate else None)
            or source.get("source_cases") != 128 or source.get("batch_source_cases") != 16
            or source.get("planned_batches") != 1
            or source.get("library_token_hard_cap") != 4096
            or source.get("skill_commit_policy") != "adaptive_legal"
            or source.get("adaptive_commit_objective") != "seen_source_min_family_gain_then_mean_v1"
            or source.get("initial_library_prior_exposure_distinct_sources") != 128
            or source.get("consolidation_parent_run") != main["run_id"]
            or source.get("consolidation_parent_config") != SOURCE_DISJOINT_ARMS["native_claim45"][2]
            or source.get("initial_library_publication") != f"runs/{main['run_id']}/publications/b8.json"
            or any(source.get(k) != main.get(k) for k in shared)
            or frozen["files"].get("experiments/openexempt_online.py") != digest
            or frozen["files"].get(source["input_packet"])
                != main_frozen["files"].get(main["input_packet"])
            or frozen["packages"] != main_frozen["packages"]
            or any(frozen["files"].get(p) != h for p, h in main_frozen["files"].items()
                   if p.startswith("legal_skill_guard/"))
            or complete.get("status") != "completed_seen_TRAIN_consolidation"
            or complete.get("training_phase") != CONSOLIDATION_PHASE
            or complete.get("execution_dispatch") != main["phase_dispatch"]
            or complete.get("actual_teacher_responses") != 2
            or not 0 <= complete.get("actual_native_calls", -1) <= (256 if coordinate else 512)):
        raise ValueError("Require the actual declared completed continuation and its exact source epoch")
    rows, before, _, _, parent_sources, parent_complete = observed_consolidation_inputs(source)
    parent_path = ROOT / source["initial_library_publication"]
    parent = read(parent_path)["bank"]
    initial_path, start_path = out / "initialization.json", out / "consolidation_started.json"
    result_path = out / "consolidation_result.json"
    initial, start, result = read(initial_path), read(start_path), read(result_path)
    if (initial.get("bank") != parent or initial.get("initial_case_exposure") != 128
            or initial.get("parent_publication") != source["initial_library_publication"]
            or start.get("parent_bank_sha256") != csha(parent)
            or start.get("prior_source_exposure") != 128
            or start.get("imported_exact_native_origins") != 512
            or start.get("all_seen_source_ids") != sorted({r["case_id"] for r in rows})
            or start.get("before_metrics") != metrics(before)
            or publication.get("parent_bank_sha256") != csha(parent)
            or publication.get("teacher_update_policy") != policy
            or len(publication.get("training_decisions", [])) != 2):
        raise ValueError("A continuation must start from the same actual B8 and full observed TRAIN population")
    extras = {*parent_sources, parent_path, initial_path, start_path, result_path,
              continued_source_snapshot(digest)}
    actual_bank, actual_records = parent, before
    grid = {(r["case_id"], r["family"]) for r in rows}
    for step, decision in enumerate(publication["training_decisions"], 1):
        wire_path = out / "teacher" / f"b1_candidate{step}" / "wire_request.json"
        response_path = wire_path.with_name("response.json")
        body = json.loads(read(wire_path)["user_prompt"])
        task = tuple(FAMILIES)[step - 1] if coordinate else None
        evidence = body["already_seen_training"]
        families = {r["family"] for r in evidence}
        if (csha(body["current_parent_library"]) != csha(actual_bank)
                or body.get("teaching_task") != task
                or len(evidence) > 32
                or families != ({task} if coordinate else set(FAMILIES))
                or body["training_evidence_manifest"]["consolidation_scope"]
                    ["all_optimization_source_ids"] != start["all_seen_source_ids"]):
            raise ValueError("Both scheduled teachers must use their actual parent and bounded task evidence")
        extras.update((wire_path, response_path))
        if not response_path.is_file():
            raise ValueError("A declared teacher opportunity needs its actual completed response")
        if decision.get("accepted"):
            bank, records = decision["candidate"], decision["actual_replay"]
            if (decision.get("attempt_parent_bank_sha256") != csha(actual_bank)
                    or len(records) != len(grid)
                    or {(r["case_id"], r["family"]) for r in records} != grid
                    or any(r["bank_sha256"] != csha(bank) for r in records)):
                raise ValueError("Use only actual committed TRAIN states, never the last rejected proposal")
            actual_bank, actual_records = bank, records
    if (publication["bank"] != actual_bank or complete.get("bank") != actual_bank
            or publication.get("bank_sha256") != csha(actual_bank)
            or result.get("bank_sha256") != csha(actual_bank)
            or result.get("before") != metrics(before) or result.get("after") != metrics(actual_records)
            or result.get("actual_new_teacher_responses") != 2
            or result.get("linked_acquisition_teacher_responses") != parent_complete["actual_teacher_responses"]
            or result.get("total_linked_teacher_responses") != parent_complete["actual_teacher_responses"] + 2
            or complete.get("consolidation_result") != result):
        raise ValueError("The final bank and all costs must retain the actual acquisition/continuation chain")
    return actual_bank, extras


def utility_source_disjoint_banks(cfg):
    """Close actual v6/predecessor learning and retained banks before new questions."""
    check_source_disjoint_plan(cfg)
    evaluation_request_workers(cfg)
    extras = {ROOT / UTILITY_SOURCE_DISJOINT_PROTOCOL, ROOT / DISPATCH_PROTOCOL,
              ROOT / cfg["inference_environment"]}

    def checked(name, digest):
        path = runtime_sources.checked_path(ROOT, name)
        if sha(path) != digest:
            raise ValueError("An actual utility-epoch source changed: " + name)
        extras.add(path)
        return path

    main_path = checked(UTILITY_SOURCE_DISJOINT_ARMS["utility45"][2],
        "5e0486a5352d2e534b50265e3b902ac3aaa0c7d2c5107dd2b904f20a3191e894")
    main_frozen_path = checked(str(main_path.with_suffix(".frozen.json").relative_to(ROOT)),
        "182e6cbf98e6ee7da8801ad7874554da50a071a91a8a4297e20d87b4fbea30ef")
    main, main_frozen = read(main_path), read(main_frozen_path)
    main_out = ROOT / "runs" / safe_component(main["run_id"])
    if (not (main_out / "completion.json").is_file()
            or not (main_out / "terminal_preservation.json").is_file()
            or (main_out / "failure.json").exists()):
        raise ValueError("Finish and preserve the actual full v6 main before opening a new evaluation")
    for name, digest in SOURCE_DISJOINT_LEGACY_RECEIPTS.items():
        checked(name, digest)
    legacy_cfg = read(ROOT / "configs/openexempt_adaptive_supplement_TEST128_20261027_run01.json")
    legacy_frozen = read(ROOT / "configs/openexempt_adaptive_supplement_TEST128_20261027_run01.frozen.json")
    if legacy_frozen["files"].get("experiments/openexempt_frozen_eval.py") != (
            "b1430ca922add90a361cf04c0943597ef3374d25264bcabd096b2106d264915a"):
        raise ValueError("Retain the actual validated comparator epoch")
    for name in ACE_ACTOR_FILES:
        digest = legacy_frozen["files"].get(name)
        if not digest:
            raise ValueError("The original comparison must bind every native ACE actor source")
        checked(name, digest)
    construction = read(checked(
        "artifacts/research/openexempt_legal_scope_20261020/"
        "Next_IID128_confirmatory_20261030_fixed_seed_zero_overlap564_sources_dual_sealed_not_evaluated.json",
        "80d3a962df82247a4e5f55c45af838e384f15d2c839a89c6e075f5513b2ae589"))
    packet = ROOT / UTILITY_SOURCE_DISJOINT_PACKET
    checked(str((packet / "inputs.json").relative_to(ROOT)), UTILITY_SOURCE_DISJOINT_PACKET_SHA256)
    selection, key_data = read(packet / "preselection.json"), read(packet / "exclusion_source_keys.json")
    recipe_path = ROOT / "configs/openexempt_IID128_confirmatory_TEST_20261030_recipe.json"
    recipe = read(recipe_path)
    if (construction.get("source_overlap") != 0 or construction.get("source_cases") != 128
            or construction.get("input_packet_sha256") != UTILITY_SOURCE_DISJOINT_PACKET_SHA256
            or selection.get("seed") != 2026103001 or selection.get("source_cases") != 128
            or selection.get("tasks") != 256 or selection.get("preselected_source_case_ids") != []
            or selection.get("original_generator_unmodified") is not True
            or selection.get("input_packet_sha256") != UTILITY_SOURCE_DISJOINT_PACKET_SHA256
            or key_data.get("input_packet_sha256") != UTILITY_SOURCE_DISJOINT_PACKET_SHA256
            or len(set(key_data.get("source_keys", []))) != 128
            or set(selection.get("source_keys", [])) != set(key_data["source_keys"])
            or recipe.get("dataset_seed") != 2026103001 or recipe.get("source_cases") != 128):
        raise ValueError("Keep the original one-shot ff29 construction and source identities")
    extras.update((packet / "preselection.json", packet / "exclusion_source_keys.json", recipe_path))
    installed = {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()}
    if (installed != main_frozen["packages"] or cfg["generation"] != main["generation"]
            or cfg["inference_environment"] != main["inference_environment"]):
        raise ValueError("Keep the actual original8B packages, service capture and decoding")
    critical = {p: h for p, h in main_frozen["files"].items() if p.startswith("legal_skill_guard/")}
    if not critical or any(sha(ROOT / p) != h for p, h in critical.items()):
        raise ValueError("The common task, decoder, scorer or native transport changed")
    extras.update(ROOT / p for p in critical)
    checked(main["input_packet"], cfg["training_packet_sha256"])
    train = read(ROOT / main["input_packet"])["rows"]
    source_ids = sorted({r["case_id"] for r in train})
    train_keys = {r["source_key"] for r in train}
    if len(train) != 256 or len(source_ids) != 128 or len(train_keys) != 128 or train_keys & set(key_data["source_keys"]):
        raise ValueError("Use all original TRAIN128, disjoint from the new IID source keys")
    main_arm = next(a for a in cfg["arms"] if a["name"] == "utility45")
    main_snapshot = checked(main_arm["source_snapshot"], main_arm["source_snapshot_sha256"])
    if sha(main_snapshot) != main_frozen["files"]["experiments/openexempt_online.py"]:
        raise ValueError("The main source snapshot must be its actual learning-freeze bytes")

    def same_actor(snapshot):
        protected = ("actor_payload", "direct_case_input", "direct_request_key", "Online.answer", "Online.grade")
        current = ROOT / "experiments/openexempt_online.py"
        def constants(path):
            return {target.id: ast.dump(node.value, include_attributes=False)
                    for node in ast.parse(path.read_text()).body if isinstance(node, ast.Assign)
                    for target in node.targets if isinstance(target, ast.Name)}
        reference = constants(main_snapshot)
        for path in (snapshot, current):
            observed = constants(path)
            if (any(runtime_sources.function_ast(main_snapshot, key) != runtime_sources.function_ast(path, key)
                    for key in protected)
                    or any(reference[k] != observed.get(k) for k in
                           ("ACTOR_SYSTEM", "DIRECT_NUMERIC_SYSTEM", "PROGRAM_ACTOR_SYSTEM"))):
                raise ValueError("Teaching revisions must not change the frozen actor interface")

    same_actor(main_snapshot)
    banks = {}
    for arm in cfg["arms"]:
        name, role = arm["name"], arm["role"]
        if name == "empty":
            banks[name] = []
            continue
        path = checked(arm["source_config"], arm["source_config_sha256"])
        frozen_path = checked(str(path.with_suffix(".frozen.json").relative_to(ROOT)), arm["source_frozen_sha256"])
        source, frozen = read(path), read(frozen_path)
        if frozen["config_sha256"] != sha(path) or any(source["generation"].get(k) != cfg["generation"].get(k)
                for k in (*FINAL_DECODING, "base_url", "model", "model_root")):
            raise ValueError("Every source must retain its actual freeze and original executor settings")
        out = ROOT / "runs" / safe_component(source["run_id"])
        complete_path = checked(str((out / "completion.json").relative_to(ROOT)), arm["source_completion_sha256"])
        checked(str((out / "terminal_preservation.json").relative_to(ROOT)), arm["source_terminal_preservation_sha256"])
        if (out / "failure.json").exists():
            raise ValueError("A failed or incomplete construction cannot supply a final bank")
        complete = read(complete_path)
        publication_name = ("publication.json" if name == "static" else "publications/final.json"
                            if name == "text45" else "publications/b1.json" if role == "B1_frozen"
                            else "publications/b8.json")
        publication_path = checked(str((out / publication_name).relative_to(ROOT)), arm["source_publication_sha256"])
        publication = read(publication_path)
        retained = name in {"static", "ACE45", "ACE_common45", "text45"}
        if retained:
            old_name = "ACE45" if name == "ACE_common45" else name
            old = next(a for a in legacy_cfg["arms"] if a["name"] == old_name)
            if old["source_config"] != arm["source_config"]:
                raise ValueError("Retain the declared existing comparator construction")
            for item in (path, frozen_path, complete_path, publication_path):
                if legacy_frozen["files"].get(str(item.relative_to(ROOT))) != sha(item):
                    raise ValueError("The already-validated comparator construction changed")
            if name != "static" and (source.get("source_cases") != 128
                    or source.get("planned_batches") != 8 or source.get("batch_source_cases") != 16
                    or frozen["files"].get(source["input_packet"]) != cfg["training_packet_sha256"]):
                raise ValueError("Retained experience banks must use the same complete TRAIN128")
            if name == "static":
                if (complete["status"] != "compiled_law_only_static_bank_not_evaluated"
                        or source.get("source_cases") != 0 or publication.get("training_sources_seen") != 0
                        or publication.get("actual_native_generations") != 0):
                    raise ValueError("Static must remain the original blind law-only compilation")
                bank = publication["bank"]
            elif name in {"ACE45", "ACE_common45"}:
                if (complete["status"] != "completed_declared_ACE_adaptation_stream"
                        or len(complete["batch_summary"]) != 8
                        or publication["playbook"] != complete["final_playbook"]):
                    raise ValueError("Use ACE's actual final eight-batch playbook")
                bank = publication["playbook"]
            else:
                if (complete["status"] != "completed_trace2skill_text_offline_adaptation"
                        or publication["bank"] != complete["final_bank"]
                        or trace2skill_actor_bank(publication["files"]) != publication["bank"]
                        or publication["files_sha256"] != csha(publication["files"])
                        or complete["final_files_sha256"] != publication["files_sha256"]):
                    raise ValueError("Retain all files of the completed Text adaptation")
                bank = publication["bank"]
        else:
            snapshot = checked(arm["source_snapshot"], arm["source_snapshot_sha256"])
            if sha(snapshot) != frozen["files"].get("experiments/openexempt_online.py"):
                raise ValueError("Bind each learner's actual source, including historical versions")
            same_actor(snapshot)
            allowed = {"run_id", "protocol"}
            if name == "strict45":
                allowed |= {"admission_contract", "adaptive_commit_objective"}
                if (source.get("admission_contract") != "strict_native_full_counts_v1"
                        or source.get("adaptive_commit_objective") != "seen_source_min_family_gain_then_mean_v1"):
                    raise ValueError("The strict control changes the declared admission/selection bundle")
            elif name == "no_execution45":
                allowed.add("teacher_execution_evidence_visible")
                if source.get("teacher_execution_evidence_visible") is not False:
                    raise ValueError("The teacher-evidence control must explicitly withhold execution outcomes")
                entry = "experiments/openexempt_teacher_evidence_control.py"
                if not frozen["files"].get(entry):
                    raise ValueError("Bind the actual separate teacher-control serialization entry")
                checked(entry, frozen["files"][entry])
            elif name == "projection45":
                allowed |= {"teacher_evidence_contract", "admission_contract", "feedback_retention", "adaptive_commit_objective"}
                if (source.get("teacher_evidence_contract") != "native_claim_task_projection_updates_v5"
                        or csha(complete["bank"]) != "02b119a968c76f1e8a2c359f6d35e950012b53f83c9dc08251874401fd7e5702"):
                    raise ValueError("The seventh bank is a historical version, not a matched v6 ablation")
            if (any(source.get(k) != main.get(k) for k in (set(source) | set(main)) - allowed)
                    or frozen["packages"] != main_frozen["packages"]
                    or any(frozen["files"].get(p) != h for p, h in critical.items())
                    or source.get("source_cases") != 128 or source.get("planned_batches") != 8
                    or source.get("batch_source_cases") != 16 or source.get("initial_library_publication")
                    or source.get("warm_source_case_ids")
                    or complete["status"] != "completed_bounded_mechanism_study"
                    or len(complete["batch_summary"]) != 8 or complete.get("actual_teacher_responses") != 16
                    or complete["execution_dispatch"] != main["phase_dispatch"]
                    or frozen["files"].get(source["input_packet"]) != cfg["training_packet_sha256"]):
                raise ValueError("Require the complete declared empty-origin eight-batch method/control")
            initial_path = out / "initialization.json"
            initial = read(initial_path)
            if initial["bank"] != [] or initial.get("parent_publication") is not None or initial.get("initial_case_exposure", 0) != 0:
                raise ValueError("No historical library or extra TRAIN exposure may enter a cold build")
            extras.add(initial_path)
            previous = csha([])
            for batch in range(1, 9):
                pub_path = out / "publications" / f"b{batch}.json"
                first_path = out / "batches" / f"b{batch}_prequential.json"
                records_path = out / "batches" / f"b{batch}_prequential_records.json"
                saved, first, first_records = read(pub_path), read(first_path), read(records_path)["skills"]
                ids = set(source_ids[(batch - 1) * 16:batch * 16])
                grid = {(r["case_id"], r["family"], r["source_key"]) for r in train if r["case_id"] in ids}
                if (saved["parent_bank_sha256"] != previous or first["parent_bank_sha256"] != previous
                        or saved["bank_sha256"] != csha(saved["bank"])
                        or first["source_cases"] != 16 or first["tasks_per_arm"] != 32
                        or len(first_records) != 32
                        or {(r["case_id"], r["family"], r["source_key"]) for r in first_records} != grid):
                    raise ValueError("Preserve every original chronological source and actual publication")
                previous = saved["bank_sha256"]
                extras.update((pub_path, first_path, records_path))
                if name == "no_execution45":
                    for attempt in (1, 2):
                        request_path = out / "teacher" / f"b{batch}_candidate{attempt}" / "wire_request.json"
                        request = read(request_path)
                        body = json.loads(request["user_prompt"])
                        validate_withheld_request(request["system_prompt"], body)
                        for case in body["already_seen_training"]:
                            row = next(r for r in train if r["case_id"] == case["source_case_id"]
                                       and r["family"] == case["family"])
                            target_path = ROOT / source["grading_directory"] / f"{row['case_id']}.json"
                            if (case["facts"] != row["components"]["facts"]
                                    or case["public_solved_steps"] != row["components"]["solved_steps"]
                                    or case["public_asset_reference_catalog"] != public_asset_catalog(row)
                                    or body["complete_public_statutes"].get(case["public_statutes_ref"])
                                       != row["components"]["statutes"]
                                    or case["original_training_target"] != read(target_path)["targets"][row["family"]]):
                                raise ValueError("Retain each selected original TRAIN target and all public case context")
                        extras.add(request_path)
            bank = publication["bank"]
            if role == "B1_frozen":
                snapshot_path = out / "frozen_after_B1.json"
                snap = read(snapshot_path)
                if (snap.get("bank") != bank or snap.get("bank_sha256") != csha(bank)
                        or snap.get("publication_bank_sha256") != csha(bank)
                        or snap.get("freeze_after_exactly_batch") != 1
                        or snap.get("not_selected_by_later_performance_or_nonempty_success") is not True
                        or snap.get("evaluation_only_never_teacher_or_admission_feedback") is not True):
                    raise ValueError("Use the learner's actual time-fixed B1 snapshot")
                extras.add(snapshot_path)
            elif bank != complete["bank"] or csha(bank) != previous:
                raise ValueError("Use the actual B8 publication even if its last proposals were rejected")
        if name == "ACE_common45":
            wrapped = read(checked(arm["representation_artifact"], arm["representation_sha256"]))
            if wrapped != ace_common_direct_bank(bank):
                raise ValueError("The shared ACE representation must retain the entire learned playbook")
            bank = wrapped
        if csha(bank) != arm["bank_sha256"]:
            raise ValueError("The actual bank differs from the prebound final comparison")
        if arm["backend"] == "direct":
            validate_scoped_bank(bank)
            if any(s["guidance"]["operators"] for s in bank):
                raise ValueError("Direct inference must not introduce a hidden numerical solver")
        banks[name] = bank
    return banks, train_keys, extras


def source_disjoint_banks(cfg):
    """Read only TRAIN provenance, sealed metadata and already-validated old banks.

    The former evaluation's sealed source receipts establish the retained bank
    constructions; its predictions and scores are never imported. Every arm is
    executed afresh on the new packet under this explicitly new inference epoch.
    """
    if cfg.get("evaluation_stage") == UTILITY_SOURCE_DISJOINT_STAGE:
        return utility_source_disjoint_banks(cfg)
    check_source_disjoint_plan(cfg)
    evaluation_request_workers(cfg)
    profile, protocol, _ = source_disjoint_profile(cfg)
    continued = cfg["evaluation_stage"] == CONTINUED_SOURCE_DISJOINT_STAGE
    extras = {ROOT / protocol, ROOT / DISPATCH_PROTOCOL,
              ROOT / cfg["inference_environment"]}

    def checked(name, expected):
        path = runtime_sources.checked_path(ROOT, name)
        if sha(path) != expected:
            raise ValueError("An explicitly bound source artifact changed: " + name)
        extras.add(path)
        return path

    for name, digest in SOURCE_DISJOINT_LEGACY_RECEIPTS.items():
        checked(name, digest)
    legacy_cfg = read(ROOT / "configs/openexempt_adaptive_supplement_TEST128_20261027_run01.json")
    legacy_frozen = read(ROOT / "configs/openexempt_adaptive_supplement_TEST128_20261027_run01.frozen.json")
    if legacy_frozen["files"].get("experiments/openexempt_frozen_eval.py") != (
            "b1430ca922add90a361cf04c0943597ef3374d25264bcabd096b2106d264915a"):
        raise ValueError("The retained bank receipt must come from its actual validated runtime")
    metadata_path = ROOT / SOURCE_DISJOINT_PACKET / "construction_completion.json"
    metadata = read(metadata_path)
    key_path = ROOT / SOURCE_DISJOINT_PACKET / "exclusion_source_keys.json"
    key_data = read(key_path)
    checked(SOURCE_DISJOINT_PACKET + "/inputs.json", SOURCE_DISJOINT_PACKET_SHA256)
    if (metadata.get("status") != "generated_sealed_not_predicted_or_graded"
            or metadata.get("source_cases") != 128 or metadata.get("task_views") != 256
            or metadata.get("dataset_seed") != 2026102701
            or metadata.get("input_packet_sha256") != SOURCE_DISJOINT_PACKET_SHA256
            or metadata.get("historical_overlap") != 0
            or metadata.get("semantic_case_and_label_review_performed") is not False
            or key_data.get("input_packet_sha256") != SOURCE_DISJOINT_PACKET_SHA256
            or key_data.get("source_cases") != 128
            or len(set(key_data.get("source_keys", []))) != 128
            or metadata["all_new_packet_files_sha256_before_status"].get(str(key_path.relative_to(ROOT)))
                != sha(key_path)):
        raise ValueError("Retain the original one-shot sealed IID construction and source keys")
    extras.update((metadata_path, key_path, ROOT / SOURCE_DISJOINT_PACKET / "preselection.json"))
    main_path = ROOT / SOURCE_DISJOINT_ARMS["native_claim45"][2]
    main, main_frozen = read(main_path), read(main_path.with_suffix(".frozen.json"))
    if (sha(main_path) != "36a34352d4bc9e300a2d38c6914477d411eaa8e9c0d5e3dfb4e4735f6a4a5eb6"
            or main_frozen["config_sha256"] != sha(main_path)
            or cfg["generation"] != main["generation"]
            or cfg["inference_environment"] != main["inference_environment"]):
        raise ValueError("Use the actual third formal method and captured single-model environment")
    installed = {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()}
    if (installed != main_frozen["packages"]
            or main_frozen["files"].get(cfg["inference_environment"])
                != sha(ROOT / cfg["inference_environment"])):
        raise ValueError("Keep the actual third-run packages and immutable model-service capture")
    critical = {p: h for p, h in main_frozen["files"].items()
                if p.startswith("legal_skill_guard/") or p == "experiments/openexempt_online.py"}
    if not critical:
        raise ValueError("The current common actor/learning source differs from the actual third epoch")
    if continued:
        if critical.get("experiments/openexempt_online.py") != (
                "3213e92d8e3a3c2c3b4e565dd3553a17ba9b2e425e68e607232749363e8c1985"):
            raise ValueError("The actual third acquisition source must retain its original version")
        original = continued_source_snapshot(critical["experiments/openexempt_online.py"])
        current = continued_source_snapshot(CONTINUED_ONLINE_SHA256)
        protected = ("actor_payload", "direct_case_input", "direct_request_key", "acceptance",
                     "task_admission", "legal_scope_admission", "Online.answer", "Online.grade",
                     "Online.composed_replay")
        def constants(path):
            return {target.id: ast.dump(node.value, include_attributes=False)
                    for node in ast.parse(path.read_text()).body if isinstance(node, ast.Assign)
                    for target in node.targets if isinstance(target, ast.Name)}
        old_constants, current_constants = constants(original), constants(current)
        if (any(runtime_sources.function_ast(original, key) != runtime_sources.function_ast(current, key)
                for key in protected)
                or any(old_constants[key] != current_constants[key] for key in
                       ("ACTOR_SYSTEM", "DIRECT_NUMERIC_SYSTEM", "PROGRAM_ACTOR_SYSTEM"))
                or any(sha(ROOT / p) != h for p, h in critical.items()
                       if p != "experiments/openexempt_online.py")):
            raise ValueError("Only the approved teaching changes may differ; the actual actor/scorer/gates must match")
        extras.update((original, current))
    elif any(sha(ROOT / p) != h for p, h in critical.items()):
        raise ValueError("The current common actor/learning source differs from the actual third epoch")
    extras.update(ROOT / p for p in critical)
    if main_frozen["files"].get(main["input_packet"]) != cfg["training_packet_sha256"]:
        raise ValueError("Bind the actual original TRAIN packet before provenance checks")
    if continued:
        checked(main["input_packet"], cfg["training_packet_sha256"])
    train_rows = read(ROOT / main["input_packet"])["rows"]
    source_ids = sorted({r["case_id"] for r in train_rows})
    if len(source_ids) != 128 or len(train_rows) != 256:
        raise ValueError("Retain the complete original TRAIN source grid")
    banks, train_keys = {}, set()
    for arm in cfg["arms"]:
        name, role = arm["name"], arm["role"]
        if name == "empty":
            banks[name] = []
            continue
        path = checked(arm["source_config"], arm["source_config_sha256"])
        frozen_path = checked(str(path.with_suffix(".frozen.json").relative_to(ROOT)), arm["source_frozen_sha256"])
        source, frozen = read(path), read(frozen_path)
        if frozen["config_sha256"] != sha(path):
            raise ValueError("A source config no longer matches its learning freeze")
        if any(source["generation"].get(k) != cfg["generation"].get(k)
               for k in (*FINAL_DECODING, "base_url", "model", "model_root")):
            raise ValueError("Retain the same executor, model and generation budget for every bank")
        out = ROOT / "runs" / safe_component(source["run_id"])
        complete_path = checked(str((out / "completion.json").relative_to(ROOT)), arm["source_completion_sha256"])
        terminal = checked(str((out / "terminal_preservation.json").relative_to(ROOT)), arm["source_terminal_preservation_sha256"])
        if (out / "failure.json").exists():
            raise ValueError("A failed learner is not a completed final-bank condition")
        complete = read(complete_path)
        legacy_name = "ACE45" if name == "ACE_common45" else name
        retained = name in {"static", "ACE45", "ACE_common45", "text45"}
        if retained:
            old = next(a for a in legacy_cfg["arms"] if a["name"] == legacy_name)
            if (old["source_config"] != arm["source_config"]
                    or old["source_config_sha256"] != arm["source_config_sha256"]):
                raise ValueError("Retain the actual already-validated comparator construction")
        publication_name = ("publication.json" if name == "static" else
                            "publications/final.json" if name == "text45" else
                            "publications/b1.json" if role == "B1_frozen" or
                            name in {"task_consolidated45", "joint_consolidated45"}
                            else "publications/b8.json")
        publication_path = checked(str((out / publication_name).relative_to(ROOT)), arm["source_publication_sha256"])
        publication = read(publication_path)
        if retained:
            for item in (path, frozen_path, complete_path, publication_path):
                relative = str(item.relative_to(ROOT))
                if legacy_frozen["files"].get(relative) != sha(item):
                    raise ValueError("The retained bank's validated construction bytes changed")
        if name == "static":
            if (complete["status"] != "compiled_law_only_static_bank_not_evaluated"
                    or source.get("source_cases") != 0 or source.get("planned_batches") != 0
                    or publication.get("training_sources_seen") != 0
                    or publication.get("actual_native_generations") != 0):
                raise ValueError("Static must remain the original blind zero-case law compilation")
            bank = publication["bank"]
        elif continued and name in {"task_consolidated45", "joint_consolidated45"}:
            bank, continuation_sources = continued_bank_source(
                name, source, frozen, complete, publication, out, main, main_frozen)
            extras.update(continuation_sources)
        else:
            if (source.get("source_cases") != 128 or source.get("batch_source_cases") != 16
                    or source.get("planned_batches") != 8
                    or frozen["files"].get(source["input_packet"]) != cfg["training_packet_sha256"]):
                raise ValueError("All learned banks must use the original full TRAIN128 packet")
            receipt_path = (ROOT / source["input_packet"]).parent / "preselection.json"
            receipt = read(receipt_path)
            if (receipt.get("source_cases") != 128 or len(set(receipt.get("source_keys", []))) != 128
                    or receipt.get("input_packet_sha256") != cfg["training_packet_sha256"]
                    or frozen["files"].get(str(receipt_path.relative_to(ROOT))) != sha(receipt_path)):
                raise ValueError("The original TRAIN source receipt changed")
            extras.add(receipt_path)
            train_keys.update(receipt["source_keys"])
            if name in {"ACE45", "ACE_common45"}:
                if complete["status"] != "completed_declared_ACE_adaptation_stream" or len(complete["batch_summary"]) != 8:
                    raise ValueError("ACE must retain its completed eight-batch actual lineage")
                bank = publication["playbook"]
                if bank != complete["final_playbook"] or csha(bank) != old["bank_sha256"]:
                    raise ValueError("Do not choose a different ACE checkpoint or rewrite its playbook")
            elif name == "text45":
                if (complete["status"] != "completed_trace2skill_text_offline_adaptation"
                        or publication["bank"] != complete["final_bank"]
                        or trace2skill_actor_bank(publication["files"]) != publication["bank"]
                        or publication["files_sha256"] != csha(publication["files"])
                        or complete["final_files_sha256"] != publication["files_sha256"]):
                    raise ValueError("Text must retain every file of its actual text-only adaptation")
                bank = publication["bank"]
            else:
                allowed = {"run_id", "skill_commit_policy", "protocol", "matched_main_config", "matched_policy_contrast"}
                policy = {"whole_bank": "whole_bank", "legal_scope": "legal_scope"}.get(name, "adaptive_legal")
                if (source["skill_commit_policy"] != policy
                        or any(source.get(k) != main.get(k) for k in (set(source) | set(main)) - allowed)
                        or any(frozen["files"].get(p) != h for p, h in critical.items())
                        or frozen["packages"] != main_frozen["packages"]
                        or source.get("initial_library_publication") or source.get("warm_source_case_ids")
                        or complete["status"] != "completed_bounded_mechanism_study"
                        or len(complete["batch_summary"]) != 8
                        or complete["execution_dispatch"] != main["phase_dispatch"]):
                    raise ValueError("The revised controls must differ only in declared submission policy")
                initial_path = out / "initialization.json"
                initial = read(initial_path)
                if (initial["bank"] != [] or initial.get("parent_publication") is not None
                        or initial.get("initial_case_exposure", 0) != 0
                        or initial["execution_dispatch"] != main["phase_dispatch"]
                        or any(complete["prequential_skills"][f]["tasks"] != 128 for f in FAMILIES)):
                    raise ValueError("Require the actual empty origin and every original task view")
                extras.add(initial_path)
                previous = csha([])
                for batch in range(1, 9):
                    p = out / "publications" / f"b{batch}.json"
                    saved = read(p)
                    first_path = out / "batches" / f"b{batch}_prequential.json"
                    first = read(first_path)
                    if (saved["parent_bank_sha256"] != previous
                            or first["parent_bank_sha256"] != previous
                            or saved["bank_sha256"] != csha(saved["bank"])
                            or first["source_cases"] != 16 or first["tasks_per_arm"] != 32):
                        raise ValueError("Require all eight actual successive publications and saved first forecasts")
                    records_path = out / "batches" / f"b{batch}_prequential_records.json"
                    recorded = read(records_path)["skills"]
                    batch_ids = set(source_ids[(batch - 1) * 16:batch * 16])
                    expected_grid = {(r["case_id"], r["family"], r["source_key"])
                                     for r in train_rows if r["case_id"] in batch_ids}
                    actual_grid = {(r["case_id"], r["family"], r["source_key"]) for r in recorded}
                    if len(recorded) != 32 or actual_grid != expected_grid:
                        raise ValueError("Do not reorder, resample or omit the shared TRAIN source batches")
                    previous = saved["bank_sha256"]
                    extras.update((p, first_path, records_path))
                bank = publication["bank"]
                if role == "B1_frozen":
                    snapshot_path = out / "frozen_after_B1.json"
                    snapshot = read(snapshot_path)
                    if (snapshot.get("bank") != bank or snapshot.get("bank_sha256") != csha(bank)
                            or snapshot.get("publication_bank_sha256") != csha(bank)
                            or snapshot.get("freeze_after_exactly_batch") != 1
                            or snapshot.get("not_selected_by_later_performance_or_nonempty_success") is not True
                            or snapshot.get("evaluation_only_never_teacher_or_admission_feedback") is not True):
                        raise ValueError("Use only the actual fixed B1 snapshot")
                    extras.add(snapshot_path)
                elif bank != complete["bank"] or csha(bank) != previous:
                    raise ValueError("Use the unique actual B8 terminal bank, never a best intermediate")
        if name == "ACE_common45":
            representation = arm["representation_artifact"]
            if representation != (
                    "artifacts/research/openexempt_legal_scope_20261020/ACE_actual_final_playbook_lossless_common_direct_wrapper_20261027.json"):
                raise ValueError("Freeze the predeclared lossless common-interface ACE representation")
            wrapped = read(checked(representation, arm["representation_sha256"]))
            if wrapped != ace_common_direct_bank(bank):
                raise ValueError("The complete native playbook must be preserved verbatim")
            bank = wrapped
        if csha(bank) != arm["bank_sha256"]:
            raise ValueError("The actual frozen bank differs from its prospective matrix binding")
        if arm["backend"] == "direct":
            validate_scoped_bank(bank)
            if any(s["guidance"]["operators"] for s in bank):
                raise ValueError("No direct condition may introduce a numerical interpreter")
        banks[name] = bank
    if (len(train_keys) != 128 or train_keys & set(key_data["source_keys"])
            or main_frozen["files"].get(main["input_packet"]) != cfg["training_packet_sha256"]):
        raise ValueError("Require the complete TRAIN source set disjoint from all new IID sources")
    return banks, train_keys, extras


def fixed_banks(cfg):
    """Check completed TRAIN provenance without loading TEST questions/targets."""
    if cfg.get("evaluation_stage") in SOURCE_DISJOINT_STAGES:
        return source_disjoint_banks(cfg)
    workers = evaluation_request_workers(cfg)
    schedule = cfg.get("learning_execution_schedule")
    supplement = cfg.get("evaluation_stage") == SUPPLEMENT_STAGE
    if schedule not in (None, runtime_sources.SCHEDULE, runtime_sources.CONTROL_SCHEDULE,
                         runtime_sources.ADAPTIVE_SCHEDULE):
        raise ValueError("Unknown learning execution schedule")
    if (schedule == runtime_sources.ADAPTIVE_SCHEDULE) != supplement:
        raise ValueError("The revised runtime epoch belongs only to the declared supplementary stage")
    allow_phase_dispatch = schedule is not None
    if (cfg.get("evaluation_role") != "sealed_frozen_comparison"
            or cfg.get("final_matrix_frozen") is not True
            or cfg.get("no_validation_set") is not True
            or "teacher" in cfg
            or cfg.get("execution_contract") != "direct_statutory_claims"
            or cfg.get("execution_contract_version") != 14):
        raise ValueError("Declare a frozen inference-only common14 comparison, without a teacher")
    safe_component(cfg["run_id"])
    for key in ("source_cases", "training_source_cases", "training_batch_source_cases"):
        if type(cfg.get(key)) is not int or cfg[key] < 1:
            raise ValueError("Positive complete evaluation/training source counts are required")
    if any(cfg["generation"].get(k) != v for k, v in FINAL_DECODING.items()):
        raise ValueError("Use the prespecified common final decoding, not a selected inference setting")
    if not (ROOT / cfg["statistics_plan"]).is_file():
        raise FileNotFoundError("Freeze the explicit statistics plan before TEST prediction")
    arms = cfg["arms"]
    names = [safe_component(a["name"]) for a in arms]
    if len(names) != len(set(names)) or not ROLES.issuperset(a["role"] for a in arms):
        raise ValueError("Unique comparison names and declared roles are required")
    if not {"strong_empty", "evolved", "B1_frozen", "experience", "static_law_only"} <= {
            a["role"] for a in arms}:
        raise ValueError("Include strong empty, evolution, B1-frozen, experience and law-only controls")
    empty = [a for a in arms if a["role"] == "strong_empty"]
    if len(empty) != 1 or empty[0]["name"] != cfg["reference_arm"]:
        raise ValueError("Declare exactly one strong-empty reference")
    if sum(a["role"] == "static_law_only" for a in arms) != 1:
        raise ValueError("The single compiled static bank is not independent learning repeats")
    banks, train_keys, extras, sources = {}, set(), {ROOT / cfg["statistics_plan"]}, {}
    if cfg.get("experience_replication_design") == SINGLE_BASELINE_DESIGN:
        if (cfg.get("baseline_build_amendment") != SINGLE_BASELINE_PROTOCOL
                or not (ROOT / SINGLE_BASELINE_PROTOCOL).is_file()):
            raise ValueError("Freeze the exact single-baseline amendment before TEST")
        extras.add(ROOT / SINGLE_BASELINE_PROTOCOL)
    if workers == 4:
        extras.add(ROOT / DISPATCH_PROTOCOL)
    source_configs = {}
    for arm in arms:
        name, role = arm["name"], arm["role"]
        if role == "strong_empty":
            if arm["backend"] != "direct" or arm.get("source_config"):
                raise ValueError("Strong empty must have no learned publication")
            banks[name] = []
            continue
        if (arm["backend"] not in ({"ace", "direct"} if role == "experience" else {"direct"})):
            raise ValueError("Use the declared direct/ACE task adapter, not a hidden answer selector")
        config_path = ROOT / arm["source_config"]
        source, frozen = read(config_path), read(config_path.with_suffix(".frozen.json"))
        source_configs[name] = source
        if sha(config_path) != arm["source_config_sha256"] or frozen["config_sha256"] != sha(config_path):
            raise ValueError("Learning source config differs from the declared frozen source")
        if (source["execution_contract"] != "direct_statutory_claims"
                or source["execution_contract_version"] != 14):
            raise ValueError("Final controls must share the common14 task interface")
        for key in ("base_url", "model", "model_root", "context_tokens", "max_tokens", "temperature", "top_p",
                    "top_k", "disable_thinking"):
            if source["generation"][key] != cfg["generation"][key]:
                raise ValueError("Source executor or inference budget differs: " + key)
        for name_ in SHARED_ACTOR_FILES + (ACE_ACTOR_FILES if arm["backend"] == "ace" else ()):
            extras.update(check_shared_actor_revision(
                name_, frozen["files"][name_], allow_phase_dispatch=allow_phase_dispatch,
                adaptive=supplement))
        out = ROOT / "runs" / source["run_id"]
        complete = read(out / "completion.json")
        if role == "static_law_only":
            if (source.get("source_cases") != 0 or source.get("planned_batches") != 0
                    or source.get("purpose") != "one_blind_public_law_compilation_no_performance_evaluation"
                    or source.get("input_is_public_law_contract_bundle_not_case_packet") is not True
                    or source.get("no_8B_generation_or_evaluation_in_compilation") is not True
                    or source.get("no_current_or_future_facts_labels_trajectories_scores_or_prior_bank_to_author") is not True
                    or complete["status"] != "compiled_law_only_static_bank_not_evaluated"):
                raise ValueError("Static law-only control must be a zero-case blind compilation")
            public_path = ROOT / source["input_packet"]
            if frozen["files"][source["input_packet"]] != sha(public_path):
                raise ValueError("Static author's public input changed after compilation")
            public = read(public_path)
            if (set(public) != PUBLIC_LAW_FIELDS
                    or public["no_cases_targets_trajectories_scores_or_prior_bank"] is not True):
                raise ValueError("Static compilation must use the audited public-law-only bundle")
            publication = out / "publication.json"
            published = read(publication)
            bank = published["bank"]
            if (published.get("training_sources_seen") != 0
                    or published.get("actual_native_generations") != 0
                    or published.get("compiled_not_evaluated") is not True
                    or published.get("bank_sha256") != csha(bank)
                    or csha(bank) != arm["bank_sha256"]
                    or not 0 <= published["Qwen_tokens"] <= source["library_token_hard_cap"]
                    or source["library_token_hard_cap"] != cfg["library_token_hard_cap"]):
                raise ValueError("Use the original compiled bank and common token cap, not a rewritten control")
            teacher = out / "teacher/law_only_compilation"
            request_path, response_path = teacher / "wire_request.json", teacher / "response.json"
            request, response = read(request_path), read(response_path)
            event_path = Path(response["actual_event_log_path"])
            event = read(event_path)
            if (json.loads(request["user_prompt"]) != public
                    or response["value"] != {"bank": bank}
                    or response["cache_hit"] is not False
                    or request["model"] != source["teacher"]["model"]
                    or response["model"] != request["model"]
                    or response["request_sha256"] != csha(request)
                    or response["invocation"]["returncode"] != 0
                    or response["invocation"]["tool_events_detected"]
                    or response["invocation"]["event_log_sha256"] != csha({"event_log": event["event_log"]})):
                raise ValueError("Static bank must match its fresh recorded public-only teacher request and response")
            validate_scoped_bank(bank)
            validate_scopes(bank, "\n\n".join(public["complete_public_statutes"].values()))
            if any(s["guidance"]["operators"] for s in bank):
                raise ValueError("Static control cannot add a numerical skill interpreter")
            banks[name], sources[name] = bank, source["run_id"]
            extras.update((config_path, config_path.with_suffix(".frozen.json"), public_path,
                           publication, out / "completion.json", request_path, response_path, event_path))
            continue
        if (source["source_cases"] != cfg["training_source_cases"]
                or source["batch_source_cases"] != cfg["training_batch_source_cases"]
                or source["planned_batches"] * source["batch_source_cases"] != source["source_cases"]
                or frozen["files"][source["input_packet"]] != cfg["training_packet_sha256"]):
            raise ValueError("Final learned controls must share the full TRAIN packet")
        initialization_path = out / "initialization.json"
        initial = read(initialization_path)
        if (out / "failure.json").exists() or not (out / "terminal_preservation.json").is_file():
            raise ValueError("Require actually completed and preserved learning, not only a completion flag")
        if (source.get("initial_library_publication") or source.get("warm_source_case_ids")
                or initial.get("initial_case_exposure", 0) != 0
                or (arm["backend"] == "direct" and (
                    initial["bank"] != [] or initial.get("parent_publication") is not None))
                ):
            raise ValueError("Independent learning starts from its original empty library, not a selected prior")
        if arm["backend"] == "ace":
            extras.update(check_ace_learning_origin(
                source, frozen, out, initial, complete, allow_phase_dispatch=allow_phase_dispatch,
                adaptive=supplement))
        text_method = role == "experience" and arm["backend"] == "direct"
        if text_method:
            if cfg.get("external_text_adaptation") != "trace2skill_text_offline_v1":
                raise ValueError("The text-adaptation baseline must be declared before TEST")
            validate_trace2skill_profile(source)
            for dependency in ("experiments/openexempt_trace2skill.py",
                               "legal_skill_guard/learning/trace2skill_text.py", source["protocol"]):
                if allow_phase_dispatch and dependency == "experiments/openexempt_trace2skill.py":
                    extras.update(runtime_sources.verify_revision(
                        ROOT, dependency, frozen["files"][dependency], adaptive=supplement))
                elif frozen["files"][dependency] != sha(ROOT / dependency):
                    raise ValueError("Text construction implementation changed since learning")
            if initial["patch_initial_files"] != TRACE2SKILL_INITIAL_FILES:
                raise ValueError("Text adaptation must use the original empty patch scaffold")
            if (out / "failure.json").exists() or not (out / "terminal_preservation.json").is_file():
                raise ValueError("Require actually completed and preserved text adaptation")
            if (complete["status"] != "completed_trace2skill_text_offline_adaptation"
                    or complete["source_cases"] != cfg["training_source_cases"]
                    or complete["actual_teacher_responses"] != 321
                    or not 321 <= complete["actual_teacher_attempts"] <= 642):
                raise ValueError("Incomplete text construction cannot enter the final matrix")
            total = complete["source_first_forecasts"]
            if any(complete["final_TRAIN_replay"][f]["tasks"] != cfg["training_source_cases"] for f in FAMILIES):
                raise ValueError("Text adaptation must retain its full report-only TRAIN replay")
        else:
            status = ("completed_declared_ACE_adaptation_stream" if arm["backend"] == "ace"
                      else "completed_bounded_mechanism_study")
            total = (complete["prequential"]["ace"] if arm["backend"] == "ace"
                     else complete["prequential_skills"])
        if not text_method and (complete["status"] != status or len(complete["batch_summary"]) != source["planned_batches"]):
            raise ValueError("Incomplete or failed learning is not a final learned bank")
        if any(total[f]["tasks"] != cfg["training_source_cases"] for f in FAMILIES):
            raise ValueError("Learning did not evaluate every declared source in both tasks")
        batch = 1 if role == "B1_frozen" else source["planned_batches"]
        publication = out / "publications" / ("final.json" if text_method else f"b{batch}.json")
        published = read(publication)
        field = "playbook" if arm["backend"] == "ace" else "bank"
        bank = published[field]
        if csha(bank) != arm["bank_sha256"]:
            raise ValueError("Do not select or rewrite a different learned bank")
        if supplement and role == "B1_frozen":
            snapshot_path = out / "frozen_after_B1.json"
            snapshot = read(snapshot_path)
            if (snapshot.get("bank") != bank or snapshot.get("bank_sha256") != csha(bank)
                    or snapshot.get("publication_bank_sha256") != csha(bank)
                    or snapshot.get("freeze_after_exactly_batch") != 1
                    or snapshot.get("not_selected_by_later_performance_or_nonempty_success") is not True
                    or snapshot.get("evaluation_only_never_teacher_or_admission_feedback") is not True
                    or len(set(snapshot.get("source_keys_seen", []))) != source["batch_source_cases"]):
                raise ValueError("Use the revised learner's exact original frozen B1, never a selected snapshot")
            extras.add(snapshot_path)
        if role != "B1_frozen":
            final_field = "final_playbook" if arm["backend"] == "ace" else ("final_bank" if text_method else "bank")
            if bank != complete[final_field]:
                raise ValueError("Use the final publication, not a winning intermediate checkpoint")
        if arm["backend"] == "direct":
            validate_scoped_bank(bank)
            if any(s["guidance"]["operators"] for s in bank):
                raise ValueError("The common direct actor has no numerical skill interpreter")
        elif not isinstance(bank, str):
            raise ValueError("ACE must use its actual text playbook")
        if text_method:
            if (published["files_sha256"] != csha(published["files"])
                    or complete["final_files_sha256"] != published["files_sha256"]
                    or trace2skill_actor_bank(published["files"]) != bank
                    or not 0 <= published["library_tokens"] <= source["library_token_hard_cap"]):
                raise ValueError("Preload the full published text, not a selected or rewritten excerpt")
            expected = {(r["case_id"], r["family"]) for r in read(ROOT / source["input_packet"])["rows"]}
            for filename, stage, digest in (
                    ("source_records.json", "source_first_forecasts", csha([])),
                    ("final_TRAIN_records.json", "final_TRAIN_replay", csha(bank))):
                records = read(out / filename)
                if (len(records) != len(expected)
                        or {(r["case_id"], r["family"]) for r in records} != expected
                        or any(r["stage"] != stage or r["bank_sha256"] != digest for r in records)):
                    raise ValueError("Text adaptation must retain all original and final TRAIN records")
                extras.add(out / filename)
            extras.add(out / "terminal_preservation.json")
        receipt_path = (ROOT / source["input_packet"]).parent / "preselection.json"
        receipt = read(receipt_path)
        if (receipt["source_cases"] != cfg["training_source_cases"]
                or receipt["input_packet_sha256"] != cfg["training_packet_sha256"]
                or len(set(receipt["source_keys"])) != cfg["training_source_cases"]
                or frozen["files"][str(receipt_path.relative_to(ROOT))] != sha(receipt_path)):
            raise ValueError("Learning receipt source count differs")
        train_keys.update(receipt["source_keys"])
        banks[name], sources[name] = bank, source["run_id"]
        extras.update((config_path, config_path.with_suffix(".frozen.json"), publication,
                       out / "completion.json", out / "terminal_preservation.json",
                       initialization_path, receipt_path))
    for arm in arms:
        if arm["role"] == "evolved" and not any(
                other["role"] == "B1_frozen" and other["source_config"] == arm["source_config"]
                and sources[other["name"]] == sources[arm["name"]]
                for other in arms):
            raise ValueError("Each evolved run needs its own actual B1-frozen control")
    for role in ("evolved", "experience", "B1_frozen"):
        run_ids = [sources[a["name"]] for a in arms if a["role"] == role]
        if len(run_ids) != len(set(run_ids)):
            raise ValueError("Repeated names for one learning run are not independent repeats")
    check_primary_contrasts(cfg, source_configs)
    check_secondary_contrasts(cfg, source_configs)
    extras.update(check_learning_execution_versions(cfg, source_configs))
    extras.update(check_future_learning_plan(cfg, source_configs))
    extras.update(check_initial_evaluation(cfg))
    return banks, train_keys, extras


class FrozenEvaluation:
    check = Comparison.check
    call = Comparison.call
    grade = Online.grade

    def __init__(self, config_path):
        self.cfg = read(config_path)
        self.workers = evaluation_request_workers(self.cfg)
        self._progress_lock = threading.Lock()
        self._wire_lock_guard, self._wire_locks = threading.Lock(), {}
        self.banks, self.train_keys, _ = fixed_banks(self.cfg)
        frozen = read(config_path.with_suffix(".frozen.json"))
        if frozen["config_sha256"] != sha(config_path):
            raise ValueError("Final evaluation matrix changed after freeze")
        self.bindings, self.run_id = frozen["files"], self.cfg["run_id"]
        self.out = ROOT / "runs" / self.run_id
        if self.out.exists():
            raise FileExistsError("Never overwrite or resume selected TEST answers")
        self.native, self.request_cache, self.reuse_events = [], {}, []
        self.initial_arm_names, self.prior_native_origins = set(), []
        if self.cfg.get("evaluation_stage") in (FINAL_STAGE, SUPPLEMENT_STAGE):
            self.load_initial_raw_origins()
        self.current_batch, self.stop = 0, False
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda *_: setattr(self, "stop", True))
        self.check()

    def load_initial_raw_origins(self):
        """Snapshot hash-bound original responses; both actors still decode them afresh."""
        initial = read(ROOT / self.cfg["initial_evaluation"]["source_config"])
        out = ROOT / "runs" / initial["run_id"]
        index = read(out / "native_origins_before_any_grading.json")
        if index.get("generation_sha256") != csha(self.cfg["generation"]):
            raise ValueError("Prior raw responses use different generation settings")
        self.initial_arm_names = {arm["name"] for arm in initial["arms"]}
        all_initial_arm_names = set(self.initial_arm_names)
        if self.cfg.get("evaluation_stage") == SUPPLEMENT_STAGE:
            self.initial_arm_names = set(self.cfg["retained_initial_arms"])
            if not self.initial_arm_names <= all_initial_arm_names:
                raise ValueError("Only original condition names may retain original predictions")
        for entry in index["origins"]:
            path = runtime_sources.checked_path(ROOT, entry["raw_call_path"])
            input_path = path.with_suffix(".input.json")
            if (not path.is_relative_to(out / "native") or sha(path) != entry["raw_sha256"]
                    or sha(input_path) != entry["input_sha256"]):
                raise ValueError("An original initial native response/input changed")
            raw, supplied = read(path), read(input_path)
            fingerprint = csha({"messages": supplied["messages"], "schema": supplied["schema"],
                                "generation": self.cfg["generation"]})
            if (fingerprint != entry["fingerprint"] or fingerprint in self.request_cache
                    or raw.get("transport_error") is not None or raw.get("response") is None
                    or len(raw.get("calls", [])) != 1):
                raise ValueError("Keep exactly one genuine, completed transport origin per full request")
            wire = raw["calls"][0]["request"]
            generation = self.cfg["generation"]
            observed = raw["calls"][0]["response"]
            response = raw["response"]
            if (wire.get("messages") != supplied["messages"]
                    or wire.get("response_format", {}).get("json_schema", {}).get("schema") != supplied["schema"]
                    or any(wire.get(k) != generation[k] for k in
                           ("model", "temperature", "top_p", "top_k", "max_tokens", "seed"))
                    or wire.get("chat_template_kwargs", {}).get("enable_thinking", True)
                    != (not generation["disable_thinking"])
                    or observed["id"] != response["raw_id"]
                    or observed["usage"]["prompt_tokens"] != response["prompt_tokens"]
                    or observed["usage"]["completion_tokens"] != response["completion_tokens"]
                    or observed["choices"][0]["finish_reason"] != response["finish_reason"]
                    or (observed["choices"][0]["message"].get("content") or "").strip() != response["content"]):
                raise ValueError("The saved raw native wire does not match its full request identity")
            self.request_cache[fingerprint] = {"response": raw["response"],
                                               "raw_call_path": entry["raw_call_path"]}
            self.prior_native_origins.append(entry)
        if (not self.prior_native_origins
                or len(self.prior_native_origins) != read(out / "completion.json")["actual_native_calls"]):
            raise ValueError("Preserve all initial native origins, including incomplete model outputs")
        predictions = read(out / "predictions_before_any_grading.json")
        origin_paths = {entry["raw_call_path"] for entry in self.prior_native_origins}
        grids = []
        for records in predictions.values():
            grid = {(r["source_key"], r["case_id"], r["family"]) for r in records}
            if (len(records) != 2 * initial["source_cases"] or len(grid) != len(records)
                    or len({key for key, _, _ in grid}) != initial["source_cases"]
                    or any({f for k, i, f in grid if k == key and i == case} != set(FAMILIES)
                           for key, case, _ in grid)
                    or any(r["raw_call_path"] not in origin_paths or "score" in r for r in records)):
                raise ValueError("Reuse the full pre-grading initial matrix, not selected or scored answers")
            grids.append(grid)
        if set(predictions) != all_initial_arm_names or any(grid != grids[0] for grid in grids):
            raise ValueError("The prior stage must contain every source under every original arm")

    def progress(self, stage, **extra):
        with self._progress_lock:
            RunStore.atomic_json(self.out / "progress.json", {
                "at": now(), "run_id": self.run_id, "stage": stage,
                "completed_native_calls": len(self.native), "teacher_calls": 0,
                "inference_request_workers": self.workers,
                "exact_wire_reuses_not_independent_draws": len(self.reuse_events), **extra})

    def answer(self, row, arm):
        name, bank = arm["name"], self.banks[arm["name"]]
        stage = "frozen_" + name
        if arm["backend"] == "ace":
            messages, schema = generator_payload(row, bank, direct_numeric=True, asset_references=True)
        else:
            messages, schema, _ = actor_payload(row, bank, grounded=True,
                                              direct_numeric=True, asset_references=True)
        fingerprint = csha({"messages": messages, "schema": schema,
                            "generation": self.cfg["generation"]})
        if name in self.initial_arm_names and fingerprint not in self.request_cache:
            raise ValueError("An original initial8 request changed; never silently regenerate it")
        # Guard the original actor's entire lookup/generation/cache/alias path.
        # Distinct requests may run together; identical requests have one origin.
        with self._wire_lock_guard:
            lock = self._wire_locks.setdefault(fingerprint, threading.Lock())
        with lock:
            return (ACEOnline.answer(self, row, stage, playbook=bank)
                    if arm["backend"] == "ace" else
                    Online.answer(self, row, bank, stage, name))

    def answer_row(self, row):
        arms = self.cfg["arms"]
        offset = (row["case_id"] + FAMILIES[row["family"]]) % len(arms)
        return {arm["name"]: self.answer(row, arm)
                for arm in arms[offset:] + arms[:offset]}

    def execute(self):
        self.rows = read(ROOT / self.cfg["input_packet"])["rows"]
        groups = {}
        for row in self.rows:
            if row["source_key"] in self.train_keys:
                raise ValueError("TEST source overlaps a learning source; do not drop/resample it")
            groups.setdefault(row["source_key"], []).append((row["case_id"], row["family"]))
        if len(groups) != self.cfg["source_cases"] or any(
                len(pair) != 2 or len({i for i, _ in pair}) != 1
                or {f for _, f in pair} != set(FAMILIES) for pair in groups.values()):
            raise ValueError("Evaluate the complete declared source-paired EC/EV packet")
        if len({row["case_id"] for row in self.rows}) != len(groups):
            raise ValueError("Each TEST source must have its own case identity")
        records = {a["name"]: [] for a in self.cfg["arms"]}
        if self.workers == 1:
            by_row = [self.answer_row(row) for row in self.rows]
        else:
            by_row = [None] * len(self.rows)
            pool = ThreadPoolExecutor(max_workers=self.workers)
            futures = {pool.submit(self.answer_row, row): i for i, row in enumerate(self.rows)}
            try:
                for future in as_completed(futures):
                    by_row[futures[future]] = future.result()
            except BaseException:
                self.stop = True
                for future in futures:
                    future.cancel()
                raise
            finally:
                # Drain actual in-flight records before failure/terminal backup.
                pool.shutdown(wait=True, cancel_futures=True)
        for answers in by_row:
            for name, record in answers.items():
                records[name].append(record)
        # The only grading path is below all arms/all sources' immutable answers.
        RunStore.immutable_json(self.out / "predictions_before_any_grading.json", records)
        origins = []
        for fingerprint, origin in sorted(self.request_cache.items()):
            path = ROOT / origin["raw_call_path"]
            origins.append({"fingerprint": fingerprint, "raw_call_path": origin["raw_call_path"],
                            "raw_sha256": sha(path), "input_sha256": sha(path.with_suffix(".input.json"))})
        RunStore.immutable_json(self.out / "native_origins_before_any_grading.json", {
            "generation_sha256": csha(self.cfg["generation"]), "origins": origins,
            "raw_only_no_scores_or_correct_answers": True})
        self.check()
        self.grade([r for values in records.values() for r in values])
        RunStore.immutable_json(self.out / "scored_records.json", records)
        reference = records[self.cfg["reference_arm"]]
        return {"status": "completed_frozen_comparison", "at": now(),
            "evaluation_stage": self.cfg.get("evaluation_stage", "legacy_final"),
            "metrics": {name: metrics(values) for name, values in records.items()},
            "paired_vs_strong_empty": {name: paired_effect(reference, values)
                                       for name, values in records.items()},
            "paired_vs_own_B1_frozen": {arm["name"]: paired_effect(
                records[own_B1_reference(self.cfg, arm)],
                records[arm["name"]]) for arm in self.cfg["arms"] if arm["role"] == "evolved"},
            "bank_sha256": {name: csha(bank) for name, bank in self.banks.items()},
            "actual_native_calls": len(self.native), "teacher_calls": 0,
            "prior_stage_native_origins_not_new_calls": len(self.prior_native_origins),
            "inference_request_workers": self.workers,
            "exact_wire_reuses_not_independent_draws": self.reuse_events,
            "native_prompt_tokens": sum(r["response"]["prompt_tokens"] for r in self.native),
            "native_completion_tokens": sum(r["response"]["completion_tokens"] for r in self.native),
            "statistics_plan": self.cfg["statistics_plan"],
            "paired_source_statistics": paired_source_statistics(self.cfg, records),
            **({"pooled_complete_claim_metrics": {
                    name: pooled_complete_claim_metrics(values) for name, values in records.items()}}
               if self.cfg.get("evaluation_stage") in
                  (CONTINUED_SOURCE_DISJOINT_STAGE, UTILITY_SOURCE_DISJOINT_STAGE) else {})}

    def run(self):
        self.out.mkdir(parents=True, exist_ok=False)
        RunStore.immutable_json(self.out / "evaluation_started.json", {
            "at": now(), "matrix_frozen_before_packet_load": True,
            "no_teacher_or_learning": True, "inference_request_workers": self.workers,
            "arms": self.cfg["arms"]})
        try:
            result = self.execute()
            RunStore.immutable_json(self.out / "completion.json", result)
            self.progress("terminal", state=result["status"])
        except Exception as exc:
            RunStore.immutable_json(self.out / "failure.json", {
                "at": now(), "error": repr(exc), "traceback": traceback.format_exc(),
                "actual_native_calls": len(self.native), "teacher_calls": 0,
                "no_retry_or_answer_selection": True})
            self.progress("terminal", state="failed")
            raise
        finally:
            names = [str(p.relative_to(ROOT)) for p in self.out.rglob("*") if p.is_file()]
            RunStore.immutable_json(self.out / "terminal_preservation.json",
                                    preserve(self.run_id, "actual-terminal", names))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("freeze", "run"))
    parser.add_argument("config", type=Path)
    args = parser.parse_args()
    path = args.config.resolve()
    os.chdir(ROOT)
    cfg = read(path)
    stage = cfg.get("evaluation_stage")
    if stage in SOURCE_DISJOINT_STAGES:
        check_source_disjoint_plan(cfg)
        _, _, sources = fixed_banks(cfg)
        if stage == CONTINUED_SOURCE_DISJOINT_STAGE and args.action == "freeze":
            # Test data for the historical adaptive guard, not an allowed learner epoch.
            digest = runtime_sources.ADAPTIVE_CURRENT["experiments/openexempt_online.py"]
            snapshot = ROOT / ("artifacts/research/openexempt_legal_scope_20261020/"
                "source_snapshots/continued_eval_20261029/"
                f"openexempt_online_historical_adaptive__{digest}.py")
            if sha(snapshot) != digest:
                raise ValueError("The actual historical adaptive test fixture changed")
            sources.add(snapshot)
        with (ROOT / "artifacts/openexempt_training.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if args.action == "freeze":
                freeze(path, additional_sources=(*sources, Path(__file__).resolve(),
                    ROOT / "tests/test_openexempt_source_disjoint_eval.py",
                    ROOT / "experiments/openexempt_ace_online.py",
                    *ROOT.glob("third_party/ace/prompts/*.py")))
            else:
                FrozenEvaluation(path).run()
        return
    supplement = stage == SUPPLEMENT_STAGE
    if supplement and (cfg.get("supplement_protocol") != SUPPLEMENT_PROTOCOL
            or cfg.get("protocol") != SUPPLEMENT_PROTOCOL
            or cfg.get("benchmark_development_status") != "development_informed_fixed_benchmark"
            or cfg.get("historical_comparators_not_matched_new_ablations") is not True
            or cfg.get("independent_learning_repetitions") != "user_deferred"
            or cfg.get("future_learning_plan") is not None
            or cfg.get("future_learning_plan_sha256") is not None):
        raise ValueError("Declare the actual fixed-benchmark supplement without fictitious repeats or untouched claims")
    if (cfg.get("external_text_adaptation") != "trace2skill_text_offline_v1"
            or stage not in (INITIAL_STAGE, FINAL_STAGE, SUPPLEMENT_STAGE)
            or cfg.get("ablation_design") != (SUPPLEMENT_DESIGN if supplement else "legal_scope_granularity_v1")
            or (not supplement and (cfg.get("staged_comparison_protocol") != STAGED_PROTOCOL
                or not cfg.get("future_learning_plan") or not cfg.get("future_learning_plan_sha256")))
            or cfg.get("experience_replication_design") is not None
            or len(cfg.get("arms", [])) != (8 if stage in (INITIAL_STAGE, SUPPLEMENT_STAGE) else 16)
            or cfg.get("source_cases") != 128 or cfg.get("training_source_cases") != 128
            or cfg.get("training_batch_source_cases") != 16
            or len(cfg.get("primary_contrasts", [])) != 5
            or len(cfg.get("secondary_contrasts", [])) != 2):
        raise ValueError("The formal paper entry requires the declared initial8, final16 or revised supplementary8 design")
    _, _, sources = fixed_banks(cfg)
    with (ROOT / "artifacts/openexempt_training.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.action == "freeze":
            freeze(path, additional_sources=(*sources, Path(__file__).resolve(),
                Path(__file__).resolve().parents[1] / "tests/test_openexempt_frozen_eval.py",
                ROOT / "experiments/openexempt_ace_online.py",
                *ROOT.glob("third_party/ace/prompts/*.py")))
        else:
            FrozenEvaluation(path).run()


if __name__ == "__main__":
    main()
