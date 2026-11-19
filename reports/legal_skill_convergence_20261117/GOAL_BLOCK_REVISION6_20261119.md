# LegalSkillGuard revision 6 进展与验收缺口

2026 年 11 月 19 日。原研究 Goal 仍为 `active`。M1 合同接口的正式学习与复用、M2 候选驱动的选组与筛选均已接通，并在原 TRAIN 与固定 DEV 上完成同条件比较。两项方法仍缺各自相对同信息强对照的可靠原生收益。 [现行方案](https://github.com/H00RU/LegalSkillGuard/blob/7024de8b589c1fca67c66a7d29d11cda60af4a9c/reports/legal_skill_convergence_20261117/PLAN.md) · [接续配置](https://github.com/H00RU/LegalSkillGuard/blob/7024de8b589c1fca67c66a7d29d11cda60af4a9c/reports/legal_skill_convergence_20261117/continuation_protocol_20261119.json)

## 五库机制触发与原生结果

| 数据库 | 机制触发与对照 | 原生结果 |
|---|---|---|
| LegalBench Diversity | 复用已接入正式 B8 DEV 的 M1，两个启用臂各触发 16 次。同源字面强对照覆盖同 16 题。 | M1 与同源字面强对照均为 16/16，平衡准确率均为 100%。 |
| ContractNLI | M1 员工披露的首版选择器在 7 份适用 DEV 合同均保留固定字段。跨条款版复用 6 份已源审 TRAIN 合同的 12 笔读数，在 5 份适用 DEV 合同均选择合成接口。 | 首版选择器、固定字段、强制合成、共用程序分别为 6/7、6/7、3/7、7/7。跨条款版在另一适用范围内与同输入直接对照均为 5/5，证据 F1 分别为 52.10% 和 72.00%。 |
| MAUD | 复用固定 B8 DEV，本轮无新机制触发。 | 知悉定义、负面契约和普通经营三项分别为 14/16、11/16、14/16。 |
| OpenExempt | M2 在 4 个所有权候选组内同选。B7 明示金额编辑的两种选组在同一 3 组中选到不同组，每路使用 2 笔已实测读数。 | 旧覆盖口径下，估值 F1 为 45.03%→46.13%（16 份 DEV，2 份改善、3 份退化，配对 95% 区间 −4.56 至 +8.92 个百分点）。区分明示金额与漏报后，两种选组均保留进入程序，共享筛选与同信息直接核对同判。 |
| RuleArena Airline | 复用固定 B8 DEV，本轮无新机制触发。 | 精确总费用 15/16。 |

表中保留三个比较范围。Diversity、MAUD 和 Airline 使用既有 B8 正式结果。合同结果对应所列披露假设及各自适用范围。OpenExempt 的 45.03% 与 46.13% 取自只切换估值技能的配对实验，分类 F1 两路均为 70.02%。 [五库逐臂结果](paper/tables/REVISION6_FORMAL_PATHS_20261119.json) · [后续验证](paper/tables/REVISION6_LINKS_AND_ASSERTIONS_20261119.json) · [论文初稿](paper/METHODS_AND_DEVELOPMENT_RESULTS.md)

## 独立收益仍待验收

- **M1。** 跨条款接口补回了共用程序漏判的一项许可，同输入直接对照也正确。接口相对直接对照的证据 F1 差为 −19.90 个百分点，母来源配对 95% 区间为 −36.57 至 +0.67。接续从 TRAIN 源审约束引文角色入手，区分支持许可、绑定主体及多余引文，并保留同输入直接对照。 [跨条款配对与区间](paper/tables/REVISION6_LINKS_AND_ASSERTIONS_20261119.json)
- **M2。** B7 原采纳决定来自一项引文漏报。按明示断言，进入程序 3 项可匹配、1 项未观测，提案 4 项可匹配，双方均无显式金额矛盾。按已审法域限制部署旧提案的 3 份 DEV，估值 F1 为 57.59%→54.26%。后续选组以可观测的明示金额差异为依据，漏报可作为独立覆盖目标验证。 [筛选校正与分域诊断](paper/tables/REVISION6_LINKS_AND_ASSERTIONS_20261119.json)

原 128 来源八批训练、五库冻结 TEST、消融、强对照及论文初稿已交付。Revision 6 的两个阶段新增 63 笔冻结执行器请求，教师请求 0。最近一阶段 29 项定向检查通过。连续账本 14,779 笔，14,743 完成、36 失败、在途 0。原冻结协议、TEST 终态、72 份源码快照及曝光记录完整保留。后续验证依赖原 TRAIN/DEV 上的新证据。 [冻结结果](paper/tables/TEST_B8_NATIVE_TABLES.md) · [当前交接](../../docs/NEW_CHAT_HANDOFF.md) · [revision 5 历史阻断](https://github.com/H00RU/LegalSkillGuard/blob/2ee9c49ab8349370b1ac4d257b654a15dbb7c702/reports/legal_skill_convergence_20261117/GOAL_BLOCK_20261119.md)
