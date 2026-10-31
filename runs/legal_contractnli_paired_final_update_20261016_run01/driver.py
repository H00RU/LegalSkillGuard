"""One final-update feedback intervention, never a replacement main learner."""

from __future__ import annotations

import fcntl
import json
import os
import pickle
import signal
import sys
import time
import zipfile
from pathlib import Path

from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.inference.native import WireClient
from legal_skill_guard.learning.audit import close, original_score
from legal_skill_guard.learning.experiment import now, points, read, sha
from legal_skill_guard.learning.procedures import (
    ARMS,
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
from legal_skill_guard.utils.hashing import canonical_json_sha256

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
PARENT_ID = "legal_contractnli_atomic_boundaries_20261015_run01"
PARENT = ROOT / "runs" / PARENT_ID
PROTOCOL = ROOT / "reports/experiments/paired_final_update_20261016/protocol.md"
PAIR_INSTRUCTION = (
    " This final-update intervention additionally supplies ALL six current-batch "
    "empty-library executions under the exact same ordinary-tool state, source, "
    "hypotheses and decode settings. They are the controlled same-lawyer arm, not "
    "another learner's memory. Compare every actual pair, including both-correct, "
    "both-wrong, corrected and harmed components. Distinguish a basic capability "
    "failure from a plausible whole-library-induced error; preserve the lawyer's "
    "already-correct scope distinctions. A single stochastic pair is not reliable "
    "per-skill causal credit, and reported skill IDs do not prove execution. "
    "Use source-grounded evidence to revise, merge or remove misleading boundaries, "
    "not merely append more instructions for every failure. Do not force a change, "
    "count, deletion or score gate. Do not attribute older different-policy empty "
    "answers to this parent. Only the current batch has matched empty-library "
    "controls; previous-batch post-update observations have no such control here. "
    "All valid edits are published, even if later performance is worse."
)


class PairedFinalUpdate(ProcedureStudy):
    def __init__(self):
        self.cfg = {
            **read(ROOT / "configs/contractnli_atomic_boundaries.json"),
            "planned_new_native_calls": 8,
            "planned_new_teacher_calls": 1,
        }
        self.run_id, self.out = OUT.name, OUT
        packet = read(ROOT / self.cfg["input_packet"])
        self.labels, self.training = packet["public_hypotheses"], packet["training"]
        self.future = packet["later_inputs_no_annotation_sets"]
        assert [r["id"] for r in self.future] == [568, 327, 342, 374, 624, 270, 341, 135]
        assert all("annotation_sets" not in r for r in self.future)
        self.parent_launch = read(ROOT / "artifacts/launches" / (PARENT_ID + ".json"))
        proc = Path("/proc") / str(self.parent_launch["pid"])
        self.parent_start = (proc / "stat").read_text().rsplit(")", 1)[1].split()[19]
        self.bindings = dict(read(PARENT / "declaration.json")["frozen_bindings"])
        pins = [Path(__file__), PROTOCOL, PARENT / "declaration.json"]
        pins += [PARENT / "update_transactions/trace_b3.json"]
        pins += [PARENT / "evidence_models/ordinary_M3.pickle"]
        pins += [PARENT / "evidence_models/ordinary_M3.manifest.json"]
        self.bindings.update({str(p): sha(p) for p in pins})
        self.native, self.units, self.teachers, self.shared_units = [], [], [], []
        self.teacher_attempts, self.current_batch, self.stop = 0, 4, False
        self.bank, self.static, self.public_only = [], [], []
        self.state_versions, self.before, self.after = {}, {}, {}
        self.meter = WireClient(self.cfg["generation"])
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: setattr(self, "stop", True))

    def parent_alive(self):
        proc = Path("/proc") / str(self.parent_launch["pid"])
        try:
            args = [s.decode() for s in (proc / "cmdline").read_bytes().split(b"\0") if s]
            stat = (proc / "stat").read_text().rsplit(")", 1)[1].split()
        except (FileNotFoundError, ProcessLookupError):
            return False
        if args and (args != self.parent_launch["actual_argv"] or stat[19] != self.parent_start):
            raise RuntimeError("Parent PID reused; do not infer successful completion")
        return bool(args) and stat[0] != "Z"

    def load_model(self, batch):
        manifest = read(PARENT / f"evidence_models/ordinary_M{batch}.manifest.json")
        assert sha(manifest["path"]) == manifest["pickle_sha256"]
        self.state = manifest["state_sha256"]
        self.state_versions[self.state] = manifest
        with Path(manifest["path"]).open("rb") as stream:
            self.model = pickle.load(stream)

    def one_update(self):
        self.bank = read(PARENT / "update_transactions/trace_b3.json")["publication"]
        self.load_model(3)
        current = [r for r in self.training if r["batch"] == 4]
        previous = [r for r in self.training if r["batch"] == 3]
        self.before = {
            r["id"]: read(PARENT / f"batch4_before/trace_procedures/{r['id']}.public.json")
            for r in current
        }
        self.after = {
            r["id"]: read(PARENT / f"batch3_after/trace_procedures/{r['id']}.public.json")
            for r in previous
        }
        expected = self.teacher_cases(4, include_trace=True)
        wire_path = PARENT / "teacher/trace_b4/wire_request.json"
        wire = read(wire_path)
        body = json.loads(wire["user_prompt"])
        assert wire["system_prompt"] == PROCEDURE_TEACHER
        assert body["same_parent_library_and_tool_original_train_cases"] == expected
        assert body["complete_actual_parent_library"] == self.bank
        controls, comparisons, audited = (
            [],
            [],
            list(self.before.values()) + list(self.after.values()),
        )
        for row in current:
            unit = self.before[row["id"]]
            control = read(PARENT / f"batch4_before/ordinary_memory/{row['id']}.public.json")
            assert control["published_library"] == []
            assert control["published_library_sha256"] == canonical_json_sha256([])
            assert control["actual_factual_trace"] == unit["actual_factual_trace"]
            assert control["hypothesis_ids"] == unit["hypothesis_ids"] == list(self.labels)
            controls.append(
                {
                    "document_id": row["id"],
                    "actual_empty_library_observation": self.observation(control, True),
                }
            )
            comparisons.append(
                {
                    "document_id": row["id"],
                    "whole_library_comparison_not_per_skill_causal_credit": paired(
                        [control], [unit]
                    ),
                }
            )
            audited.append(control)
        self.audit_native(audited, "all18_actual_training_observations")
        body["current_batch_all_same_tool_empty_library_observations"] = controls
        body["all_current_batch_paired_component_feedback"] = comparisons
        body["not_full_paired_feedback_training_or_per_skill_randomized_credit"] = True
        source_ids = [c["document_id"] for c in expected]
        value = self.teacher_call(
            "paired_final_update_b4",
            PROCEDURE_TEACHER + PAIR_INSTRUCTION,
            body,
            differential_schema(
                self.labels, self.bank, source_ids, guidance_schema=BOUNDARY_GUIDANCE_SCHEMA
            ),
        )
        bank = apply_differential_publication(
            self.bank, value, self.labels, source_ids, guidance_schema=BOUNDARY_GUIDANCE_SCHEMA
        )
        tokens = self.validate_library(bank)
        result = {
            "at": now(),
            "actual_parent": self.bank,
            "publication": bank,
            "actual_teacher_value": value,
            "management": publication_statistics(self.bank, value, bank, tokens),
            "same_original_teacher_wire_before_addition_sha256": sha(wire_path),
            "all12_original_main_observations_and6_empty_controls_verified": True,
            "source_case_ids": source_ids,
            "new_teacher_calls": 1,
            "all_valid_edits_unconditionally_published_without_efficacy_gate": True,
        }
        RunStore.immutable_json(OUT / "update_transaction.json", result)
        self.bank = bank

    def execute(self):
        assert not (OUT / "declaration.json").exists(), "New Run ID only"
        self.check()
        RunStore.immutable_json(
            OUT / "declaration.json",
            {
                "at": now(),
                "pid": os.getpid(),
                "argv": sys.argv,
                "frozen_bindings": self.bindings,
                "parent_launch": self.parent_launch,
                "parent_start_ticks": self.parent_start,
                "parent_progress_at_declaration": read(PARENT / "progress.json"),
                "planned_new_native_calls": 8,
                "planned_new_teacher_calls": 1,
                "explicit_parent_endpoint_references": 40,
                "single_final_update_not_full_online_learning_or_independent_repeat": True,
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
        self.progress("waiting_for_exact_parent_exit_and_gpu_lease")
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
            progress = read(PARENT / "progress.json")
            if progress["state"] != "completed" or not (PARENT / "completion.json").is_file():
                value = {
                    "at": now(),
                    "state": "cancelled",
                    "reason": "Parent did not complete the predeclared full study",
                    "completed_native_calls": 0,
                    "completed_teacher_calls": 0,
                }
                RunStore.immutable_json(OUT / "cancellation.json", value)
                RunStore.atomic_json(OUT / "progress.json", value)
                return
            assert len(list((PARENT / "later").rglob("*.public.json"))) == 40
            assert len(list(PARENT.rglob("*.final.native.json"))) == 130
            assert len(list((PARENT / "teacher").glob("*/response.json"))) == 6
            pinned = sorted((PARENT / "later").rglob("*.json"))
            pinned += [
                PARENT / "teacher/trace_b4/wire_request.json",
                PARENT / "update_transactions/trace_b4.json",
                PARENT / "evidence_models/ordinary_M4.pickle",
                PARENT / "evidence_models/ordinary_M4.manifest.json",
                PARENT / "memory_frozen_before_later.json",
            ]
            acquired_bindings = {str(p): sha(p) for p in pinned}
            self.bindings.update(acquired_bindings)
            RunStore.immutable_json(
                OUT / "accepted_parent.json",
                {
                    "at": now(),
                    "parent_completion_sha256": sha(PARENT / "completion.json"),
                    "parent_progress": progress,
                    "parent_endpoint_scores_not_opened_by_this_worker": True,
                    "exact_parent_no_longer_live": not self.parent_alive(),
                    "parent_artifacts_bound_before_new_teacher_or_generation": acquired_bindings,
                },
            )
            self.one_update()
            self.load_model(4)
            for row in self.future:
                self.answer("later", "trace_procedures", row, self.bank)
            self.finish_diagnostic()

    def finish_diagnostic(self):
        self.check()
        assert len(self.native) == len(self.units) == 8 and len(self.teachers) == 1
        assert len({u["response"]["raw_id"] for u in self.units}) == 8
        self.audit_native(self.units, "all8_new_answers_before_grading")
        gold = read(ROOT / self.cfg["grading_only"])["annotations"]
        assert sha(ROOT / self.cfg["source_archive"]) == self.cfg["source_archive_sha256"]
        with zipfile.ZipFile(ROOT / self.cfg["source_archive"]) as archive:
            author = json.loads(archive.read("contract-nli/train.json"))
        assert author["labels"] == self.labels
        originals = {r["id"]: r for r in author["documents"]}
        for row in self.training:
            assert row["text"] == originals[row["id"]]["text"]
            assert row["spans"] == originals[row["id"]]["spans"]
            assert (
                row["annotation_sets"][0]["annotations"]
                == originals[row["id"]]["annotation_sets"][0]["annotations"]
            )
        by = {a: [] for a in (*ARMS, "paired_final_update")}
        frozen = read(PARENT / "memory_frozen_before_later.json")
        expected_banks = {
            "strong_empty": [],
            "ordinary_memory": [],
            "trace_procedures": frozen["main_library"],
            "static_procedures": frozen["static_library"],
            "public_only_final_update": frozen["public_only_final_update_library"],
            "paired_final_update": self.bank,
        }
        new = {u["document_id"]: u for u in self.units}
        references = []
        for row in self.future:
            target = gold[str(row["id"])]
            assert target == originals[row["id"]]["annotation_sets"][0]["annotations"]
            assert (
                row["text"] == originals[row["id"]]["text"]
                and row["spans"] == originals[row["id"]]["spans"]
            )
            for arm in by:
                unit = (
                    new[row["id"]]
                    if arm == "paired_final_update"
                    else read(PARENT / "later" / arm / f"{row['id']}.public.json")
                )
                if arm != "paired_final_update":
                    references.append(unit)
                assert unit["published_library"] == expected_banks[arm]
                assert unit["published_library_sha256"] == canonical_json_sha256(
                    expected_banks[arm]
                )
                assert unit["actual_factual_trace"]["ordinary_model_state"] == (
                    None if arm == "strong_empty" else self.state
                )
                feedback = original_feedback(unit["response"], row, target, list(self.labels))
                close(original_score(unit["response"], row, target, list(self.labels)), feedback)
                if arm != "paired_final_update":
                    close(feedback, read(PARENT / "later_scored" / arm / f"{row['id']}.json"))
                scored = {
                    **unit,
                    **feedback,
                    "existing_parent_response_not_new_generation": arm != "paired_final_update",
                }
                RunStore.immutable_json(OUT / "scored" / arm / f"{row['id']}.json", scored)
                by[arm].append(scored)
        self.audit_native(references, "all40_actual_parent_references")
        assert len({u["response"]["raw_id"] for values in by.values() for u in values}) == 48
        done = {
            "at": now(),
            "results": {a: points(u) for a, u in by.items()},
            "paired_new_minus_parent": {a: paired(by[a], by["paired_final_update"]) for a in ARMS},
            "management": read(OUT / "update_transaction.json")["management"],
            "new_native_calls": 8,
            "new_teacher_calls": 1,
            "explicit_parent_endpoint_references": 40,
            "new_native_usage": {
                k: sum(n["response"][k] for n in self.native)
                for k in ("prompt_tokens", "completion_tokens")
            },
            "new_teacher_usage": {
                k: sum(t["invocation"]["usage"][k] for t in self.teachers)
                for k in ("input_tokens", "output_tokens", "reasoning_output_tokens")
            },
            "single_update_information_intervention_not_full_paired_feedback_learning": True,
            "not_independent_training_repetition_or_official_test_or_per_skill_causal_credit": True,
            "all8_new_answers_saved_and_audited_before_grading": True,
        }
        RunStore.immutable_json(OUT / "completion.json", done)
        RunStore.atomic_json(
            OUT / "progress.json",
            {
                "at": now(),
                "state": "completed",
                "completed_native_calls": 8,
                "completed_teacher_calls": 1,
            },
        )


if __name__ == "__main__":
    study = PairedFinalUpdate()
    try:
        study.execute()
    except BaseException as exc:
        error = {
            "at": now(),
            "error": repr(exc),
            "completed_native_calls": len(study.native),
            "completed_teacher_calls": len(study.teachers),
            "teacher_attempts": study.teacher_attempts,
            "no_retry_or_fallback": True,
        }
        RunStore.immutable_json(OUT / "failure.json", error)
        RunStore.atomic_json(
            OUT / "progress.json",
            {"state": "stopped" if isinstance(exc, InterruptedError) else "failed", **error},
        )
        raise
