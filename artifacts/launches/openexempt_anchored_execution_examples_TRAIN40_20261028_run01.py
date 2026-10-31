"""One bounded TRAIN skill-content intervention; existing actor and scorer only."""
import copy
import fcntl
import json
import os
import sys
import time
import traceback
from pathlib import Path
from types import SimpleNamespace

from artifacts.launches.openexempt_skill_position_mechanism_20261027_run01 import cache_origin
from experiments.openexempt_online import (
    DIRECT_AUTHOR_SYSTEM, DIRECT_GUIDANCE, Online, acceptance, actor_payload, freeze,
    paired_effect, preserve,
)
from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.inference.native import WireClient
from legal_skill_guard.learning.experiment import now, read, sha
from legal_skill_guard.learning.publication import apply_differential_publication, differential_schema
from legal_skill_guard.learning.task_scoped_skills import validate_scoped_bank
from legal_skill_guard.openexempt import ROOT, metrics
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha


ADDITION = """
This is a declared execution-example intervention, not the unmodified original
teacher prompt and not a full formal-learning publication. The base observation
format remains native_claim_aligned_compact_v1. The diagnostic fields specify
the actual 20-source TRAIN comparison; no future or TEST utility is asserted.

Find EXECUTION_LAPSE: quote an existing correct rule that the actor failed to
follow. Do not diagnose every failure as missing legal knowledge. Do not rewrite
a correct rule merely because a final answer ignored it. If this evidence does
not support a reusable execution aid, return an empty delta and diagnoses.

For this single test, only UPDATE existing skills. Keep every original task,
jurisdiction, operators, when, avoid_when, and procedure verbatim. A changed
procedure must begin with its complete original text followed by a newline and
one compact pedagogical execution example. Do not reorganize the rule library.
Each changed task block needs its own diagnosis with an exact nonempty substring
of that block's original rule and supporting supplied source_case_ids.

Teach concrete final-answer behavior, not another abstract reminder. For an
independent-alternative omission, show how a supported specific citation and a
supported general citation both remain in one asset's final JSON. For a value
error, show binding to that asset's value rather than copying the statutory cap.
Use the actual public citation spelling, task schema and already-seen successful
claim fragments as evidence. Deidentify assets/debtors and replace instance
amounts with clear variables; any illustrative toy amount must be explicitly
labeled hypothetical, never claimed to be a new verified successful trajectory.
Do not store source IDs, exact training asset descriptions, full target answers,
an answer lookup, or a new executable program in skills. The illustration is a
teaching aid, never a current answer; each future case still requires the actor's
own legal eligibility decisions and numeric calculation. Do not add a planner,
reviewer, fallback, external tool, or a second memory layer. All operators stay
empty. Fit the existing complete-library cap, including unchanged skills.
Return the declared delta plus audit diagnoses only. Audit metadata is never
delivered to the actor. No quality retry or candidate selection is available.
"""


def inputs(config_path):
    cfg = read(config_path)
    assert cfg["selected_public_source_groups"] == read(ROOT / cfg["sample_origin_config"])["selected_public_source_groups"]
    original = read(ROOT / cfg["source_main_config"])
    assert all(cfg[k] == original[k] for k in
               ("generation", "phase_dispatch", "inference_environment", "input_packet", "grading_directory"))
    source = ROOT / "runs" / cfg["source_main_run"]
    publication = read(source / "publications/b8.json")
    assert publication["bank_sha256"] == cfg["parent_bank_sha256"]
    complete = read(source / "completion.json")
    assert len(complete["batch_summary"]) == 8 and complete["bank"] == publication["bank"]
    parent = publication["bank"]
    records = {(r["case_id"], r["family"]): r for r in
               publication["training_decisions"][-1]["actual_replay"]}
    assert len(records) == 256 and all(r["bank_sha256"] == csha(parent) for r in records.values())
    rows = read(ROOT / cfg["input_packet"])["rows"]
    ids = {i for values in cfg["selected_public_source_groups"].values() for i in values}
    teaching = {values[i] for values in cfg["selected_public_source_groups"].values() for i in (0, -1)}
    assert len(ids) == 20 and len(teaching) == 10 and teaching <= ids
    evaluation_rows = [r for r in rows if r["case_id"] in ids]
    teaching_rows = [r for r in rows if r["case_id"] in teaching]
    empty, frozen = [], []
    extra = {Path(__file__).resolve(), source / "publications/b8.json", source / "completion.json",
             ROOT / cfg["source_main_config"], ROOT / cfg["sample_origin_config"],
             ROOT / "artifacts/launches/openexempt_skill_position_mechanism_20261027_run01.py"}
    for batch in range(1, 9):
        path = source / f"batches/b{batch}_prequential_records.json"
        pre = read(path)
        empty.extend(pre["empty"])
        frozen.extend(pre["frozen_initial"])
        extra.add(path)
    formatter = SimpleNamespace(cfg=cfg, bank=parent, meter=WireClient(cfg["generation"]),
                                prequential_empty=empty, prequential_frozen=frozen)
    body = Online.teacher_body(formatter, teaching_rows, teaching_rows, records, [])
    assert len(body["already_seen_training"]) == 20
    for case in body["already_seen_training"]:
        record = records[(case["source_case_id"], case["family"])]
        case["actual_parent_answer"]["public_native_final_submission"] = record["public_label_submission"]
    body["diagnostic_teacher_intervention"] = {
        "name": "anchored_append_only_execution_examples_v1",
        "not_the_unmodified_original_v1_teacher_prompt": True,
        "parent_prior_TRAIN_exposure_sources": 128,
        "teacher_context_sources": sorted(teaching), "evaluation_TRAIN_sources": sorted(ids),
        "not_a_new_holdout_or_future_case_test": True, "candidate_banks_max": 1,
        "only_successful_native_fragments_are_verified_experience": True}
    old_ban = ("Do not store case IDs, debtors, exact asset names or values, answer tables, output "
               "format tricks, or copied target sets in skills.")
    assert old_ban in DIRECT_AUTHOR_SYSTEM
    system = DIRECT_AUTHOR_SYSTEM.replace(old_ban,
        "Do not store case IDs, debtors, exact asset names or instance values, answer tables, "
        "or copied target sets. A deidentified procedural output illustration is allowed "
        "under the diagnostic contract below, not a per-case answer or scoring trick.") + ADDITION
    delta_schema = differential_schema(("EC", "EV"), parent, sorted(teaching), guidance_schema=DIRECT_GUIDANCE)
    diagnosis = {"type": "object", "additionalProperties": False,
        "properties": {"skill_id": {"type": "string", "enum": [s["id"] for s in parent]},
            "task": {"type": "string", "enum": ["EC", "EV"]},
            "failure_type": {"type": "string", "enum": ["EXECUTION_LAPSE"]},
            "rule_anchor": {"type": "string"},
            "source_case_ids": {"type": "array", "minItems": 1,
                                "items": {"type": "integer", "enum": sorted(teaching)}}},
        "required": ["skill_id", "task", "failure_type", "rule_anchor", "source_case_ids"]}
    schema = {"type": "object", "additionalProperties": False,
              "properties": {"delta": delta_schema, "diagnoses": {"type": "array", "items": diagnosis}},
              "required": ["delta", "diagnoses"]}
    verified = SimpleNamespace(cfg=cfg, request_cache={})
    before = []
    for row in evaluation_rows:
        record = copy.deepcopy(records[(row["case_id"], row["family"])])
        raw = ROOT / record["raw_call_path"]
        wire = read(raw.with_suffix(".input.json"))
        messages, actual_schema, _ = actor_payload(row, parent, direct_numeric=True, asset_references=True)
        assert wire["messages"] == messages and wire["schema"] == actual_schema
        if not any(v["raw_call_path"] == record["raw_call_path"] for v in verified.request_cache.values()):
            cache_origin(verified, raw)
        extra.update((raw, raw.with_suffix(".input.json")))
        before.append(record)
    for record in [*empty, *frozen]:
        if record["case_id"] in teaching:
            raw = ROOT / record["raw_call_path"]
            extra.update((raw, raw.with_suffix(".input.json")))
    return cfg, parent, evaluation_rows, teaching, body, system, schema, before, verified, extra


def guarded_candidate(parent, result, teaching):
    for op in result["delta"]["operations"]:
        assert op["operation"] == "UPDATE" and len(op["target_ids"]) == 1
    candidate = apply_differential_publication(parent, result["delta"], ("EC", "EV"),
        sorted(teaching), guidance_schema=DIRECT_GUIDANCE)
    validate_scoped_bank(candidate)
    anchors = {(d["skill_id"], d["task"]): d for d in result["diagnoses"]}
    assert len(anchors) == len(result["diagnoses"])
    old = {s["id"]: s for s in parent}
    assert {s["id"] for s in candidate} == set(old)
    changed = []
    for skill in candidate:
        prior = old[skill["id"]]
        assert skill["hypothesis_ids"] == prior["hypothesis_ids"]
        a, b = skill["guidance"], prior["guidance"]
        assert a["jurisdiction"] == b["jurisdiction"] and a["operators"] == b["operators"] == []
        assert len(a["by_task"]) == len(b["by_task"])
        for block, previous in zip(a["by_task"], b["by_task"], strict=True):
            assert all(block[k] == previous[k] for k in ("tasks", "when", "avoid_when"))
            if block["procedure"] == previous["procedure"]:
                continue
            assert block["procedure"].startswith(previous["procedure"] + "\n")
            for task in block["tasks"]:
                key = skill["id"], task
                assert key in anchors
                anchor = anchors[key]["rule_anchor"]
                assert len(anchor) >= 20 and any(anchor in previous[k] for k in ("when", "procedure", "avoid_when"))
                changed.append(key)
    assert set(changed) == set(anchors)
    return candidate, changed


def run(config_path):
    started = time.monotonic()
    cfg, parent, rows, teaching, body, system, schema, before, verified, extra = inputs(config_path)
    out = ROOT / "runs" / cfg["run_id"]
    chain = ROOT / "artifacts/launches" / cfg["run_id"]
    assert not out.exists()
    for name, value in (("teacher_body.json", body), ("teacher_schema.json", schema),
                        ("teacher_system.json", {"system": system})):
        RunStore.immutable_json(chain / name, value)
        extra.add(chain / name)
    freeze(config_path, additional_sources=extra)
    study, status = None, "failed"
    try:
        with (ROOT / "artifacts/openexempt_training.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            study = Online(config_path)
            assert study.bank == parent
            study.request_cache = verified.request_cache
            RunStore.immutable_json(out / "mechanism_started.json", {"at": now(), "pid": os.getpid(),
                "birth_ticks": Path(f"/proc/{os.getpid()}/stat").read_text().rsplit(")", 1)[1].split()[19],
                "parent_bank_sha256": csha(parent), "teacher_sources": sorted(teaching),
                "fixed_evaluation_sources": sorted({r["case_id"] for r in rows})})
            result = study.teacher_call("one_execution_example_candidate", system, body, schema)
            assert len(study.teachers) == 1
            candidate, changed = guarded_candidate(parent, result, teaching)
            tokens = study.meter.token_count(text=json.dumps(candidate, ensure_ascii=False, separators=(",", ":")))
            assert tokens <= cfg["library_token_hard_cap"]
            RunStore.immutable_json(out / "candidate_fixed_before_new_answers.json", {
                "bank": candidate, "bank_sha256": csha(candidate), "tokens": tokens,
                "changed_task_blocks": changed, "delta_and_audit": result})
            after = study._dispatch.native(lambda row: study.answer(
                row, candidate, "anchored_examples_TRAIN40", "candidate"), rows)
            assert len(study.native) <= cfg["new_native_calls_max"] == 40
            expected = {(r["case_id"], r["family"]): r.pop("score") for r in before}
            RunStore.immutable_json(out / "all_responses_before_new_grading.json", {"parent": before, "candidate": after})
            study.grade(before + after)
            assert all(r["score"] == expected[(r["case_id"], r["family"])] for r in before)
            bm, am = metrics(before), metrics(after)
            gate = acceptance(before, after, [], [])
            ec_gain = am["EC"]["f1"] - bm["EC"]["f1"]
            adopt = gate["accepted"] and ec_gain + 1e-12 >= cfg["adoption_minimum_EC_native_gain"]
            RunStore.immutable_json(out / "paired_records.json", {"parent": before, "candidate": after})
            status = "completed_anchored_execution_examples_TRAIN_probe"
            RunStore.immutable_json(out / "completion.json", {"at": now(), "status": status,
                "parent_metrics": bm, "candidate_metrics": am, "EC_native_gain": ec_gain,
                "original_complete_quality_gate": gate, "formal_adoption_accepted": adopt,
                "parent_bank_sha256": csha(parent), "candidate_bank_sha256": csha(candidate),
                "candidate_tokens": tokens, "changed_task_blocks": changed,
                "actual_native_calls": len(study.native), "actual_teacher_responses": len(study.teachers),
                "actual_teacher_attempts": study.teacher_attempts,
                "cross_stage_identical_wire_reuses": len(study.reuse_events),
                "elapsed_seconds": time.monotonic() - started,
                "native_prompt_tokens": sum(r["response"]["prompt_tokens"] for r in study.native),
                "native_completion_tokens": sum(r["response"]["completion_tokens"] for r in study.native),
                "new_baseline_generations": 0, "paired_effect": paired_effect(before, after),
                "not_TEST_independent_repeat_or_component_causal_identification": True,
                "new_full_build_not_automatically_started": True})
    except BaseException as exc:
        RunStore.immutable_json(out / "failure.json", {"at": now(), "error": repr(exc),
            "traceback": traceback.format_exc(), "no_candidate_retry_or_fallback": True,
            "actual_native_calls": len(study.native) if study else 0,
            "actual_teacher_responses": len(study.teachers) if study else 0})
        raise
    finally:
        if study is not None:
            study.progress("terminal", state=status)
        names = {str(p.relative_to(ROOT)) for p in out.rglob("*") if p.is_file()}
        names.update(str(p.relative_to(ROOT)) for p in chain.rglob("*") if p.is_file())
        RunStore.immutable_json(out / "terminal_preservation.json", preserve(cfg["run_id"], "actual-terminal", sorted(names)))


if __name__ == "__main__":
    os.chdir(ROOT)
    run(Path(sys.argv[1]).resolve())
