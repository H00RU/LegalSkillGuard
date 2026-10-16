"""Own-candidate native feedback under a fixed auxiliary; no bank admission."""

# ruff: noqa: E402 -- Frozen run-local mechanism continuation, not a framework.
from __future__ import annotations

import fcntl
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
from legal_skill_guard.learning.audit import original_score
from legal_skill_guard.learning.experiment import Comparison, now, points, read, sha
from legal_skill_guard.learning.publication import (
    apply_differential_publication,
    differential_schema,
)
from legal_skill_guard.learning.source_programs import (
    PROGRAM_GUIDANCE_SCHEMA,
    SourceProgramStudy,
    execute_program,
)
from legal_skill_guard.task import marked_text
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha

PREFIX = ROOT / "runs/legal_contractnli_execution_grounded_editor_completion_20261017_run01"
MAIN = ROOT / "runs/legal_contractnli_source_program_online_learning_20261017_run03"
CONFIG = ROOT / "configs/contractnli_source_programs_completion.json"
TRAIN = [273, 416, 261, 487, 377, 159]
TRANSFER = [430, 290, 622, 613, 383, 92]
SYSTEM = (
    "You are the existing legal-skill writer, not a critic, router, grader or "
    "answer selector. Revise the supplied current_parent_library using ONLY all "
    "18 supplied original already-seen TRAIN contracts/Gold, actual public "
    "native observations and mechanical source executions. All observation "
    "libraries/tool identities are explicit: old M1 observations are NOT "
    "executions of the current bank. Current B3 observations and this pass's "
    "candidate replay use the SAME frozen ordinaryM2 auxiliary and SAME8B. "
    "Only external memory changes; the auxiliary is NOT refitted on B3. "
    "This is a fixed two-writer-pass learning procedure. The first pass creates "
    "a draft, which is really executed by the native lawyer on the six already-"
    "seen B3 training contracts. The second pass receives these exact new "
    "answers alongside the old own answers, original Gold and both libraries. "
    "There is no utility threshold, choosing a previous/better bank or a third "
    "curator. The second structurally valid output is used unconditionally on "
    "the next six contracts, whose text/Gold/outcomes you never see here. "
    "Train the joint procedure, not only query hit counts: distinguish search "
    "miss, visible-but-rejected evidence, unsupported inference, wrong three-"
    "way relation, and damage caused by restrictive instructions. Public "
    "reasons are fallible observations, not faithful private reasoning. "
    "Use all successful and failed cases and contrasting original labels. "
    "Write concrete evidence-dependent decision tests and evidence acquisition/"
    "retention actions that a weak lawyer can actually follow. State sufficient "
    "conditions and their exact legal relation when justified by the observed "
    "contrasts; do not merely say inspect or decide again. An unestablished "
    "sufficient condition does not establish its opposite or NotMentioned. "
    "Separate a decision-bearing clause from governing, exception, definition, "
    "reference and independently redundant evidence; do not delete a class of "
    "evidence by legal intuition when supplied original annotations include it. "
    "Benchmark training labels/evidence are not universal legal truth. "
    "A skill is a reusable conditional test/procedure, not necessarily a topic "
    "card or one record per public question. No fixed count, types, one-task "
    "quota or growth. Share queries across tasks only with justified scope. "
    "Each record has id,hypothesis_ids,guidance={inspection,source_queries}. "
    "The ONLY query fields are all_phrases,any_phrases,none_phrases,include_list_preamble. "
    "Each query needs a nonempty all or any list. All all-phrases and at least "
    "one any-phrase if present must match contiguous lowercase light-suffix "
    "word/number tokens WITHIN one original SPAN; none-phrases exclude. "
    "Inflections are NOT guaranteed equivalent. Preamble=true adds only "
    "the existing fallible backward list introduction. No regex, sentence "
    "completion, cross-reference/definition resolver, semantic join or model "
    "call is implemented inside a query; never claim otherwise. The original "
    "source stays fully visible, and the lawyer can find/cite outside hits. "
    "A query hit is not evidence automatically; no hit never implies absence. "
    "The one-copy original two-field memory, ordinary candidates, source lead "
    "tags and actual per-query receipts are exactly those in the observations. "
    "Keep the actually serialized master AND scoped memory within4096 tokens; "
    "actual current counts are supplied. Aim below2700 master. Improve by "
    "concise justified updates/merges/deletions, not by accumulating reminders, "
    "synonyms or copied source clauses. Native answers are not host-repaired. "
    "Return existing atomic CREATE/UPDATE/DELETE/MERGE/NOOP edits relative to "
    "current_parent_library: CREATE has no targets; UPDATE/DELETE consumes one "
    "original parent; MERGE consumes at least two. No forward references. "
    "UPDATE keeps ID; DELETE has null skill, others one skill. Unmentioned "
    "records remain unchanged. Cite supplied original source_case_ids and "
    "explain each reusable change; metadata stays outside runtime. Empty "
    "operations require a nonempty noop_reason, otherwise noop_reason=null. "
    "No case IDs, parties, dates, original indices, fingerprints, case-answer "
    "tables or case lookup quotations in runtime skills. No other-method "
    "answers, future sources/Gold, outside law or tools. Lawyer alone decides "
    "all final labels and original evidence sets. Return only the schema."
)


class NoGold(dict):
    def __getitem__(self, key):
        if key == "annotation_sets":
            raise AssertionError("Current Gold forbidden during native construction")
        return super().__getitem__(key)

    def get(self, key, default=None):
        if key == "annotation_sets":
            raise AssertionError("Current Gold forbidden during native construction")
        return super().get(key, default)


def observation(record, row, libraries):
    if record["format"] == "audited_reference_v1":
        reference = read(Path(record["path"]))
        assert reference["raw_artifact"] == record["raw_path"]
        raw = read(Path(record["raw_path"]))
        assert reference["response"] == raw["response"]
        assert reference["published_library"] == raw["published_library"]
        trace = reference["actual_factual_trace"]
    elif record["format"] == "native_with_trace_v1":
        raw = read(Path(record["path"]))
        trace = raw["actual_factual_trace"]
    else:
        raise ValueError("Explicit original observation format required; no reconstruction")
    assert raw["document_id"] == row["id"] == record["document_id"]
    assert len(raw["calls"]) == 1 and raw["response"] is not None
    body = json.loads(raw["calls"][0]["request"]["messages"][1]["content"])
    bank = raw["published_library"]
    digest = csha(bank)
    libraries[digest] = bank
    candidates = {}
    for h, q in body["hypotheses"].items():
        candidates[h] = []
        for candidate in q["fallible_evidence_candidates"]:
            index = candidate["original_span_index"]
            assert candidate["literal_original_text"] == row["text"][slice(*row["spans"][index])]
            candidates[h].append({k: v for k, v in candidate.items() if k != "literal_original_text"})
    executions = trace["task_local_delivery"]["source_program_execution_by_skill"]
    return {"document_id": row["id"], "actual_stage": raw["stage"],
        "actual_library_sha256_resolves_from_observed_libraries": digest,
        "actual_ordinary_model_state": trace["ordinary_model_state"],
        "actual_native_response": {k: raw["response"][k] for k in ("raw_id", "finish_reason", "content")},
        "all_actual_visible_ordinary_candidates": candidates,
        "all_actual_observed_program_receipts": {sid: [{k: v for k, v in event.items()
            if k not in ("literal_original_clauses", "actual_query_arguments")} for event in events]
            for sid, events in executions.items()}}


def teaching_input(cfg, packet, parent, observation_records, capacity, phase):
    rows = {r["id"]: r for r in packet["training"][:18]}
    libraries, observations = {}, []
    for record in observation_records:
        observations.append(observation(record, rows[record["document_id"]], libraries))
    cases, executed = [], []
    for row in packet["training"][:18]:
        gold = row["annotation_sets"][0]["annotations"]
        cases.append({"document_id": row["id"], "full_original_contract_with_spans": marked_text(row),
            "all_original_annotations": gold})
        events = {s["id"]: execute_program(NoGold(row), s) for s in parent}
        pools = {h: {i for s in parent if h in s["hypothesis_ids"] for e in events[s["id"]]
            for i in e["returned_original_span_indices"]} for h in packet["public_hypotheses"]}
        executed.append({"document_id": row["id"], "all_actual_current_parent_query_executions": {
            sid: [{k: v for k, v in e.items() if k not in ("literal_original_clauses", "actual_query_arguments")}
                for e in ee] for sid, ee in events.items()},
            "all17_original_membership_comparisons": {h: {
                "returned_indices": sorted(hits), "Gold_members_reached": sorted(hits & set(gold[h]["spans"])),
                "returned_non_Gold": sorted(hits - set(gold[h]["spans"])),
                "Gold_members_missing": sorted(set(gold[h]["spans"]) - hits)} for h, hits in pools.items()}})
    return {"phase": phase, "public_hypotheses": packet["public_hypotheses"],
        "all18_original_TRAIN_sources_and_Gold": cases, "current_parent_library": parent,
        "observed_libraries": libraries, "all_actual_own_public_observations": observations,
        "all18_actual_current_parent_source_only_executions": executed,
        "current_parent_actual_capacity": capacity, "master_and_actual_scoped_cap": cfg["library_token_hard_cap"],
        "source_and_query_reference_resolution": (
            "Candidate literal text resolves exactly to original_span_index in this document's full "
            "original marked source; scores/indices are exact actually visible candidates. Query "
            "arguments resolve to observed library SHA/skill_id/query_index for actual native "
            "observations, and current_parent_library for source-only executions. No fields are "
            "filtered by score or success. All18 sources, all17 tasks and every public answer "
            "remain. Deliberately reorganized packet, not an old-wire/full-internal-vector encoding."
        ), "runtime_actor_system": cfg["bundled_solver_system"],
        "no_next_batch_future_gold_other_method_answers_or_private_reasoning": True}


def renderer(cfg, labels, meter):
    value = object.__new__(SourceProgramStudy)
    value.cfg, value.labels, value.meter = cfg, labels, meter
    return value


def load_model(cfg):
    path = ROOT / cfg["reference_training_run"] / "evidence_models/ordinary_M2.manifest.json"
    manifest = read(path)
    assert manifest["seen_original_source_ids"] == cfg["training_ids"][:12]
    assert sha(manifest["path"]) == manifest["pickle_sha256"]
    with Path(manifest["path"]).open("rb") as stream:
        model = pickle.load(stream)
    assert not model.queries and not model.programs
    return model, manifest


def prepare():
    assert not (OUT / "registration.json").exists()
    assert not Path("/proc", str(read(PREFIX / "launch.json")["pid"])).exists()
    assert read(PREFIX / "progress.json")["state"] == "completed"
    cfg = read(CONFIG)
    packet = read(ROOT / cfg["input_packet"])
    assert cfg["training_ids"][12:18] == TRAIN and cfg["training_ids"][18:24] == TRANSFER
    manual = PREFIX / "monitoring/complete12_original_author_manual_sets_wire_and_acquisition_audit.json"
    teachers = PREFIX / "monitoring/actual_two_second_pass_teacher_complete_input_value_event_audit.json"
    bindings = {**read(manual)["bindings"], **read(teachers)["verified_files"]}
    assert all(sha(p) == h for p, h in bindings.items())
    parent_path = PREFIX / "condition_publications/execution_feedback_revision.json"
    parent = read(parent_path)["publication"]  # Latest intended arm, NOT the better blind bank.
    meter = WireClient(cfg["generation"])
    render = renderer(cfg, packet["public_hypotheses"], meter)
    model, manifest = load_model(cfg)
    paths = [Path(__file__), OUT / "PROTOCOL.md", manual, teachers, parent_path,
        ROOT / "artifacts/source_program_paired_complete12_all327_before_native_loop_backup_20261017.json"]
    observations = []
    for row in packet["training"][:12]:
        stage = "batch1_after" if row["id"] in cfg["training_ids"][:6] else "batch2_before"
        ref = MAIN / stage / "skill_memory" / f"{row['id']}.reference.json"
        raw_path = read(ref)["raw_artifact"]
        observations.append({"format": "audited_reference_v1", "path": str(ref),
            "raw_path": raw_path, "document_id": row["id"]})
        paths.extend([ref, Path(raw_path)])
    for doc in TRAIN:
        path = PREFIX / f"native/execution_feedback_revision/{doc}.native.json"
        observations.append({"format": "native_with_trace_v1", "path": str(path), "document_id": doc})
        paths.append(path)
    body = teaching_input(cfg, packet, parent, observations, render.validate_library(parent), "first_native_grounded_draft")
    chars = len(render_structured_codex_prompt(SYSTEM, json.dumps(body, ensure_ascii=False, separators=(",", ":"))))
    assert chars <= CODEX_TURN_INPUT_CHARACTER_LIMIT
    RunStore.immutable_json(OUT / "teacher_inputs/first_native_grounded_draft.json", body)
    rows = {r["id"]: r for r in packet["training"]}
    bare = {}
    for doc in TRANSFER:
        messages, _, _, _ = render.make_payload("ordinary_memory", NoGold(rows[doc]), [], model, manifest["state_sha256"])
        tokens = meter.token_count(messages=messages)
        assert tokens + cfg["generation"]["max_tokens"] <= cfg["generation"]["context_tokens"]
        bare[str(doc)] = tokens
    paths.append(OUT / "teacher_inputs/first_native_grounded_draft.json")
    RunStore.immutable_json(OUT / "registration.json", {"at": now(), "files": {
        **bindings, **{str(p): sha(p) for p in paths}}, "original_teacher_source_ids": cfg["training_ids"][:18],
        "same_source_training_replay_ids": TRAIN, "next_batch_transfer_ids": TRANSFER,
        "initial_parent": parent, "old_own_observations": observations,
        "fixed_ordinary_M2_manifest": manifest, "new_native_teacher_calls": [24, 2],
        "first_teacher_complete_characters": chars, "bare_next6_prompt_tokens_no_generation": bare,
        "no_model_fit_bank_selection_or_independent_learning_claim": True})
    print(json.dumps({"teacher_characters": chars, "new_calls": [24, 2], "bare_next6_prompt_tokens": bare,
        "preparation_generation_calls": 0}))


class Probe(Comparison):
    def __init__(self):
        self.cfg = {**read(CONFIG), "planned_new_native_calls": 24, "planned_new_teacher_calls": 2}
        self.bindings = read(OUT / "registration.json")["files"]
        self.out, self.run_id = OUT, OUT.name
        self.native, self.teachers, self.teacher_attempts, self.current_batch, self.stop = [], [], 0, 3, False
        self.packet = read(ROOT / self.cfg["input_packet"])
        self.labels = self.packet["public_hypotheses"]
        self.meter = WireClient(self.cfg["generation"])
        self.renderer = renderer(self.cfg, self.labels, self.meter)
        self.model, self.manifest = load_model(self.cfg)
        self.rows = {r["id"]: r for r in self.packet["training"]}
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda *_: setattr(self, "stop", True))

    def compile(self, stage, arm, doc, bank):
        row = NoGold(self.rows[doc])
        messages, schema, _, trace = self.renderer.make_payload(arm, row, bank, self.model, self.manifest["state_sha256"])
        body = json.loads(messages[1]["content"])
        restored = body["full_contract_with_original_span_markers"]
        for tag in trace["task_local_delivery"].get("source_lead_tags_by_original_span", {}).values():
            restored = restored.replace(tag, "", 1)
        assert restored == marked_text(row)
        tokens = self.meter.token_count(messages=messages)
        assert tokens + self.cfg["generation"]["max_tokens"] <= self.cfg["generation"]["context_tokens"]
        return messages, schema, trace, {"stage": stage, "arm": arm, "document_id": doc,
            "prompt_tokens": tokens, "messages_sha256": csha(messages), "schema_sha256": csha(schema)}

    def generate_group(self, stage, pairs):
        prepared = [(arm, doc, bank, self.compile(stage, arm, doc, bank)) for arm, doc, bank in pairs]
        RunStore.immutable_json(OUT / f"prospective/{stage}.json", {
            "all_complete_inputs_fit_before_any_generation_in_group": True,
            "fixed_M2_auxiliary_state": self.manifest["state_sha256"],
            "requests": [p[3][3] for p in prepared]})
        paths = []
        for arm, doc, bank, (messages, schema, trace, _) in prepared:
            path = OUT / f"native/{stage}/{arm}/{doc}.native.json"
            self.call(path, messages, schema, self.cfg["generation"]["max_tokens"], {
                "stage": stage, "arm": arm, "document_id": doc, "call_role": "final",
                "published_library": bank, "actual_factual_trace": trace})
            paths.append(path)
        return paths

    def edit(self, name, parent, observations):
        body = teaching_input(self.cfg, self.packet, parent, observations,
            self.renderer.validate_library(parent), name)
        RunStore.immutable_json(OUT / f"teacher_inputs/{name}.json", body)
        schema = differential_schema(self.labels, parent, self.cfg["training_ids"][:18], guidance_schema=PROGRAM_GUIDANCE_SCHEMA)
        value = self.teacher_call(name, SYSTEM, body, schema)
        bank = apply_differential_publication(parent, value, self.labels,
            self.cfg["training_ids"][:18], guidance_schema=PROGRAM_GUIDANCE_SCHEMA)
        capacity = self.renderer.validate_library(bank)
        RunStore.immutable_json(OUT / f"publications/{name}.json", {
            "parent": parent, "actual_teacher_value": value, "publication": bank, "capacity": capacity,
            "all_valid_edits_used_no_efficacy_gate_fallback_or_bank_selection": True})
        return bank

    def execute(self):
        self.check()
        reg = read(OUT / "registration.json")
        observations = reg["old_own_observations"]
        draft = self.edit("first_native_grounded_draft", reg["initial_parent"], observations)
        with (ROOT / "artifacts/gpu_generation.lock").open("a+") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            draft_paths = self.generate_group("B3_draft_replay", [("skill_memory", doc, draft) for doc in TRAIN])
            draft_observations = [{"format": "native_with_trace_v1", "path": str(path),
                "document_id": doc} for path, doc in zip(draft_paths, TRAIN, strict=True)]
            final = self.edit("own_candidate_native_feedback_revision", draft, [*observations, *draft_observations])
            self.generate_group("B3_final_replay", [("skill_memory", doc, final) for doc in TRAIN])
            self.current_batch = 4
            pairs = []
            for i, doc in enumerate(TRANSFER):
                arms = ("ordinary_memory", "skill_memory") if i % 2 == 0 else ("skill_memory", "ordinary_memory")
                pairs.extend((arm, doc, final if arm == "skill_memory" else []) for arm in arms)
            self.generate_group("B4_first_encounter", pairs)
            self.finish()

    def finish(self):
        assert len(self.native) == 24 and len(self.teachers) == self.teacher_attempts == 2
        assert sha(ROOT / self.cfg["source_archive"]) == self.cfg["source_archive_sha256"]
        with zipfile.ZipFile(ROOT / self.cfg["source_archive"]) as archive:
            author = json.loads(archive.read("contract-nli/train.json"))
        rows = {r["id"]: r for r in author["documents"]}
        paths = {
            "B3_parent": [PREFIX / f"native/execution_feedback_revision/{doc}.native.json" for doc in TRAIN],
            "B3_draft": [OUT / f"native/B3_draft_replay/skill_memory/{doc}.native.json" for doc in TRAIN],
            "B3_final": [OUT / f"native/B3_final_replay/skill_memory/{doc}.native.json" for doc in TRAIN],
            "B4_ordinary": [OUT / f"native/B4_first_encounter/ordinary_memory/{doc}.native.json" for doc in TRANSFER],
            "B4_skill": [OUT / f"native/B4_first_encounter/skill_memory/{doc}.native.json" for doc in TRANSFER],
        }
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
        result = {"at": now(), "run_id": self.run_id, "new_native_teacher_calls": [24, 2],
            "all24_answers_saved_before_worker_new_outcome_scoring": True,
            "teacher_training_feedback_explicitly_contains_original_TRAIN_Gold_not_B4": True,
            "ordinary_M2_fixed_no_new_CPU_fit_or_8B_weight_update": True,
            "final_bank_used_unconditionally_not_selected_by_B3_or_B4_metrics": True,
            "metrics": {name: points(units) for name, units in groups.items()}, "all_units": groups,
            "native_usage": {k: sum(n["response"][k] for n in self.native) for k in ("prompt_tokens", "completion_tokens")},
            "new_teacher_invocations": [{"name": t["name"], "invocation": t["invocation"]} for t in self.teachers],
            "shared_prefix_costs_not_new_or_free": {"prior_paired_trial": str(PREFIX / "completion.json"),
                "full_upstream_cost_qualification": str(PREFIX / "monitoring/actual_two_second_pass_teacher_complete_input_value_event_audit.json")},
            "not_formal_TEST_fair_method_win_or_independent_learning_repeat": True,
            "all_output_sha256": {str(path): sha(path) for pp in paths.values() for path in pp}}
        RunStore.immutable_json(OUT / "completion.json", result)
        RunStore.atomic_json(OUT / "progress.json", {"at": now(), "state": "completed", "run_id": self.run_id,
            "completed_native_calls": 24, "completed_teacher_calls": 2})
        print(json.dumps({"metrics": result["metrics"], "new_native_teacher_calls": [24, 2]}, ensure_ascii=False))


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
