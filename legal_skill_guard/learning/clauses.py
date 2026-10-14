"""Factual source-only clause operations used by the published-query executor.

Only search/return original source records. Never decide legal labels, infer
facts, read annotations, repair native answers or choose skills for the lawyer.
Tokenizer/stemmer adapted from MIT-licensed ScienceClaw scilib/contracts.py,
commit e925f732c7ca435f557e88075bc47a58f1e984f1. Full notice in LICENSE.
No neural models, embeddings, trained classifier, file/network/tool execution.
"""

from __future__ import annotations

import hashlib
import json
import re

_WORD = re.compile(r"[a-z]+(?:'[a-z]+)?|\d+")
_SUFFIXES = (
    "ations",
    "ation",
    "ingly",
    "ments",
    "ment",
    "ings",
    "ing",
    "ies",
    "ied",
    "ers",
    "ed",
    "es",
    "ly",
    "s",
)


def _stem(word):
    if len(word) > 5:
        for suffix in _SUFFIXES:
            if word.endswith(suffix) and len(word) - len(suffix) >= 4:
                return word[: -len(suffix)]
    return word


def _tokens(text):
    # Preserve negation/modality: never use the author's stopword removal here.
    return tuple(_stem(word) for word in _WORD.findall(text.lower()))


def _contains(sequence, phrase):
    return any(
        sequence[i : i + len(phrase)] == phrase for i in range(len(sequence) - len(phrase) + 1)
    )


def _terms(values):
    if not isinstance(values, list) or len(values) > 32:
        raise ValueError("A term list must contain at most32 phrases; no truncation")
    result = []
    for phrase in values:
        if not isinstance(phrase, str) or not 0 < len(phrase) <= 256:
            raise ValueError("Each phrase must be nonempty and at most256 characters")
        tokens = _tokens(phrase)
        if not tokens:
            raise ValueError("A phrase must contain word/number tokens")
        result.append(tokens)
    return result


def original_clause_records(row):
    text, spans = row["text"], row["spans"]
    records = []
    for index, pair in enumerate(spans):
        if len(pair) != 2 or any(type(v) is not int for v in pair):
            raise ValueError("Original span coordinates must be integer pairs")
        start, end = pair
        if not 0 <= start <= end <= len(text):
            raise ValueError("Original span outside its source")
        records.append(
            {
                "original_span_index": index,
                "start": start,
                "end": end,
                "literal_original_text": text[start:end],
            }
        )
    return records


def find_original_clauses(records, all_phrases, any_phrases, none_phrases):
    """Mechanical ordered stem-token matches, not a relevance/semantic oracle."""
    all_terms, any_terms, none_terms = map(_terms, (all_phrases, any_phrases, none_phrases))
    if not all_terms and not any_terms:
        raise ValueError("No empty catch-all/default query")
    hits = []
    for record in records:
        sequence = _tokens(record["literal_original_text"])
        if (
            all(_contains(sequence, p) for p in all_terms)
            and (not any_terms or any(_contains(sequence, p) for p in any_terms))
            and not any(_contains(sequence, p) for p in none_terms)
        ):
            hits.append(record["original_span_index"])
    return hits


def context_original_clauses(records, anchor_indices, before, after):
    """Explicit neighbour access; no guessed semantic boundary or clipping."""
    if any(type(v) is not int or not 0 <= v <= 64 for v in (before, after)):
        raise ValueError("Context counts must be integers in0..64")
    indices = set()
    for anchor in anchor_indices:
        if type(anchor) is not int or not 0 <= anchor < len(records):
            raise ValueError("Anchor is not an original source span")
        indices.update(range(max(0, anchor - before), min(len(records), anchor + after + 1)))
    return [records[index] for index in sorted(indices)]


def execute_clause_queries(row, queries):
    """Execute the lawyer's bounded query arguments and log literal provenance.

    Only text and original span coordinates are read, even if a caller's row
    contains extra benchmark fields. Empty matches are returned unchanged, not
    substituted by another query/result. Nothing here maps observations to E/C/N.
    """
    if not isinstance(queries, list) or len(queries) > 128:
        raise ValueError("At most128 queries; no silent truncation")
    records = original_clause_records(row)
    source_hash = hashlib.sha256(
        json.dumps(
            {"text": row["text"], "spans": row["spans"]}, ensure_ascii=False, separators=(",", ":")
        ).encode()
    ).hexdigest()
    expected = {"query_id", "all_phrases", "any_phrases", "none_phrases", "before", "after"}
    ids = set()
    trace = []
    for query in queries:
        if set(query) != expected:
            raise ValueError("Exact public query fields required")
        key = query["query_id"]
        if not isinstance(key, str) or not 0 < len(key) <= 128 or key in ids:
            raise ValueError("Distinct nonempty query IDs required")
        ids.add(key)
        hits = find_original_clauses(
            records, query["all_phrases"], query["any_phrases"], query["none_phrases"]
        )
        context = context_original_clauses(records, hits, query["before"], query["after"])
        trace.append(
            {
                "query_id": key,
                "actual_query_arguments": query,
                "source_text_and_span_sha256": source_hash,
                "matched_original_span_indices": hits,
                "context_original_clauses": context,
                "no_match_is_not_a_legal_label": True,
            }
        )
    return trace
