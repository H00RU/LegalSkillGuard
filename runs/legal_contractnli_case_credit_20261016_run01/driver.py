"""One bounded test of case-local teacher credit, with no runtime extra layer."""

from __future__ import annotations

import copy
import fcntl
import json
import os
import pickle
import signal
import sys
import time
import zipfile
from pathlib import Path

import numpy as np

from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.inference.native import WireClient
from legal_skill_guard.learning.audit import close, original_score
from legal_skill_guard.learning.experiment import (
    ENDPOINTS,
    REFLECTOR_PROMPT,
    now,
    points,
    read,
    sha,
)
from legal_skill_guard.learning.procedures import (
    ARMS,
    BOUNDARY_GUIDANCE_SCHEMA,
    PROCEDURE_TEACHER,
    local_executor_trace,
)
from legal_skill_guard.learning.publication import (
    apply_differential_publication,
    differential_schema,
    paired,
    publication_statistics,
)
from legal_skill_guard.task import marked_text, original_feedback
from legal_skill_guard.utils.hashing import canonical_json_sha256
from runs.legal_contractnli_contrastive_procedure_20261016_run01.driver import (
    PARENT,
    ROOT,
    TRAIN,
    ContrastiveStudy,
)

RUN_ID = "legal_contractnli_case_credit_20261016_run01"
GROUPING = ROOT / "runs/legal_contractnli_contrastive_delivery_20261016_run01"
PROTOCOL = ROOT / "reports/experiments/grounded_feedback_20261016/case_credit_protocol.md"
CONDITIONS = ("direct_refinement", "case_reflected_refinement")

EDITOR_SYSTEM = PROCEDURE_TEACHER.split("Only NON-NULL", 1)[0] + (
    "Only six B4-after observations are supplied, all genuinely executed under "
    "the exact current M4 parent and ordinary tool. Earlier18 cases have null "
    "current observations; never invent them. All24 original sources and Gold "
    "remain supplied. Compare different original labels for the SAME exact "
    "hypothesis, including unresolved near-misses, before settling a conditional "
    "relation. If source differences do not justify a confident universal rule, "
    "retain an inspection boundary rather than forcing a label or case lookup. "
    "The source_grounded_case_reflections list is either empty or contains "
    "separate public case audits derived ONLY from these same six observations. "
    "They are fallible teacher opinions, not contract facts or causal proof. "
    "Check each against complete original source and annotations. Do not append "
    "a rule merely because an audit calls it useful; correct/merge/remove "
    "unsupported breadth only with source justification, never performance "
    "admission or rollback. Keep original self-contained complete evidence, "
    "including redundant support. Do not let candidate membership replace a "
    "full-source check. Runtime remains one native answer; no current-case "
    "reflection, answer patch, planner or extra semantic judge. Return the "
    "requested atomic differential edit within the complete4096-token cap."
)

PUBLIC_REFLECTOR = REFLECTOR_PROMPT.replace(
    "your chain of thought / reasoning / thinking process, detailed analysis and calculations",
    "a concise source-supported public audit summary, not hidden reasoning",
).replace(
    "Your chain of thought / reasoning / thinking process, detailed analysis and calculations",
    "A concise source-supported public audit summary, not hidden reasoning",
)


class CaseCreditStudy(ContrastiveStudy):
    def __init__(self):
        self.run_id, self.out = RUN_ID, ROOT / "runs" / RUN_ID
        assert not (self.out / "declaration.json").exists(), "Never restart a Run ID"
        assert read(GROUPING / "progress.json")["state"] == "completed"
        assert not Path(f"/proc/{read(GROUPING / 'launch.json')['pid']}").exists()
        base = ROOT / "configs/contractnli_grounded_feedback.json"
        assert sha(base) == read(base.with_suffix(".frozen.json"))["config_sha256"]
        self.cfg = {**read(base), "planned_new_native_calls": 16, "planned_new_teacher_calls": 8}
        packet = read(ROOT / self.cfg["input_packet"])
        self.labels, self.training = packet["public_hypotheses"], packet["training"]
        self.future = packet["later_inputs_no_annotation_sets"]
        assert (
            len(self.training) == 24
            and [r["id"] for r in self.future] == self.cfg["expected_later_ids"]
        )
        assert all("annotation_sets" not in r for r in self.future)
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
        self.bindings = read(GROUPING / "declaration.json")["frozen_bindings"].copy()
        paths = [p for p in GROUPING.rglob("*") if p.is_file() and p.suffix == ".json"]
        paths += [
            Path(__file__),
            PROTOCOL,
            ROOT / "third_party/ace/prompts/reflector.py",
            ROOT / "third_party/ace/LICENSE.txt",
            ROOT / "third_party/ace/NOTICE.md",
        ]
        self.bindings.update({str(p.resolve()): sha(p) for p in paths})
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: setattr(self, "stop", True))

    def reflect(self, row):
        unit = read(PARENT / f"batch4_after/trace_procedures/{row['id']}.public.json")
        assert unit["published_library"] == self.bank
        assert unit["actual_factual_trace"]["ordinary_model_state"] == self.state
        cited = sorted(
            {sid for q in (unit["parsed"] or {}).values() for sid in q["used_skill_ids"]}
        )
        known = {s["id"]: s for s in self.bank}
        assert set(cited) <= set(known)
        tags = {
            "type": "array",
            "minItems": len(cited),
            "maxItems": len(cited),
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "tag"],
                "properties": {
                    "id": {"type": "string"},
                    "tag": {"type": "string", "enum": ["helpful", "harmful", "neutral"]},
                },
            },
        }
        if cited:
            tags["items"]["properties"]["id"]["enum"] = cited
        fields = (
            "reasoning",
            "error_identification",
            "root_cause_analysis",
            "correct_approach",
            "key_insight",
        )
        schema = {
            "type": "object",
            "additionalProperties": False,
            "required": [*fields, "bullet_tags"],
            "properties": {**{k: {"type": "string"} for k in fields}, "bullet_tags": tags},
        }
        prompt = PUBLIC_REFLECTOR.format(
            json.dumps(
                {"original_hypotheses": self.labels, "full_original_contract": marked_text(row)},
                ensure_ascii=False,
            ),
            json.dumps(local_executor_trace(unit), ensure_ascii=False),
            unit["response"]["content"],
            json.dumps(row["annotation_sets"][0]["annotations"], ensure_ascii=False),
            json.dumps(unit["queries"], ensure_ascii=False),
            json.dumps([known[s] for s in cited], ensure_ascii=False),
        )
        value = self.teacher_call(
            f"reflect_source_{row['id']}",
            "Use the pinned ACE-inspired case audit below, adapted to original "
            "ContractNLI labels AND complete binary evidence. Return concise public "
            "source-supported findings, not your hidden reasoning. The supplied "
            "trace is only the local8B's actual untrusted text, not causal proof "
            "or source facts. Check against the full contract and gold. Do not "
            "invent an error on correct components. Separate condition misuse, "
            "source assertion, wrong relation, missing/excess evidence and genuinely "
            "uncertain annotation without relabelling it. Consider candidates "
            "fallible; evidence outside them is allowed. Tag exactly each supplied "
            "actually reported skill once; helpful/harmful is your audit opinion, "
            "not efficacy admission or deletion. No tools, future cases, named-case "
            "patches, current-case retries or external law. Keep findings compact.",
            prompt,
            schema,
        )
        assert len(value["bullet_tags"]) == len({t["id"] for t in value["bullet_tags"]})
        assert {t["id"] for t in value["bullet_tags"]} == set(cited)
        return {
            "document_id": row["id"],
            "actual_observation_raw_id": unit["response"]["raw_id"],
            "actual_parent_library_sha256": unit["published_library_sha256"],
            "actual_parent_tool_state": self.state,
            "reflection": value,
        }

    def edit(self, arm, body, reflections):
        request = {**copy.deepcopy(body), "source_grounded_case_reflections": reflections}
        seen = [r["id"] for r in self.training]
        value = self.teacher_call(
            arm,
            EDITOR_SYSTEM,
            request,
            differential_schema(
                self.labels, self.bank, seen, guidance_schema=BOUNDARY_GUIDANCE_SCHEMA
            ),
        )
        bank = apply_differential_publication(
            self.bank, value, self.labels, seen, guidance_schema=BOUNDARY_GUIDANCE_SCHEMA
        )
        count = self.validate_library(bank)
        self.compiled[arm] = bank
        RunStore.immutable_json(
            self.out / "update_transactions" / f"{arm}.json",
            {
                "at": now(),
                "actual_parent": self.bank,
                "actual_teacher_value": value,
                "publication": bank,
                "management": publication_statistics(self.bank, value, bank, count),
                "common_original_information_sha256": canonical_json_sha256(body),
                "reflection_count": len(reflections),
                "all_valid_edits_published_without_effect_gate": True,
            },
        )

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
                "new_teacher_calls_planned": 8,
                "inherited_native_calls": 138,
                "inherited_teacher_calls": 6,
                "same_parent_source_gold_own_observations_different_teacher_case_credit_only": True,
                "no_runtime_extra_model_stage_or_effect_admission": True,
            },
        )
        body = self.teacher_body()
        del body["both_full_runtime_library_token_caps"]
        body["full_library_token_cap"] = self.cfg["library_token_hard_cap"]
        self.edit(CONDITIONS[0], body, [])
        reflections = [self.reflect(r) for r in self.training if r["batch"] == 4]
        RunStore.immutable_json(
            self.out / "source_grounded_case_reflections.json", {"reflections": reflections}
        )
        self.edit(CONDITIONS[1], body, reflections)
        self.progress("waiting_for_gpu_lease")
        with (ROOT / "artifacts/gpu_generation.lock").open("a+") as lease:
            while True:
                self.check()
                try:
                    fcntl.flock(lease.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    time.sleep(2)
            later = {a: [] for a in CONDITIONS}
            for i, row in enumerate(self.future):
                for arm in CONDITIONS[i % 2 :] + CONDITIONS[: i % 2]:
                    later[arm].append(self.answer("later", arm, row, self.bank_for(arm)))
            self.complete(later)

    def complete(self, later):
        self.check()
        assert len(self.native) == len(self.units) == 16 and len(self.teachers) == 8
        reference = {
            a: [read(PARENT / f"later/{a}/{r['id']}.public.json") for r in self.future]
            for a in ARMS
        }
        self.audit(
            self.units + [u for units in reference.values() for u in units],
            "all48_saved_before_grading",
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
            original = json.loads(archive.read("contract-nli/train.json"))
        sources = {r["id"]: r for r in original["documents"]}
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
                RunStore.immutable_json(
                    self.out / "later_scored" / arm / f"{row['id']}.json", scored
                )
                by[arm].append(scored)
        metrics, intervals, transitions = {a: points(u) for a, u in by.items()}, {}, {}
        rng = np.random.default_rng(self.cfg["bootstrap_seed"])
        for arm in CONDITIONS:
            controls = ((CONDITIONS[0],) if arm == CONDITIONS[1] else ()) + ARMS
            for control in controls:
                name, draws = arm + "_minus_" + control, {e: [] for e in ENDPOINTS}
                for _ in range(self.cfg["bootstrap_draws"]):
                    indices = rng.integers(0, 8, 8)
                    a, b = (points([by[k][i] for i in indices]) for k in (arm, control))
                    for endpoint in ENDPOINTS:
                        draws[endpoint].append(a[endpoint] - b[endpoint])
                intervals[name] = {
                    e: {
                        "point": metrics[arm][e] - metrics[control][e],
                        "ci95_descriptive_one_update_eight_exposed_sources": list(
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
            "new_teacher_calls": 8,
            "inherited_native_calls": 138,
            "inherited_teacher_calls": 6,
            "total_ancestry_native_calls": 154,
            "total_ancestry_teacher_calls": 14,
            "development": metrics,
            "paired_transitions": transitions,
            "descriptive_intervals": intervals,
            "new_native_usage": {
                k: sum(n["response"][k] for n in self.native)
                for k in ("prompt_tokens", "completion_tokens")
            },
            "new_teacher_usage": {
                k: sum(t["invocation"]["usage"][k] for t in self.teachers)
                for k in ("input_tokens", "output_tokens", "reasoning_output_tokens")
            },
            "all16_new_and32_references_saved_replayed_before_grading": True,
            "teacher_additional_calls_are_treatment_not_equal_budget": True,
            "ACE_inspired_case_credit_not_full_ACE_or_formal_online_repeat": True,
            "exposed_development_no_bank_selection_or_answer_repair": True,
        }
        RunStore.immutable_json(self.out / "completion.json", done)
        RunStore.atomic_json(
            self.out / "progress.json",
            {
                "at": now(),
                "state": "completed",
                "run_id": RUN_ID,
                "completed_native_calls": 16,
                "completed_teacher_calls": 8,
            },
        )


if __name__ == "__main__":
    study = CaseCreditStudy()
    try:
        study.execute()
    except BaseException as exc:
        failure = {
            "at": now(),
            "run_id": RUN_ID,
            "error": repr(exc),
            "completed_native_calls": len(study.native),
            "completed_teacher_calls": len(study.teachers),
            "teacher_attempts": study.teacher_attempts,
            "no_retry_fallback_pruning_or_old_bank_selection": True,
        }
        RunStore.immutable_json(study.out / "failure.json", failure)
        RunStore.atomic_json(
            study.out / "progress.json",
            {"state": "stopped" if isinstance(exc, InterruptedError) else "failed", **failure},
        )
        raise
