# LegalSkillGuard Revision 6 进展与验收缺口

截至 2026 年 11 月 20 日，原研究 Goal 仍为 `active`。M1 的 Diversity 正式入口、合同接口拟合和 DEV 复用已接通。M2 已将候选驱动选组接入 OpenExempt 的正式训练更新，并用 ContractNLI 的原 B5 提案验证了另一种选组差异。两项方法各自相对强对照的可靠原生收益仍待验收。 [现行方案](https://github.com/H00RU/LegalSkillGuard/blob/7024de8b589c1fca67c66a7d29d11cda60af4a9c/reports/legal_skill_convergence_20261117/PLAN.md) · [接续协议](https://github.com/H00RU/LegalSkillGuard/blob/7024de8b589c1fca67c66a7d29d11cda60af4a9c/reports/legal_skill_convergence_20261117/continuation_protocol_20261119.json)

## 最新固定 DEV 与接续断点

目前阶段为 `revision6_cni_independent_receipt_release_settled`。连续账本累计 15,180 笔，其中 15,144 笔完成、36 笔历史失败，当前在途 0。 [恢复与交接](../../docs/NEW_CHAT_HANDOFF.md)

第三方取得核对将原文中的合法取得与相应的保密定义或例外绑定。固定 DEV 五臂各改善三份引文，分类各 13/16。全部 272 项累计证据 F1 为四内部臂 54.24%、PARSE 46.23%。同原文规则下，12 份 TRAIN 的合成读器仍未超过直接读器。 [TRAIN 对照和五库累计](paper/tables/REVISION6_CNI_INDEPENDENT_RECEIPT_AND_FIXED_DEV_20261120.json)

OpenExempt 多提案允许逐任务采用分类或估值版本，并用两个同预算原文组筛查。在四次过渡的 16 份前向 TRAIN 上，候选驱动、按时间和按答案分歧均为分类 F1 64.98%、估值 F1 53.73%。相对纯原生拟合，两项平均差 +5.21 个百分点，95% 配对区间 [+1.27, +10.10]。三条筛查策略的预测一致，固定 DEV 沿用。 [组合选组与前向结果](paper/tables/REVISION6_OE_PORTFOLIO_TRAIN_20261120.json)

ContractNLI 去掉示例编号，并逐项定位对外披露和独立取得的许可及限制。合成、固定与直接在同一 12 份 TRAIN 的两道题上分别答对 7/24、15/24、6/24。合成读器仍漏判全部对外披露许可，两个归档读器各 18/24。36 笔新调用已结算，固定 DEV 沿用。 [定向证据实测](paper/tables/REVISION6_CNI_TRANSFER_WITNESSES_TRAIN_20261120.json)

ContractNLI 用相同原文和三个原 TRAIN 范例比较对外披露与从第三方取得。B5–B8 两题合计，合成、固定和直接读法分别为 1/24、3/24、12/24，两条归档读器各 18/24。全部 36 笔新执行正常解码，结构化读数没有给出任何许可或禁止模态。本候选未扩验。 [原生分类、证据与配对差](paper/tables/REVISION6_CNI_DIRECTED_TRANSFER_TRAIN_20261120.json)

MAUD 的两个节选可用于核对负面契约引用的例外编号。原 TRAIN 一份合同的引用排除了疫情前导条件，固定 DEV 一份合同的编号范围包含该条件。五臂固定 DEV 对适用合同均已答对，负面契约正确数各保持 13/16。共复用五笔原响应，无模型新增请求。 [条款与原生结果](paper/tables/REVISION6_MAUD_SELECTIVE_IMPORT_TRAIN_AND_FIXED_DEV_20261120.json)

OpenExempt B4 和 B7 两个过渡纳入同批普通及 PARSE 实测提案。B7 候选驱动选中普通提案新增跨任务冲突的一组，保留进入程序。按时间与原生拟合采纳普通提案，答案分歧与进入风险选组也保留进入程序。八份下一批 TRAIN 上，候选驱动的分类与估值 F1 为 63.54% 和 65.12%，按时间及原生拟合为 56.15% 和 66.85%。各选组用同一筛查规则和每组六笔预算。结果未达到扩大验证的条件，固定 DEV 沿用。 [多提案选组与前向结果](paper/tables/REVISION6_OE_CANDIDATE_GROUP_TRAIN_20261120.json)

用已引用的完整用途限制条款区分独立证据与辅助文字。原 TRAIN 的 72 笔索引读数中，固定和直接各改善一份，合成不变。单题 M1 与同信息匹配对照的用途题证据 F1 分别从 69.32% 到 73.13%、85.71% 到 90.48%。固定 DEV 五臂无触发，新增模型请求 0。 [原生训练和固定 DEV 明细](paper/tables/REVISION6_CNI_PURPOSE_SUPPORT_TRAIN_AND_FIXED_DEV_20261120.json)

M1 在 B5–B8 的七份仅一题待解的合同上进行单题读取。同全文、同原文证明的首轮 14 笔实测中，直接读法出现六处相反标签。七笔补测逐项明确标签含义，保留 M1 和固定字段读数。M1、固定加直接匹配对照、直接单题、归档直接双题的待解题正确数依次为 7/7、7/7、5/7、7/7，全部 14 题的正确类证据 F1 为 78.71%、86.90%、72.62%、83.33%。M1 对匹配对照和归档直接双题的待解题证据 F1 差分别为 −16.39 和 −9.25 个百分点，配对区间均跨零。固定 DEV 沿用。 [首轮诊断](paper/tables/REVISION6_CNI_PROJECTED_READ_TRAIN_20261120.json) · [标签澄清与强对照](paper/tables/REVISION6_CNI_PROJECTED_DIRECT_TRAIN_20261120.json)

M1 用原 B1–B4 无共用原文证明的任务拟合读器，按 B5–B8 的待解任务选一路。后四批 12 份合同中两份可完全由原文作答。M1、同信息固定加直接选型、直接读器分别为 23/24、22/24、23/24，正确类证据 F1 为 79.73%、75.00%、76.81%。两项差的配对区间均跨零。复用 72 笔，新增 0，固定 DEV 沿用。 [待解任务选型](paper/tables/REVISION6_CNI_RESIDUAL_ROUTING_TRAIN_20261120.json)

用可复查的编号和定义补全员工披露引文。固定 DEV 五臂各改善两份、零退化，分类各保持 13/16。四内部臂的员工披露证据 F1 从 61.27% 到 65.15%，PARSE 从 49.36% 到 52.50%。五份单题配对上 M1 与直接均为 5/5，证据 F1 为 67.33% 对 80.00%。收益来自共用核验，新增模型请求 0。 [细分指标与累计结果](paper/tables/REVISION6_CNI_RECIPIENT_EVIDENCE_AND_FIXED_DEV_20261120.json)

ContractNLI 的实际 B4 提案在三组角色证据下触发不同的 M2 采纳决定，候选驱动采纳，按时间与答案分歧保留进入读器。用原 B5 三份 TRAIN 前向验证，四路均答对 5/6。正确类证据 F1 为候选驱动与仅按原生拟合 55.56%，按时间与答案分歧 30.56%，配对 95% 区间 [−25.00, +100.00] 个百分点。复用 27 笔、新增三笔，未触发 DEV 扩验。 [前向实测与控制](paper/tables/REVISION6_CNI_B4_RECIPIENT_SELECTION_TRAIN_20261120.json)

OpenExempt B5 最早组的分类和估值候选原高 18.25 和 22.22 个百分点。同样给两路核验不适用的伊利诺伊引文后，该组差值均归零。候选驱动与按时间均保留进入程序。固定 DEV 四个内部臂分类 F1 为 79.63%→80.74%，估值 74.50%→74.85%。PARSE 分类 78.92%→79.27%，估值保持 72.31%。新增 0，所有臂零退化。 [五库累计与归因结果](paper/tables/REVISION6_ILLINOIS_ELIGIBILITY_AND_FIXED_DEV_20261120.json)

MAUD 核验相邻契约款各自的例外前导及引用关系。原 TRAIN 覆盖 3/24，均与原参考一致。在已有三路读数的 9 份合同上，合成、固定、直接分别由 12/18、11/18、10/18 到 14/18、13/18、12/18。三臂各修正 2 项，共用规则解释本次变化。合成相对两条对照的配对区间下界仍为 0。固定 DEV 覆盖 0/16。复用 27 笔原响应，新增 0。 [原生比较](paper/tables/REVISION6_MAUD_BRANCH_PREAMBLE_TRAIN_20261120.json)

M2 补齐 B2 和 B5 先前未纳入比较的 TRAIN 当批筛选，复用 32 笔实测响应。B2 估值候选的当批 F1 高 25.00 个百分点，收益集中在两路共享的最新组，组内没有通过源约束核验的修正。B5 分类和估值候选分别低 9.19 和 28.82 个百分点。候选驱动和按时间在两批均保留进入程序，未补读下一批。 [同信息筛选和采纳结果](paper/tables/REVISION6_OE_MISSING_FORWARD_FIT_TRAIN_20261120.json)

本轮将明确的非授予结论绑定到权利正文。原 TRAIN 的 24 份合同识别出 5 份，均符合原参考。后四批中，M1 和匹配对照的权利题各从 8/12 到 10/12，归档直接保持 11/12。两任务正确类证据 F1 分别为 76.11%、73.61%、74.03%。新增收益归于共用核验，M1 对两条对照的证据差均未达到扩验标准。固定 DEV 覆盖 1/16，五臂输出均未改变。复用归档，新增请求 0。 [TRAIN 与固定 DEV 对照](paper/tables/REVISION6_CNI_RIGHTS_SCOPE_TRAIN_AND_FIXED_DEV_20261120.json)

M1 在 B1–B4 原 TRAIN 拟合读器路由，在 B5–B8 的 12 份合同前向验证。按合同选择时，M1、同信息匹配对照、归档直接读器各答对 23/24、22/24、23/24，正确类证据 F1 为 71.62%、68.97%、70.69%，复用 72 笔原请求。随后将两项任务各自的读法放进一次读取，新增 17 笔冻结执行器请求，17 项检查通过。三路答对 20/24、20/24、23/24，证据 F1 为 68.61%、66.11%、70.69%。M1 相对匹配对照的证据 F1 差为 +2.50 个百分点，配对区间 [0, +7.50]。三路用途题均为 12/12，两条新路径在权利题均为 8/12，归档直接为 11/12。两项比较均未达到扩验条件，五库固定 DEV 结果沿用。 [按合同选择](paper/tables/REVISION6_CNI_FORWARD_ROUTING_TRAIN_20261120.json) · [单次读取双任务](paper/tables/REVISION6_CNI_MIXED_ROUTING_TRAIN_20261120.json)

M2 的新门槛先在各路 TRAIN 上应用共用规则，再决定是否采纳提案。B6 分类更新的 TRAIN 平均增量从 +0.69 变为 −2.46 个百分点，因而保留原程序。16 份原前向 TRAIN 分类 F1 从 61.78% 到 62.80%，估值 F1 保持 51.65%。两种选组策略仍同判。相对不更新的平均差为 +0.43 个百分点，配对区间 [−1.03, +2.10]。复用 112 笔归档响应，新增 0。 [共用规则后的采纳与前向结果](paper/tables/REVISION6_OE_RESIDUAL_ACQUISITION_TRAIN_20261120.json)

Airline 的巴拿马至美国费率经 288 个规则改写核对，与封存基准逐项一致。固定 DEV 对最后一份适用来源执行了这套规则，五臂总费用正确数各由 15/16 到 16/16。M1 的制作引文回放把合成的正确类证据 F1 从 49.47% 提升至 65.28%，直接对照从 70.96% 到 73.23%，分类数不变。两项改动新增模型请求均为 0。 [线路回放](paper/tables/REVISION6_AIRLINE_PANAMA_AND_FIXED_DEV_20261120.json) · [制作证据链](paper/tables/REVISION6_CNI_COPY_EVIDENCE_CLOSURE_TRAIN_20261120.json)

M1 将副本制作与处置后留存绑定到各自条款。在 11 份 ContractNLI 原 TRAIN 合同上完成 33 笔三路实测。应用同一原文规则后，合成、固定、直接分别答对 12/22、11/22、13/22。共同全量处置核查为三臂各再修正 4 题，无退化，方法间差值不变。合成的正确类证据 F1 为 49.47%，直接为 70.96%。新增规则在固定 DEV 中覆盖 0/16。 [三臂实测](paper/tables/REVISION6_CNI_COPY_LIFECYCLE_TRAIN_20261120.json) · [全量处置回放](paper/tables/REVISION6_CNI_COPY_DISPOSITION_READBACK_TRAIN_20261120.json)

M2 分任务采纳复用 112 笔归档响应。类别核查排除了 B7 两次把非服装物品报成服装的表面一致性。候选驱动和按时间均只采纳 B7 的估值改动。四次过渡合计 16 份原前向 TRAIN，两路的分类和估值 F1 均为 61.78% 和 51.65%。相对只按训练分数选路线，两任务平均差 +3.83 个百分点，配对区间 [+0.89, +7.47]。相对不更新差 −0.08 个百分点，区间包含零。固定 DEV 沿用既有结果，新增请求 0。 [类别核查](paper/tables/REVISION6_OE_ITEM_VALIDATED_ACQUISITION_TRAIN_20261120.json) · [分任务采纳](paper/tables/REVISION6_OE_PORT_ACQUISITION_TRAIN_20261120.json)

M1 条款锚点在 9 份 MAUD 原 TRAIN 的两项契约任务上答对 11/18，固定字段和直接对照为 10/18、9/18。两组配对区间下界均为零。原文回放确认两份 TRAIN 合同的疫情例外只点名普通经营款。三臂用同一规则各修正一题，固定 DEV 覆盖 0/16。实测新增 27 笔，回放复用全部读数。 [MAUD 三臂配对](paper/tables/REVISION6_MAUD_CLAUSE_ANCHORS_TRAIN_20261120.json) · [同信息回放](paper/tables/REVISION6_MAUD_SUBSECTION_READBACK_TRAIN_20261120.json)

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

累计 B8 DEV 已结算。五库各有 16 份原 DEV 母来源。下表为启用两项方法的臂及相应同信息对照所能支持的结论。 [五库累计指标和逐臂结果](paper/tables/REVISION6_CNI_INDEPENDENT_RECEIPT_AND_FIXED_DEV_20261120.json)

| 数据库 | 机制与对照 | 累计原生指标 |
|---|---|---|
| LegalBench Diversity | M1 正式路径已触发。同源字面强对照同样答对全部题。 | 准确 16/16 |
| ContractNLI | M1 合成接口和 M2 候选驱动选组已触发。四个内部臂累计结果持平。 | 内部臂 202/272，证据 F1 54.24%。PARSE 193/272，证据 F1 46.23%。 |
| MAUD | 本轮增益来自共用条款核验。 | 知悉定义 16/16，负面契约 13/16，普通经营 14/16 |
| OpenExempt | M2 B7 候选驱动选组已触发。相同信息下共享筛选与直接筛选同判。最新分类和估值收益来自共用规则。 | 分类 F1 80.74%，估值 F1 74.85% |
| RuleArena Airline | 巴拿马线路收益来自共用费率规则。 | 精确总费用 16/16 |

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
