#!/usr/bin/env python3
"""Combine official DLawBench scores and process constraints into TF-GRPO rewards."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from legal_skill_guard.evolution.advantage import ScoredMember, compute_advantages
from legal_skill_guard.evolution.reward import (
    RewardComponents,
    proposed_final_was_redirected,
    trajectory_reward,
)
from legal_skill_guard.utils.hashing import sha256_file

try:
    from scripts.collect_phase3_groups import DEFAULT_CONFIG
    from scripts.run_phase1_baseline import ROOT, atomic_json, load_yaml
except ModuleNotFoundError:
    from collect_phase3_groups import DEFAULT_CONFIG  # type: ignore[no-redef]
    from run_phase1_baseline import ROOT, atomic_json, load_yaml  # type: ignore[no-redef]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    config = load_yaml(args.config.resolve())
    run_root = ROOT / config["outputs"]["run_root"] / args.run_id
    trajectories = {
        value["trajectory_id"]: value
        for path in sorted((run_root / "trajectories").glob("*/*.json"))
        for value in [json.loads(path.read_text(encoding="utf-8"))]
    }
    sessions = {
        value["source_trajectory_id"]: value
        for path in sorted((run_root / "evaluations/official_sessions").glob("*.json"))
        for value in [json.loads(path.read_text(encoding="utf-8"))]
    }
    if set(trajectories) != set(sessions):
        missing = sorted(set(trajectories) - set(sessions))
        raise RuntimeError(
            f"Official evaluation is incomplete; missing {len(missing)} trajectories"
        )
    rewards: dict[str, dict] = {}
    grouped: dict[str, list[ScoredMember]] = defaultdict(list)
    for trajectory_id, trajectory in trajectories.items():
        scores = sessions[trajectory_id]["evaluation"]["scores"]
        steps = trajectory["steps"]
        questions = [step for step in steps if step.get("rendered_question")]
        repeat_count = sum(
            any(
                item["validator_id"] == "question_not_repeated" and not item["passed"]
                for item in step["verifier_results"]
            )
            for step in questions
        )
        repeat_rate = repeat_count / len(questions) if questions else 0.0
        severe = any(
            not item["passed"] and item["severity"] == "severe"
            for step in steps
            for item in step["verifier_results"]
        )
        premature = any(proposed_final_was_redirected(step) for step in steps)
        components = RewardComponents(
            elicitation=(float(scores["discovery_rate"]) + float(scores["EAS"])) / 2,
            resolution=(float(scores["absolute_accuracy"]) + float(scores["MES"])) / 2,
            fidelity=float(scores["grounding_rate"]),
            turns=len(questions),
            repeated_question_rate=repeat_rate,
            premature_final=premature,
            unsupported_claim=float(scores["grounding_rate"]) < 0.5,
            hidden_field_leak=severe,
        )
        result = trajectory_reward(components)
        rewards[trajectory_id] = {
            "group_id": trajectory["group_id"],
            "components": components.model_dump(mode="json"),
            "reward": result.model_dump(mode="json"),
        }
        grouped[trajectory["group_id"]].append(
            ScoredMember(
                trajectory_id=trajectory_id,
                reward=result.final_reward,
                premature_final=premature,
                unsupported_claim=components.unsupported_claim,
                turns=len(questions),
            )
        )
    advantages = {
        group_id: compute_advantages(
            group_id,
            records,
            epsilon=float(config["evolution"]["advantage_epsilon"]),
        ).model_dump(mode="json")
        for group_id, records in sorted(grouped.items())
    }
    output = {
        "schema_version": 1,
        "run_id": args.run_id,
        "scoring_script_sha256": sha256_file(Path(__file__)),
        "trajectories": rewards,
        "groups": advantages,
        "valid_groups": len(advantages),
        "informative_groups": sum(item["informative"] for item in advantages.values()),
        "low_variance_groups": sum(not item["informative"] for item in advantages.values()),
    }
    atomic_json(run_root / "evolution/group_advantages.json", output)
    manifest_path = run_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["reward_scoring"] = {
        "script": str(Path(__file__).resolve().relative_to(ROOT)),
        "sha256": output["scoring_script_sha256"],
        "valid_groups": output["valid_groups"],
        "informative_groups": output["informative_groups"],
    }
    manifest["status"] = "advantages_complete"
    atomic_json(manifest_path, manifest)
    print(json.dumps({key: output[key] for key in output if key not in {"trajectories", "groups"}}))


if __name__ == "__main__":
    main()
