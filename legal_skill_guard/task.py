"""Native task and binary original-span membership metrics; no semantic judge."""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping, Sequence
from typing import Any

from jsonschema import validate

CHOICES = ("Entailment", "Contradiction", "NotMentioned")


def coherent_native_schema(schema: Mapping[str, Any]) -> dict[str, Any]:
    """Encode the PUBLIC answer contract before generation, never repair a reply.

    The original scorer deliberately does not call this function: old invalid
    label/evidence combinations retain their actual historical penalties.
    All new treatment and control arms must use the same native constraint.
    """
    result = copy.deepcopy(schema)
    for key, original in result["properties"].items():
        nonneutral, neutral = copy.deepcopy(original), copy.deepcopy(original)
        nonneutral["properties"]["choice"]["enum"] = ["Entailment", "Contradiction"]
        nonneutral["properties"]["spans"]["minItems"] = 1
        neutral["properties"]["choice"]["enum"] = ["NotMentioned"]
        neutral["properties"]["spans"]["maxItems"] = 0
        result["properties"][key] = {"anyOf": [nonneutral, neutral]}
    return result


def marked_text(row: Mapping[str, Any]) -> str:
    parts, recovered, last = [], [], 0
    for index, (start, end) in enumerate(row["spans"]):
        if not (
            type(start) is int and type(end) is int and last <= start < end <= len(row["text"])
        ):
            raise ValueError("Invalid or overlapping original span coordinates")
        gap, span = row["text"][last:start], row["text"][start:end]
        parts.extend((gap, f"<SPAN {index}>", span, f"</SPAN {index}>"))
        recovered.extend((gap, span))
        last = end
    parts.append(row["text"][last:])
    recovered.append(row["text"][last:])
    if "".join(recovered) != row["text"]:
        raise ValueError("Full original contract changed")
    return "".join(parts)


def output_schema(
    row: Mapping[str, Any],
    keys: Sequence[str],
    library: Sequence[Mapping[str, Any]],
    *,
    reporting: bool = True,
) -> dict[str, Any]:
    if len(keys) != len(set(keys)) or not keys:
        raise ValueError("Original hypothesis identities must be distinct and nonempty")
    one: dict[str, Any] = {
        "type": "object",
        "additionalProperties": not reporting,
        "properties": {
            "choice": {"type": "string", "enum": list(CHOICES)},
            "spans": {
                "type": "array",
                "items": {"type": "integer", "enum": list(range(len(row["spans"])))},
            },
        },
        "required": ["choice", "spans"],
    }
    if reporting:
        ids = [s["id"] for s in library]
        if len(ids) != len(set(ids)) or any(not isinstance(i, str) or not i for i in ids):
            raise ValueError("Invalid published skill identities")
        used = (
            {"type": "array", "items": {"type": "string", "enum": ids}}
            if ids
            else {"type": "array", "items": {"type": "string"}, "maxItems": 0}
        )
        one["properties"].update({"reason": {"type": "string"}, "used_skill_ids": used})
        one["required"].extend(("reason", "used_skill_ids"))
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {key: one for key in keys},
        "required": list(keys),
    }


def render_library(library: Sequence[Mapping[str, Any]]) -> str:
    """The exact lossless library payload used for delivery and capacity metering."""
    return json.dumps(list(library), ensure_ascii=False, separators=(",", ":"))


def solver_messages(
    row: Mapping[str, Any],
    labels: Mapping[str, Any],
    library: Sequence[Mapping[str, Any]],
    system: str,
    *,
    show_span_value_enum_in_prompt: bool = True,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """Only original text and public hypotheses; no annotation access here."""
    keys = list(labels)
    schema = output_schema(row, keys, library)
    common = json.loads(json.dumps(schema["properties"][keys[0]]))
    if not show_span_value_enum_in_prompt:
        # Source markers identify the evidence; the native schema enforces its
        # range. Do not duplicate an answer-like numeric candidate list in text.
        common["properties"]["spans"]["items"] = {"type": "integer"}
    body = {
        "full_contract_with_original_span_markers": marked_text(row),
        "hypotheses": {key: labels[key]["hypothesis"] for key in keys},
        "output_contract": {
            "required_hypothesis_keys": keys,
            "common_schema_for_each_hypothesis": common,
            "schema_is_permitted_values_not_current_answers": True,
        },
    }
    rendered = render_library(library)
    messages = [
        {"role": "system", "content": system + "\nReusable skills: " + rendered},
        {"role": "user", "content": json.dumps(body, ensure_ascii=False)},
    ]
    return messages, schema


def original_feedback(
    response: Mapping[str, Any] | None,
    row: Mapping[str, Any],
    gold: Mapping[str, Any],
    keys: Sequence[str],
) -> dict[str, Any]:
    parsed, valid, error = None, False, None
    try:
        if response is None or response["finish_reason"] != "stop":
            raise ValueError("No complete native public answer")
        parsed = json.loads(response["content"])
        validate(parsed, output_schema(row, keys, [], reporting=False))
        valid = True
    except Exception as exc:
        error = repr(exc)
    queries = []
    for key in keys:
        g, prediction = gold[key], parsed[key] if valid else None
        gold_spans = set(g["spans"])
        if g["choice"] not in CHOICES or any(type(i) is not int for i in g["spans"]):
            raise ValueError("Malformed original benchmark annotation")
        nonneutral = g["choice"] != "NotMentioned"
        if bool(gold_spans) != nonneutral:
            raise ValueError("Original evidence presence differs from original class")
        predicted_spans = set(prediction["spans"]) if valid else set()
        tp, fp, fn = (
            len(gold_spans & predicted_spans),
            len(predicted_spans - gold_spans),
            len(gold_spans - predicted_spans),
        )
        f1 = 2 * tp / (2 * tp + fp + fn) if nonneutral else None
        correct = bool(valid and prediction["choice"] == g["choice"])
        queries.append(
            {
                "hypothesis_id": key,
                "gold": g,
                "prediction": prediction,
                "label_correct": correct,
                "gold_non_neutral": nonneutral,
                "evidence_tp": tp,
                "evidence_fp": fp,
                "evidence_fn": fn,
                "evidence_f1_gold_non_neutral": f1,
                "joint_exact": bool(correct and predicted_spans == gold_spans),
                "joint_soft": float(correct) * f1
                if nonneutral
                else float(correct and not predicted_spans),
            }
        )
    return {
        "public_valid": valid,
        "public_error": error,
        "parsed": parsed,
        "queries": queries,
        "native_public_answer_never_rewritten": True,
    }


def original_metrics(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    queries = [q for r in rows for q in r["queries"]]
    if not queries:
        raise ValueError("No original tasks to aggregate")
    positive = [q for q in queries if q["gold_non_neutral"]]
    tp, fp, fn = (sum(q["evidence_" + field] for q in positive) for field in ("tp", "fp", "fn"))
    neutral_correct = [q for q in queries if not q["gold_non_neutral"] and q["label_correct"]]
    return {
        "documents": len(rows),
        "hypotheses": len(queries),
        "label_correct": sum(q["label_correct"] for q in queries),
        "label_accuracy": sum(q["label_correct"] for q in queries) / len(queries),
        "gold_non_neutral_queries": len(positive),
        "evidence_tp": tp,
        "evidence_fp": fp,
        "evidence_fn": fn,
        "evidence_micro_f1_gold_non_neutral": 2 * tp / (2 * tp + fp + fn) if positive else None,
        "evidence_query_mean_f1_gold_non_neutral": sum(
            q["evidence_f1_gold_non_neutral"] for q in positive
        )
        / len(positive)
        if positive
        else None,
        "joint_exact_correct": sum(q["joint_exact"] for q in queries),
        "joint_soft_mean": sum(q["joint_soft"] for q in queries) / len(queries),
        "public_valid_documents": sum(r["public_valid"] for r in rows),
        "length_cutoffs": sum(
            bool(r["response"] and r["response"]["finish_reason"] == "length") for r in rows
        ),
        "class_denominators": {
            label: {
                "n": sum(q["gold"]["choice"] == label for q in queries),
                "correct": sum(
                    q["gold"]["choice"] == label and q["label_correct"] for q in queries
                ),
            }
            for label in CHOICES
        },
        "correct_nm_with_nonempty_evidence": sum(
            bool(q["prediction"]["spans"]) for q in neutral_correct
        ),
        "correct_nm_with_empty_evidence": sum(
            not q["prediction"]["spans"] for q in neutral_correct
        ),
        "nonneutral_label_and_all_evidence_correct": sum(q["joint_exact"] for q in positive),
        "reported_skill_use_queries": sum(
            bool(q["prediction"] and q["prediction"].get("used_skill_ids")) for q in queries
        ),
        "reported_skill_use_not_internal_causal_proof": True,
        "usage": {
            field: sum((r["response"] or {})[field] if r["response"] else 0 for r in rows)
            for field in ("prompt_tokens", "completion_tokens")
        },
    }
