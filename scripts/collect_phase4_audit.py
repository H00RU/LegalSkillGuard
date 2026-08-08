#!/usr/bin/env python3
"""Collect paired candidate-off/candidate-on rollouts on the training acceptance pool."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import yaml

from legal_skill_guard.environment.dlawbench_adapter import DLawBenchAdapter
from legal_skill_guard.schemas.skill import SkillContract
from legal_skill_guard.skills.loader import load_skill

try:
    from scripts.run_phase1_baseline import (
        CASES,
        PERSONAS,
        ROOT,
        LocalVLLMServer,
        atomic_json,
        build_manifest,
        load_yaml,
        stable_seed,
    )
    from scripts.run_phase2_static_skills import run_stateful_trajectory
except ModuleNotFoundError:
    from run_phase1_baseline import (  # type: ignore[no-redef]
        CASES,
        PERSONAS,
        ROOT,
        LocalVLLMServer,
        atomic_json,
        build_manifest,
        load_yaml,
        stable_seed,
    )
    from run_phase2_static_skills import run_stateful_trajectory  # type: ignore[no-redef]

DEFAULT_CONFIG = ROOT / "configs/experiments/phase4_paired_audit.yaml"


def materialize_library(root: Path, candidate: SkillContract) -> tuple[Path, Path]:
    without = root / "without_candidate"
    with_candidate = root / "with_candidate"
    if not without.exists():
        shutil.copytree(ROOT / "skills/seed", without)
    if not with_candidate.exists():
        shutil.copytree(ROOT / "skills/seed", with_candidate)
        activated = candidate.model_copy(deep=True)
        activated.status = "active"
        (with_candidate / f"{activated.skill_id}.yaml").write_text(
            yaml.safe_dump(
                activated.model_dump(mode="json", exclude_none=True),
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
    return without, with_candidate


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--run-id")
    parser.add_argument("--pair-limit", type=int)
    parser.add_argument("--no-start-server", action="store_true")
    args = parser.parse_args()
    config_path = args.config.resolve()
    config = load_yaml(config_path)
    candidate = load_skill(args.candidate.resolve())
    split = json.loads((ROOT / config["data"]["split_manifest"]).read_text(encoding="utf-8"))
    partition = config["data"]["run_partition"]
    cells = [
        (case_id, persona)
        for case_id in split["partitions"][partition]["case_ids"]
        for persona in config["data"]["personas"]
    ]
    if args.pair_limit:
        cells = cells[: args.pair_limit]
    run_id = args.run_id or f"phase4_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
    run_root = ROOT / config["outputs"]["run_root"] / run_id
    without, with_candidate = materialize_library(run_root / "library_inputs", candidate)
    execution = {
        "workers": 1,
        "candidate": str(args.candidate.resolve()),
        "candidate_skill_id": candidate.skill_id,
        "pairs": len(cells),
        "auto_start_server": not args.no_start_server,
    }
    manifest = build_manifest(run_id, config_path, config, execution)
    manifest["phase"] = 4
    manifest["candidate_skill"] = candidate.model_dump(mode="json")
    manifest_path = run_root / "manifest.json"
    atomic_json(manifest_path, manifest)
    adapter = DLawBenchAdapter(CASES, PERSONAS)
    failures: list[dict[str, str]] = []
    with LocalVLLMServer(
        config, run_root / "vllm_server.log", auto_start=not args.no_start_server
    ) as client:
        for index, (case_id, persona) in enumerate(cells, 1):
            pair_id = f"{case_id}__{persona}"
            pair_seed = stable_seed(config["seed"], "phase4", candidate.skill_id, pair_id)
            for condition, library in (("without", without), ("with", with_candidate)):
                path = run_root / "trajectories" / condition / f"{pair_id}.json"
                if path.is_file():
                    continue
                try:
                    trajectory = run_stateful_trajectory(
                        run_id=run_id,
                        method="Ours_legal_skill_guard",
                        partition=partition,
                        case_id=case_id,
                        persona=persona,
                        adapter=adapter,
                        client=client,
                        config=config,
                        seed_override=pair_seed,
                        skill_path=library,
                        skill_version=f"seed_v0.1.0_{condition}_{candidate.skill_id}",
                        executable_skills=True,
                    )
                    # Both sides intentionally share the rollout seed and policy method.
                    # The condition suffix prevents evaluator/session-key collisions while
                    # leaving the skill switch as the only behavioral intervention.
                    trajectory.trajectory_id = f"{trajectory.trajectory_id}__{condition}"
                    atomic_json(path, trajectory.model_dump(mode="json"))
                except Exception as exc:
                    failures.append(
                        {"pair_id": pair_id, "condition": condition, "error": str(exc)}
                    )
                    print(f"FAILED {pair_id} {condition}: {exc}", flush=True)
            print(f"pair {index}/{len(cells)} {pair_id}", flush=True)
    completed = len(list((run_root / "trajectories").glob("*/*.json")))
    manifest.update(
        status="failed" if failures else "pairs_collected",
        completed_at=datetime.now(UTC).isoformat(),
        expected_trajectories=2 * len(cells),
        completed_trajectories=completed,
        failures=failures,
    )
    atomic_json(manifest_path, manifest)
    if failures or completed != 2 * len(cells):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
