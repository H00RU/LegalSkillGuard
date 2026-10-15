"""One durable entry point for preparation, background learning and reporting."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from legal_skill_guard.data import prepare_packets
from legal_skill_guard.experiment.storage import RunStore, safe_component
from legal_skill_guard.learning.experiment import ROOT, Comparison, read, sha
from legal_skill_guard.report import write_report


def study_for(config, run_id):
    method = read(config).get("method", "callable")
    if method == "answer_review":
        from legal_skill_guard.learning.review import ReviewStudy

        return ReviewStudy(config, run_id=run_id)
    if method != "callable":
        raise ValueError("Unknown declared learning method")
    return Comparison(config, run_id=run_id)


def prepare(config):
    cfg = read(config)
    frozen = config.with_suffix(".frozen.json")
    if frozen.exists():
        raise FileExistsError("Already frozen; use a new config for any change")
    if cfg.get("method", "callable") == "answer_review":
        from legal_skill_guard.learning.review import prepare_review_packets

        selection = prepare_review_packets(ROOT, cfg)
    elif cfg.get("method", "callable") == "callable":
        selection = prepare_packets(ROOT, cfg)
    else:
        raise ValueError("Unknown declared learning method")
    pid = cfg["model_process_pid"]  # Explicit identity; never discover/substitute another.
    proc = Path("/proc") / str(pid)
    argv = [v.decode() for v in (proc / "cmdline").read_bytes().split(b"\0") if v]
    if not any("Qwen3-8B" in v for v in argv) or "--served-model-name" not in argv:
        raise RuntimeError("Original frozen 8B process identity unavailable")
    environment = {
        "at": datetime.now(UTC).isoformat(),
        "pid": pid,
        "actual_argv": argv,
        "process_start_ticks": (proc / "stat").read_text().rsplit(")", 1)[1].split()[19],
        "model_on_disk_missing_after_incident": True,
        "same_live_loaded_model_not_restarted_or_redownloaded": True,
        "weight_file_sha256_not_recovered": True,
        "tokenizer_access": "same serving vLLM /tokenize; no local substitute",
        "environment_reconstruction_not_bitwise_historical_environment": True,
    }
    RunStore.immutable_json(ROOT / cfg["inference_environment"], environment)
    ledger = ROOT / cfg["teacher"]["ledger"]
    if not ledger.exists():
        RunStore.immutable_json(
            ledger,
            {
                "schema_version": 2,
                "model": cfg["teacher"]["model"],
                "max_invocations": cfg["teacher"]["total_invocation_budget"],
                "historical_count_lower_bound": 1225,
                "reservations": [],
                "historical_reservation_records_missing": True,
                "lower_bound_basis": "1190 reservations before Oct14 main + at least35 main teacher attempts before deletion; raw prefix lost",
                "count_is_not_an_exact_recovery_of_historical_usage": True,
                "new_reservations_only_no_fabricated_historical_records": True,
            },
        )
    paths = sorted((ROOT / "legal_skill_guard").rglob("*.py"))
    paths += sorted((ROOT / "third_party").rglob("*.py"))
    paths += sorted(
        p
        for p in (ROOT / "third_party").rglob("*")
        if p.is_file() and (p.suffix in (".txt", ".md") or p.name == "LICENSE")
    )
    paths += [
        config,
        ROOT / cfg["input_packet"],
        ROOT / cfg["grading_only"],
        ROOT / cfg["preselection"],
        ROOT / cfg["inference_environment"],
        ROOT / "pyproject.toml",
        ROOT / "uv.lock",
        ROOT / "docs/METHOD_AND_PROTOCOL.md",
    ]
    if "method_protocol" in cfg:
        paths.append(ROOT / cfg["method_protocol"])
    RunStore.immutable_json(
        frozen,
        {
            "at": datetime.now(UTC).isoformat(),
            "config_sha256": sha(config),
            "files": {str(p.resolve()): sha(p) for p in sorted(set(paths))},
            "mutable_ledgers_logs_and_status_not_bound": True,
        },
    )
    return {
        "frozen": str(frozen),
        "train_sources": len(selection["training_ids"]),
        "future_sources": len(selection["future_ids"]),
        "model_calls": 0,
        "teacher_calls": 0,
    }


def verify_learning(study):
    """One actual experience update; a reconstruction check, not method evidence."""
    study.cfg = {**study.cfg, "planned_new_native_calls": 2, "planned_new_teacher_calls": 1}
    study.training = study.training[:1]
    study.future = []
    study.current_batch = 1
    study.check()
    RunStore.immutable_json(
        study.out / "declaration.json",
        {
            "at": datetime.now(UTC).isoformat(),
            "run_id": study.run_id,
            "purpose": "engineering_reconstruction_one_seen_document_only",
            "not_a_method_comparison_or_paper_metric": True,
            "gold_is_training_feedback_only": True,
            "config_overrides": {
                "planned_native": 2,
                "planned_teacher": 1,
                "training_ids": [study.training[0]["id"]],
            },
            "original_config": study.cfg,
            "frozen_bindings": study.bindings,
        },
    )
    RunStore.immutable_json(study.out / "launch.json", {"pid": os.getpid(), "argv": sys.argv})
    row = study.training[0]
    before = study.collect("reconstruction_before", "experience", [row], [])
    study.before["experience"][row["id"]] = before
    bank = study.update_callable("experience", 1)
    after = study.collect("reconstruction_after", "experience", [row], bank)
    from legal_skill_guard.learning.audit import close, original_score

    for u in before + after:
        expected = original_score(
            u["response"], row, row["annotation_sets"][0]["annotations"], list(study.labels)
        )
        close(expected, {k: u[k] for k in expected})
    value = {
        "at": datetime.now(UTC).isoformat(),
        "purpose": "engineering_reconstruction_only",
        "native_calls": len(study.native),
        "teacher_calls": len(study.teachers),
        "actual_document_id": row["id"],
        "before_public_valid": before[0]["public_valid"],
        "after_public_valid": after[0]["public_valid"],
        "published_skill_count": len(bank),
        "actual_original_feedback_reaches_teacher_and_publication_reaches_lawyer": True,
        "independent_score_agrees": True,
        "not_evidence_of_learning_generalization": True,
    }
    RunStore.immutable_json(study.out / "engineering_completion.json", value)
    RunStore.atomic_json(study.out / "progress.json", {"state": "completed", **value})
    return value


def worker(config, run_id, engineering):
    lock = ROOT / "artifacts/gpu_generation.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("a+") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        study = study_for(config, run_id)
        try:
            if engineering:
                if read(config).get("method") == "answer_review":
                    raise ValueError("No extra pre-training model qualification for answer-review")
                return verify_learning(study)
            study.execute()
            return write_report(study.out)
        except BaseException as exc:
            value = {
                "at": datetime.now(UTC).isoformat(),
                "run_id": run_id,
                "error": repr(exc),
                "completed_native_calls": len(study.native),
                "completed_teacher_calls": len(study.teachers),
                "teacher_attempts": study.teacher_attempts,
                "current_batch": study.current_batch,
                "no_silent_resume_or_fallback": True,
            }
            RunStore.immutable_json(study.out / "failure.json", value)
            RunStore.atomic_json(
                study.out / "progress.json",
                {"state": "stopped" if isinstance(exc, InterruptedError) else "failed", **value},
            )
            raise


def launch(config, run_id, engineering):
    # Launch lock prevents two requests creating two workers for the same Run ID.
    root = ROOT / "artifacts/launches"
    root.mkdir(parents=True, exist_ok=True)
    with (root / "launch.lock").open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        record = root / (run_id + ".json")
        if record.exists() or (ROOT / "runs" / run_id).exists():
            raise FileExistsError("Existing Run ID; never overwrite or restart it")
        if engineering and read(config).get("method") == "answer_review":
            raise ValueError("Answer-review starts the declared development study directly")
        probe = study_for(config, run_id)
        probe.check()
        argv = [
            str(ROOT / ".venv/bin/python"),
            "-m",
            "legal_skill_guard.cli",
            "worker",
            "--config",
            str(config),
            "--run-id",
            run_id,
        ]
        if engineering:
            argv.append("--engineering")
        with (root / (run_id + ".log")).open("xb") as log:
            process = subprocess.Popen(
                argv,
                cwd=ROOT,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )
        value = {
            "at": datetime.now(UTC).isoformat(),
            "run_id": run_id,
            "pid": process.pid,
            "actual_argv": argv,
            "background_independent_of_conversation": True,
            "engineering_only": engineering,
            "log": str(root / (run_id + ".log")),
        }
        RunStore.immutable_json(record, value)
        return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "launch", "worker", "status", "report"])
    parser.add_argument("--config", type=Path, default=ROOT / "configs/contractnli_review.json")
    parser.add_argument("--run-id")
    parser.add_argument(
        "--engineering",
        action="store_true",
        help="one-document real-chain reconstruction check only",
    )
    args = parser.parse_args()
    config = args.config.resolve()
    run_id = safe_component(args.run_id or read(config)["run_id"])
    if args.command == "prepare":
        value = prepare(config)
    elif args.command == "launch":
        value = launch(config, run_id, args.engineering)
    elif args.command == "worker":
        value = worker(config, run_id, args.engineering)
    elif args.command == "report":
        value = write_report(ROOT / "runs" / run_id)
    else:
        run = ROOT / "runs" / run_id
        value = (
            read(run / "progress.json")
            if (run / "progress.json").is_file()
            else {"state": "not_started", "run_id": run_id}
        )
    print(json.dumps(value, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
