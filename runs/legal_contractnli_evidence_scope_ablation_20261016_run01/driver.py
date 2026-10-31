"""Archived content ablation; no new learner, teacher, or production layer."""

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
from jsonschema import validate

from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.inference.native import WireClient
from legal_skill_guard.learning.audit import close, original_score
from legal_skill_guard.learning.evidence_programs import evidence_proposals
from legal_skill_guard.learning.experiment import ENDPOINTS, now, points, read, sha
from legal_skill_guard.learning.procedures import (
    ProcedureStudy,
    local_executor_trace,
    procedure_messages,
)
from legal_skill_guard.learning.publication import paired
from legal_skill_guard.task import original_feedback, render_library
from legal_skill_guard.utils.hashing import canonical_json_sha256

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
MAIN = ROOT / "runs/legal_contractnli_grounded_feedback_20261016_run01"
FINAL = ROOT / "runs/legal_contractnli_grounded_final_assessment_20261016_run01"
ACE = ROOT / "runs/legal_contractnli_ace_same_data_20261016_run01"
PROTOCOL = (
    ROOT / "reports/experiments/grounded_feedback_20261016/evidence_scope_ablation_protocol.md"
)
REMOVE = "nda-complete-operative-evidence"
CONDITIONS = ("ordinary_memory", "full_bank", "without_global_evidence_skill")


def remove_id_metadata(value):
    if isinstance(value, dict):
        return {k: remove_id_metadata(v) for k, v in value.items()}
    if isinstance(value, list):
        return [remove_id_metadata(v) for v in value if v != REMOVE]
    return value


class EvidenceScopeAblation(ProcedureStudy):
    def __init__(self):
        assert not (OUT / "declaration.json").exists(), "Never restart a Run ID"
        base = ROOT / "configs/contractnli_grounded_feedback.json"
        self.cfg = {**read(base), "planned_new_native_calls": 26, "planned_new_teacher_calls": 0}
        self.run_id, self.out = OUT.name, OUT
        packet = read(ROOT / self.cfg["input_packet"])
        self.labels, self.training = packet["public_hypotheses"], packet["training"]
        self.future = packet["later_inputs_no_annotation_sets"]
        assert len(self.training) == 24 and len(self.future) == 8
        assert [r["id"] for r in self.future] == self.cfg["expected_later_ids"]
        assert all("annotation_sets" not in r for r in self.future)
        self.rows = [r for r in self.training if r["batch"] >= 2] + self.future
        assert len(self.rows) == len({r["id"] for r in self.rows}) == 26
        self.native, self.units, self.teachers = [], [], []
        self.teacher_attempts, self.current_batch, self.stop = 0, 0, False
        self.meter = WireClient(self.cfg["generation"])
        self.bank, self.static, self.model, self.state = [], [], None, None
        self.full_banks, self.ablated, self.manifests, self.state_versions = {}, {}, {}, {}
        for version in range(1, 5):
            bank = read(MAIN / f"update_transactions/trace_b{version}.json")["publication"]
            assert sum(s["id"] == REMOVE for s in bank) == 1
            self.full_banks[version] = bank
            self.ablated[version] = [s for s in bank if s["id"] != REMOVE]
            manifest = read(MAIN / f"evidence_models/ordinary_M{version}.manifest.json")
            assert sha(manifest["path"]) == manifest["pickle_sha256"]
            self.manifests[version] = manifest
            self.state_versions[manifest["state_sha256"]] = manifest
        self.references = {arm: [] for arm in CONDITIONS[:2]}
        for row in self.rows:
            stage = f"batch{row['batch']}_before" if "batch" in row else "later"
            folder = MAIN if "batch" in row else FINAL
            for arm in self.references:
                actual = "trace_procedures" if arm == "full_bank" else arm
                self.references[arm].append(
                    read(folder / stage / actual / f"{row['id']}.public.json")
                )
        self.dependency = read(ACE / "launch.json")
        self.bindings = read(ACE / "declaration.json")["frozen_bindings"].copy()
        pins = [Path(__file__), PROTOCOL, ACE / "launch.json"]
        pins += list((MAIN / "update_transactions").glob("trace_b*.json"))
        for version, manifest in self.manifests.items():
            pins += [
                Path(manifest["path"]),
                MAIN / f"evidence_models/ordinary_M{version}.manifest.json",
            ]
        for units in self.references.values():
            for unit in units:
                p = Path(unit["raw_artifact"])
                pins += [p, p.with_name(p.name.replace(".final.native.json", ".public.json"))]
        prepared = OUT / "pre_generation_single_removal_identity.json"
        if prepared.exists():
            pins.append(prepared)
        self.bindings.update({str(p.resolve()): sha(p) for p in pins})
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: setattr(self, "stop", True))

    def teacher_call(self, *args, **kwargs):
        raise RuntimeError("This diagnostic has zero teachers and never edits a library")

    def dependency_alive(self):
        proc = Path("/proc") / str(self.dependency["pid"])
        try:
            args = [v.decode() for v in (proc / "cmdline").read_bytes().split(b"\0") if v]
            stat = (proc / "stat").read_text().rsplit(")", 1)[1].split()
        except (FileNotFoundError, ProcessLookupError):
            return False
        if args:
            assert args == self.dependency["actual_argv"]
            assert stat[19] == self.dependency["process_start_ticks"]
        return bool(args) and stat[0] != "Z"

    def select_version(self, version):
        manifest = self.manifests[version]
        assert sha(manifest["path"]) == manifest["pickle_sha256"]
        with Path(manifest["path"]).open("rb") as stream:
            self.model = pickle.load(stream)
        assert not self.model.programs and not self.model.queries
        self.state, self.bank = manifest["state_sha256"], self.ablated[version]

    def audit_wire(self, units, name):
        rows = {r["id"]: r for r in self.training + self.future}
        models = {}
        for unit in units:
            row = rows[unit["document_id"]]
            state = unit["actual_factual_trace"]["ordinary_model_state"]
            if state not in models:
                manifest = self.state_versions[state]
                assert sha(manifest["path"]) == manifest["pickle_sha256"]
                with Path(manifest["path"]).open("rb") as stream:
                    models[state] = pickle.load(stream)
            proposal = evidence_proposals(models[state], row, self.labels)
            close(proposal, unit["actual_factual_trace"]["proposals"])
            bank = unit["published_library"]
            assert canonical_json_sha256(bank) == unit["published_library_sha256"]
            messages, schema = procedure_messages(
                row, self.labels, self.cfg["bundled_solver_system"], bank, proposal
            )
            raw = read(unit["raw_artifact"])
            wire = raw["calls"][0]["request"]
            assert wire["messages"] == messages
            assert wire["response_format"]["json_schema"]["schema"] == schema
            for key in ("model", "temperature", "top_p", "top_k", "max_tokens", "seed"):
                assert wire[key] == self.cfg["generation"][key]
            assert raw["response"] == unit["response"]
            if unit["response"]["finish_reason"] == "stop":
                validate(json.loads(unit["response"]["content"]), schema)
            local_executor_trace(unit)
        RunStore.immutable_json(
            OUT / "audits" / f"{name}.json",
            {
                "at": now(),
                "observations": len(units),
                "source_bank_model_candidates_schema_decode_wire_response_trace_replayed": True,
                "no_new_gold_read_or_answers_repaired": True,
            },
        )

    def prepare(self):
        self.check()
        assert self.dependency_alive(), "Queue against the actual currently live ACE PID"
        self.audit_wire(
            [u for group in self.references.values() for u in group], "all52_reference_wires"
        )
        library_tokens = {
            version: self.validate_library(bank) for version, bank in self.ablated.items()
        }
        changes = []
        for row, control in zip(self.rows, self.references["full_bank"], strict=True):
            version = row["batch"] - 1 if "batch" in row else 4
            self.select_version(version)
            proposal = evidence_proposals(self.model, row, self.labels)
            old, old_schema = procedure_messages(
                row,
                self.labels,
                self.cfg["bundled_solver_system"],
                self.full_banks[version],
                proposal,
            )
            new, new_schema, _, trace = self.messages("trace_procedures", row, self.bank)
            assert control["published_library"] == self.full_banks[version]
            assert control["actual_factual_trace"]["ordinary_model_state"] == self.state
            assert old == read(control["raw_artifact"])["calls"][0]["request"]["messages"]
            assert (
                old[0]["content"].replace(
                    render_library(self.full_banks[version]), render_library(self.bank), 1
                )
                == new[0]["content"]
            )
            assert remove_id_metadata(json.loads(old[1]["content"])) == json.loads(
                new[1]["content"]
            )
            assert remove_id_metadata(old_schema) == new_schema
            close(proposal, trace["proposals"])
            changes.append(
                {
                    "source": row["id"],
                    "version": version,
                    "removed_skill_id": REMOVE,
                    "original_library_sha256": canonical_json_sha256(self.full_banks[version]),
                    "ablated_library_sha256": canonical_json_sha256(self.bank),
                }
            )
        RunStore.immutable_json(
            OUT / "pre_generation_single_removal_identity.json",
            {
                "at": now(),
                "all26_actual_reference_inputs_verified": True,
                "changes": changes,
                "only_record_and_necessary_ID_metadata_removed_no_legal_rewording": True,
                "all4_ablated_library_live_tokens": library_tokens,
                "zero_qualification_generations": True,
            },
        )

    def execute(self):
        self.check()
        prepared = read(OUT / "pre_generation_single_removal_identity.json")
        assert prepared["all26_actual_reference_inputs_verified"]
        assert len(prepared["changes"]) == 26
        RunStore.immutable_json(
            OUT / "declaration.json",
            {
                "at": now(),
                "run_id": self.run_id,
                "pid": os.getpid(),
                "argv": sys.argv,
                "config": self.cfg,
                "frozen_bindings": self.bindings,
                "dependency": self.dependency,
                "new_native_calls": 26,
                "new_teacher_calls": 0,
                "explicit_old_reference_answers": 52,
                "removed_skill_id": REMOVE,
                "source_ids": [r["id"] for r in self.rows],
                "posthoc_content_ablation_not_online_training_or_formal_confirmation": True,
                "length_and_required_ID_metadata_change_not_token_matched_pure_wording_test": True,
                "historical_single_seed_controls_not_contemporaneous_independent_repeats": True,
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
        self.progress("waiting_for_exact_ACE_dependency_and_gpu_lease")
        while self.dependency_alive():
            self.check()
            time.sleep(3)
        with (ROOT / "artifacts/gpu_generation.lock").open("a+") as lease:
            while True:
                self.check()
                try:
                    fcntl.flock(lease.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    time.sleep(3)
            RunStore.immutable_json(
                OUT / "gpu_lease_acquired.json",
                {
                    "at": now(),
                    "exact_ACE_pid_no_longer_live": True,
                    "actual_ACE_progress_at_acquisition": read(ACE / "progress.json"),
                },
            )
            for row in self.rows:
                self.current_batch = row["batch"] if "batch" in row else 4
                version = row["batch"] - 1 if "batch" in row else 4
                self.select_version(version)
                stage = f"batch{row['batch']}_before" if "batch" in row else "later"
                self.answer(stage, "trace_procedures", row, self.bank)
            self.finish_ablation()

    def finish_ablation(self):
        self.check()
        assert len(self.native) == len(self.units) == 26 and not self.teachers
        groups = {**self.references, CONDITIONS[2]: self.units}
        all_units = [u for group in groups.values() for u in group]
        assert len({u["response"]["raw_id"] for u in all_units}) == 78
        self.audit_wire(all_units, "all78_wires_before_new_grading")
        assert sha(ROOT / self.cfg["source_archive"]) == self.cfg["source_archive_sha256"]
        with zipfile.ZipFile(ROOT / self.cfg["source_archive"]) as archive:
            original = json.loads(archive.read("contract-nli/train.json"))
        originals = {r["id"]: r for r in original["documents"]}
        later_gold = read(ROOT / self.cfg["grading_only"])["annotations"]
        scored = {phase: {arm: [] for arm in CONDITIONS} for phase in ("first_encounter", "later")}
        for arm, units in groups.items():
            for row, unit in zip(self.rows, units, strict=True):
                source = originals[row["id"]]
                assert row["text"] == source["text"] and row["spans"] == source["spans"]
                annotations = source["annotation_sets"][0]["annotations"]
                if "batch" in row:
                    assert row["annotation_sets"][0]["annotations"] == annotations
                else:
                    assert later_gold[str(row["id"])] == annotations
                feedback = original_feedback(unit["response"], row, annotations, list(self.labels))
                close(
                    original_score(unit["response"], row, annotations, list(self.labels)), feedback
                )
                phase = "first_encounter" if "batch" in row else "later"
                value = {
                    **unit,
                    **feedback,
                    "condition": arm,
                    "existing_reference_not_new_generation": arm != CONDITIONS[2],
                }
                scored[phase][arm].append(value)
                RunStore.immutable_json(OUT / "scored" / arm / f"{row['id']}.json", value)
        metrics = {
            phase: {arm: points(units) for arm, units in arms.items()}
            for phase, arms in scored.items()
        }
        transitions, intervals = {}, {}
        rng = np.random.default_rng(self.cfg["bootstrap_seed"])
        for phase, arms in scored.items():
            transitions[phase], intervals[phase] = {}, {}
            for control in CONDITIONS[:2]:
                transitions[phase][control] = paired(arms[control], arms[CONDITIONS[2]])
                draws = {key: [] for key in ENDPOINTS}
                n = len(arms[control])
                for _ in range(self.cfg["bootstrap_draws"]):
                    indices = rng.integers(0, n, n)
                    a, b = (
                        points([arms[arm][i] for i in indices]) for arm in (CONDITIONS[2], control)
                    )
                    for key in ENDPOINTS:
                        draws[key].append(a[key] - b[key])
                intervals[phase][control] = {
                    key: {
                        "point": metrics[phase][CONDITIONS[2]][key] - metrics[phase][control][key],
                        "ci95_descriptive_fixed_banks_exposed_sources": list(
                            map(float, np.quantile(values, [0.025, 0.975]))
                        ),
                    }
                    for key, values in draws.items()
                }
        done = {
            "at": now(),
            "run_id": self.run_id,
            "new_native_calls": 26,
            "new_teacher_calls": 0,
            "existing_reference_answers_not_new_generation": 52,
            "metrics": metrics,
            "paired_ablation_minus_control": transitions,
            "descriptive_source_intervals": intervals,
            "new_native_usage": {
                k: sum(n["response"][k] for n in self.native)
                for k in ("prompt_tokens", "completion_tokens")
            },
            "all26_saved_all78_replayed_before_original_gold_scoring": True,
            "no_original_scores_or_answers_changed_no_automatic_publication_or_best_bank_selection": True,
            "not_a_new_learning_run_independent_repeat_or_formal_test": True,
        }
        RunStore.immutable_json(OUT / "completion.json", done)
        RunStore.atomic_json(
            OUT / "progress.json",
            {
                "at": now(),
                "run_id": self.run_id,
                "state": "completed",
                "completed_native_calls": 26,
                "completed_teacher_calls": 0,
            },
        )


if __name__ == "__main__":
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="X does not have valid feature names, but LGBMClassifier was fitted with feature names",
        )
        study = EvidenceScopeAblation()
        if "--prepare-only" in sys.argv:
            study.prepare()
        else:
            try:
                study.execute()
            except BaseException as exc:
                failure = {
                    "at": now(),
                    "run_id": study.run_id,
                    "error": repr(exc),
                    "completed_native_calls": len(study.native),
                    "completed_teacher_calls": 0,
                    "no_retry_fallback_or_original_artifact_repair": True,
                }
                RunStore.immutable_json(OUT / "failure.json", failure)
                RunStore.atomic_json(
                    OUT / "progress.json",
                    {
                        "state": "stopped" if isinstance(exc, InterruptedError) else "failed",
                        **failure,
                    },
                )
                raise
