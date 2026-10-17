"""Teacher-authored pure source features, not advice or final evidence answers.

Reuses the attributed ScienceClaw scorer and its contract-OOF design hook.
Published functions run in restricted, resource-limited CPU subprocesses. This
is a trusted-teacher research executor, not a general hostile-code sandbox.
No current annotations, document IDs, network/filesystem capability, extra LLM,
quality admission, fallback, host legal verdict or native answer repair.
"""

from __future__ import annotations

import ast
import copy
import json
import subprocess
import sys

import numpy as np
from jsonschema import validate

from legal_skill_guard._vendor.scienceclaw_contracts import ContractModel
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha

from .evidence_programs import SCORER_PARAMETERS, public_document
from .publication import apply_differential_publication, skill_record_schema

FEATURE_PROTOCOL = "source_scoped_anchored_log_odds_v1"
GUIDANCE_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["feature_names", "python_source"],
    "properties": {
        "feature_names": {"type": "array", "minItems": 1,
                          "items": {"type": "string", "minLength": 1}},
        "python_source": {"type": "string", "minLength": 1},
    },
}
BUILTINS = (
    "abs", "all", "any", "bool", "dict", "enumerate", "float", "int",
    "isinstance", "len", "list", "max", "min", "range", "reversed",
    "round", "set", "sorted", "str", "sum", "tuple", "zip", "ValueError",
)
ATTRIBUTES = frozenset((
    "lower", "upper", "casefold", "strip", "lstrip", "rstrip", "split",
    "splitlines", "join", "replace", "startswith", "endswith", "find",
    "rfind", "index", "count", "isalpha", "isdigit", "isalnum", "isspace",
    "isupper", "islower", "append", "extend", "insert", "add", "discard",
    "update", "get", "items", "keys", "values", "setdefault", "pop",
    "copy", "sort", "union", "intersection", "difference", "search",
    "match", "fullmatch", "findall", "finditer", "compile", "sub", "escape",
    "group", "groups", "groupdict", "start", "end", "span",
    "I", "M", "S", "A", "X", "IGNORECASE", "MULTILINE", "DOTALL",
    "ASCII", "VERBOSE",
))
CHILD = """import builtins,json,re,resource,sys
resource.setrlimit(resource.RLIMIT_CPU,(2,2))
resource.setrlimit(resource.RLIMIT_AS,(192*1024*1024,192*1024*1024))
resource.setrlimit(resource.RLIMIT_FSIZE,(0,0))
p=json.load(sys.stdin)
g={'__builtins__':{k:getattr(builtins,k) for k in p['allowed_builtins']},'re':re}
exec(compile(p['python_source'],'<published-source-feature>','exec'),g)
y=g['span_features'](p['text'],p['spans'])
sys.stdout.write(json.dumps(y,allow_nan=False,separators=(',',':')))
"""


def validate_source(source):
    tree = ast.parse(source, mode="exec")
    definitions = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    if len({n.name for n in definitions}) != len(definitions):
        raise ValueError("Published helper function names must be distinct")
    functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    if "span_features" not in functions:
        raise ValueError("A published span_features(text, spans) function is required")
    main = functions["span_features"].args
    if ([a.arg for a in main.args] != ["text", "spans"] or main.posonlyargs
            or main.vararg or main.kwarg or main.kwonlyargs or main.defaults):
        raise ValueError("Exact span_features(text, spans) signature required")
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) and not (
                isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)):
            raise ValueError("Only function definitions and a module docstring are permitted")
    calls = set(BUILTINS) | {n.name for n in definitions}
    forbidden = (ast.Import, ast.ImportFrom, ast.ClassDef, ast.AsyncFunctionDef,
                 ast.Global, ast.Nonlocal, ast.With, ast.AsyncWith, ast.Await,
                 ast.Yield, ast.YieldFrom)
    for node in ast.walk(tree):
        if isinstance(node, forbidden):
            raise ValueError("Imports, external capabilities and dynamic program objects are forbidden")
        if isinstance(node, ast.Name) and "__" in node.id:
            raise ValueError("Reflective names are forbidden")
        if isinstance(node, ast.FunctionDef) and (node.decorator_list or "__" in node.name):
            raise ValueError("Decorators and reflective function names are forbidden")
        if isinstance(node, ast.Attribute) and node.attr not in ATTRIBUTES:
            raise ValueError("Only documented pure text/container/regex attributes are permitted")
        if isinstance(node, ast.Call) and not (
                isinstance(node.func, ast.Name) and node.func.id in calls
                or isinstance(node.func, ast.Attribute) and node.func.attr in ATTRIBUTES):
            raise ValueError("Only documented pure calls and defined helpers are permitted")
    return tree


def validate_library(library, public_ids):
    if len({s["id"] for s in library}) != len(library):
        raise ValueError("Duplicate source-feature skill ID")
    for skill in library:
        validate(skill, skill_record_schema(public_ids, guidance_schema=GUIDANCE_SCHEMA))
        names = skill["guidance"]["feature_names"]
        if len(set(names)) != len(names) or len(set(skill["hypothesis_ids"])) != len(skill["hypothesis_ids"]):
            raise ValueError("Duplicate feature name or public scope")
        validate_source(skill["guidance"]["python_source"])


def publish(parent, value, public_ids, seen_ids):
    library = apply_differential_publication(
        parent, value, public_ids, seen_ids, guidance_schema=GUIDANCE_SCHEMA)
    validate_library(library, public_ids)
    return library


def execute_source_features(skill, document):
    """Exactly one pure invocation. Errors propagate; no replacement feature."""
    guidance = skill["guidance"]
    validate_source(guidance["python_source"])
    text, spans = document["text"], document["spans"]
    payload = {"python_source": guidance["python_source"], "text": text,
               "spans": spans, "allowed_builtins": BUILTINS}
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-c", CHILD],
        input=json.dumps(payload, ensure_ascii=False), text=True,
        capture_output=True, timeout=5, check=True,
        env={"LC_ALL": "C.UTF-8", "PYTHONHASHSEED": "0"})
    values = json.loads(result.stdout)
    n, width = len(spans), len(guidance["feature_names"])
    if not isinstance(values, list) or len(values) != n or any(
            not isinstance(row, list) or len(row) != width
            or any(type(x) not in (bool, int, float) for x in row) for row in values):
        raise ValueError("Published feature output has wrong original-span shape/types")
    matrix = np.asarray(values, dtype=float).reshape(n, width)
    if not np.isfinite(matrix).all() or np.any(matrix < 0) or np.any(matrix > 1):
        raise ValueError("Published source features must be finite in [0,1]; never clip")
    return matrix, {"skill_id": skill["id"], "program_sha256": csha(guidance),
                    "public_source_sha256": csha({"text": text, "spans": spans}),
                    "feature_shape": [n, width], "feature_values_sha256": csha(values),
                    "one_resource_limited_CPU_subprocess_no_Gold_ID_or_model": True}


class ExecutableFeatureModel(ContractModel):
    """One existing word/feature LR and corresponding OOF calibration stack."""

    def __init__(self, library, public_ids, **parameters):
        validate_library(library, public_ids)
        self.library = copy.deepcopy(library)
        self.program_sha256 = csha(library)
        self.feature_protocol = "pure_source_code_features_contract_oof_v1"
        self._source_feature_cache = {}
        self.source_execution_receipts = []
        super().__init__(**parameters)

    def _hypothesis_design(self, original, corpus, key):
        if not self.library:
            return original
        from scipy.sparse import csr_matrix, hstack

        return hstack((original, csr_matrix(self.source_features(corpus, key))), format="csr")

    def source_features(self, corpus, key):
        """All declared source features; scope masks are public, not semantic routing."""
        width = sum(len(s["guidance"]["feature_names"]) for s in self.library)
        added = np.zeros((corpus.n, width), dtype=float)
        for did in corpus.doc_ids:
            document = corpus.documents[did]
            cache_key = csha({"text": document["text"], "spans": document["spans"]})
            if cache_key not in self._source_feature_cache:
                outputs = []
                for skill in self.library:
                    matrix, receipt = execute_source_features(skill, document)
                    outputs.append(matrix)
                    self.source_execution_receipts.append(receipt)
                self._source_feature_cache[cache_key] = outputs
            offset = 0
            for skill, values in zip(self.library, self._source_feature_cache[cache_key], strict=True):
                end = offset + values.shape[1]
                if key in skill["hypothesis_ids"]:
                    added[corpus.rows(did), offset:end] = values
                offset = end
        return added


def anchored_probability(base, features, coefficients):
    """A fused log-odds correction, with an exact numerical zero identity.

    The identity is algebraic, not an error/score/uncertainty-dependent fallback.
    Every published feature is evaluated. It does not guarantee non-harm where
    a nonzero learned correction applies.
    """
    from scipy.special import expit, logit

    base = np.asarray(base, dtype=float)
    if not np.isfinite(base).all() or np.any(base <= 0) or np.any(base >= 1):
        raise ValueError("Strict finite base probabilities required; never clip")
    correction = np.asarray(features @ coefficients).reshape(-1)
    if correction.shape != base.shape or not np.isfinite(correction).all():
        raise ValueError("Invalid source correction")
    corrected = expit(logit(base) + correction)
    return np.where(correction == 0, base, corrected)


class AnchoredFeatureModel(ExecutableFeatureModel):
    """Unchanged ordinary scorer plus one fused, source-scoped log-odds term.

    The proper Bernoulli objective uses actual source-held-out BASE predictions,
    not the base's approximately perfect in-sample probabilities. Teacher
    features were induced on all seen TRAIN; this cross-fitting is for fitting
    the correction, not an independent validation of feature induction.
    """

    def __init__(self, library, public_ids, **parameters):
        super().__init__(library, public_ids, **parameters)
        self.parameters = copy.deepcopy(parameters)
        self.feature_protocol = FEATURE_PROTOCOL

    def _hypothesis_design(self, original, corpus, key):
        return original

    def base_scores(self, items, documents):
        return ContractModel.predict_scores(self, items, documents)

    def fit(self, train_documents, train_annotations, hypotheses):
        from scipy.optimize import minimize
        from scipy.special import expit, logit

        documents, annotations = list(train_documents), list(train_annotations)
        ContractModel.fit(self, documents, annotations, hypotheses)
        self.base_fit_count = 1
        self.outer_source_partitions = []
        self.residual_coefficients = {}
        self.residual_fit_diagnostics = {}
        width = sum(len(s["guidance"]["feature_names"]) for s in self.library)
        if not self.library:
            self.residual_coefficients = {h: np.zeros(0) for h in hypotheses}
            return self
        held_scores = {}
        for fold in sorted(set(self.fold_of_.values())):
            training = [d for d in documents if self.fold_of_[str(d["doc_id"])] != fold]
            held = [d for d in documents if self.fold_of_[str(d["doc_id"])] == fold]
            train_ids, held_ids = ({str(d["doc_id"]) for d in rows} for rows in (training, held))
            assert training and held and not train_ids & held_ids
            self.outer_source_partitions.append({"fold": fold,
                "training_doc_ids": sorted(train_ids), "scored_doc_ids": sorted(held_ids)})
            subset = [a for a in annotations if str(a["doc_id"]) in train_ids]
            np.random.seed(self.parameters["seed"])
            ordinary = ContractModel(**self.parameters).fit(training, subset, hypotheses)
            self.base_fit_count += 1
            items = [{"doc_id": str(d["doc_id"]), "hypothesis_key": h,
                      "n_spans": len(d["spans"])} for d in held for h in hypotheses]
            for item, vector in zip(items, ordinary.predict_scores(items, held), strict=True):
                held_scores[(item["doc_id"], item["hypothesis_key"])] = np.asarray(vector)
        for h in hypotheses:
            features = self.source_features(self.corpus_, h)
            indices, targets, offsets = [], [], []
            for annotation in self.by_h_[h]:
                rows = self.corpus_.rows(annotation["doc_id"])
                target = np.zeros(len(rows))
                target[annotation["evidence"]] = 1
                probabilities = held_scores[(annotation["doc_id"], h)]
                if (not np.isfinite(probabilities).all() or np.any(probabilities <= 0)
                        or np.any(probabilities >= 1)):
                    raise ValueError("Invalid held-source probabilities; no clipping or substitute")
                indices.extend(rows.tolist()); targets.extend(target.tolist())
                offsets.extend(logit(probabilities).tolist())
            x, y, offset = features[np.asarray(indices)], np.asarray(targets), np.asarray(offsets)

            def objective(beta):
                z = offset + x @ beta
                loss = np.sum(np.logaddexp(0, z) - y*z) + np.dot(beta, beta)/(2*self.C)
                gradient = x.T @ (expit(z)-y) + beta/self.C
                return float(loss), gradient

            result = minimize(objective, np.zeros(width), jac=True, method="L-BFGS-B",
                options={"maxiter": 300, "ftol": 1e-12, "gtol": 1e-8})
            if not result.success or not np.isfinite(result.x).all():
                raise ValueError("Source-correction optimization failed; no alternative fit")
            self.residual_coefficients[h] = result.x
            self.residual_fit_diagnostics[h] = {"training_span_rows": len(y),
                "nonzero_feature_rows": int(np.any(x != 0, axis=1).sum()),
                "objective": float(result.fun), "iterations": int(result.nit)}
        self.actual_held_source_base_probabilities = {
            d+"::"+h: v.tolist() for (d, h), v in held_scores.items()}
        return self

    def predict_scores(self, items, documents):
        from legal_skill_guard._vendor.scienceclaw_contracts import _Corpus

        if not hasattr(self, "residual_coefficients"):
            raise ValueError("Fit the source correction before prediction")
        items, documents = list(items), list(documents)
        base = self.base_scores(items, documents)
        corpus = _Corpus(documents)
        features = {h: self.source_features(corpus, h)
                    for h in {str(item["hypothesis_key"]) for item in items}}
        return [anchored_probability(p, features[str(it["hypothesis_key"])][corpus.rows(str(it["doc_id"]))],
                    self.residual_coefficients[str(it["hypothesis_key"])])
                for it, p in zip(items, base, strict=True)]


def fit_feature_model(rows, labels, library):
    from threadpoolctl import threadpool_limits

    if len(rows) < 2 or len({r["id"] for r in rows}) != len(rows):
        raise ValueError("Distinct already-seen TRAIN sources required")
    annotations = [{"doc_id": str(r["id"]), "hypothesis_key": h,
                    "label": a["choice"], "evidence_spans": a["spans"]}
                   for r in rows for h, a in r["annotation_sets"][0]["annotations"].items()]
    np.random.seed(SCORER_PARAMETERS["seed"])
    with threadpool_limits(limits=2):
        model = AnchoredFeatureModel(library, list(labels), **SCORER_PARAMETERS).fit(
            [public_document(r) for r in rows], annotations, labels)
    if model.m2_ is None or model.m2_free_ is None:
        raise ValueError("Required trained membership heads missing; no substitute")
    assert {(a["doc_id"], a["key"]) for a in model.scoring_pairs_} == {
        (str(r["id"]), h) for r in rows for h in labels}
    # Training executions remain auditable, but their matrices are not an
    # example cache or current-case label store shipped as skills.
    model._source_feature_cache.clear()
    return model
