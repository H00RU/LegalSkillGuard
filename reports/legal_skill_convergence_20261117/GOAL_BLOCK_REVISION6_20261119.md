# LegalSkillGuard Revision 6 进展与验收缺口

截至 2026 年 11 月 20 日，原研究 Goal 仍为 `active`。M1 的 Diversity 正式入口、合同接口拟合和 DEV 复用已接通。M2 已将候选驱动选组接入 OpenExempt 的正式训练更新，并用 ContractNLI 的原 B5 提案验证了另一种选组差异。两项方法各自相对强对照的可靠原生收益仍待验收。 [现行方案](https://github.com/H00RU/LegalSkillGuard/blob/7024de8b589c1fca67c66a7d29d11cda60af4a9c/reports/legal_skill_convergence_20261117/PLAN.md) · [接续协议](https://github.com/H00RU/LegalSkillGuard/blob/7024de8b589c1fca67c66a7d29d11cda60af4a9c/reports/legal_skill_convergence_20261117/continuation_protocol_20261119.json)

## 最新固定 DEV 与接续断点

目前阶段为 `revision6_oe_forward_acquisition_settled`。连续账本累计 15,007 笔，其中 14,971 笔完成、36 笔失败，当前在途 0。最后一轮新增模型请求 0，92 项检查通过。接续优先核对 MAUD 原 TRAIN 中疫情例外与上位条款的归属，再根据原文证据判断是否值得开展新的同信息比较。 [恢复与交接](../../docs/NEW_CHAT_HANDOFF.md)

OpenExempt 四次逐批选组比较复用 56 笔响应。候选驱动与按时间均在 B7 采纳提案，答案分歧与进入程序风险均保留原程序。统一额度对照下，四次合计 16 份原前向 TRAIN 的估值 F1 分别为 24.79%、24.79%、23.85%、23.85%，候选驱动相对答案分歧的配对区间为 −1.98 至 +4.27 个百分点。固定 DEV 沿用上轮，新增请求 0。 [四次配对选组与原生前向结果](paper/tables/REVISION6_OE_FORWARD_ACQUISITION_TRAIN_20261120.json)

OpenExempt 单项额度比较中，候选驱动、答案分歧和按时间三种策略在同组池下均选 B7-3，各复用两笔估值并采纳同一候选。候选在 B8 唯一同范围高值资产报 980 美元，原参考为 700。使用 B7 共同申报金额校准的共用上限，四个内部臂估值 F1 从 72.82% 到 74.50%，PARSE 从 70.58% 到 72.31%，五臂各改善 3 份、无退化。新增请求 0。 [等预算选组与五库累计指标](paper/tables/REVISION6_OE_JOINT_ITEM_CAP_AND_FIXED_DEV_20261120.json)

用途限制的同信息引文核对复用 72 笔 TRAIN 读数。排除不支持用途限制的已确认辅助引文后，合成、固定分栏、直接的正确类证据 F1 为 70.70%、56.12%、61.94%。合成对固定分栏差 +14.58 个百分点，配对区间为 +4.86 至 +25.99。合成对直接差 +8.76 个百分点，区间包含零，确认组差缩至 +1.15。五臂固定 DEV 原生输出均未改变。 [同信息引文对照与五库既有 DEV](paper/tables/REVISION6_INDEXED_EVIDENCE_CONTROL_AND_FIXED_DEV_20261120.json)

M1 的同条款索引接口已完成原 24 份 ContractNLI TRAIN 的三路实测。首组 11 份的两题合计正确类证据 F1 为合成 71.22%、固定分栏 60.32%、直接 54.94%。锁定接口后，确认组用途限制为 10/13、10/13、11/13，正确类证据 F1 为 64.49%、55.40%、57.84%。确认组得分方向一致，配对区间包含零，且合成分类少于直接读器一项。两个阶段新增 72 笔执行器请求，均正常响应。固定 DEV 沿用原结果。 [首组 TRAIN](paper/tables/REVISION6_INDEXED_EFFECTS_TRAIN_20261120.json) · [确认组 TRAIN](paper/tables/REVISION6_INDEXED_EFFECTS_CONFIRMATION_TRAIN_20261120.json)

OpenExempt 的 B6 提案在两件产权明确的资产上正确加入伊利诺伊通配分类，估值一项为零、一项未报。按基准的逐资产逐法条口径，同信息直接规则在原 TRAIN 核对 14 个金额、固定 DEV 核对 5 个，均与原参考一致。固定 DEV 四个内部臂的估值 F1 由 68.48% 到 72.82%，PARSE 由 66.24% 到 70.58%，五臂各改善 2 份、无退化。正向结果来自共用规则。新增请求 0。 [估值对照与最新五库累计指标](paper/tables/REVISION6_ILLINOIS_PAIR_AMOUNTS_AND_FIXED_DEV_20261120.json)

B5 新增同预算的答案分歧选组。候选驱动与答案分歧挑选不同 TRAIN 合同，但都保留进入读器，固定 DEV 的全部原生预测一致。应用上一版共同规则后，候选驱动和答案分歧在独立开发题上各为 16/16，按时间为 15/16。将出现在受保护数据定义中的「开发」与许可条款分开后，按时间也达到 16/16，固定 B8 五臂各修正一项且无退化。复用 10 笔选组 TRAIN、32 笔固定 DEV 和 2 笔定义适用 TRAIN 原响应，新增请求 0。 [B5 答案分歧对照与最新五库累计结果](paper/tables/REVISION6_CNI_B5_DISAGREEMENT_AND_FIXED_DEV_20261120.json)

ContractNLI 将独立开发与此前知悉分开核验。原 TRAIN 中 7 份无独立开发路径的合同和 1 份明确许可的合同均与原参考一致。五臂固定 DEV 该题各由 11/16 升至 15/16，修正 4 项、退化 0 项。归档 B5 采用同一规则，候选驱动选组为 16/16、按时间选组为 15/16，分类差的配对 95% 区间为 0 至 +18.75 个百分点。答对且证据匹配的 F1 差为 +15.55 个百分点，区间为 −4.74 至 +37.14。新增请求 0。 [独立开发结果](paper/tables/REVISION6_CNI_DEVELOPMENT_AND_FIXED_DEV_20261120.json)

OpenExempt 的 B7 威斯康星自住房候选只获得分类采纳。B8 唯一同范围住房没有分类迁移，候选只报 75,000 美元，原参考为 112,850 美元。B8 局部候选与进入程序的分类与估值 F1 同为 64.17% 和 69.54%。复用 32 笔原 TRAIN 请求，固定 DEV 覆盖 0/16，新增请求 0。 [自住房前向结果](paper/tables/REVISION6_WI_HOMESTEAD_TRANSFER_20261120.json)

MAUD 整节引用核验在 B5 原 TRAIN 找到一份双侧支持。固定 DEV 另有一例共用前导段，可从同一原文连接到两类义务。五臂负面契约各 12/16→13/16，普通经营各为 14/16。各臂适用相同规则。复用原请求，新增 0。 [整节引用](paper/tables/REVISION6_MAUD_SECTION_REFERENCE_AND_FIXED_DEV_20261120.json)

MAUD 的联合范围字段在同一 10 份原 TRAIN 中将合成判定从 10/20 提到 16/20。固定及直接分别为 15/20、13/20，配对区间跨零，尚未达到扩验条件。新增 10 笔、复用 30 笔。账本 14,935 笔、在途 0。 [联合范围配对](paper/tables/REVISION6_MAUD_JOINT_SCOPE_20261120.json)

M1 在 10 份原 TRAIN MAUD 合同上比较完整的疫情例外归属判定。合成、固定、同信息直接作答分别为 10/20、15/20、13/20。五个普通经营漏判均读到了疫情触发，四个读数只连到负面契约。该候选未达到前向扩验条件。新增 30 笔，账本 14,925 笔，在途 0。 [MAUD TRAIN 配对结果](paper/tables/REVISION6_MAUD_COVENANT_FIT_20261120.json)

B5 披露对象选组新增了按答案分歧的同预算对照。两种主动排序在三组原 TRAIN 合同中选中同一份并保留进入程序，按时间选组采纳提案。三路在固定 DEV 各为 22/32，证据 F1 依次为 30.31%、30.31%、40.07%。复用 38 笔原请求，新增 0。 [M2 披露对象选组](paper/tables/REVISION6_RECIPIENT_ACQUISITION_20261120.json)

最新比较覆盖原 B6–B8 中此前未做权利授予配对读取的 8 份 TRAIN 合同。合成、固定及同信息直接读器的分类依次为 0/8、2/8、8/8，证据 F1 依次为 0%、20.83%、75.42%。24 笔冻结执行器读取全部正常结算，连续账本达 14,895 笔，在途 0。该单任务接口没有触发 DEV 扩验。 [权利授予 TRAIN 结果](paper/tables/REVISION6_LICENSE_FORWARD_TRAIN_20261120.json)

累计 B8 DEV 已结算。五库各有 16 份原 DEV 母来源。下表为启用两项方法的臂及相应同信息对照所能支持的结论。 [五库累计指标和逐臂结果](paper/tables/REVISION6_OE_JOINT_ITEM_CAP_AND_FIXED_DEV_20261120.json)

| 数据库 | 机制与对照 | 累计原生指标 |
|---|---|---|
| LegalBench Diversity | M1 正式路径已触发。同源字面强对照同样答对全部题。 | 准确 16/16 |
| ContractNLI | M1 合成接口和 M2 候选驱动选组已触发。四个内部臂累计结果持平。 | 内部臂 202/272，证据 F1 52.98%。PARSE 193/272，证据 F1 45.26%。 |
| MAUD | 本轮增益来自共用条款核验。 | 知悉定义 16/16，负面契约 13/16，普通经营 14/16 |
| OpenExempt | M2 B7 候选驱动选组已触发。相同信息下共享筛选与直接筛选同判。最新估值收益来自共用规则。 | 分类 F1 79.63%，估值 F1 74.50% |
| RuleArena Airline | 累计回放未新增触发证据。 | 精确总费用 15/16 |

此前的 ContractNLI 修订识别保护本协议和限制公开参与谈判事实的条款。协议披露题在四个内部臂各由 4/16 升到 7/16，PARSE 由 10/16 升到 11/16，均无退化。相同原文规则下，原 TRAIN 多数类回退为 13/16，归档 B5 候选驱动和按时间选组为 9/16 和 11/16。独立验收仍需要新证据区分两项方法与各自强对照。 [协议披露明细](paper/tables/REVISION6_CNI_AGREEMENT_DISCLOSURE_AND_FIXED_DEV_20261120.json)

协议披露回放复用 15 笔 TRAIN 和 6 笔 DEV 的原请求，新增模型请求 0，68 项检查通过。已核验原冻结协议、72 份源码快照、TEST 终态与曝光回执。接续时优先推进有原文和对照依据的可归因改进。 [当前交接](../../docs/NEW_CHAT_HANDOFF.md) · [当前 Goal](../../docs/CURRENT_GOAL.md) · [论文初稿](paper/METHODS_AND_DEVELOPMENT_RESULTS.md)

## 较早批次的机制核验与原生结果

| 数据库 | 机制触发与对照 | 原生结果 |
|---|---|---|
| LegalBench Diversity | 沿用已接入正式 B8 DEV 的 M1。两个启用臂各触发 16 次，同源字面强对照覆盖同一批 16 题。 | M1 与同源字面强对照均为 16/16，平衡准确率均为 100%。 |
| ContractNLI | 员工披露首版选择器在 7 份适用合同均保留固定字段，跨条款版在另一次比较的 5 份适用合同均启用合成接口。用途限制与权利授予使用另外一组固定 DEV 配对。M2 的 B5 回放改变提案采纳决定。 | 员工披露首版选择器和固定字段均为 6/7，强制合成 3/7，共用程序 7/7。跨条款版合成和直接对照均为 5/5，证据 F1 为 52.10% 和 72.00%。用途限制与权利授予的合成和直接对照为 20/32 和 22/32。M2 候选驱动与按时间选组为 149/272 和 148/272。 |
| MAUD | 既有 B8 DEV，本轮无新机制触发。 | 知悉定义 14/16，负面契约 11/16，普通经营 14/16。 |
| OpenExempt | M2 B7 候选驱动和按时间各筛一个组，预算均为两笔实测读数。在旧金额覆盖口径下两种选组作出不同决定。以明示金额区分漏报后，两路均保留进入程序，共享与同信息直接筛选同判。 | 旧口径估值 F1 为 46.13% 和 45.03%，两路分类 F1 均为 70.02%。16 份 DEV 中两份改善、三份退化，估值 F1 差的 95% 区间为 −4.56 至 +8.92 个百分点。 |
| RuleArena Airline | 既有 B8 DEV，本轮无新机制触发。 | 精确总费用 15/16。 |

各比较沿用其已登记的适用范围和原生分母。 [五库正式路径](paper/tables/REVISION6_FORMAL_PATHS_20261119.json) · [首轮强对照](paper/tables/REVISION6_LINKS_AND_ASSERTIONS_20261119.json) · [论文初稿](paper/METHODS_AND_DEVELOPMENT_RESULTS.md)

## 较早实测与候选证据

- **M1 合同接口。** 用途限制与权利授予在 6 份源审 TRAIN 合同中，合成、固定字段和直接读器分别正确 11/12、9/12、7/12。固定 DEV 按统一原文规则修复了合成的两处用途限制漏判。两任务合计分类 20/32 对 22/32，证据 F1 45.02% 对 32.84%，配对差的 95% 区间为 −6.12 至 +31.50 个百分点。状态词改写的 12 笔新 TRAIN 请求中，两路在相同位置各答对 7/12，按正确分类计入证据时两路持平。接续以原 TRAIN 原文能定位的关系极性错误为依据，保留同信息直接臂。 [合同用途配对](paper/tables/REVISION6_USE_LICENSE_AND_ARCHIVE_COVERAGE_20261120.json) · [共同规则与回放](paper/tables/REVISION6_USE_SCOPE_AND_OREGON_TRANSFER_20261120.json) · [状态词实测](paper/tables/REVISION6_STATUS_WORDS_AND_TRANSFER_CAPACITY_20261120.json)
- **M2 OpenExempt 迁移。** B4 俄勒冈候选在一份原 TRAIN 及其两个金额改写中正确给出 6/6 个服装金额，进入程序为 4/6。后续 16 份原 TRAIN 无适用来源，固定 DEV 唯一适用来源的输出未变。B7 联邦金额片段在固定 DEV 的四个适用位置两路都给出相同的唯一金额。另有 56 笔 B2–B8 归档请求，候选在 43 个联邦兜底额和 12 个宾州一般豁免金额位置均无正确正额。 [分法条选择](paper/tables/REVISION6_ROLE_QUERY_AND_SCOPED_AMOUNTS_20261120.json) · [片段覆盖](paper/tables/REVISION6_STATUS_WORDS_AND_TRANSFER_CAPACITY_20261120.json) · [估值归档](paper/tables/REVISION6_USE_LICENSE_AND_ARCHIVE_COVERAGE_20261120.json)
- **M2 ContractNLI 选组。** 同一池含 5 个已源审组、10 笔归档读数。候选驱动选中 B1 的保留义务极性冲突、保留进入读器；按时间选中 B5、采纳提案。两种策略各用两笔读数筛选，选定组内共享、逐例和同信息直接检查同判。排名使用完整响应归档。固定 16 份 DEV 上复用两套读器的 32 笔实测响应，整体分类 149/272 对 148/272，差 +0.37 个百分点，95% 区间 −3.68 至 +5.51。证据 F1 为 25.57% 对 26.46%，保留义务分类 5/16 对 7/16。接续优先寻找有真实提案支持、能在新母来源改变输出的已审范围。 [选组、同信息比较与固定 DEV](paper/tables/REVISION6_RETENTION_GROUP_TRANSFER_20261120.json)

原 128 来源八批训练、五库冻结 TEST、消融和论文初稿均保留。 [冻结结果](paper/tables/TEST_B8_NATIVE_TABLES.md)
