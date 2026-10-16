"""Source-conditioned external skills with auditable factual layout operations.

The host checks literal source cues and locates possible list introductions. It
never predicts a legal relation, appends evidence to an answer, or selects a
winning library. All published edits remain effective until an explicit edit.
Historical identical controls are references, never new native generations.
"""

from __future__ import annotations

import copy
import importlib.metadata
import json
import os
import pickle
import re
import signal
import sys
import zipfile
from pathlib import Path

import numpy as np
from jsonschema import validate

from legal_skill_guard.experiment.storage import RunStore, safe_component
from legal_skill_guard.inference.codex_cli_client import CodexCLIClient
from legal_skill_guard.inference.native import WireClient
from legal_skill_guard.report import write_report
from legal_skill_guard.task import original_feedback, render_library
from legal_skill_guard.utils.hashing import canonical_json_sha256

from .audit import close, original_score
from .clauses import _contains, _tokens
from .evidence_programs import SCORER_PARAMETERS, evidence_proposals
from .experiment import ENDPOINTS, ROOT, now, points, read, sha
from .feedback_history import grounded_teacher_input, intervention_history
from .procedures import (
    BOUNDARY_GUIDANCE_SCHEMA,
    ProcedureStudy,
    local_executor_trace,
    procedure_messages,
)
from .publication import (
    apply_differential_publication,
    differential_schema,
    paired,
    publication_statistics,
    skill_record_schema,
)

ARMS = (
    "strong_empty",
    "ordinary_memory",
    "unconditional_layout",
    "static_procedures",
    "trace_procedures",
)
PREFIX_ARMS = tuple(a for a in ARMS if a != "static_procedures")
GUIDANCE_SCHEMA = copy.deepcopy(BOUNDARY_GUIDANCE_SCHEMA)
GUIDANCE_SCHEMA["required"] += ["source_triggers", "source_operations"]
GUIDANCE_SCHEMA["properties"].update(
    source_triggers={
        "type": "array",
        "minItems": 1,
        "items": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "string", "minLength": 1, "maxLength": 128},
        },
    },
    source_operations={
        "type": "array",
        "items": {"type": "string", "enum": ["list_preamble"]},
    },
)
ITEM = re.compile(r"^\s*(?:\([A-Za-z0-9ivxIVX]+\)|[a-z]\))\s*")
TERMINAL = re.compile(r"""[.!?][\s”’"'\)\]]*$""")

API = (
    "Runtime API: each guidance adds source_triggers and source_operations. "
    "source_triggers is a nonempty OR of nonempty AND groups of short positive "
    'source phrases. Example [["return"],["destroy"]] means either literal '
    'topic cue; [["return","copy"]] requires both somewhere in the full NDA, '
    "not necessarily the same clause. Matching is case-insensitive contiguous "
    "word-token matching with the existing light suffix normalizer, not semantic "
    "entailment; synonyms and some inflections need separate OR alternatives. "
    "Use broad reusable factual eligibility cues, not a full annotated quotation, "
    "case fingerprint, legal label, absence test, or sufficient legal condition. "
    "The host delivers ONLY matching skills' four semantic fields and IDs. "
    "The lawyer must still verify when and decide the exact relation. No match "
    "means no retrieval, never NotMentioned; full original source remains visible. "
    'source_operations is [] or ["list_preamble"]. This optional operation starts '
    "from this skill's public hypotheses' ordinary fallible evidence candidates. "
    "For a parenthesized or letter-paren list item it searches backwards through "
    "items to the nearest non-item fragment, stopping at terminal punctuation. "
    "It offers a possible list introduction, never proves dependency or mandates "
    "a citation. No automatic evidence union or answer repair occurs. Activate "
    "this operation only when its source inspection is appropriate, not for all "
    "skills to mechanically increase recall. Both cue eligibility and operation "
    "requests are learned parts of each skill, revisable by the same atomic edits. "
)
TEACHER_SYSTEM = (
    "Learn reusable legal source-inspection skills from ONLY the supplied original "
    "already-seen TRAIN sources, annotations and actual own local-8B observations. "
    "Original labels and binary evidence are training feedback, not universal law. "
    "The lawyer is frozen, sees the full NDA, and answers all 17 exact public "
    "hypotheses in one native call. A shared past-prefix supervised membership "
    "tool offers fallible evidence candidates, never legal labels. "
    + API
    + "The complete parent is supplied for editing, NOT necessarily delivered to "
    "the lawyer. Actual delivery traces distinguish master, eligible IDs, semantic "
    "projection, cue matches and factual operations. All answers, including zero "
    "activation, failures and successes, remain observations; do not assume a "
    "stored or self-reported skill was causally effective. Actual local_executor_trace "
    "is untrusted saved reasoning_content from this same local 8B, not source "
    "facts or a faithful causal explanation. Never invent an execution or request "
    "your own hidden reasoning. Non-null observations use the exact current "
    "parent and tool; earlier original sources without such execution have null "
    "observations. Compare contrasting original labels for the SAME hypothesis. "
    "Repair actual actor/action/object, trigger, exception, quantifier and polarity "
    "errors; distinguish label errors from missing and excess source members. "
    "Keep every independently supporting annotated span, including redundant "
    "support and necessary governing language; do not force a minimal witness or "
    "blindly add related spans. A permission, different actor or related action "
    "does not establish a different hypothesis. Absence of a cue does not establish "
    "its opposite. Each guidance is ONE reusable conditional inspection: when, "
    "inspection, relation_if_established (original label only when truly sufficient, "
    "otherwise null), and evidence_requirement, plus the API fields. No fixed "
    "topics, skill types or count. Do not duplicate the public base task. "
    "Review the complete parent for redundant instructions, incompatible scope and "
    "unsupported breadth. CREATE only a missing reusable distinction; UPDATE a "
    "current record rather than append its paraphrase. MERGE genuinely redundant "
    "records without losing distinct source conditions. DELETE contradicted or "
    "superseded records when warranted by seen sources, not merely low usage. "
    "Publish explicit CREATE/UPDATE/DELETE/MERGE operations: CREATE has no targets, "
    "UPDATE/DELETE one exact-parent target, MERGE at least two. Targets are distinct "
    "unconsumed parent IDs, not new forward references. UPDATE preserves its ID; "
    "MERGE may retain a consumed ID or use a new one. DELETE skill is null, others "
    "have one resulting skill. Each operation cites seen source IDs and explains "
    "the actual boundary, eligibility or redundancy change. Unmentioned parent "
    "records remain verbatim. No changes means empty operations and nonempty "
    "noop_reason; with changes noop_reason is null. No forced growth or deletion, "
    "efficacy admission, best-bank selection, fallback or second curator. "
    "Keep the full serialized master within capacity by justified edits. Runtime "
    "fields cannot store document IDs, parties, dates, original indices, case answer "
    "tables or copied case-specific lookup phrases. Audit references stay outside "
    "runtime. No outside law, tools, future contracts, other methods or future Gold."
)
STATIC_SYSTEM = (
    "Write compact reusable legal inspection skills using ONLY the supplied public "
    "hypotheses and inference API. No contracts, observations or Gold are available; "
    "invent none. Use one atomic conditional inspection per record, exact original "
    "polarity, all independent source support, and null relation when inspection "
    "does not settle a label. Skills are fallible, not verdicts or required evidence. "
    "No fixed count or forced coverage; avoid redundant restatements and case IDs. "
    + API
    + "Return the full requested library within the serialized master token budget."
)
HISTORY_FEEDBACK = "observable_intervention_history_v1"
HISTORY_TEACHER_SYSTEM = TEACHER_SYSTEM + (
    " This run supplies ONLY observable execution inputs/public answers and original "
    "annotations, not local private self-narratives. Do not invent private reasoning "
    "or treat a short public reason as a faithful causal explanation. Historical "
    "intervention evidence keeps ALL earlier own public answers and exact old "
    "bank/tool identities plus previous actual edits and their original rationales. "
    "Those rationales are claims to check, not verified explanations. Read the explicit "
    "historical_feedback_columns in order. Compare recurrent errors with prior "
    "edits and contrasting original labels for the same hypothesis. Do not repeat "
    "an unsupported repair just because its rationale sounded plausible. Distinguish "
    "missed eligibility, delivered-but-not-followed guidance, unsupported legal "
    "conditions, missing source members and excess citations. Older-version answers "
    "are NOT current-parent executions; tool changes confound before/after outcomes, "
    "and no outcome proves an individual skill caused it. Grounded grouped feedback "
    "aligns current delivery, candidates and source operations. Annotated-span text "
    "references resolve exactly in the complete source, not an omitted summary. "
    "Only this same teacher publishes edits; no extra judge, selector or efficacy "
    "gate. Retain, revise, consolidate or remove according to seen source evidence, "
    "not a deletion quota, usage frequency, current Gold copying or a best-bank score."
)


def eligible_delivery(row, bank):
    """Positive factual cue matching only; annotations and predictions are unread."""
    sequence = _tokens(row["text"])
    selected, checks = [], []
    for skill in bank:
        groups = skill["guidance"]["source_triggers"]
        hits = [all(_contains(sequence, _tokens(p)) for p in g) for g in groups]
        active = any(hits)
        checks.append({"skill_id": skill["id"], "matched_groups": hits, "eligible": active})
        if active:
            selected.append(
                {
                    "id": skill["id"],
                    "hypothesis_ids": skill["hypothesis_ids"],
                    "guidance": {
                        k: skill["guidance"][k] for k in BOUNDARY_GUIDANCE_SCHEMA["required"]
                    },
                }
            )
    return selected, checks


def list_preamble_links(row, seeds):
    """Fallible layout coordinates, NOT source entailment or a final evidence set."""
    texts = [row["text"][a:b].strip() for a, b in row["spans"]]
    links = []
    for seed in seeds:
        if type(seed) is not int or not 0 <= seed < len(texts):
            raise ValueError("Invalid original candidate index")
        if not ITEM.match(texts[seed]):
            continue
        for index in range(seed - 1, -1, -1):
            if TERMINAL.search(texts[index]):
                break
            if ITEM.match(texts[index]):
                continue
            links.append({"candidate_span_index": seed, "possible_preamble_span_index": index})
            break
    return links


def conditioned_messages(row, labels, system, bank, proposals, *, unconditional=False):
    selected, checks = eligible_delivery(row, bank)
    active = {s["id"] for s in selected}
    links = {}
    for key in labels:
        requesters = [
            s["id"]
            for s in bank
            if s["id"] in active
            and key in s["hypothesis_ids"]
            and "list_preamble" in s["guidance"]["source_operations"]
        ]
        if unconditional:
            requesters = ["unconditional_layout_control_not_a_skill"]
        if requesters and proposals is not None:
            found = list_preamble_links(
                row,
                [c["original_span_index"] for c in proposals["by_hypothesis"][key]["candidates"]],
            )
            if found:
                links[key] = {"requested_by": requesters, "links": found}
    messages, schema = procedure_messages(row, labels, system, selected, proposals)
    if links:
        body = json.loads(messages[1]["content"])
        for key, value in links.items():
            body["hypotheses"][key]["fallible_source_layout_links"] = value["links"]
        body["source_layout_link_contract"] = (
            "These are possible list introductions found by a source-layout operation, "
            "not proven legal dependencies or required evidence. Independently inspect "
            "the original child and possible introduction in the full source. Accept or "
            "reject each; never automatically union links into your answer or infer a label."
        )
        messages[1]["content"] = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    delivery = {
        "source_text_and_spans_sha256": canonical_json_sha256(
            {"text": row["text"], "spans": row["spans"]}
        ),
        "published_master_sha256": canonical_json_sha256(bank),
        "published_master_skill_count": len(bank),
        "actually_delivered_skill_ids": [s["id"] for s in selected],
        "actually_delivered_projection": selected,
        "actually_delivered_projection_sha256": canonical_json_sha256(selected),
        "positive_source_cue_checks": checks,
        "actual_source_operations": links,
        "unconditional_layout_control": unconditional,
        "no_match_never_decides_a_relation": True,
    }
    return messages, schema, delivery


def encode_parent_projections(original):
    """Factor exact repeated projections, without summarizing any observation."""
    body = copy.deepcopy(original)
    parent = {s["id"]: s for s in body["complete_actual_parent_library"]}
    for case in body["cumulative_seen_original_train_cases"]:
        obs = case["actual_own_same_parent_observation"]
        if obs is None:
            continue
        delivery = obs["actual_source_conditioning_and_delivery"]
        expected = parent_projection(parent, delivery["actually_delivered_skill_ids"])
        if (
            expected != delivery.pop("actually_delivered_projection")
            or canonical_json_sha256(expected) != delivery["actually_delivered_projection_sha256"]
        ):
            raise ValueError("Projection must equal the exact parent subset before factoring")
    body["lossless_projection_encoding"] = {
        "version": "exact-current-parent-projection-reference-v1",
        "meaning": "For every non-null observation reconstruct actually_delivered_projection from the ordered actually_delivered_skill_ids and complete_actual_parent_library. Each projected record contains id, hypothesis_ids, and guidance fields when, inspection, relation_if_established, evidence_requirement only. This is exactly the delivered subset, NOT the whole parent. Every original source, Gold, actual answer, local trace, cue match, operation, order, projection hash and token count is unchanged.",
    }
    if decode_parent_projections(body) != original:
        raise ValueError("Factored teacher observations failed exact roundtrip")
    return body


def parent_projection(parent, ids):
    return [
        {
            "id": sid,
            "hypothesis_ids": parent[sid]["hypothesis_ids"],
            "guidance": {
                k: parent[sid]["guidance"][k] for k in BOUNDARY_GUIDANCE_SCHEMA["required"]
            },
        }
        for sid in ids
    ]


def decode_parent_projections(encoded):
    body = copy.deepcopy(encoded)
    legend = body.pop("lossless_projection_encoding")
    if legend["version"] != "exact-current-parent-projection-reference-v1":
        raise ValueError("Unknown teacher projection encoding")
    parent = {s["id"]: s for s in body["complete_actual_parent_library"]}
    for case in body["cumulative_seen_original_train_cases"]:
        obs = case["actual_own_same_parent_observation"]
        if obs is not None:
            delivery = obs["actual_source_conditioning_and_delivery"]
            delivery["actually_delivered_projection"] = parent_projection(
                parent, delivery["actually_delivered_skill_ids"]
            )
    return body


def prepare_conditioned_inputs(cfg):
    """Reuse the immutable original packet; bind every referenced dependency."""
    packet = read(ROOT / cfg["input_packet"])
    selection = read(ROOT / cfg["preselection"])
    if (
        [r["id"] for r in packet["training"]] != cfg["training_ids"]
        or [r["id"] for r in packet["later_inputs_no_annotation_sets"]] != cfg["expected_later_ids"]
        or selection["training_ids"] != cfg["training_ids"]
        or selection["future_ids"] != cfg["expected_later_ids"]
        or sha(ROOT / cfg["source_archive"]) != cfg["source_archive_sha256"]
    ):
        raise ValueError("Unchanged preselected original source packet required")
    if any("annotation_sets" in r for r in packet["later_inputs_no_annotation_sets"]):
        raise ValueError("Later Gold in inference packet")
    with zipfile.ZipFile(ROOT / cfg["source_archive"]) as archive:
        original = json.loads(archive.read("contract-nli/train.json"))
    documents = {r["id"]: r for r in original["documents"]}
    if packet["public_hypotheses"] != original["labels"]:
        raise ValueError("Original public hypotheses differ")
    for row in packet["training"]:
        if {k: v for k, v in row.items() if k != "batch"} != documents[row["id"]]:
            raise ValueError("Original TRAIN source/annotation identity mismatch")
    for row in packet["later_inputs_no_annotation_sets"]:
        if row != {k: v for k, v in documents[row["id"]].items() if k != "annotation_sets"}:
            raise ValueError("Original later source identity mismatch")
    main, final = (ROOT / cfg[k] for k in ("reference_training_run", "reference_final_run"))
    bindings = [ROOT / cfg["source_archive"]]
    if "parent_protocol" in cfg:
        bindings.append(ROOT / cfg["parent_protocol"])
    for batch in range(1, 5):
        manifest_path = main / "evidence_models" / f"ordinary_M{batch}.manifest.json"
        manifest = read(manifest_path)
        bindings += [manifest_path, Path(manifest["path"])]
    for row in packet["training"]:
        for arm in ("strong_empty",) if row["batch"] == 1 else ("strong_empty", "ordinary_memory"):
            path = main / f"batch{row['batch']}_before" / arm / f"{row['id']}.public.json"
            bindings += [path, Path(read(path)["raw_artifact"])]
    for row in packet["later_inputs_no_annotation_sets"]:
        for arm in ("strong_empty", "ordinary_memory"):
            path = final / "later" / arm / f"{row['id']}.public.json"
            bindings += [path, Path(read(path)["raw_artifact"])]
    for key in ("reference_ACE_run", "reference_final_run"):
        path = ROOT / cfg[key] / "completion.json"
        bindings.append(path)
    if "continuation_parent" in cfg:
        parent = ROOT / cfg["continuation_parent"]
        bindings += [
            ROOT / cfg["continuation_parent_config"],
            (ROOT / cfg["continuation_parent_config"]).with_suffix(".frozen.json"),
        ]
        parent_cfg = read(ROOT / cfg["continuation_parent_config"])
        bindings += [ROOT / parent_cfg[key] for key in ("method_protocol", "parent_protocol")]
        bindings += [
            parent / name
            for name in (
                "failure.json",
                "declaration.json",
                "source_snapshot.json",
                "static_procedures.json",
            )
        ]
        for folder in ("teacher", "update_transactions", "inherited_evidence_models"):
            bindings += sorted((parent / folder).rglob("*.json"))
        for folder in sorted(parent.glob("batch*_before")) + sorted(parent.glob("batch*_after")):
            bindings += sorted(folder.rglob("*.json"))
        bindings += sorted(parent.glob("batch*_summary.json"))
    if cfg.get("teacher_feedback") == HISTORY_FEEDBACK:
        references = cfg["explicit_historical_reference_files"]
        if len(references) != 110 or (
            cfg["planned_new_native_calls"], cfg["planned_new_teacher_calls"],
            cfg["planned_logical_historical_references"], cfg["planned_unique_historical_native_responses"],
        ) != (56, 4, 110, 92):
            raise ValueError("Explicit full56/4 history study with110/92 controls required")
        for name in references.values():
            path = ROOT / name
            bindings += [path, Path(read(path)["raw_artifact"])]
        static = ROOT / cfg["fixed_static_control_run"]
        bindings += [static / "static_procedures.json"]
        bindings += [static / "teacher/static_public_task_only" / n for n in ("wire_request.json", "response.json")]
        bindings.append(ROOT / cfg["reference_previous_source_conditioned_run"] / "completion.json")
    return selection, sorted(set(bindings))


class ConditionedStudy(ProcedureStudy):
    """One complete online study, reusing only transparent immutable controls."""

    def __init__(self, config_path, *, run_id=None):
        self.config_path = Path(config_path).resolve()
        self.cfg = read(self.config_path)
        if (
            self.cfg["method"] != "source_conditioned_memory"
            or self.cfg["memory_representation"] != "source_conditioned_boundary_v1"
            or self.cfg["teacher_feedback"] not in (
                "cumulative_sources_hypothesis_grounded_feedback_v1", HISTORY_FEEDBACK
            )
        ):
            raise ValueError("Explicit newly frozen source-conditioned configuration required")
        self.run_id = safe_component(run_id or self.cfg["run_id"])
        self.out = ROOT / "runs" / self.run_id
        self.report = ROOT / self.cfg["report_directory"] / self.run_id
        if self.out.exists():
            raise FileExistsError("New Run ID required")
        frozen = read(self.config_path.with_suffix(".frozen.json"))
        if frozen["config_sha256"] != sha(self.config_path):
            raise ValueError("Frozen configuration differs")
        self.bindings = frozen["files"]
        packet = read(ROOT / self.cfg["input_packet"])
        self.labels, self.training = packet["public_hypotheses"], packet["training"]
        self.future = packet["later_inputs_no_annotation_sets"]
        if (len(self.labels), len(self.training), len(self.future)) != (17, 24, 8):
            raise ValueError("Declared17 hypotheses/24 TRAIN/8 exposed development required")
        if any(sum(r["batch"] == b for r in self.training) != 6 for b in range(1, 5)):
            raise ValueError("Four batches of six required")
        self.native, self.teachers, self.units, self.references = [], [], [], []
        self.inherited_native, self.inherited_units, self.inherited_teachers = [], [], []
        self.teacher_attempts, self.current_batch, self.stop = 0, 0, False
        self.bank, self.static = [], []
        self.versions = {canonical_json_sha256([]): []}
        self.model, self.state = None, None
        self.state_versions, self.before, self.after, self.summaries = {}, {}, {}, []
        self.meter = WireClient(self.cfg["generation"])
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: setattr(self, "stop", True))

    def bank_for(self, arm):
        if arm not in ARMS:
            raise ValueError("Unknown declared condition")
        return (
            self.bank
            if arm == "trace_procedures"
            else self.static
            if arm == "static_procedures"
            else []
        )

    def messages(self, arm, row, bank):
        if bank != self.bank_for(arm):
            raise ValueError("Wrong actual master library")
        state = None if arm == "strong_empty" else self.state
        proposal = evidence_proposals(None if state is None else self.model, row, self.labels)
        messages, schema, delivery = conditioned_messages(
            row,
            self.labels,
            self.cfg["bundled_solver_system"],
            bank,
            proposal,
            unconditional=arm == "unconditional_layout",
        )
        delivery["actually_delivered_projection_tokens"] = self.meter.token_count(
            text=render_library(delivery["actually_delivered_projection"])
        )
        return (
            messages,
            schema,
            None,
            {
                "ordinary_model_state": state,
                "proposals": proposal,
                "source_conditioned_delivery": delivery,
            },
        )

    def validate_library(self, bank):
        if len({s["id"] for s in bank}) != len(bank):
            raise ValueError("Duplicate skill IDs")
        for skill in bank:
            validate(skill, skill_record_schema(self.labels, guidance_schema=GUIDANCE_SCHEMA))
            if len(set(skill["hypothesis_ids"])) != len(skill["hypothesis_ids"]):
                raise ValueError("Duplicate public hypothesis scope")
            groups = skill["guidance"]["source_triggers"]
            normalized = [tuple(_tokens(p) for p in group) for group in groups]
            if any(not tokens for group in normalized for tokens in group):
                raise ValueError("Empty normalized source trigger")
            # OR/AND are idempotent: inflection alternatives may normalize to
            # the same cue. Retain them verbatim, charge their full tokens and
            # record every result; they are neither invalid nor repaired.
            ops = skill["guidance"]["source_operations"]
            if len(set(ops)) != len(ops):
                raise ValueError("Duplicate source operations")
        count = self.meter.token_count(text=render_library(bank))
        if count > self.cfg["library_token_hard_cap"]:
            raise ValueError(
                "Full master over capacity; no pruning, fallback or old-bank selection"
            )
        return count

    def initial_static(self):
        if self.cfg["teacher_feedback"] == HISTORY_FEEDBACK:
            source = ROOT / self.cfg["fixed_static_control_run"]
            value = read(source / "static_procedures.json")
            self.static = value["library"]
            tokens = self.validate_library(self.static)
            RunStore.immutable_json(self.out / "static_procedures.json", {
                "library": self.static,
                "serialized_master_tokens": tokens,
                "explicit_existing_public_task_only_control_not_a_new_teacher": True,
                "source_artifact": str(source / "static_procedures.json"),
                "source_sha256": sha(source / "static_procedures.json"),
                "historical_teacher_cost_not_new_spend": read(source / "teacher/static_public_task_only/response.json")["invocation"]["usage"],
            })
            return
        value = self.teacher_call(
            "static_public_task_only",
            STATIC_SYSTEM,
            {
                "public_hypotheses": self.labels,
                "full_master_token_cap": self.cfg["library_token_hard_cap"],
            },
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["library"],
                "properties": {
                    "library": {
                        "type": "array",
                        "items": skill_record_schema(self.labels, guidance_schema=GUIDANCE_SCHEMA),
                    }
                },
            },
        )
        self.static = value["library"]
        tokens = self.validate_library(self.static)
        RunStore.immutable_json(
            self.out / "static_procedures.json",
            {
                "library": self.static,
                "serialized_master_tokens": tokens,
                "public_task_only_same_source_conditioning_and_operation_API": True,
            },
        )

    def observation(self, unit, include_trace):
        value = super().observation(unit, include_trace)
        value["actual_published_master_sha256"] = value.pop("actual_library_sha256")
        value["actual_source_conditioning_and_delivery"] = unit["actual_factual_trace"][
            "source_conditioned_delivery"
        ]
        value["historical_exact_request_reference_not_fresh_generation"] = unit.get(
            "historical_exact_request_reference", False
        )
        return value

    def teacher_input(self, batch, *, include_trace):
        history_mode = self.cfg["teacher_feedback"] == HISTORY_FEEDBACK
        if history_mode:
            include_trace = False
        value = super().teacher_input(batch, include_trace=include_trace)
        value["serialized_parent_master_tokens"] = value.pop("exact_runtime_parent_library_tokens")
        value["runtime_library_encoding"] = (
            "The complete master is retained for editing. Only actually source-eligible "
            "four-field semantic projections are delivered, with per-observation receipts."
        )
        value["source_conditioning_API"] = API
        if history_mode:
            units = [
                u for u in self.units + self.references
                if u["arm"] == "trace_procedures" and u["stage"].startswith("batch")
                and u["stage"].endswith(("_before", "_after"))
            ]
            history = intervention_history(
                self.training, batch, self.bank, self.state, units,
                [read(self.out / f"update_transactions/b{i}.json") for i in range(1, batch)],
            )
            value = grounded_teacher_input(value, self.training, history)
        if (
            self.cfg.get("teacher_packet_encoding")
            == "exact-current-parent-projection-reference-v1"
        ):
            return encode_parent_projections(value)
        return value

    def update(self, batch, *, include_trace):
        body = self.teacher_input(batch, include_trace=include_trace)
        source_ids = [r["document_id"] for r in body["cumulative_seen_original_train_cases"]]
        value = self.teacher_call(
            f"source_conditioned_b{batch}",
            HISTORY_TEACHER_SYSTEM if self.cfg["teacher_feedback"] == HISTORY_FEEDBACK else TEACHER_SYSTEM,
            body,
            differential_schema(
                self.labels, self.bank, source_ids, guidance_schema=GUIDANCE_SCHEMA
            ),
        )
        bank = apply_differential_publication(
            self.bank, value, self.labels, source_ids, guidance_schema=GUIDANCE_SCHEMA
        )
        tokens = self.validate_library(bank)
        stats = publication_statistics(self.bank, value, bank, tokens)
        RunStore.immutable_json(
            self.out / "update_transactions" / f"b{batch}.json",
            {
                "at": now(),
                "batch": batch,
                "actual_parent": self.bank,
                "actual_teacher_value": value,
                "publication": bank,
                "management": stats,
                "source_case_ids": source_ids,
                "all_valid_changes_published_without_efficacy_gate": True,
                "no_mandatory_growth_merge_delete_or_frequency_based_eviction": True,
            },
        )
        return bank, stats

    def fit_ordinary(self, batch):
        path = (
            ROOT
            / self.cfg["reference_training_run"]
            / "evidence_models"
            / f"ordinary_M{batch}.manifest.json"
        )
        record = read(path)
        manifest = {k: v for k, v in record.items() if k != "state_sha256"}
        rows = [r for r in self.training if r["batch"] <= batch]
        if (
            canonical_json_sha256(manifest) != record["state_sha256"]
            or manifest["original_training_rows_sha256"] != canonical_json_sha256(rows)
            or manifest["seen_original_source_ids"] != [r["id"] for r in rows]
            or manifest["parameters"] != SCORER_PARAMETERS
            or manifest["programs"]
            or sha(manifest["path"]) != manifest["pickle_sha256"]
        ):
            raise ValueError("Inherited shared model/prefix identity mismatch")
        with Path(manifest["path"]).open("rb") as stream:
            model = pickle.load(stream)
        if model.programs or model.queries:
            raise ValueError("Shared ordinary tool must have no skill query features")
        self.model, self.state = model, record["state_sha256"]
        self.state_versions[self.state] = manifest
        RunStore.immutable_json(
            self.out / "inherited_evidence_models" / f"M{batch}.json",
            {
                "manifest_path": str(path),
                "manifest_sha256": sha(path),
                **record,
                "exact_inherited_fit_not_a_new_fit_or_lawyer_weight_update": True,
            },
        )

    def reference_answer(self, stage, arm, row):
        """Exact full-wire validation, not a silent cache or failure substitution."""
        self.check()
        history_mode = self.cfg["teacher_feedback"] == HISTORY_FEEDBACK
        if history_mode:
            key = f"{stage}/{arm}/{row['id']}"
            path = ROOT / self.cfg["explicit_historical_reference_files"][key]
        elif stage == "later":
            if arm not in ("strong_empty", "ordinary_memory"):
                raise ValueError("Undeclared later reference")
            path = (
                ROOT / self.cfg["reference_final_run"] / "later" / arm / f"{row['id']}.public.json"
            )
        else:
            if not stage == f"batch{row['batch']}_before":
                raise ValueError("Only predeclared first-encounter references")
            source_arm = "strong_empty" if row["batch"] == 1 else arm
            if source_arm not in ("strong_empty", "ordinary_memory"):
                raise ValueError("Only identical cold controls may share a reference")
            path = (
                ROOT
                / self.cfg["reference_training_run"]
                / stage
                / source_arm
                / f"{row['id']}.public.json"
            )
        old = read(path)
        reference_bank = self.bank_for(arm) if arm == "static_procedures" else []
        messages, schema, plan, trace = self.messages(arm, row, reference_bank)
        generation = self.cfg["generation"]
        expected = {
            k: generation[k]
            for k in ("model", "temperature", "top_p", "top_k", "max_tokens", "seed")
        }
        expected.update(
            messages=messages,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "contractnli_callable_final",
                    "strict": True,
                    "schema": schema,
                },
            },
        )
        raw = read(old["raw_artifact"])
        if (
            len(raw["calls"]) != 1
            or raw["calls"][0]["request"] != expected
            or raw["response"] != old["response"]
        ):
            raise ValueError(
                "Declared reference is not the identical native request; no substitute"
            )
        if (
            old["published_library"] != reference_bank
            or old["actual_factual_trace"]["ordinary_model_state"] != trace["ordinary_model_state"]
        ):
            raise ValueError("Reference bank or tool mismatch")
        close(old["actual_factual_trace"]["proposals"], trace["proposals"])
        unit = {
            **old,
            "stage": stage,
            "arm": arm,
            "actual_public_plan": plan,
            "actual_factual_trace": trace,
            "historical_exact_request_reference": True,
            "reference_public_artifact": str(path),
            "reference_public_sha256": sha(path),
            "not_a_new_native_call_or_independent_repeat": True,
        }
        RunStore.immutable_json(self.out / stage / arm / f"{row['id']}.reference.json", unit)
        self.references.append(unit)
        return unit

    def audit_native(self, units, name):
        rows = {r["id"]: r for r in self.training + self.future}
        models = {}
        for unit in units:
            row = rows[unit["document_id"]]
            state = unit["actual_factual_trace"]["ordinary_model_state"]
            model = None
            if state is not None:
                manifest = self.state_versions[state]
                if sha(manifest["path"]) != manifest["pickle_sha256"]:
                    raise ValueError("Inherited model changed")
                if state not in models:
                    with Path(manifest["path"]).open("rb") as stream:
                        models[state] = pickle.load(stream)
                model = models[state]
            proposal = evidence_proposals(model, row, self.labels)
            close(proposal, unit["actual_factual_trace"]["proposals"])
            messages, schema, delivery = conditioned_messages(
                row,
                self.labels,
                self.cfg["bundled_solver_system"],
                unit["published_library"],
                proposal,
                unconditional=unit["arm"] == "unconditional_layout",
            )
            delivery["actually_delivered_projection_tokens"] = self.meter.token_count(
                text=render_library(delivery["actually_delivered_projection"])
            )
            close(delivery, unit["actual_factual_trace"]["source_conditioned_delivery"])
            if canonical_json_sha256(unit["published_library"]) != unit["published_library_sha256"]:
                raise ValueError("Master identity mismatch")
            raw = read(unit["raw_artifact"])
            wire = raw["calls"][0]["request"]
            if (
                len(raw["calls"]) != 1
                or wire["messages"] != messages
                or wire["response_format"]["json_schema"]["schema"] != schema
                or raw["response"] != unit["response"]
            ):
                raise ValueError("Actual source/selection/operation/native wire identity mismatch")
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
            self.out / "audits" / f"{name}.json",
            {
                "at": now(),
                "logical_observations": len(units),
                "master_eligibility_delivered_projection_operation_wire_and_original_score_replayed": True,
            },
        )

    def execute(self):
        self.check()
        RunStore.immutable_json(
            self.out / "launch.json", {"at": now(), "pid": os.getpid(), "argv": sys.argv}
        )
        RunStore.immutable_json(
            self.out / "declaration.json",
            {
                "at": now(),
                "run_id": self.run_id,
                "config": self.cfg,
                "frozen_bindings": self.bindings,
                "development_candidate_not_confirmed_improvement": True,
                "historical_exact_request_controls_not_new_generations_or_independent_repeat": True,
                "lawyer_retains_all_legal_and_final_evidence_authority": True,
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
        settings = self.cfg["teacher"]
        checker = CodexCLIClient(
            model=settings["model"],
            executable="/usr/bin/codex",
            cache_root=self.out / "teacher_admin",
            invocation_budget_path=ROOT / settings["ledger"],
            max_invocations=settings["total_invocation_budget"],
        )
        ready, teacher, budget = (
            self.meter.readiness(),
            checker.preflight(),
            checker.invocation_budget_status(),
        )
        RunStore.immutable_json(
            self.out / "readiness.json",
            {
                "native": ready,
                "teacher": teacher,
                "budget": budget,
                "runtime_versions": {
                    p: importlib.metadata.version(p)
                    for p in ("numpy", "scipy", "scikit-learn", "lightgbm", "jsonschema")
                },
            },
        )
        if (
            not ready["ready"]
            or not teacher["ready"]
            or budget["available"] < self.cfg["planned_new_teacher_calls"]
        ):
            raise RuntimeError("Declared existing native/teacher unavailable; no substitute")
        self.initial_static()
        for batch in range(1, 5):
            self.current_batch = batch
            rows = [r for r in self.training if r["batch"] == batch]
            before = {a: [] for a in PREFIX_ARMS}
            for index, row in enumerate(rows):
                order = list(PREFIX_ARMS)
                offset = (batch + index) % len(order)
                for arm in order[offset:] + order[:offset]:
                    if batch == 1 or arm in ("strong_empty", "ordinary_memory") or (
                        self.cfg["teacher_feedback"] == HISTORY_FEEDBACK and arm == "unconditional_layout"
                    ):
                        unit = self.reference_answer(f"batch{batch}_before", arm, row)
                    else:
                        unit = self.collect(f"batch{batch}_before", arm, [row], self.bank_for(arm))[
                            0
                        ]
                    before[arm].append(unit)
                self.before[row["id"]] = before["trace_procedures"][-1]
            self.bank, management = self.update(batch, include_trace=True)
            self.versions[canonical_json_sha256(self.bank)] = copy.deepcopy(self.bank)
            self.fit_ordinary(batch)
            after = self.collect(f"batch{batch}_after", "trace_procedures", rows, self.bank)
            self.after.update({u["document_id"]: u for u in after})
            delivery = [u["actual_factual_trace"]["source_conditioned_delivery"] for u in after]
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
                "first_encounter_trace_minus_same_layout_control": paired(
                    before["unconditional_layout"], before["trace_procedures"]
                ),
                "library_management": management,
                "actual_after_delivered_skill_ids_by_source": {
                    str(r["id"]): d["actually_delivered_skill_ids"]
                    for r, d in zip(rows, delivery, strict=True)
                },
                "actual_after_delivered_projection_tokens": [
                    d["actually_delivered_projection_tokens"] for d in delivery
                ],
                "after_is_seen_fit_with_new_gold_and_tool_not_pure_skill_effect": True,
            }
            self.summaries.append(summary)
            RunStore.immutable_json(self.out / f"batch{batch}_summary.json", summary)
            self.audit_native(
                [
                    u
                    for u in self.units + self.references
                    if u["stage"].startswith(f"batch{batch}_")
                ],
                f"batch{batch}",
            )
            write_report(self.out)
            self.progress(
                "batch_complete",
                completed_batches=batch,
                logical_historical_references=len(self.references),
            )
        first = [r for r in self.training if r["batch"] == 1]
        retained = self.collect("retention_b4", "trace_procedures", first, self.bank)
        RunStore.immutable_json(
            self.out / "retention_b4.json",
            {
                "metrics": points(retained),
                "B1_M1_to_M4": paired([self.after[r["id"]] for r in first], retained),
                "never_to_teacher_admission_or_best_bank_selection": True,
            },
        )
        RunStore.immutable_json(
            self.out / "memory_frozen_before_later.json",
            {
                "at": now(),
                "main_library": self.bank,
                "static_library": self.static,
                "ordinary_model_state": self.state,
                "last_published_not_best_library": True,
            },
        )
        later = {a: [] for a in ARMS}
        for index, row in enumerate(self.future):
            offset = index % len(ARMS)
            for arm in ARMS[offset:] + ARMS[:offset]:
                later[arm].append(
                    self.reference_answer("later", arm, row)
                    if arm in ("strong_empty", "ordinary_memory") or (
                        self.cfg["teacher_feedback"] == HISTORY_FEEDBACK
                        and arm in ("unconditional_layout", "static_procedures")
                    )
                    else self.answer("later", arm, row, self.bank_for(arm))
                )
        self.finish(later)

    def finish(self, later):
        self.check()
        all_native = self.inherited_native + self.native
        all_teachers = self.inherited_teachers + self.teachers
        all_units = self.inherited_units + self.units
        history_mode = self.cfg["teacher_feedback"] == HISTORY_FEEDBACK
        required = (56, 4, 110, 56) if history_mode else (90, 5, 76, 90)
        required_old = 92 if history_mode else 58
        if (len(all_native), len(all_teachers), len(self.references), len(all_units)) != (
            *required,
        ) or any(len(u) != 8 for u in later.values()):
            raise ValueError(
                "Complete predeclared native/teacher/reference schedule required: " + str(required)
            )
        if (len(self.native), len(self.teachers)) != (
            self.cfg["planned_new_native_calls"],
            self.cfg["planned_new_teacher_calls"],
        ):
            raise ValueError("Fresh calls differ from the explicit continuation budget")
        self.audit_native(all_units + self.references, "complete_before_new_later_grading")
        new_ids = {n["response"]["raw_id"] for n in self.native}
        inherited_ids = {n["response"]["raw_id"] for n in self.inherited_native}
        old_ids = {u["response"]["raw_id"] for u in self.references}
        if (
            len(new_ids | inherited_ids) != required[0]
            or len(old_ids) != required_old
            or new_ids & inherited_ids
            or (new_ids | inherited_ids) & old_ids
        ):
            raise ValueError("Physical new/historical response identity counts mismatch")
        # No later scoring read before all40 logical answers and all166 wire replays.
        gold = read(ROOT / self.cfg["grading_only"])["annotations"]
        rows = {r["id"]: r for r in self.future}
        scored = {}
        for arm, units in later.items():
            scored[arm] = []
            for unit in units:
                row = rows[unit["document_id"]]
                feedback = original_feedback(
                    unit["response"], row, gold[str(row["id"])], list(self.labels)
                )
                close(
                    original_score(unit["response"], row, gold[str(row["id"])], list(self.labels)),
                    feedback,
                )
                value = {**unit, **feedback}
                RunStore.immutable_json(
                    self.out / "later_scored" / arm / f"{row['id']}.json", value
                )
                scored[arm].append(value)
        results = {a: points(u) for a, u in scored.items()}
        rng, intervals = np.random.default_rng(self.cfg["bootstrap_seed"]), {}
        for control in ARMS:
            if control == "trace_procedures":
                continue
            draws = {e: [] for e in ENDPOINTS}
            for _ in range(self.cfg["bootstrap_draws"]):
                indices = rng.integers(0, 8, 8)
                a, b = (
                    points([scored[arm][i] for i in indices])
                    for arm in ("trace_procedures", control)
                )
                for e in ENDPOINTS:
                    draws[e].append(a[e] - b[e])
            intervals[control] = {
                e: {
                    "point": results["trace_procedures"][e] - results[control][e],
                    "ci95_descriptive_conditional_on_one_developmental_learning_run": list(
                        map(float, np.quantile(x, [0.025, 0.975]))
                    ),
                }
                for e, x in draws.items()
            }
        historical = {
            "original_M4": read(ROOT / self.cfg["reference_final_run"] / "completion.json")[
                "development"
            ]["trace_procedures"],
        }
        ace = read(ROOT / self.cfg["reference_ACE_run"] / "completion.json")
        # Preserve the native comparator's saved names; these are historical results.
        historical["ACE_complete_comparison"] = ace["development"]
        if history_mode:
            historical["previous_source_conditioned_M4"] = read(
                ROOT / self.cfg["reference_previous_source_conditioned_run"] / "completion.json"
            )["development"]
        done = {
            "at": now(),
            "run_id": self.run_id,
            "new_native_calls": len(self.native),
            "new_teacher_calls": len(self.teachers),
            "explicitly_inherited_study_native_calls": len(self.inherited_native),
            "explicitly_inherited_study_teacher_calls": len(self.inherited_teachers),
            "total_this_learning_study_native_calls": len(all_native),
            "total_this_learning_study_teacher_calls": len(all_teachers),
            "continuation_parent": self.cfg.get("continuation_parent"),
            "logical_historical_references": required[2],
            "unique_historical_native_responses": required_old,
            "all_logical_observations": 166,
            "all_distinct_native_responses": 148,
            "batches": self.summaries,
            "development": results,
            "paired_trace_minus_control": {
                a: paired(scored[a], scored["trace_procedures"])
                for a in ARMS
                if a != "trace_procedures"
            },
            "descriptive_source_intervals": intervals,
            "historical_same_source_comparisons_not_independent_or_equal_compute": historical,
            "new_native_usage": {
                k: sum(n["response"][k] for n in self.native)
                for k in ("prompt_tokens", "completion_tokens")
            },
            "referenced_unique_native_usage_not_new_spend": {
                k: sum(
                    u["response"][k]
                    for u in {u["response"]["raw_id"]: u for u in self.references}.values()
                )
                for k in ("prompt_tokens", "completion_tokens")
            },
            "new_teacher_usage": {
                k: sum(t["invocation"]["usage"][k] for t in self.teachers)
                for k in ("input_tokens", "output_tokens", "reasoning_output_tokens")
            },
            "inherited_study_native_usage_not_new_spend": {
                k: sum(n["response"][k] for n in self.inherited_native)
                for k in ("prompt_tokens", "completion_tokens")
            },
            "inherited_study_teacher_usage_not_new_spend": {
                k: sum(t["invocation"]["usage"][k] for t in self.inherited_teachers)
                for k in ("input_tokens", "output_tokens", "reasoning_output_tokens")
            },
            "new_cpu_fits": 0,
            "inherited_original_same_prefix_cpu_fits": 4,
            "exposed_development_not_formal_test_or_independent_learning_repeat": True,
            "no_current_gold_host_verdict_answer_repair_or_best_bank_selection": True,
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
                "completed_native_calls": len(self.native),
                "completed_teacher_calls": len(self.teachers),
                "total_learning_study_native_calls": len(all_native),
                "total_learning_study_teacher_calls": len(all_teachers),
                "logical_historical_references": required[2],
                "completed_batches": 4,
            },
        )


class ConditionedCompletion(ConditionedStudy):
    """Explicit terminal54 suffix, never an automatic retry or fresh study."""

    def __init__(self, config_path, *, run_id=None):
        super().__init__(config_path, run_id=run_id)
        parent = ROOT / self.cfg["continuation_parent"]
        old_cfg = read(ROOT / self.cfg["continuation_parent_config"])
        failure = read(parent / "failure.json")
        if failure[
            "error"
        ] != "ValueError('Complete teacher input exceeds character capacity; never truncate')" or (
            failure["completed_native_calls"],
            failure["completed_teacher_calls"],
            failure["teacher_attempts"],
        ) != (54, 4, 4):
            raise ValueError("Only the exact documented terminal54 capacity failure is accepted")
        pid = read(parent / "launch.json")["pid"]
        if (Path("/proc") / str(pid)).exists():
            raise ValueError("Parent must have exited before a new completion")
        for key in (
            "generation",
            "teacher",
            "bundled_solver_system",
            "library_token_hard_cap",
            "input_packet",
            "grading_only",
            "training_ids",
            "expected_later_ids",
            "memory_representation",
        ):
            if self.cfg[key] != old_cfg[key]:
                raise ValueError("Continuation changed an inference/data/teacher condition: " + key)
        if (
            self.cfg.get("teacher_packet_encoding")
            != "exact-current-parent-projection-reference-v1"
        ):
            raise ValueError("Explicit lossless encoding declaration required")
        self.parent = parent
        self.static = read(parent / "static_procedures.json")["library"]
        for batch in range(1, 4):
            transaction = read(parent / "update_transactions" / f"b{batch}.json")
            bank = transaction["publication"]
            self.versions[canonical_json_sha256(bank)] = bank
            self.summaries.append(read(parent / f"batch{batch}_summary.json"))
            manifest = read(
                ROOT
                / self.cfg["reference_training_run"]
                / "evidence_models"
                / f"ordinary_M{batch}.manifest.json"
            )
            self.state_versions[manifest["state_sha256"]] = {
                k: v for k, v in manifest.items() if k != "state_sha256"
            }
        self.bank = copy.deepcopy(bank)
        self.state = manifest["state_sha256"]
        with Path(manifest["path"]).open("rb") as stream:
            self.model = pickle.load(stream)
        for path in sorted(parent.glob("batch*_before/*/*.reference.json")):
            self.references.append(read(path))
        for path in sorted(parent.glob("batch*_*/*/*.public.json")):
            unit = read(path)
            self.inherited_units.append(unit)
            self.inherited_native.append(read(unit["raw_artifact"]))
            if unit["stage"] == "batch4_before" and unit["arm"] == "trace_procedures":
                self.before[unit["document_id"]] = unit
            if unit["stage"].endswith("_after"):
                self.after[unit["document_id"]] = unit
        for name in (
            "static_public_task_only",
            "source_conditioned_b1",
            "source_conditioned_b2",
            "source_conditioned_b3",
        ):
            self.inherited_teachers.append(
                {"name": name, **read(parent / "teacher" / name / "response.json")}
            )
        if (
            len(self.inherited_native),
            len(self.inherited_teachers),
            len(self.references),
            len(self.before),
            len(self.after),
        ) != (54, 4, 60, 6, 18):
            raise ValueError("Exact complete prefix54/4/60 and observations required")

    def execute(self):
        self.check()
        self.current_batch = 4
        RunStore.immutable_json(
            self.out / "launch.json", {"at": now(), "pid": os.getpid(), "argv": sys.argv}
        )
        RunStore.immutable_json(
            self.out / "declaration.json",
            {
                "at": now(),
                "run_id": self.run_id,
                "config": self.cfg,
                "frozen_bindings": self.bindings,
                "explicit_terminal_prefix_not_fresh_training_or_independent_repeat": True,
                "inherited_native": 54,
                "inherited_teacher": 4,
                "new_native_planned": 36,
                "new_teacher_planned": 1,
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
        self.audit_native(
            self.inherited_units + self.references, "inherited114_before_new_generation"
        )
        self.validate_library(self.bank)
        self.validate_library(self.static)
        for batch, summary in enumerate(self.summaries, 1):
            RunStore.immutable_json(
                self.out / f"batch{batch}_summary.json",
                {
                    **summary,
                    "explicit_inherited_summary_from": str(
                        self.parent / f"batch{batch}_summary.json"
                    ),
                },
            )
        self.bank, management = self.update(4, include_trace=True)
        self.versions[canonical_json_sha256(self.bank)] = copy.deepcopy(self.bank)
        self.fit_ordinary(4)
        rows = [r for r in self.training if r["batch"] == 4]
        before = {}
        for arm in PREFIX_ARMS:
            suffix = "reference" if arm in ("strong_empty", "ordinary_memory") else "public"
            before[arm] = [
                read(self.parent / "batch4_before" / arm / f"{r['id']}.{suffix}.json") for r in rows
            ]
        after = self.collect("batch4_after", "trace_procedures", rows, self.bank)
        self.after.update({u["document_id"]: u for u in after})
        summary = {
            "at": now(),
            "batch": 4,
            "source_ids": [r["id"] for r in rows],
            "before": {a: points(u) for a, u in before.items()},
            "after": {"trace_procedures": points(after)},
            "strong_empty": points(before["strong_empty"]),
            "update_effects": paired(before["trace_procedures"], after),
            "first_encounter_trace_minus_ordinary": paired(
                before["ordinary_memory"], before["trace_procedures"]
            ),
            "first_encounter_trace_minus_same_layout_control": paired(
                before["unconditional_layout"], before["trace_procedures"]
            ),
            "library_management": management,
            "explicit_inherited_before_actual_new_after": True,
            "after_is_seen_fit_with_new_gold_and_tool_not_pure_skill_effect": True,
        }
        self.summaries.append(summary)
        RunStore.immutable_json(self.out / "batch4_summary.json", summary)
        self.audit_native(after, "new_batch4_after")
        write_report(self.out)
        first = [r for r in self.training if r["batch"] == 1]
        retained = self.collect("retention_b4", "trace_procedures", first, self.bank)
        RunStore.immutable_json(
            self.out / "retention_b4.json",
            {
                "metrics": points(retained),
                "B1_M1_to_M4": paired([self.after[r["id"]] for r in first], retained),
                "never_to_teacher_admission_or_best_bank_selection": True,
            },
        )
        RunStore.immutable_json(
            self.out / "memory_frozen_before_later.json",
            {
                "at": now(),
                "main_library": self.bank,
                "static_library": self.static,
                "ordinary_model_state": self.state,
                "last_published_not_best_library": True,
            },
        )
        later = {a: [] for a in ARMS}
        for index, row in enumerate(self.future):
            offset = index % len(ARMS)
            for arm in ARMS[offset:] + ARMS[:offset]:
                later[arm].append(
                    self.reference_answer("later", arm, row)
                    if arm in ("strong_empty", "ordinary_memory")
                    else self.answer("later", arm, row, self.bank_for(arm))
                )
        self.finish(later)
