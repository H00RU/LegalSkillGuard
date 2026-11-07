"""Sealed, resumable state machine for exactly the authorized live preflight."""
from __future__ import annotations

import ast
import hashlib
import json
import os
import tempfile
import time
from copy import deepcopy
from pathlib import Path

from .checkpoint import Checkpoints, immutable_json
from .client import ExecutorClient, TeacherClient
from .controls import SharedMaterial, project_material
from .coverage import digest
from .data_store import PreflightData
from .engine import analyze, proposal_schema
from .engine import wire_messages as messages
from .learning import SkillLibrary
from .ledger import BudgetLedger
from .scoring import official_openexempt_metrics, task_score
from .source_learning import DurableOracle, learn_source
from .thinking import select_thinking
from .compilation import prepare_request


def atomic_json(path: Path, value: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix=".state-")
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, sort_keys=True, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def science_files(root: Path) -> dict[str, str]:
    files = [*sorted((root / "legal_skill_guard/rr").glob("*.py")),
             *sorted((root / "experiments").glob("rr_v2*.py")),
             *sorted((root / "tests").glob("test_rr*.py"))]
    files += sorted((root / "tests/fixtures").glob("rr_*.json"))
    files += [root / name for name in ["legal_skill_guard/openexempt.py",
              "legal_skill_guard/inference/codex_cli_client.py", "README.md", "pyproject.toml", "uv.lock",
              "reports/legalskillguard_rule_reasoning_protocol_v2.json", "configs/rr_v2_preflight.json"]]
    if (root / "configs/rr_v2_formal.json").exists():
        files.append(root / "configs/rr_v2_formal.json")
    for directory, pattern in [("data/cache/openexempt/servantez-OpenExempt-ec6fa25", "*.py"),
                                ("data/cache/rr_v2/RuleArena/airline", "*.py"),
                                ("data/cache/rr_v2/SARA_reference/statutes/prolog", "*.pl")]:
        files += sorted((root / directory).rglob(pattern))
    for directory in ["data/cache/openexempt/servantez-OpenExempt-ec6fa25/data", "data/cache/rr_v2/RuleArena/airline/fee_tables"]:
        files += [p for p in (root / directory).rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    runtime = root / "reports/rr_v2_evidence/reference_runtime.json"
    if runtime.exists():
        files.append(runtime)
        files += [root / name for name in json.loads(runtime.read_text())["files"]]
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files if p.is_file()}


def scientific_code_binding(files: dict) -> str:
    operational = {"configs/rr_v2_preflight.json", "configs/rr_v2_formal.json",
                   "reports/legalskillguard_rule_reasoning_protocol_v2.json"}
    return digest({k: v for k, v in files.items() if k not in operational})


def active_seal_path(artifacts: Path) -> Path:
    for name in ("seal.semantic_path.json", "seal.oracle_guard.json", "seal.native_contract_fix.json", "seal.parser_fix.json", "seal.json"):
        if (artifacts / name).exists():
            return artifacts / name
    return artifacts / "seal.json"


def create_seal(root: Path, *, offline_mock: bool = False, processing_repair: dict | None = None,
                wire_repair: dict | None = None, processing_continuation: dict | None = None) -> dict:
    root = Path(root)
    config = json.loads((root / "configs/rr_v2_preflight.json").read_text())
    protocol = json.loads((root / "reports/legalskillguard_rule_reasoning_protocol_v2.json").read_text())
    if config["formal_run_enabled"] or config["frozen_test_enabled"] or protocol["run_enabled"] or \
            protocol["execution_request"]["frozen_test_enabled"]:
        raise ValueError("This goal cannot enable formal training/evaluation")
    data = PreflightData(root, root / config["source_manifest"])
    evidence = json.loads((root / "reports/rr_v2_evidence/offline_latest.json").read_text())
    if evidence["exit_code"] or not evidence["network_blocked"]:
        raise ValueError("Offline acceptance must pass before sealing")
    for name, wanted in evidence["files"].items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != wanted:
            raise ValueError("Offline evidence is stale: " + name)
    files = science_files(root)
    required_checks = {name for name in files if name.startswith(("legal_skill_guard/rr/", "experiments/rr_v2", "tests/test_rr")) and name.endswith(".py")}
    if not offline_mock and not required_checks <= set(evidence["files"]):
        raise ValueError("Offline receipt does not cover all current RR implementation and tests")
    # Authorization/status files are protected during the live job, while the
    # reproducibility binding uses scientific code and generation parameters.
    semantic_config = {"executor": config["executor"], "teacher": config["teacher"],
                       "protocol_methods": protocol["methods"], "A_limits": protocol["A_limits"],
                       "B_limits": protocol["B_limits"], "training": protocol["training"],
                       "thinking": protocol["thinking"]}
    binding = {"code_hash": scientific_code_binding(files), "config_hash": digest(semantic_config),
               "data_hash": data.manifest["data_hash"],
               "source_manifest_hash": digest(data.manifest)}
    result = {"schema": 1, "stage": "preflight", "offline_mock": offline_mock,
              "binding": binding, "protected_files": files, "config": config,
              "allowlist": data.manifest["allowlist"], "pilot_order": data.order,
              "offline_evidence_hash": digest(evidence), "formal_execution_enabled": False}
    if processing_repair is not None:
        result["processing_repair"] = processing_repair
    if wire_repair is not None:
        result["wire_repair"] = wire_repair
    if processing_continuation is not None:
        result["processing_continuation"] = processing_continuation
    filename = "seal.oracle_guard.json" if processing_continuation else "seal.native_contract_fix.json" if wire_repair else "seal.parser_fix.json" if processing_repair else "seal.json"
    immutable_json(root / config["artifact_directory"] / filename, result)
    return result


def generation_contract(source: str) -> dict:
    """Literal AST identities of every engine item used to form wire inputs."""
    tree = ast.parse(source)
    wanted = {"PROPOSAL_SCHEMA", "messages", "source_text"}
    found = {}
    for node in tree.body:
        name = node.name if isinstance(node, (ast.FunctionDef, ast.ClassDef)) else \
            node.targets[0].id if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) else None
        if name in wanted:
            found[name] = digest(ast.dump(node, include_attributes=False))
    if set(found) != wanted:
        raise ValueError("Cannot verify the complete generation contract")
    return found


def seal_parser_repair(root: Path) -> dict:
    """One deterministic parser repair; completed generations are never redrawn.

    Generation records keep their exact original client/code/config binding.
    New analysis records use the repaired scientific binding, in a new directory.
    Only unchanged wire construction can continue the remaining fixed requests.
    """
    import tarfile
    root = Path(root)
    cfg = json.loads((root / "configs/rr_v2_preflight.json").read_text())
    artifacts = root / cfg["artifact_directory"]
    original = json.loads((artifacts / "seal.json").read_text())
    preserved = artifacts / "preserved_before_parser_fix"
    receipt = json.loads((preserved / "receipt.json").read_text())
    if not receipt["client_terminal_verified"] or receipt["error"] != "RecursionError during JSON decoding of the fourth completed wire response":
        raise ValueError("Parser repair requires the preserved terminal failure")
    if Path(f"/proc/{receipt['client_pid']}").exists():
        raise ValueError("Stop and preserve before repairing scientific code")
    archive_path = preserved / "frozen_scientific_files.tar.gz"
    if hashlib.sha256(archive_path.read_bytes()).hexdigest() != receipt["frozen_archive_sha256"]:
        raise ValueError("Preserved frozen source changed")
    with tarfile.open(archive_path) as archive:
        old_engine = archive.extractfile("legal_skill_guard/rr/engine.py").read().decode()
    contract = generation_contract(old_engine)
    if generation_contract((root / "legal_skill_guard/rr/engine.py").read_text()) != contract:
        raise ValueError("A processing-only repair cannot alter model instructions or response schema")
    current = science_files(root)
    allowed = {"legal_skill_guard/rr/engine.py", "legal_skill_guard/rr/preflight.py",
               "legal_skill_guard/rr/formal.py", "experiments/rr_v2_preflight.py",
               "tests/test_rr_engine.py", "tests/test_rr_pipeline.py"}
    changed = {name for name in current.keys() | original["protected_files"].keys()
               if current.get(name) != original["protected_files"].get(name)}
    if not changed <= allowed or "legal_skill_guard/rr/engine.py" not in changed:
        raise ValueError("Repair changed unrelated generation, reference, configuration or data files")
    # No successful prior analysis may silently change its scientific result.
    data = PreflightData(root, root / cfg["source_manifest"])
    validated, affected = [], []
    ledger = BudgetLedger(root / cfg["ledger_path"], sources=original["allowlist"],
                          code_hash=original["binding"]["code_hash"], config_hash=original["binding"]["config_hash"])
    calls = ledger.export()["calls"]
    if len(calls) != 4 or any(r["status"] != "completed" for r in calls):
        raise ValueError("Unexpected charged state; do not reset or start another sweep")
    by_hash = {r["request_hash"]: r["result"] for r in calls}
    for path in sorted((artifacts / "thinking").glob("*.json")):
        record = json.loads(path.read_text())
        checked = analyze(data.public(record["source"]), by_hash[record["wire_request_hash"]]["content"])
        proof = {"record": str(path.relative_to(root)), "record_hash": digest(record),
                 "analysis_hash": digest(checked)}
        if digest(checked) != digest(record["analysis"]):
            if record["source"] != calls[-1]["source"] or checked["structural_pass"] or \
                    not any("bounded JSON nesting" in x for x in checked["diagnostics"]) or \
                    digest({k: v for k, v in checked.items() if k != "diagnostics"}) != \
                    digest({k: v for k, v in record["analysis"].items() if k != "diagnostics"}):
                raise ValueError("Parser repair altered an unaffected completed analysis")
            affected.append(proof)
        else:
            validated.append(proof)
    fourth = calls[-1]
    checked = analyze(data.public(fourth["source"]), fourth["result"]["content"])
    if checked["structural_pass"] or not any("bounded JSON nesting" in x for x in checked["diagnostics"]):
        raise ValueError("The original fault was not classified as a retained parse failure")
    repair = {"kind": "bounded_parser_processing_only", "generation_binding": original["binding"],
              "prior_seal_hash": digest(original), "generation_contract": contract,
              "unchanged_generation_client_hash": current["legal_skill_guard/rr/client.py"],
              "affected_sources": [fourth["source"]], "unaffected_analyses_verified": validated,
              "retained_parse_failures_reclassified": affected,
              "prior_model_calls": [{"id": r["id"], "request_hash": r["request_hash"]} for r in calls],
              "new_model_reruns": 0, "thinking_directory": "thinking_parser_fix"}
    result = create_seal(root, processing_repair=repair, offline_mock=original["offline_mock"])
    ledger.start_bugfix_round(reason=receipt["error"], affected_sources=repair["affected_sources"],
                             new_code_hash=result["binding"]["code_hash"])
    immutable_json(artifacts / "parser_repair_receipt.json", {"repair": repair,
                   "new_analysis_binding": result["binding"], "generation_binding_unchanged": True,
                   "executor_charged_before_resume": 4, "teacher_charged_before_resume": 0})
    return result


def score_source(source: dict, analysis: dict, grade: dict, *, native_oe: bool = True) -> dict:
    dataset, answer = source["dataset"], analysis.get("answer")
    if dataset == "OpenExempt":
        scores = {}
        for family in ("EC", "EV"):
            value = answer.get(family) if isinstance(answer, dict) else None
            score = task_score(dataset, value, grade["targets"][family], family=family)
            if native_oe and isinstance(value, dict):
                score["official_metrics"] = official_openexempt_metrics(family, value, grade["targets"][family])
            scores[family] = score
        return {"task_correct": all(s["correct"] for s in scores.values()), "views": scores}
    result = task_score(dataset, answer, grade["answer"])
    return {"task_correct": result["correct"], "views": {"main": result}}


def ingest_source(*, source: dict, grade: dict, library: SkillLibrary, thinking: bool,
                  call, learner, ledger, artifacts: Path, binding: dict,
                  purpose: str, id_prefix: str, offline_mock: bool, oracle_artifacts: Path | None = None,
                  tokenize=None, request_config=None) -> dict:
    calls, previous, learning, actions, remaining = [], None, None, [], 5.0
    learning_attempts = []
    for step in range(2):
        suffix = "\nAvailable learned patterns: " + json.dumps([
            {k: p[k] for k in ('pattern_hash', 'pattern')} for p in library.patterns])
        user_suffix = ''
        if learning is not None:
            user_suffix = "\nTraining interface repair evidence (no reference program): " + json.dumps({
                "status": learning["status"], "refinement": learning.get("refinement"),
                "learned_pattern": learning.get("learned_pattern"),
                'connector_synthesis_status': learning.get('connector_synthesis_status'),
                'schema_repair_needed': learning.get('schema_repair_needed', False)})
        started = time.monotonic()
        prepared = prepare_request(source, previous=previous, system_suffix=suffix,
            user_suffix=user_suffix, tokenize=tokenize, request_config=request_config, thinking=thinking,
            planning_seconds=remaining)
        remaining = max(0, remaining - (time.monotonic() - started))
        if prepared['action'] is not None:
            actions.append(prepared['action'])
        wire = call(call_id=f"{id_prefix}:{source['key']}:{step}", source=source,
                    purpose=purpose, prompt=prepared['messages'], thinking=thinking, schema=prepared['schema'])
        started = time.monotonic()
        analysis = analyze(source, wire['content'], planning_seconds=remaining, library=library.export())
        remaining = max(0, remaining - (time.monotonic() - started))
        calls.append({"step": step, "request_hash": wire["request_hash"], "analysis": analysis,
                      "raw_content": wire["content"], "usage": wire["usage"],
                      "elapsed_seconds": wire["elapsed_seconds"]})
        previous = analysis
        if learning is None or learning.get('schema_repair_needed', False):
            oracle = DurableOracle(ledger, oracle_artifacts or artifacts, source, grade)
            learning = learner(source, grade, oracle, proposal=analysis.get('executable_proposal'))
            learning_attempts.append({'step': step, 'learning': deepcopy(learning)})
        if analysis["certificate_status"] == "completion_stable":
            break
    return {"source": source["key"], "dataset": source["dataset"], "calls": calls,
            "analysis": previous, "learning": learning,
            "score": score_source(source, previous, grade, native_oe=not offline_mock),
            "binding": binding, "input_hash": source["content_hash"], "offline_mock": offline_mock,
            "translation_actions": actions, 'learning_attempts': learning_attempts}


class Preflight:
    def __init__(self, root: Path, *, executor=None, teacher=None, learner=None, oracle_artifacts=None):
        self.root = Path(root)
        self.config = json.loads((self.root / "configs/rr_v2_preflight.json").read_text())
        base = self.root / self.config["artifact_directory"]
        self.seal = json.loads(active_seal_path(base).read_text())
        self.artifacts = base / self.seal.get("processing_continuation", {}).get("artifact_subdirectory", "")
        self.data = PreflightData(self.root, self.root / self.config["source_manifest"])
        self.verify_binding()
        generation = self.seal.get("processing_continuation", self.seal.get("processing_repair", {})).get("generation_binding", self.seal["binding"])
        self.ledger = BudgetLedger(self.root / self.config["ledger_path"], sources=self.seal["allowlist"],
                                   code_hash=generation["code_hash"], config_hash=generation["config_hash"])
        self.executor = executor or ExecutorClient(self.ledger, self.artifacts, self.config["executor"])
        self.teacher = teacher or TeacherClient(self.ledger, self.artifacts, self.config["teacher"])
        self.learner = learner or learn_source
        self.oracle_artifacts = Path(oracle_artifacts) if oracle_artifacts else self.artifacts
        if self.seal["offline_mock"] != bool(getattr(self.executor, "is_offline_mock", False)):
            raise ValueError("A mock seal cannot dispatch a real model or masquerade as live evidence")
        if self.seal["offline_mock"] != bool(getattr(self.teacher, "is_offline_mock", False)):
            raise ValueError("Teacher mock/live scope differs")
        self.checkpoints = Checkpoints(self.artifacts / "checkpoints", self.seal["binding"])

    def verify_binding(self):
        if self.config != self.seal["config"] or self.data.manifest["allowlist"] != self.seal["allowlist"] or \
                digest(self.data.manifest) != self.seal["binding"]["source_manifest_hash"]:
            raise ValueError("Sealed input/config/state binding differs")
        if science_files(self.root) != self.seal["protected_files"]:
            # A completed generation stage may be restored after a narrowly
            # verified adapter prompt correction. The receipt binds all current
            # files and every preserved payload/output; it cannot authorize calls.
            from .readiness import validate
            validate(self.root, self.seal['binding'])
        if "processing_repair" in self.seal:
            original = json.loads((self.artifacts / "seal.json").read_text())
            repair = self.seal["processing_repair"]
            if digest(original) != repair["prior_seal_hash"] or repair["generation_binding"] != original["binding"] or \
                    generation_contract((self.root / "legal_skill_guard/rr/engine.py").read_text()) != repair["generation_contract"]:
                raise ValueError("Generation compatibility proof changed")

    def _call(self, *, call_id: str, source: dict, purpose: str, prompt: list[dict], thinking: bool, schema: dict | None = None) -> dict:
        self.verify_binding()
        client = self.executor
        repair = self.seal.get("wire_repair")
        if repair and purpose == "thinking_probe":
            if call_id not in repair["unaffected_calls"]:
                raise ValueError("Only exact verified unaffected generation records may be reused")
            old = repair["generation_binding"]
            ledger = BudgetLedger(self.root / self.config["ledger_path"], sources=self.seal["allowlist"],
                                  code_hash=old["code_hash"], config_hash=old["config_hash"])
            with ledger.transaction() as db:
                row = db.execute("SELECT status,request_hash FROM calls WHERE id=?", (call_id,)).fetchone()
            if row != ("completed", repair["unaffected_calls"][call_id]["request_hash"]):
                raise ValueError("Unchanged response is missing; do not regenerate it")
            if self.seal["offline_mock"]:
                client = self.executor
                original_ledger = client.ledger
                client.ledger = ledger
                try:
                    return client.generate(call_id, source=source["key"], purpose=purpose, messages=prompt,
                                           thinking=thinking, schema=schema or proposal_schema(source["dataset"], source=source))
                finally:
                    client.ledger = original_ledger
            client = ExecutorClient(ledger, self.artifacts, self.config["executor"])
        revision = self.seal.get('study_preflight_revision')
        if revision:
            payload = client.payload(messages=prompt, thinking=thinking, schema=schema)
            self.ledger.register_study_request(call_id, revision=revision, source=source['key'],
                request={'thinking': thinking, 'payload': payload}, step=int(call_id.rsplit(':', 1)[1]))
        return client.generate(call_id, source=source["key"], purpose=purpose, messages=prompt,
                               thinking=thinking, schema=schema or proposal_schema(source["dataset"], source=source))

    def thinking(self) -> dict:
        if "processing_continuation" in self.seal:
            selection = json.loads((self.artifacts / self.seal.get("wire_repair", {}).get("selection_file", "thinking_selection.json")).read_text())
            if selection["binding"] != self.seal["processing_continuation"]["thinking_binding"]:
                raise ValueError("Preserved thinking evidence binding differs")
            return selection
        records = []
        for source_id in self.data.order:
            source = self.data.public(source_id)
            for thinking in (True, False):
                repair = self.seal.get("wire_repair", self.seal.get("processing_repair", {}))
                directory = repair.get("thinking_directory", "thinking")
                path = self.artifacts / directory / f"{digest((source_id, thinking))}.json"
                if path.exists():
                    record = json.loads(path.read_text())
                else:
                    targeted = "wire_repair" in self.seal and source["dataset"] == "OpenExempt"
                    wire = self._call(call_id=f"{'native_contract_fix' if targeted else 'thinking'}:{source_id}:{thinking}", source=source,
                                      purpose="preflight_bug_retry" if targeted else "thinking_probe", prompt=messages(source), thinking=thinking)
                    analysis = analyze(source, wire["content"])
                    score = score_source(source, analysis, self.data.grade(source_id), native_oe=not self.seal["offline_mock"])
                    record = {"source": source_id, "dataset": source["dataset"], "thinking": thinking,
                              "analysis": analysis, "score": score, "structural_pass": analysis["structural_pass"],
                              "task_correct": score["task_correct"], "usage": wire["usage"],
                              "elapsed_seconds": wire["elapsed_seconds"],
                              "reasoning_present": bool(wire.get("reasoning_content")),
                              "template_profile_observed": True,
                              "actual_backend_effect_verified": False,
                              "wire_request_hash": wire["request_hash"], "binding": self.seal["binding"],
                              "generation_binding": self.seal["wire_repair"]["generation_binding"]
                              if "wire_repair" in self.seal and not targeted else
                              self.seal.get("processing_repair", {}).get("generation_binding", self.seal["binding"]),
                              "offline_mock": self.seal["offline_mock"]}
                    # A tokenizer hash by itself does not prove generation
                    # behavior. The full paired selector checks reasoning too.
                    if not self.seal["offline_mock"]:
                        environment = json.loads((self.root / "reports/rr_v2_evidence/environment_no_generation.json").read_text())
                        record["template_profile_observed"] = environment["tokenizer_profiles"][str(thinking).lower()]["template_profile_observed"]
                    immutable_json(path, record)
                if record["binding"] != self.seal["binding"] or record["source"] != source_id:
                    raise ValueError("Thinking record binding changed")
                records.append(record)
                print(json.dumps({"stage": "thinking", "records": len(records), "source": source_id,
                                  "profile": thinking, "structure": record["structural_pass"],
                                  "correct": record["task_correct"]}), flush=True)
        selection = select_thinking(records, self.data.order)
        selection.update({"offline_mock": self.seal["offline_mock"], "binding": self.seal["binding"],
                          "records_hash": digest(records)})
        immutable_json(self.artifacts / self.seal.get("wire_repair", {}).get("selection_file", "thinking_selection.json"), selection)
        return selection

    def _snapshot(self, records: list[dict], library: SkillLibrary, teacher_record: dict | None) -> str:
        state = {"stage": "preflight", "complete_sources": [r["source"] for r in records],
                 "source_record_hashes": [digest(r) for r in records], "library": library.export(),
                 "teacher_record": teacher_record, "pending_partial_batch_sources": [r["source"] for r in records][16:],
                 "offline_mock": self.seal["offline_mock"], "formal_B8": False}
        key = self.checkpoints.save(state, stage="preflight", ledger_export=self.ledger.export())
        restored = self.checkpoints.load(key)
        if restored["state"] != state:
            raise ValueError("Checkpoint roundtrip differs")
        atomic_json(self.artifacts / "state.json", {"checkpoint": key, "complete_sources": state["complete_sources"],
                                                   "restore_verified": True})
        return key

    def _summarize(self, records: list[dict], library: SkillLibrary) -> dict:
        path = self.artifacts / "teacher_batch1.json"
        if path.exists():
            cached = json.loads(path.read_text())
            if cached["source_ids"] != self.data.order[:16] or cached["reuse_requires_matching_binding"] != self.seal["binding"]:
                raise ValueError("Cached teacher batch binding differs")
            return cached
        common = [{"source": r["source"], "dataset": r["dataset"],
                   "program_status": r["analysis"]["program_status"],
                   "certificate_status": r["analysis"]["certificate_status"],
                   "learning_status": r["learning"]["status"],
                   "refinement": r["learning"].get("refinement"),
                   "pattern": r["learning"].get("learned_pattern")} for r in records]
        pattern_schema = {"type": "object", "additionalProperties": False,
                          "required": ["fields", "graphs", "basis", "universal_semantic_equivalence_claim"],
                          "properties": {"fields": {"type": "array", "items": {"type": "string"}},
                                         "graphs": {"type": "array", "items": {"type": "string"}},
                                         "basis": {"type": "string"},
                                         "universal_semantic_equivalence_claim": {"type": "boolean"}}}
        schema = {"type": "object", "additionalProperties": False, "required": ["patterns", "notes"],
                  "properties": {"patterns": {"type": "array", "items": pattern_schema}, "notes": {"type": "string"}}}
        response = self.teacher.summarize(
            self.seal.get('study_preflight_revision', 'pilot') + '_teacher_batch1', source_ids=self.data.order[:16],
            system_prompt="Summarize observed source-grounded interface patterns only. Do not use tools. Never invent verified fields, laws or labels. Do not route by source IDs. Return parameterized patterns; encode each connector graph as a JSON string. Keep unverified proposals explicitly unverified.",
            user_prompt=json.dumps({"common_first_16_training_records": common,
                                    "current_parameterized_library": library.export()}, ensure_ascii=False, sort_keys=True),
            output_schema=schema)
        accepted, pending = [], []
        known = {item["pattern_hash"]: item["pattern"] for item in library.patterns}
        for item in response["value"]["patterns"]:
            try:
                item = {**item, "graphs": [json.loads(g) for g in item["graphs"]]}
                normalized = SkillLibrary()
                key = normalized.add(item, source="teacher_common_batch")
                if key in known:
                    accepted.append(key)
                else:
                    pending.append({"proposal": item, "reason": "not_verified_by_shared_training_material"})
            except (ValueError, TypeError, KeyError) as exc:
                pending.append({"proposal": item, "reason": str(exc)})
        result = {"response": response, "accepted_pattern_hashes": accepted, "pending_proposals": pending,
                  "source_ids": self.data.order[:16], "batch_record_accepted": True,
                  "reuse_requires_matching_binding": self.seal["binding"], "offline_mock": self.seal["offline_mock"]}
        immutable_json(path, result)
        return result

    def pilot(self) -> dict:
        selection = json.loads((self.artifacts / self.seal.get("wire_repair", {}).get("selection_file", "thinking_selection.json")).read_text())
        expected_thinking = self.seal.get("processing_continuation", {}).get("thinking_binding", self.seal["binding"])
        if selection["engineering_block"] or selection["binding"] != expected_thinking:
            raise ValueError("Thinking selection is blocked or belongs to another sealed run")
        pointer = self.artifacts / "state.json"
        if pointer.exists():
            prior = self.checkpoints.load(json.loads(pointer.read_text())["checkpoint"])["state"]
            for source_id, expected in zip(prior["complete_sources"], prior["source_record_hashes"]):
                path = self.artifacts / "pilot_sources" / f"{digest(source_id)}.json"
                if digest(json.loads(path.read_text())) != expected:
                    raise ValueError("Saved pilot source record was altered")
        complete_path=self.artifacts/'pilot_completion.json'
        if complete_path.exists():
            complete=json.loads(complete_path.read_text())
            if not pointer.exists() or prior['complete_sources']!=self.data.order or \
                    complete['binding']!=self.seal['binding'] or complete['sources']!=20 or \
                    digest(SkillLibrary.restore(self.artifacts/'partial_library.frozen.json').export())!=complete['library_sha256'] or \
                    digest(json.loads((self.artifacts/'teacher_batch1.json').read_text()))!=digest(prior['teacher_record']):
                raise ValueError('Completed pilot snapshot differs')
            # Return the immutable budget snapshot; later repair charges remain
            # visible in the same live ledger and never rewrite this completion.
            return complete
        records, library, teacher_record = [], SkillLibrary(), None
        for source_id in self.data.order:
            source = self.data.public(source_id)
            path = self.artifacts / "pilot_sources" / f"{digest(source_id)}.json"
            if path.exists():
                record = json.loads(path.read_text())
                if record["binding"] != self.seal["binding"] or record["source"] != source_id or \
                        record["input_hash"] != source["content_hash"] or record["offline_mock"] != self.seal["offline_mock"]:
                    raise ValueError("Pilot source binding differs")
            else:
                grade = self.data.grade(source_id)
                record = ingest_source(source=source, grade=grade, library=library,
                    thinking=self.config['executor']['enable_thinking'], call=self._call, learner=self.learner,
                    ledger=self.ledger, artifacts=self.artifacts, binding=self.seal["binding"],
                    purpose="preflight_bug_retry" if self.seal.get('study_preflight_revision') else "pilot_ingestion",
                    id_prefix=self.seal.get('study_preflight_revision', "pilot"), offline_mock=self.seal["offline_mock"],
                    oracle_artifacts=self.oracle_artifacts,
                    tokenize=(lambda prompt: self.executor.tokenize(prompt, thinking=self.config['executor']['enable_thinking']))
                             if not self.seal['offline_mock'] else None,
                    request_config=self.config['executor'])
                if "processing_continuation" in self.seal:
                    record["generation_binding"] = self.seal["processing_continuation"]["generation_binding"]
                immutable_json(path, record)
            pattern = record["learning"].get("learned_pattern")
            if pattern is not None:
                library.add(pattern, source=source_id)
            records.append(record)
            if len(records) == 16:
                teacher_record = self._summarize(records, library)
                first_path = self.artifacts / "B1_preflight_partial.json"
                if first_path.exists():
                    first = json.loads(first_path.read_text())["checkpoint"]
                    saved = self.checkpoints.load(first)["state"]
                    if saved["source_record_hashes"] != [digest(r) for r in records] or saved["library"] != library.export() or saved["teacher_record"] != teacher_record:
                        raise ValueError("Saved first-batch checkpoint differs")
                else:
                    first = self._snapshot(records, library, teacher_record)
                immutable_json(self.artifacts / "B1_preflight_partial.json", {"checkpoint": first,
                                "sources": 16, "teacher_batch_record": digest(teacher_record),
                                "stage": "preflight", "formal_evaluation_run": False})
            self._snapshot(records, library, teacher_record)
            print(json.dumps({"stage": "pilot", "sources": len(records), "dataset": source["dataset"],
                              "source": source_id, "learning": record["learning"]["status"],
                              "oracle_views": len(record["learning"]["oracle_views"]),
                              "patterns": len(library.patterns)}), flush=True)
        for record in records:
            grade = self.data.grade(record["source"])
            labels = grade["targets"] if record["dataset"] == "OpenExempt" else {"answer": grade["answer"]}
            proposals = [{"decoded_proposal": c["analysis"].get("proposal"),
                          "raw_content": c["raw_content"], "parse_status": c["analysis"]["program_status"],
                          "wire_request_hash": c["request_hash"]} for c in record["calls"]]
            material = SharedMaterial(record["source"], proposals, labels,
                                      record["learning"]["oracle_views"],
                                      {"batch_record": digest(teacher_record),
                                       "summary": teacher_record["response"]["value"]} if teacher_record else {},
                                      [record["learning"]["learned_pattern"]] if record["learning"].get("learned_pattern") else [])
            projections = {arm: project_material(material, arm) for arm in ("M00", "M10", "M01", "M11", "MA", "MB")}
            immutable_json(self.artifacts / "arm_shared_material" / f"{digest(record['source'])}.json", projections)
        frozen = library.freeze(self.artifacts / "partial_library.frozen.json")
        restored = SkillLibrary.restore(self.artifacts / "partial_library.frozen.json")
        if restored.export() != library.export():
            raise ValueError("Frozen partial library restore failed")
        result = {"sources": len(records), "patterns": len(library.patterns),
                  "library_sha256": frozen["sha256"], "restore_verified": True,
                  "teacher_batch_record_accepted": bool(teacher_record and teacher_record["batch_record_accepted"]),
                  "pending_partial_batch_sources": self.data.order[16:],
                  "ledger": self.ledger.export(), "stage": "preflight", "formal_B8": False,
                  "offline_mock": self.seal["offline_mock"], "binding": self.seal["binding"]}
        immutable_json(self.artifacts / "pilot_completion.json", result)
        return result
