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
from dataclasses import dataclass

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


@dataclass
class SourceQueryLinear:
    """One affine prediction, with the ordinary word coefficient block preserved."""

    coef_: np.ndarray
    intercept_: np.ndarray

    def decision_function(self, values):
        return np.asarray(values @ self.coef_.reshape(-1)).reshape(-1) + self.intercept_[0]


def fit_query_coefficients(values, target, word_offset, C):
    """Convex weighted logistic fit; no intercept or updates to word parameters."""
    from scipy.optimize import minimize
    from scipy.special import expit

    n = len(target)
    positive = float(np.sum(target))
    if not 0 < positive < n:
        raise ValueError("Query coefficients require the already-fitted binary word head")
    weights = np.where(target > 0, n / (2 * positive), n / (2 * (n - positive)))

    def objective(coefficients):
        logits = word_offset + np.asarray(values @ coefficients).reshape(-1)
        loss = np.sum(weights * (np.logaddexp(0, logits) - target * logits))
        loss += np.dot(coefficients, coefficients) / (2 * C)
        gradient = np.asarray(values.T @ (weights * (expit(logits) - target))).reshape(-1)
        return float(loss), gradient + coefficients / C

    result = minimize(
        objective,
        np.zeros(values.shape[1]),
        jac=True,
        method="L-BFGS-B",
        options={"maxiter": 200, "ftol": 1e-12, "gtol": 1e-8},
    )
    if not result.success or not np.isfinite(result.x).all():
        raise ValueError("Query coefficient optimization failed; no substitute")
    return result.x


class ProgramEvidenceModel(ContractModel):
    """Learn sparse query coefficients without changing the ordinary base model.

    This avoids both a tree's hard minimum-support block and the confound where
    merely adding unused columns changes feature-subsampling randomness.
    """

    def __init__(self, programs, public_ids, **parameters):
        self.programs = copy.deepcopy(programs)
        self.program_sha256 = canonical_json_sha256(self.programs)
        self.queries = program_queries(self.programs, public_ids)
        self._query_cache = {}
        self.feature_protocol = "preserved_word_and_calibrator_query_coefficients_v1"
        self._base_fit = True
        self._zero_query_features = False
        super().__init__(**parameters)

    def _hypothesis_design(self, original, corpus, key):
        if not self.queries or self._base_fit:
            return original
        from scipy.sparse import csr_matrix, hstack

        cache_key = (canonical_json_sha256(corpus.texts), key)
        if cache_key not in self._query_cache:
            values = np.zeros((corpus.n, 2 * len(self.queries)), dtype=np.float32)
            for document_id in corpus.doc_ids:
                rows = corpus.rows(document_id)
                texts = [corpus.texts[int(i)] for i in rows]
                values[rows] = query_features(texts, key, self.queries)[0]
            self._query_cache[cache_key] = csr_matrix(values)
        added = self._query_cache[cache_key]
        if self._zero_query_features:
            added = csr_matrix(added.shape, dtype=np.float32)
        return hstack((original, added), format="csr")

    def scores_without_query_terms(self, items, documents):
        """Teacher/audit-only counterfactual, never a selected solver answer."""
        if self._zero_query_features:
            raise ValueError("Nested diagnostic execution")
        self._zero_query_features = True
        try:
            return self.predict_scores(items, documents)
        finally:
            self._zero_query_features = False

    def fit(self, train_documents, train_annotations, hypotheses):
        # The entire ordinary model, including contract-OOF calibration, is fit
        # identically across arms. Programs cannot steal its word coefficients
        # or alter tree-feature subsampling merely by adding sparse columns.
        self._base_fit = True
        super().fit(train_documents, train_annotations, hypotheses)
        self._base_fit = False
        if not self.queries:
            return self
        corpus = self.corpus_
        base_width = self.X1_.shape[1]
        for key, word_model in list(self.lr_.items()):
            if word_model is None:
                continue  # The declared shared learned head remains unchanged.
            design = self._hypothesis_design(self.X1_, corpus, key)
            indices, targets = [], []
            for annotation in self.by_h_[key]:
                rows = corpus.rows(annotation["doc_id"])
                values = np.zeros(len(rows))
                values[annotation["evidence"]] = 1
                indices.extend(map(int, rows))
                targets.extend(values)
            indices, targets = np.asarray(indices), np.asarray(targets)
            values = design[indices, base_width:]
            coefficients = fit_query_coefficients(
                values, targets, word_model.decision_function(self.X1_[indices]), self.C
            )
            self.lr_[key] = SourceQueryLinear(
                np.concatenate((word_model.coef_[0], coefficients)).reshape(1, -1),
                word_model.intercept_.copy(),
            )
        return self


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
    names = [
        f"program_{qid}_{kind}" for qid, _, _ in model.queries for kind in ("match", "context")
    ]
    model.program_feature_coefficients_ = {}
    for key in labels:
        linear = model.lr_.get(key)
        if linear is None:
            model.program_feature_coefficients_[key] = {
                "no_seen_positive_or_negative_linear_class": True,
                "coefficients": {},
            }
            continue
        coefficients = linear.coef_[0][model.X1_.shape[1] :]
        model.program_feature_coefficients_[key] = {
            "no_seen_positive_or_negative_linear_class": False,
            "coefficients": dict(zip(names, map(float, coefficients), strict=True)),
        }
    model._query_cache.clear()
    return model


def evidence_proposals(model, row, labels):
    """Execute actual programs and record scores; never read current annotations."""
    from threadpoolctl import threadpool_limits

    if model is None:
        return None  # Declared zero-data initial state, not a failed-model fallback.
    if (
        getattr(model, "feature_protocol", None)
        != "preserved_word_and_calibrator_query_coefficients_v1"
    ):
        raise ValueError("Historical state needs its frozen source, not compatibility fallback")
    document = public_document(row)
    items = [
        {"doc_id": str(row["id"]), "hypothesis_key": k, "n_spans": len(row["spans"])}
        for k in labels
    ]
    with threadpool_limits(limits=2):
        vectors = model.predict_scores(items, [document])
        controls = model.scores_without_query_terms(items, [document]) if model.queries else vectors
    texts = [row["text"][a:b] for a, b in row["spans"]]
    by = {}
    for key, vector, control in zip(labels, vectors, controls, strict=True):
        if len(vector) != len(row["spans"]) or not np.isfinite(vector).all():
            raise ValueError("Invalid evidence score vector; no substitute or score repair")
        if len(control) != len(vector) or not np.isfinite(control).all():
            raise ValueError("Invalid diagnostic score vector; no substitute")
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
            "same_fixed_model_without_query_terms": {
                "raw_scores": control.tolist(),
                "candidate_members": [int(i) for i, p in enumerate(control) if p > 0.5],
                "teacher_and_audit_only_never_selected_as_the_native_answer": True,
            },
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
