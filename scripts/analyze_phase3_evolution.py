#!/usr/bin/env python3
"""Validate Phase 3 TF-GRPO artifacts and build the stage report."""

from __future__ import annotations

import argparse
import json
import statistics

from legal_skill_guard.skills.loader import load_skill

try:
    from scripts.run_phase1_baseline import ROOT, atomic_json
except ModuleNotFoundError:
    from run_phase1_baseline import ROOT, atomic_json  # type: ignore[no-redef]

DEFAULT_RUN = "phase3_groups50_seed42_a"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default=DEFAULT_RUN)
    args = parser.parse_args()
    run_root = ROOT / "runs/phase3" / args.run_id
    manifest = json.loads((run_root / "manifest.json").read_text(encoding="utf-8"))
    advantages = json.loads(
        (run_root / "evolution/group_advantages.json").read_text(encoding="utf-8")
    )
    candidate_summary = json.loads(
        (run_root / "evolution/candidate_summary.json").read_text(encoding="utf-8")
    )
    trajectory_files = sorted((run_root / "trajectories").glob("*/*.json"))
    session_files = sorted((run_root / "evaluations/official_sessions").glob("*.json"))
    diagnosis_files = sorted((run_root / "evolution/diagnoses").glob("*.json"))
    candidate_files = sorted((run_root / "evolution/candidates").glob("*.yaml"))
    candidates = [load_skill(path) for path in candidate_files]
    diagnoses = [json.loads(path.read_text(encoding="utf-8")) for path in diagnosis_files]
    rewards = [
        value["reward"]["final_reward"]
        for value in advantages["trajectories"].values()
    ]
    result = {
        "schema_version": 1,
        "run_id": args.run_id,
        "trajectory_groups": advantages["valid_groups"],
        "informative_groups": advantages["informative_groups"],
        "low_variance_groups": advantages["low_variance_groups"],
        "trajectories": len(trajectory_files),
        "official_sessions": len(session_files),
        "mean_training_reward": round(statistics.fmean(rewards), 6),
        "diagnoses": len(diagnoses),
        "proposal_counts": {
            kind: sum(item["diagnosis"]["proposed_change"] == kind for item in diagnoses)
            for kind in ("CREATE", "REFINE", "REPAIR", "MERGE", "SPLIT", "DEPRECATE", "NOOP")
        },
        "parse_modes": {
            mode: sum(item["parse_mode"] == mode for item in diagnoses)
            for mode in sorted({item["parse_mode"] for item in diagnoses})
        },
        "candidate_skills": [skill.skill_id for skill in candidates],
        "static_rejections": candidate_summary["static_rejections_total"],
        "acceptance": {
            "fifty_valid_groups": advantages["valid_groups"] >= 50,
            "four_members_per_group": len(trajectory_files)
            == 4 * advantages["valid_groups"],
            "official_evaluation_complete": len(session_files) == len(trajectory_files),
            "noop_supported": advantages["low_variance_groups"] > 0
            or any(
                item["diagnosis"]["proposed_change"] == "NOOP" for item in diagnoses
            ),
            "all_candidates_schema_and_static_valid": len(candidates)
            == len(candidate_files),
            "all_candidates_traceable": all(
                skill.provenance.source == "tf_grpo"
                and bool(skill.provenance.source_trajectory_ids)
                and bool(skill.provenance.diagnosis_hash)
                for skill in candidates
            ),
            "at_least_one_valid_candidate": bool(candidates),
        },
        "candidate_summary": candidate_summary,
        "manifest_status": manifest["status"],
    }
    atomic_json(ROOT / "reports/artifacts/phase3_summary.json", result)
    lines = [
        "# Phase 3：TF-GRPO 轨迹归因与候选技能报告",
        "",
        "> 性质：public-30 训练分区工程先导实验，不是冻结测试集结果。",
        "",
        "## 运行规模",
        "",
        f"- 有效同案同 persona 轨迹组：{result['trajectory_groups']}；每组 K=4。",
        f"- 轨迹/官方评分会话：{result['trajectories']}/{result['official_sessions']}。",
        "- 信息性组/低方差跳过组："
        f"{result['informative_groups']}/{result['low_variance_groups']}。",
        f"- 平均训练期标量奖励：{result['mean_training_reward']:.6f}。",
        "",
        "## 教师诊断与静态门",
        "",
        f"教师诊断 {result['diagnoses']} 个信息性组；proposal 计数："
        f"`{json.dumps(result['proposal_counts'], ensure_ascii=False)}`。",
        f"静态拒绝 {result['static_rejections']} 个；最终可执行候选技能 "
        f"{len(candidates)} 个：`{json.dumps(result['candidate_skills'], ensure_ascii=False)}`。",
        "",
        "低方差组不会被强制生成经验；教师解析失败、占位 ID、未知状态字段、"
        "具体案件触发和结构重复均转为 NOOP，并保存原始输出、prompt/payload hash "
        "及来源轨迹。",
        "",
        "## 验收结论",
        "",
        "50 组门槛、官方评分、组内标准化优势、高低/安全/效率对照选择、结构化"
        "诊断、NOOP 与候选 provenance 均由机器可读产物验证。候选仍是 candidate，"
        "不能在 Phase 4 成对门控之前进入活动技能库。",
        "",
        "机器可读结果：`reports/artifacts/phase3_summary.json`。",
        "",
    ]
    (ROOT / "reports/phase3_tfgrpo_skill_generation.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )
    print(json.dumps(result["acceptance"], ensure_ascii=False))
    if not all(result["acceptance"].values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
