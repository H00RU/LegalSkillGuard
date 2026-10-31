"""Evaluate exact archived knowledge with compact deterministic serialization."""

from __future__ import annotations

import fcntl
import os
import pickle
import signal
import sys
import time
import zipfile
from pathlib import Path

import numpy as np
from jsonschema import validate

from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.inference.native import WireClient
from legal_skill_guard.learning.audit import close, original_score
from legal_skill_guard.learning.experiment import ENDPOINTS, now, points, read, sha
from legal_skill_guard.learning.procedures import ARMS, BOUNDARY_GUIDANCE_SCHEMA
from legal_skill_guard.learning.publication import paired, skill_record_schema
from legal_skill_guard.task import original_feedback, render_library
from runs.legal_contractnli_contrastive_procedure_20261016_run01.driver import (
    FIELDS,
    NEW_ARMS,
    PARENT,
    ROOT,
    TRAIN,
    ContrastiveStudy,
    branch_guidance_schema,
)

RUN_ID = "legal_contractnli_contrastive_delivery_20261016_run01"
COMPILER = ROOT / "runs/legal_contractnli_contrastive_procedure_20261016_run01"
PROTOCOL = ROOT / "reports/experiments/grounded_feedback_20261016/contrastive_delivery_protocol.md"


def flat_delivery(bank):
    result = []
    for skill in bank:
        common = skill["guidance"]
        branches = common["branches"]
        if not branches:
            result.append(
                {
                    "id": f"f{len(result) + 1}",
                    "hypothesis_ids": skill["hypothesis_ids"],
                    "guidance": {k: common[k] for k in FIELDS},
                }
            )
        for branch in branches:
            guidance = {"relation_if_established": branch["relation_if_established"]}
            for key in ("when", "inspection", "evidence_requirement"):
                guidance[key] = common[key] + "\n" + branch[key]
            result.append(
                {
                    "id": f"f{len(result) + 1}",
                    "hypothesis_ids": [branch["hypothesis_id"]],
                    "guidance": {k: guidance[k] for k in FIELDS},
                }
            )
    return result


class DeliveryStudy(ContrastiveStudy):
    def __init__(self):
        self.run_id, self.out = RUN_ID, ROOT / "runs" / RUN_ID
        assert not (self.out / "declaration.json").exists(), "Never restart a Run ID"
        old = read(COMPILER / "progress.json")
        assert old["state"] == "failed" and old["completed_native_calls"] == 0
        assert old["completed_teacher_calls"] == 1
        assert read(PARENT / "progress.json")["state"] == "completed"
        for folder in (PARENT, COMPILER):
            assert not Path(f"/proc/{read(folder / 'launch.json')['pid']}").exists()
        base = ROOT / "configs/contractnli_grounded_feedback.json"
        assert sha(base) == read(base.with_suffix(".frozen.json"))["config_sha256"]
        self.cfg = {**read(base), "planned_new_native_calls": 16, "planned_new_teacher_calls": 0}
        packet = read(ROOT / self.cfg["input_packet"])
        self.labels, self.training = packet["public_hypotheses"], packet["training"]
        self.future = packet["later_inputs_no_annotation_sets"]
        assert [r["id"] for r in self.future] == self.cfg["expected_later_ids"]
        assert all("annotation_sets" not in r for r in self.future)
        self.native, self.units, self.teachers = [], [], []
        self.teacher_attempts, self.current_batch, self.stop = 0, 4, False
        self.meter = WireClient(self.cfg["generation"])
        manifest = read(TRAIN / "evidence_models/ordinary_M4.manifest.json")
        assert sha(manifest["path"]) == manifest["pickle_sha256"]
        self.state, self.state_versions = (
            manifest["state_sha256"],
            {manifest["state_sha256"]: manifest},
        )
        with Path(manifest["path"]).open("rb") as stream:
            self.model = pickle.load(stream)
        self.teacher_artifact = COMPILER / "teacher/compile_contrastive_knowledge/response.json"
        bank = read(self.teacher_artifact)["value"]["library"]
        self.compiled = dict(zip(NEW_ARMS, (bank, flat_delivery(bank)), strict=True))
        self.bindings = read(COMPILER / "declaration.json")["frozen_bindings"].copy()
        paths = [p for p in COMPILER.rglob("*") if p.is_file() and p.suffix == ".json"]
        paths += [Path(__file__), PROTOCOL]
        self.bindings.update({str(p.resolve()): sha(p) for p in paths})
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: setattr(self, "stop", True))

    def teacher_call(self, *args, **kwargs):
        raise RuntimeError("No new teacher allowed; exact archived knowledge only")

    def execute(self):
        self.check()
        counts = {}
        for arm, bank in self.compiled.items():
            assert len(bank) == len({s["id"] for s in bank})
            schema = (
                branch_guidance_schema(self.labels)
                if arm == NEW_ARMS[0]
                else BOUNDARY_GUIDANCE_SCHEMA
            )
            for skill in bank:
                validate(skill, skill_record_schema(self.labels, guidance_schema=schema))
            counts[arm] = self.meter.token_count(text=render_library(bank))
            assert counts[arm] <= 4096, "No capacity relaxation, pruning or fallback"
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
                "new_teacher_calls_planned": 0,
                "inherited_native_calls": 122,
                "inherited_teacher_calls": 6,
                "exact_archived_compiler_response": str(self.teacher_artifact),
                "archived_teacher_sha256": sha(self.teacher_artifact),
                "failed_compiler_run_preserved_not_restarted": True,
            },
        )
        RunStore.immutable_json(
            self.out / "compiled_libraries.json",
            {
                "at": now(),
                "libraries": self.compiled,
                "live_runtime_tokens": counts,
                "verbatim_common_and_branch_legal_texts_and_relations": True,
                "only_flat_headings_removed_and_ids_shortened_not_knowledge_pruned": True,
                "flat_ids_sequential_and_different_prompt_lengths_not_token_matched": True,
            },
        )
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
        assert len(self.native) == len(self.units) == 16 and not self.teachers
        references = {
            a: [read(PARENT / f"later/{a}/{r['id']}.public.json") for r in self.future]
            for a in ARMS
        }
        self.audit(
            self.units + [u for units in references.values() for u in units],
            "all48_saved_before_grading",
        )
        assert (
            len(
                {
                    u["response"]["raw_id"]
                    for units in [*later.values(), *references.values()]
                    for u in units
                }
            )
            == 48
        )
        gold = read(ROOT / self.cfg["grading_only"])["annotations"]
        with zipfile.ZipFile(ROOT / self.cfg["source_archive"]) as archive:
            import json

            original = json.loads(archive.read("contract-nli/train.json"))
        sources = {r["id"]: r for r in original["documents"]}
        by = {}
        for arm, units in {**references, **later}.items():
            by[arm] = []
            for row, unit in zip(self.future, units, strict=True):
                source, annotations = sources[row["id"]], gold[str(row["id"])]
                assert (
                    unit["document_id"] == row["id"]
                    and source["text"] == row["text"]
                    and source["spans"] == row["spans"]
                )
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
            controls = ((NEW_ARMS[1],) if arm == NEW_ARMS[0] else ()) + ARMS
            for control in controls:
                name, draws = arm + "_minus_" + control, {e: [] for e in ENDPOINTS}
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
        done = {
            "at": now(),
            "run_id": RUN_ID,
            "new_native_calls": 16,
            "new_teacher_calls": 0,
            "inherited_native_calls": 122,
            "inherited_teacher_calls": 6,
            "total_ancestry_native_calls": 138,
            "total_ancestry_teacher_calls": 6,
            "development": results,
            "paired_transitions": transitions,
            "descriptive_intervals": intervals,
            "new_native_usage": {
                k: sum(n["response"][k] for n in self.native)
                for k in ("prompt_tokens", "completion_tokens")
            },
            "archived_compiler_usage_not_new_teacher": read(self.teacher_artifact)["invocation"][
                "usage"
            ],
            "all16_new_and32_reference_saved_replayed_before_grading": True,
            "no_quality_admission_or_best_bank_rollback": True,
            "same_new_knowledge_but_ids_and_lengths_differ_not_pure_structure_causality": True,
            "new_vs_incumbent_adds_knowledge_refinement_not_pure_format": True,
            "development_only_not_full_online_repeat_or_formal_test": True,
        }
        RunStore.immutable_json(self.out / "completion.json", done)
        RunStore.atomic_json(
            self.out / "progress.json",
            {
                "at": now(),
                "state": "completed",
                "run_id": RUN_ID,
                "completed_native_calls": 16,
                "completed_teacher_calls": 0,
            },
        )


if __name__ == "__main__":
    study = DeliveryStudy()
    try:
        study.execute()
    except BaseException as exc:
        failure = {
            "at": now(),
            "run_id": RUN_ID,
            "error": repr(exc),
            "completed_native_calls": len(study.native),
            "completed_teacher_calls": 0,
            "no_retry_fallback_pruning_or_old_bank_selection": True,
        }
        RunStore.immutable_json(study.out / "failure.json", failure)
        RunStore.atomic_json(
            study.out / "progress.json",
            {"state": "stopped" if isinstance(exc, InterruptedError) else "failed", **failure},
        )
        raise
