"""Executable acquisition skills: one named library and source-only inline leads.

Reuses attributed lexical/layout primitives, never labels or native answers.
V1's failed0-native/1-teacher source is in its source snapshot/Git/backup.
"""

from __future__ import annotations

import copy
import json

from jsonschema import validate

from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.task import (
    coherent_native_schema,
    marked_text,
    output_schema,
    render_library,
)
from legal_skill_guard.utils.hashing import canonical_json_sha256

from .clauses import find_original_clauses, original_clause_records
from .conditioned import list_preamble_links
from .experiment import now
from .literal_evidence import LiteralEvidenceStudy, literal_feedback_view
from .publication import (
    apply_differential_publication,
    differential_schema,
    publication_statistics,
    skill_record_schema,
)
from .task_local import bounded_teacher_packet, task_skill_projection

PROGRAM_FIELDS = ("inspection", "source_queries")
TERMS = {"type": "array", "maxItems": 32, "items": {"type": "string", "minLength": 1, "maxLength": 256}}
DIRECT_QUERY_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["all_phrases", "any_phrases", "none_phrases", "include_list_preamble"],
    "properties": {k: copy.deepcopy(TERMS) for k in ("all_phrases", "any_phrases", "none_phrases")}
    | {"include_list_preamble": {"type": "boolean"}},
}
PROGRAM_GUIDANCE_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": list(PROGRAM_FIELDS),
    "properties": {
        "inspection": {"type": "string", "minLength": 1},
        "source_queries": {"type": "array", "minItems": 1, "maxItems": 8, "items": DIRECT_QUERY_SCHEMA},
    },
}
PROGRAM_API = (
    " A skill has id, public hypothesis_ids, and guidance with ONLY inspection "
    "and source_queries. inspection is a concise reusable procedure for reading "
    "found source and retaining complete evidence, not a conditional verdict. "
    "Each skill has1..8 queries: all_phrases, any_phrases, none_phrases and "
    "include_list_preamble. Every all phrase is needed, one any phrase if "
    "nonempty, and no none phrase; at least one all/any phrase is required. "
    "Matching is contiguous lower-case lightly suffix-stemmed word/number "
    "tokens within each original SPAN, preserving negation/modality. The boolean "
    "option adds only the existing fallible list-introduction locations for "
    "matched list items. There are NO neighbour windows, label rules, source "
    "eligibility or model calls inside programs. Every query executes exactly "
    "as published on original text/spans. The complete NAMED library appears "
    "ONCE, with public-question ID references and actual per-query direct/list "
    "receipts. Inline SOURCE_LEADS tags point to found original SPANs, not "
    "verified relevance. The original contract text is intact and occurs once; "
    "ordinary candidates remain available. Empty hits never mean NotMentioned. "
    "The lawyer alone chooses all labels and complete final SPAN sets, can "
    "reject noisy hits and find evidence elsewhere. Both the full master and "
    "actual one-copy named library plus ID references must fit4096 serving "
    "tokens. Aim below2200 master tokens to leave correction room. No fixed "
    "skill count/types, coverage quota, forced growth or hidden truncation."
)
PROGRAM_TEACHER = (
    "Learn reusable SOURCE-ACQUISITION AND COMPLETE-EVIDENCE INSPECTION skills "
    "from ONLY supplied original TRAIN sources/Gold members, actual own public "
    "answers, parent-query traces and parent memory. The target is acquiring "
    "and retaining ALL original evidence members on later contracts while "
    "preserving three-way decisions, NOT finding a new label-separating rule. "
    "Evidence acquisition/completeness can justify an edit without a new class "
    "condition. " + PROGRAM_API +
    " Compare ALL supplied successes, failures and different-label sources. "
    "Distinguish search miss, noisy retrieval, failure to use visible members "
    "and wrong actor/action/scope/polarity. Distill justified actions for "
    "operative, governing, definitional, exception and independently redundant "
    "evidence; these are possible source functions, not fixed skill types. "
    "Do not recount Gold roles while omitting their reusable action from runtime. "
    "Prefer short compositional queries justified by observed counterexamples, "
    "not catch-all terms or long synonym lists. Same topic is not evidence. "
    "Do not group public hypotheses merely because topics are similar: the "
    "actual query AND inspection must transfer across their scope. Gold is "
    "benchmark feedback, not universal legal truth. Current-before and previous-"
    "after used the same parent/tool; older raw cases stay archived, not supplied. "
    "No invented execution/private reasoning. Publish atomic CREATE/UPDATE/"
    "DELETE/MERGE/NOOP: CREATE has no targets, UPDATE/DELETE one original parent, "
    "MERGE at least two distinct original parents; no forward references. UPDATE "
    "preserves ID, MERGE may keep a consumed ID. Only DELETE has null skill. "
    "Unmentioned records stay verbatim. Each edit cites supplied source_case_ids "
    "and explains its generic acquisition/inspection change; training metadata "
    "never goes to the lawyer. operations=[] requires nonempty noop_reason, "
    "otherwise noop_reason=null. Every structurally valid edit publishes, "
    "without efficacy gates, rollback, best bank or forced growth/deletion. "
    "Runtime must not contain case IDs, parties, dates, original indices, "
    "fingerprints, answer tables or copied case lookup text. No outside law, "
    "tools, future Gold, other-method answers, model fitting or answers for "
    "the lawyer. Return only the publication schema."
)
PROGRAM_STATIC = (
    "Write compact reusable source-acquisition and complete-evidence inspection "
    "skills using ONLY these public hypotheses and runtime API. No documents, "
    "Gold, cases or outcomes exist in this input; invent none. Prefer focused "
    "compositional queries, not broad catch-all term lists or generic instructions "
    "telling the host how to show text (the API already does that). These are "
    "fallible source inspections, not automatic verdict rules. Return only the "
    "library schema. " + PROGRAM_API
)
PROGRAM_NOTICE = (
    " All17 public tasks share the complete source and one-copy "
    "published_source_programs library. A question's applicable_published_skills "
    "contains ID references to those complete named records, not missing "
    "guidance. Read their inspection and the one-copy source_program_query_receipts. "
    "SOURCE_LEADS tags before original SPANs identify mechanical query/list "
    "hits by skill ID/query index, not labels or proven relevance. Only original "
    "contract text is evidence. Preserve original SPAN indices. A different "
    "question's skill is not a condition this question must satisfy. Missing "
    "skills/empty hits never mean NotMentioned. Independently inspect the entire "
    "source, reject noisy leads, retain independent/governing evidence and make "
    "every final label and complete evidence decision yourself. used_skill_ids "
    "must come from this question's ID references and may be empty."
)


def program_projection(bank, labels):
    return task_skill_projection(bank, labels, semantic_fields=PROGRAM_FIELDS)


def one_copy_memory(bank, labels):
    return {"published_source_programs": bank, "hypotheses": {
        h: {"applicable_published_skills": [{"id": s["id"]} for s in bank if h in s["hypothesis_ids"]]}
        for h in labels
    }}


def execute_program(row, skill):
    records, events = original_clause_records(row), []
    for i, query in enumerate(skill["guidance"]["source_queries"]):
        validate(query, DIRECT_QUERY_SCHEMA)
        hits = find_original_clauses(records, query["all_phrases"], query["any_phrases"], query["none_phrases"])
        links = list_preamble_links(row, hits) if query["include_list_preamble"] else []
        returned = sorted(set(hits) | {v["possible_preamble_span_index"] for v in links})
        events.append({"skill_id": skill["id"], "query_index": i, "actual_query_arguments": copy.deepcopy(query),
            "matched_original_span_indices": hits, "possible_list_preamble_links": links,
            "returned_original_span_indices": returned, "literal_original_clauses": [records[j] for j in returned]})
    return events


def source_program_messages(messages, delivery, row, bank, labels, *, system):
    result, trace = copy.deepcopy(messages), copy.deepcopy(delivery)
    projection = program_projection(bank, labels)
    trace.update({"skill_delivery_encoding": "one_copy_named_source_programs_v2",
        "published_master_sha256": canonical_json_sha256(bank), "published_master_skill_count": len(bank),
        "actual_task_local_projection": projection, "actual_task_local_projection_sha256": canonical_json_sha256(projection),
        "canonical_projection_is_resolved_named_library_not_literal_wire_repetition": True,
        "source_program_executions": {}, "source_program_execution_by_skill": {}, "source_lead_tags_by_original_span": {}})
    if not bank:
        assert result == messages
        return result, trace
    body = json.loads(result[1]["content"])
    executed = {s["id"]: execute_program(row, s) for s in bank}
    trace["source_program_execution_by_skill"] = executed
    lead_map = {}
    for sid, events in executed.items():
        for event in events:
            for i in event["returned_original_span_indices"]:
                lead_map.setdefault(i, {}).setdefault(sid, []).append(event["query_index"])
    annotated = marked_text(row)
    tags = {i: "<SOURCE_LEADS>" + json.dumps(values, ensure_ascii=False, separators=(",", ":")) + "</SOURCE_LEADS>"
            for i, values in sorted(lead_map.items())}
    for i, tag in tags.items():
        annotated = annotated.replace(f"<SPAN {i}>", tag + f"<SPAN {i}>", 1)
    restored = annotated
    for tag in tags.values():
        restored = restored.replace(tag, "", 1)
    if restored != marked_text(row):
        raise ValueError("Mechanical lead tags changed the original source")
    body["full_contract_with_original_span_markers"] = annotated
    body["published_source_programs"] = copy.deepcopy(bank)
    body["source_program_query_receipts"] = {
        sid: [{k: v for k, v in event.items() if k not in ("literal_original_clauses", "actual_query_arguments", "skill_id")}
              for event in events] for sid, events in executed.items()
    }
    records = original_clause_records(row)
    for h, question in body["hypotheses"].items():
        ids = [s["id"] for s in bank if h in s["hypothesis_ids"]]
        question["applicable_published_skills"] = [{"id": sid} for sid in ids]
        events = [event for sid in ids for event in executed[sid]]
        receipts = [{k: v for k, v in event.items() if k != "literal_original_clauses"} for event in events]
        members = sorted({i for event in events for i in event["returned_original_span_indices"]})
        trace["source_program_executions"][h] = {"receipts": receipts,
            "literal_original_clauses": [records[i] for i in members],
            "all_source_hits_returned_without_gold_relevance_filter_or_answer_union": True}
        if events:
            trace["actual_source_operations"].setdefault(h, {})["source_query_receipts"] = receipts
    trace["source_lead_tags_by_original_span"] = {str(i): tag for i, tag in tags.items()}
    trace["actual_one_copy_named_memory"] = one_copy_memory(bank, labels)
    result[0]["content"] = system + PROGRAM_NOTICE
    result[1]["content"] = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    return result, trace


def program_member_feedback(unit, row, labels):
    trace = unit["actual_factual_trace"]["task_local_delivery"]["source_program_executions"]
    if unit["published_library"] and set(trace) != set(labels):
        raise ValueError("Nonempty memory needs every public-task receipt")
    if not unit["published_library"] and trace:
        raise ValueError("Empty initial memory cannot have program receipts")
    feedback = {}
    for h in labels:
        actual = trace[h] if unit["published_library"] else {"receipts": [], "literal_original_clauses": []}
        gold = set(row["annotation_sets"][0]["annotations"][h]["spans"])
        returned = {c["original_span_index"] for c in actual["literal_original_clauses"]}
        feedback[h] = {"actual_source_receipts": actual["receipts"],
            "actual_returned_original_member_indices": sorted(returned), "original_Gold_members_reached": sorted(gold & returned),
            "returned_non_Gold_members": sorted(returned - gold), "original_Gold_members_not_reached": sorted(gold - returned)}
    return {"document_id": row["id"], "actual_response_raw_id": unit["response"]["raw_id"],
        "all_original_hypotheses": feedback, "descriptive_query_coverage_not_native_answer_utility_or_semantic_gate": True}


class SourceProgramStudy(LiteralEvidenceStudy):
    def __init__(self, config_path, *, run_id=None):
        super().__init__(config_path, run_id=run_id)
        if (self.cfg.get("teacher_publication_format"), self.cfg.get("skill_delivery_encoding"), self.cfg["memory_representation"]) != (
            "source_acquisition_programs_v2", "one_copy_named_source_programs_v2", "source_acquisition_program_v2"
        ):
            raise ValueError("Explicit minimal one-copy v2 required; historical v1 needs its frozen source")
        if self.cfg.get("static_public_reference") or self.cfg.get("continuation_parent"):
            raise ValueError("Own empty learning and own public-only program control required")

    def make_payload(self, arm, row, bank, model, state):
        messages, schema, plan, trace = super().make_payload(arm, row, [], model, state)
        messages, delivery = source_program_messages(messages, trace["task_local_delivery"], row, bank, self.labels,
                                                   system=self.cfg["bundled_solver_system"])
        if bank:
            schema = coherent_native_schema(output_schema(row, list(self.labels), bank))
            for h, wrapped in schema["properties"].items():
                ids = [s["id"] for s in bank if h in s["hypothesis_ids"]]
                used = {"type": "array", "items": {"type": "string", "enum": ids}} if ids else {"type": "array", "items": {"type": "string"}, "maxItems": 0}
                for branch in wrapped["anyOf"]:
                    branch["properties"]["used_skill_ids"] = copy.deepcopy(used)
        delivery["actual_scoped_delivery_tokens"] = self.meter.token_count(text=json.dumps(one_copy_memory(bank, self.labels), ensure_ascii=False, separators=(",", ":")))
        return messages, schema, plan, {**trace, "task_local_delivery": delivery}

    def validate_library(self, bank):
        for skill in bank:
            validate(skill, skill_record_schema(self.labels, guidance_schema=PROGRAM_GUIDANCE_SCHEMA))
            execute_program({"text": "", "spans": []}, skill)
            if len(set(skill["hypothesis_ids"])) != len(skill["hypothesis_ids"]):
                raise ValueError("Duplicate original public scope")
        master = self.meter.token_count(text=render_library(bank))
        scoped = self.meter.token_count(text=json.dumps(one_copy_memory(bank, self.labels), ensure_ascii=False, separators=(",", ":")))
        if max(master, scoped) > self.cfg["library_token_hard_cap"]:
            raise ValueError("Full one-copy program memory over declared capacity; no pruning")
        return {"master_tokens": master, "scoped_delivery_tokens": scoped}

    def initial_static(self):
        value = self.teacher_call("static_public_task_only", PROGRAM_STATIC, {
            "public_hypotheses": self.labels, "full_master_and_one_copy_named_memory_token_cap": self.cfg["library_token_hard_cap"],
        }, {"type": "object", "additionalProperties": False, "required": ["library"], "properties": {
            "library": {"type": "array", "items": skill_record_schema(self.labels, guidance_schema=PROGRAM_GUIDANCE_SCHEMA)},
        }})
        self.static = value["library"]
        tokens = self.validate_library(self.static)
        RunStore.immutable_json(self.out / "static_procedures.json", {"library": self.static, **tokens,
            "fresh_public_task_only_control_no_cases_gold_or_observations": True,
            "explicit_historical_public_only_static_reference": False, "same_direct_query_API_and_one_copy_named_guidance_as_main": True})

    def update(self, batch):
        tokens = self.validate_library(self.bank)
        body = bounded_teacher_packet(self.training, batch, self.labels, self.bank, self.state, self.before, self.after,
            master_tokens=tokens["master_tokens"], cap=self.cfg["library_token_hard_cap"], semantic_fields=PROGRAM_FIELDS)
        rows = [r for r in self.training if r["id"] in body["supplied_original_witness_ids"]]
        body = literal_feedback_view(body, rows)
        body["serialized_parent_scoped_delivery_tokens"] = tokens["scoped_delivery_tokens"]
        body["canonical_projection_is_resolved_named_library_not_literal_wire_repetition"] = True
        body["actual_runtime_source_lead_tags_by_case"] = {
            str(row["id"]): (self.before[row["id"]] if row["batch"] == batch else self.after[row["id"]])[
                "actual_factual_trace"]["task_local_delivery"]["source_lead_tags_by_original_span"] for row in rows
        }
        body["actual_parent_source_program_member_feedback"] = [program_member_feedback(
            self.before[row["id"]] if row["batch"] == batch else self.after[row["id"]], row, self.labels) for row in rows]
        schema = differential_schema(self.labels, self.bank, body["supplied_original_witness_ids"], guidance_schema=PROGRAM_GUIDANCE_SCHEMA)
        value = self.teacher_call(f"task_local_b{batch}", PROGRAM_TEACHER, body, schema)
        published = apply_differential_publication(self.bank, value, self.labels, body["supplied_original_witness_ids"], guidance_schema=PROGRAM_GUIDANCE_SCHEMA)
        capacity = self.validate_library(published)
        stats = {**publication_statistics(self.bank, value, published, capacity["master_tokens"]), "serialized_scoped_delivery_tokens": capacity["scoped_delivery_tokens"]}
        RunStore.immutable_json(self.out / f"update_transactions/b{batch}.json", {"at": now(), "batch": batch,
            "actual_parent": self.bank, "actual_teacher_value": value, "publication": published, "management": stats,
            "source_case_ids": body["supplied_original_witness_ids"], "all_valid_changes_published_without_efficacy_gate": True,
            "actual_current_and_previous_same_parent_window_not_full_cumulative_raw_history": True,
            "no_fixed_skill_count_growth_deletion_or_best_bank_selection": True, "new_teacher_invocation_for_this_edit": True,
            "teacher_publication_format": "source_acquisition_programs_v2", "skill_delivery_encoding": "one_copy_named_source_programs_v2",
            "no_query_coefficient_fit_or_native_answer_rewrite": True})
        return published, stats
