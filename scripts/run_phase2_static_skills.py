#!/usr/bin/env python3
"""Run B2 text skills and B3 executable skills on the training acceptance pool."""

from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from legal_skill_guard.agent.state_manager import StateManager
from legal_skill_guard.agent.stateful_policy import parse_policy_envelope, render_action
from legal_skill_guard.data_visibility import assert_online_payload_safe
from legal_skill_guard.environment.client_simulator import Phase1ClientSimulator
from legal_skill_guard.environment.dlawbench_adapter import DLawBenchAdapter
from legal_skill_guard.inference.openai_client import ChatClient, GenerationConfig
from legal_skill_guard.schemas.action import ActionDecision, StructuredAction
from legal_skill_guard.schemas.experiment import ResearchStep, ResearchTrajectory
from legal_skill_guard.schemas.trajectory import Message, TokenUsage
from legal_skill_guard.skills.engine import SkillEngine
from legal_skill_guard.skills.loader import load_skill_directory, render_text_skills
from legal_skill_guard.verifiers.deterministic import StopGate, verify_action

try:
    from scripts.run_phase1_baseline import (
        CASES,
        PERSONAS,
        PROMPT_DIR,
        ROOT,
        LocalVLLMServer,
        atomic_json,
        build_manifest,
        dialogue_text,
        load_yaml,
        stable_seed,
    )
except ModuleNotFoundError:
    from run_phase1_baseline import (  # type: ignore[no-redef]
        CASES,
        PERSONAS,
        PROMPT_DIR,
        ROOT,
        LocalVLLMServer,
        atomic_json,
        build_manifest,
        dialogue_text,
        load_yaml,
        stable_seed,
    )

DEFAULT_CONFIG = ROOT / "configs/experiments/phase2_static_skills.yaml"
PHASE2_PROMPT = ROOT / "configs/prompts/phase2_stateful_policy_zh.txt"


def generation(values: dict[str, Any], seed: int, disable_thinking: bool) -> GenerationConfig:
    return GenerationConfig(
        temperature=float(values["temperature"]),
        top_p=float(values["top_p"]),
        max_tokens=int(values["max_tokens"]),
        seed=seed,
        disable_thinking=disable_thinking,
    )


def terminal_memo(
    client: ChatClient,
    config: dict[str, Any],
    opening: str,
    dialogue: list[tuple[str, str]],
    seed: int,
) -> tuple[str, TokenUsage, str | None]:
    prompt = (PROMPT_DIR / "phase1_memo_zh.txt").read_text(encoding="utf-8").format(
        opening=opening, dialogue=dialogue_text(opening, dialogue)
    )
    response = client.generate(
        [{"role": "user", "content": prompt}],
        generation(config["generation"]["memo"], seed, config["generation"]["disable_thinking"]),
    )
    return (
        response.content,
        TokenUsage(prompt=response.prompt_tokens, completion=response.completion_tokens),
        response.finish_reason,
    )


def run_stateful_trajectory(
    *,
    run_id: str,
    method: str,
    partition: str,
    case_id: str,
    persona: str,
    adapter: DLawBenchAdapter,
    client: ChatClient,
    config: dict[str, Any],
    sample_index: int = 0,
    seed_override: int | None = None,
    skill_path: Path | None = None,
    skill_version: str | None = None,
    executable_skills: bool | None = None,
) -> ResearchTrajectory:
    started = time.monotonic()
    seed = seed_override if seed_override is not None else stable_seed(
        config["seed"], method, case_id, persona, str(sample_index)
    )
    visible = adapter.lawyer_case(case_id)
    max_turns = int(config["dialogue"]["max_turns"])
    library_path = skill_path or ROOT / config["skill_library"]["path"]
    skills = load_skill_directory(library_path, active_only=True)
    library_version = skill_version or config["skill_library"]["version"]
    use_executable_skills = (
        method
        in {
            "B3_static_executable_skills",
            "B5_tfgrpo_no_gate",
            "Ours_legal_skill_guard",
        }
        if executable_skills is None
        else executable_skills
    )
    engine = SkillEngine(skills)
    text_skills = render_text_skills(skills)
    guidance = (
        "以下是静态文字经验，只能作为提示参考，不具有程序化强制力：\n" + text_skills
        if method == "B2_static_text_skills"
        else (
            "候选动作将在模型输出后由外部可执行技能与风险门审计；"
            "不要假设动作必然执行。"
            if use_executable_skills
            else "本方法不启用外部可执行技能。"
        )
    )
    system = (
        PHASE2_PROMPT.read_text(encoding="utf-8")
        .replace("{opening}", visible["opening"])
        .replace("{method_guidance}", guidance)
    )
    manager = StateManager()
    state = manager.initial(
        f"{case_id}_{persona}_{seed}", visible["opening"], max_turns=max_turns, persona=persona
    )
    simulator = Phase1ClientSimulator.from_template_file(
        adapter.client_case(case_id),
        adapter.persona(persona),
        client,
        PROMPT_DIR / "phase1_client_zh.txt",
        generation(
            config["generation"]["client"],
            seed,
            config["generation"]["disable_thinking"],
        ),
    )
    dialogue: list[tuple[str, str]] = []
    steps: list[ResearchStep] = []
    status = "max_turns_forced_memo"

    for turn in range(1, max_turns + 1):
        state_before = state.model_dump(mode="json")
        user = json.dumps(
            {
                "turn": turn,
                "remaining_questions": max_turns - turn + 1,
                "visible_dialogue": dialogue_text(visible["opening"], dialogue),
                "state": state_before,
            },
            ensure_ascii=False,
        )
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        response = client.generate(
            messages,
            generation(
                config["generation"]["policy"],
                seed + turn,
                config["generation"]["disable_thinking"],
            ),
        )
        envelope, parse_mode = parse_policy_envelope(response.content)
        state = manager.merge(state, envelope.state_patch, turn)
        state.candidate_action = envelope.action.model_dump(mode="python")
        if use_executable_skills:
            decision = engine.apply(state, envelope.action)
        else:
            decision = ActionDecision(original=envelope.action, final=envelope.action)
        gate_verdict, gate_reason = StopGate().evaluate(state, decision.final)
        if use_executable_skills and gate_verdict == "REDIRECT":
            unresolved = sorted(
                (fact for fact in state.facts if fact.status in {"unknown", "disputed"}),
                key=lambda fact: (
                    {"high": 0, "medium": 1, "low": 2}[fact.criticality],
                    fact.fact_id,
                ),
            )
            redirected = StructuredAction(
                action_type="clarify",
                target_type="fact" if unresolved else "session",
                target_id=unresolved[0].fact_id if unresolved else None,
                reason=f"stop_gate:{gate_reason}",
            )
            decision.changes.append(
                {
                    "skill_id": "system.stop_gate",
                    "before": decision.final.model_dump(mode="python"),
                    "after": redirected.model_dump(mode="python"),
                }
            )
            decision.final = redirected
        elif use_executable_skills and gate_verdict == "ABSTAIN":
            decision.final = StructuredAction(
                action_type="abstain", target_type="session", reason=f"stop_gate:{gate_reason}"
            )
        verification = verify_action(state, decision)
        question = None
        client_text = None
        client_hash = None
        client_finish = None
        usage = TokenUsage(prompt=response.prompt_tokens, completion=response.completion_tokens)
        if decision.final.action_type in {"ask", "clarify", "verify", "summarize"}:
            question = render_action(decision.final, state)
            simulated, client_hash = simulator.respond(question, seed + 10_000 + turn)
            client_text = simulated.content
            client_finish = simulated.finish_reason
            dialogue.append((question, client_text))
            state = manager.mark_asked(state, decision.final.target_id)
            usage.prompt += simulated.prompt_tokens
            usage.completion += simulated.completion_tokens
        else:
            status = "abstained" if decision.final.action_type == "abstain" else "memo_submitted"
        state_after = state.model_dump(mode="json")
        step = ResearchStep(
            turn=turn,
            visible_input=[Message(**message) for message in messages],
            state_before=state_before,
            state_patch=envelope.state_patch,
            state_after=state_after,
            raw_policy_output=response.content,
            parse_mode=parse_mode,
            proposed_action=envelope.action,
            action_decision=decision,
            rendered_question=question,
            client_response=client_text,
            client_input_sha256=client_hash,
            verifier_results=verification,
            stop_gate_verdict=gate_verdict,
            stop_gate_reason=gate_reason,
            token_usage=usage,
            lawyer_finish_reason=response.finish_reason,
            client_finish_reason=client_finish,
        )
        steps.append(step)
        if decision.final.action_type in {"final", "abstain"}:
            break

    memo, memo_usage, memo_finish = terminal_memo(
        client, config, visible["opening"], dialogue, seed + max_turns + 1
    )
    if memo_finish == "length":
        raise RuntimeError(f"Memo truncated for {case_id}/{persona}/{method}")
    if steps:
        steps[-1].token_usage.prompt += memo_usage.prompt
        steps[-1].token_usage.completion += memo_usage.completion
    trajectory = ResearchTrajectory(
        trajectory_id=f"{method}__{case_id}__{persona}__sample{sample_index}__seed{seed}",
        group_id=f"{case_id}__{persona}",
        sample_index=sample_index,
        run_id=run_id,
        method=method,
        partition=partition,
        case_id=case_id,
        persona=persona,
        seed=seed,
        model_id=config["model"]["id"],
        model_revision=config["model"]["revision"],
        skill_library_version=library_version,
        status=status,
        opening=visible["opening"],
        max_turns=max_turns,
        steps=steps,
        memo=memo,
        elapsed_seconds=round(time.monotonic() - started, 3),
        created_at=datetime.now(UTC),
    )
    assert_online_payload_safe(trajectory.model_dump(mode="json"))
    return trajectory


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--run-id")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--case-limit", type=int)
    parser.add_argument(
        "--methods",
        nargs="+",
        choices=[
            "B2_static_text_skills",
            "B3_static_executable_skills",
            "B5_tfgrpo_no_gate",
            "Ours_legal_skill_guard",
        ],
    )
    parser.add_argument("--no-start-server", action="store_true")
    args = parser.parse_args()
    config_path = args.config.resolve()
    config = load_yaml(config_path)
    methods = args.methods or list(config["methods"])
    split = json.loads((ROOT / config["data"]["split_manifest"]).read_text(encoding="utf-8"))
    partition = config["data"]["run_partition"]
    case_ids = list(split["partitions"][partition]["case_ids"])
    personas = list(config["data"]["personas"])
    if args.smoke:
        case_ids, personas = case_ids[:1], personas[:1]
    elif args.case_limit:
        case_ids = case_ids[: args.case_limit]
    run_id = args.run_id or f"phase2_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
    run_root = ROOT / config["outputs"]["run_root"] / run_id
    execution = {
        "workers": 1,
        "methods": methods,
        "smoke": args.smoke,
        "case_limit": args.case_limit,
        "auto_start_server": not args.no_start_server,
    }
    manifest_path = run_root / "manifest.json"
    manifest = build_manifest(run_id, config_path, config, execution)
    manifest["phase"] = 2
    manifest["skill_library"] = config["skill_library"]
    atomic_json(manifest_path, manifest)
    adapter = DLawBenchAdapter(CASES, PERSONAS)
    tasks = [
        (method, case, persona)
        for method in methods
        for case in case_ids
        for persona in personas
    ]
    failures: list[dict[str, str]] = []
    with LocalVLLMServer(
        config, run_root / "vllm_server.log", auto_start=not args.no_start_server
    ) as model_client:
        for method, case_id, persona in tasks:
            path = run_root / "trajectories" / method / f"{case_id}__{persona}.json"
            if path.is_file():
                continue
            try:
                trajectory = run_stateful_trajectory(
                    run_id=run_id,
                    method=method,
                    partition=partition,
                    case_id=case_id,
                    persona=persona,
                    adapter=adapter,
                    client=model_client,
                    config=config,
                )
                atomic_json(path, trajectory.model_dump(mode="json"))
                print(f"completed {method} {case_id} {persona}", flush=True)
            except Exception as exc:
                failures.append(
                    {
                        "method": method,
                        "case_id": case_id,
                        "persona": persona,
                        "error": str(exc),
                    }
                )
                print(f"FAILED {method} {case_id} {persona}: {exc}", flush=True)
    completed = len(list((run_root / "trajectories").glob("*/*.json")))
    manifest.update(
        status="failed" if failures else "complete",
        completed_at=datetime.now(UTC).isoformat(),
        expected_trajectories=len(tasks),
        completed_trajectories=completed,
        failures=failures,
    )
    atomic_json(manifest_path, manifest)
    if failures or completed != len(tasks):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
