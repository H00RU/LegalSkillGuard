"""Report only saved observations; never make model calls or alter a skill."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from legal_skill_guard.experiment.storage import RunStore


def _number(value):
    return "N/A" if value is None else f"{100 * value:.2f}"


def _completed_comparisons(value):
    """The three actual saved completion formats, not inferred/missing results."""
    if "prequential_results" in value:
        sections = [("在线首次遇到比较（不同库状态，非固定末库测试）", value["prequential_results"])]
    elif "development" in value:
        sections = [("固定末次库的开发迁移评估", value["development"])]
    elif "results" in value:
        sections = [("固定末次库的开发比较", value["results"])]
    elif "main_results" in value and "probe_results" in value:
        sections = [
            ("主开发比较", value["main_results"]),
            ("独立来源交付/示例探针", value["probe_results"]),
        ]
    else:
        raise ValueError("Unrecognized completion format; do not invent a comparison")
    for title, metrics in sections:
        if not metrics:
            raise ValueError(f"Empty completed comparison: {title}")
        sizes = {(m["documents"], m["hypotheses"]) for m in metrics.values()}
        if len(sizes) != 1:
            raise ValueError(f"Inconsistent comparison denominators: {title}")
    return sections


def write_report(run: Path):
    done = run / "completion.json"
    sections = _completed_comparisons(json.loads(done.read_text())) if done.exists() else []
    summaries = [json.loads(p.read_text()) for p in sorted(run.glob("batch*_summary.json"))]
    rows = []
    for summary in summaries:
        phase_keys = (
            (("before", "before"), ("after", "after"))
            if "before" in summary
            else (("before", "before_first_encounter"), ("after", "after_seen_training_fit"))
        )
        strong = summary.get("strong_empty")
        for phase, key in phase_keys:
            for arm, m in summary[key].items():
                rows.append(
                    {
                        "batch": summary["batch"],
                        "phase": phase,
                        "arm": arm,
                        "documents": m["documents"],
                        "hypotheses": m["hypotheses"],
                        "accuracy": m["label_accuracy"],
                        "evidence_precision": m["evidence_tp"]
                        / (m["evidence_tp"] + m["evidence_fp"])
                        if m["evidence_tp"] + m["evidence_fp"]
                        else None,
                        "evidence_recall": m["evidence_tp"] / (m["evidence_tp"] + m["evidence_fn"])
                        if m["evidence_tp"] + m["evidence_fn"]
                        else None,
                        "evidence_micro_f1": m["evidence_micro_f1_gold_non_neutral"],
                        "joint_exact_accuracy": m["joint_exact_accuracy"],
                        "same_batch_strong_accuracy": strong["label_accuracy"]
                        if strong is not None
                        else None,
                        "same_batch_strong_evidence_micro_f1": strong[
                            "evidence_micro_f1_gold_non_neutral"
                        ]
                        if strong is not None
                        else None,
                    }
                )
    stream = io.StringIO()
    if rows:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    # Reports are derived, replaceable outputs; immutable native artifacts stay untouched.
    run.mkdir(parents=True, exist_ok=True)
    (run / "training_curve.csv").write_text(stream.getvalue())
    lines = [
        "# 当前运行的真实结果",
        "",
        "before＝本批首次遇到；after＝教师见过本批标签后的拟合。不同批次不等难。",
        "以下依据本Run的显式保存/引用；历史逐请求相同的控制不是新生成或独立重复，不以技能数证明收益。",
        "",
        "|批次|条件|阶段|分类 %|依据 F1 %|联合全对 %|",
        "|---|---|---|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "|"
            + "|".join(str(row[k]) for k in ("batch", "arm", "phase"))
            + "|"
            + "|".join(
                _number(row[k]) for k in ("accuracy", "evidence_micro_f1", "joint_exact_accuracy")
            )
            + "|"
        )
    if done.exists():
        for title, metrics in sections:
            documents, hypotheses = next(
                iter({(m["documents"], m["hypotheses"]) for m in metrics.values()})
            )
            lines += [
                "",
                f"## {title}：每条件{documents}份合同、{hypotheses}个命题",
                "",
                "不是官方测试；命题数不是独立来源数，单个学习副本不支持跨学习稳定性结论。",
                "",
                "|条件|分类 %|依据 F1 %|联合全对 %|",
                "|---|---:|---:|---:|",
            ]
            for arm, m in metrics.items():
                lines.append(
                    "|"
                    + arm
                    + "|"
                    + "|".join(
                        _number(m[k])
                        for k in (
                            "label_accuracy",
                            "evidence_micro_f1_gold_non_neutral",
                            "joint_exact_accuracy",
                        )
                    )
                    + "|"
                )
    else:
        lines += ["", "[PENDING RESULT — 全部终点回答尚未完成，未读取终点评分标签。]"]
    (run / "results.md").write_text("\n".join(lines) + "\n")
    RunStore.atomic_json(
        run / "report_status.json",
        {
            "completed_batches": len(summaries),
            "final_comparison_complete": done.exists(),
            "new_model_calls": 0,
            "new_teacher_calls": 0,
        },
    )
    return {"completed_batches": len(summaries), "final_comparison_complete": done.exists()}
