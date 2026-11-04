"""Build the declared paper-based SkillCommit adaptation, then evaluate it.

Uses the unchanged direct actor, transports and official grader. No admission
or learned-library state from our proposed method enters this construction.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import signal
import time
import traceback
from pathlib import Path

import numpy as np

from experiments.openexempt_online import Online, direct_request_key, freeze, preserve
from legal_skill_guard.experiment.storage import RunStore, safe_component
from legal_skill_guard.inference.native import WireClient
from legal_skill_guard.learning.experiment import Comparison, now, read, sha
from legal_skill_guard.learning.phase_dispatch import PhaseDispatch
from legal_skill_guard.learning.skillcommit import (
    MECHANISM_ROLE,
    PATCH_ROLE,
    PATTERN_ROLE,
    REFERENCE_ROLE,
    DenseEncoder,
    actor_bank,
    decode_teacher_reference,
    leakage_reason,
    mechanism_schema,
    memory,
    memory_text,
    patch_schema,
    pattern_schema,
    reference_schema,
    select_anchor_group,
    select_supported_version,
    solved,
)
from legal_skill_guard.openexempt import FAMILIES, ROOT, evaluate, metrics
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha


def validate_profile(cfg):
    expected = {
        "learner": "skillcommit_paper_adaptation_verified_reference_v2",
        "reference_contract": "one_answer_aware_reference_native_verified_before_patch_v1",
        "memory_language_contract": "English_public_task_and_pinned_encoder_v1",
        "execution_contract": "direct_statutory_claims", "execution_contract_version": 14,
        "source_cases": 128, "batch_source_cases": 16, "planned_batches": 8,
        "no_validation_set": True, "patch_attempts": 3, "pattern_attempts": 3,
        "retrieval_candidates": 4, "reverse_witnesses": 2, "minimum_scope": 2,
        "compatibility_threshold": 2 / 3, "deployment_memories": 4,
        "delivered_library_token_hard_cap": 8192,
        "construction_schedule": "native_per_source_online_independent_EC_EV",
        "success_contract": "native_target_self_score_ceiling_with_empty_case_check",
        "repair_safety_scope_contract": "repair_memory_only_v2",
        "evaluation_is_existing_observed_TEST_supplement": True,
        "independent_repetitions_USER_DEFERRED": True,
    }
    if any(cfg.get(k) != v for k, v in expected.items()):
        raise ValueError("Incomplete or changed SkillCommit paper-adaptation protocol")
    if cfg["generation"]["seed"] != 45 or cfg["generation"]["max_tokens"] != 8192:
        raise ValueError("Retain the same executor seed and output budget")
    if Path(cfg["exclusive_training_lock"]).resolve() != ROOT / "artifacts/openexempt_training.lock":
        raise ValueError("Use the canonical shared inference/training lock")
    if cfg["encoder"]["revision"] != "a5beb1e3e68b9ab74eb54cfd186867f64f240e1a":
        raise ValueError("Bind the declared independent encoder revision")
    if (len(cfg["encoder"]["files_sha256"]) != 6
            or len(cfg["train_packet_sha256"]) != 64):
        raise ValueError("Bind actual encoder and training artifacts before freezing")


class SkillCommit:
    check = Comparison.check
    call = Comparison.call
    teacher_call = Comparison.teacher_call
    answer = Online.answer
    grade = Online.grade

    def __init__(self, config_path):
        self.config_path = Path(config_path).resolve()
        self.cfg = read(self.config_path)
        validate_profile(self.cfg)
        frozen = read(self.config_path.with_suffix(".frozen.json"))
        if frozen["config_sha256"] != sha(self.config_path):
            raise ValueError("Frozen SkillCommit configuration changed")
        self.bindings = frozen["files"]
        self.run_id = safe_component(self.cfg["run_id"])
        self.out = ROOT / "runs" / self.run_id
        if self.out.exists():
            raise FileExistsError("A new Run ID is required; do not overwrite an experiment")
        main = read(ROOT / self.cfg["common_actor_config"])
        for key in ("generation", "input_packet", "grading_directory", "inference_environment",
                    "actor_skill_order", "execution_contract", "execution_contract_version"):
            if self.cfg[key] != main[key]:
                raise ValueError("Common actor or TRAIN input differs: " + key)
        if sha(ROOT / self.cfg["input_packet"]) != self.cfg["train_packet_sha256"]:
            raise ValueError("TRAIN packet changed")
        self.rows = read(ROOT / self.cfg["input_packet"])["rows"]
        if (len(self.rows) != 256 or len({r["source_key"] for r in self.rows}) != 128
                or len({(r["case_id"], r["family"]) for r in self.rows}) != 256
                or {r["batch"] for r in self.rows} != set(range(1, 9))):
            raise ValueError("Require the original complete paired TRAIN128")
        self.native, self.teachers, self.teacher_attempts = [], [], 0
        self.request_cache, self.reuse_events = {}, []
        self.current_batch, self.stop, self.sequence = 0, False, 0
        self.phase, self.started = "construction", time.monotonic()
        self._dispatch = PhaseDispatch(self.cfg,
            environment=read(ROOT / self.cfg["inference_environment"]),
            on_failure=lambda: setattr(self, "stop", True))
        self.answer = self._dispatch.locked_requests(self.answer,
            lambda *args, **kwargs: direct_request_key(self.cfg, *args, **kwargs))
        self.teacher_call = self._dispatch.limited_teacher(self.teacher_call)
        self.meter = WireClient(self.cfg["generation"])
        self.targets, self.ceilings = {}, {}
        self.memories = {f: {} for f in FAMILIES}
        self.patterns, self.residual = ({f: [] for f in FAMILIES} for _ in range(2))
        self.first, self.summaries = [], []
        for path, digest in self.cfg["encoder"]["files_sha256"].items():
            if sha(path) != digest:
                raise ValueError("Pinned semantic encoder changed")
        self.out.mkdir(parents=True)
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: setattr(self, "stop", True))
        self.check()
        if not self.meter.readiness()["ready"]:
            raise RuntimeError("Original frozen 8B service is unavailable")
        self.progress("load_cpu_encoder")
        self.encoder = DenseEncoder(self.cfg["encoder"])
        RunStore.immutable_json(self.out / "initialization.json", {
            "at": now(), "run_id": self.run_id, "initial_memories": [],
            "common_actor_config_sha256": sha(ROOT / self.cfg["common_actor_config"]),
            "execution_dispatch": self._dispatch.receipt(),
            "paper_based_not_author_code": True, "encoder": self.cfg["encoder"],
            "TEST_predictions_and_labels_not_loaded_for_construction": True,
        })

    def progress(self, stage, **extra):
        with self._dispatch.progress_lock:
            RunStore.atomic_json(self.out / "progress.json", {
                "at": now(), "run_id": self.run_id, "state": "running",
                "phase": self.phase, "stage": stage, "current_batch": self.current_batch,
                "completed_native_calls": len(self.native),
                "completed_teacher_calls": len(self.teachers),
                "teacher_attempts": self.teacher_attempts,
                "first_encounter_tasks": len(self.first),
                "active_patterns": {f: len(v) for f, v in self.patterns.items()},
                "residual_patches": {f: len(v) for f, v in self.residual.items()},
                "elapsed_seconds": time.monotonic() - self.started, **extra})
            if stage in ("arrival_complete", "library_frozen_before_TEST", "terminal"):
                print(json.dumps({"at": now(), "stage": stage, "phase": self.phase,
                    "batch": self.current_batch, "first_tasks": len(self.first),
                    "patterns": {f: len(v) for f, v in self.patterns.items()},
                    "residuals": {f: len(v) for f, v in self.residual.items()},
                    "native": len(self.native), "teacher": len(self.teachers), **extra}), flush=True)

    def event(self, role, value):
        self.sequence += 1
        name = f"{self.sequence:06d}_{safe_component(role)}"
        RunStore.immutable_json(self.out / "events" / (name + ".json"), value)
        return name

    def teach(self, role, system, body, schema):
        if self.phase != "construction":
            raise ValueError("No teacher may run after the final library is frozen")
        name = self.event(role + "_request", {"role": role, "body_sha256": csha(body)})
        result = self.teacher_call(name, system, body, schema)
        if len(self.teachers) > self.cfg["planned_teacher_responses_max"]:
            raise ValueError("Declared construction response upper bound exceeded")
        return result

    def reference(self, row):
        key = (row["case_id"], row["family"])
        if key not in self.targets:
            value = read(ROOT / self.cfg["grading_directory"] /
                         f"{row['case_id']}.json")["targets"][row["family"]]
            self.targets[key] = value
            self.ceilings[key] = evaluate(row, value, value)["f1"]
        return self.targets[key]

    def passes(self, record):
        return solved(record, self.ceilings[(record["case_id"], record["family"])])

    def replay(self, item, rows, purpose):
        label = self.event("replay", {"purpose": purpose, "memory": item,
            "source_ids": [r["case_id"] for r in rows]})
        bank = actor_bank([item])
        self.check_delivery(bank)
        answers = self._dispatch.native(
            lambda row: self.answer(row, bank, label, "skillcommit_replay"), rows)
        self.grade(answers)
        result = [{**r, "passed": self.passes(r)} for r in answers]
        RunStore.immutable_json(self.out / "replays" / (label + ".json"), result)
        return result

    def check_delivery(self, bank):
        tokens = self.meter.token_count(text=json.dumps(bank, ensure_ascii=False,
                                                       separators=(",", ":")))
        if tokens > self.cfg["delivered_library_token_hard_cap"]:
            raise ValueError("Selected complete memories exceed capacity; no text clipping")
        return tokens

    def deploy(self, row):
        family = row["family"]
        pool = [self.memories[family][i] for i in self.patterns[family] + self.residual[family]]
        ranked = self.encoder.rank(row["prompt"], pool, self.cfg["deployment_memories"])
        bank = actor_bank([m for _, m in ranked])
        count = self.check_delivery(bank)
        return bank, {"memory_ids": [m["id"] for _, m in ranked],
                      "similarities": [score for score, _ in ranked], "tokens": count,
                      "query_is_original_public_prompt_only": True}

    def teacher_reference(self, row, first, original_input):
        """One training-only reference; no unverified-reference substitution."""
        response = self.teach("reference", REFERENCE_ROLE, {
            "original_public_task_messages": original_input["messages"],
            "original_public_answer_schema": original_input["schema"],
            "released_TRAIN_reference": self.reference(row),
            "actual_failed_answer": first["parsed"],
            "actual_failed_public_output": read(ROOT / first["raw_call_path"])["response"]["content"],
            "actual_parse_error": first["parse_error"],
            "reference_is_training_only_and_never_deployed": True,
        }, reference_schema(original_input["schema"]))
        record = {"case_id": row["case_id"], "source_key": row["source_key"],
                  "family": row["family"], "parse_error": None,
                  "parsed": decode_teacher_reference(row["family"], response["reference_answer"],
                                                     original_input),
                  "public_label_submission": response["reference_answer"]}
        self.grade([record])
        record["passed"] = self.passes(record)
        self.event("teacher_reference_validation", {"reference": response,
            "actual_verification": record, "not_a_native_executor_generation": True,
            "no_reference_or_target_rendered_to_replay": True})
        if not record["passed"]:
            self.event("unverified_reference_skip_patch", {"case_id": row["case_id"],
                "family": row["family"], "actual_verification": record,
                "no_semantic_regeneration_or_gold_substitution": True})
            return None
        return {"reference": response, "actual_verification": record}

    def patch(self, row, first):
        target = self.reference(row)
        parent_input = self.out / "native" / "first_forecasts" / (
            f"{row['case_id']}_{row['family']}_skillcommit.input.json")
        original_input = read(parent_input)
        verified_reference = self.teacher_reference(row, first, original_input)
        if verified_reference is None:
            return None
        replay_feedback, previous = None, None
        for attempt in range(1, self.cfg["patch_attempts"] + 1):
            response = self.teach("patch", PATCH_ROLE, {
                "original_public_task_messages": original_input["messages"],
                "original_public_answer_schema": original_input["schema"],
                "released_TRAIN_reference": target,
                "native_verifier_accepted_teacher_reference": verified_reference,
                "actual_failed_answer": first["parsed"],
                "actual_failed_public_output": read(ROOT / first["raw_call_path"])["response"]["content"],
                "actual_parse_error": first["parse_error"], "native_score": first["score"],
                "attempt": attempt, "previous_patch": previous,
                "latest_actual_source_replay": replay_feedback,
                "reference_is_training_only": True,
            }, patch_schema())
            if not response["repairable"]:
                self.event("patch_abstain", {"case_id": row["case_id"],
                    "family": row["family"], "attempt": attempt, "response": response})
                return None
            previous = response
            reason = ("author_reports_instance_solution" if response["contains_instance_solution"]
                      else leakage_reason(response["repair_memory"], row, target))
            if not response["repair_memory"].strip():
                reason = "empty_repair"
            if reason:
                replay_feedback = {"rejected_before_replay": reason}
                self.event("patch_leakage_reject", {"case_id": row["case_id"],
                    "family": row["family"], "attempt": attempt, "reason": reason})
                continue
            item = memory(row["family"], "patch", {
                "when": "Use this repair only when its stated factual and legal conditions apply.",
                "repair": response["repair_memory"],
                "avoid_when": "Do not apply outside the repair's stated conditions or exceptions.",
            }, [row["case_id"]])
            replay_feedback = self.replay(item, [row], "local_patch_validation")[0]
            if replay_feedback["passed"]:
                self.memories[row["family"]][item["id"]] = item
                self.residual[row["family"]].append(item["id"])
                self.event("patch_admitted", {"memory": item, "attempt": attempt,
                    "actual_validation": replay_feedback})
                return item
        return None

    def mechanism(self, members, incoming, *, expansion):
        ordered = [m for m in members if m["id"] != incoming["id"]] + [incoming]
        labels = {f"M{i}": m for i, m in enumerate(ordered)}
        response = self.teach("mechanism", MECHANISM_ROLE, {
            "mode": "expand_parent" if expansion else "form_root",
            "anonymous_memories": {k: memory_text(v) for k, v in labels.items()},
            "incoming_member": list(labels)[-1], "already_replay_supported": True,
        }, mechanism_schema(labels))
        selected = response["selected_members"]
        if len(selected) != len(set(selected)) or not set(selected) <= set(labels):
            raise ValueError("Invalid mechanism member selection")
        if not response["same_mechanism"]:
            return None
        if (list(labels)[-1] not in selected or len(selected) < self.cfg["minimum_scope"]
                or (expansion and set(selected) != set(labels))):
            self.event("mechanism_abstain", {"response": response,
                "reason": "no_supported_incoming_containing_mechanism"})
            return None
        if not response["shared_mechanism"].strip():
            raise ValueError("A positive mechanism assessment needs its shared procedure")
        return [labels[k] for k in selected], response["shared_mechanism"]

    def consolidate(self, family, members, mechanism, *, parent=None):
        sources = sorted({i for m in members for i in m["sources"]})
        rows = [next(r for r in self.rows if r["case_id"] == i and r["family"] == family)
                for i in sources]
        versions, previous, feedback = [], None, None
        for attempt in range(1, self.cfg["pattern_attempts"] + 1):
            description = self.teach("pattern", PATTERN_ROLE, {
                "anonymous_memory_texts": [memory_text(m) for m in members],
                "shared_execution_mechanism": mechanism,
                "previous_candidate": previous,
                "anonymous_actual_replay_feedback": feedback,
                "attempt": attempt, "fixed_source_count": len(rows),
                "no_source_questions_targets_or_identity": True,
            }, pattern_schema())
            item = memory(family, "pattern", description, sources,
                          parent=parent["id"] if parent else None)
            answers = self.replay(item, rows, "full_scope_abstraction_validation")
            support = [r["case_id"] for r in answers if r["passed"]]
            version = {"attempt": attempt, "memory": item, "supported_sources": support}
            versions.append(version)
            if len(support) == len(rows):
                return self.commit(family, item, members, parent=parent, split=False)
            previous = description
            feedback = [{"anonymous_source": f"S{i}", "passed": r["passed"],
                "native_f1": r["score"]["f1"], "parse_error": r["parse_error"],
                "public_model_submission": r["public_label_submission"]}
                for i, r in enumerate(answers)]
        selected = select_supported_version(versions, self.cfg["minimum_scope"])
        if selected is None:
            self.event("abstraction_rejected", {"family": family, "versions": versions})
            return False
        support = selected["supported_sources"]
        narrowed = memory(family, "pattern", selected["memory"]["description"], support,
                          parent=parent["id"] if parent else None)
        narrowed_rows = [r for r in rows if r["case_id"] in support]
        checked = self.replay(narrowed, narrowed_rows, "split_scope_revalidation")
        if not all(r["passed"] for r in checked):
            self.event("split_rejected", {"family": family, "selected": selected,
                "actual_revalidation": checked})
            return False
        return self.commit(family, narrowed, members, parent=parent, split=True)

    def commit(self, family, item, members, *, parent, split):
        if parent and not split:
            self.patterns[family].remove(parent["id"])
        self.memories[family][item["id"]] = item
        if item["id"] not in self.patterns[family]:
            self.patterns[family].append(item["id"])
        covered = set(item["sources"])
        for member in members:
            if (member["id"] in self.residual[family]
                    and set(member["sources"]) <= covered):
                self.residual[family].remove(member["id"])
        self.event("pattern_split" if split else "pattern_commit", {
            "memory": item, "parent": parent, "members": [m["id"] for m in members],
            "active_patterns": self.patterns[family], "residual_patches": self.residual[family]})
        return True

    def consider(self, incoming):
        family, case_id = incoming["family"], incoming["sources"][0]
        source = next(r for r in self.rows if r["case_id"] == case_id and r["family"] == family)
        candidates = [self.memories[family][i] for i in self.patterns[family]]
        for similarity, parent in self.encoder.rank(memory_text(incoming), candidates,
                                                    self.cfg["retrieval_candidates"]):
            witnesses = parent["sources"][:self.cfg["reverse_witnesses"]]
            prior_rows = [next(r for r in self.rows if r["case_id"] == i and r["family"] == family)
                          for i in witnesses]
            forward = self.replay(parent, [source], "active_parent_on_incoming")
            reverse = self.replay(incoming, prior_rows, "incoming_patch_on_parent_witnesses")
            compatibility = sum(r["passed"] for r in forward + reverse) / (1 + len(reverse))
            self.event("active_compatibility", {"parent_id": parent["id"],
                "incoming_id": incoming["id"], "similarity": similarity,
                "witness_sources": witnesses, "compatibility": compatibility})
            if compatibility + 1e-12 < self.cfg["compatibility_threshold"]:
                continue
            assessed = self.mechanism([parent, incoming], incoming, expansion=True)
            if assessed and self.consolidate(family, *assessed, parent=parent):
                return
        neighbors = [self.memories[family][i] for i in self.residual[family]
                     if i != incoming["id"]]
        ranked = self.encoder.rank(memory_text(incoming), neighbors,
                                   self.cfg["retrieval_candidates"])
        if not ranked:
            return
        pool = [incoming, *[m for _, m in ranked]]
        transfers = {}
        for origin in pool:
            others = [m for m in pool if m["id"] != origin["id"]]
            rows = [next(r for r in self.rows if r["case_id"] == m["sources"][0]
                         and r["family"] == family) for m in others]
            result = self.replay(origin, rows, "residual_directed_cross_replay")
            for destination, answer in zip(others, result, strict=True):
                transfers[(origin["id"], destination["id"])] = answer["passed"]
        chosen = select_anchor_group(incoming["id"], [m["id"] for _, m in ranked], transfers,
                                     {m["id"]: s for s, m in ranked})
        if chosen is None:
            return
        members = [self.memories[family][i] for i in chosen["members"]]
        self.event("root_compatibility", {**chosen, "incoming_id": incoming["id"],
            "transfers": [{"from": a, "to": b, "passed": v}
                          for (a, b), v in transfers.items()]})
        assessed = self.mechanism(members, incoming, expansion=False)
        if assessed:
            selected_ids = [m["id"] for m in assessed[0]]
            if any(all(a == b or transfers.get((a, b), False) for b in selected_ids)
                   for a in selected_ids):
                self.consolidate(family, *assessed)
            else:
                self.event("mechanism_subset_without_anchor", {
                    "selected_members": selected_ids, "no_unverified_root_published": True})

    def snapshot(self):
        return {f: {"active_patterns": [self.memories[f][i] for i in self.patterns[f]],
                    "residual_patches": [self.memories[f][i] for i in self.residual[f]]}
                for f in FAMILIES}

    def build(self):
        for index, row in enumerate(self.rows, 1):
            self.current_batch = row["batch"]
            bank, delivery = self.deploy(row)
            first = self.answer(row, bank, "first_forecasts", "skillcommit")
            # Labels are first loaded only after this task's actual forecast.
            self.reference(row)
            self.grade([first])
            self.first.append(first)
            RunStore.immutable_json(self.out / "forecasts" /
                f"{row['case_id']}_{row['family']}.json", {"record": first, "delivery": delivery})
            if not self.passes(first):
                admitted = self.patch(row, first)
                if admitted:
                    self.consider(admitted)
            self.event("arrival_complete", {"case_id": row["case_id"], "family": row["family"],
                "first_native_f1": first["score"]["f1"], "library_sha256": csha(self.snapshot())})
            self.progress("arrival_complete", completed_TRAIN_tasks=index)
            if index % 32 == 0:
                summary = {"batch": self.current_batch, "first_encounter_metrics":
                    metrics([r for r in self.first if r["case_id"] in {
                        x["case_id"] for x in self.rows if x["batch"] == self.current_batch}]),
                    "library": self.snapshot(), "actual_native_calls": len(self.native),
                    "actual_teacher_responses": len(self.teachers)}
                self.summaries.append(summary)
                RunStore.immutable_json(self.out / "batches" / f"b{self.current_batch}.json", summary)
                RunStore.atomic_json(self.out / "batch_summary.json", self.summaries)
        final = self.snapshot()
        publication = {"at": now(), "library": final, "library_sha256": csha(final),
            "train_sources": 128, "completed_training_tasks": len(self.first),
            "no_TEST_loaded_during_build": True, "cost": self.cost(),
            "method": "SkillCommit-paper-adaptation", "not_author_code": True}
        RunStore.immutable_json(self.out / "publications/final.json", publication)
        RunStore.immutable_json(self.out / "build_completion.json", {
            "status": "completed_skillcommit_paper_adaptation_build", **publication,
            "first_encounter_metrics": metrics(self.first)})
        self.phase = "frozen_evaluation"
        self.progress("library_frozen_before_TEST")
        return publication

    def cost(self):
        usages = [r.get("invocation", {}).get("usage") for r in self.teachers]
        unknown = sum(not isinstance(v, dict) for v in usages)
        def teacher_total(field):
            return None if unknown else sum(v.get(field, 0) for v in usages)
        return {
            "actual_native_generations": len(self.native),
            "native_input_tokens": sum((r.get("response") or {}).get("prompt_tokens", 0)
                                       for r in self.native),
            "native_output_tokens": sum((r.get("response") or {}).get("completion_tokens", 0)
                                        for r in self.native),
            "actual_teacher_responses": len(self.teachers), "teacher_attempts": self.teacher_attempts,
            "teacher_input_tokens": teacher_total("input_tokens"),
            "teacher_output_tokens": teacher_total("output_tokens"),
            "teacher_cached_input_tokens_subset": teacher_total("cached_input_tokens"),
            "teacher_reasoning_output_tokens_subset": teacher_total("reasoning_output_tokens"),
            "successful_teacher_usage_records_missing": unknown,
            "unsuccessful_teacher_attempts_usage_not_assumed_zero":
                self.teacher_attempts - len(self.teachers),
            "exact_request_reuses": len(self.reuse_events),
            "elapsed_seconds": time.monotonic() - self.started,
        }

    def evaluate(self, publication):
        if csha(self.snapshot()) != publication["library_sha256"]:
            raise ValueError("Actual final library changed")
        packet = ROOT / self.cfg["evaluation_input_packet"]
        if sha(packet) != self.cfg["evaluation_packet_sha256"]:
            raise ValueError("Existing frozen TEST packet changed")
        test_rows = read(packet)["rows"]
        if (len(test_rows) != 256 or len({r["source_key"] for r in test_rows}) != 128
                or {r["source_key"] for r in self.rows} & {r["source_key"] for r in test_rows}):
            raise ValueError("Require the same 128 source-disjoint TEST cases")
        self.rows = [*self.rows, *test_rows]
        build_native, teacher_count = len(self.native), len(self.teachers)
        self.current_batch = 0
        self.event("evaluation_started", {"final_library_sha256": publication["library_sha256"],
            "packet_sha256": sha(packet), "existing_previously_observed_TEST_supplement": True})
        def predict(row):
            bank, delivery = self.deploy(row)
            answer = self.answer(row, bank, "frozen_TEST", "skillcommit")
            RunStore.immutable_json(self.out / "TEST_delivery" /
                f"{row['case_id']}_{row['family']}.json", delivery)
            return answer
        predictions = self._dispatch.native(predict, test_rows)
        RunStore.immutable_json(self.out / "TEST_predictions_before_grading.json", predictions)
        if len(self.teachers) != teacher_count or csha(self.snapshot()) != publication["library_sha256"]:
            raise ValueError("A frozen evaluation cannot update memory or call a teacher")
        old_grade = self.cfg["grading_directory"]
        self.cfg["grading_directory"] = self.cfg["evaluation_grading_directory"]
        try:
            self.grade(predictions)
        finally:
            self.cfg["grading_directory"] = old_grade
        RunStore.immutable_json(self.out / "TEST_scored_records.json", predictions)
        return {"metrics": metrics(predictions), "test_native_generations": len(self.native) - build_native,
                "teacher_calls_during_test": 0, "paired_existing_main": self.paired(predictions)}

    def paired(self, records):
        # The old scores are loaded only after construction and all new forecasts.
        old = read(ROOT / self.cfg["existing_scored_records"])
        if isinstance(old, dict):
            old = old["utility45"]
        source_order = sorted({r["source_key"] for r in records})
        own = {(r["source_key"], r["family"]): r["score"]["f1"] for r in records}
        main = {(r["source_key"], r["family"]): r["score"]["f1"] for r in old
                if r.get("arm") == "utility45" or r.get("condition") == "utility45"}
        if set(own) != set(main):
            raise ValueError("The old and new scored source grids differ")
        rng = np.random.default_rng(self.cfg["paired_bootstrap_seed"])
        indices = rng.integers(0, len(source_order), size=(20000, len(source_order)))
        result = {"direction": "existing_main_minus_SkillCommit_adaptation",
            "analysis": "posthoc_existing_TEST_supplement_not_original_18_endpoint_family",
            "conditional_on_actual_frozen_libraries_not_independent_build_variance": True}
        for family in FAMILIES:
            differences = np.array([main[(s, family)] - own[(s, family)] for s in source_order])
            draws = differences[indices].mean(axis=1)
            result[family] = {"delta_pp": float(differences.mean() * 100),
                "ordinary95_pp": (np.quantile(draws, [.025, .975]) * 100).tolist(),
                "two_endpoint_fwer95_pp": (np.quantile(draws, [.0125, .9875]) * 100).tolist()}
        return result

    def run(self):
        state = "failed"
        try:
            publication = self.build()
            evaluation = self.evaluate(publication)
            state = "completed_skillcommit_existing_TEST_supplement"
            RunStore.immutable_json(self.out / "completion.json", {
                "at": now(), "status": state, "run_id": self.run_id,
                "library_sha256": publication["library_sha256"], **evaluation,
                "build_cost": publication["cost"], "total_build_and_TEST_cost": self.cost(),
                "retired_implementation_attempt": self.cfg.get("retired_implementation_attempt")})
        except Exception as exc:
            RunStore.immutable_json(self.out / "failure.json", {"at": now(),
                "error": repr(exc), "traceback": traceback.format_exc(),
                "phase": self.phase, "actual_library": self.snapshot(), "cost": self.cost()})
            raise
        finally:
            self.progress("terminal", state=state)
            names = [str(p.relative_to(ROOT)) for p in self.out.rglob("*")
                     if p.is_file() and "/cache/" not in str(p)]
            receipt = preserve(self.run_id, "actual-terminal", names)
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
        additional = [Path(__file__).resolve(), ROOT / cfg["common_actor_config"],
            ROOT / cfg["existing_scored_records"], ROOT / cfg["paper_source"]]
        additional.extend((ROOT / cfg["evaluation_input_packet"]).parent.rglob("*.json"))
        if cfg.get("retired_implementation_attempt"):
            previous = ROOT / "runs" / cfg["retired_implementation_attempt"]["run_id"]
            additional.extend([previous / "failure.json", previous / "terminal_preservation.json"])
        print(json.dumps({"bound_files": len(freeze(config, additional_sources=additional)["files"])}))
    else:
        with Path(cfg["exclusive_training_lock"]).open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            SkillCommit(config).run()


if __name__ == "__main__":
    main()
