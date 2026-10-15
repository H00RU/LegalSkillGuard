"""Online executable evidence memory, with a same-label data-only control.

The frozen lawyer still emits every original relation and evidence member. The
teacher edits factual query programs, not answer tables. An external supervised
scorer learns how their actual matches relate to original span membership.
No current-case annotations, efficacy admission, answer repair or model swap.
"""

from __future__ import annotations

import copy
import importlib.metadata
import json
import os
import pickle
import signal
import sys
import time
import zipfile
from pathlib import Path

import numpy as np
from jsonschema import validate

from legal_skill_guard.data import FUTURE_IDS, source_components
from legal_skill_guard.experiment.storage import RunStore, safe_component
from legal_skill_guard.inference.codex_cli_client import CodexCLIClient
from legal_skill_guard.inference.native import WireClient
from legal_skill_guard.report import write_report
from legal_skill_guard.task import marked_text, original_feedback
from legal_skill_guard.utils.hashing import canonical_json_sha256

from .audit import close, original_score
from .evidence_programs import (
    SCORER_PARAMETERS,
    evidence_proposals,
    fit_program_model,
    program_queries,
    program_solver_messages,
)
from .experiment import ENDPOINTS, ROOT, Comparison, now, points, read, sha
from .interface import callable_skill_schema, publication_schema, publish, query_schema
from .publication import paired

ARMS = ("strong_empty", "base_memory", "static_memory", "evolving_memory")

PROGRAM_TEACHER_SYSTEM = (
    "Learn reusable FACTUAL SOURCE-QUERY PROGRAMS from every supplied already-seen "
    "original TRAIN case and your own learner's genuine outputs. This is supervised "
    "external evidence memory, not language-model weight training or pure verbal "
    "memory. At inference the frozen lawyer receives the complete original NDA and "
    "fallible evidence-membership candidates from a CPU classifier. It receives NO "
    "program guidance text, current gold, prior draft, legal verdict from the host, "
    "or mandatory intermediate checks. Guidance is a human-readable program docstring, "
    "not a policy delivered to the lawyer. Only executable queries can change features. "
    "Each scoped query produces two binary span features: a literal phrase match and "
    "membership in its explicit before/after context window. A supervised TF-IDF/LR/"
    "LightGBM scorer fits these features against ALL seen original membership labels, "
    "including all-negative NotMentioned cases. It learns feature relevance rather "
    "than automatically unioning matches into evidence. Matching is contiguous "
    "lower-case lightly suffix-stemmed word/number tokens; all_phrases are all needed, "
    "any_phrases needs one if nonempty, none_phrases excludes. At least one all/any "
    "phrase is required. before/after are explicit counts of original neighbour "
    "spans. Negation and modality are preserved. Public hypothesis_ids constrain "
    "execution; the same legal topic does not make a span evidence. Empty matches "
    "do not mean NotMentioned. Do not create broad catch-all neighbour windows or "
    "exhaustive synonym lists to manufacture coverage. Use compact reusable phrases "
    "that distinguish observed missing support from tempting non-evidence, including "
    "independent parallel support and necessary definitional/exception context. "
    "Inspect actual counterexamples across ALL seen cases, not only failures or one "
    "label. Labels are original benchmark feedback, not universal legal rules. "
    "Do not claim query hits or self-reported skill IDs prove legal utility. "
    "Runtime programs must not contain document IDs, parties, dates, source span "
    "indices, answer tables or automatic Entailment/Contradiction/NotMentioned rules. "
    "Publish explicit CREATE/UPDATE/DELETE/MERGE operations on the exact parent. "
    "Unmentioned parent records remain verbatim. CREATE has no targets; UPDATE and "
    "DELETE exactly one; MERGE at least two. Targets are distinct original parent "
    "IDs, never forward references. UPDATE preserves its target ID; MERGE may reuse "
    "a consumed ID or create a new ID. Only DELETE has null skill. Each edit cites "
    "actual seen source_case_ids and explains the changed factual boundary; those "
    "audit fields never enter inference. A non-deleted skill has at least one query. "
    "No mandatory skill types, counts or growth. If no change is warranted, return "
    "operations [] and a nonempty noop_reason; otherwise noop_reason is null. All "
    "structurally valid edits are published without efficacy gates or rollback. "
    "No tools, external facts, private thinking, invented trajectories, other "
    "learners, retention cases or future evaluation. Return exactly the JSON schema."
)

STATIC_PROGRAM_SYSTEM = (
    "Create a compact reusable library of FACTUAL SOURCE-QUERY PROGRAMS using ONLY "
    "the supplied public ContractNLI hypotheses and query API. No documents, answers, "
    "annotations or learner outputs are provided; do not invent any. Programs are "
    "features of an external supervised evidence scorer, not legal verdict rules. "
    "Each skill has id, distinct public hypothesis_ids, guidance as a human-readable "
    "docstring NOT delivered to the lawyer, and one or more factual queries. Each "
    "query has all_phrases, any_phrases, none_phrases and before/after original-span "
    "neighbour counts. Matching is contiguous lower-case lightly suffix-stemmed "
    "word/number tokens; all terms required, any needs one if supplied, none excludes. "
    "At least one all/any phrase is required. Preserve negation/modality. A match is "
    "not verified evidence, and a miss is not NotMentioned. The full original source "
    "remains available to the frozen lawyer. Prefer compact phrases identifying "
    "relevant operative clauses and their explicit context, not generic catch-all "
    "queries, long synonym enumeration, case IDs, parties, dates, source indices or "
    "answer lookup tables. No fixed types, counts or mandatory growth. Return the "
    "requested library; this static library will never receive experience updates."
)


def executable_publication_schema(labels, parent, seen_ids):
    schema = publication_schema(labels, parent, seen_ids)
    skill = schema["properties"]["operations"]["items"]["properties"]["skill"]["anyOf"][0]
    skill["properties"]["queries"]["minItems"] = 1
    return schema


def prepare_operator_packets(root, cfg):
    """Original TRAIN data; evaluation is explicitly already-exposed development."""
    archive = root / cfg["source_archive"]
    if sha(archive) != cfg["source_archive_sha256"]:
        raise ValueError("Pinned archive bytes differ")
    with zipfile.ZipFile(archive) as stream:
        data = json.loads(stream.read("contract-nli/train.json"))
    docs = {r["id"]: r for r in data["documents"]}
    training, future = cfg["training_ids"], cfg["expected_later_ids"]
    selected = set(training + future)
    if len(training) != 24 or len(future) != 8 or len(selected) != 32:
        raise ValueError("Declared24 TRAIN/8 development source matrix required")
    if selected & set(FUTURE_IDS):
        raise ValueError("Protected historical24 cannot enter development")
    for group in source_components(data["documents"]):
        if len(set(group) & selected) > 1 or (
            set(group) & selected and set(group) & set(FUTURE_IDS)
        ):
            raise ValueError("Duplicate or protected source component")
    RunStore.immutable_json(
        root / cfg["input_packet"],
        {
            "public_hypotheses": data["labels"],
            "training": [{**docs[i], "batch": j // 6 + 1} for j, i in enumerate(training)],
            "later_inputs_no_annotation_sets": [
                {k: v for k, v in docs[i].items() if k != "annotation_sets"} for i in future
            ],
        },
    )
    RunStore.immutable_json(
        root / cfg["grading_only"],
        {
            "annotations": {str(i): docs[i]["annotation_sets"][0]["annotations"] for i in future},
            "read_only_after_all32_later_native_answers_saved": True,
            "developer_exposed_previously_not_a_new_blind_test": True,
        },
    )
    selection = {
        "training_ids": training,
        "future_ids": future,
        "source_archive_sha256": sha(archive),
        "read_members": ["contract-nli/train.json"],
        "source_disjoint": True,
        "selection": cfg["selection_description"],
        "later_ids_already_exposed_by_completed_compact_delivery": True,
        "official_dev_test_opened": False,
    }
    RunStore.immutable_json(root / cfg["preselection"], selection)
    return selection


def teacher_observation(unit):
    """Only actual own public output, tool actions and component feedback.

    Exact query bodies live once in the supplied historical library versions.
    Full float vectors remain in raw artifacts; the teacher gets the actual
    binary candidates delivered at inference and exact query match/context sets.
    """
    proposal = unit["actual_factual_trace"]["proposals"]
    return {
        "stage": unit["stage"],
        "raw_id": unit["response"]["raw_id"],
        "raw_artifact": unit["raw_artifact"],
        "public_content_verbatim": unit["response"]["content"],
        "finish_reason": unit["response"]["finish_reason"],
        "public_valid": unit["public_valid"],
        "public_error": unit["public_error"],
        "program_library_sha256": unit["published_library_sha256"],
        "evidence_state": unit["actual_factual_trace"]["state"],
        "actual_candidate_sets_and_query_executions": None
        if proposal is None
        else {
            k: {
                "candidate_members": [c["original_span_index"] for c in v["candidates"]],
                "queries": [
                    {f: t[f] for f in ("query_id", "direct_matches", "context")}
                    for t in v["executed_program_queries"]
                ],
            }
            for k, v in proposal["by_hypothesis"].items()
        },
        "original_component_feedback": [
            {
                "hypothesis_id": q["hypothesis_id"],
                "label_correct": q["label_correct"],
                "joint_exact": q["joint_exact"],
                "missing_original_members": sorted(
                    set(q["gold"]["spans"]) - set((q["prediction"] or {}).get("spans", []))
                ),
                "excess_original_members": sorted(
                    set((q["prediction"] or {}).get("spans", [])) - set(q["gold"]["spans"])
                ),
            }
            for q in unit["queries"]
        ],
    }


class OperatorStudy(Comparison):
    """Four real online updates, not isolated B1 or a post-hoc chosen library."""

    def __init__(self, config_path, *, run_id=None):
        self.config_path = Path(config_path).resolve()
        self.cfg = read(self.config_path)
        self.run_id = safe_component(run_id or self.cfg["run_id"])
        self.out = ROOT / "runs" / self.run_id
        self.report = ROOT / self.cfg["report_directory"] / self.run_id
        if self.out.exists():
            raise FileExistsError("New Run ID required")
        frozen = read(self.config_path.with_suffix(".frozen.json"))
        if frozen["config_sha256"] != sha(self.config_path):
            raise ValueError("Frozen config differs")
        self.bindings = frozen["files"]
        packet = read(ROOT / self.cfg["input_packet"])
        self.labels, self.training = packet["public_hypotheses"], packet["training"]
        self.future = packet["later_inputs_no_annotation_sets"]
        if (len(self.labels), len(self.training), len(self.future)) != (17, 24, 8):
            raise ValueError("Original17 hypotheses,24 TRAIN,8 development required")
        if any(sum(r["batch"] == b for r in self.training) != 6 for b in range(1, 5)):
            raise ValueError("Each batch has six original sources")
        if any("annotation_sets" in r for r in self.future):
            raise ValueError("Evaluation annotations in inference packet")
        self.meter = WireClient(self.cfg["generation"])
        self.native, self.units, self.teachers, self.shared_units = [], [], [], []
        self.teacher_attempts, self.current_batch, self.stop = 0, 0, False
        self.bank, self.static, self.before, self.after = [], [], {}, {}
        self.versions = {canonical_json_sha256([]): []}
        self.models = {a: None for a in ARMS if a != "strong_empty"}
        self.states = dict.fromkeys(self.models)
        self.state_versions, self.summaries = {}, []
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda *_: setattr(self, "stop", True))

    def bank_for(self, arm):
        return (
            self.bank if arm == "evolving_memory" else self.static if arm == "static_memory" else []
        )

    def messages(self, arm, row, bank):
        if arm not in ARMS or bank != self.bank_for(arm):
            raise ValueError("Wrong arm or current program library")
        model = None if arm == "strong_empty" else self.models[arm]
        state = None if arm == "strong_empty" else self.states[arm]
        if model is not None and model.program_sha256 != canonical_json_sha256(bank):
            raise ValueError("Model/program version mismatch")
        proposal = evidence_proposals(model, row, self.labels)
        messages, schema = program_solver_messages(
            row, self.labels, self.cfg["bundled_solver_system"], proposal
        )
        return messages, schema, None, {"state": state, "proposals": proposal}

    def validate_programs(self, bank):
        program_queries(bank, self.labels)
        tokens = self.meter.token_count(text=json.dumps(bank, ensure_ascii=False))
        if tokens > self.cfg["library_token_hard_cap"]:
            raise ValueError("Full program library exceeds cap; no pruning or fallback")
        return tokens

    def initial_static(self):
        item = callable_skill_schema(self.labels)
        item["properties"]["queries"]["minItems"] = 1
        value = self.teacher_call(
            "static_public_task_only",
            STATIC_PROGRAM_SYSTEM,
            {
                "public_hypotheses": self.labels,
                "factual_query_api": query_schema(),
                "library_token_cap": self.cfg["library_token_hard_cap"],
            },
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["library"],
                "properties": {"library": {"type": "array", "items": item}},
            },
        )
        self.static = value["library"]
        tokens = self.validate_programs(self.static)
        RunStore.immutable_json(
            self.out / "static_programs.json",
            {
                "library": self.static,
                "tokens": tokens,
                "no_train_sources_or_labels_or_outputs_seen": True,
            },
        )

    def update(self, batch):
        seen = [r for r in self.training if r["batch"] <= batch]
        body = {
            "original_public_hypotheses": self.labels,
            "complete_actual_parent_library": self.bank,
            "actual_historical_program_libraries": self.versions,
            "query_id_encoding": "skill_id + __q + zero-based query index in the matching historical library",
            "factual_query_api": query_schema(),
            "all_seen_original_train_cases": [
                {
                    "document_id": r["id"],
                    "full_original_contract_with_spans": marked_text(r),
                    "original_annotations": r["annotation_sets"][0]["annotations"],
                    "actual_first_encounter_before_learning": teacher_observation(
                        self.before[r["id"]]
                    ),
                    "actual_prior_seen_fit_after_learning": teacher_observation(self.after[r["id"]])
                    if r["id"] in self.after
                    else None,
                }
                for r in seen
            ],
            "full_library_token_cap": self.cfg["library_token_hard_cap"],
            "no_future_retention_other_learners_or_private_thinking": True,
        }
        value = self.teacher_call(
            f"evolving_b{batch}",
            PROGRAM_TEACHER_SYSTEM,
            body,
            executable_publication_schema(self.labels, self.bank, [r["id"] for r in seen]),
        )
        bank = publish(self.bank, value, self.labels, [r["id"] for r in seen])
        tokens = self.validate_programs(bank)
        RunStore.immutable_json(
            self.out / "update_transactions" / f"b{batch}.json",
            {
                "at": now(),
                "batch": batch,
                "actual_parent": self.bank,
                "actual_teacher_value": value,
                "publication": bank,
                "library_tokens": tokens,
                "source_case_ids": [r["id"] for r in seen],
                "no_effect_gate_or_rollback_or_mandatory_growth": True,
            },
        )
        self.bank = bank
        self.versions[canonical_json_sha256(bank)] = copy.deepcopy(bank)

    def fit_memories(self, batch):
        seen = [r for r in self.training if r["batch"] <= batch]
        for arm in self.models:
            self.check()
            self.progress("fit_external_memory", current_arm=arm)
            started = time.monotonic()
            model = fit_program_model(seen, self.labels, self.bank_for(arm))
            path = self.out / "evidence_models" / f"{arm}_M{batch}.pickle"
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as stream:
                pickle.dump(model, stream, protocol=5)
                stream.flush()
                os.fsync(stream.fileno())
            manifest = {
                "at": now(),
                "arm": arm,
                "batch": batch,
                "path": str(path),
                "pickle_sha256": sha(path),
                "seen_original_source_ids": [r["id"] for r in seen],
                "original_training_rows_sha256": canonical_json_sha256(seen),
                "programs": self.bank_for(arm),
                "program_library_sha256": model.program_sha256,
                "parameters": SCORER_PARAMETERS,
                "fit_and_serialize_seconds": time.monotonic() - started,
                "original_scoring_pair_count": len(model.scoring_pairs_),
                "original_not_mentioned_pair_count": sum(
                    a["label"] == "NotMentioned" for a in model.scoring_pairs_
                ),
                "feature_split_counts": dict(
                    zip(model.feature_names_, map(int, model.m2_.feature_importances_), strict=True)
                ),
                "feature_names_are_training_full_head_before_any_inference": True,
                "no_lawyer_weights_updated": True,
            }
            identity = canonical_json_sha256(manifest)
            RunStore.immutable_json(
                path.with_suffix(".manifest.json"), {"state_sha256": identity, **manifest}
            )
            self.models[arm], self.states[arm] = model, identity
            self.state_versions[identity] = manifest

    def share_cold(self, unit, arm, row):
        messages, schema, _, trace = self.messages(arm, row, [])
        wire = read(unit["raw_artifact"])["calls"][0]["request"]
        if (
            wire["messages"] != messages
            or wire["response_format"]["json_schema"]["schema"] != schema
        ):
            raise ValueError("Cold sharing requires identical actual native input")
        shared = {
            **unit,
            "stage": "batch1_before",
            "arm": arm,
            "actual_factual_trace": trace,
            "shared_exact_cold_answer_no_new_generation": True,
        }
        RunStore.immutable_json(
            self.out / "batch1_before" / arm / f"{row['id']}.shared.json", shared
        )
        self.shared_units.append(shared)
        return shared

    def execute(self):
        self.check()
        RunStore.immutable_json(
            self.out / "launch.json", {"at": now(), "pid": os.getpid(), "argv": sys.argv}
        )
        RunStore.immutable_json(
            self.out / "declaration.json",
            {
                "at": now(),
                "config": self.cfg,
                "frozen_bindings": self.bindings,
                "new_method_development_not_confirmed_improvement": True,
                "hybrid_supervised_external_memory_not_pure_verbal_skill_learning": True,
            },
        )
        RunStore.immutable_json(
            self.out / "source_snapshot.json",
            {
                "files": {
                    p: {"sha256": h, "utf8_text": Path(p).read_text()}
                    for p, h in self.bindings.items()
                    if Path(p).suffix in (".py", ".md", ".txt") or Path(p).name == "LICENSE"
                }
            },
        )
        t = self.cfg["teacher"]
        checker = CodexCLIClient(
            model=t["model"],
            executable="/usr/bin/codex",
            cache_root=self.out / "teacher_admin",
            invocation_budget_path=ROOT / t["ledger"],
            max_invocations=t["total_invocation_budget"],
        )
        ready, teacher_ready, budget = (
            self.meter.readiness(),
            checker.preflight(),
            checker.invocation_budget_status(),
        )
        RunStore.immutable_json(
            self.out / "readiness.json",
            {
                "native": ready,
                "teacher": teacher_ready,
                "budget": budget,
                "runtime_versions": {
                    p: importlib.metadata.version(p)
                    for p in ("numpy", "scipy", "scikit-learn", "lightgbm", "jsonschema")
                },
            },
        )
        if not ready["ready"] or not teacher_ready["ready"] or budget["available"] < 5:
            raise RuntimeError("Declared inference/teacher unavailable; no substitute")
        self.initial_static()
        for batch in range(1, 5):
            self.current_batch = batch
            rows = [r for r in self.training if r["batch"] == batch]
            before = {a: [] for a in ("strong_empty", "base_memory", "evolving_memory")}
            for index, row in enumerate(rows):
                if batch == 1:
                    base = self.collect("batch1_before", "strong_empty", [row], [])[0]
                    before["strong_empty"].append(base)
                    for arm in ("base_memory", "evolving_memory"):
                        before[arm].append(self.share_cold(base, arm, row))
                else:
                    order = list(before)
                    offset = (batch + index) % len(order)
                    for arm in order[offset:] + order[:offset]:
                        before[arm].extend(
                            self.collect(f"batch{batch}_before", arm, [row], self.bank_for(arm))
                        )
                self.before[row["id"]] = before["evolving_memory"][-1]
            self.update(batch)
            self.fit_memories(batch)
            after = self.collect(f"batch{batch}_after", "evolving_memory", rows, self.bank)
            for unit in after:
                self.after[unit["document_id"]] = unit
            summary = {
                "at": now(),
                "batch": batch,
                "source_ids": [r["id"] for r in rows],
                "before": {a: points(u) for a, u in before.items()},
                "after": {"evolving_memory": points(after)},
                "strong_empty": points(before["strong_empty"]),
                "update_effects": paired(before["evolving_memory"], after),
                "first_encounter_evolving_minus_same_label_base": paired(
                    before["base_memory"], before["evolving_memory"]
                ),
                "actual_library_counts": {"evolving_memory": len(self.bank)},
                "actual_query_count": len(program_queries(self.bank, self.labels)),
                "external_model_states": copy.deepcopy(self.states),
                "after_includes_new_labels_and_program_update_not_a_pure_skill_causal_effect": True,
            }
            self.summaries.append(summary)
            RunStore.immutable_json(self.out / f"batch{batch}_summary.json", summary)
            write_report(self.out)
            self.progress("batch_complete", completed_batches=batch)
        first = [r for r in self.training if r["batch"] == 1]
        retained = self.collect("retention_b4", "evolving_memory", first, self.bank)
        RunStore.immutable_json(
            self.out / "retention_b4.json",
            {
                "metrics": points(retained),
                "B1_M1_to_M4": paired([self.after[r["id"]] for r in first], retained),
                "never_to_teacher_or_publication_gate": True,
            },
        )
        RunStore.immutable_json(
            self.out / "memory_frozen_before_later.json",
            {
                "at": now(),
                "library": self.bank,
                "static": self.static,
                "evidence_states": self.states,
                "last_published_not_best_checkpoint": True,
            },
        )
        later = {a: [] for a in ARMS}
        for index, row in enumerate(self.future):
            offset = index % len(ARMS)
            for arm in ARMS[offset:] + ARMS[:offset]:
                later[arm].append(self.answer("later", arm, row, self.bank_for(arm)))
        self.finish(later)

    def audit_native(self):
        """Reconstruct source/tool/schema from saved states, and original scores."""
        rows = {r["id"]: r for r in self.training + self.future}
        models = {}
        for unit in self.units + self.shared_units:
            row = rows[unit["document_id"]]
            state = unit["actual_factual_trace"]["state"]
            model = None
            if state is not None:
                manifest = self.state_versions[state]
                if sha(manifest["path"]) != manifest["pickle_sha256"]:
                    raise ValueError("Saved evidence state changed")
                if state not in models:
                    with Path(manifest["path"]).open("rb") as stream:
                        models[state] = pickle.load(stream)  # Only our hashed local artifacts.
                model = models[state]
                if model.program_sha256 != unit["published_library_sha256"]:
                    raise ValueError("Native unit has wrong program/state version")
            proposal = evidence_proposals(model, row, self.labels)
            close(proposal, unit["actual_factual_trace"]["proposals"])
            messages, schema = program_solver_messages(
                row,
                self.labels,
                self.cfg["bundled_solver_system"],
                unit["actual_factual_trace"]["proposals"],
            )
            native = read(unit["raw_artifact"])
            wire = native["calls"][0]["request"]
            if (
                wire["messages"] != messages
                or wire["response_format"]["json_schema"]["schema"] != schema
                or native["response"] != unit["response"]
            ):
                raise ValueError("Actual source/tool/schema/answer wire mismatch")
            if unit["response"]["finish_reason"] == "stop":
                validate(json.loads(unit["response"]["content"]), schema)
            if "annotation_sets" in row:
                expected = original_score(
                    unit["response"],
                    row,
                    row["annotation_sets"][0]["annotations"],
                    list(self.labels),
                )
                close(expected, {k: unit[k] for k in expected})
        RunStore.immutable_json(
            self.out / "native_state_audit.json",
            {
                "at": now(),
                "physical_responses": len(self.native),
                "logical_observations": len(self.units) + len(self.shared_units),
                "exact_hashed_state_source_tool_schema_wire_and_train_original_score": True,
            },
        )

    def finish(self, later):
        self.check()
        if (len(self.native), len(self.teachers), len(self.shared_units)) != (122, 5, 12):
            raise ValueError("Declared complete learning/control call matrix required")
        if any(len(units) != 8 for units in later.values()):
            raise ValueError("All32 later answers required before current grading Gold")
        self.audit_native()
        gold = read(ROOT / self.cfg["grading_only"])["annotations"]
        future = {r["id"]: r for r in self.future}
        by = {}
        for arm, units in later.items():
            by[arm] = []
            for unit in units:
                row = future[unit["document_id"]]
                scored = original_feedback(
                    unit["response"], row, gold[str(row["id"])], list(self.labels)
                )
                expected = original_score(
                    unit["response"], row, gold[str(row["id"])], list(self.labels)
                )
                close(expected, {k: scored[k] for k in expected})
                value = {**unit, **scored}
                RunStore.immutable_json(
                    self.out / "later_scored" / arm / f"{row['id']}.json", value
                )
                by[arm].append(value)
        results = {a: points(u) for a, u in by.items()}
        rng = np.random.default_rng(self.cfg["bootstrap_seed"])
        intervals = {}
        for control in ARMS[:-1]:
            draws = {e: [] for e in ENDPOINTS}
            for _ in range(self.cfg["bootstrap_draws"]):
                sample = rng.integers(0, 8, 8)
                current, other = (
                    points([by[a][int(i)] for i in sample]) for a in ("evolving_memory", control)
                )
                for endpoint in draws:
                    draws[endpoint].append(current[endpoint] - other[endpoint])
            intervals[control] = {
                e: {
                    "point": results["evolving_memory"][e] - results[control][e],
                    "ci95_descriptive_conditional_on_one_learned_state": list(
                        map(float, np.quantile(v, [0.025, 0.975]))
                    ),
                }
                for e, v in draws.items()
            }
        raw_ids = [n["response"]["raw_id"] for n in self.native]
        if len(set(raw_ids)) != len(raw_ids):
            raise ValueError("Duplicate physical generation identities")
        done = {
            "at": now(),
            "run_id": self.run_id,
            "new_native_calls": len(self.native),
            "new_teacher_calls": len(self.teachers),
            "explicit_shared_cold_answers": len(self.shared_units),
            "batches": self.summaries,
            "development": results,
            "paired_evolving_minus_control": {
                a: paired(by[a], by["evolving_memory"]) for a in ARMS[:-1]
            },
            "descriptive_source_intervals": intervals,
            "native_usage": {
                k: sum(n["response"][k] for n in self.native)
                for k in ("prompt_tokens", "completion_tokens")
            },
            "teacher_usage": {
                k: sum(t["invocation"]["usage"][k] for t in self.teachers)
                for k in ("input_tokens", "output_tokens", "reasoning_output_tokens")
            },
            "cpu_fit_seconds": sum(
                s["fit_and_serialize_seconds"] for s in self.state_versions.values()
            ),
            "later_developer_exposed_not_official_test_or_independent_learning_repeat": True,
            "learned_scorer_is_supervised_external_memory_not_lawyer_weight_update": True,
            "final_native_answers_not_repaired_merged_selected_or_filled": True,
            "ordinary_same_label_memory_must_be_beaten_to_claim_program_learning_value": True,
        }
        RunStore.immutable_json(self.out / "completion.json", done)
        RunStore.immutable_json(self.report / "complete_metrics.json", done)
        write_report(self.out)
        RunStore.atomic_json(
            self.out / "progress.json",
            {
                "at": now(),
                "state": "completed",
                "run_id": self.run_id,
                "completed_native_calls": len(self.native),
                "completed_teacher_calls": len(self.teachers),
                "completed_batches": 4,
            },
        )
