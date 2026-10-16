"""Annotation-withheld training audit; never an inference judge or edit gate."""

from __future__ import annotations

import copy

from jsonschema import validate

from legal_skill_guard.task import CHOICES, marked_text


SOURCE_AUDIT_SYSTEM = (
    "Audit the supplied fallible legal skills against ONLY the complete original "
    "sources and public hypotheses provided. No tools, outside law, annotations, "
    "learner answers or invented outcomes. The parent was previously learned, so "
    "its claims are not independent truth. For EVERY parent skill and EVERY "
    "source/public-hypothesis pair in its scope, inspect whether its COMPLETE "
    "decisive condition is actually established. A topic cue, a related clause, "
    "an actor/action with a different trigger, or auxiliary governing language "
    "does not by itself establish that inference. Do not assume each source "
    "fragment independently proves the hypothesis. Evaluate the actual actor, "
    "action, object, condition, exception, quantifier and original polarity. "
    "Return r as the ORIGINAL relation only when this skill and the complete "
    "source establish it; otherwise null. Null means no sufficient skill "
    "inference, NEVER automatic NotMentioned or a prediction that Gold is absent. "
    "Do not force every source to fit a skill. A mixed inspection may establish "
    "different relations in different sources; it need not settle every case. "
    "In each check, d is the source ID, h its exact public hypothesis, r the "
    "established relation or null, s the inspected original span indices. These "
    "are claimed inspected groups, not benchmark evidence or verified proofs. "
    "For a null check s may name a near-miss group or be empty. No case-level "
    "prose is required. Give one concise source-grounded public finding per "
    "skill explaining actual scope and insufficient conditions; no private "
    "reasoning. Preserve all skill IDs and cover all declared pairs exactly "
    "once. Do not edit skills, choose a bank, grade the lawyer or invent labels."
)

EDITOR_AUDIT_INSTRUCTION = (
    " This run additionally supplies a separate annotation-withheld source "
    "audit of the EXACT parent against all cumulative TRAIN sources. It used "
    "the same authorized teacher, not an independent oracle/model, and may be "
    "wrong. No current annotations, lawyer answers or outcomes were in that "
    "request, but its parent was already Gold-trained. Use its explicit "
    "condition/source claims together with original annotations and actual "
    "learner observations to locate unsupported generalizations. r=null says "
    "the skill did not establish a relation; it is not NM, a failure, or a "
    "requirement to broaden the rule until every positive case fits. Compare "
    "contrasting sources for the SAME hypothesis. Separate sufficient "
    "conditions from clauses merely co-occurring with a labeled case and from "
    "auxiliary members of a complete annotated evidence set. An annotated "
    "member need not be independently sufficient. Preserve it as contextual "
    "evidence when appropriate without promoting it into an alternative "
    "decisive condition. Repair the generic actor/action/trigger/exception "
    "boundary, not a case-specific exception or another unconditional warning. "
    "Check the complete parent, including unchanged skills with contradictory "
    "seen cases. Audit/Gold differences are diagnostic data, never an automatic "
    "edit, quality score, acceptance threshold, deletion or rollback. No fixed "
    "number of edits. All structurally valid edits will be published. Audit "
    "case IDs/groups stay training-only; lawyer authority and output remain "
    "unchanged. Return only the existing differential publication schema."
)


def source_audit_input(bank, rows, labels):
    """Construct this request without reading row annotations or model outcomes."""
    if not bank or not rows:
        raise ValueError("A source audit requires a nonempty actual parent and seen sources")
    return {
        "actual_parent_library": copy.deepcopy(bank),
        "public_hypotheses": copy.deepcopy(labels),
        "complete_original_sources_without_annotation_sets": [
            {"document_id": row["id"], "full_original_contract_with_spans": marked_text(row)}
            for row in rows
        ],
        "current_annotations_learner_answers_outcomes_and_future_sources_withheld": True,
        "parent_is_prior_gold_trained_not_independent_truth": True,
    }


def source_audit_schema(bank, rows, labels):
    return {
        "type": "object", "additionalProperties": False, "required": ["skill_reports"],
        "properties": {"skill_reports": {
            "type": "array", "minItems": len(bank), "maxItems": len(bank),
            "items": {
                "type": "object", "additionalProperties": False,
                "required": ["skill_id", "finding", "checks"],
                "properties": {
                    "skill_id": {"type": "string", "enum": [s["id"] for s in bank]},
                    "finding": {"type": "string", "minLength": 1},
                    "checks": {"type": "array", "items": {
                        "type": "object", "additionalProperties": False,
                        "required": ["d", "h", "r", "s"],
                        "properties": {
                            "d": {"type": "integer", "enum": [r["id"] for r in rows]},
                            "h": {"type": "string", "enum": list(labels)},
                            "r": {"anyOf": [{"type": "string", "enum": list(CHOICES)}, {"type": "null"}]},
                            "s": {"type": "array", "items": {"type": "integer", "minimum": 0}},
                        },
                    }},
                },
            },
        }},
    }


def checked_source_audit(report, bank, rows, labels):
    """Verify references/coverage only; retain even every semantic disagreement."""
    validate(report, source_audit_schema(bank, rows, labels))
    sources, skills = {r["id"]: r for r in rows}, {s["id"]: s for s in bank}
    reports = report["skill_reports"]
    if len(reports) != len({r["skill_id"] for r in reports}) or {r["skill_id"] for r in reports} != set(skills):
        raise ValueError("Source audit must cover each exact parent skill once")
    differences, total, established = [], 0, 0
    for record in reports:
        expected = {(d, h) for d in sources for h in skills[record["skill_id"]]["hypothesis_ids"]}
        pairs = [(c["d"], c["h"]) for c in record["checks"]]
        if len(pairs) != len(set(pairs)) or set(pairs) != expected:
            raise ValueError("Source audit must cover all and only cumulative source/scope pairs")
        for check in record["checks"]:
            row = sources[check["d"]]
            if len(check["s"]) != len(set(check["s"])) or any(
                type(i) is not int or not 0 <= i < len(row["spans"]) for i in check["s"]
            ):
                raise ValueError("Source audit references must be distinct existing original spans")
            total += 1
            established += check["r"] is not None
            gold = row["annotation_sets"][0]["annotations"][check["h"]]["choice"]
            if check["r"] is not None and check["r"] != gold:
                differences.append({"skill_id": record["skill_id"], "d": check["d"],
                                    "h": check["h"], "claimed_relation": check["r"], "original_train_label": gold})
    return {
        "source_scope_checks": total, "nonnull_condition_claims": established,
        "nonnull_claim_original_training_label_differences": differences,
        "null_is_not_a_case_label_or_required_rule_coverage": True,
        "all_original_sources_gold_and_observations_remain_available_to_editor": True,
        "source_audit_is_fallible_and_not_semantically_verified_by_host": True,
        "no_effect_gate_bank_selection_or_answer_repair": True,
    }
