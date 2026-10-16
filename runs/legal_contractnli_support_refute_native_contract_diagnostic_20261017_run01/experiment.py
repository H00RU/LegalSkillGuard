"""One prospective native execution intervention; no semantic host verdicts."""

# ruff: noqa: E402 -- Explicit immutable run-local diagnostic, not a new framework.
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

from jsonschema import Draft202012Validator, ValidationError, validate

from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.inference.native import WireClient
from legal_skill_guard.learning.audit import original_score
from legal_skill_guard.learning.experiment import Comparison, now, points, read, sha
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha

PARENT = ROOT / "runs/legal_contractnli_native_grounded_fixed_tool_continuation_20261017_run02"
CONFIG = ROOT / "configs/contractnli_source_programs_completion.json"
BACKUP = ROOT / "artifacts/native_loop_complete30_all380_before_nli_contract_backup_20261017.json"
DOCS = [430, 290, 622, 613, 383, 92]
ARMS = ("ordinary_memory", "skill_memory")
STAGE = "support_refute_B4"
ORDER_OLD = "For each emit choice, spans, reason, used_skill_ids in that order."
ORDER_NEW = ("For each emit hypothesis_supported, hypothesis_refuted, choice, "
    "spans, reason, used_skill_ids in that order.")
NOTICE = (
    " First judge the exact supplied hypothesis against the full NDA, including "
    "its negation: hypothesis_supported=true only when contractual evidence "
    "supports that hypothesis; hypothesis_refuted=true only when contractual "
    "evidence opposes it. Refuted does NOT mean merely unsupported or missing "
    "query hits. Both false means the document settles neither direction. "
    "Emit your own consistent original label: supported only -> Entailment; "
    "refuted only -> Contradiction; neither -> NotMentioned. All three relations "
    "remain available for every question. Cite all original evidence for your "
    "supported/opposed decision; do not discard opposing evidence as absence."
)
PATTERNS = (("Entailment", True, False), ("Contradiction", False, True),
    ("NotMentioned", False, False))


def consistency_schema(original):
    result = copy.deepcopy(original)
    for key, question in original["properties"].items():
        branches = question["anyOf"]
        assert len(branches) == 2
        assert branches[0]["properties"]["choice"]["enum"] == ["Entailment", "Contradiction"]
        assert branches[1]["properties"]["choice"]["enum"] == ["NotMentioned"]
        expanded = []
        for label, supported, refuted in PATTERNS:
            old = branches[int(label == "NotMentioned")]
            new = copy.deepcopy(old)
            new["properties"] = {
                "hypothesis_supported": {"type": "boolean", "enum": [supported]},
                "hypothesis_refuted": {"type": "boolean", "enum": [refuted]},
                **copy.deepcopy(old["properties"]),
            }
            new["properties"]["choice"] = {"type": "string", "enum": [label]}
            new["required"] = ["hypothesis_supported", "hypothesis_refuted", *old["required"]]
            # Every non-flag constraint is unchanged for this original class.
            restored = copy.deepcopy(new)
            for flag in ("hypothesis_supported", "hypothesis_refuted"):
                del restored["properties"][flag]
                restored["required"].remove(flag)
            restored["properties"]["choice"] = copy.deepcopy(old["properties"]["choice"])
            assert restored == old
            expanded.append(new)
        result["properties"][key] = {"anyOf": expanded}
    return result


def schema_check(schema):
    Draft202012Validator.check_schema(schema)
    one = next(iter(schema["properties"].values()))
    validator = Draft202012Validator(one)
    checked = 0
    for label, supported, refuted in PATTERNS:
        sample = {"hypothesis_supported": supported, "hypothesis_refuted": refuted,
            "choice": label, "spans": [] if label == "NotMentioned" else [0],
            "reason": "Synthetic schema check, not a legal answer.", "used_skill_ids": []}
        validator.validate(sample)
        checked += 1
        for wrong in (x[0] for x in PATTERNS if x[0] != label):
            invalid = {**sample, "choice": wrong}
            try:
                validator.validate(invalid)
            except ValidationError:
                checked += 1
            else:
                raise AssertionError("Inconsistent flags/label were allowed")
    invalid = {**sample, "hypothesis_supported": True, "hypothesis_refuted": True}
    assert not validator.is_valid(invalid)
    return {"valid_and_invalid_patterns_checked": checked + 1, "no_generation": True}


class Probe(Comparison):
    def __init__(self, preparing=False):
        self.cfg = {**read(CONFIG), "planned_new_native_calls": 12, "planned_new_teacher_calls": 0}
        audit = PARENT / "monitoring/complete30_native36_original_author_sets_wire_and_failure_decomposition_audit.json"
        self.bindings = read(audit)["bindings"] if preparing else read(OUT / "registration.json")["files"]
        self.out, self.run_id = OUT, OUT.name
        self.native, self.teachers, self.teacher_attempts, self.current_batch, self.stop = [], [], 0, 4, False
        self.meter = WireClient(self.cfg["generation"])
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: setattr(self, "stop", True))

    def compile(self, arm, doc):
        old_path = PARENT / f"native/B4_first_encounter/{arm}/{doc}.native.json"
        old = read(old_path)
        assert old["arm"] == arm and old["document_id"] == doc
        request = old["calls"][0]["request"]
        messages = copy.deepcopy(request["messages"])
        assert len(messages) == 2 and messages[0]["role"] == "system"
        assert messages[0]["content"].count(ORDER_OLD) == 1
        messages[0]["content"] = messages[0]["content"].replace(ORDER_OLD, ORDER_NEW) + NOTICE
        assert messages[1] == request["messages"][1]
        schema = consistency_schema(request["response_format"]["json_schema"]["schema"])
        tokens = self.meter.token_count(messages=messages)
        assert tokens + self.cfg["generation"]["max_tokens"] <= self.cfg["generation"]["context_tokens"]
        payload = {"messages": messages, "schema": schema, "trace": old["actual_factual_trace"],
            "published_library": old["published_library"], "original_request_artifact": str(old_path),
            "stage": STAGE, "arm": arm, "document_id": doc, "prompt_tokens": tokens,
            "messages_sha256": csha(messages), "schema_sha256": csha(schema),
            "original_user_string_unchanged": True}
        return payload

    def execute(self):
        self.check()
        with (ROOT / "artifacts/gpu_generation.lock").open("a+") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            registration = read(OUT / "registration.json")
            for entry in registration["ordered_requests"]:
                payload = read(Path(entry["path"]))
                current = self.compile(entry["arm"], entry["document_id"])
                assert current == payload
                self.call(OUT / f"native/{entry['arm']}/{entry['document_id']}.native.json",
                    payload["messages"], payload["schema"], self.cfg["generation"]["max_tokens"], {
                        "stage": STAGE, "arm": entry["arm"], "document_id": entry["document_id"],
                        "call_role": "final", "published_library": payload["published_library"],
                        "actual_factual_trace": payload["trace"],
                        "original_request_artifact": payload["original_request_artifact"]})
                raw = self.native[-1]
                if raw["response"]["finish_reason"] != "stop":
                    raise InterruptedError("Incomplete native answer saved; no retry or repair")
                validate(json.loads(raw["response"]["content"]), payload["schema"])
            self.finish()

    def finish(self):
        assert len(self.native) == 12 and not self.teachers and self.teacher_attempts == 0
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
                    raw = read(path)
                    row = rows[doc]
                    scored = original_score(raw["response"], row, row["annotation_sets"][0]["annotations"], list(author["labels"]))
                    if scored["public_valid"]:
                        validate(scored["parsed"], raw["calls"][0]["request"]["response_format"]["json_schema"]["schema"])
                    units.append({"document_id": doc, "response": raw["response"], **scored})
                    hashes[str(path)] = sha(path)
                groups[version + "_" + arm] = units
        contrasts = {}
        for version in ("old_contract", "support_refute_contract"):
            ordinary = groups[version + "_ordinary_memory"]
            skill = groups[version + "_skill_memory"]
            counts = {k: 0 for k in ("label_fixes", "label_damage", "joint_fixes", "joint_damage", "true_gained", "true_lost")}
            for a, b in zip(ordinary, skill, strict=True):
                for x, y in zip(a["queries"], b["queries"], strict=True):
                    assert x["hypothesis_id"] == y["hypothesis_id"] and x["gold"] == y["gold"]
                    for key in ("label", "joint"):
                        field = "label_correct" if key == "label" else "joint_exact"
                        counts[key + "_fixes"] += int(not x[field] and y[field])
                        counts[key + "_damage"] += int(x[field] and not y[field])
                    gold = set(x["gold"]["spans"])
                    aa, bb = set(x["prediction"]["spans"]), set(y["prediction"]["spans"])
                    counts["true_gained"] += len((bb - aa) & gold)
                    counts["true_lost"] += len((aa - bb) & gold)
            contrasts[version + "_skill_minus_ordinary"] = counts
        self.check()
        result = {"at": now(), "run_id": self.run_id, "new_native_teacher_calls": [12, 0],
            "historical_reference_answers_not_new_independent_repetitions": 12,
            "all12_saved_before_new_outcome_scoring": True,
            "metrics": {name: points(units) for name, units in groups.items()},
            "same_contract_skill_contrasts": contrasts, "all_units": groups,
            "new_native_usage": {k: sum(v["response"][k] for v in self.native) for k in ("prompt_tokens", "completion_tokens")},
            "actual_raw_outputs_scored_no_choice_mapping_or_answer_repair": True,
            "shared_prefix_costs_not_free": str(PARENT / "completion.json"),
            "not_formal_TEST_independent_learning_or_method_win": True, "all_output_sha256": hashes}
        RunStore.immutable_json(OUT / "completion.json", result)
        RunStore.atomic_json(OUT / "progress.json", {"at": now(), "run_id": self.run_id,
            "state": "completed", "completed_native_calls": 12, "completed_teacher_calls": 0})
        print(json.dumps({"metrics": result["metrics"], "contrasts": contrasts}, ensure_ascii=False))


def prepare():
    assert not (OUT / "registration.json").exists()
    assert read(PARENT / "progress.json")["state"] == "completed"
    assert not Path("/proc", str(read(PARENT / "launch.json")["pid"])).exists()
    receipt = read(BACKUP)
    assert receipt["completed_new_native_teacher_calls"] == [30, 2]
    assert sha(receipt["archive"]) == receipt["archive_sha256"]
    probe = Probe(preparing=True)
    probe.check()
    records, systems = [], set()
    for i, doc in enumerate(DOCS):
        for arm in (ARMS if i % 2 == 0 else ARMS[::-1]):
            payload = probe.compile(arm, doc)
            systems.add(payload["messages"][0]["content"])
            path = OUT / f"prospective/{arm}/{doc}.json"
            RunStore.immutable_json(path, payload)
            records.append({"arm": arm, "document_id": doc, "path": str(path), "sha256": sha(path),
                "prompt_tokens": payload["prompt_tokens"], "messages_sha256": payload["messages_sha256"],
                "schema_sha256": payload["schema_sha256"]})
    assert len(systems) == 1
    checks = {arm: schema_check(read(OUT / f"prospective/{arm}/{DOCS[0]}.json")["schema"]) for arm in ARMS}
    paths = [Path(__file__), OUT / "PROTOCOL.md", BACKUP, PARENT / "completion.json",
        PARENT / "monitoring/complete30_native36_original_author_sets_wire_and_failure_decomposition_audit.json",
        PARENT / "monitoring/complete30_nonvacuous_delivery_scope_reasoning_and_contradiction_loss_audit.json",
        *[Path(v["path"]) for v in records]]
    RunStore.immutable_json(OUT / "registration.json", {"at": now(), "files": {
        **probe.bindings, **{str(p): sha(p) for p in paths}},
        "ordered_requests": records, "new_native_teacher_calls": [12, 0],
        "all12_full_requests_fit_before_first_generation": True, "synthetic_schema_checks": checks,
        "old_user_strings_banks_queries_candidates_tool_and_generation_unchanged": True,
        "all_source_classes_available_no_semantic_host_or_posthoc_mapping": True,
        "known_development_cases_not_independent_or_TEST": True})
    print(json.dumps({"prepared_new_calls": [12, 0], "requests": records, "schema_checks": checks}))


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
                "no_retry_fallback_admission_bank_selection_or_answer_repair": True}
            RunStore.immutable_json(OUT / "failure.json", value)
            RunStore.atomic_json(OUT / "progress.json", {"state": "stopped" if isinstance(exc, InterruptedError) else "failed", **value})
            raise
    else:
        raise ValueError("Explicit prepare, launch or worker required")
