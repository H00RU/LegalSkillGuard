"""Lossless format recovery of saved proposals, without inventing a program.

Only explicit type/serialization aliases are converted. Queries, source links,
branches, roles, rules and labels are never inferred. Every edit is reversible.
"""
from __future__ import annotations

import json
import math
import re
from copy import deepcopy

from .interfaces import FIELDS


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Ambiguous duplicate JSON key: " + key)
        result[key] = value
    return result


def recover_format(raw: str) -> dict:
    text = raw.strip()
    fenced = re.fullmatch(r"```(?:json)?[ \t]*\n(.*)\n```", text, re.S)
    if fenced:
        text = fenced[1]
    if len(text) > 1_048_576:
        return {"status": "unrecoverable_format", "reason": "size_limit", "events": []}
    depth, quoted, escaped = 0, False, False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "[{":
            depth += 1
            if depth > 64:
                return {"status": "unrecoverable_format", "reason": "nesting_limit_no_truncation", "events": []}
        elif char in "]}":
            depth -= 1
    try:
        original = json.loads(text, object_pairs_hook=_unique_object)
    except ValueError as exc:
        return {"status": "unrecoverable_format", "reason": str(exc), "events": []}
    if not isinstance(original, dict):
        return {"status": "unrecoverable_format", "reason": "root_is_not_object", "events": []}
    value, events = deepcopy(original), []

    def edit(path, before, after, reason):
        events.append({"path": path, "before": deepcopy(before), "after": deepcopy(after), "reason": reason})

    def visit(node, path):
        if isinstance(node, list):
            return [visit(x, [*path, i]) for i, x in enumerate(node)]
        if not isinstance(node, dict):
            return node
        # Explicit literal wrappers are not computation. Never synthesize an op
        # or choose an output variable for a missing query.
        if path[:3] == ["program", "body", "query"] and set(node) == {"literal"} and type(node["literal"]) in (str, int, bool):
            edit(path, node, node["literal"], "explicit_literal_wrapper")
            return node["literal"]
        kind, val = node.get("type"), node.get("value")
        binding_path = len(path) == 4 and type(path[-1]) is int and (
            path[:3] == ["program", "body", "bindings"] or
            path[0] == "interfaces" and type(path[1]) is int and path[2] == "bindings")
        if binding_path and kind == "integer" and isinstance(val, str) and re.fullmatch(r"-?(?:0|[1-9][0-9]*)", val):
            edit([*path, "value"], val, int(val), "canonical_integer_literal")
            node["value"] = int(val)
        elif binding_path and kind == "rational" and (type(val) is int or type(val) is float and math.isfinite(val)):
            # decode_slots already interprets rational values as Fraction(str(v)).
            edit([*path, "value"], val, str(val), "same_Fraction_str_literal")
            node["value"] = str(val)
        elif binding_path and kind == "boolean" and (type(val) is bool or val in ("true", "false")):
            converted = val == "true" if isinstance(val, str) else val
            edit([*path, "value"], val, converted, "explicit_boolean_literal")
            edit([*path, "type"], kind, "scalar", "boolean_is_scalar_bool")
            node["value"], node["type"] = converted, "scalar"
        elif binding_path and kind == "string" and isinstance(val, str):
            edit([*path, "type"], kind, "scalar", "string_is_scalar_text")
            node["type"] = "scalar"
        aliases = [k for k in ("allowed_semantic_fields", "allowed_semantic_field_names") if k in node]
        if len(path) == 2 and path[0] == "interfaces" and type(path[1]) is int and len(aliases) == 1 and "fields" not in node:
            alias = aliases[0]
            fields = node[alias]
            if isinstance(fields, list) and all(isinstance(f, str) and f in FIELDS for f in fields):
                events.append({"path": path, "rename_from": alias, "rename_to": "fields",
                               "reason": "explicit_fixed_field_list_alias"})
                node["fields"] = node.pop(alias)
        for key in list(node):
            node[key] = visit(node[key], [*path, key])
        return node

    value = visit(value, [])
    restored = deepcopy(value)
    for event in reversed(events):
        parent = restored
        for key in event["path"][:-1]:
            parent = parent[key]
        if "rename_from" in event:
            target = restored
            for key in event["path"]:
                target = target[key]
            target[event["rename_from"]] = target.pop(event["rename_to"])
        elif event["path"]:
            parent[event["path"][-1]] = deepcopy(event["before"])
        else:
            restored = deepcopy(event["before"])
    if restored != original:
        raise AssertionError("Format recovery was not reversible")
    return {"status": "normalized" if events or fenced else "unchanged", "proposal": value,
            "events": events, "reversible": True, "fence_removed": bool(fenced),
            "missing_semantics_synthesized": False, "labels_used": False}
