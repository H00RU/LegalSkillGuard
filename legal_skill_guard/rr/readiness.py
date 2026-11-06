"""Bind formal-only offline integration to an unchanged, completed real pilot.

This receipt cannot authorize model calls. Historical pilot bindings and charged
rows remain intact; future outputs bind to their own current execution code.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

from .checkpoint import Checkpoints, immutable_json
from .coverage import digest
from .example_synthesis import fit_shared_examples
from .learning import SkillLibrary
from .preflight import active_seal_path, science_files, scientific_code_binding

FORMAL_ONLY_FILES = {
    "legal_skill_guard/rr/routing.py", "legal_skill_guard/rr/formal.py",
    "legal_skill_guard/rr/example_synthesis.py", "legal_skill_guard/rr/readiness.py",
    "tests/test_rr_pipeline.py",
}
OPERATIONAL_FILES = {"configs/rr_v2_preflight.json", "configs/rr_v2_formal.json",
                     "reports/legalskillguard_rule_reasoning_protocol_v2.json"}
RECEIPT = "reports/rr_v2_evidence/formal_readiness_core.json"


def current_binding(root: Path) -> dict:
    config = json.loads((root / "configs/rr_v2_preflight.json").read_text())
    protocol = json.loads((root / "reports/legalskillguard_rule_reasoning_protocol_v2.json").read_text())
    manifest = json.loads((root / config["source_manifest"]).read_text())
    for name, key in [("public_train.json", "public_train"), ("grading_only/train.json", "grading_train")]:
        if _file_hash(root / "data/packets/rr_v2" / name) != manifest["packet_sha256"][key]:
            raise ValueError("Fixed TRAIN packet changed")
    semantic = {"executor": config["executor"], "teacher": config["teacher"],
                "protocol_methods": protocol["methods"], "A_limits": protocol["A_limits"],
                "B_limits": protocol["B_limits"], "training": protocol["training"],
                "thinking": protocol["thinking"]}
    return {"code_hash": scientific_code_binding(science_files(root)),
            "config_hash": digest(semantic), "data_hash": manifest["data_hash"],
            "source_manifest_hash": digest(manifest)}


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(root: Path) -> dict:
    root = Path(root)
    config = json.loads((root / "configs/rr_v2_preflight.json").read_text())
    base = root / config["artifact_directory"]
    seal_path = active_seal_path(base)
    seal = json.loads(seal_path.read_text())
    stage = base / seal.get("processing_continuation", {}).get("artifact_subdirectory", "")
    completion = json.loads((stage / "pilot_completion.json").read_text())
    if seal["offline_mock"] or completion["sources"] != 20 or not completion["restore_verified"] or \
            not completion["teacher_batch_record_accepted"]:
        raise ValueError("Formal preparation requires the actual completed20-source pilot")
    files = science_files(root)
    changed = {name for name in set(files) | set(seal["protected_files"])
               if files.get(name) != seal["protected_files"].get(name)}
    compatibility_path = root / 'reports/rr_v2_evidence/semantic_preflight/wire_replay.json'
    compatibility = None
    if not changed <= FORMAL_ONLY_FILES:
        # This is a completed-stage proof, never a generic relaxation of sealing.
        allowed = FORMAL_ONLY_FILES | {'legal_skill_guard/rr/engine.py', 'legal_skill_guard/rr/preflight.py',
                    'legal_skill_guard/rr/source_learning.py', 'experiments/rr_v2_semantic_preflight.py',
                    'experiments/rr_v2_core_preflight.py'}
        compatibility = json.loads(compatibility_path.read_text())
        learning=json.loads((root/'reports/rr_v2_evidence/semantic_preflight/learning_replay.json').read_text())
        if not learning['all_exact'] or learning.get('execution_binding')!=current_binding(root):
            raise ValueError('Current B main algorithm must reproduce the bound source semantics')
        if not seal.get('study_preflight_revision') or not changed <= allowed or \
                compatibility.get('execution_binding') != current_binding(root) or \
                compatibility.get('preflight_binding') != seal['binding'] or \
                not compatibility.get('all_payloads_equal') or not compatibility.get('all_analyses_equal') or \
                compatibility.get('sources') != 20 or compatibility.get('records') != 36 or \
                compatibility.get('new_model_calls') != 0 or \
                not compatibility.get('current_real_wire_bytes_equal'):
            raise ValueError('Changed pilot code needs exact complete generation/output compatibility evidence')
    offline = json.loads((root / "reports/rr_v2_evidence/offline_latest.json").read_text())
    if offline["exit_code"] or not offline["network_blocked"] or any(
            _file_hash(root / name) != wanted for name, wanted in offline["files"].items()):
        raise ValueError("Offline acceptance is absent or stale")
    required = {n for n in files if n.startswith(("legal_skill_guard/rr/", "experiments/rr_v2", "tests/test_rr")) and n.endswith(".py")}
    if not required <= set(offline["files"]):
        raise ValueError("Offline receipt does not cover the complete implementation")
    manifest = json.loads((root / config["source_manifest"]).read_text())
    public = json.loads((root / "data/packets/rr_v2/public_train.json").read_text())["sources"]
    execution_binding = current_binding(root)
    public = {s["key"]: s for s in public}
    grades = json.loads((root / "data/packets/rr_v2/grading_only/train.json").read_text())["sources"]
    grades = {sid: grades[sid] for sid in manifest["pilot_order"]}
    source_paths = [stage / "pilot_sources" / f"{digest(s)}.json" for s in manifest["pilot_order"]]
    records = [json.loads(p.read_text()) for p in source_paths]
    if [r["source"] for r in records] != manifest["pilot_order"] or any(
            r["binding"] != seal["binding"] or r["offline_mock"] or len(r["calls"]) > 2 or
            len(r["learning"]["oracle_views"]) > 4 for r in records):
        raise ValueError("Actual pilot source bindings or budgets differ")
    pointer = json.loads((stage / "state.json").read_text())
    checkpoint = Checkpoints(stage / "checkpoints", seal["binding"]).load(pointer["checkpoint"])
    if checkpoint["state"]["complete_sources"] != manifest["pilot_order"] or \
            checkpoint["state"]["source_record_hashes"] != [digest(r) for r in records]:
        raise ValueError("Actual complete checkpoint source records differ")
    frozen = SkillLibrary.restore(stage / "partial_library.frozen.json")
    if digest(frozen.export()) != completion["library_sha256"]:
        raise ValueError("Actual frozen partial library differs")
    restore_path = root / ("reports/rr_v2_evidence/semantic_preflight/restore.json"
                           if seal.get('study_preflight_revision') else
                           "reports/rr_v2_evidence/actual_pilot_restore_verified.json")
    restore = json.loads(restore_path.read_text())
    if not restore["network_and_subprocess_blocked"] or restore["model_calls_added"] or restore["oracle_views_added"]:
        raise ValueError("Completed pilot did not pass free restore verification")
    example_model = fit_shared_examples(public, records, grades)
    example_path = stage / "MB_preflight_examples.frozen.json"
    immutable_json(example_path, example_model)
    paths = [seal_path, *source_paths, example_path, restore_path,
             stage / "checkpoints" / f"{pointer['checkpoint']}.json",
             *(stage / n for n in ["pilot_completion.json", "partial_library.frozen.json", "state.json",
                                   "teacher_batch1.json", "B1_preflight_partial.json", "teacher_transport_retry_receipt.json"])]
    if compatibility is not None:
        paths.append(compatibility_path)
    db = sqlite3.connect(root / config["ledger_path"])
    try:
        rows = db.execute("SELECT * FROM calls ORDER BY id").fetchall()
    finally:
        db.close()
    if any(row[6] not in {"completed", "failed"} for row in rows):
        raise ValueError("A model call is still live or unresolved")
    counts = {role: sum(row[1] == role for row in rows) for role in ("executor", "teacher")}
    if seal.get('study_preflight_revision'):
        authorization = json.loads((root / config['repair_execution_policy']).read_text())
        db = sqlite3.connect(root / config['ledger_path'])
        try:
            row = db.execute("SELECT value FROM meta WHERE key='study_preflight_authorization'").fetchone()
        finally:
            db.close()
        if not row or json.loads(row[0]) != authorization:
            raise ValueError('Current user authorization is absent from persistent ledger')
        if counts['executor'] > 6000 or counts['teacher'] > 20:
            raise ValueError('Original study allocation exceeded')
    elif counts["executor"] > 100 or counts["teacher"] > 2:
        raise ValueError("Historical preflight budget exceeded")
    transport = json.loads((stage / "teacher_transport_retry_receipt.json").read_text())
    teacher = json.loads((stage / "teacher_batch1.json").read_text())
    if teacher["response"]["model"] != config["teacher"]["model"] or \
            not transport["request_identical"]:
        raise ValueError("Teacher transport evidence differs")
    core_path=root/'reports/rr_v2_evidence/semantic_preflight/core_acceptance.json'
    core=json.loads(core_path.read_text())
    if core['execution_binding']!=execution_binding or not core['complete'] or not core['A_pass'] or not core['B_pass'] or \
            core['fallback_native_results_count_as_core_success'] or core['legacy_or_default_outputs_count_as_core_success']:
        raise ValueError('Separate current real A/B primary semantic evidence is required')
    core_files=[core_path,root/'reports/rr_v2_evidence/semantic_preflight/core_wire_compatibility.json',
                root/'artifacts/rr_v2_preflight/core_primary_v1/seal.json'] + [root/item['record_path'] for item in core['records']]
    paths.extend(core_files)
    result = {"schema": 1, "scope": "implementation_and_bounded_preflight_only",
              "engineering_ready": True, "core_A_primary_semantic_pass": True, "core_B_primary_semantic_pass": True,
              "core_primary_sources": core["fresh_primary_source_count"], "formal_launch_authorized": False,
              "execution_binding": execution_binding, "preflight_binding": seal["binding"],
              "formal_only_changed_files": sorted(changed),
              "unchanged_actual_pilot_components_verified": True,
              "protected_scientific_files": {n: v for n, v in files.items() if n not in OPERATIONAL_FILES},
              "preserved_pilot_files": {str(p.relative_to(root)): _file_hash(p) for p in paths},
              "original_call_ids": [row[0] for row in rows], "original_call_rows_hash": digest(rows),
              "preflight_counts": counts, "extra_model_calls_for_formal_integration": 0,
              "teacher_transport": {"executable": transport["actual_retry_executable"],
                                    "executable_sha256": transport["direct_cli_sha256"],
                                    "configured_launcher_sha256": transport["launcher_sha256"],
                                    "same_model_parameters": True},
              "offline_receipt_hash": digest(offline),
              "not_a_formal_performance_result": True}
    immutable_json(root / RECEIPT, result)
    return result


def validate(root: Path, preflight_binding: dict) -> dict:
    result = json.loads((root / RECEIPT).read_text())
    if not result["engineering_ready"] or result["preflight_binding"] != preflight_binding or \
            current_binding(root) != result["execution_binding"]:
        raise ValueError("Formal execution preparation binding differs")
    files = {n: v for n, v in science_files(root).items() if n not in OPERATIONAL_FILES}
    if files != result["protected_scientific_files"] or any(
            _file_hash(root / name) != wanted for name, wanted in result["preserved_pilot_files"].items()):
        raise ValueError("Prepared execution code or preserved actual pilot changed")
    config = json.loads((root / "configs/rr_v2_preflight.json").read_text())
    db = sqlite3.connect(root / config["ledger_path"])
    try:
        ids = result["original_call_ids"]
        rows = db.execute("SELECT * FROM calls WHERE id IN (" + ",".join("?" for _ in ids) + ") ORDER BY id", ids).fetchall()
    finally:
        db.close()
    if digest(rows) != result["original_call_rows_hash"]:
        raise ValueError("Historical charged calls were altered")
    transport = result["teacher_transport"]
    if _file_hash(Path(transport["executable"])) != transport["executable_sha256"]:
        raise ValueError("Verified teacher executable changed")
    return result
