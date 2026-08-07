#!/usr/bin/env python3
"""Validate Phase 1 trajectories and generate deterministic custom metrics."""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

from legal_skill_guard.schemas.trajectory import Trajectory
from scripts.run_phase1_baseline import DEFAULT_CONFIG, ROOT, atomic_json, load_yaml

REQUIRED_MEMO_SECTIONS = ("案情概要", "关键事实", "法律问题", "风险评估", "下一步建议")


def mean(values: list[int | float]) -> float:
    return round(statistics.fmean(values), 4) if values else 0.0


def normalized_question(value: str) -> str:
    return "".join(value.split()).strip("，。？！：；,.?!:;")


def summarize(records: list[Trajectory]) -> dict[str, Any]:
    questions = [
        normalized_question(step.rendered_question)
        for record in records
        for step in record.steps
        if step.rendered_question
    ]
    duplicate_questions = sum(count - 1 for count in Counter(questions).values() if count > 1)
    trajectories_with_internal_repeat = 0
    for record in records:
        local = [
            normalized_question(step.rendered_question)
            for step in record.steps
            if step.rendered_question
        ]
        trajectories_with_internal_repeat += int(len(local) != len(set(local)))

    actions = [step.proposed_action for record in records for step in record.steps]
    prompt_tokens = [sum(step.token_usage.prompt for step in record.steps) for record in records]
    completion_tokens = [
        sum(step.token_usage.completion for step in record.steps) for record in records
    ]
    turns = [sum(step.rendered_question is not None for step in record.steps) for record in records]
    return {
        "trajectories": len(records),
        "unique_cases": len({record.case_id for record in records}),
        "personas": sorted({record.persona for record in records}),
        "status_counts": dict(sorted(Counter(record.status for record in records).items())),
        "mean_dialogue_turns": mean(turns),
        "max_dialogue_turns_observed": max(turns, default=0),
        "mean_prompt_tokens": mean(prompt_tokens),
        "mean_completion_tokens": mean(completion_tokens),
        "mean_total_tokens": mean(
            [a + b for a, b in zip(prompt_tokens, completion_tokens, strict=True)]
        ),
        "mean_memo_characters": mean([len(record.memo) for record in records]),
        "nonempty_memo_rate": mean([bool(record.memo.strip()) for record in records]),
        "five_section_memo_rate": mean(
            [
                all(section in record.memo for section in REQUIRED_MEMO_SECTIONS)
                for record in records
            ]
        ),
        "forced_memo_rate": mean(
            [record.status == "max_turns_forced_memo" for record in records]
        ),
        "structured_action_parse_rate": mean(
            [action.parse_mode in {"json", "json_fragment"} for action in actions]
        ),
        "fallback_action_count": sum(action.parse_mode == "fallback" for action in actions),
        "questions": len(questions),
        "exact_duplicate_question_rate": (
            round(duplicate_questions / len(questions), 4) if questions else 0.0
        ),
        "trajectories_with_internal_exact_repeat": trajectories_with_internal_repeat,
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
    paths = sorted((run_root / "trajectories").glob("*/*.json"))
    records = [Trajectory.model_validate_json(path.read_text(encoding="utf-8")) for path in paths]
    by_method = {
        method: summarize([record for record in records if record.method == method])
        for method in sorted({record.method for record in records})
    }
    by_method_persona = {
        f"{method}::{persona}": summarize(
            [
                record
                for record in records
                if record.method == method and record.persona == persona
            ]
        )
        for method, persona in sorted({(record.method, record.persona) for record in records})
    }
    expected = int(manifest.get("expected_trajectories") or 0)
    metrics = {
        "schema_version": 1,
        "run_id": args.run_id,
        "integrity": {
            "manifest_status": manifest.get("status"),
            "expected_trajectories": expected,
            "observed_trajectories": len(records),
            "complete": expected == len(records) and not manifest.get("failures"),
            "schema_valid": True,
        },
        "overall": summarize(records),
        "by_method": by_method,
        "by_method_persona": by_method_persona,
    }
    output = run_root / "evaluations/custom_metrics.json"
    atomic_json(output, metrics)
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    if not metrics["integrity"]["complete"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
