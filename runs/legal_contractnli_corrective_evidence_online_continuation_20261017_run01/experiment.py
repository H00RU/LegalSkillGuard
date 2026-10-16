"""B4 error-grounded online update followed by the preselected next eight sources."""

# ruff: noqa: E402 -- Immutable run-local entry; no production framework added.
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
    example_catalogue,
    expanded_library,
    gold_annotated_view,
    guidance_schema,
    scoped_output_schema,
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
from legal_skill_guard.task import marked_text, render_library
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha

PARENT = ROOT / "runs/legal_contractnli_native_grounded_fixed_tool_continuation_20261017_run02"
CONFIG = ROOT / "configs/contractnli_source_programs_completion.json"
PREVIOUS = ROOT / "runs/legal_contractnli_evidence_anchored_skill_mechanism_20261017_run01"
AUDIT = PREVIOUS / "monitoring/complete24_original_author_manual_sets_native_wires_all5_contrasts_and_source_uncertainty_audit.json"
TERMINAL_BACKUP = ROOT / "artifacts/anchored_complete24_all442_before_corrective_source_backup_20261017.json"
PRELAUNCH_BACKUP = ROOT / "artifacts/corrective_episode_continuation_prelaunch_all_bindings_backup_20261017.json"
DOCS = read(CONFIG)["expected_later_ids"]
ARMS = ("empty", "joint")
spec = importlib.util.spec_from_file_location("frozen_own_observation_reader", PARENT / "experiment.py")
SOURCE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(SOURCE)


def ordered_pairs():
    return [(arm, doc) for i, doc in enumerate(DOCS)
        for arm in (ARMS if i % 2 == 0 else ARMS[::-1])]


class Study(Comparison):
    def __init__(self, preparing=False):
        self.cfg = {**read(CONFIG), "run_id": OUT.name,
            "planned_new_native_calls": 16, "planned_new_teacher_calls": 1,
            "memory_representation": "past_member_corrective_examples_v1",
            "method_protocol": str(OUT / "PROTOCOL.md")}
        self.bindings = read(AUDIT)["bindings"] if preparing else read(OUT / "registration.json")["files"]
        self.out, self.run_id = OUT, OUT.name
        self.native, self.teachers, self.teacher_attempts, self.current_batch, self.stop = [], [], 0, 5, False
        self.meter = WireClient(self.cfg["generation"])
        self.labels = read(ROOT / self.cfg["input_packet"])["public_hypotheses"]
        self.catalogue = {} if preparing else read(OUT / "past_example_catalogue.json")
        self.answers = []
        self.source_rows = {} if preparing else {v["id"]: v for v in read(OUT / "inference_sources_without_Gold.json")["documents"]}
        self.model, self.manifest = SOURCE.CORE.load_model(self.cfg)
        self.render = SOURCE.CORE.renderer(self.cfg, self.labels, self.meter)
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: setattr(self, "stop", True))

    def compile(self, arm, doc, bank):
        row = SOURCE.CORE.NoGold(self.source_rows[doc])
        messages0, schema0, trace = SOURCE.compact_payload(
            self.render, self.cfg, self.labels, row, "ordinary_memory", [],
            self.model, self.manifest["state_sha256"])
        original = json.loads(messages0[1]["content"])
        assert "published_source_programs" not in original and "source_program_query_receipts" not in original
        runtime = expanded_library(bank, self.catalogue, arm)
        body = copy.deepcopy(original)
        body["published_evidence_anchored_skills"] = runtime
        references = {}
        for h, question in body["hypotheses"].items():
            ids = [s["id"] for s in runtime if h in s["hypothesis_ids"]]
            references[h] = [{"id": sid} for sid in ids]
            question["applicable_published_skills"] = references[h]
        restored = copy.deepcopy(body)
        del restored["published_evidence_anchored_skills"]
        for h in self.labels:
            restored["hypotheses"][h]["applicable_published_skills"] = original["hypotheses"][h]["applicable_published_skills"]
        assert restored == original
        assert json.dumps(restored, ensure_ascii=False, separators=(",", ":")) == messages0[1]["content"]
        schema = scoped_output_schema(schema0, runtime, self.labels)
        fields = body["output_contract"]["fields_in_order"]
        assert fields == ["choice", "spans", "reason", "used_skill_ids"]
        system = self.cfg["bundled_solver_system"] + CANDIDATE_NOTICE + MEMORY_NOTICE
        assert "For each emit " + ", ".join(fields) + " in that order." in system
        master_tokens = self.meter.token_count(text=render_library(runtime))
        scoped_tokens = self.meter.token_count(text=json.dumps({
            "published_evidence_anchored_skills": runtime, "applicable_published_skills": references},
            ensure_ascii=False, separators=(",", ":")))
        assert max(master_tokens, scoped_tokens) <= self.cfg["library_token_hard_cap"]
        messages = [{"role": "system", "content": system},
            {"role": "user", "content": json.dumps(body, ensure_ascii=False, separators=(",", ":"))}]
        tokens = self.meter.token_count(messages=messages)
        assert tokens + self.cfg["generation"]["max_tokens"] <= self.cfg["generation"]["context_tokens"]
        factual = {
            "ordinary_model_state": self.manifest["state_sha256"],
            "ordinary_source_facts_built_without_current_Gold": trace,
            "actual_corrective_evidence_delivery": {
                "published_library_sha256": csha(runtime), "public_scope_references": references,
                "master_tokens": master_tokens, "scoped_tokens": scoped_tokens,
                "past_evidence_corrections_not_current_verdicts": True,
                "learned_query_DSL_not_used": True}}
        return {
            "messages": messages, "schema": schema, "actual_factual_trace": factual,
            "published_library": runtime,
            "ordinary_input_source_artifact": str(OUT / "inference_sources_without_Gold.json"),
            "stage": "corrective_B5", "arm": arm, "document_id": doc, "prompt_tokens": tokens,
            "messages_sha256": csha(messages), "schema_sha256": csha(schema),
            "all_nonmemory_original_source_input_data_roundtrips_byte_identically": True}

    def freeze_after_teacher(self, value):
        schema = read(OUT / "teacher_schema.json")
        bank = apply_differential_publication(read(OUT / "parent_library.json"), value, self.labels, self.cfg["training_ids"][:24],
            guidance_schema=guidance_schema(self.catalogue))
        for op in value["operations"]:
            if op["skill"] is not None:
                refs = op["skill"]["guidance"]["historical_example_refs"]
                assert all(self.catalogue[r]["source_case_id"] in op["source_case_ids"] for r in refs)
        validate(value, schema)
        RunStore.immutable_json(OUT / "publication.json", {"actual_teacher_value": value,
            "publication_with_training_only_refs": bank,
            "actual_runtime_joint_library": expanded_library(bank, self.catalogue, "joint"),
            "all_structurally_valid_output_used_no_effect_gate": True})
        entries = []
        for arm, doc in ordered_pairs():
            payload = self.compile(arm, doc, bank)
            path = OUT / f"prospective/{arm}/{doc}.json"
            RunStore.immutable_json(path, payload)
            entries.append({"arm": arm, "document_id": doc, "path": str(path), "sha256": sha(path),
                "messages_sha256": payload["messages_sha256"], "schema_sha256": payload["schema_sha256"],
                "prompt_tokens": payload["prompt_tokens"]})
        extra = [OUT / "publication.json", *[Path(e["path"]) for e in entries]]
        extra.extend(p for p in (OUT / "teacher").rglob('*.json'))
        self.bindings = {**self.bindings, **{str(p): sha(p) for p in extra}}
        RunStore.immutable_json(OUT / "post_teacher_frozen_inputs.json", {"at": now(),
            "files": self.bindings, "ordered_requests": entries, "all16_fit_before_first_generation": True,
            "actual_teacher_calls": 1, "new_native_calls": 0})
        self.preserve_before_native()
        return entries

    def preserve_before_native(self):
        receipt = read(PRELAUNCH_BACKUP)
        assert sha(receipt["archive"]) == receipt["archive_sha256"]
        with tarfile.open(receipt["archive"], "r:gz") as archive:
            bundle = archive.extractfile("repository.bundle").read()
        assert hashlib.sha256(bundle).hexdigest() == receipt["git_bundle_sha256"]
        paths = {Path(p) for p in self.bindings}
        paths.update([OUT / "registration.json", OUT / "post_teacher_frozen_inputs.json", PRELAUNCH_BACKUP])
        data = {"project/" + str(p.resolve().relative_to(ROOT)): p.read_bytes() for p in paths}
        data["repository.bundle"] = bundle
        manifest = {"at": now(), "source_git_HEAD_prelaunch": receipt["git_HEAD"],
            "member_sha256": {p: hashlib.sha256(v).hexdigest() for p, v in data.items()},
            "actual_new_native_teacher_calls": [0, 1], "planned_logical_native_answers": 16,
            "same_vdb_not_offsite_model_or_auth_backup": True}
        data["SNAPSHOT_MANIFEST.json"] = json.dumps(manifest, ensure_ascii=False, indent=2).encode()
        target = Path('/media/sangfor/vdb/legal-skill-backups') / (OUT.name + "-actual-teacher-before-native.tar.gz")
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
                assert hashlib.sha256(archive.extractfile(member).read()).digest() == hashlib.sha256(data[member.name]).digest()
                seen.add(member.name)
        assert seen == set(data)
        RunStore.immutable_json(OUT / "actual_teacher_and16_inputs_preserved_before_native.json", {
            "at": now(), "archive": str(target), "archive_sha256": sha(target),
            "members": len(data), "source_git_HEAD_prelaunch": receipt["git_HEAD"],
            "all_member_hashes_and_previously_verified_bundle_preserved": True})

    def execute(self):
        self.check()
        value = self.teacher_call("corrective_B4_update", TEACHER_SYSTEM,
            read(OUT / "teacher_input.json"), read(OUT / "teacher_schema.json"))
        entries = self.freeze_after_teacher(value)
        self.progress("acquiring_shared_GPU_lease")
        with (ROOT / "artifacts/gpu_generation.lock").open("a+") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            self.check()
            seen = {}
            for entry in entries:
                payload = read(Path(entry["path"]))
                key = csha({"messages": payload["messages"], "schema": payload["schema"], "generation": self.cfg["generation"]})
                dest = OUT / f"native/{entry['arm']}/{entry['document_id']}.native.json"
                if key in seen:
                    path = seen[key]
                    RunStore.immutable_json(dest.with_suffix(".reference.json"), {
                        "target_arm": entry["arm"], "document_id": entry["document_id"],
                        "raw_artifact": str(path), "exact_full_request_sha256": key,
                        "not_new_generation_or_independent_repeat": True})
                else:
                    self.call(dest, payload["messages"], payload["schema"], self.cfg["generation"]["max_tokens"], {
                        k: payload[k] for k in ("stage", "arm", "document_id", "actual_factual_trace", "published_library", "ordinary_input_source_artifact")}
                        | {"call_role": "final"})
                    path = dest
                    raw = self.native[-1]
                    if raw["response"]["finish_reason"] != "stop":
                        raise InterruptedError("Incomplete native output saved; no retry")
                    validate(json.loads(raw["response"]["content"]), payload["schema"])
                    seen[key] = path
                self.answers.append({"arm": entry["arm"], "document_id": entry["document_id"], "path": str(path)})
            self.finish()

    def finish(self):
        assert len(self.answers) == 16 and len(self.teachers) == self.teacher_attempts == 1
        assert sha(ROOT / self.cfg["source_archive"]) == self.cfg["source_archive_sha256"]
        with zipfile.ZipFile(ROOT / self.cfg["source_archive"]) as archive:
            author = json.loads(archive.read("contract-nli/train.json"))
        rows = {r["id"]: r for r in author["documents"]}
        groups = {arm: [] for arm in ARMS}
        for item in self.answers:
            raw, row = read(Path(item["path"])), rows[item["document_id"]]
            scored = original_score(raw["response"], row, row["annotation_sets"][0]["annotations"], list(author["labels"]))
            if scored["public_valid"]:
                validate(scored["parsed"], raw["calls"][0]["request"]["response_format"]["json_schema"]["schema"])
            groups[item["arm"]].append({"document_id": row["id"], "response": raw["response"], **scored})
        self.check()
        result = {"at": now(), "run_id": self.run_id, "new_native_teacher_calls": [len(self.native), 1],
            "logical_answers": 16, "all_new_outputs_saved_before_quality_scoring": True,
            "metrics": {arm: points(units) for arm, units in groups.items()}, "all_units": groups,
            "actual_answer_references": self.answers,
            "new_native_usage": {k: sum(r["response"][k] for r in self.native) for k in ("prompt_tokens", "completion_tokens")},
            "new_teacher_invocations": [{"name": t["name"], "invocation": t["invocation"]} for t in self.teachers],
            "shared_upstream_costs_not_free_or_independent": str(PREVIOUS / "completion.json"),
            "original_labels_and_full_span_sets_scored_without_repair": True,
            "not_formal_TEST_or_independent_learning_or_method_win": True}
        RunStore.immutable_json(OUT / "completion.json", result)
        RunStore.atomic_json(OUT / "progress.json", {"at": now(), "run_id": self.run_id, "state": "completed",
            "completed_native_calls": len(self.native), "completed_teacher_calls": 1, "logical_answers": 16})
        print(json.dumps({"metrics": result["metrics"], "new_calls": result["new_native_teacher_calls"]}))


def latest_B4_observation(raw, row, libraries):
    body = json.loads(raw["calls"][0]["request"]["messages"][1]["content"])
    bank = raw["published_library"]
    digest = csha(bank)
    libraries[digest] = bank
    candidates = {}
    for h, question in body["hypotheses"].items():
        candidates[h] = copy.deepcopy(question["fallible_evidence_candidates"])
        for c in candidates[h]:
            i = c["original_span_index"]
            assert body["ordinary_candidate_original_text"][str(i)] == row["text"][slice(*row["spans"][i])]
    return {
        "document_id": row["id"], "actual_stage": raw["stage"],
        "actual_serving_format": "gold_only_evidence_anchors_v1",
        "actual_library_sha256": digest,
        "actual_ordinary_model_state": raw["actual_factual_trace"]["ordinary_model_state"],
        "actual_native_response": {k: raw["response"][k] for k in ("raw_id", "finish_reason", "content")},
        "all_actual_visible_ordinary_candidates": candidates,
        "all_actual_observed_program_receipts": {},
    }


def prepare():
    assert not (OUT / "registration.json").exists()
    assert read(PREVIOUS / "progress.json")["state"] == "completed"
    assert not Path("/proc", str(read(PREVIOUS / "launch.json")["pid"])).exists()
    saved = read(TERMINAL_BACKUP)
    assert saved["complete_new_native_teacher_calls"] == [24, 1]
    assert sha(saved["archive"]) == saved["archive_sha256"]
    study = Study(preparing=True)
    study.check()
    packet = read(ROOT / study.cfg["input_packet"])
    rows = packet["training"][:24]
    assert [row["id"] for row in rows] == study.cfg["training_ids"][:24]
    assert not set(DOCS) & {row["id"] for row in rows}
    assert sha(ROOT / study.cfg["source_archive"]) == study.cfg["source_archive_sha256"]
    with zipfile.ZipFile(ROOT / study.cfg["source_archive"]) as archive:
        author = json.loads(archive.read("contract-nli/train.json"))
    originals = {v["id"]: v for v in author["documents"]}
    for row in rows:
        actual = originals[row["id"]]
        assert (row["text"], row["spans"], row["annotation_sets"]) == (
            actual["text"], actual["spans"], actual["annotation_sets"])
    sources = [{key: originals[d][key] for key in ("id", "text", "spans")} for d in DOCS]
    assert all("annotation_sets" not in row for row in sources)
    RunStore.immutable_json(OUT / "inference_sources_without_Gold.json", {
        "documents": sources, "previously_preselected_exposed_development_ids_not_TEST": DOCS})
    study.source_rows = {v["id"]: v for v in sources}
    prior_input = read(PREVIOUS / "teacher_input.json")
    libraries = copy.deepcopy(prior_input["observed_libraries"])
    observations = copy.deepcopy(prior_input["actual_own_public_observations"])
    raw_paths = []
    for row in rows[18:24]:
        path = PREVIOUS / f"native/joint/{row['id']}.native.json"
        raw = read(path)
        assert raw["document_id"] == row["id"] and raw["arm"] == "joint"
        observations.append(latest_B4_observation(raw, row, libraries))
        raw_paths.append(path)
    assert len(observations) == len({o["document_id"] for o in observations}) == 24
    study.catalogue = example_catalogue(rows, study.labels, study.meter, observations)
    RunStore.immutable_json(OUT / "past_example_catalogue.json", study.catalogue)
    parent = read(PREVIOUS / "publication.json")["publication_with_training_only_refs"]
    RunStore.immutable_json(OUT / "parent_library.json", parent)
    expanded = expanded_library(parent, study.catalogue, "joint")
    scope = {h: [{"id": skill["id"]} for skill in expanded if h in skill["hypothesis_ids"]] for h in study.labels}
    parent_capacity = {
        "master_tokens": study.meter.token_count(text=render_library(expanded)),
        "scoped_tokens": study.meter.token_count(text=json.dumps({
            "published_evidence_anchored_skills": expanded, "applicable_published_skills": scope},
            ensure_ascii=False, separators=(",", ":")))}
    assert max(parent_capacity.values()) <= study.cfg["library_token_hard_cap"]
    body = {
        "public_hypotheses": study.labels,
        "current_parent_library": parent,
        "current_parent_corrective_expansion_capacity": parent_capacity,
        "observed_libraries": libraries,
        "all24_original_TRAIN_sources": [{
            "document_id": row["id"],
            "full_original_contract_with_TRAIN_Gold_tags": gold_annotated_view(row, study.labels, marked_text(row)),
            "all_original_annotations": row["annotation_sets"][0]["annotations"]} for row in rows],
        "actual_own_public_observations": observations,
        "past_original_evidence_example_refs": {
            ref: {k: v for k, v in value.items() if k != "runtime_example"}
            for ref, value in study.catalogue.items()},
        "past_training_annotation_conflicts_to_resolve_not_future_case_patches": [
            "Supplied past334/nda18 Gold includes58,65,68; the parent excludes proxy solicitation despite those original member annotations. Preserve corpus evidence rather than imposing an unsupported idealized exclusion.",
            "Supplied past416/nda10 Gold is the complete definition sentence12, not general secrecy13/14. The parent conditionally demands both; distinguish readable source context from unconditional legal-premise completion."],
        "memory_token_hard_cap_including_expanded_examples": 4096,
        "target_expanded_total_tokens": 2800,
        "runtime_common_system": study.cfg["bundled_solver_system"] + CANDIDATE_NOTICE + MEMORY_NOTICE,
        "newest6_own_observations_share_actual_parent4_Gold_only_format": True,
        "new_reference_expansion_is_corrective_not_assumed_behavior_equal_to_old_Gold_only": True,
        "no_next8_text_Gold_other_arms_or_private_reasoning": True,
        "older_actual_banks_tool_states_and_formats_remain_explicit": True,
    }
    chars = len(render_structured_codex_prompt(
        TEACHER_SYSTEM, json.dumps(body, ensure_ascii=False, separators=(",", ":"))))
    assert chars <= CODEX_TURN_INPUT_CHARACTER_LIMIT
    RunStore.immutable_json(OUT / "teacher_input.json", body)
    RunStore.immutable_json(OUT / "teacher_schema.json", differential_schema(
        study.labels, parent, study.cfg["training_ids"][:24],
        guidance_schema=guidance_schema(study.catalogue)))
    previews = [study.compile("empty", d, parent) for d in DOCS]
    paths = [
        Path(__file__), OUT / "representation.py", OUT / "PROTOCOL.md", AUDIT,
        TERMINAL_BACKUP, OUT / "inference_sources_without_Gold.json",
        OUT / "past_example_catalogue.json", OUT / "parent_library.json",
        OUT / "teacher_input.json", OUT / "teacher_schema.json",
        PREVIOUS / "teacher_input.json", PREVIOUS / "publication.json",
        PREVIOUS / "completion.json", *raw_paths]
    RunStore.immutable_json(OUT / "registration.json", {
        "at": now(), "files": {**study.bindings, **{str(p): sha(p) for p in paths}},
        "teacher_prompt_characters": chars,
        "all24_author_sources_Gold_actual_own_observations_and_inline_tags_roundtrip_verified": True,
        "historical_example_refs": len(study.catalogue),
        "local_negative_only_refs": sum(v["component_feedback"]["local_negative_only_without_whole_document_relation"] for v in study.catalogue.values()),
        "planned_new_native_max_teacher_calls": [16, 1],
        "fixed_previously_exposed_next_development_ids": DOCS, "arms": ARMS,
        "initial_parent_corrective_capacity": parent_capacity,
        "empty_full_context_previews_not_proof_future_teacher_bank_fits": [
            {"doc": x["document_id"], "tokens": x["prompt_tokens"]} for x in previews],
        "no_preparation_generations_or_new_fit": True,
        "actual_teacher_and16_inputs_preserved_before_native_by_worker": True,
        "not_formal_TEST_independent_learning_or_full_training_restart": True})
    print(json.dumps({
        "teacher_characters": chars, "example_refs": len(study.catalogue),
        "planned_new_native_max_teacher": [16, 1],
        "parent_actual_corrective_capacity": parent_capacity,
        "preparation_generation_calls": 0}))


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
        study = Study()
        try:
            study.execute()
        except BaseException as exc:
            value = {"at": now(), "run_id": OUT.name, "error": repr(exc),
                "completed_native_calls": len(study.native), "completed_teacher_calls": len(study.teachers),
                "teacher_attempts": study.teacher_attempts, "logical_answers": len(study.answers),
                "no_retry_fallback_repair_effect_admission_or_bank_selection": True}
            RunStore.immutable_json(OUT / "failure.json", value)
            RunStore.atomic_json(OUT / "progress.json", {"state": "stopped" if isinstance(exc, InterruptedError) else "failed", **value})
            raise
    else:
        raise ValueError("Explicit prepare, launch or worker required")
