"""Native ACE legal adaptation with the same data, backbone and evidence models."""

from __future__ import annotations

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
from legal_skill_guard.inference.codex_cli_client import CodexCLIClient
from legal_skill_guard.inference.native import WireClient
from legal_skill_guard.task import original_feedback
from legal_skill_guard.utils.hashing import canonical_json_sha256

from .audit import close, original_score
from .evidence_programs import evidence_proposals, program_solver_messages
from .experiment import (
    ENDPOINTS,
    GENERATOR_PROMPT,
    INITIAL_PLAYBOOK,
    ROOT,
    Comparison,
    bullets,
    now,
    points,
    read,
    sha,
)
from .procedures import ARMS, ProcedureStudy, local_executor_trace
from .publication import paired

CONDITIONS = ("ace_legal", "ace_empty")


def ace_messages(row, labels, system, bank, proposals):
    ids = [{"id": key} for key in bullets(bank)]
    messages, schema = program_solver_messages(
        row, labels, system, proposals, guidance=ids, show_span_value_enum_in_prompt=False
    )
    prefix = GENERATOR_PROMPT.split("Your output should be a json object", 1)[0]
    messages[0]["content"] += (
        "\n"
        + prefix
        + (
            "\nFor this legal task use the supplied common output_contract, not ACE "
            "final_answer/reasoning/bullet_ids wrapper fields. Report actually used "
            "native bullet IDs per hypothesis in used_skill_ids. reason is a short "
            "public rationale, not private thinking. Reflection is empty: no current "
            "gold or current-case correction is supplied. Evidence candidates are "
            "fallible source leads, not legal labels or required citations."
        )
    )
    body = json.loads(messages[1]["content"])
    body["ACE_playbook_verbatim"] = bank
    body["ACE_current_case_reflection"] = "(empty)"
    messages[1]["content"] = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    return messages, schema


class ACESameData(Comparison):
    def __init__(self, config_path):
        path = Path(config_path).resolve()
        config = read(path)
        assert config["method"] == "native_ace_same_data_legal_adaptation"
        base = read(ROOT / config["base_config"])
        self.cfg = {
            **base,
            **config,
            "teacher": {
                **base["teacher"],
                "total_invocation_budget": config["teacher_invocation_budget"],
            },
        }
        # The base artifact describes a different teacher context/measurement
        # schedule; it is not capacity evidence for this native ACE adaptation.
        self.cfg.pop("input_budget_evidence", None)
        frozen = read(path.with_suffix(".frozen.json"))
        assert frozen["config_sha256"] == sha(path)
        self.bindings = {
            **frozen["files"],
            str(path.with_suffix(".frozen.json")): sha(path.with_suffix(".frozen.json")),
        }
        self.run_id = config["run_id"]
        self.out = ROOT / "runs" / self.run_id
        assert not (self.out / "declaration.json").exists(), "Never restart a Run ID"
        self.report = ROOT / config["report_directory"] / self.run_id
        packet = read(ROOT / self.cfg["input_packet"])
        self.labels, self.training = packet["public_hypotheses"], packet["training"]
        self.future = packet["later_inputs_no_annotation_sets"]
        assert [r["id"] for r in self.training] == base["training_ids"]
        assert [r["id"] for r in self.future] == base["expected_later_ids"]
        assert all("annotation_sets" not in r for r in self.future)
        self.native, self.units, self.teachers = [], [], []
        self.teacher_attempts, self.current_batch, self.stop = 0, 0, False
        self.meter = WireClient(self.cfg["generation"])
        self.banks = {"ace_legal": INITIAL_PLAYBOOK}
        self.before, self.after = {"ace_legal": {}}, {"ace_legal": {}}
        self.model, self.state, self.state_versions = None, None, {}
        self.manifests, self.summaries = {}, []
        self.source_parent = ROOT / "runs" / config["evidence_parent_run"]
        self.reference = ROOT / "runs" / config["reference_run"]
        for batch in (1, 2, 3, 4):
            manifest = read(self.source_parent / f"evidence_models/ordinary_M{batch}.manifest.json")
            assert sha(manifest["path"]) == manifest["pickle_sha256"]
            rows = [r for r in self.training if r["batch"] <= batch]
            assert manifest["seen_original_source_ids"] == [r["id"] for r in rows]
            assert manifest["original_training_rows_sha256"] == canonical_json_sha256(rows)
            assert manifest["programs"] == []
            self.manifests[batch] = manifest
            self.state_versions[manifest["state_sha256"]] = manifest
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: setattr(self, "stop", True))

    def observation(self, unit):
        return ProcedureStudy.observation(self, unit, include_trace=True)

    def messages(self, arm, row, bank):
        assert arm in CONDITIONS
        assert bank == (self.banks["ace_legal"] if arm == "ace_legal" else INITIAL_PLAYBOOK)
        proposal = evidence_proposals(self.model, row, self.labels)
        messages, schema = ace_messages(
            row, self.labels, self.cfg["bundled_solver_system"], bank, proposal
        )
        return messages, schema, None, {"ordinary_model_state": self.state, "proposals": proposal}

    def use_shared_model(self, batch):
        manifest = self.manifests[batch]
        assert sha(manifest["path"]) == manifest["pickle_sha256"]
        with Path(manifest["path"]).open("rb") as stream:
            self.model = pickle.load(stream)
        assert not self.model.programs and not self.model.queries
        self.state = manifest["state_sha256"]
        RunStore.immutable_json(
            self.out / f"shared_ordinary_M{batch}.json",
            {
                "actual_manifest": manifest,
                "explicit_inherited_fit_not_new_cpu_training": True,
                "same_past_prefix_labels_as_main_method": True,
            },
        )

    def execute(self):
        self.check()
        settings = self.cfg["teacher"]
        checker = CodexCLIClient(
            model=settings["model"],
            executable="/usr/bin/codex",
            cache_root=self.out / "teacher_admin",
            invocation_budget_path=ROOT / settings["ledger"],
            max_invocations=settings["total_invocation_budget"],
        )
        budget = checker.invocation_budget_status()
        assert budget["available"] >= 28, "Complete predeclared teacher sequence needs capacity"
        RunStore.immutable_json(
            self.out / "declaration.json",
            {
                "at": now(),
                "run_id": self.run_id,
                "pid": os.getpid(),
                "argv": sys.argv,
                "config": self.cfg,
                "frozen_bindings": self.bindings,
                "teacher_budget": budget,
                "new_native_calls_planned": 52,
                "new_teacher_calls_planned": 28,
                "native_ACE_legal_adaptation_not_our_new_method_or_canonical_reproduction": True,
                "teacher_own_actual_trace_access_matches_main": True,
                "generous8192_playbook_vs_main4096_not_equal_context_or_teacher_compute": True,
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
        self.progress("waiting_for_gpu_lease")
        with (ROOT / "artifacts/gpu_generation.lock").open("a+") as lease:
            while True:
                self.check()
                try:
                    fcntl.flock(lease.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    time.sleep(2)
            self.run_learning()

    def run_learning(self):
        first_checkpoint = None
        for batch in (1, 2, 3, 4):
            self.current_batch = batch
            rows = [r for r in self.training if r["batch"] == batch]
            before = self.collect(
                f"batch{batch}_before", "ace_legal", rows, self.banks["ace_legal"]
            )
            for unit in before:
                self.before["ace_legal"][unit["document_id"]] = [unit]
            self.banks["ace_legal"] = self.update_ace(batch)
            self.use_shared_model(batch)
            learned = None
            if batch == 1:
                first_checkpoint = self.collect(
                    "batch1_after", "ace_legal", rows, self.banks["ace_legal"]
                )
                learned = points(first_checkpoint)
            summary = {
                "at": now(),
                "batch": batch,
                "source_ids": [r["id"] for r in rows],
                "first_encounter": points(before),
                "B1_seen_checkpoint_if_collected": learned,
                "management": read(self.out / f"update_transactions/ace_legal_b{batch}.json"),
                "raw_different_source_curve_not_monotonicity_or_forgetting_proof": True,
                "B1_after_measurement_never_supplied_to_teachers": True,
            }
            self.summaries.append(summary)
            RunStore.immutable_json(self.out / f"batch{batch}_summary.json", summary)
            self.audit_own(
                [u for u in self.units if u["stage"].startswith(f"batch{batch}_")], f"batch{batch}"
            )
            self.progress("batch_complete", completed_batches=batch)
        first = [r for r in self.training if r["batch"] == 1]
        retained = self.collect("retention_b4", "ace_legal", first, self.banks["ace_legal"])
        RunStore.immutable_json(
            self.out / "retention_b4.json",
            {
                "metrics": points(retained),
                "B1_M1_to_M4": paired(first_checkpoint, retained),
                "never_to_teacher_or_admission": True,
                "ordinary_model_also_changes_not_pure_memory_effect": True,
            },
        )
        RunStore.immutable_json(
            self.out / "memory_frozen_before_later.json",
            {
                "at": now(),
                "native_playbook": self.banks["ace_legal"],
                "ordinary_model_state": self.state,
                "final_not_best_bank": True,
            },
        )
        later = {arm: [] for arm in CONDITIONS}
        for index, row in enumerate(self.future):
            for arm in CONDITIONS[index % 2 :] + CONDITIONS[: index % 2]:
                bank = self.banks["ace_legal"] if arm == "ace_legal" else INITIAL_PLAYBOOK
                later[arm].append(self.answer("later", arm, row, bank))
        self.finish(later)

    def audit_own(self, units, name):
        rows, models = {r["id"]: r for r in self.training + self.future}, {}
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="X does not have valid feature names, but LGBMClassifier was fitted with feature names",
            )
            for unit in units:
                row = rows[unit["document_id"]]
                state = unit["actual_factual_trace"]["ordinary_model_state"]
                model = None
                if state is not None:
                    manifest = self.state_versions[state]
                    assert sha(manifest["path"]) == manifest["pickle_sha256"]
                    if state not in models:
                        with Path(manifest["path"]).open("rb") as stream:
                            models[state] = pickle.load(stream)
                    model = models[state]
                proposal = evidence_proposals(model, row, self.labels)
                close(proposal, unit["actual_factual_trace"]["proposals"])
                bank = unit["published_library"]
                assert canonical_json_sha256(bank) == unit["published_library_sha256"]
                messages, schema = ace_messages(
                    row, self.labels, self.cfg["bundled_solver_system"], bank, proposal
                )
                raw = read(unit["raw_artifact"])
                assert raw["calls"][0]["request"]["messages"] == messages
                assert (
                    raw["calls"][0]["request"]["response_format"]["json_schema"]["schema"] == schema
                )
                assert raw["response"] == unit["response"]
                if unit["response"]["finish_reason"] == "stop":
                    validate(json.loads(unit["response"]["content"]), schema)
                if "annotation_sets" in row:
                    close(
                        original_score(
                            unit["response"],
                            row,
                            row["annotation_sets"][0]["annotations"],
                            list(self.labels),
                        ),
                        unit,
                    )
                local_executor_trace(unit)
        RunStore.immutable_json(
            self.out / "audits" / f"{name}.json",
            {
                "at": now(),
                "observations": len(units),
                "actual_source_native_playbook_candidates_schema_wire_trace_and_training_score_verified": True,
            },
        )

    def finish(self, later):
        self.check()
        assert len(self.native) == len(self.units) == 52 and len(self.teachers) == 28
        assert len({n["response"]["raw_id"] for n in self.native}) == 52
        self.audit_own(self.units, "all52_own_before_endpoint_grading")
        reference = {
            a: [read(self.reference / f"later/{a}/{r['id']}.public.json") for r in self.future]
            for a in ARMS
        }
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="X does not have valid feature names, but LGBMClassifier was fitted with feature names",
            )
            ProcedureStudy.audit_native(
                self,
                [u for units in reference.values() for u in units],
                "all32_reference_before_grading",
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
                source, annotations = sources[row["id"]], gold[str(row["id"])]
                assert row["text"] == source["text"] and row["spans"] == source["spans"]
                assert annotations == source["annotation_sets"][0]["annotations"]
                feedback = original_feedback(unit["response"], row, annotations, list(self.labels))
                close(
                    original_score(unit["response"], row, annotations, list(self.labels)), feedback
                )
                scored = {**unit, **feedback}
                by[arm].append(scored)
                RunStore.immutable_json(
                    self.out / "later_scored" / arm / f"{row['id']}.json", scored
                )
        metrics, transitions = {arm: points(units) for arm, units in by.items()}, {}
        rng, intervals = np.random.default_rng(self.cfg["bootstrap_seed"]), {}
        for control in ("ace_empty", *ARMS):
            transitions[control] = paired(by[control], by["ace_legal"])
            draws = {endpoint: [] for endpoint in ENDPOINTS}
            for _ in range(self.cfg["bootstrap_draws"]):
                indices = rng.integers(0, 8, 8)
                a, b = (points([by[arm][i] for i in indices]) for arm in ("ace_legal", control))
                for endpoint in ENDPOINTS:
                    draws[endpoint].append(a[endpoint] - b[endpoint])
            intervals[control] = {
                endpoint: {
                    "point": metrics["ace_legal"][endpoint] - metrics[control][endpoint],
                    "ci95_descriptive_one_learning_run_eight_exposed_sources": list(
                        map(float, np.quantile(values, [0.025, 0.975]))
                    ),
                }
                for endpoint, values in draws.items()
            }
        done = {
            "at": now(),
            "run_id": self.run_id,
            "new_native_calls": 52,
            "new_teacher_calls": 28,
            "development": metrics,
            "ace_minus_control_transitions": transitions,
            "descriptive_source_intervals": intervals,
            "batches": self.summaries,
            "new_native_usage": {
                k: sum(n["response"][k] for n in self.native)
                for k in ("prompt_tokens", "completion_tokens")
            },
            "new_teacher_usage": {
                k: sum(t["invocation"]["usage"][k] for t in self.teachers)
                for k in ("input_tokens", "output_tokens", "reasoning_output_tokens")
            },
            "all16_new_endpoints_and32_references_saved_replayed_before_grading": True,
            "own_empty_generator_control_distinguishes_prompt_effects": True,
            "same24_data_backbone_tool_not_equal_compute_or_context_or_canonical_ACE": True,
            "no_new_model_task_source_selection_answer_repair_or_bank_gate": True,
            "exposed_development_not_formal_test_or_independent_repeat_of_main": True,
        }
        RunStore.immutable_json(self.out / "completion.json", done)
        RunStore.atomic_json(
            self.out / "progress.json",
            {
                "at": now(),
                "state": "completed",
                "run_id": self.run_id,
                "completed_native_calls": 52,
                "completed_teacher_calls": 28,
            },
        )


if __name__ == "__main__":
    study = ACESameData(
        sys.argv[1]
        if len(sys.argv) > 1
        else ROOT / "configs/contractnli_ace_same_data_20261016.json"
    )
    try:
        study.execute()
    except BaseException as exc:
        failure = {
            "at": now(),
            "run_id": study.run_id,
            "error": repr(exc),
            "completed_native_calls": len(study.native),
            "completed_teacher_calls": len(study.teachers),
            "teacher_attempts": study.teacher_attempts,
            "no_retry_fallback_repair_or_bank_selection": True,
        }
        RunStore.immutable_json(study.out / "failure.json", failure)
        RunStore.atomic_json(
            study.out / "progress.json",
            {"state": "stopped" if isinstance(exc, InterruptedError) else "failed", **failure},
        )
        raise
