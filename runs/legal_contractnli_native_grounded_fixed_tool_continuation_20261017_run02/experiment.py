"""Fixed-tool native-feedback continuation with reversible one-copy serving."""

# ruff: noqa: E402 -- Independent frozen run-local entry point.
from __future__ import annotations

import copy
import fcntl
import importlib.util
import json
import os
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
from legal_skill_guard.learning.audit import original_score
from legal_skill_guard.learning.experiment import Comparison, now, points, read, sha
from legal_skill_guard.learning.publication import (
    apply_differential_publication,
    differential_schema,
)
from legal_skill_guard.learning.source_programs import PROGRAM_GUIDANCE_SCHEMA
from legal_skill_guard.task import marked_text
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha

PROTOTYPE = ROOT / "runs/legal_contractnli_native_grounded_fixed_tool_continuation_20261017_run01"
spec = importlib.util.spec_from_file_location("fixed_tool_packet_helpers", PROTOTYPE / "experiment.py")
CORE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(CORE)
PREFIX, CONFIG, TRAIN, TRANSFER = CORE.PREFIX, CORE.CONFIG, CORE.TRAIN, CORE.TRANSFER
ENCODING = "one_copy_candidate_catalogue_and_named_columnar_source_receipts_v1"
NOTICE = (
    " Ordinary candidate original_span_index resolves to exact quoted text in "
    "ordinary_candidate_original_text, shared once across questions; scores and "
    "membership are fallible. The complete original NDA remains above with "
    "unchanged SPAN indices. When published_source_programs exists, its named "
    "records occur once and each question references applicable IDs. "
    "source_program_query_receipts has two NAMED columns per skill: "
    "matched_original_span_indices and possible_list_preamble_links. Each "
    "column's array position is the zero-based source_queries index, including "
    "empty queries. A query returns its direct matches plus the listed possible "
    "preamble indices; these are unverified reading leads, not labels or proven "
    "relevance. No duplicate inline lead tags are inserted in the source. "
    "Read each applicable inspection; another question's test is not yours. "
    "Missing skills or empty hits never establish NotMentioned. Reject noise, "
    "inspect the full NDA and retain all needed original evidence yourself. "
    "Report only IDs actually used; the list may be empty."
)
SYSTEM = CORE.SYSTEM.replace(
    "The one-copy original two-field memory, ordinary candidates, source lead "
    "tags and actual per-query receipts are exactly those in the observations.",
    "The two-field memory/query semantics are unchanged. Actual observation "
    "encodings are explicit: historical inputs used inline tags/literal "
    "repetition; new parent/draft/final inputs share the new reversible format. "
    "The exact serving notice follows: " + NOTICE,
) + (
    " Before this first writer call, the same parent was newly executed on "
    "all six B3 sources under the common compact serving format and fixedM2. "
    "These are real new observations, not assumed behavioral equivalence of "
    "two data-equivalent encodings. The draft and final use that same format."
)


def compact_payload(render, cfg, labels, row, arm, bank, model, state):
    messages, schema, _, trace = render.make_payload(arm, row, bank, model, state)
    original = json.loads(messages[1]["content"])
    body, trace = copy.deepcopy(original), copy.deepcopy(trace)
    catalog = {}
    for question in body["hypotheses"].values():
        for candidate in question["fallible_evidence_candidates"]:
            index = candidate["original_span_index"]
            literal = candidate.pop("literal_original_text")
            assert literal == row["text"][slice(*row["spans"][index])]
            if str(index) in catalog:
                assert catalog[str(index)] == literal
            catalog[str(index)] = literal
    body["ordinary_candidate_original_text"] = {k: catalog[k] for k in sorted(catalog, key=int)}
    body["full_contract_with_original_span_markers"] = marked_text(row)
    delivery = trace["task_local_delivery"]
    old_tags = delivery.get("source_lead_tags_by_original_span", {})
    if bank:
        compact = {}
        for sid, receipts in original["source_program_query_receipts"].items():
            assert [r["query_index"] for r in receipts] == list(range(len(receipts)))
            compact[sid] = {key: [copy.deepcopy(r[key]) for r in receipts] for key in (
                "matched_original_span_indices", "possible_list_preamble_links")}
        body["source_program_query_receipts"] = compact
    # Reconstruct ALL original user-body data; no semantic filtering or union into answers.
    restored = copy.deepcopy(body)
    for question in restored["hypotheses"].values():
        for candidate in question["fallible_evidence_candidates"]:
            candidate["literal_original_text"] = catalog[str(candidate["original_span_index"])]
    del restored["ordinary_candidate_original_text"]
    text = marked_text(row)
    for index, tag in old_tags.items():
        text = text.replace(f"<SPAN {index}>", tag + f"<SPAN {index}>", 1)
    restored["full_contract_with_original_span_markers"] = text
    if bank:
        decoded = {}
        for sid, columns in body["source_program_query_receipts"].items():
            decoded[sid] = []
            for index, (hits, links) in enumerate(zip(columns["matched_original_span_indices"],
                    columns["possible_list_preamble_links"], strict=True)):
                decoded[sid].append({"query_index": index, "matched_original_span_indices": hits,
                    "possible_list_preamble_links": links,
                    "returned_original_span_indices": sorted(set(hits) | {x["possible_preamble_span_index"] for x in links})})
        restored["source_program_query_receipts"] = decoded
    assert restored == original
    delivery["derived_inline_tags_not_served"] = old_tags
    delivery["source_lead_tags_by_original_span"] = {}
    delivery["skill_delivery_encoding"] = ENCODING
    delivery["actual_served_named_columnar_receipts"] = body.get("source_program_query_receipts", {})
    delivery["all_original_user_body_data_roundtrips_not_behavior_invariance"] = True
    messages = copy.deepcopy(messages)
    messages[0]["content"] = cfg["bundled_solver_system"] + NOTICE
    messages[1]["content"] = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    return messages, schema, trace


def observation(record, rows, libraries):
    if record["format"] == "audited_reference_v1":
        ref = read(Path(record["path"]))
        raw = read(Path(record["raw_path"]))
        assert ref["raw_artifact"] == record["raw_path"] and ref["response"] == raw["response"]
        trace = ref["actual_factual_trace"]
    elif record["format"] in ("native_with_trace_v1", ENCODING):
        raw = read(Path(record["path"]))
        trace = raw["actual_factual_trace"]
    else:
        raise ValueError("Explicit original observation format required")
    doc = raw["document_id"]
    assert doc == record["document_id"]
    row = rows[doc]
    body = json.loads(raw["calls"][0]["request"]["messages"][1]["content"])
    bank = raw["published_library"]
    digest = csha(bank)
    libraries[digest] = bank
    candidates = {}
    for h, question in body["hypotheses"].items():
        candidates[h] = []
        for candidate in question["fallible_evidence_candidates"]:
            i = candidate["original_span_index"]
            if record["format"] == ENCODING:
                literal = body["ordinary_candidate_original_text"][str(i)]
                assert "literal_original_text" not in candidate
            else:
                literal = candidate["literal_original_text"]
            assert literal == row["text"][slice(*row["spans"][i])]
            candidates[h].append({k: v for k, v in candidate.items() if k != "literal_original_text"})
    events = trace["task_local_delivery"]["source_program_execution_by_skill"]
    return {"document_id": doc, "actual_stage": raw["stage"],
        "actual_serving_format": record["format"], "actual_library_sha256": digest,
        "actual_ordinary_model_state": trace["ordinary_model_state"],
        "actual_native_response": {k: raw["response"][k] for k in ("raw_id", "finish_reason", "content")},
        "all_actual_visible_ordinary_candidates": candidates,
        "all_actual_observed_program_receipts": {sid: [{k: v for k, v in e.items()
            if k not in ("literal_original_clauses", "actual_query_arguments")} for e in ee] for sid, ee in events.items()}}


def teaching_input(probe, parent, records, phase):
    body = CORE.teaching_input(probe.cfg, probe.packet, parent, [], probe.render.validate_library(parent), phase)
    rows = {r["id"]: r for r in probe.packet["training"][:18]}
    libraries = {}
    body["all_actual_own_public_observations"] = [observation(r, rows, libraries) for r in records]
    body["observed_libraries"] = libraries
    body["new_common_native_serving_encoding"] = ENCODING
    body["new_actual_serving_notice"] = NOTICE
    body["no_assumed_behavior_invariance_from_reversible_data_compaction"] = True
    return body


class Probe(Comparison):
    def __init__(self, preparing=False):
        self.cfg = {**read(CONFIG), "planned_new_native_calls": 30, "planned_new_teacher_calls": 2}
        old = read(PROTOTYPE / "registration.json")
        self.bindings = old["files"] if preparing else read(OUT / "registration.json")["files"]
        self.out, self.run_id = OUT, OUT.name
        self.native, self.teachers, self.teacher_attempts, self.current_batch, self.stop = [], [], 0, 3, False
        self.packet = read(ROOT / self.cfg["input_packet"])
        self.labels = self.packet["public_hypotheses"]
        self.meter = WireClient(self.cfg["generation"])
        self.render = CORE.renderer(self.cfg, self.labels, self.meter)
        self.model, self.manifest = CORE.load_model(self.cfg)
        self.rows = {r["id"]: r for r in self.packet["training"]}
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: setattr(self, "stop", True))

    def compile(self, stage, arm, doc, bank):
        messages, schema, trace = compact_payload(self.render, self.cfg, self.labels,
            CORE.NoGold(self.rows[doc]), arm, bank, self.model, self.manifest["state_sha256"])
        tokens = self.meter.token_count(messages=messages)
        assert tokens + self.cfg["generation"]["max_tokens"] <= self.cfg["generation"]["context_tokens"]
        return messages, schema, trace, {"stage": stage, "arm": arm, "document_id": doc,
            "prompt_tokens": tokens, "messages_sha256": csha(messages), "schema_sha256": csha(schema)}

    def group(self, stage, pairs):
        prepared = [(arm, doc, bank, self.compile(stage, arm, doc, bank)) for arm, doc, bank in pairs]
        RunStore.immutable_json(OUT / f"prospective/{stage}.json", {"all_complete_group_inputs_fit_before_first_call": True,
            "fixed_ordinary_M2_state": self.manifest["state_sha256"], "requests": [v[3][3] for v in prepared]})
        records = []
        for arm, doc, bank, (messages, schema, trace, _) in prepared:
            path = OUT / f"native/{stage}/{arm}/{doc}.native.json"
            self.call(path, messages, schema, self.cfg["generation"]["max_tokens"], {
                "stage": stage, "arm": arm, "document_id": doc, "call_role": "final",
                "published_library": bank, "actual_factual_trace": trace})
            records.append({"format": ENCODING, "path": str(path), "document_id": doc})
        return records

    def edit(self, name, parent, records):
        body = teaching_input(self, parent, records, name)
        RunStore.immutable_json(OUT / f"teacher_inputs/{name}.json", body)
        schema = differential_schema(self.labels, parent, self.cfg["training_ids"][:18], guidance_schema=PROGRAM_GUIDANCE_SCHEMA)
        value = self.teacher_call(name, SYSTEM, body, schema)
        bank = apply_differential_publication(parent, value, self.labels,
            self.cfg["training_ids"][:18], guidance_schema=PROGRAM_GUIDANCE_SCHEMA)
        capacity = self.render.validate_library(bank)
        RunStore.immutable_json(OUT / f"publications/{name}.json", {
            "actual_parent": parent, "actual_teacher_value": value, "publication": bank, "capacity": capacity,
            "all_valid_edits_used_without_efficacy_gate_or_bank_selection": True})
        return bank

    def execute(self):
        self.check()
        reg = read(OUT / "registration.json")
        parent, old = reg["initial_parent"], reg["old_own_observations"]
        with (ROOT / "artifacts/gpu_generation.lock").open("a+") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            observed = self.group("B3_compact_parent", [("skill_memory", doc, parent) for doc in TRAIN])
            draft = self.edit("first_native_grounded_draft", parent, [*old, *observed])
            draft_records = self.group("B3_draft_replay", [("skill_memory", doc, draft) for doc in TRAIN])
            final = self.edit("own_candidate_native_feedback_revision", draft, [*old, *observed, *draft_records])
            self.group("B3_final_replay", [("skill_memory", doc, final) for doc in TRAIN])
            self.current_batch = 4
            pairs = []
            for i, doc in enumerate(TRANSFER):
                for arm in (("ordinary_memory", "skill_memory") if i % 2 == 0 else ("skill_memory", "ordinary_memory")):
                    pairs.append((arm, doc, final if arm == "skill_memory" else []))
            self.group("B4_first_encounter", pairs)
            self.finish()

    def finish(self):
        assert len(self.native) == 30 and len(self.teachers) == self.teacher_attempts == 2
        assert sha(ROOT / self.cfg["source_archive"]) == self.cfg["source_archive_sha256"]
        with zipfile.ZipFile(ROOT / self.cfg["source_archive"]) as archive:
            author = json.loads(archive.read("contract-nli/train.json"))
        rows = {r["id"]: r for r in author["documents"]}
        paths = {"B3_old_encoding_parent": [PREFIX / f"native/execution_feedback_revision/{d}.native.json" for d in TRAIN]}
        paths.update({stage: [OUT / f"native/{stage}/skill_memory/{d}.native.json" for d in TRAIN]
            for stage in ("B3_compact_parent", "B3_draft_replay", "B3_final_replay")})
        paths.update({"B4_" + arm: [OUT / f"native/B4_first_encounter/{arm}/{d}.native.json" for d in TRANSFER]
            for arm in ("ordinary_memory", "skill_memory")})
        groups = {}
        for name, pp in paths.items():
            units = []
            for path in pp:
                raw = read(path)
                row = rows[raw["document_id"]]
                scored = original_score(raw["response"], row, row["annotation_sets"][0]["annotations"], list(author["labels"]))
                if scored["public_valid"]:
                    validate(scored["parsed"], raw["calls"][0]["request"]["response_format"]["json_schema"]["schema"])
                units.append({"document_id": row["id"], "response": raw["response"], **scored})
            groups[name] = units
        self.check()
        result = {"at": now(), "run_id": self.run_id, "new_native_teacher_calls": [30, 2],
            "all30_saved_before_worker_new_outcome_scoring": True,
            "teachers_receive_TRAIN_Gold_and_actual_own_answers_but_never_B4": True,
            "same_ordinaryM2_and_common_compact_native_format_for_parent_draft_final_B4": True,
            "no_new_model_fit_or_final_bank_efficacy_selection": True,
            "metrics": {name: points(units) for name, units in groups.items()}, "all_units": groups,
            "native_usage": {k: sum(v["response"][k] for v in self.native) for k in ("prompt_tokens", "completion_tokens")},
            "new_teacher_invocations": [{"name": t["name"], "invocation": t["invocation"]} for t in self.teachers],
            "shared_prefix_costs_not_new_free_or_independent": str(PREFIX / "monitoring/actual_two_second_pass_teacher_complete_input_value_event_audit.json"),
            "not_formal_TEST_fair_method_win_or_independent_learning_repeat": True,
            "all_output_sha256": {str(path): sha(path) for pp in paths.values() for path in pp}}
        RunStore.immutable_json(OUT / "completion.json", result)
        RunStore.atomic_json(OUT / "progress.json", {"at": now(), "state": "completed", "run_id": self.run_id,
            "completed_native_calls": 30, "completed_teacher_calls": 2})
        print(json.dumps({"metrics": result["metrics"], "new_calls": [30, 2]}, ensure_ascii=False))


def prepare():
    assert not (OUT / "registration.json").exists()
    terminal = read(PROTOTYPE / "prelaunch_terminal.json")
    assert terminal["state"] == "cancelled_before_launch" and terminal["completed_native_calls"] == 0
    previous = read(PROTOTYPE / "registration.json")
    probe = Probe(preparing=True)
    probe.check()
    parent = previous["initial_parent"]
    shape = teaching_input(probe, parent, previous["old_own_observations"], "historical_only_shape_preview_not_sent")
    chars = len(render_structured_codex_prompt(SYSTEM, json.dumps(shape, ensure_ascii=False, separators=(",", ":"))))
    assert chars <= CODEX_TURN_INPUT_CHARACTER_LIMIT
    RunStore.immutable_json(OUT / "historical_only_teacher_shape_not_sent.json", shape)
    requests = []
    for stage, arm, ids, bank in (("B3_compact_parent", "skill_memory", TRAIN, parent),
            ("B4_initial_parent_capacity_only", "skill_memory", TRANSFER, parent),
            ("B4_ordinary_capacity_only", "ordinary_memory", TRANSFER, [])):
        requests.extend(probe.compile(stage, arm, d, bank)[3] for d in ids)
    paths = [Path(__file__), OUT / "PROTOCOL.md", OUT / "historical_only_teacher_shape_not_sent.json",
        PROTOTYPE / "experiment.py", PROTOTYPE / "PROTOCOL.md", PROTOTYPE / "registration.json",
        PROTOTYPE / "prelaunch_terminal.json", PROTOTYPE / "monitoring/initial_parent_next6_complete_native_capacity.json"]
    RunStore.immutable_json(OUT / "registration.json", {"at": now(), "files": {
        **previous["files"], **{str(p): sha(p) for p in paths}}, "initial_parent": parent,
        "old_own_observations": previous["old_own_observations"], "new_native_teacher_calls": [30, 2],
        "serving_encoding": ENCODING, "first18_original_teacher_sources": probe.cfg["training_ids"][:18],
        "B3_training_replay_ids": TRAIN, "B4_transfer_ids_not_teacher_inputs": TRANSFER,
        "historical_only_preview_characters_not_a_call": chars,
        "all18_capacity_only_requests_roundtrip_data_equal_not_behavior_invariance": requests,
        "future_draft_final_capacity_not_proven_by_initial_parent_fit": True,
        "no_new_model_fit_or_independent_learning_claim": True})
    print(json.dumps({"new_calls": [30, 2], "historical_preview_characters": chars,
        "capacity_only_requests": [{k:r[k] for k in ("stage", "document_id", "prompt_tokens")} for r in requests],
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
        probe = Probe()
        try:
            probe.execute()
        except BaseException as exc:
            value = {"at": now(), "run_id": OUT.name, "error": repr(exc),
                "completed_native_calls": len(probe.native), "completed_teacher_calls": len(probe.teachers),
                "teacher_attempts": probe.teacher_attempts,
                "no_retry_fallback_admission_bank_selection_or_answer_repair": True}
            RunStore.immutable_json(OUT / "failure.json", value)
            RunStore.atomic_json(OUT / "progress.json", {"state": "stopped" if isinstance(exc, InterruptedError) else "failed", **value})
            raise
    else:
        raise ValueError("Explicit prepare, launch or worker required")
