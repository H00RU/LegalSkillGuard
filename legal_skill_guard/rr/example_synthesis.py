"""Ordinary connector synthesis for MB from the shared training extraction.

This control retains every extracted typed value and uses example agreement,
without collision selection or learned field minimization. Frozen output stores
role graphs and type signatures; labels and concrete binding values stay in the
training material. The finite candidate pool is never a completion certificate.
"""
from __future__ import annotations

import time
from copy import deepcopy

from .coverage import SourceLedger, digest
from .engine import _native, decode_slots, source_text
from .horn import Atom
from .interfaces import Amount, Connector, InterfaceError, Relation
from .learning import parameterize_graph
from .public_horn import parse_public


def _rule_graph(rule, erase):
    graph = {"slot": "atom0"}
    columns = {x for x in rule.body[0].arguments if x.startswith("?")}
    for i, atom in enumerate(rule.body[1:], 1):
        current = {x for x in atom.arguments if x.startswith("?")}
        shared = sorted(columns & current)
        right = {"slot": f"atom{i}"}
        if erase and shared:
            renamed = [f"rhs{i}_{x}" for x in shared]
            right = {"op": "bind_rename", "inputs": [right], "params": {"from": shared, "to": renamed}}
            current = (current - set(shared)) | set(renamed)
            shared = []
        graph = {"op": "join_on", "inputs": [graph, right], "params": {"keys": shared}}
        columns |= current
    return graph


def _horn_signature(public):
    parsed = parse_public(public)
    if parsed.residuals:
        raise ValueError("An incomplete public grammar cannot supply missing metadata")
    signature = []
    for rule in parsed.rules:
        variables = {}
        def terms(atom):
            result = []
            for term in atom.arguments:
                if term.startswith("?"):
                    variables.setdefault(term, f"variable{len(variables)}")
                    result.append(variables[term])
                else:
                    result.append("constant_role")
            return result
        signature.append({"body": [terms(a) for a in rule.body], "head": terms(rule.head)})
    return digest(signature), parsed


def _horn_masks(parsed):
    n = len(parsed.rules)
    masks = [set(), set(range(n))] + [{i} for i in range(n)] + [set(range(n)) - {i} for i in range(n)]
    result, seen = [], set()
    for mask in masks:
        graph_hash = digest([_rule_graph(r, i in mask) for i, r in enumerate(parsed.rules)])
        if graph_hash not in seen:
            seen.add(graph_hash)
            result.append([i in mask for i in range(n)])
        if len(result) == 32:
            break
    return result


def _matches(pattern, facts):
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


def _horn_predict(public, mask, *, deadline=None):
    _, parsed = _horn_signature(public)
    if len(mask) != len(parsed.rules):
        return None
    facts = set(parsed.facts)
    deadline = min(deadline, time.monotonic() + 5) if deadline is not None else time.monotonic() + 5
    for _ in range(32):
        new = set()
        for i, rule in enumerate(parsed.rules):
            if time.monotonic() >= deadline:
                return None
            graph = _rule_graph(rule, mask[i])
            relation = Connector(graph).execute({f"atom{j}": _matches(a, facts) for j, a in enumerate(rule.body)})
            for row in relation.rows:
                binding = dict(zip(relation.columns, row))
                if any(x.startswith("?") and x not in binding for x in rule.head.arguments):
                    return None
                new.add(Atom(rule.head.predicate, tuple(binding.get(x, x) for x in rule.head.arguments), rule.head.positive))
        if new <= facts:
            if parsed.query in facts and parsed.query.negate() in facts:
                return None
            return "True" if parsed.query in facts else "False" if parsed.query.negate() in facts else "Unknown"
        facts |= new
    return None


def _fit_horn_examples(sources, records, labels):
    groups, used_views = {}, 0
    for record in records:
        source = sources[record["source"]]
        if source["dataset"] != "ProofWriter_OWA_depth5":
            continue
        try:
            signature, parsed = _horn_signature(source["public"])
        except ValueError:
            continue
        group = groups.setdefault(signature, {"masks": {}, "examples": []})
        for mask in _horn_masks(parsed):
            group["masks"][digest(mask)] = mask
        group["examples"].append((source["public"], labels[record["source"]]["answer"]))
        for view in record["learning"]["oracle_views"]:
            if view.get("status") == "reference_failed" or view.get("answer") is None:
                continue
            public = view.get("view", {}).get("public")
            if public is not None and _horn_signature(public)[0] == signature:
                group["examples"].append((public, view["answer"]))
                used_views += 1
    families = []
    for signature, group in sorted(groups.items()):
        accepted, rejected = [], []
        candidates = sorted(group["masks"].values(), key=digest)[:32]
        for mask in candidates:
            valid = all(_horn_predict(public, mask) == answer for public, answer in group["examples"])
            (accepted if valid else rejected).append(mask)
        families.append({"signature": signature, "accepted_masks": accepted, "rejected_masks": rejected,
                         "examples": len(group["examples"]), "candidate_count": len(candidates)})
    return families, used_views


def ordinary_horn_prediction(source: dict, frozen: dict) -> dict | None:
    if source["dataset"] != "ProofWriter_OWA_depth5":
        return None
    if digest(frozen["content"]) != frozen.get("sha256") or not frozen["content"]["frozen"]:
        raise ValueError("Example-synthesis state changed")
    try:
        signature, parsed = _horn_signature(source["public"])
    except ValueError:
        return {"status": "unresolved_public_metadata", "is_Omega": False}
    family = next((f for f in frozen["content"].get("horn_families", []) if f["signature"] == signature), None)
    masks = family["accepted_masks"] if family is not None else _horn_masks(parsed)
    deadline = time.monotonic() + 5
    answers = [_horn_predict(source["public"], mask, deadline=deadline) for mask in masks]
    if not answers:
        return {"status": "NO_VALID_CONNECTOR", "answer": None, "is_Omega": False}
    stable = None not in answers and len(set(answers)) == 1
    return {"status": "candidate_pool_agreement_only" if stable else "ambiguous_connector",
            "answer": answers[0] if stable else None, "is_Omega": False,
            "candidate_count": len(masks), "training_examples_matched": family is not None}


def _case(body: dict, graph: dict, source: dict) -> tuple[str, dict, dict]:
    ledger = SourceLedger.from_text(source_text(source))
    units = {c.id: ledger.text[c.start:c.end] for c in ledger.clauses}
    slots, _ = decode_slots(body, set(units), units)
    names = {name: f"slot{i}" for i, name in enumerate(slots)}
    columns = {}

    def column(name):
        if name not in columns:
            columns[name] = f"column{len(columns)}"
        return columns[name]

    # Normalize equalities jointly across all extracted relations, retaining
    # the full witness columns even when a proposed graph erases one of them.
    for value in slots.values():
        if isinstance(value, Relation):
            for name in value.columns:
                column(name)

    def visit(node):
        if "slot" in node:
            return {"slot": names[node["slot"]]}
        params = {}
        for key, value in node.get("params", {}).items():
            if key.endswith("_slot"):
                params[key] = names[value]
            elif key in {"keys", "from", "to"}:
                params[key] = [column(x) for x in value]
            elif key in {"primitive", "scope"}:
                params[key] = value
            else:
                raise ValueError("Unsupported graph parameter")
        return {"op": node["op"], "inputs": [visit(x) for x in node["inputs"]],
                **({"params": params} if params else {})}

    parameterize_graph(graph)  # reject concrete routing strings in graph metadata
    normalized = visit(graph)
    cloned, memo = deepcopy(slots), {}
    def normalize_value(value):
        if id(value) in memo:
            return memo[id(value)]
        if isinstance(value, Relation):
            result = Relation(tuple(column(c) for c in value.columns), value.rows, value.closed)
            memo[id(value)] = result
            return result
        if isinstance(value, list):
            result = []
            memo[id(value)] = result
            result.extend(normalize_value(x) for x in value)
            return result
        return value
    environment = {names[name]: normalize_value(value) for name, value in cloned.items()}
    # Semantic types and witness-column equality structure determine
    # compatibility. Amounts, names, source IDs and labels are absent.
    kinds = []
    for binding in body.get("bindings", []):
        value = slots[binding["name"]]
        kind = {"type": binding["type"]}
        if isinstance(value, Relation):
            kind.update(columns=list(environment[names[binding["name"]]].columns), closed=value.closed)
        kinds.append(kind)
    projection = body.get("project", "identity")
    signature = digest({"slot_types": kinds, "projection": projection})
    return signature, normalized, environment


def _predict(graph: dict, environment: dict, projection: str):
    value = Connector(graph).execute(deepcopy(environment))
    if projection == "amount_value" and isinstance(value, Amount):
        return value.value
    if projection != "identity":
        raise InterfaceError("Unsupported output projection")
    return _native(value)


def fit_shared_examples(sources: dict, records: list[dict], labels: dict) -> dict:
    groups = {}
    skipped, raw_views = 0, 0
    for record in records:
        source = sources[record["source"]]
        target = labels[record["source"]]
        answer = target.get("targets", target.get("answer"))
        raw_views += len(record["learning"]["oracle_views"])
        for call in record["calls"]:
            proposal = call["analysis"].get("proposal", {})
            program = proposal.get("program", {})
            if program.get("kind") != "connector":
                skipped += 1
                continue
            body = program.get("body", {})
            if len(body.get("candidates", [])) > 32:
                skipped += 1
                continue
            for graph in body.get("candidates", [])[:32]:
                try:
                    signature, normalized, environment = _case(body, graph, source)
                except (ValueError, TypeError, KeyError, InterfaceError):
                    skipped += 1
                    continue
                group = groups.setdefault(signature, {"graphs": {}, "examples": {},
                                                       "projection": body.get("project", "identity")})
                group["graphs"][digest(normalized)] = normalized
                key = digest({"environment": environment, "answer": answer})
                group["examples"][key] = (environment, answer)
    families = []
    for signature, group in sorted(groups.items()):
        accepted, rejected = [], []
        candidates = sorted(group["graphs"].items())[:32]
        for key, graph in candidates:
            valid = True
            for environment, answer in group["examples"].values():
                try:
                    valid &= digest(_predict(graph, environment, group["projection"])) == digest(answer)
                except (ValueError, TypeError, KeyError, InterfaceError):
                    valid = False
                if not valid:
                    break
            (accepted if valid else rejected).append(graph if valid else key)
        families.append({"signature": signature, "accepted_graphs": accepted,
                         "rejected_graph_hashes": rejected,
                         "examples": len(group["examples"]), "candidate_count": len(candidates),
                         "candidate_bound_reached": len(group["graphs"]) > 32})
    horn_families, used_views = _fit_horn_examples(sources, records, labels)
    content = {"schema": 1, "frozen": True, "policy": "ordinary_shared_example_synthesis",
               "metadata_policy": "all_same_budget_extracted_typed_values",
               "families": families, "horn_families": horn_families, "source_count": len(records),
               "raw_budgeted_views_available": raw_views,
               "budgeted_views_used_in_public_grammar_synthesis": used_views,
               "unbound_view_policy": "retain_shared_material_without_inventing_extractions",
               "skipped_unexecutable_proposals": skipped, "extra_model_calls": 0,
               "source_answers_stored_as_patterns": False, "finite_candidate_pool_is_Omega": False}
    return {"content": content, "sha256": digest(content)}


def filter_shared_examples(proposal: dict, source: dict, frozen: dict) -> tuple[dict, dict]:
    if not frozen.get("content", {}).get("frozen") or digest(frozen["content"]) != frozen.get("sha256"):
        raise ValueError("Ordinary-example synthesis artifact is not intact and frozen")
    result = deepcopy(proposal)
    program = result.get("program", {})
    evidence = {"ordinary_example_synthesis_applied": True, "removed": 0,
                "untested_candidates_retained": 0, "finite_candidate_pool_is_Omega": False}
    if program.get("kind") != "connector":
        return result, evidence
    families = {x["signature"]: x for x in frozen["content"]["families"]}
    body = program["body"]
    if len(body.get("candidates", [])) > 32:
        evidence["candidate_bound_exceeded"] = True
        return result, evidence
    kept = []
    for graph in body.get("candidates", [])[:32]:
        try:
            signature, normalized, _ = _case(body, graph, source)
            family = families.get(signature, {})
            key = digest(normalized)
            if key in family.get("rejected_graph_hashes", []):
                evidence["removed"] += 1
                continue
            if key not in {digest(g) for g in family.get("accepted_graphs", [])}:
                evidence["untested_candidates_retained"] += 1
            kept.append(graph)
        except (ValueError, TypeError, KeyError, InterfaceError):
            kept.append(graph)  # the shared engine reports malformed IR
    body["candidates"] = kept
    return result, evidence
