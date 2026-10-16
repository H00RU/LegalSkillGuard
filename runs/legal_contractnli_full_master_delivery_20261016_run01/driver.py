"""Finite26-call semantic-delivery intervention; no production component."""

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

import numpy as np
from jsonschema import validate

from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.inference.native import WireClient
from legal_skill_guard.learning.audit import close, original_score
from legal_skill_guard.learning.conditioned import conditioned_messages, parent_projection
from legal_skill_guard.learning.evidence_programs import evidence_proposals
from legal_skill_guard.learning.experiment import ENDPOINTS, Comparison, now, points, read, sha
from legal_skill_guard.learning.procedures import local_executor_trace, procedure_messages
from legal_skill_guard.learning.publication import paired
from legal_skill_guard.task import original_feedback, render_library
from legal_skill_guard.utils.hashing import canonical_json_sha256

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
CONFIG = ROOT / "configs/contractnli_source_condition_audit_completion.json"
PARENT = ROOT / "runs/legal_contractnli_source_condition_audit_completion_20261016_run01"
PREFIX = ROOT / "runs/legal_contractnli_source_condition_audit_learning_20261016_run01"
REFERENCES = ("trace_procedures", "ordinary_memory", "unconditional_layout", "strong_empty")
TREATMENT = "complete_master_semantic_delivery"


def complete_semantics(row, labels, system, bank, proposals):
    """Change semantic visibility only; retain the exact old factual operations."""
    old, old_schema, delivery = conditioned_messages(row, labels, system, bank, proposals)
    projection = parent_projection({s["id"]: s for s in bank}, [s["id"] for s in bank])
    messages, schema = procedure_messages(row, labels, system, projection, proposals)
    old_body, body = json.loads(old[1]["content"]), json.loads(messages[1]["content"])
    if "source_layout_link_contract" in old_body:
        body["source_layout_link_contract"] = old_body["source_layout_link_contract"]
        for h in labels:
            if "fallible_source_layout_links" in old_body["hypotheses"][h]:
                body["hypotheses"][h]["fallible_source_layout_links"] = old_body["hypotheses"][h]["fallible_source_layout_links"]
    # All user-body differences must be the two explicit skill-ID metadata fields.
    expected = copy.deepcopy(old_body)
    expected["output_contract"]["common_schema_for_each_hypothesis"]["properties"]["used_skill_ids"] = body["output_contract"]["common_schema_for_each_hypothesis"]["properties"]["used_skill_ids"]
    for h in labels:
        expected["hypotheses"][h]["applicable_published_skill_ids"] = body["hypotheses"][h]["applicable_published_skill_ids"]
    assert expected == body
    for h in labels:
        for before, after in zip(old_schema["properties"][h]["anyOf"], schema["properties"][h]["anyOf"], strict=True):
            expected_schema = copy.deepcopy(before)
            expected_schema["properties"]["used_skill_ids"] = after["properties"]["used_skill_ids"]
            assert expected_schema == after
    assert old[0]["content"].split("\nReusable skills: ", 1)[0] == messages[0]["content"].split("\nReusable skills: ", 1)[0]
    messages[1]["content"] = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    actual = {**delivery,
        "original_filtered_semantic_skill_ids": delivery["actually_delivered_skill_ids"],
        "actually_delivered_skill_ids": [s["id"] for s in projection],
        "actually_delivered_projection": projection,
        "actually_delivered_projection_sha256": canonical_json_sha256(projection),
        "semantic_delivery_policy": "complete_current_master_no_positive_cue_gate_v1",
        "source_operations_policy": "unchanged_original_filtered_operations",
    }
    assert actual["actual_source_operations"] == delivery["actual_source_operations"]
    return messages, schema, actual


class FullMasterDelivery(Comparison):
    def __init__(self):
        assert not (OUT / "declaration.json").exists(), "Never restart or overwrite a Run"
        self.cfg = {**read(CONFIG), "planned_new_native_calls": 26, "planned_new_teacher_calls": 0}
        self.run_id, self.out = OUT.name, OUT
        packet = read(ROOT / self.cfg["input_packet"])
        self.labels = packet["public_hypotheses"]
        self.rows = [
            {k: v for k, v in row.items() if k != "annotation_sets"}
            for row in packet["training"] if row["batch"] > 1
        ] + [{**row, "batch": 5} for row in packet["later_inputs_no_annotation_sets"]]
        assert len(self.rows) == len({r["id"] for r in self.rows}) == 26
        assert all("annotation_sets" not in r for r in self.rows)
        self.by_id = {r["id"]: r for r in self.rows}
        self.banks, self.models, self.states = {}, {}, {}
        self.bindings = read(CONFIG.with_suffix(".frozen.json"))["files"].copy()
        pins = [Path(__file__), OUT / "protocol.md", OUT / "queued_parent_identity.json", CONFIG.with_suffix(".frozen.json")]
        for version in range(1, 5):
            path = (PREFIX if version < 4 else PARENT) / f"update_transactions/b{version}.json"
            self.banks[version] = read(path)["publication"]
            mp = ROOT / self.cfg["reference_training_run"] / f"evidence_models/ordinary_M{version}.manifest.json"
            manifest = read(mp)
            assert sha(manifest["path"]) == manifest["pickle_sha256"]
            with Path(manifest["path"]).open("rb") as stream:
                self.models[version] = pickle.load(stream)
            assert not self.models[version].programs and not self.models[version].queries
            self.states[version] = manifest["state_sha256"]
            pins += [path, mp, Path(manifest["path"])]
        self.bindings.update({str(p.resolve()): sha(p) for p in pins})
        self.dependency = read(OUT / "queued_parent_identity.json")
        self.native, self.teachers, self.units = [], [], []
        self.teacher_attempts, self.current_batch, self.stop = 0, 0, False
        self.meter = WireClient(self.cfg["generation"])
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: setattr(self, "stop", True))

    def dependency_alive(self):
        proc = Path("/proc") / str(self.dependency["pid"])
        try:
            argv = [v.decode() for v in (proc / "cmdline").read_bytes().split(b"\0") if v]
            stat = (proc / "stat").read_text().rsplit(")", 1)[1].split()
        except (FileNotFoundError, ProcessLookupError):
            return False
        if not argv or stat[0] == "Z":
            return False
        assert argv == self.dependency["actual_argv"] and stat[19] == self.dependency["process_start_ticks"]
        return True

    def payload(self, row, arm):
        assert arm in (*REFERENCES, TREATMENT)
        version = row["batch"] - 1
        bank = self.banks[version] if arm in ("trace_procedures", TREATMENT) else []
        proposal = evidence_proposals(None if arm == "strong_empty" else self.models[version], row, self.labels)
        args = (row, self.labels, self.cfg["bundled_solver_system"], bank, proposal)
        messages, schema, delivery = complete_semantics(*args) if arm == TREATMENT else conditioned_messages(*args, unconditional=arm == "unconditional_layout")
        delivery["actually_delivered_projection_tokens"] = self.meter.token_count(text=render_library(delivery["actually_delivered_projection"]))
        return messages, schema, {
            "ordinary_model_state": None if arm == "strong_empty" else self.states[version],
            "proposals": proposal, "source_conditioned_delivery": delivery,
        }

    def audit_wire(self, units, name):
        for unit in units:
            row = self.by_id[unit["document_id"]]
            messages, schema, trace = self.payload(row, unit["condition"])
            raw = read(unit["raw_artifact"])
            assert len(raw["calls"]) == 1 and raw["response"] == unit["response"]
            wire = raw["calls"][0]["request"]
            expected = {key: self.cfg["generation"][key] for key in ("model", "temperature", "top_p", "top_k", "max_tokens", "seed")}
            expected.update(messages=messages, response_format={"type": "json_schema", "json_schema": {"name": "contractnli_callable_final", "strict": True, "schema": schema}})
            assert wire == expected
            close(trace, unit["actual_factual_trace"])
            assert unit["published_library"] == (self.banks[row["batch"] - 1] if unit["condition"] in ("trace_procedures", TREATMENT) else [])
            if unit["response"]["finish_reason"] == "stop":
                validate(json.loads(unit["response"]["content"]), schema)
            local_executor_trace(unit)
        RunStore.immutable_json(OUT / f"audits/{name}.json", {"at": now(), "logical_observations": len(units), "full_source_version_tool_delivery_layout_schema_decode_and_raw_replayed": True})

    def execute(self):
        self.check()
        RunStore.immutable_json(OUT / "declaration.json", {
            "at": now(), "run_id": self.run_id, "pid": os.getpid(), "argv": sys.argv,
            "config": self.cfg, "frozen_bindings": self.bindings, "dependency": self.dependency,
            "planned_new_native_teacher": [26, 0], "planned_historical_references": 104,
            "fixed_banks_development_delivery_intervention_not_online_learning_or_formal_test": True,
        })
        self.progress("waiting_for_exact_parent_exit_and_gpu_lease")
        while self.dependency_alive():
            self.check()
            time.sleep(3)
        done = read(PARENT / "completion.json")
        assert read(PARENT / "progress.json")["state"] == "completed"
        assert (done["new_native_calls"], done["new_teacher_calls"], done["total_this_learning_study_native_calls"], done["total_this_learning_study_teacher_calls"]) == (20, 1, 56, 7)
        assert read(PARENT / "audits/complete_before_new_later_grading.json")["logical_observations"] == 166
        refs, pins = [], [PARENT / "completion.json", PARENT / "audits/complete_before_new_later_grading.json"]
        for row in self.rows:
            stage = f"batch{row['batch']}_before" if row["batch"] < 5 else "later"
            source = PREFIX if row["batch"] < 5 else PARENT
            for arm in REFERENCES:
                suffix = "public" if arm == "trace_procedures" else "reference"
                path = source / stage / arm / f"{row['id']}.{suffix}.json"
                unit = {**read(path), "condition": arm, "existing_reference_not_new_generation": True}
                refs.append(unit)
                pins += [path, Path(unit["raw_artifact"])]
        assert len(refs) == 104
        self.bindings.update({str(p.resolve()): sha(p) for p in pins})
        self.check()
        RunStore.immutable_json(OUT / "terminal_parent_and_references_frozen.json", {"at": now(), "bindings": self.bindings, "reference_raw_ids": [u["response"]["raw_id"] for u in refs]})
        self.audit_wire(refs, "all104_historical_wires_before_generation")
        capacity = []
        for row in self.rows:
            messages, _, _ = self.payload(row, TREATMENT)
            tokens = self.meter.token_count(messages=messages)
            assert tokens + self.cfg["generation"]["max_tokens"] <= self.cfg["generation"]["context_tokens"], "Full original input cannot be clipped"
            capacity.append({"document_id": row["id"], "prompt_tokens": tokens})
        RunStore.immutable_json(OUT / "all26_unchanged_capacity_no_qualification_generation.json", {"at": now(), "requests": capacity, "generation_calls": 0})
        RunStore.immutable_json(OUT / "source_snapshot.json", {"files": {p: {"sha256": h, "utf8_text": Path(p).read_text()} for p, h in self.bindings.items() if Path(p).suffix in (".py", ".md", ".txt")}})
        with (ROOT / "artifacts/gpu_generation.lock").open("a+") as lease:
            while True:
                self.check()
                try:
                    fcntl.flock(lease.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    time.sleep(3)
            RunStore.immutable_json(OUT / "gpu_lease_acquired.json", {"at": now(), "exact_parent_exited_successfully": True})
            for row in self.rows:
                self.current_batch = row["batch"]
                messages, schema, trace = self.payload(row, TREATMENT)
                dest = OUT / f"answers/{row['id']}.final.native.json"
                response = self.call(dest, messages, schema, self.cfg["generation"]["max_tokens"], {"stage": "online_first_encounter" if row["batch"] < 5 else "later", "arm": TREATMENT, "document_id": row["id"], "call_role": "final"})
                unit = {"condition": TREATMENT, "document_id": row["id"], "response": response, "raw_artifact": str(dest), "actual_factual_trace": trace, "published_library": self.banks[row["batch"] - 1], "existing_reference_not_new_generation": False}
                RunStore.immutable_json(OUT / f"answers/{row['id']}.public.json", unit)
                self.units.append(unit)
            self.finish(refs)

    def finish(self, refs):
        self.check()
        assert len(self.native) == len(self.units) == 26 and not self.teachers
        all_units = refs + self.units
        assert len(all_units) == len({u["response"]["raw_id"] for u in all_units}) == 130
        self.audit_wire(all_units, "all130_actual_wires_before_original_grading")
        assert sha(ROOT / self.cfg["source_archive"]) == self.cfg["source_archive_sha256"]
        with zipfile.ZipFile(ROOT / self.cfg["source_archive"]) as archive:
            author = json.loads(archive.read("contract-nli/train.json"))
        assert author["labels"] == self.labels
        originals = {r["id"]: r for r in author["documents"]}
        groups = {a: [] for a in (*REFERENCES, TREATMENT)}
        for unit in all_units:
            row = self.by_id[unit["document_id"]]
            source = originals[row["id"]]
            assert {k: v for k, v in row.items() if k != "batch"} == {k: v for k, v in source.items() if k != "annotation_sets"}
            gold = source["annotation_sets"][0]["annotations"]
            feedback = original_feedback(unit["response"], row, gold, list(self.labels))
            close(original_score(unit["response"], row, gold, list(self.labels)), feedback)
            value = {**unit, **feedback}
            RunStore.immutable_json(OUT / f"scored/{unit['condition']}/{row['id']}.json", value)
            groups[unit["condition"]].append(value)
        results, contrasts = {}, {}
        rng = np.random.default_rng(20261016)
        for cohort, ids in {**{f"B{b}": [r["id"] for r in self.rows if r["batch"] == b] for b in (2, 3, 4)}, "online18": [r["id"] for r in self.rows if r["batch"] < 5], "exposed_development8": [r["id"] for r in self.rows if r["batch"] == 5]}.items():
            subset = {a: [u for u in us if u["document_id"] in ids] for a, us in groups.items()}
            results[cohort] = {a: points(us) for a, us in subset.items()}
            contrasts[cohort] = {a: {"paired": paired(subset[a], subset[TREATMENT])} for a in REFERENCES}
            if cohort not in ("online18", "exposed_development8"):
                continue
            for arm in REFERENCES:
                draws = {e: [] for e in ENDPOINTS}
                for _ in range(2000):
                    indices = rng.integers(0, len(ids), len(ids))
                    new, old = (points([subset[a][i] for i in indices]) for a in (TREATMENT, arm))
                    for e in ENDPOINTS:
                        draws[e].append(new[e] - old[e])
                contrasts[cohort][arm]["descriptive_source_intervals_not_independent_learning_repeats"] = {e: {"point": results[cohort][TREATMENT][e] - results[cohort][arm][e], "ci95": list(map(float, np.quantile(v, [0.025, 0.975])))} for e, v in draws.items()}
        RunStore.immutable_json(OUT / "completion.json", {"at": now(), "run_id": self.run_id, "new_native_calls": 26, "new_teacher_calls": 0, "logical_historical_references_not_new_spend": 104, "results": results, "contrasts": contrasts, "new_native_usage": {k: sum(n["response"][k] for n in self.native) for k in ("prompt_tokens", "completion_tokens")}, "referenced_native_usage_not_new_spend": {k: sum(u["response"][k] for u in refs) for k in ("prompt_tokens", "completion_tokens")}, "all26_saved_all130_replayed_before_original_grading": True, "not_token_matched_or_new_online_learning_or_formal_test": True, "no_bank_edit_winner_gate_retry_fallback_or_qualification_generations": True})
        RunStore.atomic_json(OUT / "progress.json", {"at": now(), "run_id": self.run_id, "state": "completed", "completed_native_calls": 26, "completed_teacher_calls": 0})


if __name__ == "__main__":
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="X does not have valid feature names")
        study = FullMasterDelivery()
        try:
            study.execute()
        except BaseException as exc:
            failure = {"at": now(), "run_id": study.run_id, "error": repr(exc), "completed_native_calls": len(study.native), "completed_teacher_calls": 0, "no_retry_fallback_or_parent_repair": True}
            RunStore.immutable_json(OUT / "failure.json", failure)
            RunStore.atomic_json(OUT / "progress.json", {"state": "stopped" if isinstance(exc, InterruptedError) else "failed", **failure})
            raise
