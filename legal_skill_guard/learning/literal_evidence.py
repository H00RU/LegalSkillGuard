"""Literal source grounding at the two existing evidence-use interfaces.

No new supervision, model, planner, semantic verdict, output repair or gate.
This module is not imported by the currently frozen task-local worker. A new
prospective learner/configuration is required before using its presentation.
"""

from __future__ import annotations

import copy
import json

from legal_skill_guard.experiment.storage import RunStore

from .evidence_programs import evidence_proposals
from .experiment import now
from .publication import apply_differential_publication, differential_schema, publication_statistics
from .task_local import (
    LOCAL_GUIDANCE_SCHEMA,
    LOCAL_TEACHER_SYSTEM,
    TaskLocalStudy,
    bounded_teacher_packet,
    task_local_messages,
)


def original_span_text(row, index):
    if type(index) is not int or not 0 <= index < len(row["spans"]):
        raise ValueError("Literal evidence must reference an original source span")
    start, end = row["spans"][index]
    return row["text"][start:end]


def literal_candidate_view(row, proposals):
    """Keep candidate IDs, scores, order and internal trace; add exact source text."""
    if proposals is None:
        return None  # The same declared zero-data tool state, not a failed tool.
    result = copy.deepcopy(proposals)
    for value in result["by_hypothesis"].values():
        indices = [c["original_span_index"] for c in value["candidates"]]
        if len(indices) != len(set(indices)):
            raise ValueError("Duplicate source candidate identities; no repair")
        for candidate in value["candidates"]:
            text = original_span_text(row, candidate["original_span_index"])
            if "literal_original_text" in candidate and candidate["literal_original_text"] != text:
                raise ValueError("Candidate quotation disagrees with original source")
            candidate["literal_original_text"] = text
    return result


def literal_feedback_view(packet, source_rows):
    """Quote original Gold/actual members beside existing supervised feedback.

    All sources, successes, labels and verbatim public responses stay available.
    The union includes correct evidence, missing evidence and false citations;
    successful witnesses are grounded alongside failures, not filtered out.
    No excerpt is a new answer, an independently judged fact, or inference input.
    """
    result = copy.deepcopy(packet)
    sources = {r["id"]: r for r in source_rows}
    cases = {c["document_id"]: c for c in result["original_cases_and_actual_same_parent_observations"]}
    if set(sources) != set(cases):
        raise ValueError("Only the actual supplied feedback window may be quoted")
    answers = {
        d: json.loads(c["actual_public_response"]["content"]) if c["actual_public_valid"] else None
        for d, c in cases.items()
    }
    for h, entries in result["hypothesis_indexed_original_feedback"].items():
        for entry in entries:
            d = entry["document_id"]
            gold = cases[d]["original_annotations"][h]
            prediction = None if answers[d] is None else answers[d][h]
            gs = set(gold["spans"])
            ps = set() if prediction is None else set(prediction["spans"])
            correct = prediction is not None and prediction["choice"] == gold["choice"]
            if entry["original_Gold_choice"] != gold["choice"] or entry["original_Gold_span_indices"] != gold["spans"] or entry["label_matches_original"] != correct:
                raise ValueError("Original feedback disagrees with its actual case")
            entry["literal_original_evidence_comparison"] = [
                {
                    "original_span_index": i,
                    "literal_original_text": original_span_text(sources[d], i),
                    "original_Gold_member": i in gs,
                    "actual_public_answer_member": i in ps,
                }
                for i in sorted(gs | ps)
            ]
    result["literal_evidence_comparison_view"] = {
        "verbatim_original_source_not_generated_solution_or_new_annotation": True,
        "all_original_cases_gold_successes_and_actual_answers_retained": True,
        "empty_comparison_list_is_not_an_independent_NotMentioned_proof": True,
        "fragments_resolve_in_the_complete_original_contract_not_as_standalone_proofs": True,
    }
    return result


LITERAL_TEACHER_NOTICE = (
    " Exact original candidate text is shown beside its index to the lawyer. "
    "The hypothesis-indexed feedback quotes literal original Gold and actual "
    "citation members, including successful witnesses; "
    "membership flags only restate the supplied original Gold and actual public "
    "answer. An empty comparison list is not an independent NM proof. Read the full source "
    "when a fragment is a list item, anaphor or incomplete clause. For every "
    "label-implying edit, check supplied different-label witnesses against the "
    "complete condition. Do not broaden a condition to accommodate one success "
    "while also admitting a supplied negative witness. If no generic separating "
    "condition is justified, publish an inspection procedure with null relation "
    "rather than an unsupported label implication. This is not a requirement "
    "to null all relations, grow the library, or discard difficult examples."
)


class LiteralEvidenceStudy(TaskLocalStudy):
    """The same full online schedule, with explicitly declared grounded views."""

    def __init__(self, config_path, *, run_id=None):
        super().__init__(config_path, run_id=run_id)
        if self.cfg.get("candidate_source_view") != "literal_original_span_v1" or self.cfg.get("teacher_feedback_view") != "literal_evidence_comparisons_v1" or self.cfg.get("continuation_parent"):
            raise ValueError("Fresh own learning and explicit literal evidence views required")

    def make_payload(self, arm, row, bank, model, state):
        proposals = literal_candidate_view(row, evidence_proposals(None if arm == "strong_empty" else model, row, self.labels))
        messages, schema, delivery = task_local_messages(row, self.labels, self.cfg["bundled_solver_system"], bank, proposals, unconditional_layout=arm == "unconditional_layout")
        delivery["actual_scoped_delivery_tokens"] = self.meter.token_count(text=json.dumps(delivery["actual_task_local_projection"], ensure_ascii=False, separators=(",", ":")))
        delivery["candidate_source_view"] = "literal_original_span_v1"
        return messages, schema, None, {
            "ordinary_model_state": None if arm == "strong_empty" else state,
            "proposals": proposals, "task_local_delivery": delivery,
        }

    def update(self, batch):
        tokens = self.validate_library(self.bank)
        packet = bounded_teacher_packet(self.training, batch, self.labels, self.bank, self.state, self.before, self.after, master_tokens=tokens["master_tokens"], cap=self.cfg["library_token_hard_cap"])
        sources = packet["supplied_original_witness_ids"]
        body = literal_feedback_view(packet, [r for r in self.training if r["id"] in sources])
        body["serialized_parent_scoped_delivery_tokens"] = tokens["scoped_delivery_tokens"]
        value = self.teacher_call(f"task_local_b{batch}", LOCAL_TEACHER_SYSTEM + LITERAL_TEACHER_NOTICE, body, differential_schema(self.labels, self.bank, sources, guidance_schema=LOCAL_GUIDANCE_SCHEMA))
        published = apply_differential_publication(self.bank, value, self.labels, sources, guidance_schema=LOCAL_GUIDANCE_SCHEMA)
        capacity = self.validate_library(published)
        stats = {**publication_statistics(self.bank, value, published, capacity["master_tokens"]), "serialized_scoped_delivery_tokens": capacity["scoped_delivery_tokens"]}
        RunStore.immutable_json(self.out / f"update_transactions/b{batch}.json", {
            "at": now(), "batch": batch, "actual_parent": self.bank,
            "actual_teacher_value": value, "publication": published, "management": stats,
            "source_case_ids": sources, "all_valid_changes_published_without_efficacy_gate": True,
            "actual_current_and_previous_same_parent_window_not_full_cumulative_raw_history": True,
            "no_fixed_skill_count_growth_deletion_or_best_bank_selection": True,
            "new_teacher_invocation_for_this_edit": True,
            "teacher_feedback_view": "literal_evidence_comparisons_v1",
            "original_annotations_and_actual_answers_not_rewritten": True,
        })
        return published, stats
