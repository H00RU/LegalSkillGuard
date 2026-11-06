"""Future formal hooks over the original ledger; all current launch gates are off."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from types import SimpleNamespace

from .checkpoint import immutable_json
from .client import ExecutorClient, TeacherClient
from .controls import ARMS, SharedMaterial, project_material
from .coverage import digest
from .engine import proposal_schema
from .example_synthesis import fit_shared_examples
from .learning import SkillLibrary
from .ledger import BUCKETS, BudgetError, BudgetLedger
from .preflight import (
    Preflight,
    active_seal_path,
    atomic_json,
    ingest_source,
    science_files,
    scientific_code_binding,
    score_source,
)
from .readiness import RECEIPT as READINESS_RECEIPT
from .readiness import validate as validate_readiness
from .routing import route_prediction
from .scoring import aggregate
from .source_learning import learn_source


def diagnostic_plan(manifest: dict) -> list[dict]:
    """Fixed parent IDs and comparators; no labels or prediction-based selection."""
    return [{"source": row["key"], "dataset": dataset,
             "comparator": "MA" if i < 4 else "MB", "max_variants": 2}
            for dataset in ("OpenExempt", "RuleArena_Airline", "SARA_v2_Binary", "ProofWriter_OWA_depth5")
            for i, row in enumerate(manifest["split"]["datasets"][dataset]["test"][:8])]


class FormalLedger(BudgetLedger):
    """Uses the *same* SQLite tables and original 6000/20 allocation."""
    def __init__(self, path, *, sources, code_hash, config_hash, protocol, manifest, partition,
                 origin_binding=None):
        if not protocol["run_enabled"] or partition == "test" and not protocol["execution_request"]["frozen_test_enabled"]:
            raise BudgetError("Formal training/evaluation is not authorized")
        self.protocol, self.manifest, self.partition = protocol, manifest, partition
        self.train_order = manifest["formal_train_order"]
        self.allowed_formal = {r["key"] for d in manifest["split"]["datasets"].values() for r in d[partition]}
        origin = origin_binding or {"code_hash": code_hash, "config_hash": config_hash}
        super().__init__(path, sources=sources, code_hash=origin["code_hash"], config_hash=origin["config_hash"])
        self.execution_binding = {"code_hash": code_hash, "config_hash": config_hash}

    def _source(self, source):
        if source not in self.allowed_formal:
            raise BudgetError("Source outside authorized formal partition")

    def reserve_oracle(self, source, view_hash):
        if self.partition != "train" or source.startswith("ContractNLI:"):
            raise BudgetError("No oracle or reference feedback during evaluation")
        return super().reserve_oracle(source, view_hash)

    def reserve(self, call_id, *, role, purpose, source, request):
        self._source(source)
        mapping = {"formal_train": "full_build_including_pilot", "formal_dev": "dev_six_arms",
                   "formal_test": "frozen_test_six_arms", "formal_B1": "B1_test_M11",
                   "formal_diagnostic": "diagnostics", "formal_native_empty": "native_empty",
                   "formal_teacher_summary": "teacher"}
        if purpose not in mapping or (role == "teacher") != (purpose == "formal_teacher_summary"):
            raise BudgetError("Unauthorized formal purpose/role")
        expected_partition = "train" if purpose in {"formal_train", "formal_teacher_summary"} else "dev" if purpose == "formal_dev" else "test"
        if self.partition != expected_partition:
            raise BudgetError("Formal purpose belongs to another data partition")
        if (purpose == "formal_train" or role == "teacher") and self.partition != "train":
            raise BudgetError("Training role cannot read evaluation sources")
        bucket = mapping[purpose]
        request_hash = digest({"request": request, "spec": self.spec,
                               "execution_binding": self.execution_binding})
        with self.transaction() as db:
            row = db.execute("SELECT role,purpose,source,request_hash,status,result FROM calls WHERE id=?", (call_id,)).fetchone()
            if row:
                if row[:4] != (role, purpose, source, request_hash):
                    raise BudgetError("Formal cached record binding differs")
                if row[4] != "completed":
                    raise BudgetError("Failed/reserved formal call remains charged; no implicit redispatch")
                return {"dispatch": False, "result": json.loads(row[5])}
            total = db.execute("SELECT COUNT(*) FROM calls WHERE role=?", (role,)).fetchone()[0]
            if total >= (6000 if role == "executor" else 20):
                raise BudgetError("Original study total exhausted")
            used = db.execute("SELECT COUNT(*) FROM calls WHERE bucket=?", (bucket,)).fetchone()[0]
            if used >= (20 if role == "teacher" else BUCKETS[bucket]):
                raise BudgetError("Original allocation exhausted")
            if purpose == "formal_train":
                consumed = db.execute("SELECT COUNT(*) FROM calls WHERE source=? AND bucket='full_build_including_pilot'", (source,)).fetchone()[0]
                if consumed >= 2:
                    raise BudgetError("Training source already spent its two calls, including preflight")
            if purpose in {"formal_dev", "formal_test", "formal_B1", "formal_diagnostic", "formal_native_empty"}:
                prefix, step = call_id.rsplit(":", 1)
                limit = 1 if purpose == "formal_native_empty" else 3
                if step not in {str(i) for i in range(limit)}:
                    raise BudgetError("Whole prediction call index exceeds its shared limit")
                used_prediction = db.execute("SELECT COUNT(*) FROM calls WHERE substr(id,1,?)=?",
                    (len(prefix) + 1, prefix + ":")).fetchone()[0]
                if used_prediction >= limit:
                    raise BudgetError("Whole prediction call cap includes failed requests")
            if role == "teacher":
                batch = request.get("source_ids", [])
                if len(batch) != 16 or batch not in [self.train_order[i:i + 16] for i in range(0, 128, 16)]:
                    raise BudgetError("Teacher batch does not match the fixed build order")
                anchors = tuple(batch)
                count = db.execute("SELECT COUNT(*) FROM calls WHERE role='teacher' AND source IN (" + ",".join("?" for _ in anchors) + ")", anchors).fetchone()[0]
                if count >= 2:
                    raise BudgetError("Teacher batch two-call limit includes preflight and failures")
            db.execute("INSERT INTO calls VALUES (?,?,?,?,?,?,?,?,NULL)",
                       (call_id, role, purpose, bucket, source, request_hash, "reserved", time.time()))
        return {"dispatch": True, "request_hash": request_hash}


class FormalExecutor(ExecutorClient):
    def validate_scope(self, source, purpose, thinking):
        self.ledger._source(source)
        if thinking is not self.config['enable_thinking']:
            raise BudgetError('Executor thinking differs from explicit user-selected OFF profile')
        if purpose not in {"formal_train", "formal_dev", "formal_test", "formal_B1", "formal_diagnostic", "formal_native_empty"} or type(thinking) is not bool:
            raise BudgetError("Invalid authorized formal executor purpose")


class FormalTeacher(TeacherClient):
    summary_purpose = "formal_teacher_summary"


def dry_run(root: Path) -> dict:
    cfg = json.loads((root / "configs/rr_v2_formal.json").read_text())
    manifest = json.loads((root / "reports/rr_v2_evidence/data_manifest.json").read_text())
    return {"executed": False, "model_calls": 0, "train_sources": 128, "batches": 8,
            "sources_per_batch": 16, "one_shared_build": True,
            "fixed_train_order_hash": digest(manifest["formal_train_order"]),
            "B1_after_sources": 16, "B8_after_sources": 128,
            "run_enabled": cfg["run_enabled"], "frozen_test_enabled": cfg["frozen_test_enabled"],
            "auto_evaluate_after_training": False, "original_ledger_reused": True,
            "diagnostics": diagnostic_plan(manifest), "diagnostic_predictions_max": 128,
            "diagnostic_executor_calls_max": 384}


class FormalRun:
    def __init__(self, root: Path, *, partition: str):
        self.root = Path(root)
        self.cfg = json.loads((root / "configs/rr_v2_formal.json").read_text())
        self.protocol = json.loads((root / "reports/legalskillguard_rule_reasoning_protocol_v2.json").read_text())
        if not self.cfg["run_enabled"] or not self.protocol["run_enabled"]:
            raise BudgetError("Formal run stays disabled; this goal must stop after bounded preflight")
        if partition == "train" and (not self.cfg["full_build_enabled"] or not self.protocol["execution_request"]["full_build_enabled"]):
            raise BudgetError("128-source build is disabled")
        if partition == "test" and (not self.cfg["frozen_test_enabled"] or not self.protocol["execution_request"]["frozen_test_enabled"]):
            raise BudgetError("Frozen testing remains disabled")
        self.partition = partition
        config = json.loads((root / "configs/rr_v2_preflight.json").read_text())
        self.config = config
        self.artifacts = root / self.cfg["artifact_directory"]
        self.manifest = json.loads((root / config["source_manifest"]).read_text())
        code = science_files(root)
        semantic = {"executor": config["executor"], "teacher": config["teacher"],
                    "protocol_methods": self.protocol["methods"], "A_limits": self.protocol["A_limits"],
                    "B_limits": self.protocol["B_limits"], "training": self.protocol["training"],
                    "thinking": self.protocol["thinking"]}
        self.binding = {"code_hash": scientific_code_binding(code), "config_hash": digest(semantic),
                        "data_hash": self.manifest["data_hash"], "source_manifest_hash": digest(self.manifest)}
        self.readiness = validate_readiness(root)
        self.preflight_binding = self.readiness['preflight_binding']
        self.pref = root / self.readiness['preflight_artifact_directory']
        self.ledger = FormalLedger(root / config["ledger_path"], sources=self.manifest["allowlist"],
            code_hash=self.binding["code_hash"], config_hash=self.binding["config_hash"],
            protocol=self.protocol, manifest=self.manifest, partition=partition,
            origin_binding=self.readiness['ledger_origin_binding'])
        self.executor = FormalExecutor(self.ledger, self.artifacts, config["executor"])
        self.teacher = FormalTeacher(self.ledger, self.artifacts, config["teacher"])
        self.teacher.adapter.executable = self.readiness["teacher_transport"]["executable"]
        self.order = self.manifest["formal_train_order"]

    def packet(self, kind: str, partition: str):
        path = self.root / "data/packets/rr_v2" / (f"public_{partition}.json" if kind == "public" else f"grading_only/{partition}.json")
        if hashlib.sha256(path.read_bytes()).hexdigest() != self.manifest["packet_sha256"][f"{kind if kind == 'public' else 'grading'}_{partition}"]:
            raise ValueError("Frozen dataset packet differs")
        return json.loads(path.read_text())["sources"]

    def _call(self, *, call_id, source, purpose, prompt, thinking, schema):
        return self.executor.generate(call_id, source=source["key"], purpose=purpose,
                                      messages=prompt, thinking=thinking, schema=schema)

    def train(self):
        if self.partition != "train":
            raise BudgetError("Wrong formal partition")
        public = {s["key"]: s for s in self.packet("public", "train")}
        grading = self.packet("grading", "train")
        library = SkillLibrary(stage="formal_train")
        completed = []
        for source_id in self.order:
            source = public[source_id]
            prior = self.pref / "pilot_sources" / f"{digest(source_id)}.json"
            path = self.artifacts / "sources" / f"{digest(source_id)}.json"
            record_path = path if path.exists() else prior
            if record_path.exists():
                record = json.loads(record_path.read_text())
                expected_binding = self.preflight_binding if record_path == prior else self.binding
                if record["binding"] != expected_binding or record["input_hash"] != source["content_hash"] or record["offline_mock"]:
                    raise ValueError("Training reuse input/code/config/state mismatch")
            else:
                record = ingest_source(source=source, grade=grading[source_id], library=library,
                    thinking=self.executor.config["enable_thinking"], call=self._call, learner=learn_source,
                    ledger=self.ledger, artifacts=self.artifacts, binding=self.binding,
                    purpose="formal_train", id_prefix="formal", offline_mock=False,
                    tokenize=lambda prompt: self.executor.tokenize(prompt, thinking=self.executor.config['enable_thinking']),
                    request_config=self.config['executor'])
                immutable_json(path, record)
            pattern = record["learning"].get("learned_pattern")
            if pattern:
                library.add(pattern, source=source_id)
            completed.append(record)
            if len(completed) % 16 == 0:
                batch = len(completed) // 16
                if batch == 1:
                    teacher_record = json.loads((self.pref / "teacher_batch1.json").read_text())
                    if teacher_record["source_ids"] != self.order[:16] or teacher_record["reuse_requires_matching_binding"] != self.preflight_binding:
                        raise ValueError("Preflight teacher batch cannot be reused")
                else:
                    teacher = self.teacher
                    class BatchTeacher:
                        def summarize(inner, call_id, **kwargs):
                            return teacher.summarize(f"formal_teacher_batch{batch}", **kwargs)
                    proxy = SimpleNamespace(artifacts=self.artifacts / "batches" / f"B{batch}",
                        data=SimpleNamespace(order=self.order[(batch - 1) * 16:batch * 16]),
                        teacher=BatchTeacher(), seal={"binding": self.binding, "offline_mock": False})
                    teacher_record = Preflight._summarize(proxy, completed[-16:], library)
                snapshot = {"stage": f"B{batch}", "binding": self.binding,
                            "completed_sources": [r["source"] for r in completed],
                            "source_record_hashes": [digest(r) for r in completed],
                            "library": library.export(), "teacher_batch_record": teacher_record,
                            "ledger": self.ledger.export()}
                snapshot_path = self.artifacts / "batches" / f"B{batch}.json"
                if snapshot_path.exists():
                    saved = json.loads(snapshot_path.read_text())
                    if {k: v for k, v in saved.items() if k != "ledger"} != {k: v for k, v in snapshot.items() if k != "ledger"}:
                        raise ValueError("Saved formal batch checkpoint differs")
                else:
                    immutable_json(snapshot_path, snapshot)
                for record in completed[-16:]:
                    grade = grading[record["source"]]
                    labels = grade["targets"] if record["dataset"] == "OpenExempt" else {"answer": grade["answer"]}
                    proposals = [{"decoded_proposal": c["analysis"].get("proposal"),
                                  "raw_content": c["raw_content"], "parse_status": c["analysis"]["program_status"],
                                  "wire_request_hash": c["request_hash"]} for c in record["calls"]]
                    material = SharedMaterial(record["source"], proposals, labels,
                        record["learning"]["oracle_views"],
                        {"batch_record": digest(teacher_record), "summary": teacher_record["response"]["value"]},
                        [record["learning"]["learned_pattern"]] if record["learning"].get("learned_pattern") else [])
                    immutable_json(self.artifacts / "arm_shared_material" / f"{digest(record['source'])}.json",
                                   {arm: project_material(material, arm) for arm in ARMS})
                if batch in {1, 8}:
                    frozen = SkillLibrary(library.patterns, stage=f"formal_B{batch}")
                    frozen.freeze(self.artifacts / f"B{batch}.frozen.json")
                    # Same original labels and paid proposals as B; no extra
                    # extraction or oracle calls for this ordinary-synthesis
                    # control. Concrete examples never enter its frozen state.
                    example_model = fit_shared_examples(public, completed, grading)
                    immutable_json(self.artifacts / f"B{batch}.MB.frozen.json", example_model)
            atomic_json(self.artifacts / "state.json", {"complete_sources": len(completed),
                        "source_record_hashes": [digest(r) for r in completed], "binding": self.binding})
        return {"training_complete": True, "sources": len(completed), "batches": 8,
                "auto_evaluate_after_training": False, "ledger": self.ledger.export()}

    def evaluate(self, checkpoint="B8"):
        if checkpoint not in {"B1", "B8"} or checkpoint == "B1" and self.partition != "test":
            raise BudgetError("B1 is the single additional frozen M11 test only")
        library_path = self.artifacts / f"{checkpoint}.frozen.json"
        snapshot = json.loads((self.artifacts / "batches/B8.json").read_text())
        if snapshot["binding"] != self.binding or len(snapshot["completed_sources"]) != 128:
            raise BudgetError("Evaluation requires all 128 sources and frozen B8 configuration")
        library = SkillLibrary.restore(library_path).export()
        example_model = json.loads((self.artifacts / f"{checkpoint}.MB.frozen.json").read_text())
        public = self.packet("public", self.partition)
        before = digest(library)
        predictions = {}
        for arm in (["M11"] if checkpoint == "B1" else ["M00", "M10", "M01", "M11", "MA", "MB"]):
            predictions[arm] = {}
            for source in public:
                path = self.artifacts / "predictions" / self.partition / checkpoint / arm / f"{digest(source['key'])}.json"
                if path.exists():
                    result = json.loads(path.read_text())
                else:
                    owner = self
                    def generate(prompt, *, purpose, step, arm, schema):
                        return owner.executor.generate(f"{owner.partition}:{checkpoint}:{arm}:{source['key']}:{step}",
                            source=source["key"], purpose="formal_B1" if checkpoint == "B1" else f"formal_{owner.partition}", messages=prompt,
                            thinking=owner.executor.config["enable_thinking"], schema=schema)
                    try:
                        result = route_prediction(source, arm=arm, library=library, generate=generate,
                                                  protocol=self.protocol, partition=self.partition,
                                                  example_model=example_model if arm == "MB" else None,
                                                  tokenize=lambda prompt: self.executor.tokenize(prompt, thinking=self.executor.config['enable_thinking']),
                                                  request_config=self.config['executor'], thinking=self.executor.config['enable_thinking'])
                    except Exception as exc:
                        result = {"arm": arm, "result": {"answer": None, "certificate_status": "budget_exhausted"},
                                  "failure": repr(exc), "source_failure_retained_in_denominator": True}
                    result.update({"binding": self.binding, "input_hash": source["content_hash"]})
                    immutable_json(path, result)
                if result["binding"] != self.binding or result["input_hash"] != source["content_hash"]:
                    raise ValueError("Evaluation prediction binding changed")
                predictions[arm][source["key"]] = result
        # Grading is opened only after every prediction is committed. No labels
        # or intermediate references enter the callback, library or teacher.
        grading = self.packet("grading", self.partition)
        results = {}
        for arm, rows in predictions.items():
            records = []
            for source in public:
                prediction = rows[source["key"]]["result"]
                score = score_source(source, prediction, grading[source["key"]])
                for view, value in score["views"].items():
                    records.append({"dataset": source["dataset"], "source": source["key"], "view": view,
                                    "correct": value["correct"], "answered": prediction["answer"] is not None,
                                    "certificate_status": prediction["certificate_status"]})
            expected = {(s["dataset"], s["key"], v) for s in public for v in (["EC", "EV"] if s["dataset"] == "OpenExempt" else ["main"])}
            results[arm] = aggregate(records, expected_outputs=expected)
        if digest(library) != before:
            raise ValueError("Frozen library changed during inference")
        immutable_json(self.artifacts / f"{self.partition}_{checkpoint}_scores.json", results)
        return results

    def native_empty(self):
        if self.partition != "test" or not (self.artifacts / "batches/B8.json").exists():
            raise BudgetError("Native empty reference is a separate post-B8 frozen test")
        snapshot = json.loads((self.artifacts / "batches/B8.json").read_text())
        if snapshot["binding"] != self.binding or len(snapshot["completed_sources"]) != 128:
            raise BudgetError("Native reference requires the complete frozen B8 build")
        public = self.packet("public", "test")
        rows = []
        from .engine import wire_messages as messages
        for source in public:
            path = self.artifacts / "native_empty" / f"{digest(source['key'])}.json"
            if path.exists():
                record = json.loads(path.read_text())
            else:
                prompt = messages(source)
                prompt[0]["content"] = "Answer the public task directly. You have no learned library or execution tools. Return the native answer in answer, program={kind:unsupported,body:{}}, empty compiled_units, unsupported_units and interfaces."
                wire = self.executor.generate(f"native_empty:{source['key']}:0", source=source["key"],
                    purpose="formal_native_empty", messages=prompt, thinking=self.executor.config["enable_thinking"], schema=proposal_schema(source["dataset"], source=source))
                try:
                    answer = json.loads(wire["content"])["answer"]
                except (ValueError, KeyError, TypeError):
                    answer = None
                record = {"source": source["key"], "answer": answer,
                          "certificate_status": "unsupported_no_certificate", "wire": wire,
                          "binding": self.binding, "input_hash": source["content_hash"], "tools": []}
                immutable_json(path, record)
            if record["binding"] != self.binding or record["input_hash"] != source["content_hash"]:
                raise ValueError("Native reference binding differs")
            rows.append(record)
        grading = self.packet("grading", "test")
        scores = {r["source"]: score_source(s, r, grading[r["source"]]) for s, r in zip(public, rows)}
        immutable_json(self.artifacts / "native_empty_scores.json", scores)
        return scores

    def diagnostics(self, public_packet: Path, grading_packet: Path):
        """Future frozen diagnostics over explicitly committed, source-local views.

        The packet is a public construction artifact, with 0..2 validated views
        per registered parent. Unsupported constructions stay in the skipped
        record. Its private grading partner is opened only after predictions.
        No training oracle is available to this entry.
        """
        if self.partition != "test":
            raise BudgetError("Diagnostics require the frozen post-B8 test gate")
        snapshot = json.loads((self.artifacts / "batches/B8.json").read_text())
        if snapshot["binding"] != self.binding or len(snapshot["completed_sources"]) != 128:
            raise BudgetError("Diagnostics require the full frozen build")
        packet = json.loads(Path(public_packet).read_text())
        if set(packet) != {"binding", "sources", "grading_sha256"} or packet["binding"] != self.binding:
            raise ValueError("Diagnostic construction binding differs")
        registered = diagnostic_plan(self.manifest)
        if [r["source"] for r in packet["sources"]] != [r["source"] for r in registered]:
            raise ValueError("Diagnostics must retain all 32 preregistered parents, including skipped ones")
        parents = {s["key"]: s for s in self.packet("public", "test")}
        library = SkillLibrary.restore(self.artifacts / "B8.frozen.json").export()
        example_model = json.loads((self.artifacts / "B8.MB.frozen.json").read_text())
        before = digest(library)
        immutable_json(self.artifacts / "diagnostics/public_packet.json", packet)
        predictions = []
        for registration, item in zip(registered, packet["sources"]):
            if set(item) != {"source", "variants", "skipped_reason"} or len(item["variants"]) > 2:
                raise ValueError("Diagnostic parent schema or two-view budget differs")
            if not item["variants"] and not item["skipped_reason"]:
                raise ValueError("Unsupported diagnostic domain needs an explicit retained reason")
            parent = parents[item["source"]]
            for index, view in enumerate(item["variants"]):
                if set(view) != {"public", "construction_receipt"} or not view["construction_receipt"].get("rules_unchanged_verified"):
                    raise ValueError("A diagnostic fact view needs an auditable source-local construction")
                public = view["public"]
                if set(public) != set(parent["public"]):
                    raise ValueError("Diagnostic public schema differs from its parent")
                if "rules" in public and public["rules"] != parent["public"]["rules"]:
                    raise ValueError("Diagnostics cannot edit the benchmark rules")
                source = {**parent, "public": public, "content_hash": digest(public)}
                for arm in ("M11", registration["comparator"]):
                    path = self.artifacts / "diagnostics/predictions" / arm / f"{digest((parent['key'], index))}.json"
                    if path.exists():
                        result = json.loads(path.read_text())
                    else:
                        def generate(prompt, *, purpose, step, arm, schema):
                            return self.executor.generate(f"diagnostic:{index}:{arm}:{parent['key']}:{step}",
                                source=parent["key"], purpose="formal_diagnostic", messages=prompt,
                                thinking=self.executor.config["enable_thinking"], schema=schema)
                        try:
                            routed = route_prediction(source, arm=arm, library=library, generate=generate,
                                                      protocol=self.protocol, partition="test",
                                                      example_model=example_model if arm == "MB" else None,
                                                      tokenize=lambda prompt: self.executor.tokenize(prompt, thinking=self.executor.config['enable_thinking']),
                                                      request_config=self.config['executor'], thinking=self.executor.config['enable_thinking'])
                        except Exception as exc:
                            routed = {"result": {"answer": None, "certificate_status": "translation_unresolved"},
                                      "failure": repr(exc), "source_failure_retained_in_denominator": True}
                        result = {"source": parent["key"], "dataset": parent["dataset"], "variant": index,
                                  "arm": arm, "routed": routed, "input_hash": source["content_hash"],
                                  "binding": self.binding, "frozen_library_hash": before}
                        immutable_json(path, result)
                    if result["binding"] != self.binding or result["input_hash"] != source["content_hash"] or result["frozen_library_hash"] != before:
                        raise ValueError("Diagnostic prediction reuse binding differs")
                    predictions.append(result)
        raw_grades = Path(grading_packet).read_bytes()
        if hashlib.sha256(raw_grades).hexdigest() != packet["grading_sha256"]:
            raise ValueError("Diagnostic grading packet differs from its committed hash")
        grades = json.loads(raw_grades)
        scores = []
        for row in predictions:
            source = parents[row["source"]]
            grade = grades[row["source"]][str(row["variant"])]
            scores.append({"source": row["source"], "dataset": row["dataset"], "variant": row["variant"],
                           "arm": row["arm"], "score": score_source(source, row["routed"]["result"], grade)})
        if digest(library) != before:
            raise ValueError("Diagnostics changed the frozen library")
        result = {"scores": scores, "skipped": [r for r in packet["sources"] if not r["variants"]],
                  "binding": self.binding, "actual_predictions": len(predictions),
                  "source_cluster_is_uncertainty_unit": True, "library_unchanged": True}
        immutable_json(self.artifacts / "diagnostics/scores.json", result)
        return result
