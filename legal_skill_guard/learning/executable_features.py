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

FEATURE_PROTOCOL = "pure_source_code_features_contract_oof_v1"
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
        self.feature_protocol = FEATURE_PROTOCOL
        self._source_feature_cache = {}
        self.source_execution_receipts = []
        super().__init__(**parameters)

    def _hypothesis_design(self, original, corpus, key):
        if not self.library:
            return original
        from scipy.sparse import csr_matrix, hstack

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
        return hstack((original, csr_matrix(added)), format="csr")


def fit_feature_model(rows, labels, library):
    from threadpoolctl import threadpool_limits

    if len(rows) < 2 or len({r["id"] for r in rows}) != len(rows):
        raise ValueError("Distinct already-seen TRAIN sources required")
    annotations = [{"doc_id": str(r["id"]), "hypothesis_key": h,
                    "label": a["choice"], "evidence_spans": a["spans"]}
                   for r in rows for h, a in r["annotation_sets"][0]["annotations"].items()]
    np.random.seed(SCORER_PARAMETERS["seed"])
    with threadpool_limits(limits=2):
        model = ExecutableFeatureModel(library, list(labels), **SCORER_PARAMETERS).fit(
            [public_document(r) for r in rows], annotations, labels)
    if model.m2_ is None or model.m2_free_ is None:
        raise ValueError("Required trained membership heads missing; no substitute")
    assert {(a["doc_id"], a["key"]) for a in model.scoring_pairs_} == {
        (str(r["id"]), h) for r in rows for h in labels}
    # Training executions remain auditable, but their matrices are not an
    # example cache or current-case label store shipped as skills.
    model._source_feature_cache.clear()
    return model
