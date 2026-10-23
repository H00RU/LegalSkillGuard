"""Frozen EC/EV comparison: existing actors/scorer, no teacher or skill updates.

This entry point is not used until methods, publications and the complete matrix
are fixed. It never imports a TEST packet at module import or plan validation.
"""

from __future__ import annotations

import argparse
import ast
from concurrent.futures import ThreadPoolExecutor, as_completed
import fcntl
import json
import os
import signal
import threading
import traceback
from pathlib import Path

import numpy as np

from experiments.openexempt_ace_online import ACEOnline
from experiments.openexempt_online import Online, actor_payload, freeze, paired_effect, preserve
from experiments.openexempt_trace2skill import validate_profile as validate_trace2skill_profile
from legal_skill_guard.experiment.storage import RunStore, safe_component
from legal_skill_guard.learning.experiment import INITIAL_PLAYBOOK, Comparison, now, read, sha
from legal_skill_guard.learning.legal_namespace import validate_scopes
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
    if text_design and (len(text_arms) != 3 or len(ace_arms) != 3):
        raise ValueError("The expanded matrix requires three ACE and three text-adaptation learners")
    evolved = [a["name"] for a in cfg["arms"] if a["role"] == "evolved"]
    evolved.sort(key=lambda name: source_configs[name]["generation"]["seed"])
    if (len(evolved) != len(LEARNING_SEEDS)
            or tuple(source_configs[n]["generation"]["seed"] for n in evolved) != LEARNING_SEEDS):
        raise ValueError("Complete three evolution runs at declared learning seeds 45,145,245")
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
        elif (len(before) != 3
              or tuple(source_configs[n]["generation"]["seed"] for n in before) != LEARNING_SEEDS):
            raise ValueError("Align three independent control learning runs by seed")
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
    expected = {"whole_bank": ("whole_bank", "carry_partial_and_refine"),
                "first_commit": ("legal_scope", "batch_only_first_commit")}
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
    seen, variants = set(), set()
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
                    "no_validation_set", "phase_dispatch", "inference_environment"):
            if source.get(key) != parent.get(key):
                raise ValueError("Ablation changes an undeclared common condition: " + key)
        teachers = [{k: v for k, v in config.get("teacher", {}).items()
                     if k != "total_invocation_budget"} for config in (parent, source)]
        if teachers[0] != teachers[1]:
            raise ValueError("Ablations must retain the common teacher and invocation policy")
        seen.add(name)
        variants.add(variant)


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
    primary, secondary = cfg["primary_contrasts"], cfg.get("secondary_contrasts", [])
    if not primary or len(secondary) != 2:
        raise ValueError("Prespecify the complete primary and two-ablation secondary families")
    contrasts = primary + secondary
    matrices = {name: np.asarray([[grid[key, f] for f in FAMILIES] for key in keys])
                for name, grid in grids.items()}
    differences, repeated = [], []
    for j, contrast in enumerate(contrasts):
        after = np.stack([matrices[n] for n in contrast["after"]])
        before = np.stack([matrices[n] for n in contrast["before"]])
        if j < len(primary) and (after.shape[0] != 3 or before.shape[0] not in (1, 3)):
            raise ValueError("Analyze three learned banks with single common or seed-paired controls")
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
    rng = np.random.Generator(np.random.PCG64(2026102192))
    indices = rng.integers(len(keys), size=(20000, len(keys)))
    draws = delta[indices].mean(axis=1)
    m, secondary_m = len(primary) * len(FAMILIES), len(secondary) * len(FAMILIES)
    ordinary = np.quantile(draws, [0.025, 0.975], axis=0, method="linear")
    adjusted = np.concatenate((
        np.quantile(draws[:, :len(primary)], [0.025 / m, 1 - 0.025 / m], axis=0, method="linear"),
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
    return {"protocol": "conditional_paired_source_bootstrap_three_learning_runs",
            "sources": len(keys), "source_keys_sorted": keys, "endpoints": list(FAMILIES),
            "bootstrap_draws": 20000, "bootstrap_seed": 2026102192,
            "rng": "NumPy Generator PCG64", "numpy_version": np.__version__, "quantile_method": "linear",
            "primary_family_comparisons": m,
            "contrasts": {c["name"]: result[c["name"]] for c in primary},
            "secondary_family_comparisons": secondary_m,
            "secondary_contrasts": {c["name"]: result[c["name"]] for c in secondary},
            "secondary_single_learning_seed45_not_three_repeats_or_matched_actual_compute": True,
            "all_primary_adjusted_lower_bounds_positive": all(
                endpoint["adjusted_lower_positive"] for c in primary
                for endpoint in result[c["name"]]["endpoints"].values()),
            "conditional_on_actual_learned_banks_and_fixed_decoding_not_algorithm_population": True,
            "single_empty_and_static_prediction_not_independent_replicates": True}


def check_ace_learning_origin(source, frozen, out, initial, complete, *, _lineage=None,
                              allow_phase_dispatch=False):
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
            version_sources.update(runtime_sources.verify_revision(ROOT, name, digest))
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
            allow_phase_dispatch=allow_phase_dispatch))
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


def check_shared_actor_revision(name, expected, *, allow_phase_dispatch=False):
    """Allow only the recorded teacher-log-only edit in the shared module.

    Final inference never calls Comparison.teacher_call. Every other AST node
    must match the original hash-bound source; all other actor files still
    require byte identity. The old source joins the final immutable freeze.
    """
    if allow_phase_dispatch and name in runtime_sources.HISTORICAL:
        return runtime_sources.verify_revision(ROOT, name, expected)
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
    """Match actual within-seed runtimes without pretending seed45 was parallel."""
    schedule = cfg.get("learning_execution_schedule")
    if schedule is None:
        if any(source.get("phase_dispatch") is not None for source in source_configs.values()):
            raise ValueError("Declare the changed learning execution schedule before TEST")
        return set()
    if (schedule != runtime_sources.SCHEDULE
            or cfg.get("learning_execution_schedule_protocol") != runtime_sources.PROTOCOL):
        raise ValueError("Declare the exact prospective learning execution amendment")
    protocol = ROOT / runtime_sources.PROTOCOL
    if not protocol.is_file():
        raise ValueError("Freeze the prospective learning execution protocol")
    extras, environments = runtime_sources.validate_bundle(ROOT) | {protocol}, {}
    for name, source in source_configs.items():
        if source.get("source_cases") == 0:
            continue  # The static author compiles public law; it does not run 8B learning.
        arm = next(a for a in cfg["arms"] if a["name"] == name)
        frozen = read((ROOT / arm["source_config"]).with_suffix(".frozen.json"))
        out = ROOT / "runs" / source["run_id"]
        environment = runtime_sources.validate_learning_receipt(
            ROOT, source, frozen, read(out / "initialization.json"), read(out / "completion.json"))
        seed = source["generation"]["seed"]
        environments.setdefault(seed, set()).add((str(environment), sha(environment)))
        extras.add(environment)
    if set(environments) != set(LEARNING_SEEDS) or any(len(v) != 1 for v in environments.values()):
        raise ValueError("Main, ACE, Text and controls must match their actual within-seed environment")
    if environments[145] != environments[245]:
        raise ValueError("Both future repeat seeds must use the same captured new single-model environment")
    normalized_argv = []
    for seed in LEARNING_SEEDS:
        environment = Path(next(iter(environments[seed]))[0])
        argv = list(read(environment)["actual_argv"])
        if (argv.count("--max-num-seqs") != 1
                or argv.index("--max-num-seqs") + 1 >= len(argv)):
            raise ValueError("Capture exactly one actual serving sequence limit")
        index = argv.index("--max-num-seqs")
        if argv[index + 1] != ("1" if seed == 45 else "4"):
            raise ValueError("The actual service does not match the declared learning-seed boundary")
        normalized_argv.append(argv[:index] + argv[index + 2:])
    if any(argv != normalized_argv[0] for argv in normalized_argv[1:]):
        raise ValueError("The serving transition changed more than the declared sequence limit")
    return extras


def fixed_banks(cfg):
    """Check completed TRAIN provenance without loading TEST questions/targets."""
    workers = evaluation_request_workers(cfg)
    schedule = cfg.get("learning_execution_schedule")
    if schedule not in (None, runtime_sources.SCHEDULE):
        raise ValueError("Unknown learning execution schedule")
    allow_phase_dispatch = schedule == runtime_sources.SCHEDULE
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
                name_, frozen["files"][name_], allow_phase_dispatch=allow_phase_dispatch))
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
                source, frozen, out, initial, complete, allow_phase_dispatch=allow_phase_dispatch))
        text_method = role == "experience" and arm["backend"] == "direct"
        if text_method:
            if cfg.get("external_text_adaptation") != "trace2skill_text_offline_v1":
                raise ValueError("The text-adaptation baseline must be declared before TEST")
            validate_trace2skill_profile(source)
            for dependency in ("experiments/openexempt_trace2skill.py",
                               "legal_skill_guard/learning/trace2skill_text.py", source["protocol"]):
                if allow_phase_dispatch and dependency == "experiments/openexempt_trace2skill.py":
                    extras.update(runtime_sources.verify_revision(ROOT, dependency, frozen["files"][dependency]))
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
        self.current_batch, self.stop = 0, False
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda *_: setattr(self, "stop", True))
        self.check()

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
        self.check()
        self.grade([r for values in records.values() for r in values])
        RunStore.immutable_json(self.out / "scored_records.json", records)
        reference = records[self.cfg["reference_arm"]]
        return {"status": "completed_frozen_comparison", "at": now(),
            "metrics": {name: metrics(values) for name, values in records.items()},
            "paired_vs_strong_empty": {name: paired_effect(reference, values)
                                       for name, values in records.items()},
            "paired_vs_own_B1_frozen": {arm["name"]: paired_effect(
                records[next(a["name"] for a in self.cfg["arms"]
                             if a["role"] == "B1_frozen"
                             and a["source_config"] == arm["source_config"])],
                records[arm["name"]]) for arm in self.cfg["arms"] if arm["role"] == "evolved"},
            "bank_sha256": {name: csha(bank) for name, bank in self.banks.items()},
            "actual_native_calls": len(self.native), "teacher_calls": 0,
            "inference_request_workers": self.workers,
            "exact_wire_reuses_not_independent_draws": self.reuse_events,
            "native_prompt_tokens": sum(r["response"]["prompt_tokens"] for r in self.native),
            "native_completion_tokens": sum(r["response"]["completion_tokens"] for r in self.native),
            "statistics_plan": self.cfg["statistics_plan"],
            "paired_source_statistics": paired_source_statistics(self.cfg, records)}

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
    if (cfg.get("external_text_adaptation") != "trace2skill_text_offline_v1"
            or len(cfg.get("arms", [])) != 16
            or cfg.get("source_cases") != 128 or cfg.get("training_source_cases") != 128
            or cfg.get("training_batch_source_cases") != 16
            or len(cfg.get("primary_contrasts", [])) != 5
            or len(cfg.get("secondary_contrasts", [])) != 2):
        raise ValueError("The formal paper entry requires the full declared16-arm128-source design")
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
