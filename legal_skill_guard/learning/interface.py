"""Factual callable skills: public-scope source access, not legal verdict code.

Reuses the project's atomic differential editor and original native task. The
ScienceClaw-derived lexical primitive is separately attributed under MIT.
There is no legal predicate evaluator, current annotation access, answer repair,
automatic alternative query, effect gate or mandatory skill count.
"""

from __future__ import annotations

import copy
import json

from jsonschema import validate

from legal_skill_guard.task import solver_messages

from .clauses import execute_clause_queries
from .publication import (
    DELTA_TEACHER_SYSTEM,
    apply_differential_publication,
    differential_schema,
    skill_record_schema,
)

QUERY_API_SYSTEM = (
    " In this study each skill also contains queries: reusable factual source-access "
    "procedures, NOT programs deciding Entailment, Contradiction or NotMentioned. "
    "Each query has all_phrases, any_phrases, none_phrases and before/after neighbour "
    "counts. Matching is contiguous lower-case lightly stemmed word/number tokens "
    "within each original span: all terms required, at least one any term if present, "
    "no none term. At least one all or any phrase is required. No match is NOT a "
    "NotMentioned verdict; the final lawyer still receives the complete document. "
    "Only literal original spans and explicit neighbours can be returned. Negation "
    "and modality are not removed. Queries should locate an obligation, exception, "
    "definition or scope needing inspection, while guidance explains how the lawyer "
    "should examine those original clauses. Do not encode case identifiers, parties, "
    "dates, source indices, lookup tables or automatic legal labels in recipes. "
    "A skill can have no queries when guidance alone is warranted; do not force "
    "lexical actions or growth. Prefer a few compact reusable queries, not exhaustive "
    "word enumeration. Actual receipts in experience feedback are mechanical source "
    "matches, NOT verified legal relevance. Distinguish query miss, lawyer non-use, "
    "wrong relation and missing/excess final evidence. Never infer an error or "
    "trajectory in source-only data. Published recipes execute exactly as written "
    "when invoked under the supplied solver-delivery contract; a scope-only run "
    "executes every applicable recipe without a lawyer action-selection stage. "
    "The host does not reinterpret recipes or decide legal relevance."
)
TEACHER_SYSTEM = DELTA_TEACHER_SYSTEM + QUERY_API_SYSTEM


def query_schema():
    terms = {
        "type": "array",
        "maxItems": 32,
        "items": {"type": "string", "minLength": 1, "maxLength": 256},
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["all_phrases", "any_phrases", "none_phrases", "before", "after"],
        "properties": {
            k: copy.deepcopy(terms) for k in ("all_phrases", "any_phrases", "none_phrases")
        }
        | {
            "before": {"type": "integer", "minimum": 0, "maximum": 64},
            "after": {"type": "integer", "minimum": 0, "maximum": 64},
        },
    }


def callable_skill_schema(public_ids):
    schema = skill_record_schema(public_ids)
    schema["required"].append("queries")
    schema["properties"]["queries"] = {"type": "array", "maxItems": 8, "items": query_schema()}
    return schema


def publication_schema(public_ids, parent, seen_ids):
    schema = differential_schema(public_ids, parent, seen_ids)
    schema["properties"]["operations"]["items"]["properties"]["skill"] = {
        "anyOf": [callable_skill_schema(public_ids), {"type": "null"}]
    }
    return schema


def validate_queries(queries):
    # Use the actual executor to validate arguments on a synthetic empty source.
    # This is not a model test or a source/gold-dependent admission criterion.
    execute_clause_queries(
        {"text": "", "spans": []}, [{"query_id": str(i), **q} for i, q in enumerate(queries)]
    )


def publish(parent, value, public_ids, seen_ids):
    validate(value, publication_schema(public_ids, parent, seen_ids))
    for skill in parent:
        validate(skill, callable_skill_schema(public_ids))
        validate_queries(skill["queries"])
    for operation in value["operations"]:
        if operation["skill"] is not None:
            validate_queries(operation["skill"]["queries"])

    # Reuse the exact existing all-or-stop transaction semantics. Strip only the
    # added recipe field for the old editor, then restore the original full
    # record by identity, including unchanged parent records verbatim.
    def plain(skill):
        return {k: v for k, v in skill.items() if k != "queries"}

    reduced = copy.deepcopy(value)
    candidates = {s["id"]: s for s in parent}
    for operation in reduced["operations"]:
        if operation["skill"] is not None:
            candidates[operation["skill"]["id"]] = copy.deepcopy(operation["skill"])
            operation["skill"] = plain(operation["skill"])
    edited = apply_differential_publication(
        [plain(s) for s in parent], reduced, public_ids, seen_ids
    )
    return [copy.deepcopy(candidates[s["id"]]) for s in edited]


def execute_plan(row, labels, library, plan):
    # This is the original action-schema validation only. No native planner,
    # source-dependent router, new generic actions or alternative query is added.
    fields = {}
    for key in labels:
        ids = [s["id"] for s in library if key in s["hypothesis_ids"]]
        selected = (
            {"type": "array", "items": {"type": "string", "enum": ids}}
            if ids
            else {"type": "array", "items": {"type": "string"}, "maxItems": 0}
        )
        fields[key] = {
            "type": "object",
            "additionalProperties": False,
            "required": ["skill_ids", "generic_queries"],
            "properties": {
                "skill_ids": selected,
                "generic_queries": {"type": "array", "maxItems": 4, "items": query_schema()},
            },
        }
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": list(labels),
        "properties": fields,
    }
    validate(plan, schema)
    bank = {s["id"]: s for s in library}
    if len(bank) != len(library):
        raise ValueError("Duplicate published IDs; no repair")
    trace = {}
    for key in labels:
        selected = plan[key]["skill_ids"]
        if len(selected) != len(set(selected)):
            raise ValueError("Duplicate actual invocation IDs; no repair")
        invocations = []
        for sid in selected:
            queries = [{"query_id": f"skill_{i}", **q} for i, q in enumerate(bank[sid]["queries"])]
            invocations.append(
                {
                    "actually_invoked_skill_id": sid,
                    "exact_published_queries": copy.deepcopy(bank[sid]["queries"]),
                    "receipts": execute_clause_queries(row, queries),
                }
            )
        generic = [
            {"query_id": f"generic_{i}", **q} for i, q in enumerate(plan[key]["generic_queries"])
        ]
        trace[key] = {
            "published_skill_invocations": invocations,
            "explicit_generic_query_receipts": execute_clause_queries(row, generic),
        }
    return trace


def compact_receipts(trace):
    def compact(receipt):
        return {
            k: copy.deepcopy(v) for k, v in receipt.items() if k != "context_original_clauses"
        } | {
            "context_original_span_indices": [
                r["original_span_index"] for r in receipt["context_original_clauses"]
            ]
        }

    return {
        key: {
            "published_skill_invocations": [
                {**i, "receipts": [compact(r) for r in i["receipts"]]}
                for i in t["published_skill_invocations"]
            ],
            "explicit_generic_query_receipts": [
                compact(r) for r in t["explicit_generic_query_receipts"]
            ],
        }
        for key, t in trace.items()
    }


def final_messages(row, labels, library, system, trace=None):
    guidance = [{k: v for k, v in s.items() if k != "queries"} for s in library]
    messages, schema = solver_messages(row, labels, guidance, system)
    body = json.loads(messages[1]["content"])
    body["original_public_short_descriptions"] = {
        k: v["short_description"] for k, v in labels.items()
    }
    if trace is not None:
        body["actual_factual_query_execution"] = compact_receipts(trace)
        body["full_original_source_is_present_once_without_removed_clauses"] = True
        messages[0]["content"] += (
            " Factual query receipts are actual mechanical matches, not legal "
            "relevance decisions or gold. Inspect their exact referenced original "
            "SPAN text in the complete NDA above; the source appears once rather "
            "than duplicating its clauses per query. Empty hits do not imply "
            "NotMentioned. Neighbour clauses are context, not automatically "
            "supporting evidence. Decide every label and all evidence yourself "
            "from the FULL original NDA. You may cite any original span, not only "
            "query results. Do not execute further tools or alter source indices."
        )
    messages[1]["content"] = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    return messages, schema
