"""Direct source-program skills and visible inspections, not label-rule memory.

Reuses the existing attributed lexical primitive and atomic publisher. Published
queries return fallible source locations, never final citations or legal labels.
There is no fitted query coefficient, router, critic, answer repair or fallback.
"""

from __future__ import annotations

import copy
import json

from jsonschema import validate

from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.task import render_library

from .clauses import execute_clause_queries
from .experiment import now
from .interface import query_schema, validate_queries
from .literal_evidence import LiteralEvidenceStudy, literal_feedback_view
from .publication import (
    apply_differential_publication,
    differential_schema,
    publication_statistics,
    skill_record_schema,
)
from .task_local import (
    LOCAL_GUIDANCE_SCHEMA,
    bounded_teacher_packet,
    task_skill_projection,
)

PROGRAM_GUIDANCE_SCHEMA = copy.deepcopy(LOCAL_GUIDANCE_SCHEMA)
PROGRAM_GUIDANCE_SCHEMA["properties"]["relation_if_established"] = {"type": "null"}
PROGRAM_GUIDANCE_SCHEMA["required"].append("source_queries")
PROGRAM_GUIDANCE_SCHEMA["properties"]["source_queries"] = {
    "type": "array", "minItems": 1, "maxItems": 8, "items": query_schema(),
}

PROGRAM_API = (
    " Each runtime skill has id, public hypothesis_ids and named guidance fields "
    "when, inspection, relation_if_established, evidence_requirement, "
    "source_operations, source_queries. relation_if_established is always null: "
    "this memory teaches factual source acquisition and evidence inspection, not "
    "automatic E/C/NM conditions. The lawyer still makes all original decisions. "
    "Each skill has1..8 source_queries using the existing API: all_phrases, "
    "any_phrases, none_phrases, before, after. A span matches every all phrase, "
    "one any phrase if present, and no none phrase; at least one all/any phrase "
    "is required. Matching is contiguous lower-case lightly suffix-stemmed "
    "word/number tokens, preserving negation and modality. before/after are "
    "explicit original-span neighbour counts0..64, not semantic relevance. "
    "source_operations is [] or [list_preamble], the existing fallible layout "
    "operation on ordinary candidates. Every published query executes exactly "
    "once under its public hypothesis scope, without case routing, a native "
    "planner or a learned query classifier. The original source, ordinary "
    "candidates, full named inspection guidance, exact query arguments and "
    "all query-result locations are visible together. Literal returned clauses "
    "are quoted once per public question; duplicate query hits keep their "
    "individual receipts. Query hits are unverified source leads, not mandatory "
    "citations. Empty hits are not NotMentioned. No source is deleted, no hits "
    "are selected by confidence/Gold, and no native answer is edited. Both the "
    "full master and complete repeated named skill projection, including query "
    "arguments, must fit4096 tokens. Aim below2200 master tokens to leave room "
    "for later corrections; do not force a count or coverage quota."
)

PROGRAM_TEACHER = (
    "Learn compact reusable SOURCE-ACQUISITION AND COMPLETE-EVIDENCE INSPECTION "
    "programs from the supplied original TRAIN contracts, original member "
    "annotations, actual own public answers, actual query traces and parent "
    "memory. The training objective is to acquire and correctly retain ALL "
    "original evidence members on later contracts, while preserving correct "
    "three-way legal decisions; it is NOT discovery of a new label-separating "
    "condition. An evidence-search or completeness repair is warranted even "
    "when no new E/C boundary exists and the old class rule was correct. "
    "Distill the action needed to recover missed operative, governing, "
    "definitional, exception and independently redundant members; these are "
    "possible source functions, not fixed skill types or required records. "
    "Do not spend the output recounting every Gold member while leaving its "
    "reusable acquisition/inspection absent from runtime. " + PROGRAM_API +
    " Inspect all supplied successes, failures and different-label cases. "
    "Use actual parent-query members/extra/missing feedback to distinguish "
    "a search miss, noisy context, failure to use already-visible evidence, "
    "and wrong actor/scope/polarity. The same topic or lexical match is not "
    "evidence. Avoid catch-all neighbour windows and long synonym lists; "
    "prefer compact compositional source conditions whose actual training "
    "counterexamples justify them. Preserve independent support and governing "
    "language; a sufficient reason for a label is not necessarily its complete "
    "benchmark evidence set. Keep actual query arguments consistent with the "
    "inspection. Do not write new conditional label rules or infer NM from "
    "unmet conditions, missing skills or empty candidates. Original annotations "
    "are benchmark feedback, not universal legal truth. Current-before and "
    "previous-after used the same parent/tool; older raw cases are archived, "
    "not supplied. No invented execution, private reasoning or other-method "
    "answers. Publish one atomic CREATE/UPDATE/DELETE/MERGE/NOOP edit: CREATE "
    "has no targets; UPDATE/DELETE one original parent target; MERGE at least "
    "two distinct original parent IDs. No forward references. UPDATE keeps "
    "its ID; MERGE may keep a consumed ID. Only DELETE has null skill. "
    "Unmentioned records stay verbatim. Cite supplied source_case_ids and "
    "explain the generic acquisition/inspection change in rationale; these "
    "training metadata never go to the lawyer. operations=[] requires a "
    "nonempty noop_reason, otherwise noop_reason=null. No mandatory growth, "
    "effect admission, rollback or best bank. Runtime cannot store case IDs, "
    "parties, dates, original indices, document fingerprints, answer tables "
    "or copied case-specific lookup text. No outside law, tools, future Gold, "
    "model updates or answers on behalf of the lawyer. Return the exact schema."
)
PROGRAM_STATIC = (
    "Write compact reusable source-acquisition and complete-evidence inspection "
    "programs using ONLY these public legal hypotheses and runtime API. No "
    "contracts, Gold, cases, trajectories or outcomes are available; invent "
    "none. Programs locate fallible source leads and help inspect all relevant "
    "original spans; they do not decide labels or final evidence. No fixed "
    "count/types or forced topic coverage. Return exactly the library schema. "
    + PROGRAM_API
)
PROGRAM_NOTICE = (
    " Each supplied skill's source_queries has actually executed on this full "
    "original contract. factual_source_query_receipts give all direct/context "
    "locations; factual_source_query_clauses quote their original text once "
    "per question. They are fallible search leads, not classified evidence or "
    "required citations. Apply the named inspection to those leads and the "
    "entire original source, reject irrelevant hits and find missing evidence "
    "elsewhere. Empty hits never imply NotMentioned. relation_if_established "
    "is null because the skills do not supply legal verdicts. You alone emit "
    "every original label and final complete evidence set."
)


def program_projection(bank, labels):
    projection = task_skill_projection(bank, labels)
    by_id = {s["id"]: s for s in bank}
    for records in projection.values():
        for record in records:
            record["source_queries"] = copy.deepcopy(by_id[record["id"]]["guidance"]["source_queries"])
    return projection


def source_program_messages(messages, delivery, row, bank, labels):
    """Read text/spans only; publish every source hit, never choose an answer."""
    result, trace = copy.deepcopy(messages), copy.deepcopy(delivery)
    projection = program_projection(bank, labels)
    trace["skill_delivery_encoding"] = "named_source_programs_v1"
    trace["actual_named_instruction_and_program_projection"] = projection
    trace["canonical_instruction_projection_excludes_separately_supplied_program_arguments"] = True
    trace["source_program_executions"] = {}
    trace["source_program_execution_by_skill"] = {}
    if not bank:
        assert result == messages
        return result, trace
    body = json.loads(result[1]["content"])
    receipts = {}
    for skill in bank:
        queries = [{"query_id": f"{skill['id']}__q{i}", **q} for i, q in enumerate(skill["guidance"]["source_queries"])]
        receipts[skill["id"]] = execute_clause_queries(row, queries)
    trace["source_program_execution_by_skill"] = receipts
    for h, question in body["hypotheses"].items():
        question["applicable_published_skills"] = projection[h]
        events, clauses = [], {}
        for skill in bank:
            if h not in skill["hypothesis_ids"]:
                continue
            for event in receipts[skill["id"]]:
                events.append({"skill_id": skill["id"], "query_id": event["query_id"],
                               "matched_original_span_indices": event["matched_original_span_indices"],
                               "context_original_span_indices": [c["original_span_index"] for c in event["context_original_clauses"]]})
                for clause in event["context_original_clauses"]:
                    clauses[clause["original_span_index"]] = clause
        question["factual_source_query_receipts"] = events
        question["factual_source_query_clauses"] = [clauses[i] for i in sorted(clauses)]
        trace["source_program_executions"][h] = {
            "receipts": events, "literal_original_clauses": question["factual_source_query_clauses"],
            "all_source_hits_returned_without_gold_relevance_filter_or_answer_union": True,
        }
        if events:
            trace["actual_source_operations"].setdefault(h, {})["source_query_receipts"] = events
    result[0]["content"] += PROGRAM_NOTICE
    result[1]["content"] = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    return result, trace


def program_member_feedback(unit, row, labels):
    """Original TRAIN member comparisons, not causal credit or admission."""
    trace = unit["actual_factual_trace"]["task_local_delivery"]["source_program_executions"]
    if unit["published_library"]:
        if set(trace) != set(labels):
            raise ValueError("A nonempty program bank requires every public-task receipt")
    elif trace:
        raise ValueError("Empty initial memory cannot have a fabricated program receipt")
    feedback = {}
    for h in labels:
        actual = trace.get(h, {"receipts": [], "literal_original_clauses": []})
        gold = set(row["annotation_sets"][0]["annotations"][h]["spans"])
        returned = {c["original_span_index"] for c in actual["literal_original_clauses"]}
        feedback[h] = {
            "actual_source_receipts": actual["receipts"],
            "actual_returned_original_member_indices": sorted(returned),
            "original_Gold_members_reached": sorted(gold & returned),
            "returned_non_Gold_members": sorted(returned - gold),
            "original_Gold_members_not_reached": sorted(gold - returned),
        }
    return {"document_id": row["id"], "actual_response_raw_id": unit["response"]["raw_id"],
            "all_original_hypotheses": feedback,
            "descriptive_query_coverage_not_native_answer_utility_or_semantic_gate": True}


class SourceProgramStudy(LiteralEvidenceStudy):
    """The existing full online schedule, with directly executed learned skills."""

    def __init__(self, config_path, *, run_id=None):
        super().__init__(config_path, run_id=run_id)
        if (self.cfg.get("teacher_publication_format"), self.cfg.get("skill_delivery_encoding")) != ("source_acquisition_programs_v1", "named_source_programs_v1"):
            raise ValueError("Explicit direct-source-program writer/delivery required")
        if self.cfg.get("static_public_reference") or self.cfg.get("continuation_parent"):
            raise ValueError("Own empty learning and own public-only program control required")

    def make_payload(self, arm, row, bank, model, state):
        messages, schema, plan, trace = super().make_payload(arm, row, bank, model, state)
        messages, delivery = source_program_messages(messages, trace["task_local_delivery"], row, bank, self.labels)
        delivery["actual_scoped_delivery_tokens"] = self.meter.token_count(text=json.dumps(delivery["actual_named_instruction_and_program_projection"], ensure_ascii=False, separators=(",", ":")))
        return messages, schema, plan, {**trace, "task_local_delivery": delivery}

    def validate_library(self, bank):
        for skill in bank:
            validate(skill, skill_record_schema(self.labels, guidance_schema=PROGRAM_GUIDANCE_SCHEMA))
            validate_queries(skill["guidance"]["source_queries"])
            if len(set(skill["hypothesis_ids"])) != len(skill["hypothesis_ids"]) or len(set(skill["guidance"]["source_operations"])) != len(skill["guidance"]["source_operations"]):
                raise ValueError("Duplicate original scope or operation")
        master = self.meter.token_count(text=render_library(bank))
        scoped = self.meter.token_count(text=json.dumps(program_projection(bank, self.labels), ensure_ascii=False, separators=(",", ":")))
        if max(master, scoped) > self.cfg["library_token_hard_cap"]:
            raise ValueError("Full named program memory over declared capacity; no pruning")
        return {"master_tokens": master, "scoped_delivery_tokens": scoped}

    def initial_static(self):
        value = self.teacher_call("static_public_task_only", PROGRAM_STATIC, {
            "public_hypotheses": self.labels, "full_master_and_actual_named_projection_token_cap": self.cfg["library_token_hard_cap"],
        }, {"type": "object", "additionalProperties": False, "required": ["library"], "properties": {
            "library": {"type": "array", "items": skill_record_schema(self.labels, guidance_schema=PROGRAM_GUIDANCE_SCHEMA)},
        }})
        self.static = value["library"]
        tokens = self.validate_library(self.static)
        RunStore.immutable_json(self.out / "static_procedures.json", {
            "library": self.static, **tokens, "fresh_public_task_only_control_no_cases_gold_or_observations": True,
            "explicit_historical_public_only_static_reference": False,
            "same_executable_query_API_and_named_guidance_as_main": True,
        })

    def update(self, batch):
        tokens = self.validate_library(self.bank)
        body = bounded_teacher_packet(self.training, batch, self.labels, self.bank, self.state, self.before, self.after,
                                      master_tokens=tokens["master_tokens"], cap=self.cfg["library_token_hard_cap"])
        rows = [r for r in self.training if r["id"] in body["supplied_original_witness_ids"]]
        body = literal_feedback_view(body, rows)
        body["serialized_parent_scoped_delivery_tokens"] = tokens["scoped_delivery_tokens"]
        body["actual_parent_source_program_member_feedback"] = [program_member_feedback(
            self.before[row["id"]] if row["batch"] == batch else self.after[row["id"]], row, self.labels,
        ) for row in rows]
        schema = differential_schema(self.labels, self.bank, body["supplied_original_witness_ids"], guidance_schema=PROGRAM_GUIDANCE_SCHEMA)
        value = self.teacher_call(f"task_local_b{batch}", PROGRAM_TEACHER, body, schema)
        published = apply_differential_publication(self.bank, value, self.labels, body["supplied_original_witness_ids"], guidance_schema=PROGRAM_GUIDANCE_SCHEMA)
        capacity = self.validate_library(published)
        stats = {**publication_statistics(self.bank, value, published, capacity["master_tokens"]), "serialized_scoped_delivery_tokens": capacity["scoped_delivery_tokens"]}
        RunStore.immutable_json(self.out / f"update_transactions/b{batch}.json", {
            "at": now(), "batch": batch, "actual_parent": self.bank, "actual_teacher_value": value,
            "publication": published, "management": stats, "source_case_ids": body["supplied_original_witness_ids"],
            "all_valid_changes_published_without_efficacy_gate": True,
            "actual_current_and_previous_same_parent_window_not_full_cumulative_raw_history": True,
            "no_fixed_skill_count_growth_deletion_or_best_bank_selection": True,
            "new_teacher_invocation_for_this_edit": True,
            "teacher_publication_format": "source_acquisition_programs_v1",
            "skill_delivery_encoding": "named_source_programs_v1",
            "direct_source_hits_plus_full_inspection_not_query_coefficient_fit": True,
            "original_annotations_and_native_answers_not_rewritten": True,
        })
        return published, stats
