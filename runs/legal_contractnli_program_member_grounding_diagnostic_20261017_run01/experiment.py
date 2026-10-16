"""Six native answers isolating source-program member text delivery."""

# ruff: noqa: E402 -- Run-local entry point, never imported by the learner.
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
sys.path.insert(0, str(ROOT))

from jsonschema import validate

from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.inference.native import WireClient
from legal_skill_guard.learning.audit import close, original_score
from legal_skill_guard.learning.experiment import Comparison, now, points, read, sha
from legal_skill_guard.learning.source_programs import execute_program
from legal_skill_guard.utils.hashing import canonical_json_sha256

MAIN = ROOT / "runs/legal_contractnli_source_program_online_learning_20261017_run03"
SOURCE = ROOT / "runs/legal_contractnli_decision_boundary_content_diagnostic_20261017_run01"
CONFIG = ROOT / "configs/contractnli_source_programs_completion.json"
IDS = [273, 416, 261, 487, 377, 159]


class SourceOnly(dict):
    def __getitem__(self, key):
        if key not in ("text", "spans"):
            raise AssertionError("Native member construction may read only original text/spans")
        return super().__getitem__(key)


def grounded_request(original, row):
    result = copy.deepcopy(original)
    body = json.loads(result["messages"][1]["content"])
    bank = body["published_source_programs"]
    executed = {s["id"]: execute_program(row, s) for s in bank}
    assert body["source_program_query_receipts"] == {
        sid: [{k: v for k, v in event.items() if k not in ("literal_original_clauses", "actual_query_arguments", "skill_id")}
            for event in events] for sid, events in executed.items()}
    for h, question in body["hypotheses"].items():
        assert "unverified_source_program_members" not in question
        ids = [s["id"] for s in bank if h in s["hypothesis_ids"]]
        assert question["applicable_published_skills"] == [{"id": sid} for sid in ids]
        indices = sorted({i for sid in ids for event in executed[sid] for i in event["returned_original_span_indices"]})
        question["unverified_source_program_members"] = [{"original_span_index": i,
            "literal_original_text": row["text"][row["spans"][i][0]:row["spans"][i][1]]} for i in indices]
    result["messages"][1]["content"] = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    restored = copy.deepcopy(result)
    for question in body["hypotheses"].values():
        question.pop("unverified_source_program_members")
    restored["messages"][1]["content"] = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    assert restored == original
    return result


def prepare():
    assert not (OUT / "registration.json").exists()
    cfg = read(CONFIG)
    audit_path = SOURCE / "monitoring/complete6_independent_original_author_sets_and_wire_audit.json"
    audit = read(audit_path)
    assert all(sha(p) == h for p, h in audit["bindings"].items())
    assert read(SOURCE / "progress.json")["state"] == "completed"
    for run in (MAIN, SOURCE):
        assert not (Path("/proc") / str(read(run / "launch.json")["pid"])).exists()
    packet = read(ROOT / cfg["input_packet"])
    rows = {r["id"]: r for r in packet["training"]}
    assert [r["id"] for r in packet["training"] if r["batch"] == 3] == IDS
    meter, requests = WireClient(cfg["generation"]), {}
    for d in IDS:
        raw_path = SOURCE / f"inspection_rewrite/{d}.native.json"
        request = grounded_request(read(raw_path)["calls"][0]["request"], SourceOnly(rows[d]))
        tokens = meter.token_count(messages=request["messages"])
        assert tokens + request["max_tokens"] <= cfg["generation"]["context_tokens"]
        requests[str(d)] = {"source_raw_path": str(raw_path), "source_raw_sha256": sha(raw_path),
            "prospective_request_sha256": canonical_json_sha256(request), "full_prompt_tokens": tokens,
            "output_reservation": request["max_tokens"]}
    paths = [CONFIG, CONFIG.with_suffix(".frozen.json"), Path(__file__), OUT / "PROTOCOL.md", audit_path,
        SOURCE / "completion.json", SOURCE / "launch.json", SOURCE / "progress.json", SOURCE / "diagnostic_bank.json"]
    RunStore.immutable_json(OUT / "registration.json", {"at": now(), "source_ids": IDS,
        "files": {**audit["bindings"], **{str(p): sha(p) for p in paths}}, "requests": requests,
        "planned_new_native_teacher_calls": [6, 0], "fixed_semantic_bank_teacher_sequence_not_new_cost": 1363,
        "prior_B3_outcomes_known_development_not_blind_TEST": True,
        "all6_full_capacity_and_source_only_roundtrips_checked_without_generation": True})


class Probe(Comparison):
    def __init__(self):
        self.cfg = {**read(CONFIG), "planned_new_native_calls": 6, "planned_new_teacher_calls": 0}
        self.bindings = read(OUT / "registration.json")["files"]
        self.run_id, self.out = OUT.name, OUT
        self.native, self.teachers, self.teacher_attempts, self.current_batch, self.stop = [], [], 0, 3, False
        self.rows = {r["id"]: r for r in read(ROOT / self.cfg["input_packet"])["training"]}
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: setattr(self, "stop", True))

    def execute(self):
        self.check()
        registration = read(OUT / "registration.json")
        with (ROOT / "artifacts/gpu_generation.lock").open("a+") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            for d in IDS:
                original = read(SOURCE / f"inspection_rewrite/{d}.native.json")["calls"][0]["request"]
                request = grounded_request(original, SourceOnly(self.rows[d]))
                assert canonical_json_sha256(request) == registration["requests"][str(d)]["prospective_request_sha256"]
                self.call(OUT / f"grounded_members/{d}.native.json", request["messages"],
                    request["response_format"]["json_schema"]["schema"], request["max_tokens"],
                    {"stage": "fixed_M2_B3_all_literal_program_members", "arm": "grounded_members",
                        "document_id": d, "call_role": "final"})
                assert self.native[-1]["calls"][0]["request"] == request
            self.finish_probe()

    def finish_probe(self):
        assert len(self.native) == len({n["response"]["raw_id"] for n in self.native}) == 6
        assert not self.teachers and not self.teacher_attempts
        assert sha(ROOT / self.cfg["source_archive"]) == self.cfg["source_archive_sha256"]
        with zipfile.ZipFile(ROOT / self.cfg["source_archive"]) as archive:
            author = json.loads(archive.read("contract-nli/train.json"))
        rows = {r["id"]: r for r in author["documents"] if r["id"] in IDS}
        groups = {name: [] for name in ("ordinary_memory", "semantic_M2", "grounded_members")}
        files = {}
        for d in IDS:
            for name in groups:
                path = MAIN / f"batch3_before/ordinary_memory/{d}.final.native.json" if name == "ordinary_memory" else SOURCE / f"inspection_rewrite/{d}.native.json" if name == "semantic_M2" else OUT / f"grounded_members/{d}.native.json"
                raw = read(path)
                assert len(raw["calls"]) == 1
                if name == "grounded_members":
                    original = read(SOURCE / f"inspection_rewrite/{d}.native.json")["calls"][0]["request"]
                    assert raw["calls"][0]["request"] == grounded_request(original, SourceOnly(rows[d]))
                score = original_score(raw["response"], rows[d], rows[d]["annotation_sets"][0]["annotations"], list(author["labels"]))
                if score["public_valid"]:
                    validate(score["parsed"], raw["calls"][0]["request"]["response_format"]["json_schema"]["schema"])
                if name == "ordinary_memory":
                    close(score["queries"], read(MAIN / f"batch3_before/ordinary_memory/{d}.public.json")["queries"])
                groups[name].append({"document_id": d, "response": raw["response"], **score})
                files[str(path)] = sha(path)
        paired = {}
        for name in ("ordinary_memory", "semantic_M2"):
            pairs = [(a, b) for left, right in zip(groups[name], groups["grounded_members"], strict=True)
                for a, b in zip(left["queries"], right["queries"], strict=True)]
            paired[name] = {field: {"fixes": sum(not a[field] and b[field] for a, b in pairs),
                "damage": sum(a[field] and not b[field] for a, b in pairs)} for field in ("label_correct", "joint_exact")}
            def true(q):
                return set() if q["prediction"] is None else set(q["prediction"]["spans"]) & set(q["gold"]["spans"])
            nn = [(a, b) for a, b in pairs if a["gold_non_neutral"]]
            paired[name].update(true_original_members_gained=sum(len(true(b) - true(a)) for a, b in nn),
                true_original_members_lost=sum(len(true(a) - true(b)) for a, b in nn))
        self.check()
        result = {"at": now(), "run_id": self.run_id, "source_ids": IDS,
            "all6_new_answers_saved_before_outcome_scoring": True,
            "only_source_only_literal_program_member_view_added_all_other_input_fields_unchanged": True,
            "new_native_teacher_calls": [6, 0], "fixed_bank_prior_teacher1363_not_new_or_independent_learning": True,
            "new_native_usage": {k: sum(n["response"][k] for n in self.native) for k in ("prompt_tokens", "completion_tokens")},
            "metrics": {name: points(units) for name, units in groups.items()}, "paired_grounding_vs_archived": paired,
            "all_units": groups, "audited_file_sha256": {**self.bindings, **files},
            "no_main_admission_rollback_automatic_adoption_or_TEST_claim": True}
        RunStore.immutable_json(OUT / "completion.json", result)
        RunStore.atomic_json(OUT / "progress.json", {"at": now(), "state": "completed", "run_id": self.run_id,
            "completed_native_calls": 6, "completed_teacher_calls": 0})
        print(json.dumps({k: result[k] for k in ("run_id", "metrics", "paired_grounding_vs_archived")}, ensure_ascii=False))


if __name__ == "__main__":
    command = sys.argv[1]
    if command == "prepare":
        prepare()
    elif command == "launch":
        assert (OUT / "registration.json").exists() and not (OUT / "launch.json").exists()
        argv = [str(ROOT / ".venv/bin/python"), str(Path(__file__).resolve()), "worker"]
        with (OUT / "worker.log").open("xb") as log:
            child = subprocess.Popen(argv, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                start_new_session=True, env={**os.environ, "PYTHONUNBUFFERED": "1"})
        RunStore.immutable_json(OUT / "launch.json", {"at": now(), "pid": child.pid, "actual_argv": argv,
            "background_independent_of_conversation": True})
        print(json.dumps({"run_id": OUT.name, "pid": child.pid}))
    elif command == "worker":
        probe = Probe()
        try:
            probe.execute()
        except BaseException as exc:
            value = {"at": now(), "run_id": OUT.name, "error": repr(exc), "completed_native_calls": len(probe.native),
                "completed_teacher_calls": 0, "no_retry_fallback_or_answer_repair": True}
            RunStore.immutable_json(OUT / "failure.json", value)
            RunStore.atomic_json(OUT / "progress.json", {"state": "stopped" if isinstance(exc, InterruptedError) else "failed", **value})
            raise
    else:
        raise ValueError("Explicit prepare, launch or worker required")
