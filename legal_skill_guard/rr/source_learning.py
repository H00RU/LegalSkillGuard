"""Source-preserving training views, durable four-view oracles and B learning.

Reference implementations live exclusively in this training module. Prediction
entry points never import oracles or receive their reference-only data.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import tarfile
import tempfile
import time
from copy import deepcopy
from dataclasses import asdict
from functools import lru_cache
from itertools import combinations
from pathlib import Path

from .checkpoint import immutable_json
from .coverage import digest
from .horn import Atom
from .interfaces import Connector, Observation, Relation, refine
from .learning import parameterize_graph
from .oracles import ROOT, airline, proofwriter, reference_atom
from .public_horn import parse_atom, parse_public


def _people(program: str) -> list[str]:
    return sorted(set(re.findall(r'"((?:Alice|Bob|Charlie|Dorothy|Eve|Frank|George|Harry|John|Mary))"', program)))


@lru_cache(maxsize=1)
def sara_files() -> Path:
    destination = ROOT / "data/cache/rr_v2/SARA_reference"
    with tarfile.open(ROOT / "data/cache/rr_v2/sara_v2.tar.gz") as archive:
        for member in archive.getmembers():
            if member.isfile() and member.name.startswith("sara_v2/statutes/prolog/"):
                relative = Path(member.name).relative_to("sara_v2")
                target = destination / relative
                if ".." in relative.parts:
                    raise ValueError("Unsafe source member")
                target.parent.mkdir(parents=True, exist_ok=True)
                raw = archive.extractfile(member).read()
                if target.exists() and target.read_bytes() != raw:
                    raise ValueError("Pinned SARA reference code changed")
                if not target.exists():
                    target.write_bytes(raw)
    return destination


def sara_case(grade: dict) -> tuple[str, str]:
    with tarfile.open(ROOT / "data/cache/rr_v2/sara_v2.tar.gz") as archive:
        raw = archive.extractfile(f"sara_v2/cases/{grade['original_id']}.pl").read().decode()
    prefix, tests = raw.split("% Test", 1)
    query = re.search(r":-\s*(.*?)\.\s*(?:\n|$)", tests, re.S)[1].strip()
    query = query.removeprefix("\\+").strip()
    if not re.fullmatch(r's[\w]+\([\w\s,".\-]*\)', query):
        raise ValueError("Unsupported reference question syntax")
    return prefix, query


def sara_answer(grade: dict, view: dict) -> str:
    prefix, query = sara_case(grade)
    if view.get("edit") is not None:
        edit = view["edit"]
        lines = prefix.splitlines()
        if set(edit) != {"line", "old", "new"} or edit["old"] not in _people(prefix) or edit["new"] not in _people(prefix):
            raise ValueError("Invalid source-local person reassignment")
        line = lines[edit["line"]]
        if not re.match(r"(?:agent_|patient_)\(", line) or f'"{edit["old"]}"' not in line:
            raise ValueError("Only an existing event participant may be reassigned")
        lines[edit["line"]] = line.replace(f'"{edit["old"]}"', f'"{edit["new"]}"', 1)
        prefix = "\n".join(lines) + "\n"
    runtime = ROOT / ".local-tools/rr-v2-swipl/root/usr"
    environment = dict(os.environ)
    environment["SWI_HOME_DIR"] = str(runtime / "lib/swi-prolog")
    environment["LD_LIBRARY_PATH"] = str(runtime / "lib") + (":" + environment["LD_LIBRARY_PATH"] if environment.get("LD_LIBRARY_PATH") else "")
    with tempfile.TemporaryDirectory(prefix="rr-sara-reference-") as temporary:
        program = Path(temporary) / "source.pl"
        program.write_text(prefix)
        completed = subprocess.run([str(runtime / "bin/swipl"), "-q", "-f", "none", "-s", str(program),
                                    "-g", f"(({query})->write('Entailment');write('Contradiction')),flush_output,halt"],
                                   cwd=sara_files(), env=environment, capture_output=True, text=True,
                                   timeout=20, check=False)
    label = completed.stdout.strip()
    if completed.returncode or "ERROR" in completed.stderr or label not in {"Entailment", "Contradiction"}:
        raise RuntimeError(f"SARA reference failed (exit {completed.returncode}, stdout {completed.stdout[-400:]!r}): " + completed.stderr[-1500:])
    return label


@lru_cache(maxsize=1)
def _oe_reference():
    from legal_skill_guard.openexempt import UPSTREAM, upstream
    Jurisdiction = upstream("source.jurisdiction").Jurisdiction
    Factory = upstream("source.statute_factory").StatuteFactory
    Solver = upstream("source.solver").Solver
    jurisdictions = [Jurisdiction(s) for s in ("FEDERAL", "ARIZONA", "ILLINOIS", "OREGON", "PENNSYLVANIA", "WISCONSIN")]
    statutes = Factory.load_statute_sets(str(UPSTREAM / "data/statutes"), jurisdictions)
    mapping = {s.jurisdiction: s for s in statutes}
    return Solver(mapping), mapping


def oe_answer(grade: dict, view: dict) -> dict:
    from legal_skill_guard.openexempt import upstream
    case_data = deepcopy(grade["construction_only_case"])
    values = view["values"]
    if len(values) != len(case_data["assets"]) or any(type(v) not in (int, float) or v <= 0 for v in values):
        raise ValueError("OE views change positive asset values only, never eligibility or rules")
    for asset, value in zip(case_data["assets"], values):
        asset["dollar_value"] = value
    case = upstream("source.case").Case.create_case(**case_data)
    solver, mapping = _oe_reference()
    jurisdictions = mapping[case.state_jurisdiction].allowable_exemption_jurisdictions()
    return {"EC": solver.solve_exemption_classification(case, jurisdictions),
            "EV": solver.solve_exemption_valuation(case, jurisdictions)}


def _pw_representation(atom: Atom, aliases: dict) -> str:
    def original(term):
        if term not in aliases:
            raise ValueError("Variant introduces an entity outside the original public domain")
        return aliases[term]
    parts = [original(atom.arguments[0]), "is", atom.predicate] if len(atom.arguments) == 1 else \
        [original(atom.arguments[0]), atom.predicate, original(atom.arguments[1])]
    return "(" + " ".join(json.dumps(v) for v in parts + ["+" if atom.positive else "~"]) + ")"


def pw_answer(source: dict, grade: dict, view: dict) -> str:
    if view["public"]["rules"] != source["public"]["rules"] or view["public"]["query"] != source["public"]["query"]:
        raise ValueError("Source-local views cannot change rules or query")
    ref = grade["reference_representation"]
    aliases = {}
    for raw in ref["facts"] + [ref["query"]]:
        atom = reference_atom(raw)
        for term in atom.arguments:
            aliases[term.casefold().removeprefix("the ")] = term
    facts = [parse_atom(t) for t in view["public"]["facts"]]
    if any(a.negate() in facts for a in facts):
        raise ValueError("Variant violates the consistent-source schema")
    result = proofwriter(ref, facts_override=[_pw_representation(a, aliases) for a in facts])
    if result["status"] != "closure_complete":
        raise ValueError("Reference semantics not resolved")
    return result["answer"]


def original_view(source: dict, grade: dict) -> dict:
    dataset = source["dataset"]
    if dataset == "OpenExempt":
        return {"kind": dataset, "values": [a["dollar_value"] for a in grade["construction_only_case"]["assets"]]}
    if dataset == "RuleArena_Airline":
        return {"kind": dataset, "arguments": deepcopy(grade["reference_arguments"])}
    if dataset == "ProofWriter_OWA_depth5":
        return {"kind": dataset, "public": deepcopy(source["public"])}
    if dataset == "SARA_v2_Binary":
        return {"kind": dataset, "edit": None}
    return {"kind": dataset}


def evaluate_reference(source: dict, grade: dict, view: dict):
    if view["kind"] != source["dataset"]:
        raise ValueError("Oracle benchmark binding differs")
    if source["dataset"] == "OpenExempt":
        return oe_answer(grade, view)
    if source["dataset"] == "RuleArena_Airline":
        before, after = grade["reference_arguments"], view["arguments"]
        if any(before[k] != after[k] for k in before if k != "bag_list") or len(before["bag_list"]) != len(after["bag_list"]):
            raise ValueError("Airline variants must preserve route/class/rules and bag count")
        return airline(after)
    if source["dataset"] == "ProofWriter_OWA_depth5":
        return pw_answer(source, grade, view)
    if source["dataset"] == "SARA_v2_Binary":
        return sara_answer(grade, view)
    raise ValueError("ContractNLI has no counterfactual gold oracle")


class OracleUnavailable(RuntimeError):
    """A charged view has no trustworthy reference label; never fabricate one."""


class DurableOracle:
    def __init__(self, ledger, artifacts: Path, source: dict, grade: dict):
        ledger._source(source["key"])
        self.ledger, self.root, self.source, self.grade = ledger, Path(artifacts), source, grade

    def query(self, view: dict):
        key = digest(view)
        directory = self.root / "oracle_views" / digest(self.source["key"]) / key
        path = directory / "result.json"
        reference_hash = digest(self.grade)
        if path.exists():
            record = json.loads(path.read_text())
            if record["view_hash"] != key or record["reference_hash"] != reference_hash:
                raise ValueError("Oracle resume binding differs")
            return record["answer"]
        failure = directory / "failure.json"
        if failure.exists():
            raise OracleUnavailable("Previously failed view remains charged; reference not re-dispatched: " +
                                    json.loads(failure.read_text())["error"])
        self.ledger.reserve_oracle(self.source["key"], key)
        immutable_json(directory / "request.json", {"source": self.source["key"], "view": view,
                                                   "reference_hash": reference_hash})
        start = time.monotonic()
        try:
            answer = evaluate_reference(self.source, self.grade, view)
        except Exception as exc:
            immutable_json(directory / "failure.json", {"error": repr(exc), "view_slot_charged": True})
            raise OracleUnavailable(str(exc)) from exc
        immutable_json(path, {"view_hash": key, "reference_hash": reference_hash, "answer": answer,
                              "elapsed_seconds": time.monotonic() - start})
        return answer


def _atom_text(atom: Atom) -> str:
    if len(atom.arguments) == 1:
        return f"{atom.arguments[0]} is {'' if atom.positive else 'not '}{atom.predicate}."
    verb = atom.predicate if atom.positive else "does not " + atom.predicate.removesuffix("s")
    return f"{atom.arguments[0]} {verb} {atom.arguments[1]}."


def candidate_views(source: dict, grade: dict) -> list[dict]:
    base = original_view(source, grade)
    views = []
    dataset = source["dataset"]
    if dataset == "OpenExempt":
        for i, j in combinations(range(len(base["values"])), 2):
            view = deepcopy(base)
            view["values"][i], view["values"][j] = view["values"][j], view["values"][i]
            if view != base:
                views.append(view)
    elif dataset == "RuleArena_Airline":
        bags = base["arguments"]["bag_list"]
        for i, j in combinations(range(1, len(bags)), 2):
            view = deepcopy(base)
            current = view["arguments"]["bag_list"]
            current[i]["weight"], current[j]["weight"] = current[j]["weight"], current[i]["weight"]
            if view != base:
                views.append(view)
    elif dataset == "SARA_v2_Binary":
        prefix, _ = sara_case(grade)
        people = _people(prefix)
        for i, line in enumerate(prefix.splitlines()):
            if not re.match(r"(?:agent_|patient_)\(", line):
                continue
            for old in people:
                for new in people:
                    if old != new and f'"{old}"' in line:
                        views.append({"kind": dataset, "edit": {"line": i, "old": old, "new": new}})
    elif dataset == "ProofWriter_OWA_depth5":
        parsed = parse_public(source["public"])
        if parsed.residuals:
            return []
        entities = sorted({x for a in parsed.facts for x in a.arguments})
        for i, text in enumerate(source["public"]["facts"]):
            atom = parse_atom(text)
            for pos, original in enumerate(atom.arguments):
                for other in entities:
                    if other == original:
                        continue
                    args = list(atom.arguments)
                    args[pos] = other
                    new = Atom(atom.predicate, tuple(args), atom.positive)
                    if new in parsed.facts or new.negate() in parsed.facts:
                        continue
                    view = deepcopy(base)
                    view["public"]["facts"][i] = _atom_text(new)
                    views.append(view)
    return sorted({digest(v): v for v in views}.values(), key=digest)


def coarse_and_metadata(source: dict, grade: dict, view: dict) -> tuple[dict, dict]:
    dataset = source["dataset"]
    if dataset == "OpenExempt":
        values = view["values"]
        levels = sorted(set(values))
        return {"amount_multiset": sorted(values)}, {"membership": [
            [{"lineage": f"asset{i}"}, levels.index(value)] for i, value in enumerate(values)]}
    if dataset == "RuleArena_Airline":
        bags = view["arguments"]["bag_list"][1:]
        weights = sorted({b["weight"] for b in bags})
        sizes = sorted({tuple(b["size"]) for b in bags})
        return {"weights": sorted(b["weight"] for b in bags), "sizes": sorted(tuple(b["size"]) for b in bags)}, \
            {"membership": [[sizes.index(tuple(b["size"])), weights.index(b["weight"])] for b in bags]}
    if dataset == "ProofWriter_OWA_depth5":
        atoms = [parse_atom(t) for t in view["public"]["facts"]]
        signature = sorted((a.predicate, a.positive, len(a.arguments)) for a in atoms)
        parsed = parse_public(view["public"])
        return {"primitive_existence_signature": signature}, {"entity_equality": {
            "facts": [[{"entity": x} for x in a.arguments] for a in atoms],
            "query_roles": [{"entity": x} for x in parsed.query.arguments],
            "rule_constant_roles": [[{"entity": x} for a in r.body + (r.head,) for x in a.arguments if not x.startswith("?")]
                                    for r in parsed.rules]}}
    if dataset == "SARA_v2_Binary":
        prefix, _ = sara_case(grade)
        lines = prefix.splitlines()
        if view["edit"] is not None:
            edit = view["edit"]
            lines[edit["line"]] = lines[edit["line"]].replace(f'"{edit["old"]}"', f'"{edit["new"]}"', 1)
        names = _people(prefix)
        facts = [line for line in lines if re.match(r"\w+_\(", line)]
        return {"predicate_counts": sorted(re.match(r"(\w+_)\(", f)[1] for f in facts)}, \
            {"entity_equality": [[{"entity": x} for x in re.findall(r'"([^"\n]+)"', f) if x in names] for f in facts]}
    return {}, {}


def _matches(pattern: Atom, facts: set[Atom]) -> Relation:
    columns = tuple(dict.fromkeys(a for a in pattern.arguments if a.startswith("?")))
    rows = []
    for fact in sorted(facts):
        if (pattern.predicate, pattern.positive, len(pattern.arguments)) != (fact.predicate, fact.positive, len(fact.arguments)):
            continue
        binding = {}
        for formal, actual in zip(pattern.arguments, fact.arguments):
            if formal.startswith("?"):
                if formal in binding and binding[formal] != actual:
                    break
                binding[formal] = actual
            elif formal != actual:
                break
        else:
            rows.append(tuple(binding[c] for c in columns))
    return Relation(columns, tuple(rows))


def rule_graph(rule, *, erase_equalities: bool) -> dict:
    graph = {"slot": "atom0"}
    columns = {x for x in rule.body[0].arguments if x.startswith("?")}
    for i, atom in enumerate(rule.body[1:], 1):
        current = {x for x in atom.arguments if x.startswith("?")}
        shared = sorted(columns & current)
        right = {"slot": f"atom{i}"}
        if erase_equalities and shared:
            renamed = [f"rhs{i}_{x}" for x in shared]
            right = {"op": "bind_rename", "inputs": [right], "params": {"from": shared, "to": renamed}}
            current = (current - set(shared)) | set(renamed)
            shared = []
        graph = {"op": "join_on", "inputs": [graph, right], "params": {"keys": shared}}
        columns |= current
    return graph


def horn_sketches(public: dict) -> list[list[dict]]:
    parsed = parse_public(public)
    if parsed.residuals:
        return []
    n = len(parsed.rules)
    masks = [set(), set(range(n))] + [{i} for i in range(n)] + [set(range(n)) - {i} for i in range(n)]
    result, seen = [], set()
    for mask in masks:
        graphs = [rule_graph(r, erase_equalities=i in mask) for i, r in enumerate(parsed.rules)]
        key = digest(graphs)
        if key not in seen:
            seen.add(key)
            result.append(graphs)
        if len(result) == 32:
            break
    return result


def predict_horn_sketch(public: dict, graphs: list[dict]) -> str | None:
    parsed = parse_public(public)
    if parsed.residuals or len(graphs) != len(parsed.rules):
        return None
    facts = set(parsed.facts)
    deadline = time.monotonic() + 5
    for _ in range(32):
        new = set()
        for rule, graph in zip(parsed.rules, graphs):
            if time.monotonic() >= deadline:
                return None
            relation = Connector(graph).execute({f"atom{i}": _matches(a, facts) for i, a in enumerate(rule.body)})
            for row in relation.rows:
                bound = dict(zip(relation.columns, row))
                if any(x.startswith("?") and x not in bound for x in rule.head.arguments):
                    return None  # cannot invent a witness erased by projection
                new.add(Atom(rule.head.predicate, tuple(bound.get(x, x) for x in rule.head.arguments), rule.head.positive))
        if new <= facts:
            if parsed.query in facts and parsed.query.negate() in facts:
                return None
            return "True" if parsed.query in facts else "False" if parsed.query.negate() in facts else "Unknown"
        facts |= new
    return None


def learn_source(source: dict, grade: dict, oracle: DurableOracle, *, trace: dict | None = None) -> dict:
    if source["dataset"] == "ContractNLI":
        return {"status": "no_counterfactual_oracle", "oracle_views": [], "learned_pattern": None,
                "finite_candidate_pool_is_Omega": False}
    base = original_view(source, grade)
    answer = grade["targets"] if source["dataset"] == "OpenExempt" else grade["answer"]
    coarse, metadata = coarse_and_metadata(source, grade, base)
    observations = [Observation(coarse, metadata, answer, digest(base))]
    remaining = candidate_views(source, grade)
    sketches = horn_sketches(source["public"]) if source["dataset"] == "ProofWriter_OWA_depth5" else []
    if trace is not None:
        trace.update(source=source['key'],events=[],initial_candidates=len(sketches),
            base_predictions=[dict(graph_hash=digest(g),prediction=predict_horn_sketch(source['public'],g)) for g in sketches])
    sketches = [g for g in sketches if predict_horn_sketch(source["public"], g) == answer]
    if trace is not None:
        trace['base_retained']=len(sketches)
    queried = []
    for _ in range(4):
        ranked = []
        for view in remaining:
            c, m = coarse_and_metadata(source, grade, view)
            if digest(c) != digest(coarse) or digest(m) == digest(metadata):
                continue
            predictions = [predict_horn_sketch(view["public"], g) for g in sketches] if sketches else []
            disagreements = sum(a != b for a, b in combinations(predictions, 2))
            predicted_change = sum(p is not None and p != answer for p in predictions)
            ranked.append((-disagreements, -predicted_change, digest(view), view))
        if not ranked:
            break
        view = min(ranked, key=lambda x: x[:3])[3]
        key = digest(view)
        remaining = [v for v in remaining if digest(v) != key]
        try:
            target = oracle.query(view)
        except OracleUnavailable as exc:
            queried.append({"view": view, "view_hash": key, "status": "reference_failed",
                            "answer": None, "error": str(exc), "view_slot_charged": True})
            continue
        c, m = coarse_and_metadata(source, grade, view)
        observations.append(Observation(c, m, target, key))
        queried.append({"view": view, "view_hash": key, "answer": target})
        if sketches:
            predictions = [predict_horn_sketch(view['public'],g) for g in sketches]
            if trace is not None:
                trace['events'].append(dict(view_hash=key,reference_answer=target,
                    before=[dict(graph_hash=digest(g),prediction=p) for g,p in zip(sketches,predictions)],
                    removed=sum(p!=target for p in predictions)))
            sketches = [g for g,p in zip(sketches,predictions) if p == target]
    refinement = refine(observations)
    pattern = None
    graphs = []
    if refinement.status == "identified_on_observed_collisions":
        fields = list(refinement.minimal_field_sets[0])
        if sketches and "entity_equality" in fields:
            # Activating equality obligations forbids renaming a required
            # shared witness apart, even if an irrelevant rule fit the labels.
            exact = [rule_graph(r, erase_equalities=False) for r in parse_public(source["public"]).rules]
            if any(digest(g) == digest(exact) for g in sketches):
                graphs = [parameterize_graph(g) for g in exact if g.get("op") == "join_on"]
        graphs = list({digest(g): g for g in graphs}.values())
        pattern = {"fields": fields, "graphs": graphs, "basis": "observed_source_collisions",
                   "universal_semantic_equivalence_claim": False}
    if trace is not None:
        trace['retained_candidates']=len(sketches)
        trace['refinement']=asdict(refinement)
        trace['selected_pattern']=pattern
        exact=[rule_graph(r,erase_equalities=False) for r in parse_public(source['public']).rules] if sketches else []
        observations_to_check=[(source.get('public'),answer)] + [(v['view'].get('public'),v['answer'])
            for v in queried if v.get('status')!='reference_failed']
        trace['selected_connector_semantics']=[dict(reference_answer=target,
            prediction=predict_horn_sketch(public,exact)) for public,target in observations_to_check
            if public is not None and exact]
    failures = sum(v.get("status") == "reference_failed" for v in queried)
    return {"status": "reference_oracle_unresolved" if failures and pattern is None else refinement.status,
            **({"reference_failures": failures} if failures else {}),
            "oracle_views": queried, "refinement": asdict(refinement),
            "learned_pattern": pattern, "connector_candidates_retained": len(sketches),
            "connector_synthesis_status": "equality_constrained_graphs" if graphs else "field_constraint_only_or_unresolved",
            "finite_candidate_pool_is_Omega": False}
