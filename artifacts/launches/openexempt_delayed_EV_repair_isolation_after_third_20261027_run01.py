"""One bounded TRAIN causal replay after the live formal process exits."""
import copy
import fcntl
import importlib.metadata
import json
import os
import sys
import time
import traceback
from pathlib import Path

from experiments.openexempt_online import Online, acceptance, actor_payload, freeze, paired_effect, preserve
from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.learning.experiment import now, read, sha
from legal_skill_guard.learning.task_scoped_skills import task_view, validate_scoped_bank
from legal_skill_guard.openexempt import ROOT, metrics
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha


def fingerprint(cfg, row, bank):
    messages, schema, _ = actor_payload(row, bank, grounded=True, direct_numeric=True, asset_references=True)
    return csha({"messages": messages, "schema": schema, "generation": cfg["generation"]})


def load_origins(source, cfg):
    """Uniform original raw-response reuse, including length-ended responses."""
    cache, index = {}, []
    for path in sorted((source / "native").rglob("*.json")):
        if path.name.endswith((".input.json", ".answer.json")):
            continue
        raw, supplied = read(path), read(path.with_suffix(".input.json"))
        assert raw.get("transport_error") is None and len(raw["calls"]) == 1
        wire, observed, response = raw["calls"][0]["request"], raw["calls"][0]["response"], raw["response"]
        assert wire["messages"] == supplied["messages"]
        assert wire["response_format"]["json_schema"]["schema"] == supplied["schema"]
        assert all(wire[k] == cfg["generation"][k] for k in
                   ("model", "temperature", "top_p", "top_k", "max_tokens", "seed"))
        assert wire.get("chat_template_kwargs", {}).get("enable_thinking", True) == (
            not cfg["generation"]["disable_thinking"])
        assert observed["id"] == response["raw_id"]
        assert observed["usage"]["prompt_tokens"] == response["prompt_tokens"]
        assert observed["usage"]["completion_tokens"] == response["completion_tokens"]
        assert (observed["choices"][0]["message"].get("content") or "").strip() == response["content"]
        key = csha({"messages": supplied["messages"], "schema": supplied["schema"],
                    "generation": cfg["generation"]})
        assert key not in cache, "Multiple physical origins must not be quality-selected"
        cache[key] = {"response": copy.deepcopy(response), "raw_call_path": str(path.relative_to(ROOT))}
        index.append({"fingerprint": key, "raw_call_path": str(path.relative_to(ROOT)),
                      "raw_sha256": sha(path), "input_sha256": sha(path.with_suffix(".input.json"))})
    assert len(cache) == read(source / "completion.json")["actual_native_calls"]
    return cache, index


def wait_and_check_source(cfg, chain):
    while True:
        process = Path("/proc") / str(cfg["source_main_pid"]) / "stat"
        if not process.exists():
            break
        assert process.read_text().rsplit(") ", 1)[1].split()[19] == cfg["source_main_start_ticks"]
        progress = read(ROOT / "runs" / cfg["source_main_run"] / "progress.json")
        RunStore.atomic_json(chain / "progress.json", {
            "at": now(), "state": "waiting_for_actual_main_exit_no_GPU_or_teacher",
            "queue_pid": os.getpid(), "actual_main_pid": cfg["source_main_pid"],
            "main_stage": progress["stage"], "main_native": progress["completed_native_calls"]})
        time.sleep(20)
    source = ROOT / "runs" / cfg["source_main_run"]
    complete = read(source / "completion.json")
    assert complete["status"] == "completed_bounded_mechanism_study" and len(complete["batch_summary"]) == 8
    assert not (source / "failure.json").exists()
    assert read(source / "publications/b8.json")["bank"] == complete["bank"]
    terminal = read(source / "terminal_preservation.json")
    assert len(terminal["paths"]) == 2
    for item in terminal["paths"]:
        path = Path(item["path"])
        assert path.name == cfg["source_main_run"] + "-actual-terminal.tar.gz"
        assert sha(path) == item["sha256"]
    source_path = ROOT / cfg["source_main_config"]
    manifest_path = source_path.with_suffix(".frozen.json")
    assert sha(source_path) == cfg["source_main_config_sha256"]
    assert sha(manifest_path) == cfg["source_main_manifest_sha256"]
    manifest, source_cfg = read(manifest_path), read(source_path)
    assert all(sha(ROOT / p) == h for p, h in manifest["files"].items())
    assert {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()} == manifest["packages"]
    assert all(cfg[k] == source_cfg[k] for k in
               ("generation", "phase_dispatch", "input_packet", "grading_directory", "inference_environment"))
    model = Path("/proc") / str(cfg["source_model_pid"]) / "stat"
    assert model.read_text().rsplit(") ", 1)[1].split()[19] == cfg["source_model_start_ticks"]
    return source, manifest


def run_isolation(config_path, source, source_manifest, chain):
    cfg = read(config_path)
    assert "teacher" not in cfg and cfg["new_teacher_calls_max"] == 0
    assert cfg["study_kind"] == "retrospective_delayed_repair_TRAIN_causal_replay_not_formal_learning"
    out = ROOT / "runs" / cfg["run_id"]
    assert not out.exists() and not config_path.with_suffix(".frozen.json").exists()
    parent = read(ROOT / cfg["initial_library_publication"])["bank"]
    original = read(ROOT / cfg["original_full_proposal_path"])
    banks = {"parent": parent, "original_mixed": original["proposed_bank"],
             "isolated": read(ROOT / cfg["isolated_bank_path"])}
    assert {name: csha(bank) for name, bank in banks.items()} == cfg["bank_sha256"]
    response_path = ROOT / cfg["source_teacher_response"]
    assert sha(response_path) == cfg["source_teacher_response_sha256"]
    skill = next(o["skill"] for o in read(response_path)["value"]["operations"]
                 if (o.get("skill") or {}).get("id") == "federal-specific-personal-property-boundaries")
    repaired = next(s for s in banks["isolated"] if s["id"] == skill["id"])
    assert next(b for b in repaired["guidance"]["by_task"] if b["tasks"] == ["EV"]) == next(
        b for b in skill["guidance"]["by_task"] if b["tasks"] == ["EV"])
    assert task_view(banks["isolated"], "EC") == task_view(parent, "EC")
    assert [s for s in banks["isolated"] if s["id"] != skill["id"]] == [s for s in parent if s["id"] != skill["id"]]
    for bank in banks.values():
        validate_scoped_bank(bank)
        assert all(not s["guidance"]["operators"] for s in bank)
    rows = [r for r in read(ROOT / cfg["input_packet"])["rows"]
            if cfg["source_id_start"] <= r["case_id"] <= cfg["source_id_end"]]
    assert len(rows) == 192 and len({r["source_key"] for r in rows}) == 96
    work = {name: [r for r in rows if r["case_id"] <= cfg["original_gate_seen_source_id_end"]
                  or (name != "original_mixed" and r["family"] == "EV")] for name in banks}
    cache, index = load_origins(source, cfg)
    used, new = set(), set()
    for name, selected in work.items():
        for row in selected:
            key = fingerprint(cfg, row, banks[name])
            if key in cache:
                used.add(cache[key]["raw_call_path"])
            else:
                assert name == "isolated" and row["family"] == "EV", "No baseline regeneration"
                new.add(key)
    assert len(new) <= cfg["new_native_calls_max"]
    index_path = RunStore.immutable_json(chain / "raw_source_index_and_plan.json", {
        "at": now(), "all_physical_origins": index, "new_native_upper_bound": len(new),
        "logical_tasks": {name: len(values) for name, values in work.items()},
        "no_quality_selection_no_teacher_no_new_baseline": True})
    extra = {ROOT / p for p in source_manifest["files"]}
    extra.update({Path(__file__).resolve(), index_path, response_path,
                  ROOT / cfg["isolated_bank_path"], ROOT / cfg["original_full_proposal_path"],
                  source / "completion.json", source / "terminal_preservation.json",
                  (ROOT / cfg["source_main_config"]).with_suffix(".frozen.json")})
    for name in used:
        p = ROOT / name
        extra.update((p, p.with_suffix(".input.json")))
    freeze(config_path, additional_sources=extra)
    study = None
    try:
        study = Online(config_path)
        study.rows, study.current_batch, study.request_cache = rows, 3, cache
        study.check()
        assert study.bank == parent
        for bank in banks.values():
            assert study.meter.token_count(text=json.dumps(bank, ensure_ascii=False, separators=(",", ":"))) <= 4096
        RunStore.immutable_json(out / "diagnostic_started.json", {
            "at": now(), "actual_pid": os.getpid(), "not_a_formal_build_or_learning_repeat": True,
            "max_new_native": len(new), "original_gate_sources": 48,
            "subsequent_retrospective_TRAIN_EV_sources": 48, "teacher_calls": 0})
        variants = {}
        for name, selected in work.items():
            variants[name] = study._dispatch.native(
                lambda r: study.answer(r, banks[name], "delayed_" + name, name), selected)
            if name != "isolated":
                assert len(study.native) == 0, "Historical parent/mixed must never be regenerated"
        assert len(study.native) == len(new) and len(study.native) <= 56
        RunStore.immutable_json(out / "all_responses_before_any_new_grading.json", variants)
        for values in variants.values():
            study.grade(values)
        RunStore.immutable_json(out / "scored_records.json", variants)
        expected = {(r["case_id"], r["family"]): r["score"] for r in original["proposed_replay"]}
        assert all(r["score"] == expected[r["case_id"], r["family"]] for r in variants["original_mixed"])
        seen_end, current_start = cfg["original_gate_seen_source_id_end"], cfg["original_gate_current_source_id_start"]
        def cohort(name, which):
            return [r for r in variants[name] if
                (current_start <= r["case_id"] <= seen_end if which == "current" else r["case_id"] < current_start)]
        gates = {name: acceptance(cohort("parent", "current"), cohort(name, "current"),
                                 cohort("parent", "prior"), cohort(name, "prior"))
                 for name in ("original_mixed", "isolated")}
        assert gates["original_mixed"]["accepted"] == original["proposed_whole_bank_acceptance"]["accepted"] is False
        later = {name: [r for r in variants[name] if r["case_id"] >= cfg["subsequent_EV_source_id_start"]]
                 for name in ("parent", "isolated")}
        assert all(len(v) == 48 for v in later.values())
        lm = {name: metrics(v)["EV"] for name, v in later.items()}
        safe = all(lm["isolated"][k] <= lm["parent"][k] for k in
                   ("invalid_format", "negative_or_unscored_asset_claims"))
        supported = (gates["isolated"]["accepted"] and lm["isolated"]["f1"] > lm["parent"]["f1"] + 1e-12
                     and lm["isolated"]["full_output_f1"] >= lm["parent"]["full_output_f1"] - 1e-12 and safe)
        result = {"at": now(), "status": "completed_bounded_TRAIN_causal_isolation",
            "bank_sha256": cfg["bank_sha256"], "original_full_gate": gates,
            "original_seen48_metrics": {name: metrics([r for r in values if r["case_id"] <= seen_end])
                                        for name, values in variants.items()},
            "subsequent_TRAIN48_EV_metrics": lm,
            "subsequent_TRAIN48_EV_effect": paired_effect(later["parent"], later["isolated"]),
            "coupled_repair_hypothesis_conditionally_supported": supported,
            "not_a_new_TEST_or_general_method_success_claim": True,
            "actual_native_calls": len(study.native), "actual_teacher_calls": len(study.teachers),
            "native_prompt_tokens": sum(v["response"]["prompt_tokens"] for v in study.native),
            "native_completion_tokens": sum(v["response"]["completion_tokens"] for v in study.native),
            "prior_raw_origins_not_new_calls": len(cache) - len(study.native),
            "raw_wire_reuses_not_independent_draws": len(study.reuse_events),
            "automatic_new_training_or_TEST": False}
        assert result["actual_teacher_calls"] == 0
        RunStore.immutable_json(out / "completion.json", result)
        study.progress("terminal", state=result["status"])
        return result
    except BaseException as exc:
        RunStore.immutable_json(out / "failure.json", {"at": now(), "error": repr(exc),
            "traceback": traceback.format_exc(), "actual_native_calls": len(study.native) if study else 0,
            "no_retry_or_answer_selection": True})
        raise
    finally:
        names = [str(p.relative_to(ROOT)) for p in out.rglob("*") if p.is_file() and "/cache/" not in str(p)]
        RunStore.immutable_json(out / "terminal_preservation.json", preserve(cfg["run_id"], "actual-terminal", names))


def main(config_path):
    cfg = read(config_path)
    chain = ROOT / "artifacts/launches" / cfg["run_id"]
    RunStore.immutable_json(chain / "queued.json", {"at": now(), "queue_pid": os.getpid(),
        "config_sha256": sha(config_path), "script_sha256": sha(Path(__file__)),
        "protocol_sha256": sha(ROOT / cfg["protocol"]),
        "isolated_bank_file_sha256": sha(ROOT / cfg["isolated_bank_path"]),
        "wait_for_actual_main_exit": cfg["source_main_pid"], "no_concurrent_GPU_job": True,
        "does_not_start_matched_full_controls_or_TEST": True})
    try:
        source, manifest = wait_and_check_source(cfg, chain)
        queued = read(chain / "queued.json")
        assert sha(config_path) == queued["config_sha256"]
        assert sha(Path(__file__)) == queued["script_sha256"]
        assert sha(ROOT / cfg["protocol"]) == queued["protocol_sha256"]
        assert sha(ROOT / cfg["isolated_bank_path"]) == queued["isolated_bank_file_sha256"]
        with (ROOT / "artifacts/openexempt_training.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            RunStore.atomic_json(chain / "progress.json", {"at": now(), "state": "starting_controlled_TRAIN_isolation",
                                                        "actual_pid": os.getpid()})
            result = run_isolation(config_path, source, manifest, chain)
        RunStore.atomic_json(chain / "progress.json", {"at": now(), "state": result["status"],
                                                     "actual_native_calls": result["actual_native_calls"]})
    except BaseException as exc:
        RunStore.immutable_json(chain / "failure.json", {"at": now(), "error": repr(exc), "traceback": traceback.format_exc()})
        raise


if __name__ == "__main__":
    os.chdir(ROOT)
    main(Path(sys.argv[1]).resolve())
