"""Task-local skill presentation and bounded, original-Gold online feedback.

All public hypotheses share one full-source context. Public scope is structural
metadata, not a semantic router or a proof of internal content isolation.
"""

from __future__ import annotations

import copy
import importlib.metadata
import json
import os
import pickle
import signal
import sys
import zipfile
from pathlib import Path

import numpy as np
from jsonschema import validate

from legal_skill_guard.experiment.storage import RunStore, safe_component
from legal_skill_guard.data import source_components
from legal_skill_guard.inference.codex_cli_client import CodexCLIClient
from legal_skill_guard.inference.native import WireClient
from legal_skill_guard.report import write_report
from legal_skill_guard.task import CHOICES, coherent_native_schema, marked_text, original_feedback, output_schema, render_library
from legal_skill_guard.utils.hashing import canonical_json_sha256

from .conditioned import list_preamble_links
from .audit import close, original_score
from .evidence_programs import SCORER_PARAMETERS, evidence_proposals
from .experiment import ENDPOINTS, ROOT, Comparison, now, points, read, sha
from .procedures import BOUNDARY_GUIDANCE_SCHEMA
from .publication import apply_differential_publication, differential_schema, paired, publication_statistics, skill_record_schema

LOCAL_GUIDANCE_SCHEMA = copy.deepcopy(BOUNDARY_GUIDANCE_SCHEMA)
LOCAL_GUIDANCE_SCHEMA["required"] += ["source_operations"]
LOCAL_GUIDANCE_SCHEMA["properties"]["source_operations"] = {
    "type": "array", "items": {"type": "string", "enum": ["list_preamble"]},
}
SEMANTIC_FIELDS = tuple(BOUNDARY_GUIDANCE_SCHEMA["required"])
ARMS = ("strong_empty", "ordinary_memory", "unconditional_layout", "static_procedures", "skill_memory")
PREFIX_ARMS = tuple(a for a in ARMS if a != "static_procedures")
LOCAL_INSTRUCTION = (
    " Work through the supplied public hypotheses. Each question contains its "
    "own complete applicable skill records and fallible source candidates. All "
    "17 questions and the full contract remain visible together; a skill on a "
    "different question is not a condition that this question must satisfy. "
    "Independently inspect the entire source even when this question has no "
    "skills or candidates. A missing skill, an unestablished when condition, "
    "or a null relation_if_established never means NotMentioned. A non-null "
    "conditional relation is not a verdict about this contract. Check the "
    "complete condition and original hypothesis polarity yourself. Skill IDs "
    "reported for a question must come from that question's supplied records; "
    "an empty used_skill_ids list is always allowed. Possible list introductions "
    "are fallible layout suggestions, not proven legal dependencies or required "
    "citations. Decide every original label and final evidence set yourself."
)


def task_skill_projection(bank, labels):
    """No case text, predictions, annotations, or lexical eligibility are read."""
    if len({s["id"] for s in bank}) != len(bank):
        raise ValueError("Duplicate published skill identity")
    for skill in bank:
        if not skill["hypothesis_ids"] or not set(skill["hypothesis_ids"]) <= set(labels):
            raise ValueError("Skill scope must use the original public hypotheses")
        if "source_triggers" in skill["guidance"]:
            raise ValueError("New task-local records cannot retain obsolete routing fields")
    return {
        h: [
            {"id": s["id"], "guidance": {k: s["guidance"][k] for k in SEMANTIC_FIELDS}}
            for s in bank if h in s["hypothesis_ids"]
        ]
        for h in labels
    }


def task_local_messages(row, labels, system, bank, proposals, *, unconditional_layout=False):
    """One original17-question answer, with complete skill text beside its task."""
    projection = task_skill_projection(bank, labels)
    schema = coherent_native_schema(output_schema(row, list(labels), bank))
    questions, operations = {}, {}
    for h, label in labels.items():
        ids = [s["id"] for s in projection[h]]
        used = (
            {"type": "array", "items": {"type": "string", "enum": ids}}
            if ids else {"type": "array", "items": {"type": "string"}, "maxItems": 0}
        )
        for branch in schema["properties"][h]["anyOf"]:
            branch["properties"]["used_skill_ids"] = copy.deepcopy(used)
        candidates = None if proposals is None else proposals["by_hypothesis"][h]["candidates"]
        requesters = [
            s["id"] for s in bank
            if h in s["hypothesis_ids"] and "list_preamble" in s["guidance"]["source_operations"]
        ]
        if unconditional_layout:
            requesters = ["unconditional_layout_control_not_a_skill"]
        links = list_preamble_links(row, [c["original_span_index"] for c in candidates]) if requesters and candidates is not None else []
        if links:
            operations[h] = {"requested_by": requesters, "links": links}
        questions[h] = {
            "original_hypothesis": label["hypothesis"],
            "original_public_short_description": label["short_description"],
            "applicable_published_skills": projection[h],
            "fallible_evidence_candidates": candidates,
            "fallible_source_layout_links": links,
        }
    body = {
        "full_contract_with_original_span_markers": marked_text(row),
        "hypotheses": questions,
        "output_contract": {
            "required_hypothesis_keys": list(labels),
            "fields_in_order": ["choice", "spans", "reason", "used_skill_ids"],
            "original_choice_values": list(CHOICES),
            "NotMentioned_requires_empty_spans": True,
            "other_original_choices_require_nonempty_original_span_indices": True,
            "reason_at_most15_words_per_hypothesis": True,
            "used_skill_ids_must_be_from_this_question_and_may_be_empty": True,
            "per_question_native_schema_is_permitted_values_not_current_answers": True,
        },
        "ordinary_source_evidence_tool": None if proposals is None else {
            "meaning": "Fallible original-span membership learned only from past TRAIN annotations; not legal labels or calibrated legal confidence.",
            "selection": proposals["selection"],
            "may_reject_candidates_and_cite_other_original_spans": True,
            "empty_candidates_never_mean_NotMentioned": True,
        },
    }
    messages = [
        {"role": "system", "content": system + LOCAL_INSTRUCTION},
        {"role": "user", "content": json.dumps(body, ensure_ascii=False, separators=(",", ":"))},
    ]
    delivery = {
        "source_text_and_spans_sha256": canonical_json_sha256({"text": row["text"], "spans": row["spans"]}),
        "published_master_sha256": canonical_json_sha256(bank),
        "published_master_skill_count": len(bank),
        "actual_task_local_projection": projection,
        "actual_task_local_projection_sha256": canonical_json_sha256(projection),
        "actual_source_operations": operations,
        "unconditional_layout_control": unconditional_layout,
        "complete_public_scope_without_case_eligibility_or_legal_host_decision": True,
        "all17_tasks_remain_in_one_context_not_semantic_isolation": True,
    }
    return messages, schema, delivery


def bounded_teacher_packet(training, batch, labels, bank, state, before, after, *, master_tokens, cap):
    """Current-before + previous-after, both actual same-parent observations.

    Earlier raw evidence remains archived, not silently represented as present.
    Gold comparisons are supervised training feedback, not an inference judge.
    """
    witnesses = [r for r in training if r["batch"] in (batch - 1, batch)]
    if not witnesses or not any(r["batch"] == batch for r in witnesses):
        raise ValueError("Current original training batch required")
    parent_sha = canonical_json_sha256(bank)
    expected_projection = task_skill_projection(bank, labels)
    cases, index = [], {h: [] for h in labels}
    for row in witnesses:
        unit = before[row["id"]] if row["batch"] == batch else after[row["id"]]
        trace = unit["actual_factual_trace"]
        if (
            unit["document_id"] != row["id"]
            or unit["stage"] != f"batch{row['batch']}_{'before' if row['batch'] == batch else 'after'}"
            or unit["published_library_sha256"] != parent_sha
            or unit["published_library"] != bank
            or trace["ordinary_model_state"] != state
            or trace["task_local_delivery"]["actual_task_local_projection"] != expected_projection
        ):
            raise ValueError("Teacher observation is not the exact current parent/tool")
        gold = row["annotation_sets"][0]["annotations"]
        parsed = unit["parsed"] if unit["public_valid"] else None
        if parsed is not None and parsed != json.loads(unit["response"]["content"]):
            raise ValueError("Public answer was rewritten before teacher feedback")
        cases.append({
            "document_id": row["id"],
            "observation_kind": "current_batch_before" if row["batch"] == batch else "previous_batch_after",
            "full_original_contract_with_spans": marked_text(row),
            "original_annotations": gold,
            "actual_public_response": {
                k: unit["response"][k] for k in ("raw_id", "finish_reason", "content")
            },
            "actual_public_valid": unit["public_valid"],
            "actual_parent_master_sha256": parent_sha,
            "actual_ordinary_tool_state": state,
            # These are exactly the candidate tables visible to the lawyer.
            # Full internal/diagnostic vectors remain in the immutable trace,
            # not in an editor input which never used them as observations.
            "actual_ordinary_proposals": None if trace["proposals"] is None else {
                "selection": trace["proposals"]["selection"],
                "by_hypothesis": {
                    h: {"candidates": trace["proposals"]["by_hypothesis"][h]["candidates"]}
                    for h in labels
                },
            },
            "actual_delivered_skill_ids_by_public_hypothesis": {
                h: [s["id"] for s in values]
                for h, values in trace["task_local_delivery"]["actual_task_local_projection"].items()
            },
            "actual_factual_source_operations": trace["task_local_delivery"]["actual_source_operations"],
        })
        for h, target in gold.items():
            pred = None if parsed is None else parsed[h]
            gs, ps = set(target["spans"]), set() if pred is None else set(pred["spans"])
            index[h].append({
                "document_id": row["id"],
                "original_Gold_choice": target["choice"],
                "actual_choice": None if pred is None else pred["choice"],
                "label_matches_original": pred is not None and pred["choice"] == target["choice"],
                "original_Gold_span_indices": target["spans"],
                "missing_original_members": sorted(gs - ps),
                "extra_original_members": sorted(ps - gs),
                "full_source_and_public_answer_resolve_in_original_cases_not_copied_here": True,
            })
    return {
        "original_public_hypotheses": labels,
        "hypothesis_indexed_original_feedback": index,
        "complete_actual_parent_library": bank,
        "actual_parent_library_sha256": parent_sha,
        "actual_parent_ordinary_tool_state": state,
        "original_cases_and_actual_same_parent_observations": cases,
        "supplied_original_witness_ids": [r["id"] for r in witnesses],
        "full_library_token_cap": cap,
        "serialized_parent_master_tokens": master_tokens,
        "earlier_experience_carried_by_parent_memory_not_all_older_raw_cases_in_this_request": True,
        "all_older_original_sources_gold_and_answers_remain_archived": True,
        "window_is_explicit_online_learning_design_not_lossless_full_history_encoding": True,
        "no_future_contracts_grading_private_narratives_or_other_method_answers": True,
    }


RUNTIME_API = (
    "Runtime: all17 original hypotheses and the complete original NDA share one "
    "native answer. Each public hypothesis directly receives every published "
    "skill in its declared scope, without lexical or semantic retrieval. Scope "
    "is public task metadata, not a legal verdict or content isolation. Each "
    "guidance has when, inspection, relation_if_established, evidence_requirement "
    "and source_operations. A null relation is an evidence/inspection procedure, "
    "never NM. When the same inspection establishes different labels under "
    "different conditions, prefer separately clear conditional records, not a "
    "mixed rule whose implicit label the weak lawyer must reconstruct. Scope "
    "may cover several original hypotheses only when that same procedure "
    "transfers. No fixed count/types or compulsory hypothesis coverage. "
    "source_operations is [] or [list_preamble]. This factual operation starts "
    "from ordinary source candidates in the public scope, finds possible "
    "governing list introductions and adds optional original-span links. It "
    "does not determine legal dependencies, labels or final evidence. There "
    "are no source_triggers, case eligibility, legal host decisions or answer "
    "repairs. Both full-master serialization and total semantic projection "
    "over the17 questions must fit the supplied token cap; shared-scope text "
    "is charged each time delivered. No pruning or fallback if over capacity."
)
LOCAL_TEACHER_SYSTEM = (
    "Learn reusable legal inspection skills from ONLY the supplied original "
    "TRAIN cases, original labels/evidence, actual public observations and "
    "complete current parent memory. " + RUNTIME_API +
    " Current-before and previous-after really used the same parent and ordinary "
    "tool. Earlier experience survives in memory; older raw cases are archived, "
    "not supplied here. Do not invent their current failures or private reasoning. "
    "The grouped index resolves full original source, Gold, public answer and "
    "candidate table in original_cases_and_actual_same_parent_observations. "
    "Keep every success/failure; do not select only impressive examples. Compare "
    "different labels for the SAME exact public hypothesis where present. "
    "Distinguish incomplete source coverage, mistaken relation/polarity and an "
    "inapplicable rule. Improve coverage by complementary justified procedures, "
    "not by treating an unmet sufficient condition as necessary or inferring NM. "
    "Do not confuse a conditional permission with universal permission or an "
    "auxiliary Gold span with a sufficient legal condition. Preserve complete "
    "independent and governing evidence; do not prescribe fixed candidate counts. "
    "Original labels are benchmark training feedback, not universal legal truth. "
    "Publish explicit CREATE/UPDATE/DELETE/MERGE against original parent IDs: "
    "CREATE has no targets; UPDATE/DELETE one; MERGE at least two distinct parent "
    "IDs. No forward references. UPDATE preserves ID; MERGE can retain a consumed "
    "ID or create a new ID. DELETE skill is null; other operations supply one "
    "resulting skill. Cite only supplied witness case IDs and explain the "
    "generic distinction changed. Unmentioned records stay verbatim. No change "
    "means operations=[] and a nonempty noop_reason; otherwise noop_reason=null. "
    "No mandatory growth/deletion, usage-based eviction or efficacy admission. "
    "All structurally valid changes publish. Runtime text cannot store source "
    "IDs, parties, dates, original indices, case answer tables, source fingerprints "
    "or copied case-specific lookup text. No future sources, other learners, "
    "outside law, tools, answer generation for the lawyer, best-bank selection "
    "or model updates. Return only the requested publication schema."
)
LOCAL_STATIC_SYSTEM = (
    "Write a compact reusable inspection library using ONLY these public legal "
    "hypotheses and runtime API. No cases, Gold or observations are available; "
    "invent none. Skills are fallible procedures, not answers, mandatory evidence "
    "or outside law. No fixed topics/count and no case tables. " + RUNTIME_API +
    " Return only the requested library within both stated token budgets."
)


def prepare_task_local_inputs(cfg):
    packet, selection = read(ROOT / cfg["input_packet"]), read(ROOT / cfg["preselection"])
    if (
        sha(ROOT / cfg["source_archive"]) != cfg["source_archive_sha256"]
        or [r["id"] for r in packet["training"]] != cfg["training_ids"]
        or [r["id"] for r in packet["later_inputs_no_annotation_sets"]] != cfg["expected_later_ids"]
        or selection["training_ids"] != cfg["training_ids"]
        or selection["future_ids"] != cfg["expected_later_ids"]
        or (
            cfg["planned_new_native_calls"] + cfg.get("planned_inherited_native_calls", 0),
            cfg["planned_new_teacher_calls"] + cfg.get("planned_inherited_teacher_calls", 0),
            cfg["planned_logical_observations"], cfg["planned_same_run_cold_aliases"],
        ) != (148, 5, 166, 18)
        or cfg.get("teacher_packet_encoding") != "lawyer_visible_candidate_tables_v1"
    ):
        raise ValueError("Exact original24/8 and full148/5 schedule required")
    with zipfile.ZipFile(ROOT / cfg["source_archive"]) as archive:
        author = json.loads(archive.read("contract-nli/train.json"))
    original = {r["id"]: r for r in author["documents"]}
    if author["labels"] != packet["public_hypotheses"]:
        raise ValueError("Original public hypotheses changed")
    for row in packet["training"]:
        if {k: v for k, v in row.items() if k != "batch"} != original[row["id"]]:
            raise ValueError("Original TRAIN text, spans or labels changed")
    for row in packet["later_inputs_no_annotation_sets"]:
        if row != {k: v for k, v in original[row["id"]].items() if k != "annotation_sets"}:
            raise ValueError("Original later source changed or Gold entered inference")
    groups = source_components(author["documents"])
    train_ids, future_ids = set(cfg["training_ids"]), set(cfg["expected_later_ids"])
    if (
        sum(bool(set(g) & train_ids) for g in groups) != 24
        or sum(bool(set(g) & future_ids) for g in groups) != 8
        or any(set(g) & train_ids and set(g) & future_ids for g in groups)
    ):
        raise ValueError("Exact24/8 distinct and source-disjoint components required")
    paths = [ROOT / cfg["source_archive"]]
    for batch in range(1, 5):
        path = ROOT / cfg["reference_training_run"] / f"evidence_models/ordinary_M{batch}.manifest.json"
        paths += [path, Path(read(path)["path"])]
    if cfg.get("continuation_parent"):
        parent = ROOT / cfg["continuation_parent"]
        parent_config = ROOT / cfg["continuation_parent_config"]
        paths += [parent_config, parent_config.with_suffix(".frozen.json")]
        paths += sorted(p for p in parent.rglob("*.json") if p.is_file())
    if cfg.get("static_public_reference"):
        if (
            cfg.get("static_control_policy") != "fixed_public_only_reference_v1"
            or cfg.get("continuation_parent")
            or cfg.get("planned_inherited_native_calls", 0) != 0
            or cfg.get("planned_inherited_teacher_calls") != 1
            or cfg["planned_new_teacher_calls"] != 4
        ):
            raise ValueError("Fixed public-only control is distinct from main learning inheritance")
        reference = ROOT / cfg["static_public_reference"]
        paths += [reference / name for name in ("wire_request.json", "response.json", "event_log.json")]
    return selection, paths


class TaskLocalStudy(Comparison):
    """One fresh complete online learner; only shared wire/storage primitives."""

    def __init__(self, config_path, *, run_id=None):
        self.config_path = Path(config_path).resolve()
        self.cfg = read(self.config_path)
        if self.cfg["method"] != "task_local_memory" or self.cfg["teacher_feedback"] != "current_and_previous_same_parent_v1" or self.cfg["memory_representation"] != "task_local_boundary_v1":
            raise ValueError("Explicit task-local bounded online protocol required")
        self.run_id = safe_component(run_id or self.cfg["run_id"])
        self.out, self.report = ROOT / "runs" / self.run_id, ROOT / self.cfg["report_directory"] / self.run_id
        if self.out.exists():
            raise FileExistsError("New Run ID required; no automatic resume")
        frozen = read(self.config_path.with_suffix(".frozen.json"))
        if frozen["config_sha256"] != sha(self.config_path):
            raise ValueError("Frozen configuration changed")
        self.bindings = frozen["files"]
        packet = read(ROOT / self.cfg["input_packet"])
        self.labels, self.training, self.future = packet["public_hypotheses"], packet["training"], packet["later_inputs_no_annotation_sets"]
        if (len(self.labels), len(self.training), len(self.future)) != (17, 24, 8) or any(sum(r["batch"] == b for r in self.training) != 6 for b in range(1, 5)):
            raise ValueError("Exact original17/four6/eight exposed development required")
        if any("annotation_sets" in r for r in self.future):
            raise ValueError("Later annotations in inference packet")
        self.native, self.teachers, self.units, self.aliases, self.summaries = [], [], [], [], []
        self.inherited_native, self.inherited_teachers = [], []
        self.prefix_answers, self.prefix_teachers, self.prefix_slots = {}, {}, set()
        self.bank, self.static, self.before, self.after, self.state_versions = [], [], {}, {}, {}
        self.model, self.state = None, None
        self.teacher_attempts, self.current_batch, self.stop = 0, 0, False
        self.meter = WireClient(self.cfg["generation"])
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: setattr(self, "stop", True))
        if self.cfg.get("continuation_parent"):
            parent = ROOT / self.cfg["continuation_parent"]
            old = read(ROOT / self.cfg["continuation_parent_config"])
            failure = read(parent / "failure.json")
            if (
                self.cfg.get("continuation_kind") != "explicit_B2_before_editor_hidden_vector_packing_repair_v1"
                or (self.cfg.get("planned_inherited_native_calls"), self.cfg.get("planned_inherited_teacher_calls")) != (36, 2)
                or failure["error"] != "ValueError('Complete teacher input exceeds character capacity; never truncate')"
                or (failure["completed_native_calls"], failure["completed_teacher_calls"], failure["teacher_attempts"], failure["current_batch"]) != (36, 2, 2, 2)
                or (Path("/proc") / str(read(parent / "launch.json")["pid"])).exists()
                or (parent / "teacher/task_local_b2").exists()
                or (parent / "update_transactions/b2.json").exists()
            ):
                raise ValueError("Only the explicit terminal36/2 pre-B2-editor prefix is accepted")
            for key in ("generation", "teacher", "bundled_solver_system", "library_token_hard_cap", "input_packet", "grading_only", "preselection", "training_ids", "expected_later_ids", "source_archive", "source_archive_sha256", "reference_training_run", "memory_representation", "teacher_feedback"):
                if self.cfg[key] != old[key]:
                    raise ValueError("Prefix reuse changed an inference/data condition: " + key)
            for path in sorted(parent.glob("batch*_*/*/*.public.json")):
                unit = read(path)
                key = (unit["stage"], unit["arm"], unit["document_id"])
                if key in self.prefix_answers:
                    raise ValueError("Duplicate inherited slot")
                self.prefix_answers[key] = (path, unit)
            self.prefix_slots = {
                ("batch1_before", "strong_empty", r["id"]) for r in self.training if r["batch"] == 1
            } | {
                ("batch1_after", "skill_memory", r["id"]) for r in self.training if r["batch"] == 1
            } | {
                ("batch2_before", a, r["id"]) for r in self.training if r["batch"] == 2 for a in PREFIX_ARMS
            }
            if set(self.prefix_answers) != self.prefix_slots or len(self.prefix_slots) != 36:
                raise ValueError("Exact complete36-response prefix required")
            self.prefix_teachers = {name: parent / "teacher" / name for name in ("static_public_task_only", "task_local_b1")}

    def progress(self, stage, **extra):
        super().progress(stage, inherited_native_calls=len(self.inherited_native), inherited_teacher_calls=len(self.inherited_teachers), **extra)

    def answer(self, stage, arm, row, bank, gold=None):
        key = (stage, arm, row["id"])
        if key not in self.prefix_slots:
            return super().answer(stage, arm, row, bank, gold)
        if key not in self.prefix_answers:
            raise ValueError("Inherited response cannot be consumed twice")
        path, original = self.prefix_answers.pop(key)
        unit = {**copy.deepcopy(original), "explicit_inherited_from": str(path), "inherited_response_not_new_generation": True}
        if unit["published_library"] != bank:
            raise ValueError("Inherited response uses another bank")
        RunStore.immutable_json(self.out / stage / arm / f"{row['id']}.reference.json", unit)
        self.inherited_native.append(read(unit["raw_artifact"]))
        self.units.append(unit)
        return unit

    def teacher_call(self, name, system, body, schema):
        if name not in self.prefix_teachers:
            if self.cfg.get("continuation_parent") and (self.prefix_answers or self.prefix_teachers):
                raise ValueError("Complete exact prefix must replay before any new teacher")
            return super().teacher_call(name, system, body, schema)
        source = self.prefix_teachers.pop(name)
        wire, response = read(source / "wire_request.json"), read(source / "response.json")
        events = read(source / "event_log.json")
        user = body if isinstance(body, str) else json.dumps(body, ensure_ascii=False, separators=(",", ":"))
        if (
            wire["system_prompt"] != system or wire["user_prompt"] != user or wire["output_schema"] != schema
            or wire["model"] != self.cfg["teacher"]["model"] or wire["reasoning_effort"] != self.cfg["teacher"]["reasoning_effort"]
            or canonical_json_sha256(wire) != response["request_sha256"]
            or canonical_json_sha256(response["value"]) != response["response_sha256"]
            or response["model"] != self.cfg["teacher"]["model"]
            or response["cache_hit"] or response["invocation"]["returncode"] != 0 or response["invocation"]["tool_events_detected"]
            or response["invocation"]["attempt"] != 1
            or canonical_json_sha256({"event_log": events["event_log"]}) != response["invocation"]["event_log_sha256"]
        ):
            raise ValueError("Inherited teacher request/value differs from the exact original")
        validate(response["value"], schema)
        dest = self.out / "teacher" / name
        for filename in ("wire_request.json", "response.json", "event_log.json"):
            RunStore.immutable_json(dest / filename, read(source / filename))
        RunStore.immutable_json(dest / "explicit_historical_reference.json", {"source": str(source), "not_a_new_invocation_cache_hit_or_independent_learning_repeat": True})
        self.inherited_teachers.append({"name": name, **response, "explicit_inherited_from": str(source)})
        return response["value"]

    def bank_for(self, arm):
        if arm not in ARMS:
            raise ValueError("Unknown task-local study arm")
        return self.bank if arm == "skill_memory" else self.static if arm == "static_procedures" else []

    def make_payload(self, arm, row, bank, model, state):
        proposals = evidence_proposals(None if arm == "strong_empty" else model, row, self.labels)
        messages, schema, delivery = task_local_messages(row, self.labels, self.cfg["bundled_solver_system"], bank, proposals, unconditional_layout=arm == "unconditional_layout")
        delivery["actual_scoped_delivery_tokens"] = self.meter.token_count(text=json.dumps(delivery["actual_task_local_projection"], ensure_ascii=False, separators=(",", ":")))
        return messages, schema, None, {"ordinary_model_state": None if arm == "strong_empty" else state, "proposals": proposals, "task_local_delivery": delivery}

    def messages(self, arm, row, bank):
        if bank != self.bank_for(arm):
            raise ValueError("Wrong published master for the declared arm")
        return self.make_payload(arm, row, bank, self.model, self.state)

    def validate_library(self, bank):
        for skill in bank:
            validate(skill, skill_record_schema(self.labels, guidance_schema=LOCAL_GUIDANCE_SCHEMA))
            if len(set(skill["hypothesis_ids"])) != len(skill["hypothesis_ids"]) or len(set(skill["guidance"]["source_operations"])) != len(skill["guidance"]["source_operations"]):
                raise ValueError("Duplicate scope or factual operation")
        projection = task_skill_projection(bank, self.labels)
        master = self.meter.token_count(text=render_library(bank))
        scoped = self.meter.token_count(text=json.dumps(projection, ensure_ascii=False, separators=(",", ":")))
        if max(master, scoped) > self.cfg["library_token_hard_cap"]:
            raise ValueError("Master or delivered knowledge over declared capacity; no pruning/fallback")
        return {"master_tokens": master, "scoped_delivery_tokens": scoped}

    def fit_ordinary(self, batch):
        path = ROOT / self.cfg["reference_training_run"] / f"evidence_models/ordinary_M{batch}.manifest.json"
        record = read(path)
        manifest = {k: v for k, v in record.items() if k != "state_sha256"}
        rows = [r for r in self.training if r["batch"] <= batch]
        if canonical_json_sha256(manifest) != record["state_sha256"] or manifest["original_training_rows_sha256"] != canonical_json_sha256(rows) or manifest["seen_original_source_ids"] != [r["id"] for r in rows] or manifest["parameters"] != SCORER_PARAMETERS or manifest["programs"] or sha(manifest["path"]) != manifest["pickle_sha256"]:
            raise ValueError("Shared supervised tool is not the exact original prefix fit")
        with Path(manifest["path"]).open("rb") as stream:
            model = pickle.load(stream)
        if model.programs or model.queries:
            raise ValueError("Ordinary tool cannot contain learned skill-query features")
        self.model, self.state = model, record["state_sha256"]
        self.state_versions[self.state] = manifest
        RunStore.immutable_json(self.out / f"inherited_evidence_models/M{batch}.json", {"manifest_path": str(path), "manifest_sha256": sha(path), **record, "inherited_same_prefix_fit_not_new_CPU_fit_or_lawyer_weight_update": True})

    def cold_alias(self, arm, row, actual):
        messages, schema, plan, trace = self.messages(arm, row, [])
        raw = read(actual["raw_artifact"])
        expected = {k: self.cfg["generation"][k] for k in ("model", "temperature", "top_p", "top_k", "max_tokens", "seed")}
        expected.update(messages=messages, response_format={"type": "json_schema", "json_schema": {"name": "contractnli_callable_final", "strict": True, "schema": schema}})
        if len(raw["calls"]) != 1 or raw["calls"][0]["request"] != expected:
            raise ValueError("Only genuinely identical within-run cold requests may be shared")
        unit = {**copy.deepcopy(actual), "arm": arm, "actual_public_plan": plan, "actual_factual_trace": trace, "same_run_exact_cold_alias_not_new_generation": True}
        RunStore.immutable_json(self.out / f"batch1_before/{arm}/{row['id']}.reference.json", unit)
        self.aliases.append(unit)
        return unit

    def audit_units(self, units, name):
        rows = {r["id"]: r for r in self.training + self.future}
        models = {}
        for unit in units:
            row = rows[unit["document_id"]]
            stage, arm = unit["stage"], unit["arm"]
            if stage in ("later", "retention_b4"):
                version = 4
            elif stage == f"batch{row['batch']}_before":
                version = row["batch"] - 1
            elif stage == f"batch{row['batch']}_after":
                version = row["batch"]
            else:
                raise ValueError("Undeclared source/stage pairing")
            expected_bank = (
                read(self.out / f"update_transactions/b{version}.json")["publication"] if arm == "skill_memory" and version
                else self.static if arm == "static_procedures" else []
            )
            expected_state = None if arm == "strong_empty" or not version else read(ROOT / self.cfg["reference_training_run"] / f"evidence_models/ordinary_M{version}.manifest.json")["state_sha256"]
            if unit["published_library"] != expected_bank or unit["actual_factual_trace"]["ordinary_model_state"] != expected_state:
                raise ValueError("Actual source/stage uses the wrong published bank or prefix tool")
            state = unit["actual_factual_trace"]["ordinary_model_state"]
            model = None
            if state is not None:
                manifest = self.state_versions[state]
                if sha(manifest["path"]) != manifest["pickle_sha256"]:
                    raise ValueError("Inherited model bytes changed")
                if state not in models:
                    with Path(manifest["path"]).open("rb") as stream:
                        models[state] = pickle.load(stream)
                model = models[state]
            messages, schema, _, trace = self.make_payload(unit["arm"], row, unit["published_library"], model, state)
            close(trace, unit["actual_factual_trace"])
            if canonical_json_sha256(unit["published_library"]) != unit["published_library_sha256"]:
                raise ValueError("Published memory identity mismatch")
            raw = read(unit["raw_artifact"])
            expected = {k: self.cfg["generation"][k] for k in ("model", "temperature", "top_p", "top_k", "max_tokens", "seed")}
            expected.update(messages=messages, response_format={"type": "json_schema", "json_schema": {"name": "contractnli_callable_final", "strict": True, "schema": schema}})
            if len(raw["calls"]) != 1 or raw["calls"][0]["request"] != expected or raw["response"] != unit["response"]:
                raise ValueError("Full native task/source/memory/tool/schema/decoding replay mismatch")
            if unit["response"]["finish_reason"] == "stop":
                validate(json.loads(unit["response"]["content"]), schema)
            if "annotation_sets" in row:
                close(original_score(unit["response"], row, row["annotation_sets"][0]["annotations"], list(self.labels)), unit)
        RunStore.immutable_json(self.out / f"audits/{name}.json", {"at": now(), "logical_observations": len(units), "complete_source_task_scope_operation_tool_schema_decode_and_original_score_replayed": True})

    def initial_static(self):
        value = self.teacher_call("static_public_task_only", LOCAL_STATIC_SYSTEM, {
            "public_hypotheses": self.labels,
            "full_master_and_actual_scoped_projection_token_cap": self.cfg["library_token_hard_cap"],
        }, {"type": "object", "additionalProperties": False, "required": ["library"], "properties": {"library": {"type": "array", "items": skill_record_schema(self.labels, guidance_schema=LOCAL_GUIDANCE_SCHEMA)}}})
        self.static = value["library"]
        tokens = self.validate_library(self.static)
        inherited = any(t["name"] == "static_public_task_only" for t in self.inherited_teachers)
        RunStore.immutable_json(self.out / "static_procedures.json", {
            "library": self.static, **tokens,
            "fresh_public_task_only_control_no_cases_gold_or_observations": not inherited,
            "explicit_historical_public_only_static_reference": inherited,
            "fixed_public_control_not_inherited_main_skill_memory": bool(self.cfg.get("static_public_reference")),
        })

    def update(self, batch):
        tokens = self.validate_library(self.bank)
        body = bounded_teacher_packet(self.training, batch, self.labels, self.bank, self.state, self.before, self.after, master_tokens=tokens["master_tokens"], cap=self.cfg["library_token_hard_cap"])
        body["serialized_parent_scoped_delivery_tokens"] = tokens["scoped_delivery_tokens"]
        sources = body["supplied_original_witness_ids"]
        value = self.teacher_call(f"task_local_b{batch}", LOCAL_TEACHER_SYSTEM, body, differential_schema(self.labels, self.bank, sources, guidance_schema=LOCAL_GUIDANCE_SCHEMA))
        published = apply_differential_publication(self.bank, value, self.labels, sources, guidance_schema=LOCAL_GUIDANCE_SCHEMA)
        capacity = self.validate_library(published)
        stats = {**publication_statistics(self.bank, value, published, capacity["master_tokens"]), "serialized_scoped_delivery_tokens": capacity["scoped_delivery_tokens"]}
        RunStore.immutable_json(self.out / f"update_transactions/b{batch}.json", {
            "at": now(), "batch": batch, "actual_parent": self.bank,
            "actual_teacher_value": value, "publication": published, "management": stats,
            "source_case_ids": sources, "all_valid_changes_published_without_efficacy_gate": True,
            "actual_current_and_previous_same_parent_window_not_full_cumulative_raw_history": True,
            "no_fixed_skill_count_growth_deletion_or_best_bank_selection": True,
            "new_teacher_invocation_for_this_edit": not (self.cfg.get("continuation_parent") and batch == 1),
        })
        return published, stats

    def execute(self):
        self.check()
        RunStore.immutable_json(self.out / "launch.json", {"at": now(), "pid": os.getpid(), "argv": sys.argv})
        RunStore.immutable_json(self.out / "declaration.json", {
            "at": now(), "run_id": self.run_id, "config": self.cfg, "frozen_bindings": self.bindings,
            "fresh_empty_memory_learning_under_own_task_local_observations": not bool(self.cfg.get("continuation_parent")),
            "all_matched_controls_fresh_except_exact_same_run_cold_aliases": not bool(self.cfg.get("continuation_parent")),
            "explicit_continuation_parent": self.cfg.get("continuation_parent"),
            "explicit_fixed_public_only_static_reference": self.cfg.get("static_public_reference"),
            "continuation_not_an_independent_learning_repeat": bool(self.cfg.get("continuation_parent")),
            "single17_task_context_not_semantic_isolation_or_host_legal_decision": True,
            "exposed_development_not_formal_test_or_proven_improvement": True,
        })
        RunStore.immutable_json(self.out / "source_snapshot.json", {"files": {
            p: {"sha256": h, "utf8_text": Path(p).read_text()}
            for p, h in self.bindings.items() if Path(p).suffix in (".py", ".md", ".txt") or Path(p).name == "LICENSE"
        }})
        settings = self.cfg["teacher"]
        checker = CodexCLIClient(model=settings["model"], executable="/usr/bin/codex", cache_root=self.out / "teacher_admin", invocation_budget_path=ROOT / settings["ledger"], max_invocations=settings["total_invocation_budget"])
        native, teacher, budget = self.meter.readiness(), checker.preflight(), checker.invocation_budget_status()
        RunStore.immutable_json(self.out / "readiness.json", {
            "at": now(), "native": native, "teacher": teacher, "budget": budget,
            "runtime_versions": {p: importlib.metadata.version(p) for p in ("numpy", "scipy", "scikit-learn", "lightgbm", "jsonschema")},
            "no_qualification_generation_or_teacher_request": True,
        })
        if not native["ready"] or not teacher["ready"] or budget["available"] < self.cfg["planned_new_teacher_calls"]:
            raise RuntimeError("Original existing model/teacher unavailable; no substitute")
        if self.cfg.get("continuation_parent"):
            RunStore.immutable_json(self.out / "explicit_continuation_provenance.json", {
                "parent_failure": read(ROOT / self.cfg["continuation_parent"] / "failure.json"),
                "inherited_actual_native_teacher_calls": [36, 2], "planned_new_native_teacher_calls": [112, 3],
                "packing_evidence": read(ROOT / self.cfg["input_budget_evidence"]),
                "not_a_fresh_independent_learning_repeat_or_automatic_retry": True,
            })
        self.initial_static()
        for batch in range(1, 5):
            self.current_batch = batch
            rows = [r for r in self.training if r["batch"] == batch]
            before = {a: [] for a in PREFIX_ARMS}
            for index, row in enumerate(rows):
                if batch == 1:
                    cold = self.collect("batch1_before", "strong_empty", [row], [])[0]
                    for arm in PREFIX_ARMS:
                        before[arm].append(cold if arm == "strong_empty" else self.cold_alias(arm, row, cold))
                else:
                    order = list(PREFIX_ARMS)
                    offset = (batch + index) % len(order)
                    for arm in order[offset:] + order[:offset]:
                        before[arm] += self.collect(f"batch{batch}_before", arm, [row], self.bank_for(arm))
                self.before[row["id"]] = before["skill_memory"][-1]
            self.audit_units([u for values in before.values() for u in values], f"batch{batch}_before_teacher")
            self.bank, stats = self.update(batch)
            self.fit_ordinary(batch)
            after = self.collect(f"batch{batch}_after", "skill_memory", rows, self.bank)
            self.after.update({u["document_id"]: u for u in after})
            self.audit_units(after, f"batch{batch}_after")
            summary = {
                "at": now(), "batch": batch, "source_ids": [r["id"] for r in rows],
                "before": {a: points(us) for a, us in before.items()},
                "after": {"skill_memory": points(after)}, "strong_empty": points(before["strong_empty"]),
                "first_encounter_skill_minus_ordinary": paired(before["ordinary_memory"], before["skill_memory"]),
                "first_encounter_skill_minus_all_layout": paired(before["unconditional_layout"], before["skill_memory"]),
                "seen_update_effects": paired(before["skill_memory"], after), "library_management": stats,
                "after_changes_supervised_tool_and_memory_not_pure_skill_effect": True,
                "before_actual_responses_inherited": bool(self.cfg.get("continuation_parent") and batch <= 2),
                "after_actual_responses_and_editor_inherited": bool(self.cfg.get("continuation_parent") and batch == 1),
            }
            self.summaries.append(summary)
            RunStore.immutable_json(self.out / f"batch{batch}_summary.json", summary)
            write_report(self.out)
            self.progress("batch_complete", completed_batches=batch)
        first = [r for r in self.training if r["batch"] == 1]
        retained = self.collect("retention_b4", "skill_memory", first, self.bank)
        self.audit_units(retained, "retention_b4")
        RunStore.immutable_json(self.out / "retention_b4.json", {
            "metrics": points(retained), "B1_M1_to_M4": paired([self.after[r["id"]] for r in first], retained),
            "shared_supervised_tool_also_changes_not_pure_memory_forgetting": True,
            "not_to_teacher_admission_or_best_bank_selection": True,
        })
        RunStore.immutable_json(self.out / "memory_frozen_before_later.json", {"at": now(), "main_library": self.bank, "static_library": self.static, "ordinary_model_state": self.state, "last_published_not_best_library": True})
        later = {a: [] for a in ARMS}
        for index, row in enumerate(self.future):
            offset = index % len(ARMS)
            for arm in ARMS[offset:] + ARMS[:offset]:
                later[arm].append(self.answer("later", arm, row, self.bank_for(arm)))
        self.finish(later)

    def finish(self, later):
        self.check()
        all_units = self.units + self.aliases
        all_native = self.inherited_native + self.native
        all_teachers = self.inherited_teachers + self.teachers
        if (
            (len(all_native), len(all_teachers), self.teacher_attempts + len(self.inherited_teachers), len(self.aliases), len(all_units)) != (148, 5, 5, 18, 166)
            or len(self.native) != self.cfg["planned_new_native_calls"] or len(self.teachers) != self.cfg["planned_new_teacher_calls"]
            or len(self.inherited_native) != self.cfg.get("planned_inherited_native_calls", 0)
            or len(self.inherited_teachers) != self.cfg.get("planned_inherited_teacher_calls", 0)
            or self.prefix_answers or self.prefix_teachers or any(len(us) != 8 for us in later.values())
        ):
            raise ValueError("Full148/5/18/166 schedule required before development grading")
        expected_slots = {
            (f"batch{r['batch']}_before", arm, r["id"]) for r in self.training for arm in PREFIX_ARMS
        } | {
            (f"batch{r['batch']}_after", "skill_memory", r["id"]) for r in self.training
        } | {
            ("retention_b4", "skill_memory", r["id"]) for r in self.training if r["batch"] == 1
        } | {("later", arm, r["id"]) for r in self.future for arm in ARMS}
        if len(expected_slots) != 166 or {(u["stage"], u["arm"], u["document_id"]) for u in all_units} != expected_slots:
            raise ValueError("Complete166 predeclared source/arm/stage slots required")
        if {t["name"] for t in all_teachers} != {"static_public_task_only", *(f"task_local_b{b}" for b in range(1, 5))}:
            raise ValueError("Teacher roles differ from declared static plus four edits")
        ids = {n["response"]["raw_id"] for n in all_native}
        if len(ids) != 148 or {u["response"]["raw_id"] for u in all_units} != ids:
            raise ValueError("Distinct physical response/alias identities differ")
        self.audit_units(all_units, "complete166_before_later_grading")
        # Only now open the original TRAIN-development annotations, never TEST.
        grading = read(ROOT / self.cfg["grading_only"])["annotations"]
        with zipfile.ZipFile(ROOT / self.cfg["source_archive"]) as archive:
            author = json.loads(archive.read("contract-nli/train.json"))
        original = {r["id"]: r for r in author["documents"]}
        scored = {a: [] for a in ARMS}
        for arm, us in later.items():
            for row, unit in zip(self.future, us, strict=True):
                if unit["document_id"] != row["id"]:
                    raise ValueError("Endpoint source order/identity mismatch")
                gold = original[row["id"]]["annotation_sets"][0]["annotations"]
                if grading[str(row["id"]) ] != gold:
                    raise ValueError("Development Gold differs from original author TRAIN")
                feedback = original_feedback(unit["response"], row, gold, list(self.labels))
                close(original_score(unit["response"], row, gold, list(self.labels)), feedback)
                value = {**unit, **feedback}
                RunStore.immutable_json(self.out / f"later_scored/{arm}/{row['id']}.json", value)
                scored[arm].append(value)
        metrics = {a: points(us) for a, us in scored.items()}
        rng, intervals = np.random.default_rng(self.cfg["bootstrap_seed"]), {}
        for arm in ARMS:
            if arm == "skill_memory":
                continue
            draws = {e: [] for e in ENDPOINTS}
            for _ in range(self.cfg["bootstrap_draws"]):
                sample = rng.integers(0, 8, 8)
                a, b = (points([scored[k][i] for i in sample]) for k in ("skill_memory", arm))
                for e in ENDPOINTS:
                    draws[e].append(a[e] - b[e])
            intervals[arm] = {e: {"point": metrics["skill_memory"][e] - metrics[arm][e], "ci95_descriptive_one_learning_artifact": list(map(float, np.quantile(values, [0.025, 0.975])))} for e, values in draws.items()}
        main_ids = {u["response"]["raw_id"] for u in all_units if u["arm"] == "skill_memory"}
        if len(main_ids) != 62:
            raise ValueError("Main-path/shared-cold cost accounting mismatch")
        done = {
            "at": now(), "run_id": self.run_id, "new_native_calls": len(self.native), "new_teacher_calls": len(self.teachers),
            "new_teacher_attempts": self.teacher_attempts, "same_run_exact_cold_aliases": 18,
            "logical_observations": 166, "distinct_native_responses": 148,
            "explicitly_inherited_native_calls": len(self.inherited_native), "explicitly_inherited_teacher_calls": len(self.inherited_teachers),
            "whole_learning_lineage_native_teacher_calls": [148, 5],
            "continuation_parent": self.cfg.get("continuation_parent"),
            "new_external_historical_native_references": len(self.inherited_native),
            "main_path_unique_native_calls_including_shared_cold_fit_retention_and_endpoint": 62,
            "other_control_only_unique_native_calls": 86,
            "inherited_logical_observations_not_new_calls": len(self.inherited_native) + (18 if self.inherited_native else 0),
            "new_main_path_unique_native_calls": sum(n["response"]["raw_id"] in main_ids for n in self.native),
            "new_other_control_only_unique_native_calls": sum(n["response"]["raw_id"] not in main_ids for n in self.native),
            "main_teacher_edits": 4, "static_control_teacher_calls": 1,
            "batches": self.summaries, "development": metrics,
            "paired_skill_minus_control": {a: paired(scored[a], scored["skill_memory"]) for a in ARMS if a != "skill_memory"},
            "descriptive_source_intervals_not_independent_learning_repeats": intervals,
            "new_native_usage": {k: sum(n["response"][k] for n in self.native) for k in ("prompt_tokens", "completion_tokens")},
            "inherited_native_usage_not_new_spend": {k: sum(n["response"][k] for n in self.inherited_native) for k in ("prompt_tokens", "completion_tokens")},
            "main_path_native_usage_not_to_add_again_to_total": {k: sum(n["response"][k] for n in self.native if n["response"]["raw_id"] in main_ids) for k in ("prompt_tokens", "completion_tokens")},
            "new_teacher_usage": {k: sum(t["invocation"]["usage"][k] for t in self.teachers) for k in ("input_tokens", "output_tokens", "reasoning_output_tokens")},
            "inherited_teacher_usage_not_new_spend": {k: sum(t["invocation"]["usage"][k] for t in self.inherited_teachers) for k in ("input_tokens", "output_tokens", "reasoning_output_tokens")},
            "new_CPU_fits": 0, "inherited_exact_prefix_CPU_fits": 4,
            "fresh_own_online_skill_learning_not_fixed_bank_delivery_probe": not bool(self.cfg.get("continuation_parent")),
            "own_online_learning_continuation_not_fixed_bank_or_independent_repeat": bool(self.cfg.get("continuation_parent")),
            "bounded_window_changes_teacher_information_not_lossless_full_history": True,
            "exposed_development_not_formal_test_or_independent_repeat": True,
            "no_host_legal_decision_answer_repair_effect_admission_or_best_bank": True,
        }
        RunStore.immutable_json(self.out / "completion.json", done)
        RunStore.immutable_json(self.report / "complete_metrics.json", done)
        write_report(self.out)
        RunStore.atomic_json(self.out / "progress.json", {"at": now(), "run_id": self.run_id, "state": "completed", "completed_native_calls": len(self.native), "completed_teacher_calls": len(self.teachers), "inherited_native_calls": len(self.inherited_native), "inherited_teacher_calls": len(self.inherited_teachers), "completed_batches": 4, "logical_observations": 166})
