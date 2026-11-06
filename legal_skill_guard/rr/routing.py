"""Actual six-arm inference routing, with one common 3-call prediction budget."""
from __future__ import annotations

import json
from copy import deepcopy

from .controls import ARMS, PredictionBudget
from .coverage import Clause, SourceLedger, digest
from .engine import analyze, source_text, proposal_schema
from .engine import wire_messages as messages
from .example_synthesis import filter_shared_examples, ordinary_horn_prediction
from .interfaces import FIELDS


def _walk(node):
    yield node
    if isinstance(node, dict):
        for child in node.get("inputs", []):
            yield from _walk(child)


def apply_interfaces(proposal: dict, arm: str, library: dict) -> dict:
    result = deepcopy(proposal)
    policy = ARMS[arm].interface
    if policy == "ordinary_IO_local_binding_repair" or result.get("program", {}).get("kind") != "connector":
        return result
    active = set(FIELDS) if policy == "all_extracted_metadata_example_synthesis" else {
        f for item in library.get("patterns", []) for f in item["pattern"]["fields"]}
    extracted = {f for item in result.get("interfaces", []) for f in item.get("fields", [])}
    required = active & extracted
    body = result["program"]["body"]
    candidates = []
    for graph in body.get("candidates", []):
        valid = True
        nodes = list(_walk(graph))
        if "entity_equality" in required:
            # The current extractor has requested same-witness metadata. A graph
            # that explicitly renames that witness apart and then cross-joins
            # cannot satisfy it. Ordinary I/O arms retain their local repair.
            renamed = any(n.get("op") == "bind_rename" and n.get("params", {}).get("from") != n.get("params", {}).get("to") for n in nodes if isinstance(n, dict))
            cross = any(n.get("op") == "join_on" and not n.get("params", {}).get("keys") for n in nodes if isinstance(n, dict))
            if renamed and cross:
                valid = False
        if "aggregation_stage" in required:
            for node in nodes:
                if node.get("op") == "map" and node.get("params", {}).get("primitive") == "cap":
                    scope = node["params"].get("scope")
                    child = node.get("inputs", [{}])[0]
                    if scope == "closed_group" and child.get("op") == "map":
                        valid = False
        if valid:
            candidates.append(graph)
    body["candidates"] = candidates
    return result


def translation_action(source: dict, previous: dict, compilation: str) -> dict:
    """Consume the source-level coverage planner without treating H as Omega."""
    ledger = SourceLedger.from_text(source_text(source))
    if previous.get("source_ledger_snapshot"):
        saved = [Clause(**{**c, "context": tuple(c.get("context", ()))})
                 for c in previous["source_ledger_snapshot"]]
        restored = SourceLedger(ledger.text, saved)
        restored.validate()
        if {c.id for c in saved} != {c.id for c in ledger.clauses}:
            raise ValueError("Coverage action source registry differs")
        ledger = restored
    units = {c.id for c in ledger.clauses}
    residual = previous.get("residual_units", [])
    assessment = previous.get("public_grammar_assessment", {})
    if compilation == "generic_CEGAR_fixed_batch":
        selected, basis = residual[:1], "generic_fixed_one_unit"
    elif compilation == "full":
        selected, basis = residual, "full_source_translation"
    elif "batch" in assessment:
        selected = assessment["batch"]
        basis = assessment.get("planning_status", "coverage_assessment")
    else:
        # Unverified natural-language scope remains TOP. The exact finite
        # kernel cannot certify a cheaper action without a source-level
        # observation contract, so keep all open clauses in the action.
        selected, basis = residual, "conservative_full_source_no_separation_claim"
    if not set(selected) <= units:
        raise ValueError("Coverage planner selected an absent source unit")
    if not selected and previous.get("certificate_status") != "completion_stable":
        selected, basis = sorted(units), "full_source_IR_repair"
    return {"selected": list(selected), "context_closure": sorted(ledger.closure(set(selected))),
            "selection_basis": basis, "source_ledger_hash": ledger.version,
            "joint_separation_complete": basis == "separation_complete"}


def route_prediction(source: dict, *, arm: str, library: dict, generate, protocol: dict,
                     partition: str, offline_mock: bool = False,
                     example_model: dict | None = None) -> dict:
    if arm not in ARMS:
        raise ValueError("Unknown inference arm")
    if not library.get("frozen"):
        raise ValueError("Inference requires a frozen library")
    if offline_mock:
        if not getattr(generate, "is_offline_mock", False):
            raise ValueError("Offline bypass cannot dispatch a real model client")
    elif not protocol["run_enabled"] or partition == "test" and not protocol["execution_request"]["frozen_test_enabled"]:
        raise ValueError("Formal prediction/evaluation remains disabled")
    before = digest(library)
    example_before = digest(example_model)
    profile, budget = ARMS[arm], PredictionBudget()
    history, actions = [], []
    previous = None
    for step in range(2):
        purpose = "parse" if step == 0 else "repair"
        budget.reserve(purpose)
        prompt = messages(source, previous=previous)
        prompt[0]["content"] += "\nCompilation policy: " + profile.compilation + ". Interface policy: " + profile.interface + "."
        if profile.interface == "collision_refined":
            prompt[0]["content"] += "\nFrozen role patterns: " + json.dumps([x["pattern"] for x in library.get("patterns", [])])
        if step and previous is not None:
            action = translation_action(source, previous, profile.compilation)
            actions.append(action)
            prompt[1]["content"] += "\nSelected translation batch and verified planning basis: " + json.dumps(action)
        wire = generate(prompt, purpose=purpose, step=step, arm=arm,
                        schema=proposal_schema(source["dataset"], source=source, previous=previous))
        result = analyze(source, wire["content"])
        if "proposal" in result:
            constrained = apply_interfaces(result["proposal"], arm, library)
            example_evidence = None
            if arm == "MB" and example_model is not None:
                constrained, example_evidence = filter_shared_examples(constrained, source, example_model)
            if constrained != result["proposal"]:
                result = analyze(source, json.dumps(constrained))
            if example_evidence is not None:
                result["ordinary_example_synthesis"] = example_evidence
        if arm == "MB" and example_model is not None:
            result["ordinary_horn_synthesis"] = ordinary_horn_prediction(source, example_model)
        if profile.compilation == "full" and result.get("residual_units") and result["certificate_status"] == "completion_stable":
            result["certificate_status"] = "translation_unresolved"
            result["full_compilation_required"] = True
        history.append(result)
        previous = result
        if result["certificate_status"] == "completion_stable":
            break
    if previous is None or previous["certificate_status"] != "completion_stable":
        budget.reserve("fallback")
        prompt = messages(source)
        prompt[0]["content"] += "\nFinal fixed fallback. Preserve all uncertainty; give the native task answer without claiming a certificate."
        wire = generate(prompt, purpose="fallback", step=len(history), arm=arm,
                        schema=proposal_schema(source["dataset"], source=source))
        fallback = analyze(source, wire["content"])
        fallback["certificate_status"] = "unsupported_no_certificate" if source["dataset"] == "ContractNLI" else "translation_unresolved"
        fallback["fallback_used"] = True
        previous = fallback
        history.append(fallback)
    if digest(library) != before or digest(example_model) != example_before:
        raise ValueError("Prediction modified the frozen library")
    return {"arm": arm, "result": previous, "history": history,
            "model_calls": len(budget.calls), "call_purposes": budget.calls,
            "translation_actions": actions,
            "tools": list(profile.tools), "frozen_library_unchanged": True}
