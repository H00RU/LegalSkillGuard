"""Correct a duplicated native ABI definition; preserve all task data and costs."""

# ruff: noqa: E402 -- Frozen run-local driver using only old pure schema helpers.
from __future__ import annotations

import copy
import fcntl
import importlib.util
import json
import os
import signal
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from jsonschema import validate

from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.inference.native import WireClient
from legal_skill_guard.learning.audit import original_score
from legal_skill_guard.learning.experiment import Comparison, now, points, read, sha
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha

STOPPED = ROOT / "runs/legal_contractnli_support_refute_native_contract_diagnostic_20261017_run01"
spec = importlib.util.spec_from_file_location("frozen_consistency_schema_helpers", STOPPED / "experiment.py")
BASE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(BASE)
PARENT, CONFIG, DOCS, ARMS = BASE.PARENT, BASE.CONFIG, BASE.DOCS, BASE.ARMS
BACKUP = ROOT / "artifacts/support_refute_stopped8_all406_before_corrected_source_backup_20261017.json"
AUDIT = STOPPED / "monitoring/terminal8_all_actual_wire_schema_valid_but_conflicting_user_contract_not_quality_evidence.json"


def output_fields(schema):
    fields = list(next(iter(schema["properties"].values()))["anyOf"][0]["properties"])
    assert fields == ["hypothesis_supported", "hypothesis_refuted", "choice", "spans", "reason", "used_skill_ids"]
    for question in schema["properties"].values():
        for branch in question["anyOf"]:
            assert list(branch["properties"]) == branch["required"] == fields
    return fields


class Probe(Comparison):
    def __init__(self, preparing=False):
        self.cfg = {**read(CONFIG), "planned_new_native_calls": 12, "planned_new_teacher_calls": 0}
        self.bindings = read(AUDIT)["bindings"] if preparing else read(OUT / "registration.json")["files"]
        self.out, self.run_id = OUT, OUT.name
        self.native, self.teachers, self.teacher_attempts, self.current_batch, self.stop = [], [], 0, 4, False
        self.meter = WireClient(self.cfg["generation"])
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: setattr(self, "stop", True))

    def compile(self, arm, doc):
        path = PARENT / f"native/B4_first_encounter/{arm}/{doc}.native.json"
        old = read(path)
        assert old["arm"] == arm and old["document_id"] == doc
        request = old["calls"][0]["request"]
        messages = copy.deepcopy(request["messages"])
        assert len(messages) == 2 and messages[0]["content"].count(BASE.ORDER_OLD) == 1
        schema = BASE.consistency_schema(request["response_format"]["json_schema"]["schema"])
        fields = output_fields(schema)
        assert BASE.ORDER_NEW == "For each emit " + ", ".join(fields[:-1]) + ", " + fields[-1] + " in that order."
        messages[0]["content"] = messages[0]["content"].replace(BASE.ORDER_OLD, BASE.ORDER_NEW) + BASE.NOTICE
        original = json.loads(messages[1]["content"])
        old_fields = original["output_contract"]["fields_in_order"]
        assert old_fields == fields[2:]
        body = copy.deepcopy(original)
        body["output_contract"]["fields_in_order"] = fields
        restored = copy.deepcopy(body)
        restored["output_contract"]["fields_in_order"] = old_fields
        assert restored == original
        assert json.dumps(restored, ensure_ascii=False, separators=(",", ":")) == messages[1]["content"]
        messages[1]["content"] = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
        assert body["output_contract"]["fields_in_order"] == output_fields(schema)
        tokens = self.meter.token_count(messages=messages)
        assert tokens + self.cfg["generation"]["max_tokens"] <= self.cfg["generation"]["context_tokens"]
        return {"messages": messages, "schema": schema, "trace": old["actual_factual_trace"],
            "published_library": old["published_library"], "original_request_artifact": str(path),
            "stage": BASE.STAGE, "arm": arm, "document_id": doc, "prompt_tokens": tokens,
            "messages_sha256": csha(messages), "schema_sha256": csha(schema),
            "only_user_change_is_schema_derived_output_order_metadata": True,
            "original_task_data_and_user_bytes_roundtrip_after_restoring_old_order": True}

    def execute(self):
        self.check()
        with (ROOT / "artifacts/gpu_generation.lock").open("a+") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            for entry in read(OUT / "registration.json")["ordered_requests"]:
                payload = read(Path(entry["path"]))
                assert self.compile(entry["arm"], entry["document_id"]) == payload
                self.call(OUT / f"native/{entry['arm']}/{entry['document_id']}.native.json",
                    payload["messages"], payload["schema"], self.cfg["generation"]["max_tokens"], {
                        "stage": BASE.STAGE, "arm": entry["arm"], "document_id": entry["document_id"],
                        "call_role": "final", "published_library": payload["published_library"],
                        "actual_factual_trace": payload["trace"],
                        "original_request_artifact": payload["original_request_artifact"]})
                raw = self.native[-1]
                if raw["response"]["finish_reason"] != "stop":
                    raise InterruptedError("Incomplete output retained; no retry or repair")
                validate(json.loads(raw["response"]["content"]), payload["schema"])
            self.finish()

    def finish(self):
        assert len(self.native) == 12 and not self.teachers
        assert sha(ROOT / self.cfg["source_archive"]) == self.cfg["source_archive_sha256"]
        with zipfile.ZipFile(ROOT / self.cfg["source_archive"]) as archive:
            author = json.loads(archive.read("contract-nli/train.json"))
        rows = {r["id"]: r for r in author["documents"]}
        groups, hashes = {}, {}
        for version in ("old_contract", "support_refute_contract"):
            for arm in ARMS:
                units = []
                for doc in DOCS:
                    path = PARENT / f"native/B4_first_encounter/{arm}/{doc}.native.json" if version == "old_contract" else OUT / f"native/{arm}/{doc}.native.json"
                    raw, row = read(path), rows[doc]
                    scored = original_score(raw["response"], row, row["annotation_sets"][0]["annotations"], list(author["labels"]))
                    if scored["public_valid"]:
                        validate(scored["parsed"], raw["calls"][0]["request"]["response_format"]["json_schema"]["schema"])
                    units.append({"document_id": doc, "response": raw["response"], **scored})
                    hashes[str(path)] = sha(path)
                groups[version + "_" + arm] = units
        contrasts = {}
        for version in ("old_contract", "support_refute_contract"):
            ordinary, skill = (groups[version + "_" + arm] for arm in ARMS)
            counts = {k: 0 for k in ("label_fixes", "label_damage", "joint_fixes", "joint_damage", "true_gained", "true_lost")}
            for a, b in zip(ordinary, skill, strict=True):
                for x, y in zip(a["queries"], b["queries"], strict=True):
                    assert x["hypothesis_id"] == y["hypothesis_id"] and x["gold"] == y["gold"]
                    for key, field in (("label", "label_correct"), ("joint", "joint_exact")):
                        counts[key + "_fixes"] += int(not x[field] and y[field])
                        counts[key + "_damage"] += int(x[field] and not y[field])
                    gold = set(x["gold"]["spans"])
                    aa, bb = set(x["prediction"]["spans"]), set(y["prediction"]["spans"])
                    counts["true_gained"] += len((bb - aa) & gold)
                    counts["true_lost"] += len((aa - bb) & gold)
            contrasts[version + "_skill_minus_ordinary"] = counts
        self.check()
        result = {"at": now(), "run_id": self.run_id, "new_native_teacher_calls": [12, 0],
            "old_reference_answers_not_independent_repeats": 12,
            "all12_saved_before_new_quality_scoring": True,
            "metrics": {name: points(units) for name, units in groups.items()},
            "same_contract_skill_contrasts": contrasts, "all_units": groups,
            "new_native_usage": {k: sum(v["response"][k] for v in self.native) for k in ("prompt_tokens", "completion_tokens")},
            "stopped8_prototype_usage_not_hidden_or_free": read(AUDIT)["new_native_usage"],
            "stopped8_answers_never_used_as_new_reference_or_scored": True,
            "unchanged_original_choice_scoring_no_posthoc_mapping_or_repair": True,
            "shared_upstream_learning_costs_not_free": str(PARENT / "completion.json"),
            "not_formal_TEST_independent_learning_or_method_win": True, "all_output_sha256": hashes}
        RunStore.immutable_json(OUT / "completion.json", result)
        RunStore.atomic_json(OUT / "progress.json", {"at": now(), "run_id": self.run_id,
            "state": "completed", "completed_native_calls": 12, "completed_teacher_calls": 0})
        print(json.dumps({"metrics": result["metrics"], "contrasts": contrasts}, ensure_ascii=False))


def prepare():
    assert not (OUT / "registration.json").exists()
    assert read(STOPPED / "progress.json")["state"] == "stopped"
    assert not Path("/proc", str(read(STOPPED / "launch.json")["pid"])).exists()
    receipt = read(BACKUP)
    assert receipt["stopped_new_native_teacher_calls"] == [8, 0]
    assert sha(receipt["archive"]) == receipt["archive_sha256"]
    probe = Probe(preparing=True)
    probe.check()
    entries, systems = [], set()
    for i, doc in enumerate(DOCS):
        for arm in (ARMS if i % 2 == 0 else ARMS[::-1]):
            payload = probe.compile(arm, doc)
            systems.add(payload["messages"][0]["content"])
            path = OUT / f"prospective/{arm}/{doc}.json"
            RunStore.immutable_json(path, payload)
            entries.append({"path": str(path), "sha256": sha(path), "arm": arm, "document_id": doc,
                "prompt_tokens": payload["prompt_tokens"], "messages_sha256": payload["messages_sha256"],
                "schema_sha256": payload["schema_sha256"]})
    assert len(systems) == 1
    checks = {arm: BASE.schema_check(read(OUT / f"prospective/{arm}/{DOCS[0]}.json")["schema"]) for arm in ARMS}
    paths = [Path(__file__), OUT / "PROTOCOL.md", BACKUP, AUDIT, STOPPED / "registration.json",
        STOPPED / "failure.json", STOPPED / "progress.json", STOPPED / "operator_safe_stop_output_contract_inconsistency.json",
        *[Path(r["path"]) for r in entries]]
    RunStore.immutable_json(OUT / "registration.json", {"at": now(), "files": {
        **probe.bindings, **{str(p): sha(p) for p in paths}}, "ordered_requests": entries,
        "all12_full_inputs_fit_and_original_task_data_roundtrip_before_any_generation": True,
        "output_order_consistent_in_user_system_and_all_actual_native_schema_branches": True,
        "new_native_teacher_calls": [12, 0], "synthetic_schema_checks": checks,
        "stopped8_usage_inherited_as_cost_not_answers": read(AUDIT)["new_native_usage"],
        "known_development_not_independent_or_TEST": True})
    print(json.dumps({"prepared_new_calls": [12, 0], "requests": entries, "schema_checks": checks}))


if __name__ == "__main__":
    command = sys.argv[1]
    if command == "prepare":
        prepare()
    elif command == "launch":
        assert (OUT / "registration.json").exists() and not (OUT / "launch.json").exists()
        argv = [str(ROOT / ".venv/bin/python"), str(Path(__file__).resolve()), "worker"]
        with (OUT / "worker.log").open("xb") as log:
            child = subprocess.Popen(argv, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log,
                stderr=subprocess.STDOUT, start_new_session=True, env={**os.environ, "PYTHONUNBUFFERED": "1"})
        RunStore.immutable_json(OUT / "launch.json", {"at": now(), "pid": child.pid, "actual_argv": argv,
            "background_independent_of_conversation": True})
        print(json.dumps({"run_id": OUT.name, "pid": child.pid}))
    elif command == "worker":
        probe = Probe()
        try:
            probe.execute()
        except BaseException as exc:
            value = {"at": now(), "run_id": OUT.name, "error": repr(exc),
                "completed_native_calls": len(probe.native), "completed_teacher_calls": 0,
                "no_retry_fallback_answer_repair_or_bank_selection": True}
            RunStore.immutable_json(OUT / "failure.json", value)
            RunStore.atomic_json(OUT / "progress.json", {"state": "stopped" if isinstance(exc, InterruptedError) else "failed", **value})
            raise
    else:
        raise ValueError("Explicit prepare, launch or worker required")
