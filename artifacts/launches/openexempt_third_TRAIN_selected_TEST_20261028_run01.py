"""Evaluate the complete third bank selected on TRAIN before fourth TEST scores."""
import fcntl
import os
import signal
import sys
import time
import traceback
from pathlib import Path

from artifacts.launches.openexempt_deadline12h_pipeline_20261028_run01 import version_supplement
from experiments.openexempt_online import actor_payload, preserve
from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.learning.experiment import now, read, sha

from legal_skill_guard.openexempt import ROOT

STOP = False


def stop_requested(*_):
    global STOP
    STOP = True


def progress(chain, stage, **fields):
    if STOP:
        raise InterruptedError("Operator stopped the reference-test queue")
    RunStore.atomic_json(chain / "progress.json", {"at": now(), "stage": stage, **fields})


def verify_archive(path):
    receipt = read(path)
    assert len(receipt["paths"]) == 2
    assert all(sha(v["path"]) == v["sha256"] for v in receipt["paths"])


def prepare(path):
    cfg = read(path)
    chain = ROOT / "artifacts/launches" / cfg["run_id"]
    test_cfg = read(ROOT / cfg["test_config"])
    source = ROOT / "runs" / cfg["source_training_run"]
    publication = read(source / "publications/b8.json")
    assert publication["bank_sha256"] == cfg["expected_bank_sha256"]
    complete = read(source / "completion.json")
    assert complete["status"] == "completed_bounded_mechanism_study" and len(complete["batch_summary"]) == 8
    evidence = read(ROOT / cfg["TRAIN_decision_evidence"])
    old, new = evidence["versions"]
    assert old["run_id"] == cfg["source_training_run"]
    for family in ("EC", "EV"):
        for metric in ("f1", "full_output_f1"):
            assert old["actual_final_TRAIN_metrics"][family][metric] > new["actual_final_TRAIN_metrics"][family][metric]
    source_cfg = read(ROOT / test_cfg["source_training_config"])
    rows = {(r["case_id"], r["family"]): r for r in read(ROOT / source_cfg["input_packet"])["rows"]}
    accepted = [d for d in publication["training_decisions"] if d["accepted"]]
    records = accepted[-1]["actual_replay"]
    assert len(records) == 256
    for record in records:
        row = rows[record["case_id"], record["family"]]
        messages, schema, _ = actor_payload(row, publication["bank"], grounded=True,
            direct_numeric=True, asset_references=True, skill_delivery_contract=test_cfg["skill_delivery_contract"])
        original = read((ROOT / record["raw_call_path"]).with_suffix(".input.json"))
        assert messages == original["messages"] and schema == original["schema"]
    paths = {path.resolve(), Path(__file__).resolve(), ROOT / cfg["test_config"],
        ROOT / cfg["TRAIN_decision_evidence"], ROOT / test_cfg["source_training_config"],
        (ROOT / test_cfg["source_training_config"]).with_suffix(".frozen.json"),
        source / "publications/b8.json", source / "completion.json", source / "terminal_preservation.json",
        ROOT / "artifacts/launches/openexempt_deadline12h_pipeline_20261028_run01.py",
        ROOT / "experiments/openexempt_online.py"}
    bindings = {str(p.relative_to(ROOT)): sha(p) for p in sorted(paths)}
    plan = chain / "prepared_protocol.json"
    if plan.exists():
        assert read(plan)["files"] == bindings
    else:
        predecessor = ROOT / "runs" / cfg["predecessor_test_run"]
        assert not (predecessor / "completion.json").exists()
        assert not (ROOT / "runs" / test_cfg["run_id"]).exists()
        RunStore.immutable_json(plan, {"at": now(), "files": bindings,
            "method_chosen_before_fourth_TEST_scores": True,
            "selection_basis": "both native/full families on complete128 TRAIN; not the old TEST",
            "actual_completed_B8_only_no_best_prefix": True,
            "original_third_training_interface_verified_same256_TRAIN_wires": True,
            "new_teacher_calls": 0, "new_native_calls_during_prepare": 0,
            "new_primary_not_opened_and_independent_learning_repeats_deferred": True})
    return cfg, chain


def run(path):
    cfg, chain = prepare(path)
    predecessor = ROOT / cfg["predecessor_chain"]
    checkpoint = predecessor / "checkpoint_ready.json"
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, stop_requested)
    try:
        while not checkpoint.exists():
            progress(chain, "waiting_fourth_frozen_TEST_terminal_no_inference")
            if (predecessor / "pipeline_failure.json").exists():
                raise RuntimeError("Fourth TEST failed; do not bypass its completion or preservation")
            try:
                ticks = Path(f"/proc/{cfg['predecessor_pid']}/stat").read_text().rsplit(")", 1)[1].split()[19]
            except FileNotFoundError:
                if checkpoint.exists():
                    break
                raise RuntimeError("Predecessor disappeared without a completed checkpoint")
            assert ticks == cfg["predecessor_start_ticks"]
            time.sleep(10)
        assert read(checkpoint)["test_run"] == cfg["predecessor_test_run"]
        old_test = ROOT / "runs" / cfg["predecessor_test_run"]
        assert read(old_test / "completion.json")["status"] == "completed_observed_original_TEST_version_supplement"
        verify_archive(old_test / "terminal_preservation.json")
        verify_archive(ROOT / "runs" / cfg["source_training_run"] / "terminal_preservation.json")
        with (ROOT / "artifacts/openexempt_training.lock").open("a") as lock:
            while True:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    progress(chain, "waiting_original_inference_lock")
                    time.sleep(5)
            progress(chain, "fixed_third_B8_version_TEST_no_learning_or_updated_selection")
            result = version_supplement(ROOT / cfg["test_config"], chain)
            assert result["source_training_run"] == cfg["source_training_run"]
            RunStore.immutable_json(chain / "checkpoint_ready.json", {"at": now(),
                "test_run": read(ROOT / cfg["test_config"])["run_id"],
                "source_training_run": cfg["source_training_run"],
                "all8_endpoint_numeric_differences_positive": result["all8_endpoint_numeric_differences_positive"],
                "method_selection_frozen_on_TRAIN_before_fourth_TEST_scores": True,
                "full_goal_new_primary_fair_controls_and_paper_not_complete": True})
            progress(chain, "reference_TEST_complete_full_goal_active")
    except BaseException as exc:
        RunStore.immutable_json(chain / "pipeline_failure.json", {"at": now(), "error": repr(exc),
            "traceback": traceback.format_exc(), "no_best_response_or_source_replacement": True})
        raise
    finally:
        names = [str(p.relative_to(ROOT)) for p in chain.rglob("*") if p.is_file()
                 and p.name not in ("progress.json", "pipeline_progress.json")]
        if names:
            RunStore.immutable_json(chain / "terminal_preservation.json", preserve(cfg["run_id"], "actual-terminal", names))


if __name__ == "__main__":
    os.chdir(ROOT)
    action, path = sys.argv[1], Path(sys.argv[2]).resolve()
    if action == "prepare":
        cfg, chain = prepare(path)
        print({"prepared": cfg["run_id"], "new_teacher_or_native_calls": 0}, flush=True)
    elif action == "run":
        run(path)
    else:
        raise ValueError("Use prepare or run")
