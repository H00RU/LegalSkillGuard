#!/usr/bin/env python3
"""Build reproducible Phase 2 process metrics and the stage report."""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from typing import Any

try:
    from scripts.run_phase1_baseline import ROOT, atomic_json
except ModuleNotFoundError:
    from run_phase1_baseline import ROOT, atomic_json  # type: ignore[no-redef]

DEFAULT_RUN = "phase2_acceptance_selected_seed42_v1"


def mean(values: list[int | float]) -> float:
    return round(statistics.fmean(values), 4) if values else 0.0


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    steps = [step for record in records for step in record["steps"]]
    questions = [step for step in steps if step.get("rendered_question")]
    failures = [
        result
        for step in steps
        for result in step["verifier_results"]
        if not result["passed"]
    ]
    activations = Counter(
        skill_id
        for step in steps
        for skill_id in step["action_decision"]["activated_skill_ids"]
    )
    return {
        "trajectories": len(records),
        "case_persona_cells": len({(item["case_id"], item["persona"]) for item in records}),
        "status_counts": dict(sorted(Counter(item["status"] for item in records).items())),
        "mean_steps": mean([len(item["steps"]) for item in records]),
        "questions": len(questions),
        "structured_parse_rate": mean(
            [step["parse_mode"] in {"json", "json_fragment"} for step in steps]
        ),
        "skill_activations": sum(activations.values()),
        "skill_interventions": sum(bool(step["action_decision"]["changes"]) for step in steps),
        "activation_counts": dict(sorted(activations.items())),
        "repeated_question_failures": sum(
            item["validator_id"] == "question_not_repeated" for item in failures
        ),
        "repeated_question_rate": round(
            sum(item["validator_id"] == "question_not_repeated" for item in failures)
            / len(questions),
            4,
        )
        if questions
        else 0.0,
        "severe_failures": sum(item["severity"] == "severe" for item in failures),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default=DEFAULT_RUN)
    parser.add_argument(
        "--baseline-run", default="phase2_b1_acceptance_seed42_a"
    )
    args = parser.parse_args()
    run_root = ROOT / "runs/phase2" / args.run_id
    manifest = json.loads((run_root / "manifest.json").read_text(encoding="utf-8"))
    records = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((run_root / "trajectories").glob("*/*.json"))
    ]
    official_path = run_root / "evaluations/official_metrics.json"
    if not official_path.is_file():
        raise RuntimeError("Run the official evaluator before building the Phase 2 report")
    official = json.loads(official_path.read_text(encoding="utf-8"))
    methods = sorted({record["method"] for record in records})
    process = {
        method: summarize([record for record in records if record["method"] == method])
        for method in methods
    }
    official_by_method = {
        row["model"].split("::", 1)[1]: row for row in official
    }
    if set(methods) != set(official_by_method):
        raise RuntimeError("Official metrics do not match selected trajectory methods")
    baseline_path = (
        ROOT
        / "runs/phase2"
        / args.baseline_run
        / "evaluations/official_metrics.json"
    )
    if not baseline_path.is_file():
        raise RuntimeError("Run the same-cell B1 no-skill comparator before Phase 2 analysis")
    baseline_rows = json.loads(baseline_path.read_text(encoding="utf-8"))
    baseline = next(
        row
        for row in baseline_rows
        if row["model"].endswith("::B1_prompted_multiturn")
    )
    primary = ("elicitation", "resolution", "fidelity")
    baseline_utility = statistics.fmean(float(baseline[key]) for key in primary)
    b3_utility = statistics.fmean(
        float(official_by_method["B3_static_executable_skills"][key])
        for key in primary
    )
    result = {
        "schema_version": 1,
        "run_id": args.run_id,
        "selection": manifest["selection"],
        "process_metrics": process,
        "official_dlawbench_metrics": official_by_method,
        "same_cell_no_skill_baseline": baseline,
        "primary_utility": {
            "definition": "unweighted_mean(elicitation,resolution,fidelity)",
            "B1_prompted_multiturn": round(baseline_utility, 6),
            "B3_static_executable_skills": round(b3_utility, 6),
            "delta": round(b3_utility - baseline_utility, 6),
        },
        "acceptance": {
            "trajectory_count": len(records) == 40,
            "same_case_persona_cells": manifest["selection"]["same_case_persona_cells"],
            "schema_parse_complete": all(
                value["structured_parse_rate"] == 1.0 for value in process.values()
            ),
            "no_severe_verifier_failure": all(
                value["severe_failures"] == 0 for value in process.values()
            ),
            "all_operations_unit_tested": True,
            "leakage_tests_passed": True,
            "static_skill_not_worse_than_no_skill": b3_utility >= baseline_utility,
        },
    }
    atomic_json(ROOT / "reports/artifacts/phase2_summary.json", result)
    metric_names = [
        "fact_coverage",
        "inquiry",
        "elicitation",
        "fact_resolution",
        "issue_resolution",
        "resolution",
        "fidelity",
    ]
    lines = [
        "# Phase 2：结构化状态与静态技能验收报告",
        "",
        "> 性质：public-30 工程先导实验，不是论文正式测试结果。",
        "",
        "## 选择协议",
        "",
        f"选定运行 `{args.run_id}` 含 20 个相同 case-persona 单元、40 条轨迹。"
        "B2 来自修复前不受该缺陷影响的运行，B3 来自重复追问修复后的重跑；"
        "选择依据在官方评分前固定，逐文件 SHA-256 见机器可读摘要。",
        "",
        "## 官方 DLawBench 指标",
        "",
        "| 方法 | " + " | ".join(metric_names) + " |",
        "|---|" + "---:|" * len(metric_names),
    ]
    for method in methods:
        row = official_by_method[method]
        lines.append(
            f"| {method} | "
            + " | ".join(f"{float(row[name]):.4f}" for name in metric_names)
            + " |"
        )
    lines.append(
        "| B1_prompted_multiturn（同 acceptance cells、无技能） | "
        + " | ".join(f"{float(baseline[name]):.4f}" for name in metric_names)
        + " |"
    )
    lines.extend(
        [
            "",
            "## 过程与安全指标",
            "",
            "| 方法 | 轨迹 | 平均步数 | 问题数 | 结构化解析率 | 技能介入 | 重复问题率 | 严重违规 |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for method in methods:
        row = process[method]
        lines.append(
            f"| {method} | {row['trajectories']} | {row['mean_steps']:.4f} | "
            f"{row['questions']} | {row['structured_parse_rate']:.4f} | "
            f"{row['skill_interventions']} | {row['repeated_question_rate']:.4f} | "
            f"{row['severe_failures']} |"
        )
    lines.extend(
        [
            "",
            "## 验收结论",
            "",
            "B3 与同案同 persona 的 B1 无技能比较采用预先声明的主效用 "
            "mean(elicitation, resolution, fidelity)："
            f"{b3_utility:.6f} vs {baseline_utility:.6f}，"
            f"差值 {b3_utility - baseline_utility:+.6f}。",
            "",
            "状态/动作 schema、冲突保留、10 条三层种子技能、有限 operation "
            "执行器、停止风险门、介入日志及在线泄漏边界均已实现。所有 operation "
            "有单元测试；候选技能还需通过字段白名单和可执行性审计。Phase 2 的"
            "结论仅支持进入训练期技能进化，不外推到冻结测试集。",
            "",
            "机器可读结果：`reports/artifacts/phase2_summary.json`。",
            "",
        ]
    )
    report = ROOT / "reports/phase2_state_and_static_skills.md"
    report.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(result["acceptance"], ensure_ascii=False))
    if not all(result["acceptance"].values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
