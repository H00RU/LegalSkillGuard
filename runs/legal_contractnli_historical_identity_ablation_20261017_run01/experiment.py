"""Bounded two-state ablation of historical identity and full-case examples."""

from __future__ import annotations

import copy
import fcntl
import json
import os
import re
import signal
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
PARENT = ROOT / "runs/legal_contractnli_contextual_experience_online_continuation_20261017_run03"
sys.path.insert(0, str(ROOT))

from jsonschema import validate

from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.inference.native import WireClient
from legal_skill_guard.learning.audit import original_score
from legal_skill_guard.learning.experiment import Comparison, now, points, read, sha
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha

ARMS = ("opaque_refs", "procedures_only")
MEMORY_KEYS = ("published_contextual_skills", "past_context_complete_demonstrations")
CONFIG = ROOT / "configs/contractnli_source_programs_completion.json"
BACKUP = OUT / "prelaunch_source_parent_and_inputs_backup.json"


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def alphabetic(index):
    """Bijective zero-based alphabetic identifiers, not current integer indices."""
    result = ""
    index += 1
    while index:
        index, digit = divmod(index - 1, 26)
        result = chr(ord("a") + digit) + result
    return result


def typed_history(memory):
    value = copy.deepcopy(memory)
    for name, demo in value[MEMORY_KEYS[1]].items():
        old = demo.pop("full_original_past_contract_with_local_span_markers")
        indices = [int(i) for i in re.findall(r"<PAST " + re.escape(name) + r" SPAN (\d+)>", old)]
        assert indices == list(range(len(indices)))
        keys = {i: name + ":" + alphabetic(i) for i in indices}
        assert len(set(keys.values())) == len(keys)
        new = old
        for i, key in keys.items():
            for slash in ("", "/"):
                marker = f"<{slash}PAST {name} SPAN {i}>"
                assert new.count(marker) == 1
                new = new.replace(marker, f"<{slash}PAST {key}>")
        restored = new
        for i, key in keys.items():
            for slash in ("", "/"):
                restored = restored.replace(f"<{slash}PAST {key}>", f"<{slash}PAST {name} SPAN {i}>")
        assert restored == old
        demo["full_original_past_contract_with_local_fragment_markers"] = new
        for h, answer in demo["original_annotated_answers"].items():
            old_answer = copy.deepcopy(answer)
            members = answer.pop("spans")
            answer["past_fragment_keys"] = [keys[i] for i in members]
            inverse = {key: i for i, key in keys.items()}
            assert {"choice": answer["choice"], "spans": [inverse[k] for k in answer["past_fragment_keys"]]} == old_answer
    return value


def transform(old, arm, meter, generation):
    payload = copy.deepcopy(old)
    body = json.loads(payload["messages"][1]["content"])
    old_memory = {k: copy.deepcopy(body[k]) for k in MEMORY_KEYS}
    memory = typed_history(old_memory) if arm == "opaque_refs" else copy.deepcopy(old_memory)
    if arm == "procedures_only":
        memory[MEMORY_KEYS[1]] = {}
        for skill in memory[MEMORY_KEYS[0]]:
            skill["guidance"]["past_demonstration_refs"] = []
    else:
        needle = "PAST Hn SPAN i markers and original_annotated_answers "
        replacement = "PAST Hn:alphabetic markers and past_fragment_keys in original_annotated_answers "
        assert payload["messages"][0]["content"].count(needle) == 1
        payload["messages"][0]["content"] = payload["messages"][0]["content"].replace(needle, replacement)
    for k in MEMORY_KEYS:
        body[k] = memory[k]
    original_body = json.loads(old["messages"][1]["content"])
    assert {k: v for k, v in body.items() if k not in MEMORY_KEYS} == {k: v for k, v in original_body.items() if k not in MEMORY_KEYS}
    assert payload["schema"] == old["schema"]
    for new_skill, old_skill in zip(memory[MEMORY_KEYS[0]], old_memory[MEMORY_KEYS[0]], strict=True):
        assert new_skill["id"] == old_skill["id"] and new_skill["hypothesis_ids"] == old_skill["hypothesis_ids"]
        assert new_skill["guidance"]["inspection"] == old_skill["guidance"]["inspection"]
    payload["messages"][1]["content"] = compact(body)
    refs = {h: v["applicable_published_skills"] for h, v in body["hypotheses"].items()}
    capacity = {"master_tokens": meter.token_count(text=compact(memory)),
        "scoped_tokens": meter.token_count(text=compact({**memory, "applicable_published_skills": refs}))}
    assert max(capacity.values()) <= 4096
    tokens = meter.token_count(messages=payload["messages"])
    assert tokens + generation["max_tokens"] <= generation["context_tokens"]
    payload.update(arm=arm, published_library=memory, prompt_tokens=tokens,
        messages_sha256=csha(payload["messages"]), historical_numeric_control_messages_sha256=old["messages_sha256"])
    payload["actual_factual_trace"]["actual_contextual_memory"] = {
        **capacity, "memory_sha256": csha(memory), "scope_references": refs,
        "identity_intervention": arm, "all_nonmemory_current_data_and_procedure_text_unchanged": True}
    return payload


def prepare():
    assert not (OUT / "registration.json").exists()
    cfg = read(CONFIG)
    meter = WireClient(cfg["generation"])
    phase = read(PARENT / "B7_post_teacher_frozen_inputs.json")
    bindings = dict(phase["files"])
    bindings[str(PARENT / "B7_post_teacher_frozen_inputs.json")] = sha(PARENT / "B7_post_teacher_frozen_inputs.json")
    assert all(sha(p) == h for p, h in bindings.items())
    selection = read(PARENT / "source_exposure_selection.json")
    entries = []
    for stage in ("B6", "B7"):
        for i, doc in enumerate(selection[stage]):
            old_path = PARENT / f"prospective/{stage}/joint/{doc}.json"
            old = read(old_path)
            for arm in (ARMS if i % 2 == 0 else ARMS[::-1]):
                payload = transform(old, arm, meter, cfg["generation"])
                path = OUT / f"prospective/{stage}/{arm}/{doc}.json"
                RunStore.immutable_json(path, payload)
                entries.append({"stage": stage, "arm": arm, "document_id": doc, "path": str(path),
                    "sha256": sha(path), "prompt_tokens": payload["prompt_tokens"]})
    files = [Path(__file__).resolve(), OUT / "PROTOCOL.md", *[Path(e["path"]) for e in entries]]
    bindings.update({str(p): sha(p) for p in files})
    result = {"at": now(), "run_id": OUT.name, "files": bindings, "ordered_requests": entries,
        "planned_new_native_teacher_calls": [32, 0], "actual_parent_banks_not_score_selected": True,
        "same16_preselected_sources_all_current_data_and_schema_unchanged": True,
        "all_original_past_sources_and_selected_annotations_roundtrip": True,
        "not_independent_learning_TEST_or_main_method_promotion": True}
    RunStore.immutable_json(OUT / "registration.json", result)
    print(compact({k: v for k, v in result.items() if k not in ("files", "ordered_requests")}))


class Study(Comparison):
    def __init__(self):
        self.cfg = {**read(CONFIG), "planned_new_native_calls": 32, "planned_new_teacher_calls": 0}
        self.out, self.run_id = OUT, OUT.name
        self.bindings = {**read(OUT / "registration.json")["files"], **read(OUT / "parent_terminal_bindings.json")["files"]}
        self.native, self.teachers, self.teacher_attempts, self.current_batch, self.stop = [], [], 0, 6, False
        self.answers, self.stage_results = [], {}
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: setattr(self, "stop", True))

    def score(self, stage):
        answers = [a for a in self.answers if a["stage"] == stage]
        assert len(answers) == 16
        assert sha(ROOT / self.cfg["source_archive"]) == self.cfg["source_archive_sha256"]
        with zipfile.ZipFile(ROOT / self.cfg["source_archive"]) as archive:
            author = json.loads(archive.read("contract-nli/train.json"))
        rows = {r["id"]: r for r in author["documents"]}
        groups = {}
        controls = []
        for doc in read(PARENT / "source_exposure_selection.json")[stage]:
            for arm in ("empty", "joint"):
                path = PARENT / f"native/{stage}/{arm}/{doc}.native.json"
                raw, p = read(path), read(PARENT / f"prospective/{stage}/{arm}/{doc}.json")
                assert raw["calls"][0]["request"]["messages"] == p["messages"]
                assert raw["calls"][0]["request"]["response_format"]["json_schema"]["schema"] == p["schema"]
                controls.append({"stage": stage, "arm": "inherited_" + arm, "document_id": doc, "path": str(path)})
        for a in answers + controls:
            row, raw = rows[a["document_id"]], read(a["path"])
            value = original_score(raw["response"], row, row["annotation_sets"][0]["annotations"], list(author["labels"]))
            assert value["public_valid"]
            groups.setdefault(a["arm"], []).append({"document_id": row["id"], "response": raw["response"], **value})
        result = {"at": now(), "stage": stage, "all16_new_saved_before_quality_scoring": True,
            "metrics": {arm: points(units) for arm, units in groups.items()}, "all_units": groups,
            "actual_new_answers": answers, "explicit_historical_controls_not_new_or_independent": controls}
        RunStore.immutable_json(OUT / f"stage_results/{stage}.json", result)
        self.stage_results[stage] = result

    def execute(self):
        self.check()
        assert read(PARENT / "progress.json")["state"] == "completed"
        assert read(PARENT / "completion.json")["logical_answers"] == 40
        receipt = read(BACKUP)
        assert receipt["all_members_verified"] and sha(receipt["archive"]) == receipt["archive_sha256"]
        entries = read(OUT / "registration.json")["ordered_requests"]
        self.progress("acquiring_shared_GPU_lease")
        with (ROOT / "artifacts/gpu_generation.lock").open("a+") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            for stage in ("B6", "B7"):
                self.current_batch = int(stage[1:])
                for e in [e for e in entries if e["stage"] == stage]:
                    self.check()
                    p = read(e["path"])
                    path = OUT / f"native/{stage}/{e['arm']}/{e['document_id']}.native.json"
                    response = self.call(path, p["messages"], p["schema"], self.cfg["generation"]["max_tokens"],
                        {k: p[k] for k in ("stage", "arm", "document_id", "published_library", "actual_factual_trace")} | {"call_role": "final"})
                    if response["finish_reason"] != "stop":
                        raise InterruptedError("Incomplete actual output retained; no retry")
                    validate(json.loads(response["content"]), p["schema"])
                    self.answers.append({"stage": stage, "arm": e["arm"], "document_id": e["document_id"], "path": str(path)})
                self.score(stage)
        assert len(self.native) == len(self.answers) == 32
        result = {"at": now(), "run_id": self.run_id, "actual_new_native_teacher_calls": [32, 0],
            "actual_new_answer_references": self.answers, "stage_metrics": {k: v["metrics"] for k, v in self.stage_results.items()},
            "new_native_usage": {k: sum(r["response"][k] for r in self.native) for k in ("prompt_tokens", "completion_tokens")},
            "parent_costs_not_free_or_independent": str(PARENT / "completion.json"),
            "not_new_online_learning_independent_repeat_TEST_or_main_method_promotion": True}
        self.check()
        RunStore.immutable_json(OUT / "completion.json", result)
        RunStore.atomic_json(OUT / "progress.json", {"at": now(), "run_id": self.run_id, "state": "completed", **result})


if __name__ == "__main__":
    command = sys.argv[1]
    if command == "prepare":
        prepare()
    elif command == "launch":
        assert not (OUT / "launch.json").exists() and BACKUP.is_file()
        assert read(PARENT / "progress.json")["state"] == "completed"
        argv = [str(ROOT / ".venv/bin/python"), str(Path(__file__).resolve()), "worker"]
        with (OUT / "worker.log").open("xb") as log:
            child = subprocess.Popen(argv, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log,
                stderr=subprocess.STDOUT, start_new_session=True, env={**os.environ, "PYTHONUNBUFFERED": "1"})
        RunStore.immutable_json(OUT / "launch.json", {"at": now(), "pid": child.pid,
            "actual_argv": argv, "background_independent_of_conversation": True})
        print(compact({"run_id": OUT.name, "pid": child.pid}))
    elif command == "worker":
        study = Study()
        try:
            study.execute()
        except BaseException as exc:
            result = {"at": now(), "run_id": OUT.name, "error": repr(exc),
                "actual_new_native_teacher_calls": [len(study.native), 0], "logical_answers": len(study.answers),
                "no_retry_fallback_repair_admission_or_best_bank_selection": True}
            RunStore.immutable_json(OUT / "failure.json", result)
            RunStore.atomic_json(OUT / "progress.json", {"state": "stopped" if isinstance(exc, InterruptedError) else "failed", **result})
            raise
    else:
        raise ValueError("Explicit prepare, launch or worker required")
