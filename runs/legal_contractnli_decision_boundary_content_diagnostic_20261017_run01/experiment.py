"""Fixed-program six-source diagnostic of learned legal-inspection content."""

# ruff: noqa: E402 -- Independent run-local entry point.
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
from legal_skill_guard.inference.native import WireClient
from legal_skill_guard.learning.audit import close, original_score
from legal_skill_guard.learning.experiment import Comparison, now, points, read, sha
from legal_skill_guard.learning.source_programs import SourceProgramStudy, unpack_program_feedback
from legal_skill_guard.utils.hashing import canonical_json_sha256

SOURCE = ROOT / "runs/legal_contractnli_source_program_online_learning_20261017_run03"
CONFIG = ROOT / "configs/contractnli_source_programs_completion.json"
IDS = [273, 416, 261, 487, 377, 159]
SYSTEM = (
    "Test whether precise learned legal-inspection CONTENT helps a frozen lawyer. "
    "Use ONLY the supplied original B1/B2 TRAIN feedback and public hypotheses. "
    "The original_M2_training_feedback contains actual M1-parent observations; "
    "the separate published_M2_bank is the resulting candidate to edit, NOT the "
    "bank used in those observations. No newer executions or future cases exist "
    "in this input. Replace ONLY each named skill's inspection string. IDs, "
    "public scopes, executable queries, actor prompt/schema and all other input "
    "conditions are fixed by this controlled diagnostic. "
    "Distill concrete reusable evidence-dependent legal reasoning procedures, "
    "not just generic reminders to check actors, actions, conditions or polarity. "
    "Use supplied contrasting outcomes to teach which distinctions matter for "
    "the exact public hypotheses and how to test them in the full source. "
    "A skill may explain conditional reasoning, distinctions between related "
    "actions/triggers/scopes, and justified implications, without declaring a "
    "verdict for a current contract. Explain how to handle qualifications, "
    "contrasting evidence and insufficient support rather than forcing a label. "
    "Keep acquisition and complete-original-evidence inspection where useful. "
    "Do not confuse allowing evidence-completeness learning WITHOUT a new class "
    "condition with prohibiting justified legal decision distinctions. Within a "
    "shared skill, distinguish its exact public tasks rather than transferring "
    "one task's criterion to another. Preserve every final choice and evidence "
    "decision as the lawyer's own, with no host verdict or mandatory citation. "
    "Gold is benchmark training feedback, not universal legal truth. No outside "
    "law/tools, invented observed reasoning or claims that an untested skill "
    "worked. No document IDs, entities, dates, original indices, copied lookup "
    "clauses, answer tables or future data in runtime text. Prefer concise "
    "procedures to synonym lists or broad topic summaries; the whole unchanged "
    "query bank plus new prose must fit BOTH4096-token capacities. Aim for "
    "concise replacements, not a second long playbook. No performance-based "
    "selection, second curator, rollback, answer repair or another attempt. "
    "Return exactly inspection_by_skill_id for every supplied existing ID."
)


def identity(pid):
    proc = Path("/proc") / str(pid)
    try:
        fields = (proc / "stat").read_text().rsplit(")", 1)[1].split()
        return {"pid": pid, "state": fields[0], "start_ticks": fields[19],
            "argv": [s.decode() for s in (proc / "cmdline").read_bytes().split(b"\0") if s]}
    except FileNotFoundError:
        return None


def rewrite_request(original, old_bank, new_bank):
    assert len(old_bank) == len(new_bank)
    for old, new in zip(old_bank, new_bank, strict=True):
        restored = copy.deepcopy(new)
        restored["guidance"]["inspection"] = old["guidance"]["inspection"]
        assert restored == old
    request = copy.deepcopy(original)
    body = json.loads(request["messages"][1]["content"])
    assert body["published_source_programs"] == old_bank
    body["published_source_programs"] = copy.deepcopy(new_bank)
    request["messages"][1]["content"] = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    restored = copy.deepcopy(request)
    body["published_source_programs"] = copy.deepcopy(old_bank)
    restored["messages"][1]["content"] = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    assert restored == original
    return request


def prepare():
    assert not (OUT / "registration.json").exists()
    cfg, frozen = read(CONFIG), read(CONFIG.with_suffix(".frozen.json"))
    assert all(sha(p) == h for p, h in frozen["files"].items())
    bank = read(SOURCE / "update_transactions/b2.json")["publication"]
    packet = read(ROOT / cfg["input_packet"])
    assert [r["id"] for r in packet["training"] if r["batch"] == 3] == IDS
    audit_path = SOURCE / "monitoring/M2_full_actual_teacher_packet_and_publication_audit.json"
    assert all(sha(p) == h for p, h in read(audit_path)["audited_file_sha256"].items())
    parent = identity(read(SOURCE / "launch.json")["pid"])
    assert parent is not None and parent["state"] != "Z"
    paths = [CONFIG, CONFIG.with_suffix(".frozen.json"), Path(__file__), OUT / "PROTOCOL.md", audit_path,
        SOURCE / "launch.json", SOURCE / "update_transactions/b2.json"]
    paths += [SOURCE / "teacher/task_local_b2" / n for n in ("wire_request.json", "response.json", "event_log.json")]
    RunStore.immutable_json(OUT / "registration.json", {"at": now(), "source_ids": IDS,
        "fixed_M2_bank": bank, "source_worker_identity": parent,
        "files": {**frozen["files"], **{str(p): sha(p) for p in paths}},
        "planned_new_native_calls": 6, "planned_new_teacher_calls": 1,
        "registered_before_new_teacher_and_all_new_native_answers": True,
        "teacher_has_only_original_M2_training_feedback_not_B2_after_or_B3": True,
        "no_current_complete_B3_metrics_read_for_this_registration": True})


class Probe(Comparison):
    def __init__(self):
        self.cfg = {**read(CONFIG), "planned_new_native_calls": 6, "planned_new_teacher_calls": 1}
        self.bindings = read(OUT / "registration.json")["files"]
        self.run_id, self.out = OUT.name, OUT
        self.native, self.teachers, self.teacher_attempts, self.current_batch, self.stop = [], [], 0, 3, False
        self.labels = read(ROOT / self.cfg["input_packet"])["public_hypotheses"]
        self.meter = WireClient(self.cfg["generation"])
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: setattr(self, "stop", True))

    def execute(self):
        registration = read(OUT / "registration.json")
        old_bank = registration["fixed_M2_bank"]
        wire = read(SOURCE / "teacher/task_local_b2/wire_request.json")
        feedback = json.loads(wire["user_prompt"])
        decoded = unpack_program_feedback(feedback)
        assert decoded["supplied_original_witness_ids"] == self.cfg["training_ids"][:12]
        schema = {"type": "object", "additionalProperties": False, "required": ["inspection_by_skill_id"],
            "properties": {"inspection_by_skill_id": {"type": "object", "additionalProperties": False,
                "required": [s["id"] for s in old_bank],
                "properties": {s["id"]: {"type": "string", "minLength": 1, "maxLength": 3000} for s in old_bank}}}}
        value = self.teacher_call("inspection_semantics", SYSTEM, {
            "original_M2_training_feedback": feedback, "published_M2_bank": old_bank,
            "same_fixed_native_actor_system": self.cfg["bundled_solver_system"],
            "unchanged_full_master_and_one_copy_token_cap": self.cfg["library_token_hard_cap"],
        }, schema)
        new_bank = copy.deepcopy(old_bank)
        for skill in new_bank:
            skill["guidance"]["inspection"] = value["inspection_by_skill_id"][skill["id"]]
        tokens = SourceProgramStudy.validate_library(self, new_bank)
        RunStore.immutable_json(OUT / "diagnostic_bank.json", {"old_bank": old_bank, "bank": new_bank,
            "bank_sha256": canonical_json_sha256(new_bank),
            "capacity": tokens, "only_inspection_strings_changed_not_main_publication_or_efficacy_admission": True})
        expected = registration["source_worker_identity"]
        self.progress("waiting_for_exact_main_worker_exit_after_one_teacher")
        while True:
            self.check()
            live = identity(expected["pid"])
            if live is None or live["state"] == "Z":
                break
            assert (live["start_ticks"], live["argv"]) == (expected["start_ticks"], expected["argv"])
            time.sleep(5)
        terminal = read(SOURCE / "progress.json")
        assert terminal["state"] in ("completed", "failed", "stopped")
        audit_path = SOURCE / "monitoring/independent_B3_before.json"
        audit = read(audit_path)
        assert audit["complete_source_ids"] == IDS and audit["distinct_native_responses"] == 24
        assert all(sha(p) == h for p, h in audit["audited_file_sha256"].items())
        self.bindings = {**self.bindings, **audit["audited_file_sha256"], str(audit_path): sha(audit_path)}
        RunStore.immutable_json(OUT / "source_terminal_and_complete_B3_bindings.json", {
            "at": now(), "terminal_state": terminal, "files": self.bindings,
            "specific_worker_exited_not_timeout_and_complete_B3_not_unrelated_full148_required": True})
        with (ROOT / "artifacts/gpu_generation.lock").open("a+") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            for d in IDS:
                raw = read(SOURCE / f"batch3_before/skill_memory/{d}.final.native.json")
                request = rewrite_request(raw["calls"][0]["request"], old_bank, new_bank)
                self.call(OUT / f"inspection_rewrite/{d}.native.json", request["messages"],
                    request["response_format"]["json_schema"]["schema"], request["max_tokens"],
                    {"stage": "fixed_M2_complete_B3_inspection_rewrite", "arm": "inspection_rewrite",
                        "document_id": d, "call_role": "final", "published_library": new_bank})
                assert self.native[-1]["calls"][0]["request"] == request
            self.finish_probe(old_bank, new_bank)

    def finish_probe(self, old_bank, new_bank):
        assert len(self.native) == len({n["response"]["raw_id"] for n in self.native}) == 6
        assert len(self.teachers) == self.teacher_attempts == 1
        assert sha(ROOT / self.cfg["source_archive"]) == self.cfg["source_archive_sha256"]
        with zipfile.ZipFile(ROOT / self.cfg["source_archive"]) as archive:
            author = json.loads(archive.read("contract-nli/train.json"))
        rows = {r["id"]: r for r in author["documents"] if r["id"] in IDS}
        groups = {name: [] for name in ("ordinary_memory", "original_M2", "inspection_rewrite")}
        files = {}
        for d in IDS:
            row = rows[d]
            for arm, name in (("ordinary_memory", "ordinary_memory"), ("skill_memory", "original_M2"), (None, "inspection_rewrite")):
                path = OUT / f"inspection_rewrite/{d}.native.json" if arm is None else SOURCE / f"batch3_before/{arm}/{d}.final.native.json"
                raw = read(path)
                assert len(raw["calls"]) == 1
                if arm is None:
                    original = read(SOURCE / f"batch3_before/skill_memory/{d}.final.native.json")["calls"][0]["request"]
                    assert raw["calls"][0]["request"] == rewrite_request(original, old_bank, new_bank)
                score = original_score(raw["response"], row, row["annotation_sets"][0]["annotations"], list(author["labels"]))
                if score["public_valid"]:
                    validate(score["parsed"], raw["calls"][0]["request"]["response_format"]["json_schema"]["schema"])
                if arm is not None:
                    close(score["queries"], read(SOURCE / f"batch3_before/{arm}/{d}.public.json")["queries"])
                groups[name].append({"document_id": d, "response": raw["response"], **score})
                files[str(path)] = sha(path)
        paired = {}
        for name in ("ordinary_memory", "original_M2"):
            pairs = [(a, b) for left, right in zip(groups[name], groups["inspection_rewrite"], strict=True)
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
            "diagnostic_bank_sha256": canonical_json_sha256(new_bank),
            "all6_answers_saved_before_new_outcome_scoring": True,
            "only_runtime_inspection_content_changed_exact_request_roundtrip": True,
            "new_native_teacher_calls": [6, 1], "extra_teacher_not_budget_matched_method_comparison": True,
            "new_native_usage": {k: sum(n["response"][k] for n in self.native) for k in ("prompt_tokens", "completion_tokens")},
            "new_teacher_invocation": self.teachers[0]["invocation"],
            "metrics": {name: points(units) for name, units in groups.items()}, "paired_rewrite_vs_archived": paired,
            "all_units": groups, "audited_file_sha256": {**self.bindings, **files},
            "no_main_bank_admission_rollback_automatic_restart_or_independent_learning_claim": True,
            "exposed_TRAIN_development_not_formal_TEST_or_significance": True}
        RunStore.immutable_json(OUT / "completion.json", result)
        RunStore.atomic_json(OUT / "progress.json", {"at": now(), "state": "completed", "run_id": self.run_id,
            "completed_native_calls": 6, "completed_teacher_calls": 1})
        print(json.dumps({k: result[k] for k in ("run_id", "metrics", "paired_rewrite_vs_archived")}, ensure_ascii=False))


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
            "background_independent_of_conversation": True, "teacher_then_waits_exact_main_before_GPU_generation": True})
        print(json.dumps({"run_id": OUT.name, "pid": child.pid}))
    elif command == "worker":
        probe = Probe()
        try:
            probe.execute()
        except BaseException as exc:
            value = {"at": now(), "run_id": OUT.name, "error": repr(exc), "completed_native_calls": len(probe.native),
                "completed_teacher_calls": len(probe.teachers), "teacher_attempts": probe.teacher_attempts,
                "no_retry_fallback_or_answer_repair": True}
            RunStore.immutable_json(OUT / "failure.json", value)
            RunStore.atomic_json(OUT / "progress.json", {"state": "stopped" if isinstance(exc, InterruptedError) else "failed", **value})
            raise
    else:
        raise ValueError("Explicit prepare, launch or worker required")
