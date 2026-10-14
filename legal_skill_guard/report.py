"""Report only saved observations; never make model calls or alter a skill."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from legal_skill_guard.experiment.storage import RunStore


def _number(value):
    return "N/A" if value is None else f"{100 * value:.2f}"


def write_report(run: Path):
    summaries = [json.loads(p.read_text()) for p in sorted(run.glob("batch*_summary.json"))]
    rows = []
    for summary in summaries:
        for phase in ("before", "after"):
            for arm, m in summary[phase].items():
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
                        "same_batch_strong_accuracy": summary["strong_empty"]["label_accuracy"],
                        "same_batch_strong_evidence_micro_f1": summary["strong_empty"][
                            "evidence_micro_f1_gold_non_neutral"
                        ],
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
        "以下仅依据这个新 Run 保存的回答；不填历史成绩，不以技能数证明收益。",
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
    done = run / "completion.json"
    if done.exists():
        value = json.loads(done.read_text())
        lines += [
            "",
            "## 固定末次库：24个不同TRAIN来源的开发迁移评估",
            "",
            "不是官方测试；单个学习副本不支持跨学习稳定性结论。",
            "",
            "|条件|分类 %|依据 F1 %|联合全对 %|",
            "|---|---:|---:|---:|",
        ]
        for arm, m in value["development"].items():
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
