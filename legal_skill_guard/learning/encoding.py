"""Lossless receipt encoding shared by the current solver and teacher pipeline.

Remove repeated audit hashes/constants and a duplicate published-query copy.
Every actual invocation, argument, match and original context index survives.
No result selection, recomputation, deduplication, legal verdict or repair.
"""

from copy import deepcopy


def encode_receipts(compact_trace):
    data = deepcopy(compact_trace)
    source_hashes = set()

    def encode_one(receipt):
        if receipt["no_match_is_not_a_legal_label"] is not True:
            raise ValueError("Unexpected receipt semantics; no conversion")
        source_hashes.add(receipt.pop("source_text_and_span_sha256"))
        receipt.pop("no_match_is_not_a_legal_label")
        if receipt["actual_query_arguments"].pop("query_id") != receipt["query_id"]:
            raise ValueError("Actual query identity differs; no repair")

    for record in data.values():
        for invocation in record["published_skill_invocations"]:
            expected = [
                {k: v for k, v in r["actual_query_arguments"].items() if k != "query_id"}
                for r in invocation["receipts"]
            ]
            if invocation["exact_published_queries"] != expected:
                raise ValueError("Published recipe differs from actual executed bodies")
            invocation.pop("exact_published_queries")
            for receipt in invocation["receipts"]:
                encode_one(receipt)
        for receipt in record["explicit_generic_query_receipts"]:
            encode_one(receipt)
    if len(source_hashes) > 1:
        raise ValueError("One complete original document required; no source mixing")
    return {
        "encoding": "lossless-factual-receipts-v1",
        "source_text_and_span_sha256": next(iter(source_hashes), None),
        "no_match_is_not_a_legal_label": True,
        "by_hypothesis": data,
    }


def decode_receipts(encoded):
    if encoded["encoding"] != "lossless-factual-receipts-v1":
        raise ValueError("Wrong encoding contract")
    data = deepcopy(encoded["by_hypothesis"])

    def decode_one(receipt):
        receipt["source_text_and_span_sha256"] = encoded["source_text_and_span_sha256"]
        receipt["no_match_is_not_a_legal_label"] = encoded["no_match_is_not_a_legal_label"]
        receipt["actual_query_arguments"]["query_id"] = receipt["query_id"]

    for record in data.values():
        for invocation in record["published_skill_invocations"]:
            for receipt in invocation["receipts"]:
                decode_one(receipt)
            invocation["exact_published_queries"] = [
                {k: v for k, v in r["actual_query_arguments"].items() if k != "query_id"}
                for r in invocation["receipts"]
            ]
        for receipt in record["explicit_generic_query_receipts"]:
            decode_one(receipt)
    return data


def lean_final_messages(messages):
    """Same full source, guidance, queries and actual receipts; encoding only."""
    import json

    copied = deepcopy(messages)
    body = json.loads(copied[1]["content"])
    original = body["actual_factual_query_execution"]
    encoded = encode_receipts(original)
    if decode_receipts(encoded) != original:
        raise ValueError("Lossless roundtrip failed")
    body["actual_factual_query_execution"] = encoded
    copied[1]["content"] = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    copied[0]["content"] += (
        " Receipt encoding is lossless-factual-receipts-v1. by_hypothesis holds "
        "the same actual skill and generic-query executions. All actual query "
        "arguments, matches and context indices are unchanged. The source hash "
        "and no-match semantics are written once for this complete document. "
        "The exact published query bodies are already present as each executed "
        "receipt actual_query_arguments; query_id is written once per receipt. "
        "These are factual matches, never legal relevance or a legal verdict."
    )
    return copied
