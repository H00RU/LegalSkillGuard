"""Explicit decisions on existing leads, with lossless original-index output.

Research execution candidate, not imported by the running production worker.
No judge, retrieval change, label correction or choice-dependent citation filter.
"""

from __future__ import annotations

import copy
import json

from jsonschema import validate

NOTE = (
    " For each hypothesis explicitly check EVERY original index in "
    "evidence_check_order. evidence_flags has exactly that order and length: "
    "true means you select that original SPAN as a member of the COMPLETE "
    "evidence set for your decision; false means you reject it as a citation. "
    "Evaluate each separately, including independently operative redundant "
    "support and necessary governing language, not just a shortest witness. "
    "A member need not independently prove the whole relation. A reading lead "
    "or neighbouring context is NOT automatically an evidence member. Use the "
    "entire original NDA to decide; fallible scores never dictate a flag. "
    "Cite any needed original SPAN outside that check order in other_spans. "
    "Then give the original choice and short reason. For NotMentioned select "
    "no evidence. The host only transposes your explicit selections; it will "
    "not add, erase, fix, or reconcile evidence with your choice."
)


def compile_membership(messages, span_count):
    """Change the evidence decision unit, not sources, leads, scores or task."""
    result = copy.deepcopy(messages)
    body = json.loads(result[1]["content"])
    properties, order = {}, {}
    for h, item in body["hypotheses"].items():
        ordinary = {c["original_span_index"] for c in item["fallible_evidence_candidates"]}
        additional = {c["original_span_index"] for c in item["additional_source_read_indices"]}
        checked = sorted(ordinary | additional)
        assert all(type(i) is int and 0 <= i < span_count for i in checked)
        order[h] = item["evidence_check_order"] = checked
        outside = sorted(set(range(span_count)) - set(checked))
        outside_schema = {"type": "array", "items": {"type": "integer"}}
        if outside:
            outside_schema["items"]["enum"] = outside
        else:
            outside_schema["maxItems"] = 0
        properties[h] = {
            "type": "object", "additionalProperties": False,
            "required": ["evidence_flags", "other_spans", "choice", "reason"],
            "properties": {
                "evidence_flags": {"type": "array", "items": {"type": "boolean"},
                    "minItems": len(checked), "maxItems": len(checked)},
                "other_spans": outside_schema,
                "choice": {"type": "string", "enum": ["Entailment", "Contradiction", "NotMentioned"]},
                "reason": {"type": "string"},
            },
        }
    result[0]["content"] = result[0]["content"].replace(
        "For each emit choice, spans, reason in that order.",
        "For each emit evidence_flags, other_spans, choice, reason in that order.",
    ).replace("Return choice, spans and reason only.", "Use the supplied evidence-membership output contract.") + NOTE
    assert "For each emit choice, spans, reason in that order." not in result[0]["content"]
    body["output_contract"] = {
        "required_hypothesis_keys": list(order),
        "fields_in_generation_order": ["evidence_flags", "other_spans", "choice", "reason"],
        "evidence_flags_are_aligned_to_each_evidence_check_order": True,
        "other_spans_may_cite_any_original_index_not_in_that_order": True,
        "choice_is_the_original_three_way_relation_not_a_host_decision": True,
        "schema_is_permitted_values_not_answers": True,
    }
    result[1]["content"] = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    schema = {"type": "object", "additionalProperties": False,
        "required": list(order), "properties": properties}
    return result, schema, order


def original_coordinate_view(value, order, schema):
    """Transpose explicit native bits; never consult a label, score or Gold."""
    validate(value, schema)
    return {h: {"choice": v["choice"], "spans": sorted({
        i for i, take in zip(order[h], v["evidence_flags"], strict=True) if take
    } | set(v["other_spans"])), "reason": v["reason"]} for h, v in value.items()}


def encode_original_coordinate_view(value, order):
    """Only for set-level round-trip proofs, never to generate a model answer."""
    return {h: {"evidence_flags": [i in v["spans"] for i in order[h]],
        "other_spans": sorted(set(v["spans"]) - set(order[h])),
        "choice": v["choice"], "reason": v["reason"]} for h, v in value.items()}
