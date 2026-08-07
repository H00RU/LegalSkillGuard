#!/usr/bin/env python3
"""Run the Phase 1 B0/B1 pilot against a pinned local Qwen3-4B server."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from legal_skill_guard.agent.phase1_policy import parse_lawyer_action
from legal_skill_guard.data_visibility import assert_online_view_safe
from legal_skill_guard.environment.client_simulator import Phase1ClientSimulator
from legal_skill_guard.environment.dlawbench_adapter import DLawBenchAdapter
from legal_skill_guard.inference.openai_client import ChatClient, GenerationConfig
from legal_skill_guard.schemas.trajectory import (
    Action,
    Message,
    TokenUsage,
    Trajectory,
    TrajectoryStep,
)
from legal_skill_guard.utils.hashing import canonical_json_sha256, sha256_file

ROOT = Path(__file__).resolve().parents[1]
REVISION = "9f6325f29f07b296fac110a6e1880bdd5d9ca538"
CASES = (
    ROOT
    / "data/raw/dlawbench"
    / REVISION
    / "data/case_backgrounds/cases_cn.jsonl"
)
PERSONAS = ROOT / "data/raw/dlawbench" / REVISION / "config/personas.json"
DEFAULT_CONFIG = ROOT / "configs/experiments/phase1_pilot.yaml"
MODEL_MANIFEST = ROOT / "data/manifests/qwen3_4b_model.json"
PROMPT_DIR = ROOT / "configs/prompts"
METHODS = ("B0_direct", "B1_prompted_multiturn")


def utc_now() -> datetime:
    return datetime.now(UTC)


def stable_seed(base: int, *parts: str) -> int:
    digest = hashlib.sha256(":|:".join((str(base), *parts)).encode()).digest()
    return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def source_tree_hash() -> str:
    roots = [ROOT / name for name in ("legal_skill_guard", "scripts", "configs", "tests")]
    files = [
        path
        for root in roots
        for path in root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    ]
    files.extend([ROOT / "pyproject.toml", ROOT / "uv.lock"])
    return canonical_json_sha256(
        {str(path.relative_to(ROOT)): sha256_file(path) for path in sorted(files)}
    )


def git_revision() -> str | None:
    git = shutil.which("git") or str(ROOT.parent / ".tools/bin/git")
    completed = subprocess.run(
        [git, "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return completed.stdout.strip() if completed.returncode == 0 else None


class LocalVLLMServer(AbstractContextManager[ChatClient]):
    def __init__(self, config: dict[str, Any], log_path: Path, auto_start: bool = True) -> None:
        inference = config["inference"]
        self.config = config
        self.base_url = f"http://{inference['host']}:{inference['port']}/v1"
        self.client = ChatClient(self.base_url, inference["served_model_name"])
        self.log_path = log_path
        self.auto_start = auto_start
        self.process: subprocess.Popen | None = None
        self.log_handle = None

    def __enter__(self) -> ChatClient:
        if self.client.is_ready():
            return self.client
        if not self.auto_start:
            raise RuntimeError(f"No matching model server at {self.base_url}")

        model = self.config["model"]
        inference = self.config["inference"]
        local_model_path = ROOT / model.get("local_path", "")
        model_reference = str(local_model_path) if local_model_path.is_dir() else model["id"]
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_handle = self.log_path.open("a", encoding="utf-8")
        command = [
            sys.executable,
            "-m",
            "vllm.entrypoints.openai.api_server",
            "--model",
            model_reference,
            "--served-model-name",
            inference["served_model_name"],
            "--host",
            inference["host"],
            "--port",
            str(inference["port"]),
            "--dtype",
            model["dtype"],
            "--max-model-len",
            str(inference["max_model_len"]),
            "--gpu-memory-utilization",
            str(inference["gpu_memory_utilization"]),
            "--tensor-parallel-size",
            str(inference["tensor_parallel_size"]),
            "--enable-prefix-caching",
            "--disable-log-requests",
            "--generation-config",
            "vllm",
        ]
        if model_reference == model["id"]:
            command.extend(["--revision", model["revision"]])
        environment = os.environ.copy()
        environment["HF_HOME"] = str(ROOT / "data/cache/huggingface")
        environment["TOKENIZERS_PARALLELISM"] = "false"
        self.process = subprocess.Popen(
            command,
            cwd=ROOT,
            env=environment,
            stdout=self.log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            deadline = time.monotonic() + 1800
            while time.monotonic() < deadline:
                if self.process.poll() is not None:
                    tail = "\n".join(
                        self.log_path.read_text(encoding="utf-8").splitlines()[-80:]
                    )
                    raise RuntimeError(
                        f"vLLM server exited with {self.process.returncode}:\n{tail}"
                    )
                if self.client.is_ready():
                    return self.client
                time.sleep(2)
            raise TimeoutError(f"vLLM server did not become ready; see {self.log_path}")
        except BaseException:
            self._stop()
            raise

    def _stop(self) -> None:
        if self.process is not None and self.process.poll() is None:
            os.killpg(self.process.pid, signal.SIGTERM)
            try:
                self.process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                os.killpg(self.process.pid, signal.SIGKILL)
                self.process.wait(timeout=10)
        if self.log_handle is not None:
            self.log_handle.close()

    def __exit__(self, *exc_info: object) -> None:
        self._stop()


def generation_config(
    values: dict[str, Any], seed: int, disable_thinking: bool
) -> GenerationConfig:
    return GenerationConfig(
        temperature=float(values["temperature"]),
        top_p=float(values["top_p"]),
        max_tokens=int(values["max_tokens"]),
        seed=seed,
        disable_thinking=disable_thinking,
    )


def run_b0(
    run_id: str,
    case_id: str,
    adapter: DLawBenchAdapter,
    client: ChatClient,
    config: dict[str, Any],
) -> Trajectory:
    started = time.monotonic()
    seed = stable_seed(config["seed"], "B0_direct", case_id)
    case = adapter.lawyer_case(case_id)
    prompt = (PROMPT_DIR / "phase1_b0_direct_zh.txt").read_text(encoding="utf-8").format(
        opening=case["opening"]
    )
    messages = [{"role": "user", "content": prompt}]
    settings = config["generation"]["lawyer"]
    response = client.generate(
        messages,
        GenerationConfig(
            temperature=float(settings["temperature"]),
            top_p=float(settings["top_p"]),
            max_tokens=int(settings["max_tokens_memo"]),
            seed=seed,
            disable_thinking=config["generation"]["disable_thinking"],
        ),
    )
    action = Action(
        tool="write_memo",
        content=response.content,
        parse_mode="fallback",
        raw_model_output=response.content,
    )
    step = TrajectoryStep(
        turn=0,
        visible_input=[Message(**message) for message in messages],
        proposed_action=action,
        action_after_skills=action,
        latency_ms=round((time.monotonic() - started) * 1000),
        token_usage=TokenUsage(
            prompt=response.prompt_tokens, completion=response.completion_tokens
        ),
    )
    return Trajectory(
        trajectory_id=f"B0_direct__{case_id}__seed{seed}",
        run_id=run_id,
        method="B0_direct",
        case_id=case_id,
        jurisdiction="CN",
        persona="P_NA",
        seed=seed,
        model_id=config["model"]["id"],
        model_revision=config["model"]["revision"],
        status="memo_submitted",
        opening=case["opening"],
        max_turns=0,
        steps=[step],
        memo=response.content,
        elapsed_seconds=round(time.monotonic() - started, 3),
        created_at=utc_now(),
    )


def dialogue_text(opening: str, history: list[tuple[str, str]]) -> str:
    lines = [f"客户（开场）：{opening}"]
    for index, (question, answer) in enumerate(history, start=1):
        lines.extend((f"律师（第{index}轮）：{question}", f"客户：{answer}"))
    return "\n".join(lines)


def run_b1(
    run_id: str,
    case_id: str,
    persona_key: str,
    adapter: DLawBenchAdapter,
    client: ChatClient,
    config: dict[str, Any],
) -> Trajectory:
    started = time.monotonic()
    seed = stable_seed(config["seed"], "B1_prompted_multiturn", case_id, persona_key)
    visible_case = adapter.lawyer_case(case_id)
    max_turns = int(config["dialogue"]["max_turns"])
    system = (PROMPT_DIR / "phase1_b1_lawyer_zh.txt").read_text(encoding="utf-8").format(
        opening=visible_case["opening"], max_turns=max_turns
    )
    client_settings = config["generation"]["client"]
    simulator = Phase1ClientSimulator.from_template_file(
        adapter.client_case(case_id),
        adapter.persona(persona_key),
        client,
        PROMPT_DIR / "phase1_client_zh.txt",
        generation_config(
            client_settings,
            seed,
            config["generation"]["disable_thinking"],
        ),
    )
    lawyer_history: list[dict[str, str]] = []
    dialogue: list[tuple[str, str]] = []
    steps: list[TrajectoryStep] = []
    memo = ""
    status = "max_turns_forced_memo"
    lawyer_settings = config["generation"]["lawyer"]

    for turn in range(1, max_turns + 1):
        step_started = time.monotonic()
        remaining = max_turns - turn + 1
        messages = [{"role": "system", "content": system}, *lawyer_history]
        messages.append(
            {
                "role": "user",
                "content": f"[轮次状态] 即将执行第 {turn} 轮，尚可提问 {remaining} 次。",
            }
        )
        lawyer_response = client.generate(
            messages,
            GenerationConfig(
                temperature=float(lawyer_settings["temperature"]),
                top_p=float(lawyer_settings["top_p"]),
                max_tokens=int(
                    lawyer_settings[
                        "max_tokens_memo" if turn == max_turns else "max_tokens_action"
                    ]
                ),
                seed=seed + turn,
                disable_thinking=config["generation"]["disable_thinking"],
            ),
        )
        action = parse_lawyer_action(lawyer_response.content)
        question = None
        client_response = None
        client_input_hash = None
        prompt_tokens = lawyer_response.prompt_tokens
        completion_tokens = lawyer_response.completion_tokens
        if action.tool == "write_memo":
            memo = action.content
            status = "memo_submitted"
        else:
            question = action.content
            simulated, client_input_hash = simulator.respond(question, seed + 10_000 + turn)
            client_response = simulated.content
            dialogue.append((question, client_response))
            prompt_tokens += simulated.prompt_tokens
            completion_tokens += simulated.completion_tokens
            lawyer_history.extend(
                [
                    {"role": "assistant", "content": lawyer_response.content},
                    {
                        "role": "user",
                        "content": json.dumps(
                            {"client_response": client_response}, ensure_ascii=False
                        ),
                    },
                ]
            )
        steps.append(
            TrajectoryStep(
                turn=turn,
                visible_input=[Message(**message) for message in messages],
                proposed_action=action,
                action_after_skills=action,
                rendered_question=question,
                client_response=client_response,
                client_input_sha256=client_input_hash,
                latency_ms=round((time.monotonic() - step_started) * 1000),
                token_usage=TokenUsage(prompt=prompt_tokens, completion=completion_tokens),
            )
        )
        if memo:
            break

    if not memo:
        step_started = time.monotonic()
        prompt = (PROMPT_DIR / "phase1_memo_zh.txt").read_text(encoding="utf-8").format(
            opening=visible_case["opening"],
            dialogue=dialogue_text(visible_case["opening"], dialogue),
        )
        messages = [{"role": "user", "content": prompt}]
        response = client.generate(
            messages,
            GenerationConfig(
                temperature=float(lawyer_settings["temperature"]),
                top_p=float(lawyer_settings["top_p"]),
                max_tokens=int(lawyer_settings["max_tokens_memo"]),
                seed=seed + max_turns + 1,
                disable_thinking=config["generation"]["disable_thinking"],
            ),
        )
        memo = response.content
        action = Action(
            tool="write_memo",
            content=memo,
            parse_mode="fallback",
            raw_model_output=memo,
        )
        steps.append(
            TrajectoryStep(
                turn=max_turns + 1,
                visible_input=[Message(**message) for message in messages],
                proposed_action=action,
                action_after_skills=action,
                latency_ms=round((time.monotonic() - step_started) * 1000),
                token_usage=TokenUsage(
                    prompt=response.prompt_tokens,
                    completion=response.completion_tokens,
                ),
            )
        )

    return Trajectory(
        trajectory_id=f"B1_prompted_multiturn__{case_id}__{persona_key}__seed{seed}",
        run_id=run_id,
        method="B1_prompted_multiturn",
        case_id=case_id,
        jurisdiction="CN",
        persona=persona_key,
        seed=seed,
        model_id=config["model"]["id"],
        model_revision=config["model"]["revision"],
        status=status,
        opening=visible_case["opening"],
        max_turns=max_turns,
        steps=steps,
        memo=memo,
        elapsed_seconds=round(time.monotonic() - started, 3),
        created_at=utc_now(),
    )


def build_manifest(run_id: str, config_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    if not MODEL_MANIFEST.is_file():
        raise RuntimeError(
            "Pinned model manifest is missing; run scripts/verify_phase1_model.py first"
        )
    split_path = ROOT / config["data"]["split_manifest"]
    prompts = sorted(PROMPT_DIR.glob("phase1_*.txt"))
    return {
        "schema_version": 1,
        "run_id": run_id,
        "phase": 1,
        "status": "running",
        "started_at": utc_now().isoformat(),
        "git_commit": git_revision(),
        "source_tree_sha256": source_tree_hash(),
        "config": str(config_path.relative_to(ROOT)),
        "config_sha256": sha256_file(config_path),
        "data_manifest_sha256": sha256_file(ROOT / config["data"]["source_manifest"]),
        "split_manifest_sha256": sha256_file(split_path),
        "model_manifest": str(MODEL_MANIFEST.relative_to(ROOT)),
        "model_manifest_sha256": sha256_file(MODEL_MANIFEST),
        "prompt_sha256": {
            str(path.relative_to(ROOT)): sha256_file(path) for path in prompts
        },
        "model": config["model"],
        "generation": config["generation"],
        "inference": config["inference"],
        "packages": {
            name: importlib.metadata.version(name)
            for name in ("torch", "transformers", "vllm", "modelscope")
        },
        "hardware": {
            "nvidia_smi": subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=name,driver_version,memory.total",
                    "--format=csv,noheader",
                ],
                text=True,
                stdout=subprocess.PIPE,
                check=True,
            ).stdout.strip()
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--run-id")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--methods", nargs="+", choices=METHODS, default=list(METHODS))
    parser.add_argument("--no-start-server", action="store_true")
    args = parser.parse_args()

    config_path = args.config.resolve()
    config = load_yaml(config_path)
    split = json.loads((ROOT / config["data"]["split_manifest"]).read_text(encoding="utf-8"))
    case_ids = split["partitions"][config["data"]["run_partition"]]["case_ids"]
    personas = list(config["data"]["personas"])
    if args.smoke:
        case_ids = case_ids[:1]
        personas = personas[:1]

    run_id = args.run_id or f"phase1_{utc_now().strftime('%Y%m%dT%H%M%SZ')}"
    run_root = ROOT / config["outputs"]["run_root"] / run_id
    trajectory_root = run_root / "trajectories"
    manifest_path = run_root / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["config_sha256"] != sha256_file(config_path):
            raise RuntimeError("Cannot resume a run with a different configuration")
    else:
        manifest = build_manifest(run_id, config_path, config)
        atomic_json(manifest_path, manifest)

    adapter = DLawBenchAdapter(CASES, PERSONAS)
    tasks: list[tuple[str, str, str]] = []
    if "B0_direct" in args.methods:
        tasks.extend(("B0_direct", case_id, "P_NA") for case_id in case_ids)
    if "B1_prompted_multiturn" in args.methods:
        tasks.extend(
            ("B1_prompted_multiturn", case_id, persona)
            for case_id in case_ids
            for persona in personas
        )

    def output_path(method: str, case_id: str, persona: str) -> Path:
        return trajectory_root / method / f"{case_id}__{persona}.json"

    pending = [task for task in tasks if not output_path(*task).is_file()]
    failures: list[dict[str, str]] = []
    with LocalVLLMServer(
        config, run_root / "vllm_server.log", auto_start=not args.no_start_server
    ) as model_client, ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        future_tasks = {}
        for method, case_id, persona in pending:
            if method == "B0_direct":
                future = executor.submit(
                    run_b0, run_id, case_id, adapter, model_client, config
                )
            else:
                future = executor.submit(
                    run_b1,
                    run_id,
                    case_id,
                    persona,
                    adapter,
                    model_client,
                    config,
                )
            future_tasks[future] = (method, case_id, persona)
        for future in as_completed(future_tasks):
            task = future_tasks[future]
            try:
                trajectory = future.result()
                serialized = trajectory.model_dump(mode="json")
                assert_online_view_safe(serialized)
                atomic_json(output_path(*task), serialized)
                print(f"completed {task[0]} {task[1]} {task[2]}", flush=True)
            except Exception as exc:
                failures.append(
                    {"method": task[0], "case_id": task[1], "persona": task[2], "error": str(exc)}
                )
                print(f"FAILED {task}: {exc}", file=sys.stderr, flush=True)

    completed_files = sorted(trajectory_root.glob("*/*.json"))
    manifest.update(
        {
            "status": "failed" if failures else "dialogues_complete",
            "completed_at": utc_now().isoformat(),
            "expected_trajectories": len(tasks),
            "completed_trajectories": len(completed_files),
            "failures": failures,
        }
    )
    atomic_json(manifest_path, manifest)
    print(
        json.dumps(
            {
                "run_id": run_id,
                "expected": len(tasks),
                "completed": len(completed_files),
                "failures": len(failures),
                "manifest": str(manifest_path),
            },
            ensure_ascii=False,
        )
    )
    if failures or len(completed_files) != len(tasks):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
