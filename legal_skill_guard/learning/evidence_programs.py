"""Executable source-query features, learned outside a frozen lawyer.

Attributed ScienceClaw supplies the supervised evidence scorer, with original
NotMentioned negatives included in its second-stage training. Published query
programs add mechanical per-span features, not legal verdicts or forced answer
citations. Their docstrings are not delivered as lawyer instructions. No feature
is score-gated, no answer is repaired, and no external language model is loaded.
"""

from __future__ import annotations

import copy
import json

import numpy as np
from jsonschema import validate

from legal_skill_guard._vendor.scienceclaw_contracts import ContractModel
from legal_skill_guard.task import coherent_native_schema
from legal_skill_guard.utils.hashing import canonical_json_sha256

from .clauses import context_original_clauses, find_original_clauses
from .interface import callable_skill_schema, final_messages, validate_queries

SCORER_PARAMETERS = {
    "C": 10.0,
    "n_folds": 5,
    "context": 0.5,
    "char_weight": 0.0,
    "stage2": "lgbm",
    "use_not_mentioned": True,
    "hyp_id": True,
    "seed": 45,
    "n_jobs": 2,
    "n_estimators": 200,
    "plm": False,
    "emb_C": 10.0,
}


def program_queries(programs, public_ids):
    """Validate published source programs without interpreting their legal truth."""
    if len({s["id"] for s in programs}) != len(programs):
        raise ValueError("Duplicate program IDs; no deduplication")
    result = []
    for skill in programs:
        validate(skill, callable_skill_schema(public_ids))
        validate_queries(skill["queries"])
        if not skill["queries"]:
            raise ValueError("Executable programs need a factual query; no silent text-only skill")
        if len(skill["hypothesis_ids"]) != len(set(skill["hypothesis_ids"])):
            raise ValueError("Duplicate public scope")
        for index, query in enumerate(skill["queries"]):
            result.append((f"{skill['id']}__q{index}", list(skill["hypothesis_ids"]), query))
    return result


def query_features(span_texts, hypothesis_id, queries):
    """Two factual channels per query: direct match versus explicit context.

    A context hit is NOT automatically supporting evidence. The supervised
    scorer must learn its relation to original annotation membership.
    """
    records = [
        {"original_span_index": i, "literal_original_text": text}
        for i, text in enumerate(span_texts)
    ]
    values = np.zeros((len(records), 2 * len(queries)), dtype=np.float32)
    trace = []
    for index, (qid, scope, query) in enumerate(queries):
        if hypothesis_id not in scope:
            continue
        hits = find_original_clauses(
            records, query["all_phrases"], query["any_phrases"], query["none_phrases"]
        )
        context = context_original_clauses(records, hits, query["before"], query["after"])
        neighbours = [r["original_span_index"] for r in context]
        values[hits, 2 * index] = 1.0
        values[neighbours, 2 * index + 1] = 1.0
        trace.append(
            {"query_id": qid, "exact_query": query, "direct_matches": hits, "context": neighbours}
        )
    return values, trace


class ProgramEvidenceModel(ContractModel):
    """Keep author scoring/stacking, insert query features in BOTH scorer heads."""

    def __init__(self, programs, public_ids, **parameters):
        self.programs = copy.deepcopy(programs)
        self.program_sha256 = canonical_json_sha256(self.programs)
        self.queries = program_queries(self.programs, public_ids)
        self._query_cache = {}
        super().__init__(**parameters)

    def _pair_block(self, corpus, features, rows, key, *args, **kwargs):
        original = super()._pair_block(corpus, features, rows, key, *args, **kwargs)
        if not self.queries:
            return original
        texts = [corpus.texts[int(i)] for i in rows]
        cache_key = (canonical_json_sha256(texts), key)
        if cache_key not in self._query_cache:
            self._query_cache[cache_key] = query_features(texts, key, self.queries)[0]
        added = self._query_cache[cache_key]
        free = self.n_free_
        names = [
            f"program_{qid}_{kind}" for qid, _, _ in self.queries for kind in ("match", "context")
        ]
        self.feature_names_ = self.feature_names_[:free] + names + self.feature_names_[free:]
        self.n_free_ = free + added.shape[1]
        # The author's unknown-hypothesis scoring head takes the first n_free_
        # columns. Appending after the private head would silently drop programs.
        return np.concatenate((original[:, :free], added, original[:, free:]), axis=1)


def public_document(row):
    return {"doc_id": str(row["id"]), "text": row["text"], "spans": row["spans"]}


def fit_program_model(rows, labels, programs):
    from threadpoolctl import threadpool_limits

    if len({r["id"] for r in rows}) != len(rows) or len(rows) < 2:
        raise ValueError("At least2 distinct seen TRAIN sources required")
    annotations = [
        {
            "doc_id": str(r["id"]),
            "hypothesis_key": k,
            "label": a["choice"],
            "evidence_spans": a["spans"],
        }
        for r in rows
        for k, a in r["annotation_sets"][0]["annotations"].items()
    ]
    np.random.seed(SCORER_PARAMETERS["seed"])
    with threadpool_limits(limits=2):
        model = ProgramEvidenceModel(programs, list(labels), **SCORER_PARAMETERS).fit(
            [public_document(r) for r in rows], annotations, labels
        )
    if model.m2_ is None or model.m2_free_ is None:
        raise ValueError("Both declared scoring heads must be fitted; no lexical substitute")
    expected = {(str(r["id"]), k) for r in rows for k in labels}
    actual = {(a["doc_id"], a["key"]) for a in model.scoring_pairs_}
    if actual != expected or len(model.scoring_pairs_) != len(expected):
        raise ValueError("Every original TRAIN hypothesis must reach binary membership fitting")
    model._query_cache.clear()
    return model


def evidence_proposals(model, row, labels):
    """Execute actual programs and record scores; never read current annotations."""
    from threadpoolctl import threadpool_limits

    if model is None:
        return None  # Declared zero-data initial state, not a failed-model fallback.
    document = public_document(row)
    items = [
        {"doc_id": str(row["id"]), "hypothesis_key": k, "n_spans": len(row["spans"])}
        for k in labels
    ]
    with threadpool_limits(limits=2):
        vectors = model.predict_scores(items, [document])
    texts = [row["text"][a:b] for a, b in row["spans"]]
    by = {}
    for key, vector in zip(labels, vectors):
        if len(vector) != len(row["spans"]) or not np.isfinite(vector).all():
            raise ValueError("Invalid evidence score vector; no substitute or score repair")
        _, trace = query_features(texts, key, model.queries)
        selected = [
            {"original_span_index": int(i), "membership_score": float(p)}
            for i, p in enumerate(vector)
            if p > 0.5
        ]
        by[key] = {
            "candidates": selected,
            "raw_scores": vector.tolist(),
            "executed_program_queries": trace,
            "score_head": "hypothesis_specific_stack"
            if model.lr_.get(key) is not None
            else "learned_shared_head",
        }
    return {
        "source_text_and_spans_sha256": canonical_json_sha256(
            {"text": row["text"], "spans": row["spans"]}
        ),
        "program_library_sha256": model.program_sha256,
        "selection": "ordinary learned binary membership decision p>0.5, not tuned",
        "by_hypothesis": by,
    }


def program_solver_messages(row, labels, system, proposals):
    """One original final answer; operator docstrings are not lawyer policy text."""
    messages, schema = final_messages(row, labels, [], system)
    body = json.loads(messages[1]["content"])
    body["output_contract"]["original_choice_evidence_consistency"] = {
        "NotMentioned": "spans must be []",
        "Entailment_or_Contradiction": "spans must contain original source indices",
    }
    if proposals is not None:
        body["learned_source_evidence_tool"] = {
            "meaning": "Fallible source-span membership predictions learned only from past TRAIN annotations; not legal labels or calibrated legal confidence.",
            "selection": proposals["selection"],
            "candidate_members_by_hypothesis": {
                k: v["candidates"] for k, v in proposals["by_hypothesis"].items()
            },
            "may_reject_candidates_or_cite_other_original_source_spans": True,
            "empty_candidates_do_not_mean_NotMentioned": True,
            "candidate_union_is_not_the_final_answer": True,
        }
    messages[1]["content"] = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    return messages, coherent_native_schema(schema)
