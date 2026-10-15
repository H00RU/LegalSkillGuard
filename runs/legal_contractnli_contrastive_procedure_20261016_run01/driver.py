"""One compiled knowledge bank, coherent versus deterministic atomic delivery."""

from __future__ import annotations

import copy
import fcntl
import json
import os
import pickle
import signal
import sys
import time
import warnings
import zipfile
from pathlib import Path

import numpy as np
from jsonschema import validate

from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.inference.native import WireClient
from legal_skill_guard.learning.audit import close, original_score
from legal_skill_guard.learning.experiment import ENDPOINTS, now, points, read, sha
from legal_skill_guard.learning.procedures import ARMS, BOUNDARY_GUIDANCE_SCHEMA, ProcedureStudy
from legal_skill_guard.learning.publication import TEACHER_SYSTEM, paired, skill_record_schema
from legal_skill_guard.task import marked_text, original_feedback, render_library
from legal_skill_guard.utils.hashing import canonical_json_sha256

ROOT = Path(__file__).resolve().parents[2]
TRAIN = ROOT / "runs/legal_contractnli_grounded_feedback_20261016_run01"
PARENT = ROOT / "runs/legal_contractnli_grounded_final_assessment_20261016_run01"
RUN_ID = "legal_contractnli_contrastive_procedure_20261016_run01"
PROTOCOL = ROOT / "reports/experiments/grounded_feedback_20261016/contrastive_procedure_protocol.md"
NEW_ARMS = ("coherent_branches", "flattened_branches")
FIELDS = ("when", "inspection", "relation_if_established", "evidence_requirement")

COMPILER_SYSTEM = TEACHER_SYSTEM.replace(
    "hidden reasoning or invented actions", "teacher hidden reasoning or invented actions"
) + (
    " Compile a compact full library of COHERENT CONTRASTIVE procedures, not "
    "independent outcome slogans. For the SAME exact legal issue, keep supported "
    "ordinary conditions, qualifying exceptions and non-applicability together. "
    "Do not mix unrelated topics or force three branches, all relations, one "
    "skill per hypothesis or any skill count. A generic inspection may have no "
    "branches. The outer four fields describe common source inspection, with "
    "null relation. Each branch names its exact public hypothesis and has its "
    "own condition, inspection, conditional relation and complete-evidence need. "
    "The common inspection must tell the lawyer to establish branch conditions "
    "from actual source and check relevant qualifiers before using a relation. "
    "A missing match is not evidence of the opposite relation or NotMentioned. "
    "Keep source conditions distinct from the exact hypothesis's polarity. "
    "Preserve rare supported boundaries; do not invent counterexamples merely "
    "to balance a structure. Consolidate true overlap without losing actor, "
    "action, object, trigger, exception or independent source evidence. "
    "The same existing 8B answers all17 in one call with full NDA and fallible "
    "same-data ordinary evidence candidates, never legal labels. All skills "
    "are visible; no planner or host selects or executes branches. No current "
    "answer tables, source indices, named parties, dates or case IDs in guidance. "
    "All24 original seen sources and labels are supplied. Only the six actual "
    "B4-after observations use the current M4 bank/tool; earlier observations "
    "are null. The supplied local_executor_trace is that same 8B's untrusted "
    "saved reasoning_content, not faithful causal evidence or teacher reasoning. "
    "Check actual answers against source/annotations; all successes and failures "
    "are included. No retention or future results are supplied. Do not invent "
    "them. Original labels are benchmark observations, not universal law. "
    "Return one full compiled library and one grounded rationale per skill. "
    "Audit case IDs stay in rationales only. This diagnostic mechanically makes "
    "a second library from your SAME text: for each branch it REPEATS common "
    "when/inspection/evidence plus branch when/inspection/evidence verbatim in "
    "one old atomic record. Both complete compact JSON encodings must fit4096 "
    "tokens each; keep common text particularly brief and avoid paraphrases. "
    "Do not fill the budget. No pruning, retry, fallback or quality admission "
    "will rescue an oversized output. No case-specific edits are requested."
)


def branch_guidance_schema(labels):
    branch = copy.deepcopy(BOUNDARY_GUIDANCE_SCHEMA)
    branch["required"].append("hypothesis_id")
    branch["properties"]["hypothesis_id"] = {"type": "string", "enum": list(labels)}
    guidance = copy.deepcopy(BOUNDARY_GUIDANCE_SCHEMA)
    guidance["properties"]["relation_if_established"] = {"type": "null"}
    guidance["required"].append("branches")
    guidance["properties"]["branches"] = {"type": "array", "items": branch}
    return guidance


def flatten(bank):
    """Preserve each common/branch field verbatim; no legal decision or rewrite."""
    result = []
    for i, skill in enumerate(bank):
        common = skill["guidance"]
        if not common["branches"]:
            result.append({**skill, "guidance": {k: common[k] for k in FIELDS}})
        for j, branch in enumerate(common["branches"]):
            guidance = {"relation_if_established": branch["relation_if_established"]}
            for key in ("when", "inspection", "evidence_requirement"):
                guidance[key] = "Common: " + common[key] + "\nBranch: " + branch[key]
            result.append(
                {
                    "id": f"flat-{i + 1}-{j + 1}",
                    "hypothesis_ids": [branch["hypothesis_id"]],
                    "guidance": {k: guidance[k] for k in FIELDS},
                }
            )
    return result


class ContrastiveStudy(ProcedureStudy):
    def __init__(self):
        self.run_id, self.out = RUN_ID, ROOT / "runs" / RUN_ID
        assert not (self.out / "declaration.json").exists(), "Never restart a Run ID"
        progress = read(PARENT / "progress.json")
        assert progress["state"] == "completed" and progress["completed_native_calls"] == 44
        launch = read(PARENT / "launch.json")
        assert not Path(f"/proc/{launch['pid']}").exists(), "Wait for exact parent exit"
        base = ROOT / "configs/contractnli_grounded_feedback.json"
        assert sha(base) == read(base.with_suffix(".frozen.json"))["config_sha256"]
        self.cfg = {**read(base), "planned_new_native_calls": 16, "planned_new_teacher_calls": 1}
        packet = read(ROOT / self.cfg["input_packet"])
        self.labels, self.training = packet["public_hypotheses"], packet["training"]
        self.future = packet["later_inputs_no_annotation_sets"]
        assert [r["id"] for r in self.future] == self.cfg["expected_later_ids"]
        assert len(self.training) == 24 and all("annotation_sets" not in r for r in self.future)
        self.native, self.units, self.teachers = [], [], []
        self.teacher_attempts, self.current_batch, self.stop = 0, 4, False
        self.meter = WireClient(self.cfg["generation"])
        self.bank = read(TRAIN / "update_transactions/trace_b4.json")["publication"]
        self.compiled = {}
        manifest = read(TRAIN / "evidence_models/ordinary_M4.manifest.json")
        assert sha(manifest["path"]) == manifest["pickle_sha256"]
        self.state, self.state_versions = (
            manifest["state_sha256"],
            {manifest["state_sha256"]: manifest},
        )
        with Path(manifest["path"]).open("rb") as stream:
            self.model = pickle.load(stream)
        self.bindings = read(PARENT / "declaration.json")["frozen_bindings"].copy()
        paths = [p for p in PARENT.rglob("*") if p.is_file() and p.suffix == ".json"]
        paths += [Path(__file__), PROTOCOL]
        self.bindings.update({str(p.resolve()): sha(p) for p in paths})
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: setattr(self, "stop", True))

    def bank_for(self, arm):
        return self.compiled[arm]

    def teacher_body(self):
        cases, observed = [], []
        for row in self.training:
            unit = None
            if row["batch"] == 4:
                unit = read(PARENT / f"batch4_after/trace_procedures/{row['id']}.public.json")
                assert unit["published_library"] == self.bank
                assert unit["actual_factual_trace"]["ordinary_model_state"] == self.state
                observed.append(unit)
            cases.append(
                {
                    "document_id": row["id"],
                    "full_original_contract_with_spans": marked_text(row),
                    "original_annotations": row["annotation_sets"][0]["annotations"],
                    "observation_kind": "actual_M4_B4_after"
                    if unit
                    else "source_only_no_M4_execution",
                    "actual_own_same_parent_observation": self.observation(unit, True)
                    if unit
                    else None,
                }
            )
        assert len(observed) == 6
        self.audit(observed, "all6_actual_teacher_observations")
        grouped = {}
        for key in self.labels:
            grouped[key] = []
            for case, row in zip(cases, self.training, strict=True):
                gold = case["original_annotations"][key]
                observation = case["actual_own_same_parent_observation"]
                prediction = None
                if observation is not None and observation["public_valid"]:
                    prediction = json.loads(observation["actual_public_response"]["content"])[key]
                grouped[key].append(
                    {
                        "document_id": row["id"],
                        "original_annotation": gold,
                        "all_original_annotated_source_spans": [
                            {"original_span_index": i, "verbatim_source_text": row["text"][a:b]}
                            for i in gold["spans"]
                            for a, b in [row["spans"][i]]
                        ],
                        "actual_current_M4_prediction_or_null": prediction,
                    }
                )
        return {
            "original_public_hypotheses": self.labels,
            "hypothesis_grouped_grounded_feedback": grouped,
            "complete_actual_parent_library": self.bank,
            "cumulative_seen_original_train_cases": cases,
            "actual_parent_library_sha256": canonical_json_sha256(self.bank),
            "actual_parent_ordinary_tool_state": self.state,
            "cumulative_original_train_count": 24,
            "actual_current_M4_observation_count": 6,
            "both_full_runtime_library_token_caps": 4096,
            "no_retention_future_other_learner_results": True,
            "all_six_observations_without_outcome_selection": True,
        }

    def compile(self):
        record = skill_record_schema(
            self.labels, guidance_schema=branch_guidance_schema(self.labels)
        )
        schema = {
            "type": "object",
            "additionalProperties": False,
            "required": ["library", "grounding_rationales"],
            "properties": {
                "library": {"type": "array", "items": record},
                "grounding_rationales": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["skill_id", "source_case_ids", "rationale"],
                        "properties": {
                            "skill_id": {"type": "string", "minLength": 1},
                            "source_case_ids": {
                                "type": "array",
                                "minItems": 1,
                                "items": {
                                    "type": "integer",
                                    "enum": [r["id"] for r in self.training],
                                },
                            },
                            "rationale": {"type": "string", "minLength": 1},
                        },
                    },
                },
            },
        }
        value = self.teacher_call(
            "compile_contrastive_knowledge", COMPILER_SYSTEM, self.teacher_body(), schema
        )
        bank = value["library"]
        ids = [s["id"] for s in bank]
        rationale_ids = [r["skill_id"] for r in value["grounding_rationales"]]
        assert len(ids) == len(set(ids)) == len(rationale_ids) == len(set(rationale_ids))
        assert set(ids) == set(rationale_ids)
        for skill in bank:
            assert len(skill["hypothesis_ids"]) == len(set(skill["hypothesis_ids"]))
            assert all(
                b["hypothesis_id"] in skill["hypothesis_ids"] for b in skill["guidance"]["branches"]
            )
        self.compiled = dict(zip(NEW_ARMS, (bank, flatten(bank)), strict=True))
        counts = {}
        for arm, library in self.compiled.items():
            assert len(library) == len({s["id"] for s in library})
            if arm == "flattened_branches":
                for skill in library:
                    validate(
                        skill,
                        skill_record_schema(self.labels, guidance_schema=BOUNDARY_GUIDANCE_SCHEMA),
                    )
            counts[arm] = self.meter.token_count(text=render_library(library))
            assert counts[arm] <= 4096, "Full encoding exceeds capacity; no pruning or fallback"
        RunStore.immutable_json(
            self.out / "compiled_libraries.json",
            {
                "at": now(),
                "libraries": self.compiled,
                "live_runtime_tokens": counts,
                "grounding_rationales": value["grounding_rationales"],
                "flat_is_deterministic_verbatim_common_plus_branch_projection": True,
                "different_lengths_and_ids_not_token_matched": True,
                "all_valid_results_evaluated_no_quality_admission": True,
            },
        )

    def audit(self, units, name):
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="X does not have valid feature names, but LGBMClassifier was fitted with feature names",
            )
            self.audit_native(units, name)

    def execute(self):
        self.check()
        RunStore.immutable_json(
            self.out / "declaration.json",
            {
                "at": now(),
                "run_id": RUN_ID,
                "pid": os.getpid(),
                "argv": sys.argv,
                "config": self.cfg,
                "frozen_bindings": self.bindings,
                "new_native_calls_planned": 16,
                "new_teacher_calls_planned": 1,
                "inherited_native_calls": 122,
                "inherited_teacher_calls": 5,
                "fixed_development_diagnostic_not_online_training_or_independent_repeat": True,
                "teacher_excludes_retention_and_endpoint_inputs_answers_labels_metrics": True,
            },
        )
        self.compile()
        self.check()
        self.progress("waiting_for_gpu_lease")
        with (ROOT / "artifacts/gpu_generation.lock").open("a+") as lease:
            while True:
                self.check()
                try:
                    fcntl.flock(lease.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    time.sleep(2)
            later = {a: [] for a in NEW_ARMS}
            for i, row in enumerate(self.future):
                for arm in NEW_ARMS[i % 2 :] + NEW_ARMS[: i % 2]:
                    later[arm].append(self.answer("later", arm, row, self.bank_for(arm)))
            self.complete(later)

    def complete(self, later):
        self.check()
        assert len(self.native) == len(self.units) == 16 and len(self.teachers) == 1
        reference = {
            a: [read(PARENT / f"later/{a}/{r['id']}.public.json") for r in self.future]
            for a in ARMS
        }
        self.audit(
            self.units + [u for units in reference.values() for u in units],
            "all48_answers_before_grading",
        )
        assert (
            len(
                {
                    u["response"]["raw_id"]
                    for units in [*later.values(), *reference.values()]
                    for u in units
                }
            )
            == 48
        )
        gold = read(ROOT / self.cfg["grading_only"])["annotations"]
        with zipfile.ZipFile(ROOT / self.cfg["source_archive"]) as archive:
            author = json.loads(archive.read("contract-nli/train.json"))
        sources = {r["id"]: r for r in author["documents"]}
        by = {}
        for arm, units in {**reference, **later}.items():
            by[arm] = []
            for row, unit in zip(self.future, units, strict=True):
                source = sources[row["id"]]
                assert (
                    unit["document_id"] == row["id"]
                    and row["text"] == source["text"]
                    and row["spans"] == source["spans"]
                )
                annotations = gold[str(row["id"])]
                assert annotations == source["annotation_sets"][0]["annotations"]
                feedback = original_feedback(unit["response"], row, annotations, list(self.labels))
                close(
                    original_score(unit["response"], row, annotations, list(self.labels)), feedback
                )
                scored = {**unit, **feedback}
                RunStore.immutable_json(
                    self.out / "later_scored" / arm / f"{row['id']}.json", scored
                )
                by[arm].append(scored)
        results, intervals, transitions = {a: points(u) for a, u in by.items()}, {}, {}
        rng = np.random.default_rng(self.cfg["bootstrap_seed"])
        for arm in NEW_ARMS:
            for control in (("flattened_branches",) if arm == "coherent_branches" else ()) + ARMS:
                name = arm + "_minus_" + control
                draws = {e: [] for e in ENDPOINTS}
                for _ in range(self.cfg["bootstrap_draws"]):
                    indices = rng.integers(0, 8, 8)
                    a, b = (points([by[k][i] for i in indices]) for k in (arm, control))
                    for e in ENDPOINTS:
                        draws[e].append(a[e] - b[e])
                intervals[name] = {
                    e: {
                        "point": results[arm][e] - results[control][e],
                        "ci95_descriptive_one_compilation_eight_exposed_sources": list(
                            map(float, np.quantile(v, [0.025, 0.975]))
                        ),
                    }
                    for e, v in draws.items()
                }
                transitions[name] = paired(by[control], by[arm])
        response = self.teachers[0]
        done = {
            "at": now(),
            "run_id": RUN_ID,
            "new_native_calls": 16,
            "new_teacher_calls": 1,
            "inherited_native_calls": 122,
            "inherited_teacher_calls": 5,
            "total_ancestry_native_calls": 138,
            "total_ancestry_teacher_calls": 6,
            "development": results,
            "paired_transitions": transitions,
            "descriptive_intervals": intervals,
            "new_native_usage": {
                k: sum(n["response"][k] for n in self.native)
                for k in ("prompt_tokens", "completion_tokens")
            },
            "new_teacher_usage": response["invocation"]["usage"],
            "all16_new_and32_reference_saved_replayed_before_grading": True,
            "new_vs_incumbent_changes_knowledge_and_adds_teacher_not_pure_format": True,
            "no_efficacy_admission_or_bank_selection": True,
            "exposed_development_not_formal_test_or_evolution_repeat": True,
        }
        RunStore.immutable_json(self.out / "completion.json", done)
        RunStore.atomic_json(
            self.out / "progress.json",
            {
                "at": now(),
                "state": "completed",
                "run_id": RUN_ID,
                "completed_native_calls": 16,
                "completed_teacher_calls": 1,
            },
        )


if __name__ == "__main__":
    study = ContrastiveStudy()
    try:
        study.execute()
    except BaseException as exc:
        failure = {
            "at": now(),
            "error": repr(exc),
            "run_id": RUN_ID,
            "completed_native_calls": len(study.native),
            "completed_teacher_calls": len(study.teachers),
            "teacher_attempts": study.teacher_attempts,
            "no_retry_fallback_or_old_bank_selection": True,
        }
        RunStore.immutable_json(study.out / "failure.json", failure)
        RunStore.atomic_json(
            study.out / "progress.json",
            {"state": "stopped" if isinstance(exc, InterruptedError) else "failed", **failure},
        )
        raise
