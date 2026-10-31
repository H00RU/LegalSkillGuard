"""Finite fixed-M4 mechanism ablation; not a new production inference layer."""

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
from legal_skill_guard.learning.conditioned import conditioned_messages
from legal_skill_guard.learning.evidence_programs import evidence_proposals
from legal_skill_guard.learning.experiment import ENDPOINTS, Comparison, now, points, read, sha
from legal_skill_guard.learning.procedures import local_executor_trace
from legal_skill_guard.learning.publication import paired
from legal_skill_guard.task import original_feedback, render_library
from legal_skill_guard.utils.hashing import canonical_json_sha256

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
PARENT = ROOT / "runs/legal_contractnli_source_conditioned_completion_20261016_run01"
CONFIG = ROOT / "configs/contractnli_source_conditioned_completion.json"
PROTOCOL = OUT / "protocol.md"
REFERENCE_ARMS = {"main_reporting": "trace_procedures", "layout_reporting": "unconditional_layout"}
NEW_ARMS = (
    "main_no_reporting",
    "layout_no_reporting",
    "learned_operations_only_no_reporting",
)
CONTRASTS = (
    ("main_no_reporting", "main_reporting"),
    ("layout_no_reporting", "layout_reporting"),
    ("main_no_reporting", "layout_no_reporting"),
    ("main_no_reporting", "learned_operations_only_no_reporting"),
)


def without_report_field(schema):
    result = copy.deepcopy(schema)
    if isinstance(result, dict):
        if "properties" in result and "used_skill_ids" in result["properties"]:
            del result["properties"]["used_skill_ids"]
            result["required"].remove("used_skill_ids")
        return {k: without_report_field(v) for k, v in result.items()}
    if isinstance(result, list):
        return [without_report_field(v) for v in result]
    return result


def no_reporting(messages, schema):
    """One output-contract intervention, retaining reason and all decision rules."""
    result = copy.deepcopy(messages)
    replacements = (
        ("then report supplied skill IDs actually used.", ""),
        (
            "For each emit choice, spans, reason, used_skill_ids in that order.",
            "For each emit choice, spans, reason in that order.",
        ),
    )
    for old, new in replacements:
        assert result[0]["content"].count(old) == 1, "Unexpected frozen reporting contract"
        result[0]["content"] = result[0]["content"].replace(old, new, 1)
    body = json.loads(result[1]["content"])
    common = body["output_contract"]["common_schema_for_each_hypothesis"]
    body["output_contract"]["common_schema_for_each_hypothesis"] = without_report_field(common)
    result[1]["content"] = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    native = without_report_field(schema)
    assert "used_skill_ids" not in json.dumps(body["output_contract"])
    assert "used_skill_ids" not in json.dumps(native)
    return result, native


class ExecutionContractAblation(Comparison):
    def __init__(self):
        assert not (OUT / "declaration.json").exists(), "Never restart an existing Run ID"
        self.cfg = {**read(CONFIG), "planned_new_native_calls": 24, "planned_new_teacher_calls": 0}
        self.run_id, self.out = OUT.name, OUT
        packet = read(ROOT / self.cfg["input_packet"])
        self.labels, self.training = packet["public_hypotheses"], packet["training"]
        self.future = packet["later_inputs_no_annotation_sets"]
        assert [r["id"] for r in self.future] == self.cfg["expected_later_ids"]
        assert len(self.future) == 8 and all("annotation_sets" not in r for r in self.future)
        self.bank = read(PARENT / "memory_frozen_before_later.json")["main_library"]
        assert self.bank == read(PARENT / "update_transactions/b4.json")["publication"]
        manifest_path = (
            ROOT / self.cfg["reference_training_run"] / "evidence_models/ordinary_M4.manifest.json"
        )
        self.manifest = read(manifest_path)
        assert sha(self.manifest["path"]) == self.manifest["pickle_sha256"]
        with Path(self.manifest["path"]).open("rb") as stream:
            self.model = pickle.load(stream)
        assert not self.model.programs and not self.model.queries
        self.state = self.manifest["state_sha256"]
        self.native, self.teachers, self.units = [], [], []
        self.teacher_attempts, self.current_batch, self.stop = 0, 4, False
        self.meter = WireClient(self.cfg["generation"])
        self.dependency = read(OUT / "queued_parent_identity.json")
        self.bindings = read(PARENT / "declaration.json")["frozen_bindings"].copy()
        pins = [
            Path(__file__), PROTOCOL, CONFIG, OUT / "queued_parent_identity.json",
            PARENT / "memory_frozen_before_later.json", PARENT / "update_transactions/b4.json",
            manifest_path, Path(self.manifest["path"]),
        ]
        prepared = OUT / "pre_generation_transform_identity.json"
        if prepared.exists():
            pins.append(prepared)
        self.bindings.update({str(p.resolve()): sha(p) for p in pins})
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: setattr(self, "stop", True))

    def dependency_alive(self):
        proc = Path("/proc") / str(self.dependency["pid"])
        try:
            args = [v.decode() for v in (proc / "cmdline").read_bytes().split(b"\0") if v]
            stat = (proc / "stat").read_text().rsplit(")", 1)[1].split()
        except (FileNotFoundError, ProcessLookupError):
            return False
        if args:
            assert args == self.dependency["actual_argv"], "Dependency PID was replaced"
            assert stat[19] == self.dependency["process_start_ticks"]
        return bool(args) and stat[0] != "Z"

    def payload(self, row, arm):
        layout = arm in ("layout_reporting", "layout_no_reporting")
        bank = [] if layout else self.bank
        proposal = evidence_proposals(self.model, row, self.labels)
        messages, schema, provenance = conditioned_messages(
            row, self.labels, self.cfg["bundled_solver_system"], bank, proposal,
            unconditional=layout,
        )
        if arm in NEW_ARMS:
            messages, schema = no_reporting(messages, schema)
        if arm == "learned_operations_only_no_reporting":
            rendered = render_library(provenance["actually_delivered_projection"])
            old = "\nReusable skills: " + rendered
            assert messages[0]["content"].endswith(old)
            messages[0]["content"] = messages[0]["content"][:-len(old)] + "\nReusable skills: []"
            body = json.loads(messages[1]["content"])
            for hypothesis in body["hypotheses"].values():
                hypothesis["applicable_published_skill_ids"] = []
            messages[1]["content"] = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
        assert arm in (*REFERENCE_ARMS, *NEW_ARMS)
        return messages, schema, {
            "ordinary_model_state": self.state,
            "proposals": proposal,
            "mechanical_parent_eligibility_and_operations": provenance,
            "semantic_guidance_delivered": not layout and arm != NEW_ARMS[2],
            "skill_use_output_required": arm in REFERENCE_ARMS,
            "master_library_sha256": canonical_json_sha256(self.bank),
        }

    def audit_wire(self, units, name):
        rows = {r["id"]: r for r in self.future}
        for unit in units:
            messages, schema, trace = self.payload(rows[unit["document_id"]], unit["condition"])
            raw = read(unit["raw_artifact"])
            assert len(raw["calls"]) == 1 and raw["response"] == unit["response"]
            wire = raw["calls"][0]["request"]
            assert wire["messages"] == messages
            assert wire["response_format"]["json_schema"]["schema"] == schema
            for key in ("model", "temperature", "top_p", "top_k", "max_tokens", "seed"):
                assert wire[key] == self.cfg["generation"][key]
            if unit["condition"] in NEW_ARMS:
                close(trace, unit["actual_input_trace"])
            else:
                original = unit["actual_factual_trace"]
                close(trace["proposals"], original["proposals"])
                close(trace["mechanical_parent_eligibility_and_operations"], original["source_conditioned_delivery"])
                assert original["ordinary_model_state"] == self.state
                assert unit["published_library"] == ([] if unit["condition"] == "layout_reporting" else self.bank)
            if unit["response"]["finish_reason"] == "stop":
                validate(json.loads(unit["response"]["content"]), schema)
            local_executor_trace(unit)
        RunStore.immutable_json(OUT / "audits" / f"{name}.json", {
            "at": now(), "observations": len(units),
            "full_source_fixed_M4_model_candidates_eligibility_operations_contract_native_wires_replayed": True,
            "no_new_grading_access_or_native_answer_repair": True,
        })

    def answer(self, row, arm):
        messages, schema, trace = self.payload(row, arm)
        dest = OUT / "later" / arm / f"{row['id']}.final.native.json"
        response = self.call(dest, messages, schema, self.cfg["generation"]["max_tokens"], {
            "stage": "later", "arm": arm, "document_id": row["id"], "call_role": "final",
        })
        unit = {
            "condition": arm, "document_id": row["id"], "response": response,
            "raw_artifact": str(dest), "actual_input_trace": trace,
            "existing_reference_not_new_generation": False,
        }
        RunStore.immutable_json(dest.with_name(f"{row['id']}.public.json"), unit)
        self.units.append(unit)

    def execute(self):
        self.check()
        RunStore.immutable_json(OUT / "declaration.json", {
            "at": now(), "run_id": self.run_id, "pid": os.getpid(), "argv": sys.argv,
            "config": self.cfg, "frozen_bindings": self.bindings, "dependency": self.dependency,
            "new_native_calls_planned": 24, "new_teacher_calls_planned": 0,
            "explicit_old_references_planned": 16,
            "fixed_bank_exposed8_development_not_new_learning_or_formal_test": True,
        })
        self.progress("waiting_for_exact_parent_exit_and_gpu_lease")
        while self.dependency_alive():
            self.check()
            time.sleep(3)
        done = read(PARENT / "completion.json")
        status = read(PARENT / "progress.json")
        assert status["state"] == "completed", "Parent did not fully complete; cancel without generation"
        assert (done["total_this_learning_study_native_calls"], done["total_this_learning_study_teacher_calls"]) == (90, 5)
        assert (done["all_logical_observations"], done["all_distinct_native_responses"]) == (166, 148)
        audit = read(PARENT / "audits/complete_before_new_later_grading.json")
        assert audit["logical_observations"] == 166
        refs = []
        pins = [PARENT / "completion.json", PARENT / "audits/complete_before_new_later_grading.json"]
        for arm, parent_arm in REFERENCE_ARMS.items():
            for row in self.future:
                path = PARENT / "later" / parent_arm / f"{row['id']}.public.json"
                unit = {**read(path), "condition": arm, "existing_reference_not_new_generation": True}
                refs.append(unit)
                pins += [path, Path(unit["raw_artifact"])]
        self.bindings.update({str(p.resolve()): sha(p) for p in pins})
        RunStore.immutable_json(OUT / "parent_terminal_and_all_reference_bindings.json", {
            "at": now(), "parent_state": status, "all_bindings": self.bindings,
            "references": [{"condition": u["condition"], "document_id": u["document_id"], "raw_id": u["response"]["raw_id"]} for u in refs],
        })
        self.audit_wire(refs, "all16_exact_parent_requests_before_new_generation")
        RunStore.immutable_json(OUT / "source_snapshot.json", {"files": {
            p: {"sha256": h, "utf8_text": Path(p).read_text()}
            for p, h in self.bindings.items() if Path(p).suffix in (".py", ".md", ".txt")
        }})
        with (ROOT / "artifacts/gpu_generation.lock").open("a+") as lease:
            while True:
                self.check()
                try:
                    fcntl.flock(lease.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    time.sleep(3)
            RunStore.immutable_json(OUT / "gpu_lease_acquired.json", {"at": now(), "parent_completed_and_exact_process_exited": True})
            for index, row in enumerate(self.future):
                offset = index % len(NEW_ARMS)
                for arm in NEW_ARMS[offset:] + NEW_ARMS[:offset]:
                    self.answer(row, arm)
            self.finish_ablation(refs)

    def finish_ablation(self, refs):
        self.check()
        assert len(self.native) == len(self.units) == 24 and not self.teachers
        all_units = refs + self.units
        assert len(all_units) == len({u["response"]["raw_id"] for u in all_units}) == 40
        self.audit_wire(all_units, "all40_wires_before_original_grading")
        assert sha(ROOT / self.cfg["source_archive"]) == self.cfg["source_archive_sha256"]
        with zipfile.ZipFile(ROOT / self.cfg["source_archive"]) as archive:
            author = json.loads(archive.read("contract-nli/train.json"))
        assert author["labels"] == self.labels
        originals = {r["id"]: r for r in author["documents"]}
        grading = read(ROOT / self.cfg["grading_only"])["annotations"]
        groups = {a: [] for a in (*REFERENCE_ARMS, *NEW_ARMS)}
        for unit in all_units:
            source = originals[unit["document_id"]]
            row = next(r for r in self.future if r["id"] == source["id"])
            assert (row["text"], row["spans"]) == (source["text"], source["spans"])
            gold = source["annotation_sets"][0]["annotations"]
            assert grading[str(row["id"])] == gold
            feedback = original_feedback(unit["response"], row, gold, list(self.labels))
            close(original_score(unit["response"], row, gold, list(self.labels)), feedback)
            value = {**unit, **feedback}
            groups[unit["condition"]].append(value)
            RunStore.immutable_json(OUT / "scored" / unit["condition"] / f"{row['id']}.json", value)
        metrics = {arm: points(units) for arm, units in groups.items()}
        rng, contrasts = np.random.default_rng(self.cfg["bootstrap_seed"]), {}
        for treatment, control in CONTRASTS:
            draws = {key: [] for key in ENDPOINTS}
            for _ in range(self.cfg["bootstrap_draws"]):
                indices = rng.integers(0, 8, 8)
                a, b = (points([groups[arm][i] for i in indices]) for arm in (treatment, control))
                for key in ENDPOINTS:
                    draws[key].append(a[key] - b[key])
            contrasts[treatment + "_minus_" + control] = {
                "paired": paired(groups[control], groups[treatment]),
                "descriptive_source_intervals_not_independent_learning_repeats": {
                    key: {"point": metrics[treatment][key] - metrics[control][key],
                          "ci95": list(map(float, np.quantile(values, [0.025, 0.975])))}
                    for key, values in draws.items()
                },
                "per_source_net": [{
                    "document_id": a["document_id"],
                    "label_correct": sum(q["label_correct"] for q in a["queries"]) - sum(q["label_correct"] for q in b["queries"]),
                    "joint_exact": sum(q["joint_exact"] for q in a["queries"]) - sum(q["joint_exact"] for q in b["queries"]),
                } for a, b in zip(groups[treatment], groups[control], strict=True)],
            }
        done = {
            "at": now(), "run_id": self.run_id, "new_native_calls": 24, "new_teacher_calls": 0,
            "explicit_old_references_not_new_generations": 16, "metrics": metrics,
            "contrasts": contrasts,
            "new_native_usage": {k: sum(n["response"][k] for n in self.native) for k in ("prompt_tokens", "completion_tokens")},
            "referenced_native_usage_not_new_spend": {k: sum(u["response"][k] for u in refs) for k in ("prompt_tokens", "completion_tokens")},
            "all24_saved_all40_replayed_before_original_gold_grading": True,
            "no_bank_edit_automatic_winner_publication_or_qualification_generations": True,
            "not_new_online_learning_independent_repeat_or_official_test": True,
        }
        RunStore.immutable_json(OUT / "completion.json", done)
        RunStore.atomic_json(OUT / "progress.json", {"at": now(), "run_id": self.run_id, "state": "completed", "completed_native_calls": 24, "completed_teacher_calls": 0})


if __name__ == "__main__":
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="X does not have valid feature names, but LGBMClassifier was fitted with feature names")
        study = ExecutionContractAblation()
        try:
            study.execute()
        except BaseException as exc:
            failure = {"at": now(), "run_id": study.run_id, "error": repr(exc), "completed_native_calls": len(study.native), "completed_teacher_calls": 0, "no_retry_fallback_or_parent_repair": True}
            RunStore.immutable_json(OUT / "failure.json", failure)
            RunStore.atomic_json(OUT / "progress.json", {"state": "stopped" if isinstance(exc, InterruptedError) else "failed", **failure})
            raise
