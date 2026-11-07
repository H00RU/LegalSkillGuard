"""Collision-led interface learning and parameterized external library state."""
from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from typing import Callable

from .checkpoint import immutable_json
from .coverage import digest
from .interfaces import FIELDS, Connector, ConnectorPool, Observation, choose_view, refine


def parameterize_graph(graph: dict) -> dict:
    """Canonicalize slot/column roles; retain DSL operators, no source identities."""
    Connector(graph).validate()
    slots, columns = {}, {}
    def role(table, name, prefix):
        if name not in table:
            table[name] = f"{prefix}{len(table)}"
        return table[name]
    def visit(node):
        if "slot" in node:
            return {"slot": role(slots, node["slot"], "slot")}
        result = {"op": node["op"], "inputs": [visit(c) for c in node["inputs"]]}
        params = {}
        for key, value in sorted(node.get("params", {}).items()):
            if key.endswith("_slot"):
                params[key] = role(slots, value, "slot")
            elif key in {"keys", "from", "to"}:
                params[key] = list(value) if node['op'] == 'group_by' and set(value) <= {'owner', 'period', 'unit'} else \
                    [role(columns, x, "column") for x in value]
            elif key in {"primitive", "scope"} and value in {
                    "cap", "sum_amounts", "exists", "all", "any", "element", "closed_group"}:
                params[key] = value
            else:
                raise ValueError("Graph metadata must be a supported semantic role, not a routing string")
        if params:
            result["params"] = params
        return result
    return visit(graph)


def learn_interfaces(*, base_view: dict, base_answer, candidates: list[Connector],
                     fact_views: list[dict], coarse: Callable, metadata: Callable,
                     oracle=None, project: Callable = lambda x: x) -> dict:
    """One source, one bounded H, at most four combined oracle views.

    Every returned view, including rejected/unused views, is common material for
    all six arms. Unknown interfaces and candidate disagreement remain explicit.
    """
    pool = ConnectorPool(list(candidates))
    observations = [Observation(coarse(base_view), metadata(base_view), base_answer, digest(base_view))]
    pool.observe(base_view, base_answer, project=project)
    remaining = [v for v in fact_views if digest(v) != digest(base_view)]
    queried = []
    for _ in range(4):
        if oracle is None or not pool.candidates:
            break
        view = choose_view(pool, remaining, project=project)
        if view is None:
            # Interface collision search can still be informative after H has
            # fit the base label. Prefer an equal coarse observation with new
            # role structure; do not consult labels to select it.
            eligible = [v for v in remaining if digest(coarse(v)) == digest(coarse(base_view))
                        and digest(metadata(v)) != digest(metadata(base_view))]
            view = min(eligible, key=digest) if eligible else None
        if view is None:
            break
        key = digest(view)
        remaining = [v for v in remaining if digest(v) != key]
        answer = oracle.query(view)
        queried.append({"view": view, "view_hash": key, "answer": answer})
        observations.append(Observation(coarse(view), metadata(view), answer, key))
        pool.observe(view, answer, project=project)
    refinement = refine(observations)
    graphs = [parameterize_graph(c.graph) for c in pool.candidates]
    reusable = refinement.status == "identified_on_observed_collisions" and bool(graphs)
    return {"status": "NO_VALID_CONNECTOR" if not pool.candidates else refinement.status,
            "schema_repair_needed": not bool(pool.candidates),
            "refinement": asdict(refinement), "oracle_views": queried,
            "base_observation": asdict(observations[0]),
            "retained_graphs": [c.graph for c in pool.candidates],
            "learned_pattern": {"fields": list(refinement.minimal_field_sets[0]),
                                "graphs": graphs, "basis": "observed_source_collisions",
                                "universal_semantic_equivalence_claim": False} if reusable else None,
            "finite_candidate_pool_is_Omega": False}


class SkillLibrary:
    """Immutable snapshots of parameterized patterns, separate from source logs."""
    def __init__(self, patterns: list[dict] | None = None, *, frozen: bool = False, stage: str = "preflight"):
        self.patterns = deepcopy(patterns or [])
        self.frozen = frozen
        if stage not in {"preflight", "formal_train", "formal_B1", "formal_B8"}:
            raise ValueError("Unknown library stage")
        self.stage = stage

    def add(self, pattern: dict, *, source: str) -> str:
        if self.frozen:
            raise ValueError("Frozen library cannot learn from prediction feedback")
        if set(pattern) != {"fields", "graphs", "basis", "universal_semantic_equivalence_claim"}:
            raise ValueError("Library pattern contains source values or unsupported fields")
        if not set(pattern["fields"]) <= set(FIELDS) or pattern["universal_semantic_equivalence_claim"]:
            raise ValueError("Unsupported interface family or unproved equivalence claim")
        # Re-parameterize even if the caller already did so; alpha normalization
        # must be idempotent and applied before cross-source pattern merging.
        cleaned = {**deepcopy(pattern), "graphs": [parameterize_graph(g) for g in pattern["graphs"]]}
        key = digest(cleaned)
        for item in self.patterns:
            if item["pattern_hash"] == key:
                if source not in item["evidence_sources"]:
                    item["evidence_sources"].append(source)
                return key
        self.patterns.append({"pattern_hash": key, "pattern": cleaned,
                              "evidence_sources": [source]})
        return key

    def export(self) -> dict:
        return {"schema": 1, "stage": self.stage, "frozen": self.frozen,
                "patterns": deepcopy(self.patterns), "source_answers_stored_as_patterns": False}

    def freeze(self, path: Path) -> dict:
        self.frozen = True
        content = self.export()
        payload = {"content": content, "sha256": digest(content)}
        immutable_json(path, payload)
        return payload

    @classmethod
    def restore(cls, path: Path) -> SkillLibrary:
        value = json.loads(Path(path).read_text())
        if value["sha256"] != digest(value["content"]):
            raise ValueError("Frozen library hash differs")
        content = value["content"]
        if content["stage"] not in {"preflight", "formal_B1", "formal_B8"} or not content["frozen"]:
            raise ValueError("Not a frozen preflight snapshot")
        for item in content["patterns"]:
            if item["pattern_hash"] != digest(item["pattern"]):
                raise ValueError("Parameterized pattern hash differs")
        return cls(content["patterns"], frozen=True, stage=content["stage"])
