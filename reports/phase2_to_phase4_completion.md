# Phase 2–4 框架完成与实验断点报告

> 范围：Qwen3-4B、DLawBench public-30 工程先导；不是论文 Phase 5 冻结测试结论。

## 结论

LegalSkillGuard 的在线咨询环、离线技能进化环、候选技能门控和版本回滚闭环已经贯通。Phase 2、3、4 的实施方案完成标准均有真实模型轨迹、官方 DLawBench 评分和机器可读产物支持，不以“代码文件存在”代替验收。

活动技能库仍为 `seed_v0.1.0`。这是门禁的预期结果：Phase 3 产生的首个高覆盖候选虽然提高平均训练期 reward，但有害配对率超阈值，因此进入 `REPAIR` 而没有污染活动库。

## 与实施方案的逐阶段对齐

| 阶段 | 方案完成标准 | 实测证据 | 结论 |
|---|---|---|---|
| Phase 2 | operation 单测、无泄漏、介入可追踪、静态技能不劣于无技能 | 20 个同案同 persona 单元；B2/B3 40 条轨迹和官方评分；B1 同单元 20 条对照；B3 主效用 0.676100，B1 0.564067；差值 +0.112033 | 通过 |
| Phase 3 | 至少 50 个有效组、schema 有效、支持 NOOP、来源可追溯 | 50 组 × K=4；200 条轨迹和 200 个官方评分；46 个信息性组、4 个低方差组；43 个 NOOP、3 个 CREATE；3 个静态有效候选 | 通过 |
| Phase 4 | 四条决策路径、有害技能阻止、可回滚、审计报告 | 20 对/40 条轨迹/40 个官方评分；10 个触发对；平均差 +0.053794；有害率 0.30 > 0.15；最终 `REPAIR`；活动指针未改变 | 通过 |

## 关键运行与产物

- Phase 2 选定运行：`runs/phase2/phase2_acceptance_selected_seed42_v1`。
- Phase 2 同单元 B1：`runs/phase2/phase2_b1_acceptance_seed42_v2`。
- Phase 3：`runs/phase3/phase3_groups50_seed42_a`。
- Phase 4：`runs/phase4/phase4_evolved_final_guard_seed42_a`。
- 机器摘要：`reports/artifacts/phase2_summary.json`、`phase3_summary.json`、`phase4_summary.json`。
- 人类可读报告：`reports/phase2_state_and_static_skills.md`、`phase3_tfgrpo_skill_generation.md`、`phase4_paired_audit_and_rollback.md`。
- 待修订候选：`skills/repair/evolved.final_with_unverified_claim_guard__phase4_evolved_final_guard_seed42_a.yaml`。
- 活动版本指针：`skills/versions/current.json`，保持 `seed_v0.1.0`。

`runs/` 受 Git 忽略，但每个正式运行包含配置、数据、split、模型 revision、prompt、源码和 evaluator provenance。版本库保留聚合报告、候选决策和可复现代码。

## 断线前后问题及处理

1. Phase 3 教师原始 payload 超过 8192 token 上下文。轨迹摘要改为只保留决策所需动作字段，并把问题/客户回复各限制为 240 字；46 个教师输入随后全部落入安全 token 预算。原失败诊断被隔离保留，没有混入正式候选目录。
2. Phase 2 B1 对照配置使用了 Phase 2 policy 字段，而 Phase 1 runner 要求 `generation.lawyer`。首次 20/20 在推理前失败并保留失败 manifest；修复配置 schema 后以新 run-id 完成 20/20 生成和评分。
3. Phase 3 多 worker 官方评分的中断产物被移入 diagnostic 目录，正式指标以单 worker 从零生成，确保 200 个 session 来源一致。
4. Phase 4 候选只在临时 `with_candidate` 库激活；最终 `REPAIR` 没有创建 v0.2，也没有改变 active pointer。

## 尚未完成且不得混称为本阶段结果

Phase 0–4 完成意味着论文项目的工程框架闭环已经具备，不意味着论文实验已经完成。Phase 5 仍需在可获得的完整数据上重新固定 case-level train/acceptance/test split，冻结提示、模型、技能库和阈值，然后执行：

- B0–B6 与 Ours 的 RQ1 主矩阵；
- 核心消融与弱/强模型公平 2×2；
- 至少 3 个随机种子、配对置信区间和显著性检验；
- persona/领域分组、安全、效率和技能指标；
- Qwen3.5-9B 对比及后续教师替换方案。

当前 public DLawBench checkout 只有 30 个中国法公开案件，不是方案所述论文语料 264 案；LeCoDe 对话文件还需要机构签署申请。这两个限制必须在 Phase 5 数据协议中显式处理，不能用本次 engineering pilot 代替冻结测试结果。
