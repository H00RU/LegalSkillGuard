"""Offline Trace2Skill text adaptation on the common public EC/EV interface.

This deliberately does not call the proposed learner's update or admission
gate. Source trajectories use the empty library, all before label feedback;
independent trajectory analysts and hierarchical merges produce one text skill.
It is not the original tool-using ReAct pipeline or an exact author replica.
"""

from __future__ import annotations

import argparse
import copy
import fcntl
import json
import signal
import traceback
from pathlib import Path

from experiments.openexempt_online import Online, direct_request_key, freeze, preserve
from legal_skill_guard.experiment.storage import RunStore, safe_component
from legal_skill_guard.inference.native import WireClient
from legal_skill_guard.learning.experiment import Comparison, now, read, sha
from legal_skill_guard.learning.phase_dispatch import PhaseDispatch
from legal_skill_guard.learning.trace2skill_text import (
    ANALYST_ROLE, INITIAL_FILES, MERGE_ROLE, TRANSLATOR_ROLE,
    actor_bank, apply_patch, merge_groups, patch_schema,
)
from legal_skill_guard.openexempt import FAMILIES, ROOT, metrics
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha


def validate_profile(cfg):
    expected = {
        "learner": "trace2skill_text_offline_v1",
        "execution_contract": "direct_statutory_claims",
        "execution_contract_version": 14,
        "source_cases": 128,
        "batch_source_cases": 16,
        "planned_batches": 8,
        "merge_batch_size": 5,
        "max_merge_levels": 5,
        "translation_calls": 1,
        "library_token_hard_cap": 8192,
        "analysis_mode": "single_trajectory_text_with_released_native_verifier_feedback",
        "trace_initial_library": "empty_no_skill",
        "patch_initial_files": INITIAL_FILES,
        "patch_failure_policy": "stop_preserve_no_repair_or_first_patch_fallback",
        "final_TRAIN_validation_policy": "report_only_no_bank_or_seed_selection",
        "no_validation_set": True,
    }
    if any(cfg.get(key) != value for key, value in expected.items()):
        raise ValueError("Declare the complete Trace2Skill text-adaptation policy before freeze")
    if cfg.get("initial_library_publication") or cfg.get("warm_source_case_ids"):
        raise ValueError("No imported source trajectories, bank or teacher output")
    if cfg["generation"]["seed"] not in (45, 145, 245):
        raise ValueError("Only the declared independent-learning seeds are allowed")
    if Path(cfg["exclusive_training_lock"]).resolve() != (ROOT / "artifacts/openexempt_training.lock").resolve():
        raise ValueError("All learners share the same canonical training lock")
    if cfg["planned_teacher_responses_max"] != 321 or cfg["planned_teacher_transport_attempts_max"] != 642:
        raise ValueError("Account for 256 analysts, 64 merges and one translation")
    predecessors = cfg.get("required_completed_predecessors", [])
    if len(predecessors) < 2 or len(predecessors) != len(set(predecessors)):
        raise ValueError("Declare distinct completed current learners as operational predecessors")


class Trace2Skill:
    # Only existing source/model-bound transports, direct actor and native grader.
    # No new orchestration layer or inheritance of a different learning policy.
    check = Comparison.check
    call = Comparison.call
    teacher_call = Comparison.teacher_call
    answer = Online.answer
    grade = Online.grade

    def __init__(self, config_path):
        self.cfg = read(config_path)
        validate_profile(self.cfg)
        frozen = read(Path(config_path).with_suffix(".frozen.json"))
        if frozen["config_sha256"] != sha(config_path):
            raise ValueError("Frozen external-method configuration changed")
        self.bindings = frozen["files"]
        self.run_id = safe_component(self.cfg["run_id"])
        self.out = ROOT / "runs" / self.run_id
        if self.out.exists():
            raise FileExistsError("New Run ID required; no resume or overwriting predictions")
        for predecessor in self.cfg["required_completed_predecessors"]:
            path = ROOT / "runs" / safe_component(predecessor)
            if not (path / "completion.json").is_file() or not (path / "terminal_preservation.json").is_file():
                raise ValueError("Required prior learner must actually finish and be preserved")
            if (path / "failure.json").exists():
                raise ValueError("A failed predecessor cannot be counted as a completed learner")
            if read(path / "completion.json")["status"] not in (
                    "completed_bounded_mechanism_study", "completed_declared_ACE_adaptation_stream",
                    "completed_trace2skill_text_offline_adaptation"):
                raise ValueError("A stopped or partial predecessor is not completed learning")
        packet = ROOT / self.cfg["input_packet"]
        if sha(packet) != self.cfg["same_public_packet_sha256"]:
            raise ValueError("Source packet changed")
        self.rows = read(packet)["rows"]
        ids = {row["case_id"] for row in self.rows}
        if (len(self.rows) != 256 or len(ids) != 128
                or {(row["case_id"], row["family"]) for row in self.rows} !=
                {(case, family) for case in ids for family in FAMILIES}
                or {row["batch"] for row in self.rows} != set(range(1, 9))):
            raise ValueError("The same complete128-source paired packet is required")
        if any(len([row for row in self.rows if row["batch"] == batch]) != 32 for batch in range(1, 9)):
            raise ValueError("Each original TRAIN batch must contain exactly32 tasks")
        for case in ids:
            if len({row["batch"] for row in self.rows if row["case_id"] == case}) != 1:
                raise ValueError("A source cannot cross batches")
        self.native, self.teachers, self.teacher_attempts = [], [], 0
        self.request_cache, self.reuse_events = {}, []
        self.current_batch, self.stop = 0, False
        self._dispatch = PhaseDispatch(self.cfg,
            environment=(read(ROOT / self.cfg['inference_environment'])
                         if self.cfg.get('phase_dispatch') is not None else None),
            on_failure=lambda: setattr(self, 'stop', True))
        self.answer = self._dispatch.locked_requests(self.answer,
            lambda *args, **kwargs: direct_request_key(self.cfg, *args, **kwargs))
        self.teacher_call = self._dispatch.limited_teacher(self.teacher_call)
        self.files, self.bank = copy.deepcopy(INITIAL_FILES), []
        self.meter = WireClient(self.cfg["generation"])
        self.out.mkdir(parents=True)
        RunStore.immutable_json(self.out / "initialization.json", {
            "execution_dispatch": self._dispatch.receipt(),
            "at": now(), "bank": [], "patch_initial_files": self.files,
            "patch_initial_files_sha256": csha(self.files),
            "source_trajectory_skill_content": None,
            "offline_creation_not_causal_online_batch_updates": True,
            "text_analyst_with_native_TRAIN_feedback_not_agentic_author_replica": True})
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda *_: setattr(self, "stop", True))
        self.check()
        if not self.meter.readiness()["ready"]:
            raise RuntimeError("The original frozen8B service is unavailable")
        self.progress("initialized")

    def progress(self, stage, **extra):
        with self._dispatch.progress_lock:
            RunStore.atomic_json(self.out / "progress.json", {
                "at": now(), "run_id": self.run_id, "state": "running", "stage": stage,
                "current_batch": self.current_batch, "completed_native_calls": len(self.native),
                "completed_teacher_calls": len(self.teachers), "teacher_attempts": self.teacher_attempts,
                "execution_dispatch": self._dispatch.receipt(),
                "cross_stage_identical_wire_reuses": len(self.reuse_events), **extra})

    def execute(self):
        def source_answer(row):
            if self._dispatch.native_workers == 1:
                self.current_batch = row["batch"]
            return self.answer(row, [], "source_first_forecasts", "trace2skill_source")
        sources = self._dispatch.native(source_answer, self.rows)
        # Release feedback only after the complete corpus of source predictions.
        self.grade(sources)
        RunStore.immutable_json(self.out / "source_records.json", sources)
        if self._dispatch.teacher_workers > 1:
            self.current_batch = 0  # Multiple offline dataset batches may be active.
        def analyze_source(pair):
            row, source = pair
            if self._dispatch.teacher_workers == 1:
                self.current_batch = row["batch"]
            raw = read(ROOT / source["raw_call_path"])
            saved_input = read(self.out / "native/source_first_forecasts" /
                               f"{row['case_id']}_{row['family']}_trace2skill_source.input.json")
            target = read(ROOT / self.cfg["grading_directory"] /
                          f"{row['case_id']}.json")["targets"][row["family"]]
            solved = (source["parse_error"] is None
                      and source["score"]["full_output_claim_fp"] == 0
                      and source["score"]["full_output_claim_fn"] == 0)
            return self.teacher_call(f"map_{row['case_id']}_{row['family']}", ANALYST_ROLE, {
                "immutable_initial_files": INITIAL_FILES,
                "single_source_public_messages": saved_input["messages"],
                "single_source_public_schema": saved_input["schema"],
                "own_actual_trajectory_response": raw["response"],
                "actual_decoded_submission": source["parsed"],
                "actual_parse_error": source["parse_error"],
                "released_native_TRAIN_score": source["score"],
                "released_native_TRAIN_target": target,
                "outcome": "success" if solved else "failure",
                "no_other_source_or_future_TEST_feedback": True,
            }, patch_schema())
        patches = self._dispatch.teacher(analyze_source, zip(self.rows, sources, strict=True))
        level = 0
        while len(patches) > 1:
            level += 1
            if level > self.cfg["max_merge_levels"]:
                raise ValueError("Declared merge depth exhausted; no forced or first-patch fallback")
            def merge_group(pair):
                index, group = pair
                return self.teacher_call(f"merge_L{level}_{index:03d}", MERGE_ROLE, {
                    "immutable_initial_files": INITIAL_FILES,
                    "all_patches_in_this_ordered_group": group,
                    "merge_level": level,
                    "group_index": index,
                    "no_performance_based_patch_selection": True,
                }, patch_schema())
            patches = self._dispatch.teacher(merge_group,
                enumerate(merge_groups(patches, self.cfg["merge_batch_size"]), 1))
        if len(patches) != 1:
            raise ValueError("Every source must produce a recorded patch or explicit empty patch")
        final = self.teacher_call("translate_final_patch", TRANSLATOR_ROLE, {
            "immutable_initial_files": INITIAL_FILES,
            "complete_hierarchically_merged_patch": patches[0],
        }, patch_schema())
        self.files = apply_patch(INITIAL_FILES, final)
        self.bank = actor_bank(self.files)
        tokens = self.meter.token_count(text=json.dumps(self.bank, ensure_ascii=False, separators=(",", ":")))
        if tokens > self.cfg["library_token_hard_cap"]:
            raise ValueError("Complete text skill exceeds capacity; no clipping or older-bank selection")
        publication = {"at": now(), "bank": self.bank, "bank_sha256": csha(self.bank),
            "files": self.files, "files_sha256": csha(self.files), "library_tokens": tokens,
            "initial_source_tasks": len(sources), "hierarchical_merge_levels": level,
            "no_original_source_forecast_replaced": True,
            "no_performance_based_skill_or_seed_selection": True}
        RunStore.immutable_json(self.out / "publications/final.json", publication)
        self.current_batch = 0
        def final_answer(row):
            if self._dispatch.native_workers == 1:
                self.current_batch = row["batch"]
            return self.answer(row, self.bank, "final_TRAIN_replay", "trace2skill_final")
        final_train = self._dispatch.native(final_answer, self.rows)
        self.grade(final_train)
        RunStore.immutable_json(self.out / "final_TRAIN_records.json", final_train)
        if len(self.teachers) > self.cfg["planned_teacher_responses_max"]:
            raise ValueError("Actual construction exceeded the declared response maximum")
        return {
            "status": "completed_trace2skill_text_offline_adaptation",
            "final_bank": self.bank, "final_bank_sha256": csha(self.bank),
            "final_files_sha256": csha(self.files), "source_cases": 128,
            "source_first_forecasts": metrics(sources),
            "final_TRAIN_replay": metrics(final_train),
            "final_TRAIN_replay_is_not_unseen_case_or_TEST": True,
            "not_an_online_evolution_curve_or_agentic_author_replica": True,
            "official_TEST_opened": False,
        }

    def run(self):
        state = "failed"
        try:
            result = self.execute()
            state = result["status"]
            RunStore.immutable_json(self.out / "completion.json", {
                "at": now(), "run_id": self.run_id, **result,
                "execution_dispatch": self._dispatch.receipt(),
                "actual_native_calls": len(self.native), "actual_teacher_responses": len(self.teachers),
                "actual_teacher_attempts": self.teacher_attempts, "raw_wire_reuses": self.reuse_events,
                "native_prompt_tokens": sum((r.get("response") or {}).get("prompt_tokens", 0) for r in self.native),
                "native_completion_tokens": sum((r.get("response") or {}).get("completion_tokens", 0) for r in self.native),
            })
        except Exception as exc:
            RunStore.immutable_json(self.out / "failure.json", {
                "at": now(), "error": repr(exc), "traceback": traceback.format_exc(),
                "actual_files": self.files, "actual_bank": self.bank,
                "actual_native_calls": len(self.native), "actual_teacher_responses": len(self.teachers),
                "actual_teacher_attempts": self.teacher_attempts})
            raise
        finally:
            self.progress("terminal", state=state)
            names = [str(p.relative_to(ROOT)) for p in self.out.rglob("*")
                     if p.is_file() and "/cache/" not in str(p)]
            receipt = preserve(self.run_id, "actual-terminal", names)
            RunStore.immutable_json(self.out / "terminal_preservation.json", receipt)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("freeze", "run"))
    parser.add_argument("config", type=Path)
    args = parser.parse_args()
    config = args.config.resolve()
    cfg = read(config)
    validate_profile(cfg)
    if args.action == "freeze":
        print(json.dumps({"bound_files": len(freeze(config, additional_sources=[Path(__file__).resolve()])["files"])}))
    else:
        with Path(cfg["exclusive_training_lock"]).open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            Trace2Skill(config).run()


if __name__ == "__main__":
    main()
