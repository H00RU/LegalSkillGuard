"""One fixed, case-free legal library on the complete existing TRAIN stream.

No learning, new teacher, TEST access, answer import or queue. The direct actor,
grader and transport are the same implementations used by the completed main
run. All 256 predictions precede grading; original main records are comparison
data only, never model responses for this control.
"""

from __future__ import annotations

import argparse
from collections import Counter
import copy
import fcntl
import json
import signal
import time
import traceback
from pathlib import Path

from experiments.openexempt_online import Online, freeze, paired_effect, preserve
from legal_skill_guard.experiment.storage import RunStore, safe_component
from legal_skill_guard.inference.native import WireClient
from legal_skill_guard.learning.experiment import Comparison, now, read, sha
from legal_skill_guard.learning.legal_namespace import validate_scopes
from legal_skill_guard.learning.task_scoped_skills import validate_scoped_bank
from legal_skill_guard.openexempt import FAMILIES, ROOT, metrics
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha


def validate_profile(cfg):
    if (cfg.get("learner") != "frozen_case_free_static_TRAIN_control_v1"
            or cfg.get("execution_contract") != "direct_statutory_claims"
            or cfg.get("execution_contract_version") != 14
            or (cfg.get("source_cases"), cfg.get("batch_source_cases"),
                cfg.get("planned_batches")) != (128, 16, 8)
            or cfg.get("planned_native_calls_max") != 256
            or cfg.get("planned_new_teacher_calls") != 0
            or "teacher" in cfg or cfg.get("no_validation_set") is not True):
        raise ValueError("Declare the fixed128 TRAIN direct control without a teacher")
    safe_component(cfg["run_id"])
    if Path(cfg["exclusive_training_lock"]).resolve() != (
            ROOT / "artifacts/openexempt_training.lock").resolve():
        raise ValueError("Use the existing canonical training lock")
    main_path = ROOT / cfg["comparison_reference_config"]
    if sha(main_path) != cfg["comparison_reference_config_sha256"]:
        raise ValueError("The recorded main reference configuration changed")
    reference = read(main_path)
    original = read(main_path.with_suffix(".frozen.json"))["files"]
    for name in ("experiments/openexempt_online.py", "legal_skill_guard/openexempt.py",
                 "legal_skill_guard/learning/legal_namespace.py",
                 "legal_skill_guard/learning/task_scoped_skills.py"):
        if sha(ROOT / name) != original[name]:
            raise ValueError("The actual main actor/scorer changed: " + name)
    ace = read(ROOT / cfg["completed_ACE_reference_config"])
    for key in ("generation", "input_packet", "grading_directory",
                "inference_environment", "source_cases", "batch_source_cases", "planned_batches"):
        if cfg[key] != reference[key] or ace[key] != reference[key]:
            raise ValueError("Control must retain the actual main/ACE128 setting: " + key)
    if cfg["generation"]["seed"] != 45 or cfg["library_token_hard_cap"] != 4096:
        raise ValueError("Retain the main seed45 and complete4096-token cap")
    if cfg["required_completed_predecessors"] != [reference["run_id"], ace["run_id"]]:
        raise ValueError("Wait for both declared full learners, without changing their order")
    compiler_path = ROOT / cfg["static_compiler_config"]
    if sha(compiler_path) != cfg["static_compiler_config_sha256"]:
        raise ValueError("The original blind compiler configuration changed")
    compiler = read(compiler_path)
    expected = f"runs/{safe_component(compiler['run_id'])}/publication.json"
    if cfg["initial_library_publication"] != expected:
        raise ValueError("Only the original zero-case static publication is permitted")
    return reference


def require_completed_predecessors(cfg):
    for name, status in zip(cfg["required_completed_predecessors"], (
            "completed_bounded_mechanism_study", "completed_declared_ACE_adaptation_stream"), strict=True):
        out = ROOT / "runs" / safe_component(name)
        if ((out / "failure.json").exists() or not (out / "completion.json").is_file()
                or not (out / "terminal_preservation.json").is_file()
                or len(list((out / "publications").glob("b*.json"))) != 8
                or read(out / "completion.json")["status"] != status):
            raise ValueError("Required full learner is not complete and preserved: " + name)


class FixedTrainControl:
    check = Comparison.check
    call = Comparison.call
    answer = Online.answer
    grade = Online.grade
    progress = Online.progress

    def __init__(self, config_path):
        self.cfg = read(config_path)
        self.reference = validate_profile(self.cfg)
        frozen = read(Path(config_path).with_suffix(".frozen.json"))
        if frozen["config_sha256"] != sha(config_path):
            raise ValueError("Frozen TRAIN-control configuration changed")
        self.bindings = frozen["files"]
        self.run_id = safe_component(self.cfg["run_id"])
        self.out = ROOT / "runs" / self.run_id
        if self.out.exists():
            raise FileExistsError("New Run ID required; do not resume or overwrite predictions")
        require_completed_predecessors(self.cfg)
        packet = ROOT / self.cfg["input_packet"]
        if sha(packet) != self.cfg["same_public_packet_sha256"]:
            raise ValueError("The complete existing TRAIN packet changed")
        self.rows = read(packet)["rows"]
        expected = {(i, family) for i in range(181, 309) for family in FAMILIES}
        if (len(self.rows) != 256
                or {(r["case_id"], r["family"]) for r in self.rows} != expected
                or any(r["batch"] != (r["case_id"] - 181) // 16 + 1 for r in self.rows)):
            raise ValueError("Retain all original128 sources, task pairs and eight batches")
        publication = read(ROOT / self.cfg["initial_library_publication"])
        self.bank = copy.deepcopy(publication["bank"])
        self.bank_hash = csha(self.bank)
        if (self.bank_hash != publication["bank_sha256"]
                or self.bank_hash != self.cfg["static_bank_sha256"]
                or publication["training_sources_seen"] != 0
                or publication["actual_native_generations"] != 0
                or publication["Qwen_tokens"] > self.cfg["library_token_hard_cap"]
                or any(s["guidance"]["operators"] for s in self.bank)):
            raise ValueError("Use the unchanged case-free direct text bank, without programs")
        validate_scoped_bank(self.bank)
        validate_scopes(self.bank, self.rows[0]["components"]["statutes"])
        self.native, self.teachers, self.teacher_attempts = [], [], 0
        self.request_cache, self.reuse_events = {}, []
        self.current_batch, self.stop, self.summaries = 0, False, []
        self.meter = WireClient(self.cfg["generation"])
        self.check()
        if not self.meter.readiness()["ready"]:
            raise RuntimeError("The original frozen8B service is unavailable")
        self.out.mkdir()
        RunStore.immutable_json(self.out / "initialization.json", {
            "at": now(), "bank": self.bank, "bank_sha256": self.bank_hash,
            "original_zero_case_publication": self.cfg["initial_library_publication"],
            "original_compilation_teacher_responses": publication["actual_teacher_responses"],
            "original_compilation_tokens": publication["Qwen_tokens"],
            "no_control_updates_or_new_teacher": True,
            "TRAIN_diagnostic_not_final_TEST_or_online_learning": True})
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda *_: setattr(self, "stop", True))
        self.progress("initialized")

    def execute(self):
        records = []
        for batch in range(1, 9):
            self.current_batch = batch
            current = []
            for row in self.rows:
                if row["batch"] != batch:
                    continue
                if csha(self.bank) != self.bank_hash:
                    raise ValueError("A fixed control cannot update or replace its library")
                current.append(self.answer(row, self.bank, f"b{batch}_fixed", "static"))
            if len(current) != 32:
                raise ValueError("An incomplete source batch cannot be reported")
            RunStore.immutable_json(self.out / "batches" / f"b{batch}_predictions.json", current)
            records.extend(current)
        if len(records) != 256 or self.teachers or self.teacher_attempts:
            raise ValueError("Complete256 predictions and zero new teaching are required")
        RunStore.immutable_json(self.out / "predictions_before_labels.json", records)
        self.progress("all256_predictions_saved_before_grading")
        self.grade(records)
        RunStore.immutable_json(self.out / "scored_records.json", records)
        all_main, all_empty = [], []
        for batch in range(1, 9):
            selected = [r for r in records if r["case_id"] in range(181 + 16 * (batch - 1), 181 + 16 * batch)]
            reference = read(ROOT / "runs" / self.reference["run_id"] / "batches" /
                             f"b{batch}_prequential_records.json")
            keys = {(r["case_id"], r["family"]) for r in selected}
            for role in ("skills", "empty"):
                if len(reference[role]) != 32 or {(r["case_id"], r["family"]) for r in reference[role]} != keys:
                    raise ValueError("Reference comparison must contain all same-source tasks")
            all_main.extend(reference["skills"])
            all_empty.extend(reference["empty"])
            summary = {"batch": batch, "source_cases": 16, "tasks": 32,
                "static": metrics(selected), "reference_main": metrics(reference["skills"]),
                "reference_empty": metrics(reference["empty"]),
                "static_minus_main": paired_effect(reference["skills"], selected),
                "static_minus_empty": paired_effect(reference["empty"], selected)}
            RunStore.immutable_json(self.out / "batches" / f"b{batch}_scores.json", summary)
            self.summaries.append(summary)
        phases = {}
        for first in (1, 2, 3):
            lower = 181 + 16 * (first - 1)
            select = lambda values: [r for r in values if r["case_id"] >= lower]
            static, main, empty = select(records), select(all_main), select(all_empty)
            phases[f"B{first}_B8"] = {"source_cases": len(static) // 2,
                "static": metrics(static), "reference_main": metrics(main),
                "reference_empty": metrics(empty),
                "static_minus_main": paired_effect(main, static),
                "static_minus_empty": paired_effect(empty, static)}
        if csha(self.bank) != self.bank_hash:
            raise ValueError("No score-based final bank replacement")
        return {"status": "completed_frozen_static_TRAIN_control", "phase_summary": phases}

    def run(self):
        status = "failed"
        started = time.monotonic()
        try:
            result = self.execute()
            status = result["status"]
            RunStore.immutable_json(self.out / "completion.json", {
                "at": now(), **result, "run_id": self.run_id, "batch_summary": self.summaries,
                "fixed_bank_sha256": self.bank_hash, "actual_native_calls": len(self.native),
                "elapsed_execute_and_scoring_seconds_not_GPU_busy_time": time.monotonic() - started,
                "actual_HTTP_requests": sum(len(v["calls"]) for v in self.native),
                "native_prompt_tokens": sum(v["response"]["prompt_tokens"] for v in self.native),
                "native_completion_tokens": sum(v["response"]["completion_tokens"] for v in self.native),
                "native_finish_reasons": dict(Counter(v["response"]["finish_reason"] for v in self.native)),
                "actual_new_teacher_responses": 0, "actual_new_teacher_attempts": 0,
                "cross_stage_identical_wire_reuses": self.reuse_events,
                "not_final_TEST_or_independent_learning_or_terminal_main_bank_comparison": True})
        except Exception as exc:
            RunStore.immutable_json(self.out / "failure.json", {
                "at": now(), "error": repr(exc), "actual_native_calls": len(self.native),
                "actual_bank_sha256": csha(self.bank), "actual_new_teacher_responses": 0,
                "traceback": traceback.format_exc()})
            raise
        finally:
            self.progress("terminal", state=status)
            names = [str(p.relative_to(ROOT)) for p in self.out.rglob("*")
                     if p.is_file() and "/cache/" not in str(p)]
            RunStore.immutable_json(self.out / "terminal_preservation.json",
                                    preserve(self.run_id, "actual-terminal", names))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("freeze", "run"))
    parser.add_argument("config", type=Path)
    args = parser.parse_args()
    config = args.config.resolve()
    cfg = read(config)
    reference = validate_profile(cfg)
    if args.action == "freeze":
        reference_dir = ROOT / "runs" / reference["run_id"]
        compiler_path = ROOT / cfg["static_compiler_config"]
        compiler = read(compiler_path)
        compiler_dir = ROOT / "runs" / compiler["run_id"]
        additional = [Path(__file__).resolve(), ROOT / cfg["comparison_reference_config"],
            (ROOT / cfg["comparison_reference_config"]).with_suffix(".frozen.json"),
            ROOT / cfg["completed_ACE_reference_config"], ROOT / cfg["static_compiler_config"],
            compiler_path.with_suffix(".frozen.json"), ROOT / compiler["driver_path"],
            ROOT / compiler["input_packet"], ROOT / compiler["public_provenance"],
            reference_dir / "completion.json", reference_dir / "terminal_preservation.json"]
        additional.extend(p for p in compiler_dir.rglob("*")
                          if p.is_file() and "/cache/" not in str(p))
        additional.extend(reference_dir / "batches" / f"b{i}_prequential_records.json" for i in range(1, 9))
        print(json.dumps({"bound_files": len(freeze(config, additional_sources=additional)["files"])}))
    else:
        with Path(cfg["exclusive_training_lock"]).open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            FixedTrainControl(config).run()


if __name__ == "__main__":
    main()
