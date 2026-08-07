#!/usr/bin/env python3
"""Evaluate Phase 1 trajectories with the pinned official DLawBench evaluator code."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from scripts.run_phase1_baseline import (
    DEFAULT_CONFIG,
    LocalVLLMServer,
    atomic_json,
    load_yaml,
    utc_now,
)

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / "third_party/DLawBench"
UPSTREAM_SRC = UPSTREAM / "src"
REVISION = "9f6325f29f07b296fac110a6e1880bdd5d9ca538"
CASE_DIR = ROOT / "data/raw/dlawbench" / REVISION / "data/case_backgrounds"
CASE_FILE = CASE_DIR / "cases_cn.jsonl"


def import_official_evaluator(served_model: str) -> tuple[Any, Any]:
    sys.path.insert(0, str(UPSTREAM_SRC))
    from dlawbench import api_utils, evaluate  # noqa: PLC0415
    from dlawbench.case_utils import normalize_case  # noqa: PLC0415

    os.environ["LOCALHOST_API_KEY"] = "local-research"
    if served_model not in api_utils.LOCALHOST_MODELS:
        api_utils.LOCALHOST_MODELS.append(served_model)
    api_utils.MODEL_PARAMS[served_model] = {
        "chat_template_kwargs": {"enable_thinking": False}
    }
    original_call = api_utils.call_model

    def constrained_call(model_name: str, messages: list[dict], **kwargs: Any) -> Any:
        kwargs["max_tokens"] = min(int(kwargs.get("max_tokens") or 3072), 3072)
        kwargs["temperature"] = 0.0
        kwargs["response_format"] = {"type": "json_object"}
        return original_call(model_name, messages, **kwargs)

    evaluate.call_model = constrained_call
    return evaluate, normalize_case


def case_index() -> tuple[dict[str, dict], dict[str, int]]:
    records: dict[str, dict] = {}
    lines: dict[str, int] = {}
    for line_number, line in enumerate(CASE_FILE.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            record = json.loads(line)
            records[record["id"]] = record
            lines[record["id"]] = line_number
    return records, lines


def upstream_session(trajectory: dict[str, Any], case_line: int) -> dict[str, Any]:
    log = []
    for step in trajectory["steps"]:
        if step.get("rendered_question") and step.get("client_response"):
            log.append(
                {
                    "type": "talk",
                    "turn": len(log) + 1,
                    "lawyer_message": step["rendered_question"],
                    "client_response": step["client_response"],
                }
            )
    log.append({"type": "memo", "content_length": len(trajectory["memo"])})
    return {
        "case_id": trajectory["case_id"],
        "jurisdiction": "CN",
        "persona": trajectory["persona"],
        "lawyer_model": f"Qwen3-4B::{trajectory['method']}",
        "client_model": "Qwen3-4B-phase1",
        "turns_used": sum(item["type"] == "talk" for item in log),
        "max_turns": trajectory["max_turns"],
        "status": trajectory["status"],
        "memo": trajectory["memo"],
        "log": log,
        "case_file": CASE_FILE.name,
        "case_line": case_line,
        "source_trajectory_id": trajectory["trajectory_id"],
    }


def scores_complete(evaluation: dict[str, Any]) -> bool:
    scores = evaluation.get("scores") or {}
    required = ("MES", "EAS", "discovery_rate", "absolute_accuracy", "grounding_rate")
    return all(scores.get(key) is not None for key in required)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--no-start-server", action="store_true")
    args = parser.parse_args()

    config = load_yaml(args.config.resolve())
    run_root = ROOT / config["outputs"]["run_root"] / args.run_id
    manifest_path = run_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    trajectory_files = sorted((run_root / "trajectories").glob("*/*.json"))
    if not trajectory_files:
        raise RuntimeError(f"No trajectories found under {run_root}")
    records, line_numbers = case_index()
    session_root = run_root / "evaluations/official_sessions"
    pending = [
        path
        for path in trajectory_files
        if not (session_root / f"{path.parent.name}__{path.name}").is_file()
    ]
    failures: list[dict[str, str]] = []

    with LocalVLLMServer(
        config, run_root / "vllm_evaluator.log", auto_start=not args.no_start_server
    ):
        served_model = config["inference"]["served_model_name"]
        os.environ["LOCALHOST_BASE_URL"] = (
            f"http://{config['inference']['host']}:{config['inference']['port']}/v1"
        )
        evaluate, normalize_case = import_official_evaluator(served_model)

        def evaluate_one(path: Path) -> tuple[Path, dict[str, Any]]:
            trajectory = json.loads(path.read_text(encoding="utf-8"))
            session = upstream_session(trajectory, line_numbers[trajectory["case_id"]])
            case = normalize_case(records[trajectory["case_id"]])
            evaluation = evaluate.evaluate_session(session, case, served_model)
            if not scores_complete(evaluation):
                raise RuntimeError(
                    f"Official evaluator returned incomplete scores: {evaluation.get('scores')}"
                )
            session["evaluation"] = evaluation
            session["evaluated_at"] = utc_now().isoformat()
            session["evaluator"] = {
                "implementation": "official DLawBench evaluate.py",
                "revision": REVISION,
                "judge_model": config["model"],
                "completion_cap": 3072,
                "structured_output": "json_object",
            }
            return path, session

        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
            futures = {executor.submit(evaluate_one, path): path for path in pending}
            for future in as_completed(futures):
                path = futures[future]
                try:
                    source, session = future.result()
                    output = session_root / f"{source.parent.name}__{source.name}"
                    atomic_json(output, session)
                    print(f"evaluated {source.parent.name} {source.stem}", flush=True)
                except Exception as exc:
                    failures.append({"trajectory": str(path), "error": str(exc)})
                    print(f"FAILED evaluation {path}: {exc}", file=sys.stderr, flush=True)

    session_files = sorted(session_root.glob("*.json"))
    metrics_md = run_root / "evaluations/official_metrics.md"
    metrics_json = run_root / "evaluations/official_metrics.json"
    metrics_command = [
        sys.executable,
        str(UPSTREAM / "scripts/metrics.py"),
        "--sessions",
        str(session_root / "*.json"),
        "--case-dir",
        str(CASE_DIR),
    ]
    if not failures and len(session_files) == len(trajectory_files):
        subprocess.run(metrics_command + ["--output", str(metrics_md)], check=True, cwd=UPSTREAM)
        subprocess.run(
            metrics_command + ["--format", "json", "--output", str(metrics_json)],
            check=True,
            cwd=UPSTREAM,
        )
    manifest["evaluation"] = {
        "status": "failed" if failures else "complete",
        "official_evaluator_revision": REVISION,
        "expected_sessions": len(trajectory_files),
        "completed_sessions": len(session_files),
        "failures": failures,
        "metrics_markdown": str(metrics_md.relative_to(ROOT)),
        "metrics_json": str(metrics_json.relative_to(ROOT)),
    }
    manifest["status"] = "failed" if failures else "evaluation_complete"
    atomic_json(manifest_path, manifest)
    if failures or len(session_files) != len(trajectory_files):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
