"""Explicit checkpoint completion and a separately queued feedback intervention."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import pickle
import signal
import sys
import time
import warnings
import zipfile
from pathlib import Path

from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.inference.native import WireClient
from legal_skill_guard.learning.audit import close, original_score
from legal_skill_guard.learning.experiment import now, points, read, sha
from legal_skill_guard.learning.procedures import (
    BOUNDARY_GUIDANCE_SCHEMA,
    PROCEDURE_TEACHER,
    ProcedureStudy,
)
from legal_skill_guard.learning.publication import (
    apply_differential_publication,
    differential_schema,
    paired,
    publication_statistics,
)
from legal_skill_guard.task import original_feedback
from runs.legal_contractnli_paired_final_update_20261016_run01.driver import PAIR_INSTRUCTION

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT / "runs/legal_contractnli_atomic_boundaries_20261015_run01"
MAIN_ID = "legal_contractnli_atomic_completion_20261016_run01"
PAIR_ID = "legal_contractnli_paired_final_update_20261016_run02"
MAIN = ROOT / "runs" / MAIN_ID
PROTOCOL = ROOT / "reports/experiments/atomic_completion_20261016/protocol.md"
MAIN_ARMS = ("strong_empty", "ordinary_memory", "static_procedures", "trace_procedures")


def usage(records, *, teacher=False):
    keys = (
        ("input_tokens", "output_tokens", "reasoning_output_tokens")
        if teacher
        else ("prompt_tokens", "completion_tokens")
    )
    rows = [r["invocation"]["usage"] if teacher else r["response"] for r in records]
    return {k: sum(r[k] for r in rows) for k in keys}


class Completion(ProcedureStudy):
    def __init__(self, mode):
        self.mode = mode
        self.run_id = MAIN_ID if mode == "main" else PAIR_ID
        self.out = ROOT / "runs" / self.run_id
        assert not (self.out / "declaration.json").exists(), "Never restart an existing Run ID"
        self.cfg = {
            **read(ROOT / "configs/contractnli_atomic_boundaries.json"),
            "planned_new_native_calls": 52 if mode == "main" else 8,
            "planned_new_teacher_calls": 1,
        }
        packet = read(ROOT / self.cfg["input_packet"])
        self.labels, self.training = packet["public_hypotheses"], packet["training"]
        self.future = packet["later_inputs_no_annotation_sets"]
        assert [r["id"] for r in self.future] == [568, 327, 342, 374, 624, 270, 341, 135]
        assert all("annotation_sets" not in r for r in self.future)
        self.native, self.units, self.teachers, self.shared_units = [], [], [], []
        self.teacher_attempts, self.current_batch, self.stop = 0, 4, False
        self.meter = WireClient(self.cfg["generation"])
        self.inherited_units = [read(p) for p in sorted(OLD.glob("batch*/*/*.public.json"))]
        self.inherited_shares = [read(p) for p in sorted(OLD.glob("batch1_before/*/*.shared.json"))]
        self.inherited_native = [read(p) for p in sorted(OLD.rglob("*.final.native.json"))]
        self.inherited_teachers = [
            read(p) for p in sorted((OLD / "teacher").glob("*/response.json"))
        ]
        assert len(self.inherited_units) == len(self.inherited_native) == 78
        assert len(self.inherited_shares) == 12 and len(self.inherited_teachers) == 5
        assert read(OLD / "progress.json")["state"] == "failed"
        assert read(OLD / "monitoring/stopped_prefix_and_capacity_root_audit.json")[
            "all90_logical_original_source_wire_model_library_and_scores_replayed"
        ]
        self.bank = read(OLD / "update_transactions/trace_b3.json")["publication"]
        self.static = read(OLD / "static_procedures.json")["library"]
        self.public_only = []
        self.before = {
            r["id"]: read(OLD / f"batch4_before/trace_procedures/{r['id']}.public.json")
            for r in self.training
            if r["batch"] == 4
        }
        self.after = {
            r["id"]: read(OLD / f"batch{r['batch']}_after/trace_procedures/{r['id']}.public.json")
            for r in self.training
            if r["batch"] < 4
        }
        self.state_versions = {
            m["state_sha256"]: m
            for b in (1, 2, 3)
            for m in [read(OLD / f"evidence_models/ordinary_M{b}.manifest.json")]
        }
        self.summaries = [read(OLD / f"batch{b}_summary.json") for b in (1, 2, 3)]
        self.load_model(3, OLD)
        original = read(OLD / "declaration.json")["frozen_bindings"]
        paths = {Path(p) for p in original}
        paths.update(Path(p) for p in read(OLD / "source_snapshot.json")["files"])
        paths.update(p for p in OLD.rglob("*") if p.is_file() and p.suffix == ".json")
        paths.update(Path(m["path"]) for m in self.state_versions.values())
        paths.update(
            [
                Path(__file__),
                PROTOCOL,
                ROOT / "runs/legal_contractnli_paired_final_update_20261016_run01/driver.py",
            ]
        )
        self.bindings = {str(p.resolve()): sha(p) for p in paths}
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: setattr(self, "stop", True))
        self.parent_launch = None
        if mode == "paired":
            self.parent_launch = read(ROOT / "artifacts/launches" / (MAIN_ID + ".json"))
            proc = Path("/proc") / str(self.parent_launch["pid"])
            self.parent_start = (proc / "stat").read_text().rsplit(")", 1)[1].split()[19]

    def progress(self, stage, **extra):
        extra.update(
            inherited_native_calls=78 if self.mode == "main" else 0,
            main_component_completed=(self.out / "main_completion.json").exists(),
        )
        super().progress(stage, **extra)

    def load_model(self, batch, directory):
        manifest = read(directory / f"evidence_models/ordinary_M{batch}.manifest.json")
        assert sha(manifest["path"]) == manifest["pickle_sha256"]
        self.state_versions[manifest["state_sha256"]] = manifest
        self.state = manifest["state_sha256"]
        with Path(manifest["path"]).open("rb") as stream:
            self.model = pickle.load(stream)

    def teacher_call(self, name, system, body, schema):
        if self.mode == "main" and name == "trace_b4":
            parent_tokens = self.validate_library(self.bank)
            body = {
                **body,
                "exact_runtime_parent_library_tokens": parent_tokens,
                "runtime_library_encoding": "UTF8 compact JSON, exactly the lawyer system library payload",
                "remaining_tokens_after_parent": self.cfg["library_token_hard_cap"] - parent_tokens,
                "capacity_note": "Keep the complete resulting library within this same real-token budget. Correct, consolidate or remove source-unsupported material rather than only lengthen guidance; no forced growth, count or deletion quota.",
            }
        return super().teacher_call(name, system, body, schema)

    def declare(self):
        self.check()
        RunStore.immutable_json(
            self.out / "declaration.json",
            {
                "at": now(),
                "pid": os.getpid(),
                "argv": sys.argv,
                "config": self.cfg,
                "frozen_bindings": self.bindings,
                "mode": self.mode,
                "explicit_failed_ancestry": str(OLD),
                "new_native_calls_planned": self.cfg["planned_new_native_calls"],
                "new_teacher_calls_planned": 1,
                "inherited_physical_native_calls": 78 if self.mode == "main" else 0,
                "inherited_teacher_responses_including_failed_auxiliary": 5
                if self.mode == "main"
                else 0,
                "not_independent_from_empty_learning_or_unchanged_original_protocol": True,
            },
        )
        RunStore.immutable_json(
            self.out / "source_snapshot.json",
            {
                "files": {
                    p: {"sha256": h, "utf8_text": Path(p).read_text()}
                    for p, h in self.bindings.items()
                    if Path(p).suffix in (".py", ".md", ".txt")
                }
            },
        )

    def audit(self, units, name):
        # Suppress only the already-understood sklearn array-name warning, not
        # fit/transport/schema/source/score errors or any other warning class.
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="X does not have valid feature names, but LGBMClassifier was fitted with feature names",
            )
            self.audit_native(units, name)

    def score_groups(self, groups, phase):
        assert all(len(v) == 8 for v in groups.values())
        expected_banks = {
            "strong_empty": [],
            "ordinary_memory": [],
            "static_procedures": self.static,
            "trace_procedures": (
                read(MAIN / "memory_frozen_before_later.json")["main_library"]
                if self.mode == "paired"
                else self.bank
            ),
            "paired_final_update": self.bank,
            "public_only_final_update": self.public_only,
        }
        for arm, units in groups.items():
            for unit in units:
                assert unit["published_library"] == expected_banks[arm]
                assert unit["actual_factual_trace"]["ordinary_model_state"] == (
                    None if arm == "strong_empty" else self.state
                )
        self.audit([u for v in groups.values() for u in v], phase + "_native_before_grading")
        gold = read(ROOT / self.cfg["grading_only"])["annotations"]
        assert sha(ROOT / self.cfg["source_archive"]) == self.cfg["source_archive_sha256"]
        with zipfile.ZipFile(ROOT / self.cfg["source_archive"]) as archive:
            author = json.loads(archive.read("contract-nli/train.json"))
        assert author["labels"] == self.labels
        originals = {r["id"]: r for r in author["documents"]}
        rows = {r["id"]: r for r in self.future}
        scored = {a: [] for a in groups}
        for arm, units in groups.items():
            for unit in units:
                row = rows[unit["document_id"]]
                source = originals[row["id"]]
                assert row["text"] == source["text"] and row["spans"] == source["spans"]
                assert gold[str(row["id"])] == source["annotation_sets"][0]["annotations"]
                feedback = original_feedback(
                    unit["response"], row, gold[str(row["id"])], list(self.labels)
                )
                close(
                    original_score(unit["response"], row, gold[str(row["id"])], list(self.labels)),
                    feedback,
                )
                value = {**unit, **feedback, "evaluation_condition": arm}
                RunStore.immutable_json(
                    self.out / "scored" / phase / arm / f"{row['id']}.json", value
                )
                scored[arm].append(value)
        return scored

    def run_main(self):
        # Main update is not contingent on an auxiliary teacher being successful.
        self.bank, management = self.update(4, include_trace=True)
        self.fit_ordinary(4)
        rows = [r for r in self.training if r["batch"] == 4]
        after = self.collect("batch4_after", "trace_procedures", rows, self.bank)
        before = {
            a: [read(OLD / "batch4_before" / a / f"{r['id']}.public.json") for r in rows]
            for a in ("strong_empty", "ordinary_memory", "trace_procedures")
        }
        summary = {
            "at": now(),
            "batch": 4,
            "before": {a: points(u) for a, u in before.items()},
            "after": {"trace_procedures": points(after)},
            "library_management": management,
            "update_effects": paired(before["trace_procedures"], after),
            "after_also_includes_new_supervised_tool_labels_not_pure_skill_effect": True,
        }
        self.summaries.append(summary)
        RunStore.immutable_json(self.out / "batch4_summary.json", summary)
        first = [r for r in self.training if r["batch"] == 1]
        retained = self.collect("retention_b4", "trace_procedures", first, self.bank)
        RunStore.immutable_json(
            self.out / "retention_b4.json",
            {
                "metrics": points(retained),
                "B1_M1_to_M4": paired([self.after[r["id"]] for r in first], retained),
                "never_to_teacher_or_admission": True,
            },
        )
        RunStore.immutable_json(
            self.out / "memory_frozen_before_later.json",
            {
                "at": now(),
                "main_library": self.bank,
                "static_library": self.static,
                "ordinary_model_state": self.state,
                "last_published_not_best_bank": True,
            },
        )
        later = {a: [] for a in MAIN_ARMS}
        for index, row in enumerate(self.future):
            offset = index % len(MAIN_ARMS)
            for arm in MAIN_ARMS[offset:] + MAIN_ARMS[:offset]:
                later[arm].append(self.answer("later", arm, row, self.bank_for(arm)))
        assert len(self.native) == len(self.units) == 44 and len(self.teachers) == 1
        self.audit(
            self.inherited_units + self.inherited_shares + self.units,
            "main_all122_physical_and12_shared",
        )
        scored = self.score_groups(later, "main")
        ids = [u["response"]["raw_id"] for u in self.inherited_units + self.units]
        assert len(ids) == len(set(ids)) == 122
        done = {
            "at": now(),
            "run_id": self.run_id,
            "new_native_calls": 44,
            "new_teacher_calls": 1,
            "inherited_native_calls": 78,
            "total_physical_native_calls": 122,
            "explicit_inherited_shared_cold_observations": 12,
            "inherited_teacher_responses": 5,
            "failed_inherited_auxiliary_teacher_response_count": 1,
            "development": {a: points(u) for a, u in scored.items()},
            "paired_trace_minus_control": {
                a: paired(scored[a], scored["trace_procedures"])
                for a in MAIN_ARMS
                if a != "trace_procedures"
            },
            "batches": self.summaries,
            "new_native_usage": usage(self.native),
            "new_teacher_usage": usage(self.teachers, teacher=True),
            "all_ancestry_native_usage": usage(self.inherited_native + self.native),
            "all_ancestry_teacher_usage_including_failed_auxiliary": usage(
                self.inherited_teachers + self.teachers, teacher=True
            ),
            "all32_main_answers_saved_and_replayed_before_main_grading": True,
            "amended_engineering_completion_not_independent_learning_repeat": True,
            "auxiliary_success_not_required_for_this_main_completion": True,
        }
        RunStore.immutable_json(self.out / "main_completion.json", done)
        self.progress("main_complete_before_optional_auxiliary", completed_main_native_calls=44)
        # Exactly reuse the previously failed auxiliary RESPONSE as a declared
        # reference under corrected actual-delivery metering, never a main bank.
        failed = read(OLD / "teacher/public_only_final_update_b4/response.json")
        wire = read(OLD / "teacher/public_only_final_update_b4/wire_request.json")
        body = json.loads(wire["user_prompt"])
        parent = read(OLD / "update_transactions/trace_b3.json")["publication"]
        self.public_only = apply_differential_publication(
            parent,
            failed["value"],
            self.labels,
            [c["document_id"] for c in body["same_parent_library_and_tool_original_train_cases"]],
            guidance_schema=BOUNDARY_GUIDANCE_SCHEMA,
        )
        tokens = self.validate_library(self.public_only)
        RunStore.immutable_json(
            self.out / "inherited_auxiliary_publication.json",
            {
                "at": now(),
                "source_failed_response": str(
                    OLD / "teacher/public_only_final_update_b4/response.json"
                ),
                "source_response_sha256": sha(
                    OLD / "teacher/public_only_final_update_b4/response.json"
                ),
                "actual_parent": parent,
                "publication": self.public_only,
                "actual_delivered_tokens": tokens,
                "explicit_new_protocol_adoption_not_retroactive_old_publication_or_new_generation": True,
                "not_a_pure_trace_ablation_because_new_main_has_capacity_metadata": True,
            },
        )
        auxiliary = [
            self.answer("auxiliary_later", "public_only_final_update", row, self.public_only)
            for row in self.future
        ]
        extra = self.score_groups({"public_only_final_update": auxiliary}, "auxiliary")
        assert len(self.native) == 52 and len(self.teachers) == 1
        RunStore.immutable_json(
            self.out / "completion.json",
            {
                **done,
                "at": now(),
                "new_native_calls": 52,
                "total_physical_native_calls": 130,
                "auxiliary": {a: points(u) for a, u in extra.items()},
                "new_native_usage": usage(self.native),
                "all_ancestry_native_usage": usage(self.inherited_native + self.native),
                "main32_and_auxiliary8_have_separate_saved_answer_grading_barriers": True,
                "not_a_single40_answers_before_any_grading_protocol": True,
            },
        )
        RunStore.atomic_json(
            self.out / "progress.json",
            {
                "at": now(),
                "state": "completed",
                "completed_native_calls": 52,
                "completed_teacher_calls": 1,
                "inherited_native_calls": 78,
                "main_component_completed": True,
            },
        )

    def parent_alive(self):
        proc = Path("/proc") / str(self.parent_launch["pid"])
        try:
            args = [s.decode() for s in (proc / "cmdline").read_bytes().split(b"\0") if s]
            stat = (proc / "stat").read_text().rsplit(")", 1)[1].split()
        except (FileNotFoundError, ProcessLookupError):
            return False
        if args and (args != self.parent_launch["actual_argv"] or stat[19] != self.parent_start):
            raise RuntimeError("Exact parent PID reused")
        return bool(args) and stat[0] != "Z"

    def run_paired(self):
        if (
            not (MAIN / "main_completion.json").is_file()
            or len(list((MAIN / "later").glob("*/*.public.json"))) != 32
        ):
            value = {
                "at": now(),
                "state": "cancelled",
                "reason": "Main44/32 endpoint component incomplete",
                "completed_native_calls": 0,
                "completed_teacher_calls": 0,
            }
            RunStore.immutable_json(self.out / "cancellation.json", value)
            RunStore.atomic_json(self.out / "progress.json", value)
            return
        assert len(list((MAIN / "batch4_after").rglob("*.final.native.json"))) == 6
        assert len(list((MAIN / "retention_b4").rglob("*.final.native.json"))) == 6
        pins = [
            MAIN / "main_completion.json",
            MAIN / "memory_frozen_before_later.json",
            MAIN / "teacher/trace_b4/wire_request.json",
            MAIN / "update_transactions/trace_b4.json",
            MAIN / "evidence_models/ordinary_M4.pickle",
            MAIN / "evidence_models/ordinary_M4.manifest.json",
        ] + list((MAIN / "later").rglob("*.json"))
        acquired = {str(p): sha(p) for p in pins}
        self.bindings.update(acquired)
        RunStore.immutable_json(
            self.out / "accepted_parent.json",
            {
                "at": now(),
                "bindings_before_new_teacher": acquired,
                "main_completion_not_parsed_for_scores": True,
                "auxiliary_success_not_required": True,
            },
        )
        wire = read(MAIN / "teacher/trace_b4/wire_request.json")
        body = json.loads(wire["user_prompt"])
        assert wire["system_prompt"] == PROCEDURE_TEACHER
        assert body["same_parent_library_and_tool_original_train_cases"] == self.teacher_cases(
            4, include_trace=True
        )
        assert body["complete_actual_parent_library"] == self.bank
        controls = []
        comparisons = []
        audit_units = list(self.before.values()) + [
            self.after[r["id"]] for r in self.training if r["batch"] == 3
        ]
        for row in self.training:
            if row["batch"] != 4:
                continue
            unit = self.before[row["id"]]
            control = read(OLD / f"batch4_before/ordinary_memory/{row['id']}.public.json")
            assert (
                control["published_library"] == []
                and control["actual_factual_trace"] == unit["actual_factual_trace"]
            )
            controls.append(
                {
                    "document_id": row["id"],
                    "actual_empty_library_observation": self.observation(control, True),
                }
            )
            comparisons.append(
                {
                    "document_id": row["id"],
                    "whole_library_not_per_skill_credit": paired([control], [unit]),
                }
            )
            audit_units.append(control)
        self.audit(audit_units, "all18_actual_same_tool_training_observations")
        body["current_batch_all_same_tool_empty_library_observations"] = controls
        body["all_current_batch_paired_component_feedback"] = comparisons
        refs = [c["document_id"] for c in body["same_parent_library_and_tool_original_train_cases"]]
        value = self.teacher_call(
            "paired_final_update_b4",
            PROCEDURE_TEACHER + PAIR_INSTRUCTION,
            body,
            differential_schema(
                self.labels, self.bank, refs, guidance_schema=BOUNDARY_GUIDANCE_SCHEMA
            ),
        )
        bank = apply_differential_publication(
            self.bank, value, self.labels, refs, guidance_schema=BOUNDARY_GUIDANCE_SCHEMA
        )
        tokens = self.validate_library(bank)
        management = publication_statistics(self.bank, value, bank, tokens)
        RunStore.immutable_json(
            self.out / "update_transaction.json",
            {
                "at": now(),
                "actual_parent": self.bank,
                "publication": bank,
                "actual_teacher_value": value,
                "management": management,
                "same_main_teacher_request_sha256": sha(
                    MAIN / "teacher/trace_b4/wire_request.json"
                ),
                "all_valid_edits_unconditionally_published_without_effect_gate": True,
            },
        )
        self.bank = bank
        self.load_model(4, MAIN)
        fresh = [self.answer("later", "trace_procedures", row, self.bank) for row in self.future]
        assert len(self.native) == 8 and len(self.teachers) == 1
        self.audit(fresh, "all8_new_native_answers_before_grading")
        groups = {
            a: [read(MAIN / "later" / a / f"{r['id']}.public.json") for r in self.future]
            for a in MAIN_ARMS
        }
        groups["paired_final_update"] = fresh
        scored = self.score_groups(groups, "paired")
        assert len({u["response"]["raw_id"] for values in groups.values() for u in values}) == 40
        main = read(MAIN / "main_completion.json")
        close({a: points(scored[a]) for a in MAIN_ARMS}, main["development"])
        done = {
            "at": now(),
            "new_native_calls": 8,
            "new_teacher_calls": 1,
            "explicit_existing_main_endpoint_references": 32,
            "results": {a: points(u) for a, u in scored.items()},
            "paired_new_minus_control": {
                a: paired(scored[a], scored["paired_final_update"]) for a in MAIN_ARMS
            },
            "management": management,
            "new_native_usage": usage(self.native),
            "new_teacher_usage": usage(self.teachers, teacher=True),
            "all8_new_answers_saved_and_replayed_before_grading_or_main_scores": True,
            "single_update_intervention_not_full_paired_training_or_independent_repeat": True,
        }
        RunStore.immutable_json(self.out / "completion.json", done)
        RunStore.atomic_json(
            self.out / "progress.json",
            {
                "at": now(),
                "state": "completed",
                "completed_native_calls": 8,
                "completed_teacher_calls": 1,
            },
        )

    def execute(self):
        self.declare()
        if self.mode == "paired":
            self.progress("waiting_for_exact_main_exit_and_gpu_lease")
            while self.parent_alive():
                self.check()
                time.sleep(5)
        with (ROOT / "artifacts/gpu_generation.lock").open("a+") as lease:
            while True:
                self.check()
                try:
                    fcntl.flock(lease.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    time.sleep(5)
            if self.mode == "main":
                self.run_main()
            else:
                self.run_paired()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["main", "paired"])
    args = parser.parse_args()
    study = Completion(args.mode)
    try:
        study.execute()
    except BaseException as exc:
        failure = {
            "at": now(),
            "error": repr(exc),
            "completed_native_calls": len(study.native),
            "completed_teacher_calls": len(study.teachers),
            "teacher_attempts": study.teacher_attempts,
            "main_component_completed": (study.out / "main_completion.json").is_file(),
            "no_retry_fallback_or_old_bank_selection": True,
        }
        RunStore.immutable_json(study.out / "failure.json", failure)
        RunStore.atomic_json(
            study.out / "progress.json",
            {"state": "stopped" if isinstance(exc, InterruptedError) else "failed", **failure},
        )
        raise
