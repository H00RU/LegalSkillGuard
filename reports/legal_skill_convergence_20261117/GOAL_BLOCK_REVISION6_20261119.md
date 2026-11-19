# LegalSkillGuard Revision 6 进展与验收缺口

截至 2026 年 11 月 20 日，原研究 Goal 仍为 `active`。M1 的 Diversity 正式入口、合同接口拟合和 DEV 复用已接通。M2 已将候选驱动选组接入 OpenExempt 的正式训练更新，并用 ContractNLI 的原 B5 提案验证了另一种选组差异。两项方法各自相对强对照的可靠原生收益仍待验收。 [现行方案](https://github.com/H00RU/LegalSkillGuard/blob/7024de8b589c1fca67c66a7d29d11cda60af4a9c/reports/legal_skill_convergence_20261117/PLAN.md) · [接续协议](https://github.com/H00RU/LegalSkillGuard/blob/7024de8b589c1fca67c66a7d29d11cda60af4a9c/reports/legal_skill_convergence_20261117/continuation_protocol_20261119.json)

## 五库机制与原生结果

| 数据库 | 机制触发与对照 | 原生结果 |
|---|---|---|
| LegalBench Diversity | 沿用已接入正式 B8 DEV 的 M1。两个启用臂各触发 16 次，同源字面强对照覆盖同一批 16 题。 | M1 与同源字面强对照均为 16/16，平衡准确率均为 100%。 |
| ContractNLI | 员工披露首版选择器在 7 份适用合同均保留固定字段，跨条款版在另一次比较的 5 份适用合同均启用合成接口。用途限制与权利授予使用另外一组固定 DEV 配对。M2 的 B5 回放改变提案采纳决定。 | 员工披露首版选择器和固定字段均为 6/7，强制合成 3/7，共用程序 7/7。跨条款版合成和直接对照均为 5/5，证据 F1 为 52.10% 和 72.00%。用途限制与权利授予的合成和直接对照为 20/32 和 22/32。M2 候选驱动与按时间选组为 149/272 和 148/272。 |
| MAUD | 既有 B8 DEV，本轮无新机制触发。 | 知悉定义 14/16，负面契约 11/16，普通经营 14/16。 |
| OpenExempt | M2 B7 候选驱动和按时间各筛一个组，预算均为两笔实测读数。在旧金额覆盖口径下两种选组作出不同决定。以明示金额区分漏报后，两路均保留进入程序，共享与同信息直接筛选同判。 | 旧口径估值 F1 为 46.13% 和 45.03%，两路分类 F1 均为 70.02%。16 份 DEV 中两份改善、三份退化，估值 F1 差的 95% 区间为 −4.56 至 +8.92 个百分点。 |
| RuleArena Airline | 既有 B8 DEV，本轮无新机制触发。 | 精确总费用 15/16。 |

各比较沿用其已登记的适用范围和原生分母。 [五库正式路径](paper/tables/REVISION6_FORMAL_PATHS_20261119.json) · [首轮强对照](paper/tables/REVISION6_LINKS_AND_ASSERTIONS_20261119.json) · [论文初稿](paper/METHODS_AND_DEVELOPMENT_RESULTS.md)

## 最近实测与接续断点

- **M1 合同接口。** 用途限制与权利授予在 6 份源审 TRAIN 合同中，合成、固定字段和直接读器分别正确 11/12、9/12、7/12。固定 DEV 按统一原文规则修复了合成的两处用途限制漏判。两任务合计分类 20/32 对 22/32，证据 F1 45.02% 对 32.84%，配对差的 95% 区间为 −6.12 至 +31.50 个百分点。状态词改写的 12 笔新 TRAIN 请求中，两路在相同位置各答对 7/12，按正确分类计入证据时两路持平。接续以原 TRAIN 原文能定位的关系极性错误为依据，保留同信息直接臂。 [合同用途配对](paper/tables/REVISION6_USE_LICENSE_AND_ARCHIVE_COVERAGE_20261120.json) · [共同规则与回放](paper/tables/REVISION6_USE_SCOPE_AND_OREGON_TRANSFER_20261120.json) · [状态词实测](paper/tables/REVISION6_STATUS_WORDS_AND_TRANSFER_CAPACITY_20261120.json)
- **M2 OpenExempt 迁移。** B4 俄勒冈候选在一份原 TRAIN 及其两个金额改写中正确给出 6/6 个服装金额，进入程序为 4/6。后续 16 份原 TRAIN 无适用来源，固定 DEV 唯一适用来源的输出未变。B7 联邦金额片段在固定 DEV 的四个适用位置两路都给出相同的唯一金额。另有 56 笔 B2–B8 归档请求，候选在 43 个联邦兜底额和 12 个宾州一般豁免金额位置均无正确正额。 [分法条选择](paper/tables/REVISION6_ROLE_QUERY_AND_SCOPED_AMOUNTS_20261120.json) · [片段覆盖](paper/tables/REVISION6_STATUS_WORDS_AND_TRANSFER_CAPACITY_20261120.json) · [估值归档](paper/tables/REVISION6_USE_LICENSE_AND_ARCHIVE_COVERAGE_20261120.json)
- **M2 ContractNLI 选组。** 同一池含 5 个已源审组、10 笔归档读数。候选驱动选中 B1 的保留义务极性冲突、保留进入读器；按时间选中 B5、采纳提案。两种策略各用两笔读数筛选，选定组内共享、逐例和同信息直接检查同判。排名使用完整响应归档。固定 16 份 DEV 上复用两套读器的 32 笔实测响应，整体分类 149/272 对 148/272，差 +0.37 个百分点，95% 区间 −3.68 至 +5.51。证据 F1 为 25.57% 对 26.46%，保留义务分类 5/16 对 7/16。接续优先寻找有真实提案支持、能在新母来源改变输出的已审范围。 [选组、同信息比较与固定 DEV](paper/tables/REVISION6_RETENTION_GROUP_TRANSFER_20261120.json)

原 128 来源八批训练、五库冻结 TEST、消融和论文初稿均保留。累计账本 14,835 笔，其中完成 14,799、失败 36、在途 0。最近回放新增模型请求 0，44 项定向检查通过。原冻结协议、72 份冻结源码快照、TEST 终态和曝光记录通过核验。后续在原 TRAIN/DEV 上开展有明确依据的最小比较，出现可归因的原生改善后锁定相应版本与验证范围。 [冻结结果](paper/tables/TEST_B8_NATIVE_TABLES.md) · [当前交接](../../docs/NEW_CHAT_HANDOFF.md) · [当前 Goal](../../docs/CURRENT_GOAL.md)
