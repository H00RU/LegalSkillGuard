"""Lossless skill-field serialization, not routing or semantic compilation.

Every original scope, word, conditional relation and record order is preserved.
Only repeated field names move to a shared header. No model, verdict, eviction,
answer operation, score admission or on-error alternative is introduced.
"""

from __future__ import annotations

import copy
import json

from .task_local import SEMANTIC_FIELDS

COLUMNS = ("id", *SEMANTIC_FIELDS)
TABLE_NOTICE = (
    " Applicable skills are lossless rows under skill_table_columns, in that "
    "column order: id, when, inspection, relation_if_established, "
    "evidence_requirement. All original words and public applicability remain. "
    "Read each row as the same named-field record, not an automatic verdict."
)


def encode_skill_projection(projection):
    rows = {}
    for h, records in projection.items():
        rows[h] = []
        for record in records:
            if set(record) != {"id", "guidance"} or set(record["guidance"]) != set(SEMANTIC_FIELDS):
                raise ValueError("Exact original public semantic fields required; never drop extras")
            rows[h].append([record["id"], *[copy.deepcopy(record["guidance"][k]) for k in SEMANTIC_FIELDS]])
    return {"columns": list(COLUMNS), "by_hypothesis": rows}


def decode_skill_projection(table):
    if set(table) != {"columns", "by_hypothesis"} or table["columns"] != list(COLUMNS):
        raise ValueError("Declared exact shared header required; no guessed decoding")
    result = {}
    for h, rows in table["by_hypothesis"].items():
        result[h] = []
        for row in rows:
            if not isinstance(row, list) or len(row) != len(COLUMNS):
                raise ValueError("Incomplete skill row; no padding or default values")
            result[h].append({"id": row[0], "guidance": dict(zip(SEMANTIC_FIELDS, copy.deepcopy(row[1:]), strict=True))})
    return result


def scoped_budget_view(projection):
    # Empty memory has no table/header on the wire. This is the ordinary zero-data
    # input, not an exception path; its existing empty-arm requests stay exact.
    return encode_skill_projection(projection) if any(projection.values()) else projection


def table_skill_messages(messages, delivery):
    result, trace = copy.deepcopy(messages), copy.deepcopy(delivery)
    projection = trace["actual_task_local_projection"]
    trace["actual_task_local_projection_is_lossless_decoded_semantic_view"] = True
    trace["skill_delivery_encoding"] = "scoped_lossless_table_v1"
    trace["actual_wire_skill_table"] = None
    if not any(projection.values()):
        assert result == messages  # No skills: no new header or prompt alteration.
        return result, trace
    table = encode_skill_projection(projection)
    if decode_skill_projection(table) != projection:
        raise ValueError("Lossless skill encoding changed its actual records")
    body = json.loads(result[1]["content"])
    if set(body["hypotheses"]) != set(projection):
        raise ValueError("Exact original hypothesis scope required")
    for h, records in projection.items():
        if body["hypotheses"][h]["applicable_published_skills"] != records:
            raise ValueError("Wire skill records differ from their semantic projection")
        body["hypotheses"][h]["applicable_published_skills"] = table["by_hypothesis"][h]
    body["skill_table_columns"] = list(COLUMNS)
    result[0]["content"] += TABLE_NOTICE
    result[1]["content"] = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    trace["actual_wire_skill_table"] = table
    return result, trace
