"""Atomic legal boundaries learned from same-parent executor observations.

The ordinary evidence tool is shared with the same-data control. No learned
query terms, new model, extra inference stage, answer repair or effect gate.
The final-update ablation changes teacher information, not the published main
library. Local executor text is untrusted data, never teacher hidden reasoning.
"""

from __future__ import annotations

import copy
import importlib.metadata
import json
import os
import pickle
import signal
import sys
import time
from pathlib import Path

import numpy as np
from jsonschema import validate

from legal_skill_guard.experiment.storage import RunStore, safe_component
from legal_skill_guard.inference.codex_cli_client import CodexCLIClient
from legal_skill_guard.inference.native import WireClient
from legal_skill_guard.report import write_report
from legal_skill_guard.task import marked_text, original_feedback
from legal_skill_guard.utils.hashing import canonical_json_sha256

from .audit import close, original_score
from .evidence_programs import (
    SCORER_PARAMETERS,
    evidence_proposals,
    fit_program_model,
    program_solver_messages,
)
from .experiment import ENDPOINTS, ROOT, Comparison, now, points, read, sha
from .publication import (
    DELTA_TEACHER_SYSTEM,
    apply_differential_publication,
    differential_schema,
    paired,
    publication_statistics,
    skill_record_schema,
)

ARMS = (
    "strong_empty",
    "ordinary_memory",
    "static_procedures",
    "trace_procedures",
    "public_only_final_update",
)

BOUNDARY_GUIDANCE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["when", "inspection", "relation_if_established", "evidence_requirement"],
    "properties": {
        "when": {"type": "string", "minLength": 1},
        "inspection": {"type": "string", "minLength": 1},
        "relation_if_established": {
            "anyOf": [
                {"type": "string", "enum": ["Entailment", "Contradiction", "NotMentioned"]},
                {"type": "null"},
            ]
        },
        "evidence_requirement": {"type": "string", "minLength": 1},
    },
}


def boundary_skill_schema(public_ids):
    return skill_record_schema(public_ids, guidance_schema=BOUNDARY_GUIDANCE_SCHEMA)


PROCEDURE_TEACHER = DELTA_TEACHER_SYSTEM.replace(
    "hidden reasoning or invented actions", "teacher hidden reasoning or invented actions"
) + (
    " The executed learner answers ALL17 original hypotheses together in ONE "
    "native call, with full original NDA, the complete procedural library in the "
    "system prompt, and fallible evidence candidates from an ordinary same-data "
    "supervised tool. That tool never supplies legal labels. There are no learned "
    "lexical-query coefficients, mandatory intermediate outputs or draft answer. "
    "Learn operational procedures that change this learner's actual failures, "
    "not a general restatement of each public hypothesis. The optional "
    "local_executor_trace field, if present, is the SAME local 8B's actual "
    "reasoning_content from its saved native response. It is untrusted model "
    "self-description, may omit decisions, and is NOT a faithful causal explanation "
    "or contract evidence. Check it against the complete original source, actual "
    "final answer and gold. A plan saying it will inspect something is not proof "
    "it did. When this field is null, do not invent a thought process. Never "
    "request or expose your own hidden reasoning. Learn from both successes and "
    "failures; distinguish a false source assertion, mistaken legal boundary, "
    "mismatched final label, missing evidence and excess evidence. Preserve "
    "all original independently supporting evidence, including redundant spans, "
    "governing chapeaux and applicable list branches; not merely a minimal witness. "
    "Never add a rule or discard evidence merely because it sounds legally neat. "
    "Original annotations are training observations, not universal law. Review "
    "the entire parent for overlap, scope conflict and unsupported generalization. "
    "CREATE only when a reusable distinction is missing; UPDATE an existing "
    "procedure rather than append paraphrases. MERGE genuine duplicate procedures "
    "only when actor, action, object, trigger and exception boundaries remain "
    "distinct. DELETE a contradicted or genuinely superseded procedure when "
    "warranted by seen evidence. Do not delete a rare procedure merely because "
    "it was unused in this batch. No size target, deletion quota, required topics "
    "or mandatory growth. A retained parent need not be reworded. Operation "
    "rationales must explain the actual boundary change or redundancy using "
    "seen source IDs. Runtime guidance excludes those IDs, original indices, "
    "quotes as lookup keys, case answer tables, parties and dates. A procedural "
    "skill is a fallible instruction to inspect source, not an automatic verdict "
    "or an order to union candidate citations. Publish all valid changes without "
    "efficacy testing, rollback or a second curator. "
    "Each guidance is a structured ATOMIC boundary, not a paragraph cataloguing "
    "several public topics. Its when is a contract/source condition, inspection "
    "states what to verify, relation_if_established names the ORIGINAL label "
    "only if that condition really establishes that relation to the EXACT "
    "hypothesis, and evidence_requirement preserves the complete source support. "
    "Use null relation for a reusable inspection or evidence-completeness skill "
    "that does not itself settle the relation. A prohibition can ENTAIL a negative "
    "hypothesis; a permission does not automatically entail any other hypothesis. "
    "A related action, different actor, missing trigger or absent universal "
    "coverage must not be silently treated as the requested proposition. "
    "Multiple hypothesis IDs are appropriate only when this SAME conditional "
    "inspection or inference actually transfers, not merely because topics are "
    "related. Use separate atomic records for genuinely different conditions "
    "rather than rewriting an entire mixed-topic paragraph. The solver receives "
    "your declared skill IDs next to each exact public hypothesis and its "
    "fallible evidence candidates, while all rule contents remain visible once. "
    "There is no separate planner, semantic router or host legal decision. Do not duplicate "
    "the base task instruction or force one record per hypothesis. "
    "Every supplied response was generated under the EXACT current parent and "
    "ordinary-tool state: all current-batch first encounters and all previous-"
    "batch post-update answers. No success/error-based sampling is performed. "
    "Older raw trajectories under other parents are deliberately not presented "
    "as failures of this parent. Their retained knowledge is the full parent "
    "library; do not invent unprovided cases or delete rare older boundaries "
    "merely because they are absent from this feedback window."
)

STATIC_TEACHER = (
    "Write compact reusable legal document-inspection procedures using ONLY the "
    "supplied public hypotheses and inference contract. No original contracts, "
    "labels, solver outputs, training statistics or experiences are supplied. "
    "Do not invent any. Distinguish support, affirmative opposition and unresolved "
    "issues relative to the exact original hypothesis, including its negation. "
    "Evidence must include all independently supporting original spans, redundant "
    "support and required scope. Skills are fallible instructions, not current "
    "contract facts, verdicts, or mandatory citations. All records are visible "
    "together in one17-hypothesis call. No required topics, types or count. "
    "Avoid redundant paraphrases, document identifiers, dates, original span "
    "indices or answer tables. Return the requested full library within budget. "
    "Each guidance is one structured condition/inspection/relation/evidence "
    "boundary, not a catalogue of unrelated topics. relation_if_established "
    "uses the exact original label only when the source condition establishes "
    "that relation to the exact hypothesis, including its polarity; use null "
    "for an inspection-only skill. No fixed count or mandatory decision rule."
)


def local_executor_trace(unit):
    """Recover only this local response; never a teacher event log or substitute."""
    native = read(unit["raw_artifact"])
    if native["response"] != unit["response"] or len(native["calls"]) != 1:
        raise ValueError("Executor trace/public response identity mismatch")
    wire = native["calls"][0]["response"]
    if wire["id"] != unit["response"]["raw_id"]:
        raise ValueError("Executor trace raw ID mismatch")
    message = wire["choices"][0]["message"]
    if (message.get("content") or "").strip() != unit["response"]["content"]:
        raise ValueError("Executor trace belongs to another public answer")
    trace = message.get("reasoning_content")
    if not isinstance(trace, str) or not trace.strip():
        raise ValueError("Declared local trace unavailable; no invented/empty substitute")
    return {"raw_id": wire["id"], "reasoning_content_verbatim": trace}


def procedure_messages(row, labels, system, bank, proposals):
    # The native grammar still enforces source indices. No long numerical enum
    # is printed as an answer-like array. This is common to ALL new conditions.
    messages, schema = program_solver_messages(
        row,
        labels,
        system,
        proposals,
        guidance=bank,
        show_span_value_enum_in_prompt=False,
    )
    body = json.loads(messages[1]["content"])
    candidate_map = (
        None
        if proposals is None
        else body["learned_source_evidence_tool"].pop("candidate_members_by_hypothesis")
    )
    body["hypotheses"] = {
        key: {
            "original_hypothesis": labels[key]["hypothesis"],
            "original_public_short_description": labels[key]["short_description"],
            "applicable_published_skill_ids": [s["id"] for s in bank if key in s["hypothesis_ids"]],
            "fallible_evidence_candidates": None if candidate_map is None else candidate_map[key],
        }
        for key in labels
    }
    del body["original_public_short_descriptions"]
    body["skill_binding_is_public_metadata_not_a_current_answer_or_semantic_router"] = True
    instruction = (
        " Each hypothesis explicitly names its applicable published skills and "
        "fallible evidence candidates. The complete library remains visible once. "
        "For an atomic skill, independently verify its when condition and scope "
        "against this full original contract before considering its conditional "
        "relation. A non-null relation is NOT a verdict about this contract; null "
        "means inspection guidance, not NotMentioned. Preserve the original "
        "hypothesis polarity. An unrelated rule, empty skill list, empty candidate "
        "list or high membership score never supplies a legal label. Do not union "
        "citations by rule or alter any final answer after generation."
    )
    messages[0]["content"] = messages[0]["content"].replace(
        "\nReusable skills: ", instruction + "\nReusable skills: ", 1
    )
    messages[1]["content"] = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    return messages, schema


class ProcedureStudy(Comparison):
    def __init__(self, config_path, *, run_id=None):
        self.config_path = Path(config_path).resolve()
        self.cfg = read(self.config_path)
        if self.cfg["method"] != "trace_procedural_memory":
            raise ValueError("Explicit trace-procedure method required")
        if (
            self.cfg.get("memory_representation") != "guarded_atomic_boundary_v1"
            or self.cfg.get("teacher_feedback") != "same_parent_current_before_previous_after_v1"
        ):
            raise ValueError("Atomic boundary study requires its own newly frozen config")
        self.run_id = safe_component(run_id or self.cfg["run_id"])
        self.out = ROOT / "runs" / self.run_id
        self.report = ROOT / self.cfg["report_directory"] / self.run_id
        if self.out.exists():
            raise FileExistsError("New Run ID required")
        frozen = read(self.config_path.with_suffix(".frozen.json"))
        if frozen["config_sha256"] != sha(self.config_path):
            raise ValueError("Frozen config differs")
        self.bindings = frozen["files"]
        packet = read(ROOT / self.cfg["input_packet"])
        self.labels, self.training = packet["public_hypotheses"], packet["training"]
        self.future = packet["later_inputs_no_annotation_sets"]
        if (len(self.labels), len(self.training), len(self.future)) != (17, 24, 8):
            raise ValueError("Declared24 TRAIN/8 exposed development required")
        if any(sum(r["batch"] == b for r in self.training) != 6 for b in range(1, 5)):
            raise ValueError("Four batches of six sources required")
        if any("annotation_sets" in r for r in self.future):
            raise ValueError("Development gold in inference packet")
        self.native, self.teachers, self.units, self.shared_units = [], [], [], []
        self.teacher_attempts, self.current_batch, self.stop = 0, 0, False
        self.bank, self.static, self.public_only = [], [], []
        self.versions = {canonical_json_sha256([]): []}
        self.model, self.state = None, None
        self.state_versions, self.before, self.after, self.summaries = {}, {}, {}, []
        self.meter = WireClient(self.cfg["generation"])
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: setattr(self, "stop", True))

    def bank_for(self, arm):
        if arm not in ARMS:
            raise ValueError("Unknown procedural condition")
        return (
            self.bank
            if arm == "trace_procedures"
            else self.static
            if arm == "static_procedures"
            else self.public_only
            if arm == "public_only_final_update"
            else []
        )

    def messages(self, arm, row, bank):
        if bank != self.bank_for(arm):
            raise ValueError("Incorrect actual library")
        state = None if arm == "strong_empty" else self.state
        model = None if state is None else self.model
        proposal = evidence_proposals(model, row, self.labels)
        messages, schema = procedure_messages(
            row, self.labels, self.cfg["bundled_solver_system"], bank, proposal
        )
        return messages, schema, None, {"ordinary_model_state": state, "proposals": proposal}

    def validate_library(self, bank):
        if len({s["id"] for s in bank}) != len(bank):
            raise ValueError("Duplicate skill IDs; no repair")
        for skill in bank:
            validate(skill, boundary_skill_schema(self.labels))
            if len(set(skill["hypothesis_ids"])) != len(skill["hypothesis_ids"]):
                raise ValueError("Duplicate public scope")
        tokens = self.meter.token_count(text=json.dumps(bank, ensure_ascii=False))
        if tokens > self.cfg["library_token_hard_cap"]:
            raise ValueError("Full library exceeds capacity; no pruning or fallback")
        return tokens

    def initial_static(self):
        value = self.teacher_call(
            "static_public_task_only",
            STATIC_TEACHER,
            {
                "public_hypotheses": self.labels,
                "full_library_token_cap": self.cfg["library_token_hard_cap"],
            },
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["library"],
                "properties": {
                    "library": {"type": "array", "items": boundary_skill_schema(self.labels)}
                },
            },
        )
        self.static = value["library"]
        tokens = self.validate_library(self.static)
        RunStore.immutable_json(
            self.out / "static_procedures.json",
            {"library": self.static, "tokens": tokens, "public_task_only": True},
        )

    def observation(self, unit, include_trace):
        proposals = unit["actual_factual_trace"]["proposals"]
        return {
            "stage": unit["stage"],
            "raw_id": unit["response"]["raw_id"],
            "raw_artifact": unit["raw_artifact"],
            "actual_public_response": unit["response"],
            "public_valid": unit["public_valid"],
            "public_error": unit["public_error"],
            "actual_library_sha256": unit["published_library_sha256"],
            "actual_candidates_as_delivered": None
            if proposals is None
            else {k: v["candidates"] for k, v in proposals["by_hypothesis"].items()},
            "original_component_feedback": [
                {
                    "hypothesis_id": q["hypothesis_id"],
                    "label_correct": q["label_correct"],
                    "joint_exact": q["joint_exact"],
                    "missing_original_members": sorted(
                        set(q["gold"]["spans"]) - set((q["prediction"] or {}).get("spans", []))
                    ),
                    "excess_original_members": sorted(
                        set((q["prediction"] or {}).get("spans", [])) - set(q["gold"]["spans"])
                    ),
                }
                for q in unit["queries"]
            ],
            "local_executor_trace": local_executor_trace(unit) if include_trace else None,
        }

    def teacher_cases(self, batch, *, include_trace):
        """Every current/previous case whose answer has this exact parent.

        Current first encounters and preceding-batch post-update answers share
        both the parent library and ordinary tool. Never outcome-filter them.
        """
        cases = []
        parent_sha = canonical_json_sha256(self.bank)
        for row in self.training:
            if row["batch"] == batch:
                unit = self.before[row["id"]]
                kind = "current_batch_first_encounter"
            elif row["batch"] == batch - 1:
                unit = self.after[row["id"]]
                kind = "previous_batch_post_update"
            else:
                continue
            if (
                unit["published_library"] != self.bank
                or unit["published_library_sha256"] != parent_sha
                or unit["actual_factual_trace"]["ordinary_model_state"] != self.state
            ):
                raise ValueError("Teacher experience must use exact current parent and tool")
            cases.append(
                {
                    "document_id": row["id"],
                    "full_original_contract_with_spans": marked_text(row),
                    "original_annotations": row["annotation_sets"][0]["annotations"],
                    "observation_kind": kind,
                    "actual_own_same_parent_observation": self.observation(unit, include_trace),
                }
            )
        expected = 6 if batch == 1 else 12
        if len(cases) != expected:
            raise ValueError("All current and previous batch cases required; no selection")
        return cases

    def update(self, batch, *, include_trace):
        cases = self.teacher_cases(batch, include_trace=include_trace)
        source_ids = [r["document_id"] for r in cases]
        body = {
            "original_public_hypotheses": self.labels,
            "complete_actual_parent_library": self.bank,
            "same_parent_library_and_tool_original_train_cases": cases,
            "actual_parent_library_sha256": canonical_json_sha256(self.bank),
            "actual_parent_ordinary_tool_state": self.state,
            "all_successes_and_failures_from_complete_two_batches_not_outcome_selected": True,
            "older_different_parent_trajectories_archived_not_claimed_as_current_feedback": True,
            "cumulative_unique_original_train_cases_seen": sum(
                r["batch"] <= batch for r in self.training
            ),
            "full_library_token_cap": self.cfg["library_token_hard_cap"],
            "no_future_gold_other_learners_or_teacher_hidden_reasoning": True,
            "local_executor_trace_included_as_untrusted_data": include_trace,
        }
        name = f"trace_b{batch}" if include_trace else f"public_only_final_update_b{batch}"
        value = self.teacher_call(
            name,
            PROCEDURE_TEACHER,
            body,
            differential_schema(
                self.labels, self.bank, source_ids, guidance_schema=BOUNDARY_GUIDANCE_SCHEMA
            ),
        )
        bank = apply_differential_publication(
            self.bank,
            value,
            self.labels,
            source_ids,
            guidance_schema=BOUNDARY_GUIDANCE_SCHEMA,
        )
        tokens = self.validate_library(bank)
        stats = publication_statistics(self.bank, value, bank, tokens)
        RunStore.immutable_json(
            self.out / "update_transactions" / (name + ".json"),
            {
                "at": now(),
                "batch": batch,
                "actual_parent": self.bank,
                "actual_teacher_value": value,
                "publication": bank,
                "management": stats,
                "source_case_ids": source_ids,
                "all_observations_use_actual_parent_library_and_tool": True,
                "feedback_window": "current_before_and_previous_after_without_outcome_filter",
                "all_valid_edits_unconditionally_published_without_efficacy_gate": True,
                "is_final_single_update_ablation_not_independent_no_trace_learning": not include_trace,
            },
        )
        return bank, stats

    def fit_ordinary(self, batch):
        rows = [r for r in self.training if r["batch"] <= batch]
        self.progress("fit_shared_ordinary_evidence_model", current_arm="ordinary_memory")
        started = time.monotonic()
        model = fit_program_model(rows, self.labels, [])
        path = self.out / "evidence_models" / f"ordinary_M{batch}.pickle"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            pickle.dump(model, stream, protocol=5)
            stream.flush()
            os.fsync(stream.fileno())
        manifest = {
            "at": now(),
            "path": str(path),
            "pickle_sha256": sha(path),
            "batch": batch,
            "seen_original_source_ids": [r["id"] for r in rows],
            "original_training_rows_sha256": canonical_json_sha256(rows),
            "parameters": SCORER_PARAMETERS,
            "programs": [],
            "all_nonempty_tool_conditions_share_this_identical_model": True,
            "no_query_coefficients_or_lawyer_weight_updates": True,
            "original_scoring_pairs": len(model.scoring_pairs_),
            "fit_seconds": time.monotonic() - started,
        }
        state = canonical_json_sha256(manifest)
        RunStore.immutable_json(
            path.with_suffix(".manifest.json"), {"state_sha256": state, **manifest}
        )
        self.model, self.state = model, state
        self.state_versions[state] = manifest

    def share_cold(self, unit, arm, row):
        messages, schema, _, trace = self.messages(arm, row, [])
        wire = read(unit["raw_artifact"])["calls"][0]["request"]
        if (
            wire["messages"] != messages
            or wire["response_format"]["json_schema"]["schema"] != schema
        ):
            raise ValueError("Cold sharing requires identical native inputs")
        shared = {
            **unit,
            "arm": arm,
            "actual_factual_trace": trace,
            "shared_exact_cold_answer_no_new_generation": True,
        }
        RunStore.immutable_json(
            self.out / "batch1_before" / arm / f"{row['id']}.shared.json", shared
        )
        self.shared_units.append(shared)
        return shared

    def execute(self):
        self.check()
        RunStore.immutable_json(
            self.out / "launch.json", {"at": now(), "pid": os.getpid(), "argv": sys.argv}
        )
        RunStore.immutable_json(
            self.out / "declaration.json",
            {
                "at": now(),
                "config": self.cfg,
                "frozen_bindings": self.bindings,
                "development_candidate_not_confirmed_improvement": True,
                "local_8b_trace_as_untrusted_training_data_not_teacher_hidden_reasoning": True,
                "ordinary_tool_same_gold_and_weights_all_nonempty_conditions": True,
                "memory_representation": self.cfg["memory_representation"],
                "teacher_feedback": self.cfg["teacher_feedback"],
                "original_hypothesis_binding_without_semantic_router_or_host_verdict": True,
            },
        )
        RunStore.immutable_json(
            self.out / "source_snapshot.json",
            {
                "files": {
                    p: {"sha256": h, "utf8_text": Path(p).read_text()}
                    for p, h in self.bindings.items()
                    if Path(p).suffix in (".py", ".md", ".txt") or Path(p).name == "LICENSE"
                }
            },
        )
        t = self.cfg["teacher"]
        checker = CodexCLIClient(
            model=t["model"],
            executable="/usr/bin/codex",
            cache_root=self.out / "teacher_admin",
            invocation_budget_path=ROOT / t["ledger"],
            max_invocations=t["total_invocation_budget"],
        )
        ready, tr, budget = (
            self.meter.readiness(),
            checker.preflight(),
            checker.invocation_budget_status(),
        )
        RunStore.immutable_json(
            self.out / "readiness.json",
            {
                "native": ready,
                "teacher": tr,
                "budget": budget,
                "runtime_versions": {
                    p: importlib.metadata.version(p)
                    for p in ("numpy", "scipy", "scikit-learn", "lightgbm", "jsonschema")
                },
            },
        )
        if not ready["ready"] or not tr["ready"] or budget["available"] < 6:
            raise RuntimeError("Declared native/teacher unavailable; no substitutes")
        self.initial_static()
        for batch in range(1, 5):
            self.current_batch = batch
            rows = [r for r in self.training if r["batch"] == batch]
            before = {a: [] for a in ("strong_empty", "ordinary_memory", "trace_procedures")}
            for index, row in enumerate(rows):
                if batch == 1:
                    unit = self.collect("batch1_before", "strong_empty", [row], [])[0]
                    before["strong_empty"].append(unit)
                    for arm in ("ordinary_memory", "trace_procedures"):
                        before[arm].append(self.share_cold(unit, arm, row))
                else:
                    order = list(before)
                    offset = (batch + index) % 3
                    for arm in order[offset:] + order[:offset]:
                        before[arm].extend(
                            self.collect(f"batch{batch}_before", arm, [row], self.bank_for(arm))
                        )
                self.before[row["id"]] = before["trace_procedures"][-1]
            if batch == 4:
                # Both teachers see the EXACT same M3 parent and pre-M4 public
                # observations. This branch is never a candidate main library.
                self.public_only, _ = self.update(batch, include_trace=False)
            self.bank, management = self.update(batch, include_trace=True)
            self.versions[canonical_json_sha256(self.bank)] = copy.deepcopy(self.bank)
            self.fit_ordinary(batch)
            after = self.collect(f"batch{batch}_after", "trace_procedures", rows, self.bank)
            self.after.update({u["document_id"]: u for u in after})
            summary = {
                "at": now(),
                "batch": batch,
                "source_ids": [r["id"] for r in rows],
                "before": {a: points(u) for a, u in before.items()},
                "after": {"trace_procedures": points(after)},
                "strong_empty": points(before["strong_empty"]),
                "update_effects": paired(before["trace_procedures"], after),
                "first_encounter_trace_minus_ordinary": paired(
                    before["ordinary_memory"], before["trace_procedures"]
                ),
                "library_management": management,
                "after_is_seen_fit_with_new_gold_not_a_pure_skill_effect": True,
            }
            self.summaries.append(summary)
            RunStore.immutable_json(self.out / f"batch{batch}_summary.json", summary)
            self.audit_native(
                [
                    u
                    for u in self.units + self.shared_units
                    if u["stage"].startswith(f"batch{batch}_")
                ],
                f"batch{batch}",
            )
            write_report(self.out)
            self.progress("batch_complete", completed_batches=batch)
        first = [r for r in self.training if r["batch"] == 1]
        retained = self.collect("retention_b4", "trace_procedures", first, self.bank)
        RunStore.immutable_json(
            self.out / "retention_b4.json",
            {
                "metrics": points(retained),
                "B1_M1_to_M4": paired([self.after[r["id"]] for r in first], retained),
                "never_to_teacher_or_admission": True,
            },
        )
        RunStore.immutable_json(
            self.out / "memory_frozen_before_later.json",
            {
                "at": now(),
                "main_library": self.bank,
                "static_library": self.static,
                "public_only_final_update_library": self.public_only,
                "ordinary_model_state": self.state,
                "last_published_not_best_library": True,
            },
        )
        later = {a: [] for a in ARMS}
        for index, row in enumerate(self.future):
            offset = index % len(ARMS)
            for arm in ARMS[offset:] + ARMS[:offset]:
                later[arm].append(self.answer("later", arm, row, self.bank_for(arm)))
        self.finish(later)

    def audit_native(self, units, name):
        rows, models = {r["id"]: r for r in self.training + self.future}, {}
        for unit in units:
            row = rows[unit["document_id"]]
            state = unit["actual_factual_trace"]["ordinary_model_state"]
            model = None
            if state is not None:
                manifest = self.state_versions[state]
                if sha(manifest["path"]) != manifest["pickle_sha256"]:
                    raise ValueError("Frozen ordinary model changed")
                if state not in models:
                    with Path(manifest["path"]).open("rb") as stream:
                        models[state] = pickle.load(stream)
                model = models[state]
                if model.programs or model.queries:
                    raise ValueError("Unplanned learned-query model")
            proposal = evidence_proposals(model, row, self.labels)
            close(proposal, unit["actual_factual_trace"]["proposals"])
            messages, schema = procedure_messages(
                row,
                self.labels,
                self.cfg["bundled_solver_system"],
                unit["published_library"],
                proposal,
            )
            raw = read(unit["raw_artifact"])
            wire = raw["calls"][0]["request"]
            if (
                wire["messages"] != messages
                or wire["response_format"]["json_schema"]["schema"] != schema
                or raw["response"] != unit["response"]
            ):
                raise ValueError("Native source/library/tool/schema/response mismatch")
            if unit["response"]["finish_reason"] == "stop":
                validate(json.loads(unit["response"]["content"]), schema)
            if "annotation_sets" in row:
                close(
                    original_score(
                        unit["response"],
                        row,
                        row["annotation_sets"][0]["annotations"],
                        list(self.labels),
                    ),
                    unit,
                )
            local_executor_trace(unit)
        RunStore.immutable_json(
            self.out / "audits" / (name + ".json"),
            {
                "at": now(),
                "logical_observations": len(units),
                "original_source_bank_model_wire_schema_score_and_local_trace_identity_verified": True,
            },
        )

    def finish(self, later):
        self.check()
        if (len(self.native), len(self.teachers), len(self.shared_units)) != (130, 6, 12) or any(
            len(v) != 8 for v in later.values()
        ):
            raise ValueError("Complete declared130/6/12 and40 later responses required")
        self.audit_native(self.units + self.shared_units, "complete")
        gold = read(ROOT / self.cfg["grading_only"])["annotations"]
        rows = {r["id"]: r for r in self.future}
        by = {}
        for arm, units in later.items():
            by[arm] = []
            for unit in units:
                row = rows[unit["document_id"]]
                feedback = original_feedback(
                    unit["response"], row, gold[str(row["id"])], list(self.labels)
                )
                close(
                    original_score(unit["response"], row, gold[str(row["id"])], list(self.labels)),
                    feedback,
                )
                scored = {**unit, **feedback}
                RunStore.immutable_json(
                    self.out / "later_scored" / arm / f"{row['id']}.json", scored
                )
                by[arm].append(scored)
        identities = [n["response"]["raw_id"] for n in self.native]
        if len(set(identities)) != 130:
            raise ValueError("Physical response IDs must be unique")
        results = {a: points(u) for a, u in by.items()}
        rng, intervals = np.random.default_rng(self.cfg["bootstrap_seed"]), {}
        for control in (
            "strong_empty",
            "ordinary_memory",
            "static_procedures",
            "public_only_final_update",
        ):
            draws = {e: [] for e in ENDPOINTS}
            for _ in range(self.cfg["bootstrap_draws"]):
                indices = rng.integers(0, 8, 8)
                a, b = (
                    points([by[arm][i] for i in indices]) for arm in ("trace_procedures", control)
                )
                for e in ENDPOINTS:
                    draws[e].append(a[e] - b[e])
            intervals[control] = {
                e: {
                    "point": results["trace_procedures"][e] - results[control][e],
                    "ci95_descriptive_conditional_on_this_one_learning_run": list(
                        map(float, np.quantile(x, [0.025, 0.975]))
                    ),
                }
                for e, x in draws.items()
            }
        done = {
            "at": now(),
            "run_id": self.run_id,
            "new_native_calls": 130,
            "new_teacher_calls": 6,
            "explicit_shared_cold_answers": 12,
            "batches": self.summaries,
            "development": results,
            "paired_trace_minus_control": {
                a: paired(by[a], by["trace_procedures"]) for a in ARMS if a != "trace_procedures"
            },
            "descriptive_source_intervals": intervals,
            "native_usage": {
                k: sum(n["response"][k] for n in self.native)
                for k in ("prompt_tokens", "completion_tokens")
            },
            "teacher_usage": {
                k: sum(t["invocation"]["usage"][k] for t in self.teachers)
                for k in ("input_tokens", "output_tokens", "reasoning_output_tokens")
            },
            "cpu_fit_seconds": sum(s["fit_seconds"] for s in self.state_versions.values()),
            "public_only_final_update_is_one_update_information_ablation_not_full_no_trace_training": True,
            "exposed_development_not_official_test_or_independent_learning_repeat": True,
            "no_current_gold_to_lawyer_no_host_answer_repair_or_library_selection": True,
        }
        RunStore.immutable_json(self.out / "completion.json", done)
        RunStore.immutable_json(self.report / "complete_metrics.json", done)
        write_report(self.out)
        RunStore.atomic_json(
            self.out / "progress.json",
            {
                "at": now(),
                "state": "completed",
                "run_id": self.run_id,
                "completed_native_calls": 130,
                "completed_teacher_calls": 6,
                "completed_batches": 4,
            },
        )
