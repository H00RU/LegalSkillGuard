"""One queued fixed-context TRAIN evidence intervention; not a production layer."""
import copy
import fcntl
import json
import os
import signal
import sys
import time
import traceback
from pathlib import Path
from types import SimpleNamespace

from artifacts.launches.openexempt_skill_position_mechanism_20261027_run01 import cache_origin
from experiments.openexempt_online import Online, acceptance, freeze, native_claim_feedback, preserve
from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.learning.experiment import now, read, sha
from legal_skill_guard.openexempt import ROOT, metrics
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha

STOP = False
STUDIES = []


def stop_requested(*_):
    global STOP
    STOP = True
    for study in STUDIES:
        study.stop = True


def progress(chain, stage, **fields):
    if STOP:
        raise InterruptedError("Operator stopped the queued TRAIN mechanism probe")
    RunStore.atomic_json(chain / "queue_progress.json", {"at": now(), "stage": stage, **fields})


def observation_view(record, target):
    """The existing direct-answer teacher view, without additional trace tokens."""
    assert record.get("native_program") is None and record.get("execution_receipt") is None
    response = read(ROOT / record["raw_call_path"])["calls"][0]["response"]
    choice = response["choices"][0]
    message = choice["message"]
    reasoning, native = message.get("reasoning_content") or "", message.get("content") or ""
    emitted = {"raw_call_path": record["raw_call_path"], "finish_reason": choice["finish_reason"],
        "emitted_by_executor_unverified": True,
        "reasoning": {"text": reasoning[-1024:], "characters": len(reasoning),
                      "truncated_to_tail": len(reasoning) > 1024}}
    if record["parse_error"] is not None:
        emitted["failed_native_final"] = {"head": native[:256],
            "tail": native[-256:] if len(native) > 512 else native[256:],
            "characters": len(native), "middle_omitted": len(native) > 512}
    return {"case_id": record["case_id"], "family": record["family"],
        "executed_answer": (record.get("parsed") or {}).get("answer"),
        "parse_error": record["parse_error"], "execution_error": record.get("execution_error"),
        "score": copy.deepcopy(record["score"]),
        "native_claim_feedback": native_claim_feedback(record, target),
        "source_model_emitted_evidence": emitted}


def context(cfg):
    source = ROOT / "runs" / cfg["source_run"]
    parent_publication = read(source / "publications/b4.json")
    assert parent_publication["bank_sha256"] == cfg["parent_bank_sha256"]
    history = {(r["case_id"], r["family"]): r for r in
               parent_publication["training_decisions"][-1]["actual_replay"]}
    first = read(source / "batches/b5_prequential_records.json")["skills"]
    before = {**history, **{(r["case_id"], r["family"]): r for r in first}}
    assert len(history) == 128 and len(before) == 160 and max(k[0] for k in before) == 260
    original = json.loads(read(source / "teacher/b5_candidate2/wire_request.json")["user_prompt"])
    cases = {(c["source_case_id"], c["family"]): c for c in original["already_seen_training"]}
    assert len(cases) == 64 and csha(original["current_parent_library"]) == cfg["parent_bank_sha256"]
    for key, case in cases.items():
        p = before[key]
        assert case["actual_parent_answer"]["score"] == p["score"]
        assert case["actual_parent_answer"]["executed_answer"] == (p.get("parsed") or {}).get("answer")
    decision = read(source / "candidates/b5_candidate1.json")
    after = {(r["case_id"], r["family"]): r for r in decision["actual_replay"]}
    old_feedback = original["candidate_revision_feedback"][-1]
    for view in old_feedback["feedback_witness_replay"]:
        key = view["case_id"], view["family"]
        assert view == observation_view(after[key], cases[key]["original_training_target"])
    evidence = read(ROOT / cfg["selection_evidence"])
    chosen = evidence["intervention_eight_actual_witnesses"]
    assert len(chosen) == 8 and sum(z["outcome"] == "actual_safe_improvement" for z in chosen) == 4
    paired = copy.deepcopy(original)
    feedback = paired["candidate_revision_feedback"][-1]
    feedback["feedback_witness_replay"], feedback["feedback_reference_replay"] = [], []
    feedback["feedback_witness_roles"] = []
    for index, item in enumerate(chosen):
        key = item["case_id"], item["family"]
        old, new = before[key], after[key]
        assert key in cases and csha(old) == item["before_record_sha256"]
        assert csha(new) == item["after_record_sha256"]
        feedback["feedback_witness_replay"].append(observation_view(new, cases[key]["original_training_target"]))
        feedback["feedback_reference_replay"].append({"case_id": key[0], "family": key[1],
            "reference_location": "already_seen_training.actual_parent_answer",
            "reference_is_this_request_parent": True, "bank_sha256": old["bank_sha256"],
            "score": copy.deepcopy(old["score"]), "raw_call_path": old["raw_call_path"],
            "record_sha256": csha(old)})
        feedback["feedback_witness_roles"].append({"index": index, "case_id": key[0], "family": key[1],
            "role": "uncommitted_proposal", "selection_reason": item["outcome"]})
    feedback["feedback_witness_rule"] = evidence["intervention_selection_rule"]
    mandatory = {r["case_id"] for packet in (original, paired)
                 for f in packet["candidate_revision_feedback"] for r in f["feedback_witness_replay"]}
    for packet in (original, paired):
        packet["training_evidence_manifest"]["mandatory_feedback_witness_source_ids"] = sorted(mandatory)
        packet["training_evidence_manifest"]["rule"] = "fixed original T8 context; joint arm-witness union; no new cases or original labels"
        packet["candidate_feedback_contract"].update({"attempt": 1, "max_attempts": 1})
        assert mandatory <= set(packet["training_evidence_manifest"]["selected_source_ids"])
    assert all(original[k] == paired[k] for k in original if k != "candidate_revision_feedback")
    records = list(before.values())
    files = {source / "publications/b4.json", source / "batches/b5_prequential_records.json",
             source / "teacher/b5_candidate2/wire_request.json", source / "candidates/b5_candidate1.json",
             source / "candidates/b5_candidate2.json"}
    for batch in range(1, 6):
        path = source / f"batches/b{batch}_prequential_records.json"
        files.add(path)
        records.extend(read(path)["empty"])
    for name in ("b5_candidate1", "b5_candidate2"):
        d = read(source / f"candidates/{name}.json")
        records.extend(d.get("proposed_replay", d["actual_replay"]))
    assert all(r["case_id"] <= 260 for r in records)
    origins = {ROOT / r["raw_call_path"] for r in records}
    files.update(origins)
    files.update(p.with_suffix(".input.json") for p in origins)
    return {"packets": {"negative": original, "paired": paired}, "history": history,
            "first": first, "before": before, "publication": parent_publication,
            "origins": origins, "files": files}


def prepare(path):
    cfg = read(path)
    chain = ROOT / "artifacts/launches" / cfg["run_id"]
    ctx = context(cfg)
    assert sha(ROOT / cfg["source_config"].replace(".json", ".frozen.json")) == cfg["source_manifest_sha256"]
    assert sha(ROOT / "experiments/openexempt_online.py") == cfg["source_code_sha256"]
    for arm, packet in ctx["packets"].items():
        RunStore.immutable_json(chain / f"teacher_input_{arm}.json", packet)
    bound = {*ctx["files"], path.resolve(), Path(__file__).resolve(), ROOT / cfg["protocol"],
             ROOT / "experiments/openexempt_online.py",
             ROOT / "artifacts/launches/openexempt_skill_position_mechanism_20261027_run01.py",
             ROOT / cfg["source_config"], ROOT / cfg["source_config"].replace(".json", ".frozen.json"),
             ROOT / cfg["selection_evidence"], *(ROOT / p for p in cfg["arm_configs"].values()),
             *(chain / f"teacher_input_{arm}.json" for arm in ctx["packets"])}
    for arm_config in cfg["arm_configs"].values():
        bound.update(ROOT / name for name in read(ROOT / arm_config).get("inference_dependency_artifacts", []))
    bindings = {str(p.relative_to(ROOT)): sha(p) for p in sorted(bound)}
    plan = chain / "prepared_protocol.json"
    if plan.exists():
        assert read(plan)["files"] == bindings
    else:
        RunStore.immutable_json(plan, {"at": now(), "files": bindings, "prefix_sources": 80,
            "fixed_context_sources": 32, "two_fresh_teacher_responses_max": 2,
            "native_calls_max": 608, "future_TRAIN_sources": 48,
            "different_background_or_original_labels": False, "new_calls_during_prepare": 0})
    return cfg, chain, ctx


class FixedContextStudy(Online):
    """Diagnostic input isolation only; production Online and its gates unchanged."""
    def __init__(self, path, packet):
        self.packet = copy.deepcopy(packet)
        super().__init__(path)
        STUDIES.append(self)
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, stop_requested)

    def teacher_body(self, current, seen, observations, rejected):
        assert sorted({r["case_id"] for r in current}) == list(range(245, 261))
        assert len(seen) == len(observations) == 160
        assert csha(self.bank) == csha(self.packet["current_parent_library"])
        return copy.deepcopy(self.packet)

    def teacher_call(self, name, system, body, schema):
        assert body == self.packet
        # Identical outcome-neutral wording in BOTH fresh arms.
        system = system.replace("proposal errors from remaining regressions", "proposal outcomes from remaining regressions")
        system = system.replace("Witnesses concern actual changed requests, retained harms, and still-failed "
            "proposal evidence, not unchanged background errors.", "Witnesses concern actual changed-request "
            "improvements or errors, retained harms, and unresolved proposal evidence, not unchanged background errors.")
        self.actual_teacher_system_sha256 = csha(system)
        return super().teacher_call(name, system, body, schema)


def verify_receipt(path):
    receipt = read(path)
    assert len(receipt["paths"]) == 2
    assert all(sha(p["path"]) == p["sha256"] for p in receipt["paths"])


def run(path):
    cfg, chain, ctx = prepare(path)
    predecessor = ROOT / cfg["predecessor_chain"]
    source = ROOT / "runs" / cfg["source_run"]
    test = ROOT / "runs" / cfg["observed_TEST_run"]
    checkpoint = predecessor / "checkpoint_ready.json"
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, stop_requested)
    try:
        while not checkpoint.exists():
            progress(chain, "waiting_full8_and_observed_TEST_terminal_no_inference")
            if (predecessor / "pipeline_failure.json").exists():
                raise RuntimeError("Predecessor failed; do not bypass its actual test or preserve gate")
            stat = Path(f"/proc/{cfg['predecessor_pid']}/stat")
            try:
                ticks = stat.read_text().rsplit(")", 1)[1].split()[19]
            except FileNotFoundError:
                if checkpoint.exists():
                    break
                raise RuntimeError("Predecessor disappeared without its verified checkpoint")
            assert ticks == cfg["predecessor_start_ticks"]
            time.sleep(10)
        ready = read(checkpoint)
        assert ready["test_run"] == cfg["observed_TEST_run"]
        assert read(source / "completion.json")["status"] == "completed_bounded_mechanism_study"
        assert len(read(source / "completion.json")["batch_summary"]) == 8
        assert read(test / "completion.json")["status"] == "completed_observed_original_TEST_version_supplement"
        verify_receipt(source / "terminal_preservation.json")
        verify_receipt(test / "terminal_preservation.json")
        if ready["all8_endpoint_numeric_differences_positive"]:
            RunStore.immutable_json(chain / "completion.json", {"at": now(),
                "status": "skipped_existing_version_has_all8_numeric_gains", "new_native_calls": 0,
                "new_teacher_responses": 0, "full_goal_fresh_primary_and_paper_still_pending": True})
            return
        with (ROOT / "artifacts/openexempt_training.lock").open("a") as lock:
            while True:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    progress(chain, "waiting_predecessor_to_release_actual_training_lock")
                    time.sleep(5)
            manifest = read(ROOT / cfg["source_config"].replace(".json", ".frozen.json"))
            assert all(sha(ROOT / p) == digest for p, digest in manifest["files"].items())
            immutable = {ROOT / p for p in read(chain / "prepared_protocol.json")["files"]}
            immutable.update({chain / "prepared_protocol.json", ROOT / cfg["source_config"],
                ROOT / cfg["source_config"].replace(".json", ".frozen.json"), source / "completion.json",
                source / "terminal_preservation.json", test / "completion.json", test / "terminal_preservation.json"})
            RunStore.immutable_json(chain / "pre_probe_source_preservation.json", preserve(cfg["run_id"],
                "source-before-TRAIN-probe", [*manifest["files"], *(str(p.relative_to(ROOT)) for p in immutable)]))
            immutable.add(chain / "pre_probe_source_preservation.json")
            parent = ctx["publication"]["bank"]
            results, studies = {}, {}
            for arm, config in cfg["arm_configs"].items():
                arm_path = ROOT / config
                freeze(arm_path, additional_sources=immutable)
                study = FixedContextStudy(arm_path, ctx["packets"][arm])
                studies[arm] = study
                study.current_batch, study.latest = 5, copy.deepcopy(ctx["history"])
                if arm == "negative":
                    imported = SimpleNamespace(cfg=study.cfg, request_cache={})
                    for p in sorted(ctx["origins"]):
                        cache_origin(imported, p)
                    study.request_cache = imported.request_cache
                else:
                    study.request_cache = copy.deepcopy(studies["negative"].request_cache)
                RunStore.immutable_json(study.out / "prefix_raw_import.json", {
                    "at": now(), "raw_only_not_old_scores_or_parsed_answers": True,
                    "origins": [{"path": v["raw_call_path"], "sha256": sha(ROOT / v["raw_call_path"]),
                        "wire_sha256": sha((ROOT / v["raw_call_path"]).with_suffix(".input.json"))}
                        for _, v in sorted(study.request_cache.items())]})
                RunStore.immutable_json(study.out / "publications/b4.json", ctx["publication"])
                current = [r for r in study.rows if 245 <= r["case_id"] <= 260]
                seen = [r for r in study.rows if r["case_id"] <= 260]
                progress(chain, "one_fresh_teacher_then_full_prefix_admission", arm=arm)
                publication = study.update(current, seen, copy.deepcopy(ctx["first"]))
                assert len(study.teachers) == 1 and len(study.latest) == 160
                result = {"bank": study.bank, "bank_sha256": csha(study.bank),
                    "bank_changed": study.bank != parent, "prefix_before": metrics(list(ctx["before"].values())),
                    "prefix_after": metrics(list(study.latest.values())), "publication": publication,
                    "learning_native_calls": len(study.native), "learning_teacher_responses": len(study.teachers),
                    "teacher_system_sha256": study.actual_teacher_system_sha256}
                results[arm] = result
                RunStore.immutable_json(study.out / "prefix_complete.json", result)
            assert results["negative"]["teacher_system_sha256"] == results["paired"]["teacher_system_sha256"]
            banks = {"parent": parent, **{arm: v["bank"] for arm, v in results.items()}}
            RunStore.immutable_json(chain / "both_banks_fixed_before_subsequent_TRAIN.json", {
                "at": now(), "banks": banks, "future_TRAIN_targets_not_read": True})
            evaluator = studies["negative"]
            for key, value in studies["paired"].request_cache.items():
                if key in evaluator.request_cache:
                    assert evaluator.request_cache[key] == value
                else:
                    evaluator.request_cache[key] = copy.deepcopy(value)
            # Import ungraded native answers only, never the future scored-record files.
            future_imports = []
            for batch in (6, 7):
                for case in range(181 + (batch - 1) * 16, 181 + batch * 16):
                    for family in ("EC", "EV"):
                        rec = read(source / f"native/b{batch}_prequential/{case}_{family}_skills.answer.json")
                        assert "score" not in rec and rec["bank_sha256"] == cfg["parent_bank_sha256"]
                        p = ROOT / rec["raw_call_path"]
                        cache_origin(evaluator, p)
                        future_imports.append({"path": rec["raw_call_path"], "sha256": sha(p),
                                               "wire_sha256": sha(p.with_suffix(".input.json"))})
            RunStore.immutable_json(chain / "future_ungraded_native_import.json", future_imports)
            future_rows = [r for r in evaluator.rows if 261 <= r["case_id"] <= 308]
            assert len(future_rows) == 96
            forecasts = {}
            for arm, bank in banks.items():
                progress(chain, "subsequent_TRAIN48_all_arms_before_grading", arm=arm)
                forecasts[arm] = evaluator._dispatch.native(lambda row: evaluator.answer(
                    row, bank, "subsequent_TRAIN48", arm), future_rows)
            RunStore.immutable_json(chain / "all_subsequent_responses_before_grading.json", forecasts)
            assert all("score" not in r for records in forecasts.values() for r in records)
            evaluator.grade([r for records in forecasts.values() for r in records])
            parent_gate = acceptance(forecasts["parent"], forecasts["paired"], [], [])
            control_gate = acceptance(forecasts["negative"], forecasts["paired"], [], [])
            scores = {arm: metrics(records) for arm, records in forecasts.items()}
            parent_gain = scores["paired"]["mean_family_f1"] - scores["parent"]["mean_family_f1"]
            control_gain = scores["paired"]["mean_family_f1"] - scores["negative"]["mean_family_f1"]
            total_native = sum(len(s.native) for s in studies.values())
            total_teacher = sum(len(s.teachers) for s in studies.values())
            assert total_native <= 608 and total_teacher == 2
            result = {"at": now(), "status": "completed_fixed_context_paired_TRAIN_mechanism",
                "prefix_results": results, "subsequent_TRAIN_metrics": scores,
                "intervention_vs_parent_original_gate": parent_gate,
                "intervention_vs_fresh_control_original_gate": control_gate,
                "subsequent_native_mean_gain_vs_parent": parent_gain,
                "subsequent_native_mean_gain_vs_fresh_control": control_gain,
                "formal_adoption_accepted": results["paired"]["bank_changed"] and parent_gate["accepted"]
                    and control_gate["accepted"] and min(parent_gain, control_gain) > 1e-12,
                "actual_native_calls": total_native, "actual_teacher_responses": total_teacher,
                "native_prompt_tokens": sum(v["response"]["prompt_tokens"] for s in studies.values() for v in s.native),
                "native_completion_tokens": sum(v["response"]["completion_tokens"] for s in studies.values() for v in s.native),
                "prefix_learning_native_calls": {arm: v["learning_native_calls"] for arm, v in results.items()},
                "not_formal_training_TEST_validation_or_independent_replication": True,
                "new_production_source_or_full_build_not_automatically_started": True,
                "prospective_TEST_packet_not_opened": True}
            RunStore.immutable_json(chain / "paired_records.json", {
                "prefix_before": list(ctx["before"].values()),
                "prefix_after": {a: list(s.latest.values()) for a, s in studies.items()},
                "subsequent_TRAIN": forecasts})
            for arm, study in studies.items():
                RunStore.immutable_json(study.out / "completion.json", {"at": now(),
                    "status": result["status"], "arm": arm, "coordinator_result": str((chain / "completion.json").relative_to(ROOT)),
                    "learning_native_calls": results[arm]["learning_native_calls"], "learning_teacher_responses": 1,
                    "subsequent_TRAIN_metrics": scores[arm], "bank_sha256": csha(study.bank)})
            RunStore.immutable_json(chain / "completion.json", result)
    except BaseException as exc:
        RunStore.immutable_json(chain / "failure.json", {"at": now(), "error": repr(exc),
            "traceback": traceback.format_exc(), "actual_native_calls": sum(len(s.native) for s in STUDIES),
            "actual_teacher_responses": sum(len(s.teachers) for s in STUDIES), "no_answer_selection_or_fallback": True})
        raise
    finally:
        for study in STUDIES:
            study.progress("terminal", state="completed_TRAIN_probe" if (chain / "completion.json").exists() else "failed_TRAIN_probe")
        files = {str(p.relative_to(ROOT)) for p in chain.rglob("*") if p.is_file() and p.name != "queue_progress.json"}
        for study in STUDIES:
            files.update(str(p.relative_to(ROOT)) for p in study.out.rglob("*") if p.is_file())
        if files:
            RunStore.immutable_json(chain / "terminal_preservation.json", preserve(cfg["run_id"], "actual-terminal", sorted(files)))


if __name__ == "__main__":
    os.chdir(ROOT)
    action, config_path = sys.argv[1], Path(sys.argv[2]).resolve()
    if action == "prepare":
        cfg, chain, _ = prepare(config_path)
        print(json.dumps({"prepared": cfg["run_id"], "new_native_or_teacher_calls": 0}), flush=True)
    elif action == "run":
        run(config_path)
    else:
        raise ValueError("Use prepare or run")
