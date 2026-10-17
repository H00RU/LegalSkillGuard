"""Finite final-phase guidance ablation; keep actual native read actions fixed."""

# ruff: noqa: E402 -- Frozen run-local mechanism study, not a production layer.
from __future__ import annotations

import copy
import fcntl
import json
import os
import signal
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
PARENT = ROOT / "runs/legal_contractnli_source_read_execution_diagnostic_20261017_run01"
CONFIG = ROOT / "configs/contractnli_source_programs_completion.json"
sys.path.insert(0, str(ROOT))

from jsonschema import validate

from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.inference.native import WireClient
from legal_skill_guard.learning.audit import original_score
from legal_skill_guard.learning.experiment import Comparison, now, points, read, sha
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def transform(original):
    payload = copy.deepcopy(original)
    before = json.loads(original["messages"][1]["content"])
    body = copy.deepcopy(before)
    changes = []
    for skill in body["published_contextual_skills"]:
        guidance = skill["guidance"]
        assert set(guidance) == {"inspection", "past_demonstration_refs"}
        assert guidance["inspection"] and guidance["past_demonstration_refs"] == []
        changes.append({"id": skill["id"], "omitted_inspection_sha256": csha(guidance["inspection"])})
        guidance["inspection"] = ""
    restored = copy.deepcopy(body)
    for current, old in zip(restored["published_contextual_skills"], before["published_contextual_skills"], strict=True):
        current["guidance"]["inspection"] = old["guidance"]["inspection"]
    assert restored == before and len(changes) == 4
    assert not body["past_context_complete_demonstrations"]
    payload["messages"][1]["content"] = compact(body)
    assert all(payload["messages"][i] == original["messages"][i] for i in (0, 2, 3))
    payload["published_library"] = {k: body[k] for k in ("published_contextual_skills", "past_context_complete_demonstrations")}
    payload["actual_factual_trace"] = {
        "ordinary_model_state": original["actual_factual_trace"]["ordinary_model_state"],
        "actual_current_source_read": original["actual_factual_trace"]["actual_current_source_read"],
        "inherited_source_trace_not_current_delivery": csha(original["actual_factual_trace"]),
        "final_contextual_projection_sha256": csha(payload["published_library"]),
        "only_final_inspection_strings_emptied": changes,
        "all_actual_S1_actions_and_true_read_receipts_unchanged": True,
    }
    payload["arm"] = "skill_read_without_final_inspection"
    return payload


def prepare():
    assert not (OUT / "registration.json").exists()
    complete = read(PARENT / "completion.json")
    assert read(PARENT / "progress.json")["state"] == "completed"
    assert complete["actual_new_native_teacher_calls"] == [32, 0]
    cfg, registry = read(CONFIG), read(PARENT / "registration.json")
    bindings = dict(registry["files"])
    for path in PARENT.glob("native/*/*/*.json"):
        bindings[str(path)] = sha(path)
    for pattern in ("source_reads/*/*/*.json", "prospective_actual/*/*/*.json", "stage_results/*.json"):
        bindings.update({str(path): sha(path) for path in PARENT.glob(pattern)})
    entries, meter = [], WireClient(cfg["generation"])
    for item in complete["actual_final_answers"]:
        if item["arm"] != "skill_read":
            continue
        stage, doc = item["stage"], item["document_id"]
        old_path = PARENT / f"prospective_actual/{stage}/skill_read/{doc}.final.json"
        payload = transform(read(old_path))
        payload["parent_exact_final_payload"] = str(old_path)
        payload["parent_final_raw"] = item["path"]
        payload["prompt_tokens"] = meter.token_count(messages=payload["messages"])
        assert payload["prompt_tokens"] + cfg["generation"]["max_tokens"] <= cfg["generation"]["context_tokens"]
        path = OUT / f"prospective/{stage}/{doc}.json"
        RunStore.immutable_json(path, payload)
        entries.append({"stage": stage, "document_id": doc, "path": str(path)})
        bindings[str(path)] = sha(path)
    assert [(e["stage"], e["document_id"]) for e in entries] == [
        (stage, doc) for stage in ("B6", "B7") for doc in registry["source_selection"][stage]]
    for path in (Path(__file__).resolve(), OUT / "PROTOCOL.md", PARENT / "registration.json", PARENT / "completion.json"):
        bindings[str(path)] = sha(path)
    assert all(sha(path) == digest for path, digest in bindings.items())
    RunStore.immutable_json(OUT / "registration.json", {"at": now(), "run_id": OUT.name,
        "files": bindings, "ordered_requests": entries, "actual_parent_new_calls": [32, 0],
        "planned_new_native_teacher_calls": [8, 0], "shared_actual_parent_first_calls": 8,
        "not_new_online_learning_or_independent_repeat_or_TEST": True})
    print(compact({"prepared": len(entries), "frozen_bindings": len(bindings)}))


class Study(Comparison):
    def __init__(self):
        self.out, self.run_id = OUT, OUT.name
        self.cfg = {**read(CONFIG), "planned_new_native_calls": 8, "planned_new_teacher_calls": 0}
        self.bindings = read(OUT / "registration.json")["files"]
        self.native, self.teachers, self.teacher_attempts, self.current_batch, self.stop = [], [], 0, 6, False
        self.answers = []
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: setattr(self, "stop", True))

    def execute(self):
        self.check()
        backup = read(OUT / "prelaunch_backup.json")
        assert backup["all_members_verified"] and sha(backup["archive"]) == backup["archive_sha256"]
        self.progress("acquiring_shared_GPU_lease")
        with (ROOT / "artifacts/gpu_generation.lock").open("a+") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            for entry in read(OUT / "registration.json")["ordered_requests"]:
                p = read(entry["path"])
                self.current_batch = int(p["stage"][1:])
                dest = OUT / f"native/{p['stage']}/{p['document_id']}.final.native.json"
                result = self.call(dest, p["messages"], p["schema"], self.cfg["generation"]["max_tokens"], {
                    "stage": p["stage"], "arm": p["arm"], "document_id": p["document_id"],
                    "call_role": "final", "published_library": p["published_library"],
                    "actual_factual_trace": p["actual_factual_trace"], "payload": entry["path"]})
                assert result["finish_reason"] == "stop", "Incomplete answer retained; no retry"
                validate(json.loads(result["content"]), p["schema"])
                self.answers.append({**entry, "raw_path": str(dest)})
        assert len(self.answers) == len(self.native) == 8
        for entry in self.answers:
            p, raw = read(entry["path"]), read(entry["raw_path"])
            assert len(raw["calls"]) == 1 and raw["transport_error"] is None
            wire = raw["calls"][0]["request"]
            assert wire["messages"] == p["messages"]
            assert wire["response_format"]["json_schema"]["schema"] == p["schema"]
        self.check()
        assert sha(ROOT / self.cfg["source_archive"]) == self.cfg["source_archive_sha256"]
        with zipfile.ZipFile(ROOT / self.cfg["source_archive"]) as archive:
            author = json.loads(archive.read("contract-nli/train.json"))
        rows = {r["id"]: r for r in author["documents"]}
        grouped = {}
        for entry in self.answers:
            row, raw = rows[entry["document_id"]], read(entry["raw_path"])
            value = original_score(raw["response"], row, row["annotation_sets"][0]["annotations"], list(author["labels"]))
            assert value["public_valid"]
            grouped.setdefault(entry["stage"], []).append({"document_id": row["id"], "response": raw["response"], **value})
        complete = {"at": now(), "run_id": self.run_id, "actual_new_native_teacher_calls": [8, 0],
            "actual_new_answers": self.answers, "all8_saved_and_wires_checked_before_TRAIN_grading": True,
            "stage_metrics": {stage: points(units) for stage, units in grouped.items()},
            "pooled_metrics": points([u for units in grouped.values() for u in units]),
            "new_native_usage": {k: sum(raw["response"][k] for raw in self.native) for k in ("prompt_tokens", "completion_tokens")},
            "shared_parent_source_reads8_not_new_or_free": str(PARENT / "completion.json"),
            "not_learning_repeat_or_superiority_claim_or_official_TEST": True}
        RunStore.immutable_json(OUT / "completion.json", complete)
        RunStore.atomic_json(OUT / "progress.json", {"state": "completed", **complete})


if __name__ == "__main__":
    command = sys.argv[1]
    if command == "prepare":
        prepare()
    elif command == "launch":
        assert not (OUT / "launch.json").exists() and (OUT / "prelaunch_backup.json").exists()
        argv = [str(ROOT / ".venv/bin/python"), str(Path(__file__).resolve()), "worker"]
        with (OUT / "worker.log").open("xb") as log:
            child = subprocess.Popen(argv, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log,
                stderr=subprocess.STDOUT, start_new_session=True, env={**os.environ, "PYTHONUNBUFFERED": "1"})
        RunStore.immutable_json(OUT / "launch.json", {"at": now(), "pid": child.pid, "actual_argv": argv,
            "background_independent_of_conversation": True})
        print(compact({"run_id": OUT.name, "pid": child.pid}))
    elif command == "worker":
        study = Study()
        try:
            study.execute()
        except BaseException as exc:
            value = {"at": now(), "run_id": OUT.name, "error": repr(exc),
                "actual_new_native_teacher_calls": [len(study.native), 0], "no_retry_fallback_or_repair": True}
            RunStore.immutable_json(OUT / "failure.json", value)
            RunStore.atomic_json(OUT / "progress.json", {"state": "stopped" if isinstance(exc, InterruptedError) else "failed", **value})
            raise
    else:
        raise ValueError("Explicit prepare, launch or worker required")
