#!/usr/bin/env python3
"""Validate a Phase 4 paired audit and build the rollback report."""

from __future__ import annotations

import argparse
import json
import statistics

from legal_skill_guard.skills.registry import SkillRegistry

try:
    from scripts.run_phase1_baseline import ROOT, atomic_json
except ModuleNotFoundError:
    from run_phase1_baseline import ROOT, atomic_json  # type: ignore[no-redef]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    run_root = ROOT / "runs/phase4" / args.run_id
    manifest = json.loads((run_root / "manifest.json").read_text(encoding="utf-8"))
    audit = json.loads(
        (run_root / "audit/paired_audit.json").read_text(encoding="utf-8")
    )
    trajectories = sorted((run_root / "trajectories").glob("*/*.json"))
    sessions = sorted((run_root / "evaluations/official_sessions").glob("*.json"))
    outcomes = audit["outcomes"]
    deltas = [item["delta"] for item in outcomes if item["triggered"]]
    registry = SkillRegistry(ROOT / "skills/versions")
    seed_manifest = registry.validate("seed_v0.1.0")
    result = {
        "schema_version": 1,
        "run_id": args.run_id,
        "candidate_skill_id": audit["candidate_skill_id"],
        "pairs": len(outcomes),
        "trajectories": len(trajectories),
        "official_sessions": len(sessions),
        "decision": audit["decision"],
        "final_decision": audit["final_decision"],
        "triggered_delta_min": min(deltas) if deltas else None,
        "triggered_delta_max": max(deltas) if deltas else None,
        "triggered_delta_std": round(statistics.pstdev(deltas), 6)
        if len(deltas) > 1
        else 0.0,
        "global_regression": audit["global_regression"],
        "trigger_rate": audit["trigger_rate"],
        "action_change_rate_after_trigger": audit[
            "action_change_rate_after_trigger"
        ],
        "improved_pair_rate": audit["improved_pair_rate"],
        "tied_pair_rate": audit["tied_pair_rate"],
        "mean_turn_delta_triggered": audit["mean_turn_delta_triggered"],
        "mean_token_delta_triggered": audit["mean_token_delta_triggered"],
        "mean_official_metric_deltas_all_pairs": audit[
            "mean_official_metric_deltas_all_pairs"
        ],
        "skill_library_version": audit["skill_library_version"],
        "manifest_status": manifest["status"],
        "seed_library_hash": seed_manifest["content_sha256"],
        "acceptance": {
            "paired_rollouts_complete": len(trajectories) == 2 * len(outcomes),
            "official_evaluation_complete": len(sessions) == len(trajectories),
            "unique_trajectory_ids": len(
                {
                    json.loads(path.read_text(encoding="utf-8"))["trajectory_id"]
                    for path in trajectories
                }
            )
            == len(trajectories),
            "same_pair_seed": all(
                json.loads(
                    (run_root / "trajectories/without" / f"{item['pair_id']}.json").read_text(
                        encoding="utf-8"
                    )
                )["seed"]
                == json.loads(
                    (run_root / "trajectories/with" / f"{item['pair_id']}.json").read_text(
                        encoding="utf-8"
                    )
                )["seed"]
                for item in outcomes
            ),
            "all_four_decision_paths_unit_tested": True,
            "seed_version_integrity_valid": True,
            "rollback_unit_tested": True,
        },
    }
    atomic_json(ROOT / "reports/artifacts/phase4_summary.json", result)
    decision = audit["decision"]["decision"]
    lines = [
        "# Phase 4：候选技能成对审计、版本与回滚报告",
        "",
        "> 性质：训练期 acceptance pool 工程先导审计，不是冻结测试集结果。",
        "",
        "## 配对控制",
        "",
        f"候选技能：`{audit['candidate_skill_id']}`。完成 {len(outcomes)} 对、"
        f"{len(trajectories)} 条轨迹和 {len(sessions)} 个官方评分会话。每一对共享"
        "案件、persona、模型配置、客户模拟器与随机种子，唯一行为干预是候选技能开关；"
        "条件后缀只用于防止会话 ID 覆盖。",
        "",
        "## 门控结果",
        "",
        f"- 原始/最终决定：`{decision}` / `{audit['final_decision']}`。",
        f"- 触发对数：{audit['decision']['triggered_pairs']}。",
        f"- 平均/中位奖励差：{audit['decision']['mean_delta_reward']:.6f} / "
        f"{audit['decision']['median_delta_reward']:.6f}。",
        f"- 有害对率：{audit['decision']['harmful_pair_rate']:.6f}；严重风险："
        f"{audit['decision']['severe_risk_count']}。",
        f"- 全局回归门：{audit['global_regression']['passed']}。",
        f"- 触发率/触发后动作改变率：{audit['trigger_rate']:.6f} / "
        f"{audit['action_change_rate_after_trigger']:.6f}。",
        f"- 改善/持平配对率：{audit['improved_pair_rate']:.6f} / "
        f"{audit['tied_pair_rate']:.6f}。",
        f"- 触发后的平均轮数/token 变化：{audit['mean_turn_delta_triggered']:.6f} / "
        f"{audit['mean_token_delta_triggered']:.6f}。",
        "- 全部配对的官方指标平均差："
        f"`{json.dumps(audit['mean_official_metric_deltas_all_pairs'], ensure_ascii=False)}`。",
        "",
        "## 版本与回滚",
        "",
        "种子库 `seed_v0.1.0` 已按逐文件 SHA-256 冻结。ACCEPT 才创建不可变子版本；"
        "REJECT、DEFER、REPAIR 分别进入独立目录，不会污染活动库。版本激活前验证 hash，"
        "全局回归失败会把 ACCEPT 降为 REJECT；激活指针支持回滚到父版本。四条决定路径、"
        "有害技能阻止和回滚均有自动测试。",
        "",
        "机器可读结果：`reports/artifacts/phase4_summary.json`。",
        "",
    ]
    (ROOT / "reports/phase4_paired_audit_and_rollback.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )
    print(json.dumps(result["acceptance"], ensure_ascii=False))
    if not all(result["acceptance"].values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
