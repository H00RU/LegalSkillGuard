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
PROGRAM_FEATURE_PROTOCOL = "joint_word_query_contract_oof_calibration_v2"


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
    """Historical v1 pickle type; new fits use ordinary LogisticRegression.

    Kept solely so immutable old model artifacts remain readable, not as a
    runtime alternative or a second training path.
    """

    coef_: np.ndarray
    intercept_: np.ndarray

    def decision_function(self, values):
        return np.asarray(values @ self.coef_.reshape(-1)).reshape(-1) + self.intercept_[0]


class ProgramEvidenceModel(ContractModel):
    """Fit source-query features consistently through contract-OOF calibration.

    Programs enter the sparse first-stage design in every training fold and at
    inference. They never add columns to the second-stage tree. The ordinary
    control is a separately fitted empty-program model on the exact same data,
    not a query-zero counterfactual of a differently calibrated program model.
    """

    def __init__(self, programs, public_ids, **parameters):
        self.programs = copy.deepcopy(programs)
        self.program_sha256 = canonical_json_sha256(self.programs)
        self.queries = program_queries(self.programs, public_ids)
        self._query_cache = {}
        self.feature_protocol = PROGRAM_FEATURE_PROTOCOL
        self._zero_query_features = False
        super().__init__(**parameters)

    def _hypothesis_design(self, original, corpus, key):
        if not self.queries:
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
        """Mask-only audit under the SAME fitted head, not an ordinary baseline.

        Word coefficients and the tree can co-adapt to query signals in v2.
        This diagnostic must never be called a same-data no-program model,
        selected answer, deployment alternative or efficacy gate.
        """
        if self._zero_query_features:
            raise ValueError("Nested diagnostic execution")
        self._zero_query_features = True
        try:
            return self.predict_scores(items, documents)
        finally:
            self._zero_query_features = False

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


def evidence_proposals(model, row, labels, *, reading_threshold=0.5):
    """Execute actual programs and record scores; never read current annotations."""
    from threadpoolctl import threadpool_limits

    if (type(reading_threshold) not in (int, float) or not np.isfinite(reading_threshold)
            or not 0 <= reading_threshold < 1):
        raise ValueError("Explicit finite source-reading threshold in[0,1) required")
    if model is None:
        return None  # Declared zero-data initial state, not a failed-model fallback.
    if (
        getattr(model, "feature_protocol", None)
        != PROGRAM_FEATURE_PROTOCOL
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
            if p > reading_threshold
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
        "selection": ("ordinary learned binary membership decision p>0.5, not tuned"
            if reading_threshold == 0.5 else
            f"source-reading proposals p>{reading_threshold!r}; ordinary binary decision remains p>0.5; not final evidence"),
        "by_hypothesis": by,
    }


def fit_reading_threshold(scores, targets, *, beta=2.0):
    """Training-only retrieval calibration, never a native answer or bank gate."""
    s, y = np.asarray(scores, dtype=float), np.asarray(targets)
    if (s.ndim != 1 or y.shape != s.shape or not len(s) or not np.isfinite(s).all()
            or np.any((s < 0) | (s > 1)) or not np.isin(y, (0, 1)).all()
            or not np.any(y) or not np.isfinite(beta) or beta <= 0):
        raise ValueError("Valid probability/target arrays with positives and finite beta required")
    order = np.argsort(-s, kind="stable")
    ordered, tp = s[order], np.cumsum(y[order], dtype=np.int64)
    ends = np.flatnonzero(np.r_[ordered[:-1] != ordered[1:], True])
    hits, selected = tp[ends], ends + 1
    fp, fn = selected - hits, int(y.sum()) - hits
    b2 = beta * beta
    values = (1 + b2) * hits / ((1 + b2) * hits + b2 * fn + fp)
    best = int(np.argmax(values))  # Equal objectives prefer fewer read proposals.
    threshold = float(np.nextafter(ordered[ends[best]], -np.inf))
    if not 0 <= threshold < 1:
        raise ValueError("Calibrated reading threshold exceeds the declared probability contract")
    prediction = s > threshold
    assert int(prediction.sum()) == int(selected[best])  # Do not split equal-score blocks.
    return {"threshold": threshold, "comparison": "strictly_greater_than", "beta": beta,
        "training_component_Fbeta": float(values[best]),
        "TP": int(hits[best]), "FP": int(fp[best]), "FN": int(fn[best]),
        "precision": float(hits[best] / selected[best]),
        "recall": float(hits[best] / int(y.sum())),
        "training_parameter_fit_not_native_performance_or_independent_confirmation": True}


def fit_source_group_reading_policy(rows, labels, source_groups, *, seed=2026101903,
                                   n_splits=5, beta=2.0, progress=None):
    """Fit the existing ordinary tool out of source group, then its read policy.

    ALL input cases remain training data; no separate DEV/validation/TEST is
    reserved. Outer folds exclude connected source identities from feature
    fitting and both ordinary model stages. The calibrated threshold is a
    shared supervised-tool parameter, NOT skill gain or a publication gate.
    """
    import gc
    import time

    row_by_id = {r["id"]: r for r in rows}
    flat = [i for group in source_groups for i in group]
    if (len(row_by_id) != len(rows) or len(set(flat)) != len(flat)
            or set(flat) != set(row_by_id) or any(not g for g in source_groups)
            or n_splits < 2 or len(source_groups) < n_splits):
        raise ValueError("Complete distinct source groups and sufficient folds required")
    groups = sorted([sorted(g) for g in source_groups])
    order = np.random.default_rng(seed).permutation(len(groups))
    assigned = {int(g): int(i % n_splits) for i, g in enumerate(order)}
    group_of = {doc: g for g, members in enumerate(groups) for doc in members}
    fold_of = {doc: assigned[group_of[doc]] for doc in row_by_id}
    records, folds, observed = [], [], set()
    all_scores, all_targets, all_nn = [], [], []
    for fold in range(n_splits):
        train = [r for r in rows if fold_of[r["id"]] != fold]
        held = [r for r in rows if fold_of[r["id"]] == fold]
        if progress:
            progress({"stage": "fit_started", "fold": fold, "attempted_CPUfits": fold + 1,
                "completed_CPUfits": fold, "training_source_ids": [r["id"] for r in train],
                "heldout_source_ids": [r["id"] for r in held]})
        started = time.monotonic()
        model = fit_program_model(train, labels, [])
        fitted_seconds = time.monotonic() - started
        assert set(model.corpus_.doc_ids) == {str(r["id"]) for r in train} and not model.programs
        assert not {group_of[r["id"]] for r in train} & {group_of[r["id"]] for r in held}
        for row in held:
            assert row["id"] not in observed
            observed.add(row["id"])
            proposals = evidence_proposals(model, row, labels)
            for h in labels:
                scores = proposals["by_hypothesis"][h]["raw_scores"]
                gold = row["annotation_sets"][0]["annotations"][h]
                target = np.zeros(len(scores), dtype=np.int8)
                target[gold["spans"]] = 1
                all_scores.extend(scores); all_targets.extend(target.tolist())
                all_nn.extend([gold["choice"] != "NotMentioned"] * len(scores))
                records.append({"source_id": row["id"], "fold": fold, "hypothesis": h,
                    "original_annotation": gold, "actual_out_of_source_group_scores": scores})
        receipt = {"fold": fold, "training_source_ids": [r["id"] for r in train],
            "heldout_source_ids": [r["id"] for r in held],
            "actual_CPU_fit_seconds": fitted_seconds,
            "actual_fit_and_scoring_seconds": time.monotonic() - started,
            "both_model_stages_and_features_exclude_heldout_source_components": True}
        folds.append(receipt)
        if progress:
            progress({"stage": "fold_completed", "completed_CPUfits": fold + 1,
                      "fold_receipt": receipt, "actual_fold_score_records": records[-len(held)*len(labels):]})
        del model
        gc.collect()
    assert observed == set(row_by_id) and len(records) == len(rows) * len(labels)
    s, y, nn = np.asarray(all_scores), np.asarray(all_targets), np.asarray(all_nn, dtype=bool)
    policy = fit_reading_threshold(s, y, beta=beta)
    precision_reference = fit_reading_threshold(s, y, beta=1.0)
    diagnostics = {}
    for name, threshold in (("original_binary_0.5", 0.5), ("fitted_F1", precision_reference["threshold"]),
                            ("fitted_reading_Fbeta", policy["threshold"])):
        selected = s > threshold
        diagnostics[name] = {}
        for subset, mask in (("ALL_hypotheses_including_NM_negatives", np.ones(len(s), dtype=bool)),
                             ("Gold_non_neutral_only", nn)):
            tp = int(np.sum(selected & (y == 1) & mask))
            fp = int(np.sum(selected & (y == 0) & mask))
            fn = int(np.sum(~selected & (y == 1) & mask))
            diagnostics[name][subset] = {"TP": tp, "FP": fp, "FN": fn,
                "precision": tp / (tp + fp) if tp + fp else 0,
                "recall": tp / (tp + fn), "component_F1": 2 * tp / (2 * tp + fp + fn)}
    return {"reading_policy": policy, "F1_parameter_reference_not_another_deployed_policy": precision_reference,
        "training_component_diagnostics_not_native_performance": diagnostics,
        "all_source_group_OOF_records": records, "folds": folds, "source_groups": groups,
        "source_fold_assignment": {str(i): f for i, f in fold_of.items()},
        "actual_completed_CPUfits": len(folds), "seed": seed,
        "selected_threshold_metrics_are_training_parameter_fit_not_independent_test": True,
        "no_new_native_teacher_or_GPU_model_service": True}


def program_solver_messages(
    row, labels, system, proposals, *, guidance=None, show_span_value_enum_in_prompt=True
):
    """One native answer; optional semantic guidance is distinct from query features.

    Historical query runs pass no guidance and retain their exact input. A new
    procedural study must explicitly provide the genuine lawyer-facing bank.
    """
    messages, schema = final_messages(
        row,
        labels,
        [] if guidance is None else guidance,
        system,
        show_span_value_enum_in_prompt=show_span_value_enum_in_prompt,
    )
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
