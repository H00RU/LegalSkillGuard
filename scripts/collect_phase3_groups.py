#!/usr/bin/env python3
"""Collect K=4 stateful trajectories for 50 same-case same-persona TF-GRPO groups."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

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

from legal_skill_guard.environment.dlawbench_adapter import DLawBenchAdapter

DEFAULT_CONFIG = ROOT / "configs/experiments/phase3_tfgrpo.yaml"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--run-id")
    parser.add_argument("--group-limit", type=int)
    parser.add_argument("--no-start-server", action="store_true")
    args = parser.parse_args()
    config_path = args.config.resolve()
    config = load_yaml(config_path)
    split = json.loads((ROOT / config["data"]["split_manifest"]).read_text(encoding="utf-8"))
    partition = config["data"]["run_partition"]
    cells = [
        (case_id, persona)
        for case_id in split["partitions"][partition]["case_ids"]
        for persona in config["data"]["personas"]
    ]
    target = args.group_limit or int(config["evolution"]["target_valid_groups"])
    cells = cells[:target]
    group_size = int(config["evolution"]["group_size"])
    run_id = args.run_id or f"phase3_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
    run_root = ROOT / config["outputs"]["run_root"] / run_id
    execution = {
        "workers": 1,
        "group_size": group_size,
        "target_groups": len(cells),
        "auto_start_server": not args.no_start_server,
    }
    manifest_path = run_root / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        manifest = build_manifest(run_id, config_path, config, execution)
        manifest["phase"] = 3
        manifest["evolution"] = config["evolution"]
        atomic_json(manifest_path, manifest)
    adapter = DLawBenchAdapter(CASES, PERSONAS)
    failures: list[dict[str, str]] = []
    expected = len(cells) * group_size
    with LocalVLLMServer(
        config, run_root / "vllm_server.log", auto_start=not args.no_start_server
    ) as client:
        for group_index, (case_id, persona) in enumerate(cells, start=1):
            group_id = f"{case_id}__{persona}"
            for sample_index in range(group_size):
                path = (
                    run_root
                    / "trajectories/B3_static_executable_skills"
                    / f"{group_id}__sample{sample_index}.json"
                )
                if path.is_file():
                    continue
                seed = stable_seed(config["seed"], "phase3", group_id, str(sample_index))
                try:
                    trajectory = run_stateful_trajectory(
                        run_id=run_id,
                        method="B3_static_executable_skills",
                        partition=partition,
                        case_id=case_id,
                        persona=persona,
                        adapter=adapter,
                        client=client,
                        config=config,
                        sample_index=sample_index,
                        seed_override=seed,
                    )
                    atomic_json(path, trajectory.model_dump(mode="json"))
                except Exception as exc:
                    failures.append(
                        {
                            "group_id": group_id,
                            "sample_index": sample_index,
                            "error": str(exc),
                        }
                    )
                    print(f"FAILED {group_id} sample={sample_index}: {exc}", flush=True)
            completed_group = len(
                list(
                    (run_root / "trajectories/B3_static_executable_skills").glob(
                        f"{group_id}__sample*.json"
                    )
                )
            )
            print(
                f"group {group_index}/{len(cells)} {group_id}: {completed_group}/{group_size}",
                flush=True,
            )
    completed = len(list((run_root / "trajectories").glob("*/*.json")))
    complete_groups = sum(
        len(
            list(
                (run_root / "trajectories/B3_static_executable_skills").glob(
                    f"{case_id}__{persona}__sample*.json"
                )
            )
        )
        == group_size
        for case_id, persona in cells
    )
    manifest.update(
        status="failed" if failures else "groups_collected",
        completed_at=datetime.now(UTC).isoformat(),
        expected_trajectories=expected,
        completed_trajectories=completed,
        valid_groups=complete_groups,
        failures=failures,
    )
    atomic_json(manifest_path, manifest)
    if failures or completed != expected or complete_groups != len(cells):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

