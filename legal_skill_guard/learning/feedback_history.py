"""Teacher-only historical facts, not a runtime wiki or skill utility estimator.

Keep old executions explicitly tied to their actual bank and tool. Do not turn
their self-narratives, reported skill IDs, or before/after scores into causes.
Sources/Gold already live in the teacher's cumulative original-case packet.
"""

from __future__ import annotations

import copy
import json

from legal_skill_guard.learning.audit import close, original_score
from legal_skill_guard.task import marked_text
from legal_skill_guard.utils.hashing import canonical_json_sha256

HISTORY_COLUMNS = (
    "document_id", "historical_raw_id", "actual_prediction_not_source_facts",
    "label_correct", "joint_exact", "missing_original_members",
    "excess_original_members", "actually_offered_candidate_indices_not_membership_scores",
)


def intervention_history(training, batch, parent, tool_state, own_units, transactions):
    """Lossless factual projections of every available earlier own training answer.

    Excludes only exact-current-parent/tool observations already delivered in the
    main teacher packet. Historical public answers are preserved, not summarized;
    candidate *indices* are explicitly a projection, not their original scores.
    Callers must audit native wires separately before submitting any packet.
    """
    seen = {r["id"]: r for r in training if r["batch"] <= batch}
    if not seen or len(seen) != len([r for r in training if r["batch"] <= batch]):
        raise ValueError("Distinct cumulative original training sources required")
    parent_sha = canonical_json_sha256(parent)
    banks, events, grouped, observed = {}, [], {}, []
    previous = []
    for index, transaction in enumerate(transactions, 1):
        if transaction["batch"] != index or index >= batch:
            raise ValueError("Only complete own earlier publication prefix is historical")
        if transaction["actual_parent"] != previous:
            raise ValueError("Historical publication lineage is discontinuous")
        value = transaction["actual_teacher_value"]
        publication = transaction["publication"]
        if any(
            source_id not in seen or seen[source_id]["batch"] > index
            for op in value["operations"] for source_id in op["source_case_ids"]
        ):
            raise ValueError("Historical rationale cites an unseen source")
        psha, nsha = map(canonical_json_sha256, (previous, publication))
        banks[psha] = copy.deepcopy(previous)
        banks[nsha] = copy.deepcopy(publication)
        events.append({
            "batch": index,
            "actual_parent_library_sha256": psha,
            "actual_published_library_sha256": nsha,
            "original_noop_reason": value["noop_reason"],
            "actual_edits": [
                {
                    "operation": op["operation"],
                    "target_ids": op["target_ids"],
                    "result_id": None if op["skill"] is None else op["skill"]["id"],
                    "source_case_ids": op["source_case_ids"],
                    "original_teacher_rationale_not_verified_causal_truth": op["rationale"],
                }
                for op in value["operations"]
            ],
        })
        previous = publication
    if len(events) != batch - 1 or previous != parent:
        raise ValueError("All previous publications ending at exact parent required")
    banks.pop(parent_sha, None)  # Present once as complete_actual_parent_library.
    seen_calls, slots, exact_current = set(), set(), []
    if any(u["document_id"] not in seen for u in own_units):
        raise ValueError("Future or non-training execution cannot enter history")
    ordered = sorted(own_units, key=lambda u: (seen[u["document_id"]]["batch"], u["stage"].endswith("_after"), u["document_id"]))
    for unit in ordered:
        document_id, stage = unit["document_id"], unit["stage"]
        if document_id not in seen:
            raise ValueError("Future or non-training execution cannot enter history")
        row = seen[document_id]
        legal_stages = (f"batch{row['batch']}_before", f"batch{row['batch']}_after")
        if unit["arm"] != "trace_procedures" or stage not in legal_stages:
            raise ValueError("Only own training first/after executions, never controls or retention")
        if row["batch"] == batch and stage.endswith("_after"):
            raise ValueError("Current publication outcome is unavailable before its teacher")
        raw_id = unit["response"]["raw_id"]
        if raw_id in seen_calls:
            raise ValueError("Historical references must not duplicate physical executions")
        if (document_id, stage) in slots:
            raise ValueError("Each actual training encounter appears exactly once")
        seen_calls.add(raw_id)
        slots.add((document_id, stage))
        bank, trace = unit["published_library"], unit["actual_factual_trace"]
        bsha = canonical_json_sha256(bank)
        if bsha != unit["published_library_sha256"]:
            raise ValueError("Historical master identity changed")
        state = trace["ordinary_model_state"]
        if bsha == parent_sha and state == tool_state:
            exact_current.append(raw_id)
            continue
        known_bank = parent if bsha == parent_sha else banks.get(bsha)
        if known_bank != bank:
            raise ValueError("Execution bank is not in the actual publication lineage")
        gold = row["annotation_sets"][0]["annotations"]
        score = original_score(unit["response"], row, gold, list(gold))
        close(score, unit)
        delivery = trace["source_conditioned_delivery"]
        if delivery["published_master_sha256"] != bsha:
            raise ValueError("Historical delivery belongs to another bank")
        observed.append({
            "raw_id": raw_id,
            "document_id": document_id,
            "stage": stage,
            "actual_library_sha256": bsha,
            "actual_ordinary_tool_state": state,
            "actual_delivered_skill_ids": delivery["actually_delivered_skill_ids"],
            "actual_source_operations": delivery["actual_source_operations"],
            "actual_public_response_metadata": {
                k: v for k, v in unit["response"].items() if k != "content"
            },
            "actual_public_answer_fields_stored_once_in_grouped_history": True,
            "original_content_canonical_json_sha256": canonical_json_sha256(unit["response"]["content"]),
            "native_answer_key_order": list(json.loads(unit["response"]["content"])) if score["public_valid"] else None,
            "invalid_public_content_verbatim": None if score["public_valid"] else unit["response"]["content"],
            "original_public_valid": score["public_valid"],
            "raw_native_artifact_for_external_audit_not_a_teacher_tool": unit["raw_artifact"],
        })
        proposals = trace["proposals"]
        for query in score["queries"]:
            key, prediction = query["hypothesis_id"], query["prediction"]
            candidate_indices = None if proposals is None else [
                c["original_span_index"] for c in proposals["by_hypothesis"][key]["candidates"]
            ]
            grouped.setdefault(key, []).append([
                document_id, raw_id, copy.deepcopy(prediction),
                query["label_correct"], query["joint_exact"],
                sorted(set(query["gold"]["spans"]) - set((prediction or {}).get("spans", []))),
                sorted(set((prediction or {}).get("spans", [])) - set(query["gold"]["spans"])),
                candidate_indices,
            ])
    expected = 6 * (2 * batch - 1)
    expected_slots = {
        (r["id"], f"batch{r['batch']}_{phase}")
        for r in seen.values() for phase in ("before", "after")
        if phase == "before" or r["batch"] < batch
    }
    if slots != expected_slots or len(seen_calls) != expected or len(exact_current) != (6 if batch == 1 else 12):
        raise ValueError("Complete own before/after prefix and exact-parent window required")
    return {
        "meaning": "Earlier-version executions, NOT current-parent failures. All original sources and Gold are in the cumulative cases. Old bank/tool identity must remain explicit. A shared episode outcome or reported skill ID is not per-skill causal value. Tool changes confound before/after publication changes. No inference-time agent reads this history.",
        "earlier_library_versions_except_current_parent": banks,
        "actual_previous_publications": events,
        "earlier_own_training_executions": observed,
        "historical_feedback_columns_each_row_uses_this_exact_order": list(HISTORY_COLUMNS),
        "hypothesis_grouped_historical_feedback": grouped,
        "exact_current_parent_observations_already_in_main_packet": exact_current,
        "all_available_earlier_answers_preserved_not_outcome_selected": True,
        "no_private_executor_narrative_or_invented_execution": True,
        "not_a_new_judge_router_curator_or_utility_gate": True,
    }


def grounded_teacher_input(body, training, history):
    """Align observed input/output and reference repeated Gold text in full sources.

    This is a NEW learning-signal design: historical public facts replace private
    local self-narratives. It is not asserted to reproduce an old teacher call.
    Original contracts, Gold, and public answers remain complete; repeated quoted
    Gold text resolves exactly to its unchanged source SPAN, without a summary.
    """
    result = copy.deepcopy(body)
    sources = {r["id"]: r for r in training}
    cases = {c["document_id"]: c for c in result["cumulative_seen_original_train_cases"]}
    parent = {s["id"]: s for s in result["complete_actual_parent_library"]}
    for document_id, case in cases.items():
        row = sources[document_id]
        if case["full_original_contract_with_spans"] != marked_text(row):
            raise ValueError("Teacher must retain every complete original source")
        if case["original_annotations"] != row["annotation_sets"][0]["annotations"]:
            raise ValueError("Teacher must retain all original annotations")
        observation = case["actual_own_same_parent_observation"]
        if observation is not None:
            observation["local_executor_trace"] = None
    for key, examples in result["hypothesis_grouped_grounded_feedback"].items():
        for example in examples:
            document_id = example["document_id"]
            row, case = sources[document_id], cases[document_id]
            expected = [
                {"original_span_index": i, "verbatim_source_text": row["text"][row["spans"][i][0]:row["spans"][i][1]]}
                for i in case["original_annotations"][key]["spans"]
            ]
            if example["all_original_annotated_source_spans"] != expected:
                raise ValueError("Repeated annotation text differs from exact original SPAN")
            example["all_original_annotated_source_spans"] = [
                {"original_span_index": v["original_span_index"]} for v in expected
            ]
            observation = case["actual_own_same_parent_observation"]
            if observation is None:
                continue
            delivery = observation["actual_source_conditioning_and_delivery"]
            current = example["actual_current_parent_observation"]
            current["actual_delivered_scoped_skill_ids"] = [
                sid for sid in delivery["actually_delivered_skill_ids"] if key in parent[sid]["hypothesis_ids"]
            ]
            candidates = observation["actual_candidates_as_delivered"]
            current["actually_offered_candidate_indices_not_membership_scores"] = None if candidates is None else [
                c["original_span_index"] for c in candidates[key]
            ]
            current["actual_source_layout_operation"] = delivery["actual_source_operations"].get(key)
    result["grouped_gold_text_reference"] = (
        "Each all_original_annotated_source_spans entry references the EXACT <SPAN i> "
        "text in that document_id's complete full_original_contract_with_spans below. "
        "No annotation, source sentence, or member is removed or summarized. The "
        "same Gold text is not repeated beside every hypothesis. Inspect the actual "
        "source when interpreting each contrasting label."
    )
    result["local_executor_trace_included_as_untrusted_data"] = False
    result["historical_intervention_evidence_not_current_parent_execution"] = history
    return result
