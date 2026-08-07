#!/usr/bin/env python3
"""Compare two Phase 1 runs after removing non-semantic runtime fields."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from legal_skill_guard.utils.hashing import canonical_json_sha256
from scripts.run_phase1_baseline import ROOT, atomic_json


def normalized_trajectory(value: dict[str, Any]) -> dict[str, Any]:
    result = json.loads(json.dumps(value, ensure_ascii=False))
    result.pop("run_id", None)
    result.pop("created_at", None)
    result.pop("elapsed_seconds", None)
    for step in result.get("steps", []):
        step.pop("latency_ms", None)
    return result


def load_run(run_id: str) -> dict[str, str]:
    root = ROOT / "runs/phase1" / run_id / "trajectories"
    values: dict[str, str] = {}
    for path in sorted(root.glob("*/*.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        key = str(path.relative_to(root))
        values[key] = canonical_json_sha256(normalized_trajectory(value))
    return values


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_a")
    parser.add_argument("run_b")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    left = load_run(args.run_a)
    right = load_run(args.run_b)
    keys = sorted(set(left) | set(right))
    mismatches = [key for key in keys if left.get(key) != right.get(key)]
    result = {
        "schema_version": 1,
        "run_a": args.run_a,
        "run_b": args.run_b,
        "semantic_fields_excluded": [
            "run_id",
            "created_at",
            "elapsed_seconds",
            "steps[].latency_ms",
        ],
        "trajectory_keys_equal": set(left) == set(right),
        "trajectories_compared": len(keys),
        "semantic_hashes_equal": not mismatches,
        "mismatches": mismatches,
        "hashes_a": left,
        "hashes_b": right,
    }
    output = args.output or (
        ROOT / "runs/phase1" / args.run_b / "evaluations/reproducibility.json"
    )
    atomic_json(output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["trajectory_keys_equal"] or mismatches:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
