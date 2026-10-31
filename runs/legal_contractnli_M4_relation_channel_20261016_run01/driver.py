"""Eight-source explicit-relation channel intervention, zero new teachers."""

from __future__ import annotations

import copy
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
from legal_skill_guard.learning.procedures import ProcedureStudy
from legal_skill_guard.learning.publication import paired
from legal_skill_guard.task import original_feedback

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
MAIN_ID = "legal_contractnli_atomic_completion_20261016_run01"
PAIR_ID = "legal_contractnli_paired_final_update_20261016_run02"
MAIN = ROOT / "runs" / MAIN_ID
PROTOCOL = ROOT / "reports/experiments/M4_relation_channel_20261016/protocol.md"
ARMS = ("strong_empty", "ordinary_memory", "static_procedures", "trace_procedures")
TREATMENT = "explicit_relations_suppressed"


class RelationChannel(ProcedureStudy):
    def __init__(self):
        assert not (OUT / "declaration.json").exists(), "Never restart an existing Run ID"
        parent = read(MAIN / "declaration.json")
        self.cfg = {
            **parent["config"],
            "run_id": OUT.name,
            "planned_new_native_calls": 8,
            "planned_new_teacher_calls": 0,
        }
        self.run_id, self.out = OUT.name, OUT
        packet = read(ROOT / self.cfg["input_packet"])
        self.labels, self.training = packet["public_hypotheses"], packet["training"]
        self.future = packet["later_inputs_no_annotation_sets"]
        frozen = read(MAIN / "memory_frozen_before_later.json")
        self.original_bank = frozen["main_library"]
        self.bank = copy.deepcopy(self.original_bank)
        self.changed = []
        for old, new in zip(self.original_bank, self.bank, strict=True):
            if old["guidance"]["relation_if_established"] is not None:
                self.changed.append(old["id"])
            new["guidance"]["relation_if_established"] = None
            assert {**old["guidance"], "relation_if_established": None} == new["guidance"]
            assert old["id"] == new["id"] and old["hypothesis_ids"] == new["hypothesis_ids"]
        assert self.changed and len(self.bank) == 24
        assert [r["id"] for r in self.future] == [568, 327, 342, 374, 624, 270, 341, 135]
        assert all("annotation_sets" not in r for r in self.future)
        self.static = frozen["static_library"]
        manifest = read(MAIN / "evidence_models/ordinary_M4.manifest.json")
        assert sha(manifest["path"]) == manifest["pickle_sha256"]
        with Path(manifest["path"]).open("rb") as stream:
            self.model = pickle.load(stream)
        self.state = manifest["state_sha256"]
        self.state_versions = {self.state: manifest}
        self.meter = WireClient(self.cfg["generation"])
        self.native, self.units, self.teachers = [], [], []
        self.teacher_attempts, self.current_batch, self.stop = 0, 4, False
        self.bindings = dict(parent["frozen_bindings"])
        pins = [
            Path(__file__),
            PROTOCOL,
            MAIN / "main_completion.json",
            MAIN / "memory_frozen_before_later.json",
            Path(manifest["path"]),
            MAIN / "evidence_models/ordinary_M4.manifest.json",
        ]
        pins.extend((MAIN / "later").rglob("*.json"))
        self.bindings.update({str(p): sha(p) for p in pins})
        self.dependencies = []
        for rid in (MAIN_ID, PAIR_ID):
            launch = read(ROOT / "artifacts/launches" / (rid + ".json"))
            proc = Path("/proc") / str(launch["pid"])
            try:
                ticks = (proc / "stat").read_text().rsplit(")", 1)[1].split()[19]
            except FileNotFoundError:
                ticks = None
            self.dependencies.append({**launch, "start_ticks_at_declaration": ticks})
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: setattr(self, "stop", True))

    def dependency_alive(self, dependency):
        proc = Path("/proc") / str(dependency["pid"])
        try:
            args = [s.decode() for s in (proc / "cmdline").read_bytes().split(b"\0") if s]
            stat = (proc / "stat").read_text().rsplit(")", 1)[1].split()
        except (FileNotFoundError, ProcessLookupError):
            return False
        if args and (
            args != dependency["actual_argv"]
            or stat[19] != dependency["start_ticks_at_declaration"]
        ):
            raise RuntimeError("Exact dependency PID was replaced")
        return bool(args) and stat[0] != "Z"

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
            OUT / "declaration.json",
            {
                "at": now(),
                "pid": os.getpid(),
                "argv": sys.argv,
                "config": self.cfg,
                "frozen_bindings": self.bindings,
                "dependencies": self.dependencies,
                "source_ids": [r["id"] for r in self.future],
                "original_M4_library": self.original_bank,
                "delivered_intervention_library": self.bank,
                "uniformly_suppressed_explicit_relation_skill_ids": self.changed,
                "all_other_guidance_fields_scopes_order_ids_unchanged": True,
                "new_native_calls": 8,
                "new_teacher_calls": 0,
                "existing_main_response_references": 32,
                "posthoc_exposed_development_diagnostic_not_new_learning_or_confirmation": True,
                "operator_has_seen_complete_main_outcomes_no_case_selection": True,
            },
        )
        RunStore.immutable_json(
            OUT / "source_snapshot.json",
            {
                "files": {
                    p: {"sha256": h, "utf8_text": Path(p).read_text()}
                    for p, h in self.bindings.items()
                    if Path(p).suffix in (".py", ".md", ".txt")
                }
            },
        )
        self.progress("waiting_for_both_exact_dependencies_and_gpu_lease")
        while any(self.dependency_alive(d) for d in self.dependencies):
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
            assert len(list((MAIN / "later").glob("*/*.public.json"))) == 32
            RunStore.immutable_json(
                OUT / "gpu_lease_acquired.json",
                {
                    "at": now(),
                    "both_dependencies_no_longer_live": True,
                    "source_bank_same_completed_main_not_selected_checkpoint": True,
                    "actual_intervention_library_tokens": self.validate_library(self.bank),
                },
            )
            for row in self.future:
                self.answer("later", "trace_procedures", row, self.bank)
            self.finish_intervention()

    def finish_intervention(self):
        self.check()
        assert len(self.native) == len(self.units) == 8 and not self.teachers
        groups = {
            a: [read(MAIN / "later" / a / f"{r['id']}.public.json") for r in self.future]
            for a in ARMS
        }
        groups[TREATMENT] = self.units
        self.audit(
            [u for units in groups.values() for u in units],
            "all40_native_answers_before_new_grading",
        )
        gold = read(ROOT / self.cfg["grading_only"])["annotations"]
        assert sha(ROOT / self.cfg["source_archive"]) == self.cfg["source_archive_sha256"]
        with zipfile.ZipFile(ROOT / self.cfg["source_archive"]) as archive:
            author = json.loads(archive.read("contract-nli/train.json"))
        originals = {r["id"]: r for r in author["documents"]}
        rows = {r["id"]: r for r in self.future}
        expected_banks = {
            "strong_empty": [],
            "ordinary_memory": [],
            "static_procedures": self.static,
            "trace_procedures": self.original_bank,
            TREATMENT: self.bank,
        }
        scored, identities = {}, []
        for arm, units in groups.items():
            scored[arm] = []
            for unit in units:
                row = rows[unit["document_id"]]
                source = originals[row["id"]]
                assert row["text"] == source["text"] and row["spans"] == source["spans"]
                assert gold[str(row["id"])] == source["annotation_sets"][0]["annotations"]
                assert unit["published_library"] == expected_banks[arm]
                assert unit["actual_factual_trace"]["ordinary_model_state"] == (
                    None if arm == "strong_empty" else self.state
                )
                feedback = original_feedback(
                    unit["response"], row, gold[str(row["id"])], list(self.labels)
                )
                close(
                    original_score(unit["response"], row, gold[str(row["id"])], list(self.labels)),
                    feedback,
                )
                value = {
                    **unit,
                    **feedback,
                    "evaluation_condition": arm,
                    "existing_main_response_not_new_generation": arm != TREATMENT,
                }
                RunStore.immutable_json(OUT / "scored" / arm / f"{row['id']}.json", value)
                scored[arm].append(value)
                identities.append(unit["response"]["raw_id"])
        assert len(set(identities)) == 40
        main = read(MAIN / "main_completion.json")
        close({a: points(scored[a]) for a in ARMS}, main["development"])
        result = {
            "at": now(),
            "run_id": self.run_id,
            "new_native_calls": 8,
            "new_teacher_calls": 0,
            "explicit_existing_response_references": 32,
            "results": {a: points(u) for a, u in scored.items()},
            "paired_intervention_minus_control": {
                a: paired(scored[a], scored[TREATMENT]) for a in ARMS
            },
            "new_native_usage": {
                k: sum(n["response"][k] for n in self.native)
                for k in ("prompt_tokens", "completion_tokens")
            },
            "all8_saved_and_all40_native_replayed_before_new_grading": True,
            "not_a_new_learning_run_or_independent_repeat_or_unexposed_test": True,
            "only_explicit_relation_metadata_removed_not_all_natural_language_relation_cues": True,
        }
        RunStore.immutable_json(OUT / "completion.json", result)
        RunStore.atomic_json(
            OUT / "progress.json",
            {
                "at": now(),
                "state": "completed",
                "completed_native_calls": 8,
                "completed_teacher_calls": 0,
            },
        )


if __name__ == "__main__":
    study = RelationChannel()
    try:
        study.execute()
    except BaseException as exc:
        failure = {
            "at": now(),
            "error": repr(exc),
            "completed_native_calls": len(study.native),
            "completed_teacher_calls": 0,
            "no_retry_fallback_or_answer_repair": True,
        }
        RunStore.immutable_json(OUT / "failure.json", failure)
        RunStore.atomic_json(
            OUT / "progress.json",
            {"state": "stopped" if isinstance(exc, InterruptedError) else "failed", **failure},
        )
        raise
