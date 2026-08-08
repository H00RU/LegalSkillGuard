#!/usr/bin/env python3
"""Score Phase 4 pairs, decide the candidate, and freeze or reject it."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

import yaml

from legal_skill_guard.evolution.acceptance import (
    AcceptanceThresholds,
    PairOutcome,
    decide_skill,
    global_regression_passes,
)
from legal_skill_guard.evolution.reward import (
    RewardComponents,
    proposed_final_was_redirected,
    trajectory_reward,
)
from legal_skill_guard.schemas.skill import SkillContract
from legal_skill_guard.skills.loader import load_skill_directory
from legal_skill_guard.skills.registry import SkillRegistry
from legal_skill_guard.utils.hashing import sha256_file

try:
    from scripts.collect_phase4_audit import DEFAULT_CONFIG
    from scripts.run_phase1_baseline import ROOT, atomic_json, load_yaml
except ModuleNotFoundError:
    from collect_phase4_audit import DEFAULT_CONFIG  # type: ignore[no-redef]
    from run_phase1_baseline import ROOT, atomic_json, load_yaml  # type: ignore[no-redef]


def process_outcome(trajectory: dict, session: dict) -> dict[str, object]:
    scores = session["evaluation"]["scores"]
    questions = [step for step in trajectory["steps"] if step.get("rendered_question")]
    repeats = sum(
        any(
            result["validator_id"] == "question_not_repeated" and not result["passed"]
            for result in step["verifier_results"]
        )
        for step in questions
    )
    severe = any(
        result["severity"] == "severe" and not result["passed"]
        for step in trajectory["steps"]
        for result in step["verifier_results"]
    )
    components = RewardComponents(
        elicitation=(float(scores["discovery_rate"]) + float(scores["EAS"])) / 2,
        resolution=(float(scores["absolute_accuracy"]) + float(scores["MES"])) / 2,
        fidelity=float(scores["grounding_rate"]),
        turns=len(questions),
        repeated_question_rate=repeats / len(questions) if questions else 0.0,
        premature_final=any(
            proposed_final_was_redirected(step) for step in trajectory["steps"]
        ),
        unsupported_claim=float(scores["grounding_rate"]) < 0.5,
        hidden_field_leak=severe,
    )
    return {
        "reward": trajectory_reward(components).final_reward,
        "unsupported_claim": float(components.unsupported_claim),
        "premature_final": float(components.premature_final),
        "severe_risk": severe,
        "turns": len(questions),
        "tokens": sum(
            step["token_usage"]["prompt"] + step["token_usage"]["completion"]
            for step in trajectory["steps"]
        ),
        "official": {
            key: float(scores[key])
            for key in (
                "MES",
                "EAS",
                "discovery_rate",
                "absolute_accuracy",
                "grounding_rate",
            )
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    config = load_yaml(args.config.resolve())
    run_root = ROOT / config["outputs"]["run_root"] / args.run_id
    manifest_path = run_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    candidate = SkillContract.model_validate(manifest["candidate_skill"])
    trajectories = {
        (path.parent.name, path.stem): json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((run_root / "trajectories").glob("*/*.json"))
    }
    sessions = {
        value["source_trajectory_id"]: value
        for path in sorted((run_root / "evaluations/official_sessions").glob("*.json"))
        for value in [json.loads(path.read_text(encoding="utf-8"))]
    }
    outcomes: list[PairOutcome] = []
    pair_details: list[dict[str, object]] = []
    pair_ids = sorted({pair_id for _, pair_id in trajectories})
    for pair_id in pair_ids:
        without = trajectories[("without", pair_id)]
        with_candidate = trajectories[("with", pair_id)]
        result_without = process_outcome(without, sessions[without["trajectory_id"]])
        result_with = process_outcome(
            with_candidate, sessions[with_candidate["trajectory_id"]]
        )
        triggered = any(
            candidate.skill_id in step["action_decision"]["activated_skill_ids"]
            for step in with_candidate["steps"]
        )
        action_changed = any(
            change["skill_id"] == candidate.skill_id
            and change.get("before") != change.get("after")
            for step in with_candidate["steps"]
            for change in step["action_decision"]["changes"]
        )
        outcome = PairOutcome(
            pair_id=pair_id,
            triggered=triggered,
            reward_without=float(result_without["reward"]),
            reward_with=float(result_with["reward"]),
            severe_risk_with=bool(result_with["severe_risk"]),
            unsupported_claim_delta=float(result_with["unsupported_claim"])
            - float(result_without["unsupported_claim"]),
            premature_final_delta=float(result_with["premature_final"])
            - float(result_without["premature_final"]),
        )
        outcomes.append(outcome)
        without_official = result_without["official"]
        with_official = result_with["official"]
        assert isinstance(without_official, dict) and isinstance(with_official, dict)
        pair_details.append(
            {
                **outcome.model_dump(mode="json"),
                "delta": outcome.delta,
                "action_changed": action_changed,
                "turn_delta": int(result_with["turns"])
                - int(result_without["turns"]),
                "token_delta": int(result_with["tokens"])
                - int(result_without["tokens"]),
                "official_metric_deltas": {
                    key: float(with_official[key]) - float(without_official[key])
                    for key in without_official
                },
            }
        )
    settings = config["acceptance"]
    decision = decide_skill(
        outcomes,
        AcceptanceThresholds(
            minimum_triggered_pairs=settings["minimum_triggered_pairs"],
            minimum_mean_delta=settings["minimum_mean_delta"],
            maximum_harmful_pair_rate=settings["maximum_harmful_pair_rate"],
        ),
    )
    baseline_mean = statistics.fmean(outcome.reward_without for outcome in outcomes)
    candidate_mean = statistics.fmean(outcome.reward_with for outcome in outcomes)
    regression_passed = global_regression_passes(
        baseline_mean, candidate_mean, settings["maximum_global_drop"]
    )
    candidate.evaluation.paired_cases = len(outcomes)
    candidate.evaluation.triggered_pairs = decision.triggered_pairs
    candidate.evaluation.mean_delta_reward = decision.mean_delta_reward
    candidate.evaluation.median_delta_reward = decision.median_delta_reward
    candidate.evaluation.harmful_pair_rate = decision.harmful_pair_rate
    candidate.evaluation.severe_risk_count = decision.severe_risk_count
    final_decision = decision.decision
    if final_decision == "ACCEPT" and not regression_passed:
        final_decision = "REJECT"
    destinations = {
        "ACCEPT": ("skills/accepted", "active"),
        "REJECT": ("skills/rejected", "rejected"),
        "DEFER": ("skills/deferred", "candidate"),
        "REPAIR": ("skills/repair", "candidate"),
    }
    destination, status = destinations[final_decision]
    destination_root = ROOT / destination
    destination_root.mkdir(parents=True, exist_ok=True)
    candidate.status = status
    output_skill = destination_root / f"{candidate.skill_id}__{args.run_id}.yaml"
    output_skill.write_text(
        yaml.safe_dump(
            candidate.model_dump(mode="json", exclude_none=True),
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    version = None
    if final_decision == "ACCEPT":
        skills_by_id = {
            skill.skill_id: skill for skill in load_skill_directory(ROOT / "skills/seed")
        }
        skills_by_id[candidate.skill_id] = candidate
        skills = list(skills_by_id.values())
        version = f"v0.2.0-{args.run_id}"
        registry = SkillRegistry(ROOT / "skills/versions")
        registry.create_version(
            version,
            skills,
            parent_version="seed_v0.1.0",
            evidence={"run_id": args.run_id, "decision": decision.model_dump(mode="json")},
        )
        registry.activate(version)
    triggered_details = [item for item in pair_details if item["triggered"]]
    official_keys = (
        "MES",
        "EAS",
        "discovery_rate",
        "absolute_accuracy",
        "grounding_rate",
    )
    audit = {
        "schema_version": 1,
        "run_id": args.run_id,
        "scoring_script_sha256": sha256_file(Path(__file__)),
        "candidate_skill_id": candidate.skill_id,
        "decision": decision.model_dump(mode="json"),
        "final_decision": final_decision,
        "global_regression": {
            "baseline_mean": baseline_mean,
            "candidate_mean": candidate_mean,
            "passed": regression_passed,
        },
        "trigger_rate": decision.triggered_pairs / decision.pairs if decision.pairs else 0,
        "action_change_rate_after_trigger": (
            sum(bool(item["action_changed"]) for item in triggered_details)
            / len(triggered_details)
            if triggered_details
            else 0
        ),
        "improved_pair_rate": (
            sum(float(item["delta"]) > 0 for item in triggered_details)
            / len(triggered_details)
            if triggered_details
            else 0
        ),
        "tied_pair_rate": (
            sum(float(item["delta"]) == 0 for item in triggered_details)
            / len(triggered_details)
            if triggered_details
            else 0
        ),
        "mean_turn_delta_triggered": (
            statistics.fmean(float(item["turn_delta"]) for item in triggered_details)
            if triggered_details
            else 0
        ),
        "mean_token_delta_triggered": (
            statistics.fmean(float(item["token_delta"]) for item in triggered_details)
            if triggered_details
            else 0
        ),
        "mean_official_metric_deltas_all_pairs": {
            key: statistics.fmean(
                float(item["official_metric_deltas"][key]) for item in pair_details  # type: ignore[index]
            )
            for key in official_keys
        },
        "outcomes": pair_details,
        "skill_library_version": version,
    }
    atomic_json(run_root / "audit/paired_audit.json", audit)
    manifest["status"] = "audit_complete"
    manifest["audit"] = audit
    atomic_json(manifest_path, manifest)
    print(json.dumps({key: audit[key] for key in audit if key != "outcomes"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
