"""One source-scoped native-contract repair, after preserving the terminal run."""
from __future__ import annotations

import ast
import hashlib
import json
import shutil
import tarfile
from pathlib import Path

from .checkpoint import immutable_json
from .coverage import digest
from .data_store import PreflightData
from .engine import PROPOSAL_SCHEMA, analyze, proposal_schema, wire_messages
from .ledger import BudgetLedger
from .preflight import create_seal, generation_contract, science_files


def seal_native_contract_repair(root: Path) -> dict:
    root = Path(root)
    config = json.loads((root / "configs/rr_v2_preflight.json").read_text())
    artifacts = root / config["artifact_directory"]
    preserved = artifacts / "preserved_before_native_contract_fix"
    receipt = json.loads((preserved / "receipt.json").read_text())
    original = json.loads((preserved / "seal.json").read_text())
    if not receipt["client_terminal_verified"] or receipt["executor_charged"] != 40 or \
            receipt["teacher_charged"] or receipt["paid_model_rerun_rounds_used"]:
        raise ValueError("Preserve the complete original forty and unused rerun allowance first")
    if Path(f"/proc/{receipt['client_pid']}").exists():
        raise ValueError("Stop and preserve before changing scientific source")
    archive_path = preserved / "frozen_scientific_files.tar.gz"
    if hashlib.sha256(archive_path.read_bytes()).hexdigest() != receipt["frozen_archive_sha256"]:
        raise ValueError("Preserved source snapshot differs")
    with tarfile.open(archive_path) as archive:
        old_engine = archive.extractfile("legal_skill_guard/rr/engine.py").read().decode()
    if generation_contract(old_engine) != generation_contract((root / "legal_skill_guard/rr/engine.py").read_text()):
        raise ValueError("The shared source compiler instructions or base schema changed")
    current = science_files(root)
    allowed = {"legal_skill_guard/rr/engine.py", "legal_skill_guard/rr/ledger.py",
               "legal_skill_guard/rr/preflight.py", "legal_skill_guard/rr/repair.py",
               "legal_skill_guard/rr/formal.py", "legal_skill_guard/rr/routing.py",
               "experiments/rr_v2_preflight.py", "tests/test_rr_engine.py", "tests/test_rr_pipeline.py"}
    changed = {k for k in current.keys() | original["protected_files"].keys()
               if current.get(k) != original["protected_files"].get(k)}
    if not changed <= allowed or current["legal_skill_guard/rr/client.py"] != original["protected_files"]["legal_skill_guard/rr/client.py"]:
        raise ValueError("Repair changed unrelated runtime, client, data or configuration")
    for name, wanted in receipt["wire_artifact_hashes"].items():
        if hashlib.sha256((artifacts / name).read_bytes()).hexdigest() != wanted:
            raise ValueError("An original billed response was altered")
    data = PreflightData(root, root / config["source_manifest"])
    old_generation = receipt["generation_binding"]
    ledger = BudgetLedger(root / config["ledger_path"], sources=data.manifest["allowlist"],
                          code_hash=old_generation["code_hash"], config_hash=old_generation["config_hash"])
    calls = ledger.export()["calls"]
    if len(calls) != 40 or any(c["status"] != "completed" for c in calls):
        raise ValueError("The original forty calls are not terminal")
    by_id = {c["id"]: c for c in calls}
    unaffected, affected = {}, []
    for path in sorted((preserved / "thinking_records").glob("*.json")):
        record = json.loads(path.read_text())
        source = data.public(record["source"])
        call = by_id[f"thinking:{source['key']}:{record['thinking']}"]
        if call["request_hash"] != record["wire_request_hash"]:
            raise ValueError("Source/profile request binding differs")
        request = json.loads((Path(call["result"]["artifact_directory"]) / "request.json").read_text()) if not original["offline_mock"] else None
        if source["dataset"] == "OpenExempt":
            affected.append({"source": source["key"], "thinking": record["thinking"], "record_hash": digest(record)})
            continue
        if proposal_schema(source["dataset"]) != PROPOSAL_SCHEMA:
            raise ValueError("An unaffected response schema changed")
        if request is not None and (request["payload"]["messages"] != wire_messages(source) or request["payload"]["response_format"]["json_schema"]["schema"] != proposal_schema(source["dataset"])):
            raise ValueError("An unaffected wire input changed")
        checked = analyze(source, call["result"]["content"])
        if digest(checked) != digest(record["analysis"]):
            raise ValueError("An unaffected source analysis changed")
        unaffected[call["id"]] = {"request_hash": call["request_hash"], "record_hash": digest(record),
                                  "analysis_hash": digest(checked), "prompt_hash": digest(wire_messages(source))}
    if len(affected) != 8 or len(unaffected) != 32:
        raise ValueError("Repair must preserve exactly eight affected and thirty-two unchanged profiles")
    repair = {"kind": "OE_native_output_contract_only", "generation_binding": old_generation,
              "prior_analysis_binding": original["binding"], "unaffected_calls": unaffected,
              "affected_original_records": affected, "thinking_directory": "thinking_native_contract_fix",
              "selection_file": "thinking_selection.native_contract_fix.json",
              "max_additional_model_calls": 8, "max_actual_rerun_rounds": 1,
              "new_sources_seeds_or_quality_parameters": False}
    result = create_seal(root, offline_mock=original["offline_mock"], wire_repair=repair)
    registration = ledger.start_model_rerun_round(reason="OE public text refers to a supplied native schema but EC/EV and citation/claim_value fields were absent from that schema",
        new_binding={k: result["binding"][k] for k in ("code_hash", "config_hash")})
    immutable_json(artifacts / "native_contract_repair_receipt.json", {
        "repair": repair, "registration": registration, "new_binding": result["binding"],
        "all_original_calls_still_charged": 40, "original_records_preserved": True})
    return result


def seal_oracle_processing_repair(root: Path) -> dict:
    """Flush native reference output and quarantine failed views; no model rerun."""
    root = Path(root)
    config = json.loads((root / "configs/rr_v2_preflight.json").read_text())
    base = root / config["artifact_directory"]
    preserved = base / "preserved_before_sara_oracle_fix"
    receipt = json.loads((preserved / "receipt.json").read_text())
    original = json.loads((preserved / "seal.json").read_text())
    if not receipt["client_terminal_verified"] or Path(f"/proc/{receipt['client_pid']}").exists():
        raise ValueError("The previous client must be terminal and preserved")
    archive_path = preserved / "frozen_scientific_files.tar.gz"
    if hashlib.sha256(archive_path.read_bytes()).hexdigest() != receipt["frozen_archive_sha256"]:
        raise ValueError("Preserved scientific snapshot differs")
    current = science_files(root)
    allowed = {"legal_skill_guard/rr/source_learning.py", "legal_skill_guard/rr/preflight.py",
               "legal_skill_guard/rr/ledger.py", "legal_skill_guard/rr/formal.py", "legal_skill_guard/rr/repair.py",
               "experiments/rr_v2_preflight.py", "tests/test_rr_pipeline.py"}
    changed = {k for k in current.keys() | original["protected_files"].keys()
               if current.get(k) != original["protected_files"].get(k)}
    if not changed <= allowed:
        raise ValueError("An oracle-only continuation cannot change model code, inputs or configuration")
    def ingestion_ast(source):
        return ast.dump(next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == "ingest_source"), include_attributes=False)
    with tarfile.open(archive_path) as archive:
        old_ingestion = archive.extractfile("legal_skill_guard/rr/preflight.py").read().decode()
    if ingestion_ast(old_ingestion) != ingestion_ast((root / "legal_skill_guard/rr/preflight.py").read_text()):
        raise ValueError("The model-facing source ingestion function changed")
    generation = original["binding"]
    ledger = BudgetLedger(root / config["ledger_path"], sources=original["allowlist"],
                          code_hash=generation["code_hash"], config_hash=generation["config_hash"])
    calls = ledger.export()["calls"]
    if any(c["status"] != "completed" for c in calls):
        raise ValueError("No ambiguous model request may be retried by a processing repair")
    continuation = {"kind": "native_reference_flush_and_failed_view_quarantine",
                    "generation_binding": generation, "thinking_binding": generation,
                    "artifact_subdirectory": "oracle_guard", "additional_model_reruns": 0,
                    "prior_scientific_binding": original["binding"], "ingestion_ast_hash": digest(ingestion_ast(old_ingestion)),
                    "unchanged_generation_components": {name: current[name] for name in (
                        "legal_skill_guard/rr/engine.py", "legal_skill_guard/rr/client.py")},
                    "prior_call_hashes": {c["id"]: c["request_hash"] for c in calls}}
    result = create_seal(root, offline_mock=original["offline_mock"], wire_repair=original.get("wire_repair"),
                         processing_continuation=continuation)
    ledger.register_processing_continuation(new_binding={k: result["binding"][k] for k in ("code_hash", "config_hash")},
                                           generation_binding=ledger.execution_binding)
    stage = base / continuation["artifact_subdirectory"]
    stage.mkdir(exist_ok=True)
    if (base / "oracle_views").exists():
        shutil.copytree(base / "oracle_views", stage / "oracle_views", dirs_exist_ok=True)
    name = original.get("wire_repair", {}).get("selection_file", "thinking_selection.json")
    immutable_json(stage / name, json.loads((base / name).read_text()))
    immutable_json(base / "oracle_processing_repair_receipt.json", {"continuation": continuation,
                   "new_scientific_binding": result["binding"], "all_prior_calls_still_charged": len(calls),
                   "new_model_reruns": 0, "failed_view_slots_retained": True})
    return result
