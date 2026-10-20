"""Causal online ACE adaptation on public EC/EV, not an evaluated reproduction.

One frozen 8B generator, one native reflection per completed TRAIN task, and one
batch ADD curator. No answer retry, our score gate, fixed numerical prior, best
checkpoint selection or hidden validation split. Common empty controls and all
rejected/failed transport costs remain visible. See the matched-profile protocol.
"""

from __future__ import annotations

import argparse
import copy
import fcntl
import json
import signal
import traceback
from pathlib import Path

from jsonschema import ValidationError, validate

from experiments.openexempt_online import Online, freeze, paired_effect, preserve
from legal_skill_guard.experiment.storage import RunStore, safe_component
from legal_skill_guard.inference.native import WireClient
from legal_skill_guard.learning.experiment import (
    INITIAL_PLAYBOOK,
    Comparison,
    bullets,
    now,
    read,
    sha,
)
from legal_skill_guard.learning.openexempt_ace import (
    commit_additions,
    curator_request,
    decode_generator,
    generator_payload,
    reflector_request,
    validate_reflection,
)
from legal_skill_guard.openexempt import FAMILIES, ROOT, metrics
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha

ROLE_SYSTEM = (
    "Follow the supplied ACE role and exact JSON schema. Use source-supported public "
    "explanations, not private chain of thought. Feedback is released TRAIN only, "
    "never a future/test answer. Do not invent a rollout, repair a recorded prediction, "
    "use tools or propose changes to the verifier, model, interface or experiment.")


def validate_profile(cfg):
    if (cfg.get("learner") != "ace_native_online_v1"
            or cfg.get("execution_contract") != "source_grounded_claim_operations"):
        raise ValueError("Declare this native-role ACE online adaptation")
    if (cfg.get("initial_library_publication") or cfg.get("warm_source_case_ids")
            or cfg.get("ace_capacity_policy") != "error_without_truncation"
            or cfg.get("stop_policy") != "full_stream_or_operator_or_contract_error"):
        raise ValueError("ACE starts empty; declare capacity and full-stream stopping before freeze")
    if cfg["source_cases"] <= 0 or cfg["source_cases"] % cfg["batch_source_cases"]:
        raise ValueError("Whole source-disjoint batches are required")
    lock = Path(cfg["exclusive_training_lock"])
    if not lock.is_absolute() or lock.resolve() != (ROOT / "artifacts/openexempt_training.lock").resolve():
        raise ValueError("Declare the SAME canonical absolute training lock as the main learner")


class ACEOnline:
    check = Comparison.check
    call = Comparison.call
    teacher_call = Comparison.teacher_call
    grade = Online.grade

    def __init__(self, config_path):
        self.cfg = read(config_path)
        validate_profile(self.cfg)
        frozen = read(Path(config_path).with_suffix(".frozen.json"))
        if frozen["config_sha256"] != sha(config_path):
            raise ValueError("Frozen ACE configuration changed")
        self.bindings = frozen["files"]
        self.run_id = safe_component(self.cfg["run_id"])
        self.out = ROOT / "runs" / self.run_id
        if self.out.exists():
            raise FileExistsError("New Run ID required; do not overwrite or resume predictions")
        self.rows = read(ROOT / self.cfg["input_packet"])["rows"]
        keys = [(r["case_id"], r["family"]) for r in self.rows]
        ids = {r["case_id"] for r in self.rows}
        batches = self.cfg["source_cases"] // self.cfg["batch_source_cases"]
        if (len(keys) != len(set(keys)) or len(ids) != self.cfg["source_cases"]
                or set(keys) != {(i, f) for i in ids for f in FAMILIES}
                or {r["batch"] for r in self.rows} != set(range(1, batches + 1))):
            raise ValueError("Exactly paired sources and explicit frozen batches are required")
        for batch in range(1, batches + 1):
            group = [r for r in self.rows if r["batch"] == batch]
            if (len(group) != 2 * self.cfg["batch_source_cases"]
                    or any(len({r["batch"] for r in self.rows if r["case_id"] == i}) != 1
                           for i in {r["case_id"] for r in group})):
                raise ValueError("A source cannot cross TRAIN batches")
        self.playbook = INITIAL_PLAYBOOK
        self.native, self.teachers, self.teacher_attempts = [], [], 0
        self.request_cache, self.reuse_events = {}, []
        self.current_batch, self.stop, self.summaries = 0, False, []
        self.episodes = {arm: [] for arm in ("ace", "empty", "empty_direct_numeric")}
        self.meter = WireClient(self.cfg["generation"])
        self.out.mkdir(parents=True)
        RunStore.immutable_json(self.out / "initialization.json", {
            "playbook": self.playbook, "playbook_sha256": csha(self.playbook),
            "legal_prior_bullets": 0, "published_numerical_programs": 0,
            "profile": "native_per_task_reflection_batch_ADD_curator",
            "not_unmodified_author_defaults_or_a_performance_result": True})
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda *_: setattr(self, "stop", True))
        self.check()
        if not self.meter.readiness()["ready"]:
            raise RuntimeError("Existing frozen executor unavailable; no fallback")
        self.progress("initialized")

    def progress(self, stage, **extra):
        RunStore.atomic_json(self.out / "progress.json", {
            "at": now(), "run_id": self.run_id, "state": "running", "stage": stage,
            "current_batch": self.current_batch, "completed_native_calls": len(self.native),
            "completed_teacher_calls": len(self.teachers), "teacher_attempts": self.teacher_attempts,
            "playbook_bullets": len(bullets(self.playbook)),
            "cross_stage_identical_wire_reuses": len(self.reuse_events), **extra})

    def answer(self, row, stage):
        self.check()
        messages, schema = generator_payload(row, self.playbook)
        path = self.out / "native" / stage / f"{row['case_id']}_{row['family']}_ace.json"
        RunStore.immutable_json(path.with_suffix(".input.json"), {
            "messages": messages, "schema": schema, "playbook_sha256": csha(self.playbook),
            "delivered_bullet_ids": list(bullets(self.playbook)),
            "current_or_future_feedback_available": False})
        response = self.call(path, messages, schema, self.cfg["generation"]["max_tokens"], {
            "stage": stage, "arm": "ace", "document_id": row["case_id"],
            "family": row["family"], "call_role": "openexempt_ace_generator",
            "playbook_sha256": csha(self.playbook)})
        value, decoded, used, rationale, error = None, None, None, None, None
        try:
            if response["finish_reason"] != "stop":
                raise ValueError("Incomplete native ACE output: " + str(response["finish_reason"]))
            value = json.loads(response["content"])
            validate(value, schema)
            if len(value["bullet_ids"]) != len(set(value["bullet_ids"])):
                raise ValueError("Repeated native bullet provenance")
            used, rationale = copy.deepcopy(value["bullet_ids"]), value["reasoning"]
            decoded = decode_generator(row, self.playbook, value)
        except (ValueError, ValidationError) as exc:
            error = repr(exc)
        record = {"case_id": row["case_id"], "source_key": row["source_key"],
            "family": row["family"], "stage": stage, "arm": "ace",
            "playbook_sha256": csha(self.playbook), "parsed": None if decoded is None else
            {"answer": decoded["answer"]}, "parse_error": error,
            "used_bullet_ids": used, "public_rationale": rationale,
            "native_program": None if decoded is None else decoded["native_program"],
            "execution_receipt": None if decoded is None else decoded["execution_receipt"],
            "actual_wrapper_submission": value, "raw_call_path": str(path.relative_to(ROOT))}
        RunStore.immutable_json(path.with_suffix(".answer.json"), record)
        return record

    def update(self, rows, observations, controls):
        parent, reflections = self.playbook, []
        for row, observation in zip(rows, observations, strict=True):
            target = read(ROOT / self.cfg["grading_directory"] /
                          f"{row['case_id']}.json")["targets"][row["family"]]
            view = {**observation, "answer": (observation.get("parsed") or {}).get("answer")}
            key = row["case_id"], row["family"]
            feedback = {"original_score": observation["score"],
                        "same_case_public_control_observations": controls[key],
                        "TRAIN_feedback_never_a_prediction_repair": True}
            prompt, schema, cited = reflector_request(row, view, target, parent, feedback)
            name = f"b{self.current_batch}_{row['case_id']}_{row['family']}_reflector"
            reflection = self.teacher_call(name, ROLE_SYSTEM, prompt, schema)
            validate_reflection(reflection, schema, cited)
            reflections.append(reflection)
        prompt, schema, counted = curator_request(parent, reflections, rows,
            current_step=self.current_batch * self.cfg["batch_source_cases"] * 2,
            total_samples=self.cfg["source_cases"] * 2,
            token_budget=self.cfg["library_token_hard_cap"])
        operations = self.teacher_call(f"b{self.current_batch}_curator", ROLE_SYSTEM, prompt, schema)
        committed = commit_additions(counted, operations, schema,
            token_count=self.meter.token_count, token_budget=self.cfg["library_token_hard_cap"])
        self.check()
        publication = {"at": now(), **committed, "parent_playbook_sha256": csha(parent),
            "playbook_sha256": csha(committed["playbook"]), "actual_ADD_delta": operations,
            "reflections": reflections, "native_counter_semantics": "last_tag_per_ID_in_batch",
            "no_our_score_gate_or_best_bank_selection": True}
        RunStore.immutable_json(self.out / "publications" / f"b{self.current_batch}.json", publication)
        self.playbook = committed["playbook"]
        return publication

    def execute(self):
        batches = self.cfg["source_cases"] // self.cfg["batch_source_cases"]
        for batch in range(1, batches + 1):
            self.current_batch = batch
            current = [r for r in self.rows if r["batch"] == batch]
            records = {arm: [] for arm in self.episodes}
            for row in current:
                arms = ("ace", "empty", "empty_direct_numeric")
                offset = (row["case_id"] + FAMILIES[row["family"]]) % len(arms)
                for arm in arms[offset:] + arms[:offset]:
                    record = (self.answer(row, f"b{batch}_prequential") if arm == "ace" else
                              Online.answer(self, row, [], f"b{batch}_prequential", arm))
                    records[arm].append(record)
            # No current target is opened before every arm/task has a prediction.
            self.grade([r for values in records.values() for r in values])
            RunStore.immutable_json(self.out / "batches" / f"b{batch}_records.json", records)
            summary = {"batch": batch, **{arm: metrics(values) for arm, values in records.items()},
                "ace_minus_empty": paired_effect(records["empty"], records["ace"]),
                "ace_minus_direct_numeric": paired_effect(records["empty_direct_numeric"], records["ace"]),
                "parent_playbook_sha256": csha(self.playbook), "official_test_opened": False}
            RunStore.immutable_json(self.out / "batches" / f"b{batch}_prequential.json", summary)
            controls = {(r["case_id"], r["family"]): {arm: next(x for x in records[arm]
                if (x["case_id"], x["family"]) == (r["case_id"], r["family"]))
                for arm in ("empty", "empty_direct_numeric")} for r in current}
            publication = self.update(current, records["ace"], controls)
            summary["resulting_playbook_sha256"] = publication["playbook_sha256"]
            self.summaries.append(summary)
            for arm, values in records.items():
                self.episodes[arm].extend(values)
            RunStore.atomic_json(self.out / "batch_summary.json", self.summaries)
            self.progress("batch_complete", latest_batch=summary)
        return "completed_declared_ACE_adaptation_stream"

    def run(self):
        state = "failed"
        try:
            state = self.execute()
            RunStore.immutable_json(self.out / "completion.json", {
                "at": now(), "run_id": self.run_id, "status": state,
                "final_playbook": self.playbook, "final_playbook_sha256": csha(self.playbook),
                "batch_summary": self.summaries,
                "prequential": {arm: metrics(values) for arm, values in self.episodes.items()},
                "actual_native_calls": len(self.native), "actual_teacher_responses": len(self.teachers),
                "actual_teacher_attempts": self.teacher_attempts, "raw_wire_reuses": self.reuse_events,
                "native_prompt_tokens": sum((r.get("response") or {}).get("prompt_tokens", 0) for r in self.native),
                "native_completion_tokens": sum((r.get("response") or {}).get("completion_tokens", 0) for r in self.native),
                "not_a_fair_comparison_claim_or_final_TEST_result": True})
        except Exception as exc:
            RunStore.immutable_json(self.out / "failure.json", {
                "at": now(), "error": repr(exc), "traceback": traceback.format_exc(),
                "actual_playbook": self.playbook, "actual_native_calls": len(self.native),
                "actual_teacher_responses": len(self.teachers),
                "actual_teacher_attempts": self.teacher_attempts})
            raise
        finally:
            self.progress("terminal", state=state)
            files = [str(p.relative_to(ROOT)) for p in self.out.rglob("*")
                     if p.is_file() and "/cache/" not in str(p)]
            receipt = preserve(self.run_id, "actual-terminal", files)
            RunStore.immutable_json(self.out / "terminal_preservation.json", receipt)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("freeze", "run"))
    parser.add_argument("config", type=Path)
    args = parser.parse_args()
    config = args.config.resolve()
    cfg = read(config)
    validate_profile(cfg)
    if args.action == "freeze":
        extra = [Path(__file__).resolve(), *ROOT.glob("third_party/ace/prompts/*.py"),
                 ROOT / "third_party/ace/LICENSE.txt", ROOT / "third_party/ace/NOTICE.md"]
        print(json.dumps({"bound_files": len(freeze(config, additional_sources=extra)["files"])}))
    else:
        with Path(cfg["exclusive_training_lock"]).open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            ACEOnline(config).run()


if __name__ == "__main__":
    main()
