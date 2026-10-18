"""Teacher-only, readable lossless catalogs. No training/inference decisions."""

import json
from collections import Counter
from copy import deepcopy

from .packing import unpack_cases

LEGEND = (
    "Lossless teacher catalogs v2. Every original source remains verbatim. "
    "An object containing only text_ref is exactly the verbatim_text_catalog "
    "entry at that zero-based index, not a summary. Table columns_ref refers "
    "to the ordered column_catalog entry. Expand those two references first. "
    "If legacy all_seen_train_cases is present, actual_global_query_bodies stores all exact query bodies in an ordered "
    "record table. Each plan generic_queries and receipt actual_query_arguments "
    "is a zero-based row reference to this global query table, not a case-local "
    "table. Each observation still has its own receipt table; identical receipt "
    "rows are stored once, but every hypothesis invocation and generic action "
    "retains its ordered row references, including repeated actions. Then "
    "apply the original lossless_teacher_encoding instructions in body when present. "
    "For other teacher bodies, restore references and the derived fields below. All supplied "
    "Tables with derived_original_member_feedback=true omit two derivable columns: "
    "proposed_original_indices is sorted(original_member_hits plus "
    "unannotated_read_proposals_not_false_legal_claims); "
    "original_non_neutral_member_target is original_choice != NotMentioned. "
    "source strings are preserved; explicitly partial historical contexts remain partial. "
    "No supplied source, annotation, public observation, feedback, historical bank, "
    "duplicate action, or ordering is removed. No-match is not a legal label."
)

MEMBER_COLUMNS = ["proposed_original_indices", "original_choice", "original_non_neutral_member_target",
                  "original_member_hits", "original_member_misses",
                  "unannotated_read_proposals_not_false_legal_claims"]


def canonical(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def encode_teacher_body(original):
    body = deepcopy(original)
    global_queries, query_lookup = [], {}
    query_columns = None
    legacy_cases = "all_seen_train_cases" in body
    for case in body.get("all_seen_train_cases", []):
        local_table = case.pop("actual_query_bodies")
        local_refs = []
        if local_table:
            if query_columns is None:
                query_columns = local_table["columns"]
            if local_table["columns"] != query_columns:
                raise ValueError("Incompatible actual query columns; no repair")
            for row in local_table["rows"]:
                identity = canonical(row)
                if identity not in query_lookup:
                    query_lookup[identity] = len(global_queries)
                    global_queries.append(deepcopy(row))
                local_refs.append(query_lookup[identity])
        for field in (
            "actual_before_publication_observations",
            "actual_prior_post_publication_observations",
        ):
            for obs in case[field]:
                plan = obs["actual_plan"]
                column = plan["columns"].index("generic_queries")
                for row in plan["rows"]:
                    row[column] = [local_refs[i] for i in row[column]]
                trace = obs["actual_factual_trace"]
                receipts = trace["receipts"]
                if not receipts:
                    continue
                column = receipts["columns"].index("actual_query_arguments")
                unique, lookup, refs = [], {}, []
                for row in receipts["rows"]:
                    row[column] = local_refs[row[column]]
                    identity = canonical(row)
                    if identity not in lookup:
                        lookup[identity] = len(unique)
                        unique.append(deepcopy(row))
                    refs.append(lookup[identity])
                receipts["rows"] = unique
                by_h = trace["by_hypothesis"]
                skill_col = by_h["columns"].index("published_skill_invocations")
                generic_col = by_h["columns"].index("explicit_generic_query_receipts")
                for row in by_h["rows"]:
                    row[generic_col] = [refs[i] for i in row[generic_col]]
                    invocations = row[skill_col]
                    if invocations:
                        inv_col = invocations["columns"].index("receipts")
                        for invocation in invocations["rows"]:
                            invocation[inv_col] = [refs[i] for i in invocation[inv_col]]
    query_table = (
        {"encoding": "record-table-v1", "columns": query_columns, "rows": global_queries}
        if global_queries
        else []
    )
    if legacy_cases:
        body["actual_global_query_bodies"] = query_table
    columns, column_lookup = [], {}

    def share_columns(value):
        if isinstance(value, list):
            return [share_columns(v) for v in value]
        if not isinstance(value, dict):
            return value
        result = {k: share_columns(v) for k, v in value.items()}
        if value.get("encoding") in ("record-table-v1", "keyed-record-table-v1"):
            selected_columns = value["columns"]
            if selected_columns == MEMBER_COLUMNS:
                for row in value["rows"]:
                    if (row[0] != sorted(row[3]+row[5]) or type(row[2]) is not bool
                            or row[2] != (row[1] != "NotMentioned")):
                        raise ValueError("Inconsistent member feedback; never normalize or repair")
                selected_columns = [MEMBER_COLUMNS[i] for i in (1,3,4,5)]
                result["rows"] = [[row[i] for i in (1,3,4,5)] for row in result["rows"]]
                result["derived_original_member_feedback"] = True
            identity = canonical(selected_columns)
            if identity not in column_lookup:
                column_lookup[identity] = len(columns)
                columns.append(deepcopy(selected_columns))
            result.pop("columns")
            result["columns_ref"] = column_lookup[identity]
        return result

    body = share_columns(body)
    counts = Counter()
    plain_fields = {"encoding", "original_full_contract_with_spans", "lossless_teacher_encoding"}

    def count_text(value):
        if isinstance(value, str):
            counts[value] += 1
        elif isinstance(value, list):
            for item in value:
                count_text(item)
        elif isinstance(value, dict):
            if set(value) == {"text_ref"}:
                raise ValueError("Reserved text-reference object in original data")
            for key, item in value.items():
                if key not in plain_fields:
                    count_text(item)

    count_text(body)
    texts = [
        s
        for s, n in counts.items()
        if len(s) >= 20 and n > 1 and (len(canonical(s)) - 18) * (n - 1) > len(canonical(s)) + 4
    ]
    text_lookup = {s: i for i, s in enumerate(texts)}

    def share_text(value):
        if isinstance(value, str):
            return {"text_ref": text_lookup[value]} if value in text_lookup else value
        if isinstance(value, list):
            return [share_text(v) for v in value]
        if isinstance(value, dict):
            return {k: (v if k in plain_fields else share_text(v)) for k, v in value.items()}
        return value

    payload = {
        "encoding": "lossless-teacher-catalog-v2",
        "legend": LEGEND,
        "column_catalog": columns,
        "verbatim_text_catalog": texts,
        "body": share_text(body),
    }
    expected = deepcopy(original)
    if legacy_cases:
        expected["all_seen_train_cases"] = unpack_cases(expected["all_seen_train_cases"])
    if decode_teacher_body(payload) != expected:
        raise ValueError("Complete teacher source/observations/history roundtrip differs")
    return payload


def decode_teacher_body(payload):
    if payload["encoding"] != "lossless-teacher-catalog-v2":
        raise ValueError("Unexpected encoding")

    def restore(value):
        if isinstance(value, list):
            return [restore(v) for v in value]
        if not isinstance(value, dict):
            return value
        if set(value) == {"text_ref"}:
            return deepcopy(payload["verbatim_text_catalog"][value["text_ref"]])
        result = {k: restore(v) for k, v in value.items() if k != "columns_ref"}
        if "columns_ref" in value:
            result["columns"] = deepcopy(payload["column_catalog"][value["columns_ref"]])
        if result.pop("derived_original_member_feedback", False):
            if result["columns"] != [MEMBER_COLUMNS[i] for i in (1,3,4,5)]:
                raise ValueError("Unexpected derived-member columns")
            result["rows"] = [[sorted(hit+unannotated), choice, choice != "NotMentioned",
                               hit, miss, unannotated]
                              for choice,hit,miss,unannotated in result["rows"]]
            result["columns"] = deepcopy(MEMBER_COLUMNS)
        return result

    body = restore(payload["body"])
    if "all_seen_train_cases" in body:
        queries = body.pop("actual_global_query_bodies")
        for case in body["all_seen_train_cases"]:
            case["actual_query_bodies"] = deepcopy(queries)
        body["all_seen_train_cases"] = unpack_cases(body["all_seen_train_cases"])
    return body
