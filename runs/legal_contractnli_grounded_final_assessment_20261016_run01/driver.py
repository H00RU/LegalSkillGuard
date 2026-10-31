"""Only the predeclared44 final evaluations of an explicitly stopped parent."""

from __future__ import annotations

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

import numpy as np

from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.inference.native import WireClient
from legal_skill_guard.learning.audit import close, original_score
from legal_skill_guard.learning.experiment import ENDPOINTS, now, points, read, sha
from legal_skill_guard.learning.procedures import ARMS, ProcedureStudy
from legal_skill_guard.learning.publication import paired
from legal_skill_guard.task import original_feedback
from legal_skill_guard.utils.hashing import canonical_json_sha256

ROOT = Path(__file__).resolve().parents[2]
PARENT = ROOT / "runs/legal_contractnli_grounded_feedback_20261016_run01"
RUN_ID = "legal_contractnli_grounded_final_assessment_20261016_run01"
PROTOCOL = ROOT / "reports/experiments/grounded_feedback_20261016/final_assessment_protocol.md"


def usage(records, teacher=False):
    keys = (
        ("input_tokens", "output_tokens", "reasoning_output_tokens")
        if teacher
        else ("prompt_tokens", "completion_tokens")
    )
    rows = [r["invocation"]["usage"] if teacher else r["response"] for r in records]
    return {k: sum(r[k] for r in rows) for k in keys}


class FinalAssessment(ProcedureStudy):
    def __init__(self):
        self.run_id, self.out = RUN_ID, ROOT / "runs" / RUN_ID
        assert not (self.out / "declaration.json").exists(), "Never restart an existing Run ID"
        assert read(PARENT / "progress.json")["state"] == "stopped"
        assert not Path("/proc/3003556").exists(), "Original worker must have exited"
        base = ROOT / "configs/contractnli_grounded_feedback.json"
        frozen = read(base.with_suffix(".frozen.json"))
        assert sha(base) == frozen["config_sha256"]
        self.cfg = {**read(base), "planned_new_native_calls": 44, "planned_new_teacher_calls": 0}
        self.report = ROOT / self.cfg["report_directory"] / RUN_ID
        packet = read(ROOT / self.cfg["input_packet"])
        self.labels, self.training = packet["public_hypotheses"], packet["training"]
        self.future = packet["later_inputs_no_annotation_sets"]
        assert len(self.training) == 24 and len(self.future) == 8
        assert all("annotation_sets" not in r for r in self.future)
        self.native, self.units, self.teachers = [], [], []
        self.teacher_attempts, self.current_batch, self.stop = 0, 4, False
        self.meter = WireClient(self.cfg["generation"])
        self.inherited_units = [read(p) for p in sorted(PARENT.glob("batch*/*/*.public.json"))]
        self.inherited_native = [
            read(p) for p in sorted(PARENT.glob("batch*/*/*.final.native.json"))
        ]
        self.shared_units = [read(p) for p in sorted(PARENT.glob("batch1_before/*/*.shared.json"))]
        self.inherited_teachers = [
            read(p) for p in sorted((PARENT / "teacher").glob("*/response.json"))
        ]
        assert len(self.inherited_units) == len(self.inherited_native) == 78
        assert len(self.shared_units) == 12 and len(self.inherited_teachers) == 5
        self.bank = read(PARENT / "update_transactions/trace_b4.json")["publication"]
        self.static = read(PARENT / "static_procedures.json")["library"]
        self.before = {
            r["id"]: read(PARENT / f"batch4_before/trace_procedures/{r['id']}.public.json")
            for r in self.training
            if r["batch"] == 4
        }
        self.after = {
            r["id"]: read(
                PARENT / f"batch{r['batch']}_after/trace_procedures/{r['id']}.public.json"
            )
            for r in self.training
            if r["batch"] < 4
        }
        self.summaries = [read(PARENT / f"batch{b}_summary.json") for b in (1, 2, 3)]
        manifests = [
            read(PARENT / f"evidence_models/ordinary_M{b}.manifest.json") for b in (1, 2, 3, 4)
        ]
        self.state_versions = {m["state_sha256"]: m for m in manifests}
        for m in manifests:
            assert sha(m["path"]) == m["pickle_sha256"]
        self.state = manifests[-1]["state_sha256"]
        with Path(manifests[-1]["path"]).open("rb") as stream:
            self.model = pickle.load(stream)
        self.versions = {canonical_json_sha256([]): []}
        for b in (1, 2, 3, 4):
            bank = read(PARENT / f"update_transactions/trace_b{b}.json")["publication"]
            self.versions[canonical_json_sha256(bank)] = bank
        self.bindings = read(PARENT / "declaration.json")["frozen_bindings"].copy()
        assert all(sha(p) == h for p, h in self.bindings.items())
        paths = [p for p in PARENT.rglob("*") if p.is_file() and p.suffix in (".json", ".pickle")]
        paths += [Path(__file__), PROTOCOL]
        self.bindings.update({str(p.resolve()): sha(p) for p in paths})
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: setattr(self, "stop", True))

    def teacher_call(self, *args, **kwargs):
        raise RuntimeError("Final assessment prohibits all new teacher calls or updates")

    def progress(self, stage, **extra):
        super().progress(stage, inherited_native_calls=78, inherited_teacher_calls=5, **extra)

    def audit(self, units, name):
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="X does not have valid feature names, but LGBMClassifier was fitted with feature names",
            )
            self.audit_native(units, name)

    def execute(self):
        self.check()
        RunStore.immutable_json(
            self.out / "declaration.json",
            {
                "at": now(),
                "pid": os.getpid(),
                "argv": sys.argv,
                "config": self.cfg,
                "frozen_bindings": self.bindings,
                "explicit_stopped_parent": str(PARENT),
                "new_native_calls_planned": 44,
                "new_teacher_calls_planned": 0,
                "inherited_native_calls": 78,
                "inherited_teacher_calls": 5,
                "original_stop_not_erased_or_silently_resumed": True,
                "post_stop_fixed_assessment_not_independent_learning_repeat": True,
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
        self.progress("waiting_for_gpu_lease")
        with (ROOT / "artifacts/gpu_generation.lock").open("a+") as lease:
            while True:
                self.check()
                try:
                    fcntl.flock(lease.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    time.sleep(2)
            self.run_evaluation()

    def run_evaluation(self):
        rows = [r for r in self.training if r["batch"] == 4]
        after = self.collect("batch4_after", "trace_procedures", rows, self.bank)
        before = {
            a: [read(PARENT / f"batch4_before/{a}/{r['id']}.public.json") for r in rows]
            for a in ("strong_empty", "ordinary_memory", "trace_procedures")
        }
        summary = {
            "at": now(),
            "batch": 4,
            "source_ids": [r["id"] for r in rows],
            "before": {a: points(u) for a, u in before.items()},
            "after": {"trace_procedures": points(after)},
            "library_management": read(PARENT / "update_transactions/trace_b4.json")["management"],
            "update_effects": paired(before["trace_procedures"], after),
            "after_is_seen_fit_with_new_gold_not_pure_skill_effect": True,
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
        later = {a: [] for a in ARMS}
        for index, row in enumerate(self.future):
            offset = index % len(ARMS)
            for arm in ARMS[offset:] + ARMS[:offset]:
                later[arm].append(self.answer("later", arm, row, self.bank_for(arm)))
        self.complete(later)

    def complete(self, later):
        self.check()
        assert len(self.native) == len(self.units) == 44 and not self.teachers
        assert all(len(v) == 8 for v in later.values())
        self.audit(
            self.inherited_units + self.shared_units + self.units,
            "all122_physical_and12_shared_before_grading",
        )
        gold = read(ROOT / self.cfg["grading_only"])["annotations"]
        with zipfile.ZipFile(ROOT / self.cfg["source_archive"]) as archive:
            author = json.loads(archive.read("contract-nli/train.json"))
        originals = {r["id"]: r for r in author["documents"]}
        rows, by = {r["id"]: r for r in self.future}, {}
        for arm, units in later.items():
            by[arm] = []
            for u in units:
                row, source = rows[u["document_id"]], originals[u["document_id"]]
                assert row["text"] == source["text"] and row["spans"] == source["spans"]
                assert gold[str(row["id"])] == source["annotation_sets"][0]["annotations"]
                feedback = original_feedback(
                    u["response"], row, gold[str(row["id"])], list(self.labels)
                )
                close(
                    original_score(u["response"], row, gold[str(row["id"])], list(self.labels)),
                    feedback,
                )
                scored = {**u, **feedback}
                RunStore.immutable_json(
                    self.out / "later_scored" / arm / f"{row['id']}.json", scored
                )
                by[arm].append(scored)
        native = self.inherited_native + self.native
        assert len({n["response"]["raw_id"] for n in native}) == len(native) == 122
        results, intervals = {a: points(u) for a, u in by.items()}, {}
        rng = np.random.default_rng(self.cfg["bootstrap_seed"])
        for control in ARMS[:-1]:
            draws = {e: [] for e in ENDPOINTS}
            for _ in range(self.cfg["bootstrap_draws"]):
                indices = rng.integers(0, 8, 8)
                a, b = (
                    points([by[arm][i] for i in indices]) for arm in ("trace_procedures", control)
                )
                for e in ENDPOINTS:
                    draws[e].append(a[e] - b[e])
            intervals[control] = {
                e: {
                    "point": results["trace_procedures"][e] - results[control][e],
                    "ci95_descriptive_conditional_on_one_learning_run": list(
                        map(float, np.quantile(x, [0.025, 0.975]))
                    ),
                }
                for e, x in draws.items()
            }
        done = {
            "at": now(),
            "run_id": RUN_ID,
            "explicit_stopped_parent": str(PARENT),
            "new_native_calls": 44,
            "new_teacher_calls": 0,
            "inherited_native_calls": 78,
            "inherited_teacher_calls": 5,
            "total_physical_native_calls": 122,
            "explicit_inherited_cold_shared_observations": 12,
            "batches": self.summaries,
            "development": results,
            "descriptive_source_intervals": intervals,
            "paired_trace_minus_control": {
                a: paired(by[a], by["trace_procedures"]) for a in ARMS[:-1]
            },
            "new_native_usage": usage(self.native),
            "new_teacher_usage": usage([], teacher=True),
            "all_ancestry_native_usage": usage(native),
            "all_ancestry_teacher_usage": usage(self.inherited_teachers, teacher=True),
            "all32_endpoint_answers_saved_and_replayed_before_grading": True,
            "post_stop_assessment_not_independent_or_original_worker_success": True,
            "exposed_development_not_official_test": True,
            "no_current_gold_to_solver_no_bank_selection_or_new_learning": True,
        }
        RunStore.immutable_json(self.out / "completion.json", done)
        RunStore.immutable_json(self.report / "complete_metrics.json", done)
        RunStore.atomic_json(
            self.out / "progress.json",
            {
                "at": now(),
                "state": "completed",
                "run_id": RUN_ID,
                "completed_native_calls": 44,
                "completed_teacher_calls": 0,
                "inherited_native_calls": 78,
                "inherited_teacher_calls": 5,
            },
        )


if __name__ == "__main__":
    study = FinalAssessment()
    try:
        study.execute()
    except BaseException as exc:
        failed = {
            "at": now(),
            "error": repr(exc),
            "completed_native_calls": len(study.native),
            "completed_teacher_calls": 0,
            "inherited_native_calls": 78,
            "no_retry_fallback_or_old_bank_selection": True,
        }
        RunStore.immutable_json(study.out / "failure.json", failed)
        RunStore.atomic_json(
            study.out / "progress.json",
            {"state": "stopped" if isinstance(exc, InterruptedError) else "failed", **failed},
        )
        raise
