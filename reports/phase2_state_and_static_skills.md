# Phase 2：结构化状态与静态技能验收报告

> 性质：public-30 工程先导实验，不是论文正式测试结果。

## 选择协议

选定运行 `phase2_acceptance_selected_seed42_v1` 含 20 个相同 case-persona 单元、40 条轨迹。B2 来自修复前不受该缺陷影响的运行，B3 来自重复追问修复后的重跑；选择依据在官方评分前固定，逐文件 SHA-256 见机器可读摘要。

## 官方 DLawBench 指标

| 方法 | fact_coverage | inquiry | elicitation | fact_resolution | issue_resolution | resolution | fidelity |
|---|---:|---:|---:|---:|---:|---:|---:|
| B2_static_text_skills | 0.7367 | 0.0000 | 0.3683 | 0.7000 | 0.0833 | 0.3917 | 0.9117 |
| B3_static_executable_skills | 0.8450 | 0.0000 | 0.4225 | 0.7708 | 0.6042 | 0.6875 | 0.9183 |
| B1_prompted_multiturn（同 acceptance cells、无技能） | 0.6617 | 0.0000 | 0.3308 | 0.5867 | 0.4333 | 0.5100 | 0.8514 |

## 过程与安全指标

| 方法 | 轨迹 | 平均步数 | 问题数 | 结构化解析率 | 技能介入 | 重复问题率 | 严重违规 |
|---|---:|---:|---:|---:|---:|---:|---:|
| B2_static_text_skills | 20 | 2.6000 | 32 | 1.0000 | 0 | 0.3125 | 0 |
| B3_static_executable_skills | 20 | 5.3000 | 95 | 1.0000 | 98 | 0.2316 | 0 |

## 验收结论

B3 与同案同 persona 的 B1 无技能比较采用预先声明的主效用 mean(elicitation, resolution, fidelity)：0.676100 vs 0.564067，差值 +0.112033。

状态/动作 schema、冲突保留、10 条三层种子技能、有限 operation 执行器、停止风险门、介入日志及在线泄漏边界均已实现。所有 operation 有单元测试；候选技能还需通过字段白名单和可执行性审计。Phase 2 的结论仅支持进入训练期技能进化，不外推到冻结测试集。

机器可读结果：`reports/artifacts/phase2_summary.json`。
