"""Readable, reversible teacher tables; no observations or source text selected."""

from copy import deepcopy

from .encoding import decode_receipts, encode_receipts

LEGEND = (
    "Teacher-only lossless-observation-tables-v1 serialization: a record table "
    "has columns and ordered rows; zip each row with columns to reconstruct its "
    "object. A keyed-record table additionally has ordered keys, one per row; "
    "each key identifies the reconstructed object. Empty arrays/maps are literal. "
    "Nested tables follow the same rule. No rows, duplicates, ordering, source "
    "text, annotations, plans, public answers or component feedback are removed. "
    "Factual trace uses lossless-factual-receipts-v1: its source hash and no-match "
    "constant apply to every receipt; restore query_id inside actual_query_arguments "
    "from the receipt query_id. exact_published_queries is exactly the executed "
    "argument bodies without query_id, in order. context_original_span_indices "
    "refer to the original marked source, not a judgement of legal relevance. "
    "Each case actual_query_bodies table stores exact query objects once; "
    "actual_query_arguments and each plan generic_queries entry are zero-based "
    "references into that table. Repeated references mean repeated actions, "
    "not deduplication. original-index-runs-v1 stores inclusive [start,end] "
    "runs in the exact original order, with no removed indices. For the factual "
    "trace, receipts is one ordered table and each invocation/generic receipt "
    "entry is its zero-based row reference. Receipt matched/context indices "
    "are inclusive runs; repeated receipt row references still mean repeated "
    "executions. The decoder reconstructs the original nested trace exactly."
)


def table(records, keys=None):
    if not records:
        return {} if keys is not None else []
    columns = list(records[0])
    if any(list(record) != columns for record in records):
        raise ValueError("Nonuniform record fields; no omitted or repaired field")
    value = {
        "encoding": "record-table-v1",
        "columns": columns,
        "rows": [[record[column] for column in columns] for record in records],
    }
    if keys is not None:
        value["encoding"] = "keyed-record-table-v1"
        value["keys"] = list(keys)
    return value


def expand(value):
    if isinstance(value, list):
        return [expand(item) for item in value]
    if not isinstance(value, dict):
        return value
    if value.get("encoding") in ("record-table-v1", "keyed-record-table-v1"):
        records = [
            {column: expand(item) for column, item in zip(value["columns"], row, strict=True)}
            for row in value["rows"]
        ]
        return dict(zip(value["keys"], records, strict=True)) if "keys" in value else records
    return {key: expand(item) for key, item in value.items()}


def keyed(records):
    return table(list(records.values()), records)


def indices(values):
    if not values:
        return []
    runs = []
    for value in values:
        if runs and value == runs[-1][1] + 1:
            runs[-1][1] = value
        else:
            runs.append([value, value])
    # Fixed representation for these exact ordered source indices, not sampling.
    return runs


def pack_cases(cases):
    result = deepcopy(cases)
    for case in result:
        queries, query_lookup = [], {}

        def query_ref(value):
            import json

            identity = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
            if identity not in query_lookup:
                query_lookup[identity] = len(queries)
                queries.append(deepcopy(value))
            return query_lookup[identity]

        case["original_annotations"] = keyed(case["original_annotations"])
        for field in (
            "actual_before_publication_observations",
            "actual_prior_post_publication_observations",
        ):
            for observation in case.get(field, []):
                if observation["parsed_public_answer"] is not None:
                    observation["parsed_public_answer"] = keyed(observation["parsed_public_answer"])
                plan = observation["actual_plan"]
                for item in plan.values():
                    item["generic_queries"] = [query_ref(q) for q in item["generic_queries"]]
                observation["actual_plan"] = keyed(plan)
                trace = encode_receipts(observation["actual_factual_trace"])
                all_receipts = []

                def receipt_ref(receipt):
                    receipt["actual_query_arguments"] = query_ref(receipt["actual_query_arguments"])
                    for name in ("matched_original_span_indices", "context_original_span_indices"):
                        receipt[name] = indices(receipt[name])
                    index = len(all_receipts)
                    all_receipts.append(receipt)
                    return index

                for item in trace["by_hypothesis"].values():
                    for invocation in item["published_skill_invocations"]:
                        invocation["receipts"] = [receipt_ref(r) for r in invocation["receipts"]]
                    item["published_skill_invocations"] = table(item["published_skill_invocations"])
                    item["explicit_generic_query_receipts"] = [
                        receipt_ref(r) for r in item["explicit_generic_query_receipts"]
                    ]
                trace["receipts"] = table(all_receipts)
                trace["by_hypothesis"] = keyed(trace["by_hypothesis"])
                observation["actual_factual_trace"] = trace
                observation["original_component_feedback"] = table(
                    observation["original_component_feedback"]
                )
        case["actual_query_bodies"] = table(queries)
    if unpack_cases(result) != cases:
        raise ValueError("Teacher table roundtrip not exact")
    return result


def unpack_cases(cases):
    result = expand(deepcopy(cases))
    for case in result:
        queries = case.pop("actual_query_bodies")
        for field in (
            "actual_before_publication_observations",
            "actual_prior_post_publication_observations",
        ):
            for observation in case.get(field, []):
                for item in observation["actual_plan"].values():
                    item["generic_queries"] = [
                        deepcopy(queries[index]) for index in item["generic_queries"]
                    ]
                trace = observation["actual_factual_trace"]
                all_receipts = trace.pop("receipts")
                for receipt in all_receipts:
                    receipt["actual_query_arguments"] = deepcopy(
                        queries[receipt["actual_query_arguments"]]
                    )
                    for name in ("matched_original_span_indices", "context_original_span_indices"):
                        receipt[name] = [
                            index for start, end in receipt[name] for index in range(start, end + 1)
                        ]
                for item in trace["by_hypothesis"].values():
                    item["explicit_generic_query_receipts"] = [
                        deepcopy(all_receipts[index])
                        for index in item["explicit_generic_query_receipts"]
                    ]
                    for invocation in item["published_skill_invocations"]:
                        invocation["receipts"] = [
                            deepcopy(all_receipts[index]) for index in invocation["receipts"]
                        ]
                observation["actual_factual_trace"] = decode_receipts(trace)
    return result
