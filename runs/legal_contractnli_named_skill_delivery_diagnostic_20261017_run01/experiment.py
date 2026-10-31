"""One-factor, six-contract fixed-M1 skill serialization diagnosis."""

# ruff: noqa: E402 -- Run-local entry point resolves the shared project root.

from __future__ import annotations

import copy
import fcntl
import json
import os
import signal
import subprocess
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from jsonschema import validate

from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.learning.audit import close, original_score
from legal_skill_guard.learning.experiment import Comparison, now, points, read, sha
from legal_skill_guard.learning.skill_tables import (
    COLUMNS,
    TABLE_NOTICE,
    decode_skill_projection,
    table_skill_messages,
)
from legal_skill_guard.task import marked_text

SOURCE = ROOT / "runs/legal_contractnli_witness_table_online_learning_20261016_run01"
CONFIG = ROOT / "configs/contractnli_witness_table.json"
ARMS = ("ordinary_memory", "skill_memory")


def named_request(original):
    result = copy.deepcopy(original)
    system = result["messages"][0]["content"]
    assert system.endswith(TABLE_NOTICE) and system.count(TABLE_NOTICE) == 1
    body = json.loads(result["messages"][1]["content"])
    assert body.pop("skill_table_columns") == list(COLUMNS)
    projection = decode_skill_projection({
        "columns": list(COLUMNS),
        "by_hypothesis": {h: q["applicable_published_skills"] for h, q in body["hypotheses"].items()},
    })
    for h, records in projection.items():
        body["hypotheses"][h]["applicable_published_skills"] = records
    result["messages"][0]["content"] = system[:-len(TABLE_NOTICE)]
    result["messages"][1]["content"] = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    roundtrip, _ = table_skill_messages(result["messages"], {"actual_task_local_projection": projection})
    assert roundtrip == original["messages"]
    assert {k: v for k, v in result.items() if k != "messages"} == {k: v for k, v in original.items() if k != "messages"}
    return result


def process_identity(pid):
    proc = Path("/proc") / str(pid)
    if not proc.exists():
        return None
    try:
        fields = (proc / "stat").read_text().rsplit(")", 1)[1].split()
        return {"pid": pid, "state": fields[0], "start_ticks": fields[19],
                "argv": [x.decode() for x in (proc / "cmdline").read_bytes().split(b"\0") if x]}
    except FileNotFoundError:
        return None


def prepare():
    assert not (OUT / "registration.json").exists()
    cfg, frozen = read(CONFIG), read(CONFIG.with_suffix(".frozen.json"))
    assert frozen["config_sha256"] == sha(CONFIG)
    assert all(sha(p) == digest for p, digest in frozen["files"].items())
    audit_path = SOURCE / "monitoring/complete_B2_independent_original_author_and_matched_error_audit.json"
    audit = read(audit_path)
    assert all(sha(p) == digest for p, digest in audit["audited_file_sha256"].items())
    ids = cfg["training_ids"][6:12]
    assert ids == [262, 588, 538, 177, 136, 187]
    parent = read(SOURCE / "update_transactions/b1.json")["publication"]
    assert len(parent) == 6
    files = {**frozen["files"], str(CONFIG): sha(CONFIG),
             str(CONFIG.with_suffix(".frozen.json")): sha(CONFIG.with_suffix(".frozen.json")),
             str(Path(__file__)): sha(__file__), str(OUT / "PROTOCOL.md"): sha(OUT / "PROTOCOL.md")}
    for p in (audit_path, SOURCE / "launch.json", SOURCE / "operator_stop_request.json", SOURCE / "update_transactions/b1.json"):
        files[str(p)] = sha(p)
    for d in ids:
        for arm in ARMS:
            public = SOURCE / f"batch2_before/{arm}/{d}.public.json"
            unit = read(public)
            raw = Path(unit["raw_artifact"])
            value = read(raw)
            assert len(value["calls"]) == 1 and value["response"] == unit["response"]
            assert unit["published_library"] == (parent if arm == "skill_memory" else [])
            if arm == "skill_memory":
                named_request(value["calls"][0]["request"])
            files.update({str(public): sha(public), str(raw): sha(raw)})
    stop = read(SOURCE / "operator_stop_request.json")
    live = process_identity(stop["pid"])
    if live is not None and live["state"] != "Z":
        assert live["start_ticks"] == stop["process_start_ticks"] and live["argv"] == stop["actual_argv_checked"]
    RunStore.immutable_json(OUT / "registration.json", {
        "at": now(), "source_ids": ids, "fixed_M1_bank": parent, "files": files,
        "source_worker_identity": {"pid": stop["pid"], "start_ticks": stop["process_start_ticks"], "argv": stop["actual_argv_checked"]},
        "planned_new_native_calls": 6, "planned_new_teacher_calls": 0,
        "all_six_actual_requests_roundtrip_exactly": True,
        "existing_B2_scores_known_not_blind_or_formal_TEST": True,
        "local_construction_checks_not_generation_or_efficacy": True,
    })


class Probe(Comparison):
    def __init__(self):
        registration = read(OUT / "registration.json")
        self.cfg = {**read(CONFIG), "planned_new_native_calls": 6, "planned_new_teacher_calls": 0}
        self.bindings = registration["files"]
        self.run_id, self.out = OUT.name, OUT
        self.native, self.teachers, self.teacher_attempts, self.current_batch, self.stop = [], [], 0, 2, False
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: setattr(self, "stop", True))

    def execute(self):
        registration = read(OUT / "registration.json")
        expected = registration["source_worker_identity"]
        self.progress("waiting_for_exact_source_worker_exit")
        while True:
            self.check()
            live = process_identity(expected["pid"])
            if live is None or live["state"] == "Z":
                break
            assert live["start_ticks"] == expected["start_ticks"] and live["argv"] == expected["argv"]
            time.sleep(5)
        terminal = read(SOURCE / "progress.json")
        assert terminal["state"] in ("completed", "failed", "stopped")
        RunStore.immutable_json(OUT / "source_terminal_provenance.json", {
            "at": now(), "actual_terminal_state": terminal,
            "exact_worker_exited_or_zombie_not_a_timeout_inference": True,
            "complete_B2_prefix_independent_of_unrelated_full148_completion": True,
        })
        with (ROOT / "artifacts/gpu_generation.lock").open("a+") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            for d in registration["source_ids"]:
                original = read(SOURCE / f"batch2_before/skill_memory/{d}.final.native.json")["calls"][0]["request"]
                request = named_request(original)
                self.call(OUT / f"named_fields/{d}.native.json", request["messages"],
                          request["response_format"]["json_schema"]["schema"], request["max_tokens"],
                          {"stage": "fixed_M1_complete_B2_named_fields", "arm": "named_fields", "document_id": d, "call_role": "final"})
                assert self.native[-1]["calls"][0]["request"] == request
            self.finish_probe()

    def finish_probe(self):
        registration = read(OUT / "registration.json")
        ids = registration["source_ids"]
        assert len(self.native) == len({n["response"]["raw_id"] for n in self.native}) == 6
        assert sha(ROOT / self.cfg["source_archive"]) == self.cfg["source_archive_sha256"]
        with zipfile.ZipFile(ROOT / self.cfg["source_archive"]) as archive:
            author = json.loads(archive.read("contract-nli/train.json"))
        rows = {r["id"]: r for r in author["documents"] if r["id"] in ids}
        groups = {name: [] for name in ("ordinary_memory", "table_skills", "named_skills")}
        for d in ids:
            row = rows[d]
            for arm, name in (("ordinary_memory", "ordinary_memory"), ("skill_memory", "table_skills"), (None, "named_skills")):
                if arm is None:
                    raw = read(OUT / f"named_fields/{d}.native.json")
                    expected = named_request(read(SOURCE / f"batch2_before/skill_memory/{d}.final.native.json")["calls"][0]["request"])
                else:
                    raw = read(SOURCE / f"batch2_before/{arm}/{d}.final.native.json")
                    expected = raw["calls"][0]["request"]
                assert len(raw["calls"]) == 1 and raw["calls"][0]["request"] == expected
                assert json.loads(expected["messages"][1]["content"])["full_contract_with_original_span_markers"] == marked_text(row)
                score = original_score(raw["response"], row, row["annotation_sets"][0]["annotations"], list(author["labels"]))
                if score["public_valid"]:
                    validate(score["parsed"], expected["response_format"]["json_schema"]["schema"])
                if arm is not None:
                    close(score["queries"], read(SOURCE / f"batch2_before/{arm}/{d}.public.json")["queries"])
                groups[name].append({"document_id": d, "response": raw["response"], **score})
        paired = {}
        for name in ("ordinary_memory", "table_skills"):
            pairs = [(a, b) for left, right in zip(groups[name], groups["named_skills"], strict=True)
                     for a, b in zip(left["queries"], right["queries"], strict=True)]
            paired[name] = {field: {
                "fixes": sum(not a[field] and b[field] for a, b in pairs),
                "damage": sum(a[field] and not b[field] for a, b in pairs),
            } for field in ("label_correct", "joint_exact")}
            nn = [(a, b) for a, b in pairs if a["gold_non_neutral"]]
            def sets(q):
                return set() if q["prediction"] is None else set(q["prediction"]["spans"]) & set(q["gold"]["spans"])
            paired[name]["true_evidence_members_gained"] = sum(len(sets(b) - sets(a)) for a, b in nn)
            paired[name]["true_evidence_members_lost"] = sum(len(sets(a) - sets(b)) for a, b in nn)
        self.check()
        result = {"at": now(), "run_id": self.run_id, "source_ids": ids,
                  "all6_new_answers_saved_before_new_outcome_scoring": True,
                  "new_native_calls": 6, "new_teacher_calls": 0,
                  "only_named_vs_positional_skill_serialization_changes": True,
                  "not_new_learning_formal_TEST_or_significance_evidence": True,
                  "metrics": {name: points(units) for name, units in groups.items()},
                  "paired_named_vs_archived": paired, "all_units": groups,
                  "audited_file_sha256": {**self.bindings, **{str(p): sha(p) for p in (OUT / "named_fields").glob("*.native.json")}},
                  "no_method_selection_bank_rollback_or_automatic_launch": True}
        RunStore.immutable_json(OUT / "completion.json", result)
        RunStore.atomic_json(OUT / "progress.json", {"at": now(), "state": "completed", "run_id": self.run_id, "completed_native_calls": 6, "completed_teacher_calls": 0})
        print(json.dumps({k: v for k, v in result.items() if k in ("run_id", "metrics", "paired_named_vs_archived")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    command = sys.argv[1]
    if command == "prepare":
        prepare()
    elif command == "launch":
        assert (OUT / "registration.json").exists() and not (OUT / "launch.json").exists()
        argv = [str(ROOT / ".venv/bin/python"), str(Path(__file__).resolve()), "worker"]
        with (OUT / "worker.log").open("xb") as log:
            child = subprocess.Popen(argv, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True, env={**os.environ, "PYTHONUNBUFFERED": "1"})
        RunStore.immutable_json(OUT / "launch.json", {"at": now(), "pid": child.pid, "actual_argv": argv, "background_independent_of_conversation": True})
        print(json.dumps({"run_id": OUT.name, "pid": child.pid}))
    elif command == "worker":
        probe = Probe()
        try:
            probe.execute()
        except BaseException as exc:
            value = {"at": now(), "run_id": OUT.name, "error": repr(exc), "completed_native_calls": len(probe.native), "completed_teacher_calls": 0, "no_retry_fallback_or_answer_repair": True}
            RunStore.immutable_json(OUT / "failure.json", value)
            RunStore.atomic_json(OUT / "progress.json", {"state": "stopped" if isinstance(exc, InterruptedError) else "failed", **value})
            raise
    else:
        raise ValueError("Explicit prepare, launch or worker command required")
