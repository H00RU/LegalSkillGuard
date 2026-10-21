"""Causal online ACE adaptation on public EC/EV, not an evaluated reproduction.

One frozen 8B generator, native TRAIN reflection/regeneration, and one batch ADD
curator. First-encounter scores never use these labeled TRAIN regenerations.
No inference fallback, our score gate, fixed numerical prior, best checkpoint
selection or hidden validation split. All actual costs remain visible.
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
from legal_skill_guard.learning.ace_native import update_bullet_counts
from legal_skill_guard.learning.experiment import (
    INITIAL_PLAYBOOK,
    Comparison,
    bullets,
    now,
    read,
    sha,
)
from legal_skill_guard.learning.legal_namespace import public_asset_catalog
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
    "never a future/test answer. Do not invent a rollout or rewrite an original forecast, "
    "use tools or propose changes to the verifier, model, interface or experiment.")


def validate_profile(cfg):
    if (cfg.get("learner") != "ace_native_online_v2"
            or cfg.get("execution_contract") not in (
                "source_grounded_claim_operations", "direct_statutory_claims")):
        raise ValueError("Declare this native-role ACE online adaptation")
    rounds = cfg.get("ace_max_TRAIN_reflection_rounds")
    if type(rounds) is not int or rounds < 1 or rounds > 3:
        raise ValueError("Declare one to three native TRAIN reflection/regeneration rounds")
    if (cfg["execution_contract"] == "direct_statutory_claims"
            and cfg.get("execution_contract_version") not in (13, 14)):
        raise ValueError("Direct ACE must declare the common answer contract v13 or v14")
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
            "execution_contract": self.cfg["execution_contract"],
            "profile": "native_TRAIN_reflect_regenerate_batch_ADD_curator",
            "max_TRAIN_reflection_rounds": self.cfg["ace_max_TRAIN_reflection_rounds"],
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

    def answer(self, row, stage, *, playbook=None, training_reflection=None, training=False):
        self.check()
        if training_reflection is not None and not training:
            raise ValueError("Released feedback is forbidden in first-encounter inference")
        book = self.playbook if playbook is None else playbook
        direct = self.cfg["execution_contract"] == "direct_statutory_claims"
        asset_references = self.cfg.get("execution_contract_version") == 14
        messages, schema = generator_payload(row, book, direct_numeric=direct,
            training_reflection=training_reflection, asset_references=asset_references)
        fingerprint = csha({"messages": messages, "schema": schema,
                            "generation": self.cfg["generation"]})
        path = self.out / "native" / stage / f"{row['case_id']}_{row['family']}_ace.json"
        RunStore.immutable_json(path.with_suffix(".input.json"), {
            "messages": messages, "schema": schema, "playbook_sha256": csha(book),
            "delivered_bullet_ids": list(bullets(book)), "TRAIN_only": training,
            "valuation_output_contract": "direct_numeric" if direct else "inline_claim_program",
            "current_TRAIN_reflection_available": training_reflection is not None,
            **({"public_asset_reference_catalog": public_asset_catalog(row)}
               if asset_references else {}),
            "future_or_TEST_feedback_available": False})
        alias = None
        raw_call_path = str(path.relative_to(ROOT))
        if fingerprint in self.request_cache:
            original = self.request_cache[fingerprint]
            response = copy.deepcopy(original["response"])
            raw_call_path = original["raw_call_path"]
            alias = {"fingerprint": fingerprint, "raw_call_path": raw_call_path,
                     "not_an_independent_generation": True}
            self.reuse_events.append({"stage": stage, "case_id": row["case_id"],
                "family": row["family"], "arm": "ace", **alias})
        else:
            response = self.call(path, messages, schema, self.cfg["generation"]["max_tokens"], {
                "stage": stage, "arm": "ace", "document_id": row["case_id"],
                "family": row["family"], "call_role": "openexempt_ace_generator",
                "TRAIN_only": training, "training_reflection": training_reflection is not None,
                "playbook_sha256": csha(book)})
            self.request_cache[fingerprint] = {"response": copy.deepcopy(response),
                                              "raw_call_path": raw_call_path}
        value, decoded, used, rationale, error = None, None, None, None, None
        try:
            if response["finish_reason"] != "stop":
                raise ValueError("Incomplete native ACE output: " + str(response["finish_reason"]))
            value = json.loads(response["content"])
            validate(value, schema)
            if len(value["bullet_ids"]) != len(set(value["bullet_ids"])):
                raise ValueError("Repeated native bullet provenance")
            used, rationale = copy.deepcopy(value["bullet_ids"]), value["reasoning"]
            decoded = decode_generator(row, book, value, direct_numeric=direct,
                                        asset_references=asset_references)
        except (ValueError, ValidationError) as exc:
            error = repr(exc)
        record = {"case_id": row["case_id"], "source_key": row["source_key"],
            "family": row["family"], "stage": stage, "arm": "ace",
            "playbook_sha256": csha(book), "TRAIN_only": training,
            "parsed": None if decoded is None else
            {"answer": decoded["answer"]}, "parse_error": error,
            "used_bullet_ids": used, "public_rationale": rationale,
            "native_program": None if decoded is None else decoded["native_program"],
            "execution_receipt": None if decoded is None else decoded["execution_receipt"],
            "actual_wrapper_submission": value, "raw_call_path": raw_call_path}
        if alias is not None:
            record["physical_alias_of_identical_wire"] = alias
        RunStore.immutable_json(path.with_suffix(".answer.json"), record)
        return record

    @staticmethod
    def train_solved(record):
        score = record["score"]
        return (record["parse_error"] is None and not score["invalid_format"]
                and score["full_output_claim_fp"] == 0
                and score["full_output_claim_fn"] == 0)

    def update(self, rows, observations, controls):
        parent, reflections, all_tags, trajectories = self.playbook, [], [], []
        for row, observation in zip(rows, observations, strict=True):
            # The complete first-encounter batch is already immutable. The native
            # TRAIN-initial call is identical under this fixed-seed profile and
            # may reuse that raw wire; it is still freshly decoded and scored.
            prediction = self.answer(row, f"b{self.current_batch}_TRAIN_initial",
                                     playbook=parent, training=True)
            self.grade([prediction])
            target = read(ROOT / self.cfg["grading_directory"] /
                          f"{row['case_id']}.json")["targets"][row["family"]]
            key = row["case_id"], row["family"]
            local_book, rounds = parent, []
            initially_solved = self.train_solved(prediction)
            limit = 1 if initially_solved else self.cfg["ace_max_TRAIN_reflection_rounds"]
            for number in range(1, limit + 1):
                view = {**prediction, "answer": (prediction.get("parsed") or {}).get("answer")}
                feedback = {"original_score": prediction["score"],
                    "same_case_public_control_observations": controls[key],
                    "first_encounter_score_never_replaced": observation["score"],
                    "TRAIN_feedback_never_a_prediction_repair": True}
                prompt, schema, cited = reflector_request(row, view, target, local_book, feedback,
                    direct_numeric=self.cfg["execution_contract"] == "direct_statutory_claims",
                    asset_references=self.cfg.get("execution_contract_version") == 14)
                name = f"b{self.current_batch}_{row['case_id']}_{row['family']}_r{number}_reflector"
                reflection = self.teacher_call(name, ROLE_SYSTEM, prompt, schema)
                validate_reflection(reflection, schema, cited)
                all_tags.extend(reflection["bullet_tags"])
                current = {"round": number, "teacher_role": name,
                           "actual_pre_reflection_score": prediction["score"],
                           "reflection": reflection}
                if initially_solved:
                    rounds.append(current)
                    break
                if reflection["bullet_tags"]:
                    local_book = update_bullet_counts(local_book, reflection["bullet_tags"])
                prediction = self.answer(row, f"b{self.current_batch}_TRAIN_round{number}",
                    playbook=local_book, training_reflection=reflection, training=True)
                self.grade([prediction])
                current.update({"regenerated_prediction": prediction,
                                "solved_after_TRAIN_regeneration": self.train_solved(prediction)})
                rounds.append(current)
                if self.train_solved(prediction):
                    break
            reflections.append(reflection)
            trajectory = {"source_case_id": row["case_id"], "family": row["family"],
                "initial_first_encounter_observation": observation,
                "TRAIN_initially_solved": initially_solved, "rounds": rounds,
                "TRAIN_final_prediction": prediction,
                "TRAIN_finally_solved": self.train_solved(prediction),
                "TRAIN_only_not_replacement_or_generalization": True}
            RunStore.immutable_json(self.out / "training" /
                f"b{self.current_batch}_{row['case_id']}_{row['family']}.json", trajectory)
            trajectories.append(trajectory)
        prompt, schema, counted = curator_request(parent, reflections, rows,
            current_step=self.current_batch * self.cfg["batch_source_cases"] * 2,
            total_samples=self.cfg["source_cases"] * 2,
            token_budget=self.cfg["library_token_hard_cap"],
            direct_numeric=self.cfg["execution_contract"] == "direct_statutory_claims",
            asset_references=self.cfg.get("execution_contract_version") == 14,
            all_round_bullet_tags=all_tags)
        operations = self.teacher_call(f"b{self.current_batch}_curator", ROLE_SYSTEM, prompt, schema)
        committed = commit_additions(counted, operations, schema,
            token_count=self.meter.token_count, token_budget=self.cfg["library_token_hard_cap"])
        self.check()
        publication = {"at": now(), **committed, "parent_playbook_sha256": csha(parent),
            "playbook_sha256": csha(committed["playbook"]), "actual_ADD_delta": operations,
            "reflections": reflections, "actual_TRAIN_trajectories": trajectories,
            "native_counter_semantics": "last_tag_per_ID_in_batch_all_TRAIN_rounds",
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
