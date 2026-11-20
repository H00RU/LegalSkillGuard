# 当前 Goal 恢复与交接

原研究 Goal 仍为 active，当前执行依据为 revision 6，源自 GitHub 主分支提交 `7024de8b589c1fca67c66a7d29d11cda60af4a9c`。M1 与 M2 的正式路径已接通，两项贡献各自的可靠原生收益仍待验收。连续账本 15,400 笔，在途 0。冻结协议、TEST 结果和曝光记录保留。

[主分支当前方案](https://github.com/H00RU/LegalSkillGuard/blob/main/reports/legal_skill_convergence_20261117/PLAN.md) · [主分支接续配置](https://github.com/H00RU/LegalSkillGuard/blob/main/reports/legal_skill_convergence_20261117/continuation_protocol_20261119.json) · [Revision 6 进展与验收缺口](../reports/legal_skill_convergence_20261117/GOAL_BLOCK_REVISION6_20261119.md)

## 最新断点

阶段 `revision6_cni_retention_evidence_scope_settled`，会话 `61166` 正常退出，绑定 `e4c5324bf05750d62ae00baeb69056d549aba3baa89b7ab1be5ade738de88bca`。11 项定向测试通过。已核验原冻结协议、72 份源码快照、TEST 终态、结果与曝光回执。 条款核验（本地 `legal_skill_guard/paired_interfaces/cni_retention_evidence_scope.py`） · 归档回放（本地 `experiments/convergence_revision6_cni_retention_evidence_scope.py`）

共用原文核验在 24 份原 TRAIN 中识别两条退还义务，固定 DEV 16 份无触发。三份后批配对合同上，合成、固定字段、直接读取各答对 2/3。正确类证据 F1 分别为 66.67%、55.56%、66.67%，直接读取由 50.00% 升至与合成持平。第三份合同的处置条款与原参考分类仍有分歧，原参考与评分保留。复用 9 笔归档读数，新增请求 0，五库固定 DEV 指标沿用。 共享规则把退还义务与相邻的持续保密和保密对象例外分开。接续时选不同的 M1 合同关系，或核验同信息下仍有实际差异的 M2 提案。 [原生配对与五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_RETENTION_EVIDENCE_SCOPE_TRAIN_DEV_20261120.json)

## Revision 6 ContractNLI 员工与关联方访问的前一断点

阶段 `revision6_cni_employee_access_scope_settled`，会话 `44829` 正常退出，绑定 `8769a465f5a7e3deb8d696008b25f3a4ac669387784a94a55cbe813c8b47a87a`。核验 3 笔受影响 TRAIN、2 笔固定 DEV 和 B5 重拟合的 60 笔前缀归档响应。新增 0，在途 0。16 项测试通过，原冻结协议、72 份源码快照、TEST 终态、结果与曝光回执已核验。 许可链代码（本地 `legal_skill_guard/paired_interfaces/cni_employee_access_scope.py`） · 归档回放（本地 `experiments/convergence_revision6_cni_employee_access_scope.py`）

B5 第二份的两条许可链分别取接收方前导与员工分项、关联方人员限制。B7 第二份为直接员工共享许可。两份均精确匹配 TRAIN 分类和引文。B4 的 51 对可行组在给相同原文后逐项一致，均为 58/60、正确类证据 F1 92.48%。B5 同信息重拟合七个策略的选组和采纳保持。固定 DEV 另有一份承包商访问，原 TRAIN 无同型且与归档的 M1 同条件五源队列无交集。探索性回放内部四臂员工题各 14/16→15/16，PARSE 仍 14/16，五臂正确类证据 F1 各增 6.25 个百分点。五库累计使用有 TRAIN 支持的规则。后续选择另一个可核验的消费者，或相同原文下有实际剩余配对差异的 M2 提案。 [逐批比较与五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_EMPLOYEE_ACCESS_SCOPE_TRAIN_DEV_20261120.json)

## Revision 6 M2 ContractNLI B4 作用域选组的前一断点

阶段 `revision6_cni_b4_scope_transfer_settled`，会话 `12747` 正常退出，绑定 `9283dd88afb2cc0ee8f15b9faf7aada96b1d2ca62d257b0a62b95cb0ad0b8982`。核验 70 笔不同归档响应，原拟合材料 60 笔及后批 16 笔有 6 笔重叠。新增 0，在途 0。7 项测试通过，原冻结协议、72 份源码、TEST 终态、结果和曝光回执已核验。 选组代码（本地 `legal_skill_guard/paired_interfaces/cni_scope_transfer_selection.py`） · 完整回放（本地 `experiments/convergence_revision6_cni_b4_scope_transfer.py`）

51 对可行组在其未参与筛选的早批合同上均没有类别或正确类引文分变化。相同原文核验下，12 份后批、60 项全部有精确配对。46 对与时间对照逐项一致，另外 5 对只改变 B5 第二份的员工访问证据，分类均为 58/60，正确类证据 F1 为 90.81% 对 91.65%。该差异的两路均只给一处引文，一路引员工访问限制，另一路引相邻用途限制。原参考还包括关联方人员许可与接收方前导。可继续检验两类受领人条件的独立引文，任何新增产出须与完整原文核验对照。B5 早批的探索性外部合同检查在 72 对中也无正增益，59 对持平、10 对少一项分类、3 对损失引文分。B4 四读器和现有作用域的选组已穷尽。 [五库累计与全部配对](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_B4_SCOPE_TRANSFER_TRAIN_20261120.json)

## Revision 6 ContractNLI 权利条款的前一断点

阶段 `revision6_cni_rights_operative_scope_settled`，会话 `6805` 正常退出，绑定 `84463746a23981d9fd43244ad9d07ccda18a3759faeca027d8128445c24fe23a`。核验 45 笔匹配 TRAIN 和 5 笔受影响固定 DEV 原响应，新增 0，在途 0。17 项测试通过，原冻结协议、72 份源码快照、TEST 终态、结果与曝光回执已核验。 条款作用域（本地 `legal_skill_guard/paired_interfaces/cni_rights_operative_scope.py`） · 同条件回放（本地 `experiments/convergence_revision6_cni_rights_operative_scope.py`）

给各路相同的完整原文核验后，12 份后批 TRAIN 的合成和固定字段逐题输出一致，三路均为 12/12。正确类证据 F1 为 90.28%、90.28%、90.00%，合成对直接的配对区间为 [−6.94,+6.39] 个百分点。固定 DEV 的权利题四内部臂各修正三份，PARSE 修正两份，零退化。两份仍未解决的误报涉及设备与资源归属、项目限定借用。保留为共用规则。后续选择存在实际匹配差异的不同 M1 消费者或 M2 真实提案。 [原生配对和五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_RIGHTS_OPERATIVE_SCOPE_TRAIN_DEV_20261120.json)

## Revision 6 OpenExempt 联邦物品角色的前一断点

阶段 `revision6_oe_federal_asset_roles_settled`，会话 `16537` 正常退出，绑定 `cc9df7a08eea1caabf32e91bff5e0700bacb2ef996fe87113a17a510403cbb4b`。核对 B2、B3 各 24 笔及 4 笔受影响固定 DEV 原响应。新增 0，在途 0。8 项测试通过，已核验原冻结协议、72 份源码快照、TEST 终态、结果和曝光回执。 联邦物品角色核验（本地 `legal_skill_guard/paired_interfaces/convergence_oe_federal_asset_roles.py`） · 同条件回放（本地 `experiments/convergence_revision6_oe_federal_asset_roles.py`）

B2 的早批程序及输入在两种夫妻申报上限口径下完全一致。提案删除了喷泉的超额申报，该资产是否属于法条列举类别及应报金额仍未决。加入烫衣板和首饰核验后，四种同预算筛选仍保留进入程序。四份 B2 TRAIN 中，筛选与原生拟合的估值 F1 为 60.71% 和 61.55%。B3 三份有同版本法条，原实测候选池缺少 B2 提案的同条件响应。B3 进入程序复算分类／估值 F1 为 52.56%／65.12%。固定 DEV 五臂两项指标各改善一份、零退化。保留共用修订，后续从不同的 M1 合同消费者或有原文修复见证且确有后批区分的 M2 候选继续。 [五库累计与逐批结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_FEDERAL_ASSET_ROLES_TRAIN_DEV_20261120.json)

下一项 M1 原文线索来自 ContractNLI 权利题。固定 DEV 的联合臂和 PARSE 各有 5 项将未提及判为蕴含。联合臂错误来源中的未归类权利线索分别涉及附于单段的知识产权许可保留、现有知识产权归属、设备与资源权属、项目限定借用与第三方披露权，以及一份没有剩余词法线索的合同。原 TRAIN 的整合条款同时出现在两类标签中，不能凭整合条款分类。后续先在原 TRAIN 建立按法律行为、受权主体和被约束条款的检验，并把保留原权利、段内限制和正文明确不授予分开。先核对现有权利接口与强对照采用的来源，DEV 只用于说明开发动机。 现有权利上下文（本地 `legal_skill_guard/paired_interfaces/cni_rights_context.py`） · 现有权利接口（本地 `legal_skill_guard/paired_interfaces/cni_rights_topology.py`）

## Revision 6 OpenExempt 伊利诺伊州健康辅助器具的前一断点

阶段 `revision6_oe_illinois_health_roles_settled`，回放会话 `38160` 正常退出，绑定 `1561d37eba22aee0e80bf225344a09092971546ec6196a694efd8a39cb5bf81c`。核对 24 笔 B5、24 笔 B6 实测及 4 笔固定 DEV 原响应，新增 0，在途 0。11 项测试通过，原冻结协议、72 份源码快照、TEST 终态、结果与曝光回执已核验。 物品角色核验（本地 `legal_skill_guard/paired_interfaces/convergence_oe_illinois_health_roles.py`） · 同条件回放（本地 `experiments/convergence_revision6_oe_illinois_health_roles.py`）

B5 在给各路旧排除规则后，进入程序估值 F1 为 78.13%。加入新原文见证后，候选驱动、时间、分歧及进入风险均选同两组并采纳同一估值更新，F1 为 80.21%。共用直接核验也将进入程序提升至 80.21%，四路均保留进入程序。B6 四份原 TRAIN 中一份含相同版本法条，原实测候选池缺少 B5 提案的同条件响应。已复算 B6 进入程序，三路共用修订的分类／估值 F1 均为 75.73%／50.33%。固定 DEV 五臂各纠正一份分类，零退化。后续沿用共用投影。B2 联邦物品提案撤回超过上限的申报，该撤回未提供可核验的正确金额。后续优先处理原文能独立确定物品类别、金额的新候选，或不同的 M1 消费者。 [按批结果及五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_ILLINOIS_HEALTH_ROLES_TRAIN_DEV_20261120.json)

## Revision 6 ContractNLI 跨条款引文和 B5 采纳的前一断点

阶段 `revision6_cni_b5_purpose_tail_settled`，引文回放会话 `23412`、后批会话 `71278` 正常退出，后者绑定 `4ebc17e1e565671469d2938b3659a1423bfc611ae4d9b70738a19cef1c5659f7`。复用 B5 拟合 30 笔、B6 配对 6 笔及 B7–B8 原生产读器 12 笔，新增 0，在途 0。15 项检查通过，已核验原冻结协议、72 份源码快照、TEST 终态与曝光回执。 引文压缩（本地 `legal_skill_guard/paired_interfaces/cni_purpose_citation_ranges.py`） · B5 重拟合（本地 `experiments/convergence_revision6_cni_purpose_citation_ranges.py`） · 后批回放（本地 `experiments/convergence_revision6_cni_b5_purpose_tail.py`）

B6 第一份合同的 46 段连续引用压缩至唯一限用途条款。各路使用完整原文路径后，B6 候选驱动 3/3、证据 F1 71.11%，时间和分歧对照各 2/3、66.67%。沿用锁定采纳在六份 B7–B8 后批上分类均为 6/6，证据 F1 为 57.78% 对 74.44%，两条配对区间均为 [−50.00, 0] 个百分点。九份合计候选驱动仍多一项分类，证据 F1 差 −9.63 个百分点，区间 [−33.33, +4.44]。M1 与固定 DEV 沿用累计。该用途采纳分支已完成全部可用后批配对，后续使用有新原文依据的其他真实提案或不同的 M1 消费者。 [选组、后批结果与五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_PURPOSE_RANGE_AND_B5_TRANSFER_20261120.json)

## Revision 6 ContractNLI 限用途全文核验的前一断点

阶段 `revision6_cni_use_purpose_binding_settled`，会话 `11335` 正常退出，绑定 `ac826eea1a16d079f64f3269359035996842fe2d63d622678083142819f6b3a6`。复用 72 笔索引 TRAIN 实测、已核验的 M2 前向和 5 笔受影响的固定 DEV 物理响应，新增 0，在途 0。12 项检查通过，已核验原冻结协议、72 份源码快照、TEST 终态与曝光回执。 条款绑定与全文核验（本地 `legal_skill_guard/paired_interfaces/cni_use_purpose_binding.py`） · 实测回放（本地 `experiments/convergence_revision6_cni_use_purpose_binding.py`）

固定 DEV 共用规则修正每臂两项用途分类和 PARSE 一处引文，无退化。两份误判分别来自披露复制条款与保密注意义务，已看过固定 DEV 错误，保留为开发证据。四内部臂累计 235/272、证据 F1 67.30%，PARSE 223/272、60.34%。M1 前向 12 份中配对路由与最强匹配对照都为 12/12，正确类证据 F1 为 91.67% 和 88.89%，配对区间 [−9.72, +15.28] 个百分点。M2 固定选组复算的三份 B6 用途题，候选驱动 3/3、时间和分歧各 2/3，分类差区间下界为零，正确类证据 F1 反向为 39.20% 对 55.56%。单一分类差在 B6 第三份，另见固定 DEV 相近并列语法的参考歧异。后续若推进该项，优先处理跨独立条款的大段引文，保留同信息强对照。 [逐源回放及五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_GOVERNED_USE_PURPOSE_TRAIN_DEV_20261120.json)

## Revision 6 Airline 真实提案的前一断点

阶段 `revision6_airline_candidate_archive_settled`，会话 `44069` 正常退出，绑定 `eb99eb28e5369fef7775d1526160f58aebb11b85786898c0a52d88e7566b5b70`。复用 58 笔 TRAIN 响应，新增 0，在途 0。11 项检查通过，已核验原冻结协议、72 份源码快照、TEST 终态及曝光回执。 修订执行器（本地 `experiments/convergence_revision6_airline_source_actor.py`） · 八批实际提案（本地 `experiments/convergence_revision6_airline_candidate_archive.py`）

普通教师和 PARSE 各八项提案，逐批与各自进入程序同分，累计各 7/24。普通和 PARSE 分别改变 5 和 3 个原生输出，均未改善正确数。已绑定费率版本的执行器在 TRAIN 24/24，固定 DEV 各臂实际调用 16 次并保持 16/16，适用输入无需模型读数。M2 正式 Airline 程序未产生差异。保留 Airline 共用控制，下一条实测优先选择还有未决来源的合同消费者，或在同信息下能改变采纳并在后批复现的候选。 [分库实测及五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_AIRLINE_CANDIDATE_ARCHIVE_TRAIN_DEV_20261120.json)

## Revision 6 MAUD 例外前导的前一断点

阶段 `revision6_maud_preamble_attachment_settled`，会话 `69383` 正常退出，绑定 `072b68fccd65d1715c53f4de9c159aec80c364355b9814b3303a89e73670a5ba`。复用 36 笔 TRAIN 和 39 笔固定 DEV 同输入读数，新增 0，在途 0。10 项检查通过，已核验原冻结协议、72 份源码快照、TEST 终态及曝光回执。 解码代码（本地 `legal_skill_guard/paired_interfaces/maud_operative_family_projection.py`） · 前导核验（本地 `legal_skill_guard/paired_interfaces/maud_preamble_governance.py`） · 回放入口（本地 `experiments/convergence_revision6_maud_preamble_attachment.py`）

新解码保持 100 个已声明的本地状态。同一族不同锚点额外恢复的唯一肯定输出匹配固定 DEV 标签，但其所指条款被负面义务的编号列表明确排除。给各路同一原文前导及排除证据后，合成 16/26、固定字段和直接均 20/26。原 TRAIN 三路为 17/18、13/18、12/18，维持原比较。消融累计沿用，当前离线修订未进入正式臂。下一步从另一种未决 M1 消费者或有实质后批采纳差异的 M2 候选继续。 [配对与五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_MAUD_PREAMBLE_ATTACHMENT_TRAIN_DEV_20261120.json)

## Revision 6 OpenExempt 俄勒冈服饰的前一断点

阶段 `revision6_oe_oregon_apparel_scope_settled`，会话 `23058` 正常退出，绑定 `07fc81d79e3d48294b6b678831ea6163572d80734f66d19d8827c8509aae3380`。复用 144 笔原 TRAIN 与 2 笔受影响的固定 DEV 响应，新增 0，在途 0。10 项检查通过，原冻结协议、72 份源码快照、TEST 终态、结果和曝光回执已核验。 条文核验（本地 `legal_skill_guard/paired_interfaces/convergence_oe_oregon_apparel_scope.py`） · 前向比较（本地 `experiments/convergence_revision6_oe_oregon_apparel_scope.py`）

新规则将服饰与其他条款的适用性绑定到原文、资产和任务视图。固定 DEV 五臂分类各修正一份、零退化，估值与其他四库保持。三种见证使用方式在共用原文证据后均与同预算时间和分歧强对照逐资产一致。保留共用规则，后续选择能改变同信息比较的 M1 合同关系或 M2 候选路径。 [实测及五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_OREGON_APPAREL_SCOPE_TRAIN_DEV_20261120.json)

## Revision 6 OpenExempt 威斯康星营业资产的前一断点

阶段 `revision6_oe_wi_business_property_settled`，会话 `73354` 已正常退出，绑定 `8ee964d23732181c879442bf65e220bd79eb4b0cee2dca3c5e9dc52e75dbed69`。复用 144 笔原 TRAIN 响应，新增 0，在途 0。11 项检查通过，原冻结协议、72 份源码快照、TEST 终态、结果和曝光回执已核验。 营业资产作用域（本地 `legal_skill_guard/paired_interfaces/convergence_oe_wi_business_property.py`） · 采纳与前向比较（本地 `experiments/convergence_revision6_oe_wi_business_property.py`）

新规则按原文区分营业设备、企业权益、存款账户及自住住宅。六份 TRAIN 和三份固定 DEV 每任务分别核实 56 项和 28 项，全部匹配参考。B7 加入见证后，反证筛选的候选驱动选 PARSE 估值、按时间选普通估值，两者均保留原分类程序。16 份后批归档上，给各路同一原文修正后两种选组逐资产申报相同，分类／估值 F1 为 70.87%／62.71%。在修复见证门槛下先统一原文修正，候选驱动、按时间和按分歧逐资产一致，72.98%／62.51%；相对纯原生拟合的双指标平均差 +2.86 个百分点，母来源配对区间 [+0.07,+6.74]。固定 DEV 五臂均已无相应错误，五库累计沿用。继续要求能区别按时间和分歧强对照的实质后批差异。 [实测及累计结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_WI_BUSINESS_PROPERTY_TRAIN_DEV_20261120.json)

## Revision 6 OpenExempt 只按反证采纳的前一断点

阶段 `revision6_oe_refutation_portfolio_settled`，会话 `8708` 已正常退出，绑定 `87ca36998e42a484c42b711117d07a523c233906f197721bd2a1a109d570b7c3`。复用 144 笔原响应，新增 0，在途 0。10 项检查通过，原冻结协议、72 份源码快照、TEST 终态、结果和曝光回执通过核验。 候选驱动选组实现（本地 `legal_skill_guard/paired_interfaces/convergence_oe_refutation_portfolio.py`） · 实测前向复算（本地 `experiments/convergence_revision6_oe_refutation_portfolio.py`）

原 B3→B4、B4→B5、B6→B7、B7→B8 的实际前向读数用于比较只按反证和要求修复见证的筛选。候选驱动在 B7 选择普通分类及 PARSE 估值，按时间选择普通分类与普通估值。后批两份差异只涉及申报顺序。16 份上各反证筛选和原生拟合的逐资产申报多重集全部相同。候选驱动分类／估值 F1 为 65.77%／59.50%；先前见证门槛保留进入程序，为 71.68%／61.04%。两项平均的配对差 −3.73 个百分点，区间 [−7.65, −0.71]。继续保留先前采纳门槛，固定 DEV 与五库累计沿用。后续候选须在后批有可复用的作用域和实质申报差，或转向能分辨同信息对照的 M1 消费者。 [策略及原生结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_REFUTATION_PORTFOLIO_TRAIN_20261120.json)

## Revision 6 受领类别定义的前一断点

阶段 `revision6_cni_defined_disclosure_audience_settled`，会话 `67277` 已退出，绑定 `68898c9cc5611db9ad0a66c0a6e518b73db1b56f263ab393ad9f245a942138ae`。复用 M1 36 笔、B4 拟合 60 笔、后批 16 笔归档读数，新增 0，在途 0。14 项检查通过，原冻结协议、72 份源码快照、TEST 终态、结果及曝光回执已核验。 受领类别实现（本地 `legal_skill_guard/paired_interfaces/cni_defined_disclosure_audience.py`） · 复算入口（本地 `experiments/convergence_revision6_cni_defined_disclosure_audience.py`）

四份原 TRAIN 明确授权的分类全匹配，三份引文精确匹配。原 B5 第二份的受控关联方许可与一般第三方禁令保留两种合同范围解释。七条已测策略都给出原 benchmark 记错、但与其中一种许可解释相容的答案，当前源文约束不能淘汰任何策略。明确授权的共用证据使后批候选驱动与按时间证据 F1 同升 0.56 个百分点至 91.65%，各为 58/60 且逐题一致。后批合成与直接各为 11/12，正确类证据 F1 为 87.50% 与 85.71%，两条归档整文对照均为 91.67%。固定 DEV 公开文本在规则锁定前可见，唯一命中的合同五臂已正确引用，累计不变。后续从可明确归因并能区分强对照的其他关系或实际提案继续。 [原生实测与五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_DEFINED_DISCLOSURE_AUDIENCE_TRAIN_DEV_20261120.json)

## Revision 6 复制与传递例外的前一断点

阶段 `revision6_cni_copy_exception_scope_settled`，会话 `14338` 已正常退出，绑定 `45ddb92a3eae8c1458291b811471374ee02a95f7c64f2c55b72f2d0c0910ab81`。复用复制动作 15 笔、复制生命周期 33 笔、B4 后批 18 笔原响应，新增 0，在途 0。11 项检查通过，核验原冻结协议、72 份源码快照、TEST 终态、结果和曝光回执。 作用域核验（本地 `legal_skill_guard/paired_interfaces/cni_copy_exception_scope.py`） · 执行入口（本地 `experiments/convergence_revision6_cni_copy_exception_scope.py`）

原 B5 第二份明示目的许可、原 B8 第三份附受领条件的传递例外均与复制题分类及引文匹配。两份后批复制动作比较的合成、固定、直接在共同核验后均为 2/2、正确类证据 F1 100%。11 份生命周期比较为 9/11、9/11、10/11。原 B4 校准范围无新见证，七种策略保持原选组与程序，在 60 项后批比较上各为 58/60。固定 DEV 0/16。B5 第三份仅为自身利益的书面同意条款仍不足以判定一般复制权。另一个原 B4 比较剩余错误是原 B5 第二份允许向受控关联方传递，同时明示一般第三方禁令，须先识别原 TRAIN 中可核实的关系与不同采纳。 [配对、归因和五库结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_COPY_EXCEPTION_SCOPE_TRAIN_DEV_20261120.json)

## Revision 6 限定受领人许可的前一断点

阶段 `revision6_cni_limited_audience_settled`，会话 `92581` 已正常退出，绑定 `d0d49ec113c645a36d50a284bfb9a516c582842ed466ea0929fc9564ddcb72ee`。复用 36 笔 M1、60 笔 B4 拟合及 18 笔前向归档读数，新增 0，在途 0。9 项检查通过。已校验原冻结协议、72 份源码快照、TEST 终态、结果及曝光回执。 许可作用域实现（本地 `legal_skill_guard/paired_interfaces/cni_limited_audience.py`） · 配对入口（本地 `experiments/convergence_revision6_cni_limited_audience.py`）

限定受领人许可在原 TRAIN 4/24 命中，分类与引文均精确匹配。后批合成、固定和直接分别为 10/12、9/12、10/12，正确类证据 F1 为 79.17%、70.83%、77.38%，两条归档整文对照均为 11/12、88.89%。七条 B4 策略的采纳和后批程序不变。候选驱动、按时间逐题一致，57/60、88.59%。固定 DEV 覆盖 0/16。保留为共用原文核验。剩余 B5 第三份的复制条件同时写有书面同意与仅为自身利益的限定，后续如比较须先从原 TRAIN 分开核实动作、受益范围和许可效果。 [分库累计和同信息实测](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_LIMITED_AUDIENCE_TRAIN_DEV_20261120.json)

## Revision 6 ContractNLI 定义分项的前一断点

阶段 `revision6_cni_definition_evidence_paths_settled`，会话 `21588` 已正常退出，绑定 `61beead5de5f4ab53339f57584744d6e1d515dddf4bbd912101f5537d3a18541`。复用 18 笔定义读取和 12 笔原 B8 候选读数；新增 0，在途 0。16 项相关检查通过。核对原冻结协议、72 份源码快照、TEST 终态、结果和曝光回执。 原文核验（本地 `legal_skill_guard/paired_interfaces/cni_definition_evidence_paths.py`） · 执行入口（本地 `experiments/convergence_revision6_cni_definition_evidence_paths.py`）

两个定义列举及一个正文绑定序言通过原 TRAIN 核验。加上分项引文后，合成和直接的同信息全文对照均为 6/6、证据 F1 94.81%，逐题一致，固定字段为 4/6、61.48%。B8 的 PARSE 进入程序在共用原文证据后由 1/3 至 2/3，与提案持平，证据 F1 为 66.67% 对 33.33%。固定 DEV 0/16 命中。OpenExempt 原 B8 的相近服饰及相关资产上未检出候选之间的分类差。后续从不同的未解条款角色或确实分流的候选采纳继续。 [原生结果及五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_DEFINITION_EVIDENCE_PATHS_TRAIN_DEV_20261120.json)

## Revision 6 M2 法条级采纳的前一断点

阶段 `revision6_oe_statute_portfolio_settled`，会话 `59428` 已退出，绑定 `74c327f246e8d8e3d124a31b0273ef240b195dc763cf5f8c25c2324ddc579220`。OpenExempt 分类或估值更新只可替换题面允许的一条法条。两个程序都明确处理的资产可转用新程序的同条款输出。各筛选策略共用候选池、来源核验和每批两个组的预算。按原顺序比较 B3→B4、B4→B5、B6→B7、B7→B8 的实际输出。144 笔原响应均复用，新增 0、在途 0。11 项检查通过，冻结协议、结果和曝光回执已核验。 法条级执行（本地 `legal_skill_guard/paired_interfaces/convergence_oe_statute_portfolio.py`） · 实测入口（本地 `experiments/convergence_revision6_oe_statute_portfolio.py`） · [配对与五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_STATUTE_PORTFOLIO_TRAIN_20261120.json)

116 个按法条重组的候选中，51 个在当批原生拟合为正，只有 B7 俄勒冈州 § 18.345(1)(a) 分类有可核实修正。候选驱动与答案分歧、进入风险采纳同一更新，按时间保留进入程序。原 B8 的 4 份后批无该法条，16 份后批比较中，候选驱动及全部同范围对照均无输出变化，分类／估值 F1 为 71.68%／61.04%。相对全任务原生拟合的双指标平均差 +3.73 个百分点，母来源配对区间 [+0.71,+7.65]，同范围原生拟合与候选驱动逐题一致。没有启动固定 DEV 扩验。后续若再推进法条级采纳，先找到在原来后批重复出现且能区别分歧选组的真实候选，以免把无后批适用范围的拟合差误计成原生收益。

## Revision 6 ContractNLI 协议事实的前一断点

阶段 `revision6_cni_agreement_fact_scope_settled`，会话 `28762` 已退出，绑定 `6038e6ead5eafdc0101365ea643a165b67641773e2e3f9c2f576bf579ac8bca1`。区分协议事实、已提供保密材料的事实、其他义务与拟议交易。新核验命中 7/24 份原 TRAIN 和 7/16 份固定 DEV，分类和引文均符合原参考。19 项检查通过，原冻结协议、72 份源快照、TEST 终态、结果和曝光回执已核验。连续账本 15,400，在途 0，新增 0。 原文规则（本地 `legal_skill_guard/paired_interfaces/cni_agreement_fact_scope.py`） · 同信息回放（本地 `experiments/convergence_revision6_cni_agreement_fact_scope.py`） · [配对及五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_AGREEMENT_FACT_SCOPE_TRAIN_DEV_20261120.json)

协议事实题四个内部臂固定 DEV 各由 7/16 至 13/16，PARSE 由 11/16 至 15/16，零分类退化。ContractNLI 累计四内部臂 233/272、证据 F1 66.56%，PARSE 221/272、59.49%。其余四库沿用。七份早批 M1 对照中，共用核验后合成 5/7、固定字段 6/7、直接作答 6/7。复用 21 笔原读数和 12 笔受影响的固定 DEV 响应。

M2 复用 60 笔拟合和 19 笔后批原读数，原 B4 同一选组机制在加入协议事实核验后从 54 对变为 51 对可行组。候选驱动、按时间及作用域分歧均选 [B4-2, B4-3]，12 份后批原 TRAIN 的协议事实各为 12/12、正确类证据 F1 88.89%。原五题 60 项比较中，候选驱动与按时间均为 57/60、87.48% 且逐题一致。所有所需后批角色都已有精确响应。该修订保留为共用原文核验，后续需要不同的消费者或能实质分流的候选行为。

## Revision 6 ContractNLI 口头信息作用域的前一断点

阶段 `revision6_cni_oral_information_scope_settled`，会话 `88519` 已退出，绑定 `e988b036c5b174411ba1b4dfdd3e8e3387fe1f6a33f9c83d0f50c75755a01002`。原 B8 第三份的信息定义未指定口头形式，任何形式只修饰接收方的传播禁令。复核 12 笔 B8 TRAIN 与 4 笔受影响固定 DEV 的原响应，新增 0、在途 0。17 项检查通过，原冻结协议、72 份源码快照、TEST 终态、汇总和曝光回执已核验。 原文规则（本地 `legal_skill_guard/paired_interfaces/cni_oral_information_scope.py`） · 回放入口（本地 `experiments/convergence_revision6_cni_oral_information_scope.py`） · [配对结果及五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_ORAL_INFORMATION_SCOPE_TRAIN_DEV_20261120.json)

共用原文核验后，B8 口头题四路同为 3/3、正确类证据 F1 88.89%，原 PARSE 提案的单合同分类优势由同信息进入程序全部复现。固定 DEV 两处为指定对象的跨媒介定义和明示讨论分项。四个内部臂各 14/16→15/16，正确类证据 F1 50.86%→59.79%。PARSE 保持 11/16，F1 26.49%→35.42%。ContractNLI 累计四臂 227/272、F1 64.36%，PARSE 217/272、57.29%。修订保留为共用原文核验。其余四库结果沿用。

下一处可核查的分歧是协议事实披露题。四个内部臂固定 DEV 剩余九处错误均输出 Contradiction，原参考为七处 NotMentioned、两处 Entailment。已复核联合臂的 16 笔固定 DEV 原始响应，12 个 Contradiction、2 个 NotMentioned、2 个 Entailment 均与原解码一致。未修正错误的引文包括所有权、修订、返还和存续条款，问题已出现在模型原始作答。下一步在原 TRAIN 的同信息读数中检查这些作用对象是否也被当作协议事实的授权，保留已测的协议事实和直接对照。

## Revision 6 M2 后三批候选审查的前一断点

阶段 `revision6_cni_late_candidate_residuals_settled`，会话 `77628` 已退出，绑定 `2b06860bd440cdf096f6e2b6f55f01773a9d922e8c829fa98b5b29c501b72c41`。B6–B8 九份原 TRAIN 各复用普通、PARSE 的进入程序与提案，逐笔核对 36 个物理响应、同一原文数据和执行器设置。六个原提案都已测量并历史性地保留进入程序。新增 0、在途 0；冻结协议、TEST 终态和曝光回执已核验。 复算入口（本地 `experiments/convergence_revision6_cni_late_candidate_residuals.py`） · [诊断与五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_LATE_CANDIDATE_RESIDUALS_TRAIN_20261120.json)

B6 权利题的普通提案原始证据 F1 44.44%→77.78%，独立引文仅来自第一份的明示非授予正文。共用同一原文证据后，普通进入与提案均为 88.89%，PARSE 两路均为 100%。B7 第三方披露在加入两份可证实的条款后四路均为 3/3、证据 F1 100%。B8 非技术类别的 PARSE 提案为 2/3，普通进入程序为 3/3。口头形式题的 PARSE 提案为 3/3，其余三路均为 2/3，四路正确类证据 F1 都是 55.56%。唯一分类差位于 B8 第三份，提案的未提及判断伴随长引文，尚无覆盖更多合同的可验证选组信号。B8 第二份另有一笔提案长度截断，按已归档原生输出计分。

后续先核对 B8 第三份的信息定义与下游传播限制原文，区分明示口头形式、泛称沟通方式与未提及，然后评估这类证据能否在原 TRAIN 阻止两路共同错误或产生候选分流。保留这次真实提案的分类差和所有对照；固定 DEV 沿用。

## Revision 6 ContractNLI 权利引文补齐的前一断点

阶段 `revision6_cni_rights_citation_links_settled`，会话 `36256` 已退出，绑定 `53762542d7275631d0e43e7f4b45707d01fad5d01a4e2f1820435250b702cc63`。逐笔复核 45 笔原响应，共用引文核验命中四份后批 TRAIN，原参考全部一致。三路分类保持 12/12，正确类证据 F1 为合成 83.33%、固定字段 83.89%、直接 75.83%。相对固定的配对区间跨零，合成候选继续留在 TRAIN 库。固定 DEV 与原 M2 B4 校准源均无命中，新增 0。14 项检查通过，原冻结协议、72 份源快照、TEST 终态与曝光回执已核验。 共用引文规则（本地 `legal_skill_guard/paired_interfaces/cni_rights_citation_links.py`） · 配对执行（本地 `experiments/convergence_revision6_cni_rights_citation_links.py`） · [配对及五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_RIGHTS_CITATION_LINKS_TRAIN_DEV_20261120.json)

## Revision 6 M1 跨条款权利见证的前一断点

阶段 `revision6_cni_rights_topology_settled`。会话 `43769` 正常退出，绑定 `0344bd07ef4dafd6473a946695d2e4d993d39f9e77de379c355d837d538e77e2`，无在途。12 份后批原 TRAIN 加 3 份早批作用对象排除对照。45 笔实际响应和冻结请求逐笔匹配，255,398 tokens，教师 0。合成把每类条款的三个字段压成一个关系，27 个状态等价。11 项检查通过，冻结协议、72 份源快照、TEST 终态和曝光回执已核验。 运行入口（本地 `experiments/convergence_revision6_cni_rights_topology.py`） · [复算结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_LINKED_RIGHTS_TRAIN_20261120.json)

共享原文核验后，合成、固定字段及同输入直接在后批均正确 12/12，正确类证据 F1 分别为 75.00%、75.56%、73.06%。合成相对固定差 −0.56 个百分点，95% 配对区间 [−4.17,+2.50]，相对直接差 +1.94，区间 [−6.94,+10.56]。三路原始读数均错判三份早批排除对照，共用核验后均为 3/3。该候选留在 TRAIN 库快照，未启动固定 DEV。原 B4 M2 的四程序在 15 份原 TRAIN 权利题中全部预测蕴含，三份已核验排除样本不能区分这四种程序的分类，无新增 M2 请求。

后批引文回读发现，B6 第三份合成和固定均漏引独立的既有知识产权归属条款。本轮的专利权关系只覆盖披露所生权利，已有知识产权仍缺对应关系。B8 第三份两路均只引明示不授予，直接还找到所有权条款并多引一个定义。B7 第三份合成和固定都读到了同一对所有权与专利权条款，其他返还、通用处分和权限上下文造成多引。后续先查原 TRAIN 能否同时覆盖既有权利归属、披露新生权利与不相关权利，再决定能否区分新的合成关系及同信息固定字段、整文对照。

## Revision 6 ContractNLI 权利授予条款作用对象的前一断点

阶段 `revision6_cni_rights_context_settled`，会话 60306 已正常退出，绑定 `0caa111525163f59e8c3b4d95231f79a673d3481ebe663f7e2595444606207d9`。11 项检查通过，冻结协议、72 份原冻结源码快照、TEST 终态和曝光回执已校验。复用 72 笔索引配对、17 笔混合读数及 10 笔受影响的正式 TRAIN/DEV 读数，新增 0。固定 DEV 五臂权利题 9/16 到 11/16，零退化。该修订保留为共用原文核验。 条款作用域（本地 `legal_skill_guard/paired_interfaces/cni_rights_context.py`） · 配对执行（本地 `experiments/convergence_revision6_cni_rights_context.py`） · [结果和五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_RIGHTS_CONTEXT_AND_FIXED_DEV_20261120.json)

后批 B5–B8 的 12 份合同上，M1 路由与同预算固定路由均为 8/12，归档整文为 11/12。原请求显示两路共有四项弃答。B6 第一份把实质非授予条款和对象定义读成两个本应同 ID 的锚点。B8 第二份把同一标题当作相反两种效果。既有明示非授予核验已覆盖这两份。B5 第三份把用途限制读成非授予，原参考依据第一方的独占所有权。B7 第三份把返还条款读成非授予，原参考依据供方保留信息所有权与专利独占权。后续按原 TRAIN 核对所有权、使用许可和专利权能否提供可区分的关系样本。保留同信息整文、固定字段与既有明示见证对照。M2 从存在独立选组或采纳差异的候选继续。

原 TRAIN 已查到九份含所有权保留或专利独占词形的合同，九份的权利题参考均为蕴含。其中三份已有明示非授予见证。该词形子集缺少反例，后续如比较新的 M1 关系，须从原 TRAIN 加入其他对象、主体和实际权限的同类候选，检验多条款引用是否增加正确类证据，同时观察全组分类。固定 DEV 沿用本轮已结算成绩。

## Revision 6 M2 ContractNLI 双组选组的前一断点

阶段 `revision6_cni_portfolio_veto_attribution_settled`。作用域回放会话 39594、原文归因会话 97294 均正常退出，后者绑定 `77ca37c55eeaf7c199c0b7ba472247a37f51f5af20db00648c511a091c68ac7f`。复用 60 笔拟合与 22 笔后批实际响应，60 项全部可配对。新增 0，12 项检查通过，原冻结协议、72 份源码快照、TEST 终态和曝光回执已核验。 作用域回放（本地 `experiments/convergence_revision6_cni_portfolio_veto_scope.py`） · 原文归因（本地 `experiments/convergence_revision6_cni_portfolio_veto_attribution.py`）

B4 双组否决只在后批出现同类作用域时生效。候选驱动后批证据 F1 由 83.19% 到 86.93%，分类为 57/60。相对最强对照的证据差来自 B8 第三份合同。各路共享该合同对外知悉例外的总则和相应引文后，时间与原生拟合等强对照逐题复现 M2。固定 DEV 无覆盖，五库累计不需重算。继续寻找不同的未解候选作用域或关系读法。 [配对与五库指标](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_PORTFOLIO_SCOPED_VETO_TRAIN_20261120.json)

## Revision 6 OpenExempt B6 类别和估价资产键的前一断点

阶段 `revision6_oe_b6_valuation_key_settled`。类别核验会话 28651、估价键核验会话 95414 正常退出，后者绑定 `f515b1ccb1678b4d707d5975eb97d3e5ec1b0271a8638c3f92fa339b48630e4f`。复用同一组 24 笔 B6 原读数及 3 笔固定 DEV，新增 0。11 项检查通过，原冻结协议、72 份源码快照、TEST 终态和曝光回执已核验。 类别核验回放（本地 `experiments/convergence_revision6_oe_b6_item_categories.py`） · 估价键回放（本地 `experiments/convergence_revision6_oe_b6_valuation_key.py`）

原 B6 PARSE 分类优势在共用条文排除后由 +8.52 降到 +0.74 个百分点，再统一绑定出处明确的估价后缀后为 −1.34。四种同预算强对照均保留进入程序，纯原生拟合只采纳普通估值。B7–B8 八份原 TRAIN 无对应法域，固定 DEV 五臂的原生指标保持。后续复用此归因，按不同候选族或不同关系接口推进。 [两步验证与五库指标](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_B6_ITEM_CATEGORY_AND_VALUATION_KEYS_20261120.json)

## Revision 6 ContractNLI 标记词作用对象的前一断点

阶段 `revision6_cni_designation_cue_roles_settled`。会话 51785 正常退出，绑定 `b677f3efb37f6e206c51a0a33d1b63b2ec37da4b75a6b406c2abb0354e40e727`。复用原 12 笔 M1、60 笔 M2 拟合及 27 笔 M2 后批读数，并核实累计路径受影响的物理响应。新增请求 0，12 项检查通过。原冻结协议、72 份快照、TEST 终态及曝光回执已核验。 运行入口（本地 `experiments/convergence_revision6_cni_designation_cue_roles.py`） · 作用对象核验（本地 `legal_skill_guard/paired_interfaces/cni_designation_cue_roles.py`）

新规则在原 TRAIN 和固定 DEV 分别消解八份和四份合同的非资格标记线索。固定 DEV 五臂标记题达到 16/16，均改善四份，零退化。M1 定向六份没有新覆盖，M2 原 B4 选组与后批预测保持。保留共用修订，选择其他未解合同关系或能分流的候选证据继续。 [配对与累计结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_DESIGNATION_CUE_ROLES_AND_FIXED_DEV_20261120.json)

## Revision 6 ContractNLI 第三方披露核验的前一断点

阶段 `revision6_cni_disclosure_authorization_settled`。会话 46556 正常退出，绑定 `18a5afa6763dbd9d3e2f2cfa4c3b5409dd3fd6076dafaf9b8dc389c134b36582`。复用 36 笔 M1、60 笔 M2 拟合和 27 笔 M2 原后批精确读数，另核实受修订影响的累计路径。新增请求 0，9 项检查通过。原冻结协议、72 份快照、TEST 终态和曝光回执已核验。 运行入口（本地 `experiments/convergence_revision6_cni_disclosure_authorization.py`） · 原文核验（本地 `legal_skill_guard/paired_interfaces/cni_disclosure_authorization.py`）

第三方披露前置批准及限定分项的共同核验，覆盖原 TRAIN 五份、固定 DEV 两份，分类及引文全匹配。固定 DEV 五臂各修正两项分类、零退化。M1 同信息合成 7/24、固定 17/24，归档整文强对照 20/24。M2 原 B4 选组及程序均保持，后批分类各 57/60，候选驱动证据 F1 低于所有强对照。保留此次修订为共用原文证据，其他四库沿用。具有竞争性外部许可或不明角色定义的合同继续保留未决作用域。 [配对与五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_DISCLOSURE_AUTHORIZATION_AND_FIXED_DEV_20261120.json)

## Revision 6 OpenExempt 威斯康星州消费品的前一断点

阶段 `revision6_oe_wi_consumer_goods_settled`。会话 44989 正常退出，绑定 `ba5a134925942eba23123e74d1133bd644de4d86c859fb2d32b347e11f8dc799`。复用 40 笔 B8 TRAIN、96 笔同输入固定 DEV，另核实累计路径变化所涉 2 笔物理响应。新增 0，9 项检查通过，原冻结协议、72 份源码快照、TEST 终态和曝光回执校验通过。 实测入口（本地 `experiments/convergence_revision6_oe_wi_consumer_goods.py`） · 原文核验（本地 `legal_skill_guard/paired_interfaces/convergence_oe_wi_consumer_goods.py`）

四个筛选策略见到 B8 第四组消费品证据后都选 PARSE 分类和普通估值。共用原文投影后四路均保留进入程序，在固定 DEV 落后纯原生拟合 5.63 个百分点。时间、分歧与候选驱动逐题一致。共用修订使累计 OpenExempt 五臂分类 F1 各提高 0.625 个百分点，其他库沿用。后续 M2 需要有剩余读数差异的新候选证据。继续保留 EC／EV 的原生输入各自允许的产权信息。 [拟合、对照与五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_WI_CONSUMER_GOODS_AND_FIXED_DEV_20261120.json)

## Revision 6 ContractNLI 到期与保留义务的前一断点

阶段 `revision6_cni_survival_term_scope_settled`。会话 96014 正常退出，绑定 `40e9aee1820275b889e7c9e91fada37281bf244cdd56ba951f06c929a34bc22c`。复用 TRAIN、固定 DEV 各 4 笔响应，新增 0，15 项检查通过。原冻结协议、72 份执行快照、TEST 终态及曝光回执已核验。 回放入口（本地 `experiments/convergence_revision6_cni_survival_term_scope.py`） · 原文核验（本地 `legal_skill_guard/paired_interfaces/cni_survival_term_scope.py`）

将签署日起的到期、实际协议终止和资料保留后的保密义务分别取证。三份 TRAIN 和四份固定 DEV 的分类与证据匹配。五臂固定 DEV 各修正一题分类，正确类证据 F1 从 43.75% 到 56.25%，零退化。四内部臂预测一致，修订由各路共用。其余四库沿用上一断点。后续从还需读器解消的合同关系或能改变同信息强对照选组的新见证继续。 [结果与累计指标](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_SURVIVAL_TERM_SCOPE_AND_FIXED_DEV_20261120.json)

## Revision 6 OpenExempt 俄勒冈个人财产的前一断点

阶段 `revision6_oe_oregon_tangible_settled`。离线会话 41356 正常退出，绑定 `72f3f3ba277732b1aefd3325687a314a7597046a98bf219e83dcb7646b12f2b2`。复用 144 笔 TRAIN、1 笔固定 DEV，新增请求 0。14 项测试通过，已核对原冻结协议、72 份源码快照、TEST 终态和曝光回执。 可运行入口（本地 `experiments/convergence_revision6_oe_oregon_tangible.py`） · 原文核验代码（本地 `legal_skill_guard/paired_interfaces/convergence_oe_oregon_tangible.py`）

俄勒冈动产补全只接受明示单人所有权、逐项核验的原文。原 TRAIN 四项分类、五项估值和固定 DEV 一项估值均与参考一致。B4 五条组合筛选证据改变，入库决定维持。16 份后批 TRAIN 上，候选驱动、按时间和按分歧的原生预测逐题一致。OpenExempt 固定 DEV 的 PARSE 估值 F1 从 79.26% 升到 79.56%，四个内部臂持平，其他库沿用。后续保留共用投影，按新原文见证或新的合同关系推进。 [配对与五库累计结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_OREGON_TANGIBLE_TRAIN_DEV_20261120.json)

## Revision 6 M1 分槽留存证据的前一断点

阶段 `revision6_cni_retention_witnesses_forward_settled`。早批会话 61452 与后批会话 67848 已正常退出。合计 12 笔正常响应、57,691 tokens。初次 Schema 请求被 xgrammar 拒绝，账本保留该失败，去重校验移至本地后重新绑定。16 项检查通过，原冻结协议、72 份执行快照、TEST 终态与曝光回执均已核验。 [后批执行入口](../experiments/convergence_revision6_cni_retention_witnesses_forward.py)

把处分后的保留许可和全量处置禁止分别绑定到各自的引文，穷举确认原消费者 243 个状态保持等价。三份早批原 TRAIN 上复用九笔归档，新增三笔。各路共用原文依据后分类均为 3/3，合成、固定字段、直接读法的正确类证据 F1 分别为 61.11%、57.78%、59.26%。锁定该接口后，在三份预先登记的后批原 TRAIN 新增九笔，同一全文和索引下三路均正确 2/3，证据 F1 分别为 66.67%、27.78%、50.00%。对两个强对照的配对区间下界均为零，相对直接读法的提升集中于 B5 的一份合同。五库固定 DEV 沿用。 [早批锁定](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_RETENTION_WITNESSES_FIT_TRAIN_20261120.json) · [同输入后批结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_RETENTION_WITNESSES_FORWARD_TRAIN_20261120.json)

B6 第一份的各路均判为禁止，原参考为未提及。保留逐题输出及引用，当前不扩大该样式到固定 DEV。下一步按其他新原文作用域或实际差异推进。

## Revision 6 ContractNLI 法定披露与通知的前一断点

阶段 `revision6_cni_notice_coverage_links_settled`。离线会话 45843 已正常退出，13 项检查通过。原冻结协议、72 份执行快照、TEST 终态、结果及曝光回执校验通过。 [通知覆盖执行入口](../experiments/convergence_revision6_cni_notice_coverage_links.py)

把法定披露例外与通用送达、终止、地址变更和安全事件通知分开。明示通知法务的条款须绑定到信息提供方。新规则覆盖一份原 TRAIN 和五份固定 DEV，六份均与原分类一致。固定 DEV 五臂的通知题均由 12/16 升至 16/16，正确类证据 F1 由 68.75% 升至 93.75%，零退化。ContractNLI 累计四内部臂为 217/272、证据 F1 60.16%，PARSE 为 208/272、53.27%。在这批原 TRAIN 中，23/24 份可由共用原文核验判定，仅 B2 第一份保留未决，B5–B8 无未决样本可供本项 M1 前向配对。其他四库沿用，新增模型请求 0。 [通知证据与五库累计 DEV](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_NOTICE_COVERAGE_LINKS_AND_FIXED_DEV_20261120.json)

B2 的未决提醒来自董事任职资格与相邻 SEC 申报分项，保留原断言。法定通知在原后批没有适合作为新单任务 M1 对照的未决来源。后续继续寻找独立可证的法律关系，以及能改变同信息强对照采纳决定的真实 M2 提案。

## Revision 6 M2 ContractNLI 双组选取的前一断点

阶段 `revision6_cni_complement_contractor_control_settled`。离线会话 82798 与 44882 已正常退出，13 项检查通过。原冻结协议、72 份执行快照、TEST 终态、结果及曝光回执校验通过。 [双组选取入口](../experiments/convergence_revision6_cni_complementary_acquisition.py) · [原文归因入口](../experiments/convergence_revision6_cni_complement_contractor_control.py)

在 B4 和 B5 原四读器候选池中，各筛选策略使用两组、八笔相同预算。候选驱动优先覆盖已知领先程序的反证，再保留更多未被排除的备选程序。B4 共 54 对可行组，候选驱动选 B3 第二组和 B4 第二组，逐题程序与六条对照分别不同。复用 35 笔精确后批响应，在 12 份原 TRAIN 的 60 项上，候选驱动为 55/60，六条对照均为 54/60。唯一分类差来自明示向承包商披露的许可。把三条经原文核对的同类许可给每路后，全部为 55/60。候选驱动的正确类证据 F1 为 79.86%，对照为 80.89% 至 82.94%。B5 的候选驱动与直接冲突覆盖、领先程序反证计数逐题配置相同。固定 DEV 公开输入无新增同型许可。新增请求 0，五库累计 DEV 沿用。 [双组选取与同信息配对](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_COMPLEMENTARY_ACQUISITION_TRAIN_20261120.json)

保留 B4 双组选取的不同采纳及同信息校正后的评分。B5 沿用两条相同配置的强对照。下一轮优先定位其他可核实的新条款作用域或真实提案差异。

## Revision 6 ContractNLI 完整处置与留存的前一断点

阶段 `revision6_cni_disposition_sequence_settled`。离线会话 66200 已正常退出，14 项检查通过。原冻结协议、72 份执行快照、TEST 终态、结果及曝光回执校验通过。 [完整处置执行入口](../experiments/convergence_revision6_cni_disposition_sequence.py)

核对同一请求下的完整交还与销毁分项，排除有形副本限定和相竞争的留存例外。原 TRAIN 8/24 份有明确全量处置证据，四份为已有规则覆盖，四份由新规则覆盖。八份分类均与参考一致。固定 DEV 一份命中，五臂各修正同一项留存分类和引文，零退化。ContractNLI 累计四内部臂为 213/272、证据 F1 58.69%，PARSE 为 204/272、51.80%。给原 B5 M2 两路同一规则后，候选驱动和按时间的固定 DEV 留存分类各由 5/16、7/16 升到 6/16、8/16。其他四库沿用，新增模型请求 0。 [留存配对和五库累计 DEV](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_COMPLETE_DISPOSITION_AND_FIXED_DEV_20261120.json)

固定 DEV 另一份合同只要求处置有形副本，保密定义同时涵盖口头和电子信息，证据不足以判断所有形式的留存。两项方法继续以新增的可核验条款关系或能改变同信息强对照采纳决定的真实提案为依据。

## Revision 6 M2 ContractNLI B5 合并候选的前一断点

阶段 `revision6_cni_b5_candidate_conflicts_settled`。离线会话 20535 已正常退出，14 项检查通过。锁定七套逐题程序并核对 84 笔原始请求、冻结协议、72 份执行快照及 TEST 曝光回执。 [选组执行入口](../experiments/convergence_revision6_cni_b5_candidate_conflicts.py)

合并 B5 普通与 PARSE 的两个实际提案及各自进入程序，验证 60 笔前缀读数。B1 首组的普通提案响应未完整解码，保留归档并对所有策略使用同一 14 组完整前缀和每组四笔预算。候选驱动、两种答案分歧对照和原文分类冲突计数均选 B2 第一组，并锁定相同的逐题程序。后批九份原 TRAIN、七个受选型影响的假设共 63 项，四路逐题一致，均为 56/63、正确类证据 F1 81.64%。按时间和原生拟合均为 56/63、82.17%，按作用域内答案及引文分歧为 57/63、79.01%。44 项由共用原文规则直接确定。复用 24 笔后批读数，新增模型请求 0，五库固定 DEV 沿用。 [B5 选组及后批配对](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_B5_CANDIDATE_CONFLICTS_TRAIN_20261120.json)

下一次 M2 比较需要能区分同信息直接冲突计数的真实采纳决定。M1 的两个剩余固定 DEV 员工许可问题没有经独立原文证明的同型 TRAIN 合同，B8 第三份仅有更宽的本组织内披露措辞。后续依照可核验的新条款作用域推进。

## Revision 6 ContractNLI 员工许可链的前一断点

阶段 `revision6_cni_employee_witness_projection_settled`。离线会话 32627 正常退出。定向检查 17 项通过。原冻结协议、72 份源码快照、TEST 终态、结果汇总与曝光回执均通过校验。 [许可链执行入口](../experiments/convergence_revision6_cni_employee_witness_projection.py)

两条共用规则分别绑定明示员工许可和已有的唯一许可链。明示许可覆盖原 TRAIN 4/24，四份分类及许可句匹配参考，三份完整引文精确匹配，固定 DEV 未触发。把该规则同样给 B4 联合候选和全部对照，后批五种策略均为 26/27。候选驱动与两种分歧控制仍逐题一致，证据 F1 为 91.85%，按时间与原生拟合为 92.67%。许可链恢复另覆盖原 TRAIN 2/24、固定 DEV 5/16。在固定 DEV 上五臂均修正一项分类、改善两项证据，零退化。ContractNLI 累计四内部臂为 212/272、证据 F1 58.50%，PARSE 为 203/272、51.54%。其他四库沿用。两轮均无新增模型请求。 [TRAIN 归因](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_EMPLOYEE_PERMISSION_TRAIN_DEV_20261120.json) · [五库累计 DEV](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_EMPLOYEE_WITNESS_PROJECTION_AND_FIXED_DEV_20261120.json)

本次提升来自所有臂共用的原文规则。固定 DEV 剩余两个员工题涉及项目参与人和承包商访问，继续前需在原 TRAIN 确认同类主体及可区分的控制。候选驱动与同预算分歧筛选沿用已结算结果，下一次前向比较需要有不同采纳决定的真实提案。

## Revision 6 M2 ContractNLI B4 联合候选的前一断点

阶段 `revision6_cni_b4_portfolio_complete_settled`。会话 49609 已正常退出，最后一笔读数与原公开输入、普通进入程序及冻结执行配置逐项匹配。三份终态及源快照、原冻结协议、72 份原冻结源码快照、TEST 终态与曝光回执均校验。九项检查通过。 [候选筛选实现](../legal_skill_guard/paired_interfaces/cni_candidate_portfolio.py) · [按原批次配对入口](../experiments/convergence_revision6_cni_b4_portfolio_later.py) · [缺失读数执行入口](../experiments/convergence_revision6_cni_b4_portfolio_complete.py)

将普通和 PARSE 两个 B4 提案与各自进入程序合并，按题比较四个实际读器。各筛选策略使用相同的每组四笔读数与共用原文判据。候选驱动与两种按分歧筛选选择了相同组，逐题程序和预测均一致。后批 B6–B8 九份合同、27 项受选型影响的判断上，三路均为 25/27、正确类证据 F1 85.19%，按时间与原生拟合均为 26/27、80.19%。相对原生拟合，分类差 −3.70、证据 F1 差 +4.99 个百分点，95% 配对区间分别为 [−11.11, 0] 和 [−1.28, +13.12]。说明性地去掉一份对照引用 67 段的合同，证据差为 +1.57 个百分点。本轮未建立 M2 的独立收益。复用 79 笔原 TRAIN 读数，新增 1 笔（12,112 tokens），固定 DEV 沿用。 [锁定与配对结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_B4_CANDIDATE_PORTFOLIO_TRAIN_20261120.json)

后续根据新原文见证及真实候选，找出由候选驱动和同预算分歧对照作出不同决策的作用域。M1 继续从可独立核验的合同关系出发，使用锁定的同输入比较。保留原五库冻结结果。

## Revision 6 M1 MAUD 固定 DEV 的前一断点

阶段 `revision6_maud_locked_operative_dev_settled`，会话 91921 已退出，绑定 `18d85b95364d6bb2ed46489a072bfb03d1db74ea00b63bdf89f12df062e94985`。各路收到相同两个节选、同一锚点库存及共用原文核验。复用 8 笔原对照，新增 31 笔、124,953 tokens。 [按源执行入口](../experiments/convergence_revision6_maud_locked_operative_dev.py)

锁定在原后批 TRAIN 答对 17/18 的条款关系接口。16 份原固定 DEV 中 13 份有可见疫情标记及两类契约锚点，统一原文核验后合成、固定字段、直接读法分别为 11/26、21/26、20/26。合成相对两个强对照的母来源配对差为 −38.46、−34.62 个百分点，两个区间上界均为 −15.38。 50 个标记中 30 个被排除两类作用域，13 个重复同一家族。复用原去重规则后合成恢复到 14/26，原锚点组及增补锚点组均低于强对照。五库累计 DEV 沿用。 若在原 16 份上把可用合同全部切到合成接口，普通经营和负面契约各为 6/16 和 8/16，原正式臂为 14/16 和 13/16。12 项检查通过，原冻结协议、72 份源码快照、TEST 终态与曝光回执已校验。后续沿用已有实测，只有得到不同的条款归属依据才继续这一接口族。 [全量与配对结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_MAUD_LOCKED_OPERATIVE_FIXED_DEV_20261120.json) · [读数归因](../experiments/convergence_revision6_maud_locked_dev_readouts.py)

## Revision 6 ContractNLI 存续义务的前一断点

阶段 `revision6_cni_survival_trigger_roles_settled`，会话 53606 已正常退出，绑定 `c63e8652c543f118bf83daac0bed79400c21093d249861991c78b374f6f0f9fe`。通过正式累计 DEV 的本地读取入口复现五臂旧输出，保留本协议名称、明确终止及所保留义务的原文路径。 [条款见证](../legal_skill_guard/paired_interfaces/cni_survival_triggers.py) · [可运行入口](../experiments/convergence_revision6_cni_survival_trigger_roles.py)

把本协议的终止前件与继续生效的义务分开核对。两份原 TRAIN 复现已有见证，另命中三份原固定 DEV，五份均与原分类及义务引文一致。固定 DEV 的正确类引文 F1，四内部臂从 39.58% 升到 43.75%，PARSE 从 35.83% 升到 43.75%，五臂零退化。包含终止前件的完整路径记录也保留；把前件列为另一条基准引文时，一份合同评分下降。 ContractNLI 累计分类为四内部臂 211/272、PARSE 202/272，引文 F1 更新为 57.91% 和 50.99%。 这是已阅 DEV 的共用规则。原 TRAIN 的强对照已使用相同原文见证，M1 独立验收尚缺。复用 4 笔原 TRAIN 及 6 笔原 DEV，新增 0。7 项检查通过，原冻结协议、72 份源码快照、TEST 终态、结果与曝光回执已校验。后续比较沿用该公共输出和原最强控制。 [汇总](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_SURVIVAL_TRIGGER_ROLES_AND_FIXED_DEV_20261120.json)

## Revision 6 M2 OpenExempt 单项豁免见证的前一断点

阶段 `revision6_oe_b8_item_witness_settled`，会话 74761 正常退出，绑定 `7995446736d8e2bfa435e26bbebbb17a84bc7161cb0dbe884fdb19c6a3bb26f8`。以 B7 已锁定的原生估值口径，逐资产核对联邦条文、所有权、物品类型及单项金额。在原文身份绑定、追加见证和所有对照共用修正三种条件下比较。 [来源见证](../legal_skill_guard/paired_interfaces/convergence_oe_item_witness.py) · [配对执行](../experiments/convergence_revision6_oe_b8_item_witness.py)

在 B8 第四组，原文核实 PARSE 新增两项联邦适用分类，并核实普通提案补报一笔正确估值、另有一笔超过 B7 已校准的单项上限。加入见证后，候选驱动、按时间、按分歧均采纳分类更新，估值保留进入程序。16 份固定 DEV 上分类／估值 F1 为 72.68%／62.63%，原生拟合为 72.68%／68.40%，两项平均差 −2.88 个百分点，配对区间 [−5.73, −0.52]。 同一条文修正给各路后，四种筛选均保留进入程序。原五臂累计 DEV 逐题输出保持一致。原 B8 TRAIN 六项、固定 DEV 九项可核实主张均匹配原参考，所有权未决的资产保持未决。 复用 40 笔 TRAIN 和 96 笔固定 DEV 读数，新增 0。9 项检查通过，原冻结协议、72 份快照、TEST 终态和曝光回执校验通过。本条文及 B8 候选已有充分开发证据，接续从有独立分流机会的新见证族或其他实际候选推进。 [TRAIN 与固定 DEV 结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_B8_ITEM_WITNESSES_TRAIN_DEV_20261120.json)

## Revision 6 M2 OpenExempt B8 固定 DEV 的前一断点

阶段 `revision6_oe_b8_screened_dev_settled`，会话 11705 正常退出，绑定 `bfe1287ece2b35c4ff42b74e8f57eaee787b6dc2619574036f254b8524e0a163`。B4 已运行同一进入程序，但原请求缺少 B8 法域提示及估值资产清单。本次补齐 32 笔可比的进入程序读数，其中新增 16 笔，共 110,969 tokens，并复用 16 笔同请求归档。两条 B8 对照的 64 笔归档读数全部复用。按合同配对，13 项检查通过。 [配对执行代码](../experiments/convergence_revision6_oe_b8_screened_dev.py)

OpenExempt B8 四个筛选策略均保留进入程序。16 份固定 DEV 使用相同的 B8 法域与资产输入，在同一套原文核验下，筛选、原生拟合、原正式采纳三路的分类／估值 F1 分别为 66.47%／62.63%、72.68%／68.40%、73.11%／68.40%。筛选相对原生拟合的两项平均差为 −5.99 个百分点，母来源配对区间 [−13.63, −1.17]。 原生拟合选中 PARSE 分类与普通提案估值，在四份 B8 TRAIN 上平均增加 5.00 个百分点。四组均未检出该组合的新增反证，两项变更都缺少原文证实的修正见证。要求每项变更均有修正见证时，六种同预算双组均拒绝；仅按反证筛选时六种均可采纳该组合。 相对原生拟合，筛选在分类上修正 0 份、退化 3 份，在估值上修正 1 份、退化 5 份。原五库累计 DEV 沿用，原冻结协议、72 份源码快照、TEST 终态与曝光已校验。后续需要有独立原文支持的新见证或实测候选，使候选驱动和同预算对照产生可检验的分流。 [结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_B8_SCREENED_FIXED_DEV_20261120.json) · [TRAIN 入库门槛归因](../experiments/convergence_revision6_oe_b8_gate_attribution.py)

## Revision 6 M1 MAUD 逐锚点见证的前一断点

阶段 `revision6_maud_anchor_witness_train_settled`，会话 2520 已正常退出，绑定 `c6447b0d114b9aa83cdd2e1857f61a7cc88d7b8194893a6a0733509fa5edbca4`。逐锚点版区分肯定见证、排除和未决。与原消费者穷举核验 2,916 个状态及覆盖组合。 [读器和冻结比较](../experiments/convergence_revision6_maud_anchor_witness_train.py)

M1 从每条义务的锚点反查直接适用的疫情例外。九份原后批 TRAIN 的 45 个锚点都被模型填入肯定见证，两类契约的 18 项原始答案全为 Yes。应用相同原文核验后，新接口、固定字段、直接读法、前一有效关系接口分别为 13/18、13/18、12/18、17/18。相对直接读法的分类配对区间为 [0, +16.67] 个百分点。新增 9 笔，复用 36 笔，固定 DEV 沿用。 四项相对前版的退化分布在两份合同，均涉及两类义务。没有传输错误。新请求共 40,476 tokens，6 项检查通过。在途 0。原冻结协议、72 份源码快照、TEST 终态、结果与曝光回执已经过哈希校验。保留原前版关系和本次实测，下一步从不同原文关系或有新证据的 M2 提案推进。 [原生结果及逐项差异](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_MAUD_ANCHOR_WITNESS_TRAIN_20261120.json)

## Revision 6 M2 ContractNLI 原条款作用域否决的前一断点

阶段 `revision6_cni_scoped_veto_settled`，绑定 `c712a04cd77638589f410821351fc276e6bcae68733e3ae17a5d47b256cfb957`，在途 0。三种否决分别绑定谈判事实保密、代表披露许可与口头信息持续受约束的已见证条款。后批原文命中同一条款作用域则沿用候选驱动的否决，其他情况沿用完整前缀原生拟合选型。 [作用域实现](../legal_skill_guard/paired_interfaces/cni_veto_scope.py)

复用五组已封存的比较和 12 份不同的后批 TRAIN 合同。限制否决的迁移范围后，B5 口头信息题从 8/9、正确类证据 F1 81.48% 恢复至 9/9、92.59%，与四个强对照持平。B4 两项分类增益均来自同一份超出对应作用域的 B5 合同。PARSE B4 的 B6–B8 回放中分类仍为 7/9，证据 F1 为 24.07%，四个强对照为 26.54%。固定 DEV 沿用，新增请求 0。 PARSE B4 后批证据差值的配对区间为 [−22.22, +14.81] 个百分点。三种作用域在固定 DEV 公开文本中分别命中 1/16、6/16、0/16。9 项检查通过。已校验原冻结协议、72 份源码快照、TEST 终态和曝光回执。沿用固定 DEV 与已封存响应，后续从不同条款角色或有新来源证据的实测提案推进。 [比较结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_SCOPED_VETO_TRAIN_20261120.json)

## Revision 6 M2 B5 分类冲突筛选的前一断点

阶段 `revision6_cni_b5_assertion_screen_settled`，会话 72643 已结束，绑定 `afb9c32193191b57573cc3a908bf433353ff840f653f8f0cf701176599193bb2`。复用 B5 早先被整组拒绝的普通提案与进入程序，共 30 笔 B1–B5 原请求。共用原文核验后，口头信息题进入程序 10/15、提案 12/15。B4 第一份明确约束口头信息，进入程序分类正确但引文不全，提案答未提及。分开分类冲突与引文缺失后，候选驱动选中该组并否决口头信息更新。按时间、按分歧、按适用题分歧及完整前缀原生拟合均采纳。仅按引文见证选组仍和对照同判。 [原始提案、组池与结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_B5_ASSERTION_SCREEN_TRAIN_20261120.json)

后批九份中八份由共用规则确定。B8 第三份没有同一口头信息条款，精确归档的进入程序答蕴含，实测提案答未提及并符合参考。候选驱动为 8/9、正确类证据 F1 81.48%，四强对照为 9/9、92.59%，配对区间 [−33.33, 0] 个百分点。新增一笔，11,948 tokens，八项检查通过。固定 DEV 沿用。该反例只能证实原组的错误，不能把否决迁移到未覆盖的口头信息作用域。后续保留已结算响应，只有不同的来源范围或真实提案才继续验证。原冻结协议、72 份快照、TEST 终态与曝光均通过核对。 [评估代码](../experiments/convergence_revision6_cni_b5_assertion_screen.py)

## Revision 6 ContractNLI 副本原文角色的前一断点

阶段 `revision6_cni_copy_mention_roles_settled`，绑定 `8db34f32349f3a718d6df4ebf3665ba5804af919c41f8e7bef96941bbd9cadfe`。同一条文规则识别原文的定义、行政送达、现存副本及真实制作，并恢复编号条款的统摄项。原 TRAIN 两份、固定 DEV 三份可由此判为未提及，均符合原参考。复用 15 笔配对 TRAIN、6 笔固定 DEV 原请求，新增 0。14 项检查通过。 [配对结果与五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_COPY_MENTION_ROLES_AND_FIXED_DEV_20261120.json)

共享角色核验后，早批合成、固定、直接各为 3/3、1/3、2/3，后批为 2/2、1/2、1/2。后批正确类证据 F1 为 100%、50%、50%，两项相对强对照的配对区间下界仍为零。产出差异的两种统摄写法在固定 DEV 均未命中。固定 DEV 五臂用共用规则各修正三题且零退化，ContractNLI 全量运行四内部臂 211/272、证据 F1 57.67%，PARSE 202/272、50.52%。接续沿用新共用规则和原读数，从不同作用域或候选更新推进独立验证。 [可运行重放](../experiments/convergence_revision6_cni_copy_mention_roles.py)

## Revision 6 M1 副本动作配对的前一断点

阶段 `revision6_cni_copy_action_train_settled`，会话 15518 已结束，绑定 `fff93bc366dd1ed1681cc83100ec98aa7583f824448143c0623947beae56435b`。按每处副本措辞将动作、保护对象与当前授权合成局部关系，60 个完整及未决状态通过等价核验。原 TRAIN 的五份未决合同均纳入。同一公开输入先完成早批九笔，合成、固定、直接分类为 2/3、0/3、1/3。依早批结果锁定合成，再完成 B8 六笔，后批分类为 1/2、0/2、0/2，正确类证据 F1 为 25%、0%、0%。相对两强对照的分类配对区间均为 [0, +100] 个百分点。固定 DEV 公开结构覆盖 9/16，未触发扩验。15 笔都正常解码，共 134,238 tokens，复用 9 笔历史请求，12 项检查通过。 [前向实验与五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_COPY_ACTION_TRAIN_20261120.json)

B8 第二份的合成把七处副本措辞统一引到同一组句子，六处因无各自锚点被拒，余下一处落在定义。B8 第三份分类正确，但附带了现存副本返还条款，缺少实际统摄项。保留原读数、参考和两批结果。若继续该结构，下一条可检验改动是给各路同样的制作、现存副本和统摄证据，确认读器能否据此修复上述错误。原冻结协议、72 份快照、TEST 终态、原结果和曝光回执通过校验。 [接口](../legal_skill_guard/paired_interfaces/cni_copy_action_scope.py)

## Revision 6 ContractNLI 副本授权共用修订的前一断点

阶段 `revision6_cni_copy_approval_settled`，绑定 `0c34aea6b88a867888396531040a8eda34b945c91b131448416401c421e59214`。把制作新副本的禁止、取得书面授权前的限制和分项继承的保密信息范围绑定起来。原 TRAIN 1/24 与固定 DEV 1/16 命中，两项标签及引用均与原参考一致。固定 DEV 五臂各修正一题，无退化。完整执行四内部臂 208/272、证据 F1 56.57%，PARSE 199/272、49.42%。复用受影响原请求三笔，新增 0，27 项检查通过。 [原文范围与五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_COPY_APPROVAL_AND_FIXED_DEV_20261120.json)

前一阶段 `revision6_cni_cumulative_dev_settled` 将七个后续共用修订接入同一固定 DEV 运行入口。从原 B8 上游执行基线运行，逐项匹配七个封存输出。32 笔原执行请求，四内部臂 207/272、56.57%，PARSE 198/272、49.05%，与此前累计表逐臂一致。随后在此入口叠加书面授权来源核验，并从 272 项完整计算确认最新结果。后续直接复用新入口和这一规则。继续副本任务需有不同关系，例如能区分绑定同一动词的目的例外和只约束披露对象的例外。 [统一入口](../experiments/convergence_revision6_cni_cumulative_dev.py) · [逐臂重算](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_EXECUTABLE_CUMULATIVE_DEV_20261120.json)

## Revision 6 OpenExempt 宾州资产的前一断点

阶段 `revision6_oe_pa_civilian_assets_settled`，绑定 `5eefcb0b932d0456ed9454d84be4b5d7ae2033a0f547f0fe798469736f786840`。核对随题宾州服装、书籍、缝纫机及军服条款，按原文资产排除不适用引文。固定 DEV 四内部臂分类／估值 F1 为 86.03%／83.50%，PARSE 为 85.45%／79.26%。五臂分类各改善两份、估值各改善三份，零退化。复用 TRAIN 144 笔、DEV 10 笔实测，新增 0，11 项检查通过。 [实测与五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_PA_CIVILIAN_ASSETS_AND_FIXED_DEV_20261120.json)

B4 第四份的普通提案 EC 无有效原生输出。按每条实际程序组合恢复同组已付的其他读数，核实 PARSE 分类新增两项不适用引文，照常计入普通提案的原生缺失。两项新增错误没有影响合格提案的采纳。候选驱动、按时间及按分歧在 B3、B4、B6、B7 的 16 份下一批 TRAIN 上均为分类 69.95%、估值 56.90%。完整组消融及去掉新增类别证据后也逐源同判。原冻结协议、72 份快照、TEST 终态与曝光回执已核对。以后共享此条文核验，沿用 B4 读数，改进方向需有新的可归因提案或 M1 原文关系。 [选组比较代码](../experiments/convergence_revision6_oe_pa_civilian_assets.py)

## Revision 6 OpenExempt 俄勒冈估值的前一断点

阶段 `revision6_oe_oregon_property_settled`，绑定 `8c2b7e1af7ed9500def522226fe75c10104d6e93d1b2f26a06db34abfae0de4d`。按随题俄勒冈个人财产条款和逐资产评分口径，核对申报产权与金额，覆盖原 TRAIN 4/32、固定 DEV 2/16，九个金额均符合原参考。固定 DEV 估值 F1 四内部臂由 80.36% 升到 80.66%，PARSE 由 76.65% 升到 77.62%，均零退化。分类沿用 84.93%／84.35%。 [相同输入的 TRAIN 候选与五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_OREGON_PROPERTY_AND_FIXED_DEV_20261120.json)

B2 的普通提案与进入程序估值仍同为 60.71%，B6 进入程序 49.97%、普通提案 49.17%、PARSE 35.62%。继续给所有臂相同的金额证明，只有出现不同的可归因提案或作用域才派发后续比较。复用 TRAIN 48 笔和固定 DEV 3 笔原响应，新增 0，11 项检查通过。原授权文件、冻结协议、72 份快照、TEST 终态、聚合结果和曝光回执通过核验。

## Revision 6 MAUD 重复标记和节选定位的前一断点

阶段 `revision6_maud_excerpt_provenance_settled`，绑定 `2d1bdb7a944fd252c2ccb967d5cd72af94af69edc609007faeba7ab318c975be`。实现重复标记的保守合并和节选原文定位，核验九笔后批 TRAIN 与 32 笔原固定 DEV 请求。后批合成臂在共用来源规则下仍为 17/18，固定字段 13/18，直接读法 12/18。B5 一份合同的两对文本标记在两处给出已知与未决的不同投影，合并后原生输出持平。固定 DEV 有 4/16 份符合重复标记条件，五臂的两道契约题均已答对。23 项检查通过，新增请求 0。 [回放代码](../experiments/convergence_revision6_maud_excerpt_provenance.py) · [分母与逐项证据](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_MAUD_EXCERPT_PROVENANCE_20261120.json)

固定 DEV 剩余五项契约失分。第 1 份的两项有节选外的 §6.2 明文例外；第 9 份的负面契约明文保留适用的疫情法律，第 12 份的负面契约明确未引入疫情例外条目，两项与参考有分歧；第 10 份原节选无疫情标记，母合同最先出现疫情字样的条款管的是资料访问。保留原输入、参考与累计分数。结束重复标记假设的扩验，下一轮定位有不同源证、训练覆盖和读数差异的关系，或区分完整前缀原生对照的 M2 候选。

## Revision 6 ContractNLI B4 PARSE 提案的后批断点

阶段 `revision6_cni_task_screen_parse_later_settled`。会话 20649 已结束，绑定 `f6e8a2adca482c71e8e51738d824d5c9f0041de91aa28f71ebc14a3166c21d53`。原 B6–B8 九份 TRAIN 均未由现有共用源证确定第三方披露题。两路原版程序完整配对，18 笔全部正常解码，共 224,202 tokens。10 项相关检查通过，原冻结协议、72 份快照、TEST 终态和曝光回执保留。 [匹配读数和逐份结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_TASK_SCREEN_PARSE_LATER_TRAIN_20261120.json)

- 候选驱动和四个强对照在九份合同上逐份分类得分一致，各为 7/9。正确类证据 F1 为 31.62% 对 26.54%，候选驱动在三份改善、两份退化，母来源配对 95% 区间 [−24.31, +36.18] 个百分点。原固定 DEV 的公开输入有 15/16 待解，进入程序已有 15 笔精确读数，B4 PARSE 提案缺 15 笔。当前前向区间不足以启动该扩验。复用这些证据，优先推进有不同作用域依据的 M1 合同接口或能改善同信息对照的新 M2 更新。

## Revision 6 ContractNLI B4 普通提案的后批断点

阶段 `revision6_cni_task_screen_b4_later_settled`。会话 37909 已结束，绑定 `fd1dcb4bb27680f4ceeb7f2401afc5901f9eea89e18fe8de7422d66792179248`。原 B6–B8 九份 TRAIN 中，协议事实披露题七份由共用规则确定，余 B6-3、B7-3 各补一笔精确进入程序读数，共 23,956 tokens。九笔 B4 采纳程序原读数全部复用。五个策略均为 7/9，正确类证据 F1 74.07%。两份待解合同在两路均失分，B5 的一题分类优势未在后批复现。 [按来源结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_TASK_SCREEN_B4_LATER_TRAIN_20261120.json)

## Revision 6 ContractNLI 用途证明的前一断点

阶段 `revision6_cni_purpose_proof_settled`。会话 89278 已退出，绑定 `b62c8b3f4142dc2bbbd2ff23b3f117c6ad0a5f5224eae687432d3c5753397b6d`。九笔前向实际响应沿用，新增 0，10 项检查通过。原 TRAIN 3/24 份出现完整用途限制，分类和引文均精确匹配原参考。固定 DEV 原文覆盖 0/16，未读取新评分。

- 仅校准同类引文后，候选驱动 7/9，四对照 6/9，正确类证据 F1 为 74.07% 对 62.96%。把能由随题条款确定的分类也共享给所有臂后，五路均为 7/9 和 74.07%。新证明在原 B1–B5 拟合前缀覆盖为零，保留原筛选版本和 B4 其他假设的结论。 [分类与引文归因消融](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_PURPOSE_PROOF_TRAIN_20261120.json)

## Revision 6 ContractNLI B3 与 B5 按假设前向比较的前一断点

阶段 `revision6_cni_task_screen_forward_settled`。会话 50594 已退出，绑定 `1066315c3c36bbd6043a72f2bb1514909582336252a0948503d072b34e0f7bbd`。B3 普通和 B5 PARSE 的下批原 TRAIN 在 B4-3、B6-1、B6-3 补三笔进入程序读数，均正常解码，共 32,878 tokens。其余差异题由共用源文核验固定。复用实际候选响应，按合同成对计分。10 项检查通过，原冻结协议、72 份快照、TEST 终态及曝光回执通过核验。 [两次过渡、逐份结果与区间](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_TASK_SCREEN_FORWARD_TRAIN_20261120.json)

- 六份新过渡母来源、九道采纳相关题上，候选驱动 7/9，时间、分歧、范围内分歧及逐假设原生拟合均 6/9。正确类证据 F1 为 53.81% 对 59.26%。母来源等权的分类差 +8.33 个百分点，95% 区间 [0, +25.00]，证据差 −4.09 个百分点，区间 [−15.60, +3.33]。B4 路线分流后评分相同，B6 第三份用途题修正一项，第一份用途题的正确引文附近附带大量无关跨度。
- 原 TRAIN 已定位两处用途作用域：B6 第一份的独立“solely”句，第三份在第三方披露列表后继承同一禁止模态的用途分支。现有共用充分证明均未命中。下一轮用相同的原文限制与引文核验同时检验所有候选及强对照，复用三笔实测。按新证据评估 B6 的分类差和证据退化来自何处。

## Revision 6 ContractNLI B4 按假设筛选的前一断点

普通提案与 PARSE 提案分别绑定 `ed91b9b517e1cf7375eecd992823cf6412776ee6dd536cdd182eca6d16630479`、`f067dc1b8a5290fa00348131fc30b00792b7658847d0efd84649771b060936a9`。会话 90517、2324 已退出。每个比较复用 24 笔前缀拟合及 6 笔前向响应，7 项检查通过，新增 0。每个筛选策略从同一原 TRAIN 组池选一组、两笔筛查响应，并用相同的逐假设原生门槛。候选驱动按会被采纳的假设定位原文证据损失，只否决发生损失的假设。

- 普通提案中只保留 `nda-10` 的进入读器。B5 为 39/51，时间、分歧、候选范围内分歧和完整前缀原生选择为 38/51。正确类证据 F1 同为 50.98%。
- PARSE 提案中只保留 `nda-7` 的进入读器。B5 为 40/51，四个强对照为 39/51，正确类证据 F1 50.98% 对 49.02%。两项分类差均为 +1.96 个百分点，配对区间下界为 0。两次前向比较共用 B5 的三个母来源，独立母来源仍为 3。 [普通提案](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_TASK_SCREEN_TRAIN_20261120.json) · [PARSE 提案](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_TASK_SCREEN_PARSE_TRAIN_20261120.json)

## Revision 6 OpenExempt 条文适用的前一断点

阶段 `revision6_oe_clause_scope_settled`。会话 95346 已退出，绑定 `b7fc42625e3048f2b471aa5e9732abefe0237f62fda79afd7fc231a49b84d7a9`。复用 B6 的 24 笔执行响应与固定 DEV 的 10 笔受影响响应，新增 0，15 项检查通过。核对原冻结协议、72 份快照、TEST 终态和曝光回执。 [B6 法域分解与五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_CLAUSE_SCOPE_AND_FIXED_DEV_20261120.json)

- `convergence_oe_clause_scope.py` 使用随题精确条文核验择法条款和资产类型。B6 进入程序分类 F1 从 60.16% 到 63.49%，PARSE 保持 72.01%。PARSE 的正差只在亚利桑那与伊利诺伊，原 B7、B8 均无这两个法域。四种同预算筛选仍保留进入程序，纯原生拟合选 PARSE 分类。
- 固定 DEV 的变化均为删除不适用的宾州缝纫机引文。四内部臂分类／估值 F1 由 83.79%／79.13% 升至 84.93%／80.36%，分别改善 2／3 份。PARSE 由 83.01%／75.45% 升至 84.35%／76.65%，分别改善 3／2 份。五臂零退化，原参考无冲突。接续候选统一使用共用条文核验。B6 后续派发须有不同于已结算证据的依据。

## Revision 6 OpenExempt 资产键绑定的前一断点

阶段 `revision6_oe_ec_identity_settled`。离线会话 8805、30728 均已结束。前者在 B2、B3、B5、B6 的 16 份原 TRAIN 上复用 64 笔进入程序和普通提案响应，补入 32 笔原先未进比较的 PARSE 响应。每份来源的三个程序使用相同公开输入和冻结设置。B6 的 PARSE 分类高 10.81 个百分点，估值低 14.35 个百分点；纯原生拟合只选 PARSE 分类，四个同预算原文筛选均保留进入程序。 [完整候选池及采纳](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_REJECTED_PARSE_TRAIN_20261120.json)

- `convergence_oe_ec_identity.py` 把唯一匹配的大小写别名连回原资产，保留歧义项和精确键，随后对所有程序重用既有原文规则。B6 的四份 TRAIN 中三份触发键绑定，PARSE 分类 F1 为 70.97%→72.01%，进入程序保持 60.16%，四种原文筛选的采纳相同。固定 DEV 五臂各改善一份、零退化，四内部臂分类 F1 83.27%→83.79%，PARSE 82.49%→83.01%，估值沿用。
- 本轮去重复用 98 笔历史执行器响应，新增 0，在途 0，22 项检查通过。两个绑定是 `91e9f8b168b11baea5f563da63cdcba453da14ee08a764a385af27a722ce625d` 和 `1f7e6278eb8cca8c9530eb8309b42e318dc4725a8cada94793d1a5297b0786e6`。原冻结协议、72 份源码快照、TEST 终态与曝光回执通过核验。后续候选统一使用新资产键，B6 PARSE 无候选驱动采纳差异，接续选择不同的源文关系或实际提案。 [资产绑定与五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_EC_IDENTITY_AND_FIXED_DEV_20261120.json)

## Revision 6 M1 协议事实披露的前一断点

阶段 `revision6_cni_agreement_fact_train_settled`。会话 69083 已结束，回执 `artifacts/legal_skill_convergence_20261117/handoff/revision6_cni_agreement_fact_train_terminal_20261120.json`，绑定 `6f3a2d565c6847fe67988ec3f434d6d418db27462ec4ba4364fe798f0a0aaf7e`。21 笔新冻结读数全部正常解码，共 101,527 tokens。复用两条原臂的配套读数，另逐笔核验先前十份合同的 30 笔实测，其中五份与本次重合，接口和请求分别保留。17 项检查通过，冻结协议、72 份源码快照、TEST 终态和曝光已核对。 [三路实测、源范围与多数类对照](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_AGREEMENT_FACT_TRAIN_20261120.json)

- `cni_agreement_fact_relation.py` 保留九个局部状态的消费者，将披露规则和协议事实的作用域合成具名关系。七份前四批原 TRAIN 在共用规则仍未确定的范围内，合成 1/7，固定字段与直接各 6/7，留一多数类亦为 6/7。正确类证据 F1 分别为 9.52% 和 85.71%。合成均预测蕴含，六处错误使用了一般保密、用途、谈判内容或存续条款。唯一对的参考引用审计安排性质，合成缺少支配该义务的前导证据。
- 拟合快照保留进入程序。原后四批另有四份公开匹配、固定 DEV 十份，均未派发该接口。累计五库沿用已结算的强制披露通知修订。后续选不同的有 TRAIN 源证的关系，或有真实候选可区分完整前缀原生对照的 M2 比较。

## Revision 6 ContractNLI 强制披露通知的前一断点

阶段 `revision6_cni_notice_roles_settled`。会话 59204 已退出，回执 `artifacts/legal_skill_convergence_20261117/handoff/revision6_cni_notice_roles_terminal_20261120.json`，绑定 `c68165563d15488b861cecbe1d915f9385c6452bb8e9c81861219bf858a0b2ac`。12 项检查通过，复用 4 笔 TRAIN 和 14 笔固定 DEV 原请求，新增 0。已核对原冻结协议、72 份源码快照、TEST 终态和曝光回执。 [原文证据与五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_NOTICE_ROLES_AND_FIXED_DEV_20261120.json)

- `cni_compelled_notice_roles.py` 连接强制披露的触发、编号通知义务及合同明示的信息提供方。新增原文覆盖 TRAIN 2/24、固定 DEV 7/16，均符合原生分类参考，证据集合完全匹配分别为 2/2、5/7。正式固定 DEV 回放五臂的通知题均从 8/16 到 12/16，证据 F1 达 68.75%，零退化。相对早期覆盖保护，普通教师与 PARSE 的正确数均保持 12/16，证据 F1 分别由 39.58%、43.75% 达到 68.75%。
- 已纳入累计五库开发结果。ContractNLI 四内部臂 207/272，证据 F1 56.57%；PARSE 198/272，证据 F1 49.05%。共用修订保留 M1 和 M2 的独立对照结论。剩余四个固定 DEV 错误均为缺乏通知义务依据的肯定预测。原 TRAIN 内没有严格强制披露触发与负面通知参考的同类组合。后续优先用有原 TRAIN 支持的关系继续匹配比较。

## Revision 6 ContractNLI 引文选组的前一断点

阶段 `revision6_cni_archive_group_guard_settled`。会话 73512 已退出，回执 `artifacts/legal_skill_convergence_20261117/handoff/revision6_cni_archive_group_guard_terminal_20261120.json`，绑定 `d08901110a49e0e4801565ef1e56aa97e8454309686a25d07f5ec8066877d0e1`。18 项检查通过，去重复用 39 笔原 TRAIN 响应，新增 0。已核对原冻结协议、72 份源码快照、TEST 终态和曝光回执。 [B1、B4 采纳与后批评分](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_ARCHIVE_GROUP_GUARD_TRAIN_20261120.json)

- `cni_signed_candidate_groups.py` 依据候选相对进入程序新增的原文冲突或证据缺失选组。各筛选策略在同一池中选一组、两笔响应，并用同一原生门槛和否决规则。B4 PARSE 候选在当批原生分类高 3 项，在累计前缀低 4 项。候选驱动筛中 B2 第一份合同的四项有源文证据的退化，保留进入程序。按时间、按分歧和当批原生评分均采纳候选。B5 三份合同各为 39/51。正确类证据 F1 为候选驱动 50.06%、时间及分歧 47.71%、逐假设原生 49.02%。候选驱动相对时间的配对区间为 −0.80 至 +5.88 个百分点。完整 TRAIN 前缀原生对照与候选驱动逐项同判。
- B1 普通提案在三份拟合合同上多答对一项，三个源证组均无可区分的增减，全部筛选采纳候选。在 B2、B3 六份原 TRAIN 的共用规则结果中，候选 66/102、进入程序 76/102，逐假设原生选择 72/102。B1 的前向退化及 B4 的较强对照持平均已封存。下一轮优先验证有真实候选能区分完整前缀对照的范围。固定 DEV 累计沿用。

## Revision 6 MAUD 条件与稀疏见证的前一断点

阶段 `revision6_maud_witness_train_settled`。会话 35401 已结束，回执 `artifacts/legal_skill_convergence_20261117/handoff/revision6_maud_witness_train_terminal_20261120.json`，绑定 `c0a93c00d277cbc816761d764e083d7392d94a223db27542ce764c09db40a304`。9 笔新冻结读数、42,308 tokens，原归档对照复用 36 笔，16 项检查通过。已核对原冻结协议、72 份源码快照、TEST 终态和曝光回执。 [原生结果及退化归因](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_MAUD_WITNESS_TRAIN_20261120.json)

- `maud_covenant_witnesses.py` 将条件单独读出，每类义务存一个已验证的标记和锚点、未决标记与核验状态。两个标记的 2,916 种局部状态与覆盖组合均复现原消费者。九笔实际读数正常解码，每个肯定见证都通过条件真值与锚点家族的结构检查。
- 原 B5–B8 九份适用 TRAIN 上，在相同原文核验后，稀疏见证 13/18，固定字段 13/18，直接读法 12/18，前一去重联合接口 17/18。相对前版的四处退化集中在两份仅负面节选有疫情标记的合同，一份将同一条件错接到两类义务，一份保留两类未决。按此前原文复核口径搁置两个负面参考冲突后，四路分别为 13/16、13/16、12/16、15/16。该结构在固定 DEV 的覆盖为 0/16，累计五库结果沿用。后续保留锚点修复，优先选择在原开发语料中有覆盖的新关系结构和能区分同信息对照的实际候选。

## Revision 6 MAUD 限制清单锚点的前一断点

阶段 `revision6_maud_governor_dev_settled`。会话 78214 已退出，回执 `artifacts/legal_skill_convergence_20261117/handoff/revision6_maud_governor_dev_terminal_20261120.json`，绑定 `4f9612b5d5295ed2e7fa63d6c253cd00d644bfcb94a4814ae30dfc1ee91490ce`。12 笔新冻结读数、52,362 tokens，全部正常解码。复用 9 笔原 TRAIN 响应，14 项检查通过。已核对原冻结协议、72 份源码快照、TEST 终态和曝光回执。 [DEV 配对及逐位点统计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_MAUD_GOVERNOR_DEV_20261120.json)

- `maud_covenant_governors.py` 补齐带同意插语、间接禁止和集体禁止的限制清单锚点。四份原固定 DEV 的目标节选各补一个锚点，三份原清单在目标节选无负面锚点。原 TRAIN 的九笔联合读数有五份出现同一家族双槽冲突，合计 12 个标记。联合枚举在语法上排除同一家族重复，保留消费者的 100 个既有局部状态。
- 三路使用同一全文、同一补齐锚点和相同共用规则。合成、固定、直接正确数为 2/8、6/8、5/8，原始和规则后分数相同。合成在三份合同的七个标记上排除两类关系，三道普通经营题失分。合成对固定与直接的母来源配对差为 −50.0 与 −37.5 个百分点，上界均为零。联合枚举未进入正式路由，五库累计 DEV 沿用。后续保留补齐锚点作为共用输入，针对已观察的排除偏差，验证可保留显式条件和单家族关系的表示。
- 复算此轮绑定时，将保存的 `binding.json` 中 `eligibility` 的键恢复为整数位点，再按原函数取摘要。结算时已按生成时的键类型复核。

## Revision 6 OpenExempt B8 候选池的前一断点

阶段 `revision6_oe_b8_portfolio_settled`。会话 81628 已结束，回执 `artifacts/legal_skill_convergence_20261117/handoff/revision6_oe_b8_portfolio_terminal_20261120.json`，绑定 `b235e7fd6ffcc574b4502e7840d07612cd43957005c73bb2ee8ac3a85f3317dd`。10 项检查通过，复用 40 笔原 B8 TRAIN 响应，新增 0，在途 0。已核对原冻结协议、72 份源码快照、TEST 终态和曝光回执。 [B8 候选池及五库固定 DEV](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_B8_PORTFOLIO_TRAIN_AND_FIXED_DEV_20261120.json)

- `convergence_revision6_oe_b8_portfolio.py` 绑定三个实际进入程序和两个实际提案，在四份原 B8 母来源上重建 25 种分类／估值组合。共用威斯康星州住宅豁免规则核到 1/4 份，产权、居住和额度均与原参考一致。两个组预算下，候选驱动和按时间选相同组，按分歧和按进入程序风险选不同组，四路均保留 M2 的进入程序。只按当批原生分数拟合选用 PARSE 分类和普通提案估值，两任务平均 F1 增量 +5.00 个百分点。固定 DEV 对住宅规则覆盖 0/16，五库结果沿用。历史实际采纳按原绑定保留。B1–B8 现有选组证据直接复用。
- MAUD 的原文候选检查在固定 DEV 上找到 11/16 份含疫情标记且两类义务都有可见锚点的合同。已知正向区间仍限于 TRAIN。此前的单侧节选子类仍为 0/16。下一轮优先定位其中可由修订接口解决的关系表示问题，沿用同信息固定与直接读法。

## Revision 6 OpenExempt B1 家庭用品选组的前一断点

阶段 `revision6_oe_b1_household_fit_settled`。会话 61917 已退出，回执 `artifacts/legal_skill_convergence_20261117/handoff/revision6_oe_b1_household_fit_terminal_20261120.json`，绑定 `df7f8075c4f626d9a6acbfa5e3fd80209945083365b63f57c92ebe6c0a03f653`。13 项检查通过，复用 40 笔 B1/B2 同输入读数及 6 笔受影响固定 DEV 读数，新增 0。原冻结协议、72 份源码快照、TEST 终态和曝光回执通过核验。 [B1 选组、B2 实测与五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_B1_HOUSEHOLD_FIT_TRAIN_AND_FIXED_DEV_20261120.json)

- `convergence_oe_illinois_household.py` 将明确家用物件与服装、谋生工具、专业处方辅助器具分开。原 TRAIN／DEV 覆盖 1/32、3/16，均无原参考冲突。适用于所有臂的共用规则修复烘干机和台灯的误引。B1 普通提案仅换估值的两任务平均原生增量由 +4.17 个百分点降至 0，候选驱动、按时间、按分歧及原生拟合均保留进入程序。B2 复用历史进入程序和历史 PARSE 的完整成对结果。普通提案没有后批匹配读数，共用核验后无需为本项选组比较补读。
- 已阅固定 DEV 中，四内部臂分类／估值从 81.88%／78.61% 到 83.27%／79.13%，PARSE 从 81.80%／74.93% 到 82.49%／75.45%，五臂零退化。复用本次 B1 和已有 B2–B7 候选比较，后续按新的源文结构或可与强对照区分的采纳路径继续。

## Revision 6 MAUD 重复条款锚点的前一断点

阶段 `revision6_maud_anchor_idempotence_settled`。回放会话 63941 已退出，回执 `artifacts/legal_skill_convergence_20261117/handoff/revision6_maud_anchor_idempotence_terminal_20261120.json`，绑定 `38a66211e9bb62a2058382961aaf7b71cd5be2ef38cef48937f96d8574dc38f6`。18 项检查通过，复用 18 笔原模型请求，新增 0。原冻结协议、72 份源码快照、TEST 终态和曝光回执通过核验。 [响应回放与来源覆盖](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_MAUD_ANCHOR_IDEMPOTENCE_TRAIN_20261120.json)

- `maud_anchor_idempotence.py` 保留重复锚点表达的一项已知义务和另一项未决义务。新接口恢复 B7 第三份、B8 第一份和第三份的普通经营输出，原始正确数 8/18→11/18。旧锚点在 B8 第二份恢复可见分行例外的肯定判断，原负面参考为 No，旧锚点总分保持 11/18。共用条款核验和敏感性得分沿用。
- 仅负面契约节选有疫情线索的原 TRAIN 为 B1 第三份、B6 第二份和 B8 第二份，已分别进入此前校准及后批配对。固定 DEV 无同结构，未读取 DEV 标签。后续复用当前结果；有明确新结构或不同真实候选时再运行。

## Revision 6 MAUD 条件和义务关系的前一断点

阶段 `revision6_maud_operative_attribution_settled`。实测会话 18105 和回放会话 36102 已退出。回执 `artifacts/legal_skill_convergence_20261117/handoff/revision6_maud_operative_attribution_terminal_20261120.json`，实测绑定 `2e83eab92918066a69b22ac011d5b8f6bbbcdca1c5356ee2c2f291b696c4428f`，回放绑定 `3c864ae686a1f48099f7917ef2f7424451cc06ceddbddc501c8de5b5cee4447f`。新增 9 笔、42,217 tokens，正常解码 9/9，复用 27 笔同输入对照。16 项检查通过，原冻结协议、72 份源码快照、TEST 终态和曝光回执均已核验。 [实测和原文归因](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_MAUD_OPERATIVE_EDGES_TRAIN_20261120.json)

- `maud_operative_edges.py` 在单个焦点上联合绑定有效疫情条件和具体义务。原后四批 9 份较晚 TRAIN 的新接口、固定、直接和旧锚点原始得分依次为 8/18、10/18、9/18、11/18。既有共用核验后为 15/18、13/18、12/18、14/18。
- B7 第一份合同中，同一公司普通经营和负面条款有两个各自纳入疫情措施的前导段。共用原文核验恢复新接口两题后四路为 17/18、13/18、12/18、14/18。搁置 B6 第二份和 B8 第二份有可见单项例外且原参考为 No 的负面题，敏感性结果为 15/16、13/16、12/16、14/16。保留完整原生评分。两项强对照的配对区间下界均为零，固定 DEV 无该原文结构，沿用此前结果。继续时复用本次完整配对，优先验证新结构或不同真实候选。

## Revision 6 OpenExempt 机动车估值的前一断点

阶段 `revision6_oe_motor_vehicle_settled`。会话 90086 已退出，回执 `artifacts/legal_skill_convergence_20261117/handoff/revision6_oe_motor_vehicle_terminal_20261120.json`，绑定 `c303c407b164570a7dc1584c812a4607fdb6c05c9f00352e3e2001b29cbb7bb1`。16 项检查通过，复用 16 笔 B2 和 5 笔固定 DEV 原请求，新增 0。原冻结协议、72 份源码快照、TEST 终态和曝光回执均已核验。 [固定 DEV 五库与 B2 筛选](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_MOTOR_VEHICLE_TRAIN_AND_FIXED_DEV_20261120.json)

- `convergence_oe_motor_vehicle.py` 从适用的题面法条读取金额。联邦规则限产权明确的单一申报人，威斯康星州只输出保守上下界同意的金额。原 TRAIN 的 1 个和固定 DEV 的 5 个金额均与原参考一致。已阅 DEV 中四个内部臂估值 F1 由 76.59% 升至 78.61%，PARSE 由 73.30% 升至 74.93%，五臂零退化。分类沿用。
- B2 唯一适用车辆的进入程序和候选均报对 $4,450。完整 B2 两程序原生输出与同预算策略的选择照旧。后续独立比较需利用另一个真实候选采纳差异或新的消费者语义范围，避免重试该金额假设。

## Revision 6 ContractNLI 外部顾问许可的前一断点

阶段 `revision6_cni_external_recipients_settled`。会话 76307 已退出，回执 `artifacts/legal_skill_convergence_20261117/handoff/revision6_cni_external_recipients_terminal_20261120.json`，绑定 `7292c75bee65b9a6500f14ed769f85302271e14871b2449b7e267b26861205de`。15 项检查通过，复用 18 笔 B3 原请求和 2 笔固定 DEV 原请求，新增 0。原冻结协议、72 份源码快照、TEST 终态和曝光回执均已核验。 [原生指标和五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_EXTERNAL_RECIPIENTS_TRAIN_AND_FIXED_DEV_20261120.json)

- `cni_external_recipients.py` 区分需要知悉的外部顾问和须经单独批准的其他第三方，并把外部成员定义补到引用。原 TRAIN 两处都是 B3 提案此前丢失的许可。共用核验后 B3 的 NDA-7 分类两路各 6/9，证据 F1 为进入程序 43.33%、提案 38.89%。B4 三份原 TRAIN 找到提案响应，缺少同设置的 B3 进入程序响应。当前范围的分类差异已由共用核验解释，未追加该后批读数。
- 已阅固定 DEV 五臂各修正一项外部披露。累计分类内部臂 203/272、PARSE 194/272，证据 F1 分别为 54.61%、46.97%。其余四库沿用。后续优先验证有新来源依据且能区分现有强对照的候选或合同接口。

## Revision 6 M2 MAUD 八批候选的前一断点

阶段 `revision6_maud_candidate_archive_settled`。会话 39474 已退出，回执 `artifacts/legal_skill_convergence_20261117/handoff/revision6_maud_candidate_archive_terminal_20261120.json`，绑定 `810723401e0589a44810bd021756c7e2947c7821ec694e2a66120477528ac58b`。29 项检查通过，90 笔归档响应逐笔核验，新增 0。原冻结协议、72 份源码快照、TEST 终态和曝光回执均已核验。 [逐批原生计分与五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_MAUD_CANDIDATE_ARCHIVE_TRAIN_20261120.json)

- `convergence_revision6_maud_candidate_archive.py` 覆盖八批原 24 份 MAUD TRAIN 的 16 项实测提案。16 项中原记录 5 项正增益、7 项输出有差异。共用 B4 无损恢复及源文核验后，3 项正增益、1 项退化均来自普通经营题。同样给予两路旧 TRAIN 母合同的范围证据后，16 项逐项同判。后者是回顾性对照，母合同未进入模型提示。固定 DEV 的 16 份公开输入均未命中新规则，累计指标沿用。
- `maud_negative_preamble.py` 核验 B1 第一份合同的编号例外直接管辖本段禁止义务，归档 PARSE 提案将原正确的 Yes 改为 No。共用规则恢复该题。正式 M2 和普通教师的八批 MAUD 程序逐批相同。下一条 M2 比较须有可改变采纳且在后批有覆盖的真实候选，复用本次 MAUD 全库候选证据。

## Revision 6 ContractNLI 具名事件关系的前一断点

阶段 `revision6_cni_event_residual_settled`。会话 57128 已退出，回执 `artifacts/legal_skill_convergence_20261117/handoff/revision6_cni_event_residual_terminal_20261120.json`，绑定 `35985a97b18506427187856f923c82a3e4083170df7b677f6658ea66950d7ab9`。19 项检查通过，复用配对请求 12 笔和受影响原 TRAIN 请求 2 笔，新增 0。 [同信息引文归因](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_EVENT_RESIDUAL_TRAIN_AND_FIXED_DEV_20261120.json)

- `cni_event_relation.py` 的具名关系保持 27 个部分状态的原消费者结果。会话 80579 已结算三笔新冻结读数，29,901 tokens，旧固定／直接请求及旧合成回复共九笔复用。六个原未决判断全部给出分类。三路在已有共用规则下各为 7/9，合成的正确类证据 F1 为 62.96%，两条强对照均为 56.30%。差异集中在 B2 第二份的存续条款。 [三笔实测与配对](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_EVENT_RELATION_TRAIN_20261120.json)
- `cni_event_residual.py` 将三路的存续证据绑定到同一协议终止条款，并核验另一份合同的所有处分项都承接同一个请求前导。合成、固定、直接逐项预测一致，分类各 8/9、正确类证据 F1 各 74.07%。固定 DEV 五臂无输出改动。六份后批原 TRAIN 仍保留，下一条路径须有新的源文依据和可与强对照区分的机制。

## Revision 6 ContractNLI 事件链接的前一断点

阶段 `revision6_cni_event_linkage_settled`。会话 42779 已退出，回执 `artifacts/legal_skill_convergence_20261117/handoff/revision6_cni_event_linkage_terminal_20261120.json`，绑定 `19b7f80100c36810dc56b3f7a3083d50eb44c7898a3500038b823aeec69cfb55`。18 项检查通过。共用修订复用 9 笔配对、6 笔原 TRAIN 和 1 笔原 DEV，新增 0。首版上下文引文的回执及三处 DEV 退化仍保留。 [原文归因与五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_EVENT_LINKAGE_AND_FIXED_DEV_20261120.json)

- `cni_event_linkage.py` 核实交易终止、请求与后续处分条款的连接，以及法定或归档例外。周围条款用于核实连接，直接授权保留的条款进入证据。三处固定 DEV 保留例外的分类均维持，PARSE 改善一份引文，累计证据 F1 为 46.60%。四个内部臂累计为 54.24%。
- M1 联合事件读数的会话 14484 已正常结束，绑定 `5d00cafc9efeef02870af0281ad023222ed3c0f4cf06005fb4dfcf2ef0fbde70`。九笔正常完成，87,637 tokens。合成、固定、直接原生正确数为 3/9、7/9、7/9，共用原文回放为 6/9、7/9、7/9。两份合同合成输出的六个任务均为未决。后批六份原 TRAIN 的输入覆盖已记录，扩验条件未达。继续 M1 需要能处理这类未决事件关系的实质新候选，M2 需要不同的源文和采纳差异。 [九笔原始对照](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_EVENT_WITNESS_TRAIN_20261120.json)

## Revision 6 M2 冲突方向与选组的前一断点

阶段 `revision6_oe_signed_direction_settled`。会话 28615 已退出，回执 `artifacts/legal_skill_convergence_20261117/handoff/revision6_oe_signed_direction_terminal_20261120.json`，绑定 `4cbb13be23eeecd447d2d20bc93bca24ac71bbbd1ee8b6bd38563352e48ac566`。19 项检查通过。原前向候选池 144 笔，B2/B5 当批复核 32 笔，两池重叠 8 笔，去重 168 笔。新增请求 0。 [原文方向与六批选组结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_SIGNED_DIRECTION_TRAIN_20261120.json)

- `convergence_oe_signed_direction.py` 只把候选实际改动且被独立源据否定的断言计为该候选的新冲突，记录由另一任务揭示的既有错误及方向未决的冲突。B7 的车辆引文归为估值误引，家庭用品引文缺少独立方向证据。B2 和 B3 换组选例，六批均沿用原候选采纳。16 份前向 TRAIN 的候选驱动和两条同预算强对照逐预测一致，分类与估值 F1 为 66.01%／54.54%。
- B2、B5 的选组对照均保留进入程序，已有证据支持继续复用现有结果。后续集中到有实质不同候选与源文关系的 M2 比较，或有原文差异支持的 M1 合同接口，五库固定 DEV 沿用。

## Revision 6 OpenExempt 资产类别的前一断点

阶段 `revision6_oe_item_categories_settled`。会话 30790 已退出，回执 `artifacts/legal_skill_convergence_20261117/handoff/revision6_oe_item_categories_terminal_20261120.json`，绑定 `c0ddaa91ce91b44a7c2205b038fef4fb62602127b2f48a78637fd4634155cc73`。16 项检查通过，复用 144 笔 TRAIN 和 3 笔受影响 DEV 原响应。首个回放在逐条输出比较时退出，重新核对引文多重集并使用封存原顺序完成。新增请求 0。 [五库累计与来源归因](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_ITEM_CATEGORIES_AND_FIXED_DEV_20261120.json)

- `convergence_oe_item_category.py` 使用原题法条、独立资产类别和产权。四个固定 DEV 内部臂分类 F1 从 81.44% 升至 81.88%，估值为 76.59%。PARSE 分类／估值由 81.35%／73.01% 到 81.80%／73.30%。五臂零退化，已纳入累计五库 DEV。
- 按原 B7 采纳决定重放，各主要选组对照的前向分类和估值 F1 均为 66.01%／54.54%。两个母来源的差别只在引文顺序，回执 `handoff/revision6_oe_item_categories_claim_order_20261120.json` 验证了同一多重集及重复计数。B7 新增的两条跨任务冲突中，俄勒冈家庭用品引文在原 EC、EV 参考均存在，车辆引文在两者均缺席。下一步在有独立原文支持和真实不同提案时，测试能区分分类漏引与估值误引的筛选。

## Revision 6 M2 同任务候选选组的前一断点

阶段 `revision6_oe_competing_port_settled`。会话 52854 已退出，回执 `artifacts/legal_skill_convergence_20261117/handoff/revision6_oe_competing_port_terminal_20261120.json`，绑定 `eb7de24cfb5038cdfea496e22ec85c4a7897c83c826b4989e15a5f32b8196879`。复用 144 笔实测，31 项检查通过。三次命令行尝试在历史候选池哈希校验时退出，导入 `experiments.convergence_revision6_oe_competing_port` 调用 `run(True)` 通过原哈希并完成。所有尝试均为离线回放。 [M2 选组及前向结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_COMPETING_PORT_TRAIN_20261120.json)

- 在原两组预算下，B7 第二组发现普通估值提案新增两处跨任务冲突，第四组有适用于 PARSE 的原文修正。新策略采纳 PARSE 估值，按时间和按分歧仍采纳普通估值。其余三批采纳决定沿用。16 份前向 TRAIN 分类 F1 均为 64.98%，估值 F1 为 52.34% 对 53.73%，两项平均差 −0.69 个百分点，配对区间 [−1.85, 0]。基于此结果沿用固定 DEV。M2 下一条路径须有独立来源支持修正可迁移，或有不同的真实提案与来源关系。

## Revision 6 MAUD 负面契约引文的前一断点

阶段 `revision6_maud_negative_witness_settled`。会话 18006 已退出，回执 `artifacts/legal_skill_convergence_20261117/handoff/revision6_maud_negative_witness_terminal_20261120.json`，绑定 `09a0c32a021df8fda5b5c618cac360e8171d416396e3ed152ff0aa27e2e094ef`。21 项检查通过，复用 70 笔物理响应，新增 0。 [引文范围和同条件回放](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_MAUD_NEGATIVE_WITNESS_TRAIN_20261120.json)

- `maud_negative_witness.py` 复用编号引入证据，将负面题节选中未引用的前导例外、节选截止后的单项例外、可见契约单项例外和独立访问义务落到原文位置。B6 第三份四路负面判定均由 Yes 改为未决，计分持平。B6 第二份贷款及 B8 第二份分行例外的原文位置经精确母合同校验，原参考均为 No。公开 DEV 覆盖 0/16，固定 DEV 分数沿用。
- MAUD 联合字段保留此前的普通经营前向信号及区间。继续使用原 TRAIN/DEV，待有实质修订和适用来源时再扩验此路径。

## Revision 6 MAUD 联合字段前向的前一断点

阶段 `revision6_maud_joint_forward_settled`。会话 58680 已退出，回执 `artifacts/legal_skill_convergence_20261117/handoff/revision6_maud_joint_forward_terminal_20261120.json`，绑定 `f19399eeec815a953fbfa7e09f560d45a0f545bcd8e46a1c408e6d4d6b83e680`。原 B6 第二、第三份和 B8 第二份合同共三笔新联合读数，21,183 tokens，九笔匹配对照复用，全部正常解码。首个会话 3567 在探活时因沙箱网络限制退出，发生在请求预留之前；同绑定后续正常完成。 [前向比较](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_MAUD_JOINT_FORWARD_TRAIN_20261120.json)

- 三份普通经营话题联合、固定、直接、旧锚点合成分别为 3/3、1/3、0/3、2/3。四路负面契约均为 0/3，未满足固定 DEV 扩验条件。联合读器的负面肯定引用来自具体贷款、借款和分行关闭例外，后续应先按原始任务范围区分统摄前导段、明确引入的条款和单项例外。保留原读数和标签。

## Revision 6 MAUD 联合范围同信息核验的前一断点

阶段 `revision6_maud_joint_scope_controls_settled`。会话 22280 已退出，回执 `artifacts/legal_skill_convergence_20261117/handoff/revision6_maud_joint_scope_controls_terminal_20261120.json`。19 项相关检查通过，复用 40 笔原物理响应。已有规则同时应用后，联合、固定、直接和旧合成依次为 19/20、17/20、16/20、14/20。回到原 TRAIN 母合同核对两处共同修正，母合同未进入提示或评分。 [原文与四路原生比较](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_MAUD_JOINT_SCOPE_CONTROLS_TRAIN_20261120.json)

## Revision 6 跨条款用途证据的前一断点

阶段 `revision6_cni_purpose_links_settled`。会话 47349 已退出，回执 `artifacts/legal_skill_convergence_20261117/handoff/revision6_cni_purpose_links_terminal_20261120.json`，绑定 `7d26d7a3d18b3863219b37de62e2f9c021cf59e843d6f77a9dbd292b667d2ea1`。26 项相关检查通过，账本 15,180 笔，在途 0。 [跨条款证据和五库累计结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_PURPOSE_LINKS_TRAIN_20261120.json)

- `cni_purpose_links.py` 绑定两份合同中同名用途的许可例外，以及另一份合同中相邻段落的披露方、接收方和所指信息。只在用途判断已经为 Entailment 且引用必要条款时补引。TRAIN 三路各改善 3、2、1 份，零退化。
- 沿用排除未勾选选项的口径，双读器和两个强对照各 23/24。共用链接后正确类证据 F1 为 84.58% 对 83.19%，差 +1.39 个百分点，区间 [−4.86, +7.64]。固定 DEV 16 份无该结构，未读取 DEV 标签。双读器用途引文的归因比较已结算，原实测直接复用。

## Revision 6 未勾选条款归因的前一断点

阶段 `revision6_cni_form_attribution_settled`。会话 28268 已退出，回执 `artifacts/legal_skill_convergence_20261117/handoff/revision6_cni_form_attribution_terminal_20261120.json`，绑定 `82989a4b2aaaf0a78f208f96445b5bc6411f357b1d5a49749f2d397cbb5d196b`。23 项相关测试通过，账本 15,180 笔，在途 0。 [来源归因与五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_FORM_ATTRIBUTION_TRAIN_20261120.json)

- `cni_form_evidence.py` 区分单选表单中已选、排除和未决选项。24 份原 TRAIN 仅 B5 第三份匹配。两项选项均未勾选，合成物理响应把第 9 段作为非授予义务的锚点；第 27 段的书面许可条件未提供独立非授予依据。原参考答案为 Entailment，仅引用第 9 段。固定 DEV 的 16 份公开输入无适用组，未读取 DEV 标签。
- 单独搁置该断言后，原双读器比较中 M1 与两强对照均为 23/24，正确类证据 F1 为 80.77% 对 78.19%。用途复合条款共用修订后为 83.75% 对 79.58%。两个证据差的配对区间均跨零。官方原始得分和已有曝光原样封存。后续用途证据仍可考察明确的跨条款依赖，单选模板没有可供扩验的固定 DEV 母来源。

## Revision 6 M2 按假设采纳的前一断点

阶段 `revision6_cni_scoped_adoption_settled`。会话 34812 已退出，回执 `artifacts/legal_skill_convergence_20261117/handoff/revision6_cni_scoped_adoption_terminal_20261120.json`，绑定 `5f5ae6784e02d890a07523a6caf253c9820ba0070efdd22f12aed95ec6e86ca0`。18 项相关检查通过，复用 24 笔 B1–B4 和 6 笔 B5 请求，新增 0，账本 15,180 笔，在途 0。 [全 17 假设的 B5 结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_SCOPED_ADOPTION_TRAIN_20261120.json)

- 原 B4 候选的角色范围采纳现在与整份、逐假设及同范围原生选型同台核验。按假设保留进入程序或候选版本，并将七个策略各自的 17 项程序分配封存。B5 上各策略均答对 35/51。候选驱动与同范围原生选择逐项相同，正确类证据 F1 均为 32.35%。按时间与按分歧均为 29.41%，全部逐假设选型为 34.31%，整份采纳为 39.54%。超出两项角色范围的 45 项中，整份提案的证据收益未被收窄后保留。固定 DEV 沿用。
- B4 的两个 MAUD 表面正向提案对应已有的同一截断修复。B3 合同候选在两个角色假设上有退化，但目前可同时源证这两项的归档组只有一组。沿用已有证据，后续选择可独立区分强对照的新原文关系或新实测提案。

## Revision 6 OpenExempt 亚利桑那家庭用品的前一断点

阶段 `revision6_oe_arizona_household_settled`。评估会话 76074 已退出，回执 `artifacts/legal_skill_convergence_20261117/handoff/revision6_oe_arizona_household_terminal_20261120.json`，绑定 `b27af6d351b4b72fc67c845608e99df3350a2eb602126626f87d4a016096f0b9`。19 项相关测试通过，复用 16 笔 B2 TRAIN 和 4 笔固定 DEV，新增 0，连续账本 15,180 笔，在途 0。 [同信息选组与五库累计指标](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_ARIZONA_HOUSEHOLD_AND_FIXED_DEV_20261120.json)

- `convergence_oe_arizona_household.py` 核对原输入法条、明确资产类型、产权和上限。B2 第四个母来源的空调引文和配套误引解释了原候选估值增益。共用规则把批次估值差由 +25.00 个百分点降至零。候选驱动和按时间仍选同一组，按分歧选另一组，均保留进入程序。B2 的缺失前向请求仍无选择对照可验证。
- 固定 DEV 五臂同一份母来源的分类和估值各改善、零退化。四内部臂分类／估值 F1 为 81.44%／76.59%，PARSE 为 81.35%／73.01%。已并入累计五库 DEV。保留原冻结结果和曝光记录，独立收益仍待验收。
- 补查已归档 B6 组合选组的原当批读数。新规则仅改变第三组。仅替换估值的两任务平均拟合差由 −3.28 到 −0.78 个百分点，五个策略仍保留进入程序。复用原读数作诊断，B6 的原前向结果已有结算。 [原组合选组](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_PORTFOLIO_TRAIN_20261120.json)

## Revision 6 复合条款用途证据的前一断点

阶段 `revision6_cni_compound_purpose_dev_settled`。TRAIN 会话 45460、固定 DEV 会话 11372 已退出。回执 `artifacts/legal_skill_convergence_20261117/handoff/revision6_cni_compound_purpose_dev_terminal_20261120.json`，绑定 `357f1b91a404def46e61b0c1c890cb73c004fce4a68eb4032a06b89e399e0095`。23 项相关测试通过，账本 15,180 笔，在途 0。 [TRAIN 与五臂固定 DEV](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_COMPOUND_PURPOSE_TRAIN_AND_FIXED_DEV_20261120.json)

- `cni_compound_purpose.py` 仅在已引用完整限定用途时，按义务作用域去除可复核的附带引文。24 份 TRAIN 的合成、固定、直接各改善 2、1、1 份，零退化。沿用锁定选择策略在已检查错误的 B5–B8 复算，双读器正确类证据 F1 为 86.53% 对 79.58%，配对区间 [−1.39, +15.28] 个百分点。固定 DEV 80 个候选输出均未改变，五臂用途分类各 13/16。新增请求 0。
- B5 权利题触发差异的三笔请求均正常结束。合成解码为 Entailment，固定字段未决，单独直接为 Contradiction。这项分类结果与用途证据规则独立。保留现有双读器和强对照结果。M2 的 B1 无原生正向提案，B2、B5 的现有拟合及四次匹配过渡已有结算，按原始候选池重复选组缺少新证据。

## Revision 6 双读器联合选择的前一断点

阶段 `revision6_cni_evidence_pair_settled`。会话 54147 已退出，回执 `artifacts/legal_skill_convergence_20261117/handoff/revision6_cni_evidence_pair_terminal_20261120.json`，绑定 `31b4e4bd7167924fed0f3ec3f5c11d2d95a455581bf3cb3386a95018ff5bfca6`。2 项定向测试通过，复用 72 笔原 TRAIN 请求，新增 0，账本 15,180 笔，在途 0。 [双读器 TRAIN 结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_EVIDENCE_PAIR_TRAIN_20261120.json)

- `cni_evidence_pair.py` 按任务拟合两读器同判时的证据取法和异判时的整条答案选择。训练前缀 B1–B4，前向 B5–B8。每个配对各有两笔实测读数，原文证明和用途引文筛法共用。直接加合成较直接加固定字段及直接单读均由 23/24 到 24/24，证据 F1 78.19%→83.55%。正向配对区间跨零，固定 DEV 沿用。
- 两条配对最终均未选证据并集或交集。M1 七处改变中，一处权利题相对匹配臂从未决到正确。两处用途证据退化分别涉及复合条款下的附带义务，以及返还标题和终止后义务。旧 B5–B8 结果用于开发诊断。 [GitHub 已发布断点](https://github.com/H00RU/LegalSkillGuard/commit/826758c6d51fc34f9bc408c045958afc3ef33369)

## Revision 6 第三方取得证据链的前一断点

阶段 `revision6_cni_independent_receipt_release_settled`。评估会话 22305 已退出，发布回执 `artifacts/legal_skill_convergence_20261117/handoff/revision6_cni_independent_receipt_release_terminal_20261120.json`，绑定 `a48685d17a07cc7db4b4080d243739ed889938ebb8b926cb7a84affaa7cb07ae`。7 项测试通过，核对 25 笔 TRAIN、6 笔 DEV 的改动相关物理请求，新增 0，账本 15,180 笔，在途 0。 [来源规则与五库累计分数](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_INDEPENDENT_RECEIPT_AND_FIXED_DEV_20261120.json)

- `cni_independent_receipt.py` 把合法第三方取得连到治理的保密定义或例外，保留已引用的独立取得授权。15 份 TRAIN、3 份固定 DEV 证据覆盖，分类与原参考均一致；有一份原参考引用此前知悉，核验规则保留实际取得项的证据。四内部臂取得题固定 DEV 证据 F1 为 15.63%→33.13%，PARSE 13.54%→26.88%，分类各 13/16。累计 272 项证据 F1 为 54.24% 和 46.23%。
- `convergence_revision6_cni_independent_receipt_release.py` 的回放入口在原五臂 16 份合同上逐项复现封存输出。三路原 TRAIN 实测复用同一核对，取得题合成、固定、直接分别由 4→9、8→9、3→10，分母各 12，正确类证据 F1 最终为 69.76%、61.43%、81.67%。改进归于共用来源规则，当前没有 M1 扩验任务。M2 继续保留组合选组及同预算强对照回执。

## Revision 6 分类与估值组合选组的前一断点

阶段 `revision6_oe_portfolio_settled`。会话 14198 已退出。回执 `artifacts/legal_skill_convergence_20261117/handoff/revision6_oe_portfolio_terminal_20261120.json`，绑定 `0fe1674655609ca2625219174b7b02bae0f218356fb71a601fe9912fb610f7d5`。11 项定向检查通过，复核 144 笔归档请求，新增 0，账本 15,180 笔，在途 0。 [多提案分任务选组](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_PORTFOLIO_TRAIN_20261120.json)

- `convergence_oe_portfolio.py` 允许把分类和估值分别绑定到两到三个真实读器。B3、B4、B6、B7 共核查四个原前向 TRAIN 过渡。每个选组策略筛两组，分别使用 8 或 12 笔归档读数。门槛对每个替换任务要求原文支持的修正，并对实际组合检查新增冲突。入库快照按批次、策略、任务封存。
- 候选驱动、按时间和按答案分歧均只在 B7 采纳普通提案的估值，前向 16 份的分类和估值 F1 同为 64.98%、53.73%。只按原生拟合为 58.47%、49.82%，两项平均差 +5.21 个百分点，95% 配对区间 [+1.27, +10.10]。进入风险选组从未更换任务，和不更新同为 64.98%、52.86%。候选驱动对其平均差 +0.43 个百分点，区间 [−1.03, +2.10]。该结果给出共同筛查门槛的收益证据，候选驱动与按时间和答案分歧逐项同判，固定 DEV 沿用。后续仅在出现可区别同预算选组且可能向原有新母来源迁移的真实提案时扩展此路径。

## Revision 6 第三方转移证据的前一断点

阶段 `revision6_cni_transfer_witnesses_settled`。会话 18922 已正常退出。回执 `artifacts/legal_skill_convergence_20261117/handoff/revision6_cni_transfer_witnesses_terminal_20261120.json`，绑定 `be9f5142a3198d1bc807c9219921b510c79215d935830c0ed6047a5f5c80290b`。6 项测试通过，新增执行器 36 笔，教师 0，连续账本 15,180 笔，在途 0。 [配对结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_TRANSFER_WITNESSES_TRAIN_20261120.json)

- `cni_transfer_witnesses.py` 移除示例编号，联动改为四个方向和模态的证据位置。实际比较沿用全部 12 份 B5–B8 原 TRAIN。合成、固定、直接正确数 7/24、15/24、6/24，正确类证据 F1 为 23.21%、20.10%、20.63%。两条归档读器各 18/24。新实验改动同时发生，无法分别归因。
- 合成的外部披露许可 0/12，限制 12/12，导致披露题全部预测为矛盾。固定读器定位披露许可 10/12，独立取得许可 9/12。原读数均成功解码，原始分类在 `post_settlement_witness_counts.json`。两条同信息证据差的配对区间均含零。定向证据布局未过扩验门槛，后续仅在出现可消解许可漏判的新证据时重启这一问题。M2 沿用多提案选组完成态。

## Revision 6 信息转移方向的前一断点

阶段 `revision6_cni_directed_transfer_settled`。会话 45535 已正常退出。回执 `artifacts/legal_skill_convergence_20261117/handoff/revision6_cni_directed_transfer_terminal_20261120.json`，绑定 `7158a4a5ed09759fa427cab987068fa9c9a0e0da95f86f79f207307cda30e9e6`。5 项定向测试通过，36 笔 Qwen 请求结算，教师 0，连续账本 15,144 笔，在途 0。 [同信息三路实测](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_DIRECTED_TRANSFER_TRAIN_20261120.json)

- `cni_directed_transfer.py` 从发送、接收和对手方身份生成两个方向关系，并核对 27 个状态的消费等价。三条读法共用三份 B1–B4 原 TRAIN 范例及 B5–B8 全部 12 份原 TRAIN。合成、固定、直接分别正确 1/24、3/24、12/24，原归档普通与 PARSE 各 18/24。合成相对当前直接读法的正确类证据 F1 差是 −22.37 个百分点，配对区间 [−36.81, −10.22]。
- 24 笔结构化读数均成功解码。固定的 116 条转移全标为无有效规则。合成的 84 条一半同样标记，一半模态未决，其中 52 条锚点与六个例子编号重合。直接读法的 12 条取得题全答未提及。回执同目录的 `post_settlement_raw_force_diagnostic.json` 记录原始计数。例子编号出现在新合同锚点中是后续可辨别的提示缺陷，尚未证明因果。若继续这一结构，先消除编号碰撞并明确两路模态代码再锁定新比较，保留两个归档读器作基准。固定 DEV 未扩验。

## Revision 6 MAUD 选择性引用的前一断点

阶段 `revision6_maud_selective_import_settled`。离线会话 16802 已退出，回执 `artifacts/legal_skill_convergence_20261117/handoff/revision6_maud_selective_import_terminal_20261120.json`，绑定 `253298965a1fbcc10e4bd867f0ad6e56ef89c6b1692864b42fc927666c55cf32`。17 项定向测试通过，新增请求 0，账本 15,108 笔，在途 0。 [选择性引用与固定 DEV](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_MAUD_SELECTIVE_IMPORT_TRAIN_AND_FIXED_DEV_20261120.json)

- `maud_selective_import.py` 在同一合同的两个原始节选之间绑定可唯一匹配的前导段，并解析明确的逐项引用与连续编号范围。B6 第三份原 TRAIN 的负面前导不引入普通经营的疫情例外。合成和固定均引用被排除的前导例外，直接引用后续独立举债条目。保留原标签与三臂响应。条款级排除无法据此回答整项负面契约问题。
- 固定 DEV 一份有可逆逐字核对的共同前导和编号范围，疫情条件在引用范围内。五臂均已判为 Yes，无输出变化，负面契约各 13/16。验证 3 笔 TRAIN、2 笔 DEV 的原始物理响应。当前不扩大该读法，后续应找有覆盖且同信息强对照仍有可证缺口的关系。M2 沿用上一阶段已结算比较。

## Revision 6 多提案反证选组的前一断点

阶段 `revision6_oe_candidate_group_settled`。离线会话 74766 已退出，回执 `artifacts/legal_skill_convergence_20261117/handoff/revision6_oe_candidate_group_terminal_20261120.json`，绑定 `ea2eeeea9db02661cb57cdad86616bd7353a2c77d52e3009c0c4841015d3ddbe`。9 项定向测试通过，新增请求 0，连续账本 15,108 笔，在途 0。 [同预算双提案选组](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_CANDIDATE_GROUP_TRAIN_20261120.json)

- `convergence_revision6_oe_candidate_group.py` 核实 B4→B5 和 B7→B8 的进入读器、普通提案和 PARSE 提案，比较 16 份原 TRAIN 母来源。核对 120 笔归档请求，包括 32 笔可逆布局原请求。两批对照均使用原请求、同一来源规则和统一入库门槛，每个选组选定一组六笔，另保留纯原生拟合。已封存每个策略的所选读器。
- B4 两项提案原生拟合均为负，五策略均保留进入程序。B7 优先反证的策略选第二组，核对出普通提案新增两处跨任务冲突，保留进入读器。按时间选末组并采纳普通提案。按答案分歧和进入风险都选第三组，也保留进入程序。八份下一批 TRAIN 的分类与估值 F1 分别为候选驱动 63.54% 和 65.12%，按时间及原生拟合 56.15% 和 66.85%。两项均值的配对差区间 [−1.25, +8.71] 个百分点。结果来自事后比较，两个同预算强对照逐预测相同，未派发 DEV。恢复后沿用该回放，不重复比较同一候选组。

## Revision 6 用途证据范围的前一断点

阶段 `revision6_cni_purpose_support_dev_settled`。会话 42381 已退出，回执 `artifacts/legal_skill_convergence_20261117/handoff/revision6_cni_purpose_support_dev_terminal_20261120.json`。5 项定向测试通过，新增请求 0，连续账本 15,108 笔，在途 0。 [用途证据范围与固定 DEV](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_PURPOSE_SUPPORT_TRAIN_AND_FIXED_DEV_20261120.json)

- `cni_purpose_support.py` 从已引用的完整用途限制出发，识别标题、当事人介绍、信息介质和其他披露义务。保留已经核实的跨条款链和独立法律效果。24 份 TRAIN 的 72 笔索引实测中，合成不变，固定和直接各改善一份，零退化。七份单题比较中，M1 的用途题正确类证据 F1 为 69.32%→73.13%，同条件匹配对照为 85.71%→90.48%。该收益来自共用证据规则。
- 原固定 DEV 全部 16 份、五臂均未触发删除，累计原生指标沿用。后续无需重复本轮规则或原单题读法。合同 M1 仍需能补全真实未解关系的接口，M2 仍需能区别同信息且含按原生分数选型的对照。MAUD B4 两个候选的当批表面分类收益均来自同一归档进入请求的长度截断，论文此前已有等信息传输修复，未据此派发 M2。

## Revision 6 单题标签的前一断点

阶段 `revision6_cni_projected_direct_settled`。首轮会话 66467 和补测会话 26241 均已退出。补测回执 `artifacts/legal_skill_convergence_20261117/handoff/revision6_cni_projected_direct_terminal_20261120.json`，绑定 `eb2d7f9bf536ecae9cb7fa588d0b7c5b8f67c32c066b8c2e6fcd4e348ff6a072`。两个相关测试通过。账本 15,072 笔完成、37 笔历史失败、0 笔在途。 [标签澄清与强对照](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_PROJECTED_DIRECT_TRAIN_20261120.json)

- `cni_projected_reader.py` 和实验入口 `convergence_revision6_cni_projected_read.py` 在 B5–B8 的七份仅一题待解的合同上沿用锁定的选读器策略。直接读法首轮有六处相反标签，`convergence_revision6_cni_projected_direct.py` 仅改写直接读法中的标签说明，全文、已证明任务、输出 schema 和模型保持一致。先后新增 14 笔和 7 笔，复用了全部适用的合成、固定及归档双题读数。 [首轮诊断](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_PROJECTED_READ_TRAIN_20261120.json)
- 澄清后，M1、匹配对照、直接单题、归档直接双题在待解题上分别答对 7/7、7/7、5/7、7/7。按全部 14 题计算，正确类证据 F1 分别为 78.71%、86.90%、72.62%、83.33%。M1 对匹配对照和归档双题的待解题证据 F1 差均为负，配对区间均跨零，固定 DEV 沿用。恢复时先核对最新状态和连续账本，只有发现原 TRAIN 支持的新缺口才启动下一比较。M2 下一比较需能区分候选驱动与同预算、同信息的直接及按原生表现选型对照。

## Revision 6 按待解任务选读器的前一断点

阶段 `revision6_cni_residual_routing_settled`。离线会话 28188 已退出，回执 `artifacts/legal_skill_convergence_20261117/handoff/revision6_cni_residual_routing_terminal_20261120.json`，绑定 `e03715e920e5964d92f13365bac675e2b332fa3215b28d1807bae7de10e1dd5f`。14 项测试通过。沿用 72 笔同信息归档，新增 0，账本 15,087 笔，在途 0。 [任务级选型与原生前向结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_RESIDUAL_ROUTING_TRAIN_20261120.json)

- `cni_residual_routing.py` 分别估计每个读器在没有源文证明的任务上的分类和正确类证据 F1。每份合同最多选一次完整读法。来自明确前导或唯一非授予条款的证明对所有对照共用。B1–B4 拟合后，B5–B8 12 份合同的 24 项中 11 项共用证明、13 项依赖读器。两份无需读器是回放中的逻辑预算记录。所有采纳的原文证明均与原参考一致，另保留 B2 广泛用途匹配与原标签的一份分歧。
- M1、同任务选型的固定加直接、直接读器分别为 23/24、22/24、23/24，正确类证据 F1 是 79.73%、75.00%、76.81%；旧 M1 路由共用同一证明后为 75.84%。强对照的差区间均跨零，未启动固定 DEV 扩验。后续只比较有新来源或响应证据支持的机制，唯一任务或同时已证明的作用域继续按本轮规则区分。

## Revision 6 员工披露证据链的前一断点

阶段 `revision6_cni_recipient_evidence_settled`。会话 5848 已退出，回执 `artifacts/legal_skill_convergence_20261117/handoff/revision6_cni_recipient_evidence_terminal_20261120.json`，绑定 `55bc87f747bdc11105fed8b1795d16e166fdee238a0afe7014c652c3457942e7`。15 项测试通过。复用三路单题配对 15 笔并核验固定 DEV 4 笔。连续账本 15,087 笔，新增 0，在途 0。 [证据链及累计五库结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_RECIPIENT_EVIDENCE_AND_FIXED_DEV_20261120.json)

- `cni_recipient_evidence.py` 在已有肯定读数引用唯一许可证据时，补完整编号前导和所引用的成员定义。事前批准的要求按具体动作和受领人区分。未改分类、原引文或读器输出。原 TRAIN 覆盖 2/24，固定 DEV 覆盖 5/16，五臂均修正两份引文、零退化。固定 DEV 员工披露证据 F1 四内部臂 61.27%→65.15%，PARSE 49.36%→52.50%。累计 ContractNLI 证据 F1 分别为 53.21% 和 45.45%。
- 在五份单题同信息配对上，M1 和直接读器分类均为 5/5，证据 F1 分别由 52.10% 到 67.33%、72.00% 到 80.00%。M1 减直接的差为 −12.67 个百分点，95% 配对区间 [−25.67, +10.67]。固定字段的 0/5 分类保持。此次证据补全归于共用规则，M1 仍需可区别同信息直接读器的原生收益。当前没有在跑的任务。

## Revision 6 B4 角色组选组的前一断点

阶段 `revision6_cni_b4_recipient_selection_settled`。会话 17562 已正常退出，回执 `artifacts/legal_skill_convergence_20261117/handoff/revision6_cni_b4_recipient_selection_terminal_20261120.json`，绑定 `8f7f68c90f3437feff628b833403c8c6c14810762bf9ad0e04d172b365223d38`。新增 Qwen3-8B thinking OFF 3 笔、33,899 tokens，复用 27 笔原响应。12 项测试和 2 项子测试通过。账本完成 15,051、历史失败 37、在途 0。 [同预算选组与前向评分](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_B4_RECIPIENT_SELECTION_TRAIN_20261120.json)

- `convergence_revision6_cni_b4_recipient_selection.py` 从 B1–B4 的 12 份原 TRAIN 实测和原文完整角色组选择 B4 真实更新。候选驱动选 B2 第一组并采纳。按时间和回答分歧均选 B4 第三组并保留进入读器。各用同一组池、两笔筛选读数，直接、共享和独立补全筛选同判。纯原生拟合对照也采纳。
- B5 原三份合同复用已采纳程序原响应，只补精确缺失的 B3 进入程序。两路原文、输出契约和预算一致。四路都是 5/6。正确类证据 F1 候选驱动和仅按原生拟合为 55.56%，按时间与答案分歧为 30.56%，配对 95% 区间 [−25.00, +100.00] 个百分点。所有路在同一份合同的第三方披露题失分，合同分别写明受控关联方授权和一般第三方禁令。现有源证明未确定二者的分类边界，保留各自的原生判断。没有触发固定 DEV 扩验或待恢复运行。

## Revision 6 伊利诺伊误引的前一断点

阶段 `revision6_oe_illinois_eligibility_settled`。会话 8621 已退出，回执 `artifacts/legal_skill_convergence_20261117/handoff/revision6_oe_illinois_eligibility_terminal_20261120.json`，绑定 `dec0579d16ec13cc267ca62b7c4f75d0a45abb78b49550d7fa4491773ac9ab01`。14 项相关检查通过，复用 16 笔 B5 和 3 笔固定 DEV，新增 0。账本 15,084 笔，在途 0。 [固定 DEV 与 B5 同信息分解](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_ILLINOIS_ELIGIBILITY_AND_FIXED_DEV_20261120.json)

- `convergence_oe_illinois_eligibility.py` 核验 §12-1001 的父节没有独立授予，按同一公共法条和明确资产类型剔除不适用的分项。原 TRAIN 和固定 DEV 在每项任务分别覆盖 45、10 个资产与引文位置，均与原参考相容。
- B5 最早组净删 7 项分类误引，另删 3 项估值误引并新增 1 项估值误引。所有这些差异均属所核范围。共用后该组进入程序与候选两项 F1 同分。候选驱动与按时间仍同选并保留进入程序；无 B5 前向补读。固定 DEV 的四个内部臂为分类 80.74%、估值 74.85%，PARSE 为 79.27%、72.31%。收益来自共用规则，其他四库结果沿用。

## Revision 6 MAUD 相邻款的前一断点

阶段 `revision6_maud_branch_preamble_settled`。会话 67742 已退出，回执 `artifacts/legal_skill_convergence_20261117/handoff/revision6_maud_branch_preamble_terminal_20261120.json`，绑定 `53ddbc9030af3bd22386cac671ee0336528998fe47cc0d482c7a5cfd5a800dad`。复用 27 笔 MAUD TRAIN 响应，18 项相关测试通过。连续账本 15,084 笔，在途 0。 [支配范围与三臂评分](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_MAUD_BRANCH_PREAMBLE_TRAIN_20261120.json)

- `maud_branch_preamble.py` 要求版本化摘录显示款的顺序、自己的例外前导和主义务。在后款有明确导入、前导中间缺失或自身出现疫情线索时保留未决。原 24 份中 3 份满足。已测后四批两份适用，三臂每臂修正 2 项，结果为 14/18、13/18、12/18。合成相对固定的配对区间为 [0, +16.67]，相对直接为 [0, +27.78] 个百分点。原固定 DEV 覆盖 0/16。
- 残余正向差异来自普通经营任务，负面契约三臂均为 6/9。贷款修改和网点临时关闭的单项例外沿用已归档的标注口径敏感性结果。下一次合同改动需要独立可核实的原文机制区别同信息强对照，避免重测已知的前导条件或单项语义分歧。当前没有待恢复的运行。

## Revision 6 的 M2 前一断点

阶段 `revision6_oe_missing_forward_fit_settled`。会话 42759 已退出，回执 `artifacts/legal_skill_convergence_20261117/handoff/revision6_oe_missing_forward_fit_terminal_20261120.json`，绑定 `82dafee8c56ba792877174ab4666278628e9e8ca31af093c2c25ce1d160f2462`。复用 B2 与 B5 合计 32 笔 EC、EV 原响应。连续账本 15,084 笔，在途 0。 [两批当批筛选与方法对照](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_MISSING_FORWARD_FIT_TRAIN_20261120.json)

- `convergence_revision6_oe_missing_forward_fit.py` 核对原候选程序与两路输出的收据，再执行原同信息采纳门槛。B2 有四个完整组。估值 F1 的 +25.00 个百分点全部来自最新组，该组没有通过源约束筛选的修正。B5 有三个完整组，分类和估值候选的当批 F1 各低 9.19、28.82 个百分点。候选驱动和按时间在两批均选最新组并保留原程序。四种筛选策略与仅按原生分数的对照已分别存档。没有待恢复的运行或已获证据支持的 B2/B5 前向补读。
- 现有前向库的 B3 分类与 B4 估值在当批分数为正，在下一批转负。B7 估值保留原小幅收益，候选驱动与按时间采用同一程序。后续选择机制需要找到能导致两路采纳不同的可验证 TRAIN 修正，再使用独立母来源验证。不由已经定位的共用法规修复推断选组效应。

## Revision 6 非授予核验的前一断点

阶段 `revision6_cni_rights_scope_settled`。离线会话 43227 已退出，回执 `artifacts/legal_skill_convergence_20261117/handoff/revision6_cni_rights_scope_terminal_20261120.json`，绑定 `265f9a0b288ab5ee1715b4080932381737b685e090980f172abf0616c1fdf985`。22 项相关测试通过。原始请求复用 17 笔混合 TRAIN、72 笔原分路 TRAIN 和 2 笔覆盖固定 DEV 的请求。新增 0，账本 15,084 笔，在途 0。 [共用非授予核验与前向结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_RIGHTS_SCOPE_TRAIN_AND_FIXED_DEV_20261120.json)

- `cni_rights_scope.py` 从正文核验非授予及受保护对象，标题仅作为指向正文的索引。保留与真实授予相冲突的读数。混合 TRAIN 两臂各修正 2 项权利判断，归档直接的分类不变，补全 1 项标题引文。两任务总分类为 22/24、22/24、23/24，正确类证据 F1 为 76.11%、73.61%、74.03%。证据差对匹配和归档直接的区间分别为 [0, +7.50] 和 [−5.56, +13.19] 个百分点。修正归于共用核验。
- 权利题固定 DEV 的 16 份中有 1 份匹配条款，五臂各保持 9/16，证据 F1 内部臂 35.12%、PARSE 35.57%。五库累计沿用。前向仍有未解决的选择性产权条款和模板选项。只在找到超出已测非授予核验的可复现作用域依据后继续该路径。

## Revision 6 合同读器的前一断点

阶段 `revision6_cni_mixed_routing_settled`。会话 4472 已正常退出，17 笔新冻结执行器请求全部完成，17 项相关检查通过。回执 `artifacts/legal_skill_convergence_20261117/handoff/revision6_cni_mixed_routing_terminal_20261120.json`，绑定 `9f7efeaada623d8a3ddfc020851fc493857128a2e7e01861bdf6d4473969aa79`。账本完成 15,048 笔、历史失败 36 笔、在途 0。 [单次读取双任务](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_MIXED_ROUTING_TRAIN_20261120.json)

- `cni_mixed_indexed_reader.py` 在同一份完整合同的一次读取中按任务执行读器。M1 在五份没有原文规则直接证明的合同上对用途任务采用合成接口，匹配对照采用直接读法。权利任务两臂使用拟合得到的同一固定字段。其余七份合同的请求完全相同，共用响应。改动过的请求取得实测响应后才评分。
- B5–B8 的 24 项分类，M1、匹配对照、归档直接各为 20、20、23。用途题三路均为 12/12。权利题两条新路径各为 8/12，归档直接为 11/12。正确类证据 F1 各为 68.61%、66.11%、70.69%，M1 对匹配差 +2.50 个百分点，配对区间 [0, +7.50]。候选未过扩验门槛，固定 DEV 沿用。
- 前一阶段 `revision6_cni_forward_routing_settled`，会话 12734 复用 72 笔归档读数。按合同只选一路的 M1、匹配对照、归档直接答对 23/24、22/24、23/24，正确类证据 F1 为 71.62%、68.97%、70.69%。两项对比的配对区间均跨零。续接时保留这两次前向证据。M1 继续推进须有可区分强对照的源文机制，M2 继续推进须有能区别同信息按时间选组的新提案。当前没有待恢复的运行。 [按合同选择](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_FORWARD_ROUTING_TRAIN_20261120.json)

## Revision 6 M2 采纳门槛的前一断点

阶段 `revision6_oe_residual_acquisition_settled`。离线会话 4318 已结算，回执 `handoff/revision6_oe_residual_acquisition_terminal_20261120.json`。归档 EC 与 EV 各 56 笔，新增 0，31 项检查通过。账本 15,067 笔，在途 0。 [TRAIN 采纳与前向结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_RESIDUAL_ACQUISITION_TRAIN_20261120.json)

- `convergence_revision6_oe_residual_acquisition.py` 在相同原 TRAIN 原生标签、任务组合和单组四响应预算下，比较原门槛、共用规则后的原生门槛，以及再对共用规则后输出核验修正的门槛。比较用当前锁定的公开规则回放原批次，选组和采纳只使用当批结果。原门槛的 16 份前向预测与已封存结果相同，核对时仅忽略同一资产下的声明顺序。
- B6 只换分类的 TRAIN 平均增量由 +0.69 变为 −2.46 个百分点。校正后不换分类，仍保留 B7 估值更新。候选驱动和按时间在 16 份原前向 TRAIN 均为分类 F1 62.80%、估值 F1 51.65%，旧门槛为 61.78%、51.65%。相对不更新的平均差 +0.43 个百分点，配对区间 [−1.03, +2.10]。相对共用规则后只按原生 TRAIN 选路线的差为 +6.64，区间 [+2.57, +11.45]。两种新门槛同判，强按时间对照复现全部采纳决定。
- 保留五库固定 DEV 与原冻结 TEST。继续时直接复用这四次过渡，选组模块仍需能与同信息按时间对照作出不同采纳决定、且有后批原生收益的实际提案。

## Revision 6 Airline 巴拿马线路的前一断点

阶段 `revision6_airline_panama_settled`，离线会话 14109 已结算。回执 `handoff/revision6_airline_panama_terminal_20261120.json`。借助 24 份原 TRAIN 行李清单做 288 个双方向、六舱位规则核对，公开表格编译、穷举分配及封存基准算法逐项同价。用原 B8 DEV 的 16 份来源回放，覆盖曾未支持的一份巴拿马至美国线路，五臂总费用各 15/16→16/16，修正 1、退化 0。复用一笔物理响应，新增 0。31 项相关检查通过。 [线路结果及五库累计表](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_AIRLINE_PANAMA_AND_FIXED_DEV_20261120.json)

- `convergence_revision6_airline_panama.py` 读取原费率表中的巴拿马分支、免费额度及重量和尺寸规则。对照从封存基准加载原算法，用标准库读取同一套 CSV。288 个核对是规则改写，固定 DEV 仍为原 16 份。该改进对五臂共有，无新增独立机制证据。
- 前一阶段 `revision6_copy_evidence_closure_settled`，会话 27406 使用 33 笔归档响应，新增 0，26 项检查通过。`cni_copy_evidence_graph.py` 只改实际引到唯一、可独立核验的制作动作的引文。11 份原 TRAIN 中九份有证据链，合成、固定、直接各改 6、4、1 个引文。正确类证据 F1 为 65.28%、60.89%、73.23%。合成相对固定差 +4.38 个百分点，相对直接差 −7.95，两组配对区间含零。固定 DEV 一份有规则适用链，五臂引文均原样保留。 [制作证据链回放](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_COPY_EVIDENCE_CLOSURE_TRAIN_20261120.json)
- 账本累计 15,067 笔，完成 15,031、历史失败 36、在途 0。续接时保留 Airline 原 B8 DEV 公共规则和 CNI 三臂证据。M1 的新比较须有不同的作用域错误或关系表示，M2 仍需能区别同信息按时间选组的真实提案。当前没有待恢复的运行。

## Revision 6 副本制作与处置后留存的前一断点

阶段 `revision6_copy_disposition_readback_settled`，会话 93780 完成 33 笔执行器响应、194,553 tokens、零传输错误。回放会话 31322 复用全部响应，新增 0。账本完成 15,031 笔、历史失败 36 笔、在途 0，23 项检查通过。回执 `handoff/revision6_copy_lifecycle_terminal_20261120.json` 和 `handoff/revision6_copy_disposition_readback_terminal_20261120.json`。 [三臂实测](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_COPY_LIFECYCLE_TRAIN_20261120.json) · [全量处置回放](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_COPY_DISPOSITION_READBACK_TRAIN_20261120.json)

- `cni_copy_lifecycle.py` 将制作、留存各自的权限和禁止绑定到实际条款，跨条款引用须保留原始索引，留存额外要求处置后的时点。两类消费者在 27 和 81 个声明状态上分别等价。B5–B8 同时命中两类原文提示的 11 份母合同全部进入比较。原三路分类为合成 11/22、固定 8/22、直接 2/22。应用同一套旧原文规则后为 12/22、11/22、13/22，合成相对直接的正确类证据 F1 差 −21.49 个百分点，95% 区间 [−34.02, −8.46]。
- 三路存在将可选销毁方式或披露方保有介质所有权当作留存许可的错误。`cni_disposition_closure.py` 核对全量返还和已知留存例外后，四份原 TRAIN 支持共同的处置结论。三臂分别再修正 4 项，退化 0。最终合成、固定、直接为 16/22、15/22、17/22，正确类证据 F1 为 49.47%、51.20%、70.96%。固定 DEV 仅用公开源文检查，覆盖 0/16。该候选的 B8 TRAIN 快照 `active=null`，五库累计 DEV 沿用。
- 续接复用上述两组读数。制作与留存组合版本已经比较，同一布局无需重复派发。若继续这一结构，下一条可检验差异需要来自能正确绑定当事人、动作及时点且减少无关引文的关系表示。M2 仍需能区别同信息按时间选组并转移到后批的实际提案。

## Revision 6 OpenExempt 分任务采纳的前一断点

阶段 `revision6_oe_port_acquisition_settled`，回执 `handoff/revision6_oe_port_acquisition_terminal_20261120.json`。三个离线会话 31625、20797、13552 已结算。复用 56 笔分类和 56 笔估值物理响应，新增请求 0，35 项检查通过。连续账本 15,034 笔、在途 0。 [联合选组](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_JOINT_ACQUISITION_TRAIN_20261120.json) · [类别核查](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_ITEM_VALIDATED_ACQUISITION_TRAIN_20261120.json) · [分任务采纳](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_PORT_ACQUISITION_TRAIN_20261120.json)

- `convergence_oe_joint_acquisition.py` 比较四种技能组合。每种策略每批筛同一份预算的一组，包含两程序各一笔分类、一笔估值。共享枚举与同信息直接核对逐项同判。B6 的一个分类与估值冲突随正额估值消失，记为未核验消失。B7 另有两项把洗碗机和路由器加入服装分类的输出一致，精确法条与原文识别判为分类错误。
- `convergence_oe_pa_item_forms.py` 对原文可确定的物品和精确法条过滤错误的服装与缝纫机主张。类别核查后，B7 只有估值获得可验证修正。分任务门槛将候选驱动和按时间的 B7 都改为只采纳估值，并保留原分类。B8 四份原 TRAIN 分类 F1 同为 60.42%，估值 F1 由 51.07% 到 54.52%。
- 四次过渡合计 16 份原前向 TRAIN。候选驱动和按时间均为分类 F1 61.78%、估值 F1 51.65%。答案分歧、进入程序风险及不更新都是 62.80%、50.78%，平均差 −0.08 个百分点，配对区间 [−2.15, +2.08]。只按 TRAIN 分数选路线为 54.13%、51.65%，分任务门槛使两任务平均分相对该对照高 3.83 个百分点，配对区间 [+0.89, +7.47]。分任务收益支持约束采纳范围，当前选组未区别于按时间。新类别规则固定 DEV 覆盖 0/16。固定 DEV 五库结果沿用。
- 接续时直接复用同一组档案。M2 候选驱动仍需真实提案使同信息、同预算强对照作出不同采纳决定，且这种差异在后续母来源有原生收益。优先寻找上述条件成立的其他提案，或继续 M1 的可归因改动。

## Revision 6 MAUD 条款锚点与分款回放的前一断点

阶段 `revision6_maud_subsection_readback_settled`。会话 2186 的 27 笔模型响应全部结算，125,303 tokens，零传输错误。随后回放复用全部 27 笔，新增 0。连续账本完成 14,998 笔、历史失败 36 笔、在途 0，27 项检查通过。回执 `handoff/revision6_maud_covenant_anchors_terminal_20261120.json` 和 `handoff/revision6_maud_subsection_readback_terminal_20261120.json`。 [三臂配对](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_MAUD_CLAUSE_ANCHORS_TRAIN_20261120.json) · [同信息回放](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_MAUD_SUBSECTION_READBACK_TRAIN_20261120.json)

- `maud_covenant_anchors.py` 为真实义务列出原文位置。合成用同一组锚点解码两类契约，固定读器各填一个锚点，直接读器给原生答案。三臂的锚点、节选与执行预算一致。试验覆盖 B5–B8 全部 9 份符合原文条件的 TRAIN。合成 11/18，固定 10/18，直接 9/18，两组配对区间下界均为零。
- B3 联合读器将明确点名 4.1(a) 的例外归给负面契约。本次 B8 的同类写法被三个读器扩张到负面契约。`maud_subsection_proviso.py` 在原 24 份 TRAIN 找到这两例，在固定 DEV 0/16。回放同一规则后三臂各修 1 题，方法间差值不变。合成的负面契约结果为 4/9，普通经营 8/9，固定 5/9、6/9，直接 4/9、6/9。本版本保留为 TRAIN 证据。
- 接续时复用目前两组 MAUD 范围读数，寻找可验证的条款归属差异与前向覆盖；只在有新的读者或规则能实质改变这类错误时扩验。M2 继续以可区别按时间和同信息强对照、并有后续原生读数的实际提案为依据。

## Revision 6 OpenExempt 逐批前向选组的前一断点

阶段 `revision6_oe_forward_acquisition_settled`，回执 `handoff/revision6_oe_forward_acquisition_terminal_20261120.json`。账本 15,007 笔、在途 0，92 项检查通过。 [四次前向与五库累计结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_FORWARD_ACQUISITION_TRAIN_20261120.json)

- `convergence_oe_bound_acquisition.py` 区分同一主张上的明示额度修正与原错误主张消失。四种策略共用原组池、同一提案和原生评估门槛，每次筛一组、两笔已有物理估值读数。额度使用当批公开事实和保守的联邦单项上限，未把后批校准回填到旧批次。
- `convergence_revision6_oe_forward_acquisition.py` 核对原 B3、B4、B6、B7 的拟合和下一批实际请求，源文、传输配置和输出语法一致，差异限于程序。64 次归档引用对应 56 笔独立响应。B2、B5 缺少配对的原下一批程序读数。前向一份提案没有主路径 EV 输出，按零计入原分母。
- B7 候选驱动和按时间均选 B7-3、采纳提案。答案分歧和进入程序风险在 B7-2 看到多项原错误消失，但无明示修复且提案仍有额度冲突，保留原程序。其余三批四策略采纳决定一致。统一额度过滤后，16 个前向母来源上两组分别为 24.79% 和 23.85%，差 +0.94 个百分点，配对区间 −1.98 至 +4.27。按时间复现候选驱动四次采纳决定。
- B4 有一项超过原文 680 美元的 700 美元预测仍处于官方估值容差，删除会降原生 F1。保留原生和统一过滤两组评分，固定 DEV 沿用上轮。本组不需要重跑，下一项需真实提案能区别于按时间选组并在独立母来源保持收益。

## Revision 6 联邦单项额度与前向估值的前一断点

阶段 `revision6_oe_joint_item_cap_settled`，回执 `handoff/revision6_oe_joint_item_cap_terminal_20261120.json`。账本完成 14,971 笔、历史失败 36 笔、在途 0，90 项检查通过。 [等预算选组、训练前向与五库累计指标](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_JOINT_ITEM_CAP_AND_FIXED_DEV_20261120.json)

- `convergence_oe_federal_item_cap.py` 限于题面逐资产逐法条估值、联邦法条和财产类型可确认、产权明确的范围。B7 两个可区分共同申报口径的原生金额均使用每项 700 美元，按申报人数叠加匹配 0 次。校准按 OpenExempt 原题评分口径。
- `convergence_revision6_oe_joint_item_cap.py` 在同一 B7 组池和每策略两笔真实读数下，候选驱动、答案分歧与按时间均选择 B7-3 并持久化同一提案。提案把家具由 800 改为 700。B8 唯一高值资产上，进入程序漏报、提案报 980，参考是 700。整程序 B8 前向 F1 为 43.75% 对 47.50%，三种选组同结果。组内共享与同信息直接筛选同判。本片段无需再次派发。
- 同一校准规则只改已有的超额估值。固定 DEV 4 个适用金额均匹配参考，三份实际修正。内部四臂 EV F1 72.82%→74.50%、平均相对误差 0.0400→0.0193。PARSE EV F1 70.58%→72.31%。五臂各 0 退化。复用归档 TRAIN 32 笔及适用 DEV 6 笔，新增 0。

## Revision 6 同信息引文对照的前一断点

阶段 `revision6_indexed_evidence_control_settled`，回执 `handoff/revision6_indexed_evidence_control_terminal_20261120.json`。账本完成 14,971 笔、历史失败 36 笔、在途 0。88 项检查通过。 [用途限制对照与五库既有 DEV](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_INDEXED_EVIDENCE_CONTROL_AND_FIXED_DEV_20261120.json)

- `cni_purpose_citations.py` 只在已引用一条自足的用途限制时排除可确认的定义性、保密披露、编号或通知引文。保留所引用的另一项限用途许可和跨条款来源。本版保留全部原生分类。
- `convergence_revision6_indexed_evidence_control.py` 逐笔复用原 72 笔实测并把同一规则给三路。固定分栏 2 份、直接 3 份改善，合成 0 次改写，均无退化。三路正确类证据 F1 分别为 70.70%（合成）、56.12%（固定分栏）、61.94%（直接）。确认组内合成对直接由 +6.65 缩为 +1.15 个百分点，配对区间 −11.54 至 +14.62。
- 原 B5-2 条件只覆盖所述自行受益用途，源审并记录两种合同模式未选定和适用方未决，缺少把该句普遍扩展到全部非约定用途的原文依据。该差异计入原生分类，保留现行原文规则，不基于此例改变默认分类。
- 固定 B8 DEV 16 份沿用现行五臂输出。合成接口未派发 DEV。后续需有超出共用引文清理并区别于同信息直接读者的实际机制，避免重跑这两组 TRAIN。

## Revision 6 同条款索引确认的前一断点

阶段 `revision6_indexed_effects_confirmation_settled`。回执 `handoff/revision6_indexed_effects_confirmation_terminal_20261120.json`。首组会话 `22134` 和确认组会话 `13589` 均结束。连续账本完成 14,971 笔、历史失败 36 笔、在途 0。 [首组 TRAIN 封存结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_INDEXED_EFFECTS_TRAIN_20261120.json) · [确认组 TRAIN 与五库既有 DEV](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_INDEXED_EFFECTS_CONFIRMATION_TRAIN_20261120.json)

- `cni_indexed_effects.py` 以同一条款索引绑定法律动作与受保护对象，校验 9 种局部状态的消费者等价性。首组 11 份原 TRAIN 新增 33 笔且无解析错误。合成、固定分栏、直接两题合计分别为 19/22、19/22、18/22，正确类证据 F1 为 71.22%、60.32%、54.94%。用途限制单项合成 10/11，两对照各 9/11。
- `convergence_revision6_indexed_effects_confirmation.py` 在其余 13 份原 TRAIN 完成 39 笔，零读数错误。主指标用途限制三路分别为 10/13、10/13、11/13，正确类证据 F1 为 64.49%、55.40%、57.84%。合成对分栏差 +9.08 个百分点，95% 区间 0 至 +19.34，对直接差 +6.65，区间 −9.23 至 +23.79。次要指标未授予权利为 8/13、8/13、6/13。两组累计新增 72 笔、教师 0。
- 确认组全量响应封存后，单任务评分误调用双任务汇总并退出。`convergence_revision6_indexed_effects_confirmation_finalize.py` 逐笔核对原始请求、冻结模型及完整响应，从同一批 39 笔完成评分。未补发。86 项相关检查通过。
- 本版用途限制比直接读器少答对的 B5-2 合同对自行受益用途设书面批准条件，两索引读器分别判未提及和未决，直接读器判蕴含。保留条款及原参考，不由该差异推出跨母来源规则。此版保留 TRAIN 证据，固定 DEV 尚未派发。

## Revision 6 伊利诺伊估值的前一断点

阶段 `revision6_illinois_pair_amounts_settled`，回执 `handoff/revision6_illinois_pair_amounts_terminal_20261120.json`。账本 14,935 笔、在途 0，84 项检查通过。 [原生估值与五库累计指标](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_ILLINOIS_PAIR_AMOUNTS_AND_FIXED_DEV_20261120.json)

- `convergence_oe_illinois_amount.py` 只对题面逐资产逐法条独立估值、辖区与原条文相符、单债务人产权和金额明确的资产计算上限。原 TRAIN 6 份的 14 个金额和固定 DEV 2 份的 5 个金额均匹配原生参考；联名或产权仅被主张时保留原输出。
- `convergence_revision6_illinois_pair_amounts.py` 复用 B6 原进入程序与普通教师实际提案的四笔分类、估值读数。两件获正确分类的资产分别报零和漏报。原进入、完整提案和仅接入受支持提案金额三路在该母来源均为 0% 估值 F1，同信息直接为 44.44%。没有通过估值采纳的提案读数。
- 共用估值修订在完整固定 DEV 上使四个内部臂 68.48%→72.82%、PARSE 66.24%→70.58%。五臂各改善 2 份、退化 0，F1 配对差区间为 0 至 +11.46 个百分点，平均相对误差持平。复用 4 笔适用 DEV 的独立物理响应。B6 原提案无需复试；M2 接续须有能超出同信息检查的候选差异。

## Revision 6 B5 答案分歧强对照的前一断点

阶段 `revision6_cni_b5_disagreement_settled`，回执 `handoff/revision6_cni_b5_disagreement_terminal_20261120.json`。账本 14,935 笔、在途 0，81 项检查通过。 [B5 强对照与五库累计指标](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_B5_DISAGREEMENT_AND_FIXED_DEV_20261120.json)

- `cni_development_definition.py` 将限定范围内的数据定义和开发计划条目识别为保密对象。在完整原文和跨度核对通过、且没有其他开发线索时，判定该合同未提及独立开发。匹配 1 份原 TRAIN 和 1 份固定 DEV。固定 B8 五臂各由 15/16 到 16/16，一项修正，无退化。累计四个内部臂 202/272、证据 F1 52.98%，PARSE 193/272、45.26%。
- `convergence_revision6_cni_b5_disagreement.py` 复用同一 5 组、10 笔原 TRAIN 实测，三种策略各筛一组、花两笔已测读数。候选驱动选 B1-1、进入读器符合该组证据。答案分歧选 B4-0、两个读器都未通过，默认也保留进入读器。两种策略的固定 DEV 读器及输出相同。按时间 B5-1 仍采纳提案。应用新公共规则后，三路在固定 DEV 的独立开发题均为 16/16。候选驱动对按时间的正确类证据 F1 差为 +9.30 个百分点，配对 95% 区间为 −8.20 至 +27.71。
- 本轮复用 B5 固定 DEV 32 笔原响应，另验证定义适用 TRAIN 的 2 笔归档响应，新增请求 0。B5 当前选组和原提案无需再读。M2 后续需要在同预算下能改变强对照采纳决定的实际提案及适用的前向母来源。

## Revision 6 ContractNLI 独立开发的前一断点

阶段 `revision6_cni_development_release_settled`，回执 `handoff/revision6_cni_development_release_terminal_20261120.json`。账本 14,935 笔、在途 0，78 项检查通过。 [独立开发与五库累计指标](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_DEVELOPMENT_AND_FIXED_DEV_20261120.json)

- `cni_independent_development.py` 在完整合同范围内区分此前知悉、不参考保密信息的开发例外和未决开发线索。仅在完整源文覆盖且没有未解释线索时判定未提及。原 TRAIN 的 7 项无开发路径及 1 项明确许可均与原参考相符。
- `convergence_revision6_cni_development_release.py` 对固定 B8 五臂应用相同规则，独立开发各 11/16→15/16，4 项修正、0 项退化。四个内部臂合计 201/272、证据 F1 52.61%，PARSE 192/272、44.89%。本轮范围内核验 TRAIN 15 笔及 DEV 10 笔，使用的另一套 B5 比较复用 32 笔原响应。
- B5 按时间、候选驱动在同规则下由 11/16、12/16 分别到 15/16、16/16。候选驱动相对按时间的分类差区间为 0 至 +18.75 个百分点，答对且证据匹配的 F1 差为 +15.55，区间为 −4.74 至 +37.14。两路共同修复 4 项，独立差异未达扩验条件。新增请求 0。

## Revision 6 M2 威斯康星自住房的前一断点

阶段 `revision6_wi_homestead_transfer_settled`，回执 `handoff/revision6_wi_homestead_transfer_terminal_20261120.json`。账本 14,935 笔、在途 0，75 项检查通过。 [威斯康星自住房前向结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_WI_HOMESTEAD_TRANSFER_20261120.json)

- `convergence_oe_wi_homestead.py` 仅按原题提供的辖区、已确立产权、居住用途和单项估值规则核对威斯康星自住房。B7 的候选补对分类，但进入程序与候选的 75,000 美元都只计单人额度。按原题共同产权与法条每人 75,000 美元核得 142,200 美元。共享、逐例和同信息直接筛选对这个范围一致。
- `convergence_revision6_wi_homestead_transfer.py` 保存 B7 只采纳分类的局部训练快照，复用 B7 与 B8 共 32 笔原请求。在 B8 唯一同范围来源，候选省略威斯康星分类且仍只报 75,000 美元，原参考为 112,850 美元。局部候选没有改写任何 B8 母来源，分类和估值分别保持 64.17% 和 69.54%。同信息直接补齐后为 65.36% 和 71.03%。
- 固定 DEV 16 母来源范围命中为 0，未读 DEV 标签或新增请求。B8 先前准备的所有权选组两路同选，继续保留原记录。只有另有源文与候选的可迁移差异时才派发。

## Revision 6 MAUD 整节引用的前一断点

阶段 `revision6_maud_section_reference_settled`，回执 `handoff/revision6_maud_section_reference_terminal_20261120.json`。账本 14,935 笔、在途 0，72 项检查通过。 [整节引用与五库累计表](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_MAUD_SECTION_REFERENCE_AND_FIXED_DEV_20261120.json)

- `maud_section_reference.py` 将可见疫情例外绑定到两个明确归属的分项。整节覆盖、分项限制和别节引用各有回归。原 B5 第一份 TRAIN 证明第 6.8 节覆盖整个第 5.1 节。原两路普通经营与负面契约均答对。
- `convergence_revision6_maud_section_reference.py` 在此前累计入口复用固定 DEV 的相同原请求。唯一新命中为两节选共有、置于两类义务之前的前导段。五臂负面契约各 12/16→13/16，无退化，配对 95% 区间为 0 至 +18.75 个百分点。普通经营 14/16、知悉定义 16/16。复用 TRAIN、DEV 各 2 笔。新增模型请求 0。
- 此修订归入共用规则，五臂两项契约输出逐项一致。本轮固定 DEV 的整节覆盖写法为 0，只有前导段一例。联合接口的原扩验门槛和 M1/M2 的独立验收缺口仍保留。

## Revision 6 M1 MAUD 联合范围字段的前一断点

阶段 `revision6_maud_joint_scope_settled`，回执 `handoff/revision6_maud_joint_scope_terminal_20261120.json`。会话 65943 已结算，新增 10 笔执行器响应、32,386 tokens，教师 0。账本 14,935 笔、在途 0，68 项回归通过。 [MAUD 联合范围配对结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_MAUD_JOINT_SCOPE_20261120.json)

- `convergence_revision6_maud_joint_scope.py` 用九值局部范围表达两类契约的已知与未决状态。语义等价覆盖原消费者 100 个状态。源文、锚点、执行器配置和原生评分与上一次相同，核验并复用 30 笔已有实测记录。
- 联合字段普通经营 9/10、负面契约 7/10，合计 16/20。旧合成 10/20，固定 15/20，直接 13/20。联合版较旧合成修正 6 项、无退化。较固定差 +5 个百分点，95% 区间为 −10 至 +20；较直接差 +15，区间为 −10 至 +40。原预登记扩验条件未达。新程序也改了范围指令，数值代表整版接口的变化。
- 29 个局部读数选了 15 个仅普通经营和 14 个仅负面契约，双侧范围未在实测中被选择。原 B5 第一份 MAUD 合同的两视图均给出第 6.8 节对整个第 5.1 节的疫情例外，第 5.1(a) 和 (b) 分属两类义务，可作为整体引用机制的原文证据。该合同未参与此次读取。当前候选未达扩验条件，保留现有 DEV 结论。

## Revision 6 M1 MAUD 疫情例外归属的前一断点

阶段 `revision6_maud_covenant_fit_settled`，回执 `handoff/revision6_maud_covenant_fit_terminal_20261120.json`。会话 61446 已结算，新增 30 笔执行器响应、97,391 tokens，教师 0。账本 14,925 笔、在途 0，68 项回归通过。 [MAUD 原 TRAIN 配对结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_MAUD_COVENANT_FIT_20261120.json)

- `convergence_revision6_maud_covenant_fit.py` 复用既有契约关系编译器，在 100 个局部状态上验证固定与合成输出等价。在 10 份原 TRAIN 疫情线索母合同上做完整原生比较，各路收到同样的两项原节选和原文锚点。
- 合成、固定与直接分别答对 10/20、15/20、13/20。合成相对固定修正 1 项、退化 6 项，按母来源的 95% 配对区间为 −45 至 −5 个百分点。普通经营正例的 5 个合成漏判均识别疫情触发，其中 4 个读数只将触发连到负面契约。三路传输正常。该布局未达到 B5–B8 前向读取条件，保留原固定 DEV 和已有共用规则。

## Revision 6 M2 披露对象选组的前一断点

阶段 `revision6_recipient_acquisition_settled`，回执 `handoff/revision6_recipient_acquisition_terminal_20261120.json`。复用 6 笔 TRAIN、32 笔 DEV 原请求。新增 0，账本 14,895 笔，在途 0，68 项回归通过。 [披露对象选组结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_RECIPIENT_ACQUISITION_20261120.json)

- `convergence_revision6_recipient_acquisition.py` 只打开 B5 原提案的员工和外部代理两个假设。三个策略共用三份有明确源文的原 TRAIN 合同，每策略筛选一组、两笔实测读数。候选驱动和答案分歧选 B4 第 1 份，进入和提案分别漏员工、漏外部代理，两路保留进入程序。按时间选 B4 第 3 份，候选正确区分传入来源和对外披露并被采纳。
- 固定 DEV 各为 22/32。候选驱动与分歧逐项同判，证据 F1 均 30.31%，按时间为 40.07%。分类差的配对 95% 区间为 −15.63 至 +18.75 个百分点，答对后计入的证据 F1 为 29.90% 对 31.21%。共用源文规则在固定 DEV 无适用问题。该局部选组未达到扩验条件。
- B3 OpenExempt 提案新增的俄勒冈主要住所分类仅在该批一份 TRAIN 有相同原文前提。后续原 TRAIN 与固定 DEV 的已核验资产清单里没有同范围住所，未派发该项派生读取。

## Revision 6 M1 权利授予单任务的前一断点

阶段 `revision6_license_forward_settled`，回执 `handoff/revision6_license_forward_terminal_20261120.json`。会话 98915 已退出，24 笔执行器调用完成，教师 0，账本 14,895 笔、在途 0。68 项回归通过。 [权利授予配对结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_LICENSE_FORWARD_TRAIN_20261120.json)

- `convergence_revision6_license_forward.py` 将权利授予单独编译，合成从 3 个固定字段缩到 2 个关系读数，对原 729 个状态核对输出等价。B6–B8 原 TRAIN 中此前未做该配对的 8 份合同均入组，三臂共用完整原文、原生索引、模型和证据规则。
- 参考均为蕴含。合成 0/8、固定 2/8、直接 8/8，证据 F1 为 0%、20.83%、75.42%。合成作答为 7 次未提及、1 次未决，传输与解码均正常。已有共用原文规则在本组无适用位置。这一压缩布局未达到 DEV 扩验条件。合同接口下一次比较需要针对另一个能与直接读法区分的源文缺口。M2 本阶段新增派发为 0。

## Revision 6 ContractNLI 协议披露的前一断点

阶段 `revision6_cni_agreement_disclosure_release_settled`，回执 `handoff/revision6_cni_agreement_disclosure_release_terminal_20261120.json`。68 项检查通过，新增请求 0，账本 14,871 笔、在途 0。 [协议披露与五库累计表](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_AGREEMENT_DISCLOSURE_AND_FIXED_DEV_20261120.json)

- `convergence_revision6_cni_agreement_disclosure_release.py` 复用归档响应，把协议本身和参与谈判事实的披露限制接入累计 B8 DEV。四个内部臂各 4/16→7/16，PARSE 10/16→11/16，均无退化。全部假设分别为 197/272 和 188/272。
- 保留同一原文规则和原 TRAIN 多数类回退组成的强对照。固定 DEV 为 13/16，归档 B5 候选驱动与按时间选组依次为 9/16、11/16。相同路径仅在有新的源文机制和能预先区分对照的证据时再运行。继续核实实际状态，从此断点接续。

## Revision 6 ContractNLI 明示标记的前一断点

阶段 `revision6_cni_qualification_release_settled`，回执 `handoff/revision6_cni_qualification_release_terminal_20261120.json`。65 项检查通过，新增请求 0，账本 14,871 笔、在途 0。 [ContractNLI 与五库累计表](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_QUALIFICATION_AND_FIXED_DEV_20261120.json)

- `convergence_revision6_cni_qualification_release.py` 将已核验的明示标记角色和四份 TRAIN 支持的免标记逻辑接入累计 B8 DEV。五臂各 4/16→12/16，修复八题、退化零题。四内部臂全部假设为 194/272，PARSE 为 187/272。复用八笔 TRAIN、十六笔 DEV 原请求。
- 合同、资产和 MAUD 的累计共用修订均已保留。这轮原生提升归于共用规则。剩余未确定的标记线索不作推断，后续有明确可区分的 TRAIN 证据时再考虑新的候选。

## Revision 6 MAUD 知悉定义的前一断点

阶段 `revision6_maud_knowledge_release_settled`，回执 `handoff/revision6_maud_knowledge_release_terminal_20261120.json`。62 项检查通过，新模型请求 0，账本 14,871 笔、在途 0。 [知悉定义与五库累计表](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_MAUD_KNOWLEDGE_AND_FIXED_DEV_20261120.json)

- `convergence_revision6_maud_knowledge_release.py` 把两类原文关系加入累计固定 DEV，即定义要求完成合理调查，以及定义明文计入所列人员应当知悉的事实。四内部臂 14/16→16/16，PARSE 15/16→16/16。原 TRAIN 15 份明示构成推定知悉均与参考相合。累计矩阵继续保留 OpenExempt 分类及 MAUD 负面契约的既有修订。
- 当前知悉定义固定 DEV 已达各臂共同上限。同信息独立差异仍未得到验证。继续其它仍有原生错误且有原 TRAIN 区分依据的语义范围，避免复跑本项。

## Revision 6 MAUD 跨节选恢复的前一断点

阶段 `revision6_maud_parallel_release_settled`，回执 `handoff/revision6_maud_parallel_release_terminal_20261120.json`。59 项检查通过，新增请求 0，账本 14,871 笔、在途 0。 [MAUD 原文和固定 DEV 评分](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_MAUD_PARALLEL_EXCERPT_RELEASE_20261120.json)

- `maud_parallel_excerpt.py` 仅恢复原请求同一合同的相邻视图中唯一对齐的内部省略。原 TRAIN 两个对照的疫情措辞均不管目标负面义务。固定 DEV 两份恢复中，一份的例外管辖原负面义务，另一份只继承 A、C、D、E 项且未继承疫情 B 项。该案原参考 Yes，保留范围差异。
- `convergence_revision6_maud_parallel_release.py` 在已结算的 OpenExempt 修订入口上合并此次 MAUD 公共规则，五臂负面契约各由 11/16 到 12/16。核验目标原请求包含两视图，复用 TRAIN 两笔、DEV 四笔去重请求。M1 独立原生收益仍待验证。相同源文规则流程已结算，避免重复比较。

## Revision 6 一般财产条款的前一断点

阶段 `revision6_ec_property_release_settled`，总回执 `handoff/revision6_ec_property_release_terminal_20261120.json`。55 项检查通过，模型新增请求 0，连续账本 14,871 笔、在途 0。 [分类 TRAIN 与固定 DEV 结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_EC_GENERAL_PROPERTY_RELEASE_20261120.json)

- `convergence_revision6_ec_general_property.py` 封存 B2、B6 的原始候选与进入程序分类读数。只保留原法条、资产与产权同时满足的新增索赔，B2 回放 F1 为 43.75% 对同信息直接 46.13%，B6 两路同为 38.53%。未发现已测的同版本前向候选响应。历史候选采纳不变。
- 累计固定 DEV 的新入口为 `convergence_revision6_ec_property_release.py`。它在原累计正式 DEV 各臂上应用同一一般财产条款核对，仅再评分改变的 EC。四内部臂为 70.02%→79.63%，PARSE 为 68.63%→78.92%。各方法独立分类消融差为零。继续其它原文有可区分候选的范围时保留这一共同规则及其新评分底座。

## Revision 6 资产绑定与家电迁移的前一断点

阶段 `revision6_candidate_asset_binding_appliance_transfer_settled`，总回执 `handoff/revision6_candidate_asset_binding_appliance_transfer_terminal_20261120.json`。54 项检查通过，新增请求 0，连续账本 14,871 笔、在途 0。 [对照及结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CANDIDATE_ASSET_BINDING_AND_APPLIANCES_20261120.json)

- `convergence_revision6_candidate_asset_binding.py` 对 B2–B8 实际进入程序和候选同时按原文资产绑定。八个表面正确的候选新增位置中有四个只涉及资产名。B2 车辆和 B6 住宅停留在命名差异。固定 B8 DEV 两条正式存档臂均无绑定变更。
- `convergence_revision6_appliance_amount_transfer.py` 用 B8 智能恒温器正确新增的 241 美元作为候选学习证据。固定 DEV 命中 1/16，进入程序和 B8 候选都对洗烘一体机给出 1,275 美元。局部候选改写 0，F1 39.89%。同信息直接修正至 700 美元，F1 40.41%。同一算术作用域的已有归档无需复试。下一条候选优先核对原文能否区分其新增适用性判断，而非只提供金额。

## Revision 6 处分后保留接口的前一断点

阶段 `revision6_retention_grant_replay_settled`，总回执 `handoff/revision6_retention_grant_replay_terminal_20261120.json`。会话 96527 已结算，36 笔执行器请求完成，教师 0，累计 14,871 笔、在途 0。51 项检查通过。 [三路实测与共有证明消融](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_RETENTION_INTERFACE_AND_GRANTS_20261120.json)

- `convergence_revision6_retention_interface.py` 将 12 份已源审原 TRAIN 的逐项配对结果保存为独立快照。固定、合成、直接均为 4/12，且均修复 B7。合成的六项未决集中在是否存在适用保留许可。原 provisional 快照中的 `active` 只表示按初次联合分完成候选排序，已被这次强对照否决，固定 DEV 无派发。
- `convergence_revision6_retention_grant_replay.py` 从完整原文提取五份合同的明确保留例外，向三路同样提供。合成 6/12，固定与直接均 9/12。按分类正确计入证据后，合成比直接低 13.70 个百分点，95% 配对区间 −27.41 到 −2.22。避免重复派发这次读法。可接续查找需要跨条款绑定、且同信息直接检查仍未解决的实测错误。

## Revision 6 局部否决的前一断点

阶段 `revision6_retention_scope_settled`，总回执 `handoff/revision6_retention_scope_terminal_20261120.json`。47 项定向检查通过，新增模型请求 0，账本 14,835 笔、在途 0。原冻结协议、72 份源码、TEST 终态及曝光记录通过校验。 [最新结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_RETENTION_SCOPE_20261120.json)

- `convergence_revision6_retention_scope.py` 只对可见禁留证据与 B5 提案分类相冲突的保留义务使用进入读器。固定 DEV 触发 2/16，两处结论持平，整体与原提案同为 148/272、证据 F1 26.46%。同信息直接改判为 147/272。备份例外分隔在后文的来源仍可保留副本，交接特定文件的另一份来源未覆盖完整假设。局部否决未入库。
- 从后续三份原 TRAIN 核验六笔实测。B7 的保留义务误判在普通和 PARSE 两路均出现，独立源审区分请求销毁时禁留、预先可能同意复制、请求时处分复制件以及关系终止返还。新增假设是分别编码上述范围和动作，再与看同样原文的直接读者比较。先验证其他已审 TRAIN 有可区分的证据，已结算局部否决不复跑。

## Revision 6 保留义务候选选组的前一断点

阶段 `revision6_retention_group_transfer_settled`，总回执 `handoff/revision6_retention_group_transfer_terminal_20261120.json`。44 项定向检查通过，新增模型请求 0，账本 14,835 笔、在途 0。原冻结协议、72 份源码、TEST 终态及曝光记录通过校验。 [最新结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_RETENTION_GROUP_TRANSFER_20261120.json)

- M2 的 `convergence_revision6_retention_group_selection.py` 复用 B5 实际 PARSE 式提案前后两路响应。按候选的实测极性变化选中 B1 的原文已审合同并保留进入读器，按时间选中 B5 合同并采纳提案。筛选的共享与同信息直接在两组选定数据上逐项同判。两种训练库已保存，历史采纳决定不改。
- `convergence_revision6_retention_group_transfer.py` 核验 B4 与 B8 DEV 的原文、Qwen 配置、原生消费者及两个读器版本。复用相同 16 母样本上的 32 笔响应。候选驱动与按时间为 149/272、148/272，证据 F1 为 25.57%、26.46%。保留义务为 5/16、7/16。接续优先找真实候选在先前源审范围内回避错误后仍能向其他母样本迁移的证据。
- M1 以状态词实测和用途限制原读器的上一阶段回执为当前断点，同一状态词和引文筛选未重跑。

## Revision 6 状态词与覆盖的前一断点

阶段 `revision6_status_words_and_transfer_capacity_settled`，回执 `handoff/revision6_status_words_transfer_capacity_terminal_20261120.json`。12 笔新 TRAIN 配对请求结算，教师 0。43 项定向检查通过，账本 14,835 笔，在途 0。原冻结协议、TEST 终态、曝光和 72 份源码通过校验。 [最新结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_STATUS_WORDS_AND_TRANSFER_CAPACITY_20261120.json)

- M1 的 `convergence_revision6_contract_status_words.py` 对真、假和未决作等价状态词编码，729 个原消费者状态均保留。两路 TRAIN 正确位置完全相同，均 7/12。状态词证据 F1 72.22% 对直接 55.56%，差值来自同一母样本的两项错误分类，分类正确时的联合证据分持平。旧接口 11/12，状态词未进入 DEV。
- M2 的 `convergence_revision6_fragment_transfer_capacity.py` 核实 B4 片段在 B5–B8 后续 16 份原 TRAIN 均无适用资产。B7 联邦片段的四个固定 DEV 位置均有两路唯一金额且逐项相同。继续寻找已审原文关系能区分提案与进入程序的真实迁移；已有两片段的相同条件无需重跑。

## Revision 6 用途漏判与俄勒冈迁移的前一断点

阶段 `revision6_use_scope_and_oregon_transfer_settled`，回执 `handoff/revision6_use_scope_oregon_terminal_20261120.json`。新增模型请求为 0，41 项定向检查通过，连续账本 14,823 笔、在途 0。冻结协议、TEST 终态及曝光记录和 72 份源码完整。 [最新结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_USE_SCOPE_AND_OREGON_TRANSFER_20261120.json)

- M1 的 `convergence_revision6_contract_use_scope_replay.py` 核对了 32 笔原 DEV 配对。合成的 10 个用途缺席输出都有原始引文，两字段均为否；其中 2 个引文包含完整限定。共享原文规则恢复这两项，两任务合计 20/32 对直接 22/32，证据 F1 45.02% 对 32.84%，配对区间跨零。接续须先确定新的 TRAIN 原文证据是否能消除关系读取本身的极性错误。
- M2 的 `convergence_revision6_oregon_apparel_transfer.py` 保存 B4 服装估值范围的选择。候选六处金额均正确，原程序漏报两处，并误列四处车辆适用。固定 B4 DEV 只命中一份，候选片段改写 0 份，16.12% 对同信息直接校正 16.95%，B5 前向 TRAIN 无覆盖。只在已有真实候选呈现跨母来源的有效范围时扩大迁移。

## Revision 6 用途与权利配对的前一断点

阶段 `revision6_use_license_and_archive_coverage_settled`，总回执 `handoff/revision6_use_license_archive_coverage_terminal_20261120.json`。32 笔新执行器请求均结算，教师 0，39 项定向检查通过，账本 14,823 笔、在途 0。冻结协议、TEST 终态和曝光记录及 72 份源码通过哈希检验。 [最新结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_USE_LICENSE_AND_ARCHIVE_COVERAGE_20261120.json)

- M1 的 `convergence_revision6_contract_use_license_dev.py` 用 18 笔原始 TRAIN 读数和两路共用的原文补齐规则保存 B8 选择，16 份固定 DEV 的合成与同输入直接各完成 16 笔。两任务合计 18/32 对 22/32，证据 F1 40.34% 对 32.84%。用途限制 9/16 对 13/16，合成修正 3 项、退化 7 项。权利限制两路均 9/16，证据差 +11.69 个百分点，区间跨零。保留训练快照与实测封印。接续优先用原 TRAIN 审核合成接口将限定条款读为缺席的实际原因。
- M1 的 `convergence_revision6_contract_employee_witnesses.py` 复算同条款许可，已有的 5 份 TRAIN 正例路径通过源审。原 16 份 DEV 没有符合这些确切句式的母来源。
- M2 的 `convergence_revision6_candidate_archive_coverage.py` 核验 B2–B8 两路 56 笔 EV 请求。联邦兜底豁免 43 个、宾州一般豁免 12 个可核对位置中，候选均无正确正额。当前两项法条缺少可迁移的正向候选。接续仅在其他已审法律关系能提供实际正向区分时比较。

## Revision 6 分栏读器与分法条选择的前一断点

阶段 `revision6_role_query_and_scoped_amounts_settled`，回执 `handoff/revision6_role_query_scoped_amounts_terminal_20261120.json`。37 项定向检查通过，12 笔新 TRAIN 执行器请求全结算，教师请求 0，账本 14,791 笔、在途 0。原冻结协议、曝光与终态和 72 份源码已校验。 [最新结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_ROLE_QUERY_AND_SCOPED_AMOUNTS_20261120.json)

- M1 的 `convergence_revision6_contract_referenced_definitions.py` 保留许可仍使用的定义，培训源审保留全部已引用的必需证据，5 份原 DEV 的合成 F1 恢复至原来的 52.10%，同输入直接仍为 72.00%。新角色分栏见 `convergence_revision6_contract_role_query.py`，两路去重后的归档评分保存在 `convergence_revision6_contract_role_redecode.py`。相同栏位下合成与直接分类 5/6、6/6，证据 F1 41.67%、63.33%，源审支持 2/6、3/6。两版保留，原正式接口继续运行。接续优先检查还能通过 TRAIN 源审且有对照差异的权限限定形式。
- M2 的 `convergence_revision6_scoped_candidate_amounts.py` 保存 B7 逐法条选择，联邦选候选、威斯康星保留进入程序。复用 32 笔原生 TRAIN 请求验证 B7 及 B8 前向链，固定 DEV 有 4 份适用、0 次输出改写，45.03% 对直接金额校正 46.28%。选择范围暂不扩大。接续查原批次其他实际候选中是否有完整、可迁移的明示差异。

## Revision 6 引文筛选与金额核验的前一断点

阶段 `revision6_citation_roles_and_statutory_amounts_settled`，回执 `handoff/revision6_citations_statutory_amounts_terminal_20261119.json`。三项离线回放和源代码已经绑定。34 项定向检查通过，连续账本 14,779 笔，在途 0。原 TEST 终态、曝光记录、冻结协议和 72 份源码快照通过校验。 [最新结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CITATIONS_AND_STATUTORY_AMOUNTS_20261119.json)

- M1 `convergence_revision6_contract_citation_roles.py` 在 6 份源审 TRAIN 上删掉 3 条多余引文，保留原已引用的必需证明。5 份 DEV 同信息比较中，合成证据 F1 由 52.10% 降至 48.10%，直接对照仍为 72.00%，分类均为 5/5。正式选型保持原解码。接续用可审的 TRAIN 例子区分定义是否支持主体和信息范围，再决定新的结构读数。
- M2 `convergence_revision6_candidate_statutory_amounts.py` 找到 B7 同一件资产的两处真实正额错误。进入程序在联邦条款超额，提案在威斯康星条款少报，两路均未通过全组筛选。金额相同的重复条目可提供标量读数，原生重复照常保留。`convergence_revision6_statutory_amount_dev.py` 的同规则 DEV 回放使两臂估值 F1 各提高 1.25 个百分点。接续从新能通过整组法条核验的实际候选出发，避开相同证据重跑。

## Revision 6 跨条款与明示断言的前一断点

阶段 `revision6_links_and_assertions_settled`。新增的 M1 正式参数 `--development-path contract-links` 结算 10 笔固定 DEV 读数，另有 5 笔同输入直接对照。五份适用合同均选择合成，合成与直接同为 5/5，证据 F1 为 52.10% 与 72.00%。合成与直接分别输出 9 条和 1 条落在标注之外的引文。后续优先用 TRAIN 源审区分支持许可、补齐主体的必要引文与多余引文。

正式 M2 参数 `--development-path candidate-edits --batch 7` 现进入明示断言筛选。旧覆盖口径保留在 `candidate-edits-coverage`。B7 单一差异是引文漏报，经校正共同保留进入程序。避免重复派发已结算原请求。新选组须能观测明示金额或以漏报为单独验证目标。

本阶段回执 `handoff/revision6_links_assertions_terminal_20261119.json`，连续账本 14,779 笔，在途 0。两项独立收益未达成。 [结果及配对区间](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_LINKS_AND_ASSERTIONS_20261119.json)

## Revision 6 运行与断点

- M1 合同正式拟合、持久化与固定 DEV 配对已结算，入口为 `python -m experiments.convergence_formal_train_fit` 的 `--development-path contract-interface`。指针 `handoff/revision6_formal_contract_M1_current.json`。8 笔归档 TRAIN 读数已复用。正式阶段选择了固定字段，7 个适用 DEV 上与固定字段对照同为 6/7，强制合成为 3/7，历史共用程序为 7/7。有关未读现象的下一条假设需通过 TRAIN 原文的代表人定义与跨句指代验证，复用已有链接引文试验。
- 上一阶段的 M2 所有权选组与金额覆盖口径已结算。有所有权审计的 4 组中两路同选；金额编辑的同一 3 组等预算比较中，两路选组不同，覆盖口径下候选驱动组采纳提案。B8 前向估值提升 3.75 个百分点，分类退化 14.17 个百分点，已登记只改变估值的固定 DEV 比较。
- OpenExempt 固定 DEV 会话 11982 已结算，指针 `handoff/revision6_candidate_M2_DEV_current.json`。对两种选组持久化的估值技能进行 16 母来源配对，分类复用同一基线，公共控制后估值 F1 为 45.03% 与 46.13%，2 份改善、3 份退化，配对 95% 区间跨 0。没有扩大到新源或 TEST。
- 当前阶段 `revision6_matched_paths_settled`，`handoff/revision6_formal_paths_terminal_20261119.json` 与 `handoff/run_state.json` 已同步。连续账本 14,764 笔，新增 48 笔执行器调用，在途 0。复用两条链的结算材料，下一步针对实际读数定位的错误和训练先验继续。 [五库汇总](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_FORMAL_PATHS_20261119.json)

## Revision 5 历史交接

用户已恢复同一研究 Goal（`01a1edc7-ae76-7441-acaf-be2240b0b4b1`）。当前工作安排采用 revision 5，已从指定提交 `56ed2142df80c47ce155351902916b10ae626904` 校验并同步三份入口。工具中的原 Goal 文本继续保留原研究对象和验收条件。原 `protocol.json` 由冻结轮次使用。

- [新版 PLAN](../reports/legal_skill_convergence_20261117/PLAN.md) · [接续协议](../reports/legal_skill_convergence_20261117/continuation_protocol_20261119.json) · [服务器指令](../reports/legal_skill_convergence_20261117/SERVER_GOAL.md)
- 已结算 128 来源八批训练、五库冻结 TEST、消融、强对照及论文初稿。冻结 TEST 终态 `dbbc3b355cad2328b14f7255bfe4a23b9a8b449c80d581159f0c99c3bc93fd7d`。恢复时连续账本为 14447 行，在途 0；最新结算见下。
- 本阶段只补充了决定下一步所缺的证据。M1 对齐候选和读数、训练选择并追到库与原生结果。M2 对齐原始教师请求、反馈、候选、共享筛选和最终库，保留同信息强对照。发现可实施的新缺口后使用独立开发版本做最小 TRAIN/DEV 比较。
- 原候选库存的独立验证容量结论适用于后续独立确认。这一阶段继续在现有 TRAIN/DEV 上工作，保留原 TEST 的曝光事实。
- 恢复时读取 `handoff/run_state.json`、实际任务、账本及源码绑定。入口同步回执 `handoff/continuation_revision5_authority_20261119.json`，以下记录按当时日期保留。

## 当前状态

原 Goal 已登记为 `blocked`，阶段为 `revision5_independent_effects_blocked`。连续三次核对的共同阻断是缺少能与同信息强对照区分的 TRAIN/DEV 候选证据。账本 14,716 笔，在途 0。恢复后先核对新的证据和实际状态，从尚未验证的候选继续。 [阻断说明与证据](../reports/legal_skill_convergence_20261117/GOAL_BLOCK_20261119.md)

## Revision 5 五库累计正式 B8 DEV 已封存

五臂全量原生结果已合并，复用同一批 80 个 DEV 母来源。ContractNLI 为四个内部臂 186/272、PARSE 179/272。联合臂 OpenExempt 分类和估值 F1 为 70.02%、68.48%。Diversity 16/16，MAUD 三项 14/16、11/16、14/16，Airline 15/16。 [正式入口](../experiments/convergence_revision5_release_dev.py) · [最终开发评分](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CUMULATIVE_FORMAL_DEV_20261119.json)

两条 M1 臂在 Diversity 各有 16 次关系接口调用，其余四库为 0。两组 M2 对照全库最终程序一致。四组机制消融在每库的原生输出差异均为 0。后续以可区别同信息控制的 TRAIN 来源或候选为触发依据，避免重复启动验证。13 项测试通过，1,920 个原生视图按封印逐项校验，在途 0，连续账本 14,716 笔。最新回执 `handoff/revision5_release_B8_DEV_terminal_20261119.json`。

最近派发核对 `handoff/revision5_followup_applicability_receipt_20261119.json`。两版 MAUD 局部接口的 8 笔响应共覆盖 2 处已绑定的非疫情例外。当前共用规则未决的 8 份有疫情线索 TRAIN 合同中，原两路共同答对 7 份，余下 1 份为已审的嵌套例外口径分歧。保留现有流程和读数，未启动新任务。

同信息派发门复核见 `handoff/revision5_matched_followup_gate_20261119.json`。Diversity 同源字面控制与 M1 的原生差为 0。宾州合并形态后 M1 较固定字段在分类和估值中分别低 5.12 和 4.29 个百分点。OpenExempt 分类绑定修正改变了 B7 回放的候选选择，共享筛选与同信息直接核对同步改变。宾州 B8 正向冲突的两路判定也一致。本轮沿用已有表和回执，没有新派发。

## Revision 5 ContractNLI 披露协议本身的来源绑定接入正式 B8 DEV

当前阶段 `revision5_CNI_agreement_event_attachment_formal_dev_settled`。以明示协议存在或谈判事实为对象，补齐主动和被动禁止的来源绑定。五臂正式 B8 DEV 各修正一项分类，分类与证据均无退化。ContractNLI 的四个内部臂和 PARSE 总分类分别为 186/272、179/272。额外解释覆盖的交易考虑条款只留作诊断。 [实现](../experiments/convergence_revision5_cni_agreement_event_attachment.py) · [评分](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_AGREEMENT_EVENT_ATTACHMENT_20261119.json)

核对 30 笔有效归档请求。共用探索性证据后的同源配对为固定 4/10、合成 7/10、直接 3/10。留一母来源的 TRAIN 多数类达 8/10。四组消融仍一致。下一步复用已有记录，只在可归因的 TRAIN 新差异出现时派发后续实验。最新本地验证回执为 `handoff/revision5_CNI_agreement_event_attachment_terminal_20261119.json`，15 项检查通过，连续账本 14,716 笔、在途 0。

## Revision 5 ContractNLI 递交对象接入正式 B8 DEV

当前阶段 `revision5_CNI_disposition_roles_formal_dev_settled`。正式 B8 DEV 已用经 TRAIN 源审支持的条款角色修订替换 ContractNLI 终止处分槽位，五臂均为 14/16。内部臂总分类 176/272→185/272，PARSE 169/272→178/272。两路比较均有 9 项分类改善、0 项分类退化、1 项证据退化。「请求返还或销毁、接收方应遵从」的额外 DEV 试验为 15/16，仅保留为探索结果。 [实现](../experiments/convergence_revision5_cni_disposition_roles.py) · [集成与筛选回放](../experiments/convergence_revision5_cni_disposition_roles_gate.py) · [评分与终态](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_DISPOSITION_ROLES_20261119.json)

两项机制的四个正式消融比较在 ContractNLI 输出仍一致。B8 两个 TRAIN 候选的 12 笔归档响应和原生效益已核对，共享修订后仍保留现行程序。下一项付费验证需有能区分同信息强对照的新 TRAIN 证据。11 项检查通过，在途 0，连续账本 14,716 笔。恢复时以 `handoff/revision5_CNI_disposition_roles_terminal_20261119.json` 为最新本地验证回执，原 TEST 及曝光哈希保持。

## Revision 5 ContractNLI 终止处分的实际触发条件已结算

把返还、销毁和清除义务与其自己的协议终止、覆盖关系终止或书面请求绑定。拒绝把相邻条款的单独保密存续、签署回寄和邮件回执当作处分触发。仅在可测的处分候选都绑定到请求时，才输出终止处分「未提及」；其他未决文本保留原判定。

固定 B8 DEV 上五臂均从 5/16 到 12/16，7 项改善、0 项退化，配对 95% 区间为 +18.75 至 +68.75 个百分点。普通教师证据 F1 为 25.00%→65.63%，PARSE 为 21.58%→62.20%。TRAIN 的八份请求限定合同均与既有源审一致。分类普通教师 11/24→17/24，PARSE 12/24→18/24，各有 7 项改善和 1 项退化。TRAIN 与 DEV 各留存一处请求语义与基准标签差异。 [代码](../experiments/convergence_revision5_cni_disposition_events.py) · [分臂、区间与取证](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_DISPOSITION_EVENTS_20261119.json)

核验原六份 M1 TRAIN 合同的 12 笔固定／合成请求、响应与解码。两臂原始结果均为 3/6，同一来源触发证据送入原消费者后两臂均为 6/6。固定 DEV 的收益来自两路共用的规则。原 M1/M2 选择保留，未派发新实验。下一步只比较能在同信息下区分读器的未解来源。

6 项相关测试通过，账本保持 14,716 笔、在途 0。冻结协议、72 份源码、TEST 终态与曝光记录均通过校验。回执见 `handoff/revision5_CNI_disposition_events_terminal_20261119.json`，Goal 保持活跃。

## Revision 5 ContractNLI 明示标记的条款角色回放已结算

把原信息的资格条件与副本标记、保留现有标识、留存确认和解除保密区分。对同时含两种义务的条款保留未决；只有全媒介定义本身用合取明确要求标记、且无竞争线索时才确认普遍要求。该分流以原 24 份 TRAIN 和固定 B8 的 16 份 DEV 归档输出做同信息比较，先封存再按原评分器评分。

B8 五臂均由 4/16 到 8/16，4 项改善、0 项退化，配对 95% 区间为 +6.25 至 +50.00 个百分点。把所有标记线索一律作为“不能判定未提及”的对照只到 6/16。两项差异来自副本标记及保留既有标识。内部臂证据 F1 由 34.72% 到 55.56%，PARSE 由 22.22% 到 47.22%。TRAIN 两路分别从 9/24 到 14/24，均有 6 项改善、1 项退化。 [代码](../experiments/convergence_revision5_cni_designation_scope.py) · [逐臂结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_DESIGNATION_SCOPE_20261119.json)

复核原六份 M1 TRAIN 的 12 笔固定／合成物理读数。新增分流在其中一份判为未提及，与基准标签一致，但原已审的项目保密定义支持不经明示标记的路径。这说明标记线索缺失规则不能替代资格途径的源文核查，保留为回顾性诊断。两臂增益相同，本轮未改正式选择或派发新 M1/M2 请求。固定 DEV 仍有 11 份资格范围未决，下一步需要能识别其原文支持的途径，并先核实 TRAIN 覆盖。

5 项相关测试通过，连续账本 14,716 笔、在途 0。冻结协议、72 份源码、原 TEST 终态及曝光回执均通过校验。回执见 `handoff/revision5_CNI_designation_scope_terminal_20261119.json`。Goal 保持活跃。

## Revision 5 ContractNLI 共用来源规则已合入 B8 开发流程

复用了先前分开核验的定义成员、传达形式、条款前导、终止处分、存续与披露对象等规则。只执行可绑定的原文范围。以相同规则处理原 24 份 TRAIN 和原 B8 的 16 份 DEV 合同，基线逐项复现已封存的原生分数。B8 的每臂 272 个 ContractNLI 视图均有封存结果。

B8 的同信息 PARSE 分类由 165/272 到 169/272，证据 F1 由 35.77% 到 37.17%，4 项分类和 5 项证据改善，均无退化。四个内部臂分类保持 176/272，证据 F1 由 45.62% 到 45.67%。TRAIN 普通教师和 PARSE 的分类分别为 281/408→286/408、282/408→296/408，证据分别有 2 项、1 项下降，完整分项保留。 [入口](../experiments/convergence_revision5_cni_compose_scope.py) · [五臂配对结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_COMPOSE_SCOPE_20261119.json)

两组 M1 和两组 M2 的原生输出仍逐项一致。共同漏判最多的是全体信息是否必须明示标记（两系均错 12/16）和终止时是否必须返还或销毁（两系均错 11/16）。后续须先确认这些未解形式是否有可靠的 TRAIN 源文证据和可区别的接口读数。M2 跨法条结果维持直接对照结论，本轮未派发新实验。

4 项相关测试通过，新增模型请求 0，账本 14,716 笔、在途 0。冻结协议、72 份原源码、TEST 终态、结果与曝光回执通过校验。回执见 `handoff/revision5_CNI_compose_scope_terminal_20261119.json`，Goal 保持活跃。

## Revision 5 M2 宾州跨法条正向冲突已结算

核验 B7、B8 原 TRAIN 程序流的归档输出及 B8 当批新提案。用原已审资产、原文和法条重新封存每路原生输出。这里只认原输出中的肯定引用或正额估值。在旧同法条、分视图产权核对外，追加同一件资产能否同时作为服装和缝纫机的检查。两种视图的产权仍分别限定。

B7 宾州来源两路均无跨法条冲突。B8 的同一份宾州来源上，进入程序、B7 前向提案和 B8 当批新提案各对四件资产同时作出冲突的肯定判断。每项单独可满足，但四组均不能由同一资产类别解释；既有同法条产权核对在这些位置均相容。使用相同的两条法规、同一资产绑定和分视图产权的直接规则，与联合枚举对实际读数逐项等价。两种规则均未区分进入程序和当批提案。

事后在归档输出中同时移除相冲突的两项类别主张，B8 当批两路在该来源的分类／估值平均 F1 均提高 5.00 个百分点。该诊断没有选定哪条主张有原文支持，同信息直接规则复现同一处理。保留历史更新与原始输出，未派发新 M2 请求。 [比较代码](../experiments/convergence_revision5_oe_m2_cross_citation.py) · [归档结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_OE_M2_CROSS_CITATION_20261119.json)

8 项定向测试通过，连续账本 14,716 笔、在途 0。原冻结协议、72 份源码、TEST 终态和曝光记录均通过校验。回执见 `handoff/revision5_OE_M2_cross_citation_terminal_20261119.json`。Goal 保持活跃，两项独立原生收益仍待建立。

## Revision 5 OpenExempt 宾州跨任务形态对齐已结算

复用原四份 TRAIN、五份 DEV 的 36 笔实测读数，逐笔核验原请求、模型响应与生产解码。新入口在两视图的申报人、法规前提、资产名称及金额对齐后合并形态可能集，产权仍按各自原文判定。两路均用相同合并逻辑和宾州金额规则，先封存预测再打分。匹配 TRAIN 12 组资产、DEV 14 组。DEV 的同资产形态读数，关系接口 6 组不一致，其中 3 组无交集；固定字段只 1 组不一致，仍有交集。

TRAIN 估值中，合并后固定字段为 82.02%，关系接口为 85.00%，差值 2.98 个百分点。固定 DEV 合并后，关系接口的估值从 64.60% 到 66.83%，分类从 77.87% 到 73.71%。固定字段和源文直接核对在两项均持平，估值 71.11%、分类 78.83%。合并后的关系对固定差值为估值 −4.29、分类 −5.12 个百分点。保留跨视图结果供诊断；当前宾州形态候选没有继续派发读数的依据，M2 原直接对照结论保留。 [比较代码](../experiments/convergence_revision5_oe_paired_forms.py) · [完整分项及配对区间](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_OE_PAIRED_FORMS_20261119.json)

5 项相关测试通过，无新增模型请求，连续账本 14,716 笔、在途 0。原冻结协议、72 份源码、TEST 终态及曝光回执均通过校验。回执见 `handoff/revision5_OE_paired_forms_terminal_20261119.json`。Goal 保持活跃，两项独立原生增益仍待建立。

## Revision 5 OpenExempt 宾州一般金额条款回放已结算

[新版执行入口](../experiments/convergence_revision5_oe_pa_monetary.py) 将原八个宾州 TRAIN 视图中逐字一致的 § 8123 条款编译到两路共同消费者。单人只处理来源已确立的产权；联合申报按原题明示的共同所有前提。估值只在原题逐资产、逐法条的独立计量范围内计算。B8 的五份宾州来源中，EC 和 EV 分别支持 10、12 项原文可确定的主张。封存新输出后逐臂按原评分器评分。

在完整 16 来源 OpenExempt B8 DEV 上，四个内部臂的 EC F1 为 65.14%→70.02%，EV 为 65.36%→68.48%，母来源改善数分别为 5、3，均无退化。同信息 PARSE 的 EC 为 63.89%→68.63%，EV 为 61.30%→66.24%，两项均有 5 个来源改善、0 个退化。 [五臂结果及配对区间](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_OE_PA_MONETARY_20261119.json)

复用原宾州 M1 四份 TRAIN 和五份 DEV 的配对读数。共用规则后，TRAIN 的 EV 为固定 69.32%、关系 88.12%；固定 DEV 的 EV 为固定 71.11%、关系 64.60%，差值 −6.51 个百分点，配对区间 [−11.27, −1.90]。同信息源审直接核对在 DEV 达到 71.11%。差异项中，固定独有的 6 项主张均有来源支持，关系独有的 2 项缺来源支持。原候选继续保留为实验对照。当前仍缺 M1 在强对照下的可迁移原生增益和 M2 可区别直接筛选的证据。

4 项定向测试通过。新增模型请求 0，账本 14,716 笔、在途 0。原冻结协议、72 份源码、TEST 终态与曝光回执均通过校验。状态与验证见 `handoff/run_state.json` 和 `handoff/revision5_OE_PA_monetary_terminal_20261119.json`。

## Revision 5 OpenExempt 分类的原文资产键已接入 B8 DEV

B8 原输出把若干带金额的资产名称与同一件资产的规范名称分开列出。新版只归并能够唯一对齐原文资产描述、估价措辞和同一金额的键，再合并该资产已经作答的法条。归并放在共用政策前后均得到相同输出。已接入 [B8 正式开发入口](../experiments/convergence_revision5_oe_ec_formal.py)，独立封存五臂各 16 个 EC 预测，每臂复用其他 368 个原生视图。

B8 四个内部臂 EC F1 从 53.29% 到 65.14%，配对差值区间为 [4.18, 20.91] 个百分点，8 个母来源改善、0 个退化。同信息 PARSE 从 52.15% 到 63.89%，7 个母来源改善、0 个退化。原 32 个 TRAIN 母来源的普通臂由 37.52% 到 40.22%，PARSE 由 47.63% 到 50.21%，两路各有 2 个退化。该修复为两路共用的原文绑定。 [分臂结果与回放](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_OE_EC_BINDING_20261119.json)

同一修复回放了 B7–B8 的 32 笔归档 M2 配对响应。B7 进入程序的明确冲突从 0 到 5，候选仍为 2。共同筛选和同信息直接核对都失去“进入程序兼容”的拒绝前提，回放中两路均改为采纳候选。固定 B8 前向的候选平均分类／估值 F1 较进入程序低 9.25 个百分点。保留原 B7 选择及两套诊断；当前没有相对直接核对的分流依据，未派发新 M2 运行。

15 项相关测试通过。无新增模型请求，账本 14,716 笔、在途 0。原冻结协议、72 份执行源码、TEST 终态、结果与曝光登记均通过校验。最新回执见 `handoff/revision5_EC_source_binding_terminal_20261119.json`。后续只对有归因依据的未解读数或能区分强对照的候选继续派发；本次五个 EC 评分单元已结算，直接复用。

## Revision 5 Diversity 与五库正式 DEV 已结算

按用户最新指令接入 [Diversity 正式流程](../experiments/convergence_revision5_diversity_formal.py)。用原 24 个 Diversity TRAIN 母来源形成八批修订快照。96 个候选的原生结果与整篇审计一致。B1、B2、B4、B8 的五臂均为 16/16。B8 仅 M1 臂由 14/16 提至 16/16，同信息固定坐标臂由 9/16 提至 16/16。两组 M1 臂在每个训练后检查点均有 16/16 母来源选择合成布局，坐标数从每臂 97 降到 52。原生收益来自共享原文读数。M1 在同信息比较中缩减 46.4% 的坐标，原生结果持平。

[五库联合 B8 DEV](../experiments/convergence_revision5_formal_native.py) 复用其他四库已经验证的公共规则，并核验每个预测的原臂、来源和规则。普通教师臂的 ContractNLI 分类正确数为 156/272→176/272，证据 F1 为 36.37%→45.62%。MAUD 知悉定义为 8/16→14/16，负面契约为 9/16→11/16，普通经营条款为 14/16→14/16。OpenExempt EC F1 为 50.19%→53.29%，EV F1 为 44.37%→65.36%。Airline 费用精确率为 2/16→15/16。其他四库没有触发本次 M1，公共规则分别在 16、8、13、13 个母来源改变输出。联合 B8 两组 M1 和两组 M2 消融的原生输出逐项一致。 [分臂、分库、触发计数与原生指标](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_FORMAL_NATIVE_DEV_20261119.json)

OpenExempt B7 的 M2 共享筛选与同信息直接蕴含对照都保留原程序。封存的 B8 前向结果也复用同一选择。本轮未派发新 M2 实验。后续依赖合成接口胜过同信息对照的未解来源，或 M2 与同信息强对照确实分流且有原生正向依据的候选；已结算批次直接复用。 [M2 同信息门槛回执](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_M2_OE_JOINT_NATIVE_GATE_20261119.json)

两次本地运行均已结束。30 个 DEV 评分单元及 2,400 条母来源预测的封印通过核验，18 项相关测试通过。新增模型请求 0，连续账本 14,716 笔、在途 0。原冻结协议、72 份执行源码、TEST 终态及曝光回执均通过哈希校验。本轮回执为 `handoff/revision5_formal_native_terminal_20261119.json`，当前进程与决定见 `handoff/run_state.json`。现有 Goal 保持活跃，双贡献的独立原生收益仍待验证。

## Revision 5 ContractNLI 披露对象绑定的配对已结算

公共披露对象规则之外，10 个符合条款组条件的 TRAIN 母来源已用冻结 Qwen 同输入实测。固定／合成／直接为 3/10、1/10、1/10。对记录中的组外标记核对原编号，公开规则只修复确已通读且声称组外的非空编号全部落在组内的响应。复用同一批原响应后，三路为 3/10、5/10、1/10，留一来源 TRAIN 多数类为 8/10。该候选未达到继续派发固定 DEV 的依据。

原实测目录由 `handoff/revision5_CNI_keyed_disclosure_current.json` 绑定，复算入口 `python -m experiments.convergence_revision5_cni_keyed_disclosure_scope`，只作离线结算。完成 30 笔 Qwen、154,532 tokens，教师 0；账本 14,716 笔、在途 0。16 份固定 DEV 中有 13 份符合文本条件，当前没有对应新读数。下一候选需针对少数类的有效披露对象证据并保留同信息对照。 [实测及回放结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_KEYED_DISCLOSURE_20261119.json)

## Revision 5 五库统一开发对照已结算

用户将推进 Goal 的 Codex 切到 6.2-sol high，实验读者和教师仍沿用原绑定。入口 `python -m experiments.convergence_revision5_common_native_dev` 将原文规则应用于原 B8 DEV 的五库、五臂、共 1,920 个原生视图。普通教师臂在 ContractNLI 分类、Diversity、MAUD 知悉定义、OpenExempt EV 和 Airline 分别从 156/272、9/16、8/16、44.37% 和 2/16 提高到 176/272、16/16、14/16、65.36% 和 15/16。全部分项区间及逐项退化已记入表。

两组 M1 的原差异各 7 项，共用规则后各 384 项逐项一致。两组 M2 两版本均逐项一致。后续必须在这套同信息规则之上取得可归因的独立效果后，才进入修订正式流程。复用新对照入口及预测封存，新增模型请求 0，账本 14,686 笔、在途 0。 [五库开发结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_COMMON_NATIVE_DEV_20261119.json)

## Revision 5 ContractNLI 原文条件下的接口缩减已结算

用原文中唯一可核实的条款部分求值。单项已知时固定和合成各需 4、3 个字段；双项已知时完整回执各需两个相反授权状态，只有弃去这些状态的诊断才可将字段缩至零。原 24 TRAIN／16 固定 DEV 的完整回执字段总数为 130/89 和 92/62。这一项没有实测生成耗时。

复核上轮 18 笔配对，统一公共前提后，仍需读取的两项固定答对 1 项、合成与直接各答对 2 项。正式 TRAIN 和固定 DEV 的既有读数在覆盖合同内也已答对余项。无新增请求，账本 14,686 笔、在途 0。复算 `python -m experiments.convergence_revision5_cni_conditioned_use_license`，回执 `handoff/revision5_CNI_conditioned_use_license_terminal_20261119.json`。后续候选须在公共前提之外的未决判断上具备可验证的原生差异。 [回放结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_CONDITIONED_USE_LICENSE_20261119.json)

## Revision 5 ContractNLI 从属条款引文回放已结算

同一规则核对已引用分项与原文编号和唯一前导句。既有引文全部保留时，固定 B8 DEV 普通教师与 PARSE 的用途限制证据 F1 分别由 24.61% 到 28.15%、23.75% 到 25.63%。只保留已核对的最小条款组合分别达到 29.40%、26.88%。原生标签不变。复用了 45 笔 TRAIN 与 32 笔固定 DEV 归档响应及上轮 18 笔 Qwen 配对响应。源文支持校准仍选择固定，两个接口仍漏读跨片段否定授予的实际条款。

复算入口 `python -m experiments.convergence_revision5_cni_clause_witness`，终态回执 `handoff/revision5_CNI_clause_witness_terminal_20261119.json`。新增请求 0，账本 14,686 笔、在途 0。该修补跨两个既有程序改善证据，后续研究需要在共用条款核对之上引入可验证的独立差异。 [回放结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_CLAUSE_WITNESS_20261119.json)

## Revision 5 ContractNLI 用途限制与权利授予配对已结算

18 笔冻结 Qwen 调用覆盖六份 TRAIN 合同及三种同输入读法。前段选择固定，后段固定、合成及直接作答分别为 3/6、4/6、4/6，证据 F1 为 32.78%、52.78%、38.33%。合成在一份合同上恢复两个实质未提及判断；另一份合同的跨片段否定授予条款由直接读者完整引用，两个接口均漏读。源审后段为 6/6。原 B8 DEV 16 份的同形拆分否定或紧邻先行词覆盖为零。该对照的接口采用决定保持固定。

原绑定及恢复记录在 `handoff/revision5_CNI_use_and_license_current.json` 指向的目录。复核入口 `python -m experiments.convergence_revision5_cni_use_and_license_evidence`，总回执 `handoff/revision5_CNI_use_and_license_terminal_20261119.json`。首次调用已经结算，恢复只移除比对时的运行时缓存标记，完全复用首笔响应。账本 14,686 笔、在途 0。23 项检查通过。后续需要覆盖其他来源并能超过同信息对照的结构变化。 [配对结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_USE_AND_LICENSE_20261119.json)

## Revision 5 OpenExempt 共享反馈的分类收益已定位

首轮教师的解释反馈绑定鹦鹉。唯一新增的正确分类引文来自同案胸针。原生 EC 把胸针列为申报人的已知资产，旧模板将该表述与单纯持有都归为未决。共用的直接规则按原文资产归属、个人用途前提和伊利诺伊州随题条文补足引文，在四份试验输入上逐项复现首轮共享提案的 EC 输出和 35.83% F1。其原共享筛选决定继续保留。共核验 20 笔 EC 响应。

原 32 份 TRAIN 中规则只覆盖两份，普通教师和 PARSE 的 EC F1 分别增加 1.56 和 1.74 个百分点。固定 B8 DEV 的 16 份覆盖为零。离线复算入口 `python -m experiments.convergence_revision5_oe_illinois_asset_attribution`，终态 `handoff/revision5_OE_illinois_asset_attribution_terminal_20261119.json`，新增请求 0，账本 14,668 笔、在途 0。接续工作需要新的、能在同信息直接规则之上预测原生差异的 TRAIN 证据。 [评分与来源绑定](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_OE_ILLINOIS_ASSET_ATTRIBUTION_20261119.json)

## Revision 5 ContractNLI 同句引文修复已结算

十二笔固定和合成读数、一组六笔直接作答及另两组二十六笔签名作用域和定义成员读数均按原始请求复核。一条合成读数的披露许可和就地定义共用原文句 14。两臂共用同句引文归并后仅这条读数变化，合成精确匹配 5/6→6/6、证据 F1 37.62%→54.29%。固定为 0/6 和 16.67%。归档直接作答为 6/6 和 58.33%，且同样正确引用句 14。另两组未出现重复引文。

离线复算入口 `python -m experiments.convergence_revision5_cni_colocated_citation`，终态 `handoff/revision5_CNI_colocated_citation_terminal_20261119.json`。新增模型请求 0，连续账本 14,668 笔、在途 0。原冻结和曝光校验通过。此处诊断已结算，接续检查具有独立原生收益依据的新候选，保留直接作答和后见源文对照。 [配对读数与评分](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_COLOCATED_CITATION_20261119.json)

## Revision 5 MAUD 已采纳候选的共用作用域回放已结算

逐笔核对 B6 普通教师、B6 PARSE 和 B8 PARSE 的 18 笔归档响应及已保存程序。三项已采纳提案原先分别多答对 1、1、2 题。给进入程序和候选共用知悉定义与契约作用域核对后，两路逐题同判，三组分别各为 9/9、9/9、8/9。普通经营契约检查复用了已核验的母合同定义，属于回顾性对照。

B8 知悉题的完整定义以已知事实为准，并纳入已收到的书面通知。将这一来源条件送入原有限消费者后，无需再读字段即可判定该题。原 24 份 TRAIN 余下四份均有截断或省略，剩余固定与合成字段数为 8 和 4。固定 B8 DEV 没有同形式的通知定义，两路知悉题保持 14/16 和 15/16。

三项历史库更新均保留。回放中三项均无法再通过正收益门槛。B8 余下一项错误属于已归档的负面契约嵌套例外。新增请求 0，连续账本 14,668 笔、在途 0，20 项检查通过。原冻结协议、72 份源码、结果终态、汇总表和曝光回执已核验。回执为 `handoff/revision5_MAUD_adoption_scope_terminal_20261119.json`。 [回放结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_MAUD_ADOPTION_SCOPE_20261119.json)

## Revision 5 ContractNLI 逆向工程的动作与证据范围已结算

按接收方、逆向工程动作及对象核对条款。同一规则用于普通教师和 PARSE，两路在原 TRAIN 上均从 3/24 提高到 23/24。余下一份原生正例的参考引文仅约束出版、复制和使用，保留标注与源文判定的差异。原生总收益为正的五项提案共 63 个配对，逆向工程标签唯一变化来自截断。在保留已完整返回的题目后，候选与进入程序在该题逐项同判。

固定 B8 DEV 两路均从 1/16 到 16/16，单句对照已经复现全部标签。根据同一 DEV 中的义务列表反馈，将连续分项连回约束接收方的前导条款，证据 F1 从 97.92% 到 100%。这一步复用了已查阅的 DEV。

核验 111 笔 TRAIN 和 32 笔 DEV 物理响应，原训练库决定保留。无需为该假设重复候选读数。若后续找到超出共用动作及对象检查的源句，再比较合成关系的独立作用。新增请求 0，连续账本 14,668 笔、在途 0，31 项检查通过。原冻结协议、72 份源码、结果终态、汇总表与曝光回执已校验。回执为 `handoff/revision5_CNI_reverse_engineering_terminal_20261119.json`。 [回放结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_REVERSE_ENGINEERING_20261119.json)

## Revision 5 OpenExempt 俄勒冈资产资格与用途编辑已结算

按两任务实际原文和随题俄勒冈条款，排除长笛的机动车估值，并在产权已确立的分类原文补入乐器引文。B7 提案的两处冲突减为一处。两路在四份 B7 TRAIN 上的分类 F1 各增 1.59 个百分点，原生估值 F1 均保持。受影响的提案估值在次要全输出计数下少一条误报。既定 B8 DEV 的 16 份来源中此规则覆盖为零。

余下一处涉及画作能否归入家庭用品。用途编辑将同一幅画明确限定为营业转售，保留原产权、价格及条款。独立补全允许四个签名，共享解释允许两个。相同信息的直接规则在全部 81 种已知和未知组合上与共享枚举同判。用途编辑只做离线核验，保留原 TRAIN 标注及选择。

32 份原 TRAIN 中四个视图有本次规则涉及的类别。回顾性检查中，余下家庭用品引文的原生参考在分类和估值均为正。源文规则保留类别未决。已回放原 B7/B8 两个程序及固定 B8 DEV 的两路归档响应。新增请求 0，账本 14,668 笔、在途 0，27 项检查通过。原冻结协议、72 份源码、终态、原结果摘要和曝光回执校验通过。回执为 `handoff/revision5_OE_oregon_eligibility_terminal_20261119.json`。 [证据与回放](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_OE_OREGON_ELIGIBILITY_20261119.json)

## Revision 5 OpenExempt 分类断言与 B7→B8 选择回放已结算

核对 B7 和 B8 各四份原 TRAIN 的 32 笔执行响应。按原数据生成器的姓氏复数规则，在 B8 恢复一处联名债务人称呼绑定。两路采用同一辖区、金额、兜底和资产类别检查。通配条款补出的资产行只支持该项引文，其余未作答类别保持未决。若把新行视作已答全类别，B7 两路各有 22、15 处冲突。按实际断言核对后为 0、2，原候选的两处冲突均保留。

B7 提案在共用检查后高 8.44 个百分点。独立补全采纳提案，共享筛选和同信息直接核对均保留进入程序。B8 归档前向回放中，保留程序的原生双任务均值高 4.25 个百分点，配对 95% 区间为 [−4.86, 14.82]。共享与直接核对逐项一致。

本轮在共用检查后重新核对原 B7 选择和四份原 B8 前向 TRAIN 来源，保留历史原生评分和实际库更新。下一步需要能在现有断言约束和同信息直接规则下改变候选采纳的新监督证据。新增请求 0，账本 14,668 笔、在途 0，27 项检查通过。原冻结协议、72 份源码、TEST 终态、结果摘要和曝光回执校验通过。回执为 `handoff/revision5_OE_assertion_coverage_terminal_20261119.json`。 [回放结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_OE_ASSERTION_COVERAGE_20261119.json)

## Revision 5 ContractNLI B5 共用作用域与回归门槛已结算

给进入程序和 B5 提案应用相同的完整记录恢复、协议存在性覆盖检查及既有招揽规则。旧批次差距从少 24 题缩至少 7 题，修正后为 110/204 对 103/204。当批提案为 40/51，进入程序为 37/51。即使将截断项 17 题全计对，旧批次的提案上界仍为 109/204，原保留决定成立。

固定 B8 DEV 中，初版协议存在性检查覆盖三份合同，其中一份明示协议本身须保密却被判为未提及。补上保护条件后在同一 DEV 回放，普通教师该题由 3/16 到 4/16，PARSE 由 9/16 到 11/16。配对 95% 区间分别为 [0.00, 18.75] 和 [0.00, 31.25] 个百分点。

已核验 30 笔 TRAIN 与 32 笔 DEV 真实响应。保留两版 DEV 回放。B5 当批仍有协议存在性与留存的标签增益，旧批次回归仍超出传输修复可恢复的范围。继续此路线需要有候选收益能覆盖同条件回归的依据。新增请求 0，账本 14,668 笔、在途 0。27 项检查通过，冻结协议、72 份源码、TEST 终态、结果摘要和曝光回执校验通过。回执为 `handoff/revision5_CNI_retention_controls_terminal_20261119.json`。 [回放结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_RETENTION_CONTROLS_20261119.json)

## Revision 5 ContractNLI 截断响应与候选选择已结算

按实际请求核对 93 笔 TRAIN 和 64 笔 DEV 响应，并对照保存的运行源码确认遇到截断时整组拒收。实验回放在最后一条完整记录处停止，跳过未闭合题目。B5 普通教师提案恢复 13 个完整题目、10 个正确标签，包括用途限制和未授予权利。恢复记录中有 12 题各列 179 个索引；证据质量问题仍在。B5 旧批次正确数 82/204→92/204，进入程序 106/204。即使把该笔 17 题全给满分，提案至多 99/204，原拒绝决定仍成立。五项提案均保持原决定。

同一规则用于原 B1 与固定 B8 DEV。B1 普通教师恢复 14 个完整题目、9 个正确标签，正确数 134/272→143/272。PARSE 同期保持 149/272，B8 两路都无变化。由于修复只保留已产生的完整题目，后续候选比较应把它用作共用对照。此截断无法解释 B5 的全部回归。

新增请求 0，账本 14,668 笔、在途 0，17 项检查通过。复核了原冻结协议、72 份源码、冻结结果摘要、终态和曝光回执。回执为 `handoff/revision5_CNI_partial_wire_terminal_20261119.json`。 [归档回放](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_PARTIAL_WIRE_20261119.json)

## Revision 5 ContractNLI 存续作用域与提案追踪已结算

复用原 24 TRAIN 和固定 B8 DEV 的 16 份来源。按同一合同、终止事件和义务绑定，TRAIN 有 10 份匹配原生参考，另有 B3 一份原文明确在一年终止条款保留十八个月的收购限制，原生参考仍为矛盾。对这一已知 TRAIN 文本完成两处独立数值替换，局部十八、十二、六个月结果为真、假、假，同时保留原文和原标注。直接比较期限与三种补全完全一致。两个改写只做了离线复核。

固定 DEV 上单条款和链接核对同判。PARSE 证据 F1 23.33%→35.83%，正确数保持 11/16。另核对五个原生总收益为正的原提案、63 个候选配对和 81 笔提案归档响应。11 次存续标签变化为五次修正和六次退化，均缺当前规则的严格原文证明，其中两次修正复用同一来源的签署与交付参考。继续此链路需要与正确终止事件相绑定、能区别于直接核对的原生提案变化。[比较结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_SURVIVAL_SCOPE_20261119.json)

新增模型请求 0，账本 14,668 笔、在途 0，15 项检查通过。冻结协议、72 份源码、原结果表、TEST 终态和曝光回执均已核验。回执为 `handoff/revision5_CNI_survival_scope_terminal_20261119.json`。

## Revision 5 ContractNLI 信息类别与定义绑定已结算

复用 18 笔配对读数、45 笔 TRAIN 和 32 笔固定 B8 DEV 归档响应。从已引成员回连定义后，六份配对合同两任务的固定、合成、直接作答分别为 9/12、12/12、11/12。使用全文的直接核对也恢复了两项任务的全部 12 个正确判断。保留原始读数、仅查完整引文、按成员回连和全文对照。

四份 TRAIN 补充覆盖分别来自明示类别、并列共用名词、段末认定和同一披露方的保密义务。扩展版覆盖 16/17 个类别正例，余下一份只在序言列出业务类别，仍未确定定义引用关系。PARSE 全文核对在 TRAIN 为 11/24→18/24→20/24，固定 DEV 为 5/16→8/16，两版 DEV 预测逐项相同。普通教师标签数在两组均保持。后续需要能区别于全文直接规则的已审关系条件才安排新的物理比较。[比较结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_DEFINITION_BINDING_20261119.json)

新增模型请求 0，账本 14,668 笔、在途 0，18 项检查通过。原冻结协议、72 份源码、TEST 终态、原结果表和曝光回执已核验。回执为 `handoff/revision5_CNI_definition_binding_terminal_20261119.json`。

## Revision 5 ContractNLI 定义成员与传达形式比较已结算

归档普通教师和 PARSE 在 24 份 TRAIN 上的“只含技术信息”正确数分别为 17 和 11。六份定向合同上，比较固定字段、合成关系和直接作答。三个读器共用完整原文、原生索引、模型和预算，固定及合成消费者在全部 729 个声明状态上等价。两项原生问题合计分别答对 6/12、8/12、2/12，普通教师归档为 10/12。合成的两处分类增益来自将只列传达形式的定义判为未提及。四份实际纳入非技术类别的合同，两种接口均误判。

对原响应引用做独立源审，合成在四份类别正例中已引用三份足够的组合，固定和直接作答各一份。直接作答对口头形式全判未提及，原引用六份均充分。回顾性重放共用同一源审条件，类别正确数依次为合成 5/6、固定 1/6、直接 3/6。后续先验证能从源码和原文把类别与作用域一起绑定的解码，并保留全文同信息直接核对。[比较结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_DEFINITION_MEMBERSHIP_20261119.json)

会话 65888 已结算。18 笔 Qwen 共 101,786 tokens，教师 0，账本 14,668 笔、在途 0，12 项检查通过。原冻结协议、72 份源码、TEST 终态、原结果表和曝光回执均已核验。回执为 `handoff/revision5_CNI_definition_membership_terminal_20261119.json`。

## Revision 5 OpenExempt 资产类别作用域已结算

B7 同一来源的四项残余冲突已按原文修正。披巾符合两条类别条款，分类视图明示产权。装饰画和长笛的两项估值不符合该州条款。使用同一类别规则后，B6 仍只替换分类，B7 新增冲突 4→0，分类 F1 为 60.96%→62.02%，估值均为 45.98%。规则设计使用了该 B7 案例，此数为回顾性结果。

复用 120 笔原 TRAIN 及 64 笔固定 B8 DEV 响应。DEV 普通教师和 PARSE 的分类各增 1.77 个百分点，估值各增 1.04 个百分点。54 个已答资产向量上未发生共享独立拒绝，同信息直接核对逐项同判。保留类别范围为共用对照。继续此链路需要找到在这一对照下仍可区分的源文绑定和实际提案分歧。[比较结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_OE_CATEGORY_SCOPE_20261119.json)

新增请求 0，账本 14,650 笔、在途 0。19 项检查通过，已核验原冻结协议、72 份源码、TEST 终态、原结果表和曝光回执。回执为 `handoff/revision5_OE_category_scope_terminal_20261119.json`。

## Revision 5 OpenExempt 联邦兜底估值与 B7 路由已结算

复用已按实际请求核验的 60 笔 TRAIN 及 32 笔固定 B8 DEV EV 响应，另沿用 B6/B7 两路比较的 32 笔归档核验。原生估值明确按资产和法条组合独立计算。源文绑定联邦适用、产权、兜底条款及住宅转用额度，已确认的 49 项 TRAIN、29 项 DEV 估值全部匹配参考。四份 TRAIN 和三份 DEV 的已确认独立金额之和可高于一份共用额度。两路共用同一规则，固定 DEV EV F1 在原金额上限基础上达到 64.32% 和 60.26%。

B6 仍只替换分类。B7 新增冲突由 10 项到 4 项，三份来源可采用候选分类，逐来源回放两任务均值差为 +1.56 个百分点，区间跨零。同信息直接核对逐项复现。保留原更新决定，以辖区、资产估值、产权和兜底计算作为后续共用对照。要继续该路线，需要定位共用修正后剩下的可归因候选差异。[比较结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_OE_WILDCARD_REPLAY_20261119.json)

新增请求 0，账本 14,650 笔、在途 0。17 项检查通过，冻结协议、72 份源码、TEST 终态、原结果表和曝光回执已校验。回执为 `handoff/revision5_OE_wildcard_replay_terminal_20261119.json`。

## Revision 5 MAUD 知悉定义的节选约束与读数缩减已结算

复用 36 笔原 TRAIN 与 32 笔固定 B8 DEV 响应，逐笔核验实际请求中的节选。无新增模型请求。原 48 状态消费者可按明示定义将 19/24 TRAIN、11/16 DEV 直接定值。保留其余原预测后，TRAIN 普通教师 9/24→24/24、PARSE 10/24→23/24。DEV 普通教师 8/16→14/16、PARSE 10/16→15/16。合成接口的待读字段总数分别为 5 和 6，固定接口为 9 和 11。缩减来自有限域检查，直接规则逐份复现已确定的标签。

一份 B5 原节选在列完一方的实际知悉后截断，配对母合同续文明确要求双方合理调查。保留原节选参考标签和母合同解释，各自绑定证据。TRAIN 其余未决处为截断／省略及已收书面通知。DEV 的“经合理调查后”变体和“审慎履职时应知”的推定形式在 TRAIN 节选和已对齐母合同中未见匹配，保留为反馈。进一步实测需要可从 TRAIN 观察且能区分同信息直接规则的关系条件。[比较结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_MAUD_KNOWLEDGE_RESIDUAL_20261119.json)

账本 14,650 笔、在途 0，13 项相关检查通过。扩大检查时一项旧源审测试因历史登记缺 `artifact_root` 未通过。冻结协议、72 份源码、TEST 终态、原结果表和曝光回执已校验。回执为 `handoff/revision5_MAUD_knowledge_residual_terminal_20261119.json`。

## Revision 5 OpenExempt B6 分任务选择与 B7 前向回放已结算

在原 B6 只替换分类优于整组替换，公共辖区和金额对照及训练期间的源文检查都选择了该路线。B7 两个程序相同配置的归档读数显示，原始分类 F1 略升，但同样过滤辖区外引文后下降 14.46 个百分点，新增资格冲突 10 项，来自两份来源。B7 逐来源不新增冲突的回放只在另两份使用候选分类。两任务均值相对公共对照增加 0.76 个百分点，区间跨零，直接核对同判。该比较依赖两路归档分类，不改变训练库决定。后续需要有能区别于该直接核对的原生证据。[比较结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_OE_B6_TASK_ROUTE_20261119.json)

核验 32 笔原响应，新增请求 0，账本 14,650 笔、在途 0，23 项检查通过。原冻结协议、72 份源码、TEST 终态和曝光回执已校验。回执为 `handoff/revision5_OE_B6_task_route_terminal_20261119.json`。

## Revision 5 OpenExempt 共同断言位置核查已结算

五组原 TRAIN 投影、32 笔归档响应均按请求、程序和语义绑定核验。限制到两路共同作答位置后，共享约束相容性差异为 0/5。B8 有类型诊断中的相容性改善只需移除原两个无匹配作答的零额断言。共享反馈提案新增一个零额，原共享拒绝仍由这一个新增断言与已有断言解释。保留缺测与原采纳记录。后续需要在共同已答且有源文支撑的位置上发现候选分歧，才有依据重复投影或安排前向比较。[比较结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_OE_MATCHED_PROJECTION_SUPPORT_20261119.json)

新增请求 0，账本 14,650 笔、在途 0，22 项检查通过。原冻结协议、72 份源码、TEST 终态和曝光回执已校验，回执为 `handoff/revision5_OE_matched_projection_support_terminal_20261119.json`。

## Revision 5 ContractNLI 法定披露通知已结算

核验 B3–B5 五项整体原生为正的提案，共 63 个来源－提案配对。应用同一直接源文检查后，两路的通知标签与证据逐项相同。条款链接为原 TRAIN 三份合同补充了引文，两路证据 F1 各提高 6.81 个百分点，分类与同句对照均为 24/24。固定 B8 DEV 上，初版把四个涵盖法定披露的条款判为“未提及”，两路 12/16→8/16。追加的覆盖检查保留这四份原读数，两路恢复到 12/16。此轮复用已经查阅的 DEV 反馈。后续需要有明确的法定触发、通知对象或证据范围分歧，且同信息检查无法复现候选区别。[比较结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_COMPELLED_NOTICE_20261119.json)

新增请求 0，核验 111 笔原 TRAIN 和 32 笔固定 DEV 响应，连续账本 14,650 笔、在途 0。22 项检查通过，原冻结协议、72 份源码、TEST 终态和曝光回执已校验。回执为 `handoff/revision5_CNI_compelled_notice_terminal_20261119.json`。

## Revision 5 ContractNLI 副本制作条件已结算

六份原 TRAIN 合同的固定与合成接口共 12 笔有效读数，两路均未形成完整判断。固定局部读数全空，合成在一份合同识别真实的拍摄禁止，在两处把逆向工程或销毁现存副本误读为制作限制。直接对照答对 4/6，完整 TRAIN 两路 10/24→18/24。固定 B8 DEV 普通教师 6/16→9/16，PARSE 5/16→8/16。保留直接对照；继续探测须有独立原文证据区分同一句内的制作与后续处置，或发现不同原生候选能越过已量化的对照。[比较结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_COPY_SCOPE_20261119.json)

会话 1681 已结算，新增 12 笔 Qwen、31,985 tokens，教师 0。核验原 TRAIN 45 笔、固定 DEV 32 笔，账本 14,650 笔、在途 0，18 项检查通过。原冻结协议、72 份源码、TEST 终态和曝光回执已校验。回执为 `handoff/revision5_CNI_copy_scope_terminal_20261119.json`。

## Revision 5 ContractNLI 分途径标记条件已结算

原合成读数错把并列的书面标记和口头确认读成免标记路径。把途径连到定义后，两种局部接口的九个状态均保持原消费者输出。六份 TRAIN 合同的原程序、旧直接规则、按途径的直接规则为 2/6、4/6、5/6。直接规则与六份源审结论一致；剩一份广义定义和基准“未提及”存在分歧。该范围保留直接对照，合成接口只做了离线验证。后续比较需有独立源审与原生标注一致、且能区别于直接规则的途径。[比较结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_DESIGNATION_ROUTES_20261119.json)

核验 14 笔原响应，新增请求 0，账本 14,638 笔，在途 0。17 项检查通过。原冻结协议、72 份源码、TEST 终态和曝光回执已校验。回执为 `handoff/revision5_CNI_designation_routes_terminal_20261119.json`。

## Revision 5 OpenExempt 所有权候选的局部回放已结算

已核验首轮与纠偏提案的 40 笔原生响应及首轮四笔分配读数。局部合并保护原文已确立的资产所有权；共享反馈 EC 仍有一项引文增益，来源未确立该资产所有权，既有共享筛选仍为 0/2。两路局部 EV 均为 40.42%→44.58%，原预测加同信息公开估值上限可逐来源复现同一 F1。此直接对照在原 32 份 TRAIN 和固定 16 份 B8 DEV 上复用 60 和 32 笔物理响应。固定 DEV 的普通教师 44.37%→49.50%，PARSE 42.08%→44.31%。保留对照和原采纳决定。后续只在找到独立可审的适用条件及可区分的前向原生候选时扩展引文监督。

新增请求 0，账本 14,638 笔、在途 0，37 项检查通过。原冻结协议、72 份执行源码、TEST 终态和曝光回执已校验。回执为 `handoff/revision5_OE_scoped_policy_replay_terminal_20261119.json`。[比较结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_OE_SCOPED_POLICY_REPLAY_20261119.json)

## Revision 5 MAUD 契约前导条件的直接回放已结算

MAUD 负面契约节选可同时包含普通经营分项。只排除前一分项疫情措辞，固定 B8 DEV 两路 9/16→10/16。追加从两项 TRAIN 漏判得到的负面契约前导条件规则后，TRAIN 两路 20/24→22/24，复用同一 DEV 两路 9/16→11/16。两项 DEV 修正均由直接源文判定复现，保留原政策、第一轮回放与冻结结果。此前旁路遮蔽和已收通知的精确模式在固定 DEV 的 16 份合同中均无覆盖。新比较须保留现有直接对照，并提出能独立区分真实候选的约束。[比较结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_MAUD_SECTION_SCOPE_20261119.json)

新增请求 0，账本 14,638 笔、在途 0，27 项检查通过。原冻结协议、72 份执行源码、TEST 终态及曝光回执已校验。回执为 `handoff/revision5_MAUD_section_scope_terminal_20261119.json`。

## Revision 5 MAUD B6/B8 旁路疫情词的配对诊断已结算

原 B6/B8 两份合同的普通经营节选不含疫情词，疫情词在负面契约节选。进入程序在两案答 Yes，原采纳候选答 No。只遮蔽旁路疫情词时两案均改为正确的 No，同宽无关词遮蔽保持原 Yes。B8 知悉标准对两种遮蔽都不变。负面契约编辑项未评分。原 B6 另一份合同的普通经营义务有明示疫情措施，保留其原生正例。后续需用未修改原文的任务局部读法作强对照，单独核对通知定义。[比较结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_MAUD_SIBLING_CUE_20261119.json)

会话 85901 已结算，新增四笔 Qwen、36,001 tokens，教师 0，账本 14,638 笔、在途 0，23 项检查通过。原冻结协议、72 份源码、TEST 终态和曝光回执已校验。回执为 `handoff/revision5_MAUD_sibling_cue_terminal_20261119.json`。

## Revision 5 MAUD B4 空证据字段的同条件比较已结算

三份原 B4 TRAIN 合同的 MAUD 进入程序有一笔共享截断，停在必为空的证据数组。保留常量字段和省略后重建两路各三笔，全部完成，保留八种原生标签组合。逐题复现两路正式采纳候选的输出，原 4/9 提至 6/9，原先完成的两案合计仍为 4/6。作为共用输出恢复保留，原采纳决定保留。后续在已采纳的 B6/B8 候选上复核由询问义务和已收通知引起的实质变化。[比较结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_MAUD_ZERO_EVIDENCE_20261119.json)

ContractNLI B1/B4 的讨论和接触限制各自与人员招揽禁止并列，B3 的接触限制以陪同为条件。保留原招揽规则的适用范围。会话 85301 已结算，新增六笔 Qwen、35,877 tokens，教师 0，账本 14,634 笔、在途 0。22 项检查通过。原冻结协议、72 份执行源码、TEST 终态和曝光回执已校验。回执为 `handoff/revision5_MAUD_zero_evidence_terminal_20261119.json`。

## Revision 5 ContractNLI 招揽限制的 TRAIN 与固定 DEV 已结算

原 24 份 TRAIN 的四份人员招揽正例均可由源文规则判定。原 B4 PARSE 候选连同正确输入的 B5 补跑在相同 15 份合同上由 6/15 到 10/15，四项正例均保留。固定 B8 DEV 零请求回放，普通教师 8/16→14/16、PARSE 11/16→14/16，逐条和跨条款输出完全一致。PARSE 的三个正例有一项退化，其参考条款限制绕过引荐方与联系人交易。查到一份不同条件的 TRAIN 接触限制，未找到同一交易义务的 TRAIN 证据。保留直接对照。后续只有在能用 TRAIN 区分交易限制、接触限制及人员招揽时才扩展规则。[比较结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_NONSOLICITATION_20261119.json)

新增请求 0，账本 14,628 笔、在途 0，20 项检查通过，原冻结协议、72 份执行源码、TEST 终态和曝光回执已校验。回执为 `handoff/revision5_CNI_nonsolicitation_terminal_20261119.json`。

## Revision 5 ContractNLI 按假设限定更新的前向比较已结算

B4 PARSE 候选在 B1–B3 只对员工披露有正向净差，限定该假设后跑固定 B5 TRAIN。进入程序 35/51、完整候选 38/51、限定路由 36/51。限定路由新增正确标签错引使用及复制条款。源文核验拒绝替换并保留另一处证据改进，输出的标签及引文与逐条直接规则一致，均为 35/51。完整候选三份合同各净增一项，招揽限制的三项“未提及”修复解释全部净增。前向比较该假设须保护真实禁止条款的召回。当前无在途任务，原训练库决策保留。[比较结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_SCOPED_UPDATE_20261119.json)

补跑会话 33134 结算三笔、34,542 tokens。首次三笔漏传原逐句编号文本，22,933 tokens 连续记账并排除。账本 14,628 笔，教师 0，18 项检查通过。原冻结协议、72 份执行源码、TEST 终态和曝光回执已校验。回执为 `handoff/revision5_CNI_scoped_update_terminal_20261119.json`。

## Revision 5 ContractNLI 披露许可与限制的同条件比较已结算

四份原 TRAIN 合同的固定与合成接口共八笔读数已结算。两个任务合计原程序 2/8、固定 2/8、合成 3/8、逐条源审直接对照 8/8。合成增量集中在协议存在的限制，第三方许可下降。八笔响应均完成，部分判定因缺少引文或作用域未决而为空。保留原采纳决定及同信息直接对照。后续仅在新发现可验证的引文和命题绑定机制或实际候选选择差异时再启动前向比较。[比较结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_SIGNED_SCOPE_20261119.json)

会话 16978 已结算，新增八笔 Qwen、48,916 tokens，教师 0，账本 14,622 笔、在途 0。原冻结协议、72 份源码、TEST 终态和曝光回执均已校验。回执为 `handoff/revision5_CNI_signed_scope_terminal_20261119.json`。

## Revision 5 ContractNLI 披露对象与例外作用域已复核

24 份原 TRAIN 合同、45 笔归档物理响应已核验。原程序、明示对象规则和跨条款链接分别取得 9/24、10/24、10/24，官方证据 F1 为 29.17%、40.28%、41.27%。唯一新增的跨条款证据也由共用源文的直接规则恢复。B8 原候选已经因原生退化被拒绝，B3–B5 五项原生正向候选的旧决定保留。三份存在用语歧义的合同保留原预测。若能从整份原 TRAIN 合同可靠区分矛盾和未提及，再登记可区别于同信息直接规则的原生预期。[回放结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_DISCLOSURE_OBJECTS_20261119.json)

当前无在途作业，新增请求 0，账本 14,614 笔，18 项相关检查通过。原冻结协议、72 份执行源码、TEST 终态和曝光回执已校验。回执为 `handoff/revision5_CNI_disclosure_objects_terminal_20261119.json`。

## Revision 5 ContractNLI 共享披露定义改名已结算

两份原 TRAIN 合同中，员工与外部顾问通过同一已审定义接入披露许可。仅改名并重算偏移，复用原 B3 两路四笔原题响应，新增四笔原生请求。两路四项标签均保持正确，证据集合各改变两项。进入程序证据 F1 为 25.00%→43.33%，候选为 0%→25.00%。直接按同一原文链接许可和定义为 86.43%，四项均有完整证据。原更新决定保留。后续需要能找到互相竞争的定义或明确的披露例外，才值得比较新共同约束。[比较结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_DEFINITION_ALIAS_20261119.json)

会话 23921 已结算，新增四笔 Qwen、76,355 tokens，教师请求 0。连续账本 14,614 笔、在途 0，16 项检查通过。原冻结协议、源码、TEST 终态和曝光回执已校验。回执为 `handoff/revision5_CNI_definition_alias_terminal_20261119.json`。

## Revision 5 M2 OpenExempt 原生冲突归因已结算

复用 B4、B7 共 12 笔原题和编辑响应。逐项做三次留一复核，24 项共享上限冲突均只能通过移除其中一份编辑读数消除。整组删除原题冲突索赔会删除 20 项预测、误删 7 项原生正确预测，四组中三组 EV F1 下降。可归因删除规则在四组全部等于同信息本地筛选。当前金额编辑链已经核验到原题指标，无理由再按相同冲突直接修原答案。后续需要新的作用域或候选证据，能够定位原任务中的错误并与同信息对照产生不同采纳决定。[重放结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_OE_CONFLICT_LOCALIZATION_20261119.json)

新增请求 0，账本 14,610 笔、在途 0，24 项检查通过。原冻结协议、72 份源码、TEST 终态和曝光回执已校验。当前无待结算任务，回执为 `handoff/revision5_OE_conflict_localization_terminal_20261119.json`。

## Revision 5 M2 OpenExempt B7 同预算选例已结算

在不同于 B4 校准的原 B7 TRAIN 来源上比较句首先验和原生分歧选例，每路两笔，均复用相同的两个原始 EV。四个共同位置上，句首编辑两路均无冲突。原生分歧编辑揭示进入程序一处未改资产冲突，候选在共同位置兼容，在全部正额位置仍有两处冲突。共享枚举和直接检查一致。B4 上两条规则同选已知有效编辑，B7 上原生分歧更有信息。保留原 B7 采纳决定，不重复此句首先验。下一步需要新的候选级信号或有来源支持的共同约束，能与直接选例区分并产生前向原生效应。[比较结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_OE_EDIT_ACQUISITION_20261119.json)

会话 88756 已结算。新增 4 笔 Qwen、44,154 tokens，教师请求 0。账本 14,610 笔、在途 0，21 项检查通过。原冻结协议、72 份源码、TEST 终态和曝光回执已校验。回执为 `handoff/revision5_OE_edit_acquisition_terminal_20261119.json`。

## Revision 5 M2 OpenExempt B4 原生金额编辑已结算

原 B4 同一 TRAIN 来源的两件资产分别加一美元，其余原文和原生请求保持。复用两笔原始 EV，新增四笔。两路共有四个完全可比的辖区内资产引文位置。第一种编辑在进入程序触发四项冲突、候选触发两项，第二种两路均兼容。单例金额上限无违规。共享枚举等于同信息直接检查，且候选仍有冲突，保留原先所有权断言拒绝。后续比较需要能在执行预算相等时预测哪种可实现编辑更有信息，并有能区分更新选择及前向原生收益的候选。[比较结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_OE_NATIVE_AMOUNT_EDITS_20261119.json)

会话 56651 的四笔请求均已结算。汇总零计数错误已离线修复，无重发。新增 32,837 Qwen tokens，教师 0，账本 14,606 笔、在途 0。19 项相关检查通过，原冻结协议、源码、TEST 终态和曝光回执已校验。终态为 `handoff/revision5_OE_native_amount_edits_terminal_20261119.json`。

## Revision 5 M2 OpenExempt 源文选例和跨任务作用域已核对

复用 B3、B4、B7、B8 的原始候选、进入程序及 64 笔原生响应。扩大金额编辑语法后，9 个正向母来源的合法编辑覆盖从 1 个到 7 个，共 24 个编辑候选。B7 原有两条候选冲突在分开绑定 EC、EV 所有权证据后均保留。B8 简化蕴含对两路各产生四条冲突，四个位置均为 EC 未确立、EV 已确立所有权，按各视图补全后冲突均消失。直接检查和共享枚举在 81 个状态上一致。下一步仅在有可区分的实际更新预期时，使用更贴近当前候选错因的源文组发起最小比较。新编辑仍只有源文证据。[聚合证据](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_OE_M2_SOURCE_PLACEMENT_20261119.json)

新增请求 0，账本 14,602 笔、在途 0。24 项检查通过，原冻结协议、72 份执行源码、TEST 终态和曝光回执已校验。当前无待结算任务，回执为 `handoff/revision5_OE_M2_source_placement_terminal_20261119.json`。

## Revision 5 OpenExempt 宾州原 B8 DEV 比较已结算

固定公开渲染模板将资产组及所有权绑定到申报人，复现原八个 TRAIN 视图并覆盖原 B8 DEV 全部 10 个宾州视图。与共用所有权锚定及同一消费者的固定两字段对照相比，关系接口 EV F1 为 57.46% 对 68.25%，EC 为 76.44% 对 77.40%。固定字段原生分数逐题达到源审执行，10 个输出中 9 个完全一致。保留共用锚定与强对照。下一步回到 M2 的真实候选和共享证据，需找到能改变原生正向候选采纳、且能够与同信息直接筛选区分的缺口。[比较结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_OE_SCOPED_FORMS_DEV_20261119.json)

会话 87439 已结算。新增 20 笔 Qwen、123,613 tokens，教师请求 0。连续账本 14,602 笔、在途 0。14 项检查通过。原冻结协议、72 份执行源码、TEST 终态和曝光回执已校验。回执为 `handoff/revision5_OE_scoped_forms_DEV_terminal_20261119.json`。

## Revision 5 OpenExempt 宾州资产形态关系已结算

真实配对使用原四份已源审宾州 TRAIN 的八个 EC/EV 视图。固定字段与关系接口使用相同原文、资产索引、所有权证据和消费者。源审后 EC F1 为 61.13% 和 60.24%，EV 为 36.61% 和 76.61%。回顾性词项规则复现全部 24 条源审字段组，EC 为 74.82%、EV 为 82.86%。原 B8 DEV 每类五个宾州视图均可解析资产，现有所有权锚定只覆盖每类一份。仅检查 DEV 公开输入。后续先按原渲染模板对齐所有权状态并给两个读器共用，再决定比较范围。[结果表](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_OE_SCOPED_FORMS_20261119.json)

会话 7748 已结算。新增 16 笔 Qwen、99,151 tokens，教师请求 0。账本 14,582 笔、在途 0，10 项检查通过。原冻结协议、72 份执行源码、TEST 终态与曝光回执已校验。回执为 `handoff/revision5_OE_scoped_forms_terminal_20261119.json`。

## Revision 5 OpenExempt 资产锚定与逐项输出已结算

复用三份 TRAIN 的 18 笔原始读数。资产名与估价通过同一源文引文绑定。逐项执行保留所有可行补全均支持的引用和值。两项联合改善三个视图，再对齐两笔只差开头冠词大小写的引文后改善另一笔 EV。四项改善集中在一份母来源。固定记录平均官方 F1 由 38.89% 提至 EC 63.89%、EV 68.89%。合成记录保持 EC 16.67%、EV 38.89%，相关资产分类仍为空。保留共用解码和逐项确定性控制。只有找到可核验且能改变原生结果的分类绑定，才用新候选开展同条件比较。[比较结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_OE_CLAIM_PROJECTION_20261119.json)

新增请求 0，账本 14,566 笔、在途 0。17 项相关检查通过。原冻结协议、72 份执行源码、TEST 终态与曝光回执均已校验。当前无待结算任务，回执为 `handoff/revision5_OE_claim_projection_terminal_20261119.json`。

## Revision 5 Airline 免费行李额度分配已结算

编译原规则表，并按单件超重和超尺寸取最大值后可省下的费用，分配免费额度。穷举同一输入的所有额度分配，逐题复现最优总价。在原 24 份 TRAIN 上，原进入程序、输入顺序、仅按超重减免排序、联合分配分别答对 7、18、21、24 份。封存规则用于原 B8 DEV，分别答对 2、11、13、15 份，未覆盖的一个线路沿用原预测。七组 TRAIN 交换行李位置的证据来自规则推导，尚无改序后的读数。共用修复成立，共享监督独立收益未建立。[比较结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_AIRLINE_ALLOWANCE_20261119.json)

复用 40 笔历史响应，新增请求 0，账本 14,566 笔、在途 0。19 项检查通过，原冻结协议、72 份执行源码、TEST 终态和曝光回执均已校验。回执为 `handoff/revision5_Airline_allowance_terminal_20261119.json`。当前无待结算任务。下一步比较应保留精确分配对照，并先找到会影响学习选择的源文约束。

## Revision 5 M1 ContractNLI 独立开发与第三方取得已结算

六份原 TRAIN 合同的独立开发与第三方取得共 12 项判定。固定和合成布局在共同消费者的 729 个状态上等价，原进入程序答对 10 项，固定和合成各答对 2 项。回顾性直接规则把明示时间与同一例外分项绑定，并检验第三方来源，12 项均正确。合成接口未产生独立收益。[比较结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_INDEPENDENT_ROUTES_20261119.json)

会话 80796 已结算，新增 12 笔 Qwen、52,186 tokens，教师请求 0。账本共 14,566 笔、在途 0。21 项相关检查通过，原冻结协议、72 份执行源码、TEST 终态与曝光回执通过校验。回执为 `handoff/revision5_CNI_independent_routes_terminal_20261119.json`。当前无待结算任务。保留直接规则作为上述条款结构的强对照。

## Revision 5 M1 Diversity B8 DEV 同信息对照已结算

原 B8 DEV 的 16 笔合成接口读数全用固定州籍坐标及合成金额关系。原 TRAIN 字面金额规则从两条原引文修复了错误合计，原生正确数由 14/16 到 16/16。固定与合成消费者使用相同原文州籍和金额后均为 16/16，原生与中间判断逐题一致。这个差异由共用解析解释。[对照结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_M1_DIVERSITY_DEV_LITERAL_20261119.json)

新增请求 0，账本 14,554 笔、在途 0。8 项相关检查通过，一个旧 RR 检查缺其 TRAIN fixture。原冻结协议、72 份执行源码、TEST 终态和曝光回执均已校验。结算入口为 `handoff/revision5_M1_diversity_DEV_literal_terminal_20261119.json`。当前无待结算任务。该语法范围内，同信息固定对照已达到原 B8 DEV 的原生满分。

## Revision 5 M2 ContractNLI 口头信息定义回放已结算

B3 与 B4 的普通教师均只收到原生汇总，普通、M2 两臂分批采纳共同程序。B3 新增两起有源文支持的漏判，B4 修复两起。独立开发回放用原文链接口头披露、保护条款及同一披露方。B3 九份合同的原生正确数由 7→9，同句核查为 8。后续 12 份 TRAIN 分类 11/12 固定，答对才计入的证据 F1 由 65.28% 到 83.33%，同句为 73.61%。共享、逐例与直接证据核查在可证范围内等价。[回放结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_ORAL_SCOPE_20261119.json)

用封存 TRAIN 规则复核原 B8 DEV 的单项假设，16 份只命中两份，跨条款与同句结果完全一致。复用 45 笔 TRAIN 与 32 笔 DEV 执行响应，新增请求 0，连续账本 14,554 笔、在途 0。25 项相关检查通过，原冻结协议、72 份执行源码、TEST 终态与曝光回执均已校验。结算入口为 `handoff/revision5_CNI_oral_scope_terminal_20261119.json`。当前无待结算任务。这个链路的下一步需有可独立验证的新作用域，且在同信息强对照下能给出不同的更新决定。

## Revision 5 M1 ContractNLI 明示标记条件已结算

原 24 份 TRAIN 合同的进入程序全答蕴含，实际答对 5/24。六份定向比较中，固定坐标在两个局部字段全部弃读，答对 0/6。合成关系答对 1/6，原进入程序也答对 1/6。仅采纳固定读器在六案都给出的普遍标记断言，仍为 1/6。回顾性字面规则用同一原文在 24 份中覆盖五份并全部答对。两路消费者在全部 27 个声明状态保持等价。[配对结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_DESIGNATION_20261119.json)

会话 48056 已结算，12 笔 Qwen 请求、50,969 tokens，教师请求 0。账本共 14,554 笔、在途 0，21 项检查通过，原冻结协议、72 份执行源码、TEST 终态和曝光回执均已核验。结算入口为 `handoff/revision5_CNI_designation_terminal_20261119.json`。当前无待结算任务。律师读器继续比较的依据应来自字面规则未覆盖、且原文作用域可独立核实的结构。

## Revision 5 M1 OpenExempt 逐件部分执行已结算

复用三份原 TRAIN 来源的 18 笔物理响应，保留四笔原解码拒绝。独立开发版本在固定程序的资产独立性下，使用相同的原文资产绑定和源审核查固定及合成记录，再逐件释放对未决输入不变的输出。整案核查全部弃答。固定记录的 EC 和 EV 平均 F1 均为 38.89%，合成记录为 16.67% 和 38.89%。两路六个视图中五个输出相同，另一份 EC 视图中固定记录多恢复两件资产。收益来自共用的逐件执行。[比较表](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_OE_ASSET_PROJECTION_20261119.json)

新增 0 笔请求，账本 14,542 笔、在途 0，32 项检查通过。原冻结协议、72 份执行源码、TEST 终态及曝光回执均已校验。恢复时先查 `handoff/revision5_OE_asset_projection_terminal_20261119.json`。当前无待结算任务。这个分支继续推进所需的新依据，是配对读数之间存在可由原文验证的新增差异，并且该差异在共用逐件执行后仍能改变原生结果。

## Revision 5 M2 MAUD 嵌套例外累积核对已结算

B6 晋级的普通和 PARSE 式程序在各自同版本、同读取契约下，分别在 B6 贷款项答 `No`、B8 网点项答 `Yes`；原生参考均为 `No`。四笔归档模型响应已核验。两种统一作用域口径各自只允许两案同答，因此两个观察单独有效，累积无法共存；同信息相等检查作出相同判定。加入源文支持区分的第三种候选口径，明确单项例外计入且“不构成违反”说明归为另一类，两路混合读数重新相容。已查阅 MAUD 原论文和版本发布说明，未确定这两种写法的官方标注取舍。[累积核对](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_MAUD_NESTED_EXCEPTION_JOIN_20261119.json)

结算入口 `handoff/revision5_MAUD_nested_exception_join_terminal_20261119.json`。保留原生标签、原文两种写法和三种口径的敏感性核验。当前无待结算任务，新增请求 0，账本 14,542 笔、在途 0。31 项检查通过，原冻结协议、72 份源码、TEST 终态与曝光回执均已校验。

## Revision 5 MAUD 母合同定义覆盖核对已结算

逐份匹配原 24 份 TRAIN 母合同与 24 笔留存响应。六份普通经营定义中，一份在分号截断。母合同续段明确把符合条件的疫情应对纳入该定义。同信息直接规则将旧 `No` 恢复为参考 `Yes`。在 48 项原 TRAIN 契约问题中，旧程序答对 41 项，简单关键词诊断 44 项，补定义和区分作用域后的回顾性直接重放 46 项。剩余两项标注差异都出现在禁限条款内的具体贷款或设施例外，需独立核实作用域后才可作为学习依据。[母合同核验](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_MAUD_PARENT_DEFINITION_COVERAGE_20261119.json)

结算入口为 `handoff/revision5_MAUD_parent_definition_coverage_terminal_20261119.json`。新增请求 0，账本 14,542 笔、在途 0，17 项检查通过。原冻结协议、72 份归档源码、TEST 终态及曝光回执通过核验。保留恢复定义作为同信息对照，当前没有新任务队列。

## Revision 5 M2 跨组累积证据审计已结算

复用此前 16 条及新增核对的 19 条早期 TRAIN 验证，合计 35 条记录、82 笔去重物理响应。三组候选、语义和读取契约完全相同的重复记录，各自已有一次验证覆盖合并后的全部响应。其拒绝均已在单组出现。即使将读取契约不同但语义作用域相同的记录放在同一诊断中，也没有只在累积后才发现的冲突。35 条记录的二元与联合检查对已有读数全部同判，另有六对记录因语义作用域不同未合并。[审计表](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_M2_CUMULATIVE_AUDIT_20261119.json)

结算入口为 `handoff/revision5_M2_cumulative_audit_terminal_20261119.json`。新增请求 0，连续账本 14,542 笔、在途 0。17 项检查通过，原冻结协议、72 份归档源码、TEST 终态和曝光回执通过核验。继续 M2 需有不同的、可用原文核实的关系以及可测的更新选择差异。

## Revision 5 M2 ContractNLI 返还与留存共享筛选已结算

七份原 TRAIN 合同的终止返还及留存条款已分别核实。复用 B3–B5 五个本批原生正收益提案的 31 笔去重响应，原流程采纳三个提案。B5 PARSE 式提案当批分类增益 5.88 个百分点，先前 TRAIN 增益 2.45 个百分点，同时在一份明文禁止留存的合同新增错误许可。以新增冲突作筛选时，共享与同信息直接规则回顾性重放会作出相同拒绝。替换原合同一处归档例外的四查询离线构造也得到相同的直接规则签名。[筛选重放](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_M2_CNI_DISPOSITION_RETENTION_20261119.json)

结算入口 `handoff/revision5_M2_CNI_disposition_retention_terminal_20261119.json`。新增请求 0，账本 14,542 笔、在途 0。17 项检查通过，原冻结协议、72 份归档源码、TEST 终态与曝光回执均已复核。恢复后只在找到有来源证据、可实测区分解释路径的关系时启动新的 M2 比较。

## Revision 5 ContractNLI 终止触发覆盖核对已结算

原 24 份 TRAIN 合同及对应物理响应已复核。复用 21 份原文完全匹配的旧源审，20 份原图卡未闭合的事实保留。七份原文明确把返还或销毁绑定到协议或所涉关系终止，三份的相应图边缺少终止标签。此前未命中字面规则的五份标注正例中，一份明确写明服务终止，直接规则可恢复。另三份的引文分别是交易未继续、关系未建立、目的完成，合同另列协议终止条件。最后一份只受请求触发。十份请求触发合同的参考标签为一份蕴含、九份未提及。[覆盖审计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_TRIGGER_COVERAGE_20261119.json)

恢复时核对 `handoff/revision5_CNI_trigger_coverage_terminal_20261119.json`。当前无待结算任务，连续账本 14,542 笔、在途 0，新增模型请求 0。继续比较需有可独立核实的不同作用域结构或其他源文支持的实现缺口。11 项相关检查通过，原冻结协议、72 份源码、TEST 终态和曝光回执已核验。

## Revision 5 M1 ContractNLI 返还与销毁义务配对已结算

原共同程序在 24 份 TRAIN 合同上均判定终止时须返还或销毁，实际答对 11/24。针对六份原 TRAIN 合同，两路使用同一完整合同和原生证据索引。合成接口把终止条件及其是否作用于同一项义务合成一个关系，保持声明域 81 个状态的消费者输出。固定与合成各答对 3/6。把错答和弃答的证据分记为零后，固定的平均证据 F1 为 17.86%，合成为 32.78%。原生证据 F1 为 17.86% 和 49.44%，其中 16.67 个百分点来自一份空引用弃答。合成读器在一份合同额外找到了真正受终止触发的返还条款。[配对与错因](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_M1_CNI_DISPOSITION_SCOPE_20261119.json)

针对这六种已审结构构造的窄字面对照答对 6/6，证据 F1 为 88.33%。其余原 TRAIN 只扫描语法命中。当前没有待结算任务。继续该链路需先找到现有 TRAIN 中超出显式同句或连续分项规则、同时有独立原文证据的结构。会话 64817 已结算，12 笔 Qwen 请求、39,901 tokens，教师调用 0。账本 14,542 笔、在途 0，11 项检查通过，原冻结协议、72 份源码、TEST 终态和曝光回执均已核验。结算入口为 `handoff/revision5_CNI_disposition_scope_terminal_20261119.json`。

## Revision 5 M1 ContractNLI 跨条款证据配对已结算

按原文中的代表人定义和使用位置筛查原 24 份 TRAIN 合同，六份入组。两路读取同一完整合同和原生证据索引，均可分别引用许可条款和外部定义，消费者的 36 个声明状态逐项保持等价。固定坐标答对 0/6，证据 F1 为 16.67%。合成关系答对 5/6，证据 F1 为 37.62%，其中两份许可结论有独立源审支持。原多任务共同程序答对 6/6，证据 F1 为 58.33%。[配对结果与错因](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_M1_CNI_LINKED_EVIDENCE_20261119.json)

两份必须跨条款引用的合同中，合成读器在一份补齐两处漏引，证据 F1 从原程序的 50% 升至 85.71%。另一份两路均选错条款，把保密限制当成另节的明示许可。三份合成输出标签正确但引用不支持判定，另有一份因重复引用同一索引而拒绝解码。复查 24 份原 TRAIN 合同后，这两种已知措辞各匹配一份。按原文直接连接定义与许可的回顾性规则答对 2/2，平均证据 F1 为 90%。当前无待结算任务。若继续此链路，先找现有 TRAIN 中的其他条款结构，再明确同信息对照的可测差异。[字面匹配预检](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_M1_CNI_LINKED_LITERAL_PREFLIGHT_20261119.json)

会话 70296 已结算，12 笔 Qwen 请求、99,412 tokens，教师请求 0。连续账本 14,530 笔、在途 0。原冻结协议、72 份源码、TEST 终态及曝光回执已校验；20 项定向检查通过，历史持久化检查仍有一项缺 `artifact_root`。结算入口为 `handoff/revision5_CNI_linked_evidence_terminal_20261119.json`。

## Revision 5 M2 二元与联合筛选审计已结算

复用 16 组有真实读数的历史 TRAIN 投影，逐笔核验 45 笔去重后的物理响应。12 组伴随正向原生候选增益。每条验证记录均只有一组读数。16 组的完整签名都可以由其所有二元投影重建，二元筛选和联合筛选在留存读数上的判定全部一致。[筛选审计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_M2_PAIRWISE_SCOPE_20261119.json)

在一份原 B7 TRAIN 来源中，两件资产的估值有原文引文，所有权均未决。只编辑一处估值，在受控的所有权条件投影中，独立补全允许 12 个签名，二元闭包允许 6 个，共享补全允许 4 个。同信息的直接换算与求和可以精确恢复这 4 个签名。本次没有新增模型请求，连续账本为 14,518 行、在途 0。17 项相关检查通过，原冻结协议、72 份源码、TEST 终态及曝光回执均已校验。当前没有待结算任务。恢复时从 `handoff/revision5_M2_pairwise_scope_terminal_20261119.json` 核对结算状态；只有找到可与同信息强对照产生不同选择的源文证据，才登记新的定向比较。

## Revision 5 OpenExempt B7 跨原生任务共享筛选已结算

按基准求解器确认，同一案件、同资产、同辖区的一笔正额估值只会来自分类任务的合格引文集合。对原 B7 四份 TRAIN 来源复用原生读数。仅比较两个程序均明示资产的读数，并在同一辖区内绑定原引文。候选和进入程序各有 10 项正额估值断言。候选两项与同资产已答的分类冲突，进入程序无冲突，逐例补全两路均允许。官方 TRAIN 参考定位了其中一项估值多报，以及一项两路共有的分类漏报。

原 B7 字面读数全未知，历史更新因此保留旧程序。用原教师程序的同一所有权政策补测两个字面槽，均准确恢复估值、保留所有权未知。此开发比较中，原生和逐例补全采纳候选，共享筛选保留进入程序。直接检查“正额估值蕴含分类合格”的同信息强对照也保留进入程序。证明在九种已知和未知的端口组合中，此公共蕴含与共享枚举完全等价。

复用原 B8 四份前向 TRAIN 的同条件读数，保留程序相对候选的 EC F1 变化为 +14.17 个百分点，EV F1 为 −3.75，等权平均 +5.21，配对描述性区间 [−2.50, 14.38]。该正向结果来自回顾性四来源比较，且公共蕴含对照作出相同选择。当前不构成 M2 相对该强对照的独立收益。

会话 79942 已结算，新增 2 笔 Qwen 字面读取、11,716 tokens，原生与教师新增 0。连续账本 14,518 行、在途 0。20 项相关检查通过。原冻结协议、72 份源码、TEST 终态及曝光回执通过校验。[B7 筛选与 B8 前向结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_M2_OE_JOINT_NATIVE_GATE_20261119.json)

## Revision 5 MAUD 三值调查关系配对已结算

用同一消费者的调查条件合成三值关系，保留原实际知悉字段。层叠的普通合取会在一项未知时输出假，三值关系保留未知。逐一证明声明域中 48 个状态的原案输出等价。候选读取字段由四个减到两个。同一 9 份 TRAIN 节选每份新增一笔读数，保留已结算的 18 笔固定和原合成对照。27 笔请求逐份确认原文、定界、模型参数一致。

三值关系为 3/9，与原合成接口逐题一致，固定坐标为 4/9。四份实际知悉定义仍均未答出。三值读器在其中两份正确识别无需调查，但把引文明确写出的实际知悉字段读成假。在两路都采用同一条引文字面修正的离线重放中，三值为 5/9，固定为 6/9。保留新代码及负结果，原库未采纳候选。

会话 14283 已结算，9 笔 Qwen 请求、10,782 tokens，教师请求 0。原合成和固定坐标的九笔请求分别使用 13,367 和 11,053 tokens。连续账本 14,516 行、在途 0。7 项相关检查通过。原冻结协议、72 份归档源码、TEST 终态和曝光回执已核验。[三值关系实测](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_M1_MAUD_TERNARY_RELATION_20261119.json)

## Revision 5 MAUD 同一定义范围配对已结算

逐笔确认原四份 TRAIN 合同的八笔标量读数都正常返回 `unread`。四案原有索引都保留了足以引用定义与调查条件的片段。独立开发版保留每份任务给定的完整节选，按公开定义语句合并人员列表与共用限定，固定和合成读器共用同一输入。对照包含原四案、四份经源审确认范围完整的实际知悉定义，以及一份带局部调查例外的定义。最后一案的原索引曾切开人员列表与调查条件，新版恢复完整引文。

原四案固定读器答对 3/4，合成答对 2/4。局部调查例外案均答对。四份实际知悉定义均未答出，整组固定为 4/9、合成为 3/9。固定读器两次已定位正确条款并读出调查条件缺席，但把原文明确写出的实际知悉留为未知。离线复用已引用的定义，仅填入该字面字段，两次均由原消费者解码为实际知悉。合成读器在这四案均直接返回 `unread`。这次配对未发现合成关系的独立原生收益。

会话 90494 已结算，18 笔 Qwen 请求使用 24,420 tokens，教师请求 0。连续账本 14,507 行、在途 0，21 项相关检查通过。原冻结协议、72 份归档源码、TEST 终态、曝光回执已核验。[配对结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_M1_MAUD_DEFINITION_SCOPE_20261119.json)

## Revision 5 ContractNLI 同一许可事件配对已结算

原四份 TRAIN 合同的披露读数曾将定义段当作许可，或将相邻条款的告知义务当作访问授权。独立开发版保留原合同全文和消费者，按原文动作及其语法续接生成可引用条款，两种表示共用输入。四份合同的候选条款数由 1、4、6、15 各缩为 1，均保留原先独立审定的条款，八份参考解码通过。

两路在能独立证实员工披露许可的三份合同上均答对，证据 F1 均为 100%。四案官方分数中，固定坐标答对 3/4、证据 F1 为 75%，合成关系答对 4/4、证据 F1 为 100%。差值全部出在第四份合同。该案允许访问的文字只列出代理人与专业顾问，原文源审未建立员工关系。固定读器保留未决，合成读器断言了接收方员工关系，恰与官方标签一致。这一题不能作为源忠实的 M1 独立收益。原全 17 假设结果作为历史参照，本次比较只对员工披露假设计分。

会话 67586 已结算，新增 8 笔 Qwen 请求、15,676 tokens，教师请求 0。账本共 14,489 行、在途 0。逐笔核对同信息请求、生产解码、72 份冻结源码、TEST 终态及曝光回执。定向检查通过 36 项，3 项历史持久化检查因旧检查点缺少 `artifact_root` 失败。[配对结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_M1_CNI_OPERATIVE_ANCHORS_20261119.json)

## Revision 5 Diversity 州籍复用与前向归因

24 个原 TRAIN 来源的 96 份实测候选中，固定州籍坐标 192/192 与独立源审一致，重放可把同一人、同一引文的坐标合并为 136 个槽位。48 份固定州籍响应的完整生产解码逐项一致。这是已保存响应的坐标复用核验，尚未测量修改读器的 token 成本。直接合成州籍关系的忠实读数为 63/96，33 次误读形成的关系仍与某种州籍分配相容，等价图的一致性检查无法将这些误读排除。

前向采用合成接口的 15 次判断中，14 次保留固定州籍坐标，1 次在 B2 使用合成州籍关系。那一案具备州籍多样性、金额未达门槛，所选接口把两个条件都读反，整题仍答对。只替换为同来源、同金额接口候选的正确州籍读数，保留原金额读数，答案变错。这一命中来自两处源语义误读的抵消。复用 96 份已结算响应，新增请求 0，账本 14,481 行、在途 0。原冻结协议、源码、终态和曝光回执通过校验。[前向归因结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_M1_CITIZENSHIP_REUSE_20261119.json)

## Revision 5 OpenExempt 资产披露覆盖比较已结算

原 B8 提案的四来源平均原生增益全部来自一份 TRAIN 来源。原筛选要求字面占有措辞，遗漏该来源中仅披露金额、经 EC 和 EV 独立原文审核仍未确定所有权的资产。该资产的精确 EV 引文和金额匹配由 1 项增至 2 项。整案 EV F1 从 30% 升至 50%，只交换这一项资产得到 40%。按公开输入的实际辖区绑定，新增独立版本只编辑该资产的一处估值。

候选两笔字面读数都保留所有权未知，并准确返回估值。原进入程序和 B8 候选在同语法、同事实的四个投影槽中全部读为零，各保留 1/16 个逐例补全签名、0/2 个共享签名和 0/1 个固定单解释签名。原配对筛选要求进入程序有共享见证，因此本次未触发额外拒绝。实测覆盖了遗漏的获益来源，结论仍不支持该候选产生独立的共享筛选收益。

会话 54039 已结算，新增 10 笔 Qwen 请求、60,010 tokens，复用原生预测与评分。连续账本 14,481 行，在途 0。原冻结协议、72 份冻结源码、TEST 终态及曝光回执通过校验。本次交接回执为 `handoff/revision5_OE_disclosure_terminal_20261119.json`。[配对结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_M2_DISCLOSURE_COVERAGE_20261119.json)

## Revision 5 金额关系极性对比已结算

原 96 笔 Diversity TRAIN 候选覆盖 304 个局部读数，全部引用对应关系的完整原文。合成金额关系中，未达标出现 7 次误读、7 次正确，达标的 42 次判断全部正确。B3 有一次未达标误判影响了实际前向答案。

对原 B3 和 B4 的全部 6 个 Diversity TRAIN 来源，使用同一消费者编译严格金额谓词的逻辑补。单诉求的 78 个状态和同对诉求的 6084 个状态逐一验证了原界值、未知和解码结果。逐笔核对了六对物理请求，模型、采样、输入和 JSON 语法一致，唯一改动在系统提示的金额极性部分。逻辑补原生答对 2/6，1/6 的局部关系全部忠实。原严格金额关系为 4/6、4/6，同信息的固定坐标为 4/6、3/6。原 B3 错误未修复。相对原金额关系，逻辑补修正 1 题、退化 3 题，原本正确的 4 个达标局部关系全部误读。保留该有限域试验的负结果并维持原库。

会话 64542 已结算，新增 6 笔 Qwen 请求、6934 执行器 tokens、教师请求 0。连续账本 14471 行，在途 0。复核了原冻结协议、归档源码 72 文件、曝光回执和 TEST 终态。终态回执为 `handoff/revision5_M1_amount_polarity_terminal_20261119.json`。[聚合结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_M1_AMOUNT_POLARITY_20261119.json)

## Revision 5 同信息金额提取对照

对原 96 笔 TRAIN 候选做离线重放。使用同一有限句法从 112 条已核对的金额引文提取有序金额，将其送入现有固定坐标或合成关系解码器。保留每笔实际州籍读数。固定州籍坐标时，固定金额坐标原生正确数从 16/24 到 24/24，合成金额关系从 21/24 到 24/24。合成州籍关系时，两种金额表示为 19/24 和 17/24。沿原前向路线，只替换合成路线的金额输入，结果为 18/21 到 19/21。共用的原文金额提取已经解释了固定州籍条件下的收益，现有对比未识别出金额关系合成的额外原生收益。此处为保存响应的 TRAIN 解码重放，新增模型请求 0。没有安排 DEV 或新的独立验证。[同信息对照](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_M1_LITERAL_AMOUNT_CONTROL_20261119.json)

## Revision 5 路由和退化定位

M1 复用原 96 笔 TRAIN 候选，在 B2–B8 的 21 个前向来源上，只用每批之前的完整匹配母来源校准。将局部源忠实率按关系类型分解，再按目标接口中各类关系的数量计算联合分数。该规则逐题选出原路线，原生正确 18/21，合成接口实际使用 15 次，其中 13 次通过全部局部源审。同一候选池的纯原生排序得到 16/21，改变 3 条路线并带来 2 题退化。现有重放结果不支持为了这一排序变更追加读数。

M2 两路定向修订的四个 EV 输出逐项一致。相对 B8 的 8.75 个百分点 EV 损失全部来自一份未参与共享冲突构造的 TRAIN 母来源，其 EV F1 从 61.67% 降至 26.67%。少了 5 项准确引文金额、新增 2 项，净少 3 项，涉及 3 个资产。在原共享冲突所属来源上，先前提案的 EC 从 0 提高到 1/3，两路修订均回到 0，EV 均为 1/3。退化来源没有既有、已证实的仅原文所有权审计卡，不能用本次比对归因到所有权断言。复用的原生成绩和输出共同表明，这次修订没有保住目标来源上的收益。

本轮新增请求 0，连续账本 14465 行、在途 0。分析入口为 `handoff/revision5_m1_component_and_oe_loss_localization_20261119.json`。[聚合结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_SOURCE_LOCALIZATION_20261119.json)

## Revision 5 已结算结果

新方案的原请求链路复核及定向实测均已结算。会话 92397 的两路输出均已封存；原汇总读错教师用量字段，使用同一账本和已结算响应离线补写终态。代码已修复，并核验再次打开该终态不会派发请求。新增 2 笔教师及 16 笔 Qwen，共 37,093 教师 tokens 和 128,148 执行器 tokens，连续账本 14465 行、在途 0。

复测原四个 OpenExempt TRAIN 来源，按逐例独立补全反馈修订的程序 EC/EV F1 为 27.50%/31.67%，共享解释反馈为 28.125%/31.67%，原 B8 为 27.50%/40.42%。两路均低于原 B8 的原生均值，原生收益门未进入投影筛选。两路 EV 都覆盖 11 个正确资产键，但同一资产的引文和金额全部匹配由 B8 的 9 项降为 6 项。共享组的 3 个精确金额后缀别名恢复后，既有 F1 结论相同。保留原技能库和比较条件，当前没有可采纳的细化结果。

[M1/M2 原请求核对、定向 TRAIN 结果与哈希](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CONTINUATION_AUDIT_20261119.json) · [更新后的论文初稿](../reports/legal_skill_convergence_20261117/paper/METHODS_AND_DEVELOPMENT_RESULTS.md)

## Revision 5 证据核对与启动记录

M1 核对了 24 个 Diversity TRAIN 来源的全部 96 笔候选读数，其中 15 笔按原请求精确复用。固定坐标 10/24、合成候选 37/72 完整源忠实。逐批核对 21 个前向来源的实际路线和记分，15 次使用合成接口、6 次使用普通程序，共答对 18 题。保留原同语法、同校准条件的控制结果，不将事后逐题上界当策略。

M2 核验 80 笔正式教师原请求和响应，CLI 均为 gpt-6.1-sol/high。OpenExempt 的 B4–B8 共同教师和 PARSE 收到相同的既往语义反馈。正式 M2 筛选评估普通教师已测的同一提案。B8 条件投影中旧程序和新提案均不兼容共享签名，实际没有独立共享拒绝。独立反馈小试的两笔原请求只有解释反馈不同。共享反馈提案通过字面事实且原生正向、独立签名保留 2/16、共享签名保留 0/2。共享筛选因此保留原程序，独立补全选择该提案。历史汇总布尔值只记录共享筛选采纳另一项提案的情况，原回执保留。

原生正向提案的实际冲突未回传给其教师。已启动原四个 OpenExempt TRAIN 来源上的独立版本，两个教师条件共享起始提案、四组原始投影读数、已审事实与逐槽允许值，解释约束为唯一处理差异。每路一份提案，先复测原生收益与字面源审，再用原测量接口验签名。唯一会话 92397，入口 `handoff/revision5_oe_candidate_feedback_repair_current.json`。复核证据为 `handoff/revision5_evidence_reconciliation_20261119.json`。

## Revision 4 期间的历史记录

# 当前Goal恢复：从真实反例后的修订继续

模型切换后的恢复记录：get_goal 已核实同一研究目标恢复为 `active`。Qwen3-8B 服务及配置已核验。全局 Codex 模型已变为 gpt-6.2-sol，项目改从 `configs/legal_skill_convergence_teacher_v1.json` 显式绑定原教师 gpt-6.1-sol/high。教师复核为只读，无新教师调用。

工具会话 40235 已终结。固定控制命中历史同 wire 记录，关系提示新增一笔本地推理，仍出现原州籍极性错误。读者指针指向 3b0464…，其精确绑定源码已封存。

最新已结算任务为固定 TRAIN 20 母来源共同 B0，对应工具会话 97558，读 `handoff/pilot_b0_current.json` 的真实状态和绑定。24 个逻辑读数含四个 OpenExempt 母来源各自独立的 EC 与 EV。若已完成则复用结果；运行中保留绑定源码。MAUD 两版和 Diversity M2 补丁比较均为终态，详见 DEVELOPMENT_EVIDENCE_20261118.md。

先读AGENTS.md、PROJECT_MAP.md、docs/CURRENT_GOAL.md，调用get_goal；不创建/重置Goal。固定方案reports/legal_skill_convergence_20261117/，上游37a76ff。旧方案只作资产与失败证据。

每次压缩/中断后读artifacts/legal_skill_convergence_20261117/handoff/run_state.json及最新pointer，核对实际进程、工具会话、账本reserved、冻结绑定和terminal。从未完成处继续，不凭旧PID或计划重启任务。实际账本计数及在途响应以 run_state 和对应的当前指针为准。M2 补丁比较结算时累计 12455 条，当前 Goal 物理请求 28 次（教师 2、Qwen 26），共 140185 tokens。B0 用量继续在原账本累加。服务原PID536850/537626保留，Qwen thinking OFF；教师gpt-6.1-sol/high已真实验证。

## 必须保留的真实结论

Diversity-6学习母来源d201b0…：工程修复后固定接口错误/不忠实，联合关系正确/忠实；两个混合配置也未通过。四候选实际配对后，库选联合关系。Diversity-5另一母来源03d239…：预先选择的所学模板实际执行，但同州籍比较错读为true，原生错误；固定接口正确/忠实。不能只展示首例，当前无总体收益证据。

Goal目录下的不可变阶段：
- source_audit_01/e38bce316d85c79bf57edf72d264e2bf36e198de4a4861096bdce574541ba563：1次教师源审终结，58效果/59例外引文过，缺16项引用、无真实歧义。引文过不等于法律真值闭合。
- diversity_reader_probe_01/18332fc82acbf5eaacb06fa64bdd6996dbff04edc82644f75c64d30ac84a71ef：共同工程修复前2次拒绝，source_snapshot12文件封存。
- 同父目录9a28210778704b982ffd5c9b77aa09a22867d589364108632afbfe70decdc2cb：共同修复后固定vs关系2次终结，source_snapshot12文件。
- 8e876932dd6cd9b4f22d874608ebd5ddc0d4648e158b47f4bac6c3166ac127fd：四候选终结，精确复用上述2份有效wire，仅新增2混合读取。
- actual_interface_library_v1/c40b513f3ff9c985eed9fb9207ebb93d6c38a11d5adaf31cf776bbef56ded71c：实际库保存/恢复及新母来源读前选择。
- diversity_reader_probe_01/add5766667c7aec93f6d55098133bb0432a26f16b02f8648b29840af9401843c：另一母来源实际复用已终结，负结果，source_snapshot14文件。工具2038已exit0，不能重复启动。

旧工具会话86997、86319、38407、2034、2038均已终结。不可用当前已改的probe脚本重跑旧binding；用各source_snapshot或公开提交重现。目标是继续未完成修订，不重复已有记录。

## 代码与下一项实质修订

residual.propose是原合成器的扩展；relational_program/diversity_relational是真实组合接口；formal_training.RelationalInterfaceLibrary是真实配对读数、源忠实性、保存/恢复/新母来源选择。模板版本已绑定提示和执行器。旧观察保留，新模板排除无版本及版本不匹配的观察。AST 极性提示改写已完成。实际同一 TRAIN 错误未消失，后续要从主体绑定或结构化极性入手。

shared_semantics是新M2，旧风险选择器不用。diversity_supervision 有真实源编辑和派生闭包。完整读取条件下 K 为单解释。四个预选 TRAIN 来源上的受控遮蔽可以从原文变更产生非平凡共享事实关系，该受控诊断与后续真实补丁、自然不完备验证分别保存。新选组逻辑能够识别每组单独允许、联合时无共同解释的候选签名。下一步需接真实合同作用域及独立K/非平凡共享组和教师更新，不能捏造歧义或把拒绝全部更新算收益。保留177审计、失败和连续账本，不另开题。

## 数据、公开与复核

固定名册128/80/160，CNI17、MAUD3，MAUD TRAIN23/72语法section扩展；旧审计输入变更须复核。读normalized_inputs_current/diversity_train_current/diversity_holdout_current/contract_nearduplicate_current获取版本。不要打开sealed_test或sealed_native，不要全目录搜索原始数据。名册锁定回执为 sealed_source_roster_current.json，模型和技能库的 B8 冻结独立完成。未做 TEST 评分。

633e0e296cbfde8819a0d2c786b9cddc9bf379fa 已公开并核对分支引用；后续复用负结果、成本与离线重放器当前以本地包为准。重放命令python -m experiments.convergence_replay_public_evidence，已0新调用重现10逻辑解码/8物理响应并核150文件hash，不需私有账本或原始缓存。包只含公开TRAIN，不含DEV/TEST封存、整库账本或凭据。

曾因疑似私密合同外发被自动审批拒绝；官方公开MAUD data.zip的Git blob74dc33bf4b8720df325d2858ea74c2790f16db20与本地完全一致，本次每段请求亦是公开原文切片证明后，同一动作重新审批获准，当前无待用户授权阻断。不要重问已授权目的地或资源。

公开Git使用已验证公开父提交为parent的临时bare repo，不上传本地私有历史，不force/main。第二版prepare曾read-tree超时但未写远端，改用父提交对象缓存已解决；不因只读核验网络失败重推。保留所有无关dirty文件。

从共同 B0 读完后逐来源误差继续配对修订和完整小试。下一阶段沿既定方案完成 128 来源八批矩阵、DEV 曲线、冻结 TEST、消融和迁移。英文方法与开发结果初稿保存在本地 paper/METHODS_AND_DEVELOPMENT_RESULTS.md。当前Goal未达成，不以交报告或跑通机制宣布完成；有证据+实质变化+可检验预期才继续，不设置虚构优化轮次上限。


## 最近运行核验

MAUD Knowledge Definition 固定四母来源的配对已结算。引用版固定与合成各 0/4，共 6 次长度拒绝。标量版保留前三母来源的六次合法读数。最长来源展开语法请求超时，保留在账。用等价因子化语法只补最后一对，语法从 234214 字节降到 4125 字节。八次合法输出均为 unread，固定与合成各 0/4。八个参考输入仍通过生产链。格式故障与读者未能绑定判定条件已区分。会话 96236、52359、4568 均为终态，各绑定已封存，不重复读数。

ContractNLI 四份文档、68 项原生假设的公共证据布局已验证。分类 30/68→36/68，证据 F1 0.0276→0.3571。之后各臂共享此布局。Airline 两个真实配对仅发出两次编辑请求，原始控制精确复用。两例实际费用差均为 0，违反独立编译的 −70 关系。从实际反例继续教师补丁，在同一原生任务和衍生组比较普通与关系选择。会话 66775 已终结，见 `handoff/remaining_TRAIN_probes_terminal_20261118.json`。

OpenExempt 自然所有权会话 43131 已结算。固定 B0 精确复用，一次教师 gpt-6.1-sol/high 与八次新 Qwen。两条补丁及原技能原生 EC F1 均为 0，普通和共享均保留原技能。源审保留所有权真假两种可能。修订门控要求字面断言在全部解释中成立，零次新调用复查了原六项所有权断言，均不受源文支持。原运行的共享兼容结论保留。见 `handoff/natural_OE_runtime_followthrough_20261118.json`。

五臂冻结入口要求完整 B0/B1/B2/B4/B8 DEV 和同一 B8。DEV80原文与 TEST160身份元数据已核验。正式训练及冻结 TEST 尚未启动，TEST 原文和评分保持封存。定向检查 75 项及两个子检查通过。论文工作稿已记录共同 B0、真实 M2 诊断与 MAUD 输出处理。

当前连续账本 12510 条，0 条在途，当前 Goal 增量 83 条，累计已计 Qwen 396280、教师 79894 tokens。失败请求保留且单列。远端研究分支核验至 `cb630cf8b4ac6752e834847f2b679a566cc19434`。保留177源审、旧运行及全部暴露记录。


## 11 月 18 日恢复与后续结果

旧曝光事件记录于 2026-11-17 08:05:17 UTC（北京时间 16:05:17）。仓库登记与事件副本字节相同，原来源清单哈希一致。现行 TRAIN 与旧事件交集 0，DEV80 中 64 个来源来自旧 DEV72，仍标记为已暴露开发来源。现行 TEST160 对旧事件、历史登记和连续账本的来源 ID 交集均为 0，正式名册含 Diversity 且无 SARA。只比较身份元数据，未打开封存 TEST 文本和评分。复核回执为 `handoff/heldout_exposure_resume_check_20261118.json`。用户明确沿原 Goal 继续，原登记不撤销。用户已恢复同一个系统 Goal，状态经核验为 active。

Airline 会话 64324 已结算，四笔固定响应精确复用，八次新 Qwen 与一次原配置教师请求。固定技能及两个补丁在两个原生 TRAIN 来源均为 0/2。三个选择器均保留原技能。两条补丁均未通过两例的差分或独立费用关系检查。绑定源码及规则表已封存。缺少新的更新依据时不重复这组提示。

当前账本 12519 条，零在途。已计执行器 433324、教师 97030 tokens。后续在 ContractNLI 的接收方和员工许可条款上复核局部绑定，保持同一输入和公共证据布局，不接触 TEST。


## DEV B0 与 CNI 生产结果

CNI 员工披露原生问题在四份既定 TRAIN 合同上比较固定坐标与自动合成接收方关系。消费者等价域从 36 种坐标到 12 种关系，8/8 参考读取通过生产解码和原生证据 ID 检查。三个独立审阅片段能建立员工许可，另一片段仅建立代理人和专业顾问许可，参考保留未决。真实配对共 8 次合法响应，固定与合成原生各 0/4。固定 2 个结构化读数未通过源语义或原生判断，合成 4 个均未读。真实调用 18300 tokens。会话 15872 已结算，11 个绑定文件已封存。该结果与 CNI 共用证据布局的原生改善分别报告。

当前唯一运行任务是共同 DEV B0，工具会话 84995，使用 `handoff/dev_b0_current.json`。正式协议规定的 80 个 DEV 母来源、96 个公共读数单元，TRAIN 核验过的 CNI 证据布局对所有臂共同使用，OpenExempt EC/EV 独立。实际分词已核验最长输入 19017 tokens，均在上下文预算内。预测封存后在本地读取 DEV 评分，无个案反馈送入教师，不打开 TEST。恢复时先核对当前工具会话、绑定与账本，禁止从旧准备状态重复启动。

最近一次核对连续账本 12530 条，含 1 条在途。已计 Qwen 468059、教师 97030 tokens。系统 Goal active。五臂训练和 B8 冻结仍待完成，当前仅共同 DEV B0。继续沿固定八批接通 TRAIN 实际更新和读者选择，不据历史暴露恢复旧队列。


## 续跑控制记录

确认当前 Goal 为 active。已核验公开研究分支 `4283011fbe9e5f3bf3d802c2065cd5aa5bd3386e`，仅同步源码、测试、汇总和交接。DEV B0 唯一生成会话 84995，归档监听 34372，当前已保存 26/80 个母来源，连续账本中的该阶段请求记录 43/96 笔。以实际会话、`handoff/dev_b0_current.json` 和已落盘预测为准。核对时连续账本 12570 条，1 条在途。绑定源码未改；归档监听只保存原绑定，未派发下一任务。TEST 未打开。

对已经完成的 CNI M1 八条真实读数完成技能库保存、恢复和留一选择，四个目标均保留固定接口，无新调用。五臂共同 B0 路由复用了四个已有 CNI 物理读取，每臂核对 68 个原生输出一致，未预装方法独有小试技能。已实现同池 M2 选择函数，用既有 OpenExempt 实测验证两候选皆因字面所有权无来源支持被拒绝，没有新的原生收益。固定 128 来源的八批每批 16 项经原身份、任务与指纹绑定验证。

CNI 公共布局的 4 母来源成对自举中，分类增量为 0.088，探索性 95% 区间 [0.000,0.221]；证据 F1 增量为 0.330，区间 [0.176,0.465]。两项属于公共工程布局结果。定向检查 78 项及两个子检查通过。

Airline 已登记一次有实质变化的后续检查，见 `handoff/airline_structured_update_current.json`。复用之前两个失败母源及双编辑，每个公开输入只读取一批逐行李费用；三种确定性聚合复用同一批读数，分别验证原生分数与差分关系。该阶段尚未发请求，DEV 任务终态且零保留后从此精确绑定继续。正式强对照选择、八批学习、DEV 曲线和冻结 TEST 尚待完成。



## 最新断点

当前系统 Goal active。DEV B0 会话 84995 与归档会话 34372 已结算，80 个来源、96 次物理响应，报告与16份绑定文件保留。DEV 分类与证据指标已保存。96 次调用共605907 tokens。训练规模仍为128来源、八批和592项原生任务。

Airline 逐行李费用阶段 85789 已结算。三种聚合各 0/2，模型读对票价与 ID，核验的超尺寸和超重费用仅 1/56 个字段正确。四笔调用共19480 tokens。随后从同一公开费率条款编译共用规则，只让冻结模型读票价、尺寸和重量。新阶段 47863 已终结，原生结果同件取最大值 2/2，另两种聚合 0/2，两个编辑费用差均 −70。普通与关系选择均选中正确聚合。四次新调用共2950 tokens。该定点原生收益来自公共消费者修复和确定性规则，当前两来源结果未证明 M2 独有优势。参考与实际回执见 `handoff/airline_public_fee_runtime_20261118.json`。

最近连续账本 12631 条、在途 0，已计执行器 1079961、教师 97030 tokens。五臂固定训练、强对照最终选择及冻结 TEST 尚待执行。TEST 文件保持封存。公开研究分支最近核验至 `2a1fadd311a8be8195b3c07a22f695a5f3d8146f`，已补同步核验至 `994391113bd171d7c9b4b914b4dac6841cfe0813`。论文初稿已补真实 DEV B0 与分段失败证据。


Airline 共用工具后的 DEV 对照 51488 已结算。由公开规则适用范围预选 2/16 来源，两次新读取共 1474 tokens，全部答对。其余十四项原 B0 精确复用，全库 0/16→2/16。适用域的 TRAIN 参考输入 7/7，仅代表独立规则校验。此修订作为共同组件进入后续对照，单独的 M1/M2 效果尚未建立。当前无生成任务在途，账本 12633 条，执行器 1081435、教师 97030 tokens。80 项相关检查及两个子检查通过。


## 当前固定 TRAIN 小试与断点

系统 Goal active。当前普通教师对照为工具会话 37765，绑定 `47c98bab0b745aa536e37d29133f3db3984109e829079934922268630c3388ba`。恢复时查 `handoff/native_teacher_pilot_current.json`、进程和连续账本，再接已保存的候选。首个版本会话 42802 在 600 秒超时，失败已结算，零候选、零执行器调用，20 份绑定文件和 CLI 传输证据已归档。恢复版继续使用 gpt-6.1-sol/high，只提供公开任务说明与 TRAIN 汇总，明确输出紧凑 JSON 并要求直接提交技能。

ContractNLI 四个固定 TRAIN 员工披露来源的参与者锚点修订已终结，会话 60050。两臂共用逐字提取的名称、角色与偏移，参考链保持 8/8。八次新读取使用 29842 tokens。原生固定 3/4、合成 2/4，核查引用与许可后两臂都只确认 1/4。保留十三份绑定文件和原始读数，后续按许可动作与来源身份绑定处理，不沿用未核验的分类正分。

PARSE 式可逆强对照已准备，同 20 母源的 24 个原始冻结响应均可恢复全部原生输出及证据，零新读取。Airline 两个已审配对的绝对回归与固定差值对照精确复用四份原响应，和普通原生选择均选中同一程序。完整固定20对照、五臂八批训练仍待完成，TEST 保持封存。

核对时连续账本 12643 条、在途 1，当前 Goal 已计执行器 1111277、教师 97030 tokens。已失败的教师请求没有可确认的 token 结算字段。复现入口为 `python -m experiments.convergence_parse_pilot prepare` 和 `python -m experiments.convergence_replay_external_controls`。跟踪 `handoff/run_state.json`，恢复前核对现有会话。

## 完整原生配对与当前强对照

会话 94263 已结算。固定四份合同的完整 17 假设口径，固定 39/68、合成 37/68，原公共 B0 36/68。证据 F1 为 0.3401 与 0.4927，变化全部在未改写的 16 项，主要来自一份合同。目标员工披露均 4/4，核验所引许可后均为 2/4。共 8 次 Qwen、87787 tokens，零生产拒绝。已保存 24 份绑定文件、逐来源评分和引文核查。论文初稿纳入该结果。

普通教师恢复版会话 37765 也已在 600 秒超时，终态已归账。两次均只见 CLI 开始事件，未收到提案或 token 回执。原教师 gpt-6.1-sol/high 未改，本地登录状态已核对。保留两次失败，不重复发相同程序提案。独立 PARSE 式小试正在运行，工具会话 75716，绑定 `1d77b9ad571fc4164dc47267470bd1af4317b2b8b9195665e3db910943ebc2f1`，教师只需返回字段别名、顺序和短指导。重入先核对该会话和连续账本。此前 24 个实际物理响应已完成原 schema 回放。

八批记录器已用固定128来源检查五臂共同 B0 初始化、逐批证据绑定以及未完训练拒绝封存。定向验证 81 项及两个子检查通过。仍需选定完整强对照和执行正式八批、DEV曲线及封存 TEST。当前账本 12655 条、在途 1，已计执行器 1218531、教师 114710 tokens。最近公开核验提交 `b691b8b9e0613f51831fc0a59de507f32f1c4b51`。

## 当前强对照补测

原 PARSE 会话 75716 已结算，冻结教师五份提案均有效返回。ContractNLI 候选 33/68，对应共同布局 36/68。Airline 候选 0/4，共同费率修订 2/4。当前补测为会话 69223，绑定 `c74bb734f209470fd2814bcdd56177c10e616138bc16ecfb200c1d0ef82c0b84`，完成 Diversity、MAUD 和 OpenExempt 对原教师提案的实际评分。三份使用了改写后的别名排序，已经验证可恢复为唯一原字段。复用五份教师响应和之前两库评分，只补原来没有实际读取的 16 项。上一版 24 份绑定文件均已归档。继续遵守原教师模型、固定小试范围和 TEST 隔离。

普通教师程序对照的两个失败已保存。由于同一教师的简化 PARSE 输出已经返回，已对一谓词、两种 schema 模式及纯组合函数的紧凑程序合约完成离线校验。通过现有程序校验后用于后续教师程序对照，当前未派发。核对时账本 12673 条、在途 1，已计执行器 1279936、教师 183991 tokens。

## 当前小试断点

系统 Goal active。重入先验证唯一生成会话 66228 和 `handoff/compact_teacher_scope_current.json`。该会话从固定20源、同公开信息与同一 gpt-6.1-sol/high 和 Qwen3-8B thinking OFF 执行 SCOPE 式分解对照。确认终态后再接反例归因、回归控制与外部排名。保留准备版和运行版绑定，不重发已结算请求。

PARSE 会话 69223 和普通紧凑会话 52538 已结算。PARSE 完成20母来源的96项原生任务并保留 MAUD 和 OpenExempt 候选，外部排名记录见 `handoff/parse_complete_fixed20_ranking_receipt_20261118.json`。普通紧凑对照五库均保留共同程序。会话 62245 在 OpenExempt 预分词处终止，保留四份教师提案和三库读数。只修复读者收到的冗余工具信息，完整公开任务与原生 schema 均保留。冻结分词初次拒绝为 27115 tokens，修订后同组最长 7391 tokens。绑定源码已封存，未重复发已完成的库和教师。

五臂共同 DEV B0 已复核并封存，全部来源的原生预测每臂一致。Airline 2/16，384 项原生任务每臂，零新请求。用 `python -m experiments.convergence_shared_dev_checkpoint` 复核。此共用检查点可在锁定外部家族后重新绑定正式研究，无需重发请求。正式八批、独立效果、后续 DEV 曲线与 B8 TEST 都仍待完成。TEST 核查仅用身份元数据。

## 最新恢复入口

SCOPE 会话 66228 和离线归因 44006 均已结算。五教师、24执行器分别用 87426 和193117 tokens。MAUD 选入 9/12 候选，其余四库保留共同程序。归因使用每库第一条测得错误的原来源，六个实际组合均能用已保存的谓词输出复现。归因结果见 `handoff/compact_SCOPE_composition_attribution_20261118.json`，仍需源文编辑阶段及完整外部排序。

会话 65543 已结算，绑定 `87e5e11540893f15e5346d3004ff98c1dfabec3c659ea09d644ef7d4c001aef5`。两个之前结果相反的 TRAIN 来源加入相同的原文摘录后，固定和合成各答对 1/2。源文摘录修复了第二母来源的同州籍错误，但第一母来源仍有重复的金额误读和合成比较极性误读。见 `handoff/diversity_source_binding_result_20261118.json`。按可见原文中的共同主张建模和验证同源金额的可合并性，再处理关系符号与名字证据。保留旧有正、负结果与11月18日各版绑定。

新 M1 校准入口的 Diversity 独立来源审阅在八批24母来源中核对了96候选和384个局部事实，用零次新读数。当前无生成会话，连续账本 12742 笔、零在途，Goal 内执行器 1790742、教师 359847 tokens。还需 SCOPE 合法编辑回归、两项外部回归与五库排名、正式八批/B1/B2/B4/B8 DEV、独立消融和最终 TEST。继续以终态证据判断，TEST 仍封存。Goal active。

## 当前可恢复状态

会话 79058、99169、62152 均已结算，当前无生成任务，连续账本12762笔、零在途。`handoff/run_state.json` 索引精确绑定，已归档三次运行源码。`handoff/locked_external_baseline_20261118.json` 完成四个适配的固定20来源排序，PARSE 式家族锁定。Scope 可逆角色更名后的 MAUD 候选 9/12、共同程序 8/12。回归候选池中无正向普通教师更新，先行原生筛选保留原技能。原 Airline 两对回归不重复跑。

共有条款分组在八批24母来源上验证96候选，并在原两个母源上真实测完四布局。固定州籍加合成金额在校准 2/2；冻结选择后，后续两个母源固定 2/2、合成 0/2。原文均明确低于门槛，合成金额关系仍读过线。后续按新的金额读数证据行动，不能原样重跑或选择性引用校准结果。新 M2 金额约束已离线编译，每处共有条款的共享签名3种、独立4种，属于控制缺失量的诊断。真实读数、候选选择与原生更新仍待。

`handoff/formal_bootstrap_current.json` 是锁定外部家族后的五臂共同 B0。零新调用验证128个 TRAIN 母来源、八批、80个 DEV 母来源及160个 TEST 元数据身份。下一步从已有绑定接通真实 B1 更新和其后的全部矩阵，先完成两机制当前有依据的 TRAIN/DEV 优化。TEST 未打开，Goal active。

## 当前 B1 与金额证据

会话 77024、52664 已结算。M2 两补丁与原接口原生各2/4，三者在三个编辑上均有效弃答，连明确过线的锚点也未读出。四种选择保留原接口。后续改成模型读取带原文证据的已知金额，再由确定性消费者计算下界。待运行阶段见 `handoff/m2_amount_projection_current.json`。五臂 B1 前置观察16母来源、74任务完全同输入同读数，复用13个逻辑读数，新增7笔，39970 tokens。各绑定均封存。B1 尚待完成五臂的更新和固定 DEV。

跟踪唯一生成会话 33790，对应 `handoff/formal_b1_fit_current.json`。初次27605已终结，CNI 教师提案真实返回，执行器因过长输入拒绝预留，原代码与提案保留。复用原教师结果并仅压缩重复宿主参数的恢复运行已启动。不得从旧指针重新启动。M1 两臂的同池 B1 接线已通过准备核验，`handoff/formal_b1_m1_current.json` 绑定三母来源及12候选。待当前生成任务结算后接续，不并发派发。TEST 保持封存，Goal active。

## B1 五臂已结算，固定 DEV 运行中

五臂已完成同一批 16 个 TRAIN 母来源、74 个原生任务的正式更新。普通教师拟合会话 33790 已结算，恢复版精确复用初次已付提案。两对照合计 10 个物理教师请求、36 个物理执行器读数，分别使用 176202 和 261251 tokens。普通教师只采纳 ContractNLI，原生正确数从 27/51 到 28/51。PARSE 只采纳 OpenExempt，EC/EV 合计的任务平均效用从 0.135665 到 0.213021。

M1 会话 64380 已结算，三个固定 Diversity 母来源的 12 个配对读数共 11713 tokens。两个含 M1 的臂共用实测候选池和同一接口快照。会话 42872 已提交全部五臂更新，当前 M2 正式关系提供器覆盖 OpenExempt。该范围首批没有原生得分提高的普通候选，两个含 M2 的臂保留对应更新。来源审计及控制项证据保存在 `handoff/formal_b1_primary_current.json`。

独立的金额读取诊断已结算，见 `handoff/m2_amount_projection_current.json`。三次调用共 708 tokens，输出为未知、未知、过线，无生产拒绝。判定使用逐字引文中的确定金额及 75000 门槛。原九个关系读取全部未知。该诊断尚无配对的原生更新效果。三个阶段的源码绑定已归档。

当前唯一生成任务为固定 B1 DEV，会话 25532，入口 `handoff/formal_b1_dev_current.json`。80 个固定母来源、五个封存技能库。仅在预测封存后读取 DEV 评分，按母来源计算与 B0 的配对变化及独立臂差异。恢复先核对会话、连续账本及终态，避免再次启动。B2–B8、其余 DEV 检查点、消融和冻结 TEST 待完成。TEST 原文及评分继续封存。


## B1 已结算单元与 B2 续跑

B1 DEV 已结算普通教师、仅 M1、仅 M2 和联合四臂，每臂 80 个预定母来源。会话 25532 继续测锁定的 PARSE 外部臂。以 `handoff/formal_b1_dev_current.json`、连续账本和实际会话为准。

Diversity 的仅 M1 臂和联合臂均为 12/16，普通教师和仅 M2 臂均为 9/16。两组独立 M1 对比的准确率和平衡准确率均增加 0.1875，按母来源配对自举的 95% 区间为 [−0.125, 0.500]。9 个来源执行合成接口，7 个保留共同程序。相对于各自匹配臂，5 个原生错误修复，2 个退化。5 个修复均逐单元通过原文核查。合成路径中，州籍关系 12/21 与同对金额关系 10/12 受原文支持。离线审计回执见 `handoff/B1_M1_DEV_source_audit_20261118.json`，未向推理或教师提供此审计。

普通教师 ContractNLI 从 B0 的 149/272 降至 B1 的 134/272，原生增量 −0.0551，母来源配对区间 [−0.1544, 0.0147]。据此从 B2 开始，同一合同候选在通过当批 TRAIN 得分后，还需通过已见 TRAIN 合同上的原生回归核对。普通教师与外部臂都执行该核对。DEV 单题及标签不进入教师反馈。B2 观察入口 `handoff/formal_B2_observe_current.json` 已离线绑定原定 16 母来源、74 原生任务和各臂 B1 快照。拟合和 B2/B4/B8 DEV 入口已实现，仍需真实读数。

从原 177 份审阅中重核固定 OpenExempt TRAIN 的 44 份资产审阅，逐份核对版本、原生视图和文件哈希。保留 5 个有自然未知所有权、金额可合法编辑的母来源，出现在 B1、B5、B7、B8。B2 的候选如在同一固定原生训练集提高，可用已见的 B1 自然组做共享解释验证。该覆盖审核用了零次模型调用。金额遮蔽诊断与自然所有权监督继续分别记录。TEST 原文和评分仍封存。


## B1 DEV 完整终态与 B2 唯一运行

B1 DEV 会话 25532 已退出，五臂各 80 个固定母来源、384 个任务全部评分封存。新增 57 次 Qwen 物理读数，476710 tokens。36 份绑定源码已按哈希归档。完整分库指标、臂间配对区间和实际路径见 `handoff/formal_b1_dev_current.json` 对应的终态。

Diversity 的仅 M1 臂和联合臂均为 12/16，其余三臂均为 9/16。联合臂对锁定 PARSE 的配对差同为 0.1875 [−0.125, 0.500]。OpenExempt 普通教师及三个方法臂的 EC/EV 平均 F1 为 0.250826/0.161200，PARSE 为 0.237771/0.223942。PARSE 的两任务平均差为 0.024843 [−0.017132, 0.068345]。M2 的两个独立配对在五库原生分数均未变化。ContractNLI 的 PARSE 分类保留 149/272，其他四臂为 134/272，平均证据 F1 分别 0.255689 和 0.289042。

B2 观测已启动，会话 94143 对应 `handoff/formal_B2_observe_current.json`，是当前唯一生成任务。使用上一批各臂实际封存技能，原定 16 个母来源及 74 个任务。进入 B2 的改动程序最长输入实测 15303 tokens，仍使用原 8192 输出预算及 32768 上下文。结算后核对全部五臂预测和账本，再用既定候选计划拟合。最新请求状态以 `handoff/run_state.json`、实际会话及连续账本为准。

B8 TEST 入口和跨库技能屏蔽入口已编译。离线试验核对了已保存 M1 状态的屏蔽，并确认缺少 B2 实际训练回执时拒绝最终封存。两项 B8 实验尚未运行，TEST 原文和评分保持封存。系统 Goal active。

OpenExempt 官方精确率、召回率、F1 与 EV MARE 已从 B0/B1 封存评分汇总，零新调用。B1 的四个共同程序臂 EV MARE 为 3.036917（15/16 有官方值），PARSE 为 0.561578（14/16 有官方值）。未定义或拒绝的案例保留在覆盖记录中。回执 `handoff/B1_openexempt_official_metrics_20261118.json`。


## B2 观测终态与实测拟合

会话 94143 已结算。B2 固定 16 个母来源、74 个任务全部进入五臂原生预测。运行新增 29 次执行器、208380 tokens，42 份绑定文件已封存。普通教师和三个方法臂的当批原生得分一致，PARSE 臂为独立实测。观察尚未更新 B2 技能库。

当前唯一生成会话 10960，从 `handoff/formal_B2_fit_current.json` 精确恢复。拟合使用实测的 B2 当批反馈和已见 TRAIN 合同回归核查。M2 和普通筛选看到同一个教师候选，B2 自然关系证据只来自已经可见的固定 TRAIN 来源。恢复先核对会话、账本和终态，不重复发出请求。B2 更新与 DEV、后续批次及 B8 封存测试均待实际结算。TEST 保持封存。


B1 离线补核完成。Diversity 三个 M1 对比按原生 Yes/No 分层的平衡准确率差均为 0.1875，母来源配对区间 [−0.0625, 0.375]。未分层准确率区间保留。每臂引用 96 个已结算物理响应，五臂取并集为 153 个，其中新增 57 个。共同教师与仅 M2 各引用 608936 tokens，含 M1 的两臂各 617742，PARSE 为 603832。跨臂复用由物理 ID 去重，引用成本不相加。ContractNLI 分类退化拆分显示，普通教师臂的 NotMentioned 正确数由 12 降至 0，Entailment 由 132 降至 123，Contradiction 由 5 升至 11。三项离线补核均零模型调用，回执分别见 `handoff/B1_Diversity_BAL_accuracy_20261118.json`、`handoff/B1_DEV_cost_audit_20261118.json` 和 `handoff/B1_CNI_aggregate_confusion_20261118.json`。


## B2 训练与 DEV 终态，B3 运行

拟合会话 10960 已结算并提交全部五臂 B2 快照。十条教师提案均未提高各自的实测 TRAIN 原生表现，普通教师、PARSE 和 M2 对应程序均保留。两个 M1 臂共享新增 12 个配对，接口库各累计 24 个实测候选读数。49 个物理执行器和 10 个教师调用分别计 251451 和 175165 tokens，50 份绑定源码已封存。见 `handoff/B2_training_terminal_audit_20261118.json`。

固定 B2 DEV 会话 71563 已结算，五臂各 80 母来源，新增 7 个模型读数及 7448 tokens，54 份绑定文件归档。两条 M1 臂在 Diversity 实际选择 7 个合成接口，原生准确率和平衡准确率均为 10/16。普通教师、仅 M2 和 PARSE 均为 9/16。三组 M1 配对差为 0.0625，母来源 95% 区间 [0, 0.1875]。其余库分数沿用精确匹配的 B1 模型输出。B1 的 M1 开发差值 0.1875 未在 B2 完全保持。B2 的 M2 独立对比仍为零差。

M2 固定小试会话 35706 已终结，`handoff/m2_positive_schema_probe_current.json`。复用四个 OpenExempt 母来源的原生对比和两笔原有投影，另用两笔投影、11624 tokens，无教师或原生重发。已测 PARSE 候选的 TRAIN 原生平均 F1 提升 0.089694。它在自然未知所有权的两变体都断言非所有，独立来源审阅不支持。单解释、独立补全、共享解释的兼容检查各通过，三者的共同事实门控均拒绝候选。该结果为事实断言问题。81 项离线有限枚举中，独立可兼容 36、共享可兼容 28，事实门控后仅 4 项，均与所有共享签名兼容。当前投影的两个字段都是事实字段，该设计在事实门控后无法区分共享选择。后续按现有量阈值消费者把可证事实和有多种解释的派生判断分开，再做真实同池验证。见 `handoff/M2_literal_gate_subsumption_20261118.json`。

B1 ContractNLI 唯一截断响应的 14 个完整证据数组有 13 个各引用至少 131 项，B1–B2 已见 TRAIN 的 102 个原生标注中最大证据数为 10。该运行失败作为原结果保存。见 `handoff/B1_CNI_DEV_excess_evidence_20261118.json`。若修复过量证据，需对受影响的臂匹配验证并保留全部原生假设。

B3 固定 TRAIN 观察唯一生成会话 80601，入口 `handoff/formal_B3_observe_current.json`。16 母来源、74 原生任务从各臂的 B2 已结算快照开始。恢复时核对会话、状态和连续账本，不重复请求。B3 及以后拟合、B4/B8 DEV、消融和 B8 TEST 尚待结算。TEST 保持封存，系统 Goal active。

金额关系的投影修订已在原 Diversity TRAIN 编辑组离线贯通。明示金额与未述金额沿用事实门控，过线判断单独进入共同解释。相同编辑仍只有 3 种共享签名，独立有 4 种。确有一组通过事实门控、通过独立补全、被共享解释否决的派生判断，排除了本次自然投影的门控覆盖问题。该见证由参考代码生成，未当作模型读数或原生收益。见 `handoff/M2_Diversity_judgment_preflight_20261118.json`。


## B3 观察终态与当前拟合

B3 观察会话 80601 已结算，16 个母来源、74 项原生任务覆盖五臂。31 个新增 Qwen 读数用 217444 tokens，42 份绑定源码已封存。拟合为当前唯一生成会话 3377，入口 `handoff/formal_B3_fit_current.json`。普通 ContractNLI 候选在当批净增 1/51，在前两批回归核查净增 1/102；其余结论待五臂封存。恢复时先核对实时会话、账本和终态。

补核 B2 的 7 个 Diversity DEV 合成读取，全部局部关系与原文一致，修复 1 项，没有相对于普通程序的退化。B1→B2 的路由切换涉及全部 16 个 Diversity DEV 母来源，5 个原先正确的合成结果回到普通程序后出错，同时出现 3 个反向修复。前两批 6 个 TRAIN 母来源中，固定原始读取与生产普通程序的原生得分有 2 处不同。见 `handoff/B1_B2_M1_route_audit_20261118.json`。汇总未进入教师或训练选择。

M2 的新投影执行层已实现。候选须引用精确条款、读出可见金额，并答对确定过线的锚点。候选的独立、单解释和共享选择共用相同的原生测量与上述检查。固定小试中两个既定 Diversity 校准母来源的原生正候选已逐物理响应重核，见 `handoff/m2_amount_judgment_probe_current.json`。六个新投影尚未派发。B4 拟合的量阈值接线已在临时副本核验，等 B3 结算并归档后才更换。TEST 继续封存。


## B3 封存与 B4 运行

会话 3377 已结算并封存五臂 B3 快照，累计 48 个 TRAIN 母来源。10 笔教师和 56 笔 Qwen 分别用 175713 与 376227 tokens，50 份绑定源码已归档。普通教师采纳 ContractNLI 与 OpenExempt 更新。锁定 PARSE 保留五库原程序。OpenExempt 候选的当批原生均值提高 0.010818，但两个真实投影都在原文只说明占有的情况下断言有所有权。普通教师程序已替换，M2 臂保留旧程序，两条快照链均已核对。这次分歧由来源事实检查产生，原生泛化影响等待固定 B4 DEV。见 `handoff/B3_training_terminal_audit_20261118.json`。

会话 23775 已结算，固定小试中两个预选 Diversity 母来源的原生结果精确复用，普通为 1/2，已测接口为 2/2。额外六个混合投影用 3522 tokens，无原生或教师重发。候选在确定过线锚点答对，普通程序仍弃答。候选在低金额变体把 10000 美元写为 10，三种筛选均拒绝。该布局的原生文本确有千美元坐标约定。离线用绑定原文数字替换这一个表面单位后，原实测判断序列同时符合独立与共享解释，故纯单位修复不足以在这批读数上产生共享选择差。未把替换结果计为模型读数。31 份旧源码已封存。B4 前向投影明确金额字段始终使用精确美元，保持来源引用与独立评分。参见 `handoff/M2_judgment_unit_error_audit_20261118.json`。

B4 的下一次拟合已接入当前可见 TRAIN 的量阈值组和共同事实锚点。候选须先在同一原生批次提高，才新增投影。两类教师都收到同一份无原文、无标签的 B3 所有权错误反馈。改动在 B3 和金额小试源码归档完成后落实，B4 观察绑定不含这些新拟合文件。B4 入场候选的 11 个公开视图已用实际分词检查，最大输入 8946 tokens，输出额度 8192，上下文 32768，零生成。当前唯一生成会话 61599，从 `handoff/formal_B4_observe_current.json` 恢复。B4–B8 和后续 DEV 及最终验证尚待，TEST 区仍封存。


## B4 前向证据与 M1 时间顺序重放

在 B2、B3 六个固定 Diversity TRAIN 母来源上按时间顺序重放。每一折只使用之前已见的 TRAIN 和原先已付的实测候选。普通程序 6/6，现行 M1 选择 5/6，直接对照实测普通程序选择 4/6。现行规则选用三个合成读取，其中一个通过逐关系源审，替代规则选用两个，均未通过。保留现行规则。回执见 `handoff/M1_incumbent_through_B3_20261118.json`。

B3 的两个 OpenExempt 程序在下一批四个固定 TRAIN 母来源上实测。仅 M2 相对普通教师的 EC 平均 F1 差为 −0.014464（两升一降一平），EV 为 −0.000424（一升一降两平）。B3 的程序分歧由字面所有权检查触发。逐来源与程序哈希见 `handoff/B3_M2_next_TRAIN_audit_20261118.json`。

B4 两条长度受限响应中，一条 OpenExempt EV 响应在 63,478 个尾部空白字符后缺外层闭括号。离线复用完全相同的请求及原生解码器，仅补括号，原生 F1 维持 0。另一条仍有不完整答案字段，结构恢复拒绝。原运行结果保留。三个核验均未发出新请求，未读取 DEV 或 TEST。58 项定向验证通过。

B4 观察会话 61599 已结算。五臂逐臂完成 16 个固定 TRAIN 母来源和 74 个原生任务。38 个新 Qwen 响应用 282287 tokens，原绑定的 42 份文件全部已按哈希归档。当前唯一生成会话 76509，读取 `handoff/formal_B4_fit_current.json` 和 `handoff/run_state.json`。该会话实际进入普通教师 ContractNLI。启动后核对账本为 13144 笔、1 笔在途。当前 Goal 已结算用量为 Qwen 4046647、教师 904255 tokens。五臂 B4 快照结算后继续固定 B4 DEV。B5–B8、最终 DEV、冻结 TEST 和独立验证仍待，TEST 原文及评分封存。

M2 签名诊断 `handoff/M2_signature_through_B3_20261118.json` 复用三组原生正向候选的投影。两组 OpenExempt 只剩有原文支持的断言时各保留 2/2 共享签名。金额组保留 1/3，实际响应另有单位错误。三组均无已隔离的共享拒绝。B4 终态后可运行 `python -m experiments.convergence_m2_signature_audit --through 4` 追加已有物理投影的核对，零新调用。上一轮公开研究分支已核验至 `15634344022b1d102f79ed63490c719c0783257e`。

M1 同语法对照设计已锁四个既定 Diversity 小试来源和候选版本，见 `handoff/m1_same_grammar_controls_prepared.json`。固定、静态最短、原生分数普通搜索和源忠实性选择共用同一候选，逐来源留一。B2 来源四条实测读数核验完毕，其余三来源在 B7/B8。B8 后运行 `python -m experiments.convergence_m1_pilot_controls replay`，零新增调用。独立对照成绩仍待完整读数。

B0、B1、B2 五臂九指标 DEV 曲线已生成。矢量 PDF、600 dpi PNG 和封存指标点在 `dev_curve_figures/B2/`。`python3 -m experiments.convergence_plot_dev_curves --through 4` 在 B4 DEV 结算后生成下一版，B8 同理。已将 B1/B2 的 90 个点逐一与终态指标比较，均一致。

B4 拟合原会话 76509 在接口拟合阶段收到 SIGTERM 并退出。账本的 10 笔教师和 64 笔执行器均已结算，核对零在途及 54 份未改变的绑定文件后，同一运行已在 11279 复用既有响应继续。见 `handoff/B4_fit_interruption_20261118.json`。恢复先核对会话 11279 或其终态，避免重启。最近公开研究分支核验为 `4787d417faada4f70ddc888669ea5e4b51fe1d34`。

## B4 五臂封存，固定 DEV 在运行

恢复会话 11279 已正常终结。64/128 个来源已进入五臂正式训练。B4 拟合累计 72 个 Qwen、10 个教师请求，分别用 518284、175676 tokens，54 份绑定文件已按哈希归档。SIGTERM 后仅补发尚未开始的 8 个接口读数。两个含 M1 的臂各保存 48 个实测候选读数。见 `handoff/B4_training_terminal_audit_20261118.json`。

普通教师采纳 ContractNLI、MAUD 和 OpenExempt。ContractNLI 当批 21/51→25/51，前三批 78/153→81/153。其证据 F1 当批 0.28758→0.28105，前三批 0.24566→0.29699。PARSE 的 ContractNLI 候选当批净增 9/51，前三批净减 10/153，保留原程序。两臂的 MAUD 候选均在当批净增 2/9。OpenExempt 普通候选当批效用增加 0.021537，相对 M2 旧程序增加 0.028981。它在两个只说明占有的原文变体上断言无所有权，并遗漏明示金额。三种解释兼容检查均通过，字面事实检查拒绝，M2 保留原程序。四组实际原生正提案仍无单独由共享解释导致的拒绝。回执 `handoff/M2_signature_through_B4_20261118.json`。

M1 时间顺序离线核验已延伸至 B4 的九个固定来源。普通 7/9，现行规则 6/9，替代规则 5/9。两套规则在新增的三个来源均运行普通程序。继续保留现行选择。见 `handoff/M1_incumbent_through_B4_20261118.json`。

当前唯一生成会话 3504，从 `handoff/formal_B4_DEV_current.json` 恢复。它绑定已封存五臂 B4 和固定 80 个 DEV 来源。运行完毕后核对账本、五臂终态、绑定和分库效果，再画 B4 曲线并续跑 B5。B8 前 TEST 保持封存，Goal active。

## 后续 TRAIN 证据与 B5 准备

`handoff/M1_consumer_support_through_B4_20261118.json` 复核 48 个物理读数。全部局部关系忠实的有 24 条，遮蔽不受支持单元并用原消费者重算后有 33 条保持确定的原生输出。额外 9 条均原生正确，但按时间顺序替换候选选择的忠实性条件后，九个后续 TRAIN 来源的路由不变，两规则均 6/9。现行 M1 保留。

`handoff/m2_oe_title_value_current.json` 已冻结四笔自然所有权诊断，来源为固定小试同一母来源及原金额变体，比较实际 B4 正候选和进入 B4 的 M2 程序。它把教师程序的原生输出说明放在引用输入里，以唯一投影 schema 要求逐字资产金额证据，分别核验字面事实和所有权过滤后的局部金额。共享签名 2，独立签名 4。B4 的原生比较精确复用。B4 DEV 终态且账本零在途后从 `python -m experiments.convergence_oe_title_value_probe run` 开始。准备及 60 项定向校验完成，诊断尚无实测效果。

B5 固定观察已准备，`handoff/formal_B5_observe_current.json` 绑定 16 个来源、74 个任务及五臂 B4 快照。模型阶段串行执行，先确认实际会话与终态。未使用 TEST 文本或标签。

## 真实配对诊断与 DEV 会话换接

会话 99670 已终结。`handoff/m2_oe_title_value_current.json` 绑定四次 Qwen 读取，共 24355 tokens。两程序均达到 2/2 的逐字金额引文。候选两次保留所有权未知，派生量为 0、0，全部兼容规则均接受。旧程序输出明示金额、0，并于第一变体误断言所有权。仅移除字面断言的敏感性核验保留旧程序的 1/4 个独立签名及 0/2 个共享签名，未替换模型读数或更新。`handoff/M2_title_value_signal_audit_20261118.json` 保存该区别和结算哈希。56 份原绑定文件已归档。B4 程序未改变。

B4 DEV 会话 17651 已从原绑定继续。原 3504 在无在途后结束，17 笔结算均保留。首次换接 86060 因一份暂停产物被当作可评分缓存退出。对应请求从未预留，归档产物后调用已首次完成。原异常和文件哈希见 `handoff/B4_DEV_boundary_resume_archive_20261118.json`。后续优先核对 17651 和真实账本。若再次有请求边界换接，须区分无物理预留的中断产物与真实响应。B4 开发终态后核对分库效果、源审和曲线，再接已准备的 B5。进入 B5 前可对已定位的运行时暂停缓存缺陷做单独离线修复并重绑未开始的任务。TEST 保持封存。

暂停缓存修复已在隔离副本通过精确重放。它单独归档请求预留前的中断，重试用当前已付响应重现了原始 B4 DEV 解码结果。补丁、重放脚本和哈希见 `handoff/generation_hold_boundary_fix_draft_20261118.json`。待 B4 DEV 结算并完成源快照归档后，再应用修复和重绑未启动的 B5 观察。

## 当前外部对照运行和四臂证据

B4 DEV 原绑定 1530764d… 的前四个臂各完成 80 个来源、384 个原生任务。仅 M1 与双机制的 Diversity 各 14/16，匹配对照各 9/16，官方平衡准确率增量 0.3125，母来源分层区间 [0.0625, 0.5625]。16 个来源均走合成接口，6 个修复的全部局部关系通过独立源审，1 个退化。OpenExempt 两条 M2 对比的 EC 平均 F1 均增 0.07996 [0.00539, 0.16039]，EV 增 0.00634 [−0.02947, 0.03999]。这是保留旧程序的比较，原选择由字面事实拒绝触发。见 `handoff/B4_M1_DEV_two_arm_seal_20261118.json`、`handoff/B4_M1_DEV_source_audit_20261118.json` 及 `handoff/B4_OE_DEV_four_arm_audit_20261118.json`。

原会话 17651 停在外部 schema 的请求边界，77 笔已付响应均结算，无缓存污染。唯一生成会话 55236 已恢复 PARSE。五臂完全结算后，依次归档 58 份源文件，跑 `python -m experiments.convergence_eval_cost_audit --batch 4`，再生成完整 B4 曲线并更新 B5。成本脚本已在 B1/B2 的物理账本复算成功。源快照归档后再将已验证的暂停缓存修复放入代码并重绑未开始的 B5。TEST 封存，Goal active。

交叉投影会话 68045 已终结，8 个新读数、48500 tokens，原生评分完全复用。两程序各识别 4/4 个明示金额。候选引文 0/4 通过，3 条所有权陈述缺源据。旧程序引文 4/4，4 条所有权陈述缺源据。敏感性分析对两程序均保留 2/16 个独立派生签名和 0/2 个共享签名，模型值和选择本身未改变。证据 `handoff/M2_title_partition_signal_audit_20261118.json`。下一诊断 `handoff/m2_oe_conditioned_value_current.json` 已准备，只让模型读派生值，把同一源审 K 提供给两套程序，排除本轮必然触发的字面字段混淆。应在串行空档运行，保留 B4 快照。61 项定向测试通过。

## B4 DEV 完成，唯一在途 B5 观察

外部对照会话 55236 正常终结。原绑定内五臂均有 80 来源、384 个原生任务；58 个源文件已按哈希归档。阶段 121 次物理 Qwen 读取、935794 tokens，耗时 3547.93 执行器秒，保留 6 次长度截断。B4 五臂完整曲线见 `reports/legal_skill_convergence_20261117/paper/figures/DEV_B0_B4.pdf`。原生区间和物理去重成本核验见 `handoff/DEV_B4_native_effects_20261118.json`、`handoff/DEV_B4_physical_cost_audit_20261118.json`。联合臂相对 PARSE 的 Diversity 平衡准确率变化 0.3125 [0.0625, 0.5625]，OpenExempt EC/EV 变化 0.00490/−0.00318，区间跨零。

条件派生量诊断会话 2935 已正常终结。两程序拿到相同 K、共 8 读数，47912 tokens，58 个源文件归档。原生正候选逐例独立通过、共享及固定单解释拒绝；旧程序也四次返回全部明示金额且同样不兼容共享解释。保留这个实际约束分歧，效果归因仍要求在后续新的正向 TRAIN 提案中分辨程序表现。不要原样重跑同一候选。见 `handoff/m2_oe_conditioned_value_current.json`。

暂停缓存修复只在 B4 与条件诊断归档后应用，68 项测试和 2 个子测试通过。B5 旧准备绑定无实际记录，新绑定只改变 `control_programs.py` 的暂停路径。`handoff/B5_observe_generation_hold_rebind_20261118.json` 确认原 16 来源、74 原生任务、五臂 B4 进入技能库、原模型和评分保持一致。唯一生成会话 94033，从 `handoff/formal_B5_observe_current.json` 和 `handoff/run_state.json` 续跑。B5 观察结算后归档并接五臂正式拟合；新 M2 诊断尚未改动训练选择器。TEST 仍封存。

## B5 拟合前向接入源条件比较

两类教师从 B5 开始收到相同的 B4 全额错误反馈，均只包含已测错误及来源关系。继续沿同一 TRAIN 批比较候选和进入程序。OpenExempt 新候选在四个当批原生来源上取得正向总差后，才启用固定小试内同一组四项交叉投影。检查依据为双方拿到的同源事实和相同的派生读数接口。字面通过、成对完整、独立补全支持候选且共享解释只支持进入程序时，记录由共享解释单独产生的拒绝。其余情形沿原字面选择，并记录独立补全及单一解释的结果用于匹配归因。B5 观察的 42 份绑定文件未改动。8 笔既有读数按原始请求内容与物理账本重放通过，70 项定向测试和 2 个子测试通过。详见 `handoff/B5_M2_forward_replay_20261118.json`。

会话 94033 终结，五臂各 16 个来源和 74 项任务均已封存，44 个实际 Qwen 读数共 307726 tokens，42 份观察绑定文件已逐一归档。`handoff/B5_entering_native_comparison_20261118.json` 记录 B4 程序对新 B5 TRAIN 的前向比较。两个 M1 臂各 3/3，对照各 2/3，三条合成读数及修复均通过逐关系源审。OpenExempt EC 和 EV 的匹配平均差分别为 0.168198 和 −0.002232，EC 四例均提升。保留程序仍来自 B4 字面决定。源审回执 `handoff/B5_entering_M1_source_audit_20261118.json`。

从 `handoff/formal_B5_fit_current.json`、`handoff/run_state.json` 续接唯一生成会话 31551。拟合绑定 `4b469fdcda5476dbee3bfc5799e70fd958a2c33f7d2ef87e5ec11c56c7d46fe3` 含 59 个源文件，实际已到普通教师 ContractNLI。先核查真实会话和保留请求，再在 B5 终态归档和审计新候选；之后推进 B6。B5 观测已覆盖累计 80/128，正式更新结算仍 64/128。TEST 未打开，Goal active。

OpenExempt EC 的普通程序有一次长度截断，当例未返回可评分 EC。按原协议计入四例后 F1 增量仍为 0.168198。三组成对可评分结果中，保留程序的平均精确率增加 0.127204，召回率增加 0.333333，F1 增加 0.182597。EV 四例均可评分，平均召回不变。这个拆解从已保存预测用原原生评分复算，零新请求。回执 `handoff/B5_entering_OE_metric_audit_20261118.json`。

## B5 拟合已结算提案与 B8 评分隔离

会话 31551 中普通教师 ContractNLI 提案当批分类 35/51→37/51，先前固定 12 个 TRAIN 来源 106/204→82/204，证据 F1 分别 0.46405→0.37255、0.29301→0.21920。早期回归保护保留程序，两批证据均来自实际已结算读数。普通教师 Diversity 与 MAUD 提案当批原生效用持平，均保留进入程序。ContractNLI 核验见 `handoff/B5_CNI_training_regression_audit_20261118.json`。

预检复现了证据标注题数不等时，等权合同区间的点估计偏离按题原生均值。B8 原生评分仍由独立评分器执行，评分时保存证据 F1 的适用题目范围，供后续直接用封存分数进行按题加权的母来源重采样。此改动只涉及未运行的 TEST 入口和证据复算代码，B5 的 59 份绑定仍一致。B1、B2、B4 旧 DEV 回执精确复算，72 项定向测试及 2 个子测试通过。已重新核对 160 个 TEST 身份与连续账本无交集，TEST 原文及标签保持封存。见 `handoff/B8_evidence_audit_preedit_20261118.json` 和 `handoff/B8_evidence_audit_preflight_20261118.json`。

B5 普通 OpenExempt 提案未通过原生正向门槛。四个来源相对 M2 进入程序均下降，平均差 −0.094659。EC 0.189319→0.015625，EV 0.015625→0。三个完成的 EV 原始响应均只返回一个资产，第四个长度截断。按生产路径恢复枚举字符并解码，结果与原预测一致。提案原生读者含只适用于诊断的分流条件。前向可检验假设是用明确的组件字段触发局部条件，让原生分支保留完整输入资产范围。只在 B5 封存后落实，匹配两教师信息、原生评分和条件投影。回执 `handoff/B5_OE_native_positive_gate_audit_20261118.json`。

会话 31551 在下一个教师请求前正常触发保存边界，46 个 Qwen、6 个教师响应已结算，零在途，59 份绑定源码逐一核验。唯一生成会话 68552 已在原绑定恢复，实际进入 PARSE 教师 Diversity。以 `handoff/formal_B5_fit_current.json`、`handoff/run_state.json`、真实会话和连续账本为准。终态后先归档原拟合和审阅五臂结果，再接原定 B6。边界回执 `handoff/B5_fit_boundary_settled_31551_20261118.json`。公开提交核验至 `9f00e6ae4896519653fd2fd759c78483c1812032`。

## B5 完整更新，B6 观察已运行

会话 68552 正常终结，五臂均已完成前 80/128 个固定 TRAIN 来源及第 5 批更新。B5 拟合各类实付为 71 笔 Qwen、10 笔教师，分别 567750、176913 tokens，59 份源文件已逐一归档。普通教师及 M2 保留五库技能。PARSE 仅采纳 ContractNLI，分类当批 35/51→38/51、前四批 107/204→112/204，证据 F1 当批 0.30642→0.38366、前四批 0.26330→0.29234。M1 时间顺序复算含 12 个固定 TRAIN 来源，普通和现行各 9/12，替代选择 8/12。现行运行六次合成，有四条全关系忠实。回执 `handoff/B5_training_terminal_audit_20261118.json`、`handoff/B5_CNI_PARSE_training_regression_audit_20261118.json` 和 `handoff/M1_incumbent_through_B5_20261118.json`。

唯一生成会话 19830 正在执行 B6 观察。绑定 `a23d04550d6bc43a4bb661c926b2c3b7e7347ebc787514f89de8922709f864d0` 含五个 B5 快照与 42 个观察源文件，顺序仍为原 16 个母来源、74 项任务。继续从 `handoff/formal_B6_observe_current.json` 和 `handoff/run_state.json` 查实际会话。B6 观察终结后先归档，随后用 `python -m experiments.convergence_formal_train_fit prepare --batch 6` 绑定新提案条件。

B6 OpenExempt 拟合已实现两路编译。同一提案的来源所有权规则同时进入原生读者和局部投影读者，局部分流指令只接收带组件字段及独立源审事实的投影输入。两教师收到完全相同的 B5 结果摘要。普通与 M2 仍比较同一提案，PARSE 保留原可逆格式接口。两条教师路径从封存原生预测记录资产数量，再用现有分数决定是否进入局部比较。8 笔 B5 原生与 8 笔 B4 条件投影都按已付原始请求精确重放，75 项定向测试及 2 个子测试通过。新逻辑不在 42 份正在运行的观察文件中。前向绑定和证据见 `handoff/B6_OE_scoped_fit_preflight_v2_20261118.json`。后续只在同一批实测达到原生正向门槛时派发条件投影，继续保留 TEST 隔离。

## B6 已结算的 M1 配对与 B0 参照预检

B6 普通和仅 M1 在已结算的三例 Diversity TRAIN 上均答对。M1 三条实际都用合成读取，局部关系全部经源审通过。零新请求，见 `handoff/B6_entering_M1_pair_audit_20261118.json`。以真实会话和账本等待 B6 五臂终态，再归档并派发已预检的 B6 拟合。

最终 TEST 驱动器已接入固定 B0 推理参照。它在正式 B8 冻结时固定原始初始库、比较数据及源码快照，并在同一 160 个来源上独立封存推理、评分和成本回执。仍保留五个正式 B8 臂。实际 B0 五臂共有程序与原 DEV 回执核对通过，合成预检覆盖 160 个来源及参照请求去重，B4 历史成本回执精确复算，77 项定向测试及 2 个子测试通过。改动在运行中的 42 份 B6 观察绑定之外。真实 TEST 原文及标签保持封存。见 `handoff/B8_initial_reference_preedit_20261118.json` 和 `handoff/B8_initial_reference_preflight_20261118.json`。

B6 原会话 19830 留存 39 个已付响应后在请求边界退出。唯一生成会话 69078 已按原绑定续跑外部对照，42 个源码哈希一致。以实际会话、账本和 `handoff/formal_B6_observe_current.json` 判断终态。B5、B6 的八例新 TRAIN 上，两套前向程序哈希分别一致。按批次分层，保留程序的 EC F1 平均差 0.12190 [0.06583, 0.17673]，七升一平，EV 平均差 −0.01826 [−0.03604, −0.00112]，三降五平。此比较来自 B4 字面事实门槛的保留决定。见 `handoff/B6_observe_boundary_19830_20261118.json`、`handoff/B5_B6_OE_fixed_program_forward_20261118.json`。最终 B0 参照已同步至 `4a2cfb36ce608d9605d8401a1e660ee0d28948de`。

## B6 观察结算，正式拟合运行中

会话 69078 已正常结束。B6 观察五臂各 16 来源、74 原生任务全部封存。45 笔 Qwen 请求共 387024 tokens，换接后仅补六笔未发出的请求，42 份原源码已归档。B6 两组 M1 比较均 3/3 对 3/3，两个匹配 M2 比较的 EC 和 EV 平均差为 0.07560、−0.03429。原生回执 `handoff/B6_entering_native_comparison_20261118.json`。

会话 29252 是唯一生成会话，运行五臂 B6 拟合。从 `handoff/formal_B6_fit_current.json` 和 `handoff/run_state.json` 恢复。新绑定 `a7d0be3e8f17f5f6ddaf7793582f68de5541fc24804956ab5e42f591208c6e30` 含 60 个源码文件，实测 B5 反馈、共享所有权政策字段和原固定条件投影与预检一致。待 OpenExempt 普通新提案结算后，逐视图核对资产覆盖和相对 M2 进入程序的得分。若触发条件投影，核实是否实际改变匹配选择。B6 拟合全结算后归档并接原定 B7。观察累计 96/128，正式更新结算 80/128。TEST 未开封。

## B6 资产覆盖实测及 B7 修订证据

B6 普通 OpenExempt 已实测。八笔原生请求的同一共有所有权规则正确传入，局部分流指令未混入。EC 四例的资产数量符合参考，F1 均值 0.25992，相对 M2 进入程序提高 0.09405。四例 EV 均正常结束且只返回一个资产，F1 均值 0.01471，相对 M2 进入程序下降 0.10100。合计相对 M2 进入程序差 −0.00348，未派发共享投影。回执 `handoff/B6_scoped_fit_ordinary_candidate_audit_20261118.json`。

EV 已实现从公开案情渲染模板提取的资产槽，原生解码区分 `null` 省略和空申报数组。B1–B6 的 24 个 EV 原生参考全部无损回译，一例原生参考确实省略了一个列出的资产。新路径在隔离副本模拟普通与 PARSE 端到端恢复。现有在途 B6 绑定未改动，B6 归档后才接入 B7 和后续阶段。预检 `handoff/B7_EV_inventory_wire_preflight_20261119.json` 与 `handoff/B7_EV_isolated_runtime_preflight_20261119.json`。

B8 DEV 屏蔽在代码中绑定真实教师提案源和预测所用的物理请求。离线复核覆盖 B1–B5 四次联合臂接受的程序版本，以及 B4 联合臂 80 个 DEV 路由。B4 的现有读数无跨库命中。B8 尚待原定 DEV 主比较终态，不用该预检替代最终屏蔽结果。见 `handoff/B8_transfer_provenance_preflight_v2_20261119.json`。

## B6 完整结算，B7 首次观测资产槽

会话 29252 已终态。49 笔 Qwen 和 10 笔教师响应全部结算，分别用 315972、176917 tokens。原 60 份源码均已归档，五臂正式更新累计 96/128。普通教师采纳 MAUD 与 OpenExempt，PARSE 采纳 MAUD，M2 原生门槛保留 OpenExempt 进入程序。B6 第五次可追溯程序更新已从原提案教师回执核验。见 `handoff/B6_training_terminal_audit_20261119.json`。

M1 已复算至 B6。15 个固定前向 TRAIN 来源上，普通和现行各 12/15，替代选择 11/15。现行 9 次合成读取中，7 次全部局部关系获源审支持。见 `handoff/M1_incumbent_through_B6_20261118.json`。

唯一生成会话 6038 已进入 B7。`handoff/formal_B7_observe_current.json` 绑定 `d0ccb8b273b17ff2d195de1f25db13f16e6b495f171e3e39749f05b45bc63927`，原定 16 来源、74 任务，44 份观察文件。B7 的四例公开 EV 均成功绑定资产槽，数量 4、3、3、2，继承的 PARSE 可逆编译也已核对。80 项定向测试与 2 个子测试通过。共同 EV 接口延续至 B7、B8 拟合、B8 DEV 及其屏蔽比较，以及所有五个 TEST 臂和最终静态 B0。B6 原绑定来源保持历史归档。见 `handoff/B7_bound_observe_preflight_20261119.json`。继续核对实际会话，终态归档，再接同一读取接口的 B7 拟合。TEST 保持封存。

B7 首四个普通教师 EV 已结算并复算。之中的四个物理请求均按源文本绑定，四个返回的原生资产键集均与参考完全一致，官方 EV F1 均值 0.11859。回执 `handoff/B7_EV_asset_inventory_actual_common_teacher_skill_learning_20261119.json`，可用 `/tmp/convergence_B7_ev_inventory_actual_20261119.py` 复算普通臂。待其余臂和 B7 拟合，继续核对同源收益与共享选择。公开分支核验至 `0300bfec4cf7a4f3bca7067de3582d271286a151`。

## B7 观察结算及公开辖区约束验证

会话 6038 正常终结。五臂各封存 B7 原定 16 个来源、74 个任务，44 笔 Qwen 共 354745 tokens，44 份绑定文件已归档。观察累计 112/128，正式更新累计 96/128。两组 M1 Diversity 比较均为 3/3 对 3/3。仅 M1 三次均实际使用合成接口，各局部关系全部通过源审。两组匹配 OpenExempt 比较的 EC、EV F1 均差为 −0.00666、+0.01357。五臂的每例 EV 均返还完整参考资产集合，合计 12 个独立物理 EV 读数。见 `handoff/B7_entering_native_comparison_20261119.json` 和 `handoff/B7_completed_and_B8_jurisdiction_rehearsal_20261119.json`。

对已保存的 B7 EV 预测仅删除案情明示辖区之外的引文，普通臂 F1 0.11859→0.28203，M2 0.13217→0.25020，PARSE 0.14763→0.31984，三臂召回均保持原值。再去掉超过案情资产估值或非正值的索赔，三个 F1 分别为 0.31389、0.27103、0.33770。以上为固定已付响应的离线分解，真实生成收益待匹配比较。正常范围检查覆盖 B1–B7 28 个 EC、28 个 EV TRAIN 原生参考。其中 180 个参考 EV 索赔均不超过案情资产值。

公开辖区枚举仅在隔离草稿实现。56 个参考均经普通及 PARSE 无损回译，引文范围从 71 个缩至 9–23 个。冻结解码后端已用原有 Unicode 枚举恢复和字段顺序验证准入及排除，合成账本两条生产路径也已通过。后端接受小数形式 780.15 越过整数上界 780，故金额没有作为硬语法约束部署。源码和复算脚本在 `artifacts/legal_skill_convergence_20261117/B8_OE_public_jurisdiction_preflight_20261119/source_snapshot` 保留十份哈希。待 B7 实测新提案及 B8 正式接入审查；未更改 B7 代码。

B7 拟合会话 8196 绑定 `ca1b6269b98871ac5eaa2b5731ed8f5ab1e981d24ded2ab42f918de53776f53b` 的 62 份文件和同一资产槽。连接受限的启动在执行器就绪检查退出，核对零账本记录后，8196 已在原绑定进入真实拟合。以 `handoff/formal_B7_fit_current.json`、实际会话与账本为准。继续观察普通 OpenExempt 新提案的 EC、EV 原生门槛及条件投影的真实选择。TEST 保持封存，Goal active。

## B7 原生正提案和共享选择的实测分解

B7 普通 OpenExempt 提案的八笔原生响应均正常结束，四个 EC 和四个 EV 均返回参考数量的资产。相对 M2 进入程序，EC F1 从 0.24505 升至 0.29606，EV 从 0.13217 升至 0.16865，合计平均收益 0.04375。普通教师根据其进入程序采纳候选，原生收益 0.04721。见 `handoff/B7_scoped_fit_ordinary_candidate_audit_20261119.json`。

固定条件验证使用十笔实际响应，其中两笔字面读取和四笔候选分量在 B7 新发，四笔进入程序分量精确复用。两个字面读取均正常结束且所有权、明示估值均返回 null。候选和进入程序的四条派生读数同为 1450、1550、1450、1550。独立补全可解释这组分量，共享和固定单一解释均无法解释。匹配选择因字面正监督不足保留进入程序，共享门未单独改变选择。字面和条件投影使用各自绑定的 TRAIN 母来源。见 `handoff/B7_OE_shared_selection_audit_20261119.json`。

B8 的隔离实现已接通固定最后一批观察、拟合、DEV、跨库屏蔽和封存 TEST 的共同公开辖区规则。仅新版 M2 提案的字面读取采用专用指令，分别读取明示金额和所有权；原生任务指导和派生分量指导保留各自接口。B8 四个公开 TRAIN 事实的 EC/EV 均成功缩小引文列表，数量为 21、21、16、21，未读入本批评分参考。87 项定向测试和 2 个子测试通过。12 份隔离实现及改前原文件均已按哈希归档。见 `handoff/B8_scoped_runtime_stage_wiring_preflight_20261119.json`。须先核对会话 8196 的终态并归档 62 份 B7 源码，之后应用已检验的 B8 代码。TEST 仍封存。

## B7 完整结算，B8 最后一批观察已运行

B7 五臂完成前 112/128 个固定来源的正式拟合。55 笔 Qwen 和 10 笔教师请求均已结算，分别使用 326795、177537 tokens。62 份原绑定源码已封存。普通和 PARSE 教师各采纳一个 OpenExempt 更新，M2 保留进入程序。最终 B7 选择回执与先前十笔投影逐字节复算一致。M1 的 18 个前向 Diversity TRAIN 来源，普通和现行各 15/18，替代选择 14/18。现行 12 次合成读取中 10 次的全部关系通过源审。B1–B7 的三次 OpenExempt 原生正提案中两次因字面断言被拒，B7 因字面读数全空，同一共享规则尚未独立改变选择。见 `handoff/B7_training_terminal_audit_20261119.json`、`handoff/M1_incumbent_through_B7_20261118.json` 和 `handoff/B1_B7_OpenExempt_selection_accounting_20261119.json`。

B8 边界后已部署 12 份经过隔离验证的文件，改前和改后均有哈希。实际工作树 87 项定向测试和 2 个子测试通过，普通及 PARSE 生产冒烟通过。B8 固定四个 OpenExempt TRAIN 的两个视图均绑定公开辖区；四案允许的引文数为 21、21、16、21，继承的真实 PARSE 技能库已逐例编译。公开约束适用于五臂、DEV 屏蔽和最终同条件 B0 参照。专用字面读取只在 B8 拟合的新候选中触发。见 `handoff/B8_scoped_runtime_applied_20261119.json` 与 `handoff/B8_bound_observe_preflight_20261119.json`。

唯一生成会话 42498 正在执行 B8 固定 16 来源、74 项任务的观察。绑定 `b7e11b4eb48dc703375ddb0eafb9bc391b274682ef8160e56184aa495d65d4e6` 的 45 份源码已核对。按 `handoff/formal_B8_observe_current.json`、`handoff/run_state.json`、实际会话和连续账本续接。观察封存后归档原绑定，继续原定五臂 B8 拟合、固定 DEV 曲线与跨库屏蔽。TEST 原文和标签仍封存。

## B8 五臂观察结算，最后一批正式拟合

会话 42498 已正常结束。五臂各封存最后 16 个固定 TRAIN 来源及 74 项原生任务，累计观察 128/128。44 笔 Qwen 请求共 301744 tokens，45 份绑定源码均已归档。五臂 OpenExempt 的四个 EC 和四个 EV 均按公开辖区执行，共 24 个独立原生响应。EV 五臂全数返回参考资产键，EC 每臂仅一例返回完整参考资产键。普通、M2、PARSE 的 EC F1 分别为 0.45625、0.59792、0.57024，EV F1 分别为 0.47500、0.43750、0.41667。B8 前向程序沿用刚封存的 B7 实际决策，跨批次读数使用不同案情。见 `handoff/B8_observe_scope_and_coverage_20261119.json` 和 `handoff/B8_entering_native_comparison_20261119.json`。

Diversity 两组配对均为 M1 3/3、匹配对照 2/3，一例改善、两例持平。仅 M1 的三例均实际运行合成接口，所有局部关系通过源审。改善的一例包含四个州籍匹配和两个金额条款。见 `handoff/B8_entering_M1_pair_audit_20261119.json`。

唯一生成会话 41841 已开始 B8 五臂拟合，绑定为 `7dd5b245f42eeb90c2c90d8d962ce5f7c120d696230a7d05c0b2fdbcae042943`，核对 63 份源码、同一教师和执行器、公开辖区及专用字面读取。以 `handoff/formal_B8_fit_current.json`、实际会话及连续账本续接。正式拟合至 112/128，等 B8 终态后封存全部 128，再执行固定五臂 DEV 和跨库屏蔽。B8 原生正提案出现时，核对字面读取是否恢复明示金额，及配对共享门的实际选择。TEST 未冻结或打开。见 `handoff/B8_bound_fit_preflight_20261119.json`。

B8 DEV 图的两个 OpenExempt 面板单独显示采用修订输入的 B8 端点。B4 原始九指标数据与 600 dpi PNG 重绘逐像素一致。新端点布局已用合成点演练，最终图按 B8 封存分数生成。见 `handoff/B8_DEV_scope_plot_preflight_20261119.json`。

## B8 原生正提案、字面恢复与共享条件读数

B8 普通 OpenExempt 候选的八笔原生读数均正常结束。相对 M2 进入程序，EC F1 变化 −0.00714，EV F1 提高 0.05000，平均原生收益 0.02143。两个字面投影从原文恢复金额 115、215，保持所有权未知，字面门通过。候选与进入程序在固定条件投影中的读数仍同为 1450、1550、1450、1550。原生、字面和独立补全选择支持候选，共享与固定单一解释均拒绝它，但进入程序也无共享见证。按既定配对门，保护性拒绝未独立触发，复算决定为采纳。十笔投影逐字节复算，四笔进入程序响应精确复用，六笔为 B8 新响应。见 `handoff/B8_scoped_fit_ordinary_candidate_audit_20261119.json`、`handoff/B8_OE_shared_selection_audit_20261119.json`。待五臂终态再核对实际技能库决定。

为定位这组全额复制，已实现同两个程序、同固定 TRAIN 母来源和同四个条件输入的标签探针。从返回金额改为选择全额、零额、未知，经过源审的金额只用于确定性还原，两个程序收到相同的新契约。合成回执验证可区分一组一致分量与两边全额；现网解码语法接受三个标签并拒绝直接返回数字。它只使用原小试范围和 B8 已结算原生得分。须在当前拟合终止并归档后补做一次成对诊断；正式 B8 库不受该诊断改写。见 `handoff/B8_OE_typed_component_preflight_20261119.json`。

新增论文评测表生成器，已由 B4 真实五臂证据复算 10 项原生指标、五组固定对照的母来源配对区间、完整来源数，以及逐臂实付调用引用、tokens、耗时。四个 Markdown 表均通过渲染，B8 DEV 与固定 TEST 终态将沿用同一核对。见 `handoff/B8_evaluation_tables_rehearsal_B4_20261119.json`。会话 41841 仍是唯一生成任务，63 份 B8 绑定保持不变。TEST 保持封存。

## B8 训练完整封存，部分共享见证与固定 DEV

会话 41841 已正常结算。原定五臂各完成全部 128 个 TRAIN 来源及八批更新，40 份历史更新回执齐全。B8 拟合为 51 笔 Qwen 与 10 笔教师，分别用 302331、177018 tokens，63 份源码原样归档。现行 M1 的逐批前向 Diversity TRAIN 正确数为 18/21，普通及另一固定选择规则均为 17/21。现行 15 次合成读取中 13 次全部关系经源审支持。见 `handoff/B8_training_terminal_audit_20261119.json`、`handoff/M1_incumbent_through_B8_20261118.json`。

五臂库的实际因子已逐批核对。B7 唯一不同的 M2 程序位于 OpenExempt，B8 普通与 M2 采纳同一候选，因此 M2 对普通、联合对 M1 两对的全部程序、接口和格式提案相同，差别只在臂身份和训练记录。B8 固定 DEV 保留原比较，后续用实际预测和物理请求核验这一结构结论。见 `handoff/B8_final_library_factor_audit_20261119.json`。

固定 TRAIN 标签探针的八笔 Qwen 读数已全部结算，共 47500 tokens，64 份源码归档。候选读数依次为未知、0、0、未知，进入程序为 0、0、0、0。逐笔请求原样复核。候选仅保留两种共享签名中的一个，任一有值的零额槽即可排除另一个；进入程序的全零不留下共享签名。逐案例独立补全分别允许 4 项和 1 项签名，固定单一解释均不接受。两个未知保留为缺测，实际定案仍按所有四值可见的旧门，普通原生选择也采纳候选。该观测证明部分读数能提供额外的区分证据，M2 的独立原生收益仍未建立。见 `handoff/B8_OE_typed_partial_shared_witness_20261119.json`。

补查 OpenExempt 同案的 EC/EV，32 个 TRAIN 参考均满足同资产的正额 EV 引文属于 EC。B8 实测候选的 25 条正额 EV 资产引文对中，15 对的资产在 EC 省略，另 5 对未出现在 EC 对该资产的已答引文中。离线按 EC 过滤 EV 使候选 EV F1 从 0.48750 降到 0.18125；按 EV 补充 EC 使 EC F1 从 0.59077 降到 0.57946，保留原始结果，不做强制合并。只比较两视图公开资产估值和辖区一致的事实，原文表述可不同。见 `handoff/B8_OE_native_cross_view_diagnostic_aligned_facts_20261119.json`。

唯一生成会话 13559 已运行五臂固定 80 来源的 B8 DEV，绑定 `db6b0eba1553f5030b93e50769d23a2acaf7dbbc8d1c5f8b65f27969ae5db0ac`，67 份源码、五个原 DEV 重放根已核验。TEST 160 个身份与连续账本和教师回执全部来源引用交集为零，原文及标签保持封存。继续按真实会话结算固定 DEV、曲线、跨库屏蔽及后续协议。见 `handoff/B8_bound_DEV_preflight_20261119.json` 与 `handoff/B8_prefreeze_exposure_metadata_audit_20261119.json`。

## B8 DEV 四臂精确对照与 M2 反馈配对预检

B8 DEV 普通、仅 M1、仅 M2、联合四臂的各 80 个 DEV 母来源均已结算，外部 PARSE 仍运行。M2 两组对照逐项 384 个原生分数、80 份原生预测和各 96 个引用的物理响应均相同，实测与封存库因子一致。见 `handoff/B8_M2_DEV_exact_equivalence_20261119.json`。

M1 的两组对照均在 Diversity 上从 9/16 提高到 14/16 的平衡准确率，差 0.3125，原母来源配对分层区间 [0.0625, 0.5625]。仅 M1 的 16 例均执行了合成接口，14 例的全部局部关系通过源审。六个原生修正例均通过逐关系源审，另有一个退化。B4 与 B8 的四个对应臂在这 16 个来源上均使用相同物理读数，属于同一固定 DEV 证据。见 `handoff/B8_M1_DEV_two_arm_balanced_accuracy_20261119.json`、`handoff/B8_M1_DEV_source_audit_20261118.json` 和 `handoff/B4_B8_Diversity_DEV_source_overlap_20261119.json`。

M2 新成对验证已绑定原定四个 OpenExempt TRAIN 小试母来源、八项原生任务和同一 B8 起始程序。两路教师各出一个只修改所有权政策的提案。公共事实、八笔既有投影、单槽允许值、基线原生统计和可执行框架相同，变化仅为逐例补全或共享解释的反馈。预检复算候选的唯一共享见证、进入程序的零共享见证及全未知时两个见证均保留；原文字面仍独立核验。主比较为相同原生输入上的 EC/EV 及同候选集上的选择差异。未改 B8 库或当前 DEV 绑定，尚未派发这项配对的请求。见 `handoff/B8_OE_feedback_pair_current.json`、`handoff/B8_OE_feedback_pair_final_preflight_20261119.json`。当前会话 13559 仍是唯一生成阶段，TEST 原文及标签保持封存。

## B8 DEV 与跨库屏蔽结算，M2 配对运行

会话 13559 正常结算。原定五臂各完成固定 DEV 的 80 个母来源与 384 个原生计分单元，B8 新增 112 笔本地推理、846531 tokens，均正常结束。67 份原绑定源码已归档。Diversity 两组 M1 消融及联合对 PARSE 的平衡准确率差均为 +31.25 个百分点，母来源配对分层 95% 区间 [6.25, 56.25]。联合对 PARSE 的 ContractNLI 证据 F1 差为 +9.91 个百分点 [4.38, 15.42]，四个内部臂得分相同。OpenExempt 两项联合对 PARSE 的区间均跨零。PARSE 的 MAUD knowledge definition 得分领先 12.50 个百分点。完整曲线与原生分数、区间、成本表已复算并纳入论文稿。见 `handoff/formal_B8_DEV_current.json`、`handoff/DEV_B8_physical_cost_audit_20261118.json` 和 `paper/tables/DEV_B8_NATIVE_TABLES.md`。

会话 6109 的 B8 DEV 跨库屏蔽正常结算，69 份绑定源码已归档。屏蔽前后 80 例执行轨迹、384 个原生计分及引用的 96 个物理响应逐项一致。五库均未观察到跨库技能命中。新增请求及 tokens 均为零。见 `handoff/B8_DEV_transfer_terminal_audit_20261119.json`。

唯一生成会话 63369 已启动配对 TRAIN 验证，绑定 `601f652e0c7249775ed5bbbe4b02ba9bf41f39c584ff8e3cbae2871f80ef59a3`，65 份源码已核验。用 `handoff/B8_OE_feedback_pair_current.json`、实际会话和原账本核对后续，待结算后归档并复算同案两种原生 F1、共同候选集与共享见证。八批封存库和历史 DEV 保留，TEST 原文、标签仍封存。

## OpenExempt 共享反馈配对结算及分量读法复核

会话 63369 已结算，65 份绑定源码原样归档。两个教师仅收到不同的解释反馈，四个固定 OpenExempt TRAIN 案例与两种原生输入相同。共享反馈与独立反馈提案的 EC F1 分别为 0.35833 和 0.27500，EV F1 均为 0.35833。B8 进入程序为 EC 0.27500、EV 0.40417。共享提案对进入程序的两项平均变化为 +0.01875。差异来自一例的一条正确法条引用。用公开源文的精确资产描述和金额后缀复算，两臂差保持 +0.08333。正式原生分数原样保留。

共享反馈提案通过字面和逐例补全检查。四个条件分量读数为零、零、零、未知，保留 2/16 个独立签名和 0/2 个共享签名。共享选择器与固定单一解释均未采纳这条提案。该批消耗 30 笔 Qwen、223122 tokens 和 2 笔教师、35560 tokens。见 `handoff/B8_OE_feedback_pair_terminal_audit_20261119.json`、`handoff/B8_OE_feedback_EC_alias_audit_20261119.json`。

唯一生成会话 41540 复核重复零额是否源于将同一文本的两个分量分别读取。三个原已评分程序只改共同的投影读法，分别读取原文本和数额编辑文本。每份文本同时读转发与保留分量，语法接受全额、零额、未知的九个组合，由外部原共享签名验证。全未知保留两种解释，双零保留零种，皆不会作为有区分力的见证。六次 Qwen 计划已绑定 `f9f58c8addac8862d514f4db6a506ca52e81b2a78769e0fd27e33c33aca1561f`。待实际终态比较两文本及三程序原始读数，原生分数不因投影读法复核重计。TEST 原文与标签保持封存。见 `handoff/B8_OE_joint_component_current.json`、`handoff/B8_OE_joint_component_preflight_20261119.json`。

## 正式 B8 五库 TEST 已冻结并启动

会话 41540 已正常结算。六笔 Qwen 共 35852 tokens，66 份绑定源码归档。三个程序各自返回四个未知分量，保留 2/2 共享解释和 16/16 独立补全。联合读取消除了双零断言，三程序的实际读数一致，未形成可用于独立更新的区分证据。先前共享反馈的单条 EC 引文改善仍记录为固定 TRAIN 结果。TEST 采用既定 B8 设置，含五个正式训练臂和静态 B0 推理参照。

最新冻结前身份复核含连续账本 13967 条、491 份教师回执及其 3118 个来源引用，160 个 TEST 身份零交集，历史曝光回执哈希一致。会话 50891 已完成仅身份元数据的冻结准备，库选择 `7aeb014317fe3e7892d7a53b770a2a9d3c5acf837afd38a9949538c5fb172817`，执行绑定 `6be2912140323eab28a30a416ea5e4054517eeda4c1843527b7b6d70a79eaada`，72 份现行与封存运行文件逐一核对。见 `handoff/B8_final_freeze_decision_20261119.json` 和 `handoff/B8_verified_frozen_TEST_binding_20261119.json`。

会话 81580 为唯一活动生成阶段，已按冻结绑定启动 160 个 TEST 母来源，每库 32 个。正式推理第一次原文访问已登记。每臂封存全部预测后评分，不以 TEST 内容调整代码、技能库或对照。核对 `handoff/formal_B8_TEST_current.json`、实际会话、账本和访问回执。受绑定文件继续保持原样，进度只写非绑定记录。完成后按同一阶段复算五库原生指标、独立消融、强对照、静态 B0 及成本，再完成论文。

终态分析入口已准备为 `python -m experiments.convergence_test_mechanism_audit`，五正式臂及静态参照结算前拒绝运行。旧 B8 DEV 的预测封印、M2 两组精确等价和源忠实性汇总已用于离线核对。该入口读取封存预测与每库汇总，复核两组 M1 的逐关系来源和两组 M2 的预测与物理响应，并复算联合对静态 B0 的原生指标区间。该脚本不属于活动推理绑定。

## 固定小试同语法对照与八批更新核对

在 `m1_same_grammar_controls_prepared.json` 的原设计下，四个固定 Diversity TRAIN 小试来源已用 B8 封存候选读数逐源留一。固定坐标、静态最短 schema、仅依据原生分数的搜索、以及源忠实性搜索均得到 2/4 原生正确和 2/4 完整源忠实。两种学习选择器四案均选中同一候选。三案各有两份兼容校准来源，一案均退回固定接口。四种对照引用的既有物理读数并集为 10。无新增请求。见 `handoff/B8_M1_pilot_same_grammar_terminal_audit_20261119.json`。

八批训练的实际决策与保存的技能库逐批复核。普通教师与 PARSE 各测 40 个提案，最终分别采纳 10 和 8 个。当前批原生得分退化的提案分别为 9 和 16 个，两臂各有一个当前批提升被先前 TRAIN 合同回归检查拒绝。M2 条件保存了 6 次实际程序变更，13 个在关系作用域内的数据集批次中，没有一次更新决定单独由共享解释拒绝改变。见 `handoff/B8_training_update_decision_accounting_20261119.json`，离线入口为 `python -m experiments.convergence_train_update_audit`。

论文稿按 RQ1–RQ5 组织原生结果、学习曲线、两项独立消融与跨库复用证据。保留细粒度 TRAIN 诊断与旧结果于附录，加入可追溯的同语法对照与训练决策汇总，并核对相关工作及五库的一手引用。此轮离线分析未读取 TEST 内容或标签。唯一 TEST 会话仍为 81580，当前预测和账本以 `handoff/run_state.json` 为准。

## TEST 评分依赖恢复与普通教师臂封存

会话 81580 在普通教师臂完整封存 160 份预测并结算 192 笔物理响应后退出。第一次原生评分访问已登记。RuleArena 原生评分器导入时缺少 pandas，评分文件尚未写出。经核对，原评分器查找 `.local-tools/rr-v2-deps`，归档中已有其依赖闭包。恢复该本地解析路径，按历史清单核实 2803 个文件哈希，包括 pandas 2.3.3。法条、预测、72 份冻结绑定、评分代码和 TEST 名册保持原样。合成票价输入运行通过。见 `handoff/B8_TEST_original_scoring_dependency_recovery_20261119.json`。

会话 82357 已按原冻结绑定接续。普通教师臂沿用同一预测封印与 192 笔已结算响应，五库原生评分回执已齐，首臂评分封存。当前唯一活动生成会话为 82357，已进入仅 M1 臂。恢复时以 `handoff/formal_B8_TEST_current.json`、实际会话、账本和 `handoff/B8_TEST_original_scoring_dependency_resumed_20261119.json` 为准，旧会话 81580 已终止。正式 TEST 数值待五臂与静态参照全部结算后提交。

## 签名回放与原生覆盖补表

复用原物理 TRAIN 投影，已将 M2 签名审计扩至 B8。六个原生正收益条件中无独立共享解释拒绝。三个所有权条件移除被独立源审否决的字面断言后，均重新兼容 2/2 共享签名；受控金额条件的原始读数也无法通过逐例独立补全。B7 与 B8 的字面投影对两个所有权解释均兼容。这是原读数的敏感性复算，保留原生分数和实际程序选择。见 `handoff/M2_signature_through_B8_20261118.json`。

已由五臂封存 B8 DEV 逐项复算全量原生覆盖和 OpenExempt 官方次指标。五臂均处理 384/384 原生计分单元，无回退。联合臂与 PARSE 的 EV MARE 分别为 2.588、0.240，两臂各有 16/16 个官方值。论文沿用固定全队列的主 F1 口径。测试补表的同一入口为 `python -m experiments.convergence_eval_coverage --partition test`，只在五臂和静态参照终态后运行。见 `handoff/DEV_B8_coverage.json`。当前评分依赖已恢复，测试运行状态仍按实际会话 82357 与账本核实。

会话 82357 下的普通教师、仅 M1、仅 M2 和联合四臂均已封存各 160 份预测与评分文件。PARSE 启动时 TEST 累计 224 笔物理推理。续接该会话的 PARSE 臂及静态 B0 参照，绑定保持 `6be2912140323eab28a30a416ea5e4054517eeda4c1843527b7b6d70a79eaada`。见 `handoff/B8_TEST_internal_arms_sealed_20261119.json`。补表、TRAIN 审计与稿件已核验远端 `e2fc546556e5a397a589b3059f1d86a9b3e8cd43`。

## 方法图与冻结审计复现

论文已加入 M1/M2 方法图，展示固定消费者的等价检查与共享解释对允许签名的约束。两例均为示意。矢量 PDF 无嵌入位图，600 dpi PNG 为 4500×2334，独立重绘逐字节一致。原生推理与评分未改动。详见 `handoff/method_overview_audit_20261119.json`。附录记录冻结范围、原评分依赖恢复、五项终态复算命令以及公开 DEV 证据回放范围。

## 冻结 TEST 汇总证据打包

新增 `python -m experiments.convergence_test_evidence_manifest`。它将五臂和静态 B0 的技能库哈希、预测封印、原生评分、成本和各库评分回执绑定到同一终态。输出论文的原生总表、覆盖表、机制汇总及哈希索引。已在四个封存内部臂验证 640 个预测、3072 个原生计分项及实际技能库选择，未提取成绩数值。原始题文、标签、预测和账本留存在本地。

主体推理仍使用会话 82357。唯一离线分析会话 77390 已启动，于该冻结绑定写出终态且账本结算后执行原生效应、物理成本、覆盖、机制、建表和索引。它不调用模型、也不推送。终态后先核对 77390 和 `handoff/B8_TEST_offline_analysis_completed_20261119.json`，再按回执补做缺失项。

已用封存预测核对两组 M2 配对。M2 对普通教师、联合对仅 M1，各 160/160 个母来源的物理响应集合一致，768/768 个原生输出逐项一致。核对未读取评分文件或标签。正式评分矩阵仍待 PARSE 和静态 B0 结算。见 `handoff/B8_TEST_M2_internal_prediction_equivalence_20261119.json`。索引代码与复现说明已核验远端 `d0a0f750babf327d439b5240d3aaf7ba82912b6c`。

## 五正式臂评分已封存，静态 B0 在运行

在连续账本快照中，冻结边界为第 13967 行。边界前零 TEST 名册交集；边界后所见 317 笔均使用原冻结 TEST 命名空间与执行角色，无教师、TRAIN 或 DEV 请求，也无名册外请求。72 个运行文件和读文、评分访问回执已核对。该回执是运行中快照。见 `handoff/B8_TEST_exposure_ledger_inflight_20261119.json`。

会话 82357 已完成普通教师、仅 M1、仅 M2、联合、PARSE 五臂。独立核对五臂总计 800 个封存预测和 3840 个原生计分项的技能库与封印。静态 B0 已用原批次 0 的快照启动，前 3 个预测的库哈希与预先封存选择一致。见 `handoff/B8_TEST_five_formal_arms_static_started_20261119.json`。终态核对继续使用原会话 82357 和离线分析会话 77390。

对照原协议的十项交付要求，已复核全量 128 个 TRAIN 来源及各臂共 40 份批次回执、固定 20 例小试、五个 DEV 检查点的 25 份评分封印和联合作用域复用对照。DEV 共 9600 个计分项，全部绑定冻结前同一来源队列；PARSE 锁定回执与 B0 预登记选择的规范哈希一致。核验未使用 TEST 标签，完整指标和研究判定须等静态参照和终态分析。见 `handoff/B8_TEST_delivery_prerequisite_audit_20261119.json`。

## 五臂封存结果的内部复核

固定的五个 TEST 臂已复核同一组 160 个母来源和每臂 768 个原生任务。Diversity 原生准确率在两组 M1 消融中均由 25/32 变为 26/32，6 题修正、5 题退化。两组 M1 臂的 32 题均实际走合成接口，无回退。22 题通过所有局部关系的原文核查，覆盖全部 6 题修正；5 题退化均有至少一项未通过。两组 M2 消融的全部已封存原生分数与对应预测一致。分层区间和 B0 对比以整组终态复算为准。

内部回执为 `handoff/B8_TEST_five_arm_native_preview_20261119.json` 和 `handoff/B8_TEST_internal_M1_source_fidelity_20261119.json`。仅使用冻结后的评分成品及 M1 原文核验所需材料；未另读原生标签文件或触发新的模型请求。主会话 82357 继续完成静态 B0，离线会话 77390 等待整组终态。

## 冻结 TEST 结算与研究结论

会话 82357 和终态分析会话 77390 均正常退出。冻结 TEST 包含 5 个正式臂和静态 B0，均覆盖原定 160 个独立母来源（每库 32），每条件封存 768 个原生任务。480 笔物理执行全部结算，共 3,102,630 tokens，累计执行 5,161.9 秒。冻结前后分别核对账本第 13967、14447 行边界和全部 72 个运行文件。冻结前零 TEST 身份交集，冻结后所有请求均属本次 TEST 执行，无教师请求或训练、开发请求。曝光复核及终态产物分别见 `handoff/B8_TEST_exposure_ledger_terminal_20261119.json` 和 `handoff/B8_TEST_offline_analysis_completed_20261119.json`。

- **M1。** 两组消融及与 PARSE 的比较均为 Diversity balanced accuracy 70.83%→83.33%，差值 +12.50 个百分点，母来源分层配对 95% 区间 [−5.00, 30.00]。准确率 25/32→26/32。6 道修正题的所有局部关系通过原文核验，5 道退化题均含不受原文支持的 claim 关系。该测试支持逐题机制归因，整体提升仍不确定。
- **M2。** 两组消融均有 768/768 个原生输出与 160/160 个物理响应集合逐项相同。完整 TRAIN 的 13 个具备关系证书的决策中，单独归因于共享解释的否决为零次。共享反馈的小试取得单条正确引文，但提案无法满足共享解释，最终测试没有可归因的原生提升。
- **强对照和静态参照。** 相对 PARSE，联合臂 ContractNLI evidence F1 提高 7.02 个百分点 [2.43, 11.85]，MAUD 的 negative-interim covenant 提高 12.50 [3.12, 25.00]。四个内部臂在这两项一致。相对静态 B0，联合臂 ContractNLI 分类准确率提高 4.96 [1.29, 9.01]，evidence F1 提高 10.52 [6.05, 15.94]。两组结果衡量系统与训练基线差异。

128 来源八批训练、DEV 曲线、五库冻结 TEST、独立消融、锁定强对照、跨库屏蔽对照和论文初稿均已落盘。两项方法分别取得可靠独立增益的研究目标尚未达成。保留冻结版本、原始证据与暴露记录。当前 TRAIN/DEV 已核对的失败不足以支持新的实质修订，原冻结 TEST 继续作为本次正式终验。

[论文初稿](../reports/legal_skill_convergence_20261117/paper/METHODS_AND_DEVELOPMENT_RESULTS.md) · [五库原生指标与对照](../reports/legal_skill_convergence_20261117/paper/tables/TEST_B8_NATIVE_TABLES.md) · [源忠实及 M2 机制证据](../reports/legal_skill_convergence_20261117/paper/tables/TEST_B8_MECHANISM_AUDIT.json) · [结果封印索引](../reports/legal_skill_convergence_20261117/paper/tables/TEST_B8_EVIDENCE_MANIFEST.json)

## 封存交付后的 TRAIN 路由复核

复用 96 笔原始 Diversity TRAIN 读数，在已定的 21 个前向来源上逐批核验。现行 M1 答对 18/21，普通程序答对 17/21。3 道现行错题中，2 道有其他合成候选给出源忠实的正确答案，1 道由普通程序答对。逐题事后选取的上界为 21/21。存在正确合成候选的两题都只有 4 个已匹配的历史校准来源。

三条重放均只按当批之前的 TRAIN 证据作选择。把校准中的固定读器与实际普通程序分开比较后，仅更换有正向配对依据的固定路由，得 19/21；多出的 1 题来自固定读器。按州籍配对数和诉求条款的绑定规模限制校准，同 21 题得 16/21。允许经源审核的局部子集单独支持原生输出时得 17/21。三项均未进入生产路由。M2 延续原签名审计的结果，现有六组原生正收益条件中尚无能独立改变选择的共享拒绝。

脚本及结果按哈希保存在 `postfreeze_TRAIN_routing_20261119/`，入口为 `handoff/B8_postfreeze_TRAIN_routing_20261119.json`。复核只读原 TRAIN，不读 DEV 或 TEST；连续账本仍停在 14447 行，无在途请求，72 个冻结文件校验一致。

## M2 合同作用域的 TRAIN 证据复核

以锁定 MAUD TRAIN 母合同的原始归档和已结算源审为准，定位了早先节选未覆盖的 3 处内部引用锚点。原源审的两段输入已复核，一段可逐字在母合同中定位，另一段去掉原生页码附注并归一化空白后有唯一位置。全文中的疫情关键词集中在重大不利影响定义处。第 5.2(iii) 节的已审局部同意豁免条款也已定位；该条款的外部法律触发条件和原审缺少的附件仍无独立来源证书。已定位的引用未建立可用于 M2 的多值作用域解释。

复算四个锁定 MAUD TRAIN 母来源的可逆角色改名控制，逐笔比对了 16 个原执行器响应。普通程序和原生正向提案各有 12/12 个原生输出在改名前后逐项一致，提案在改名后的原生分数仍为 9/12，普通程序为 8/12。这组真实响应无法通过角色不变性区分两种更新选择。

回执入口为 `handoff/B8_postfreeze_M2_MAUD_source_scope_20261119.json`，并带有脚本与源证据哈希。复核只使用原 TRAIN，新增调用为零，账本第 14447 行无在途，72 个冻结运行文件已复核。

## 独立验证的来源容量核对

连续账本逐笔核验了已提交的 480 笔 TEST 请求，五库各 32 个、共 160 个母来源全部进入曝光登记。固定协议要求每库 32 个独立母来源。原 MAUD 候选库存 87 个身份中，80 个已经由历史记录、原划分或本次 TEST 排除。合并已知重复边后，原库存中待复审的未曝光母来源最多还有 7 个。原 ContractNLI 候选池最多还剩 25 个组。两者都低于协议配额。上界仅覆盖原协议库存，不代表公开语料库全量剩余数。

交付后的两轮 TRAIN 续查分别核对了 M1 路由和 M2 合同作用域。前者的单题改善来自固定读器，后者的 12 个原生输出在普通程序和候选程序各自的角色改名前后全部一致。冻结终验仍未支持两项可靠独立收益。现有库存无法按同一协议锁定新的独立验证队列，已完成的 TEST 保留其原冻结版本与曝光事实。

复算入口为 `handoff/B8_postfreeze_confirmation_capacity_20261119.json`，含分析脚本、原清单、协议、近重复记录和终态哈希。容量核对只用身份元数据与账本，不读取 TEST 题文或标签，新增模型调用为零。
