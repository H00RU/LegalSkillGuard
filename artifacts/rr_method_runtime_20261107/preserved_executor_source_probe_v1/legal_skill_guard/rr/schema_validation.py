"""Second authorized schema repair: two-request gate on the existing ledger.

Every response is checked as received. No missing query, branch, source link or
answer is synthesized. Semantic checks use only the locked TRAIN source and its
already available original grading record, never test answers or new oracles.
"""
from __future__ import annotations

import hashlib
import json
import re
from fractions import Fraction
from pathlib import Path

import jsonschema

from .checkpoint import immutable_json
from .client import ExecutorClient
from .coverage import SourceLedger, digest
from .data_store import PreflightData
from .engine import _exact_json_answer, analyze, decode_slots, proposal_schema, source_text
from .ledger import BudgetLedger
from .preflight import atomic_json, science_files, scientific_code_binding, score_source
from .raw_recovery import _unique_object
from .grounding import source_grounding
from .wire_validation import validate_wire

STAGE = "artifacts/rr_v2_preflight/strict_contract_round2"



def validate_response(source: dict, grade: dict, content: str) -> dict:
    try:
        proposal = json.loads(content, object_pairs_hook=_unique_object)
        validate_wire(proposal, proposal_schema(source["dataset"], source=source))
    except (ValueError, RecursionError, jsonschema.ValidationError) as exc:
        return {"pass": False, "systemic_failure": True, "reason": "strict_schema_or_JSON_failure",
                "error": str(exc)[:1500], "typed_schema_pass": False, "model_IR_executed": False}
    try:
        analysis = analyze(source, content)
    except Exception as exc:
        return {"pass": False, "systemic_failure": True, "reason": "typed_execution_exception",
                "error": repr(exc), "typed_schema_pass": True, "model_IR_executed": False}
    executed = analysis["program_status"] in {"executed_expression", "candidate_pool_agreement_only"}
    if not executed:
        return {"pass": False, "systemic_failure": True, "reason": "no_executable_model_IR",
                "typed_schema_pass": True, "model_IR_executed": False, "analysis": analysis}
    grounding = source_grounding(source_text(source), source["dataset"], proposal)
    candidate = analysis.get("candidate_answer")
    if proposal["program"]["kind"] == "expression":
        from .coverage import evaluate
        ledger = SourceLedger.from_text(source_text(source))
        units = {c.id: ledger.text[c.start:c.end] for c in ledger.clauses}
        slots, _ = decode_slots(proposal["program"]["body"], set(units), units)
        exact = _exact_json_answer(evaluate(proposal["program"]["body"]["query"], slots))
        grounding["checks"].append({"check": "native_JSON_preserves_exact_result", "pass": exact})
        grounding["pass"] &= exact
    score = score_source(source, {"answer": candidate}, grade)
    passed = grounding["pass"] and bool(score["task_correct"])
    return {"pass": passed, "systemic_failure": False,
            "reason": "typed_execution_and_TRAIN_semantic_checks_passed" if passed else "TRAIN_semantics_or_source_grounding_unresolved",
            "typed_schema_pass": True, "model_IR_executed": True, "analysis": analysis,
            "program_answer": candidate, "program_native_score": score, "source_grounding": grounding,
            "grading_scope": "original_fixed_TRAIN_label_only", "new_oracle_queries": 0}


def execution_binding(root):
    config = json.loads((root / "configs/rr_v2_preflight.json").read_text())
    protocol = json.loads((root / "reports/legalskillguard_rule_reasoning_protocol_v2.json").read_text())
    manifest = json.loads((root / config["source_manifest"]).read_text())
    semantic = {"executor": config["executor"], "teacher": config["teacher"],
                "protocol_methods": protocol["methods"], "A_limits": protocol["A_limits"],
                "B_limits": protocol["B_limits"], "training": protocol["training"], "thinking": protocol["thinking"]}
    return {"code_hash": scientific_code_binding(science_files(root)), "config_hash": digest(semantic),
            "data_hash": manifest["data_hash"], "source_manifest_hash": digest(manifest)}


def prepare(root: Path) -> dict:
    cfg = json.loads((root / "configs/rr_v2_preflight.json").read_text())
    protocol = json.loads((root / "reports/legalskillguard_rule_reasoning_protocol_v2.json").read_text())
    if cfg["max_targeted_bugfix_rounds"] != 2 or protocol["preflight"]["max_targeted_live_bugfix_rerun_rounds"] != 2 or \
            cfg["formal_run_enabled"] or protocol["run_enabled"]:
        raise ValueError("Explicit round2 protocol with formal execution disabled required")
    offline = json.loads((root / "reports/rr_v2_evidence/offline_latest.json").read_text())
    if offline["exit_code"] or not offline["network_blocked"] or any(
            hashlib.sha256((root / k).read_bytes()).hexdigest() != v for k, v in offline["files"].items()):
        raise ValueError("Current offline acceptance is required before dispatch")
    auth = json.loads((root / cfg["second_round_authorization"]).read_text())
    data = PreflightData(root, root / cfg["source_manifest"])
    old = json.loads((root / "reports/rr_v2_evidence/strict_contract_candidate/proposed_validation_plan.json").read_text())
    forensic = json.loads((root / "reports/rr_v2_evidence/strict_contract_round2/raw_recovery_audit.json").read_text())
    if forensic["counts"]["calls"] != 36 or forensic["counts"]["executable_restored"] != 0 or forensic["labels_loaded"]:
        raise ValueError("Resolve lossless raw recovery before spending any generation")
    binding = execution_binding(root)
    precheck = json.loads((root / "reports/rr_v2_evidence/strict_contract_round2/backend_schema_precheck.json").read_text())
    verified_schemas = {r["source"]: r for r in precheck["records"]}
    if len(verified_schemas) != 12 or not precheck["network_blocked"]:
        raise ValueError("All twelve source-bound schemas require an offline decoder check")
    stage = root / STAGE
    calls, order = {}, []
    for item in old["calls"]:
        source = data.public(item["source"])
        original_id = item["reuse_original_prompt_from_call_id"]
        request_path = None
        for parent in [root / "artifacts/rr_v2_preflight/oracle_guard", root / "artifacts/rr_v2_preflight"]:
            path = parent / "calls" / digest(original_id) / "request.json"
            if path.exists():
                request_path = path
                break
        if request_path is None:
            raise ValueError("Missing original literal request")
        original = json.loads(request_path.read_text())
        payload = original["payload"]
        if digest(payload) != item["original_payload_hash"]:
            raise ValueError("Original request changed")
        schema = proposal_schema(source["dataset"], source=source)
        verified = verified_schemas[source["key"]]
        if verified["schema_hash"] != digest(schema) or not verified["original_tokenization_exact_match"] or \
                digest(original["tokenization"]["tokens"]) != verified["token_ids_hash"] or \
                not verified["full_input_plus_reserved_output_fits"]:
            raise ValueError("Strict source schema or literal original prompt differs from offline check")
        revised = {**payload, "response_format": {"type": "json_schema", "json_schema": {
            "name": "rr_joint_proposal", "strict": True, "schema": schema}}}
        call_id = item["proposed_call_id"]
        immutable_json(stage / "planned_requests" / f"{digest(call_id)}.json", {
            "source": source["key"], "call_id": call_id, "original_id": original_id,
            "original_request_hash": original["request_hash"], "original_payload_hash": digest(payload),
            "payload": revised, "only_response_schema_changed": True,
            "tokenization": original["tokenization"], "tokenization_basis": "exact_original_serving_tokens_reverified_locally"})
        calls[call_id] = {"source": source["key"], "payload_hash": digest(revised), "original_id": original_id}
        order.append(call_id)
    base = json.loads((root / "artifacts/rr_v2_preflight/seal.oracle_guard.json").read_text())
    prior = base["processing_continuation"]["generation_binding"]
    ledger = BudgetLedger(root / cfg["ledger_path"], sources=data.manifest["allowlist"],
                          code_hash=prior["code_hash"], config_hash=prior["config_hash"])
    registered = ledger.register_strict_schema_round2(new_binding={k: binding[k] for k in ("code_hash", "config_hash")},
        authorization=auth, calls=calls, order=order, forensic_hash=digest(forensic))
    result = {"binding": binding, "protected_files": science_files(root), "registered_plan": registered,
              "config": cfg, "authorization_hash": digest(auth), "formal_run_enabled": False,
              "gate_max_physical_calls": 2, "all_calls_max": 12, "teacher_calls_added": 0,
              "backend_schema_precheck_hash": digest(precheck)}
    immutable_json(stage / "seal.json", result)
    return result


def run(root: Path, *, continue_after_gate: bool = False) -> dict:
    stage = root / STAGE
    seal = json.loads((stage / "seal.json").read_text())
    if science_files(root) != seal["protected_files"] or execution_binding(root) != seal["binding"]:
        raise ValueError("Frozen second-round implementation changed")
    cfg = seal["config"]
    data = PreflightData(root, root / cfg["source_manifest"])
    ledger = BudgetLedger(root / cfg["ledger_path"], sources=data.manifest["allowlist"],
        code_hash=seal["binding"]["code_hash"], config_hash=seal["binding"]["config_hash"])
    client = ExecutorClient(ledger, stage, cfg["executor"])
    client.readiness()
    if continue_after_gate:
        review = json.loads((stage / "gate_review.json").read_text())
        if review.get("approved") is not True or review.get("reviewed_call_ids") != seal["registered_plan"]["order"][:2]:
            raise ValueError("Review both actual typed/executed/semantic gate records before continuation")
    while True:
        with ledger.transaction() as db:
            state = json.loads(db.execute("SELECT value FROM meta WHERE key='strict_schema_round2_state'").fetchone()[0])
        if state["phase"] in {"stopped", "complete"}:
            break
        if not continue_after_gate and state["next_index"] >= 2:
            break
        if science_files(root) != seal["protected_files"]:
            raise ValueError("Frozen source/config changed before the next physical dispatch")
        call_id = seal["registered_plan"]["order"][state["next_index"]]
        planned = json.loads((stage / "planned_requests" / f"{digest(call_id)}.json").read_text())
        source = data.public(planned["source"])
        print(json.dumps({"stage": "strict_schema_round2", "call_index": state["next_index"] + 1,
                          "phase": state["phase"], "source": source["key"]}), flush=True)
        path = stage / "validations" / f"{digest(call_id)}.json"
        if path.exists():
            outcome = json.loads(path.read_text())
        else:
            try:
                payload = planned["payload"]
                def reuse_verified_tokenization(messages, *, thinking):
                    if messages != payload["messages"] or thinking is not True:
                        raise ValueError("Cannot reuse tokenization for a changed prompt/profile")
                    return planned["tokenization"]
                client.tokenize = reuse_verified_tokenization
                wire = client.generate(call_id, source=source["key"], purpose="preflight_bug_retry",
                    messages=payload["messages"], thinking=True, schema=payload["response_format"]["json_schema"]["schema"])
                outcome = validate_response(source, data.grade(source["key"]), wire["content"])
                outcome["wire_request_hash"] = wire["request_hash"]
            except Exception as exc:
                with ledger.transaction() as db:
                    reserved = db.execute("SELECT status FROM calls WHERE id=?", (call_id,)).fetchone()
                if reserved is None or reserved[0] == "reserved":
                    atomic_json(stage / "unreconciled_error.json", {"call_id": call_id, "error": repr(exc),
                                "reserved": reserved is not None, "no_implicit_retry": True})
                    raise
                outcome = {"pass": False, "systemic_failure": True, "reason": "charged_wire_or_processing_failure", "error": repr(exc)}
            immutable_json(path, outcome)
        state = ledger.record_strict_schema_validation(call_id, outcome)
        atomic_json(stage / "status.json", state)
        print(json.dumps({"validated": source["key"], "pass": outcome["pass"],
                          "reason": outcome["reason"], "phase_after": state["phase"]}), flush=True)
    result = {"state": state, "ledger": ledger.export(), "goal_complete": False,
              "formal_training_started": False, "frozen_test_started": False}
    name = "round_result.json" if state["phase"] in {"stopped", "complete"} else "gate_result.json"
    immutable_json(stage / name, result)
    return result
