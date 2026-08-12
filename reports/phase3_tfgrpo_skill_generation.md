# Phase 3：TF-GRPO 轨迹归因与候选技能报告

> 性质：public-30 训练分区工程先导实验，不是冻结测试集结果。

## 运行规模

- 有效同案同 persona 轨迹组：50；每组 K=4。
- 轨迹/官方评分会话：200/200。
- 信息性组/低方差跳过组：46/4。
- 平均训练期标量奖励：0.504880。

## 教师诊断与静态门

教师诊断 46 个信息性组；proposal 计数：`{"CREATE": 3, "REFINE": 0, "REPAIR": 0, "MERGE": 0, "SPLIT": 0, "DEPRECATE": 0, "NOOP": 43}`。
静态拒绝 35 个；最终可执行候选技能 3 个：`["evolved.final_with_unverified_claim_guard", "final_action_target_consistency_guard", "final_fact_confirmation_guard"]`。

低方差组不会被强制生成经验；教师解析失败、占位 ID、未知状态字段、具体案件触发和结构重复均转为 NOOP，并保存原始输出、prompt/payload hash 及来源轨迹。

## 验收结论

50 组门槛、官方评分、组内标准化优势、高低/安全/效率对照选择、结构化诊断、NOOP 与候选 provenance 均由机器可读产物验证。候选仍是 candidate，不能在 Phase 4 成对门控之前进入活动技能库。

机器可读结果：`reports/artifacts/phase3_summary.json`。
