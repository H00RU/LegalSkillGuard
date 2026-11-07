"""Actual six-arm inference routing, with one common 3-call prediction budget."""
from __future__ import annotations

import json
import time
from copy import deepcopy

from .controls import ARMS, PredictionBudget
from .coverage import Clause, SourceLedger, digest
from .engine import analyze, source_text, proposal_schema
from .engine import wire_messages as messages
from .example_synthesis import filter_shared_examples, ordinary_horn_prediction
from .interfaces import FIELDS
from .compilation import prepare_request


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
    old_to_new = {}
    for index, graph in enumerate(body.get("candidates", [])):
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
            old_to_new[index] = len(candidates)
            candidates.append(graph)
    body["candidates"] = candidates
    if 'selected' in body:
        body['selected'] = old_to_new.get(body['selected'], -1)
    for nodes in body.get('source_links', {}).values():
        for i, node in enumerate(nodes):
            if node.startswith('connector:'):
                old = int(node.split(':')[1])
                nodes[i] = 'connector:' + str(old_to_new[old]) if old in old_to_new else 'removed_connector:' + str(old)
    return result


def route_prediction(source: dict, *, arm: str, library: dict, generate, protocol: dict,
                     partition: str, offline_mock: bool = False,
                     example_model: dict | None = None, tokenize=None,
                     request_config=None, thinking=True) -> dict:
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
    previous, remaining = None, 5.0
    for step in range(2):
        purpose = "parse" if step == 0 else "repair"
        budget.reserve(purpose)
        suffix = "\nCompilation policy: " + profile.compilation + ". Interface policy: " + profile.interface + "."
        if profile.interface == "collision_refined":
            suffix += "\nAvailable learned patterns: " + json.dumps([
                {k:x[k] for k in ('pattern_hash', 'pattern')} for x in library.get('patterns', [])])
        started = time.monotonic()
        prepared = prepare_request(source, previous=previous, compilation=profile.compilation,
            system_suffix=suffix, tokenize=tokenize, request_config=request_config, thinking=thinking,
            planning_seconds=remaining)
        remaining = max(0, remaining - (time.monotonic() - started))
        if prepared['action'] is not None:
            actions.append(prepared['action'])
        wire = generate(prepared['messages'], purpose=purpose, step=step, arm=arm,
                        schema=prepared['schema'])
        started = time.monotonic()
        result = analyze(source, wire['content'], planning_seconds=remaining,
            library=library if profile.interface == 'collision_refined' else None)
        remaining = max(0, remaining - (time.monotonic() - started))
        if "proposal" in result:
            original_proposal = deepcopy(result['proposal'])
            pattern_uses = deepcopy(result.get('pattern_uses', []))
            executable = result.get('executable_proposal', result['proposal'])
            constrained = apply_interfaces(executable, arm, library)
            example_evidence = None
            if arm == "MB" and example_model is not None:
                constrained, example_evidence = filter_shared_examples(constrained, source, example_model)
            if constrained != executable:
                started = time.monotonic()
                result = analyze(source, json.dumps(constrained), planning_seconds=remaining)
                remaining = max(0, remaining - (time.monotonic() - started))
                result['proposal'] = original_proposal
                selected = constrained.get('program', {}).get('body', {}).get('selected', -1)
                graphs = constrained.get('program', {}).get('body', {}).get('candidates', [])
                executed = {digest(n) for n in _walk(graphs[selected])} if type(selected) is int and 0<=selected<len(graphs) and result.get('execution_states') else set()
                for use in pattern_uses:
                    if 'candidate' in use:
                        use['status'] = 'executed_main_program' if use['expanded_graph_hash'] in executed else 'not_executed_after_interface_policy'
                result['pattern_uses'] = pattern_uses
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
        fallback = analyze(source, wire['content'], planning_seconds=remaining)
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
