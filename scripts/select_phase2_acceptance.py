#!/usr/bin/env python3
"""Create a provenance-preserving Phase 2 selection from immutable source rollouts."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import UTC, datetime

from legal_skill_guard.utils.hashing import sha256_file

try:
    from scripts.run_phase1_baseline import ROOT, atomic_json
except ModuleNotFoundError:
    from run_phase1_baseline import ROOT, atomic_json  # type: ignore[no-redef]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default="phase2_acceptance_selected_seed42_v1")
    parser.add_argument("--b2-run", default="phase2_acceptance_seed42_a")
    parser.add_argument("--b3-run", default="phase2_acceptance_b3_seed42_v2")
    args = parser.parse_args()
    phase_root = ROOT / "runs/phase2"
    destination = phase_root / args.run_id
    selections = {
        "B2_static_text_skills": phase_root / args.b2_run,
        "B3_static_executable_skills": phase_root / args.b3_run,
    }
    records: list[dict[str, str]] = []
    observed_cells: dict[str, set[tuple[str, str]]] = {}
    for method, source_run in selections.items():
        source_manifest = json.loads(
            (source_run / "manifest.json").read_text(encoding="utf-8")
        )
        if source_manifest.get("status") not in {"complete", "evaluation_complete"}:
            raise RuntimeError(f"Source run is incomplete: {source_run}")
        source_files = sorted((source_run / "trajectories" / method).glob("*.json"))
        if len(source_files) != 20:
            raise RuntimeError(f"Expected 20 {method} trajectories, found {len(source_files)}")
        observed_cells[method] = set()
        for source in source_files:
            value = json.loads(source.read_text(encoding="utf-8"))
            if value["method"] != method:
                raise RuntimeError(f"Method mismatch in {source}")
            observed_cells[method].add((value["case_id"], value["persona"]))
            output = destination / "trajectories" / method / source.name
            output.parent.mkdir(parents=True, exist_ok=True)
            if output.exists() and sha256_file(output) != sha256_file(source):
                raise RuntimeError(f"Existing selected file differs: {output}")
            if not output.exists():
                shutil.copy2(source, output)
            records.append(
                {
                    "method": method,
                    "source_run_id": source_run.name,
                    "source": str(source.relative_to(ROOT)),
                    "selected": str(output.relative_to(ROOT)),
                    "sha256": sha256_file(source),
                }
            )
    if observed_cells["B2_static_text_skills"] != observed_cells[
        "B3_static_executable_skills"
    ]:
        raise RuntimeError("B2 and corrected B3 do not cover the same case-persona cells")
    base_manifest = json.loads(
        (selections["B3_static_executable_skills"] / "manifest.json").read_text(
            encoding="utf-8"
        )
    )
    base_manifest.update(
        run_id=args.run_id,
        status="selected_for_official_evaluation",
        started_at=datetime.now(UTC).isoformat(),
        completed_at=datetime.now(UTC).isoformat(),
        expected_trajectories=40,
        completed_trajectories=40,
        failures=[],
        execution={
            "workers": 0,
            "methods": list(selections),
            "selection_only": True,
            "source_runs": [args.b2_run, args.b3_run],
        },
        selection={
            "policy": "predeclared_bugfix_provenance_selection",
            "reason": (
                "B2 comes from the original acceptance rollout; B3 comes from the "
                "post-fix rerun that clears stale action content and rechecks skill "
                "preconditions. No score was used for selection."
            ),
            "same_case_persona_cells": True,
            "records": records,
        },
        prompt_sha256={
            str(path.relative_to(ROOT)): sha256_file(path)
            for path in sorted((ROOT / "configs/prompts").glob("phase1_*.txt"))
            + [ROOT / "configs/prompts/phase2_stateful_policy_zh.txt"]
        },
    )
    atomic_json(destination / "manifest.json", base_manifest)
    print(
        json.dumps(
            {
                "run_id": args.run_id,
                "trajectories": len(records),
                "cells": len(observed_cells["B2_static_text_skills"]),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
