"""Task-local skill presentation and bounded, original-Gold online feedback.

All public hypotheses share one full-source context. Public scope is structural
metadata, not a semantic router or a proof of internal content isolation.
"""

from __future__ import annotations

import copy
import json

from legal_skill_guard.task import CHOICES, coherent_native_schema, marked_text, output_schema
from legal_skill_guard.utils.hashing import canonical_json_sha256

from .conditioned import list_preamble_links
from .procedures import BOUNDARY_GUIDANCE_SCHEMA

LOCAL_GUIDANCE_SCHEMA = copy.deepcopy(BOUNDARY_GUIDANCE_SCHEMA)
LOCAL_GUIDANCE_SCHEMA["required"] += ["source_operations"]
LOCAL_GUIDANCE_SCHEMA["properties"]["source_operations"] = {
    "type": "array", "items": {"type": "string", "enum": ["list_preamble"]},
}
SEMANTIC_FIELDS = tuple(BOUNDARY_GUIDANCE_SCHEMA["required"])
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
            "actual_ordinary_proposals": trace["proposals"],
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
