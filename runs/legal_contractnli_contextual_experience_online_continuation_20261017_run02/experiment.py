"""Two forward online batches and retention with complete past-case context."""

# ruff: noqa: E402 -- Run-local frozen research entry, not a new framework.
from __future__ import annotations

import copy
import fcntl
import hashlib
import importlib.util
import io
import json
import os
import signal
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(OUT))

from jsonschema import validate
from representation import (
    CANDIDATE_NOTICE,
    MEMORY_NOTICE,
    TEACHER_SYSTEM,
    compact,
    expanded_memory,
    gold_annotated_view,
    guidance_schema,
    make_catalogue,
    pack_observation,
    scoped_output_schema,
    text_identity,
)

from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.inference.codex_cli_client import (
    CODEX_TURN_INPUT_CHARACTER_LIMIT,
    render_structured_codex_prompt,
)
from legal_skill_guard.inference.native import WireClient
from legal_skill_guard.learning.audit import original_score
from legal_skill_guard.learning.experiment import Comparison, now, points, read, sha
from legal_skill_guard.learning.publication import (
    apply_differential_publication,
    differential_schema,
)
from legal_skill_guard.task import marked_text
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha

PROTOTYPE = ROOT / "runs/legal_contractnli_contextual_experience_online_continuation_20261017_run01"
CONFIG = ROOT / "configs/contractnli_source_programs_completion.json"
PRIOR = ROOT / "runs/legal_contractnli_corrective_evidence_online_continuation_20261017_run01"
AUDIT = PRIOR / "monitoring/complete16_original_author_manual_sets_paired_changes_actual_wires_and_source_uncertainty_audit.json"
TERMINAL_BACKUP = ROOT / "artifacts/corrective_complete16_all490_before_contextual_source_backup_20261017.json"
PRELAUNCH_BACKUP = ROOT / "artifacts/contextual_experience_prelaunch_all_bindings_backup_20261017.json"
HELPER = ROOT / "runs/legal_contractnli_native_grounded_fixed_tool_continuation_20261017_run02/experiment.py"
spec = importlib.util.spec_from_file_location("frozen_ordinary_M2_compact_helpers", HELPER)
SOURCE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(SOURCE)
ARMS = ("empty", "joint")


def author_train(cfg):
    assert sha(ROOT / cfg["source_archive"]) == cfg["source_archive_sha256"]
    with zipfile.ZipFile(ROOT / cfg["source_archive"]) as archive:
        return json.loads(archive.read("contract-nli/train.json"))


def actual_observation(raw, row, libraries, encoding):
    body = json.loads(raw["calls"][0]["request"]["messages"][1]["content"])
    assert body["full_contract_with_original_span_markers"] == marked_text(row)
    bank = raw["published_library"]
    digest = csha(bank)
    libraries[digest] = bank
    candidates = {}
    for h, question in body["hypotheses"].items():
        candidates[h] = copy.deepcopy(question["fallible_evidence_candidates"])
        for item in candidates[h]:
            i = item["original_span_index"]
            assert body["ordinary_candidate_original_text"][str(i)] == row["text"][slice(*row["spans"][i])]
    return {"document_id": row["id"], "actual_stage": raw["stage"],
        "actual_serving_format": encoding, "actual_library_sha256": digest,
        "actual_ordinary_model_state": raw["actual_factual_trace"]["ordinary_model_state"],
        "actual_native_response": {k: raw["response"][k] for k in ("raw_id", "finish_reason", "content")},
        "all_actual_visible_ordinary_candidates": candidates,
        "all_actual_observed_program_receipts": {}}


class Study(Comparison):
    def __init__(self, preparing=False):
        self.cfg = {**read(CONFIG), "run_id": OUT.name, "planned_new_native_calls": 40,
            "planned_new_teacher_calls": 2, "memory_representation": "full_past_context_original_annotations_v1",
            "method_protocol": str(OUT / "PROTOCOL.md")}
        self.bindings = read(AUDIT)["bindings"] if preparing else read(OUT / "registration.json")["files"]
        self.out, self.run_id = OUT, OUT.name
        self.native, self.teachers, self.teacher_attempts, self.current_batch, self.stop = [], [], 0, 6, False
        self.answers, self.seen, self.phase_results = [], {}, {}
        self.meter = WireClient(self.cfg["generation"])
        self.labels = read(ROOT / self.cfg["input_packet"])["public_hypotheses"]
        author = author_train(self.cfg)
        assert self.labels == author["labels"]
        self.author_rows = {r["id"]: r for r in author["documents"]}
        self.initial_ids = self.cfg["training_ids"] + self.cfg["expected_later_ids"]
        self.past_ids = list(self.initial_ids)
        self.model, self.manifest = SOURCE.CORE.load_model(self.cfg)
        self.render = SOURCE.CORE.renderer(self.cfg, self.labels, self.meter)
        if preparing:
            self.source_rows, self.selection = {}, {}
        else:
            self.source_rows = {r["id"]: r for r in read(OUT / "inference_sources_without_Gold.json")["documents"]}
            self.selection = read(OUT / "source_exposure_selection.json")
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: setattr(self, "stop", True))

    def memory_capacity(self, memory):
        references = {h: [{"id": s["id"]} for s in memory["published_contextual_skills"]
            if h in s["hypothesis_ids"]] for h in self.labels}
        return {"master_tokens": self.meter.token_count(text=compact(memory)),
            "scoped_tokens": self.meter.token_count(text=compact({**memory, "applicable_published_skills": references}))}

    def compile(self, stage, arm, doc, bank, catalogue):
        row = SOURCE.CORE.NoGold(self.source_rows[doc])
        messages0, schema0, trace = SOURCE.compact_payload(self.render, self.cfg, self.labels,
            row, "ordinary_memory", [], self.model, self.manifest["state_sha256"])
        original = json.loads(messages0[1]["content"])
        memory, excluded = expanded_memory(bank, catalogue, row["text"], arm)
        body = {**memory, **copy.deepcopy(original)}
        references = {}
        cards = memory["published_contextual_skills"]
        for h in self.labels:
            refs = [{"id": s["id"]} for s in cards if h in s["hypothesis_ids"]]
            references[h] = body["hypotheses"][h]["applicable_published_skills"] = refs
        restored = copy.deepcopy(body)
        for k in memory:
            del restored[k]
        for h in self.labels:
            restored["hypotheses"][h]["applicable_published_skills"] = original["hypotheses"][h]["applicable_published_skills"]
        assert compact(restored) == messages0[1]["content"]
        assert list(body)[:2] == ["published_contextual_skills", "past_context_complete_demonstrations"]
        capacity = self.memory_capacity(memory)
        assert max(capacity.values()) <= self.cfg["library_token_hard_cap"]
        schema = scoped_output_schema(schema0, cards, self.labels)
        assert body["output_contract"]["fields_in_order"] == ["choice", "spans", "reason", "used_skill_ids"]
        messages = [{"role": "system", "content": self.cfg["bundled_solver_system"] + CANDIDATE_NOTICE + MEMORY_NOTICE},
            {"role": "user", "content": compact(body)}]
        tokens = self.meter.token_count(messages=messages)
        assert tokens + self.cfg["generation"]["max_tokens"] <= self.cfg["generation"]["context_tokens"]
        return {"stage": stage, "arm": arm, "document_id": doc, "messages": messages, "schema": schema,
            "prompt_tokens": tokens, "messages_sha256": csha(messages), "schema_sha256": csha(schema),
            "published_library": memory, "actual_factual_trace": {
                "ordinary_model_state": self.manifest["state_sha256"],
                "ordinary_source_facts_built_without_current_Gold": trace,
                "actual_contextual_memory": {**capacity, "memory_sha256": csha(memory),
                    "same_text_example_refs_excluded_to_prevent_answer_leakage": excluded,
                    "current_source_text_sha256": text_identity(row["text"]),
                    "scope_references": references}},
            "all_original_nonmemory_data_roundtrips_byte_identically": True}

    def teacher_body(self, parent, catalogue, history, stage):
        visible_ids = [int(v) for v in catalogue["documents"]]
        rows = [self.author_rows[d] for d in visible_ids]
        observations = [o for o in history["actual_own_public_observations"] if o["document_id"] in visible_ids]
        assert {o["document_id"] for o in observations} == set(visible_ids)
        library_ids = {o["actual_library_sha256"] for o in observations}
        visible_libraries = {h: history["observed_libraries"][h] for h in sorted(library_ids)}
        if stage == "B7":
            assert set(self.selection["B6"]) <= set(visible_ids)
            assert all(int(ref.split(":")[0]) in visible_ids
                for s in parent for ref in s["guidance"]["historical_example_refs"])
        memory, _ = expanded_memory(parent, catalogue, None, "joint")
        body = {"public_hypotheses": self.labels, "current_parent_library": parent,
            "parent_new_representation_capacity_not_assumed_to_fit": self.memory_capacity(memory),
            "stage": stage, "observed_libraries": visible_libraries,
            "actual_seen_history_source_ids": list(self.past_ids),
            "visible_teacher_source_ids": visible_ids,
            "packet_policy": "initial_all32" if stage == "B6" else "complete_current8_plus_all_parent_example_case_sources",
            "original_seen_TRAIN_sources": [{"document_id": r["id"],
                "full_original_contract_with_TRAIN_Gold_tags": gold_annotated_view(r, self.labels),
                "all_original_annotations": r["annotation_sets"][0]["annotations"]} for r in rows],
            "actual_own_public_observations_one_copy": [pack_observation(o, self.author_rows[o["document_id"]]) for o in observations],
            "full_case_costs_paid_once_across_references": {d: {k: v for k, v in item.items()
                if k in ("text_sha256", "whole_marked_source_native_tokens")} for d, item in catalogue["documents"].items()},
            "past_hypothesis_refs_and_component_feedback": catalogue["references"],
            "runtime_common_system": self.cfg["bundled_solver_system"] + CANDIDATE_NOTICE + MEMORY_NOTICE,
            "memory_token_hard_cap": 4096, "target_expanded_total_tokens": 2800,
            "only_own_observations_no_other_arm_answers_or_private_reasoning": True,
            "future_stage_sources_and_Gold_not_supplied": True,
            "training_failure_modes_to_repair": [
                "Class decisions can contradict an already correct inspection and erase true evidence through NM; do not equate missing retrieval or a familiar pattern with absence.",
                "Union-only local examples omitted decision-bearing trigger context. Full original past context must accompany every selected answer, including NM.",
                "A positive cue is not automatically necessary: preserve semantic equivalence, incorporated definitions, universal exceptions and complete responsive evidence without blanket genre exclusions."]}
        chars = len(render_structured_codex_prompt(TEACHER_SYSTEM, compact(body)))
        assert chars <= CODEX_TURN_INPUT_CHARACTER_LIMIT, (stage, chars)
        return body, chars

    def preserve_phase(self, stage, phase_path):
        receipt = read(PRELAUNCH_BACKUP)
        assert sha(receipt["archive"]) == receipt["archive_sha256"]
        with tarfile.open(receipt["archive"], "r:gz") as archive:
            bundle = archive.extractfile("repository.bundle").read()
        assert hashlib.sha256(bundle).hexdigest() == receipt["git_bundle_sha256"]
        paths = {Path(p).resolve() for p in self.bindings}
        paths.update([OUT / "registration.json", phase_path, PRELAUNCH_BACKUP])
        data = {"project/" + str(p.relative_to(ROOT)): p.read_bytes() for p in paths}
        data["repository.bundle"] = bundle
        manifest = {"at": now(), "prelaunch_git_HEAD": receipt["git_HEAD"],
            "phase": stage, "actual_native_teacher_calls_before_phase": [len(self.native), len(self.teachers)],
            "member_sha256": {p: hashlib.sha256(v).hexdigest() for p, v in data.items()}}
        data["SNAPSHOT_MANIFEST.json"] = json.dumps(manifest, ensure_ascii=False, indent=2).encode()
        target = Path('/media/sangfor/vdb/legal-skill-backups') / f"{OUT.name}-{stage}-actual-teacher-before-native.tar.gz"
        with target.open("xb") as output:
            with tarfile.open(fileobj=output, mode="w:gz", compresslevel=3) as archive:
                for name, value in sorted(data.items()):
                    info = tarfile.TarInfo(name)
                    info.size = len(value)
                    archive.addfile(info, io.BytesIO(value))
        seen = set()
        with tarfile.open(target, "r|gz") as archive:
            for member in archive:
                assert member.name not in seen
                assert hashlib.sha256(archive.extractfile(member).read()).hexdigest() == hashlib.sha256(data[member.name]).hexdigest()
                seen.add(member.name)
        assert seen == set(data)
        RunStore.immutable_json(OUT / f"{stage}_actual_teacher_and_inputs_preserved.json", {
            "at": now(), "archive": str(target), "archive_sha256": sha(target), "members": len(data),
            "prelaunch_git_HEAD": receipt["git_HEAD"], "all_members_verified": True,
            "same_vdb_not_offsite_model_or_auth_backup": True})

    def publish(self, stage, parent, catalogue, value):
        bank = apply_differential_publication(parent, value, self.labels, list(map(int, catalogue["documents"])),
            guidance_schema=guidance_schema(catalogue))
        for op in value["operations"]:
            if op["skill"] is not None:
                assert all(catalogue["references"][r]["source_case_id"] in op["source_case_ids"]
                    for r in op["skill"]["guidance"]["historical_example_refs"])
        memory, _ = expanded_memory(bank, catalogue, None, "joint")
        capacity = self.memory_capacity(memory)
        assert max(capacity.values()) <= self.cfg["library_token_hard_cap"]
        pub = OUT / f"publications/{stage}.json"
        RunStore.immutable_json(pub, {"at": now(), "actual_teacher_value": value,
            "parent_library": parent, "publication": bank, "full_runtime_memory_without_same_case_exclusions": memory,
            "full_expanded_capacity": capacity, "all_structurally_valid_edits_used_no_effect_gate": True})
        order = [(stage, arm, doc) for i, doc in enumerate(self.selection[stage])
            for arm in (ARMS if i % 2 == 0 else ARMS[::-1])]
        if stage == "B7":
            order.extend(("B7_retention", "joint", doc) for doc in self.selection["B6"])
        entries = []
        for label, arm, doc in order:
            payload = self.compile(label, arm, doc, bank, catalogue)
            path = OUT / f"prospective/{label}/{arm}/{doc}.json"
            RunStore.immutable_json(path, payload)
            entries.append({"stage": label, "arm": arm, "document_id": doc, "path": str(path),
                "sha256": sha(path), "prompt_tokens": payload["prompt_tokens"]})
        extra = [pub, *[Path(e["path"]) for e in entries], *[p for p in (OUT / "teacher").rglob("*.json")]]
        self.bindings = {**self.bindings, **{str(p): sha(p) for p in extra}}
        phase_path = OUT / f"{stage}_post_teacher_frozen_inputs.json"
        RunStore.immutable_json(phase_path, {"at": now(), "files": self.bindings,
            "ordered_requests": entries, "all_full_inputs_fit_before_phase_generation": True})
        self.preserve_phase(stage, phase_path)
        return bank, entries

    def generate_entry(self, entry):
        payload = read(entry["path"])
        key = csha({"messages": payload["messages"], "schema": payload["schema"], "generation": self.cfg["generation"]})
        dest = OUT / f"native/{entry['stage']}/{entry['arm']}/{entry['document_id']}.native.json"
        if key in self.seen:
            path = self.seen[key]
            RunStore.immutable_json(dest.with_suffix(".reference.json"), {
                "raw_artifact": str(path), "exact_full_request_sha256": key,
                "not_new_generation_or_independent_repeat": True})
        else:
            self.call(dest, payload["messages"], payload["schema"], self.cfg["generation"]["max_tokens"],
                {k: payload[k] for k in ("stage", "arm", "document_id", "published_library", "actual_factual_trace")}
                | {"call_role": "final"})
            raw = self.native[-1]
            if raw["response"]["finish_reason"] != "stop":
                raise InterruptedError("Incomplete native output retained; no retry")
            validate(json.loads(raw["response"]["content"]), payload["schema"])
            path = self.seen[key] = dest
        self.answers.append({"stage": entry["stage"], "arm": entry["arm"],
            "document_id": entry["document_id"], "path": str(path), "prospective": entry["path"]})

    def scored_units(self, answers):
        groups = {}
        for item in answers:
            raw, row = read(item["path"]), self.author_rows[item["document_id"]]
            value = original_score(raw["response"], row, row["annotation_sets"][0]["annotations"], list(self.labels))
            assert value["public_valid"]
            groups.setdefault(item["arm"], []).append({"document_id": row["id"],
                "response": raw["response"], **value})
        return groups

    def score_stage(self, stage):
        answers = [a for a in self.answers if a["stage"] == stage]
        assert len(answers) == 16
        groups = self.scored_units(answers)
        value = {"at": now(), "stage": stage, "all16_saved_before_paired_quality_scoring": True,
            "metrics": {arm: points(units) for arm, units in groups.items()},
            "all_units": groups, "actual_answers": answers, "same_fixed_ordinary_M2_not_strong_empty": True}
        RunStore.immutable_json(OUT / f"stage_results/{stage}.json", value)
        self.phase_results[stage] = value

    def execute(self):
        self.check()
        history, parent = read(OUT / "initial_history.json"), read(OUT / "parent_library.json")
        for number, stage in [(6, "B6"), (7, "B7")]:
            self.current_batch = number
            if stage == "B6":
                catalogue = read(OUT / "learning_inputs/B6_catalogue.json")
            else:
                own = [a for a in self.answers if a["stage"] == "B6" and a["arm"] == "joint"]
                assert len(own) == 8
                for item in own:
                    row = self.author_rows[item["document_id"]]
                    history["actual_own_public_observations"].append(actual_observation(read(item["path"]), row,
                        history["observed_libraries"], "full_past_context_original_annotations_v1"))
                self.past_ids.extend(self.selection["B6"])
                replay_ids = {int(ref.split(":")[0]) for s in parent
                    for ref in s["guidance"]["historical_example_refs"]}
                visible_ids = [d for d in self.past_ids if d in replay_ids or d in self.selection["B6"]]
                visible_observations = [o for o in history["actual_own_public_observations"]
                    if o["document_id"] in visible_ids]
                catalogue = make_catalogue([self.author_rows[d] for d in visible_ids], self.labels,
                    visible_observations, self.meter)
                RunStore.immutable_json(OUT / "learning_inputs/B7_full_actual_history_archive.json", history)
                body, chars = self.teacher_body(parent, catalogue, history, stage)
                RunStore.immutable_json(OUT / "learning_inputs/B7_catalogue.json", catalogue)
                RunStore.immutable_json(OUT / "learning_inputs/B7_teacher_input.json", body)
                RunStore.immutable_json(OUT / "learning_inputs/B7_teacher_schema.json", differential_schema(
                    self.labels, parent, visible_ids, guidance_schema=guidance_schema(catalogue)))
                RunStore.immutable_json(OUT / "learning_inputs/B7_roundtrip_receipt.json", {
                    "at": now(), "teacher_characters": chars, "actual_seen_history_sources": self.past_ids,
                    "visible_teacher_sources": visible_ids,
                    "all_current8_and_parent_example_full_sources_no_B7_or_other_arm_answers": True,
                    "explicit_bounded_replay_not_lossless_all40_teacher_input": True})
                paths = list((OUT / "learning_inputs").glob("B7_*.json"))
                paths.extend(Path(a["path"]) for a in self.answers)
                paths.append(OUT / "stage_results/B6.json")
                self.bindings = {**self.bindings, **{str(p): sha(p) for p in paths}}
            value = self.teacher_call("update_to_" + stage, TEACHER_SYSTEM,
                read(OUT / f"learning_inputs/{stage}_teacher_input.json"),
                read(OUT / f"learning_inputs/{stage}_teacher_schema.json"))
            parent, entries = self.publish(stage, parent, catalogue, value)
            self.progress("acquiring_shared_GPU_lease", current_arm=stage)
            with (ROOT / "artifacts/gpu_generation.lock").open("a+") as lock:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
                for entry in entries:
                    self.check()
                    self.generate_entry(entry)
            self.score_stage(stage)
        self.finish()

    def finish(self):
        assert len(self.answers) == 40 and len(self.teachers) == self.teacher_attempts == 2
        forward = self.scored_units([a for a in self.answers if a["stage"] in ("B6", "B7")])
        retention = self.scored_units([a for a in self.answers if a["stage"] == "B7_retention"])
        assert len(retention["joint"]) == 8
        result = {"at": now(), "run_id": self.run_id, "actual_new_native_teacher_calls": [len(self.native), 2],
            "logical_answers": 40, "forward_metrics": {arm: points(u) for arm, u in forward.items()},
            "B6_retention_before": self.phase_results["B6"]["metrics"]["joint"],
            "B6_retention_after": points(retention["joint"]), "retention_units": retention,
            "phase_metrics": {s: v["metrics"] for s, v in self.phase_results.items()},
            "actual_answer_references": self.answers,
            "new_native_usage": {k: sum(r["response"][k] for r in self.native) for k in ("prompt_tokens", "completion_tokens")},
            "new_teacher_invocations": [{"name": t["name"], "invocation": t["invocation"]} for t in self.teachers],
            "shared_upstream_costs_not_free_or_independent": str(PRIOR / "completion.json"),
            "not_formal_full_training_independent_learning_mature_comparison_or_TEST": True}
        self.check()
        RunStore.immutable_json(OUT / "completion.json", result)
        RunStore.atomic_json(OUT / "progress.json", {"at": now(), "run_id": self.run_id, "state": "completed",
            "completed_native_calls": len(self.native), "completed_teacher_calls": 2, "logical_answers": 40})
        print(compact({"forward_metrics": result["forward_metrics"], "new_calls": result["actual_new_native_teacher_calls"]}))


def prepare():
    assert not (OUT / "registration.json").exists()
    assert read(PRIOR / "progress.json")["state"] == "completed"
    assert not Path('/proc', str(read(PRIOR / "launch.json")["pid"])).exists()
    receipt = read(TERMINAL_BACKUP)
    assert receipt["complete_new_native_teacher_calls"] == [16, 1]
    assert sha(receipt["archive"]) == receipt["archive_sha256"]
    study = Study(preparing=True)
    study.check()
    prior_body = read(PRIOR / "teacher_input.json")
    history = {"observed_libraries": copy.deepcopy(prior_body["observed_libraries"]),
        "actual_own_public_observations": copy.deepcopy(prior_body["actual_own_public_observations"])}
    for doc in study.cfg["expected_later_ids"]:
        history["actual_own_public_observations"].append(actual_observation(
            read(PRIOR / f"native/joint/{doc}.native.json"), study.author_rows[doc],
            history["observed_libraries"], "past_member_corrective_examples_v1"))
    assert len(history["actual_own_public_observations"]) == 32
    parent = read(PRIOR / "publication.json")["publication_with_training_only_refs"]
    catalogue = make_catalogue([study.author_rows[d] for d in study.past_ids], study.labels,
        history["actual_own_public_observations"], study.meter)
    body, chars = study.teacher_body(parent, catalogue, history, "B6")
    assert read(PROTOTYPE / "progress.json")["state"] == "cancelled_before_launch"
    assert not (PROTOTYPE / "launch.json").exists()
    study.selection = read(PROTOTYPE / "source_exposure_selection.json")
    docs = study.selection["B6"] + study.selection["B7"]
    sources = [{k: study.author_rows[d][k] for k in ("id", "text", "spans")} for d in docs]
    study.source_rows = {r["id"]: r for r in sources}
    previews = [study.compile("B6" if d in study.selection["B6"] else "B7", "empty", d, parent, catalogue) for d in docs]
    schema = differential_schema(study.labels, parent, study.past_ids, guidance_schema=guidance_schema(catalogue))
    writes = {"source_exposure_selection.json": study.selection,
        "inference_sources_without_Gold.json": {"documents": sources}, "initial_history.json": history,
        "initial_seen_TRAIN.json": {"documents": [study.author_rows[d] for d in study.past_ids]},
        "parent_library.json": parent, "learning_inputs/B6_catalogue.json": catalogue,
        "learning_inputs/B6_teacher_input.json": body, "learning_inputs/B6_teacher_schema.json": schema}
    for name, value in writes.items():
        RunStore.immutable_json(OUT / name, value)
    paths = [Path(__file__), OUT / "representation.py", OUT / "PROTOCOL.md", AUDIT, TERMINAL_BACKUP,
        PRIOR / "teacher_input.json", PRIOR / "publication.json", PRIOR / "completion.json",
        *[p for p in PROTOTYPE.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"],
        *[OUT / name for name in writes]]
    registration = {"at": now(), "files": {**study.bindings, **{str(p): sha(p) for p in paths}},
        "teacher_characters_B6": chars, "initial_seen_sources": study.initial_ids,
        "fresh_forward_sources_relative_to_current_project": {s: study.selection[s] for s in ("B6", "B7")},
        "planned_max_native_teacher_calls": [40, 2], "planned_logical_answers": 40,
        "all32_own_observations_original_sources_and_reference_encoding_roundtrip_verified": True,
        "all16_empty_full_inputs_fit_not_proof_future_teacher_bank_fits": [
            {"document_id": p["document_id"], "prompt_tokens": p["prompt_tokens"]} for p in previews],
        "preparation_generation_teacher_new_fit_calls": [0, 0, 0],
        "initial_schema_references_include_genuine_full_context_NM": sum(
            v["original_relation"] == "NotMentioned" for v in catalogue["references"].values()),
        "preselection_reused_verbatim_from_zero_call_prototype_without_resampling": str(PROTOTYPE),
        "not_formal_TEST_or_independent_learning_repeat": True}
    RunStore.immutable_json(OUT / "registration.json", registration)
    print(compact({k: v for k, v in registration.items() if k != "files"}))


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
        RunStore.immutable_json(OUT / "launch.json", {"at": now(), "pid": child.pid,
            "actual_argv": argv, "background_independent_of_conversation": True})
        print(compact({"run_id": OUT.name, "pid": child.pid}))
    elif command == "worker":
        study = Study()
        try:
            study.execute()
        except BaseException as exc:
            value = {"at": now(), "run_id": OUT.name, "error": repr(exc),
                "completed_native_calls": len(study.native), "completed_teacher_calls": len(study.teachers),
                "teacher_attempts": study.teacher_attempts, "logical_answers": len(study.answers),
                "no_retry_fallback_repair_admission_or_best_bank_selection": True}
            RunStore.immutable_json(OUT / "failure.json", value)
            RunStore.atomic_json(OUT / "progress.json", {"state": "stopped" if isinstance(exc, InterruptedError) else "failed", **value})
            raise
    else:
        raise ValueError("Explicit prepare, launch or worker required")
