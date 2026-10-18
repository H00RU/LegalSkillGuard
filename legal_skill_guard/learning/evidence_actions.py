"""Source-only evidence bundles and explicitly selected native citation actions.

Reuses the existing trusted-teacher, resource-limited pure Python executor.
No learned score head, legal verdict, current Gold, answer repair or fallback.
Every original set remains expressible through singleton source actions.
"""

from __future__ import annotations

import copy
import json
import time

from jsonschema import ValidationError, validate

from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha
from .decision_evidence import procedure_payload
from .executable_features import MEMBER_PROGRAM_GUIDANCE_SCHEMA, _execute_pure_source, validate_source
from .publication import skill_record_schema

GROUP_GUIDANCE_SCHEMA = MEMBER_PROGRAM_GUIDANCE_SCHEMA
GROUP_ENTRYPOINT = "propose_evidence_groups"
GROUP_ARGUMENTS = ("text", "spans", "public_hypothesis_key", "ordinary_candidate_indices")

COMPILER_SYSTEM = (
    "Compile reusable evidence-acquisition skills from ONLY the supplied already-revealed "
    "TRAIN sources, original annotations and actual observations. The previous prose bank "
    "is fallible reference, not demonstrated success. Do not merely restate advice. "
    "Publish CREATE operations from the empty program representation, or explicit NOOP. "
    "Each guidance contains only python_source defining exactly "
    "propose_evidence_groups(text, spans, public_hypothesis_key, ordinary_candidate_indices). "
    "It returns a list of distinct source-index groups, each a sorted list of at least two "
    "distinct original integer SPAN indices. Return [] when no compound unit is supported. "
    "This is a normal no-match result, never an exception fallback. Discover observable "
    "relationships such as an operative lead-in and dependent limb, a split linked clause, "
    "or independently responsive repeated provisions. Do not indiscriminately join neighbors, "
    "all exceptions, or every occurrence of a topic. ordinary_candidate_indices is exactly "
    "the fallible shared tool's current selection; other source indices remain available. "
    "Programs receive ONLY current public text/coordinates, the public hypothesis key and "
    "those candidate indices: no current annotation, document ID, model or external access. "
    "Never emit E/C/NM, an answer table, confidence, a mandatory final evidence set, parties, "
    "dates, source fingerprints or fixed source indices. Compute indices from current input. "
    "All original singleton selections remain available; the lawyer chooses its legal label "
    "and citations. Bundles are optional source-grounded compound actions, not verified legal "
    "conclusions. Do not invent a hypothetical native gain from CPU group coverage. "
    "Use only documented pure builtins and string/container/regex attributes; re is supplied "
    "by the executor, so do not import it. Only function definitions and a module docstring "
    "may appear at top level. No imports, globals, decorators, reflection, tools or private "
    "thinking. Use plain unannotated signatures. No fixed program count or one-per-hypothesis "
    "rule. Keep the complete serialized library under4096 target8B tokens, aiming3200. "
    "Every structurally valid result is used without efficacy admission, retry or selected "
    "checkpoint. Return the exact differential JSON with auditable source provenance."
)


def validate_group_library(bank, labels):
    if len({s["id"] for s in bank}) != len(bank):
        raise ValueError("Duplicate evidence-group skill identity")
    for skill in bank:
        validate(skill, skill_record_schema(labels, guidance_schema=GROUP_GUIDANCE_SCHEMA))
        if len(set(skill["hypothesis_ids"])) != len(skill["hypothesis_ids"]):
            raise ValueError("Duplicate evidence-group public scope")
        validate_source(skill["guidance"]["python_source"], entrypoint=GROUP_ENTRYPOINT, arguments=GROUP_ARGUMENTS)


def execute_evidence_groups(bank, row, labels, proposals):
    """Execute all applicable source skills; errors propagate without substitutes."""
    validate_group_library(bank, labels)
    menus, receipts = {h: [] for h in labels}, []
    for skill in bank:
        for h in skill["hypothesis_ids"]:
            indices = [v["original_span_index"] for v in proposals["by_hypothesis"][h]["candidates"]]
            started = time.monotonic()
            groups = _execute_pure_source(skill["guidance"]["python_source"], row,
                GROUP_ENTRYPOINT, GROUP_ARGUMENTS, extra=(h, indices))
            if not isinstance(groups, list):
                raise ValueError("Group program must return a list; no repair")
            seen = set()
            for group in groups:
                if (not isinstance(group, list) or len(group) < 2
                        or any(type(i) is not int or not 0 <= i < len(row["spans"]) for i in group)
                        or group != sorted(set(group)) or tuple(group) in seen):
                    raise ValueError("Noncanonical, duplicate or invalid original source group; never normalize")
                seen.add(tuple(group))
                menus[h].append({"action_id": f"B{len(menus[h])}", "spans": list(group)})
            receipts.append({"skill_id": skill["id"], "hypothesis_id": h,
                "program_sha256": csha(skill["guidance"]),
                "public_source_sha256": csha({"text": row["text"], "spans": row["spans"]}),
                "actual_candidate_indices_argument": indices, "actual_groups": groups,
                "CPU_seconds": time.monotonic()-started,
                "no_Gold_document_ID_or_model_in_program_arguments": True})
    return menus, receipts


def _action_spec(action_id, members):
    return {"type": "object", "additionalProperties": False,
        "properties": {"action_id": {"type": "string", "enum": [action_id]},
                       "spans": {"type": "array", "enum": [members]}},
        "required": ["action_id", "spans"]}


def evidence_action_payload(row, labels, proposals, system, prose_bank, menus, *, atomic):
    """Same complete source/prose/candidates; compare bundles with atomic choices."""
    messages, schema = procedure_payload(row, labels, proposals, system, prose_bank, public_reason_words=64)
    body = json.loads(messages[1]["content"])
    for h in labels:
        body["hypotheses"][h]["compiled_evidence_actions"] = copy.deepcopy(menus[h])
    messages[0]["content"] += (
        " compiled_evidence_actions are fallible source-only compound citation proposals. "
        "They do not establish a legal relation or mandate any citation. Read their original "
        "members in the unchanged full source. Reject irrelevant groups and select any "
        "individual original source index when appropriate; all original sets remain available.")
    if atomic:
        schema["$defs"] = {"singleton": {"anyOf": [
            _action_spec(f"S{i}", [i]) for i in range(len(row["spans"]))]}}
        for h, spec in schema["properties"].items():
            items = {"anyOf": [{"$ref": "#/$defs/singleton"}, *[
                _action_spec(a["action_id"], a["spans"]) for a in menus[h]]]}
            for branch in spec["anyOf"]:
                fields = branch["properties"]
                previous = fields.pop("spans")
                fields["actions"] = {"type": "array", "items": copy.deepcopy(items),
                    **{k: previous[k] for k in ("minItems", "maxItems") if k in previous}}
                branch["required"] = ["reason", "choice", "actions"]
        old = "THEN decide choice and final spans yourself. Return reason, choice, spans in that order; no extra fields or model calls."
        if old not in messages[0]["content"]:
            raise ValueError("Original public-answer contract changed; no silent prompt adapter")
        messages[0]["content"] = messages[0]["content"].replace(old,
            "THEN decide choice and source evidence actions yourself. Return reason, choice, actions "
            "in that order; no extra fields or model calls.")
        messages[0]["content"] += (
            " Each action has action_id then its complete explicitly emitted spans payload. "
            "S<i> selects exactly [i] for ANY original index i. Each offered B action selects "
            "exactly its visible compound members; choosing one is optional. Use S actions "
            "instead whenever only part of a bundle is responsive. The decoder binds an action "
            "to its source-index payload, not to a legal verdict. The host only concatenates "
            "indices actually emitted inside chosen actions, never adds, filters or repairs them. "
            "NotMentioned uses [], while Entailment/Contradiction needs a responsive action.")
        body["output_contract"] = {"required_hypothesis_keys": list(labels),
            "field_order": ["reason", "choice", "actions"],
            "actions": "[{action_id: S<original index> or an offered B ID, spans: its complete bound original integer list}]",
            "every_original_set_expressible_as_singletons": True,
            "NM_empty_EC_nonempty": True, "no_host_added_members_or_verdict": True}
    messages[1]["content"] = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    return messages, schema


def action_metric_view(native, labels, schema):
    """Literal syntax projection only. Every returned index was explicitly emitted."""
    value, answer, errors = None, {}, []
    try:
        if native["finish_reason"] != "stop":
            raise ValueError("Incomplete native action answer; no substitute")
        value = json.loads(native["content"])
        validate(value, schema)
        answer = {h: {"reason": value[h]["reason"], "choice": value[h]["choice"],
            "spans": [i for action in value[h]["actions"] for i in action["spans"]]} for h in labels}
    except (ValueError, TypeError, KeyError, ValidationError) as error:
        errors.append(str(error))
    return {**native, "content": json.dumps(answer, ensure_ascii=False, separators=(",", ":")),
        "raw_id": None, "actual_native_raw_ids": [native["raw_id"]],
        "finish_reason": ("length" if native["finish_reason"] == "length" else None) if errors else "stop",
        "actual_native_action_value": value, "action_projection_errors": errors,
        "original_metric_view_not_native_server_response": True,
        "all_explicit_native_indices_labels_and_duplicates_preserved": not errors,
        "invalid_native_content": native["content"] if errors else None}
