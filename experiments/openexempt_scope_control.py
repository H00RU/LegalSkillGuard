"""Fixed-library, TRAIN-only public-namespace projection mechanism control.

The case, citation vocabulary, task scope, skill text and generation are fixed.
Only the public namespace filter differs. No teacher, learning or answer repair.
"""
from __future__ import annotations

import argparse
from collections import Counter
import fcntl
import json
from pathlib import Path
import signal
import time
import traceback

from experiments.openexempt_online import Online, actor_payload, freeze, paired_effect, preserve
from legal_skill_guard.experiment.storage import RunStore, safe_component
from legal_skill_guard.inference.native import WireClient
from legal_skill_guard.learning.experiment import Comparison, now, read, sha
from legal_skill_guard.learning.phase_dispatch import PhaseDispatch
from legal_skill_guard.learning.task_scoped_skills import validate_scoped_bank
from legal_skill_guard.openexempt import ROOT, metrics
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha

CONDITIONS = {"scoped": True, "all_same_task_skills": False}
TRAIN_PACKET = "data/packets/openexempt_closed_feedback_public_assets128_20261021/inputs.json"
TRAIN_GRADING = "data/packets/openexempt_closed_feedback_public_assets128_20261021/grading_only"
MAIN_BANK = "06934565cafca0ee93488971183420828eb56da74ee7ceaac8ce45e3f1e971ce"


def payload(row, bank, stage, arm, *, public_namespace_filter=True):
    return actor_payload(row, bank, direct_numeric=True, asset_references=True,
                         public_namespace_filter=public_namespace_filter)


def profile(cfg):
    if (cfg.get("learner") != "fixed_public_namespace_projection_TRAIN_mechanism_v1"
            or cfg.get("execution_contract") != "direct_statutory_claims"
            or cfg.get("execution_contract_version") != 14
            or cfg.get("input_packet") != TRAIN_PACKET
            or cfg.get("grading_directory") != TRAIN_GRADING
            or cfg.get("conditions") != list(CONDITIONS)
            or cfg.get("source_cases") != 16 or cfg.get("planned_logical_predictions") != 64
            or cfg.get("planned_native_calls_max") != 64
            or cfg.get("planned_new_teacher_calls") != 0 or "teacher" in cfg
            or cfg.get("no_validation_set") is not True):
        raise ValueError("Declare the fixed two-condition16-source TRAIN-only mechanism study")
    safe_component(cfg["run_id"])
    reference_path = ROOT / cfg["reference_config"]
    if sha(reference_path) != cfg["reference_config_sha256"]:
        raise ValueError("The predeclared TRAIN continuation reference changed")
    reference = read(reference_path)
    for key in ("generation", "input_packet", "grading_directory", "inference_environment"):
        if cfg[key] != reference[key]:
            raise ValueError("Keep the original actor/environment/data: " + key)
    manifest_path = ROOT / cfg["preedit_payload_manifest"]
    if sha(manifest_path) != cfg["preedit_payload_manifest_sha256"]:
        raise ValueError("The before-edit actor/sample manifest changed")
    manifest = read(manifest_path)
    publication_path = ROOT / cfg["initial_library_publication"]
    if sha(publication_path) != cfg["initial_library_publication_sha256"]:
        raise ValueError("The actual predeclared main publication changed")
    publication = read(publication_path)
    bank = publication["bank"]
    if (csha(bank) != MAIN_BANK or publication["bank_sha256"] != MAIN_BANK
            or manifest["bank_sha256"] != MAIN_BANK
            or any(s["guidance"]["operators"] for s in bank)):
        raise ValueError("Use the unchanged main textual bank without programs")
    validate_scoped_bank(bank)
    if sha(ROOT / TRAIN_PACKET) != manifest["input_packet_sha256"]:
        raise ValueError("Keep the original complete TRAIN packet")
    rows = read(ROOT / TRAIN_PACKET)["rows"]
    for row in rows:
        messages, schema, _ = payload(row, bank, "preview", "scoped")
        fingerprint = csha({"messages": messages, "schema": schema,
                            "generation": cfg["generation"]})
        if fingerprint != manifest["default_wire_sha256"][f"{row['case_id']}_{row['family']}"]:
            raise ValueError("The original default actor wire changed")
    selected = cfg["selected_source_case_ids"]
    if selected != manifest["selected_source_case_ids"] or len(set(selected)) != 16:
        raise ValueError("Use the public-only prebound sample, not selected outcomes")
    selected_rows = [row for row in rows if row["case_id"] in selected]
    if (len(selected_rows) != 32
            or Counter(r["batch"] for r in selected_rows) != {b: 4 for b in range(1, 9)}
            or Counter(r["family"] for r in selected_rows) != {"EC": 16, "EV": 16}):
        raise ValueError("Include both tasks of two sources from each original cohort")
    preview = []
    for row in selected_rows:
        before, schema, scoped = payload(row, bank, "preview", "scoped")
        after, other_schema, all_skills = payload(row, bank, "preview", "all_same_task_skills",
                                                public_namespace_filter=False)
        if schema != other_schema or before[0] != after[0]:
            raise ValueError("The actor system and answer schema must remain identical")
        # A background skill message is the only message allowed to differ.
        is_skill = lambda message: message["content"].startswith("Background reusable skills. ")
        if ([m for m in before if not is_skill(m)]
                != [m for m in after if not is_skill(m)]):
            raise ValueError("The public case or law input changed")
        all_by_id = {s["id"]: s for s in all_skills}
        if any(all_by_id.get(s["id"]) != s for s in scoped):
            raise ValueError("The control may add irrelevant rules, not rewrite relevant ones")
        preview.append({"case_id": row["case_id"], "family": row["family"],
                        "scoped_ids": [s["id"] for s in scoped],
                        "all_same_task_ids": [s["id"] for s in all_skills]})
    return bank, selected_rows, preview


class ScopeControl:
    check = Comparison.check
    call = Comparison.call
    answer = Online.answer
    grade = Online.grade
    progress = Online.progress

    def __init__(self, config_path):
        self.cfg = read(config_path)
        self.bank, self.rows, self.preview = profile(self.cfg)
        frozen = read(config_path.with_suffix(".frozen.json"))
        if frozen["config_sha256"] != sha(config_path):
            raise ValueError("Frozen control configuration changed")
        self.bindings = frozen["files"]
        self.run_id = safe_component(self.cfg["run_id"])
        self.out = ROOT / "runs" / self.run_id
        if self.out.exists():
            raise FileExistsError("Use a new Run ID; never resume or overwrite predictions")
        self.native, self.teachers, self.teacher_attempts = [], [], 0
        self.request_cache, self.reuse_events = {}, []
        self.current_batch, self.stop = 0, False
        self.meter = WireClient(self.cfg["generation"])
        self._dispatch = PhaseDispatch(self.cfg,
            environment=read(ROOT / self.cfg["inference_environment"]),
            on_failure=lambda: setattr(self, "stop", True))
        self.answer = self._dispatch.locked_requests(
            self.answer, PhaseDispatch.payload_key(self.cfg["generation"], payload))
        self.check()
        if not self.meter.readiness()["ready"]:
            raise RuntimeError("The original resident8B service is unavailable")
        self.out.mkdir()
        RunStore.immutable_json(self.out / "initialization.json", {
            "at": now(), "TRAIN_mechanism_not_new_training_or_TEST": True,
            "bank_sha256": MAIN_BANK, "preview": self.preview,
            "all256_original_default_actor_wires_unchanged": True,
            "no_teacher_learning_or_output_repair": True})
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda *_: setattr(self, "stop", True))
        self.progress("initialized")

    def execute(self):
        work = []
        for row in self.rows:
            arms = list(CONDITIONS)
            if (row["case_id"] + (row["family"] == "EV")) % 2:
                arms.reverse()
            work.extend((row, arm) for arm in arms)

        def predict(item):
            row, arm = item
            if csha(self.bank) != MAIN_BANK:
                raise ValueError("The fixed library cannot change")
            return self.answer(row, self.bank, "paired_TRAIN", arm,
                               public_namespace_filter=CONDITIONS[arm])

        records = self._dispatch.native(predict, work)
        if len(records) != 64 or len(self.native) > 64 or self.teachers:
            raise ValueError("Retain all64 predictions within the zero-teacher budget")
        RunStore.immutable_json(self.out / "predictions_before_grading.json", records)
        self.grade(records)
        RunStore.immutable_json(self.out / "scored_records.json", records)
        groups = {arm: [r for r in records if r["arm"] == arm] for arm in CONDITIONS}
        return {"status": "completed_fixed_public_scope_TRAIN_mechanism",
                "metrics": {arm: metrics(values) for arm, values in groups.items()},
                "unfiltered_minus_scoped": paired_effect(groups["scoped"], groups["all_same_task_skills"]),
                "bank_sha256": MAIN_BANK, "logical_predictions": 64,
                "actual_native_calls": len(self.native), "new_teacher_calls": 0,
                "exact_wire_reuses_not_independent_draws": self.reuse_events,
                "native_prompt_tokens": sum(r["response"]["prompt_tokens"] for r in self.native),
                "native_completion_tokens": sum(r["response"]["completion_tokens"] for r in self.native),
                "finish_reasons": dict(Counter(r["response"]["finish_reason"] for r in self.native)),
                "TRAIN_descriptive_not_new_source_confirmation_or_learning_repeat": True}

    def run(self):
        started = time.monotonic()
        try:
            result = self.execute()
            RunStore.immutable_json(self.out / "completion.json", {
                "at": now(), **result,
                "elapsed_execute_seconds_not_GPU_busy_time": time.monotonic() - started})
            self.progress("terminal", state=result["status"])
        except Exception as exc:
            RunStore.immutable_json(self.out / "failure.json", {
                "at": now(), "error": repr(exc), "traceback": traceback.format_exc(),
                "actual_native_calls": len(self.native), "new_teacher_calls": 0})
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
    cfg = read(path)
    if args.action == "freeze":
        profile(cfg)
        additional = [Path(__file__).resolve(), ROOT / cfg["reference_config"],
                      ROOT / cfg["preedit_payload_manifest"],
                      ROOT / cfg["source_preservation_receipt"]]
        print(json.dumps({"bound_files": len(freeze(path, additional_sources=additional)["files"])}))
    else:
        with (ROOT / "artifacts/openexempt_training.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            ScopeControl(path).run()


if __name__ == "__main__":
    main()
