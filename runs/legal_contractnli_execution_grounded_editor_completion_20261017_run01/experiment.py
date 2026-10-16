"""Explicit failed0/2-prefix continuation; paired own-program revision, not retry."""

# ruff: noqa: E402 -- Independent, frozen run-local entry point.
from __future__ import annotations

import fcntl
import importlib.util
import json
import os
import pickle
import signal
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from jsonschema import validate

from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.inference.codex_cli_client import (
    CODEX_TURN_INPUT_CHARACTER_LIMIT,
    render_structured_codex_prompt,
)
from legal_skill_guard.inference.native import WireClient
from legal_skill_guard.learning.audit import close, original_score
from legal_skill_guard.learning.experiment import Comparison, now, points, read, sha
from legal_skill_guard.learning.publication import apply_differential_publication, differential_schema
from legal_skill_guard.learning.source_programs import PROGRAM_GUIDANCE_SCHEMA, SourceProgramStudy
from legal_skill_guard.task import marked_text
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha

PREFIX = ROOT / "runs/legal_contractnli_execution_grounded_editor_diagnostic_20261017_run01"
spec = importlib.util.spec_from_file_location("paired_editor_prefix", PREFIX / "experiment.py")
CORE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(CORE)
MAIN, CONFIG, IDS, ARMS = CORE.MAIN, CORE.CONFIG, CORE.IDS, CORE.ARMS
SYSTEM = CORE.SYSTEM.replace(
    "revising a fixed M2 DRAFT once", "revising its OWN first-pass proposal once"
).replace("this M2 draft", "this current proposal").replace(
    "this supplied M2 DRAFT", "this supplied current proposal"
) + (
    " This is one explicitly costed SECOND writer pass, not a hidden retry or "
    "new critic. The earlier two-call diagnostic failed before ANY lawyer "
    "answer. You receive your own exact prior response/current proposal and "
    "actual tokenizer measurements of BOTH master and real one-copy scope "
    "representation. No native outcomes under it exist. Revise relative to "
    "current_proposal_library, not original_M2_draft_library. Both arms receive "
    "this same capacity procedure, even if a prior proposal fit. Its executed "
    "scope/index format cannot be changed or hidden. Aim below2700 master to "
    "leave real scope overhead within the4096 hard limit. Condense repeated "
    "prose and redundant phrases without erasing justified legal distinctions "
    "or evidence coverage. Reconsider query precision/composition using all "
    "supplied original training contrasts; do not equate length with utility. "
    "The feedback arm additionally sees actual executions of THIS current "
    "proposal on all12 TRAIN sources; the blind arm receives none. These are "
    "source-only operations, not native answers. No B3/future/other-arm outcome "
    "is provided. This is the only additional writer pass in this diagnostic; "
    "invalid/oversize final output fails the experiment without another pass, "
    "clipping, pruning, cap raise or using the previous bank."
)


def prepare():
    assert not (OUT / "registration.json").exists()
    assert not Path("/proc", str(read(PREFIX / "launch.json")["pid"])).exists()
    failure = read(PREFIX / "failure.json")
    assert [failure["completed_native_calls"], failure["completed_teacher_calls"]] == [0, 2]
    audit_path = PREFIX / "monitoring/terminal0_native_2_teacher_capacity_audit.json"
    audit = read(audit_path)
    assert all(sha(p) == h for p, h in audit["source_and_comparator_bindings"].items())
    cfg, packet = read(CONFIG), read(ROOT / read(CONFIG)["input_packet"])
    observed_parent = read(MAIN / "update_transactions/b2.json")["actual_parent"]
    capacities, chars, parents, lineage = {}, {}, {}, []
    paths = [Path(__file__), OUT / "PROTOCOL.md", audit_path, PREFIX / "failure.json", PREFIX / "launch.json",
        ROOT / "artifacts/source_program_paired_editor_terminal0_2_all301_backup_20261017.json"]
    for arm in ARMS:
        parent = audit["arms"][arm]["proposed_bank_not_a_new_serving_publication"]
        inputs, observations = CORE.teaching_inputs(cfg, packet, parent, observed_parent)
        body = inputs[arm]
        assert body.pop("fixed_M2_draft_library") == parent
        body["current_proposal_library"] = parent
        body["original_M2_draft_library"] = read(PREFIX / "registration.json")["fixed_original_M2_draft"]
        prior = read(PREFIX / f"teacher/{arm}/response.json")
        body["own_exact_first_pass_response"] = prior["value"]
        body["same_writer_actual_capacity_feedback"] = {
            k: audit["arms"][arm][k] for k in (
                "skill_count", "query_count", "master_tokens", "actual_one_copy_and_scope_tokens",
                "scope_overhead_tokens", "over_cap_tokens",
            )
        } | {"hard_cap_for_both_representations": cfg["library_token_hard_cap"],
            "no_native_answers_under_either_first_pass_proposal_exist": True}
        user = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
        chars[arm] = len(render_structured_codex_prompt(SYSTEM, user))
        assert chars[arm] <= CODEX_TURN_INPUT_CHARACTER_LIMIT
        RunStore.immutable_json(OUT / f"teacher_inputs/{arm}.json", body)
        capacities[arm], parents[arm] = body["same_writer_actual_capacity_feedback"], parent
        lineage.append({"arm": arm, "explicit_inherited_not_new_spend": True,
            "response_path": str(PREFIX / f"teacher/{arm}/response.json"), "invocation": prior["invocation"]})
        paths.extend([OUT / f"teacher_inputs/{arm}.json", PREFIX / f"teacher/{arm}/response.json", *observations])
    bindings = {**audit["source_and_comparator_bindings"], **{str(p): sha(p) for p in paths}}
    RunStore.immutable_json(OUT / "registration.json", {
        "at": now(), "files": bindings, "teacher_source_ids": cfg["training_ids"][:12],
        "native_source_ids": IDS, "current_proposal_parent_by_arm": parents,
        "inherited_actual_teacher_invocations": lineage, "capacity_feedback": capacities,
        "teacher_rendered_characters": chars, "new_native_teacher_calls": [12, 2],
        "lineage_native_teacher_calls_if_complete": [12, 4],
        "equal_two_writer_calls_each_not_equal_tokens_or_independent_learning": True,
        "all12_answers_saved_before_any_new_scoring_no_future_teacher_observation": True,
    })
    print(json.dumps({"bindings": len(bindings), "teacher_prompt_chars": chars,
        "preparation_generation_calls": 0, "new_native_teacher_calls": [12, 2]}))


class Probe(Comparison):
    def __init__(self):
        self.cfg = {**read(CONFIG), "planned_new_native_calls": 12, "planned_new_teacher_calls": 2}
        self.bindings = read(OUT / "registration.json")["files"]
        self.run_id, self.out = OUT.name, OUT
        self.native, self.teachers, self.teacher_attempts, self.current_batch, self.stop = [], [], 0, 3, False
        self.packet = read(ROOT / self.cfg["input_packet"])
        self.labels = self.packet["public_hypotheses"]
        self.meter = WireClient(self.cfg["generation"])
        self.renderer = object.__new__(SourceProgramStudy)
        self.renderer.cfg, self.renderer.labels, self.renderer.meter = self.cfg, self.labels, self.meter
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: setattr(self, "stop", True))

    def execute(self):
        self.check()
        reg, banks = read(OUT / "registration.json"), {}
        for arm in ARMS:
            parent = reg["current_proposal_parent_by_arm"][arm]
            schema = differential_schema(self.labels, parent, reg["teacher_source_ids"], guidance_schema=PROGRAM_GUIDANCE_SCHEMA)
            value = self.teacher_call(arm, SYSTEM, read(OUT / f"teacher_inputs/{arm}.json"), schema)
            banks[arm] = apply_differential_publication(parent, value, self.labels,
                reg["teacher_source_ids"], guidance_schema=PROGRAM_GUIDANCE_SCHEMA)
            capacity = self.renderer.validate_library(banks[arm])
            RunStore.immutable_json(OUT / f"condition_publications/{arm}.json", {
                "actual_parent_proposal": parent, "actual_teacher_value": value,
                "publication": banks[arm], "capacity": capacity,
                "all_valid_edits_used_no_efficacy_gate_or_fallback": True})
        manifest = read(ROOT / self.cfg["reference_training_run"] / "evidence_models/ordinary_M2.manifest.json")
        assert manifest["seen_original_source_ids"] == reg["teacher_source_ids"]
        assert sha(manifest["path"]) == manifest["pickle_sha256"]
        with Path(manifest["path"]).open("rb") as stream:
            model = pickle.load(stream)
        assert not model.queries and not model.programs
        rows = {r["id"]: r for r in self.packet["training"]}
        prepared, counts = {}, {}
        for arm in ARMS:
            for d in IDS:
                row = CORE.NoGold(rows[d])
                messages, schema, _, trace = self.renderer.make_payload("skill_memory", row, banks[arm], model, manifest["state_sha256"])
                baseline = json.loads(read(MAIN / f"batch3_before/ordinary_memory/{d}.final.native.json")["calls"][0]["request"]["messages"][1]["content"])
                body = json.loads(messages[1]["content"])
                assert all(body["hypotheses"][h]["fallible_evidence_candidates"] == baseline["hypotheses"][h]["fallible_evidence_candidates"] for h in self.labels)
                restored = body["full_contract_with_original_span_markers"]
                for tag in trace["task_local_delivery"]["source_lead_tags_by_original_span"].values():
                    restored = restored.replace(tag, "", 1)
                assert restored == marked_text(row)
                tokens = self.meter.token_count(messages=messages)
                assert tokens + self.cfg["generation"]["max_tokens"] <= self.cfg["generation"]["context_tokens"]
                prepared[arm, d] = messages, schema, trace
                counts[f"{arm}/{d}"] = {"prompt_tokens": tokens, "messages_sha256": csha(messages), "schema_sha256": csha(schema)}
        RunStore.immutable_json(OUT / "all12_prospective_native_inputs.json", {
            "requests": counts, "both_proposals_valid_before_any_native": True,
            "same_ordinary_M2_candidates_source_and_decode_no_fit": True})
        with (ROOT / "artifacts/gpu_generation.lock").open("a+") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            for index, d in enumerate(IDS):
                for arm in ARMS if index % 2 == 0 else ARMS[::-1]:
                    messages, schema, trace = prepared[arm, d]
                    self.call(OUT / f"native/{arm}/{d}.native.json", messages, schema, self.cfg["generation"]["max_tokens"], {
                        "stage": "paired_own_program_second_revision_B3", "arm": arm, "document_id": d,
                        "call_role": "final", "published_library": banks[arm], "actual_factual_trace": trace})
            self.finish_probe()

    def finish_probe(self):
        assert len(self.native) == len({r["response"]["raw_id"] for r in self.native}) == 12
        assert len(self.teachers) == self.teacher_attempts == 2
        assert sha(ROOT / self.cfg["source_archive"]) == self.cfg["source_archive_sha256"]
        with zipfile.ZipFile(ROOT / self.cfg["source_archive"]) as archive:
            author = json.loads(archive.read("contract-nli/train.json"))
        rows = {r["id"]: r for r in author["documents"] if r["id"] in IDS}
        groups, files = {a: [] for a in ("ordinary_memory", *ARMS)}, {}
        for d in IDS:
            for arm in groups:
                path = MAIN / f"batch3_before/ordinary_memory/{d}.final.native.json" if arm == "ordinary_memory" else OUT / f"native/{arm}/{d}.native.json"
                raw = read(path)
                score = original_score(raw["response"], rows[d], rows[d]["annotation_sets"][0]["annotations"], list(author["labels"]))
                if score["public_valid"]:
                    validate(score["parsed"], raw["calls"][0]["request"]["response_format"]["json_schema"]["schema"])
                if arm == "ordinary_memory":
                    close(score["queries"], read(MAIN / f"batch3_before/ordinary_memory/{d}.public.json")["queries"])
                groups[arm].append({"document_id": d, "response": raw["response"], **score})
                files[str(path)] = sha(path)
        contrasts = {}
        for old, new in (("ordinary_memory", ARMS[0]), ("ordinary_memory", ARMS[1]), (ARMS[0], ARMS[1])):
            pairs = [(a, b) for left, right in zip(groups[old], groups[new], strict=True)
                for a, b in zip(left["queries"], right["queries"], strict=True)]
            value = {k: {"fixes": sum(not a[k] and b[k] for a, b in pairs), "damage": sum(a[k] and not b[k] for a, b in pairs)} for k in ("label_correct", "joint_exact")}
            def true(q):
                return set() if q["prediction"] is None else set(q["prediction"]["spans"]) & set(q["gold"]["spans"])
            nn = [(a, b) for a, b in pairs if a["gold_non_neutral"]]
            value.update(true_members_gained=sum(len(true(b) - true(a)) for a, b in nn),
                true_members_lost=sum(len(true(a) - true(b)) for a, b in nn))
            contrasts[new + "_minus_" + old] = value
        self.check()
        result = {"at": now(), "run_id": self.run_id, "native_source_ids": IDS,
            "all12_new_answers_saved_before_any_new_outcome_scoring": True,
            "new_native_teacher_calls": [12, 2], "lineage_native_teacher_calls": [12, 4],
            "inherited_failed_prefix_invocations": read(OUT / "registration.json")["inherited_actual_teacher_invocations"],
            "equal_two_writer_calls_each_not_matched_tokens_or_independent_learning": True,
            "metrics": {a: points(us) for a, us in groups.items()}, "paired_contrasts": contrasts, "all_units": groups,
            "native_usage": {k: sum(n["response"][k] for n in self.native) for k in ("prompt_tokens", "completion_tokens")},
            "teacher_invocations": [{"name": t["name"], "invocation": t["invocation"]} for t in self.teachers],
            "audited_file_sha256": {**self.bindings, **files},
            "not_formal_TEST_significance_or_main_skill_admission": True}
        RunStore.immutable_json(OUT / "completion.json", result)
        RunStore.atomic_json(OUT / "progress.json", {"at": now(), "state": "completed", "run_id": self.run_id,
            "completed_native_calls": 12, "completed_teacher_calls": 2})
        print(json.dumps({k: result[k] for k in ("run_id", "metrics", "paired_contrasts")}, ensure_ascii=False))


if __name__ == "__main__":
    command = sys.argv[1]
    if command == "prepare":
        prepare()
    elif command == "launch":
        assert (OUT / "registration.json").exists() and not (OUT / "launch.json").exists()
        argv = [str(ROOT / ".venv/bin/python"), str(Path(__file__).resolve()), "worker"]
        with (OUT / "worker.log").open("xb") as log:
            child = subprocess.Popen(argv, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log,
                stderr=subprocess.STDOUT, start_new_session=True, env={**os.environ, "PYTHONUNBUFFERED": "1"})
        RunStore.immutable_json(OUT / "launch.json", {"at": now(), "pid": child.pid, "actual_argv": argv,
            "background_independent_of_conversation": True})
        print(json.dumps({"run_id": OUT.name, "pid": child.pid}))
    elif command == "worker":
        probe = Probe()
        try:
            probe.execute()
        except BaseException as exc:
            value = {"at": now(), "run_id": OUT.name, "error": repr(exc), "completed_native_calls": len(probe.native),
                "completed_teacher_calls": len(probe.teachers), "teacher_attempts": probe.teacher_attempts,
                "inherited_failed_prefix_native_teacher_calls": [0, 2],
                "no_retry_fallback_other_arm_selection_cap_raise_or_answer_repair": True}
            RunStore.immutable_json(OUT / "failure.json", value)
            RunStore.atomic_json(OUT / "progress.json", {"state": "stopped" if isinstance(exc, InterruptedError) else "failed", **value})
            raise
    else:
        raise ValueError("Explicit prepare, launch or worker required")
