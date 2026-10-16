"""Paired fixed-draft revision with/without actual query execution feedback."""

# ruff: noqa: E402 -- Independent run-local entry point.
from __future__ import annotations

import copy
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
from legal_skill_guard.learning.audit import close, original_score
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

MAIN = ROOT / "runs/legal_contractnli_source_program_online_learning_20261017_run03"
PREVIOUS = ROOT / "runs/legal_contractnli_program_member_grounding_diagnostic_20261017_run01"
CONFIG = ROOT / "configs/contractnli_source_programs_completion.json"
IDS = [273, 416, 261, 487, 377, 159]
ARMS = ("blind_revision", "execution_feedback_revision")
SYSTEM = (
    "Act as the SAME legal-skill editor revising a fixed M2 DRAFT once, not a "
    "new critic or selection gate. Use ONLY the supplied12 original B1/B2 TRAIN "
    "sources, original Gold, actual old native M1-parent observations and memory. "
    "Old native answers used M1 and its stated ordinary tool, NOT this M2 draft. "
    "If draft_execution_feedback is present, it is real source-only query "
    "execution, NOT new lawyer answers or hidden reasoning under the draft. "
    "If absent, no measured draft executions are supplied; invent none. "
    "Improve both exact legal decision distinctions and complete evidence "
    "acquisition while reducing off-task/noisy retrieval. A skill is one "
    "concrete reusable inspection/test with executable queries, not a topic "
    "folder or generic reminder to check actors and polarity. Share a scope "
    "ONLY when EVERY query and the inspection actually serve every public "
    "task in that scope. Otherwise split/restructure records using ordinary "
    "CRUD, not a new router. Do not pool different tasks' retrieval criteria "
    "because they mention similar concepts. No fixed skill count, type, growth "
    "or one-skill-per-question quota. Preserve justified older distinctions. "
    "Write concise evidence-dependent decision procedures from supplied "
    "contrasts, not automatic verdicts for a new document. Distinguish exact "
    "actors, actions, triggers, scope, exceptions, quantifiers and polarity. "
    "Acquisition/completeness can justify an edit without a new class "
    "condition; this does NOT prohibit a useful legal decision distinction. "
    "Keep needed governing and independently operative evidence, but do not "
    "recommend every related definition, heading or actor mention as evidence. "
    "A contextual reading lead is not automatically an annotated witness. "
    "Each record is id, hypothesis_ids and guidance={inspection,source_queries}. "
    "Queries have exactly all_phrases,any_phrases,none_phrases,include_list_preamble. "
    "At least one all/any phrase is needed. They perform contiguous lowercase "
    "light-suffix-stemmed word/number matching WITHIN one original SPAN: all "
    "all-phrases, at least one any-phrase when nonempty, no none-phrase. "
    "Preamble=true adds only actual fallible backward list-introduction links. "
    "No regex, windows, paragraph walks, cross-reference resolver or semantic "
    "join exists. Do not claim these unimplemented actions were executed; "
    "inspection may direct the lawyer to read more of the full source. "
    "Use actual supplied execution to find silent misses, wrong scopes, broad "
    "hits and lost members when available. Prefer compositional transferable "
    "queries to catch-all words, long memorized clauses or synonym accumulation. "
    "The library is shown once with public-task references and source-only "
    "index/tag receipts, NOT the failed extra literal-member view. All17 tasks, "
    "ordinary candidates and the original NDA remain visible; empty hits or "
    "missing skills never mean NotMentioned. Lawyer alone emits labels and all "
    "final original indices; it may reject hits and cite elsewhere. "
    "Both master and actual one-copy+scope memory must fit4096 tokens; aim "
    "below2700 master, using concise concrete inspections and focused queries. "
    "Return atomic edits relative to this supplied M2 DRAFT: CREATE no target; "
    "UPDATE/DELETE one unconsumed original ID; MERGE at least two. No forward "
    "references. UPDATE keeps ID; DELETE has null skill; others one skill. "
    "Unmentioned records remain verbatim. Each edit cites supplied original "
    "source_case_ids and explains the reusable change. Empty operations need "
    "nonempty noop_reason; otherwise noop_reason=null. All valid edits are "
    "used unconditionally, without score admission, best bank, rollback, "
    "fallback or second curator. Gold is benchmark TRAIN feedback, not universal "
    "legal truth. No case IDs, parties, dates, original indices, fingerprints, "
    "lookup clauses or answer tables in runtime text. No outside law/tools, "
    "future sources/Gold, other arms' outcomes or model fitting. Return ONLY "
    "the provided differential-publication schema."
)


class NoGold(dict):
    def __getitem__(self, key):
        if key == "annotation_sets":
            raise AssertionError("Current Gold is forbidden in native construction")
        return super().__getitem__(key)

    def get(self, key, default=None):
        if key == "annotation_sets":
            raise AssertionError("Current Gold is forbidden in native construction")
        return super().get(key, default)


def teaching_inputs(cfg, packet, draft, observed_parent):
    """All12 cases/Gold/actual old answers, not a lossless old-wire encoding."""
    cases, measured, paths = [], [], []
    for row in packet["training"][:12]:
        stage = "batch1_after" if row["batch"] == 1 else "batch2_before"
        path = MAIN / stage / "skill_memory" / f"{row['id']}.reference.json"
        unit = read(path)
        assert unit["published_library"] == observed_parent
        gold = row["annotation_sets"][0]["annotations"]
        parsed = unit["parsed"] if unit["public_valid"] else None
        if parsed is not None:
            assert parsed == json.loads(unit["response"]["content"])
        ordinary = {h: unit["actual_factual_trace"]["proposals"]["by_hypothesis"][h]["candidates"] for h in packet["public_hypotheses"]}
        cases.append({"document_id": row["id"], "full_original_contract_with_spans": marked_text(row),
            "original_annotations": gold, "actual_old_M1_public_valid": unit["public_valid"],
            "actual_old_M1_public_response": {k: unit["response"][k] for k in ("raw_id", "finish_reason", "content")},
            "actual_old_M1_bank_sha256": unit["published_library_sha256"],
            "actual_old_ordinary_tool_state": unit["actual_factual_trace"]["ordinary_model_state"],
            "actual_old_visible_ordinary_candidates": ordinary})
        executions = {s["id"]: execute_program(NoGold(row), s) for s in draft}
        returned = sorted({i for events in executions.values() for e in events for i in e["returned_original_span_indices"]})
        atoms = [{"original_span_index": i, "literal_original_text": row["text"][row["spans"][i][0]:row["spans"][i][1]],
            "original_Gold_member_of_public_tasks": [h for h, g in gold.items() if i in g["spans"]]} for i in returned]
        by_skill = {}
        for skill in draft:
            records = []
            for event in executions[skill["id"]]:
                hits = set(event["returned_original_span_indices"])
                records.append({k: copy.deepcopy(v) for k, v in event.items() if k not in ("literal_original_clauses", "actual_query_arguments")} | {
                    "actual_arguments_resolve_exactly_from_draft_skill_id_and_query_index": True,
                    "per_declared_public_task_original_membership": {h: {
                        "original_Gold_members_reached": sorted(set(gold[h]["spans"]) & hits),
                        "returned_non_Gold_members": sorted(hits - set(gold[h]["spans"])),
                        "original_Gold_members_not_reached": sorted(set(gold[h]["spans"]) - hits),
                    } for h in skill["hypothesis_ids"]}})
            by_skill[skill["id"]] = records
        measured.append({"document_id": row["id"], "all_actual_draft_query_executions": by_skill,
            "all_unique_actual_returned_source_atoms": atoms,
            "source_query_only_execution_not_a_native_answer_or_semantic_gate": True})
        paths.extend((path, Path(unit["raw_artifact"])))
    assert [c["document_id"] for c in cases] == cfg["training_ids"][:12]
    common = {"public_hypotheses": packet["public_hypotheses"], "actual_M1_native_parent_library": observed_parent,
        "fixed_M2_draft_library": draft, "all12_original_TRAIN_and_actual_old_M1_observations": cases,
        "editor_feedback_is_deliberately_reorganized_not_old_wire_lossless_or_full_internal_vectors": True,
        "all_sources_successes_failures_and_public_tasks_retained_no_future_inputs": True,
        "runtime_original_two_field_API_and_actual_actor_system": cfg["bundled_solver_system"],
        "full_master_and_one_copy_capacity": cfg["library_token_hard_cap"]}
    return {ARMS[0]: {**common, "draft_execution_feedback": None},
        ARMS[1]: {**common, "draft_execution_feedback": measured}}, paths


def prepare():
    assert not (OUT / "registration.json").exists()
    assert not (Path("/proc") / str(read(PREVIOUS / "launch.json")["pid"])).exists()
    previous_audit = read(PREVIOUS / "monitoring/complete6_original_author_manual_sets_and_wire_audit.json")
    assert all(sha(p) == h for p, h in previous_audit["bindings"].items())
    cfg, frozen = read(CONFIG), read(CONFIG.with_suffix(".frozen.json"))
    assert all(sha(p) == h for p, h in frozen["files"].items())
    packet = read(ROOT / cfg["input_packet"])
    tx_path = MAIN / "update_transactions/b2.json"
    tx = read(tx_path)
    inputs, observations = teaching_inputs(cfg, packet, tx["publication"], tx["actual_parent"])
    chars = {}
    for arm, body in inputs.items():
        user = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
        chars[arm] = len(render_structured_codex_prompt(SYSTEM, user))
        assert chars[arm] <= CODEX_TURN_INPUT_CHARACTER_LIMIT
        RunStore.immutable_json(OUT / f"teacher_inputs/{arm}.json", body)
    assert {k: v for k, v in inputs[ARMS[0]].items() if k != "draft_execution_feedback"} == {
        k: v for k, v in inputs[ARMS[1]].items() if k != "draft_execution_feedback"}
    paths = [CONFIG, CONFIG.with_suffix(".frozen.json"), Path(__file__), OUT / "PROTOCOL.md", tx_path,
        PREVIOUS / "completion.json", PREVIOUS / "monitoring/complete6_original_author_manual_sets_and_wire_audit.json",
        *(OUT / f"teacher_inputs/{a}.json" for a in ARMS), *observations]
    RunStore.immutable_json(OUT / "registration.json", {"at": now(), "fixed_original_M2_draft": tx["publication"],
        "teacher_source_ids": cfg["training_ids"][:12], "native_source_ids": IDS,
        "files": {**frozen["files"], **{str(p): sha(p) for p in paths}},
        "teacher_rendered_characters": chars, "new_native_teacher_calls": [12, 2],
        "one_teacher_call_each_not_matched_input_tokens": True,
        "all12_native_answers_before_any_new_scoring_no_future_teacher_observation": True})
    print(json.dumps({"teacher_prompt_chars": chars, "new_calls": [12, 2], "preparation_generation_calls": 0}))


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
        reg = read(OUT / "registration.json")
        draft, banks = reg["fixed_original_M2_draft"], {}
        schema = differential_schema(self.labels, draft, reg["teacher_source_ids"], guidance_schema=PROGRAM_GUIDANCE_SCHEMA)
        for arm in ARMS:
            value = self.teacher_call(arm, SYSTEM, read(OUT / f"teacher_inputs/{arm}.json"), schema)
            banks[arm] = apply_differential_publication(draft, value, self.labels, reg["teacher_source_ids"], guidance_schema=PROGRAM_GUIDANCE_SCHEMA)
            capacity = self.renderer.validate_library(banks[arm])
            RunStore.immutable_json(OUT / f"condition_publications/{arm}.json", {"draft": draft,
                "actual_teacher_value": value, "publication": banks[arm], "capacity": capacity,
                "every_valid_edit_used_without_efficacy_gate_bank_choice_or_answer_repair": True})
        manifest_path = ROOT / self.cfg["reference_training_run"] / "evidence_models/ordinary_M2.manifest.json"
        manifest = read(manifest_path)
        assert manifest["seen_original_source_ids"] == reg["teacher_source_ids"]
        assert sha(manifest["path"]) == manifest["pickle_sha256"]
        with Path(manifest["path"]).open("rb") as stream:
            model = pickle.load(stream)
        assert not model.queries and not model.programs
        rows = {r["id"]: r for r in self.packet["training"]}
        prepared, counts = {}, {}
        for arm in ARMS:
            for d in IDS:
                row = NoGold(rows[d])
                messages, native_schema, _, trace = self.renderer.make_payload("skill_memory", row, banks[arm], model, manifest["state_sha256"])
                original = read(MAIN / f"batch3_before/ordinary_memory/{d}.final.native.json")["calls"][0]["request"]
                baseline = json.loads(original["messages"][1]["content"])
                body = json.loads(messages[1]["content"])
                assert all(body["hypotheses"][h]["fallible_evidence_candidates"] == baseline["hypotheses"][h]["fallible_evidence_candidates"] for h in self.labels)
                restored = body["full_contract_with_original_span_markers"]
                for tag in trace["task_local_delivery"]["source_lead_tags_by_original_span"].values():
                    restored = restored.replace(tag, "", 1)
                assert restored == marked_text(row)
                tokens = self.meter.token_count(messages=messages)
                assert tokens + self.cfg["generation"]["max_tokens"] <= self.cfg["generation"]["context_tokens"]
                prepared[arm, d] = (messages, native_schema, trace)
                counts[f"{arm}/{d}"] = {"prompt_tokens": tokens, "messages_sha256": csha(messages), "schema_sha256": csha(native_schema)}
        RunStore.immutable_json(OUT / "all12_prospective_native_inputs.json", {"requests": counts,
            "both_proposals_validated_before_any_native_call": True, "same_ordinary_M2_candidates_source_and_decode_not_new_fit": True})
        with (ROOT / "artifacts/gpu_generation.lock").open("a+") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            for index, d in enumerate(IDS):
                order = ARMS if index % 2 == 0 else ARMS[::-1]
                for arm in order:
                    messages, native_schema, trace = prepared[arm, d]
                    self.call(OUT / f"native/{arm}/{d}.native.json", messages, native_schema, self.cfg["generation"]["max_tokens"],
                        {"stage": "paired_M2_revision_B3", "arm": arm, "document_id": d, "call_role": "final",
                            "published_library": banks[arm], "actual_factual_trace": trace})
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
            value.update(true_members_gained=sum(len(true(b) - true(a)) for a, b in nn), true_members_lost=sum(len(true(a) - true(b)) for a, b in nn))
            contrasts[new + "_minus_" + old] = value
        self.check()
        result = {"at": now(), "run_id": self.run_id, "native_source_ids": IDS,
            "all12_new_answers_saved_before_any_new_outcome_scoring": True, "new_native_teacher_calls": [12, 2],
            "one_fresh_teacher_each_not_matched_input_tokens_or_independent_learning": True,
            "metrics": {a: points(us) for a, us in groups.items()}, "paired_contrasts": contrasts, "all_units": groups,
            "native_usage": {k: sum(n["response"][k] for n in self.native) for k in ("prompt_tokens", "completion_tokens")},
            "teacher_invocations": [{"name": t["name"], "invocation": t["invocation"]} for t in self.teachers],
            "audited_file_sha256": {**self.bindings, **files}, "not_formal_TEST_significance_or_main_skill_admission": True}
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
            child = subprocess.Popen(argv, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                start_new_session=True, env={**os.environ, "PYTHONUNBUFFERED": "1"})
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
                "no_retry_fallback_other_arm_selection_or_answer_repair": True}
            RunStore.immutable_json(OUT / "failure.json", value)
            RunStore.atomic_json(OUT / "progress.json", {"state": "stopped" if isinstance(exc, InterruptedError) else "failed", **value})
            raise
    else:
        raise ValueError("Explicit prepare, launch or worker required")
