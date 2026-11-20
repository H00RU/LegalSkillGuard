# LegalSkillGuard Revision 6 进展与验收缺口

截至 2026 年 11 月 20 日，原研究 Goal 仍为 `active`。M1 的 Diversity 正式入口、合同接口拟合和 DEV 复用已接通。M2 已将候选驱动选组接入 OpenExempt 的正式训练更新，并用 ContractNLI 的原 B5 提案验证了另一种选组差异。两项方法各自相对强对照的可靠原生收益仍待验收。 [现行方案](https://github.com/H00RU/LegalSkillGuard/blob/7024de8b589c1fca67c66a7d29d11cda60af4a9c/reports/legal_skill_convergence_20261117/PLAN.md) · [接续协议](https://github.com/H00RU/LegalSkillGuard/blob/7024de8b589c1fca67c66a7d29d11cda60af4a9c/reports/legal_skill_convergence_20261117/continuation_protocol_20261119.json)

**接续优先级。** M1 沿用 Diversity 正式链与同源字面对照，复用 MAUD 的 TRAIN 和固定 DEV 强配对，后续比较由可验证的新条款归属依据触发。M2 复用 OpenExempt B1–B8 的已结算证据，针对有新原文依据且能与同信息强对照区分的采纳路径安排前向配对。最近的累计开发分数按库、按臂保留。原 128 来源八批训练、五库冻结 TEST、消融与曝光记录按原版本归档。 [五库累计 DEV](paper/tables/REVISION6_CNI_NOTICE_COVERAGE_LINKS_AND_FIXED_DEV_20261120.json) · [冻结结果](paper/tables/TEST_B8_NATIVE_TABLES.md)

## 最新 TRAIN、固定 DEV 与接续断点

目前阶段为 `revision6_cni_retention_witnesses_forward_settled`。连续账本累计 15,355 笔，其中 15,318 笔完成、37 笔历史失败，当前在途 0。 [恢复与交接](../../docs/NEW_CHAT_HANDOFF.md)

**最新 M1 留存实验。** 把处分后的保留许可和全量处置禁止分别绑定到各自的引文，穷举确认原消费者 243 个状态保持等价。三份早批原 TRAIN 上复用九笔归档，新增三笔。各路共用原文依据后分类均为 3/3，合成、固定字段、直接读法的正确类证据 F1 分别为 61.11%、57.78%、59.26%。锁定该接口后，在三份预先登记的后批原 TRAIN 新增九笔，同一全文和索引下三路均正确 2/3，证据 F1 分别为 66.67%、27.78%、50.00%。对两个强对照的配对区间下界均为零，相对直接读法的提升集中于 B5 的一份合同。五库固定 DEV 沿用。 [早批锁定](paper/tables/REVISION6_CNI_RETENTION_WITNESSES_FIT_TRAIN_20261120.json) · [同输入后批结果](paper/tables/REVISION6_CNI_RETENTION_WITNESSES_FORWARD_TRAIN_20261120.json) 初次 Schema 失败一笔，正常响应十二笔。

**最新 ContractNLI 通知实验。** 把法定披露例外与通用送达、终止、地址变更和安全事件通知分开。明示通知法务的条款须绑定到信息提供方。新规则覆盖一份原 TRAIN 和五份固定 DEV，六份均与原分类一致。固定 DEV 五臂的通知题均由 12/16 升至 16/16，正确类证据 F1 由 68.75% 升至 93.75%，零退化。ContractNLI 累计四内部臂为 217/272、证据 F1 60.16%，PARSE 为 208/272、53.27%。在这批原 TRAIN 中，23/24 份可由共用原文核验判定，仅 B2 第一份保留未决，B5–B8 无未决样本可供本项 M1 前向配对。其他四库沿用，新增模型请求 0。 [通知证据与五库累计 DEV](paper/tables/REVISION6_CNI_NOTICE_COVERAGE_LINKS_AND_FIXED_DEV_20261120.json)

**最新 M2 双组选取实验。** 在 B4 和 B5 原四读器候选池中，各筛选策略使用两组、八笔相同预算。候选驱动优先覆盖已知领先程序的反证，再保留更多未被排除的备选程序。B4 共 54 对可行组，候选驱动选 B3 第二组和 B4 第二组，逐题程序与六条对照分别不同。复用 35 笔精确后批响应，在 12 份原 TRAIN 的 60 项上，候选驱动为 55/60，六条对照均为 54/60。唯一分类差来自明示向承包商披露的许可。把三条经原文核对的同类许可给每路后，全部为 55/60。候选驱动的正确类证据 F1 为 79.86%，对照为 80.89% 至 82.94%。B5 的候选驱动与直接冲突覆盖、领先程序反证计数逐题配置相同。固定 DEV 公开输入无新增同型许可。新增请求 0，五库累计 DEV 沿用。 [双组选取与同信息配对](paper/tables/REVISION6_CNI_COMPLEMENTARY_ACQUISITION_TRAIN_20261120.json)

**最新 ContractNLI 处置实验。** 核对同一请求下的完整交还与销毁分项，排除有形副本限定和相竞争的留存例外。原 TRAIN 8/24 份有明确全量处置证据，四份为已有规则覆盖，四份由新规则覆盖。八份分类均与参考一致。固定 DEV 一份命中，五臂各修正同一项留存分类和引文，零退化。ContractNLI 累计四内部臂为 213/272、证据 F1 58.69%，PARSE 为 204/272、51.80%。给原 B5 M2 两路同一规则后，候选驱动和按时间的固定 DEV 留存分类各由 5/16、7/16 升到 6/16、8/16。其他四库沿用，新增模型请求 0。 [留存配对和五库累计 DEV](paper/tables/REVISION6_CNI_COMPLETE_DISPOSITION_AND_FIXED_DEV_20261120.json)

**最新 M2 实验。** 合并 B5 普通与 PARSE 的两个实际提案及各自进入程序，验证 60 笔前缀读数。B1 首组的普通提案响应未完整解码，保留归档并对所有策略使用同一 14 组完整前缀和每组四笔预算。候选驱动、两种答案分歧对照和原文分类冲突计数均选 B2 第一组，并锁定相同的逐题程序。后批九份原 TRAIN、七个受选型影响的假设共 63 项，四路逐题一致，均为 56/63、正确类证据 F1 81.64%。按时间和原生拟合均为 56/63、82.17%，按作用域内答案及引文分歧为 57/63、79.01%。44 项由共用原文规则直接确定。复用 24 笔后批读数，新增模型请求 0，五库固定 DEV 沿用。 [B5 选组及后批配对](paper/tables/REVISION6_CNI_B5_CANDIDATE_CONFLICTS_TRAIN_20261120.json)

**最新 ContractNLI 实验。** 两条共用规则分别绑定明示员工许可和已有的唯一许可链。明示许可覆盖原 TRAIN 4/24，四份分类及许可句匹配参考，三份完整引文精确匹配，固定 DEV 未触发。把该规则同样给 B4 联合候选和全部对照，后批五种策略均为 26/27。候选驱动与两种分歧控制仍逐题一致，证据 F1 为 91.85%，按时间与原生拟合为 92.67%。许可链恢复另覆盖原 TRAIN 2/24、固定 DEV 5/16。在固定 DEV 上五臂均修正一项分类、改善两项证据，零退化。ContractNLI 累计四内部臂为 212/272、证据 F1 58.50%，PARSE 为 203/272、51.54%。其他四库沿用。两轮均无新增模型请求。 [TRAIN 归因](paper/tables/REVISION6_CNI_EMPLOYEE_PERMISSION_TRAIN_DEV_20261120.json) · [五库累计 DEV](paper/tables/REVISION6_CNI_EMPLOYEE_WITNESS_PROJECTION_AND_FIXED_DEV_20261120.json)

**最新 M2 实验。** 将普通和 PARSE 两个 B4 提案与各自进入程序合并，按题比较四个实际读器。各筛选策略使用相同的每组四笔读数与共用原文判据。候选驱动与两种按分歧筛选选择了相同组，逐题程序和预测均一致。后批 B6–B8 九份合同、27 项受选型影响的判断上，三路均为 25/27、正确类证据 F1 85.19%，按时间与原生拟合均为 26/27、80.19%。相对原生拟合，分类差 −3.70、证据 F1 差 +4.99 个百分点，95% 配对区间分别为 [−11.11, 0] 和 [−1.28, +13.12]。说明性地去掉一份对照引用 67 段的合同，证据差为 +1.57 个百分点。本轮未建立 M2 的独立收益。复用 79 笔原 TRAIN 读数，新增 1 笔（12,112 tokens），固定 DEV 沿用。 [B4 锁定与后批配对](paper/tables/REVISION6_CNI_B4_CANDIDATE_PORTFOLIO_TRAIN_20261120.json)

**最新 M1 实验。** 锁定在原后批 TRAIN 答对 17/18 的条款关系接口。16 份原固定 DEV 中 13 份有可见疫情标记及两类契约锚点，统一原文核验后合成、固定字段、直接读法分别为 11/26、21/26、20/26。合成相对两个强对照的母来源配对差为 −38.46、−34.62 个百分点，两个区间上界均为 −15.38。 50 个标记中 30 个被排除两类作用域，13 个重复同一家族。复用原去重规则后合成恢复到 14/26，原锚点组及增补锚点组均低于强对照。五库累计 DEV 沿用。 新增 31 笔，复用 8 笔。 [同输入固定 DEV](paper/tables/REVISION6_MAUD_LOCKED_OPERATIVE_FIXED_DEV_20261120.json)

**ContractNLI 存续共用规则。** 把本协议的终止前件与继续生效的义务分开核对。两份原 TRAIN 复现已有见证，另命中三份原固定 DEV，五份均与原分类及义务引文一致。固定 DEV 的正确类引文 F1，四内部臂从 39.58% 升到 43.75%，PARSE 从 35.83% 升到 43.75%，五臂零退化。包含终止前件的完整路径记录也保留；把前件列为另一条基准引文时，一份合同评分下降。 ContractNLI 累计分类为四内部臂 211/272、PARSE 202/272，引文 F1 更新为 57.91% 和 50.99%。 新增模型请求 0。 [已阅 DEV 配对和五库累计](paper/tables/REVISION6_CNI_SURVIVAL_TRIGGER_ROLES_AND_FIXED_DEV_20261120.json)

**M2 单项豁免见证。** 在 B8 第四组，原文核实 PARSE 新增两项联邦适用分类，并核实普通提案补报一笔正确估值、另有一笔超过 B7 已校准的单项上限。加入见证后，候选驱动、按时间、按分歧均采纳分类更新，估值保留进入程序。16 份固定 DEV 上分类／估值 F1 为 72.68%／62.63%，原生拟合为 72.68%／68.40%，两项平均差 −2.88 个百分点，配对区间 [−5.73, −0.52]。 同一条文修正给各路后，四种筛选均保留进入程序。原五臂累计 DEV 逐题输出保持一致。原 B8 TRAIN 六项、固定 DEV 九项可核实主张均匹配原参考，所有权未决的资产保持未决。 复用已结算读数，新增请求 0。 [逐任务数据](paper/tables/REVISION6_OE_B8_ITEM_WITNESSES_TRAIN_DEV_20261120.json)

**此前 M2 同输入比较。** OpenExempt B8 四个筛选策略均保留进入程序。16 份固定 DEV 使用相同的 B8 法域与资产输入，在同一套原文核验下，筛选、原生拟合、原正式采纳三路的分类／估值 F1 分别为 66.47%／62.63%、72.68%／68.40%、73.11%／68.40%。筛选相对原生拟合的两项平均差为 −5.99 个百分点，母来源配对区间 [−13.63, −1.17]。 原生拟合选中 PARSE 分类与普通提案估值，在四份 B8 TRAIN 上平均增加 5.00 个百分点。四组均未检出该组合的新增反证，两项变更都缺少原文证实的修正见证。要求每项变更均有修正见证时，六种同预算双组均拒绝；仅按反证筛选时六种均可采纳该组合。 新增 16 笔，复用 80 笔，原五库累计 DEV 沿用。 [同输入配对结果](paper/tables/REVISION6_OE_B8_SCREENED_FIXED_DEV_20261120.json) · [入库门槛归因](../../experiments/convergence_revision6_oe_b8_gate_attribution.py)

**M1 MAUD 逐锚点实验。** M1 从每条义务的锚点反查直接适用的疫情例外。九份原后批 TRAIN 的 45 个锚点都被模型填入肯定见证，两类契约的 18 项原始答案全为 Yes。应用相同原文核验后，新接口、固定字段、直接读法、前一有效关系接口分别为 13/18、13/18、12/18、17/18。相对直接读法的分类配对区间为 [0, +16.67] 个百分点。新增 9 笔，复用 36 笔，固定 DEV 沿用。 [原生结果](paper/tables/REVISION6_MAUD_ANCHOR_WITNESS_TRAIN_20261120.json)

M2 将否决限制在原文见证对应的条款作用域。复用五组已封存的比较和 12 份不同的后批 TRAIN 合同。限制否决的迁移范围后，B5 口头信息题从 8/9、正确类证据 F1 81.48% 恢复至 9/9、92.59%，与四个强对照持平。B4 两项分类增益均来自同一份超出对应作用域的 B5 合同。PARSE B4 的 B6–B8 回放中分类仍为 7/9，证据 F1 为 24.07%，四个强对照为 26.54%。固定 DEV 沿用，新增请求 0。 后续验证需要不同的条款角色或有新原文依据的实测候选。 [作用域实现](../../legal_skill_guard/paired_interfaces/cni_veto_scope.py) · [按批配对与累计 DEV](paper/tables/REVISION6_CNI_SCOPED_VETO_TRAIN_20261120.json)

M2 在实际 B5 普通提案的同条件比较中识别到口头信息分类退化。候选驱动因此保留进入程序，四个强对照选用提案。后批九份中八份由共用规则确定，唯一待解合同提案答对、进入程序答错。候选驱动 8/9、证据 F1 81.48%，强对照 9/9、92.59%，配对区间 [−33.33, 0] 个百分点。新请求一笔，固定 DEV 沿用。 [拟合与按母来源后批结果](paper/tables/REVISION6_CNI_B5_ASSERTION_SCREEN_TRAIN_20261120.json)

ContractNLI 副本共用规则绑定现存副本的处理及制作禁令的统摄项。固定 DEV 五臂各修正三项，无退化。合成与两强对照在同一共用规则下的后批分类各为 2/2、1/2、1/2，证据 F1 为 100%、50%、50%。两项配对区间下界仍为零，固定 DEV 也无本次纠正的统摄写法。 [原始读数复用与五库累计](paper/tables/REVISION6_CNI_COPY_MENTION_ROLES_AND_FIXED_DEV_20261120.json)

M1 副本接口按动作绑定保护对象和授权。早批三份合成、固定、直接为 2/3、0/3、1/3。锁定合成后，两份 B8 原 TRAIN 为 1/2、0/2、0/2，正确类证据 F1 为 25%、0%、0%，配对区间下界为零。在另一份 B8，七处副本措辞共享同一组引文，六处缺少各自的原文锚点。15 笔正常结算，固定 DEV 沿用。 [按原批次比较和机制结果](paper/tables/REVISION6_CNI_COPY_ACTION_TRAIN_20261120.json)

ContractNLI 七个已结算共用修订已合入同一评估入口，逐题复现此前结果。新增授权作用域核验绑定分项中的复制禁令和上层保密对象，固定 DEV 五臂各修正一题。完整重算四内部臂为 208/272、证据 F1 56.57%，PARSE 为 199/272、49.42%。 [统一回放](paper/tables/REVISION6_CNI_EXECUTABLE_CUMULATIVE_DEV_20261120.json) · [副本授权与五库累计](paper/tables/REVISION6_CNI_COPY_APPROVAL_AND_FIXED_DEV_20261120.json)

OpenExempt 宾州共用条文核验使固定 DEV 四内部臂分类／估值 F1 达 86.03%／83.50%，PARSE 达 85.45%／79.26%，五臂零退化。在原 B4 第四份一条普通候选分类读数无效的情况下，按组合继续使用其他实测读数，恢复两项 PARSE 分类错误证据。16 份下一批 TRAIN 上，候选驱动与按时间、按分歧均为 69.95%／56.90%。 [候选采纳与五库累计](paper/tables/REVISION6_OE_PA_CIVILIAN_ASSETS_AND_FIXED_DEV_20261120.json)

OpenExempt 共用俄勒冈原文核验覆盖四份原 TRAIN 和两份固定 DEV，九个金额均与原参考一致。固定 DEV 估值 F1 四内部臂由 80.36% 升至 80.66%，PARSE 由 76.65% 升至 77.62%，五臂零退化。B2 普通提案与进入程序持平，B6 进入程序维持估值优势。 [配对 TRAIN 和五库累计](paper/tables/REVISION6_OE_OREGON_PROPERTY_AND_FIXED_DEV_20261120.json)

MAUD 将重复义务标记连回相同的可见文本，重放九份原后批 TRAIN。在共用规则下，合成读器保持 17/18。固定字段 13/18，直接读法 12/18。固定 DEV 四份可合并合同上五个正式臂均已答对两项契约题。余五项涉及一份节选外的双义务例外、两处可见作用域与参考分歧以及一处节选无疫情字样。沿用原评分与五库指标，新增请求 0。 [归档读数和原文覆盖](paper/tables/REVISION6_MAUD_EXCERPT_PROVENANCE_20261120.json)

按原文共同确定用途题的分类和引文后，B3 及 B5 的后批五路结果同为 7/9、证据 F1 74.07%。B4 普通提案在原 B6–B8 协议事实题的另外九份合同上也五路同分，7/9、证据 F1 74.07%。此前 B5 的原始结果均保留。 [用途归因](paper/tables/REVISION6_CNI_PURPOSE_PROOF_TRAIN_20261120.json) · [B4 后批复核](paper/tables/REVISION6_CNI_TASK_SCREEN_B4_LATER_TRAIN_20261120.json)

B4 PARSE 第三方披露筛选沿用原决策，在 B6–B8 九份 TRAIN 上补齐 18 笔，全部正常解码。五路分类均 7/9。候选驱动的正确类证据 F1 为 31.62%，四个强对照均为 26.54%，母来源配对区间 [−24.31, +36.18] 个百分点。此前 B5 的分类优势未复现，固定 DEV 沿用。 [第三方披露后批](paper/tables/REVISION6_CNI_TASK_SCREEN_PARSE_LATER_TRAIN_20261120.json)

ContractNLI 按假设筛选在 B4 普通与 PARSE 两个不同提案上各拦下一项更新。原 B5 三份合同上，相对三个同预算选组和完整前缀逐假设原生拟合，候选驱动分别为 39/51 对 38/51 和 40/51 对 39/51。正确类证据 F1 分别持平和 +1.96 个百分点。两次共用三个独立母来源。另两次过渡在各自下批的六份合同、九道采纳相关题上达 7/9 对 6/9，证据 F1 为 53.81% 对 59.26%。新增三笔、32,878 tokens，复用原候选实测与前缀。分类区间下界为零，固定 DEV 沿用。 [普通提案](paper/tables/REVISION6_CNI_TASK_SCREEN_TRAIN_20261120.json) · [PARSE 提案](paper/tables/REVISION6_CNI_TASK_SCREEN_PARSE_TRAIN_20261120.json) · [额外前向比较](paper/tables/REVISION6_CNI_TASK_SCREEN_FORWARD_TRAIN_20261120.json)

OpenExempt 共用原文核验区分择法条款与资产条款。B6 进入程序分类 F1 为 60.16%→63.49%，PARSE 保持 72.01%。PARSE 的两个正差来自亚利桑那和伊利诺伊，后两批原 TRAIN 无相同法域。四种同预算筛选仍保留进入程序。固定 DEV 五臂删除不适用的宾州缝纫机引文，分类和估值均改善，无退化。复用 34 笔原响应。 [B6 法域分解和五库累计](paper/tables/REVISION6_OE_CLAUSE_SCOPE_AND_FIXED_DEV_20261120.json)

OpenExempt 补入 B2、B3、B5、B6 的四个正式测量后未采纳的 PARSE 提案。16 份原 TRAIN 上，各程序使用相同公开输入。B6 的 PARSE 分类比进入程序高 10.81 个百分点，估值低 14.35 个百分点。B6 唯一资产键绑定使 PARSE 分类从 70.97% 到 72.01%，四种原文筛选仍保留进入程序。固定 DEV 五臂各修一份、零退化，四个内部臂分类 F1 由 83.27% 到 83.79%，PARSE 由 82.49% 到 83.01%。本轮去重复用 98 笔，无新增请求。 [同条件候选池](paper/tables/REVISION6_OE_REJECTED_PARSE_TRAIN_20261120.json) · [修订及固定 DEV](paper/tables/REVISION6_OE_EC_IDENTITY_AND_FIXED_DEV_20261120.json)

协议事实披露接口在七份前四批原 TRAIN 比较。合成 1/7，固定字段、直接及留一多数类各 6/7。合成六处误判均为把其他条款当成协议事实的披露限制。21 笔正常解码，拟合保留现行程序，累计固定 DEV 沿用。 [拟合与同输入对照](paper/tables/REVISION6_CNI_AGREEMENT_FACT_TRAIN_20261120.json)

ContractNLI 共用原文核验绑定强制披露触发、通知义务和信息提供方，覆盖原 TRAIN 2/24、固定 DEV 7/16。固定 DEV 五臂各答对 12/16，比原累计规则多 4 项。与同为 12/16 的早期覆盖保护相比，普通教师和 PARSE 的证据 F1 分别从 39.58%、43.75% 提升到 68.75%，零退化。累计五库更新了该项共用规则。 [固定 DEV 与原文覆盖](paper/tables/REVISION6_CNI_NOTICE_ROLES_AND_FIXED_DEV_20261120.json)

ContractNLI B4 PARSE 候选的原文冲突选组筛到四项退化。B5 分类各为 39/51，候选驱动正确类证据 F1 为 50.06%，按时间及分歧为 47.71%，逐假设原生为 49.02%。完整 TRAIN 前缀原生对照保留同一进入程序。B1 选组均采纳候选，两批前向为 66/102，进入程序为 76/102。去重复用 39 笔原响应，新增 0。 [完整同条件结果](paper/tables/REVISION6_CNI_ARCHIVE_GROUP_GUARD_TRAIN_20261120.json)

MAUD 显式读取疫情条件，每类义务存一条见证及未决范围。九份原后批 TRAIN 经共用核验后，稀疏见证、固定字段、直接读法、前一去重联合接口分别答对 13/18、13/18、12/18、17/18。相对前版的四处退化集中在两份只有负面节选含疫情标记的合同。新增 9 笔、复用 36 笔。固定 DEV 对该退化结构覆盖 0/16。 [原生比较与范围归因](paper/tables/REVISION6_MAUD_WITNESS_TRAIN_20261120.json)

MAUD 在 4/16 份原固定 DEV 的负面契约节选恢复了旧规则漏掉的限制清单锚点。三路共用修订后的输入，联合编码、固定字段、直接读法各答对 2/8、6/8、5/8。联合编码在三份合同上将七个标记的两类关系全部排除，三个普通经营问题失分；12 笔新读数正常解码。该编码留在开发比较，累计五库指标沿用。 [同输入结果与标记归因](paper/tables/REVISION6_MAUD_GOVERNOR_DEV_20261120.json)

OpenExempt B8 在四份原 TRAIN 上比较三个进入程序、两个真实提案及其 25 种分类／估值组合。共用住宅豁免核验覆盖 1/4 份 TRAIN，固定 DEV 0/16。每种筛选用相同的双组预算，候选驱动、按时间、按分歧和按进入程序风险均保留 M2 的进入程序。纯原生拟合选中 PARSE 分类与普通提案估值，当批两任务平均 F1 增加 5.00 个百分点。固定 DEV 分数沿用。40 笔归档响应逐笔复用，新增 0。 [B8 候选池与五库累计](paper/tables/REVISION6_OE_B8_PORTFOLIO_TRAIN_AND_FIXED_DEV_20261120.json)

OpenExempt B1 采用同一池中的三个实际程序。共用伊利诺伊州家庭用品核验后，普通提案仅替换估值的两任务原生平均增量由 +4.17 个百分点降至 0，全部已测筛选策略均保留进入程序。固定 DEV 四内部臂分类／估值 F1 为 83.27%／79.13%，PARSE 为 82.49%／75.45%，无退化。复用 46 笔原响应。 [B1 采纳、B2 后批及五库累计](paper/tables/REVISION6_OE_B1_HOUSEHOLD_FIT_TRAIN_AND_FIXED_DEV_20261120.json)

MAUD 两种锚点接口共用重复锚点去重。新接口恢复三项普通经营判断，原始正确数由 8/18 升至 11/18；共用条款核验已覆盖三项，强对照得分沿用。原 TRAIN 中疫情线索仅见于负面节选的三份合同均已进入比较，固定 DEV 无此结构。复用 18 笔原响应。 [解码回放与覆盖](paper/tables/REVISION6_MAUD_ANCHOR_IDEMPOTENCE_TRAIN_20261120.json)

MAUD 新接口将有效疫情条件与具体义务合成局部关系。九份较晚 TRAIN 上，使用相同条款范围核验后，新接口 17/18、固定字段 13/18、直接读器 12/18、旧锚点 14/18。搁置两项原参考与明示单项例外分歧的负面契约标签后，四路分别为 15/16、13/16、12/16、14/16。两条强对照的配对区间下界均为零。新增 9 笔实测，复用 27 笔，固定 DEV 沿用。 [配对结果与原文归因](paper/tables/REVISION6_MAUD_OPERATIVE_EDGES_TRAIN_20261120.json)

OpenExempt 将联邦机动车金额绑定到适用条款，并核算题面威斯康星州的可结转额度。已阅固定 DEV 中，四个内部臂估值 F1 从 76.59% 到 78.61%，PARSE 从 73.30% 到 74.93%，无退化。B2 两程序已报对唯一适用的 TRAIN 金额，候选驱动、按时间及按分歧均保留进入程序。复用 21 笔原响应。 [来源核验与五库累计](paper/tables/REVISION6_OE_MOTOR_VEHICLE_TRAIN_AND_FIXED_DEV_20261120.json)

ContractNLI 外部披露核验把专业顾问定义连回明确的许可条款，并将必要知悉许可与其他第三方的批准要求分开。B3 提案在该题由 4/9 到 6/9，与进入程序同分，证据 F1 为 38.89% 对 43.33%。已阅固定 DEV 五臂各修正一项，无退化；累计 ContractNLI 四内部臂为 203/272，PARSE 为 194/272。复用 20 笔响应，新增 0。 [配对 TRAIN 和五库累计 DEV](paper/tables/REVISION6_CNI_EXTERNAL_RECIPIENTS_TRAIN_AND_FIXED_DEV_20261120.json)

MAUD 原八批的 16 项教师与 PARSE 提案在 24 份 TRAIN 上有 5 项原始正增益。共用 B4 输出恢复和可见条款规则后，3 项正增益及 1 项退化均集中在普通经营题。给予两路一致的既有母合同范围证据后，16 项候选与各自进入程序逐题一致。正式 M2 与普通教师的 MAUD 程序八批逐批相同。新负面契约规则核实 B1 一项列举的疫情例外，固定 DEV 0/16 命中。复用 90 笔实际响应。 [原请求校验与逐批原生结果](paper/tables/REVISION6_MAUD_CANDIDATE_ARCHIVE_TRAIN_20261120.json)

ContractNLI 三份早批合同的具名事件关系补上六个未决分类。三路应用已有共用规则后均为 7/9。合成证据 F1 为 62.96%，两条强对照为 56.30%。新增同源存续引文及请求触发核验后，三路逐项同判，均为 8/9、正确类证据 F1 74.07%。新增三笔冻结读数，固定 DEV 沿用。 [配对实测](paper/tables/REVISION6_CNI_EVENT_RELATION_TRAIN_20261120.json) · [引文归因](paper/tables/REVISION6_CNI_EVENT_RESIDUAL_TRAIN_AND_FIXED_DEV_20261120.json)

ContractNLI 的处分、存续和保留事件接口在三份早批 TRAIN 上分别为合成 3/9、固定 7/9、直接 7/9。九笔实测均正常解码，合成在两份合同上将六个问题的关系留为未决。共用原文核验后为 6/9、7/9、7/9。保留例外的最小引文修订使固定 DEV 的 PARSE 该题证据 F1 从 23.45% 到 29.70%，四个内部臂为 66.00%，分类均沿用。 [三路实测](paper/tables/REVISION6_CNI_EVENT_WITNESS_TRAIN_20261120.json) · [统一引文与五库累计](paper/tables/REVISION6_CNI_EVENT_LINKAGE_AND_FIXED_DEV_20261120.json)

OpenExempt 用各自任务的原文证据归因跨任务冲突。B7 原两条冲突仅一条可归于估值候选，另一条保留未决。B2 和 B3 选组改变，六次采纳决定沿用。16 份前向 TRAIN 上四条配对选择路线均为 66.01% 分类 F1 和 54.54% 估值 F1。复用 168 笔去重的实际响应。 [方向归因与前向原生计分](paper/tables/REVISION6_OE_SIGNED_DIRECTION_TRAIN_20261120.json)

OpenExempt 共用品类核验把固定 DEV 四个内部臂的分类 F1 从 81.44% 提高到 81.88%，估值保持 76.59%。PARSE 分类／估值为 81.80%／73.30%，五臂零退化。原 B7 选组采纳后检查的 16 份前向 TRAIN，引文多重集逐源一致，分类／估值均为 66.01%／54.54%。B7 的俄勒冈家庭用品引文在原 EC 和 EV 参考中均存在，车辆引文在两份参考均缺席。 [品类核验与五库累计](paper/tables/REVISION6_OE_ITEM_CATEGORIES_AND_FIXED_DEV_20261120.json)

OpenExempt B7 同任务组筛查发现普通估值候选新增两处跨任务冲突，改采纳 PARSE 估值。按时间与按答案分歧继续采纳普通估值。16 份前向 TRAIN 分类 F1 各为 64.98%，估值 F1 为 52.34% 对 53.73%。两项平均差 −0.69 个百分点，95% 配对区间 [−1.85, 0]。复用 144 笔原物理响应。 [真实候选与前向结果](paper/tables/REVISION6_OE_COMPETING_PORT_TRAIN_20261120.json)

MAUD 负面契约的引文核验区分了节选外的例外、未引入的前导例外和可见的单项例外。B6 第三份在四路都由 Yes 转为未决，原生分数持平。另两份的原文支持贷款修改或分行关闭的局部例外，原参考均为 No。16 份公开 DEV 无这一修订的适用案例，复用原 TRAIN 70 笔，新增 0。 [引文位置和四路回放](paper/tables/REVISION6_MAUD_NEGATIVE_WITNESS_TRAIN_20261120.json)

MAUD 对早四批四路读数应用相同原文规则后，联合字段 19/20，固定字段 17/20，直接读法 16/20，两处相对双对照的修正由原 TRAIN 母合同支持。后四批锁定三个同结构合同，普通经营联合 3/3、固定 1/3、直接 0/3、旧锚点合成 2/3，四路负面契约均为 0/3。联合相对固定的区间下界为零。新增三笔、复用九笔，固定 DEV 沿用。 [早期归因](paper/tables/REVISION6_MAUD_JOINT_SCOPE_CONTROLS_TRAIN_20261120.json) · [前向实测](paper/tables/REVISION6_MAUD_JOINT_FORWARD_TRAIN_20261120.json)

共用跨条款用途证据覆盖原 TRAIN 3/24，直接、固定、合成分别改善 3、2、1 份，零退化。沿用搁置未勾选选项的归因口径，双读器与两强对照仍各为 23/24，正确类证据 F1 为 84.58% 对 83.19%，差的配对区间 [−4.86, +7.64] 个百分点。固定 DEV 无适用案例。 [用途证据与强对照](paper/tables/REVISION6_CNI_PURPOSE_LINKS_TRAIN_20261120.json)

ContractNLI 双读器多答对的一项权利假设引用了未勾选的单向协议选项，原参考也只引该选项。原生评分保留。搁置该断言的敏感性分析中，M1 和两个强对照均为 23/24，正确类证据 F1 为 80.77% 对 78.19%。固定 DEV 公开输入无该结构。 [原始响应和来源归因](paper/tables/REVISION6_CNI_FORM_ATTRIBUTION_TRAIN_20261120.json)

ContractNLI 在 B5 三份原 TRAIN 合同上验证 B4 候选的 17 项逐假设采纳。七个策略均答对 35/51。候选驱动与同范围原生选择逐项相同，正确类证据 F1 均为 32.35%。按时间或分歧为 29.41%，全部逐假设原生选择为 34.31%，整份提案为 39.54%。复用 30 笔原响应，固定 DEV 沿用。 [采纳范围和原生结果](paper/tables/REVISION6_CNI_SCOPED_ADOPTION_TRAIN_20261120.json)

OpenExempt B2 估值提案原有 +25.00 个百分点的 F1 优势。将亚利桑那家庭用品核验同时给候选和进入程序后，估值差归零，所有选组仍保留进入程序。固定 DEV 四内部臂分类／估值 F1 提升到 81.44%／76.59%，PARSE 到 81.35%／73.01%，各改善一份、零退化。 [B2 归因与固定 DEV](paper/tables/REVISION6_OE_ARIZONA_HOUSEHOLD_AND_FIXED_DEV_20261120.json)

复合用途条款的共用证据规则修复合成读器的两份 TRAIN 合同，固定字段和直接读器也各改善一份。旧后四批双读器证据 F1 回放为 86.53% 对 79.58%，配对区间 [−1.39, +15.28] 个百分点。该比较已用于规则开发。固定 DEV 五臂均无触发，累计五库分数沿用。 [共用用途核验](paper/tables/REVISION6_CNI_COMPOUND_PURPOSE_TRAIN_AND_FIXED_DEV_20261120.json)

ContractNLI 用早四批拟合双读器选择规则，用后四批原 TRAIN 比较相同两读预算的直接加合成与直接加固定字段。M1、匹配对照及单独直接分别答对 24/24、23/24、23/24，正确类证据 F1 为 83.55%、78.19%、78.19%。两项证据差的 95% 配对区间均为 [−4.07, +14.58] 个百分点。共用原文证明后，13 项待解任务仍呈同向差异。此项比较复用 72 笔原请求，新增 0，固定 DEV 沿用。 [双读器前向比较](paper/tables/REVISION6_CNI_EVIDENCE_PAIR_TRAIN_20261120.json)

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

累计 B8 DEV 已结算。五库各有 16 份原 DEV 母来源。下表列出最新累计原生指标，以及各库触发情况与对照结果。 [五库累计指标和逐臂结果](paper/tables/REVISION6_CNI_NOTICE_COVERAGE_LINKS_AND_FIXED_DEV_20261120.json)

| 数据库 | 机制与对照 | 累计原生指标 |
|---|---|---|
| LegalBench Diversity | M1 正式路径已触发。同源字面强对照同样答对全部题。 | 准确 16/16 |
| ContractNLI | M1 合成接口和 M2 候选驱动选组已触发。共用条款核验改善固定 DEV，四个内部臂累计结果持平。 | 内部臂 217/272，证据 F1 60.16%。PARSE 208/272，证据 F1 53.27%。 |
| MAUD | M1 联合字段在三个前向 TRAIN 的普通经营题上各答对，负面契约均未答对。固定 DEV 的增益来自共用条款核验。 | 知悉定义 16/16，负面契约 13/16，普通经营 14/16 |
| OpenExempt | M2 B7 候选驱动选组已触发。共用品类核验后，候选驱动与同预算按时间及按分歧的前向原生预测一致。固定 DEV 纳入共用机动车额度、家庭用品、资产键、条文适用与逐件估值核验。 | 分类 F1 86.03%，估值 F1 83.50% |
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
